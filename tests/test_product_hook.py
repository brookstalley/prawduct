"""Tests for product-hook — session governance Python script.

Invokes the hook via subprocess.run with a controlled environment.
Uses a mock git script to simulate git status output.
"""

from __future__ import annotations

import json
import os
import subprocess
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

HOOK_PATH = Path(__file__).resolve().parent.parent / "tools" / "product-hook"


def run_hook(
    command: str,
    project_dir: Path,
    *,
    git_output: str | None = "",
    env_extra: dict[str, str] | None = None,
    has_git: bool = True,
) -> subprocess.CompletedProcess:
    """Run product-hook with a controlled environment.

    Args:
        command: Hook command ('clear', 'stop', or invalid).
        project_dir: The simulated project directory.
        git_output: What the mock git status --porcelain should return.
            None means git is not available.
        env_extra: Additional env vars to set.
        has_git: Whether to make git available on PATH.
    """
    env = {
        "HOME": str(project_dir),
        "CLAUDE_PROJECT_DIR": str(project_dir),
        "PATH": "",
    }

    if has_git and git_output is not None:
        # Create a mock git that returns preset output
        mock_bin = project_dir / "_mock_bin"
        mock_bin.mkdir(exist_ok=True)
        mock_git = mock_bin / "git"
        mock_git.write_text(textwrap.dedent(f"""\
            #!/bin/bash
            if [[ "$1" == "rev-parse" ]]; then
                echo ".git"
                exit 0
            fi
            if [[ "$1" == "status" ]]; then
                printf '%s' '{git_output}'
                exit 0
            fi
            exit 0
        """))
        mock_git.chmod(0o755)
        env["PATH"] = str(mock_bin)
    elif not has_git:
        pass

    # Need system tools (python3 itself, etc.)
    system_paths = "/usr/bin:/bin:/usr/sbin:/sbin"
    if env["PATH"]:
        env["PATH"] = env["PATH"] + ":" + system_paths
    else:
        env["PATH"] = system_paths

    if env_extra:
        env.update(env_extra)

    return subprocess.run(
        ["python3", str(HOOK_PATH), command],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )


def make_session_start(prawduct_dir: Path, offset_seconds: int = -60) -> str:
    """Create a .session-start file. Returns the timestamp written."""
    ts = datetime.now(timezone.utc) + timedelta(seconds=offset_seconds)
    stamp = ts.strftime("%Y-%m-%dT%H:%M:%SZ")
    (prawduct_dir / ".session-start").write_text(stamp)
    return stamp


# =============================================================================
# clear command
# =============================================================================


