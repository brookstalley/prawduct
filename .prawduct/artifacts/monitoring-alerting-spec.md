---
artifact: monitoring-alerting-spec
version: 1
depends_on:
  - artifact: pipeline-architecture
  - artifact: scheduling-spec
  - artifact: nonfunctional-requirements
depended_on_by:
  - artifact: failure-recovery-spec
last_validated: 2026-02-16
---

# Monitoring & Alerting Specification

<!-- sourced: docs/self-improvement-architecture.md § Failure Modes, 2026-02-16 -->

Prawduct's monitoring system is `tools/session-health-check.sh` — it runs at session start and checks infrastructure health, observation patterns, and project state.

## Health Metrics

| Metric | What It Measures | Expected Range | Collection |
|--------|-----------------|----------------|------------|
| Active observation count | Unarchived observation files | < 30 files | File count in framework-observations/ (excluding archive/) |
| Noted observation age | Days since oldest `status: noted` observation | < 2 days | Parsed from observation YAML |
| Triage recency | Days since last_triage in observation_backlog | < 7 days | Read from project-state.yaml |
| Working notes freshness | Age of files in working-notes/ | < 14 days | File modification time |
| Skill file length | Lines in each SKILL.md | Per H1 thresholds (SKILL.md: 400/600, sub-files: 300) | wc -l |
| Deprecated term references | Surviving references to removed vocabulary | 0 | grep for patterns from deprecated_terms |
| Source-artifact divergence | Source commits since last artifact update | < 10 commits | git log comparison |
| Archive backlog | Resolved observations not yet archived | 0 | Status check in observation files |

## Failure Detection

| Failure Type | Detection Method | Severity |
|--------------|-----------------|----------|
| Observation accumulation | Active count > 30 | warning |
| Stale noted observations | Age > 2 days without triage | warning |
| Working notes expired | Age > 14 days | note |
| Skill file over-length | Lines > H1 threshold + 25% | warning |
| Deprecated term survival | Any match found | warning |
| Source-artifact divergence | > 10 commits since last .prawduct/ update | warning |
| Missing governance state | .session-governance.json absent during active build | blocking |
| PFR diagnosis missing | Governance-sensitive files edited without `pfr_state.diagnosis_written: true` in .session-governance.json | blocking |
| PFR observation missing | Governance-sensitive files edited but `pfr_state.observation_file` not set or file doesn't exist | blocking |

## Alerting

All alerts are surfaced during session resumption — there is no background alerting, no email, no Slack. The session health check output is presented to the user by the Orchestrator during Session Resumption step 2.

**Action model:** Patterns are presented with concrete recommendations. User decides act-now or defer. Deferred patterns are not re-presented unless new observations accumulate.

## Logging

- **change_log:** Append-only record of all framework changes with what, why, blast radius, classification, date
- **Observation files:** Structured YAML records of framework behavior findings
- **Evaluation results:** Per-scenario scoring with evidence, in eval-history/
- **Git history:** Complete version history of all framework files

## Distinguishing "No Data" from "Failure"

- **No observations generated:** If session-health-check finds zero active observations and no recent change_log entries, this may indicate the observation system is not being invoked. Flag as warning (Failure Mode 1 from self-improvement-architecture.md).
- **No patterns detected:** Normal when observation volume is low. Not a failure — the tiered threshold system requires multiple occurrences before surfacing patterns (Learn Slowly principle).
- **No infrastructure issues:** Ideal state. Health check reports "all clear" and session continues normally.
