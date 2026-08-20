"""CRT-3X9D — the critic-active session-mutation guard.

The Critic is documented as unable to mutate the session it reviews, but a
coordinator subagent (spawned via `Agent`, which does not inherit the skill's
restricted allow-list) ran `prawduct-hook clear` and clobbered the session under
review. The fix enforces the invariant at the mutation site: while a review is
active (a `.critic-active` marker), a bare `prawduct-hook clear` refuses; the
genuine SessionStart (`clear --session-start`), `--force`, a stale marker, and no
marker all proceed. The design is crash-resilient — a marker self-corrects via
TTL expiry, a session-start sweep, and an explicit override.

Two layers:
  * Unit — lib/critic_marker (write/clear/review_active + TTL + fallbacks).
  * Behavioral — the real CLI via subprocess (the reviewer's actual attack path).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from lib import critic_consolidate as cc  # noqa: E402
from lib import critic_marker as cm  # noqa: E402

# Reuse the proven plugin-runtime subprocess harness (same tests/ dir → importable
# under pytest's prepend import mode).
from test_plugin_runtime import run_plugin_hook  # noqa: E402


def _prawduct(tmp_path: Path) -> Path:
    p = tmp_path / ".prawduct"
    (p / "artifacts").mkdir(parents=True)
    (p / "project-state.yaml").write_text("backlog_format_version: 2\n")
    return p


def _write_marker(prawduct: Path, *, started_at: str | None = None, raw: str | None = None) -> Path:
    """Write a marker with a chosen started_at (or arbitrary raw bytes)."""
    marker = prawduct / cm.MARKER_NAME
    if raw is not None:
        marker.write_text(raw)
    else:
        marker.write_text(json.dumps({"started_at": started_at, "pid": 1, "tool": "critic"}))
    return marker


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


# =============================================================================
# Unit — lib/critic_marker
# =============================================================================


class TestCriticMarkerUnit:
    def test_write_then_review_active_fresh(self, tmp_path):
        prawduct = _prawduct(tmp_path)
        assert cm.write_marker(prawduct) is True
        marker = prawduct / cm.MARKER_NAME
        assert marker.is_file()
        payload = json.loads(marker.read_text())
        assert payload["tool"] == "critic" and "started_at" in payload
        active, age = cm.review_active(prawduct)
        assert active is True
        assert age is not None and age < 60  # just written

    def test_marker_payload_carries_no_pid(self, tmp_path):
        # The marker is written by the short-lived critic-begin hook process,
        # so any pid it records is dead by the time a reader checks it —
        # `ps -p <pid>` then reads as "the review died" on every healthy
        # review (field report 2026-08-02: that false signal outranked the
        # grace-window guidance and triggered a duplicate dispatch). Nothing
        # in the framework reads the field; the marker must not carry it.
        prawduct = _prawduct(tmp_path)
        cm.write_marker(prawduct)
        payload = json.loads((prawduct / cm.MARKER_NAME).read_text())
        assert "pid" not in payload
        assert "started_at" in payload  # liveness stays answered by age

    def test_write_marker_noop_outside_repo(self, tmp_path):
        # The Critic only runs in an onboarded repo; outside one this is a no-op.
        missing = tmp_path / "nope" / ".prawduct"
        assert cm.write_marker(missing) is False
        assert not missing.exists()

    def test_clear_marker_idempotent(self, tmp_path):
        prawduct = _prawduct(tmp_path)
        assert cm.clear_marker(prawduct) is False  # absent → no-op
        cm.write_marker(prawduct)
        assert cm.clear_marker(prawduct) is True   # present → removed
        assert not (prawduct / cm.MARKER_NAME).is_file()
        assert cm.clear_marker(prawduct) is False  # idempotent

    def test_review_active_absent(self, tmp_path):
        prawduct = _prawduct(tmp_path)
        assert cm.review_active(prawduct) == (False, None)

    def test_stale_marker_is_not_active_and_asking_removes_nothing(self, tmp_path):
        """A marker past the TTL blocks nothing — and finding that out must not
        be what deletes it. Expiry makes a marker REMOVABLE; `boundary_sweep`
        decides whether it may actually go, because a complete roster is kept at
        any age. A predicate that unlinked while answering would be a second,
        silent home for that decision, reachable by any caller who only asked."""
        prawduct = _prawduct(tmp_path)
        old = datetime.now(timezone.utc) - timedelta(seconds=cm.CRITIC_ACTIVE_TTL_SECONDS + 120)
        marker = _write_marker(prawduct, started_at=_iso(old))
        active, age = cm.review_active(prawduct)
        assert active is False
        assert marker.is_file(), "asking whether a review is live must not remove anything"

    def test_boundary_just_inside_ttl_is_active(self, tmp_path):
        prawduct = _prawduct(tmp_path)
        recent = datetime.now(timezone.utc) - timedelta(seconds=cm.CRITIC_ACTIVE_TTL_SECONDS - 120)
        _write_marker(prawduct, started_at=_iso(recent))
        active, age = cm.review_active(prawduct)
        assert active is True

    def test_corrupt_marker_falls_back_to_mtime(self, tmp_path):
        # Unparseable started_at → age falls back to the file mtime. A freshly
        # written corrupt marker is recent by mtime, so it still counts as active
        # (protective); an old one expires. Either way `clear` is never bricked —
        # the override exists, and an expired marker blocks nothing.
        prawduct = _prawduct(tmp_path)
        _write_marker(prawduct, raw="not json at all")
        active, _ = cm.review_active(prawduct)
        assert active is True  # recent by mtime

    def test_corrupt_and_old_marker_is_stale(self, tmp_path):
        prawduct = _prawduct(tmp_path)
        marker = _write_marker(prawduct, raw="not json")
        old = (datetime.now(timezone.utc) - timedelta(seconds=cm.CRITIC_ACTIVE_TTL_SECONDS + 600)).timestamp()
        import os
        os.utime(marker, (old, old))
        active, _ = cm.review_active(prawduct)
        assert active is False
        assert marker.is_file(), "the predicate reports; it does not release"


# =============================================================================
# Behavioral — the real CLI (the reviewer's actual path)
# =============================================================================


class TestClearGuardCLI:
    def test_bare_clear_refuses_with_active_marker(self, tmp_path):
        prawduct = _prawduct(tmp_path)
        # The session state a reviewer must not clobber.
        (prawduct / ".session-reflected").write_text("builder reflection — must survive")
        cm.write_marker(prawduct)

        result = run_plugin_hook("clear", tmp_path, git_status=" M src/app.py")

        assert result.returncode == 2, result.stderr
        # The refusal states the REASON, not the guard's internal id: an
        # operator in a governed product cannot resolve "CRT-3X9D", and the id
        # displaced the sentence that makes the message actionable. The id
        # lives in the comment above the guard.
        assert "independent reviewer" in result.stderr
        assert "CRT-3X9D" not in result.stderr
        # Actionable override (the waiver-style correction path).
        # The remedy is the NAMED act, not a bare `rm`. `critic-end` clears the
        # marker and nothing else, so the refusal has to say what that costs on a
        # review whose reviewers all reported — `rm` said nothing at all while
        # doing exactly the same damage.
        assert "--force" in result.stderr
        assert "prawduct-hook critic-end" in result.stderr
        assert "prawduct-hook critic-consolidate" in result.stderr
        assert "rm .prawduct/.critic-active" not in result.stderr
        # No mutation occurred.
        assert (prawduct / ".session-reflected").read_text() == "builder reflection — must survive"
        assert (prawduct / cm.MARKER_NAME).is_file(), "guard must not remove the marker"
        assert not (prawduct / ".session-start").is_file(), "refused clear must not write session-start"

    def test_session_start_proceeds_and_sweeps_a_stale_marker(self, tmp_path):
        """A session boundary proceeds unrefused and sweeps a marker the TTL has
        released — the crashed-Critic rescue this act exists for.

        This test used to write a FRESH marker and assert the sweep, which
        pinned a defect: `/clear` and `startup` share one hook entry, and
        `/clear` resets context *in-process*, so a fresh marker there may belong
        to a reviewer that is still running. A correction, not a relaxation —
        the same shape as the earlier `resume` correction in
        `test_session_boundary_events.py`. What the sweep exists for is asserted
        here, and the case it must no longer touch is asserted beside it.
        """
        prawduct = _prawduct(tmp_path)
        old = datetime.now(timezone.utc) - timedelta(seconds=cm.CRITIC_ACTIVE_TTL_SECONDS + 300)
        _write_marker(prawduct, started_at=_iso(old))
        result = run_plugin_hook("clear", tmp_path, "--session-start", git_status=" M src/app.py")
        assert result.returncode == 0, result.stderr
        assert not (prawduct / cm.MARKER_NAME).is_file(), "session start must sweep a stale marker"
        # And says so. A marker with no dispatch behind it is the least
        # interesting sweep there is, which is exactly why it was the one left
        # silent — but the act still removes the Stop hook's handle on whatever
        # set that marker, so the boundary owes the reader a line either way.
        assert "swept" in result.stdout
        assert "/prawduct:critic" in result.stdout, "a sweep names the way back"
        assert (prawduct / ".session-start").is_file()
        assert (prawduct / ".session-git-baseline").read_text() == " M src/app.py"

    def test_session_start_proceeds_but_keeps_a_live_marker(self, tmp_path):
        """The half the old assertion inverted. The boundary still runs in full —
        anchors captured, session started — while the marker survives, because a
        boundary event is not evidence that the reviewing process died.

        Both halves are asserted together: `.session-start` present proves the
        boundary was not demoted to a continuation, which is the other way this
        could pass while being wrong.
        """
        prawduct = _prawduct(tmp_path)
        cm.write_marker(prawduct)
        result = run_plugin_hook("clear", tmp_path, "--session-start", git_status=" M src/app.py")
        assert result.returncode == 0, result.stderr
        assert (prawduct / cm.MARKER_NAME).is_file(), (
            "a live marker must survive a boundary — /clear resets context "
            "in-process, so the dispatched reviewer may still be writing"
        )
        assert (prawduct / ".session-start").is_file(), (
            "the boundary itself must still run; only the sweep is gated"
        )

    def test_force_overrides_active_marker(self, tmp_path):
        prawduct = _prawduct(tmp_path)
        cm.write_marker(prawduct)
        result = run_plugin_hook("clear", tmp_path, "--force")
        assert result.returncode == 0, result.stderr
        assert not (prawduct / cm.MARKER_NAME).is_file()
        assert (prawduct / ".session-start").is_file()

    def test_stale_marker_does_not_block_bare_clear(self, tmp_path):
        prawduct = _prawduct(tmp_path)
        old = datetime.now(timezone.utc) - timedelta(seconds=cm.CRITIC_ACTIVE_TTL_SECONDS + 300)
        _write_marker(prawduct, started_at=_iso(old))
        result = run_plugin_hook("clear", tmp_path)
        assert result.returncode == 0, result.stderr
        assert not (prawduct / cm.MARKER_NAME).is_file(), "stale marker must be swept"
        assert (prawduct / ".session-start").is_file()

    def test_no_marker_bare_clear_proceeds(self, tmp_path):
        # Regression: with no review active, bare clear behaves exactly as before.
        prawduct = _prawduct(tmp_path)
        result = run_plugin_hook("clear", tmp_path, git_status=" M app.py")
        assert result.returncode == 0, result.stderr
        assert (prawduct / ".session-start").is_file()
        assert (prawduct / ".session-git-baseline").read_text() == " M app.py"


def _real_repo(tmp_path: Path) -> Path:
    """A real git repo with one commit and a dirty file — critic-begin (v3)
    derives the dispatch manifest from actual git state, so the mock-git
    harness can't drive it."""
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        "HOME": str(tmp_path / "_home"),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
    }
    (tmp_path / "_home").mkdir(exist_ok=True)

    def git(*args):
        subprocess.run(["git", *args], cwd=repo, env=env, check=True,
                       capture_output=True, timeout=10)

    git("init", "--quiet", "-b", "main")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "T")
    (repo / "app.py").write_text("x = 1\n")
    git("add", "app.py")
    git("commit", "-q", "-m", "init")
    (repo / "app.py").write_text("x = 2\n")  # dirty diff to dispatch against
    return repo


