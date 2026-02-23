"""Tests for product-hook — session governance bash script.

Invokes the hook via subprocess.run with a controlled environment.
Uses a mock git script to simulate git status output.
"""

from __future__ import annotations

import json
import os
import subprocess
import textwrap
from datetime import datetime, timezone
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
        "PATH": "",  # Start with empty PATH
    }

    if has_git and git_output is not None:
        # Create a mock git that returns preset output
        mock_bin = project_dir / "_mock_bin"
        mock_bin.mkdir(exist_ok=True)
        mock_git = mock_bin / "git"
        # The mock handles: rev-parse --git-dir, status --porcelain
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
        # No git on PATH at all — but we need basic tools
        pass

    # Always need basic system tools (date, rm, cat, head, awk, grep, etc.)
    system_paths = "/usr/bin:/bin:/usr/sbin:/sbin"
    if env["PATH"]:
        env["PATH"] = env["PATH"] + ":" + system_paths
    else:
        env["PATH"] = system_paths

    if env_extra:
        env.update(env_extra)

    return subprocess.run(
        ["bash", str(HOOK_PATH), command],
        capture_output=True,
        text=True,
        env=env,
        timeout=10,
    )


def make_session_start(prawduct_dir: Path, offset_seconds: int = -60) -> str:
    """Create a .session-start file. Returns the timestamp written."""
    ts = datetime.now(timezone.utc)
    # offset_seconds < 0 means session started in the past
    from datetime import timedelta

    ts = ts + timedelta(seconds=offset_seconds)
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
        # New session-start should be created
        assert (prawduct / ".session-start").exists()

    def test_creates_session_start_timestamp(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        run_hook("clear", tmp_path)

        content = (prawduct / ".session-start").read_text().strip()
        # Should be ISO 8601 UTC format
        assert content.endswith("Z")
        # Should parse as a valid timestamp
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

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 2
        assert "REFLECTION" in result.stderr

    def test_changes_with_reflection_passes(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-reflected").write_text("I reflected on changes.")

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 0


class TestStopCriticGate:
    def test_critic_gate_triggers(self, tmp_path: Path):
        """Build plan + code changes + no findings → blocked."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n")
        (prawduct / ".session-reflected").write_text("reflected")
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 2
        assert "CRITIC" in result.stderr

    def test_critic_gate_passes_with_recent_findings(self, tmp_path: Path):
        """Valid findings with recent mtime → passes."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n")
        (prawduct / ".session-reflected").write_text("reflected")
        make_session_start(prawduct, offset_seconds=-60)

        # Create findings file (after session start)
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
        make_session_start(prawduct)

        # Only .prawduct files changed — no code changes
        result = run_hook("stop", tmp_path, git_output=" M .prawduct/learnings.md")

        assert result.returncode == 0

    def test_no_git_exits_clean(self, tmp_path: Path):
        """No git available → gates skip gracefully."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        # Create a mock git that always fails (simulating no git repo)
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
        """Findings with mtime before session start → blocked."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n")
        (prawduct / ".session-reflected").write_text("reflected")

        # Create findings file first
        findings = {"findings": [], "summary": "Old findings."}
        (prawduct / ".critic-findings.json").write_text(json.dumps(findings))

        import time
        time.sleep(1.1)  # Ensure mtime is strictly before session start

        # Now create session start (after findings)
        make_session_start(prawduct, offset_seconds=0)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 2
        assert "CRITIC" in result.stderr


# =============================================================================
# Content validation (Chunk 3 — strengthened Critic gate)
# =============================================================================


class TestCriticContentValidation:
    """Tests for the content validation added to the Critic gate."""

    def _setup_critic_scenario(self, tmp_path: Path, findings_content: str) -> Path:
        """Set up a scenario where mtime check passes and content is validated."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n")
        (prawduct / ".session-reflected").write_text("reflected")
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

    def test_no_python3_falls_back_to_mtime_only(self, tmp_path: Path):
        """Without python3, falls back to mtime-only check (passes)."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n")
        (prawduct / ".session-reflected").write_text("reflected")
        make_session_start(prawduct, offset_seconds=-60)
        # Rubber-stamp content that would fail validation
        (prawduct / ".critic-findings.json").write_text(
            json.dumps({"findings": [], "summary": ""})
        )

        # Build a mock_bin with git + essential tools but NO python3
        mock_bin = tmp_path / "_mock_bin_nopy"
        mock_bin.mkdir()
        mock_git = mock_bin / "git"
        mock_git.write_text(
            '#!/bin/bash\nif [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi\n'
            'if [[ "$1" == "status" ]]; then printf " M src/app.py"; exit 0; fi\nexit 0\n'
        )
        mock_git.chmod(0o755)
        # Symlink tools the hook needs from /usr/bin (head, awk, grep) but NOT python3
        import shutil
        for tool in ["head", "awk", "grep"]:
            tool_path = shutil.which(tool)
            if tool_path:
                os.symlink(tool_path, mock_bin / tool)

        result = run_hook(
            "stop", tmp_path, git_output=" M src/app.py",
            env_extra={"PATH": str(mock_bin) + ":/bin"},
        )

        assert result.returncode == 0


# =============================================================================
# Invalid command
# =============================================================================


class TestInvalidCommand:
    def test_unknown_command(self, tmp_path: Path):
        result = run_hook("bogus", tmp_path)

        assert result.returncode == 1
        assert "Usage" in result.stderr
