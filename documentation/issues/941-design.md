# Issue #941 — review-stats: Actionable Rate Ignores Recorded Dispositions: Design

`status: draft · stage: design · area: governance/telemetry · added: 2026-10-02 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/941`

Related: #563 (the `gate.blocked` / `probe.fired` event kinds, split out of #263 with this item),
`plugin/docs/governance-telemetry.md` (the `--json` contract this extends).

## Problem (restated)

`review-stats` reports an "actionable rate" per grouping as *the share of reviews with at least one
blocking or warning finding* (`telemetry._group_stats`, `_ACTIONABLE`). That is severity presence,
a statement about what a reviewer **labelled**, not about what the builder **did**. Since 2026-07-29
the builder's answer is recorded as `disposition` facts (`accept` / `file` / `fixed`) plus verify-pass
resolution facts, and `dispositions.census` already folds both into one state per finding. Nothing
joins the two, so the instrument review proportionality is argued from still cannot tell a finding
that produced a fix from one that was accepted and ignored.

Success: `review-stats` states, for the reviews it reports, **what happened to the findings** —
and says plainly how many reviews it could and could not state that for.

## What is in the tree (verified 2026-10-02)

- `telemetry._read_events` reads only `.prawduct/.governance-ledger.jsonl`, keeps `review.*` events,
  and `_extract_row` takes severities from `event["review"]["findings"]`. Re-derive:
  `grep -n 'disposition' plugin/lib/telemetry.py` returns nothing.
- Every `review.critic` ledger event carries `review.fact_id` — the evidence-store review fact's id,
  which is the `review_id` that `disposition` and resolution facts target. It is how
  `ledger.review_event_exists` already de-duplicates. Findings in that event carry `fid`.
  So **the join key already exists on both sides**; no producer change is needed.
  (`review.pr` events: not verified to carry `fact_id`; see Open Q-2.)
- `dispositions.census(store, review_ids=[...])` accepts an explicit set of review ids and returns
  per-finding `state` (`fixed`, `waived`, `accepted`, `filed`, `fixed-unreviewed`, `undispositioned`,
  `resolved-*`) with a summary. It already owns precedence (resolution beats disposition; both
  present is a counted `conflict`). The `review_ids` parameter exists for exactly this caller
  ("a caller that has already computed which reviews it is talking about").
- The two stores differ in keying and lifetime: the ledger is per-worktree and gitignored; the
  evidence store is clone-shared under the git common dir. A review recorded from another worktree
  of the same clone is in the store but not in this ledger; the reverse (ledger event whose fact is
  gone, e.g. a fresh clone) is possible.

## The design fork, decided

The issue asks: **A** `review-stats` grows an evidence-store read with a severity fallback, or **B**
`review-stats` and `render-dispositions` converge into one reporting surface.

**Recommendation: A, implemented as a thin call into the existing census — never a second reader.**

- B's cost is a user-visible rename and merged output contracts for two commands with different
  audiences (`review-stats` is a cost/yield instrument over a window; `render-dispositions` is a
  per-review table that lands in PR bodies). Convergence is a product decision with no demand yet.
- A's feared cost is "two stores with different keying". That cost is real only if telemetry
  *re-derives* disposition state. It does not have to: telemetry hands the census the set of
  `fact_id`s it already holds and consumes the finished per-finding `state`. Precedence, conflict
  handling and the unrecognised-resolution rule stay in `dispositions.py`. One owner for the
  answer; the join is one function call.
- A leaves B open. If a later item converges the surfaces, the join written here is the part that
  survives.

## Requirements

- **R-1 Join by `fact_id`.** For every windowed `review.*` event with a string `review.fact_id`,
  look up that review in the evidence store through `dispositions.census(review_ids=…)`. One store
  read per `review-stats` run, not per event or per grouping.
- **R-2 Keep the severity metric, rename nothing.** `actionable_rate` keeps its meaning and its
  key (consumers, TEL-7A4X, key on it). It is documented as *severity-labelled*. The new numbers
  sit beside it.
- **R-3 New per-group block `dispositions`.** Over blocking and warning findings of the joined
  reviews only (notes and observations are outside the "severity does not exempt" debt, matching
  the census): `joined_reviews`, `unjoined_reviews`, `findings` (joined blocking+warning), and a
  `by_state` tally using the census's state names verbatim. Plus two derived rates, each with its
  denominator stated in the key set:
  - `acted_on_rate` — joined blocking/warning findings in `fixed`, `fixed-unreviewed` ÷ joined
    blocking/warning findings.
  - `dismissed_rate` — `accepted` + `waived` ÷ the same denominator.
  `filed` is reported in `by_state` and in neither rate: it is a real defect deferred, which is
  neither a fix nor a dismissal. `undispositioned` likewise stays visible rather than being folded
  into "not acted on".
