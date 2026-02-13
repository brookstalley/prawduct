# Test Scenario: Simple Family Utility

## Scenario Overview

- **Primary structural:** `has_human_interface` (modality: screen, platform: mobile)
- **Domain:** Utility
- **Risk Level:** Low
- **Phase:** 1 (vertical slice scenario)
- **Purpose:** Tests pacing sensitivity, scope restraint, and non-technical user handling. The system should NOT interrogate this the same way it interrogates a B2B platform.

## Evaluation Procedure

### Setup

1. Create an isolated project directory for the evaluation. This must be **outside the prawduct repo** to avoid polluting the framework tree:
   ```bash
   mkdir -p /tmp/eval-family-utility
   ```
2. Copy the project-state template into it:
   ```bash
   cp templates/project-state.yaml /tmp/eval-family-utility/project-state.yaml
   ```

### Running the evaluation

3. Start a new LLM conversation. Provide the prawduct framework context (CLAUDE.md, skills/, templates/, docs/) as reference material the LLM can read from, but set `/tmp/eval-family-utility` as the project directory where all output files go.
4. Send the Input prompt (below) as the user's opening message.
5. For each system question, respond using the scripted Test Conversation responses below. If the system asks about a topic not covered, respond in character as the test persona.
6. Let the system run through Stages 0 → 0.5 → 1 → 2 → 3.

### Evaluating results

7. After the run completes, evaluate against the Evaluation Rubric (below) by checking:
   - `/tmp/eval-family-utility/project-state.yaml` against the C5 criteria
   - `/tmp/eval-family-utility/artifacts/*.md` against the C3 criteria
   - The conversation transcript against C1, C2, and C4 criteria
8. Record pass/fail for each must-do, must-not-do, and quality criterion.

### Recording results

9. **Before cleanup**, write the evaluation results to `eval-history/family-utility-{YYYY-MM-DD}.md` in the prawduct repo. This file must include:
   - YAML frontmatter with scenario name, date, evaluator type, framework version (git SHA), and pass/partial/fail/unable counts per component.
   - Detailed pass/fail per rubric criterion with evidence.
   - Issues found and any skill updates made as a result.
   - Meta-observations about the evaluation process itself.

   **This step is mandatory.** Unrecorded evaluations are wasted work — the results are needed to detect regressions across framework changes.

   **For the complete recording format and evaluation procedures**, see `docs/evaluation-methodology.md`.

### Cleanup

10. Delete the evaluation directory when done:
    ```bash
    rm -rf /tmp/eval-family-utility
    ```

## Input

> "I want to build an app for my family to keep track of scores when we play board games together"

The input is deliberately vague, non-technical, and low-stakes. It signals a non-technical user with a simple, personal need.

## Test Conversation

To ensure repeatable evaluation, the following scripted responses define what the test user says when asked about each topic. The evaluator provides these responses regardless of how the system phrases its questions. If the system doesn't ask about a topic (e.g., because it infers the answer), the corresponding response is not volunteered.

**When asked to confirm classification or assumptions:**
> "Yeah, that sounds right."
>
> Accept reasonable inferences. Only correct if the system makes an obviously wrong assumption.

**When asked about users / who uses it:**
> "Mostly my family — me, my wife, and our two kids, ages 10 and 14. Sometimes we have friends over for game night too, maybe 2-3 extra people."

**When asked about the core action / what "track scores" means:**
> "I'd love to keep track of scores during a game and also see a history over time. Like, who's winning at Catan overall."

**When asked about platform / where they use it:**
> "On our phones, at the table while we're playing."

**When asked about data persistence / whether history matters:**
> "Yeah, I'd want to keep the history. That's half the fun."

**When asked about sharing / multi-user / how multiple people interact:**
> "It would be cool if everyone could enter their own scores on their own phone."

**When asked about current process / how they do it now:**
> "We just use pen and paper. It works fine but we lose the paper and there's no history."

