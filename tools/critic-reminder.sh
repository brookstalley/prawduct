#!/usr/bin/env bash
#
# critic-reminder.sh — Mechanical check: was the Critic run before committing?
#
# Purpose: Enforces the governance philosophy "The Critic Is Not Optional"
# by checking whether framework-modifying commits include evidence of
# Critic review. Exits 2 when framework files are modified without
# evidence of Critic review — this blocks both git hooks and Claude Code hooks.
#
# Usage:
#   ./tools/critic-reminder.sh              # Check staged changes
#   ./tools/critic-reminder.sh --last       # Check most recent commit
#
# What it checks:
#   1. Are any skill, template, principle, or design docs being modified?
#   2. If so, does the commit message or recent git log mention "Critic" or
#      "Framework Governance"?
#
# Exit codes:
#   0 — No framework files modified, or Critic evidence found
#   2 — Framework files modified but no Critic evidence found (DENY)
#
# Exit code 2 is used because:
#   - Claude Code hooks treat exit 2 as "deny" (blocks the tool call)
#   - Git pre-commit hooks treat any non-zero as "reject"
#   - So exit 2 works correctly in both contexts

set -euo pipefail

FRAMEWORK_PATTERNS=(
    "CLAUDE.md"
    "skills/"
    "templates/"
    "docs/"
    "scripts/"
    "framework-observations/README.md"
    "framework-observations/schema.yaml"
)

check_mode="${1:-staged}"

# Determine which files changed
if [[ "$check_mode" == "--last" ]]; then
    changed_files=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || echo "")
    commit_msg=$(git log -1 --pretty=%B 2>/dev/null || echo "")
else
    changed_files=$(git diff --cached --name-only 2>/dev/null || echo "")
    commit_msg=""
fi

if [[ -z "$changed_files" ]]; then
    echo "No changed files detected."
    exit 0
fi

# Check if any framework files are modified
framework_modified=false
modified_framework_files=()

for file in $changed_files; do
    for pattern in "${FRAMEWORK_PATTERNS[@]}"; do
        if [[ "$file" == $pattern* ]]; then
            framework_modified=true
            modified_framework_files+=("$file")
            break
        fi
    done
done

if [[ "$framework_modified" == false ]]; then
    echo "No framework files modified. Critic review not required."
    exit 0
fi

echo "Framework files modified:"
for f in "${modified_framework_files[@]}"; do
    echo "  - $f"
done
echo ""

# --- Check for structured Critic findings (primary path) ---

repo_root=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
critic_evidence=false
findings_file=""

if [[ -n "$repo_root" ]]; then
    findings_file="$repo_root/.claude/.critic-findings.json"
fi

if [[ -n "$findings_file" && -f "$findings_file" ]]; then
    # Check 1: Was the findings file modified within the last 2 hours?
    if [[ "$(uname)" == "Darwin" ]]; then
        file_age_seconds=$(( $(date +%s) - $(stat -f %m "$findings_file") ))
    else
        file_age_seconds=$(( $(date +%s) - $(stat -c %Y "$findings_file") ))
    fi
    max_age_seconds=$((2 * 60 * 60))  # 2 hours

    if [[ "$file_age_seconds" -le "$max_age_seconds" ]]; then
        # Check 2: Does it contain all 7 checks?
        check_count=$(python3 -c "
import json, sys
try:
    with open('$findings_file') as f:
        data = json.load(f)
    print(data.get('total_checks', 0))
except:
    print(0)
" 2>/dev/null || echo "0")

        if [[ "$check_count" -eq 7 ]]; then
            # Check 3: Do reviewed_files cover all staged framework files?
            reviewed_files=$(python3 -c "
import json
try:
    with open('$findings_file') as f:
        data = json.load(f)
    for f in data.get('reviewed_files', []):
        print(f)
except:
    pass
" 2>/dev/null || echo "")

            all_covered=true
            for f in "${modified_framework_files[@]}"; do
                if ! echo "$reviewed_files" | grep -qF "$f"; then
                    all_covered=false
                    echo "WARNING: Staged file '$f' not in Critic reviewed_files list."
                fi
            done

            if [[ "$all_covered" == true ]]; then
                critic_evidence=true
                echo "Structured Critic findings verified: all 7 checks present, all staged files reviewed."
            else
                echo "WARNING: Critic findings exist but don't cover all staged framework files."
                echo "Re-run the Critic with all files, or add missing files to the review."
            fi
        else
            echo "WARNING: Critic findings file has $check_count/7 checks. All 7 required."
        fi
    else
        echo "WARNING: Critic findings are stale (older than 2 hours). Re-run the Critic."
    fi
fi

# --- Fallback: keyword in commit message + observation file (deprecated, backward compatible) ---

if [[ "$critic_evidence" == false ]]; then
    keyword_found=false
    obs_found=false

    if [[ -n "$commit_msg" ]]; then
        if echo "$commit_msg" | grep -qi -e "critic" -e "framework governance" -e "governance review"; then
            keyword_found=true
        fi
    fi

    today=$(date +%Y-%m-%d)
    if ls framework-observations/"${today}"*.yaml >/dev/null 2>&1; then
        for obs_file in framework-observations/"${today}"*.yaml; do
            if grep -q "session_type: framework_dev" "$obs_file" 2>/dev/null; then
                obs_found=true
                break
            fi
        done
    fi

    if [[ "$keyword_found" == true && "$obs_found" == true ]]; then
        critic_evidence=true
        echo "Critic evidence found via fallback (keyword + observation file)."
        echo "NOTE: This fallback path is deprecated. Use tools/record-critic-findings.sh for structured evidence."
    elif [[ "$keyword_found" == true ]]; then
        critic_evidence=true
        echo "Critic evidence found via commit message keyword."
        echo "NOTE: This fallback path is deprecated. Use tools/record-critic-findings.sh for structured evidence."
    fi
fi

# --- Result ---

if [[ "$critic_evidence" == true ]]; then
    # Clean up pending flags
    if [[ -n "$repo_root" ]]; then
        rm -f "$repo_root/.claude/.critic-pending"
    fi
    exit 0
else
    echo ""
    echo "BLOCKED: Framework files were modified but no Critic review evidence found."
    echo ""
    echo "To unblock, run the Critic and record findings:"
    echo "  1. Read skills/critic/SKILL.md and apply Framework Governance mode (all 7 checks)"
    echo "  2. Run: tools/record-critic-findings.sh --files 'file1,file2' --check 'Name:sev:summary' (x7)"
    echo "  3. Include 'Framework Governance Review' in commit message"
    echo ""
    echo "The commit gate verifies:"
    echo "  - .claude/.critic-findings.json exists and is < 2 hours old"
    echo "  - All 7 Critic checks are recorded"
    echo "  - All staged framework files appear in reviewed_files"
    exit 2
fi
