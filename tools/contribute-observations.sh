#!/usr/bin/env bash
#
# contribute-observations.sh — Check, format, and submit product observations to the framework
#
# Non-interactive tool for the observation contribution pipeline. The Orchestrator
# handles human-in-the-loop review (privacy check, approval); this tool handles
# the mechanics.
#
# Modes:
#   --check <product-dir>              JSON summary for Orchestrator consumption
#   --format <product-dir> [files...]  Issue body markdown to stdout
#   --submit <product-dir> [files...]  Create GitHub issue via gh, mark files contributed
#
# Self-hosted repos (framework developing itself) always return count 0 — the
# framework's own observations are acted on directly, not contributed via issues.
#
# Exit codes:
#   0 — Success
#   1 — Error (missing args, invalid paths, YAML parse failure)
#   2 — gh CLI not available (--submit only)

set -uo pipefail

# --- Resolve framework directory from script location ---

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRAMEWORK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# --- Parse arguments ---

MODE=""
PRODUCT_DIR=""
SPECIFIC_FILES=()

usage() {
    echo "Usage:" >&2
    echo "  $(basename "$0") --check <product-dir>" >&2
    echo "  $(basename "$0") --format <product-dir> [file1.yaml ...]" >&2
    echo "  $(basename "$0") --submit <product-dir> [file1.yaml ...]" >&2
    exit 1
}

