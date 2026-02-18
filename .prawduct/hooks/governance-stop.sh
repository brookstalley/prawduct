#!/usr/bin/env bash
#
# governance-stop.sh — Stop hook
#
# Blocks (exit 2) when critical governance debt exists. All enforcement
# logic preserved; messages are terse pointers to skill files.
#
# Critical debt that blocks:
#   - Framework files edited without Critic review
#   - Chunks completed without Critic review
#   - Overdue governance checkpoints
#   - Incomplete DCP steps (when DCP is active)
#
# Hook protocol:
#   - Reads JSON from stdin (includes stop_hook_active to prevent loops)
#   - exit 0: allow Claude to stop
#   - exit 2: block Claude from stopping (stderr message shown)

# No set -e or pipefail: hooks must never exit silently on any bash version.
# -u catches undefined variable typos.
set -u

# --- Resolve paths ---

# Derive framework root from this script's location (hooks live at <framework>/.prawduct/hooks/)
FRAMEWORK_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
PRAWDUCT_DIR="${CLAUDE_PROJECT_DIR:-$REPO_ROOT}/.prawduct"

if [[ -z "$PRAWDUCT_DIR" || "$PRAWDUCT_DIR" == "/.prawduct" ]]; then
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

SESSION_FILE="$PRAWDUCT_DIR/.session-governance.json"
if [[ ! -f "$SESSION_FILE" ]]; then
    exit 0
fi

# --- Check for critical governance debt ---

result=$(python3 -c "
import json, sys, os, time

session_file = '$SESSION_FILE'
prawduct_dir = '$PRAWDUCT_DIR'
findings_file = os.path.join(prawduct_dir, '.critic-findings.json') if prawduct_dir else ''

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
    all_covered = False
    if findings_file and os.path.exists(findings_file):
        try:
            with open(findings_file) as f:
                findings = json.load(f)

            file_age = time.time() - os.path.getmtime(findings_file)
            max_age = 2 * 60 * 60  # 2 hours

            if file_age > max_age:
                critical_issues.append('Critic findings stale (>2h)')
            elif findings.get('total_checks', 0) < 4:
                critical_issues.append(f'Critic findings: {findings.get(\"total_checks\", 0)} checks (need 4+)')
            else:
                reviewed = set(findings.get('reviewed_files', []))
                uncovered = [f for f in edited_files if f not in reviewed]
                if uncovered:
                    critical_issues.append(f'{len(uncovered)} edited file(s) not in Critic findings')
                else:
                    all_covered = True
        except:
            critical_issues.append('Critic findings file invalid')
    else:
        file_list = ', '.join(edited_files[:5])
        critical_issues.append(f'No Critic review for: {file_list}')

# --- Product governance debt ---
gov = data.get('governance_state', {})

chunks_without_review = gov.get('chunks_completed_without_review', 0)
if chunks_without_review > 0:
    critical_issues.append(f'{chunks_without_review} chunk(s) without Critic review')

checkpoints_due = gov.get('governance_checkpoints_due', [])
if checkpoints_due:
    critical_issues.append(f'{len(checkpoints_due)} governance checkpoint(s) overdue')

# --- PFR debt ---
pfr = data.get('pfr_state', {})
if pfr.get('required', False):
    if not pfr.get('diagnosis_written', False):
        critical_issues.append('PFR: governance-sensitive files edited without pre-fix diagnosis. Write diagnosis to .prawduct/.session-governance.json pfr_state.diagnosis (symptom, five_whys, root_cause, root_cause_category, meta_fix_plan) and set pfr_state.diagnosis_written to true. Or if cosmetic: set pfr_state.cosmetic_justification and pfr_state.required to false.')
    elif not pfr.get('observation_file'):
        gov_files = ', '.join(pfr.get('governance_sensitive_files', [])[:5])
        critical_issues.append(f'PFR: governance-sensitive files edited ({gov_files}) but no observation captured. Create observation via tools/capture-observation.sh with root_cause_analysis block, then set pfr_state.observation_file in .prawduct/.session-governance.json.')

# --- DCP classification enforcement ---
# When 3+ governed files are edited without DCP classification, block.
# This mechanically enforces the Stage 6 governance table.
dc = data.get('directional_change', {})
if dc.get('needs_classification', False) and not dc.get('active', False):
    file_count = dc.get('triggered_at_file_count', 3)
    critical_issues.append(f'DCP: {file_count}+ governed files edited without change classification. Read $FRAMEWORK_ROOT/skills/orchestrator/stage-6-iteration.md and classify per DCP tiers (mechanical/enhancement/structural). Then set directional_change.active and tier in .prawduct/.session-governance.json, or set needs_classification to false if mechanical.')

# --- DCP debt ---
if dc.get('active', False):
    if 'plan_stage_review_completed' in dc and not dc.get('plan_stage_review_completed', False):
        critical_issues.append('DCP: plan-stage review incomplete')

    total_phases = dc.get('total_phases', 0)
    phases_reviewed = dc.get('phases_reviewed_count', 0)
    if 'phases_reviewed_count' in dc and total_phases > 1 and phases_reviewed == 0:
        critical_issues.append(f'DCP: 0/{total_phases} phase reviews done')

    if 'observation_captured' in dc and not dc.get('observation_captured', False):
        critical_issues.append('DCP: observation not captured')

    if not dc.get('retrospective_completed', False):
        critical_issues.append('DCP: retrospective incomplete')

    # Artifact freshness: enhancement/structural DCPs must verify artifacts
    tier = dc.get('tier', '')
    if tier in ('enhancement', 'structural'):
        artifacts_verified = dc.get('artifacts_verified', [])
        if not artifacts_verified:
            critical_issues.append('DCP: artifact freshness not verified. Read artifact_manifest in project-state.yaml, identify artifacts describing affected behavior, verify each is current, update stale ones, then record the list in directional_change.artifacts_verified')

if critical_issues:
    print('; '.join(critical_issues))
else:
    print('')
" 2>/dev/null || echo "")

if [[ -n "$result" && "$result" != "" ]]; then
    echo "" >&2
    echo "BLOCKED: Governance debt. Read $FRAMEWORK_ROOT/skills/critic/SKILL.md and resolve:" >&2
    echo "$result" >&2
    echo "" >&2
    exit 2
fi

exit 0
