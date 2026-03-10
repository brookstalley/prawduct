"""Tests for v5 migration logic (Chunk 5).

Covers: learnings split, project-state migration, v4→v5 auto-migration
via sync, v4→v5 via migrate, init v5 file structure, and idempotency.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

# Load modules
ROOT = Path(__file__).resolve().parent.parent

_sync_path = ROOT / "tools" / "prawduct-sync.py"
_sync_spec = importlib.util.spec_from_file_location("prawduct_sync", _sync_path)
_sync_mod = importlib.util.module_from_spec(_sync_spec)
_sync_spec.loader.exec_module(_sync_mod)

split_learnings_v5 = _sync_mod.split_learnings_v5
migrate_project_state_v5 = _sync_mod.migrate_project_state_v5
migrate_v4_to_v5 = _sync_mod.migrate_v4_to_v5
create_manifest = _sync_mod.create_manifest

_init_path = ROOT / "tools" / "prawduct-init.py"
_init_spec = importlib.util.spec_from_file_location("prawduct_init", _init_path)
_init_mod = importlib.util.module_from_spec(_init_spec)
_init_spec.loader.exec_module(_init_mod)

run_init = _init_mod.run_init
GITIGNORE_ENTRIES = _init_mod.GITIGNORE_ENTRIES

_migrate_path = ROOT / "tools" / "prawduct-migrate.py"
_migrate_spec = importlib.util.spec_from_file_location("prawduct_migrate", _migrate_path)
_migrate_mod = importlib.util.module_from_spec(_migrate_spec)
_migrate_spec.loader.exec_module(_migrate_mod)

detect_version = _migrate_mod.detect_version
run_migrate = _migrate_mod.run_migrate
V4_GITIGNORE_ENTRIES = _migrate_mod.V4_GITIGNORE_ENTRIES


# =============================================================================
# split_learnings_v5
# =============================================================================


class TestSplitLearnings:
    def test_creates_detail_from_existing_learnings(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        learnings = prawduct / "learnings.md"
        learnings.write_text(
            "# Learnings\n\n"
            "## Rule: Always run tests before committing\n"
            "Confirmed pattern from 3 incidents.\n"
        )

        actions = split_learnings_v5(tmp_path)

        assert len(actions) == 1
        assert "learnings-detail.md" in actions[0]
        detail = prawduct / "learnings-detail.md"
        assert detail.is_file()
        assert detail.read_text() == learnings.read_text()

    def test_skips_when_detail_exists(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "learnings.md").write_text("# Learnings\n\nSome content.\n")
        (prawduct / "learnings-detail.md").write_text("# Detail\n\nExisting.\n")

        actions = split_learnings_v5(tmp_path)

        assert actions == []

    def test_splits_starter_content(self, tmp_path: Path):
        """Even the default starter text triggers a split (cheap backup)."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "learnings.md").write_text(
            "# Learnings\n\nAccumulated wisdom from building this product.\n"
        )

        actions = split_learnings_v5(tmp_path)

        assert len(actions) == 1
        assert (prawduct / "learnings-detail.md").is_file()

    def test_skips_header_only_learnings(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "learnings.md").write_text("# Learnings\n")

        actions = split_learnings_v5(tmp_path)

        assert actions == []

    def test_skips_missing_learnings(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()

        actions = split_learnings_v5(tmp_path)

        assert actions == []

    def test_idempotent(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "learnings.md").write_text(
            "# Learnings\n\nReal content here.\n"
        )

        split_learnings_v5(tmp_path)
        actions = split_learnings_v5(tmp_path)

        assert actions == []

    def test_preserves_original_learnings(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        original = "# Learnings\n\n## Rule: Test first\n\nAlways.\n"
        (prawduct / "learnings.md").write_text(original)

        split_learnings_v5(tmp_path)

        assert (prawduct / "learnings.md").read_text() == original


# =============================================================================
# migrate_project_state_v5
# =============================================================================


class TestMigrateProjectState:
    def _make_v4_state(self, tmp_path: Path, content: str | None = None) -> Path:
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir(exist_ok=True)
        state = prawduct / "project-state.yaml"
        if content is None:
            content = (
                "# Project State\n\n"
                "classification:\n"
                "  domain: utility\n\n"
                "current_phase: building\n\n"
                "build_plan:\n"
                "  strategy: null\n"
            )
        state.write_text(content)
        return state

    def test_removes_current_phase(self, tmp_path: Path):
        state = self._make_v4_state(tmp_path)

        actions = migrate_project_state_v5(tmp_path)

        content = state.read_text()
        assert "current_phase:" not in content
        assert len(actions) == 1

    def test_adds_work_in_progress(self, tmp_path: Path):
        state = self._make_v4_state(tmp_path)

        migrate_project_state_v5(tmp_path)

        content = state.read_text()
        assert "work_in_progress:" in content
        assert "description: null" in content
        assert "size: null" in content
        assert "type: null" in content

    def test_adds_health_check(self, tmp_path: Path):
        state = self._make_v4_state(tmp_path)

        migrate_project_state_v5(tmp_path)

        content = state.read_text()
        assert "health_check:" in content
        assert "last_full_check: null" in content
        assert "last_check_findings: null" in content

    def test_preserves_existing_content(self, tmp_path: Path):
        state = self._make_v4_state(tmp_path)

        migrate_project_state_v5(tmp_path)

        content = state.read_text()
        assert "classification:" in content
        assert "domain: utility" in content
        assert "build_plan:" in content

    def test_idempotent(self, tmp_path: Path):
        self._make_v4_state(tmp_path)

        migrate_project_state_v5(tmp_path)
        actions = migrate_project_state_v5(tmp_path)

        assert actions == []

    def test_skips_missing_file(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()

        actions = migrate_project_state_v5(tmp_path)

        assert actions == []

    def test_handles_null_current_phase(self, tmp_path: Path):
        state = self._make_v4_state(
            tmp_path, "classification:\n  domain: null\n\ncurrent_phase: null\n"
        )

        migrate_project_state_v5(tmp_path)

        content = state.read_text()
        assert "current_phase:" not in content
        assert "work_in_progress:" in content

    def test_skips_if_already_v5(self, tmp_path: Path):
        """File with work_in_progress and health_check and no current_phase."""
        self._make_v4_state(
            tmp_path,
            "classification:\n  domain: null\n\n"
            "work_in_progress:\n  description: null\n\n"
            "health_check:\n  last_full_check: null\n",
        )

        actions = migrate_project_state_v5(tmp_path)

        assert actions == []

    def test_handles_current_phase_at_start(self, tmp_path: Path):
        """current_phase at the very start of file."""
        state = self._make_v4_state(
            tmp_path, "current_phase: discovery\n\nclassification:\n  domain: null\n"
        )

        migrate_project_state_v5(tmp_path)

        content = state.read_text()
        assert "current_phase:" not in content
        assert "classification:" in content


# =============================================================================
# migrate_v4_to_v5 (sync auto-migration)
# =============================================================================


class TestMigrateV4ToV5:
    def _make_v4_product(self, tmp_path: Path) -> Path:
        """Create a minimal v4 product with format_version 1 manifest."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "classification:\n  domain: null\n\ncurrent_phase: building\n"
        )
        (prawduct / "learnings.md").write_text(
            "# Learnings\n\n## Rule: Test first\n\nAlways test.\n"
        )
        manifest = {
            "format_version": 1,
            "framework_source": str(ROOT),
            "product_name": "TestProduct",
            "files": {},
        }
        (prawduct / "sync-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        return tmp_path

    def test_full_migration(self, tmp_path: Path):
        product = self._make_v4_product(tmp_path)

        actions = migrate_v4_to_v5(product)

        assert len(actions) >= 2
        # Learnings detail created
        assert (product / ".prawduct" / "learnings-detail.md").is_file()
        # Project state updated
        state = (product / ".prawduct" / "project-state.yaml").read_text()
        assert "work_in_progress:" in state
        assert "health_check:" in state
        assert "current_phase:" not in state
        # Manifest version bumped
        manifest = json.loads(
            (product / ".prawduct" / "sync-manifest.json").read_text()
        )
        assert manifest["format_version"] == 2

    def test_skips_v5_product(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        manifest = {"format_version": 2, "files": {}}
        (prawduct / "sync-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )

        actions = migrate_v4_to_v5(tmp_path)

        assert actions == []

    def test_skips_no_manifest(self, tmp_path: Path):
        actions = migrate_v4_to_v5(tmp_path)

        assert actions == []

    def test_idempotent(self, tmp_path: Path):
        product = self._make_v4_product(tmp_path)

        migrate_v4_to_v5(product)
        actions = migrate_v4_to_v5(product)

        assert actions == []

    def test_handles_invalid_manifest(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "sync-manifest.json").write_text("not json")

        actions = migrate_v4_to_v5(tmp_path)

        assert actions == []


# =============================================================================
# Init v5 file structure
# =============================================================================


class TestInitV5Structure:
    def test_creates_boundary_patterns(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")

        bp = tmp_path / ".prawduct" / "artifacts" / "boundary-patterns.md"
        assert bp.is_file()
        content = bp.read_text()
        assert "Contract Surfaces" in content
        assert "TestProduct" in content
        assert "{{PRODUCT_NAME}}" not in content

    def test_boundary_patterns_not_overwritten(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")

        bp = tmp_path / ".prawduct" / "artifacts" / "boundary-patterns.md"
        bp.write_text("# Custom boundary patterns\n")

        result = run_init(str(tmp_path), "TestProduct")

        assert bp.read_text() == "# Custom boundary patterns\n"
        assert not any("boundary-patterns" in a for a in result["actions"])

    def test_manifest_is_v5(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")

        manifest = json.loads(
            (tmp_path / ".prawduct" / "sync-manifest.json").read_text()
        )
        assert manifest["format_version"] == 2

    def test_gitignore_has_subagent_briefing(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")

        content = (tmp_path / ".gitignore").read_text()
        assert ".prawduct/.subagent-briefing.md" in content

    def test_project_state_has_v5_sections(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")

        content = (tmp_path / ".prawduct" / "project-state.yaml").read_text()
        assert "work_in_progress:" in content
        assert "health_check:" in content
        assert "current_phase:" not in content

    def test_boundary_patterns_action_reported(self, tmp_path: Path):
        result = run_init(str(tmp_path), "TestProduct")

        assert any("boundary-patterns.md" in a for a in result["actions"])


# =============================================================================
# Migrate v4→v5 via run_migrate
# =============================================================================


class TestRunMigrateV5:
    def _make_v4_repo(self, tmp_path: Path, name: str = "TestProduct") -> Path:
        """Create a minimal v4 repo with format_version 1."""
        repo = tmp_path / "myrepo"
        repo.mkdir()
        prawduct = repo / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            f'product_identity:\n    name: "{name}"\n\n'
            "current_phase: building\n\n"
            "build_plan:\n  strategy: null\n"
        )
        (prawduct / "learnings.md").write_text(
            "# Learnings\n\n## Rule: Test first\n\nAlways test.\n"
        )
        (repo / "CLAUDE.md").write_text("# CLAUDE.md\n\n## What This Is\n\nV4 content.\n")
        tools = repo / "tools"
        tools.mkdir()
        hook_src = ROOT / "tools" / "product-hook"
        if hook_src.is_file():
            (tools / "product-hook").write_bytes(hook_src.read_bytes())
        else:
            (tools / "product-hook").write_text("#!/usr/bin/env python3\n# v4 hook")
        import stat
        (tools / "product-hook").chmod(
            (tools / "product-hook").stat().st_mode | stat.S_IXUSR
        )
        claude_dir = repo / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"matcher": "clear", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" clear"}
                ]}],
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" stop"}
                ]}],
            }
        }, indent=2))
        manifest = {
            "format_version": 1,
            "framework_source": str(ROOT),
            "product_name": name,
            "auto_pull": False,
            "files": {
                "CLAUDE.md": {
                    "template": "templates/product-claude.md",
                    "strategy": "block_template",
                    "generated_hash": "old_hash",
                },
                ".prawduct/critic-review.md": {
                    "template": "templates/critic-review.md",
                    "strategy": "template",
                    "generated_hash": "old_hash",
                },
                "tools/product-hook": {
                    "source": "tools/product-hook",
                    "strategy": "always_update",
                    "generated_hash": "old_hash",
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
        return repo

    def test_v4_to_v5_migration(self, tmp_path: Path):
        repo = self._make_v4_repo(tmp_path)

        result = run_migrate(str(repo))

        assert result["version_before"] == "v4"
        assert result["version_after"] == "v5"

    def test_v4_to_v5_creates_learnings_detail(self, tmp_path: Path):
        repo = self._make_v4_repo(tmp_path)

        run_migrate(str(repo))

        assert (repo / ".prawduct" / "learnings-detail.md").is_file()

    def test_v4_to_v5_updates_project_state(self, tmp_path: Path):
        repo = self._make_v4_repo(tmp_path)

        run_migrate(str(repo))

        state = (repo / ".prawduct" / "project-state.yaml").read_text()
        assert "work_in_progress:" in state
        assert "health_check:" in state
        assert "current_phase:" not in state

    def test_v4_to_v5_creates_boundary_patterns(self, tmp_path: Path):
        repo = self._make_v4_repo(tmp_path)

        run_migrate(str(repo))

        bp = repo / ".prawduct" / "artifacts" / "boundary-patterns.md"
        assert bp.is_file()
        assert "Contract Surfaces" in bp.read_text()

    def test_v4_to_v5_bumps_manifest_version(self, tmp_path: Path):
        repo = self._make_v4_repo(tmp_path)

        run_migrate(str(repo))

        manifest = json.loads(
            (repo / ".prawduct" / "sync-manifest.json").read_text()
        )
        assert manifest["format_version"] == 2

    def test_v4_to_v5_adds_gitignore_entries(self, tmp_path: Path):
        repo = self._make_v4_repo(tmp_path)
        (repo / ".gitignore").write_text("node_modules/\n")

        run_migrate(str(repo))

        content = (repo / ".gitignore").read_text()
        assert ".prawduct/.subagent-briefing.md" in content

    def test_v4_to_v5_preserves_user_content(self, tmp_path: Path):
        repo = self._make_v4_repo(tmp_path)

        run_migrate(str(repo))

        state = (repo / ".prawduct" / "project-state.yaml").read_text()
        assert 'name: "TestProduct"' in state
        assert "build_plan:" in state

    def test_v4_to_v5_idempotent(self, tmp_path: Path):
        repo = self._make_v4_repo(tmp_path)

        run_migrate(str(repo))
        result = run_migrate(str(repo))

        assert result["actions"] == []
        assert result["version_before"] == "v5"
        assert result["version_after"] == "v5"

    def test_v1_to_v5_full_path(self, tmp_path: Path):
        """v1 repos migrate all the way to v5."""
        repo = tmp_path / "myrepo"
        repo.mkdir()
        prawduct = repo / ".prawduct"
        prawduct.mkdir()
        (prawduct / "framework-path").write_text(str(ROOT))
        (prawduct / "framework-version").write_text("1.0")
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n    name: "LegacyApp"\n\ncurrent_phase: discovery\n'
        )
        (prawduct / "learnings.md").write_text(
            "# Learnings\n\n## Rule: Check errors\n\nImportant.\n"
        )
        (repo / "CLAUDE.md").write_text("# Old CLAUDE.md\nLegacy content.\n")
        (repo / ".claude").mkdir()
        (repo / ".claude" / "settings.json").write_text(json.dumps({
            "hooks": {
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "$(cat .prawduct/framework-path)/tools/governance-hook stop"}
                ]}],
            }
        }, indent=2))

        result = run_migrate(str(repo))

        assert result["version_before"] == "v1"
        assert result["version_after"] == "v5"
        # v5 structure present
        assert (repo / ".prawduct" / "learnings-detail.md").is_file()
        state = (repo / ".prawduct" / "project-state.yaml").read_text()
        assert "work_in_progress:" in state
        assert "current_phase:" not in state
        manifest = json.loads(
            (repo / ".prawduct" / "sync-manifest.json").read_text()
        )
        assert manifest["format_version"] == 2


# =============================================================================
# Sync with v5 migration
# =============================================================================


class TestSyncV5Migration:
    def _make_v4_product_for_sync(self, tmp_path: Path) -> Path:
        """Create a v4 product that run_sync can process."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n    name: "SyncTest"\n\n'
            "current_phase: building\n"
        )
        (prawduct / "learnings.md").write_text(
            "# Learnings\n\n## Rule: Sync works\n\nConfirmed.\n"
        )
        manifest = {
            "format_version": 1,
            "framework_source": str(ROOT),
            "product_name": "SyncTest",
            "auto_pull": False,
            "files": {},
        }
        (prawduct / "sync-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        return tmp_path

    def test_sync_triggers_v5_migration(self, tmp_path: Path):
        product = self._make_v4_product_for_sync(tmp_path)

        result = _sync_mod.run_sync(
            str(product), str(ROOT), no_pull=True
        )

        assert result["synced"] is True
        # Manifest should be v5 now
        manifest = json.loads(
            (product / ".prawduct" / "sync-manifest.json").read_text()
        )
        assert manifest["format_version"] == 2

    def test_sync_creates_learnings_detail(self, tmp_path: Path):
        product = self._make_v4_product_for_sync(tmp_path)

        _sync_mod.run_sync(str(product), str(ROOT), no_pull=True)

        assert (product / ".prawduct" / "learnings-detail.md").is_file()

    def test_sync_updates_project_state(self, tmp_path: Path):
        product = self._make_v4_product_for_sync(tmp_path)

        _sync_mod.run_sync(str(product), str(ROOT), no_pull=True)

        state = (product / ".prawduct" / "project-state.yaml").read_text()
        assert "work_in_progress:" in state
        assert "current_phase:" not in state

    def test_sync_no_migration_for_v5(self, tmp_path: Path):
        """v5 products skip migration during sync."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        manifest = {
            "format_version": 2,
            "framework_source": str(ROOT),
            "product_name": "V5Product",
            "auto_pull": False,
            "files": {},
        }
        (prawduct / "sync-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )

        result = _sync_mod.run_sync(str(tmp_path), str(ROOT), no_pull=True)

        # No migration actions
        assert not any("v5" in a.lower() for a in result["actions"])

    def test_sync_places_boundary_patterns(self, tmp_path: Path):
        """Sync places boundary-patterns.md via place_once."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        manifest = {
            "format_version": 2,
            "framework_source": str(ROOT),
            "product_name": "BPTest",
            "auto_pull": False,
            "files": {},
        }
        (prawduct / "sync-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )

        result = _sync_mod.run_sync(str(tmp_path), str(ROOT), no_pull=True)

        bp = tmp_path / ".prawduct" / "artifacts" / "boundary-patterns.md"
        assert bp.is_file()
        assert "BPTest" in bp.read_text()


# =============================================================================
# Gitignore v5 entries
# =============================================================================


class TestGitignoreV5:
    def test_init_gitignore_has_subagent_briefing(self):
        assert ".prawduct/.subagent-briefing.md" in GITIGNORE_ENTRIES

    def test_migrate_gitignore_has_subagent_briefing(self):
        assert ".prawduct/.subagent-briefing.md" in V4_GITIGNORE_ENTRIES

    def test_migrate_gitignore_has_reflections(self):
        assert ".prawduct/reflections.md" in V4_GITIGNORE_ENTRIES


# =============================================================================
# create_manifest format_version
# =============================================================================


class TestCreateManifestV5:
    def test_format_version_is_2(self, tmp_path: Path):
        manifest = create_manifest(tmp_path, ROOT, "Test", {})
        assert manifest["format_version"] == 2