**When asked about anything not covered above:**
> Give a brief, non-technical, cooperative answer consistent with the persona: an enthusiastic, non-technical parent who wants something simple for family game nights.

**General persona:** Enthusiastic but non-technical. Uses plain language. Doesn't volunteer technical requirements. Wants to get to building quickly. Does not push back on system recommendations.

## Test Conversation (Build Phase — Stages 4-6)

These scripted responses extend the test conversation for the build and iteration phases.

**When asked to confirm the build plan:**
> "Sounds good, let's build it."

**When shown progress during building (chunk completion messages):**
> [No response needed. Accept silently unless the system explicitly asks a question.]

**When asked about a Builder flag (artifact insufficiency or spec ambiguity):**
> "Whatever you think is best."
>
> Accept the system's recommendation. The test persona trusts the system's technical judgment.

**When presented with the working product and asked to try it:**
> "This is great! One thing though — can you add a way to time our games? It would be fun to see how long each game takes."

**When asked about additional changes after the timer iteration:**
> "Nope, that's perfect. Thanks!"

**General persona (continued):** Same as Stages 0-3 — enthusiastic, non-technical, cooperative. Doesn't push back on technical recommendations.

## Evaluation Rubric

### Domain Analyzer (C2)

**Must-do:**

- `[simulation]` Detect `has_human_interface` structural characteristic (modality: screen, platform: mobile).
- `[simulation]` Classify domain as Utility (Entertainment/Utility also acceptable).
- `[simulation]` Assign low risk profile.
- `[interactive]` Ask about core users (who in the family, how many, ages relevant?).
- `[interactive]` Ask about the core action (what does "track scores" mean — per-game results, running leaderboards, both?).
- `[interactive]` Ask about platform (phone at the table, web at home, both?).
- `[interactive]` Surface data persistence as a consideration (do historical scores matter, or is it session-by-session?).
- `[simulation]` Limit total discovery questions to 5-8 for this risk level.

**Must-not-do:**

- `[interactive]` Must not ask about enterprise authentication, SSO, or complex authorization.
- `[interactive]` Must not ask about regulatory or compliance requirements.
- `[interactive]` Must not ask about API contracts, webhooks, or integrations.
- `[interactive]` Must not ask about monitoring infrastructure or alerting.
- `[interactive]` Must not recommend not building this.
- `[simulation]` Must not generate more than 10 discovery questions total.
- `[interactive]` Must not ask the user to self-assess their technical expertise.

**Quality criteria:**

- `[interactive]` Questions are ordered by impact (most important first).
- `[interactive]` Questions use plain language — "Where will you use this?" not "What's your target platform?"
- `[interactive]` Inferences are made and confirmed rather than asked open-endedly: "Since this is for family game nights, I'm assuming you don't need enterprise security — just a simple way to identify who's playing. Sound right?"

### Orchestrator (C1)

**Must-do:**

- `[interactive]` Progress through stages 0 → 0.5 → 1 → 2 without excessive back-and-forth.
- `[interactive]` Infer non-technical user from input style and vocabulary.
- `[interactive]` Adjust vocabulary accordingly (no unexplained jargon).
- `[interactive]` Confirm classification in plain language.
- `[interactive]` Make reasonable assumptions and state them explicitly.
- `[interactive]` Recognize when discovery is "good enough" and transition to product definition.

**Must-not-do:**

- `[interactive]` Must not conduct more than 2-3 rounds of discovery questions for this risk level.
- `[interactive]` Must not use technical terminology without explanation.
- `[interactive]` Must not ask the user to choose between technical alternatives they can't evaluate.
- `[interactive]` Must not require the user to make decisions outside their expertise.

**Quality criteria:**

- `[interactive]` Conversation feels proportionate to the product's simplicity.
- `[interactive]` The user doesn't feel interrogated.
- `[interactive]` Assumptions are stated clearly enough that the user can correct them.
- `[interactive]` Stage transitions happen naturally, not abruptly.

