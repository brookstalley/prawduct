---
schema: 1
type: feature
scope: native-review-paired
date: 2026-11-12
title: development builds pair the native code review with every boundary Critic review
---
#1130 asks whether the Critic should hand generic code review to the host's native `/code-review`.
Nothing local had measured the native review, so on development builds both now run at every
boundary review and their results are recorded for a monthly blind comparison. #1130 stays open
until the comparison and the owner's decision are recorded on it.

### Chunk 0: the host facts, measured
A live session established that `code-review` runs from a subagent and from a forked skill, runs on
its caller's model, comes back either inline or in the background, and ran its `high` recipe when
asked for `medium` (Claude Code 2.1.322). `.prawduct/research/native-review-paired/` holds the note
and `fork_costs.py`, which re-derives each fork's recipe, wall clock and tokens.

### Chunk 01: a development build's boundary review dispatches the native review
`critic-begin` decides the pairing once: a `cumulative` review, a `-dev` plugin version, and no
`native_review_pairing: false` in `project-state.yaml`. When it pairs, the manifest gains a
`native_review` block. The block holds the `code-review` arguments at `high` over the review's commit
range, the reviewers' model, the text path and a rendered wrapper prompt, and `critic-begin` prints
the dispatch line the fork acts on. The validator refuses a block that carries `--fix`, `--comment`,
`--post`, `max` or `ultra`. The dev-build test moved to `core.is_dev_version`, which the contribution
buckets also use. The dispatch instruction lives in the printed line, not in the Critic's skill
prose, so reviews that never pair pay no tokens for it. `.prawduct/.native-reviews/` is a session
path: the wrapper writes there while the reviewers run, and consolidation exempts session paths from
its changed-tree refusal.

### Chunk 02: the record, and the builder sees both lists
`critic-begin` writes a sidecar beside the text, because consolidation deletes the manifest and the
native run may finish later. `prawduct-hook native-review record <id>` appends one `native.review`
ledger event per paired review. The event holds the range, the level, a duration clocked from the
dispatch stamp, and each finding's file and line, but never its text. `ledger-append` refuses that
event kind, which sits outside `review.` so that older readers skip it rather than count it as a
Critic review. `native-review show [<id>]` prints a native review's text. The Critic's
`NEXT-ACTION`, on every path that renders the findings record, names the native list and its count
once the text has landed, so the builder works from both. The
directory ignores itself, so a repo whose root `.gitignore` predates the entry never sees it as
untracked. The wrapper records with the binary that dispatched it, so the sidecar's writer and reader
are one build.

### Chunk 03: the comparison
`compare.py` joins each native run to its Critic review fact and matches findings by file. It
reports shared, Critic-only and native-only findings per goal, each instrument's wall clock and
tokens, and progress toward the stop condition. It also writes a blind sheet and its key for the
verifier. `review-stats` keeps native runs out of every Critic total and reports them on their own
line.

## Consumer note
On a development build of the plugin, each boundary (`cumulative`) Critic review also starts the
host's native `/code-review` at `high` over the same range, beside the Critic and never blocking it.
Its findings are listed in the review's `NEXT-ACTION`, and `prawduct-hook native-review show` prints
them. Set `native_review_pairing: false` in `.prawduct/project-state.yaml` to opt a repo out. Released
builds do nothing new. Every build's `.gitignore` contract gains `.prawduct/.native-reviews/`, so the
gitignore advisory asks once for `prawduct-hook update-gitignore`.
