#!/usr/bin/env bash
#
# compact-governance-reinject.sh — SessionStart hook (compact matcher)
#
# Fires AFTER context compaction completes. Re-injects governance instructions
# into the fresh post-compaction context so Claude knows to re-read skill files
# from disk and has current governance debt status.
#
# Uses unified .session-governance.json for all governance state.
#
# Hook protocol:
#   - SessionStart hooks: no stdin
#   - stdout: plain text injected into Claude's context
#   - exit 0: always (SessionStart hooks don't block)

set -euo pipefail

# Derive framework root from this script's location (hooks live at <framework>/.claude/hooks/)
FRAMEWORK_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

if [[ -z "${CLAUDE_PROJECT_DIR:-}" ]]; then
    echo "CONTEXT RESTORED AFTER COMPACTION."
    echo "Read skills/orchestrator/SKILL.md from disk before taking action."
    exit 0
fi

SESSION_FILE="$CLAUDE_PROJECT_DIR/.claude/.session-governance.json"

# Detect product repo: check for .prawduct/framework-path
IS_PRODUCT_REPO=false
FRAMEWORK_PATH_FILE="$CLAUDE_PROJECT_DIR/.prawduct/framework-path"
if [[ -f "$FRAMEWORK_PATH_FILE" ]]; then
    IS_PRODUCT_REPO=true
    STORED_FRAMEWORK_PATH=$(cat "$FRAMEWORK_PATH_FILE" 2>/dev/null || echo "")
fi

if [[ -f "$SESSION_FILE" ]]; then
    # Governance state exists — output recovery instructions with debt summary
    debt_summary=$(python3 -c "
import json, sys

try:
    with open('$SESSION_FILE') as f:
        session = json.load(f)
except:
    print('Governance state: unknown')
    sys.exit(0)

gov = session.get('governance_state', {})
fw = session.get('framework_edits', {})

lines = []
fw_files = fw.get('files', [])
if fw_files:
    lines.append(f'Framework files edited: {len(fw_files)} ({fw.get(\"total_edits\", 0)} total edits)')

chunks = gov.get('chunks_completed_without_review', 0)
if chunks > 0:
    lines.append(f'Chunks without review: {chunks}')

product_files = gov.get('product_files_changed', 0)
if product_files > 0:
    lines.append(f'Product files changed: {product_files}')

obs = gov.get('observations_captured_this_session', 0)
lines.append(f'Observations captured: {obs}')

print('\\n'.join(lines) if lines else 'No governance debt detected')
" 2>/dev/null || echo "Governance state: unknown")

    if [[ "$IS_PRODUCT_REPO" == true && -n "$STORED_FRAMEWORK_PATH" ]]; then
        cat <<REINJECT
CONTEXT RESTORED AFTER COMPACTION — Product repo governance instructions follow.

This is a product repo. The prawduct framework is at: $STORED_FRAMEWORK_PATH
Skill files are in the framework directory. Read them using absolute paths.

MANDATORY AFTER CHANGES:
1. Read $STORED_FRAMEWORK_PATH/skills/critic/SKILL.md from disk, apply all applicable checks
2. Record findings in .prawduct/project-state.yaml -> build_state.reviews
3. Update .claude/.session-governance.json governance debt to 0

CURRENT GOVERNANCE DEBT:
$debt_summary

FOR FULL PROCEDURES: Read $STORED_FRAMEWORK_PATH/skills/orchestrator/SKILL.md (process),
$STORED_FRAMEWORK_PATH/skills/critic/SKILL.md (review), $STORED_FRAMEWORK_PATH/skills/builder/SKILL.md (build).
REINJECT
    else
        cat <<REINJECT
CONTEXT RESTORED AFTER COMPACTION — Governance instructions follow.

Skill files were in your context but have been compacted. They still exist on disk.
Read them when needed.

MANDATORY AFTER CHANGES:
1. Read skills/critic/SKILL.md from disk, apply all applicable checks
2. Record findings (framework: tools/record-critic-findings.sh; product: project-state.yaml -> build_state.reviews)
3. Update .claude/.session-governance.json governance debt to 0

CURRENT GOVERNANCE DEBT:
$debt_summary

FOR FULL PROCEDURES: Read skills/orchestrator/SKILL.md (process), skills/critic/SKILL.md
(review), skills/builder/SKILL.md (build). These files are on disk — use the Read tool.
REINJECT
    fi
else
    if [[ "$IS_PRODUCT_REPO" == true && -n "$STORED_FRAMEWORK_PATH" ]]; then
        cat <<REINJECT
CONTEXT RESTORED AFTER COMPACTION.
This is a product repo. The prawduct framework is at: $STORED_FRAMEWORK_PATH
Read $STORED_FRAMEWORK_PATH/skills/orchestrator/SKILL.md from disk before taking action.
Changes require Critic review ($STORED_FRAMEWORK_PATH/skills/critic/SKILL.md).
REINJECT
    else
        cat <<REINJECT
CONTEXT RESTORED AFTER COMPACTION.
Read skills/orchestrator/SKILL.md from disk before taking action.
Changes require Critic review (skills/critic/SKILL.md).
REINJECT
    fi
fi

exit 0
