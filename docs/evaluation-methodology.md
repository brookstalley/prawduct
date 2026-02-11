# Evaluation Methodology

This document defines the complete evaluation lifecycle for the Prawduct framework — how to run evaluations, extract learnings, update skills, detect regressions, and continuously improve the evaluation process itself.

## Context

The framework has detailed test scenarios with structured rubrics and mandatory result recording (see CLAUDE.md § "Recording Evaluation Results"). This document provides the methodology for using that infrastructure systematically.

**What this covers:**
- How to set up and run an evaluation end-to-end
- How to analyze results and extract learnings
- When to update skills vs. defer decisions
- How to detect regressions across framework changes
- When to use simulation vs. interactive evaluation
- How to improve the evaluation process itself through meta-learning

**Why this matters:**
- **HR5 (No Confidence Without Basis)**: If our eval process isn't documented, we can't have confidence in our learnings
- **R6.2 (Pattern Extraction)**: "Requires statistical significance, not anecdotes" — we need documented baselines to distinguish patterns from noise
- **"Apply the framework to itself"** (CLAUDE.md): Our own eval process should be as rigorous as what we demand from user products

---

## A. Evaluation Types

### Scenario-Based vs. Exploratory

**Scenario-based evaluation**
- Tests against defined rubrics in `tests/scenarios/`
- Structured input, scripted responses, predetermined criteria
- Purpose: Validate framework behavior, detect regressions, measure progress
- When: After skill changes, before releases, for baseline establishment

**Exploratory evaluation**
- Ad-hoc testing with real product ideas
- Unscripted conversation, subjective assessment
- Purpose: Discover edge cases, surface new patterns, validate real-world applicability
- When: Prototyping new features, investigating reported issues, learning from real usage

### Simulation vs. Interactive

**Simulation** (LLM plays test persona)
- **Pros:** Fast, cheap, repeatable, can run many scenarios quickly
- **Cons:** Cannot evaluate conversation quality, question ordering, vocabulary calibration, or stage transitions
- **When to use:**
  - Mechanical criteria (classification, artifact structure, project-state schema)
  - Artifact content verification (data model entities, test scenarios, NFRs)
  - Fast regression checks after skill changes
  - Initial scenario validation (does the rubric work?)

**Interactive** (human plays test persona)
- **Pros:** Can evaluate all criteria including conversation quality, provides full transcript
- **Cons:** Slow, expensive, requires human time, less repeatable
- **When to use:**
  - Conversation quality criteria (question ordering, plain language, stage transitions)
  - Expertise calibration validation (does system adapt vocabulary correctly?)
  - Pacing sensitivity testing (does user feel interrogated?)
  - Baseline establishment for new scenarios

**Hybrid approach**
1. Run simulation first for mechanical criteria (fast, cheap)
2. Identify "unable-to-evaluate" conversation criteria
3. Run targeted interactive eval for those specific criteria only

### Decision Matrix

| Evaluation Need | Type | Evaluator | Typical Duration |
|-----------------|------|-----------|------------------|
| Regression check after skill change | Scenario-based | Simulation | 10-20 min per scenario |
| New scenario baseline | Scenario-based | Interactive | 45-90 min |
| Conversation quality verification | Scenario-based | Interactive | 45-90 min |
| Edge case discovery | Exploratory | Human | Variable |
| Real product validation | Exploratory | Human | Variable |

---

## B. Running an Evaluation

### Pre-Eval Setup Checklist

Before starting an evaluation:

- [ ] **Clean framework state**: Run `git status` to verify no uncommitted changes
- [ ] **Record framework version**: Note current git SHA for result tracking (`git rev-parse --short HEAD`)
- [ ] **Create isolated project directory**: `mkdir -p /tmp/eval-{scenario}/`
- [ ] **Copy project-state template**: `cp templates/project-state.yaml /tmp/eval-{scenario}/`
- [ ] **Verify scenario file exists**: Check `tests/scenarios/{scenario}.md` has complete rubric
- [ ] **Check scenario prerequisites**: Verify framework has required Phase/shape support (e.g., automation scenarios need Phase 2)
- [ ] **Choose evaluator type**: Simulation or interactive? (See § A above)

