# Requirements

## V1 Scope

Not everything below is v1. Our own principles demand we scope ourselves. Requirements are tagged:

- **[v1]** — Must have for initial usable system
- **[v1.5]** — Build soon after v1 validates, architecturally accommodate now
- **[v2]** — Important but can wait for real usage data

---

## R1: Validation & Discovery

### R1.0: Build Validation [v1]
Before investing in discovery, the system must assess whether the product idea warrants building. This includes:
- Is this a solved problem? If good solutions exist, surface them and ask what's different about the user's need.
- Is this actually one product or multiple? If multiple, help the user pick one to start.
- Is this feasible for LLM-assisted development? Some products (real-time multiplayer, safety-critical systems, heavy hardware integration) have constraints that should be surfaced early.

The system must be willing to recommend not building.

### R1.1: Intake Classification [v1]
The system must analyze raw user input and classify the product idea along two dimensions:
- **Domain:** Social, marketplace, productivity, B2B, utility, content, automation, developer tool, etc.
- **Product shape:** UI application, background automation/pipeline, API/service, multi-party platform, or hybrid. This classification determines which artifacts are relevant.

Classification must not require the user to understand these categories.

### R1.2: Dynamic Questioning [v1]
The system must generate context-appropriate discovery questions based on the product's classification. Questions must be prioritized by impact: ask the questions whose answers most change the direction of the project first.

### R1.3: Expertise Calibration [v1]
The system must infer the user's expertise level across multiple dimensions (product thinking, technical architecture, design, domain knowledge) from conversational signals — not by asking the user to self-assess. It must adjust its vocabulary, depth, and what it chooses to explain vs. assume accordingly.

### R1.4: Proactive Expertise [v1]
The system must surface considerations the user hasn't raised, particularly in areas where the user lacks expertise. It must not merely ask questions — it must bring knowledge the user doesn't have and flag risks the user hasn't considered.

### R1.5: Opinionated Pushback [v1]
The system must challenge user decisions that conflict with good product, design, or engineering practice. It must do so constructively, with rationale, and defer when the user makes an informed decision to proceed anyway.

### R1.6: Scope Management [v1]
The system must help users identify an appropriate v1 scope. It must distinguish between what's essential now, what should be architecturally accommodated but not built, and what's genuinely later. It must resist scope creep while remaining responsive to legitimate scope evolution.

### R1.7: Prior Art Awareness [v1]
For product domains where existing solutions are common, the system must surface relevant alternatives. Not to discourage building, but to sharpen the differentiation question and to learn from what existing products do well or poorly. The system should use web search when needed to assess the competitive landscape.

### R1.8: Pacing Sensitivity [v1]
The system must recognize and adapt to user impatience. Some users want thorough discovery. Some want to build immediately and iterate. The system must find the minimum viable discovery for the product's risk level — a family utility needs less upfront thinking than a B2B platform — and not hold the user hostage to a process they find tedious. When accelerating, the system must be explicit about what it's assuming and what risks it's accepting on the user's behalf.

