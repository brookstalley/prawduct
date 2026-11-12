---
schema: 1
type: feature
scope: bounded-cumulative
date: 2026-11-11
title: A repeat cumulative reviews what changed since the last boundary review
closes: [brookstalley/prawduct#890]
---
A long-lived branch's repeat `cumulative` used to re-review the whole bundle every time, even when
an earlier boundary review had already rated most of it. The design is
`.prawduct/artifacts/bounded-cumulative-design.md`; the owner's six decisions are dated
2026-09-22, and Decision 2 was re-ruled on 2026-11-11. Composition and the PR gate do not change.

### The trade is re-derivable (Chunk 01)

`tools/measure-repeat-cumulative-yield.py <repo>` re-derives the design's measured trade from a
repo's ledger, its evidence store or both, read-only. For every cumulative it finds the newest
earlier cumulative on the same lineage and splits that review's findings into delta, old-only and
no-files. `--until`/`--since` set the window, and `--vanished-in changed|source` selects how a
replay of the interaction sweep reads "gone". Its replay found the sweep reaching none of the
same-base stale-prose losses through a word the finding names, under either reading, so the owner
ruled that no sweep is built.

### Frontier and interval (Chunk 02)

`gates.boundary_frontier` finds the newest boundary review that the current bundle extends cleanly:
same base, on this branch's history, not already at HEAD, and a clean path to it from the
merge-base. Another branch's review in the clone-wide store is skipped, and only this branch's own
review can report its base as moved. A blocker on the newest candidate forces the full span rather
than an older frontier, so a superseded blocker still clears only through a full span.

`critic-begin --mode cumulative` bounds the interval to that review's tree → HEAD when one exists.
The delta is the subject, the roster comes from the delta, and the rest of the bundle reaches the
reviewer as `files_context`, read and rated by no pass. Record-lint and the chunk proposal still
grade the whole bundle, exactly as a full span would. Any declined condition falls back to the full
span and says why. `span`, `bounded_from` and `span_reason` ride the manifest, the review fact and
the findings cache, which the ledger copies. `/prawduct:critic cumulative full` (or `full`) asks
for the whole bundle; `infer-critic-mode` answers it with the rationale `explicit-args full`, which
`critic-begin` reads from `--chosen-by`.

### Protocol (Chunk 03)

The reviewer's `Signals:` line ends `Span: bounded from <id>` or `Span: full` on a cumulative.
`review-protocol.md` says what a bounded reviewer rates: the delta, never `files_context`, with
record-lint and `test-status` still covering the whole bundle. `review-cycle.md` and the Critic
skill describe the bounded repeat and the `full` override, and every sentence that said a
cumulative always spans merge-base...HEAD now says when it does.
