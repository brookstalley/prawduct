#!/usr/bin/env bash
#
# governance-tracker.sh — PostToolUse hook for Edit/Write
#
# Unified governance tracker that replaces framework-edit-tracker.sh and
# product-governance-tracker.sh. Fires after every Edit or Write tool call.
# Tracks edited files and governance debt in a single .session-governance.json
# file. Provides escalating reminders via additionalContext.
#
# All projects use the same tracking mechanism. The governance state file
# tracks framework edits, product edits, chunk review debt, FRP debt, and
# observation capture — in one place.
#
# Hook protocol:
#   - Reads JSON from stdin (tool_name, tool_input with file_path)
#   - stdout: JSON with additionalContext (injected into Claude's context)
#   - stderr: ignored for PostToolUse
#   - exit 0: always (PostToolUse hooks are advisory, not blocking)

set -euo pipefail

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

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
CLAUDE_DIR="${CLAUDE_PROJECT_DIR:-$repo_root}/.claude"
SESSION_FILE="$CLAUDE_DIR/.session-governance.json"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

mkdir -p "$CLAUDE_DIR"

# --- Classify the file ---

# Framework file patterns
FRAMEWORK_PATTERNS=(
    "CLAUDE.md"
    "skills/"
    "templates/"
    "docs/"
    "scripts/"
    "tools/"
    ".claude/hooks/"
    ".claude/settings.json"
    "framework-observations/README.md"
    "framework-observations/schema.yaml"
)

is_framework_file=false
rel_path=""
if [[ -n "$repo_root" ]]; then
    rel_path="${file_path#"$repo_root"/}"
    for pattern in "${FRAMEWORK_PATTERNS[@]}"; do
        if [[ "$rel_path" == $pattern* ]]; then
            is_framework_file=true
            break
        fi
    done
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

# --- Track the edit and produce governance context ---

result=$(python3 -c "
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
messages = []

if is_framework:
    # --- Framework file tracking ---
    edits = data['framework_edits']

    # Update file entry
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

    total_edits = edits['total_edits']
    file_count = len(edits['files'])

    if total_edits >= 3:
        file_list = ', '.join(e['path'] for e in edits['files'])
        messages.append(f'URGENT: {total_edits} framework edits across {file_count} file(s) without Critic review. Files: {file_list}. Run Critic (skills/critic/SKILL.md) and record findings via tools/record-critic-findings.sh before committing.')
    else:
        messages.append(f'Framework file modified: {file_path}. Run Critic as a standalone step before committing.')

    # Maintain .critic-pending flag for backward compatibility with critic-gate.sh
    repo_root_path = '$repo_root'
    if repo_root_path:
        pending_path = os.path.join(repo_root_path, '.claude', '.critic-pending')
        try:
            with open(pending_path, 'w') as f:
                f.write(timestamp)
        except:
            pass

elif is_product:
    # --- Product file tracking ---
    if basename_file == 'project-state.yaml':
        # Heavy path: parse project-state.yaml for governance debt
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

                if unreviewed:
                    gov['chunks_completed_without_review'] = len(unreviewed)
                    chunks_str = ', '.join(unreviewed[:3])
                    if len(unreviewed) > 3:
                        chunks_str += f' (+{len(unreviewed) - 3} more)'
                    messages.append(f'CRITIC REVIEW OVERDUE: {len(unreviewed)} chunk(s) completed without Critic review: {chunks_str}. Read skills/critic/SKILL.md from disk and apply Product Governance before proceeding.')
                else:
                    gov['chunks_completed_without_review'] = 0

                # Check stage transitions without FRP
                current_stage = ps.get('current_stage', '')
                last_frp_stage = gov.get('last_frp_stage', '')
                if current_stage and last_frp_stage and current_stage != last_frp_stage:
                    stage_transitions = gov.get('stage_transitions_without_frp', 0) + 1
                    gov['stage_transitions_without_frp'] = stage_transitions
                    if stage_transitions >= 1:
                        messages.append(f'FRP OVERDUE: Stage transitioned to \"{current_stage}\" without Framework Reflection.')

                # Check governance checkpoints
                checkpoints = build_plan.get('governance_checkpoints', [])
                completed_chunk_count = sum(1 for c in chunks if c.get('status') == 'complete')
                overdue_checkpoints = []
                for cp in checkpoints:
                    trigger = cp.get('after_chunk', cp.get('trigger', ''))
                    completed = cp.get('completed', False)
                    if not completed:
                        if isinstance(trigger, int) and completed_chunk_count >= trigger:
                            overdue_checkpoints.append(f'after chunk {trigger}')
                            messages.append(f'GOVERNANCE CHECKPOINT OVERDUE: Checkpoint after chunk {trigger} not completed.')
                        elif isinstance(trigger, str):
                            for chunk in chunks:
                                if chunk.get('name', chunk.get('id', '')) == trigger and chunk.get('status') == 'complete':
                                    overdue_checkpoints.append(f'after \"{trigger}\"')
                                    messages.append(f'GOVERNANCE CHECKPOINT OVERDUE: Checkpoint after \"{trigger}\" not completed.')
                                    break
                gov['governance_checkpoints_due'] = overdue_checkpoints

        except ImportError:
            pass
        except Exception:
            pass
    else:
        # Light path: non-project-state.yaml product file
        files_changed = gov.get('product_files_changed', 0) + 1
        gov['product_files_changed'] = files_changed
        gov['last_product_file_edit'] = timestamp
        observations_count = gov.get('observations_captured_this_session', 0)

        if files_changed > 0 and files_changed % 10 == 0:
            messages.append(f'{files_changed} product files modified. Have you updated project-state.yaml chunk status?')
        elif files_changed >= 10 and observations_count == 0 and files_changed % 5 == 0:
            messages.append(f'{files_changed} product files modified with 0 observations captured. If the build revealed anything about the framework, capture an observation via tools/capture-observation.sh.')

gov['last_updated'] = timestamp
data['governance_state'] = gov

# Write updated state
try:
    with open(session_file, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
except:
    pass

# Output messages
if messages:
    print('\n'.join(messages))
else:
    print('')
" 2>/dev/null || echo "")

if [[ -n "$result" && "$result" != "" ]]; then
    python3 -c "
import json
msg = '''$result'''
if msg.strip():
    print(json.dumps({'additionalContext': msg.strip()}))
" 2>/dev/null
fi

exit 0
