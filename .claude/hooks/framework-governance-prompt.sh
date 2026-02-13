#!/usr/bin/env bash
#
# framework-governance-prompt.sh — UserPromptSubmit hook for framework governance
#
# Fires when the user sends a message. Checks .session-edits.json for framework
# file edits and .critic-findings.json for Critic coverage. Injects governance
# context so Claude runs the Critic automatically instead of asking.
#
# Hook protocol:
#   - Reads JSON from stdin (user prompt data)
#   - stdout: JSON with additionalContext (injected into Claude's context)
#   - exit 0: always (UserPromptSubmit hooks don't block)

set -euo pipefail

# --- Fast path: check for session edits ---

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -z "$REPO_ROOT" ]]; then
    exit 0
fi

SESSION_EDITS="$REPO_ROOT/.claude/.session-edits.json"
if [[ ! -f "$SESSION_EDITS" ]]; then
    exit 0
fi

# Consume stdin (required by hook protocol)
cat > /dev/null

# --- Check governance coverage ---

summary=$(python3 -c "
import json, sys, os, time

session_file = '$SESSION_EDITS'
findings_file = '$REPO_ROOT/.claude/.critic-findings.json'

try:
    with open(session_file) as f:
        session = json.load(f)
except:
    sys.exit(0)

edited_files = [entry['path'] for entry in session.get('files', [])]
if not edited_files:
    sys.exit(0)

# Check if Critic findings exist and cover all edited files
all_covered = False
if os.path.exists(findings_file):
    try:
        with open(findings_file) as f:
            findings = json.load(f)

        file_age = time.time() - os.path.getmtime(findings_file)
        max_age = 2 * 60 * 60  # 2 hours

        if file_age <= max_age and findings.get('total_checks', 0) == 7:
            reviewed = set(findings.get('reviewed_files', []))
            uncovered = [f for f in edited_files if f not in reviewed]
            if not uncovered:
                all_covered = True
    except:
        pass

if not all_covered:
    file_list = ', '.join(edited_files)
    print(f'FRAMEWORK GOVERNANCE: {len(edited_files)} framework file(s) modified without complete Critic review ({file_list}). Run Critic automatically before committing — do not ask the user.')
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
