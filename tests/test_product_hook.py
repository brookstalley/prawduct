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


class TestDesignerHandoffSkipsCriticGate:
    """v1.4 F6 — chunks declared `Type: designer-handoff` skip the stop-hook
    Critic gate. This formalizes the carveout that previously lived as a
    user-memory rule (not a framework rule), so the structural enforcement
    matches the methodology.

    Only `designer-handoff` skips the gate. `doc-only` and `cleanup` still
    require Critic findings — only their *protocol* adjusts (Critic's domain,
    not the gate's). Unknown Type values fall through to the default
    behavior (gate fires) per the helper's fail-closed default.
    """

    def test_designer_handoff_skips_critic_with_code_changes(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text(
            "# Build Plan\n\n## Status\n- [ ] Chunk 01: Visual polish\n\n"
            "## Build Chunks\n\n"
            "### Chunk 01: Visual polish\n\n"
            "- **Type:** designer-handoff\n",
        )
        (prawduct / ".session-reflected").write_text(
            "Session reflection: handed off design tokens for designer review; no Critic gating per F6."
        )
        (prawduct / ".session-git-baseline").write_text("")
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M src/styles.css")

        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "CRITIC" not in result.stderr
        # User must see the skip — invisible carveouts are exactly what
        # the framework rule replaces.
        assert "designer-handoff" in result.stderr.lower()

    def test_code_chunk_still_requires_critic(self, tmp_path: Path):
        """Sanity check: when the current chunk's Type is `code` (the default),
        the Critic gate still fires for non-doc-only changes."""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text(
            "# Build Plan\n\n## Status\n- [ ] Chunk 01: Feature\n\n"
            "## Build Chunks\n\n"
            "### Chunk 01: Feature\n\n"
            "- **Type:** code\n",
        )
        (prawduct / ".session-reflected").write_text(
            "Session reflection: implemented feature and verified all tests pass correctly."
        )
        (prawduct / ".session-git-baseline").write_text("")
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 2
        assert "CRITIC" in result.stderr

    def test_unknown_type_falls_through_to_critic_gate(self, tmp_path: Path):
        """Fail-closed contract: a typo'd Type value must not silently skip
        the Critic — the gate fires as if the field were `code`. (The parser
        surfaces the typo error elsewhere; the gate just refuses to honor it.)"""
        prawduct = tmp_path / ".prawduct"
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True)
        (artifacts / "build-plan.md").write_text(
            "# Build Plan\n\n## Status\n- [ ] Chunk 01: Mystery\n\n"
            "## Build Chunks\n\n"
            "### Chunk 01: Mystery\n\n"
            "- **Type:** wibble\n",
        )
        (prawduct / ".session-reflected").write_text(
            "Session reflection: did something, value unclear; tests all pass currently."
        )
        (prawduct / ".session-git-baseline").write_text("")
        make_session_start(prawduct)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert result.returncode == 2
        assert "CRITIC" in result.stderr


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
            "skipped": 0,
            "duration_seconds": 12,
            "command": "pytest -q",
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
            "skipped": 0,
            "duration_seconds": 12,
            "command": "pytest -q",
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
            "skipped": 0,
            "duration_seconds": 12,
            "command": "pytest -q",
            "total": 100,
        }))

        result = run_hook("test-status", tmp_path, git_output="")

        assert result.returncode == 1
        assert "stale" in result.stdout
        assert "predates session" in result.stdout

    def test_no_timestamp_in_evidence_is_stale(self, tmp_path: Path):
        """Evidence missing the timestamp field is stale.

        With the schema validator wired into ``tests_are_current``, the
        missing-field error surfaces before the freshness fallback runs —
        so the message names the field rather than reporting "no timestamp"
        from the older fallback path. Either form is acceptable to callers
        because the exit code is the load-bearing signal.
        """
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-start").write_text("2026-04-17T10:00:00Z")
        (prawduct / ".test-evidence.json").write_text(json.dumps({
            "git_sha": "deadbeef" * 5,
            "passed": 100,
            "failed": 0,
            "skipped": 0,
            "duration_seconds": 12,
            "command": "pytest -q",
            "total": 100,
        }))

        result = run_hook("test-status", tmp_path, git_output="")

        assert result.returncode == 1
        assert "stale" in result.stdout
        assert "timestamp" in result.stdout

    def test_no_session_marker_accepts_passing_evidence(self, tmp_path: Path):
        """Without a session-start marker, accept evidence with passing tests."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".test-evidence.json").write_text(json.dumps({
            "timestamp": "2026-04-17T10:05:00Z",
            "passed": 100,
            "failed": 0,
            "skipped": 0,
            "duration_seconds": 12,
            "command": "pytest -q",
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
            "skipped": 0,
            "duration_seconds": 12,
            "command": "pytest -q",
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

    def test_schema_violation_surfaces_in_test_status(self, tmp_path: Path):
        """Writer typo (``ran_at`` instead of ``timestamp``) fails loud
        with the schema-validator message, not the older "no timestamp"
        fallback. Proves the schema check runs before the freshness logic.
        """
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-start").write_text("2026-04-17T10:00:00Z")
        (prawduct / ".test-evidence.json").write_text(json.dumps({
            "ran_at": "2026-04-17T10:05:00Z",  # typo: should be "timestamp"
            "passed": 100,
            "failed": 0,
            "skipped": 0,
            "duration_seconds": 12,
            "command": "pytest -q",
        }))

        result = run_hook("test-status", tmp_path, git_output="")

        assert result.returncode == 1
        assert "missing required field(s)" in result.stdout
        assert "timestamp" in result.stdout

    def test_single_line_output(self, tmp_path: Path):
        """test-status outputs exactly one status line."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        result = run_hook("test-status", tmp_path, git_output="")

        lines = result.stdout.strip().splitlines()
        assert len(lines) == 1
        assert lines[0].startswith("stale")


# =============================================================================
# validate-evidence subcommand: schema enforcement
# =============================================================================


def _valid_evidence() -> dict:
    """Build a fully-schema-valid evidence dict.

    Tests reach for this when the test isn't *about* a missing or wrong-typed
    field — saves repeating the full set of required fields in every fixture.
    """
    return {
        "timestamp": "2026-05-05T12:00:00Z",
        "passed": 880,
        "failed": 0,
        "skipped": 0,
        "duration_seconds": 287,
        "command": "pytest -q",
    }


class TestValidateEvidenceSchema:
    """Schema validation behavior — what the validator accepts and rejects.

    Driven through the ``validate-evidence`` subcommand because that's the
    user-visible surface; the schema-helper internals aren't importable here.
    """

    def _write(self, tmp_path: Path, evidence: object) -> None:
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir(exist_ok=True)
        (prawduct / ".test-evidence.json").write_text(json.dumps(evidence))

    def test_full_valid_schema_accepted(self, tmp_path: Path):
        self._write(tmp_path, _valid_evidence())

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 0, result.stderr
        assert "valid" in result.stdout

    def test_extra_fields_allowed(self, tmp_path: Path):
        """Optional metadata (git_sha, total) and free-form fields don't reject."""
        evidence = _valid_evidence() | {
            "git_sha": "deadbeef" * 5,
            "total": 880,
            "chunk": "Chunk 01",
            "branch": "feature/test-evidence-schema-validator",
            "notes": "all green",
        }
        self._write(tmp_path, evidence)

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 0, result.stderr

    def test_duration_seconds_as_float_accepted(self, tmp_path: Path):
        evidence = _valid_evidence() | {"duration_seconds": 287.86}
        self._write(tmp_path, evidence)

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 0, result.stderr

    def test_single_missing_field_named(self, tmp_path: Path):
        evidence = _valid_evidence()
        del evidence["command"]
        self._write(tmp_path, evidence)

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 1
        assert "missing required field(s)" in result.stderr
        assert "command" in result.stderr

    def test_multiple_missing_fields_sorted_and_comma_joined(self, tmp_path: Path):
        evidence = _valid_evidence()
        for f in ("command", "skipped", "duration_seconds"):
            del evidence[f]
        self._write(tmp_path, evidence)

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 1
        assert "missing required field(s): command, duration_seconds, skipped" in result.stderr

    def test_wrong_type_named(self, tmp_path: Path):
        """``passed: "100"`` (str) names the field and shows expected vs. actual."""
        evidence = _valid_evidence() | {"passed": "100"}
        self._write(tmp_path, evidence)

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 1
        assert "schema violation" in result.stderr
        assert "passed must be int" in result.stderr
        assert "got str" in result.stderr

    def test_multiple_wrong_types_semicolon_joined(self, tmp_path: Path):
        evidence = _valid_evidence() | {"passed": "100", "failed": "0"}
        self._write(tmp_path, evidence)

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 1
        assert "schema violation" in result.stderr
        # Both violations reported in one error
        assert "passed must be int" in result.stderr
        assert "failed must be int" in result.stderr
        assert ";" in result.stderr

    def test_missing_takes_precedence_over_wrong_type(self, tmp_path: Path):
        """When evidence has BOTH a missing field AND a wrong-typed field,
        the validator reports the missing field — fixing missing fields is
        the higher-priority repair, and we don't want users distracted by
        wrong-type messages on fields that may not even be present.
        """
        evidence = _valid_evidence() | {"passed": "100"}  # wrong type
        del evidence["timestamp"]                          # missing
        self._write(tmp_path, evidence)

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 1
        assert "missing required field(s)" in result.stderr
        assert "timestamp" in result.stderr
        # The wrong-type message must NOT appear — missing-field check returns first.
        assert "schema violation" not in result.stderr


