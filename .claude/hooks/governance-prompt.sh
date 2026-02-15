#!/usr/bin/env bash
#
# governance-prompt.sh — UserPromptSubmit hook
#
# Unified governance prompt that replaces framework-governance-prompt.sh and
# product-governance-prompt.sh. Fires when the user sends a message.
#
# Two responsibilities:
# 1. If Orchestrator hasn't been activated, injects instruction to activate (HR9).
# 2. Reads .session-governance.json for governance debt and injects context so
#    Claude has governance awareness at the start of processing.
#
# No framework/product branching — reads one state file, reports what it finds.
#
# Hook protocol:
#   - Reads JSON from stdin (user prompt data)
#   - stdout: JSON with additionalContext (injected into Claude's context)
#   - exit 0: always (UserPromptSubmit hooks don't block)

set -euo pipefail

# --- Resolve paths ---

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
CLAUDE_DIR="${CLAUDE_PROJECT_DIR:-$REPO_ROOT}/.claude"

if [[ -z "$CLAUDE_DIR" || "$CLAUDE_DIR" == "/.claude" ]]; then
    cat > /dev/null
    exit 0
fi

# Consume stdin (required by hook protocol)
cat > /dev/null

# --- Check Orchestrator activation ---

if [[ -n "$REPO_ROOT" ]]; then
    MARKER="$REPO_ROOT/.claude/.orchestrator-activated"
    if [[ ! -f "$MARKER" ]]; then
        python3 -c "
import json
msg = 'ORCHESTRATOR NOT ACTIVATED. Reads of skill files (except orchestrator/SKILL.md) and template files are BLOCKED. Edits to all governed files are BLOCKED. Before doing anything else, you MUST read skills/orchestrator/SKILL.md and follow its activation process (Session Resumption or new project setup). This is HR9 — no governance bypass. Do this NOW, before responding to the user\\'s request.'
print(json.dumps({'additionalContext': msg}))
" 2>/dev/null
        exit 0
    fi
fi

# --- Check governance state from unified session file ---

SESSION_FILE="$CLAUDE_DIR/.session-governance.json"
if [[ ! -f "$SESSION_FILE" ]]; then
    exit 0
fi

summary=$(python3 -c "
import json, sys, os, time

session_file = '$SESSION_FILE'
repo_root = '$REPO_ROOT'
findings_file = os.path.join(repo_root, '.claude', '.critic-findings.json') if repo_root else ''

try:
    with open(session_file) as f:
        data = json.load(f)
except:
    sys.exit(0)

items = []

# --- Framework governance ---
framework_edits = data.get('framework_edits', {})
edited_files = [entry['path'] for entry in framework_edits.get('files', [])]

if edited_files:
    # Check if Critic findings exist and cover all edited files
    all_covered = False
    if findings_file and os.path.exists(findings_file):
        try:
            with open(findings_file) as f:
                findings = json.load(f)
            file_age = time.time() - os.path.getmtime(findings_file)
            max_age = 2 * 60 * 60  # 2 hours
            if file_age <= max_age and findings.get('total_checks', 0) >= 6:
                reviewed = set(findings.get('reviewed_files', []))
                uncovered = [f for f in edited_files if f not in reviewed]
                if not uncovered:
                    all_covered = True
        except:
            pass

    if not all_covered:
        file_list = ', '.join(edited_files)
        items.append(f'FRAMEWORK GOVERNANCE: {len(edited_files)} framework file(s) modified without complete Critic review ({file_list}). Run Critic automatically before committing — do not ask the user.')

# --- Product governance ---
gov = data.get('governance_state', {})

chunks_without_review = gov.get('chunks_completed_without_review', 0)
if chunks_without_review > 0:
    items.append(f'{chunks_without_review} chunk(s) completed without Critic review — read skills/critic/SKILL.md from disk and apply Product Governance before proceeding')

stage_transitions = gov.get('stage_transitions_without_frp', 0)
if stage_transitions > 0:
    items.append(f'{stage_transitions} stage transition(s) without Framework Reflection — read skills/orchestrator/SKILL.md from disk for the Framework Reflection Protocol')

checkpoints_due = gov.get('governance_checkpoints_due', [])
if checkpoints_due:
    items.append(f'{len(checkpoints_due)} governance checkpoint(s) overdue — read skills/review-lenses/SKILL.md from disk and apply Architecture + Skeptic + Testing lenses')

files_changed = gov.get('product_files_changed', 0)
observations = gov.get('observations_captured_this_session', 0)
if files_changed >= 10 and observations == 0:
    items.append(f'{files_changed} product files modified with 0 observations captured')

if items:
    print('Governance status:\\n- ' + '\\n- '.join(items))
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
