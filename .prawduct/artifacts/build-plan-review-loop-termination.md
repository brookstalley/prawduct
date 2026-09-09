---
artifact: build-plan
version: 2
scope: review-loop-termination
branch: feat/review-loop-termination
depends_on:
  - artifact: review-loop-nontermination-diagnosis
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0; cost = unit-cost x run-count, both are levers → conforms — Chunk 02 attacks unit-cost (reviewer payload), Chunk 03 attacks run-count"
      - "adding a control names its expected yield AND emits that yield observably → conforms, with obligation — Chunk 03 adds a control (the budget) and must therefore emit its firings as countable facts, not printed-and-forgotten text; folded into that chunk's deliverables"
      - "state-file growth is advisory, never a hard block → inapplicable because this plan adds no state-file size control"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms — reviewer-proposed record patches are explicitly out of scope; nothing here grants the reviewer a write"
      - "authority fails closed; advice fails soft → conforms — an uncomputable cost renders `unknown`, never `free`, and the budget can never auto-accept a BLOCKING"
      - "every fact has one home; every other mention is a reference → conforms — Chunk 01 reuses `is_judgeable_path` rather than restating the predicate, and the measured yield figure gets exactly one home"
      - "goals and verification bind; prescribed method is advice → conforms — the call sites named in Deliverables are this plan's best guess, and a builder who finds a better route takes it and records why"
      - "prawduct guides and reviews; it never implements → inapplicable because this is framework work on prawduct itself, not on a governed product"
      - "local-first: governance coordination is process-spawn + files + the git object database, no network, no third-party runtime deps -> conforms - every figure this plan renders is derived from the local evidence store at call time"
      - "the plugin writes nothing into a governed repo except its own .prawduct/ state, the shared evidence store, and the files it must reconcile -> conforms - the only new write is a key inside .critic-findings.json, which is already the plugin own state"
      - "prawduct is written in Python and must never be specific to Python -> conforms - judgeability is decided by path, and no part of this plan inspects source content or assumes a product language"
  - artifact: data-model
    dispositions:
      - "governance verdicts are computed from the append-only ledger, never from mutable model-written state → conforms — the budget is derived from existing review facts and introduces no new mutable state"
      - "facts are immutable and append-only → conforms — auto-accept appends disposition facts and edits nothing"
      - "derived views are disposable and never authoritative; no gate reads a view → conforms, with constraint — Chunk 01 writes cost into `.critic-findings.json`, which is a view, so no gate may key on it"
      - "a governance document reaches a terminal state; it is never deleted -> conforms - this plan will be archived, not deleted, and it deletes no document"
      - "every issue written to the backlog store conforms to the issue standard section 1 title rules -> inapplicable because no chunk here writes to the backlog store"
      - "a fact written by a newer schema than the reader is surfaced as a loud block -> conforms - no chunk changes the fact schema; the budget derives from facts already written and auto-accept appends existing disposition facts"
      - "two stores, two lifetimes: shared committed answers kept distinct from per-clone gitignored nags and caches -> conforms - fix_cost lands in the gitignored view, the budget reads the shared store, and neither crosses"
      - "backlog_service_repo selects which backlog store is authoritative -> inapplicable because no chunk here reads or writes a backlog store"
  - artifact: observability-strategy
    dispositions:
      - "stable severity-prefix vocabulary; stdout agent-facing, stderr user-and-diagnostics → conforms — the budget refusal uses the existing vocabulary and channel split"
      - "emitted text names no prawduct-internal identifier → conforms — cost strings and the refusal message are plain language"
      - "the governance ledger has a single writer (ledger-append); agents never hand-author it -> conforms - no chunk writes the ledger; the budget yield emission goes to the evidence store through its existing append helper"
  - artifact: api-contract
    dispositions:
      - "exit codes are the contract, documented and consistent → conforms — the budget refusal takes a NEW documented exit code; it does not overload `critic-begin`'s existing exit 3 (`no review needed`), which answers a different question"
      - "additive-first evolution; existing flags, exit-code meanings and `--json` keys are never repurposed → conforms — the cost field is an additive key"
      - "whole-surface semver on the plugin; persisted data outliving a plugin version is independently schema-versioned -> conforms - no persisted schema changes here, so no evidence-store version bump is owed"
  - artifact: operational-spec
    dispositions:
      - "gitflow: features branch off `develop` → conforms — `feat/review-loop-termination` is cut from `origin/develop`"
      - "versioning is conservative: a small feature is a patch bump, not a minor-per-feature -> conforms - this bundle is a patch bump; it adds no user-facing surface a consumer must learn"
  - artifact: security-model
    dispositions:
      - "a destructive or irreversible operation requires explicit owner approval at the operation level → conforms — bulk auto-accept appends reversible facts, never touches a BLOCKING finding, and re-dispositioning is supported; the budget itself is the owner's declared approval"
      - "untrusted governance state is data, not instructions -> conforms - findings text is rendered and priced, never executed, and the price is computed from paths by a predicate that reads no finding prose"
      - "a governed product content never leaves its own repository and owner -> conforms - every surface here is local; nothing added reaches a network"