### Artifact Generator (C3)

**Must-do:**

- `[simulation]` Produce all 7 universal artifacts: product brief, data model, security model, test specifications, non-functional requirements, operational spec, dependency manifest.
- `[simulation]` All artifacts have correct YAML frontmatter with dependency declarations.
- `[simulation]` Data model includes at minimum: Player, Game, Score/Session entities.
- `[simulation]` Security model is proportionate (simple player identification, not enterprise auth).
- `[simulation]` Test specifications include concrete scenarios — not "test scoring" but "test recording scores for a 3-player game of Catan" or equivalent specificity.
- `[simulation]` NFRs are proportionate (not demanding 99.99% uptime for a family app).
- `[simulation]` Operational spec is simple (single deployment target, basic backup).
- `[simulation]` Dependency manifest is minimal (no unnecessary third-party services).

**Must-not-do:**

- `[simulation]` Must not generate UI-shape-specific artifacts (IA, screen specs, design direction, etc.) — those are Phase 2.
- `[simulation]` Must not generate API, automation, or multi-party artifacts.
- `[simulation]` Must not over-engineer the security model.
- `[simulation]` Must not specify enterprise-grade operational requirements.

**Quality criteria:**

- `[simulation]` Artifacts are internally consistent (entities in data model appear in test specs and security model).
- `[simulation]` Cross-references between artifacts are accurate.
- `[simulation]` A coding agent reading these artifacts could begin building without ambiguity.
- `[simulation]` Complexity of artifacts is proportionate to the product.

### Review Lenses (C4)

**Must-do:**

- `[simulation]` Product Lens: confirms this solves a real (if small) problem; scope is appropriate.
- `[simulation]` Design Lens: raises first-run/empty state experience and basic accessibility.
- `[simulation]` Architecture Lens: raises data persistence choice and deployment simplicity.
- `[simulation]` Skeptic Lens: raises at least one realistic concern (e.g., data loss risk, offline use at game night, what happens when someone disputes a score).
- `[simulation]` Each finding has a specific recommendation, not just an observation.
- `[simulation]` Each finding has a severity level (blocking / warning / note).

**Must-not-do:**

- `[simulation]` Must not raise enterprise-scale concerns for a family app.
- `[simulation]` Must not produce vague findings ("consider the user experience").
- `[simulation]` Must not block on concerns disproportionate to the risk level.

**Quality criteria:**

- `[simulation]` Findings are specific and actionable.
- `[simulation]` Severity ratings are proportionate to the product's risk level.
- `[simulation]` Addressing the findings would measurably improve the artifacts.
- `[simulation]` No lens produces more than 3-5 findings for a low-risk utility.

### Project State (C5)

The rubric evaluates the resulting `project-state.yaml` after the full process (Stages 0-2).

**Must-do (structural):**

- `[simulation]` All populated fields use correct types per the template schema (strings for strings, lists for lists, etc.).
- `[simulation]` No fields added that don't exist in the template schema.
- `[simulation]` Risk factors include rationale, not just a level.

**Must-do (content after Stages 0-2):**

- `[simulation]` `classification.domain`: populated ("utility" or "entertainment/utility").
- `[simulation]` `classification.structural.has_human_interface`: not null, with modality "screen" and platform indicating mobile.
- `[simulation]` `classification.risk_profile.overall`: "low".
- `[simulation]` `classification.risk_profile.factors`: at least 2 evaluated factors with rationale.
- `[simulation]` `product_definition.vision`: a clear, specific one-sentence description (not generic).
- `[simulation]` `product_definition.users.personas`: at least one persona with name, description, and primary needs.
- `[simulation]` `product_definition.core_flows`: at least 2 flows (score recording, history viewing).
- `[simulation]` `product_definition.scope.v1`: at least 3 concrete items.
- `[simulation]` `product_definition.scope.later`: at least 1 item explicitly deferred.
- `[simulation]` `product_definition.platform`: populated (mobile).
- `[simulation]` `product_definition.nonfunctional`: at least performance and uptime populated, proportionate to risk level.
- `[simulation]` `technical_decisions`: at least one data storage decision and one deployment target decision, each with rationale.
- `[simulation]` `design_decisions.accessibility_approach`: populated (even if minimal, e.g., "standard platform accessibility").
- `[simulation]` `user_expertise`: at least `technical_depth` and `product_thinking` inferred with evidence.
- `[simulation]` `current_stage`: "definition" or later.
- `[simulation]` `change_log`: at least 1 entry (initial classification).

