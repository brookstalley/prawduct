<!-- Operational Specification Template
     Tier: 1 (Source of Truth)
     Owner: Artifact Generator (C3)

     Usage: Copy this template to your project's artifacts/ directory.
     Covers how the product runs in production: deployment, backup,
     monitoring, and failure recovery. Proportionate to risk — a simple
     app gets a simple ops story.
-->
---
artifact: operational-spec
version: 1
depends_on:
  - artifact: nonfunctional-requirements
  - artifact: security-model
depended_on_by:
  - artifact: dependency-manifest
last_validated: null
---

# Operational Specification

## Deployment

<!-- How and where the product is deployed.
     Proportionate to risk:
     - Low-risk: single deployment target, simple process (e.g., "deploy to
       Vercel via git push" or "build and install on home server")
     - High-risk: staging environments, blue-green deploys, rollback procedures
     Source: project-state.yaml → technical_decisions.operational -->

## Backup & Recovery

<!-- How data is backed up and how to restore from backup.
     Even a low-risk family app should have basic backup.
     Proportionate to risk:
     - Low-risk: "SQLite file backed up daily to cloud storage"
     - High-risk: point-in-time recovery, RTO/RPO targets, tested restore procedures -->

## Monitoring

<!-- What to watch to know the product is healthy.
     Proportionate to risk:
     - Low-risk: "Is the app responding?" (basic health check)
     - High-risk: application metrics, error rates, latency percentiles,
       business metrics, alerting thresholds -->

## Failure Recovery

<!-- What happens when things break, and how to fix them.
     Proportionate to risk:
     - Low-risk: "Restart it." Seriously — if the blast radius is small,
       simple recovery is the right answer.
     - High-risk: runbooks, escalation procedures, failover, incident response -->