def _run_real(command: str, repo: Path, *args: str):
    import subprocess

    root = Path(__file__).resolve().parent.parent / "plugin"
    env = {
        "HOME": str(repo.parent / "_home"),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "CLAUDE_PLUGIN_ROOT": str(root),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        ["python3", str(root / "bin" / "prawduct-hook"), command, *args],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=30,
    )


class TestCriticBeginEndCLI:
    def test_begin_writes_then_end_removes(self, tmp_path):
        repo = _real_repo(tmp_path)
        prawduct = repo / ".prawduct"
        prawduct.mkdir()
        begin = _run_real("critic-begin", repo, "--mode", "chunk")
        assert begin.returncode == 0, begin.stderr
        marker = prawduct / cm.MARKER_NAME
        assert marker.is_file()
        payload = json.loads(marker.read_text())
        # A parseable server-side timestamp so review_active can age it.
        datetime.strptime(payload["started_at"], "%Y-%m-%dT%H:%M:%SZ")

        end = _run_real("critic-end", repo)
        assert end.returncode == 0, end.stderr
        assert not marker.is_file()

    def test_end_is_idempotent_when_absent(self, tmp_path):
        _prawduct(tmp_path)
        result = run_plugin_hook("critic-end", tmp_path)
        assert result.returncode == 0, result.stderr

    def test_begin_without_mode_refuses_with_remedy(self, tmp_path):
        """v3: a bare critic-begin means a stale cached skill is driving a
        newer hook — refuse at dispatch with the reload remedy, and leave no
        marker (no review is starting)."""
        repo = _real_repo(tmp_path)
        (repo / ".prawduct").mkdir()
        begin = _run_real("critic-begin", repo)
        assert begin.returncode == 1
        assert "--mode is required" in begin.stderr
        assert not (repo / ".prawduct" / cm.MARKER_NAME).is_file()

    def test_begin_clears_leftover_partials(self, tmp_path):
        """A waived or stale-failed coordinator review leaves .critic-partials/
        behind (consolidate removes them only on success). A leftover partial at
        the same commit as a fresh dispatch would merge as if the new reviewer
        wrote it, so critic-begin resets the dir — every review starts clean."""
        repo = _real_repo(tmp_path)
        prawduct = repo / ".prawduct"
        prawduct.mkdir()
        partials = prawduct / ".critic-partials"
        partials.mkdir()
        (partials / "manifest.json").write_text("{}")
        (partials / "correctness.json").write_text("{}")

        begin = _run_real("critic-begin", repo, "--mode", "chunk")
        assert begin.returncode == 0, begin.stderr
        assert not (partials / "correctness.json").exists(), (
            "critic-begin must remove leftover partials from a prior review"
        )
        assert "leftover .critic-partials" in begin.stdout
        # The fresh dispatch manifest replaced the leftovers.
        assert (partials / "manifest.json").is_file()
        assert (prawduct / cm.MARKER_NAME).is_file()

    def test_begin_without_partials_stays_quiet(self, tmp_path):
        repo = _real_repo(tmp_path)
        prawduct = repo / ".prawduct"
        prawduct.mkdir()
        begin = _run_real("critic-begin", repo, "--mode", "chunk")
        assert begin.returncode == 0, begin.stderr
        assert "leftover" not in begin.stdout
        assert (prawduct / cm.MARKER_NAME).is_file()


class TestDesignerHandoffMarkerOrdering:
    """CRT-6F2N — the designer-handoff early exit must precede critic-begin.

    The marker lifecycle is agent-followed prose (the skill, not the hook,
    decides when to run critic-begin), so the pin is structural: in the
    critic SKILL's step 1, the designer-handoff early-exit instruction must
    appear BEFORE the critic-begin instruction. Without that ordering, a
    designer-handoff invocation set the marker and exited without critic-end,
    leaving `clear` blocked until the 30-minute TTL.
    """

    def test_skill_prose_orders_early_exit_before_critic_begin(self):
        # kernel-v3 chunk 05: dispatch is `critic-begin --mode <mode> …` (the
        # bare `run \`prawduct-hook critic-begin\`` step died with the
        # code-written manifest), and a descriptive mention now precedes the
        # flow in Structural Constraints — so the ordering pin anchors inside
        # the Getting Started flow, where the instructions live. The invariant
        # is unchanged: the early exit must precede the dispatch instruction.
        text = (_ROOT / "skills" / "critic" / "SKILL.md").read_text(encoding="utf-8")
        flow_pos = text.find("## Getting Started")
        assert flow_pos != -1, "Getting Started flow missing from SKILL.md"
        flow = text[flow_pos:]
        exit_pos = flow.find("Designer-handoff early exit")
        begin_pos = flow.find("`prawduct-hook critic-begin --mode")
        assert exit_pos != -1, "designer-handoff early-exit instruction missing from the flow"
        assert begin_pos != -1, "critic-begin dispatch instruction missing from the flow"
        assert exit_pos < begin_pos, (
            "the designer-handoff early exit must come before critic-begin "
            "(CRT-6F2N: no critic-active marker for a review that never happens)"
        )