### Execution Procedure

**1. Start new LLM conversation**
   - Provide prawduct framework as reference context (CLAUDE.md, skills/, templates/, docs/)
   - Set `/tmp/eval-{scenario}/` as the project directory where all output files go
   - For simulation: LLM will generate outputs based on scenario
   - For interactive: Human plays test persona, full conversation captured

**2. Provide input prompt**
   - Use exact input from scenario file's "Input" section
   - For interactive: Type as if you are the test persona

**3. Respond to system questions**
   - **For simulation**: LLM uses scripted responses from scenario's "Test Conversation" section
   - **For interactive**: Human responds in character as test persona, following persona guidelines
   - If system asks about a topic not covered in scripted responses, respond in character

**4. Let system progress through stages**
   - Expected progression: Stages 0 → 0.5 → 1 → 2 → 3
   - Do not intervene unless system gets stuck or deviates significantly
   - If deviation occurs, note in observations section of results

**5. Capture complete record**
   - **For simulation**: Capture generated project-state.yaml and artifacts/
   - **For interactive**: Additionally capture full conversation transcript with clear user/system turn boundaries

### Evaluation Procedure

**1. Evaluate project-state.yaml**
   - Open `/tmp/eval-{scenario}/project-state.yaml`
   - For each C5 rubric criterion, check: PASS / PARTIAL / FAIL / UNABLE
   - Record specific evidence (field names, values, rationale quality)

