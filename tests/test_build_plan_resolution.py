"""Tests for active build-plan resolution (v1.6.0 Chunk 06).

The build-plan-consuming tooling resolves the active plan via an optional
`active_build_plan:` pointer in project-state.yaml, falling back to the
conventional `artifacts/build-plan.md`. The resolver lives in tools/lib/core.py
and is mirrored inline in tools/product-hook (standalone in product repos). A
parity test pins the two implementations together, like the GITIGNORE mirror.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent

# lib resolver via prawduct-setup importlib
_spec = importlib.util.spec_from_file_location("prawduct_setup", _ROOT / "tools" / "prawduct-setup.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
resolve_build_plan_path = _mod.resolve_build_plan_path
read_str_yaml_key = _mod.read_str_yaml_key
BUILD_PLAN_POINTER_KEY = _mod.BUILD_PLAN_POINTER_KEY
DEFAULT_BUILD_PLAN_REL = _mod.DEFAULT_BUILD_PLAN_REL

# product-hook inline mirror via SourceFileLoader (extensionless shebang script)
_hook_loader = importlib.machinery.SourceFileLoader("product_hook_res", str(_ROOT / "tools" / "product-hook"))
_hook_spec = importlib.util.spec_from_loader("product_hook_res", _hook_loader)
_hook = importlib.util.module_from_spec(_hook_spec)
_hook_loader.exec_module(_hook)


def _prawduct(tmp_path: Path, state: str = "") -> Path:
    p = tmp_path / ".prawduct"
    (p / "artifacts").mkdir(parents=True)
    (p / "project-state.yaml").write_text(state)
    return p


class TestResolveBuildPlanPath:
    def test_pointer_set_returns_pointed_file(self, tmp_path: Path):
        prawduct = _prawduct(tmp_path, "active_build_plan: artifacts/v1.6.0-foo-plan.md\n")
        resolved = resolve_build_plan_path(prawduct)
        assert resolved == prawduct / "artifacts" / "v1.6.0-foo-plan.md"

    def test_pointer_absent_falls_back_to_default(self, tmp_path: Path):
        prawduct = _prawduct(tmp_path, "views_enabled: true\n")
        resolved = resolve_build_plan_path(prawduct)
        assert resolved == prawduct / "artifacts" / "build-plan.md"

    def test_no_project_state_falls_back_to_default(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        resolved = resolve_build_plan_path(prawduct)
        assert resolved == prawduct / "artifacts" / "build-plan.md"

    def test_pointer_to_missing_file_still_returned(self, tmp_path: Path):
        # The resolver returns the pointed path even if it doesn't exist;
        # callers treat a missing plan as "no active build plan".
        prawduct = _prawduct(tmp_path, "active_build_plan: artifacts/gone-plan.md\n")
        resolved = resolve_build_plan_path(prawduct)
        assert resolved == prawduct / "artifacts" / "gone-plan.md"
        assert not resolved.is_file()

    def test_default_constant(self):
        assert DEFAULT_BUILD_PLAN_REL == "artifacts/build-plan.md"
        assert BUILD_PLAN_POINTER_KEY == "active_build_plan"


class TestReadStrYamlKey:
    def test_reads_top_level_scalar(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("active_build_plan: artifacts/x-plan.md\nother: 1\n")
        assert read_str_yaml_key(p, "active_build_plan") == "artifacts/x-plan.md"

    def test_strips_quotes_and_comments(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text('active_build_plan: "artifacts/y-plan.md"  # the active one\n')
        assert read_str_yaml_key(p, "active_build_plan") == "artifacts/y-plan.md"

    def test_ignores_nested_key(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("nested:\n  active_build_plan: artifacts/z-plan.md\n")
        assert read_str_yaml_key(p, "active_build_plan") is None

    def test_missing_key_returns_none(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("views_enabled: true\n")
        assert read_str_yaml_key(p, "active_build_plan") is None

    def test_missing_file_returns_none(self, tmp_path: Path):
        assert read_str_yaml_key(tmp_path / "nope.yaml", "active_build_plan") is None


class TestProductHookMirrorParity:
    """The inline product-hook resolver must match the lib resolver on the same
    inputs (same discipline as the GITIGNORE_ENTRIES mirror test)."""

    def test_constants_match(self):
        assert _hook._BUILD_PLAN_POINTER_KEY == BUILD_PLAN_POINTER_KEY
        assert _hook._DEFAULT_BUILD_PLAN_REL == DEFAULT_BUILD_PLAN_REL

    def test_pointer_set_parity(self, tmp_path: Path):
        prawduct = _prawduct(tmp_path, "active_build_plan: artifacts/v1.6.0-foo-plan.md\n")
        assert _hook._resolve_build_plan_path(prawduct) == resolve_build_plan_path(prawduct)

    def test_pointer_absent_parity(self, tmp_path: Path):
        prawduct = _prawduct(tmp_path, "views_enabled: true\n")
        assert _hook._resolve_build_plan_path(prawduct) == resolve_build_plan_path(prawduct)

    def test_str_key_parity(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text('active_build_plan: "artifacts/y-plan.md"  # c\n')
        assert _hook._read_str_yaml_key(p, "active_build_plan") == read_str_yaml_key(p, "active_build_plan")
