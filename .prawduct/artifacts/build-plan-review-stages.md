---
artifact: build-plan
version: 2
scope: review-stages
branch: feature/review-stages
partition: "01 serial first (the norm every later chunk cites); 02 → 03 → 04 serial (all three edit the critic skill prose and `critic_mode.py` / `critic_consolidate.py` at one seam); 05 and 06 delegable to isolated worktrees after 01 lands — 05 owns `building.md`, `templates/`, the `test-evidence record` directive and `docs/discipline.md`; 06 owns `session-digest.md`, `migrate_plugin.py` / `anchor_repair.py`, the doctor skill and a new probe module. Neither touches a file 02–04 edit."
program: consumer-overhead-program-2026-09.md (proposed WS8 — the owner-authorized trade the program scoped out; that program lives on the unmerged branch `docs/consumer-overhead-program`)
depends_on:
  - artifact: review-proportionality-assessment-2026-09-17
  - artifact: review-loop-nontermination-diagnosis
related_issues:
  - "brookstalley/prawduct#292 — defer per-chunk reviews on short plans (Chunk 04; the owner trade-off it waited on is now made)"
  - "brookstalley/prawduct#719 — no onboarding leg asks for a toolchain declaration (Chunk 06 adds the sibling leg for `risk_surfaces:`; #719 itself is not built here)"
  - "brookstalley/prawduct#167, #815, #776, #731 — NOT built here; WS1 of the consumer-overhead program (`build-plan-review-round-economy.md` on that branch)"
  - "brookstalley/prawduct#653, #679, #767 — NOT built here; WS6 of the same program"
  - "brookstalley/prawduct#792, #680 — NOT built here; WS3 of the same program"
  - "brookstalley/prawduct#561 — NOT built here; recommended for WS7 (the false-positive sweep) because it is classification, not review depth"
  - "brookstalley/prawduct#164 — NOT built here; L, its own plan. Named because Chunk 05's language-neutral wording must not claim a Swift/C# coverage floor that #164 says does not exist"
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is a P0 constraint; run-count and per-mode payload are the levers → ENGAGED: this plan pulls both — the inner-loop severity table shrinks the reviewer's payload and the fix→verify loop it generates, and Chunk 04 removes whole rounds"
      - "proportionality ratchets both ways; a control that fires repeatedly and never blocks is removed by default, and a new control names its yield → ENGAGED, in the removal direction: Chunks 03–04 retire two escalators (the 5-file coordinator fallback; the per-chunk review on short plans) on the ledger evidence in the assessment, and each names the evidence that would have kept it (a blocking finding from that control in the 2026-08-01 → 09-17 window; none found). [DECISION: the owner accepts a bounded miss-rate increase in exchange for wall-clock — a coverage or design gap found at the boundary review instead of mid-chunk | stated 2026-09-17 in the session that drew this plan (\"optimizing for saving a lot of wall clock for at most a minor drop in quality\"); the prior three efficiency plans held miss-rate constant and the complaint survived them | user can veto/override]"
      - "state-file growth past its threshold is an advisory, never a hard block → inapplicable, because no chunk changes a size gate"
      - "review rigor is stage-keyed; the inner stage blocks only on ships-broken and the boundary is never inferred away → this plan BIRTHS it (Chunk 01, owner decision 2026-09-17) and the remaining chunks conform to it: 02 carries `stage` to every reviewer, 03 flips the defaults, 04 defers only inner-stage reviews and leaves the boundary gate untouched, 05–06 restate it in product terms"
  - artifact: architecture
    dispositions:
      - "prawduct is Python but never Python-specific; it consumes verdicts and never re-implements a product's tooling → ENGAGED by Chunk 05: the inner-loop verification ceiling is declared in the product's own words, never as a runner flag; and by Chunk 05's template edit, which removes the pytest-shaped acceptance criteria from the shipped example"
      - "authority fails closed; advice fails soft, never silent → ENGAGED by Chunk 04: the Stop gate on a short plan's non-final chunk becomes a WARNING that names the boundary review it defers to, never a silent skip; the boundary gate (`check-cumulative-critic`) is untouched and still fails closed"
      - "every fact has one home → ENGAGED by Chunk 02: `stage` is derived in `critic-begin` from the review interval and carried to every reader through the manifest; no prose surface re-derives it"
      - "goals and verification bind; prescribed method is advice → conforms; the chunks below name what binds (the stage norm, the inner BLOCKING set) and leave the mechanism to the builder where the assessment's guess may be wrong"
      - "the plugin writes nothing into a governed repo except its own state → conforms; Chunk 06's risk-surface ask is a doctor report and an advisory, never a write"
      - "local-first, no third-party runtime dependency → conforms"
      - "an independent reviewer never mutates the session it reviews → conforms; the stage line a reviewer receives is rendered by `critic-begin`, and the reviewer still writes only its partial"
      - "prawduct guides and reviews; it never implements → conforms; the inner-loop verification ceiling is a preference the product fills, never a command prawduct writes"
  - artifact: data-model
    dispositions:
      - "verdicts computed from the append-only fact ledger, never from mutable model-written state → conforms; `stage` is code-derived at dispatch and recorded on the review fact; no gate reads it from prose"
      - "a persisted format is a lock-in decision; consumer queries precede fields → ENGAGED by Chunk 02: `stage` on the manifest and review fact is a new field; its consumers are named before it is added (the reviewer prompt, `review-stats` by stage — which is the yield query the ratchet norm has been waiting for — and Chunk 04's Stop-gate predicate)"
      - "facts are immutable and append-only → conforms"
      - "a newer-schema fact surfaces as a loud block → ENGAGED by Chunk 02: adding a field to the review fact is additive and must not trip `evidence status`'s schema-ahead read"
      - "derived views are disposable and never authoritative → conforms; `.critic-findings.json` may carry `stage` for display, and no gate reads it from there"
      - "a governance document reaches a terminal state, never deleted → inapplicable, because no chunk archives or deletes a document"
      - "every backlog write conforms to the issue standard's title rules → conforms; the only backlog write is Chunk 04's status update on #292, made through `/prawduct:backlog`"
      - "two stores, two lifetimes → conforms; `stage` lives on the shared committed fact, and Chunk 06's advisory dismissal lives in the per-clone advisory store like every other advisory"
      - "`backlog_service_repo` selects the authoritative backlog store → conforms; Chunk 04 reaches #292 through the skill, never the frozen markdown"
  - artifact: api-contract
    dispositions:
      - "exit codes are the contract, on a documented scheme → conforms; no exit code changes meaning (Chunk 04's Stop change is severity of a message, not an exit code)"
      - "additive-first evolution: flags and `--json` keys are added, never repurposed → conforms; `stage` is a new key on the manifest and `review-stats --json`"
      - "whole-surface semver on the plugin; persisted data that outlives a version is independently schema-versioned → ENGAGED by Chunk 02: an optional field on the review fact must follow the evidence store's own versioning rule — open that rule before adding the key, and bump only if the rule says an additive field is a bump"
  - artifact: observability-strategy
    dispositions:
      - "terminal signals use a stable severity-prefix vocabulary → conforms; Chunk 04's deferred-review line uses the existing WARNING prefix"
      - "text emitted into a governed product names no prawduct-internal identifier → ENGAGED by Chunks 04 and 06: the deferral line and the risk-surface ask are written in the product's terms"
      - "the governance ledger has a single writer → conforms; no chunk hand-authors the ledger, and the `by_stage` block is read from facts the existing writer already appends"
