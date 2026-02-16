---
artifact: scheduling-spec
version: 1
depends_on:
  - artifact: pipeline-architecture
  - artifact: nonfunctional-requirements
depended_on_by:
  - artifact: monitoring-alerting-spec
  - artifact: configuration-spec
last_validated: 2026-02-16
---

# Scheduling Specification

<!-- MINIMAL: Event-driven, no scheduling. -->

## Applicability

Prawduct is event-driven — it activates when a user starts an LLM session and provides input. There is no cron schedule, no periodic execution, no background processing.

## Trigger Type

**Event-driven:** User input in an LLM session triggers all framework processing. The "schedule" is whenever the user decides to work on their product.

## Execution Window

A single session. Duration varies from minutes (quick framework change) to hours (full discovery-to-build-plan for a new product). No timeout — the session ends when the user ends it or when context is exhausted.

## Concurrency

Not applicable. One user, one session, one project at a time.

## Periodic Maintenance

The only time-based concern is observation staleness:
- Observations with `status: noted` older than 2 days should be triaged
- Working notes older than 2 weeks should be incorporated into Tier 1 or deleted
- These checks run at session start via `tools/session-health-check.sh`, not on a schedule
