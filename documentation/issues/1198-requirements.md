# Issue #1198 — part-merged plan: the cumulative-final chunk reads done: Requirements

`status: draft · stage: requirements · area: plan-status · added: 2026-11-20 · source: upstream
bug report 2026-11-18 and its triage comment · issue:
https://github.com/brookstalley/prawduct/issues/1198`

Related: #1141 (a chunk done from another chunk's review; same class, and its requirements are
amended by this document, see "Effect on #1141"), #1082 (span certification, and the ruling that
took path credit from spans but kept it for naming), #1060 (a blocking finding a spanning review
cleared has no record). The norm this item defends is `plugin/methodology/planning.md` "Chunk
state".

## Problem

A product repo shipped a six-chunk plan in two parts. Chunks 01 to 04 were built and reviewed,
then a boundary `cumulative` review ran before the part-one PR, then a `verify-resolutions` pass
over a fix. Afterwards `plan status` read 01 to 04 `done`, 05 `open` and 06 `done`, where 06 is
the plan's `Type: cumulative-final` chunk and none of its work existed. A second plan in the same
repo did the same on the same day. Each chunk took two `plan retract` calls to reopen, one per
certifying fact.

The plan then claims its final, cumulative-reviewed chunk is complete. Every reader of chunk
state inherits that: the briefing skips it, `infer-critic-mode` sees one open chunk fewer, and
`boundary_cumulative_still_owed` (which asks for exactly one open chunk) is asked the wrong
question when chunk 05 is later built.

## Cause: reproduced

The triage comment read the route from the code. It is now reproduced on develop at `63fdfbdd`
with a throwaway fixture (a real git repo, the test suite's own plan and fact helpers; no test
was added).

| Fixture (six chunks; 01 to 04 committed with scoped subjects) | `chunk_proposal`, `cumulative` | `chunk_states` with a fact naming the proposal |
|---|---|---|
| 06 lists `docs/guide.md`; no other chunk lists it; part one commits it | 01, 02, 03, 04, **06**; no note | 05 `open`, **06 `done`** |
| 06 lists the directory `docs/site/`; part one adds `docs/site/new.md` | 01, 02, 03, 04, **06**; no note | 05 `open`, **06 `done`** |
| Control: part one touches nothing 06 lists | 01, 02, 03, 04 | 05 and 06 `open` |
| Control: 05 and 06 both list `docs/guide.md` | 01, 02, 03, 04, with the shared-path note | 05 and 06 `open` |

`final` and `chunk` modes return the same proposals for the same diffs, so the mode is not the
cause. The cause is the path half of the proposal (`plan_status._deliverable_chunks`): one touch
of a path that only one chunk lists proposes that chunk, whoever's work the touch was. With no
`--chunks` at dispatch, the proposal is what the fact names, and a named chunk is certified.

Nothing special-cases `Type: cumulative-final`. That chunk is the likeliest victim for a plain
reason: it tends to list the paths that close a plan (a change fragment, a guide, a release
note), and shipping part one early means writing exactly those paths early. Which path it was in
the reporting repo is not known; the report does not carry chunk 06's Deliverables.

The second certifying fact is by design of a different rule and is confirmed by reading only:
a `verify-resolutions` dispatch proposes the chunks named on the chain of the review it verifies
(`critic_consolidate._proposed_chunks`), so it copied 06 forward. That is why one retraction left
the chunk `done` under the next fact.

This also settles route A in #1141's requirements, which that document marked as read and not
run: the directory fixture above is that route.

## Goals

- G1. A review does not certify a chunk on the strength of a path touch that was another chunk's
  work, in any mode.
- G2. A chunk state that cannot be right is visible in `plan status` without anyone suspecting it
  first.
- G3. Withdrawing a wrong certification takes one command per chunk, however many facts carry it.
- G4. Shipping a plan in parts is either a supported shape with a stated procedure, or the
  methodology says it is not. Today it is neither.

## Non-goals

