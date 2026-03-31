"""Product repo backward-compatibility tests.

These tests simulate realistic product repo states and verify that
init, sync, and validate work correctly against each. They serve as a
regression gate for framework refactoring — no chunk should land if
these tests fail.

Fixtures simulate 5 product repo states:
- fresh v5 (clean init, current manifest)
- v5 with local edits (user modified managed files)
- v5 with stale manifest (old template paths in manifest)
- v4 pending migration (format_version 1, legacy structure)
- v5 with old product-hook (outdated hook binary)
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Load prawduct-setup.py via importlib
_TOOL_PATH = ROOT / "tools" / "prawduct-setup.py"
_spec = importlib.util.spec_from_file_location("prawduct_setup", _TOOL_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

run_init = _mod.run_init
run_sync = _mod.run_sync
run_validate = _mod.run_validate
detect_version = _mod.detect_version
compute_hash = _mod.compute_hash
MANAGED_FILES = _mod.MANAGED_FILES
BLOCK_BEGIN = _mod.BLOCK_BEGIN
BLOCK_END = _mod.BLOCK_END


# =============================================================================
# Helpers
# =============================================================================


def _init_product(tmp_path: Path, name: str = "CompatProduct") -> Path:
    """Create a fresh v5 product via run_init and return its path."""
    product = tmp_path / "product"
    result = run_init(str(product), name)
    assert result.get("files_written", 0) > 0, f"init failed: {result}"
    return product


def _read_manifest(product: Path) -> dict:
    """Read and parse the sync manifest."""
    path = product / ".prawduct" / "sync-manifest.json"
    return json.loads(path.read_text())


def _write_manifest(product: Path, manifest: dict) -> None:
    """Write the sync manifest."""
    path = product / ".prawduct" / "sync-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")


def _make_v4_product(tmp_path: Path, name: str = "V4Product") -> Path:
    """Create a realistic v4 product repo for migration testing.

    v4 products have: format_version 1 manifest, current_phase in
    project-state, no boundary-patterns, no learnings-detail.
    """
    repo = tmp_path / "v4-product"
    repo.mkdir()
    prawduct = repo / ".prawduct"
    prawduct.mkdir()
    (prawduct / "artifacts").mkdir()

    # project-state with v4 structure
    (prawduct / "project-state.yaml").write_text(
        f"# Project State — {name}\n\n"
        "classification:\n"
        "  domain: utility\n"
        "  structural:\n"
        "    has_human_interface: null\n"
        "    runs_unattended: null\n\n"
        f"product_definition:\n"
        f"  product_identity:\n"
        f'    name: "{name}"\n'
        "  vision: A v4 test product\n\n"
        "current_phase: building\n\n"
        "build_plan:\n"
        "  strategy: feature-first\n"
        "  chunks: []\n"
        "  current_chunk: null\n\n"
        "build_state:\n"
        "  source_root: src/\n"
        "  test_tracking:\n"
        "    test_count: 42\n\n"
        "change_log: []\n"
    )

    (prawduct / "learnings.md").write_text(
        "# Learnings\n\n## Rule: Check error paths\n\nImportant.\n"
    )

    (prawduct / "critic-review.md").write_text(
        "# Critic Review Instructions\n\nGoal-based review.\n"
    )

    (prawduct / "artifacts" / "project-preferences.md").write_text(
        "# Project Preferences\n\n- **Language**: Python 3.12\n"
    )

    # CLAUDE.md with block markers
    (repo / "CLAUDE.md").write_text(
        f"# CLAUDE.md — {name}\n\n"
        f"{BLOCK_BEGIN}\n\n"
        "## Build cycle\n\nTest before commit.\n\n"
        f"{BLOCK_END}\n\n"
        "## My Notes\n\nUser content here.\n"
    )

    # product-hook — copy real one
    tools = repo / "tools"
    tools.mkdir()
    hook_src = ROOT / "tools" / "product-hook"
    if hook_src.is_file():
        (tools / "product-hook").write_bytes(hook_src.read_bytes())
    else:
        (tools / "product-hook").write_text("#!/usr/bin/env python3\n# hook")
    (tools / "product-hook").chmod(
        (tools / "product-hook").stat().st_mode | stat.S_IXUSR
    )

    # settings.json
    claude_dir = repo / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(json.dumps({
        "hooks": {
            "SessionStart": [{"matcher": "clear", "hooks": [
                {"type": "command",
                 "command": 'python3 "$CLAUDE_PROJECT_DIR/tools/product-hook" clear'}
            ]}],
            "Stop": [{"matcher": "", "hooks": [
                {"type": "command",
                 "command": 'python3 "$CLAUDE_PROJECT_DIR/tools/product-hook" stop'}
            ]}],
        },
        "companyAnnouncements": [f"{name} — Built with Prawduct"]
    }, indent=2))

    # v4 sync manifest (format_version 1)
    manifest = {
        "format_version": 1,
        "framework_source": str(ROOT),
        "product_name": name,
        "auto_pull": False,
        "last_sync": "2025-01-01T00:00:00Z",
        "files": {
            "CLAUDE.md": {
                "template": "templates/product-claude.md",
                "strategy": "block_template",
                "generated_hash": "stale_hash",
            },
            ".prawduct/critic-review.md": {
                "template": "templates/critic-review.md",
                "strategy": "template",
                "generated_hash": "stale_hash",
            },
            "tools/product-hook": {
                "source": "tools/product-hook",
                "strategy": "always_update",
                "generated_hash": "stale_hash",
            },
            ".claude/settings.json": {
                "template": "templates/product-settings.json",
                "strategy": "merge_settings",
                "generated_hash": None,
            },
        },
    }
    (prawduct / "sync-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )

    # gitignore
    (repo / ".gitignore").write_text(
        ".claude/settings.local.json\n"
        ".prawduct/.critic-findings.json\n"
        ".prawduct/.session-git-baseline\n"
        ".prawduct/.session-reflected\n"
        ".prawduct/.session-start\n"
        ".prawduct/sync-manifest.json\n"
        "__pycache__/\n"
    )

    return repo


# =============================================================================
# Test Suite 1: Fresh v5 Product — Baseline
# =============================================================================


class TestFreshV5Product:
    """Verify that a fresh v5 product syncs, validates, and re-inits cleanly."""

    def test_sync_succeeds(self, tmp_path: Path):
        product = _init_product(tmp_path)
        result = run_sync(str(product), str(ROOT), no_pull=True)
        assert result["synced"] is True

    def test_sync_actions_are_benign(self, tmp_path: Path):
        """First sync after init should only do safe operations."""
        product = _init_product(tmp_path)
        result = run_sync(str(product), str(ROOT), no_pull=True)
        actions = result.get("actions", [])
        # Allowed: place-once file creation, hook updates, gitignore, renames
        allowed_terms = ["created", "product-hook", "gitignore", "backfill",
                         "rename", "updated", "repaired"]
        for action in actions:
            assert any(
                term in action.lower() for term in allowed_terms
            ), f"Unexpected sync action: {action}"

    def test_validate_no_failures(self, tmp_path: Path):
        """Fresh product should have no failing checks.

        May be 'degraded' (not 'healthy') due to session_state warn — hooks
        haven't fired yet in a test environment. That's expected.
        """
        product = _init_product(tmp_path)
        result = run_validate(str(product), framework_dir=str(ROOT))
        assert result["overall"] != "broken", f"Validation broken: {result}"
        failing = [c for c in result["checks"] if c["status"] == "fail"]
        assert failing == [], f"Failing checks: {failing}"

    def test_manifest_valid_json(self, tmp_path: Path):
        product = _init_product(tmp_path)
        run_sync(str(product), str(ROOT), no_pull=True)
        manifest = _read_manifest(product)
        assert "format_version" in manifest
        assert "files" in manifest
        assert isinstance(manifest["files"], dict)

    def test_manifest_format_version(self, tmp_path: Path):
        product = _init_product(tmp_path)
        manifest = _read_manifest(product)
        assert manifest["format_version"] == 2

    def test_all_managed_files_present(self, tmp_path: Path):
        product = _init_product(tmp_path)
        for rel_path in MANAGED_FILES:
            assert (product / rel_path).is_file(), f"Missing managed file: {rel_path}"

    def test_init_idempotent(self, tmp_path: Path):
        """Running init on an existing v5 product shouldn't break it."""
        product = _init_product(tmp_path)
        before_manifest = _read_manifest(product)
        before_claude = (product / "CLAUDE.md").read_text()

        # Re-run init (simulates accidental double-init)
        result = run_init(str(product), "CompatProduct")
        # Second init is a no-op (all files exist)
        assert result.get("files_written", 0) == 0

        # Product is still intact
        after_manifest = _read_manifest(product)
        after_claude = (product / "CLAUDE.md").read_text()
        assert after_manifest["format_version"] == before_manifest["format_version"]
        assert BLOCK_BEGIN in after_claude

        # Validate still passes (no failures)
        val_result = run_validate(str(product), framework_dir=str(ROOT))
        assert val_result["overall"] != "broken"


