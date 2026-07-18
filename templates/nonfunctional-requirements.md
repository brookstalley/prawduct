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
last_validated: null
---

# Non-Functional Requirements

<!-- OPTIONAL norm home ("Direction"). To record a norm, add a `## Direction` heading here with
     entries — each: a bold **Statement.**, then `Why:` (required), `Status:` (steady-state |
     in-transition + its tracking item), and optional `Retroactivity:` / `Rulings:` lines.
     Normative statements BIND future work — not descriptions of current behavior. Norms bind;
     descriptions track — see /prawduct:methodology norms for the anatomy, the
     normative-vs-descriptive test, and the lifecycle rules. Add the heading ONLY with a real
     entry: a bare `## Direction` heading reads as ratified norms to the advisory probes. A
     product with no norms to declare leaves this comment as-is — "none to ratify" is recorded
     owner-confirmed through the doctor's Norm Ratification Flow (/prawduct:doctor), never as a
     side effect of authoring this artifact. Don't restate the rules here. -->

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
