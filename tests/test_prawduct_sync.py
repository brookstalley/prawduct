"""Tests for prawduct-sync.py — the product repo sync module.

Uses importlib to handle the hyphenated filename.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Load prawduct-sync.py despite the hyphen in its name
_TOOL_PATH = Path(__file__).resolve().parent.parent / "tools" / "prawduct-sync.py"
_spec = importlib.util.spec_from_file_location("prawduct_sync", _TOOL_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

compute_hash = _mod.compute_hash
compute_block_hash = _mod.compute_block_hash
extract_block = _mod.extract_block
render_template = _mod.render_template
merge_settings = _mod.merge_settings
create_manifest = _mod.create_manifest
run_sync = _mod.run_sync
BLOCK_BEGIN = _mod.BLOCK_BEGIN
BLOCK_END = _mod.BLOCK_END


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

        assert manifest["format_version"] == 1
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
            "tools/product-hook",
            ".claude/settings.json",
        }


# =============================================================================
# run_sync
# =============================================================================


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

        manifest = create_manifest(product, fw, product_name, hashes)
        (product / ".prawduct" / "sync-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n"
        )

        return product

    def test_no_manifest_skips(self, tmp_path: Path):
        product = tmp_path / "product"
        product.mkdir()
        result = run_sync(str(product))
        assert result["synced"] is False
        assert result["reason"] == "no manifest"

    def test_invalid_manifest_skips(self, tmp_path: Path):
        product = tmp_path / "product"
        (product / ".prawduct").mkdir(parents=True)
        (product / ".prawduct" / "sync-manifest.json").write_text("bad json{{{")
        result = run_sync(str(product))
        assert result["synced"] is False
        assert result["reason"] == "invalid manifest JSON"

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

    def test_user_edited_block_skipped(self, tmp_path: Path):
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # User edits inside the block
        claude = (product / "CLAUDE.md").read_text()
        claude = claude.replace("Content v1", "My custom content")
        (product / "CLAUDE.md").write_text(claude)

        # Update template
        (fw / "templates" / "product-claude.md").write_text(
            f"# {{{{PRODUCT_NAME}}}} CLAUDE.md\n\n"
            f"{BLOCK_BEGIN}\nContent v2\n{BLOCK_END}\n"
        )

        result = run_sync(str(product), framework_dir=str(fw))
        # Should skip CLAUDE.md because user edited the block
        assert not any("CLAUDE.md" in a for a in result["actions"])
        assert any("Skipped CLAUDE.md" in n for n in result["notes"])
        # User's content preserved
        assert "My custom content" in (product / "CLAUDE.md").read_text()

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

    def test_skips_user_edited_block(self, tmp_path: Path):
        """If user edited content inside markers, skip with note."""
        fw = self._setup_framework(tmp_path)
        product = self._setup_product(tmp_path, fw)

        # User edits inside the markers
        claude = (product / "CLAUDE.md").read_text()
        claude = claude.replace("Content v1", "My custom content")
        (product / "CLAUDE.md").write_text(claude)

        # Update template
        (fw / "templates" / "product-claude.md").write_text(
            f"# CLAUDE.md — {{{{PRODUCT_NAME}}}}\n\n"
            f"{BLOCK_BEGIN}\n\n## What This Is\n\nContent v2\n\n{BLOCK_END}\n"
        )

        result = run_sync(str(product), framework_dir=str(fw))
        assert not any("CLAUDE.md" in a for a in result["actions"])
        assert any("user edited block" in n for n in result["notes"])
        assert "My custom content" in (product / "CLAUDE.md").read_text()

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
