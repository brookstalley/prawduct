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
  - artifact: data-model
    dispositions:
      - "governance verdicts are computed from the append-only ledger, never from mutable model-written state → conforms — the budget is derived from existing review facts and introduces no new mutable state"
      - "facts are immutable and append-only → conforms — auto-accept appends disposition facts and edits nothing"
      - "derived views are disposable and never authoritative; no gate reads a view → conforms, with constraint — Chunk 01 writes cost into `.critic-findings.json`, which is a view, so no gate may key on it"
  - artifact: observability-strategy
    dispositions:
      - "stable severity-prefix vocabulary; stdout agent-facing, stderr user-and-diagnostics → conforms — the budget refusal uses the existing vocabulary and channel split"
      - "emitted text names no prawduct-internal identifier → conforms — cost strings and the refusal message are plain language"
  - artifact: api-contract
    dispositions:
      - "exit codes are the contract, documented and consistent → conforms — the budget refusal takes a NEW documented exit code; it does not overload `critic-begin`'s existing exit 3 (`no review needed`), which answers a different question"
      - "additive-first evolution; existing flags, exit-code meanings and `--json` keys are never repurposed → conforms — the cost field is an additive key"
  - artifact: operational-spec
    dispositions:
      - "gitflow: features branch off `develop` → conforms — `feat/review-loop-termination` is cut from `origin/develop`"
  - artifact: security-model
    dispositions:
      - "a destructive or irreversible operation requires explicit owner approval at the operation level → conforms — bulk auto-accept appends reversible facts, never touches a BLOCKING finding, and re-dispositioning is supported; the budget itself is the owner's declared approval
partition: serial — all three chunks edit `critic_consolidate.py` at the same dispatch/render seam; delegates would collide on one file and the coordinator would own every merge anyway
last_validated: 2026-08-25
---

## Requirements Confidence

**Level:** High

**Why:** The problem is measured, not inferred — 732 review facts in this clone's evidence
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

- [ ] Chunk 01: Cost-to-clear rendered on every finding
- [ ] Chunk 02: Judgeability governs review scope; Records Pass covers what it drops
- [ ] Chunk 03: Round budget, auto-accept at exhaustion, and the yield prose correction

Context: Plan authored 2026-08-25 from `review-loop-nontermination-diagnosis.md`, owner-approved
scope (options 1 + B + A of seven framed). Nothing built yet. Next: Chunk 01. Branch cut from
`origin/develop`. The diagnosis artifact is untracked until Chunk 01's commit carries it.

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
  pre-change baseline (39% non-judgeable across 732 facts). The expected reading is near 0%
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
  39% of all files handed to reviewers (5,887 of 14,923 file-slots) and 36% of all findings.
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
    `non-judgeable-only` class (1,374) this chunk is actually dropping.
- **The success metric cannot verify this chunk, so a guard test must.** Blinding the reviewer
  and narrowing the reviewer both show up as *fewer findings and less reader load* — the exact
  reading this chunk is trying to produce. Acceptance therefore requires a test that fails if
  the oracle is withheld, not merely a smaller number.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `.prawduct/artifacts/review-loop-nontermination-diagnosis.md`
  (Option 1; root causes RC2, RC6)
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

### Chunk 03: Round budget, auto-accept at exhaustion, and the yield prose correction

- **Type:** cumulative-final
- **Description:** A declared per-scope ceiling on full review rounds — **6 by default, on in every
  governed repo, `null` to disable**. At exhaustion
  `critic-begin` refuses a further full round — naming the remedy, in the same shape as its
  existing "no review needed" exit — and the outstanding non-blocking findings are auto-accepted
  into a census rendered by `prawduct-hook render-dispositions`. This is the terminating rule
  the measured data says nothing else supplies: finding yield does not decay (13.5 → 15.4 →
  15.5 → 18.4 findings per full round, 99% of them new), so there is no natural fixed point and
  the only principled stop is a declared budget.
- **Depends on:** Chunk 02
- **Artifacts consumed:** `.prawduct/artifacts/review-loop-nontermination-diagnosis.md`
  (Option A; root cause RC2)
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
  with a test that fails if a blocking finding is ever swept; `tests/test_v5_methodology.py` —
  the corrected yield paragraph carries its figure, and the token reading is updated.
- **Acceptance criteria:** `pytest tests/ -v` green; exercised on this branch's own review
  history — the refusal fires at the ceiling, the census renders, every BLOCKING survives
  untouched and still blocks the gate.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run ONCE (Type: cumulative-final — no
     separate `final`) and blocking findings resolved
  3. Chunk marked `[x]` in Status
