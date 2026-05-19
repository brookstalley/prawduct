#!/usr/bin/env python3
"""
prawduct-setup.py — Unified tool for Prawduct product repos.

Handles initialization, migration, sync, and validation of product repos.
Replaces the former prawduct-init.py, prawduct-migrate.py, and prawduct-sync.py.

Subcommands:
  setup     Auto-detect repo state and init/migrate/sync as needed
  sync      Sync product repo with framework template updates
  validate  Health check — verify repo structure and configuration
  views     Inspect derived views (Status / release-notes / scope-rollups);
            --refresh regenerates them from change-log tags

Usage:
  python3 tools/prawduct-setup.py setup <target> [--name NAME]
  python3 tools/prawduct-setup.py sync <product_dir> [--framework-dir <dir>]
  python3 tools/prawduct-setup.py validate <target> [--json]
  python3 tools/prawduct-setup.py views <product_dir> [--refresh] [--json]
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
    LearningEntry,
    _HISTORICAL_RENDER_DEPTH_CAP,
    _bootstrap_manifest,
    _match_historical_render,
    _resolve_framework_dir,
    _try_pull_framework,
    add_block_markers,
    apply_renames,
    archive_v1_dirs,
    audit_learnings,
    clean_gitignore,
    clean_v1_session_files,
    compute_block_hash,
    compute_hash,
    copy_hook,
    create_manifest,
    delete_v1_files,
    detect_version,
    enable_v1_4_coverage,
    enable_v1_4_settings_layout,
    enable_v1_4_views,
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
    parse_learning_metadata,
    parse_learnings_file,
    render_template,
    replace_settings,
    run_audit_learnings,
    run_init,
    run_migrate,
    run_migrate_coverage,
    run_migrate_settings_layout,
    run_sentinel,
    run_sync,
    run_validate,
    run_views_command,
    split_learnings_v5,
    untrack_gitignored_files,
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
    sync_parser.add_argument("--force", action="store_true", help="Overwrite locally-edited whole-file templates (no effect on block_template files; their in-marker content is always overwritten)")

    # --- validate ---
    validate_parser = subparsers.add_parser(
        "validate",
        help="Health check — verify repo structure and configuration",
    )
    validate_parser.add_argument("target_dir", help="Product repo directory to validate")
    validate_parser.add_argument("--json", action="store_true", dest="json_mode", help="JSON output only")

    # --- migrate ---
    # Per-feature opt-in migrations. Unlike `setup`, which auto-detects
    # version and migrates the whole layout, `migrate` is the explicit
    # surface for v1.4 features that require user intent (e.g. coverage
    # enforcement, which commits the project to BLOCKING Critic findings).
    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Per-feature v1.4 opt-in migrations (e.g. --enable-coverage, --enable-settings-layout)",
    )
    migrate_parser.add_argument("product_dir", help="Product repo directory")
    migrate_parser.add_argument(
        "--enable-coverage",
        action="store_true",
        dest="enable_coverage",
        help=(
            "Enable v1.4 F4 symbol-coverage enforcement: flip "
            "coverage_required: true in project-state.yaml and surface "
            "evidence-shape NOTEs. Critic Goal 1 will BLOCK on changed "
            "files missing from .test-evidence.json's changes_referenced."
        ),
    )
    migrate_parser.add_argument(
        "--enable-settings-layout",
        action="store_true",
        dest="enable_settings_layout",
        help=(
            "Stamp .claude/settings.json as on the v1.4 canonical minimal "
            "layout. Runs an aggressive legacy_cleanup pass (strips v1/v3 "
            "hook markers, regenerates the banner, preserves user hooks) "
            "and sets the manifest's v1_4_settings_migrated flag. v1.4.1's "
            "Critic NOTE on unmigrated products keys off this flag."
        ),
    )
    migrate_parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "Re-run even when the manifest tracks the migration as complete "
            "(useful for re-surfacing evidence-shape NOTEs after wiring up a "
            "verifier, or re-normalizing a hand-edited settings.json)."
        ),
    )
    migrate_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_mode",
        help="JSON output only",
    )

    # --- views ---
    views_parser = subparsers.add_parser(
        "views",
        help="Inspect or refresh derived views (Status / release-notes / scope-rollups)",
    )
    views_parser.add_argument("product_dir", help="Product repo directory")
    views_parser.add_argument(
        "--refresh",
        action="store_true",
        help="Regenerate views (write files); without this, reports planned actions only",
    )
    views_parser.add_argument("--json", action="store_true", dest="json_mode", help="JSON output only")

    # --- audit-learnings ---
    audit_parser = subparsers.add_parser(
        "audit-learnings",
        help=(
            "Audit .prawduct/learnings.md against optional lifecycle metadata "
            "(confirmations / created / sentinel). Reports promotion / "
            "retirement / stale candidates; --apply retires sentinel-pass "
            "entries to learnings-detail.md."
        ),
    )
    audit_parser.add_argument("product_dir", help="Product repo directory")
    audit_parser.add_argument(
        "--apply",
        action="store_true",
        help=(
            "Move sentinel-pass entries from learnings.md to "
            "learnings-detail.md under the 'Historical (structurally "
            "enforced)' section. Without --apply, the command only reports "
            "what would change."
        ),
    )
    audit_parser.add_argument(
        "--json", action="store_true", dest="json_mode", help="JSON output only"
    )

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

    elif args.command == "views":
        result = run_views_command(args.product_dir, refresh=args.refresh)

        if args.json_mode:
            print(json.dumps(result, indent=2))
        else:
            if "error" in result:
                log(f"Error: {result['error']}")
                return 1
            if not result["enabled"]:
                log("Views disabled (set views_enabled: true in project-state.yaml).")
                return 0
            mode = "refresh" if args.refresh else "dry-run"
            log(f"Derived views ({mode}):")
            for view in result["views"]:
                marker = {"noop": " ", "write": "*", "create": "+"}.get(view["action"], "?")
                log(f"  {marker} {view['summary']}")
            if not args.refresh:
                any_changes = any(v["action"] != "noop" for v in result["views"])
                if any_changes:
                    log("")
                    log("  Run with --refresh to apply.")
        return 0

    elif args.command == "migrate":
        # Per-feature opt-in migrations. Each flag dispatches to its own
        # runner; exactly one must be set. Mutual exclusion is enforced at
        # dispatch time rather than via argparse mutually_exclusive_group so
        # the help text shows both flags as peer options.
        feature_flags = [
            ("enable_coverage", args.enable_coverage),
            ("enable_settings_layout", args.enable_settings_layout),
        ]
        active = [name for name, on in feature_flags if on]
        if not active:
            log(
                "error: `migrate` requires a feature flag "
                "(--enable-coverage or --enable-settings-layout)"
            )
            migrate_parser.print_help()
            return 1
        if len(active) > 1:
            log(
                "error: `migrate` accepts one feature flag per invocation; "
                f"got {', '.join(active)}. Run them as separate commands."
            )
            return 1

        if args.enable_coverage:
            result = run_migrate_coverage(args.product_dir, force=args.force)
            success_label = "Coverage migration"
            on_off_field = "enabled"
            on_off_label = "coverage_required"
            on_off_location = "on disk"
        else:  # args.enable_settings_layout
            result = run_migrate_settings_layout(args.product_dir, force=args.force)
            success_label = "Settings-layout migration"
            on_off_field = "migrated"
            on_off_label = "v1_4_settings_migrated"
            on_off_location = "in manifest"

        if args.json_mode:
            print(json.dumps(result, indent=2))
        else:
            if "error" in result:
                log(f"Error: {result['error']}")
                return 1
            if result["actions"]:
                log(f"{success_label} applied to {result['product_dir']}:")
                for action in result["actions"]:
                    log(f"  + {action}")
            else:
                log(f"{success_label}: no changes ({result['product_dir']})")
            for note in result["notes"]:
                log(f"  * {note}")
            log("")
            log(
                f"  {on_off_label} is "
                + ("ON" if result.get(on_off_field) else "OFF")
                + f" {on_off_location}."
            )
        return 0 if "error" not in result else 1

    elif args.command == "audit-learnings":
        result = run_audit_learnings(args.product_dir, apply=args.apply)

        if args.json_mode:
            print(json.dumps(result, indent=2))
            return 0 if "error" not in result else 1

        if "error" in result:
            log(f"Error: {result['error']}")
            return 1

        promotions = result["promotions"]
        retirements = result["retirements"]
        stale_flags = result["stale_flags"]
        errors = result["errors"]

        mode_label = "apply" if result["applied"] else "dry-run"
        log(f"Learnings audit ({mode_label}): {result['product_dir']}")

        if promotions:
            log("")
            log(f"  Promotion candidates ({len(promotions)} — advisory):")
            for p in promotions:
                log(f"    * {p['title']} (confirmations={p['confirmations']})")

        if retirements:
            log("")
            log(f"  Retirement candidates ({len(retirements)}):")
            for r in retirements:
                if r["passed"] is True:
                    status = "applied" if r["applied"] else "pending --apply"
                    log(f"    * {r['title']}  [sentinel pass — {status}]")
                elif r["passed"] is False:
                    log(f"    ! {r['title']}  [sentinel FAIL — {r['sentinel']}]")
                else:
                    log(f"    ? {r['title']}  [sentinel skipped — {r['sentinel']}]")

        if stale_flags:
            log("")
            log(f"  Stale flags ({len(stale_flags)}):")
            for s in stale_flags:
                log(
                    f"    * {s['title']}  "
                    f"(created={s['created']}, age={s['age_days']}d, "
                    f"confirmations={s['confirmations']})"
                )

        if errors:
            log("")
            log(f"  Errors ({len(errors)}):")
            for e in errors:
                log(f"    ! {e['title']}: {e['error']}")

        if not (promotions or retirements or stale_flags or errors):
            log("  No lifecycle actions — every entry is either active "
                "with no metadata or annotated but not yet a candidate.")

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
