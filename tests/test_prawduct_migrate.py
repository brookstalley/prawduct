"""Tests for prawduct-migrate.py — the migration script.

Uses importlib to handle the hyphenated filename.
"""

from __future__ import annotations

import importlib.util
import json
import stat
from pathlib import Path

import pytest

# Load prawduct-migrate.py despite the hyphen in its name
_TOOL_PATH = Path(__file__).resolve().parent.parent / "tools" / "prawduct-migrate.py"
_spec = importlib.util.spec_from_file_location("prawduct_migrate", _TOOL_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

detect_version = _mod.detect_version
infer_product_name = _mod.infer_product_name
write_template_overwrite = _mod.write_template_overwrite
write_template_if_missing = _mod.write_template_if_missing
replace_settings = _mod.replace_settings
delete_v1_files = _mod.delete_v1_files
archive_v1_dirs = _mod.archive_v1_dirs
clean_v1_session_files = _mod.clean_v1_session_files
clean_gitignore = _mod.clean_gitignore
add_block_markers = _mod.add_block_markers
upgrade_manifest_strategy = _mod.upgrade_manifest_strategy
run_migrate = _mod.run_migrate
V1_GITIGNORE_ENTRIES = _mod.V1_GITIGNORE_ENTRIES
V3_GITIGNORE_ENTRIES = _mod.V3_GITIGNORE_ENTRIES
V4_GITIGNORE_ENTRIES = _mod.V4_GITIGNORE_ENTRIES
V1_SESSION_FILES = _mod.V1_SESSION_FILES
BLOCK_BEGIN = _mod.BLOCK_BEGIN
BLOCK_END = _mod.BLOCK_END
compute_block_hash = _mod.compute_block_hash


# =============================================================================
# detect_version
# =============================================================================


class TestDetectVersion:
    def test_v1_has_framework_path(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / ".prawduct" / "framework-path").write_text("/some/path")
        assert detect_version(tmp_path) == "v1"

    def test_v3_has_product_hook_no_manifest(self, tmp_path: Path):
        (tmp_path / "tools").mkdir()
        (tmp_path / "tools" / "product-hook").write_text("#!/bin/bash")
        assert detect_version(tmp_path) == "v3"

    def test_v4_has_product_hook_and_manifest(self, tmp_path: Path):
        (tmp_path / "tools").mkdir()
        (tmp_path / "tools" / "product-hook").write_text("#!/usr/bin/env python3")
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / ".prawduct" / "sync-manifest.json").write_text("{}")
        assert detect_version(tmp_path) == "v4"

    def test_unknown_has_neither(self, tmp_path: Path):
        assert detect_version(tmp_path) == "unknown"

    def test_partial_has_both(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / ".prawduct" / "framework-path").write_text("/some/path")
        (tmp_path / "tools").mkdir()
        (tmp_path / "tools" / "product-hook").write_text("#!/bin/bash")
        assert detect_version(tmp_path) == "partial"


# =============================================================================
# infer_product_name
# =============================================================================


class TestInferProductName:
    def test_quoted_name(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / ".prawduct" / "project-state.yaml").write_text(
            'product_identity:\n    name: "WorldGround"\n'
        )
        assert infer_product_name(tmp_path) == "WorldGround"

    def test_unquoted_name(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / ".prawduct" / "project-state.yaml").write_text(
            "product_identity:\n    name: MyApp\n"
        )
        assert infer_product_name(tmp_path) == "MyApp"

    def test_missing_file(self, tmp_path: Path):
        assert infer_product_name(tmp_path) is None

    def test_missing_field(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / ".prawduct" / "project-state.yaml").write_text(
            "product_identity:\n    personality: null\n"
        )
        assert infer_product_name(tmp_path) is None

    def test_template_placeholder(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / ".prawduct" / "project-state.yaml").write_text(
            'product_identity:\n    name: "{{PRODUCT_NAME}}"\n'
        )
        assert infer_product_name(tmp_path) is None


