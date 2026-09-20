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
      - "proportionality ratchets both ways; a new control names its expected yield and emits it observably → NO LONGER ENGAGED: the only new control here was Chunk 02, withdrawn 2026-09-20. The ratchet turned out to bite in the other direction — the control was withdrawn BECAUSE its measured yield was negative (it refuses a 300s pass and forces a 720s one), which is the norm working"
      - "state-file growth is an advisory, never a hard block → inapplicable"
      - "review rigor is stage-keyed → conforms; nothing remaining changes a severity"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms: no reviewer write path changes"
      - "authority fails closed; advice fails soft → THE NORM THAT KILLED CHUNK 02. A refusal is authority, but its evidence (`diagnose_fix_churn`, file-level by its own docstring: it rules out work in a file the review never saw, NOT new work written into one it named) is advisory strength. Chunk 02 made advice into authority without strengthening the evidence; the remedy was to withdraw it, not to add machinery letting weak evidence clear a gate"
      - "local-first; no third-party runtime dependency → conforms"
      - "the plugin writes nothing into a governed repo except its own state → conforms"
      - "prawduct is Python but never Python-specific → conforms"
      - "prawduct guides and reviews; it never implements → conforms"
      - "goals and verification bind; prescribed method is advice → moot; the departing chunk is withdrawn and `167-design.md` is left as it was"
      - "every fact has one home → VIOLATED BY CHUNK 02, found in review and fixed by withdrawal: `_anchor_named_files` became a SECOND answer to 'which files did that pass name', disagreeing with `diagnose_fix_churn` on whether observations count. Reusing the anchor was D1's argument and was honoured; the `named` predicate was the copy nobody noticed"
  - artifact: data-model
    dispositions:
      - "verdicts computed from facts, no model in a fact's write path → conforms: the refusal is computed from stored findings and observations"
      - "facts immutable and append-only → conforms; no fact kind is added or edited now that Chunk 02 is withdrawn"
      - "derived views never authoritative → moot; the reader that engaged it is withdrawn"
      - "a governance document reaches a terminal state, never deleted → conforms"
      - "backlog title rules on every write path → conforms"
      - "a fact from a newer schema is a loud block → inapplicable"
      - "two stores, two lifetimes → conforms"
      - "`backlog_service_repo` selects the authoritative store → inapplicable"
  - artifact: api-contract
    dispositions:
      - "exit codes are the contract, documented and consistent → conforms by reverting: exit 5 was added by Chunk 02 and is withdrawn with it, so the documented surface is unchanged from `develop` and 5 stays unallocated for whatever earns it"
      - "additive-first evolution; existing exit-code meanings never repurposed → conforms: 5 is new; 3 and 4 keep their contracts, which is exactly D4's reasoning"
      - "whole-surface semantic versioning → conforms"
partition: >-
  Serial, coordinator only. Chunks 01 and 03 both edit `critic_consolidate.py` prose and code, so a
  delegate on both would collide on that file. Chunk 01 additionally edits three files under the
  reviewer-payload ceilings, so its declared raise is computed against whatever 03 leaves.
  (Chunk 02 also edited `begin_review` in that module; withdrawn 2026-09-20.)
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

- ~~[ASSUMPTION: extending D3's `named` set to include the anchor's OWN observations is a scope
  correction to `167-design.md`]~~ — **MOOT 2026-09-20**, Chunk 02 withdrawn. The measurement
  behind it stands and is worth keeping for whoever picks #167 up: September verify anchors with a
  non-empty `named` set are **20/114 findings-only, 56/114 with observations**, against 139/186
  (Jul) and 129/300 (Aug) before the inner-stage demotion. What the assumption got wrong was not
  the reach but the DIRECTION — widening `named` widens how often a refusal fires, and each firing
  was net-negative. `167-design.md` is left unamended.

**What would raise confidence:** N/A for what is planned.

## Status

