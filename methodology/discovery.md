# Discovery: Understanding What to Build

The goal of discovery is to understand the problem space deeply enough to design a good solution. Not perfectly — deeply enough. The right depth depends on the stakes.

## The Core Question

Before you can build anything well, you need to understand what kind of thing you're building. Not in abstract terms — in structural terms that determine what artifacts you'll need and what risks you'll face.

**Five structural characteristics** shape every product. Detect these early from user language and context:

- **Has human interface** — Users see screens, hear audio, read output. Signals: "dashboard", "app", "users will see", "button". Implications: need interaction design, accessibility, onboarding, state handling (empty, loading, error).

- **Runs unattended** — Operates without humans watching. Signals: "automatically", "cron", "monitors", "runs in background". Implications: need failure recovery, monitoring, alerting, scheduling. Silent failure is the default — design against it.

- **Exposes programmatic interface** — Other systems call it. Signals: "API", "webhook", "endpoint", "integration". Implications: need API contracts, versioning, consumer documentation, error codes.

- **Has multiple party types** — Different user types with different privileges. Signals: "buyers and sellers", "admin panel", "teachers and students". Implications: need per-party specs, trust boundaries, data isolation.

- **Handles sensitive data** — Data that has regulatory, privacy, or safety implications. Signals: "health", "payments", "children", "PII". Implications: need data lifecycle design, breach scenarios, audit trails, regulatory awareness.

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

## What Discovery Produces

Discovery produces a `project-state.yaml` with:
- **Classification**: structural characteristics, domain, risk level
- **Product definition**: vision, personas, core flows, scope (v1 / accommodate / later / out of scope)
- **User expertise profile**: what the user knows and doesn't, inferred from conversation
- **Product identity**: name, personality, technology preferences

Discovery is done when you have enough understanding to design artifacts that won't need fundamental rework. For a low-risk product, that might be 10 minutes. For a high-risk product, it might be several sessions.

## Common Traps

**Over-discovery**: Asking so many questions the user loses patience. Scale to risk. A personal utility doesn't need 25 questions about failure modes.

**Under-discovery**: Missing a structural characteristic. If you don't detect "handles sensitive data" for a health app, you'll miss entire requirement categories. Better to detect and confirm than to miss.

**Interrogation mode**: Asking questions one at a time in a rigid sequence. Batch related questions. Make inferences. Have a conversation, not an interview.

**Ignoring developer preferences**: Asking what to build but not how to build it. Technical users have strong opinions about testing, tooling, code style, and architecture patterns. Ask early.

**Domain blindness**: Not leveraging your own knowledge of the domain. If someone's building a marketplace, you know marketplaces need trust systems, dispute resolution, and payment escrow. Surface that knowledge; don't wait for the user to think of it.
