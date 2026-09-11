# Issue #724 — Critic: A Pre-Dispatch Precondition Check for Stale Test Evidence in `verify-resolutions`: Requirements

`status: draft · stage: requirements · area: critic · added: 2026-09-05 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/724`

Related: `COV-3M8Q` (backlog-internal id; the already-ruled-out content-equivalence route this item
declines to repeat — see Scope-out), `plugin/lib/critic_consolidate.py::begin_review` (the "GATE AS
DISPATCHER" mechanism this item extends by analogy, not by touching), v3.2.2's per-mode reviewer
payload (`goals-1-3.md`) — the "make review cheap, not skippable" direction COV-3M8Q's resolution
already shipped, which this item continues rather than duplicates.

## Problem

Issue #724 reports a 27-round, 4.5-hour branch and, from prawduct's own `review-stats` telemetry,
that `verify-resolutions` is 59% of all review rounds and 64% of those rounds (51 of 80) return
zero findings — the single largest addressable cost the report identifies. It offers eight
recommendations (R1–R8). This item takes the requirements step for the one whose gap is confirmed
against the current tree, whose fix is sound without further conditions, and whose sibling
recommendation (R1) turns out to already be closed territory — see Grounding facts and Scope-out.

The report's **W1** names the mechanism directly: *"One escalate-tier round's sole blocking finding
was: the saved suite evidence is stale and red. That is a hook-knowable state.
`test-status` already exits non-zero for it. The round spent its full duration to tell me to run
the suite."* Grounded below: this is not a one-off, it is how the pipeline is wired today — test
evidence freshness is checked **after** a reviewer is dispatched, and in `verify-resolutions`
specifically, the resulting WARNING is structurally promoted to a **BLOCKING** finding, so the
round cannot end cheaply once it fires.

## Grounding facts

Re-verified against the current tree (v3.4.1-dev, 2026-09-05):

- **The verdict is already computed, synchronously, with no reviewer involved.**
  `plugin/lib/gates.py::tests_are_current` (`:161-231`) returns `(is_current, reason)` from the
  saved `.prawduct/.test-evidence.json` alone: invalid whenever the saved run reports `failed > 0`
  or a self-reported `degraded` run (`_load_test_evidence`, `:130-158`), or whenever neither the
  session-fresh clause nor the tree-valid clause (`_test_evidence_tree_valid`, `:234-`) holds. This
  is exactly the verdict `prawduct-hook test-status` exits 1 on (`gates.py:1285-1295`) — a
  millisecond check against a JSON file and a git tree-diff, no LLM, no file reads beyond the one
  record.
- **Today that check runs one step too late.** `plugin/skills/critic/SKILL.md` step 4 dispatches
  the review (`prawduct-hook critic-begin`) whose only pre-dispatch refusal is a review already in
  flight (`begin_review`'s in-flight guard, `critic_consolidate.py:1654-1694`) — nothing there
  consults test freshness. Step 5, **after** dispatch, is where it is first asked: *"run
  `prawduct-hook test-status` to validate evidence covers the current tree (exit 1 = stale →
  WARNING in your review)."* The reviewer has already been spent by the time this fires.
- **`verify-resolutions` cannot let that WARNING stay a WARNING.** Step 1's per-mode scope states
  it outright: *"`verify-resolutions` = goals 1-3 against the delta since the prior review fact,
  and new findings there are BLOCKING only — anything lesser is an observation in your report,
  never a `findings` entry."* So the identical staleness signal that is a WARNING in `chunk`/`final`
  is mechanically promoted to BLOCKING the moment the mode is `verify-resolutions` — precisely W1's
  "sole blocking finding," and precisely why it cost a full round rather than a note: a BLOCKING
  finding is what the next round exists to verify, not what evidence composition already answered.
- **The pattern this item extends already exists, once, for a different axis, with a measured
  yield.** `begin_review`'s own "GATE AS DISPATCHER" clause (`critic_consolidate.py:1960-2053`)
  refuses to dispatch (`status: "no-review-needed"`, CLI exit 3) when the interval holds no
  judgeable path (`coverage_algebra.judgeable_files`) and no pending actionable finding — moving a
  check the coverage gate already made post-hoc (`check-cumulative-critic` could tell you a round
  was unnecessary, but only after you paid for it) to before the reviewer is spent. Measured at
  the time it shipped: 62 of 492 review facts (12.6%, ~5.2 opus-hours) covered entirely
  non-judgeable intervals. This item is the same move — check-you-already-have, relocated earlier
  — applied to test-evidence freshness instead of path judgeability.
- **The refusal costs nothing new to the operator.** Whether caught at dispatch or mid-review, the
  remedy is identical — run the declared suite and record it — and nothing downstream already
  treats stale evidence as silently acceptable: `test-status` (used directly, and by
  `release_readiness.py:705`) and the PR-gate's `suite_vouches_for_tree` call
  (`gates.py:1618`, surfaced as a `NOTE`) already tell the operator the same thing at those other
  points. Moving the check earlier changes **when** the operator learns it, not **whether** they
  must eventually act on it — the same "refuses only what the gate would already say" safety
  argument the existing judgeable-path guard states for itself (`critic_consolidate.py:1969-1971`).

## Decision

**Add one pre-dispatch precondition check, scoped to `verify-resolutions` only:** before
`begin_review` derives the verify-resolutions interval or writes the manifest, it asks the same
verdict `tests_are_current` already computes. A stale verdict refuses dispatch with a new terminal
status distinct from `"no-review-needed"` — the two mean different things (nothing to review, vs.
something to review that the evidence can't presently validate) and conflating them would make a
future reader of `begin_review`'s reason string unable to tell a free round from a blocked one.

**Scoped to `verify-resolutions`, not all four modes**, for a reason grounded above rather than
asserted: `verify-resolutions`'s own promotion rule is what turns a routine staleness signal into a
full-cost BLOCKING finding, and its scope (goals 1-3 against a bounded delta) has little
independent value once the suite that would validate the fix is unreliable. `chunk`/`final`/
`cumulative` review code content whose value does not depend on suite freshness — refusing them
over stale evidence would suppress reviews that remain useful for reasons unrelated to the tests.
Widening this precondition to the other three modes is separable future work (Scope-out).

## Requirements

MUST unless marked SHOULD.

- **PDC1** `begin_review`, for `mode_token == "verify-resolutions"` only, calls the same freshness
  verdict `prawduct-hook test-status` already exposes (`gates.tests_are_current`, or a verdict
  extracted to a shared call both sites use) before deriving the prior-review anchor or writing
  the manifest. No new staleness logic is written — this requirement is satisfied only by reuse,
  never a second implementation of what "stale" means (the drift risk the existing tree-valid
  clause's own docstring names for a parallel case at `gates.py:174-177`).
- **PDC2** A stale verdict returns `{"status": "precondition-failed", "reason": <verbatim reason
  string from the freshness verdict>}` from `begin_review`, **before** the in-flight-guard's
  downstream work (tree capture, prior-fact lookup, manifest write, critic-active marker) runs.
  `cmd_critic_begin` maps this to its own new exit code — not 1 (generic failure), not 2
  (scope-widened), not 3 (no-review-needed) — so the SKILL's per-exit-code table gains exactly one
  new row rather than overloading an existing one.
- **PDC3** On a `precondition-failed` refusal: no manifest is written, no `.critic-partials/` reset
  runs, and no critic-active marker is set — the same "nothing spent" guarantee `no-review-needed`
  already gives (`critic_consolidate.py`'s own framing: a refusal here must cost the operator
  nothing beyond having asked).
- **PDC4** The printed refusal states the freshness verdict's own reason string verbatim (never a
  re-derived summary of it) and one remedy line: run the declared suite, record it, then re-invoke
  `/prawduct:critic verify-resolutions`. A builder reading the refusal sees the same words
  `test-status` alone would have printed, so the two can never drift into disagreeing about why.
- **PDC5** `--force` bypasses this precondition exactly as it already bypasses the
  `no-review-needed` refusal, for the same reason: an operator who explicitly asks for the review
  anyway (e.g., confirming a suspected false-stale reading) is not blocked by a guard meant to save
  routine cost.
- **PDC6** The refusal appends a `guard-refusal` evidence fact (the existing sink,
  `evidence.append_guard_refusal`, a new `kind` distinct from `critic-dispatch-free-interval`) on
  the same "soft — a store failure must not turn a correct refusal into an error, but must not go
  unremarked either" terms the existing guard already follows, so this guard's own yield (did it
  ever refuse a round that would have found something real?) stays falsifiable rather than merely
  asserted.
- **PDC7** No existing `verify-resolutions` behavior for a **current** evidence verdict changes:
  this item adds one refusal path ahead of today's flow and touches nothing else in
  `begin_review`'s interval derivation, anchor logic, or scope-widening check.

## Acceptance

- [ ] A `verify-resolutions` dispatch against stale test evidence (no evidence, a failing saved
      run, a self-reported degraded run, or a tree/timestamp mismatch neither freshness clause
      relaxes) refuses before any manifest is written or marker is set, citing the freshness
      verdict's own reason (PDC1–PDC4).
- [ ] The same dispatch with `--force` proceeds as it does today (PDC5).
- [ ] `chunk`, `final`, and `cumulative` dispatches are behaviorally unchanged by this item on
      both current and stale evidence (Decision, PDC7).
- [ ] The refusal is recorded as a `guard-refusal` evidence fact distinct in `kind` from the
      existing judgeable-path refusal (PDC6).

## Scope-out (this item)

- **R1 (issue's semantic-equivalence / AST gate) — not carried forward, and not because of
  effort.** This is the same route already built, reviewed, and reverted in this repo as
  **`COV-3M8Q`** (ruled 2026-07-29): `coverage_algebra.is_judgeable_path`'s own docstring
  (`:82-98`) records that a normalized-AST exception for comment/docstring-only `.py` edits is
  **unsound here for a repo-specific reason no amount of narrowing fixes** — `waivers.py`'s
  `prawduct:allow` pragma is a source **comment** that `compliance.py` acts on, so an AST-identical
  edit can silently suppress a compliance check, and tests assert over `.py` prose, so a
  docstring-only edit can change test-relevant behavior. All three original reviewers found the
  same hole; the exception was reverted the same session it was built
  (`.prawduct/learnings-detail.md:1828`). `COV-3M8Q` was itself later dropped (2026-07-31,
  `migration-scrub-decisions.md`) because its only other live route — "make review cheap, not
  skippable" — had already shipped as the per-mode reviewer payload split (`goals-1-3.md`, v3.2.2).
  Re-opening the content-equivalence route for issue #724 would re-litigate a ruling already made
  on this exact codebase with this exact failure mode named; this item declines to.
- **R2 (`do_not` machine-checkable remedy patterns).** Independently valuable, but requires a
  finding-schema change (a structured `do_not` field, a verify-time grep pass over the fix diff)
  that is a separable requirements item of its own, not a corollary of the dispatch-time check
  here.
- **R4 (class-scoped findings must enumerate every instance).** A finding-authoring and
  verify-pass requirement, unrelated to pre-dispatch preconditions; the issue itself notes it is
  "the producer-side half" of an already-filed report.
- **R5 (prose findings default to `accept_unless:`), R6 (structural round-cost challenge), R7 (say
  what would make a cheap check runnable), R8 (in-session re-check without a new dispatch).** Each
  is a distinct mechanism (finding format, CLI argument contract, error messaging, dispatch
  architecture respectively) with its own design surface; bundling any into this item would make
  a single requirements document responsible for four unrelated decisions.
- **Widening the stale-evidence precondition to `chunk`/`final`/`cumulative`.** The Decision above
  states why `verify-resolutions` is the mode where the fix is unambiguous; whether the other three
  modes should also refuse on stale evidence is a real question (their reviews have code-content
  value independent of test freshness) left for a follow-on item informed by this one's outcome.

## Evidence / references

- `plugin/lib/gates.py:161-231` (`tests_are_current`), `:130-158` (`_load_test_evidence`),
  `:1285-1295` (`test-status` CLI), `:1618` (`suite_vouches_for_tree` at the PR gate, surfaced as a
  `NOTE` not a hard block).
- `plugin/lib/critic_consolidate.py:1594-1694` (`begin_review`'s signature and in-flight guard —
  the only precondition checked before today), `:1960-2053` (the existing "GATE AS DISPATCHER"
  judgeable-path refusal this item's mechanism mirrors, including its measured yield and its
  `guard-refusal` evidence sink).
- `plugin/lib/coverage_algebra.py:73-104` (`is_judgeable_path`, whose docstring records the
  2026-07-29 ruling against content-equivalence — `COV-3M8Q` — verbatim).
- `plugin/skills/critic/SKILL.md` step 1 (per-mode scope; the sentence promoting `verify-resolutions`
  findings to BLOCKING-only), step 4 (dispatch and its exit-code table), step 5 (today's post-dispatch
  `test-status` check).
- `.prawduct/learnings-detail.md:1828` — the full COV-3M8Q post-mortem (built, reviewed at 10
  blocking findings, reverted same session) and its corollary: *"prefer the fix that removes the
  cost over the fix that removes the check."*
- `.prawduct/artifacts/migration-scrub-decisions.md:259` — COV-3M8Q's 2026-07-31 drop, recording
  that its "make review cheap" alternative had already shipped in v3.2.2.
- Issue #724 body — the `review-stats` telemetry (136 reviews, verify-resolutions 59%/64%-empty),
  W1, and recommendations R1–R8 in full.
