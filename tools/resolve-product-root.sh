#!/usr/bin/env bash
#
# resolve-product-root.sh — Shared product root resolution
#
# Purpose: Provides consistent product root detection across all tools.
# All repos (including the framework itself) use .prawduct/ for prawduct
# outputs. Falls back to repo root for legacy repos without .prawduct/.
# This script detects which layout is in use and outputs the resolved
# product root path.
#
# Usage (as command — prints product root path):
#   PRODUCT_ROOT=$(tools/resolve-product-root.sh)
#
# Usage (sourced — sets PRODUCT_ROOT and REPO_ROOT variables):
#   source tools/resolve-product-root.sh
#
# Detection order:
#   1. .prawduct/project-state.yaml → product root is .prawduct/
#   2. Root project-state.yaml → product root is repo root
#   3. .prawduct/ directory exists → product root is .prawduct/
#   4. Fallback → product root is repo root
#
# Exit codes:
#   0 — Product root resolved (path printed to stdout)
#   1 — Not in a git repository

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo "")
if [[ -z "$REPO_ROOT" ]]; then
    echo "Error: Not in a git repository." >&2
    exit 1
fi

if [[ -f "$REPO_ROOT/.prawduct/project-state.yaml" ]]; then
    PRODUCT_ROOT="$REPO_ROOT/.prawduct"
elif [[ -f "$REPO_ROOT/project-state.yaml" ]]; then
    PRODUCT_ROOT="$REPO_ROOT"
elif [[ -d "$REPO_ROOT/.prawduct" ]]; then
    PRODUCT_ROOT="$REPO_ROOT/.prawduct"
else
    PRODUCT_ROOT="$REPO_ROOT"
fi

# When executed (not sourced), print the path
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "$PRODUCT_ROOT"
fi
