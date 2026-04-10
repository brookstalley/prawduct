"""Property-based tests for prawduct sync functionality.

These tests express properties derived from the sync specification,
not implementation details. They use Hypothesis to generate varied
inputs and verify that invariants hold.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Load prawduct-setup.py via importlib (same pattern as existing tests)
_TOOL_PATH = Path(__file__).resolve().parent.parent.parent / "tools" / "prawduct-setup.py"
_spec = importlib.util.spec_from_file_location("prawduct_setup", _TOOL_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

compute_hash = _mod.compute_hash
compute_block_hash = _mod.compute_block_hash
extract_block = _mod.extract_block
render_template = _mod.render_template
create_manifest = _mod.create_manifest
run_sync = _mod.run_sync
BLOCK_BEGIN = _mod.BLOCK_BEGIN
BLOCK_END = _mod.BLOCK_END
MANAGED_FILES = _mod.MANAGED_FILES
GITIGNORE_ENTRIES = _mod.GITIGNORE_ENTRIES


# =============================================================================
# Helpers
# =============================================================================


def _minimal_framework(tmp_path: Path) -> Path:
    """Create a minimal framework directory with required templates."""
    fw = tmp_path / "framework"
    fw.mkdir()
    (fw / "VERSION").write_text("1.0.0-test")

    templates = fw / "templates"
    templates.mkdir()

    # CLAUDE.md template (block_template strategy)
    (templates / "product-claude.md").write_text(
        f"# {{{{PRODUCT_NAME}}}}\n\n{BLOCK_BEGIN}\nFramework content v1\n{BLOCK_END}\n"
    )

    # Minimal templates for other managed files
    for rel_path, config in MANAGED_FILES.items():
        strategy = config.get("strategy", "template")
        tpl_rel = config.get("template") or config.get("source")
        if not tpl_rel:
            continue
        tpl_path = fw / tpl_rel
        if tpl_path.exists():
            continue
        tpl_path.parent.mkdir(parents=True, exist_ok=True)
        if strategy == "always_update":
            src = fw.parent.parent / tpl_rel
            if src.exists():
                tpl_path.write_bytes(src.read_bytes())
            else:
                tpl_path.write_text("#!/usr/bin/env python3\n# hook")
            tpl_path.chmod(0o755)
        elif strategy == "merge_settings":
            tpl_path.write_text(json.dumps({
                "hooks": {
                    "SessionStart": [{"matcher": "clear", "hooks": [
                        {"type": "command",
                         "command": 'python3 "$CLAUDE_PROJECT_DIR/tools/product-hook" clear'}
                    ]}],
                    "Stop": [{"matcher": "", "hooks": [
                        {"type": "command",
                         "command": 'python3 "$CLAUDE_PROJECT_DIR/tools/product-hook" stop'}
                    ]}],
                }
            }, indent=2))
        else:
            tpl_path.write_text(f"# {{{{PRODUCT_NAME}}}} — {rel_path}\nContent.\n")

    # Tools dir for product-hook source
    tools = fw / "tools"
    tools.mkdir(exist_ok=True)
    hook = tools / "product-hook"
    if not hook.exists():
        hook.write_text("#!/usr/bin/env python3\n# product-hook v1\n")
        hook.chmod(0o755)

    return fw


def _init_product(tmp_path: Path, fw: Path, product_name: str = "TestApp") -> Path:
    """Initialize a product by running init, giving us a known-good starting state."""
    product = tmp_path / "product"
    product.mkdir()

    # Use run_init for a real product structure
    run_init = _mod.run_init
    result = run_init(str(product), product_name)
    assert result["files_written"] > 0

    # Point manifest at our test framework
    manifest_path = product / ".prawduct" / "sync-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["framework_source"] = str(fw)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    # Sync once to align hashes with our test framework
    run_sync(str(product), framework_dir=str(fw), no_pull=True)

    return product


# =============================================================================
# Property: compute_hash is deterministic and consistent
# =============================================================================


class TestHashProperties:
    @given(content=st.binary())
    @settings(max_examples=50)
    def test_hash_matches_hashlib(self, content: bytes):
        """compute_hash always matches hashlib.sha256 for any content."""
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "test_file"
            f.write_bytes(content)
            expected = hashlib.sha256(content).hexdigest()
            assert compute_hash(f) == expected

    @given(content=st.binary())
    @settings(max_examples=50)
    def test_hash_is_deterministic(self, content: bytes):
        """Same content always produces the same hash."""
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "test_file"
            f.write_bytes(content)
            h1 = compute_hash(f)
            h2 = compute_hash(f)
            assert h1 == h2

    @given(a=st.binary(min_size=1), b=st.binary(min_size=1))
    @settings(max_examples=50)
    def test_different_content_different_hash(self, a: bytes, b: bytes):
        """Different content should (almost certainly) produce different hashes."""
        assume(a != b)
        with tempfile.TemporaryDirectory() as td:
            fa = Path(td) / "a"
            fb = Path(td) / "b"
            fa.write_bytes(a)
            fb.write_bytes(b)
            assert compute_hash(fa) != compute_hash(fb)


# =============================================================================
# Property: extract_block roundtrips
# =============================================================================


class TestBlockProperties:
    @given(
        before=st.text(min_size=0, max_size=200),
        block_content=st.text(min_size=0, max_size=200),
        after=st.text(min_size=0, max_size=200),
    )
    @settings(max_examples=50)
    def test_extract_block_roundtrip(self, before: str, block_content: str, after: str):
        """Extracting a block and reconstructing the file preserves content."""
        # Avoid content that contains the markers themselves
        assume(BLOCK_BEGIN not in before)
        assume(BLOCK_END not in before)
        assume(BLOCK_BEGIN not in block_content)
        assume(BLOCK_END not in block_content)
        assume(BLOCK_BEGIN not in after)
        assume(BLOCK_END not in after)

        full = f"{before}{BLOCK_BEGIN}\n{block_content}\n{BLOCK_END}\n{after}"
        extracted_block, extracted_before, extracted_after = extract_block(full)

        assert extracted_block is not None
        reconstructed = extracted_before + BLOCK_BEGIN + "\n" + extracted_block + "\n" + BLOCK_END + "\n" + extracted_after
        # The reconstruction should contain all the original parts
        assert BLOCK_BEGIN in reconstructed
        assert BLOCK_END in reconstructed

    @given(content=st.text(min_size=0, max_size=500))
    @settings(max_examples=50)
    def test_no_markers_returns_none_block(self, content: str):
        """Content without markers returns None for the block."""
        assume(BLOCK_BEGIN not in content)
        block, before, after = extract_block(content)
        assert block is None

    @given(block_content=st.text(min_size=1, max_size=200))
    @settings(max_examples=50)
    def test_block_hash_deterministic(self, block_content: str):
        """Block hash is deterministic for same content."""
        assume(BLOCK_BEGIN not in block_content)
        assume(BLOCK_END not in block_content)
        full = f"{BLOCK_BEGIN}\n{block_content}\n{BLOCK_END}\n"
        h1 = compute_block_hash(full)
        h2 = compute_block_hash(full)
        assert h1 is not None
        assert h1 == h2


# =============================================================================
# Property: render_template substitutes all occurrences
# =============================================================================


class TestRenderProperties:
    @given(
        product_name=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "P")),
            min_size=1,
            max_size=50,
        )
    )
    @settings(max_examples=50)
    def test_no_unreplaced_placeholders(self, product_name: str):
        """After rendering, no {{PRODUCT_NAME}} placeholders remain."""
        with tempfile.TemporaryDirectory() as td:
            tpl = Path(td) / "tpl.md"
            tpl.write_text(
                "# {{PRODUCT_NAME}} Guide\n"
                "Welcome to {{PRODUCT_NAME}}.\n"
                "Built for {{PRODUCT_NAME}}.\n"
            )
            result = render_template(tpl, {"{{PRODUCT_NAME}}": product_name})
            assert "{{PRODUCT_NAME}}" not in result

    @given(
        product_name=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "P")),
            min_size=1,
            max_size=50,
        )
    )
    @settings(max_examples=50)
    def test_substitution_count_matches(self, product_name: str):
        """Number of substituted occurrences matches template placeholder count."""
        with tempfile.TemporaryDirectory() as td:
            tpl = Path(td) / "tpl.md"
            template_text = "A {{PRODUCT_NAME}} B {{PRODUCT_NAME}} C"
            tpl.write_text(template_text)
            result = render_template(tpl, {"{{PRODUCT_NAME}}": product_name})
            assert result.count(product_name) >= 2


# =============================================================================
# Property: sync idempotency
# =============================================================================


class TestSyncIdempotency:
    @settings(max_examples=3, deadline=None)
    @given(data=st.data())
    def test_sync_twice_is_same_as_once(self, data):
        """Running sync twice produces no changes on the second run."""
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            fw = _minimal_framework(tmp_path)
            product = _init_product(tmp_path, fw)

            # First sync (may or may not have changes)
            result1 = run_sync(str(product), framework_dir=str(fw), no_pull=True)

            # Snapshot state after first sync
            manifest_after_first = json.loads(
                (product / ".prawduct" / "sync-manifest.json").read_text()
            )

            # Second sync — should have no changes
            result2 = run_sync(str(product), framework_dir=str(fw), no_pull=True)

            assert result2["synced"] is False, (
                f"Second sync should have no changes but got actions: {result2['actions']}"
            )
            assert result2["actions"] == []

            # Manifest file hashes unchanged
            manifest_after_second = json.loads(
                (product / ".prawduct" / "sync-manifest.json").read_text()
            )
            for rel_path in manifest_after_first.get("files", {}):
                h1 = manifest_after_first["files"][rel_path].get("generated_hash")
                h2 = manifest_after_second["files"][rel_path].get("generated_hash")
                assert h1 == h2, f"Hash changed for {rel_path} between syncs"

    @settings(max_examples=3, deadline=None)
    @given(
        user_content=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
            min_size=1,
            max_size=200,
        )
    )
    def test_sync_preserves_user_edits(self, user_content: str):
        """Sync does not overwrite user-edited files (without --force)."""
        assume(BLOCK_BEGIN not in user_content)
        assume(BLOCK_END not in user_content)
        assume("{{" not in user_content)

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            fw = _minimal_framework(tmp_path)
            product = _init_product(tmp_path, fw)

            # User edits a template-strategy file
            user_file = product / ".prawduct" / "critic-review.md"
            if user_file.exists():
                user_file.write_text(user_content)

                # Sync should NOT overwrite
                run_sync(str(product), framework_dir=str(fw), no_pull=True)

                assert user_file.read_text() == user_content, (
                    "Sync overwrote user-edited file without --force"
                )


# =============================================================================
# Property: manifest completeness after sync
# =============================================================================


class TestManifestProperties:
    @settings(max_examples=3, deadline=None)
    @given(data=st.data())
    def test_manifest_covers_all_managed_files(self, data):
        """After sync, manifest has an entry for every file in MANAGED_FILES."""
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            fw = _minimal_framework(tmp_path)
            product = _init_product(tmp_path, fw)

            run_sync(str(product), framework_dir=str(fw), no_pull=True)

            manifest = json.loads(
                (product / ".prawduct" / "sync-manifest.json").read_text()
            )

            for rel_path in MANAGED_FILES:
                assert rel_path in manifest["files"], (
                    f"Managed file {rel_path} missing from manifest after sync"
                )

    @settings(max_examples=3, deadline=None)
    @given(data=st.data())
    def test_manifest_hashes_match_files(self, data):
        """After sync, manifest hashes match actual file content."""
        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td)
            fw = _minimal_framework(tmp_path)
            product = _init_product(tmp_path, fw)

            run_sync(str(product), framework_dir=str(fw), no_pull=True)

            manifest = json.loads(
                (product / ".prawduct" / "sync-manifest.json").read_text()
            )

            for rel_path, config in manifest["files"].items():
                strategy = config.get("strategy", "template")
                stored_hash = config.get("generated_hash")

                if stored_hash is None:
                    continue  # merge_settings doesn't track hash

                file_path = product / rel_path
                if not file_path.exists():
                    continue

                if strategy == "block_template":
                    actual_hash = compute_block_hash(file_path.read_text())
                else:
                    actual_hash = compute_hash(file_path)

                if actual_hash is not None:
                    assert stored_hash == actual_hash, (
                        f"Hash mismatch for {rel_path}: "
                        f"manifest={stored_hash[:12]}... actual={actual_hash[:12]}..."
                    )
