# Issue #292 — Critic: Defer Per-Chunk Reviews on Short Plans to One Cumulative: Requirements

`status: draft · stage: requirements · area: building/critic · added: 2026-08-01 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/292`

Related: TEL-6P2D (review-stats windowing / zero-yield pruning — a sibling telemetry item, not this
item's scope); Principle 11 (Proportional Effort) and Principle 23 (Challenge Gently, Defer
Gracefully) are the principles the issue's own Evidence section invokes for the tradeoff this item
makes structural.

## Problem

For a chunked build plan, `chunk`-mode Critic review runs after every non-final chunk, and a
`cumulative` review at the end re-derives coverage over the whole bundle regardless. For a **short**
plan (few chunks, no elevated risk) that is the biggest avoidable review cost: N per-chunk passes a
single end-of-plan `cumulative` would cover just as well, at a fraction of the wall-clock. The
2026-06-22 chunk-mode yield (~1 actionable finding across 7 reviews) is mild supporting evidence
only — early-detection value is not captured by finding-count — so the acceptable-tradeoff bounds
must be pinned deliberately, not inferred from that one data point, and a plan outside those bounds
must be provably unaffected.

## Grounding facts

Re-verified against the current tree (2026-09-09):

- **The framework already infers `cumulative` on a clean tree, unconditionally.** `lib/critic_mode.py`
  rule 2 (`_rule_cumulative_fires`, lines 568-607) fires whenever the working tree holds no code
  in-flight, the branch is ≥2 commits ahead of its base, and no fresh cumulative record already covers
  HEAD — with **no chunk-count or risk-tier condition of any kind**. Rule 4's `_clean_tree_redirect`
  (lines 328-377) goes further: even a **single** commit ahead of base, on a clean tree, redirects an
  explicit `chunk`/`final` request (and grounds the same fallback inside plain inference) to
  `cumulative`, because that is the only mode whose interval isn't empty. Concretely: a builder who
  simply never invokes `/prawduct:critic` between chunks — committing chunk 1, chunk 2, chunk 3, then
  running `/prawduct:critic` once — is **already** routed to one `cumulative` pass today, on a
  10-chunk escalate-tier plan exactly as readily as on a 2-chunk trivial one. Deferring per-chunk
  review is not gated by anything today; it is simply undetected.
