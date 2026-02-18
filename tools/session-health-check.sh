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
import sys, os
sys.path.insert(0, '$SCRIPT_DIR')
import obs_utils

obs_dir = '$OBS_DIR'
if not os.path.isdir(obs_dir):
    print('  (framework-observations/ not found)')
    print('PATTERNS_REQUIRING_ACTION: 0')
    sys.exit(0)

files = obs_utils.find_observation_files(obs_dir)
if not files:
    print('  No observation files found.')
    print('PATTERNS_REQUIRING_ACTION: 0')
    sys.exit(0)

all_obs = obs_utils.parse_observations(files)
patterns = obs_utils.detect_patterns(all_obs)

if patterns:
    for p in patterns:
        print(f\"  PATTERN: {p['type']} ({p['active_count']} active of {p['total_count']} total, {p['tier']} threshold: {p['threshold']}+)\")
        if p['skills']:
            print(f\"    Affected skills: {', '.join(p['skills'])}\")
        for action in p['actions']:
            print(f'    -> {action}')
        print()
else:
    pass  # Silence when no actionable patterns

print(f'PATTERNS_REQUIRING_ACTION: {len(patterns)}')
" 2>/dev/null || echo "  (python3/yaml not available for pattern analysis)
PATTERNS_REQUIRING_ACTION: 0")

# Extract the count for use by callers
patterns_count=$(echo "$actionable_output" | grep "^PATTERNS_REQUIRING_ACTION:" | head -1 | sed 's/.*: //')

filtered_actionable=$(echo "$actionable_output" | grep -v "^PATTERNS_REQUIRING_ACTION:" | grep -v "^$")
if [[ -n "$filtered_actionable" ]]; then
    echo "## Actionable Observation Patterns"
    echo "$filtered_actionable"
    echo ""
fi

# If --actionable-only, skip non-pattern sections
if [[ "$MODE" == "--actionable-only" ]]; then
    echo "PATTERNS_REQUIRING_ACTION: ${patterns_count:-0}"
    exit 0
fi

# --- 2. Backlog status from project-state.yaml ---

backlog_output=""
if [[ -f "$PROJECT_STATE" ]]; then
    # Extract priority: next items (only output if items exist)
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
except Exception as e:
    print(f'  (Could not parse backlog: {e})')
" 2>/dev/null || true)
    if [[ -n "$next_items" ]]; then
        backlog_output+="$next_items"$'\n'
    fi

    # Check triage freshness (only output warnings)
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
except Exception as e:
    print(f'  (Could not check triage: {e})')
" 2>/dev/null || true)
    if [[ -n "$triage_info" ]]; then
        backlog_output+="$triage_info"$'\n'
    fi

    # Check for stale deferred items (>4 weeks) — reads from split file if available
    stale_info=$(python3 -c "
import yaml, sys, os
from datetime import datetime, timedelta
try:
    with open('$PROJECT_STATE') as f:
        data = yaml.safe_load(f)
    backlog = data.get('observation_backlog', {})
    deferred_file = backlog.get('deferred_file') or data.get('deferred_backlog_file')
    deferred = []
    if deferred_file:
        deferred_path = os.path.join(os.path.dirname('$PROJECT_STATE'), deferred_file)
        if os.path.isfile(deferred_path):
            with open(deferred_path) as df:
                deferred_data = yaml.safe_load(df)
            deferred = deferred_data.get('deferred_items', []) if deferred_data else []
    if not deferred:
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
except Exception as e:
    print(f'  (Could not check deferred items: {e})')
" 2>/dev/null || true)
    if [[ -n "$stale_info" ]]; then
        backlog_output+="$stale_info"$'\n'
    fi
fi

if [[ -n "$backlog_output" ]]; then
    echo "## Observation Backlog"
    echo "$backlog_output"
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

# --- 3b. Uncontributed observations (product repos only) ---

uncontributed_count=0
# Only check for non-self-hosted repos (product repos with a framework-path)
if [[ -f "$PRODUCT_ROOT/framework-path" ]]; then
    # Verify this isn't self-hosted (framework-path doesn't point to self)
    fw_path=$(cat "$PRODUCT_ROOT/framework-path" 2>/dev/null || echo "")
    fw_repo_root=""
    if [[ -n "$fw_path" && -d "$fw_path" ]]; then
        fw_repo_root=$(cd "$fw_path" && git rev-parse --show-toplevel 2>/dev/null || echo "")
    fi
    if [[ -n "$fw_repo_root" && "$fw_repo_root" != "$REPO_ROOT" ]]; then
        contrib_check=$("$SCRIPT_DIR/contribute-observations.sh" --check "$REPO_ROOT" 2>/dev/null || echo '{}')
        uncontributed_count=$(echo "$contrib_check" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print(data.get('uncontributed_count', 0))
except:
    print(0)
" 2>/dev/null || echo "0")
        if [[ "${uncontributed_count:-0}" -gt 0 ]]; then
            echo "## Uncontributed Observations"
            echo "  $uncontributed_count observation file(s) have not been contributed to the framework."
            echo "  The Orchestrator can help submit these during session resumption."
            echo ""
        fi
    fi
fi

# --- 4. Session edits pending review ---

SESSION_GOV="$REPO_ROOT/.prawduct/.session-governance.json"
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

# --- 5. Divergence Detection ---

divergence_warnings=0

divergence_output=$(python3 -c "
import subprocess, sys, os
from datetime import datetime, timedelta

repo_root = '$REPO_ROOT'
product_root = '$PRODUCT_ROOT'
warnings = 0

# Get last .prawduct/ commit date
try:
    result = subprocess.run(
        ['git', '-C', repo_root, 'log', '-1', '--format=%aI', '--', '.prawduct/'],
        capture_output=True, text=True, timeout=10
    )
    last_prawduct_commit = result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None
except:
    last_prawduct_commit = None

# Get last source commit date (anything outside .prawduct/)
try:
    # Count source commits since last .prawduct/ commit
    if last_prawduct_commit:
        result = subprocess.run(
            ['git', '-C', repo_root, 'rev-list', '--count',
             '--after=' + last_prawduct_commit, 'HEAD', '--',
             '.', ':!.prawduct/'],
            capture_output=True, text=True, timeout=10
        )
        source_commits_since = int(result.stdout.strip()) if result.returncode == 0 and result.stdout.strip() else 0
    else:
        source_commits_since = 0

    result = subprocess.run(
        ['git', '-C', repo_root, 'log', '-1', '--format=%aI', '--',
         '.', ':!.prawduct/'],
        capture_output=True, text=True, timeout=10
    )
    last_source_commit = result.stdout.strip() if result.returncode == 0 and result.stdout.strip() else None
except:
    source_commits_since = 0
    last_source_commit = None

if last_prawduct_commit:
    print(f'  Last .prawduct/ commit: {last_prawduct_commit[:10]}')
else:
    print('  Last .prawduct/ commit: (none found)')

if last_source_commit:
    print(f'  Last source commit: {last_source_commit[:10]}')
else:
    print('  Last source commit: (none found)')

if source_commits_since > 0:
    print(f'  Source commits since last artifact update: {source_commits_since}')
    if source_commits_since >= 10:
        print(f'  WARNING: {source_commits_since} source commits since last .prawduct/ update. Artifacts may be stale.')
        warnings += 1
    elif source_commits_since >= 5:
        print(f'  NOTE: {source_commits_since} source commits since last artifact update.')

# Check time since last .prawduct/ modification
if last_prawduct_commit:
    try:
        prawduct_date = datetime.fromisoformat(last_prawduct_commit.replace('Z', '+00:00')).replace(tzinfo=None)
        age_days = (datetime.now() - prawduct_date).days
        if age_days > 7:
            print(f'  WARNING: .prawduct/ last updated {age_days} days ago. Consider a consistency review.')
            warnings += 1
    except:
        pass

print(f'DIVERGENCE_WARNINGS: {warnings}')
" 2>/dev/null || echo "DIVERGENCE_WARNINGS: 0")

divergence_warnings=$(echo "$divergence_output" | grep "^DIVERGENCE_WARNINGS:" | head -1 | sed 's/.*: //')
divergence_content=$(echo "$divergence_output" | grep -v "^DIVERGENCE_WARNINGS:" | grep -v "^$")
if [[ "${divergence_warnings:-0}" -gt 0 && -n "$divergence_content" ]]; then
    echo "## Divergence Signals"
    echo "$divergence_content"
    echo ""
fi

# --- 6. Infrastructure Health ---

infra_warnings=0

infra_output=$(python3 -c "
import sys, os, glob
sys.path.insert(0, '$SCRIPT_DIR')
import obs_utils
from datetime import datetime

obs_dir = '$OBS_DIR'
archive_dir = os.path.join(obs_dir, 'archive')
working_notes_dir = os.path.join('$PRODUCT_ROOT', 'working-notes')
warnings = 0

# --- Observation directory ---
active_files = obs_utils.find_observation_files(obs_dir)
archived_files = glob.glob(os.path.join(archive_dir, '*.yaml')) if os.path.isdir(archive_dir) else []
print(f'  framework-observations/: {len(active_files)} active files, {len(archived_files)} archived')

if len(active_files) > 50:
    print(f'  WARNING: {len(active_files)} active observation files (threshold: 50).')
    warnings += 1

# --- Archive backlog ---
archivable = obs_utils.find_archivable(obs_dir)
if archivable:
    print(f'  WARNING: {len(archivable)} file(s) ready to archive. Run: tools/update-observation-status.sh --archive-all')
    warnings += 1

# --- Stale observations ---
all_obs = obs_utils.parse_observations(active_files)
now = datetime.now()
oldest_unresolved = None
stale_noted = 0
for obs in all_obs:
    if obs.get('status', 'noted') == 'noted':
        ts = obs.get('_timestamp', '')
        if ts:
            try:
                obs_date = datetime.fromisoformat(ts.replace('Z', '+00:00')).replace(tzinfo=None)
                age_days = (now - obs_date).days
                if age_days > 30:
                    stale_noted += 1
                if oldest_unresolved is None or obs_date < oldest_unresolved:
                    oldest_unresolved = obs_date
            except:
                pass

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
    stale_wn = sum(1 for wf in wn_files if (now - datetime.fromtimestamp(os.path.getmtime(os.path.join(working_notes_dir, wf)))).days > 14)
    if wn_files:
        print(f'  working-notes/: {len(wn_files)} file(s), {stale_wn} older than 14 days')
        if stale_wn > 0:
            print(f'  WARNING: {stale_wn} working note(s) older than 14 days. Incorporate into Tier 1 or delete.')
            warnings += 1

print(f'INFRASTRUCTURE_WARNINGS: {warnings}')
" 2>/dev/null || echo "  (python3/yaml not available for infrastructure health check)
INFRASTRUCTURE_WARNINGS: 0")

infra_warnings=$(echo "$infra_output" | grep "^INFRASTRUCTURE_WARNINGS:" | head -1 | sed 's/.*: //')
if [[ "${infra_warnings:-0}" -gt 0 ]]; then
    echo "## Infrastructure Health"
    echo "$infra_output" | grep -v "^INFRASTRUCTURE_WARNINGS:" | grep -E "WARNING|ALERT"
    echo ""
fi

# --- 7. Project State File Health ---

state_warnings=0
if [[ -f "$PROJECT_STATE" ]]; then
    state_health_output=$(python3 -c "
import yaml, sys

state_file = '$PROJECT_STATE'
warnings = 0
msgs = []

try:
    with open(state_file) as f:
        data = yaml.safe_load(f)

    cl = data.get('change_log', []) or []
    if len(cl) > 10:
        msgs.append(f'  change_log: {len(cl)} entries (compact with tools/compact-project-state.sh)')
        warnings += 1

    bp = data.get('build_plan', {}) or {}
    chunks = bp.get('chunks', []) or []
    chunks_complete = sum(1 for c in chunks if c.get('status') == 'complete')
    if chunks_complete > 20:
        msgs.append(f'  build_plan.chunks: {chunks_complete} compaction-eligible')
        warnings += 1

    bs = data.get('build_state', {}) or {}
    reviews = bs.get('reviews', []) or []
    reviews_resolved = sum(1 for r in reviews
                          if all(f.get('status') in ('resolved', 'deferred')
                                 for f in r.get('findings', [])))
    if reviews_resolved > 20:
        msgs.append(f'  build_state.reviews: {reviews_resolved} compaction-eligible')
        warnings += 1

    it = data.get('iteration_state', {}) or {}
    fc = it.get('feedback_cycles', []) or []
    fc_complete = sum(1 for c in fc if c.get('status') == 'complete')
    if fc_complete > 10:
        msgs.append(f'  feedback_cycles: {fc_complete} completed (compact)')
        warnings += 1

    for m in msgs:
        print(m)

except Exception as e:
    print(f'  (Could not analyze project state: {e})')

print(f'STATE_WARNINGS: {warnings}')
" 2>/dev/null || echo "STATE_WARNINGS: 0")

    state_warnings=$(echo "$state_health_output" | grep "^STATE_WARNINGS:" | head -1 | sed 's/.*: //')
    if [[ "${state_warnings:-0}" -gt 0 ]]; then
        echo "## Project State Health"
        echo "$state_health_output" | grep -v "^STATE_WARNINGS:"
        echo ""
    fi
fi

# --- 8. Skill File Health ---

skill_warnings=0

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

print(f'SKILL_WARNINGS: {warnings}')
" 2>/dev/null || echo "SKILL_WARNINGS: 0")

skill_warnings=$(echo "$skill_health_output" | grep "^SKILL_WARNINGS:" | head -1 | sed 's/.*: //')
if [[ "${skill_warnings:-0}" -gt 0 ]]; then
    echo "## Skill File Health"
    echo "$skill_health_output" | grep -v "^SKILL_WARNINGS:" | grep -v "^$"
    echo ""
fi

# --- 9. Deprecated Term Scanning ---

deprecated_warnings=0
if [[ -f "$PROJECT_STATE" ]]; then
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
        print('DEPRECATED_TERM_WARNINGS: 0')
        sys.exit(0)

    # Exclusion patterns: historical records
    exclude_dirs = ['eval-history', 'framework-observations/archive', '.prawduct/framework-observations/archive', 'working-notes', '.prawduct/working-notes', '.git', '.claude']

    # For project-state.yaml, we need to exclude change_log and deprecated_terms sections
    # We'll handle this by post-filtering matches in project-state.yaml
    # state_file may be at .prawduct/project-state.yaml — compute its rel_path for matching
    state_rel_path = os.path.relpath(state_file, repo_root)

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
                        if 'framework-observations/' in rel_path:
                            basename = os.path.basename(rel_path)
                            if basename.endswith('.yaml') and basename != 'schema.yaml':
                                continue

                        # Skip project-state.yaml matches in excluded sections
                        if rel_path == state_rel_path:
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

    print(f'DEPRECATED_TERM_WARNINGS: {total_warnings}')

except Exception as e:
    print(f'  (Could not scan deprecated terms: {e})')
    print('DEPRECATED_TERM_WARNINGS: 0')
" 2>/dev/null || echo "DEPRECATED_TERM_WARNINGS: 0")

    deprecated_warnings=$(echo "$deprecated_output" | grep "^DEPRECATED_TERM_WARNINGS:" | head -1 | sed 's/.*: //')
    if [[ "${deprecated_warnings:-0}" -gt 0 ]]; then
        echo "## Deprecated Term Scanning"
        echo "$deprecated_output" | grep -v "^DEPRECATED_TERM_WARNINGS:" | grep -v "^$"
        echo ""
    fi
fi

# --- 10. Dependency Graph Consistency ---

dep_graph_warnings=0
if [[ -f "$PROJECT_STATE" ]]; then
    dep_graph_output=$(python3 -c "
import yaml, sys, os

state_file = '$PROJECT_STATE'
warnings = 0

try:
    with open(state_file) as f:
        data = yaml.safe_load(f)
    # Load manifest from split file if pointer exists, else fall back to inline
    manifest = None
    manifest_file = data.get('artifact_manifest_file')
    if manifest_file:
        manifest_path = os.path.join(os.path.dirname(state_file), manifest_file)
        if os.path.isfile(manifest_path):
            with open(manifest_path) as mf:
                manifest = yaml.safe_load(mf) or {}
    if manifest is None:
        manifest = data.get('artifact_manifest', {})
    if not manifest:
        print('  (No artifact_manifest found)')
        print('DEP_GRAPH_WARNINGS: 0')
        sys.exit(0)

    # Collect all entries across all manifest categories
    all_entries = {}
    categories = ['human_docs', 'source_components', 'tooling', 'artifacts', 'test_specs']
    for cat in categories:
        entries = manifest.get(cat, []) or []
        for entry in entries:
            name = entry.get('name')
            if name:
                all_entries[name] = {
                    'depends_on': entry.get('depends_on', []) or [],
                    'depended_on_by': entry.get('depended_on_by', []) or [],
                    'has_depended_on_by': 'depended_on_by' in entry,
                    'category': cat
                }

    if not all_entries:
        print('  (No manifest entries found)')
        print('DEP_GRAPH_WARNINGS: 0')
        sys.exit(0)

    # Compute correct depended_on_by from depends_on
    computed_dob = {name: set() for name in all_entries}
    for name, info in all_entries.items():
        for dep in info['depends_on']:
            # depends_on may be a string or dict with 'artifact' key
            dep_name = dep.get('artifact') if isinstance(dep, dict) else dep
            if dep_name and dep_name in computed_dob:
                computed_dob[dep_name].add(name)

    # Compare declared vs computed (only for entries that declare depended_on_by)
    mismatches = []
    for name, info in all_entries.items():
        if not info['has_depended_on_by']:
            continue  # Skip entries that don't track reverse dependencies
        declared = set()
        for d in info['depended_on_by']:
            d_name = d.get('artifact') if isinstance(d, dict) else d
            if d_name:
                declared.add(d_name)
        computed = computed_dob.get(name, set())

        if declared != computed:
            missing = computed - declared
            extra = declared - computed
            mismatches.append({
                'name': name,
                'category': info['category'],
                'missing': sorted(missing),
                'extra': sorted(extra)
            })

    if mismatches:
        print(f'  WARNING: {len(mismatches)} depended_on_by inconsistencies detected:')
        for m in mismatches:
            parts = []
            if m['missing']:
                parts.append(f\"missing: {', '.join(m['missing'])}\")
            if m['extra']:
                parts.append(f\"extra: {', '.join(m['extra'])}\")
            print(f\"    {m['name']} ({m['category']}): {'; '.join(parts)}\")
        warnings = len(mismatches)
        print(f'  ACTION: Fix depended_on_by in project-state.yaml to match inverse of depends_on.')
    print(f'DEP_GRAPH_WARNINGS: {warnings}')

except Exception as e:
    print(f'  (Could not validate dependency graph: {e})')
    print('DEP_GRAPH_WARNINGS: 0')
" 2>/dev/null || echo "DEP_GRAPH_WARNINGS: 0")

    dep_graph_warnings=$(echo "$dep_graph_output" | grep "^DEP_GRAPH_WARNINGS:" | head -1 | sed 's/.*: //')
    if [[ "${dep_graph_warnings:-0}" -gt 0 ]]; then
        echo "## Dependency Graph Consistency"
        echo "$dep_graph_output" | grep -v "^DEP_GRAPH_WARNINGS:" | grep -v "^$"
        echo ""
    fi
fi

# --- Session length check: suggest /compact when beneficial ---
if [[ -f "$SESSION_GOV" ]]; then
    total_edits=$(python3 -c "
import json
try:
    with open('$SESSION_GOV') as f:
        data = json.load(f)
    print(data.get('framework_edits', {}).get('total_edits', 0))
except:
    print(0)
" 2>/dev/null || echo "0")
    if [[ "${total_edits:-0}" -gt 15 ]]; then
        echo "## Context Management"
        echo "  NOTE: $total_edits edits this session. Consider /compact to free context before continuing."
        echo ""
    fi
fi

echo "PATTERNS_REQUIRING_ACTION: ${patterns_count:-0}"
echo "INFRASTRUCTURE_WARNINGS: ${infra_warnings:-0}"
echo "STATE_WARNINGS: ${state_warnings:-0}"
echo "SKILL_WARNINGS: ${skill_warnings:-0}"
echo "DIVERGENCE_WARNINGS: ${divergence_warnings:-0}"
echo "DEPRECATED_TERM_WARNINGS: ${deprecated_warnings:-0}"
echo "DEP_GRAPH_WARNINGS: ${dep_graph_warnings:-0}"
echo "UNCONTRIBUTED_OBSERVATIONS: ${uncontributed_count:-0}"
echo ""
echo "=========================================="
