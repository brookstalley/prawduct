# Self-Improvement Architecture

**Purpose**: Documents the framework's automatic self-improvement system - the architectural goal, philosophy, implementation approach, and critical requirements that ensure the framework learns without manual intervention.

**Tier**: 1 (Source of Truth)
**Owner**: Framework maintainers
**Last updated**: 2026-02-11

---

## The Goal: Self-Improvement Without Manual Meta-Requests

### The Problem This Solves

**Traditional improvement model**: Someone notices a problem → explicitly requests analysis → manually extracts learnings → manually updates system → hopes the same pattern gets captured next time

**The failure mode**: Even *asking* "how do we improve automatically?" is itself a manual meta-improvement request. This creates infinite regress - every level of meta-improvement requires explicit human intervention.

**The solution**: Make observation an **unavoidable side-effect** of normal framework operation, not an activity someone has to remember to invoke.

### The Architectural Goal

**The framework must improve itself automatically through normal use, without requiring anyone to explicitly request observation, analysis, or improvement.**

This is not a feature. This is an **existential requirement**. A framework that helps users build software but can't reliably improve its own capabilities will ossify. Its advice will drift from reality. Its patterns will lag behind discovered needs.

**Success criteria**:
- Every framework interaction produces structured observations (automatic, not invoked)
- Pattern detection happens on accumulated observations (periodic or threshold-triggered, not manual)
- Skill updates are proposed when patterns cross thresholds (human-approved but auto-generated)
- The system observes its own observation failures (meta-level automatic capture)

---

## The Philosophy: Observation as Side-Effect

### Core Principle

**Observation must be an unavoidable side-effect of framework operation, not an opt-in activity.**

Analogy: Git automatically creates reflog entries when you perform operations. You don't "remember to log." The logging is built into the operation. If git reflog were optional, it would be useless (you'd forget to enable it when you need it most).

Similarly, framework reflection must be **automatic and blocking**:
- Every stage transition records a reflection in `change_log` (not "may record" — **must record**)
- Observation files are written when substantive findings exist (not for "no concerns")
- The `change_log` entry is the proof that reflection happened; observation files capture signal worth acting on

### Why This Matters

**The meta-problem identified 2026-02-11**: We built an observation capture system in the morning. Ran an eval in the afternoon. The eval didn't capture observations. We discovered this during rubric evaluation, not immediately.

**The lesson**: Building a feature ≠ feature works ≠ feature is used ≠ feature is enforced.

Reflection as side-effect means:
1. **Can't be forgotten** - reflection is part of every stage transition, recorded in `change_log`
2. **Can't be skipped** - `change_log` entry is a blocking requirement
3. **Signal is captured** - substantive findings become observation files; non-findings are still reflected

### What Gets Observed

**During product sessions** (session_type: product_use):
- Framework Reflection Protocol at every stage transition (proportionality, coverage, applicability, missing guidance)
- User corrections to framework outputs
- Deviations from expected stage progressions
- Gaps between framework questions and user needs

**During evaluations** (session_type: evaluation):
- Failed must-do/must-not-do criteria
- Partial passes and quality issues
- Rubric ambiguities and test scenario problems
- Framework capability gaps (e.g., Phase 2 scenarios on Phase 1 framework)

**During framework development** (session_type: framework_dev):
- Conversations about improving the framework itself
- Meta-improvement discussions (like the one that created this doc)
- Observation system failures (framework observing its own observation needs)

**Critical**: Observations must be **generalized, not product-specific**. "Framework didn't ask about offline requirements for media apps" (general) not "Brooks's sleep app needs offline mode" (specific).

---

## The Three-Phase Architecture

### Why Three Phases?

Self-improvement has distinct layers that require different capabilities and different amounts of data:

**Phase 1: Capture** (Build immediately)
- Reflection at every stage transition (recorded in `change_log`), observation files for substantive findings
- Minimal data needed (just need framework to run)
- Side-effect of normal operation
- **Status**: Built 2026-02-11, refined 2026-02-11 (reflection/observation split)

**Phase 2: Pattern Detection** (Build after project volume)
- Analyze accumulated observations for patterns
- Requires multiple observations to detect signal vs noise
- Applies thresholds (1 occurrence = noted, 4+ = pattern detected)
- **Status**: Not built yet (need observation data first)

**Phase 3: Incorporation** (Build after validation infrastructure)
- Proposes skill updates based on detected patterns
- Validates proposed changes against principles and historical projects
- Requires human approval before merging
- **Status**: Not built yet (need pattern detection first)

### Why Capture Must Be Phase 1

**Cannot build pattern detection without observation data.** Trying to build Phase 2 before Phase 1 is like trying to analyze logs that don't exist.

