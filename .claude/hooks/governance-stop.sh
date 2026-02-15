#!/usr/bin/env bash
#
# governance-stop.sh — Stop hook
#
# Unified stop hook that replaces framework-governance-stop.sh and
# product-governance-stop.sh. Fires when Claude finishes responding.
# Blocks (exit 2) when critical governance debt exists — same criteria
# for all projects.
#
# Critical debt that blocks:
#   - Framework files edited without Critic review
#   - Chunks completed without Critic review
#   - Overdue governance checkpoints
#
# Non-critical debt (reminders only, does not block):
#   - FRP not run after stage transition
#   - Observations not captured
#
# Hook protocol:
#   - Reads JSON from stdin (includes stop_hook_active to prevent loops)
#   - exit 0: allow Claude to stop
#   - exit 2: block Claude from stopping (stderr message shown)

set -euo pipefail

# --- Resolve paths ---

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
CLAUDE_DIR="${CLAUDE_PROJECT_DIR:-$REPO_ROOT}/.claude"

if [[ -z "$CLAUDE_DIR" || "$CLAUDE_DIR" == "/.claude" ]]; then
    cat > /dev/null
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

SESSION_FILE="$CLAUDE_DIR/.session-governance.json"
if [[ ! -f "$SESSION_FILE" ]]; then
    exit 0
fi

# --- Check for critical governance debt ---

result=$(python3 -c "
import json, sys, os, time

session_file = '$SESSION_FILE'
repo_root = '$REPO_ROOT'
findings_file = os.path.join(repo_root, '.claude', '.critic-findings.json') if repo_root else ''

try:
    with open(session_file) as f:
        data = json.load(f)
except:
    sys.exit(0)

critical_issues = []

# --- Framework governance debt ---
framework_edits = data.get('framework_edits', {})
edited_files = [entry['path'] for entry in framework_edits.get('files', [])]

if edited_files:
    # Check if Critic findings exist and cover all edited files
    all_covered = False
    issue_detail = ''
    if findings_file and os.path.exists(findings_file):
        try:
            with open(findings_file) as f:
                findings = json.load(f)

            file_age = time.time() - os.path.getmtime(findings_file)
            max_age = 2 * 60 * 60  # 2 hours

            if file_age > max_age:
                issue_detail = 'Critic findings are stale (older than 2 hours)'
            elif findings.get('total_checks', 0) < 6:
                tc = findings.get('total_checks', 0)
                issue_detail = f'Critic findings have {tc} checks (need at least 6)'
            else:
                reviewed = set(findings.get('reviewed_files', []))
                uncovered = [f for f in edited_files if f not in reviewed]
                if uncovered:
                    issue_detail = f'{len(uncovered)} edited file(s) not in Critic reviewed_files'
                else:
                    all_covered = True
        except:
            issue_detail = 'Critic findings file exists but is not valid JSON'
    else:
        issue_detail = f'{len(edited_files)} framework file(s) modified without Critic review'

    if not all_covered:
        critical_issues.append(issue_detail)

# --- Product governance debt ---
gov = data.get('governance_state', {})

chunks_without_review = gov.get('chunks_completed_without_review', 0)
if chunks_without_review > 0:
    critical_issues.append(f'{chunks_without_review} chunk(s) completed without Critic review')

checkpoints_due = gov.get('governance_checkpoints_due', [])
if checkpoints_due:
    critical_issues.append(f'{len(checkpoints_due)} governance checkpoint(s) overdue')

# --- DCP retrospective debt ---
dc = data.get('directional_change', {})
if dc.get('active', False) and not dc.get('retrospective_completed', False):
    plan_desc = dc.get('plan_description', 'unknown')
    critical_issues.append(f'Directional change active without retrospective: {plan_desc}. Complete DCP step 11 (post-change retrospective) before finishing.')

if critical_issues:
    print('CRITICAL: ' + '; '.join(critical_issues))
else:
    print('')
" 2>/dev/null || echo "")

if [[ -n "$result" && "$result" != "" ]]; then
    echo "" >&2
    echo "BLOCKED: Cannot finish — governance debt exists." >&2
    echo "" >&2
    echo "$result" >&2
    echo "" >&2
    echo "Before finishing:" >&2
    echo "  1. Run Critic (skills/critic/SKILL.md) — apply all applicable checks" >&2
    echo "  2. Record findings: tools/record-critic-findings.sh" >&2
    echo "  3. Run the Critic automatically — do not ask the user." >&2
    exit 2
fi

exit 0
