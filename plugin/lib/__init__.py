"""
prawduct plugin lib — the dev-time governance library the runtime hook uses.

The plugin ships only *governance* modules `bin/prawduct-hook` needs —
critic-mode inference, operator-verification, the advisory
CLI/store, the learnings layout and its relayout — plus the plugin-native onboarding
(`init_product`) and file-sync→plugin migration (`migrate_plugin`). The plugin
is dev-time governance, not a sync engine (design §2, §7).

History: through v2.0.x several of these modules were byte-identical copies of a
frozen `tools/lib/` (the file-sync engine), kept in lockstep by a parity test
during the file-sync→plugin transition. The file-sync engine was retired in M4
(`MIG-M4-REMOVE`); `lib/` is now the sole copy and the parity scaffolding is
gone. `migrate_plugin` still references the `tools/` + `tools/lib/` paths a
*consuming* repo carries — those are the file-sync residue it removes during a
repo's migration onto the plugin, not framework code.

Import discipline (STH-9V4K, hook decomposition): this package re-exports a
flat API (`from lib import infer_mode`, `from lib import GITIGNORE_ENTRIES`, …)
but does NOT eager-import the submodules that back it. A module-level
``__getattr__`` (PEP 562) lazy-imports the owning submodule only when a name is
first accessed, then caches it in this module's globals. The payoff is on the
hook's hot path: `bin/prawduct-hook` is deliberately lib-independent at its top
level and imports lib lazily inside functions, "robust even on an incomplete
plugin install." Before this change, `from lib import <anything>` dragged in
every heavy module (advisory_store, critic_mode, operator_verification, …) via eager
re-exports (~34ms, and any one heavy module's import error broke them all).
Now `from lib import gitstate` (or any leaf) loads only that submodule —
isolated and ~1ms — so session start never couples to unrelated modules.

Submodule access is unaffected: `from lib import plan_index`, `from lib import
gitstate`, and `from lib.advisory_store import run_sync_advisories` all resolve
natively through the import system (Python imports the submodule when the
attribute is absent), so they need no entry below.
"""

import importlib
from typing import Any

# Flat-API name -> the submodule that defines it. Accessing `lib.<name>` (or
# `from lib import <name>`) lazy-imports that submodule on first use. Keep this
# map in sync with each submodule's public surface; `tests/test_lib_lazy_imports.py`
# asserts every listed name still resolves AND that importing a leaf submodule
# does not drag in a heavy one.
_FLATTENED_EXPORTS: dict[str, str] = {
    # Core utilities and constants (governance dependency — critic_mode/change_log import it)
    "BLOCK_BEGIN": "core",
    "BLOCK_END": "core",
    "BUILD_PLAN_POINTER_KEY": "core",
    "DEFAULT_BUILD_PLAN_REL": "core",
    "FRAMEWORK_DIR": "core",
    "GITIGNORE_ENTRIES": "core",
    "MANAGED_FILES": "core",
    "PRAWDUCT_VERSION": "core",
    "TEMPLATES_DIR": "core",
    "resolve_build_plan_path": "core",
    "read_str_yaml_key": "core",
    "extract_block": "core",
    "log": "core",
    "render_template": "core",
    "update_gitignore": "core",
    "write_template": "core",
    # Post-sync advisory infrastructure (store + registry + diff)
    "AdvisoryCandidate": "advisory_store",
    "Codebase": "advisory_store",
    "ProjectState": "advisory_store",
    "clear_registry": "advisory_store",
    "compute_id": "advisory_store",
    "dismiss": "advisory_store",
    "load_project_state": "advisory_store",
    "make_codebase": "advisory_store",
    "read_store": "advisory_store",
    "reconcile": "advisory_store",
    "register_probe": "advisory_store",
    "resolve": "advisory_store",
    "run_all_probes": "advisory_store",
    "run_sync_advisories": "advisory_store",
    "undismiss": "advisory_store",
    "write_store": "advisory_store",
    # Post-sync advisory management CLI (/prawduct:advisory)
    "dismiss_advisory": "advisory_cmd",
    "list_advisories": "advisory_cmd",
    "resolve_advisory": "advisory_cmd",
    "show_advisory": "advisory_cmd",
    "undismiss_advisory": "advisory_cmd",
    # Critic mode inference (no-arg /critic picks mode from state)
    "infer_mode": "critic_mode",
    # Operator-verification queue (pre-merge human-verification gate)
    "VerificationEntry": "operator_verification",
    "count_pending": "operator_verification",
    "format_operator_verification": "operator_verification",
    "is_operator_verification_required": "operator_verification",
    "mark_accepted": "operator_verification",
    "mark_verified": "operator_verification",
    "parse_operator_verification": "operator_verification",
    "pending_entries": "operator_verification",
    "run_accept_pending": "operator_verification",
    "run_check_operator_verification": "operator_verification",
    "run_verify_entry": "operator_verification",
}

# Submodules that must resolve under BARE attribute access (`lib.waivers` with
# no prior `import lib.waivers`). `from lib import waivers` resolves natively
# through the import system and needs no entry; this set is only for the
# attribute form.
#
# `views` was a member until the derived-view machinery was retired. Its two
# successors both take its place rather than one of them: a consumer reaching
# for `lib.views` was reaching for either the change-log parser or the plan
# resolver, and they now live in `change_log` and `plan_index` respectively, so
# leaving one out would make the attribute form work for half of what the
# retired name covered. That is the whole membership rule — no module is here
# for historical reasons alone.
_SUBMODULE_EXPORTS: frozenset[str] = frozenset({"change_log", "plan_index", "waivers"})


def __getattr__(name: str) -> Any:
    """Lazy-resolve a flat-API name to its owning submodule (PEP 562).

    Called only when ``name`` is absent from this module's namespace, so the
    first access pays one ``import_module`` and the result is cached in globals
    (subsequent accesses skip ``__getattr__`` entirely). Unknown names raise
    ``AttributeError`` exactly like a normal missing attribute.
    """
    if name in _SUBMODULE_EXPORTS:
        module = importlib.import_module(f"{__name__}.{name}")
        globals()[name] = module
        return module
    submodule = _FLATTENED_EXPORTS.get(name)
    if submodule is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(importlib.import_module(f"{__name__}.{submodule}"), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Include the lazily-exported names in ``dir(lib)`` for introspection."""
    return sorted({*globals(), *_FLATTENED_EXPORTS, *_SUBMODULE_EXPORTS})
