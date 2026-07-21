# Example: Cloud-Managed Approach (Event-Driven System)

A design outline (no code) showing a different but equally valid approach for a serverless event-processing system using managed cloud services.

- **What You Get**: Failed event investigation via structured log search with event ID, processing latency monitoring via cloud provider metrics, dead-letter queue alerting for poison messages, end-to-end event flow tracing via propagated correlation headers.
- **Architecture**: Functions emit structured logs to cloud-native log service (CloudWatch, Cloud Logging); cloud provider supplies invocation metrics automatically; events carry correlation headers through queues; alerts via cloud-native alerting rules.
- **Instrumentation**: Layer 1 (cloud provider auto-captures invocation duration, errors, cold starts), Layer 2 (structured logging middleware on function entry/exit), Layer 3 (event type, source queue, and business entity ID as log fields). No layer 4 — cloud provider metrics eliminate need for manual instrumentation.
- **Correlation**: Event ID (from message metadata) propagated through all processing stages. No session concept — events are independent. Domain entity ID (order_id, user_id) extracted from event payload and added to every log entry.
- **Sensitive data**: Structural approach — log event type and entity ID, never event payload. PII fields stripped at ingestion by log service filter rules.
- **Infrastructure**: Fully managed — no observability infrastructure to deploy or maintain. Cost scales with usage. Alerting rules defined as infrastructure-as-code alongside function definitions.
- **Agent access**: Cloud provider CLIs (aws logs, gcloud logging) serve as the agent's observability interface — no custom MCP needed. The development agent queries logs via CLI commands during debugging. For richer access, a thin MCP wrapper around the cloud provider's log/metric APIs adds structured querying.
- **Why this is strong**: Zero infrastructure overhead — the cloud provider handles storage, retention, and scaling. Correlation through event headers means you can trace a business transaction across dozens of function invocations. Structural data filtering (log the ID, not the payload) is simpler and more reliable than field-level blocklists in a high-throughput event system. Cloud CLIs provide agent access with no additional infrastructure.
