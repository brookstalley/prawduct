#!/usr/bin/env bash
#
# product-governance-stop.sh — Stop hook for product build governance
#
# Fires when Claude finishes responding. Reads .product-session.json governance
# state and blocks (exit 2) only for critical governance debt:
#   - Chunks completed without Critic review
#   - Overdue governance checkpoints
#
# Does NOT block for softer items (FRP, observations) — those are handled by
# Layer 1 (PostToolUse additionalContext reminders).
#
# Hook protocol:
#   - Reads JSON from stdin (includes stop_hook_active to prevent loops)
#   - exit 0: allow Claude to stop
#   - exit 2: block Claude from stopping (stderr message shown)

set -euo pipefail

# --- Fast path: check for active product session ---

# $CLAUDE_PROJECT_DIR is set by Claude Code to the directory where it was launched.
# We use this instead of git rev-parse because the product directory may not be a
# git repo, but the session file always lives in the framework's .claude/ directory.
if [[ -z "${CLAUDE_PROJECT_DIR:-}" ]]; then
    exit 0
fi

SESSION_FILE="$CLAUDE_PROJECT_DIR/.claude/.product-session.json"
if [[ ! -f "$SESSION_FILE" ]]; then
    exit 0
fi

# Read stdin for stop_hook_active flag to prevent infinite loops
input=$(cat)
stop_hook_active=$(echo "$input" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    print('true' if data.get('stop_hook_active', False) else 'false')
except:
    print('false')
" 2>/dev/null || echo "false")

if [[ "$stop_hook_active" == "true" ]]; then
    exit 0
fi

# --- Check for critical governance debt ---

result=$(python3 -c "
import json, sys

session_file = '$SESSION_FILE'
try:
    with open(session_file) as f:
        session = json.load(f)
except:
    sys.exit(0)

gov = session.get('governance_state', {})
critical_issues = []

# Critical: chunks completed without Critic review
chunks_without_review = gov.get('chunks_completed_without_review', 0)
if chunks_without_review > 0:
    critical_issues.append(f'{chunks_without_review} chunk(s) completed without Critic review')

# Critical: overdue governance checkpoints
checkpoints_due = gov.get('governance_checkpoints_due', [])
if checkpoints_due:
    critical_issues.append(f'{len(checkpoints_due)} governance checkpoint(s) overdue')

if critical_issues:
    print('CRITICAL: ' + '; '.join(critical_issues))
else:
    print('')
" 2>/dev/null || echo "")

if [[ -n "$result" && "$result" != "" ]]; then
    echo "" >&2
    echo "BLOCKED: Cannot finish — critical product governance debt exists." >&2
    echo "" >&2
    echo "$result" >&2
    echo "" >&2
    echo "Before finishing:" >&2
    echo "  1. Run Critic review (skills/critic/SKILL.md Mode 2) on completed chunks" >&2
    echo "  2. Complete any overdue governance checkpoints" >&2
    echo "  3. Update project-state.yaml with review results" >&2
    exit 2
fi

exit 0