- **Nothing machine-enforces "each chunk gets its own review" — it is a methodology prescription,
  not a gate.** The stop hook's Critic gate checks only that *composed* review coverage spans the
  *session's* baseline tree → the current working tree with zero unresolved blocking findings
  (`skills/critic/review-cycle.md:18`; `methodology/building.md:7,17` — "the git baseline, reflection
  gate, and Critic gate all scope to the session" and "per-work-cycle governance is the methodology's
  responsibility, not the hook's"). The PR gate (`check-cumulative-critic`) checks only that composed
  coverage spans `merge-base...HEAD` with zero unresolved blocking (`review-cycle.md:20`) — "**no
  single run needs to carry any particular mode label**: chunk, final, cumulative, and
  verify-resolutions facts compose identically." Per-chunk review is prescribed in
  `review-cycle.md`'s "Per-Chunk Cycle" (lines 120-127) and `methodology/building.md:103`, but neither
  gate can see *how many* chunks a single review fact's tree-span happens to cover — a review fact
  records `base_tree`/`head_tree`/`files_reviewed` and nothing about commit or chunk count
  (`lib/evidence.py:84`'s `KNOWN_KINDS`, and no field on any fact body carries a chunk/commit count).
- **Consequence for the issue's own C2 guardrail.** The issue requires "a regression test proves a
  NON-eligible plan (4+ chunks or escalate-tier) still gets per-chunk reviews." Given the fact above,
  this **cannot** be built as a check that inspects an existing review fact after the fact and infers
  how many chunks it swallowed — that information doesn't exist in the store today, for *any* plan,
  eligible or not. The guardrail has to be built the other way around: **the moment a plan claims
  deferral is the only moment eligibility can be checked**, and an ineligible plan's claim must be
  *refused* (falling through to today's ordinary per-chunk behavior) rather than detected
  retroactively.
- **`Type: cumulative-final` is the direct, already-shipped precedent for exactly this shape, scoped
  to one chunk.** `methodology/planning.md` "Choosing a Chunk Type" and
  `skills/critic/review-cycle.md:14,73,334` already let the **last** chunk of a multi-chunk plan
  declare that its own review IS the plan's one `cumulative` pass — "commit the chunk, then run
  `/prawduct:critic cumulative` once — no separate `final`." This issue's ask is that generalization
  applied to *every* chunk of an eligible short plan, not a new mechanism: chunks 1..N-1 stop needing
  their own `chunk`-mode pass, and the last chunk keeps declaring `Type: cumulative-final` exactly as
  it does today.
- **Risk-tier classification already exists with exactly the two verdicts the issue names.**
  `prawduct-hook classify-diff-risk` (`lib/risk.py`) prints `standard` or `escalate`
  (lines 386,406,413,416,427) as its sole stdout token. Per its own docstring (lines 1-46): a risk
  surface is either a product-declared `risk_surfaces:` list or, absent that, framework-shaped
  derived defaults (`skills/`, `lib/gates*`, `bin/*hook*`, plus contract paths parsed from
  `boundary-patterns.md`) — "governance/contract-path scope always gets per-chunk review" in the
  issue's own words is precisely this derived-default set. Critically, the match scope is **always**
  `merge-base(base)...HEAD` plus the working tree (line 33-34), independent of which Critic mode is
  asking — so a tier check run at any point on a branch already reflects every file touched so far on
  that branch, with no new diff-scoping logic needed to make a mid-plan check meaningful.
  **Caveat**: the reviewer-*model* consumer of this verdict is paused (2026-07-14, emergency patch;
  `lib/risk.py:11-16`) — `classify-diff-risk` still runs and still prints a real verdict, only the
  downstream model-tier selection is dormant. This item consumes the verdict string only, never the
  paused model-selection behavior, so the pause does not block this item and restoring tiering is out
  of scope here.
- **Chunk count is already available through the one function that owns the question.**
  `buildplan_refs.resolve_chunk_progress(project_dir, plan.path)` (imported and called by
  `critic_mode.infer_mode`, lines 205-208) returns `.total`/`.complete`/`.current_id` for the plan
  actually governing the current branch. No new counting logic is needed; re-deriving chunk progress
  locally rather than asking this one owner is the exact defect class `critic_mode.py`'s module
  docstring (lines 1-15, 765-772) names as having reached three consumers before (CRT-7B4M).
- **The open question the issue itself names — session boundaries — is real and unresolved by
  anything above.** The stop hook fires at session end and asks only "does composed coverage reach
  the working tree from this session's baseline" (`review-cycle.md:18`). If an eligible plan's chunks
  1 and 2 land in one session with chunk 3 planned for a later session, chunk 1+2's diff has **no**
  review fact at all under this proposal (deferral is the whole point) — so at that session's stop
  event, the gate sees zero coverage of a non-empty diff and would WARN/block on exactly the work this
  item means to exempt. Nothing today distinguishes "no review because deferred, honestly" from "no
  review because the builder skipped one." This is the one piece of new *gate* logic the issue's own
  proposal calls for ("resolve how a deferred plan interacts with the stop-hook gate and session
  boundaries") and the one place this item cannot simply reuse existing inference.

## Decisions

**1. Eligibility is `chunk-count ≤ 3 AND risk tier standard`, checked at the plan's declaration and
re-checked, not assumed, at every point deferral would otherwise apply.** Chunk count comes from
`buildplan_refs.resolve_chunk_progress(...).total` — the plan's full Status-box count, unfiltered by
`Type:` (a plan mixing one `trivial` chunk into a 3-chunk short plan is still a 3-chunk plan; carving
out `Type:`-based exceptions is unwarranted complexity for a bound this narrow). Risk tier comes from
the existing `classify-diff-risk`, called again — not cached from plan-authoring time — at each point
this item's stop-hook relaxation (Decision 3) would otherwise fire, because the files a plan actually
touches aren't fully known until the chunks are written. **A single `escalate` verdict anywhere in
the plan revokes eligibility for the rest of the plan and does not re-instate on a later `standard`
read** — fail closed, mirroring `classify-diff-risk`'s own "declared risk + unverifiable diff →
escalate" failure-honesty posture (`lib/risk.py:36-40`) rather than trusting a point-in-time snapshot.

**2. No new Critic mode, and no new per-chunk `Type:` value.** The last chunk of an eligible deferred
plan keeps declaring `Type: cumulative-final` exactly as today (Fact 4 above) — that mechanism is
unchanged and is not this item's to rebuild. What's new is scoped to chunks 1..N-1: they stop being
told to run their own `chunk`-mode pass. This keeps the change additive to `critic_mode.py`'s existing
four-mode ladder rather than growing a fifth mode.

**3. The genuinely new logic is a stop-hook relaxation, not a mode-inference change.** Mode inference
needs no change: a builder who doesn't invoke `/prawduct:critic` between chunks of an eligible plan
already gets `cumulative` correctly inferred once the plan completes (Fact 1). The new code is the
eligibility predicate itself (a function in `lib/critic_mode.py`, consuming the same
`buildplan_refs`/`classify-diff-risk` primitives named in Decision 1) plus one new consumer: the stop
hook's Critic-gate check, which — only for a plan that has both *declared* deferral (Decision 4) and
*passed* the eligibility predicate against everything committed so far — treats "no review coverage
yet" for chunks 1..N-1 as expected rather than a gap, and resumes its ordinary requirement once the
plan's declared last chunk is reached (at which point `Type: cumulative-final`'s existing contract
takes back over unchanged).

**4. Deferral is a plan-level declaration, re-validated rather than trusted.** Eligibility is a
property of the whole plan, not any one chunk, so the declaration surface is plan-level frontmatter
(alongside the existing `depends_on:`/`governed_by:`/`branch:` keys — `templates/build-plan.md:8-86`)
— exact key name and shape are a design-stage decision (Scope-out). Whatever shape it takes, **a
declaration is advisory, not authoritative**: the stop-hook relaxation in Decision 3 re-runs the
eligibility predicate every time it would apply the relaxation, and an ineligible plan's declaration
is *ignored* (falls through to today's unmodified per-session gate behavior) rather than honored and
separately flagged — the same fail-open-to-inference shape `critic_mode.py` already uses for an
unrecognized `Critic mode:` token (`ChunkModeRead.unrecognized`, lines 117-146, 775-878): a wrong
claim changes no verdict, it just doesn't get what it asked for.

**5. Findings surfaced only at the terminal cumulative are handled by existing machinery, not new
machinery.** If the deferred cumulative pass finds a BLOCKING defect that originated in chunk 1, the
existing `verify-resolutions` cycle (fix → one verify pass) closes it exactly as it would for any
other cumulative finding today (`review-cycle.md` "Per-Chunk Cycle" step 3, "Verify-resolutions
anchoring and demotion"). The bigger blast radius this implies — a chunk-1 defect surfacing only at
end-of-plan — is the accepted cost the issue's own Evidence section names (Principle 23, the owner's
tradeoff); this item does not need to soften it further, only to make the tradeoff apply exclusively
to plans the eligibility bound has cleared.

## Requirements

MUST unless marked SHOULD.

- **SPC-1** A plan is deferral-eligible only while `buildplan_refs.resolve_chunk_progress(...).total
  ≤ 3` for its full chunk count and `classify-diff-risk` has returned `standard` for every check run
  against it so far; one `escalate` result revokes eligibility for the remainder of the plan,
  permanently (Decision 1).
- **SPC-2** A plan declares deferral once, at the plan level, not per chunk (Decision 4). The exact
  frontmatter key and value shape are a design-stage decision (Scope-out); it must live beside the
  plan's other plan-level fields, not invent a second location for plan-scoped configuration.
- **SPC-3** The last chunk of a deferral-declaring plan continues to declare `Type: cumulative-final`
  unchanged — no new `Type:` value, no new Critic mode (Decision 2).
- **SPC-4** Chunks 1..N-1 of an eligible, deferral-declaring plan are not required to receive their
  own `chunk`-mode review before the next chunk begins; the methodology text describing the
  Per-Chunk Cycle (`skills/critic/review-cycle.md`) and the build cycle (`methodology/building.md`)
  states this exemption's exact bounds so a builder following it is not fighting prescriptive prose
  that still says otherwise.
- **SPC-5** The stop hook's Critic-gate check, on a session ending mid-plan, does not WARN or block
  for missing review coverage over chunks 1..N-1's diff when (a) the active plan currently declares
  deferral and (b) SPC-1's eligibility predicate still holds against everything committed on the
  branch so far. The moment either condition fails, the gate's ordinary behavior applies with no
  further exemption for the rest of the plan (Decision 1's fail-closed revocation).
- **SPC-6** Once the plan's declared last chunk is committed, ordinary `Type: cumulative-final`
  handling resumes unchanged: one `cumulative` pass is both that chunk's review and the PR-gate
  evidence, exactly as for a non-deferred `cumulative-final` plan today.
- **SPC-7** A plan that does not meet SPC-1 gets no behavior change from this item at all: its stop
  hook, mode inference, and per-chunk review requirements are exactly what they are today, whether or
  not it carries a deferral declaration (Decision 4's "ignored, not flagged" rule).
- **SPC-8** Regression coverage (the issue's own mandatory guardrail, "load-bearing, not a nicety")
  proves SPC-7 directly: a plan with 4+ chunks, and separately a plan whose committed diff classifies
  `escalate`, each declaring deferral, still trip the stop hook's ordinary per-session coverage
  requirement exactly as an equivalent plan with no deferral declaration would — the declaration
  changes nothing observable for either case.

## Acceptance

- [ ] A plan with ≤3 chunks, standard risk tier throughout, and a deferral declaration completes its
      non-final chunks with no per-chunk `chunk`-mode review required, and its declared last chunk's
      one `Type: cumulative-final` cumulative pass is both that chunk's review and the PR-gate
      evidence — exactly as `Type: cumulative-final` already behaves today, just applied to every
      chunk instead of only the last.
- [ ] A session ending after chunk 1 or 2 of such a plan (but before the last chunk) does not have its
      stop hook WARN or block for missing review coverage over the deferred chunks' diff.
- [ ] A chunk landing mid-plan that classifies `escalate` permanently revokes the deferral for the
      rest of that plan; every subsequent chunk (declaration notwithstanding) gets its normal
      per-chunk review and the stop hook's ordinary requirement.
- [ ] A 4+-chunk plan, or a plan whose diff is `escalate`-tier from its first chunk, gets identical
      stop-hook and per-chunk-review behavior whether or not it carries a deferral declaration — proven
      by a regression test, not left to inspection.
- [ ] No existing `Type: cumulative-final`, `chunk`, `final`, `cumulative`, or `verify-resolutions`
      behavior changes for a plan that never declares deferral.

## Scope-out (this item)

- The exact plan-level frontmatter key/value shape for the deferral declaration (Decision 4) — a
  design-stage decision, on the precedent of `depends_on:`/`governed_by:`/`branch:`.
- Restoring the paused reviewer-model tier consumer (`reviewer-session-model`, 2026-07-14) — this item
  consumes `classify-diff-risk`'s verdict string only, unchanged by that pause.
- `TEL-6P2D`'s review-stats windowing and zero-yield pruning-candidate flag — a sibling telemetry item
  with its own scope, not a dependency of this one.
- Any change to how `verify-resolutions` anchors or demotes, or to the disposition/fix cycle for
  findings the terminal cumulative surfaces (Decision 5) — existing machinery, reused as-is.
- Any change to `classify-diff-risk`'s own surface-matching logic, `risk_surfaces:` declaration
  format, or the derived-default surface list — consumed exactly as it exists today.
- Widening eligibility beyond the issue's own proposed bound (chunk-count ≤ 3, standard tier, never
  escalate) — that bound is itself the requirement (SPC-1), not a placeholder pending a larger study.

## Evidence / references

- `plugin/lib/critic_mode.py:1-75` (module docstring, the four-rule precedence ladder),
  `:117-146,775-878` (`ChunkModeRead`, the fail-open-to-inference / escalate-on-unreadable pattern
  Decision 4 mirrors), `:205-208` (`buildplan_refs.resolve_chunk_progress` as the one owner of chunk
  count/current-id), `:262-287` (rule 4), `:328-377` (`_clean_tree_redirect`), `:568-607` (rule 2,
  `_rule_cumulative_fires`).
- `plugin/skills/critic/review-cycle.md:14` (mode/frequency table, the `cumulative-final` row),
  `:18` (stop-hook Critic-gate scope — session baseline → working tree), `:20` (PR-gate composition —
  "no single run needs to carry any particular mode label"), `:73,334` (`cumulative-final` Type
  semantics, the direct precedent), `:77-84` (Evidence and Composition — what a review fact records),
  `:120-127` (Per-Chunk Cycle, the prescription being narrowed).
- `plugin/methodology/building.md:7,17` ("the git baseline, reflection gate, and Critic gate all
  scope to the session"; "per-work-cycle governance is the methodology's responsibility, not the
  hook's"), `:103` (the per-chunk `/prawduct:critic` instruction).
- `plugin/methodology/planning.md` "Critic Mode Per Chunk" and "Choosing a Chunk Type" — the
  authoring heuristics and the `cumulative-final` Type definition this item generalizes.
- `plugin/lib/risk.py:1-46` (docstring: resolution order, failure honesty, output contract, the
  2026-07-14 model-tier pause), `:386,406,413,416,427` (the `standard`/`escalate` print sites).
- `plugin/lib/evidence.py:84` (`KNOWN_KINDS`) — no fact body carries a chunk/commit count, which is
  why the issue's guardrail (C2) must be built as a refusal at declaration time, not detection after
  the fact.
- `plugin/templates/build-plan.md:8-86` (plan-level frontmatter block — `depends_on:`, `governed_by:`,
  `branch:` — the precedent location for the new deferral declaration).
- `plugin/docs/principles.md:45-46` (Principle 11, Proportional Effort), `:87-88` (Principle 23,
  Challenge Gently, Defer Gracefully) — the two principles the issue's own Evidence section invokes.
- Issue #292 body — the original eligibility proposal (chunk-count ≤ 3, risk tier standard, never
  escalate-tier), the mandatory C2 guardrail language ("load-bearing, not a nicety"), and the
  2026-06-22 chunk-mode yield figure (~1 actionable across 7 reviews) cited as mild supporting
  evidence only.
