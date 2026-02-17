#!/usr/bin/env bash
#
# record-critic-findings.sh — Record structured Critic findings for the commit gate
#
# Purpose: Makes Critic evidence recording a structured, verifiable operation.
# The commit gate checks .prawduct/.critic-findings.json for structured findings
# rather than relying on keyword matching in commit messages.
#
# Merge behavior: When called multiple times in a session, findings ACCUMULATE
# rather than overwriting. Files are unioned, checks are merged (latest wins
# per check name). The SessionStart hook clears findings on /clear or startup.
# This prevents the "second review erases first" problem in multi-change sessions.
#
# The Critic applies context-dependent checks — not every check applies to every
# review. The required minimum is 4 checks (the always-applicable checks 3-6), but
# build-stage reviews include checks 1-2 and skill file reviews add checks 7-9.
#
# Usage:
#   tools/record-critic-findings.sh \
#     --files "skills/orchestrator/SKILL.md,skills/critic/SKILL.md" \
#     --check "Spec Compliance:not-applicable:No build-stage implementation to review" \
#     --check "Test Integrity:not-applicable:No build-stage tests to review" \
#     --check "Scope Discipline:pass:Changes stay within stated scope" \
#     --check "Proportionality:pass:Change weight appropriate" \
#     --check "Coherence:warning:Stage 6 examples slightly outdated" \
#     --check "Learning/Observability:pass:Observation paths complete" \
#     --check "Generality:pass:No enumerated concerns added" \
#     --check "Instruction Clarity:pass:Instructions are imperative" \
#     --check "Cumulative Health:pass:Skill length proportionate"
#
# Exit codes:
#   0 — Findings recorded to .prawduct/.critic-findings.json
#   1 — Validation failure (missing checks, invalid names/severities)

set -euo pipefail

# --- Known Critic checks (from skills/critic/SKILL.md) ---
# Checks 3-6 are always applicable; Checks 1-2 apply at build stages, Checks 7-9 apply when reviewing skill/template files.

ALL_VALID_CHECKS=(
    "Spec Compliance"
    "Test Integrity"
    "Scope Discipline"
    "Proportionality"
    "Coherence"
    "Learning/Observability"
    "Generality"
    "Instruction Clarity"
    "Cumulative Health"
)

# Minimum required: the 4 always-applicable checks
ALWAYS_APPLICABLE_CHECKS=(
    "Scope Discipline"
    "Proportionality"
    "Coherence"
    "Learning/Observability"
)

VALID_SEVERITIES="pass not-applicable note warning blocking"

# --- Parse arguments ---

FILES=""
declare -a CHECKS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --files)   FILES="$2"; shift 2 ;;
        --check)   CHECKS+=("$2"); shift 2 ;;
        --help|-h)
            echo "Usage: tools/record-critic-findings.sh --files FILE_LIST --check CHECK_ENTRY [--check ...]"
            echo ""
            echo "Required:"
            echo "  --files    Comma-separated list of all reviewed files"
            echo "  --check    One per Critic check, format: 'CheckName:severity:summary'"
            echo "             Must provide at least 4 checks (the always-applicable checks)"
            echo ""
            echo "Check names: ${ALL_VALID_CHECKS[*]}"
            echo "Severities: $VALID_SEVERITIES"
            echo ""
            echo "Example:"
            echo "  --check 'Scope Discipline:pass:Changes stay within stated scope'"
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

[[ -z "$FILES" ]] && errors+=("--files is required")