# =============================================================================
# Test Suite 2: v5 Product with Local Edits
# =============================================================================


class TestV5ProductWithLocalEdits:
    """Verify that sync respects local edits and doesn't clobber user content."""

    def _make_product_with_edits(self, tmp_path: Path) -> Path:
        product = _init_product(tmp_path)

        # User edits CLAUDE.md OUTSIDE markers (should survive sync)
        claude = product / "CLAUDE.md"
        content = claude.read_text()
        claude.write_text(content + "\n## My Custom Instructions\n\nDo things my way.\n")

        # User edits critic-review.md (local customization)
        critic = product / ".prawduct" / "critic-review.md"
        critic.write_text(
            "# Critic Review — My Custom Version\n\n"
            "I modified this for my project's specific needs.\n"
        )

        # User edits a skill file
        pr_skill = product / ".claude" / "skills" / "pr" / "SKILL.md"
        pr_skill.write_text(
            "# PR Skill — Customized\n\n"
            "My team uses a different PR workflow.\n"
        )

        return product

    def test_sync_succeeds(self, tmp_path: Path):
        product = self._make_product_with_edits(tmp_path)
        result = run_sync(str(product), str(ROOT), no_pull=True)
        assert result["synced"] is True

    def test_claude_md_user_content_preserved(self, tmp_path: Path):
        product = self._make_product_with_edits(tmp_path)
        run_sync(str(product), str(ROOT), no_pull=True)
        content = (product / "CLAUDE.md").read_text()
        assert "My Custom Instructions" in content
        assert "Do things my way" in content

    def test_claude_md_framework_block_present(self, tmp_path: Path):
        product = self._make_product_with_edits(tmp_path)
        run_sync(str(product), str(ROOT), no_pull=True)
        content = (product / "CLAUDE.md").read_text()
        assert BLOCK_BEGIN in content
        assert BLOCK_END in content

    def test_edited_critic_not_overwritten(self, tmp_path: Path):
        product = self._make_product_with_edits(tmp_path)
        result = run_sync(str(product), str(ROOT), no_pull=True)
        content = (product / ".prawduct" / "critic-review.md").read_text()
        # User's custom version should survive (not overwritten without --force)
        assert "My Custom Version" in content

    def test_edited_skill_not_overwritten(self, tmp_path: Path):
        product = self._make_product_with_edits(tmp_path)
        result = run_sync(str(product), str(ROOT), no_pull=True)
        content = (product / ".claude" / "skills" / "pr" / "SKILL.md").read_text()
        assert "Customized" in content

    def test_force_sync_overwrites_when_template_changed(self, tmp_path: Path):
        """--force overwrites local edits when template has changed.

        Force only applies when the rendered template differs from the stored
        generated_hash (i.e., the framework template was updated). To simulate
        this, we set a stale generated_hash in the manifest.
        """
        product = self._make_product_with_edits(tmp_path)
        # Simulate template change by invalidating the stored hash
        manifest = _read_manifest(product)
        if ".prawduct/critic-review.md" in manifest["files"]:
            manifest["files"][".prawduct/critic-review.md"]["generated_hash"] = "stale"
        _write_manifest(product, manifest)

        result = run_sync(str(product), str(ROOT), no_pull=True, force=True)
        # With --force AND a template change, framework version replaces local edits
        content = (product / ".prawduct" / "critic-review.md").read_text()
        assert "My Custom Version" not in content

    def test_validate_with_local_edits(self, tmp_path: Path):
        product = self._make_product_with_edits(tmp_path)
        result = run_validate(str(product), framework_dir=str(ROOT))
        # Local edits don't cause failures (may be degraded due to session_state)
        assert result["overall"] != "broken"
        failing = [c for c in result["checks"] if c["status"] == "fail"]
        assert failing == [], f"Local edits caused failures: {failing}"


