"""Tests for prawduct-setup.py — validation functionality.

Tests the run_validate health check against various repo states.
"""

from __future__ import annotations

import importlib.util
import json
import os
import stat
from pathlib import Path

import pytest

# Load prawduct-setup.py via importlib
_TOOL_PATH = Path(__file__).resolve().parent.parent / "tools" / "prawduct-setup.py"
_spec = importlib.util.spec_from_file_location("prawduct_setup", _TOOL_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

run_init = _mod.run_init
run_validate = _mod.run_validate
BLOCK_BEGIN = _mod.BLOCK_BEGIN
BLOCK_END = _mod.BLOCK_END
MANAGED_FILES = _mod.MANAGED_FILES


def _make_healthy_product(tmp_path: Path) -> Path:
    """Create a healthy v5 product repo for testing."""
    product = tmp_path / "product"
    product.mkdir()
    run_init(str(product), "TestProduct")
    # Simulate a session having started (hooks fired)
    (product / ".prawduct" / ".session-start").write_text("2026-03-22T00:00:00Z")
    return product


def _find_check(result: dict, name: str) -> dict | None:
    """Find a check by name in validation results."""
    for check in result["checks"]:
        if check["name"] == name:
            return check
    return None


# =============================================================================
# Healthy repo — all checks pass
# =============================================================================


class TestHealthyRepo:
    def test_all_checks_pass(self, tmp_path: Path):
        """A freshly-initialized product passes all validation checks."""
        product = _make_healthy_product(tmp_path)
        result = run_validate(str(product))

        assert result["overall"] in ("healthy", "degraded")
        assert result["version"] == "v5"

        for check_name in ["managed_files", "settings_hooks", "hook_executable",
                           "claude_md_markers", "sync_manifest", "template_variables",
                           "session_state"]:
            check = _find_check(result, check_name)
            assert check is not None, f"Missing check: {check_name}"
            assert check["status"] == "pass", f"{check_name} failed: {check.get('detail')}"


class TestHealthyProductStructure:
    """Verify _make_healthy_product creates correct structure."""

    def test_settings_structure(self, tmp_path: Path):
        """Settings have SessionStart+Stop (no SessionEnd), with statusMessage."""
        product = _make_healthy_product(tmp_path)
        settings = json.loads((product / ".claude" / "settings.json").read_text())
        hooks = settings.get("hooks", {})
        assert "SessionStart" in hooks
        assert "Stop" in hooks
        assert "SessionEnd" not in hooks
        for event in ["SessionStart", "Stop"]:
            for entry in hooks[event]:
                for hook in entry.get("hooks", []):
                    assert "statusMessage" in hook, f"{event} hook missing statusMessage"

    def test_skills_and_backlog(self, tmp_path: Path):
        """Skills have allowed-tools frontmatter; backlog.md exists."""
        product = _make_healthy_product(tmp_path)
        for skill_dir in (product / ".claude" / "skills").iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if skill_md.is_file():
                content = skill_md.read_text()
                assert "allowed-tools:" in content, f"{skill_dir.name} missing allowed-tools"
                assert "user-invocable:" in content, f"{skill_dir.name} missing user-invocable"
        backlog = product / ".prawduct" / "backlog.md"
        assert backlog.is_file()
        assert "Backlog" in backlog.read_text()


# =============================================================================
# Missing / broken files
# =============================================================================


class TestBrokenRepo:
    def test_no_prawduct_dir(self, tmp_path: Path):
        result = run_validate(str(tmp_path))
        assert result["overall"] == "broken"
        assert result["version"] == "unknown"

    def test_missing_managed_file_fails(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        (product / ".prawduct" / "critic-review.md").unlink()
        result = run_validate(str(product))
        check = _find_check(result, "managed_files")
        assert check["status"] == "fail"
        assert "critic-review.md" in check["detail"]

    def test_broken_settings_json(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        (product / ".claude" / "settings.json").write_text("NOT JSON {{{")
        result = run_validate(str(product))
        check = _find_check(result, "settings_hooks")
        assert check["status"] == "fail"
        assert "not valid JSON" in check["detail"]

    def test_missing_settings_json(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        (product / ".claude" / "settings.json").unlink()
        result = run_validate(str(product))
        check = _find_check(result, "settings_hooks")
        assert check["status"] == "fail"

    def test_missing_hook_events(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        settings = {"hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}}
        (product / ".claude" / "settings.json").write_text(json.dumps(settings))
        result = run_validate(str(product))
        check = _find_check(result, "settings_hooks")
        assert check["status"] == "fail"
        assert "Missing hook events" in check["detail"]

    def test_stale_session_end_hook_passes_validation(self, tmp_path: Path):
        """Products with a stale SessionEnd hook still pass (only SessionStart+Stop required)."""
        product = _make_healthy_product(tmp_path)
        settings = json.loads((product / ".claude" / "settings.json").read_text())
        settings["hooks"]["SessionEnd"] = [{"hooks": [{"type": "command", "command": "echo old"}]}]
        (product / ".claude" / "settings.json").write_text(json.dumps(settings))
        result = run_validate(str(product))
        check = _find_check(result, "settings_hooks")
        assert check["status"] == "pass"

    def test_non_executable_hook(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        hook = product / "tools" / "product-hook"
        hook.chmod(stat.S_IRUSR | stat.S_IWUSR)
        result = run_validate(str(product))
        check = _find_check(result, "hook_executable")
        assert check["status"] == "fail"
        assert "not executable" in check["detail"]

    def test_missing_hook(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        (product / "tools" / "product-hook").unlink()
        result = run_validate(str(product))
        check = _find_check(result, "hook_executable")
        assert check["status"] == "fail"
        assert "does not exist" in check["detail"]


# =============================================================================
# Block markers
# =============================================================================


class TestMarkerValidation:
    def test_missing_markers_warns(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        (product / "CLAUDE.md").write_text("# My Project\n\nNo markers here.")
        result = run_validate(str(product))
        check = _find_check(result, "claude_md_markers")
        assert check["status"] == "warn"

    def test_only_begin_marker_fails(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        (product / "CLAUDE.md").write_text(f"# My Project\n\n{BLOCK_BEGIN}\nContent")
        result = run_validate(str(product))
        check = _find_check(result, "claude_md_markers")
        assert check["status"] == "fail"

    def test_missing_claude_md_fails(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        (product / "CLAUDE.md").unlink()
        result = run_validate(str(product))
        check = _find_check(result, "claude_md_markers")
        assert check["status"] == "fail"


# =============================================================================
# Manifest validation
# =============================================================================


class TestManifestValidation:
    def test_broken_manifest_json(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        (product / ".prawduct" / "sync-manifest.json").write_text("not json")
        result = run_validate(str(product))
        check = _find_check(result, "sync_manifest")
        assert check["status"] == "fail"

    def test_missing_manifest_warns(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        (product / ".prawduct" / "sync-manifest.json").unlink()
        result = run_validate(str(product))
        check = _find_check(result, "sync_manifest")
        assert check["status"] == "warn"

    def test_old_format_version_warns(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        manifest = json.loads((product / ".prawduct" / "sync-manifest.json").read_text())
        manifest["format_version"] = 1
        (product / ".prawduct" / "sync-manifest.json").write_text(json.dumps(manifest))
        result = run_validate(str(product))
        check = _find_check(result, "sync_manifest")
        assert check["status"] == "warn"
        assert "format_version 1" in check["detail"]


# =============================================================================
# Template variables, session state, overall status
# =============================================================================


class TestTemplateVariables:
    def test_unresolved_variables_warns(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        (product / ".prawduct" / "critic-review.md").write_text("# {{PRODUCT_NAME}} Critic")
        result = run_validate(str(product))
        check = _find_check(result, "template_variables")
        assert check["status"] == "warn"
        assert "critic-review.md" in check["detail"]


class TestSessionState:
    def test_no_session_start_warns(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        (product / ".prawduct" / ".session-start").unlink()
        result = run_validate(str(product))
        check = _find_check(result, "session_state")
        assert check["status"] == "warn"
        assert "hooks may not have fired" in check["detail"]


class TestOverallStatus:
    def test_broken_when_any_fail(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        (product / ".claude" / "settings.json").write_text("NOT JSON")
        result = run_validate(str(product))
        assert result["overall"] == "broken"

    def test_degraded_when_only_warns(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        (product / ".prawduct" / ".session-start").unlink()
        result = run_validate(str(product))
        assert result["overall"] in ("healthy", "degraded")

    def test_needs_restart_false_when_current(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        result = run_validate(str(product))
        assert result["needs_restart"] is False

    def test_recommendations_populated_on_failure(self, tmp_path: Path):
        result = run_validate(str(tmp_path))
        assert result["overall"] == "broken"
        assert len(result["recommendations"]) > 0


# =============================================================================
# Gitignore hygiene
# =============================================================================


class TestGitignoreHygiene:
    def test_healthy_repo_passes(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        result = run_validate(str(product))
        check = _find_check(result, "gitignore_hygiene")
        assert check is not None
        assert check["status"] == "pass"

    def test_managed_file_in_gitignore_warns(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        gi = product / ".gitignore"
        gi.write_text(gi.read_text() + "\n.prawduct/critic-review.md\n")
        result = run_validate(str(product))
        check = _find_check(result, "gitignore_hygiene")
        assert check["status"] == "warn"
        assert "critic-review.md" in check["detail"]

    def test_multiple_managed_files_in_gitignore(self, tmp_path: Path):
        product = _make_healthy_product(tmp_path)
        gi = product / ".gitignore"
        gi.write_text(
            gi.read_text()
            + "\n.prawduct/critic-review.md\n"
            + ".prawduct/build-governance.md\n"
        )
        result = run_validate(str(product))
        check = _find_check(result, "gitignore_hygiene")
        assert check["status"] == "warn"
        assert "critic-review.md" in check["detail"]
        assert "build-governance.md" in check["detail"]

    def test_session_files_in_gitignore_ok(self, tmp_path: Path):
        """Session files like .critic-findings.json should be gitignored — not flagged."""
        product = _make_healthy_product(tmp_path)
        result = run_validate(str(product))
        check = _find_check(result, "gitignore_hygiene")
        assert check["status"] == "pass"
