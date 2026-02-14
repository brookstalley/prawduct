#!/usr/bin/env bash
#
# product-governance-prompt.sh — UserPromptSubmit hook for product builds
#
# Fires when the user sends a message during an active product build session.
# Injects additionalContext summarizing any accumulated governance debt so
# Claude has governance awareness at the start of processing.
#
# Hook protocol:
#   - Reads JSON from stdin (user prompt data)
#   - stdout: JSON with additionalContext (injected into Claude's context)
#   - exit 0: always (UserPromptSubmit hooks don't block)

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

# Consume stdin (required by hook protocol)
cat > /dev/null

# --- Summarize governance state ---

summary=$(python3 -c "
import json, sys

session_file = '$SESSION_FILE'
try:
    with open(session_file) as f:
        session = json.load(f)
except:
    sys.exit(0)

gov = session.get('governance_state', {})
items = []

# Chunks without review
chunks_without_review = gov.get('chunks_completed_without_review', 0)
if chunks_without_review > 0:
    items.append(f'{chunks_without_review} chunk(s) completed without Critic review — read skills/critic/SKILL.md from disk and apply Mode 2 (Product Governance) before proceeding')

# Stage transitions without FRP
stage_transitions = gov.get('stage_transitions_without_frp', 0)
if stage_transitions > 0:
    items.append(f'{stage_transitions} stage transition(s) without Framework Reflection — read skills/orchestrator/SKILL.md from disk for the Framework Reflection Protocol')

# Overdue checkpoints
checkpoints_due = gov.get('governance_checkpoints_due', [])
if checkpoints_due:
    items.append(f'{len(checkpoints_due)} governance checkpoint(s) overdue — read skills/review-lenses/SKILL.md from disk and apply Architecture + Skeptic + Testing lenses')

# Observation reminder
files_changed = gov.get('product_files_changed', 0)
observations = gov.get('observations_captured_this_session', 0)
if files_changed >= 10 and observations == 0:
    items.append(f'{files_changed} product files modified with 0 observations captured')

if items:
    print('Active product build governance status:\\n- ' + '\\n- '.join(items))
else:
    print('')
" 2>/dev/null || echo "")

if [[ -n "$summary" && "$summary" != "" ]]; then
    python3 -c "
import json
msg = '''$summary'''
if msg.strip():
    print(json.dumps({'additionalContext': msg.strip()}))
" 2>/dev/null
fi

exit 0
