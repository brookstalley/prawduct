#!/usr/bin/env bash
#
# product-chunk-gate.sh — PreToolUse hook for Edit/Write (product builds)
#
# Fires before every Edit or Write tool call. Blocks edits to product files
# when completed chunks lack Critic review. This is the mechanical enforcement
# that prevents chunk progression without governance review.
#
# The PostToolUse tracker (product-governance-tracker.sh) accumulates governance
# state in .product-session.json. This hook reads that state and blocks when
# chunks_completed_without_review > 0.
#
# Exceptions (not blocked):
#   - Edits to project-state.yaml (needed to record review results)
#   - Edits to files outside the product directory
#   - No active product session
#
# Hook protocol:
#   - Reads JSON from stdin (tool_name, tool_input with file_path)
#   - exit 0: allow the tool call
#   - exit 2: deny the tool call (stderr message shown to Claude)

set -euo pipefail

# --- Fast path: check for active product session ---

# $CLAUDE_PROJECT_DIR is set by Claude Code to the directory where it was launched.
if [[ -z "${CLAUDE_PROJECT_DIR:-}" ]]; then
    exit 0
fi

SESSION_FILE="$CLAUDE_PROJECT_DIR/.claude/.product-session.json"
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
import json
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

# Check if file is under product directory
if [[ "$norm_file" != "$product_dir"* ]]; then
    exit 0
fi

# --- Exception: always allow edits to project-state.yaml (needed to record reviews) ---

basename_file=$(basename "$file_path")
if [[ "$basename_file" == "project-state.yaml" ]]; then
    exit 0
fi

# --- Check governance state ---

result=$(python3 -c "
import json, sys

session_file = '$SESSION_FILE'
try:
    with open(session_file) as f:
        session = json.load(f)
except:
    sys.exit(0)

gov = session.get('governance_state', {})

# Block when chunks have been completed without Critic review
chunks_without_review = gov.get('chunks_completed_without_review', 0)
if chunks_without_review > 0:
    print(f'BLOCKED: {chunks_without_review} chunk(s) completed without Critic review.')
else:
    print('')
" 2>/dev/null || echo "")

if [[ -n "$result" && "$result" != "" ]]; then
    echo "" >&2
    echo "$result" >&2
    echo "" >&2
    echo "Product file edits are blocked until governance debt is resolved." >&2
    echo "" >&2
    echo "To unblock:" >&2
    echo "  1. Run Critic review (skills/critic/SKILL.md Mode 2) on completed chunks" >&2
    echo "  2. Record findings in project-state.yaml build_state.reviews" >&2
    echo "  3. Update .claude/.product-session.json governance_state.chunks_completed_without_review to 0" >&2
    exit 2
fi

exit 0
