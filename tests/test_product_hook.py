"""Tests for product-hook — session governance Python script.

Invokes the hook via subprocess.run with a controlled environment.
Uses a mock git script to simulate git status output.
"""

from __future__ import annotations

import json
import os
import subprocess
import textwrap
import time
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
    head_sha: str = "deadbeef" * 5,
    git_branch: str = "main",
    gh_pr_list_json: str = "[]",
) -> subprocess.CompletedProcess:
    """Run product-hook with a controlled environment.

    Uses a file-based approach for git output to safely handle multi-line
    content (avoids textwrap.dedent breaking the shebang).

    Args:
        command: Hook command ('clear', 'stop', or invalid).
        project_dir: The simulated project directory.
        git_output: What the mock git status --porcelain should return.
            None means git is not available.
        env_extra: Additional env vars to set.
        has_git: Whether to make git available on PATH.
        head_sha: Mock SHA returned by `git rev-parse HEAD`. Default is
            deterministic for stable test output.
        git_branch: What `git branch --show-current` returns. Defaults to "main"
            so the PR gate doesn't fire by default in tests that don't care.
        gh_pr_list_json: JSON string returned by `gh pr list`. Defaults to "[]"
            (no PRs). Set to e.g. '[{"number": 1}]' to simulate a PR existing.
    """
    env = {
        "HOME": str(project_dir),
        "CLAUDE_PROJECT_DIR": str(project_dir),
        "PATH": "",
    }

    if has_git and git_output is not None:
        mock_bin = project_dir / "_mock_bin"
        mock_bin.mkdir(exist_ok=True)

        # Write git status output to a file for safe multi-line handling
        git_output_file = mock_bin / "_git_status_output"
        git_output_file.write_text(git_output)

        mock_git = mock_bin / "git"
        mock_git.write_text(
            "#!/bin/bash\n"
            'if [[ "$1" == "rev-parse" && "$2" == "HEAD" ]]; then\n'
            f'    echo "{head_sha}"\n'
            '    exit 0\n'
            "fi\n"
            'if [[ "$1" == "rev-parse" ]]; then\n'
            '    echo ".git"\n'
            '    exit 0\n'
            "fi\n"
            'if [[ "$1" == "status" ]]; then\n'
            f'    cat "{git_output_file}"\n'
            "    exit 0\n"
            "fi\n"
            'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then\n'
            f'    echo "{git_branch}"\n'
            "    exit 0\n"
            "fi\n"
            'if [[ "$1" == "worktree" ]]; then\n'
            "    exit 0\n"
            "fi\n"
            'if [[ "$1" == "ls-files" ]]; then\n'
            "    exit 1\n"
            "fi\n"
            "exit 0\n"
        )
        mock_git.chmod(0o755)

        # Mock gh — only handles `gh pr list ... --json number`
        mock_gh = mock_bin / "gh"
        mock_gh.write_text(
            "#!/bin/bash\n"
            'if [[ "$1" == "pr" && "$2" == "list" ]]; then\n'
            f"    cat <<'JSONEOF'\n{gh_pr_list_json}\nJSONEOF\n"
            "    exit 0\n"
            "fi\n"
            "exit 0\n"
        )
        mock_gh.chmod(0o755)

        env["PATH"] = str(mock_bin)
    elif not has_git:
        pass

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
        timeout=15,
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

    def test_preserves_reflection_to_log(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-reflected").write_text("## Session 1\nI learned things.")

        run_hook("clear", tmp_path)

        log = prawduct / "reflections.md"
        assert log.is_file()
        assert "## Session 1" in log.read_text()
        assert "I learned things." in log.read_text()
        assert not (prawduct / ".session-reflected").exists()

    def test_appends_multiple_reflections(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        # First session
        (prawduct / ".session-reflected").write_text("## Session 1\nFirst.")
        run_hook("clear", tmp_path)

        # Second session
        (prawduct / ".session-reflected").write_text("## Session 2\nSecond.")
        run_hook("clear", tmp_path)

        log = (prawduct / "reflections.md").read_text()
        assert "## Session 1" in log
        assert "## Session 2" in log
        assert "---" in log  # separator between sessions

    def test_skips_empty_reflection(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-reflected").write_text("")

        run_hook("clear", tmp_path)

        assert not (prawduct / "reflections.md").exists()

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
        # Build plan present → reflection is mandatory
        artifacts = prawduct / "artifacts"
        artifacts.mkdir()
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        # Clean baseline so " M src/app.py" is a session change
        (prawduct / ".session-git-baseline").write_text("")

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 2
        assert "REFLECTION" in result.stderr

    def test_changes_with_reflection_passes(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 0

    def test_short_reflection_rejected(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        artifacts = prawduct / "artifacts"
        artifacts.mkdir()
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("too short")

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 2
        assert "REFLECTION" in result.stderr

    def test_reflection_message_includes_methodology_check(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        artifacts = prawduct / "artifacts"
        artifacts.mkdir()
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
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
        """Git status differs from baseline + build plan -> reflection gate fires."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        artifacts = prawduct / "artifacts"
        artifacts.mkdir()
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        # Baseline had one file dirty
        (prawduct / ".session-git-baseline").write_text(" M existing.py")

        # Now a different file is changed — not in baseline
        result = run_hook("stop", tmp_path, git_output=" M src/new.py")

        assert result.returncode == 2
        assert "REFLECTION" in result.stderr

    def test_no_baseline_falls_back_to_current(self, tmp_path: Path):
        """Missing baseline file + build plan -> uses git_has_changes (backward compat)."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        artifacts = prawduct / "artifacts"
        artifacts.mkdir()
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
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


class TestSessionChangesDocOnly:
    """Tests for _session_changes_are_doc_only() — gates reflection for doc-only edits."""

    def test_single_md_change_skips_reflection(self, tmp_path: Path):
        """Single .md file changed -> doc-only -> no reflection gate."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")

        result = run_hook("stop", tmp_path, git_output=" M docs/README.md")

        assert result.returncode == 0

    def test_metadata_only_no_gate(self, tmp_path: Path):
        """Only .prawduct metadata changed -> no session changes -> no gate."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")

        result = run_hook("stop", tmp_path, git_output=" M .prawduct/project-state.yaml")

        assert result.returncode == 0

    def test_no_changes_no_gate(self, tmp_path: Path):
        """No changes at all -> no gate (has_changes is False)."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")

        result = run_hook("stop", tmp_path, git_output="")

        assert result.returncode == 0

    def test_multiple_md_changes_skip_reflection(self, tmp_path: Path):
        """Multiple .md files changed -> doc-only -> no reflection gate."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")

        result = run_hook("stop", tmp_path, git_output=" M docs/README.md\n M CHANGELOG.md")

        assert result.returncode == 0

    def test_mixed_md_and_code_requires_reflection(self, tmp_path: Path):
        """Mix of .md and code files + build plan -> not doc-only -> reflection gate fires."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        artifacts = prawduct / "artifacts"
        artifacts.mkdir()
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-git-baseline").write_text("")

        result = run_hook("stop", tmp_path, git_output=" M docs/README.md\n M src/app.py")

        assert result.returncode == 2
        assert "REFLECTION" in result.stderr


class TestStopCriticGate:
    def test_critic_gate_triggers(self, tmp_path: Path):
        """Active build plan + code changes + no findings -> blocked."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
        (prawduct / ".session-git-baseline").write_text("")
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 2
        assert "CRITIC" in result.stderr

    def test_critic_gate_triggers_from_project_state(self, tmp_path: Path):
        """Active build plan in project-state.yaml (no build-plan.md) -> Critic gate fires."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        state_yaml = "build_plan:\n  strategy: feature-first\n  chunks:\n    - id: chunk-01\n      status: in_progress\n"
        (prawduct / "project-state.yaml").write_text(state_yaml)
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
        (prawduct / ".session-git-baseline").write_text("")
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 2
        assert "CRITIC" in result.stderr

    def test_empty_chunks_skips_critic(self, tmp_path: Path):
        """Build plan with chunks: [] (template default) -> Critic gate skipped."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        state_yaml = "build_plan:\n  strategy: null\n  chunks: []\n  current_chunk: null\n"
        (prawduct / "project-state.yaml").write_text(state_yaml)
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
        (prawduct / ".session-git-baseline").write_text("")
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")
        assert result.returncode == 0

    def test_all_chunks_complete_skips_critic(self, tmp_path: Path):
        """All chunks status: complete -> Critic gate skipped (plan is finished)."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        state_yaml = (
            "build_plan:\n  strategy: feature-first\n  chunks:\n"
            "    - id: chunk-01\n      status: complete\n"
            "    - id: chunk-02\n      status: complete\n"
        )
        (prawduct / "project-state.yaml").write_text(state_yaml)
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
        (prawduct / ".session-git-baseline").write_text("")
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")
        assert result.returncode == 0

    def test_mixed_chunks_triggers_critic(self, tmp_path: Path):
        """One complete + one pending chunk -> Critic gate fires."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        state_yaml = (
            "build_plan:\n  strategy: feature-first\n  chunks:\n"
            "    - id: chunk-01\n      status: complete\n"
            "    - id: chunk-02\n      status: pending\n"
        )
        (prawduct / "project-state.yaml").write_text(state_yaml)
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
        (prawduct / ".session-git-baseline").write_text("")
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")
        assert result.returncode == 2
        assert "CRITIC" in result.stderr

    def test_no_build_plan_anywhere_skips_critic(self, tmp_path: Path):
        """No build-plan.md and no build plan in project-state -> Critic gate skipped."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        state_yaml = "current_phase: discovery\n\nopen_questions: []\n"
        (prawduct / "project-state.yaml").write_text(state_yaml)
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
        (prawduct / ".session-git-baseline").write_text("")
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 0

    def test_completed_build_plan_skips_critic(self, tmp_path: Path):
        """Completed build plan (all [x]) + code changes -> Critic gate skipped."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text(
            "# Build Plan\n\n## Status\n- [x] Chunk 1 — done\n- [x] Chunk 2 — done\n"
        )
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
        (prawduct / ".session-git-baseline").write_text("")
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 0

    def test_critic_gate_passes_with_recent_findings(self, tmp_path: Path):
        """Valid findings with recent mtime -> passes."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
        (prawduct / ".session-git-baseline").write_text("")
        make_session_start(prawduct, offset_seconds=-60)

        findings = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "files_reviewed": ["src/app.py"],
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
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
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
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
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
# Doc-only and waiver behavior on Critic and PR gates
# =============================================================================


class TestDocOnlySkipsCriticGate:
    """Doc-only sessions should not require Critic review even with an active build plan."""

    def test_md_only_skips_critic_with_active_build_plan(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-git-baseline").write_text("")
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M docs/README.md\n M CHANGELOG.md")

        assert result.returncode == 0
        assert "CRITIC" not in result.stderr

    def test_mixed_doc_and_code_still_triggers_critic(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
        (prawduct / ".session-git-baseline").write_text("")
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M docs/README.md\n M src/app.py")

        assert result.returncode == 2
        assert "CRITIC" in result.stderr


class TestGatesWaived:
    """Agent-declared gate waivers via .gates-waived JSON."""

    def test_critic_waiver_skips_critic_gate(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".gates-waived").write_text(json.dumps({"critic": "trivial config bump, no logic changes"}))
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 0
        assert "CRITIC" not in result.stderr
        assert "GATE WAIVERS" in result.stderr
        assert "trivial config bump" in result.stderr

    def test_reflection_waiver_skips_reflection_gate(self, tmp_path: Path):
        """Reflection waiver suppresses the BLOCKING reflection gate (active build plan)."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        # Active build plan -> reflection gate is BLOCKING. Without waiver this returns 2.
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        # Critic findings already valid so the Critic gate doesn't fire and pollute the test.
        (prawduct / ".critic-findings.json").write_text(json.dumps({
            "files_reviewed": ["src/app.py"],
            "findings": [],
            "summary": "No issues found.",
        }))
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".gates-waived").write_text(json.dumps({"reflection": "minor cleanup, nothing to learn"}))
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 0, f"stderr={result.stderr}"
        assert "REFLECTION" not in result.stderr
        assert "minor cleanup" in result.stderr

    def test_critic_waiver_not_noted_when_findings_present(self, tmp_path: Path):
        """If Critic findings already exist, the gate would not have fired -
        the waiver is a no-op and should not be noted."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".critic-findings.json").write_text(json.dumps({
            "files_reviewed": ["src/app.py"],
            "findings": [],
            "summary": "No issues found.",
        }))
        (prawduct / ".gates-waived").write_text(json.dumps({"critic": "shouldn't print"}))
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 0
        # Waiver should NOT be noted because the gate would have been silent
        assert "GATE WAIVERS" not in result.stderr
        assert "shouldn't print" not in result.stderr

    def test_unknown_waiver_keys_warn(self, tmp_path: Path):
        """Typo in waiver key produces a stderr warning so the agent learns."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".gates-waived").write_text(json.dumps({"critc": "typo"}))

        result = run_hook("stop", tmp_path, git_output=" M docs/README.md")

        assert "unknown keys" in result.stderr
        assert "critc" in result.stderr

    def test_pr_waiver_suppresses_pr_blocker(self, tmp_path: Path):
        """PR waiver suppresses the BLOCKING PR REVIEW gate when a real PR exists with no evidence."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".gates-waived").write_text(json.dumps({"pr": "shipping a hotfix branch, no PR review needed"}))
        make_session_start(prawduct)

        result = run_hook(
            "stop",
            tmp_path,
            git_output=" M src/app.py",
            git_branch="feature/foo",
            gh_pr_list_json='[{"number": 42}]',
        )

        assert result.returncode == 0
        assert "PR REVIEW" not in result.stderr
        assert "shipping a hotfix" in result.stderr

    def test_pr_waiver_not_noted_when_no_pr_exists(self, tmp_path: Path):
        """PR waiver on a branch with no PR is a no-op — should not be noted."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".gates-waived").write_text(json.dumps({"pr": "no need"}))
        make_session_start(prawduct)

        result = run_hook(
            "stop",
            tmp_path,
            git_output=" M src/app.py",
            git_branch="feature/foo",
            gh_pr_list_json="[]",
        )

        assert result.returncode == 0
        assert "GATE WAIVERS" not in result.stderr
        assert "no need" not in result.stderr

    def test_boolean_waiver_value_is_ignored(self, tmp_path: Path):
        """`True` is not a valid reason — must require a real string."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".gates-waived").write_text(json.dumps({"critic": True}))
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 2
        assert "CRITIC" in result.stderr

    def test_pr_waiver_with_empty_reason_ignored(self, tmp_path: Path):
        """Empty pr reason -> waiver ignored -> blocker fires."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".gates-waived").write_text(json.dumps({"pr": ""}))
        make_session_start(prawduct)

        result = run_hook(
            "stop",
            tmp_path,
            git_output=" M src/app.py",
            git_branch="feature/foo",
            gh_pr_list_json='[{"number": 42}]',
        )

        assert result.returncode == 2
        assert "PR REVIEW" in result.stderr

    def test_invalid_waiver_json_is_ignored(self, tmp_path: Path):
        """Corrupt .gates-waived must not crash the gate or silently bypass it."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".gates-waived").write_text("not valid json {{{")
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        # Invalid waiver = treat as no waiver = critic gate fires normally
        assert result.returncode == 2
        assert "CRITIC" in result.stderr

    def test_empty_value_in_waiver_is_ignored(self, tmp_path: Path):
        """Empty/missing reason -> waiver is ignored. Force the agent to write a real reason."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".gates-waived").write_text(json.dumps({"critic": ""}))
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 2
        assert "CRITIC" in result.stderr

    def test_waiver_file_removed_at_session_start(self, tmp_path: Path):
        """clear should auto-delete .gates-waived so waivers never carry across sessions."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".gates-waived").write_text(json.dumps({"critic": "from previous session"}))

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert not (prawduct / ".gates-waived").exists()


# =============================================================================
# Defensive untrack of session files at session start
# =============================================================================


def _init_real_git_repo(repo_dir: Path) -> None:
    """Initialize a real git repo for tests that need git ls-files / rm --cached."""
    subprocess.run(["git", "init", "--quiet", "-b", "main"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo_dir, check=True)


def _real_git_run_clear(project_dir: Path) -> subprocess.CompletedProcess:
    """Run product-hook clear with real git on PATH (no mock)."""
    env = {
        "HOME": str(project_dir),
        "CLAUDE_PROJECT_DIR": str(project_dir),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
    }
    return subprocess.run(
        ["python3", str(HOOK_PATH), "clear"],
        capture_output=True,
        text=True,
        env=env,
        timeout=20,
    )


class TestGitHasCodeChangesUsesBaseline:
    """git_has_code_changes() must consult the session baseline (mirroring git_has_session_changes)."""

    def test_pre_existing_dirty_files_in_baseline_do_not_trigger_critic(self, tmp_path: Path):
        """A file in the baseline must NOT count as a 'code change' for the Critic gate."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        # Baseline captures src/app.py as ALREADY dirty at session start
        (prawduct / ".session-git-baseline").write_text(" M src/app.py\n")
        make_session_start(prawduct)

        # Current state: SAME dirty file, no new changes
        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        # Critic gate should NOT fire because nothing changed since session start
        assert result.returncode == 0
        assert "CRITIC" not in result.stderr

    def test_new_change_after_baseline_triggers_critic(self, tmp_path: Path):
        """Adding a new file after session start must still trigger the Critic gate."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
        (prawduct / ".session-git-baseline").write_text(" M src/app.py\n")
        make_session_start(prawduct)

        # Baseline had src/app.py; current adds src/new.py
        result = run_hook("stop", tmp_path, git_output=" M src/app.py\n M src/new.py")

        assert result.returncode == 2
        assert "CRITIC" in result.stderr


class TestWorktreeBriefing:
    """The session briefing must surface worktree state when more than one is attached."""

    def test_single_worktree_no_briefing_line(self, tmp_path: Path):
        _init_real_git_repo(tmp_path)
        # Make an initial commit so it's a real-ish repo
        (tmp_path / "README.md").write_text("# test")
        subprocess.run(["git", "add", "README.md"], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)
        (tmp_path / ".prawduct").mkdir()

        result = _real_git_run_clear(tmp_path)
        assert result.returncode == 0
        assert "Worktrees:" not in result.stdout

    def test_multiple_worktrees_surfaced_in_briefing(self, tmp_path: Path):
        main_repo = tmp_path / "main"
        main_repo.mkdir()
        _init_real_git_repo(main_repo)
        (main_repo / "README.md").write_text("# test")
        subprocess.run(["git", "add", "README.md"], cwd=main_repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=main_repo, check=True)

        # Create a second worktree on a feature branch
        feature_path = tmp_path / "feature-wt"
        subprocess.run(
            ["git", "worktree", "add", "-b", "feature/foo", str(feature_path)],
            cwd=main_repo,
            check=True,
            capture_output=True,
        )
        (main_repo / ".prawduct").mkdir()

        result = _real_git_run_clear(main_repo)
        assert result.returncode == 0
        assert "Worktrees:" in result.stdout
        assert "main" in result.stdout
        assert "feature/foo" in result.stdout


class TestDefensiveUntrackOfSessionFiles:
    """cmd_clear must untrack any session files that were accidentally committed."""

    def test_untracks_session_handoff_if_committed(self, tmp_path: Path):
        _init_real_git_repo(tmp_path)
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        handoff = prawduct / ".session-handoff.md"
        handoff.write_text("# stale handoff content from a previous session")

        # Force commit despite gitignore (-f) to simulate the accidental-commit case.
        subprocess.run(["git", "add", "-f", str(handoff)], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "accidental"], cwd=tmp_path, check=True)

        # Verify it's tracked
        ls = subprocess.run(
            ["git", "ls-files", "--error-unmatch", ".prawduct/.session-handoff.md"],
            cwd=tmp_path,
            capture_output=True,
        )
        assert ls.returncode == 0

        result = _real_git_run_clear(tmp_path)
        assert result.returncode == 0
        # Now it should NOT be tracked
        ls2 = subprocess.run(
            ["git", "ls-files", "--error-unmatch", ".prawduct/.session-handoff.md"],
            cwd=tmp_path,
            capture_output=True,
        )
        assert ls2.returncode != 0
        # File on disk preserved (cmd_clear may overwrite with new handoff, but it must exist)
        assert handoff.exists()
        # The user-facing message mentions what happened
        assert "untracked" in result.stdout.lower()

    def test_untracks_multiple_session_files(self, tmp_path: Path):
        _init_real_git_repo(tmp_path)
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        files = {
            ".prawduct/.session-handoff.md": "old handoff",
            ".prawduct/.test-evidence.json": "{}",
            ".prawduct/.critic-findings.json": "{}",
            ".prawduct/.gates-waived": "{}",
        }
        for rel, content in files.items():
            p = tmp_path / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            subprocess.run(["git", "add", "-f", rel], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "all session files"], cwd=tmp_path, check=True)

        result = _real_git_run_clear(tmp_path)
        assert result.returncode == 0
        for rel in files:
            ls = subprocess.run(
                ["git", "ls-files", "--error-unmatch", rel],
                cwd=tmp_path,
                capture_output=True,
            )
            assert ls.returncode != 0, f"{rel} still tracked after clear"

    def test_no_untrack_when_files_not_tracked(self, tmp_path: Path):
        """Clean repo: clear should run silently without printing the untrack notice."""
        _init_real_git_repo(tmp_path)
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        # Make a single committed source file so the repo isn't empty
        (tmp_path / "src.py").write_text("# code")
        subprocess.run(["git", "add", "src.py"], cwd=tmp_path, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=tmp_path, check=True)

        result = _real_git_run_clear(tmp_path)
        assert result.returncode == 0
        assert "untracked previously-committed" not in result.stdout


# =============================================================================
# test-status subcommand
# =============================================================================


class TestTestStatus:
    """The test-status subcommand: trust-the-cycle session-timestamp freshness check."""

    def test_no_evidence_is_stale(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        result = run_hook("test-status", tmp_path, git_output="")

        assert result.returncode == 1
        assert "stale" in result.stdout
        assert "no .test-evidence.json" in result.stdout

    def test_evidence_with_failing_tests_is_stale(self, tmp_path: Path):
        """Failing tests mean evidence is stale regardless of timing."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        (prawduct / ".session-start").write_text(now)
        (prawduct / ".test-evidence.json").write_text(json.dumps({
            "timestamp": now,
            "passed": 100,
            "failed": 3,
            "total": 103,
        }))

        result = run_hook("test-status", tmp_path, git_output="")

        assert result.returncode == 1
        assert "3 test(s) failing" in result.stdout

    def test_evidence_from_this_session_is_current(self, tmp_path: Path):
        """Evidence written after session start is current."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        session_start = "2026-04-17T10:00:00Z"
        evidence_time = "2026-04-17T10:05:00Z"
        (prawduct / ".session-start").write_text(session_start)
        (prawduct / ".test-evidence.json").write_text(json.dumps({
            "timestamp": evidence_time,
            "passed": 100,
            "failed": 0,
            "total": 100,
        }))

        result = run_hook("test-status", tmp_path, git_output="")

        assert result.returncode == 0, result.stdout
        assert "current" in result.stdout
        assert "this session" in result.stdout

    def test_evidence_before_session_start_is_stale(self, tmp_path: Path):
        """Evidence from a previous session is stale."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        session_start = "2026-04-17T10:00:00Z"
        old_evidence = "2026-04-17T09:00:00Z"
        (prawduct / ".session-start").write_text(session_start)
        (prawduct / ".test-evidence.json").write_text(json.dumps({
            "timestamp": old_evidence,
            "passed": 100,
            "failed": 0,
            "total": 100,
        }))

        result = run_hook("test-status", tmp_path, git_output="")

        assert result.returncode == 1
        assert "stale" in result.stdout
        assert "predates session" in result.stdout

    def test_no_timestamp_in_evidence_is_stale(self, tmp_path: Path):
        """Legacy evidence without a timestamp field is stale."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-start").write_text("2026-04-17T10:00:00Z")
        (prawduct / ".test-evidence.json").write_text(json.dumps({
            "git_sha": "deadbeef" * 5,
            "passed": 100,
            "failed": 0,
            "total": 100,
        }))

        result = run_hook("test-status", tmp_path, git_output="")

        assert result.returncode == 1
        assert "no timestamp" in result.stdout

    def test_no_session_marker_accepts_passing_evidence(self, tmp_path: Path):
        """Without a session-start marker, accept evidence with passing tests."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".test-evidence.json").write_text(json.dumps({
            "timestamp": "2026-04-17T10:05:00Z",
            "passed": 100,
            "failed": 0,
            "total": 100,
        }))

        result = run_hook("test-status", tmp_path, git_output="")

        assert result.returncode == 0, result.stdout
        assert "current" in result.stdout
        assert "no session marker" in result.stdout

    def test_metadata_commits_do_not_invalidate(self, tmp_path: Path):
        """The whole point: metadata-only commits between test run and Critic
        must not cause staleness. With session-timestamp checking, only the
        timestamp matters — git state changes are irrelevant."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        session_start = "2026-04-17T10:00:00Z"
        evidence_time = "2026-04-17T10:05:00Z"
        (prawduct / ".session-start").write_text(session_start)
        (prawduct / ".test-evidence.json").write_text(json.dumps({
            "timestamp": evidence_time,
            "passed": 50,
            "failed": 0,
            "total": 50,
        }))

        # Dirty tree with metadata changes — should still be current
        result = run_hook(
            "test-status",
            tmp_path,
            git_output=(
                " M .prawduct/backlog.md\n"
                " M .prawduct/.critic-findings.json\n"
                " M .claude/settings.json\n"
            ),
        )

        assert result.returncode == 0, result.stdout
        assert "current" in result.stdout

    def test_single_line_output(self, tmp_path: Path):
        """test-status outputs exactly one status line."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        result = run_hook("test-status", tmp_path, git_output="")

        lines = result.stdout.strip().splitlines()
        assert len(lines) == 1
        assert lines[0].startswith("stale")


