#!/usr/bin/env bash
#
# update-observation-status.sh — Update observation statuses and archive resolved files
#
# Purpose: Manages the observation lifecycle by updating individual observation
# statuses within files and archiving fully-resolved files. Enforces valid
# status transitions and prevents archiving files with active observations.
#
# Usage:
#   tools/update-observation-status.sh --file FILE --obs-index N --status STATUS
#   tools/update-observation-status.sh --archive FILE
#   tools/update-observation-status.sh --archive-all
#   tools/update-observation-status.sh --list-archivable
#   tools/update-observation-status.sh --product-dir /path/to/project --archive-all
#
# Options:
#   --product-dir DIR  Resolve product root from DIR instead of CWD.
#                      Use when a subagent's CWD differs from the target product.
#
# Operations:
#   --file FILE --obs-index N --status STATUS
#       Update observation N (0-indexed) within FILE to the given status.
#       Validates that the transition is forward-only.
#
#   --archive FILE
#       Move FILE to framework-observations/archive/ if ALL observations
#       in the file are in terminal status (acted_on or archived).
#
#   --archive-all
#       Archive all fully-resolved observation files at once.
#
#   --list-archivable
#       List files eligible for archiving (all observations terminal).
#
# Exit codes:
#   0 — Operation completed successfully
#   1 — Validation failure or missing prerequisites

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse --product-dir before other args
_PRODUCT_DIR_OVERRIDE=""
_remaining_args=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --product-dir) _PRODUCT_DIR_OVERRIDE="$2"; shift 2 ;;
        *) _remaining_args+=("$1"); shift ;;
    esac
done
set -- "${_remaining_args[@]+"${_remaining_args[@]}"}"

# Resolve product root (shared detection logic)
source "$SCRIPT_DIR/resolve-product-root.sh" ${_PRODUCT_DIR_OVERRIDE:+--product-dir "$_PRODUCT_DIR_OVERRIDE"}

OBS_DIR="$PRODUCT_ROOT/framework-observations"
ARCHIVE_DIR="$OBS_DIR/archive"

# Valid statuses in lifecycle order (index = rank)
STATUSES=("noted" "triaged" "requires_pattern" "acted_on" "archived")

# Terminal statuses (eligible for archiving)
TERMINAL_STATUSES=("acted_on" "archived")

get_status_rank() {
    local status="$1"
    for i in "${!STATUSES[@]}"; do
        if [[ "${STATUSES[$i]}" == "$status" ]]; then
            echo "$i"
            return 0
        fi
    done
    echo "-1"
    return 1
}

is_terminal() {
    local status="$1"
    for ts in "${TERMINAL_STATUSES[@]}"; do
        if [[ "$status" == "$ts" ]]; then
            return 0
        fi
    done
    return 1
}

# Check if all observations in a file are in terminal status
all_terminal() {
    local file="$1"
    python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
import obs_utils
sys.exit(0 if obs_utils.all_terminal('$file') else 1)
" 2>/dev/null
    return $?
}

# List all archivable files
list_archivable() {
    python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
import obs_utils

archivable = obs_utils.find_archivable('$OBS_DIR')
if not archivable:
    print('No files eligible for archiving.')
else:
    print(f'{len(archivable)} file(s) eligible for archiving:')
    import os
    for f in archivable:
        print(f'  {os.path.basename(f)}')
" 2>/dev/null
}

