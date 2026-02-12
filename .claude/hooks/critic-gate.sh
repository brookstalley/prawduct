#!/usr/bin/env bash
#
# critic-gate.sh — PreToolUse hook for Bash (git commit gate)
#
# Fires before every Bash tool call. Only activates when the command is a
# git commit. Delegates to tools/critic-reminder.sh for the actual check.
# If framework files are staged without Critic evidence, denies the commit.
#
# Hook protocol:
#   - Reads JSON from stdin (tool_name, tool_input with command)
#   - exit 0: allow the tool call
#   - exit 2: deny the tool call (stderr message shown to Claude)

set -euo pipefail

# Read the hook input JSON from stdin
input=$(cat)

# Extract the bash command from tool_input
command=$(echo "$input" | python3 -c "
import json, sys
data = json.load(sys.stdin)
tool_input = data.get('tool_input', {})
print(tool_input.get('command', ''))
" 2>/dev/null || echo "")

# Only activate for git commit commands
# Match: git commit, git commit -m, git add ... && git commit, etc.
if ! echo "$command" | grep -qE '(^|&&\s*|;\s*)git\s+commit'; then
    exit 0
fi

# Resolve repo root
repo_root=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -z "$repo_root" ]]; then
    exit 0
fi

# Check for the .critic-pending flag — if it doesn't exist, no framework
# files were modified in this session, so no Critic review needed
if [[ ! -f "$repo_root/.claude/.critic-pending" ]]; then
    # No pending flag, but still run the check in case files were staged
    # outside this session (e.g., git add from terminal)
    :
fi

# Delegate to critic-reminder.sh for the actual governance check
# It checks staged files against framework patterns and looks for evidence
if "$repo_root/tools/critic-reminder.sh" 2>&1; then
    # Evidence found or no framework files staged — allow commit
    # Clean up the pending flag, stale findings, and session edits
    rm -f "$repo_root/.claude/.critic-pending"
    rm -f "$repo_root/.claude/.critic-findings.json"
    rm -f "$repo_root/.claude/.session-edits.json"
    exit 0
else
    # Framework files staged without Critic evidence — deny commit
    echo "" >&2
    echo "BLOCKED: Framework governance review required before committing." >&2
    echo "" >&2
    echo "Framework files are staged but no Critic review evidence was found." >&2
    echo "Run the Critic as a standalone step:" >&2
    echo "  1. Read skills/critic/SKILL.md" >&2
    echo "  2. Apply Framework Governance mode (all checks) to your changes" >&2
    echo "  3. Record findings, then retry the commit" >&2
    echo "  4. Include 'Framework Governance Review' in the commit message" >&2
    exit 2
fi
