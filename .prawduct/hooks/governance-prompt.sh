#!/usr/bin/env bash
#
# governance-prompt.sh — UserPromptSubmit hook
#
# Single responsibility: if the Orchestrator hasn't been activated, inject
# the activation instruction (HR9). No other advisory output — governance
# enforcement is handled by governance-gate.sh and governance-stop.sh.
#
# Hook protocol:
#   - Reads JSON from stdin (user prompt data)
#   - stdout: JSON with additionalContext (only for activation reminder)
#   - exit 0: always (UserPromptSubmit hooks don't block)

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

# Consume stdin (required by hook protocol)
cat > /dev/null

# --- Check Orchestrator activation ---

if [[ -n "$REPO_ROOT" ]]; then
    MARKER="$PRAWDUCT_DIR/.orchestrator-activated"
    if [[ ! -f "$MARKER" ]]; then
        python3 -c "
import json
msg = 'ORCHESTRATOR NOT ACTIVATED. Reads of skill files (except orchestrator/SKILL.md) and template files are BLOCKED. Edits to all governed files are BLOCKED. Before doing anything else, you MUST read $FRAMEWORK_ROOT/skills/orchestrator/SKILL.md and follow its activation process (Session Resumption or new project setup). This is HR9 — no governance bypass. Do this NOW, before responding to the user\\'s request.'
print(json.dumps({'additionalContext': msg}))
" 2>/dev/null
        exit 0
    fi
fi

exit 0
