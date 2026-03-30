"""
prawduct lib — extracted modules from prawduct-setup.py.

Re-exports all public names for backward compatibility. Consumers that
import via importlib (tests, shim scripts) see the same namespace as before.
"""

# Core utilities and constants
from .core import (  # noqa: F401
    BLOCK_BEGIN,
    BLOCK_END,
    FILE_RENAMES,
    FRAMEWORK_DIR,
    GITIGNORE_ENTRIES,
    MANAGED_FILES,
    PRAWDUCT_VERSION,
    SKILL_PLACEMENTS,
    TEMPLATES_DIR,
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
    update_gitignore,
    write_template,
    write_template_overwrite,
)

# Init command
from .init_cmd import run_init  # noqa: F401

# Migration operations
from .migrate_cmd import (  # noqa: F401
    add_block_markers,
    archive_v1_dirs,
    clean_gitignore,
    clean_v1_session_files,
    delete_v1_files,
    generate_sync_manifest,
    migrate_backlog,
    migrate_change_log,
    migrate_project_state_v5,
    run_migrate,
    split_learnings_v5,
    upgrade_manifest_strategy,
)

# Sync operations
from .sync_cmd import (  # noqa: F401
    _bootstrap_manifest,
    apply_renames,
    migrate_v4_to_v5,
    run_sync,
)

# Validate command
from .validate_cmd import run_validate  # noqa: F401
