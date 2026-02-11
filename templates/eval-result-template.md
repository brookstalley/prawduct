---
scenario: [scenario-name]              # e.g., family-utility, background-data-pipeline
date: YYYY-MM-DD                       # When evaluation was performed
evaluator: [type]                      # claude-simulation | claude-interactive | human
framework_version: [git-sha]           # Git SHA at eval time (git rev-parse --short HEAD)
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
                                       # Example: { file: "skills/review-lenses/SKILL.md", change: "Made accessibility evaluation mandatory for UI apps" }
notes: ""                              # Free-form observations, limitations, context
---

# [Scenario Name] Evaluation Results

**Scenario:** [scenario-name] | **Date:** YYYY-MM-DD | **Evaluator:** [type] | **Framework:** [git-sha]

## Domain Analyzer (C2)

### Must-do

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | [Copy criterion from scenario rubric] | PASS/PARTIAL/FAIL/UNABLE | [Specific evidence from project-state.yaml or artifacts, or "Needs transcript"] |
| 2 | [Criterion] | PASS | [Evidence] |

### Must-not-do

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | [Copy criterion from scenario rubric] | PASS | [Evidence] |

### Quality criteria

| # | Criterion | Result | Notes |
|---|-----------|--------|-------|
| 1 | [Copy criterion from scenario rubric] | PASS | [Explanation or "Needs transcript"] |

**C2 score: X/Y must-do/must-not-do PASS, X/Y quality criteria PASS**

---

## Orchestrator (C1)

### Must-do

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | [Criterion] | PASS | [Evidence] |

### Must-not-do

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | [Criterion] | PASS | [Evidence] |

### Quality criteria

| # | Criterion | Result | Notes |
|---|-----------|--------|-------|
| 1 | [Criterion] | PASS | [Notes] |

**C1 score: X/Y evaluable criteria PASS, X criteria need transcript**

---

## Artifact Generator (C3)

### Must-do

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | [Criterion] | PASS | [Evidence] |

### Must-not-do

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | [Criterion] | PASS | [Evidence] |

### Quality criteria

| # | Criterion | Result | Notes |
|---|-----------|--------|-------|
| 1 | [Criterion] | PASS | [Notes] |

**C3 score: X/Y PASS, X/Y quality criteria PASS**

---

## Review Lenses (C4)

### Must-do

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | [Criterion] | PASS | [Evidence] |

### Must-not-do

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | [Criterion] | PASS | [Evidence] |

### Quality criteria

| # | Criterion | Result | Notes |
|---|-----------|--------|-------|
| 1 | [Criterion] | PASS | [Notes] |

**C4 score: X/Y must-do/must-not-do PASS, X/Y quality criteria PASS**

---

## Project State (C5)

### Must-do (structural)

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | [Criterion] | PASS | [Evidence] |

### Must-do (content)

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | [Criterion] | PASS | [Evidence] |

### Must-not-do

| # | Criterion | Result | Evidence |
|---|-----------|--------|----------|
| 1 | [Criterion] | PASS | [Evidence] |

### Quality criteria

| # | Criterion | Result | Notes |
|---|-----------|--------|-------|
| 1 | [Criterion] | PASS | [Notes] |

**C5 score: X/Y PASS, X/Y quality criteria PASS**

---

## End-to-End Success Criteria

| # | Criterion | Result |
|---|-----------|--------|
| 1 | [Criterion from scenario] | PASS |
| 2 | [Criterion] | PASS |

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

---

## Issues Requiring Skill Updates

### Issue 1: [Descriptive Title]

**Problem:** [What failed or was partial? Which criterion(s)?]

**Evidence:** [From rubric evaluation — quote specific values from project-state.yaml, artifacts, or transcript]

**Generality test:** [Does this apply to other product shapes? Mentally test against family-utility, background-pipeline, B2B API, etc.]

**Fix:** [What skill was changed and how? Be specific about what instruction was added/modified/removed]

**Skill updated:** `path/to/skill.md` — [Brief description of change]

### Issue 2: [Title]

[Repeat for each issue that requires skill changes]

---

## Observations NOT Acted On

[What was noticed but intentionally not changed, with rationale. This is critical for "Learn Slowly" — document why you're NOT reacting to single instances.]

**Example format:**

**Observation:** System didn't ask about [specific topic].

**Decided against:** [Explain why this doesn't warrant a skill change yet]
- Is there an existing general principle that should have covered this?
- Is this specific to one scenario or generalizable?
- Is this one instance, or a pattern across multiple evals?

**Watch for:** If this recurs in [condition], consider [potential action].

---

## Meta-Observations (Eval Process Itself)

### Rubric Improvements Needed
- [Criterion that was ambiguous — what made it hard to evaluate?]
- [Redundant criteria that could be merged — which ones always pass/fail together?]
- [Missing coverage area — what did we observe that the rubric didn't check?]

### Scenario Design Issues
- [Scripted response gaps — did system ask about a topic not covered in test conversation?]
- [Input prompt signals — did the input produce the expected classification?]
- [Persona behavior — was the test persona realistic and consistent?]

### Process Improvements
- [Friction in setup/execution/recording — what steps were tedious or error-prone?]
- [Automation opportunities — what could be scripted or mechanized?]
- [Template or checklist updates — did we miss steps in the methodology?]

### Method Appropriateness
- [Should this have been interactive instead of simulation? Why?]
- [Which unable-to-evaluate criteria were most costly to miss?]
- [Did the evaluation take longer than expected? What slowed it down?]

---

## Notes

[Additional context, observations, or insights that don't fit above categories]

