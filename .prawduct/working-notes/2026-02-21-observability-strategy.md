# Design Proposal: Observability Strategy Integration

**Status**: Proposal (not yet implemented)
**Tier**: 3 (Working Note — design exploration)
**Created**: 2026-02-21
**Expires**: 2026-03-07

---

## Problem Statement

Observability in prawduct is currently treated as:

1. **A developer preference** (Domain Analyzer dimension 11): "logging strategy" as a methodology choice alongside code style and testing approach. This captures *how* to log (structured vs. unstructured, log4j vs. winston) but not *what* to observe or *why*.

2. **An unattended-system concern** (monitoring-alerting-spec.md for `runs_unattended` only): Detailed monitoring, alerting, health metrics, and failure detection — but only for pipelines and background systems.

This creates a gap: **interactive products get zero observability guidance.** A web app, mobile app, or CLI tool built by prawduct will have no logging architecture, no error tracking, no performance metrics, and no health signals unless the user explicitly asks for them or mentions logging as a development preference.

### Why This Is Wrong

Every product benefits from observability, proportionate to its risk and complexity:

| Product Type | What Observability Provides |
|-------------|---------------------------|
| Low-risk family utility | Error logs that help debug problems. Health check that confirms it's running. |
| Medium-risk web app | Structured logs for debugging. Error tracking for reliability. Performance metrics for optimization. |
| High-risk SaaS platform | Distributed tracing across services. SLI/SLO monitoring. Alerting on degradation. Audit logging for compliance. Cost monitoring. |
| CLI tool | Verbosity levels for user-facing output. Debug logging for developers. Error reporting with context. |
| Background pipeline | *(Already well-served by monitoring-alerting-spec.md)* |

The current framework treats observability as optional rather than fundamental. This is analogous to how accessibility was treated before HR7 — something that got added "if the user asked" rather than something built into every product by default.

### The Key Distinction

**"Logging strategy"** (developer preference, dimension 11) answers: *How do we format logs? What library do we use? Where do logs go?*

**"Observability architecture"** (product concern) answers: *What do we instrument? What do we measure? How do we know when something's wrong? How do we debug problems in production?*

The first is a methodology choice. The second is an architectural decision. Prawduct conflates them by putting both under dimension 11.

---

## Proposed Solution

### A. Observability as Universal Concern

Move observability from "developer preference" to a first-class cross-cutting concern that every product addresses, proportionate to risk. This parallels how prawduct handles:
- **Security**: Universal, depth scaled by `handles_sensitive_data` + risk
- **Accessibility**: Universal for `has_human_interface`, depth scaled by risk (HR7)
- **Operations**: Universal, depth scaled by `runs_unattended` + risk

Observability becomes: **universal, depth scaled by risk + structural characteristics.**

### B. New Universal Template: observability-strategy.md

