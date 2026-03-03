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

## Example A: Three-Signal Architecture (API Service)

<!-- A design outline (no code) showing a strong observability approach
     for a multi-endpoint API service with database and external dependencies.

     - **What You Get**: Slow-response debugging via span performance tables,
       error investigation via correlated logs+traces, cache effectiveness
       monitoring via span attributes, user-reported issue tracing via
       domain-scoped correlation IDs.
     - **Architecture**: App sends traces to a trace backend; trace backend
       derives RED metrics (rate, errors, duration) automatically and pushes
       to a metrics store; structured logs ship to a log aggregator with
       trace context attached; a visualization layer queries all three.
     - **Instrumentation**: Layer 1 (auto-instrumentation for HTTP and DB),
       Layer 2 (decorator on service methods), Layer 3 (cache tier and
       domain entity attributes on spans), Layer 4 (none needed — layers
       1-3 cover everything).
     - **Correlation**: Request ID (generated or from header), session ID
       (from auth token), domain entity ID (set by handler). All three
       injected into every span and log line.
     - **Sensitive data**: Blocklist of parameter names (password, token,
       secret, key) — never recorded in spans. Auth tokens logged as
       presence/absence, never values.
     - **Infrastructure**: All observability services behind an opt-in
       profile — zero cost in dev when not needed. NoOp provider when
       disabled means instrumentation code stays but produces nothing.
     - **Agent access**: MCP tools expose log search (by time, keyword,
       correlation ID), trace lookup (by trace ID or span name), and
       metric queries. The development agent can verify observability
       signals during building and investigate failures without leaving
       the development loop.
     - **Why this is strong**: Derived metrics eliminate manual counter/
       histogram maintenance. Correlation context means any user-reported
       issue traces to full call tree. Sensitive data filtering is a
       safety net, not developer discipline. Zero-cost-when-disabled
       means observability code is never "in the way." Agent-accessible
       interfaces close the debugging loop — the agent can investigate
       without asking the developer to check a dashboard. -->

## Example B: Cloud-Managed Approach (Event-Driven System)

<!-- A design outline (no code) showing a different but equally valid
     approach for a serverless event-processing system using managed
     cloud services.

     - **What You Get**: Failed event investigation via structured log
       search with event ID, processing latency monitoring via cloud
       provider metrics, dead-letter queue alerting for poison messages,
       end-to-end event flow tracing via propagated correlation headers.
     - **Architecture**: Functions emit structured logs to cloud-native
       log service (CloudWatch, Cloud Logging); cloud provider supplies
       invocation metrics automatically; events carry correlation headers
       through queues; alerts via cloud-native alerting rules.
     - **Instrumentation**: Layer 1 (cloud provider auto-captures
       invocation duration, errors, cold starts), Layer 2 (structured
       logging middleware on function entry/exit), Layer 3 (event type,
       source queue, and business entity ID as log fields). No layer 4
       — cloud provider metrics eliminate need for manual instrumentation.
     - **Correlation**: Event ID (from message metadata) propagated
       through all processing stages. No session concept — events are
       independent. Domain entity ID (order_id, user_id) extracted from
       event payload and added to every log entry.
     - **Sensitive data**: Structural approach — log event type and
       entity ID, never event payload. PII fields stripped at ingestion
       by log service filter rules.
     - **Infrastructure**: Fully managed — no observability infrastructure
       to deploy or maintain. Cost scales with usage. Alerting rules
       defined as infrastructure-as-code alongside function definitions.
     - **Agent access**: Cloud provider CLIs (aws logs, gcloud logging)
       serve as the agent's observability interface — no custom MCP
       needed. The development agent queries logs via CLI commands
       during debugging. For richer access, a thin MCP wrapper around
       the cloud provider's log/metric APIs adds structured querying.
     - **Why this is strong**: Zero infrastructure overhead — the cloud
       provider handles storage, retention, and scaling. Correlation
       through event headers means you can trace a business transaction
       across dozens of function invocations. Structural data filtering
       (log the ID, not the payload) is simpler and more reliable than
       field-level blocklists in a high-throughput event system. Cloud
       CLIs provide agent access with no additional infrastructure. -->
