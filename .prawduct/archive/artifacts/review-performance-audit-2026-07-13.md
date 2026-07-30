# Review Performance — Audit Findings and Improvement Plan (2026-07-13)

**Provenance.** Owner-requested audit of Critic + PR-reviewer latency on large products
(motivating case: discodon — 5+ min per review, often for minor changes). Findings are
grounded in discodon's governance ledger (`.prawduct/.governance-ledger.jsonl`, 279 reviews
with durations, 2026-06 through 2026-07-13) plus a code read of the review data plane
(`skills/critic/*`, `skills/pr/*`, `lib/critic_mode.py`, `lib/critic_consolidate.py`,
`lib/evidence.py`, `lib/coverage_algebra.py`, `lib/risk.py`, `lib/gates.py`).

**Status.** Findings doc — no requirements written yet. Every recommendation below must
route through `/prawduct:backlog` + discovery before implementation (requirements precede
code). Estimated work is sizing input for planning, not a plan.

---

## 1. Problem

On large products, each Critic review and each PR review costs ~4–7 minutes of wall clock
regardless of change size. At the PR boundary the costs stack sequentially (cumulative
Critic, then PR reviewer). Total measured cost on discodon: **25.0 hours of review wall
clock in ~6 weeks** (Critic 18.8h across 213 reviews; PR 6.2h across 66 reviews).

The goal: cut latency substantially **without weakening review value** — the
reviewer-model A/B (`reviewer-model-ab-2026-06-10.md`) proved bundle-boundary depth
catches real defects, so acceleration must come from waste, not from judgment.

## 2. Evidence

### 2.1 Review cost is flat in scope — fixed overhead dominates

| Files reviewed | n | median | mean |
|---|---|---|---|
| 1–2 | 6 | 225s | 265s |
| 3–4 | 12 | 230s | 240s |
| 5–9 | 53 | 240s | 277s |
| 10–19 | 73 | 300s | 322s |
| 20+ | 68 | 240s | 370s |

A 2-file review costs the same as a 20-file review. The cost driver is the fixed
context-establishment every review pays, not the diff. On discodon that fixed reading
list is: 3 protocol files, `project-state.yaml` (44KB), and in `final`/`cumulative` mode
`learnings.md` (68KB) plus Backlog Reconciliation's "walk every open item" against a
**440KB** `backlog.md`. ~0.5MB of governance state read (or grepped through) to judge a
3-line diff.

### 2.2 Per-mode medians vs. targets

| Mode | n | median | p90 | protocol target |
|---|---|---|---|---|
| chunk | 44 | 240s | 540s | 1–2 min |
| final | 26 | 340s | 600s | 4–10 min |
| cumulative | 58 | 420s | 760s (max 2100s) | 4–10 min |
| verify-resolutions | 84 | 150s | 300s | 1–2 min |
| PR review | 66 | 300s | 420s | — |

`verify-resolutions` (the delta-review design) works — cheapest mode, most-used. `chunk`
misses its target 2× because it pays the same fixed overhead as everything else.

### 2.3 Other readings

- **PR boundary is sequential**: cumulative (420s median) then PR reviewer (300s median)
  = ~12 min per PR, both reading the same full bundle.
- **Blocking findings are near-zero**: 4 across 213 Critic reviews. Volume is
  warnings/notes (cumulative: 1.56 W + 2.73 N per review). Warning-driven fix cycles feed
  84 verify-resolutions runs (4.7h total — cheap per-run, high count).
- **Composition already carries some PRs**: 66 PR reviews vs. 58 cumulative runs — the
  label-free gate passes on composed chunk facts + free edges for some branches.
- **Model tiering is not a lever**: the A/B settled opus as the efficiency frontier;
  sonnet was ruled out (higher cost, zero novel findings).

## 3. Root causes

**RC1 — Fixed context overhead, invariant in diff size.** The protocol mandates reading
project state, learnings (final mode), and the full open backlog (Backlog Reconciliation)
every `final`/`cumulative`, with no filtering by relevance to the diff. Product-state
bloat (discodon: 440KB backlog, 68KB learnings, 44KB project-state) multiplies it.

