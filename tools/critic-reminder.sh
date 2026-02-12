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

# Check for Critic evidence in commit message or recent log
critic_evidence=false

if [[ -n "$commit_msg" ]]; then
    if echo "$commit_msg" | grep -qi -e "critic" -e "framework governance" -e "governance review"; then
        critic_evidence=true
    fi
fi

# Also check recent observation files for framework_dev type with today's date
today=$(date +%Y-%m-%d)
if ls framework-observations/"${today}"*.yaml >/dev/null 2>&1; then
    for obs_file in framework-observations/"${today}"*.yaml; do
        if grep -q "session_type: framework_dev" "$obs_file" 2>/dev/null; then
            critic_evidence=true
            break
        fi
    done
fi

if [[ "$critic_evidence" == true ]]; then
    echo "Critic evidence found. Governance review appears complete."
    # Clean up the pending flag set by framework-edit-tracker.sh
    repo_root=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
    if [[ -n "$repo_root" ]]; then
        rm -f "$repo_root/.claude/.critic-pending"
    fi
    exit 0
else
    echo "WARNING: Framework files were modified but no Critic review evidence found."
    echo ""
    echo "The governance philosophy states: 'The Critic Is Not Optional.'"
    echo "Before committing, run Framework Governance mode:"
    echo "  1. Read skills/critic/SKILL.md"
    echo "  2. Apply all checks to your changes"
    echo "  3. Include 'Framework Governance Review' in commit message"
    echo ""
    echo "If you've already run the Critic, mention it in your commit message"
    echo "or create an observation file (framework-observations/{date}-*.yaml)."
    exit 2
fi
