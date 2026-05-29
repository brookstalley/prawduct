"""Tests for prawduct-setup.py — sync functionality.

Uses importlib to handle the hyphenated filename.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Load prawduct-setup.py via importlib
_TOOL_PATH = Path(__file__).resolve().parent.parent / "tools" / "prawduct-setup.py"
_spec = importlib.util.spec_from_file_location("prawduct_setup", _TOOL_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

compute_hash = _mod.compute_hash
compute_block_hash = _mod.compute_block_hash
extract_block = _mod.extract_block
render_template = _mod.render_template
merge_settings = _mod.merge_settings
create_manifest = _mod.create_manifest
apply_renames = _mod.apply_renames
_bootstrap_manifest = _mod._bootstrap_manifest
FILE_RENAMES = _mod.FILE_RENAMES
MANAGED_FILES = _mod.MANAGED_FILES
run_sync = _mod.run_sync
_try_pull_framework = _mod._try_pull_framework
_try_auto_commit = _mod._lib_sync_cmd._try_auto_commit
_read_sync_config = _mod._lib_sync_cmd._read_sync_config
_branch_is_protected = _mod._lib_sync_cmd._branch_is_protected
_DEFAULT_PROTECTED_BRANCHES = _mod._lib_sync_cmd._DEFAULT_PROTECTED_BRANCHES
PRAWDUCT_VERSION = _mod.PRAWDUCT_VERSION
_match_historical_render = _mod._match_historical_render
_HISTORICAL_RENDER_DEPTH_CAP = _mod._HISTORICAL_RENDER_DEPTH_CAP
BLOCK_BEGIN = _mod.BLOCK_BEGIN
BLOCK_END = _mod.BLOCK_END
GITIGNORE_ENTRIES = _mod.GITIGNORE_ENTRIES
migrate_backlog = _mod.migrate_backlog
enable_v1_4_views = _mod.enable_v1_4_views
enable_v1_4_coverage = _mod.enable_v1_4_coverage
run_migrate_coverage = _mod.run_migrate_coverage
enable_v1_4_settings_layout = _mod.enable_v1_4_settings_layout
run_migrate_settings_layout = _mod.run_migrate_settings_layout
untrack_gitignored_files = _mod.untrack_gitignored_files


# =============================================================================
# compute_hash
# =============================================================================


class TestComputeHash:
    def test_returns_sha256(self, tmp_path: Path):
        f = tmp_path / "hello.txt"
        f.write_text("hello world")
        expected = hashlib.sha256(b"hello world").hexdigest()
        assert compute_hash(f) == expected

    def test_returns_none_for_missing(self, tmp_path: Path):
        assert compute_hash(tmp_path / "nope.txt") is None

    def test_empty_file(self, tmp_path: Path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        expected = hashlib.sha256(b"").hexdigest()
        assert compute_hash(f) == expected


# =============================================================================
# render_template
# =============================================================================


class TestRenderTemplate:
    def test_substitution(self, tmp_path: Path):
        tpl = tmp_path / "tpl.md"
        tpl.write_text("# {{PRODUCT_NAME}} Guide\nWelcome to {{PRODUCT_NAME}}.")
        result = render_template(tpl, {"{{PRODUCT_NAME}}": "MyApp"})
        assert result == "# MyApp Guide\nWelcome to MyApp."

    def test_no_subs(self, tmp_path: Path):
        tpl = tmp_path / "tpl.md"
        tpl.write_text("Hello world")
        assert render_template(tpl, {}) == "Hello world"


# =============================================================================
# merge_settings
# =============================================================================


class TestMergeSettings:
    def _template(self, tmp_path: Path, with_banner: bool = False) -> Path:
        tpl = tmp_path / "template.json"
        data: dict = {
            "hooks": {
                "SessionStart": [{"matcher": "clear", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" clear"}
                ]}],
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" stop"}
                ]}],
            }
        }
        if with_banner:
            data["companyAnnouncements"] = "{{PRODUCT_NAME}} — Built with Prawduct"
        tpl.write_text(json.dumps(data, indent=2))
        return tpl

    def test_creates_new(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        tpl = self._template(tmp_path)
        assert merge_settings(dst, tpl) is True
        data = json.loads(dst.read_text())
        assert "Stop" in data["hooks"]

    def test_preserves_user_hooks(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        dst.parent.mkdir(parents=True)
        dst.write_text(json.dumps({
            "hooks": {
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "my-custom-hook stop"}
                ]}]
            }
        }, indent=2))
        tpl = self._template(tmp_path)
        merge_settings(dst, tpl)
        data = json.loads(dst.read_text())
        commands = []
        for entry in data["hooks"]["Stop"]:
            for hook in entry.get("hooks", []):
                commands.append(hook.get("command", ""))
        assert any("product-hook" in c for c in commands)
        assert any("my-custom-hook" in c for c in commands)

    def test_subs_applied_to_banner(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        tpl = self._template(tmp_path, with_banner=True)
        merge_settings(dst, tpl, subs={"{{PRODUCT_NAME}}": "TestApp"})
        data = json.loads(dst.read_text())
        assert "TestApp" in data["companyAnnouncements"]
        assert "{{PRODUCT_NAME}}" not in data["companyAnnouncements"]

    def test_banner_always_updated(self, tmp_path: Path):
        """Banner is framework-managed, always updated from template."""
        dst = tmp_path / ".claude" / "settings.json"
        dst.parent.mkdir(parents=True)
        dst.write_text(json.dumps({
            "companyAnnouncements": "Old banner",
            "hooks": {}
        }, indent=2))
        tpl = self._template(tmp_path, with_banner=True)
        result = merge_settings(dst, tpl, subs={"{{PRODUCT_NAME}}": "NewApp"})
        assert result is True
        data = json.loads(dst.read_text())
        assert "NewApp" in data["companyAnnouncements"]

    def test_preserves_other_keys(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        dst.parent.mkdir(parents=True)
        dst.write_text(json.dumps({
            "customSetting": True,
            "hooks": {}
        }, indent=2))
        tpl = self._template(tmp_path)
        merge_settings(dst, tpl)
        data = json.loads(dst.read_text())
        assert data["customSetting"] is True

    def test_handles_bad_json(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        dst.parent.mkdir(parents=True)
        dst.write_text("not valid json {{{")
        tpl = self._template(tmp_path)
        assert merge_settings(dst, tpl) is False

    def test_idempotent(self, tmp_path: Path):
        dst = tmp_path / ".claude" / "settings.json"
        tpl = self._template(tmp_path)
        merge_settings(dst, tpl)
        assert merge_settings(dst, tpl) is False

    def test_removes_stale_prawduct_hook_events(self, tmp_path: Path):
        """When template drops an event (e.g. SessionEnd), merge removes our hook but keeps user hooks."""
        dst = tmp_path / ".claude" / "settings.json"
        dst.parent.mkdir(parents=True)
        # Product has a stale SessionEnd with our hook + a user hook
        dst.write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"matcher": "clear", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" clear"}
                ]}],
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" stop"}
                ]}],
                "SessionEnd": [
                    {"matcher": "", "hooks": [
                        {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" session-end"}
                    ]},
                    {"matcher": "", "hooks": [
                        {"type": "command", "command": "my-custom-cleanup"}
                    ]}
                ]
            }
        }, indent=2))
        tpl = self._template(tmp_path)
        result = merge_settings(dst, tpl)
        assert result is True
        data = json.loads(dst.read_text())
        # SessionEnd should still exist but ONLY with the user's hook
        assert "SessionEnd" in data["hooks"]
        se_commands = [
            hook.get("command", "")
            for entry in data["hooks"]["SessionEnd"]
            for hook in entry.get("hooks", [])
        ]
        assert "my-custom-cleanup" in se_commands
        assert not any("product-hook" in c for c in se_commands)

    def test_removes_stale_event_entirely_when_no_user_hooks(self, tmp_path: Path):
        """When template drops an event and product has only our hook, the event is removed entirely."""
        dst = tmp_path / ".claude" / "settings.json"
        dst.parent.mkdir(parents=True)
        dst.write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"matcher": "clear", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" clear"}
                ]}],
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" stop"}
                ]}],
                "SessionEnd": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" session-end"}
                ]}]
            }
        }, indent=2))
        tpl = self._template(tmp_path)
        result = merge_settings(dst, tpl)
        assert result is True
        data = json.loads(dst.read_text())
        assert "SessionEnd" not in data["hooks"]


# =============================================================================
# create_manifest
# =============================================================================


class TestCreateManifest:
    def test_basic_structure(self, tmp_path: Path):
        fw = tmp_path / "framework"
        fw.mkdir()
        hashes = {
            "CLAUDE.md": "abc123",
            ".prawduct/critic-review.md": "def456",
            "tools/product-hook": "ghi789",
            ".claude/settings.json": None,
        }
        manifest = create_manifest(tmp_path / "product", fw, "TestApp", hashes)

        assert manifest["format_version"] == 2
        assert manifest["framework_source"] == str(fw)
        assert manifest["product_name"] == "TestApp"
        assert "last_sync" in manifest
        assert manifest["files"]["CLAUDE.md"]["strategy"] == "block_template"
        assert manifest["files"]["CLAUDE.md"]["generated_hash"] == "abc123"
        assert manifest["files"]["tools/product-hook"]["strategy"] == "always_update"
        assert manifest["files"][".claude/settings.json"]["strategy"] == "merge_settings"
        assert manifest["files"][".claude/settings.json"]["generated_hash"] is None

    def test_has_all_managed_files(self, tmp_path: Path):
        manifest = create_manifest(tmp_path, tmp_path, "X", {})
        assert set(manifest["files"].keys()) == {
            "CLAUDE.md",
            ".prawduct/critic-review.md",
            ".prawduct/pr-review.md",
            ".prawduct/build-governance.md",
            ".claude/skills/pr/SKILL.md",
            ".claude/skills/janitor/SKILL.md",
            ".claude/skills/prawduct-doctor/SKILL.md",
            ".claude/skills/learnings/SKILL.md",
            ".claude/skills/prawduct-advisory/SKILL.md",
            ".claude/skills/backlog/SKILL.md",
            ".claude/skills/critic/SKILL.md",
            "tools/product-hook",
            ".claude/settings.json",
        }


# =============================================================================
# _bootstrap_manifest
# =============================================================================


class TestBootstrapManifest:
    """Tests for automatic manifest creation on repos missing one."""

    def test_bootstrap_creates_manifest_on_sync(self, tmp_path: Path):
        """run_sync bootstraps a manifest when .prawduct/ exists but no manifest."""
        fw = tmp_path / "framework"
        fw.mkdir()
        templates = fw / "templates"
        templates.mkdir()
        (templates / "product-claude.md").write_text(
            f"# {{{{PRODUCT_NAME}}}}\n\n"
            f"{BLOCK_BEGIN}\nContent\n{BLOCK_END}\n"
        )

        product = tmp_path / "myapp"
        product.mkdir()
        (product / ".prawduct").mkdir()

        result = run_sync(str(product), framework_dir=str(fw))
        assert result["synced"] is True
        assert any("Bootstrapped" in a for a in result["actions"])
        assert (product / ".prawduct" / "sync-manifest.json").is_file()

    def test_bootstrap_infers_product_name_from_state(self, tmp_path: Path):
        """Bootstrap reads product_identity.name from project-state.yaml.

        Regression: bootstrapping previously scanned for a non-existent top-level
        `product_name:` key, so cloning a repo into a differently-named directory
        rewrote the banner in .claude/settings.json to the new dir name.
        """
        fw = tmp_path / "framework"
        fw.mkdir()
        (fw / "templates").mkdir()

        product = tmp_path / "mydir"
        product.mkdir()
        prawduct_dir = product / ".prawduct"
        prawduct_dir.mkdir()
        (prawduct_dir / "project-state.yaml").write_text(
            'product_identity:\n  name: "WorldGround"\nschema_version: 2\n'
        )

        manifest = _bootstrap_manifest(product, fw)
        assert manifest["product_name"] == "WorldGround"

    def test_bootstrap_falls_back_to_dir_name(self, tmp_path: Path):
        """Without project-state.yaml, bootstrap uses directory name."""
        fw = tmp_path / "framework"
        fw.mkdir()
        (fw / "templates").mkdir()

        product = tmp_path / "cool-app"
        product.mkdir()
        (product / ".prawduct").mkdir()

        manifest = _bootstrap_manifest(product, fw)
        assert manifest["product_name"] == "cool-app"

    def test_bootstrap_hashes_existing_files(self, tmp_path: Path):
        """Existing files get real hashes; missing files get None."""
        fw = tmp_path / "framework"
        fw.mkdir()
        (fw / "templates").mkdir()

        product = tmp_path / "app"
        product.mkdir()
        (product / ".prawduct").mkdir()
        # Create one managed file
        critic = product / ".prawduct" / "critic-review.md"
        critic.write_text("# Critic review\n")

        manifest = _bootstrap_manifest(product, fw)
        # Existing file gets a real hash
        assert manifest["files"][".prawduct/critic-review.md"]["generated_hash"] is not None
        # Missing file gets None
        assert manifest["files"][".prawduct/pr-review.md"]["generated_hash"] is None

    def test_bootstrap_checks_old_rename_paths(self, tmp_path: Path, monkeypatch):
        """Bootstrap finds files at old rename paths for hash computation."""
        test_renames = {
            "old/cmd.md": "new/skill/SKILL.md",
        }
        test_managed = {
            "new/skill/SKILL.md": {
                "template": "templates/skill.md",
                "strategy": "template",
                "description": "test",
            },
        }
        monkeypatch.setattr(_mod._lib_sync_cmd, "FILE_RENAMES", test_renames)
        monkeypatch.setattr(_mod._lib_sync_cmd, "MANAGED_FILES", test_managed)
        monkeypatch.setattr(_mod._lib_core, "MANAGED_FILES", test_managed)

        fw = tmp_path / "framework"
        fw.mkdir()
        (fw / "templates").mkdir()

        product = tmp_path / "app"
        product.mkdir()
        (product / ".prawduct").mkdir()
        (product / "old").mkdir()
        (product / "old" / "cmd.md").write_text("skill content")

        manifest = _bootstrap_manifest(product, fw)
        # Hash computed from old path, stored under new key
        assert manifest["files"]["new/skill/SKILL.md"]["generated_hash"] is not None

    def test_no_bootstrap_without_prawduct_dir(self, tmp_path: Path):
        """No .prawduct/ directory: returns 'not a prawduct repo'."""
        fw = tmp_path / "framework"
        fw.mkdir()

        product = tmp_path / "random-dir"
        product.mkdir()

        result = run_sync(str(product), framework_dir=str(fw))
        assert result["synced"] is False
        assert result["reason"] == "not a prawduct repo"


# =============================================================================
# apply_renames
# =============================================================================


class TestApplyRenames:
    """Tests for the file rename/move mechanism."""

    def _make_manifest(self, files: dict) -> dict:
        return {"format_version": 2, "files": files}

    def test_move_file_and_transfer_manifest_entry(self, tmp_path: Path, monkeypatch):
        """Old file present, new absent: move file and transfer manifest entry."""
        monkeypatch.setattr(_mod._lib_sync_cmd, "FILE_RENAMES", {
            "old/file.md": "new/dir/SKILL.md",
        })
        (tmp_path / "old").mkdir()
        (tmp_path / "old" / "file.md").write_text("my content")
        manifest = self._make_manifest({
            "old/file.md": {"strategy": "template", "generated_hash": "abc123"},
        })

        actions: list[str] = []
        apply_renames(tmp_path, manifest, actions)

        assert (tmp_path / "new" / "dir" / "SKILL.md").read_text() == "my content"
        assert not (tmp_path / "old" / "file.md").exists()
        assert "new/dir/SKILL.md" in manifest["files"]
        assert "old/file.md" not in manifest["files"]
        assert manifest["files"]["new/dir/SKILL.md"]["generated_hash"] == "abc123"
        assert any("Moved:" in a for a in actions)

    def test_preserves_user_edits(self, tmp_path: Path, monkeypatch):
        """File content is byte-identical after move (user edits survive)."""
        monkeypatch.setattr(_mod._lib_sync_cmd, "FILE_RENAMES", {
            "commands/pr.md": "skills/pr/SKILL.md",
        })
        (tmp_path / "commands").mkdir()
        edited_content = "# PR skill\nUser added this line\n"
        (tmp_path / "commands" / "pr.md").write_text(edited_content)
        manifest = self._make_manifest({
            "commands/pr.md": {"strategy": "template", "generated_hash": "oldhash"},
        })

        actions: list[str] = []
        apply_renames(tmp_path, manifest, actions)

        assert (tmp_path / "skills" / "pr" / "SKILL.md").read_text() == edited_content

    def test_both_exist_deletes_old(self, tmp_path: Path, monkeypatch):
        """Both old and new exist: delete old (leftover), keep new."""
        monkeypatch.setattr(_mod._lib_sync_cmd, "FILE_RENAMES", {
            "old/file.md": "new/file.md",
        })
        (tmp_path / "old").mkdir()
        (tmp_path / "old" / "file.md").write_text("old content")
        (tmp_path / "new").mkdir()
        (tmp_path / "new" / "file.md").write_text("new content")
        manifest = self._make_manifest({
            "old/file.md": {"strategy": "template", "generated_hash": "abc"},
        })

        actions: list[str] = []
        apply_renames(tmp_path, manifest, actions)

        assert (tmp_path / "new" / "file.md").read_text() == "new content"
        assert not (tmp_path / "old" / "file.md").exists()
        assert "old/file.md" not in manifest["files"]
        assert any("leftover" in a for a in actions)

    def test_stale_manifest_entry_cleaned(self, tmp_path: Path, monkeypatch):
        """Old path in manifest but file doesn't exist: clean manifest entry."""
        monkeypatch.setattr(_mod._lib_sync_cmd, "FILE_RENAMES", {
            "old/file.md": "new/file.md",
        })
        manifest = self._make_manifest({
            "old/file.md": {"strategy": "template", "generated_hash": "abc"},
        })

        actions: list[str] = []
        apply_renames(tmp_path, manifest, actions)

        assert "old/file.md" not in manifest["files"]
        assert any("stale" in a.lower() for a in actions)

    def test_neither_exists_noop(self, tmp_path: Path, monkeypatch):
        """Neither old file nor manifest entry: no-op."""
        monkeypatch.setattr(_mod._lib_sync_cmd, "FILE_RENAMES", {
            "old/file.md": "new/file.md",
        })
        manifest = self._make_manifest({})

        actions: list[str] = []
        apply_renames(tmp_path, manifest, actions)

        assert actions == []
        assert manifest["files"] == {}

    def test_empty_directory_cleanup(self, tmp_path: Path, monkeypatch):
        """Empty parent directory of old path is removed after move."""
        monkeypatch.setattr(_mod._lib_sync_cmd, "FILE_RENAMES", {
            "commands/pr.md": "skills/pr/SKILL.md",
        })
        (tmp_path / "commands").mkdir()
        (tmp_path / "commands" / "pr.md").write_text("content")
        manifest = self._make_manifest({
            "commands/pr.md": {"strategy": "template", "generated_hash": "x"},
        })

        actions: list[str] = []
        apply_renames(tmp_path, manifest, actions)

        assert not (tmp_path / "commands").exists()
        assert any("empty directory" in a.lower() for a in actions)

    def test_nonempty_directory_preserved(self, tmp_path: Path, monkeypatch):
        """Parent directory with other files is NOT removed."""
        monkeypatch.setattr(_mod._lib_sync_cmd, "FILE_RENAMES", {
            "commands/pr.md": "skills/pr/SKILL.md",
        })
        (tmp_path / "commands").mkdir()
        (tmp_path / "commands" / "pr.md").write_text("content")
        (tmp_path / "commands" / "custom.md").write_text("user file")
        manifest = self._make_manifest({
            "commands/pr.md": {"strategy": "template", "generated_hash": "x"},
        })

        actions: list[str] = []
        apply_renames(tmp_path, manifest, actions)

        assert (tmp_path / "commands").exists()
        assert (tmp_path / "commands" / "custom.md").exists()

    def test_old_file_no_manifest_entry(self, tmp_path: Path, monkeypatch):
        """Old file exists but no manifest entry: still move it."""
        monkeypatch.setattr(_mod._lib_sync_cmd, "FILE_RENAMES", {
            "commands/pr.md": "skills/pr/SKILL.md",
        })
        (tmp_path / "commands").mkdir()
        (tmp_path / "commands" / "pr.md").write_text("content")
        manifest = self._make_manifest({})

        actions: list[str] = []
        apply_renames(tmp_path, manifest, actions)

        assert (tmp_path / "skills" / "pr" / "SKILL.md").read_text() == "content"
        assert not (tmp_path / "commands" / "pr.md").exists()
        assert any("Moved:" in a for a in actions)


