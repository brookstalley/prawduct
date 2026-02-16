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
2. Criteria annotated `[interactive]` in the rubric are marked `DEFERRED` (not UNABLE) in simulation results
3. After simulation, prompt user: "N criteria require interactive testing. Would you like to run interactive evaluation now?"
4. If yes, run targeted interactive eval for `[interactive]` and `[hybrid]` criteria only
5. Report simulation score separately from deferred count

### Decision Matrix

| Evaluation Need | Type | Evaluator | Typical Duration |
|-----------------|------|-----------|------------------|
| Regression check after skill change | Scenario-based | Simulation | 10-20 min per scenario |
| New scenario baseline | Scenario-based | Interactive | 45-90 min |
| Conversation quality verification | Scenario-based | Interactive | 45-90 min |
| Edge case discovery | Exploratory | Human | Variable |
| Real product validation | Exploratory | Human | Variable |

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

**Recommendation**: Use simulation for most regression checks (covers ~60-80% of criteria). Reserve interactive for first baseline runs, when conversation-quality issues are suspected, and before major releases.

### Eval Mode Annotations

Each rubric criterion in `tests/scenarios/*.md` is annotated with an eval mode:

| Annotation | Meaning | Simulation behavior |
|------------|---------|-------------------|
| `[simulation]` | Evaluable from file outputs (project-state.yaml, artifacts, code) | Evaluate normally |
| `[interactive]` | Requires conversation transcript | Mark as `DEFERRED` (not UNABLE) |
| `[hybrid]` | Partially evaluable from files, fully from transcript | Evaluate what's possible, note limitations |

**Result categories** for annotated evaluations:
- `PASS` / `PARTIAL` / `FAIL` — standard results
- `DEFERRED` — criterion requires interactive evaluation; not counted as a failure
- `UNABLE` — criterion cannot be evaluated for reasons other than eval mode (e.g., prerequisite not met)

**Simulation run reporting**: Report simulation-evaluable results as the primary score. Report deferred count separately: "Simulation score: X/Y PASS (Z criteria deferred to interactive evaluation)." This distinguishes genuine failures from eval mode limitations.

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
   - Expected progression: Stages 0 → 1 → 2 → 3
   - Do not intervene unless system gets stuck or deviates significantly
   - If deviation occurs, note in observations section of results

**5. Capture complete record**
   - **For simulation**: Capture generated project-state.yaml and artifacts/
   - **For interactive**: Additionally capture full conversation transcript with clear user/system turn boundaries

### Delegation to Subagents (When Using Task Tool)

Delegation does not transfer verification responsibility. The coordinating agent must independently verify results.

**Pre-delegation:** Ensure subagent has access to all framework files and instructions include the complete evaluation procedure.

**Post-completion verification (MANDATORY):**

- [ ] Evaluation results file exists: `eval-history/{scenario-name}-{YYYY-MM-DD}.md` with complete YAML frontmatter
- [ ] Spot-check 3-5 rubric criteria have evidence recorded
- [ ] `change_log` has framework reflection entries for each stage (see Recording Results § step 7)
- [ ] If observation file exists, verify field completeness
- [ ] Artifacts were generated (or cleanup already happened and results reference them)
- [ ] Baseline comparison done (if regression check)

If verification fails, document the failure as an observation (type: process_friction) and either re-run or complete missing steps manually.

### Two-Phase Evaluation (Recommended for Build Stages)

When evaluating scenarios that include build stages (Stages 4-6), use a two-phase approach. This is driven by a practical constraint: subagents launched via the Task tool may not have permission to execute runtime commands (npm install, npm test, npm run dev) in temporary directories.

**Phase 1: Document Generation (Stages 0-4)**
- Delegatable to a subagent via Task tool
- Covers: classification, discovery, definition, artifact generation, build planning
- Produces: project-state.yaml, all artifacts, build plan
- Subagent can scaffold the project (mkdir, file writes) but should stop before runtime commands

**Phase 2: Build + Iteration (Stages 5-6)**
- Must run in the main conversation with runtime access
- Covers: Builder execution, Critic governance, iteration cycles
- Requires: node/npm (or equivalent runtime) available and functional

**Pre-Phase-2 checklist:**
- [ ] Verify runtime is available: `node --version && npm --version`
- [ ] Verify Phase 1 output is complete: project-state.yaml, artifacts/, build plan
- [ ] Verify scaffold from Phase 1 (if any) is intact in the eval directory

**Handoff procedure:**
1. Phase 1 subagent completes and returns
2. Main conversation reads all Phase 1 output from the eval directory
3. Main conversation resumes from Stage 5 (or wherever Phase 1 left off)
4. Main conversation completes Stages 5-6 with full runtime access

