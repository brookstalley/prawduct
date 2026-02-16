#!/usr/bin/env bash
#
# governance-gate.sh — PreToolUse hook for Edit/Write/Read
#
# Unified governance gate. Fires before every Edit, Write, or Read tool call.
# Enforces three governance requirements:
#
# 1. Skill/template read gating: Reads of skill files (except orchestrator/SKILL.md)
#    and template files are blocked until the Orchestrator is activated. This ensures
#    all framework access routes through the Orchestrator. (HR9)
#
# 2. Orchestrator activation: Edits/writes to any governed file require Orchestrator
#    activation. (HR9: No Governance Bypass)
#
# 3. Chunk review: If a product build is active and chunks have been completed
#    without Critic review, blocks further product file edits until governance
#    debt is resolved.
#
# Marker lifecycle:
#   Created:  Orchestrator activation (step 3) or Session Resumption (step 1)
#   Read:     This hook (PreToolUse, on every Edit/Write/Read to governed files)
#   Deleted:  On /clear (SessionStart hook), new startup (SessionStart hook),
#             or successful commit (critic-gate.sh cleanup)
#
# Hook protocol:
#   - Reads JSON from stdin (tool_name, tool_input with file_path)
#   - exit 0: allow the tool call
#   - exit 2: deny the tool call (stderr message shown to Claude)

set -euo pipefail

# Read the hook input JSON from stdin
input=$(cat)

# Extract the tool name and file path from the tool input
read -r tool_name file_path <<< "$(echo "$input" | python3 -c "
import json, sys
data = json.load(sys.stdin)
tool_name = data.get('tool_name', '')
tool_input = data.get('tool_input', {})
file_path = tool_input.get('file_path', '')
print(f'{tool_name} {file_path}')
" 2>/dev/null || echo " ")"

if [[ -z "$file_path" ]]; then
    exit 0
fi

# Derive framework root from this script's location (hooks live at <framework>/.claude/hooks/)
FRAMEWORK_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
CLAUDE_DIR="${CLAUDE_PROJECT_DIR:-$repo_root}/.claude"
rel_path=""
if [[ -n "$repo_root" ]]; then
    rel_path="${file_path#"$repo_root"/}"
fi

# --- For Read calls: only gate skill and template files ---