class TestClear:
    def test_resets_session_state(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-reflected").write_text("old reflection")
        (prawduct / ".session-start").write_text("old timestamp")

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert not (prawduct / ".session-reflected").exists()
        assert (prawduct / ".session-start").exists()

    def test_creates_session_start_timestamp(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        run_hook("clear", tmp_path)

        content = (prawduct / ".session-start").read_text().strip()
        assert content.endswith("Z")
        datetime.strptime(content, "%Y-%m-%dT%H:%M:%SZ")


# =============================================================================
# stop command
# =============================================================================


class TestStopNoPrawduct:
    def test_no_prawduct_dir_exits_clean(self, tmp_path: Path):
        result = run_hook("stop", tmp_path)
        assert result.returncode == 0


class TestStopNoChanges:
    def test_no_changes_exits_clean(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        result = run_hook("stop", tmp_path, git_output="")
        assert result.returncode == 0


class TestStopReflectionGate:
    def test_changes_no_reflection_blocks(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        # Clean baseline so " M src/app.py" is a session change
        (prawduct / ".session-git-baseline").write_text("")

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 2
        assert "REFLECTION" in result.stderr

    def test_changes_with_reflection_passes(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("I reflected on changes.")

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 0

    def test_reflection_message_includes_methodology_check(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 2
        assert "methodology" in result.stderr.lower()


class TestSessionScopedChanges:
    """Tests for session-scoped change detection (git baseline comparison)."""

    def test_clear_creates_git_baseline(self, tmp_path: Path):
        """Baseline file should exist after clear."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        run_hook("clear", tmp_path, git_output=" M existing.py")

        assert (prawduct / ".session-git-baseline").exists()
        assert " M existing.py" in (prawduct / ".session-git-baseline").read_text()

    def test_preexisting_changes_no_reflection_needed(self, tmp_path: Path):
        """Same git status as baseline -> no reflection gate."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        # Baseline captured with pre-existing changes
        (prawduct / ".session-git-baseline").write_text(" M existing.py")

        # Current status is identical — no new changes
        result = run_hook("stop", tmp_path, git_output=" M existing.py")

        assert result.returncode == 0

    def test_new_session_changes_require_reflection(self, tmp_path: Path):
        """Git status differs from baseline -> reflection gate fires."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        # Baseline had one file dirty
        (prawduct / ".session-git-baseline").write_text(" M existing.py")

        # Now a different file is changed — not in baseline
        result = run_hook("stop", tmp_path, git_output=" M src/new.py")

        assert result.returncode == 2
        assert "REFLECTION" in result.stderr

    def test_no_baseline_falls_back_to_current(self, tmp_path: Path):
        """Missing baseline file -> uses git_has_changes (backward compat)."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        # No baseline file exists

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 2
        assert "REFLECTION" in result.stderr

    def test_baseline_cleaned_on_clear(self, tmp_path: Path):
        """Clear removes old baseline before creating new one."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("old baseline content")

        run_hook("clear", tmp_path, git_output="")

        # Baseline should now be empty (clean status)
        assert (prawduct / ".session-git-baseline").read_text() == ""


class TestStopCriticGate:
    def test_critic_gate_triggers(self, tmp_path: Path):
        """Build plan + code changes + no findings -> blocked."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n")
        (prawduct / ".session-reflected").write_text("reflected")
        (prawduct / ".session-git-baseline").write_text("")
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 2
        assert "CRITIC" in result.stderr

    def test_critic_gate_passes_with_recent_findings(self, tmp_path: Path):
        """Valid findings with recent mtime -> passes."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n")
        (prawduct / ".session-reflected").write_text("reflected")
        (prawduct / ".session-git-baseline").write_text("")
        make_session_start(prawduct, offset_seconds=-60)

        findings = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "findings": [],
            "summary": "No issues found.",
        }
        (prawduct / ".critic-findings.json").write_text(json.dumps(findings))

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 0

    def test_prawduct_only_changes_skip_critic(self, tmp_path: Path):
        """Only .prawduct/ changes don't trigger Critic gate."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n")
        (prawduct / ".session-reflected").write_text("reflected")
        (prawduct / ".session-git-baseline").write_text("")
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M .prawduct/learnings.md")

        assert result.returncode == 0

    def test_no_git_exits_clean(self, tmp_path: Path):
        """No git available -> gates skip gracefully."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        mock_bin = tmp_path / "_mock_bin"
        mock_bin.mkdir()
        mock_git = mock_bin / "git"
        mock_git.write_text("#!/bin/bash\nexit 1\n")
        mock_git.chmod(0o755)

        result = run_hook(
            "stop", tmp_path, git_output=None, has_git=False,
            env_extra={"PATH": str(mock_bin) + ":/usr/bin:/bin"},
        )

        assert result.returncode == 0

    def test_stale_findings_blocked(self, tmp_path: Path):
        """Findings with mtime before session start -> blocked."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n")
        (prawduct / ".session-reflected").write_text("reflected")
        (prawduct / ".session-git-baseline").write_text("")

        # Create findings file first
        findings = {"findings": [], "summary": "Old findings."}
        (prawduct / ".critic-findings.json").write_text(json.dumps(findings))

        import time
        time.sleep(1.1)

        # Now create session start (after findings)
        make_session_start(prawduct, offset_seconds=0)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 2
        assert "CRITIC" in result.stderr


# =============================================================================
# Content validation
# =============================================================================


class TestCriticContentValidation:
    def _setup_critic_scenario(self, tmp_path: Path, findings_content: str) -> Path:
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n")
        (prawduct / ".session-reflected").write_text("reflected")
        (prawduct / ".session-git-baseline").write_text("")
        make_session_start(prawduct, offset_seconds=-60)
        (prawduct / ".critic-findings.json").write_text(findings_content)
        return prawduct

    def test_rejects_empty_summary(self, tmp_path: Path):
        self._setup_critic_scenario(
            tmp_path,
            json.dumps({"findings": [], "summary": ""}),
        )
        result = run_hook("stop", tmp_path, git_output=" M src/app.py")
        assert result.returncode == 2

    def test_rejects_missing_summary(self, tmp_path: Path):
        self._setup_critic_scenario(
            tmp_path,
            json.dumps({"findings": []}),
        )
        result = run_hook("stop", tmp_path, git_output=" M src/app.py")
        assert result.returncode == 2

    def test_rejects_invalid_json(self, tmp_path: Path):
        self._setup_critic_scenario(tmp_path, "not valid json {{{")
        result = run_hook("stop", tmp_path, git_output=" M src/app.py")
        assert result.returncode == 2

    def test_accepts_real_findings_with_summary(self, tmp_path: Path):
        self._setup_critic_scenario(
            tmp_path,
            json.dumps({
                "findings": [
                    {"check": "Test Integrity", "severity": "warning", "summary": "Missing edge case test"}
                ],
                "summary": "1 warning. Changes ready to proceed after addressing.",
            }),
        )
        result = run_hook("stop", tmp_path, git_output=" M src/app.py")
        assert result.returncode == 0

    def test_accepts_clean_review_with_real_summary(self, tmp_path: Path):
        self._setup_critic_scenario(
            tmp_path,
            json.dumps({
                "findings": [],
                "summary": "No issues found. Changes are ready to proceed.",
            }),
        )
        result = run_hook("stop", tmp_path, git_output=" M src/app.py")
        assert result.returncode == 0


# =============================================================================
# Invalid command
# =============================================================================


class TestInvalidCommand:
    def test_unknown_command(self, tmp_path: Path):
        result = run_hook("bogus", tmp_path)
        assert result.returncode == 1
        assert "Usage" in result.stderr

    def test_no_command(self, tmp_path: Path):
        """No arguments at all."""
        env = {
            "HOME": str(tmp_path),
            "CLAUDE_PROJECT_DIR": str(tmp_path),
            "PATH": "/usr/bin:/bin",
        }
        result = subprocess.run(
            ["python3", str(HOOK_PATH)],
            capture_output=True,
            text=True,
            env=env,
            timeout=10,
        )
        assert result.returncode == 1
        assert "Usage" in result.stderr


# =============================================================================
# Sync trigger (unit test via import)
# =============================================================================


class TestSyncTrigger:
    """Test that clear triggers sync (best-effort)."""

    def test_clear_with_no_manifest_succeeds(self, tmp_path: Path):
        """Clear should succeed even without a manifest (sync is best-effort)."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        result = run_hook("clear", tmp_path)
        assert result.returncode == 0
        assert (prawduct / ".session-start").exists()