class TestConcurrentDispatchGuard:
    """`critic-begin` must refuse to displace a review that is still live.

    The defect these pin (filed as brookstalley/prawduct#602, near-duplicate of
    #171, observed live 2026-07-29, 2026-07-30 and 2026-08-05): `begin_review`
    archived the partials directory and overwrote the manifest unconditionally.
    Dispatching over an in-flight review therefore destroyed completed findings
    — and, worse, left the displaced review's reviewers running so their
    partials landed in the NEW review's directory, where a partial at the same
    commit is indistinguishable from one written for it and consolidates as the
    wrong review.

    NOT a v3.2.5 regression: the sweep is in the 3.2.3/3.2.4/3.2.5 trees alike
    and no tag carried a guard.

    The seam every test here turns on: **an orphaned partial with no marker is
    still swept** (`test_begin_clears_leftover_partials` is the standing
    contract, deliberately unchanged); a partial with a LIVE marker is not.
    """

    def _dispatch(self, tmp_path):
        repo = _real_repo(tmp_path)
        (repo / ".prawduct").mkdir()
        first = _run_real("critic-begin", repo, "--mode", "chunk")
        assert first.returncode == 0, first.stderr
        assert (repo / ".prawduct" / cm.MARKER_NAME).is_file()
        return repo

    @staticmethod
    def _complete_the_roster(repo: Path) -> Path:
        """Write the dispatched review's one partial where that review expects
        it, and return the path. Partials are keyed by review id, so a fixture
        writing a bare `reviewer.json` leaves the roster INCOMPLETE and every
        assertion about a complete roster silently tests the wrong state."""
        partials = repo / ".prawduct" / ".critic-partials"
        manifest = json.loads((partials / "manifest.json").read_text())
        path = repo / manifest["rendezvous"]["reviewer"]["partial"]
        path.write_text('{"role": "reviewer"}')
        return path

    def test_refuses_while_a_review_is_live_and_leaves_it_intact(self, tmp_path):
        """The core incident: a second dispatch must not touch the first's state."""
        repo = self._dispatch(tmp_path)
        partials = repo / ".prawduct" / ".critic-partials"
        first_id = json.loads((partials / "manifest.json").read_text())["id"]
        partial = self._complete_the_roster(repo)

        second = _run_real("critic-begin", repo, "--mode", "chunk")

        assert second.returncode == 1, "a dispatch over a live review must refuse"
        assert "already in flight" in second.stderr
        assert first_id in second.stderr, "the refusal names the review it protected"
        # The whole point: nothing of the first review was disturbed.
        assert json.loads((partials / "manifest.json").read_text())["id"] == first_id
        assert partial.read_text() == '{"role": "reviewer"}'
        assert not (repo / ".prawduct" / ".critic-partials-archive").exists(), (
            "a refused dispatch must not archive the live review's partials"
        )

    def test_refuses_a_complete_roster_even_after_the_marker_expires(self, tmp_path):
        """Age says whether more reviewers are coming; it says nothing about
        whether findings already written are worth keeping. The destroyed review
        in the 2026-08-05 report had every partial on disk — a purely time-based
        guard would still have swept it once the window passed."""
        repo = self._dispatch(tmp_path)
        prawduct = repo / ".prawduct"
        partials = prawduct / ".critic-partials"
        partial = self._complete_the_roster(repo)
        # Expire the marker: strictly past the TTL, so review_active() is False.
        stale = datetime.now(timezone.utc) - timedelta(
            seconds=cm.CRITIC_ACTIVE_TTL_SECONDS + 60
        )
        (prawduct / cm.MARKER_NAME).write_text(
            json.dumps({"started_at": stale.strftime("%Y-%m-%dT%H:%M:%SZ"), "tool": "critic"})
        )
        assert cm.review_active(prawduct) == (False, None), "precondition: marker is stale"

        second = _run_real("critic-begin", repo, "--mode", "chunk")

        assert second.returncode == 1, "a complete roster is finished work at any age"
        assert "every reviewer has reported" in second.stderr
        assert "critic-consolidate" in second.stderr, (
            "the remedy for a complete roster is to consolidate it, not to discard it"
        )
        assert partial.is_file()

    def test_critic_end_escapes_a_live_marker_with_an_incomplete_roster(self, tmp_path):
        """`critic-end` is the escape for condition (a) ONLY — a live marker whose
        roster has not completed. Named narrowly on purpose: it does not clear a
        complete roster, which is the separate state the next two tests cover."""
        repo = self._dispatch(tmp_path)
        refused = _run_real("critic-begin", repo, "--mode", "chunk")
        assert refused.returncode == 1
        assert "prawduct-hook critic-end" in refused.stderr

        assert _run_real("critic-end", repo).returncode == 0
        again = _run_real("critic-begin", repo, "--mode", "chunk")
        assert again.returncode == 0, f"after critic-end a dispatch proceeds: {again.stderr}"

    def _strand_a_complete_roster(self, tmp_path):
        """The state a failed consolidation leaves: a valid manifest, every
        roster partial present, and NO live marker.

        Reachable without contrivance — `consolidate` fail-closes on a malformed
        partial, a commit mismatch, or a store/ledger write error and leaves the
        partials in place so the fix can retry; its only two `remove_partials`
        call sites are `begin_review` (behind the guard) and consolidate-on-success.
        """
        repo = self._dispatch(tmp_path)
        prawduct = repo / ".prawduct"
        self._complete_the_roster(repo)
        assert _run_real("critic-end", repo).returncode == 0  # marker gone, partials stay
        assert not (prawduct / cm.MARKER_NAME).exists()
        return repo, prawduct

    def test_a_stranded_complete_roster_is_refused_with_a_remedy_that_reaches_it(
        self, tmp_path
    ):
        """The guard must not create a state nothing can clear. `critic-end` does
        not touch partials and no TTL expires them, so the refusal here must NOT
        claim either — it must name the one command that does work."""
        repo, _prawduct = self._strand_a_complete_roster(tmp_path)

        refused = _run_real("critic-begin", repo, "--mode", "chunk")

        assert refused.returncode == 1
        assert "STRANDED" in refused.stderr
        assert "prawduct-hook critic-discard" in refused.stderr
        assert "expires on its own" not in refused.stderr, (
            "no marker is live here — promising expiry would be false"
        )
        assert "critic-end` will NOT clear this" in refused.stderr

    def test_critic_discard_unblocks_a_stranded_roster_and_archives_it(self, tmp_path):
        """The escape works, and it preserves rather than deletes — discarding a
        completed review's findings is a decision, so they stay recoverable."""
        repo, prawduct = self._strand_a_complete_roster(tmp_path)
        assert _run_real("critic-begin", repo, "--mode", "chunk").returncode == 1

        discard = _run_real("critic-discard", repo)

        assert discard.returncode == 0, discard.stderr
        assert "archived" in discard.stdout
        archive = prawduct / ".critic-partials-archive"
        assert archive.is_dir() and any(archive.iterdir()), "partials archived, not deleted"
        again = _run_real("critic-begin", repo, "--mode", "chunk")
        assert again.returncode == 0, f"discard must unblock dispatch: {again.stderr}"

    def test_a_refused_dispatch_does_not_sweep_the_marker(self, tmp_path):
        """The Stop hook's abandoned-review branch is gated on `marker_present`
        and is what prints the manual-recovery remedy. A dispatch that swept a
        stale marker on its way past would delete the signal producing those
        instructions — so the guard reads with `sweep=False`."""
        repo = self._dispatch(tmp_path)
        prawduct = repo / ".prawduct"
        self._complete_the_roster(repo)
        stale = datetime.now(timezone.utc) - timedelta(
            seconds=cm.CRITIC_ACTIVE_TTL_SECONDS + 60
        )
        (prawduct / cm.MARKER_NAME).write_text(
            json.dumps({"started_at": stale.strftime("%Y-%m-%dT%H:%M:%SZ"), "tool": "critic"})
        )

        assert _run_real("critic-begin", repo, "--mode", "chunk").returncode == 1
        assert (prawduct / cm.MARKER_NAME).is_file(), (
            "a refused dispatch must leave the marker for the Stop gate to find"
        )

    def test_incomplete_roster_names_who_it_is_waiting_on(self, tmp_path):
        """The observability half. `methodology/building.md` tells an agent whose
        review looks slow to re-invoke, and nothing distinguished in-flight from
        dead — so the guide's own failure path led into the destructive dispatch.
        The refusal answers that question at the moment it is being asked."""
        repo = self._dispatch(tmp_path)
        second = _run_real("critic-begin", repo, "--mode", "chunk")
        assert second.returncode == 1
        assert "still waiting on reviewer" in second.stderr
        assert "still running" in second.stderr

    def test_stray_partials_with_no_valid_manifest_are_still_swept(self, tmp_path):
        """The seam, stated as its own test: with no marker AND no valid manifest,
        `pending_state` is not `complete`, so the sweep runs exactly as before.

        Scoped precisely to what the fixture builds. An earlier version of this
        test claimed to pin "a waived or stale-failed review's leftovers" — those
        carry a VALID manifest and often a complete roster, which is the state the
        guard now refuses (see the stranded-roster tests above), so the claim was
        green precisely where it was wrong."""
        repo = _real_repo(tmp_path)
        prawduct = repo / ".prawduct"
        prawduct.mkdir()
        partials = prawduct / ".critic-partials"
        partials.mkdir()
        (partials / "reviewer.json").write_text('{"role": "reviewer"}')
        assert not (prawduct / cm.MARKER_NAME).exists(), "precondition: no live review"

        begin = _run_real("critic-begin", repo, "--mode", "chunk")

        assert begin.returncode == 0, begin.stderr
        assert not (partials / "reviewer.json").exists(), (
            "an orphaned partial with no marker is still swept"
        )