# =============================================================================
# run_sync
# =============================================================================


class TestUntrackGitignoredFiles:
    """untrack_gitignored_files must remove both file AND directory entries from the index.

    Regression: previously the helper called `git rm --cached` without `-r`, so any
    directory entry like `.prawduct/.pr-reviews/` silently failed (git returns 128).
    """

    def _init_repo(self, tmp_path: Path) -> Path:
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)
        subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)
        return repo

    def test_removes_directory_entry(self, tmp_path: Path):
        repo = self._init_repo(tmp_path)
        pr_dir = repo / ".prawduct" / ".pr-reviews"
        pr_dir.mkdir(parents=True)
        (pr_dir / "branch.json").write_text("{}")
        subprocess.run(["git", "add", "-f", ".prawduct"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

        # Confirm tracked
        ls = subprocess.run(
            ["git", "ls-files", ".prawduct/.pr-reviews/branch.json"],
            cwd=repo, capture_output=True, text=True,
        )
        assert ls.stdout.strip(), "expected branch.json tracked"

        untracked = untrack_gitignored_files(repo)
        assert ".prawduct/.pr-reviews" in untracked

        # Confirm removed from index
        ls2 = subprocess.run(
            ["git", "ls-files", ".prawduct/.pr-reviews/branch.json"],
            cwd=repo, capture_output=True, text=True,
        )
        assert not ls2.stdout.strip(), "branch.json should be untracked"
        # File on disk preserved
        assert (pr_dir / "branch.json").exists()

    def test_removes_file_entry(self, tmp_path: Path):
        repo = self._init_repo(tmp_path)
        prawduct = repo / ".prawduct"
        prawduct.mkdir()
        (prawduct / ".session-handoff.md").write_text("old handoff")
        subprocess.run(["git", "add", "-f", ".prawduct/.session-handoff.md"], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)

        untracked = untrack_gitignored_files(repo)
        assert ".prawduct/.session-handoff.md" in untracked


class TestRunSync:
    def _setup_framework(self, tmp_path: Path) -> Path:
        """Create a minimal framework dir with templates."""
        fw = tmp_path / "framework"
        fw.mkdir()
        templates = fw / "templates"
        templates.mkdir()
        (templates / "product-claude.md").write_text(
            f"# {{{{PRODUCT_NAME}}}} CLAUDE.md\n\n"
            f"{BLOCK_BEGIN}\nContent v1\n{BLOCK_END}\n"
        )
        (templates / "critic-review.md").write_text("# {{PRODUCT_NAME}} Critic v1")
        (templates / "product-settings.json").write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"matcher": "clear", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" clear"}
                ]}],
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" stop"}
                ]}],
            }
        }, indent=2))
        tools = fw / "tools"
        tools.mkdir()
        (tools / "product-hook").write_text("#!/usr/bin/env python3\n# hook v1")
        return fw

    def _setup_product(self, tmp_path: Path, fw: Path, product_name: str = "TestApp") -> Path:
        """Create a product dir with manifest and initial files."""
        product = tmp_path / "product"
        product.mkdir()
        (product / ".prawduct").mkdir()

        subs = {"{{PRODUCT_NAME}}": product_name}

        # Write initial files
        claude_content = render_template(fw / "templates" / "product-claude.md", subs)
        (product / "CLAUDE.md").write_text(claude_content)

        critic_content = render_template(fw / "templates" / "critic-review.md", subs)
        (product / ".prawduct" / "critic-review.md").write_text(critic_content)

        (product / "tools").mkdir()
        (product / "tools" / "product-hook").write_bytes(
            (fw / "tools" / "product-hook").read_bytes()
        )

        (product / ".claude").mkdir()
        (product / ".claude" / "settings.json").write_text(
            (fw / "templates" / "product-settings.json").read_text()
        )

        # Build file hashes (block hash for CLAUDE.md)
        hashes = {
            "CLAUDE.md": compute_block_hash(claude_content),
            ".prawduct/critic-review.md": compute_hash(product / ".prawduct" / "critic-review.md"),
            "tools/product-hook": compute_hash(product / "tools" / "product-hook"),
            ".claude/settings.json": None,  # merge_settings doesn't use hash
        }

        # Write .gitignore so sync doesn't report it as an action
        (product / ".gitignore").write_text(
            "\n".join(GITIGNORE_ENTRIES) + "\n"
        )

        manifest = create_manifest(product, fw, product_name, hashes)
        (product / ".prawduct" / "sync-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )

        return product

    def test_no_prawduct_dir_skips(self, tmp_path: Path):
        product = tmp_path / "product"
        product.mkdir()
        result = run_sync(str(product))
        assert result["synced"] is False
        assert result["reason"] == "not a prawduct repo"

    def test_invalid_manifest_skips(self, tmp_path: Path):
        product = tmp_path / "product"
        (product / ".prawduct").mkdir(parents=True)
        (product / ".prawduct" / "sync-manifest.json").write_text("bad json{{{")
        result = run_sync(str(product))
        assert result["synced"] is False
        assert result["reason"] == "invalid manifest JSON"

    def test_backlog_probe_silent_without_legacy_backlog(self, tmp_path: Path):
        """The v1.7.0 production roster contains the `legacy-backlog-format`
        probe (Phase 1's empty-roster no-op ship is now historical). On a
        product with no `.prawduct/backlog.md`, the probe stays silent, so a
        real sync still writes an empty advisory store and the next briefing
        emits no ADVISORIES section (spec A5 — no "0 active" noise).

        This exercises the true production path — `run_sync` →
        `run_sync_advisories`, which calls `register_backlog_probes()` then
        `run_all_probes`. The empty store here is the probe correctly NOT
        firing, not an empty roster (see the positive trigger/resolve test
        below)."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # A real sync runs the advisory step regardless of whether any managed
        # file changed (the step sits before run_sync's final return). reason is
        # the benign "no updates needed", never an error.
        result = run_sync(str(product), framework_dir=str(fw))
        assert result["reason"] in ("ok", "no updates needed")

        # Store written, but no advisories — the backlog probe is silent with
        # no backlog file present.
        store = _mod._lib_advisory_store.read_store(str(product))
        assert store["advisories"] == []

        # Briefing omits the section entirely (A5) — load product-hook and
        # render. The hook is an extensionless shebang script, so it needs an
        # explicit SourceFileLoader (mirrors test_product_hook._load_product_hook).
        import importlib.machinery

        hook_path = Path(__file__).resolve().parent.parent / "tools" / "product-hook"
        hook_loader = importlib.machinery.SourceFileLoader("product_hook_noop", str(hook_path))
        hook_spec = importlib.util.spec_from_loader("product_hook_noop", hook_loader)
        hook_mod = importlib.util.module_from_spec(hook_spec)
        hook_loader.exec_module(hook_mod)
        briefing = hook_mod.assemble_session_briefing(product, [])
        assert "ADVISORIES" not in briefing

    def test_legacy_backlog_triggers_then_resolves_on_migration(self, tmp_path: Path):
        """End-to-end: a product with a legacy backlog (>5 items, none
        structured) gets a `feature: backlog` advisory on sync; recording
        `backlog_format_version: 2` in project-state.yaml + re-syncing
        auto-resolves it (resolution condition reads the shared answer store)."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)
        legacy = "# Backlog\n\n## Queue\n\n" + "".join(
            f"- **legacy item {i}** (reflection) body\n" for i in range(6)
        )
        (product / ".prawduct" / "backlog.md").write_text(legacy)

        run_sync(str(product), framework_dir=str(fw))
        store = _mod._lib_advisory_store.read_store(str(product))
        active = [a for a in store["advisories"] if a.get("state") == "active"]
        assert len(active) == 1
        adv = active[0]
        assert adv["feature"] == "backlog"
        assert adv["type"] == "legacy-backlog-format"
        assert adv["recommended_action"] == "/backlog migrate"

        # Migration writes the resolution fact; re-sync auto-resolves.
        (product / ".prawduct" / "project-state.yaml").write_text(
            "backlog_format_version: 2\n"
        )
        run_sync(str(product), framework_dir=str(fw))
        store2 = _mod._lib_advisory_store.read_store(str(product))
        assert [a for a in store2["advisories"] if a.get("state") == "active"] == []
        resolved = [a for a in store2["advisories"] if a.get("state") == "resolved"]
        assert any(a["id"] == adv["id"] and a.get("resolved_by") == "sync" for a in resolved)

    def test_framework_not_found_skips(self, tmp_path: Path):
        product = tmp_path / "product"
        (product / ".prawduct").mkdir(parents=True)
        manifest = {
            "format_version": 1,
            "framework_source": "/nonexistent/path",
            "product_name": "Test",
            "files": {},
        }
        (product / ".prawduct" / "sync-manifest.json").write_text(json.dumps(manifest))
        result = run_sync(str(product))
        assert result["synced"] is False
        assert result["reason"] == "framework not found"

    def test_sibling_prawduct_fallback(self, tmp_path: Path):
        """When manifest points to nonexistent path, fall back to ../prawduct."""
        # Create framework at sibling "prawduct" directory
        parent = tmp_path / "source"
        parent.mkdir()
        fw = parent / "prawduct"
        fw.mkdir()
        templates = fw / "templates"
        templates.mkdir()
        (templates / "product-claude.md").write_text(
            f"# {{{{PRODUCT_NAME}}}} CLAUDE.md\n\n"
            f"{BLOCK_BEGIN}\nContent v2\n{BLOCK_END}\n"
        )
        (templates / "critic-review.md").write_text("# {{PRODUCT_NAME}} Critic v1")
        (templates / "product-settings.json").write_text(json.dumps({
            "hooks": {"SessionStart": [], "Stop": []}
        }))
        tools = fw / "tools"
        tools.mkdir()
        (tools / "product-hook").write_text("#!/usr/bin/env python3\n# hook v2")

        # Create product as sibling with manifest pointing to nonexistent path
        product = parent / "myapp"
        product.mkdir()
        (product / ".prawduct").mkdir()
        (product / "CLAUDE.md").write_text(
            f"# MyApp CLAUDE.md\n\n{BLOCK_BEGIN}\nContent v1\n{BLOCK_END}\n"
        )
        (product / ".prawduct" / "critic-review.md").write_text("# MyApp Critic v1")
        (product / "tools").mkdir()
        (product / "tools" / "product-hook").write_text("#!/usr/bin/env python3\n# hook v1")
        (product / ".claude").mkdir()
        (product / ".claude" / "settings.json").write_text(json.dumps({"hooks": {}}))

        block_hash = compute_block_hash(f"# MyApp CLAUDE.md\n\n{BLOCK_BEGIN}\nContent v1\n{BLOCK_END}\n")
        manifest = {
            "format_version": 1,
            "framework_source": "/nonexistent/old/path",
            "product_name": "MyApp",
            "last_sync": "2026-01-01T00:00:00Z",
            "files": {
                "CLAUDE.md": {
                    "template": "templates/product-claude.md",
                    "strategy": "block_template",
                    "generated_hash": block_hash,
                },
                ".prawduct/critic-review.md": {
                    "template": "templates/critic-review.md",
                    "strategy": "template",
                    "generated_hash": compute_hash(product / ".prawduct" / "critic-review.md"),
                },
                "tools/product-hook": {
                    "source": "tools/product-hook",
                    "strategy": "always_update",
                    "generated_hash": compute_hash(product / "tools" / "product-hook"),
                },
                ".claude/settings.json": {
                    "template": "templates/product-settings.json",
                    "strategy": "merge_settings",
                    "generated_hash": None,
                },
            },
        }
        (product / ".prawduct" / "sync-manifest.json").write_text(json.dumps(manifest))

        result = run_sync(str(product))
        assert result["synced"] is True
        assert any("CLAUDE.md" in a for a in result["actions"])
        assert "Content v2" in (product / "CLAUDE.md").read_text()

    def test_no_changes_needed(self, tmp_path: Path):
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)
        result = run_sync(str(product), framework_dir=str(fw))
        assert result["synced"] is False
        assert result["reason"] == "no updates needed"

    def test_template_update_propagates(self, tmp_path: Path):
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # Update the template block content
        (fw / "templates" / "product-claude.md").write_text(
            f"# {{{{PRODUCT_NAME}}}} CLAUDE.md\n\n"
            f"{BLOCK_BEGIN}\nContent v2\n{BLOCK_END}\n"
        )

        result = run_sync(str(product), framework_dir=str(fw))
        assert result["synced"] is True
        assert any("CLAUDE.md" in a for a in result["actions"])
        content = (product / "CLAUDE.md").read_text()
        assert "Content v2" in content

    def test_user_edits_inside_block_overwritten(self, tmp_path: Path):
        """Marker contract: content inside the block is framework-owned and
        overwritten on sync regardless of --force."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # User edits inside the block (against the contract)
        claude = (product / "CLAUDE.md").read_text()
        claude = claude.replace("Content v1", "My custom content")
        (product / "CLAUDE.md").write_text(claude)

        # Update template
        (fw / "templates" / "product-claude.md").write_text(
            f"# {{{{PRODUCT_NAME}}}} CLAUDE.md\n\n"
            f"{BLOCK_BEGIN}\nContent v2\n{BLOCK_END}\n"
        )

        result = run_sync(str(product), framework_dir=str(fw))
        assert any("CLAUDE.md" in a for a in result["actions"])
        assert not any("Skipped CLAUDE.md" in n for n in result["notes"])
        content = (product / "CLAUDE.md").read_text()
        assert "Content v2" in content
        assert "My custom content" not in content

    def test_force_flag_no_op_for_block_template(self, tmp_path: Path):
        """--force is unnecessary for block_template (always overwrites by default)
        but should produce the same result without errors."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        claude = (product / "CLAUDE.md").read_text()
        claude = claude.replace("Content v1", "My custom content")
        (product / "CLAUDE.md").write_text(claude)

        (fw / "templates" / "product-claude.md").write_text(
            f"# {{{{PRODUCT_NAME}}}} CLAUDE.md\n\n"
            f"{BLOCK_BEGIN}\nContent v2\n{BLOCK_END}\n"
        )

        result = run_sync(str(product), framework_dir=str(fw), force=True)
        assert any("CLAUDE.md" in a for a in result["actions"])
        content = (product / "CLAUDE.md").read_text()
        assert "Content v2" in content
        assert "My custom content" not in content

    def test_always_update_overwrites(self, tmp_path: Path):
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # Update hook source
        (fw / "tools" / "product-hook").write_text("#!/usr/bin/env python3\n# hook v2")

        result = run_sync(str(product), framework_dir=str(fw))
        assert result["synced"] is True
        assert any("product-hook" in a for a in result["actions"])
        assert "hook v2" in (product / "tools" / "product-hook").read_text()

    def test_manifest_updated_after_sync(self, tmp_path: Path):
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # Update template
        (fw / "templates" / "product-claude.md").write_text(
            f"# {{{{PRODUCT_NAME}}}} CLAUDE.md\n\n"
            f"{BLOCK_BEGIN}\nContent v2\n{BLOCK_END}\n"
        )

        run_sync(str(product), framework_dir=str(fw))

        # Running again should find nothing to do
        result = run_sync(str(product), framework_dir=str(fw))
        assert result["synced"] is False
        assert result["reason"] == "no updates needed"

    def test_missing_template_noted(self, tmp_path: Path):
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # Delete a template
        (fw / "templates" / "critic-review.md").unlink()

        # Also update another template to trigger sync
        (fw / "templates" / "product-claude.md").write_text(
            f"# {{{{PRODUCT_NAME}}}} v2\n\n"
            f"{BLOCK_BEGIN}\nContent v2\n{BLOCK_END}\n"
        )

        result = run_sync(str(product), framework_dir=str(fw))
        assert any("Template missing" in n for n in result["notes"])

    def test_framework_dir_from_env(self, tmp_path: Path, monkeypatch):
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # Point manifest at nonexistent dir
        manifest_path = product / ".prawduct" / "sync-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["framework_source"] = "/nonexistent"
        manifest_path.write_text(json.dumps(manifest))

        # But set env var to real framework
        monkeypatch.setenv("PRAWDUCT_FRAMEWORK_DIR", str(fw))

        # Update template to have something to sync
        (fw / "templates" / "product-claude.md").write_text(
            f"# {{{{PRODUCT_NAME}}}} v2\n\n"
            f"{BLOCK_BEGIN}\nContent v2\n{BLOCK_END}\n"
        )

        result = run_sync(str(product))
        assert result["synced"] is True

    def test_user_edited_template_file_skipped(self, tmp_path: Path):
        """Template strategy skips when user edited file and template changed."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # User edits critic-review.md
        (product / ".prawduct" / "critic-review.md").write_text("# My custom critic review")

        # Update template
        (fw / "templates" / "critic-review.md").write_text("# {{PRODUCT_NAME}} Critic v2")

        result = run_sync(str(product), framework_dir=str(fw))
        assert not any("critic-review" in a for a in result["actions"])
        assert any("local edits" in n and "critic-review" in n for n in result["notes"])
        assert "My custom critic review" in (product / ".prawduct" / "critic-review.md").read_text()

    def test_force_overwrites_user_edited_template_file(self, tmp_path: Path):
        """--force overwrites user-edited template-strategy files."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # User edits critic-review.md
        (product / ".prawduct" / "critic-review.md").write_text("# My custom critic review")

        # Update template
        (fw / "templates" / "critic-review.md").write_text("# {{PRODUCT_NAME}} Critic v2")

        result = run_sync(str(product), framework_dir=str(fw), force=True)
        assert any("Force-updated" in a and "critic-review" in a for a in result["actions"])
        assert "Critic v2" in (product / ".prawduct" / "critic-review.md").read_text()

    def test_autofix_local_already_at_target_refreshes_manifest_silently(self, tmp_path: Path):
        # Local content matches the current rendered template, but the manifest's
        # stored_hash is stale (e.g. a prior manual sync left the file caught up
        # without updating the manifest). The previous code reported "local edits"
        # and skipped — silently freezing the file forever. Autofix detects
        # local == rendered and refreshes the manifest hash without warning.
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        (fw / "templates" / "critic-review.md").write_text("# {{PRODUCT_NAME}} Critic v2")
        (product / ".prawduct" / "critic-review.md").write_text("# TestApp Critic v2")

        result = run_sync(str(product), framework_dir=str(fw))

        assert not any("local edits" in n and "critic-review" in n for n in result["notes"])
        assert not any("Force-updated" in a and "critic-review" in a for a in result["actions"])
        assert (product / ".prawduct" / "critic-review.md").read_text() == "# TestApp Critic v2"

        manifest = json.loads((product / ".prawduct" / "sync-manifest.json").read_text())
        rendered_hash = hashlib.sha256(b"# TestApp Critic v2").hexdigest()
        assert manifest["files"][".prawduct/critic-review.md"]["generated_hash"] == rendered_hash

    def test_autofix_null_stored_hash_with_matching_content(self, tmp_path: Path):
        # null stored_hash + local matches current template → autofix records the hash.
        # Previously this was the most common silent-skip case.
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        manifest = json.loads((product / ".prawduct" / "sync-manifest.json").read_text())
        manifest["files"][".prawduct/critic-review.md"]["generated_hash"] = None
        (product / ".prawduct" / "sync-manifest.json").write_text(json.dumps(manifest, indent=2))

        (fw / "templates" / "critic-review.md").write_text("# {{PRODUCT_NAME}} Critic v2")
        (product / ".prawduct" / "critic-review.md").write_text("# TestApp Critic v2")

        result = run_sync(str(product), framework_dir=str(fw))

        assert not any("local edits" in n and "critic-review" in n for n in result["notes"])
        new_manifest = json.loads((product / ".prawduct" / "sync-manifest.json").read_text())
        assert new_manifest["files"][".prawduct/critic-review.md"]["generated_hash"] is not None

    def test_autofix_does_not_mask_genuine_local_edits(self, tmp_path: Path):
        # Autofix only triggers when local == rendered. Files with genuine local
        # customization (different from both stored and current template) still skip
        # with the "local edits" warning, preserving user work.
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        (product / ".prawduct" / "critic-review.md").write_text("# Custom local critic")
        (fw / "templates" / "critic-review.md").write_text("# {{PRODUCT_NAME}} Critic v2")

        result = run_sync(str(product), framework_dir=str(fw))

        assert (product / ".prawduct" / "critic-review.md").read_text() == "# Custom local critic"
        assert any("local edits" in n and "critic-review" in n for n in result["notes"])

    def test_merge_settings_during_sync(self, tmp_path: Path):
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # Update settings template with banner
        (fw / "templates" / "product-settings.json").write_text(json.dumps({
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

        result = run_sync(str(product), framework_dir=str(fw))
        assert result["synced"] is True
        data = json.loads((product / ".claude" / "settings.json").read_text())
        assert "TestApp" in data["companyAnnouncements"]

    def test_self_heals_product_name_from_project_state(self, tmp_path: Path):
        """Sync re-reads product_identity.name from project-state.yaml and
        corrects a manifest that was bootstrapped with the wrong name.

        Regression: legacy manifests (pre-v1.3.9 bootstraps, or product_identity
        changed after init) kept a stale product_name that was never refreshed,
        so every sync re-rendered settings.json and other templates with the
        wrong banner — producing perpetual dirty diffs on managed files.
        """
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw, product_name="OldName")

        # Commit the correct identity in project-state.yaml; manifest still
        # has "OldName" from _setup_product (simulating a legacy clone).
        (product / ".prawduct" / "project-state.yaml").write_text(
            'product_identity:\n  name: "CorrectName"\nschema_version: 2\n'
        )

        result = run_sync(str(product), framework_dir=str(fw))
        assert result["synced"] is True
        assert any(
            "Corrected product_name" in a and "OldName" in a and "CorrectName" in a
            for a in result["actions"]
        ), result["actions"]

        manifest = json.loads((product / ".prawduct" / "sync-manifest.json").read_text())
        assert manifest["product_name"] == "CorrectName"

    def test_leaves_product_name_alone_when_matches_identity(self, tmp_path: Path):
        """No correction action when manifest and project-state agree."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw, product_name="TestApp")
        (product / ".prawduct" / "project-state.yaml").write_text(
            'product_identity:\n  name: "TestApp"\nschema_version: 2\n'
        )

        result = run_sync(str(product), framework_dir=str(fw))
        assert not any("Corrected product_name" in a for a in result["actions"])

    def test_falls_back_to_manifest_when_identity_missing(self, tmp_path: Path):
        """Without product_identity.name, sync keeps the manifest-cached name.

        Ensures the self-heal doesn't clobber legacy manifests whose
        project-state.yaml predates the identity block.
        """
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw, product_name="LegacyName")
        # Intentionally no project-state.yaml

        result = run_sync(str(product), framework_dir=str(fw))
        assert not any("Corrected product_name" in a for a in result["actions"])
        assert not any("Populated product_name" in a for a in result["actions"])
        manifest = json.loads((product / ".prawduct" / "sync-manifest.json").read_text())
        assert manifest["product_name"] == "LegacyName"

    def test_populates_missing_product_name_from_identity(self, tmp_path: Path):
        """When manifest has no product_name but project-state has identity,
        sync populates the cache and logs a visible action.

        Covers the legacy-manifest path where cached_name is None but identity
        is present — mutation must persist and be user-visible.
        """
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw, product_name="TestApp")
        # Strip product_name from manifest (simulates a manifest format that
        # never wrote the field, or one that was manually cleared).
        manifest_path = product / ".prawduct" / "sync-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        del manifest["product_name"]
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

        (product / ".prawduct" / "project-state.yaml").write_text(
            'product_identity:\n  name: "RealName"\nschema_version: 2\n'
        )

        result = run_sync(str(product), framework_dir=str(fw))
        assert any(
            "Populated product_name" in a and "RealName" in a
            for a in result["actions"]
        ), result["actions"]

        manifest = json.loads(manifest_path.read_text())
        assert manifest["product_name"] == "RealName"

    def test_no_mutation_when_cache_missing_and_identity_missing(self, tmp_path: Path):
        """When both manifest product_name and identity are absent, sync
        renders with the directory name but does not silently mutate the
        manifest cache.

        Keeping the manifest untouched avoids a cache write that would only
        ever be reflected if some other action triggered a manifest flush.
        """
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw, product_name="StartName")
        manifest_path = product / ".prawduct" / "sync-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        del manifest["product_name"]
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        # No project-state.yaml, no identity.

        run_sync(str(product), framework_dir=str(fw))

        manifest = json.loads(manifest_path.read_text())
        assert "product_name" not in manifest

    def test_backfills_missing_managed_files(self, tmp_path: Path):
        """Sync adds managed files missing from manifest (added after product init)."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # Add a new template to the framework (simulating a new managed file)
        (fw / "templates" / "pr-review.md").write_text("# {{PRODUCT_NAME}} PR Review v1")
        (fw / ".claude" / "skills" / "pr").mkdir(parents=True, exist_ok=True)
        (fw / ".claude" / "skills" / "pr" / "SKILL.md").write_text("# PR skill for {{PRODUCT_NAME}}")

        # Remove pr-review and skills/pr from the manifest (simulating old product)
        manifest_path = product / ".prawduct" / "sync-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"].pop(".prawduct/pr-review.md", None)
        manifest["files"].pop(".claude/skills/pr/SKILL.md", None)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

        result = run_sync(str(product), framework_dir=str(fw))
        assert result["synced"] is True
        assert any("New:" in a and "pr-review" in a for a in result["actions"])
        assert any("New:" in a and "SKILL.md" in a for a in result["actions"])
        assert (product / ".prawduct" / "pr-review.md").is_file()
        assert (product / ".claude" / "skills" / "pr" / "SKILL.md").is_file()

        # Verify manifest now includes the new files
        manifest = json.loads(manifest_path.read_text())
        assert ".prawduct/pr-review.md" in manifest["files"]
        assert ".claude/skills/pr/SKILL.md" in manifest["files"]

    def test_backfill_idempotent(self, tmp_path: Path):
        """Running sync twice after backfill produces no updates."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        (fw / "templates" / "pr-review.md").write_text("# {{PRODUCT_NAME}} PR Review v1")
        (fw / ".claude" / "skills" / "pr").mkdir(parents=True, exist_ok=True)
        (fw / ".claude" / "skills" / "pr" / "SKILL.md").write_text("# PR skill for {{PRODUCT_NAME}}")

        # Remove from manifest
        manifest_path = product / ".prawduct" / "sync-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest["files"].pop(".prawduct/pr-review.md", None)
        manifest["files"].pop(".claude/skills/pr/SKILL.md", None)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

        # First sync creates files
        run_sync(str(product), framework_dir=str(fw))

        # Second sync — nothing to do
        result = run_sync(str(product), framework_dir=str(fw))
        assert result["synced"] is False
        assert result["reason"] == "no updates needed"

    def test_sync_notes_unignored_managed_files(self, tmp_path: Path):
        """Sync produces notes telling user to git-add unignored managed files."""
        fw = self._setup_framework(tmp_path)
        product = tmp_path / "product"
        product.mkdir()
        (product / ".prawduct").mkdir(parents=True)
        (product / ".prawduct" / "critic-review.md").write_text("# Critic")

        # Create a manifest pointing at framework
        manifest = {
            "format_version": 2,
            "framework_source": str(fw),
            "product_name": "Test",
            "files": {},
        }
        (product / ".prawduct" / "sync-manifest.json").write_text(json.dumps(manifest))

        # Incorrectly gitignore a managed file
        gi = product / ".gitignore"
        gi.write_text(
            "\n".join(GITIGNORE_ENTRIES) + "\n"
            + ".prawduct/critic-review.md\n"
        )

        result = run_sync(str(product), framework_dir=str(fw))
        matching_notes = [n for n in result["notes"] if "critic-review.md" in n and "git add" in n]
        assert len(matching_notes) == 1


# =============================================================================
# run_sync — stale-clean detection (auto-resolves files matching historical templates)
# =============================================================================


class TestStaleCleanDetection:
    """Verifies that run_sync auto-resolves 'stale-clean' files (whose content
    matches a historical framework template render) without --force, while
    still skipping genuinely user-edited files."""

    def _make_git_framework(self, tmp_path: Path) -> Path:
        fw = tmp_path / "framework"
        fw.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=fw, check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=fw, check=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=fw, check=True)
        (fw / "templates").mkdir()
        # Initial templates required by run_sync
        (fw / "templates" / "product-claude.md").write_text(
            f"# {{{{PRODUCT_NAME}}}} CLAUDE.md\n\n{BLOCK_BEGIN}\nv1 block\n{BLOCK_END}\n"
        )
        (fw / "templates" / "critic-review.md").write_text("# v1 critic for {{PRODUCT_NAME}}\n")
        (fw / "templates" / "pr-review.md").write_text("# v1 pr review for {{PRODUCT_NAME}}\n")
        (fw / "templates" / "product-settings.json").write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"matcher": "clear", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" clear"}
                ]}],
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" stop"}
                ]}],
            }
        }, indent=2))
        (fw / "tools").mkdir()
        (fw / "tools" / "product-hook").write_text("#!/usr/bin/env python3\n# hook v1")
        subprocess.run(["git", "add", "."], cwd=fw, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "initial framework"], cwd=fw, check=True)
        return fw

    def _bump_critic_template(self, fw: Path, content: str, message: str) -> None:
        (fw / "templates" / "critic-review.md").write_text(content)
        subprocess.run(["git", "add", "templates/critic-review.md"], cwd=fw, check=True)
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=fw, check=True)

    def _bump_pr_template(self, fw: Path, content: str, message: str) -> None:
        (fw / "templates" / "pr-review.md").write_text(content)
        subprocess.run(["git", "add", "templates/pr-review.md"], cwd=fw, check=True)
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=fw, check=True)

    def _make_product_with_stale_critic(self, tmp_path: Path, fw: Path,
                                          critic_content: str) -> Path:
        """Set up product with critic-review.md content NOT matching the manifest's
        stored hash AND not matching the current rendered template (the stale-file
        situation)."""
        product = tmp_path / "product"
        product.mkdir()
        (product / ".prawduct").mkdir()
        (product / "tools").mkdir()
        (product / ".claude").mkdir()

        subs = {"{{PRODUCT_NAME}}": "App"}
        # CLAUDE.md and product-hook stay current
        (product / "CLAUDE.md").write_text(
            render_template(fw / "templates" / "product-claude.md", subs)
        )
        (product / "tools" / "product-hook").write_text(
            (fw / "tools" / "product-hook").read_text()
        )
        (product / ".claude" / "settings.json").write_text(
            (fw / "templates" / "product-settings.json").read_text()
        )
        # Critic gets the supplied content (the "stale" or "edited" content)
        (product / ".prawduct" / "critic-review.md").write_text(critic_content)

        # Manifest stores a fake "stored hash" different from both current file and
        # the current rendered template — this triggers the local-edits skip path
        # (or the new stale-clean check).
        hashes = {
            "CLAUDE.md": compute_block_hash((product / "CLAUDE.md").read_text()),
            ".prawduct/critic-review.md": "stale-stored-hash-doesnt-match-anything",
            "tools/product-hook": compute_hash(product / "tools" / "product-hook"),
            ".claude/settings.json": None,
        }
        (product / ".gitignore").write_text("\n".join(GITIGNORE_ENTRIES) + "\n")
        manifest = create_manifest(product, fw, "App", hashes)
        (product / ".prawduct" / "sync-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        return product

    def test_stale_clean_file_auto_resolved(self, tmp_path: Path):
        """Product file matches an old historical render → auto-update without --force,
        action contains 'Auto-resolved' and the short SHA, manifest hash is updated."""
        fw = self._make_git_framework(tmp_path)
        # Bump critic template; v1 content is now historical
        self._bump_critic_template(fw, "# v2 critic for {{PRODUCT_NAME}}\n", "bump critic")

        # Product still has v1's rendered content (the stale-clean case)
        product = self._make_product_with_stale_critic(tmp_path, fw, "# v1 critic for App\n")

        result = run_sync(str(product), framework_dir=str(fw), no_pull=True)
        critic_actions = [a for a in result["actions"] if "critic-review.md" in a]
        assert any("Auto-resolved" in a for a in critic_actions), critic_actions
        # File is now at v2 (current template render)
        assert (product / ".prawduct" / "critic-review.md").read_text() == "# v2 critic for App\n"
        # Manifest's generated_hash now matches the current rendered template
        new_manifest = json.loads((product / ".prawduct" / "sync-manifest.json").read_text())
        new_hash = new_manifest["files"][".prawduct/critic-review.md"]["generated_hash"]
        expected_hash = hashlib.sha256(b"# v2 critic for App\n").hexdigest()
        assert new_hash == expected_hash
        # No skip note for this file
        assert not any("local edits" in n and "critic-review.md" in n for n in result["notes"])

    def test_genuine_local_edit_still_skipped(self, tmp_path: Path):
        """Product file matches no historical render → existing skip-with-force note."""
        fw = self._make_git_framework(tmp_path)
        self._bump_critic_template(fw, "# v2 critic for {{PRODUCT_NAME}}\n", "bump critic")

        # Product has hand-edited content that no historical template render produced
        product = self._make_product_with_stale_critic(
            tmp_path, fw, "# my hand-written critic — not a framework version\n"
        )

        result = run_sync(str(product), framework_dir=str(fw), no_pull=True)
        assert any("local edits" in n and "critic-review.md" in n for n in result["notes"])
        assert not any("Auto-resolved" in a and "critic-review.md" in a for a in result["actions"])
        # File unchanged
        assert (product / ".prawduct" / "critic-review.md").read_text() == \
            "# my hand-written critic — not a framework version\n"

    def test_force_flag_still_works_for_genuine_edits(self, tmp_path: Path):
        """--force overrides the genuine-edit skip and overwrites with the current template."""
        fw = self._make_git_framework(tmp_path)
        self._bump_critic_template(fw, "# v2 critic for {{PRODUCT_NAME}}\n", "bump critic")

        product = self._make_product_with_stale_critic(
            tmp_path, fw, "# my hand-written critic — not a framework version\n"
        )

        result = run_sync(str(product), framework_dir=str(fw), no_pull=True, force=True)
        assert any("Force-updated" in a and "critic-review.md" in a for a in result["actions"])
        assert (product / ".prawduct" / "critic-review.md").read_text() == "# v2 critic for App\n"

    def test_stale_clean_takes_precedence_over_force(self, tmp_path: Path):
        """Even with --force, the stale-clean path runs first (cheaper note for the user
        and unambiguous about why the file changed)."""
        fw = self._make_git_framework(tmp_path)
        self._bump_critic_template(fw, "# v2 critic for {{PRODUCT_NAME}}\n", "bump critic")

        product = self._make_product_with_stale_critic(tmp_path, fw, "# v1 critic for App\n")

        result = run_sync(str(product), framework_dir=str(fw), no_pull=True, force=True)
        # Auto-resolved wins; no Force-updated for this file
        critic_actions = [a for a in result["actions"] if "critic-review.md" in a]
        assert any("Auto-resolved" in a for a in critic_actions)
        assert not any("Force-updated" in a for a in critic_actions)

    def test_mixed_batch_per_file_outcome(self, tmp_path: Path):
        """Two stale files in one sync, different templates: one stale-clean,
        one genuinely edited. Each file gets its correct outcome — auto-resolved
        for the stale-clean, skipped for the edited."""
        fw = self._make_git_framework(tmp_path)
        # Bump both templates so v1 content for each is now historical
        self._bump_critic_template(fw, "# v2 critic for {{PRODUCT_NAME}}\n", "bump critic")
        self._bump_pr_template(fw, "# v2 pr review for {{PRODUCT_NAME}}\n", "bump pr-review")

        # Set up product with critic-review.md stale-clean (matches v1 render)
        # and pr-review.md genuinely edited (matches no historical render)
        product = self._make_product_with_stale_critic(tmp_path, fw, "# v1 critic for App\n")
        (product / ".prawduct" / "pr-review.md").write_text(
            "# my hand-written pr-review — never a framework version\n"
        )
        # Manifest needs an entry for pr-review.md with a stale stored hash
        manifest = json.loads((product / ".prawduct" / "sync-manifest.json").read_text())
        manifest["files"][".prawduct/pr-review.md"] = {
            "template": "templates/pr-review.md",
            "strategy": "template",
            "generated_hash": "stale-stored-hash-doesnt-match-anything",
        }
        (product / ".prawduct" / "sync-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )

        result = run_sync(str(product), framework_dir=str(fw), no_pull=True)

        # critic-review.md → auto-resolved (stale-clean)
        assert any(
            "Auto-resolved" in a and "critic-review.md" in a
            for a in result["actions"]
        ), result["actions"]
        # pr-review.md → skipped (genuine edit)
        assert any(
            "local edits" in n and "pr-review.md" in n
            for n in result["notes"]
        ), result["notes"]
        # And not the wrong way around
        assert not any(
            "Auto-resolved" in a and "pr-review.md" in a
            for a in result["actions"]
        )
        assert not any(
            "local edits" in n and "critic-review.md" in n
            for n in result["notes"]
        )

        # Confirm files: critic updated to v2; pr-review unchanged
        assert (product / ".prawduct" / "critic-review.md").read_text() == "# v2 critic for App\n"
        assert (product / ".prawduct" / "pr-review.md").read_text() == \
            "# my hand-written pr-review — never a framework version\n"

    def test_render_cache_populated_during_history_walk(self, tmp_path: Path):
        """The per-sync render cache must be populated by _match_historical_render
        as it walks history. Verified by counting `git show` invocations: each
        unique (sha, historical_path) pair should be looked up at most once."""
        fw = self._make_git_framework(tmp_path)
        # Multiple bumps so the helper has several commits to walk
        self._bump_critic_template(fw, "# v2 critic for {{PRODUCT_NAME}}\n", "bump critic v2")
        self._bump_critic_template(fw, "# v3 critic for {{PRODUCT_NAME}}\n", "bump critic v3")
        self._bump_critic_template(fw, "# v4 critic for {{PRODUCT_NAME}}\n", "bump critic v4")

        product = self._make_product_with_stale_critic(tmp_path, fw, "# v1 critic for App\n")

        original_run = subprocess.run
        show_calls: list[list[str]] = []

        def counting_run(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args", [])
            if isinstance(cmd, list) and "show" in cmd and any(":" in str(t) for t in cmd):
                show_calls.append(list(cmd))
            return original_run(*args, **kwargs)

        import unittest.mock as mock
        with mock.patch.object(subprocess, "run", side_effect=counting_run):
            run_sync(str(product), framework_dir=str(fw), no_pull=True)

        # Each `git show <sha>:<path>` argument should appear at most once
        # — duplicates would mean the cache failed to memoize.
        show_args = []
        for c in show_calls:
            for token in c:
                if isinstance(token, str) and ":" in token and "/" in token:
                    show_args.append(token)
        assert len(show_args) == len(set(show_args)), (
            f"Duplicate git-show args (cache miss): {show_args}"
        )
        # And we did walk *some* history (sanity check — at least one show happened)
        assert len(show_args) >= 1, "Expected at least one git-show during history walk"


# =============================================================================
# extract_block
# =============================================================================


class TestExtractBlock:
    def test_markers_found(self):
        content = f"before\n{BLOCK_BEGIN}\nblock body\n{BLOCK_END}\nafter\n"
        block, before, after = extract_block(content)
        assert block == f"{BLOCK_BEGIN}\nblock body\n{BLOCK_END}"
        assert before == "before\n"
        assert after == "\nafter\n"

    def test_missing_markers(self):
        content = "no markers here"
        block, before, after = extract_block(content)
        assert block is None
        assert before == content
        assert after == ""

    def test_malformed_end_before_begin(self):
        content = f"{BLOCK_END}\nstuff\n{BLOCK_BEGIN}\n"
        block, before, after = extract_block(content)
        assert block is None

    def test_begin_without_end(self):
        content = f"before\n{BLOCK_BEGIN}\nblock body\n"
        block, before, after = extract_block(content)
        assert block is None

    def test_end_without_begin(self):
        content = f"block body\n{BLOCK_END}\nafter\n"
        block, before, after = extract_block(content)
        assert block is None

    def test_empty_block(self):
        content = f"before\n{BLOCK_BEGIN}{BLOCK_END}\nafter\n"
        block, before, after = extract_block(content)
        assert block == f"{BLOCK_BEGIN}{BLOCK_END}"
        assert before == "before\n"
        assert after == "\nafter\n"

    def test_roundtrip_invariant(self):
        content = f"title\n\n{BLOCK_BEGIN}\nbody\n{BLOCK_END}\nfooter\n"
        block, before, after = extract_block(content)
        assert before + block + after == content


# =============================================================================
# compute_block_hash
# =============================================================================


class TestComputeBlockHash:
    def test_hash_of_block_only(self):
        block_text = f"{BLOCK_BEGIN}\nblock body\n{BLOCK_END}"
        content = f"header\n{block_text}\nfooter\n"
        expected = hashlib.sha256(block_text.encode()).hexdigest()
        assert compute_block_hash(content) == expected

    def test_none_without_markers(self):
        assert compute_block_hash("no markers here") is None

    def test_same_block_different_headers(self):
        block = f"{BLOCK_BEGIN}\nsame body\n{BLOCK_END}"
        content_a = f"header A\n{block}\nfooter A\n"
        content_b = f"header B\n{block}\nfooter B\n"
        assert compute_block_hash(content_a) == compute_block_hash(content_b)


# =============================================================================
# _match_historical_render
# =============================================================================


class TestMatchHistoricalRender:
    """Verifies the helper that detects 'stale-clean' files — files whose
    current content matches a historical framework template render. A match
    means the file was framework-produced at some past version and is safe
    to overwrite without --force."""

    def _make_git_framework(self, tmp_path: Path) -> Path:
        fw = tmp_path / "framework"
        fw.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=fw, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=fw, check=True)
        subprocess.run(["git", "config", "user.name", "Test"], cwd=fw, check=True)
        (fw / "templates").mkdir()
        return fw

    def _commit(self, fw: Path, paths: list[str], message: str) -> str:
        subprocess.run(["git", "add", *paths], cwd=fw, check=True)
        subprocess.run(["git", "commit", "-q", "-m", message], cwd=fw, check=True)
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=fw, check=True, capture_output=True, text=True
        )
        return result.stdout.strip()

    def test_matches_current_template_returns_head_sha(self, tmp_path: Path):
        fw = self._make_git_framework(tmp_path)
        (fw / "templates" / "foo.md").write_text("Hello {{PRODUCT_NAME}}\n")
        head_sha = self._commit(fw, ["templates/foo.md"], "add foo")

        target_hash = hashlib.sha256(b"Hello App\n").hexdigest()
        result = _match_historical_render(
            fw, "templates/foo.md", target_hash, {"{{PRODUCT_NAME}}": "App"}
        )
        assert result == head_sha[:12]

    def test_matches_mid_history_returns_old_sha(self, tmp_path: Path):
        fw = self._make_git_framework(tmp_path)
        (fw / "templates" / "foo.md").write_text("v1 {{PRODUCT_NAME}}\n")
        v1_sha = self._commit(fw, ["templates/foo.md"], "v1")
        (fw / "templates" / "foo.md").write_text("v2 {{PRODUCT_NAME}}\n")
        v2_sha = self._commit(fw, ["templates/foo.md"], "v2")
        (fw / "templates" / "foo.md").write_text("v3 {{PRODUCT_NAME}}\n")
        self._commit(fw, ["templates/foo.md"], "v3")

        # Target file content matches v2's render with current subs
        target_hash = hashlib.sha256(b"v2 App\n").hexdigest()
        result = _match_historical_render(
            fw, "templates/foo.md", target_hash, {"{{PRODUCT_NAME}}": "App"}
        )
        assert result == v2_sha[:12]

    def test_no_match_returns_none(self, tmp_path: Path):
        fw = self._make_git_framework(tmp_path)
        (fw / "templates" / "foo.md").write_text("v1 {{PRODUCT_NAME}}\n")
        self._commit(fw, ["templates/foo.md"], "v1")
        (fw / "templates" / "foo.md").write_text("v2 {{PRODUCT_NAME}}\n")
        self._commit(fw, ["templates/foo.md"], "v2")

        # Genuine local edit — never produced by the framework
        target_hash = hashlib.sha256(b"hand-edited content\n").hexdigest()
        result = _match_historical_render(
            fw, "templates/foo.md", target_hash, {"{{PRODUCT_NAME}}": "App"}
        )
        assert result is None

    def test_template_renamed_uses_follow(self, tmp_path: Path):
        fw = self._make_git_framework(tmp_path)
        # Stable shared lines so git's rename-detection similarity threshold
        # recognizes the rename across content changes (single-line files
        # below the threshold won't be detected as renames).
        stable = (
            "shared line one — stable across versions\n"
            "shared line two — stable across versions\n"
            "shared line three — stable across versions\n"
        )
        # Commit 1: file at old path with unique first line
        (fw / "templates" / "old-name.md").write_text(f"v1 legacy {{{{PRODUCT_NAME}}}}\n{stable}")
        legacy_sha = self._commit(fw, ["templates/old-name.md"], "add old-name")
        # Commit 2: rename + change first line so v1 only exists in commit 1
        subprocess.run(["git", "mv", "templates/old-name.md", "templates/new-name.md"], cwd=fw, check=True)
        (fw / "templates" / "new-name.md").write_text(f"v2 mid {{{{PRODUCT_NAME}}}}\n{stable}")
        subprocess.run(["git", "commit", "-q", "-am", "rename + bump"], cwd=fw, check=True)
        # Commit 3: another content update at the new path
        (fw / "templates" / "new-name.md").write_text(f"v3 latest {{{{PRODUCT_NAME}}}}\n{stable}")
        self._commit(fw, ["templates/new-name.md"], "v3")

        # Without --follow, commit 1 is invisible from the new path. With --follow,
        # the helper finds it.
        target_hash = hashlib.sha256(f"v1 legacy App\n{stable}".encode()).hexdigest()
        result = _match_historical_render(
            fw, "templates/new-name.md", target_hash, {"{{PRODUCT_NAME}}": "App"}
        )
        assert result == legacy_sha[:12]

    def test_template_not_in_git_returns_none(self, tmp_path: Path):
        # fw is not a git repo at all
        fw = tmp_path / "no-git"
        fw.mkdir()
        (fw / "templates").mkdir()
        (fw / "templates" / "foo.md").write_text("anything\n")
        result = _match_historical_render(
            fw, "templates/foo.md", "deadbeef" * 8, {}
        )
        assert result is None

    def test_depth_cap_respected(self, tmp_path: Path):
        fw = self._make_git_framework(tmp_path)
        # Create cap+10 commits; oldest commit's content is the target
        oldest_content = "oldest version\n"
        (fw / "templates" / "foo.md").write_text(oldest_content)
        oldest_sha = self._commit(fw, ["templates/foo.md"], "commit 1")
        for i in range(2, _HISTORICAL_RENDER_DEPTH_CAP + 11):
            (fw / "templates" / "foo.md").write_text(f"version {i}\n")
            self._commit(fw, ["templates/foo.md"], f"commit {i}")

        # Oldest is now beyond the cap → should NOT be found
        target_hash = hashlib.sha256(oldest_content.encode()).hexdigest()
        result = _match_historical_render(fw, "templates/foo.md", target_hash, {})
        assert result is None
        # Sanity: a commit within the cap window IS found
        recent_target = hashlib.sha256(
            f"version {_HISTORICAL_RENDER_DEPTH_CAP + 10}\n".encode()
        ).hexdigest()
        result_recent = _match_historical_render(fw, "templates/foo.md", recent_target, {})
        assert result_recent is not None
        # And that result is NOT the oldest sha
        assert result_recent != oldest_sha[:12]

    def test_cache_avoids_redundant_renders(self, tmp_path: Path):
        fw = self._make_git_framework(tmp_path)
        (fw / "templates" / "foo.md").write_text("v1 {{PRODUCT_NAME}}\n")
        self._commit(fw, ["templates/foo.md"], "v1")
        (fw / "templates" / "foo.md").write_text("v2 {{PRODUCT_NAME}}\n")
        self._commit(fw, ["templates/foo.md"], "v2")

        cache: dict = {}
        target_hash = hashlib.sha256(b"v2 App\n").hexdigest()
        result1 = _match_historical_render(
            fw, "templates/foo.md", target_hash, {"{{PRODUCT_NAME}}": "App"}, cache=cache
        )
        cache_after_first = dict(cache)
        assert result1 is not None
        assert len(cache_after_first) >= 1

        # Second call with the same cache: any commits already rendered should
        # not be re-rendered. The cache should not grow if all relevant SHAs
        # were already populated. We verify by asserting the second call
        # returns the same result and doesn't shrink/clear the cache.
        result2 = _match_historical_render(
            fw, "templates/foo.md", target_hash, {"{{PRODUCT_NAME}}": "App"}, cache=cache
        )
        assert result2 == result1
        # Cache contents preserved (no spurious recomputation)
        assert cache == cache_after_first


# =============================================================================
# run_sync — block_template strategy
# =============================================================================


class TestRunSyncBlockTemplate:
    def _setup_framework(self, tmp_path: Path) -> Path:
        """Create a framework with marked CLAUDE.md template."""
        fw = tmp_path / "framework"
        fw.mkdir()
        templates = fw / "templates"
        templates.mkdir()
        (templates / "product-claude.md").write_text(
            f"# CLAUDE.md — {{{{PRODUCT_NAME}}}}\n\n"
            f"{BLOCK_BEGIN}\n\n## What This Is\n\nContent v1\n\n{BLOCK_END}\n"
        )
        (templates / "critic-review.md").write_text("# {{PRODUCT_NAME}} Critic v1")
        (templates / "product-settings.json").write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"matcher": "clear", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" clear"}
                ]}],
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" stop"}
                ]}],
            }
        }, indent=2))
        tools = fw / "tools"
        tools.mkdir()
        (tools / "product-hook").write_text("#!/usr/bin/env python3\n# hook v1")
        return fw

    def _setup_product(self, tmp_path: Path, fw: Path, product_name: str = "TestApp") -> Path:
        """Create a product with block_template manifest for CLAUDE.md."""
        product = tmp_path / "product"
        product.mkdir()
        (product / ".prawduct").mkdir()

        subs = {"{{PRODUCT_NAME}}": product_name}

        # Write CLAUDE.md from template (with markers)
        claude_content = render_template(fw / "templates" / "product-claude.md", subs)
        (product / "CLAUDE.md").write_text(claude_content)

        critic_content = render_template(fw / "templates" / "critic-review.md", subs)
        (product / ".prawduct" / "critic-review.md").write_text(critic_content)

        (product / "tools").mkdir()
        (product / "tools" / "product-hook").write_bytes(
            (fw / "tools" / "product-hook").read_bytes()
        )

        (product / ".claude").mkdir()
        (product / ".claude" / "settings.json").write_text(
            (fw / "templates" / "product-settings.json").read_text()
        )

        # Compute block hash for CLAUDE.md
        block_hash = compute_block_hash(claude_content)

        hashes = {
            "CLAUDE.md": block_hash,
            ".prawduct/critic-review.md": compute_hash(product / ".prawduct" / "critic-review.md"),
            "tools/product-hook": compute_hash(product / "tools" / "product-hook"),
            ".claude/settings.json": None,
        }

        (product / ".gitignore").write_text("\n".join(GITIGNORE_ENTRIES) + "\n")

        manifest = create_manifest(product, fw, product_name, hashes)
        (product / ".prawduct" / "sync-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )

        return product

    def test_propagates_template_update(self, tmp_path: Path):
        """Block update in template propagates to product file."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # Update template block content
        (fw / "templates" / "product-claude.md").write_text(
            f"# CLAUDE.md — {{{{PRODUCT_NAME}}}}\n\n"
            f"{BLOCK_BEGIN}\n\n## What This Is\n\nContent v2\n\n{BLOCK_END}\n"
        )

        result = run_sync(str(product), framework_dir=str(fw))
        assert result["synced"] is True
        assert any("CLAUDE.md" in a for a in result["actions"])

        content = (product / "CLAUDE.md").read_text()
        assert "Content v2" in content
        assert BLOCK_BEGIN in content
        assert BLOCK_END in content

    def test_preserves_user_content_outside_markers(self, tmp_path: Path):
        """User content before/after markers is preserved during sync."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # User adds content after END marker
        claude = (product / "CLAUDE.md").read_text()
        claude += "\n## My Custom Section\n\nUser notes here.\n"
        (product / "CLAUDE.md").write_text(claude)

        # Update template block content
        (fw / "templates" / "product-claude.md").write_text(
            f"# CLAUDE.md — {{{{PRODUCT_NAME}}}}\n\n"
            f"{BLOCK_BEGIN}\n\n## What This Is\n\nContent v2\n\n{BLOCK_END}\n"
        )

        result = run_sync(str(product), framework_dir=str(fw))
        assert result["synced"] is True

        content = (product / "CLAUDE.md").read_text()
        assert "Content v2" in content
        assert "My Custom Section" in content
        assert "User notes here." in content

    def test_autofix_block_already_at_target_refreshes_manifest_silently(self, tmp_path: Path):
        # Parallel to the template-strategy autofix: when the block content matches
        # the current rendered template, sync silently refreshes the manifest hash
        # rather than reporting "local edits" on a file that's already in shape.
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        (fw / "templates" / "product-claude.md").write_text(
            f"# CLAUDE.md — {{{{PRODUCT_NAME}}}}\n\n"
            f"{BLOCK_BEGIN}\n\n## What This Is\n\nContent v2\n\n{BLOCK_END}\n"
        )
        (product / "CLAUDE.md").write_text(
            f"# CLAUDE.md — TestApp\n\n"
            f"{BLOCK_BEGIN}\n\n## What This Is\n\nContent v2\n\n{BLOCK_END}\n"
        )

        result = run_sync(str(product), framework_dir=str(fw))

        assert not any("local edits" in n and "CLAUDE.md" in n for n in result["notes"])
        assert not any("Force-updated" in a for a in result["actions"])
        assert "Content v2" in (product / "CLAUDE.md").read_text()

    def test_overwrites_user_edits_inside_block(self, tmp_path: Path):
        """Marker contract: content inside PRAWDUCT:BEGIN/END is framework-owned.
        User edits inside the block are overwritten on sync — customization belongs
        outside the markers."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # User edits inside the markers (against the contract)
        claude = (product / "CLAUDE.md").read_text()
        claude = claude.replace("Content v1", "My custom content")
        (product / "CLAUDE.md").write_text(claude)

        # Update template
        (fw / "templates" / "product-claude.md").write_text(
            f"# CLAUDE.md — {{{{PRODUCT_NAME}}}}\n\n"
            f"{BLOCK_BEGIN}\n\n## What This Is\n\nContent v2\n\n{BLOCK_END}\n"
        )

        result = run_sync(str(product), framework_dir=str(fw))
        assert any("CLAUDE.md" in a for a in result["actions"])
        assert not any("block has local edits" in n for n in result["notes"])
        new_content = (product / "CLAUDE.md").read_text()
        assert "My custom content" not in new_content
        assert "Content v2" in new_content

    def test_handles_missing_markers_in_product(self, tmp_path: Path):
        """Product file without markers — skip with note."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # Remove markers from product file
        (product / "CLAUDE.md").write_text("# My CLAUDE.md\n\nNo markers here.\n")

        # Update template
        (fw / "templates" / "product-claude.md").write_text(
            f"# CLAUDE.md — {{{{PRODUCT_NAME}}}}\n\n"
            f"{BLOCK_BEGIN}\n\n## What This Is\n\nContent v2\n\n{BLOCK_END}\n"
        )

        result = run_sync(str(product), framework_dir=str(fw))
        assert not any("CLAUDE.md" in a for a in result["actions"])
        assert any("no markers" in n for n in result["notes"])

    def test_creates_missing_file(self, tmp_path: Path):
        """If product file is missing, create from full template."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # Delete the CLAUDE.md
        (product / "CLAUDE.md").unlink()

        # Update template to trigger hash mismatch
        (fw / "templates" / "product-claude.md").write_text(
            f"# CLAUDE.md — {{{{PRODUCT_NAME}}}}\n\n"
            f"{BLOCK_BEGIN}\n\n## What This Is\n\nContent v2\n\n{BLOCK_END}\n"
        )

        result = run_sync(str(product), framework_dir=str(fw))
        assert result["synced"] is True
        assert any("CLAUDE.md" in a for a in result["actions"])

        content = (product / "CLAUDE.md").read_text()
        assert "Content v2" in content
        assert "TestApp" in content

    def test_idempotent(self, tmp_path: Path):
        """Running sync twice with no changes produces no updates."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # First sync with template change
        (fw / "templates" / "product-claude.md").write_text(
            f"# CLAUDE.md — {{{{PRODUCT_NAME}}}}\n\n"
            f"{BLOCK_BEGIN}\n\n## What This Is\n\nContent v2\n\n{BLOCK_END}\n"
        )

        run_sync(str(product), framework_dir=str(fw))

        # Second sync — nothing to do
        result = run_sync(str(product), framework_dir=str(fw))
        assert result["synced"] is False
        assert result["reason"] == "no updates needed"

    def test_restores_drifted_block(self, tmp_path: Path):
        """When template hasn't changed but product block drifted, overwrite it.
        Marker contract: block content is framework-owned regardless of why it drifted."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # Agent modifies the block content (drift) without a template change
        claude = (product / "CLAUDE.md").read_text()
        claude = claude.replace("Content v1", "Content v1\n\nAgent added this line")
        (product / "CLAUDE.md").write_text(claude)

        # Template is unchanged — stored hash matches rendered block hash
        result = run_sync(str(product), framework_dir=str(fw))
        assert result["synced"] is True
        assert any("CLAUDE.md" in a for a in result["actions"])

        # Block should be restored to original template content
        content = (product / "CLAUDE.md").read_text()
        assert "Agent added this line" not in content
        assert "Content v1" in content

        # User content outside markers should be preserved
        assert "# CLAUDE.md — TestApp" in content

    def test_no_restore_when_block_matches(self, tmp_path: Path):
        """When template and product block both match stored hash, no action."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # No changes to template or product — everything in sync
        result = run_sync(str(product), framework_dir=str(fw))
        assert result["synced"] is False
        assert not any("Restored" in a for a in result["actions"])

    def test_template_without_markers_skips(self, tmp_path: Path):
        """Template without markers (bug) — skip with note."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # Replace template with unmarked version
        (fw / "templates" / "product-claude.md").write_text(
            "# CLAUDE.md — {{PRODUCT_NAME}}\n\nNo markers template.\n"
        )

        result = run_sync(str(product), framework_dir=str(fw))
        assert not any("CLAUDE.md" in a for a in result["actions"])
        assert any("no markers" in n for n in result["notes"])


# =============================================================================
# run_sync — place-once files
# =============================================================================


class TestRunSyncPlaceOnce:
    """Tests for place-once file creation during sync."""

    def _setup_framework(self, tmp_path: Path) -> Path:
        fw = tmp_path / "framework"
        fw.mkdir()
        templates = fw / "templates"
        templates.mkdir()
        (templates / "product-claude.md").write_text(
            f"# {{{{PRODUCT_NAME}}}} CLAUDE.md\n\n"
            f"{BLOCK_BEGIN}\nContent v1\n{BLOCK_END}\n"
        )
        (templates / "critic-review.md").write_text("# {{PRODUCT_NAME}} Critic v1")
        (templates / "product-settings.json").write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"matcher": "clear", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" clear"}
                ]}],
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" stop"}
                ]}],
            }
        }, indent=2))
        (templates / "project-preferences.md").write_text(
            "# Project Preferences\n\n## Language & Runtime\n\n- **Language**:\n"
        )
        tools = fw / "tools"
        tools.mkdir()
        (tools / "product-hook").write_text("#!/usr/bin/env python3\n# hook v1")
        return fw

    def _setup_product(self, tmp_path: Path, fw: Path) -> Path:
        product = tmp_path / "product"
        product.mkdir()
        prawduct = product / ".prawduct"
        prawduct.mkdir()
        (prawduct / "artifacts").mkdir()

        subs = {"{{PRODUCT_NAME}}": "TestApp"}
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

        (product / ".gitignore").write_text("\n".join(GITIGNORE_ENTRIES) + "\n")

        hashes = {
            "CLAUDE.md": compute_block_hash(claude_content),
            ".prawduct/critic-review.md": compute_hash(prawduct / "critic-review.md"),
            "tools/product-hook": compute_hash(product / "tools" / "product-hook"),
            ".claude/settings.json": None,
        }
        manifest = create_manifest(product, fw, "TestApp", hashes)
        (prawduct / "sync-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        return product

    def test_creates_missing_preferences(self, tmp_path: Path):
        """Sync places project-preferences.md if missing from existing repo."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        result = run_sync(str(product), framework_dir=str(fw))

        prefs = product / ".prawduct" / "artifacts" / "project-preferences.md"
        assert prefs.is_file()
        assert "Project Preferences" in prefs.read_text()
        assert any("project-preferences" in a for a in result["actions"])

    def test_does_not_overwrite_existing_preferences(self, tmp_path: Path):
        """Sync skips project-preferences.md if it already exists."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        prefs = product / ".prawduct" / "artifacts" / "project-preferences.md"
        prefs.write_text("# Project Preferences\n\n- **Language**: Python\n")

        result = run_sync(str(product), framework_dir=str(fw))

        assert "Python" in prefs.read_text()
        assert not any("project-preferences" in a for a in result["actions"])

    def test_records_template_hash_on_creation(self, tmp_path: Path):
        """Sync records template hash in manifest when creating a place-once file."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        run_sync(str(product), framework_dir=str(fw))

        manifest = json.loads(
            (product / ".prawduct" / "sync-manifest.json").read_text()
        )
        pot = manifest.get("place_once_templates", {})
        prefs_entry = pot.get(".prawduct/artifacts/project-preferences.md")
        assert prefs_entry is not None
        assert "template_hash" in prefs_entry
        assert "template" in prefs_entry
        assert "created_at" in prefs_entry
        assert len(prefs_entry["template_hash"]) == 64  # SHA-256 hex

    def test_bootstraps_hash_for_preexisting_file(self, tmp_path: Path):
        """For products that already have the file, sync bootstraps hash tracking."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # Pre-create the preferences file (simulating a pre-existing product)
        prefs = product / ".prawduct" / "artifacts" / "project-preferences.md"
        prefs.write_text("# My custom preferences\n")

        run_sync(str(product), framework_dir=str(fw))

        manifest = json.loads(
            (product / ".prawduct" / "sync-manifest.json").read_text()
        )
        pot = manifest.get("place_once_templates", {})
        assert ".prawduct/artifacts/project-preferences.md" in pot

    def test_preserves_existing_hash_tracking(self, tmp_path: Path):
        """Sync does not overwrite existing place_once_templates entries."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # Run sync once to populate tracking
        run_sync(str(product), framework_dir=str(fw))
        manifest = json.loads(
            (product / ".prawduct" / "sync-manifest.json").read_text()
        )
        original_hash = manifest["place_once_templates"][
            ".prawduct/artifacts/project-preferences.md"
        ]["template_hash"]

        # Update the template in the framework
        (fw / "templates" / "project-preferences.md").write_text(
            "# Updated Preferences\n\n## New Section\n"
        )

        # Run sync again — hash should NOT be updated (preserves original)
        run_sync(str(product), framework_dir=str(fw))
        manifest = json.loads(
            (product / ".prawduct" / "sync-manifest.json").read_text()
        )
        preserved_hash = manifest["place_once_templates"][
            ".prawduct/artifacts/project-preferences.md"
        ]["template_hash"]
        assert preserved_hash == original_hash

    def test_template_hash_is_deterministic(self, tmp_path: Path):
        """Same template content produces the same hash."""
        fw = self._setup_framework(tmp_path)

        # Create two independent products
        (tmp_path / "a").mkdir()
        p1 = self._setup_product(tmp_path / "a", fw)
        (tmp_path / "b").mkdir()
        p2 = self._setup_product(tmp_path / "b", fw)

        run_sync(str(p1), framework_dir=str(fw))
        run_sync(str(p2), framework_dir=str(fw))

        m1 = json.loads((p1 / ".prawduct" / "sync-manifest.json").read_text())
        m2 = json.loads((p2 / ".prawduct" / "sync-manifest.json").read_text())

        h1 = m1["place_once_templates"][".prawduct/artifacts/project-preferences.md"]["template_hash"]
        h2 = m2["place_once_templates"][".prawduct/artifacts/project-preferences.md"]["template_hash"]
        assert h1 == h2


# =============================================================================
# run_sync — template drift advisories
# =============================================================================


class TestRunSyncTemplateDrift(TestRunSyncPlaceOnce):
    """Tests for template drift detection and advisory generation."""

    def test_no_advisory_when_template_unchanged(self, tmp_path: Path):
        """No advisory when template hasn't changed since tracking was set up."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # First sync: creates file + bootstraps tracking
        run_sync(str(product), framework_dir=str(fw))
        # Second sync: template unchanged, no advisory
        result = run_sync(str(product), framework_dir=str(fw))

        assert result.get("advisories", []) == []

    def test_advisory_when_template_changed(self, tmp_path: Path):
        """Advisory generated when template evolves after tracking was set up."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # First sync: creates file + bootstraps tracking
        run_sync(str(product), framework_dir=str(fw))

        # Update the template in the framework
        (fw / "templates" / "project-preferences.md").write_text(
            "# Updated Preferences\n\n## New PBT Section\n\n- **Testing strategies**: hypothesis\n"
        )

        # Second sync: template changed → advisory
        result = run_sync(str(product), framework_dir=str(fw))

        advisories = result.get("advisories", [])
        assert len(advisories) == 1
        assert advisories[0]["type"] == "template_drift"
        assert "project-preferences.md" in advisories[0]["file"]
        assert "/janitor" in advisories[0]["message"]

    def test_advisory_persists_across_syncs(self, tmp_path: Path):
        """Advisory keeps firing until template hash is updated (by janitor)."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        run_sync(str(product), framework_dir=str(fw))

        # Update template
        (fw / "templates" / "project-preferences.md").write_text("# V2\n")

        # Advisory on second sync
        result1 = run_sync(str(product), framework_dir=str(fw))
        assert len(result1.get("advisories", [])) == 1

        # Advisory persists on third sync (hash not updated)
        result2 = run_sync(str(product), framework_dir=str(fw))
        assert len(result2.get("advisories", [])) == 1

    def test_no_advisory_for_freshly_bootstrapped(self, tmp_path: Path):
        """No advisory for entries just bootstrapped in this sync."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # Pre-create preferences (simulating pre-existing product)
        prefs = product / ".prawduct" / "artifacts" / "project-preferences.md"
        prefs.write_text("# My prefs\n")

        # Now update the template BEFORE first sync
        (fw / "templates" / "project-preferences.md").write_text("# Different\n")

        # First sync: bootstraps with current template hash → no advisory
        # (we can't detect drift from the original because we just started tracking)
        result = run_sync(str(product), framework_dir=str(fw))
        assert result.get("advisories", []) == []


# =============================================================================
# _try_pull_framework
# =============================================================================


class _FakeCompletedProcess:
    """Minimal stand-in for subprocess.CompletedProcess."""

    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _make_mock_subprocess(responses: dict):
    """Build a namespace that replaces ``_mod.subprocess`` for testing.

    ``responses`` maps a git subcommand (e.g. ``"rev-parse"``) to either:
      - a ``_FakeCompletedProcess`` to return, or
      - an exception to raise.
    Unrecognised subcommands return success with empty output.
    """
    import types

    ns = types.SimpleNamespace()
    ns.TimeoutExpired = subprocess.TimeoutExpired

    def fake_run(cmd, *, capture_output=True, text=True, cwd=None, timeout=None):
        # Identify the git subcommand (cmd[1])
        subcmd = cmd[1] if len(cmd) > 1 else ""
        val = responses.get(subcmd)
        if val is None:
            return _FakeCompletedProcess()
        if isinstance(val, Exception):
            raise val
        return val

    ns.run = fake_run
    return ns


class TestTryPullFramework:
    """Unit tests for _try_pull_framework."""

    def test_not_a_git_repo(self, tmp_path: Path, monkeypatch):
        mock = _make_mock_subprocess({
            "rev-parse": _FakeCompletedProcess(returncode=128, stderr="fatal: not a git repo"),
        })
        monkeypatch.setattr(_mod._lib_core, "subprocess", mock)
        assert _try_pull_framework(tmp_path, auto_pull=True) == []

    def test_auto_pull_clean_up_to_date(self, tmp_path: Path, monkeypatch):
        mock = _make_mock_subprocess({
            "rev-parse": _FakeCompletedProcess(),
            "status": _FakeCompletedProcess(stdout=""),
            "pull": _FakeCompletedProcess(stdout="Already up to date.\n"),
        })
        monkeypatch.setattr(_mod._lib_core, "subprocess", mock)
        assert _try_pull_framework(tmp_path, auto_pull=True) == []

    def test_auto_pull_clean_updated(self, tmp_path: Path, monkeypatch):
        mock = _make_mock_subprocess({
            "rev-parse": _FakeCompletedProcess(),
            "status": _FakeCompletedProcess(stdout=""),
            "pull": _FakeCompletedProcess(stdout="Updating abc123..def456\n"),
        })
        monkeypatch.setattr(_mod._lib_core, "subprocess", mock)
        notes = _try_pull_framework(tmp_path, auto_pull=True)
        assert len(notes) == 1
        assert "updated" in notes[0].lower()

    def test_auto_pull_dirty_tree(self, tmp_path: Path, monkeypatch):
        mock = _make_mock_subprocess({
            "rev-parse": _FakeCompletedProcess(),
            "status": _FakeCompletedProcess(stdout=" M dirty-file.py\n"),
        })
        monkeypatch.setattr(_mod._lib_core, "subprocess", mock)
        notes = _try_pull_framework(tmp_path, auto_pull=True)
        assert len(notes) == 1
        assert "uncommitted" in notes[0].lower()

    def test_auto_pull_not_fast_forwardable(self, tmp_path: Path, monkeypatch):
        mock = _make_mock_subprocess({
            "rev-parse": _FakeCompletedProcess(),
            "status": _FakeCompletedProcess(stdout=""),
            "pull": _FakeCompletedProcess(
                returncode=1,
                stderr="fatal: Not possible to fast-forward, aborting.",
            ),
        })
        monkeypatch.setattr(_mod._lib_core, "subprocess", mock)
        notes = _try_pull_framework(tmp_path, auto_pull=True)
        assert len(notes) == 1
        assert "not fast-forwardable" in notes[0].lower()

    def test_auto_pull_general_failure(self, tmp_path: Path, monkeypatch):
        mock = _make_mock_subprocess({
            "rev-parse": _FakeCompletedProcess(),
            "status": _FakeCompletedProcess(stdout=""),
            "pull": _FakeCompletedProcess(returncode=1, stderr="error: something"),
        })
        monkeypatch.setattr(_mod._lib_core, "subprocess", mock)
        notes = _try_pull_framework(tmp_path, auto_pull=True)
        assert len(notes) == 1
        assert "pull failed" in notes[0].lower()

    def test_advisory_behind(self, tmp_path: Path, monkeypatch):
        mock = _make_mock_subprocess({
            "rev-parse": _FakeCompletedProcess(),
            "fetch": _FakeCompletedProcess(),
            "rev-list": _FakeCompletedProcess(stdout="3\n"),
        })
        monkeypatch.setattr(_mod._lib_core, "subprocess", mock)
        notes = _try_pull_framework(tmp_path, auto_pull=False)
        assert len(notes) == 1
        assert "3" in notes[0]
        assert "behind" in notes[0].lower()

    def test_advisory_up_to_date(self, tmp_path: Path, monkeypatch):
        mock = _make_mock_subprocess({
            "rev-parse": _FakeCompletedProcess(),
            "fetch": _FakeCompletedProcess(),
            "rev-list": _FakeCompletedProcess(stdout="0\n"),
        })
        monkeypatch.setattr(_mod._lib_core, "subprocess", mock)
        assert _try_pull_framework(tmp_path, auto_pull=False) == []

    def test_advisory_fetch_fails(self, tmp_path: Path, monkeypatch):
        mock = _make_mock_subprocess({
            "rev-parse": _FakeCompletedProcess(),
            "fetch": _FakeCompletedProcess(returncode=1, stderr="error"),
        })
        monkeypatch.setattr(_mod._lib_core, "subprocess", mock)
        assert _try_pull_framework(tmp_path, auto_pull=False) == []

    def test_git_not_on_path(self, tmp_path: Path, monkeypatch):
        mock = _make_mock_subprocess({
            "rev-parse": FileNotFoundError("git not found"),
        })
        monkeypatch.setattr(_mod._lib_core, "subprocess", mock)
        assert _try_pull_framework(tmp_path, auto_pull=True) == []

    def test_timeout(self, tmp_path: Path, monkeypatch):
        mock = _make_mock_subprocess({
            "rev-parse": subprocess.TimeoutExpired(cmd="git", timeout=30),
        })
        monkeypatch.setattr(_mod._lib_core, "subprocess", mock)
        notes = _try_pull_framework(tmp_path, auto_pull=True)
        assert len(notes) == 1
        assert "timed out" in notes[0].lower()


# =============================================================================
# run_sync — pull integration
# =============================================================================


class TestRunSyncPull:
    """Integration tests for pull behavior within run_sync."""

    def _setup_framework(self, tmp_path: Path) -> Path:
        fw = tmp_path / "framework"
        fw.mkdir()
        templates = fw / "templates"
        templates.mkdir()
        (templates / "product-claude.md").write_text(
            f"# {{{{PRODUCT_NAME}}}} CLAUDE.md\n\n"
            f"{BLOCK_BEGIN}\nContent v1\n{BLOCK_END}\n"
        )
        (templates / "critic-review.md").write_text("# {{PRODUCT_NAME}} Critic v1")
        (templates / "product-settings.json").write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"matcher": "clear", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" clear"}
                ]}],
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" stop"}
                ]}],
            }
        }, indent=2))
        tools = fw / "tools"
        tools.mkdir()
        (tools / "product-hook").write_text("#!/usr/bin/env python3\n# hook v1")
        return fw

    def _setup_product(self, tmp_path: Path, fw: Path, manifest_overrides: dict | None = None) -> Path:
        product = tmp_path / "product"
        product.mkdir()
        (product / ".prawduct").mkdir()

        subs = {"{{PRODUCT_NAME}}": "TestApp"}
        claude_content = render_template(fw / "templates" / "product-claude.md", subs)
        (product / "CLAUDE.md").write_text(claude_content)
        critic_content = render_template(fw / "templates" / "critic-review.md", subs)
        (product / ".prawduct" / "critic-review.md").write_text(critic_content)
        (product / "tools").mkdir()
        (product / "tools" / "product-hook").write_bytes(
            (fw / "tools" / "product-hook").read_bytes()
        )
        (product / ".claude").mkdir()
        (product / ".claude" / "settings.json").write_text(
            (fw / "templates" / "product-settings.json").read_text()
        )

        (product / ".gitignore").write_text("\n".join(GITIGNORE_ENTRIES) + "\n")

        hashes = {
            "CLAUDE.md": compute_block_hash(claude_content),
            ".prawduct/critic-review.md": compute_hash(product / ".prawduct" / "critic-review.md"),
            "tools/product-hook": compute_hash(product / "tools" / "product-hook"),
            ".claude/settings.json": None,
        }
        manifest = create_manifest(product, fw, "TestApp", hashes)
        if manifest_overrides:
            manifest.update(manifest_overrides)
        (product / ".prawduct" / "sync-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )
        return product

    def test_no_pull_skips_entirely(self, tmp_path: Path, monkeypatch):
        """no_pull=True means _try_pull_framework is never called."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        called = []

        original = _mod._try_pull_framework

        def spy(fw_dir, auto_pull):
            called.append(True)
            return original(fw_dir, auto_pull)

        monkeypatch.setattr(_mod._lib_sync_cmd, "_try_pull_framework", spy)
        run_sync(str(product), framework_dir=str(fw), no_pull=True)
        assert called == []

    def test_default_manifest_uses_auto_pull_true(self, tmp_path: Path, monkeypatch):
        """Manifest without auto_pull field defaults to auto_pull=True."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # Remove auto_pull from manifest to simulate old manifests
        manifest_path = product / ".prawduct" / "sync-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        manifest.pop("auto_pull", None)
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

        captured_auto_pull = []

        def fake_pull(fw_dir, auto_pull):
            captured_auto_pull.append(auto_pull)
            return []

        monkeypatch.setattr(_mod._lib_sync_cmd, "_try_pull_framework", fake_pull)
        run_sync(str(product), framework_dir=str(fw))
        assert captured_auto_pull == [True]

    def test_manifest_auto_pull_false_uses_advisory(self, tmp_path: Path, monkeypatch):
        """Manifest with auto_pull=false passes False to _try_pull_framework."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw, manifest_overrides={"auto_pull": False})

        captured_auto_pull = []

        def fake_pull(fw_dir, auto_pull):
            captured_auto_pull.append(auto_pull)
            return []

        monkeypatch.setattr(_mod._lib_sync_cmd, "_try_pull_framework", fake_pull)
        run_sync(str(product), framework_dir=str(fw))
        assert captured_auto_pull == [False]

    def test_pull_notes_appear_in_result(self, tmp_path: Path, monkeypatch):
        """Notes from _try_pull_framework appear in the sync result."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        monkeypatch.setattr(_mod._lib_sync_cmd, "_try_pull_framework", lambda fw_dir, auto_pull: ["Framework updated via git pull"])
        result = run_sync(str(product), framework_dir=str(fw))
        assert "Framework updated via git pull" in result["notes"]

    def test_pull_failure_does_not_block_sync(self, tmp_path: Path, monkeypatch):
        """Even when pull reports a problem, sync proceeds normally."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        monkeypatch.setattr(
            _mod._lib_sync_cmd, "_try_pull_framework",
            lambda fw_dir, auto_pull: ["Framework pull failed — run git pull manually"],
        )

        # Update template to trigger a real sync action
        (fw / "templates" / "product-claude.md").write_text(
            f"# {{{{PRODUCT_NAME}}}} CLAUDE.md\n\n"
            f"{BLOCK_BEGIN}\nContent v2\n{BLOCK_END}\n"
        )

        result = run_sync(str(product), framework_dir=str(fw))
        assert result["synced"] is True
        assert any("CLAUDE.md" in a for a in result["actions"])
        assert "Framework pull failed — run git pull manually" in result["notes"]