# =============================================================================
# Content validation
# =============================================================================


class TestCriticContentValidation:
    def _setup_critic_scenario(self, tmp_path: Path, findings_content: str) -> Path:
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
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
                "files_reviewed": ["src/app.py"],
                "findings": [
                    {"goal": "Nothing Is Unintended", "severity": "warning", "summary": "Missing edge case test"}
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
                "files_reviewed": ["src/app.py"],
                "findings": [],
                "summary": "No issues found. Changes are ready to proceed.",
            }),
        )
        result = run_hook("stop", tmp_path, git_output=" M src/app.py")
        assert result.returncode == 0

    def test_rejects_missing_files_reviewed(self, tmp_path: Path):
        self._setup_critic_scenario(
            tmp_path,
            json.dumps({
                "findings": [],
                "summary": "No issues found.",
            }),
        )
        result = run_hook("stop", tmp_path, git_output=" M src/app.py")
        assert result.returncode == 2

    def test_rejects_empty_files_reviewed(self, tmp_path: Path):
        self._setup_critic_scenario(
            tmp_path,
            json.dumps({
                "files_reviewed": [],
                "findings": [],
                "summary": "No issues found.",
            }),
        )
        result = run_hook("stop", tmp_path, git_output=" M src/app.py")
        assert result.returncode == 2

    def test_rejects_finding_without_goal(self, tmp_path: Path):
        self._setup_critic_scenario(
            tmp_path,
            json.dumps({
                "files_reviewed": ["src/app.py"],
                "findings": [
                    {"severity": "warning", "summary": "Missing test"}
                ],
                "summary": "1 warning.",
            }),
        )
        result = run_hook("stop", tmp_path, git_output=" M src/app.py")
        assert result.returncode == 2


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


