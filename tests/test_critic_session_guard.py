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

_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

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