# =============================================================================
# migrate_backlog
# =============================================================================


class TestMigrateBacklog:

    def test_no_project_state(self, tmp_path: Path):
        """Returns empty when project-state.yaml is missing."""
        (tmp_path / ".prawduct").mkdir()
        assert migrate_backlog(tmp_path) == []

    def test_no_matching_sections(self, tmp_path: Path):
        """Returns empty when no backlog-related sections exist."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n\nbuild_plan:\n  chunks: []\n"
        )
        assert migrate_backlog(tmp_path) == []

    def test_remaining_work_with_pending_items(self, tmp_path: Path):
        """Parses remaining_work, converts non-completed items to backlog.md."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "build_plan:\n"
            "  strategy: test\n"
            "  remaining_work:\n"
            '    - item: "Add caching"\n'
            '      description: "Performance optimization for API"\n'
            "      phase: pending\n"
            '    - item: "Done thing"\n'
            '      description: "Already finished"\n'
            "      phase: completed\n"
            '    - item: "Fix logging"\n'
            '      description: "Structured logging needed"\n'
            "      phase: blocked\n"
            "  chunks: []\n"
        )

        actions = migrate_backlog(tmp_path)
        assert len(actions) == 2
        assert any("2 backlog" in a for a in actions)

        backlog = (prawduct / "backlog.md").read_text()
        assert "**Add caching**" in backlog
        assert "Performance optimization" in backlog
        assert "**Fix logging**" in backlog
        assert "(migrated)" in backlog
        # Completed items should not appear
        assert "Done thing" not in backlog

    def test_remaining_work_all_completed(self, tmp_path: Path):
        """All completed items — removes section, no items in backlog.md."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "build_plan:\n"
            "  strategy: test\n"
            "  remaining_work:\n"
            '    - item: "Done A"\n'
            "      phase: completed\n"
            '    - item: "Done B"\n'
            "      phase: completed\n"
            "  chunks: []\n"
        )

        actions = migrate_backlog(tmp_path)
        # No pending items, so nothing to write
        assert actions == []

    def test_remaining_work_preserves_build_plan(self, tmp_path: Path):
        """After migration, build_plan structure is kept (strategy, chunks)."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "build_plan:\n"
            "  strategy: test-strategy\n"
            "  remaining_work:\n"
            '    - item: "Pending"\n'
            "      phase: pending\n"
            "  chunks: []\n"
            "  current_chunk: null\n"
        )

        migrate_backlog(tmp_path)

        state = (prawduct / "project-state.yaml").read_text()
        assert "strategy: test-strategy" in state
        assert "chunks: []" in state
        assert "current_chunk: null" in state
        # remaining_work replaced with pointer
        assert "remaining_work:" not in state or "migrated to" in state

    def test_future_work_raw_yaml(self, tmp_path: Path):
        """Top-level future_work extracted as raw YAML with cleanup marker."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n\n"
            "future_work:\n"
            "  - Add dark mode\n"
            "  - Support i18n\n\n"
            "build_state:\n  source_root: src\n"
        )

        actions = migrate_backlog(tmp_path)
        assert len(actions) == 2

        backlog = (prawduct / "backlog.md").read_text()
        assert "CLEANUP" in backlog
        assert "future_work" in backlog
        assert "```yaml" in backlog
        assert "Add dark mode" in backlog

        state = (prawduct / "project-state.yaml").read_text()
        assert "future_work:" not in state or "migrated to" in state
        # Other sections preserved
        assert "product_identity:" in state
        assert "build_state:" in state

    def test_multiple_sections(self, tmp_path: Path):
        """Both remaining_work and future_work migrated together."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "build_plan:\n"
            "  remaining_work:\n"
            '    - item: "Pending task"\n'
            "      phase: pending\n"
            "  chunks: []\n\n"
            "future_work:\n"
            "  - Another idea\n\n"
            "build_state:\n  source_root: src\n"
        )

        actions = migrate_backlog(tmp_path)
        backlog = (prawduct / "backlog.md").read_text()
        assert "**Pending task**" in backlog
        assert "Another idea" in backlog

    def test_appends_to_existing_backlog(self, tmp_path: Path):
        """Migrated content appended to existing backlog.md."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "backlog.md").write_text(
            "# Backlog\n\n- **Existing item** — already here (builder)\n"
        )
        (prawduct / "project-state.yaml").write_text(
            "future_work:\n  - New idea\n\nbuild_state:\n  source_root: src\n"
        )

        migrate_backlog(tmp_path)

        backlog = (prawduct / "backlog.md").read_text()
        assert "Existing item" in backlog
        assert "New idea" in backlog
        assert "Migrated from project-state.yaml" in backlog

    def test_idempotent(self, tmp_path: Path):
        """Second run produces no changes."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "future_work:\n  - Some idea\n\nbuild_state:\n  source_root: src\n"
        )

        actions1 = migrate_backlog(tmp_path)
        assert len(actions1) > 0

        actions2 = migrate_backlog(tmp_path)
        assert actions2 == []

    def test_pointer_comment_in_yaml(self, tmp_path: Path):
        """Pointer comment replaces migrated section in project-state.yaml."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n\n"
            "future_work:\n  - Idea A\n  - Idea B\n\n"
            "build_state:\n  source_root: src\n"
        )

        migrate_backlog(tmp_path)

        state = (prawduct / "project-state.yaml").read_text()
        assert "migrated to .prawduct/backlog.md" in state


# =============================================================================
# Framework commit recording + advisory enrichment (for the briefing's
# structured Framework Freshness block).
# =============================================================================


def _git_init_with_initial_commit(fw: Path) -> str:
    """Init fw as a git repo, commit everything, return short HEAD SHA."""
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=str(fw), check=True)
    subprocess.run(["git", "-C", str(fw), "config", "user.email", "test@test"], check=True)
    subprocess.run(["git", "-C", str(fw), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(fw), "add", "."], check=True)
    subprocess.run(
        ["git", "-C", str(fw), "commit", "-q", "-m", "initial templates"],
        check=True,
    )
    result = subprocess.run(
        ["git", "-C", str(fw), "rev-parse", "--short", "HEAD"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


class TestSyncRecordsFrameworkCommit(TestRunSyncPlaceOnce):
    """sync writes the framework HEAD short SHA into the manifest at sync
    time so freshness checks can later compute commits-behind precisely."""

    def test_framework_commit_written_when_fw_is_git(self, tmp_path: Path):
        fw = self._setup_framework(tmp_path)
        sha = _git_init_with_initial_commit(fw)
        product = self._setup_product(tmp_path, fw)

        # Force a sync action by changing a tracked template
        (fw / "templates" / "critic-review.md").write_text("# {{PRODUCT_NAME}} Critic v2")
        run_sync(str(product), framework_dir=str(fw))

        manifest = json.loads((product / ".prawduct" / "sync-manifest.json").read_text())
        assert manifest.get("framework_commit") == sha

    def test_framework_commit_omitted_when_fw_not_git(self, tmp_path: Path):
        fw = self._setup_framework(tmp_path)
        # Deliberately NOT git-initialized
        product = self._setup_product(tmp_path, fw)

        (fw / "templates" / "critic-review.md").write_text("# {{PRODUCT_NAME}} Critic v2")
        run_sync(str(product), framework_dir=str(fw))

        manifest = json.loads((product / ".prawduct" / "sync-manifest.json").read_text())
        assert not manifest.get("framework_commit")


class TestAdvisoryEnrichment(TestRunSyncPlaceOnce):
    """Template-drift advisories include the commit / date / subject of the
    most recent change to the template, so the briefing can show *what*
    drifted, not just *that* something drifted."""

    def test_advisory_includes_last_change_when_fw_is_git(self, tmp_path: Path):
        fw = self._setup_framework(tmp_path)
        _git_init_with_initial_commit(fw)
        product = self._setup_product(tmp_path, fw)

        # First sync bootstraps drift tracking with the current template hash
        run_sync(str(product), framework_dir=str(fw))

        # Modify and commit the template — drift advisory should fire on next sync
        (fw / "templates" / "project-preferences.md").write_text(
            "# Updated Preferences\n\n## New Section\n"
        )
        subprocess.run(["git", "-C", str(fw), "add", "."], check=True)
        subprocess.run(
            ["git", "-C", str(fw), "commit", "-q", "-m", "add new section to prefs"],
            check=True,
        )

        result = run_sync(str(product), framework_dir=str(fw))
        advisories = result.get("advisories", [])
        assert len(advisories) == 1
        adv = advisories[0]
        # Existing fields still present
        assert adv["type"] == "template_drift"
        assert "/janitor" in adv["message"]
        # New enrichment fields populated when fw is git
        assert adv["last_changed_commit"]  # short SHA
        assert adv["last_changed_subject"] == "add new section to prefs"
        assert adv["last_changed_date"]  # YYYY-MM-DD

    def test_advisory_has_empty_change_fields_when_fw_not_git(self, tmp_path: Path):
        fw = self._setup_framework(tmp_path)
        # NOT git-initialized
        product = self._setup_product(tmp_path, fw)
        run_sync(str(product), framework_dir=str(fw))

        (fw / "templates" / "project-preferences.md").write_text("# v2\n")
        result = run_sync(str(product), framework_dir=str(fw))

        advisories = result.get("advisories", [])
        assert len(advisories) == 1
        # When fw isn't git, helper returns None and fields are empty strings
        assert advisories[0]["last_changed_commit"] == ""
        assert advisories[0]["last_changed_subject"] == ""


# =============================================================================
# v1.4 derived-views auto-enable (one-shot migration during sync).
#
# Sync silently flips ``views_enabled`` to ``true`` and lands a ``scope_rollups:
# {}`` placeholder so existing v1.3.x repos pick up the v1.4 derived-views
# feature without an explicit opt-in. Tracked via manifest one-shot flag.
# =============================================================================


class TestEnableV1_4Views:

    def test_no_project_state_no_op(self, tmp_path: Path):
        """Missing .prawduct/project-state.yaml — returns empty, no flag set."""
        manifest: dict = {}
        assert enable_v1_4_views(tmp_path, manifest) == []
        assert "v1_4_views_enabled" not in manifest

    def test_already_migrated_no_op(self, tmp_path: Path):
        """Manifest flag set — short-circuits without reading the file."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        # Write a file that WOULD trigger changes if the function ran
        (prawduct / "project-state.yaml").write_text("views_enabled: false\n")
        manifest: dict = {"v1_4_views_enabled": True}

        actions = enable_v1_4_views(tmp_path, manifest)

        assert actions == []
        # File unchanged
        assert (prawduct / "project-state.yaml").read_text() == "views_enabled: false\n"

    def test_pre_chunk_06_repo_adds_both_keys(self, tmp_path: Path):
        """Legacy v1.3.x bootstrap: neither key present → both appended, flag set."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n\nbuild_state:\n  source_root: src\n"
        )
        manifest: dict = {}

        actions = enable_v1_4_views(tmp_path, manifest)

        assert any("Added scope_rollups" in a for a in actions)
        assert any("Added views_enabled: true" in a for a in actions)
        assert manifest["v1_4_views_enabled"] is True

        state = (prawduct / "project-state.yaml").read_text()
        assert "scope_rollups: {}" in state
        assert "views_enabled: true" in state
        # Pre-existing content preserved
        assert "product_identity:" in state
        assert "name: TestApp" in state
        assert "build_state:" in state

    def test_post_chunk_06_repo_flips_false_to_true(self, tmp_path: Path):
        """Post-Chunk-06 template default: ``views_enabled: false`` and
        ``scope_rollups: {}`` present → flag flips, scope_rollups untouched."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        original = (
            "product_identity:\n  name: TestApp\n\n"
            "views_enabled: false\n\n"
            "scope_rollups: {}\n"
        )
        (prawduct / "project-state.yaml").write_text(original)
        manifest: dict = {}

        actions = enable_v1_4_views(tmp_path, manifest)

        assert any("Flipped views_enabled" in a for a in actions)
        # No scope_rollups action — it was already present
        assert not any("Added scope_rollups" in a for a in actions)
        assert manifest["v1_4_views_enabled"] is True

        state = (prawduct / "project-state.yaml").read_text()
        assert "views_enabled: true" in state
        assert "views_enabled: false" not in state
        # scope_rollups: {} preserved verbatim
        assert "scope_rollups: {}" in state

    def test_already_on_no_file_changes(self, tmp_path: Path):
        """Both keys present and views_enabled already true → no file edits,
        but the one-shot flag is still recorded so subsequent syncs skip."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        original = "views_enabled: true\n\nscope_rollups: {}\n"
        (prawduct / "project-state.yaml").write_text(original)
        manifest: dict = {}

        actions = enable_v1_4_views(tmp_path, manifest)

        assert actions == []
        assert manifest["v1_4_views_enabled"] is True
        # File byte-identical
        assert (prawduct / "project-state.yaml").read_text() == original

    def test_idempotent_second_run(self, tmp_path: Path):
        """After a successful run sets the flag, second invocation is a no-op
        even with mutating content."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text("views_enabled: false\n")
        manifest: dict = {}

        actions1 = enable_v1_4_views(tmp_path, manifest)
        assert actions1  # First run does work
        assert manifest["v1_4_views_enabled"] is True

        # User then opts back out manually:
        (prawduct / "project-state.yaml").write_text("views_enabled: false\n")

        # Second run respects the user's explicit choice — flag is still set,
        # so no flip back to true.
        actions2 = enable_v1_4_views(tmp_path, manifest)
        assert actions2 == []
        assert (prawduct / "project-state.yaml").read_text() == "views_enabled: false\n"

    def test_only_scope_missing_adds_just_scope(self, tmp_path: Path):
        """``views_enabled: true`` present but no ``scope_rollups:`` → adds
        only the placeholder, no flip needed."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: A\n\nviews_enabled: true\n"
        )
        manifest: dict = {}

        actions = enable_v1_4_views(tmp_path, manifest)

        assert any("Added scope_rollups" in a for a in actions)
        assert not any("Flipped views_enabled" in a for a in actions)
        assert not any("Added views_enabled" in a for a in actions)
        state = (prawduct / "project-state.yaml").read_text()
        assert "scope_rollups: {}" in state

    def test_commented_views_key_does_not_count(self, tmp_path: Path):
        """A commented-out ``# views_enabled: ...`` doesn't satisfy detection —
        the function still appends the real top-level key."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "# old: views_enabled: false (commented)\nproduct_identity:\n  name: A\n"
        )
        manifest: dict = {}

        actions = enable_v1_4_views(tmp_path, manifest)

        assert any("Added views_enabled: true" in a for a in actions)
        state = (prawduct / "project-state.yaml").read_text()
        # Both the comment and the real top-level key are present
        assert "# old: views_enabled: false (commented)" in state
        assert "\nviews_enabled: true" in state

    def test_nested_views_key_not_counted_as_top_level(self, tmp_path: Path):
        """A nested ``views_enabled: false`` (indented under another key) is
        not the top-level field. ``has_views_key`` doesn't match it (the
        substring check looks for ``\\nviews_enabled:`` with no leading space),
        so the function appends a real top-level key. The nested line is left
        verbatim."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        original = "nested:\n  views_enabled: false\n"
        (prawduct / "project-state.yaml").write_text(original)
        manifest: dict = {}

        actions = enable_v1_4_views(tmp_path, manifest)

        assert any("Added views_enabled: true" in a for a in actions)
        assert not any("Flipped views_enabled" in a for a in actions)

        state = (prawduct / "project-state.yaml").read_text()
        # Nested line preserved unchanged
        assert "  views_enabled: false" in state
        # New top-level key appended
        assert "\nviews_enabled: true" in state

    def test_run_sync_integrates_enable_v1_4_views(self, tmp_path: Path):
        """End-to-end: run_sync on a legacy product repo (no scope_rollups, no
        views_enabled) lands both keys, sets manifest flag, and persists it."""
        fw = tmp_path / "framework"
        fw.mkdir()
        (fw / "templates").mkdir()
        # Minimal templates so run_sync doesn't trip on missing files
        (fw / "templates" / "critic-review.md").write_text("# {{PRODUCT_NAME}} Critic\n")
        (fw / "templates" / "project-preferences.md").write_text("# Preferences\n")
        (fw / "templates" / "pr-review.md").write_text("# {{PRODUCT_NAME}} PR Review\n")
        (fw / "templates" / "boundary-patterns.md").write_text("# Boundaries\n")
        (fw / "tools").mkdir()
        (fw / "tools" / "product-hook").write_text("#!/usr/bin/env python3\n")

        product = tmp_path / "product"
        prawduct = product / ".prawduct"
        prawduct.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: LegacyApp\n"
        )
        # Pre-existing v5 manifest without v1_4_views_enabled flag
        manifest = {
            "framework_version": "1.3.15",
            "framework_path": str(fw),
            "format_version": 2,
            "product_name": "LegacyApp",
            "files": {},
            "auto_pull": False,
        }
        (prawduct / "sync-manifest.json").write_text(json.dumps(manifest))

        run_sync(str(product), framework_dir=str(fw), no_pull=True)

        state = (prawduct / "project-state.yaml").read_text()
        assert "views_enabled: true" in state
        assert "scope_rollups: {}" in state

        post = json.loads((prawduct / "sync-manifest.json").read_text())
        assert post.get("v1_4_views_enabled") is True

        # Second sync: flag set, no re-enable actions related to v1.4 views
        result2 = run_sync(str(product), framework_dir=str(fw), no_pull=True)
        for a in result2.get("actions", []):
            assert "views_enabled" not in a
            assert "scope_rollups" not in a


# =============================================================================
# v1.4 F4c — coverage-required opt-in migration (Chunk 10).
#
# Unlike v1.4 views, coverage enforcement is intentionally NOT auto-enabled on
# sync — turning it on commits the project to BLOCKING Critic findings on
# missing changes_referenced. The helper is invoked only via the new
# `prawduct-setup migrate --enable-coverage` subcommand.
# =============================================================================


class TestEnableV1_4Coverage:

    def test_no_project_state_no_op(self, tmp_path: Path):
        """Missing .prawduct/project-state.yaml — returns empty actions/notes,
        no manifest flag set. Mirrors enable_v1_4_views' fail-quiet contract
        for repos that aren't fully scaffolded."""
        manifest: dict = {}
        actions, notes = enable_v1_4_coverage(tmp_path, manifest)
        assert actions == []
        assert notes == []
        assert "v1_4_coverage_enabled" not in manifest

    def test_pre_v1_4_repo_appends_block(self, tmp_path: Path):
        """Legacy v1.3.x bootstrap (no coverage_required key) → block
        appended at end, flag set, surfaces next-PR consequence + missing-
        evidence note (no evidence file exists in this fresh fixture)."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(
            "product_identity:\n  name: TestApp\n\nbuild_state:\n  source_root: src\n"
        )
        manifest: dict = {}

        actions, notes = enable_v1_4_coverage(tmp_path, manifest)

        assert any("Added coverage_required: true" in a for a in actions)
        assert manifest["v1_4_coverage_enabled"] is True

        state = (prawduct / "project-state.yaml").read_text()
        assert "coverage_required: true" in state
        # Pre-existing content preserved (additive append, not rewrite)
        assert "product_identity:" in state
        assert "name: TestApp" in state

        # Notes surface both the missing-evidence path and the next-PR
        # consequence so the user can't enable enforcement and then be
        # surprised at the first BLOCKING finding.
        assert any("No .prawduct/.test-evidence.json" in n for n in notes)
        assert any("BLOCK on changed files" in n for n in notes)

    def test_flips_false_to_true(self, tmp_path: Path):
        """Explicit `coverage_required: false` → flips to true; the YAML
        rewrite is targeted (one line replaced)."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        original = (
            "product_identity:\n  name: TestApp\n\n"
            "coverage_required: false\n"
        )
        (prawduct / "project-state.yaml").write_text(original)
        manifest: dict = {}

        actions, _ = enable_v1_4_coverage(tmp_path, manifest)

        assert any("Flipped coverage_required: false → true" in a for a in actions)
        assert manifest["v1_4_coverage_enabled"] is True

        state = (prawduct / "project-state.yaml").read_text()
        assert "coverage_required: true" in state
        assert "coverage_required: false" not in state
        # Unrelated content untouched
        assert "product_identity:" in state
        assert "name: TestApp" in state

    def test_already_on_no_file_changes(self, tmp_path: Path):
        """Key already true → no rewrite, no actions, manifest flag set,
        notes mention 'already true'. The flag is still recorded so a later
        accidental re-run short-circuits."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        original = "coverage_required: true\n"
        (prawduct / "project-state.yaml").write_text(original)
        manifest: dict = {}

        actions, notes = enable_v1_4_coverage(tmp_path, manifest)

        assert actions == []
        assert manifest["v1_4_coverage_enabled"] is True
        # File byte-identical
        assert (prawduct / "project-state.yaml").read_text() == original
        assert any("already true" in n for n in notes)

    def test_one_shot_manifest_short_circuits(self, tmp_path: Path):
        """Manifest flag set → function returns empty without reading the
        YAML. Mirrors enable_v1_4_views' one-shot tracking so a user who
        re-edits coverage_required back to false isn't fought."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text("coverage_required: false\n")
        manifest: dict = {"v1_4_coverage_enabled": True}

        actions, notes = enable_v1_4_coverage(tmp_path, manifest)

        assert actions == []
        assert notes == []
        # File unchanged — the one-shot tracking didn't even read it
        assert (prawduct / "project-state.yaml").read_text() == (
            "coverage_required: false\n"
        )

    def test_force_overrides_one_shot(self, tmp_path: Path):
        """`force=True` bypasses the one-shot tracking. The intended use is
        re-surfacing evidence-shape NOTEs after wiring up a verifier — the
        YAML may already be on, but the user wants to re-check the evidence
        situation."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text("coverage_required: true\n")
        # Legacy evidence to trigger the deprecation note
        (prawduct / ".test-evidence.json").write_text(
            '{"timestamp":"2026-05-19T00:00:00Z","passed":1,"failed":0,'
            '"skipped":0,"duration_seconds":1.0,"command":"pytest"}'
        )
        manifest: dict = {"v1_4_coverage_enabled": True}

        actions, notes = enable_v1_4_coverage(tmp_path, manifest, force=True)

        # No YAML actions (already on), but the legacy-evidence NOTE fires.
        assert actions == []
        assert any("Legacy evidence shape detected" in n for n in notes)
        assert any("v1.5 will drop" in n for n in notes)

    def test_legacy_evidence_surfaces_deprecation_note(self, tmp_path: Path):
        """Evidence file exists but has no `verifier` field → v1.5-removal
        warning. The wording is load-bearing for the chunk's deprecation
        signaling."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text("coverage_required: false\n")
        (prawduct / ".test-evidence.json").write_text(
            '{"timestamp":"2026-05-19T00:00:00Z","passed":1,"failed":0,'
            '"skipped":0,"duration_seconds":1.0,"command":"pytest"}'
        )
        manifest: dict = {}

        actions, notes = enable_v1_4_coverage(tmp_path, manifest)

        assert any("Flipped coverage_required" in a for a in actions)
        assert any("Legacy evidence shape detected" in n for n in notes)
        assert any("test-reference-verify" in n for n in notes)

    def test_modern_evidence_emits_no_deprecation(self, tmp_path: Path):
        """F4a-shape evidence (has `verifier`) suppresses the legacy NOTE —
        only the next-PR consequence is surfaced. Otherwise the migration
        would cry wolf at every freshly-onboarded product that already
        emits the new schema."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text("coverage_required: false\n")
        (prawduct / ".test-evidence.json").write_text(
            '{"timestamp":"2026-05-19T00:00:00Z","passed":1,"failed":0,'
            '"skipped":0,"duration_seconds":1.0,"command":"pytest",'
            '"verifier":"test-reference-verify (floor: symbol-grep)",'
            '"coverage_level":"referenced","tests_executed":[],'
            '"changes_referenced":[]}'
        )
        manifest: dict = {}

        _, notes = enable_v1_4_coverage(tmp_path, manifest)

        assert not any("Legacy evidence shape" in n for n in notes)
        assert any("BLOCK on changed files" in n for n in notes)

    def test_unparseable_evidence_surfaces_diagnostic(self, tmp_path: Path):
        """Bad JSON in evidence → diagnostic NOTE, not a crash. Mirrors the
        verify-coverage tolerance — a broken evidence file shouldn't make
        the migration unreachable."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text("coverage_required: false\n")
        (prawduct / ".test-evidence.json").write_text("{not valid json")
        manifest: dict = {}

        _, notes = enable_v1_4_coverage(tmp_path, manifest)

        assert any("Could not parse" in n for n in notes)

    def test_flip_preserves_inline_comment(self, tmp_path: Path):
        """`coverage_required: false  # opt-in deferred` → flips to true,
        comment preserved. Detector strips comments via `split('#', 1)`;
        the mutator must match the same shape or a silent no-op results
        (Critic Chunk 10 NOTE). Catches asymmetry regression."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        original = "coverage_required: false  # opt-in deferred to next sprint\n"
        (prawduct / "project-state.yaml").write_text(original)
        manifest: dict = {}

        actions, _ = enable_v1_4_coverage(tmp_path, manifest)

        assert any("Flipped coverage_required" in a for a in actions)
        state = (prawduct / "project-state.yaml").read_text()
        # Value flipped, comment preserved verbatim
        assert "coverage_required: true" in state
        assert "# opt-in deferred to next sprint" in state
        # The pre-flip form is gone
        assert "coverage_required: false" not in state

    def test_indented_key_does_not_count_as_top_level(self, tmp_path: Path):
        """Nested `coverage_required: true` (indented under another section)
        is NOT detected as the top-level setting. The function appends a real
        top-level key; the nested line is left verbatim. Mirrors the column-0
        discipline shared with `is_views_enabled` and `verify-coverage`."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        original = "nested:\n  coverage_required: true\n"
        (prawduct / "project-state.yaml").write_text(original)
        manifest: dict = {}

        actions, _ = enable_v1_4_coverage(tmp_path, manifest)

        assert any("Added coverage_required: true" in a for a in actions)
        state = (prawduct / "project-state.yaml").read_text()
        # Nested line preserved unchanged
        assert "  coverage_required: true" in state
        # New top-level key appended
        assert "\ncoverage_required: true" in state


