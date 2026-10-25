---
schema: 1
type: feature
scope: evidence-transport
date: 2026-10-25
title: Evidence transport: review facts travel with the branch as git notes
closes: [brookstalley/prawduct#1052, brookstalley/prawduct#1050]
---

Critic review, resolution and chunk-imported facts now travel with the branch: consolidation
appends each fact's store line as a note on its anchor commit under `refs/notes/prawduct`, and a
clone that fetches the ref ingests those lines into its own evidence store, so it reaches the same
coverage verdict from the same facts. A plan's lifecycle (in progress, merged and awaiting
release, released, superseded) is observed from git and the change record by `plan status`,
stored nowhere. Wave 3 of #1050; closes #1052 and, as its last child, #1050.

## Consumer note

Three new commands: `prawduct-hook evidence ingest` (reads the ref into the store; session start
runs it), `evidence sync` (fetch, merge, ingest, push — `/prawduct:pr create|update` runs it after
the branch push) and `evidence configure --apply` (`doctor` offers it; `onboard` runs it) so plain
`git fetch` carries the notes. A fresh clone shows coverage for a branch after one `evidence sync`
or a configured refspec plus a fetch. Mid-chunk reviews of uncommitted trees stay readable only in
the clone that holds the tree; the boundary `cumulative` is committed, so the PR gate's verdict is
identical in every clone. `plan status` prints a `lifecycle:` line and `--json` gains `lifecycle`;
`--probe-pr` asks GitHub for a merged PR when git alone cannot tell (never run by a hook).
