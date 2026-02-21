# Self-Improvement Architecture

**Purpose**: Documents the framework's automatic self-improvement system - the architectural goal, philosophy, implementation approach, and critical requirements that ensure the framework learns without manual intervention.

**Tier**: 1 (Source of Truth)
**Owner**: Framework maintainers
**Last updated**: 2026-02-17

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

See `framework-observations/README.md` § "Observation Capture Guidelines" for the complete list of what to capture and what not to capture, with examples. The three session types (product_use, evaluation, framework_dev) each have distinct capture points.

**Critical**: Observations must be **generalized, not product-specific**.

---

## The Three-Phase Architecture

### Why Three Phases?

Self-improvement has distinct layers with **data dependencies**: you can't detect patterns without observations, and you can't incorporate learnings without patterns. Each phase enables the next — this isn't just incremental, it's sequential by necessity.

```
Phase 1 (Capture):        Observations as side-effect of operation
                           ↓
Phase 2 (Detection):      Patterns across accumulated observations
                           ↓
Phase 3 (Incorporation):  Validated skill updates from patterns
```

See "Component Architecture" below for implementation details and current status of each phase.

---

## Component Architecture: C8 Learning System

### C8 Overview

The Learning System (C8) consists of five sub-components. Phase 1 builds only C8a. The rest are v2+.

### C8a: Observer (Phase 1 - BUILT 2026-02-11)

**Purpose**: Passive observation collection as side-effect of framework operation.

**Implementation**:
- `framework-observations/` directory in framework repo AND product repos (`.prawduct/framework-observations/`)
- YAML files with schema: observation_id, timestamp, session_type, observations array
- Mandatory reflection at every Orchestrator stage transition (recorded in `change_log` — blocking)
- Observation files created only for substantive findings (see `framework-observations/README.md` for criteria)
- **Product repo contribution**: Product repos capture observations locally during builds. `tools/contribute-observations.sh` upstreams them to the framework via GitHub issues. The Orchestrator prompts for contribution during session resumption when `UNCONTRIBUTED_OBSERVATIONS > 0`.

**Location**: Framework repo for self-hosted observations. Product repos capture observations locally; the contribution pipeline (`contribute-observations.sh --submit`) bridges product-use signal to the framework repo.

**Status tracking**: Each observation has `status: noted | triaged | requires_pattern | acted_on | archived`

**Provenance**: Links to session context, evidence, framework version (git SHA)

### C8b: Pattern Extractor (Phase 2 - PARTIALLY BUILT)

**Purpose**: Periodic analysis of accumulated observations to identify statistically meaningful patterns.

**Approach**:
- Parse all observation files
- Group by (type + skills_affected)
- Count occurrences across sessions
- Apply tiered thresholds:
  - 1 occurrence → status: noted (watch for recurrence)
  - 2-3 occurrences → status: emerging (flag for review)
  - Threshold for pattern detection varies by type: meta 2+, build 3+, product 4+

**Output**: Actionable patterns surfaced during session resumption via `tools/session-health-check.sh`, with proposed actions and affected skill files

**Trigger**: Session start (via `tools/session-health-check.sh`). Fully automated periodic triggers remain future work.

**Principle**: Learn Slowly - requires strong evidence (multiple occurrences) before acting

**Remaining**: Fully automated periodic triggers (beyond session-start); pattern detection generates observations about its own effectiveness (meta-learning).

### C8c: Validation Pipeline (Phase 3 - NOT BUILT)

**Purpose**: Validates proposed skill changes before incorporation.

**Four gates**:
1. **Consistency with principles** - Hard rules are axioms, learnings must not violate them
2. **Appropriate specificity** - Not too broad (applies to everything), not too narrow (one product only)
3. **Reversibility** - Can this change be undone if later evidence contradicts it?
4. **Adversarial testing** - Apply to historical projects, does it improve or regress results?

**Output**: Validated learnings ready for incorporation OR rejected learnings with rationale

**Remaining**: Build validation pipeline with all four gates. Design adversarial testing against historical evals.

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

