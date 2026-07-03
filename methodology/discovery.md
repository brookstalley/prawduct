# Discovery: Understanding What to Build

The goal of discovery is to understand the problem space deeply enough to design a good solution. Not perfectly — deeply enough. The right depth depends on the stakes.

## The Core Question

Before you can build anything well, you need to understand what kind of thing you're building — in structural terms that determine what artifacts you'll need and what risks you'll face.

**Six structural characteristics** shape every product. Detect these early from user language and context:

- **Has human interface** — Users see screens, hear audio, read output. Signals: "dashboard", "app", "users will see", "button". Implications: interaction design, accessibility, onboarding, state handling (empty, loading, error).

- **Runs unattended** — Operates without humans watching. Signals: "automatically", "cron", "monitors", "runs in background". Implications: failure recovery, monitoring, alerting, scheduling. Silent failure is the default — design against it.

- **Exposes programmatic interface** — Other systems call it: a network service, a library/SDK, an on-device/platform interface, or a CLI — not just HTTP. Signals: "API", "SDK", "webhook", "endpoint", "plugin", "CLI", "integration". Implications: an API contract (operations, inputs/outputs, error model) plus three *recorded* decisions — versioning scheme, deprecation/compatibility policy, and error model — since adding any later is a breaking change for every consumer. Record the decision (a deliberate "none — internal-only" counts) in `design_decisions.api_versioning_approach`; a deferral must be dated with a revisit trigger. If the surface carries authorization or sensitive data, also surface the OWASP API Top 10 *design* failures — object-level authz (BOLA), mass assignment, excessive data exposure (checklist: `templates/api-contract.md`).

- **Has multiple party types** — Different user types with different privileges. Signals: "buyers and sellers", "admin panel", "teachers and students". Implications: per-party specs, trust boundaries, data isolation.

- **Handles sensitive data** — Regulatory, privacy, or safety implications. Signals: "health", "payments", "children", "PII". Implications: data lifecycle design, breach scenarios, audit trails, regulatory awareness.