last_validated: 2026-09-17
---

# Build plan — review rigor is stage-keyed

## What I would do differently (advisory obligation)

**Cut Chunk 04 if you want the smallest plan.** Chunks 01–03 are the philosophy change and carry
most of the saving with the least miss-rate risk: once the inner loop blocks only on ships-broken
and the coordinator no longer fires on file count alone, a chunk review is a two-minute single pass
and the fix→verify treadmill has nothing to feed on. Chunk 04 (no per-chunk review on short plans)
is the one chunk that removes a *review* rather than a *severity*; it is the largest per-plan saving
and the only one with a concrete miss story (#716's round-4 defect was present since chunk 1). The
plan keeps it because the owner put it on the table, and records it as vetoable.

**Do not expect this plan alone to hit the program's targets.** It attacks the philosophy; the
program's WS1/WS3/WS6 plans attack the mechanics. Merge the `docs/consumer-overhead-program` branch
so those plans are on develop and pickable, and run WS1 Chunks 01–02 in parallel with this plan.

**The number to watch is not rounds, it is minutes per scope.** Stage-keying can lower rounds while
lengthening the boundary review (it now carries everything the inner loop deferred). The success
metric below is priced in minutes so that trade is visible.

## Requirements Confidence

**Level:** Medium

**Why:** The problem, the evidence and the three shifts are settled in
`review-proportionality-assessment-2026-09-17.md`. What is unconfirmed is the exact membership of
the inner-loop BLOCKING set, the short-plan threshold, and whether the principle amendment in
Chunk 01 is wanted at all.

**Open assumptions:**
- `[ASSUMPTION: the inner-loop BLOCKING set is exactly — test failures in evidence; a test deleted or weakened; changed behavior with no test at all; a silently dropped requirement; exploitable security in changed code; a cross-component contract break; a norm departure without a recorded decision; an unlisted dependency. Everything else the tables rate today is an observation at the inner stage | HIGH impact | user can add or remove members before Chunk 02 is built]`
- `[ASSUMPTION: "no test at all" stays BLOCKING at the inner stage, because a unit test is the contract and is cheap; only the test-QUALITY bars (error paths, real dependencies, E2E floor, property-based, structure) defer | MED impact | user can override]`
- `[ASSUMPTION: a short plan is ≤ 3 chunks, no chunk touching a declared risk surface (#292's proposed bound, owner-unconfirmed until now) | MED impact | user can change the threshold]`
- `[ASSUMPTION: Principle 11 gains one sentence rather than a new principle | LOW impact | user can decline the amendment; the NFR norm still carries the rule]`
- `[ASSUMPTION: the 5-file coordinator fallback for products with no `risk_surfaces:` is retired outright, not lowered — a product that has not said where its risk lives gets one reviewer and a one-time ask, not three reviewers forever | HIGH impact | user can keep a fallback at a higher count]`

**What would raise confidence:** the owner ticks or edits the five lines above; nothing else.

## Success

Measured the same way the assessment measured the problem (`prawduct-hook review-stats`, and each
repo's `.prawduct/.governance-ledger.jsonl` filtered by `ts`), four weeks after consumers install
the release that carries this plan, against the 2026-09-13 → 09-17 window in the assessment:

| Metric | Baseline (assessment §1) | Target |
|---|---|---|
| Reviewer minutes per build-plan scope, median (this repo) | 21 | ≤ 12 |
| Zero-finding verify-resolutions rounds, share (3.5.1-dev siblings) | 80% | ≤ 40%, on ≤ half the count |
| Coordinator dispatches on product repos with no `risk_surfaces:` | every 5+-file `final`/`cumulative` | 0 |
| Blocking findings first found at the boundary that a chunk review would previously have raised | not instrumented — Chunk 02's `stage` field on the fact makes it countable | report the number; it is the price paid, not a target |

Language check for every chunk: the diff must read the same for a Swift, C#, JS or Python product.
Any chunk that names a runner, a suffix or a test framework outside a template *example* fails its
own acceptance.

## Out of scope

- Any coverage grant without a review fact (the loop-termination Chunk 03 cut stands).
- Content or AST equivalence anywhere (#367 ruling).
- The mechanics in the consumer-overhead program (WS1, WS3, WS5, WS6, WS7) — they compose with
  this plan and are drawn already.
- Reviewer model selection (the `reviewer-session-model` pin is untouched).
- #164 and #561 (language classification) — named so Chunk 05 does not over-claim; built elsewhere.

## Status

- [x] Chunk 01: The stage norm — ratified, and the two "thoroughness is safe" sentences retired
- [x] Chunk 02: Stage reaches every reviewer — derived once, carried on the manifest, severity keyed on it
- [x] Chunk 03: Defaults fail cheap at the inner stage — mode inference and the roster
- [ ] Chunk 04: A short plan owes one boundary review, not one per chunk (#292)
- [ ] Chunk 05: The inner loop has a verification ceiling; the suite runs at Verify and at the boundary
- [ ] Chunk 06: Product-facing surfaces say it, and a product is asked once where its risk lives
Context: Drawn 2026-09-17 from `review-proportionality-assessment-2026-09-17.md`. Chunk 01 shipped
2026-09-17 on `feature/review-stages` (owner ratified the entry and the Principle 11 sentence the same day).
Chunk 02 shipped 2026-09-17 on the same branch (chunk review + two verify passes, the second bought by
correcting a sentence the first demoted; both live runs of the new protocol). Chunk 03 shipped 2026-09-17
(chunk review clean, one verify pass for two observations answered in the tree; the fleet measurement it
ran overturned the plan's inherited "no blocking finding attributable to the fallback" claim — see the
chunk's `[DECISION]`, owner-vetoable). Chunk 04 is next. The consumer-overhead program and its five plans are on the unmerged
branch `docs/consumer-overhead-program` (checked out in an agent worktree under
`.claude/worktrees/`); this plan is written to sit beside them, not replace them.

## Chunk 01: The stage norm — ratified, and the two "thoroughness is safe" sentences retired

- **Type:** doc-only
- **Description:** Add one `## Direction` entry to `.prawduct/artifacts/nonfunctional-requirements.md`:
  *Review rigor is stage-keyed.* The **inner stage** is any review of an uncommitted diff (`chunk`,
  `final`, `verify-resolutions`); it blocks only on the inner BLOCKING set (Requirements Confidence,
  first assumption) and reports everything else as an observation, pre-priced, carried to the
  boundary. The **boundary stage** is any review over `merge-base…HEAD` (`cumulative`) and the PR
  review; it runs the full table and is never skipped. *The failure direction is symmetric*: an
  inner-stage review run at boundary rigor is a defect, priced in minutes and the rounds it
  manufactures; a boundary review run at inner rigor is a defect, priced in what ships. Carry the
  owner's 2026-09-17 decision as the entry's `[DECISION]`, engaging the wall-clock norm's why.
  Under the same entry, name the two sentences it retires — `planning.md` "Under-declaring Type is
  safe (worst case: redundant Critic work)" and the "fails safe to thoroughness" family
  (`review-cycle.md` canonical statement, `planning.md`, `critic_mode.py` docstrings, `SKILL.md`
  fall-through) — and their replacement: *unsure defaults to the inner-stage review of whatever
  interval exists; the boundary is never inferred away.* This chunk records the retirement; Chunks
  02–03 perform it, so the norm leads the code (Requirements Precede Code; norms bind).
  Amend Principle 11 in `plugin/docs/principles.md` with one sentence: rigor also has two stages —
  the inner loop proves the change, the boundary proves the bundle. Owner ratifies both in this
  chunk's Done-when; the Critic treats the amendment as norm birth otherwise.
- **Deliverables:** the Direction entry with Why, Status `steady-state`, and the DECISION line; the
  Principle 11 sentence; a pin in `tests/test_v5_methodology.py` (beside the existing principle
  pins) that the sentence is present; a pin that no surface under `plugin/` still says "fails safe
  to thoroughness" or "under-declaring … is safe" — **red until Chunk 03 lands**, so mark it
  `xfail(strict=True)` with the chunk-03 reason and flip it there.
- **Acceptance criteria:** `prawduct-hook jurisdiction --file <this plan>` ranks
  `nonfunctional-requirements.md` among the governing artifacts, and the entry raises its rank
  (measured 2026-09-17: fourth before the entry, second after, behind `architecture.md` — the
  ranker scores vocabulary overlap with the whole plan, and this plan's `governed_by:` block carries
  eight architecture dispositions, so "first" was a guess about the ranker that the ranker
  refutes; re-derive with the command); `/prawduct:doctor`'s norm-registry check reports the new
  entry with a Why and no tracking id owed (it is steady-state, not in-transition).
- **Done when:** owner has said yes to the entry text and the Principle 11 sentence (record the
  reply's date in the entry); pins green (one xfail); `/prawduct:critic`; tick.

## Chunk 02: Stage reaches every reviewer — derived once, carried on the manifest, severity keyed on it

- **Description:** Three surfaces, one fact. **(a)** `critic-begin` (`critic_consolidate.begin_review`)
  derives `stage: inner | boundary` from the interval it already computes (uncommitted-diff
  intervals are inner; merge-base→HEAD is boundary) and writes it to the manifest; the manifest
  validator admits it; `critic-consolidate` carries it onto the review fact; `review-stats` gains a
  `by_stage` block (additive; bump `schema_version` per its contract). Open the validator and the
  fact schema before adding the key — the plan names them, the code decides the spelling.
  **(b)** `skills/critic/goals-1-3.md` (the inner-stage file by construction) gets a stage-keyed
  severity section: the inner BLOCKING set as a list; every other `→ BLOCKING` / `→ WARNING` in
  Goals 1–3 becomes an observation entry (the `observations` array the file already defines for
  `verify-resolutions` becomes the carrier for `chunk` too). `review-protocol.md` (read by `final`
  and `cumulative`) branches on the manifest's `stage`: at `inner`, Goals 4–7 report observations
  only and Goals 1–3 use the inner set; at `boundary`, the table as it stands. State the rule once
  in `review-cycle.md`'s per-mode table (a `Stage` row) and have both protocol files point at it.
  **(c)** The coordinator's reviewer prompt in `review-protocol.md` replaces the freeform
  `Signals: [summary]` with a code-rendered line — `Stage: <stage> · Judgeable files: <n> · Type:
  <chunk type>` — produced by `critic-begin` (print it with the manifest) so no coordinator invents
  it; `agents/critic-reviewer.md` says what the line means and that severity definitions come from
  the protocol file it was handed. Token ceilings: `goals-1-3.md` (2434), `review-protocol.md`
  (4050), `review-cycle.md` (10448) — the additions are paid in place where a class is removable
  (the per-rule severity tokens that the inner set now covers as a group are the candidate) or the
  ceiling is raised in the same commit with the reason; never trimmed to fit.
- **Tests:** manifest carries `stage` for each of the four modes with the expected value; a
  `verify-resolutions` and a `chunk` dispatch never carry `boundary`; a `cumulative` never carries
  `inner`; `review-stats --json` groups by stage; the rendered reviewer line matches the manifest
  (mutate the manifest, watch the line change); a discipline-table pin for any moved anchor; the
  reviewer-facing prose pins that the inner BLOCKING set is stated once and pointed at from both
  protocol files (`test_record_lint`-style: the module that reads both).
- **Acceptance criteria:** a `chunk` review of a fixture diff that adds an untested error path and a
  substring assertion returns those as observations, not findings; the same diff under `cumulative`
  returns them as findings. This is the property Chunk 01's norm states; the fixture is the pin.
- **Built 2026-09-17 — what the code decided where the plan guessed:**
  (1) `goals-1-3.md` cannot *point at* `review-cycle.md` for the set — `test_is_self_contained`
  forbids any read-directive there — so the inner BLOCKING set is stated in full on three carriers
  (`goals-1-3.md`, `review-protocol.md`, `review-cycle.md`) in the norm's own sentence, and
  `TestInnerBlockingSetIsOneSentence` pins all three against the norm's text (the "module that
  reads both", widened to the four surfaces). `review-protocol.md` carries it inline rather than
  pointing because an inner-stage `final` reviewer decides finding-or-observation per bullet.
  (2) `critic-consolidate` *refused* an `observations` array from any non-verify dispatch; the
  gate now keys on the manifest's stage (`stage_of_manifest`, deriving from the mode only for a
  manifest written before the field) and refuses at `boundary` alone. (3) The coordinator's
  reviewer schema (`agents/critic-reviewer.md`) had no `observations` arm, so an inner-stage
  `final` under a coordinator roster had nowhere to put a demotion; added, with the stage
  condition. (4) Record-lint at the inner stage: `chunk-ref-missing` stays a finding (a declared
  deliverable that does not exist is a dropped requirement — a set member); the two learnings
  budget checks are BLOCKING at the boundary and observations here, per the norm's "records".
  **Contracts renegotiated in the open:** `TestReviewCycle::test_the_per_mode_table_records_the_
  severity_narrowing` (one boundary column rates every severity, not three);
  `TestResolutionFacts::test_observations_outside_verify_mode_fail_closed` → the boundary refusal
  plus the inner-stage `final` persisting them; `test_review_stats` key pins (`by_stage`, report
  schema 4 → 5). **Schema readings:** the review fact gains an optional body key — the store's
  `SCHEMA_VERSION` versions the *envelope*, and `observations` set the precedent of an optional
  body key with no bump, so no bump; the report schema bumps on any key-set change and did.
  **Token ceilings raised by declaration** (goals-1-3 2434 → 2609, review-protocol 4050 → 4312,
  review-cycle 10448 → 10864): the plan's payment candidate — the per-rule severity tokens — is
  pinned identical across the two protocol files by `test_discipline_table` and the verdict-count
  drift detector, and the ratings still instruct as the boundary ratings the reviewer relays.
  **Acceptance criterion, split:** the mechanical half is pinned (an inner-stage dispatch's
  demoted error-path and substring items reach the fact as observations with 0/0/0 counts; the
  same array from a `cumulative` dispatch is refused) — the live half, a model reviewer *choosing*
  observation over finding on such a diff, is this chunk's own Critic review, whose `Signals:` line
  and partial are the first real run of the new protocol. `review.pr` events carry no `stage`
  yet (the PR skill is untouched here); `review-stats` renders them "(unrecorded)".
  **The live half held:** the chunk review (rev-20260917T172352Z-83aa1965) rendered
  `Stage: inner · Judgeable files: 12 · Type: code` and demoted two items to observations. Its one
  BLOCKING was a fourth carrier the plan never named — `VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE`,
  printed at every verify dispatch, still said "everything the protocol rates BLOCKING stays
  BLOCKING, no list to check". Re-keyed on the set (its two escalations named as such), pinned as the
  fourth carrier in `TestInnerBlockingSetIsOneSentence`; the directive's token pin moved 770 → 843
  with the reason.
- **Done when:** tests pass; `/prawduct:critic`; tick.

## Chunk 03: Defaults fail cheap at the inner stage — mode inference and the roster

- **Description:** **(a)** `critic_mode.infer_mode` rule 4: no active plan and no other rule fired →
  `chunk` on a dirty tree (the inner review of the interval that exists), `cumulative` on a clean
  one (already the redirect); `final` is no longer the fail-safe. The `SKILL.md` fall-through
  ("if the subcommand exits non-zero, default to `final`") follows the same rule. **(b)**
  `critic_consolidate._derive_roster`: retire the `COORDINATOR_FILE_THRESHOLD` branch (5+ files
  with no declared risk surfaces → three reviewers). A product with no declaration gets the
  single-pass roster below the judgeable-12 threshold like every other product; the "we learned
  nothing" argument in the code comment is answered by Chunk 06's ask, not by escalating forever.
  Keep the risk-surface and judgeable-12 escalators unchanged. **(c)** Prose sweep, by grep, of the
  retired sentences Chunk 01 named — `planning.md`, `review-cycle.md` (the canonical fail-safe
  statement and "never reviewed *less* than before"), `discovery.md` § Surface Risk Surfaces
  (rewrite the paragraph that promises the absent case is never reviewed less; it now promises the
  ask), `critic_mode.py` docstrings, `SKILL.md`. Flip Chunk 01's xfail pin. **(d)** Confirm the
  yield-floor sentence (diagnosis fix #6: a full review returns 13–18 true findings regardless of
  round) is present in `review-cycle.md` — the assessment's survey found it there; if so, nothing
  to add, say so in the change-log body.
- **Tests:** rule-4 fixtures (no plan, dirty tree → `chunk`; no plan, clean tree → `cumulative`);
  roster fixtures — no declaration + 5 files → single-pass; no declaration + 12 judgeable →
  coordinator; declared surface touched + 1 file → coordinator (the escalators survive); the
  roster config block's replay table gains a row for the retired rule with its measured yield
  (from the assessment: no blocking finding attributable to the fallback in the window — re-derive
  it against the ledger with the query in the change-log body); the grep pin from Chunk 01 goes
  green.
- **Measured at build (2026-09-17):** the fleet query the Tests line asked for
  (`python3 tests/spikes/fallback_roster_yield.py`, 2026-08-01 → 09-17, six undeclared product
  repos, stores deduplicated by clone) does NOT return the zero the disposition above inherited from
  the assessment: the fallback alone sent 87 `final`/`cumulative` reviews to three reviewers and those
  reviews carried 48 blocking findings (0.55 per review; 45 of them in one product), against 0.78 per
  review for the 18 single-pass reviews in the same repos. So the ratchet norm's removal-by-default
  trigger ("fires and never blocks") is not what retires this control. What does is the owner's
  decision recorded on the norm, applied here with the number attached: `[DECISION: the 5-file
  coordinator fallback is retired outright with 48 blocking findings on its record | the record shows
  no per-review yield advantage for three reviewers over one on the same repos, and how many of the
  48 a single reviewer would have missed is not measurable from the store — the plan's HIGH-impact
  assumption was made knowing a bounded miss is the price, and this is that price stated rather than
  assumed | user can veto/override — restoring the fallback at a higher count is one branch in
  `_derive_roster` and its config-block row]`. The `governed_by` disposition that says "none found"
  is left as written and corrected by this line, so the plan's own text shows the measurement
  overturning the claim.
- **Done when:** tests pass; `/prawduct:critic`; tick.

## Chunk 04: A short plan owes one boundary review, not one per chunk (#292)

- **Description:** A build plan with ≤ 3 chunks, none of whose chunks touches a declared risk
  surface, infers no per-chunk review: `infer_mode` treats every non-final chunk as reviewed at the
  boundary, the last chunk as `cumulative-final` semantics without the declaration, and the Stop
  hook's Critic gate on such a plan's non-final chunk emits a **WARNING** that names the deferred
  boundary review — never a BLOCK, never silence. A plan can opt out with an explicit
  `Critic mode:` on any chunk (the existing override wins). The `review_round_budget` counts the
  same. Record `[DECISION: short plans defer per-chunk review to the boundary | the owner's
  2026-09-17 trade; #292's evidence (chunk-mode yield ≈ 1 actionable per 7 reviews) and the
  assessment's small-scope medians (5 rounds, 20 minutes, for ≤ 5-file scopes) | user can
  veto/override]` in the plan's chunk section and on #292.
- **Tests:** the load-bearing one #292 names — a 4-chunk plan, and a 3-chunk plan with a chunk
  touching a declared risk surface, still infer `chunk` per non-final chunk and still BLOCK at Stop;
  the eligible plan warns with the boundary review named; the explicit `Critic mode:` override
  restores per-chunk review; `check-cumulative-critic` on the eligible plan's branch is unchanged
  (the boundary gate never knows the plan was short).
- **Acceptance criteria:** on a fixture 3-chunk plan, the only review facts on the branch after all
  three chunks are one `cumulative` (plus any `verify-resolutions` its blockers bought); the PR gate
  passes on that alone.
- **Built (2026-09-17):** `[DECISION: short plans defer per-chunk review to the boundary | the
  owner's 2026-09-17 trade; #292's evidence (chunk-mode yield ≈ 1 actionable per 7 reviews) and the
  assessment's small-scope medians (5 rounds, 20 minutes, for ≤ 5-file scopes) | user can
  veto/override]`. One predicate, `critic_mode.short_plan_deferral`, read by inference and by the
  Stop gate; `tests/test_short_plan_deferral.py` carries #292's guardrail (a 4-chunk plan, a plan
  touching a risk surface, a plan declaring `Critic mode:`, and work on the base branch itself all
  still infer `chunk` and still block at Stop), and every guard was mutation-verified red. **Where
  the mechanism departs from the description above**, each with its reason: **(1)** `infer_mode`
  answers a fifth, output-only token `deferred` rather than "treating the chunk as reviewed at the
  boundary" inside a mode — every mode dispatches, and any dispatch spends the round the chunk exists
  to remove; a non-zero exit was rejected because the skill reads that as inference *failing* and
  falls back to `chunk`. **(2)** "Declared risk surface" is the tier predicate
  (`risk.paths_touch_risk_surface`: the declared list when present, else the derived defaults plus
  the product's contract paths), evaluated against the paths the BRANCH has changed — committed since
  the merge-base and in the working tree — so the same fact has one home and eligibility is re-asked
  at every inference and every Stop; a later chunk that lands on a surface owes its review like any
  other. **(3)** One condition the description did not name: the branch must not be the base itself,
  because on the base merge-base…HEAD is empty and the "boundary review" would defer every chunk to
  nothing. **(4)** The Stop WARNING's channel: at exit 0 the harness *logs* stderr and delivers it to
  nobody (Claude Code hooks reference, checked 2026-09-17), so the gate emits one JSON object on stdout
  — `systemMessage` (the user's transcript) and `additionalContext` (the model's context; `Stop` is
  among the events that honor it) — the first JSON the Stop hook has ever written; stderr keeps a copy
  for the log. Blast radius: three inference fixtures widened from three chunks to four so they keep
  testing rule 4's grounding and rule 3's last-chunk arm; the last is a renegotiated contract, stated
  in the test. Token readings: SKILL 3484 → 3615 and review-cycle 10864 → 11090 raised by
  declaration (a control that removes review work), planning 5597 → 5704 recorded.
- **Done when:** tests pass; `/prawduct:critic`; #292 moved to `stage: shipped` at merge; tick.

## Chunk 05: The inner loop has a verification ceiling; the suite runs at Verify and at the boundary

- **Type:** doc-only
- **Description:** **(a)** `methodology/building.md`: the baseline paragraph keeps "every session
  starts clean" and stops prescribing a suite run — the baseline is `test-status` current, or one
  run of the declared suite when it is not (the paragraph already says check first; make that the
  lead). Add an **inner-loop verification ceiling** beside the delegate one, in the same words:
  while building, run the narrowest thing that proves the change — the project's
  `Inner-loop verification` row where it has one, else the tests for the files you touched; the
  declared suite runs at Verify and at the boundary. A cost bound, not a rigor discount.
  **(b)** `templates/project-preferences.md`: an `Inner-loop verification` row next to
  `Delegate verification`, unset, in the product's own words, with the same "prawduct will not
  invent a vocabulary for it" sentence; `/prawduct:doctor` proposes one from what the repo already
  encodes, as it does for delegates. **(c)** `templates/test-specifications.md`: one sentence under
  the testing floor — *the floor is a product floor, checked at the boundary; a chunk owes the
  tests that prove its change* — so a reviewer stops reading "one E2E per core flow" as a per-chunk
  bar. **(d)** `templates/build-plan.md`: the worked example's `uv run pytest -q` acceptance criteria
  become "the declared suite passes" (language-neutral); the tooling names stay in the preferences
  example where they belong. **(e)** The two discipline directives printed at `test-evidence record`
  (rows 1–2 of `docs/discipline.md`): keep the cheap half at record time — *for each new test, name
  what would turn it red* — and move the mutation-watch sentence to the PR skill's pre-review step
  (boundary). Update the discipline table's channel and anchor cells for both rows in the same
  commit; `tests/test_discipline_table.py` pins them. **(f)** Owed by Chunk 04, carried here because
  the partition gives this chunk `building.md` and `templates/`: the build cycle's "Critic review"
  paragraph and its "Skipping `final` mode" trap, and the build-plan template's "Done when" steps and
  `cumulative-final` example, must state the short-plan rule (a plan of at most 3 chunks touching no
  risk surface owes one `cumulative` at its last chunk, inference answers `deferred` mid-chunk, and a
  `Critic mode:` on any chunk opts back in) — the canonical statement is `review-cycle.md`'s "When
  Review Is Required" row, and these surfaces point at it rather than restate the conditions.
- **Tests:** discipline-table pins green on the moved anchors; the `building.md` ceiling
  (4786) — pay in place from the class the delegate paragraph and the new one now share, or raise
  with reason; a pin that the template example names no test runner outside the preferences
  section; the `test-evidence record` directive test asserts the retained sentence and the absence
  of the moved one, and the PR skill test asserts its presence.
- **Acceptance criteria:** a reader of `building.md` who stops at the build cycle knows what to run
  while iterating and when the whole suite is owed, without opening `delegation.md`.
- **Done when:** tests pass; `/prawduct:critic`; tick.

## Chunk 06: Product-facing surfaces say it, and a product is asked once where its risk lives

- **Type:** cumulative-final
- **Description:** **(a)** `methodology/session-digest.md`: one hardest-rules bullet — *Rigor is
  stage-keyed: inner-loop reviews block only on ships-broken; the boundary review runs everything
  and is never skipped. Unsure defaults to the cheaper inner review.* The file is 9,493 characters
  against a hard 10,000 (`test_plugin_methodology_digest.py`, the harness spills above it): count
  characters, not tokens, and pay in place if the bullet does not fit. **(b)** The scaffolded
  product anchor (`STATIC_ANCHOR` in `lib/migrate_plugin.py`): the "Run `/prawduct:critic` after
  medium+ work" line gains the same sentence in product terms; register the new anchor version the
  way `anchor_repair.py` grades anchors (open it first — the plan does not know the mechanism's
  spelling) so already-onboarded repos read as *stale*, not *edited*. **(c)** The ask: a new probe
  (pattern: `lib/onboarding_probes.py`) that fires **once** when a product has judgeable work and no
  `risk_surfaces:` key — in the product's terms: *where would a missed defect cost you most?* — with
  the discovery section as its landing; `/prawduct:doctor`'s health check reports the same
  condition as degraded with the fix. Dismissable like every advisory. `risk_surfaces: []` clears
  it (that is the opt-out, per `discovery.md`). **(d)** `docs/discipline.md` and
  `documentation/project-structure.md` if either lists the digest's hardest rules.
- **Tests:** digest character pin; anchor version pin and the stale-vs-edited grading fixture;
  probe fixtures — key absent + judgeable work → fires once; key present (empty or not) → silent;
  no judgeable work → silent; dismissed → silent; doctor reports the degraded row.
- **Acceptance criteria:** a fresh `prawduct-hook init-product` scaffold carries the sentence;
  a sibling repo run with the dev plugin shows the advisory once at SessionStart and not again
  after `risk_surfaces: []` is written (verify against a copy, never a sibling's live tree).
- **Done when:** tests pass; `/prawduct:critic cumulative` (this chunk's review is the bundle's);
  change-log entry `scope=review-stages` covering all six chunks in its body; tick.
