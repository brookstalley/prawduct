---
artifact: build-plan
version: 2
scope: review-convergence
branch: feature/review-convergence
backlog: brookstalley/prawduct#724
depends_on:
  - artifact: review-cost-investigation-2026-09-19
  - artifact: review-loop-nontermination-diagnosis
  - artifact: build-plan-review-loop-termination
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0; cost = unit-cost × run-count, both levers → conforms: every chunk here attacks run-count, which is the lever `review-cost-decision` did not touch"
      - "proportionality ratchets both ways; a new control names its expected yield and emits it observably → engaged by Chunk 02, which adds a REFUSAL. Its expected yield is measured, not asserted: 56 of 114 September verify anchors carry a non-empty named set once observations count, against 20 without. `guard-refusal` facts already exist in this store (12 today), so its firings are queryable and it can be retired on evidence"
      - "state-file growth is an advisory, never a hard block → inapplicable"
      - "review rigor is stage-keyed → conforms; Chunk 02 refuses a dispatch and changes no severity"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms: Chunk 02 refuses BEFORE dispatch, and no reviewer write path changes"
      - "authority fails closed; advice fails soft → engaged and load-bearing. A refusal IS authority, so Chunk 02 must fail CLOSED: an unreadable anchor dispatches the review rather than refusing it, because a refusal computed from a degraded read would skip a round nobody judged"
      - "local-first; no third-party runtime dependency → conforms"
      - "the plugin writes nothing into a governed repo except its own state → conforms"
      - "prawduct is Python but never Python-specific → conforms"
      - "prawduct guides and reviews; it never implements → conforms"
      - "goals and verification bind; prescribed method is advice → engaged: Chunk 02 departs from `167-design.md`'s D3 as written, and the departure is recorded in the chunk rather than by amending that document"
      - "every fact has one home → conforms: Chunk 02 reuses `begin_review`'s already-resolved anchor rather than re-deriving one via `diagnose_fix_churn`'s lineage search, which is D1's whole argument"
  - artifact: data-model
    dispositions:
      - "verdicts computed from facts, no model in a fact's write path → conforms: the refusal is computed from stored findings and observations"
      - "facts immutable and append-only → conforms: Chunk 02 appends a `guard-refusal` fact, edits none"
      - "derived views never authoritative → engaged: `_prior_review_fact` reads `.critic-findings.json`'s `fact_id` POINTER and then reads the fact from the store, which is D7-legal (the view carries a pointer; the verdict comes from the fact). Chunk 02 must not start reading findings out of the view"
      - "a governance document reaches a terminal state, never deleted → conforms"
      - "backlog title rules on every write path → conforms"
      - "a fact from a newer schema is a loud block → inapplicable"
      - "two stores, two lifetimes → conforms"
      - "`backlog_service_repo` selects the authoritative store → inapplicable"
  - artifact: api-contract
    dispositions:
      - "exit codes are the contract, documented and consistent → ENGAGED, and the main external surface here: Chunk 02 adds exit 5 (`self-inflicted-refusal`), which `167-design.md` D4 argues for over reusing 3 or 4. The exit-code table and the skill's own row ship in the same chunk"
      - "additive-first evolution; existing exit-code meanings never repurposed → conforms: 5 is new; 3 and 4 keep their contracts, which is exactly D4's reasoning"
      - "whole-surface semantic versioning → conforms"
partition: >-
  Serial, coordinator only. Chunks 01 and 03 both edit `critic_consolidate.py` prose and code, and
  Chunk 02 edits `begin_review` in the same module; a delegate on any two would collide on that
  file. Chunk 01 additionally edits three files now under the reviewer-payload ceilings, so its
  declared raise has to be computed against whatever 02 and 03 leave.
last_validated: 2026-09-19
---

## Requirements Confidence

**Level:** High for Chunks 01–03, and they are the whole plan. #847/#694 is deliberately NOT a
chunk here — see "Deferred, with its reason" below.

