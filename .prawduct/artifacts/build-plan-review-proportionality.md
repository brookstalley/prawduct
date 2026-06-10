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

**Out of scope.** (a) Cross-project telemetry aggregation — filed as TEL-7A4X
(`/prawduct:backlog`, this session); chunk 03 only guarantees the per-project event schema and
`--json` contract it needs. (a2) Phase-instrumentation event PRODUCERS (`build.chunk`,
`plan.authored`, `discovery.session` — data requirement 3's wall-clock-per-phase): the
envelope accommodates them by design, but emitting them honestly needs hook instrumentation
with real open questions (when does "research" start/end? build time ≠ session time across
interleaved chunks) — deferred deliberately, not silently; extend TEL-7A4X or file separately
when chunks 02-03 are live. (b) Adaptive/sampled review depth from telemetry (revisit only WITH telemetry evidence,
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

**Level:** High for chunks 01-03; Medium for 04-05 (design decisions below are inferences
awaiting veto, not confirmed requirements).

**Confidence history (kept deliberately):** ch.02-03 were FIRST marked High while the ledger
was designed mechanism-first ("append review records") without eliciting what questions the
data must answer; the user's analytics requirements (2026-06-10) restructured the schema to
the event envelope. High now means *requirements-elicited* High — the "Ledger data
requirements" section IS the elicitation. The framework fix (schema-lock-in tripwire) ships
in ch.01 so the next persisted format starts with the questions.

**Ledger data requirements (user-elicited 2026-06-10 — the questions the data must answer).**
These are the schema's requirements; fields exist to serve them. v1 implements the recording
and the review-scoped reporting; the schema must accommodate ALL of them without migration:
1. Which reviewer model is most efficient per ROLE — builder vs Critic vs PR reviewer
   (cost/duration vs actionable-finding yield, by model, by role)?
2. Which areas of the codebase are most risky (findings density per path over time —
   requires finding-level file attribution, not summary-string parsing)?
3. Wall clock across PHASES — research / plan / build / review — per FEATURE (requires every
   event to carry the build-plan `scope` as the feature key, and an envelope that later
   event kinds — `build.chunk`, `plan.authored`, `discovery.session` — can join without
   schema change).
4. Cross-project aggregation (TEL-7A4X): stable per-line `schema_version` + `project`;
   consumers skip unknown event kinds and unknown fields.

**Open assumptions / unknowns:**
- [ASSUMPTION: the ledger is ADDITIVE — `.prawduct/.critic-findings.json` stays the canonical
  "latest record" all 19 existing code references keep reading; the Critic additionally
  appends one EVENT line to `.prawduct/.governance-ledger.jsonl`; only the PR gate learns to
  scan the ledger. Rationale: relocating the record would churn lib/gates.py,
  critic_mode.py, core.py, briefing.py, the hook, 4 skills, and ~10 test files for zero
  soundness gain | HIGH impact | user can override]
- [ASSUMPTION: envelope/payload split — every event shares
  `{schema_version, event, ts, duration_seconds, project, scope, chunk, actor:{role,model},
  git:{head,base}}`; the event-kind payload (`review: {...}` for v1) nests beneath.
  Aggregators key on the envelope without understanding every payload; v1 emits ONLY
  `review.critic` and `review.pr` events | HIGH impact | user can override]
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
Context: CHUNKS 01+02 BUILT 2026-06-10 (S1 complete; checkboxes flip at release via
change-log tags `chunks=01|02 | scope=review-proportionality`). Ch.01 (ed3a330):
cumulative-as-final prose on four surfaces + advisory pin test; the Critic's WARNING caught
the under-enumerated template surface. Ch.02 (6c9241b): lib/ledger.py structural writer +
PR-gate ledger fallback in lib/gates.py + schema additions (model/files) + 36 tests; Critic
`final` (explicit, side-plan convention) clean — and it dogfooded ledger-append, so the
ledger holds its first real correctly-scoped event. NEXT: PR-1 (ch.01+02 — keystone in the
smallest bundle; user-confirmed direction pending) — the PR's cumulative review will append
event #2 and exercise the gate live. Then S2 = ch.03+04 → /clear; S3 = ch.05 + ONE
cumulative (which IS ch.05's review, per the rule ch.01 ships) + PR-2. Governance
checkpoint 1 (post-ch.02): additive-ledger held under its own final review (0 blocking,
0 warnings); gate fallback fail-closed paths pinned by adversarial tests — proceed.

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
- **Schema-lock-in tripwire** (framework fix from this plan's own near-miss, 2026-06-10):
  `methodology/building.md` "Decision Research" + `methodology/planning.md` — one sentence
  each: *a persisted format/schema is ALWAYS a lock-in decision regardless of implementation
  size (reversal cost, not LOC); a chunk introducing one must enumerate the questions the
  data must answer — its consumers' future queries are its requirements — before designing
  fields.* Root cause it fixes: this plan's ch.02 was first designed mechanism-first
  ("append review records") with High confidence; the user's analytics questions then
  restructured the schema (event envelope). Budgets apply — displace, don't stack.
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

### Chunk 02: Governance-event ledger — append-only history + PR-gate ledger fallback

The single-slot findings file forces a choice between reviewing new work and preserving the
PR-gate record (observed twice on 2026-06-10) — and review history is unmeasurable because
each record overwrites the last. The ledger is a **governance-event** ledger shaped by the
"Ledger data requirements" above (NOT a review-findings dump): envelope/payload split,
`.prawduct/.governance-ledger.jsonl`, one event per line. v1 emits `review.critic` events
only (`review.pr` arrives in ch.05; build/plan/discovery event kinds are accommodated by the
envelope and explicitly NOT built — see Out of scope).

- **Structural writer** (`bin/prawduct-hook ledger-append`): the agent never hand-authors
  JSONL. The Critic runs `prawduct-hook ledger-append --event review.critic
  [--scope <scope>] [--chunk <id>] [--model <id>]`; the helper reads the just-written
  `.critic-findings.json`, validates it, computes the envelope itself (`ts`, `project` =
  repo dirname, `git.head`/`git.base`, `schema_version: 1`), nests the record as the
  `review` payload, and appends one line (single `O_APPEND` write). `--scope` is passed
  EXPLICITLY by the reviewer from the plan it reviewed against — `active_build_plan` is only
  the fallback, because side-plans (this very plan, pre-repoint) would otherwise
  mis-attribute the feature key. `duration_seconds` and `actor.model` come from the findings
  record / `--model`; both nullable — never invented.
- **Producer prose** (`skills/critic/SKILL.md` step 7 + `review-protocol.md` Output Format):
  one added instruction — run `ledger-append` after writing findings. Records gain `model`
  in the findings file too (the reviewer knows what it ran as). Findings entries gain an
  optional structured `files` list (which files each finding is about) — data requirement 2
  (risky areas) needs attribution, not summary-string parsing. Protocol budget <3120 — plan
  the displacement before writing.
- **Schema** (`lib/gates.py::validate_critic_findings`): `model` optional at record level,
  `files` optional list-of-str per finding, validated-when-present (the established
  optional-field pattern). Envelope validation lives in `ledger-append` (the single writer).
- **PR-gate fallback** (`lib/gates.py::check_cumulative_critic`): when the latest record's
  mode is neither cumulative nor a chained verify-resolutions, scan the ledger newest-first
  for the first `review.critic` event whose payload qualifies and evaluate THAT under the
  existing checks unchanged (commit coverage, chain scope ⊆, 0 blocking). Unparseable lines
  are skipped with a stderr note, never crash the gate; no qualifying event → today's
  failure messages. This dissolves the deferred-review problem: a chunk review after the
  cumulative no longer destroys the PR gate's evidence.
- **Hygiene**: ledger gitignored alongside `.critic-findings.json` (confirm the
  `init-product`/`update_gitignore` entry set covers `.governance-ledger.jsonl`; add if
  not); `docs/project-structure.md` + `skills/critic/review-cycle.md` "Recording Reviews"
  document the event shape; size is unbounded-but-tiny (one line per event) — note a
  future-prune escape hatch in prose, build nothing.
- **Tests**: `ledger-append` envelope correctness (event/ts/project/git/scope fallback
  order, nullable duration/model), append-after-review payload equality with the latest
  file, gate-fallback accept (latest=chunk record, ledger holds qualifying cumulative@HEAD →
  exit 0), fallback honesty (ledger cumulative stale over code → exit 1 with today's
  message), corrupt-line tolerance, schema accepts/rejects `model`/`files` shapes. Real-git
  fixtures per `tests/test_cumulative_gate.py` conventions (HOME outside repo — pyc-cache
  learning).

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

- Reads `.prawduct/.governance-ledger.jsonl`; tolerates missing file (exit 0, "no review
  history"), skips corrupt lines and UNKNOWN event kinds with a count (forward-compat:
  v1 reports on `review.*` events only).
- Reports per `actor.role` × `actor.model` × review mode (and overall): event count,
  total/median `duration_seconds`, findings by severity, **actionable rate** (% of reviews
  with ≥1 blocking/warning), findings-per-review — data requirement 1. Plus a
  findings-by-file rollup from finding-level `files` (top-N paths by actionable findings) —
  data requirement 2's first cut. Per-`scope` rollups group everything by feature — the seam
  data requirement 3's phase events will join later. Human table on stdout; `--json` emits a
  stable machine shape (top-level `schema_version`, `project`, `generated_at`) — the
  contract TEL-7A4X builds on; document the event schema + report shape in a new
  `docs/governance-telemetry.md` (small).
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
  `record_consumed`/`spot_checks` note so telemetry distinguishes scoped from full runs.
- **Ledger event**: the PR reviewer (or the `/prawduct:pr` skill on its behalf) runs
  `prawduct-hook ledger-append --event review.pr ...` so role-vs-role model-efficiency
  comparisons (data requirement 1) have both review roles in the data from day one.
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
