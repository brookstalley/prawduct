---
schema: 1
type: fix
scope: chunk-plan-order
date: 2026-11-22
title: "No chunk certified while an earlier one is open (#1141, #1198)"
closes: [brookstalley/prawduct#1141, brookstalley/prawduct#1198]
---
A review could certify a chunk whose work it never covered. A diff that touched a later chunk's
Deliverables path proposed that chunk. With `--chunks` omitted, the proposal is what the review
fact names, so the chunk read `done`. #1198 hit this on a part-merged plan: part one wrote a file
that only the cumulative-final chunk listed, and the boundary review certified that chunk while an
earlier one was still open. #1141 hit it in `chunk` mode: a new file under a later chunk's
directory named that chunk.

### Chunk 01: plan order in the proposal

`plan_status._deliverable_chunks` already enforced the one-owner rule for path credit. It now also
enforces plan order. A chunk credited only by a path is proposed only while every open chunk
before it is proposed too. Once one open chunk is left out, every later path-only chunk is
withheld, and the dispatch prints a note naming the path and the earlier open chunk. Done and
dropped chunks open no gap. Words still name a chunk out of order: a scoped `(Chunk N)` subject in
a `final` or `cumulative`, `--chunks`, or a span. That is how a delegated chunk landing first is
credited. The subject walk now runs before the path rule, so the rule knows which chunks words
named.

`ChunkProposal` gains `withheld`, `touched` (every open chunk the work covers, before either rule)
and `evidence` (the paths and commits that named each proposed chunk). The Stop-path deferral
(`critic_mode.extension_deferral_owed`) now reads `touched`. Before, work on a chunk held back by
either rule read as "touches no open chunk", which deferred the review of a chunk nobody had
reviewed (#1141-R3).

### Chunk 02: the `chunk`-mode refusal and the recorded route

A `chunk` review is one chunk's review, and plan order cannot tell two adjacent chunks apart. So a
`chunk` dispatch with `--chunks` omitted, whose proposal names more than one chunk, now exits 8
(`chunks-ambiguous`) before anything is written. The message names the paths that proposed each
chunk and the two `--chunks` lines to re-run with. Each refusal records one `guard-refusal` fact,
the one sink every pre-dispatch refusal uses. The manifest and the review fact also record
`chunks_declared` (whether `--chunks` was passed) and `chunks_evidence` (the paths and commits that
named each proposed chunk). Nothing reads them for state; they carry the route a `done` row will
print. The critic skill's exit table gains the row for 8.

### Chunk 03: legible rows and the out-of-order flag

Every row a review fact certified now says how that fact came to name the chunk, read from the fact
alone. The proposal's path or commit, `--chunks` (in or outside the proposal), a span, or that the
fact predates the record. `plan status` also flags a review-done chunk with an open chunk before it
(`ahead_of`, also a key in `plan status --json`). The flag is worded by route: out of order is
expected when the builder's own words named the chunk, and otherwise the flag names the retraction
to run if the work is not built. The `/clear` handoff prints the same table. When the Stop-path
deferral holds, its message now names a done chunk that the pending work touches, together with the
fact that certified it (`plan_status.done_chunks_touched`). Only the code's own naming is questioned:
it stays silent for a chunk certified by the builder's words (`--chunks`, or a span's scoped
subject), and for the one chunk the newest review named. That is where a wrong certification is
met first.

### Chunk 04: `plan retract <chunk> --all`

`plan retract` withdrew one fact's certification at a time, and a chunk certified by several
facts, or by a span that surfaces once the naming facts are withdrawn, took one run per fact.
`--all` now withdraws every certification in one command, one `chunk-retracted` fact per pair. That
is each fact naming the chunk, including a blocked one that would certify once its blocker
resolves, and then any span a withdrawal uncovers. `plan_status.retraction_plan` plans the pairs
and only reads; the CLI writes behind it. A write that fails partway says what was written and
exits 1, and a re-run converges, because every written pair answers `already`. `--all` with
`--fact` is a usage error. Without `--all`, the "still reads done" line names it.

### Chunk 05: bug-report intake

A bug report about `plan status` or chunk state now carries what decides the row: the affected
`plan status --json` row, and the certifying fact's chunk fields. `evidence list` gains `--id` and
`--json`, so the intake can read those fields; the one-row listing never showed a body. On a `-dev`
build, the report's Found-in label also carries the plugin tree's commit
(`prawduct v3.9.1-dev (plugin, build <commit>)`). A version plus a commit is enough to rule version
skew in or out. A released version keeps its bare label, and the report's machine-read `found_in`
stays the bare version.

### Chunk 06: methodology and descriptions

`planning.md` "Chunk state" states the plan-order rule, how to name a chunk built ahead of an open
one, the `chunk`-mode refusal, and `retract --all`. Plan Shape gains "A plan may ship in parts",
which says to merge each part with a merge commit or a fast-forward, because a squash reopens the
part's chunks. An end-to-end test pins both outcomes. The API contract records exit 8,
`chunks_declared`/`chunks_evidence`, `plan status --json`'s `ahead_of` and its route lines, `plan
retract --all`, and `evidence list --id/--json`. The data model records the two new fact fields,
and the review cycle's manifest key list names them.

## Consumer note
A review no longer certifies a later chunk just because its diff touched that chunk's files while
an earlier chunk is still open. Earlier certifications are not rewritten: `plan status` flags any
done chunk with an open chunk before it, and `plan retract <chunk> --all` reopens one that was
never built. `critic-begin` prints a note when it holds a chunk back. To credit
a chunk you built ahead of an earlier one, give its commits a scoped subject
(`<type>(<scope>): … (Chunk N)`) or pass `--chunks N`. A `chunk` review whose diff proposes two
chunks now stops with exit 8 and asks you to name the one you built with `--chunks`.
`plan status` now says how each done chunk became done, and flags one with an open chunk before it.
`plan retract <chunk> --all --reason …` withdraws every certification of a chunk at once.
