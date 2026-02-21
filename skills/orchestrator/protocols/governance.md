# Orchestrator: Governance Protocols

Protocols for framework reflection, stage transitions, expertise calibration, post-fix reflection, and structural critique. Read on demand at stage boundaries or when referenced.

---

## Framework Reflection Protocol

At every stage transition, pause and assess: **did the framework serve this product well in the stage just completed?**

**Assess these six dimensions:**

| Dimension | Question |
|-----------|----------|
| Proportionality | Was the work this stage required proportionate to the product's complexity and risk? |
| Coverage | Did the stage surface everything important? Was anything missed? |
| Applicability | Were any framework-required outputs inapplicable to this product? |
| Missing guidance | Did you have to improvise because the framework lacked guidance? |
| Documentation freshness | Did this stage create, modify, or reveal anything that makes existing documentation inaccurate — or expose content that has outlived its original purpose? |
| Learning completeness | Did this stage create, modify, or remove anything that the observation system should track? Are all new areas observable? |

**Documentation freshness covers two failure modes:** (1) Content that was true but is now wrong — facts changed, capabilities added, files created. (2) Content that is still technically true but serves the wrong purpose — roadmaps for completed work, build instructions for finished phases, temporary guidance that became permanent. Both make documentation misleading. The second is harder to detect because the content passes a "is this accurate?" check while failing a "does this still belong here?" check.

**Per-stage focus areas:**

| Stage | Focus |
|-------|-------|
| 0 (Intake) | Did structural characteristic detection cover this product adequately? Were domain-specific characteristics identified? Were risk factors appropriate? Did classification reveal a gap in the structural characteristic set? |
| 1 (Discovery) | Was question count proportionate? Were the right topics covered? |
| 2 (Definition) | Were scope and technical decisions at the right level of detail? |
| 3 (Artifacts) | Were the right artifacts generated? Were review findings appropriate? Do artifact descriptions in CLAUDE.md still match what was generated? |
| 4 (Build Planning) | Was chunking appropriate? Did build plan translate specs into concrete instructions? |
| 5 (Building) | Were artifact specs sufficient to build from? Did Critic add value? Right chunk size? Did the build reveal spec descriptions that don't match implementation? |
| 6 (Iteration) | Was feedback classification accurate? Did change impact assessment help? Did feedback cycles change artifacts in ways not reflected in documentation? For framework dev: did changes preserve learning system completeness? |

**What to do with findings:**

1. **Always** record a reflection entry in `change_log` (proves reflection happened):
   - `what: "Framework reflection: Stage N (name) complete"`
   - `why: "[assessment summary or 'no concerns']"`
   - **Update governance tracking (product builds only):** After recording the FRP, update `.prawduct/.session-governance.json` → `governance_state.last_frp_stage` to the current stage and reset `stage_transitions_without_frp` to 0.
2. **Capture substantive findings as observations.** If any dimension above produced a finding beyond "no concerns" — including documentation drift, missing guidance, proportionality issues, or coverage gaps — you MUST run `tools/capture-observation.sh` with the finding. This is not optional: substantive findings that remain only in `change_log` narrative are silently dropped from the learning system (HR2: No Silent Requirement Dropping). The tool handles schema compliance, UUIDs, timestamps, git SHAs, and write-access fallback automatically. Only create observations when there's signal — not for "no concerns." Non-substantive stage reflections are already recorded in `change_log`. See `framework-observations/README.md` for substantiveness criteria.
3. **If documentation is stale, update it in this session — don't defer.** Documentation drift compounds: a stale doc misleads the next session, which produces more stale docs. File creation, capability changes, and structural additions are the most common triggers.
4. **Surface findings to the user** briefly: "Framework note: [observation]." Keep to 1-2 sentences unless there's a significant finding. Don't slow down an eager user.
5. Keep all observations **general, not product-specific**. The insight must apply across products.

---

## Stage Transition Protocol