**Why:** #167 has a complete technical design (`documentation/issues/167-design.md`, 2026-09-15)
with D1–D5, a mechanism, a test plan and a files-touched table. #640's fix exists as a finished
branch that was Critic-reviewed before it stranded. #851 was filed today from a live reproduction.
Every mechanism named below was read at its call site on 2026-09-19.

**Open assumptions / unknowns:**

- [ASSUMPTION: extending D3's `named` set to include the anchor's OWN observations is a scope
  correction to `167-design.md`, not a new decision requiring the owner | MED impact | user can
  veto]. The design's D3 explicitly deferred the empty-`named` case because *"no store field
  carries [observations] today"*. That premise went false in between: `review-loop-termination`
  Chunk 01 shipped observation recording, and observations carry `files`. Measured on this repo's
  store — September verify anchors with a non-empty `named` set: **20/114 findings-only, 56/114
  with observations**, against 139/186 (Jul) and 129/300 (Aug) before the demotion. So the
  extension restores the design's intended reach rather than widening it. Recorded as a departure
  in Chunk 02 rather than by amending `167-design.md`, per the norm that a decision is recorded
  where it is made.

**What would raise confidence:** N/A for what is planned.

## Status

- [ ] Chunk 01: Re-apply the `rule-unenforced` substitution (#640, stranded branch)
- [ ] Chunk 02: Refuse a verify pass anchored on a verify pass that found only its own churn (#167)
- [ ] Chunk 03: The cost lead knows an anchor makes the next edit cost a round (#851)
Context: Plan written 2026-09-19 on `feature/review-convergence`, cut from `develop` at 4f2911e6
(the `review-cost-decision` merge). Nothing built yet. Next: Chunk 01.

## Deferred, with its reason — #847 / #694 is not a chunk

**#847's stated direction is falsified and must not be built.** It proposes a class finding carry
its members as a structured list. **#199** (closed NOT_PLANNED, no closing comment) records an
agent running exactly that instance sweep and still missing four sites, two of them one line below
fixes it had just made; what converged was articulating the **generating rule**. **#694** carries
the better framing — a class finding states the closure PROPERTY, with any grep as a hint rather
than the criterion — and is open at `stage: design` with an explicit acceptance criterion that the
*actor* be decided.

**#199 also disqualifies the cheap fix**: the failure recurred four times under existing guidance,
which it calls evidence that adding prose to one actor's protocol is the intervention most likely
to fail again. So this needs a design pass that picks the actor on evidence — and **this session is
new evidence for the FIXER side**: three instances in one day, all fixer-side, all mine, one of
which made the file worse than leaving it alone (recorded as a rule in
`.claude/rules/learnings/reviews.md`). Building it inside this plan would be deriving a design
under build pressure, which is the trap the item itself names.

## Verification Strategy

Chunk 02 is a refusal, and a refusal is the one thing that cannot be verified by a passing test
alone: a guard that never fires and a guard that cannot fire are the same green. Each chunk
therefore carries a **positive control** — a fixture that MUST trip the guard — asserted alongside
the negative case, and Chunk 02 additionally re-measures its own yield against the real store so
the number in its docstring is derived rather than copied from this plan.

## Build Chunks

### Chunk 01: Re-apply the `rule-unenforced` substitution

- **Description:** #640 is CLOSED while its fix sits unmerged on `fix/reviewer-rule-over-instance`,
  verified 2026-09-19 (`rule-unenforced` appears nowhere on `develop`). When a written rule has no
  enforcer, a reviewer files ONE finding naming the rule and what would mechanize it, at the
  severity an instance would have carried, instead of one finding per occurrence. Substitution,
  never suppression. Re-applied onto this branch rather than merged: the source branch is 281
  commits behind and predates the learnings-v2 migration, so its `.prawduct/learnings*.md` edits
  have no destination.
- **Depends on:** none
- **Artifacts consumed:** the stranded branch's payload (`git diff` against its merge-base)
- **Deliverables:** the reviewer-facing rule in `plugin/agents/critic-reviewer.md`, its pointer in
  `plugin/skills/critic/review-cycle.md`, the PR-reviewer half in
  `plugin/skills/pr/review-protocol.md`, and `tests/test_control_yield_tokens.py` ported from the
  branch; the learnings entry re-authored into the area-file structure that replaced
  `learnings.md`, never copied from the branch's pre-migration copy
- **Tests:** the branch's own test file, ported and re-run; plus the reviewer-payload readings
  re-recorded, because all three prose files sit inside the routes Chunk 03 of the previous plan
  now bounds
- **Acceptance criteria:** `rule-unenforced` reaches every reviewer surface that can emit it,
  proven by grep over two vocabularies; the payload ceilings are ratcheted in this same commit with
  a declared reason that prices the SUM
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed and chunk marked `[x]` in Status

### Chunk 02: Refuse a verify pass anchored on a verify pass that found only its own churn

- **Description:** #167, built to `documentation/issues/167-design.md` D1–D5, with one recorded
  departure. `begin_review`'s `verify-resolutions` branch gains a refusal keyed on its
  already-resolved anchor: when that anchor is ITSELF a `verify-resolutions` fact, left zero
  unresolved blocking, and the new delta's judgeable files are a non-empty subset of the files the
  anchor's own items named — refuse with new exit 5, `self-inflicted-refusal`.
- **Depends on:** Chunk 01 (both edit `critic_consolidate.py`; serial per `partition:`)
- **Artifacts consumed:** `documentation/issues/167-design.md` D1–D5 and its Files-touched table
- **Deliverables:** the refusal in `plugin/lib/critic_consolidate.py`'s `begin_review`, placed
  after the free-interval check and before the round-budget check (D5); exit 5 added to the
  exit-code table in `.prawduct/artifacts/api-contract.md` and to the skill's own row in
  `plugin/skills/critic/SKILL.md`; a `guard-refusal` fact so the control's firings are queryable
- **[DECISION: D3's `named` set includes the anchor's OWN observations, not only its findings |
  engages the design's why rather than overriding it: D3 deferred this case because "no store field
  carries [observations] today", and that premise went false when `review-loop-termination` Chunk
  01 shipped observation recording. Since the inner stage demotes everything below BLOCKING into
  observations, findings-only leaves D3 matching 20 of 114 September anchors against 139/186 and
  129/300 before the demotion — the control would ship at a quarter of its designed reach.
  Including observations restores it to 56/114 | user can veto and ship findings-only]**
- **Tests:** the positive control first — an anchor that MUST be refused — then each conjunct
  mutated independently, because `A and B and C` reverted whole goes red on A's fixture while B and
  C stay unpinned; a first-verify-after-a-full-round fixture that must NOT be refused (D2's floor);
  an unreadable-anchor fixture that must DISPATCH, not refuse (fail closed the safe way); and the
  yield re-measured from the store rather than copied from this plan
- **Acceptance criteria:** exit 5 is reachable and distinct from 3 and 4; a first verify pass after
  any full round is never refused regardless of severity mix; a degraded anchor read dispatches
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed and chunk marked `[x]` in Status

### Chunk 03: The cost lead knows an anchor makes the next edit cost a round

- **Description:** #851, filed today from a live reproduction in the previous plan's own review.
  `cost_lead` prices judgeability via `commit_cost`, which is correct pre-anchor and wrong after a
  `verify-resolutions` pass has anchored the working tree: from then on ANY further edit opens a new
  delta needing its own pass, judgeable or not. The lead told me a batch was free; it bought a full
  round. Verify the #600 lineage the backlog dedup asserted before building on it.
- **Depends on:** Chunks 01–02
- **Artifacts consumed:** brookstalley/prawduct#851
- **Deliverables:** the anchor condition reaching `cost_lead`, computed by the caller as the module
  already does for `price_sentence` and `span`, so `cost_lead` stays a pure function of its
  arguments; the close says a further edit re-opens the delta and names the pass that closes it
- **Tests:** the anchored and un-anchored cases render different leads, with a positive control
  that the anchored case is reachable; the pure-function property preserved (no new git read inside
  `cost_lead`)
- **Acceptance criteria:** after a verify pass anchors the tree, the close no longer says a fix
  buys no extra round
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status
