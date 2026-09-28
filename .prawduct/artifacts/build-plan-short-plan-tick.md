---
artifact: build-plan
version: 1
scope: short-plan-tick
branch: fix/short-plan-tick-deadlock
partition: serial — one chunk, five small files
depends_on:
  - artifact: build-plan-opus-55-w1-always-on
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review rigor is stage-keyed → conforms: the fix restores the boundary review a short plan owes; it adds no review and removes none"
      - "review wall-clock is P0 → conforms: inference reaches `cumulative` without an explicit override, saving a wasted dispatch that answers `deferred`"
  - artifact: architecture
    dispositions:
      - "every fact has one home → conforms: the tick-at-commit rule is stated once, in planning.md (the tick definition and the short-plan bullet beside it); the digest and the deferral rationale restate only the trigger. It stays out of review-cycle.md because every reviewer loads that file and this is builder guidance"
      - "goals and verification bind; prescribed method is advice → conforms: the tick rule is a definition the gates read, not method"
---

# Build Plan: short-plan tick deadlock

## Problem

On a short plan (at most 3 chunks, no risk surface), no chunk before the last gets a review of its
own; the boundary `cumulative` is every chunk's review. Two rules then contradict each other:

- **The tick rule** (digest, `planning.md`) says tick a box only after its chunk's review. A
  deferred chunk has no review until the boundary, so a builder who follows the rule leaves every
  box unticked.
- **The inference** (`critic_mode._mid_plan_start`) counts 2 or more unticked boxes as mid-plan.
  On a short plan, mid-plan answers `deferred`, so `cumulative` is never inferred.

The deferral rationale also says `cumulative` is "inferred once the last chunk is committed". The
predicate reads ticks, not commits, so that claim is false. W1 hit this on 2026-09-28 and had to
dispatch `cumulative` explicitly. The code was built for ticks at commit: the test fixture lands
each chunk's tick in its own commit. Only the prose disagrees.

## Success

- A deferred chunk's box is ticked when its chunk is committed. Only the last box waits for the
  boundary review. This is stated once, in `planning.md`, where ticks are defined, and the
  digest's tick bullet agrees with it.
- The deferral rationale tells the builder to tick the box and says what the inference actually
  counts.
- A test pins that the rationale names the tick. A second test pins the shape of the deadlock: all
  chunks committed, none ticked, a clean tree. There the answer is still `deferred`, but its
  rationale now names the remedy.

## Out of scope

- Changing the inference. Git cannot tell "committed, not ticked" apart from "not built yet", so
  ticks remain the signal.

## Requirements Confidence: High

The owner confirmed the direction in session on 2026-09-28: tick deferred chunks at commit, with
the last box waiting for the cumulative. The alternative was to change the inference and leave the
rule alone. It was rejected because the Stop gate reads the same ticks: with every box unticked it
would only warn at session end, so a short plan could close without its boundary review.

## Status

- [ ] Chunk 01: the tick rule, the rationale, and their tests

## Chunk 01: the tick rule, the rationale, and their tests

**Type:** code
**Files:** `plugin/lib/critic_mode.py` (`_deferral_rationale`), `tests/test_short_plan_deferral.py`,
`plugin/methodology/planning.md`,
`plugin/methodology/session-digest.md`, `plugin/lib/buildplan_refs.py` (docstring), and the token
readings the suite reports.
**Done when:** the deadlock test's rationale names the tick. The suite passes. The cumulative
Critic review has run.