class TestCriticRestore:
    """`critic-restore` — the recovery the review-identity binding replaces.

    Before a partial carried review identity, an archived review was recovered by
    copying its partials into the CURRENT review's directory: a partial bound only
    to the commit it reviewed was schema- and commit-valid against whatever
    manifest happened to be there, so review A's findings landed in the record
    under review B's id. Keying the filenames by review id and checking
    ``dispatch_id`` makes that copy inert — correctly, since it was always a
    mis-attribution — which is why the recovery it removes is owed a replacement
    that restores the review AS ITSELF, manifest included.

    The archive is also reachable only through a listing that is bounded (newest
    three), so the refusals here name what IS available rather than leaving the
    caller to guess an id.
    """

    @staticmethod
    def _partial_for(manifest: dict, role: str = "reviewer") -> str:
        return json.dumps({
            "role": role,
            "goals": ["Nothing Is Broken"],
            "dispatch_id": manifest["id"],
            "commit_reviewed": manifest["commit_reviewed"],
            "model": None,
            "duration_seconds": 1,
            "findings": [],
            "summary": "the review being restored",
        })

    def _archived_complete_review(self, tmp_path) -> tuple[Path, str]:
        """A complete, unconsolidated review sitting in the archive.

        `critic-discard` is the archiving path used here because it is the one
        that reaches this state: since the in-flight guard landed, a later
        dispatch REFUSES a complete roster rather than sweeping it, so discard is
        how a finished-but-unconsolidated review gets archived at all."""
        repo = _real_repo(tmp_path)
        prawduct = repo / ".prawduct"
        prawduct.mkdir()
        begin = _run_real("critic-begin", repo, "--mode", "chunk")
        assert begin.returncode == 0, begin.stderr
        partials = prawduct / ".critic-partials"
        manifest = json.loads((partials / "manifest.json").read_text())
        (repo / manifest["rendezvous"]["reviewer"]["partial"]).write_text(
            self._partial_for(manifest)
        )
        discard = _run_real("critic-discard", repo)
        assert discard.returncode == 0, discard.stderr
        assert not (partials / "manifest.json").exists(), "precondition: nothing pending"
        return repo, manifest["id"]

    def test_restore_then_consolidate_records_the_archived_reviews_own_id(self, tmp_path):
        """The load-bearing round trip: what comes back consolidates as ITSELF.

        The recovery this replaces recorded the restored findings under whichever
        review's manifest was in the directory. The fact appended here must carry
        the archived review's id, or the replacement has reproduced the defect."""
        repo, review_id = self._archived_complete_review(tmp_path)

        restore = _run_real("critic-restore", repo, review_id)
        assert restore.returncode == 0, restore.stderr
        assert review_id in restore.stdout, "the restore names the review it brought back"
        assert "critic-consolidate" in restore.stdout, (
            "a restored review is inert until it is consolidated — say so"
        )

        consolidated = _run_real("critic-consolidate", repo)
        assert consolidated.returncode == 0, consolidated.stderr
        assert "consolidated" in consolidated.stdout, consolidated.stdout

        facts = (repo / ".git" / "prawduct" / "evidence.jsonl").read_text()
        assert review_id in facts, (
            "the fact must carry the RESTORED review's id, not a fresh one"
        )

    def test_restore_copies_and_leaves_the_archive_intact(self, tmp_path):
        """The archive is the last trace an unconsolidated review ever ran. A
        restore that consumed it would mean a restored-then-swept review leaves
        nothing at all — so restore copies."""
        repo, review_id = self._archived_complete_review(tmp_path)
        archived = repo / ".prawduct" / ".critic-partials-archive" / review_id
        before = sorted(p.name for p in archived.iterdir())

        assert _run_real("critic-restore", repo, review_id).returncode == 0

        assert sorted(p.name for p in archived.iterdir()) == before, (
            "restore must not consume the archive"
        )
        restored = sorted(
            p.name for p in (repo / ".prawduct" / ".critic-partials").iterdir()
        )
        assert restored == before, "every archived file comes back"

    def test_restore_refuses_onto_a_non_empty_partials_directory(self, tmp_path):
        """Merging two reviews' files into one directory is the mis-attribution
        this whole binding exists to prevent — so restore refuses rather than
        writing, and names the command that actually clears what is in the way.

        `critic-end` is deliberately NOT the remedy here: it clears the marker
        only, so the files would still be there and the next restore would refuse
        identically. A refusal whose remedy does not reach the state is worse
        than none."""
        repo, review_id = self._archived_complete_review(tmp_path)
        second = _run_real("critic-begin", repo, "--mode", "chunk")
        assert second.returncode == 0, second.stderr
        live_manifest = json.loads(
            (repo / ".prawduct" / ".critic-partials" / "manifest.json").read_text()
        )

        refused = _run_real("critic-restore", repo, review_id)

        assert refused.returncode == 1
        assert "prawduct-hook critic-discard" in refused.stderr, (
            "the remedy must be the command that clears files, not just the marker"
        )
        assert "prawduct-hook critic-end\n" not in refused.stderr, (
            "critic-end leaves the files in place — offering it as the remedy here "
            "would send the caller back to an identical refusal"
        )
        # Nothing of the live review was disturbed.
        assert json.loads(
            (repo / ".prawduct" / ".critic-partials" / "manifest.json").read_text()
        )["id"] == live_manifest["id"]

    def test_restore_refuses_a_complete_roster_by_naming_consolidate(self, tmp_path):
        """State-specific remedies: a complete roster in the way is finished work,
        and the way to clear it without losing anything is to record it."""
        repo, review_id = self._archived_complete_review(tmp_path)
        assert _run_real("critic-begin", repo, "--mode", "chunk").returncode == 0
        partials = repo / ".prawduct" / ".critic-partials"
        manifest = json.loads((partials / "manifest.json").read_text())
        (repo / manifest["rendezvous"]["reviewer"]["partial"]).write_text(
            self._partial_for(manifest)
        )

        refused = _run_real("critic-restore", repo, review_id)

        assert refused.returncode == 1
        assert "critic-consolidate" in refused.stderr

    def test_restore_of_an_unknown_id_names_what_is_available(self, tmp_path):
        """The archive holds at most a handful of sets under names nobody memorised.
        An id-not-found that does not list them sends the caller to `ls`."""
        repo, review_id = self._archived_complete_review(tmp_path)

        refused = _run_real("critic-restore", repo, "rev-does-not-exist")

        assert refused.returncode == 1
        assert review_id in refused.stderr, (
            "an unknown id must name the ids that ARE restorable"
        )

    def test_bare_restore_lists_the_archive_instead_of_a_usage_line(self, tmp_path):
        """Missing argument is a usage error, and the question it raises — which
        review? — is answerable from disk, so answer it."""
        repo, review_id = self._archived_complete_review(tmp_path)

        bare = _run_real("critic-restore", repo)

        assert bare.returncode == 1
        assert review_id in bare.stderr

    def test_unknown_argument_is_a_usage_error(self, tmp_path):
        repo, _review_id = self._archived_complete_review(tmp_path)
        assert _run_real("critic-restore", repo, "--wat").returncode == 1

    def test_restore_outside_an_onboarded_repo_refuses(self, tmp_path):
        repo = _real_repo(tmp_path)
        result = _run_real("critic-restore", repo, "rev-anything")
        assert result.returncode == 1

    def test_an_empty_archive_says_so(self, tmp_path):
        repo = _real_repo(tmp_path)
        (repo / ".prawduct").mkdir()
        result = _run_real("critic-restore", repo, "rev-anything")
        assert result.returncode == 1
        assert "archive" in result.stderr.lower()


class TestRestoreArgumentIsUntrusted:
    """The review id comes from a caller and becomes a path segment.

    `_archive_leftovers` learned this the expensive way: it built its destination
    directory from an id read raw off disk, so `rev-../../escape` walked out of
    the archive and `/tmp/x` replaced the base outright — and because an archive
    failure degrades to DELETE, both failed silently. That guard was added at the
    use, and this is the second use of the same value in the same direction, so
    it gets the same gate and its own test rather than inheriting the lesson by
    proximity."""

    @staticmethod
    def _archive_with_one_set(tmp_path: Path) -> Path:
        prawduct = tmp_path / ".prawduct"
        archived = prawduct / cc.ARCHIVE_DIRNAME / "rev-real"
        archived.mkdir(parents=True)
        (archived / cc.MANIFEST_NAME).write_text("{}")
        return prawduct

    @pytest.mark.parametrize(
        "hostile",
        ["../../escape", "..", "a/b", "a\\b", "/tmp/absolute", ""],
    )
    def test_a_traversing_id_is_refused_like_any_unknown_one(self, tmp_path, hostile):
        prawduct = self._archive_with_one_set(tmp_path)

        result = cc.restore_review(prawduct, hostile)

        assert result["status"] == "error"
        assert result["kind"] == "unknown"
        assert not cc.partials_dir(prawduct).exists(), (
            "a refused restore must not create the destination it was refused"
        )

    def test_a_traversing_id_cannot_reach_a_directory_that_does_exist(self, tmp_path):
        """The gate has to fire on the NAME, not merely on the target missing —
        otherwise it is an accident of layout rather than a guard."""
        prawduct = self._archive_with_one_set(tmp_path)
        # `<archive>/../.critic-partials-archive/rev-real` resolves to a real
        # directory, so `is_dir()` alone would let this through.
        result = cc.restore_review(
            prawduct, f"../{cc.ARCHIVE_DIRNAME}/rev-real"
        )

        assert result["status"] == "error"
        assert result["kind"] == "unknown"


