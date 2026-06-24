<!-- Build Plan: api-design (target: minor — adds a cross-cutting concern + new artifact)
     Tier: 1 (Source of Truth)

     Closes the framework's largest uncovered cross-cutting concern: the product's
     OWN exposed API. Today "versioning" appears exactly once in the framework
     (discovery.md:15, as one word in a list of implications) and is dropped at
     every downstream stage — no artifact template, no builder guidance, no Critic
     check. The matrix (.prawduct/cross-cutting-concerns.md) has no row for it.
     Row 32 "Foreign API verification" is the CONSUMPTION side, a different concern.

     Motivating evidence (../scriob): ran unversioned at bare root paths for 697 of
     700 commits on an unchallenged "versioning deferred until external consumers
     exist" note (boundary-patterns.md:35), then paid a coordinated breaking-change
     retrofit (commit 250c4c5, mounting /api/v1 across frontend + e2e + ingress +
     docs at once) when a deploy forced the issue. The framework never pressure-
     tested the deferral because it had no opinion to test it with.

     Design stance (user-confirmed): FORCE THE DECISION, don't mandate the answer.
     Gates are WARNING / dismissable advisory — a product can record "none —
     internal-only" and pass. A deferral must be dated and carry a revisit trigger.
     Gate the three load-bearing DECISIONS (versioning, deprecation/compat, error
     model); SURFACE the ~10 other API-design considerations as prose in the
     api-contract template + janitor theme + discovery prompts — never as new gates
     (a noisy gate is a broken gate; "warnings are effectively blocking").
-->
---
artifact: build-plan
version: 2
scope: api-design
depends_on: []
last_validated: null
---

## Requirements Confidence

**Level:** High

