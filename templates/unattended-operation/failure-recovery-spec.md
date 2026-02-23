---
artifact: failure-recovery-spec
version: 1
depends_on:
  - artifact: pipeline-architecture
  - artifact: monitoring-alerting-spec
last_validated: null
---

# Failure Recovery Specification

<!-- Every pipeline stage can fail. This artifact defines what happens when each stage fails, how the system recovers, and what constitutes acceptable degraded behavior. For automations, failure handling is not an edge case — it's a core design concern, per "The Product Includes Its Operations" principle. -->

## Per-Stage Failure Handling

<!-- For each processing stage defined in the Pipeline Architecture, specify: -->
<!-- - Stage name -->
<!-- - Possible failure modes (timeout, bad data, auth failure, rate limit, dependency down) -->
<!-- - Behavior on failure: skip and continue? Retry? Abort the pipeline? Use cached data? -->
<!-- - Impact on downstream stages: does this stage's failure block later stages? -->
<!-- - Recovery action: what is needed to restore normal operation? -->

## Partial Success Behavior

<!-- What happens when some sources/stages succeed and others fail? -->
<!-- - Is partial output delivered (e.g., digest with 8 of 10 sources)? -->
<!-- - Is partial output clearly marked as partial? -->
<!-- - At what threshold does partial become "too degraded to deliver"? -->

## Retry Logic

<!-- For retryable failures: -->
<!-- - Which failures are retryable vs. permanent? -->
<!-- - Retry count and delay strategy (fixed, exponential backoff) -->
<!-- - Maximum retry duration -->
<!-- - What happens after retries are exhausted? -->

## Dead Letter / Failed Item Handling

<!-- When individual items fail processing: -->
<!-- - Are they logged for later inspection? -->
<!-- - Are they retried separately from the pipeline run? -->
<!-- - Is there a dead letter queue or equivalent? -->
<!-- - Proportionate: a side project may just log and skip; a critical pipeline needs dead letter queues. -->

## Data Integrity on Failure

<!-- If the pipeline fails mid-run: -->
<!-- - Is output idempotent (safe to re-run without duplicates)? -->
<!-- - Is there a risk of partial/duplicate output? -->
<!-- - How is state cleaned up after a failed run? -->

## Recovery Procedures

<!-- For the operator (likely the developer themselves for a side project): -->
<!-- - How to diagnose a failure (what to check first) -->
<!-- - How to manually re-run after fixing the issue -->
<!-- - How to verify recovery was successful -->