# =============================================================================
# `prawduct-setup migrate --enable-coverage` subcommand runner.
# =============================================================================


class TestRunMigrateCoverage:

    def _scaffold(self, tmp_path: Path, yaml: str) -> Path:
        """Create a minimal product layout: .prawduct/ with project-state.yaml
        and a sync-manifest.json. Returns the product root."""
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(yaml)
        (prawduct / "sync-manifest.json").write_text(
            json.dumps({"version": "1.3.17", "files": {}})
        )
        return tmp_path

    def test_no_prawduct_returns_error(self, tmp_path: Path):
        """Refuse to migrate a non-product directory."""
        result = run_migrate_coverage(str(tmp_path))
        assert "error" in result
        assert "no .prawduct/ directory" in result["error"]

    def test_no_manifest_returns_actionable_error(self, tmp_path: Path):
        """Half-scaffolded repo (.prawduct/ exists but no manifest) → error
        names what to run next, not just 'not found'."""
        (tmp_path / ".prawduct").mkdir()
        (tmp_path / ".prawduct" / "project-state.yaml").write_text("")
        result = run_migrate_coverage(str(tmp_path))
        assert "error" in result
        assert "prawduct-setup setup" in result["error"]

    def test_persists_manifest_flag(self, tmp_path: Path):
        """After a successful run, sync-manifest.json on disk has
        v1_4_coverage_enabled set."""
        product = self._scaffold(tmp_path, "coverage_required: false\n")
        result = run_migrate_coverage(str(product))
        assert "error" not in result
        assert result["enabled"] is True

        manifest = json.loads(
            (product / ".prawduct" / "sync-manifest.json").read_text()
        )
        assert manifest.get("v1_4_coverage_enabled") is True

    def test_reports_enabled_state_from_disk(self, tmp_path: Path):
        """`enabled` field in result reflects the on-disk YAML, not the
        manifest flag — a user could re-edit between runs, and the runner
        must report ground truth."""
        product = self._scaffold(tmp_path, "coverage_required: false\n")
        run_migrate_coverage(str(product))

        # User manually reverts
        (product / ".prawduct" / "project-state.yaml").write_text(
            "coverage_required: false\n"
        )

        # Re-run without --force: one-shot kicks in, no flip — but the
        # `enabled` report reflects what's actually in the YAML now.
        result = run_migrate_coverage(str(product))
        assert result["enabled"] is False
        assert result["actions"] == []

    def test_force_flag_bypasses_one_shot(self, tmp_path: Path):
        """--force re-runs even after manifest one-shot is set, so users can
        re-surface evidence-shape NOTEs after wiring up a verifier."""
        product = self._scaffold(tmp_path, "coverage_required: true\n")
        (product / ".prawduct" / ".test-evidence.json").write_text(
            '{"timestamp":"2026-05-19T00:00:00Z","passed":1,"failed":0,'
            '"skipped":0,"duration_seconds":1.0,"command":"pytest"}'
        )

        # First run: sets the flag.
        run_migrate_coverage(str(product))
        # Second run: without --force, manifest one-shot short-circuits.
        no_force = run_migrate_coverage(str(product))
        assert no_force["notes"] == []
        # Third run: with --force, notes re-surface.
        forced = run_migrate_coverage(str(product), force=True)
        assert any("Legacy evidence shape" in n for n in forced["notes"])

    def test_result_shape_is_stable(self, tmp_path: Path):
        """The result dict must always carry product_dir, enabled, force,
        actions, notes — JSON-mode callers depend on the keys being
        present regardless of branch."""
        product = self._scaffold(tmp_path, "coverage_required: false\n")
        result = run_migrate_coverage(str(product))
        assert set(result.keys()) >= {
            "product_dir",
            "enabled",
            "force",
            "actions",
            "notes",
        }