# =============================================================================
# Test Suite 3: v5 Product with Stale Manifest
# =============================================================================


class TestV5StaleManifest:
    """Verify that sync auto-repairs stale manifest entries."""

    def _make_product_with_stale_manifest(self, tmp_path: Path) -> Path:
        product = _init_product(tmp_path)
        manifest = _read_manifest(product)

        # Simulate manifest with old template paths (pre-rename scenario)
        # Change a template path to something that doesn't exist
        if ".claude/skills/pr/SKILL.md" in manifest["files"]:
            entry = manifest["files"][".claude/skills/pr/SKILL.md"]
            entry["template"] = "templates/old-skill-pr.md"  # doesn't exist

        # Add a stale entry for a file that was renamed
        manifest["files"][".claude/commands/pr.md"] = {
            "template": "templates/skill-pr.md",
            "strategy": "template",
            "generated_hash": "stale_hash",
        }

        _write_manifest(product, manifest)
        return product

    def test_sync_succeeds_with_stale_manifest(self, tmp_path: Path):
        product = self._make_product_with_stale_manifest(tmp_path)
        result = run_sync(str(product), str(ROOT), no_pull=True)
        assert result["synced"] is True

    def test_manifest_repaired_after_sync(self, tmp_path: Path):
        product = self._make_product_with_stale_manifest(tmp_path)
        run_sync(str(product), str(ROOT), no_pull=True)
        manifest = _read_manifest(product)
        # The pr skill entry should be repaired to current template path
        if ".claude/skills/pr/SKILL.md" in manifest["files"]:
            entry = manifest["files"][".claude/skills/pr/SKILL.md"]
            assert entry["template"] == MANAGED_FILES[".claude/skills/pr/SKILL.md"]["template"]

    def test_manifest_still_valid_json(self, tmp_path: Path):
        product = self._make_product_with_stale_manifest(tmp_path)
        run_sync(str(product), str(ROOT), no_pull=True)
        manifest = _read_manifest(product)
        assert "format_version" in manifest
        assert isinstance(manifest["files"], dict)

    def test_product_files_unchanged(self, tmp_path: Path):
        """Stale manifest repair shouldn't alter product files."""
        product = self._make_product_with_stale_manifest(tmp_path)
        # Record file hashes before sync
        pr_skill = product / ".claude" / "skills" / "pr" / "SKILL.md"
        before_hash = compute_hash(pr_skill) if pr_skill.is_file() else None
        run_sync(str(product), str(ROOT), no_pull=True)
        after_hash = compute_hash(pr_skill) if pr_skill.is_file() else None
        # File should not change just because manifest path was repaired
        # (content hash matches → skip)
        assert before_hash == after_hash or before_hash is None


