#!/usr/bin/env bash
#
# observation-analysis.sh — Parse framework observations and detect patterns
#
# Purpose: Partially closes the learning loop by analyzing accumulated
# observations in framework-observations/*.yaml. Groups by type and
# affected skills, applies pattern detection thresholds, and produces
# a summary report.
#
# Tiered thresholds (from framework-observations/README.md):
#   Meta (process_friction, rubric_issue):           2+ = pattern detected
#   Build-phase (artifact_insufficiency, etc.):      3+ = pattern detected
#   Product behavior (coverage, proportionality...): 4+ = pattern detected
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
obs_types=$(grep -h "  - type:" "${obs_files_filtered[@]}" 2>/dev/null | sed 's/.*type: //' | sort -u)
for otype in $obs_types; do
    count=$(count_matches "type: $otype" "${obs_files_filtered[@]}")
    if [[ "$count" -gt 0 ]]; then
        # Tiered thresholds: meta/process types act faster
        case "$otype" in
            process_friction|rubric_issue)
                # Meta observations — act at 2+
                if [[ "$count" -ge 2 ]]; then
                    threshold="PATTERN DETECTED (meta)"
                else
                    threshold="noted"
                fi
                ;;
            artifact_insufficiency|spec_ambiguity|deployment_friction|critic_gap)
                # Build-phase observations — act at 3+
                if [[ "$count" -ge 3 ]]; then
                    threshold="PATTERN DETECTED (build)"
                elif [[ "$count" -ge 2 ]]; then
                    threshold="requires_pattern"
                else
                    threshold="noted"
                fi
                ;;
            *)
                # Product behavior observations — act at 4+
                if [[ "$count" -ge 4 ]]; then
                    threshold="PATTERN DETECTED"
                elif [[ "$count" -ge 2 ]]; then
                    threshold="requires_pattern"
                else
                    threshold="noted"
                fi
                ;;
        esac
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
for status in noted triaged requires_pattern acted_on; do
    count=$(count_matches "status: $status" "${obs_files_filtered[@]}")
    if [[ "$count" -gt 0 ]]; then
        echo "  $status: $count"
    fi
done
echo ""

# --- Patterns (2+ occurrences) ---
if [[ "$MODE" == "--patterns-only" || "$MODE" == "--full" ]]; then
    echo "=========================================="
    echo " Patterns Requiring Review (tiered thresholds)"
    echo "=========================================="
    echo ""

    found_pattern=false

    # Meta observations (threshold: 2+)
    for otype in process_friction rubric_issue; do
        count=$(count_matches "type: $otype" "${obs_files_filtered[@]}")
        if [[ "$count" -ge 2 ]]; then
            found_pattern=true
            echo "--- $otype ($count occurrences, meta threshold: 2+) ---"
            grep -B1 -A3 "type: $otype" "${obs_files_filtered[@]}" 2>/dev/null | \
                grep "description:" | \
                sed 's/.*description: /  /' | \
                head -10
            echo ""
        fi
    done

    # Build-phase observations (threshold: 3+)
    for otype in artifact_insufficiency spec_ambiguity deployment_friction critic_gap; do
        count=$(count_matches "type: $otype" "${obs_files_filtered[@]}")
        if [[ "$count" -ge 3 ]]; then
            found_pattern=true
            echo "--- $otype ($count occurrences, build threshold: 3+) ---"
            grep -B1 -A3 "type: $otype" "${obs_files_filtered[@]}" 2>/dev/null | \
                grep "description:" | \
                sed 's/.*description: /  /' | \
                head -10
            echo ""
        fi
    done

    # Product behavior observations (threshold: 4+)
    for otype in proportionality coverage applicability missing_guidance; do
        count=$(count_matches "type: $otype" "${obs_files_filtered[@]}")
        if [[ "$count" -ge 4 ]]; then
            found_pattern=true
            echo "--- $otype ($count occurrences, product threshold: 4+) ---"
            grep -B1 -A3 "type: $otype" "${obs_files_filtered[@]}" 2>/dev/null | \
                grep "description:" | \
                sed 's/.*description: /  /' | \
                head -10
            echo ""
        fi
    done

    if [[ "$found_pattern" == false ]]; then
        echo "  No patterns detected yet (all types below their tier threshold)."
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
shopt -s nullglob
for dir in ../*/working-notes . working-notes; do
    if [[ -d "$dir" ]]; then
        for f in "$dir"/framework-observations-*.yaml; do
            if [[ -f "$f" ]]; then
                fallback_files+=("$f")
            fi
        done
    fi
done
shopt -u nullglob

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