class TestRestoreEdgeStates:
    """The branches the round-trip tests do not walk."""

    def test_an_archived_set_with_no_files_is_named_as_such(self, tmp_path):
        prawduct = tmp_path / ".prawduct"
        (prawduct / cc.ARCHIVE_DIRNAME / "rev-hollow").mkdir(parents=True)

        result = cc.restore_review(prawduct, "rev-hollow")

        assert result["status"] == "error"
        assert result["kind"] == "unusable"
        assert "rev-hollow" in result["reason"]

    def test_a_manifestless_set_restores_but_says_it_cannot_consolidate(self, tmp_path):
        """`_archive_leftovers` names a set `unmanifested-<stamp>` when the
        manifest was unreadable or absent. Those files come back for reading, not
        for recording — and advice that fails soft still names its consequence,
        rather than leaving the reader to infer a consolidation is waiting."""
        prawduct = tmp_path / ".prawduct"
        archived = prawduct / cc.ARCHIVE_DIRNAME / "unmanifested-20260806T000000Z"
        archived.mkdir(parents=True)
        (archived / "correctness.rev-gone.json").write_text("{}")

        result = cc.restore_review(prawduct, "unmanifested-20260806T000000Z")

        assert result["status"] == "ok"
        assert result["consolidatable"] is False
        assert "no dispatch manifest" in result["blocked_reason"]
        assert result["restored"] == ["correctness.rev-gone.json"]

    def test_a_pre_keying_archive_restores_but_cannot_be_recorded(self, tmp_path):
        """The upgrade case, and the one the Governance Checkpoint names as this
        plan's exposure. A set archived by v3.2.6 carries a manifest with no
        `rendezvous`, so `consolidate` fail-closes on it. Telling the operator to
        run `critic-consolidate` and letting them meet that refusal would be a
        remedy that cannot reach the state — the failure this subsystem's
        refusals were rewritten to stop producing."""
        prawduct = tmp_path / ".prawduct"
        archived = prawduct / cc.ARCHIVE_DIRNAME / "rev-20260801T000000Z-old"
        archived.mkdir(parents=True)
        (archived / cc.MANIFEST_NAME).write_text(json.dumps({
            "id": "rev-20260801T000000Z-old",
            "mode": "cumulative (bundle review, ready for merge)",
            "mode_chosen_by": "legacy",
            "roster": ["reviewer"],
            "roster_chosen_by": "legacy",
            # No `rendezvous` — the key Chunk 1 added.
            "commit_reviewed": "a" * 40,
            "base_commit": "b" * 40,
            "base_tree": "c" * 40,
            "head_tree": "d" * 40,
            "head_commit": "a" * 40,
            "files_changed": ["x.py"],
            "files_reviewed": ["x.py"],
            "base_reviewed": True,
        }))
        (archived / "reviewer.json").write_text("{}")

        result = cc.restore_review(prawduct, "rev-20260801T000000Z-old")

        assert result["status"] == "ok", "the files still come back — that is the ask"
        assert result["consolidatable"] is False, (
            "a manifest without `rendezvous` cannot consolidate; saying otherwise "
            "sends the operator into a refusal whose remedy cannot reach them"
        )
        assert "rendezvous" in result["blocked_reason"]

    def test_an_unreadable_archive_is_not_reported_as_an_empty_one(self, tmp_path):
        """An absence-claim is evidence only when the place it read resolved. A
        permission error rendering as "the archive holds nothing to restore" tells
        an operator their unconsolidated findings are gone, and they act on it."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        # A file where the archive directory belongs: exists, cannot be listed.
        (prawduct / cc.ARCHIVE_DIRNAME).write_text("not a directory")

        names, problem = cc.archived_reviews(prawduct)

        assert names == []
        assert problem, "an unreadable archive must not render as an empty one"
        rendered = cc.archive_listing(names, problem)
        assert "holds nothing to restore" not in rendered
        assert "not the same" in rendered

    def test_an_absent_archive_is_a_clean_empty(self, tmp_path):
        """The other side of the same seam: absent IS empty, and must not be
        dressed up as a fault."""
        names, problem = cc.archived_reviews(tmp_path / ".prawduct")
        assert (names, problem) == ([], "")
        assert "holds nothing to restore" in cc.archive_listing(names, problem)

    def test_a_live_marker_with_no_partials_is_refused_with_critic_end(self, tmp_path):
        """The one state where `critic-end` IS the remedy that reaches: nothing is
        on disk to clear, so clearing the marker is the whole job."""
        prawduct = tmp_path / ".prawduct"
        archived = prawduct / cc.ARCHIVE_DIRNAME / "rev-real"
        archived.mkdir(parents=True)
        (archived / cc.MANIFEST_NAME).write_text("{}")
        cm.write_marker(prawduct)

        result = cc.restore_review(prawduct, "rev-real")

        assert result["status"] == "error"
        assert result["kind"] == "pending"
        assert "prawduct-hook critic-end" in result["reason"]
        assert "critic-discard" not in result["reason"], (
            "there are no partials to discard — naming it would not reach the state"
        )

    def test_an_unreadable_manifest_in_the_way_still_names_a_working_remedy(
        self, tmp_path
    ):
        """`pending_state` reports `unreadable` for a manifest that will not parse.
        The files are still in the way, so the remedy is still the one that
        removes files."""
        prawduct = tmp_path / ".prawduct"
        (prawduct / cc.ARCHIVE_DIRNAME / "rev-real").mkdir(parents=True)
        (prawduct / cc.ARCHIVE_DIRNAME / "rev-real" / cc.MANIFEST_NAME).write_text("{}")
        partials = cc.partials_dir(prawduct)
        partials.mkdir(parents=True)
        (partials / cc.MANIFEST_NAME).write_text("not json{")

        result = cc.restore_review(prawduct, "rev-real")

        assert result["status"] == "error"
        assert result["kind"] == "pending"
        assert "prawduct-hook critic-discard" in result["reason"]


class TestRestoreIsAllOrNothing:
    """A restore that dies halfway must not leave the files that make the NEXT
    restore refuse.

    The refusal `restore_review` fires on a non-empty partials directory is
    correct and load-bearing — but a failed copy that leaves its first file
    behind converts its own failure into that refusing state, and the caller's
    retry then meets a different refusal than the one that fired. Nothing
    re-runs this transition on the caller's behalf, so it undoes its own
    leavings rather than relying on a retry."""

    def test_a_failed_copy_leaves_the_partials_directory_empty(
        self, tmp_path, monkeypatch
    ):
        prawduct = tmp_path / ".prawduct"
        archived = prawduct / cc.ARCHIVE_DIRNAME / "rev-abc"
        archived.mkdir(parents=True)
        # Sorted order puts the partial first, so the failure lands with one file
        # already written — the state the rollback exists for.
        (archived / "correctness.rev-abc.json").write_text("{}")
        (archived / cc.MANIFEST_NAME).write_text("{}")

        real_copy = cc.shutil.copy2
        seen: list[object] = []

        def flaky(src, dst):
            seen.append(dst)
            if len(seen) > 1:
                raise OSError("no space left on device")
            return real_copy(src, dst)

        monkeypatch.setattr(cc.shutil, "copy2", flaky)

        result = cc.restore_review(prawduct, "rev-abc")

        assert result["status"] == "error"
        assert result["kind"] == "write-failed"
        assert len(seen) == 2, "precondition: the failure lands mid-copy"
        assert list(cc.partials_dir(prawduct).iterdir()) == [], (
            "a half-restored set would refuse every subsequent restore"
        )
        assert sorted(p.name for p in archived.iterdir()) == [
            "correctness.rev-abc.json",
            cc.MANIFEST_NAME,
        ], "the archive is still the only copy"


class TestArchiveMessagesNameTheWayBack:
    """Every message that ends at "archived to X" names how to get X back.

    A preserved file nobody can act on is not a recovery — before
    `critic-restore` existed these messages were the whole story, and the story
    stopped at the archive path. The pin is behavioral (what the commands print),
    not a source grep, because the claim is about what a reader is told."""

    def test_discard_names_the_restore(self, tmp_path):
        repo = _real_repo(tmp_path)
        prawduct = repo / ".prawduct"
        prawduct.mkdir()
        assert _run_real("critic-begin", repo, "--mode", "chunk").returncode == 0
        manifest = json.loads(
            (prawduct / ".critic-partials" / "manifest.json").read_text()
        )
        (repo / manifest["rendezvous"]["reviewer"]["partial"]).write_text("{}")

        discard = _run_real("critic-discard", repo)

        assert discard.returncode == 0, discard.stderr
        assert "critic-restore" in discard.stdout, (
            "discard archives — it must say how to undo that"
        )
        assert manifest["id"] in discard.stdout, "…and under which name"

    def test_dispatch_archiving_leftovers_names_the_restore(self, tmp_path):
        repo = _real_repo(tmp_path)
        prawduct = repo / ".prawduct"
        prawduct.mkdir()
        partials = prawduct / ".critic-partials"
        partials.mkdir()
        (partials / "manifest.json").write_text("{}")
        (partials / "reviewer.json").write_text('{"role": "reviewer"}')

        begin = _run_real("critic-begin", repo, "--mode", "chunk")

        assert begin.returncode == 0, begin.stderr
        assert "archived" in begin.stdout
        assert "critic-restore" in begin.stdout

    def test_the_in_flight_refusal_names_the_restore(self, tmp_path):
        """The refusal's own argument is "dispatching would archive this" — so it
        is an archive message, and it used to end at "recoverable only by someone
        who knows the archive exists and still has the review id." That sentence
        was the accurate description of a subsystem with no way back; leaving it
        standing once there is one would understate the remedy at the exact moment
        someone is deciding whether to force past the guard."""
        repo = _real_repo(tmp_path)
        (repo / ".prawduct").mkdir()
        assert _run_real("critic-begin", repo, "--mode", "chunk").returncode == 0

        refused = _run_real("critic-begin", repo, "--mode", "chunk")

        assert refused.returncode == 1
        assert "already in flight" in refused.stderr
        assert "critic-restore" in refused.stderr

    def test_the_stranded_roster_refusal_names_the_restore(self, tmp_path):
        """`critic-discard` is the escape offered there, and it archives — so the
        escape has to carry its own undo too."""
        repo = _real_repo(tmp_path)
        prawduct = repo / ".prawduct"
        prawduct.mkdir()
        assert _run_real("critic-begin", repo, "--mode", "chunk").returncode == 0
        manifest = json.loads(
            (prawduct / ".critic-partials" / "manifest.json").read_text()
        )
        (repo / manifest["rendezvous"]["reviewer"]["partial"]).write_text("{}")
        assert _run_real("critic-end", repo).returncode == 0

        refused = _run_real("critic-begin", repo, "--mode", "chunk")

        assert refused.returncode == 1
        assert "prawduct-hook critic-discard" in refused.stderr
        assert "critic-restore" in refused.stderr


# =============================================================================
# The boundary sweep — what it keeps, what it removes, and what it says
# =============================================================================


def _expired(prawduct: Path) -> None:
    """Age the marker strictly past the TTL, in the SAME clock domain the code
    reads. Every actor here — this stamp, `review_active`, and the CLI
    subprocess — runs on the real wall clock; a frozen `now` on one side and a
    real clock on the other turns a TTL into a test that goes red at
    stamp+TTL."""
    old = datetime.now(timezone.utc) - timedelta(seconds=cm.CRITIC_ACTIVE_TTL_SECONDS + 60)
    _write_marker(prawduct, started_at=_iso(old))


def _dispatched(prawduct: Path, *, complete: bool) -> str:
    """A schema-valid dispatch manifest, with every roster partial on disk when
    `complete`. Returns the review id.

    The manifest shape comes from `test_critic_consolidate`'s fixture rather
    than a second hand-rolled copy: a schema change there would otherwise make
    this one merely INVALID, `pending_state` would answer "unreadable", and
    every assertion below about a complete roster would quietly be testing the
    wrong state. The preconditions asserted at each call site are the second
    line of defence against exactly that.
    """
    from test_critic_consolidate import _manifest_dict  # noqa: PLC0415 — test fixture reuse

    manifest = _manifest_dict(roster=["reviewer"])
    cc.partials_dir(prawduct).mkdir(parents=True, exist_ok=True)
    cc.manifest_path(prawduct).write_text(json.dumps(manifest))
    if complete:
        for role in manifest["roster"]:
            cc.partial_path(prawduct, role, manifest["id"]).write_text(
                json.dumps({"role": role})
            )
    return manifest["id"]


class TestBoundarySweepDecidesByRecoverability:
    """The boundary asks two questions, not one.

    The TTL answers "is the dispatching process gone?" — and a `yes` there does
    not license deleting the marker, because a review whose reviewers have ALL
    reported is one deterministic step from being recorded and the Stop hook's
    backstop runs that step off `marker_present`. A purely time-based sweep
    therefore threw away finished reviews: the longer a review ran, the more
    likely it was to lose its own findings.
    """

    def test_no_marker_is_not_a_retention(self, tmp_path):
        """The token exists because a bool could not say this. `absent` and
        `retained` are the two states an announcement must never confuse."""
        prawduct = _prawduct(tmp_path)
        assert cm.boundary_sweep(prawduct) == cm.SWEEP_ABSENT
        assert cm.SWEEP_ABSENT not in cm.SWEEP_RETAINED

    def test_a_live_marker_is_retained_untouched(self, tmp_path):
        prawduct = _prawduct(tmp_path)
        cm.write_marker(prawduct)
        assert cm.boundary_sweep(prawduct) == cm.SWEEP_RETAINED_LIVE
        assert (prawduct / cm.MARKER_NAME).is_file()

    def test_an_expired_marker_with_a_complete_roster_is_retained(self, tmp_path):
        """The self-heal this must not discard: every reviewer reported, the
        marker is what the Stop hook consolidates from, and age says nothing
        about whether findings already written are worth keeping."""
        prawduct = _prawduct(tmp_path)
        _expired(prawduct)
        _dispatched(prawduct, complete=True)
        assert cc.pending_state(prawduct) == ("complete", []), "precondition"
        assert cm.review_active(prawduct)[0] is False, "precondition"

        assert cm.boundary_sweep(prawduct) == cm.SWEEP_RETAINED_COMPLETE
        assert (prawduct / cm.MARKER_NAME).is_file(), (
            "a complete roster is finished work at any age — sweeping it removes "
            "the Stop hook's only handle on those findings"
        )

    def test_an_expired_marker_with_an_incomplete_roster_is_swept(self, tmp_path):
        prawduct = _prawduct(tmp_path)
        _expired(prawduct)
        _dispatched(prawduct, complete=False)
        assert cc.pending_state(prawduct)[0] == "incomplete", "precondition"

        assert cm.boundary_sweep(prawduct) == cm.SWEEP_SWEPT
        assert not (prawduct / cm.MARKER_NAME).is_file()
        assert cc.manifest_path(prawduct).is_file(), (
            "the sweep releases the MARKER; the review's own record is not its to delete"
        )

    def test_an_expired_marker_with_no_dispatch_at_all_is_swept(self, tmp_path):
        prawduct = _prawduct(tmp_path)
        _expired(prawduct)
        assert cm.boundary_sweep(prawduct) == cm.SWEEP_SWEPT
        assert not (prawduct / cm.MARKER_NAME).is_file()

    def test_a_corrupt_but_fresh_marker_survives(self, tmp_path):
        """Decided by AGE, not readability — the standing rule, re-asserted
        through the new entry point. "Corrupt ⇒ swept" would delete a marker a
        reviewer had just written and mangled."""
        prawduct = _prawduct(tmp_path)
        _write_marker(prawduct, raw="{not json")
        assert cm.boundary_sweep(prawduct) == cm.SWEEP_RETAINED_LIVE
        assert (prawduct / cm.MARKER_NAME).is_file()

    def test_an_unanswerable_roster_retains_rather_than_deletes(self, tmp_path, monkeypatch):
        """"Cannot tell" is not "not complete". The module prices the
        asymmetry: retaining a dead marker is loud and reversible by a named
        command, deleting a recoverable one is silent and costs a review round —
        so a consolidation module that cannot answer must not be read as a no."""
        prawduct = _prawduct(tmp_path)
        _expired(prawduct)
        _dispatched(prawduct, complete=True)

        def explode(_prawduct_dir):
            raise RuntimeError("consolidation lib unavailable")

        monkeypatch.setattr(cc, "pending_state", explode)
        assert cm.boundary_sweep(prawduct) == cm.SWEEP_RETAINED_UNKNOWN
        assert cm.SWEEP_RETAINED_UNKNOWN in cm.SWEEP_RETAINED
        assert (prawduct / cm.MARKER_NAME).is_file()

    def test_the_roster_is_consulted_before_anything_is_unlinked(self, tmp_path, monkeypatch):
        """The ordering bug this function exists to avoid: `review_active`'s
        sweeping default deletes the marker as it answers, so a roster question
        asked afterwards would always be asked about a marker that was already
        gone. Pinned by observing that the roster read still SEES the marker."""
        prawduct = _prawduct(tmp_path)
        _expired(prawduct)
        _dispatched(prawduct, complete=True)
        seen = []
        real_state = cc.pending_state

        def spy(prawduct_dir):
            seen.append((prawduct_dir / cm.MARKER_NAME).is_file())
            return real_state(prawduct_dir)

        monkeypatch.setattr(cc, "pending_state", spy)
        cm.boundary_sweep(prawduct)
        assert seen == [True], "the liveness read must not sweep on the way past"


class TestBoundaryAnnouncesWhicheverActItTook:
    """Neither branch may be silent, and the swept one least of all.

    A retention was already announced; the sweep printed nothing — while being
    the branch that DESTROYS something. It removes the Stop hook's only handle
    on the review, so after it there is no later gate to raise the subject:
    this notice is the whole signal, not a courtesy on top of one.
    """

    def test_a_swept_marker_says_so_and_names_the_review(self, tmp_path):
        prawduct = _prawduct(tmp_path)
        _expired(prawduct)
        review_id = _dispatched(prawduct, complete=False)

        result = run_plugin_hook("clear", tmp_path, "--session-start", git_status=" M a.py")

        assert result.returncode == 0, result.stderr
        assert not (prawduct / cm.MARKER_NAME).is_file()
        assert "swept" in result.stdout
        assert review_id in result.stdout, "the id is what makes any recovery addressable"
        assert "still waiting on reviewer" in result.stdout, (
            "the on-disk state comes from the one shared reading, not a fourth account"
        )
        assert "will not fire" in result.stdout, (
            "the notice has to say that no later gate will raise this review again"
        )
        # The shared reading is printed by surfaces that RETAIN and by this one,
        # which does not — so an unconditional "a /clear retains the marker" read
        # as "waiting is safe" directly above the paragraph saying it is gone.
        # Sharing a reading means it has to be true wherever it is printed.
        assert "retains the marker" not in result.stdout
        assert "releases it once the liveness window has passed" in result.stdout
        assert (prawduct / ".session-start").is_file(), "the boundary itself still runs"

    def test_a_retained_complete_roster_is_told_to_consolidate_not_clear(self, tmp_path):
        prawduct = _prawduct(tmp_path)
        _expired(prawduct)
        _dispatched(prawduct, complete=True)

        result = run_plugin_hook("clear", tmp_path, "--session-start", git_status=" M a.py")

        assert result.returncode == 0, result.stderr
        assert (prawduct / cm.MARKER_NAME).is_file(), (
            "the session boundary must not discard a review the Stop hook can still heal"
        )
        assert "prawduct-hook critic-consolidate" in result.stdout
        assert "NOT clearing" in result.stdout
        assert "no session event proves its reviewers died" not in result.stdout, (
            "that head is a claim about TIME and is false once the TTL has released "
            "the marker — this retention rests on the roster instead"
        )

    def test_a_live_marker_keeps_the_liveness_head(self, tmp_path):
        """The two retentions rest on different evidence and must not be
        reported with each other's reason."""
        prawduct = _prawduct(tmp_path)
        cm.write_marker(prawduct)

        result = run_plugin_hook("clear", tmp_path, "--session-start", git_status=" M a.py")

        assert result.returncode == 0, result.stderr
        assert (prawduct / cm.MARKER_NAME).is_file()
        assert "no session event proves its reviewers died" in result.stdout


