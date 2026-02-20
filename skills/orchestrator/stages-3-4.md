# Orchestrator: Stages 3–4 (Artifact Generation, Build Planning)

---

## Stage 3: Artifact Generation

**Trigger:** `current_stage` is "artifact-generation".

1. **Readiness check.** Before invoking the Artifact Generator, verify the Stage Transition Protocol prerequisites (read `skills/orchestrator/protocols.md` § Stage Transition Protocol if not already loaded). If anything is missing, fill it in now — don't proceed with gaps.
2. **Generate and review in phases.** Invoke the Artifact Generator as a **separate agent** per the Artifact Generator Agent Protocol in `skills/orchestrator/protocols.md`. Do NOT load `agents/artifact-generator/SKILL.md` into your context — the agent reads its own instructions. Artifacts are generated in dependency order, with Review Lenses applied at dependency boundaries to catch errors before they propagate downstream.

   For each phase, the cycle is: invoke AG agent → verify output → invoke Review Lenses agent → resolve blocking findings (re-invoke AG if needed) → proceed to next phase.

   **Phase A — Foundation:**
   1. Invoke the AG agent for Phase A (generate the Product Brief). Include project context, framework root, and structural characteristics in the prompt.
   2. Verify output: artifact exists at `.prawduct/artifacts/product-brief.md`, has YAML frontmatter, manifest updated.
   3. **MANDATORY**: Invoke the Review Lenses agent (per the Review Lenses Agent Protocol in `skills/orchestrator/protocols.md`) with the **Product and Design lenses** applied to the Product Brief.
   4. Update `project-state.yaml` → `review_findings.entries` with structured findings (stage, phase, lens, findings with severity/recommendation/status).
   5. If any blocking findings, re-invoke the AG agent with the findings and instruction to resolve them. The Product Brief is the foundation for all other artifacts — errors here infect everything.

   **Phase B — Structure:**
   1. Invoke the AG agent for Phase B (generate Data Model and NFRs). The agent reads the Phase A Product Brief from disk.
   2. Verify output: artifacts exist, frontmatter present, manifest updated.
   3. **MANDATORY**: Invoke the Review Lenses agent with the **Architecture lens** applied to the Data Model, NFRs, and their relationship to the Product Brief.
   4. Update `project-state.yaml` → `review_findings.entries` with structured findings.
   5. If any blocking findings, re-invoke the AG agent with the findings.

   **Phase C — Integration:**
   1. Invoke the AG agent for Phase C (generate Security Model, Test Specifications, Operational Spec, Dependency Manifest, and structural artifacts). The agent reads all prior artifacts from disk and runs the full cross-artifact consistency check.
   2. Verify output: all expected artifacts exist, frontmatter present, manifest updated, consistency check passed.
   3. **MANDATORY**: Invoke the Review Lenses agent with **all five lenses** (Product, Design, Architecture, Skeptic, Testing) across the complete artifact set. The Testing Lens activates here — test specifications now exist and should be evaluated for comprehensiveness, risk traceability, and failure mode coverage.
   4. Update `project-state.yaml` → `review_findings.entries` with structured findings (severity: blocking / warning / note).
   5. If any blocking findings, re-invoke the AG agent with the findings.

   **Risk-proportionate phasing:**

   | Risk Level | Phases | Notes |
   |------------|--------|-------|
   | Low | 2 checkpoints: Phase A + review, then Phase B+C combined + full review | Foundation review (Product Brief) is never skipped |
   | Medium | 3 phases as described above (A → B → C) | Standard flow |
   | High | 3 phases with deeper review at each boundary | Consider additional domain-specific lenses |

   **CRITICAL — Review Lenses are mandatory in Stage 3 regardless of risk level.** Invoke the Review Lenses agent per the Review Lenses Agent Protocol in `skills/orchestrator/protocols.md` at each mandatory phase. (Both Stage 2 and Stage 3 apply lenses. Stage 2 catches definition issues; Stage 3 catches artifact generation issues. Different stages, different quality gates.) If you are running a simulation or automated process, Review Lenses are still required. Skipping review = quality gate failure.

3. Present a summary of the artifacts and all review findings to the user, then continue to build planning. Do not wait for explicit confirmation.

4. Run the Framework Reflection Protocol (read `skills/orchestrator/protocols.md` § FRP if not already loaded). Record reflection in `change_log`.

5. Update `current_stage` to "build-planning".

**If the user interrupts with corrections** before or during build planning, handle them using the same cosmetic/functional/directional classification from Stage 2.

**Transition to Stage 4** after presenting artifacts and resolving any blocking review findings.

---

## Stage 4: Build Planning

**Trigger:** `current_stage` is "build-planning".

**What to do:**

1. Invoke the AG agent for Phase D (Build Planning) per the Artifact Generator Agent Protocol in `skills/orchestrator/protocols.md`. Do NOT load `agents/artifact-generator/SKILL.md` into your context. The agent reads all prior artifacts from disk, generates the build plan artifact (`artifacts/build-plan.md`), and populates `project-state.yaml` → `build_plan` with the strategy, chunks, and governance checkpoints.
2. Verify output: build plan artifact exists, frontmatter present, `build_plan` populated in project-state.yaml.
3. Invoke the Review Lenses agent with the **Architecture and Skeptic lenses** applied to the build plan and its relationship to prior artifacts. If any blocking findings, re-invoke the AG agent with the findings.

4. **Present the build plan to the user in plain language.** Not as a YAML dump — as a readable summary covering the technology, chunk sequence, what each delivers for the user, the early feedback milestone, and total chunk count. Example: "Here's the build plan: Setting up the project with [technology]. Then [chunks in order], each delivering [what the user cares about]. By chunk [N], you'll see [early feedback milestone]. [N] chunks total. Starting the build now." For low-risk products, keep to 1-2 paragraphs focused on sequence and when they'll see something working.

5. **Continue to build.** Do not wait for explicit confirmation — the user confirmed their intent when they described the product. If the user interrupts with changes:
   - **Reordering** (build X before Y): update chunk dependencies and order.
   - **Scope changes** (add/remove functionality): this is a Stage 2 concern — flag it. Small scope change (affects 1-2 artifacts and ≤1 chunk): update artifacts and regenerate the build plan. Large scope change (affects 3+ artifacts or requires new chunks): discuss whether to re-enter discovery.
   - **Technology changes**: update `technical_decisions`, relevant artifacts, and regenerate the build plan.

6. Run the Framework Reflection Protocol (read `skills/orchestrator/protocols.md` § FRP if not already loaded). Record reflection in `change_log`.

   **FRP focus for Stage 4:** Was the chunking appropriate? Did the build plan translate artifact specs into concrete instructions? Were there gaps between what the artifacts specify and what the Builder would need?

7. Update `current_stage` to "building".

**Transition to Stage 5** after presenting the build plan.
