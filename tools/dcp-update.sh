#!/usr/bin/env bash
#
# dcp-update.sh — Manage Directional Change Protocol state
#
# Purpose: Wraps DCP state transitions that previously required manual JSON edits
# to .session-governance.json. Reduces the 5+ manual edits per DCP to single
# commands, eliminating a major source of process friction (Pattern Extractor
# Cluster 1, root cause: no tooling layer for workflow state management).
#
# Usage:
#   tools/dcp-update.sh classify --tier enhancement --description "Add NFR traceability"
#   tools/dcp-update.sh classify --tier structural --description "Redesign stage pipeline" --phases 3
#   tools/dcp-update.sh classify --tier mechanical
#   tools/dcp-update.sh phase-reviewed
#   tools/dcp-update.sh plan-reviewed
#   tools/dcp-update.sh artifacts-verified --artifacts "build-plan.md nonfunctional-requirements.md"
#   tools/dcp-update.sh observation-captured
#   tools/dcp-update.sh retrospective-done
#   tools/dcp-update.sh complete
#   tools/dcp-update.sh status

set -euo pipefail

# Resolve framework root (same as governance-hook shim)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRAMEWORK_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Resolve product .prawduct dir
if [[ -n "${CLAUDE_PROJECT_DIR:-}" ]]; then
    PRAWDUCT_DIR="$CLAUDE_PROJECT_DIR/.prawduct"
else
    PRAWDUCT_DIR="$FRAMEWORK_ROOT/.prawduct"
fi

# Follow .active-product pointer if it exists
ACTIVE_PRODUCT="$PRAWDUCT_DIR/.active-product"
if [[ -f "$ACTIVE_PRODUCT" ]]; then
    TARGET_DIR=$(cat "$ACTIVE_PRODUCT" | tr -d '[:space:]')
    if [[ -d "$TARGET_DIR/.prawduct" ]]; then
        PRODUCT_PRAWDUCT="$TARGET_DIR/.prawduct"
    else
        PRODUCT_PRAWDUCT="$PRAWDUCT_DIR"
    fi
else
    PRODUCT_PRAWDUCT="$PRAWDUCT_DIR"
fi

SESSION_FILE="$PRODUCT_PRAWDUCT/.session-governance.json"

if [[ ! -f "$SESSION_FILE" ]]; then
    echo "ERROR: No session governance file at $SESSION_FILE" >&2
    exit 1
fi

usage() {
    cat <<'EOF'
Usage: tools/dcp-update.sh <command> [options]

Commands:
  classify              Set DCP tier and activate tracking
    --tier TYPE         Required: mechanical | enhancement | structural
    --description TEXT  Required for enhancement/structural: plan summary
    --phases N          Optional: total phases (structural only, default 1)

  phase-reviewed        Increment phases_reviewed_count
  plan-reviewed         Mark plan-stage review completed (structural only)
  artifacts-verified    Record verified artifacts
    --artifacts LIST    Space-separated artifact names
  observation-captured  Mark observation as captured
  retrospective-done    Mark retrospective as completed
  complete              Set active=false (after commit)
  status                Show current DCP state
EOF
    exit 1
}

# Use Python for JSON manipulation (jq not guaranteed on macOS)
json_read() {
    python3 -c "
import json, sys
with open('$SESSION_FILE') as f:
    data = json.load(f)
dc = data.get('directional_change', {})
print(json.dumps(dc, indent=2))
"
}

json_update() {
    # $1 = Python dict expression to merge into directional_change
    python3 -c "
import json
with open('$SESSION_FILE') as f:
    data = json.load(f)
dc = data.setdefault('directional_change', {})
dc.update($1)
with open('$SESSION_FILE', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
"
}

[[ $# -lt 1 ]] && usage

COMMAND="$1"
shift

case "$COMMAND" in
    classify)
        TIER=""
        DESC=""
        PHASES=1
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --tier) TIER="$2"; shift 2 ;;
                --description) DESC="$2"; shift 2 ;;
                --phases) PHASES="$2"; shift 2 ;;
                *) echo "Unknown option: $1" >&2; exit 1 ;;
            esac
        done

        if [[ -z "$TIER" ]]; then
            echo "ERROR: --tier is required" >&2
            exit 1
        fi

        case "$TIER" in
            mechanical)
                json_update '{"needs_classification": False, "active": False, "tier": "mechanical"}'
                echo "DCP: classified as mechanical (no DCP needed)"
                ;;
            enhancement)
                if [[ -z "$DESC" ]]; then
                    echo "ERROR: --description required for enhancement tier" >&2
                    exit 1
                fi
                json_update "{\"active\": True, \"needs_classification\": False, \"tier\": \"enhancement\", \"plan_description\": \"$DESC\", \"retrospective_completed\": False, \"observation_captured\": False, \"artifacts_verified\": []}"
                echo "DCP: classified as enhancement — '$DESC'"
                ;;
            structural)
                if [[ -z "$DESC" ]]; then
                    echo "ERROR: --description required for structural tier" >&2
                    exit 1
                fi
                json_update "{\"active\": True, \"needs_classification\": False, \"tier\": \"structural\", \"plan_description\": \"$DESC\", \"retrospective_completed\": False, \"plan_stage_review_completed\": False, \"total_phases\": $PHASES, \"phases_reviewed_count\": 0, \"observation_captured\": False, \"artifacts_verified\": []}"
                echo "DCP: classified as structural ($PHASES phase(s)) — '$DESC'"
                ;;
            *)
                echo "ERROR: tier must be mechanical, enhancement, or structural" >&2
                exit 1
                ;;
        esac
        ;;

    phase-reviewed)
        python3 -c "
import json
with open('$SESSION_FILE') as f:
    data = json.load(f)
dc = data.setdefault('directional_change', {})
count = dc.get('phases_reviewed_count', 0) + 1
dc['phases_reviewed_count'] = count
total = dc.get('total_phases', 0)
with open('$SESSION_FILE', 'w') as f:
    json.dump(data, f, indent=2)
    f.write('\n')
print(f'DCP: phase review {count}/{total}')
"
        ;;

    plan-reviewed)
        json_update '{"plan_stage_review_completed": True}'
        echo "DCP: plan-stage review marked complete"
        ;;

    artifacts-verified)
        ARTIFACTS=""
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --artifacts) ARTIFACTS="$2"; shift 2 ;;
                *) echo "Unknown option: $1" >&2; exit 1 ;;
            esac
        done
        if [[ -z "$ARTIFACTS" ]]; then
            echo "ERROR: --artifacts required" >&2
            exit 1
        fi
        # Convert space-separated to Python list
        PYLIST=$(python3 -c "import sys; print([a for a in '$ARTIFACTS'.split()])")
        json_update "{\"artifacts_verified\": $PYLIST}"
        echo "DCP: artifacts verified — $ARTIFACTS"
        ;;

    observation-captured)
        json_update '{"observation_captured": True}'
        echo "DCP: observation marked as captured"
        ;;

    retrospective-done)
        json_update '{"retrospective_completed": True}'
        echo "DCP: retrospective marked complete"
        ;;

    complete)
        json_update '{"active": False}'
        echo "DCP: completed (active=false)"
        ;;

    status)
        echo "DCP state:"
        json_read
        ;;

    *)
        echo "Unknown command: $COMMAND" >&2
        usage
        ;;
esac
