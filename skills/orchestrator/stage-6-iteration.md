# Orchestrator: Stage 6 (Iteration)

This stage handles post-build iteration: user feedback, change classification, and the Directional Change Protocol.
Read the main `skills/orchestrator/SKILL.md` for activation, session resumption, and routing.
Read `skills/orchestrator/protocols.md` for the Framework Reflection Protocol (FRP).

---

## Stage 6: Iteration

**Trigger:** `current_stage` is "iteration".

**What to do:**

The user has a working product and provides feedback. Handle feedback in lightweight cycles.

1. **Receive user feedback.** Listen for what the user wants to change. For changes triggered by the observation system (the "act now" path from session resumption pattern surfacing), apply the Root Cause Protocol (see `skills/orchestrator/protocols.md`) before planning the fix. The goal is not just to fix the symptom but to close the gap that allowed the symptom.

2. **Classify the feedback:**

   - **Cosmetic** (wording, formatting, minor adjustments that don't change behavior or contracts): Implement directly. No artifact updates needed. Quick cycle: fix → test → done.
   - **Functional** (new feature, changed behavior, different flow): Update affected artifacts first, then build. This is a mini Stage 5 loop:
     1. Assess change impact: what artifacts change? What chunks are affected? Any regressions? Consult `artifact_manifest` to identify affected artifacts.
     2. Update the relevant artifacts (whichever are affected — see `artifact_manifest`).
     3. Create new chunk(s) or identify existing chunks to modify.
     4. Builder implements → Critic reviews → tests pass.
   - **Directional** (fundamentally different product vision, or structural framework changes): Follow the Directional Change Protocol below.

   **Change governance (all sizes)**

   Every file change in a governed project requires Critic review before committing (see `skills/critic/SKILL.md`). This is automatic — do not ask the user.

   | Change type | Protocol |
   |---|---|
   | 1-2 files | Implement → Critic review → commit |
   | 3+ files, mechanical (renames, reference updates) | Implement → Critic review → commit |
   | 3+ files, adds/modifies capability | DCP Enhancement tier |
   | Changes framework concepts or governance | DCP Structural tier |

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

Multi-file changes receive governance proportionate to their **impact**, not their file count. Classify every multi-file change into one of three tiers:

**Classification test:** "Does this change what the framework *is* (structural), what it *does* (enhancement), or just how it *looks* (mechanical)?"

| Tier | When | Process |
|---|---|---|
| **Mechanical** | Renames, moves, reference updates, formatting — any file count | Normal Critic review. No DCP. |
| **Enhancement** | Adds/modifies capability, 3+ files, doesn't change framework concepts | Plan → Implement → Full Critic review. |
| **Structural** | Changes framework concepts, modifies governance rules, introduces new vocabulary | Full protocol below. |

### Mechanical changes

No DCP needed. Implement the changes, run Critic review (see `skills/critic/SKILL.md`), commit.

### Enhancement changes

1. **Write a brief plan** in `working-notes/` describing the change, motivation, and affected files. Before implementing, check `observation_backlog` in `project-state.yaml` and recent `framework-observations/` for patterns relevant to the planned approach — prior observations may identify risks or constraints that should inform the plan.
2. **Implement** the change.
3. **Run Critic review** (see `skills/critic/SKILL.md`) — all applicable checks.
4. **Register deprecated terms** if any concepts were renamed/removed: write to `project-state.yaml` → `deprecated_terms` with replacement and grep patterns.

Set `directional_change` in `.session-governance.json` to track: `{"active": true, "plan_description": "<summary>", "retrospective_completed": false}`. Set `active` to `false` after commit.

### Structural changes (full protocol)

1. **Flag and confirm.** "That's a significant shift — it would mean rethinking [X]. Want to explore that direction?"
2. **Reclassification check (product builds).** If the product's fundamental nature changed, re-run classification.
3. **Write a plan** in `working-notes/` describing the change, motivation, affected files, and phases. Before planning, check `observation_backlog` in `project-state.yaml` and recent `framework-observations/` for patterns relevant to the planned change — incorporate relevant findings into the plan to avoid repeating known issues. For observation-driven changes, include root cause analysis (see Root Cause Protocol in `skills/orchestrator/protocols.md`). Set `directional_change` in `.session-governance.json`: `{"active": true, "plan_description": "<summary>", "retrospective_completed": false, "plan_stage_review_completed": false, "total_phases": <N>, "phases_reviewed_count": 0, "observation_captured": false}`.
4. **Plan-stage Critic review.** Apply Generality, Coherence, and Learning/Observability checks to the plan. Set `plan_stage_review_completed` to `true`.
5. **Impact assessment.** Map blast radius via `artifact_manifest`. Register deprecated terms in `project-state.yaml` → `deprecated_terms`.
6. **Implement.** For multi-phase changes, run lightweight Coherence + Learning/Observability reviews between phases. Increment `phases_reviewed_count` after each.
7. **Final Critic review** — all applicable checks (see `skills/critic/SKILL.md`).
8. **Observation.** Write an observation covering what the change accomplished, what governance caught, and what slipped through. Set `observation_captured` to `true`.
9. **Retrospective.** Answer: (a) Could the learning system have caught this earlier? (b) What process gaps surfaced? (c) Does the fix generalize? Capture findings as observations. Set `retrospective_completed` to `true`. After commit, set `active` to `false`.

The governance-stop hook enforces DCP completion mechanically — it checks these tracking fields and blocks session completion when steps are incomplete.
