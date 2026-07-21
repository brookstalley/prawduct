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

## Property-Based Tests

<!-- Include this section when the domain involves mathematical operations,
     data transformations, serialization/deserialization round-trips, parsing,
     stateful protocols, or complex input validation. Property-based tests
     complement example-based tests by verifying that invariants hold across
     many automatically generated inputs, catching edge cases that hand-picked
     examples miss.

     Skip this section when the product is purely CRUD, UI-driven, or has no
     transformation logic where invariants apply.

     Common property types:

     **Round-trip fidelity** — Convert A→B→A and verify the result matches
     (within tolerance for lossy transformations). Applies to: serialization,
     encoding, format conversion, compression.

     **Invariant preservation** — After a transformation, some property of the
     data must still hold. Applies to: sorting (output is same length, same
     elements), filtering (output is subset), mathematical operations
     (result within valid range).

     **Equivalence** — Two implementations or paths produce the same result.
     Applies to: optimized vs. reference implementation, cached vs. computed,
     batch vs. single-item processing.

     Use the following format for each property:

     **Property: [invariant name]**
     - Strategy: [what inputs to generate, what property to verify]
     - Example: [one concrete instance demonstrating the property]
     - Library: [hypothesis, proptest, fast-check, etc. — match project-preferences] -->

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

## Product Verification Scenarios

<!-- Define what to observe in the RUNNING product beyond what automated tests
     cover, and what "correct" looks like. Scale to chunk significance and
     structural characteristics — not every product needs elaborate scenarios.

     Product verification catches issues that unit/integration/E2E tests miss:
     visual correctness, interaction feel, accessibility in practice, timing
     and animation, cross-browser/cross-platform rendering, actual API responses.

     Each scenario specifies what to observe and what "correct" looks like:

     **Scenario: [what to verify]**
     - Setup: [product running state needed]
     - Observe: [what to look at, call, or drive]
     - Correct: [what the output should look like or how it should behave]
     - Incorrect: [what would indicate a problem]

     For simple products, this may be a few lines. For products with human
     interfaces or complex integrations, be more specific. -->

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