# =============================================================================
# write_template_overwrite
# =============================================================================


class TestWriteTemplateOverwrite:
    def test_creates_new_file(self, tmp_path: Path):
        src = tmp_path / "template.md"
        src.write_text("# {{PRODUCT_NAME}}")
        dst = tmp_path / "output" / "result.md"

        result = write_template_overwrite(src, dst, {"{{PRODUCT_NAME}}": "MyApp"})

        assert result is True
        assert dst.read_text() == "# MyApp"

    def test_overwrites_existing(self, tmp_path: Path):
        src = tmp_path / "template.md"
        src.write_text("# {{PRODUCT_NAME}} v3")
        dst = tmp_path / "result.md"
        dst.write_text("# Old v1 bootstrap content")

        result = write_template_overwrite(src, dst, {"{{PRODUCT_NAME}}": "MyApp"})

        assert result is True
        assert dst.read_text() == "# MyApp v3"

    def test_idempotent_same_content(self, tmp_path: Path):
        src = tmp_path / "template.md"
        src.write_text("# MyApp")
        dst = tmp_path / "result.md"
        dst.write_text("# MyApp")

        result = write_template_overwrite(src, dst, {})

        assert result is False


# =============================================================================
# write_template_if_missing
# =============================================================================


class TestWriteTemplateIfMissing:
    def test_creates_when_missing(self, tmp_path: Path):
        src = tmp_path / "template.md"
        src.write_text("# {{PRODUCT_NAME}} Review")
        dst = tmp_path / "output" / "review.md"

        result = write_template_if_missing(src, dst, {"{{PRODUCT_NAME}}": "MyApp"})

        assert result is True
        assert dst.read_text() == "# MyApp Review"

    def test_skips_existing(self, tmp_path: Path):
        src = tmp_path / "template.md"
        src.write_text("# New content")
        dst = tmp_path / "existing.md"
        dst.write_text("# User-edited content")

        result = write_template_if_missing(src, dst, {})

        assert result is False
        assert dst.read_text() == "# User-edited content"


# =============================================================================
# replace_settings
# =============================================================================