if [[ $# -lt 2 ]]; then
    if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
        echo "contribute-observations.sh — Check, format, and submit product observations"
        echo ""
        echo "Modes:"
        echo "  --check <product-dir>              JSON: uncontributed count and file list"
        echo "  --format <product-dir> [files...]  Markdown issue body to stdout"
        echo "  --submit <product-dir> [files...]  Create GitHub issue, mark files contributed"
        echo ""
        echo "Self-hosted repos return count 0 (observations acted on directly)."
        exit 0
    fi
    usage
fi

case "$1" in
    --check|--format|--submit)
        MODE="${1#--}"
        PRODUCT_DIR="$2"
        shift 2
        while [[ $# -gt 0 ]]; do
            SPECIFIC_FILES+=("$1")
            shift
        done
        ;;
    *)
        usage
        ;;
esac

# --- Validate product directory ---

if [[ ! -d "$PRODUCT_DIR" ]]; then
    echo "Error: Product directory not found: $PRODUCT_DIR" >&2
    exit 1
fi

# Resolve to absolute path
PRODUCT_DIR="$(cd "$PRODUCT_DIR" && pwd)"

OBS_DIR="$PRODUCT_DIR/.prawduct/framework-observations"
if [[ ! -d "$OBS_DIR" ]]; then
    # No observations directory — report zero
    if [[ "$MODE" == "check" ]]; then
        echo '{"uncontributed_count": 0, "files": [], "self_hosted": false, "reason": "no framework-observations directory"}'
        exit 0
    else
        echo "Error: No framework-observations directory at $OBS_DIR" >&2
        exit 1
    fi
fi

# --- Self-hosted detection ---
# Compare the resolved framework dir to the product dir's repo root.
# If they're the same, this is the framework developing itself.

is_self_hosted() {
    local product_repo_root
    product_repo_root=$(cd "$PRODUCT_DIR" && git rev-parse --show-toplevel 2>/dev/null || echo "")
    if [[ -n "$product_repo_root" && "$product_repo_root" == "$FRAMEWORK_DIR" ]]; then
        return 0
    fi
    # Also check if .prawduct/framework-path points to the same repo
    local fw_path_file="$PRODUCT_DIR/.prawduct/framework-path"
    if [[ -f "$fw_path_file" ]]; then
        local fw_path
        fw_path=$(cat "$fw_path_file")
        local fw_repo_root
        fw_repo_root=$(cd "$fw_path" 2>/dev/null && git rev-parse --show-toplevel 2>/dev/null || echo "")
        if [[ -n "$fw_repo_root" && -n "$product_repo_root" && "$fw_repo_root" == "$product_repo_root" ]]; then
            return 0
        fi
    fi
    return 1
}

if is_self_hosted; then
    if [[ "$MODE" == "check" ]]; then
        echo '{"uncontributed_count": 0, "files": [], "self_hosted": true}'
        exit 0
    elif [[ "$MODE" == "format" || "$MODE" == "submit" ]]; then
        echo "Error: Self-hosted repo — observations are acted on directly, not contributed via issues." >&2
        exit 1
    fi
fi

# --- Resolve framework repo for --submit ---

resolve_framework_repo() {
    local fw_dir=""
    local fw_path_file="$PRODUCT_DIR/.prawduct/framework-path"
    if [[ -f "$fw_path_file" ]]; then
        fw_dir=$(cat "$fw_path_file")
    else
        fw_dir="$FRAMEWORK_DIR"
    fi

    if [[ ! -d "$fw_dir/.git" ]]; then
        echo ""
        return
    fi

    # Use gh to get the repo identifier
    local repo_name
    repo_name=$(cd "$fw_dir" && gh repo view --json nameWithOwner -q '.nameWithOwner' 2>/dev/null || echo "")
    echo "$repo_name"
}

# --- Get uncontributed files ---

get_uncontributed_json() {
    python3 -c "
import sys, json, os
sys.path.insert(0, '$SCRIPT_DIR')
import obs_utils

obs_dir = '$OBS_DIR'
if not os.path.isdir(obs_dir):
    print(json.dumps([]))
    sys.exit(0)

files = obs_utils.get_uncontributed(obs_dir)
print(json.dumps([os.path.basename(f) for f in files]))
" 2>/dev/null || echo "[]"
}

# --- CHECK mode ---

if [[ "$MODE" == "check" ]]; then
    python3 -c "
import sys, json, os
sys.path.insert(0, '$SCRIPT_DIR')
import obs_utils

obs_dir = '$OBS_DIR'
if not os.path.isdir(obs_dir):
    print(json.dumps({'uncontributed_count': 0, 'files': [], 'self_hosted': False}))
    sys.exit(0)

files = obs_utils.get_uncontributed(obs_dir)
result = {
    'uncontributed_count': len(files),
    'files': [os.path.basename(f) for f in files],
    'self_hosted': False
}
print(json.dumps(result))
" 2>/dev/null
    exit $?
fi

# --- Resolve file list (specific files or all uncontributed) ---

resolve_files() {
    if [[ ${#SPECIFIC_FILES[@]} -gt 0 ]]; then
        # Validate specified files exist
        for f in "${SPECIFIC_FILES[@]}"; do
            if [[ "$f" == /* ]]; then
                if [[ -f "$f" ]]; then
                    echo "$f"
                else
                    echo "Error: File not found: $f" >&2
                    exit 1
                fi
            elif [[ -f "$OBS_DIR/$f" ]]; then
                echo "$OBS_DIR/$f"
            elif [[ -f "$f" ]]; then
                echo "$(cd "$(dirname "$f")" && pwd)/$(basename "$f")"
            else
                echo "Error: File not found: $f" >&2
                exit 1
            fi
        done
    else
        # All uncontributed files
        python3 -c "
import sys, os
sys.path.insert(0, '$SCRIPT_DIR')
import obs_utils

obs_dir = '$OBS_DIR'
files = obs_utils.get_uncontributed(obs_dir)
for f in files:
    print(f)
" 2>/dev/null
    fi
}

TARGET_FILES=()
while IFS= read -r line; do
    [[ -n "$line" ]] && TARGET_FILES+=("$line")
done < <(resolve_files)

if [[ ${#TARGET_FILES[@]} -eq 0 ]]; then
    if [[ "$MODE" == "format" ]]; then
        echo "No uncontributed observations found."
        exit 0
    else
        echo "No uncontributed observations to submit."
        exit 0
    fi
fi

# --- FORMAT mode (also used by SUBMIT) ---

format_issue_body() {
    local files_json
    files_json=$(printf '%s\n' "${TARGET_FILES[@]}" | python3 -c "
import sys, json
print(json.dumps([l.strip() for l in sys.stdin if l.strip()]))
" 2>/dev/null)

    python3 -c "
import sys, os, yaml, json
sys.path.insert(0, '$SCRIPT_DIR')
import obs_utils

files = json.loads('$files_json')
product_dir = '$PRODUCT_DIR'
product_name = os.path.basename(product_dir)

# Parse all observations from the target files
all_entries = []
for filepath in files:
    try:
        with open(filepath) as fh:
            for doc in yaml.safe_load_all(fh):
                if not doc or 'observations' not in doc:
                    continue
                session_type = doc.get('session_type', 'unknown')
                session_ctx = doc.get('session_context', {})
                skills = doc.get('skills_affected', [])
                for obs in doc.get('observations', []):
                    if obs.get('status', 'noted') in ('acted_on', 'archived'):
                        continue
                    all_entries.append({
                        'obs': obs,
                        'session_type': session_type,
                        'session_context': session_ctx,
                        'skills': skills,
                        'source_file': os.path.basename(filepath)
                    })
    except Exception as e:
        print(f'<!-- Error parsing {filepath}: {e} -->', file=sys.stderr)
        continue

if not all_entries:
    print('No active observations to format.')
    sys.exit(0)

# Build issue body
lines = []
lines.append(f'## Product Observations from \`{product_name}\`')
lines.append('')
lines.append(f'**Source:** {product_name} ({len(files)} observation file(s), {len(all_entries)} active observation(s))')
fw_version = all_entries[0].get('session_context', {}).get('framework_version', 'unknown')
lines.append(f'**Framework version at capture:** {fw_version}')
lines.append('')

for i, entry in enumerate(all_entries, 1):
    obs = entry['obs']
    obs_type = obs.get('type', 'unknown')
    severity = obs.get('severity', 'note')
    description = obs.get('description', '')
    evidence = obs.get('evidence', '')
    proposed_action = obs.get('proposed_action')
    skills = entry['skills']
    rca = obs.get('root_cause_analysis', {})

    lines.append(f'### {i}. {obs_type} ({severity})')
    lines.append('')
    lines.append(f'**Description:** {description}')
    lines.append('')
    lines.append(f'**Evidence:** {evidence}')
    lines.append('')

    if proposed_action and str(proposed_action) != 'null' and str(proposed_action).lower() != 'none':
        lines.append(f'**Proposed Action:** {proposed_action}')
        lines.append('')

    if skills:
        lines.append(f'**Skills Affected:** {\", \".join(skills)}')
        lines.append('')

    # Collapsible RCA + source details
    has_rca = rca and rca.get('symptom')
    lines.append('<details>')
    lines.append(f'<summary>Details (source: {entry[\"source_file\"]})</summary>')
    lines.append('')

    if has_rca:
        lines.append('**Root Cause Analysis:**')
        lines.append(f'- Symptom: {rca.get(\"symptom\", \"\")}')
        lines.append(f'- Root Cause: {rca.get(\"root_cause\", \"\")}')
        lines.append(f'- Category: {rca.get(\"category\", \"\")}')
        five_whys = rca.get('five_whys', [])
        if five_whys:
            lines.append('- 5-Whys:')
            for w in five_whys:
                lines.append(f'  - **{w.get(\"why\", \"\")}** {w.get(\"answer\", \"\")}')
        lines.append('')

    stage = obs.get('stage', '')
    if stage:
        lines.append(f'Stage: {stage}')
    lines.append(f'Session type: {entry[\"session_type\"]}')
    lines.append('')
    lines.append('</details>')
    lines.append('')

print('\n'.join(lines))
" 2>/dev/null
}

if [[ "$MODE" == "format" ]]; then
    format_issue_body
    exit $?
fi

# --- SUBMIT mode ---

if [[ "$MODE" == "submit" ]]; then
    # Check for gh CLI
    if ! command -v gh &>/dev/null; then
        echo "Error: GitHub CLI (gh) is not installed." >&2
        echo "" >&2
        echo "Install it to submit observations automatically:" >&2
        echo "  macOS:  brew install gh" >&2
        echo "  Linux:  https://github.com/cli/cli/blob/trunk/docs/install_linux.md" >&2
        echo "" >&2
        echo "After installing: gh auth login" >&2
        echo "" >&2
        echo "Alternatively, use --format to generate the issue body and paste it manually." >&2
        exit 2
    fi

    # Check gh auth
    if ! gh auth status &>/dev/null 2>&1; then
        echo "Error: gh is not authenticated. Run: gh auth login" >&2
        exit 2
    fi

    # Resolve framework repo
    FRAMEWORK_REPO=$(resolve_framework_repo)
    if [[ -z "$FRAMEWORK_REPO" ]]; then
        echo "Error: Could not determine framework GitHub repository." >&2
        echo "Ensure the framework directory has a git remote configured." >&2
        exit 1
    fi

    # Generate issue body
    ISSUE_BODY=$(format_issue_body)
    if [[ -z "$ISSUE_BODY" ]]; then
        echo "Error: No observations to submit." >&2
        exit 1
    fi

    PRODUCT_NAME=$(basename "$PRODUCT_DIR")
    OBS_COUNT=${#TARGET_FILES[@]}
    ISSUE_TITLE="Product observations from ${PRODUCT_NAME} (${OBS_COUNT} file(s))"

    # Create the issue
    ISSUE_URL=$(gh issue create \
        --repo "$FRAMEWORK_REPO" \
        --title "$ISSUE_TITLE" \
        --body "$ISSUE_BODY" 2>&1)

    ISSUE_EXIT=$?
    if [[ $ISSUE_EXIT -ne 0 ]]; then
        echo "Error creating GitHub issue: $ISSUE_URL" >&2
        exit 1
    fi

    echo "Created issue: $ISSUE_URL"

    # Mark files as contributed
    TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    for filepath in "${TARGET_FILES[@]}"; do
        python3 -c "
import sys

filepath = sys.argv[1]
issue_url = sys.argv[2]
timestamp = sys.argv[3]

# Read the file
with open(filepath) as f:
    content = f.read()

# Add contribution fields before the closing ---
lines = content.rstrip().split('\n')

if lines and lines[-1].strip() == '---':
    lines.insert(-1, 'contributed_to_framework: \"' + timestamp + '\"')
    lines.insert(-1, 'contribution_issue_url: \"' + issue_url + '\"')
else:
    lines.append('contributed_to_framework: \"' + timestamp + '\"')
    lines.append('contribution_issue_url: \"' + issue_url + '\"')

with open(filepath, 'w') as f:
    f.write('\n'.join(lines) + '\n')
" "$filepath" "$ISSUE_URL" "$TIMESTAMP" 2>/dev/null
        if [[ $? -eq 0 ]]; then
            echo "  Marked contributed: $(basename "$filepath")"
        else
            echo "  Warning: Could not mark $(basename "$filepath") as contributed" >&2
        fi
    done

    exit 0
fi
