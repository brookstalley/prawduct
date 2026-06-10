---
artifact: build-plan
version: 2
scope: review-proportionality
depends_on: [gate-soundness]
last_validated: 2026-06-10
---

# Build Plan — Review Proportionality (two-sided: cheaper where safe, deeper where risky)

**Problem.** Review cost = runs-per-PR × unit-cost-per-run. After reviewer-model tiering
(unit cost, ~4x) and the CRT-4J8W chain gate (fix-loop run-count), three structural taxes
remain — paying twice for assurance already bought — and two gaps keep the framework's value
felt rather than demonstrated:
1. `Type: cumulative-final` is *defined* as the chunk's own `final` review PLUS a cumulative —
   two 4-10 min full reviews over nearly the same diff, on every multi-chunk plan.
2. The single-slot `.critic-findings.json` manufactures review work: reviewer-model-tiering
   ch.02's review was deferred-and-declared because running it would clobber the PR-gate
   record; any chunk review after a cumulative destroys the record the PR gate needs.
3. The PR reviewer re-derives code soundness over the same `merge-base...HEAD` the
   cumulative-Critic gate just certified.
4. Review value is unmeasured: every findings record carries mode/duration/severities, but
   each review overwrites the last, so no aggregation is possible — "is it worth it" stays a
   vibe (Principle 9, Visible Costs, unapplied to the framework itself).
5. Proportionality only runs one way: review depth scales by size/type, never by diff RISK —
   yet `reviewer-model-ab-2026-06-10.md` showed the top-tier reviewer catching 2 real warnings
   opus missed precisely on a governance-gate bundle.

**Success.** A medium multi-chunk plan's total review budget is: N short `chunk` passes + ONE
full cumulative (serving as the last chunk's review) + one scoped release review — with
`prawduct-hook review-stats` able to show, from recorded history, the cost and actionable-
finding rate of every mode. Bundles touching declared risk surfaces get a deeper reviewer
automatically; bundles that don't, don't. No review is skipped that today's rules require —
every change removes *duplicate* assurance or adds *missing* depth, never loosens severity.

**Out of scope.** (a) Cross-project telemetry aggregation — filed as its own backlog item
(`/prawduct:backlog`, this session); chunk 03 only guarantees the per-project record schema it
needs. (b) Adaptive/sampled review depth from telemetry (revisit only WITH telemetry evidence,
explicitly rejected for now: clean streaks say nothing about builder blind spots). (c) Any
severity-semantics change (warnings stay effectively blocking). (d) Async/background reviews
(STH-3W7F territory; separate design). (e) Skipping the PR reviewer (settled: independence is
the point — ch.5 *scopes* it, never removes it). (f) BLD-7W2J (single-slot
`active_build_plan`) — sibling pain, different pointer, not this plan.

**Prerequisite.** This plan builds ON the gate-soundness chunk-05 chain machinery
(`extends_cumulative`, `_chain_anchor`, rule-1b). Merge the gate-soundness PR
(feature/gate-soundness → develop) first, then branch `feature/review-proportionality` off
develop. Per the plan-lifecycle rule (`methodology/planning.md`), `active_build_plan` keeps
pointing at the gate-soundness plan until its release ships; until the repoint, invoke
`/prawduct:critic` per this plan's chunk Done-whens explicitly (the reviewer-model-tiering
side-plan precedent).

## Requirements Confidence

**Level:** High for chunks 01-03 (every requirement traces to a concretely observed cost this
week, with the defective rule/file identified); Medium for 04-05 (design decisions below are
inferences awaiting veto, not confirmed requirements).

**Open assumptions / unknowns:**
- [ASSUMPTION: the ledger is ADDITIVE — `.prawduct/.critic-findings.json` stays the canonical
  "latest record" all 19 existing code references keep reading; the Critic additionally
  appends each record as one line to `.prawduct/.critic-reviews.jsonl`; only the PR gate
  learns to scan the ledger. Rationale: relocating the record would churn lib/gates.py,
  critic_mode.py, core.py, briefing.py, the hook, 4 skills, and ~10 test files for zero
  soundness gain | HIGH impact | user can override]
- [ASSUMPTION: ledger-fallback applies ONLY to `check-cumulative-critic`: when the latest
  findings file doesn't qualify (wrong mode), the gate scans the ledger newest-first for a
  cumulative/chain record and evaluates it under ALL existing checks (commit coverage, chain
  scope, 0 blocking — a stale ledger record still fails honestly). Inference and the stop-hook
  gate keep reading the latest record only (advisory consumers; latest-state is what they
  govern) | MED impact | user can override]
