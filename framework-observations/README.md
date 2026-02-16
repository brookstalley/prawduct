# Framework Observations

This directory contains the framework's automatic observation capture system — the foundation of Prawduct's self-improvement loop.

## Purpose

Every framework interaction (product session, evaluation run, framework development conversation) automatically produces structured observations. These observations accumulate and are analyzed for patterns. When patterns cross a threshold, they trigger skill updates. This transforms framework improvement from an explicit, invoked activity into an automatic side-effect of normal operation.

## How It Works

### Phase 1 (Current): Capture
Every framework session automatically writes observations to this directory. No manual invocation required.

**Capture points:**
1. **Orchestrator stage transitions** — Framework Reflection Protocol assessments written to observation journal
2. **Evaluation runs** — Framework findings extracted from eval-history/ results
3. **Framework development** — Conversations about improving the framework itself
4. **Manual capture** — `/observe "description"` command for ad-hoc observations
5. **Builder flags** (Stage 5) — When the Builder encounters artifact insufficiency or spec ambiguity, it writes an observation. These are the highest-value observations: they reveal planning deficiencies that improve the Artifact Generator and templates.
6. **Critic product governance** (Stage 5) — When the Critic identifies scope violations or spec compliance gaps, those findings are captured as observations.
7. **Iteration cycles** (Stage 6) — When user feedback reveals gaps in the original artifacts or build plan, the pattern is captured for future improvement.

### Phase 2 (After Project Volume): Analysis
Pattern detection runs periodically or on-demand:
- Parses all observation entries
- Groups by type + affected skills
- Applies thresholds (single instance → noted, 2-3 → watch, 4+ → pattern detected)
- Generates pattern reports in `pattern-reports/`

### Phase 3 (After Validation Infrastructure): Incorporation
Learning proposer generates skill updates from detected patterns:
- Proposes specific skill changes
- Runs validation pipeline (consistency, specificity, adversarial testing)
- Creates PR with provenance linking to observation IDs
- Requires human approval before merge

## Observation Schema

Each observation entry is a YAML file with this structure:

```yaml
---
observation_id: uuid
timestamp: ISO-8601
session_type: product_use | evaluation | framework_dev
session_context:
  product_classification: [if product_use]
  scenario_name: [if evaluation]
  framework_version: git-sha
observations:
  - type: proportionality | coverage | applicability | missing_guidance | rubric_issue | process_friction | artifact_insufficiency | spec_ambiguity | deployment_friction | critic_gap | skill_quality | external_practice_drift | documentation_drift | structural_critique | integration_friction
    stage: [0, 1, 2, 3, 4, 5, 6, or "meta"]
    severity: note | warning | blocking
    description: "Generalized statement (not product-specific)"
    evidence: "What triggered this observation"
    proposed_action: "What could address this" | null
    status: noted | triaged | requires_pattern | acted_on | archived
skills_affected: [list of skill files this relates to]
---
```

See `schema.yaml` for the complete schema definition.

## Key Properties

**Lifecycle-managed:** Observations progress through statuses and are archived when resolved
**Queryable:** YAML format enables grep, pattern detection, and future tooling
**Versioned:** Git tracks when observations were added and what framework version produced them
**Provenance:** Every observation links to session context, evidence, and git SHA

## Querying Observations

### Find observations affecting a specific skill
```bash
grep -l "skills/orchestrator/SKILL.md" framework-observations/*.yaml
```

### Find all blocking-severity observations
```bash
grep -A5 "severity: blocking" framework-observations/*.yaml
```

### Count observations by type
```bash
grep "type:" framework-observations/*.yaml | sort | uniq -c
```

### Find observations with status: noted (no action taken yet)
```bash
grep -B5 "status: noted" framework-observations/*.yaml
```

## File Naming Convention

```
framework-observations/{YYYY-MM-DD}-{short-description}.yaml
```

**Examples:**
- `2026-02-11-meta-improvement-loop.yaml` — First observation documenting the creation of this system
- `2026-02-11-family-utility-eval.yaml` — Observations from family-utility evaluation run
- `2026-02-12-product-session-1.yaml` — Observations from a product use session

**For product sessions:** Use UUIDs or session identifiers instead of product-specific names to avoid leaking product details into framework observations.

## Observation Capture Guidelines

**Core heuristic:** Would this observation change what the framework does for future products? If not, don't capture it.

