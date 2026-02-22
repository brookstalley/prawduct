# V2 Experiment: Principles-Based Architecture

Created: 2026-02-22
Branch: `principles-based-architecture`
Status: Testing

## Motivation

Three converging problems with the process engine approach:

1. **Self-improvement not working without prompting.** Observations were write-only — filed in structured YAML, but nothing systematically read them before making decisions. The learning loop was open: capture → file → forget → repeat.

2. **Too complex and prescriptive.** 8 hooks, 3,280 lines of governance Python, 1,147 lines of Orchestrator procedures. Each past failure added mechanism rather than strengthening principles, creating complexity that bred more complexity. The machinery constrained LLM judgment rather than leveraging it.

3. **Centralized runtime coupling.** Products required `framework-path` pointing to a local clone, hooks doing runtime resolution, session governance JSON — making distribution and independent adaptation impossible.

## Core Insight

Claude's strength is judgment, synthesis, and pattern recognition — not checklist execution. Twenty well-crafted principles that Claude genuinely internalizes catch more problems than two hundred checklist items it mechanically processes. And principles compose naturally for novel situations; checklists can't.

But principles alone have failed hundreds of times. The failures trace to four root causes:
- **Context loss** (after compaction, Claude forgets principles)
- **Competing pressures** (helpfulness training overwhelms governance instinct)
- **Ambiguity in application** (Claude misjudges what "proportional" means)
- **No feedback signal** (violating a principle has no immediate consequence)

The architecture addresses each directly.

## What Was Built

### Three-Layer Architecture

**Layer 1: Principles (always in context, ~1,500 tokens)**
22 principles inline in CLAUDE.md, organized by category:
- Quality (5): Tests Are Contracts, Complete Delivery, Living Documentation, Reasoned Decisions, Honest Confidence
- Product (4): Bring Expertise, Accessibility From the Start, Visible Costs, Clean Deployment
- Process (5): Proportional Effort, Scope Discipline, Coherent Artifacts, Independent Review, Validate Before Propagating
- Learning (4): Root Cause Discipline, Automatic Reflection, Close the Learning Loop, Evolving Principles
- Judgment (4): Infer Confirm Proceed, Structural Awareness, Governance Is Structural, Challenge Gently Defer Gracefully

Plus 5 Review Perspectives (Product, Design, Architecture, Skeptic, Testing) as thinking modes.

Addresses context loss: principles are in CLAUDE.md, which is always loaded.

**Layer 2: Learned Judgment (learnings.md, ~800 tokens)**
Narrative worked examples of good and bad judgment, seeded from 8 lessons distilled from existing framework observations:
- Reactive systems can't detect missing things
- Governance complexity breeds governance complexity
- Independent review catches what self-review misses
- Principles need runtime enforcement, not just change-time checks
- Filed-away observations don't change behavior
- Phase-based implementation enables independent testing
- Denormalized state drifts without mechanical validation
- Escape hatches in classification create silent failures

Addresses ambiguity: worked examples teach judgment by analogy, which LLMs are good at.

**Layer 3: Minimal Mechanical Enforcement (2 hooks, 60 lines)**
- SessionStart/clear: Resets `.session-reflected` marker
- Stop: If files were modified and no reflection captured → block with reminder

Addresses competing pressures and no feedback signal: one habit is enforced mechanically (reflection), and that habit produces the feedback signal.

### Methodology Guides (4 narrative essays)

| Guide | Words | Replaces |
|-------|-------|----------|
| `methodology/discovery.md` | 800 | Domain Analyzer SKILL.md + stages-0-2.md |
| `methodology/planning.md` | 754 | Artifact Generator SKILL.md + stages-3-4.md |
| `methodology/building.md` | 1,015 | Builder SKILL.md + stage-5-build.md |
| `methodology/reflection.md` | 1,145 | FRP + PFR + DCP retrospective in protocols/ |

These teach understanding and judgment, not steps. They're essays, not checklists.

### Files Created

| File | Purpose |
|------|---------|
| `methodology/discovery.md` | How to explore problem spaces |
| `methodology/planning.md` | How to design artifacts and decompose into chunks |
| `methodology/building.md` | How to build with quality, including Critic review |
| `methodology/reflection.md` | The learning loop — the heart of self-improvement |
| `.prawduct/learnings.md` | Seeded project wisdom (8 entries from observations) |
| `tools/reflection-hook` | 60-line bash script for session reflection enforcement |

### Files Modified

| File | Change |
|------|--------|
| `CLAUDE.md` | Complete rewrite — principles inline, routing, methodology pointers |
| `docs/principles.md` | Refined from HR1-10 + philosophy + lenses → 22 principles + review perspectives |
| `.claude/settings.json` | 8 hook commands → 2 (clear + stop via reflection-hook) |
| `.gitignore` | Added `.session-reflected` and `.session-start` |
| `docs/project-structure.md` | Added methodology/, learnings.md, reflection-hook |
| `.prawduct/project-state.yaml` | Change log entry |

### Files Preserved (not modified, not deleted)

All existing infrastructure remains on disk:
- `skills/orchestrator/SKILL.md` and all sub-files
- `skills/domain-analyzer/SKILL.md`, `skills/builder/SKILL.md`
- `agents/critic/SKILL.md` (still the independent reviewer — referenced from methodology)
- `agents/review-lenses/SKILL.md`, `agents/artifact-generator/SKILL.md`, etc.
- `tools/governance-hook` and `tools/governance/` Python module (all 3,280 lines)
- All templates, evaluation infrastructure, test scenarios
- All observation files and observation tooling

The old system is available for reference and can be reconnected by restoring settings.json hooks.

## Measurements

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Hook commands in settings.json | 8 | 2 | -75% |
| Settings.json lines | 95 | 29 | -69% |
| Active governance enforcement | 3,280 lines (Python) | 60 lines (bash) | -98% |
| Orchestrator procedures | 1,147 lines (7 files) | 0 (replaced by methodology) | -100% |
| Total active instruction surface | ~4,427 lines | ~615 lines | -86% |
| Existing tests passing | 108/108 | 108/108 | No regression |

## What to Test

1. **Product build from scratch**: Does Claude follow principles without hooks forcing it?
2. **Framework development task**: Does proportional governance happen through judgment?
3. **Critic invocation**: Does Claude invoke the Critic at the right times from building.md guidance?
4. **Reflection quality**: Does the stop hook produce genuine reflection, not rubber-stamp compliance?
5. **Learning accumulation**: Does learnings.md grow with useful entries over multiple sessions?
6. **Failure recovery**: When something goes wrong, does root cause discipline engage without mechanical PFR enforcement?

## Risks

- **Principle violations under pressure**: Without hooks gating every edit, Claude may skip governance when the user says "just do it." The principles say not to, but helpfulness training is strong.
- **Critic invocation forgetting**: The Critic is now invoked by judgment (building.md says to), not by mechanical hooks. After compaction, Claude may forget to invoke it.
- **Reflection depth**: The stop hook enforces that reflection happens, but not that it's meaningful. Could become rubber-stamp.
- **Learnings bloat**: Without mechanical pruning triggers, learnings.md could grow past useful size.

## Rollback Plan

Restore `.claude/settings.json` from main branch to reconnect all 8 hooks to the governance module. Everything else can coexist — the new files (methodology/, learnings.md) don't conflict with the old system.

```bash
git checkout main -- .claude/settings.json
```