**Why:** The problem (no pipeline coverage for the product's own API design), success (3 gated decisions + ~10 surfaced considerations threaded across discovery / planning / a new artifact template / the Critic / doctor / janitor / a migration advisory / the matrix), and scope (force-the-decision at WARNING severity; explicitly NOT mandating versioning) are each statable in one sentence. Every insertion point was located file:line this session by mapping the symmetric Foreign-API pattern (prose-only) and the doctor-check ↔ advisory-probe convention end to end.

**Open assumptions / unknowns:**
- `[ASSUMPTION: versioning + deprecation/compat + stability-tier record as ONE design_decisions.api_versioning_approach block (sub-fields: scheme, deprecation_policy, stability_tiers, status[active|deferred], rationale, revisit_trigger, date); error-model is a SEPARATE design_decisions.api_error_model_approach block with its own Critic bullet | MED impact | user can split versioning/deprecation apart or fold error-model in]`
- `[ASSUMPTION: the advisory probe detects "exposes an API" via a Codebase scan (web-framework imports: fastapi/flask/django-rest/express/fastify/gin/spring + presence of openapi/swagger/*.proto files) and resolves on a top-level api_versioning_decided fact — because load_project_state skips nested blocks (advisory_store.py:386) so it cannot read classification.structural.exposes_programmatic_interface | MED impact | user can prefer a top-level mirror fact set during discovery instead of a code scan]`
- `[ASSUMPTION: the Critic versioning/error-model checks are author-declared via a new **Exposed API:** build-plan field, mirroring Foreign-API's opt-in model (an undeclared chunk gets no check) rather than auto-detected from boundary-patterns globs | MED impact | user can request the coded auto-detect variant — deferred to backlog as the stronger guarantee]`
- `[ASSUMPTION: gate severity is WARNING / dismissable advisory across the board (user-confirmed), never BLOCKING | HIGH impact | confirmed, not inferred]`
- `[ASSUMPTION: methodology/Critic files touched here (planning.md, review-protocol.md, building.md, the skill files) stay under their token-budget guardrail tests by trimming adjacent prose IN the same chunk that adds text — review-protocol.md is known-tight (ceiling 3120→3350 in v2.1.8) | MED impact | if a budget can't be met by trim, the chunk splits or the budget-raise is justified separately]`

**What would raise confidence:** N/A (High).

## Status

- [x] Chunk 01: Keystone — the API decision record + capture-point wiring
- [x] Chunk 02: The api-contract artifact template + planning section + build-plan field
- [x] Chunk 03: Forward Critic gates (versioning + error-model WARNINGs)
- [x] Chunk 04: Retroactive detection — doctor check #9 + janitor hygiene theme
- [ ] Chunk 05: Migration nudge — the api-versioning advisory probe (CODE)
- [ ] Chunk 06: Coherence & close — matrix row, OWASP-API security prompt, cumulative review

Context: Plan on feature/api-design-versioning (off develop; gate-fidelity stays separate for its own PR). **Chunk 01 (keystone) DONE** — decision-record schema added to `templates/project-state.yaml` (`design_decisions.api_versioning_approach` + `api_error_model_approach`; commented-out `api_versioning_decided` answer-store fact) and the two capture points wired (`discovery.md`:15, `planning.md`:29). Critic `final`: no BLOCKING; stale-evidence WARNING cleared (1405 green recorded); AC1 wording reconciled to the commented-out fact per Critic NOTE. **Chunk 02 DONE** — new `templates/api-contract.md` (transport-neutral: network/library/on-device/CLI, NOT HTTP-only, per user feedback), planning Exposed-API section, build-plan `**Exposed API:**` field, discovery/planning wording neutralized, + guard tests (1411 green). building.md pointer dropped (at token ceiling; Builder covered by existing Boundary Investigation). **Chunk 03 DONE** — `skills/critic/review-protocol.md` Goal 2 gained an **Exposed API** bullet beside Foreign-API: versioning+deprecation decision (`api_versioning_approach` present, or a dated deferral w/ revisit trigger) → WARNING if missing; error-model decision (`api_error_model_approach`) → WARNING if missing. No trim needed — the v2.1.8 3120→3350 bump reserved room for exactly these checks (file now 3211/3350). Also flipped the Status checkboxes for Chunks 01/02 (prior sessions tracked completion only in this Context line — coherence fix). **Chunk 04 DONE** — `skills/doctor/SKILL.md` gained health check #9 "API versioning decision" (modeled on #6/#7: detect exposed-API-but-no-recorded-decision → report `degraded`, read-and-guide, no auto-edit; the on-demand twin of the Chunk 05 advisory) + the degraded-classification line extended; `skills/janitor/SKILL.md` gained an `### API Design & Versioning Hygiene` Investigation Theme between Dependency Health and Controllability (transport-neutral framing, HTTP/REST as one example per the Chunk 02 lesson; survey-not-gate) + `api` added to the scope shorthand list. No skill-file budget guards exist; 1411 green. This was the **early-feedback milestone** — `/prawduct:doctor` check #9 can now run against a real product (e.g. ../scriob). Next: **Chunk 05** (the only CODE chunk — the `api-versioning` advisory probe in `lib/`). Then Chunk 06 (coherence/close + cumulative review = the PR gate). Change-log entry added at feature close (bundle-at-release convention).

## Build Chunks

### Chunk 01: Keystone — the API decision record + capture-point wiring

- **Description:** Establish the one concept everything else keys off — a *recorded API decision* — and wire the two capture points (discovery detects, planning records). The gates (Chunks 03-05) and detection (Chunk 04) all read this. Thin vertical slice through the spine: data model (project-state) → discovery capture → planning capture.

- **Depends on:** none

- **Artifacts consumed:** this plan; `.prawduct/cross-cutting-concerns.md` (the coverage model); `templates/project-state.yaml`, `methodology/discovery.md`, `methodology/planning.md`.

- **Deliverables:**
  1. `templates/project-state.yaml` — under `design_decisions`, add an `api_versioning_approach` block (sub-fields: `scheme`, `deprecation_policy`, `stability_tiers`, `status` [active|deferred], `rationale`, `revisit_trigger`, `date`) and a separate `api_error_model_approach` block (`envelope`, `status`, `rationale`), each commented in the house style and defaulting `null`. Add a top-level `api_versioning_decided` answer-store fact, documented as a commented-out optional key (matching the backlog resolution-fact convention near `operator_verification_required` ~L286) — absent/null both read as undecided; a product adds the live key when it records its decision, which suppresses the probe. Keep `classification.structural.exposes_programmatic_interface` as the trigger SIGNAL — add a one-line cross-ref comment pointing at the new decision block.
  2. `methodology/discovery.md` — the "Exposes programmatic interface" line (line 15): expand the implication from a passing list to *decisions to record* — versioning, deprecation/backward-compat, and error model — and note these are captured (not just noted). Keep it tight (the OWASP-API security prompt lands in Chunk 06; reference it forward there).
  3. `methodology/planning.md` — the structurally-triggered artifact line for *Programmatic interface* (line 29): the API-contract checklist currently reads "operations, request/response formats, error codes, authentication, rate limits" and **omits versioning**. Add versioning, deprecation/compatibility, and the conventions/evolution dimension.

- **Tests:** none new (doc/template/config only). Guard: the project-state template must remain valid YAML and any existing template-shape test must pass.
- **Acceptance criteria:**
  1. `templates/project-state.yaml` parses as valid YAML; new decision blocks present with house-style comments; `api_versioning_decided` documented as a commented-out top-level answer-store fact (matching the resolution-fact convention) — absent/null both read as undecided by the Chunk 05 probe.
  2. Full suite green: `python3 -m pytest -q` (no regressions).
  3. discovery.md:15 and planning.md:29 name versioning + deprecation + error model explicitly.
- **Critic mode:** final
  <!-- Override forward to `final`: this chunk lands the architectural keystone
       (the decision-record schema) that Chunks 02-06 build on; coherence of the
       record's shape matters before later chunks consume it (planning.md
       "Override forward to final on an early keystone"). -->
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass.
  2. `/prawduct:critic final` run and blocking findings resolved.
  3. Committed and chunk marked `[x]` in Status.

