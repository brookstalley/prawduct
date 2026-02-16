# Multi-Layer Meta-Analysis: Background Data Pipeline Evaluation
**Date:** 2026-02-11
**Created:** 2026-02-11
**Expires:** 2026-02-25 (Tier 3, 2-week expiration)

## Purpose
Comprehensive critical analysis of the background-data-pipeline evaluation at ALL layers: scenario success, efficiency, automatic observation capture, test quality, and meta-learnings about the evaluation process itself.

User requested: "Question EVERYTHING. What can we improve?"

---

## Layer 1: Did the Scenario Succeed?

### Results Summary
- **70.6% criteria evaluable** (72/102) - simulation limitations prevented conversation quality assessment
- **Of evaluable criteria**: 84.7% PASS, 12.5% PARTIAL, 2.8% FAIL
- **Classification**: ✓ Correct (automation-pipeline, NOT ui-application)
- **Artifacts**: ✓ All 12 generated (7 universal + 5 automation-specific)
- **Review Lenses**: ✗ Not run (blocking issue)

### Critical Finding: **Phase Mismatch**

**The test scenario expects Phase 2 capabilities, but we're testing a Phase 1 framework.**

Evidence:
- Scenario header: "Phase: 2 (product shape diversity)"
- Domain Analyzer: "Automation/Pipeline (Phase 2)" - no discovery questions implemented
- Artifact Generator: "Shape-specific artifacts are added in Phase 2"
- Yet scenario rubric REQUIRES: pipeline architecture, scheduling, monitoring, failure recovery, configuration specs

**What actually happened**: The simulation succeeded by improvising BEYOND the framework's documented capabilities. The Task agent generated Phase 2 artifacts even though the framework doesn't officially support them yet.

**Implication**: Cannot fairly evaluate framework against capabilities it doesn't claim to have. Many "PASS" results are actually "agent went beyond Phase 1 scope."

**Recommendation**: Mark this scenario as Phase 2 baseline - don't run until automation shape support is officially added to framework.

---

## Layer 2: Did Observation Capture Work?

### **CRITICAL FAILURE: No Observations Captured**

We implemented automatic observation capture this morning (`framework-observations/` with mandatory capture at stage transitions). **This eval should have automatically created observation entries. It didn't.**

Evidence:
```bash
$ ls framework-observations/
2026-02-11-meta-improvement-loop.yaml  # From earlier (the irony!)
README.md                              # From implementation
schema.yaml                            # From implementation
```

**Expected**: `2026-02-11-background-pipeline-eval.yaml` documenting:
- Phase 2 capability gap observed during classification
- Discovery question improvisation required
- Operational artifacts generated beyond framework scope

**What went wrong**:
1. Task agent ran stages 0 → 0.5 → 1 → 2 → 3
2. Orchestrator skill § Mandatory Observation Capture says: "At every stage transition, write observations to framework-observations/"
3. Agent either:
   - Didn't read the updated Orchestrator skill (cached version?)
   - Read it but didn't follow the instruction (new, not reinforced?)
   - Determined no significant observations (unlikely given obvious Phase 2 mismatch)

**The meta-irony**: We built a self-improvement system to avoid manual observation invocation. Then the first eval AFTER building it failed to use it. We failed to observe our observation system's failure automatically.

**Immediate action taken**: Manually created `2026-02-11-background-pipeline-eval.yaml` with 6 observations about Phase 2 gap, observation capture failure, Review Lenses gap, rubric issues.

**Next steps**:
1. Make observation capture BLOCKING (not optional): Orchestrator must verify file created before stage transition
2. Add observation verification to eval methodology checklist
3. Investigate why Task agent didn't follow instruction (skill too new? needs reinforcement? instruction unclear?)

---

## Layer 3: Was the Test Scenario Well-Designed?

### Scenario Quality Assessment

#### **Strengths** ✓
- **Clear input prompt**: Signals automation (schedule, unattended), technical user (RSS, Slack), clear pain point
- **Comprehensive persona**: Alex Chen has defined technical level, needs, constraints
- **Detailed scripted responses**: 11 topic areas covered
- **Concrete rubric criteria**: 102 specific must-do/must-not-do/quality checks

#### **Issues** ⚠

**Issue 1: Phase 2 Expectations on Phase 1 Framework**
- Scenario requires capabilities framework doesn't have yet
- Should have "Prerequisites" section: "Requires Phase 2 automation support"

**Issue 2: Rubric Over-Weighted Toward Interactive Criteria**
- 30/102 criteria (29.4%) require transcript analysis (UNABLE in simulation)
- Question: If simulation can only evaluate 70%, is the rubric poorly designed for simulation testing?
- Counterpoint: Maybe scenario is meant for interactive baseline only?