- [ASSUMPTION: records gain `model` (reviewer model id) and `schema_version` fields — needed
  for cost-per-finding-by-model and cross-project aggregation; optional in the validator for
  back-compat like every prior field addition | LOW impact | user can override]
- [ASSUMPTION: risk surfaces resolve from, in order: a `risk_surfaces:` list in
  `project-state.yaml` (explicit, product-ownable) → else derived defaults (paths matching
  `skills/`, `lib/gates*`, `bin/*hook*`, plus contract files named in
  `.prawduct/artifacts/boundary-patterns.md`). Escalation = the coordinator/fork dispatches
  declare the top-tier model (currently the model family above opus per
  reviewer-model-ab-2026-06-10) instead of `opus` when the review scope intersects a risk
  surface | MED impact | user can override]
- [ASSUMPTION: the PR reviewer's scoped protocol still re-walks the diff for
  release-readiness questions (narrative-vs-diff honesty requires looking at the diff) but
  consumes the gate-qualifying Critic record for code-soundness instead of re-deriving it,
  with an explicit adversarial spot-check duty (sample ≥2 of the record's claims against the
  code; escalate if either fails) | MED impact | user can override]

**What would raise confidence:** chunk-01/02 telemetry running for a few sessions before
chunks 04-05 land would replace the Medium assumptions with measured priors — the chunk
ordering below deliberately enables that, but does not require it.

## Status

