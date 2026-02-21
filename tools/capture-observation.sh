#!/usr/bin/env bash
#
# capture-observation.sh — Create schema-compliant observation files automatically
#
# Purpose: Reduces observation capture from "hand-write complex YAML" to
# "call a script with args." Auto-generates UUIDs, ISO-8601 timestamps,
# git SHAs, validates enums, and produces schema-compliant YAML.
#
# Note: The schema requires five_whys (structured array of why/answer pairs)
# in root_cause_analysis, but this tool only generates the summary RCA fields
# (symptom, root_cause, category). The five_whys array must be added by the
# agent when writing observations directly. The --rca-* fields provide the
# minimum RCA summary; the agent should always perform 5-whys analysis and
# include the full chain in the observation file.
#
# Usage:
#   tools/capture-observation.sh \
#     --session-type framework_dev \
#     --type process_friction \
#     --severity warning \
#     --description "Observation capture requires hand-writing 194-line schema YAML" \
#     --evidence "Existing observation files have inconsistent formats" \
#     --skills-affected "skills/orchestrator/SKILL.md,agents/critic/SKILL.md" \
#     [--stage meta] \
#     [--proposed-action "Create capture tool"] \
#     [--status noted] \
#     [--append path/to/existing-file.yaml] \
#     [--product-dir /path/to/project]
#
# For evaluation sessions, also pass:
#     --scenario-name family-utility
#
# For product_use sessions, also pass:
#     --product-classification "human_interface (screen) - Utility"
#
# Exit codes:
#   0 — Observation file written successfully
#   1 — Validation failure (missing required field, invalid enum value)

set -euo pipefail

# --- Valid enum values (from framework-observations/schema.yaml) ---

VALID_SESSION_TYPES="product_use evaluation framework_dev"

VALID_OBS_TYPES="proportionality coverage applicability missing_guidance rubric_issue process_friction artifact_insufficiency spec_ambiguity deployment_friction critic_gap skill_quality external_practice_drift documentation_drift structural_critique governance_compliance architectural_inconsistency integration_friction pushback defect"

VALID_SEVERITIES="note info warning blocking"

VALID_STAGES="0 0.5 1 2 3 4 5 6 meta"

VALID_STATUSES="noted triaged requires_pattern acted_on"

VALID_RCA_CATEGORIES="missing_process process_not_enforced incomplete_coverage wrong_abstraction missing_detection vocabulary_drift missing_guidance"

# --- Parse arguments ---

SESSION_TYPE=""
OBS_TYPE=""
SEVERITY=""
DESCRIPTION=""
EVIDENCE=""
SKILLS_AFFECTED=""
STAGE=""
PROPOSED_ACTION=""
STATUS="noted"
APPEND_FILE=""
SCENARIO_NAME=""
PRODUCT_CLASSIFICATION=""
RCA_SYMPTOM=""
RCA_ROOT_CAUSE=""
RCA_CATEGORY=""
_PRODUCT_DIR_OVERRIDE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --product-dir)        _PRODUCT_DIR_OVERRIDE="$2"; shift 2 ;;
        --session-type)       SESSION_TYPE="$2"; shift 2 ;;
        --type)               OBS_TYPE="$2"; shift 2 ;;
        --severity)           SEVERITY="$2"; shift 2 ;;
        --description)        DESCRIPTION="$2"; shift 2 ;;
        --evidence)           EVIDENCE="$2"; shift 2 ;;
        --skills-affected)    SKILLS_AFFECTED="$2"; shift 2 ;;
        --stage)              STAGE="$2"; shift 2 ;;
        --proposed-action)    PROPOSED_ACTION="$2"; shift 2 ;;
        --status)             STATUS="$2"; shift 2 ;;
        --append)             APPEND_FILE="$2"; shift 2 ;;
        --scenario-name)      SCENARIO_NAME="$2"; shift 2 ;;
        --product-classification) PRODUCT_CLASSIFICATION="$2"; shift 2 ;;
        --rca-symptom|--root-cause-symptom)        RCA_SYMPTOM="$2"; shift 2 ;;
        --rca-root-cause|--root-cause)            RCA_ROOT_CAUSE="$2"; shift 2 ;;
        --rca-category|--root-cause-category)     RCA_CATEGORY="$2"; shift 2 ;;
        --help|-h)
            echo "Usage: tools/capture-observation.sh --session-type TYPE --type OBS_TYPE --severity SEV --description DESC --evidence EVID --skills-affected SKILLS [options]"
            echo ""
            echo "Required:"
            echo "  --session-type     product_use | evaluation | framework_dev"
            echo "  --type             Observation type (see schema.yaml for full list)"
            echo "  --severity         note | warning | blocking"
            echo "  --description      What was observed (generalized, not product-specific)"
            echo "  --evidence         Specific evidence that triggered this observation"
            echo "  --skills-affected  Comma-separated list of affected skill paths"
            echo ""
            echo "Optional:"
            echo "  --stage              Framework stage (0, 0.5, 1-6, meta)"
            echo "  --proposed-action    Suggested action to address this"
            echo "  --status             noted (default) | triaged | requires_pattern | acted_on"
            echo "  --append FILE        Append observation to existing session file"
            echo "  --scenario-name      Required for evaluation sessions"
            echo "  --product-classification  Required for product_use sessions"
            echo ""
            echo "Root Cause Analysis (required for all observations):"
            echo "  --rca-symptom        The immediate problem observed"
            echo "    (alias: --root-cause-symptom)"
            echo "  --rca-root-cause     The deepest structural cause identified (from 5-whys)"
            echo "    (alias: --root-cause)"
            echo "  --rca-category       missing_process | process_not_enforced | incomplete_coverage |"
            echo "                       wrong_abstraction | missing_detection | vocabulary_drift"
            echo "    (alias: --root-cause-category)"
            exit 0
            ;;
        *)
            echo "Error: Unknown argument: $1" >&2
            echo "Run with --help for usage." >&2
            exit 1
            ;;
    esac
