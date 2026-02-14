#!/usr/bin/env bash
#
# compact-governance-reinject.sh — SessionStart hook (compact matcher)
#
# Fires AFTER context compaction completes. Re-injects governance instructions
# into the fresh post-compaction context so Claude knows to re-read skill files
# from disk and has current governance debt status.
#
# Hook protocol:
#   - SessionStart hooks: no stdin
#   - stdout: plain text injected into Claude's context
#   - exit 0: always (SessionStart hooks don't block)

set -euo pipefail

if [[ -z "${CLAUDE_PROJECT_DIR:-}" ]]; then
    echo "CONTEXT RESTORED AFTER COMPACTION."
    echo "Read skills/orchestrator/SKILL.md from disk before taking action."
    exit 0
fi

SESSION_FILE="$CLAUDE_PROJECT_DIR/.claude/.product-session.json"

# --- Check if a product build is active ---

if [[ -f "$SESSION_FILE" ]]; then
    # Active product build — output full governance recovery instructions
    debt_summary=$(python3 -c "
import json, sys

try:
    with open('$SESSION_FILE') as f:
        session = json.load(f)
except:
    print('Chunks without review: unknown')
    print('Product files changed: unknown')
    print('Observations captured: unknown')
    sys.exit(0)

gov = session.get('governance_state', {})
print(f\"Chunks without review: {gov.get('chunks_completed_without_review', 0)}\")
print(f\"Product files changed: {gov.get('product_files_changed', 0)}\")
print(f\"Observations captured: {gov.get('observations_captured_this_session', 0)}\")
" 2>/dev/null || echo "Chunks without review: unknown")

    cat <<REINJECT
CONTEXT RESTORED AFTER COMPACTION — Governance instructions follow.

You are in an active product build. Skill files were in your context but have been
compacted. They still exist on disk. Read them when needed.

MANDATORY AFTER EACH CHUNK:
1. Read skills/critic/SKILL.md from disk, apply Mode 2 (Product Governance)
2. Record findings in project-state.yaml → build_state.reviews
3. Update .claude/.product-session.json → governance_state.chunks_completed_without_review to 0

CURRENT GOVERNANCE DEBT:
$debt_summary

FOR FULL PROCEDURES: Read skills/orchestrator/SKILL.md (process), skills/critic/SKILL.md
(review), skills/builder/SKILL.md (build). These files are on disk — use the Read tool.
REINJECT
else
    # No active product build — framework dev reminder
    cat <<REINJECT
CONTEXT RESTORED AFTER COMPACTION.
You are working on the Prawduct framework. Read skills/orchestrator/SKILL.md from disk
for session process. Framework changes require Critic review (skills/critic/SKILL.md,
Framework Governance mode, all 7 checks).
REINJECT
fi

exit 0