if [[ ${#CHECKS[@]} -lt 4 ]]; then
    errors+=("At least 4 --check entries required. Got ${#CHECKS[@]}.")
fi

# Parse and validate each check
declare -a PARSED_NAMES=()
declare -a PARSED_SEVERITIES=()
declare -a PARSED_SUMMARIES=()

for check_entry in "${CHECKS[@]}"; do
    # Split on first two colons: name:severity:summary (summary may contain colons)
    check_name=$(echo "$check_entry" | cut -d: -f1)
    check_sev=$(echo "$check_entry" | cut -d: -f2)
    check_summary=$(echo "$check_entry" | cut -d: -f3-)

    [[ -z "$check_name" ]] && errors+=("Check entry missing name: '$check_entry'")
    [[ -z "$check_sev" ]] && errors+=("Check entry missing severity: '$check_entry'")
    [[ -z "$check_summary" ]] && errors+=("Check entry missing summary: '$check_entry'")

    # Validate check name
    if [[ -n "$check_name" ]]; then
        name_valid=false
        for valid_name in "${ALL_VALID_CHECKS[@]}"; do
            if [[ "$check_name" == "$valid_name" ]]; then
                name_valid=true
                break
            fi
        done
        if [[ "$name_valid" == false ]]; then
            errors+=("Invalid check name: '$check_name'. Valid: ${ALL_VALID_CHECKS[*]}")
        fi
    fi

    # Validate severity
    if [[ -n "$check_sev" ]]; then
        sev_valid=false
        for valid_sev in $VALID_SEVERITIES; do
            if [[ "$check_sev" == "$valid_sev" ]]; then
                sev_valid=true
                break
            fi
        done
        if [[ "$sev_valid" == false ]]; then
            errors+=("Invalid severity '$check_sev' for check '$check_name'. Valid: $VALID_SEVERITIES")
        fi
    fi

    PARSED_NAMES+=("$check_name")
    PARSED_SEVERITIES+=("$check_sev")
    PARSED_SUMMARIES+=("$check_summary")
done

# Verify all always-applicable checks are present
for required in "${ALWAYS_APPLICABLE_CHECKS[@]}"; do
    found=false
    for provided in "${PARSED_NAMES[@]}"; do
        if [[ "$provided" == "$required" ]]; then
            found=true
            break
        fi
    done
    if [[ "$found" == false ]]; then
        errors+=("Missing required check: '$required' (always applicable)")
    fi
done

# Check for duplicates (bash 3 compatible)
for ((i=0; i<${#PARSED_NAMES[@]}; i++)); do
    for ((j=i+1; j<${#PARSED_NAMES[@]}; j++)); do
        if [[ "${PARSED_NAMES[$i]}" == "${PARSED_NAMES[$j]}" ]]; then
            errors+=("Duplicate check: '${PARSED_NAMES[$i]}'")
        fi
    done
done

# Report all errors at once
if [[ ${#errors[@]} -gt 0 ]]; then
    echo "Validation errors:" >&2
    for err in "${errors[@]}"; do
        echo "  - $err" >&2
    done
    exit 1
fi

# --- Generate output ---

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Determine output location
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -n "$REPO_ROOT" ]]; then
    OUTPUT_DIR="$REPO_ROOT/.prawduct"
else
    OUTPUT_DIR=".prawduct"
fi
mkdir -p "$OUTPUT_DIR"
OUTPUT_FILE="$OUTPUT_DIR/.critic-findings.json"

# Build JSON using python3 for reliable escaping
IFS=',' read -ra FILE_ARRAY <<< "$FILES"

# Build check args as newline-delimited triples
CHECK_ARGS=""
for i in "${!PARSED_NAMES[@]}"; do
    CHECK_ARGS+="${PARSED_NAMES[$i]}"$'\n'
    CHECK_ARGS+="${PARSED_SEVERITIES[$i]}"$'\n'
    CHECK_ARGS+="${PARSED_SUMMARIES[$i]}"$'\n'
done

python3 -c "
import json, sys, os

files = [f.strip() for f in sys.argv[1].split(',')]
timestamp = sys.argv[2]
git_sha = sys.argv[3]
output_file = sys.argv[4]

# Read check data from stdin (newline-delimited triples)
check_lines = sys.stdin.read().strip().split('\n')
checks = []
i = 0
while i + 2 < len(check_lines):
    checks.append({
        'name': check_lines[i],
        'severity': check_lines[i+1],
        'summary': check_lines[i+2]
    })
    i += 3

# Merge with existing findings if present (accumulate across multiple reviews
# in the same session). The SessionStart hook clears this file on /clear or
# startup, so cross-session contamination is not a concern.
existing_files = set()
existing_checks = {}  # name -> check dict (latest wins)
if os.path.exists(output_file):
    try:
        with open(output_file) as f:
            existing = json.load(f)
        existing_files = set(existing.get('reviewed_files', []))
        for c in existing.get('checks', []):
            existing_checks[c['name']] = c
    except (json.JSONDecodeError, KeyError):
        pass  # Corrupt file — start fresh

# Merge: union of files, latest checks win by name
merged_files = sorted(existing_files | set(files))
for c in checks:
    existing_checks[c['name']] = c
merged_checks = list(existing_checks.values())

# Determine highest severity (excluding not-applicable)
severity_order = {'not-applicable': -1, 'pass': 0, 'note': 1, 'warning': 2, 'blocking': 3}
applicable_checks = [c for c in merged_checks if c['severity'] != 'not-applicable']
if applicable_checks:
    max_sev = max(applicable_checks, key=lambda c: severity_order.get(c['severity'], 0))
    highest = max_sev['severity']
else:
    highest = 'pass'

output = {
    'timestamp': timestamp,
    'git_sha': git_sha,
    'reviewed_files': merged_files,
    'checks': merged_checks,
    'highest_severity': highest,
    'total_checks': len(merged_checks)
}

with open(output_file, 'w') as f:
    json.dump(output, f, indent=2)
    f.write('\n')
" "$FILES" "$TIMESTAMP" "$GIT_SHA" "$OUTPUT_FILE" <<< "$CHECK_ARGS"

echo "Critic findings recorded to: $OUTPUT_FILE"

# Print summary
echo ""
echo "Summary:"
echo "  Files reviewed: ${#FILE_ARRAY[@]}"
echo "  Checks: ${#CHECKS[@]}"
for i in "${!PARSED_NAMES[@]}"; do
    sev="${PARSED_SEVERITIES[$i]}"
    marker="✓"
    if [[ "$sev" == "warning" ]]; then marker="⚠"; fi
    if [[ "$sev" == "blocking" ]]; then marker="✗"; fi
    if [[ "$sev" == "note" ]]; then marker="·"; fi
    if [[ "$sev" == "not-applicable" ]]; then marker="—"; fi
    echo "  $marker ${PARSED_NAMES[$i]}: ${PARSED_SEVERITIES[$i]} — ${PARSED_SUMMARIES[$i]}"
done

exit 0
