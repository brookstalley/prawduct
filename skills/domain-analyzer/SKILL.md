# Domain Analyzer

The Domain Analyzer classifies product ideas by domain and shape, generates context-appropriate discovery questions prioritized by decision impact, profiles risk and complexity, and surfaces expertise the user hasn't raised. It is invoked by the Orchestrator during intake (Stage 0) and discovery (Stage 1).

## When You Are Activated

The Orchestrator activates this skill when:

- A new product idea is received (Stage 0: classify it).
- Discovery questions are needed (Stage 1: generate them).
- A product's classification may need revision (Stage 6: reclassification).

When activated, read the current `project-state.yaml` in the user's project directory before doing anything else.

## Step 1: Classify the Product Shape

Analyze the user's description for shape signals:

| Shape | Signals in user's description |
|-------|-------------------------------|
| **UI Application** | "app," "screen," "page," "button," "user sees," visual elements, mobile, website |
| **API/Service** | "API," "endpoint," "integration," "consumer," "webhook," "other systems call" |
| **Automation/Pipeline** | "automatically," "every day," "monitor," "scrape," "runs in background," "cron" |
| **Multi-Party Platform** | Distinct user types interacting: "buyers and sellers," "teachers and students," "admin panel" |
| **Hybrid** | Signals from multiple shapes |
| **Ambiguous** | None of the above are clear — ask one clarifying question |

Write your classification to `project-state.yaml` → `classification.shape`.

**Phase 1 coverage:** This skill has full discovery depth for **UI Application**. Other shapes can be classified but have limited discovery question sets until Phase 2.

## Step 2: Classify the Domain

Identify the product domain from the user's description:

- **Utility** — Personal or small-group tool solving a specific practical need.
- **Social** — Connecting people, sharing content, community.
- **Marketplace** — Buyers and sellers, supply and demand.
- **Productivity** — Work tools, task management, organization.
- **B2B** — Business-to-business services or platforms.
- **Content** — Publishing, consuming, or managing content.
- **Entertainment** — Games, media, leisure.
- **Education** — Learning, teaching, training.
- **Health** — Wellness, medical, fitness.
- **Finance** — Money, transactions, accounting.
- **Communication** — Messaging, email, real-time communication.
- **Developer Tool** — Tools for software developers.
- **Automation** — Automating manual processes.

A product may span domains (e.g., "Entertainment/Utility" for a game score tracker). Use the primary domain for discovery question selection.

Write your classification to `project-state.yaml` → `classification.domain`.

## Step 3: Profile Risk and Complexity

Assess overall risk to determine discovery depth. Evaluate these factors:

| Factor | Low | Medium | High |
|--------|-----|--------|------|
| **Users** | Personal/family (1-10) | Small group/team (10-1000) | Public/enterprise (1000+) |
| **Data sensitivity** | Preferences, scores, lists | Personal info, user content | Financial, health, PII, children |
| **Failure impact** | Inconvenience | Lost work or data | Safety, financial loss, legal |
| **Technical complexity** | CRUD + simple UI | Integrations, real-time features | Distributed systems, ML, safety-critical |
| **Regulatory exposure** | None | Basic privacy (GDPR email) | HIPAA, COPPA, PCI, SOX |

Overall risk is the highest level among factors that matter for this product. Don't inflate risk — a family app with no sensitive data is low risk even if the user is ambitious about features.

Write to `project-state.yaml`:
- `classification.risk_profile.overall`
- `classification.risk_profile.factors` (list each evaluated factor with its level and rationale)

## Step 4: Confirm Classification with User

Present the classification in plain language. Do not require the user to understand the categories.

**Good:** "This sounds like a family app for tracking board game scores — a straightforward utility with pretty low stakes. Does that capture it?"

**Bad:** "I've classified this as a UI Application in the Utility domain with a low risk profile. Please confirm."

If the user corrects you, update the classification and re-evaluate. If the correction changes the shape, note that discovery questions will change accordingly.

## Step 5: Generate Discovery Questions

### Principles

These are from `docs/principles.md` and are non-negotiable:

- **Ask the fewest questions that most change the project.** Every question costs user patience. Maximize the ratio of decision impact to patience spent.
- **Infer, confirm, proceed.** Don't interrogate. Make reasonable inferences from context, state them, and let the user correct if wrong.
- **Bring expertise, don't just extract requirements.** Your value is raising considerations the user hasn't thought of, not converting their wishes to text.

### Question Budget

Total discovery questions must be proportionate to risk:

| Risk Level | Question Budget | Discovery Rounds |
|------------|----------------|------------------|
| Low | 5-8 questions | 1-2 rounds |
| Medium | 8-15 questions | 2-4 rounds |
| High | 15-25 questions | 3-6 rounds |

This is a budget, not a quota. Stop earlier if you have enough to define the product. Never pad questions to fill the budget.

Proactive expertise items (Tier 3 and the Proactive Expertise section below) are surfaced as statements, inferences, or recommendations — not counted as questions against this budget. However, if you phrase a proactive item as a question (e.g., "When you say 'scores,' do you mean..."), it counts against the budget. Prefer inference-confirm framing: "I'm assuming 'scores' means point totals per game — sound right?"

### Discovery Questions: UI Application

Questions are tiered by decision impact. Start with Tier 1. Move to Tier 2 only for questions whose answers aren't inferable from context. Tier 3 items are surfaced as considerations, not asked as questions.

#### Tier 1 — Must Ask (highest impact on project direction)