- [x] Chunk 01: Re-apply the `rule-unenforced` substitution (#640, stranded branch)
- [x] Chunk 03: The cost lead knows an anchor makes the next edit cost a round (#851)

Chunk 02 (#167, exit 5) was built, reviewed and then WITHDRAWN — see "Chunk 02 — WITHDRAWN after
review" below. It is deliberately absent from this list rather than unticked: nothing here is owed.

Context: Plan written 2026-09-19 on `feature/review-convergence`, cut from `develop` at 4f2911e6
(the `review-cost-decision` merge). Chunks 01 and 03 committed; Chunk 02 reverted 2026-09-20.
Next: the cumulative's remaining findings, then PR.

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

Each chunk carries a **positive control** — a fixture that MUST trip the guard — asserted
alongside the negative case, because a guard that never fires and a guard that cannot fire are the
same green.

That discipline was necessary and turned out not to be sufficient, which is this plan's main
lesson. Chunk 02's positive control did fire, on the predicate as specified; what no test asked was
what the CALLER pays immediately after the refusal. A control can be correct at its own boundary
and still be net-negative, and only pricing the forced fallback shows it — see "Chunk 02 — WITHDRAWN after review".

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
- **DESCOPED, explicitly (2026-09-20, closing a review note):** "every surface" means every surface
  that can emit it, and the single-pass `chunk` and `verify-resolutions` routes are deliberately
  NOT among them. `SKILL.md` routes both to `goals-1-3.md` and says "Read **nothing else**", so
  neither carries the rule and neither should: `goals-1-3.md` is under a standing trim-or-relocate
  rule, the inner stage demotes the target class into observations, and `verify-resolutions` rates
  new findings BLOCKING-only. The boundary is stated rather than assumed, which is all the note
  asked for — a criterion whose "every" has no written edge is one the next reader widens.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed and chunk marked `[x]` in Status

### Chunk 02 — WITHDRAWN after review (#167, exit 5)

Built as specified, reviewed, and reverted in full on 2026-09-20 (revert of `853be5d3`). Kept here
rather than deleted because the reason is the useful output of this plan, and because #167 is still
open: the next attempt should start from this, not from `167-design.md` alone.

**What it did.** `begin_review`'s `verify-resolutions` branch refused with a new exit 5 when the
anchor was itself a `verify-resolutions` fact, it left zero unresolved blocking, and the delta's
judgeable files were a non-empty subset of the files that anchor's own items named.

**Why it was withdrawn.** Two independent reviewers of the 2026-09-20 cumulative converged on it
(R-1 and R-6), and the numbers settle it:

* The refusal cannot discharge the coverage obligation it leaves behind. `is_self_inflicted_verify`
  fires only on a NON-EMPTY judgeable delta, `coverage_algebra.review_edges` composes only
  `kind == "review"` facts, and `_free_edge_files` grants a free edge only when nothing judgeable
  changed. So every firing leaves an uncomposable gap, `check-cumulative-critic` returns
  `uncovered`, and its own remedy text prescribes the pass that was just refused.
* Priced with `review-stats` over 1,047 recorded reviews: the refused `verify-resolutions` has a
  median of **300s**, and the only remaining non-`--force` route, `cumulative`, has a median of
  **720s**. The guard more than doubles the cost in exactly the case it was built to cheapen.

**The durable finding, and the thing to design against next time.** The evidence available for this
decision is FILE-level. `diagnose_fix_churn` says so in its own docstring — it rules out work in a
file the review never saw, *not new work written into one it named* — so it cannot tell churn from
substantial new work in a file the last review happened to touch. That is advisory strength, and a
refusal is authority. The mistake was not the predicate's tuning; it was using advisory-strength
evidence to make an authoritative refusal, and then (in the first proposed repair) reaching for a
new composable edge kind to let that weak evidence clear a gate. **Refusing a round needs
content-level evidence that the delta is churn.** Until something supplies that, the gate's
existing advisory NOTE plus a free `disposition --accept` is the right strength for what is known.

Recorded as a rule in `.claude/rules/learnings/core.md`, on the cost axis of "A refusal hands the
caller a REPLACEMENT route, and it is checked by its PROPERTIES, never its name" — the 2026-09-20
merge folded the standalone pricing rule into that heading, so it is the one to grep for.

**What is NOT withdrawn:** the observation-recording measurement above, which stands on its own.

### Chunk 03: The cost lead knows an anchor makes the next edit cost a round

- **Description:** #851, filed today from a live reproduction in the previous plan's own review.
  `cost_lead` prices judgeability via `commit_cost`, which is correct pre-anchor and wrong after a
  `verify-resolutions` pass has anchored the working tree: from then on ANY further edit opens a new
  delta needing its own pass, judgeable or not. The lead told me a batch was free; it bought a full
  round. Verify the #600 lineage the backlog dedup asserted before building on it.
- **Depends on:** Chunk 01 (Chunk 02 was also a dependency; withdrawn, and nothing in 03 relied on it)
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
