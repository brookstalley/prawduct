---
artifact: release-plan
version: 1
release: v3.3.1
last_validated: 2026-08-11
---

# Release plan — v3.3.1

A patch release cut same-day on v3.3.0, carrying one fix. One scope, shipping; nothing withheld.

## Release classification

| Scope | Disposition | Blocker |
|---|---|---|
| plan-backfill-completeness | ships | |

**Owner decision 2026-08-11: cut immediately as a patch.** Requested in-session — *"we must fix the
new issue and get a release out"* — after the defect was observed landing in a consumer repo rather
than inferred from code.

## Why a patch and not a minor

The change makes `plan-backfill` **refuse** work it previously proposed. It adds no capability, no
config surface and no persisted format, and it changes no behaviour an adopter's own code depends
on. `archive-plan` — the explicit route, and the one a human invokes — is byte-unchanged.

The honest counter-argument, recorded rather than resolved away: this **does** change what a
consumer sees at a release cut. A repo whose plans carry unticked chunks, or no `## Status` roster
at all, will find `plan-backfill` proposing fewer plans than it did on v3.3.0, and reporting them
under `blocked` instead. That is a visible behaviour change in a governance tool. It stays a patch
because the new behaviour is *refusal* — the failure direction is a plan left live that a human can
still archive in one command, versus v3.3.0's direction of unbuilt work silently recorded as
shipped. Conservative versioning plus a strictly safer failure direction lands on patch.

## What ships

`plan-backfill` no longer proposes archiving a plan whose own `## Status` does not evidence
completion. Selection was by change-log `release=` tag on a scope, never by the plan's checkboxes —
deliberately, per `backfill()`'s docstring — which is sound only when scope and plan finish
together. They do not when a scope ships partially.

Observed, not theorised: hallucinote's `plans/TOUR/build-plan.md` was archived as
`lifecycle: completed`, `released_in: v1.8.0` with chunks C1 and D1 unbuilt and still live work.
That product had declined the identical proposal at its two previous cuts and recorded the decline
both times. Filed as #634.

Three states now: all ticked → archive; some unticked → blocked, naming the chunks; **no readable
`## Status` roster → blocked**, because an absent roster reads as `[]` exactly like a finished plan.

## Consumer impact

- **Nothing to migrate.** No persisted format, no config key, no state file.
- **Rollback is clean** in both directions: reverting restores the v3.3.0 selection, which is
  permissive. Nothing written under v3.3.1 needs unwinding, because the change only ever *withholds*
  a move.
- **A repo mid-release-cut will see a shorter `shipped` list**, with the withheld plans under
  `blocked` and the blocking chunk named. That is the intended difference, and the remedy is in the
  message: tick the chunks, or archive explicitly.

## Verification recorded by hand

- Suite green at the commit under review: **4336 passed, 0 failed, 11 skipped** (`test-status`
  exit 0).
- The defect reproduced end-to-end against the live consumer tree before the fix
  (`plan-backfill --json` proposing TOUR under `shipped`), and **cannot be re-run now** — that tree
  moved when the incident landed and TOUR left the live set. The regression is therefore held by
  fixtures, not by that reproduction: `test_unticked_boxes_block_the_AUTOMATIC_sweep`,
  `test_a_plan_with_no_status_roster_is_refused_not_passed`, and
  `test_the_explicit_route_still_archives_an_unfinished_plan`.
- One existing assertion was **inverted, not weakened** — `test_unticked_boxes_do_not_block_archiving`.
  Its rationale (dead plans must not live forever) still binds and is now served by the explicit
  route, which the third test above pins precisely so the block cannot become a trap.
