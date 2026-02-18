# Orchestrator: Stage 6 (Iteration)

This stage handles post-build iteration: user feedback, change classification, and the Directional Change Protocol.
Read the main `skills/orchestrator/SKILL.md` for activation, session resumption, and routing.
Read `skills/orchestrator/protocols.md` for the Framework Reflection Protocol (FRP).

---

## Stage 6: Iteration

**Trigger:** `current_stage` is "iteration".

**What to do:**

The user has a working product and provides feedback. Handle feedback in lightweight cycles.

1. **Receive user feedback.** Listen for what the user wants to change. For all non-cosmetic changes, apply the Post-Fix Reflection Protocol (see `skills/orchestrator/protocols.md` § PFR) — classify the issue and, if framework-relevant, perform root cause analysis before planning the fix. The RCA informs what to fix: the implementation should target the root cause, not just the surface symptom.

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
   - **Functional:** Update affected artifacts → create or modify chunks for the change → Builder implements (if PFR classified this as framework-relevant in step 1, the implementation should target the root cause identified in the 5-whys, not just the surface symptom) → Critic reviews → run tests → verify no regressions.

5. **Verify no regressions.** Run all tests after every change. If a test fails, fix the regression before proceeding.

5a. **Post-Fix Reflection (completion).** For **functional** changes that PFR classified as framework-relevant in step 1: now that the fix is verified, apply PFR steps 4-6 (meta-fix across the product, capture framework observation, present contribution pathway). For product-specific changes, skip. For directional changes, the DCP retrospective (step 9) handles this.

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

**Mechanical enforcement:** When `governance-tracker.sh` detects 3+ distinct governed files edited without `directional_change.active = true`, it sets `directional_change.needs_classification = true` in `.prawduct/.session-governance.json`. The stop hook blocks until you classify. To unblock:
- **Mechanical:** Set `needs_classification` to `false` (no DCP needed).
- **Enhancement/Structural:** Set `active` to `true`, `needs_classification` to `false`, and follow the appropriate tier protocol below.

### Mechanical changes

No DCP needed. Implement the changes, run Critic review (see `skills/critic/SKILL.md`), commit. Set `directional_change.needs_classification` to `false` in `.prawduct/.session-governance.json` if the tracker flagged it.

### Enhancement changes

1. **Write a brief plan** in `working-notes/` describing the change, motivation, and affected files. Before implementing, check `observation_backlog` in `project-state.yaml` and recent `framework-observations/` for patterns relevant to the planned approach — prior observations may identify risks or constraints that should inform the plan. Apply PFR steps 1-2 (classify + RCA) before implementation if the enhancement addresses a known issue or gap. After implementation and Critic review, complete PFR steps 4-6.
2. **Implement** the change.
3. **Verify artifact freshness.** Read `artifact_manifest` in `project-state.yaml` to get the full artifact list. For each artifact, ask: "does this artifact describe behavior affected by my changes?" Read each candidate artifact and verify it still matches implementation. Update any stale artifacts. Record which artifacts you verified in `directional_change.artifacts_verified` (list of artifact names). **The stop hook enforces this** — it blocks completion when `artifacts_verified` is empty for enhancement/structural DCPs.
4. **Run Critic review** (see `skills/critic/SKILL.md`) — all applicable checks.
5. **Register deprecated terms** if any concepts were renamed/removed: write to `project-state.yaml` → `deprecated_terms` with replacement and grep patterns.

Set `directional_change` in `.prawduct/.session-governance.json` to track: `{"active": true, "tier": "enhancement", "plan_description": "<summary>", "retrospective_completed": false, "artifacts_verified": []}`. Set `active` to `false` after commit.

### Structural changes (full protocol)