**Issue 3: Subjective "Proportionate" Criteria**
- Multiple criteria use terms like "proportionate", "substantive", "actionable" without concrete thresholds
- Examples:
  - "Monitoring spec is substantive" - how many alert conditions is substantive? What makes them non-generic?
  - "Output proportionate to risk level" - proportionate compared to what baseline?
- Makes evaluation inconsistent across evaluators

**Issue 4: Rubric Length (102 Criteria)**
- Is this sustainable? Took ~35 minutes to evaluate against rubric
- Multiply by 5 scenarios = ~3 hours just for rubric evaluation (not including simulation run)
- Some criteria may be redundant:
  - "Surface monitoring" (discovery) + "Monitoring spec substantive" (artifact) - both needed or consolidate?

#### **Recommendations**

1. **Add Prerequisites Section**:
```markdown
## Prerequisites
- Framework Phase: 2 (automation shape support)
- Required Skills: Domain Analyzer automation questions, Artifact Generator automation templates
- Blockers: This scenario cannot run until Phase 2 automation support is implemented
```

2. **Make Subjective Criteria Concrete**:
```markdown
# Instead of:
"Monitoring spec is substantive"

# Write:
"Monitoring spec includes at least 3 alert conditions with specific triggers (e.g., 'no articles for 2 consecutive days') and clear actions (e.g., 'post to #alerts channel'), not generic recommendations ('implement monitoring')"
```

3. **Separate Simulation vs. Interactive Criteria**:
```markdown
## Simulation-Evaluable Criteria (run first for quick regression checks)
- Classification correctness
- Artifact structure and presence
- Cross-reference validation

## Interactive-Only Criteria (baseline establishment only)
- Conversation quality and pacing
- Vocabulary calibration
- Stage transition naturalness
```

4. **Consider Rubric Budget**: Should scenarios have a max criterion count? E.g., "Phase 1 scenarios: 40-60 criteria max, Phase 2: 60-80"?

---

## Layer 4: Was the Evaluation Process Efficient?

### Time Breakdown
- **Simulation run**: ~25 minutes (artifacts timestamped 10:00-10:19)
- **Rubric evaluation**: ~35 minutes (going through 102 criteria, many UNABLE)
- **Meta-analysis**: ~30 minutes (this document, observation creation)
- **Total**: ~90 minutes

### Efficiency Analysis

**Compared to interactive eval** (45-90 min per methodology):
- Simulation saved ~0 minutes because we still spent 60 min on eval + meta-analysis
- But simulation was run by Task agent autonomously (I could do other work in parallel)

**Process friction identified**:

1. **No mechanical validation scripts**
   - Had to manually check: artifact presence, frontmatter structure, schema compliance
   - These could be scripted: `./scripts/validate-project-state.sh /tmp/eval-background-pipeline/`

2. **Observation capture not verified**
   - Had to manually check framework-observations/ directory to discover failure
   - Should be in eval checklist: "✓ Observation file exists"

3. **Review Lenses not run - discovered late**
   - Noticed during C4 evaluation that lenses weren't executed
   - Should be caught earlier: Task agent should report "Review Lenses complete" before finishing

4. **UNABLE criteria inflation**
   - 30 UNABLE criteria still required evaluation (had to consider each and mark UNABLE)
   - If simulation known to produce ~30% UNABLE, can we pre-filter rubric?

**Automation opportunities**:

1. **Mechanical validation script**:
```bash
#!/bin/bash
# scripts/validate-eval-output.sh
PROJECT_DIR=$1
SCENARIO=$2

# Check project-state schema
python scripts/validate-schema.py $PROJECT_DIR/project-state.yaml

# Check artifact presence (expect 7 universal + shape-specific)
python scripts/check-artifacts.py $PROJECT_DIR/artifacts/

# Check observation file exists
if [ ! -f "framework-observations/$(date +%Y-%m-%d)-${SCENARIO}-eval.yaml" ]; then
  echo "ERROR: No observation file created"
  exit 1
fi

echo "Mechanical validation: PASS"
```

2. **Cross-reference validator**:
```python
# Check entities in data-model appear in test-specs
# Check dependencies in frontmatter match actual references
# Check risk factors mentioned in NFRs
```

3. **Simulation-appropriate rubric filter**:
```bash
# Generate reduced rubric with only simulation-evaluable criteria
./scripts/filter-rubric.sh background-data-pipeline simulation
```

### Efficiency Verdict

**Current process**: Reasonable for first run, but doesn't scale to 5 scenarios × multiple regression checks.

