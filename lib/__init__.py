"""
prawduct plugin lib — governance subset of the framework's tools/lib.

v2.0.0 plugin distribution: the plugin ships only the *governance* modules the
runtime hook (`bin/prawduct-hook`) needs — critic-mode inference,
operator-verification, derived views, the post-sync advisory CLI/store, and the
learnings-lifecycle audit. The file-sync *transport* modules (`sync_cmd`,
`migrate_cmd`, `init_cmd`, `validate_cmd`, `views_cmd`) are deliberately NOT
bundled: the plugin is dev-time governance, not a sync engine (design §2, §7;
build-plan Chunk 5 "Exclude sync-only machinery from the plugin runtime").

Parity (Chunk 5 + Chunk 13): seven modules — `core`, `critic_mode`, `views`,
`advisory_cmd`, `advisory_store`, `backlog_probes`, `audit_learnings_cmd` — are
byte-identical copies of their `tools/lib/` counterparts, locked by a parity
test so they cannot drift during Phase-1 coexistence. `audit_learnings_cmd`
joined this set in Chunk 13 (it is pure governance — stdlib-only, operates on
the consumer's own `learnings.md`, zero sync coupling — and was mis-grouped with
the transport modules in Chunk 5). `operator_verification` is bundled but
**intentionally diverged** from `tools/lib/` (its user-facing hints name the
plugin-native enable / `prawduct-hook verify-operator-verification` path, not
the frozen 1.x `prawduct-setup` path), so it is excluded from the byte-parity
lock. When file-sync is fully removed (backlog `MIG-M4-REMOVE`, post-2.0.0), the
remaining duplication collapses.
"""

# Core utilities and constants (governance dependency — critic_mode/views import it)
from .core import (  # noqa: F401
    BLOCK_BEGIN,
    BLOCK_END,
    BUILD_PLAN_POINTER_KEY,
    DEFAULT_BUILD_PLAN_REL,
    FILE_RENAMES,
    FRAMEWORK_DIR,
    GITIGNORE_ENTRIES,
    MANAGED_FILES,
    PRAWDUCT_VERSION,
    SKILL_PLACEMENTS,
    TEMPLATES_DIR,
    resolve_build_plan_path,
    read_str_yaml_key,
    V1_GITIGNORE_ENTRIES,
    V1_SESSION_FILES,
    V3_GITIGNORE_ENTRIES,
    V4_GITIGNORE_ENTRIES,
    _resolve_framework_dir,
    _try_pull_framework,
    compute_block_hash,
    compute_hash,
    copy_hook,
    create_manifest,
    detect_version,
    ensure_dir,
    extract_block,
    infer_product_name,
    load_json,
    log,
    merge_settings,
    render_template,
    replace_settings,
    untrack_gitignored_files,
    update_gitignore,
    write_template,
    write_template_overwrite,
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