1. **Flag and confirm.** "That's a significant shift — it would mean rethinking [X]. Want to explore that direction?"
2. **Reclassification check (product builds).** If the product's fundamental nature changed, re-run classification.
3. **Write a plan** in `working-notes/` describing the change, motivation, affected files, and phases. Before planning, check `observation_backlog` in `project-state.yaml` and recent `framework-observations/` for patterns relevant to the planned change — incorporate relevant findings into the plan to avoid repeating known issues. For observation-driven changes, include root cause analysis (see Post-Fix Reflection Protocol in `skills/orchestrator/protocols.md` § PFR). Set `directional_change` in `.prawduct/.session-governance.json`: `{"active": true, "tier": "structural", "plan_description": "<summary>", "retrospective_completed": false, "plan_stage_review_completed": false, "total_phases": <N>, "phases_reviewed_count": 0, "observation_captured": false, "artifacts_verified": []}`.
4. **Plan-stage Critic review.** Apply Generality, Coherence, and Learning/Observability checks to the plan. Set `plan_stage_review_completed` to `true`.
5. **Impact assessment.** Map blast radius via `artifact_manifest`. Register deprecated terms in `project-state.yaml` → `deprecated_terms`.
6. **Implement.** For multi-phase changes, run lightweight Coherence + Learning/Observability reviews between phases. Increment `phases_reviewed_count` after each.
7. **Verify artifact freshness.** Same as Enhancement step 3: read `artifact_manifest`, identify artifacts describing affected behavior, verify each is current, update stale ones, record the list in `directional_change.artifacts_verified`. **The stop hook enforces this.**
8. **Final Critic review** — all applicable checks (see `skills/critic/SKILL.md`).
9. **Observation.** Write an observation covering what the change accomplished, what governance caught, and what slipped through. Set `observation_captured` to `true`.
10. **Retrospective.** Answer: (a) Could the learning system have caught this earlier? (b) What process gaps surfaced? (c) Does the fix generalize? Capture findings as observations. Set `retrospective_completed` to `true`. After commit, set `active` to `false`.

The governance-stop hook enforces DCP completion mechanically — it checks these tracking fields and blocks session completion when steps are incomplete.

---

## Post-Fix Reflection (PFR) — Mechanical Enforcement

PFR ensures root cause analysis happens before fixes to governance-sensitive files, and that learning is captured as an observation. It is orthogonal to DCP — a mechanical DCP change still needs PFR if it touches governance-sensitive files.

### Governance-sensitive files

`skills/`, `tools/`, `scripts/`, `.prawduct/hooks/`. These define framework behavior. Changes to docs, templates, config, and artifacts are NOT governance-sensitive.

### How it works

1. **`governance-gate.sh`** independently detects governance-sensitive file edits and blocks them until `pfr_state.diagnosis_written: true` exists in `.session-governance.json`. This includes the very first edit — absence of `pfr_state` is treated as "diagnosis needed", not "PFR not triggered". The diagnosis must include `symptom`, `five_whys`, `root_cause`, `root_cause_category`, and `meta_fix_plan`. **`governance-tracker.sh`** (PostToolUse) handles bookkeeping — tracking which files were edited and maintaining `governance_sensitive_files` — but the gate does not depend on the tracker having run.
2. After implementing the fix, create an observation via `tools/capture-observation.sh` with a `root_cause_analysis` block and set `pfr_state.observation_file` to the observation file path.
3. **`governance-stop.sh`** blocks session completion if PFR is required but no observation file is set.
4. **`critic-gate.sh`** blocks commit if PFR is required but the observation file doesn't exist.

### The flow

```
1. Read files, understand the bug (reads are allowed)
2. Write diagnosis to .session-governance.json pfr_state
3. governance-gate now allows edits to governance-sensitive files
4. Implement fix
5. Create observation with root_cause_analysis via capture-observation.sh
6. Set pfr_state.observation_file in session state
7. Commit — critic-gate validates observation file exists
```

### Cosmetic escape hatch

If a change is truly cosmetic (typo fix in an error message, formatting), set `pfr_state.cosmetic_justification` to describe why and `pfr_state.required` to `false`. Both gates accept this. The Critic can flag insufficient justification as a warning.

### `root_cause_category` values

`missing_process` | `process_not_enforced` | `incomplete_coverage` | `wrong_abstraction` | `missing_detection` | `vocabulary_drift`

These enable mechanical pattern detection across fixes — if multiple fixes share the same category, that's a systematic gap.
