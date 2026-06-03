"""Tests for the plugin runtime's PR-review gate + PR-review prose.

Covers the stop-hook PR-review-evidence gate (bin/prawduct-hook stop) and the
PR-reviewer template/skill content. The file-sync init/sync/manifest behavior
(prawduct-setup.py) retired with the engine in M4.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / "bin" / "prawduct-hook"
FRAMEWORK_DIR = REPO_ROOT


# =============================================================================
# Helpers
# =============================================================================


def run_hook(
    command: str,
    project_dir: Path,
    *,
    git_output: str | None = "",
    git_script: str | None = None,
    gh_script_body: str | None = None,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run the plugin runtime (bin/prawduct-hook) with controlled mocks for git and gh.

    If git_script is provided, it's used as the full git mock script body.
    Otherwise a basic git mock is generated from git_output.
    """
    env = {
        "HOME": str(project_dir),
        "CLAUDE_PROJECT_DIR": str(project_dir),
        "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT),
        "PATH": "",
    }

    mock_bin = project_dir / "_mock_bin"
    mock_bin.mkdir(exist_ok=True)

    if git_script is not None:
        mock_git = mock_bin / "git"
        mock_git.write_text("#!/bin/bash\n" + git_script + "\nexit 0\n")
        mock_git.chmod(0o755)
    elif git_output is not None:
        mock_git = mock_bin / "git"
        # Build script line by line to avoid f-string + dedent issues
        lines = [
            "#!/bin/bash",
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            f'if [[ "$1" == "status" ]]; then printf \'%s\' \'{git_output}\'; exit 0; fi',
            "exit 0",
        ]
        mock_git.write_text("\n".join(lines) + "\n")
        mock_git.chmod(0o755)

    if gh_script_body is not None:
        gh_script = mock_bin / "gh"
        gh_script.write_text("#!/bin/bash\n" + gh_script_body + "\nexit 0\n")
        gh_script.chmod(0o755)

    env["PATH"] = str(mock_bin) + ":/usr/bin:/bin:/usr/sbin:/sbin"

    if env_extra:
        env.update(env_extra)

    return subprocess.run(
        ["python3", str(HOOK_PATH), command],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )


# =============================================================================
# Hook: Stop gate for PR review evidence
# =============================================================================