- Changing the span rule, or returning path credit to spans (#1082).
- Deciding what review depth part one of a plan owes. Only which chunks its reviews certify.
- Rewriting facts already in a store. Wrong ones are retracted; R6 covers finding them.
- A general model of file ownership across chunks. The shared-path rule stays as it is.

## Requirements

**Certification**

- R1. A path touch alone does not certify a `Type: cumulative-final` chunk while any earlier chunk
  of the plan is open and is not named by the same review. The chunk is left out of the proposal
  and a note says why, naming the path and the open chunk. `--chunks` still names it, with the
  existing declared-outside-proposal warning.
- R2. Design decides how far R1 generalises, and states which existing fixtures change:
  (a) cumulative-final only; (b) any chunk proposed by path alone while an earlier chunk is open
  and unproposed; (c) no path-only proposal in whole-plan modes at all, leaving subjects and
  `--chunks`. Whichever it picks holds in `chunk`, `final` and `cumulative` alike, because the
  reproduction shows the three agree. It must keep the short-plan case working: a plan whose last
  chunk is built and reviewed by the boundary `cumulative` still finishes on that review
  (`test_the_end_of_plan_cumulative_still_names_every_built_chunk`).
- R3. A `verify-resolutions` pass never widens what its chain certifies, and inherits a narrowing:
  once R1 keeps a chunk out of a review's `chunks`, the verify pass over that review does not name
  it. This is today's inheritance rule; the requirement is a test that pins it for this case.

**Legibility**

- R4. `plan status` flags any row that is `done` by a review fact while an earlier chunk is `open`
  and the done chunk is `Type: cumulative-final`. The flag names the certifying fact and
  `plan retract` as the remedy. It is advice printed with the row; it changes no state and no
  gate, and it renders through the one table renderer so the `/clear` handoff and the PR payload
  show it too.
- R5. Design decides whether R4 extends to every out-of-order `done` (a later chunk done, an
  earlier one open). That state is legitimate for independent chunks, so if it extends, the
  wording must not call a legitimate state wrong.
- R6. The flag in R4 is how a repo already carrying this defect finds it after upgrading. No
  migration, no doctor check that rewrites state.

**Recovery**

- R7. `plan retract <chunk> --all --reason …` withdraws every fact that certifies the chunk now or
  would certify it once the current one is withdrawn: each review or import fact of the plan's
  scope that names it, and a span that certifies it. It writes one `chunk-retracted` fact per
  pair, as today, prints each pair, and ends by printing the chunk's state. `--all` with `--fact`
  is a usage error.
- R8. `--all` keeps `retract`'s refusals: a ticked `## Status` box still refuses first, and a
  re-run after a full withdrawal answers `already` and writes nothing.
- R9. Without `--all`, the existing "still reads done, certified by <next fact>" line also names
  `--all`.

**Methodology**

- R10. `planning.md` says what a plan shipped in parts owes, in the place "Chunk state" already
  covers certification: that a part-one boundary review certifies the chunks built so far and
  not the plan's cumulative-final chunk, and what the last part's boundary review then spans.
  If the owner's answer to question 1 is that part-shipping is not a supported shape, the same
  place says so and points at splitting the plan ("Plan Shape").

## Non-functional

- NF1. `chunk_states` gains no git walk. R4 reads chunk `Type:` from the plan text it already
  holds and the states it already computed.
- NF2. Every change fails closed: when in doubt fewer chunks are named, a chunk stays `open`, and
  gates stay armed.
- NF3. `chunks` on the fact remains the only thing naming certification reads. R1 changes what
  the proposal offers, not how a fact is read, so facts written before the change read as before
  (and are caught by R4 where wrong).

## Acceptance

- A1. The first two fixtures in the table above run as tests, in each of `chunk`, `final` and
  `cumulative`, and end with 06 `open`. Both controls stay as they are. Each new test is seen red
  on develop before the fix.
- A2. The report's sequence runs as one test: chunks 01 to 04 reviewed, a `cumulative` over part
  one, a `verify-resolutions` over it, and 05 and 06 both `open` at the end.
- A3. A fact written before the fix that names 06 (the reproduced state) renders with the R4
  flag, and one `plan retract 06 --all` leaves it `open`.
- A4. After 05 and 06 are built, the plan's real boundary `cumulative` certifies both and the plan
  reads finished.
- A5. A falsifying query over the prose: no sentence in `planning.md`, `critic/SKILL.md` or
  `review-cycle.md` still says a whole-plan review names every open chunk whose Deliverables the
  diff touches without the R1 exception.

## Effect on #1141

#1141's R1 ends "Whole-plan modes keep today's behaviour, since naming several chunks is their
purpose." This issue is the counter-example: the wrong certification arrived in a whole-plan
mode. That sentence should be replaced by a reference to R1 and R2 here. The two documents
otherwise fit: #1141 stops a `chunk` review from naming a second chunk unasked and makes every
`done` row say how it became done; this one stops a path touch from certifying a boundary chunk
early, flags the state, and adds `--all`. They touch the same functions and are best designed
together and built as one plan.

## Open questions for the owner

1. Is shipping one plan in two PRs a supported shape (R10)? The reporting repo did it twice in a
   day, which suggests it is natural. Recommendation: support it, state it in `planning.md`, and
   keep the advice to split a plan that is known in advance to ship in waves.
2. R2: how far should the rule generalise? Recommendation: (b), the plan-order rule, because it
   also shuts #1141's route A and needs no knowledge of chunk types; (a) is the smallest change
   if (b) breaks plans that are legitimately built out of order.
3. Should #1141 and this item be merged into one backlog item at design, or stay two items with
   one design document?

## What was checked, and what was not

Run on develop at `63fdfbdd`: `plan_status.chunk_proposal` and `chunk_states` over the four
fixtures in the table, in all three modes. Read: `_deliverable_chunks`, `_touches`,
`chunk_states`, `retraction_target`, `_cmd_plan_retract`, `critic_consolidate._proposed_chunks`
(the `verify-resolutions` branch), `critic_mode.declares_boundary_cumulative` and
`boundary_cumulative_still_owed`, and `planning.md` "Chunk state". Not run: a change fragment as
the sole-owner path (it takes the same path rule once its text is no longer the `plan new` stub,
but the fixture used a plain doc), the `verify-resolutions` inheritance, and any end-to-end
`critic-begin` dispatch. Not known: which path certified chunk 06 in the reporting repo. The
certifying fact's `chunks` and `chunks_proposed`, and chunk 06's Deliverables, would confirm it;
the requirements do not wait on them.