```markdown
---
artifact: observability-strategy
version: 1
depends_on:
  - artifact: nonfunctional-requirements
  - artifact: product-brief
depended_on_by:
  - artifact: operational-spec
  - artifact: test-specifications
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

## Observability Principles

<!-- What guides observability decisions for this product:
     - What's the primary purpose? (debugging, reliability, compliance, user insight)
     - What's the cost tolerance for observability infrastructure?
     - What's the operational model? (developer debugging vs. SRE monitoring vs. automated response) -->

## Logging

<!-- Logging architecture for this product:

     ### Log Levels
     What each level means for THIS product:
     - error: [when to use — failed operations that need attention]
     - warn: [when to use — degraded but functional, approaching limits]
     - info: [when to use — significant business events, state transitions]
     - debug: [when to use — detailed flow for troubleshooting]

     ### Structured Logging
     - Format: [structured JSON / plain text / platform default]
     - Standard fields: [timestamp, level, message, ...product-specific context fields]
     - Correlation: [request ID, session ID, user ID — what ties related log entries together]

     ### Key Events to Log
     - [List the specific events worth logging for this product]
     - [Authentication events, data mutations, external API calls, error conditions]
     - [Business-significant events: orders placed, reports generated, etc.]

     ### Log Destinations
     - Development: [console / file / dev tool]
     - Production: [stdout for containers / log aggregation service / file rotation]

     ### Retention
     - [How long to keep logs — proportionate to risk and compliance needs]

     For low-risk products: "console.error for errors, console.warn for warnings.
     No structured logging. No aggregation." is perfectly valid. -->

## Metrics

<!-- Quantitative measurements of product health and behavior.

     ### Application Metrics
     - [Request latency (p50, p95, p99) — if applicable]
     - [Error rate]
     - [Throughput / request rate]
     - [Queue depth / backlog — if applicable]

     ### Business Metrics
     - [Product-specific: active users, conversion rate, data freshness, etc.]
     - [These come from the product brief's success criteria]

     ### Infrastructure Metrics
     - [CPU/memory/disk — if self-hosted]
     - [Cloud provider metrics — if cloud-deployed]
     - [Cost metrics — if operational cost is a concern]

     For low-risk products: "No formal metrics. Health is determined by whether
     the app works." is valid. -->

## Alerting

<!-- When and how to notify someone that something needs attention.

     ### Alert Conditions
     - [Error rate exceeds threshold]
     - [Latency exceeds threshold]
     - [Health check fails]
     - [Business metric anomaly]

     ### Alert Channels
     - [Email, Slack, PagerDuty, push notification — proportionate to severity and risk]

     ### Alert Design
     - [Include enough context to act without investigating]
     - [Avoid alert fatigue — only alert on actionable conditions]

     For low-risk products: "No automated alerting. The user will notice if it's
     broken." is valid. -->

## Tracing

<!-- Distributed tracing for understanding request flow across components.

     ### When Tracing Is Warranted
     - Multiple services or microservices
     - Complex async workflows
     - Performance debugging across system boundaries

     ### Trace Context
     - [What trace context to propagate]
     - [How traces connect to logs (trace ID in log entries)]

     For most products: "Single service — tracing not applicable." -->

## Error Handling and Reporting

<!-- How errors are captured, reported, and made actionable.

     ### Error Classification
     - [Expected errors (user input, network) vs. unexpected (bugs, state corruption)]
     - [How each class is handled: retry, report, alert, recover]

     ### Error Context
     - [What context is captured with errors: stack trace, request data, user action, system state]
     - [PII considerations: what to redact from error reports]

     ### Error Reporting
     - [How errors reach developers: error tracking service (Sentry, etc.), log aggregation, email]
     - [For low-risk: "Errors logged to console. Developer checks manually." is valid.]

     This section bridges observability and the product's error handling strategy.
     The error handling pattern (how code handles errors) feeds the observability
     system (how errors are reported and tracked). -->

## Instrumentation Approach

<!-- Technology choices for observability infrastructure.

     ### Technology Selection
     - [Logging library and rationale]
     - [Metrics system and rationale (if applicable)]
     - [Tracing system and rationale (if applicable)]
     - [Error tracking service and rationale (if applicable)]

     Technology choices are documented in the dependency manifest with full
     justification. This section captures the architectural rationale for
     the observability stack as a whole.

     Framework note: Prawduct does not prescribe specific tools. OpenTelemetry,
     Datadog, Grafana, CloudWatch, plain console.log — all are valid choices
     when justified for the product's context. The choice is a technology
     decision, not a framework decision. -->

## Health Signals

<!-- How to determine if the product is healthy.

     ### Health Check
     - [What constitutes "healthy" for this product]
     - [Health check endpoint / command / signal]

     ### Degraded States
     - [How to detect partial functionality]
     - [What "degraded but functional" looks like]

     For low-risk products: "If the app launches and the main screen renders,
     it's healthy." -->
```

### C. Proportionality in Practice

The template above shows all sections. Here's what the Artifact Generator produces at each risk level:

**Low-risk utility (e.g., family score tracker):**
```markdown
# Observability Strategy

## Logging
Error and warning messages logged to console. No structured logging.
No log aggregation. Debug messages available in development.

## Health Signals
App launches and main screen renders correctly. No formal health check endpoint.

## Metrics, Alerting, Tracing
Not applicable for a low-risk personal utility.

## Error Handling
Errors displayed to user in-app. console.error for developer debugging.
No error tracking service.
```

**Medium-risk web app (e.g., team productivity tool):**
```markdown
# Observability Strategy

## Observability Principles
Primary purpose: debugging production issues and tracking reliability.
Cost tolerance: low — use built-in platform logging + free-tier services.

## Logging
Structured JSON logging via [library]. Standard fields: timestamp, level,
requestId, userId, message, error (when applicable).

Key events: authentication (login/logout/failure), data mutations (create/update/delete),
external API calls (request/response/error), permission denials.

Development: console output. Production: stdout (containerized) → log aggregation.
Retention: 30 days.

## Metrics
- Request latency (p50, p95, p99)
- Error rate (5xx responses / total requests)
- Active sessions
- API response times by endpoint

## Alerting
- Error rate > 5% for 5 minutes → Slack notification
- Health check failure → Slack notification (then email after 15 min)
- P99 latency > 2s sustained → Slack notification

## Health Signals
GET /health returns 200 when app is running, database is connected,
and external dependencies are reachable.

## Error Handling
Expected errors (validation, auth): logged at warn, returned to user with context.
Unexpected errors: logged at error with stack trace + request context, returned
to user as generic message. Sentry (or equivalent) for error aggregation.
```

