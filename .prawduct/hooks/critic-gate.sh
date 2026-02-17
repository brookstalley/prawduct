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

# No set -e or pipefail: hooks must never exit silently on any bash version.
# -u catches undefined variable typos.
set -u

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

# Derive framework root from this script's location (hooks live at <framework>/.prawduct/hooks/)
FRAMEWORK_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# Resolve repo root and PRAWDUCT_DIR
repo_root=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -z "$repo_root" ]]; then
    exit 0
fi
PRAWDUCT_DIR="${CLAUDE_PROJECT_DIR:-$repo_root}/.prawduct"

# Check for the .critic-pending flag — if it doesn't exist, no framework
# files were modified in this session, so no Critic review needed
if [[ ! -f "$PRAWDUCT_DIR/.critic-pending" ]]; then
    # No pending flag, but still run the check in case files were staged
    # outside this session (e.g., git add from terminal)
    :
fi

# Delegate to critic-reminder.sh for the actual governance check
# It checks staged files against framework patterns and looks for evidence
if "$FRAMEWORK_ROOT/tools/critic-reminder.sh" 2>&1; then
    # Evidence found or no framework files staged — allow commit
    # Clean up governance state after successful commit
    rm -f "$PRAWDUCT_DIR/.critic-pending"
    rm -f "$PRAWDUCT_DIR/.critic-findings.json"
    rm -f "$PRAWDUCT_DIR/.session-edits.json"        # legacy, remove if present
    rm -f "$PRAWDUCT_DIR/.session-governance.json"
    rm -f "$PRAWDUCT_DIR/.orchestrator-activated"
    exit 0
else
    # Framework files staged without Critic evidence — deny commit
    echo "" >&2
    echo "BLOCKED: Framework governance review required before committing." >&2
    echo "" >&2
    echo "Framework files are staged but no Critic review evidence was found." >&2
    echo "Run the Critic as a standalone step:" >&2
    echo "  1. Read $FRAMEWORK_ROOT/skills/critic/SKILL.md" >&2
    echo "  2. Apply all applicable checks to your changes" >&2
    echo "  3. Record findings, then retry the commit" >&2
    echo "  4. Include 'Governance Review' in the commit message" >&2
    exit 2
fi
