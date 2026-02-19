#!/usr/bin/env bash
#
# measure-context-overhead.sh — Measure token-approximate context overhead of framework startup
#
# Counts words (rough token proxy, ~1.3 words/token) in the files loaded at
# session start: CLAUDE.md + Orchestrator SKILL.md + project-state.yaml + stage file.
# Reports total and per-file to give a baseline for the "context consumed by framework" claim.
#
# Usage:
#   tools/measure-context-overhead.sh              # Default: measure self-hosted
#   tools/measure-context-overhead.sh /path/to/project  # Measure a product project
#
# Exit codes:
#   0 — Report produced

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FW_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TARGET="${1:-$FW_ROOT}"

echo "=========================================="
echo " Context Overhead Measurement"
echo " $(date +%Y-%m-%d)"
echo "=========================================="
echo ""

total_words=0
total_lines=0

measure_file() {
    local label="$1"
    local filepath="$2"
    if [[ -f "$filepath" ]]; then
        local words lines
        words=$(wc -w < "$filepath" | tr -d ' ')
        lines=$(wc -l < "$filepath" | tr -d ' ')
        local est_tokens=$(( words * 100 / 75 ))  # ~1.33 tokens/word
        printf "  %-45s %5s words  %5s lines  ~%s tokens\n" "$label" "$words" "$lines" "$est_tokens"
        total_words=$(( total_words + words ))
        total_lines=$(( total_lines + lines ))
    else
        printf "  %-45s (not found)\n" "$label"
    fi
}

echo "## Always-Loaded Files"
echo ""
measure_file "CLAUDE.md" "$TARGET/CLAUDE.md"
measure_file "Orchestrator SKILL.md" "$FW_ROOT/skills/orchestrator/SKILL.md"
echo ""

echo "## Session-Start Files (loaded during resumption)"
echo ""

# Detect product root
if [[ -d "$TARGET/.prawduct" ]]; then
    PRODUCT_ROOT="$TARGET/.prawduct"
else
    PRODUCT_ROOT="$TARGET"
fi

measure_file "project-state.yaml" "$PRODUCT_ROOT/project-state.yaml"

# Determine which stage file would be loaded
STAGE=$(python3 -c "
import yaml, sys
try:
    with open('$PRODUCT_ROOT/project-state.yaml') as f:
        data = yaml.safe_load(f)
    print(data.get('current_stage', 'unknown'))
except:
    print('unknown')
" 2>/dev/null || echo "unknown")

case "$STAGE" in
    intake|discovery|definition)  STAGE_FILE="$FW_ROOT/skills/orchestrator/stages-0-2.md" ;;
    artifact-generation|build-planning)  STAGE_FILE="$FW_ROOT/skills/orchestrator/stages-3-4.md" ;;
    building)  STAGE_FILE="$FW_ROOT/skills/orchestrator/stage-5-build.md" ;;
    iteration)  STAGE_FILE="$FW_ROOT/skills/orchestrator/stage-6-iteration.md" ;;
    *)  STAGE_FILE="" ;;
esac

if [[ -n "$STAGE_FILE" ]]; then
    measure_file "Stage file ($STAGE)" "$STAGE_FILE"
fi

echo ""
echo "## Summary"
total_tokens=$(( total_words * 100 / 75 ))
echo ""
echo "  Total: $total_words words, $total_lines lines, ~$total_tokens tokens"
echo ""

# Context budget estimate (200k tokens typical)
budget=200000
pct=$(( total_tokens * 100 / budget ))
echo "  Estimated context usage: ~${pct}% of 200k token budget"
echo ""
echo "=========================================="