**Next iteration should**:
- Add mechanical validation (saves ~10 min per eval)
- Verify observation capture automatically (saves discovering failures)
- Create simulation-filtered rubrics (reduces UNABLE overhead)
- Consider parallel simulation runs (all 5 scenarios simultaneously if independent)

---

## Layer 5: Meta-Learnings (Evaluating the Evaluation)

### What We Learned About Our Learning System

**Finding 1: Building a Feature ≠ Feature Works**

We built observation capture with:
- ✓ Directory structure (framework-observations/)
- ✓ Schema definition (observation entry format)
- ✓ Orchestrator instructions (write at stage transitions)
- ✓ Documentation (README with guidelines)

But we didn't verify:
- ✗ Skill actually invoked in practice
- ✗ Output files actually created
- ✗ Observations actually useful for pattern detection

**Lesson**: Test-your-tests principle applies to meta-features. If observation capture fails silently, we've built a self-improvement system that doesn't self-improve.

**Action**: Add verification layer - every new framework feature needs a "Does it actually work?" test.

---

**Finding 2: Manual Meta-Improvement Still Required**

Even with observation capture implemented, this meta-analysis was MANUAL:
- I had to notice observation capture didn't work
- I had to manually create the observation file
- I had to manually analyze rubric quality
- I had to manually identify process friction

**Question**: Can we make meta-improvement automatic too?

**Partial answer**: Some can be scripted:
- Observation file presence → automated check
- Rubric UNABLE percentage → automated metric
- Eval time tracking → automated logging

But deep analysis ("Is the rubric over-weighted toward interactive criteria?") requires human judgment... for now.

**Lesson**: Self-improvement has layers. Layer 1 (capture observations) can be automatic. Layer 2 (analyze patterns) needs thresholds and rules. Layer 3 (improve the improvement system) still requires human insight.

---

**Finding 3: Phase Discipline Matters**

Phase 1 is "family utility vertical slice" - UI application only.

Yet we ran a Phase 2 scenario (automation/pipeline) against Phase 1 framework and got:
- Mixed results (some PASS, some improvisation)
- Unclear evaluation (is framework failing or scenario premature?)
- Wasted time (can't fairly assess capabilities that don't exist)

**Lesson**: Phase gates exist for a reason. Don't run Phase 2 scenarios until Phase 2 framework is built.

**Action**: Mark scenarios with explicit phase requirements. Block execution if prerequisites not met.

---

**Finding 4: Simulation Has a Role, But Know Its Limits**

Simulation was valuable for:
- ✓ Classification testing (automation-pipeline correctly identified)
- ✓ Artifact generation testing (12 artifacts produced)
- ✓ Schema compliance (project-state structure valid)
- ✓ Autonomous execution (Task agent ran without intervention)

