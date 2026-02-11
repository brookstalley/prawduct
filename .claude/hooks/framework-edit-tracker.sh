#!/usr/bin/env bash
#
# framework-edit-tracker.sh — PostToolUse hook for Edit/Write
#
# Fires after every Edit or Write tool call. Checks whether the modified file
# is a framework file (skills/, templates/, docs/, CLAUDE.md, etc.). If so,
# outputs a governance reminder to stderr (which enters Claude's context) and
# touches a .critic-pending flag for the commit gate to check.
#
# Hook protocol:
#   - Reads JSON from stdin (tool_name, tool_input with file_path)
#   - stdout: ignored for PostToolUse
#   - stderr: message shown to Claude as tool feedback
#   - exit 0: always (PostToolUse hooks are advisory, not blocking)

set -euo pipefail

# Read the hook input JSON from stdin
input=$(cat)

# Extract the file path from the tool input
# Edit uses "file_path", Write uses "file_path"
file_path=$(echo "$input" | python3 -c "
import json, sys
data = json.load(sys.stdin)
# tool_input contains the parameters passed to the tool
tool_input = data.get('tool_input', {})
print(tool_input.get('file_path', ''))
" 2>/dev/null || echo "")

if [[ -z "$file_path" ]]; then
    exit 0
fi

# Resolve to a path relative to the repo root
repo_root=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -z "$repo_root" ]]; then
    exit 0
fi

# Make the path relative to repo root for pattern matching
rel_path="${file_path#"$repo_root"/}"

# Framework file patterns — same as tools/critic-reminder.sh
FRAMEWORK_PATTERNS=(
    "CLAUDE.md"
    "skills/"
    "templates/"
    "docs/"
    "scripts/"
    "framework-observations/README.md"
    "framework-observations/schema.yaml"
)

is_framework_file=false
for pattern in "${FRAMEWORK_PATTERNS[@]}"; do
    if [[ "$rel_path" == $pattern* ]]; then
        is_framework_file=true
        break
    fi
done

if [[ "$is_framework_file" == false ]]; then
    exit 0
fi

# Touch the pending flag so the commit gate knows framework files were modified
mkdir -p "$repo_root/.claude"
touch "$repo_root/.claude/.critic-pending"

# Output reminder to stderr — this enters Claude's context as tool feedback
echo "Framework file modified: $rel_path" >&2
echo "Run Critic (skills/critic/SKILL.md Mode 1) as a standalone step before committing." >&2

exit 0