**Must-not-do:**

- `[simulation]` Must not leave `classification.structural` with no active structural characteristics after Stage 0.
- `[simulation]` Must not add regulatory constraints for this scenario.
- `[simulation]` Must not set `risk_profile.overall` above "low" for this scenario.

**Quality criteria:**

- `[simulation]` A reader of `project-state.yaml` alone — without seeing the conversation — can understand what's being built, for whom, and what's in v1 scope.
- `[simulation]` Values are specific, not generic ("family score-tracking app for board game nights" not "a utility application").
- `[simulation]` Scope decisions reflect the test conversation (score tracking and history in v1, fancier features deferred).

### Build Plan (Stage 4)

**Must-do:**

- `[simulation]` Generate a build plan with at least 4 chunks (scaffold + data layer + at least 2 feature chunks).
- `[simulation]` Every core flow from the Product Brief is mapped to at least one chunk.
- `[simulation]` Each chunk has acceptance criteria traceable to specific test specification scenarios.
- `[simulation]` Early feedback milestone identified by chunk 3 or earlier.
- `[simulation]` Scaffolding chunk specifies exact initialization commands (not "set up the project" — actual commands).
- `[simulation]` Dependency manifest packages are listed in the scaffold's install commands.
- `[simulation]` Build plan specifies concrete project structure (directory names, not just "organize by feature").
- `[simulation]` Governance checkpoints include at least one mid-build and one final review.

**Must-not-do:**

- `[simulation]` Must not produce more than 8 chunks for this simple product.
- `[simulation]` Must not require the user to make technology decisions at this stage (those were decided in Stage 2).
- `[simulation]` Must not include chunks for features not in v1 scope.

**Quality criteria:**

- `[simulation]` Chunk ordering makes sense: scaffold → data → features by user value → polish.
- `[simulation]` A Builder reading this plan could execute it without making decisions.
- `[simulation]` The plan is proportionate — not enterprise-grade build infrastructure for a family app.

### Builder (Stage 5)

**Must-do:**

- `[simulation]` Scaffold chunk works: `npm run dev` (or equivalent) starts the app, `npm test` (or equivalent) runs.
- `[simulation]` Code implements all core flows from the Product Brief: score recording, game history viewing, leaderboard.
- `[simulation]` Data entities in the code match the Data Model artifact: Player, Game, Score/Session entities (or equivalent).
- `[simulation]` Tests are written alongside each chunk, not all at the end.
- `[simulation]` All tests pass after every chunk (`npm test` exits 0).
- `[simulation]` App loads and is interactive in a browser when running locally.

**Must-not-do:**

- `[simulation]` Must not choose technologies not specified in the build plan or dependency manifest.
- `[simulation]` Must not add features not in the chunk deliverables.
- `[simulation]` Must not delete or weaken tests from previous chunks.
- `[simulation]` Must not skip writing tests for a feature chunk.

**Quality criteria:**

- `[simulation]` Code complexity is proportionate to the product's simplicity.
- `[simulation]` The app actually works: you can record scores, view history, see the leaderboard.
- `[simulation]` Test names are specific and descriptive (not "test1").

### Critic Product Governance (Stage 5)

**Must-do:**