**Efficiency note:** This approach typically covers ~88% of rubric criteria (all mechanical + build criteria). The remaining ~12% are conversation-quality criteria that require interactive evaluation regardless of phase structure.

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

### Transcript Analysis (Interactive Evaluations Only)

When using interactive evaluation, follow these procedures for conversation-quality criteria:

1. **Capture full transcript** with clear turn boundaries (User/System labels).
2. **Quote specific evidence** for each conversation-quality criterion. Example: `| 2 | Questions use plain language | PASS | System asked "Where will you use this?" not "What's your target platform?" |`
3. **Rate subjective criteria**: count question rounds for pacing, check for abrupt stage transitions, identify vocabulary calibration to persona.
4. **For simulation-based evals**: mark conversation criteria as "unable-to-evaluate" with reason "Needs transcript."

### Recording Results

**This step is mandatory before cleanup.** Unrecorded evaluations are wasted work.

**1. Create results file**
   - Filename: `eval-history/{scenario}-{YYYY-MM-DD}.md`
   - If multiple runs same day: `{scenario}-{YYYY-MM-DD}-2.md`

**2. Add YAML frontmatter**
   - See § F (Recording Format) below for complete template
   - Include: scenario, date, evaluator type, framework version (git SHA)
   - Include: pass/partial/fail/unable counts total and by component
   - Include: skills_updated list (initially empty, fill in after § C)

**3. Document detailed findings**
   - Use table format from § F (Recording Format)
   - For each criterion: result + specific evidence
   - For "unable-to-evaluate": explain why (e.g., "Needs transcript")

**4. Identify issues**
   - List each failed must-do/must-not-do as an issue
   - List each partial pass with explanation
   - List any quality criteria failures
   - Group related findings (e.g., "Orchestrator over-explained in 3 places")

**5. Add meta-observations**
   - See § E (Evaluating the Evaluation) for template
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

**7. Verify framework reflection and observation capture**

   **Tier 1 — BLOCKING (mechanical):**
   - [ ] `change_log` in the eval's `project-state.yaml` has a "Framework reflection" entry for each stage transition (0→1, 1→2, 2→3, completion)
   - [ ] If an observation file exists in `framework-observations/`, each entry has non-empty `type`, `description`, `evidence`, and `severity` fields
   - If either check fails → evaluation is incomplete

   **Tier 2 — WARNING (judgment):**
   - [ ] If an observation file exists, assess substantiveness: do entries identify specific framework issues? (See `framework-observations/README.md` for criteria.)
   - [ ] If no observation file exists, check `change_log` reflection entries — did any identify concerns that warranted capture? (See `framework-observations/README.md` capture criteria.) If so, note as a warning.
   - If warnings → record in meta-observations for process improvement

**8. Learning loop health check (post-eval)**

   After recording results and verifying observation capture, check the health of the learning loop itself:

   - [ ] **Pattern threshold check:** Run `./tools/observation-analysis.sh --patterns-only`. If any observation types have crossed their tier threshold (meta: 2+, build-phase: 3+, product: 4+) and are not yet tracked in `observation_backlog`, add them.
   - [ ] **Stale `noted` check:** If any observations have `status: noted` and are more than 2 days old, they should be triaged — update to `triaged` or `acted_on` and add to `observation_backlog` if deferred.
   - [ ] **Update `last_triage`:** Set `observation_backlog.last_triage` to today's date in `project-state.yaml`.

### Cleanup

**After results are recorded, observations extracted, observation capture verified, learning loop health checked, and all committed to the prawduct repo:**

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

**2b. Assess skill instruction quality.** During evaluation, the evaluator follows skill instructions to produce outputs. After recording product-level results, assess the instructions themselves:
   - Were any skill instructions ambiguous — did you have to guess the intent?
   - Were any instructions hard to find — buried in paragraphs or nested conditionals?
   - Did any instructions contradict each other?
   - Did any skill feel disproportionately long for its purpose?

   If yes to any: capture as observation (type: `skill_quality`, stage: "meta"). This ensures every evaluation run also audits instruction quality, catching cumulative drift that per-change reviews miss.

**3. Generality test**
   - Mentally apply proposed fix to other structural characteristics
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

**5b. Triage remaining observations into `observation_backlog`**
   - For each observation NOT immediately acted on, add to `project-state.yaml` → `observation_backlog`
   - Assign priority: `next` (implement soon), `soon` (next few sessions), or `deferred` (watch for pattern)
   - Include rationale for the priority decision
   - Update observation status from `noted` to `triaged`
   - This ensures no observations are forgotten — they're either acted on or tracked

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