class TestLearningsSizeWarning:
    """Tests for oversized learnings.md warning on clear."""

    def test_warns_when_learnings_exceeds_threshold(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        # Write a learnings file larger than 8KB
        (prawduct / "learnings.md").write_text("# Learnings\n" + "x" * 9000)

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert "learnings.md" in result.stdout
        assert "pruning" in result.stdout.lower()

    def test_no_warning_for_small_learnings(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "learnings.md").write_text("# Learnings\nSmall file.")

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert "learnings" not in result.stdout.lower()

    def test_no_warning_when_learnings_missing(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert "learnings" not in result.stdout.lower()


class TestProjectStateSizeWarning:
    """Tests for oversized project-state.yaml warning on clear."""

    def test_warns_when_project_state_exceeds_threshold(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        # Write a project-state file larger than 40KB
        (prawduct / "project-state.yaml").write_text("# State\n" + "x" * 41000)

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert "project-state.yaml" in result.stdout
        assert "compacting" in result.stdout.lower()

    def test_no_warning_for_small_project_state(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text("# State\ncurrent_phase: building")

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert "project-state" not in result.stdout.lower()

    def test_no_warning_when_project_state_missing(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert "project-state" not in result.stdout.lower()


class TestProjectPreferencesWarning:
    """Tests for missing project-preferences.md warning on clear."""

    def test_warns_when_code_exists_but_no_preferences(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "artifacts").mkdir()
        # Create a source file so it looks like a real project
        (tmp_path / "main.py").write_text("print('hello')")

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert "project-preferences.md" in result.stdout
        assert "CRITICAL" in result.stdout

    def test_no_warning_when_preferences_filled(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        artifacts = prawduct / "artifacts"
        artifacts.mkdir()
        (artifacts / "project-preferences.md").write_text(
            "# Project Preferences\n\n## Language & Runtime\n\n- **Language**: Python\n"
        )
        (tmp_path / "main.py").write_text("print('hello')")

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert "project-preferences" not in result.stdout.lower()

    def test_warns_when_template_unfilled(self, tmp_path: Path):
        """Unfilled template (empty Language field) + source code → CRITICAL warning."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        artifacts = prawduct / "artifacts"
        artifacts.mkdir()
        # Write the unfilled template (fields have nothing after the colon)
        (artifacts / "project-preferences.md").write_text(
            "# Project Preferences\n\n## Language & Runtime\n\n- **Language**:\n- **Version**:\n"
        )
        (tmp_path / "main.py").write_text("print('hello')")

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert "project-preferences.md" in result.stdout
        assert "CRITICAL" in result.stdout

    def test_no_warning_for_new_project_without_code(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "artifacts").mkdir()

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert "project-preferences" not in result.stdout.lower()


class TestSyncTrigger:
    """Test that clear triggers sync (best-effort)."""

    def test_clear_with_no_manifest_succeeds(self, tmp_path: Path):
        """Clear should succeed even without a manifest (sync is best-effort)."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        result = run_hook("clear", tmp_path)
        assert result.returncode == 0
        assert (prawduct / ".session-start").exists()


class TestSessionEndCommandRemoved:
    """session-end was removed — verify it's no longer accepted."""

    def test_session_end_rejected(self, tmp_path: Path):
        """session-end should be rejected as an unknown command."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        result = run_hook("session-end", tmp_path)
        assert result.returncode == 1
        assert "Usage" in result.stderr


# =============================================================================
# Staleness scan
# =============================================================================
# =============================================================================


class TestStalenessNoState:
    """Staleness scan with no project state should produce no findings."""

    def test_no_project_state_no_findings(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert "Stale:" not in result.stdout


class TestComputedTestCount:
    """Test count is now computed and shown in briefing (not tracked in YAML)."""

    def test_briefing_shows_computed_test_count(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "TestApp"\n\n'
            "build_state:\n  source_root: null\n"
        )
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_app.py").write_text(
            "\n".join(f"def test_case_{i}():\n    pass\n" for i in range(8))
        )

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert "Tests: ~8" in result.stdout

    def test_briefing_no_count_when_no_tests(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "TestApp"\n\n'
            "build_state:\n  source_root: null\n"
        )

        result = run_hook("clear", tmp_path)

        assert "Tests:" not in result.stdout


class TestStalenessArchitecture:
    """Architecture staleness detection."""

    def test_detects_unmentioned_directory(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "TestApp"\n\n'
            'build_state:\n  source_root: "src"\n  test_tracking:\n    test_count: 0\n'
        )
        (artifacts / "architecture.md").write_text("# Architecture\n\n## api\nThe API layer.\n\n## models\nData models.\n")

        # Create src/ with api, models (mentioned) and workers (not mentioned)
        src = tmp_path / "src"
        (src / "api").mkdir(parents=True)
        (src / "models").mkdir()
        (src / "workers").mkdir()

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert "Stale:" in result.stdout
        assert "workers" in result.stdout
        assert "architecture" in result.stdout

    def test_no_finding_when_all_dirs_mentioned(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "TestApp"\n\n'
            'build_state:\n  source_root: "src"\n  test_tracking:\n    test_count: 0\n'
        )
        (artifacts / "architecture.md").write_text("# Architecture\n\napi layer, models layer\n")

        src = tmp_path / "src"
        (src / "api").mkdir(parents=True)
        (src / "models").mkdir()

        result = run_hook("clear", tmp_path)

        assert "architecture" not in result.stdout

    def test_no_finding_when_no_architecture_artifact(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "TestApp"\n\n'
            'build_state:\n  source_root: "src"\n  test_tracking:\n    test_count: 0\n'
        )
        src = tmp_path / "src"
        (src / "workers").mkdir(parents=True)

        result = run_hook("clear", tmp_path)

        assert "architecture" not in result.stdout


class TestStalenessDependencies:
    """Dependency staleness detection."""

    def test_detects_missing_deps_in_requirements(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "TestApp"\n\nbuild_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n'
        )
        (artifacts / "dependency-manifest.md").write_text(
            "# Dependencies\n\n## flask\nWeb framework.\n\n## pytest\nTesting.\n"
        )
        (tmp_path / "requirements.txt").write_text("flask==2.0\npytest>=7.0\nredis>=4.0\ncelery>=5.0\n")

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert "Stale:" in result.stdout
        assert "dependencies" in result.stdout
        assert "redis" in result.stdout

    def test_detects_missing_deps_in_package_json(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "TestApp"\n\nbuild_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n'
        )
        (artifacts / "dependency-manifest.md").write_text(
            "# Dependencies\n\n## react\nUI framework.\n"
        )
        (tmp_path / "package.json").write_text(json.dumps({
            "dependencies": {"react": "^18.0", "axios": "^1.0"},
            "devDependencies": {"jest": "^29.0"},
        }))

        result = run_hook("clear", tmp_path)

        assert "dependencies" in result.stdout
        assert "axios" in result.stdout

    def test_no_finding_when_all_deps_in_manifest(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "TestApp"\n\nbuild_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n'
        )
        (artifacts / "dependency-manifest.md").write_text(
            "# Dependencies\n\n## flask\nWeb framework.\n\n## pytest\nTesting.\n"
        )
        (tmp_path / "requirements.txt").write_text("flask==2.0\npytest>=7.0\n")

        result = run_hook("clear", tmp_path)

        assert "dependencies" not in result.stdout

    def test_no_finding_when_no_manifest(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "TestApp"\n\nbuild_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n'
        )
        (tmp_path / "requirements.txt").write_text("flask==2.0\n")

        result = run_hook("clear", tmp_path)

        assert "dependencies" not in result.stdout


class TestStalenessGraceful:
    """Staleness scan handles missing/broken files gracefully."""

    def test_missing_project_state_no_crash(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        result = run_hook("clear", tmp_path)
        assert result.returncode == 0

    def test_empty_project_state_no_crash(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text("")

        result = run_hook("clear", tmp_path)
        assert result.returncode == 0

    def test_corrupt_package_json_no_crash(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "TestApp"\n\nbuild_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n'
        )
        (artifacts / "dependency-manifest.md").write_text("# Dependencies\n")
        (tmp_path / "package.json").write_text("{not valid json")

        result = run_hook("clear", tmp_path)
        assert result.returncode == 0


class TestStalenessPerformance:
    """Staleness scan completes within timeout."""

    def test_scan_completes_within_5_seconds(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "TestApp"\n\n'
            'build_state:\n  source_root: "src"\n  test_tracking:\n    test_count: 100\n'
        )
        (artifacts / "architecture.md").write_text("# Arch\n")
        (artifacts / "dependency-manifest.md").write_text("# Deps\n")
        (tmp_path / "requirements.txt").write_text("flask==2.0\n")
        src = tmp_path / "src"
        src.mkdir()

        start = time.time()
        result = run_hook("clear", tmp_path)
        elapsed = time.time() - start

        assert result.returncode == 0
        assert elapsed < 5.0


class TestStalenessBuildPlan:
    """Staleness scan detects stale build plans."""

    def test_staleness_detects_stale_build_plan_file(self, tmp_path: Path):
        """build-plan.md exists but no active work -> warning."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n"
        )
        (artifacts / "build-plan.md").write_text("# Build Plan\n## Chunk 1\nDone.\n")

        result = run_hook("clear", tmp_path)
        assert "build plan" in result.stdout.lower()
        assert "no active work" in result.stdout

    def test_staleness_detects_all_chunks_complete(self, tmp_path: Path):
        """build-plan.md with all Status items checked -> stale."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n"
        )
        (artifacts / "build-plan.md").write_text(
            "# Build Plan — My Feature (2026-03-28)\n\n"
            "## Status\n\n"
            "- [x] Chunk 1: Setup — done\n"
            "- [x] Chunk 2: Implement — done\n"
            "Context: All complete.\n"
        )

        result = run_hook("clear", tmp_path)
        assert "build plan" in result.stdout.lower()
        assert "all chunks complete" in result.stdout

    def test_staleness_no_warning_with_active_status(self, tmp_path: Path):
        """build-plan.md with unchecked Status items -> not stale."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n"
        )
        (artifacts / "build-plan.md").write_text(
            "# Build Plan — My Feature (2026-03-28)\n\n"
            "## Status\n\n"
            "- [x] Chunk 1: Setup — done\n"
            "- [ ] Chunk 2: Implement\n"
            "Context: Chunk 1 done, starting chunk 2.\n"
        )

        result = run_hook("clear", tmp_path)
        # Should not have any staleness warning about build plan
        stale_lines = [l for l in result.stdout.splitlines() if "stale" in l.lower() or "build plan" in l.lower()]
        assert not any("no active work" in l for l in stale_lines)
        assert not any("all chunks complete" in l for l in stale_lines)

    def test_staleness_no_warning_with_active_wip_fallback(self, tmp_path: Path):
        """build-plan.md without Status section but active WIP -> not stale (backward compat)."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n\n"
            "work_in_progress:\n  description: building feature X\n  size: medium\n"
        )
        (artifacts / "build-plan.md").write_text("# Build Plan\n## Chunk 1\nIn progress.\n")

        result = run_hook("clear", tmp_path)
        assert "no active work" not in result.stdout

    def test_staleness_detects_completed_plan_in_state(self, tmp_path: Path):
        """Strategy set but no active chunks -> warning about completed plan."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n\n"
            "build_plan:\n  strategy: feature-first\n  chunks: []\n  current_chunk: null\n"
        )

        result = run_hook("clear", tmp_path)
        assert "completed build plan" in result.stdout.lower()

    def test_staleness_no_warning_for_null_strategy(self, tmp_path: Path):
        """Template defaults (strategy: null, chunks: []) -> no warning."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n\n"
            "build_plan:\n  strategy: null\n  chunks: []\n  current_chunk: null\n"
        )

        result = run_hook("clear", tmp_path)
        assert "build plan" not in result.stdout.lower()


# =============================================================================
# Chunk 2: Session Briefing
# =============================================================================


# =============================================================================


class TestSessionBriefing:
    """Session briefing is printed to stdout during clear."""

    def test_briefing_printed_to_stdout(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "work_in_progress:\n  description: null\n  size: null\n  type: null\n"
            "\nbuild_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert "== SESSION BRIEFING ==" in result.stdout

    def test_briefing_contains_project_name(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "Discodon"\n\n'
            "work_in_progress:\n  description: null\n  size: null\n  type: null\n"
            "\nbuild_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )

        result = run_hook("clear", tmp_path)

        assert "Project: Discodon" in result.stdout

    def test_briefing_shows_upgrade_info(self, tmp_path: Path):
        """When upgrade_info is passed, briefing shows framework upgrade line near top."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "work_in_progress:\n  description: null\n  size: null\n  type: null\n"
            "\nbuild_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )

        # Import product-hook (no .py extension) via importlib with explicit loader
        import importlib.util
        import importlib.machinery
        loader = importlib.machinery.SourceFileLoader("product_hook", str(HOOK_PATH))
        spec = importlib.util.spec_from_loader("product_hook", loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        upgrade = {"previous_version": "1.0.0", "new_version": "1.1.0"}
        briefing = mod.assemble_session_briefing(tmp_path, [], upgrade_info=upgrade)
        assert "Framework: upgraded v1.0.0 \u2192 v1.1.0 this session" in briefing
        # Should appear before project line
        lines = briefing.splitlines()
        fw_idx = next(i for i, l in enumerate(lines) if "Framework:" in l)
        proj_idx = next(i for i, l in enumerate(lines) if "Project:" in l)
        assert fw_idx < proj_idx

    def test_briefing_no_upgrade_without_info(self, tmp_path: Path):
        """When no upgrade_info, briefing has no framework upgrade line."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "work_in_progress:\n  description: null\n  size: null\n  type: null\n"
            "\nbuild_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )

        import importlib.util
        import importlib.machinery
        loader = importlib.machinery.SourceFileLoader("product_hook", str(HOOK_PATH))
        spec = importlib.util.spec_from_loader("product_hook", loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        briefing = mod.assemble_session_briefing(tmp_path, [])
        assert "Framework:" not in briefing

    def test_briefing_shows_advisories(self, tmp_path: Path):
        """Advisories appear in session briefing when template drift detected."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "work_in_progress:\n  description: null\n  size: null\n  type: null\n"
            "\nbuild_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )

        import importlib.util
        import importlib.machinery
        loader = importlib.machinery.SourceFileLoader("product_hook", str(HOOK_PATH))
        spec = importlib.util.spec_from_loader("product_hook", loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        advisories = [
            {
                "type": "template_drift",
                "file": ".prawduct/artifacts/project-preferences.md",
                "template": "templates/project-preferences.md",
                "message": "project-preferences.md template has new content — run /janitor scope=templates to review",
            }
        ]
        briefing = mod.assemble_session_briefing(tmp_path, [], advisories=advisories)
        assert "Advisories:" in briefing
        assert "project-preferences.md" in briefing
        assert "/janitor" in briefing

    def test_briefing_no_advisories_when_empty(self, tmp_path: Path):
        """No advisory section when list is empty."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "work_in_progress:\n  description: null\n  size: null\n  type: null\n"
            "\nbuild_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )

        import importlib.util
        import importlib.machinery
        loader = importlib.machinery.SourceFileLoader("product_hook", str(HOOK_PATH))
        spec = importlib.util.spec_from_loader("product_hook", loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        briefing = mod.assemble_session_briefing(tmp_path, [], advisories=[])
        assert "Advisories:" not in briefing

    def test_briefing_shows_work_in_progress(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            'work_in_progress:\n  description: "implementing user auth"\n  size: "medium"\n  type: "feature"\n'
            "\nbuild_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )

        result = run_hook("clear", tmp_path)

        assert "implementing user auth" in result.stdout
        assert "medium" in result.stdout
        assert "feature" in result.stdout

    def test_briefing_shows_no_active_work(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "work_in_progress:\n  description: null\n  size: null\n  type: null\n"
            "\nbuild_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )

        result = run_hook("clear", tmp_path)

        assert "none active" in result.stdout

    def test_briefing_includes_staleness_warnings(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        artifacts = prawduct / "artifacts"
        artifacts.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            'build_state:\n  source_root: "src"\n'
        )
        # Architecture mentions "api" but not "utils"
        (artifacts / "architecture.md").write_text("# Architecture\n\n## api module\n")
        src = tmp_path / "src"
        src.mkdir()
        (src / "api").mkdir()
        (src / "utils").mkdir()  # Not mentioned in architecture

        result = run_hook("clear", tmp_path)

        assert "Stale:" in result.stdout
        assert "utils" in result.stdout

    def test_briefing_shows_computed_count_with_tests(self, tmp_path: Path):
        """Briefing shows computed test count when tests exist."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "build_state:\n  source_root: null\n"
        )
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_app.py").write_text(
            "\n".join(f"def test_case_{i}():\n    pass\n" for i in range(20))
        )

        result = run_hook("clear", tmp_path)

        assert "Tests: ~20" in result.stdout

    def test_briefing_shows_current_chunk(self, tmp_path: Path):
        """Session briefing shows current_chunk from WIP."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            'work_in_progress:\n  description: "Building auth"\n  size: "large"\n'
            '  type: "feature"\n  current_chunk: "chunk 5 of 12: OAuth integration"\n'
        )

        result = run_hook("clear", tmp_path)

        assert "Resume:" in result.stdout
        assert "chunk 5 of 12" in result.stdout

    # --- Build plan Status as work context source ---

    def test_briefing_uses_build_plan_status(self, tmp_path: Path):
        """Session briefing reads description/size/type from build plan."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n'
        )
        (artifacts / "build-plan.md").write_text(
            "# Build Plan — Add User Auth (2026-03-28)\n\n"
            "**Size**: Medium | **Type**: Feature | **Governance**: Critic per chunk\n\n"
            "## Status\n\n"
            "- [x] Chunk 1: Setup — done\n"
            "- [ ] Chunk 2: OAuth integration\n"
            "- [ ] Chunk 3: Tests\n"
            "Context: Chunk 1 done. Next: implement OAuth flow.\n"
        )

        result = run_hook("clear", tmp_path)

        assert "Add User Auth" in result.stdout
        assert "Medium" in result.stdout
        assert "Feature" in result.stdout
        assert "Resume:" in result.stdout
        assert "Chunk 2: OAuth integration" in result.stdout
        assert "Context:" in result.stdout
        assert "Chunk 1 done" in result.stdout

    def test_briefing_build_plan_overrides_wip(self, tmp_path: Path):
        """Build plan Status takes priority over project-state.yaml WIP."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            'work_in_progress:\n  description: "Old stale WIP"\n'
        )
        (artifacts / "build-plan.md").write_text(
            "# Build Plan — New Feature (2026-03-28)\n\n"
            "## Status\n\n"
            "- [ ] Chunk 1: Setup\n"
            "Context: Starting fresh.\n"
        )

        result = run_hook("clear", tmp_path)

        assert "New Feature" in result.stdout
        assert "Old stale WIP" not in result.stdout

    def test_briefing_falls_back_to_wip_without_status(self, tmp_path: Path):
        """Build plan without Status section falls back to WIP."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            'work_in_progress:\n  description: "Legacy WIP"\n  size: "small"\n'
        )
        (artifacts / "build-plan.md").write_text(
            "# Build Plan\n\n## Chunks\n\n### Chunk 1\nDo things.\n"
        )

        result = run_hook("clear", tmp_path)

        # Build plan has no title after "Build Plan", so falls back to WIP
        assert "Legacy WIP" in result.stdout

    def test_briefing_includes_learnings(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "build_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )
        (prawduct / "learnings.md").write_text(
            "# Learnings\n\n"
            "- When adding API endpoints, always update TypeScript types first\n"
            "- Never swallow Redis connection errors\n"
            "- Always run integration tests after IPC changes\n"
        )

        result = run_hook("clear", tmp_path)

        assert "Learnings" in result.stdout
        assert "3 rules" in result.stdout

    def test_briefing_shows_topic_index(self, tmp_path: Path):
        """Session briefing shows section headers as topic index."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "build_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )
        (prawduct / "learnings.md").write_text(
            "# Learnings\n\n"
            "## Testing\n"
            "- When mocking, match sync/async\n"
            "- Always use OS-assigned ports\n"
            "\n"
            "## Architecture\n"
            "- Never hardcode container names\n"
        )

        result = run_hook("clear", tmp_path)

        assert "3 rules" in result.stdout
        assert "Testing" in result.stdout
        assert "Architecture" in result.stdout
        assert "|" in result.stdout  # Topics joined with pipe

    def test_briefing_flat_learnings_no_headers(self, tmp_path: Path):
        """Falls back gracefully when learnings have no section headers."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "build_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )
        (prawduct / "learnings.md").write_text(
            "# Learnings\n\n"
            "- When doing A, do B\n"
            "- When doing C, do D\n"
            "- Always do E\n"
        )

        result = run_hook("clear", tmp_path)

        assert "3 rules" in result.stdout
        assert "read .prawduct/learnings.md" in result.stdout

    def test_briefing_excludes_resolved_topics(self, tmp_path: Path):
        """Topics with (RESOLVED) in the header are excluded from index."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "build_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )
        (prawduct / "learnings.md").write_text(
            "# Learnings\n\n"
            "## Active Topic\n"
            "- Rule one\n"
            "\n"
            "## Old Bug (RESOLVED)\n"
            "- This was fixed\n"
        )

        result = run_hook("clear", tmp_path)

        assert "Active Topic" in result.stdout
        assert "RESOLVED" not in result.stdout

    def test_briefing_no_update_nudge_for_test_count(self, tmp_path: Path):
        """Briefing should not ask to manually update test_count (it's computed now)."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "build_state:\n  source_root: null\n"
        )

        result = run_hook("clear", tmp_path)

        assert "if you add or remove tests" not in result.stdout
        assert "update this before session end" not in result.stdout

    def test_briefing_shows_critic_duration(self, tmp_path: Path):
        """Briefing should show last Critic review duration."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "build_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )
        (prawduct / ".critic-findings.json").write_text(json.dumps({
            "timestamp": "2026-03-19T10:00:00Z",
            "duration_seconds": 195,
            "files_reviewed": ["src/app.py"],
            "findings": [],
            "summary": "No issues found."
        }))

        result = run_hook("clear", tmp_path)

        assert "3m15s" in result.stdout
        assert "grumpier" in result.stdout.lower()

    def test_briefing_no_critic_duration_when_missing(self, tmp_path: Path):
        """Briefing should not show duration if findings have no duration_seconds."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "build_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )
        (prawduct / ".critic-findings.json").write_text(json.dumps({
            "timestamp": "2026-03-19T10:00:00Z",
            "files_reviewed": ["src/app.py"],
            "findings": [],
            "summary": "No issues found."
        }))

        result = run_hook("clear", tmp_path)

        assert "Last Critic review" not in result.stdout

    def test_briefing_excludes_redundant_reminders(self, tmp_path: Path):
        """Briefing should not include reminders that are already in CLAUDE.md Critical Rules."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "build_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )

        result = run_hook("clear", tmp_path)

        assert "Reminders:" not in result.stdout

    def test_briefing_under_400_tokens(self, tmp_path: Path):
        """Session briefing should be under 400 tokens even with all sections populated."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "LargeApp"\n\n'
            'work_in_progress:\n  description: "implementing feature X"\n  size: "medium"\n  type: "feature"\n'
            "\nbuild_state:\n  source_root: \"src\"\n  test_tracking:\n    test_count: 500\n"
        )
        (prawduct / "learnings.md").write_text(
            "# Learnings\n\n"
            + "\n".join(f"- When doing thing_{i}, always check consequence_{i}" for i in range(20))
        )
        # Create test files that diverge from count
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_big.py").write_text(
            "\n".join(f"def test_case_{i}():\n    pass\n" for i in range(100))
        )
        # Add backlog with items
        (prawduct / "backlog.md").write_text(
            "# Backlog\n\n"
            "- **Add caching** — performance optimization (builder)\n"
            "- **Fix logging** — structured logging needed (critic)\n"
        )

        result = run_hook("clear", tmp_path)

        # Extract just the briefing
        lines = result.stdout.split("\n")
        briefing_start = None
        for i, line in enumerate(lines):
            if "== SESSION BRIEFING ==" in line:
                briefing_start = i
                break

        assert briefing_start is not None
        briefing_text = "\n".join(lines[briefing_start:])
        # Rough token estimate: words * 1.3
        word_count = len(briefing_text.split())
        estimated_tokens = int(word_count * 1.3)
        assert estimated_tokens < 400, f"Briefing ~{estimated_tokens} tokens, exceeds 400: {briefing_text}"

    def test_briefing_shows_backlog_count_and_items(self, tmp_path: Path):
        """Session briefing includes backlog count AND items inline."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n"
        )
        (prawduct / "backlog.md").write_text(
            "# Backlog\n\n"
            "- **Add caching** — performance optimization (builder)\n"
            "- **Support dark mode** — UI enhancement (critic)\n"
        )

        result = run_hook("clear", tmp_path)
        assert "Backlog: 2 pending items" in result.stdout
        assert "Add caching" in result.stdout
        assert "Support dark mode" in result.stdout

    def test_briefing_no_backlog_when_empty(self, tmp_path: Path):
        """No backlog line when file exists but has no items."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n"
        )
        (prawduct / "backlog.md").write_text(
            "# Backlog\n\n<!-- No items yet -->\n"
        )

        result = run_hook("clear", tmp_path)
        assert "Backlog:" not in result.stdout

    def test_briefing_ignores_code_block_items(self, tmp_path: Path):
        """Items inside code blocks (cleanup markers) are not counted."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n"
        )
        (prawduct / "backlog.md").write_text(
            "# Backlog\n\n"
            "- **Real item** — counts (builder)\n"
            "```yaml\n"
            "- fake item inside code block\n"
            "- another fake\n"
            "```\n"
        )

        result = run_hook("clear", tmp_path)
        assert "Backlog: 1 pending" in result.stdout

    def test_briefing_excludes_resolved_section(self, tmp_path: Path):
        """Items in Resolved/Done sections are not counted."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n"
        )
        (prawduct / "backlog.md").write_text(
            "# Backlog\n\n"
            "- **Active item** — needs doing (builder)\n\n"
            "## Resolved\n\n"
            "- Old task A\n"
            "- Old task B\n"
        )

        result = run_hook("clear", tmp_path)
        assert "Backlog: 1 pending" in result.stdout

    def test_briefing_truncates_long_backlog_items(self, tmp_path: Path):
        """Long backlog items are truncated to keep briefing concise."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n"
        )
        long_item = "x" * 150
        (prawduct / "backlog.md").write_text(
            f"# Backlog\n\n- {long_item}\n"
        )

        result = run_hook("clear", tmp_path)
        assert "..." in result.stdout
        # Should be truncated, not the full 150 chars
        assert long_item not in result.stdout

    def test_briefing_caps_backlog_at_five(self, tmp_path: Path):
        """Only first 5 backlog items shown, rest summarized."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n"
        )
        items = "\n".join(f"- Item {i} (builder)" for i in range(7))
        (prawduct / "backlog.md").write_text(
            f"# Backlog\n\n{items}\n"
        )

        result = run_hook("clear", tmp_path)
        assert "Backlog: 7 pending items" in result.stdout
        assert "Item 0" in result.stdout
        assert "Item 4" in result.stdout
        assert "Item 5" not in result.stdout
        assert "... and 2 more" in result.stdout

    def test_briefing_excludes_nested_and_strikethrough(self, tmp_path: Path):
        """Nested sub-items and strikethrough items are not counted."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n"
        )
        (prawduct / "backlog.md").write_text(
            "# Backlog\n\n"
            "- **Real item** — counts (builder)\n"
            "  - Nested sub-item (should not count)\n"
            "- ~~Completed item~~ (should not count)\n"
            "- **Another real** — also counts (critic)\n"
        )

        result = run_hook("clear", tmp_path)
        assert "Backlog: 2 pending" in result.stdout


# =============================================================================


class TestSubagentBriefing:
    """Subagent briefing file generation."""

    def test_creates_briefing_file(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "build_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )

        run_hook("clear", tmp_path)

        assert (prawduct / ".subagent-briefing.md").is_file()

    def test_briefing_contains_project_name(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "Discodon"\n\n'
            "build_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )

        run_hook("clear", tmp_path)

        content = (prawduct / ".subagent-briefing.md").read_text()
        assert "Discodon" in content

    def test_briefing_contains_governance_rules(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "build_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )

        run_hook("clear", tmp_path)

        content = (prawduct / ".subagent-briefing.md").read_text()
        assert "Governance Rules" in content
        assert "tests alongside code" in content.lower()
        assert "never weaken" in content.lower()
        assert "broad exceptions" in content.lower()

    def test_briefing_includes_project_preferences(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "build_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )
        (artifacts / "project-preferences.md").write_text(
            "# Project Preferences\n\n## Language\n\n- **Language**: Python 3.12\n- **Testing**: pytest\n"
        )

        run_hook("clear", tmp_path)

        content = (prawduct / ".subagent-briefing.md").read_text()
        assert "Project Preferences" in content
        assert "Python 3.12" in content

    def test_briefing_excludes_unfilled_preferences(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "build_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )
        (artifacts / "project-preferences.md").write_text(
            "# Project Preferences\n\n- **Language**:\n- **Testing**:\n"
        )

        run_hook("clear", tmp_path)

        content = (prawduct / ".subagent-briefing.md").read_text()
        assert "Project Preferences" not in content

    def test_briefing_includes_learnings(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "build_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )
        (prawduct / "learnings.md").write_text(
            "# Learnings\n\n- When adding API endpoints, update types first\n"
        )

        run_hook("clear", tmp_path)

        content = (prawduct / ".subagent-briefing.md").read_text()
        assert "Active Learnings" in content
        assert "API endpoints" in content

    def test_briefing_handles_no_learnings(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "build_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )

        run_hook("clear", tmp_path)

        content = (prawduct / ".subagent-briefing.md").read_text()
        assert "Active Learnings" not in content

    def test_briefing_handles_no_prawduct_dir(self, tmp_path: Path):
        """No .prawduct dir = no briefing file created, no crash."""
        result = run_hook("clear", tmp_path)
        assert result.returncode == 0
        assert not (tmp_path / ".prawduct" / ".subagent-briefing.md").exists()


# =============================================================================
# Chunk 3: Compliance Canary — Code Without Tests
# =============================================================================


# =============================================================================


class TestCanaryCodeNoTests:
    """Detects source file changes with no test file changes."""

    def test_source_changed_no_tests_flags(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert "CANARY" in result.stderr
        assert "source file" in result.stderr
        assert "no test files" in result.stderr.lower()

    def test_source_and_test_changed_no_flag(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        result = run_hook("stop", tmp_path, git_output=" M src/app.py\n M tests/test_app.py")

        assert "source file" not in result.stderr.lower()

    def test_only_test_files_no_flag(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        result = run_hook("stop", tmp_path, git_output=" M tests/test_app.py")

        assert "CANARY" not in result.stderr

    def test_only_prawduct_files_no_flag(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        result = run_hook("stop", tmp_path, git_output=" M .prawduct/learnings.md")

        assert "CANARY" not in result.stderr

    def test_no_changes_no_flag(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        result = run_hook("stop", tmp_path, git_output="")

        assert "CANARY" not in result.stderr

    def test_non_code_file_no_flag(self, tmp_path: Path):
        """Config/doc files changed without tests should not flag."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        result = run_hook("stop", tmp_path, git_output=" M README.md\n M config.yaml")

        assert "CANARY" not in result.stderr

    def test_preexisting_changes_not_flagged(self, tmp_path: Path):
        """Files in baseline should not trigger canary."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text(" M src/app.py")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        # Same file as baseline — no new changes
        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert "CANARY" not in result.stderr


# =============================================================================
# Chunk 3: Compliance Canary — Dependency Without Rationale
# =============================================================================


# =============================================================================


class TestCanaryDepNoRationale:
    """Detects dependency file changes without manifest update."""

    def test_requirements_changed_no_manifest_flags(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "dependency-manifest.md").write_text("# Dependencies\n")
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        result = run_hook("stop", tmp_path, git_output=" M requirements.txt")

        assert "CANARY" in result.stderr
        assert "Dependency" in result.stderr or "dependency" in result.stderr
        assert "requirements.txt" in result.stderr

    def test_package_json_changed_no_manifest_flags(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "dependency-manifest.md").write_text("# Dependencies\n")
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        result = run_hook("stop", tmp_path, git_output=" M package.json")

        assert "CANARY" in result.stderr
        assert "package.json" in result.stderr

    def test_dep_changed_with_manifest_update_no_flag(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "dependency-manifest.md").write_text("# Dependencies\n")
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        result = run_hook(
            "stop", tmp_path,
            git_output=" M requirements.txt\n M .prawduct/artifacts/dependency-manifest.md"
        )

        assert "Dependency" not in result.stderr and "dependency" not in result.stderr

    def test_no_dep_changes_no_flag(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "dependency-manifest.md").write_text("# Dependencies\n")
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        # Might have code-no-tests canary, but not dep canary
        assert "dependency-manifest" not in result.stderr.lower()

    def test_no_manifest_file_no_flag(self, tmp_path: Path):
        """If there's no dependency manifest, don't flag dep changes."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        result = run_hook("stop", tmp_path, git_output=" M requirements.txt")

        assert "dependency-manifest" not in result.stderr.lower()


