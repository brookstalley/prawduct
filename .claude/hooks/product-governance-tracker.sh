#!/usr/bin/env bash
#
# product-governance-tracker.sh — PostToolUse hook for Edit/Write (product builds)
#
# Fires after every Edit or Write tool call. Tracks governance state for product
# builds and injects reminders when governance debt accumulates.
#
# Fast path: exits in <5ms when no product session is active.
#
# When the edited file is the product's project-state.yaml, parses it to detect:
#   - Chunks with status "complete"/"review" without Critic review → reminder
#   - Stage transitions without FRP change_log entries → reminder
# For non-project-state.yaml product files: increments changed-files counter;
# reminds about observations after 10+ files with zero captures.
#
# Hook protocol:
#   - Reads JSON from stdin (tool_name, tool_input with file_path)
#   - stdout: JSON with additionalContext (injected into Claude's context)
#   - stderr: ignored for PostToolUse (additionalContext is the primary channel)
#   - exit 0: always (PostToolUse hooks are advisory, not blocking)

set -euo pipefail

# --- Fast path: check for active product session ---

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -z "$REPO_ROOT" ]]; then
    exit 0
fi

SESSION_FILE="$REPO_ROOT/.claude/.product-session.json"
if [[ ! -f "$SESSION_FILE" ]]; then
    exit 0
fi

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

# --- Check if file is in the product directory ---