## E. Evaluating the Evaluation (Meta-Learning)

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

## F. Recording Format

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
evaluation_approach:
  mode: simulation                     # simulation | interactive | hybrid
  total_criteria: 0                    # Total rubric criteria
  simulation_evaluable: 0             # [simulation] criteria
  interactive_only: 0                 # [interactive] criteria
  hybrid: 0                           # [hybrid] criteria
  deferred: 0                         # Criteria skipped due to eval mode
result:
  pass: 0                              # Total criteria passed
  partial: 0                           # Partially met
  fail: 0                              # Failed
  deferred: 0                          # Skipped due to eval mode (not a failure)
  unable_to_evaluate: 0                # Could not assess for non-mode reasons
  by_component:                        # Breakdown per component
    C2_domain_analyzer: { pass: 0, partial: 0, fail: 0, deferred: 0, unable: 0 }
    C1_orchestrator: { pass: 0, partial: 0, fail: 0, deferred: 0, unable: 0 }
    C3_artifact_generator: { pass: 0, partial: 0, fail: 0, deferred: 0, unable: 0 }
    C4_review_lenses: { pass: 0, partial: 0, fail: 0, deferred: 0, unable: 0 }
    C5_project_state: { pass: 0, partial: 0, fail: 0, deferred: 0, unable: 0 }
    end_to_end: { pass: 0, partial: 0, fail: 0, deferred: 0, unable: 0 }
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

**Generality test:** [Does this apply to other structural characteristics?]

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

## G. External Best Practice Review

### Purpose

Skill instructions are the framework's primary interface with LLMs. External research on prompt engineering and LLM instruction design evolves continuously. This section defines when and how to compare skills against current best practices, ensuring the framework doesn't drift from effective instruction patterns.

### Review Triggers

**Scheduled (during evaluation):** During any evaluation that includes step 2b (skill instruction quality assessment), additionally check standards S1-S6 from `docs/skill-authoring-guide.md` against the skills exercised in that evaluation. Record violations as observations (type: `external_practice_drift` or `skill_quality` depending on whether the issue is structural drift or general quality degradation).

**Threshold (observation-driven):** When 2+ observations of type `skill_quality` or `external_practice_drift` accumulate against the same skill, trigger a focused review of that skill against all standards in the authoring guide.

**Calendar (periodic):** Every 3 months — or after major model capability changes (new model family, significant behavior shifts) — conduct a full review of all skills against current external research. This involves:
1. Gathering current best practices from authoritative sources (Anthropic docs, peer-reviewed prompt engineering research, major platform guides).
2. Comparing gathered practices against `docs/skill-authoring-guide.md` standards.
3. Updating the guide if new patterns are identified (add standards, update provenance links, revise thresholds).
4. Auditing all skills against the updated guide.
5. Recording findings as observations.
6. Updating `Last external review` date in the authoring guide.

### Procedure

1. **Gather practices.** Consult current sources: Anthropic's prompt engineering documentation, industry guides from major LLM platforms, and any new research on instruction-following accuracy. Focus on structural patterns (how to write instructions) rather than domain-specific techniques.

2. **Compare against guide.** For each gathered practice, check whether `docs/skill-authoring-guide.md` already covers it. If not, assess whether it's relevant to skill authoring (some practices apply to user-facing prompts but not to system instructions).

3. **Update guide.** Add new standards or refine existing ones. Every standard must include: a concrete test, a "why" rationale, and a "derived from" provenance link.

4. **Audit skills.** Apply updated standards to each skill file. Use the same severity framework as the Critic: blocking (would cause wrong behavior), warning (reduces instruction clarity), note (minor improvement opportunity).

5. **Record observations.** Write findings to `framework-observations/` as type `external_practice_drift` with specific evidence and proposed actions.

6. **Act on findings.** Follow the standard observation lifecycle: findings at meta threshold (2+) trigger skill updates through the normal learning extraction process (§ C).

---

## Summary

This methodology systematizes evaluation, learning extraction, and continuous improvement. Key principles:

- **Structure enables learning**: Even non-deterministic outputs can be evaluated systematically
- **Learn slowly**: Update skills based on patterns, not single instances
- **Meta-learning**: Improve the eval process itself by critiquing rubrics, scenarios, and methods
- **Provenance**: Every skill change references the eval that prompted it
- **Regression awareness**: Compare current results to baselines to detect unintended changes

For the required YAML frontmatter format and additional context, see CLAUDE.md § "Recording Evaluation Results".
