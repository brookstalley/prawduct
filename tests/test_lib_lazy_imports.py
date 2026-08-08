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
#
# `lib.views` was a member and served as the positive control below. It was
# deleted with the derived-view machinery, so the control moved to
# `lib.advisory_store` — a heavy module with no retirement in view. **The list
# must keep at least one member that something imports directly**, or
# `test_the_probe_can_fail` has nothing to prove the probe with and every
# empty-set assertion here goes vacuous rather than red.
HEAVY_SUBMODULES = (
    "lib.advisory_store",
    "lib.operator_verification",
    "lib.critic_mode",
    "lib.audit_learnings_cmd",
)

# The control's subject, named once so the two places that must agree — the
# import statement and the membership assertion — cannot drift apart.
POSITIVE_CONTROL = "lib.advisory_store"


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

    def test_the_probe_can_fail(self):
        """The positive control, without which every assertion above is vacuous.

        Each test here asserts an empty set. An empty set is also what a probe
        that silently stopped working returns — a renamed module, a changed
        `sys.modules` key, a subprocess whose import failed and printed nothing.
        So one test imports a heavy module directly and requires the probe to
        SEE it. If this fails, none of the greens above mean anything.

        The subject is `POSITIVE_CONTROL` rather than a literal, because the
        previous control (`lib.views`) was deleted by the work that retired
        derived views — and a control whose subject can vanish is a control that
        can go vacuous without anyone editing this file.
        """
        dragged = _clean_import_probe(f"import {POSITIVE_CONTROL}", HEAVY_SUBMODULES)
        assert POSITIVE_CONTROL in dragged, (
            "the probe reported no heavy module after importing one directly — "
            f"it is not measuring what these tests claim (got {sorted(dragged)})"
        )

    def test_the_positive_control_is_actually_probed(self):
        """The control's subject must be in the probed set.

        `_clean_import_probe` only reports modules it was ASKED about, so a
        `POSITIVE_CONTROL` missing from `HEAVY_SUBMODULES` would make the test
        above fail confusingly rather than guard anything — and a future edit
        that drops the control's module from the tuple is exactly the edit that
        would do it.
        """
        assert POSITIVE_CONTROL in HEAVY_SUBMODULES

    def test_plan_index_does_not_drag_in_heavy(self):
        """`plan_index` is imported at MODULE scope by `buildplan_refs`.

        That is a deliberate change from its predecessor `views`, which had to
        be lazy because it also carried the change-log parser and is now deleted.
        The module-scope import is only defensible while `plan_index` stays
        cheap, and "cheap" is
        a property that decays silently — one convenience import inside it bills
        every SessionStart and every Stop. Probed at the module itself so the
        regression is attributed here rather than at the three consumers.
        """
        dragged = _clean_import_probe("import lib.plan_index", HEAVY_SUBMODULES)
        assert dragged == set(), (
            f"importing lib.plan_index pulled in heavy modules {sorted(dragged)} — "
            "it is on the session hot path at module scope and must stay light"
        )

    def test_ledger_does_not_drag_in_heavy(self):
        """`ledger` reaches `plan_index.parse_build_plan_frontmatter_scope` for
        its scope fallback. A module-scope import there would pull that module
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

        `buildplan_refs` resolves a branch's plan, which `briefing`
        (SessionStart) and `gates` (Stop) both reach through a module-scope
        import — so a heavy import here bills every session. It used to reach
        the now-deleted `views` for that and had to do so lazily; it now imports
        `plan_index` at module scope, which is only safe while that module stays
        light (probed separately above). The `ledger`/`telemetry` probes were added in the
        same work that let a heavy import land at the *hotter* consumer, so the
        two importers are probed alongside the module itself rather than trusted
        to inherit its discipline.
        """
        dragged = _clean_import_probe(f"import lib.{module}", HEAVY_SUBMODULES)
        assert dragged == set(), (
            f"importing lib.{module} pulled in heavy modules {sorted(dragged)} — "
            "import them inside the function that needs them"
        )

    def test_accessing_one_flat_name_loads_only_its_owner(self):
        # Touching a core-owned name must not import advisory_store/critic_mode/etc.
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
        # `from lib import plan_index` / `waivers` — native submodule access.
        # `views` was the first of these until it was deleted; both of its
        # successors took its place, so both are exercised here.
        from lib import change_log, plan_index, waivers

        assert change_log.__name__ == "lib.change_log"
        assert plan_index.__name__ == "lib.plan_index"
        assert waivers.__name__ == "lib.waivers"

    def test_bare_attribute_access_resolves_every_submodule_export(self):
        """The form `_SUBMODULE_EXPORTS` exists FOR — `lib.<name>` with no prior
        submodule import — asserted over the whole set rather than a sample, so
        adding a member without it working fails here."""
        import lib

        for name in sorted(lib._SUBMODULE_EXPORTS):
            assert getattr(lib, name).__name__ == f"lib.{name}"

    def test_unknown_attribute_raises(self):
        import lib

        with pytest.raises(AttributeError):
            lib.this_name_does_not_exist  # noqa: B018

    def test_dir_includes_lazy_exports(self):
        import lib

        names = set(dir(lib))
        assert EXPECTED_FLAT_EXPORTS <= names
        assert {"change_log", "plan_index", "waivers"} <= names
