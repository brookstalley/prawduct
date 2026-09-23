---
artifact: build-plan
version: 2
scope: suite-at-boundary
branch: feature/820-suite-at-boundary
depends_on:
  - artifact: delegation-and-verification-cost-discovery
  - artifact: kernel-redesign-discovery
  - artifact: nonfunctional-requirements
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review rigor is stage-keyed → conforms, and this plan is its consequence for verification: the inner stage stops treating a suite that has not run yet as a finding, and the boundary stage keeps it at full weight"
      - "review wall-clock is P0 → conforms: removes a suite run per chunk and the round a stale-suite finding rides in"
  - artifact: delegation-and-verification-cost-discovery
    dispositions:
      - "ruling 6, prawduct states the goal not the mechanism → conforms: the goal is 'the declared suite passes on the tree that ships'; when a project runs it more often is its own free-text row"
      - "ruling 7, testing guidance is qualitative, no framework vocabulary → conforms: no posture enum; the framework's default is stated by stage, a concept it already owns"
  - artifact: kernel-redesign-discovery
    dispositions:
      - "C8, the testing burden sits at entry to develop → conforms: this makes the methodology say what C8 already ruled"
partition: serial — one prose surface set, one agent
last_validated: 2026-09-23
---

# Build plan — the declared suite runs at the boundary, not at every chunk (#820)

## Requirements Confidence

**Level:** High. Owner decision 2026-09-23 (recorded on #820): derive from stage, no new vocabulary.

**Problem:** `building.md` says the declared suite runs at Verify, so every chunk (and, before #704,
every delegate) pays a full run on a tree that changes again within the hour. The inner-stage
Critic then reports stale evidence as a finding when the suite simply has not run yet.

**Success:** a builder following `building.md` on a multi-chunk plan runs the inner-loop proof at
each chunk and the declared suite once, before the boundary review and PR; a chunk review reports
no finding for evidence that is merely not yet recorded; failing evidence stays BLOCKING at every
stage; a project wanting per-chunk runs says so in `Inner-loop verification` and is followed.

**Out of scope:** the session-start baseline run; gates (the PR gate's evidence requirement is
unchanged); a posture enum (declined).

**Surfaces (enumerated 2026-09-23 by two vocabularies, "at Verify" and "full/whole/declared suite"):**
`plugin/methodology/building.md` (ceiling paragraph, Verify bullet), `plugin/templates/project-preferences.md`
(`Inner-loop verification` row), `plugin/skills/critic/goals-1-3.md` and `review-protocol.md`
(stale → WARNING at inner stage), `plugin/skills/critic/SKILL.md` step 5, token-budget tests on
each, the change-log (a default change every consumer inherits). **Found while building:** two more
carriers in `plugin/skills/doctor/SKILL.md` (the row-drafting guidance, twice in one file), which the
first sweep's truncated output hid; `tests/test_suite_at_boundary.py` now pins every carrier and the
retired wording's absence.

`[DECISION: declared token raises — building.md 5055→5072, goals-1-3.md 2652→2665,
review-protocol.md 4392→4399, and the reviewer-payload sums they feed (single-pass-inner +13,
single-pass-full +7, dispatched +7; chunk and verify-resolutions per-mode loads +13), priced against
the per-chunk suite run the inner reviewer no longer recommends | each sentence is the one place its reader meets the rule, compressed in
place first, and there was no duplication to pay from; a default every consumer inherits is owed at
each surface | user can veto/override]`

## Chunk 1: move the suite to the boundary

**Delivers:** the prose above; the inner-stage reviewer reads a stale or missing record as the
normal in-flight state (no finding) while failures stay BLOCKING; the boundary reviewer keeps
stale → WARNING.

**Done when:** each changed sentence pinned by its own assertion; token budgets reconciled (pay in
place or declare a raise with its reason); targeted tests green; one `/prawduct:critic`.

## Status

- [ ] Chunk 1: move the suite to the boundary
