#!/usr/bin/env bash
#
# session-health-check.sh — Quick session orientation report
#
# Purpose: Wraps observation-analysis.sh output with backlog status from
# project-state.yaml. Used during Session Resumption to surface relevant
# findings without requiring manual inspection.
#
# Reports:
#   - Actionable patterns with proposed actions and affected skills
#   - priority: next backlog items
#   - Overdue triage (>2 weeks since last_triage)
#   - Stale deferred items (>4 weeks)
#   - Untransferred fallback observation files
#
# Usage:
#   tools/session-health-check.sh                  # Full report
#   tools/session-health-check.sh --actionable-only # Only patterns needing action
#
# Exit codes:
#   0 — Report produced (even if empty)
#   1 — Missing prerequisites (not in repo root, missing files)

set -uo pipefail

MODE="${1:---full}"
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -z "$REPO_ROOT" ]]; then
    echo "Error: Not in a git repository." >&2
    exit 1
fi

PROJECT_STATE="$REPO_ROOT/project-state.yaml"
OBS_DIR="$REPO_ROOT/framework-observations"

if [[ "$MODE" != "--actionable-only" ]]; then
    echo "=========================================="
    echo " Session Health Check"
    echo " $(date +%Y-%m-%d)"
    echo "=========================================="
    echo ""
fi

# --- 1. Actionable pattern analysis (parse observation files directly) ---

actionable_output=$(python3 -c "
import yaml, os, sys, glob

obs_dir = '$OBS_DIR'
if not os.path.isdir(obs_dir):
    print('  (framework-observations/ not found)')
    print('PATTERNS_REQUIRING_ACTION: 0')
    sys.exit(0)

files = sorted(glob.glob(os.path.join(obs_dir, '*.yaml')))
files = [f for f in files if not f.endswith('schema.yaml')]

if not files:
    print('  No observation files found.')
    print('PATTERNS_REQUIRING_ACTION: 0')
    sys.exit(0)

# Tiered thresholds
META_TYPES = {'process_friction', 'rubric_issue'}
BUILD_TYPES = {'artifact_insufficiency', 'spec_ambiguity', 'deployment_friction', 'critic_gap'}

def get_threshold(obs_type):
    if obs_type in META_TYPES:
        return 2
    elif obs_type in BUILD_TYPES:
        return 3
    else:
        return 4

# Collect all observations (handle multi-document YAML files)
all_obs = []
for f in files:
    try:
        with open(f) as fh:
            for data in yaml.safe_load_all(fh):
                if not data or 'observations' not in data:
                    continue
                skills = data.get('skills_affected', [])
                for obs in data.get('observations', []):
                    obs['_file'] = os.path.basename(f)
                    obs['_skills'] = skills
                    all_obs.append(obs)
    except:
        continue

# Group by type, filter to un-acted (noted or requires_pattern)
from collections import defaultdict
by_type = defaultdict(list)
for obs in all_obs:
    status = obs.get('status', 'noted')
    if status in ('noted', 'requires_pattern'):
        by_type[obs.get('type', 'unknown')].append(obs)

# Find actionable patterns (count >= threshold for that type)
actionable = []
for obs_type, observations in sorted(by_type.items()):
    total_of_type = sum(1 for o in all_obs if o.get('type') == obs_type)
    threshold = get_threshold(obs_type)
    if total_of_type >= threshold:
        # Collect unique proposed actions and affected skills
        actions = []
        skills = set()
        for obs in observations:
            action = obs.get('proposed_action')
            if action:
                actions.append(action)
            for s in obs.get('_skills', []):
                skills.add(s)
        actionable.append({
            'type': obs_type,
            'total': total_of_type,
            'unacted': len(observations),
            'threshold': threshold,
            'skills': sorted(skills),
            'actions': actions,
        })

# Output
if actionable:
    for item in actionable:
        tier = 'meta' if item['type'] in META_TYPES else ('build' if item['type'] in BUILD_TYPES else 'product')
        print(f\"  PATTERN: {item['type']} ({item['total']} total, {item['unacted']} un-acted, {tier} threshold: {item['threshold']}+)\")
        if item['skills']:
            print(f\"    Affected skills: {', '.join(item['skills'])}\")
        for action in item['actions']:
            print(f'    -> {action}')
        print()
else:
    print('  No patterns above threshold with un-acted observations.')
    print()

print(f'PATTERNS_REQUIRING_ACTION: {len(actionable)}')
" 2>/dev/null || echo "  (python3/yaml not available for pattern analysis)
PATTERNS_REQUIRING_ACTION: 0")

# Extract the count for use by callers
patterns_count=$(echo "$actionable_output" | grep "^PATTERNS_REQUIRING_ACTION:" | head -1 | sed 's/.*: //')

echo "## Actionable Observation Patterns"
echo "$actionable_output" | grep -v "^PATTERNS_REQUIRING_ACTION:"
echo ""

# If --actionable-only, skip non-pattern sections
if [[ "$MODE" == "--actionable-only" ]]; then
    echo "PATTERNS_REQUIRING_ACTION: ${patterns_count:-0}"
    exit 0
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

echo "PATTERNS_REQUIRING_ACTION: ${patterns_count:-0}"
echo ""
echo "=========================================="
