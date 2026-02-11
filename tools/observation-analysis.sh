#!/usr/bin/env bash
#
# observation-analysis.sh — Parse framework observations and detect patterns
#
# Purpose: Partially closes the learning loop by analyzing accumulated
# observations in framework-observations/*.yaml. Groups by type and
# affected skills, applies pattern detection thresholds, and produces
# a summary report.
#
# Thresholds (from framework-observations/README.md):
#   1 occurrence  = noted (watch for recurrence)
#   2-3           = requires_pattern (flag for review)
#   4+            = pattern detected (propose skill update)
#
# Usage:
#   ./tools/observation-analysis.sh                    # Full report
#   ./tools/observation-analysis.sh --by-skill         # Group by affected skill
#   ./tools/observation-analysis.sh --by-type          # Group by observation type
#   ./tools/observation-analysis.sh --patterns-only    # Only show 2+ occurrences
#   ./tools/observation-analysis.sh --blocking         # Only show blocking severity
#
# Output: Human-readable summary to stdout.

set -uo pipefail

OBS_DIR="framework-observations"
MODE="${1:---full}"

if [[ ! -d "$OBS_DIR" ]]; then
    echo "Error: $OBS_DIR directory not found. Run from prawduct root."
    exit 1
fi

obs_files=("$OBS_DIR"/*.yaml)
# Filter out schema.yaml
obs_files_filtered=()
for f in "${obs_files[@]}"; do
    basename=$(basename "$f")
    if [[ "$basename" != "schema.yaml" ]]; then
        obs_files_filtered+=("$f")
    fi
done

if [[ ${#obs_files_filtered[@]} -eq 0 ]]; then
    echo "No observation files found in $OBS_DIR/"
    exit 0
fi

echo "=========================================="
echo " Framework Observation Analysis"
echo " $(date +%Y-%m-%d)"
echo "=========================================="
echo ""

# Helper: sum grep -ch output across multiple files
count_matches() {
    local pattern="$1"
    shift
    grep -ch "$pattern" "$@" 2>/dev/null | awk '{s+=$1} END {print s+0}'
}

# --- Basic counts ---
total_files=${#obs_files_filtered[@]}
total_observations=$(count_matches "^  - type:" "${obs_files_filtered[@]}")
total_blocking=$(count_matches "severity: blocking" "${obs_files_filtered[@]}")
total_warning=$(count_matches "severity: warning" "${obs_files_filtered[@]}")
total_note=$(count_matches "severity: note" "${obs_files_filtered[@]}")

echo "Overview"
echo "--------"
echo "  Observation files: $total_files"
echo "  Total observations: $total_observations"
echo "  By severity: blocking=$total_blocking, warning=$total_warning, note=$total_note"
echo ""

# --- Session types ---
echo "By Session Type"
echo "---------------"
# Dynamic: extract session types from data
session_types=$(grep -h "session_type:" "${obs_files_filtered[@]}" 2>/dev/null | sed 's/.*session_type: //' | sort -u)
for stype in $session_types; do
    count=$(grep -l "session_type: $stype" "${obs_files_filtered[@]}" 2>/dev/null | wc -l | tr -d ' ' || echo 0)
    echo "  $stype: $count files"
done
echo ""

# --- By observation type ---
echo "By Observation Type"
echo "-------------------"
# Dynamic: extract observation types from data
obs_types=$(grep -h "    type:" "${obs_files_filtered[@]}" 2>/dev/null | sed 's/.*type: //' | sort -u)
for otype in $obs_types; do
    count=$(count_matches "type: $otype" "${obs_files_filtered[@]}")
    if [[ "$count" -gt 0 ]]; then
        threshold="noted"
        if [[ "$count" -ge 4 ]]; then
            threshold="PATTERN DETECTED"
        elif [[ "$count" -ge 2 ]]; then
            threshold="requires_pattern"
        fi
        echo "  $otype: $count ($threshold)"
    fi
done
echo ""

# --- By affected skill ---
echo "By Affected Skill"
echo "------------------"
# Extract all skills_affected entries and count
grep -h "skills_affected" -A 20 "${obs_files_filtered[@]}" 2>/dev/null | \
    grep -o '"[^"]*"' | \
    sort | uniq -c | sort -rn | \
    while read -r count skill; do
        skill_clean=$(echo "$skill" | tr -d '"')
        threshold="noted"
        if [[ "$count" -ge 4 ]]; then
            threshold="PATTERN DETECTED"
        elif [[ "$count" -ge 2 ]]; then
            threshold="requires_pattern"
        fi
        echo "  $count  $skill_clean ($threshold)"
    done
echo ""

# --- By stage ---
echo "By Stage"
echo "--------"
for stage in 0 0.5 1 2 3 meta; do
    # Match both quoted and unquoted stage values
    count=$(count_matches "stage: [\"]*${stage}[\"]*$" "${obs_files_filtered[@]}")
    if [[ "$count" -gt 0 ]]; then
        echo "  Stage $stage: $count observations"
    fi
done
echo ""

# --- Status tracking ---
echo "By Status"
echo "---------"
for status in noted requires_pattern acted_on; do
    count=$(count_matches "status: $status" "${obs_files_filtered[@]}")
    if [[ "$count" -gt 0 ]]; then
        echo "  $status: $count"
    fi
done
echo ""

# --- Patterns (2+ occurrences) ---
if [[ "$MODE" == "--patterns-only" || "$MODE" == "--full" ]]; then
    echo "=========================================="
    echo " Patterns Requiring Review (2+ occurrences)"
    echo "=========================================="
    echo ""

    found_pattern=false

    for otype in proportionality coverage applicability missing_guidance rubric_issue process_friction; do
        count=$(count_matches "type: $otype" "${obs_files_filtered[@]}")
        if [[ "$count" -ge 2 ]]; then
            found_pattern=true
            echo "--- $otype ($count occurrences) ---"
            # Show descriptions for this type
            grep -B1 -A3 "type: $otype" "${obs_files_filtered[@]}" 2>/dev/null | \
                grep "description:" | \
                sed 's/.*description: /  /' | \
                head -10
            echo ""
        fi
    done

    if [[ "$found_pattern" == false ]]; then
        echo "  No patterns detected yet (all types have <2 occurrences)."
        echo ""
    fi
fi

# --- Blocking items ---
if [[ "$MODE" == "--blocking" || "$MODE" == "--full" ]]; then
    if [[ "$total_blocking" -gt 0 ]]; then
        echo "=========================================="
        echo " Blocking Observations"
        echo "=========================================="
        echo ""
        grep -B2 -A5 "severity: blocking" "${obs_files_filtered[@]}" 2>/dev/null | \
            grep -E "(description:|evidence:|proposed_action:|--)" | \
            sed 's/.*description: /  DESC: /' | \
            sed 's/.*evidence: /  EVID: /' | \
            sed 's/.*proposed_action: /  ACTION: /'
        echo ""
    fi
fi

# --- Unacted observations ---
unacted=$(count_matches "status: noted" "${obs_files_filtered[@]}")
if [[ "$unacted" -gt 0 ]]; then
    echo "=========================================="
    echo " $unacted observations with status: noted"
    echo " (not yet acted on or promoted to pattern)"
    echo "=========================================="
fi

# --- Check for fallback observation files in known project directories ---
# When the framework repo isn't writable during product sessions, observations
# are written to the project's working-notes/framework-observations-*.yaml.
# Alert if any exist so they can be transferred.
fallback_files=()
for dir in ../*/working-notes . working-notes; do
    if [[ -d "$dir" ]]; then
        for f in "$dir"/framework-observations-*.yaml 2>/dev/null; do
            if [[ -f "$f" ]]; then
                fallback_files+=("$f")
            fi
        done
    fi
done

if [[ ${#fallback_files[@]} -gt 0 ]]; then
    echo ""
    echo "=========================================="
    echo " WARNING: ${#fallback_files[@]} fallback observation file(s) found"
    echo " These were written outside the framework repo and should be transferred."
    echo "=========================================="
    for f in "${fallback_files[@]}"; do
        echo "  $f"
    done
fi