**2. Evaluate artifacts/**
   - Open each artifact file in `/tmp/eval-{scenario}/artifacts/`
   - For each C3 rubric criterion, check: PASS / PARTIAL / FAIL / UNABLE
   - Verify artifact-specific criteria (entities, frontmatter, cross-references)

**3. Evaluate conversation (interactive only)**
   - For each C1, C2, C4 conversation criterion, check: PASS / PARTIAL / FAIL / UNABLE
   - Quote specific evidence from transcript
   - **For simulation**: Mark conversation-quality criteria as "unable-to-evaluate"

**4. Score each component**
   - C2 Domain Analyzer: Sum must-do/must-not-do/quality criteria results
   - C1 Orchestrator: Sum must-do/must-not-do/quality criteria results
   - C3 Artifact Generator: Sum must-do/must-not-do/quality criteria results
   - C4 Review Lenses: Sum must-do/must-not-do/quality criteria results
   - C5 Project State: Sum must-do/must-not-do/quality criteria results
   - End-to-End: Evaluate overall success criteria

### Recording Results

**This step is mandatory before cleanup.** Unrecorded evaluations are wasted work.

**1. Create results file**
   - Filename: `eval-history/{scenario}-{YYYY-MM-DD}.md`
   - If multiple runs same day: `{scenario}-{YYYY-MM-DD}-2.md`

**2. Add YAML frontmatter**
   - See § G (Recording Format) below for complete template
   - Include: scenario, date, evaluator type, framework version (git SHA)
   - Include: pass/partial/fail/unable counts total and by component
   - Include: skills_updated list (initially empty, fill in after § C)

**3. Document detailed findings**
   - Use table format from § G (Recording Format)
   - For each criterion: result + specific evidence
   - For "unable-to-evaluate": explain why (e.g., "Needs transcript")

**4. Identify issues**
   - List each failed must-do/must-not-do as an issue
   - List each partial pass with explanation
   - List any quality criteria failures
   - Group related findings (e.g., "Orchestrator over-explained in 3 places")

**5. Add meta-observations**
   - See § F (Evaluating the Evaluation) for template
   - Document rubric ambiguities, scenario design issues, process friction

**6. Extract observations to framework observation journal**
   - Parse the evaluation results for all framework findings (Issues Requiring Skill Updates, Observations NOT Acted On, Meta-Observations)
   - For each finding, create or append to observation entry in `framework-observations/{scenario-name}-{YYYY-MM-DD}.yaml`
   - Use session_type: evaluation, include scenario_name in session_context
   - Map findings to observation types:
     - Failed must-do/must-not-do → severity: blocking or warning
     - Partial passes → severity: warning
     - Quality criteria issues → severity: note
     - Meta-observations → type: rubric_issue or process_friction
   - Set status: noted for new findings, update existing observations if this is a regression check
   - This ensures eval findings feed the pattern detection system

**7. Verify observation capture happened automatically**
   - **BLOCKING CHECK**: Verify that `framework-observations/{scenario-name}-{YYYY-MM-DD}.yaml` exists
   - If file does NOT exist, this indicates the observation capture system failed during the eval run
   - If missing:
     - Create observation entry manually documenting the capture failure
     - Mark as severity: blocking, type: process_friction
     - Investigation required: Why didn't automatic capture work?
   - If file exists:
     - Review observations to ensure they're substantive (not just "no concerns")
     - Verify at least one observation per stage transition (0 → 0.5 → 1 → 2 → 3 = 5 transitions minimum)

### Cleanup

**After results are recorded, observations extracted, observation capture verified, and all committed to the prawduct repo:**

```bash
rm -rf /tmp/eval-{scenario}
```

**Never delete the evaluation directory before results, observations, and observation verification are complete.**

---

## C. Extracting Learnings

This process transforms evaluation observations into framework improvements. Based on patterns from `working-notes/sleep-sounds-session-learnings-2026-02-10.md` and `eval-history/family-utility-2026-02-10.md`.

### Process

**1. Identify observations** from eval results
   - Failed must-do/must-not-do criteria (hard failures)
   - Partial passes or quality criteria failures (soft issues)
   - Patterns across multiple findings (e.g., "Orchestrator over-explained in 3 places")

**2. For each observation, ask:**
   - Is this a skill deficiency or a rubric problem?
   - Is this specific to this scenario or generalizable?
   - Is this one instance or a pattern? (Learn Slowly principle)
   - Does this violate a Hard Rule or just a quality standard?

**3. Generality test**
   - Mentally apply proposed fix to other product shapes
   - Check: Does this improve discovery for family-utility? Background pipeline? B2B API? Multi-party marketplace?
   - If fix only helps one scenario, it's enumeration not learning
   - Example: "Ask about dark room constraints" → Too specific. "Ask about physical context alongside platform" → General.

**4. Decision matrix**

| Observation Type | Action |
|------------------|--------|
| **Hard failure** (must-do/must-not-do violated) | Update skill immediately, document fix |
| **Soft issue affecting multiple scenarios** | Update skill, add to "patterns observed" |
| **Soft issue in single scenario** | Document in working-notes, watch for pattern |
| **Rubric ambiguity** (criterion unclear) | Update scenario rubric, re-evaluate if needed |
| **Test method limitation** (e.g., simulation can't evaluate X) | Document in eval results as "unable-to-evaluate" |

**5. Update skills with provenance**
   - Modify relevant SKILL.md file
   - Commit message: "Fix {issue} found in {scenario} eval: {what changed}"
   - Reference eval result file in commit message: "See eval-history/{scenario}-{date}.md Issue N"
   - Update eval result's `skills_updated` field with file path and brief change description

**6. Document deferred decisions**
   - Create/update working note: `working-notes/{scenario}-learnings-{date}.md`
   - List observations NOT acted on with rationale
   - Follow template from sleep-sounds-session-learnings-2026-02-10.md
   - Set expiration date: 2 weeks default per Tier 3 docs

### Example: From Observation to Skill Update

**From family-utility eval (Issue 1):**

**Observation**: Design Lens raised empty state (Finding 5) but did NOT explicitly raise accessibility as a finding. Accessibility appeared in project-state.yaml but wasn't evaluated by Review Lenses.

**Generality test**: All UI applications need accessibility evaluation. This isn't family-utility-specific.

**Decision**: Update skill immediately (hard failure of must-do criterion).

**Skill update**: Modified `skills/review-lenses/SKILL.md` — Design Lens now explicitly evaluates accessibility for all UI applications, ensuring it appears as a finding (not just in project-state).

**Commit message**: "Fix accessibility evaluation gap found in family-utility eval: Design Lens must explicitly evaluate accessibility for UI apps. See eval-history/family-utility-2026-02-10.md Issue 1"

**Provenance**: Updated `skills_updated` field in eval result with: `{ file: "skills/review-lenses/SKILL.md", change: "Made accessibility evaluation mandatory for UI apps" }`

---

## D. Regression Detection

### Baseline Approach (v1)

**Establish baseline**
- Each scenario has a baseline eval result (first pass or most recent)
- Baseline filename: `eval-history/{scenario}-baseline.md` (symlink or copy of most recent)
- Or: identify baseline by date in doc-manifest or eval result notes

**When to check for regressions**
- After any skill modification
- Before committing framework changes
- Before releases (run all scenarios)

**Process**

1. **Identify affected scenarios**
   - C2 change → all scenarios (classification affects all)
   - C1 change → all scenarios (orchestration affects all)
   - C3 change → all scenarios (artifacts affect all)
   - C4 change → all scenarios (review affects all)
   - C5 change → all scenarios (project-state affects all)
   - Component-specific change → only scenarios testing that component

2. **Re-run affected scenarios**
   - Use simulation for speed (acceptable for regression check)
   - Full rubric evaluation not required — focus on must-do/must-not-do
   - Record results as usual: `eval-history/{scenario}-{new-date}.md`

3. **Compare results**
   - Manual diff: `diff eval-history/{scenario}-baseline.md eval-history/{scenario}-{new-date}.md`
   - Focus on YAML frontmatter: pass/partial/fail counts per component
   - Check must-do/must-not-do sections for new failures

4. **Investigate regressions**
   - **Regression definition**: Previously-passing criterion now fails OR new must-not-do violation
   - **Not a regression**: New rubric criterion (stricter eval), quality criteria shift, unable-to-evaluate count change

5. **Act on regressions**
   - **If skill regression**: Revert skill change or fix the regression before committing
   - **If rubric evolution**: Update baseline, note reason in commit message
   - **If test scenario changed**: Update baseline, document why in scenario file

### Regression Examples

**True regression:**
```diff
  C2_domain_analyzer:
-   pass: 15, partial: 0, fail: 0, unable: 2
+   pass: 14, partial: 0, fail: 1, unable: 2
```
→ Must investigate: What criterion now fails? Why? Is the skill change causing it?

**Not a regression (rubric tightened):**
```diff
  # Scenario rubric added new must-do: "Must ask about cost sensitivity"
  C2_domain_analyzer:
-   pass: 15, partial: 0, fail: 0, unable: 2
+   pass: 16, partial: 0, fail: 0, unable: 2  # new criterion passes
```
→ This is rubric evolution, not skill regression. Update baseline.

**Not a regression (unable-to-evaluate increased):**
```diff
  C1_orchestrator:
-   pass: 7, partial: 0, fail: 0, unable: 5
+   pass: 7, partial: 0, fail: 0, unable: 6
```
→ New rubric criterion requires interactive eval. Not a regression; update baseline.

### Future (v2+)

Automated regression suite:
- Machine-parseable YAML frontmatter enables scripted comparison
- Automated scenario runner: `./scripts/run-all-scenarios.sh`
- Regression report: shows pass/fail deltas per component
- CI integration: block commits that regress any scenario

---

## E. Simulation vs. Interactive Evaluation

### Capabilities by Evaluator Type

| Criterion Type | Simulation | Interactive | Notes |
|----------------|------------|-------------|-------|
| Classification correctness | ✓ | ✓ | Check project-state.yaml fields |
| Artifact structure/frontmatter | ✓ | ✓ | Mechanical checks |
| Artifact content accuracy | ✓ | ✓ | Entity presence, test specificity |
| Discovery question count | ✓ | ✓ | Count from change_log or inference |
| Vocabulary calibration | ✗ | ✓ | Requires transcript analysis |
| Question ordering by impact | ✗ | ✓ | Requires transcript analysis |
| Plain language usage | ✗ | ✓ | Requires transcript analysis |
| Stage transition naturalness | ✗ | ✓ | Requires transcript analysis |
| Pacing proportionality | ✗ | ✓ | Subjective; transcript needed |
| "User feels interrogated" | ✗ | ✓ | Subjective; transcript needed |

### Transcript Analysis Procedures

When using interactive evaluation, follow these procedures for conversation-quality criteria:

**1. Capture full transcript**
   - Record complete conversation with clear turn boundaries
   - Format:
     ```markdown
     **User:** [exact user message]

     **System:** [exact system response]

     **User:** [next user message]
     ```

**2. For each conversation-quality criterion**
   - Quote specific evidence from transcript
   - Explain why it passes/partial/fails
   - Example:
     ```markdown
     | 2 | Questions use plain language | PASS | System asked "Where will you use this?" not "What's your target platform?" |
     ```

**3. Rate subjective criteria**
   - "User feels interrogated": Count question rounds, assess pacing, note if user showed impatience
   - "Stage transitions natural": Check for abrupt shifts, clear communication of next steps
   - "Vocabulary matches expertise": Identify technical terms used, check if appropriate for persona

**4. Document unable-to-evaluate**
   - For simulation-based evals, mark conversation criteria as "unable-to-evaluate"
   - Reason: "Needs transcript" or "Simulation produces outputs, not conversation"

### Cost-Benefit Analysis

**Simulation**
- **Time cost**: 10-20 minutes per scenario
- **Monetary cost**: ~$0.50-2.00 per scenario (API costs)
- **Coverage**: ~60-80% of rubric criteria (excludes conversation quality)
- **Best for**: Regression checks, initial validation, mechanical criteria

**Interactive**
- **Time cost**: 45-90 minutes per scenario (conversation + evaluation)
- **Monetary cost**: Human time >> API costs
- **Coverage**: 100% of rubric criteria
- **Best for**: Baseline establishment, conversation quality validation, new scenario testing

**Recommendation**: Use simulation for most regression checks, reserve interactive for:
- First baseline run of each scenario
- When conversation-quality issues are suspected
- Before major releases (run at least 1-2 scenarios interactively)

---

## F. Evaluating the Evaluation (Meta-Learning)

**Purpose**: Apply the framework's learning principles to the eval process itself. After each eval, critique not just what was found, but *how* it was found. Every eval should make the next eval better.

### Post-Eval Meta-Review Questions

After recording eval results, answer these questions:

**1. Rubric Quality**
- Were any criteria ambiguous or hard to evaluate?
- Did any criteria prove redundant (always pass together, always fail together)?
- Were there important observations that the rubric missed?
- Did severity levels (blocking/warning/note) feel calibrated correctly?

**2. Scenario Design**
- Did the test persona responses produce the expected conversation?
- Were scripted responses missing for topics the system asked about?
- Did the input prompt signal the right classification?
- Was the scenario too easy/hard for its stated risk level?

**3. Evaluation Method**
- Was simulation appropriate, or did we need interactive?
- How many criteria were "unable-to-evaluate" due to method choice?
- Did the evaluation take longer than expected? Why?
- Were there mechanical checks we could have automated?

**4. Process Friction**
- What steps in setup/execution/recording were tedious or error-prone?
- Did we forget any steps? (If yes, update checklists)
- Were cross-references between rubric and results hard to maintain?
- Did we discover the eval result template was missing something?

### Recording Meta-Learnings

Add this section to each eval result file (after "Observations NOT Acted On"):

```markdown
## Meta-Observations (Eval Process Itself)

### Rubric Improvements Needed
- [Criterion that was ambiguous, with proposed clarification]
- [Redundant criteria that could be merged]
- [Missing coverage area that should be added]

### Scenario Design Issues
- [Scripted response gaps encountered]
- [Input prompt signals that didn't work as expected]

### Process Improvements
- [Friction points in setup/execution/recording]
- [Automation opportunities identified]
- [Template or checklist updates needed]

### Method Appropriateness
- [Should this have been interactive instead of simulation?]
- [Which unable-to-evaluate criteria were most costly?]
```

### Evolution Process

| Meta-Learning Type | Action | Frequency |
|-------------------|--------|-----------|
| **Rubric ambiguity** | Update scenario file, note in commit message | Immediately after eval |
| **Rubric gaps** | Add criterion to scenario, re-eval if critical | Immediately if pattern, defer if single instance |
| **Scenario design issue** | Update scenario file (input, responses, persona) | Immediately after eval |
| **Process friction** | Update evaluation-methodology.md or templates | After 2-3 evals show pattern |
| **Method choice** | Update "Sim vs. Interactive" decision matrix | After pattern across multiple scenarios |

### Examples from Actual Evals

**From family-utility-2026-02-10.md, Issue 2:**
> "Finding count slightly exceeds guideline. Several are positive observations inflating count."

**Meta-learning**: Rubric unclear about whether positive observations count toward finding limit.

**Action taken**: Updated review-lenses skill to clarify "findings are actionable issues, not positive reinforcement."

**Process improvement**: Future rubrics should specify "findings = issues requiring action."

**From static-personal-site ad-hoc eval:**
> "Framework had no mechanism to prompt reflection on its own proportionality during product use."

**Meta-learning**: Testing a simpler-than-expected product exposed gap in framework self-awareness.

**Action taken**: Added Framework Reflection Protocol to Orchestrator.

**Scenario design**: Consider adding "ultra-minimal product" as a formal test scenario.

### Why Meta-Learning Matters

- **HR5 (No Confidence Without Basis)**: If our rubrics are ambiguous, our eval results aren't trustworthy
- **Learn Slowly**: Eval methodology evolves based on patterns, not single-eval reactions
- **Apply Framework to Itself**: We demand good test specs from user products; our eval rubrics deserve the same scrutiny
- **Continuous Improvement**: Each eval should make the next eval better

---

## G. Recording Format

### File Naming

```
eval-history/{scenario-name}-{YYYY-MM-DD}.md
```

**Examples:**
- `eval-history/family-utility-2026-02-10.md`
- `eval-history/background-data-pipeline-2026-02-11.md`

**If multiple runs same day:**
- `eval-history/family-utility-2026-02-10-2.md`

### Required YAML Frontmatter

```yaml
---
scenario: background-data-pipeline     # Which test scenario was run
date: 2026-02-11                       # When evaluation was performed
evaluator: claude-simulation           # claude-simulation | claude-interactive | human
framework_version: abc1234             # Git SHA at eval time
result:
  pass: 0                              # Total criteria passed
  partial: 0                           # Partially met
  fail: 0                              # Failed
  unable_to_evaluate: 0                # Could not assess (e.g., needs transcript)
  by_component:                        # Breakdown per component
    C2_domain_analyzer: { pass: 0, partial: 0, fail: 0, unable: 0 }
    C1_orchestrator: { pass: 0, partial: 0, fail: 0, unable: 0 }
    C3_artifact_generator: { pass: 0, partial: 0, fail: 0, unable: 0 }
    C4_review_lenses: { pass: 0, partial: 0, fail: 0, unable: 0 }
    C5_project_state: { pass: 0, partial: 0, fail: 0, unable: 0 }
    end_to_end: { pass: 0, partial: 0, fail: 0, unable: 0 }
skills_updated: []                     # List of modified skill files with brief change description
notes: ""                              # Free-form observations, limitations, context
---
```

### Body Structure

```markdown
# {Scenario Name} Evaluation Results

**Scenario:** {name} | **Date:** {date} | **Evaluator:** {type} | **Framework:** {SHA}

## Domain Analyzer (C2)

### Must-do

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | [criterion text] | PASS/PARTIAL/FAIL/UNABLE | [specific evidence or "Needs transcript"] |
| 2 | [criterion text] | PASS | [evidence] |

### Must-not-do

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | [criterion text] | PASS | [evidence] |

### Quality criteria

| # | Criterion | Result | Notes |
|---|-----------|--------|-------|
| 1 | [criterion text] | PASS | [explanation or "Needs transcript"] |

**C2 score: X/Y must-do/must-not-do PASS, X/Y quality criteria PASS**

---

## Orchestrator (C1)

[Same table format as C2]

**C1 score: X/Y evaluable criteria PASS, X criteria need transcript**

---

## Artifact Generator (C3)

[Same table format as C2]

**C3 score: X/Y PASS, X/Y quality criteria PASS**

---

## Review Lenses (C4)

[Same table format as C2]

**C4 score: X/Y must-do/must-not-do PASS, X/Y quality criteria PASS**

---

## Project State (C5)

### Must-do (structural)

[Table format]

### Must-do (content)

[Table format]

### Must-not-do

[Table format]

### Quality criteria

[Table format]

**C5 score: X/Y PASS, X/Y quality criteria PASS**

---

## End-to-End Success Criteria

| # | Criterion | Result |
|---|-----------|--------|
| 1 | [criterion] | PASS |

---

## Summary

| Component | Pass | Partial | Fail | Unable to Evaluate |
|-----------|------|---------|------|--------------------|
| C2 Domain Analyzer | 0 | 0 | 0 | 0 |
| C1 Orchestrator | 0 | 0 | 0 | 0 |
| C3 Artifact Generator | 0 | 0 | 0 | 0 |
| C4 Review Lenses | 0 | 0 | 0 | 0 |
| C5 Project State | 0 | 0 | 0 | 0 |
| End-to-End | 0 | 0 | 0 | 0 |
| **Total** | **0** | **0** | **0** | **0** |

## Issues Requiring Skill Updates

### Issue 1: [Title]

**Problem:** [What failed or was partial]

**Evidence:** [From rubric evaluation]

**Generality test:** [Does this apply to other product shapes?]

**Fix:** [What skill was changed and how]

**Skill updated:** `path/to/skill.md` — brief description

### Issue 2: [Title]

[Repeat for each issue]

## Observations NOT Acted On

[What was noticed but intentionally not changed, with rationale]

**Example:**
- **Observation**: System didn't ask about [specific topic]
- **Decided against**: Tier 2 Q5 already asks about [general pattern]. One session doesn't justify new enumerated concern (Learn Slowly principle).
- **Watch for**: If this recurs in future sessions, consider [action]

## Meta-Observations (Eval Process Itself)

### Rubric Improvements Needed
- [Criterion that was ambiguous, with proposed clarification]
- [Redundant criteria that could be merged]
- [Missing coverage area that should be added]

### Scenario Design Issues
- [Scripted response gaps encountered]
- [Input prompt signals that didn't work as expected]

### Process Improvements
- [Friction points in setup/execution/recording]
- [Automation opportunities identified]
- [Template or checklist updates needed]

### Method Appropriateness
- [Should this have been interactive instead of simulation?]
- [Which unable-to-evaluate criteria were most costly?]
```

---

## Summary

This methodology systematizes evaluation, learning extraction, and continuous improvement. Key principles:

- **Structure enables learning**: Even non-deterministic outputs can be evaluated systematically
- **Learn slowly**: Update skills based on patterns, not single instances
- **Meta-learning**: Improve the eval process itself by critiquing rubrics, scenarios, and methods
- **Provenance**: Every skill change references the eval that prompted it
- **Regression awareness**: Compare current results to baselines to detect unintended changes

For the required YAML frontmatter format and additional context, see CLAUDE.md § "Recording Evaluation Results".
