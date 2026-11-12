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
review can report its base as moved. A blocker on the path to the frontier forces the full span,
never an older frontier; one recorded after the frontier lies inside the bounded interval, which
spans it.

`critic-begin --mode cumulative` bounds the interval to that review's tree → HEAD when one exists.
The delta is the subject, the roster comes from the delta, and the rest of the bundle reaches the
reviewer as `files_context`, never rated on its own merits: a description there that the delta
made false is a finding about the delta file. Record-lint and the chunk proposal still
grade the whole bundle, exactly as a full span would. Any declined condition falls back to the full
span and says why. `span`, `bounded_from` and `span_reason` ride the manifest, the review fact and
the findings cache, which the ledger copies. `/prawduct:critic cumulative full` (or `full`) asks
for the whole bundle; `infer-critic-mode` answers it with the rationale `explicit-args full`, which
`critic-begin` reads from `--chosen-by`.

### Protocol (Chunk 03)

The reviewer's `Signals:` line ends `Span: bounded from <id>` or `Span: full` on a cumulative.
`review-protocol.md` says what a bounded reviewer rates: the delta, and a `files_context` file only
where the delta made its description false, with record-lint and `test-status` still covering the
whole bundle. `review-cycle.md` and the Critic
skill describe the bounded repeat and the `full` override, and every sentence that said a
cumulative always spans merge-base...HEAD now says when it does.

### Measure (Chunk 04)

`prawduct-hook review-stats` gains `by_span` (report schema 11): cumulative reviews grouped as
`bounded` or `full`, both listed even at zero, with the `full` entry counting why each one ran
full. A cumulative recorded before the field reads `full`, because nothing was bounded then. The
measurement against the design's falsifier needs bounded rows from consumer repos, so it is filed
for after the release.

## Consumer note

A repeat `/prawduct:critic cumulative` on a long-lived branch now reviews only what changed since
the branch's last clean boundary review, and says so when it dispatches (`Span: bounded from
<id>`). The PR gate is unchanged. Before a risky merge, `/prawduct:critic cumulative full` reviews
the whole branch again; a product that wants that every time can require it in its own process.