Before transitioning to any new stage, verify that the prerequisites for that stage are met. This is the system's automated completeness check — it ensures gaps are caught by the framework, not by the user remembering to ask.

**General rule:** Read `project-state.yaml` and verify the required fields for the target stage are populated. If anything is missing, decide how to handle it:

1. **Can you infer a reasonable answer from context?** → Infer, state as assumption in the product definition, proceed.
2. **Would two LLMs infer differently with meaningfully different outcomes?** → Add to `open_questions`. If it doesn't block the next stage, proceed with a note.
3. **Requires the user's product judgment** (e.g., which users to prioritize, what's in v1 scope)? → Add to `open_questions` with `waiting_on: "user"`, ask the user before proceeding.

**Per-stage prerequisites:** See `skills/orchestrator/protocols/stage-prerequisites.md` for the specific prerequisite checklist for each stage transition.

If any prerequisite is missing, fill it in with a proportionate inference and state it as an assumption in the product definition summary. If a prerequisite can't be inferred (rare — usually means discovery was insufficient), flag it to the user before proceeding.

**Context management at transitions:** After completing a stage transition, prior stage skill content (e.g., domain-analyzer questions, artifact-generator templates) is no longer needed in context. If the session has been running long (multiple stages completed), suggest `/compact` to the user before starting the next stage — controlled compaction loses less context than automatic truncation.

---

## Expertise Calibration

Throughout all stages, infer and maintain the user expertise profile in `project-state.yaml` → `user_expertise`. Never ask the user to self-assess.

**Signals to watch for:**

| Signal | Indicates |
|--------|-----------|
| Plain language, no jargon | Low technical depth |
| Focus on "what" not "how" | Low technical depth, possibly high product thinking |
| Mentions specific technologies by name | Higher technical depth |
| Asks about architecture or infrastructure | Higher technical depth |
| Mentions user needs, personas, or flows | Higher product thinking |
| Mentions edge cases unprompted | Higher design sensibility |
| Mentions deployment, monitoring, or operations | Higher operational awareness |

**How expertise affects your behavior:**

| User Expertise | Your Behavior |
|---------------|---------------|
| **Low technical depth** | Never ask technical questions. Make architecture decisions as assumptions. Explain any technical concept you must mention. Frame everything in user-facing terms: "Should this work without internet?" not "Do you need offline-first architecture?" |
| **High technical depth** | Engage at their level but lead with product questions, not technology questions. Challenge premature technology decisions: "You mentioned [X] — let's nail down what the app needs to do first, then see if that's the right fit." |
| **Low product thinking** | Help them think through users and scope. Surface personas, edge cases, and scope questions they haven't considered. This is where your proactive expertise adds the most value. |
| **High product thinking** | They've thought about users and scope. Focus on areas they haven't covered: operations, security, accessibility, cost. |

Update `user_expertise` with evidence after each conversational exchange. Early inferences may be revised as you learn more.

---

## Post-Fix Reflection Protocol (PFR)

**When to apply:** Every non-cosmetic fix in Stage 5 (chunk fixes, Critic blocking findings) and Stage 6 (functional iteration fixes). Exempt: cosmetic changes (wording, formatting, minor adjustments). DCP structural changes have their own retrospective (step 9) which is more thorough — PFR steps 4-6 (observation + contribution) still apply if relevant.

**Key principle:** Root cause analysis happens **before** implementing the fix, so the fix targets the root cause rather than the symptom.

**Steps:**

1. **Classify.** Is this fix product-specific or framework-relevant?
   - **Test:** "Would a different product with similar structural characteristics hit the same problem?"
   - If yes → framework-relevant. Continue to step 2.
   - If no → product-specific. Record briefly in `change_log` and proceed directly to step 3 (implement the fix). Skip steps 2, 4-6.