**Cannot defer capture to Phase 2.** If capture isn't built until we have project volume, we miss all the early observations that would inform pattern detection.

**Capture is the foundation.** Get it working reliably first. Everything else builds on top.

### The Phasing Logic

```
Phase 1 (now):     Capture observations automatically
                   ↓
Phase 2 (later):   Detect patterns across observations
                   ↓
Phase 3 (much later): Propose validated skill updates
```

This isn't just "build incrementally" - it's **data dependency**. You can't skip to Phase 2. You can't parallelize. Each phase enables the next.

---

## Component Architecture: C8 Learning System

### C8 Overview

The Learning System (C8) consists of five sub-components. Phase 1 builds only C8a. The rest are v2+.

### C8a: Observer (Phase 1 - BUILT 2026-02-11)

**Purpose**: Passive observation collection as side-effect of framework operation.

**Implementation**:
- `framework-observations/` directory in framework repo (NOT user project directories)
- YAML files with schema: observation_id, timestamp, session_type, observations array
- Mandatory reflection at every Orchestrator stage transition (recorded in `change_log` — blocking)
- Observation files created only for substantive findings (see `framework-observations/README.md` for criteria)

**Location**: Framework repo, not user projects. Observations are about framework behavior, not product specifics.

**Status tracking**: Each observation has `status: noted | requires_pattern | acted_on`

**Provenance**: Links to session context, evidence, framework version (git SHA)

### C8b: Pattern Extractor (Phase 2 - NOT BUILT)

**Purpose**: Periodic analysis of accumulated observations to identify statistically meaningful patterns.

**Approach**:
- Parse all observation files
- Group by (type + skills_affected)
- Count occurrences across sessions
- Apply thresholds:
  - 1 occurrence → status: noted (watch for recurrence)
  - 2-3 occurrences → status: requires_pattern (flag for review)
  - 4+ occurrences → pattern detected (propose action)

**Output**: Pattern reports in `pattern-reports/` with detected patterns, emerging patterns, single instances

**Trigger**: Weekly cron OR after N new observations OR manually invoked

**Principle**: Learn Slowly - requires strong evidence (multiple occurrences) before acting

### C8c: Validation Pipeline (Phase 3 - NOT BUILT)

**Purpose**: Validates proposed skill changes before incorporation.

**Four gates**:
1. **Consistency with principles** - Hard rules are axioms, learnings must not violate them
2. **Appropriate specificity** - Not too broad (applies to everything), not too narrow (one product only)
3. **Reversibility** - Can this change be undone if later evidence contradicts it?
4. **Adversarial testing** - Apply to historical projects, does it improve or regress results?

**Output**: Validated learnings ready for incorporation OR rejected learnings with rationale

### C8d: Incorporation Engine (Phase 3 - NOT BUILT)

**Purpose**: Routes validated learnings to appropriate skills with provenance.

**Routing**:
- New discovery questions → Domain Analyzer (C2)
- New failure modes → Critic (C6)
- New artifact patterns → Artifact Generator (C3)
- Refined thresholds → Trajectory Monitor (C7)

**Provenance**: Every skill change includes:
- Observation IDs that triggered the pattern
- Pattern detection date
- Validation results
- Human approval timestamp

**Supervision**: Human approval required before merging (supervised learning, not autonomous)

### C8e: Retirement Monitor (Phase 3+ - NOT BUILT)

**Purpose**: Reviews incorporated learnings against current evidence. System knowledge can shrink.

**Process**:
- Periodically review learnings with provenance
- Check if later evidence contradicts the learning
- If contradicted by stronger pattern, mark for retirement
- System's knowledge is curated, not just accumulated

---

## Critical Requirements

### Requirement 1: Reflection Must Be Blocking

**Status**: ENFORCED (as of 2026-02-11, refined 2026-02-11)

Framework reflection cannot be optional. Stage transitions must record a reflection entry in `change_log`.

**Rationale**: If reflection is optional, it will be skipped (accidentally or "to save time"). The data we most need (framework failures, edge cases, gaps) occurs in exceptional situations — exactly when someone is most likely to skip "optional" reflection.

**Implementation**:
- Orchestrator skill § Framework Reflection Protocol requires `change_log` entry at every stage transition (blocking)
- Observation files are created only for substantive findings (not for "no concerns")
- This split eliminates noise while preserving the side-effect guarantee

**Verification**: Evaluation methodology Step 7 Tier 1 (BLOCKING) verifies `change_log` has reflection entries; Tier 2 (WARNING) assesses observation file substantiveness

### Requirement 2: Observations Must Be Generalized

**Status**: DOCUMENTED (framework-observations/README.md)

Observations must describe patterns, not instances. They must be useful for future products, not just the current one.

**Bad**: "Brooks's sleep app needs dark room mode"
**Good**: "Framework didn't ask about physical context constraints for ambient utility apps"

