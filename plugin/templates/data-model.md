<!-- Data Model Template

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
last_validated: null
---

# Data Model

<!-- OPTIONAL norm home. To record a norm, add a `## Direction` heading with entries (a bold
     **Statement.**, then `Why:`, `Status:`, optional `Retroactivity:` / `Rulings:`) — anatomy
     and rules: /prawduct:methodology norms. Add the heading only with a real entry: the
     advisory probes read a bare `## Direction` heading as ratified norms. With no norms, leave
     this comment; "none to ratify" is recorded through /prawduct:doctor, not here. -->

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

## Access Paths

<!-- How the data is read, once there is a lot of it. Include this section only when some
     entity's count grows with users, time or activity; a small fixed set needs none.

     For each entity that grows:
     - Expected volume: an order of magnitude and what it grows with ("~10k transactions
       per account per year", "one record per sensor reading, kept 90 days"). These refine
       the growth the Non-Functional Requirements state under Scalability; keep the two agreed.
     - Read paths: each read that runs often, or while someone waits, and what finds its
       records — the key, index, partition or sort order the store offers. A read with no
       such path walks everything: say so where that is the intent, and what keeps it cheap.
     - Heavy fields: fields large beside the rest of the record (documents, blobs, embedded
       collections), so a read that does not use them can leave them behind.

     Proportionate to risk: a line per entity is enough for a family app. A review judges
     each read against this section; without it, "does this read cost too much?" has no
     answer here.

     Example:
     ### Transaction — ~10k per account per year, kept indefinitely
     | Read                        | Runs            | Found by                         |
     |-----------------------------|-----------------|----------------------------------|
     | Recent activity, one account| every page load | index on (account_id, posted_at) |
     | Search by description       | on user search  | scan, bounded to a date window   |

     Heavy: `raw_payload` (the provider's document, ~4 KB) — list reads name their fields.
-->