**Remaining**: Automated skill change proposal generation. Provenance tracking from observation IDs through to skill changes.

### C8e: Retirement Monitor (Phase 3+ - NOT BUILT)

**Purpose**: Reviews incorporated learnings against current evidence. System knowledge can shrink.

**Process**:
- Periodically review learnings with provenance
- Check if later evidence contradicts the learning
- If contradicted by stronger pattern, mark for retirement
- System's knowledge is curated, not just accumulated

**Remaining**: Build retirement monitor. Design learning retirement process with documented rationale.

---

## Inductive vs Deductive Learning

The Phase 1-3 architecture is **inductive**: observations accumulate → patterns emerge → changes proposed. This works well for behavioral issues (proportionality drift, coverage gaps, process friction) because they produce repeated observations that cross detection thresholds.

But some framework problems are **structural** — they don't produce repeated observations because the failure mode is invisible from inside the system. Example: if the framework classifies products into fixed categories, no individual product session will observe "this should use dimensions instead of categories." Each session either fits a category or gets classified as ambiguous. The structural issue only becomes visible through deductive analysis: applying the framework's own principles (Generality Over Enumeration) to its own architecture.

**The gap:** Inductive learning requires volume. Deductive analysis requires principles + research → questioning. Phase 1-3 handles the first. The Structural Critique Protocol (see `skills/orchestrator/protocols/governance.md` § "Structural Critique Protocol") handles the second.

**How they complement each other:**

| Approach | Catches | Evidence source | Threshold |
|----------|---------|----------------|-----------|
| Inductive (observations → patterns) | Behavioral drift, proportionality issues, coverage gaps, process friction | Product sessions, evaluations | 2-4+ occurrences depending on type |
| Deductive (principles → questioning) | Structural violations, taxonomy problems, architectural misalignment | Framework principles + external research | Periodic review (every 3 evals, after directional changes, or on request) |

Both feed the same action pipeline: observations → triage → skill updates → Critic governance → commit. The difference is how the observation is generated, not how it's processed.

---

## Learning from Framework Development

### The Gap This Section Addresses

The learning system's Phase 1 (capture) was designed for **product sessions**: observations at stage transitions, FRP at stage gates, observation files for substantive findings. This works because product development follows a predictable stage progression with natural reflection points.

**Framework development is different.** It happens in Stage 6 iteration, governed by the Directional Change Protocol (DCP). The DCP had governance (Critic review validates quality) but no learning step. A massive architectural reform could pass all Critic checks while producing zero captured learnings. Quality and learning are orthogonal — a change can be well-made without anyone asking "what did we learn from making it?"

### The Fix: Post-Change Retrospective

The DCP now includes a mandatory post-change retrospective that asks four questions after every directional change:

1. **Detection:** Could the learning system have caught the problem this change addresses? If not, what's missing?
2. **Process:** What did the implementation process reveal about framework gaps beyond the change itself?
3. **Architecture:** Does this change create new areas the learning system can't observe?
4. **Generalization:** Does this fix apply only to the context where the problem was discovered, or does the same gap exist in analogous contexts?

Substantive findings become observation files (via `capture-observation.sh`). The change_log entry includes a `retrospective` field summarizing key learnings for session-resumption visibility.

### The Feedback Loop

The retrospective creates a self-reinforcing cycle:

```
Directional change completes
  → Critic validates quality (step 5)
  → Retrospective captures learning (step 7)
  → Structural Critique Protocol triggers (expanded trigger)
  → Observations feed pattern detection
  → Patterns improve future detection
```

The Structural Critique Protocol now triggers after directional changes (not just every 3 evals). If a retrospective reveals that the learning system failed to detect a principle violation, that's a signal to expand the Structural Critique's dimensions or the observation system's coverage.

### Four Capture Paths