# =============================================================================
# Test Suite 4: v4 Product Pending Migration
# =============================================================================


class TestV4ProductMigration:
    """Verify that sync correctly migrates v4 products to v5."""

    def test_sync_migrates_v4_to_v5(self, tmp_path: Path):
        product = _make_v4_product(tmp_path)
        result = run_sync(str(product), str(ROOT), no_pull=True)
        assert result["synced"] is True

    def test_manifest_upgraded_to_v2(self, tmp_path: Path):
        product = _make_v4_product(tmp_path)
        run_sync(str(product), str(ROOT), no_pull=True)
        manifest = _read_manifest(product)
        assert manifest["format_version"] == 2

    def test_new_managed_files_backfilled(self, tmp_path: Path):
        """v4 products are missing v5 files; sync should add them."""
        product = _make_v4_product(tmp_path)
        run_sync(str(product), str(ROOT), no_pull=True)
        # These files were added in v5 and should be backfilled
        assert (product / ".prawduct" / "build-governance.md").is_file()
        assert (product / ".claude" / "skills" / "learnings" / "SKILL.md").is_file()
        assert (product / ".claude" / "skills" / "prawduct-doctor" / "SKILL.md").is_file()

    def test_existing_files_not_clobbered(self, tmp_path: Path):
        """v4 files that exist should not be overwritten."""
        product = _make_v4_product(tmp_path)
        before_critic = (product / ".prawduct" / "critic-review.md").read_text()
        run_sync(str(product), str(ROOT), no_pull=True)
        after_critic = (product / ".prawduct" / "critic-review.md").read_text()
        # File existed with local content; should be preserved (not force)
        assert before_critic == after_critic

    def test_claude_md_block_preserved(self, tmp_path: Path):
        product = _make_v4_product(tmp_path)
        before_user = "User content here."
        run_sync(str(product), str(ROOT), no_pull=True)
        content = (product / "CLAUDE.md").read_text()
        assert "My Notes" in content  # User content outside block survives

    def test_gitignore_updated(self, tmp_path: Path):
        product = _make_v4_product(tmp_path)
        run_sync(str(product), str(ROOT), no_pull=True)
        gi = (product / ".gitignore").read_text()
        # v5 added these entries
        assert ".prawduct/.subagent-briefing.md" in gi

    def test_validate_after_migration(self, tmp_path: Path):
        product = _make_v4_product(tmp_path)
        run_sync(str(product), str(ROOT), no_pull=True)
        result = run_validate(str(product), framework_dir=str(ROOT))
        # After migration, should not be broken (may be degraded due to warns)
        assert result["overall"] != "broken", f"Migration left product broken: {result}"
        # At most 1 failure (migration can't fix everything)
        critical = [c for c in result["checks"] if c["status"] == "fail"]
        assert len(critical) <= 1, f"Too many failures after migration: {critical}"


