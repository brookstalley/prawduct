#!/usr/bin/env bash
#
# compact-project-state.sh — Mechanical compaction of growing project-state.yaml sections
#
# Implements LIFECYCLE rules defined in templates/project-state.yaml:
#   - change_log: >20 entries → keep 10 most recent + summary block
#   - build_plan.chunks: all complete → compact to {id, name, status}
#   - build_state.reviews: all resolved → compact to {chunk_id, summary, deferred_items}
#   - review_findings.entries: resolved → compact to {stage, lens, summary, deferred_count}
#   - iteration_state.feedback_cycles: >10 completed → compact to summary form
#
# Usage:
#   tools/compact-project-state.sh [OPTIONS] [FILE]
#
#   FILE defaults to project-state.yaml in repo root.
#
#   Options:
#     --dry-run    Show what would change without writing
#     --check      Exit 1 if compaction needed, 0 if not
#     --section X  Compact only section X (repeatable)
#     --verbose    Show detailed before/after for each section
#
# Exit codes:
#   0 — Success (or --check with no compaction needed)
#   1 — Error or --check with compaction needed

set -uo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -z "$REPO_ROOT" ]]; then
    echo "Error: Not in a git repository." >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY_SCRIPT="$SCRIPT_DIR/compact-project-state.py"

if [[ ! -f "$PY_SCRIPT" ]]; then
    echo "Error: Python script not found: $PY_SCRIPT" >&2
    exit 1
fi

if ! command -v python3 &>/dev/null; then
    echo "Error: python3 is required but not found." >&2
    exit 1
fi

# Verify PyYAML is available
if ! python3 -c "import yaml" 2>/dev/null; then
    echo "Error: PyYAML is required. Install with: pip3 install pyyaml" >&2
    exit 1
fi

exec python3 "$PY_SCRIPT" "$@"