2. **Root Cause Analysis (5-whys) — before implementing.** For framework-relevant fixes only.
   - Write your RCA as natural language to `pfr_state.rca` in `.prawduct/.session-governance.json`. The governance gate blocks governance-sensitive file edits until this is written (>=50 chars). Include the 5 whys:
     1. What's the immediate problem?
     2. Why does it happen?
     3. What's the deeper structural cause?
     4. What class of problem is this?
     5. What would prevent the class, not just this instance?
   - Root cause categories for reference: `missing_process`, `process_not_enforced`, `incomplete_coverage`, `wrong_abstraction`, `missing_detection`, `vocabulary_drift`.
   - Document the analysis in the `change_log` entry (the `why` field should trace the causal chain, not just describe the symptom).
   - **The class test:** If your fix only prevents this exact symptom from recurring, you haven't gone deep enough. The fix should prevent the *class* of problem, not just the instance.

3. **Implement the fix** targeting the root cause identified in step 2. For product-specific fixes (step 1), implement targeting the immediate issue.

4. **Meta-fix.** Check the user's product for other manifestations of the same root cause.
   - **Code blast radius:** Same-stage artifacts, same module/component as the original fix. No count cap — if 10 instances exist, fix all 10. A high instance count is itself evidence of a systematic gap; note the count in the observation.
   - **Documentation blast radius:** Identify artifacts and docs that describe the behavior you just changed. If any artifact says "X works like this" and you changed how X works, update the artifact. Check `artifact_manifest` in project-state.yaml and `doc-manifest.yaml` for files describing the affected area.

5. **Framework observation.** Capture via `tools/capture-observation.sh` with `--rca-symptom`, `--rca-root-cause`, and `--rca-category` arguments (these are always required — see note below). The observation must be generalized (not product-specific) per standard observation rules in `framework-observations/README.md`.

