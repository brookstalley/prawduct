# Review Lenses

The Review Lenses provide multi-perspective evaluation of system output at every stage. They are five modes of critical thinking — Product, Design, Architecture, Skeptic, and Testing — applied to artifacts, decisions, and project state. They are not separate agents; they are perspectives the LLM adopts in sequence when invoked. The Review Lenses are invoked by the Orchestrator at stage transitions and at dependency boundaries during artifact generation.

## When You Are Activated

The Orchestrator activates this skill:

- During **Stage 0.5 (Validation):** Product and Skeptic lenses evaluate whether to build at all. (Medium/high-risk products only.)
- During **Stage 2 (Product Definition):** Product, Design, Architecture, and Skeptic lenses review crystallized decisions before artifact generation. (Testing Lens does not apply — no test specifications exist yet.)
- During **Stage 3 (Artifact Generation):** Lenses are applied in phases as artifacts are generated, not as a single post-hoc review (see Orchestrator Stage 3):
  - **Phase A (Foundation):** Product and Design lenses review the Product Brief before dependent artifacts are generated. Focus: Is the vision clear? Are personas realistic? Are flows complete? Are all states considered?
  - **Phase B (Structure):** Architecture lens reviews the Data Model and NFRs against the Product Brief. Focus: Do entities cover the flows? Are NFRs realistic for the platform and risk level?
  - **Phase C (Integration):** All five lenses review the complete artifact set. This is where cross-cutting concerns (security coverage, test completeness, dependency justification, failure modes) get full evaluation. The Testing Lens activates here — test specifications now exist and can be evaluated for comprehensiveness.
- During **Stage 4 (Build Planning):** Architecture lens reviews the build plan for feasibility and appropriate chunking. Skeptic lens checks for risks in the build ordering (e.g., late-stage dependencies, missing early feedback).
- During **Stage 5 (Build + Governance):** At governance checkpoints, Architecture, Skeptic, and Testing lenses validate the implementation so far. Architecture checks that the built code matches the designed structure. Skeptic checks for emerging risks (e.g., growing complexity, untested edge cases, drift from specs). Testing checks that implemented tests match specs and no coverage gaps have emerged.
- During **Stage 6 (Iteration):** Product lens evaluates change requests — is this what the user needs? Architecture lens evaluates blast radius — what does this change affect?

When activated:

1. Read `project-state.yaml` in the user's project directory to understand the product, its classification, and risk level.
2. Read the artifacts or decisions you've been asked to review.
3. Apply each requested lens in sequence.
4. Produce structured findings.

## Output Format

For each lens, produce findings in this format:

```
### [Lens Name] Lens

**Finding:** [Specific, concrete observation — not a vague impression.]
**Severity:** blocking | warning | note
**Recommendation:** [What to do about it.]
```

**Severity definitions:**
- **Blocking:** Must address before proceeding to the next stage. Reserved for issues that would cause real problems (missing critical functionality, security gaps, internal inconsistency).
- **Warning:** Must address before delivery but doesn't block forward progress. Issues that would hurt quality if ignored.
- **Note:** Worth considering. May improve the product but isn't a defect.

**Proportionality rule:** Severity must match the product's risk level. A note for a family utility might be a warning for a B2B platform. Don't treat every observation as a blocking issue — that makes the review useless because everything looks equally urgent.

## The Five Lenses

### Product Lens

**Core question:** Does this solve a real problem? Is the scope right?

**What to evaluate:**
- Is the vision clear and specific? Could someone not in this conversation understand what's being built?
- Are the personas realistic? Do they have distinct needs?
- Do the core flows address the personas' primary needs?
- Is the v1 scope appropriate — enough to be useful, not so much that it won't ship?
- Is anything missing that the user clearly needs but hasn't been captured?
- Is anything included that the user didn't ask for and probably doesn't need?

**Typical findings:**
- Scope includes features nobody asked for (warning)
- Core flow doesn't address primary persona need (blocking)
- Success criteria are vague or unmeasurable (warning)
- Vision statement is generic, could describe many products (note)
- Product definition references an external product or style ("like X", "X-style") without decomposing it into concrete, buildable specifications (warning). The specific borrowed aspects must be defined — otherwise every downstream artifact inherits the ambiguity and the Builder makes subjective interpretation decisions.