if [[ "$tool_name" == "Read" ]]; then
    if [[ -z "$repo_root" || -z "$rel_path" ]]; then
        exit 0
    fi

    # Check if this is a skill or template file
    is_gated_read=false
    if [[ "$rel_path" == skills/* || "$rel_path" == templates/* ]]; then
        is_gated_read=true
    fi

    if [[ "$is_gated_read" == false ]]; then
        exit 0
    fi

    # Whitelist: orchestrator/SKILL.md is always readable (it's the entry point)
    if [[ "$rel_path" == "skills/orchestrator/SKILL.md" ]]; then
        exit 0
    fi

    # Check Orchestrator activation
    MARKER="$CLAUDE_DIR/.orchestrator-activated"
    if [[ ! -f "$MARKER" ]]; then
        echo "" >&2
        echo "BLOCKED: Reading skill/template files requires Orchestrator activation. (HR9)" >&2
        echo "" >&2
        echo "Skills and templates are accessed through the Orchestrator. Before reading" >&2
        echo "this file, you must activate governance:" >&2
        echo "" >&2
        echo "  1. Read skills/orchestrator/SKILL.md (this file is always readable)" >&2
        echo "  2. Follow its activation process (Session Resumption or new project setup)" >&2
        echo "  3. After activation, skill and template files are accessible." >&2
        exit 2
    fi

    # Validate marker recency
    marker_age_ok=$(python3 -c "
import os, sys
from datetime import datetime, timedelta

marker = '$MARKER'
try:
    with open(marker) as f:
        content = f.read().strip()
    if content:
        marker_time = datetime.fromisoformat(content)
    else:
        marker_time = datetime.fromtimestamp(os.path.getmtime(marker))
    age = datetime.now() - marker_time
    if age < timedelta(hours=12):
        print('ok')
    else:
        print('stale')
except Exception:
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

    # Read allowed
    exit 0
fi

# --- For Edit/Write calls: full governance checks ---

# Determine if this file is governed
# A file is governed if it's a framework file (in the repo) or a product file
# (in an active product build directory).

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
if [[ -n "$repo_root" && "$repo_root" == "$FRAMEWORK_ROOT" ]]; then
    for pattern in "${FRAMEWORK_PATTERNS[@]}"; do
        if [[ "$rel_path" == $pattern* ]]; then
            is_framework_file=true
            break
        fi
    done
fi

# Check if file is in an active product build directory
is_product_file=false
SESSION_FILE=""
if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
    SESSION_FILE="$CLAUDE_PROJECT_DIR/.claude/.session-governance.json"
    if [[ -f "$SESSION_FILE" ]]; then
        product_dir=$(python3 -c "
import json
try:
    with open('$SESSION_FILE') as f:
        data = json.load(f)
    print(data.get('product_dir', ''))
except:
    print('')
" 2>/dev/null || echo "")

        if [[ -n "$product_dir" ]]; then
            norm_file=$(cd "$(dirname "$file_path")" 2>/dev/null && pwd)/$(basename "$file_path") 2>/dev/null || echo "$file_path"
            if [[ "$norm_file" == "$product_dir"* ]]; then
                is_product_file=true
            fi
        fi
    fi
fi

# If neither framework nor product file, allow
if [[ "$is_framework_file" == false && "$is_product_file" == false ]]; then
    exit 0
fi

# --- Check 1: Orchestrator activation (applies to framework files) ---

if [[ "$is_framework_file" == true && -n "$repo_root" ]]; then
    MARKER="$CLAUDE_DIR/.orchestrator-activated"

    if [[ ! -f "$MARKER" ]]; then
        echo "" >&2
        echo "BLOCKED: Orchestrator activation required before modifying governed files. (HR9)" >&2
        echo "" >&2
        echo "You must read skills/orchestrator/SKILL.md and follow its activation process" >&2
        echo "before editing governed files. The Orchestrator determines the appropriate" >&2
        echo "governance level for your changes." >&2
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
    with open(marker) as f:
        content = f.read().strip()
    if content:
        marker_time = datetime.fromisoformat(content)
    else:
        marker_time = datetime.fromtimestamp(os.path.getmtime(marker))

    age = datetime.now() - marker_time
    if age < timedelta(hours=12):
        print('ok')
    else:
        print('stale')
except Exception:
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
fi

# --- Check 2: Chunk review gate (applies to product files during builds) ---

if [[ "$is_product_file" == true && -f "$SESSION_FILE" ]]; then
    # Exception: always allow edits to project-state.yaml (needed to record reviews)
    basename_file=$(basename "$file_path")
    if [[ "$basename_file" == "project-state.yaml" ]]; then
        exit 0
    fi

    result=$(python3 -c "
import json, sys

session_file = '$SESSION_FILE'
try:
    with open(session_file) as f:
        session = json.load(f)
except:
    sys.exit(0)

gov = session.get('governance_state', {})

# Block when chunks have been completed without Critic review
chunks_without_review = gov.get('chunks_completed_without_review', 0)
if chunks_without_review > 0:
    print(f'BLOCKED: {chunks_without_review} chunk(s) completed without Critic review.')
else:
    print('')
" 2>/dev/null || echo "")

    if [[ -n "$result" && "$result" != "" ]]; then
        echo "" >&2
        echo "$result" >&2
        echo "" >&2
        echo "Product file edits are BLOCKED until governance debt is resolved." >&2
        echo "" >&2
        echo "To unblock — read skill files from disk (they survive context compaction):" >&2
        echo "  1. Read skills/critic/SKILL.md from disk NOW, then apply Product Governance to completed chunks" >&2
        echo "  2. Record findings in project-state.yaml -> build_state.reviews" >&2
        echo "  3. Update .claude/.session-governance.json -> governance_state.chunks_completed_without_review to 0" >&2
        exit 2
    fi
fi

# All checks passed — allow the operation
exit 0