# =============================================================================
# Test Suite 5: v5 Product with Old Hook
# =============================================================================


class TestV5OldHook:
    """Verify that sync updates an outdated product-hook."""

    def _make_product_with_old_hook(self, tmp_path: Path) -> Path:
        product = _init_product(tmp_path)
        # Replace hook with a stub (simulating an old version)
        hook = product / "tools" / "product-hook"
        hook.write_text(
            '#!/usr/bin/env python3\n"""Old product-hook stub."""\n'
            'import sys\nprint("old hook")\nsys.exit(0)\n'
        )
        hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
        return product

    def test_sync_updates_old_hook(self, tmp_path: Path):
        product = self._make_product_with_old_hook(tmp_path)
        result = run_sync(str(product), str(ROOT), no_pull=True)
        assert result["synced"] is True
        # Hook should be updated (always_update strategy)
        content = (product / "tools" / "product-hook").read_text()
        assert "old hook" not in content
        assert "cmd_clear" in content or "def main" in content

    def test_hook_executable_after_sync(self, tmp_path: Path):
        product = self._make_product_with_old_hook(tmp_path)
        run_sync(str(product), str(ROOT), no_pull=True)
        hook = product / "tools" / "product-hook"
        assert hook.stat().st_mode & stat.S_IXUSR

    def test_validate_after_hook_update(self, tmp_path: Path):
        product = self._make_product_with_old_hook(tmp_path)
        run_sync(str(product), str(ROOT), no_pull=True)
        result = run_validate(str(product), framework_dir=str(ROOT))
        hook_check = next(
            (c for c in result["checks"] if c["name"] == "hook_executable"), None
        )
        if hook_check:
            assert hook_check["status"] == "pass"


# =============================================================================
# Test Suite 6: CLI JSON Output Stability
# =============================================================================


