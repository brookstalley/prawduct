---
artifact: nonfunctional-requirements
version: 1
depends_on:
  - artifact: product-brief   # purpose lives in documentation/purpose.md
last_validated: null
---

# Non-Functional Requirements

<!-- Written toward the targets we want to hold, not a transcript of current measurements.
     Where a target is aspirational or where reality currently lags, the text says so. -->

## Direction

<!-- Ratified norms (2026-07-17). See docs/norms.md. -->

- **Review wall-clock is a P0 constraint: cost = unit-cost × run-count, and *both* factors are levers — run-count via gate and chunk structure, unit-cost via the reviewer's *payload* (what a given mode must load to answer its goals). The two independent reviews at the PR boundary run in parallel, never sequentially.**
  Why: review latency is what determines whether governance feels like a partner or a tax. The original entry treated per-review cost as fixed, but that conflated two different things: the reviewer's **model tier** is fixed (reviewers inherit the session model — reviewer-model tiering was removed deliberately and the manifest's `tier` stays telemetry only; that pin is untouched by this amendment) with the reviewer's **payload**, which was never a considered variable and is large — a `verify-resolutions` reviewer loads the full review protocol plus the review-cycle to answer three goals. Payload is per-mode and reducible without touching model selection, so "unit-cost is fixed" was an accident of the earlier framing, not a finding.
  Status: steady-state.
  Amended: 2026-07-29, owner decision. `[DECISION: unit-cost joins run-count as a declared lever, scoped to reviewer payload | the norm's why is bearable review latency; holding unit-cost fixed left the largest reducible term unexamined for the sake of a model-tiering pin that this amendment preserves separately | user can veto/override]` Scope narrows nothing and re-opens nothing: model tiering stays removed.
