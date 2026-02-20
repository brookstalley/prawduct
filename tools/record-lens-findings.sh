#!/usr/bin/env bash
#
# record-lens-findings.sh — Record structured Review Lenses findings
#
# Purpose: Records Review Lenses evaluation results for the Orchestrator to read.
# Analogous to record-critic-findings.sh but for prospective artifact evaluation.
#
# Merge behavior: When called multiple times in a session, findings ACCUMULATE
# (lenses are applied at multiple phases). Files are unioned, lenses are merged.
# The SessionStart hook clears findings on /clear or startup.
#
# Usage:
#   tools/record-lens-findings.sh \
#     --stage "artifact-generation" --phase "Phase A" \
#     --files .prawduct/artifacts/product-brief.md \
#     --lens "Product:warning:Scope includes unasked feature X" \
#     --lens "Design:note:Before-data state not addressed" \
#     --lens "Architecture:not-applied:Phase A - not applicable" \
#     --lens "Skeptic:not-applied:Phase A - not applicable" \
#     --lens "Testing:not-applied:No test specs yet"
#
# Options:
#   --product-dir DIR  Resolve product root from DIR instead of CWD.
#                      Use when a subagent's CWD differs from the target product.
#
# Exit codes:
#   0 — Findings recorded to .prawduct/.lens-findings.json
#   1 — Validation failure

set -euo pipefail

# --- Known lenses (from agents/review-lenses/SKILL.md) ---

ALL_VALID_LENSES=(
    "Product"
    "Design"
    "Architecture"
    "Skeptic"
    "Testing"
)

VALID_SEVERITIES="pass not-applied note warning blocking"

# --- Parse arguments ---

FILES=""
STAGE=""
PHASE=""
declare -a LENSES=()
_PRODUCT_DIR_OVERRIDE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --product-dir) _PRODUCT_DIR_OVERRIDE="$2"; shift 2 ;;
        --stage)   STAGE="$2"; shift 2 ;;
        --phase)   PHASE="$2"; shift 2 ;;
        --files)
            shift
            while [[ $# -gt 0 && ! "$1" =~ ^-- ]]; do
                if [[ -n "$FILES" ]]; then
                    FILES="$FILES,$1"
                else
                    FILES="$1"
                fi
                shift
            done
            ;;
        --lens)    LENSES+=("$2"); shift 2 ;;
        --help|-h)
            echo "Usage: tools/record-lens-findings.sh --stage STAGE --phase PHASE --files FILE [...] --lens ENTRY [...]"
            echo ""
            echo "Required:"
            echo "  --stage    Current stage (e.g., 'artifact-generation', 'building')"
            echo "  --files    Reviewed artifact files"
            echo "  --lens     One per lens, format: 'LensName:severity:summary'"
            echo ""
            echo "Optional:"
            echo "  --phase    Phase within stage (e.g., 'Phase A', 'Phase C')"
            echo ""
            echo "Lens names: ${ALL_VALID_LENSES[*]}"
            echo "Severities: $VALID_SEVERITIES"
            exit 0
            ;;
        *)
            echo "Error: Unknown argument: $1" >&2
            exit 1
            ;;
    esac
done

# --- Validation ---

errors=()

[[ -z "$FILES" ]] && errors+=("--files is required")
[[ -z "$STAGE" ]] && errors+=("--stage is required")