Simulation failed for:
- ✗ Conversation quality (knowledge bleed, no transcript)
- ✗ Review Lenses (weren't executed - framework gap)
- ✗ Discovery question evaluation (improvised beyond framework)

**Lesson**: Simulation is good for mechanical regression checks (artifact structure, classification logic). Interactive is required for baseline establishment (conversation quality, pacing, user calibration).

**Action**: Create "simulation checklist" and "interactive checklist" for each scenario. Run simulation first (fast), then interactive for baseline (thorough).

---

**Finding 5: Rubric Quality Matters As Much As Framework Quality**

We spent significant effort evaluating:
- What does "proportionate" mean?
- Is "substantive" a measurable criterion?
- Should design_decisions exist for non-UI products?

These are rubric design questions, not framework implementation questions.

**Lesson**: Bad rubrics produce low-confidence evaluations. "The framework passed the test" only means something if the test is good.

**Action**: Apply framework principles to test scenarios too:
- HR5 (No Confidence Without Basis): Criteria must be verifiable, not subjective
- HR3 (No Documentation Fiction): Rubrics describe observable behavior, not intent
- Specificity over enumeration: "At least 3 alert conditions" not "adequate monitoring"

---

## Layer 6: What Can We Improve? (Comprehensive Recommendations)

### Immediate (This Week)

1. **Fix observation capture**:
   - Investigate why Task agent didn't write observations
   - Make capture BLOCKING (stage transition fails if no observation file)
   - Add verification to eval methodology checklist

2. **Fix Review Lenses execution**:
   - Ensure lenses run in Stage 3 simulation
   - Add explicit "run review lenses" to Task agent prompt
   - Verify review findings documented in output

3. **Mark background-pipeline as Phase 2**:
   - Add Prerequisites section to scenario
   - Don't run again until automation support implemented
   - Create simpler Phase 1 automation scenario if needed

### Short-Term (Next 2 Weeks)

4. **Create mechanical validation scripts**:
   - Schema validator for project-state.yaml
   - Artifact presence checker
   - Cross-reference validator (entities in data-model → test-specs)
   - Observation file existence checker

5. **Make rubric criteria concrete**:
   - Replace "proportionate" with examples and thresholds
   - Replace "substantive" with minimum requirements
   - Add "Good example" / "Bad example" to subjective criteria

6. **Separate simulation vs. interactive rubrics**:
   - Mark each criterion as "simulation" or "interactive"
   - Generate filtered rubrics for each eval type
   - Set UNABLE threshold (>40% = requires interactive)

### Medium-Term (Phase 2)

7. **Add automation shape support to framework**:
   - Domain Analyzer: Tier 1-3 discovery questions for automation/pipeline
   - Artifact Generator: automation-specific artifact templates
   - Run background-pipeline scenario as Phase 2 baseline

8. **Build pattern detection (C8b)**:
   - Script to parse framework-observations/
   - Group observations by type + skills_affected
   - Apply thresholds (1 = noted, 2-3 = watch, 4+ = propose skill update)
   - Generate pattern-reports/

9. **Optimize eval efficiency**:
   - Parallel simulation runs (all scenarios simultaneously)
   - Mechanical validation before manual rubric evaluation
   - Pre-filtered rubrics (simulation-appropriate subset)
   - Target: <15 minutes per simulation, <60 minutes per interactive

### Long-Term (Phase 3 / v2)

10. **Automated regression suite**:
    - `./scripts/run-all-scenarios.sh` - runs all Phase 1 scenarios in simulation
    - Compares results to baseline
    - Generates regression report (pass/fail deltas per component)
    - CI integration (block commits that regress scenarios)

11. **Learning proposer (C8d)**:
    - Takes pattern reports
    - Generates proposed skill diffs
    - Runs adversarial validation (apply to historical evals, check if improves or regresses)
    - Creates PR with human approval required

12. **Self-application test**:
    - Run Prawduct through Prawduct
    - Use framework to design framework improvements
    - The compiler-compiles-itself test

---

## Summary: Did We Question Everything?

### Questions Asked

✓ **Did the scenario succeed?** Mixed - 84.7% pass rate on evaluable criteria, but Phase 2 mismatch invalidates some results.

✓ **Was observation capture automatic?** No - critical failure, manually created observations post-hoc.

✓ **Is the test scenario well-designed?** Partially - good persona and input, but rubric has subjective criteria, Phase 2 expectations, and 29.4% UNABLE in simulation.

✓ **Is the eval process efficient?** Adequate for first run (~90 min), but doesn't scale. Needs mechanical validation, observation verification.

✓ **What can we improve?** 12 recommendations across 4 time horizons (immediate → long-term).

✓ **Are we improving the improvement process?** Yes - this meta-analysis itself feeds back (now captured in observation file and working notes).

### Most Critical Findings

1. **Observation capture failed** - self-improvement loop not automatic
2. **Phase 2 test on Phase 1 framework** - can't fairly evaluate
3. **Review Lenses not run** - quality gate missing
4. **Rubric has subjective criteria** - reduces evaluation confidence

### Next Actions

**Before next eval**:
- [ ] Fix observation capture (make blocking)
- [ ] Fix Review Lenses execution
- [ ] Create mechanical validation script
- [ ] Mark background-pipeline as Phase 2

**For next scenario (when Phase 1 ready)**:
- [ ] Run family-utility baseline (interactive)
- [ ] Verify observation capture works
- [ ] Verify Review Lenses run
- [ ] Test mechanical validation script

**For framework development**:
- [ ] Add automation support (Phase 2) OR
- [ ] Create simpler Phase 1 automation scenario
- [ ] Build pattern detection for observations
- [ ] Improve rubric concreteness

---

## Meta-Meta Note

This analysis itself should be observed and learned from. Key observation: **We spent 90 minutes on eval, 30 minutes on meta-analysis. Is 1:3 ratio sustainable?**

As evaluation becomes routine, meta-analysis should be faster (templates, patterns, scripts). But first few evals require deep critical examination to build that efficiency.

The goal: Make evaluation-of-evaluation automatic too. When observation capture works, pattern detection should flag:
- "UNABLE percentage spiking (29.4% → 40%+)" → rubric needs interactive criteria separation
- "Eval time increasing (60min → 90min)" → need mechanical validation
- "Observation capture rate dropping (100% → 0%)" → blocking verification required

We're building a learning system about building a learning system. It's meta all the way down - until it's automatic all the way up.

