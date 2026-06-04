"""
prawduct plugin lib — the dev-time governance library the runtime hook uses.

The plugin ships only *governance* modules `bin/prawduct-hook` needs —
critic-mode inference, operator-verification, derived views, the advisory
CLI/store, the learnings-lifecycle audit — plus the plugin-native onboarding
(`init_product`) and file-sync→plugin migration (`migrate_plugin`). The plugin
is dev-time governance, not a sync engine (design §2, §7).

History: through v2.0.x several of these modules were byte-identical copies of a
frozen `tools/lib/` (the file-sync engine), kept in lockstep by a parity test
during the file-sync→plugin transition. The file-sync engine was retired in M4
(`MIG-M4-REMOVE`); `lib/` is now the sole copy and the parity scaffolding is
gone. `migrate_plugin` still references the `tools/` + `tools/lib/` paths a
*consuming* repo carries — those are the file-sync residue it removes during a
repo's migration onto the plugin, not framework code.
"""

# Core utilities and constants (governance dependency — critic_mode/views import it)
from .core import (  # noqa: F401
    BLOCK_BEGIN,
    BLOCK_END,
    BUILD_PLAN_POINTER_KEY,
    DEFAULT_BUILD_PLAN_REL,
    FRAMEWORK_DIR,
    GITIGNORE_ENTRIES,
    MANAGED_FILES,
    PRAWDUCT_VERSION,
    TEMPLATES_DIR,
    resolve_build_plan_path,
    read_str_yaml_key,
    extract_block,
    log,
    render_template,
    update_gitignore,
    write_template,
)

# Post-sync advisory infrastructure (store + registry + diff)
from .advisory_store import (  # noqa: F401
    AdvisoryCandidate,
    Codebase,
    ProjectState,
    clear_registry,
    compute_id,
    dismiss,
    load_project_state,
    make_codebase,
    read_store,
    reconcile,
    register_probe,
    resolve,
    run_all_probes,
    run_sync_advisories,
    undismiss,
    write_store,
)

# Post-sync advisory management CLI (/prawduct:advisory)
from .advisory_cmd import (  # noqa: F401
    dismiss_advisory,
    list_advisories,
    resolve_advisory,
    show_advisory,
    undismiss_advisory,
)

# Critic mode inference (no-arg /critic picks mode from state)
from .critic_mode import infer_mode  # noqa: F401

# Learnings-lifecycle audit (/prawduct:doctor Audit-Learnings flow) — pure
# governance over the consumer's own learnings.md; plugin-native, no sync.
from .audit_learnings_cmd import run_audit_learnings  # noqa: F401

# Operator-verification queue (pre-merge human-verification gate)
from .operator_verification import (  # noqa: F401
    VerificationEntry,
    count_pending,
    format_operator_verification,
    is_operator_verification_required,
    mark_accepted,
    mark_verified,
    parse_operator_verification,
    pending_entries,
    run_accept_pending,
    run_check_operator_verification,
    run_verify_entry,
)

# Derived views (regen-views) — the hook calls `from lib import views`
from . import views  # noqa: F401

# Intentional-waiver pragma recognizer — the canary calls `from lib import waivers`
from . import waivers  # noqa: F401
