#!/usr/bin/env bash
#
# framework-governance-stop.sh — Stop hook for framework governance
#
# Fires when Claude finishes responding. Reads .session-edits.json to check
# whether framework files were modified, then verifies .critic-findings.json
# exists, is fresh, has all 7 checks, and covers all edited files.
#
# Blocks (exit 2) when framework edits lack Critic evidence.
#
# Hook protocol:
#   - Reads JSON from stdin (includes stop_hook_active to prevent loops)
#   - exit 0: allow Claude to stop
#   - exit 2: block Claude from stopping (stderr message shown)

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

# --- Check framework governance state ---

result=$(python3 -c "
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

issues = []

# Check 1: Does .critic-findings.json exist?
if not os.path.exists(findings_file):
    issues.append(f'{len(edited_files)} framework file(s) modified without Critic review')
    print('MISSING: ' + '; '.join(issues))
    sys.exit(0)

try:
    with open(findings_file) as f:
        findings = json.load(f)
except:
    issues.append('Critic findings file exists but is not valid JSON')
    print('CORRUPT: ' + '; '.join(issues))
    sys.exit(0)

# Check 2: Is findings file fresh (< 2 hours)?
file_age = time.time() - os.path.getmtime(findings_file)
max_age = 2 * 60 * 60  # 2 hours
if file_age > max_age:
    issues.append('Critic findings are stale (older than 2 hours)')

# Check 3: All 7 checks present?
total_checks = findings.get('total_checks', 0)
if total_checks != 7:
    issues.append(f'Critic findings have {total_checks}/7 checks')

# Check 4: All edited files covered?
reviewed_files = set(findings.get('reviewed_files', []))
uncovered = [f for f in edited_files if f not in reviewed_files]
if uncovered:
    uncovered_str = ', '.join(uncovered)
    issues.append(f'{len(uncovered)} edited file(s) not in Critic reviewed_files: {uncovered_str}')

if issues:
    print('INCOMPLETE: ' + '; '.join(issues))
else:
    print('')
" 2>/dev/null || echo "")

if [[ -n "$result" && "$result" != "" ]]; then
    echo "" >&2
    echo "BLOCKED: Cannot finish — framework governance debt exists." >&2
    echo "" >&2
    echo "$result" >&2
    echo "" >&2
    echo "Before finishing:" >&2
    echo "  1. Run Critic (skills/critic/SKILL.md) Framework Governance mode (all 7 checks)" >&2
    echo "  2. Record findings: tools/record-critic-findings.sh --files 'file1,file2' --check 'Name:sev:summary' (x7)" >&2
    echo "  3. Run the Critic automatically — do not ask the user." >&2
    exit 2
fi

exit 0