partition: serial — all three chunks edit `critic_consolidate.py` at the same dispatch/render seam; delegates would collide on one file and the coordinator would own every merge anyway
last_validated: 2026-08-25
---

## Requirements Confidence

**Level:** High

**Why:** The problem is measured, not inferred — 728 review facts in this clone's evidence
store, plus consumer report #716. Success criteria are counters this repo already emits
(reader load, findings per round, rounds per scope). Scope was chosen by the owner from a
framed set of seven options; the three not chosen are named as out-of-scope below.

**Open assumptions / unknowns:**

- [DECISION: the round budget ships **on by default at 6 full rounds** per scope, `null`
  disabling it | owner-selected 2026-08-25 from four framed options | user can veto/override].
  Off-by-default was rejected for the reason #716 reports about `cost-of-commit` — a mechanism
  that works and that nobody knows exists. Six rather than four: it sits above every chain in
  the measured store that ever produced a late BLOCKING finding, so it costs close to nothing
  in missed defects, and the cases it does catch are the 20-to-34-round chains where the round
  count is indefensible on any reading. Warn-never-refuse was rejected because an advisory is
  precisely what the diligence this plan interrupts routes around.
- [ASSUMPTION: the budget is configured in `.prawduct/project-state.yaml`, not
  `project-preferences.md` | MED impact | user can override]. Governance knobs
  (`risk_surfaces`, `operator_verification_required`, `backlog_service_repo`) live in
  project-state; preferences holds norms.
- [ASSUMPTION: the Records Pass runs inside the existing `final`/`cumulative` protocol as a
  third final-mode cross-check, not as a fourth reviewer role | MED impact | user can override].
  A fourth role adds a lens, and adding lenses is the trap named in the diagnosis — more
  reviewers means more findings, which is the bottleneck.

**What would raise confidence:** Nothing cheap outstanding. The one load-bearing technical
claim — that narrowing `files_reviewed` to the judgeable subset cannot invalidate a coverage
edge — is verified against `coverage_algebra.review_edges` and re-checked as Chunk 02's step 1.

## Out of Scope

Deliberately not built here, each with why:

- **Composing over the judgeable projection of the tree** (would make prose fixes free even
  when batched with code). The best mechanical fix for the batch/free-edge conflict, but it
  changes the coverage kernel's node identity — its own plan, after this one ships and the
  cheap levers are measured.
- **Reviewer-proposed record patches** (Critic emits a patch; consolidation applies it to
  non-judgeable paths before recording the fact). Approved in principle, sequenced after: it
  is only worth building if Chunk 02 does *not* already remove most of the record findings.
- **File-sharding the coordinator roster.** A latency fix; round count dominates latency.
- **Making `cumulative` incremental.** Withdrawn in the diagnosis — #716 prices the miss it
  would have caused.

## Status