### Chunk 02: The api-contract artifact template + planning section + build-plan field

- **Description:** Create the artifact the framework already *references* (planning.md:29 promises an "API contract") but never shipped a template for — the "what good looks like" surface that carries the gated decisions AND the ~10 surfaced considerations. Add the planning guidance and the build-plan field that trigger the forward Critic check (Chunk 03).

- **Depends on:** Chunk 01

- **Artifacts consumed:** `methodology/planning.md` (the Foreign-API section is the structural template), `templates/build-plan.md`, `methodology/building.md`, `templates/project-state.yaml` (the decision blocks from Chunk 01).

- **Deliverables:**
  1. new `templates/api-contract.md` — protocol-aware (REST | GraphQL | gRPC) sections: Overview/protocol; Operations; Request/response shapes; **Error model** (envelope, codes — the gated decision); **Versioning** (scheme, granularity — gated); **Deprecation & compatibility** (sunset policy, breaking-change signaling, and the *evolution rules*: additive-only, tolerant-reader, never remove/repurpose a field, tolerate unknown enums — the practice that makes new versions rare); **Conventions** (timestamps ISO-8601/UTC, money as minor-units or decimal string never float, casing, opaque IDs, string enums, null/optional semantics); **Surface inventory & stability tiers** (public-contract vs internal/admin; experimental|stable|deprecated — the OWASP API9 "improper inventory" framing); **Security checklist** (pointer to the security-model + OWASP API Top 10: BOLA, mass assignment, excessive data exposure); **Conditional** (async/long-running ops 202+status; webhooks/outbound events: delivery, retry, signing, consumer idempotency, replay; CORS; consumer correlation/request-id headers). Lead with a "scale to risk" note so low-risk products fill a half-page.
  2. `methodology/planning.md` — add an "Exposed API: Versioning, Deprecation & Error Model" section mirroring "Foreign API Verification": declares the `**Exposed API:** <name>` build-plan field, the recorded-decision requirement (api_versioning_approach + api_error_model_approach present, or an explicit dated deferral), and the author-declaration trigger convention. Add `api-contract` to the structurally-triggered artifact list (it is already gestured at line 29). Trim adjacent prose to hold the file's token budget.
  3. `templates/build-plan.md` — add an `**Exposed API:**` field immediately after `**Foreign API:**` (line 307), same comment style, explaining it triggers the Critic's versioning + error-model decision check (WARNING if no decision recorded).
  4. ~~`methodology/building.md` pointer~~ — **DROPPED (spec-to-reality):** building.md is at its token ceiling (`test_v5_methodology.py`: <4950, "residual irreducible") and the Builder column is already covered by building.md's existing Boundary Investigation (API endpoints named as a contract surface) + the planning Exposed-API section. Redundant prose in a maxed file isn't proportional. Chunk 06 records the Builder coverage accordingly.
  5. **Transport-neutrality (user feedback, mid-chunk):** the artifact + discovery.md/planning.md wording + the build-plan field are written for ANY exposed interface (network service, library/SDK, on-device/platform, CLI) — not HTTP/REST. Guarded by `test_v5_templates.py::TestApiContractTemplate::test_transport_agnostic_not_http_only`.
  6. **Guard tests** (`tests/test_v5_templates.py`): `TestApiContractTemplate` (frontmatter, the 3 recorded decisions, transport-agnostic, surfaced breadth) + a `test_api_decision_fields` assertion locking the Chunk 01 keystone schema.

