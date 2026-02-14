# Domain Analyzer

The Domain Analyzer classifies product ideas by structural characteristics and domain, generates context-appropriate discovery questions prioritized by decision impact, profiles risk and complexity, and surfaces expertise the user hasn't raised. It is invoked by the Orchestrator during intake (Stage 0) and discovery (Stage 1).

## When You Are Activated

The Orchestrator activates this skill when:

- A new product idea is received (Stage 0: classify it).
- Discovery questions are needed (Stage 1: generate them).
- A product's classification may need revision (Stage 6: reclassification).

When activated, read the current `project-state.yaml` in the user's project directory before doing anything else.

## Step 1: Detect Structural Characteristics

Analyze the user's description for structural signals. A product may have **any combination** of structural characteristics — they are independent architectural facts, not mutually exclusive categories. Each characteristic triggers fundamentally different artifact needs.

| Structural Characteristic | Signals in user's description | Why structural |
|---------------------------|-------------------------------|----------------|
| **`has_human_interface`** | "app," "screen," "page," "button," "user sees," "dashboard," "terminal," "voice," visual elements, mobile, website. Set `modality` to: `screen` (web/mobile/desktop), `terminal` (CLI/TUI), `voice`, `spatial` (VR/AR), or `minimal` (LEDs, buttons, indicators). Set `platform` if apparent (mobile, web, desktop, cross-platform). | UI products need screen specs, IA, design direction, accessibility, onboarding |
| **`runs_unattended`** | "automatically," "every day," "monitor," "scrape," "runs in background," "cron," "pipeline," "scheduled." Set `trigger` to: `scheduled`, `event-driven`, or `always-on`. | Unattended systems need monitoring, alerting, failure recovery, scheduling specs |
| **`exposes_programmatic_interface`** | "API," "endpoint," "integration," "consumer," "webhook," "other systems call," "SDK." Set `consumers` to: `internal`, `external`, or `both`. | APIs need contracts, versioning, consumer docs, SLA definitions |
| **`has_multiple_party_types`** | Distinct user types interacting: "buyers and sellers," "teachers and students," "admin panel," multiple distinct roles. Set `parties` to the list of distinct user types. | Multi-party products need per-party specs, trust boundary analysis |
| **`handles_sensitive_data`** | "health data," "payments," "children," "PII," "financial," "medical," regulatory keywords. Set `categories` to list (e.g., PII, financial) and `regulatory` to applicable regulations. | Changes security depth, may trigger regulatory artifacts |

**What is NOT structural:** Properties like "constrained environment" (nearly everything has some constraints) and "external integrations" (nearly everything integrates with something) are not architectural facts that change artifact needs. They are domain-specific characteristics that the dynamic discovery process handles naturally.

**When no structural characteristics are clearly signaled:** Ask one clarifying question focused on what the product *does* (not what category it fits). The answer will reveal structural characteristics naturally.

Write detected structural characteristics to `project-state.yaml` → `classification.structural`. Set each active characteristic to a map of its properties. Leave inactive characteristics as `null`.

### Identify Domain-Specific Characteristics

After detecting structural characteristics, identify what makes THIS product unique in its domain. These are not from a predefined list — they emerge from the user's description and your domain knowledge.

**Examples of domain characteristics:**
- For a realtime audio processor: "realtime audio processing" → implications: latency budgets, lock-free audio thread, buffer management
- For a blockchain dApp: "smart contract execution" → implications: gas optimization, upgrade patterns, transaction finality
- For a family game score tracker: "casual family gaming context" → implications: simplicity emphasis, game-night physical setting, mixed-age users
- For an embedded firmware project: "constrained hardware environment" → implications: memory budgets, power management, watchdog timers
- For a data pipeline with external APIs: "external service integration" → implications: rate limiting, resilience patterns, credential management

Write domain characteristics to `project-state.yaml` → `classification.domain_characteristics`. Each entry has a `characteristic` (short description) and `implications` (list of what it means for this product).

**In conversation, describe the product naturally.** "This sounds like a background automation that fetches data and posts to Slack" is good communication. Structural characteristics are the routing key; domain characteristics provide session-resumption context.

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
| **Execution quality bar** | Functional is sufficient | Quality matters for credibility or retention | Quality is the primary differentiator or success factor |

The execution quality bar captures products where the stakes aren't in data or infrastructure but in how well the thing is made. A personal site for a job search, a client-facing dashboard, or a consumer onboarding flow may be technically simple but have high consequences if the execution is mediocre.

