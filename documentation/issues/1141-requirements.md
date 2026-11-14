# Issue #1141 — plan status: a chunk is done from another chunk's review: Requirements

`status: draft · stage: requirements · area: build-plan · added: 2026-11-14 · source: upstream
bug report 2026-11-11 and its triage comment · issue:
https://github.com/brookstalley/prawduct/issues/1141`

Related: #1082 (span certification, and the ruling that took path credit from spans), #1060 (a
blocking finding a spanning review cleared has no record), #672 (coverage composes by tree, gates
key on identity). The norm this item defends is `plugin/methodology/planning.md` "Chunk state".

## Problem

A product repo reported a five-chunk serial plan in which chunk 4 read `done` under chunk 2's
review id before chunk 4 was built. Chunks 2 and 4 both listed one module under Deliverables. The
briefing then resumed at chunk 5, and when chunk 4 was built `infer-critic-mode` answered
`deferred`, taking the work for the cumulative-final chunk's. Chunk 4 got no review of its own
unless the agent overrode the inference.

The report's stated cause (a shared Deliverables path credits both chunks) does not reproduce on
current develop: `plan_status._deliverable_chunks` credits a path to its one owner and notes the
shared path. So the wrong certification came by another route, and the record cannot say which.
That is the second defect, and the one that keeps the first open: `plan status` prints a named
certification as a bare fact id. It does not say whether the builder passed `--chunks`, whether
the id came from the dispatch's own proposal, or which path or commit subject put it there. A span
certification prints its reason; a naming certification prints none.

Read from the code, three routes can certify a chunk whose work a review did not read. None is
confirmed as the reported one.