# =============================================================================
# F5b — settings.json layout migration (manifest flag + legacy_cleanup pass).
# =============================================================================


def _minimal_template(tmp_path: Path) -> Path:
    """v1.4 canonical settings.json template. Mirrors templates/product-settings.json:
    two single-line dispatches to product-hook + a banner."""
    tpl = tmp_path / "product-settings.json"
    tpl.write_text(json.dumps({
        "hooks": {
            "SessionStart": [{"matcher": "startup|clear|resume", "hooks": [
                {"type": "command",
                 "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" clear"}
            ]}],
            "Stop": [{"matcher": "", "hooks": [
                {"type": "command",
                 "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" stop"}
            ]}],
        },
        "companyAnnouncements": ["{{PRODUCT_NAME}} — Built with Prawduct"],
    }, indent=2))
    return tpl


class TestEnableV1_4SettingsLayout:

    def test_no_settings_file_no_op(self, tmp_path: Path):
        """No .claude/settings.json — function exits cleanly without setting the
        manifest flag (the flag means 'I migrated', not 'I tried and there was
        nothing'). Mirrors enable_v1_4_views' fail-quiet contract for repos that
        aren't fully scaffolded."""
        tpl = _minimal_template(tmp_path)
        manifest: dict = {}

        actions, notes = enable_v1_4_settings_layout(
            tmp_path, tpl, {"{{PRODUCT_NAME}}": "X"}, manifest
        )

        assert actions == []
        assert notes == []
        assert "v1_4_settings_migrated" not in manifest

    def test_already_minimal_sets_flag_only(self, tmp_path: Path):
        """Product already on canonical layout (modern hook dispatch, no v1
        markers) → no file mutation, but manifest flag is set so this product
        counts as migrated. The user has explicitly opted in even though
        nothing needed changing."""
        settings = tmp_path / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"matcher": "startup|clear|resume", "hooks": [
                    {"type": "command",
                     "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" clear"}
                ]}],
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command",
                     "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" stop"}
                ]}],
            },
            "companyAnnouncements": ["MyApp — Built with Prawduct"],
        }, indent=2))
        tpl = _minimal_template(tmp_path)
        manifest: dict = {}

        actions, notes = enable_v1_4_settings_layout(
            tmp_path, tpl, {"{{PRODUCT_NAME}}": "MyApp"}, manifest
        )

        assert actions == []
        assert manifest["v1_4_settings_migrated"] is True
        # Surface to the user that this is a no-op so they don't suspect
        # the migration silently failed.
        assert any("already on the canonical" in n.lower() for n in notes)

    def test_strips_v1_hook_markers(self, tmp_path: Path):
        """Legacy v1 settings.json with framework-path / governance-hook
        markers → stripped, replaced with current dispatch, manifest flag set,
        action reported."""
        settings = tmp_path / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"matcher": "startup", "hooks": [
                    {"type": "command",
                     "command": "bash $CLAUDE_PROJECT_DIR/tools/governance-hook clear"}
                ]}],
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command",
                     "command": "bash $CLAUDE_PROJECT_DIR/tools/governance-hook stop"}
                ]}],
            },
        }, indent=2))
        tpl = _minimal_template(tmp_path)
        manifest: dict = {}

        actions, _ = enable_v1_4_settings_layout(
            tmp_path, tpl, {"{{PRODUCT_NAME}}": "Legacy"}, manifest
        )

        assert any("settings.json" in a.lower() for a in actions)
        assert manifest["v1_4_settings_migrated"] is True

        merged = json.loads(settings.read_text())
        # All hook commands now go through product-hook (the canonical form);
        # the governance-hook bash dispatcher is gone.
        cmds = [
            h.get("command", "")
            for entries in merged["hooks"].values()
            for entry in entries
            for h in entry.get("hooks", [])
        ]
        assert all("governance-hook" not in c for c in cmds)
        assert any("product-hook" in c and c.startswith("python3 ") for c in cmds)

    def test_preserves_user_hooks_during_cleanup(self, tmp_path: Path):
        """User-added Stop hook stays alongside the prawduct hook after
        migration. The legacy_cleanup pass strips only prawduct-owned entries,
        never user-authored ones — same invariant as TestMergeSettings."""
        settings = tmp_path / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"matcher": "startup", "hooks": [
                    {"type": "command",
                     "command": "bash $CLAUDE_PROJECT_DIR/tools/governance-hook clear"}
                ]}],
                "Stop": [
                    {"matcher": "", "hooks": [
                        {"type": "command",
                         "command": "bash $CLAUDE_PROJECT_DIR/tools/governance-hook stop"}
                    ]},
                    {"matcher": "", "hooks": [
                        {"type": "command", "command": "my-custom-cleanup"}
                    ]},
                ],
            },
        }, indent=2))
        tpl = _minimal_template(tmp_path)

        enable_v1_4_settings_layout(
            tmp_path, tpl, {"{{PRODUCT_NAME}}": "X"}, manifest={}
        )

        stop_cmds = [
            h.get("command", "")
            for entry in json.loads(settings.read_text())["hooks"]["Stop"]
            for h in entry.get("hooks", [])
        ]
        assert "my-custom-cleanup" in stop_cmds
        assert any("product-hook" in c and "python3" in c for c in stop_cmds)
        assert not any("governance-hook" in c for c in stop_cmds)

    def test_preserves_top_level_user_keys(self, tmp_path: Path):
        """Non-prawduct top-level keys (customSetting, permissions, etc.) are
        preserved verbatim. The migration touches hooks + banner only."""
        settings = tmp_path / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({
            "customSetting": True,
            "permissions": {"allow": ["Bash(echo *)"]},
            "hooks": {},
        }, indent=2))
        tpl = _minimal_template(tmp_path)

        enable_v1_4_settings_layout(
            tmp_path, tpl, {"{{PRODUCT_NAME}}": "X"}, manifest={}
        )

        merged = json.loads(settings.read_text())
        assert merged["customSetting"] is True
        assert merged["permissions"] == {"allow": ["Bash(echo *)"]}

    def test_one_shot_manifest_short_circuits(self, tmp_path: Path):
        """Manifest flag set → no file read, no actions, no notes. Mirrors
        enable_v1_4_coverage's one-shot tracking. Without this, an
        accidental re-invocation would re-normalize a settings.json the user
        may have since hand-edited."""
        settings = tmp_path / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        # Write something that WOULD be normalized, to prove it isn't read.
        settings.write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "bash governance-hook clear"}
                ]}]
            }
        }, indent=2))
        tpl = _minimal_template(tmp_path)
        original = settings.read_text()
        manifest: dict = {"v1_4_settings_migrated": True}

        actions, notes = enable_v1_4_settings_layout(
            tmp_path, tpl, {"{{PRODUCT_NAME}}": "X"}, manifest
        )

        assert actions == []
        assert notes == []
        assert settings.read_text() == original

    def test_force_overrides_one_shot(self, tmp_path: Path):
        """`force=True` bypasses the manifest one-shot. Use case: a user
        re-runs after manually re-editing settings.json to re-normalize."""
        settings = tmp_path / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"matcher": "", "hooks": [
                    {"type": "command", "command": "bash governance-hook clear"}
                ]}]
            }
        }, indent=2))
        tpl = _minimal_template(tmp_path)
        manifest: dict = {"v1_4_settings_migrated": True}

        actions, _ = enable_v1_4_settings_layout(
            tmp_path, tpl, {"{{PRODUCT_NAME}}": "X"}, manifest, force=True
        )

        assert any("settings.json" in a.lower() for a in actions)
        # File mutated despite the pre-existing flag.
        cmds = [
            h.get("command", "")
            for entries in json.loads(settings.read_text())["hooks"].values()
            for entry in entries
            for h in entry.get("hooks", [])
        ]
        assert not any("governance-hook" in c for c in cmds)

    def test_bad_json_surfaces_diagnostic(self, tmp_path: Path):
        """Unparseable settings.json → diagnostic note, no crash, manifest
        flag NOT set (the migration didn't actually run to completion).
        Mirrors merge_settings' bad-JSON tolerance (returns False)."""
        settings = tmp_path / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text("not valid json {{{")
        tpl = _minimal_template(tmp_path)
        manifest: dict = {}

        actions, notes = enable_v1_4_settings_layout(
            tmp_path, tpl, {"{{PRODUCT_NAME}}": "X"}, manifest
        )

        assert actions == []
        assert any("could not parse" in n.lower() or "parse" in n.lower() for n in notes)
        # No silent flag-flip when the migration didn't actually run.
        assert "v1_4_settings_migrated" not in manifest


