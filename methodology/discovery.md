# Discovery: Understanding What to Build

The goal of discovery is to understand the problem space deeply enough to design a good solution. Not perfectly — deeply enough. The right depth depends on the stakes.

## The Core Question

Before you can build anything well, you need to understand what kind of thing you're building. Not in abstract terms — in structural terms that determine what artifacts you'll need and what risks you'll face.

**Six structural characteristics** shape every product. Detect these early from user language and context:

- **Has human interface** — Users see screens, hear audio, read output. Signals: "dashboard", "app", "users will see", "button". Implications: need interaction design, accessibility, onboarding, state handling (empty, loading, error).

- **Runs unattended** — Operates without humans watching. Signals: "automatically", "cron", "monitors", "runs in background". Implications: need failure recovery, monitoring, alerting, scheduling. Silent failure is the default — design against it.

- **Exposes programmatic interface** — Other systems call it. Signals: "API", "webhook", "endpoint", "integration". Implications: need API contracts, versioning, consumer documentation, error codes.

- **Has multiple party types** — Different user types with different privileges. Signals: "buyers and sellers", "admin panel", "teachers and students". Implications: need per-party specs, trust boundaries, data isolation.

- **Handles sensitive data** — Data that has regulatory, privacy, or safety implications. Signals: "health", "payments", "children", "PII". Implications: need data lifecycle design, breach scenarios, audit trails, regulatory awareness.

