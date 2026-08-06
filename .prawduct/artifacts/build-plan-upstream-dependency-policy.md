<!-- Build Plan: upstream-dependency-policy (target: minor — adds a cross-cutting
     concern, a new spec doc, and a new advisory probe)
     Tier: 1 (Source of Truth)

     Requirements: `.prawduct/artifacts/upstream-dependency-policy-discovery.md`
     (problem, the six clauses, the three enforcement tiers, the detection design,
     five owner rulings, five open assumptions, sources checked 2026-08-05).

     Design stance, inherited from api-design and re-confirmed by the owner:
     FORCE THE DECISION, don't mandate the answer. Every gate here is WARNING or
     advisory; nothing blocks. A product records its intake terms — including
     "none" — and the nudge goes quiet.

     THE GOVERNING SENTENCE, which every chunk answers to: this policy is about
     DEPENDENCIES, not package managers. It governs any upstream artifact whose
     release someone else controls, independent of delivery mechanism. Enumerating
     ecosystems is a non-normative appendix. An ecosystem prawduct has never heard
     of is COVERED and enforced at whatever tier it can reach.
-->
---
artifact: build-plan
version: 2
scope: upstream-dependency-policy
depends_on:
  - artifact: upstream-dependency-policy-discovery
governed_by:
  - artifact: architecture
    dispositions:
      - "prawduct guides and reviews, never implements; writes no product code, config or tooling → conforms — SEE THE ROUTING NOTE BELOW; this norm changed the design"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state, the evidence store, and the files it must reconcile → conforms, same routing"
      - "written in Python, never specific to Python; a language with no populated rules is reported as *unchecked*, never silently passed → conforms — the scan's third verdict (*unclassified*) IS this norm applied to intake surfaces"
      - "local-first: no network, no daemon, no third-party runtime dependencies → conforms — the probe and doctor check are offline; registry reads live in the product's own tier-3 procedure, which is the product's tooling, not the governance runtime"
      - "every fact has one home; every other mention is a reference → conforms — the six clauses, the tier model and the mapping appendix live only in `plugin/docs/upstream-dependency-policy.md`; all six other surfaces cite it"
      - "goals and verification bind; prescribed method is advice → conforms"
      - "authority fails closed; advice fails soft → conforms — every control added here is advisory or WARNING; none blocks"
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data, not instructions → conforms — the trusted-party register is data the agent verifies against reality, never a source of authority"
      - "a governed product's content never leaves its own repository and owner → conforms — this plan adds no network surface to the governance runtime"
      - "destructive/irreversible operations need operation-level owner approval → inapplicable because this plan adds no destructive operation"
  - artifact: nonfunctional-requirements
    dispositions:
      - "adding a control names the yield it expects AND emits that yield observably → conforms — each of the three new controls declares its expected yield in its chunk and emits it where `review-stats`-class tooling can count it; see the Yield Declarations section"
      - "review wall-clock is P0; reviewer payload is the lever → conforms — the Critic addition is one bullet inside an existing goal, held budget-neutral by same-chunk trim"
      - "state-file growth past threshold is advisory, never a hard block → inapplicable"
  - artifact: data-model
    dispositions:
      - "two stores, two lifetimes — shared committed answers vs per-clone gitignored nags → conforms — the recorded-policy fact is a shared committed answer; the advisory dismissal is a per-clone nag"
      - "governance verdicts computed from the append-only fact ledger, never model-written state → inapplicable because this plan writes no evidence-store facts"
  - artifact: operational-spec
    dispositions:
      - "gitflow — features branch off `develop` → conforms"
      - "versioning is conservative: a small feature is a patch bump → exception, recorded: minor bump. This is not a small feature — it adds a cross-cutting concern with seven pipeline legs, a new canonical spec document, and a new advisory probe. Same size class as api-design, which shipped minor."
last_validated: null
---

## THE ROUTING NOTE — the norm that changed the design

`prawduct-hook jurisdiction` surfaced a direct conflict between the requirements
document and a ratified `architecture.md` norm, and resolving it improved the design.

**The conflict.** The requirements doc's §7 says conformance drift is *"offered and
applied on confirmation,"* which read as *prawduct writes the product's `.npmrc` /
`dependabot.yml` / workflow pins.* Two architecture norms forbid exactly that:
*"Prawduct guides and reviews; it never implements. It writes no product code, no
config, and no tooling — a best practice enters as a requirement captured at
discovery, Claude Code implements it, and the Critic blocks on a requirement that
went unimplemented"*; and *"the plugin writes nothing into a governed repo except its
own `.prawduct/` state, the shared evidence store, and the files it must reconcile."*
A product's package-manager and CI configs are in neither allowed set.

