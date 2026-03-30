#!/usr/bin/env python3
"""
prawduct-setup.py — Unified tool for Prawduct product repos.

Handles initialization, migration, sync, and validation of product repos.
Replaces the former prawduct-init.py, prawduct-migrate.py, and prawduct-sync.py.

Subcommands:
  setup     Auto-detect repo state and init/migrate/sync as needed
  sync      Sync product repo with framework template updates
  validate  Health check — verify repo structure and configuration

Usage:
  python3 tools/prawduct-setup.py setup <target> [--name NAME]
  python3 tools/prawduct-setup.py sync <product_dir> [--framework-dir <dir>]
  python3 tools/prawduct-setup.py validate <target> [--json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure tools/ is on sys.path so `from lib import ...` works when this
# script is loaded via importlib from other directories (tests, shims).
_tools_dir = str(Path(__file__).resolve().parent)
if _tools_dir not in sys.path:
    sys.path.insert(0, _tools_dir)

# Re-export everything from lib for backward compatibility.
# Tests and shim scripts import this module via importlib and access
# functions as module attributes — all public names must be available here.
#
# Expose lib submodules so tests can monkeypatch the correct target
# (e.g., _mod._lib_core.subprocess instead of _mod.subprocess).
import lib.core as _lib_core  # noqa: F401
import lib.sync_cmd as _lib_sync_cmd  # noqa: F401
import lib.migrate_cmd as _lib_migrate_cmd  # noqa: F401

from lib import (  # noqa: F401
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
    _bootstrap_manifest,
    _resolve_framework_dir,
    _try_pull_framework,
    add_block_markers,
    apply_renames,
    archive_v1_dirs,
    clean_gitignore,
    clean_v1_session_files,
    compute_block_hash,
    compute_hash,
    copy_hook,
    create_manifest,
    delete_v1_files,
    detect_version,
    ensure_dir,
    extract_block,
    generate_sync_manifest,
    infer_product_name,
    load_json,
    log,
    merge_settings,
    migrate_backlog,
    migrate_change_log,
    migrate_project_state_v5,
    migrate_v4_to_v5,
    render_template,
    replace_settings,
    run_init,
    run_migrate,
    run_sync,
    run_validate,
    split_learnings_v5,
    update_gitignore,
    upgrade_manifest_strategy,
    write_template,
    write_template_overwrite,
)


# =============================================================================
# CLI
# =============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prawduct product repo setup, sync, and validation.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- setup ---
    setup_parser = subparsers.add_parser(
        "setup",
        help="Auto-detect repo state and init/migrate/sync as needed",
    )
    setup_parser.add_argument("target_dir", help="Target directory for the product repo")
    setup_parser.add_argument("--name", default=None, help="Product name")
    setup_parser.add_argument("--json", action="store_true", dest="json_mode", help="JSON output only")
    setup_parser.add_argument("--force", action="store_true", help="Overwrite locally-edited files with new template versions")

    # --- sync ---
    sync_parser = subparsers.add_parser(
        "sync",
        help="Sync product repo with framework template updates",
    )
    sync_parser.add_argument("product_dir", help="Product repo directory")
    sync_parser.add_argument("--framework-dir", default=None, help="Framework directory (overrides manifest and env var)")
    sync_parser.add_argument("--json", action="store_true", dest="json_mode", help="JSON output only")
    sync_parser.add_argument("--no-pull", action="store_true", dest="no_pull", help="Skip git pull/fetch of the framework repo")
    sync_parser.add_argument("--force", action="store_true", help="Overwrite locally-edited files with new template versions")

    # --- validate ---
    validate_parser = subparsers.add_parser(
        "validate",
        help="Health check — verify repo structure and configuration",
    )
    validate_parser.add_argument("target_dir", help="Product repo directory to validate")
    validate_parser.add_argument("--json", action="store_true", dest="json_mode", help="JSON output only")

    args = parser.parse_args()

    if args.command == "setup":
        target = os.path.abspath(args.target_dir)
        if not os.path.isdir(target):
            os.makedirs(target, exist_ok=True)

        name = args.name

        # Detect state and route
        has_prawduct = os.path.isdir(os.path.join(target, ".prawduct"))
        if has_prawduct:
            version = detect_version(Path(target))
        else:
            version = "unknown"

        if version == "unknown":
            # New, non-prawduct, or partial .prawduct — init
            if name is None:
                name = Path(target).name
            result = run_init(target, name)
        elif version in ("v1", "v3", "v4", "partial"):
            result = run_migrate(target, name)
        elif version == "v5":
            result = run_sync(target, force=args.force)
        else:
            result = {"error": f"Unrecognized state: {version}"}

        if args.json_mode:
            print(json.dumps(result, indent=2))
        else:
            if "error" in result:
                log(f"Error: {result['error']}")
                return 1
            actions = result.get("actions", [])
            notes = result.get("notes", [])
            if actions:
                log(f"Setup complete: {target}")
                for action in actions:
                    log(f"  + {action}")
            else:
                log(f"Already up to date: {target}")
            if notes:
                for note in notes:
                    log(f"  * {note}")
            log("")
            log("Next: Open this directory in a new Claude Code session for full governance.")
        return 0

    elif args.command == "sync":
        result = run_sync(args.product_dir, args.framework_dir, no_pull=args.no_pull, force=args.force)

        if args.json_mode:
            print(json.dumps(result, indent=2))
        else:
            if not result["synced"]:
                if result["reason"] not in ("no manifest", "framework not found", "no updates needed"):
                    log(f"Sync skipped: {result['reason']}")
            else:
                log(f"Synced {result['product_dir']}")
                for action in result["actions"]:
                    log(f"  + {action}")
            for note in result.get("notes", []):
                log(f"  * {note}")
        return 0

    elif args.command == "validate":
        result = run_validate(args.target_dir)

        if args.json_mode:
            print(json.dumps(result, indent=2))
        else:
            status_icon = {"healthy": "OK", "degraded": "WARN", "broken": "FAIL"}
            log(f"Prawduct health: {status_icon.get(result['overall'], '?')} ({result['overall']})")
            log(f"  Version: {result['version']}")
            for check in result["checks"]:
                icon = {"pass": "+", "warn": "~", "fail": "!"}
                log(f"  {icon.get(check['status'], '?')} {check['name']}: {check['detail']}")
            if result["needs_restart"]:
                log("")
                log("  RESTART NEEDED: Some files will update on next sync")
            if result["recommendations"]:
                log("")
                for rec in result["recommendations"]:
                    log(f"  -> {rec}")
        return 0 if result["overall"] != "broken" else 1

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