- **Tests:** none new (doc/template only).
- **Acceptance criteria:**
  1. new `templates/api-contract.md` exists with all required sections; protocol-neutral framing (not REST-only).
  2. planning.md Exposed-API section mirrors the Foreign-API declaration/trigger convention; build-plan template has the `**Exposed API:**` field.
  3. Touched budgeted files (planning.md, building.md) pass their token-budget guardrail tests; `python3 -m pytest -q` green.
- **Critic mode:** chunk
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass.
  2. `/prawduct:critic chunk` run and blocking findings resolved.
  3. Committed and chunk marked `[x]` in Status.

### Chunk 03: Forward Critic gates (versioning + error-model WARNINGs)

- **Description:** The forward gate that prevents NEW drift: when a chunk declares `**Exposed API:**`, the Critic verifies a versioning/deprecation decision and an error-model decision are recorded → WARNING if missing. Mirrors the Foreign-API bullet exactly (Goal 2, prose-only, no hook).

- **Depends on:** Chunk 02 (the `**Exposed API:**` field must exist)

- **Artifacts consumed:** `skills/critic/review-protocol.md` (Goal 2, the Foreign-API bullet at line 67 is the model).

- **Deliverables:**
  1. `skills/critic/review-protocol.md` — under Goal 2 ("Nothing Is Missing"), beside the Foreign-API bullet (line 67), add: (a) chunks with `**Exposed API:**` need a recorded versioning + deprecation decision (api_versioning_approach present, or an explicit dated deferral with a revisit trigger) → WARNING if missing; (b) and a recorded error-model decision (api_error_model_approach) → WARNING if missing. Mirror the Foreign-API phrasing and severity. review-protocol.md is known-tight on its token ceiling — trim adjacent prose to make room (do not weaken existing checks).

- **Tests:** none new (the Foreign-API check has no hook/test — same prose-only model).
- **Acceptance criteria:**
  1. The two bullets read symmetric to the Foreign-API bullet; severity is WARNING (matches the force-the-decision stance).
  2. review-protocol.md passes its token-ceiling guardrail test; `python3 -m pytest -q` green.
- **Critic mode:** chunk
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass.
  2. `/prawduct:critic chunk` run and blocking findings resolved.
  3. Committed and chunk marked `[x]` in Status.

### Chunk 04: Retroactive detection — doctor check #9 + janitor hygiene theme

