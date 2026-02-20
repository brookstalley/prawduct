#!/usr/bin/env bash
#
# extract-patterns.sh — Invoke the Pattern Extractor agent or record results
#
# Purpose: Wrapper for the Pattern Extractor subagent. Called by
# session-health-check.sh when active observations exceed threshold,
# or by the Orchestrator on demand.
#
# Usage:
#   tools/extract-patterns.sh                    # Check if extraction needed
#   tools/extract-patterns.sh --record REPORT    # Record pattern report JSON
#   tools/extract-patterns.sh --status           # Show last extraction status
#
# Options:
#   --product-dir DIR  Resolve product root from DIR instead of CWD.
#                      Use when a subagent's CWD differs from the target product.
#
# Exit codes:
#   0 — Success (or extraction not needed)
#   1 — Error

set -uo pipefail

# Parse --product-dir before positional args
_PRODUCT_DIR_OVERRIDE=""
_remaining_args=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --product-dir) _PRODUCT_DIR_OVERRIDE="$2"; shift 2 ;;
        *) _remaining_args+=("$1"); shift ;;
    esac
done
set -- "${_remaining_args[@]+"${_remaining_args[@]}"}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/resolve-product-root.sh" ${_PRODUCT_DIR_OVERRIDE:+--product-dir "$_PRODUCT_DIR_OVERRIDE"}

OBS_DIR="$PRODUCT_ROOT/framework-observations"
REPORT_FILE="$PRODUCT_ROOT/.pattern-report.json"
THRESHOLD="${PRAWDUCT_PATTERN_THRESHOLD:-8}"

MODE="${1:---check}"

case "$MODE" in
    --record)
        # Record pattern report from stdin or argument
        if [[ $# -ge 2 ]]; then
            echo "$2" > "$REPORT_FILE"
        else
            cat > "$REPORT_FILE"
        fi
        echo "Pattern report recorded to: $REPORT_FILE"
        exit 0
        ;;
    --status)
        if [[ -f "$REPORT_FILE" ]]; then
            python3 -c "
import json, os
from datetime import datetime
try:
    with open('$REPORT_FILE') as f:
        data = json.load(f)
    ts = data.get('timestamp', 'unknown')
    clusters = len(data.get('clusters', []))
    obs_count = data.get('observations_analyzed', 0)
    mtime = datetime.fromtimestamp(os.path.getmtime('$REPORT_FILE'))
    age_days = (datetime.now() - mtime).days
    print(f'Last extraction: {ts} ({age_days} days ago)')
    print(f'Observations analyzed: {obs_count}')
    print(f'Clusters found: {clusters}')
    high = sum(1 for c in data.get('clusters', []) if c.get('priority') == 'high')
    if high:
        print(f'High-priority actions: {high}')
except Exception as e:
    print(f'Could not read pattern report: {e}')
" 2>/dev/null
        else
            echo "No pattern report found."
        fi
        exit 0
        ;;
    --check)
        # Check whether extraction is needed
        if [[ ! -d "$OBS_DIR" ]]; then
            echo "EXTRACTION_NEEDED: false"
            echo "REASON: no observations directory"
            exit 0
        fi

        # Count active observation files
        active_count=$(python3 -c "
import sys, os
sys.path.insert(0, '$SCRIPT_DIR')
import obs_utils
files = obs_utils.find_observation_files('$OBS_DIR')
print(len(files))
" 2>/dev/null || echo "0")

        # Check report freshness
        stale="false"
        if [[ -f "$REPORT_FILE" ]]; then
            stale=$(python3 -c "
import os
from datetime import datetime
mtime = datetime.fromtimestamp(os.path.getmtime('$REPORT_FILE'))
age_days = (datetime.now() - mtime).days
print('true' if age_days > 7 else 'false')
" 2>/dev/null || echo "true")
        else
            stale="true"
        fi

        needed="false"
        reason=""
        if [[ "$active_count" -ge "$THRESHOLD" && "$stale" == "true" ]]; then
            needed="true"
            reason="$active_count active observations (threshold: $THRESHOLD), report stale or missing"
        elif [[ "$active_count" -ge "$THRESHOLD" ]]; then
            reason="$active_count active observations but report is fresh"
        else
            reason="$active_count active observations (below threshold: $THRESHOLD)"
        fi

        echo "EXTRACTION_NEEDED: $needed"
        echo "ACTIVE_OBSERVATIONS: $active_count"
        echo "THRESHOLD: $THRESHOLD"
        echo "REPORT_STALE: $stale"
        echo "REASON: $reason"
        exit 0
        ;;
    *)
        echo "Usage: extract-patterns.sh [--check | --record REPORT | --status]" >&2
        exit 1
        ;;
esac