**The resolution — conform, don't except.** The owner's ruling ("offer, apply on
confirmation") is about *who decides*, not *which process holds the file handle*. So:
**prawduct reports the drift and presents the exact edit; the agent in session writes
it, with the owner's confirmation.** No hook, gate, or probe writes product config.
That satisfies the owner's ruling exactly, conforms to both norms, and is the routing
the first norm literally prescribes — a best practice enters as a requirement and
Claude Code implements it.

**It is also the better design**, which is why this is `conforms` and not an exception:
the agent can act on the surfaces a scanner would have to enumerate, so the
*unclassified* verdict becomes actionable instead of merely honest.

**The same reasoning removed a planned chunk.** A Python conformance scanner walking a
hardcoded list of config filenames would have re-introduced, in code, the exact
allowlist trap §6 of the requirements exists to reject — and would have violated
*"never specific to Python… reported as unchecked, never silently passed."* The
conformance scan is therefore an **agent-performed procedure guided by the spec**
(Chunk 04), not a scanner. Code does only what code does well: check whether the
policy fact exists (Chunk 05).

## Requirements Confidence

**Level:** High

**Why:** Problem, success, and scope are each statable in one sentence and are written
up in full in `upstream-dependency-policy-discovery.md`, with five owner rulings
closed on 2026-08-05. The volatility gap — the one real risk in this domain — was
closed by research the same day (requirements §2, sources §12) rather than recalled.
Every insertion point below was located in-file this session by mapping the api-design
feature's seven legs, which is the direct structural precedent.

**Open assumptions / unknowns:** the same seven that requirements §11 now carries — §11 was reconciled to this list rather than left to disagree with it. Two were added at plan-authoring time (the Critic trigger, the probe's absent scan) and one was corrected from §11's original wording after the owner confirmed the fillable template. The five most load-bearing here:

- `[ASSUMPTION: the policy is a decision record (design_decisions.upstream_dependency_policy) + a top-level answer-store fact, with rationale and the trusted-party register as a security-model ## Direction norm entry — not a new strategy-class artifact template | MED impact | owner can promote it to its own artifact template]`
- `[ASSUMPTION: enforcement posture matches api-design end to end — advisory + doctor + janitor + Critic WARNING, never BLOCKING | MED impact | owner can request a blocking gate on updater-config drift]`
- `[ASSUMPTION: the tier-3 update procedure ships as a fillable template consuming the existing runbook machinery, not a generator and not a new artifact class | MED impact | owner can prefer methodology prose, accepting the weaker binding]`
- `[ASSUMPTION: the Critic trigger is an author-declared `**Dependency change:**` build-plan field, mirroring Foreign API's and Exposed API's opt-in model, rather than diff-detected from touched manifests | MED impact | diff-detection is the stronger guarantee but requires classifying "is this a dependency manifest", which is the allowlist trap; deferred to backlog as the api-design precedent did]`
- `[ASSUMPTION: the advisory probe fires universally on the missing fact with no codebase scan at all — because §6 made the trigger universal | LOW impact | the alternative is a scan, which is the rejected allowlist]`

**What would raise confidence:** N/A (High).

## Status

- [x] Chunk 01: Keystone — the policy decision record + capture-point wiring
- [ ] Chunk 02: The canonical policy spec + the security-model home
- [ ] Chunk 03: Forward Critic gate + the `**Dependency change:**` field
- [ ] Chunk 04: Retroactive — doctor check #15 (incl. the conformance procedure) + janitor
- [ ] Chunk 05: Migration nudge — the dependency-policy advisory probe (CODE)
- [ ] Chunk 06: Coherence & close — matrix row, Known Gaps overturn, update-procedure template
Context: Plan authored 2026-08-05 on `feature/upstream-dependency-policy` (off `develop`); requirements ruled the same day. Owner confirmed both post-ruling design changes (agent-performed conformance — *"it needs to be adaptable to any platform"* — and the tier-3 fillable runbook template).

**Chunk 01 DONE.** `templates/project-state.yaml` gained the `design_decisions.upstream_dependency_policy` block (7 sub-fields incl. `surfaces`, the per-surface enforcement-tier record) and the commented-out top-level `upstream_dependency_policy_decided` answer-store fact, whose comment records *why this probe has no detection gate* so a later reader doesn't add one. `discovery.md` gained "Surface Upstream Dependency Policy" between Infrastructure Dependencies and Observability — universal trigger, defaults-with-why per Principle 20, CI actions named as the non-manifest intake surface, no ecosystem named as a requirement. `planning.md`'s Dependency Manifest bullet now carries the justification/terms split. 3743 green.

**Three carried notes from Chunk 01's learnings lookup, none silently accepted:**
1. **Chunk 03 gained a deliverable** — the session-digest line (see that chunk). Rule: a new framework-wide default that doesn't reach migrated repos isn't framework-wide.
2. **Legend-refresh gap, recorded not closed.** `templates/project-state.yaml` is scaffold-only, so an already-onboarded repo never gains the new block's commented shape guide. The api-design precedent has the identical gap and routes around it: the *methodology* carries the shape and the advisory's `recommended_action` points there. `discovery.md`'s new section does carry it, so the routing holds — but the propagation surface named by the learning (a `migrate`/refresh step) is deliberately not built. Flagged for the Chunk 01 `final` review to judge.
3. **The `docs/` pointer is deferred to Chunk 02**, where the file exists. This note originally claimed as checked fact that "no commit on this branch carries a dangling reference" — **false, and the Chunk 01 review falsified it with one `ls`**: `discovery.md` was checked and the `templates/project-state.yaml` comment written minutes earlier was not, and it carried the path. Both now name the concept, not the path; Chunk 02 adds the pointers when the target exists. The lesson is the note itself — an assertion that a check was done disarms the next reader's check, so it must not outrun what was actually checked.

**Chunk 01 review dispositions** (`rev-20260805T224332Z-55b52f6c`, 1 blocking / 4 warnings / 2 notes — all FIXED in one batch except the two notes, both accepted): the blocking builder-leg gap → Chunk 03 deliverable 4 above. The dangling template ref → fixed, and this note corrected. The legend-refresh reasoning → the plan claimed api-design has "the identical gap"; it does not, because api-design's probe and doctor check test only *presence* while this design commits doctor #15 and janitor to reading named sub-keys — `discovery.md` now names those sub-keys and says why. The "unchanged" assumptions claim → §11 reconciled. "Five clauses"/six → fixed in §4. Notes accepted: `suite-total-claim` is an inert count the protocol says to leave alone, and backlog reconciliation is unavailable on the Issues backend.

**No `verify-resolutions` round was run** — owner instruction, 2026-08-05, to fix and commit without looping. The blocking finding therefore stays unresolved in the evidence store and the Critic gate will report it until a later review spans this tree; Chunk 02's review is the natural place, since it covers the same files.

**Persisted-schema consumer queries, enumerated before the fields were designed** (planning.md's lock-in rule): the advisory probe asks *does an answer exist* (top-level fact); doctor #15 asks *does it exist* and *is it expressed per surface* (`surfaces`); janitor asks *are trusted parties still trusted and still carrying a why* (`trusted`) and *do install-time execution and pinning still match* (`install_time_execution`, `resolution_pinning`); the Critic asks *is a policy recorded* (presence). Every query has a field.

**Chunk 02 BUILT, under review.** `develop` was merged in first (the branch was cut before
v3.2.6 and the critic-review-identity work; Chunk 03 edits `review-protocol.md` and
`goals-1-3.md`, so it needed their current text and current budgets, not the pre-merge ones).
The `active_build_plan` merge conflict resolved to THIS plan on the merits — develop's side
named a plan that had finished building, which is the dormant-pointer state that slot's own
incident history is made of.

New `plugin/docs/upstream-dependency-policy.md` is the canonical home: governing sentence, six
clauses, three tiers with their three rules, and the mapping appendix marked non-normative.
`templates/security-model.md` gained an `## Upstream Dependencies` section that POINTS at it and
asks only for what is the product's own (chosen values, the trusted register each-with-its-why,
the per-surface tier reached), plus a `## Direction` routing note. The Chunk 01 `docs/` pointer
deferred to here landed on all three surfaces — `discovery.md`, `planning.md`, and the
`project-state.yaml` legend — each citing the spec directly rather than hopping through another.

**The agnosticism guard was red-verified end to end**, not just against planted strings: a
`yarn.lock` planted in Clause 5 of the real file failed
`test_no_normative_statement_names_an_ecosystem` with its line number, and was reverted. Its
form-family covers package managers, both update bots, AND manifest/lockfile names — naming a
manifest file is the allowlist trap even when no tool is named. Tokens colliding with English
(`go`, `pub`, `hex`) are guarded at their qualified spellings so the check cannot cry wolf. A
companion test pins that the same detector fires ≥5 times in the appendix, so green over the
normative body means the property holds rather than the regex being broken.

**Two one-home copies removed while writing the pointers, both self-inflicted by the same
sentence.** Adding "the clauses have one home" above prose that restated the 7-day default made
`security-model.md` and the `project-state.yaml` legend contradict themselves in place; both now
point at the spec, and a `\d+\s*days?` guard keeps the template from regaining a numeric default.
**Left deliberately:** `discovery.md` still carries the defaults in conversational form, because
its job is the elicitation script and an interviewer should not need a second file mid-interview
— the new sentence marks it as such ("what follows is how to elicit them"). Flagged for review
rather than silently kept.

**The Chunk 01 blocking finding is still unresolved in the evidence store** (line above: no
`verify-resolutions` ran, by owner instruction). `check-cumulative-critic` reports the span
uncovered. This chunk's review is the one that covers the same files.

**Chunk 02 review dispositions** (`rev-20260806T043411Z-61463dc4`, `chunk`, 1 blocking / 1 warning
/ 2 notes — all FIXED, none accepted or filed):

- **BLOCKING — the `governed_by` one-home claim was false of the tree.** `discovery.md` restated
  the 7-day default with its why, five clause substances, the tier model's Binds column and the
  intake-surface enumeration, in a form a reader can act on without following the pointer — which
  is the norm's own stated line. The finding's decisive evidence was empirical, not theoretical:
  the copies had **already diverged on day one**, before anyone edited either (spec 9 intake
  surfaces, discovery 7; "extensions" vs "plugins"). Offered an exception as the cheap route and
  it was declined on the merits — the divergence had already happened, so an exception would be
  recording a defect rather than accepting a trade. Fixed by splitting on ownership: **the spec
  owns what the policy says, `discovery.md` owns how to elicit it.** The clause substance, the
  number and the tier semantics are now citations; the trigger, the stance, the prompt-with-CI-
  actions guidance, the risk scaling and Chunk 01's reasoned sub-key list all stay, because those
  are discovery's own and not the spec's.
- **WARNING — the template's pointer did not resolve from the repo it ships into.** `security-
  model.md` is instantiated as a *product's* artifact where no `docs/` exists, and the section's
  entire routing rests on "read them there". Now qualified "in the prawduct plugin (not a path in
  this repo)", following `templates/runbook.md`, which is the one other template aimed at an
  author standing in their own repo.
- **NOTE — the guard covered one of seven surfaces.** Closed rather than accepted: the guards are
  now a parametrized sweep over `_POLICY_SURFACES`, and a roster-non-empty test stops it silently
  scanning nothing. Chunks 03-05 add their Critic bullet, doctor check, janitor theme and probe to
  that tuple; `_ECOSYSTEM_RE` is already reusable.
- **NOTE — the Deliverables list did not name the pointer edits.** Added as deliverable 4.

**A defect the fix commit found in its own tests.** Qualifying the template pointer added the
string `` `## Upstream Dependencies` `` to the Direction comment — and the test's section
extraction used `str.index`, which then bound to that *mid-sentence mention* instead of the real
heading, silently widening the scanned region to include four unrelated sections. Every assertion
still passed. `extract_section` is now line-anchored. The general shape: a test that locates its
subject by substring is one prose edit away from testing the wrong region, and it fails silently
because the wrong region usually still contains the right words.

Next: Chunk 03 — which lands against ~9/2/3 tokens of headroom on
`review-protocol.md`/`goals-1-3.md`/`building.md` respectively, so its trim is real work, not a
rider.

## Yield Declarations

`nonfunctional-requirements.md` binds every new control to name its expected yield and
emit it observably, so it can later be retired on evidence rather than defended on
principle. Three controls are added here:

| Control | Expected yield | Emitted where |
|---|---|---|
| `dependency-policy-undeclared` advisory (Ch. 05) | Fires once per product with no recorded policy; goes silent permanently on the recorded fact. A product where it fires and is *dismissed* rather than resolved is the signal the default is wrong. | Advisory store; dismissal vs resolution is already distinguishable there. |
| Critic Goal 2 WARNING on `**Dependency change:**` (Ch. 03) | A chunk that changes dependencies against no recorded policy. Expected to fire rarely after adoption — a sustained zero means the field is not being declared, not that the check works. | Review facts, counted by the existing `review-stats` mode grouping. |
| Doctor check #15 (Ch. 04) | Per-surface tier drift: policy recorded but not expressed where it could be. Expected to be the highest-yield of the three, because tier-1 expression is the leg products will skip. | Doctor's `degraded` classification line. |

## Build Chunks

### Chunk 01: Keystone — the policy decision record + capture-point wiring

- **Description:** Establish the one concept everything else keys off — a *recorded upstream intake policy* — and wire the two capture points (discovery elicits, planning carries). Chunks 02-06 all read this. Thin vertical slice through the spine: data model → discovery capture → planning capture.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/upstream-dependency-policy-discovery.md` (§4 the clauses, §5 the tiers, §6 the trigger design); `.prawduct/cross-cutting-concerns.md`; `plugin/templates/project-state.yaml`; `plugin/methodology/discovery.md`; `plugin/methodology/planning.md`.
- **Deliverables:**
  1. `plugin/templates/project-state.yaml` — under `design_decisions`, an `upstream_dependency_policy` block in house style, defaulting `null`: `minimum_release_age` (default 7 days), `trusted` (the two-tier definition + the declared-party register's pointer), `security_fast_path`, `install_time_execution`, `resolution_pinning`, `new_dependency_intake`, plus `surfaces` — the per-intake-surface record of **which enforcement tier was actually reached** (§5 rule 2), and `status` [active|deferred] + `rationale`. Add a top-level `upstream_dependency_policy_decided` answer-store fact, documented as a commented-out optional key matching the `api_versioning_decided` convention — absent and null both read as undecided. **No `revisit_trigger` field** (owner ruling: revisiting needs no scheduled prompt).
  2. `plugin/methodology/discovery.md` — a new "Surface Upstream Dependency Policy" section, sibling to Error Handling and Observability: asked of **every** product (§6's universal trigger — there is no detection gate), scaled to risk, offering prawduct's defaults with their why rather than interrogating (Principle 20). Must state that a product consuming no upstream code records that in one line, and must name at least one non-package-manager intake surface so the section cannot be read as being about package managers. Unbudgeted file — no trim needed.
  3. `plugin/methodology/planning.md` — the policy's bearing on planning: a chunk that adds or updates a dependency carries the decision, and the artifact-generation list gains the intake policy alongside the Dependency Manifest entry (line 24), which today covers justification only.
- **Tests:** none new (template/doc only). Guard: `plugin/templates/project-state.yaml` must remain valid YAML and existing template-shape tests must pass.
- **Acceptance criteria:**
  1. `plugin/templates/project-state.yaml` parses as valid YAML; the decision block and the commented-out answer-store fact are present in house style.
  2. `python3 -m pytest -q` green (no regressions).
  3. The discovery section is phrased with no ecosystem named as a requirement, states the universal trigger, and names a non-package-manager intake surface.
- **Critic mode:** final
  <!-- Override forward to `final`: this chunk lands the schema Chunks 02-06 consume;
       its shape must be right before anything reads it (planning.md "Override forward
       to final on an early keystone"). -->
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass.
  2. `/prawduct:critic final` run and blocking findings resolved.
  3. Committed and chunk marked `[x]` in Status.

### Chunk 02: The canonical policy spec + the security-model home

- **Description:** Write the one file that owns the policy — six clauses, three enforcement tiers, and the mapping appendix marked non-normative — and give the product-facing rationale its home. `architecture.md`'s *every fact has one home* norm makes this chunk the single point of truth every later surface cites rather than restates.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `.prawduct/artifacts/upstream-dependency-policy-discovery.md` (§4, §5, §9); `plugin/docs/norms.md` and `plugin/docs/waivers.md` (the `docs/` spec-file convention); `plugin/templates/security-model.md`.
- **Deliverables:**
  1. new `plugin/docs/upstream-dependency-policy.md` — the canonical spec. Sections: the governing sentence (dependencies, not package managers); the six clauses stated with no ecosystem named; the three enforcement tiers with their three rules (prefer strongest available; record the tier reached per surface; tier 3 is where judgment lives everywhere, not a consolation prize); and a **clearly-marked non-normative mapping appendix** carrying §9's three requirements verbatim — no policy statement may be phrased in terms of a named ecosystem, an absent ecosystem is fully covered at its best reachable tier, and a stale table is a documentation defect and never a coverage gap.
  2. `plugin/templates/security-model.md` — a new "Upstream Dependencies" section in the template's comment style, proportionate-to-risk like its siblings, pointing at the spec above for the clauses and telling the author what belongs *here*: the product's chosen values, its declared trusted parties **each with a why**, and its per-surface tier record. Note in the existing `## Direction` guidance comment that the intake policy is norm-shaped (it binds future work) so it lands as a Direction entry, not loose prose.
  3. **Guard tests** (`tests/test_v5_templates.py`): the spec file states the governing sentence; the mapping appendix is marked non-normative; no clause statement names an ecosystem (the agnosticism guard — this is the test that makes the governing sentence enforceable rather than aspirational); the security-model section exists and points at the spec rather than restating the clauses. The agnosticism and one-home guards sweep **every** surface that states the policy, not the spec alone: requirement 1 binds "policy statement, gate, or check", and a guard on one file is what let the same defect sit unnoticed on a neighbouring one.
  4. **The `docs/` pointers Chunk 01 deferred to here** — `methodology/discovery.md`, `methodology/planning.md`, and the `templates/project-state.yaml` legend each cite the spec directly once it exists. Chunk 01's carried note 3 assigns them to this chunk; listing them here so the deliverable roster matches what the chunk lands.
- **Tests:** the guard tests above. Each fails before the deliverable exists.
- **Acceptance criteria:**
  1. new `plugin/docs/upstream-dependency-policy.md` exists with all sections; the appendix is explicitly non-normative.
  2. The agnosticism guard test passes and would fail if a clause were rewritten to name npm or uv.
  3. `python3 -m pytest -q` green.
- **Critic mode:** chunk
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass.
  2. `/prawduct:critic chunk` run and blocking findings resolved.
  3. Committed and chunk marked `[x]` in Status.

### Chunk 03: Forward Critic gate + the `**Dependency change:**` field

- **Description:** The forward gate that prevents new drift: a chunk that changes dependencies, or edits an updater config, against no recorded policy → WARNING. Mirrors the Foreign-API and Exposed-API bullets exactly (Goal 2, author-declared, prose-only, no hook).
- **Depends on:** Chunk 02 (the spec the bullet cites)
- **Artifacts consumed:** `plugin/skills/critic/review-protocol.md` and `plugin/skills/critic/goals-1-3.md` (Goal 2 — the Exposed-API bullet is the model, and the two files carry the check for the single-pass and coordinator rosters respectively); `plugin/templates/build-plan.md`.
- **Deliverables:**
  1. `plugin/skills/critic/review-protocol.md` and `plugin/skills/critic/goals-1-3.md` — under Goal 2, beside the Exposed-API bullet: a chunk declaring `**Dependency change:**` needs a recorded upstream intake policy (`upstream_dependency_policy` present, or an explicit deferral) → **WARNING** if missing. **Both files, not one** — they are the two roster paths and a bullet in only one is a check that fires or not depending on review mode.
  2. `plugin/templates/build-plan.md` — a `**Dependency change:**` field beside `**Foreign API:**` and `**Exposed API:**` (~line 164), same comment style.
  3. `plugin/methodology/session-digest.md` — one line in the hardest-rules block: the agent's own dependency actions are governed by the product's recorded intake policy. **Added to this chunk after Chunk 01's learnings lookup** surfaced the rule *"a new framework-wide DEFAULT must land in the session digest — place-once preferences and the thin anchor don't reach migrated repos."* The digest is the only surface reaching every product vintage, and the owner's requirement was explicitly that the policy binds *"when the agent takes action, everywhere"* — without this line the agent-behavior arm reaches new products only. The digest is token-budget-bound: fund the line by trim in this chunk.
  4. `plugin/methodology/building.md` — extend § Decision Research's `**external dependency**` trigger (line 152, which today reads "long-term library/service reliance") so it covers the *terms* of entry, not only whether to depend at all. **This is requirements §7's second Builder deliverable**, and it had no chunk home until the Chunk 01 review found it — §7 names two (the `planning.md` section, delivered in Chunk 01, and this one) and §8 scopes the builder leg in with no carve-out. `building.md` is at its token ceiling (< 4810): fund the addition by trim in this chunk.
  5. Hold both Critic files, the digest, and `building.md` under their token ceilings (`tests/test_v5_methodology.py`: review-protocol.md < 3620, goals-1-3.md < 2000) by trimming adjacent prose **in this chunk**, never by weakening an existing check.
- **Tests:** none new (the Foreign-API and Exposed-API checks are prose-only on the same model); the existing token-ceiling tests are the guard.
- **Acceptance criteria:**
  1. The bullet reads symmetric to the Exposed-API bullet in **both** files; severity is WARNING.
  2. Both Critic files pass their token-ceiling tests; `python3 -m pytest -q` green.
  3. The build-plan field is present with a comment naming what it triggers.
- **Critic mode:** chunk
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass.
  2. `/prawduct:critic chunk` run and blocking findings resolved.
  3. Committed and chunk marked `[x]` in Status.

### Chunk 04: Retroactive — doctor check #15 (incl. the conformance procedure) + janitor

- **Description:** How an already-built product gets *found*, and the chunk that carries the conformance scan. Per the routing note, the scan is an **agent-performed procedure guided by Chunk 02's spec** — not a Python scanner — which is what lets it recognize intake surfaces no allowlist would enumerate and report *unclassified* honestly.
- **Depends on:** Chunks 01 and 02
- **Artifacts consumed:** `plugin/skills/doctor/SKILL.md` (checks #9 and #11 are the model — a check paired with an advisory probe; #14 is the highest existing number); `plugin/skills/janitor/SKILL.md` (the **Dependency Health** theme already exists at ~line 109 — extend it, do not add a theme); `plugin/docs/doctor-vs-janitor.md` (the placement rule).
- **Deliverables:**
  1. `plugin/skills/doctor/SKILL.md` — health check #15 "Upstream dependency policy", modelled on #9's report-and-recommend shape (no auto-edit). Two parts: **(a)** policy recorded? → `degraded` if not; **(b)** the conformance procedure — enumerate this repo's intake surfaces *by reading, not by matching a filename list*, and for each report **conformant / drifted / unclassified**, present the exact edit for the drifted ones, and write nothing without the owner's yes. Must state explicitly that unclassified surfaces are reported and that a scan finding them **does not report clean**. Extend the degraded-classification line. Add the routing note's rule in one sentence: prawduct reports, the agent applies.
  2. `plugin/skills/janitor/SKILL.md` — extend the existing **Dependency Health** theme with intake questions (is the recorded policy expressed at the best available tier per surface; are declared trusted parties still trusted and still carrying a why; are install-time execution and pinning still as recorded) and add the counterweight the theme currently lacks: today it asks only whether dependencies are *current*, which is one-directional pressure toward taking updates. Survey, not gate.
- **Tests:** none new (skill prose). Guard: any existing skill-file structure tests must pass.
- **Acceptance criteria:**
  1. Check #15 mirrors #9's shape, numbers correctly after #14, and states both the three-valued verdict and the reports-not-writes rule.
  2. The janitor change **extends Dependency Health** rather than adding a theme, and adds the current-ness counterweight.
  3. `python3 -m pytest -q` green.
- **Critic mode:** chunk
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass.
  2. `/prawduct:critic chunk` run and blocking findings resolved.
  3. Committed and chunk marked `[x]` in Status.

### Chunk 05: Migration nudge — the dependency-policy advisory probe (CODE)

- **Description:** The ambient trigger — what tells an already-onboarded product it has no recorded intake policy without anyone thinking to run a skill. The only code chunk, and deliberately the simplest possible probe: §6 made the trigger **universal**, so it fires on the missing fact with **no codebase scan at all**. That absence is the design, not an omission — a scan here would be the allowlist the requirements reject.
- **Depends on:** Chunk 01 (the `upstream_dependency_policy_decided` fact)
- **Artifacts consumed:** `plugin/lib/api_versioning_probes.py` (the closest template); `plugin/lib/advisory_store.py` (`register_probe`, `AdvisoryCandidate`, `ProjectState`); `plugin/lib/probe_families.py` (the composition root); `plugin/lib/briefing.py` (renders advisories — no change expected).
- **Deliverables:**
  1. new `plugin/lib/dependency_policy_probes.py` — `FEATURE = "upstream-dependency-policy"`, type `dependency-policy`, v1. Fires an `info` `AdvisoryCandidate` when the top-level `upstream_dependency_policy_decided` fact is falsy; suppressed by the recorded fact. `recommended_action` points at recording the decision. Includes a `register()` mirroring the api-versioning probe's. The module docstring must record *why there is no `Codebase` scan*, so a later reader does not "fix" the omission by adding one.
  2. `plugin/lib/probe_families.py` — register the new family alongside the existing eight in `register_all()`.
  3. new `tests/test_dependency_policy_probe.py` — fires when the fact is unset; suppressed when set; suppressed when explicitly recorded as "none"; roster registration; and a regression test asserting the probe consults **no** codebase scan (the design property above, pinned so it cannot be silently changed).
- **Tests:** `tests/test_dependency_policy_probe.py` above. Each behavior has a case that fails before the probe exists and passes after.
- **Acceptance criteria:**
  1. New tests pass; `python3 -m pytest -q` green.
  2. Probe is registered — a session-start sync in a repo with no recorded policy surfaces the advisory in the briefing; recording the fact suppresses it. Verify end-to-end, not by unit test alone.
  3. No new broad `except` without a `# prawduct:allow` waiver; the probe fails open on any read error (advisory infrastructure convention).
- **Critic mode:** chunk
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass.
  2. `/prawduct:critic chunk` run and blocking findings resolved.
  3. Committed and chunk marked `[x]` in Status.

### Chunk 06: Coherence & close — matrix row, Known Gaps overturn, update-procedure template

- **Description:** Make the change coherent and self-documenting, then run the one cumulative review that is the PR gate. Includes the tier-3 deliverable and the correction of a framework position this work overturns.
- **Depends on:** Chunks 01-05
- **Artifacts consumed:** `.prawduct/cross-cutting-concerns.md`; `plugin/templates/runbook.md`; `plugin/docs/runbook-authoring.md`; `.prawduct/learnings.md`; `.prawduct/change-log.md`.
- **Deliverables:**
  1. `.prawduct/cross-cutting-concerns.md` — a new row **"Upstream dependency intake"**, distinct from the existing *Dependency management* row (justification) exactly as *API design (produced)* is distinct from *Foreign API verification* (consumed). Columns per the seven legs in requirements §7.
  2. `.prawduct/cross-cutting-concerns.md` Known Gaps — **overturn the standing position.** The bullet currently reads *"Dependency management has no discovery trigger. Dependencies are a planning concern. This is by design."* Replace it: the justification half remains a planning concern; the **intake** half now has a discovery trigger, and say why the original position no longer holds (the threat model it predates). Do not delete the sentence silently — a reversed position is recorded as a reversal.
  3. new `plugin/templates/dependency-update-runbook.md` — the tier-3 deliverable (requirements §5): a fillable procedure a product derives from its recorded policy — enumerate available updates, obtain publication times, classify by tier and clause, act — built on the existing runbook machinery and pointed at from `plugin/docs/upstream-dependency-policy.md`. Written per `plugin/docs/runbook-authoring.md`.
  4. `.prawduct/learnings.md` — capture the two meta-lessons this work produced: (a) a policy for a multi-ecosystem concern must key its detection off *the decision being recorded*, not off enumerating the ecosystems, or the detector becomes the allowlist the policy exists to avoid; (b) `prawduct-hook jurisdiction` caught a norm conflict that plain review would have shipped — the conformance-write routing — which is evidence about *when* to run it (before writing the plan, not at review).
  5. `.prawduct/change-log.md` — the feature entry, tagged `scope=upstream-dependency-policy` per the bundle-at-release convention.
- **Tests:** `python3 -m pytest -q` green; all touched token budgets pass.
- **Acceptance criteria:**
  1. The matrix row is present and accurate; the Known Gaps reversal is recorded as a reversal with its reason.
  2. The runbook template exists and is reachable from the spec.
  3. `/prawduct:critic cumulative` against `develop...HEAD` passes with no unresolved BLOCKING — the `/prawduct:pr create` gate.
- **Critic mode:** cumulative
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass.
  2. Committed.
  3. `/prawduct:critic cumulative` run against `develop...HEAD` and blocking findings resolved — this chunk's review AND the PR gate.
  4. Backlog hygiene: file the deferred follow-up via `/prawduct:backlog` — the diff-detected variant of the `**Dependency change:**` trigger (open assumption 4), cross-linked to the api-design equivalent CRT-4Q7K, which is the same deferral for the same reason.

## Early Feedback Milestone

**Milestone chunk:** 04 — the first point the owner can run `/prawduct:doctor` against a real product and watch check #15 report its three-valued verdict on that product's actual intake surfaces. Chunk 05 then makes the nudge ambient.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its `/prawduct:critic <mode>` passes; the Chunk 01 keystone takes a `final` review; Chunk 06's single `cumulative` is both its own review and the `/prawduct:pr create` gate over `develop...HEAD`. Target: minor release.

- **After Chunk 01:** `final` — validate the decision-record schema before Chunks 02-06 consume it, and specifically that the `surfaces` per-tier record is shaped to carry §5 rule 2 honestly.
- **After Chunk 02:** confirm the agnosticism guard genuinely bites — write a clause naming an ecosystem, watch the test fail, revert. A guard that has never been seen to fail is not known to work.
- **After Chunk 06:** `cumulative` — all seven goals over `develop...HEAD`, the single independent-review gate before any PR.