- **Multi-process or distributed** — Multiple processes or services that communicate at runtime. Signals: "message queue", "microservice", "worker", "broker", "IPC", multiple ports/processes described. Implications: need system architecture document covering process topology, communication channels (patterns, endpoints, protocols), concurrency model, and persistence boundaries (what's durable vs. ephemeral, what lives where).

These are independent dimensions, not categories. A product can have any combination. Each one you detect changes what you need to build and how deeply you need to think about it.

## Risk Calibration

After detecting structural characteristics, assess risk. Risk drives how much discovery you do:

**Low risk** (family utility, personal tool, 1-3 users): 5-8 questions, 1-2 rounds. Infer aggressively. Move fast.

**Medium risk** (team tool, small marketplace, modest user base): 8-15 questions, 2-3 rounds. Confirm key assumptions. Cover structural implications.

**High risk** (financial data, health records, large user base, regulatory): 15-25 questions, 3-5 rounds. Deep exploration. Surface regulatory concerns. Challenge assumptions explicitly.

The right amount of discovery is the minimum that prevents building the wrong thing. Over-discovery wastes the user's time and patience. Under-discovery leads to rework or missing entire categories of requirements.

## How to Discover

**Infer, confirm, proceed.** Don't interrogate. Use context to form hypotheses, state them, and let the user correct you. "Since this handles payment data, I'm assuming we need PCI-DSS awareness and encrypted storage. Sound right?" moves faster than "What security requirements do you have?"

**Bring expertise.** Your value is raising considerations the user hasn't thought of. A non-technical user needs you to think about architecture. A non-designer needs you to think about UX. Everyone needs you to think about edge cases, operations, and accessibility. This includes developer preferences — technical users have opinions on testing approach, code style, and tooling that shape how code is written.

**Ask the fewest questions that most change the project.** Every question has a cost (user patience, session time) and a value (decision impact). Questions that determine structural characteristics are high-value. Questions about icon colors are low-value. Front-load the high-value questions.

**Detect domain-specific concerns dynamically.** Don't rely on hardcoded lists of domain questions. Use your knowledge of the domain to surface what matters. A marketplace has different critical questions than a data pipeline. A healthcare app has different concerns than a game. Your domain knowledge is the source; the structural characteristics tell you where to focus it.

**Read the room on pacing.** Every question costs user patience, and patience is finite. Watch for fatigue signals: answers getting shorter, repeated agreement without elaboration ("yes", "sure", "sounds good"), or explicit redirects ("just build it", "whatever you think"). When you see these, adapt — compress remaining questions into a single confirm-or-correct batch, shift to pure confirmation mode, or infer more aggressively and move on. Sometimes moving to the next phase is the right call even if discovery feels incomplete. Under-discovery that preserves engagement beats thorough discovery that loses the user entirely. This isn't a state machine with defined thresholds — it's a judgment call about reading the conversation, and erring toward action is usually correct.

## Surface Prior Art

After you understand the concept and structural characteristics — typically after the first exchange — search for what already exists in this space. This isn't a gate or a report; it's expertise you bring to the conversation (Principle #6).

**What to search for.** Always look for existing solutions that solve the same core problem. For medium-risk and above, also search for key libraries, established patterns, and relevant standards. If web search is available, use it — it surfaces current, specific results that training data may miss. If it's not available, draw on your domain knowledge and say so.

**Scale search depth to risk.** Low-risk: 1-2 quick searches. Medium-risk: 2-3 searches covering solutions and relevant libraries. High-risk: 3-5 searches including solutions, libraries, standards, and cautionary tales.

**Present findings as expertise, not a report.** Weave what you find into the conversation naturally: "I checked what exists in this space — [X] and [Y] are the main options. Given your needs, I'd suggest we focus on [Z] because..." Use infer-confirm-proceed. Don't dump a list of links; synthesize what matters for *this* user's decision.

**Capture what you found.** Record relevant prior art in `project-state.yaml` under `classification.prior_art`. Each entry includes: name, url (if available), relevance to this project, and relationship (alternative, complement, or reference). This informs scope decisions downstream — it's not a gate.

## Surface Operational Costs

When structural characteristics indicate ongoing costs — `runs_unattended`, uses external APIs, deploys to cloud infrastructure — surface them during discovery, not after deployment (Principle 8).

**Use infer-confirm-proceed.** "Since this calls the OpenAI API, it'll have per-request costs — probably a few dollars/month at the usage you're describing. Want me to estimate more precisely, or is 'low single digits' enough to proceed?" Don't interrogate about budgets; make a reasonable inference and let the user correct.

**Scale to risk.** Low-risk (personal tool, free tier likely): acknowledge briefly — "This should stay within free tiers." Medium-risk (team tool, moderate API usage): provide a ballpark — "Expect $10-50/month for hosting plus API costs." High-risk (production service, significant compute): itemize cost components and capture constraints.

**Capture to `project-state.yaml`** under `product_definition.nonfunctional.cost_constraints` (user's budget limits) and `product_definition.cost_estimates` (your estimates of ongoing costs). These fields already exist in the template.

## Surface Accessibility Needs

When `has_human_interface` is detected, accessibility is a structural concern — not an afterthought (Principle 7).

**Use infer-confirm-proceed.** "Since this has a user interface, I'll design with standard accessibility for the platform — sufficient contrast, keyboard or alternative navigation, and meaningful labels. Any specific accessibility needs I should know about?" This establishes the baseline without interrogating.

**Scale to risk.** Low-risk (personal or family use): platform accessibility defaults are sufficient. Medium-risk (team or small audience): target WCAG 2.1 AA as the baseline. High-risk (public-facing, accessibility-critical, or regulatory): specify WCAG target explicitly and build deep accessibility into the spec.

**Capture to `project-state.yaml`** under `design_decisions.accessibility_approach`. This field already exists in the template.

## Surface Error Handling Approach

Every product needs error handling; the question is how much design it needs upfront. Most products can rely on standard patterns — catch at boundaries, log with context, surface a clear message to the user or caller. High-risk products need deliberate error architecture.

**Use infer-confirm-proceed.** "I'll handle errors with standard patterns — catch at boundaries, log with context, surface a clear message. Anything unusual about error handling for this project?" This establishes the baseline. Most users will confirm and move on.

**Scale to risk.** Low-risk (personal tool, single user): standard patterns are sufficient — no dedicated design needed. The build methodology's test discipline already requires error case coverage, and that's enough. Medium-risk (team tool, external consumers): surface the error taxonomy — what's recoverable vs. fatal, what the user or caller sees on error. Capture the approach. High-risk (financial, health, multi-party): design the full error handling strategy — taxonomy, recovery patterns, error UX or error response contracts, reporting and alerting. This becomes a first-class section in the product brief.

**Capture to `project-state.yaml`** under `design_decisions.error_handling_approach`. This connects discovery decisions to the build phase, where test discipline (building.md) and the Critic validate that error cases are actually covered.

## Surface Infrastructure Dependencies

When the product needs external services to function — databases, message queues, auth providers, cloud storage, third-party APIs — surface these during discovery so they become testable requirements. The critical question: what must be real vs. what can be mocked during development?

**Use infer-confirm-proceed.** "Since this stores user data, I'm assuming Postgres for persistence. I'll write integration tests that verify data actually persists — not just mocked database calls. Sound right?" This establishes that real infrastructure testing is expected, not optional.

**Scale to risk.** Low-risk (personal tool, SQLite, local-only): lightweight — note the dependency, ensure at least one integration test touches real storage. Medium-risk (team tool, managed database, external APIs): explicit infrastructure list with integration test requirements for each. Declare what's mocked in tests vs. what's real. High-risk (production service, multiple external dependencies): full infrastructure dependency map with integration testing strategy, environment requirements, and mock boundary documentation.

**Key decisions to surface:**
- What external services does this product depend on? (database, cache, queue, auth, APIs)
- Which dependencies must be tested against real instances vs. mocked?
- What's the development environment strategy? (local Docker, test instance, embedded alternative)
- What happens if a dependency is unavailable? (graceful degradation vs. hard failure)

**Capture to `project-state.yaml`** under `design_decisions.infrastructure_dependencies`. This connects to the build phase where test specifications require integration tests against declared dependencies, and the Critic verifies that infrastructure assumptions in code match what's specified.

## Surface Observability Needs

Every product has observability needs — even when the answer is "console.error is enough." The depth depends on structural characteristics: products with `runs_unattended`, `exposes_programmatic_interface`, or `multi_process_distributed` need deeper observability design. Single-user local tools need minimal (error logging is sufficient).

**Use infer-confirm-proceed.** "I'll plan for error logging with enough context to debug problems. For [this type of product], that means [structured logging / console output / three-signal observability]. Any specific monitoring needs?" This establishes the baseline without interrogating.

**Scale to risk.** Low-risk (personal tool, single user): error logging to console — no structured logging, no metrics, no tracing. Medium-risk (team tool, service with dependencies): structured logging with correlation context, key operational metrics, health endpoint. High-risk (production service, multi-party, regulatory): three-signal observability (logs, metrics, traces), correlation context, sensitive data filtering, alerting.

**Key decisions to surface:**
- What signals does this product need? (logs only → logs + metrics → full three-signal)
- What ties related events together? (request ID, session ID, domain-specific IDs)
- Does sensitive data need filtering from observability output?
- What's the operational model? (developer debugging vs. SRE monitoring vs. automated response)
- Will the development agent need to query observability signals during debugging? (If yes, plan agent-accessible interfaces early.)

**Capture to `project-state.yaml`** under `design_decisions.observability_approach`.

## Identify Boundary Patterns

As structural characteristics emerge, note where components will interact — API endpoints, database schemas, IPC channels, frontend/backend type contracts. These become the project's contract surfaces, documented in `.prawduct/artifacts/boundary-patterns.md` during planning. Identifying them during discovery helps scope the build: boundary-heavy designs need more integration testing and consumer-impact investigation during building.

For products with `exposes_programmatic_interface`, `has_multiple_party_types`, or `multi_process_distributed`, boundary patterns are a significant architectural concern. Surface them: "This has an API consumed by a frontend and by third parties — those are two contract surfaces we'll need to maintain carefully."

## What Discovery Produces

Discovery produces a `project-state.yaml` with:
- **Classification**: structural characteristics, domain, risk level, prior art
- **Product definition**: vision, personas, core flows, scope (v1 / accommodate / later / out of scope)
- **Cost awareness**: operational cost estimates and constraints (when applicable)
- **Accessibility approach**: accessibility baseline scaled to risk (for human interfaces)
- **Error handling approach**: error handling strategy scaled to risk
- **Infrastructure dependencies**: external services, mock boundaries, integration test requirements — scaled to risk
- **Observability approach**: signal types, correlation context, operational model — scaled to risk
- **User expertise profile**: what the user knows and doesn't, inferred from conversation
- **Product identity**: name, personality, technology preferences

Discovery isn't a phase — it's continuous. Initial discovery produces enough understanding to start planning and building. But discovery continues throughout the project: new features need their own discovery, bug reports reveal missing understanding, and user feedback surfaces unasked questions. The depth of discovery scales with the work's size and risk, not with where you are in a timeline.

## Common Traps

**Over-discovery**: Asking so many questions the user loses patience. Scale to risk. A personal utility doesn't need 25 questions about failure modes.

**Under-discovery**: Missing a structural characteristic. If you don't detect "handles sensitive data" for a health app, you'll miss entire requirement categories. Better to detect and confirm than to miss.

**Interrogation mode**: Asking questions one at a time in a rigid sequence. Batch related questions. Make inferences. Have a conversation, not an interview.

**Ignoring developer preferences**: Asking what to build but not how to build it. Technical users have strong opinions about testing, tooling, code style, and architecture patterns. Ask early and capture them in `project-preferences.md` (see `templates/project-preferences.md`). This file is read before writing any code — it ensures every session follows the same conventions.

**Domain blindness**: Not leveraging your own knowledge of the domain. If someone's building a marketplace, you know marketplaces need trust systems, dispute resolution, and payment escrow. Surface that knowledge; don't wait for the user to think of it.

**Overweighting prior art**: Spending too much time researching existing solutions instead of understanding the user's specific needs. Prior art informs the conversation; it doesn't drive it. A few focused searches are enough.

**Using prior art to gatekeep**: "This already exists, so why build it?" is never the right response. People build things for many valid reasons — learning, customization, ownership, fun. Respect the user's choice to build. Surface what exists, then help them build something great.

**Cost blindness**: Not surfacing operational costs for products with external dependencies, cloud deployments, or API usage. The user finds out about costs after deployment instead of during design. If the product runs unattended or calls external services, mention costs during discovery.

**Accessibility afterthought**: Detecting `has_human_interface` but not establishing an accessibility baseline. Accessibility bolted on later is expensive and incomplete. When you detect a human interface, state your accessibility assumptions and let the user adjust.

**Infrastructure blindness**: Not surfacing external infrastructure dependencies (databases, queues, APIs) as testable requirements. The builder mocks everything during development, tests pass, and the product is declared complete — but nothing actually persists, queues are never tested, API calls are simulated. When structural characteristics suggest external dependencies, establish what must be tested against real infrastructure vs. mocked.

**Observability afterthought**: Detecting structural characteristics that imply monitoring needs (unattended operation, programmatic interfaces, distributed systems) but not establishing an observability baseline. Like accessibility, observability is cheaper to design in than to retrofit. When structural characteristics suggest non-trivial observability needs, state your default approach and let the user adjust.