| Path | Triggers | Captures | Mechanism |
|------|----------|----------|-----------|
| Product sessions | Stage transitions | Behavioral observations, coverage gaps, proportionality issues | FRP + observation capture (automatic, blocking) |
| Non-cosmetic fixes | Every fix in Stage 5/6 | Root cause analysis, framework gaps, class-of-problem patterns | Post-Fix Reflection Protocol (PFR) — classify, RCA before fix, meta-fix, observe, contribute |
| Framework development | Directional changes | Detection gaps, process gaps, architecture blind spots | DCP step 7 retrospective (mandatory) |
| Product deployments | Session resumption (prompted) or manual | Framework gaps as seen from real product use, coverage blind spots across diverse products | `contribute-observations.sh --submit` → GitHub issue → framework triage |

All paths feed the same downstream pipeline: observations → pattern detection → incorporation. The difference is the trigger and the questions asked, not the output format or processing. The product deployments path is unique: it brings distributed, real-world product-use signal into the framework from outside self-hosted sessions.

### Why This Matters

The concern enumeration violated Generality Over Enumeration for weeks. The Structural Critique Protocol existed but never fired (trigger cadence too low). The 17-file structural characteristics reform produced zero captured learnings until the user asked. The learning system had a blind spot for its own development process.

The retrospective closes this gap. It can't prevent architectural mistakes, but it ensures that every directional change — the kind most likely to reveal systemic issues — produces structured learnings that feed back into the system.

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

**Fix**: Made observation capture BLOCKING (stage transition fails if file not created). See `.prawduct/artifacts/governance-mechanisms.md` for how enforcement chains work.

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

**Safeguard**: Learn Slowly principle enforced by tiered thresholds (meta 2+, build 3+, product 4+ occurrences required for pattern detection)

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

**Learning**: Meta-level observation required. "Apply framework to itself" extends to self-improvement system.

### Failure Mode 6: Learning Infrastructure Modified Without Learning Review

**Symptom**: Changes affect observation capture, evaluation scenarios, or FRP dimensions, but the learning system itself is not reviewed for completeness.

**Root cause**: Critic checks didn't include learning system impact. Governance reviewed changes for generality, coherence, and proportionality — but not for whether the learning pipeline remained intact.

**Discovered**: 2026-02-12 during structural characteristics implementation. A 17-file, 6-phase reform restructured the classification system and added new observation types without anyone verifying the learning system remained complete. The Critic ran once at the end as a rubber stamp.

**Fix**: Critic Check 6 (Learning/Observability) explicitly checks whether changes preserve the framework's ability to learn. DCP provides plan-stage and per-phase reviews. FRP dimension 6 assesses whether new areas are observable. See `.prawduct/artifacts/governance-mechanisms.md` § "Enforcement Chains" for how these are mechanically enforced.

**Learning**: Governance that doesn't review its own governance creates blind spots. The Critic checked whether changes were well-made but not whether they preserved the system's ability to detect future problems.

### Failure Mode 7: Infrastructure Degrades Without Monitoring

**Symptom**: Growing collections accumulate resolved items, analysis tools produce stale results, directory sizes grow without bound.

**Root cause**: System monitors content health (are observations meaningful?) and change-time health (do changes preserve learning?) but not infrastructure health (is the plumbing degrading over time?). Critic Check 6 catches problems introduced by *changes* but not problems that emerge from *time passing* with no changes.

**Discovered**: 2026-02-12. Observation directory had no archiving mechanism; `observation-analysis.sh` counted `acted_on` observations toward pattern thresholds, potentially re-triggering already-fixed patterns.

**Fix**: Infrastructure health monitoring in `session-health-check.sh` checks lifecycle invariants. `tools/update-observation-status.sh` manages lifecycle transitions. Critic Check 6 flags growing collections without lifecycle monitoring and mechanical enforcement. See `monitoring-alerting-spec.md` for health metrics and thresholds.

**Structural principle**: Invariants, not enumerations. Define invariant properties (bounded growth, status progression, consistency) and monitor generically. New collections get monitoring at creation time (Critic Check 6), existing collections get health-checked at session time.

**Learning**: Systems that monitor their outputs but not their infrastructure degrade silently. Time-based degradation (accumulation, staleness) requires different monitoring than change-based degradation (breaking modifications). Content health and infrastructure health are orthogonal concerns.

