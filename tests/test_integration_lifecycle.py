"""Integration tests for the full product lifecycle.

Exercises the real init → sync → migrate pipeline end-to-end using
throwaway product repos. These tests catch regressions in how the tools
compose, not just how individual functions behave.

Run with: python -m pytest tests/test_integration_lifecycle.py -v
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Load prawduct-setup.py via importlib
_setup_path = ROOT / "tools" / "prawduct-setup.py"
_spec = importlib.util.spec_from_file_location("prawduct_setup", _setup_path)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

run_init = _mod.run_init
run_sync = _mod.run_sync
run_migrate = _mod.run_migrate
detect_version = _mod.detect_version
BLOCK_BEGIN = _mod.BLOCK_BEGIN
BLOCK_END = _mod.BLOCK_END


# =============================================================================
# Helpers
# =============================================================================


def make_v4_product(tmp_path: Path, name: str = "TestProduct") -> Path:
    """Create a realistic v4 product repo with all expected files.

    This simulates what a product looked like before v5: format_version 1
    manifest, current_phase in project-state, learnings with real content,
    no boundary-patterns, no learnings-detail.
    """
    repo = tmp_path / "my-product"
    repo.mkdir()
    prawduct = repo / ".prawduct"
    prawduct.mkdir()
    (prawduct / "artifacts").mkdir()

    # project-state.yaml with v4 structure (current_phase, no work_in_progress)
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
        "  vision: A test product\n\n"
        "current_phase: building\n\n"
        "build_plan:\n"
        "  strategy: feature-first\n"
        "  chunks: []\n"
        "  current_chunk: null\n\n"
        "build_state:\n"
        "  source_root: src/\n"
        "  test_tracking:\n"
        "    test_count: 12\n\n"
        "artifact_manifest:\n"
        "  artifacts: []\n\n"
        "change_log: []\n"
    )

    # Learnings with real content (should trigger split)
    (prawduct / "learnings.md").write_text(
        "# Learnings\n\n"
        "## Rule: Always check error paths\n"
        "Confirmed after 3 incidents where silent failures caused data loss.\n\n"
        "## Rule: Run the full test suite before committing\n"
        "Partial runs miss integration failures.\n\n"
        "## Provisional: Consider caching API responses\n"
        "Observed slow startup due to repeated API calls. Needs more data.\n"
    )

    # Critic review (v5 goal-based — already updated by earlier chunks)
    (prawduct / "critic-review.md").write_text(
        "# Critic Review Instructions\n\nGoal-based review.\n"
    )

    # Project preferences
    (prawduct / "artifacts" / "project-preferences.md").write_text(
        "# Project Preferences\n\n- **Language**: Python 3.12\n- **Testing**: pytest\n"
    )

    # CLAUDE.md with block markers
    (repo / "CLAUDE.md").write_text(
        f"# CLAUDE.md — {name}\n\n"
        f"{BLOCK_BEGIN}\n\n"
        "## Critical Rules\n\nTest before commit.\n\n"
        f"{BLOCK_END}\n\n"
        "## My Custom Notes\n\nUser-specific instructions here.\n"
    )

    # Product hook (copy real one)
    tools = repo / "tools"
    tools.mkdir()
    hook_src = ROOT / "tools" / "product-hook"
    if hook_src.is_file():
        (tools / "product-hook").write_bytes(hook_src.read_bytes())
    else:
        (tools / "product-hook").write_text("#!/usr/bin/env python3\n# hook")
    import stat
    (tools / "product-hook").chmod(
        (tools / "product-hook").stat().st_mode | stat.S_IXUSR
    )

    # Settings
    claude_dir = repo / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(json.dumps({
        "hooks": {
            "SessionStart": [{"matcher": "clear", "hooks": [
                {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/tools/product-hook" clear'}
            ]}],
            "Stop": [{"matcher": "", "hooks": [
                {"type": "command", "command": 'python3 "$CLAUDE_PROJECT_DIR/tools/product-hook" stop'}
            ]}],
        },
        "companyAnnouncements": [f"{name} — Built with Prawduct"]
    }, indent=2))

    # v4 sync manifest (format_version 1 — the key v4 marker)
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

    # Gitignore (v4 entries, missing v5 additions)
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


def make_v1_product(tmp_path: Path, name: str = "LegacyApp") -> Path:
    """Create a minimal v1 product repo (framework-dependent)."""
    repo = tmp_path / "legacy-app"
    repo.mkdir()
    prawduct = repo / ".prawduct"
    prawduct.mkdir()

    (prawduct / "framework-path").write_text(str(ROOT))
    (prawduct / "framework-version").write_text("1.0")
    (prawduct / "project-state.yaml").write_text(
        f'product_identity:\n    name: "{name}"\n\ncurrent_phase: discovery\n'
    )
    (prawduct / "learnings.md").write_text(
        "# Learnings\n\n## Rule: Check error codes\n\nImportant.\n"
    )
    (repo / "CLAUDE.md").write_text(
        "# Old CLAUDE.md\nSee framework-path for instructions.\n"
    )
    claude_dir = repo / ".claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(json.dumps({
        "hooks": {
            "Stop": [{"matcher": "", "hooks": [
                {"type": "command",
                 "command": "$(cat .prawduct/framework-path)/tools/governance-hook stop"}
            ]}],
        }
    }, indent=2))

    return repo


# =============================================================================
# Fresh v5 init
# =============================================================================


class TestFreshV5Init:
    """Init a brand-new product and verify full v5 structure."""

    def test_fresh_init_produces_complete_v5_product(self, tmp_path: Path):
        result = run_init(str(tmp_path / "fresh"), "FreshApp")

        repo = tmp_path / "fresh"
        assert result["files_written"] > 0

        # Core structure
        assert (repo / "CLAUDE.md").is_file()
        assert (repo / ".prawduct" / "project-state.yaml").is_file()
        assert (repo / ".prawduct" / "learnings.md").is_file()
        assert (repo / ".prawduct" / "critic-review.md").is_file()
        assert (repo / "tools" / "product-hook").is_file()
        assert (repo / ".claude" / "settings.json").is_file()
        assert (repo / ".gitignore").is_file()
        assert (repo / ".prawduct" / "sync-manifest.json").is_file()

        # v5-specific files
        assert (repo / ".prawduct" / "artifacts" / "boundary-patterns.md").is_file()
        assert (repo / ".prawduct" / "artifacts" / "project-preferences.md").is_file()

    def test_fresh_init_manifest_is_v5(self, tmp_path: Path):
        run_init(str(tmp_path / "fresh"), "FreshApp")
        manifest = json.loads(
            (tmp_path / "fresh" / ".prawduct" / "sync-manifest.json").read_text()
        )
        assert manifest["format_version"] == 2

    def test_fresh_init_project_state_is_v6(self, tmp_path: Path):
        run_init(str(tmp_path / "fresh"), "FreshApp")
        state = (tmp_path / "fresh" / ".prawduct" / "project-state.yaml").read_text()
        assert "health_check:" in state
        assert "build_state:" in state
        # v6: volatile state removed from project-state.yaml
        assert "work_in_progress:" not in state
        assert "build_plan:" not in state
        assert "current_phase:" not in state

    def test_fresh_init_gitignore_has_v5_entries(self, tmp_path: Path):
        run_init(str(tmp_path / "fresh"), "FreshApp")
        content = (tmp_path / "fresh" / ".gitignore").read_text()
        assert ".prawduct/.subagent-briefing.md" in content

    def test_fresh_init_claude_md_has_markers(self, tmp_path: Path):
        run_init(str(tmp_path / "fresh"), "FreshApp")
        content = (tmp_path / "fresh" / "CLAUDE.md").read_text()
        assert BLOCK_BEGIN in content
        assert BLOCK_END in content
        assert "FreshApp" in content

    def test_fresh_init_boundary_patterns_has_substitution(self, tmp_path: Path):
        run_init(str(tmp_path / "fresh"), "FreshApp")
        bp = (tmp_path / "fresh" / ".prawduct" / "artifacts" / "boundary-patterns.md")
        content = bp.read_text()
        assert "FreshApp" in content
        assert "{{PRODUCT_NAME}}" not in content

    def test_fresh_init_detected_as_v5(self, tmp_path: Path):
        run_init(str(tmp_path / "fresh"), "FreshApp")
        assert detect_version(tmp_path / "fresh") == "v5"

    def test_fresh_init_is_idempotent(self, tmp_path: Path):
        run_init(str(tmp_path / "fresh"), "FreshApp")
        result = run_init(str(tmp_path / "fresh"), "FreshApp")
        assert result["actions"] == []


# =============================================================================
# v4 → v5 via sync (auto-migration on session start)
# =============================================================================


class TestV4ToV5ViaSync:
    """Simulate session start on a v4 product — sync should auto-migrate."""

    def test_sync_migrates_v4_to_v5(self, tmp_path: Path):
        repo = make_v4_product(tmp_path)
        assert detect_version(repo) == "v4"

        result = run_sync(str(repo), str(ROOT), no_pull=True)

        assert result["synced"] is True
        assert detect_version(repo) == "v5"

    def test_sync_bumps_manifest_version(self, tmp_path: Path):
        repo = make_v4_product(tmp_path)

        run_sync(str(repo), str(ROOT), no_pull=True)

        manifest = json.loads(
            (repo / ".prawduct" / "sync-manifest.json").read_text()
        )
        assert manifest["format_version"] == 2

    def test_sync_creates_learnings_detail(self, tmp_path: Path):
        repo = make_v4_product(tmp_path)

        run_sync(str(repo), str(ROOT), no_pull=True)

        detail = repo / ".prawduct" / "learnings-detail.md"
        assert detail.is_file()
        content = detail.read_text()
        # Should contain the original learnings content
        assert "Always check error paths" in content
        assert "Run the full test suite" in content

    def test_sync_preserves_original_learnings(self, tmp_path: Path):
        repo = make_v4_product(tmp_path)
        original = (repo / ".prawduct" / "learnings.md").read_text()

        run_sync(str(repo), str(ROOT), no_pull=True)

        assert (repo / ".prawduct" / "learnings.md").read_text() == original

    def test_sync_updates_project_state(self, tmp_path: Path):
        repo = make_v4_product(tmp_path)

        run_sync(str(repo), str(ROOT), no_pull=True)

        state = (repo / ".prawduct" / "project-state.yaml").read_text()
        assert "work_in_progress:" in state
        assert "health_check:" in state
        assert "current_phase:" not in state
        # Preserves existing content
        assert "domain: utility" in state
        assert "feature-first" in state
        assert "test_count: 12" in state

    def test_sync_places_boundary_patterns(self, tmp_path: Path):
        repo = make_v4_product(tmp_path)

        run_sync(str(repo), str(ROOT), no_pull=True)

        bp = repo / ".prawduct" / "artifacts" / "boundary-patterns.md"
        assert bp.is_file()
        assert "Contract Surfaces" in bp.read_text()
        assert "TestProduct" in bp.read_text()

    def test_sync_preserves_user_claude_md_content(self, tmp_path: Path):
        repo = make_v4_product(tmp_path)

        run_sync(str(repo), str(ROOT), no_pull=True)

        content = (repo / "CLAUDE.md").read_text()
        assert "My Custom Notes" in content
        assert "User-specific instructions here." in content

    def test_sync_preserves_user_preferences(self, tmp_path: Path):
        repo = make_v4_product(tmp_path)

        run_sync(str(repo), str(ROOT), no_pull=True)

        prefs = (repo / ".prawduct" / "artifacts" / "project-preferences.md").read_text()
        assert "Python 3.12" in prefs

    def test_sync_migration_then_sync_is_idempotent(self, tmp_path: Path):
        repo = make_v4_product(tmp_path)

        # First sync: migration + template updates
        run_sync(str(repo), str(ROOT), no_pull=True)

        # Second sync: should be a no-op (no migration, no template changes)
        result = run_sync(str(repo), str(ROOT), no_pull=True)

        # No migration actions (already v5)
        assert not any("v5" in a.lower() or "migration" in a.lower()
                       for a in result["actions"])


# =============================================================================
# v4 → v5 via explicit migrate
# =============================================================================


class TestV4ToV5ViaMigrate:
    """Run prawduct-migrate.py on a v4 product."""

    def test_migrate_v4_to_v5(self, tmp_path: Path):
        repo = make_v4_product(tmp_path)

        result = run_migrate(str(repo))

        assert result["version_before"] == "v4"
        assert result["version_after"] == "v5"
        assert len(result["actions"]) > 0

    def test_migrate_creates_all_v5_artifacts(self, tmp_path: Path):
        repo = make_v4_product(tmp_path)

        run_migrate(str(repo))

        # Learnings split
        assert (repo / ".prawduct" / "learnings-detail.md").is_file()
        # Boundary patterns
        assert (repo / ".prawduct" / "artifacts" / "boundary-patterns.md").is_file()
        # Project state updated
        state = (repo / ".prawduct" / "project-state.yaml").read_text()
        assert "work_in_progress:" in state
        assert "health_check:" in state
        assert "current_phase:" not in state
        # Manifest bumped
        manifest = json.loads(
            (repo / ".prawduct" / "sync-manifest.json").read_text()
        )
        assert manifest["format_version"] == 2

    def test_migrate_is_idempotent(self, tmp_path: Path):
        repo = make_v4_product(tmp_path)

        run_migrate(str(repo))
        result = run_migrate(str(repo))

        assert result["actions"] == []
        assert result["version_before"] == "v5"
        assert result["version_after"] == "v5"


# =============================================================================
# v1 → v5 full legacy migration
# =============================================================================


class TestV1ToV5FullPath:
    """v1 repos should migrate all the way to v5 in one step."""

    def test_v1_migrates_to_v5(self, tmp_path: Path):
        repo = make_v1_product(tmp_path)
        assert detect_version(repo) == "v1"

        result = run_migrate(str(repo))

        assert result["version_before"] == "v1"
        assert result["version_after"] == "v5"

    def test_v1_gets_full_v5_structure(self, tmp_path: Path):
        repo = make_v1_product(tmp_path)

        run_migrate(str(repo))

        # v1 marker files gone
        assert not (repo / ".prawduct" / "framework-path").exists()
        # v5 structure present
        assert (repo / ".prawduct" / "learnings-detail.md").is_file()
        state = (repo / ".prawduct" / "project-state.yaml").read_text()
        assert "work_in_progress:" in state
        assert "current_phase:" not in state
        manifest = json.loads(
            (repo / ".prawduct" / "sync-manifest.json").read_text()
        )
        assert manifest["format_version"] == 2
        assert (repo / "tools" / "product-hook").is_file()
        assert BLOCK_BEGIN in (repo / "CLAUDE.md").read_text()

    def test_v1_migration_is_idempotent(self, tmp_path: Path):
        repo = make_v1_product(tmp_path)

        run_migrate(str(repo))
        result = run_migrate(str(repo))

        assert result["actions"] == []
        assert result["version_before"] == "v5"


# =============================================================================
# Version detection
# =============================================================================


class TestVersionDetection:
    """Verify detect_version correctly identifies all repo states."""

    def test_fresh_init_is_v5(self, tmp_path: Path):
        run_init(str(tmp_path / "fresh"), "Test")
        assert detect_version(tmp_path / "fresh") == "v5"

    def test_v4_product_is_v4(self, tmp_path: Path):
        repo = make_v4_product(tmp_path)
        assert detect_version(repo) == "v4"

    def test_v1_product_is_v1(self, tmp_path: Path):
        repo = make_v1_product(tmp_path)
        assert detect_version(repo) == "v1"

    def test_migrated_v4_is_v5(self, tmp_path: Path):
        repo = make_v4_product(tmp_path)
        run_migrate(str(repo))
        assert detect_version(repo) == "v5"

    def test_synced_v4_is_v5(self, tmp_path: Path):
        repo = make_v4_product(tmp_path)
        run_sync(str(repo), str(ROOT), no_pull=True)
        assert detect_version(repo) == "v5"

    def test_empty_dir_is_unknown(self, tmp_path: Path):
        (tmp_path / "empty").mkdir()
        assert detect_version(tmp_path / "empty") == "unknown"
