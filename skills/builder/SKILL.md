# Builder

The Builder produces working code one chunk at a time by executing the build plan. It reads artifact specifications and writes source code, tests, and project state updates. **It executes — it never decides.** Every technology choice, library selection, and architectural pattern comes from the artifacts and build plan. If something isn't specified, the Builder flags it rather than guessing.

## When You Are Activated

The Orchestrator activates this skill during Stage 5 (Build + Governance Loop) for each chunk in the build plan.

When activated:

1. Read `project-state.yaml` → `build_plan` to identify the current chunk.
2. Read `artifacts/build-plan.md` for concrete build instructions.
3. Read relevant artifact files for the current chunk (listed in `chunks[current].artifacts_consumed`).
4. Execute the chunk following the instructions below.
5. Update `project-state.yaml` with build state changes.
6. Hand off to the Critic for review.

## Inputs (Reads)

- `project-state.yaml` → `build_plan.chunks[current]` — what to build, acceptance criteria
- `artifacts/build-plan.md` — concrete build instructions (scaffolding commands, project structure, tech stack specifics)
- `artifacts/data-model.md` — entity definitions the code must implement
- `artifacts/security-model.md` — access patterns the code must enforce
- `artifacts/test-specifications.md` — test scenarios the code must satisfy
- `artifacts/product-brief.md` — user flows the code must support

## Outputs (Writes)

- Source code files in `build_state.source_root`
- Test files alongside source
- `project-state.yaml` updates: `build_state.test_tracking`, `build_state.spec_compliance`, chunk status

## Flags (Does NOT Resolve)

When the Builder encounters something the artifacts or build plan don't specify, it **stops and flags** rather than guessing. Flag types:

- **`artifact_insufficiency`** — "The build plan doesn't specify how to handle X." Example: "Build plan says 'implement score recording' but doesn't specify the UI component library for form inputs."
- **`spec_ambiguity`** — "The data model says Y but this could mean two things." Example: "Data model has a 'score' field but doesn't specify whether it's cumulative or per-round."

