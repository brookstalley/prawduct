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
#   - Overdue triage (>2 days since last_triage)
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

# Resolve product root (shared detection logic)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/resolve-product-root.sh"

PROJECT_STATE="$PRODUCT_ROOT/project-state.yaml"
OBS_DIR="$PRODUCT_ROOT/framework-observations"

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
META_TYPES = {'process_friction', 'rubric_issue', 'skill_quality', 'external_practice_drift', 'documentation_drift', 'structural_critique'}
BUILD_TYPES = {'artifact_insufficiency', 'spec_ambiguity', 'deployment_friction', 'critic_gap', 'integration_friction'}

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

# Group by type, filter to active (non-terminal: not acted_on or archived)
from collections import defaultdict
by_type = defaultdict(list)
for obs in all_obs:
    status = obs.get('status', 'noted')
    if status not in ('acted_on', 'archived'):
        by_type[obs.get('type', 'unknown')].append(obs)

# Find actionable patterns (active count >= threshold for that type)
actionable = []
for obs_type, observations in sorted(by_type.items()):
    active_count = len(observations)
    threshold = get_threshold(obs_type)
    if active_count >= threshold:
        # Collect unique proposed actions and affected skills
        actions = []
        skills = set()
        for obs in observations:
            action = obs.get('proposed_action')
            if action:
                actions.append(action)
            for s in obs.get('_skills', []):
                skills.add(s)
        total_of_type = sum(1 for o in all_obs if o.get('type') == obs_type)
        actionable.append({
            'type': obs_type,
            'active': active_count,
            'total': total_of_type,
            'threshold': threshold,
            'skills': sorted(skills),
            'actions': actions,
        })

