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

## Consumer note
A review no longer certifies a later chunk just because its diff touched that chunk's files while
an earlier chunk is still open. `critic-begin` prints a note when it holds a chunk back. To credit
a chunk you built ahead of an earlier one, give its commits a scoped subject
(`<type>(<scope>): … (Chunk N)`) or pass `--chunks N`.
