# Orchestrator: Stages 0–2 (Intake, Discovery, Definition)

---

## Stage 0: Intake & Triage

**Trigger:** New project (`current_stage: intake`), or user provides a new product idea.

**What to do:**

1. Read `skills/domain-analyzer/SKILL.md`.
2. Follow the Domain Analyzer's classification process (Steps 1-4): detect structural characteristics, identify domain-specific characteristics, classify domain, and assess risk profile.
3. The Domain Analyzer will state the classification to the user in plain language. Do not wait for confirmation — keep moving unless the classification is genuinely ambiguous (e.g., the product could plausibly be two fundamentally different things). Example: "This looks like a [domain] product with [characteristics]. Moving into discovery..."
4. Update `project-state.yaml` with classification results and initial `user_expertise` inferences from the user's opening message.
5. Run the Framework Reflection Protocol (read `skills/orchestrator/protocols/governance.md` § FRP if not already loaded). Record reflection in `change_log`.
6. Update `current_stage` to "discovery".

**Transition to Stage 1** immediately after classification. The user can correct the classification at any time — if they do, update and continue.

---

## Stage 1: Discovery

**Trigger:** `current_stage` is "discovery".

**What to do:**

1. Read `skills/domain-analyzer/SKILL.md`.
2. Follow the Domain Analyzer's discovery question generation (Step 5): generate tiered questions appropriate to the product's structural characteristics, domain characteristics, and risk level.

3. **Manage the conversation:**

   **Pacing rules by risk level:**

   | Risk | Rounds | Style |
   |------|--------|-------|
   | Low | 1-2 | Batch questions. Infer aggressively. Confirm assumptions in bulk. |
   | Medium | 2-4 | Ask the most impactful questions first. Infer where possible. |
   | High | 3-6 | Thorough but still prioritized by impact. Never exhaustive for its own sake. |

   **Within each round:**
   - Present 2-4 questions at a time, not one by one — serial questions feel like an interrogation.
   - Group related questions naturally.
   - Include your inferences alongside the questions: "I'm assuming X — let me know if that's wrong. Meanwhile, a few questions..."
   - After each user response, update `project-state.yaml` with newly discovered information.

4. **Monitor for "good enough":**

   After each round, assess: do we have enough to define the product? "Enough" means you can answer all of these:
   - Who uses this?
   - What's the core experience?
   - Where does it run?
   - What's in v1 scope?
   - What are the major design considerations?

   For low-risk products, one round of questions plus aggressive inference is often enough. Don't keep asking questions just because the question budget allows more. Stop when you have what you need.

5. **Surface proactive expertise** from the Domain Analyzer's question tiers (items marked for surfacing as considerations, not asking as questions) and its Proactive Expertise section. Frame as helpful observations or recommendations, not additional questions.

   **Guidance Evaluation during discovery.** When the user provides direction during discovery (technology preferences, architecture constraints, design requirements), apply the Guidance Evaluation trigger signals from `skills/orchestrator/stage-6-iteration.md` § Guidance Evaluation. Calibrate challenge tone to the user's expertise level (see Expertise Calibration in `skills/orchestrator/protocols/governance.md`): technical users get direct challenges with technical rationale; non-technical users get gentler framing focused on outcomes rather than principles.

   **Verification tooling opt-in.** When `has_human_interface` is active (especially web or desktop modality), surface agent verification as a consideration during discovery: "Products with user interfaces benefit from agent-accessible verification — tools that let the building agent observe and test the running product during development. Want to include verification infrastructure in the build plan?" If yes, record in `project-state.yaml` → `technical_decisions` and the Artifact Generator will include verification specifications. See `docs/high-level-design.md` § Agent Verification Architecture for the general principle.

6. **Re-evaluate risk profile.** Before transitioning, check whether discovery revealed complexity not apparent at classification time. The user's initial description may understate technical depth (e.g., "an app that plays sounds" may turn out to require real-time audio synthesis). If any risk factor has materially changed, update `classification.risk_profile` in `project-state.yaml`. If overall risk has increased, consider whether additional discovery is warranted before proceeding — but don't re-run discovery just because risk increased; only if the higher risk reveals gaps in what you've learned.

