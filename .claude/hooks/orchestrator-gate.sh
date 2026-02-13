#!/usr/bin/env bash
#
# orchestrator-gate.sh — PreToolUse hook for Edit/Write
#
# Fires before every Edit or Write tool call. Checks whether the Orchestrator
# has been activated in this session before allowing framework file modifications.
# Enforces HR9: No Governance Bypass.
#
# The Orchestrator creates .claude/.orchestrator-activated with a timestamp
# during Session Resumption (or new-project activation). This hook verifies
# that marker exists and is recent (created within the last 12 hours).
#
# Marker lifecycle:
#   Created:  Orchestrator activation (step 3) or Session Resumption (step 1)
#   Read:     This hook, on every Edit/Write to framework files
#   Deleted:  On /clear (SessionStart hook), new startup (SessionStart hook),
#             or successful commit (critic-gate.sh cleanup)
#
# Hook protocol:
#   - Reads JSON from stdin (tool_name, tool_input with file_path)
#   - exit 0: allow the tool call
#   - exit 2: deny the tool call (stderr message shown to Claude)
#
# Known observability gap: If this hook fails to block when it should (false
# negative) or blocks when it shouldn't (false positive), there is no
# observation type to capture that. Hook correctness is verified by mechanical
# testing, not by the observation system.

set -euo pipefail

# Read the hook input JSON from stdin
input=$(cat)

# Extract the file path from the tool input
file_path=$(echo "$input" | python3 -c "
import json, sys
data = json.load(sys.stdin)
tool_input = data.get('tool_input', {})
print(tool_input.get('file_path', ''))
" 2>/dev/null || echo "")

if [[ -z "$file_path" ]]; then
    exit 0
fi

# Resolve to a path relative to the repo root
repo_root=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -z "$repo_root" ]]; then
    exit 0
fi

rel_path="${file_path#"$repo_root"/}"

# Framework file patterns — files that require Orchestrator governance
FRAMEWORK_PATTERNS=(
    "CLAUDE.md"
    "skills/"
    "templates/"
    "docs/"
    "scripts/"
    "tools/"
    ".claude/hooks/"
    ".claude/settings.json"
    "framework-observations/README.md"
    "framework-observations/schema.yaml"
)

is_framework_file=false
for pattern in "${FRAMEWORK_PATTERNS[@]}"; do
    if [[ "$rel_path" == $pattern* ]]; then
        is_framework_file=true
        break
    fi
done

if [[ "$is_framework_file" == false ]]; then
    exit 0
fi

# --- Check for Orchestrator activation marker ---

MARKER="$repo_root/.claude/.orchestrator-activated"

if [[ ! -f "$MARKER" ]]; then
    echo "" >&2
    echo "BLOCKED: Orchestrator activation required before modifying framework files. (HR9)" >&2
    echo "" >&2
    echo "You must read skills/orchestrator/SKILL.md and follow its Session Resumption" >&2
    echo "process before editing framework files. The Orchestrator determines the" >&2
    echo "appropriate governance level for your changes." >&2
    echo "" >&2
    echo "Do this now:" >&2
    echo "  1. Read skills/orchestrator/SKILL.md" >&2
    echo "  2. Follow Session Resumption (read project-state.yaml, run health check, orient)" >&2
    echo "  3. The Orchestrator will create the activation marker, then you can proceed." >&2
    exit 2
fi

# Validate marker recency (must be created within the last 12 hours)
marker_age_ok=$(python3 -c "
import os, sys
from datetime import datetime, timedelta

marker = '$MARKER'
try:
    # Read timestamp from marker content
    with open(marker) as f:
        content = f.read().strip()
    if content:
        marker_time = datetime.fromisoformat(content)
    else:
        # Fall back to file mtime
        marker_time = datetime.fromtimestamp(os.path.getmtime(marker))

    age = datetime.now() - marker_time
    if age < timedelta(hours=12):
        print('ok')
    else:
        print('stale')
except Exception:
    # If we can't parse, fall back to mtime
    try:
        mtime = datetime.fromtimestamp(os.path.getmtime(marker))
        age = datetime.now() - mtime
        if age < timedelta(hours=12):
            print('ok')
        else:
            print('stale')
    except:
        print('stale')
" 2>/dev/null || echo "stale")

if [[ "$marker_age_ok" != "ok" ]]; then
    echo "" >&2
    echo "BLOCKED: Orchestrator activation marker is stale (older than 12 hours). (HR9)" >&2
    echo "" >&2
    echo "Re-read skills/orchestrator/SKILL.md and run Session Resumption to refresh." >&2
    exit 2
fi

# Marker exists and is fresh — allow the edit
exit 0