**RC2 — PR boundary serialization.** `skills/pr/SKILL.md` sequences Step 2 (cumulative
gate, which may trigger a full cumulative run) strictly before Step 3 (PR reviewer
dispatch). The PR reviewer's *work* doesn't consume the cumulative's findings — only PR
*creation* needs both. Sequencing exists for the "consumes gate-certified soundness"
framing, not a data dependency.

**RC3 — Composition-blind mode inference + goals not recorded in facts.** Two halves:

- `_rule_cumulative_fires` (`lib/critic_mode.py:340`) recommends `cumulative` on
  clean-tree + ≥2-commits-ahead + no-cumulative-record-at-HEAD. It never consults the
  coverage verdict — so a small branch whose chunk fact + free `.md` edges already
  satisfy `check-cumulative-critic` still gets a 7-minute bundle review recommended.
  Prose reinforces it (review-cycle.md "any multi-cycle branch → cumulative"; agents
  believe "the PR gate wants a cumulative" — it doesn't; the gate is mode-label-blind,
  `lib/gates.py:809`).
- Reviewer partials carry a `goals` field but `build_fact_body`
  (`lib/critic_consolidate.py:591`) drops it — facts don't record which goals ran. So
  composition can't distinguish "goals 1–3 covered this span" from "all 7 covered it."
  Consequences point both directions: redundant re-review (can't prove goals 4–7 aren't
  needed → run full cumulative) **and** a quiet weakness (a branch covered entirely by
  chunk facts passes the PR gate with goals 4–7 never having run — the "all 7 once per
  PR" guarantee is prose/advisory only, not structural).

**RC4 — No persistent repo-wide knowledge.** Goal 7's deduplication check ("this 3-line
function duplicates one somewhere else entirely") needs whole-repo awareness that is
re-derived by unguided grep — or silently shallow — every review, on a 2,000+ file repo.
Similarly, prior warning/note findings aren't surfaced to later reviewers, so known items
get re-reported (the exact failure the A/B caught sonnet doing) and re-fixed cycles churn.

**RC5 — Cumulative re-reads content already reviewed.** Facts record reviewed *paths*
but not blob SHAs, so a cumulative dispatch can't tell the reviewer which files' current
content a consolidated review already saw. The whole bundle gets full-depth reading even
when most of it is unchanged since per-chunk review.

## 4. Recommendations

IDs are stable for backlog reference. "Weakening guardrail" = why this doesn't reduce
review value.

### RP-1 — Goals-in-facts + composition-aware recommendation (fixes RC3)

**What.** (a) Merge the partials' `goals` into the fact body (union, e.g. `goals_run`).
(b) Make inference rule 2 composition-aware: before recommending `cumulative`, compute
the coverage verdict over merge-base→HEAD (via `lib.evidence` + `lib.coverage_algebra` +
`coverage.resolve_merge_base_tree` — NOT `lib.gates`, which `critic_mode` deliberately
never imports). Decision tree: all-7 coverage composes → recommend nothing ("gate
passes"); only-1–3 coverage composes → recommend a **goal-upgrade pass** (goals 4–7 +
cross-checks over the already-covered interval, skipping correctness re-derivation);
no coverage → cumulative as today. (c) Align prose: review-cycle.md mode table,
SKILL step 1, the stop-hook advisory wording.

**Mechanism note.** Prefer reusing mode `cumulative` with an optional manifest field
(e.g. `goals_scope`) over a new mode token — the mode vocabulary is pinned in
`MODE_TOKEN_TO_VERBOSE`, `gates._CRITIC_MODE_VALUES`, and tests; an optional manifest
field is additive and `validate_manifest` tolerates extra keys.

**Where.** `lib/critic_consolidate.py` (fact body, manifest field),
`lib/critic_mode.py` (rule 2), `skills/critic/review-cycle.md` + `review-protocol.md` +
`SKILL.md` (prose), tests.

**Estimate.** M — 2–3 chunks.

**Impact.** Eliminates redundant cumulatives on small branches (~7 min each, the
owner-observed case); converts others to cheaper upgrade passes. Savings shrink as chunk
count grows (multi-chunk integration still needs cross-seam reading) — correct shape for
a proportionality fix.

**Weakening guardrail.** Strictly strengthens: goals-in-facts makes the "all 7 goals ran"
guarantee structural for the first time (today it's prose-only). No gate loosens; the
gate already accepts chunk-fact chains.

### RP-2 — Parallelize the PR boundary (fixes RC2)

**What.** Dispatch the PR reviewer concurrently with the cumulative Critic run (when one
is needed); gate PR *creation* on both completing clean. Prose-only change to
`skills/pr/SKILL.md` Steps 2–3 (+ the review-cycle.md "prep work" note).

**Estimate.** S — 1 chunk.

**Impact.** ~5 min per PR when both run (66 PRs ≈ 5h saved on discodon's history).

**Weakening guardrail.** Both reviews still run in full; only their ordering changes.
Risk: a cumulative blocker invalidates the concurrent PR review (~2% incidence on
discodon — 1 blocking cumulative in 58); the existing Update Flow delta re-review covers
that path. Expected waste ≪ expected saving.

### RP-3 — Code-built review context pack (fixes RC1)

**What.** Extend `critic-begin` (already code, already derives interval/roster) to emit
a filtered context pack alongside the manifest: open backlog items whose `area:`/paths
intersect `files_changed`; learnings rules whose topics/globs match changed paths;
relevant project-state keys. The pack **discloses what it filtered** (counts by area) so
the reviewer can pull more on suspicion — full files remain readable on demand. Protocol
changes: the final-mode reading list points at the pack; Backlog Reconciliation scopes to
pack items; the *full* backlog walk moves to `/prawduct:janitor` cadence.

**Where.** `lib/critic_consolidate.py` (or a new `lib/review_pack.py`),
`lib/backlog.py` (structured item filter), learnings topic-matching (new lib code —
today the lookup is skill prose), `skills/critic/review-protocol.md` +
`review-cycle.md`, `skills/janitor` addition, tests.

**Estimate.** L — 3–4 chunks.

**Impact.** The only fix that converts the flat ~240s floor into proportional cost.
Target: chunk median 240s → ≤120s; final/cumulative fixed overhead similarly cut.
Benefits all three coordinator subagents (each pays the fixed cost today).

**Weakening guardrail.** The filter is deterministic code (auditable), disclosure lets
the reviewer widen scope, and the full walk still happens periodically via janitor.
Ship with a telemetry check: compare findings-per-review (`review-stats`) before/after;
revert threshold if warning yield drops materially.

### RP-4 — Known-findings memory in the pack (fixes RC4, noise half)

**What.** Pack addition once RP-3 exists: prior findings (any severity, with
dispositions) from the evidence store touching `files_changed`, with guidance "don't
re-report unchanged known findings; escalate if worse."

**Estimate.** S — 1 chunk (depends on RP-3).

**Impact.** Kills re-report noise and the verify-cycle churn it feeds (84 verify runs,
4.7h on discodon).

**Weakening guardrail.** Prior findings are presented, not suppressed — reviewer judgment
decides; regressions are explicitly called out for escalation.

### RP-5 — Reviewed-blob memory + incremental cumulative attention (fixes RC5)

**What.** Record per-file blob SHAs in the review fact (code-derived at consolidate
time, e.g. `git ls-tree` of `head_tree` restricted to `files_reviewed`). At cumulative
dispatch, `critic-begin` computes a focus list: files whose current blob a consolidated
review already saw (skim; attend to cross-chunk seams) vs. files never reviewed at this
content (full read). `files_reviewed` still lists everything — this scopes *attention*,
not gate semantics (the "no content-hash freshness" do-not-reintroduce note in
`coverage_algebra.is_judgeable_path` guards gate freshness, which stays untouched).

**Estimate.** M — 2–3 chunks.

**Impact.** Cumulative median 420s (p90 760s, max 2100s) drops toward delta cost on
mostly-covered bundles; compounds with RP-1 (upgrade passes get the same focus list).

**Weakening guardrail.** Attention guidance is additive; goals 4–7 explicitly still read
across seams; never-seen content is always full-read. Gates and the coverage algebra are
unchanged.

### RP-6 — Persistent symbol index (fixes RC4, capability half)

**What.** Maintain `<git-common-dir>/prawduct/symbol-index.json` keyed by blob SHA —
incremental (only changed blobs re-indexed), built by code (`prawduct-hook
symbol-index`). Reviewers look up name/signature-similar functions for *added* symbols
only — proportional by construction. Needs a spike first: extraction mechanism (ctags
vs. per-language regex vs. Python `ast`), languages covered, index size/refresh policy.

**Estimate.** L — spike + 3–4 chunks. Highest uncertainty of the set.

**Impact.** Makes goal-7 dedup **real** on 2,000+ file repos (today: unguided grep or
silently shallow) — a quality improvement that also happens to be faster.

**Weakening guardrail.** Pure addition; the index augments, never replaces, the
reviewer's own search.

### RP-7 — Governance-context-weight health check (fixes RC1 multiplier)

**What.** `/prawduct:doctor` (or janitor) computes the bytes a final-mode review must
read (project-state + learnings + open backlog + protocol) and flags over-threshold,
the way the session briefing already nags on project-state size. Product-side remedies
already exist (backlog archive via `/prawduct:backlog`, learnings compaction).

**Estimate.** S — 1 chunk.

**Impact.** Bounds the multiplier on every other fix; discodon's 440KB open backlog is
the worked example.

## 5. Proposed sequencing

| Phase | Items | Rationale |
|---|---|---|
| **1 — quick wins** | RP-1, RP-2 | RP-2 is prose-only and ships alone. RP-1 kills the owner-observed redundancy (chunk→cumulative on small branches) and structurally strengthens the all-7 guarantee. Both independent of everything else. |
| **2 — the big lever** | RP-3, then RP-4 | Attacks the dominant flat cost. RP-4 rides the pack mechanism. Ship with the findings-yield telemetry check. |
| **3 — incremental depth** | RP-5, RP-7 | RP-5 compounds with RP-1's upgrade passes. RP-7 is cheap and bounds the multiplier. |
| **4 — spike-gated** | RP-6 | Real capability win but highest uncertainty; spike decides the mechanism before committing. |

Dependency notes: RP-4 depends on RP-3. RP-5 benefits from RP-1 but doesn't require it.
Nothing else is coupled. All phases are framework work on this repo; discodon picks the
improvements up via plugin update.

## 6. Verification and telemetry

- **Baseline (recorded above, discodon, 2026-07-13):** chunk 240s / final 340s /
  cumulative 420s / verify 150s / PR 300s medians; 25.0h total over ~6 weeks; findings
  yield per mode (§2.3).
- **After each phase:** `prawduct-hook review-stats` on discodon — duration medians by
  mode AND findings-per-review by severity. A latency win that halves warning yield is a
  regression, not a win (the RP-3 guardrail).
- **Targets:** chunk ≤120s median; PR boundary (cumulative + PR review wall clock)
  ≤7 min; zero redundant cumulative runs on branches where all-7 coverage composes.

## 7. Process next steps (tomorrow)

1. File RP-1…RP-7 via `/prawduct:backlog` (this doc is the parent reference; items carry
   `RP-n` in their text).
2. Pick Phase 1; run discovery on RP-1 (the only Phase-1 item with design decisions:
   fact-field shape, upgrade-pass dispatch mechanism, prose surface list).
3. Build plan per normal governance — chunked, Critic-reviewed, with the telemetry
   checks from §6 as acceptance criteria.