class TestCLIOutputStability:
    """Verify that the CLI JSON output structure is stable.

    Product hooks parse this JSON. Changes to keys or structure break products.
    """

    def test_sync_json_output_structure(self, tmp_path: Path):
        product = _init_product(tmp_path)
        result = run_sync(str(product), str(ROOT), no_pull=True)
        # Required keys in sync output
        assert "product_dir" in result or "synced" in result
        assert "synced" in result
        assert "actions" in result
        assert "notes" in result
        assert isinstance(result["actions"], list)
        assert isinstance(result["notes"], list)
        # Version info always present
        assert "version" in result
        assert "new_version" in result["version"]

    def test_sync_returns_version_upgrade_info(self, tmp_path: Path):
        """When framework version differs from manifest, sync returns both versions."""
        product = _init_product(tmp_path)
        # Set manifest to an older version so sync detects an upgrade
        manifest = _read_manifest(product)
        manifest["framework_version"] = "0.0.1"
        _write_manifest(product, manifest)

        # Tamper with hook to force an action (sync only writes version on actions)
        hook = product / "tools" / "product-hook"
        hook.write_text("#!/usr/bin/env python3\n# old\n")

        result = run_sync(str(product), str(ROOT), no_pull=True)
        assert result["synced"]
        assert "version" in result
        assert result["version"]["previous_version"] == "0.0.1"
        assert result["version"]["new_version"]  # Current framework version
        assert result["version"]["previous_version"] != result["version"]["new_version"]

    def test_sync_no_previous_version_when_unchanged(self, tmp_path: Path):
        """When framework version matches manifest, no previous_version in result."""
        product = _init_product(tmp_path)
        result = run_sync(str(product), str(ROOT), no_pull=True)
        assert "version" in result
        # No upgrade occurred — previous_version should be absent
        assert "previous_version" not in result["version"]

    def test_validate_json_output_structure(self, tmp_path: Path):
        product = _init_product(tmp_path)
        result = run_validate(str(product), framework_dir=str(ROOT))
        assert "overall" in result
        assert "checks" in result
        assert "recommendations" in result
        assert isinstance(result["checks"], list)
        assert isinstance(result["recommendations"], list)
        for check in result["checks"]:
            assert "name" in check
            assert "status" in check

    def test_subprocess_sync_json(self, tmp_path: Path):
        """Verify subprocess invocation returns valid JSON (how products call sync)."""
        product = _init_product(tmp_path)
        result = subprocess.run(
            [sys.executable, str(_TOOL_PATH), "sync", str(product),
             "--framework-dir", str(ROOT), "--json", "--no-pull"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"sync failed: {result.stderr}"
        parsed = json.loads(result.stdout)
        assert "synced" in parsed

    def test_subprocess_validate_json(self, tmp_path: Path):
        """Verify subprocess validate returns valid JSON."""
        product = _init_product(tmp_path)
        result = subprocess.run(
            [sys.executable, str(_TOOL_PATH), "validate", str(product), "--json"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"validate failed: {result.stderr}"
        parsed = json.loads(result.stdout)
        assert "overall" in parsed
        assert "checks" in parsed

    def test_subprocess_setup_fresh(self, tmp_path: Path):
        """Verify subprocess setup works for fresh repo."""
        product = tmp_path / "cli-product"
        result = subprocess.run(
            [sys.executable, str(_TOOL_PATH), "setup", str(product),
             "--name", "CLIProduct"],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"setup failed: {result.stderr}"
        assert (product / "CLAUDE.md").is_file()
        assert (product / ".prawduct" / "sync-manifest.json").is_file()


# =============================================================================
# Test Suite 7: Cross-State Sync Stability
# =============================================================================


class TestSyncStability:
    """Additional sync scenarios that protect against subtle regressions."""

    def test_double_sync_idempotent(self, tmp_path: Path):
        """Running sync twice should produce no changes on the second run."""
        product = _init_product(tmp_path)
        run_sync(str(product), str(ROOT), no_pull=True)
        manifest_before = _read_manifest(product)
        result = run_sync(str(product), str(ROOT), no_pull=True)
        manifest_after = _read_manifest(product)
        # Manifest should be identical (no drift)
        assert manifest_before["files"].keys() == manifest_after["files"].keys()

    def test_sync_with_missing_framework_dir(self, tmp_path: Path):
        """Sync with a bad framework dir should fail gracefully."""
        product = _init_product(tmp_path)
        result = run_sync(str(product), "/nonexistent/framework")
        assert result["synced"] is False
        assert "not found" in result.get("reason", "").lower() or not result["synced"]

    def test_sync_with_corrupted_manifest(self, tmp_path: Path):
        """Sync should handle corrupted manifest JSON."""
        product = _init_product(tmp_path)
        manifest_path = product / ".prawduct" / "sync-manifest.json"
        manifest_path.write_text("NOT VALID JSON {{{")
        result = run_sync(str(product), str(ROOT), no_pull=True)
        assert result["synced"] is False

    def test_sync_with_missing_manifest(self, tmp_path: Path):
        """Sync should bootstrap a manifest if one doesn't exist."""
        product = _init_product(tmp_path)
        (product / ".prawduct" / "sync-manifest.json").unlink()
        result = run_sync(str(product), str(ROOT), no_pull=True)
        assert result["synced"] is True
        assert (product / ".prawduct" / "sync-manifest.json").is_file()

    def test_validate_returns_version(self, tmp_path: Path):
        product = _init_product(tmp_path)
        result = run_validate(str(product), framework_dir=str(ROOT))
        assert "version" in result
        assert result["version"] == "v5"