- **Description:** The retroactive half — how an already-onboarded product that shipped an unversioned API gets *found*. The Critic only reviews diffs (forward), so detection lives in doctor (on-demand / repair entry) and janitor (periodic sweep). The janitor theme also carries the breadth survey (the ~10 considerations as judgment questions, not gates).

- **Depends on:** Chunk 01 (reads the decision record / `api_versioning_decided` fact)

- **Artifacts consumed:** `skills/doctor/SKILL.md` (checks #6/#7 are the model — a check paired with an advisory probe), `skills/janitor/SKILL.md` (Investigation Themes; shorthand list ~L132).

- **Deliverables:**
  1. `skills/doctor/SKILL.md` — add health check #9 "API versioning decision": if the repo exposes an API (structural field set, or API frameworks/openapi/proto present) but no versioning decision is recorded (`api_versioning_decided` unset / `api_versioning_approach` null), report `degraded` and recommend recording the decision (or a dated deferral). Read-and-guide only — present the one-line edit, do not auto-edit project-state (consistent with doctor's posture). Note it is the on-demand surface for the same signal the Chunk 05 advisory raises ambiently.
  2. `skills/janitor/SKILL.md` — add a `### API Design & Versioning Hygiene` Investigation Theme (between Dependency Health and Controllability): a framing question plus survey bullets covering versioning scheme & granularity, deprecation/sunset policy, error-envelope consistency, REST/protocol semantics (status codes, PUT vs PATCH, conditional requests/ETags, idempotency keys), pagination/filter/sort + payload limits, wire conventions (time/money/casing/IDs/enums footguns), surface inventory & stability tiers, and presence of a published/maintained contract. Add a scope shorthand (e.g. `api`) to the shorthand list (~L132). Survey, not gate.

- **Tests:** none new (skill prose).
- **Acceptance criteria:**
  1. doctor check #9 mirrors the #6/#7 report-and-recommend shape (no auto-edit); janitor theme + shorthand consistent with the existing list.
  2. Skill-file token budgets (if any) pass; `python3 -m pytest -q` green.
- **Critic mode:** chunk
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass.
  2. `/prawduct:critic chunk` run and blocking findings resolved.
  3. Committed and chunk marked `[x]` in Status.

### Chunk 05: Migration nudge — the api-versioning advisory probe (CODE)

- **Description:** The ambient migration trigger — what *tells* an upgrading consumer they're in a bad state without having to think to run a skill. A post-sync advisory probe that fires when an API is detected but no versioning decision is recorded; dismissable (a legitimately-unversioned internal API silences it) and auto-resolving (recording the decision sets `api_versioning_decided` and the probe stops). The only code chunk.

- **Depends on:** Chunk 01 (the top-level `api_versioning_decided` fact)

- **Artifacts consumed:** `lib/upstream_probes.py` and `lib/backlog_probes.py` (the probe templates), `lib/advisory_store.py` (`register_probe`, `AdvisoryCandidate`, `Codebase`, `load_project_state`), `bin/prawduct-hook` (the `register()` call site ~L672), `lib/briefing.py` (renders advisories — no change expected).

- **Deliverables:**
  1. new `lib/api_versioning_probes.py` — a probe that fires an `AdvisoryCandidate` when the `Codebase` scan detects an exposed API (web-framework imports — fastapi/flask/django-rest/express/fastify/gin/spring — OR an openapi/swagger spec or `*.proto` file) AND the top-level fact `api_versioning_decided` is not truthy. `recommended_action` points at recording the decision (resolves the advisory); includes a `register()` mirroring `upstream_probes.register()`.
  2. `bin/prawduct-hook` — register the new probe alongside `backlog_probes` / `upstream_probes` at the existing `register()` site (~L672-673).
  3. new `tests/test_api_versioning_probe.py` — fires when API detected + fact unset; suppressed when fact set; suppressed when no API detected; (lifecycle: dismiss makes it sticky). Model on the existing probe tests.

- **Tests:** the new `tests/test_api_versioning_probe.py` above. Each behavior (fire / suppress-by-fact / suppress-by-no-API) has a case that fails before the probe exists and passes after.
- **Acceptance criteria:**
  1. New tests pass; full suite green: `python3 -m pytest -q`.
  2. Probe is registered (a session-start sync in a repo with an API framework + no decision surfaces the advisory in the briefing).
  3. No new broad `except` without a `# prawduct:allow` waiver; the probe fails open on any scan error (advisory infra convention).
- **Critic mode:** chunk
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass.
  2. `/prawduct:critic chunk` run and blocking findings resolved.
  3. Committed and chunk marked `[x]` in Status.

### Chunk 06: Coherence & close — matrix row, OWASP-API security prompt, cumulative review

- **Description:** Make the change coherent and self-documenting, then run the one cumulative review that is the PR gate. Registers the new concern in the framework's own coverage model and lands the API-specific security prompt.

- **Depends on:** Chunks 01-05

- **Artifacts consumed:** `.prawduct/cross-cutting-concerns.md`, `methodology/discovery.md`, `templates/security-model.md`, `.prawduct/learnings.md`.

- **Deliverables:**
  1. `.prawduct/cross-cutting-concerns.md` — add a row "API design (produced)": Discovery = discovery.md structural line + project-state capture; Artifact = `api-contract.md` template + the project-state decision blocks; Builder = planning.md Exposed-API section + building.md pointer; Critic = Goal-2 versioning + error-model WARNING; Notes = advisory probe + doctor #9 + janitor theme. Distinguish it from the existing row 32 (Foreign API = consumed). Update Known Gaps as needed (e.g. note the coded auto-detect variant + the standalone error-model template are deferred follow-ups).
  2. `methodology/discovery.md` (and/or `templates/security-model.md`) — a concise API-specific security prompt referencing the OWASP API Security Top 10 (excessive data exposure, mass assignment, BOLA/object-level authz) as the API-*design* failure modes distinct from the generic authn the security pipeline covers. A pointer, not a new gate.
  3. Reconcile any residual token budgets across all touched methodology/Critic/skill files.
  4. `.prawduct/learnings.md` — capture the meta-lesson (a cross-cutting concern can be uncovered even when discovery names it once, if no artifact/builder/Critic stage operationalizes it — and the coverage matrix should be audited for "named-but-dropped" concerns, not just absent ones).

- **Tests:** full suite green: `python3 -m pytest -q`.
- **Acceptance criteria:**
  1. The matrix row is present and accurate; the OWASP-API prompt lands; learnings entry added.
  2. All touched budgeted files pass their guardrail tests.
  3. `/prawduct:critic cumulative` against `develop...HEAD` passes with no unresolved BLOCKING — the `/prawduct:pr create` gate.
- **Critic mode:** cumulative
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass.
  2. Committed.
  3. `/prawduct:critic cumulative` run against `develop...HEAD` and blocking findings resolved — the chunk's review AND the PR gate.
  4. Backlog hygiene: file the two deferred follow-ups (coded auto-detect variant of the Exposed-API check; standalone error-model artifact/template if wanted) via `/prawduct:backlog`.

## Early Feedback Milestone

**Milestone chunk:** Chunk 04 (doctor check + janitor theme) — the first point the user can run `/prawduct:doctor` against a real product (e.g. ../scriob) and watch the new check report. The Chunk 05 advisory then makes it ambient.

## Governance Checkpoints

**Commit & PR cadence:** Commit per chunk after its `/prawduct:critic <mode>` passes; the Chunk 01 keystone gets a `final` review; the last chunk's one `/prawduct:critic cumulative` (its review AND the `/prawduct:pr create` gate) covers `develop...HEAD`. Target: minor release.

- After Chunk 01: `final` review — validate the decision-record schema (the keystone) before Chunks 02-06 consume it.
- After Chunk 06: `cumulative` review — all 7 goals over `develop...HEAD`, the single independent-review gate before the PR opens.