# Output
if actionable:
    for item in actionable:
        tier = 'meta' if item['type'] in META_TYPES else ('build' if item['type'] in BUILD_TYPES else 'product')
        print(f\"  PATTERN: {item['type']} ({item['active']} active of {item['total']} total, {tier} threshold: {item['threshold']}+)\")
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
        if age_days > 2:
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
for dir in ../*/working-notes "$REPO_ROOT/working-notes" "$REPO_ROOT/.prawduct/working-notes" ../*/.prawduct/working-notes; do
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

SESSION_GOV="$REPO_ROOT/.claude/.session-governance.json"
if [[ -f "$SESSION_GOV" ]]; then
    edit_count=$(python3 -c "
import json
try:
    with open('$SESSION_GOV') as f:
        data = json.load(f)
    fw = data.get('framework_edits', {})
    print(len(fw.get('files', [])))
except:
    print(0)
" 2>/dev/null || echo "0")
    if [[ "$edit_count" -gt 0 ]]; then
        echo "## Pending Session Edits"
        echo "  $edit_count framework file(s) modified without Critic review."
        echo ""
    fi
fi

# --- 5. Infrastructure Health ---

infra_warnings=0
echo "## Infrastructure Health"

infra_output=$(python3 -c "
import yaml, os, sys, glob
from datetime import datetime, timedelta

obs_dir = '$OBS_DIR'
archive_dir = os.path.join(obs_dir, 'archive')
working_notes_dir = os.path.join('$PRODUCT_ROOT', 'working-notes')
warnings = 0

# --- Observation directory ---
active_files = [f for f in glob.glob(os.path.join(obs_dir, '*.yaml'))
                if not f.endswith('schema.yaml')]
archived_files = glob.glob(os.path.join(archive_dir, '*.yaml')) if os.path.isdir(archive_dir) else []

print(f'  framework-observations/: {len(active_files)} active files, {len(archived_files)} archived')

# Warn if too many active files
if len(active_files) > 50:
    print(f'  WARNING: {len(active_files)} active observation files (threshold: 50). Consider archiving resolved files.')
    warnings += 1

# --- Archive backlog ---
archivable = 0
for f in active_files:
    try:
        all_terminal = True
        with open(f) as fh:
            for doc in yaml.safe_load_all(fh):
                if not doc or 'observations' not in doc:
                    continue
                for obs in doc.get('observations', []):
                    status = obs.get('status', 'noted')
                    if status not in ('acted_on', 'archived'):
                        all_terminal = False
                        break
                if not all_terminal:
                    break
        if all_terminal:
            archivable += 1
    except:
        continue

if archivable > 0:
    print(f'  WARNING: {archivable} file(s) ready to archive. Run: tools/update-observation-status.sh --archive-all')
    warnings += 1

# --- Stale observations ---
oldest_unresolved = None
stale_noted = 0
now = datetime.now()
for f in active_files:
    try:
        with open(f) as fh:
            for doc in yaml.safe_load_all(fh):
                if not doc or 'observations' not in doc:
                    continue
                timestamp = doc.get('timestamp', '')
                if not timestamp:
                    continue
                try:
                    obs_date = datetime.fromisoformat(timestamp.replace('Z', '+00:00')).replace(tzinfo=None)
                except:
                    continue
                for obs in doc.get('observations', []):
                    status = obs.get('status', 'noted')
                    if status == 'noted':
                        age_days = (now - obs_date).days
                        if age_days > 30:
                            stale_noted += 1
                        if oldest_unresolved is None or obs_date < oldest_unresolved:
                            oldest_unresolved = obs_date
    except:
        continue

if oldest_unresolved:
    age = (now - oldest_unresolved).days
    print(f'  Oldest un-resolved observation: {oldest_unresolved.strftime(\"%Y-%m-%d\")} ({age} days ago)')
    if stale_noted > 0:
        print(f'  WARNING: {stale_noted} observation(s) with status \"noted\" older than 30 days.')
        warnings += 1

# --- Working notes freshness ---
if os.path.isdir(working_notes_dir):
    wn_files = [f for f in os.listdir(working_notes_dir)
                if os.path.isfile(os.path.join(working_notes_dir, f)) and f != '.gitkeep']
    stale_wn = 0
    for wf in wn_files:
        wf_path = os.path.join(working_notes_dir, wf)
        mtime = datetime.fromtimestamp(os.path.getmtime(wf_path))
        if (now - mtime).days > 14:
            stale_wn += 1
    if wn_files:
        print(f'  working-notes/: {len(wn_files)} file(s), {stale_wn} older than 14 days')
        if stale_wn > 0:
            print(f'  WARNING: {stale_wn} working note(s) older than 14 days. Incorporate into Tier 1 or delete.')
            warnings += 1

print(f'INFRASTRUCTURE_WARNINGS: {warnings}')
" 2>/dev/null || echo "  (python3/yaml not available for infrastructure health check)
INFRASTRUCTURE_WARNINGS: 0")

# Display output, extract warning count
echo "$infra_output" | grep -v "^INFRASTRUCTURE_WARNINGS:"
infra_warnings=$(echo "$infra_output" | grep "^INFRASTRUCTURE_WARNINGS:" | head -1 | sed 's/.*: //')
echo ""

# --- 6. Project State File Health ---

state_warnings=0
if [[ -f "$PROJECT_STATE" ]]; then
    echo "## Project State Health"

    state_health_output=$(python3 -c "
import yaml, sys

state_file = '$PROJECT_STATE'
warnings = 0

try:
    with open(state_file) as f:
        data = yaml.safe_load(f)
    with open(state_file) as f:
        total_lines = sum(1 for _ in f)

    print(f'  Total lines: {total_lines}')

    # Count entries in growing sections
    sections = {}

    # change_log
    cl = data.get('change_log', []) or []
    cl_complete = sum(1 for _ in cl)  # all entries count, no terminal status
    sections['change_log'] = {'total': len(cl), 'compactable': max(0, len(cl) - 10)}

    # build_plan.chunks
    bp = data.get('build_plan', {}) or {}
    chunks = bp.get('chunks', []) or []
    chunks_complete = sum(1 for c in chunks if c.get('status') == 'complete')
    sections['build_plan.chunks'] = {'total': len(chunks), 'compactable': chunks_complete}

    # build_state.reviews
    bs = data.get('build_state', {}) or {}
    reviews = bs.get('reviews', []) or []
    reviews_resolved = sum(1 for r in reviews
                          if all(f.get('status') in ('resolved', 'deferred')
                                 for f in r.get('findings', [])))
    sections['build_state.reviews'] = {'total': len(reviews), 'compactable': reviews_resolved}

    # review_findings.entries
    rf = data.get('review_findings', {}) or {}
    rf_entries = rf.get('entries', []) or []
    rf_resolved = sum(1 for e in rf_entries
                      if all(f.get('status') in ('resolved', 'deferred')
                             for f in e.get('findings', [])))
    sections['review_findings.entries'] = {'total': len(rf_entries), 'compactable': rf_resolved}

    # iteration_state.feedback_cycles
    it = data.get('iteration_state', {}) or {}
    fc = it.get('feedback_cycles', []) or []
    fc_complete = sum(1 for c in fc if c.get('status') == 'complete')
    sections['iteration_state.feedback_cycles'] = {'total': len(fc), 'compactable': fc_complete}

    # Report
    growing_lines = 0
    for name, info in sections.items():
        if info['total'] > 0:
            print(f\"  {name}: {info['total']} entries ({info['compactable']} compaction-eligible)\")
            growing_lines += info['total'] * 5  # rough estimate: ~5 lines per entry

    # Threshold checks
    if sections['change_log']['total'] > 20:
        print(f\"  WARNING: change_log has {sections['change_log']['total']} entries (threshold: 20). Compact older entries.\")
        warnings += 1

    for name, info in sections.items():
        if info['compactable'] > 20:
            print(f\"  WARNING: {name} has {info['compactable']} compaction-eligible entries (threshold: 20).\")
            warnings += 1

    if growing_lines > 300:
        print(f'  WARNING: Growing sections estimated at ~{growing_lines} lines (threshold: 300). Consider compaction.')
        warnings += 1

    if all(info['total'] == 0 for info in sections.values()):
        print('  All growing sections empty (new or compacted project).')

except Exception as e:
    print(f'  (Could not analyze project state: {e})')

print(f'STATE_WARNINGS: {warnings}')
" 2>/dev/null || echo "  (python3/yaml not available for project state analysis)
STATE_WARNINGS: 0")

    echo "$state_health_output" | grep -v "^STATE_WARNINGS:"
    state_warnings=$(echo "$state_health_output" | grep "^STATE_WARNINGS:" | head -1 | sed 's/.*: //')
    if [[ "${state_warnings:-0}" -gt 0 ]]; then
        echo "  ACTION: Run 'tools/compact-project-state.sh --dry-run' to preview compaction."
    fi
    echo ""
fi

# --- 7. Skill File Health ---

skill_warnings=0
echo "## Skill File Health"

skill_health_output=$(python3 -c "
import os, glob

repo_root = '$REPO_ROOT'
skills_dir = os.path.join(repo_root, 'skills')
warnings = 0

if not os.path.isdir(skills_dir):
    print('  (skills/ directory not found)')
    print('SKILL_WARNINGS: 0')
    exit(0)

# Find all skill directories
skill_dirs = sorted([d for d in os.listdir(skills_dir)
                     if os.path.isdir(os.path.join(skills_dir, d))])

for skill_name in skill_dirs:
    skill_dir = os.path.join(skills_dir, skill_name)
    main_file = os.path.join(skill_dir, 'SKILL.md')

    if not os.path.isfile(main_file):
        continue

    with open(main_file) as f:
        main_lines = sum(1 for _ in f)

    # Check SKILL.md thresholds
    if main_lines > 600:
        print(f'  ALERT: {skill_name}/SKILL.md is {main_lines} lines (exceeds H1 Complex threshold of 600)')
        warnings += 1
    elif main_lines > 400:
        print(f'  WARNING: {skill_name}/SKILL.md is {main_lines} lines (consider decomposition, H1 threshold: 400)')
        warnings += 1

    # Check sub-files
    sub_files = [f for f in os.listdir(skill_dir)
                 if f.endswith('.md') and f != 'SKILL.md' and os.path.isfile(os.path.join(skill_dir, f))]
    for sub_file in sorted(sub_files):
        sub_path = os.path.join(skill_dir, sub_file)
        with open(sub_path) as f:
            sub_lines = sum(1 for _ in f)
        if sub_lines > 300:
            print(f'  NOTE: {skill_name}/{sub_file} is {sub_lines} lines (sub-file approaching main-file size)')
            warnings += 1

if warnings == 0:
    print('  All skill files within H1 thresholds.')

print(f'SKILL_WARNINGS: {warnings}')
" 2>/dev/null || echo "  (python3 not available for skill health check)
SKILL_WARNINGS: 0")

echo "$skill_health_output" | grep -v "^SKILL_WARNINGS:"
skill_warnings=$(echo "$skill_health_output" | grep "^SKILL_WARNINGS:" | head -1 | sed 's/.*: //')
echo ""

# --- 8. Deprecated Term Scanning ---

deprecated_warnings=0
if [[ -f "$PROJECT_STATE" ]]; then
    echo "## Deprecated Term Scanning"

    deprecated_output=$(python3 -c "
import yaml, os, sys, re, subprocess

state_file = '$PROJECT_STATE'
repo_root = '$REPO_ROOT'
warnings = 0

try:
    with open(state_file) as f:
        data = yaml.safe_load(f)
    terms = data.get('deprecated_terms', []) or []
    if not terms:
        print('  No deprecated terms registered.')
        print('DEPRECATED_TERM_WARNINGS: 0')
        sys.exit(0)

    # Exclusion patterns: historical records
    exclude_dirs = ['eval-history', 'framework-observations/archive', 'working-notes', '.git', '.claude']

    # For project-state.yaml, we need to exclude change_log and deprecated_terms sections
    # We'll handle this by post-filtering matches in project-state.yaml

    # Read project-state.yaml to find section boundaries for exclusion
    with open(state_file) as f:
        ps_lines = f.readlines()

    # Find line ranges for change_log and deprecated_terms sections
    exclude_ranges = []
    in_section = False
    section_start = None
    for i, line in enumerate(ps_lines, 1):
        if line.startswith('change_log:') or line.startswith('deprecated_terms:'):
            in_section = True
            section_start = i
        elif in_section and (line.startswith('# ====') or (not line.startswith(' ') and not line.startswith('#') and line.strip() and ':' in line)):
            exclude_ranges.append((section_start, i - 1))
            in_section = False
            # Check if this new line is also a section to exclude
            if line.startswith('change_log:') or line.startswith('deprecated_terms:'):
                in_section = True
                section_start = i
    if in_section:
        exclude_ranges.append((section_start, len(ps_lines)))

    total_warnings = 0
    for term_entry in terms:
        term = term_entry.get('term', '')
        patterns = term_entry.get('patterns', [])
        replacement = term_entry.get('replacement', 'removed')

        for pattern in patterns:
            try:
                # Use grep to find matches, excluding historical directories
                cmd = ['grep', '-rni', pattern]
                for d in exclude_dirs:
                    cmd.extend(['--exclude-dir=' + d])
                cmd.append(repo_root)
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

                if result.returncode == 0 and result.stdout.strip():
                    for line in result.stdout.strip().split('\n'):
                        if not line.strip():
                            continue
                        # Parse grep output: file:line_num:content
                        parts = line.split(':', 2)
                        if len(parts) < 3:
                            continue
                        filepath = parts[0]
                        try:
                            line_num = int(parts[1])
                        except ValueError:
                            continue

                        # Get relative path
                        rel_path = os.path.relpath(filepath, repo_root)

                        # Skip if in excluded directory
                        skip = False
                        for d in exclude_dirs:
                            if rel_path.startswith(d + '/') or rel_path.startswith(d + os.sep):
                                skip = True
                                break
                        if skip:
                            continue

                        # Skip observation entry files (historical records)
                        # Only schema.yaml and README.md in framework-observations/ are active docs
                        if rel_path.startswith('framework-observations/'):
                            basename = os.path.basename(rel_path)
                            if basename.endswith('.yaml') and basename != 'schema.yaml':
                                continue

                        # Skip project-state.yaml matches in excluded sections
                        if rel_path == 'project-state.yaml':
                            in_excluded = False
                            for start, end in exclude_ranges:
                                if start <= line_num <= end:
                                    in_excluded = True
                                    break
                            if in_excluded:
                                continue

                        print(f'  WARNING: Deprecated term \"{term}\" found in {rel_path}:{line_num}')
                        total_warnings += 1
            except Exception:
                continue

    if total_warnings == 0:
        print('  No surviving deprecated term references found.')

    print(f'DEPRECATED_TERM_WARNINGS: {total_warnings}')

except Exception as e:
    print(f'  (Could not scan deprecated terms: {e})')
    print('DEPRECATED_TERM_WARNINGS: 0')
" 2>/dev/null || echo "  (python3/yaml not available for deprecated term scanning)
DEPRECATED_TERM_WARNINGS: 0")

    echo "$deprecated_output" | grep -v "^DEPRECATED_TERM_WARNINGS:"
    deprecated_warnings=$(echo "$deprecated_output" | grep "^DEPRECATED_TERM_WARNINGS:" | head -1 | sed 's/.*: //')
    echo ""
fi

echo "PATTERNS_REQUIRING_ACTION: ${patterns_count:-0}"
echo "INFRASTRUCTURE_WARNINGS: ${infra_warnings:-0}"
echo "STATE_WARNINGS: ${state_warnings:-0}"
echo "SKILL_WARNINGS: ${skill_warnings:-0}"
echo "DEPRECATED_TERM_WARNINGS: ${deprecated_warnings:-0}"
echo ""
echo "=========================================="