done

# --- Validation ---

errors=()

# Required fields
[[ -z "$SESSION_TYPE" ]]    && errors+=("--session-type is required")
[[ -z "$OBS_TYPE" ]]        && errors+=("--type is required")
[[ -z "$SEVERITY" ]]        && errors+=("--severity is required")
[[ -z "$DESCRIPTION" ]]     && errors+=("--description is required")
[[ -z "$EVIDENCE" ]]        && errors+=("--evidence is required")
[[ -z "$SKILLS_AFFECTED" ]] && errors+=("--skills-affected is required")

# Normalize common aliases before validation
[[ "$SEVERITY" == "info" ]] && SEVERITY="note"
[[ "$STATUS" == "open" || "$STATUS" == "new" ]] && STATUS="noted"

# Enum validation
validate_enum() {
    local value="$1"
    local name="$2"
    local valid="$3"
    if [[ -n "$value" ]]; then
        local found=false
        for v in $valid; do
            if [[ "$value" == "$v" ]]; then
                found=true
                break
            fi
        done
        if [[ "$found" == false ]]; then
            errors+=("Invalid $name: '$value'. Valid values: $valid")
        fi
    fi
}

validate_enum "$SESSION_TYPE" "--session-type" "$VALID_SESSION_TYPES"
validate_enum "$OBS_TYPE" "--type" "$VALID_OBS_TYPES"
validate_enum "$SEVERITY" "--severity" "$VALID_SEVERITIES"
validate_enum "$STATUS" "--status" "$VALID_STATUSES"
[[ -n "$STAGE" ]] && validate_enum "$STAGE" "--stage" "$VALID_STAGES"

# Session-type-specific requirements
if [[ "$SESSION_TYPE" == "evaluation" && -z "$SCENARIO_NAME" ]]; then
    errors+=("--scenario-name is required for evaluation sessions")
fi
if [[ "$SESSION_TYPE" == "product_use" && -z "$PRODUCT_CLASSIFICATION" ]]; then
    errors+=("--product-classification is required for product_use sessions")
fi

# RCA validation: all three --rca-* arguments are always required
# If an observation isn't worth analyzing causally, it isn't worth recording.
[[ -z "$RCA_SYMPTOM" ]]    && errors+=("--rca-symptom is required (root cause analysis is mandatory for all observations)")
[[ -z "$RCA_ROOT_CAUSE" ]] && errors+=("--rca-root-cause is required (root cause analysis is mandatory for all observations)")
[[ -z "$RCA_CATEGORY" ]]   && errors+=("--rca-category is required (root cause analysis is mandatory for all observations)")
[[ -n "$RCA_CATEGORY" ]] && validate_enum "$RCA_CATEGORY" "--rca-category" "$VALID_RCA_CATEGORIES"

