"""Regression tests for tools/lib propagation to product repos.

product-hook imports tools/lib at runtime (regen-views, operator-verification,
advisories) but tools/lib was historically never shipped by init/sync, so
synced product repos crashed with `ModuleNotFoundError: No module named 'lib'`.
These tests pin the fix: lib ships on init, is enumerated dynamically from the
framework (no static per-module list to drift), and a fresh repo can run the
previously-crashing commands.

Cross-product evidence: hallucinote (blocked across ~6 PRs) and war-castle
(vendored lib manually as a workaround).
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

_FRAMEWORK = Path(__file__).resolve().parent.parent
_TOOL_PATH = _FRAMEWORK / "tools" / "prawduct-setup.py"

_spec = importlib.util.spec_from_file_location("prawduct_setup", _TOOL_PATH)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

run_init = _mod.run_init
run_validate = _mod.run_validate
run_migrate = _mod._lib_migrate_cmd.run_migrate
create_manifest = _mod.create_manifest
effective_managed_files = _mod._lib_core.effective_managed_files
MANAGED_FILES = _mod.MANAGED_FILES
MANAGED_DIRS = _mod._lib_core.MANAGED_DIRS

_HOOK = _FRAMEWORK / "tools" / "product-hook"


def _init_product(tmp_path: Path) -> Path:
    product = tmp_path / "product"
    result = run_init(str(product), "LibPropTest")
    assert result.get("files_written", 0) > 0, f"init failed: {result}"
    return product


class TestEffectiveManagedFiles:
    def test_empty_framework_returns_static_set(self, tmp_path: Path):
        """A framework dir without tools/lib adds nothing — preserves the
        static MANAGED_FILES set that unit tests rely on."""
        assert effective_managed_files(tmp_path) == MANAGED_FILES

    def test_enumerates_lib_modules(self, tmp_path: Path):
        """tools/lib/*.py become always_update managed entries, keyed off the
        framework dir so new modules are picked up without a code change."""
        libdir = tmp_path / "tools" / "lib"
        libdir.mkdir(parents=True)
        (libdir / "__init__.py").write_text("")
        (libdir / "core.py").write_text("x = 1\n")
        (libdir / "notpy.txt").write_text("ignored")

        result = effective_managed_files(tmp_path)

        assert "tools/lib/__init__.py" in result
        assert "tools/lib/core.py" in result
        assert "tools/lib/notpy.txt" not in result  # glob is *.py only
        assert result["tools/lib/core.py"]["strategy"] == "always_update"
        # Static entries are still present and unmodified.
        assert "tools/product-hook" in result

    def test_real_framework_includes_core(self):
        """Against the real framework, the package's own modules enumerate."""
        result = effective_managed_files(_FRAMEWORK)
        assert "tools/lib/core.py" in result
        assert "tools/lib/__init__.py" in result
        assert "tools/lib/views.py" in result


class TestInitShipsLib:
    def test_lib_present_after_init(self, tmp_path: Path):
        product = _init_product(tmp_path)
        libdir = product / "tools" / "lib"
        assert (libdir / "__init__.py").is_file()
        assert (libdir / "core.py").is_file()
        # Every framework module shipped.
        fw_modules = {p.name for p in (_FRAMEWORK / "tools" / "lib").glob("*.py")}
        shipped = {p.name for p in libdir.glob("*.py")}
        assert fw_modules == shipped

    def test_manifest_tracks_lib(self, tmp_path: Path):
        product = _init_product(tmp_path)
        manifest = json.loads(
            (product / ".prawduct" / "sync-manifest.json").read_text()
        )
        assert "tools/lib/core.py" in manifest["files"]
        assert manifest["files"]["tools/lib/core.py"]["strategy"] == "always_update"
        assert manifest["files"]["tools/lib/core.py"]["generated_hash"] is not None

    def test_reinit_is_idempotent(self, tmp_path: Path):
        """Shipping lib must not break init idempotency — a second init writes
        nothing (regression on the 'Created tools/lib/' every-time bug)."""
        product = _init_product(tmp_path)
        result = run_init(str(product), "LibPropTest")
        assert result.get("files_written", 0) == 0, result["actions"]


class TestSyncedRepoDoesNotCrash:
    def test_regen_views_no_module_error(self, tmp_path: Path):
        """The headline regression: regen-views must not ModuleNotFoundError in
        a product repo. (It may report a benign 'change-log not found'; we only
        assert the import crash is gone.)"""
        product = _init_product(tmp_path)
        proc = subprocess.run(
            [sys.executable, "tools/product-hook", "regen-views"],
            cwd=str(product),
            capture_output=True,
            text=True,
            timeout=30,
        )
        combined = proc.stdout + proc.stderr
        assert "ModuleNotFoundError" not in combined, combined
        assert "No module named 'lib'" not in combined, combined

    def test_check_operator_verification_no_module_error(self, tmp_path: Path):
        product = _init_product(tmp_path)
        proc = subprocess.run(
            [sys.executable, "tools/product-hook", "check-operator-verification"],
            cwd=str(product),
            capture_output=True,
            text=True,
            timeout=30,
        )
        combined = proc.stdout + proc.stderr
        assert "ModuleNotFoundError" not in combined, combined


def _run_hook(product: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "tools/product-hook", *args],
        cwd=str(product),
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestGuardsWhenLibAbsent:
    """The whole point of the import guards: a repo that predates lib
    propagation degrades gracefully instead of crashing. Simulated by removing
    tools/lib after init (an old un-synced repo)."""

    def _product_without_lib(self, tmp_path: Path) -> Path:
        product = _init_product(tmp_path)
        shutil.rmtree(product / "tools" / "lib")
        return product

    def test_regen_views_fails_open_with_note(self, tmp_path: Path):
        product = self._product_without_lib(tmp_path)
        proc = _run_hook(product, "regen-views")
        assert proc.returncode == 0, proc.stderr
        assert "ModuleNotFoundError" not in (proc.stdout + proc.stderr)
        assert "tools/lib" in proc.stderr

    def test_check_operator_verification_fails_open(self, tmp_path: Path):
        product = self._product_without_lib(tmp_path)
        proc = _run_hook(product, "check-operator-verification")
        # Fail OPEN: a gate that can't load its queue must not block /pr.
        assert proc.returncode == 0, proc.stderr
        assert "ModuleNotFoundError" not in (proc.stdout + proc.stderr)

    def test_accept_operator_verification_fails_closed(self, tmp_path: Path):
        product = self._product_without_lib(tmp_path)
        proc = _run_hook(product, "accept-operator-verification", "rationale")
        # Honest failure: a mutating command must not claim success absent lib.
        assert proc.returncode == 1
        assert "ModuleNotFoundError" not in (proc.stdout + proc.stderr)
        assert "tools/lib" in proc.stderr


class TestValidateChecksLib:
    def _lib_check(self, product: Path) -> dict | None:
        result = run_validate(str(product))
        for check in result["checks"]:
            if check["name"] == "hook_library":
                return check
        return None

    def test_validate_passes_with_lib(self, tmp_path: Path):
        product = _init_product(tmp_path)
        check = self._lib_check(product)
        assert check is not None and check["status"] == "pass"

    def test_validate_fails_without_lib(self, tmp_path: Path):
        product = _init_product(tmp_path)
        shutil.rmtree(product / "tools" / "lib")
        check = self._lib_check(product)
        assert check is not None and check["status"] == "fail"


class TestMigrateShipsLib:
    def test_migrate_restores_lib(self, tmp_path: Path):
        """run_migrate must install tools/lib (symmetry with init) so migrated
        v4 repos aren't left in the degraded hook-present/lib-absent state."""
        product = _init_product(tmp_path)
        shutil.rmtree(product / "tools" / "lib")
        run_migrate(str(product), "LibPropTest")
        assert (product / "tools" / "lib" / "core.py").is_file()
        assert (product / "tools" / "lib" / "__init__.py").is_file()
