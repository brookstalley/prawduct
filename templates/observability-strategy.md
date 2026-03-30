---
artifact: observability-strategy
version: 2
depends_on:
  - artifact: nonfunctional-requirements
  - artifact: product-brief
last_validated: null
---

# Observability Strategy

<!-- STATUS: This is a product specification. The Builder implements this
     as code infrastructure starting from chunk 1. Observability is not
     bolted on at the end — it's part of the product from the start.

     Proportionality:
     - Low-risk: 1-2 paragraphs. Error logging + health check. Done.
     - Medium-risk: Half a page. Structured logging + key metrics + basic alerting.
     - High-risk: Full document. Logging + metrics + tracing + alerting + dashboards.

     This template shows all sections. For low-risk products, most sections
     are "Not applicable" or a single sentence. Don't over-engineer
     observability for a family app. -->

## What You Get

<!-- What debugging and operational scenarios does this observability design enable?
     Write 3-5 concrete scenarios in the form "When X happens, you can Y."

     Guidance prompts:
     - Slow response → how do you find the bottleneck?
     - User reports a problem → how do you trace what happened?
     - Intermittent failures → how do you find the pattern?
     - Is a dependency degrading? → how do you see it before users do?

     This section is the contract: if these scenarios don't work,
     the observability strategy has failed. For low-risk products,
     one scenario ("When it crashes, the error log tells you why") is enough. -->

## Architecture

<!-- How signals flow from the application to where humans (or systems) consume them.
     For a simple product, a one-line description. For complex products, a diagram.

     Guidance: application → [exporters/collectors] → [storage] → [visualization/alerting] -->

## Signal Types

### Logging

<!-- What events get logged, at what level, in what format.

     - Log levels and what each means for THIS product
     - Structured vs. plain text
     - Key events worth logging
     - Destinations (dev vs. production)
     - Retention

     For low-risk products: "console.error for errors, console.warn for warnings.
     No structured logging. No aggregation." is perfectly valid. -->

### Metrics

<!-- Quantitative measurements. Three categories:
     - Application metrics (latency, error rate, throughput)
     - Business metrics (from product brief success criteria)
     - Infrastructure metrics (if self-hosted)

     Key decision: Can metrics be derived from existing signals (e.g.,
     generating rate/error/duration from traces) rather than instrumented
     separately? Derived metrics are cheaper to maintain.

     For low-risk products: "No formal metrics" is valid. -->

### Tracing

<!-- Request flow across components or processing stages.

     When tracing is warranted (not just microservices):
     - Multiple services or processes
     - Complex async workflows or pipelines
     - Request handling with many sequential processing steps
     - Any system where "which step was slow?" is a real question

     For most single-service products: "Not applicable." -->

## Instrumentation Layers

<!-- Four layers, from automatic to manual. Most coverage should come
     from layers 1-2. Scale to risk: low → layer 1 only (or nothing),
     medium → layers 1-2, high → all four.

     1. **Automatic/framework** — what the runtime gives for free
        (HTTP middleware, DB driver logging, ORM query logging)
     2. **Declarative** — lightweight markers that don't change business logic
        (decorators, middleware, annotations, aspect-oriented instrumentation)
     3. **Contextual** — enriching existing signals with domain attributes
        (user_id on a request span, order_id in log entries, cache hit/miss)
     4. **Manual** — explicit instrumentation for critical paths.
        Use sparingly — each manual instrument point is a maintenance burden. -->

## Correlation Context

<!-- What IDs tie related events together across signals and time?
     Three scopes to consider:

     - **Request-scoped**: ties all signals from one request/operation
     - **Session-scoped**: ties all requests from one user session
     - **Domain-scoped**: ties all operations on one business entity
       (conversation, order, deployment, etc.)

     How these IDs propagate: middleware injection, context variables,
     header forwarding, log field inclusion.

     For low-risk products: "Not applicable — single-user, single-request." is valid. -->

## Sensitive Data Filtering

<!-- What sensitive data might appear in observability output, and how
     is it prevented from leaking? Three approaches (not mutually exclusive):

     - **Blocklist**: named fields always redacted
       (password, token, ssn, api_key, etc.)
     - **Type-based**: data types that self-redact
       (e.g., Pydantic SecretStr, custom wrapper types,
       or language-specific equivalents)
     - **Structural**: separate "what happened" from "with what data"
       — log the operation and entity ID, not the entity content

     Cross-reference with security model artifact.

     For products with no sensitive data: "No sensitive data in scope." is valid. -->

## Alerting

<!-- When and how to notify someone that something needs attention.

     - Alert conditions (error rate, latency, health check failure)
     - Alert channels (proportionate to severity and risk)
     - Alert design (enough context to act; avoid fatigue)

     For low-risk: "No automated alerting" is valid. -->

## Health Signals

<!-- How to determine if the product is healthy.

     - What constitutes "healthy"
     - Health check endpoint / command / signal
     - Degraded states: what "broken but partially functional" looks like

     For low-risk products: "If the app launches and the main screen renders,
     it's healthy." -->

## Infrastructure and Deployment

<!-- Where observability infrastructure lives and how it's managed.

     - Technology choices (with rationale — documented in dependency manifest)
     - Deployment model: always-on or opt-in?
     - For products deployed in varied environments: is observability
       zero-cost when not configured? (conditional init, NoOp providers,
       optional infrastructure profiles)
     - Cost considerations for observability infrastructure itself

     Framework note: Prawduct does not prescribe specific tools. OpenTelemetry,
     Datadog, Grafana, CloudWatch, plain console.log — all are valid choices
     when justified for the product's context. The choice is a technology
     decision, not a framework decision. -->

## Agent-Accessible Observability

<!-- Observability has two consumers: human operators (dashboards, log UIs,
     alert channels) and development agents (tool interfaces for closed-loop
     debugging). Both need access to the same signals, but through different
     interfaces.

     The agent debugging loop: run → observe failure → investigate
     (query logs, check metrics, inspect traces) → fix → verify.
     This loop breaks at "investigate" if observability is only
     human-accessible. Design observability for both consumers.

     Considerations:
     - When the product already has tool interfaces (MCP servers, CLI
       commands, API endpoints) for testing or automation, add
       observability queries to the same surface. The marginal cost
       is low; the debugging efficiency gain is high.
     - Agent-accessible and human-accessible observability can overlap.
       A Grafana dashboard and an MCP log-query tool serve different
       consumers with different access patterns. Duplication is acceptable
       when it makes the agent self-sufficient for debugging.
     - Agent observability can be simpler than human observability. The
       agent needs: search logs by time/keyword/correlation ID, check
       whether specific metrics exist, inspect recent traces. Rich
       visualization is unnecessary.
     - Scale to product complexity: for a CLI tool, "read the log file"
       is sufficient. For a service with structured logging, a tool
       interface that searches by correlation ID is worth the investment.
       For a full three-signal system, tool interfaces to all three
       backends enable root-cause analysis without human intervention.

     For products without observability backends: "Not applicable —
     console output is directly readable by the agent." is valid. -->

## Verification

<!-- How to confirm observability is working as designed.

     - Can you reproduce each "What You Get" scenario?
     - If agent-accessible interfaces to observability backends exist
       (MCP tools, CLI commands, API endpoints), use them during product
       verification to confirm signals are flowing.
     - This is part of "does the product work" — including
       "can I debug it when it doesn't." -->

## Examples

See `docs/examples/` for complete observability design examples:
- `observability-api-service.md` — Three-signal architecture for an API service
- `observability-event-driven.md` — Cloud-managed approach for an event-driven system