# =============================================================================
# The reader inventory — enumerated, not argued safe
# =============================================================================


class TestMarkerAndFindingsReaderInventory:
    """Every place that meets the marker or the findings record, listed by name.

    Twice now a change to this subsystem was reasoned safe from the `clear`
    guard alone and twice a reader OUTSIDE the session was the one that broke:
    the marker's record outlives every in-session signal, so "no session event
    can observe this" is not an argument about who reads it. A retention rule
    that keeps a marker longer, or a sweep that removes it sooner, lands on all
    of them at once.

    So the readers are ENUMERATED rather than derived. The scan below finds
    them mechanically; a site the inventory does not name fails this test, and
    the inventory's value is the test that exercises that site — which is
    checked to exist rather than taken on trust. Adding a reader therefore
    costs whoever adds it one line here and one test, which is the point.
    """

    #: (source file, enclosing definition, what it touches) → the test that
    #: exercises it. `<module>` means module scope.
    INVENTORY: dict[tuple[str, str, str], str] = {
        # --- the marker: liveness, presence, and the acts that end it ---
        ("plugin/lib/critic_marker.py", "<module>", ".critic-active"):
            "tests/test_critic_session_guard.py::TestCriticMarkerUnit"
            "::test_write_then_review_active_fresh",
        ("plugin/lib/critic_marker.py", "boundary_sweep", "review_active()"):
            "tests/test_critic_session_guard.py::TestBoundarySweepDecidesByRecoverability"
            "::test_the_roster_is_consulted_before_anything_is_unlinked",
        ("plugin/lib/critic_marker.py", "boundary_sweep", "clear_marker()"):
            "tests/test_critic_session_guard.py::TestBoundarySweepDecidesByRecoverability"
            "::test_an_expired_marker_with_an_incomplete_roster_is_swept",
        ("plugin/bin/prawduct-hook", "cmd_clear", "review_active()"):
            "tests/test_critic_session_guard.py::TestClearGuardCLI"
            "::test_bare_clear_refuses_with_active_marker",
        # ONE construction for both surfaces that meet a marker without forcing.
        # The bare-clear path used to release markers by side effect of asking
        # `review_active`, which is why the row below covers a `clear` with no
        # `--session-start` as well as a boundary.
        ("plugin/bin/prawduct-hook", "_release_or_keep_marker", "boundary_sweep()"):
            "tests/test_critic_session_guard.py::TestBareClearUsesTheSameReleaseRule"
            "::test_a_bare_clear_keeps_a_complete_roster_and_says_why",
        ("plugin/bin/prawduct-hook", "cmd_clear", "clear_marker()"):
            "tests/test_critic_session_guard.py::TestClearGuardCLI"
            "::test_force_overrides_active_marker",
        ("plugin/bin/prawduct-hook", "cmd_critic_begin", "write_marker()"):
            "tests/test_critic_session_guard.py::TestCriticBeginEndCLI"
            "::test_begin_writes_then_end_removes",
        ("plugin/bin/prawduct-hook", "cmd_critic_end", "clear_marker()"):
            "tests/test_critic_session_guard.py::TestCriticBeginEndCLI"
            "::test_begin_writes_then_end_removes",
        ("plugin/bin/prawduct-hook", "cmd_critic_discard", "clear_marker()"):
            "tests/test_critic_session_guard.py::TestConcurrentDispatchGuard"
            "::test_critic_discard_unblocks_a_stranded_roster_and_archives_it",
        # The cross-session reader the whole enumeration exists for: it has NO
        # TTL, so it is the one that keeps firing after every in-session signal
        # is gone — and it consolidates rather than merely blocking.
        ("plugin/bin/prawduct-hook", "cmd_stop", "marker_present()"):
            "tests/test_stop_abandoned_critic.py::TestChunk05ConsolidateOrBlock"
            "::test_complete_partials_self_heal",
        ("plugin/lib/critic_consolidate.py", "begin_review", "review_active()"):
            "tests/test_critic_session_guard.py::TestConcurrentDispatchGuard"
            "::test_refuses_while_a_review_is_live_and_leaves_it_intact",
        ("plugin/lib/critic_consolidate.py", "restore_review", "review_active()"):
            "tests/test_critic_session_guard.py::TestRestoreEdgeStates"
            "::test_a_live_marker_with_no_partials_is_refused_with_critic_end",
        ("plugin/lib/critic_consolidate.py", "consolidate", "clear_marker()"):
            "tests/test_critic_consolidate.py::TestBeginMarksFindingsSuperseded"
            "::test_consolidation_clears_the_marker",
        # --- the findings record: the derived cache every builder actually reads ---
        ("plugin/lib/critic_consolidate.py", "consolidate", ".critic-findings.json"):
            "tests/test_critic_consolidate.py::TestConsolidateIntegration"
            "::test_complete_partials_at_head_consolidates",
        ("plugin/lib/critic_consolidate.py", "_mark_cache_superseded", ".critic-findings.json"):
            "tests/test_critic_consolidate.py::TestBeginMarksFindingsSuperseded"
            "::test_dispatch_marks_the_prior_record_naming_both_reviews",
        ("plugin/lib/critic_consolidate.py", "_prior_review_fact", ".critic-findings.json"):
            "tests/test_critic_consolidate.py::TestBeginMarksFindingsSuperseded"
            "::test_verify_still_anchors_after_an_abandoned_review",
        ("plugin/lib/critic_consolidate.py", "_already_consolidated_note", ".critic-findings.json"):
            "tests/test_critic_consolidate.py::TestConsolidateIntegration"
            "::test_already_consolidated_noop_reports_the_recorded_findings",
        # The reader that made the superseded marker necessary: a builder who
        # lost the reviewer's report reads this and nothing else.
        ("plugin/lib/briefing.py", "_summarize_critic_findings", ".critic-findings.json"):
            "tests/test_briefing_functions.py::TestSummarizeCriticFindings"
            "::test_a_superseded_record_says_so_before_anything_it_qualifies",
        ("plugin/lib/critic_mode.py", "_rule_verify_resolutions_fires", ".critic-findings.json"):
            "tests/test_critic_mode_inference.py::TestRule1VerifyResolutions"
            "::test_wins_when_diff_is_subset_of_prior_scope",
        ("plugin/lib/critic_mode.py", "_rule_postfix_fix_fires", ".critic-findings.json"):
            "tests/test_critic_mode_inference.py::TestRule1bPostCumulativeFix"
            "::test_fires_for_committed_fix_after_clean_cumulative",
        ("plugin/lib/critic_mode.py", "_fresh_cumulative_covers_head", ".critic-findings.json"):
            "tests/test_critic_mode_inference.py::TestRule2Cumulative"
            "::test_does_not_fire_when_cumulative_record_covers_head",
        ("plugin/lib/ledger.py", "ledger_append", ".critic-findings.json"):
            "tests/test_governance_ledger.py::TestLedgerAppendEnvelope"
            "::test_envelope_fields_and_payload_equality",
        # --- neither reads them: both name the paths so a product repo ignores
        #     them. Listed because a scan that skipped them would be a scan the
        #     next reader could not trust to be complete.
        ("plugin/bin/prawduct-hook", "<module>", ".prawduct/.critic-active"):
            "tests/test_build_plan_resolution.py::TestSessionGitignoreMirror"
            "::test_session_file_sets_match",
        ("plugin/bin/prawduct-hook", "<module>", ".prawduct/.critic-findings.json"):
            "tests/test_build_plan_resolution.py::TestSessionGitignoreMirror"
            "::test_session_file_sets_match",
        ("plugin/lib/core.py", "<module>", ".prawduct/.critic-active"):
            "tests/test_build_plan_resolution.py::TestSessionGitignoreMirror"
            "::test_session_file_sets_match",
        ("plugin/lib/core.py", "<module>", ".prawduct/.critic-findings.json"):
            "tests/test_build_plan_resolution.py::TestSessionGitignoreMirror"
            "::test_session_file_sets_match",
    }

    #: The marker API. A call to one of these is a site; so is a literal naming
    #: either file. Both halves are needed — an API call can reach the marker
    #: without naming it, and a path literal can reach it without the API.
    _MARKER_API = frozenset(
        {"review_active", "marker_present", "clear_marker", "write_marker", "boundary_sweep"}
    )
    _PATHS = frozenset({
        ".critic-active", ".prawduct/.critic-active",
        ".critic-findings.json", ".prawduct/.critic-findings.json",
    })
    _MARKER_MODULE = "plugin/lib/critic_marker.py"

    @classmethod
    def _scan(cls) -> set[tuple[str, str, str]]:
        """Every site in the plugin that calls the marker API or names either
        file, by (file, enclosing definition, what it touches).

        Docstrings are skipped — a module explaining the marker is not a reader
        of it — and comments never reach the AST at all, so prose about the
        subsystem cannot inflate the inventory. Bare-name calls count only
        inside `critic_marker` itself, where the API is local; elsewhere a
        module-qualified call is the only way in, and counting bare names would
        pick up unrelated functions that happen to share one (`banner.py` has
        its own `write_marker`, for the version marker).
        """
        import ast  # noqa: PLC0415 — a scanner used by one test

        root = Path(__file__).resolve().parent.parent
        sites: set[tuple[str, str, str]] = set()
        files = sorted(set((root / "plugin").rglob("*.py")) | {root / "plugin/bin/prawduct-hook"})
        for path in files:
            rel = str(path.relative_to(root))
            visitor = _ReaderSiteVisitor(rel, cls._MARKER_API, cls._PATHS, cls._MARKER_MODULE)
            visitor.visit(ast.parse(path.read_text()))
            sites |= visitor.sites
        return sites

    def test_every_site_that_meets_the_marker_or_the_record_is_inventoried(self):
        found = self._scan()
        inventoried = set(self.INVENTORY)
        unlisted = found - inventoried
        assert not unlisted, (
            "a new reader of the critic marker or findings record is not in the "
            f"inventory: {sorted(unlisted)}. Add it with the test that exercises "
            "it — this subsystem's readers outlive the session, so 'nothing in "
            "session can see it' has twice been the wrong argument."
        )
        gone = inventoried - found
        assert not gone, (
            f"the inventory names sites that no longer exist: {sorted(gone)}. "
            "Remove them — a stale inventory is a list nobody can trust to be complete."
        )

    def test_nothing_renews_a_marker_mid_review(self):
        """`write_marker`'s docstring rests on there being exactly one writer.

        It used to claim the opposite — "an over-running review can renew its
        own protection" — which is the kind of statement a reader believes and
        then designs around: it says the TTL is a rolling window when it is a
        deadline from dispatch. The claim is checkable, so it is checked here
        rather than left as prose that quietly stops being true the day someone
        adds a second writer.
        """
        writers = {site for site in self._scan() if site[2] == "write_marker()"}
        assert writers == {
            ("plugin/bin/prawduct-hook", "cmd_critic_begin", "write_marker()")
        }, (
            "a second writer makes the marker's timestamp a renewal rather than a "
            "dispatch time — reconcile `write_marker`'s docstring before adding one"
        )

    def test_every_inventoried_site_names_a_test_that_exists(self):
        """The inventory's worth is the exercise, not the listing. A reference
        that has been renamed away is the same thing as no test at all, and
        nothing else would notice."""
        import ast  # noqa: PLC0415 — a scanner used by one test

        root = Path(__file__).resolve().parent.parent
        missing = []
        for site, ref in sorted(self.INVENTORY.items()):
            rel, cls_name, test_name = ref.split("::")
            source = root / rel
            if not source.is_file():
                missing.append(f"{site} → {ref} (no such file)")
                continue
            tree = ast.parse(source.read_text())
            found = any(
                isinstance(node, ast.ClassDef)
                and node.name == cls_name
                and any(
                    isinstance(fn, ast.FunctionDef) and fn.name == test_name
                    for fn in node.body
                )
                for node in tree.body
            )
            if not found:
                missing.append(f"{site} → {ref}")
        assert not missing, "inventory points at tests that do not exist: " + "; ".join(missing)