- **Multi-process or distributed** — Multiple processes or services communicating at runtime. Signals: "message queue", "microservice", "worker", "broker", "IPC". Implications: system architecture covering process topology, communication channels, concurrency model, and persistence boundaries (what's durable vs. ephemeral, what lives where).

These are independent dimensions, not categories — a product can have any combination, and each one you detect changes what you need to build.

## Risk Calibration

After detecting structural characteristics, assess risk. Risk drives how much discovery you do. The counts below are the **typical shape, not a quota** — concrete anchors, always governed by the pacing judgment in "Read the room on pacing" below:

**Low risk** (family utility, personal tool, 1-3 users): 5-8 questions, 1-2 rounds. Infer aggressively. Move fast.

**Medium risk** (team tool, small marketplace, modest user base): 8-15 questions, 2-3 rounds. Confirm key assumptions. Cover structural implications.

**High risk** (financial data, health records, large user base, regulatory): 15-25 questions, 3-5 rounds. Deep exploration. Surface regulatory concerns. Challenge assumptions explicitly.

The right amount of discovery is the minimum that prevents building the wrong thing. Over-discovery wastes the user's patience; under-discovery leads to rework or missing entire requirement categories.

## Discovery Recurs

Discovery isn't a phase — it's a mode you enter every time the project takes on non-trivial new work: a feature, a refactor that changes user-visible behavior, a new integration. Each recurrence follows the same pattern (infer, confirm, proceed) at smaller scale.

One common entry point is **a backlog item at an early `stage:`** (`idea`/`research`/`requirements`). When `/prawduct:backlog pick` surfaces one, the next work is discovery, *not* implementation — a vague item is an undocumented requirement (Principle 6), and writing/researching it is the task. When discovery resolves it, advance the item with `/prawduct:backlog update <id> stage=design|ready` and add a `refs:` link to the doc you produced.

**Initial discovery** establishes the product's foundation — structural characteristics, personas, scope, success criteria — captured in `project-state.yaml`.

**Feature-level discovery** is shorter. For each non-trivial new feature, answer three questions in one sentence each:

1. What problem does this solve? (Observable, not abstract.)
2. What does success look like? (Specific, verifiable.)
3. What's out of scope for this iteration?

If you can answer all three, capture them in the build plan's Requirements Confidence field and proceed. If you can't answer one in a sentence, one round of clarification will probably get you there — the cheapest close is often a 60-second sketch ("here's what I think you want — confirm?"), not a full discovery session. The build cycle's `Before You Build: Confidence Check` (`methodology/building.md`) is the same pattern at the next stage (Principles 6 and 20).

## Reconciling an Existing or Docs-First Product

A product may arrive with material already in hand — an existing codebase, or requirements/architecture/vision docs written outside a discovery session. Onboarding leaves `project-state.yaml` template-default and nothing backfills it automatically — rich product thinking in `docs/`, empty source of truth, so the Critic can't calibrate rigor and the build gates won't engage. When the session briefing's **DISCOVERY NOT CAPTURED** nudge fires (template-default state + product-definition work in the repo), discovery's job is to **reconcile**, not re-interview:

1. **Read what exists first.** Requirements docs, architecture, a VISION, codebase conventions. Treat these as the user's already-stated answers — don't ask what the docs already say.
2. **Backfill the source of truth.** Populate `classification` and `product_definition` from the material; detect the six structural characteristics from the docs exactly as you would from conversation.
3. **Reference, don't duplicate.** Where `docs/` holds the detail, keep it canonical and have `project-state.yaml` point at it — set `open_questions` to the real open questions rather than copying prose into YAML (a drift-prone second copy).
4. **Confirm the inferred frame, then fill the gaps.** Surface the inferred classification and scope for a quick veto (the `[ASSUMPTION: …]` form below); run normal discovery only for what the material genuinely leaves open.

The destination is the same `project-state.yaml` as "What Discovery Produces" — reached by reading rather than only asking.

## Calibrate Rigor to Stakes, Knowledge, and Volatility

Risk Calibration sets discovery *depth* for a new product. Within any work — product, feature, or refactor — calibrate *how hard you pin down requirements and how much you research* with three questions. Size is a proxy; these are the real drivers, and they apply even to small work.

1. **What are the stakes of getting this wrong?** Consequence and blast radius. High stakes → pin requirements down harder, document the design before building, review more. A one-line change to a payment path outranks a large change to a throwaway script.
2. **Can I design a *great* solution from intrinsic knowledge?** Not adequate — great. If not, the gap is *knowledge*: decompose, plan harder, or research established patterns before committing.
3. **Does correctness depend on timely, post-training-cutoff, or fast-moving data?** If yes, the gap is *volatility*: verify against current evidence — your training is stale by construction.

Questions 2 and 3 are different gaps with different remedies: a knowledge gap wants more reasoning or decomposition; a volatility gap wants research. (A design can be high on both.)

**Re-run this when the domain expands — not just at kickoff.** A mid-work scope expansion resets your knowledge-confidence for the *new* surface. Treat it as its own work and re-ask the three questions — the most common way unresearched complexity enters is a mid-build expansion inheriting the original scope's (misplaced) confidence.

**Research when the inputs OR the design depend on timely data:**

- **Timely facts you will assert or act on** — current versions, prices, availability, recent results. Verify before relying on them, almost regardless of cost: asserting stale data as current is a correctness failure.
- **Design decisions in fast-moving domains** — a rapidly-evolving language (e.g. Zig), a fast-moving product (e.g. Claude Code itself), current best practices in an emerging field. Research scaled to stakes × implementation cost; prefer established solutions over first-principles reasoning (Principle 7).

Self-check: *"Does this depend on the current state of the world, or a field that moves faster than my training cycle?"* If yes, research before relying on intrinsic knowledge, and say what you checked. If you can't verify, proceed only with the uncertainty labeled — never assert stale knowledge as current (Principle 5).

**Make your inferences explicit (intentional inference).** Answer what you can yourself, and record each answer you *inferred* (rather than confirmed or verified) as a vetoable assumption —

`[ASSUMPTION: <what you assumed> | HIGH/MED/LOW impact | user can correct / override / defer]`

— so an inference is visible and correctable instead of buried. Surface a question to the user only when its answer is both **consequential** and **genuinely unverifiable** by you, and surface it **early** — before you've invested in implementation. The bar that earns a question is impact, not uncertainty alone.

## How to Discover

**Infer, confirm, proceed.** Don't interrogate. Form hypotheses from context, state them, and let the user correct you: "Since this handles payment data, I'm assuming PCI-DSS awareness and encrypted storage. Sound right?" moves faster than "What security requirements do you have?"

**Bring expertise.** Your value is raising considerations the user hasn't thought of — architecture for non-technical users, UX for non-designers, edge cases, operations, and accessibility for everyone. This includes developer preferences: technical users have opinions on testing, code style, and tooling that shape how code is written.

**Ask the fewest questions that most change the project.** Every question has a cost (patience, time) and a value (decision impact). Questions that determine structural characteristics are high-value; icon colors are not. Front-load the high-value questions.

**Detect domain-specific concerns dynamically.** Don't rely on hardcoded question lists — your domain knowledge is the source; structural characteristics tell you where to focus it. A marketplace, a data pipeline, a healthcare app each have different critical questions. Some domains imply testing strategies — mathematical operations and data transforms suit property-based testing, event-driven systems suit state-machine testing, APIs suit contract testing. Surface these during discovery so they reach test-specifications.

**Read the room on pacing.** Patience is finite. Fatigue signals — shortening answers, repeated bare agreement ("yes", "sure"), explicit redirects ("just build it") — mean adapt: batch remaining questions into one confirm-or-correct pass, shift to confirmation mode, or infer more aggressively and move on. Under-discovery that preserves engagement beats thorough discovery that loses the user. This isn't a state machine with thresholds — it's a judgment call, and erring toward action is usually correct.

## Surface Prior Art

After you understand the concept and structural characteristics — typically after the first exchange — search for what already exists. This isn't a gate or a report; it's expertise you bring to the conversation (Principle 7).

**What to search for.** Existing solutions to the same core problem; for medium-risk and above, also key libraries, established patterns, and standards. Use web search if available; otherwise draw on domain knowledge and say so. Per "Calibrate Rigor", a fast-moving or post-cutoff topic makes this search *mandatory*.

**Scale search depth to risk.** Low: 1-2 quick searches. Medium: 2-3 covering solutions and libraries. High: 3-5 including standards and cautionary tales.

**Present findings as expertise, not a report.** Weave them into the conversation ("I checked what exists — [X] and [Y] are the main options; given your needs I'd suggest [Z] because…"). Don't dump links; synthesize what matters for *this* decision.

**Capture** relevant prior art in `project-state.yaml` under `classification.prior_art`: name, url, relevance, relationship (alternative, complement, reference).

## Surface Operational Costs

When structural characteristics indicate ongoing costs — `runs_unattended`, external APIs, cloud deployment — surface them during discovery, not after deployment (Principle 9). Infer-confirm-proceed ("Since this calls the OpenAI API, expect a few dollars/month at your usage — precise estimate, or is that enough?"), scaled to risk: low → "should stay within free tiers"; medium → a ballpark ("$10-50/month hosting plus API"); high → itemize cost components and capture constraints.

**Capture to `project-state.yaml`** under `product_definition.nonfunctional.cost_constraints` (user's limits) and `product_definition.cost_estimates` (your estimates).

## Surface Accessibility Needs

When `has_human_interface` is detected, accessibility is a structural concern, not an afterthought (Principle 8). State the baseline for a quick veto ("I'll design with standard platform accessibility — contrast, keyboard or alternative navigation, meaningful labels. Any specific needs?"), scaled to risk: low → platform defaults; medium → WCAG 2.1 AA baseline; high → explicit WCAG target, deep accessibility in the spec.

**Capture to `project-state.yaml`** under `design_decisions.accessibility_approach`.

## Surface Error Handling Approach

Every product needs error handling; the question is how much upfront design. State the default ("catch at boundaries, log with context, surface a clear message — anything unusual here?"), scaled to risk: low → standard patterns suffice (build-side test discipline already requires error-case coverage); medium → surface the error taxonomy (recoverable vs. fatal, what the user/caller sees) and capture the approach; high → design the full strategy — taxonomy, recovery patterns, error UX or response contracts, reporting and alerting — as a first-class product-brief section.

**Capture to `project-state.yaml`** under `design_decisions.error_handling_approach`. Test discipline and the Critic validate error cases are actually covered.

## Surface Infrastructure Dependencies

When the product needs external services — databases, queues, auth providers, storage, third-party APIs — surface them as testable requirements. The critical question: **what must be real vs. what can be mocked during development?** Establish expectations by inference ("Since this stores user data, I'm assuming Postgres, with integration tests that verify data actually persists — not just mocked calls. Sound right?"), scaled to risk: low → note the dependency, at least one integration test touches real storage; medium → explicit infrastructure list with per-dependency integration-test requirements and declared mock boundaries; high → full dependency map with integration strategy, environment requirements, and mock-boundary documentation.

**Key decisions to surface:** which external services; which are tested real vs. mocked; the development environment strategy (local Docker, test instance, embedded alternative); behavior when a dependency is unavailable (graceful degradation vs. hard failure).

**Capture to `project-state.yaml`** under `design_decisions.infrastructure_dependencies` — test specifications then require integration tests against declared dependencies, and the Critic verifies code matches what's specified.

**Foreign APIs are a distinct subcategory.** When a dependency's surface the project doesn't own (vendor APIs, MCP servers, wrapped third-party libraries), name it explicitly so the planner carries it forward as `**Foreign API:** <name>` on the chunk that first wraps it — that annotation triggers the Critic's `verify-api` check (see `methodology/planning.md` "Foreign API Verification").

## Surface Observability Needs

Every product has observability needs — even when the answer is "console.error is enough." Products with `runs_unattended`, `exposes_programmatic_interface`, or `multi_process_distributed` need deeper design. State the baseline by inference, scaled to risk: low → error logging to console; medium → structured logging with correlation context, key metrics, health endpoint; high → three-signal observability (logs, metrics, traces), correlation context, sensitive-data filtering, alerting.

**Key decisions to surface:** which signals (logs only → logs + metrics → three-signal); what ties related events together (request/session/domain IDs); whether sensitive data needs filtering from output; the operational model (developer debugging vs. SRE monitoring vs. automated response); whether the development agent will need to query signals during debugging (if so, plan agent-accessible interfaces early).

**Capture to `project-state.yaml`** under `design_decisions.observability_approach`.

## Surface Behavioral Choices

When a feature affects user workflow, ask what behavioral variations exist — users differ on automation, notification, and control. Ship a safe default but make the choice configurable ("This can run automatically or wait for your go-ahead; I'll default to [safe default] — changeable in `project-preferences.md`").

**Common choices:** automatic vs. manual triggers (e.g., PRs); notification level; merge/deploy strategy; backwards compatibility. **The backwards-compatibility question is especially important:** before adding any migration path, fallback, or shim, ask whether an existing deployment actually needs migration. If not, just make the change. Backwards compatibility is a requirement to be elicited, not an assumption to be baked in.

**Capture to `project-preferences.md`** under Workflow — preferences are declared standards the Critic validates code against.

## Identify Boundary Patterns

As structural characteristics emerge, note where components will interact — API endpoints, database schemas, IPC channels, frontend/backend type contracts. These become the project's contract surfaces, documented in `.prawduct/artifacts/boundary-patterns.md` during planning. Identifying them during discovery scopes the build: boundary-heavy designs need more integration testing and consumer-impact investigation. For products with `exposes_programmatic_interface`, `has_multiple_party_types`, or `multi_process_distributed`, boundary patterns are a significant architectural concern — surface them.

## What Discovery Produces

A `project-state.yaml` with:
- **Classification**: structural characteristics, domain, risk level, prior art
- **Product definition**: vision, personas, core flows, scope (v1 / accommodate / later / out of scope)
- **Cost awareness**: operational cost estimates and constraints (when applicable)
- **Accessibility approach** (for human interfaces), **error handling approach**, **infrastructure dependencies**, **observability approach** — each scaled to risk
- **User expertise profile**: what the user knows and doesn't, inferred from conversation
- **Product identity**: name, personality, technology preferences
- **Workflow preferences**: behavioral choices for automation, PRs, merging — captured in `project-preferences.md`

Discovery scales with the work's size and risk, not with where you are in a timeline (see "Discovery Recurs").

## Common Traps

**Over-discovery**: So many questions the user loses patience. Scale to risk.

**Under-discovery**: Missing a structural characteristic — undetected "handles sensitive data" on a health app drops entire requirement categories. Detect and confirm rather than miss.

**Interrogation mode**: Rigid one-at-a-time questioning. Batch related questions, make inferences, have a conversation.

**Ignoring developer preferences**: Asking what to build but not how. Capture testing, tooling, code style, and architecture preferences early in `project-preferences.md` — read before writing any code.

**Domain blindness**: Not leveraging your own domain knowledge. A marketplace needs trust systems, dispute resolution, payment escrow — surface it; don't wait for the user.

**Overweighting prior art**: Research informs the conversation; it doesn't drive it. A few focused searches are enough.

**Using prior art to gatekeep**: "This already exists, why build it?" is never the right response — people build for learning, customization, ownership, fun. Surface what exists, then help them build something great.

**Cost blindness**: The user finds out about operational costs after deployment instead of during design.

**Accessibility afterthought**: A human interface with no accessibility baseline. Bolted on later is expensive and incomplete.

**Infrastructure blindness**: Everything mocked, tests pass, product declared complete — but nothing actually persists. Establish what must be tested real vs. mocked.

**Observability afterthought**: Monitoring-implying characteristics with no observability baseline. Like accessibility, cheaper to design in than retrofit.