# =============================================================================
# `prawduct-setup migrate --enable-settings-layout` subcommand runner.
# =============================================================================


class TestRunMigrateSettingsLayout:

    def _scaffold_product(self, tmp_path: Path, framework: Path) -> Path:
        """Create a minimal product layout with .prawduct/, .claude/settings.json
        already on the minimal layout, and a sync-manifest.json pointing at
        the given framework. Returns the product root."""
        product = tmp_path / "product"
        prawduct = product / ".prawduct"
        prawduct.mkdir(parents=True)
        (prawduct / "project-state.yaml").write_text(
            'product_identity:\n  name: "TestApp"\n'
        )
        (prawduct / "sync-manifest.json").write_text(
            json.dumps({
                "framework_version": "1.3.17",
                "framework_source": str(framework),
                "product_name": "TestApp",
                "files": {},
            })
        )
        settings = product / ".claude" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"matcher": "startup|clear|resume", "hooks": [
                    {"type": "command",
                     "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" clear"}
                ]}],
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command",
                     "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" stop"}
                ]}],
            },
            "companyAnnouncements": ["TestApp — Built with Prawduct"],
        }, indent=2))
        return product

    def _scaffold_framework(self, tmp_path: Path) -> Path:
        """Synthetic framework checkout with just enough on disk for the
        runner to resolve templates: templates/product-settings.json."""
        fw = tmp_path / "framework"
        (fw / "templates").mkdir(parents=True)
        (fw / "templates" / "product-settings.json").write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"matcher": "startup|clear|resume", "hooks": [
                    {"type": "command",
                     "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" clear"}
                ]}],
                "Stop": [{"matcher": "", "hooks": [
                    {"type": "command",
                     "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" stop"}
                ]}],
            },
            "companyAnnouncements": ["{{PRODUCT_NAME}} — Built with Prawduct"],
        }, indent=2))
        return fw

    def test_no_prawduct_returns_error(self, tmp_path: Path):
        result = run_migrate_settings_layout(str(tmp_path))
        assert "error" in result
        assert ".prawduct" in result["error"]

    def test_no_manifest_returns_actionable_error(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        result = run_migrate_settings_layout(str(tmp_path))
        assert "error" in result
        assert "prawduct-setup setup" in result["error"]

    def test_framework_unreachable_returns_actionable_error(self, tmp_path: Path):
        """Manifest's framework_source points nowhere → error names the env
        var fallback. Mirrors run_sync's framework-resolution error path so
        the recovery advice is consistent across commands."""
        product = tmp_path / "product"
        (product / ".prawduct").mkdir(parents=True)
        (product / ".prawduct" / "sync-manifest.json").write_text(
            json.dumps({"framework_source": "/nonexistent/framework", "files": {}})
        )
        result = run_migrate_settings_layout(str(product))
        assert "error" in result
        assert "framework" in result["error"].lower()

    def test_persists_manifest_flag(self, tmp_path: Path):
        """After a successful run, sync-manifest.json on disk has
        v1_4_settings_migrated set — even when nothing changed in the file
        (already-minimal case still counts as 'opted in')."""
        fw = self._scaffold_framework(tmp_path)
        product = self._scaffold_product(tmp_path, fw)

        result = run_migrate_settings_layout(str(product))

        assert "error" not in result
        assert result["migrated"] is True

        manifest = json.loads((product / ".prawduct" / "sync-manifest.json").read_text())
        assert manifest.get("v1_4_settings_migrated") is True

    def test_one_shot_short_circuits_without_force(self, tmp_path: Path):
        """Second invocation without --force is a fast no-op (flag already
        in manifest). Mirrors run_migrate_coverage's one-shot semantics."""
        fw = self._scaffold_framework(tmp_path)
        product = self._scaffold_product(tmp_path, fw)

        run_migrate_settings_layout(str(product))
        # Mutate settings.json to a non-canonical shape — second run without
        # --force should NOT touch it (flag short-circuits).
        settings_path = product / ".claude" / "settings.json"
        settings_path.write_text(json.dumps({
            "hooks": {"Stop": [{"matcher": "", "hooks": [
                {"type": "command", "command": "bash governance-hook stop"}
            ]}]}
        }, indent=2))

        result = run_migrate_settings_layout(str(product))

        assert result["actions"] == []
        # Still has the bad shape because we didn't actually re-run.
        cmds = [
            h.get("command", "")
            for entries in json.loads(settings_path.read_text())["hooks"].values()
            for entry in entries
            for h in entry.get("hooks", [])
        ]
        assert any("governance-hook" in c for c in cmds)

    def test_force_re_runs_normalization(self, tmp_path: Path):
        """--force bypasses the one-shot and re-normalizes."""
        fw = self._scaffold_framework(tmp_path)
        product = self._scaffold_product(tmp_path, fw)

        run_migrate_settings_layout(str(product))
        settings_path = product / ".claude" / "settings.json"
        settings_path.write_text(json.dumps({
            "hooks": {"Stop": [{"matcher": "", "hooks": [
                {"type": "command", "command": "bash governance-hook stop"}
            ]}]}
        }, indent=2))

        result = run_migrate_settings_layout(str(product), force=True)

        assert any("settings.json" in a.lower() for a in result["actions"])
        cmds = [
            h.get("command", "")
            for entries in json.loads(settings_path.read_text())["hooks"].values()
            for entry in entries
            for h in entry.get("hooks", [])
        ]
        assert not any("governance-hook" in c for c in cmds)

    def test_result_shape_is_stable(self, tmp_path: Path):
        """JSON-mode callers depend on the keys being present in every
        branch: product_dir, migrated, force, actions, notes."""
        fw = self._scaffold_framework(tmp_path)
        product = self._scaffold_product(tmp_path, fw)

        result = run_migrate_settings_layout(str(product))

        assert set(result.keys()) >= {
            "product_dir", "migrated", "force", "actions", "notes",
        }


# =============================================================================
# F5a — auto-commit on sync
# =============================================================================


def _git_init(repo: Path, *, branch: str = "main") -> None:
    """Initialize a git repo in `repo` with a deterministic identity."""
    subprocess.run(["git", "init", "-q", "-b", branch, str(repo)], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Test"], check=True
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "commit.gpgsign", "false"], check=True
    )