class TestCoverageEvidenceSchema:
    """v1.4 F4a — coverage-evidence fields (verifier, tests_executed,
    changes_referenced, coverage_level).

    Presence of ``verifier`` is the schema discriminator: legacy fingerprint
    evidence (no ``verifier``) keeps validating; new evidence with ``verifier``
    must also carry the other three fields with the right types. This
    enforces compat in both directions — old writers don't break, new
    writers can't silently typo a field name and lose the coverage data.
    """

    def _write(self, tmp_path: Path, evidence: object) -> None:
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir(exist_ok=True)
        (prawduct / ".test-evidence.json").write_text(json.dumps(evidence))

    def _coverage_evidence(self) -> dict:
        return _valid_evidence() | {
            "verifier": "test-reference-verify (floor: symbol-grep)",
            "tests_executed": ["tests/test_product_hook.py"],
            "changes_referenced": ["tools/product-hook"],
            "coverage_level": "referenced",
        }

    def test_legacy_fingerprint_only_still_valid(self, tmp_path: Path):
        """Evidence without ``verifier`` validates as before (compat)."""
        self._write(tmp_path, _valid_evidence())

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 0, result.stderr

    def test_full_coverage_evidence_accepted(self, tmp_path: Path):
        self._write(tmp_path, self._coverage_evidence())

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 0, result.stderr

    def test_executed_level_accepted(self, tmp_path: Path):
        """Both enum values for ``coverage_level`` are valid."""
        evidence = self._coverage_evidence() | {"coverage_level": "executed"}
        self._write(tmp_path, evidence)

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 0, result.stderr

    def test_unknown_coverage_level_rejected(self, tmp_path: Path):
        evidence = self._coverage_evidence() | {"coverage_level": "partial"}
        self._write(tmp_path, evidence)

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 1
        assert "coverage_level must be one of" in result.stderr
        assert "'partial'" in result.stderr

    def test_verifier_without_companion_fields_rejected(self, tmp_path: Path):
        """Opting into the new schema requires the full set —
        a typo like ``tests_ran`` for ``tests_executed`` is caught."""
        evidence = self._coverage_evidence()
        del evidence["tests_executed"]
        self._write(tmp_path, evidence)

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 1
        assert "missing required field(s)" in result.stderr
        assert "tests_executed" in result.stderr

    def test_changes_referenced_wrong_type_rejected(self, tmp_path: Path):
        """Lists are required so the Critic can iterate them."""
        evidence = self._coverage_evidence() | {"changes_referenced": "tools/product-hook"}
        self._write(tmp_path, evidence)

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 1
        assert "changes_referenced must be list" in result.stderr

    def test_empty_lists_accepted(self, tmp_path: Path):
        """A clean run with no changes legitimately has empty lists —
        and shape validation should accept that. Whether empty lists
        constitute a finding is the Critic's call (Chunk 09), not the
        schema's."""
        evidence = self._coverage_evidence() | {
            "tests_executed": [],
            "changes_referenced": [],
        }
        self._write(tmp_path, evidence)

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 0, result.stderr


