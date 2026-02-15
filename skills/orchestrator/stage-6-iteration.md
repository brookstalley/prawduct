# Orchestrator: Stage 6 (Iteration)

This stage handles post-build iteration: user feedback, change classification, and the Directional Change Protocol.
Read the main `skills/orchestrator/SKILL.md` for activation, session resumption, and routing.
Read `skills/orchestrator/protocols.md` for the Framework Reflection Protocol (FRP).

---

## Stage 6: Iteration

**Trigger:** `current_stage` is "iteration".

**What to do:**

The user has a working product and provides feedback. Handle feedback in lightweight cycles.

1. **Receive user feedback.** Listen for what the user wants to change.

2. **Classify the feedback:**

   - **Cosmetic** (wording, formatting, minor adjustments that don't change behavior or contracts): Implement directly. No artifact updates needed. Quick cycle: fix → test → done.
   - **Functional** (new feature, changed behavior, different flow): Update affected artifacts first, then build. This is a mini Stage 5 loop:
     1. Assess change impact: what artifacts change? What chunks are affected? Any regressions? Consult `artifact_manifest` to identify affected artifacts.
     2. Update the relevant artifacts (whichever are affected — see `artifact_manifest`).
     3. Create new chunk(s) or identify existing chunks to modify.
     4. Builder implements → Critic reviews → tests pass.
   - **Directional** (fundamentally different product vision, or 3+ file changes): Follow the Directional Change Protocol below.

   **Change governance (all sizes)**

   Every file change in a governed project requires Critic review before committing, regardless of file count. This is automatic — do not ask the user whether to run it.

   | Change size | Protocol |
   |---|---|
   | 1-2 files | Implement changes → run Critic (all applicable checks) → record findings → commit |
   | 3+ files or directional | Follow Directional Change Protocol below |

3. **Change impact assessment (R5.2).** Before implementing any functional change:

   > "That change would affect [artifacts]. Here's what it means: [impact description]. [If small: 'Quick fix, should take one iteration.' If larger: 'This touches [N] files and the [artifact]. Want to proceed?']"

   For low-risk products, keep this brief. Don't make a one-line change sound like a major undertaking.

4. **Implement the change.** Follow the cycle matching the classification:
   - **Cosmetic:** Implement the fix → run tests → verify → done.
   - **Functional:** Update affected artifacts → create or modify chunks for the change → Builder implements → Critic reviews → run tests → verify no regressions.

5. **Verify no regressions.** Run all tests after every change. If a test fails, fix the regression before proceeding.

6. **Update iteration state.** Add an entry to `project-state.yaml` → `iteration_state.feedback_cycles` with the feedback, classification, affected artifacts/chunks, and status. Run `tools/compact-project-state.sh --section change_log --section feedback_cycles` if session-health-check reports state warnings.

7. **Check for "done."** After each iteration cycle, ask: "Anything else you'd like to change?" For low-risk products, this is lightweight. Don't over-process: "Want to tweak anything?" is fine.

8. Run the Framework Reflection Protocol (read `skills/orchestrator/protocols.md` § FRP if not already loaded) when the user indicates they're satisfied (or after 3+ iteration cycles).

   **FRP focus for Stage 6:** Was the feedback classification accurate? Did the change impact assessment help? Were artifacts sufficient for the iteration, or did gaps surface?

**Low-risk product iteration rules (not framework changes):**
- Don't require formal change impact assessments for cosmetic changes.
- Don't re-run all four review lenses for minor tweaks.
- Don't update every artifact for a small functional change — update only what's actually affected.
- Bias toward action: fix, test, show, ask.
- Framework changes always require Critic review regardless of size.

---

## Directional Change Protocol

This protocol triggers when a change is classified as **directional** OR modifies **3+ files**. It ensures multi-file changes receive governance proportionate to their impact. Scale effort with change complexity, not file count alone — renaming a term across 5 files is less complex than restructuring 3 skills.

1. **Flag and confirm.** "That's a significant shift — it would mean rethinking [X]. Want to explore that direction, or keep iterating on the current version?"
2. **Reclassification check (product builds).** Consider whether reclassification of structural characteristics is warranted. If the product's fundamental nature has changed, re-run classification.
3. **Write a plan** in `working-notes/` (within the product root) describing the change, its motivation, affected files, and implementation phases. **Set governance tracking:** Update `.claude/.session-governance.json` → `directional_change` to `{"active": true, "plan_description": "<brief summary>", "retrospective_completed": false}`. The governance-stop hook blocks session completion until the retrospective is complete.
4. **Plan-stage Critic review.** Before implementing, apply Critic checks for Generality, Coherence, and Learning/Observability to the plan. This catches structural problems before they're built.
5. **Address findings** from plan-stage review before implementing. Blocking findings must be resolved.
6. **Impact assessment.** Which artifacts/files are invalidated vs. still valid? Consult `artifact_manifest` to map the blast radius. **List all removed/renamed terms** (concepts, stage names, classification labels, etc.) — the Critic's Concept Ripple check uses this list to grep for stale references across the codebase.
7. **Implement in phases.** For multi-phase changes, run a lightweight review between phases: Coherence and Learning/Observability checks. Capture a brief observation after each phase.
8. **Update artifacts and implement.** Update affected artifacts → create/modify chunks → Builder implements → Critic reviews (including Directional Change Review — see `skills/critic/SKILL.md`).
9. **Final Critic review.** After all changes are complete, run the full Critic review (all applicable checks).
10. **Session observation.** Write an observation for the full implementation, covering what the change accomplished, what governance caught, and what slipped through.
11. **Post-change retrospective.** After the final Critic review passes, answer four questions:

    a. **Detection:** Could the framework's learning system have caught the problem this change addresses? If not, what's missing?

    b. **Process:** What did the implementation process reveal about gaps beyond the change itself?

    c. **Architecture:** Does this change create new areas the learning system can't observe?

    d. **Generalization:** Does this fix apply only to where discovered, or does the same gap exist in analogous contexts? Instance-specific fixes that don't generalize are Failure Mode 9 (see `docs/self-improvement-architecture.md`).

    Capture each substantive finding as an observation using `tools/capture-observation.sh`. If no substantive findings exist, record that in the change_log entry: "Retrospective: no findings."

    **Mark retrospective complete:** Update `.claude/.session-governance.json` → `directional_change.retrospective_completed` to `true`. After the commit succeeds, set `directional_change.active` to `false`.

    This step is not optional. The Critic validates quality; the retrospective captures learning. Both are required. The governance-stop hook enforces this mechanically.
