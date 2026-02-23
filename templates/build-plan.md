<!-- Build Plan Template
     Tier: 1 (Source of Truth)
     Owner: Artifact Generator (C3)

     This artifact translates abstract technical decisions and artifact specifications
     into concrete, executable build instructions. It is the bridge between "what to build"
     (artifacts) and "how to build it" (Builder execution).

     The build plan must be specific enough that the Builder can execute without making
     technology decisions. If the Builder would need to guess, the build plan is underspecified.

     Generated during Stage 4 (Build Planning) by Artifact Generator Phase D.
     Consumed during Stage 5 (Building) by the Builder skill.
-->
---
artifact: build-plan
version: 1
depends_on:
  - artifact: product-brief
  - artifact: data-model
  - artifact: test-specifications
  - artifact: dependency-manifest
  - artifact: operational-spec
last_validated: null
---

## Scaffolding

<!--
  Exact commands to initialize the project. This is where abstract technology decisions
  (e.g., "React + Vite") become concrete instructions (e.g., "run npm create vite@latest").

  Include:
  - Project initialization command(s)
  - Dependency installation (list every package from dependency-manifest)
  - Build tool configuration
  - Test runner setup
  - Verification: what commands prove the scaffold works (e.g., "npm run dev starts without errors")
-->

### Project Initialization

[Exact commands to create the project]

### Dependencies

[Exact npm install / pip install / etc. commands, listing every package]

### Build & Test Configuration

<!--
  Test infrastructure must match the test strategy in test-specifications.md.
  The Builder must be able to run "test this level" and "test everything" without
  making decisions about where files live or how runners are configured.

  Include:
  - Test directory structure: where each level's test files live. Low-risk
    products can use a single test directory; medium/high-risk should separate
    unit, integration, and e2e directories.
  - Test runner configuration per level: how to run unit tests alone, integration
    tests alone, e2e tests alone, and all together.
  - Mock/stub library setup: when the test strategy calls for mocking external
    services, configure the mock library here.
  - Coverage tool setup: always configure coverage measurement. Low-risk products
    measure without enforcing thresholds. Medium/high-risk products set coverage
    targets from NFRs.
-->

[Configuration files to create or modify, with their contents]

### Scaffold Verification

[Commands to run that prove the scaffold is working: build succeeds, dev server starts, test runner executes]

### Verification Strategy

<!--
  Every product needs a verification approach — how the builder confirms the
  product works beyond tests, by exercising it as users or consumers would.

  The approach depends on structural characteristics and what tools are available.
  Describe the strategy. For simple products, this may be one line ("run the
  binary and check output"). For products with human interfaces, it may involve
  screenshots, browser automation, or MCP tools. For APIs, contract tests or
  direct calls. For pipelines, output inspection.

  Keep it proportionate. Don't build elaborate verification infrastructure for
  a personal utility.

  All verification infrastructure is development-only (Principle #9).
-->

[How the builder verifies the product works beyond tests. Describe the approach, scaled to product complexity.]

## Project Structure

<!--
  Directory layout and file naming conventions. Derived from the data model
  and structural characteristics. The Builder follows this structure exactly.
-->

```
[project-root]/
├── [directory structure here]
```

### Module Boundaries

[Which directories/modules own which concerns. The Builder must not cross these boundaries.]

## Build Chunks

<!--
  Ordered list of build tasks. Each chunk delivers one piece of functionality.
  For UI apps, prefer feature-first: each chunk delivers one user-visible flow end-to-end.

  Chunk ordering:
  1. Scaffold (always first)
  2. Core data entities
  3. Feature chunks by user value (highest value first)
  4. Polish (last)

  Each chunk must specify:
  - What to build (description + deliverables)
  - What artifacts to read (which specs govern this chunk)
  - What tests to write (mapped from test-specifications)
  - Acceptance criteria (concrete, verifiable)
  - Dependencies (which chunks must complete first)
-->

### Chunk 01: [Name]

- **Description:** [What this chunk delivers]
- **Depends on:** [chunk IDs, or "none" for scaffold]
- **Artifacts consumed:** [Which artifact files the Builder reads for this chunk]
- **Deliverables:** [Specific files or components produced]
- **Tests:** [Test scenarios from test-specifications that apply to this chunk]
  <!-- For medium/high-risk products, note which test levels this chunk introduces
       or extends (e.g., "adds unit tests for scoring logic, integration test for
       DB persistence, extends E2E test for full score flow"). -->
- **Acceptance criteria:** [Concrete checks — "npm test passes", "page renders scores", etc.]

<!-- Repeat for each chunk -->

## Early Feedback Milestone

<!--
  Identify the first chunk where the user can interact with the product.
  This should be no later than chunk 3 for most products.
-->

**Milestone chunk:** [chunk ID]
**What the user can do:** [Description of the interactive experience at this point]

## Governance Checkpoints

<!--
  When the Critic runs a full cross-chunk review (not just per-chunk review).
  Typically: after the early feedback milestone and after all chunks complete.
-->

- After chunk [ID]: [Review type and rationale]
