#!/usr/bin/env bash
#
# compact-governance-reinject.sh — SessionStart hook (compact matcher)
#
# Fires AFTER context compaction. Re-injects minimal recovery instructions:
# read skill files from disk (they survive compaction) and current debt status.
#
# Hook protocol:
#   - SessionStart hooks: no stdin
#   - stdout: plain text injected into Claude's context
#   - exit 0: always

# No set -e or pipefail: hooks must never exit silently on any bash version.
# -u catches undefined variable typos.
set -u

FRAMEWORK_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

if [[ -z "${CLAUDE_PROJECT_DIR:-}" ]]; then
    echo "CONTEXT RESTORED AFTER COMPACTION."
    echo "Read skills/orchestrator/SKILL.md from disk before taking action."
    exit 0
fi

SESSION_FILE="$CLAUDE_PROJECT_DIR/.prawduct/.session-governance.json"

# Detect product repo
IS_PRODUCT_REPO=false
FRAMEWORK_PATH_FILE="$CLAUDE_PROJECT_DIR/.prawduct/framework-path"
SKILL_PREFIX="skills"
if [[ -f "$FRAMEWORK_PATH_FILE" ]]; then
    IS_PRODUCT_REPO=true
    STORED_FRAMEWORK_PATH=$(cat "$FRAMEWORK_PATH_FILE" 2>/dev/null || echo "")
    SKILL_PREFIX="$STORED_FRAMEWORK_PATH/skills"
fi

# Build debt summary if governance state exists
DEBT_SUMMARY=""
if [[ -f "$SESSION_FILE" ]]; then
    DEBT_SUMMARY=$(python3 -c "
import json, sys, os

try:
    with open('$SESSION_FILE') as f:
        session = json.load(f)
except:
    sys.exit(0)

gov = session.get('governance_state', {})
fw = session.get('framework_edits', {})
lines = []

fw_files = fw.get('files', [])
if fw_files:
    lines.append(f'Framework files edited: {len(fw_files)}')

chunks = gov.get('chunks_completed_without_review', 0)
if chunks > 0:
    lines.append(f'Chunks without review: {chunks}')

print('\\n'.join(lines) if lines else 'No governance debt')
" 2>/dev/null || echo "Unknown")
fi

cat <<REINJECT
CONTEXT RESTORED AFTER COMPACTION.

Skill files are on disk — read them when needed or when hooks block you.
Start: $SKILL_PREFIX/orchestrator/SKILL.md
Critic: $SKILL_PREFIX/critic/SKILL.md
${DEBT_SUMMARY:+
GOVERNANCE DEBT:
$DEBT_SUMMARY}
REINJECT

exit 0