- **Proportionality ratchets both ways. A control that has fired repeatedly and never produced a blocking finding is removed by default; keeping it requires a reason. Adding a control names the yield it expects **and emits that yield observably**, so there is something to measure it against later — a control whose findings are printed and forgotten satisfies the letter and defeats the point, since it can never be retired on evidence, only defended on principle.**
  Why: every review finding tends to add a control and nothing ever removes one, so the system drifts monotonically toward more ceremony regardless of whether any individual addition was justified — and each addition *is* individually justified, which is why argument alone never reverses it. Making removal the default converts the question from a debate into a query, which is newly possible: the `disposition` fact kind (shipped 2026-07-29) plus the governance ledger can answer "how often did this control fire, and what did it catch." Proportionality (Principle 11) already said this; what was missing was a default that acts on it and data to act from.
  Status: in-transition — the yield query does not exist yet, and until it does this norm's removal-by-default arm runs on judgment rather than evidence. **One home, named once: the janitor's Norm Health sweep**, which is already the organ for trend-over-time and already reads the ledger. LNG-5W8R carries the enabling half (surviving canary findings must emit a ledger fact; today they are printed and lost). Chunk 02 is *not* the home — its deliverables are `record_lint.py` and subtraction edits, and it contains no yield query; an earlier revision of this line said otherwise and was wrong. Interim rule: a control may be retired on a reasoned argument recorded as a decision, but the argument must state what evidence *would* have settled it, so the query has a specification to be built against.
  Stopgap: recorded 2026-09-01, expires 2026-12-01. The interim rule above stands as a **bounded exception** for the duration, alongside the Live exceptions already recorded below. `[DECISION: the judgment-based removal arm is extended as a bounded exception until 2026-12-01 | the interim rule is what keeps the removal arm honest without the query — a control may be retired on a reasoned argument, but the argument must state what evidence *would* have settled it, which leaves the future query a specification rather than a blank; what is stalled is LNG-5W8R's enabling half, that surviving canary findings must emit a ledger fact instead of being printed and lost, and no amount of prose here substitutes for that emission | user can veto/override]` Owner ruling, 2026-09-01 (#732). Clock: LNG-5W8R, as prose on the item (#564).
  Decision: `[DECISION: proportionality ratchets both ways — removal becomes the default for a control with repeated firings and no blocking yield, and every new control must emit its yield observably | the norm's why is that each individual addition is justified, which is exactly why argument alone never reverses the accumulation; a default that acts, plus data to act from, is the only thing that does | user can veto/override]` Owner decision, 2026-07-29, stated directly ("We've been on a one-way ratchet for tighter control, more complexity, slower reviews. We really need to re-calibrate on proportionality").
  Live exception: **the `check-branch-pushed` gate** (the pre-merge push-completeness gate,
  shipped 2026-09-12) is a recorded **bounded exception** to the emission arm, on the same
  grounds as #13/#13a below: the governance ledger is a *review*-event store whose module
  documents that non-review event kinds are deliberately unbuilt, and it is schema-versioned —
  so teaching it a `gate.*` kind for one gate is a persisted-format lock-in taken for a single
  control, which is the accumulation this norm exists to stop. Amending the emission arm to
  admit a control that cannot satisfy it is the laundering tell `docs/norms.md` names.
  **Expected yield, named now so the query has something to answer:** it blocks a merge whose
  upstream ref is not the branch tip. Base rate is one known occurrence across this repo's PR
  history (2026-09-12, PR #803, which merged one commit short), and #805's prose checks cover
  the same ground *when an agent runs them* — so one firing is evidence the gate was needed, and
  a year of none alongside no recurrence of a short merge is evidence for retiring it in favour
  of the prose. Clock: the same trigger as #13 — the ledger gaining a non-review event kind, or
  the janitor's Norm Health yield query existing (`#563`) — at which point this gate is a first
  case alongside it. Decision block: the build plan for `scope: branch-pushed-gate`, § The Yield
  This Gate Cannot Emit — cited by scope rather than by path, because that plan is retained live
  under `artifacts/` until the release moves it to `artifacts/archive/`, and nothing rewrites a
  referring path when it moves (the sibling #13 cite two lines below already carries the
  post-archive form, and had to be edited by hand to get there).
  Live exception: **doctor Health Checks #13 and #13a** (the learnings descent-obligation check, shipped 2026-08-02, and the learnings-pairing check, shipped 2026-08-27) are recorded **bounded exceptions** to the emission arm — it names its expected yield and cannot emit it, because doctor has no fact-emitting path at all and building one for a single check is the accumulation this norm exists to stop. Clock: `#563` — the trigger is *when doctor gains that path*, at which point #13 is its worked first case and #13a follows it. `[DECISION: the #13 bounded exception is widened to cover doctor Health Check #13a (learnings pairing), same clock and same reason | doctor still has no fact-emitting path, so #13a can no more emit its yield than #13 can, and building one for a second single check is precisely the accumulation this norm exists to stop; the alternative — amending the emission arm to admit a control that cannot satisfy it — is the laundering tell the norms guide names, since it would edit the rule to bless the code | user can veto/override]` Owner-vetoable, recorded 2026-08-27 on `fix/silent-clear-checks`. **The exception is bounded by naming its expected yield now, so the query has something to answer:** #13a expects to fire on duplicate active headings, which is zero on this repo's 270-entry corpus today — so a firing is evidence, and a year of never firing is evidence for retiring it. **That trigger is prose here and on the item rather than a `revisit:` field** (when written, the Issues backend had no write path for one; #564 shipped it 2026-09-02, so the constraint is historical — the trigger stays prose because it names a CONDITION, not a date, and `probe_revisit_due` fires only on dated values): the adapter's `update` deliberately strips a caller-pasted `prawduct:` block and re-appends the existing one (`lib/backlog/core.py` `_body_update_preserving_block`), and no op takes a `revisit` flag — the field is read only off the frozen markdown model (`lib/backlog/legacy.py`). So the walker is the janitor's Norm Health sweep reading #563, exactly as it is for every event-bound trigger (`probe_revisit_due` fires on *dated* values and is dark post-cutover regardless). The write path was missing when this was written and is filed as `#564`, **shipped 2026-09-02** (`backlog/core.py` `_UPDATE_BLOCK`; `--revisit` at `backlog/cli.py:124`). Decision block: `artifacts/archive/build-plan-drift-burndown.md` § `governed_by` → nonfunctional-requirements.
  Recorded keep: **the `pr-scoped` review mode**. This is NOT a Live exception and is
  deliberately not labelled one — the two above are exceptions to the *emission* arm
  (controls that cannot emit their yield). This is the *removal* arm running to
  completion and returning `keep`, which is the norm working rather than a departure
  from it; labelling it `Live exception:` would make a later erosion sweep count it
  against the norm it satisfies. Ruled by the owner at the 2026-09-16 Norm Health sweep — the first
  time this arm has been run against ledger evidence rather than judgment. **The trigger is
  met on its own terms:** across 30 runs (`pr/fable/pr-scoped` 16, `pr/opus/pr-scoped` 14) it
  has returned **zero BLOCKING findings, ever**, for ~9,300s of wall-clock. It is not a
  zero-yield control — it returned 8 WARNING and 16 NOTE, ~25% actionable — but the arm as
  written keys on blocking yield, and that is absent.
  **Reason for keeping:** it guards the PR boundary, where a warning is worth more than the
  same warning mid-chunk, because it is the last read before work leaves the branch; and 30
  runs is thin evidence for retiring a release-boundary control whose miss would surface in a
  merged PR rather than a rerunnable round. Retiring it trades a small, measured cost against
  an unmeasured tail risk, which is the trade this norm's *why* warns is easy to get wrong in
  the accumulating direction and no safer in the shedding one.
  **What evidence would settle it** (required by the interim rule above, so the future query
  has a specification rather than a blank): (a) a blocking finding from `pr-scoped` at any
  point retires this exception and vindicates the control outright; (b) 100 cumulative runs
  with still zero blocking AND no post-merge defect traceable to a warning it raised is
  evidence to retire it — the second clause matters, because a warning acted on is a miss
  prevented and would otherwise read as further proof of uselessness; (c) if `pr` (unscoped,
  81 runs, 1 blocking) and `pr-scoped` converge in yield, the two modes are one control and
  the cheaper should absorb the other.
  `[DECISION: `pr-scoped` is kept despite meeting the removal-by-default trigger (30 runs,
  zero BLOCKING) | the arm keys on blocking yield, but this control guards the release
  boundary, where its 8 warnings and 16 notes are worth more than the same findings
  mid-chunk because it is the last read before work leaves the branch — and 30 runs is
  thin evidence for retiring a control whose miss surfaces in a merged PR rather than a
  rerunnable round; retiring it trades a small measured cost against an unmeasured tail
  risk | user can veto/override]` Owner ruling, 2026-09-16.
  **Annotation, 2026-09-18 (owner-directed, `pr-review-payload` Chunk 02): the ruling above graded a
  control that no longer exists.** `grep -rn "pr-scoped" plugin/` returns nothing — the mode was
  collapsed into `pr` (`artifacts/archive/build-plan-kernel-evidence-store.md`), and its 30 ledger
  rows run 2026-06-10 → 2026-07-10 and stop. So the removal arm's first evidence-based run was
  computed from historical rows for a subject that had been gone two months. **Nothing is amended
  here and the ruling is not withdrawn** — keeping a retired thing is inert, and editing a norm to
  match the tree is the laundering tell. What is recorded is what the ruling actually decided: a
  `keep` about a retired subject, whose clause (c) — has `pr` converged in yield with `pr-scoped`? —
  is unanswerable and therefore protects nothing about the reviewer that runs today. The arm's next
  run against the live `pr` mode is a separate exercise with its own evidence, and the
  `pr-review-payload` measurements above are the first numbers it would have to work from.
  Clock: the janitor's Norm Health sweep re-reads the three conditions above each run.
  Retroactivity: contain — existing controls are not swept on adoption, because the evidence to judge them does not exist yet (the very defect this norm names). The boundary is explicit and dated: controls added **from 2026-07-29** carry the observable-yield obligation at birth; controls predating it are assessed as the janitor's sweep gains yield data, not before. `compliance_canary` is the worked example and the first case — it emits nothing, so it cannot be judged, and LNG-5W8R fixes that rather than retiring it on argument.
- **State-file growth past its size threshold is surfaced as an advisory warning that prompts compaction — it is never a hard block or mechanical enforcement.**
  Why: oversized governance state is a real context-weight cost, but blocking a session on file size would be disproportionate for a local tool — this is advice (fail-soft), not authority; an over-threshold file is the nag's designed target, not a violation, so no ratification retroactivity applies.
  Status: steady-state.
- **Review rigor is stage-keyed. The *inner stage* is any review of an uncommitted diff (`chunk`, `final`, `verify-resolutions`): it blocks only on the inner BLOCKING set below and reports everything else as an observation — pre-priced, carried to the boundary, never a finding that buys a round. The *boundary stage* is any review over merge-base…HEAD (`cumulative`) and the PR review: it runs the full severity table and is never skipped or inferred away. The failure direction is symmetric: an inner-stage review run at boundary rigor is a defect, priced in minutes and the rounds it manufactures; a boundary review run at inner rigor is a defect, priced in what ships. Unsure defaults to the inner-stage review of whatever interval exists.**
  Blocks: at the inner stage, exactly — a test failure in the evidence; a test deleted or weakened; changed behavior with no test at all; a silently dropped requirement; exploitable security in changed code; a cross-component contract break; a norm departure without a recorded decision; an unlisted dependency. Everything else the severity tables rate today — test *quality* bars (error paths, real dependencies, the E2E floor, property-based, structure), design, prose, records, artifact freshness — is an observation at the inner stage and a finding at the boundary. "No test at all" stays in the set because a unit test is the contract and is cheap; only the quality bars defer.
  Why: the wall-clock norm above says review latency decides whether governance is a partner or a tax, and the ratchet norm says a control that fires and never blocks is removed by default. Severity keyed on defect class alone cannot honor either: "untested behavior → BLOCKING" fires identically on a config helper mid-chunk and a payment ledger at the PR, so every mid-chunk observation buys a fix→verify round at boundary price. The ledger shows the cost landing where the framework said it was safe: across eight governed products review is 60–70% of the hour a small change costs; this repo's ≤ 5-file scopes buy as many rounds as its large ones; and since the v3.5.0 cut four of five `verify-resolutions` rounds returned nothing. The framework already knows the stage — mode plus interval — and until now said so nowhere a reviewer could read it. Re-derive: `prawduct-hook review-stats`, and each repo's `.prawduct/.governance-ledger.jsonl` filtered on `ts`; the survey is `review-proportionality-assessment-2026-09-17.md`.
  Status: steady-state.
  Retires: two sentence families that stated the opposite failure direction — *"Under-declaring Type is safe (worst case: redundant Critic work)"* (`methodology/planning.md`) and the *"fails safe to thoroughness"* family (the canonical fail-safe statement in `skills/critic/review-cycle.md`, its restatement in `skills/critic/SKILL.md`'s fall-through, the `critic_mode.py` rule-4 rationale and the `infer-critic-mode` docstring), together with the *"never reviewed less than before"* promise for a product that declares no `risk_surfaces:` (`review-cycle.md`, `methodology/discovery.md`, the `project-state.yaml` template). Their replacement is the statement's last sentence: unsure defaults to the inner-stage review of whatever interval exists; the boundary is never inferred away. This entry records the retirement so the norm leads the code (Requirements Precede Code); the sweep that performs it lands under the same scope (`review-stages`) before this norm merges, and `tests/test_v5_methodology.py` holds the grep red (`xfail`) until it does.
  Retroactivity: migrate — completed within the birthing changeset. Every site the norm contradicts is enumerated under Retires and swept by the `review-stages` plan before the branch merges, so the norm lands on `develop` with no residual sites; born `steady-state` on that reading. The tracker is the plan's own `## Status` box for the sweep chunk (unticked until the sites are gone), and the xfail pin is the flip detector — it goes red the day the sweep lands, but it cannot see the sweep being *cut*, so the box is what a reader checks. If the sweep is cut from the scope, this line is wrong and the entry must be re-recorded `in-transition` with a tracking item.
  Decision: `[DECISION: review rigor is keyed on stage, and the inner stage blocks only on the set above | the owner accepts a bounded miss-rate increase — a coverage or design gap found at the boundary review instead of mid-chunk, the same catch later — in exchange for wall-clock; the three prior efficiency plans held miss-rate constant and the complaint survived them, which is the evidence that the philosophy, not the mechanics, is what generates the hour | user can veto/override]` Owner decision, 2026-09-17, stated directly ("optimizing for saving a lot of wall clock for at most a minor drop in quality").
  Ratified: 2026-09-17, owner — the entry text and Principle 11's two-stage sentence, confirmed as written.

## Performance

Prawduct's performance budget is dominated by one thing: **the wall-clock cost of independent
review.** This is treated as a **P0 constraint**, because review latency is what determines whether
governance feels like a partner or a tax.

The governing model is **cost = unit-cost × run-count**, and both factors are design variables.
**Run-count** is set by gate and chunk structure. **Unit-cost** is set by the reviewer's *payload* —
what a given mode must load to answer its goals — and is reducible per-mode. What stays fixed is the
reviewer's **model tier**: reviewers inherit the session model, reviewer-model tiering was removed
deliberately, and the manifest's `tier` is telemetry only. Payload and tier are independent; the
Direction amendment of 2026-07-29 separates them.

Targets we want to hold:

- **Per-chunk Critic review: ≤ 120s median.** A chunk review scopes to the local change and should
  feel like a quick gate, not a context re-establishment.
- **PR boundary (cumulative Critic + PR review): ≤ 7 minutes wall clock.** The two independent
  reviews at the PR boundary **run in parallel, never sequentially** — wall clock is the slowest
  run, not the sum. Any sequencing that exists is for narrative framing, not a data dependency, and
  is a target for removal.

  **Measured against this target, `pr-review-payload` scope, 2026-09-18.** Two readings, each with
  the command that re-derives it rather than a figure to be trusted:

  | reading | on 2026-09-18, before the change | re-derive with |
  |---|---|---|
  | PR review duration, this repo | median **420s** over 122 reviews, **0 measured / 122 self-reported** | `python3 tools/pr-review-yield.py` |
  | PR review duration, a consumer (`discodon`, v3.5) | **14.1 min/review** over 12 reviews, `clk runs` **0** | `python3 tools/measure-consumer-overhead.py ../discodon --prs` |
  | sequencing | `pr/SKILL.md` ran Step 2 then Step 3 (**#678**) | — |

  **After, measured on this bundle's own PR review, 2026-09-18.** The first PR review this repo has
  timed rather than asked a model to recall:

  | reading | after | re-derive with |
  |---|---|---|
  | PR review duration, this repo | **1 measured / 122 self-reported**; the measured run's interval **385s** | `python3 tools/pr-review-yield.py` |
  | the same run, self-reported by the reviewer | **330s** | the evidence file's `duration_seconds` |
  | the same run, as the harness timed the agent | **353s** | the dispatch's own completion record |
  | PR review duration, a consumer (`discodon`, v3.5) | **14.1 min/review**, `clk runs` still **0** — unchanged, and it cannot move until a plugin release carrying the marker reaches that repo | `python3 tools/measure-consumer-overhead.py ../discodon --prs` |

  **Read the three numbers as three different spans, not as one number measured three times** —
  pooling them re-creates exactly the hazard `dispatched_at` was added to retire, which is why
  `telemetry._extract_row` carries provenance with every row and reports the two populations apart.

  - **385s is `dispatched_at` → `ledger-append`**, marked at Step 3 before the spawn and closed at
    Step 4. It therefore includes the caller's Step 4 verification, and under a blocking cumulative
    it would include fix time until the re-dispatch re-marks. It is the span an *operator waits*,
    which is what the ≤ 7-minute target is about — and at 6m25s this run met it.
  - **353s is the harness's own measure of the agent**, i.e. the reviewer's runtime alone. The ~32s
    difference from 385s is the caller's Step 4 work, which is the expected gap rather than noise.
  - **330s is the reviewing model's estimate of its own runtime** — the thing the baseline column is
    made of, 122 times over. It is **~6% under** the harness's measure of the same run. One data
    point is not a bias estimate, but it is the first time the two have been comparable at all, and
    it is the reason the baseline's 420s median is not directly comparable to the 385s above.

  **The ≤ 7-minute target was met on a bundle whose review-round count was the real cost.** This
  boundary cost 6m25s of wall clock; the branch spent roughly six hours, almost all of it in
  *repeated* Critic rounds. `run-count` and `unit-cost` are both named as design variables at the
  top of this section — this bundle moved unit-cost, and the measurement it installs is what will
  let the next one argue about run-count with numbers instead of impressions.

  The `0 measured` column is the positive control: before this scope no review duration in either
  repo was a code-written interval, so the 420s and the 14.1 min are both the reviewing model's own
  recollection and the target had never actually been measured against. The after-table above is
  that control coming back non-zero — had it still read `0 measured`, the clock would not have
  fired and the figures beside it would have meant nothing.
- **Validating a comment-only change: ≤ 30s.** A change confined to comments must be cleared in
  under half a minute or the check is not worth keeping — at that price the question of whether
  it is proportionate stops being interesting. The budget is met by *deterministic* checks over
  the diff, not by a cheaper model review. The `coverage_algebra.py` ruling names **two** channels
  by which a comment edit can change behaviour, and a recipe is only sufficient if it answers both:
  (1) **comment-borne directives** — `prawduct:allow` and the general class (`noqa`, `type: ignore`,
  `eslint-disable`, `nolint`, `swiftlint:disable`, `pragma warning disable`) — answered by a scan of
  the added/modified comment text plus per-file language classification, O(diff); and (2) **tests
  asserting over source prose**, which is *not* answered deterministically within budget, because
  identifying such tests is O(repo) and running them is excluded by the diff-scaling constraint
  below. Channel 2 is therefore an **accepted, recorded residual** — bounded by the observation that
  it is largely an artifact of this framework repo, whose product *is* text — and not a solved
  problem. A design that silently covers only channel 1 is unsound; one that covers channel 1 and
  declares channel 2 is the bar. Owner-set, 2026-07-29. The authoritative statement of the two
  channels is the ruling in `is_judgeable_path`'s docstring (`coverage_algebra.py`), which a reader
  hits at the mechanism; this target restates the *consequence* for the budget and is deliberately
  not a duplicate of that text — if the two ever disagree about how many channels exist or what they
  are, the docstring governs.
- **A review's cost is fixed context-establishment, not diff size.** A 2-file review and a 20-file
  review cost about the same. That observation stands — but context-establishment *is* the payload,
  and payload is a per-mode design variable, so the conclusion once drawn from it ("the lever is how
  often we review, not making each review cheaper") no longer follows and has been withdrawn. Both
  optimizations are live: gate design that avoids a full re-review after a trivial post-review fix,
  **and** trimming what each mode loads.
- **Gate cost scales with the diff, not the repo.** Any check whose work is proportional to repo
  size fails at consumer scale — governed products routinely run ~20x this repo, where a five-minute
  cost here is a fifteen-minute cost there, and consumers are where the benefit actually lands. A
  check that must read the whole tree, walk all history, or execute a test suite is disqualified on
  this ground alone, independent of whether it is sound. Costs that are genuinely repo-scale are paid
  **once per repo and cached** (e.g. probing whether a repo reads doc-comment text at runtime or
  build time), never once per edit.

Hot-path budget (the interactive surface):

- **SessionStart must be fast.** The session-reset/briefing hook runs on every session start and
  must not add perceptible latency. Concretely: minimize git subprocess fan-out (batch
  `git ls-files`/status queries into single invocations), keep the hook import-light (the
  `bin/`↔`lib/` split exists to keep the hot path from importing heavy modules), and prune
  full-tree walks. Regressions here are felt on every single session.
- **No probe or gate on the hot path may block or noticeably delay session start** (see the
  Availability section and `observability-strategy.md`).

## Scalability

Prawduct is **single-actor per repo** — one product owner plus the AI runtime; there are no
concurrent human users, no multi-tenant load, no request throughput to scale. "Scale" here means
the growth of governance state within a repo, and the number of parallel worktrees a session fans
across.

- **Concurrency** is bounded and local: a handful of git worktrees per clone, a small fixed reviewer
  roster (single-pass, or three parallel reviewers for larger changes). The evidence store is shared
  per-clone and appended with single-syscall writes; there is no contention model beyond that.
- **State-file growth is the real scaling axis, and it is governed by mechanical thresholds, not
  vibes.** Files with a size target carry a mechanical check: `project-state.yaml` and
  `learnings.md` each warn past **40 KB**, prompting compaction before context weight compounds
  (the warning is intentionally mechanical because guidance alone erodes). The backlog is the file
  most prone to unbounded growth and needs the same discipline.
  - *Current state (honest):* `project-state.yaml` (~46 KB), `learnings.md` (~71 KB), and
    `backlog.md` (large) are all over their comfortable thresholds and are flagged for compaction.
    The target is that these stay under threshold; reality is currently past it, which is why the
    briefing nags.
- **Architectural change trigger:** if a repo ever needed multiple concurrent human actors,
  per-actor isolation, or a shared server-side store, that is a **structural characteristic flip**
  (`has_multiple_party_types`), not a tuning exercise — it re-derives the security and data models.

## Availability

Best-effort, local, **degraded-not-down**. Prawduct has no server, no uptime SLA, and nothing to
page. Its availability posture is expressed entirely through **fail-soft design**: every probe,
briefing, and informational path degrades to "skip with a note" rather than crashing, so a broken
probe or malformed state file never takes down a session.

- **"Healthy"** = the plugin loads, governance gates arm, and core state is present and parseable.
- **"Degraded"** = governance still works but something is off (a stale artifact, a size warning, a
  missing optional file). This is a first-class, named state surfaced by `/prawduct:doctor`, not a
  failure.
- The one thing that is *allowed* to stop you is a **governance gate blocking session end** — that
  is availability working as intended (authority fails closed), not an outage.

## Cost Constraints

- **The only meaningful operating cost is reviewer tokens.** Independent reviewers inherit the
  session model (reviewer-model tiering was removed — the manifest's `tier` is telemetry only and
  selects no model). The levers are therefore **run-count**, controlled by gate and chunk design,
  **and per-mode reviewer payload** — never the reviewer model, which stays fixed. This tracks the
  § Direction amendment of 2026-07-29; an earlier revision of this bullet still read "the lever is
  therefore run-count … not the reviewer model," which correctly excluded model tiering but wrongly
  implied payload was not a lever either.
- **No infrastructure cost.** No hosting, no external services, no databases — prawduct is a plugin
  distributed via a git-backed marketplace and runs entirely on the user's machine.
- **Context weight is a cost.** Oversized governance state (backlog, learnings, project-state)
  inflates the context every session and every review must carry — which is why the compaction
  thresholds above are a cost control, not just tidiness.
- **Versioning is conservative:** releases are versioned **conservatively** — small features are
  patch bumps rather than minor-per-feature — to keep the version number meaningful. **Ratified
  2026-07-17**; the binding form is `operational-spec.md` `## Direction`, and this line is
  descriptive and tracks it. *(Corrected 2026-07-21 — it had still read "not yet codified as a
  written rule … a candidate norm," which was false for four days and is one of the two sites that
  let v3.1.1 infer a version convention instead of reading the norm.)*