class _ReaderSiteVisitor:
    """AST walk collecting marker/findings sites; see the inventory test above.

    A plain class rather than a nested closure so the recursion carries the
    enclosing-definition stack explicitly — the stack IS the site's identity,
    and a site attributed to the wrong function would send the next reader to
    the wrong test.
    """

    def __init__(self, rel: str, api: frozenset, paths: frozenset, marker_module: str):
        self.rel = rel
        self.api = api
        self.paths = paths
        self.marker_module = marker_module
        self.enclosing: list[str] = []
        self.sites: set[tuple[str, str, str]] = set()

    def _where(self) -> str:
        return "::".join(self.enclosing) or "<module>"

    def visit(self, node) -> None:
        import ast  # noqa: PLC0415 — a scanner used by one test

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            self.enclosing.append(node.name)
            for child in ast.iter_child_nodes(node):
                self.visit(child)
            self.enclosing.pop()
            return
        # A bare string statement is a docstring: prose about the marker, not a
        # reader of it.
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            return
        if isinstance(node, ast.Call):
            fn = node.func
            name = None
            if isinstance(fn, ast.Attribute):
                name = fn.attr
            elif isinstance(fn, ast.Name) and self.rel == self.marker_module:
                name = fn.id
            if name in self.api:
                self.sites.add((self.rel, self._where(), name + "()"))
        if isinstance(node, ast.Constant) and node.value in self.paths:
            self.sites.add((self.rel, self._where(), node.value))
        for child in ast.iter_child_nodes(node):
            self.visit(child)


