---
artifact: build-plan
version: 2
scope: phase-blind-real-data-guards
depends_on:
  - artifact: operational-spec
last_validated: 2026-08-10
---

## Requirements Confidence

**Level:** High

**Why:** The failure is fully characterised — six named tests, reproduced locally, each
traced to one shared cause. Problem, success and scope are each one sentence, and the
release runbook that produced the state is checked in and readable.

**Open assumptions / unknowns:** none material.

**What would raise confidence:** N/A

## Status

- [ ] Chunk 01: Make the six real-data guards phase-independent
Context: Plan written 2026-08-10 on `fix/phase-blind-real-data-guards`, cut from
`develop` at `cf97bf82` (which carries the unpushed v3.3.0 release prep). Nothing built
yet. The six failures reproduce on this branch; that is the baseline.

## Problem

Six tests fail on `develop` after the v3.3.0 release prep ran:

```
test_change_log.py::TestAgainstTheRealChangeLog
  ::test_release_tags_partition_into_released_and_pending
  ::test_every_log_scope_that_resolves_maps_to_a_plan_declaring_it
test_plan_index.py::TestAgainstTheRealArtifactsDirectory
  ::test_the_real_tree_resolves_many_scopes_and_no_duplicates
  ::test_this_branchs_own_scope_resolves
  ::test_a_live_plan_still_beats_its_archived_namesake
  ::test_archiving_a_real_plan_removes_it_from_the_live_map
```

**Root cause — one cause, six symptoms.** Every one of these grades the repo's *own*
live state, and every one encodes **"this repo is mid-development"** as an invariant it
never names. Runbook steps 3 and 11 falsify that simultaneously and by design: step 3
tags every change-log entry `release=v3.3.0`, so the release-pending set is empty; step
11 archives every shipped plan, so `build_scope_to_plan_map()` over the live tree returns
`{}`. A repo that has just shipped everything is a legitimate state these tests cannot
describe.

Nothing shipped to consumers is wrong. `plugin/` is correct; all six live in
`TestAgainstTheReal*` classes that grade repo *data*, not plugin *behaviour*. But
`.github/workflows/tests.yml` runs on every push with no path filters, so this blocks
pushing `develop` and would turn the release surface on `main` red.

**Why the guards are not simply wrong.** They were hardened by an earlier review round
for a real reason — *"an empty intersection would make the loop below pass while
asserting nothing, which is the failure this whole class was rewritten to stop."*
Relaxing the non-emptiness assertions would restore exactly the vacuity they were
written to prevent. **Do not weaken them** (Principle 1).

## Success

`python3 -m pytest tests/` is green on this branch — with the v3.3.0 release prep in
history — and stays green on both sides of a release boundary, without any assertion
having lost teeth.

## Out Of Scope

- The release itself. Phase 1 step 13 onward resumes *after* this lands.
- Any change to `plugin/lib/plan_index.py`, `plugin/lib/change_log.py`, or any other
  production module. The defect is in the tests' corpus selection, not in the resolvers.
- The other ~30 `TestAgainstTheReal*`-style assertions elsewhere in the suite that
  happen to be phase-independent already.
- Adding a lint or gate that detects phase-dependent tests generally. Worth considering;
  belongs in the backlog, not here (Principle 12).

## Design

Three distinct repairs, chosen per test by what each one is actually guarding:

**A. Read the phase-independent corpus** (`include_archived=True`). Applies to
`test_the_real_tree_resolves_many_scopes_and_no_duplicates` and
`test_every_log_scope_that_resolves_maps_to_a_plan_declaring_it`. An archived plan is
still a real plan with real frontmatter, and the archive only ever grows — 76 plans
today against 0 live. This is a *strictly larger and strictly more discriminating*
corpus than the one it replaces, so the assertions get stronger, not weaker. The live
tree keeps its own duplicate-scope check, which is meaningful at any size including zero.

**B. Construct the live plan by perturbing a copy.** Applies to
`test_a_live_plan_still_beats_its_archived_namesake` and
`test_archiving_a_real_plan_removes_it_from_the_live_map`. Both need a live plan to
manipulate, and today both borrow whichever one the current branch happens to be
building — which is why both broke. Promoting a real archived plan into the live tree
of a `tmp_path` copy supplies one unconditionally. This makes the first test *stronger*
in particular: the real tree contains no live/archived namesake collision, so the
existing assertion passes vacuously on a scope that is merely live; constructing the
collision is what makes live-wins capable of failing.

**C. Name the phase, and cross-check it.** Applies to
`test_this_branchs_own_scope_resolves` and
`test_release_tags_partition_into_released_and_pending` — the two whose subject genuinely
*is* work in flight.

- The first hardcodes `governance-artifact-lifecycle`, so it needs editing every branch
  and breaks the moment that plan is archived. Read the scope from
  `project-state.yaml`'s `active_build_plan` pointer instead — the same pointer the
  three governance paths it names actually resolve through — and skip with an explicit
  reason when the pointer is null. Self-updating, and it grades the real mechanism.
- The second is the hard one: "there is something to cut" is *false* immediately after
  a release and that is not a bug. Keep `released` non-empty (a broken `release=` reader
  still fails). Assert the partition is total and disjoint. Then require pending-empty
  to be *explained*: every tagged entry carries a release, and the newest release tag
  equals `plugin/VERSION`. A repo mid-cycle fails that and must show pending entries; a
  repo that just cut passes it. Drift — entries tagged to a version the repo no longer
  claims — fails both ways, which is the fact worth catching.

## Build Chunks

### Chunk 01: Make the six real-data guards phase-independent

- **Description:** Apply repairs A, B and C so the six guards grade a corpus that does
  not empty at a release boundary, and prove the fix by running the suite against both
  phases of the repo.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/runbooks/cut-and-publish-a-plugin-release.md`
  (steps 3 and 11 — the two that falsify the invariants)
- **Deliverables:** `tests/test_plan_index.py`, `tests/test_change_log.py`
- **Tests:** the six themselves are the deliverable. Each must be shown capable of
  failing — verified by perturbing the corpus, not by inspection.
- **Acceptance criteria:**
  1. `python3 -m pytest tests/` is fully green on this branch.
  2. Each of the six still fails when its real subject is broken (demonstrated, not
     asserted): a mangled frontmatter scope, a mistagged release, a defeated live-wins
     ordering.
  3. `git stash`-ing the branch back to a *pre*-release-prep tree (`git worktree` at
     `origin/develop`) leaves all six green there too — the whole point is that they
     pass in both phases.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

## Verification Strategy

Two runs, one per phase: this branch (post-release-prep, everything archived and tagged)
and a worktree at `origin/develop` (pre-release-prep, plans live and entries pending).
A guard that is genuinely phase-independent is green in both; one that merely traded one
phase-dependence for the other is caught by the second run. That second run is the
acceptance criterion the first one cannot supply.