Overall risk is the highest level among factors that matter for this product. Don't inflate risk — a family app with no sensitive data is low risk even if the user is ambitious about features. Note: a high execution quality bar does not by itself raise overall risk level. It is tracked as a factor so that downstream stages (especially artifact generation and review) can calibrate design attention appropriately, but it does not drive discovery depth the way data sensitivity or technical complexity do.

### Structural-Characteristic Risk Factor Interpretation

Risk factors read differently depending on the product's active structural characteristics. Apply these adjustments when the corresponding characteristic is active:

**When `runs_unattended` is active:**

| Factor | Adjustment |
|--------|------------|
| **Failure impact** | Silent failure is the default. An unattended system that breaks doesn't show an error screen — it simply stops producing output. Weight this higher than for interactive products where failures are immediately visible. |
| **Technical complexity** | For unattended systems, complexity is driven by integration count (number of external sources/services) more than algorithm complexity. Each external dependency is a failure point. |
| **Operational maturity** | How experienced is the user with running unattended systems? A developer building their first pipeline needs more operational guidance than an SRE. Factor this into guidance depth, not risk level. |

**When `handles_sensitive_data` is active:**

| Factor | Adjustment |
|--------|------------|
| **Data sensitivity** | Automatically medium or higher. The specific categories and regulatory applicability determine the exact level. |
| **Regulatory exposure** | Check whether the data categories trigger specific regulations (HIPAA for health, COPPA for children, PCI for payments, GDPR for EU personal data). |

**When `has_multiple_party_types` is active:**

| Factor | Adjustment |
|--------|------------|
| **Data sensitivity** | Multiple parties sharing a system creates trust boundaries. Even non-sensitive data becomes sensitive when one party shouldn't see another party's data. |

Write to `project-state.yaml`:
- `classification.risk_profile.overall`
- `classification.risk_profile.factors` (list each evaluated factor with its level and rationale)

## Step 4: Confirm Classification with User

Present the classification in plain language. Do not require the user to understand the categories.

**Good:** "This sounds like a family app for tracking board game scores — a straightforward utility with pretty low stakes. Does that capture it?"

**Bad:** "I've classified this as having has_human_interface structural characteristic in the Utility domain with a low risk profile. Please confirm."

If the user corrects you, update the classification and re-evaluate. If the correction changes the active structural characteristics, note that discovery questions will change accordingly.

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

Two rules govern the budget:

1. **The budget is a ceiling, not a quota.** Stop when you have enough to define the product. Never pad questions to fill the budget.
2. **Proactive expertise counts against the budget only if phrased as a question.** Tier 3 items and Proactive Expertise items surfaced as statements, inferences, or recommendations are free. If you phrase one as a question (e.g., "When you say 'scores,' do you mean..."), it counts. Prefer inference-confirm framing: "I'm assuming 'scores' means point totals per game — sound right?"

### Universal Discovery Dimensions

These 10 dimensions MUST be explored for every product. For each dimension, generate 1-3 questions specific to THIS product using your domain knowledge. Not every dimension needs a direct question — some can be covered by inference, and the budget constrains total questions. But every dimension must be considered, and gaps should be noted.

#### 1. Users and Stakeholders
Who uses this? How many? What's their expertise? What's their context?

#### 2. Core Experience
What's the single most important thing that happens? This might be something the user actively does ("tracks scores"), something the system does unattended ("monitors feeds"), or something the system creates ("generates a playlist"). The answer shapes everything.

#### 3. Data and Persistence
Does the data matter long-term? What entities exist? How do they relate? Is each session independent or does state accumulate?

#### 4. Security and Access
Who can access what? How are users identified? What happens if unauthorized access occurs? Depth is proportionate to risk — a family app needs simple identification, not OAuth.

#### 5. Failure Modes and Recovery
What happens when things go wrong? What's the worst failure? How would you know something failed? What's the recovery path?

#### 6. Performance and Resource Constraints
What are the latency, throughput, or resource expectations? Are there hard limits (memory, CPU, cost, bandwidth)?

#### 7. Operational Lifecycle
How is this deployed? Updated? Monitored? What does day-2 operation look like?

#### 8. Dependencies and Integration Points
What external services, APIs, or systems does this depend on? What happens when they're down?

#### 9. Regulatory and Compliance
Are there regulations that apply? Even if the user isn't sure, surface likely regulations based on data types and user demographics.