class TestBareClearUsesTheSameReleaseRule:
    """A bare `prawduct-hook clear` is the invocation this whole guard exists
    for — a reviewer subagent ran exactly it and clobbered the session under
    review — and it is also a surface that meets an expired marker.

    It used to release one by SIDE EFFECT: it asked `review_active` whether to
    refuse and the answer came back with the marker already unlinked. So a
    review whose reviewers had all reported lost the Stop hook's self-heal
    silently, at the one call site the guard was written to protect, while the
    boundary beside it had just been taught not to do that. The rule now has one
    home and both callers route through it.
    """

    def test_a_bare_clear_keeps_a_complete_roster_and_says_why(self, tmp_path):
        prawduct = _prawduct(tmp_path)
        _expired(prawduct)
        _dispatched(prawduct, complete=True)

        result = run_plugin_hook("clear", tmp_path, git_status=" M a.py")

        assert result.returncode == 0, result.stderr
        assert (prawduct / cm.MARKER_NAME).is_file(), (
            "a bare clear must not discard a finished review's self-heal — the "
            "boundary beside it does not, and this is the same decision"
        )
        assert "prawduct-hook critic-consolidate" in result.stdout
        assert (prawduct / ".session-start").is_file(), "the clear itself still runs"

    def test_a_bare_clear_still_releases_a_marker_with_nothing_attached(self, tmp_path):
        """The other half: a crashed review must not brick `clear` forever, so
        an expired marker with nothing recoverable behind it still goes — now
        with the notice the boundary gives it."""
        prawduct = _prawduct(tmp_path)
        _expired(prawduct)

        result = run_plugin_hook("clear", tmp_path, git_status=" M a.py")

        assert result.returncode == 0, result.stderr
        assert not (prawduct / cm.MARKER_NAME).is_file()
        assert "swept" in result.stdout
        assert (prawduct / ".session-start").is_file()

    def test_a_live_marker_still_refuses_a_bare_clear(self, tmp_path):
        """The guard's original job, unchanged by sharing the release rule."""
        prawduct = _prawduct(tmp_path)
        cm.write_marker(prawduct)

        result = run_plugin_hook("clear", tmp_path)

        assert result.returncode == 2
        assert (prawduct / cm.MARKER_NAME).is_file()
        assert not (prawduct / ".session-start").is_file()


class TestAnUnanswerableRosterIsAnnouncedAsItself:
    """The third retention token had no head of its own and inherited the
    liveness one — "no session event proves its reviewers died", a claim about
    TIME, printed for a marker the TTL had already released. The body then said
    the state could not be read, so the notice argued with itself, and the head
    is the half that tells someone waiting is fine."""

    def test_the_unknown_head_names_its_own_ground_and_carries_the_cause(self, tmp_path):
        prawduct = _prawduct(tmp_path)
        _expired(prawduct)

        def explode(_prawduct_dir):
            raise RuntimeError("consolidation lib unavailable")

        import unittest.mock as mock  # noqa: PLC0415 — one test needs the lib to fail

        with mock.patch.object(cc, "pending_state", explode):
            outcome = cm.boundary_sweep(prawduct)

        assert outcome == cm.SWEEP_RETAINED_UNKNOWN
        assert (prawduct / cm.MARKER_NAME).is_file()
        # The CAUSE, not a paraphrase: on the one path where the lib is genuinely
        # broken, the exception is the only thing that says which way.
        assert "RuntimeError" in (cm.LAST_ROSTER_ERROR or "")
        assert "consolidation lib unavailable" in (cm.LAST_ROSTER_ERROR or "")

    def test_the_notice_for_an_unanswerable_roster_does_not_claim_liveness(self, tmp_path):
        """The head an operator actually reads. Loaded in-process rather than
        driven through the CLI: the branch is reachable only when the
        consolidation lib cannot answer, and there is no honest way to arrange
        that across a subprocess boundary without breaking the install itself.
        """
        import importlib.machinery  # noqa: PLC0415 — the extensionless hook script
        import importlib.util  # noqa: PLC0415
        import unittest.mock as mock  # noqa: PLC0415

        loader = importlib.machinery.SourceFileLoader(
            "prawduct_hook_retention_notice",
            str(Path(__file__).resolve().parent.parent / "plugin" / "bin" / "prawduct-hook"),
        )
        spec = importlib.util.spec_from_loader(loader.name, loader)
        hook = importlib.util.module_from_spec(spec)
        loader.exec_module(hook)

        prawduct = _prawduct(tmp_path)
        _expired(prawduct)
        with mock.patch.object(cc, "pending_state", side_effect=RuntimeError("lib is broken")):
            assert cm.boundary_sweep(prawduct) == cm.SWEEP_RETAINED_UNKNOWN
            notice = hook._boundary_retained_marker_notice(prawduct, cm.SWEEP_RETAINED_UNKNOWN)

        head = notice.splitlines()[0]
        assert "no session event proves its reviewers died" not in head, (
            "that is a claim about TIME, and this marker has already expired — "
            "printed here it tells the reader the reviewers may still be running"
        )
        assert "could not be assessed" in head
        assert "RuntimeError" in head and "lib is broken" in head, (
            "the cause is the only thing that says which way, on the one path "
            "where the consolidation lib is genuinely broken"
        )

    def test_a_successful_roster_read_clears_the_recorded_cause(self, tmp_path):
        """A stale cause is worse than none — it would be printed beside the
        NEXT retention, attributing a failure that did not happen."""
        prawduct = _prawduct(tmp_path)
        _expired(prawduct)

        def explode(_prawduct_dir):
            raise RuntimeError("transient")

        import unittest.mock as mock  # noqa: PLC0415 — one test needs the lib to fail

        with mock.patch.object(cc, "pending_state", explode):
            cm.boundary_sweep(prawduct)
        assert cm.LAST_ROSTER_ERROR is not None

        _expired(prawduct)
        _dispatched(prawduct, complete=True)
        assert cm.boundary_sweep(prawduct) == cm.SWEEP_RETAINED_COMPLETE
        assert cm.LAST_ROSTER_ERROR is None
