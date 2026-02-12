#!/usr/bin/env bash
#
# session-health-check.sh — Quick session orientation report
#
# Purpose: Wraps observation-analysis.sh output with backlog status from
# project-state.yaml. Used during Session Resumption to surface relevant
# findings without requiring manual inspection.
#
# Reports:
#   - Pattern analysis summary (types above threshold)
#   - priority: next backlog items
#   - Overdue triage (>2 weeks since last_triage)
#   - Stale deferred items (>4 weeks)
#   - Untransferred fallback observation files
#
# Usage:
#   tools/session-health-check.sh
#
# Exit codes:
#   0 — Report produced (even if empty)
#   1 — Missing prerequisites (not in repo root, missing files)

set -uo pipefail

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -z "$REPO_ROOT" ]]; then
    echo "Error: Not in a git repository." >&2
    exit 1
fi

PROJECT_STATE="$REPO_ROOT/project-state.yaml"
OBS_ANALYSIS="$REPO_ROOT/tools/observation-analysis.sh"

echo "=========================================="
echo " Session Health Check"
echo " $(date +%Y-%m-%d)"
echo "=========================================="
echo ""

# --- 1. Pattern analysis (delegate to observation-analysis.sh) ---

if [[ -x "$OBS_ANALYSIS" ]]; then
    patterns=$("$OBS_ANALYSIS" --patterns-only 2>/dev/null || echo "")
    if echo "$patterns" | grep -q "PATTERN DETECTED"; then
        echo "## Observation Patterns"
        echo "$patterns" | grep -A5 "PATTERN DETECTED"
        echo ""
    else
        echo "## Observation Patterns"
        echo "  No patterns above threshold."
        echo ""
    fi
else
    echo "## Observation Patterns"
    echo "  (observation-analysis.sh not found)"
    echo ""
fi

# --- 2. Backlog status from project-state.yaml ---

if [[ -f "$PROJECT_STATE" ]]; then
    echo "## Observation Backlog"

    # Extract priority: next items
    next_items=$(python3 -c "
import yaml, sys
try:
    with open('$PROJECT_STATE') as f:
        data = yaml.safe_load(f)
    backlog = data.get('observation_backlog', {})
    items = backlog.get('items', [])
    next_items = [i for i in items if i.get('priority') == 'next']
    if next_items:
        for item in next_items:
            print(f\"  - [{item.get('type', '?')}] {item.get('summary', '?')}\")
            print(f\"    Target: {', '.join(item.get('target_files', []))}\")
    else:
        print('  No priority:next items.')
except Exception as e:
    print(f'  (Could not parse backlog: {e})')
" 2>/dev/null || echo "  (python3/yaml not available for backlog parsing)")
    echo "$next_items"
    echo ""

    # Check triage freshness
    triage_info=$(python3 -c "
import yaml, sys
from datetime import datetime, timedelta
try:
    with open('$PROJECT_STATE') as f:
        data = yaml.safe_load(f)
    backlog = data.get('observation_backlog', {})
    last_triage = backlog.get('last_triage')
    if last_triage:
        if isinstance(last_triage, str):
            triage_date = datetime.strptime(last_triage, '%Y-%m-%d')
        else:
            triage_date = datetime.combine(last_triage, datetime.min.time())
        age_days = (datetime.now() - triage_date).days
        if age_days > 14:
            print(f'  WARNING: Observation triage overdue (last: {last_triage}, {age_days} days ago)')
        else:
            print(f'  Last triage: {last_triage} ({age_days} days ago)')
    else:
        print('  No triage date recorded.')
except Exception as e:
    print(f'  (Could not check triage: {e})')
" 2>/dev/null || echo "  (python3/yaml not available)")
    echo "$triage_info"
    echo ""

    # Check for stale deferred items (>4 weeks)
    stale_info=$(python3 -c "
import yaml, sys
from datetime import datetime, timedelta
try:
    with open('$PROJECT_STATE') as f:
        data = yaml.safe_load(f)
    backlog = data.get('observation_backlog', {})
    items = backlog.get('items', [])
    deferred = [i for i in items if i.get('priority') == 'deferred']
    stale = []
    for item in deferred:
        added = item.get('added')
        if added:
            if isinstance(added, str):
                added_date = datetime.strptime(added, '%Y-%m-%d')
            else:
                added_date = datetime.combine(added, datetime.min.time())
            age_days = (datetime.now() - added_date).days
            if age_days > 28:
                stale.append((item, age_days))
    if stale:
        print(f'  WARNING: {len(stale)} deferred item(s) older than 4 weeks:')
        for item, age in stale:
            print(f\"    - [{item.get('type', '?')}] {item.get('summary', '?')} ({age} days)\")
    else:
        print(f'  {len(deferred)} deferred item(s), none older than 4 weeks.')
except Exception as e:
    print(f'  (Could not check deferred items: {e})')
" 2>/dev/null || echo "  (python3/yaml not available)")
    echo "$stale_info"
    echo ""
else
    echo "## Observation Backlog"
    echo "  (project-state.yaml not found)"
    echo ""
fi

# --- 3. Fallback observation files ---

fallback_files=()
shopt -s nullglob
for dir in ../*/working-notes "$REPO_ROOT/working-notes"; do
    if [[ -d "$dir" ]]; then
        for f in "$dir"/framework-observations-*.yaml; do
            if [[ -f "$f" ]]; then
                fallback_files+=("$f")
            fi
        done
    fi
done
shopt -u nullglob

if [[ ${#fallback_files[@]} -gt 0 ]]; then
    echo "## Untransferred Observations"
    echo "  WARNING: ${#fallback_files[@]} fallback observation file(s) need transfer:"
    for f in "${fallback_files[@]}"; do
        echo "    $f"
    done
    echo ""
fi

# --- 4. Session edits pending review ---

SESSION_EDITS="$REPO_ROOT/.claude/.session-edits.json"
if [[ -f "$SESSION_EDITS" ]]; then
    edit_count=$(python3 -c "
import json
try:
    with open('$SESSION_EDITS') as f:
        data = json.load(f)
    print(len(data.get('files', [])))
except:
    print(0)
" 2>/dev/null || echo "0")
    if [[ "$edit_count" -gt 0 ]]; then
        echo "## Pending Session Edits"
        echo "  $edit_count framework file(s) modified without Critic review."
        echo ""
    fi
fi

echo "=========================================="
