---
artifact: build-plan
version: 2
scope: gate-as-dispatcher
depends_on:
  - artifact: gate-as-dispatcher-requirements
governed_by:
  - artifact: architecture
    dispositions:
      - "Authority fails closed; advice fails soft → conforms — the refusal produces no merge verdict, and every uncomputable input (diff failure, unreadable tree, missing store) dispatches"
      - "An independent reviewer never mutates the session it reviews → inapplicable because this changes whether a review starts, never what a reviewer may touch"
      - "Goals and verification bind; prescribed method is advice → conforms — the verification structure is unchanged; only the decision to spend a round moves"
  - artifact: nonfunctional-requirements
    dispositions:
      - "Review wall-clock is P0: cost = unit-cost x run-count → conforms — this is a run-count lever, the one the norm names first"
      - "Proportionality ratchets both ways; adding a control names its expected yield and emits it observably → conforms — the mirror obligation for removing a firing is met by the requirements §1 measurement plus Chunk 02's refusal telemetry"
  - artifact: data-model
    dispositions:
      - "Governance verdicts are computed from the append-only fact ledger, never mutable model-written state → conforms — the predicate reads the interval diff and the store; no model writes to the decision path"
      - "Derived views are disposable and never authoritative → conforms — nothing here reads .critic-findings.json"
last_validated: 2026-08-06
---

## Requirements Confidence

**Level:** High

**Why:** The predicate was derived from measurement, not intuition, and validated retroactively
against seven real review rounds on a merged branch — it refuses exactly rounds 3/4/5 and dispatches
1/2/6/7. Problem, success criteria and scope are each statable in one sentence
(`gate-as-dispatcher-requirements.md` §1, §3, §5).

**Open assumptions / unknowns:** carried from requirements §8 —
`[ASSUMPTION: exit code 3 signals "no review needed" | MED impact | user can override]`,
`[ASSUMPTION: override spelled --force | LOW impact | user can rename]`,
`[ASSUMPTION: the rule is mode-uniform, not verify-resolutions-only | MED impact | user can narrow]`.
One genuine unknown — requirements §9, the `learnings-detail.md` CRT-7M2D vs `METADATA_PREFIXES`
contradiction over whether `change-log.md` is judgeable. Chunk 01 step 0 closes it before anything
leans on the predicate.

**What would raise confidence:** N/A — §9 is a step, not a gap.

## Status

- [x] Chunk 01: The dispatcher asks the gate before it spends a reviewer
- [ ] Chunk 02: The refusal is observable, and the prose stops teaching the treadmill
Context: **Chunk 01 built and committed at `586ae1d`** (suite 3823 passed / 0 failed / 7 skipped).
Step 0 settled against the code by owner ruling: `change-log.md` is correctly non-judgeable, and
`learnings-detail.md`'s CRT-7M2D bullet was wrong on three of its five named files — corrected there.
The refusal is mutation-verified on both conjuncts, and the retroactive replay refuses exactly rounds
3/4/5 of `fix/backlog-import-title-boundary` while dispatching 1/2/6/7. Awaiting the `cumulative`
review before Chunk 02. Requirements in
`.prawduct/artifacts/gate-as-dispatcher-requirements.md` — read it first, it carries the
measurements, the safety argument, and the withdrawn layers. `active_build_plan` still points at
`artifacts/build-plan-critic-review-identity.md` and **must not be repointed** until the
`develop`→`main` release ships (gitflow rule, `methodology/planning.md` "Plan lifecycle"). Next:
Chunk 01 step 0.

## Verification Strategy

Tests carry most of this, but two things tests cannot say:

1. **Retroactive replay.** After Chunk 01, replay the predicate against the seven recorded rounds of
   `fix/backlog-import-title-boundary` (they are in `.git/prawduct/evidence.jsonl`) and confirm it
   refuses 3/4/5 and dispatches 1/2/6/7. This is the acceptance evidence for the whole plan — a
   predicate that cannot reproduce the split it was derived from is wrong regardless of unit tests.
2. **Live exercise.** Make a `.prawduct/`-only edit, run `/prawduct:critic verify-resolutions`, and
   watch it return in under a second with a readable message rather than spawning a reviewer. Then
   add one `.py` edit and watch the same command dispatch.

## Build Chunks

### Chunk 01: The dispatcher asks the gate before it spends a reviewer

- **Description:** Insert the refusal predicate into review dispatch. `begin_review` already derives
  `files_changed` uniformly and already calls `coverage_algebra.judgeable_files` a few lines later in
  `_derive_roster`, so the predicate is in scope at exactly the right point; and an empty-diff refusal
  already sits at that spot, giving the new refusal an existing shape to match. Refuse **iff** the
  interval holds no judgeable file **AND** no unresolved blocking finding exists that this review
  could resolve. Both conjuncts are load-bearing — dropping the second deadlocks the gate, because a
  `blocked` verdict's only remedy is the very `verify-resolutions` pass that would be refused.
- **Depends on:** none
- **Artifacts consumed:** `gate-as-dispatcher-requirements.md` §2 (the predicate), §3 (success
  criteria), §4 (the safety argument)