if [[ ${#LENSES[@]} -lt 1 ]]; then
    errors+=("At least 1 --lens entry required.")
fi

# Parse and validate each lens entry
declare -a PARSED_NAMES=()
declare -a PARSED_SEVERITIES=()
declare -a PARSED_SUMMARIES=()

for lens_entry in "${LENSES[@]}"; do
    lens_name=$(echo "$lens_entry" | cut -d: -f1)
    lens_sev=$(echo "$lens_entry" | cut -d: -f2)
    lens_summary=$(echo "$lens_entry" | cut -d: -f3-)

    [[ -z "$lens_name" ]] && errors+=("Lens entry missing name: '$lens_entry'")
    [[ -z "$lens_sev" ]] && errors+=("Lens entry missing severity: '$lens_entry'")
    [[ -z "$lens_summary" ]] && errors+=("Lens entry missing summary: '$lens_entry'")

    if [[ -n "$lens_name" ]]; then
        name_valid=false
        for valid_name in "${ALL_VALID_LENSES[@]}"; do
            if [[ "$lens_name" == "$valid_name" ]]; then
                name_valid=true
                break
            fi
        done
        if [[ "$name_valid" == false ]]; then
            errors+=("Invalid lens name: '$lens_name'. Valid: ${ALL_VALID_LENSES[*]}")
        fi
    fi

    # Normalize aliases
    [[ "$lens_sev" == "info" ]] && lens_sev="note"

    if [[ -n "$lens_sev" ]]; then
        sev_valid=false
        for valid_sev in $VALID_SEVERITIES; do
            if [[ "$lens_sev" == "$valid_sev" ]]; then
                sev_valid=true
                break
            fi
        done
        if [[ "$sev_valid" == false ]]; then
            errors+=("Invalid severity '$lens_sev' for lens '$lens_name'. Valid: $VALID_SEVERITIES")
        fi
    fi

    PARSED_NAMES+=("$lens_name")
    PARSED_SEVERITIES+=("$lens_sev")
    PARSED_SUMMARIES+=("$lens_summary")
done

if [[ ${#errors[@]} -gt 0 ]]; then
    echo "Validation errors:" >&2
    for err in "${errors[@]}"; do
        echo "  - $err" >&2
    done
    exit 1
fi

# --- Generate output ---

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)

# Determine output location via git-root-based product resolution.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/resolve-product-root.sh" ${_PRODUCT_DIR_OVERRIDE:+--product-dir "$_PRODUCT_DIR_OVERRIDE"}
OUTPUT_DIR="$PRODUCT_ROOT"
mkdir -p "$OUTPUT_DIR"
OUTPUT_FILE="$OUTPUT_DIR/.lens-findings.json"

IFS=',' read -ra FILE_ARRAY <<< "$FILES"

LENS_ARGS=""
for i in "${!PARSED_NAMES[@]}"; do
    LENS_ARGS+="${PARSED_NAMES[$i]}"$'\n'
    LENS_ARGS+="${PARSED_SEVERITIES[$i]}"$'\n'
    LENS_ARGS+="${PARSED_SUMMARIES[$i]}"$'\n'
done

python3 -c "
import json, sys, os

files = [f.strip() for f in sys.argv[1].split(',')]
timestamp = sys.argv[2]
stage = sys.argv[3]
phase = sys.argv[4] if sys.argv[4] != '' else None
output_file = sys.argv[5]

lens_lines = sys.stdin.read().strip().split('\n')
lenses = []
i = 0
while i + 2 < len(lens_lines):
    lenses.append({
        'name': lens_lines[i],
        'severity': lens_lines[i+1],
        'summary': lens_lines[i+2]
    })
    i += 3

# Merge with existing
existing_files = set()
existing_lenses = {}
existing_reviews = []
if os.path.exists(output_file):
    try:
        with open(output_file) as f:
            existing = json.load(f)
        existing_files = set(existing.get('reviewed_files', []))
        existing_reviews = existing.get('reviews', [])
    except (json.JSONDecodeError, KeyError):
        pass

merged_files = sorted(existing_files | set(files))

# Build this review entry
severity_order = {'not-applied': -1, 'pass': 0, 'note': 1, 'warning': 2, 'blocking': 3}
applicable = [l for l in lenses if l['severity'] not in ('not-applied',)]
if applicable:
    highest = max(applicable, key=lambda l: severity_order.get(l['severity'], 0))['severity']
else:
    highest = 'pass'

review_entry = {
    'timestamp': timestamp,
    'stage': stage,
    'phase': phase,
    'lenses': lenses,
    'highest_severity': highest
}

existing_reviews.append(review_entry)

output = {
    'reviewed_files': merged_files,
    'reviews': existing_reviews,
    'latest_review_timestamp': timestamp
}

with open(output_file, 'w') as f:
    json.dump(output, f, indent=2)
    f.write('\n')
" "$FILES" "$TIMESTAMP" "$STAGE" "${PHASE:-}" "$OUTPUT_FILE" <<< "$LENS_ARGS"

echo "Lens findings recorded to: $OUTPUT_FILE"
echo ""
echo "Summary:"
echo "  Stage: $STAGE${PHASE:+ / $PHASE}"
echo "  Files reviewed: ${#FILE_ARRAY[@]}"
echo "  Lenses: ${#LENSES[@]}"
for i in "${!PARSED_NAMES[@]}"; do
    sev="${PARSED_SEVERITIES[$i]}"
    marker="✓"
    if [[ "$sev" == "warning" ]]; then marker="⚠"; fi
    if [[ "$sev" == "blocking" ]]; then marker="✗"; fi
    if [[ "$sev" == "note" ]]; then marker="·"; fi
    if [[ "$sev" == "not-applied" ]]; then marker="—"; fi
    echo "  $marker ${PARSED_NAMES[$i]}: ${PARSED_SEVERITIES[$i]} — ${PARSED_SUMMARIES[$i]}"
done

exit 0