def _git_commit_all(repo: Path, message: str) -> None:
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-q", "-m", message], check=True
    )


def _git_log_subjects(repo: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), "log", "--format=%s"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


class TestReadSyncConfig:
    """F5a — `_read_sync_config` is the column-0 YAML scanner."""

    def test_defaults_when_no_project_state(self, tmp_path: Path):
        product = tmp_path / "p"
        product.mkdir()
        config = _read_sync_config(product)
        assert config["auto_commit"] is True
        assert config["protected_branches"] == list(_DEFAULT_PROTECTED_BRANCHES)

    def test_defaults_when_no_sync_block(self, tmp_path: Path):
        product = tmp_path / "p"
        (product / ".prawduct").mkdir(parents=True)
        (product / ".prawduct" / "project-state.yaml").write_text(
            "project_name: Demo\nother: thing\n"
        )
        config = _read_sync_config(product)
        assert config["auto_commit"] is True
        assert config["protected_branches"] == list(_DEFAULT_PROTECTED_BRANCHES)

    def test_explicit_disable(self, tmp_path: Path):
        product = tmp_path / "p"
        (product / ".prawduct").mkdir(parents=True)
        (product / ".prawduct" / "project-state.yaml").write_text(
            "sync:\n  auto_commit: false\n"
        )
        config = _read_sync_config(product)
        assert config["auto_commit"] is False

    def test_custom_protected_branches(self, tmp_path: Path):
        product = tmp_path / "p"
        (product / ".prawduct").mkdir(parents=True)
        (product / ".prawduct" / "project-state.yaml").write_text(
            "sync:\n"
            "  auto_commit: true\n"
            "  protected_branches:\n"
            "    - production\n"
            "    - \"hotfix/*\"\n"
        )
        config = _read_sync_config(product)
        assert config["protected_branches"] == ["production", "hotfix/*"]

    def test_inline_comment_on_value_is_tolerated(self, tmp_path: Path):
        """Mirrors the Chunk 10 inline-comment-asymmetry fix: detector and
        consumer must both tolerate trailing comments."""
        product = tmp_path / "p"
        (product / ".prawduct").mkdir(parents=True)
        (product / ".prawduct" / "project-state.yaml").write_text(
            "sync:\n  auto_commit: false  # opt out for this product\n"
        )
        config = _read_sync_config(product)
        assert config["auto_commit"] is False

    def test_malformed_falls_back_to_defaults(self, tmp_path: Path):
        product = tmp_path / "p"
        (product / ".prawduct").mkdir(parents=True)
        # Unreadable file — patch by making it a directory
        (product / ".prawduct" / "project-state.yaml").mkdir()
        config = _read_sync_config(product)
        assert config["auto_commit"] is True