- `[simulation]` Spec compliance check runs after each feature chunk (scaffold exempt from full compliance check).
- `[simulation]` Test count never decreases between chunks.
- `[simulation]` All core flows from the Product Brief have implementation evidence in `spec_compliance`.
- `[simulation]` Critic actively reviews each feature chunk with substantive evidence of review. For medium/high-risk products, at least one blocking or warning finding expected. For low-risk products, note-only findings are acceptable if the build is clean.
- `[simulation]` Critic review was invoked automatically as part of the process, not prompted by user request. The system must not ask "Want me to run the Critic?" — it runs it proactively.
- `[simulation]` Fix-by-fudging detection is active: if a test is weakened to pass, the Critic catches it.

**Must-not-do:**

- `[simulation]` Must not produce more than 5 findings per chunk for this low-risk product.
- `[simulation]` Must not block on concerns disproportionate to the product's risk level.
- `[simulation]` Must not approve a chunk where specified requirements are missing without flagging.

**Quality criteria:**

- `[simulation]` Findings are specific and actionable (not "code could be better").
- `[simulation]` The review cycle converges: blocking findings → fix → re-review → clear. Not infinite loops.
- `[hybrid]` Process feels proportionate — the Critic helps, not obstructs.

### Iteration (Stage 6)

**Must-do:**

- `[simulation]` Game timer request ("add a way to time our games") is classified as **functional** (not cosmetic, not directional).
- `[simulation]` Change impact assessment is performed: identifies which artifacts are affected (at minimum: data-model, test-specifications, build-plan).
- `[simulation]` Affected artifacts are updated before implementation (data model needs duration/timer field, test specs need timer scenarios).
- `[simulation]` New test(s) written for game timer behavior (start timer, stop timer, duration recorded with game session).
- `[simulation]` Existing tests still pass (no regressions from the change).
- `[simulation]` The timer feature works: user can time a game session and see the duration in game history.

**Must-not-do:**

- `[simulation]` Must not classify the timer request as cosmetic (it adds a new data field and new UI behavior).
- `[simulation]` Must not classify it as directional (it's a feature addition, not a product pivot).
- `[simulation]` Must not implement without updating the data model and test specification.
- `[simulation]` Must not break existing score recording, history, or leaderboard functionality.

**Quality criteria:**

- `[simulation]` The iteration cycle is efficient: one round of artifact update → build → review → done.
- `[hybrid]` The user doesn't feel like they're going through a heavyweight change process for a simple request.
- `[simulation]` The change is handled proportionately to its actual scope.

## End-to-End Success Criteria

The scenario succeeds when:

**Stages 0-3 (existing — no regression):**

1. Starting from the input above, the system produces a populated `project-state.yaml` with classification, product definition, and scope decisions.
2. All 7 universal artifacts are generated with correct frontmatter, internal consistency, and cross-references.
3. Review Lenses produce specific, actionable findings with appropriate severity.
4. The total output is proportionate to the product's simplicity — a reader should not think "this is way too much process for a family score tracker."
5. A coding agent (or human developer) reading the output would have a clear, unambiguous starting point for building this app.

**Stages 4-6 (new):**

6. Build plan translates artifacts into concrete, executable instructions with appropriate chunking.
7. App builds and runs locally — `npm run dev` (or equivalent) serves a working app.
8. Core flows work in the running app: record scores for a game, view game history, see the leaderboard.
9. All tests pass (`npm test` or equivalent exits 0).
10. The Critic actively reviewed each feature chunk with substantive findings (any severity acceptable for low-risk).
11. User feedback (game timer feature) handled in one iteration cycle without regressions.
12. At least one framework observation captured during the build phase (artifact insufficiency, spec ambiguity, or other build-phase observation type).
13. Process is proportionate to the product's simplicity — the build phase should not feel like building enterprise software.
14. The Builder never made a technology decision outside its scope — every choice traces back to artifacts or build plan.
