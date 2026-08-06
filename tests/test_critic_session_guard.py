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

    def test_stale_marker_is_swept(self, tmp_path):
        # A marker older than the TTL is not active AND is swept on read, so a
        # crashed review self-heals (resilience layer 1).
        prawduct = _prawduct(tmp_path)
        old = datetime.now(timezone.utc) - timedelta(seconds=cm.CRITIC_ACTIVE_TTL_SECONDS + 120)
        marker = _write_marker(prawduct, started_at=_iso(old))
        active, age = cm.review_active(prawduct)
        assert active is False
        assert not marker.is_file(), "stale marker must be swept"

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
        # the override exists, and old markers are swept.
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
        assert not marker.is_file()


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
        assert "--force" in result.stderr and "rm .prawduct/.critic-active" in result.stderr
        # No mutation occurred.
        assert (prawduct / ".session-reflected").read_text() == "builder reflection — must survive"
        assert (prawduct / cm.MARKER_NAME).is_file(), "guard must not remove the marker"
        assert not (prawduct / ".session-start").is_file(), "refused clear must not write session-start"

    def test_session_start_proceeds_and_sweeps_marker(self, tmp_path):
        prawduct = _prawduct(tmp_path)
        cm.write_marker(prawduct)
        result = run_plugin_hook("clear", tmp_path, "--session-start", git_status=" M src/app.py")
        assert result.returncode == 0, result.stderr
        assert not (prawduct / cm.MARKER_NAME).is_file(), "session start must sweep the marker"
        assert (prawduct / ".session-start").is_file()
        assert (prawduct / ".session-git-baseline").read_text() == " M src/app.py"

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
