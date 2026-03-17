"""Tests for PR reviewer integration — init, sync, and hook.

Tests that prawduct-init.py creates PR reviewer files, prawduct-sync.py
tracks them in the manifest, and the stop hook handles PR review evidence.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

# Load modules via importlib (hyphenated filenames)
_TOOLS = Path(__file__).resolve().parent.parent / "tools"

_init_spec = importlib.util.spec_from_file_location("prawduct_init", _TOOLS / "prawduct-init.py")
_init_mod = importlib.util.module_from_spec(_init_spec)
_init_spec.loader.exec_module(_init_mod)
run_init = _init_mod.run_init

_sync_spec = importlib.util.spec_from_file_location("prawduct_sync", _TOOLS / "prawduct-sync.py")
_sync_mod = importlib.util.module_from_spec(_sync_spec)
_sync_spec.loader.exec_module(_sync_mod)
run_sync = _sync_mod.run_sync
create_manifest = _sync_mod.create_manifest
compute_hash = _sync_mod.compute_hash
compute_block_hash = _sync_mod.compute_block_hash

HOOK_PATH = _TOOLS / "product-hook"
FRAMEWORK_DIR = _TOOLS.parent


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
    """Run product-hook with controlled mocks for git and gh.

    If git_script is provided, it's used as the full git mock script body.
    Otherwise a basic git mock is generated from git_output.
    """
    env = {
        "HOME": str(project_dir),
        "CLAUDE_PROJECT_DIR": str(project_dir),
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
# Init: PR reviewer files created
# =============================================================================


class TestInitPrReviewFiles:
    def test_creates_pr_review_md(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")
        pr_review = tmp_path / ".prawduct" / "pr-review.md"
        assert pr_review.is_file()
        content = pr_review.read_text()
        assert "PR Review" in content
        assert "No Bugs Shipped" in content

    def test_creates_pr_command(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")
        pr_cmd = tmp_path / ".claude" / "commands" / "pr.md"
        assert pr_cmd.is_file()
        content = pr_cmd.read_text()
        assert "PR lifecycle" in content
        assert "Create Flow" in content

    def test_pr_review_in_actions(self, tmp_path: Path):
        result = run_init(str(tmp_path), "TestProduct")
        actions = result["actions"]
        assert any("pr-review.md" in a for a in actions)
        assert any("commands/pr.md" in a for a in actions)

    def test_pr_reviews_gitignored(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")
        gitignore = (tmp_path / ".gitignore").read_text()
        assert ".prawduct/.pr-reviews/" in gitignore

    def test_idempotent_pr_files(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")
        result = run_init(str(tmp_path), "TestProduct")
        # Second run should not recreate PR files
        assert not any("pr-review.md" in a for a in result["actions"])
        assert not any("commands/pr.md" in a for a in result["actions"])


# =============================================================================
# Init: Manifest includes PR reviewer entries
# =============================================================================


class TestInitManifestPrEntries:
    def test_manifest_has_pr_review(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")
        manifest = json.loads(
            (tmp_path / ".prawduct" / "sync-manifest.json").read_text()
        )
        assert ".prawduct/pr-review.md" in manifest["files"]
        entry = manifest["files"][".prawduct/pr-review.md"]
        assert entry["strategy"] == "template"
        assert entry["template"] == "templates/pr-review.md"
        assert entry["generated_hash"] is not None

    def test_manifest_has_pr_command(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")
        manifest = json.loads(
            (tmp_path / ".prawduct" / "sync-manifest.json").read_text()
        )
        assert ".claude/commands/pr.md" in manifest["files"]
        entry = manifest["files"][".claude/commands/pr.md"]
        assert entry["strategy"] == "template"
        assert entry["template"] == "templates/commands-pr.md"
        assert entry["generated_hash"] is not None


# =============================================================================
# Sync: PR reviewer files tracked and updated
# =============================================================================


class TestSyncPrReviewFiles:
    @pytest.fixture()
    def product_dir(self, tmp_path: Path):
        """Create a product with a manifest pointing to the real framework."""
        run_init(str(tmp_path), "SyncTest")
        return tmp_path

    def test_sync_no_change_when_current(self, product_dir: Path):
        # Sync immediately after init — nothing should change
        result = run_sync(
            str(product_dir), str(FRAMEWORK_DIR), no_pull=True
        )
        assert not any("pr-review" in a for a in result["actions"])
        assert not any("commands/pr" in a for a in result["actions"])

    def test_sync_updates_pr_review_when_template_changes(self, product_dir: Path):
        # Write "old" content to simulate a previous template version.
        # Set stored hash to match the file on disk (user hasn't edited),
        # but it won't match the current rendered template (template "changed").
        pr_review = product_dir / ".prawduct" / "pr-review.md"
        old_content = "# Old PR Review\nPrevious version."
        pr_review.write_text(old_content)
        old_hash = compute_hash(pr_review)

        manifest_path = product_dir / ".prawduct" / "sync-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][".prawduct/pr-review.md"]["generated_hash"] = old_hash
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

        result = run_sync(
            str(product_dir), str(FRAMEWORK_DIR), no_pull=True
        )
        assert any("pr-review" in a for a in result["actions"])

    def test_sync_skips_user_edited_pr_review(self, product_dir: Path):
        # Edit the product's pr-review.md
        pr_review = product_dir / ".prawduct" / "pr-review.md"
        pr_review.write_text("# Custom PR review instructions\nUser edited this.")

        # Simulate template change
        manifest_path = product_dir / ".prawduct" / "sync-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][".prawduct/pr-review.md"]["generated_hash"] = "stale_hash"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

        result = run_sync(
            str(product_dir), str(FRAMEWORK_DIR), no_pull=True
        )
        # Should skip because user edited
        assert not any("pr-review" in a for a in result["actions"])
        assert any("pr-review" in n for n in result["notes"])

    def test_sync_updates_pr_command_when_template_changes(self, product_dir: Path):
        # Write "old" content to simulate previous version
        pr_cmd = product_dir / ".claude" / "commands" / "pr.md"
        pr_cmd.write_text("# Old PR command\nPrevious version.")
        old_hash = compute_hash(pr_cmd)

        manifest_path = product_dir / ".prawduct" / "sync-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"][".claude/commands/pr.md"]["generated_hash"] = old_hash
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

        result = run_sync(
            str(product_dir), str(FRAMEWORK_DIR), no_pull=True
        )
        assert any("commands/pr" in a for a in result["actions"])


# =============================================================================
# Sync: create_manifest includes PR entries
# =============================================================================


class TestCreateManifestPrEntries:
    def test_manifest_includes_pr_review_config(self, tmp_path: Path):
        file_hashes = {
            "CLAUDE.md": "abc123",
            ".prawduct/critic-review.md": "def456",
            ".prawduct/pr-review.md": "ghi789",
            ".claude/commands/pr.md": "jkl012",
            "tools/product-hook": "mno345",
            ".claude/settings.json": None,
        }
        manifest = create_manifest(tmp_path, FRAMEWORK_DIR, "Test", file_hashes)

        assert ".prawduct/pr-review.md" in manifest["files"]
        assert manifest["files"][".prawduct/pr-review.md"]["template"] == "templates/pr-review.md"
        assert manifest["files"][".prawduct/pr-review.md"]["generated_hash"] == "ghi789"

    def test_manifest_includes_pr_command_config(self, tmp_path: Path):
        file_hashes = {
            "CLAUDE.md": "abc123",
            ".prawduct/critic-review.md": "def456",
            ".prawduct/pr-review.md": "ghi789",
            ".claude/commands/pr.md": "jkl012",
            "tools/product-hook": "mno345",
            ".claude/settings.json": None,
        }
        manifest = create_manifest(tmp_path, FRAMEWORK_DIR, "Test", file_hashes)

        assert ".claude/commands/pr.md" in manifest["files"]
        assert manifest["files"][".claude/commands/pr.md"]["template"] == "templates/commands-pr.md"


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
        content = (FRAMEWORK_DIR / "templates" / "commands-pr.md").read_text()
        assert "Create Flow" in content
        assert "Update Flow" in content
        assert "Merge Flow" in content
        assert "Status Flow" in content

    def test_pr_command_template_has_review_gate(self):
        """The /pr command template must enforce review before PR creation."""
        content = (FRAMEWORK_DIR / "templates" / "commands-pr.md").read_text()
        # Must contain hard gate language, not just numbered steps
        assert "MANDATORY" in content
        assert "Do NOT proceed" in content or "DO NOT proceed" in content
        assert "evidence file" in content

    def test_framework_pr_command_has_review_gate(self):
        """The framework /pr command must enforce review before PR creation."""
        content = (FRAMEWORK_DIR / ".claude" / "commands" / "pr.md").read_text()
        assert "MANDATORY" in content
        assert "Do NOT proceed" in content or "DO NOT proceed" in content
        assert "evidence file" in content

    def test_agent_skill_matches_template_goals(self):
        """The full SKILL.md and condensed template should have the same goals."""
        skill = (FRAMEWORK_DIR / "agents" / "pr-reviewer" / "SKILL.md").read_text()
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
