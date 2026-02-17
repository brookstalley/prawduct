#!/usr/bin/env bash
#
# format-contribution.sh — Format an observation file as shareable contribution markdown
#
# Reads an observation YAML file and produces human-readable markdown suitable
# for contributing back to the framework repo (via GitHub issue or direct copy).
#
# Usage:
#   tools/format-contribution.sh <observation.yaml> [--output stdout|file]
#
# Options:
#   --output stdout   Print markdown to stdout (default)
#   --output file     Write to <observation-basename>.contribution.md
#
# Exit codes:
#   0 — Success
#   1 — Missing or invalid input file

set -euo pipefail

# --- Parse arguments ---

INPUT_FILE=""
OUTPUT_MODE="stdout"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --output)
            OUTPUT_MODE="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: tools/format-contribution.sh <observation.yaml> [--output stdout|file]"
            echo ""
            echo "Formats an observation file as shareable markdown for contributing"
            echo "back to the prawduct framework."
            echo ""
            echo "Options:"
            echo "  --output stdout   Print to stdout (default)"
            echo "  --output file     Write to <basename>.contribution.md"
            exit 0
            ;;
        *)
            if [[ -z "$INPUT_FILE" ]]; then
                INPUT_FILE="$1"
            else
                echo "Error: Unexpected argument: $1" >&2
                exit 1
            fi
            shift
            ;;
    esac
done

if [[ -z "$INPUT_FILE" ]]; then
    echo "Error: No observation file specified." >&2
    echo "Usage: tools/format-contribution.sh <observation.yaml> [--output stdout|file]" >&2
    exit 1
fi

if [[ ! -f "$INPUT_FILE" ]]; then
    echo "Error: File not found: $INPUT_FILE" >&2
    exit 1
fi

if [[ "$OUTPUT_MODE" != "stdout" && "$OUTPUT_MODE" != "file" ]]; then
    echo "Error: --output must be 'stdout' or 'file'" >&2
    exit 1
fi

# --- Resolve framework repo URL ---

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Try to get framework path from .prawduct/framework-path first
FRAMEWORK_PATH_FILE=""
if [[ -f ".prawduct/framework-path" ]]; then
    FRAMEWORK_PATH_FILE=".prawduct/framework-path"
fi

REPO_URL=""
if [[ -n "$FRAMEWORK_PATH_FILE" ]]; then
    FW_DIR=$(cat "$FRAMEWORK_PATH_FILE")
    REPO_URL=$(cd "$FW_DIR" && git remote get-url origin 2>/dev/null || echo "")
elif [[ -d "$FRAMEWORK_DIR/.git" ]]; then
    REPO_URL=$(cd "$FRAMEWORK_DIR" && git remote get-url origin 2>/dev/null || echo "")
fi

# Convert SSH URL to HTTPS for display
if [[ "$REPO_URL" == git@* ]]; then
    REPO_URL=$(echo "$REPO_URL" | sed 's|git@\(.*\):\(.*\)\.git|https://\1/\2|')
elif [[ "$REPO_URL" == *.git ]]; then
    REPO_URL="${REPO_URL%.git}"
fi

ISSUES_URL=""
if [[ -n "$REPO_URL" ]]; then
    ISSUES_URL="${REPO_URL}/issues"
fi

# --- Extract key fields from YAML ---

# Simple extraction using grep/sed (avoids yq dependency)
extract_field() {
    local file="$1"
    local field="$2"
    grep -m1 "^  *${field}:" "$file" 2>/dev/null | sed "s/.*${field}: *\"\{0,1\}\(.*\)\"\{0,1\}/\1/" | sed 's/"$//' || echo ""
}

OBS_DESCRIPTION=$(extract_field "$INPUT_FILE" "description")
OBS_EVIDENCE=$(extract_field "$INPUT_FILE" "evidence")
OBS_TYPE=$(extract_field "$INPUT_FILE" "type")
OBS_SEVERITY=$(extract_field "$INPUT_FILE" "severity")
OBS_PROPOSED_ACTION=$(extract_field "$INPUT_FILE" "proposed_action")

# Extract RCA fields if present
RCA_SYMPTOM=$(extract_field "$INPUT_FILE" "symptom")
RCA_ROOT_CAUSE=$(extract_field "$INPUT_FILE" "root_cause")
RCA_CATEGORY=$(extract_field "$INPUT_FILE" "category")

# --- Build markdown ---

MARKDOWN=""
MARKDOWN+="# Framework Observation: ${OBS_TYPE}"$'\n'
MARKDOWN+=""$'\n'
MARKDOWN+="## Summary"$'\n'
MARKDOWN+=""$'\n'
MARKDOWN+="**Type:** ${OBS_TYPE}"$'\n'
MARKDOWN+="**Severity:** ${OBS_SEVERITY}"$'\n'
MARKDOWN+=""$'\n'
MARKDOWN+="${OBS_DESCRIPTION}"$'\n'
MARKDOWN+=""$'\n'
MARKDOWN+="## Evidence"$'\n'
MARKDOWN+=""$'\n'
MARKDOWN+="${OBS_EVIDENCE}"$'\n'

if [[ -n "$OBS_PROPOSED_ACTION" && "$OBS_PROPOSED_ACTION" != "null" ]]; then
    MARKDOWN+=""$'\n'
    MARKDOWN+="## Proposed Action"$'\n'
    MARKDOWN+=""$'\n'
    MARKDOWN+="${OBS_PROPOSED_ACTION}"$'\n'
fi

if [[ -n "$RCA_SYMPTOM" ]]; then
    MARKDOWN+=""$'\n'
    MARKDOWN+="## Root Cause Analysis"$'\n'
    MARKDOWN+=""$'\n'
    MARKDOWN+="**Symptom:** ${RCA_SYMPTOM}"$'\n'
    MARKDOWN+="**Root Cause:** ${RCA_ROOT_CAUSE}"$'\n'
    MARKDOWN+="**Category:** ${RCA_CATEGORY}"$'\n'
fi

MARKDOWN+=""$'\n'
MARKDOWN+="## Full Observation YAML"$'\n'
MARKDOWN+=""$'\n'
MARKDOWN+='```yaml'$'\n'
MARKDOWN+="$(cat "$INPUT_FILE")"$'\n'
MARKDOWN+='```'$'\n'

MARKDOWN+=""$'\n'
MARKDOWN+="## How to Contribute"$'\n'
MARKDOWN+=""$'\n'
if [[ -n "$ISSUES_URL" ]]; then
    MARKDOWN+="To contribute this observation back to the framework:"$'\n'
    MARKDOWN+=""$'\n'
    MARKDOWN+="1. **Open an issue** at ${ISSUES_URL}/new with this content"$'\n'
    MARKDOWN+="2. **Or copy the YAML** directly to the framework's \`.prawduct/framework-observations/\` directory"$'\n'
else
    MARKDOWN+="To contribute this observation back to the framework:"$'\n'
    MARKDOWN+=""$'\n'
    MARKDOWN+="1. Copy the YAML above to the framework's \`.prawduct/framework-observations/\` directory"$'\n'
    MARKDOWN+="2. Or open an issue on the framework repository with this content"$'\n'
fi

# --- Output ---

if [[ "$OUTPUT_MODE" == "file" ]]; then
    BASENAME=$(basename "$INPUT_FILE" .yaml)
    OUTPUT_FILE="$(dirname "$INPUT_FILE")/${BASENAME}.contribution.md"
    echo "$MARKDOWN" > "$OUTPUT_FILE"
    echo "Contribution formatted: $OUTPUT_FILE"
else
    echo "$MARKDOWN"
fi

exit 0
