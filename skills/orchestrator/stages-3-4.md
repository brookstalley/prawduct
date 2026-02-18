# Orchestrator: Stages 3–4 (Artifact Generation, Build Planning)

---

## Stage 3: Artifact Generation

**Trigger:** `current_stage` is "artifact-generation".

1. **Readiness check.** Before invoking the Artifact Generator, verify the Stage Transition Protocol prerequisites (read `skills/orchestrator/protocols.md` § Stage Transition Protocol if not already loaded). If anything is missing, fill it in now — don't proceed with gaps.
2. Read `skills/artifact-generator/SKILL.md` and `skills/review-lenses/SKILL.md`.
3. **Generate and review in phases.** Artifacts are generated in dependency order, with review lenses applied at dependency boundaries to catch errors before they propagate downstream. Follow the Artifact Generator's phased process:

   **Phase A — Foundation:** Generate the Product Brief.
   - **MANDATORY**: Apply the **Product and Design lenses** to the Product Brief.
   - After each lens application, update `project-state.yaml` → `review_findings.entries` with structured findings (stage, phase, lens, findings with severity/recommendation/status).
   - If any blocking findings, resolve them before proceeding. The Product Brief is the foundation for all other artifacts — errors here infect everything.

   **Phase B — Structure:** Generate the Data Model and Non-Functional Requirements.
   - **MANDATORY**: Apply the **Architecture lens** to the Data Model, NFRs, and their relationship to the Product Brief.
   - After each lens application, update `project-state.yaml` → `review_findings.entries` with structured findings.
   - If any blocking findings, resolve them before proceeding.

   **Phase C — Integration:** Generate the Security Model, Test Specifications, Operational Specification, Dependency Manifest, and any shape-specific artifacts.
   - **MANDATORY**: Apply **all five lenses** (Product, Design, Architecture, Skeptic, Testing) across the complete artifact set. The Testing Lens activates here — test specifications now exist and should be evaluated for comprehensiveness, risk traceability, and failure mode coverage.
   - The Artifact Generator runs a full cross-artifact consistency check at this stage.
   - After each lens application, update `project-state.yaml` → `review_findings.entries` with structured findings (severity: blocking / warning / note).
   - If any blocking findings, resolve them before presenting to the user.

   **Risk-proportionate phasing:**

   | Risk Level | Phases | Notes |
   |------------|--------|-------|
   | Low | 2 checkpoints: Product Brief + review, then all remaining artifacts + full review | Foundation review (Product Brief) is never skipped |
   | Medium | 3 phases as described above (A → B → C) | Standard flow |
   | High | 3 phases with deeper review at each boundary | Consider additional domain-specific lenses |

   **CRITICAL — Review Lenses are mandatory in Stage 3 regardless of risk level.** (Both Stage 2 and Stage 3 apply lenses. Stage 2 catches definition issues; Stage 3 catches artifact generation issues. Different stages, different quality gates.) If you are running a simulation or automated process, Review Lenses are still required. Skipping review = quality gate failure.

4. Present a summary of the artifacts and all review findings to the user, then continue to build planning. Do not wait for explicit confirmation.

5. Run the Framework Reflection Protocol (read `skills/orchestrator/protocols.md` § FRP if not already loaded). Record reflection in `change_log`.

6. Update `current_stage` to "build-planning".

**If the user interrupts with corrections** before or during build planning, handle them using the same cosmetic/functional/directional classification from Stage 2.

**Transition to Stage 4** after presenting artifacts and resolving any blocking review findings.

---

## Stage 4: Build Planning

**Trigger:** `current_stage` is "build-planning".

**What to do:**

1. Read `skills/artifact-generator/SKILL.md` — specifically Phase D (Build Planning).
2. Invoke the Artifact Generator's Phase D to produce the build plan artifact (`artifacts/build-plan.md`).
3. The Artifact Generator populates `project-state.yaml` → `build_plan` with the strategy, chunks, and governance checkpoints.

4. **Present the build plan to the user in plain language.** Not as a YAML dump — as a readable summary covering the technology, chunk sequence, what each delivers for the user, the early feedback milestone, and total chunk count. Example: "Here's the build plan: Setting up the project with [technology]. Then [chunks in order], each delivering [what the user cares about]. By chunk [N], you'll see [early feedback milestone]. [N] chunks total. Starting the build now." For low-risk products, keep to 1-2 paragraphs focused on sequence and when they'll see something working.

5. **Continue to build.** Do not wait for explicit confirmation — the user confirmed their intent when they described the product. If the user interrupts with changes:
   - **Reordering** (build X before Y): update chunk dependencies and order.
   - **Scope changes** (add/remove functionality): this is a Stage 2 concern — flag it. Small scope change (affects 1-2 artifacts and ≤1 chunk): update artifacts and regenerate the build plan. Large scope change (affects 3+ artifacts or requires new chunks): discuss whether to re-enter discovery.
   - **Technology changes**: update `technical_decisions`, relevant artifacts, and regenerate the build plan.

6. Run the Framework Reflection Protocol (read `skills/orchestrator/protocols.md` § FRP if not already loaded). Record reflection in `change_log`.

   **FRP focus for Stage 4:** Was the chunking appropriate? Did the build plan translate artifact specs into concrete instructions? Were there gaps between what the artifacts specify and what the Builder would need?

7. Update `current_stage` to "building".

**Transition to Stage 5** after presenting the build plan.