### Failure Mode 8: Directional Changes Produce No Learnings

**Symptom**: A large, multi-file framework change completes with full Critic review but zero captured observations or retrospective findings.

**Root cause**: The Directional Change Protocol had governance (Critic review, step 5) but no learning step. Governance validates quality; it doesn't ask "what did we learn?" The FRP fires at product stage transitions, not after framework changes. Framework development had a blind spot: quality without learning.

**Discovered**: 2026-02-13. The 17-file structural characteristics reform produced 6 commits, 1 Critic review, and 0 observations until the user explicitly asked for retrospective.

**Fix**: DCP step 7 (post-change retrospective) makes learning a required side-effect of directional changes. Three mandatory questions (detection, process, architecture) produce structured observations. The change_log `retrospective` field makes learnings visible during session resumption.

**Safeguard**: The retrospective step is documented as "not optional" in the DCP. The Structural Critique Protocol now triggers after directional changes, providing a second learning opportunity.

**Learning**: Governance and learning are orthogonal. A change can pass all quality checks while producing zero insights. The Critic asks "is this well-made?" The retrospective asks "what did we learn from making it?" Both questions are necessary; neither implies the other.

### Failure Mode 9: Fixes Address Symptoms Without Root Cause Analysis

**Symptom**: A problem is fixed, but the same class of problem recurs because only the specific instance was addressed, not the structural cause.

**Root cause**: The fix flow (discover problem → implement fix → commit) had no step requiring causal analysis. The Post-Fix Reflection Protocol (PFR) existed in an earlier form but was advisory — it triggered only for observation-driven fixes, not for routine bug fixes or Critic findings.

**Discovered**: 2026-02-17. User observed that results improve when they explicitly request 5-whys analysis, but this should be automatic.

**Fix**: Two layers — instructional (PFR embedded in Stage 5/6 fix flows, RCA before fix, meta-fix step) and mechanical (four governance hooks enforce PFR for governance-sensitive files). See `.prawduct/artifacts/governance-mechanisms.md` § "Post-Fix Reflection (PFR)" for the complete enforcement chain.

**Learning**: Advisory protocols get skipped — this was proven again on 2026-02-17 when a governance-gate.sh bug fix skipped PFR entirely despite it being documented in skill instructions. The fix: make PFR mechanically unavoidable, the same way activation and Critic review are mechanically enforced. The `root_cause_analysis.category` enum enables mechanical pattern detection across fixes — if multiple fixes share the same category, that's a systematic gap.

### Failure Mode 10: Instance-Specific Fixes Don't Generalize

**Symptom**: A problem is discovered in one context (e.g., framework development) and fixed only there. The same gap in analogous contexts (e.g., product development) goes unnoticed until someone stumbles on it independently.

**Root cause**: No step in the fix process prompts checking whether the fix applies more broadly. The retrospective asks "what did we learn?" but not "where else does this apply?"

**Discovered**: 2026-02-13. The DCP retrospective (step 7) was added for framework development after discovering governance without learning. The same gap — directional changes without retrospective — existed on the product path but wasn't checked because the fix was scoped to where the problem was found.

**Fix**: Two reinforcing mechanisms: (1) Generalization question in DCP retrospective: "Does this fix apply only to the context where the problem was discovered, or does the same gap exist in analogous contexts?" (2) PFR step 4 (meta-fix): after every non-cosmetic fix, check the product for other manifestations of the same root cause.

**Safeguard**: The generalization question is structural — it's part of every retrospective, not a one-time check. PFR step 4 makes meta-fix a standard part of every fix cycle. Critic Check 6 (Learning/Observability) extended to cover in-file growing collections (same principle: check for the general pattern, not just the specific instance).

**Learning**: Fixing an instance without checking for the general pattern is a form of silent requirement dropping (HR2) at the meta level. The fix was correct but incomplete. Retrospectives that ask "what did we learn?" without asking "where else does this apply?" will systematically produce instance-specific fixes.

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
