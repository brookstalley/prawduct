# Example: Three-Signal Architecture (API Service)

A design outline (no code) showing a strong observability approach for a multi-endpoint API service with database and external dependencies.

- **What You Get**: Slow-response debugging via span performance tables, error investigation via correlated logs+traces, cache effectiveness monitoring via span attributes, user-reported issue tracing via domain-scoped correlation IDs.
- **Architecture**: App sends traces to a trace backend; trace backend derives RED metrics (rate, errors, duration) automatically and pushes to a metrics store; structured logs ship to a log aggregator with trace context attached; a visualization layer queries all three.
- **Instrumentation**: Layer 1 (auto-instrumentation for HTTP and DB), Layer 2 (decorator on service methods), Layer 3 (cache tier and domain entity attributes on spans), Layer 4 (none needed — layers 1-3 cover everything).
- **Correlation**: Request ID (generated or from header), session ID (from auth token), domain entity ID (set by handler). All three injected into every span and log line.
- **Sensitive data**: Blocklist of parameter names (password, token, secret, key) — never recorded in spans. Auth tokens logged as presence/absence, never values.
- **Infrastructure**: All observability services behind an opt-in profile — zero cost in dev when not needed. NoOp provider when disabled means instrumentation code stays but produces nothing.
- **Agent access**: MCP tools expose log search (by time, keyword, correlation ID), trace lookup (by trace ID or span name), and metric queries. The development agent can verify observability signals during building and investigate failures without leaving the development loop.
- **Why this is strong**: Derived metrics eliminate manual counter/histogram maintenance. Correlation context means any user-reported issue traces to full call tree. Sensitive data filtering is a safety net, not developer discipline. Zero-cost-when-disabled means observability code is never "in the way." Agent-accessible interfaces close the debugging loop — the agent can investigate without asking the developer to check a dashboard.
