---
artifact: pipeline-architecture
version: 1
depends_on:
  - artifact: product-brief
last_validated: null
---

# Pipeline Architecture

<!-- This artifact describes the pipeline's data flow: what comes in, how it's processed, and what goes out. It is the automation equivalent of Information Architecture for UI apps — it defines the system's structure. -->

## Data Sources

<!-- List every external data source the pipeline reads from. For each source, specify: -->
<!-- - Source name and type (RSS feed, API, webhook, file, database, etc.) -->
<!-- - Access method (HTTP GET, webhook listener, file watch, etc.) -->
<!-- - Authentication required (API key, OAuth, none) -->
<!-- - Expected data format (JSON, XML/RSS, CSV, etc.) -->
<!-- - Rate limits or access constraints -->
<!-- - Reliability expectations (always available? intermittent? rate-limited?) -->

## Processing Stages

<!-- Describe each processing stage in data flow order. For each stage: -->
<!-- - Stage name and purpose (one sentence) -->
<!-- - Input: what data this stage receives and from where -->
<!-- - Processing: what transformation, filtering, enrichment, or validation occurs -->
<!-- - Output: what data this stage produces -->
<!-- - Dependencies: external services or libraries this stage requires -->
<!-- - Failure behavior: what happens if this stage fails (see Failure Recovery Spec for details) -->

<!-- Example stages for a typical pipeline: Fetch → Parse → Filter → Enrich → Format → Deliver -->

## Outputs

<!-- List every output the pipeline produces. For each output: -->
<!-- - Destination (Slack channel, email, file, database, API endpoint, etc.) -->
<!-- - Format (message structure, file format, schema) -->
<!-- - Delivery method (webhook, API call, file write, etc.) -->
<!-- - Authentication required -->
<!-- - Success criteria (how to confirm delivery succeeded) -->

## Data Flow Diagram

<!-- A text-based diagram showing the flow from sources through stages to outputs. -->
<!-- Use a simple format like: -->
<!--   [Source A] ──► [Fetch] ──► [Filter] ──► [Format] ──► [Slack] -->
<!--   [Source B] ──┘                                                -->

## Data Retention

<!-- What data is stored between runs, if any? -->
<!-- - Processed article/item deduplication (remember what's been seen) -->
<!-- - Run history and logs -->
<!-- - Intermediate results -->
<!-- - Retention period and cleanup strategy -->

## Pipeline Boundaries

<!-- What this pipeline does NOT do. Explicit boundaries prevent scope creep. -->
