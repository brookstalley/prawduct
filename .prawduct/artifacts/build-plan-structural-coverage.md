---
artifact: build-plan
version: 2
scope: structural-coverage
depends_on: []
# governed_by: omitted — prawduct has declared no ratified norms yet (that absence is
# precisely what this plan makes detectable). This plan will, ironically, be governed by
# the very Direction norms it helps surface once ratification runs.
last_validated: 2026-07-16
---

## Requirements Confidence

**Level:** Medium

**Why:** The problem is crisp and confirmed with the owner (full-chain choice): the framework
has no forcing function that keys off what a product *is* to require what it should therefore
*have* — every mechanism is reactive, so a never-created artifact/characteristic/norm is
invisible (`[[reactive systems can't detect missing things]]`). Success is observable: the
detector fires correctly against this repo's empty state (the live fixture) across all three
layers, and clears as each layer is filled. The design rests on strong existing scaffolding
(the `classification.structural` schema, the probe/advisory pattern, and `api_versioning_probes`
as a working precedent for "characteristic set → required thing absent"). Medium, not High,
because several field-shape and staging decisions are inferred, not confirmed — listed below.

**Open assumptions / decisions (vetoable):**
- [DECISION: Coverage model is *universal-expected + structurally-triggered*, per planning.md — 5 artifacts expected of every product (data-model, security-model, nonfunctional-requirements, operational-spec, observability-strategy), 2 gated on a characteristic (api-contract ← `exposes_programmatic_interface`; architecture ← `multi_process_distributed`). | why: matches the methodology's own Universal-vs-Structurally-triggered split; a flat "all 7 always" would false-fire architecture on a single-process CLI | user can override the mapping]
- [DECISION: The three layers *stage* — one actionable nudge at a time. Layer 1 (artifacts) fires only when `classification.structural` IS recorded (else layer 0 owns it); layer 2 (`norm-registry-unratified`) keeps its existing "artifacts exist" gate (else layer 1 owns it). | why: proportionality / rare-and-high-signal bar — three simultaneous nags on a fresh product is noise; staging gives a fix sequence. This RE-VALIDATES the Chunk-3 narrowing: gating layer 2 on artifact existence is correct staging once layer 1 exists. | user can veto staging in favor of all-at-once]
- [DECISION: GOV-EXI2 is resolved by the upstream layer-1 owner, not by ungating `norm-registry-unratified`. | why: the prawduct blind spot (no strategy artifacts → layer-2 silent) is now owned by layer 1 flagging the missing artifacts; layer 2's gate becomes proper staging. Close GOV-EXI2 as resolved-by-this-plan. | user can override — keep GOV-EXI2's ungate-arm-(b) approach instead]
- [DECISION: Coverage is satisfied by the artifact *existing* — a deliberate `(not relevant — <reason>)` stub is valid content. No separate decline/suppression scalar: one mechanism (does the file exist?), and the decision lives in the artifact where a reader finds it. The probe owns *existence*; the Critic / risk calibration own *decision quality*. | why: proportionality for tiny repos without a rubber-stampable exclusion list; consistent with "the repo should have the artifacts even if not relevant"; self-documenting vs. an inert scalar (owner decision, 2026-07-16, replacing the earlier coverage_declined_* scalar design) | a bare `(not relevant)` passes the probe — whether to require a reason is the Critic's call, not the probe's (vetoable) |]
- [ASSUMPTION: The dogfood stops at *recording prawduct's structural characteristics* (proving the layer 0→1 transition); actually authoring the 7 artifacts is deferred to a filed follow-up — consistent with the owner's "test the fix while the artifacts still don't exist." | HIGH impact | user can override and author in-scope]

**What would raise confidence:** owner ruling on the three [DECISION] lines above (I've recorded
my picks as vetoable); Chunk 01's keystone confirms the declined-answer schema and the exact
`classification.structural` field enumeration against `templates/project-state.yaml`.

## Status

- [x] Chunk 01: Coverage keystone — expectation model + existence-based probe (one artifact end-to-end)
- [x] Chunk 02: Full layer-1 table — all 7 strategy-class artifacts (universal + structurally-triggered)
- [ ] Chunk 03: Layer 0 + staging — sharpen DISCOVERY-NOT-CAPTURED; stage the three advisories; resolve GOV-EXI2
- [ ] Chunk 04: Doctor / onboarding / methodology / propagation
- [ ] Chunk 05: Dogfood against the empty fixture + close (cumulative-final)
Context: Chunks 01-02 complete on `feature/structural-coverage`. Layer 1 is whole:
`lib/coverage_probes.py` carries the full expectation table — 5 universal artifacts always
required, 2 characteristic-triggered (api-contract ← `exposes_programmatic_interface`;
architecture ← `multi_process_distributed`) required only when the characteristic is recorded
present in `classification.structural` (read via the raw-YAML `_structural_recorded` scanner,
since `load_project_state` is column-0-only). One stable advisory, id unchanged from Chunk 01
(evidence invariant; missing set lives in `trigger_summary`, per-arm annotated). Against this
repo: exactly the 5 universal fire (no `classification` block → characteristics unrecorded →
triggered arms silent). `STRATEGY_CLASS_ARTIFACTS` now lives once in coverage_probes and is
imported by `norm_probes` (dedup). Full suite green (1802 passed). Critic chunk-mode clean
(0 blocking / 0 warning / 1 note — untracked uv.lock, left as an owner decision;
fact rev-20260716T221342Z-27a8e651). Next: Chunk 03 (layer 0 + staging).

**Chunk 01 deferred NOTES — status:** citation precision ✓ (docstring derives 5 = planning.md's
9 universal ∩ 7 strategy-class); dedup ✓ (`STRATEGY_CLASS_ARTIFACTS` single-homed in
coverage_probes, imported by norm_probes); staging-caveat docstring ✓ (resolved by completion —
the table is now whole); dogfood strengthened ✓ (exactly-one, composed with the full roster).
- **Still carried → Chunk 04:** the coverage probe family inherits GOV-5D2W's `cmd_clear`-only
  registration (the `advisory show` reconstruction no-ops) — address in the registration/doctor chunk.

## Scaffolding

### Project Initialization

None — lands inside the existing plugin repo. No new runtime dependencies: Python stdlib only,
consistent with the repo's no-third-party-HTTP posture. New probe logic follows the existing
`lib/*_probes.py` family pattern.

### Dependencies

Runtime: Python stdlib (existing `lib/` modules — `norm_probes`, `api_versioning_probes`,
`briefing`, `gates`, `core`). Dev: existing pytest stack (pytest, pytest-xdist, pytest-timeout).
No `pyproject.toml` changes.

### Scaffold Verification

`bin/prawduct-hook clear` runs the advisory roster at session start; the repo-local
`./bin/prawduct-hook` is the verification entry point (`[[when verifying a framework-repo change
by running the hook use the repo-local bin/prawduct-hook]]`). `uv run pytest -q` is green
(current baseline recorded via `test-evidence`).

### Verification Strategy

Beyond unit tests, each chunk is exercised by running `./bin/prawduct-hook clear` against
**synthetic fixtures** (a tmp product tree with a chosen `classification.structural` +
artifact set) to confirm each probe arm fires/suppresses correctly, AND observed against
**this repo's own empty state** as the end-to-end dogfood. Both are required — a test scoped
only to prawduct's own state is false coverage for onboarded repos
(`[[A test asserting the framework repo's OWN state instead of the propagated contract gives
false coverage]]`), and a test scoped only to synthetic fixtures misses the live-fixture proof
the owner asked for.

## Project Structure

```
lib/
├── coverage_probes.py     # NEW — layer-0/1 probes (FEATURE = "structural-coverage")
├── norm_probes.py         # layer-2 (norm-registry-unratified) — staging reconciliation only
├── briefing.py            # DISCOVERY-NOT-CAPTURED sharpening (layer 0)
└── core.py                # GITIGNORE/contract carriers if a nag-state file is added
bin/prawduct-hook          # DISCOVERY-NOT-CAPTURED emit site; probe-family registration
skills/doctor/SKILL.md     # coverage check (onboarding/doctor integration)
methodology/discovery.md   # operationalize the coverage expectation
methodology/planning.md    # cross-reference the expectation table
.prawduct/cross-cutting-concerns.md   # registry row
tests/test_coverage_probes.py         # NEW
# (no templates/project-state.yaml change — coverage keys off file existence, not a
#  persisted scalar; the expectation model ships in coverage_probes.py with the plugin)
```

### Module Boundaries

Probes read the consumer's own `.prawduct/` (state + artifacts dir), never execute anything,
and are fail-soft (a faulty probe never blocks startup — existing `run_sync_advisories`
contract). The expectation table (which artifact is universal vs. characteristic-gated, and the
characteristic→artifact map) lives in ONE place in `coverage_probes.py` and is imported by the
doctor check — never transcribed (`[[transcription across surfaces flattens quantifiers]]`).

## Build Chunks

### Chunk 01: Coverage keystone — expectation model + declined-answer schema + one artifact end-to-end

- **Description:** Thin vertical slice through the whole architecture. Establish (a) the
  artifact-expectation set — the universal strategy-class artifacts, extension point for the
  characteristic-triggered ones; and (b) a layer-1 probe that, for ONE universal artifact
  (data-model), fires when the file is absent and suppresses when it exists — content-agnostic, so
  a `(not relevant — <reason>)` stub satisfies coverage exactly as a full spec does (one
  mechanism, no decline/suppression scalar). Wire it through registration → advisory surface →
  both test planes. Validates the path before widening to all 7 artifacts and all 3 layers.
- **Depends on:** none
- **Artifacts consumed:** `lib/api_versioning_probes.py` (probe precedent), `lib/advisory_store.py` (`Codebase.root`, `AdvisoryCandidate`, `compute_id`, `register_probe`), `docs/norms.md` (§ Where Norms Live — the strategy-class set)
- **Deliverables:** new `lib/coverage_probes.py` (`UNIVERSAL_ARTIFACTS` + `probe_strategy_artifact_missing`, existence-only), family registration in `bin/prawduct-hook`, new `tests/test_coverage_probes.py`
- **Design note (no persisted format):** coverage keys off file *existence*, so this chunk adds
  NO project-state schema/field — the earlier `coverage_declined_*` scalar was dropped (owner
  decision), removing the lock-in it would have carried. The stable-`evidence` /
  volatile-`trigger_summary` split is the one contract to get right (advisory-id stability under
  a shrinking missing set — `compute_id` hashes evidence).
- **Tests:** unit — probe fires when absent, suppresses when present (full spec AND a bare
  `(not relevant)` stub AND an empty file — existence is the whole predicate); advisory-id
  stability; runs through the registered roster. dogfood — observe the probe fire against this
  repo (data-model absent).
- **Acceptance criteria:** the probe emits the advisory on a synthetic empty fixture and is
  silent once the file exists (any content); composed with all probe families it fires exactly
  once against this repo (data-model missing).
- **Critic mode:** final
  <!-- Override: architectural keystone — the expectation model, the persisted declined-answer
       schema, and the probe primitive all get their coherence locked before later chunks build on them. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: Full layer-1 table — all 7 strategy-class artifacts (universal + structurally-triggered)

- **Description:** Widen the keystone to the full expectation table: the 5 universal artifacts
  (fire if absent+undeclined regardless), and the 2 structurally-triggered (api-contract fires
  only when `exposes_programmatic_interface`; architecture only when `multi_process_distributed`),
  keyed off recorded `classification.structural`. Generalize the single probe to the table without
  duplicating the api-versioning precedent's logic — reuse the shape.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `methodology/planning.md` (Universal vs Structurally-triggered lists), `methodology/discovery.md` (the six characteristics)
- **Deliverables:** complete expectation table in `lib/coverage_probes.py`; per-arm advisory
  evidence/trigger text; the triggered arms read only recorded characteristics (never filesystem
  heuristics — `[[detection of structural characteristics should not rely on mechanistic surface markers]]`)
- **Tests:** unit — each universal arm and each triggered arm fires/suppresses per its condition;
  a triggered artifact stays silent when its characteristic is unset/unrecorded (that case belongs
  to layer 0); breadth check — all 7 covered, none narrowed to the common case (`[[the COMMON /
  AVAILABLE instance silently narrows the requirement to itself]]`)
- **Acceptance criteria:** synthetic fixtures across characteristic combinations produce exactly
  the expected fire set; against this repo (characteristics unrecorded), only the 5 universal arms fire.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: Layer 0 + staging — sharpen DISCOVERY-NOT-CAPTURED; stage the advisories; resolve GOV-EXI2

- **Description:** Close the upstream layer and make the chain present one nudge at a time.
  (a) **Layer 0:** sharpen the `DISCOVERY NOT CAPTURED` detection (`bin/prawduct-hook` +
  `briefing._discovery_uncaptured`) so it fires when `classification.structural` is absent or
  incomplete on a repo with product-definition work — not only on template-default nulls (the gap
  that lets prawduct's rich-but-characteristic-less state pass silently). (b) **Staging:** layer-1
  triggered arms already require recorded characteristics; confirm layer 0 owns the unrecorded
  case and layer 2 owns the artifacts-exist case, so exactly one layer speaks. (c) **GOV-EXI2:**
  record that layer-2's artifact-existence gate is now correct staging (the no-artifacts case is
  owned upstream); resolve GOV-EXI2 as resolved-by-this-plan via `/prawduct:backlog`.
- **Depends on:** Chunk 02
- **Artifacts consumed:** `bin/prawduct-hook` (emit site ~L662), `lib/briefing.py` (`_discovery_uncaptured`, `_has_product_definition_work`)
- **Deliverables:** sharpened layer-0 detection + tests; a staging note in `docs/norms.md` §
  Enforcement (the three-layer sequence); GOV-EXI2 closed with `closed-by=structural-coverage`
- **Tests:** unit — layer 0 fires on incomplete `classification.structural` + product work,
  suppresses when complete; staging — a fixture at each layer emits only that layer's advisory
- **Acceptance criteria:** the three layers never double-fire on one fixture; against this repo,
  layer 0 (characteristics unrecorded) fires and the layer-1 triggered arms stay silent.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: Doctor / onboarding / methodology / propagation

- **Description:** The onboarding/doctor half of the owner's choice, plus the methodology and
  propagation surfaces. (a) A doctor coverage check (sibling of the norm registry-integrity check)
  that reports the full three-layer status and points at the fix path — reading the SAME expectation
  table, not a transcription. (b) Operationalize the expectation in `methodology/discovery.md`
  (record structural characteristics → the artifacts they imply) and cross-reference in
  `planning.md`. (c) A `.prawduct/cross-cutting-concerns.md` row so the concern is carried across
  Discovery → Artifact → Builder → Critic (`[[a cross-cutting concern can be UNCOVERED even when
  discovery names it once]]`). (d) Provide a scaffold helper (a `prawduct-hook`/doctor step) that
  drops the stub artifacts for a product in one act — so resolving several missing artifacts is a
  30-second confirm-and-fill, not a chore, keeping a recurring nudge un-annoying. The human
  confirms/fills; the framework never silently auto-stubs (that would decide relevance on the
  owner's behalf). The coverage MODEL itself ships in `coverage_probes.py` with the plugin — no
  per-repo schema legend to propagate.
- **Depends on:** Chunk 03
- **Surfaces (project-wide concept — enumerated per planning.md):** `skills/doctor/SKILL.md`,
  `methodology/discovery.md`, `methodology/planning.md`, `.prawduct/cross-cutting-concerns.md`,
  and their guarding tests (`test_v5_methodology.py`, doctor/coverage tests). If this exceeds one
  Critic pass, split doctor from methodology.
- **Deliverables:** doctor coverage check + skill write-policy consistency; discovery/planning
  edits; cross-cutting row; stub-scaffold helper; tests
- **Tests:** doctor check output on synthetic fixtures; methodology guard tests pass; propagation
  test — the legend reaches a fresh product state, not just this repo's copy
- **Acceptance criteria:** `/prawduct:doctor` reports coverage status accurately on fixtures and
  on this repo; methodology reads coherently; onboarded-repo propagation asserted
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 05: Dogfood against the empty fixture + close

- **Description:** The acceptance the owner asked for — prove the fix on the live empty fixture,
  then demonstrate the first staged transition. Run the full chain against this repo: observe
  layer 0 fire (characteristics unrecorded). Then **record prawduct's own six structural
  characteristics** in `classification.structural` (a discovery act — reconcile from the codebase
  per discovery.md; does NOT create artifacts) and observe the chain advance: layer 0 clears, the
  layer-1 universal arms (and any now-lit triggered arms) fire "artifacts missing." **Stop there** —
  authoring the 7 strategy-class artifacts is deferred to a filed follow-up, keeping faith with
  "test the fix while the artifacts still don't exist." Cumulative review makes the branch PR-ready.
- **Depends on:** Chunk 04
- **Artifacts consumed:** the whole chain; `methodology/discovery.md` § Reconciling an Existing Product (backfill procedure)
- **Deliverables:** `classification.structural` recorded for prawduct (reconciled, each flag with
  provenance); a filed `/prawduct:backlog` follow-up to author the missing strategy-class artifacts
  (the deferred symptom-fix, now correctly downstream of the system-fix); build-plan Status closed
- **Type:** cumulative-final
- **Visual change:** yes — the advisory/doctor output is operator-facing text; append an
  operator-verification entry describing the observed layer transitions
- **Tests:** the dogfood observations are captured as an end-to-end test over a fixture mirroring
  prawduct's before/after states (not a live-repo-coupled assertion — `[[repo-coupled zero-fire
  test]]` fragility)
- **Acceptance criteria:** the recorded before/after fixture shows layer 0 → layer 1 advancing
  exactly as designed; full suite green; cumulative Critic clean
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Early Feedback Milestone

**Milestone chunk:** 01
**What the owner can see:** running `./bin/prawduct-hook clear` against this repo surfaces the
first coverage advisory — the reference repo's blind spot, finally visible.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic passes; Chunk 05's cumulative review
makes the branch PR-ready (`/prawduct:pr create` when the owner asks — merge stays with the owner
per preferences).

- After Chunk 01: confirm the expectation model + declined-answer schema before widening (the
  keystone the rest builds on).
- After Chunk 03: confirm the staging reads as one-nudge-at-a-time and GOV-EXI2's resolution holds.
- After Chunk 05 (cumulative): full-bundle review; verify the dogfood proves the chain end-to-end
  and no strategy artifact was silently authored (the fixture must stay empty).