## Status Lifecycle

Observations progress through these statuses:

```
noted → triaged → acted_on → archived
  │        │                     ↑
  │        └→ Decision recorded in project-state.yaml observation_backlog
  │           with priority (next / soon / deferred) and rationale
  │
  └→ requires_pattern (if seen 2-3 times, needs more data before action)
```

- **noted**: Initial state. Observation captured, watching for recurrence.
- **triaged**: Reviewed and prioritized. Decision recorded in `project-state.yaml` → `observation_backlog` with priority and rationale. The observation won't be forgotten.
- **requires_pattern**: Seen multiple times but not yet enough data to act. Continues accumulating evidence.
- **acted_on**: A skill or artifact has been modified to address this observation. The commit references the observation.
- **archived**: Terminal state. File moved to `archive/` directory. Excluded from active analysis but preserved in git history.

The Orchestrator's Session Resumption checks `observation_backlog` and surfaces items with `priority: next` to the user.

## Archiving

When all observations in a file reach terminal status (`acted_on`), the file is eligible for archiving. Archiving moves resolved files to `framework-observations/archive/`, keeping the active directory focused on observations that still need attention.

**When to archive:**
- After a skill update addresses all observations in a file and the commit is complete
- During session health check, when the infrastructure health report shows archivable files
- Periodically, as part of normal housekeeping

**How to archive:**
```bash
# List files eligible for archiving
tools/update-observation-status.sh --list-archivable

# Archive all resolved files at once
tools/update-observation-status.sh --archive-all

# Archive a specific file
tools/update-observation-status.sh --archive framework-observations/FILENAME.yaml
```

**What archiving does:**
- Moves the file to `framework-observations/archive/`
- Excludes it from `observation-analysis.sh` pattern counts and `session-health-check.sh` analysis
- Preserves it in git history for provenance tracking
- Does NOT delete the observation — it remains accessible via `archive/` or git log

**What archiving requires:**
- ALL observations in the file must be in terminal status (`acted_on` or `archived`)
- Files with any observation in `noted`, `triaged`, or `requires_pattern` cannot be archived
- Use `tools/update-observation-status.sh --file FILE --obs-index N --status acted_on` to update individual observations first

**Capture** (substantive — identifies something the framework should do differently):
- Framework process felt disproportionate to product complexity (with specifics)
- Framework missed important topics or asked irrelevant questions for this structural characteristic
- Framework required outputs that didn't apply to this product type
- Concrete recurring patterns across multiple sessions
- User corrected or challenged a framework assumption (signals a gap)
- Builder flagged artifact insufficiency — a spec didn't specify something needed to build (type: `artifact_insufficiency`)
- Builder flagged spec ambiguity — a spec could mean two things and Builder couldn't determine which (type: `spec_ambiguity`)
- Deployment was harder than the operational spec suggested (type: `deployment_friction`)
- Critic missed an issue that was found later during build or iteration (type: `critic_gap`)
- Skill instructions have grown disproportionate to their responsibility (type: `skill_quality`)
- Skill instructions have inconsistent voice or structure (type: `skill_quality`)
- Skill sections contradict each other (type: `skill_quality`)
- Skill structure diverges from current LLM instruction best practices documented in `docs/skill-authoring-guide.md` (type: `external_practice_drift`)
- CLAUDE.md project structure doesn't match actual files on disk (type: `documentation_drift`)
- Tier 1 document describes behavior that doesn't match implementation (type: `documentation_drift`)
- Cross-references point to renamed, moved, or deleted content (type: `documentation_drift`)
- Description of a component's capabilities is outdated, e.g., "four lenses" when five exist (type: `documentation_drift`)
- Document contains planning artifacts that should have been converted to status descriptions after the planned work completed (type: `documentation_drift`)
- Deductive analysis (principles + research → questioning) reveals a founding architectural decision violates the framework's own principles (type: `structural_critique`)
- A structural choice relies on enumerated categories where dimensional approaches would generalize better (type: `structural_critique`)
- Periodic Structural Critique Protocol review identifies concern overlap, missing concerns, or obsolete concerns (type: `structural_critique`)
- Framework outputs clutter the user's project workspace or conflict with their tooling (type: `integration_friction`)
- Path resolution logic causes confusion or requires user workarounds (type: `integration_friction`)

