"""Property-based tests for prawduct init functionality.

These tests express properties derived from the init specification:
- Init produces a valid product structure
- Init is idempotent (second run produces no new actions)
- Init substitutes product name in all templates
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

# Load prawduct-setup.py via importlib
_TOOL_PATH = Path(__file__).resolve().parent.parent.parent / "tools" / "prawduct-setup.py"
_spec = importlib.util.spec_from_file_location("prawduct_setup", _TOOL_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

run_init = _mod.run_init
MANAGED_FILES = _mod.MANAGED_FILES
BLOCK_BEGIN = _mod.BLOCK_BEGIN
BLOCK_END = _mod.BLOCK_END


# Strategy for valid product names: letters, numbers, spaces, hyphens
product_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=" -"),
    min_size=1,
    max_size=40,
).filter(lambda s: s.strip())  # Must have non-whitespace content


# =============================================================================
# Property: init produces a valid product structure
# =============================================================================


class TestInitStructure:
    @given(product_name=product_names)
    @settings(max_examples=10, deadline=None)
    def test_init_creates_required_directories(self, product_name: str):
        """Init always creates the required directory structure."""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "product"
            target.mkdir()

            run_init(str(target), product_name)

            assert (target / ".prawduct").is_dir()
            assert (target / ".prawduct" / "artifacts").is_dir()
            assert (target / ".claude").is_dir()
            assert (target / "tools").is_dir()
            assert (target / "tests").is_dir()

    @given(product_name=product_names)
    @settings(max_examples=10, deadline=None)
    def test_init_creates_manifest(self, product_name: str):
        """Init always creates a valid sync manifest."""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "product"
            target.mkdir()

            run_init(str(target), product_name)

            manifest_path = target / ".prawduct" / "sync-manifest.json"
            assert manifest_path.exists()

            manifest = json.loads(manifest_path.read_text())
            assert manifest["product_name"] == product_name
            assert "files" in manifest
            assert "format_version" in manifest

    @given(product_name=product_names)
    @settings(max_examples=10, deadline=None)
    def test_init_creates_claude_md(self, product_name: str):
        """Init always creates a CLAUDE.md with block markers."""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "product"
            target.mkdir()

            run_init(str(target), product_name)

            claude_md = target / "CLAUDE.md"
            assert claude_md.exists()
            content = claude_md.read_text()
            assert BLOCK_BEGIN in content
            assert BLOCK_END in content


# =============================================================================
# Property: init substitutes product name everywhere
# =============================================================================


class TestInitSubstitution:
    @given(product_name=product_names)
    @settings(max_examples=10, deadline=None)
    def test_no_unreplaced_placeholders(self, product_name: str):
        """After init, no file contains unreplaced {{PRODUCT_NAME}} placeholders."""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "product"
            target.mkdir()

            run_init(str(target), product_name)

            for f in target.rglob("*"):
                if not f.is_file():
                    continue
                if f.suffix in (".pyc", ".so", ".bin"):
                    continue
                try:
                    content = f.read_text()
                except UnicodeDecodeError:
                    continue
                assert "{{PRODUCT_NAME}}" not in content, (
                    f"Unreplaced placeholder in {f.relative_to(target)}"
                )


# =============================================================================
# Property: init is idempotent
# =============================================================================


class TestInitIdempotency:
    @given(product_name=product_names)
    @settings(max_examples=5, deadline=None)
    def test_init_twice_produces_no_new_files(self, product_name: str):
        """Running init twice doesn't create additional files."""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "product"
            target.mkdir()

            run_init(str(target), product_name)
            files_after_first = set(
                f.relative_to(target) for f in target.rglob("*") if f.is_file()
            )

            run_init(str(target), product_name)
            files_after_second = set(
                f.relative_to(target) for f in target.rglob("*") if f.is_file()
            )

            new_files = files_after_second - files_after_first
            assert not new_files, f"Second init created new files: {new_files}"

    @given(product_name=product_names)
    @settings(max_examples=5, deadline=None)
    def test_init_twice_preserves_content(self, product_name: str):
        """Running init twice doesn't change file contents."""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "product"
            target.mkdir()

            run_init(str(target), product_name)

            snapshot = {}
            for f in target.rglob("*"):
                if f.is_file():
                    try:
                        snapshot[f.relative_to(target)] = f.read_text()
                    except UnicodeDecodeError:
                        snapshot[f.relative_to(target)] = f.read_bytes()

            run_init(str(target), product_name)

            for rel_path, original_content in snapshot.items():
                f = target / rel_path
                assert f.exists(), f"File disappeared: {rel_path}"
                try:
                    current = f.read_text()
                except UnicodeDecodeError:
                    current = f.read_bytes()
                assert current == original_content, (
                    f"Content changed in {rel_path} on second init"
                )

    @given(product_name=product_names)
    @settings(max_examples=5, deadline=None)
    def test_second_init_fewer_actions(self, product_name: str):
        """Second init reports fewer or equal actions than first."""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "product"
            target.mkdir()

            result1 = run_init(str(target), product_name)
            result2 = run_init(str(target), product_name)

            assert result2["files_written"] <= result1["files_written"], (
                f"Second init wrote more files ({result2['files_written']}) "
                f"than first ({result1['files_written']})"
            )
