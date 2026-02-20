# Orchestrator: Stage 5 (Build + Governance Loop)

---

## Stage 5: Build + Governance Loop

**Trigger:** `current_stage` is "building".

**What to do:**

Read `skills/builder/SKILL.md`. The Critic is invoked as a separate agent — you do not need to load `agents/critic/SKILL.md` into your context.

### Per-chunk execution

For each chunk in `build_plan.chunks` (in dependency order), execute this 7-step cycle:

1. **Brief the user.** Low-risk: brief summary ("Building score recording..."). High-risk: more detail ("Building the payment processing module. This chunk covers [X]."). Never pause between chunks to ask permission. The user confirmed their intent when they described the product — execute the build plan. Only stop if a flag is raised (artifact_insufficiency, spec_ambiguity) or a governance checkpoint surfaces blocking findings.

2. **Set chunk status.** Update `build_plan.current_chunk` and the chunk's status to "in_progress".

3. **Invoke the Builder.** Load `skills/builder/SKILL.md` and execute the chunk. The Builder reads the chunk spec and relevant artifacts, writes tests and implementation, runs all tests, updates `build_state` in project-state.yaml, and sets chunk status to "review".

4. **Handle Builder flags.** If the Builder raises `artifact_insufficiency` or `spec_ambiguity`:
   - Assess whether the flag can be resolved by reading existing artifacts more carefully (sometimes it can).
   - If the gap is real: update the relevant artifact, note the change in `change_log`, and write an observation to `framework-observations/`. Then let the Builder continue.
   - If the gap requires a user decision: ask the user, update artifacts, continue.

5. **Invoke the Critic agent.** Spawn a Critic review agent per the Critic Agent Protocol in `skills/orchestrator/protocols.md`. The agent runs in a separate context — it reads `agents/critic/SKILL.md` itself and hasn't seen the Builder's reasoning. Include in the prompt: project paths, current stage, files changed in this chunk, chunk summary, any accepted tradeoffs, and whether this chunk modified shared types or modules used by other chunks (so the Critic can verify cross-chunk regression was checked). Verify the agent's output per the protocol's verification steps.

6. **Handle Critic findings.**
   - **Blocking findings:** Before the Builder fixes a blocking finding, apply PFR steps 1-2 (classify + RCA) from `skills/orchestrator/protocols.md` § PFR. If framework-relevant, the RCA informs the fix — the Builder targets the root cause, not just the symptom. After the fix, apply PFR steps 4-6 (meta-fix across the product, capture framework observation, present contribution pathway). The Critic re-reviews. Repeat until clear. Watch for fix-by-fudging (the Critic checks for this).
   - **Warnings:** Note them. The Builder addresses warnings that are quick to fix. Others are tracked in `build_state.reviews` for later.
   - **Clear:** Chunk status → "complete". Proceed to next chunk.
   - **Update governance tracking:** After Critic review, update `.prawduct/.session-governance.json` → `governance_state.chunks_completed_without_review` to 0 and set `last_critic_review_chunk` to the reviewed chunk name. (The PostToolUse hook also derives this mechanically from project-state.yaml, but explicit updates ensure consistency.)

7. **Lightweight reflection.**
   - Were the artifact specs sufficient for this chunk? If not, that's an `artifact_insufficiency` observation.
   - Did the Critic catch real issues or produce noise? That informs Critic calibration.
   - If PFR was applied during this chunk (step 6 blocking finding fixes), verify observations were captured.
   - **Framework friction check:** Did the governance system itself cause friction this chunk? If a governance hook blocked an action that required manual intervention, if Bash was used to work around a governance gate, or if a governance tool failed or produced incorrect results, capture a framework observation with type `process_friction`. Governance friction that goes uncaptured cannot be fixed.
   - After capturing any observations, increment `.prawduct/.session-governance.json` → `governance_state.observations_captured_this_session`.

### Governance checkpoints

At points marked in `build_plan.governance_checkpoints`, run a broader cross-chunk review:

1. Are the completed chunks cohering into a working product?
2. Invoke the Review Lenses agent per the Review Lenses Agent Protocol in `skills/orchestrator/protocols.md`, requesting Architecture, Skeptic, and Testing lenses on the implementation so far. (Testing Lens verifies implemented tests match specs and no coverage gaps have emerged.)
3. If issues found, address before continuing.

### Build pacing

| Risk | Chunk briefings | User interaction | Checkpoint depth |
|------|----------------|-----------------|-----------------|
| Low | Brief summaries | Don't pause between chunks | Lightweight (but not zero) |
| Medium | Per-chunk summaries | Don't pause between chunks | Moderate |
| High | Detailed briefings | Pause only if governance checkpoint has blocking findings | Thorough |

"Lightweight" means the Critic review is shorter and focuses on the minimum checks (tests pass, specs matched, no regressions) — it does **not** mean the Critic is skipped. Every chunk gets a Critic review. Every governance checkpoint gets a cross-chunk review. Zero review is never appropriate regardless of risk level.

### Build completion

When all chunks are complete:

1. Run the full Critic product governance review across the entire codebase (invoke the Critic agent per the protocol in `skills/orchestrator/protocols.md`, listing all source files).
2. Invoke the Review Lenses agent per the Review Lenses Agent Protocol in `skills/orchestrator/protocols.md`, requesting all five lenses on the complete implementation.
3. Verify all tests pass.
4. Present the result to the user:

   > "Your [product name] is built. Here's what it does: [summary of core flows]. All [N] tests pass. To try it: [how to verify it works — e.g., run the product, execute a test scenario, or try a workflow]. A few things the review found: [brief findings summary]. Want to try it out and let me know what you'd like to change?"

5. **Mention contribution opportunity.** After presenting the build result, briefly note that the framework captured observations during the build. These can be contributed back to the framework — the Orchestrator's Observation Contribution Flow (in `skills/orchestrator/SKILL.md`) will prompt for this during the next session resumption, or the user can run `tools/contribute-observations.sh --check` to see what's available. Also suggest periodic `git pull` to pick up improvements from other sessions. Keep this to 1-2 sentences — it's an FYI, not a pitch.

6. Run the Framework Reflection Protocol (read `skills/orchestrator/protocols.md` § FRP if not already loaded). Record reflection in `change_log`.

   **FRP focus for Stage 5:** Were artifact specs sufficient to build from? Did the Critic add value? Were the chunks the right size? Did proportionality hold — was the process appropriate for the product's complexity?

7. Update `current_stage` to "iteration".

8. **Compact project state.** Run `tools/compact-project-state.sh` to archive completed build entries.
   Verify with `--dry-run` first if the project has deferred findings to preserve.

**Transition to Stage 6** when all chunks are complete, all tests pass, and the product is presented to the user.
