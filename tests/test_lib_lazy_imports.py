"""Lazy-import discipline for the ``lib`` package (STH-9V4K, Chunk 1).

``lib/__init__.py`` re-exports a flat API (``from lib import infer_mode``,
``from lib import GITIGNORE_ENTRIES``, …) via a PEP-562 ``__getattr__`` that
lazy-imports the owning submodule on first access — it must NOT eager-import the
heavy submodules. This guards the hook's hot path: ``bin/prawduct-hook`` imports
lib lazily inside functions and is "robust even on an incomplete plugin
install"; eager re-exports would couple every ``from lib import <leaf>`` to every
heavy module's importability (and cost ~34ms). These tests pin both halves of
the contract: the isolation property AND the preserved flat API.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent / "plugin"

# The flat API the package must keep resolving via ``from lib import <name>``
# and ``lib.<name>``. Hard-coded as the contract (not derived from the
# implementation's map) so that dropping an export from ``__init__`` fails here.
EXPECTED_FLAT_EXPORTS = frozenset({
    # core
    "BLOCK_BEGIN", "BLOCK_END", "BUILD_PLAN_POINTER_KEY", "DEFAULT_BUILD_PLAN_REL",
    "FRAMEWORK_DIR", "GITIGNORE_ENTRIES", "MANAGED_FILES", "PRAWDUCT_VERSION",
    "TEMPLATES_DIR", "resolve_build_plan_path", "read_str_yaml_key", "extract_block",
    "log", "render_template", "update_gitignore", "write_template",
    # advisory_store
    "AdvisoryCandidate", "Codebase", "ProjectState", "clear_registry", "compute_id",
    "dismiss", "load_project_state", "make_codebase", "read_store", "reconcile",
    "register_probe", "resolve", "run_all_probes", "run_sync_advisories", "undismiss",
    "write_store",
    # advisory_cmd
    "dismiss_advisory", "list_advisories", "resolve_advisory", "show_advisory",
    "undismiss_advisory",
    # critic_mode
    "infer_mode",
    # audit_learnings_cmd
    "run_audit_learnings",
    # operator_verification
    "VerificationEntry", "count_pending", "format_operator_verification",
    "is_operator_verification_required", "mark_accepted", "mark_verified",
    "parse_operator_verification", "pending_entries", "run_accept_pending",
    "run_check_operator_verification", "run_verify_entry",
})

# Heavy submodules that must NOT be pulled in by importing a leaf.
HEAVY_SUBMODULES = (
    "lib.advisory_store",
    "lib.views",
    "lib.operator_verification",
    "lib.critic_mode",
    "lib.audit_learnings_cmd",
)


def _clean_import_probe(import_stmt: str, probe_modules: tuple[str, ...]) -> set[str]:
    """Run ``import_stmt`` in a fresh interpreter; return which ``probe_modules``
    ended up in ``sys.modules``. A clean process is required because ``sys.modules``
    is process-global and the in-test interpreter has already loaded heavy modules."""
    code = (
        "import sys\n"
        f"{import_stmt}\n"
        f"print(','.join(m for m in {probe_modules!r} if m in sys.modules))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout.strip()
    return set(out.split(",")) if out else set()


class TestLazyIsolation:
    """Importing a leaf submodule must not eager-load the heavy ones."""

    def test_leaf_submodule_does_not_drag_in_heavy(self):
        dragged = _clean_import_probe("import lib.core", HEAVY_SUBMODULES)
        assert dragged == set(), (
            f"importing lib.core pulled in heavy modules {sorted(dragged)} — "
            "lib/__init__.py must not eager-import them (PEP-562 __getattr__)"
        )

    def test_package_import_alone_is_light(self):
        # `import lib` (the package, no submodule) must also stay light — the
        # eager re-export blocks are what this chunk removed.
        dragged = _clean_import_probe("import lib", HEAVY_SUBMODULES)
        assert dragged == set(), (
            f"`import lib` pulled in {sorted(dragged)} — the package __init__ must "
            "not eager-import heavy submodules"
        )

    def test_ledger_does_not_drag_in_heavy(self):
        """`ledger` reaches `views._parse_build_plan_frontmatter_scope` for its
        scope fallback. A module-scope import there would pull a HEAVY_SUBMODULE
        into every consumer of `ledger`; the existing probes only cover `lib`
        and `lib.core`, so the coupling would have re-landed green."""
        dragged = _clean_import_probe("import lib.ledger", HEAVY_SUBMODULES)
        assert dragged == set(), (
            f"importing lib.ledger pulled in heavy modules {sorted(dragged)} — "
            "import them inside the function that needs them"
        )

    def test_telemetry_does_not_drag_in_heavy(self):
        """`telemetry` module-scope-imports `ledger`, so it inherits whatever
        `ledger` eager-loads. Probed separately because the inheritance is the
        part nobody looks at."""
        dragged = _clean_import_probe("import lib.telemetry", HEAVY_SUBMODULES)
        assert dragged == set(), (
            f"importing lib.telemetry pulled in heavy modules {sorted(dragged)} — "
            "it inherits ledger's module-scope imports"
        )

    @pytest.mark.parametrize("module", ["buildplan_refs", "briefing", "gates"])
    def test_the_hot_path_does_not_drag_in_heavy(self, module: str):
        """The SessionStart/Stop path, probed at all three of its modules.

        `buildplan_refs` reaches the same `views` helper `ledger` does, for the
        same scope fallback — but here the cost is not hypothetical: `briefing`
        (SessionStart) and `gates` (Stop) both import `buildplan_refs` at module
        scope, so a module-scope `views` import bills every session for a parse
        most of them never reach. The `ledger`/`telemetry` probes above were
        added in the same work that let this land at the *hotter* consumer, so
        the two importers are probed alongside the module itself rather than
        trusted to inherit its discipline.
        """
        dragged = _clean_import_probe(f"import lib.{module}", HEAVY_SUBMODULES)
        assert dragged == set(), (
            f"importing lib.{module} pulled in heavy modules {sorted(dragged)} — "
            "import them inside the function that needs them"
        )

    def test_accessing_one_flat_name_loads_only_its_owner(self):
        # Touching a core-owned name must not import advisory_store/views/etc.
        dragged = _clean_import_probe(
            "import lib; lib.GITIGNORE_ENTRIES", HEAVY_SUBMODULES
        )
        assert dragged == set(), (
            f"accessing lib.GITIGNORE_ENTRIES pulled in {sorted(dragged)} — "
            "__getattr__ must import only the owning submodule (core)"
        )


class TestFlatApiPreserved:
    """Every previously-eager export must still resolve, both forms."""

    def test_all_expected_names_resolve_via_attribute(self):
        import lib

        missing = [n for n in sorted(EXPECTED_FLAT_EXPORTS) if not hasattr(lib, n)]
        assert not missing, f"flat exports no longer resolve via lib.<name>: {missing}"

    def test_representative_from_imports(self):
        # Exercise the `from lib import X` form across each owning submodule.
        from lib import GITIGNORE_ENTRIES, infer_mode, run_audit_learnings  # noqa: F401
        from lib import run_sync_advisories, list_advisories, count_pending  # noqa: F401

        assert callable(infer_mode)
        assert isinstance(GITIGNORE_ENTRIES, list)

    def test_submodule_exports_resolve(self):
        # `from lib import views` / `waivers` — native submodule access.
        from lib import views, waivers

        assert views.__name__ == "lib.views"
        assert waivers.__name__ == "lib.waivers"

    def test_unknown_attribute_raises(self):
        import lib

        with pytest.raises(AttributeError):
            lib.this_name_does_not_exist  # noqa: B018

    def test_dir_includes_lazy_exports(self):
        import lib

        names = set(dir(lib))
        assert EXPECTED_FLAT_EXPORTS <= names
        assert {"views", "waivers"} <= names