| Route | How chunk 4 gets certified by chunk 2's review | Standing today |
|---|---|---|
| A. Sole-owner path | Chunk 2's diff touches a path that only chunk 4's Deliverables cover, most easily a new file under a directory chunk 4 lists. The `chunk`-mode proposal then names 02 and 04, and with no `--chunks` the proposal is what the fact names. | Open. Printed on stderr at dispatch as a proposal, with no flag that a one-chunk review is about to certify two. |
| B. Declared | `--chunks` was passed with 04 in it. | A warning is printed when the declared set leaves the proposal, and both lists are on the fact. Nothing reads them back at `plan status`. |
| C. Subject | A first-parent commit in the review's interval carries the plan's scope and `(Chunk 4)` in its subject. | By design (#1082). `plan status` prints the reason. |

A fourth explanation is version skew: the installed plugin predated the one-owner rule while
reporting `3.8.1-dev`. The requirements below hold whichever it was.

## Goals

- G1. A review certifies a chunk only when it read that chunk's work, or when the builder said so
  in words the record keeps.
- G2. Every `done` row says how it became done, in enough detail that a wrong one is diagnosed
  from `plan status` output alone, without the reporting repo's evidence store.
- G3. A wrong certification that does land is recoverable by the route the methodology names
  (`plan retract`), and the surface that meets it first says so.
- G4. The reported sequence is a regression test, written from the report's shape and from each
  route in the table, and seen to fail before the fix (core.md: a check never seen to return
  non-zero proves nothing).

## Non-goals

- Changing the span rule or returning path credit to spans (#1082, owner ruling 2026-10-27).
- A general ownership model for shared files. A path two chunks list stays creditable to neither.
- Re-certifying history. Facts already written keep what they name; R5 covers how they render.
- Requiring commit-subject conventions beyond the ones `planning.md` already states.
- The cumulative-final chunk's own review depth. Only which chunk the work is attributed to.

## Requirements

**Certification**

- R1. A `chunk`-mode review does not certify a chunk by proposal alone when the proposal names
  more than one chunk. The dispatch asks the builder to choose with `--chunks` and says, per
  proposed chunk, which touched path put it there. Design picks refusal or a narrowed default
  (for example the earliest open chunk); whichever it picks, an unstated second chunk is never
  written to `chunks`. Whole-plan modes keep today's behaviour, since naming several chunks is
  their purpose.
- R2. A path gives a chunk credit in a proposal only when the evidence is the chunk's own work
  and not a neighbour's side effect. At minimum: a file created under a directory another open
  chunk lists does not by itself propose that chunk when the same diff also has a path only an
  earlier open chunk lists. Design decides whether this is a rule on directory deliverables, on
  plan order, or folded into R1, and states which fixtures it changes.
- R3. The one-owner rule for a shared path stays, and its note stays. A test pins the report's
  exact shape: chunks 02 and 04 share one module, 02 edits it and is reviewed, 04 stays `open`
  and the next `infer-critic-mode` for 04's work infers a chunk review, not `deferred`.

**Legibility**

- R4. A row certified by naming says how the name got there: declared by `--chunks`, or taken
  from the proposal, and for a proposal the path or subject that proposed it. This is derived
  from what the fact already records (`chunks`, `chunks_proposed`) plus whatever R1 adds at
  dispatch. No stored copy of the route is added if it can be computed (hook-surface: observable
  beats stored).
- R5. A fact written before this change renders a route too, even if only "named; route not
  recorded". Absence is stated, never left as a blank that reads like the normal case.
- R6. When a declared set leaves the proposal, `plan status` shows that on the affected row.
  Today the warning is printed once at dispatch and is not seen again.
- R7. The three surfaces that print the table (`plan status`, the `/clear` handoff, the PR
  payload) agree, by sharing the renderer as they do now. The route is not a fourth reader's
  re-derivation.

**Recovery**

- R8. When `infer-critic-mode` answers `deferred` for work whose diff touches the Deliverables of
  a chunk that is already `done`, its message names that chunk, the fact that certified it, and
  `prawduct-hook plan retract <chunk> --reason …` as the remedy if the certification is wrong. It
  stays advice: the inference does not change, because a done chunk's file being edited by a later
  chunk is ordinary.
- R9. After a retraction the reported sequence completes: chunk 4 reads `open` with the
  retraction's reason, the next inference for its work is a chunk review, and that review
  certifies it. A test walks the whole sequence.

**The report itself**

- R10. The bug-report intake (`/prawduct:report-bug`) asks for, or collects, the certifying fact's
  `chunks`, `chunks_proposed`, mode and whether `--chunks` was passed whenever the component is
  `plan status` or chunk state. This issue could not be triaged to a cause for want of exactly
  those four values. Collected values pass the existing redaction rules; no file content leaves
  the product repo.
- R11. `found_in` distinguishes a development tree from a released plugin well enough to rule
  version skew in or out, or the report says it cannot. Design decides whether the existing
  version string plus a commit id is enough.

## Non-functional

- NF1. `chunk_states` stays walk-free outside a fact's own interval (its module docstring's NF1).
  The route in R4 costs no new `git log`.
- NF2. Every change here fails closed: when the route cannot be decided, fewer chunks are named,
  a chunk stays `open`, and the gates stay armed.
- NF3. No new field becomes a second source of truth for chunk state. `chunks` remains the only
  thing `fact_chunks` reads.

## Acceptance

- A1. Fixtures for routes A, B and C each produce a `plan status` whose `done` row names its
  route (R4), and route A no longer certifies the second chunk without `--chunks` (R1, R2).
- A2. The report's reproduction, steps 1 to 5, runs as one test and ends with chunk 4 reviewed
  as a chunk (R3, R9).
- A3. Each new test is seen red against develop as it stands before the fix, or the document
  recording the build says which ones were already green and why (G4).
- A4. A falsifying query over the prose: no sentence in `planning.md`, `critic/SKILL.md` or
  `review-cycle.md` still says an omitted `--chunks` names "exactly the proposal" without the R1
  exception.

## Open questions for the owner

1. R1: refuse the dispatch, or narrow to the earliest open chunk and say so? Refusal is the safer
   reading of "a certified chunk is never reviewed again"; narrowing costs the builder nothing on
   the common case. Recommendation: refuse, with the exact `--chunks` line to re-run.
2. Is the reporting repo's evidence still available? The four values in R10 would confirm which
   route this was and could shrink R2. The requirements do not wait on it.
3. R8 touches the deferral message, which several tests pin. Is advice there acceptable, or should
   the notice live only in `plan status`?

## What was checked, and what was not

Read on develop at `a76ea2ef`: `plan_status.chunk_states`, `chunk_proposal`,
`_deliverable_chunks`, `_Spans`, `render_table`, and the declared-versus-proposed handling in
`critic_consolidate` (dispatch). Not run: no fixture was built for route A, so "a new file under a
later chunk's directory proposes that chunk" is a reading of `_touches` and `_deliverable_chunks`,
not an observed result. Not read: `critic_mode`'s deferral path beyond its call into
`propose_chunks`. Design starts by reproducing route A.