- **Deliverables:**
  - the predicate + refusal in `plugin/lib/critic_consolidate.py` (`begin_review`), returning a
    distinct status the CLI maps to a new exit code
  - exit-code 3 handling and the `--force` flag in `plugin/bin/prawduct-hook` (`cmd_critic_begin`)
  - `plugin/skills/critic/SKILL.md` reads exit 3 and reports "no review needed" instead of proceeding
  - new `tests/test_critic_dispatch_refusal.py`
- **Tests:** the adversarial set, because a skip-gate needs the most adversarial coverage — this is
  the explicit lesson of the retired PR trivial fast-path (recorded on `#292`), which shipped with
  none and was withdrawn. Each must be red-verified against the code that ships:
  - one judgeable file among 50 non-judgeable → **dispatches** (fails closed)
  - a governance-protected `.md` (`skills/`, `methodology/`, `templates/`, root `CLAUDE.md`) →
    judgeable → **dispatches**; this is the trap, since it is a `.md` that must not read as free
  - a free interval **with** an unresolved blocking finding → **dispatches** (the anti-deadlock case)
  - a free interval with a clean prior fact → **refuses** (rounds 3/4/5)
  - `tree_diff` returns `None` / unreadable tree / absent evidence store → **dispatches**
  - `--force` over a free interval → **dispatches**
  - refusal leaves no critic-active marker, no manifest, and no partial reset — a refusal must not
    disturb any state a real dispatch would
- **Acceptance criteria:** full suite green; the retroactive replay in Verification Strategy §1
  reproduces the 3/4/5 vs 1/2/6/7 split; `check-cumulative-critic` returns an identical verdict to
  today for a branch with and without the change (the refusal must not widen what can merge).
- **Done when:**
  0. Resolve requirements §9 — read `gitstate.METADATA_PREFIXES` and `coverage_algebra`
     against `learnings-detail.md`'s CRT-7M2D claim, decide which is correct, and correct the losing
     one. **Read the mechanism; do not assume the learning is stale because it is inconvenient.**
     Nothing else in this chunk may be built before this is settled.
  1. Acceptance criteria met and tests pass
  2. **Commit first**, then `/prawduct:critic cumulative`, and resolve blocking findings.
     <!-- Not the template's default order (review the dirty tree, then commit). `chunk`/`final`
          both diff HEAD against the WORKING tree, so on a clean tree their interval is empty and
          the dispatch is refused; only `cumulative` reads `merge-base...HEAD`, which is where
          committed work lives. Both chunks of this plan land in one PR, so `cumulative` is the
          right mode for each — and ordering it after the commit means the reviewed tree IS the
          commit's tree. Corrected 2026-08-06 after the first dispatch refused for exactly this. -->
  3. Chunk marked `[x]` in Status

### Chunk 02: The refusal is observable, and the prose stops teaching the treadmill

- **Description:** A silent skip is indistinguishable from a broken gate, and the governing norm
  ("proportionality ratchets both ways") requires the yield claim to stay falsifiable. Record each
  refusal so "how many rounds did this save, and did any of them turn out to be needed?" is a query,
  not a memory. Then fix the three prose surfaces that instruct the treadmill — these are
  governance-protected and therefore judgeable, so they are code for review purposes.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `gate-as-dispatcher-requirements.md` §7 (the prose surfaces), §4 (the
  proportionality norm)
- **Deliverables:**
  - refusal telemetry via the existing ledger path (`ledger-append`), carrying the interval and the
    free file list — enough to answer the yield question later
  - `plugin/skills/critic/review-protocol.md` — the `NEXT-ACTION` text: *ask the gate; review only if
    it reports uncovered*, replacing the unconditional "then run ONE verify-resolutions"
  - `plugin/lib/coverage.py` — `check-cumulative-critic`'s remedy text names the free-interval check
    before prescribing a review
  - `plugin/skills/pr/SKILL.md` — Step 2's sequencing paragraph, same correction
- **Tests:** a preference-style test pinning that the `NEXT-ACTION` text no longer prescribes an
  unconditional review round (the same shape as
  `tests/preferences/test_critic_skill_structure.py`); a test that a refusal appends exactly one
  ledger event and a dispatch appends none of that kind.
- **Acceptance criteria:** full suite green; a refusal is queryable from the ledger; no prose surface
  still instructs an unconditional post-fix review round.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## What this plan deliberately does not build

Recorded here so a later reader does not "restore" them (full reasoning in requirements §5):

- **Scoping the review payload to the judgeable subset** — withdrawn on evidence. Round 6 of the
  merged branch caught a change-log sentence asserting coverage the code did not have; a reviewer
  handed only the `.py` files could not have found it.
- **Taking prose review off the blocking path** — Chunk 01 captures 100% of the measured waste, so
  this waits for evidence it is still needed.
- **Refusing when a prior fact already covers a judgeable interval** — strictly broader, unmeasured.
  Measure before building.
- **Any relaxation of `is_judgeable_path`** — already built and reverted once; see requirements §6.
