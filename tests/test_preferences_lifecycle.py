"""Tests for the project-preferences.md lifecycle across init, sync, and hook.

Three scenarios tested end-to-end:
1. New project: init places template, hook warns after code added, filled silences warning
2. Existing project: init on repo with code, immediate warning, filled silences
3. Legacy product: pre-feature repo, hook warns, sync places template, fill silences

Uses subprocess tests (matching real execution) alongside direct function calls
for component verification.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# =============================================================================
# Paths and module loading
# =============================================================================

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = REPO_ROOT / "tools" / "product-hook"
SETUP_SCRIPT_PATH = REPO_ROOT / "tools" / "prawduct-setup.py"
SYNC_SCRIPT_PATH = REPO_ROOT / "tools" / "prawduct-sync.py"
LIB_DIR_PATH = REPO_ROOT / "tools" / "lib"
TEMPLATE_PATH = REPO_ROOT / "templates" / "project-preferences.md"

# Load prawduct-setup.py via importlib
_setup_spec = importlib.util.spec_from_file_location(
    "prawduct_setup", SETUP_SCRIPT_PATH
)
_setup_mod = importlib.util.module_from_spec(_setup_spec)
_setup_spec.loader.exec_module(_setup_mod)
run_init = _setup_mod.run_init
run_sync = _setup_mod.run_sync
render_template = _setup_mod.render_template
compute_hash = _setup_mod.compute_hash
compute_block_hash = _setup_mod.compute_block_hash
create_manifest = _setup_mod.create_manifest
BLOCK_BEGIN = _setup_mod.BLOCK_BEGIN
BLOCK_END = _setup_mod.BLOCK_END

# The detection string used by the hook to identify unfilled templates
UNFILLED_MARKER = "- **Language**:\n"


# =============================================================================
# Helpers
# =============================================================================


def run_hook(
    command: str,
    project_dir: Path,
    *,
    env_extra: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Run product-hook subprocess with controlled environment.

    Does not set up mock git — preferences tests don't need it.
    """
    env = {
        "HOME": str(project_dir),
        "CLAUDE_PROJECT_DIR": str(project_dir),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
    }
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, str(HOOK_PATH), command],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )


def _setup_framework(tmp_path: Path) -> Path:
    """Create a framework dir with real sync script and templates.

    Copies the actual prawduct-sync.py so subprocess chain tests exercise
    the real sync logic.
    """
    fw = tmp_path / "framework"
    fw.mkdir()

    # Copy the real setup script (and sync shim for backward compat)
    tools = fw / "tools"
    tools.mkdir()
    shutil.copy2(SETUP_SCRIPT_PATH, tools / "prawduct-setup.py")
    shutil.copy2(SYNC_SCRIPT_PATH, tools / "prawduct-sync.py")
    shutil.copytree(LIB_DIR_PATH, tools / "lib")
    (tools / "product-hook").write_text("#!/usr/bin/env python3\n# hook v1")

    # Copy templates
    templates = fw / "templates"
    templates.mkdir()
    shutil.copy2(TEMPLATE_PATH, templates / "project-preferences.md")

    # Minimal required templates for sync (it iterates manifest files)
    (templates / "product-claude.md").write_text(
        f"# {{{{PRODUCT_NAME}}}} CLAUDE.md\n\n"
        f"{BLOCK_BEGIN}\nContent v1\n{BLOCK_END}\n"
    )
    (templates / "critic-review.md").write_text("# {{PRODUCT_NAME}} Critic v1")
    (templates / "product-settings.json").write_text(json.dumps({
        "hooks": {
            "SessionStart": [{"matcher": "clear", "hooks": [
                {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/tools/product-hook" clear'}
            ]}],
            "Stop": [{"matcher": "", "hooks": [
                {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/tools/product-hook" stop'}
            ]}],
        }
    }, indent=2))

    return fw


def _setup_legacy_product(
    tmp_path: Path, fw: Path, product_name: str = "TestApp"
) -> Path:
    """Create a product with manifest but NO project-preferences.md.

    Simulates a pre-feature repo that was init'd before preferences existed.
    """
    product = tmp_path / "product"
    product.mkdir()
    prawduct = product / ".prawduct"
    prawduct.mkdir()
    (prawduct / "artifacts").mkdir()

    subs = {"{{PRODUCT_NAME}}": product_name}

    # Write standard managed files
    claude_content = render_template(fw / "templates" / "product-claude.md", subs)
    (product / "CLAUDE.md").write_text(claude_content)

    critic_content = render_template(fw / "templates" / "critic-review.md", subs)
    (prawduct / "critic-review.md").write_text(critic_content)

    (product / "tools").mkdir()
    (product / "tools" / "product-hook").write_bytes(
        (fw / "tools" / "product-hook").read_bytes()
    )

    (product / ".claude").mkdir()
    (product / ".claude" / "settings.json").write_text(
        (fw / "templates" / "product-settings.json").read_text()
    )

    # Build manifest (preferences is place-once, not tracked in manifest)
    hashes = {
        "CLAUDE.md": compute_block_hash(claude_content),
        ".prawduct/critic-review.md": compute_hash(prawduct / "critic-review.md"),
        "tools/product-hook": compute_hash(product / "tools" / "product-hook"),
        ".claude/settings.json": None,
    }
    manifest = create_manifest(product, fw, product_name, hashes)
    (prawduct / "sync-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )

    # Crucially: NO project-preferences.md — this is the legacy state
    return product


# =============================================================================
# Scenario 1: New Project
# =============================================================================


class TestNewProject:
    """Init places template; hook warns only when code exists and prefs unfilled."""

    def test_init_places_template(self, tmp_path: Path):
        """run_init creates project-preferences.md in the artifacts dir."""
        run_init(str(tmp_path), "MyApp")

        prefs = tmp_path / ".prawduct" / "artifacts" / "project-preferences.md"
        assert prefs.is_file()
        assert "# Project Preferences" in prefs.read_text()

    def test_init_creates_artifacts_dir(self, tmp_path: Path):
        """Init creates .prawduct/artifacts/ even if it didn't exist."""
        result = run_init(str(tmp_path), "MyApp")

        assert (tmp_path / ".prawduct" / "artifacts").is_dir()
        assert any("artifacts" in a for a in result["actions"])

    def test_no_warning_without_code(self, tmp_path: Path):
        """Brand-new project with no source files: no CRITICAL warning."""
        run_init(str(tmp_path), "MyApp")

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert "CRITICAL" not in result.stdout

    def test_warning_after_code_added(self, tmp_path: Path):
        """Unfilled template + source code: CRITICAL warning."""
        run_init(str(tmp_path), "MyApp")
        (tmp_path / "app.py").write_text("print('hello')")

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert "CRITICAL" in result.stdout
        assert "project-preferences.md" in result.stdout

    def test_warning_disappears_after_filling(self, tmp_path: Path):
        """Filled preferences: no warning even with source code."""
        run_init(str(tmp_path), "MyApp")
        (tmp_path / "app.py").write_text("print('hello')")

        prefs = tmp_path / ".prawduct" / "artifacts" / "project-preferences.md"
        prefs.write_text(
            "# Project Preferences\n\n## Language & Runtime\n\n"
            "- **Language**: Python 3.12\n"
        )

        result = run_hook("clear", tmp_path)

        assert result.returncode == 0
        assert "CRITICAL" not in result.stdout

    def test_idempotent_reinit_does_not_overwrite(self, tmp_path: Path):
        """Running init twice doesn't overwrite user-edited preferences."""
        run_init(str(tmp_path), "MyApp")

        prefs = tmp_path / ".prawduct" / "artifacts" / "project-preferences.md"
        prefs.write_text("# Project Preferences\n\n- **Language**: Rust\n")

        result = run_init(str(tmp_path), "MyApp")

        assert "Rust" in prefs.read_text()
        assert not any("project-preferences" in a for a in result["actions"])

    def test_template_has_unfilled_marker(self, tmp_path: Path):
        """The template as placed by init contains the unfilled detection string."""
        run_init(str(tmp_path), "MyApp")

        prefs = tmp_path / ".prawduct" / "artifacts" / "project-preferences.md"
        assert UNFILLED_MARKER in prefs.read_text()

    def test_template_content_matches_source(self, tmp_path: Path):
        """Init places the exact content from templates/project-preferences.md."""
        run_init(str(tmp_path), "MyApp")

        prefs = tmp_path / ".prawduct" / "artifacts" / "project-preferences.md"
        expected = TEMPLATE_PATH.read_text()
        assert prefs.read_text() == expected


# =============================================================================
# Scenario 2: Existing Project First Init
# =============================================================================


class TestExistingProject:
    """Init on a directory that already has source code."""

    def test_init_with_code_produces_template(self, tmp_path: Path):
        """Init on a dir with existing code creates preferences template."""
        (tmp_path / "main.js").write_text("console.log('hello')")
        run_init(str(tmp_path), "MyApp")

        prefs = tmp_path / ".prawduct" / "artifacts" / "project-preferences.md"
        assert prefs.is_file()

    def test_immediate_warning_on_first_session(self, tmp_path: Path):
        """Init + code: first clear warns about unfilled preferences."""
        (tmp_path / "server.ts").write_text("import express from 'express'")
        run_init(str(tmp_path), "MyApp")

        result = run_hook("clear", tmp_path)

        assert "CRITICAL" in result.stdout
        assert "project-preferences.md" in result.stdout

    def test_warning_silenced_after_filling(self, tmp_path: Path):
        """After filling preferences, the warning goes away."""
        (tmp_path / "main.go").write_text("package main")
        run_init(str(tmp_path), "MyApp")

        prefs = tmp_path / ".prawduct" / "artifacts" / "project-preferences.md"
        prefs.write_text(
            "# Project Preferences\n\n## Language & Runtime\n\n"
            "- **Language**: Go 1.22\n"
        )

        result = run_hook("clear", tmp_path)
        assert "CRITICAL" not in result.stdout

    @pytest.mark.parametrize("ext", [
        ".py", ".js", ".ts", ".go", ".rs", ".java", ".rb", ".swift", ".kt",
        ".c", ".cpp", ".h",
    ])
    def test_code_extension_triggers_warning(self, tmp_path: Path, ext: str):
        """Each supported code extension triggers the has_code check."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "artifacts").mkdir()
        # Unfilled template
        (prawduct / "artifacts" / "project-preferences.md").write_text(
            "# Project Preferences\n\n- **Language**:\n"
        )
        (tmp_path / f"file{ext}").write_text("code")

        result = run_hook("clear", tmp_path)
        assert "CRITICAL" in result.stdout, f"Failed to detect {ext} as code"

    def test_prawduct_dir_excluded_from_code_detection(self, tmp_path: Path):
        """Python files inside .prawduct/ don't count as source code."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "artifacts").mkdir()
        # Only Python file is inside .prawduct
        (prawduct / "helper.py").write_text("# internal tool")

        result = run_hook("clear", tmp_path)
        assert "CRITICAL" not in result.stdout

    def test_node_modules_excluded_from_code_detection(self, tmp_path: Path):
        """Files in node_modules/ don't count as source code."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "artifacts").mkdir()
        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("module.exports = {}")

        result = run_hook("clear", tmp_path)
        assert "CRITICAL" not in result.stdout


# =============================================================================
# Scenario 3: Legacy Product Updating
# =============================================================================


class TestLegacyProduct:
    """Pre-feature repo that needs sync to place preferences template."""

    def test_sync_places_preferences_direct(self, tmp_path: Path):
        """run_sync places preferences.md when missing from existing product."""
        fw = _setup_framework(tmp_path)
        product = _setup_legacy_product(tmp_path, fw)

        result = run_sync(str(product), framework_dir=str(fw))

        prefs = product / ".prawduct" / "artifacts" / "project-preferences.md"
        assert prefs.is_file()
        assert "Project Preferences" in prefs.read_text()
        assert any("project-preferences" in a for a in result["actions"])

    def test_sync_subprocess_chain_places_preferences(self, tmp_path: Path):
        """Full subprocess chain: hook -> try_sync -> sync.py places preferences."""
        fw = _setup_framework(tmp_path)
        product = _setup_legacy_product(tmp_path, fw)

        result = run_hook("clear", product, env_extra={
            "PRAWDUCT_FRAMEWORK_DIR": str(fw),
        })

        assert result.returncode == 0
        prefs = product / ".prawduct" / "artifacts" / "project-preferences.md"
        assert prefs.is_file(), (
            f"Sync didn't place preferences.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_sync_does_not_overwrite_existing(self, tmp_path: Path):
        """Sync's place-once logic skips if preferences already exist."""
        fw = _setup_framework(tmp_path)
        product = _setup_legacy_product(tmp_path, fw)

        prefs = product / ".prawduct" / "artifacts" / "project-preferences.md"
        prefs.write_text("# My filled preferences\n- **Language**: TypeScript\n")

        result = run_sync(str(product), framework_dir=str(fw))

        assert "TypeScript" in prefs.read_text()
        assert not any("project-preferences" in a for a in result["actions"])

    def test_framework_resolution_manifest_path(self, tmp_path: Path):
        """Sync finds framework via manifest's framework_source field."""
        fw = _setup_framework(tmp_path)
        product = _setup_legacy_product(tmp_path, fw)

        # Call without explicit framework_dir — manifest has the path
        result = run_sync(str(product))

        prefs = product / ".prawduct" / "artifacts" / "project-preferences.md"
        assert prefs.is_file()

    def test_framework_resolution_env_var(self, tmp_path: Path, monkeypatch):
        """Sync finds framework via PRAWDUCT_FRAMEWORK_DIR env var."""
        fw = _setup_framework(tmp_path)
        product = _setup_legacy_product(tmp_path, fw)

        # Break manifest's framework_source
        manifest_path = product / ".prawduct" / "sync-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["framework_source"] = "/nonexistent/path"
        manifest_path.write_text(json.dumps(manifest))

        monkeypatch.setenv("PRAWDUCT_FRAMEWORK_DIR", str(fw))

        result = run_sync(str(product))

        prefs = product / ".prawduct" / "artifacts" / "project-preferences.md"
        assert prefs.is_file()

    def test_framework_resolution_sibling_fallback(self, tmp_path: Path):
        """Sync falls back to ../prawduct when manifest path is stale."""
        # Create framework as sibling "prawduct"
        parent = tmp_path / "source"
        parent.mkdir()
        sibling_fw = parent / "prawduct"
        # Build framework in a temp location, then copy as sibling
        fw = _setup_framework(tmp_path)
        shutil.copytree(fw, sibling_fw)

        # Create product as sibling with stale manifest
        product = parent / "myapp"
        product.mkdir()
        prawduct = product / ".prawduct"
        prawduct.mkdir()
        (prawduct / "artifacts").mkdir()
        manifest = {
            "format_version": 1,
            "framework_source": "/nonexistent/old/path",
            "product_name": "MyApp",
            "last_sync": "2026-01-01T00:00:00Z",
            "files": {},
        }
        (prawduct / "sync-manifest.json").write_text(json.dumps(manifest))

        result = run_sync(str(product))

        prefs = product / ".prawduct" / "artifacts" / "project-preferences.md"
        assert prefs.is_file()

    def test_stale_framework_no_fallback_fails_gracefully(self, tmp_path: Path):
        """Stale framework path with no sibling: sync skips, no crash."""
        product = tmp_path / "product"
        product.mkdir()
        prawduct = product / ".prawduct"
        prawduct.mkdir()
        manifest = {
            "format_version": 1,
            "framework_source": "/nonexistent/old/path",
            "product_name": "Test",
            "files": {},
        }
        (prawduct / "sync-manifest.json").write_text(json.dumps(manifest))

        result = run_sync(str(product))

        assert result["synced"] is False
        assert result["reason"] == "framework not found"

    def test_missing_sync_script_no_crash(self, tmp_path: Path):
        """Hook handles missing sync script gracefully (try_sync catches all)."""
        fw = _setup_framework(tmp_path)
        product = _setup_legacy_product(tmp_path, fw)

        # Delete sync scripts from framework
        (fw / "tools" / "prawduct-setup.py").unlink()
        (fw / "tools" / "prawduct-sync.py").unlink()

        result = run_hook("clear", product, env_extra={
            "PRAWDUCT_FRAMEWORK_DIR": str(fw),
        })

        assert result.returncode == 0

    def test_missing_template_sync_continues(self, tmp_path: Path):
        """Missing preferences template: sync runs but doesn't place file."""
        fw = _setup_framework(tmp_path)
        product = _setup_legacy_product(tmp_path, fw)

        # Delete just the preferences template
        (fw / "templates" / "project-preferences.md").unlink()

        result = run_sync(str(product), framework_dir=str(fw))

        prefs = product / ".prawduct" / "artifacts" / "project-preferences.md"
        assert not prefs.is_file()

    def test_broken_sync_script_no_crash(self, tmp_path: Path):
        """Broken sync script (syntax error): hook catches, returns 0."""
        fw = _setup_framework(tmp_path)
        product = _setup_legacy_product(tmp_path, fw)

        # Break the sync scripts
        (fw / "tools" / "prawduct-setup.py").write_text("THIS IS NOT PYTHON !!!")
        (fw / "tools" / "prawduct-sync.py").write_text("THIS IS NOT PYTHON !!!")

        result = run_hook("clear", product, env_extra={
            "PRAWDUCT_FRAMEWORK_DIR": str(fw),
        })

        assert result.returncode == 0

    def test_ordering_warning_before_sync_first_session(self, tmp_path: Path):
        """First session on legacy repo: warning fires (missing), then sync places file.

        The preferences check runs BEFORE try_sync in cmd_clear. On a legacy repo
        with code, the first session sees: missing prefs -> warn, then sync places file.
        """
        fw = _setup_framework(tmp_path)
        product = _setup_legacy_product(tmp_path, fw)
        (product / "app.py").write_text("print('hello')")

        result = run_hook("clear", product, env_extra={
            "PRAWDUCT_FRAMEWORK_DIR": str(fw),
        })

        # Warning should be in output (missing file when check ran)
        assert "CRITICAL" in result.stdout
        # But sync should have placed the file by end of clear
        prefs = product / ".prawduct" / "artifacts" / "project-preferences.md"
        assert prefs.is_file()

    def test_ordering_second_session_warns_unfilled(self, tmp_path: Path):
        """Second session: file exists (placed by sync) but unfilled: still warns."""
        fw = _setup_framework(tmp_path)
        product = _setup_legacy_product(tmp_path, fw)
        (product / "app.py").write_text("print('hello')")

        # First session: sync places the file
        run_hook("clear", product, env_extra={
            "PRAWDUCT_FRAMEWORK_DIR": str(fw),
        })

        # Verify file was placed and is unfilled
        prefs = product / ".prawduct" / "artifacts" / "project-preferences.md"
        assert prefs.is_file()
        assert UNFILLED_MARKER in prefs.read_text()

        # Second session: file exists but unfilled
        result = run_hook("clear", product, env_extra={
            "PRAWDUCT_FRAMEWORK_DIR": str(fw),
        })

        assert "CRITICAL" in result.stdout

    def test_ordering_third_session_no_warning_after_fill(self, tmp_path: Path):
        """Third session: file filled by user: no warning."""
        fw = _setup_framework(tmp_path)
        product = _setup_legacy_product(tmp_path, fw)
        (product / "app.py").write_text("print('hello')")

        # First session: sync places the file
        run_hook("clear", product, env_extra={
            "PRAWDUCT_FRAMEWORK_DIR": str(fw),
        })

        # User fills it
        prefs = product / ".prawduct" / "artifacts" / "project-preferences.md"
        prefs.write_text(
            "# Project Preferences\n\n## Language & Runtime\n\n"
            "- **Language**: Python 3.12\n"
        )

        # Third session: no warning
        result = run_hook("clear", product, env_extra={
            "PRAWDUCT_FRAMEWORK_DIR": str(fw),
        })

        assert "CRITICAL" not in result.stdout

    def test_warning_fires_when_sync_fails(self, tmp_path: Path):
        """When sync fails, the CRITICAL warning still appears (safety net)."""
        fw = _setup_framework(tmp_path)
        product = _setup_legacy_product(tmp_path, fw)
        (product / "app.py").write_text("print('hello')")

        # Break sync so it can't place the file
        (fw / "tools" / "prawduct-setup.py").write_text("THIS IS NOT PYTHON !!!")
        (fw / "tools" / "prawduct-sync.py").write_text("THIS IS NOT PYTHON !!!")

        result = run_hook("clear", product, env_extra={
            "PRAWDUCT_FRAMEWORK_DIR": str(fw),
        })

        # Warning should fire (preferences still missing)
        assert "CRITICAL" in result.stdout
        # File should still be missing (sync failed)
        prefs = product / ".prawduct" / "artifacts" / "project-preferences.md"
        assert not prefs.is_file()


# =============================================================================
# Cross-cutting consistency
# =============================================================================


class TestConsistency:
    """Verify init and sync produce identical content and detection works correctly."""

    def test_init_and_sync_produce_identical_content(self, tmp_path: Path):
        """Init and sync both use the same template, producing identical output."""
        # Init path
        init_dir = tmp_path / "init_project"
        init_dir.mkdir()
        run_init(str(init_dir), "TestApp")
        init_content = (
            init_dir / ".prawduct" / "artifacts" / "project-preferences.md"
        ).read_text()

        # Sync path
        fw = _setup_framework(tmp_path)
        product = _setup_legacy_product(tmp_path, fw, product_name="TestApp")
        run_sync(str(product), framework_dir=str(fw))
        sync_content = (
            product / ".prawduct" / "artifacts" / "project-preferences.md"
        ).read_text()

        assert init_content == sync_content

    def test_detection_string_matches_actual_template(self):
        """The unfilled marker used in the hook exists in the real template."""
        template_content = TEMPLATE_PATH.read_text()
        assert UNFILLED_MARKER in template_content

    def test_filled_preferences_dont_match_detection(self):
        """A properly filled preferences file doesn't contain the unfilled marker."""
        filled = (
            "# Project Preferences\n\n"
            "## Language & Runtime\n\n"
            "- **Language**: Python 3.12\n"
            "- **Version**: 3.12\n"
        )
        assert UNFILLED_MARKER not in filled