- **R-4 Coverage is an output.** `unjoined_reviews` counts events with no `fact_id`, no matching
  fact in the store, or an unreadable store. A rate over a joined subset must never print without
  the subset's size beside it. Human line: `acted on 62% of 29 joined blocking/warning findings
  (14 of 21 reviews joined)`.
- **R-5 Degradation is stated, not zero.** Store absent, unreadable or outside a git repo →
  `dispositions: {"status": "unavailable", "reason": "…"}` for the report and the human line says
  so. The severity metrics render exactly as today. An absent block must never read as "0% acted
  on".
- **R-6 Not a gate.** Read-only, pulled not pushed, exit code unchanged (0 whenever a report can
  be produced). Nothing in session hooks calls it.
- **R-7 Windowing.** The window selects ledger events as today. Disposition state is read **as of
  now**, not as of the window end, and the report says so (`dispositions.as_of`). A finding
  answered after the window closes still counts as answered; this is the point of the number.
  Recent reviews will therefore skew toward `undispositioned`, which is why that state is shown and
  never folded away.
- **R-8 Schema.** `REPORT_SCHEMA_VERSION` 7 → 8, additive key; the prose home
  (`plugin/docs/governance-telemetry.md`) is updated in the same change.

## Design

1. `telemetry._extract_row` also returns `fact_id` (string or `None`) and, per finding, `fid`.
2. `aggregate_review_stats` gains an optional `disposition_states: "dict[tuple[str,str], str] | None"`
   argument (keyed `(fact_id, fid)` → state) plus a `dispositions_unavailable: str | None` reason.
   Pure and deterministic as it is today; the I/O stays out of it.
3. `review_stats()` builds that map once: collect `fact_id`s from the windowed events, call
   `evidence.read_facts(project_dir)` then `dispositions.census(store, review_ids=ids)`, flatten
   its rows. Imports are lazy, as the module's other cross-lib imports are, so telemetry stays
   import-light and a missing evidence module degrades under R-5 rather than breaking the report.
4. `_group_stats` computes the block from `row["fact_id"]` and the map. A row whose `fact_id` is
   absent from the map is *unjoined*, not "all undispositioned".
5. `census` returns `status: error` when none of the ids is in the store. Telemetry maps that to
   "no joined reviews" (`joined_reviews: 0`), distinct from an unreadable store.

No change to `dispositions.py` behaviour. If the flattened-rows shape proves awkward, the one
permitted addition is a small exported helper beside `census` returning the finished
`{(review_id, fid): state}` map — *the answer, not the walker* — so a second consumer never
re-walks `census` output.

## Acceptance controls (each must be able to go red)

- Positive: a ledger event + store fact + `fixed` disposition on a blocking finding →
  `acted_on_rate` 1.0, `joined_reviews` 1.
- Same fixture with the disposition `accept` → `dismissed_rate` 1.0, `acted_on_rate` 0.0.
  (Distinguishes the new metric from severity presence: both fixtures leave `actionable_rate` at
  1.0, which is the discriminating assertion.)
- A resolution fact (`fixed`) and a conflicting disposition (`accept`) agree with
  `render-dispositions` for the same review — the two commands never give different states for one
  finding. Pin by running both over one fixture.
- Event without `fact_id`, and event whose `fact_id` is absent from the store → counted in
  `unjoined_reviews`; rates computed over the remainder only.
- Store missing / unreadable → `status: unavailable` with a reason; severity fields byte-identical
  to a run without the feature.
- Window: an event outside `--since/--until` contributes to neither numerator nor denominator.
- `undispositioned` findings appear in `by_state` and in neither rate.
- Real-artifact control: one test reads the repo's own ledger line shape (a real
  `review.critic` event) and asserts `review.fact_id` is present — the join key is not a belief
  about the producer.

## Risks and fallbacks

- **Survivor bias in the denominator.** Only reviews that reached the store join. Mitigated by R-4;
  the rate is never presented without its coverage.
- **Disposition recording is voluntary.** If builders rarely record, `undispositioned` dominates
  and `acted_on_rate` is low for the wrong reason. Report `undispositioned` share prominently; do
  not "fix" this by treating silence as dismissal. Whether to measure recording rate first is Q-3.
- **Cross-worktree skew.** A ledger from a worktree that did not run the review has no event for
  it; coverage is per-ledger by construction. Stated in the doc, not corrected.

## Open questions for the owner

- **Q-1 (design fork)** Confirm A-via-census over B (converge). Recommended: A. Moving the item to
  `ready` needs only this.
- **Q-2** Do `review.pr` ledger events carry `fact_id`? Not verified here. If not, they join as
  `unjoined` and the PR reviewer's dispositions stay invisible; decide whether that is accepted for
  v1 or in scope.
- **Q-3** Which headline replaces severity presence in the human line: lead with `acted on N%` and
  keep `actionable` as a trailing figure (recommended), or print both at equal weight?
- **Q-4** Should `fixed-unreviewed` (self-reported fix, no verify pass) count in `acted_on_rate`?
  Recommended yes, with the state still shown separately in `by_state`, because excluding it
  re-penalises exactly the cheap path the inner stage encourages.

## Next step

On answers to Q-1 and Q-3, move to `ready`. The build is one chunk (`telemetry.py`, the contract
doc, tests) of effort M.