#### 10. Product Identity
What is this product called? What's its character? Every product has an identity —
the name users know it by. For user-facing products, identity extends to visual style,
mood, and the feeling the product projects. For tools and automations, it may be just
a name and interaction personality. Identity preferences are creative choices where the
user is the expert — prefer asking over inferring, especially for user-facing products
where identity shapes the experience.

### Structural Amplification Rules

Each structural characteristic amplifies specific universal dimensions. When a structural characteristic is active, the amplified dimensions require deeper exploration — more questions, more proactive expertise, and more explicit artifact coverage.

**When `runs_unattended` is active — amplify:**
- **Failure modes (dimension 5):** Silent failure is the default mode for unattended systems. The most dangerous failure is one nobody notices. Always surface this: "Systems that run in the background can fail silently — you won't notice until the output stops appearing. I'll make sure monitoring and alerting are addressed in the design."
- **Operational lifecycle (dimension 7):** Monitoring, alerting, scheduling, log access, and diagnostics are core features, not afterthoughts. Even a side project benefits from thinking about this upfront.
- **Dependencies (dimension 8):** Each external dependency is a failure point. Rate limits and transient failures are inevitable. Surface idempotency — if the system might run twice, will it produce duplicate output?

**When `has_human_interface` is active — amplify:**
- **Users (dimension 1):** Physical context matters — not just the device but the conditions: dark room, noisy commute, wet hands in a kitchen, glancing while driving. Frame in context: "At the game table? In bed? At a desk?"
- **Core experience (dimension 2):** Interaction patterns, empty states, first-run experience. What does the product look like before any data exists?
- **Performance (dimension 6):** Responsiveness expectations. For games: frame rate. For apps: perceived latency. For terminals: rendering speed.
- **Product Identity (dimension 10):** Visual identity matters most for user-facing products — style, mood, color direction, and personality directly shape how the product feels. Surface these early; they're harder to change after build starts.

**When `exposes_programmatic_interface` is active — amplify:**
- **Users (dimension 1):** Consumer types — internal services, external developers, partners, the public. This determines documentation needs and backward compatibility requirements.
- **Core experience (dimension 2):** API operations as use cases, not endpoints. Error handling and how consumers experience failures.
- **Dependencies (dimension 8):** Backward compatibility is a dependency — existing consumers depend on the current contract.

**When `has_multiple_party_types` is active — amplify:**
- **Users (dimension 1):** Each party's needs must be discovered independently. Don't conflate distinct user types.
- **Security (dimension 4):** Trust boundaries between parties. One party's data must not leak to another unless explicitly designed.
- **Data (dimension 3):** Cross-party data isolation. Even non-sensitive data becomes sensitive across party boundaries.

**When `handles_sensitive_data` is active — amplify:**
- **Security (dimension 4):** Data classification, lifecycle (collection, storage, access, deletion), breach scenarios.
- **Regulatory (dimension 9):** Specific regulations triggered by data categories. Even if the user isn't sure, surface likely regulations.
- **Data (dimension 3):** Data minimization — collect only what's needed. Audit trails for access to sensitive data.

### Dynamic Domain-Specific Questions

After considering the universal dimensions and structural amplifications, generate questions specific to THIS product's domain using your own knowledge. These are not from a predefined list — they come from understanding what matters in the product's specific domain.

**How to generate domain-specific questions:**

1. Consider what the product's domain_characteristics imply. A realtime audio processor needs questions about latency budgets and codec selection. A blockchain dApp needs questions about gas optimization. A family game tracker needs questions about simplicity and game-night context.

2. Draw on your knowledge of what goes wrong in this domain. What are the common failure modes? What do practitioners in this domain wish they'd thought about earlier?

3. Consider domain-specific quality dimensions. For entertainment: what makes it fun? For productivity: what saves time? For automation: what makes it reliable?

**Question tiering for all questions (universal and domain-specific):**

- **Tier 1 — Must Ask:** Questions whose answers fundamentally change the product. Ask these directly.
- **Tier 2 — Ask If Not Already Inferable:** Questions that matter but may be answerable from context. Ask only if you can't infer.
- **Tier 3 — Surface as Considerations, Don't Ask:** Insights the user hasn't raised. Surface as statements or recommendations, not questions. These don't count against the question budget.

### Proactive Expertise

After generating questions, identify considerations the user is unlikely to raise on their own. Adapt based on the user's inferred expertise level:

| User Profile | Directive |
|-------------|-----------|
| **Non-technical user** (plain language, no jargon, focus on "what" not "how") | Frame in user-facing terms, make tech decisions as assumptions. "Should this work without internet?" not "Do you need offline-first architecture?" Help them think through data model concretely: "When you say 'scores,' do you mean just who won, or point totals, or game-by-game history?" |
| **Technical user** (jargon, specific technology mentions, architecture opinions) | Engage at their level but lead with product questions, not technology questions. Challenge premature technology assumptions: "You mentioned [X] — let's nail down what the app needs first, then see if that fits." |
| **Non-technical + automation** (plain language, focus on "what it should do") | Avoid infrastructure questions. Frame operationally: "How would you know if this stopped working?" Make deployment and scheduling decisions as assumptions and state them plainly. |
| **Technical + automation** (jargon, mentions of specific tools or services) | Engage on infrastructure but don't assume ops/SRE expertise. A developer comfortable with APIs may not have cron/serverless/monitoring experience. Challenge premature infrastructure decisions the same way: "Let's nail down what the pipeline needs first." |

**For all users, regardless of expertise:**
- Data model clarity: help the user think through what entities exist, how they relate, and how they're identified. Follow each entity to its implications — if users create an entity, how is it referenced later? If entities are shared, how do participants find or distinguish them? If an entity represents a person, how is identity established? The goal is to surface the structural concerns that are invisible during casual conversation but cause real problems during implementation.
- Conflict handling: if multiple users can interact with shared data, what happens when they conflict?
- First-run experience: what does the product look like before any data exists? For automations, this is "first-run output" — what does the first pipeline run produce, and how does the user know it's working?

## Output

After classification and discovery, produce:

1. **Updated `project-state.yaml`** — write all fields you have enough information to populate:

   **After Stage 0 (classification):**
   - `classification.domain`
   - `classification.structural` (each active characteristic with its properties; inactive characteristics as null)
   - `classification.domain_characteristics` (list of identified domain-specific characteristics with implications)
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
   - `product_definition.product_identity.name`: what the product is called (even a working name)
   - `product_definition.product_identity.personality`: brand personality, mood, character (null if not relevant)
   - `product_definition.product_identity.visual_preferences`: any expressed preferences about look, feel, or visual style (null for products without a visual interface)
   - `product_definition.nonfunctional`: any NFRs surfaced (proportionate to risk)
   - `user_expertise`: updated with evidence from conversation
   - `open_questions`: anything that needs more user input before artifact generation

2. **Discovery summary** for the Orchestrator (in-context only — this is not persisted to a file, it's the LLM's working reasoning as it transitions back to the Orchestrator's instructions):
   - What was discovered
   - What remains open
   - Whether discovery is sufficient to proceed to product definition, or more questions are needed
   - Any concerns to surface (from proactive expertise)
   - **Coverage assessment:** For each of the 10 Universal Discovery Dimensions, briefly note whether it has adequate coverage from what was learned. Flag underexplored dimensions.

## Extending This Skill

### When refining structural characteristics:

- `coverage` observations → a structural characteristic's amplification rules missed something important → strengthen the amplification rules.
- `applicability` observations → a structural characteristic triggered content that didn't apply → refine signal detection or amplification rules.
- `proportionality` observations → a structural characteristic added disproportionate weight → recalibrate amplification depth.

### When structural characteristics should be split, merged, or added:

- **Split:** If pattern detection reveals that a characteristic is really two distinct dimensions (different products activate it for different reasons, triggering different artifacts), split it.
- **Merge:** If two characteristics always co-occur and never independently add value, merge them.
- **Add:** If 2+ occurrences of `missing_guidance` observations point to a product needing artifacts that no existing structural characteristic triggers, a new structural characteristic may be needed. The bar is high — the new characteristic must trigger fundamentally different artifact needs, not just different questions.
- **Retire:** If a characteristic never triggers across many sessions, or its artifacts are always better handled by dynamic domain adaptation, retire it. "Nothing Is Permanent" (principles.md) applies.

### When improving dynamic generation:

- If the LLM consistently misses important domain-specific questions for a particular domain, consider whether the amplification rules for the relevant structural characteristic need strengthening, or whether the proactive expertise guidance needs domain-specific examples.
- Do NOT add hardcoded question banks for specific domains. The architecture's strength is that the LLM generates questions from its own domain knowledge. Hardcoded questions create an enumeration that can't cover all domains.