# Update a specific observation's status
update_status() {
    local file="$1"
    local obs_index="$2"
    local new_status="$3"

    if [[ ! -f "$file" ]]; then
        echo "Error: File not found: $file" >&2
        exit 1
    fi

    # Validate new status
    local new_rank
    new_rank=$(get_status_rank "$new_status")
    if [[ "$new_rank" == "-1" ]]; then
        echo "Error: Invalid status '$new_status'. Valid: ${STATUSES[*]}" >&2
        exit 1
    fi

    # Get current status and validate forward transition
    python3 -c "
import yaml, sys

STATUSES = ['noted', 'triaged', 'requires_pattern', 'acted_on', 'archived']

file_path = '$file'
obs_index = $obs_index
new_status = '$new_status'

try:
    with open(file_path) as f:
        content = f.read()

    # Parse to validate
    docs = list(yaml.safe_load_all(content))
    obs_count = 0
    current_status = None
    for doc in docs:
        if not doc or 'observations' not in doc:
            continue
        observations = doc.get('observations', [])
        if obs_index < len(observations):
            current_status = observations[obs_index].get('status', 'noted')
            break
        obs_index -= len(observations)

    if current_status is None:
        print(f'Error: Observation index out of range', file=sys.stderr)
        sys.exit(1)

    current_rank = STATUSES.index(current_status)
    new_rank = STATUSES.index(new_status)

    if new_rank <= current_rank:
        print(f'Error: Cannot transition from \"{current_status}\" to \"{new_status}\" (backward transition)', file=sys.stderr)
        sys.exit(1)

    # Perform the replacement using string manipulation to preserve formatting
    # Find the Nth occurrence of 'status: <value>' within observation blocks
    import re

    # Find all status lines within observation entries (indented)
    pattern = r'( {4,}status: )(\w+)'
    matches = list(re.finditer(pattern, content))

    if $obs_index >= len(matches):
        print(f'Error: Could not find observation status at index $obs_index', file=sys.stderr)
        sys.exit(1)

    match = matches[$obs_index]
    new_content = content[:match.start()] + match.group(1) + new_status + content[match.end():]

    with open(file_path, 'w') as f:
        f.write(new_content)

    print(f'Updated observation $obs_index: {current_status} -> {new_status}')

except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1
    return $?
}

# Archive a single file
archive_file() {
    local file="$1"

    if [[ ! -f "$file" ]]; then
        echo "Error: File not found: $file" >&2
        exit 1
    fi

    if ! all_terminal "$file"; then
        echo "Error: Cannot archive $(basename "$file") — contains observations not in terminal status (acted_on or archived)." >&2
        echo "  Update all observations to acted_on or archived first." >&2
        exit 1
    fi

    mkdir -p "$ARCHIVE_DIR"
    mv "$file" "$ARCHIVE_DIR/"
    echo "Archived: $(basename "$file") -> archive/"
}

# Archive all eligible files
archive_all() {
    mkdir -p "$ARCHIVE_DIR"
    local count=0
    shopt -s nullglob
    for f in "$OBS_DIR"/*.yaml; do
        basename=$(basename "$f")
        if [[ "$basename" == "schema.yaml" ]]; then
            continue
        fi
        if all_terminal "$f"; then
            mv "$f" "$ARCHIVE_DIR/"
            echo "Archived: $basename"
            count=$((count + 1))
        fi
    done
    shopt -u nullglob

    if [[ "$count" -eq 0 ]]; then
        echo "No files eligible for archiving."
    else
        echo "Archived $count file(s)."
    fi
}

# --- Main ---

if [[ $# -eq 0 ]]; then
    echo "Usage:"
    echo "  $0 --file FILE --obs-index N --status STATUS"
    echo "  $0 --archive FILE"
    echo "  $0 --archive-all"
    echo "  $0 --list-archivable"
    exit 1
fi

case "$1" in
    --file)
        if [[ $# -lt 6 ]]; then
            echo "Usage: $0 --file FILE --obs-index N --status STATUS" >&2
            exit 1
        fi
        file=""
        obs_index=""
        new_status=""
        shift
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --obs-index) obs_index="$2"; shift 2 ;;
                --status) new_status="$2"; shift 2 ;;
                *) file="$1"; shift ;;
            esac
        done
        if [[ -z "$file" || -z "$obs_index" || -z "$new_status" ]]; then
            echo "Usage: $0 --file FILE --obs-index N --status STATUS" >&2
            exit 1
        fi
        update_status "$file" "$obs_index" "$new_status"
        ;;
    --archive)
        if [[ $# -lt 2 ]]; then
            echo "Usage: $0 --archive FILE" >&2
            exit 1
        fi
        archive_file "$2"
        ;;
    --archive-all)
        archive_all
        ;;
    --list-archivable)
        list_archivable
        ;;
    *)
        echo "Unknown option: $1" >&2
        echo "Usage: $0 --file FILE --obs-index N --status STATUS | --archive FILE | --archive-all | --list-archivable" >&2
        exit 1
        ;;
esac