**Why**: Product-specific observations can't generalize. If every observation is unique to one product, pattern detection will never find signal.

### Requirement 3: Framework Must Observe Its Own Observation System

**Status**: IMPLEMENTED (2026-02-11)

The framework must observe when observation capture fails. This is the meta-level requirement.

**Evidence**: When observation capture failed during background-pipeline eval, we manually created observation file `2026-02-11-background-data-pipeline-eval.yaml` documenting:
- Type: process_friction
- Severity: blocking
- Description: "Observation capture system was built but not invoked during evaluation run"
- Proposed action: "Make observation capture BLOCKING"

This closes the loop: the framework observed its own observation failure and generated the fix.

### Requirement 4: Three-Phase Architecture Cannot Be Bypassed

**Status**: ARCHITECTURAL PRINCIPLE

You cannot build pattern detection (Phase 2) before observation capture (Phase 1). You cannot build incorporation (Phase 3) before pattern detection (Phase 2).

**Why**: Data dependency. Pattern detection needs observations. Incorporation needs patterns.

**Temptation to avoid**: "Let's just build the skill updater and manually feed it patterns." This skips the learning and automation. Don't.

### Requirement 5: Validation Must Precede Incorporation

**Status**: ARCHITECTURAL PRINCIPLE (Phase 3)

