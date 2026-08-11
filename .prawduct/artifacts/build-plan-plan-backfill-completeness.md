---
artifact: build-plan
version: 1
scope: plan-backfill-completeness
governed_by:
  - artifact: data-model.md   # § Direction — the archival norm; its Retroactivity clause is the one this amends
    dispositions:
      - "AMENDED, with a recorded ruling (Ruled 2026-08-11) rather than a rewrite. The clause said
         checkbox state is 'explicitly not a precondition'; it now is one for the mechanical sweep
         and remains none for explicit archive-plan. The stated why — keep a model out of the write
         path — is preserved exactly: the new precondition is a deterministic count, and declining
         moves judgment to a human and OUT of the write path. The norm's own two-terminal-state
         reasoning supplies the escape hatch, so a declined plan is one command from `superseded`."
  - artifact: nonfunctional-requirements.md   # § Direction — a control that fires and catches nothing is removed by default
    dispositions:
      - "This ADDS a control rather than removing one, and it carries the evidence that norm asks
         for: a live incident (hallucinote TOUR, 2026-08-11) plus two recorded declines at earlier
         cuts. The refusal names the chunks, so its yield is readable rather than asserted."
last_validated: 2026-08-11
---

# Build plan — the plan sweep stops recording unbuilt chunks as shipped

**Scope:** `plan-backfill-completeness`
**Size:** small · **Type:** bugfix
**Critic mode:** final
**Parent requirement:** [#634](https://github.com/brookstalley/prawduct/issues/634)

**Written after the code, and saying so.** `building.md` scales a small bugfix to
*understand → build → verify*, with no build-plan step, which is how this shipped without one. The
release gate then refused the cut — *"work is shipping with no plan describing it"* — because
release accounting asks a different question from build governance: every release-pending scope must
be describable. This plan is that description. The requirement itself was never missing; #634 was
filed before any code was written.

## Problem (observable)

`plan-backfill` archived hallucinote's `plans/TOUR/build-plan.md` as `lifecycle: completed`,
`released_in: v1.8.0`, with chunks C1 and D1 unticked and still live work. Two unbuilt chunks were
recorded as shipped.

Root cause: `survey()` selects plans by the change log's `release=` tag on a **scope**, and
`backfill()`'s docstring stated that the plan's own checkboxes *"are not consulted, and deliberately
so"* — the change-log release being taken as sufficient evidence the work shipped. That premise
holds only when scope and plan finish together. A scope can ship partially: `scope=tour` released in
v1.8.0 while two of seven chunks stayed unbuilt.

The affected product declined the identical proposal at its two previous cuts and recorded the
decline in its release plan both times. The third went through. A judgement call the tooling re-asks
every release is one the tooling eventually wins.

## Success

`plan-backfill` never proposes a plan whose own Status does not evidence completion, and says which
chunk stopped it. Explicit `archive-plan` is unchanged.

## Out of scope (declared, not dropped)

- **Stamping incompleteness into the archived frontmatter** (e.g. `unbuilt_at_archive:`) so the
  explicit route records *how* the work ended. Additive and probably right, but it is a new record
  field on a release-day patch, and the block already prevents the silent case.
- **Repairing the hallucinote incident.** Another session owns that tree; it was messaged with the
  two revert commands and confirmed C1/D1 genuinely unbuilt.
- **The `lifecycle-repair` migration hallucinote has not run.** Unrelated, and the owner's to run.

## Chunks

### Chunk 01: completeness gates the automatic sweep, not the explicit one

`survey()` asks a completeness predicate alongside `plan_archive.refusal_reason`; `backfill()`
archives `survey()["shipped"]`, so preview and write cannot disagree. `buildplan_refs` gains
`incompleteness_reason()` — the finished sentence, not the walker, per that module's stated rule.

Three states, because `unticked_chunk_items` alone has a hole:
- items, all ticked → archive
- items, some unticked → blocked, **naming the chunks**
- no readable `## Status` roster → blocked; `[]` there is silence, not completion

**Placement is the load-bearing decision.** The check is in `plan_backfill`, NOT in
`plan_archive.refusal_reason`, which both callers share. `archive-plan <path>` is a human asserting
the plan is done, and `plan_archive`'s docstring already records that an archived plan may carry
unticked boxes. Moving the check down would break deliberate archiving to fix the automatic kind —
and would turn the block into a trap, since the explicit route is what keeps dead plans from living
forever.

*Done when:* the three states are pinned by test; the inverted assertion carries its history and the
escape hatch is pinned beside it; `/prawduct:critic` passes with no unresolved blocking findings.

## Status

- [x] Chunk 01: completeness gates the automatic sweep, not the explicit one — built 2026-08-11

**Context:** Chunk 01 is complete; the suite is green at 4336 passed. This is a one-chunk plan, so
this closes it. Cutting as v3.3.1.
