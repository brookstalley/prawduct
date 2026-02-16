#!/usr/bin/env bash
#
# prawduct-init.sh — Mechanical prawduct integration setup and repair
#
# Detects, creates, and repairs prawduct infrastructure in a target directory.
# Handles fresh repos, stale framework paths, missing hooks, and settings.json merging.
# Both standalone (users run directly) and Orchestrator-internal (called during activation).
#
# Usage:
#   tools/prawduct-init.sh [OPTIONS] [TARGET_DIR]
#
#   TARGET_DIR defaults to current working directory.
#
#   Options:
#     --check       Report state without making changes (exit 0=healthy, 1=needs repair)
#     --dry-run     Show what would change without writing
#     --fix         Apply all repairs (default)
#     --json        JSON-only output to stdout (suppresses human-readable stderr)
#
# Exit codes:
#   0 — Success (or --check with healthy state)
#   1 — Error or --check with repairs needed

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY_SCRIPT="$SCRIPT_DIR/prawduct-init.py"

if [[ ! -f "$PY_SCRIPT" ]]; then
    echo "Error: Python script not found: $PY_SCRIPT" >&2
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "Error: python3 is required but not found." >&2
    exit 1
fi

exec python3 "$PY_SCRIPT" "$@"