class TestReplaceSettings:
    def _template(self, tmp_path: Path) -> Path:
        """Write the standard v4 product-settings.json template."""
        tpl = tmp_path / "template.json"
        tpl.write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"matcher": "clear", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" clear"}
                ]}],
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" stop"}
                ]}],
            },
            "companyAnnouncements": "{{PRODUCT_NAME}} — Built with Prawduct",
        }, indent=2))
        return tpl

    def test_creates_new(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        tpl = self._template(tmp_path)

        result = replace_settings(dst, tpl, {"{{PRODUCT_NAME}}": "MyApp"})

        assert result is True
        data = json.loads(dst.read_text())
        assert "Stop" in data["hooks"]
        assert "MyApp" in data["companyAnnouncements"]

    def test_removes_v1_hooks(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        dst.parent.mkdir(parents=True)
        dst.write_text(json.dumps({
            "hooks": {
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "$(cat .prawduct/framework-path)/tools/governance-hook stop"}
                ]}],
                "SessionStart": [{"matcher": "clear", "hooks": [
                    {"type": "command", "command": "$(cat .prawduct/framework-path)/tools/governance-hook clear"}
                ]}],
            }
        }, indent=2))
        tpl = self._template(tmp_path)

        replace_settings(dst, tpl)

        data = json.loads(dst.read_text())
        for event in data["hooks"]:
            for entry in data["hooks"][event]:
                for hook in entry.get("hooks", []):
                    assert "governance-hook" not in hook.get("command", "")
                    assert "framework-path" not in hook.get("command", "")

    def test_removes_v3_bash_hooks(self, tmp_path: Path):
        """V3 bash hooks (without python3 prefix) should be replaced."""
        dst = tmp_path / ".claude" / "settings.json"
        dst.parent.mkdir(parents=True)
        dst.write_text(json.dumps({
            "hooks": {
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "\"$CLAUDE_PROJECT_DIR/tools/product-hook\" stop"}
                ]}],
            }
        }, indent=2))
        tpl = self._template(tmp_path)

        replace_settings(dst, tpl)

        data = json.loads(dst.read_text())
        for entry in data["hooks"]["Stop"]:
            for hook in entry.get("hooks", []):
                cmd = hook.get("command", "")
                if "product-hook" in cmd:
                    assert cmd.startswith("python3 ")

    def test_preserves_user_hooks(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        dst.parent.mkdir(parents=True)
        dst.write_text(json.dumps({
            "hooks": {
                "Stop": [
                    {"matcher": "", "hooks": [
                        {"type": "command", "command": "$(cat .prawduct/framework-path)/tools/governance-hook stop"}
                    ]},
                    {"matcher": "", "hooks": [
                        {"type": "command", "command": "my-custom-hook stop"}
                    ]},
                ]
            }
        }, indent=2))
        tpl = self._template(tmp_path)

        replace_settings(dst, tpl)

        data = json.loads(dst.read_text())
        commands = []
        for entry in data["hooks"]["Stop"]:
            for hook in entry.get("hooks", []):
                commands.append(hook.get("command", ""))
        assert any("product-hook" in c for c in commands)
        assert any("my-custom-hook" in c for c in commands)
        assert not any("governance-hook" in c for c in commands)

    def test_preserves_non_hook_settings(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        dst.parent.mkdir(parents=True)
        dst.write_text(json.dumps({
            "customSetting": True,
            "hooks": {}
        }, indent=2))
        tpl = self._template(tmp_path)

        replace_settings(dst, tpl)

        data = json.loads(dst.read_text())
        assert data["customSetting"] is True

    def test_removes_prawduct_statusline(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        dst.parent.mkdir(parents=True)
        dst.write_text(json.dumps({
            "hooks": {},
            "statusLine": {"command": "python3 prawduct-statusline.py"}
        }, indent=2))
        tpl = self._template(tmp_path)

        replace_settings(dst, tpl)

        data = json.loads(dst.read_text())
        assert "statusLine" not in data

    def test_preserves_non_prawduct_statusline(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        dst.parent.mkdir(parents=True)
        dst.write_text(json.dumps({
            "hooks": {},
            "statusLine": {"command": "my-custom-statusline"}
        }, indent=2))
        tpl = self._template(tmp_path)

        replace_settings(dst, tpl)

        data = json.loads(dst.read_text())
        assert "statusLine" in data
        assert data["statusLine"]["command"] == "my-custom-statusline"

    def test_adds_banner_with_subs(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        dst.parent.mkdir(parents=True)
        dst.write_text(json.dumps({"hooks": {}}, indent=2))
        tpl = self._template(tmp_path)

        replace_settings(dst, tpl, {"{{PRODUCT_NAME}}": "BannerApp"})

        data = json.loads(dst.read_text())
        assert "companyAnnouncements" in data
        assert "BannerApp" in data["companyAnnouncements"]

    def test_idempotent(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        tpl = self._template(tmp_path)

        replace_settings(dst, tpl)
        result = replace_settings(dst, tpl)

        assert result is False


# =============================================================================
# delete_v1_files
# =============================================================================


class TestDeleteV1Files:
    def test_deletes_existing(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / ".prawduct" / "framework-path").write_text("/some/path")
        (tmp_path / ".prawduct" / "framework-version").write_text("1.0")

        deleted = delete_v1_files(tmp_path)

        assert ".prawduct/framework-path" in deleted
        assert ".prawduct/framework-version" in deleted
        assert not (tmp_path / ".prawduct" / "framework-path").exists()
        assert not (tmp_path / ".prawduct" / "framework-version").exists()

    def test_skips_missing(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        deleted = delete_v1_files(tmp_path)
        assert deleted == []


# =============================================================================
# archive_v1_dirs
# =============================================================================


class TestArchiveV1Dirs:
    def test_archives_existing(self, tmp_path: Path):
        obs_dir = tmp_path / ".prawduct" / "framework-observations"
        obs_dir.mkdir(parents=True)
        (obs_dir / "note.md").write_text("observation")

        archived = archive_v1_dirs(tmp_path)

        assert ".prawduct/framework-observations" in archived
        assert not obs_dir.exists()
        assert (tmp_path / ".prawduct" / "archive" / "framework-observations" / "note.md").is_file()

    def test_skips_already_archived(self, tmp_path: Path):
        obs_dir = tmp_path / ".prawduct" / "framework-observations"
        obs_dir.mkdir(parents=True)
        (obs_dir / "note.md").write_text("observation")

        archive_dst = tmp_path / ".prawduct" / "archive" / "framework-observations"
        archive_dst.mkdir(parents=True)

        archived = archive_v1_dirs(tmp_path)
        assert archived == []

    def test_skips_missing(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        archived = archive_v1_dirs(tmp_path)
        assert archived == []


# =============================================================================
# clean_v1_session_files
# =============================================================================


class TestCleanV1SessionFiles:
    def test_deletes_existing(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        for rel in V1_SESSION_FILES:
            (tmp_path / rel).write_text("session data")

        deleted = clean_v1_session_files(tmp_path)

        assert len(deleted) == len(V1_SESSION_FILES)
        for rel in V1_SESSION_FILES:
            assert not (tmp_path / rel).exists()

    def test_skips_missing(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        deleted = clean_v1_session_files(tmp_path)
        assert deleted == []


# =============================================================================
# clean_gitignore
# =============================================================================


class TestCleanGitignore:
    def test_removes_v1_entries(self, tmp_path: Path):
        gitignore = tmp_path / ".gitignore"
        lines = V1_GITIGNORE_ENTRIES + ["node_modules/"]
        gitignore.write_text("\n".join(lines) + "\n")

        result = clean_gitignore(tmp_path)

        assert result is True
        content = gitignore.read_text()
        for entry in V1_GITIGNORE_ENTRIES:
            assert entry not in content
        assert "node_modules/" in content

    def test_adds_v4_entries(self, tmp_path: Path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\n")

        result = clean_gitignore(tmp_path)

        assert result is True
        content = gitignore.read_text()
        for entry in V4_GITIGNORE_ENTRIES:
            assert entry in content

    def test_adds_sync_manifest_to_existing_v3(self, tmp_path: Path):
        """V3 gitignore should get sync-manifest.json added."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("\n".join(V3_GITIGNORE_ENTRIES) + "\n")

        result = clean_gitignore(tmp_path)

        assert result is True
        content = gitignore.read_text()
        assert ".prawduct/sync-manifest.json" in content

    def test_idempotent(self, tmp_path: Path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\n")

        clean_gitignore(tmp_path)
        result = clean_gitignore(tmp_path)

        assert result is False

    def test_creates_new_gitignore(self, tmp_path: Path):
        result = clean_gitignore(tmp_path)

        assert result is True
        content = (tmp_path / ".gitignore").read_text()
        for entry in V4_GITIGNORE_ENTRIES:
            assert entry in content


# =============================================================================
# run_migrate (integration)
# =============================================================================


class TestRunMigrate:
    def _make_v1_repo(self, tmp_path: Path, name: str = "TestProduct") -> Path:
        """Create a minimal v1 repo structure."""
        repo = tmp_path / "myrepo"
        repo.mkdir()
        prawduct = repo / ".prawduct"
        prawduct.mkdir()
        (prawduct / "framework-path").write_text("/some/framework")
        (prawduct / "framework-version").write_text("1.0")
        (prawduct / "project-state.yaml").write_text(
            f'product_identity:\n    name: "{name}"\n'
        )
        (repo / "CLAUDE.md").write_text(
            "# Read framework CLAUDE.md\nSee framework-path for details.\n"
        )
        claude_dir = repo / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text(json.dumps({
            "hooks": {
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "$(cat .prawduct/framework-path)/tools/governance-hook stop"}
                ]}],
            }
        }, indent=2))
        return repo

    def _make_v3_repo(self, tmp_path: Path, name: str = "TestProduct") -> Path:
        """Create a minimal v3 repo structure (bash hook, no manifest)."""
        repo = tmp_path / "myrepo"
        repo.mkdir()
        prawduct = repo / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            f'product_identity:\n    name: "{name}"\n'
        )
        (repo / "CLAUDE.md").write_text("# V3 CLAUDE.md\nPrinciples here.\n")
        tools = repo / "tools"
        tools.mkdir()
        (tools / "product-hook").write_text("#!/usr/bin/env bash\n# v3 hook")
        claude_dir = repo / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"matcher": "clear", "hooks": [
                    {"type": "command", "command": "\"$CLAUDE_PROJECT_DIR/tools/product-hook\" clear"}
                ]}],
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "\"$CLAUDE_PROJECT_DIR/tools/product-hook\" stop"}
                ]}],
            }
        }, indent=2))
        return repo

    def test_full_v1_migration(self, tmp_path: Path):
        repo = self._make_v1_repo(tmp_path)

        result = run_migrate(str(repo))

        assert result["version_before"] == "v1"
        assert result["version_after"] == "v4"
        assert result["product_name"] == "TestProduct"
        assert len(result["actions"]) > 0

        # CLAUDE.md should be current template
        claude = (repo / "CLAUDE.md").read_text()
        assert "Principles" in claude
        assert "framework-path" not in claude

        # Product hook should exist and be Python
        hook = (repo / "tools" / "product-hook").read_text()
        assert "python3" in hook or "#!/usr/bin/env python3" in hook

        # v1 files should be gone
        assert not (repo / ".prawduct" / "framework-path").exists()

        # Settings should have v4 hooks with python3 prefix
        settings = json.loads((repo / ".claude" / "settings.json").read_text())
        for entry in settings["hooks"]["Stop"]:
            for hook in entry.get("hooks", []):
                assert "governance-hook" not in hook.get("command", "")

        # Sync manifest should exist
        assert (repo / ".prawduct" / "sync-manifest.json").is_file()

        # Banner should be set
        assert "companyAnnouncements" in settings

    def test_v3_to_v4_migration(self, tmp_path: Path):
        """V3 repos get Python hook, manifest, and banner."""
        repo = self._make_v3_repo(tmp_path)

        result = run_migrate(str(repo))

        assert result["version_before"] == "v3"
        assert result["version_after"] == "v4"
        assert len(result["actions"]) > 0

        # Hook should be updated (Python version)
        hook_content = (repo / "tools" / "product-hook").read_text()
        assert "python3" in hook_content or "#!/usr/bin/env python3" in hook_content

        # Manifest should exist
        assert (repo / ".prawduct" / "sync-manifest.json").is_file()
        manifest = json.loads((repo / ".prawduct" / "sync-manifest.json").read_text())
        assert manifest["format_version"] == 1
        assert manifest["product_name"] == "TestProduct"

        # Settings should have python3 hooks and banner
        settings = json.loads((repo / ".claude" / "settings.json").read_text())
        assert "companyAnnouncements" in settings
        for event_entries in settings["hooks"].values():
            for entry in event_entries:
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "")
                    if "product-hook" in cmd:
                        assert cmd.startswith("python3 ")

    def test_idempotent_on_v4(self, tmp_path: Path):
        repo = self._make_v1_repo(tmp_path)

        run_migrate(str(repo))
        result = run_migrate(str(repo))

        assert result["actions"] == []
        assert result["version_before"] == "v4"
        assert result["version_after"] == "v4"

    def test_name_override(self, tmp_path: Path):
        repo = self._make_v1_repo(tmp_path, name="OldName")

        result = run_migrate(str(repo), product_name="NewName")

        assert result["product_name"] == "NewName"
        claude = (repo / "CLAUDE.md").read_text()
        assert "NewName" in claude

    def test_name_fallback_to_dirname(self, tmp_path: Path):
        repo = tmp_path / "cool-project"
        repo.mkdir()
        (repo / ".prawduct").mkdir()
        (repo / ".prawduct" / "framework-path").write_text("/some/framework")
        (repo / "CLAUDE.md").write_text("# old")

        result = run_migrate(str(repo))

        assert result["product_name"] == "cool-project"

    def test_partial_repo_handling(self, tmp_path: Path):
        """A repo with both framework-path and product-hook is 'partial'."""
        repo = self._make_v1_repo(tmp_path)
        (repo / "tools").mkdir()
        (repo / "tools" / "product-hook").write_text("#!/bin/bash\nold hook")

        result = run_migrate(str(repo))

        assert result["version_before"] == "partial"
        assert result["version_after"] == "v4"
        assert not (repo / ".prawduct" / "framework-path").exists()

    def test_refuses_unknown_directory(self, tmp_path: Path):
        """Running on a non-Prawduct directory returns error, no changes."""
        repo = tmp_path / "not-a-repo"
        repo.mkdir()

        result = run_migrate(str(repo))

        assert result["version_before"] == "unknown"
        assert "error" in result
        assert result["actions"] == []
        assert not (repo / "CLAUDE.md").exists()
        assert not (repo / "tools" / "product-hook").exists()

    def test_v3_preserves_user_hooks(self, tmp_path: Path):
        """V3→V4 migration preserves user hooks."""
        repo = self._make_v3_repo(tmp_path)
        settings_path = repo / ".claude" / "settings.json"
        settings = json.loads(settings_path.read_text())
        settings["hooks"]["Stop"].append(
            {"matcher": "", "hooks": [
                {"type": "command", "command": "my-custom-hook stop"}
            ]}
        )
        settings_path.write_text(json.dumps(settings, indent=2))

        run_migrate(str(repo))

        data = json.loads(settings_path.read_text())
        commands = []
        for entry in data["hooks"]["Stop"]:
            for hook in entry.get("hooks", []):
                commands.append(hook.get("command", ""))
        assert any("product-hook" in c for c in commands)
        assert any("my-custom-hook" in c for c in commands)


# =============================================================================
# add_block_markers
# =============================================================================


class TestAddBlockMarkers:
    def test_wraps_user_edited_content(self, tmp_path: Path):
        """User-edited CLAUDE.md without markers gets wrapped."""
        (tmp_path / "CLAUDE.md").write_text(
            "# CLAUDE.md — MyApp\n\n## What This Is\n\nUser content.\n"
        )
        result = add_block_markers(tmp_path, {"{{PRODUCT_NAME}}": "MyApp"})
        assert result is True
        content = (tmp_path / "CLAUDE.md").read_text()
        assert BLOCK_BEGIN in content
        assert BLOCK_END in content
        assert "User content." in content

    def test_already_marked_noop(self, tmp_path: Path):
        """File with markers is not modified."""
        original = (
            f"# CLAUDE.md — MyApp\n\n"
            f"{BLOCK_BEGIN}\n\n## What This Is\n\n{BLOCK_END}\n"
        )
        (tmp_path / "CLAUDE.md").write_text(original)
        result = add_block_markers(tmp_path, {"{{PRODUCT_NAME}}": "MyApp"})
        assert result is False
        assert (tmp_path / "CLAUDE.md").read_text() == original

    def test_missing_file(self, tmp_path: Path):
        """Missing CLAUDE.md returns False."""
        result = add_block_markers(tmp_path, {"{{PRODUCT_NAME}}": "MyApp"})
        assert result is False

    def test_wraps_content_without_headings(self, tmp_path: Path):
        """Content without ## headings still gets wrapped."""
        (tmp_path / "CLAUDE.md").write_text(
            "# CLAUDE.md — MyApp\n\nOld content without markers or headings\n"
        )
        result = add_block_markers(tmp_path, {"{{PRODUCT_NAME}}": "MyApp"})
        assert result is True
        content = (tmp_path / "CLAUDE.md").read_text()
        assert BLOCK_BEGIN in content
        assert BLOCK_END in content
        assert "Old content" in content


# =============================================================================
# upgrade_manifest_strategy
# =============================================================================


class TestUpgradeManifestStrategy:
    def test_template_to_block_template(self, tmp_path: Path):
        """Strategy changes from template to block_template."""
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / "CLAUDE.md").write_text(
            f"# Title\n\n{BLOCK_BEGIN}\nbody\n{BLOCK_END}\n"
        )
        manifest = {
            "format_version": 1,
            "files": {
                "CLAUDE.md": {
                    "template": "templates/product-claude.md",
                    "strategy": "template",
                    "generated_hash": "old_hash",
                },
            },
        }
        (tmp_path / ".prawduct" / "sync-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )

        result = upgrade_manifest_strategy(tmp_path)

        assert result is True
        updated = json.loads(
            (tmp_path / ".prawduct" / "sync-manifest.json").read_text()
        )
        assert updated["files"]["CLAUDE.md"]["strategy"] == "block_template"

    def test_already_block_template_noop(self, tmp_path: Path):
        """Already block_template returns False."""
        (tmp_path / ".prawduct").mkdir()
        manifest = {
            "format_version": 1,
            "files": {
                "CLAUDE.md": {
                    "strategy": "block_template",
                    "generated_hash": "abc",
                },
            },
        }
        (tmp_path / ".prawduct" / "sync-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )

        result = upgrade_manifest_strategy(tmp_path)
        assert result is False

    def test_hash_recomputed_as_block_hash(self, tmp_path: Path):
        """Hash is recomputed using block hash after upgrade."""
        (tmp_path / ".prawduct").mkdir()
        content = f"# Title\n\n{BLOCK_BEGIN}\nbody\n{BLOCK_END}\nfooter\n"
        (tmp_path / "CLAUDE.md").write_text(content)
        manifest = {
            "format_version": 1,
            "files": {
                "CLAUDE.md": {
                    "strategy": "template",
                    "generated_hash": "old_hash",
                },
            },
        }
        (tmp_path / ".prawduct" / "sync-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )

        upgrade_manifest_strategy(tmp_path)

        updated = json.loads(
            (tmp_path / ".prawduct" / "sync-manifest.json").read_text()
        )
        expected_hash = compute_block_hash(content)
        assert updated["files"]["CLAUDE.md"]["generated_hash"] == expected_hash


# =============================================================================
# Integration: migration + block markers
# =============================================================================


class TestMigrateBlockMarkers:
    def _make_v1_repo(self, tmp_path: Path, name: str = "TestProduct") -> Path:
        """Create a minimal v1 repo structure."""
        repo = tmp_path / "myrepo"
        repo.mkdir()
        prawduct = repo / ".prawduct"
        prawduct.mkdir()
        (prawduct / "framework-path").write_text("/some/framework")
        (prawduct / "framework-version").write_text("1.0")
        (prawduct / "project-state.yaml").write_text(
            f'product_identity:\n    name: "{name}"\n'
        )
        (repo / "CLAUDE.md").write_text(
            "# Read framework CLAUDE.md\nSee framework-path for details.\n"
        )
        claude_dir = repo / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text(json.dumps({
            "hooks": {
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "$(cat .prawduct/framework-path)/tools/governance-hook stop"}
                ]}],
            }
        }, indent=2))
        return repo

    def _make_v3_repo(self, tmp_path: Path, name: str = "TestProduct") -> Path:
        """Create a minimal v3 repo."""
        repo = tmp_path / "myrepo"
        repo.mkdir()
        prawduct = repo / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            f'product_identity:\n    name: "{name}"\n'
        )
        (repo / "CLAUDE.md").write_text("# V3 CLAUDE.md\n\n## What This Is\n\nV3 content.\n")
        tools = repo / "tools"
        tools.mkdir()
        (tools / "product-hook").write_text("#!/usr/bin/env bash\n# v3 hook")
        claude_dir = repo / ".claude"
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text(json.dumps({
            "hooks": {
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "\"$CLAUDE_PROJECT_DIR/tools/product-hook\" stop"}
                ]}],
            }
        }, indent=2))
        return repo

    def _make_v4_no_markers_repo(self, tmp_path: Path, name: str = "TestProduct") -> Path:
        """Create a v4 repo without block markers (pre-marker v4)."""
        repo = tmp_path / "myrepo"
        repo.mkdir()
        prawduct = repo / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            f'product_identity:\n    name: "{name}"\n'
        )
        (repo / "CLAUDE.md").write_text("# CLAUDE.md — TestProduct\n\n## What This Is\n\nV4 content.\n")
        tools = repo / "tools"
        tools.mkdir()
        hook_src = Path(__file__).resolve().parent.parent / "tools" / "product-hook"
        if hook_src.is_file():
            (tools / "product-hook").write_bytes(hook_src.read_bytes())
        else:
            (tools / "product-hook").write_text("#!/usr/bin/env python3\n# v4 hook")
        import stat as stat_mod
        (tools / "product-hook").chmod(
            (tools / "product-hook").stat().st_mode | stat_mod.S_IXUSR
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
        # Old-style manifest with "template" strategy
        manifest = {
            "format_version": 1,
            "framework_source": str(Path(__file__).resolve().parent.parent),
            "product_name": name,
            "files": {
                "CLAUDE.md": {
                    "template": "templates/product-claude.md",
                    "strategy": "template",
                    "generated_hash": "old_hash",
                },
            },
        }
        (prawduct / "sync-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        return repo

    def test_v1_gets_markers(self, tmp_path: Path):
        """V1→V4 migration produces CLAUDE.md with markers."""
        repo = self._make_v1_repo(tmp_path)
        result = run_migrate(str(repo))

        assert result["version_after"] == "v4"
        content = (repo / "CLAUDE.md").read_text()
        assert BLOCK_BEGIN in content
        assert BLOCK_END in content

    def test_v3_gets_markers(self, tmp_path: Path):
        """V3→V4 migration includes block markers."""
        repo = self._make_v3_repo(tmp_path)
        result = run_migrate(str(repo))

        assert result["version_after"] == "v4"
        content = (repo / "CLAUDE.md").read_text()
        assert BLOCK_BEGIN in content
        assert BLOCK_END in content

    def test_v4_gets_markers_and_strategy_upgrade(self, tmp_path: Path):
        """V4 repo without markers gets markers + strategy upgrade."""
        repo = self._make_v4_no_markers_repo(tmp_path)
        result = run_migrate(str(repo))

        content = (repo / "CLAUDE.md").read_text()
        assert BLOCK_BEGIN in content
        assert BLOCK_END in content

        manifest = json.loads(
            (repo / ".prawduct" / "sync-manifest.json").read_text()
        )
        assert manifest["files"]["CLAUDE.md"]["strategy"] == "block_template"

    def test_v1_manifest_has_block_template(self, tmp_path: Path):
        """V1→V4 manifest uses block_template strategy."""
        repo = self._make_v1_repo(tmp_path)
        run_migrate(str(repo))

        manifest = json.loads(
            (repo / ".prawduct" / "sync-manifest.json").read_text()
        )
        assert manifest["files"]["CLAUDE.md"]["strategy"] == "block_template"
