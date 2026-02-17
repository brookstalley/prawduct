#!/usr/bin/env bash
#
# governance-tracker.sh — PostToolUse hook for Edit/Write
#
# Silent bookkeeper: tracks edited files and governance state in
# .session-governance.json. No additionalContext injection — enforcement
# is handled by governance-gate.sh (blocking edits) and governance-stop.sh
# (blocking session completion).
#
# Hook protocol:
#   - Reads JSON from stdin (tool_name, tool_input with file_path)
#   - stdout: empty JSON or nothing (no advisory messages)
#   - exit 0: always (PostToolUse hooks are advisory, not blocking)

# No set -e or pipefail: hooks must never exit silently on any bash version.
# -u catches undefined variable typos.
set -u

# Read the hook input JSON from stdin
input=$(cat)

# Extract the file path from the tool input
file_path=$(echo "$input" | python3 -c "
import json, sys
data = json.load(sys.stdin)
tool_input = data.get('tool_input', {})
print(tool_input.get('file_path', ''))
" 2>/dev/null || echo "")

if [[ -z "$file_path" ]]; then
    exit 0
fi

# --- Resolve context ---

# Derive framework root from this script's location (hooks live at <framework>/.prawduct/hooks/)
FRAMEWORK_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
PRAWDUCT_DIR="${CLAUDE_PROJECT_DIR:-$repo_root}/.prawduct"
SESSION_FILE="$PRAWDUCT_DIR/.session-governance.json"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

mkdir -p "$PRAWDUCT_DIR"

# --- Classify the file ---

FRAMEWORK_PATTERNS=(
    "CLAUDE.md"
    "README.md"
    "skills/"
    "templates/"
    "docs/"
    "scripts/"
    "tools/"
    ".prawduct/hooks/"
    ".claude/settings.json"
    ".prawduct/framework-observations/README.md"
    ".prawduct/framework-observations/schema.yaml"
    ".prawduct/artifacts/"
)

is_framework_file=false
rel_path=""
if [[ -n "$repo_root" ]]; then
    rel_path="${file_path#"$repo_root"/}"
    # Only classify files as framework files in the framework repo
    if [[ "$repo_root" == "$FRAMEWORK_ROOT" ]]; then
        for pattern in "${FRAMEWORK_PATTERNS[@]}"; do
            if [[ "$rel_path" == $pattern* ]]; then
                is_framework_file=true
                break
            fi
        done
    fi
fi

# Check if file is in an active product build directory
is_product_file=false
if [[ -f "$SESSION_FILE" ]]; then
    product_dir=$(python3 -c "
import json
try:
    with open('$SESSION_FILE') as f:
        data = json.load(f)
    print(data.get('product_dir', ''))
except:
    print('')
" 2>/dev/null || echo "")

    if [[ -n "$product_dir" ]]; then
        norm_file=$(cd "$(dirname "$file_path")" 2>/dev/null && pwd)/$(basename "$file_path") 2>/dev/null || echo "$file_path"
        if [[ "$norm_file" == "$product_dir"* ]]; then
            is_product_file=true
        fi
    fi
fi

# If neither framework nor product file, exit silently
if [[ "$is_framework_file" == false && "$is_product_file" == false ]]; then
    exit 0
fi

# --- Track the edit (no advisory output) ---

python3 -c "
import json, sys, os

session_file = '$SESSION_FILE'
file_path = '$rel_path' if '$is_framework_file' == 'true' else '$file_path'
timestamp = '$TIMESTAMP'
is_framework = '$is_framework_file' == 'true'
is_product = '$is_product_file' == 'true'
basename_file = os.path.basename(file_path)

# Load or create session governance state
if os.path.exists(session_file):
    try:
        with open(session_file) as f:
            data = json.load(f)
    except:
        data = {}
else:
    data = {}

# Ensure structure
if 'framework_edits' not in data:
    data['framework_edits'] = {'files': [], 'total_edits': 0}
if 'governance_state' not in data:
    data['governance_state'] = {}

gov = data['governance_state']

if is_framework:
    # --- Framework file tracking ---
    edits = data['framework_edits']

    found = False
    for entry in edits['files']:
        if entry['path'] == file_path:
            entry['edit_count'] += 1
            entry['last_modified'] = timestamp
            found = True
            break
    if not found:
        edits['files'].append({
            'path': file_path,
            'first_modified': timestamp,
            'last_modified': timestamp,
            'edit_count': 1
        })
    edits['total_edits'] = edits.get('total_edits', 0) + 1

    # Maintain .critic-pending flag for critic-gate.sh
    prawduct_dir = '$PRAWDUCT_DIR'
    if prawduct_dir:
        pending_path = os.path.join(prawduct_dir, '.critic-pending')
        try:
            with open(pending_path, 'w') as f:
                f.write(timestamp)
        except:
            pass

    # DCP classification trigger: when 3+ distinct governed files are edited
    # without an active DCP, flag for classification. This mechanically enforces
    # the Stage 6 governance table (3+ files adding capability → DCP Enhancement).
    dc = data.get('directional_change', {})
    distinct_files = len(edits['files'])
    already_classified = dc.get('tier') is not None
    if distinct_files >= 3 and not dc.get('active', False) and not dc.get('needs_classification', False) and not already_classified:
        if 'directional_change' not in data:
            data['directional_change'] = {}
        data['directional_change']['needs_classification'] = True
        data['directional_change']['triggered_at_file_count'] = distinct_files

elif is_product:
    # --- Product file tracking ---
    if basename_file == 'project-state.yaml':
        try:
            import yaml
            with open('$file_path') as f:
                ps = yaml.safe_load(f)

            if ps:
                build_plan = ps.get('build_plan', {})
                chunks = build_plan.get('chunks', [])
                build_state = ps.get('build_state', {})
                reviews = build_state.get('reviews', [])

                reviewed_chunks = set()
                for review in reviews:
                    chunk_name = review.get('chunk', review.get('after_chunk', ''))
                    if chunk_name:
                        reviewed_chunks.add(chunk_name)

                unreviewed = []
                for chunk in chunks:
                    status = chunk.get('status', 'pending')
                    name = chunk.get('name', chunk.get('id', ''))
                    if status in ('complete', 'review') and name not in reviewed_chunks:
                        unreviewed.append(name)

                gov['chunks_completed_without_review'] = len(unreviewed) if unreviewed else 0

                # Track stage transitions
                current_stage = ps.get('current_stage', '')
                last_frp_stage = gov.get('last_frp_stage', '')
                if current_stage and last_frp_stage and current_stage != last_frp_stage:
                    gov['stage_transitions_without_frp'] = gov.get('stage_transitions_without_frp', 0) + 1

                # Track governance checkpoints
                checkpoints = build_plan.get('governance_checkpoints', [])
                completed_chunk_count = sum(1 for c in chunks if c.get('status') == 'complete')
                overdue_checkpoints = []
                for cp in checkpoints:
                    trigger = cp.get('after_chunk', cp.get('trigger', ''))
                    completed = cp.get('completed', False)
                    if not completed:
                        if isinstance(trigger, int) and completed_chunk_count >= trigger:
                            overdue_checkpoints.append(f'after chunk {trigger}')
                        elif isinstance(trigger, str):
                            for chunk in chunks:
                                if chunk.get('name', chunk.get('id', '')) == trigger and chunk.get('status') == 'complete':
                                    overdue_checkpoints.append(f'after \"{trigger}\"')
                                    break
                gov['governance_checkpoints_due'] = overdue_checkpoints

        except ImportError:
            pass
        except Exception:
            pass
    else:
        # Light path: non-project-state.yaml product file
        gov['product_files_changed'] = gov.get('product_files_changed', 0) + 1
        gov['last_product_file_edit'] = timestamp

gov['last_updated'] = timestamp
data['governance_state'] = gov

# Write updated state
try:
    with open(session_file, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
except:
    pass
" 2>/dev/null

exit 0
