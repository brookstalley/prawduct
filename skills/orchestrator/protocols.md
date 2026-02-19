# Orchestrator: Protocols

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

## Framework Friction Protocol

**When to apply:** During any session where the governance system itself caused friction — hooks blocking incorrectly, tools failing or producing wrong results, Bash workarounds for governance gates, or manual edits to `.session-governance.json`.

**What to do:** Capture a framework observation with type `process_friction` via `tools/capture-observation.sh`. Include what the friction was, what workaround was used, and root cause analysis.

**Why this exists:** PFR requires blocking Critic findings, FRP requires stage transitions, DCP requires directional changes. None fire when friction is with the governance machinery itself.

---

## Stage Transition Protocol

Before transitioning to any new stage, verify that the prerequisites for that stage are met. This is the system's automated completeness check — it ensures gaps are caught by the framework, not by the user remembering to ask.

**General rule:** Read `project-state.yaml` and verify the required fields for the target stage are populated. If anything is missing, decide how to handle it:

1. **Can you infer a reasonable answer from context?** → Infer, state as assumption in the product definition, proceed.
2. **Would two LLMs infer differently with meaningfully different outcomes?** → Add to `open_questions`. If it doesn't block the next stage, proceed with a note.
3. **Requires the user's product judgment** (e.g., which users to prioritize, what's in v1 scope)? → Add to `open_questions` with `waiting_on: "user"`, ask the user before proceeding.

**Specific prerequisites by transition:**

### → Stage 1 (Discovery)
- `classification.structural` has at least one non-null structural characteristic
- `classification.domain` is set
- `classification.risk_profile.overall` is set
- `classification.risk_profile.factors` has at least 2 entries with rationale

### → Stage 2 (Definition)
- `product_definition.vision` is set
- `product_definition.users.personas` has at least one persona
- `product_definition.core_flows` has at least one flow
- `product_definition.platform` is set
- `user_expertise` has at least `technical_depth` and `product_thinking` inferred

### → Stage 3 (Artifact Generation)
This is the highest-stakes transition — discovery becomes production. Check thoroughly:

- All Stage 2 prerequisites met
- `product_definition.scope.v1` has at least 3 items
- `product_definition.scope.later` has at least 1 item (scope without deferral is suspicious)
- `product_definition.goals` has at least 1 measurable success criterion
- `product_definition.nonfunctional` has at least `performance` and `uptime` set
- `technical_decisions` has at least one decision with rationale (the specific decisions needed depend on the product — check that every choice affecting implementation complexity has been made)
- When `structural.has_human_interface` is active: `design_decisions.accessibility_approach` is set
- `open_questions` has no high-priority items with `waiting_on: "user"` (unresolved user questions block artifact generation)
- `classification.domain_characteristics` is populated (at least 1 entry)

### → Stage 4 (Build Planning)
- All Stage 3 prerequisites met
- All 7 universal artifacts generated (or minimal artifacts where applicable) with correct frontmatter
- Cross-artifact consistency check passed
- All five review lenses applied (Testing Lens in Phase C), all blocking findings resolved
- Artifacts presented to user (user can interrupt with corrections)

### → Stage 5 (Building)
- Build plan artifact generated (`artifacts/build-plan.md`)
- `build_plan.strategy` is set in project-state.yaml
- `build_plan.chunks` has at least 3 entries (scaffold + data layer + at least one feature)
- Every chunk has `acceptance_criteria` mapped to test specification scenarios
- `build_plan.governance_checkpoints` has at least one checkpoint
- Build plan presented to user (user can interrupt with corrections)

### → Stage 6 (Iteration)
- All chunks in `build_plan.chunks` have status "complete"
- All tests pass
- Full Critic product governance review completed
- Product presented to user with instructions for running it

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
   - **Search scope:** Same-stage artifacts, same module/component as the original fix.
   - **Fix scope:** No count cap — if 10 instances exist, fix all 10. A high instance count is itself evidence of a systematic gap; note the count in the observation.

5. **Framework observation.** Capture via `tools/capture-observation.sh` with `--rca-symptom`, `--rca-root-cause`, and `--rca-category` arguments (these are always required — see note below). The observation must be generalized (not product-specific) per standard observation rules in `framework-observations/README.md`.

