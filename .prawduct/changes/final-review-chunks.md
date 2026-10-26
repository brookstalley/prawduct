---
schema: 1
type: fix
scope: final-review-chunks
date: 2026-10-26
title: A final or cumulative review certifies only what was built, and a wrong certification can be retracted
closes: [brookstalley/prawduct#1072]
---

#1072, a v3.8.0 release requirement (owner, 2026-10-26). `plan_status.propose_chunks` proposed
every open chunk for a `final` or `cumulative` review, and `critic-begin` certifies the proposal
when `--chunks` is omitted. `methodology/planning.md` recommends overriding an early keystone chunk
forward to `final`, so following that advice marked every later chunk done before it was built. A
certification could not be taken back.

### Chunk 01: a mode sets depth, not reach

- `final` and `cumulative` now propose the open chunks the review's interval touches through their
  Deliverables. They also propose any open chunk a commit subject on the plan's branch names, so a
  short plan still finishes on its one boundary review.
- They never use `built_report`'s path rule. That rule reads a later chunk's Deliverable as built
  as soon as any earlier commit touches it (the fragment `plan new` stubs is one), which a table
  tag can afford and a certification cannot. The Chunk 01 review blocked on exactly that, using
  the issue's own consumer-digest history.
- `subject_named_chunks` and `built_report` share one `git log` reader. `chunk` mode is unchanged
  and stays free of git walks on the Stop path.
- Two tests that pinned the old contract were renegotiated in the open:
  `test_whole_plan_modes_propose_every_open_chunk` and
  `test_final_proposes_every_open_chunk`. Each is renamed to the new contract, and each new
  assertion was red against the old code.
- The Critic skill's step 4 now points to `propose_chunks` instead of restating the rule. That
  lowered three reviewer-payload readings and their ceilings by 7 tokens.

### Chunk 02: a recorded retraction

- `prawduct-hook plan retract <chunk> --reason R [--fact ID] [--plan <path>] [--json]` appends a
  new `chunk-retracted` fact, `{scope, chunk, fact_id, reason, retracted_at}`.
  `plan_status.chunk_states` stops counting that one fact for that one chunk. The chunk reads open
  with the retraction's reason, the fact's other chunks stay done, and a later review of the chunk
  certifies it again.
- `--fact` omitted means the fact certifying the chunk now, and the same command re-run is a
  no-op (exit 0).
- `plan_status.retraction_target` owns the check behind the write. Its refusals: `no-scope`,
  `unknown-chunk`, `box-import` (a ticked `## Status` box certifies the chunk after any
  withdrawal, so untick it first), `not-certified`, `unknown-fact`, `other-scope`, `not-named`.
- The command needs no owner authority, because a retraction can only reopen a chunk. That arms
  gates and never disarms them.
- The kind is known, observational (the coverage verdict never reads it) and transported. A
  retraction is attached as a note on HEAD like an import, so other clones stop certifying the
  chunk too. An older plugin keeps the kind in its digest and goes on reading the chunk as done.
- The command is refused in a scratch worktree, and on an archived plan at any depth. `plan
  import-status` now uses the same archived-plan rule (`work_unit.is_live_plan_file`); its copy
  missed a nested plan's archive.
- No later proposal restores a retraction. A `verify-resolutions` pass no longer inherits a
  chunk retracted from a fact on its chain. A whole-plan review reads commit subjects only in its
  own commit range, so a mid-plan `final` names nothing built before its interval.

Noticed and left out: #1075. The same Deliverables overlap still tags a chunk `built` in `plan
status` and in `chunk`-mode proposals.

## Consumer note
`/prawduct:critic` in `final` or `cumulative` mode partway through a plan (for example, an early
keystone chunk declaring `Critic mode: final`) now certifies only the chunks that were built, not
every chunk still open. If an earlier review marked unbuilt chunks done, `prawduct-hook plan status`
shows which fact certified each chunk. `prawduct-hook plan retract <chunk> --reason "<why>"`
reopens a chunk on the record.