class TestBranchIsProtected:
    def test_exact_match(self):
        assert _branch_is_protected("main", ["main", "master"]) is True
        assert _branch_is_protected("master", ["main", "master"]) is True
        assert _branch_is_protected("feature/x", ["main", "master"]) is False

    def test_glob_match(self):
        assert _branch_is_protected("release/1.0", ["release/*"]) is True
        assert _branch_is_protected("release/foo/bar", ["release/*"]) is True
        assert _branch_is_protected("rel/1.0", ["release/*"]) is False

    def test_empty_branch_is_protected(self):
        """Detached HEAD (empty branch name) must be treated as protected —
        commits in detached HEAD become unreachable after checkout."""
        assert _branch_is_protected("", ["main"]) is True


class _AutoCommitFixture:
    """Helper for F5a tests — build a product repo with a real git history."""

    def __init__(self, tmp_path: Path):
        self.tmp_path = tmp_path
        self.fw = self._setup_framework()
        self.product = self._setup_product()

    def _setup_framework(self) -> Path:
        fw = self.tmp_path / "framework"
        fw.mkdir()
        templates = fw / "templates"
        templates.mkdir()
        (templates / "product-claude.md").write_text(
            f"# {{{{PRODUCT_NAME}}}} CLAUDE.md\n\n"
            f"{BLOCK_BEGIN}\nContent v2\n{BLOCK_END}\n"
        )
        (templates / "critic-review.md").write_text("# {{PRODUCT_NAME}} Critic v2")
        (templates / "product-settings.json").write_text(json.dumps({
            "hooks": {
                "SessionStart": [{"matcher": "clear", "hooks": [
                    {"type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR/tools/product-hook\" clear"}
                ]}],
            }
        }, indent=2))
        tools = fw / "tools"
        tools.mkdir()
        (tools / "product-hook").write_text("#!/usr/bin/env python3\n# hook v2")
        return fw

    def _setup_product(self) -> Path:
        product = self.tmp_path / "product"
        product.mkdir()
        (product / ".prawduct").mkdir()

        subs = {"{{PRODUCT_NAME}}": "TestApp"}

        # Older content so sync will detect drift on these managed files.
        claude_v1 = (
            f"# TestApp CLAUDE.md\n\n{BLOCK_BEGIN}\nContent v1\n{BLOCK_END}\n"
        )
        (product / "CLAUDE.md").write_text(claude_v1)

        critic_v1 = "# TestApp Critic v1"
        (product / ".prawduct" / "critic-review.md").write_text(critic_v1)

        (product / "tools").mkdir()
        (product / "tools" / "product-hook").write_text(
            "#!/usr/bin/env python3\n# hook v1"
        )

        (product / ".claude").mkdir()
        (product / ".claude" / "settings.json").write_text(
            (self.fw / "templates" / "product-settings.json").read_text()
        )

        hashes = {
            "CLAUDE.md": compute_block_hash(claude_v1),
            ".prawduct/critic-review.md": compute_hash(
                product / ".prawduct" / "critic-review.md"
            ),
            "tools/product-hook": compute_hash(product / "tools" / "product-hook"),
            ".claude/settings.json": None,
        }

        (product / ".gitignore").write_text("\n".join(GITIGNORE_ENTRIES) + "\n")

        manifest = create_manifest(product, self.fw, "TestApp", hashes)
        (product / ".prawduct" / "sync-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )

        # Project-state.yaml: feature-branch friendly defaults (main is protected
        # by default, which we override per-test as needed).
        (product / ".prawduct" / "project-state.yaml").write_text(
            "project_name: TestApp\n"
        )

        return product

    def init_git(self, *, branch: str = "feature/work") -> None:
        _git_init(self.product, branch=branch)
        _git_commit_all(self.product, "initial product import")

    def sync(self) -> dict:
        return run_sync(
            str(self.product), str(self.fw), no_pull=True
        )


class TestAutoCommitHappyPath:
    """Clean feature branch + framework-managed drift → single marker commit."""

    def test_creates_single_chore_sync_commit(self, tmp_path: Path):
        fix = _AutoCommitFixture(tmp_path)
        fix.init_git(branch="feature/work")

        result = fix.sync()

        subjects = _git_log_subjects(fix.product)
        # The HEAD commit is the auto-commit; the initial import remains below.
        assert subjects[0].startswith("chore(sync): prawduct v"), subjects
        # Only one new commit was produced.
        assert len(subjects) == 2

        # The action list records the commit shorthand.
        assert any(
            "Auto-committed framework sync as 'chore(sync): prawduct v" in a
            for a in result["actions"]
        ), result["actions"]

    def test_no_sync_pending_marker_on_success(self, tmp_path: Path):
        fix = _AutoCommitFixture(tmp_path)
        fix.init_git(branch="feature/work")
        # Pre-existing stale marker — auto-commit success must clear it.
        (fix.product / ".prawduct" / ".sync-pending").write_text(
            '{"reason":"stale"}\n'
        )

        fix.sync()

        assert not (fix.product / ".prawduct" / ".sync-pending").exists()

    def test_working_tree_clean_after_auto_commit(self, tmp_path: Path):
        fix = _AutoCommitFixture(tmp_path)
        fix.init_git(branch="feature/work")
        fix.sync()
        result = subprocess.run(
            ["git", "-C", str(fix.product), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.strip() == "", result.stdout

    def test_commit_message_pins_framework_version(self, tmp_path: Path):
        fix = _AutoCommitFixture(tmp_path)
        fix.init_git(branch="feature/work")
        fix.sync()
        subjects = _git_log_subjects(fix.product)
        assert subjects[0] == f"chore(sync): prawduct v{PRAWDUCT_VERSION}"


class TestAutoCommitPreconditions:
    """Each precondition must skip auto-commit and write the sync-pending marker."""

    def test_protected_branch_blocks_commit(self, tmp_path: Path):
        fix = _AutoCommitFixture(tmp_path)
        fix.init_git(branch="main")  # default-protected
        result = fix.sync()

        subjects = _git_log_subjects(fix.product)
        # No auto-commit was added.
        assert not subjects[0].startswith("chore(sync):")
        assert any("'main' is protected" in n for n in result["notes"]), result["notes"]
        marker = json.loads(
            (fix.product / ".prawduct" / ".sync-pending").read_text()
        )
        assert "main" in marker["reason"]
        assert marker["version"] == PRAWDUCT_VERSION

    def test_wip_blocks_commit(self, tmp_path: Path):
        fix = _AutoCommitFixture(tmp_path)
        fix.init_git(branch="feature/work")
        # Introduce an unrelated WIP file (untracked, not in framework-managed list).
        (fix.product / "src").mkdir()
        (fix.product / "src" / "user_code.py").write_text("# WIP\n")

        result = fix.sync()

        subjects = _git_log_subjects(fix.product)
        assert not subjects[0].startswith("chore(sync):")
        assert any("non-framework changes present" in n for n in result["notes"])
        marker_path = fix.product / ".prawduct" / ".sync-pending"
        assert marker_path.is_file()
        marker = json.loads(marker_path.read_text())
        assert any(
            "non-framework" in b for b in marker["blocked_by"]
        ), marker

    def test_rebase_in_progress_blocks_commit(self, tmp_path: Path):
        fix = _AutoCommitFixture(tmp_path)
        fix.init_git(branch="feature/work")
        # Simulate an interactive rebase by creating the marker dir.
        (fix.product / ".git" / "rebase-merge").mkdir()

        result = fix.sync()

        subjects = _git_log_subjects(fix.product)
        assert not subjects[0].startswith("chore(sync):")
        assert any("rebase in progress" in n for n in result["notes"])

    def test_merge_in_progress_blocks_commit(self, tmp_path: Path):
        fix = _AutoCommitFixture(tmp_path)
        fix.init_git(branch="feature/work")
        (fix.product / ".git" / "MERGE_HEAD").write_text("abc123\n")

        result = fix.sync()

        assert any("merge in progress" in n for n in result["notes"])

    def test_cherry_pick_in_progress_blocks_commit(self, tmp_path: Path):
        fix = _AutoCommitFixture(tmp_path)
        fix.init_git(branch="feature/work")
        (fix.product / ".git" / "CHERRY_PICK_HEAD").write_text("abc123\n")

        result = fix.sync()

        assert any("cherry-pick in progress" in n for n in result["notes"])

    def test_auto_commit_disabled_via_project_state(self, tmp_path: Path):
        fix = _AutoCommitFixture(tmp_path)
        (fix.product / ".prawduct" / "project-state.yaml").write_text(
            "project_name: TestApp\nsync:\n  auto_commit: false\n"
        )
        fix.init_git(branch="feature/work")

        result = fix.sync()

        subjects = _git_log_subjects(fix.product)
        assert not subjects[0].startswith("chore(sync):")
        # No commit; no marker either — disable is an explicit user choice, not
        # a precondition failure.
        assert not (fix.product / ".prawduct" / ".sync-pending").exists()
        assert not any(
            "Auto-commit skipped" in n for n in result["notes"]
        ), result["notes"]


class TestAutoCommitSafety:
    """Edge cases that must degrade silently or be inert."""

    def test_not_a_git_repo_is_silent_noop(self, tmp_path: Path):
        """No `.git/` directory → auto-commit step quietly does nothing."""
        fix = _AutoCommitFixture(tmp_path)
        # Intentionally do NOT init git.
        result = fix.sync()
        # Sync still completes — it returns its normal action list.
        assert result["synced"] is True
        # No marker is written; nothing to commit against.
        assert not (fix.product / ".prawduct" / ".sync-pending").exists()
        # No "Auto-committed" or "Auto-commit skipped" lines.
        for entry in result["actions"] + result["notes"]:
            assert "Auto-commit" not in entry, entry

    def test_no_drift_clears_stale_marker(self, tmp_path: Path):
        """Pre-existing marker should be cleared when there's no drift to commit."""
        fix = _AutoCommitFixture(tmp_path)
        fix.init_git(branch="feature/work")
        # First sync resolves all drift.
        fix.sync()
        # Plant a stale marker.
        (fix.product / ".prawduct" / ".sync-pending").write_text(
            '{"reason":"stale"}\n'
        )
        # Second sync has nothing to commit and should clear the marker.
        fix.sync()
        assert not (fix.product / ".prawduct" / ".sync-pending").exists()

    def test_user_authored_place_once_edits_treated_as_wip(self, tmp_path: Path):
        """Regression for Chunk 11 Critic finding 1: a user-authored append to
        `.prawduct/change-log.md` (a place-once file) at SessionStart-style
        sync time must be treated as WIP and block auto-commit, NOT swept into
        the chore(sync) marker commit. Pre-fix, PLACE_ONCE_TEMPLATES were in
        the framework-known set; the very co-mingling F5a aims to prevent was
        the default behavior on every chunk close."""
        fix = _AutoCommitFixture(tmp_path)
        # Seed `.prawduct/change-log.md` so it exists at initial-commit time.
        (fix.product / ".prawduct" / "change-log.md").write_text(
            "# Change Log\n\n## 2026-01-01: baseline\n"
        )
        fix.init_git(branch="feature/work")
        # User appends to change-log.md mid-session — the typical chunk-close
        # pattern.
        existing = (fix.product / ".prawduct" / "change-log.md").read_text()
        (fix.product / ".prawduct" / "change-log.md").write_text(
            existing + "\n## 2026-05-19: user-authored chunk entry\n"
        )

        result = fix.sync()

        subjects = _git_log_subjects(fix.product)
        # No auto-commit was made: the change-log edit is user WIP, not
        # framework drift.
        assert not subjects[0].startswith("chore(sync):"), subjects
        assert any(
            "non-framework changes present" in n for n in result["notes"]
        ), result["notes"]
        marker_path = fix.product / ".prawduct" / ".sync-pending"
        assert marker_path.is_file()
        marker = json.loads(marker_path.read_text())
        joined = " ".join(marker["blocked_by"])
        assert "change-log.md" in joined, marker

    def test_managed_paths_committed_wip_excluded(self, tmp_path: Path):
        """When committing, the auto-commit must NOT pull in WIP — but if WIP
        is present we don't auto-commit at all. This test pins the contract by
        verifying that on success, the committed paths are framework-managed.

        v1.5.1 Chunk 04(c) — the fixture writes a deliberately-stale
        ``.gitignore`` (omits the first GITIGNORE_ENTRIES line) so the next
        sync's ``update_gitignore`` step actually mutates ``.gitignore`` and
        that mutation lands in the auto-commit. Without the staleness, the
        sync finds nothing to add and ``.gitignore`` never shows up in the
        diff — the test silently stops exercising the gitignore-update path
        the moment a new entry is appended to ``GITIGNORE_ENTRIES``.
        """
        fix = _AutoCommitFixture(tmp_path)
        # Overwrite the fixture's already-current .gitignore with a stale
        # version missing one current entry — forces update_gitignore to
        # mutate it during the upcoming sync.
        stale_entries = list(GITIGNORE_ENTRIES)
        assert len(stale_entries) >= 1, "GITIGNORE_ENTRIES is empty — fixture invariant broken"
        omitted = stale_entries.pop(0)
        (fix.product / ".gitignore").write_text("\n".join(stale_entries) + "\n")
        fix.init_git(branch="feature/work")
        fix.sync()
        # Inspect last commit's diff.
        result = subprocess.run(
            ["git", "-C", str(fix.product), "show", "--name-only", "--format=", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        changed = [p for p in result.stdout.splitlines() if p]
        # .gitignore is in the allowed-set because update_gitignore is a
        # framework-owned mutation, not user WIP. Without listing it
        # explicitly, the post-fix sync would fail this assertion.
        managed = set(MANAGED_FILES.keys()) | {".prawduct/sync-manifest.json", ".gitignore"}
        for p in changed:
            assert p in managed or p.startswith(".prawduct/"), (
                f"non-managed path {p} in auto-commit"
            )
        # Sanity: confirm we actually exercised the gitignore-update path.
        assert ".gitignore" in changed, (
            f"sync should have re-added omitted entry {omitted!r} to .gitignore; "
            f"diff was {changed!r}"
        )
        gitignore_after = (fix.product / ".gitignore").read_text()
        assert omitted in gitignore_after, (
            f"update_gitignore should have re-added {omitted!r}"
        )



class TestRunSyncAdvisoryStep:
    """run_sync wires the post-sync advisory probe step (v1.6.0 Phase 1).

    Proves the integration end-to-end through the real run_sync: with a
    synthetic probe registered, a sync writes the advisory to the per-clone
    nag log, and the template-drift `advisories` return key stays a distinct
    concept. As of v1.7.0 the production roster contains the backlog probe,
    but it stays silent on these fixtures (no legacy backlog file), so the
    store is empty unless a probe is explicitly triggered (the backlog probe's
    own trigger/resolve path is covered by
    TestRunSync.test_legacy_backlog_triggers_then_resolves_on_migration).
    """

    _adv = _mod._lib_advisory_store

    @pytest.fixture(autouse=True)
    def _clean_registry(self):
        self._adv.clear_registry()
        yield
        self._adv.clear_registry()

    def _synthetic_probe(self, state, codebase):
        if state.get("synthetic_resolved") is True:
            return []
        if not codebase.has_files_matching("SYNTHETIC_TRIGGER"):
            return []
        return [
            self._adv.AdvisoryCandidate(
                type="synthetic-condition",
                evidence=("SYNTHETIC_TRIGGER present",),
                trigger_summary="Synthetic trigger present and not yet resolved.",
                recommended_action="/prawduct-advisory list",
            )
        ]

    def test_no_triggered_probe_writes_empty_store(self, tmp_path: Path):
        # No synthetic probe registered and no legacy backlog file → the only
        # production probe (backlog) is silent, so the store stays empty.
        helper = TestRunSync()
        fw = helper._setup_framework(tmp_path)
        product = helper._setup_product(tmp_path, fw)
        result = run_sync(str(product), framework_dir=str(fw))
        # The template-drift advisories key is independent of the new store.
        assert "advisories" in result
        store = self._adv.read_store(product)
        assert store["advisories"] == []

    def test_synthetic_probe_writes_advisory(self, tmp_path: Path):
        helper = TestRunSync()
        fw = helper._setup_framework(tmp_path)
        product = helper._setup_product(tmp_path, fw)
        (product / "SYNTHETIC_TRIGGER").write_text("x")
        self._adv.register_probe("synthetic", "synthetic-condition", 1, self._synthetic_probe)

        run_sync(str(product), framework_dir=str(fw))

        store = self._adv.read_store(product)
        assert len(store["advisories"]) == 1
        adv = store["advisories"][0]
        assert adv["state"] == "active"
        assert adv["feature"] == "synthetic"
        # The store landed at the gitignored nag-log path.
        assert (product / ".prawduct" / ".advisories.json").is_file()
