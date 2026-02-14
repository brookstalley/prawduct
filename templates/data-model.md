<!-- Data Model Template
     Tier: 1 (Source of Truth)
     Owner: Artifact Generator (C3)

     Usage: Copy this template to your project's artifacts/ directory.
     Derive entities from the core flows and personas in the Product Brief.
     Every entity the user talked about must appear here. If the Product Brief
     mentions "scores," there must be a Score entity (or equivalent).
-->
---
artifact: data-model
version: 1
depends_on:
  - artifact: product-brief
depended_on_by:
  - artifact: test-specifications
  - artifact: security-model
last_validated: null
---

# Data Model

## Entities

<!-- GENERATION GUIDANCE: Derive entities from the Product Brief's core flows and personas.
     Every noun the user cares about should map to an entity here.

     For each entity, define:
     - Name
     - Fields with types and constraints (required, unique, default, etc.)
     - Purpose: what this entity represents and why it exists

     EXPERIENCE-CRITICAL PARAMETERS: If an entity has fields whose values directly
     shape the user experience (visual layout proportions, timing intervals, difficulty
     curves, animation speeds), those values must be specified as concrete fields with
     constraints and defaults — not left as implementation details. Test: could two
     Builders implement this data model and produce noticeably different UX? If so,
     the divergence points need explicit specification.

     Example format:
     ### EntityName
     | Field       | Type    | Constraints          | Description            |
     |-------------|---------|----------------------|------------------------|
     | id          | UUID    | PK, auto-generated   | Unique identifier      |
     | name        | string  | required, max 100    | Display name           |
     | created_at  | datetime| auto-set             | Creation timestamp     |
-->

## Relationships

<!-- How entities relate to each other.
     Specify cardinality: one-to-one, one-to-many, many-to-many.
     Include join entities for many-to-many relationships if needed.

     Example: "A Game has many Sessions (one-to-many). A Session has many Scores
     (one-to-many). A Player can participate in many Sessions (many-to-many,
     via Score)." -->

## State Machines

<!-- If any entity has lifecycle states, document the valid transitions.
     Only include this section if entities have meaningful state changes.

     Example:
     ### GameSession States
     - setup → in-progress (when first score is recorded)
     - in-progress → completed (when host ends game)
     - completed is terminal (no transitions out)
-->

## Constraints

<!-- Validation rules, business rules, and invariants that span entities.
     Examples: "A score must be non-negative," "A game session must have
     at least 2 players," "Player names must be unique within a game." -->