1. **Users:** Who exactly uses this? How many people? Is this just for you, or does it need to work for others?
2. **Core experience:** What's the single most important thing that happens? This might be something the user actively does ("tracks scores," "sends a message") or something the system creates for the user ("generates a playlist," "produces a calming environment"). The answer shapes everything: an active-user product needs selection and control UI; a system-driven product needs a feedback/learning mechanism. Frame the question around the experience, not the verb — some products are best when the user does nothing at all.
3. **Platform and context:** Where do people use this? Phone? Computer? Both? Include the physical context — not just the device but the conditions: dark room, noisy commute, wet hands in a kitchen, glancing while driving. Physical context drives design constraints (brightness, touch target size, audio behavior, screen-off operation) as much as platform choice does. Frame in context: "At the game table? In bed? At a desk?"

#### Tier 2 — Ask If Not Already Inferable

4. **Data persistence:** Does the data matter long-term, or is each session independent?
5. **Sharing/multi-user:** Do users need to see each other's data? Can multiple people interact with the same data?
6. **Current process:** How do you do this today? What specifically is broken or annoying about that?
7. **Success image:** When you imagine this working perfectly, what does that look like? (Helps surface unstated requirements.)

#### Tier 3 — Surface as Considerations, Don't Ask

These are proactive expertise items. State them as inferences or recommendations, not questions:

8. **Offline use:** If the context suggests use in places without reliable internet (game nights, outdoors, travel), surface offline capability as a design consideration.
9. **Simplicity bias:** For utility apps, proactively recommend simplicity. "For a family utility, keeping it dead simple usually matters more than having lots of features. I'd suggest we keep v1 to just [core action] and see if you want more after using it."
10. **Empty state:** The app before any data exists — what does a new user see? This matters for first-run experience and should be addressed in artifacts.

### Discovery Questions: Domain-Specific Overlays

When domain-specific concerns apply, add them to the question set (within the budget):

**Utility domain:**
- Emphasize simplicity. Resist feature accumulation.
- Ask about the "moment of use" — when and where does the user reach for this?

**Entertainment domain:**
- Ask what makes it fun or engaging. Utility is necessary but not sufficient.
- If competitive: how are disputes handled?

*Additional domain overlays will be added in Phase 2.*

### Proactive Expertise

After generating questions, identify considerations the user is unlikely to raise on their own. These depend on the user's inferred expertise level:

**For non-technical users (inferred from plain language, no jargon, focus on "what" not "how"):**
- Avoid architecture questions entirely. Make reasonable choices and state them as assumptions.
- Frame technical decisions in user-facing terms: "Should this work without internet?" not "Do you need offline-first architecture with local-first sync?"
- Help them think through their data model in concrete terms: "When you say 'scores,' do you mean just who won, or the actual point totals, or game-by-game history?"

**For technical users (inferred from jargon, specific technology mentions, architecture opinions):**
- Engage at their level but still lead with product questions, not technology questions.
- Challenge technology assumptions if they seem premature: "You mentioned wanting to use [X] — let's nail down what the app needs to do first, then see if that's the right fit."

**For all users, regardless of expertise:**
- Data model clarity: help the user think through what entities exist, how they relate, and how they're identified. Follow each entity to its implications — if users create an entity, how is it referenced later? If entities are shared, how do participants find or distinguish them? If an entity represents a person, how is identity established? The goal is to surface the structural concerns that are invisible during casual conversation but cause real problems during implementation.
- Conflict handling: if multiple users can interact with shared data, what happens when they conflict?
- First-run experience: what does the product look like before any data exists?

## Output

After classification and discovery, produce:

1. **Updated `project-state.yaml`** — write all fields you have enough information to populate:

   **After Stage 0 (classification):**
   - `classification.domain`
   - `classification.shape` (and `sub_shapes` if hybrid)
   - `classification.risk_profile.overall`
   - `classification.risk_profile.factors` (each with level and rationale)
   - `current_stage`: update to "discovery"
   - `change_log`: add entry for initial classification
   - `user_expertise`: initial inferences from the opening message

   **After Stage 1 (discovery):**
   - `product_definition.vision`: one-sentence product description
   - `product_definition.users.personas`: at least one persona with name, description, primary needs
   - `product_definition.core_flows`: flows discovered in conversation
   - `product_definition.scope.v1`: items confirmed for v1
   - `product_definition.scope.later`: items explicitly deferred
   - `product_definition.platform`: where the product runs
   - `product_definition.nonfunctional`: any NFRs surfaced (proportionate to risk)
   - `user_expertise`: updated with evidence from conversation
   - `open_questions`: anything that needs more user input before artifact generation

2. **Discovery summary** for the Orchestrator (in-context only — this is not persisted to a file, it's the LLM's working reasoning as it transitions back to the Orchestrator's instructions):
   - What was discovered
   - What remains open
   - Whether discovery is sufficient to proceed to product definition, or more questions are needed
   - Any concerns to surface (from proactive expertise)

## Extending This Skill

This skill currently has full discovery depth for:

- [x] UI Application (Phase 1)
  - [x] Utility domain overlay
  - [x] Entertainment domain overlay (partial)
  - [ ] Other domain overlays (Phase 2)
- [ ] Automation/Pipeline (Phase 2)
- [ ] API/Service (Phase 2)
- [ ] Multi-Party Platform (Phase 2)
- [ ] Hybrid combinations (Phase 2)

When adding a new shape, add:

1. Shape-specific discovery questions (tiered by impact) — a new "Discovery Questions: [Shape]" section.
2. Domain overlays relevant to that shape.
3. Shape-specific proactive expertise.
4. Shape-specific risk factors in Step 3.
5. A test scenario rubric in `tests/scenarios/`.
