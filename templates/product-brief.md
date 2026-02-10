<!-- Product Brief Template
     Tier: 1 (Source of Truth)
     Owner: Artifact Generator (C3)

     Usage: Copy this template to your project's artifacts/ directory.
     Populate from project-state.yaml → product_definition and classification.
     This is typically the first artifact generated and the one most other
     artifacts depend on. Keep it proportionate to the product's risk level:
     ~1-2 pages for a low-risk utility, longer for complex platforms.
-->
---
artifact: product-brief
version: 1
depends_on:
  - artifact: project-state
    section: product-definition
depended_on_by:
  - artifact: data-model
  - artifact: security-model
  - artifact: test-specifications
last_validated: null
---

# Product Brief

## Vision

<!-- One clear sentence: what this product is and why it exists.
     Source: project-state.yaml → product_definition.vision -->

## Users & Personas

<!-- Who uses this product? For each persona, describe:
     - Name and role (e.g., "Family Scorekeeper")
     - Needs and motivations
     - Technical level (none / basic / intermediate / advanced)
     - Constraints (device, accessibility, connectivity)
     Source: project-state.yaml → product_definition.users.personas -->

## Core Flows

<!-- What do users actually do, in priority order?
     For each flow: name, description, and key steps.
     Mark each as must-have or nice-to-have.
     Source: project-state.yaml → product_definition.core_flows -->

## Success Criteria

<!-- How do we know this product worked? List concrete, evaluable statements.
     Source: project-state.yaml → product_definition.goals -->

## Scope

<!-- What's in, what's out, and why.
     - v1: Must have for initial release
     - Accommodate: Design for but don't build yet
     - Later: Genuinely deferred
     - Out of scope: Explicitly excluded, with rationale
     Source: project-state.yaml → product_definition.scope -->

## Platform

<!-- Where does this run? (web, mobile, desktop, CLI, etc.)
     Source: project-state.yaml → product_definition.platform -->