### D. Discovery Integration

**Expand dimension 7 (Operational Lifecycle):**

Current dimension 7 asks: "How is this deployed? Updated? Monitored? What does day-2 operation look like?"

Add observability-specific sub-questions:
- "How would you know if something's broken?" (already partially covered)
- **New**: "What do you need to see about how the product is running?" (surfaces observability depth)
- **New**: "When something goes wrong, what information helps you fix it?" (surfaces logging/debugging needs)

These are Tier 2 (ask if not inferable). For low-risk products, infer: "errors logged to console, no formal monitoring."

**Separate dimension 11 concerns:**

Currently, dimension 11 (Development Standards) conflates logging preferences (format, library) with observability requirements (what to instrument). After this change:
- Dimension 7 covers **observability architecture** (what to observe, why, how deep)
- Dimension 11 covers **logging preferences** (structured vs. unstructured, specific libraries, log format conventions)

The Artifact Generator routes dimension 7 answers to `observability-strategy.md` and dimension 11 answers to `project-preferences.md`.

### E. Structural Amplification

**When `runs_unattended` is active:**

The existing `monitoring-alerting-spec.md` becomes a **structural amplification** of the universal `observability-strategy.md`:
- `observability-strategy.md` defines principles and approach (universal)
- `monitoring-alerting-spec.md` implements those principles with specific metrics, thresholds, alerting rules, and dashboard specs (structural)

Dependency: `monitoring-alerting-spec.md` depends on `observability-strategy.md`.

**When `has_human_interface` is active:**

Amplify observability for user-facing concerns:
- Frontend error tracking (JavaScript errors, render failures, interaction failures)
- Performance metrics visible to users (page load time, interaction latency)
- User experience signals (if applicable — rage clicks, abandonment)

**When `exposes_programmatic_interface` is active:**

Amplify observability for API concerns:
- Per-endpoint latency and error rates
- Consumer-visible health endpoints
- Rate limit metrics
- API versioning and deprecation tracking

### F. Builder Integration

Observability is implemented from chunk 1, not bolted on:

1. **Scaffold chunk**: Set up logging infrastructure (library, configuration, standard fields)
2. **Every subsequent chunk**: Import logging utility; instrument key operations as they're built
3. **Error handling**: Every error path includes structured logging with context
4. **Health check**: Implemented in the first deployable chunk
5. **Metrics** (medium+ risk): Instrumented as features are built, not as a separate "add metrics" phase

**Builder checkpoint**: Before marking a chunk complete, verify key flows in that chunk are instrumented per `observability-strategy.md`.

### G. Critic Integration

**Check 1 (Spec Compliance)** — add for all products with `observability-strategy.md`:
- Key flows are instrumented (proportionate to strategy depth)
- Error handling includes logging with appropriate context
- Log levels are appropriate (not everything at INFO/DEBUG)
- Health check implemented (if specified in strategy)

**Check 5 (Coherence)** — add:
- Observability implementation matches `observability-strategy.md`
- `monitoring-alerting-spec.md` (for unattended systems) is consistent with observability strategy
- Logging approach matches `project-preferences.md` logging preferences

**Severity**: WARNING for missing instrumentation (must address before delivery). BLOCKING only if the observability infrastructure is fundamentally missing or contradicts the strategy.

### H. Review Lens Integration

**Architecture Lens** — add:
- Observability architecture check: are the observability pieces connected? (logs → aggregation, metrics → dashboards, errors → tracking)
- Cost proportionality: is the observability infrastructure appropriate for the product's scale?
- Operational readiness: can someone debug a production issue with the instrumentation provided?

**Skeptic Lens** — extend:
- "Can you tell when this product is failing?" (partially covered for `runs_unattended`; extend to all products)
- "If a user reports a bug, can a developer reproduce it from the available logs and metrics?"

### I. Onboarding Integration

For existing codebases being onboarded:

1. **Scan** for existing observability patterns:
   - Logging: log library imports, log configuration files, logging calls
   - Metrics: Prometheus, StatsD, CloudWatch, Datadog client code
   - Tracing: OpenTelemetry, Jaeger, Zipkin, X-Ray imports
   - Error tracking: Sentry, Bugsnag, Rollbar, Airbrake initialization
   - Health checks: health endpoints, readiness probes