class TestValidateEvidenceSubcommand:
    """Exit-code and IO contract of the ``validate-evidence`` subcommand."""

    def test_missing_file_exits_one(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 1
        assert result.stderr.startswith("missing:")

    def test_unreadable_json_exits_one(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".test-evidence.json").write_text("{ this is not json")

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 1
        assert result.stderr.startswith("unreadable:")

    def test_non_dict_root_exits_one(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".test-evidence.json").write_text(json.dumps([_valid_evidence()]))

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 1
        assert "evidence is not a JSON object" in result.stderr

    def test_schema_invalid_exits_one_with_invalid_prefix(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        evidence = _valid_evidence()
        del evidence["command"]
        (prawduct / ".test-evidence.json").write_text(json.dumps(evidence))

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 1
        assert result.stderr.startswith("invalid:")

    def test_valid_evidence_exits_zero_prints_valid(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".test-evidence.json").write_text(json.dumps(_valid_evidence()))

        result = run_hook("validate-evidence", tmp_path, git_output="")

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "valid"


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


def _load_product_hook():
    """Import product-hook as a module so we can call internal helpers directly.

    The shebang script has no .py extension, so the standard import machinery
    won't resolve it. Mirrors the pattern used by TestSessionBriefing.
    """
    import importlib.machinery
    import importlib.util

    loader = importlib.machinery.SourceFileLoader("product_hook", str(HOOK_PATH))
    spec = importlib.util.spec_from_loader("product_hook", loader)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestCriticModeGate:
    """The advisory mode gate fires when a multi-chunk plan is fully complete
    but the latest Critic review was chunk-mode (end-of-cycle synthesis skipped).

    Tests reference the canonical constants from product-hook
    (`_CRITIC_MODE_CHUNK`, `_CRITIC_MODE_FINAL`) rather than the literal verbose
    strings — single source of truth in the module under test.
    """

    @pytest.fixture(autouse=True)
    def _module(self):
        self.mod = _load_product_hook()

    def _make_findings(
        self,
        prawduct: Path,
        *,
        mode: str | None = None,
        files_reviewed: list[str] | None = None,
    ) -> Path:
        data: dict = {
            "files_reviewed": files_reviewed or ["src/app.py"],
            "findings": [],
            "summary": "No issues found. Changes are ready to proceed.",
        }
        if mode is not None:
            data["mode"] = mode
        path = prawduct / ".critic-findings.json"
        path.write_text(json.dumps(data))
        return path

    def _make_plan(self, prawduct: Path, *, total: int, complete: int) -> None:
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        lines = ["# Build Plan\n", "## Status\n"]
        for i in range(complete):
            lines.append(f"- [x] Chunk 0{i+1}: completed\n")
        for i in range(complete, total):
            lines.append(f"- [ ] Chunk 0{i+1}: pending\n")
        (artifacts / "build-plan.md").write_text("".join(lines))

    # ---- _critic_session_satisfies_gate ----

    def test_no_build_plan_satisfies_gate(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        self._make_findings(prawduct, mode=self.mod._CRITIC_MODE_CHUNK)
        ok, reason = self.mod._critic_session_satisfies_gate(prawduct)
        assert ok is True
        assert reason == ""

    def test_single_chunk_plan_with_chunk_mode_satisfies_gate(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        self._make_plan(prawduct, total=1, complete=1)
        self._make_findings(prawduct, mode=self.mod._CRITIC_MODE_CHUNK)
        ok, _ = self.mod._critic_session_satisfies_gate(prawduct)
        assert ok is True

    def test_single_chunk_plan_with_final_mode_satisfies_gate(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        self._make_plan(prawduct, total=1, complete=1)
        self._make_findings(prawduct, mode=self.mod._CRITIC_MODE_FINAL)
        ok, _ = self.mod._critic_session_satisfies_gate(prawduct)
        assert ok is True

    def test_multi_chunk_plan_with_incomplete_chunks_satisfies_gate(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        self._make_plan(prawduct, total=3, complete=1)
        self._make_findings(prawduct, mode=self.mod._CRITIC_MODE_CHUNK)
        ok, _ = self.mod._critic_session_satisfies_gate(prawduct)
        assert ok is True, "mid-cycle chunk-mode review is fine; gate fires only when all chunks are [x]"

    def test_multi_chunk_plan_all_complete_with_chunk_mode_unsatisfied(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        self._make_plan(prawduct, total=3, complete=3)
        self._make_findings(prawduct, mode=self.mod._CRITIC_MODE_CHUNK)
        ok, reason = self.mod._critic_session_satisfies_gate(prawduct)
        assert ok is False
        assert "3 chunks complete" in reason
        assert self.mod._CRITIC_MODE_CHUNK in reason
        assert "/critic final" in reason

    def test_multi_chunk_plan_all_complete_with_final_mode_satisfies_gate(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        self._make_plan(prawduct, total=3, complete=3)
        self._make_findings(prawduct, mode=self.mod._CRITIC_MODE_FINAL)
        ok, _ = self.mod._critic_session_satisfies_gate(prawduct)
        assert ok is True

    def test_findings_without_mode_field_treated_as_final(self, tmp_path: Path):
        """Back-compat: legacy records pre-dating v1.3.13 omit `mode`. Default to final."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        self._make_plan(prawduct, total=3, complete=3)
        self._make_findings(prawduct, mode=None)  # no mode key
        ok, _ = self.mod._critic_session_satisfies_gate(prawduct)
        assert ok is True

    # ---- validate_critic_findings (mode validation) ----

    def test_validate_critic_findings_accepts_verbose_chunk_mode(self, tmp_path: Path):
        path = tmp_path / "findings.json"
        path.write_text(json.dumps({
            "files_reviewed": ["src/app.py"],
            "findings": [],
            "summary": "No issues.",
            "mode": self.mod._CRITIC_MODE_CHUNK,
        }))
        assert self.mod.validate_critic_findings(path) is True

    def test_validate_critic_findings_accepts_verbose_final_mode(self, tmp_path: Path):
        path = tmp_path / "findings.json"
        path.write_text(json.dumps({
            "files_reviewed": ["src/app.py"],
            "findings": [],
            "summary": "No issues.",
            "mode": self.mod._CRITIC_MODE_FINAL,
        }))
        assert self.mod.validate_critic_findings(path) is True

    def test_validate_critic_findings_accepts_no_mode(self, tmp_path: Path):
        """Mode is optional; legacy records (no `mode` key) remain valid."""
        path = tmp_path / "findings.json"
        path.write_text(json.dumps({
            "files_reviewed": ["src/app.py"],
            "findings": [],
            "summary": "No issues.",
        }))
        assert self.mod.validate_critic_findings(path) is True

    def test_validate_critic_findings_rejects_short_token_mode(self, tmp_path: Path):
        """The bare short token is a writer error; the persisted form is verbose."""
        path = tmp_path / "findings.json"
        path.write_text(json.dumps({
            "files_reviewed": ["src/app.py"],
            "findings": [],
            "summary": "No issues.",
            "mode": "chunk",
        }))
        assert self.mod.validate_critic_findings(path) is False

    def test_validate_critic_findings_rejects_unknown_mode_string(self, tmp_path: Path):
        path = tmp_path / "findings.json"
        path.write_text(json.dumps({
            "files_reviewed": ["src/app.py"],
            "findings": [],
            "summary": "No issues.",
            "mode": "weird-value",
        }))
        assert self.mod.validate_critic_findings(path) is False

    def test_validate_critic_findings_rejects_non_string_mode(self, tmp_path: Path):
        path = tmp_path / "findings.json"
        path.write_text(json.dumps({
            "files_reviewed": ["src/app.py"],
            "findings": [],
            "summary": "No issues.",
            "mode": 7,
        }))
        assert self.mod.validate_critic_findings(path) is False

    def test_validate_critic_findings_accepts_verbose_cumulative_mode(self, tmp_path: Path):
        """The third mode (added in v1.4 F2) reviews `merge-base...HEAD` for PR gating."""
        path = tmp_path / "findings.json"
        path.write_text(json.dumps({
            "files_reviewed": ["src/app.py"],
            "findings": [],
            "summary": "No issues.",
            "mode": self.mod._CRITIC_MODE_CUMULATIVE,
        }))
        assert self.mod.validate_critic_findings(path) is True

    def test_validate_critic_findings_rejects_bare_cumulative_token(self, tmp_path: Path):
        """Bare 'cumulative' is the caller-side $ARGUMENTS form, not the persistence form."""
        path = tmp_path / "findings.json"
        path.write_text(json.dumps({
            "files_reviewed": ["src/app.py"],
            "findings": [],
            "summary": "No issues.",
            "mode": "cumulative",
        }))
        assert self.mod.validate_critic_findings(path) is False

    # ---- Integration: cmd_stop surfaces the advisory NOTE ----

    def test_stop_hook_surfaces_advisory_when_all_chunks_complete_with_chunk_mode(
        self, tmp_path: Path
    ):
        """End-to-end: 3-chunk plan all [x], findings mode=chunk → NOTE on stderr."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        self._make_plan(prawduct, total=3, complete=3)
        self._make_findings(prawduct, mode=self.mod._CRITIC_MODE_CHUNK)
        # Even with "complete" chunks, the existing critic gate still passes
        # because findings exist and validate. The mode advisory is the new layer.
        (prawduct / ".session-reflected").write_text(
            "Reflection captured: implemented all chunks and ran chunk-mode reviews."
        )
        make_session_start(prawduct, offset_seconds=-60)
        # Touch findings AFTER session start so they count as this-session.
        time.sleep(0.05)
        self._make_findings(prawduct, mode=self.mod._CRITIC_MODE_CHUNK)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        # Plan is "complete" so existing reflection/critic gates may not block.
        # The advisory NOTE should appear on stderr regardless of return code.
        assert "Run /critic final" in result.stderr or "/critic final" in result.stderr
        assert self.mod._CRITIC_MODE_CHUNK in result.stderr

    def test_stop_hook_no_advisory_when_final_mode_recorded(self, tmp_path: Path):
        """End-to-end: 3-chunk plan all [x], findings mode=final → no advisory."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        self._make_plan(prawduct, total=3, complete=3)
        (prawduct / ".session-reflected").write_text(
            "Reflection: ran final-mode review at end of cycle as expected."
        )
        make_session_start(prawduct, offset_seconds=-60)
        time.sleep(0.05)
        self._make_findings(prawduct, mode=self.mod._CRITIC_MODE_FINAL)

        result = run_hook("stop", tmp_path, git_output=" M src/app.py")

        assert "Run /critic final" not in result.stderr
        # The verbose chunk string must not appear in stderr — that text is only
        # in the gate's reason, which only fires for unsatisfied gates.
        assert "lighter pass, not ready for push" not in result.stderr


# =============================================================================
# check-cumulative-critic subcommand (v1.4 F2 — PR gate)
# =============================================================================


class TestCheckCumulativeCriticSubcommand:
    """The `check-cumulative-critic` subcommand provides the structural gate
    `/pr create` calls before opening a PR. It enforces that a cumulative-mode
    Critic review exists, is fresh (this session), is schema-valid, and has
    no unresolved BLOCKING findings.

    Exit 0 = gate satisfied; exit 1 = gate fails (stderr explains why).
    """

    def _make_cumulative_findings(
        self,
        prawduct: Path,
        *,
        mode: str | None,
        findings: list[dict] | None = None,
        summary: str = "No issues found. Bundle is ready to merge.",
    ) -> Path:
        data: dict = {
            "files_reviewed": ["src/app.py"],
            "findings": findings if findings is not None else [],
            "summary": summary,
        }
        if mode is not None:
            data["mode"] = mode
        path = prawduct / ".critic-findings.json"
        path.write_text(json.dumps(data))
        return path

    def test_missing_findings_file_exits_one(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        make_session_start(prawduct, offset_seconds=-60)

        result = run_hook("check-cumulative-critic", tmp_path, git_output="")

        assert result.returncode == 1
        assert "missing" in result.stderr.lower() or "no cumulative" in result.stderr.lower()

    def test_findings_exist_but_chunk_mode_exits_one(self, tmp_path: Path):
        """chunk-mode findings do NOT satisfy the cumulative gate, even if fresh."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        make_session_start(prawduct, offset_seconds=-60)
        time.sleep(0.05)
        mod = _load_product_hook()
        self._make_cumulative_findings(prawduct, mode=mod._CRITIC_MODE_CHUNK)

        result = run_hook("check-cumulative-critic", tmp_path, git_output="")

        assert result.returncode == 1
        assert "cumulative" in result.stderr.lower()

    def test_findings_exist_but_final_mode_exits_one(self, tmp_path: Path):
        """final-mode findings cover end-of-cycle but not `merge-base...HEAD` — gate still fails."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        make_session_start(prawduct, offset_seconds=-60)
        time.sleep(0.05)
        mod = _load_product_hook()
        self._make_cumulative_findings(prawduct, mode=mod._CRITIC_MODE_FINAL)

        result = run_hook("check-cumulative-critic", tmp_path, git_output="")

        assert result.returncode == 1
        assert "cumulative" in result.stderr.lower()

    def test_missing_session_start_fails_closed(self, tmp_path: Path):
        """When `.session-start` is absent the gate must fail closed: the
        freshness check cannot verify that fresh-looking cumulative findings
        are from the current session, so accepting them would be a silent
        escape hatch (see learnings.md: "Escape hatches in classification
        create silent failures"). Mirrors `_check_previous_session_gates`'s
        `needs_review = True` default."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        mod = _load_product_hook()
        # Cumulative findings exist and would otherwise satisfy the gate —
        # only the missing .session-start should cause failure.
        self._make_cumulative_findings(prawduct, mode=mod._CRITIC_MODE_CUMULATIVE)
        assert not (prawduct / ".session-start").exists()

        result = run_hook("check-cumulative-critic", tmp_path, git_output="")

        assert result.returncode == 1
        assert "session-start" in result.stderr.lower()

    def test_findings_stale_exits_one(self, tmp_path: Path):
        """Findings from a prior session do not satisfy the gate — must be this-session."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        mod = _load_product_hook()
        # Write findings BEFORE setting session-start so mtime predates it.
        self._make_cumulative_findings(prawduct, mode=mod._CRITIC_MODE_CUMULATIVE)
        time.sleep(0.05)
        make_session_start(prawduct, offset_seconds=0)

        result = run_hook("check-cumulative-critic", tmp_path, git_output="")

        assert result.returncode == 1
        assert "stale" in result.stderr.lower() or "predate" in result.stderr.lower()

    def test_findings_with_blocking_exits_one(self, tmp_path: Path):
        """Cumulative findings with unresolved BLOCKING fail the gate."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        make_session_start(prawduct, offset_seconds=-60)
        time.sleep(0.05)
        mod = _load_product_hook()
        self._make_cumulative_findings(
            prawduct,
            mode=mod._CRITIC_MODE_CUMULATIVE,
            findings=[{
                "goal": "Nothing Is Broken",
                "severity": "blocking",
                "summary": "Off-by-one in pagination handler",
            }],
            summary="1 blocking. Not ready to merge.",
        )

        result = run_hook("check-cumulative-critic", tmp_path, git_output="")

        assert result.returncode == 1
        assert "blocking" in result.stderr.lower()

    def test_fresh_clean_cumulative_findings_exit_zero(self, tmp_path: Path):
        """Happy path: cumulative mode, in session window, no blocking → gate satisfied."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        make_session_start(prawduct, offset_seconds=-60)
        time.sleep(0.05)
        mod = _load_product_hook()
        self._make_cumulative_findings(prawduct, mode=mod._CRITIC_MODE_CUMULATIVE)

        result = run_hook("check-cumulative-critic", tmp_path, git_output="")

        assert result.returncode == 0, result.stderr
        assert "satisfied" in result.stdout.lower() or "ok" in result.stdout.lower()

    def test_cumulative_findings_with_warnings_exit_zero(self, tmp_path: Path):
        """Warnings are advisory at the PR gate — only BLOCKING blocks. Matches existing PR-reviewer semantics."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        make_session_start(prawduct, offset_seconds=-60)
        time.sleep(0.05)
        mod = _load_product_hook()
        self._make_cumulative_findings(
            prawduct,
            mode=mod._CRITIC_MODE_CUMULATIVE,
            findings=[{
                "goal": "Design Is Sound",
                "severity": "warning",
                "summary": "Consider extracting the duplicated parser into a helper.",
            }],
            summary="1 warning. Bundle ready to merge after addressing.",
        )

        result = run_hook("check-cumulative-critic", tmp_path, git_output="")

        assert result.returncode == 0, result.stderr


class TestParseBuildPlanChunkRefs:
    """`_parse_build_plan_chunk_refs` extracts backticked file-path references
    from a single chunk's `### Chunk NN:` section in build-plan.md.

    Scope of chunk 02 is **file paths only** — symbol and backlog-id extraction
    are deliberately deferred (see Chunk 02 plan-vs-execution divergence in
    commit message). Symbols/backlog produce too many false positives without
    project-specific conventions; file-path drift is the highest-value check.
    """

    def _write_plan(self, prawduct: Path, body: str) -> Path:
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        path = artifacts / "build-plan.md"
        path.write_text(body)
        return path

    def test_extracts_file_paths_from_named_chunk(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        self._write_plan(
            prawduct,
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 01: Setup\n\n"
            "- **Description:** modify `agents/critic/SKILL.md` and `tools/product-hook`.\n"
            "- **Type:** code\n",
        )
        mod = _load_product_hook()
        refs = mod._parse_build_plan_chunk_refs(prawduct, "01")
        paths = [r["ref"] for r in refs["file_paths"]]
        assert "agents/critic/SKILL.md" in paths
        assert "tools/product-hook" in paths
        assert refs.get("error") is None

    def test_excludes_other_chunks(self, tmp_path: Path):
        """Refs in Chunk 02 must NOT be returned when asking for Chunk 01."""
        prawduct = tmp_path / ".prawduct"
        self._write_plan(
            prawduct,
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 01: First\n\n"
            "- **Description:** touches `path/in/chunk1.md`.\n\n"
            "### Chunk 02: Second\n\n"
            "- **Description:** touches `path/in/chunk2.md`.\n",
        )
        mod = _load_product_hook()
        refs = mod._parse_build_plan_chunk_refs(prawduct, "01")
        paths = [r["ref"] for r in refs["file_paths"]]
        assert "path/in/chunk1.md" in paths
        assert "path/in/chunk2.md" not in paths

    def test_skips_paths_preceded_by_new_qualifier(self, tmp_path: Path):
        """A backticked path immediately preceded by the word "new" is a
        forward reference within the current chunk (a file the chunk creates,
        not modifies). The verifier must not flag it as missing."""
        prawduct = tmp_path / ".prawduct"
        self._write_plan(
            prawduct,
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 01: Setup\n\n"
            "- **Deliverables:**\n"
            "  - `existing/file.md` or new `new/file.md`: detail.\n"
            "  - new `another/new.md`: more detail.\n",
        )
        mod = _load_product_hook()
        refs = mod._parse_build_plan_chunk_refs(prawduct, "01")
        paths = [r["ref"] for r in refs["file_paths"]]
        assert "existing/file.md" in paths
        assert "new/file.md" not in paths
        assert "another/new.md" not in paths

    def test_skips_paths_inside_code_fences(self, tmp_path: Path):
        """Fenced code blocks (project-structure diagrams) shouldn't trigger
        ref extraction — those are illustrative, not load-bearing."""
        prawduct = tmp_path / ".prawduct"
        self._write_plan(
            prawduct,
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 01: Setup\n\n"
            "- **Description:** modifies `real/file.md`.\n"
            "\n```\n"
            "project/\n"
            "├── `inside/fence.md`\n"
            "```\n",
        )
        mod = _load_product_hook()
        refs = mod._parse_build_plan_chunk_refs(prawduct, "01")
        paths = [r["ref"] for r in refs["file_paths"]]
        assert "real/file.md" in paths
        assert "inside/fence.md" not in paths

    def test_missing_chunk_returns_error(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        self._write_plan(
            prawduct,
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 01: Only one\n\n- **Description:** nothing.\n",
        )
        mod = _load_product_hook()
        refs = mod._parse_build_plan_chunk_refs(prawduct, "99")
        assert refs["file_paths"] == []
        assert "not found" in refs["error"].lower() or "chunk 99" in refs["error"].lower()

    def test_missing_build_plan_returns_error(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        mod = _load_product_hook()
        refs = mod._parse_build_plan_chunk_refs(prawduct, "01")
        assert refs["file_paths"] == []
        assert "build-plan" in refs["error"].lower() or "missing" in refs["error"].lower()

    def test_ignores_non_path_backticks(self, tmp_path: Path):
        """Backticked identifiers without path-like shape (no `/`, no known
        file suffix) are not extracted as paths."""
        prawduct = tmp_path / ".prawduct"
        self._write_plan(
            prawduct,
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 01: Setup\n\n"
            "- **Description:** adds `parse_func` helper to `tools/product-hook`.\n",
        )
        mod = _load_product_hook()
        refs = mod._parse_build_plan_chunk_refs(prawduct, "01")
        paths = [r["ref"] for r in refs["file_paths"]]
        assert "tools/product-hook" in paths
        assert "parse_func" not in paths

    def test_ignores_slash_command_tokens(self, tmp_path: Path):
        """Backticked slash-commands (`/pr`, `/learnings`, `/critic`) contain
        `/` but are not file paths — single-segment identifiers starting with
        `/`. They must not be extracted as path refs (else they produce
        BLOCKING ref-drift false-positives against legitimate chunk prose
        that references framework skills)."""
        prawduct = tmp_path / ".prawduct"
        self._write_plan(
            prawduct,
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 01: Setup\n\n"
            "- **Description:** `/pr` skill blocks creation; run `/learnings`"
            " before `/critic`. Touches `tools/product-hook`.\n",
        )
        mod = _load_product_hook()
        refs = mod._parse_build_plan_chunk_refs(prawduct, "01")
        paths = [r["ref"] for r in refs["file_paths"]]
        assert "tools/product-hook" in paths
        assert "/pr" not in paths
        assert "/learnings" not in paths
        assert "/critic" not in paths

    def test_keeps_absolute_paths_with_structure(self, tmp_path: Path):
        """The slash-command exclusion must not over-match: absolute paths
        like `/etc/foo.conf` (further `/`) and `/file.md` (has `.`) are
        still file paths and should be extracted (and reported missing if
        they don't exist)."""
        prawduct = tmp_path / ".prawduct"
        self._write_plan(
            prawduct,
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 01: Setup\n\n"
            "- **Description:** reads `/etc/foo.conf` and writes `/file.md`.\n",
        )
        mod = _load_product_hook()
        refs = mod._parse_build_plan_chunk_refs(prawduct, "01")
        paths = [r["ref"] for r in refs["file_paths"]]
        assert "/etc/foo.conf" in paths
        assert "/file.md" in paths


class TestVerifyChunkRefsSubcommand:
    """The `verify-chunk-refs [chunk_id]` subcommand drives the Critic's
    Goal-2 symbol-reference check. Exit 0 = all refs exist; exit 1 = at
    least one ref is missing or the gate cannot be evaluated.

    Without an explicit `chunk_id`, uses the current chunk from Status
    (first `- [ ]` item, mirroring `_parse_build_plan_status`).
    """

    def _make_project(self, tmp_path: Path) -> Path:
        prawduct = tmp_path / ".prawduct"
        (prawduct / "artifacts").mkdir(parents=True)
        return prawduct

    def test_all_refs_exist_exit_zero(self, tmp_path: Path):
        prawduct = self._make_project(tmp_path)
        (tmp_path / "real.md").write_text("content")
        (prawduct / "artifacts" / "build-plan.md").write_text(
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 01: Setup\n\n"
            "- **Description:** modifies `real.md`.\n",
        )
        result = run_hook("verify-chunk-refs", tmp_path, git_output="")
        # With no current chunk in Status (only Build Chunks section), the
        # gate would skip — so pass chunk_id explicitly via stdin? Better:
        # Use stop-style env. The subcommand accepts chunk_id as second arg.
        # Retry with explicit chunk_id.
        env_extra = {"PRAWDUCT_VERIFY_CHUNK_ID": "01"}
        result = run_hook(
            "verify-chunk-refs",
            tmp_path,
            git_output="",
            env_extra=env_extra,
        )
        assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"

    def test_bogus_file_path_exit_one(self, tmp_path: Path):
        prawduct = self._make_project(tmp_path)
        (prawduct / "artifacts" / "build-plan.md").write_text(
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 01: Setup\n\n"
            "- **Description:** modifies `does/not/exist.md`.\n",
        )
        result = run_hook(
            "verify-chunk-refs",
            tmp_path,
            git_output="",
            env_extra={"PRAWDUCT_VERIFY_CHUNK_ID": "01"},
        )
        assert result.returncode == 1
        assert "does/not/exist.md" in result.stderr

    def test_forward_ref_in_other_chunk_not_flagged(self, tmp_path: Path):
        """A bogus path in Chunk 02's section must not fail the Chunk 01 gate."""
        prawduct = self._make_project(tmp_path)
        (tmp_path / "real.md").write_text("content")
        (prawduct / "artifacts" / "build-plan.md").write_text(
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 01: First\n\n"
            "- **Description:** modifies `real.md`.\n\n"
            "### Chunk 02: Future\n\n"
            "- **Description:** will create `future/thing.md`.\n",
        )
        result = run_hook(
            "verify-chunk-refs",
            tmp_path,
            git_output="",
            env_extra={"PRAWDUCT_VERIFY_CHUNK_ID": "01"},
        )
        assert result.returncode == 0, f"stderr={result.stderr!r}"

    def test_new_qualifier_skipped(self, tmp_path: Path):
        """Paths preceded by 'new' aren't expected to exist."""
        prawduct = self._make_project(tmp_path)
        (prawduct / "artifacts" / "build-plan.md").write_text(
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 01: Setup\n\n"
            "- **Deliverables:** new `creates/this.md`: details.\n",
        )
        result = run_hook(
            "verify-chunk-refs",
            tmp_path,
            git_output="",
            env_extra={"PRAWDUCT_VERIFY_CHUNK_ID": "01"},
        )
        assert result.returncode == 0, f"stderr={result.stderr!r}"

    def test_no_build_plan_exit_one(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        result = run_hook(
            "verify-chunk-refs",
            tmp_path,
            git_output="",
            env_extra={"PRAWDUCT_VERIFY_CHUNK_ID": "01"},
        )
        assert result.returncode == 1
        assert "build-plan" in result.stderr.lower() or "missing" in result.stderr.lower()

    def test_uses_current_chunk_when_id_omitted(self, tmp_path: Path):
        """Without an explicit ID, the subcommand reads Status' first `- [ ]`."""
        prawduct = self._make_project(tmp_path)
        (prawduct / "artifacts" / "build-plan.md").write_text(
            "# Build Plan\n\n## Status\n\n"
            "- [x] Chunk 01: Done\n"
            "- [ ] Chunk 02: Current\n\n"
            "## Build Chunks\n\n"
            "### Chunk 01: Done\n- **Description:** nothing.\n\n"
            "### Chunk 02: Current\n\n"
            "- **Description:** modifies `does/not/exist.md`.\n",
        )
        result = run_hook(
            "verify-chunk-refs",
            tmp_path,
            git_output="",
        )
        assert result.returncode == 1
        assert "does/not/exist.md" in result.stderr

    def test_no_active_chunk_exit_zero(self, tmp_path: Path):
        """No chunk_id given and no Status section (or all complete) → nothing
        to check. Exit 0 (gate is moot, not violated)."""
        prawduct = self._make_project(tmp_path)
        (prawduct / "artifacts" / "build-plan.md").write_text(
            "# Build Plan\n\n## Status\n\n- [x] Chunk 01: All done\n",
        )
        result = run_hook(
            "verify-chunk-refs",
            tmp_path,
            git_output="",
        )
        assert result.returncode == 0, f"stderr={result.stderr!r}"


# =============================================================================
# v1.4 Chunk 03 (F6) — chunk-Type declaration parser
# =============================================================================


class TestParseBuildPlanChunkType:
    """`_parse_build_plan_chunk_type` extracts the `Type:` declaration from a
    single chunk's `### Chunk NN:` section. Allowed values:
      code | doc-only | cleanup | designer-handoff | cumulative-final.
    Default (field absent) is ``code`` — fail closed per learnings rule
    "escape hatches in classification create silent failures" — a missing
    field gets the full Critic protocol, never the carveout.
    Unknown values are surfaced as an error so the builder fixes the typo
    rather than silently falling through.
    """

    def _write_plan(self, prawduct: Path, body: str) -> Path:
        artifacts = prawduct / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        path = artifacts / "build-plan.md"
        path.write_text(body)
        return path

    def test_extracts_type_code(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        self._write_plan(
            prawduct,
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 01: Setup\n\n"
            "- **Description:** something.\n"
            "- **Type:** code\n",
        )
        mod = _load_product_hook()
        chunk_type, error = mod._parse_build_plan_chunk_type(prawduct, "01")
        assert chunk_type == "code"
        assert error is None

    def test_extracts_type_doc_only(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        self._write_plan(
            prawduct,
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 04: Methodology edit\n\n"
            "- **Type:** doc-only (no executable code changes)\n",
        )
        mod = _load_product_hook()
        chunk_type, error = mod._parse_build_plan_chunk_type(prawduct, "04")
        # Trailing parenthetical prose must not corrupt the type token.
        assert chunk_type == "doc-only"
        assert error is None

    def test_extracts_type_designer_handoff(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        self._write_plan(
            prawduct,
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 07: Visual polish\n\n"
            "- **Type:** designer-handoff\n",
        )
        mod = _load_product_hook()
        chunk_type, error = mod._parse_build_plan_chunk_type(prawduct, "07")
        assert chunk_type == "designer-handoff"
        assert error is None

    def test_missing_type_defaults_to_code(self, tmp_path: Path):
        """Omitted Type field is the most common case — must default to the
        most-thorough protocol (code). This is the fail-closed contract that
        prevents accidental Critic-skip."""
        prawduct = tmp_path / ".prawduct"
        self._write_plan(
            prawduct,
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 01: Setup\n\n"
            "- **Description:** something.\n"
            "- **Depends on:** none\n",
        )
        mod = _load_product_hook()
        chunk_type, error = mod._parse_build_plan_chunk_type(prawduct, "01")
        assert chunk_type == "code"
        assert error is None

    def test_unknown_type_returns_error(self, tmp_path: Path):
        """Unknown values are typos or stale conventions — surface them
        explicitly so the author fixes the field, don't silently default."""
        prawduct = tmp_path / ".prawduct"
        self._write_plan(
            prawduct,
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 01: Setup\n\n"
            "- **Type:** wibble\n",
        )
        mod = _load_product_hook()
        chunk_type, error = mod._parse_build_plan_chunk_type(prawduct, "01")
        assert chunk_type is None
        assert error is not None
        assert "wibble" in error.lower()

    def test_excludes_sibling_chunk_type(self, tmp_path: Path):
        """A Type declaration in Chunk 02 must NOT bleed into Chunk 01."""
        prawduct = tmp_path / ".prawduct"
        self._write_plan(
            prawduct,
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 01: First\n\n"
            "- **Description:** no type declared.\n\n"
            "### Chunk 02: Second\n\n"
            "- **Type:** doc-only\n",
        )
        mod = _load_product_hook()
        chunk_type, error = mod._parse_build_plan_chunk_type(prawduct, "01")
        assert chunk_type == "code"
        assert error is None

    def test_missing_chunk_returns_error(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        self._write_plan(
            prawduct,
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 01: Only one\n\n- **Type:** code\n",
        )
        mod = _load_product_hook()
        chunk_type, error = mod._parse_build_plan_chunk_type(prawduct, "99")
        assert chunk_type is None
        assert error is not None
        assert "99" in error or "not found" in error.lower()

    def test_missing_build_plan_returns_error(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        mod = _load_product_hook()
        chunk_type, error = mod._parse_build_plan_chunk_type(prawduct, "01")
        assert chunk_type is None
        assert error is not None
        assert "build-plan" in error.lower() or "missing" in error.lower()

    def test_leading_zeros_tolerant(self, tmp_path: Path):
        """`02` and `2` resolve to the same chunk — matches Chunk 02's
        ref-parser convention."""
        prawduct = tmp_path / ".prawduct"
        self._write_plan(
            prawduct,
            "# Build Plan\n\n## Build Chunks\n\n"
            "### Chunk 2: Match by number\n\n"
            "- **Type:** cleanup\n",
        )
        mod = _load_product_hook()
        chunk_type, error = mod._parse_build_plan_chunk_type(prawduct, "02")
        assert chunk_type == "cleanup"
        assert error is None


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
        assert "Place-once template advisories:" in briefing
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

    def test_briefing_shows_sync_pending_marker(self, tmp_path: Path):
        """F5a — when sync skipped auto-commit, the marker surfaces in briefing."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "work_in_progress:\n  description: null\n  size: null\n  type: null\n"
            "\nbuild_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )
        (prawduct / ".sync-pending").write_text(json.dumps({
            "reason": "branch 'main' is protected",
            "blocked_by": ["branch 'main' is protected"],
            "version": "1.3.17",
            "ts": "2026-05-19T18:00:00Z",
        }))

        import importlib.util
        import importlib.machinery
        loader = importlib.machinery.SourceFileLoader("product_hook", str(HOOK_PATH))
        spec = importlib.util.spec_from_loader("product_hook", loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        briefing = mod.assemble_session_briefing(tmp_path, [])
        assert "Framework sync pending" in briefing
        assert "branch 'main' is protected" in briefing
        assert "v1.3.17" in briefing

    def test_briefing_no_sync_pending_when_marker_absent(self, tmp_path: Path):
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
        assert "Framework sync pending" not in briefing

    def test_briefing_handles_corrupt_sync_pending(self, tmp_path: Path):
        """Marker file with invalid JSON must not crash briefing assembly."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "MyApp"\n\n'
            "work_in_progress:\n  description: null\n  size: null\n  type: null\n"
            "\nbuild_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
        )
        (prawduct / ".sync-pending").write_text("not json{{")

        import importlib.util
        import importlib.machinery
        loader = importlib.machinery.SourceFileLoader("product_hook", str(HOOK_PATH))
        spec = importlib.util.spec_from_loader("product_hook", loader)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        briefing = mod.assemble_session_briefing(tmp_path, [])
        # Fallback line points the user at the file rather than crashing.
        assert "Framework sync pending" in briefing
        assert "unreadable" in briefing

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


# =============================================================================
# Framework freshness — structured briefing facts
# =============================================================================


def _load_hook_module():
    """Load product-hook (no .py extension) as a module for direct testing."""
    import importlib.util
    import importlib.machinery
    loader = importlib.machinery.SourceFileLoader("product_hook", str(HOOK_PATH))
    spec = importlib.util.spec_from_loader("product_hook", loader)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _basic_project_state(prawduct_dir: Path) -> None:
    """Minimal project-state.yaml so the briefing can render."""
    prawduct_dir.mkdir(exist_ok=True)
    (prawduct_dir / "project-state.yaml").write_text(
        'product_identity:\n  name: "MyApp"\n\n'
        "work_in_progress:\n  description: null\n  size: null\n  type: null\n"
        "\nbuild_state:\n  source_root: null\n  test_tracking:\n    test_count: 0\n"
    )


class TestComputeFrameworkFreshness:
    """_compute_framework_freshness extracts structured drift facts from
    sync-manifest.json and (when available) the framework dir."""

    def test_returns_none_when_no_manifest(self, tmp_path: Path):
        mod = _load_hook_module()
        # No .prawduct/sync-manifest.json exists
        assert mod._compute_framework_freshness(tmp_path, "") is None

    def test_extracts_sync_data_from_manifest(self, tmp_path: Path):
        mod = _load_hook_module()
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        manifest = {
            "format_version": 2,
            "last_sync": "2026-04-23T22:13:36Z",
            "framework_version": "1.3.10",
            "framework_commit": "bc44003",
        }
        (prawduct / "sync-manifest.json").write_text(json.dumps(manifest))

        result = mod._compute_framework_freshness(tmp_path, "")
        assert result["last_sync_date"] == "2026-04-23"
        assert result["last_sync_version"] == "1.3.10"
        assert result["last_sync_commit"] == "bc44003"
        # Without fw_dir, framework_* fields and commits_behind stay None
        assert result["framework_head"] is None
        assert result["framework_version"] is None
        assert result["commits_behind"] is None

    def test_handles_legacy_manifest_without_commit(self, tmp_path: Path):
        mod = _load_hook_module()
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        # Manifest predates framework_commit field
        manifest = {
            "format_version": 2,
            "last_sync": "2026-04-23T22:13:36Z",
            "framework_version": "1.3.10",
        }
        (prawduct / "sync-manifest.json").write_text(json.dumps(manifest))

        result = mod._compute_framework_freshness(tmp_path, "")
        assert result["last_sync_commit"] is None

    def test_returns_none_for_malformed_manifest(self, tmp_path: Path):
        mod = _load_hook_module()
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "sync-manifest.json").write_text("{ this is not valid json")
        assert mod._compute_framework_freshness(tmp_path, "") is None


class TestBriefingFreshnessBlock:
    """The structured 'Framework freshness:' block in the session briefing —
    surfaces only when there's actual drift to reason about."""

    def test_no_block_when_in_sync(self, tmp_path: Path):
        _basic_project_state(tmp_path / ".prawduct")
        mod = _load_hook_module()
        freshness = {
            "framework_head": "abc1234",
            "framework_head_date": "2026-05-01",
            "framework_version": "1.3.10",
            "last_sync_date": "2026-05-01",
            "last_sync_version": "1.3.10",
            "last_sync_commit": "abc1234",
            "commits_behind": 0,
        }
        briefing = mod.assemble_session_briefing(tmp_path, [], freshness=freshness, advisories=[])
        assert "Framework freshness:" not in briefing

    def test_block_shown_when_commits_behind(self, tmp_path: Path):
        _basic_project_state(tmp_path / ".prawduct")
        mod = _load_hook_module()
        freshness = {
            "framework_head": "5885600",
            "framework_head_date": "2026-05-01",
            "framework_version": "1.3.10",
            "last_sync_date": "2026-04-23",
            "last_sync_version": "1.3.10",
            "last_sync_commit": "bc44003",
            "commits_behind": 1,
        }
        briefing = mod.assemble_session_briefing(tmp_path, [], freshness=freshness, advisories=[])
        assert "Framework freshness:" in briefing
        assert "5885600" in briefing
        assert "bc44003" in briefing
        assert "1 commit(s) since sync" in briefing
        # Versions match — no version-delta line
        assert "Version delta" not in briefing

    def test_block_shows_version_delta_when_versions_differ(self, tmp_path: Path):
        _basic_project_state(tmp_path / ".prawduct")
        mod = _load_hook_module()
        freshness = {
            "framework_head": "abc1234",
            "framework_head_date": "2026-05-01",
            "framework_version": "1.3.11",
            "last_sync_date": "2026-04-23",
            "last_sync_version": "1.3.10",
            "last_sync_commit": "bc44003",
            "commits_behind": 5,
        }
        briefing = mod.assemble_session_briefing(tmp_path, [], freshness=freshness, advisories=[])
        assert "Version delta" in briefing
        assert "v1.3.10" in briefing
        assert "v1.3.11" in briefing

    def test_block_renders_place_once_advisories_with_commit_info(self, tmp_path: Path):
        _basic_project_state(tmp_path / ".prawduct")
        mod = _load_hook_module()
        freshness = {
            "framework_head": "5885600",
            "framework_head_date": "2026-05-01",
            "framework_version": "1.3.10",
            "last_sync_date": "2026-04-23",
            "last_sync_version": "1.3.10",
            "last_sync_commit": "bc44003",
            "commits_behind": 1,
        }
        advisories = [
            {
                "type": "template_drift",
                "file": ".prawduct/artifacts/project-preferences.md",
                "template": "templates/project-preferences.md",
                "message": "msg",
                "last_changed_commit": "5885600",
                "last_changed_date": "2026-05-01",
                "last_changed_subject": "Preference enforcement framework",
            }
        ]
        briefing = mod.assemble_session_briefing(
            tmp_path, [], freshness=freshness, advisories=advisories
        )
        assert "Place-once template advisories: 1" in briefing
        assert "project-preferences.md" in briefing
        assert "5885600" in briefing
        assert "Preference enforcement framework" in briefing

    def test_legacy_manifest_shows_unknown_commit_delta(self, tmp_path: Path):
        """When manifest predates commit tracking, the block still renders
        for advisories but the commit delta is reported as unknown."""
        _basic_project_state(tmp_path / ".prawduct")
        mod = _load_hook_module()
        freshness = {
            "framework_head": "5885600",
            "framework_head_date": "2026-05-01",
            "framework_version": "1.3.10",
            "last_sync_date": "2026-04-23",
            "last_sync_version": "1.3.10",
            "last_sync_commit": None,  # legacy manifest
            "commits_behind": None,
        }
        advisories = [
            {
                "type": "template_drift",
                "file": ".prawduct/artifacts/project-preferences.md",
                "template": "templates/project-preferences.md",
                "message": "msg",
                "last_changed_commit": "",
                "last_changed_date": "",
                "last_changed_subject": "",
            }
        ]
        briefing = mod.assemble_session_briefing(
            tmp_path, [], freshness=freshness, advisories=advisories
        )
        assert "Framework freshness:" in briefing
        assert "manifest predates commit tracking" in briefing

    def test_falls_back_when_freshness_is_none_but_advisories_present(self, tmp_path: Path):
        """Backward-compat path: when freshness can't be computed but advisories
        exist, render the simple advisory list rather than dropping it."""
        _basic_project_state(tmp_path / ".prawduct")
        mod = _load_hook_module()
        advisories = [{"file": "X", "message": "X drifted"}]
        briefing = mod.assemble_session_briefing(
            tmp_path, [], advisories=advisories, freshness=None
        )
        assert "Place-once template advisories: 1 template(s)" in briefing
        assert "X drifted" in briefing


# =============================================================================
# v1.4 Chunk 09 (F4b) — verify-coverage subcommand
# =============================================================================


def _vc_git(cwd: Path, *args: str) -> None:
    """Run a real git command in `cwd`. Mirrors the helper in
    test_reference_verifier.py — verify-coverage runs `git diff` and
    `git ls-files` against a live work tree, so mocking would not exercise
    the real interaction."""
    env = os.environ.copy()
    env.setdefault("GIT_AUTHOR_NAME", "test")
    env.setdefault("GIT_AUTHOR_EMAIL", "test@example.com")
    env.setdefault("GIT_COMMITTER_NAME", "test")
    env.setdefault("GIT_COMMITTER_EMAIL", "test@example.com")
    subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        env=env,
        check=True,
        capture_output=True,
    )


def _vc_run(repo: Path) -> subprocess.CompletedProcess:
    """Invoke `product-hook verify-coverage` in `repo` with a real git on
    PATH. CLAUDE_PROJECT_DIR overrides the cwd resolution so the hook
    operates on the test repo instead of the parent project."""
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    return subprocess.run(
        ["python3", str(HOOK_PATH), "verify-coverage"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def _vc_write_evidence(repo: Path, fields: dict) -> None:
    """Write a v1.4 F4a-shaped evidence file under .prawduct/."""
    base = {
        "timestamp": "2026-05-19T14:00:00Z",
        "command": "python3 -m pytest -q",
        "passed": 1,
        "failed": 0,
        "skipped": 0,
        "duration_seconds": 1.0,
    }
    base.update(fields)
    (repo / ".prawduct" / ".test-evidence.json").write_text(json.dumps(base))


@pytest.fixture
def vc_repo(tmp_path: Path) -> Path:
    """Baseline repo mirroring a real product layout:
      - `.gitignore` excludes per-session artifact files,
      - `.prawduct/project-state.yaml` committed as a tracked baseline,
      - `src/a.py` + `tests/test_a.py` committed.

    Subsequent tests mutate `project-state.yaml` and add or modify files;
    `.test-evidence.json` is always written but never shows in the diff
    (gitignored), matching the real-world layout the check is designed
    for."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _vc_git(repo, "init", "-b", "main")
    (repo / ".prawduct").mkdir()
    (repo / ".gitignore").write_text(
        ".prawduct/.test-evidence.json\n"
        ".prawduct/.critic-findings.json\n"
    )
    (repo / ".prawduct" / "project-state.yaml").write_text(
        "# baseline state — coverage off\n"
    )
    (repo / "src").mkdir()
    (repo / "src" / "a.py").write_text("def a_helper():\n    return 1\n")
    (repo / "tests").mkdir()
    (repo / "tests" / "test_a.py").write_text(
        "from src.a import a_helper\n\n"
        "def test_a_helper():\n"
        "    assert a_helper() == 1\n"
    )
    _vc_git(repo, "add", ".")
    _vc_git(repo, "commit", "-m", "baseline")
    return repo


class TestVerifyCoverageSubcommand:
    """`verify-coverage` is the Critic Goal-1 helper for v1.4 F4b. When
    `coverage_required: true` in project-state.yaml, it cross-checks the
    diff (uncommitted + untracked) against `.test-evidence.json`'s
    `changes_referenced` list and emits per-file findings scaled to the
    declared `coverage_level`. Off by default to preserve v1.3.x behavior."""

    def test_skipped_when_coverage_required_false(self, vc_repo: Path):
        """Default v1.4 state — explicit `coverage_required: false` — exits 0
        with an explanatory message. The check is opt-in by design (the v1.4
        compat strategy depends on this skip-by-default behavior; framework
        sync flipping the flag would surprise downstream products)."""
        (vc_repo / ".prawduct" / "project-state.yaml").write_text(
            "coverage_required: false\n"
        )
        result = _vc_run(vc_repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "skipped" in result.stdout.lower()
        assert "coverage_required" in result.stdout

    def test_skipped_when_coverage_required_key_absent(self, vc_repo: Path):
        """Missing `coverage_required` key behaves like `false` — opt-in
        means no key = no enforcement."""
        (vc_repo / ".prawduct" / "project-state.yaml").write_text(
            "# no coverage_required key here\n"
        )
        result = _vc_run(vc_repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "skipped" in result.stdout.lower()

    def test_indented_coverage_required_does_not_satisfy_flag(self, vc_repo: Path):
        """A `coverage_required: true` line indented under another YAML key
        is NOT a top-level setting. Mirrors the column-0 discipline of
        `is_views_enabled` — a stray nested key must not silently turn
        enforcement on for the whole project."""
        (vc_repo / ".prawduct" / "project-state.yaml").write_text(
            "some_section:\n  coverage_required: true\n"
        )
        result = _vc_run(vc_repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "skipped" in result.stdout.lower()

    def test_missing_evidence_file_errors(self, vc_repo: Path):
        """Opt-in but no evidence file → exit 1 with actionable message."""
        (vc_repo / ".prawduct" / "project-state.yaml").write_text(
            "coverage_required: true\n"
        )
        result = _vc_run(vc_repo)
        assert result.returncode == 1
        assert ".test-evidence.json" in result.stderr
        assert "missing" in result.stderr.lower()

    def test_legacy_evidence_without_verifier_errors(self, vc_repo: Path):
        """Opt-in but evidence is legacy fingerprint-only (no `verifier`
        field) → exit 1 telling the user to run the verifier. The legacy
        skip-on-no-verifier path is intentional for v1.4 dogfooding (no
        breakage at chunk boundary 08→09 for products that opt in before
        plugging in a verifier)."""
        (vc_repo / ".prawduct" / "project-state.yaml").write_text(
            "coverage_required: true\n"
        )
        _vc_write_evidence(vc_repo, {})  # no F4a fields
        result = _vc_run(vc_repo)
        assert result.returncode == 1
        assert "verifier" in result.stderr
        assert "F4a" in result.stderr or "schema" in result.stderr.lower()

    def test_invalid_evidence_schema_errors(self, vc_repo: Path):
        """Verifier present but other F4a fields missing → schema validator
        fires, exit 1. Guards against partial writes / typos in
        product-supplied verifiers."""
        (vc_repo / ".prawduct" / "project-state.yaml").write_text(
            "coverage_required: true\n"
        )
        _vc_write_evidence(vc_repo, {"verifier": "broken"})  # missing other fields
        result = _vc_run(vc_repo)
        assert result.returncode == 1
        assert "schema" in result.stderr.lower() or "missing" in result.stderr.lower()

    def test_all_changes_covered_exit_zero(self, vc_repo: Path):
        """When every changed file appears in `changes_referenced`, exit 0.
        Modifying both `src/a.py` and `project-state.yaml` puts both in the
        diff; both must be listed for the check to pass."""
        (vc_repo / "src" / "a.py").write_text(
            "def a_helper():\n    return 2  # changed\n"
        )
        (vc_repo / ".prawduct" / "project-state.yaml").write_text(
            "coverage_required: true\n"
        )
        _vc_write_evidence(
            vc_repo,
            {
                "verifier": "test-reference-verify (floor: symbol-grep)",
                "coverage_level": "referenced",
                "tests_executed": ["tests/test_a.py"],
                "changes_referenced": [
                    "src/a.py",
                    ".prawduct/project-state.yaml",
                ],
            },
        )
        result = _vc_run(vc_repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "ok" in result.stdout.lower()
        assert "referenced" in result.stdout

    def test_missing_at_referenced_level_emits_floor_language(self, vc_repo: Path):
        """A changed file not in `changes_referenced` at the floor level
        produces BLOCKING-eligible stderr quoting the floor caveat — the
        Critic must not present floor results as proof of execution."""
        (vc_repo / "src" / "b.py").write_text("def b_helper():\n    return 1\n")
        (vc_repo / ".prawduct" / "project-state.yaml").write_text(
            "coverage_required: true\n"
        )
        _vc_write_evidence(
            vc_repo,
            {
                "verifier": "test-reference-verify (floor: symbol-grep)",
                "coverage_level": "referenced",
                "tests_executed": ["tests/test_a.py"],
                "changes_referenced": [],  # b.py is NOT covered
            },
        )
        result = _vc_run(vc_repo)
        assert result.returncode == 1
        assert "missing-coverage: src/b.py" in result.stderr
        assert "coverage_level: referenced" in result.stderr
        assert "floor check" in result.stderr
        assert "does not prove execution" in result.stderr

    def test_missing_at_executed_level_emits_executing_language(self, vc_repo: Path):
        """Same setup, `coverage_level: executed` → stronger language. The
        per-level wording is the chunk's whole point: the floor must not
        sound like executed coverage, and a real coverage tool must not
        be hedged the way the floor must be."""
        (vc_repo / "src" / "b.py").write_text("def b_helper():\n    return 1\n")
        (vc_repo / ".prawduct" / "project-state.yaml").write_text(
            "coverage_required: true\n"
        )
        _vc_write_evidence(
            vc_repo,
            {
                "verifier": "coverage.py --branch",
                "coverage_level": "executed",
                "tests_executed": ["tests/test_a.py"],
                "changes_referenced": [],
            },
        )
        result = _vc_run(vc_repo)
        assert result.returncode == 1
        assert "missing-coverage: src/b.py" in result.stderr
        assert "coverage_level: executed" in result.stderr
        assert "has no executing test" in result.stderr
        # Floor language MUST NOT appear at executed level — that would
        # erase the distinction the chunk introduces.
        assert "floor check" not in result.stderr

    def test_multiple_missing_files_listed_individually(self, vc_repo: Path):
        """One stderr line per missing file, so the Critic can quote each in
        a separate finding (matches `verify-chunk-refs`' per-ref pattern)."""
        (vc_repo / "src" / "b.py").write_text("def b():\n    return 1\n")
        (vc_repo / "src" / "c.py").write_text("def c():\n    return 1\n")
        (vc_repo / ".prawduct" / "project-state.yaml").write_text(
            "coverage_required: true\n"
        )
        _vc_write_evidence(
            vc_repo,
            {
                "verifier": "test-reference-verify (floor: symbol-grep)",
                "coverage_level": "referenced",
                "tests_executed": ["tests/test_a.py"],
                "changes_referenced": [],
            },
        )
        result = _vc_run(vc_repo)
        assert result.returncode == 1
        assert "missing-coverage: src/b.py" in result.stderr
        assert "missing-coverage: src/c.py" in result.stderr
        missing_lines = [
            line for line in result.stderr.splitlines()
            if line.startswith("missing-coverage:")
        ]
        assert len(missing_lines) >= 2

    def test_untracked_file_treated_as_missing(self, vc_repo: Path):
        """Untracked files (not yet `git add`-ed) must be picked up — they
        are precisely the silent-failure mode (new code with no test
        reference) the gate exists to catch. Mirrors the verifier's
        diff∪ls-files union."""
        (vc_repo / "src" / "untracked.py").write_text("def x():\n    return 1\n")
        (vc_repo / ".prawduct" / "project-state.yaml").write_text(
            "coverage_required: true\n"
        )
        _vc_write_evidence(
            vc_repo,
            {
                "verifier": "test-reference-verify (floor: symbol-grep)",
                "coverage_level": "referenced",
                "tests_executed": ["tests/test_a.py"],
                "changes_referenced": [],
            },
        )
        result = _vc_run(vc_repo)
        assert result.returncode == 1
        assert "src/untracked.py" in result.stderr

    def test_no_changes_exit_zero(self, vc_repo: Path):
        """A clean working tree (no uncommitted diff, no untracked files
        outside `.gitignore`) → exit 0 with `ok: 0 changed`. Enabling the
        flag is itself a tracked-file change, so this test commits the
        flag-flip first and then re-runs the check against the now-clean
        tree."""
        (vc_repo / ".prawduct" / "project-state.yaml").write_text(
            "coverage_required: true\n"
        )
        _vc_git(vc_repo, "add", ".prawduct/project-state.yaml")
        _vc_git(vc_repo, "commit", "-m", "enable coverage_required")
        _vc_write_evidence(
            vc_repo,
            {
                "verifier": "test-reference-verify (floor: symbol-grep)",
                "coverage_level": "referenced",
                "tests_executed": [],
                "changes_referenced": [],
            },
        )
        result = _vc_run(vc_repo)
        assert result.returncode == 0, f"stderr={result.stderr!r}"
        assert "ok" in result.stdout.lower()

    def test_unresolvable_base_errors(self, tmp_path: Path):
        """No git history (empty repo, no commits) → no diff base resolves;
        verify-coverage exits 1 with a diagnostic. Fail-loud beats a green
        report on a repo with nothing to compare against."""
        repo = tmp_path / "empty"
        repo.mkdir()
        _vc_git(repo, "init", "-b", "main")
        (repo / ".prawduct").mkdir()
        (repo / ".prawduct" / "project-state.yaml").write_text(
            "coverage_required: true\n"
        )
        _vc_write_evidence(
            repo,
            {
                "verifier": "test-reference-verify (floor: symbol-grep)",
                "coverage_level": "referenced",
                "tests_executed": [],
                "changes_referenced": [],
            },
        )
        result = _vc_run(repo)
        assert result.returncode == 1
        assert "base" in result.stderr.lower()