**What this lens does NOT do:** It doesn't evaluate technical feasibility (that's Architecture) or what could go wrong (that's Skeptic).

### Design Lens

**Core question:** Is the experience intuitive? Are all states handled?

**What to evaluate:**
- First-run / empty state: what does the user see before any data exists? Is this addressed?
- Error states: what happens when things go wrong? Are errors helpful?
- Loading states: if anything takes time, is the user informed?
- Accessibility: for UI applications, always produce a finding about accessibility. If accessibility has been addressed, acknowledge it as a note. If it hasn't been considered, raise it as a warning. Check: keyboard navigation, screen reader support, color contrast, touch target sizes — at the level of "has this been thought about," not a full audit.
- Onboarding: does a new user know what to do?
- Consistency: are interaction patterns consistent across flows?
- Visual/interaction identity: If the product references another product's visual style or interaction pattern, are the specific elements defined concretely enough to implement without subjective judgment? Layout proportions, spacing ratios, animation timing, and similar parameters should be specified, not assumed.

**Typical findings:**
- Empty state not addressed — user sees a blank screen (warning)
- Error messages are generic "something went wrong" (warning)
- No consideration of accessibility (warning for UI apps, note for utilities)
- Flow requires user to already know how the app works (note)

**What this lens does NOT do:** It doesn't evaluate whether the *right* thing is being built (that's Product) or whether the architecture supports it (that's Architecture).

**When to apply lightly:** For non-UI products (APIs, pipelines), the Design Lens has limited applicability. Apply it to any user-facing surfaces (API error messages, configuration interfaces) but don't force UI-thinking onto a pipeline.

### Architecture Lens

**Core question:** Will this work? Is it maintainable?

**What to evaluate:**
- Is the data model appropriate for the use cases? (Not over-normalized, not denormalized into incoherence.)
- Are the dependencies justified? Could anything be simpler?
- Is the security model proportionate? (Not too weak, not over-engineered.)
- Is the deployment strategy realistic for the product's scale?
- Are there obvious performance concerns given the NFRs?
- Is the technology appropriate for the problem? (Not using a sledgehammer for a nail.)

**Typical findings:**
- Data model missing an entity implied by core flows (blocking)
- Dependency added without justification (warning)
- Security model over-engineered for risk level (note)
- NFRs specify targets the architecture can't meet (warning)
- Deployment strategy assumes infrastructure the product doesn't need (note)

**What this lens does NOT do:** It doesn't evaluate whether the product is worth building (that's Product) or what could go wrong socially/operationally (that's Skeptic).

### Skeptic Lens

**Core question:** What will go wrong? What are we not thinking about?

**What to evaluate:**
- **Edge cases:** What happens at the boundaries? Zero users, maximum users, no data, corrupt data.
- **Failure modes:** What happens when external dependencies fail? When the network is down? When the device runs out of storage?
- **Abuse vectors:** If someone wanted to misuse this, how would they? Proportionate to risk — a family app has low abuse risk.
- **Cost surprises:** Will this cost more to run than expected? Are there per-use APIs or storage that could grow unexpectedly?
- **Unstated assumptions:** What is the system assuming that hasn't been validated? (E.g., "assumes all users have modern smartphones.")
- **Data loss risk:** Can the user lose their data? Is there a backup strategy?

**Typical findings:**
- No backup strategy — user could lose all data (warning for low-risk, blocking for higher)
- Assumes always-online but use case suggests offline scenarios (warning)
- No consideration of what happens when storage is full (note)
- Cost estimate missing for a pay-per-use API dependency (warning)

**What this lens does NOT do:** It doesn't fix problems — it finds them. Fixes are the responsibility of the Artifact Generator (for artifact issues) or the Orchestrator (for product-level issues).

### Testing Lens

**Core question:** Are the test specifications comprehensive, proportionate, and traceable to identified risks?

**When this lens applies:** Only when test specifications exist. This means Stage 3 Phase C (after Test Specifications are generated) and Stage 5 governance checkpoints. Does NOT apply in Stages 0-2, Stage 3 Phase A/B, or Stage 4.

**What to evaluate:**

- **Comprehensiveness:** Do test specs cover every core flow's happy path, error cases, and edge cases? For automations: does every pipeline stage have failure mode tests?
- **Risk traceability:** Do test specs cover the risks and edge cases the Skeptic identified? Every Skeptic finding should be traceable to at least one test scenario.
- **Failure mode coverage:** For each failure mode in the Failure Recovery Spec (automation) or implied by the architecture, is there a corresponding test?
- **Proportionality:** Is test depth appropriate to product risk? A family utility needs fewer scenarios than a financial platform. Over-testing is waste; under-testing is risk.
- **Specificity:** Are test scenarios concrete (setup, action, expected result) or generic ("test that it works")? Generic test scenarios provide false confidence.
- **Experiential proxy coverage:** For products with experiential quality requirements (visual aesthetics, responsiveness, timing feel), are there test scenarios for measurable proxies of the experiential goals? If NFRs specify render efficiency, a test should verify no full-screen redraws during normal operation. If a visual layout has proportional requirements, a test should verify the proportions mathematically. Not all UX quality is testable, but the testable proxies should be specified.
- **State coverage:** Are entity lifecycle transitions (from data model) tested, including invalid transitions?

**Typical findings:**
- Core flow X has happy-path test but no error case tests (warning)
- Skeptic identified risk Y (e.g., "feed format changes") but no test scenario covers it (warning)
- Failure Recovery Spec enumerates 8 failure modes but Test Specifications only cover 3 (blocking)
- Test scenarios are generic ("verify filtering works") rather than concrete (warning)
- Test depth disproportionate to risk — 40 test scenarios for a family utility (note)

**Proportionality guidance by risk level:**

| Risk | Expected findings | Blocking max |
|------|------------------|--------------|
| Low | 1-3 | 0-1 |
| Medium | 2-5 | 0-2 |
| High | 3-8 | 1-3 |

**What this lens does NOT do:** It doesn't evaluate test *implementation* quality (code correctness, assertion strength) — that's the Critic's Test Integrity Checker during build. The Testing Lens evaluates whether the right things are *specified* for testing, not whether the tests themselves are well-written.

## Framework Proportionality Observations

In addition to product-focused findings, every lens application should note whether the artifact being reviewed was **proportionate to the product's actual needs**. This is not a product finding — it's a framework observation that feeds back into framework improvement.

**What to watch for:**

- **An artifact that's mostly documenting absence.** If the majority of an artifact's content says "not applicable," "none," or "this product doesn't need [X]," note it. The artifact may be genuinely unnecessary for this product type, and the framework's artifact selection could be smarter.
- **A review that has nothing meaningful to say.** If a lens is applied to an artifact and produces no findings — not because the artifact is perfect, but because the lens's concerns simply don't apply — note that. The lens application may not be warranted for this product type.
- **An artifact that's missing.** If a lens reveals a gap that should be covered by an artifact the framework doesn't produce, that's a framework gap.

**Format:** Include these as a separate section after product findings:

```
### Framework Observations
[Brief note on whether this artifact and this lens application were proportionate for this product type. General observations only — no product-specific details.]
```

These observations are surfaced to the user via the Orchestrator's Framework Reflection Protocol and may lead to framework improvements.

---

## Applying Lenses to the Family Utility Scenario

For a low-risk utility like a family score tracker, the review should be **proportionate**:

- **Total findings across all lenses:** 5-12 for a low-risk product. Findings are issues or observations that require action or a specific decision — don't pad the count with positive reinforcement ("this looks good, no action needed"). If you're producing 20+ findings for a family score tracker, recalibrate.
- **Blocking findings:** 0-2 at most. A family app has few things that truly can't ship.
- **Tone:** Helpful, not adversarial. The goal is to improve the product, not to demonstrate thoroughness.
- **What NOT to raise:** Enterprise-scale concerns, regulatory compliance (unless the product actually triggers it), complex threat models, high-availability requirements.

## Applying Lenses to Automation/Pipeline Products

The following adjustments modify the general five-lens process described above for automation/pipeline products. Read the general lens descriptions first.

For automation/pipeline products, the lenses shift focus from user-facing concerns to operational concerns. The core question changes from "will users understand this?" to "will this run reliably unattended?"

### Automation Adjustments by Lens

| Lens | Automation-specific focus |
|------|--------------------------|
| **Product** | Evaluate automation scope vs. the manual process it replaces (boundary correctness). Check that success criteria are measurable for a headless system ("Digest delivered by 7 AM" not "Works well"). Check filtering/processing logic is concrete enough to implement. |
| **Design** | Does NOT evaluate screens or visual design. Evaluates: configuration UX (clear format, helpful error messages), output clarity (the pipeline's output IS its interface), observability UX (can the operator check health without digging through logs?), and error communication (do alerts explain what happened and what to do?). |
| **Architecture** | Evaluate stage isolation (can stages fail independently?), deployment appropriateness for the execution pattern and cost profile, resource efficiency (runaway cost risk from tight loops or unbounded fetches?), and operational complexity budget (infrastructure proportionate to problem?). |
| **Skeptic** | **Must always raise at least one silent-failure finding** (what happens when the pipeline fails and nobody notices?) **and at least one external-dependency-resilience finding** (what happens when services are down, slow, or rate-limited?). Also look for: configuration drift risk and cost creep from per-invocation API costs. |
| **Testing** | In addition to general criteria: every pipeline stage needs at least one failure mode test. Required automation-specific tests: silent failure detection (distinguish "no results" from "didn't run"), partial success (some sources fail, others succeed), and configuration validation (invalid/missing config). |

### Proportionality for Automation Reviews

- **Total findings across all five lenses:** 8-15 for a low-medium risk automation. Fewer than 8 likely misses operational concerns. More than 15 is over-reviewing for a side project.
- **Blocking findings:** 0-3 at most. The most likely blocking findings are: missing monitoring for silent failure, missing failure handling for a critical pipeline stage, or test specifications that don't cover failure modes.
- **What NOT to raise:** UI/UX concerns about screens or navigation (there are none), multi-user collaboration features, enterprise-grade SLA requirements for a side project, visual design feedback.

## Applying Lenses During Build (Stages 4-6)

During build phases, the lenses serve a different purpose than during artifact generation. Rather than evaluating specifications, they evaluate implementation.

**Stage 4 (Build Planning):**
- **Architecture Lens:** Is the chunk ordering technically sound? Are dependencies between chunks correctly identified? Is the scaffold sufficient? Would a developer reading this plan get stuck? Does the build plan faithfully translate all artifact specifications into build instructions? Specifically: are NFR technique requirements (not just targets) reflected as concrete instructions in the relevant chunks? Are data model constraints and experience-critical parameters reflected in chunk deliverables?
- **Skeptic Lens:** What's the riskiest chunk? What happens if a chunk fails or needs major rework? Is the early feedback milestone realistic?

**Stage 5 (Governance Checkpoints):**
- **Architecture Lens:** Does the built code match the data model? Are module boundaries respected? Is the code proportionately complex for the product's risk level?
- **Skeptic Lens:** Are there emerging risks? Untested paths? Growing complexity that suggests the architecture needs adjustment?
- **Testing Lens:** Do implemented tests match the test specifications? Have new gaps emerged as the implementation revealed edge cases not anticipated in specs?

**Stage 6 (Iteration):**
- **Product Lens:** Does this change request reflect what the user actually needs? Is it an improvement or scope creep?
- **Architecture Lens:** What's the blast radius? What code, tests, and artifacts need to change? Is this change compatible with the existing architecture?

**Proportionality in build-phase reviews:** Governance checkpoint reviews should be lighter than artifact reviews. The Critic handles per-chunk detail; the lenses provide a broader perspective at checkpoints. For low-risk products, 2-4 findings per checkpoint is appropriate.

## Extending This Skill

Phase 1 applies four lenses to universal artifacts for low-risk UI applications. Phase 2 added the Testing Lens and automation/pipeline shape guidance. Future phases add:

- [x] Stage 4-6 lens application guidance (Phase 2)
- [x] Testing Lens (5th lens): test specification comprehensiveness, risk traceability, failure mode coverage (Phase 2)
- [ ] Shape-specific lens guidance:
  - [x] Automation/Pipeline (Phase 2)
  - [ ] API/Service (Phase 2 widening)
  - [ ] Multi-party platforms (Phase 2 widening)
- [ ] Variable-depth reviews: lighter review for routine artifact generation, deeper review for major scope changes (Phase 2)
- [ ] Rotating emphasis: sometimes lead with security, sometimes with cost, to prevent blind spots (Phase 2)
- [ ] Integration with Critic (C6): Review Lens findings feed into the Critic's continuous governance during build (Phase 2)
