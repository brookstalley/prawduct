#!/bin/zsh
# Live cross-clone round trip for evidence transport (build-plan-evidence-transport.md,
# Chunk 06): clone X holds this repo's evidence store and syncs it to a local bare mirror;
# clone Y starts empty, syncs it in, and must report the same check-cumulative-critic verdict.
# Nothing leaves the machine. Usage: tools/evidence-roundtrip.sh <repo> <branch> <scratch-dir>
set -e
REPO=$1; BR=$2; S=$3; unset CLAUDE_PLUGIN_ROOT
export GIT_CONFIG_GLOBAL=/dev/null GIT_AUTHOR_NAME=rt GIT_AUTHOR_EMAIL=rt@local GIT_COMMITTER_NAME=rt GIT_COMMITTER_EMAIL=rt@local
rm -rf $S/rt && mkdir -p $S/rt && cd $S/rt
git clone -q --bare "$REPO" mirror.git
git clone -q -b "$BR" mirror.git X && git clone -q -b "$BR" mirror.git Y
git -C X branch -q develop origin/develop; git -C Y branch -q develop origin/develop
# X holds the reviewing clone's store (copied verbatim); Y starts empty.
mkdir -p X/.git/prawduct && cp "$(git -C $REPO rev-parse --path-format=absolute --git-common-dir)/prawduct/evidence.jsonl" X/.git/prawduct/evidence.jsonl
echo "== X: status before sync"; (cd X && python3 plugin/bin/prawduct-hook evidence status | grep -i 'transported\|notes' || true)
echo "== X: sync (reconcile attaches, push to mirror)"; (cd X && python3 plugin/bin/prawduct-hook evidence sync --json)
echo "== Y: before"; (cd Y && python3 plugin/bin/prawduct-hook check-cumulative-critic; echo "rc=$?") | tail -2
echo "== Y: sync (fetch, ingest)"; (cd Y && python3 plugin/bin/prawduct-hook evidence sync --json)
echo "== Y: after"; (cd Y && python3 plugin/bin/prawduct-hook check-cumulative-critic; echo "rc=$?") | tail -2
echo "== X: for comparison"; (cd X && python3 plugin/bin/prawduct-hook check-cumulative-critic; echo "rc=$?") | tail -2
echo "== Y: facts for this scope"; (cd Y && python3 plugin/bin/prawduct-hook evidence list --kind review -n 3 | head -5)