# Report all errors at once
if [[ ${#errors[@]} -gt 0 ]]; then
    echo "Validation errors:" >&2
    for err in "${errors[@]}"; do
        echo "  - $err" >&2
    done
    exit 1
fi

# --- Generate auto values ---

OBS_UUID=$(uuidgen | tr '[:upper:]' '[:lower:]')
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
TODAY=$(date +%Y-%m-%d)
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# --- Determine output location ---

# Resolve product root (shared detection logic)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/resolve-product-root.sh" ${_PRODUCT_DIR_OVERRIDE:+--product-dir "$_PRODUCT_DIR_OVERRIDE"}
OBS_DIR=""

if [[ -n "$APPEND_FILE" ]]; then
    # Appending to existing file — validate it exists
    if [[ ! -f "$APPEND_FILE" ]]; then
        echo "Error: Append target does not exist: $APPEND_FILE" >&2
        exit 1
    fi
    OUTPUT_FILE="$APPEND_FILE"
else
    # Use product root for observation directory, with write-permission check
    if [[ -d "$PRODUCT_ROOT/framework-observations" && -w "$PRODUCT_ROOT/framework-observations" ]]; then
        OBS_DIR="$PRODUCT_ROOT/framework-observations"
    else
        # Fallback: write to working-notes in product root
        mkdir -p "$PRODUCT_ROOT/working-notes"
        OBS_DIR="$PRODUCT_ROOT/working-notes"
        echo "Note: Framework observations dir not writable. Writing to $OBS_DIR/" >&2
    fi

    # Generate filename slug from description (first 6 words, hyphenated)
    SLUG=$(echo "$DESCRIPTION" | tr '[:upper:]' '[:lower:]' | tr -cs '[:alnum:]' '-' | sed 's/^-//;s/-$//' | cut -d'-' -f1-6)
    if [[ "$OBS_DIR" == *"/working-notes" ]]; then
        OUTPUT_FILE="$OBS_DIR/framework-observations-${TODAY}.yaml"
    else
        OUTPUT_FILE="$OBS_DIR/${TODAY}-${SLUG}.yaml"
    fi
fi

# --- Build YAML ---

if [[ -n "$APPEND_FILE" ]]; then
    # Append mode: add observation entry to existing observations array
    # Find the skills_affected line and insert before it
    OBS_ENTRY=""
    OBS_ENTRY+="  - type: $OBS_TYPE"$'\n'
    [[ -n "$STAGE" ]] && OBS_ENTRY+="    stage: $STAGE"$'\n'
    OBS_ENTRY+="    severity: $SEVERITY"$'\n'
    OBS_ENTRY+="    description: \"$(echo "$DESCRIPTION" | sed 's/"/\\"/g')\""$'\n'
    OBS_ENTRY+="    evidence: \"$(echo "$EVIDENCE" | sed 's/"/\\"/g')\""$'\n'
    [[ -n "$PROPOSED_ACTION" ]] && OBS_ENTRY+="    proposed_action: \"$(echo "$PROPOSED_ACTION" | sed 's/"/\\"/g')\""$'\n'
    OBS_ENTRY+="    status: $STATUS"
    OBS_ENTRY+=$'\n'"    root_cause_analysis:"
    OBS_ENTRY+=$'\n'"      symptom: \"$(echo "$RCA_SYMPTOM" | sed 's/"/\\"/g')\""
    OBS_ENTRY+=$'\n'"      root_cause: \"$(echo "$RCA_ROOT_CAUSE" | sed 's/"/\\"/g')\""
    OBS_ENTRY+=$'\n'"      category: $RCA_CATEGORY"

    # Append before the skills_affected line
    # Write entry to a temp file, then use sed to insert it (awk -v cannot
    # handle multi-line strings — the newlines in $OBS_ENTRY break it).
    ENTRY_FILE=$(mktemp)
    printf '%s\n' "$OBS_ENTRY" > "$ENTRY_FILE"
    TMPFILE=$(mktemp)
    if grep -q "^skills_affected:" "$APPEND_FILE"; then
        # Insert observation entry before skills_affected
        while IFS= read -r line; do
            if [[ "$line" == "skills_affected:"* ]]; then
                cat "$ENTRY_FILE"
            fi
            printf '%s\n' "$line"
        done < "$APPEND_FILE" > "$TMPFILE"
        mv "$TMPFILE" "$APPEND_FILE"
    else
        # No skills_affected found — append before closing ---
        found_first=false
        while IFS= read -r line; do
            if [[ "$line" == "---" && "$found_first" == true ]]; then
                cat "$ENTRY_FILE"
            fi
            printf '%s\n' "$line"
            found_first=true
        done < "$APPEND_FILE" > "$TMPFILE"
        mv "$TMPFILE" "$APPEND_FILE"
    fi
    rm -f "$ENTRY_FILE"

    # Add any new skills to skills_affected
    IFS=',' read -ra NEW_SKILLS <<< "$SKILLS_AFFECTED"
    for skill in "${NEW_SKILLS[@]}"; do
        skill=$(echo "$skill" | xargs)  # trim whitespace
        if ! grep -qF "\"$skill\"" "$APPEND_FILE" 2>/dev/null; then
            # Add this skill to the skills_affected list
            TMPFILE=$(mktemp)
            awk -v skill="$skill" '/^skills_affected:/ { print; getline; print; while (/^  - /) { print; getline; } print "  - \"" skill "\""; print; next } { print }' "$APPEND_FILE" > "$TMPFILE"
            mv "$TMPFILE" "$APPEND_FILE"
        fi
    done

    echo "Observation appended to: $OUTPUT_FILE"
else
    # New file mode: write complete observation file

    # Build session_context
    SESSION_CONTEXT="  framework_version: $GIT_SHA"
    if [[ "$SESSION_TYPE" == "evaluation" ]]; then
        SESSION_CONTEXT="  scenario_name: $SCENARIO_NAME"$'\n'"  framework_version: $GIT_SHA"
    elif [[ "$SESSION_TYPE" == "product_use" ]]; then
        SESSION_CONTEXT="  product_classification: \"$PRODUCT_CLASSIFICATION\""$'\n'"  framework_version: $GIT_SHA"
    fi

    # Build skills_affected array
    SKILLS_YAML=""
    IFS=',' read -ra SKILL_ARRAY <<< "$SKILLS_AFFECTED"
    for skill in "${SKILL_ARRAY[@]}"; do
        skill=$(echo "$skill" | xargs)  # trim whitespace
        SKILLS_YAML+="  - \"$skill\""$'\n'
    done
    # Remove trailing newline
    SKILLS_YAML="${SKILLS_YAML%$'\n'}"

    # Build observation entry
    OBS_YAML=""
    OBS_YAML+="  - type: $OBS_TYPE"$'\n'
    [[ -n "$STAGE" ]] && OBS_YAML+="    stage: $STAGE"$'\n'
    OBS_YAML+="    severity: $SEVERITY"$'\n'
    OBS_YAML+="    description: \"$(echo "$DESCRIPTION" | sed 's/"/\\"/g')\""$'\n'
    OBS_YAML+="    evidence: \"$(echo "$EVIDENCE" | sed 's/"/\\"/g')\""$'\n'
    [[ -n "$PROPOSED_ACTION" ]] && OBS_YAML+="    proposed_action: \"$(echo "$PROPOSED_ACTION" | sed 's/"/\\"/g')\""$'\n'
    OBS_YAML+="    status: $STATUS"
    OBS_YAML+=$'\n'"    root_cause_analysis:"
    OBS_YAML+=$'\n'"      symptom: \"$(echo "$RCA_SYMPTOM" | sed 's/"/\\"/g')\""
    OBS_YAML+=$'\n'"      root_cause: \"$(echo "$RCA_ROOT_CAUSE" | sed 's/"/\\"/g')\""
    OBS_YAML+=$'\n'"      category: $RCA_CATEGORY"

    cat > "$OUTPUT_FILE" <<YAMLEOF
---
observation_id: $OBS_UUID
timestamp: $TIMESTAMP
session_type: $SESSION_TYPE
session_context:
$SESSION_CONTEXT
observations:
$OBS_YAML
skills_affected:
$SKILLS_YAML
---
YAMLEOF

    echo "Observation written to: $OUTPUT_FILE"
fi

# --- Increment observations_captured_this_session in session-governance.json ---
# Resolves the desync between observation file capture and governance counter.
# Without this, the stop hook blocks with "warning-severity issues but 0 observations".
SESSION_GOV="$PRODUCT_ROOT/.session-governance.json"
if [[ -f "$SESSION_GOV" ]]; then
    python3 -c "
import json, sys
try:
    with open('$SESSION_GOV') as f:
        data = json.load(f)
    gs = data.get('governance_state', {})
    gs['observations_captured_this_session'] = gs.get('observations_captured_this_session', 0) + 1
    data['governance_state'] = gs
    with open('$SESSION_GOV', 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')
except Exception as e:
    print(f'Warning: Could not update session counter: {e}', file=sys.stderr)
" 2>/dev/null || true
fi

exit 0
