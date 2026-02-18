<!-- Test Specifications Template
     Tier: 1 (Source of Truth)
     Owner: Artifact Generator (C3)

     Usage: Copy this template to your project's artifacts/ directory.
     Test scenarios must be specific and concrete, not generic.
     Bad:  "Test that scoring works."
     Good: "Test recording a score of 47 for Player 'Alice' in a game of
            Catan with 3 players. Verify the score appears in the game session,
            the player's history updates, and the leaderboard recalculates."

     Each test specifies: setup (preconditions), action (what happens),
     expected result (what should be true afterward).
-->
---
artifact: test-specifications
version: 1
depends_on:
  - artifact: product-brief
  - artifact: data-model
  - artifact: security-model
depended_on_by:
  - artifact: operational-spec
last_validated: null
---

# Test Specifications

## Test Strategy

<!-- This section is generated before per-flow tests. It establishes the testing
     approach for the product — what levels of testing exist, how they're isolated,
     and how coverage is measured.

     ALL products with programmatic features get multi-level testing. This is the
     testing floor — proportionality scales depth and sophistication, not whether
     a level exists.

     **Testing floor (all products):**
     - Unit tests for core logic and business rules (mock external dependencies)
     - Integration tests for data persistence and service boundaries
     - At least one E2E test per core flow (proves the system works end-to-end)
     - Coverage measurement configured

     **Low-risk:** Concise strategy. Lightweight infrastructure (single test
     directory is fine, simple mocking). Coverage measured but no enforced
     thresholds. Performance tests only if NFRs specify quantified targets.

     **Medium-risk:** Explicit strategy covering test levels, isolation approach,
     mocking boundaries, and coverage targets (from NFRs). Performance tests for
     quantified NFR targets.

     **High-risk:** Detailed strategy covering all levels, isolation and data
     management, mocking boundaries, coverage targets, performance and load
     approach, and contract testing where applicable.

     Mocking principles: Mock external dependencies at integration boundaries.
     Never mock the thing being tested — a mocked database doesn't test persistence.

     Test isolation: Every test is independent. Each creates its own test data.
     No shared mutable state. No execution-order dependencies. -->

<!-- Organize tests by core flow from the Product Brief.
     For each flow, include happy path, error cases, and edge cases.
     For entities with lifecycle states (from Data Model), test each valid
     transition AND at least one invalid transition.

     Use the following format for each test.
     Each test carries a Level annotation (unit, integration, or e2e) that tells
     the Builder which test runner and directory to target:

     **Test: [descriptive name]**
     - Level: unit | integration | e2e
     - Setup: [preconditions]
     - Action: [what happens]
     - Expected: [observable outcomes] -->

## Flow: [Flow Name from Product Brief]

<!-- Repeat this section for each core flow. -->

### Happy Path

<!-- The normal, expected flow works end to end.

     **Test: [descriptive name]**
     - Setup: [preconditions — what state must exist before the test]
     - Action: [what the user or system does]
     - Expected: [what should happen — specific, observable outcomes] -->

### Error Cases

<!-- What happens when things go wrong?
     Cover: invalid input, missing data, network failure (if applicable),
     unauthorized access (per Security Model).

     **Test: [descriptive name]**
     - Setup: [preconditions]
     - Action: [the erroneous action]
     - Expected: [how the system should respond — error message, graceful handling] -->

### Edge Cases

<!-- Boundary conditions, empty states, maximum values.
     Examples: first-ever use (no data), maximum number of items,
     special characters in input, concurrent actions (if applicable).

     **Test: [descriptive name]**
     - Setup: [preconditions]
     - Action: [the boundary action]
     - Expected: [correct behavior at the boundary] -->

## State Transition Tests

<!-- Only include if the Data Model defines state machines.
     For each state machine, test every valid transition and at least one
     invalid transition.

     **Test: [Entity] [StartState] → [EndState]**
     - Setup: [entity in StartState]
     - Action: [trigger for transition]
     - Expected: [entity is now in EndState, side effects occurred]

     **Test: [Entity] invalid transition [StartState] → [InvalidState]**
     - Setup: [entity in StartState]
     - Action: [attempt invalid transition]
     - Expected: [transition rejected, entity remains in StartState] -->

## Performance & Non-Functional Tests

<!-- Include this section when NFRs specify quantified performance targets
     (response time, throughput, resource limits). Low-risk products without
     quantified NFR targets can omit this section entirely.

     Use the same Setup/Action/Expected format. Each test maps to a specific
     NFR target.

     **Test: [NFR target description]**
     - Level: integration | e2e
     - Setup: [system state, data volume, load conditions]
     - Action: [the operation under measurement]
     - Expected: [quantified target — e.g., "completes in < 200ms",
       "handles 100 concurrent requests", "memory stays under 256MB"] -->
