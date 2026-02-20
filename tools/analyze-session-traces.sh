#!/usr/bin/env bash
#
# analyze-session-traces.sh — Local trace analysis tool
#
# Reads session traces from .prawduct/traces/ and surfaces patterns:
# - Gate block frequency by rule
# - PFR trigger rate
# - DCP frequency by tier
# - Session count and duration patterns
# - Friction hotspots (most-blocked files)
#
# All analysis happens locally on the user's machine. No network calls.
#
# Usage:
#   tools/analyze-session-traces.sh                    # Summary of all sessions
#   tools/analyze-session-traces.sh --last N            # Last N sessions only
#   tools/analyze-session-traces.sh --drill-down <ts>   # Full events for one session
#
# Options:
#   --product-dir DIR  Resolve product root from DIR instead of CWD.
#                      Use when a subagent's CWD differs from the target product.
#
# Exit codes:
#   0 — Report produced
#   1 — No traces found

set -uo pipefail

# Parse --product-dir before positional args
_PRODUCT_DIR_OVERRIDE=""
_remaining_args=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --product-dir) _PRODUCT_DIR_OVERRIDE="$2"; shift 2 ;;
        *) _remaining_args+=("$1"); shift ;;
    esac
done
set -- "${_remaining_args[@]+"${_remaining_args[@]}"}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/resolve-product-root.sh" ${_PRODUCT_DIR_OVERRIDE:+--product-dir "$_PRODUCT_DIR_OVERRIDE"}

TRACES_DIR="$PRODUCT_ROOT/traces"
SESSION_LOG="$TRACES_DIR/session-log.jsonl"
SESSIONS_DIR="$TRACES_DIR/sessions"

MODE="${1:---summary}"
ARG="${2:-}"

if [[ ! -d "$TRACES_DIR" ]]; then
    echo "No traces directory found at $TRACES_DIR"
    echo "Traces are created automatically during governance operations."
    exit 1
fi

if [[ "$MODE" == "--drill-down" && -n "$ARG" ]]; then
    # Show full events for a specific session archive
    archive="$SESSIONS_DIR/$ARG.json"
    if [[ ! -f "$archive" ]]; then
        # Try with .json extension
        archive="$SESSIONS_DIR/${ARG}"
        if [[ ! -f "$archive" ]]; then
            echo "Session archive not found: $ARG"
            echo "Available archives:"
            ls -1 "$SESSIONS_DIR"/*.json 2>/dev/null | while read -r f; do
                basename "$f" .json
            done
            exit 1
        fi
    fi

    python3 -c "
import json, sys

with open('$archive') as f:
    data = json.load(f)

print(f'Session: {data.get(\"session_started\", \"unknown\")}')
print(f'Stage: {data.get(\"current_stage\", \"unknown\")}')
print(f'Schema version: {data.get(\"schema_version\", \"?\")}')
print()

events = data.get('trace', {}).get('events', [])
print(f'Trace events: {len(events)}')
print()

for ev in events:
    ts = ev.get('ts', '?')
    etype = ev.get('type', '?')
    # Format based on event type
    detail_parts = []
    for k, v in ev.items():
        if k in ('ts', 'v', 'type'):
            continue
        detail_parts.append(f'{k}={v}')
    detail = ', '.join(detail_parts)
    print(f'  {ts}  {etype:20s}  {detail}')
"
    exit 0
fi

# --- Summary mode ---

LIMIT=""
if [[ "$MODE" == "--last" && -n "$ARG" ]]; then
    LIMIT="$ARG"
fi

python3 -c "
import json, sys, os, glob

session_log = '$SESSION_LOG'
sessions_dir = '$SESSIONS_DIR'
limit = '$LIMIT'

# Read session log
entries = []
if os.path.isfile(session_log):
    with open(session_log) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

if not entries:
    print('No session log entries found.')
    print('Traces are created when governance operations complete.')
    sys.exit(1)

if limit:
    try:
        entries = entries[-int(limit):]
    except ValueError:
        pass

print(f'Sessions analyzed: {len(entries)}')
print()

# Gate block summary
all_blocks = {}
total_blocks = 0
for entry in entries:
    for rule, count in entry.get('gate_blocks', {}).items():
        all_blocks[rule] = all_blocks.get(rule, 0) + count
        total_blocks += count

if all_blocks:
    print('## Gate Blocks by Rule')
    for rule, count in sorted(all_blocks.items(), key=lambda x: -x[1]):
        print(f'  {rule:20s}  {count:4d} blocks')
    print(f'  {\"TOTAL\":20s}  {total_blocks:4d} blocks')
    print()

# PFR and DCP summary
pfr_sessions = sum(1 for e in entries if e.get('pfr_triggered'))
dcp_tiers = {}
for entry in entries:
    tier = entry.get('dcp_tier')
    if tier:
        dcp_tiers[tier] = dcp_tiers.get(tier, 0) + 1

print('## Governance Triggers')
print(f'  PFR triggered:  {pfr_sessions}/{len(entries)} sessions ({100*pfr_sessions//max(len(entries),1)}%)')
for tier, count in sorted(dcp_tiers.items()):
    print(f'  DCP {tier}:  {count} sessions')
print()

# File edit summary
total_fw = sum(e.get('files_edited', {}).get('framework', 0) for e in entries)
total_prod = sum(e.get('files_edited', {}).get('product', 0) for e in entries)
total_gov = sum(e.get('files_edited', {}).get('governance_sensitive', 0) for e in entries)
total_obs = sum(e.get('observations_captured', 0) for e in entries)

print('## Edit Summary')
print(f'  Framework files:         {total_fw}')
print(f'  Product files:           {total_prod}')
print(f'  Governance-sensitive:    {total_gov}')
print(f'  Observations captured:   {total_obs}')
print()

# Session archives available
archives = sorted(glob.glob(os.path.join(sessions_dir, '*.json'))) if os.path.isdir(sessions_dir) else []
print(f'Session archives: {len(archives)} (use --drill-down <timestamp> to inspect)')
if archives:
    print(f'  Oldest: {os.path.basename(archives[0])}')
    print(f'  Newest: {os.path.basename(archives[-1])}')
" 2>/dev/null