Automatic skill updates without validation are dangerous. The system must validate:
- Consistency (doesn't violate principles)
- Specificity (not too broad, not too narrow)
- Reversibility (can be undone if wrong)
- Adversarial testing (doesn't regress historical projects)

**Why**: A wrong lesson actively misleads (worse than no lesson). Conservative incorporation is essential.

---

## Failure Modes and Safeguards

### Failure Mode 1: Observation Capture Not Invoked

**Symptom**: Framework runs but no observation files created.

**Root cause**: Observation capture implemented as optional feature, not blocking requirement.

**Discovered**: 2026-02-11 during background-pipeline eval simulation

**Fix**: Made observation capture BLOCKING (stage transition fails if file not created)

**Safeguard**: Evaluation methodology Step 7 verifies observation file exists before completing eval

**Learning**: Building a feature ≠ feature is enforced. Must verify feature actually runs.

### Failure Mode 2: Product-Specific Observations

**Symptom**: Observation files contain specific product details instead of generalized patterns.

**Root cause**: Observer doesn't understand generalization requirement.

**Safeguard**:
- framework-observations/README.md has generalization examples (good/bad)
- Observation schema includes anti-examples in description field
- Pattern detection filters observations that don't generalize (future)

**Prevention**: Clear examples and active voice descriptions help observers generalize

### Failure Mode 3: Premature Learning

**Symptom**: Single-instance observations triggering skill changes.

**Root cause**: Skipping pattern detection, going straight from observation to incorporation.

**Safeguard**: Learn Slowly principle enforced by thresholds (4+ occurrences required for pattern)

**Prevention**: Phase 2 pattern detection applies statistical significance, not anecdotes

### Failure Mode 4: Invalid Learnings Incorporated

**Symptom**: Skill change contradicts principles or regresses historical projects.

**Root cause**: Skipping validation pipeline before incorporation.

**Safeguard**: Phase 3 validation pipeline with four gates (consistency, specificity, reversibility, adversarial)

**Prevention**: Human approval required before merging any skill change (supervised learning)

### Failure Mode 5: Observation System Itself Fails Silently

**Symptom**: Observation capture broken but no alert/error.

**Root cause**: No meta-level observation of observation system.

**Discovered**: 2026-02-11 (observation capture built but not invoked)

**Fix**: Framework now observes its own observation failures (meta-improvement loop)

**Safeguard**: Every framework development session captures observations, including observations about the observation system

**Learning**: Meta-level observation required. "Apply framework to itself" extends to self-improvement system.

---

## Success Metrics

### Phase 1 Success (Observation Capture)

✅ **Every stage transition records reflection in `change_log`** (automatic, blocking)
✅ **Substantive findings produce observation files** (signal, not noise)
✅ **Observation files follow schema** (machine-parseable, structured)
✅ **Observations are generalized** (pattern-ready, not product-specific)
✅ **Evaluation methodology verifies reflection mechanically** (Tier 1 BLOCKING check)

### Phase 2 Success (Pattern Detection)

⬜ Pattern reports generated periodically without manual invocation
⬜ Patterns show statistical significance (4+ occurrences across sessions)
⬜ Emerging patterns flagged for monitoring (2-3 occurrences)
⬜ Single instances noted but not acted on (Learn Slowly)
⬜ Pattern detection itself generates observations (meta-learning)

### Phase 3 Success (Incorporation)

⬜ Skill changes proposed automatically from detected patterns
⬜ All proposed changes pass validation pipeline
⬜ Provenance maintained (observation IDs → pattern → skill change)
⬜ Human approval required and tracked
⬜ Adversarial testing shows improvement (or flags regression)
⬜ Retired learnings documented with rationale

### Overall System Success

⬜ Framework improves without manual meta-requests
⬜ Skill quality increases over time (measured via eval regression checks)
⬜ Observation → pattern → incorporation cycle runs automatically
⬜ System observes its own observation/learning failures (closes meta-loop)
⬜ Knowledge curated (can shrink as well as grow)

---

## Historical Context

### 2026-02-11: The Day We Closed the Loop

**Morning (09:43)**: Built observation capture system from scratch
- Created framework-observations/ directory structure
- Defined observation schema
- Updated Orchestrator skill to capture at stage transitions
- First observation: documented meta-improvement loop need

**Afternoon (10:19)**: Ran background-pipeline eval (simulation)
- Expected: Observations automatically captured during eval
- Actual: No observation files created
- Discovery: Observation capture built but not invoked

**Analysis (10:35)**: Multi-layer meta-evaluation
- Identified that observation was optional, not blocking
- Recognized even "how do we automate?" is a manual meta-request
- Documented in eval-history/ and working-notes/

**Fix (11:00)**: Implemented ALL immediate fixes
- Made observation capture BLOCKING (stage fails if not created)
- Made Review Lenses MANDATORY (cannot skip)
- Created mechanical validation scripts
- Added observation verification to eval methodology
- Marked background-pipeline as Phase 2

**Meta-observation (11:15)**: Observed the fix
- Created observation file documenting fix implementation
- Closed the loop: observation → failure → observation-of-failure → fix → observation-of-fix

**Commit (11:30)**: Pushed everything
- 19 files changed (+3,756 insertions)
- Observation capture now enforced
- Self-improvement loop operational

### The Key Insight

**We didn't just fix a bug. We fixed the meta-bug**: the framework couldn't reliably improve itself because observation was optional.

The solution wasn't "remember to observe" - that's still manual. The solution was "make observation unavoidable."

### What This Demonstrates

The self-improvement system successfully improved itself:
1. System built feature (observation capture)
2. Feature failed in practice (not invoked during eval)
3. System observed the failure (manually created observation file)
4. System generated fix (made capture blocking)
5. System observed the fix (documented fix as observation)

**The loop is closed.** Future iterations will be automatic.

---

## Future Work

### Phase 1 Completion

- [ ] Run family-utility baseline to verify observation capture works automatically
- [ ] Accumulate observations from multiple product sessions
- [ ] Validate observation schema supports all needed observation types
- [ ] Monitor observation file size/format for scalability

### Phase 2: Pattern Detection

- [ ] Build pattern-detector script (parse observations, group, apply thresholds)
- [ ] Design pattern report format
- [ ] Determine pattern detection triggers (weekly? after N observations? threshold-based?)
- [ ] Validate pattern detection catches real patterns without false positives

### Phase 3: Incorporation

- [ ] Build validation pipeline (4 gates: consistency, specificity, reversibility, adversarial)
- [ ] Design skill change proposal format (with provenance)
- [ ] Implement human approval workflow
- [ ] Build adversarial testing (apply to historical evals, measure impact)
- [ ] Design learning retirement process

### Meta-Level

- [ ] Apply Prawduct to Prawduct (self-application test)
- [ ] Generate Prawduct's own build plan using Prawduct
- [ ] Use framework to design framework improvements
- [ ] The compiler-compiles-itself test

---

## References

- **Vision**: `docs/vision.md` § "Gets smarter over time"
- **Principles**: `docs/principles.md` § "Learning Principles"
- **Requirements**: `docs/requirements.md` § "R6: Learning"
- **Design**: `docs/high-level-design.md` § "C8: Learning System"
- **Methodology**: `docs/evaluation-methodology.md` § "Extracting Learnings"
- **Implementation**: `framework-observations/README.md`
- **Schema**: `framework-observations/schema.yaml`
- **History**: `eval-history/background-data-pipeline-2026-02-11.md`
- **Meta-analysis**: `working-notes/background-pipeline-eval-meta-analysis-2026-02-11.md`

---

## Conclusion

**The goal**: Self-improvement without manual meta-requests
**The philosophy**: Observation as unavoidable side-effect
**The architecture**: Three-phase approach (capture → detect → incorporate)
**The meta-requirement**: Framework observes its own observation system
**The status**: Phase 1 built and enforced, foundation solid

**This is not a feature. This is the framework's ability to learn and adapt. Without it, the framework ossifies. With it, the framework gets smarter every time it runs.**

**It's observation all the way down. And now, it's automatic all the way up.**
