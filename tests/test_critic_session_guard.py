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

_ROOT = Path(__file__).resolve().parent.parent
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
        # Actionable override (the waiver-style correction path).
        assert "CRT-3X9D" in result.stderr
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


class TestCriticBeginEndCLI:
    def test_begin_writes_then_end_removes(self, tmp_path):
        prawduct = _prawduct(tmp_path)
        begin = run_plugin_hook("critic-begin", tmp_path)
        assert begin.returncode == 0, begin.stderr
        marker = prawduct / cm.MARKER_NAME
        assert marker.is_file()
        payload = json.loads(marker.read_text())
        # A parseable server-side timestamp so review_active can age it.
        datetime.strptime(payload["started_at"], "%Y-%m-%dT%H:%M:%SZ")

        end = run_plugin_hook("critic-end", tmp_path)
        assert end.returncode == 0, end.stderr
        assert not marker.is_file()

    def test_end_is_idempotent_when_absent(self, tmp_path):
        _prawduct(tmp_path)
        result = run_plugin_hook("critic-end", tmp_path)
        assert result.returncode == 0, result.stderr

    def test_begin_clears_leftover_partials(self, tmp_path):
        """A waived or stale-failed coordinator review leaves .critic-partials/
        behind (consolidate removes them only on success). A leftover partial at
        the same commit as a fresh dispatch would merge as if the new reviewer
        wrote it, so critic-begin resets the dir — every review starts clean."""
        prawduct = _prawduct(tmp_path)
        partials = prawduct / ".critic-partials"
        partials.mkdir()
        (partials / "manifest.json").write_text("{}")
        (partials / "correctness.json").write_text("{}")

        begin = run_plugin_hook("critic-begin", tmp_path)
        assert begin.returncode == 0, begin.stderr
        assert not partials.exists(), (
            "critic-begin must remove leftover partials from a prior review"
        )
        assert "leftover .critic-partials" in begin.stdout
        assert (prawduct / cm.MARKER_NAME).is_file()

    def test_begin_without_partials_stays_quiet(self, tmp_path):
        prawduct = _prawduct(tmp_path)
        begin = run_plugin_hook("critic-begin", tmp_path)
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
        text = (_ROOT / "skills" / "critic" / "SKILL.md").read_text(encoding="utf-8")
        exit_pos = text.find("Designer-handoff early exit")
        begin_pos = text.find("run `prawduct-hook critic-begin`")
        assert exit_pos != -1, "designer-handoff early-exit instruction missing from SKILL.md"
        assert begin_pos != -1, "critic-begin instruction missing from SKILL.md"
        assert exit_pos < begin_pos, (
            "the designer-handoff early exit must come before critic-begin "
            "(CRT-6F2N: no critic-active marker for a review that never happens)"
        )
