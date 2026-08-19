---
artifact: build-plan
version: 2
scope: governance-surface-dedup
branch: fix/governance-surface-dedup
depends_on: []
governed_by:
  - artifact: architecture
    dispositions:
      - "every fact has one home; every other mention is a reference to it → conforms — this plan IS that norm applied to the injected surfaces; it deletes second authoritative statements rather than reconciling them"
      - "goals and verification bind; prescribed method is advice → DEPARTURE, recorded. Chunk 01's Deliverables prescribed one set ('CLAUDE.md + both digest variants'). Built instead as two load-event shapes (`framework`, `product`). [DECISION: two session shapes rather than one flat set | a flat set sums `session-digest.md` and `session-digest-slim.md`, which `hooks/digest.py` selects between — they are never both injected, so their sum is a total no session ever pays, and a ceiling on it would govern a fiction. Two shapes each measure what one real session actually loads. The norm blesses a better route found while reading the code, provided the why is recorded; this is that record | user can veto/override]"
      - "authority fails closed; advice fails soft → conforms — this control is authority (a hard suite failure) and fails closed; the owner ruling that made it hard rather than advisory is recorded against the NFR size norm below"
      - "an independent reviewer never mutates the session it reviews → inapplicable because this chunk adds no reviewer code and no mutation site"
      - "local-first governance coordination, no network or third-party runtime deps → conforms trivially — the assertion is pure stdlib reads of files already in the repo"
      - "the plugin writes nothing into a governed repo except its own state and the files it must reconcile → inapplicable for Chunk 01 (test-only); it BINDS Chunk 03, which edits this repo's `CLAUDE.md` — that file is named in the norm as one prawduct may reconcile, and Chunk 03 edits it as the framework repo's own content, not as a write into someone else's repo"
      - "Python, but never specific to Python → inapplicable because the assertion measures framework prose payloads, not product code; it dispatches on no product language"
      - "prawduct guides and reviews, it never implements → inapplicable because this chunk adds no product code and no gate that duplicates a product's own tooling"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0; unit-cost is the reviewer's payload, per-mode and reducible → conforms — Chunk 01 generalizes exactly this norm from reviewer payloads to every injected surface, grouping by load event because that is what 'what a given mode must load' already means"
      - "proportionality ratchets both ways — a new control names its expected yield AND emits it observably → conforms, and the obligation applies at birth (this control is added 2026-08-19, after the norm's dated 2026-07-29 boundary). **Expected yield:** it catches (a) growth in an already-budgeted injected file that nobody declared, and (b) a newly injectable digest variant that no shape budgets — the second is the defect that actually happened and went unseen. **How the yield is observable, which is the arm that usually fails:** a hard suite failure cannot be printed-and-forgotten the way a canary finding can — every firing forces an edit to `LAST_MEASURED_INJECTED_TOKENS`, and those edits are in `git log` with the commit that paid for them, so the control's firing history is queryable after the fact without building a new emission path. **What evidence would retire it:** a sustained period in which no firing ever named an unbudgeted variant AND every total edit was a deliberate declared change rather than a catch — at which point the set-membership half has stopped earning its place and the totals could fall back to the janitor's Norm Health sweep"
      - "state-file growth past its size threshold is advisory, never a hard block → inapplicable because this budgets SHIPPED PROSE PAYLOADS, not `.prawduct/` state files; the five existing per-file prose ceilings are already hard. Recorded rather than assumed because the norm's wording ('size threshold') would otherwise read as covering it. [DECISION: the total-footprint assertion is a HARD test failure | owner ruling 2026-08-19; an advisory would not have caught the defect this plan exists to fix, since nothing was blocked when the injected set grew | user can veto]"
last_validated: 2026-08-19
---

## Requirements Confidence

**Level:** Medium