# =============================================================================
# Chunk 3: Compliance Canary — Broad Exception Handling
# =============================================================================


# =============================================================================


class TestCanaryBroadException:
    """Detects broad exception handling in changed source files."""

    def test_except_exception_flags(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        # Create actual source file with broad exception
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text(
            "def handler():\n    try:\n        do_thing()\n    except Exception:\n        pass\n"
        )

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert "CANARY" in result.stderr
        assert "Broad exception" in result.stderr or "exception" in result.stderr.lower()
        assert "src/app.py" in result.stderr

    def test_except_exception_as_e_flags(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text(
            "def handler():\n    try:\n        do_thing()\n    except Exception as e:\n        pass\n"
        )

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert "exception" in result.stderr.lower()

    def test_except_base_exception_flags(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text(
            "def handler():\n    try:\n        do_thing()\n    except BaseException:\n        pass\n"
        )

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert "exception" in result.stderr.lower()

    def test_specific_exception_no_flag(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text(
            "def handler():\n    try:\n        do_thing()\n    except ValueError:\n        pass\n"
        )

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert "Broad exception" not in result.stderr

    def test_js_empty_catch_flagged(self, tmp_path: Path):
        """JS empty catch blocks are now flagged."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        src = tmp_path / "src"
        src.mkdir()
        (src / "app.js").write_text("try { } catch(e) { }\n")

        result = run_hook("stop", tmp_path, git_output=" M src/app.js")

        assert "Broad exception" in result.stderr

    def test_unsupported_language_no_flag(self, tmp_path: Path):
        """Languages without broad exception patterns don't get flagged."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        src = tmp_path / "src"
        src.mkdir()
        (src / "app.rb").write_text("begin; rescue => e; end\n")

        result = run_hook("stop", tmp_path, git_output=" M src/app.rb")

        assert "Broad exception" not in result.stderr

    def test_file_not_on_disk_no_crash(self, tmp_path: Path):
        """Changed file listed in git but not on disk (deleted) should not crash."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        result = run_hook("stop", tmp_path, git_output=" D src/app.py")

        assert result.returncode == 0


# =============================================================================
# Chunk 3: Canary Integration
# =============================================================================


# =============================================================================


class TestCanaryIntegration:
    """Canary works alongside existing gates without interference."""

    def test_canary_on_stderr_not_stdout(self, tmp_path: Path):
        """Canary findings go to stderr (visible to model when blocked, verbose otherwise)."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert "CANARY" in result.stderr
        assert "CANARY" not in result.stdout

    def test_canary_does_not_affect_exit_code(self, tmp_path: Path):
        """Canary findings are informational — don't block session end."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        # Source changed, no tests — canary fires but shouldn't block
        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert "CANARY" in result.stderr
        assert "CANARY" not in result.stdout
        assert result.returncode == 0  # Not blocked

    def test_canary_with_reflection_gate(self, tmp_path: Path):
        """Canary fires alongside reflection gate (build plan present)."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        artifacts = prawduct / "artifacts"
        artifacts.mkdir()
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-git-baseline").write_text("")
        # No .session-reflected → reflection gate fires

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        # Both canary and reflection gate should appear
        assert "CANARY" in result.stderr
        assert "REFLECTION" in result.stderr
        assert result.returncode == 2

    def test_canary_with_critic_gate(self, tmp_path: Path):
        """Canary fires alongside Critic gate."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")
        (prawduct / ".session-git-baseline").write_text("")
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert "CANARY" in result.stderr
        assert "CRITIC" in result.stderr
        assert result.returncode == 2

    def test_multiple_canaries_fire_together(self, tmp_path: Path):
        """Multiple canary findings can appear at once."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "dependency-manifest.md").write_text("# Dependencies\n")
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        # Create source file with broad exception
        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text(
            "def handler():\n    try:\n        do_thing()\n    except Exception:\n        pass\n"
        )

        # Source changed + dep changed + broad exception
        result = run_hook(
            "stop", tmp_path,
            git_output=" M src/app.py\n M requirements.txt"
        )

        canary_lines = [line for line in result.stderr.splitlines() if "CANARY" in line]
        # Should have: code-no-tests + dep-no-rationale + broad-exception
        assert len(canary_lines) >= 2  # At least code-no-tests and one more

    def test_existing_gates_still_block(self, tmp_path: Path):
        """Existing gates (reflection, Critic) still enforce even with canary present."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        artifacts = prawduct / "artifacts"
        artifacts.mkdir()
        (artifacts / "build-plan.md").write_text("# Build Plan\n\n## Status\n- [ ] Chunk 1\n")
        (prawduct / ".session-git-baseline").write_text("")

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 2
        assert "REFLECTION" in result.stderr


# =============================================================================
# Chunk 3: File Type Classification
# =============================================================================


# =============================================================================


class TestBroadExceptPragma:
    """Broad exception canary skips lines marked with prawduct:ok-broad-except."""

    def test_pragma_on_except_line_skips(self, tmp_path: Path):
        """A broad except with pragma on the same line is not flagged."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text(
            "def handler():\n"
            "    try:\n"
            "        do_thing()\n"
            "    except Exception as e:  # prawduct:ok-broad-except — system boundary\n"
            "        pass\n"
        )

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert "Broad exception" not in result.stderr

    def test_pragma_on_line_above_skips(self, tmp_path: Path):
        """A broad except with pragma on the line above is not flagged."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text(
            "def handler():\n"
            "    try:\n"
            "        do_thing()\n"
            "    # prawduct:ok-broad-except — system boundary\n"
            "    except Exception as e:\n"
            "        pass\n"
        )

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert "Broad exception" not in result.stderr

    def test_unmarked_broad_except_still_flagged(self, tmp_path: Path):
        """A broad except without pragma is still flagged."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text(
            "def handler():\n"
            "    try:\n"
            "        do_thing()\n"
            "    except Exception:\n"
            "        pass\n"
        )

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert "exception" in result.stderr.lower()

    def test_broad_except_with_raise_skips(self, tmp_path: Path):
        """A broad except that re-raises is not flagged (Python only)."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text(
            "def handler():\n"
            "    try:\n"
            "        do_thing()\n"
            "    except Exception as e:\n"
            "        logger.error('failed', exc_info=e)\n"
            "        raise\n"
        )

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert "Broad exception" not in result.stderr

    def test_broad_except_with_logging_skips(self, tmp_path: Path):
        """A broad except that logs is not flagged (Python only)."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text("Session reflection: implemented changes and verified all tests pass correctly.")

        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_text(
            "def handler():\n"
            "    try:\n"
            "        do_thing()\n"
            "    except Exception as e:\n"
            "        logging.error(f'Handler failed: {e}')\n"
            "        return None\n"
        )

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert "Broad exception" not in result.stderr


# =============================================================================
# v6: /clear Governance Warning
# =============================================================================


# =============================================================================


class TestClearGovernanceWarning:
    """/clear warns about previous session's unmet governance gates."""

    def test_warns_when_reflection_missing(self, tmp_path: Path):
        """Warns when previous session had changes but no reflection."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        # Simulate previous session: had changes, no reflection
        (prawduct / ".session-start").write_text("2026-03-01T00:00:00Z")
        (prawduct / ".session-git-baseline").write_text("")
        # No .session-reflected file

        result = run_hook("clear", tmp_path, git_output=" M src/app.py")

        assert "WARNING" in result.stdout
        assert "reflection" in result.stdout.lower()

    def test_no_warning_when_reflection_exists(self, tmp_path: Path):
        """No warning when previous session had reflection."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-start").write_text("2026-03-01T00:00:00Z")
        (prawduct / ".session-git-baseline").write_text("")
        (prawduct / ".session-reflected").write_text(
            "Session reflection: implemented changes and verified all tests pass correctly."
        )

        result = run_hook("clear", tmp_path, git_output=" M src/app.py")

        assert "WARNING" not in result.stdout or "governance" not in result.stdout.lower()

    def test_no_warning_when_no_changes(self, tmp_path: Path):
        """No warning when previous session had no changes."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-start").write_text("2026-03-01T00:00:00Z")
        (prawduct / ".session-git-baseline").write_text("")

        result = run_hook("clear", tmp_path, git_output="")

        assert "governance" not in result.stdout.lower()

    def test_warning_does_not_block(self, tmp_path: Path):
        """Warning is informational — /clear always returns 0."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-start").write_text("2026-03-01T00:00:00Z")
        (prawduct / ".session-git-baseline").write_text("")

        result = run_hook("clear", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 0


# =============================================================================
# v6: Learnings Briefing Format
# =============================================================================


# =============================================================================


class TestLearningsBriefingFormat:
    """Learnings briefing extracts rules from multiple formats."""

    def test_counts_bold_prefix_format(self, tmp_path: Path):
        """Counts rules in '- **Topic**: description' format."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "build_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )
        (prawduct / "learnings.md").write_text(
            "# Learnings\n\n"
            "## Pydantic v2\n"
            "- **No computed_field with extra=forbid**: use @property instead\n"
            "- **validate_assignment recursion**: use self.__dict__[field]\n"
        )

        result = run_hook("clear", tmp_path)

        assert "Learnings" in result.stdout
        assert "2 rules" in result.stdout
        assert "Pydantic v2" in result.stdout

    def test_counts_when_always_never_if_format(self, tmp_path: Path):
        """Counts rules in original 'When/Always/Never/If' format."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "build_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )
        (prawduct / "learnings.md").write_text(
            "# Learnings\n\n"
            "- When adding endpoints, update types first\n"
            "- Always run integration tests after IPC changes\n"
        )

        result = run_hook("clear", tmp_path)

        assert "Learnings" in result.stdout
        assert "2 rules" in result.stdout

    def test_counts_mixed_formats(self, tmp_path: Path):
        """Counts rules from both formats and shows topic index."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "build_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )
        (prawduct / "learnings.md").write_text(
            "# Learnings\n\n"
            "## Testing\n"
            "- When mocking, match sync/async\n"
            "- **OS-assigned ports only**: use socket.bind for test ports\n"
            "\n"
            "## Architecture\n"
            "- Never hardcode container names\n"
        )

        result = run_hook("clear", tmp_path)

        assert "Learnings" in result.stdout
        assert "3 rules" in result.stdout
        assert "Testing" in result.stdout
        assert "Architecture" in result.stdout


# =============================================================================
# Session Handoff
# =============================================================================


# =============================================================================


class TestSessionHandoff:
    """Tests for session handoff generation during /clear."""

    def test_handoff_includes_wip_context(self, tmp_path: Path):
        """Handoff file includes WIP description and context from project-state."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "work_in_progress:\n"
            '  description: "Build the widget"\n'
            '  size: medium\n'
            '  type: feature\n'
            '  context: "Requirements in artifacts/widget-spec.md. Key decision: use React."\n'
        )

        run_hook("clear", tmp_path)

        handoff = prawduct / ".session-handoff.md"
        assert handoff.is_file()
        content = handoff.read_text()
        assert "Build the widget" in content
        assert "Requirements in artifacts/widget-spec.md" in content
        assert "size=medium" in content

    def test_handoff_includes_reflection(self, tmp_path: Path):
        """Handoff captures session reflection before it gets archived."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "work_in_progress:\n"
            '  description: "Some task"\n'
        )
        (prawduct / ".session-reflected").write_text(
            "Completed chunk 1. Tests pass. Key insight: the API needed pagination."
        )

        run_hook("clear", tmp_path)

        handoff = prawduct / ".session-handoff.md"
        assert handoff.is_file()
        content = handoff.read_text()
        assert "Previous Session Reflection" in content
        assert "API needed pagination" in content

    def test_handoff_includes_critic_findings(self, tmp_path: Path):
        """Handoff summarizes critic findings."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "work_in_progress:\n"
            '  description: "Some task"\n'
        )
        (prawduct / ".critic-findings.json").write_text(
            json.dumps({
                "summary": "Generally clean. One warning about error handling.",
                "findings": [
                    {"severity": "warning", "goal": "Nothing Is Broken", "summary": "Missing error handling in API layer"},
                    {"severity": "note", "goal": "Decisions Were Deliberate", "summary": "Consider documenting DB choice"},
                ],
                "files_reviewed": ["src/api.py"],
            })
        )

        run_hook("clear", tmp_path)

        handoff = prawduct / ".session-handoff.md"
        content = handoff.read_text()
        assert "Critic Findings" in content
        assert "1 warning" in content
        assert "Missing error handling" in content

    def test_handoff_includes_changed_files(self, tmp_path: Path):
        """Handoff lists files changed during the session."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "work_in_progress:\n"
            '  description: "Some task"\n'
        )
        # Baseline had no changes; current status shows changes
        (prawduct / ".session-git-baseline").write_text("")

        result = run_hook(
            "clear", tmp_path,
            git_output=" M src/api.py\n M src/models.py\n"
        )

        handoff = prawduct / ".session-handoff.md"
        content = handoff.read_text()
        assert "Files Changed" in content
        assert "src/api.py" in content
        assert "src/models.py" in content

    def test_no_handoff_when_no_wip(self, tmp_path: Path):
        """No handoff file generated when there's nothing to hand off."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "work_in_progress:\n"
            "  description: null\n"
        )

        run_hook("clear", tmp_path)

        handoff = prawduct / ".session-handoff.md"
        assert not handoff.is_file()

    # --- Build plan Status as handoff source ---

    def test_handoff_uses_build_plan_status(self, tmp_path: Path):
        """Handoff reads work context from build plan Status section."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n"
        )
        (artifacts / "build-plan.md").write_text(
            "# Build Plan — Add User Auth (2026-03-28)\n\n"
            "**Size**: Medium | **Type**: Feature\n\n"
            "## Status\n\n"
            "- [x] Chunk 1: Setup — done\n"
            "- [ ] Chunk 2: OAuth integration\n"
            "Context: Chunk 1 done. Next: implement OAuth flow.\n"
        )

        run_hook("clear", tmp_path)

        handoff = prawduct / ".session-handoff.md"
        assert handoff.is_file()
        content = handoff.read_text()
        assert "Add User Auth" in content
        assert "size=Medium" in content
        assert "type=Feature" in content
        assert "Chunk 2: OAuth integration" in content
        assert "Chunk 1 done" in content

    def test_handoff_build_plan_overrides_wip(self, tmp_path: Path):
        """Handoff prefers build plan over project-state.yaml WIP."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            'work_in_progress:\n  description: "Old WIP"\n'
        )
        (artifacts / "build-plan.md").write_text(
            "# Build Plan — New Work (2026-03-28)\n\n"
            "## Status\n\n"
            "- [ ] Chunk 1: Start\n"
        )

        run_hook("clear", tmp_path)

        handoff = prawduct / ".session-handoff.md"
        assert handoff.is_file()
        content = handoff.read_text()
        assert "New Work" in content
        assert "Old WIP" not in content

    def test_no_handoff_when_no_build_plan_and_no_wip(self, tmp_path: Path):
        """No handoff when neither build plan nor WIP has active work."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n"
        )

        run_hook("clear", tmp_path)

        handoff = prawduct / ".session-handoff.md"
        assert not handoff.is_file()

    def test_briefing_includes_wip_context(self, tmp_path: Path):
        """Session briefing now surfaces WIP context field."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "work_in_progress:\n"
            '  description: "Build the widget"\n'
            '  context: "Specs in widget-spec.md. Blocked on API design."\n'
        )

        result = run_hook("clear", tmp_path)

        assert "Context: Specs in widget-spec.md" in result.stdout

    def test_briefing_references_handoff(self, tmp_path: Path):
        """Session briefing tells the model to read the handoff file."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "work_in_progress:\n"
            '  description: "Build the widget"\n'
            '  context: "Some context"\n'
        )

        result = run_hook("clear", tmp_path)

        assert ".session-handoff.md" in result.stdout

    def test_handoff_survives_missing_session_files(self, tmp_path: Path):
        """Handoff generates cleanly even without session-start or baseline."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "work_in_progress:\n"
            '  description: "Some task"\n'
            '  context: "Important context here"\n'
        )
        # No .session-start, no .session-git-baseline

        run_hook("clear", tmp_path)

        handoff = prawduct / ".session-handoff.md"
        assert handoff.is_file()
        content = handoff.read_text()
        assert "Important context here" in content

    # --- _parse_wip edge cases ---

    def test_no_project_state_file(self, tmp_path: Path):
        """No project-state.yaml produces no handoff and 'none active' in briefing."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        result = run_hook("clear", tmp_path)

        assert "none active" in result.stdout
        assert not (prawduct / ".session-handoff.md").is_file()

    def test_no_wip_section_in_state(self, tmp_path: Path):
        """project-state.yaml without work_in_progress section produces no handoff."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "build_state:\n"
            "  source_root: null\n"
        )

        result = run_hook("clear", tmp_path)

        assert "none active" in result.stdout
        assert not (prawduct / ".session-handoff.md").is_file()

    def test_wip_context_with_colon_in_value(self, tmp_path: Path):
        """WIP context containing colons (e.g. URLs) is parsed correctly."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "work_in_progress:\n"
            '  description: "Deploy service"\n'
            '  context: "Docs at http://example.com/api: see section 3"\n'
        )

        run_hook("clear", tmp_path)

        handoff = prawduct / ".session-handoff.md"
        content = handoff.read_text()
        assert "http://example.com/api: see section 3" in content

    def test_wip_all_fields_null(self, tmp_path: Path):
        """WIP with all null fields produces no handoff."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "work_in_progress:\n"
            "  description: null\n"
            "  size: null\n"
            "  type: null\n"
            "  context: null\n"
        )

        run_hook("clear", tmp_path)

        assert not (prawduct / ".session-handoff.md").is_file()

    # --- _summarize_critic_findings edge cases ---

    def test_critic_findings_empty_json(self, tmp_path: Path):
        """Empty JSON object produces no critic section in handoff."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "work_in_progress:\n"
            '  description: "Some task"\n'
        )
        (prawduct / ".critic-findings.json").write_text("{}")

        run_hook("clear", tmp_path)

        handoff = prawduct / ".session-handoff.md"
        content = handoff.read_text()
        assert "Critic Findings" not in content

    def test_critic_findings_malformed_json(self, tmp_path: Path):
        """Malformed JSON doesn't crash; critic section is skipped."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "work_in_progress:\n"
            '  description: "Some task"\n'
        )
        (prawduct / ".critic-findings.json").write_text("{not valid json")

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        handoff = prawduct / ".session-handoff.md"
        content = handoff.read_text()
        assert "Critic Findings" not in content

    def test_critic_findings_missing_severity(self, tmp_path: Path):
        """Finding without severity field is silently skipped in counts."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "work_in_progress:\n"
            '  description: "Some task"\n'
        )
        (prawduct / ".critic-findings.json").write_text(
            json.dumps({
                "summary": "Review complete",
                "findings": [
                    {"goal": "Nothing Is Broken", "summary": "No severity field here"},
                    {"severity": "warning", "goal": "Coherence", "summary": "A real warning"},
                ],
                "files_reviewed": ["src/app.py"],
            })
        )

        run_hook("clear", tmp_path)

        handoff = prawduct / ".session-handoff.md"
        content = handoff.read_text()
        assert "1 warning" in content
        assert "A real warning" in content

    def test_critic_summary_only_no_findings(self, tmp_path: Path):
        """Critic JSON with summary but empty findings list still shows summary."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "work_in_progress:\n"
            '  description: "Some task"\n'
        )
        (prawduct / ".critic-findings.json").write_text(
            json.dumps({
                "summary": "Clean review, no issues found.",
                "findings": [],
                "files_reviewed": ["src/app.py"],
            })
        )

        run_hook("clear", tmp_path)

        handoff = prawduct / ".session-handoff.md"
        content = handoff.read_text()
        assert "Critic Findings" in content
        assert "Clean review" in content

    # --- List cap boundaries ---

    def test_changed_files_capped_at_20(self, tmp_path: Path):
        """More than 20 changed files are capped with a summary line."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "work_in_progress:\n"
            '  description: "Big refactor"\n'
        )
        (prawduct / ".session-git-baseline").write_text("")
        # 25 changed files
        git_output = "".join(f" M src/file{i:02d}.py\n" for i in range(25))

        run_hook("clear", tmp_path, git_output=git_output)

        handoff = prawduct / ".session-handoff.md"
        content = handoff.read_text()
        assert "file19.py" in content  # 20th file (0-indexed) should be included
        assert "file20.py" not in content  # 21st should be capped
        assert "... and 5 more" in content

    # --- Context truncation ---

    def test_briefing_truncates_long_context(self, tmp_path: Path):
        """Context longer than 200 chars is truncated in the briefing."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        long_context = "A" * 250
        (prawduct / "project-state.yaml").write_text(
            "work_in_progress:\n"
            '  description: "Some task"\n'
            f'  context: "{long_context}"\n'
        )

        result = run_hook("clear", tmp_path)

        # Briefing should truncate
        assert "Context: " in result.stdout
        context_line = [l for l in result.stdout.splitlines() if l.startswith("Context:")][0]
        assert context_line.endswith("...")
        assert len(context_line) < 220  # "Context: " + 197 + "..."

        # Handoff should have the full context
        handoff = prawduct / ".session-handoff.md"
        content = handoff.read_text()
        assert long_context in content

    # --- Empty/whitespace reflection ---

    def test_empty_reflection_file_excluded(self, tmp_path: Path):
        """Empty or whitespace-only reflection file doesn't produce a section."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "work_in_progress:\n"
            '  description: "Some task"\n'
        )
        (prawduct / ".session-reflected").write_text("   \n  \n  ")

        run_hook("clear", tmp_path)

        handoff = prawduct / ".session-handoff.md"
        content = handoff.read_text()
        assert "Previous Session Reflection" not in content

    # --- Only some sections populated ---

    def test_handoff_with_only_reflection(self, tmp_path: Path):
        """Handoff with WIP description but only reflection content still writes file."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "work_in_progress:\n"
            '  description: "Quick fix"\n'
        )
        (prawduct / ".session-reflected").write_text(
            "Fixed the auth bug. Root cause was expired token cache."
        )

        run_hook("clear", tmp_path)

        handoff = prawduct / ".session-handoff.md"
        content = handoff.read_text()
        assert "Quick fix" in content
        assert "expired token cache" in content
        assert "Critic Findings" not in content
        assert "Files Changed" not in content


# =============================================================================
# Doc-Only Change Detection (multi-line git output tests)
# =============================================================================

