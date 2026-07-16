---
artifact: build-plan
version: 1
scope: norm-lifecycle
backlog: GOV-7Q4N
depends_on: []
last_validated: 2026-07-16
---

# Build Plan — Norm Lifecycle (normative authority across governing artifacts)

**Why now.** A consuming product (discodon) declared OpenTelemetry "the unified trace substrate"
in its observability-strategy artifact, then built a bespoke parallel telemetry system for async
tool work — and every governance layer certified it. The Critic's Goal 6 fired on the right
artifact and resolved *backwards* ("observability-strategy.md not updated for the persisted
research trace — extend it"); the PR reviewer then verified the amended artifact matched the code
and called it coherence. Root cause: prawduct's coherence model is one-directional — artifacts are
descriptions to be kept fresh (Goal 4 bidirectional freshness, building.md "update artifacts as
you go", Principle 3). The framework has no concept of a **normative statement** that binds future
work, so a divergence was laundered into documented reality through the doc-freshness pipeline
itself. Stress-testing generalized this into a norm *lifecycle* with distinct failure modes:
birth/retroactivity, boundary ambiguity, contradiction, collision, exception expiry, stalled
transition, erosion, decay, and ambient (unwritten) norms — i.e., structural characteristics.

## Problem / Success / Scope

- **Problem:** Governing-artifact statements that should bind future work (telemetry substrate,
  architectural patterns, asset rules) are enforced only as description-freshness, so divergence —
  especially divergence by *omission* — is resolved by syncing the artifact to the code, invisibly.
- **Success:**
  - A changeset that diverges from a normative statement is surfaced as an architectural decision
    (conform, or amend via vetoable DECISION) — verified by tabletop replay of the discodon
    scenario against the new protocol text: the review must flag the amendment, not request it.
  - Plans identify their governing artifacts (`governed_by:`) with mechanical candidate
    assistance from the existing work-model index.
  - Exceptions carry expiry/trigger metadata that actually fires (advisory probe), and norm
    trajectory (erosion, decay, stalls) has an owner (janitor theme + probes).
  - Net instruction payload does not grow: the four scattered divergence checks merge into one
    authority rule; token-budget guardrail tests stay green without raising budgets.
- **Out of scope:** norm IDs/schemas or evidence-store integration for rulings (rulings stay
  prose-as-learnings); LLM/NLP probe triggers (v1 probes fire only on machine-readable fields);
  a UserPromptSubmit "norm-shaped prompt" classifier (deferred — precision risk per the
  work-model review history; file as follow-up backlog candidate at Chunk 6); forced migration of
  existing products (adoption is nudge-based).

## Requirements Confidence

**Level: High** — problem, success, and scope each derive from a fully-evidenced incident plus
eight stress scenarios; the mechanism inventory (what exists to reuse) was verified against this
repo's source, not recalled.

**Open assumptions / decisions:**
- [DECISION: one canonical spec at new `docs/norms.md` (mirrors the `docs/waivers.md` precedent —
  product-facing text may reference it); every other surface references it rather than restating.
  Keeps Cumulative Health budgets flat. | keystone review after Chunk 1]
- [ASSUMPTION: norms live where they already live — `project-preferences.md` rows and Direction
  sections in strategy-class artifacts. No new registry file; the preferences Enforcement table
  becomes the index via pointer rows. | HIGH impact | user can veto → standalone norms registry]
- [ASSUMPTION: boundary rulings are captured as learnings cross-linked to the norm (statute vs
  case-law split), not inline artifact prose. | MED impact | veto → rulings accrete on the norm]
- [ASSUMPTION: v1 probes trigger ONLY on machine-readable fields — `revisit:` dates and backlog
  item ids cited in norm whys/status lines. No prose parsing. Rare-and-high-signal is a hard bar
  (the orphan-term hook's noise history nearly killed it). | HIGH impact | relax only with
  evidence]
- [ASSUMPTION: existing products adopt via doctor/advisory nudges + janitor reconcile (additive,
  non-destructive — the backlog legend-refresh pattern), since `templates/` never reaches
  already-onboarded repos. | MED impact]

## The model (summary — Chunk 1 writes the canonical version)

**Norms bind; descriptions track.** A norm = statement + **why** (required — it is the boundary-
ruling input, collision arbiter, and expiry metadata) + scope + status (`steady-state` |
`in-transition` with a tracking backlog ref) + accumulated rulings (learnings links). Lifecycle
rules: **birth** requires a retroactivity decision (migrate | contain with a modeled boundary |
grandfather with inventory — unstated mixture forbidden); **boundary ambiguity** resolves by
recorded ruling, never silent interpretation; **amendment** is a vetoable architectural decision —
amending a norm in the changeset that violates it is the tell; **exceptions** expire or carry
triggers, and expiries fire; **transitions** need an interim rule — a stalled migration is a
forcing event, not a license to improvise; **erosion/decay** are trajectory concerns owned by the
time-domain organs (advisories = cheap deterministic probes, janitor = deep sweeps); **structural
characteristics** in project-state classification are ambient norms — a flip triggers re-derivation
of structurally-triggered artifacts plus an assumption audit.

**The authority rule (canonical text lives in `docs/norms.md` § The Authority Rule — enforcement
surfaces reference it, never restate it):**

> Norms bind; descriptions track. When work departs from a normative statement, that departure
> is an architectural decision. Exactly four resolutions exist, and three of them are recorded
> decisions: conform, amend the norm, record a ruling at its edge, or take a bounded exception.
> What is never available is silent departure. [+ the general severity rule: any departure /
> normative-content change / norm birth without a recorded decision → Goal 3, BLOCKING; and the
> recorded-decision standard: owner-visible/vetoable, reasoned, timely, durably homed.]

## Surfaces enumerated (project-wide concept — full cascade)

`docs/norms.md` (new) · `.prawduct/cross-cutting-concerns.md` · `lib/work_model_index.py` ·
`bin/prawduct-hook` · `lib/backlog.py` · new `lib/norm_probes.py` · `lib/advisory_store.py`
(registration only) · `skills/backlog/SKILL.md` · `skills/critic/review-protocol.md` ·
`skills/pr/review-protocol.md` · `methodology/session-digest.md` ·
`methodology/session-digest-slim.md` · `methodology/planning.md` · `methodology/building.md` ·
`methodology/discovery.md` · `templates/build-plan.md` · `templates/project-preferences.md` ·
strategy-class templates (`templates/observability-strategy.md`, `templates/security-model.md`,
`templates/api-contract.md`, `templates/nonfunctional-requirements.md`,
`templates/operational-spec.md`, `templates/data-model.md`) · `skills/janitor/SKILL.md` ·
`skills/doctor/SKILL.md` · `skills/learnings/SKILL.md`. Each durable file is touched in exactly
one chunk (batch-durable-edits learning); token-budget guardrail tests are anticipated at Chunks
4–5 — new lines pay for themselves via the consolidation deletions.

## Build Chunks

### Chunk 1: Canonical spec + registry row (keystone)

- **Type:** doc-only. **Critic mode:** final (override forward — architectural keystone; every
  later chunk builds on this text).
- **Description:** Write new `docs/norms.md`: the model above in full — norm anatomy, where norms
  live (no new file class), the authority rule verbatim, and the lifecycle rules (birth/
  retroactivity, boundary rulings, amendment, exceptions+expiry, transitions/interim rules,
  erosion/decay ownership, characteristic-flip protocol, event-domain vs time-domain enforcement
  split). Add one row to `.prawduct/cross-cutting-concerns.md` covering the whole lifecycle
  (discovery → artifact → builder → Critic + the time-domain column noted in Notes).
- **Done when:** the spec answers all eight stress scenarios by name (contradiction-laundering,
  boundary ambiguity, characteristic flip, stalled transition, collision, retroactivity, erosion,
  decay) — each gets a one-line "which rule catches this" index entry; `/prawduct:critic`.
- **Acceptance:** a reader can classify any governing-artifact sentence as normative or
  descriptive using only the spec's tests; no other file restates the rules.

### Chunk 2: Jurisdiction assist — work-model index inversion

- **Type:** code. **Critic mode:** chunk.
- **Description:** In `lib/work_model_index.py` add a pure function `jurisdiction_candidates(...)`
  — given prompt/plan terms and the existing artifact-vocabulary index, return ranked
  (artifact, matched-terms) candidates. Reuse the existing common-words floor and stoplist
  unchanged (precision layers are load-bearing). Add a `bin/prawduct-hook jurisdiction` subcommand
  (input: text or file path; output: candidate `governed_by:` list). No hook wiring — this is an
  on-demand authoring aid invoked from the planning flow, not a tripwire.
- **Tests:** unit — known-term overlap ranks the right artifact first; floor words never match;
  empty/no-match returns empty (negative path); repo-local invocation via `python3
  bin/prawduct-hook` against THIS repo's artifacts returns sane candidates (check-own-signals
  learning).
- **Acceptance (as corrected at build):** running the subcommand on this plan's own text ranks
  `docs/norms.md` first among candidates. The originally-written acceptance named
  `cross-cutting-concerns.md` and the critic protocol, but neither is in the work-model corpus
  (`.prawduct/artifacts/*.md` + CLAUDE.md + `docs/` + `methodology/`) — a pre-existing corpus
  property, corrected here rather than widened silently. Verified repo-locally at build
  (2026-07-16): `docs/norms.md` top at 61 matched terms via `--file`, `--artifacts-only`, and
  stdin paths. The automated *live-repo* self-check test is explicitly descoped — repo-coupled
  tests break as the corpus evolves; hermetic seeded-repo CLI tests cover the behavior instead.
- **As built:** `jurisdiction_candidates(text, files)` takes `(path, content)` pairs, not "the
  existing index" as planned — the flat-union index cannot attribute terms per artifact
  (docstring records this). `--artifacts-only` added beyond plan (restricts to the `governed_by:`
  target set) with dedicated tests; directive verbs deliberately NOT exempted (weak-but-real
  overlap signal for ranking, unlike orphan detection which drops them).

### Chunk 3: Exception rails — `revisit:` field + advisory probes

- **Type:** code. **Critic mode:** chunk.
- **Description:** (a) Add optional `revisit:` metadata to backlog items in `lib/backlog.py`
  (`revisit: YYYY-MM-DD` or `revisit: <free-text trigger>`; only dated form is machine-fired) and
  document it in `skills/backlog/SKILL.md` (format section + legend-refresh canonical field set).
  (b) New `lib/norm_probes.py` registering advisory probes via `lib/advisory_store.py`:
  **revisit-due** (dated `revisit:` in the past on an open item → one stable advisory);
  **dead-why** (a norm why/status line citing a backlog id that is archived/shipped → the norm is
  up for review); **stalled-transition** (an `in-transition` norm whose tracking backlog item's
  entry is unedited — no status, stage, or content change — past the staleness window, default
  30 days, configurable); **norm-health-sweep-overdue** (Direction sections exist but the
  janitor Norm Health sweep has never run / is past its window — the sweep stamps committed
  project state the probe reads); **norm-registry-unratified** (one-shot post-upgrade: the
  product has strategy-class artifacts but no Direction section anywhere, or a preferences
  Enforcement table without the norm columns → one stable advisory pointing at the
  `/prawduct:doctor` ratification flow (Chunk 6 — same release, so the target exists at ship
  time); cleared by ratification OR a recorded "no norms to ratify" answer — shared-state, so one
  teammate's ratification clears it for everyone, per the derived-views one-shot manifest
  precedent). All probes read committed shared state; nag state stays in
  the gitignored advisory store (shared-answer/personal-nag split learning). Persisted-format
  lock-in: before coding, enumerate the queries each field must answer (who fires, what clears,
  what the advisory text needs) in a short design note in the chunk commit.
- **Tests:** per probe — positive fire, negative silence (no `revisit:`, future date, open
  tracking item), and idempotence (stable advisory id, no churn). Zero advisories emitted against
  this repo's current state (rare-and-high-signal bar).
- **Acceptance:** a synthetic expired exception surfaces exactly one advisory at sync and clears
  via the existing dismiss/resolve lifecycle.
- **As built (recorded deferrals):** (1) `norm-registry-unratified` implements only the
  no-Direction-anywhere trigger arm; the "Enforcement table lacks the norm columns" arm is
  **deferred until the columns exist** (Chunk 5 templates + doctor adoption) — the literal
  trigger would false-fire on every product today, including this repo. Revisit when Chunk 5
  lands. (2) The stall window is a module constant (`STALL_WINDOW_DAYS = 30`) with a WHY
  comment, not configurable — no probe-threshold config surface exists (sibling backlog probes
  are also bare constants); "configurable" is deferred until any probe needs it. (3) The 5th
  probe (`norm-health-sweep-overdue`) landed here reading a `norm_health_last_run` project-state
  scalar (the `backlog_last_groomed_at` pattern); the janitor writes the stamp in Chunk 6.
  (4) Zero-fire acceptance is a deliberately repo-coupled tripwire test, not hermetic — it must
  fail if this repo ratifies a Direction section without the sweep stamp.

### Chunk 4: Enforcement surfaces — Critic/PR consolidation + digest

- **Type:** doc-only. **Critic mode:** final (enforcement keystone — this is where the discodon
  inversion lived).
- **Description:** `skills/critic/review-protocol.md`: add the authority rule (reference
  `docs/norms.md`, one short block in the Review Goals preamble); rewrite Goal 4's preferences
  line to cover preferences rows AND Direction statements with the amend-to-match-own-code →
  Goal 3 routing — phrased **content-independently**: when a changeset edits any strategy-class
  artifact in a way that blesses that changeset's own code, the reviewer classifies the edit as
  descriptive-sync vs norm-change using the `docs/norms.md` test, *even when the artifact has no
  marked Direction section* (interim protection for upgraded products that haven't ratified norms
  yet — this is exactly the discodon laundering pattern). **Divergence disposition is three-way:**
  (1) divergence with a recorded vetoable ruling/amendment → verify the reasoning is genuine
  (waiver-review model), no finding if sound; (2) unrecorded, and the Critic judges the norm was
  not designed for this scenario and the departure looks correct → still BLOCKING — the missing
  thing is the *ruling*, not correct code — but the recommendation pivots to "record the boundary
  ruling / scope clarification (cheap: a DECISION block + ruling capture)" and states the Critic's
  own correctness assessment so the owner can ratify fast; (3) unrecorded and the norm plainly
  applies → BLOCKING, conform. The reviewer's correctness judgment shapes the recommendation,
  never whether a decision is required — a reviewer waiving a norm unilaterally is
  decision-by-default relocated. Scope bidirectional freshness to
  descriptive content; **delete** Goal 6's "if
  an observability strategy exists, implementation follows it" line (subsumed); extend the
  Learnings Cross-Check to scan Direction statements of artifacts named in the plan's
  `governed_by:`; add a **norm-staleness NOTE** — when review evidence suggests the registry
  itself is stale (a diverged-from norm whose why no longer holds, widespread pre-existing
  violations of it, or unratified normative-looking prose), emit a NOTE recommending the
  `/prawduct:doctor` ratification/integrity flow. Never as a downgrade: the divergence finding
  keeps its severity, because a norm binds until amended (escape-hatches-in-classification
  learning). `skills/pr/review-protocol.md`: one sentence referencing the same rule (the PR
  reviewer verified the laundering — it needs the same authority framing). Digest carriers
  (`methodology/session-digest.md`, `methodology/session-digest-slim.md`): one hardest-rules
  line — "Norms bind; descriptions track — diverging from a governing artifact's
  Direction/preferences is a decision to surface, never doc-drift to sync (`docs/norms.md`)."
  Token-budget guardrail tests must pass without raising budgets — the Goal 6 deletion and Goal 4
  merge pay for the additions; trim further if needed (compressibility-sample learning).
- **Done when:** tabletop replay of the discodon changeset against the new text: Goal 4/3 flags
  the strategy amendment as an unrecorded decision (BLOCKING), and the billboard scenario yields
  a boundary-ruling finding rather than silence or a mechanical block; `/prawduct:critic`.
- **Acceptance:** guardrail tests green; the four old divergence checks exist nowhere as separate
  instructions.

### Chunk 5: Authoring surfaces — planning/building/discovery + templates

- **Type:** doc-only. **Critic mode:** chunk.
- **Description:** `methodology/planning.md`: "Governing Artifacts" section — plans declare
  `governed_by:` (frontmatter, alongside `depends_on:`), seeded via `prawduct-hook jurisdiction`,
  reconciled against each artifact's Direction section (conform / ruling / amendment — never
  silent); plus a "new structural context" prompt (execution context, process, storage, external
  surface ⇒ state how each cross-cutting concern lands there, or why it doesn't).
  `methodology/building.md`: builder-side authority rule reference + the norm-birth tripwire
  (mirror of the requirement tripwire: a norm surfacing mid-build routes to capture — preferences
  row or Direction entry with why + retroactivity decision — before code proceeds).
  `methodology/discovery.md`: norm capture guidance (statement+why+retroactivity at birth) and
  the characteristic-flip protocol in "Discovery Recurs" (flip classification ⇒ re-derive
  structurally-triggered artifacts + assumption audit whose output is backlog requirements).
  `templates/build-plan.md`: `governed_by:` field with filled example. `templates/
  project-preferences.md`: Enforcement table gains why + audit-home columns and pointer rows
  ("norm lives in `<artifact>` § Direction"). Strategy-class templates (listed in Surfaces): a
  short `## Direction` guidance block each (comment-style, referencing `docs/norms.md` — no
  restatement). Parser-contract discipline: field labels string-identical across methodology,
  templates, and protocol text.
- **Done when:** labels grep-identical across all touched files; `/prawduct:critic`.
- **Acceptance:** authoring a toy plan against this repo produces a `governed_by:` line whose
  candidates came from the Chunk 2 command.

### Chunk 6: Time-domain sweeps + adoption path (cumulative-final)

- **Type:** cumulative-final.
- **Description:** `skills/janitor/SKILL.md`: "Norm Health" investigation theme — global
  distance-from-norm and its trend (erosion), norms whose whys reference completed/abandoned work
  (decay — cross-reference the existing Obsolescence theme rather than duplicating), in-transition
  norms with stalled tracking items; reconcile step presents re-affirm-and-schedule-cleanup vs
  retire as the explicit fork. `skills/doctor/SKILL.md`: (a) the **norm ratification flow** — the
  landing target of the `norm-registry-unratified` advisory: read the product's strategy-class
  artifacts, preferences, and learnings; propose candidate norms (statement + why + status),
  batched for owner confirm-or-correct (janitor Step-3 Reconcile pattern); write ratified norms
  into Direction sections + preferences rows, additively and non-destructively; a "no norms to
  ratify" outcome is valid (proportionality) and records the answer that clears the advisory.
  Detection and surfacing are automatic (the probe + session briefing); **execution stays
  on-demand and ratification stays with the owner** — auto-binding norms would be a norm-birth
  decision made by default, the exact anti-pattern this plan exists to kill, and the
  "auto-enable belongs with visibility, not with enforcement" learning applies verbatim.
  (b) One recurring health check — norm-registry
  integrity (Direction statements have whys, citing backlog ids where the rationale rests on
  tracked work; preferences rows have mechanisms that exist; in-transition entries carry
  tracking ids; classification currency vs observable code signals). `skills/learnings/SKILL.md`: lookup also indexes Direction
  sections so `/prawduct:learnings <topic>` returns governing norms beside case-law rules.
  Adoption path for existing products (documented in `docs/norms.md`'s adoption section, executed
  by doctor/janitor): additive and non-destructive — annotate existing strategy artifacts'
  normative statements into Direction sections opportunistically, extend Enforcement tables via
  the legend-refresh pattern; never rewrite product content wholesale. File the deferred
  follow-up backlog candidates (norm-shaped-prompt classifier; erosion metrics automation).
- **Done when:** commit, then one `/prawduct:critic cumulative` against `merge-base...HEAD` (this
  review is also the `/prawduct:pr create` gate).
- **Acceptance:** doctor run on this repo reports norm-registry status without false findings;
  janitor survey-only pass lists the Norm Health theme with sane project-specific adaptation;
  `docs/norms.md`'s adoption section carries the telemetry-substrate incident as its worked
  example (narrative norm in a strategy artifact → Direction entry with why + `in-transition`
  status + tracking backlog ref).

## Verification Strategy

Doc chunks verify by **tabletop replay**: run the stress scenarios (discodon laundering, raster
billboard, single→multi-user flip, stalled migration, collision, retroactivity, erosion, decay)
against the edited prose and confirm each is caught by the rule the Chunk 1 index says catches it.
Code chunks verify by unit tests including negative paths, plus repo-local execution
(`python3 bin/prawduct-hook …`) against this repo's own state — probes must be silent here today.
Chunk 4 additionally runs the token-budget guardrail tests.

## Governance Checkpoints

1. **After Chunk 1** — concept coherence: the spec resolves all eight scenarios without
   contradiction; the normative/descriptive test is decidable. (Everything downstream transcribes
   this.)
2. **After Chunk 4** — enforcement coherence: the discodon tabletop replay flags the laundering;
   payload budgets flat.
3. **Cumulative at Chunk 6** — full-cascade coherence + adoption-path sanity.

## Sequencing note

1 → 2 → 3 can proceed in order (2 and 3 are independent of each other; both depend only on 1's
vocabulary). 4 and 5 depend on 1 and reference 2's command (5) — build after the code lands so
methodology text names real commands. 6 last. Implementation is medium+ work: feature-branch
(`feature/norm-lifecycle`), commit this plan as the first act on the branch, repoint
`active_build_plan` when work starts.

## Status

- [x] Chunk 1: Canonical spec + registry row (keystone) — built + tabletop-hardened (10-agent
      adversarial fan-out) + Critic final keystone passed 2026-07-16; commit d8d1ef6.
- [x] Chunk 2: Jurisdiction assist — built (as-built notes in the chunk) + Critic final +
      verify-resolutions passed 2026-07-16; commit 4bd291b.
- [x] Chunk 3: Exception rails — `revisit:` field + five probes (revisit-due, dead-why,
      stalled-transition, norm-registry-unratified, norm-health-sweep-overdue — the 5th landed
      here, not deferred; janitor writes the stamp in Chunk 6). 31 tests; zero-fire against this
      repo enforced by a repo-coupled tripwire test. As-built deferrals recorded in the chunk.
- [ ] Chunk 4: Enforcement surfaces — Critic/PR consolidation + digest
- [ ] Chunk 5: Authoring surfaces — planning/building/discovery + templates
- [ ] Chunk 6: Time-domain sweeps + adoption path (cumulative-final)

Context: implementing on feature/norm-lifecycle, one commit per chunk, per-chunk Critic reviews.
Chunks 4-6 are doc chunks; 4 is the enforcement keystone (token ceiling: review-protocol.md
< 3450 est tokens — consolidation deletions pay for additions; small precedented bump only if
unavoidable).