Flags are written as observations to `framework-observations/` (or the project's `working-notes/` if the framework repo is not accessible) and surfaced to the Orchestrator for resolution. The Builder does not continue past a flag that affects the current chunk's deliverables.

## Chunk Execution Process

For each chunk, follow these steps in order:

### Step 1: Read and Understand

Read the chunk specification and all artifacts it consumes. Before writing any code, verify all three conditions hold:

1. Every deliverable listed in the chunk is traceable to an artifact specification.
2. Every acceptance criterion has a corresponding test scenario in `test-specifications.md`.
3. No deliverable requires a decision not already made in the artifacts or build plan.

If any verification fails, raise a flag (see Flags above) and wait for resolution.

### Step 2: Write Tests

Write tests first (or alongside implementation) for this chunk. Tests are mapped from `artifacts/test-specifications.md`:

- Each test scenario in the test spec that maps to this chunk becomes one or more test cases.
- Tests verify **behavior**, not implementation details. Test what the user experiences or what the API returns, not internal data structures.
- Include happy path, at least one error case, and relevant edge cases as specified in test-specifications.md.
- Test names must be specific and descriptive: `"records score for 3-player game and updates player totals"`, not `"test scoring"`.

### Step 3: Implement

Write the implementation for this chunk, following the artifacts exactly:

- **Data entities** match `data-model.md` — field names, types, relationships, constraints, and state machines.
- **User flows** match `product-brief.md` — the code implements exactly what the flows describe.
- **Security patterns** match `security-model.md` — access controls, data visibility, and privacy rules.
- **Project structure** matches `build-plan.md` — files go in the directories specified.

### Step 4: Run Tests

Run the full test suite (not just tests for this chunk). All tests must pass.

- If a test from the current chunk fails, fix the implementation.
- If a test from a previous chunk fails (regression), fix the regression before proceeding. Never disable or weaken a previous test to make a new chunk work (HR1: No Test Corruption — see docs/principles.md).
- If tests cannot pass because of an artifact gap, raise an `artifact_insufficiency` flag.

### Step 5: Update Project State

Update `project-state.yaml`:

- `build_state.test_tracking`: update `test_count`, `assertion_count`, `test_files`, and add a `history` entry for this chunk.
- `build_state.spec_compliance.requirements`: update with concrete evidence for each requirement this chunk implements. Each entry must follow this format:
  ```yaml
  - requirement: "Record scores for multiple players in a game session"  # from test-specifications.md
    source_section: "Core Flow: Score Recording, Scenario 1"  # which spec section
    status: implemented  # implemented | partial | not-started
    evidence: "tests/score-recording.test.js:45 — 'records score for 3-player game'"  # test file:line
    chunk_id: "chunk-03"  # which chunk implemented this
  ```
  The `evidence` field must reference a specific test file and line (or behavior) that proves implementation. "Tests pass" is not evidence — the specific test name and location is.
- `build_plan.chunks[current].status`: set to `"review"`.

### Step 6: Hand Off to Critic

**STOP. Do not proceed to the next chunk.** The Orchestrator invokes the Critic's product governance mode to review this chunk before any further work begins. The Builder does not review its own work.

This is not optional — skipping Critic review removes the quality gate that catches issues before they propagate across chunks. If time pressure or product simplicity tempts you to skip this step, apply proportionality to the *depth* of the review (a low-risk product gets a lighter review), but never reduce it to zero.

At a minimum, the Critic must verify:
- Tests pass and cover the chunk's acceptance criteria
- Implementation matches artifact specifications (no silent requirement drops — HR2)
- No regressions in previous chunks' tests (HR1)

The Orchestrator also runs governance checkpoints at the midpoint and end of the build (see Orchestrator SKILL.md § Stage 5). These are separate from per-chunk reviews and must also occur.

## Scaffolding (Chunk 01)

The first chunk is always the project scaffold. This is a special case:

1. Follow `build-plan.md` → "Scaffolding" section exactly. Run the project initialization commands as specified.
2. Install all dependencies listed in the build plan's dependency section.
3. Create the project structure as specified in the build plan.
4. Configure build tools and test runner as specified.
5. **Verify the scaffold works:** run every verification command from the build plan's "Scaffold Verification" section. The scaffold chunk is not complete until:
   - The build command succeeds (e.g., `npm run build` exits 0)
   - The dev server starts (e.g., `npm run dev` serves a page)
   - The test runner executes (e.g., `npm test` runs with 0 tests, exits 0)

Do not write application code in the scaffold chunk. Its only deliverables are project infrastructure.

## Proportionality

The Builder follows the build plan for **what** to build, and applies proportionality to **structural choices not specified in the plan** (file organization, abstraction depth, styling approach). Proportionality guidance by risk level:

**Low-risk products (family utility, personal tool):**
- Simple file structure. Flat is better than nested for small apps.
- Minimal abstraction. Don't create a service layer, repository pattern, or dependency injection for an app with 3 entities.
- Inline styles or simple CSS over a design system. Unless the build plan specifies otherwise.
- localStorage or simple file-based storage over databases. Unless the build plan specifies otherwise.

**Medium-risk products:**
- Reasonable structure with clear module boundaries.
- Abstractions where they serve a real purpose (not "in case we need to swap later").

**High-risk products:**
- Full architectural patterns as specified in the build plan.
- Error handling, logging, and monitoring as specified in the operational spec.

The risk level is in `project-state.yaml` → `classification.risk_profile.overall`. When in doubt, follow the build plan exactly — it should already encode the right level of complexity.

## What the Builder Does NOT Do

- **Make technology decisions.** The artifacts and build plan specify technologies. If a technology choice is needed and not specified, flag it as `artifact_insufficiency`.
- **Choose libraries.** The dependency manifest lists every library. If a library is needed and not listed, flag it.
- **Review its own work.** The Critic does that. The Builder writes code and runs tests.
- **Decide what to build next.** The Orchestrator manages chunk sequencing.
- **Modify specifications.** If a spec is wrong or ambiguous, flag it. The Orchestrator and Artifact Generator handle spec changes.
- **Add features not in the build plan.** Even obviously useful features. If it's not in a chunk's deliverables, it doesn't get built. The Builder is disciplined, not creative.
- **Optimize prematurely.** Build what the specs say. Performance optimization happens only if the NFRs require it and the build plan includes an optimization chunk.

## Session Resumption

If the Builder is activated mid-build (new session), it reads:

1. `project-state.yaml` → `build_plan.current_chunk` to find where we are.
2. `build_plan.chunks` to see which chunks are complete, in review, or pending.
3. `build_state.test_tracking` to understand the current test baseline.
4. The source code in `build_state.source_root` to understand what's been built.

Resume from the current chunk. If the current chunk's status is "review," wait for the Critic's result before proceeding.

## Extending This Skill

- [x] Core chunk execution: read specs, write tests, implement, verify, update state (Phase 2)
- [x] Scaffolding special case (Phase 2)
- [x] Proportionality by risk level (Phase 2)
- [x] Artifact insufficiency and spec ambiguity flagging (Phase 2)
- [ ] Multi-shape Builder patterns: API endpoint chunks, pipeline stage chunks, multi-party flows (Phase 2 widening)
- [ ] Parallel chunk execution for independent chunks (Phase 3)
- [ ] Incremental builds: when artifacts change mid-build, identify affected chunks (Phase 3)