6. **Contribution pathway.** Briefly mention the observation was captured — "I captured a framework observation about [topic]." Observations accumulate in `.prawduct/framework-observations/` and are surfaced for contribution during session resumption (see the Orchestrator's Observation Contribution Flow in `skills/orchestrator/SKILL.md`). For manual contribution, use `tools/contribute-observations.sh --format <product-dir>`.

**RCA applies to all observations, not just PFR.** PFR mandates 5-whys as part of the fix flow, but root cause analysis is required for *every* observation captured — whether through PFR, DCP retrospective, FRP, or ad hoc learning. The observation schema enforces this: `root_cause_analysis` with `five_whys` is a required field. If an observation isn't worth analyzing causally, it isn't worth recording.

**Relationship to DCP:** PFR and DCP serve different purposes and stay separate. DCP is about *governance proportionality* — how much review does this change need? PFR is about *learning* — is this fix addressing a class of problem? A small functional fix (no DCP needed) can reveal a framework gap (PFR triggers). A large structural DCP adding new capability (not fixing a problem) doesn't need PFR. Where they overlap (DCP structural with retrospective), DCP's retrospective subsumes PFR steps 1-3, but PFR steps 4-6 (meta-fix, observation, contribution) may still apply if the structural change was fixing a framework gap.

---

## Critic Agent Protocol

The Critic is invoked as a separate agent (via Claude Code's Task tool, `subagent_type: "general-purpose"`). This provides independent review — the agent starts with a clean context, hasn't seen the Builder's reasoning, and isn't subject to task pressure from the build.

### When to invoke

- **Stage 5 per-chunk:** After each chunk (step 5 of the per-chunk cycle)
- **Stage 6 iteration:** After every file change before committing
- **DCP Enhancement:** Step 4 (after implementation)
- **DCP Structural:** Step 4 (plan-stage review — Generality + Coherence + Learning/Observability only) and Step 8 (final full review)
- **Build completion:** Full product governance review (Stage 5 completion step 1)

### Model requirement

**Always use the best available model for the Critic agent.** Do not specify a downgraded model (e.g., `model: "haiku"`) — the Critic is a quality gate and must have the same analytical capability as the main conversation. Omit the `model` parameter to inherit the parent's model.

### Agent prompt

Include these elements in the Task tool prompt:

1. **Role:** "You are the Critic for a Prawduct governance review."
2. **Instructions source:** "Read `skills/critic/SKILL.md` for your complete check definitions, applicability table, and output format."
3. **Project context:**
   - Project directory path
   - Product root (`.prawduct/`) path
   - Current stage
   - Files changed in this review (list relative paths)
   - One-sentence summary of what was changed and why
4. **Accepted context** (prevents false positives): Any user-approved tradeoffs, design decisions explicitly discussed, or scope decisions from this session. Keep this brief — 2-3 sentences maximum. If none, say "No special tradeoffs."
5. **Task:** "Apply all applicable checks per the applicability table. Run `tools/record-critic-findings.sh` with your findings (--files for all reviewed files, --check for each applicable check). Return a structured summary in the Critic output format."

**Example invocation:**

```
Task(subagent_type="general-purpose", prompt="""
You are the Critic for a Prawduct governance review.

Read skills/critic/SKILL.md for your complete check definitions, applicability table,
and output format. Read docs/principles.md for the Hard Rules.

Project: /path/to/project
Product root: /path/to/project/.prawduct
Stage: iteration
Files changed:
- skills/orchestrator/protocols.md
- skills/orchestrator/stage-5-build.md
- CLAUDE.md

Change summary: Moved Critic invocation from in-context skill loading to subagent model.
Accepted tradeoffs: None — this is a straightforward architectural change.

Apply all applicable checks per the applicability table. Run
tools/record-critic-findings.sh with your findings. Return your full review.
""")
```

### Output verification

After the agent returns, verify these four conditions:

1. **Evidence exists:** `.prawduct/.critic-findings.json` was created or updated (check file exists).
2. **File coverage:** `reviewed_files` in the findings includes all files listed as changed.
3. **Substantiveness:** At least one check has a summary longer than 5 words. An agent returning only "pass" or "ok" for every check without analysis is rubber-stamping.
4. **Check count:** `total_checks >= 4` (the minimum always-applicable checks).

**If verification fails:** Re-invoke the agent once with an explicit note: "Your previous review was incomplete — [specific failure]. Provide substantive analysis for each check." If it fails again, conduct an in-context review as fallback (read `skills/critic/SKILL.md` and apply checks manually).

### Acting on findings

- **Blocking:** Must be resolved before proceeding. Fix the issues, then re-invoke the Critic agent for the changed files.
- **Warning:** Note them. Fix quick ones, track others in `build_state.reviews`.
- **Note:** Informational. No action required unless they accumulate.
- **No findings:** Proceed. Record the clean review.

### Governance tracking

After the Critic agent completes successfully:
- Update `.prawduct/.session-governance.json` → `governance_state.chunks_completed_without_review` to 0
- Set `last_critic_review_chunk` to current chunk name (Stage 5) or change description (Stage 6)
- The `record-critic-findings.sh` tool also resets the chunk counter automatically

---

## Extending This Skill

Remaining Orchestrator capabilities are tracked in `project-state.yaml` → `build_plan.remaining_work`.

When adding new Orchestrator capabilities:
- Modify the relevant stage sub-file or add a new one.
- Update the Stage Transition Protocol (above) if the capability changes stage prerequisites.
- Update the Expertise Calibration section (above) if the capability changes how user behavior is interpreted.
- Add test scenario criteria in `tests/scenarios/` if the capability is observable during evaluation.
