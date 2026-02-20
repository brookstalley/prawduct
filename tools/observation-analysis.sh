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
# Options:
#   --product-dir DIR  Resolve product root from DIR instead of CWD.
#                      Use when a subagent's CWD differs from the target product.
#
# Output: Human-readable summary to stdout.

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

MODE="${1:---full}"

# Resolve product root (shared detection logic)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/resolve-product-root.sh" ${_PRODUCT_DIR_OVERRIDE:+--product-dir "$_PRODUCT_DIR_OVERRIDE"}
OBS_DIR="$PRODUCT_ROOT/framework-observations"

if [[ ! -d "$OBS_DIR" ]]; then
    echo "Error: framework-observations directory not found at $OBS_DIR"
    exit 1
fi

obs_files=("$OBS_DIR"/*.yaml)
# Filter out schema.yaml (archive/ is excluded by the non-recursive glob)
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

# --- By observation type (active observations only for threshold detection) ---
echo "By Observation Type"
echo "-------------------"
# Dynamic: extract observation types from data
obs_types=$(grep -h "  - type:" "${obs_files_filtered[@]}" 2>/dev/null | sed 's/.*type: //' | sort -u)

active_counts=$(python3 -c "
import sys, os
sys.path.insert(0, '$SCRIPT_DIR')
import obs_utils

files = [$(printf '"%s",' "${obs_files_filtered[@]}")]
all_obs = obs_utils.parse_observations(files)
active_groups = obs_utils.group_by_type(all_obs, active_only=True)
all_groups = obs_utils.group_by_type(all_obs, active_only=False)

for otype in sorted(set(list(all_groups.keys()) + list(active_groups.keys()))):
    total = len(all_groups.get(otype, []))
    active = len(active_groups.get(otype, []))
    if total > 0:
        threshold = obs_utils.get_threshold(otype)
        tier = obs_utils.get_tier(otype)
        if active >= threshold:
            label = f'PATTERN DETECTED ({tier})'
        elif active >= 2:
            label = 'requires_pattern'
        else:
            label = 'noted'
        if active == total:
            print(f'  {otype}: {total} ({label})')
        else:
            print(f'  {otype}: {active} active of {total} total ({label})')
" 2>/dev/null)

if [[ -n "$active_counts" ]]; then
    echo "$active_counts"
else
    for otype in $obs_types; do
        count=$(count_matches "type: $otype" "${obs_files_filtered[@]}")
        if [[ "$count" -gt 0 ]]; then
            echo "  $otype: $count (status filtering unavailable)"
        fi
    done
fi
echo ""

# --- By affected skill (active observations only) ---
echo "By Affected Skill"
echo "------------------"
skill_counts=$(python3 -c "
import sys, os
sys.path.insert(0, '$SCRIPT_DIR')
import obs_utils
from collections import Counter

files = [$(printf '"%s",' "${obs_files_filtered[@]}")]
all_obs = obs_utils.parse_observations(files)
active_obs = [o for o in all_obs if obs_utils.is_active(o)]

skill_counter = Counter()
for obs in active_obs:
    for skill in obs.get('_skills', []):
        skill_counter[skill] += 1

for skill, count in skill_counter.most_common():
    label = 'PATTERN DETECTED' if count >= 4 else ('requires_pattern' if count >= 2 else 'noted')
    print(f'  {count}  {skill} ({label})')
" 2>/dev/null)

if [[ -n "$skill_counts" ]]; then
    echo "$skill_counts"
else
    # Fallback: grep-based counting (includes all statuses)
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
            echo "  $count  $skill_clean ($threshold) [status filtering unavailable]"
        done
fi
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
for status in noted triaged requires_pattern acted_on archived; do
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

    pattern_data=$(python3 -c "
import sys, os
sys.path.insert(0, '$SCRIPT_DIR')
import obs_utils

files = [$(printf '"%s",' "${obs_files_filtered[@]}")]
all_obs = obs_utils.parse_observations(files)
active_groups = obs_utils.group_by_type(all_obs, active_only=True)

for otype in sorted(active_groups.keys()):
    observations = active_groups[otype]
    threshold = obs_utils.get_threshold(otype)
    if len(observations) >= threshold:
        tier = obs_utils.get_tier(otype)
        print(f'PATTERN:{otype}:{len(observations)}:{tier}:{threshold}')
        for obs in observations[:10]:
            desc = obs.get('description', '')
            if desc:
                print(f'DESC:{desc}')
        print('END')
" 2>/dev/null)

    if [[ -n "$pattern_data" ]]; then
        while IFS= read -r line; do
            if [[ "$line" == PATTERN:* ]]; then
                IFS=':' read -r _ otype count tier threshold <<< "$line"
                found_pattern=true
                echo "--- $otype ($count active occurrences, $tier threshold: ${threshold}+) ---"
            elif [[ "$line" == DESC:* ]]; then
                echo "  ${line#DESC:}"
            elif [[ "$line" == "END" ]]; then
                echo ""
            fi
        done <<< "$pattern_data"
    else
        # Fallback: use grep-based counting (includes all statuses)
        for otype in process_friction rubric_issue; do
            count=$(count_matches "type: $otype" "${obs_files_filtered[@]}")
            if [[ "$count" -ge 2 ]]; then
                found_pattern=true
                echo "--- $otype ($count occurrences, meta threshold: 2+) [status filtering unavailable] ---"
                grep -B1 -A3 "type: $otype" "${obs_files_filtered[@]}" 2>/dev/null | \
                    grep "description:" | sed 's/.*description: /  /' | head -10
                echo ""
            fi
        done
        for otype in artifact_insufficiency spec_ambiguity deployment_friction critic_gap; do
            count=$(count_matches "type: $otype" "${obs_files_filtered[@]}")
            if [[ "$count" -ge 3 ]]; then
                found_pattern=true
                echo "--- $otype ($count occurrences, build threshold: 3+) [status filtering unavailable] ---"
                grep -B1 -A3 "type: $otype" "${obs_files_filtered[@]}" 2>/dev/null | \
                    grep "description:" | sed 's/.*description: /  /' | head -10
                echo ""
            fi
        done
        for otype in proportionality coverage applicability missing_guidance; do
            count=$(count_matches "type: $otype" "${obs_files_filtered[@]}")
            if [[ "$count" -ge 4 ]]; then
                found_pattern=true
                echo "--- $otype ($count occurrences, product threshold: 4+) [status filtering unavailable] ---"
                grep -B1 -A3 "type: $otype" "${obs_files_filtered[@]}" 2>/dev/null | \
                    grep "description:" | sed 's/.*description: /  /' | head -10
                echo ""
            fi
        done
    fi

    if [[ "$found_pattern" == false ]]; then
        echo "  No patterns detected yet (all active types below their tier threshold)."
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
for dir in ../*/working-notes . working-notes .prawduct/working-notes ../*/.prawduct/working-notes; do
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
