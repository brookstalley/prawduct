<!-- Non-Functional Requirements Template
     Tier: 1 (Source of Truth)
     Owner: Artifact Generator (C3)

     Usage: Copy this template to your project's artifacts/ directory.
     NFRs must be proportionate to the product's risk profile.
     For a low-risk family utility, this should fit on half a page.
     If you're writing about load balancers and CDNs for a family score
     tracker, recalibrate.
-->
---
artifact: nonfunctional-requirements
version: 1
depends_on:
  - artifact: product-brief
depended_on_by:
  - artifact: operational-spec
  - artifact: dependency-manifest
last_validated: null
---

# Non-Functional Requirements

## Performance

<!-- Response times, throughput, or processing targets.
     Proportionate to risk:
     - Low-risk: "Pages load in under 2 seconds" is fine.
     - High-risk: Specify p50/p99 latencies, throughput under load.
     Source: project-state.yaml → product_definition.nonfunctional.performance -->

## Scalability

<!-- Expected user count and data growth over time.
     Be honest: a family app serving 4-10 users doesn't need horizontal scaling.
     State the expected scale and what growth would require architectural changes.
     Source: project-state.yaml → product_definition.nonfunctional.scalability -->

## Availability

<!-- Uptime target and what "down" means for this product.
     Proportionate to risk:
     - Low-risk: "Best-effort" or "should work when the family wants to play"
     - Medium-risk: "99% uptime during business hours"
     - High-risk: "99.9% with defined SLA and incident response"
     Source: project-state.yaml → product_definition.nonfunctional.uptime -->

## Cost Constraints

<!-- Budget for hosting, external services, and APIs.
     Surface this even if the answer is "as cheap as possible" or "free tier only."
     Include ongoing operational costs, not just initial setup.
     Source: project-state.yaml → product_definition.nonfunctional.cost_constraints -->