**Don't capture** (not substantive — no actionable framework change):
- Generic approval: "Everything worked fine", "No concerns", "Process was smooth"
- Tautological: "Low-risk product had proportionate process" (baseline expectation)
- Restatements of design: "Framework asked discovery questions" (yes, that's what it does)
- Product-specific details: user preferences, implementation choices, or anything that names a specific product
- Vague assessments without actionable insight: "Framework could be better"
- Subjective style preferences: "I'd write this differently" (no actionable framework change)

**Examples:**

| Observation | Capture? | Why |
|-------------|----------|-----|
| "Framework asked 12 discovery questions for low-risk utility, exceeding 5-8 guideline." | **Yes** | Specific proportionality concern with evidence. |
| "Framework didn't ask about offline capabilities for media utility app despite user mentioning 'use while camping'." | **Yes** | Specific coverage gap with context. |
| "Stage 3 completed without significant concerns." | **No** | Generic approval. Nothing to change. |

**Generalization rule:** Every observation must generalize across products. Write "Framework missed navigation pattern discovery for apps with categorized content," not "Brooks wanted a tabbed interface for sound categories."

### When to Mark as "acted_on"

Update observation status to `acted_on` when:
1. A skill has been modified to address this observation
2. The skill change references this observation ID in the commit message
3. The observation entry is updated with the skill file changed and date

Never mark an observation as `acted_on` without a corresponding skill change committed to the repo.

## Pattern Detection Thresholds

Thresholds are tiered by observation type. Meta/process observations need fewer occurrences to trigger action because they indicate systemic issues. Build-phase observations sit in between. Product behavior observations need the most data before generalizing.

### Meta observations (threshold: 2+)
Types: `process_friction`, `rubric_issue`, `skill_quality`, `external_practice_drift`, `documentation_drift`, `structural_critique`

These indicate problems with how the framework operates, not what it produces. Two occurrences is sufficient signal — process issues tend to be structural, not coincidental.

| Occurrences | Status | Action |
|-------------|--------|--------|
| 1 | `noted` | Watch for recurrence |
| 2+ | Pattern detected | Propose skill/process update |

### Build-phase observations (threshold: 3+)
Types: `artifact_insufficiency`, `spec_ambiguity`, `deployment_friction`, `critic_gap`, `integration_friction`

These emerge during building and indicate gaps between planning and execution. Three occurrences provides enough evidence to distinguish systematic gaps from one-off misses.

| Occurrences | Status | Action |
|-------------|--------|--------|
| 1 | `noted` | Watch for recurrence |
| 2 | `requires_pattern` | Flag for review, continue watching |
| 3+ | Pattern detected | Propose artifact/template update |

### Product behavior observations (threshold: 4+)
Types: `proportionality`, `coverage`, `applicability`, `missing_guidance`

These describe how the framework interacts with specific product types. More data is needed to distinguish real patterns from product-specific quirks.

| Occurrences | Status | Action |
|-------------|--------|--------|
| 1 | `noted` | Watch for recurrence |
| 2-3 | `requires_pattern` | Flag for review, continue watching |
| 4+ | Pattern detected | Propose skill update, run validation pipeline |

**Exception:** Severity `blocking` observations may trigger action at lower thresholds regardless of type.

## Integration with Evaluation

When recording evaluation results in `eval-history/`, framework findings are duplicated to this observation journal. This ensures:
- Eval findings feed the pattern detection system
- Cross-eval patterns become visible
- Skill updates can reference observation IDs for provenance

See `docs/evaluation-methodology.md` § "Recording Results" for the extraction procedure.

## Meta-Improvement Note

This observation system itself is subject to observation. If the observation capture process proves:
- Too noisy (capturing low-signal observations)
- Too quiet (missing important patterns)
- Too burdensome (slowing down normal framework operation)
- Too ambiguous (unclear what to capture)

...those are themselves observations that should be captured (type: `process_friction`, skills_affected: `["framework-observations/README.md"]`).

The system observes its own observation needs. This is by design.

## History

**Created:** 2026-02-11
**Motivation:** Every improvement cycle required explicit invocation. Even asking "how do we make this automatic?" was itself a manual meta-improvement request. The observation capture system makes improvement a side-effect of normal framework operation.
**First observation:** `2026-02-11-meta-improvement-loop.yaml` — Documents the conversation that created this system.
