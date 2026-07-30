---
artifact: nonfunctional-requirements
version: 1
depends_on:
  - artifact: product-brief   # vision lives in README.md + CLAUDE.md
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
  Decision: `[DECISION: proportionality ratchets both ways — removal becomes the default for a control with repeated firings and no blocking yield, and every new control must emit its yield observably | the norm's why is that each individual addition is justified, which is exactly why argument alone never reverses the accumulation; a default that acts, plus data to act from, is the only thing that does | user can veto/override]` Owner decision, 2026-07-29, stated directly ("We've been on a one-way ratchet for tighter control, more complexity, slower reviews. We really need to re-calibrate on proportionality").
  Retroactivity: contain — existing controls are not swept on adoption, because the evidence to judge them does not exist yet (the very defect this norm names). The boundary is explicit and dated: controls added **from 2026-07-29** carry the observable-yield obligation at birth; controls predating it are assessed as the janitor's sweep gains yield data, not before. `compliance_canary` is the worked example and the first case — it emits nothing, so it cannot be judged, and LNG-5W8R fixes that rather than retiring it on argument.
- **State-file growth past its size threshold is surfaced as an advisory warning that prompts compaction — it is never a hard block or mechanical enforcement.**
  Why: oversized governance state is a real context-weight cost, but blocking a session on file size would be disproportionate for a local tool — this is advice (fail-soft), not authority; an over-threshold file is the nag's designed target, not a violation, so no ratification retroactivity applies.
  Status: steady-state.

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