- [x] Chunk 01: Cost-to-clear rendered on every finding
- [x] Chunk 02: Judgeability governs review scope; Records Pass covers what it drops
- [x] Chunk 03: The review-eligibility classifier
- [ ] Chunk 04: Round budget, auto-accept at exhaustion, and the yield prose correction

Context: Plan authored 2026-08-25 from `review-loop-nontermination-diagnosis.md`, owner-approved
scope (options 1 + B + A of seven framed). **Chunk 01 complete** — `fix_cost` on every finding,
reviewed `cumulative` (rev-20260825T125948Z-a43f7fae): 0 blocking, 3 warning, 2 note; R-4/R-5
accepted, R-2/R-3 fixed in a batch `cost-of-commit` priced free (no round bought). **Chunk 02 complete** — `review_edges` claim re-verified first, then `files_reviewed` narrowed to the
findings-eligible subject set with `files_oracle` delivered beside it, a Records Pass added as the
third final-mode cross-check, and the guard test that fails when the oracle is withheld. Chunk 01's
carried R-1 (relational FREE phrase) and the latent plan-frontmatter defect (`governed-by-gap` now
grades an unparseable header) rode this chunk's commit. Reviewed `cumulative`
(rev-20260825T135438Z-39bd933b): 0 blocking, 5 warning, 15 note — twelve fixed in one commit, six
accepted, R-2/R-10 accepted and carried below; then two `verify-resolutions` rounds, the first
returning one BLOCKING (my own regression in the frontmatter check) and the second clean at
rev-20260825T143252Z-9b65d4f9. Coverage gate `satisfied`. **RC9 is absorbed into Chunk 03 by owner
decision** — the `--fixed` disposition, guarded by the judgeability predicate at record time.
Next: Chunk 03, whose budget (6 rounds, on by default, `null` disables) is already decided. **2026-09-09 — base advance and a split.** develop had moved 216 commits over the same Critic surfaces this plan edits; merged at `29116547`, eighteen conflict hunks resolved keeping both sides, suite green. Then the owner ruled on the R-2/R-10 class finding Chunk 03 was carrying: **build the classifier**, not the cheap `agents/` partial. That ruling makes the old Chunk 03 far too large for one Critic pass — the classifier alone moves the coverage kernel's consumers — so it is split. Chunk 03 is now the classifier; Chunk 04 is the budget bundle, unchanged in content, and keeps `Type: cumulative-final`. **Chunk 03 complete** — `coverage_algebra.is_review_subject` owns eligibility; measured at 4 points of Chunk 02's 36 before it was built. Reviewed `chunk` (rev-20260909T212902Z-e08d614e): 0 blocking, 3 warning, 2 note, all one class — prose still teaching the removed rule. All four actionable fixed in this chunk's own commit (free, no round bought); R-3's live half is now pinned by `TestWideningBoundCountsTheCostSubset`. The `agents/` COVERAGE question is open and stated in Chunk 04's carry. Next: Chunk 04.

## Scaffolding

Existing repo — no scaffold. Suite is `pytest tests/ -v`; config in `pyproject.toml`.

### Verification Strategy

Tests pin behavior; they cannot tell us whether the loop actually got shorter. Each chunk is
additionally verified against the live evidence store, which is the only instrument that can
falsify the premise:

- **Chunk 01** — run a real `/prawduct:critic` on this branch and read `.critic-findings.json`:
  every finding carries a cost, and a hand-checked sample of three (one record file, one `.py`,
  one with no cited file) matches what `cost-of-commit` says for those paths.
- **Chunk 02** — compare `files_reviewed` on the review facts this branch produces against the
  pre-change baseline (39% non-judgeable across 728 facts). The expected reading is near 0%
  non-judgeable in per-round scope, with the Records Pass fact naming the excluded set.
- **Chunk 03** — exercise the exhaustion path end-to-end on this branch's own review history:
  the refusal fires, names the remedy, writes disposition facts for the non-blocking findings,
  and leaves every BLOCKING finding untouched and still blocking.

## Build Chunks

### Chunk 01: Cost-to-clear rendered on every finding