- [ ] Chunk 01: Cumulative-as-final — one full review per plan, not two
- [ ] Chunk 02: Findings ledger — append-only history + PR-gate ledger fallback
- [ ] Chunk 03: Review telemetry — `prawduct-hook review-stats`
- [ ] Chunk 04: Risk-surface reviewer escalation
- [ ] Chunk 05: PR-reviewer scoping — consume the record, audit it, review the release
Context: PLAN AUTHORED 2026-06-10 (designed from the post-CRT-4J8W proportionality
assessment; user approved all five + requested the cross-project-telemetry backlog item).
NOT STARTED. Prerequisite: merge feature/gate-soundness → develop, then branch
feature/review-proportionality. Session plan: S1 = ch.01+02 → /clear; S2 = ch.03+04 →
/clear; S3 = ch.05 + ONE cumulative (which IS ch.05's review, per the rule ch.01 ships) + PR.

## Chunks

### Chunk 01: Cumulative-as-final — one full review per plan, not two

`Type: cumulative-final` currently means the last chunk pays a `final` review AND a
cumulative — but cumulative is a strict superset (all 7 goals + framework checks +
learnings cross-check + backlog reconciliation, over `merge-base...HEAD` ⊇ the chunk diff).
Gate-soundness ch.05 already did the right thing ad hoc as a declared deviation; this chunk
makes it the rule. Redefine: **`cumulative-final` = the last chunk's review IS the
cumulative** — commit the chunk first (ch.4 sequencing rule), run `/prawduct:critic
cumulative` once; no separate `final`.

- `skills/critic/review-cycle.md`: Type-matrix row + "When Review Is Required" row +
  Per-Chunk Cycle note (the one-review semantics, with the superset rationale).
- `methodology/planning.md` "Critic Mode Per Chunk" + "Choosing a Chunk Type": update the
  `cumulative-final` description; drop "in addition to the chunk's own `final` review".
- `methodology/building.md`: one-line touch where `cumulative-final` semantics are implied
  (token budget <4850 — displace, don't stack).
- Enforcement check: confirm the stop-hook's "all chunks `[x]` but last review ran Goals 1-3
  only" advisory accepts a cumulative record (it should by construction — pin it with a test
  in `tests/test_critic_gate_fallthrough.py` or the hook-gate tests if no pin exists).
- `lib/critic_mode.py` inference: verify rule-3 `final` does not fight the new rule (last
  chunk + uncommitted work still infers `final` — correct for MID-chunk reviews; the
  cumulative replaces the AT-COMMIT review. Document the distinction in the chunk's prose
  edits; no code change expected — if one proves needed, that is a declared deviation).

- **Type:** code
- **Done when:**
  1. Prose updated on all three surfaces within token budgets; the advisory-acceptance pin
     test passes with the full suite.
  2. `/prawduct:critic` (inference: `chunk` mid-plan) run; blocking findings resolved.
  3. Committed; tagged change-log entry (`chunks=01 | scope=review-proportionality`).

### Chunk 02: Findings ledger — append-only history + PR-gate ledger fallback

The single-slot findings file forces a choice between reviewing new work and preserving the
PR-gate record (observed twice on 2026-06-10). Additive design (see Open assumptions —
HIGH-impact assumption #1):

- **Producer** (`skills/critic/SKILL.md` step 7 + `review-protocol.md` Output Format): after
  writing `.critic-findings.json`, append the SAME record as one line to
  `.prawduct/.critic-reviews.jsonl`. Records gain `model` (the reviewer model actually used)
  and `schema_version: 1`. Protocol budget <3120 — plan the displacement before writing.
- **Schema** (`lib/gates.py::validate_critic_findings`): `model`/`schema_version` optional,
  validated-when-present (the established optional-field pattern).
- **PR-gate fallback** (`lib/gates.py::check_cumulative_critic`): when the latest record's
  mode is neither cumulative nor a chained verify-resolutions, scan `.critic-reviews.jsonl`
  newest-first for the first cumulative/chain record and evaluate THAT under the existing
  checks unchanged (commit coverage, chain scope ⊆, 0 blocking). Unparseable ledger lines are
  skipped with a stderr note, never crash the gate; no qualifying record → today's failure
  messages. This dissolves the deferred-review problem: a chunk review after the cumulative
  no longer destroys the PR gate's evidence.
- **Hygiene**: ledger is gitignored alongside `.critic-findings.json` (confirm the
  `init-product`/`update_gitignore` entry set covers `.critic-reviews.jsonl`; add if not);
  `docs/project-structure.md` + `skills/critic/review-cycle.md` "Recording Reviews" mention
  the ledger; size is unbounded-but-tiny (one JSON line per review) — note a future-prune
  escape hatch in prose, build nothing.
- **Tests**: append-on-review (record equality with the latest file), gate-fallback accept
  (latest=chunk record, ledger holds qualifying cumulative@HEAD → exit 0), fallback honesty
  (ledger cumulative stale over code → exit 1 with today's message), corrupt-line tolerance,
  schema accepts/rejects `model`/`schema_version` shapes. Real-git fixtures per
  `tests/test_cumulative_gate.py` conventions (HOME outside repo — pyc-cache learning).

- **Type:** code
- **Critic mode:** final
  <!-- architectural keystone: chunks 03-05 build on the ledger; Goals 4-7 pay off
       before they stack on it (planning.md override heuristic) -->
- **Done when:**
  1. Tests above pass with the full suite; budgets hold.
  2. `/prawduct:critic` run (plan-override `final`); blocking findings resolved.
  3. Committed; tagged change-log entry (`chunks=02 | scope=review-proportionality`).
  4. **/clear stopping place** — keystone landed and fully reviewed; persist anything open.

### Chunk 03: Review telemetry — `prawduct-hook review-stats`

Visible Costs applied to the framework: aggregate the ledger so proportionality arguments
become evidence. New subcommand `prawduct-hook review-stats [--json]`:

- Reads `.prawduct/.critic-reviews.jsonl`; tolerates missing file (exit 0, "no review
  history") and skips corrupt lines with a count.
- Reports per mode (and overall): review count, total/median `duration_seconds`, findings by
  severity, **actionable rate** (% of reviews with ≥1 blocking/warning), findings-per-review,
  by `model` when present. Human table on stdout; `--json` emits a stable machine shape
  (top-level `schema_version`, `project` = repo dirname, `generated_at`) — this JSON is the
  contract the cross-project aggregation backlog item builds on; document it in
  `docs/` (new `docs/review-telemetry.md`, small).
- Surfacing: `/prawduct:janitor` gains a one-line pointer (run `review-stats` during
  maintenance); no automatic nagging — telemetry is pulled, not pushed.
- **Tests**: aggregation math against a synthetic ledger (mixed modes/severities/models),
  corrupt-line skip + count, empty/missing ledger, `--json` schema stability (pin the keys).

- **Type:** code
- **Done when:**
  1. Tests pass with the full suite; `review-stats` runs clean on THIS repo's real ledger
     (which chunks 01-02's reviews have begun populating — the dogfood evidence).
  2. `/prawduct:critic` (inference: `chunk`) run; blocking findings resolved.
  3. Committed; tagged change-log entry (`chunks=03 | scope=review-proportionality`).

### Chunk 04: Risk-surface reviewer escalation

Two-sided proportionality: spend MORE where risk concentrates. Per the A/B/C experiment, the
top-tier reviewer caught 2 real warnings opus missed on a governance-gate bundle — that's
the bundle class that should buy depth.

- **Classifier** (`lib/` helper + `prawduct-hook classify-diff-risk [<base>]`): resolve risk
  surfaces per the Open-assumptions order (explicit `risk_surfaces:` list in
  `project-state.yaml` → derived defaults: `skills/`, `lib/gates*`, `bin/*hook*`, plus
  backticked contract files parsed from `boundary-patterns.md` when present). Output:
  `escalate|standard` + the matched files on stderr (teach at the boundary, like every gate).
  Fail-open to `standard` ONLY on classifier errors in product repos with no declared
  surfaces; fail-closed (`escalate`) when surfaces are declared but git evaluation fails —
  declared risk + unverifiable diff must not silently get the cheap reviewer.
- **Dispatch** (`skills/critic/SKILL.md` + `review-protocol.md` coordinator instructions,
  `skills/pr/SKILL.md` step 3): before a `final`/`cumulative` review, run the classifier;
  on `escalate`, the fork/coordinator/PR-reviewer dispatches declare the top-tier model
  instead of `opus`, and the findings record's `model` field shows what actually ran (chunk
  02's field — telemetry will show whether escalation pays). `chunk`/`verify-resolutions`
  passes stay on the default tier (delta scopes; depth belongs at bundle boundaries).
- **Tests**: classifier resolution order (explicit list beats defaults), derived-default
  matching, boundary-patterns parsing, fail-open vs fail-closed branches; skill-structure
  pins for the dispatch prose (`tests/preferences/test_critic_skill_structure.py` pattern).

- **Type:** code
- **Done when:**
  1. Tests pass with the full suite; live check: `classify-diff-risk` on this branch reports
     `escalate` (it touches `skills/` + `lib/gates.py` by construction).
  2. `/prawduct:critic` (inference: `chunk`) run; blocking findings resolved.
  3. Committed; tagged change-log entry (`chunks=04 | scope=review-proportionality`).
  4. **/clear stopping place** — measurement + escalation in place; ch.05 is independent.

### Chunk 05: PR-reviewer scoping — consume the record, audit it, review the release

The PR reviewer keeps its independence and loses its duplication. Rewrite
`skills/pr/review-protocol.md` (+ the dispatch prose in `skills/pr/SKILL.md` step 3):

- **Inputs**: the gate-qualifying Critic record (latest file or ledger — same resolution the
  gate uses) is handed to the reviewer as evidence, not as truth.
- **Audit duty (independence preserved)**: adversarially spot-check ≥2 substantive claims
  from the record against the actual code; ANY failed spot-check voids the record for this
  review — fall back to today's full code-soundness pass and say so in the output.
- **Focus**: release-readiness the cumulative structurally can't see — PR narrative vs diff
  honesty (still walks the diff for THIS), version/changelog coherence, branch hygiene,
  migration/rollback notes, the "would a maintainer merge this" judgment.
- **Output contract unchanged** (severities, `.prawduct/.pr-reviews/` evidence), plus a
  `record_consumed`/`spot_checks` note so telemetry can later distinguish scoped from full
  runs.
- **Tests**: protocol-structure pins (audit duty present, void-fallback present), pr-skill
  step-3 dispatch prose pin (`tests/test_pr_reviewer.py` conventions).

- **Type:** cumulative-final
  <!-- under ch.01's NEW semantics: this chunk's review IS the one cumulative below -->
- **Done when:**
  1. Tests pass with the full suite; budgets hold.
  2. Committed; then ONE `/prawduct:critic cumulative` at HEAD — ch.01's rule applied to its
     own plan: the cumulative IS this chunk's review and the PR-gate record. Post-cumulative
     fixes ride the CRT-4J8W chain (fix → commit → `verify-resolutions`).
  3. Tagged change-log entry (`chunks=05 | scope=review-proportionality`); backlog items
     this plan resolves updated via `/prawduct:backlog`.
  4. PR via `/prawduct:pr` when the user asks — its reviewer runs the NEW scoped protocol on
     the bundle that built it (the dogfood closing the loop).

## Verification Strategy

Beyond unit tests, each chunk verifies on THIS repo live: ch.01 — the plan's own last-chunk
flow uses the one-review rule; ch.02 — after its own Critic review, the ledger holds ≥2 real
records and `check-cumulative-critic` still resolves correctly with a chunk record in the
latest slot; ch.03 — `review-stats` renders this repo's genuine history (the first real
cost/actionable-rate numbers, which also seed the "undeniably valuable" evidence base);
ch.04 — the classifier escalates on this very branch; ch.05 — the plan's own PR review runs
scoped-with-audit. Fixture repos (real git, sterile env) cover the adversarial/fail-closed
branches that must never be exercised live.

## Governance Checkpoints

1. After ch.02 (keystone): does the additive-ledger decision hold under its own Critic
   `final` review, and is the gate-fallback provably fail-closed? If not, STOP and redesign
   before 03-05 stack on it.
2. After ch.04: read `review-stats` output — if the actionable-rate data contradicts any
   ch.05 assumption (e.g., PR reviews are already cheap relative to yield), revisit ch.05's
   scope with the user before building it.