6. **Contribution pathway.** Briefly mention the observation was captured — "I captured a framework observation about [topic]." Observations accumulate in `.prawduct/framework-observations/` and are surfaced for contribution during session resumption (see the Orchestrator's Observation Contribution Flow in `skills/orchestrator/SKILL.md`). For manual contribution, use `tools/contribute-observations.sh --format <product-dir>`.

**RCA applies to all observations, not just PFR.** PFR mandates 5-whys as part of the fix flow, but root cause analysis is required for *every* observation captured — whether through PFR, DCP retrospective, FRP, or ad hoc learning. The observation schema enforces this: `root_cause_analysis` with `five_whys` is a required field. If an observation isn't worth analyzing causally, it isn't worth recording.

**Relationship to DCP:** PFR and DCP serve different purposes and stay separate. DCP is about *governance proportionality* — how much review does this change need? PFR is about *learning* — is this fix addressing a class of problem? A small functional fix (no DCP needed) can reveal a framework gap (PFR triggers). A large structural DCP adding new capability (not fixing a problem) doesn't need PFR. Where they overlap (DCP structural with retrospective), DCP's retrospective subsumes PFR steps 1-3, but PFR steps 4-6 (meta-fix, observation, contribution) may still apply if the structural change was fixing a framework gap.

---

## PFR — Mechanical Enforcement

PFR ensures root cause analysis happens before fixes to governance-sensitive files, and that learning is captured as an observation. It is orthogonal to DCP — a mechanical DCP change still needs PFR if it touches governance-sensitive files.

### Governance-sensitive files

`skills/`, `agents/`, `tools/`, `scripts/`, `.prawduct/hooks/`. These define framework behavior. Changes to docs, templates, config, and artifacts are NOT governance-sensitive.

### How it works

1. **`gate.py`** (via `governance-gate.sh` shim) detects governance-sensitive file edits and blocks them until `pfr_state.rca` in `.session-governance.json` is non-empty and >= 50 chars. The RCA is natural language including the 5 whys: What's the immediate problem? Why does it happen? What's the deeper structural cause? What class of problem is this? What would prevent the class? **`tracker.py`** (PostToolUse) handles bookkeeping — tracking which files were edited and maintaining `governance_sensitive_files` — but the gate does not depend on the tracker having run.
2. After implementing the fix, create an observation via `tools/capture-observation.sh` with a `root_cause_analysis` block and set `pfr_state.observation_file` to the observation file path.
3. **`stop.py`** blocks session completion if PFR is required but no observation file is set.
4. **`commit.py`** blocks commit if PFR is required but the observation file doesn't exist.

### The flow

```
1. Read files, understand the bug (reads are allowed)
2. Write natural language RCA to pfr_state.rca (>= 50 chars, include 5 whys)
3. gate.py now allows edits to governance-sensitive files
4. Implement fix
5. Create observation with root_cause_analysis via capture-observation.sh
6. Set pfr_state.observation_file in session state
7. Commit — commit.py archives traces and validates observation file exists
```

### Cosmetic escape hatch

If a change is truly cosmetic (typo fix in an error message, formatting), set `pfr_state.cosmetic_justification` to describe why and `pfr_state.required` to `false`. Both gates accept this. The Critic can flag insufficient justification as a warning.

### `root_cause_category` values

`missing_process` | `process_not_enforced` | `incomplete_coverage` | `wrong_abstraction` | `missing_detection` | `vocabulary_drift`

These enable mechanical pattern detection across fixes — if multiple fixes share the same category, that's a systematic gap.

---

## Framework Friction Protocol

**When to apply:** During any session where the governance system itself caused friction — hooks blocking incorrectly, tools failing or producing wrong results, Bash workarounds for governance gates, or manual edits to `.session-governance.json`.

**What to do:** Capture a framework observation with type `process_friction` via `tools/capture-observation.sh`. Include what the friction was, what workaround was used, and root cause analysis.

**Why this exists:** PFR requires blocking Critic findings, FRP requires stage transitions, DCP requires directional changes. None fire when friction is with the governance machinery itself.

---

## Structural Critique Protocol

Apply the framework's principles to its own founding architectural decisions — not just to incremental changes. This is a deductive process: start from principles and research, then question whether existing structures satisfy them.

**Triggers:** After every 3 evaluation runs, after every directional change, or on request. The post-change retrospective (Directional Change Protocol step 11) includes a targeted structural critique: does the change's motivation reveal that the learning system failed to detect a principle violation? If yes, this is a signal that the Structural Critique Protocol's triggers or dimensions need expansion.

**Process:**

1. For each major structural decision (structural characteristic taxonomy, stage progression, artifact selection, skill boundaries):
   - Which principles governed this decision?
   - Does it still satisfy them given current evidence?
   - Would a different choice better satisfy them given what we now know?
   - Are there parallel implementations for different contexts (e.g., "framework" vs. "product") that should be unified? Parallel paths that diverge only in naming, not behavior, violate Eat Your Own Cooking.
2. Record findings as `structural_critique` observations in `framework-observations/`.
3. If a founding decision violates a principle, propose a change through the normal observation → triage → action cycle. Structural critiques do not bypass governance — they feed the same process with a different evidence source.

**Why this exists:** The observation system is inductive (many observations → detect pattern → propose change). But some problems require deductive analysis (principles + research → questioning). A taxonomy built on enumerated categories might never accumulate observations saying "this should be dimensional" — the failure mode is invisible from inside the system. The Structural Critique Protocol fills this gap by periodically questioning foundations, not just changes.

---

## Extending This Skill

Remaining Orchestrator capabilities are tracked in `project-state.yaml` → `build_plan.remaining_work`.

When adding new Orchestrator capabilities:
- Modify the relevant stage sub-file or add a new one.
- Update the Stage Transition Protocol (above) if the capability changes stage prerequisites.
- Update the Expertise Calibration section (above) if the capability changes how user behavior is interpreted.
- Add test scenario criteria in `tests/scenarios/` if the capability is observable during evaluation.
