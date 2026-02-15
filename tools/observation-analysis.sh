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

MODE="${1:---full}"

# Detect observation directory: .prawduct/ first, then repo root
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -n "$REPO_ROOT" && -d "$REPO_ROOT/.prawduct/framework-observations" ]]; then
    OBS_DIR="$REPO_ROOT/.prawduct/framework-observations"
elif [[ -d "framework-observations" ]]; then
    OBS_DIR="framework-observations"
elif [[ -n "$REPO_ROOT" && -d "$REPO_ROOT/framework-observations" ]]; then
    OBS_DIR="$REPO_ROOT/framework-observations"
else
    echo "Error: framework-observations directory not found."
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

# Count active (non-terminal) observations per type using Python for accurate
# per-observation status filtering. Terminal statuses (acted_on, archived) are
# excluded from threshold counts to prevent already-fixed patterns from re-triggering.
active_counts=$(python3 -c "
import yaml, os, sys

files = [$(printf '"%s",' "${obs_files_filtered[@]}")]
active_by_type = {}
total_by_type = {}

for f in files:
    if not os.path.isfile(f):
        continue
    try:
        with open(f) as fh:
            for doc in yaml.safe_load_all(fh):
                if not doc or 'observations' not in doc:
                    continue
                for obs in doc.get('observations', []):
                    otype = obs.get('type', 'unknown')
                    status = obs.get('status', 'noted')
                    total_by_type[otype] = total_by_type.get(otype, 0) + 1
                    if status not in ('acted_on', 'archived'):
                        active_by_type[otype] = active_by_type.get(otype, 0) + 1
    except:
        continue

for otype in sorted(set(list(total_by_type.keys()) + list(active_by_type.keys()))):
    total = total_by_type.get(otype, 0)
    active = active_by_type.get(otype, 0)
    print(f'{otype} {active} {total}')
" 2>/dev/null)

if [[ -n "$active_counts" ]]; then
    while read -r otype active_count total_count; do
        if [[ "$total_count" -gt 0 ]]; then
            # Tiered thresholds applied to ACTIVE observations only
            case "$otype" in
                process_friction|rubric_issue|skill_quality|external_practice_drift|documentation_drift|structural_critique)
                    # Meta observations — act at 2+
                    if [[ "$active_count" -ge 2 ]]; then
                        threshold="PATTERN DETECTED (meta)"
                    else
                        threshold="noted"
                    fi
                    ;;
                artifact_insufficiency|spec_ambiguity|deployment_friction|critic_gap)
                    # Build-phase observations — act at 3+
                    if [[ "$active_count" -ge 3 ]]; then
                        threshold="PATTERN DETECTED (build)"
                    elif [[ "$active_count" -ge 2 ]]; then
                        threshold="requires_pattern"
                    else
                        threshold="noted"
                    fi
                    ;;
                *)
                    # Product behavior observations — act at 4+
                    if [[ "$active_count" -ge 4 ]]; then
                        threshold="PATTERN DETECTED"
                    elif [[ "$active_count" -ge 2 ]]; then
                        threshold="requires_pattern"
                    else
                        threshold="noted"
                    fi
                    ;;
            esac
            if [[ "$active_count" -eq "$total_count" ]]; then
                echo "  $otype: $total_count ($threshold)"
            else
                echo "  $otype: $active_count active of $total_count total ($threshold)"
            fi
        fi
    done <<< "$active_counts"
else
    # Fallback: simple grep counts if python3/yaml unavailable
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
# Count skills affected by active (non-terminal) observations only
skill_counts=$(python3 -c "
import yaml, os

files = [$(printf '"%s",' "${obs_files_filtered[@]}")]
skill_counts = {}

for f in files:
    if not os.path.isfile(f):
        continue
    try:
        with open(f) as fh:
            for doc in yaml.safe_load_all(fh):
                if not doc or 'observations' not in doc:
                    continue
                skills = doc.get('skills_affected', [])
                has_active = any(
                    obs.get('status', 'noted') not in ('acted_on', 'archived')
                    for obs in doc.get('observations', [])
                )
                if has_active:
                    for skill in skills:
                        skill_counts[skill] = skill_counts.get(skill, 0) + 1
    except:
        continue

for skill, count in sorted(skill_counts.items(), key=lambda x: -x[1]):
    threshold = 'noted'
    if count >= 4:
        threshold = 'PATTERN DETECTED'
    elif count >= 2:
        threshold = 'requires_pattern'
    print(f'  {count}  {skill} ({threshold})')
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

    # Use Python to count only active (non-terminal) observations per type
    # This prevents acted_on/archived observations from inflating pattern counts
    pattern_data=$(python3 -c "
import yaml, os, sys

META_TYPES = {'process_friction', 'rubric_issue', 'skill_quality', 'external_practice_drift', 'documentation_drift', 'structural_critique'}
BUILD_TYPES = {'artifact_insufficiency', 'spec_ambiguity', 'deployment_friction', 'critic_gap'}

files = [$(printf '"%s",' "${obs_files_filtered[@]}")]
active_by_type = {}
descriptions_by_type = {}

for f in files:
    if not os.path.isfile(f):
        continue
    try:
        with open(f) as fh:
            for doc in yaml.safe_load_all(fh):
                if not doc or 'observations' not in doc:
                    continue
                for obs in doc.get('observations', []):
                    otype = obs.get('type', 'unknown')
                    status = obs.get('status', 'noted')
                    if status not in ('acted_on', 'archived'):
                        active_by_type[otype] = active_by_type.get(otype, 0) + 1
                        desc = obs.get('description', '')
                        if desc:
                            descriptions_by_type.setdefault(otype, []).append(desc)
    except:
        continue

def get_threshold(t):
    if t in META_TYPES: return 2
    if t in BUILD_TYPES: return 3
    return 4

def get_tier(t):
    if t in META_TYPES: return 'meta'
    if t in BUILD_TYPES: return 'build'
    return 'product'

for otype in sorted(active_by_type.keys()):
    count = active_by_type[otype]
    threshold = get_threshold(otype)
    if count >= threshold:
        tier = get_tier(otype)
        print(f'PATTERN:{otype}:{count}:{tier}:{threshold}')
        for desc in descriptions_by_type.get(otype, [])[:10]:
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
