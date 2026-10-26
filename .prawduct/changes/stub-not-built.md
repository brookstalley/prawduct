---
schema: 1
type: fix
scope: stub-not-built
date: 2026-10-26
title: A plan's fragment stub no longer reads as its last chunk built
closes: [brookstalley/prawduct#1075]
---

#1075. `plan new` commits the change-fragment stub with the plan, and a plan's change-record chunk
lists that fragment under Deliverables. So the plan commit read as that chunk built:
- `plan status` tagged it `built` straight away;
- a Chunk 01 `chunk` review, whose interval holds the plan commit, proposed it, and so certified it
  when `--chunks` was omitted;
- on a two-chunk short plan, the Stop gate's last-chunk reading (`read_built`) demanded the
  boundary review during Chunk 01.

### Chunk 01: a stub is not work

- `change_fragments.is_unwritten_stub` is the one test for the stub: a fragment whose narrative and
  consumer note are both empty, which is what `plan new` mints. A title alone does not count,
  because `plan new --title` fills it at mint time. Text that does not parse is not a stub.
- `plan_status._work_paths` drops such a fragment from a changed set. Both readers of "which chunks
  have work" ask it: `built_report` reads the fragment at the branch head, and the review proposal
  reads it at the dispatch's own tree. A fragment that cannot be read there (deleted, or git
  failed) is dropped too, so the certifying path names fewer chunks rather than more.
- A whole-plan proposal counts a commit subject's `Chunk N` only when the subject carries the plan's
  scope (`<type>(<scope>): …`), when the plan declares one. The `plan status` tag keeps its
  fallback to every subject when none carries the scope, because a misread tag is cheap and a
  certification is not.
- `plan_status.chunk_proposal` returns notes beside the chunks, and `critic-begin` prints them. A
  note appears when the subject walk could not run, or when a chunk was left out because only an
  unscoped subject names it. Before this, either case dropped the chunk silently, and a later
  `--chunks` naming it warned as if it overreached.
- The extension deferral (the Stop gate and `cost-of-commit`) now also defers pending work that
  is only a stub fragment, or a deleted one, since neither is any chunk's work. That widens the
  next review's interval and loses no coverage.
- The `built` tag was documented as "render-only; no gate reads it". In fact the short-plan Stop
  gate reads it to arm its last-chunk block. The docstrings, `api-contract.md`, `planning.md`'s
  chunk-state rule and the cross-cutting-concerns row now say a gate may read it only to arm.
- The short-plan Stop gate's next-step advice now asks for the scoped subject form
  `<type>(<scope>): … (Chunk <id>)`, which is the only form the boundary proposal counts.

### Chunk 02: change record

This fragment.

## Consumer note
Right after `prawduct-hook plan new`, `plan status` no longer shows the change-record chunk as
`built`, and a first `/prawduct:critic` review no longer proposes it. That chunk now reads as built
once its fragment's narrative or consumer note is written and committed. A `final` or `cumulative`
review now proposes a chunk from a commit subject only when that subject carries the plan's scope,
for example `feat(<scope>): Chunk 02 — …`. When it leaves one out, `critic-begin` prints a
`PRAWDUCT NOTE` naming it, and `--chunks` declares it.