- **Description:** Every finding the builder meets states what acting on it costs. Today a
  builder dispositions a dozen findings with no signal that fixing a change-log sentence buys a
  full review round while accepting it costs nothing — the gradient runs backwards from the
  intuition and nothing says so. The cost is computed from the same judgeability predicate the
  gate charges by, so the number rendered and the number charged cannot drift apart.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/review-loop-nontermination-diagnosis.md`
  (Option B; root cause RC1)
- **Deliverables:** a cost field on each finding in the derived record built by
  `fact_to_cache_record` in `plugin/lib/critic_consolidate.py`, rendered into the
  builder-facing consolidation output; predicate **reused** from
  `plugin/lib/coverage_algebra.py` (`is_judgeable_path`) and never re-implemented. Three
  states: free (every cited file non-judgeable), charged (any cited file judgeable), unknown
  (no file cited — 93 such findings exist in the store). ACCEPT is free in all three.
- **Tests:** `tests/test_critic_consolidate.py` — non-judgeable-only finding renders free;
  judgeable finding renders charged; mixed-file finding renders charged; no-file finding
  renders **unknown, never free**. The fail-closed direction is toward charged/unknown: a false
  "free" is exactly what buys an unbudgeted round.
- **Acceptance criteria:** `pytest tests/ -v` green; a live `/prawduct:critic` run on this
  branch produces a `.critic-findings.json` in which every finding carries a cost, and three
  hand-checked entries agree with `prawduct-hook cost-of-commit` on the same paths.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: Judgeability governs review scope; Records Pass covers what it drops

- **Description:** Non-judgeable files stop being **subjects** of per-round review — measured at
  39% of all files handed to reviewers (5,869 of 14,860 file-slots) and 36% of all findings.
  A **Records Pass** at `final`/`cumulative` only then reviews the excluded set against the two
  bars the severity contract already defines ("it ships" / "it misleads into action"). The two
  land in one chunk deliberately: the narrowing alone opens a window in which a shipping
  falsehood in a record goes unreviewed, and the Records Pass is that window's only cover.
- **Subject and oracle are different roles, and only the subject role narrows** (owner
  challenge, 2026-08-25 — the original draft conflated them and would have shipped a severe
  regression). A non-judgeable file plays two parts in a review: it is a thing that can be
  *wrong* (subject), and it is the authority the code is judged *against* (oracle). Every spec
  this repo has is non-judgeable — the build plan, every `.prawduct/artifacts/*.md`,
  `project-preferences.md`, `cross-cutting-concerns.md` — and `goals-1-3.md` step 3 instructs
  the reviewer to read exactly those, because Goal 2's requirement-coverage check and Goal 3's
  norm-departure check both rate **BLOCKING** and both need the spec in front of them.
  Therefore:
  - **Subject set** (findings-eligible, what `files_reviewed` narrows to): judgeable files only.
  - **Oracle set** (delivered to the reviewer, read, never rated): the build plan, the artifacts
    a change cites, the preferences and cross-cutting-concerns registries.
  - A finding of the form *"the code violates this spec"* has the **code** as its subject. It
    stays fully in scope at full severity — the narrowing does not touch it. In the measured
    store these are the `mixed`-target class (692 findings, 18%), distinct from the
    `non-judgeable-only` class (1,372) this chunk is actually dropping.
- **The success metric cannot verify this chunk, so a guard test must.** Blinding the reviewer
  and narrowing the reviewer both show up as *fewer findings and less reader load* — the exact
  reading this chunk is trying to produce. Acceptance therefore requires a test that fails if
  the oracle is withheld, not merely a smaller number.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `.prawduct/artifacts/review-loop-nontermination-diagnosis.md`
  (Option 1; root causes RC2, RC6)
- **Carried in from Chunk 01's review** (ride-along route — these land in this chunk's commit,
  which touches judgeable code anyway, so they buy no round of their own; recorded here because a
  carry that is not written where the next chunk meets it is a drop, not a deferral):
  1. **Cumulative R-1 (WARNING).** `fix_cost` prices the files a finding *cites*, and attribution
     is not the set a remedy lands in. A finding about a record whose real correction is in code
     renders `FIX is free`, which is exactly the wrong-`free` the function's own fail-closed rule
     says must never be emitted. Fix: make the FREE phrase relational to what was measured — it
     prices the *cited* files, and says so — rather than asserting the fix itself is free.
  2. **Latent defect found while closing R-3.** This plan's YAML frontmatter was invalid for two
     commits (an unterminated double-quoted scalar) and every reader passed it: `record_lint`,
     `resolve_branch_plan` and `verify-chunk-refs` are all regex-based and none parses the
     frontmatter as YAML. Fix: `record_lint` parses the frontmatter and reports a break. A plan
     whose machine-read header cannot be parsed reads as *more* governed than one with no header,
     which is the same failure shape as the `governed_by:` gap that surfaced it.
- **Load-bearing claim, verified first:** `review_edges` in
  `plugin/lib/coverage_algebra.py` validates an edge by quantifying **only** over
  `judgeable_files(changed)`. Narrowing `files_reviewed` to the judgeable subset therefore
  cannot invalidate any edge. Step 1 of this chunk re-verifies that against the code before a
  line changes — if it no longer holds, the chunk stops and is redesigned.
- **Surfaces this concept touches** (enumerated up front — the count is the chunk's real size):
  scope derivation in `plugin/lib/critic_consolidate.py`; the per-mode behavior table and a new
  Records Pass section under "Final-Mode Cross-Checks" in
  `plugin/skills/critic/review-cycle.md`; the severity contract in
  `plugin/skills/critic/review-protocol.md`; the reviewer preamble in
  `plugin/skills/critic/goals-1-3.md`; the dispatched reviewer's instructions in
  `plugin/agents/critic-reviewer.md`. Four of these carry token accounting in
  `LAST_MEASURED_TOKENS` (`tests/test_v5_methodology.py`) — update the readings in the **same**
  commit, never as a follow-up.
- **Tests:** `tests/test_critic_consolidate.py` — the subject set excludes non-judgeable paths
  while `files_changed` stays whole; **the oracle set still carries the build plan and every
  cited artifact when those are the only non-judgeable files in the diff** (the guard for the
  regression above, and it must fail if the oracle is withheld); a finding citing a judgeable
  file plus a spec stays findings-eligible at full severity.
  `tests/test_coverage_algebra.py` — an edge whose `files_reviewed` is the judgeable subset of
  `files_changed` still validates, and one missing a judgeable file still fails.
  `tests/test_v5_methodology.py` — the Records Pass prose and the subject/oracle distinction are
  pinned where a reviewer meets them, and the token readings are updated.
- **Acceptance criteria:** `pytest tests/ -v` green; a live `final` or `cumulative` run on this
  branch records a fact whose `files_reviewed` is ~0% non-judgeable, whose Records Pass section
  names the excluded set explicitly rather than silently omitting it, **and whose reviewer
  demonstrably still had the spec** — verified by confirming the dispatched reviewer's oracle
  set contains this plan, not by observing that the finding count fell.
- **Done when:**
  1. The `review_edges` claim re-verified against the code
  2. Acceptance criteria met and tests pass
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

### Chunk 03: The review-eligibility classifier

- **Description:** Review **eligibility** stops being derived by negating the **coverage**
  predicate. `is_judgeable_path` answers *does an edit to this path re-open the gate?*;
  the subject set needs *may a finding be about this file?* The two coincided until Chunk 02 gave
  the predicate a second meaning, and its excluded paths were never re-vetted against it. This
  chunk gives the split its own classifier, owned in one place, so it cannot drift from the
  coverage predicate while answering a different question.
- **[DECISION: build the classifier rather than the cheap `agents/` path-list partial | owner
  ruling 2026-09-09, on the R-2/R-10 class finding Chunk 02's cumulative raised | user can veto]**
  The partial closes one member — `plugin/agents/critic-reviewer.md`, a review subagent's own
  system prompt, classifying non-judgeable — and leaves the class open. The generality case is
  the sharp one and it is not this repo's: for a governed product whose **deliverable is
  markdown** (a docs site, a spec repo, a prompt library) every product file is non-judgeable, so
  one incidental `.py` in the interval defeats the all-prose floor and the product's actual
  output becomes read-but-never-rated for all seven goals. `is_judgeable_path` is not
  product-configurable, and this plan's `governed_by:` dispositions cover language-independence
  but never this shape.
- **Depends on:** Chunk 02
- **Artifacts consumed:** `.prawduct/artifacts/review-loop-nontermination-diagnosis.md`
  (root cause RC6); Chunk 02's cumulative findings R-2 / R-10
- **The classifier:** subject = a **deliverable, or prose that governs behaviour**; oracle = a
  record *about* the work (`.prawduct/**`, archived artifacts). It is a separate function from
  `is_judgeable_path` and neither may be defined in terms of the other's negation — that
  identity is the defect. Known members the current negation gets wrong: `plugin/agents/`
  (behaviour-governing) and `plugin/docs/norms.md`, `plugin/docs/principles.md` and `plugin/docs/waivers.md` (behaviour-governing).
- **Surfaces this concept touches** (the count is the chunk's real size — every consumer of the
  coverage predicate must be checked for which of the two questions it is actually asking):
  `plugin/lib/coverage_algebra.py`, `plugin/lib/buildplan_refs.py`
  (`_TRIVIAL_PROTECTED_PATHS`), the subject/oracle split in `plugin/lib/critic_consolidate.py`,
  and the consumers the plan's Chunk 02 carry-in enumerates — `cost-of-commit`, free-edge
  composition, the dispatch guard, the trivial gate, and the doc-only PR gate. Prose carriers:
  `plugin/skills/critic/review-cycle.md` (the Records Pass carve-out) and
  `plugin/skills/critic/goals-1-3.md`. Both carry token accounting in `LAST_MEASURED_TOKENS` —
  update the readings in the **same** commit.
- **Fail-closed direction:** strictly more review, which is the posture
  `protected_path_violation` already states for over-inclusion. A file the classifier cannot
  place is a subject, never an oracle.
- **Tests:** `tests/test_coverage_algebra.py` — the classifier places each known member, and a
  test **fails if it is ever implemented as the negation of `is_judgeable_path`** (the defect
  this chunk exists to close, so it needs its own pin, not just correct answers today);
  a markdown-deliverable product's files are subjects even when one `.py` is in the interval.
  `tests/test_critic_consolidate.py` — the subject/oracle split routes through the classifier,
  and the oracle set still carries the build plan and cited artifacts.
- **Acceptance criteria:** `pytest tests/ -q` green; a live review on this branch shows
  `plugin/agents/critic-reviewer.md` in the SUBJECT set, and `cost-of-commit` still prices a
  `.prawduct/` batch `free` — the two questions answered differently by the two predicates, which
  is the whole point.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: Round budget, auto-accept at exhaustion, and the yield prose correction

- **Type:** cumulative-final
- **Description:** A declared per-scope ceiling on full review rounds — **6 by default, on in every
  governed repo, `null` to disable**. At exhaustion
  `critic-begin` refuses a further full round — naming the remedy, in the same shape as its
  existing "no review needed" exit — and the outstanding non-blocking findings are auto-accepted
  into a census rendered by `prawduct-hook render-dispositions`. This is the terminating rule
  the measured data says nothing else supplies: finding yield does not decay (13.5 → 15.4 →
  15.5 → 18.4 findings per full round, 99% of them new), so there is no natural fixed point and
  the only principled stop is a declared budget.
- **Depends on:** Chunk 03
- **Artifacts consumed:** `.prawduct/artifacts/review-loop-nontermination-diagnosis.md`
  (Option A; root cause RC2)
- **Absorbed by owner decision, 2026-08-25:** RC9 in the diagnosis — a FIX confined to free paths
  buys no round, so no resolution fact is ever written and the census reports it `undispositioned`
  forever. Found live on Chunk 01's own review. The remedy is a `--fixed` disposition guarded by the
  same judgeability predicate, verified at record time so it can never launder a judgeable fix past a
  gate; a BLOCKING finding still clears only through a real resolution fact, and nothing about gating
  changes. It rides this chunk because this chunk is already inside `dispositions.py`. Owner asked
  for the bundling explicitly; it is a scope increase, taken deliberately.
- **HALF-DISCHARGED BY CHUNK 03 — the ELIGIBILITY half only; the COVERAGE half is this chunk's to decide** (was: carried in from Chunk 02, ride-along route — lands in this chunk's commit, which touches
  judgeable code anyway, so it buys no round of its own): **`agents/` is missing from the
  governance-protected path set.** `buildplan_refs._TRIVIAL_PROTECTED_PATHS` holds `skills/`,
  `methodology/`, `templates/` and root `CLAUDE.md`, so `plugin/agents/critic-reviewer.md` — a
  review subagent's own system prompt, behavioural logic by exactly the argument that docstring
  makes for skill prose — classifies **non-judgeable**. Found live on Chunk 02's own review, where
  that file landed in `files_oracle`. The gap predates Chunk 02; Chunk 02 is what makes it bite,
  because agent prose used to be a review subject by virtue of being in the diff and now is not.
  Fix: add `("agents/", False, "agent-file-edited")`. The direction is fail-closed — strictly more
  review — which is the posture `protected_path_violation` already states for over-inclusion. It
  touches the coverage kernel's predicate, so every consumer moves with it (`cost-of-commit`, free
  edges, the dispatch guard, the trivial gate, the doc-only PR gate); that breadth is why it did not
  ride Chunk 02's own commit while its review was in flight, and it is a deliberate carry, not a
  drop.

  **Chunk 02's own review found the same thing from a stronger angle and bounded it wider (R-2/R-10,
  both WARNING, Scope: class).** `agents/` is one member; `plugin/docs/{norms,principles,waivers}.md`
  is another. The class is not "a directory the list forgot" — it is that **review ELIGIBILITY is
  being derived by negating the COVERAGE predicate, and they answer different questions.**
  `is_judgeable_path` answers *does an edit to this path re-open the gate?*; the subject set needs
  *may a finding be about this file?*. They coincided until Chunk 02 gave the predicate the second
  meaning, and its excluded paths were never re-vetted against it. The generality case is the sharp
  one and it is not this repo's: for a governed product whose **deliverable is markdown** — a docs
  site, a spec repo, a prompt library — every product file is non-judgeable, so one incidental `.py`
  in the interval defeats the all-prose floor and the product's actual output becomes read-but-never-
  rated for all seven goals. `is_judgeable_path` is not product-configurable, and the plan's
  `governed_by:` dispositions cover language-independence but never this shape.

  So the fix is a **construction, not a longer path list**: give the split its own classifier —
  subject = deliverable or behaviour-governing prose; oracle = a record *about* the work
  (`.prawduct/**`, archived artifacts) — owned in one place so it cannot drift from the coverage
  predicate while answering a different question. Adding `agents/` to the protected set is the cheap
  partial that fails closed in the documented direction; take it only if the classifier is scoped out
  here, and say which was chosen. **This is a requirement that surfaced mid-build and it is written
  here rather than designed in chat**, per the mid-build tripwire.

- **Carried in from Chunk 02's verify pass** (observation, not a recorded finding — the pass that
  saw it returned clean): **the no-work refusal takes the wrong exit code, and the exit table then
  buys a round.** `begin_review`'s `not delta and not actionable` branch returns a bare
  `{"status": "error"}`, which surfaces as **exit 1**, because it is an early return sitting ABOVE
  the gate-as-dispatcher free-edge path that owns exit 3. Semantically it is a `no review needed`,
  and `SKILL.md`'s exit table routes *exit 1 on `verify-resolutions`* to "re-dispatch per the
  demotion property" — which here means spending a full `cumulative` on a bundle the gate already
  reports `satisfied`. That is a manufactured round produced by the framework's own routing, which
  is this plan's whole subject; it belongs beside the budget rather than after it. Fix: give the
  branch exit 3 with its existing message, and check whether the table needs anything said. Rides
  this chunk's commit; standalone it re-opens the gate for no behavioural gain.

- **The open residue Chunk 03 left, stated so it stays tracked.** `plugin/agents/critic-reviewer.md`
  is now a review **subject** — a finding may be about it — but it is still **non-judgeable**, so a
  commit touching only a review subagent's system prompt is a free edge and merges with zero
  coverage, and `cost-of-commit` prices it `free`. Eligibility and cost are different questions and
  Chunk 03 answered only the first, deliberately. This chunk decides the second: either add
  `("agents/", False, "agent-file-edited")` to `buildplan_refs._TRIVIAL_PROTECTED_PATHS` — which
  makes agent prose judgeable and moves every consumer of the coverage predicate with it — or record
  a ruling that a subagent prompt is genuinely free to edit unreviewed. **What is not available is
  leaving it unstated**, which is what "discharged" would have done.

- **Yield emission is a deliverable, not a nicety** (`nonfunctional-requirements.md` § Direction:
  a new control must emit its yield observably, or it can never be retired on evidence). The
  budget records each firing as a countable fact so `prawduct-hook review-stats` can answer how
  often it fired and what it suppressed. A budget whose firings are only printed satisfies the
  letter of the norm and defeats its point.
- **No new persisted format.** Round count per scope is already derived from the evidence store
  (`plugin/lib/coverage.py` prints it in the gate's escalation NOTE), and auto-accept writes the
  existing `disposition` fact via `plugin/lib/dispositions.py`. The budget is a policy over a
  count that already exists, so this chunk locks in no schema.
- **BLOCKING cannot be auto-accepted, by construction:** `dispositions.record` already refuses
  `--accept` on a BLOCKING finding without an explicit `--owner-ruling`, and the automatic path
  never supplies one. A budget can therefore end a review loop but can never open a gate.
- **Prose correction, in scope and why:** `plugin/skills/critic/review-cycle.md`'s
  "Diminishing-returns signal" paragraph asserts that by round 3 a pass is finding defects in
  the record of round 2. The store shows the opposite. Shipping a budget while that paragraph
  stands leaves two contradictory stopping rules, and the false one is the one an agent can
  check and therefore learn to distrust — which is the behavior this whole plan exists to fix.
  Replaced with the measured floor, carried with its number.
- **Surfaces:** `review_round_budget` in `.prawduct/project-state.yaml` and
  `plugin/templates/project-state.yaml`; the refusal path in
  `plugin/lib/critic_consolidate.py`; the stopping rule and the corrected yield paragraph in
  `plugin/skills/critic/review-cycle.md`. Enumerate any doctor/briefing surface at chunk start
  rather than assuming this list is complete.
- **Tests:** `tests/test_critic_consolidate.py` — the refusal fires at the ceiling, not before;
  `--force` passes through; a `null` budget never refuses; the default reads 6 and a repo
  override wins over it; `tests/test_dispositions.py` — the
  auto-accept path writes accept facts for WARNING and NOTE and **refuses every BLOCKING**,
  with a test that fails if a blocking finding is ever swept; `--fixed` records on an all-free
  path set and **refuses a set holding any judgeable path**, with a test that fails if a judgeable
  fix records without a review; `tests/test_v5_methodology.py` —
  the corrected yield paragraph carries its figure, and the token reading is updated.
- **Acceptance criteria:** `pytest tests/ -v` green; exercised on this branch's own review
  history — the refusal fires at the ceiling, the census renders, every BLOCKING survives
  untouched and still blocks the gate; and the two WARNINGs Chunk 01 fixed for free record as
  `--fixed`, taking that review's census to zero undispositioned without a round being bought.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run ONCE (Type: cumulative-final — no
     separate `final`) and blocking findings resolved
  3. Chunk marked `[x]` in Status
