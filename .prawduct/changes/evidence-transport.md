---
schema: 1
type: feature
scope: evidence-transport
date: 2026-10-25
title: Evidence transport: review facts travel with the branch as git notes
closes: [brookstalley/prawduct#1052, brookstalley/prawduct#1050]
---

Critic review, resolution and chunk-imported facts now travel with the branch. Consolidation
appends each fact's store line as a note on its anchor commit under `refs/notes/prawduct`;
`/prawduct:pr create|update` pushes the ref after the branch, and a clone that has the notes
ingests them into its own evidence store at session start, so it reaches the same coverage verdict
from the same facts. The store itself still never leaves its clone, and gates read only the store:
a note is a copy, deduplicated by fact id on the way in, and verdicts still compose by the tree ids
inside each fact. A fact whose note was never written is found and re-attached before the next
push, and `evidence status` counts any that remain. A plan's lifecycle (in progress, merged and
awaiting release, released, superseded) is observed from git, the review facts' anchors and the
change record by `plan status`, stored nowhere. The Critic skill's `evidence` grant narrows to
`status` and `list`, since `ingest` writes the store a reviewer must not touch, and a test now fails
any skill or agent grant whose prefix reaches a data-plane write. Wave 3 of #1050; closes #1052
and, as its last child, #1050.

## Consumer note

- Three new commands. `prawduct-hook evidence ingest [--all]` reads the ref into the store
  (session start runs it bounded to the branch). `evidence sync [--no-push]` fetches, merges,
  ingests and pushes the ref; `/prawduct:pr create|update` runs it after the branch push, and a
  failure there is reported without blocking the PR. `evidence configure --apply` adds the notes
  fetch refspec and `notes.rewriteRef` to the clone's `.git/config`, so a plain `git fetch` brings
  the remote's notes into a tracking ref for the next sync and an amend or rebase keeps them; `/prawduct:doctor` offers it and
  `/prawduct:onboard` runs it. Exit codes are in `api-contract.md`.
- A fresh clone has an empty store: it shows a branch's coverage after one `evidence sync` run with
  that branch checked out.
- Reviews of uncommitted trees count only in the clone that holds the tree; the boundary
  `cumulative` is committed, so the PR gate's verdict is identical in every clone.
- `stats` and `contribute` read the store, so reviews ingested from another clone count there too.
- `plan status` prints a `lifecycle:` line and `--json` gains `lifecycle`; `--probe-pr` asks GitHub
  for a merged PR when git alone cannot tell (never run by a hook).