product_dir=$(python3 -c "
import json, sys
try:
    with open('$SESSION_FILE') as f:
        data = json.load(f)
    print(data.get('product_dir', ''))
except:
    print('')
" 2>/dev/null || echo "")

if [[ -z "$product_dir" ]]; then
    exit 0
fi

# Normalize paths for comparison
norm_file=$(cd "$(dirname "$file_path")" 2>/dev/null && pwd)/$(basename "$file_path") 2>/dev/null || echo "$file_path"
norm_product="$product_dir"

# Check if file is under product directory
if [[ "$norm_file" != "$norm_product"* ]]; then
    exit 0
fi

# --- File is in the product directory. Check what it is. ---

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
basename_file=$(basename "$file_path")

if [[ "$basename_file" == "project-state.yaml" ]]; then
    # --- Heavy path: parse project-state.yaml for governance debt ---

    governance_context=$(python3 -c "
import json, sys, os

session_file = '$SESSION_FILE'
project_state_file = '$file_path'

try:
    with open(session_file) as f:
        session = json.load(f)
except:
    session = {'governance_state': {}}

gov = session.get('governance_state', {})
messages = []

# Parse project-state.yaml for governance signals
try:
    # Use a simple YAML parser approach - look for key patterns
    import yaml
    with open(project_state_file) as f:
        ps = yaml.safe_load(f)

    if ps:
        # Check for chunks without Critic review
        build_plan = ps.get('build_plan', {})
        chunks = build_plan.get('chunks', [])
        build_state = ps.get('build_state', {})
        reviews = build_state.get('reviews', [])

        # Get reviewed chunk names
        reviewed_chunks = set()
        for review in reviews:
            chunk_name = review.get('chunk', '')
            if chunk_name:
                reviewed_chunks.add(chunk_name)

        # Find chunks that are complete/review without a Critic review
        unreviewed = []
        for chunk in chunks:
            status = chunk.get('status', 'pending')
            name = chunk.get('name', chunk.get('id', ''))
            if status in ('complete', 'review') and name not in reviewed_chunks:
                unreviewed.append(name)

        if unreviewed:
            gov['chunks_completed_without_review'] = len(unreviewed)
            gov['last_critic_review_chunk'] = gov.get('last_critic_review_chunk')
            chunks_str = ', '.join(unreviewed[:3])
            if len(unreviewed) > 3:
                chunks_str += f' (+{len(unreviewed) - 3} more)'
            messages.append(f'CRITIC REVIEW OVERDUE: {len(unreviewed)} chunk(s) completed without Critic review: {chunks_str}. Run Critic (skills/critic/SKILL.md Mode 2) before proceeding to next chunk.')
        else:
            gov['chunks_completed_without_review'] = 0

        # Check for stage transitions without FRP
        current_stage = ps.get('current_stage', '')
        last_frp_stage = gov.get('last_frp_stage', '')
        change_log = ps.get('change_log', [])

        # Look for FRP entries in change_log
        frp_stages = set()
        for entry in change_log:
            what = entry.get('what', '')
            if 'framework reflection' in what.lower() or 'frp' in what.lower():
                # Try to extract stage from the entry
                frp_stages.add(what)

        if current_stage and last_frp_stage and current_stage != last_frp_stage:
            # Stage has changed since last FRP
            stage_transitions = gov.get('stage_transitions_without_frp', 0) + 1
            gov['stage_transitions_without_frp'] = stage_transitions
            if stage_transitions >= 1:
                messages.append(f'FRP OVERDUE: Stage transitioned to \"{current_stage}\" without Framework Reflection. Run the Framework Reflection Protocol (see Orchestrator SKILL.md).')

        # Check governance checkpoints
        checkpoints = build_plan.get('governance_checkpoints', [])
        completed_chunk_count = sum(1 for c in chunks if c.get('status') == 'complete')
        overdue_checkpoints = []

        for cp in checkpoints:
            trigger = cp.get('after_chunk', cp.get('trigger', ''))
            completed = cp.get('completed', False)
            if not completed:
                # Check if this checkpoint should have been triggered
                if isinstance(trigger, int) and completed_chunk_count >= trigger:
                    overdue_checkpoints.append(f'after chunk {trigger}')
                    messages.append(f'GOVERNANCE CHECKPOINT OVERDUE: Checkpoint after chunk {trigger} has not been completed. Run cross-chunk review (Architecture, Skeptic, Testing lenses).')
                elif isinstance(trigger, str):
                    # Check if the named chunk is complete
                    for chunk in chunks:
                        if chunk.get('name', chunk.get('id', '')) == trigger and chunk.get('status') == 'complete':
                            overdue_checkpoints.append(f'after \"{trigger}\"')
                            messages.append(f'GOVERNANCE CHECKPOINT OVERDUE: Checkpoint after \"{trigger}\" has not been completed. Run cross-chunk review.')
                            break

        gov['governance_checkpoints_due'] = overdue_checkpoints

except ImportError:
    # No yaml module — can't parse, just track the edit
    pass
except Exception as e:
    # Don't fail the hook on parse errors
    pass

# Update session file
session['governance_state'] = gov
session['governance_state']['last_updated'] = '$TIMESTAMP'

try:
    with open(session_file, 'w') as f:
        json.dump(session, f, indent=2)
        f.write('\n')
except:
    pass

# Output messages
if messages:
    print('\\n'.join(messages))
else:
    print('')
" 2>/dev/null || echo "")

    if [[ -n "$governance_context" && "$governance_context" != "" ]]; then
        # Output additionalContext JSON to stdout
        python3 -c "
import json
msg = '''$governance_context'''
if msg.strip():
    print(json.dumps({'additionalContext': 'PRODUCT GOVERNANCE DEBT:\\n' + msg.strip()}))
" 2>/dev/null
    fi

else
    # --- Light path: non-project-state.yaml product file ---
    # Increment changed-files counter, remind about observations periodically

    reminder=$(python3 -c "
import json, sys, os

session_file = '$SESSION_FILE'
timestamp = '$TIMESTAMP'

try:
    with open(session_file) as f:
        session = json.load(f)
except:
    session = {'governance_state': {}}

gov = session.get('governance_state', {})

# Track product files changed
files_changed = gov.get('product_files_changed', 0) + 1
gov['product_files_changed'] = files_changed
gov['last_product_file_edit'] = timestamp

observations_count = gov.get('observations_captured_this_session', 0)

session['governance_state'] = gov

try:
    with open(session_file, 'w') as f:
        json.dump(session, f, indent=2)
        f.write('\n')
except:
    pass

# Remind about observations after 10+ files with zero captures
if files_changed >= 10 and observations_count == 0:
    if files_changed % 5 == 0:  # Remind every 5 files after threshold
        print(f'{files_changed} product files modified with 0 framework observations captured. If the build revealed anything about the framework (artifact gaps, missing guidance, process friction), capture an observation via tools/capture-observation.sh.')
" 2>/dev/null || echo "")

    if [[ -n "$reminder" ]]; then
        python3 -c "
import json
msg = '''$reminder'''
if msg.strip():
    print(json.dumps({'additionalContext': msg.strip()}))
" 2>/dev/null
    fi
fi

exit 0
