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

<!-- GENERATION GUIDANCE: One clear sentence from product_definition.vision.
     This anchors every downstream artifact — errors here propagate everywhere.
     Source: project-state.yaml → product_definition.vision -->

## Landscape

<!-- What existing solutions address this problem? Why build this despite
     (or because of) what exists? 1-3 sentences for low-risk, short comparison
     for higher-risk. Source: project-state.yaml → classification.prior_art -->

## Identity

<!-- What is this product called? What is its character?
     For products with user-facing surfaces (screens, terminals, voice, APIs):
     style, mood, personality — adapted to the modality. Visual style for
     screen products, interaction personality for CLIs, tone for voice
     interfaces, API design voice for developer-facing products.
     For background systems and automations: name and output formatting style.
     If the user has not expressed identity preferences, state that
     explicitly rather than inventing defaults.
     Source: project-state.yaml → product_definition.product_identity -->

## Users & Personas

<!-- Who uses this product? For each persona, describe:
     - Name and role (e.g., "Family Scorekeeper")
     - Needs and motivations
     - Technical level (none / basic / intermediate / advanced)
     - Constraints (device, accessibility, connectivity)
     Source: project-state.yaml → product_definition.users.personas -->

## Core Flows

<!-- GENERATION GUIDANCE: What users do, in priority order.
     For each flow: name, description, and key steps. Mark must-have or nice-to-have.

     STRUCTURAL ADAPTATION:
     - When runs_unattended: frame as pipeline stages (fetch, filter, format, deliver)
       not user actions.
     - When has_human_interface: frame as user journeys through the interface,
       adapted to modality (screen sequences for screen products, command
       sequences for terminals, interaction sequences for other modalities).
     - When exposes_programmatic_interface: frame as API operations that serve
       consumer use cases.
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