**Why:** The problem, the mechanism and the measurements are established — five must-agree pins over the digest pair, a perverse size coupling, and a per-file budget regime that cannot see a newly added file. What is *not* measured is how far `CLAUDE.md` actually trims once the full digest is what this repo receives; the ~1,350-token estimate is section-level arithmetic, not an edit.

**Open assumptions / unknowns:**

- `[ASSUMPTION: session-digest.md's 139-token principles roster plus a pointer to docs/principles.md is an adequate replacement for CLAUDE.md's 695-token glossed roster IN THE FRAMEWORK REPO | HIGH impact | user can veto — if the glosses are load-bearing here, Chunk 03 finds ~600 fewer tokens and lands at token parity rather than a win]`
- `[ASSUMPTION: no product repo depends on session-digest-slim.md existing | MED impact | user can correct — digest.py already falls back to the full digest when the slim file is missing, so a stale plugin cache degrades gracefully; verified in read_digest's OSError path]`
- `[ASSUMPTION: the always-injected set is exactly CLAUDE.md + the selected digest | MED impact | user can correct — the subagent briefing is per-dispatch, not per-session, and is #652's scope, deliberately excluded here]`

**What would raise confidence:** Chunk 03's step 0 — do the CLAUDE.md trim as a measurement before committing to the ceiling number. That is why it is a step, not a promise.

## Scaffolding

No scaffolding. This plan edits existing shipped prose, one hook module, and their guarding tests; the suite and toolchain are unchanged.

### Verification Strategy

Each chunk's real verification is the suite plus a **re-measurement**, because the deliverable is a number as much as a change. Chunk 01 establishes the instrument; Chunks 02-04 are each verified by the instrument moving in the expected direction and by no pin losing its subject. For Chunk 03 additionally exercise the product path: run `plugin/hooks/digest.py` against both a framework repo and a product repo fixture and confirm each receives the intended digest — a deleted variant is exactly the kind of change a green suite can miss if only the framework path is exercised.

## Build Chunks

### Chunk 01: Total-injected-footprint assertion