7. Run the Framework Reflection Protocol (read `skills/orchestrator/protocols/governance.md` § FRP if not already loaded). Record reflection in `change_log`.

8. Update `current_stage` to "definition".

**Transition to Stage 2** when you have enough to define the product.

---

## Stage 2: Product Definition

**Trigger:** `current_stage` is "definition".

### Complete project state

The Domain Analyzer will have populated many fields during Stage 1. Complete these sub-tasks:

1. Check that all required fields have values (see the Domain Analyzer's Output section for the field list).
2. Fill in anything the conversation revealed that wasn't captured yet.
3. Add `product_definition.goals` (measurable success criteria) — infer these from the conversation.
4. Make `product_definition.scope` decisions explicit: what's in v1, what's accommodated but not built, what's deferred to later (with rationale), and what's out of scope entirely (with rationale). Every feature discussed should land in exactly one bucket.
5. Set `product_definition.nonfunctional` values proportionate to the product's risk level.
6. Populate `technical_decisions` with proportionate architecture choices. Every decision must include rationale and alternatives considered (HR4). The guiding principle: **identify every architectural choice that would significantly affect implementation complexity, cost, or user experience if decided differently.** For low-risk products, make these decisions as assumptions and state them plainly. For higher-risk products, surface the tradeoffs. Common decisions include data storage, deployment target, and key technology choices — but don't limit yourself to a fixed checklist. If the product's nature raises architectural questions (e.g., how data stays in sync, how identity works, how components communicate), those are technical decisions too.
7. For UI applications, set basic `design_decisions`: at minimum, `accessibility_approach` (even "standard platform accessibility" is fine for low-risk) and general `interaction_patterns` (e.g., "mobile-first, touch-friendly"). Also set `visual_direction` — translate `product_definition.product_identity.personality` and `visual_preferences` into a concrete direction. If the user expressed preferences ("playful," "clean and minimal," "dark and moody"), translate those into a direction the Design Direction artifact can build on. If no preferences were expressed, choose a style appropriate to the platform and domain and state it as a design choice with rationale. Even for low-risk products, a one-line `visual_direction` prevents the Builder from guessing.
8. Populate `product_definition.cost_estimates` with at least a rough hosting/operational cost expectation, even if the answer is "$0 — free tier."

### Review

Before presenting to the user, invoke the Review Lenses agent per the Review Lenses Agent Protocol in `skills/orchestrator/protocols/agent-invocation.md`, requesting Product, Design, Architecture, and Skeptic lenses on the product definition. Surface any blocking findings. This catches fundamental issues (wrong scope, missing personas, infeasible architecture) before artifact generation begins. Even simple products benefit from clarity — the lenses are lightweight for simple products (they find less to flag), so the overhead is minimal. (The Testing Lens does not apply at this stage — no test specifications exist yet.)

After each lens application, update `project-state.yaml` → `review_findings.entries` with structured findings (stage, phase, lens, findings with severity/recommendation/status).

### Present and continue

1. **Present the product definition to the user** in plain language. Not as a YAML dump — as a readable summary:

   > "Here's what I'm building: **[product name]** — **[vision]**. Main users: **[personas]**. In v1: **[core flows]**. Deferring: **[later items]** because **[rationale]**. Assumptions: **[technical/design assumptions]**. I'll keep going — interrupt me if any of this is wrong."

2. Run the Stage Transition Protocol (read `skills/orchestrator/protocols/governance.md` § Stage Transition Protocol if not already loaded) to verify prerequisites are met.

3. Run the Framework Reflection Protocol (read `skills/orchestrator/protocols/governance.md` § FRP if not already loaded). Record reflection in `change_log`.

4. Update `current_stage` to "artifact-generation".

**If the user interrupts with corrections** before or during artifact generation:
- **Cosmetic changes** (wording, minor adjustments): update and proceed.
- **Functional changes** (new feature, different flow): update `project-state.yaml`, note in change log, re-evaluate if anything else is affected.
- **Directional changes** (fundamentally different product): flag this explicitly — "That's a significant shift. It might mean rethinking [X]. Want to explore that, or keep the current direction?"

**Transition to Stage 3** after presenting the definition and running the readiness check. Do not wait for explicit confirmation.