2. **Classify** the implicit observability strategy:
   - What's instrumented (which flows, which events)
   - What's measured (which metrics)
   - What's alerted on
   - What's missing (key flows without instrumentation)
3. **Present** to user: "I found these observability patterns in your codebase: [summary]. Here's the strategy I'd document: [preview]. Anything to add or change?"
4. **Generate** `observability-strategy.md` from discovered patterns + user input

---

## Integration Points

| File | Change | Scope |
|------|--------|-------|
| `templates/observability-strategy.md` | **New** — universal template for observability strategy | New file |
| `skills/domain-analyzer/SKILL.md` | Expand dimension 7 with observability sub-questions; clarify dimension 11 scope | Medium edit |
| `skills/artifact-generator/SKILL.md` | Add observability-strategy.md to universal artifact set with proportionality rules | Medium addition |
| `skills/builder/SKILL.md` | Add observability implementation guidance (chunk 1 instrumentation) | Medium addition |
| `agents/critic/SKILL.md` | Add observability compliance to Check 1, coherence to Check 5 | Medium addition |
| `agents/review-lenses/SKILL.md` | Add observability checks to Architecture Lens, extend Skeptic "can you tell when it's failing" | Small addition |
| `skills/orchestrator/onboarding.md` | Add observability pattern extraction | Medium addition |
| `docs/high-level-design.md` | Update artifact dependency diagram; add Observability to Cross-Cutting Concerns | Small edit |
| `templates/unattended-operation/monitoring-alerting-spec.md` | Add dependency on observability-strategy.md in frontmatter | Small edit |

**Estimated scope**: Structural-tier DCP. 1 new template, 8 modified files.

---

## Implementation Sequence

1. Create the `observability-strategy.md` template
2. Update Domain Analyzer with dimension 7 expansion and dimension 11 clarification
3. Update Artifact Generator with generation rules and proportionality
4. Update `monitoring-alerting-spec.md` frontmatter (dependency on observability-strategy)
5. Update Builder with instrumentation guidance
6. Update Critic with compliance checks
7. Update Review Lenses with observability checks
8. Update onboarding flow
9. Update high-level-design.md
10. Run Critic review

**Dependency**: Should be implemented after the Coverage Audit Mechanism (so the concern can be registered). Independent of the Design System Integration proposal.

---

## Relationship to Existing Templates

### monitoring-alerting-spec.md

This existing template (for `runs_unattended`) remains as a **structural amplification** of the universal observability strategy. It provides deeper coverage of monitoring thresholds, alerting rules, health metrics, and dashboard specifications that unattended systems specifically need.

After this change:
- `observability-strategy.md` (universal) → principles, logging, basic metrics
- `monitoring-alerting-spec.md` (structural, `runs_unattended`) → detailed monitoring, alerting rules, failure detection, health dashboards

### operational-spec.md

The current operational spec has a "Monitoring" section. After this change, that section references `observability-strategy.md` for the observability approach and adds only deployment-specific operational concerns (how to check logs, where dashboards live, who gets alerts).

### project-preferences.md

Logging *preferences* (library choice, format preference, log destination) stay in project-preferences.md as developer methodology. Logging *architecture* (what to instrument, log levels, correlation IDs) moves to observability-strategy.md as product architecture.

---

## Open Questions

1. **Should observability trigger a Hard Rule?** Accessibility has HR7 ("No Accessibility Afterthought"). Should observability get a similar rule ("No Observability Afterthought")? Proposed answer: **not yet.** HR7 was justified because accessibility is often genuinely forgotten and is hard to retrofit. Observability is easier to add incrementally — missing it at the start is not as costly to fix. Monitor whether products built with prawduct consistently lack observability despite the strategy artifact; if so, a Hard Rule may be warranted.

2. **Error handling strategy**: This proposal touches error handling (§ Error Handling and Reporting) but doesn't fully address the "error handling strategy" gap identified in the meta-meta analysis. A full error handling strategy (consistent taxonomy, recovery patterns, error UX) might warrant its own design proposal. For now, the observability-strategy.md covers the reporting side of errors; the handling side is partially covered by existing failure-recovery-spec.md for unattended systems.

3. **Analytics / product metrics**: This proposal includes "Business Metrics" in the metrics section, which partially addresses the analytics gap. But product analytics (user behavior tracking, feature usage, conversion funnels) is a distinct concern from operational observability. Should analytics be a separate design proposal? Proposed answer: **defer for now.** The observability strategy covers the operational side. Product analytics is a distinct concern that merits its own investigation when prawduct starts building consumer-facing products at scale.