- **Description:** The root cause of every instance in this plan: **every token budget here is asserted per-file, and a per-file ceiling cannot see a new file.** Adding `session-digest-slim.md` put ~928 tokens into every framework session with all five existing ceilings green. This chunk adds a total over a set defined by *when the cost is paid* — the always-injected surfaces — so growth by accretion fails loudly. Sets are grouped by load-event rather than weighted by importance: frequency is the honest weight and it is observable from `plugin/hooks/digest.py`, not assigned by opinion. Per-file ceilings are KEPT — they do local work this total cannot, and removing them would re-open the relocation incentive the 2026-08-05 owner rule closed.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/nonfunctional-requirements.md` § Direction (reviewer-payload norm), `.prawduct/artifacts/architecture.md` § Direction (one home per fact)
- **Deliverables:** a total-footprint assertion in `tests/test_v5_methodology.py` following the existing `LAST_MEASURED_TOKENS` precedent — a measured total plus a hard ceiling, whose failure message carries the number to write so the figure is never re-derived by hand; the set enumerated explicitly (`CLAUDE.md` + both digest variants, since either may be the injected one) with a comment naming why membership is by load-event
- **Tests:** the assertion itself, plus a test that the set is non-empty and that adding a file to the injected set without updating the total fails (the defect this exists to catch — assert the direction, not only the number)
- **Acceptance criteria:** suite green; the new assertion passes at today's measured total; temporarily adding a dummy file to the injected set turns it red
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: Collapse the standing block to its carriers

- **Description:** `plugin/methodology/building.md` restates the whole three-label standing-block shape while `plugin/methodology/reflection.md` is canonical AND the injected digest carries it unconditionally — so building.md's copy is redundant *for its own reader*. Only its last clause is load-bearing: it ties `SAFE TO CLEAR` to building.md's own chunk-close steps 1-7. Cut the shape, keep the pointer and that binding. Then narrow `test_standing_block_is_on_every_surface_that_claims_it` to the surviving carriers, replacing its docstring's "unfunding" rationale — an artifact of relocation accounting the 2026-08-05 owner rule disavowed — with what it now guards: **coverage**. No ceiling raise is needed; cutting makes building.md smaller.
- **Depends on:** Chunk 01
- **Artifacts consumed:** none
- **Deliverables:** trimmed standing-block section in `plugin/methodology/building.md`; narrowed pin and rewritten docstring in `tests/test_v5_methodology.py`; updated `LAST_MEASURED_TOKENS` entry for building.md
- **Tests:** the narrowed pin (positive assertion: the rule is present on each surviving carrier); a paired positive assertion that building.md still binds the clear verdict to its steps 1-7, so the negative "no longer restates the shape" cannot pass by deleting too much
- **Acceptance criteria:** suite green; building.md's measured tokens fall; the standing-block rule still reaches a reader who opens only building.md, via pointer plus the injected digest
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: Retire the slim digest and trim CLAUDE.md

- **Description:** The largest instance and the one that motivated the plan. `session-digest-slim.md` exists because, in the framework repo, the full digest duplicated 40-50% of the always-loaded `CLAUDE.md` — but the fix was applied to the SHIPPED artifact rather than the LOCAL one, making the cost permanent and framework-wide to serve exactly one repository. This chunk reverses that: delete the slim variant, let this repo receive the full digest like every product, and trim `CLAUDE.md` to what the digest does not carry. The two halves are **atomic** — deleting the variant without trimming re-creates the duplication it was built to fix, and trimming first opens a gap in neither surface. Surfaces touched, enumerated so the size is visible: `plugin/methodology/session-digest-slim.md` (deleted), `plugin/hooks/digest.py` (slim branch and its fallback), `CLAUDE.md`, and five pins across `tests/test_v5_methodology.py`, `tests/test_cutover_prose_coherence.py`, `tests/test_plugin_methodology_digest.py` — including deleting `test_slim_budget_at_most_half_of_full`, whose ratio made shrinking the full digest tighten the slim ceiling.
- **Depends on:** Chunk 02
- **Artifacts consumed:** `.prawduct/artifacts/architecture.md` § Direction
- **Deliverables:** `session-digest-slim.md` deleted; `plugin/hooks/digest.py` simplified to one digest (with `is_framework_repo` retained only if other callers need it — check before deleting); `CLAUDE.md` trimmed, its Principles section reduced to a pointer at the roster the digest injects; the five digest-pair pins collapsed to single-surface assertions; the ratio test deleted; the Chunk 01 total re-measured
- **Tests:** existing pins narrowed to the surviving surface; a positive assertion per collapsed pin that the rule still reaches the injected surface; a product-path test that a non-framework repo still receives the full digest unchanged
- **Acceptance criteria:** suite green; a framework-repo fixture and a product-repo fixture each receive the intended digest; the Chunk 01 total falls; no rule that was pinned on the slim variant is now unpinned
- **Type:** code
- **Done when:**
  0. Measure — perform the CLAUDE.md trim and record the actual token delta BEFORE fixing the new ceiling, so the number is measured rather than predicted (this is what "Medium" confidence buys back)
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: A findings-only turn is not safe to clear

- **Description:** The original ask (backlog **#683**), landing last because Chunks 02-03 are what make it cheap — it now edits two carriers instead of four. The standing-block spec defines `SAFE TO CLEAR` by disk and process state, so a turn whose only output is analysis in the conversation reads as safe to clear when clearing destroys the entire output. Encode: a findings-only turn must persist its findings to `.prawduct/.handoff-notes.md` before claiming `SAFE TO CLEAR`, and a `SAFE TO CLEAR` whose stated reason cites the message itself contradicts itself. Per the learnings rule that a deliverable of INSTRUCTIONS needs at least one guardrail modelling the READER — size and word-presence tests all pass while an instruction has no effect — the pin here asserts the rule's *discriminating* content, not merely that a phrase appears.
- **Depends on:** Chunk 03
- **Artifacts consumed:** none
- **Deliverables:** the findings-only rule in `plugin/methodology/reflection.md` (canonical) and `plugin/methodology/session-digest.md` (injected); pin extended; `LAST_MEASURED_TOKENS` and the Chunk 01 total updated
- **Tests:** the rule is present on both carriers and states the discriminating condition (findings-only ⇒ persist first), not just the phrase
- **Acceptance criteria:** suite green; the Chunk 01 total still under ceiling after the addition — which is the plan's own closing argument, since this addition is funded by the cuts rather than by a raise
- **Type:** doc-only
- **Critic mode:** cumulative
- **Carried coverage — read before running this chunk's review:** Chunk 01's `chunk` review anchored its PRE-commit working tree; the `ast`-based extraction in `test_every_injectable_digest_is_budgeted` was written AFTER that review, so the committed tree at `2ebfa3b8` carries logic no reviewer has seen. A `verify-resolutions` round was deliberately NOT run for it: this chunk's cumulative pass spans `merge-base...HEAD` and is its first real review, so a round then would have bought coverage this one already schedules — the fix-churn round #167 exists to refuse. Recorded here rather than assumed, because an unrecorded deferral is a drop.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Descoped

Two candidates were investigated and **deliberately dropped** — recorded so they are not re-proposed:

- **`goals-1-3.md` vs `critic/review-protocol.md`** (26 of 88 lines ≥75% duplicate, ~1,344 tokens). Not accidental redundancy: `plugin/skills/critic/SKILL.md` records it as a measured payload split — *"Loading the seven-goal protocol to run three is the payload this split removes — measured, `chunk` missed its 1-2 min target in 30 of 30 recorded runs."* Only ONE of the two files is read per review, so the duplication costs **zero runtime tokens**. It is a maintenance cost, and `review-cycle.md` already pins the two to agree.
- **`critic/review-protocol.md` vs `pr/review-protocol.md`** (2 lines, 458 chars). Same reasoning, an order of magnitude smaller.

Also out of scope and ranked **above** this whole plan by owner ruling: **#652**, role-scoping the ~23k-token `.prawduct/.subagent-briefing.md`. This plan saves single-digit hundreds of tokens per session; #652 saves ~100k per coordinator review.

## Status

- [x] Chunk 01: Total-injected-footprint assertion
- [x] Chunk 02: Collapse the standing block to its carriers
- [ ] Chunk 03: Retire the slim digest and trim CLAUDE.md
- [ ] Chunk 04: A findings-only turn is not safe to clear
Context: Chunks 01-02 shipped 2026-08-19 on `fix/governance-surface-dedup`. Chunk 02 = `db877c35` (trim + narrowed pin + paired positive test + ceiling ratchet 4810 -> 4730) and `865b2a99` (change-log). `building.md` 4806 -> 4720 est. tokens. Critic `chunk` (`rev-20260819T043045Z-3b243e8b`): 0 blocking, 1 warning (R-1 unratcheted ceiling -- FIXED in the same commit), 1 note (R-2 change-log outside the manifest -- ACCEPTed, non-judgeable path). `verify-resolutions` (`rev-20260819T044054Z-b0e58371`) confirmed R-1 `fixed` with 0 new findings, so unlike Chunk 01 this chunk carries NO uncovered delta into Chunk 04. Suite green, 4806 passed / 10 skipped, evidence current. One inert clause to fix while Chunk 03 is already editing `tests/test_v5_methodology.py`: the `LAST_MEASURED_TOKENS` comment at ~line 108 still says the freed headroom "is not a budget to spend", written when 90 tokens were free -- 10 are now and the ceiling enforces it structurally, so the clause narrates a condition that no longer obtains (Critic observation, ACCEPTed as not worth its own commit). Next: Chunk 03, which opens on the HIGH-impact roster assumption the owner may want to weigh in on first -- its step 0 measures the CLAUDE.md trim before fixing the new ceiling.
