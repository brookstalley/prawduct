"""Tests for prawduct-init.py — the product repo generator.

Uses importlib to handle the hyphenated filename.
"""

from __future__ import annotations

import importlib.util
import json
import stat
from pathlib import Path

import pytest

# Load prawduct-init.py despite the hyphen in its name
_TOOL_PATH = Path(__file__).resolve().parent.parent / "tools" / "prawduct-init.py"
_spec = importlib.util.spec_from_file_location("prawduct_init", _TOOL_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

ensure_dir = _mod.ensure_dir
write_template = _mod.write_template
copy_hook = _mod.copy_hook
merge_settings = _mod.merge_settings
update_gitignore = _mod.update_gitignore
run_init = _mod.run_init
is_v1_repo = _mod.is_v1_repo
main = _mod.main
compute_block_hash = _mod.compute_block_hash
GITIGNORE_ENTRIES = _mod.GITIGNORE_ENTRIES

# Import sync module for block constants
_SYNC_PATH = Path(__file__).resolve().parent.parent / "tools" / "prawduct-sync.py"
_sync_spec = importlib.util.spec_from_file_location("prawduct_sync", _SYNC_PATH)
_sync_mod = importlib.util.module_from_spec(_sync_spec)
_sync_spec.loader.exec_module(_sync_mod)
BLOCK_BEGIN = _sync_mod.BLOCK_BEGIN
BLOCK_END = _sync_mod.BLOCK_END


# =============================================================================
# ensure_dir
# =============================================================================


class TestEnsureDir:
    def test_creates_missing_dir(self, tmp_path: Path):
        target = tmp_path / "new" / "nested"
        assert ensure_dir(target) is True
        assert target.is_dir()

    def test_idempotent_returns_false(self, tmp_path: Path):
        target = tmp_path / "existing"
        target.mkdir()
        assert ensure_dir(target) is False


# =============================================================================
# write_template
# =============================================================================


class TestWriteTemplate:
    def test_creates_file_with_substitution(self, tmp_path: Path):
        src = tmp_path / "template.md"
        src.write_text("# {{PRODUCT_NAME}} Guide\nWelcome to {{PRODUCT_NAME}}.")
        dst = tmp_path / "output" / "result.md"

        result = write_template(src, dst, {"{{PRODUCT_NAME}}": "MyApp"})

        assert result is True
        assert dst.read_text() == "# MyApp Guide\nWelcome to MyApp."

    def test_product_name_replaced(self, tmp_path: Path):
        src = tmp_path / "tpl.md"
        src.write_text("Name: {{PRODUCT_NAME}}")
        dst = tmp_path / "out.md"

        write_template(src, dst, {"{{PRODUCT_NAME}}": "TestProduct"})
        assert "{{PRODUCT_NAME}}" not in dst.read_text()
        assert "TestProduct" in dst.read_text()

    def test_skips_existing_different_content(self, tmp_path: Path):
        src = tmp_path / "tpl.md"
        src.write_text("New content")
        dst = tmp_path / "out.md"
        dst.write_text("User-edited content")

        result = write_template(src, dst, {})

        assert result is False
        assert dst.read_text() == "User-edited content"

    def test_skips_identical_content(self, tmp_path: Path):
        src = tmp_path / "tpl.md"
        src.write_text("Same content")
        dst = tmp_path / "out.md"
        dst.write_text("Same content")

        result = write_template(src, dst, {})
        assert result is False


# =============================================================================
# copy_hook
# =============================================================================


class TestCopyHook:
    def test_creates_with_executable_bit(self, tmp_path: Path):
        src = tmp_path / "hook.sh"
        src.write_text("#!/bin/bash\necho hello")
        dst = tmp_path / "target" / "hook.sh"

        result = copy_hook(src, dst)

        assert result is True
        assert dst.is_file()
        mode = dst.stat().st_mode
        assert mode & stat.S_IXUSR

    def test_updates_when_content_changed(self, tmp_path: Path):
        src = tmp_path / "hook.sh"
        dst = tmp_path / "hook_dst.sh"

        src.write_text("#!/bin/bash\nversion 1")
        dst.write_text("#!/bin/bash\nversion 0")
        dst.chmod(dst.stat().st_mode | stat.S_IXUSR)

        src.write_text("#!/bin/bash\nversion 2")
        result = copy_hook(src, dst)

        assert result is True
        assert dst.read_text() == "#!/bin/bash\nversion 2"
        assert dst.stat().st_mode & stat.S_IXUSR

    def test_idempotent(self, tmp_path: Path):
        src = tmp_path / "hook.sh"
        src.write_text("#!/bin/bash\necho hello")
        dst = tmp_path / "hook_dst.sh"

        copy_hook(src, dst)
        result = copy_hook(src, dst)

        assert result is False


# =============================================================================
# merge_settings
# =============================================================================


class TestMergeSettings:
    def _template(self, tmp_path: Path) -> Path:
        """Write the standard product-settings.json template and return its path."""
        tpl = tmp_path / "template.json"
        tpl.write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"matcher": "clear", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" clear"}
                ]}],
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" stop"}
                ]}],
            }
        }, indent=2))
        return tpl

    def test_creates_new(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        tpl = self._template(tmp_path)

        result = merge_settings(dst, tpl)

        assert result is True
        data = json.loads(dst.read_text())
        assert "hooks" in data
        assert "Stop" in data["hooks"]

    def test_preserves_user_hooks(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        dst.parent.mkdir(parents=True)
        dst.write_text(json.dumps({
            "hooks": {
                "Stop": [
                    {"matcher": "", "hooks": [{"type": "command", "command": "my-custom-hook stop"}]}
                ]
            }
        }, indent=2))
        tpl = self._template(tmp_path)

        merge_settings(dst, tpl)

        data = json.loads(dst.read_text())
        stop_hooks = data["hooks"]["Stop"]
        # Should have both: framework hook + user hook
        commands = []
        for entry in stop_hooks:
            for hook in entry.get("hooks", []):
                commands.append(hook.get("command", ""))
        assert any("product-hook" in c for c in commands)
        assert any("my-custom-hook" in c for c in commands)

    def test_adds_framework_hooks(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        dst.parent.mkdir(parents=True)
        dst.write_text(json.dumps({"hooks": {}}, indent=2))
        tpl = self._template(tmp_path)

        merge_settings(dst, tpl)

        data = json.loads(dst.read_text())
        assert "SessionStart" in data["hooks"]
        assert "Stop" in data["hooks"]

    def test_preserves_other_keys(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        dst.parent.mkdir(parents=True)
        dst.write_text(json.dumps({
            "companyAnnouncements": True,
            "hooks": {}
        }, indent=2))
        tpl = self._template(tmp_path)

        merge_settings(dst, tpl)

        data = json.loads(dst.read_text())
        assert data["companyAnnouncements"] is True

    def test_handles_bad_json(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        dst.parent.mkdir(parents=True)
        dst.write_text("not valid json {{{")
        tpl = self._template(tmp_path)

        result = merge_settings(dst, tpl)
        assert result is False

    def test_idempotent(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        tpl = self._template(tmp_path)

        merge_settings(dst, tpl)
        result = merge_settings(dst, tpl)

        assert result is False


# =============================================================================
# update_gitignore
# =============================================================================


class TestUpdateGitignore:
    def test_creates_new(self, tmp_path: Path):
        result = update_gitignore(tmp_path)

        assert result is True
        content = (tmp_path / ".gitignore").read_text()
        for entry in GITIGNORE_ENTRIES:
            assert entry in content

    def test_appends_missing_entries(self, tmp_path: Path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text("node_modules/\n")

        result = update_gitignore(tmp_path)

        assert result is True
        content = gitignore.read_text()
        assert "node_modules/" in content
        for entry in GITIGNORE_ENTRIES:
            assert entry in content

    def test_idempotent(self, tmp_path: Path):
        update_gitignore(tmp_path)
        result = update_gitignore(tmp_path)
        assert result is False


# =============================================================================
# run_init
# =============================================================================


class TestRunInit:
    def test_creates_all_expected_files(self, tmp_path: Path):
        result = run_init(str(tmp_path), "TestProduct")

        assert (tmp_path / ".prawduct").is_dir()
        assert (tmp_path / ".prawduct" / "artifacts").is_dir()
        assert (tmp_path / "CLAUDE.md").is_file()
        assert (tmp_path / ".prawduct" / "critic-review.md").is_file()
        assert (tmp_path / ".prawduct" / "project-state.yaml").is_file()
        assert (tmp_path / ".prawduct" / "learnings.md").is_file()
        assert (tmp_path / "tools" / "product-hook").is_file()
        assert (tmp_path / ".claude" / "settings.json").is_file()
        assert (tmp_path / ".gitignore").is_file()
        assert len(result["actions"]) > 0

    def test_idempotent_second_run(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")
        result = run_init(str(tmp_path), "TestProduct")

        assert result["actions"] == []

    def test_template_substitution_in_all_files(self, tmp_path: Path):
        run_init(str(tmp_path), "MyApp")

        claude_md = (tmp_path / "CLAUDE.md").read_text()
        assert "MyApp" in claude_md
        assert "{{PRODUCT_NAME}}" not in claude_md

        project_state = (tmp_path / ".prawduct" / "project-state.yaml").read_text()
        assert "MyApp" in project_state
        assert "{{PRODUCT_NAME}}" not in project_state


# =============================================================================
# Template propagation
# =============================================================================


class TestTemplatePropagation:
    @pytest.fixture(autouse=True)
    def init_product(self, tmp_path: Path):
        run_init(str(tmp_path), "PropTest")
        self.target = tmp_path

    def test_claude_md_contains_product_verification(self):
        content = (self.target / "CLAUDE.md").read_text()
        # Product CLAUDE.md should reference product verification
        assert "verif" in content.lower()

    def test_critic_review_has_all_checks(self):
        content = (self.target / ".prawduct" / "critic-review.md").read_text()
        # Should have the 6 standard checks
        assert "Spec Compliance" in content
        assert "Test Integrity" in content
        assert "Scope Discipline" in content
        assert "Proportionality" in content
        assert "Coherence" in content
        assert "Learning" in content or "Observability" in content

    def test_project_state_has_expected_structure(self):
        content = (self.target / ".prawduct" / "project-state.yaml").read_text()
        assert "classification:" in content
        assert "product_definition:" in content
        assert "build_plan:" in content
        assert "build_state:" in content
        assert "current_phase:" in content


# =============================================================================
# V1 detection
# =============================================================================


class TestV1Detection:
    def test_detects_v1_repo(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / ".prawduct" / "framework-path").write_text("/some/path")
        assert is_v1_repo(str(tmp_path)) is True

    def test_not_v1_without_framework_path(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        assert is_v1_repo(str(tmp_path)) is False

    def test_init_exits_1_on_v1_repo(self, tmp_path: Path, monkeypatch):
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / ".prawduct" / "framework-path").write_text("/some/path")

        monkeypatch.setattr(
            "sys.argv",
            ["prawduct-init.py", str(tmp_path), "--name", "Test"],
        )
        result = main()
        assert result == 1


# =============================================================================
# Sync manifest
# =============================================================================


class TestSyncManifest:
    def test_manifest_created(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")
        manifest_path = tmp_path / ".prawduct" / "sync-manifest.json"
        assert manifest_path.is_file()

    def test_manifest_structure(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")
        manifest = json.loads(
            (tmp_path / ".prawduct" / "sync-manifest.json").read_text()
        )
        assert manifest["format_version"] == 1
        assert manifest["product_name"] == "TestProduct"
        assert "framework_source" in manifest
        assert "last_sync" in manifest
        assert "CLAUDE.md" in manifest["files"]
        assert ".prawduct/critic-review.md" in manifest["files"]
        assert "tools/product-hook" in manifest["files"]
        assert ".claude/settings.json" in manifest["files"]

    def test_manifest_has_hashes(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")
        manifest = json.loads(
            (tmp_path / ".prawduct" / "sync-manifest.json").read_text()
        )
        # Template files should have hashes
        assert manifest["files"]["CLAUDE.md"]["generated_hash"] is not None
        assert manifest["files"][".prawduct/critic-review.md"]["generated_hash"] is not None
        assert manifest["files"]["tools/product-hook"]["generated_hash"] is not None
        # merge_settings doesn't use hash
        assert manifest["files"][".claude/settings.json"]["generated_hash"] is None

    def test_manifest_idempotent(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")
        result = run_init(str(tmp_path), "TestProduct")
        # Manifest already exists — should not be recreated
        assert not any("sync-manifest" in a for a in result["actions"])


# =============================================================================
# Banner
# =============================================================================


class TestBanner:
    def test_settings_has_banner(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")
        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        assert "companyAnnouncements" in settings
        banner = settings["companyAnnouncements"]
        assert isinstance(banner, list)
        banner_text = banner[0]
        assert "TestProduct" in banner_text
        assert "Prawduct" in banner_text
        assert "{{PRODUCT_NAME}}" not in banner_text

    def test_settings_has_python_hook_commands(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")
        settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
        for event_entries in settings["hooks"].values():
            for entry in event_entries:
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "")
                    if "product-hook" in cmd:
                        assert cmd.startswith("python3 ")


# =============================================================================
# Block markers in CLAUDE.md
# =============================================================================


class TestBlockMarkers:
    def test_claude_md_has_markers(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")
        content = (tmp_path / "CLAUDE.md").read_text()
        assert BLOCK_BEGIN in content
        assert BLOCK_END in content

    def test_title_is_before_markers(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")
        content = (tmp_path / "CLAUDE.md").read_text()
        title_pos = content.find("# CLAUDE.md")
        begin_pos = content.find(BLOCK_BEGIN)
        assert title_pos < begin_pos

    def test_manifest_uses_block_template_strategy(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")
        manifest = json.loads(
            (tmp_path / ".prawduct" / "sync-manifest.json").read_text()
        )
        assert manifest["files"]["CLAUDE.md"]["strategy"] == "block_template"

    def test_manifest_hash_equals_block_hash(self, tmp_path: Path):
        run_init(str(tmp_path), "TestProduct")
        manifest = json.loads(
            (tmp_path / ".prawduct" / "sync-manifest.json").read_text()
        )
        content = (tmp_path / "CLAUDE.md").read_text()
        expected_hash = compute_block_hash(content)
        assert manifest["files"]["CLAUDE.md"]["generated_hash"] == expected_hash


# =============================================================================
# Existing CLAUDE.md merge behavior
# =============================================================================


class TestExistingClaudeMd:
    """Init on a repo that already has a CLAUDE.md without Prawduct markers."""

    def test_existing_claude_md_gets_markers(self, tmp_path: Path):
        """An existing CLAUDE.md without markers gets framework content merged in."""
        (tmp_path / "CLAUDE.md").write_text("# My Project\n\nExisting instructions.\n")

        run_init(str(tmp_path), "TestProduct")

        content = (tmp_path / "CLAUDE.md").read_text()
        assert BLOCK_BEGIN in content
        assert BLOCK_END in content

    def test_existing_content_preserved_below_markers(self, tmp_path: Path):
        """User's original content appears after PRAWDUCT:END marker."""
        user_content = "# My Project\n\nExisting instructions.\n"
        (tmp_path / "CLAUDE.md").write_text(user_content)

        run_init(str(tmp_path), "TestProduct")

        content = (tmp_path / "CLAUDE.md").read_text()
        end_pos = content.find(BLOCK_END)
        after_markers = content[end_pos + len(BLOCK_END):]
        assert "# My Project" in after_markers
        assert "Existing instructions." in after_markers

    def test_existing_claude_md_with_markers_not_modified(self, tmp_path: Path):
        """If CLAUDE.md already has markers, init leaves it alone."""
        marked_content = (
            "# CLAUDE.md — TestProduct\n\n"
            f"{BLOCK_BEGIN}\nFramework content\n{BLOCK_END}\n\n"
            "User notes here.\n"
        )
        (tmp_path / "CLAUDE.md").write_text(marked_content)

        result = run_init(str(tmp_path), "TestProduct")

        assert (tmp_path / "CLAUDE.md").read_text() == marked_content
        assert not any("CLAUDE.md" in a for a in result["actions"])

    def test_manifest_hash_correct_after_merge(self, tmp_path: Path):
        """Manifest block hash is non-null after merging into existing CLAUDE.md."""
        (tmp_path / "CLAUDE.md").write_text("# Existing\n\nStuff here.\n")

        run_init(str(tmp_path), "TestProduct")

        manifest = json.loads(
            (tmp_path / ".prawduct" / "sync-manifest.json").read_text()
        )
        content = (tmp_path / "CLAUDE.md").read_text()
        expected_hash = compute_block_hash(content)
        assert expected_hash is not None
        assert manifest["files"]["CLAUDE.md"]["generated_hash"] == expected_hash

    def test_merge_action_reported(self, tmp_path: Path):
        """The merge action appears in the result."""
        (tmp_path / "CLAUDE.md").write_text("# Existing\n")

        result = run_init(str(tmp_path), "TestProduct")

        assert any("Merged" in a and "CLAUDE.md" in a for a in result["actions"])