class TestStopPrReviewGate:
    def test_stop_clean_without_pr(self, tmp_path: Path):
        """Stop hook exits clean when there's no PR."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        result = run_hook("stop", tmp_path, git_output="")
        assert result.returncode == 0

    def test_stop_with_pr_no_evidence_blocks(self, tmp_path: Path):
        """When a PR exists but no review evidence, stop should BLOCK."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        git_script = "\n".join([
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            'if [[ "$1" == "status" ]]; then printf ""; exit 0; fi',
            'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "feature/test-pr"; exit 0; fi',
        ])

        gh_script = "\n".join([
            'if [[ "$1" == "pr" && "$2" == "list" ]]; then echo \'[{"number": 42}]\'; exit 0; fi',
        ])

        result = run_hook(
            "stop", tmp_path,
            git_script=git_script,
            gh_script_body=gh_script,
        )
        # PR without evidence is now a blocker, not advisory
        assert result.returncode == 2
        assert "PR REVIEW" in result.stderr
        assert "PR exists for branch" in result.stderr or "no review evidence" in result.stderr

    def test_stop_with_pr_and_evidence_no_warning(self, tmp_path: Path):
        """When PR exists AND review evidence exists, no warning."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        reviews_dir = prawduct / ".pr-reviews"
        reviews_dir.mkdir()
        evidence = reviews_dir / "feature--test-pr.json"
        evidence.write_text(json.dumps({
            "timestamp": "2026-03-17T14:00:00Z",
            "branch": "feature/test-pr",
            "base": "main",
            "pr_number": 42,
            "findings": [],
            "summary": "No issues found.",
        }))

        git_script = "\n".join([
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            'if [[ "$1" == "status" ]]; then printf ""; exit 0; fi',
            'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "feature/test-pr"; exit 0; fi',
        ])

        gh_script = "\n".join([
            'if [[ "$1" == "pr" && "$2" == "list" ]]; then echo \'[{"number": 42}]\'; exit 0; fi',
        ])

        result = run_hook(
            "stop", tmp_path,
            git_script=git_script,
            gh_script_body=gh_script,
        )
        assert result.returncode == 0
        # No PR review blocker expected
        assert "PR REVIEW" not in result.stderr

    def test_stop_with_pr_and_malformed_json_blocks(self, tmp_path: Path):
        """When evidence file has malformed JSON, stop should block."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        reviews_dir = prawduct / ".pr-reviews"
        reviews_dir.mkdir()
        evidence = reviews_dir / "feature--test-pr.json"
        evidence.write_text("not valid json {{{")

        git_script = "\n".join([
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            'if [[ "$1" == "status" ]]; then printf ""; exit 0; fi',
            'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "feature/test-pr"; exit 0; fi',
        ])
        gh_script = "\n".join([
            'if [[ "$1" == "pr" && "$2" == "list" ]]; then echo \'[{"number": 42}]\'; exit 0; fi',
        ])

        result = run_hook("stop", tmp_path, git_script=git_script, gh_script_body=gh_script)
        assert result.returncode == 2
        assert "PR REVIEW" in result.stderr

    def test_stop_with_pr_and_evidence_missing_findings_blocks(self, tmp_path: Path):
        """When evidence file is missing 'findings' key, stop should block."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        reviews_dir = prawduct / ".pr-reviews"
        reviews_dir.mkdir()
        evidence = reviews_dir / "feature--test-pr.json"
        evidence.write_text(json.dumps({"summary": "No issues.", "branch": "feature/test-pr"}))

        git_script = "\n".join([
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            'if [[ "$1" == "status" ]]; then printf ""; exit 0; fi',
            'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "feature/test-pr"; exit 0; fi',
        ])
        gh_script = "\n".join([
            'if [[ "$1" == "pr" && "$2" == "list" ]]; then echo \'[{"number": 42}]\'; exit 0; fi',
        ])

        result = run_hook("stop", tmp_path, git_script=git_script, gh_script_body=gh_script)
        assert result.returncode == 2
        assert "PR REVIEW" in result.stderr

    def test_stop_with_pr_and_evidence_missing_summary_blocks(self, tmp_path: Path):
        """When evidence file is missing 'summary' key, stop should block."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        reviews_dir = prawduct / ".pr-reviews"
        reviews_dir.mkdir()
        evidence = reviews_dir / "feature--test-pr.json"
        evidence.write_text(json.dumps({"findings": [], "branch": "feature/test-pr"}))

        git_script = "\n".join([
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            'if [[ "$1" == "status" ]]; then printf ""; exit 0; fi',
            'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "feature/test-pr"; exit 0; fi',
        ])
        gh_script = "\n".join([
            'if [[ "$1" == "pr" && "$2" == "list" ]]; then echo \'[{"number": 42}]\'; exit 0; fi',
        ])

        result = run_hook("stop", tmp_path, git_script=git_script, gh_script_body=gh_script)
        assert result.returncode == 2
        assert "PR REVIEW" in result.stderr

    def test_stop_on_main_branch_skips_pr_check(self, tmp_path: Path):
        """PR review check should skip main/master/develop branches."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        git_script = "\n".join([
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            'if [[ "$1" == "status" ]]; then printf ""; exit 0; fi',
            'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "main"; exit 0; fi',
        ])

        result = run_hook(
            "stop", tmp_path,
            git_script=git_script,
        )
        assert result.returncode == 0

    def test_stop_skips_pr_gate_when_pr_diff_is_doc_only(self, tmp_path: Path):
        """Gate 3 skips when the PR diff (merge-base...HEAD) is all .md, even
        when the session has uncommitted non-.md changes. Symmetric with the
        `/pr create` Step 1b fast-path: a doc-only PR was legitimately opened
        without review evidence; Gate 3 should not retroactively demand it.
        """
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        # Session: uncommitted .py change → session_doc_only=False, Gate 3 enters
        # PR diff: only .md committed → pr_doc_only=True, new skip applies
        git_script = "\n".join([
            'if [[ "$1" == "rev-parse" && "$2" == "--verify" && "$3" == "origin/main" ]]; then echo "abc123"; exit 0; fi',
            'if [[ "$1" == "rev-parse" && "$2" == "--verify" ]]; then exit 1; fi',
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            'if [[ "$1" == "status" ]]; then printf "%s" " M src/changed.py"; exit 0; fi',
            'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "feature/test-pr"; exit 0; fi',
            'if [[ "$1" == "diff" && "$2" == "--name-only" ]]; then echo ".prawduct/backlog.md"; echo "docs/notes.md"; exit 0; fi',
        ])

        gh_script = "\n".join([
            'if [[ "$1" == "pr" && "$2" == "list" ]]; then echo \'[{"number": 42}]\'; exit 0; fi',
        ])

        result = run_hook("stop", tmp_path, git_script=git_script, gh_script_body=gh_script)

        # Gate 3 should be skipped — no PR REVIEW blocker even though no
        # evidence file exists, because the PR is currently doc-only.
        assert "PR REVIEW" not in result.stderr

    def test_stop_still_blocks_when_pr_diff_includes_code(self, tmp_path: Path):
        """Confirms the doc-only skip is conditional, not unconditional:
        Gate 3 still BLOCKS when the PR's diff has any non-.md file and
        no evidence exists. Inverse of the previous test — guards against
        a future refactor accidentally over-broadening the skip.
        """
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        git_script = "\n".join([
            'if [[ "$1" == "rev-parse" && "$2" == "--verify" && "$3" == "origin/main" ]]; then echo "abc123"; exit 0; fi',
            'if [[ "$1" == "rev-parse" && "$2" == "--verify" ]]; then exit 1; fi',
            'if [[ "$1" == "rev-parse" ]]; then echo ".git"; exit 0; fi',
            'if [[ "$1" == "status" ]]; then printf "%s" " M src/changed.py"; exit 0; fi',
            'if [[ "$1" == "branch" && "$2" == "--show-current" ]]; then echo "feature/test-pr"; exit 0; fi',
            'if [[ "$1" == "diff" && "$2" == "--name-only" ]]; then echo "src/app.py"; echo "docs/notes.md"; exit 0; fi',
        ])

        gh_script = "\n".join([
            'if [[ "$1" == "pr" && "$2" == "list" ]]; then echo \'[{"number": 42}]\'; exit 0; fi',
        ])

        result = run_hook("stop", tmp_path, git_script=git_script, gh_script_body=gh_script)

        assert result.returncode == 2
        assert "PR REVIEW" in result.stderr


# =============================================================================
# Template content validation
# =============================================================================


class TestPrReviewTemplateContent:
    def test_pr_review_template_has_all_goals(self):
        """The PR review template should cover all 7 review goals."""
        content = (FRAMEWORK_DIR / "templates" / "pr-review.md").read_text()
        assert "No Bugs Shipped" in content
        assert "Tests Cover the Change" in content
        assert "Right Scope" in content
        assert "Clear Narrative" in content
        assert "Simplification" in content
        assert "Merge Hygiene" in content
        assert "Proportionality" in content

    def test_pr_command_template_has_all_flows(self):
        """The /pr command template should cover all 4 flows."""
        content = (FRAMEWORK_DIR / "templates" / "skill-pr.md").read_text()
        assert "Create Flow" in content
        assert "Update Flow" in content
        assert "Merge Flow" in content
        assert "Status Flow" in content

    def test_pr_command_template_has_review_gate(self):
        """The /pr command template must enforce review before PR creation."""
        content = (FRAMEWORK_DIR / "templates" / "skill-pr.md").read_text()
        # Must contain hard gate language, not just numbered steps
        assert "MANDATORY" in content
        assert "Do NOT proceed" in content or "DO NOT proceed" in content
        assert "evidence file" in content

    def test_framework_pr_command_has_review_gate(self):
        """The framework /pr command must enforce review before PR creation."""
        content = (FRAMEWORK_DIR / "templates" / "skill-pr.md").read_text()
        assert "MANDATORY" in content
        assert "Do NOT proceed" in content or "DO NOT proceed" in content
        assert "evidence file" in content

    def test_agent_skill_matches_template_goals(self):
        """The full SKILL.md and condensed template should have the same goals."""
        skill = (FRAMEWORK_DIR / "skills" / "pr" / "review-protocol.md").read_text()
        template = (FRAMEWORK_DIR / "templates" / "pr-review.md").read_text()

        goals = [
            "No Bugs Shipped",
            "Tests Cover the Change",
            "Right Scope",
            "Clear Narrative",
            "Simplification",
            "Merge Hygiene",
            "Proportionality",
        ]
        for goal in goals:
            assert goal in skill, f"SKILL.md missing goal: {goal}"
            assert goal in template, f"Template missing goal: {goal}"

    def test_pr_review_references_learnings(self):
        """PR reviewer must read learnings.md during setup."""
        template = (FRAMEWORK_DIR / "templates" / "pr-review.md").read_text()
        skill = (FRAMEWORK_DIR / "skills" / "pr" / "review-protocol.md").read_text()
        assert "learnings.md" in template
        assert "learnings.md" in skill

    def test_pr_review_has_learnings_crosscheck(self):
        """PR reviewer must have a Learnings Cross-Check section."""
        template = (FRAMEWORK_DIR / "templates" / "pr-review.md").read_text()
        skill = (FRAMEWORK_DIR / "skills" / "pr" / "review-protocol.md").read_text()
        assert "Learnings Cross-Check" in template
        assert "Learnings Cross-Check" in skill


# =============================================================================
# Discoverability in product CLAUDE.md
# =============================================================================


class TestDiscoverability:
    def test_product_claude_mentions_pr_command(self):
        """Product CLAUDE.md template should mention /pr for discoverability."""
        content = (FRAMEWORK_DIR / "templates" / "product-claude.md").read_text()
        assert "/pr" in content

    def test_product_claude_routes_pr_requests(self):
        """Product CLAUDE.md should mention PR-related actions routing to /pr."""
        content = (FRAMEWORK_DIR / "templates" / "product-claude.md").read_text()
        assert "PR" in content
        assert "/pr" in content

    def test_building_methodology_mentions_pr(self):
        """Building methodology should mention /pr."""
        content = (FRAMEWORK_DIR / "methodology" / "building.md").read_text()
        assert "/pr" in content
        assert "PR reviewer" in content or "PR review" in content

    def test_framework_claude_mentions_pr(self):
        """Framework CLAUDE.md should mention /pr."""
        content = (FRAMEWORK_DIR / "CLAUDE.md").read_text()
        assert "/pr" in content
