# Test Scenario: Simple Family Utility

## Scenario Overview

- **Shape:** UI Application
- **Domain:** Utility
- **Risk Level:** Low
- **Phase:** 1 (vertical slice scenario)
- **Purpose:** Tests pacing sensitivity, scope restraint, and non-technical user handling. The system should NOT interrogate this the same way it interrogates a B2B platform.

## Input

> "I want to build an app for my family to keep track of scores when we play board games together"

The input is deliberately vague, non-technical, and low-stakes. It signals a non-technical user with a simple, personal need.

## Evaluation Rubric

### Domain Analyzer (C2)

**Must-do:**

- Classify shape as UI Application.
- Classify domain as Utility (Entertainment/Utility also acceptable).
- Assign low risk profile.
- Ask about core users (who in the family, how many, ages relevant?).
- Ask about the core action (what does "track scores" mean — per-game results, running leaderboards, both?).
- Ask about platform (phone at the table, web at home, both?).
- Surface data persistence as a consideration (do historical scores matter, or is it session-by-session?).
- Limit total discovery questions to 5-8 for this risk level.

**Must-not-do:**

- Must not ask about enterprise authentication, SSO, or complex authorization.
- Must not ask about regulatory or compliance requirements.
- Must not ask about API contracts, webhooks, or integrations.
- Must not ask about monitoring infrastructure or alerting.
- Must not recommend not building this.
- Must not generate more than 10 discovery questions total.
- Must not ask the user to self-assess their technical expertise.

**Quality criteria:**

- Questions are ordered by impact (most important first).
- Questions use plain language — "Where will you use this?" not "What's your target platform?"
- Inferences are made and confirmed rather than asked open-endedly: "Since this is for family game nights, I'm assuming you don't need enterprise security — just a simple way to identify who's playing. Sound right?"

### Orchestrator (C1)

**Must-do:**

- Progress through stages 0 → 0.5 → 1 → 2 without excessive back-and-forth.
- Infer non-technical user from input style and vocabulary.
- Adjust vocabulary accordingly (no unexplained jargon).
- Confirm classification in plain language.
- Make reasonable assumptions and state them explicitly.
- Recognize when discovery is "good enough" and transition to product definition.

**Must-not-do:**

- Must not conduct more than 2-3 rounds of discovery questions for this risk level.
- Must not use technical terminology without explanation.
- Must not ask the user to choose between technical alternatives they can't evaluate.
- Must not require the user to make decisions outside their expertise.

**Quality criteria:**

- Conversation feels proportionate to the product's simplicity.
- The user doesn't feel interrogated.
- Assumptions are stated clearly enough that the user can correct them.
- Stage transitions happen naturally, not abruptly.

### Artifact Generator (C3)

**Must-do:**

- Produce all 7 universal artifacts: product brief, data model, security model, test specifications, non-functional requirements, operational spec, dependency manifest.
- All artifacts have correct YAML frontmatter with dependency declarations.
- Data model includes at minimum: Player, Game, Score/Session entities.
- Security model is proportionate (simple player identification, not enterprise auth).
- Test specifications include concrete scenarios — not "test scoring" but "test recording scores for a 3-player game of Catan" or equivalent specificity.
- NFRs are proportionate (not demanding 99.99% uptime for a family app).
- Operational spec is simple (single deployment target, basic backup).
- Dependency manifest is minimal (no unnecessary third-party services).

**Must-not-do:**

- Must not generate UI-shape-specific artifacts (IA, screen specs, design direction, etc.) — those are Phase 2.
- Must not generate API, automation, or multi-party artifacts.
- Must not over-engineer the security model.
- Must not specify enterprise-grade operational requirements.

**Quality criteria:**

- Artifacts are internally consistent (entities in data model appear in test specs and security model).
- Cross-references between artifacts are accurate.
- A coding agent reading these artifacts could begin building without ambiguity.
- Complexity of artifacts is proportionate to the product.

### Review Lenses (C4)

**Must-do:**

- Product Lens: confirms this solves a real (if small) problem; scope is appropriate.
- Design Lens: raises first-run/empty state experience and basic accessibility.
- Architecture Lens: raises data persistence choice and deployment simplicity.
- Skeptic Lens: raises at least one realistic concern (e.g., data loss risk, offline use at game night, what happens when someone disputes a score).
- Each finding has a specific recommendation, not just an observation.
- Each finding has a severity level (blocking / warning / note).

**Must-not-do:**

- Must not raise enterprise-scale concerns for a family app.
- Must not produce vague findings ("consider the user experience").
- Must not block on concerns disproportionate to the risk level.

**Quality criteria:**

- Findings are specific and actionable.
- Severity ratings are proportionate to the product's risk level.
- Addressing the findings would measurably improve the artifacts.
- No lens produces more than 3-5 findings for a low-risk utility.

## End-to-End Success Criteria

The vertical slice succeeds for this scenario when:

1. Starting from the input above, the system produces a populated `project-state.yaml` with classification, product definition, and scope decisions.
2. All 7 universal artifacts are generated with correct frontmatter, internal consistency, and cross-references.
3. Review Lenses produce specific, actionable findings with appropriate severity.
4. The total output is proportionate to the product's simplicity — a reader should not think "this is way too much process for a family score tracker."
5. A coding agent (or human developer) reading the output would have a clear, unambiguous starting point for building this app.
