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
  - type: proportionality | coverage | applicability | missing_guidance | rubric_issue | process_friction
    stage: [0, 0.5, 1, 2, 3, or "meta"]
    severity: note | warning | blocking
    description: "Generalized statement (not product-specific)"
    evidence: "What triggered this observation"
    proposed_action: "What could address this" | null
    status: noted | requires_pattern | acted_on
skills_affected: [list of skill files this relates to]
---
```

See `schema.yaml` for the complete schema definition.

## Key Properties

**Append-only:** Observations are never deleted, only status-updated
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

### What to Observe

**Capture:**
- Framework process felt disproportionate to product complexity
- Framework asked irrelevant questions for this product shape
- Framework missed important topics for this product shape
- Framework required outputs that didn't apply to this product
- User corrected or challenged framework assumptions
- Repeated patterns across multiple products

**Don't capture:**
- Product-specific details ("Brooks's app needs dark mode")
- Single-instance anomalies without broader pattern potential
- User preferences that are product-specific ("User wanted SQLite")
- Implementation details of user's product

### Substantiveness Criteria

An observation is **substantive** if it identifies a specific, actionable insight about the framework's behavior. Generic approval or "no concerns" observations dilute the signal and should not be captured.

**Substantive observations identify:**
- **Proportionality concerns**: Framework process felt too heavy or too light for the product
- **Coverage gaps**: Framework missed important topics or questions for this product shape/domain
- **Applicability mismatches**: Framework applied patterns that don't fit this product type
- **Specific patterns**: Concrete recurring behaviors across multiple sessions
- **Unexpected successes**: Framework handled something well despite expected difficulty (only if this contradicts a prior concern)

**Not substantive (do NOT capture):**
- Generic approval: "Everything worked fine", "No concerns", "Process was smooth"
- Tautological observations: "Low-risk product had proportionate process" (this is the baseline expectation)
- Vague assessments: "Framework could be better", "User seemed satisfied" (no actionable insight)
- Restatements of framework design: "Framework asked discovery questions" (yes, that's what it does)

**Examples:**

| Observation | Substantive? | Why |
|-------------|--------------|-----|
| "Stage 3 artifact generation completed without significant concerns for low-risk utility." | **No** | Generic approval. If there are no concerns, don't capture. |
| "Framework asked 12 discovery questions for low-risk utility, exceeding 5-8 guideline." | **Yes** | Specific proportionality concern with quantitative evidence. |
| "Framework didn't ask about offline capabilities for media utility app despite user mentioning 'use while camping'." | **Yes** | Specific coverage gap with context. |
| "Classification process felt appropriate." | **No** | Vague, no actionable insight. |
| "Framework adapted vocabulary well to non-technical user." | **Only if unexpected** | If this contradicts a prior concern about vocabulary calibration, capture it. Otherwise it's baseline expectation. |
| "Discovery questions were ordered by impact as expected." | **No** | Restatement of design. If ordering was POOR, that's an observation. |

**When in doubt:** Ask "What would the framework do differently based on this observation?" If the answer is "nothing, it's already doing this correctly," don't capture.

### Generalization Principle

Every observation description must be generalizable across products.

**Bad (product-specific):**
> "User's sleep sound app needs offline audio playback"

**Good (generalizable):**
> "Framework didn't ask about offline/connectivity requirements for media-heavy utility apps"

**Bad (product-specific):**
> "Brooks wanted a tabbed interface for sound categories"

**Good (generalizable):**
> "Framework missed navigation pattern discovery for apps with categorized content"

### When to Mark as "acted_on"

Update observation status to `acted_on` when:
1. A skill has been modified to address this observation
2. The skill change references this observation ID in the commit message
3. The observation entry is updated with the skill file changed and date

Never mark an observation as `acted_on` without a corresponding skill change committed to the repo.

## Pattern Detection Thresholds

These thresholds apply when Phase 2 pattern detection is operational:

| Occurrences | Status | Action |
|-------------|--------|--------|
| 1 | `noted` | Watch for recurrence |
| 2-3 | `requires_pattern` | Flag for review, continue watching |
| 4+ | Pattern detected | Propose skill update, run validation pipeline |

**Exception:** Severity `blocking` observations may trigger action at lower thresholds.

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
