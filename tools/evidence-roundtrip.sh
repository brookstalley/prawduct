#!/usr/bin/env bash
# Live cross-clone round trip for evidence transport (build-plan-evidence-transport.md,
# Chunk 06): clone X holds this repo's evidence store and syncs it to a local bare mirror;
# clone Y starts empty, syncs it in, and must report the same check-cumulative-critic verdict.
# Nothing leaves the machine. Usage: tools/evidence-roundtrip.sh <repo> <branch> <scratch-dir>
set -euo pipefail

usage() {
    echo "Usage: tools/evidence-roundtrip.sh <repo> <branch> <scratch-dir>" >&2
    exit 2
}
# Every argument is checked before anything is deleted: an empty <scratch-dir>
# would otherwise make the cleanup below `rm -rf /rt`.
[[ $# -eq 3 ]] || usage
[[ -n "$1" && -n "$2" && -n "$3" ]] || usage
[[ -d "$1" ]] || { echo "not a directory: $1" >&2; usage; }
[[ -d "$3" ]] || { echo "not a directory: $3" >&2; usage; }

REPO=$1
BR=$2
S=$3
unset CLAUDE_PLUGIN_ROOT
export GIT_CONFIG_GLOBAL=/dev/null GIT_AUTHOR_NAME=rt GIT_AUTHOR_EMAIL=rt@local GIT_COMMITTER_NAME=rt GIT_COMMITTER_EMAIL=rt@local
STORE="$(git -C "$REPO" rev-parse --path-format=absolute --git-common-dir)/prawduct/evidence.jsonl"
[[ -f "$STORE" ]] || { echo "no evidence store at $STORE" >&2; exit 1; }

rm -rf "$S/rt"
mkdir -p "$S/rt"
cd "$S/rt"
git clone -q --bare "$REPO" mirror.git
git clone -q -b "$BR" mirror.git X
git clone -q -b "$BR" mirror.git Y
# The coverage base: a local `develop` when the mirror has one.
if git -C X rev-parse -q --verify origin/develop >/dev/null; then
    git -C X branch -q develop origin/develop
    git -C Y branch -q develop origin/develop
fi
# X holds the reviewing clone's store (copied verbatim); Y starts empty.
mkdir -p X/.git/prawduct
cp "$STORE" X/.git/prawduct/evidence.jsonl
echo "== X: status before sync"; (cd X && python3 plugin/bin/prawduct-hook evidence status | grep -i 'transported\|notes' || true)
echo "== X: sync (reconcile attaches, push to mirror)"; (cd X && python3 plugin/bin/prawduct-hook evidence sync --json)
echo "== Y: before"; (cd Y && { python3 plugin/bin/prawduct-hook check-cumulative-critic && rc=0 || rc=$?; echo "rc=$rc"; }) | tail -2
echo "== Y: sync (fetch, ingest)"; (cd Y && python3 plugin/bin/prawduct-hook evidence sync --json)
echo "== Y: after"; (cd Y && { python3 plugin/bin/prawduct-hook check-cumulative-critic && rc=0 || rc=$?; echo "rc=$rc"; }) | tail -2
echo "== X: for comparison"; (cd X && { python3 plugin/bin/prawduct-hook check-cumulative-critic && rc=0 || rc=$?; echo "rc=$rc"; }) | tail -2
echo "== Y: facts for this scope"; (cd Y && python3 plugin/bin/prawduct-hook evidence list --kind review -n 3 | head -5) || true