### R1.9: Regulatory and Compliance Discovery [v1.5]
For products in regulated domains or with specific legal requirements (health data, children's data, financial transactions, EU users, accessibility law), the system must identify applicable regulatory constraints during discovery and surface them as architectural and design requirements, not afterthoughts.

## R2: Artifact Generation

### R2.1: Product-Shape-Appropriate Artifacts [v1]
The system must produce artifacts appropriate to the product's shape. Not every product needs every artifact. The system must select from the full artifact menu based on what's relevant:

**Universal artifacts (all product shapes):**
- Product brief (users, personas, core problem, success criteria)
- Data model (entities, relationships, state machines, constraints)
- Security model (authentication, authorization, data privacy, abuse prevention)
- Test specifications (unit, integration, E2E — with specific scenarios, not just "test this feature")
- Non-functional requirements (performance targets, scalability expectations, uptime requirements, cost constraints)
- Operational specification (deployment strategy, monitoring, alerting, logging, failure recovery, backup)
- Dependency manifest (external services, APIs, libraries — with justification and version pinning)

**UI application artifacts:**
- Information architecture (screens, navigation, content hierarchy)
- Screen-by-screen specifications (all states: loading, empty, error, success, partial, offline where applicable)
- Design direction (layout patterns, component inventory, interaction patterns, visual tone)
- Accessibility specification (WCAG compliance targets, screen reader support, keyboard navigation, color contrast)
- Localization requirements (what needs translating, cultural considerations, locale-specific behavior)
- Onboarding and first-run experience specification

**API/service artifacts:**
- API contracts (endpoints, request/response shapes, error codes, auth requirements, rate limits)
- Integration guide (for consumers — how to authenticate, common patterns, error handling)
- Sandbox/testing environment specification
- Versioning strategy
- SLA definition

**Automation/pipeline artifacts:**
- Pipeline architecture (inputs, processing stages, outputs, scheduling)
- Monitoring and alerting specification (what to watch, what constitutes failure, escalation)
- Configuration specification (what's configurable, defaults, validation)
- Failure and recovery specification (what happens when each stage fails, retry logic, dead letters)

**Multi-party artifacts (products with distinct user types):**
- Per-party experience specification (each party's flows, needs, and constraints)
- Party interaction model (how parties affect each other, trust boundaries)
- Migration/adoption plan (if replacing an existing process — how do parties transition?)

### R2.2: Agent-Consumable Format [v1]
All artifacts must be structured for consumption by LLM coding agents. This means: explicit, unambiguous, self-contained where possible, with clear cross-references where dependencies exist. Artifacts must not require human interpretation to be actionable.

### R2.3: Human-Readable [v1]
Despite being agent-consumable, all artifacts must also be readable by humans at the user's expertise level. A non-technical user should be able to review the product brief and screen specs. A technical user should be able to review the architecture and data model.

### R2.4: Modularity and Dependency Tracking [v1]
Artifacts must be modular with explicit dependency tracking. When a decision changes, the system must identify all downstream artifacts affected and the nature of the impact.

### R2.5: Build Ordering [v1]
The system must produce an execution plan: what gets built first, what depends on what, what can be parallelized. This plan must account for the value of early user feedback (build visible things before invisible infrastructure where feasible).

### R2.6: Cost Awareness [v1.5]
For products with ongoing operational costs (cloud hosting, API usage, LLM inference, third-party services), the system must surface cost implications during artifact generation and flag designs that may have unexpectedly high operational costs.

## R3: Quality Governance

### R3.1: Automated Critic [v1]
The system must include an automated review process that evaluates work-in-progress against specifications. This review must run continuously during development, not only at the end.

### R3.2: Spec Compliance Verification [v1]
The Critic must verify that every specified requirement is implemented. Requirements that are not implemented must be explicitly flagged — they may not be silently dropped.

### R3.3: Test Integrity Enforcement [v1]
The system must enforce that:
- Tests are written alongside or before implementation.
- Tests may not be deleted, commented out, or have assertions weakened without documented justification and explicit approval.
- Test modifications are flagged for review with explanation of what changed and why.
- Tests verify behavior, not implementation details.
- Test coverage includes happy path, error cases, edge cases, and empty/loading states.

### R3.4: Architectural Consistency [v1]
The Critic must periodically verify that implementation matches designed architecture. Module boundaries, dependency directions, and data flow must be checked against the architecture artifact.

### R3.5: Documentation Integrity [v1]
The system must enforce a documentation architecture:
- **Source of Truth documents**: exactly one canonical location for each topic. No duplication.
- **Generated documentation**: derived from implementation, not authored separately.
- **Ephemeral documentation**: working notes with explicit expiration, stored separately from canonical docs.
- Ad hoc document creation in the canonical doc space must be prevented.

### R3.6: Decision Documentation [v1]
Every non-trivial decision made during development must include rationale. "I used library X" is insufficient. "I used X because Y, considered Z, rejected it because W" is required.

### R3.7: Meta-Enforcement [v1]
Some governance checks must be structural/mechanical rather than LLM-judged, to avoid the "who watches the watchmen" problem. Examples: test count must not decrease, assertion count per test must not decrease, files in protected architectural boundaries must not be modified without explicit approval.

### R3.8: Accessibility Enforcement [v1.5]
For products with user interfaces, the Critic must verify that accessibility requirements from the specification are implemented: semantic markup, keyboard navigation, screen reader compatibility, color contrast ratios, and text scaling support.

## R4: Trajectory Management

### R4.1: Holistic Review [v1]
The system must periodically step back from incremental work and evaluate the project holistically: "If we were designing this from scratch today, knowing what we now know, would we design it this way?"

### R4.2: Refactoring Triggers [v1]
Holistic reviews must be triggered by:
- Changes that touch many modules (spreading complexity)
- Changes that work around existing structure (fighting the architecture)
- Repeated changes to the same area (accreting complexity)
- Regular cadence at feature milestones

### R4.3: Entropy Resistance [v1]
The system must actively resist project entropy: documentation drift, architectural erosion, test suite degradation, and scope creep. This is continuous, not periodic.

## R5: Feedback Integration

### R5.1: Upstream Propagation [v1]
When a user reacts to a built artifact and requests changes that affect upstream decisions, the system must propagate those changes through all affected artifacts and communicate the blast radius.

### R5.2: Change Impact Assessment [v1]
Before implementing a change, the system must assess and communicate its impact: what artifacts change, what work is invalidated, and whether the change suggests a deeper rethinking.

### R5.3: Graceful Scope Evolution [v1]
The system must handle the reality that users change their minds, discover new requirements through usage, and evolve their vision — without treating every change as a crisis or requiring a full restart.

### R5.4: Reclassification [v1.5]
When scope evolution fundamentally changes the product's nature (a cribbage app becomes a multi-game platform; a simple tool becomes a B2B service), the system must recognize the reclassification, re-run relevant discovery for the new product shape, and communicate what this means for the existing work.

## R6: Learning

### R6.1: Project Observation [v2]
The system must passively collect structured signals from every project: where governance intervened, where users changed direction, where discovery gaps appeared, what patterns emerged.

### R6.2: Pattern Extraction [v2]
The system must periodically analyze observations across projects to identify statistically meaningful patterns.

### R6.3: Conservative Incorporation [v2]
New learnings must pass validation before incorporation: consistency with existing principles, appropriate specificity, reversibility assessment, and adversarial testing against historical projects.

### R6.4: Learning Scope [v2]
The system learns *questions to ask* and *problems to watch for*. It does not learn *solutions to prescribe* or *preferences to enforce*.

### R6.5: Learning Provenance and Retirement [v2]
Every incorporated learning must carry provenance and must be subject to retirement if later evidence contradicts it.

## R7: Adaptability

### R7.1: User Spectrum [v1]
The system must function effectively for users ranging from non-technical to highly experienced, adapting language, depth, and involvement expectations dynamically.

### R7.2: Product Diversity [v1]
The system must handle the full range of software product shapes: consumer mobile apps, web applications, background automations, APIs and services, B2B platforms, family utilities, developer tools, data pipelines, and hybrids. It must not be biased toward any particular product type.

### R7.3: Agent Agnosticism [v1.5]
While the initial implementation targets Claude Code, the artifact formats and governance principles must be designed to be consumable by any competent LLM coding agent.
