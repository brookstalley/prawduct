#!/usr/bin/env bash
#
# framework-edit-tracker.sh — PostToolUse hook for Edit/Write
#
# Fires after every Edit or Write tool call. Checks whether the modified file
# is a framework file (skills/, templates/, docs/, CLAUDE.md, etc.). If so,
# tracks the edit in .claude/.session-edits.json (for the commit gate to verify
# coverage) and outputs escalating governance reminders to stderr.
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
file_path=$(echo "$input" | python3 -c "
import json, sys
data = json.load(sys.stdin)
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
    "tools/"
    ".claude/hooks/"
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

# --- Track edit in .session-edits.json ---

mkdir -p "$repo_root/.claude"
SESSION_EDITS="$repo_root/.claude/.session-edits.json"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Update session edits tracking file
python3 -c "
import json, sys, os

edits_file = '$SESSION_EDITS'
rel_path = '$rel_path'
timestamp = '$TIMESTAMP'

# Load existing or create new
if os.path.exists(edits_file):
    try:
        with open(edits_file) as f:
            data = json.load(f)
    except:
        data = {'files': [], 'total_edits': 0}
else:
    data = {'files': [], 'total_edits': 0}

# Update file entry
found = False
for entry in data['files']:
    if entry['path'] == rel_path:
        entry['edit_count'] += 1
        entry['last_modified'] = timestamp
        found = True
        break

if not found:
    data['files'].append({
        'path': rel_path,
        'first_modified': timestamp,
        'last_modified': timestamp,
        'edit_count': 1
    })

data['total_edits'] = data.get('total_edits', 0) + 1

with open(edits_file, 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')

# Output the total edit count for the shell script
print(data['total_edits'])
print(len(data['files']))
" 2>/dev/null

# Read current counts for escalating reminders
total_edits=0
file_count=0
if [[ -f "$SESSION_EDITS" ]]; then
    counts=$(python3 -c "
import json
try:
    with open('$SESSION_EDITS') as f:
        data = json.load(f)
    print(data.get('total_edits', 0))
    print(len(data.get('files', [])))
except:
    print(0)
    print(0)
" 2>/dev/null || echo "0"$'\n'"0")
    total_edits=$(echo "$counts" | head -1)
    file_count=$(echo "$counts" | tail -1)
fi

# Also maintain backward-compatible .critic-pending flag
touch "$repo_root/.claude/.critic-pending"

# --- Escalating reminders to stderr ---

echo "Framework file modified: $rel_path" >&2

if [[ "$total_edits" -ge 3 ]]; then
    # Urgent: 3+ edits without governance
    echo "" >&2
    echo "URGENT: $total_edits framework edits across $file_count file(s) without Critic review." >&2
    echo "Modified files:" >&2
    python3 -c "
import json
try:
    with open('$SESSION_EDITS') as f:
        data = json.load(f)
    for entry in data.get('files', []):
        print(f\"  - {entry['path']} ({entry['edit_count']} edits)\")
except:
    pass
" 2>/dev/null >&2
    echo "Run Critic (skills/critic/SKILL.md) and record findings via tools/record-critic-findings.sh before committing." >&2
else
    # Advisory: 1-2 edits
    echo "Run Critic (skills/critic/SKILL.md) as a standalone step before committing." >&2
fi

exit 0
