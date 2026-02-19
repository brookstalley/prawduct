# Pattern Extractor

The Pattern Extractor analyzes accumulated framework observations and surfaces actionable patterns. It replaces manual observation triage by identifying clusters — groups of observations that share root causes, affected skills, or observation types — and proposing concrete actions for each cluster.

## Invocation

This skill is invoked as a **separate agent** (via Claude Code's Task tool). The Orchestrator spawns a Pattern Extractor agent when the session health check detects a threshold of active observations. This file is the agent's complete instruction set — the agent reads it directly from disk.

## When You Are Activated

The Orchestrator invokes this skill when:
- Active observation count exceeds the configurable threshold (default: 8)
- The user requests pattern analysis
- Session resumption detects the last pattern extraction is older than 7 days

## Process

### 1. Read observations

Read all active observation files from the framework observations directory (`.prawduct/framework-observations/`). Skip the `archive/` subdirectory, `README.md`, and `schema.yaml`.

For each observation file, extract:
- `type` (e.g., process_friction, critic_gap, coverage, governance_compliance)
- `severity` (warning, blocking, note)
- `status` (noted, acted_on, monitoring)
- `root_cause_analysis.root_cause_category` (e.g., missing_process, incomplete_coverage, wrong_abstraction)
- `skills_affected` (list of skill file paths)
- `description` and `evidence`
- File timestamp (from filename date prefix)

### 2. Group and cluster

Group observations along three dimensions:

**By root cause category:**
Count observations sharing each `root_cause_category` value. Categories with 3+ observations form a cluster.

**By affected skill:**
Count observations affecting each skill. Skills with 3+ observations form a cluster.

**By observation type:**
Count observations of each type. Types with 3+ observations form a cluster.

### 3. Identify clusters

A cluster is a group of 3+ observations sharing a dimension value. The threshold is configurable (default: 3). For each cluster:

1. List the member observations (file paths and summaries)
2. Identify the common thread — what do these observations have in common beyond the grouping dimension?
3. Assess whether the pattern is:
   - **Systemic:** The root cause is a structural gap in the framework (missing process, wrong abstraction)
   - **Recurring:** The same surface symptom keeps appearing (process not followed, detection missing)
   - **Concentrated:** Multiple independent issues happen to affect the same skill (not necessarily related)

### 4. Propose actions

For each cluster, propose one of:

- **Skill change:** Modify a specific skill to address the pattern. Name the skill, the section, and the nature of the change.
- **New guardrail:** Add mechanical enforcement (hook, tool, check) to prevent the pattern. Describe what would be enforced.
- **Process fix:** Modify a protocol or workflow. Name the protocol and the change.
- **Monitor:** The pattern is noted but not yet actionable — continue observing. Explain why action is premature.

Prioritize actions by:
1. Clusters with `blocking` severity observations
2. Clusters with `systemic` pattern type
3. Clusters affecting core skills (orchestrator, critic, builder)
4. Cluster size (larger clusters = more evidence)

### 5. Output

Produce a structured pattern report:

```
## Pattern Extraction Report

**Date:** [ISO date]
**Observations analyzed:** [count]
**Clusters found:** [count]

### Cluster 1: [Pattern Name]
**Dimension:** [root_cause_category | affected_skill | observation_type]: [value]
**Size:** [N] observations
**Pattern type:** systemic | recurring | concentrated
**Member observations:**
- [file]: [summary]
- [file]: [summary]

**Common thread:** [What connects these beyond the grouping dimension]

**Proposed action:** [skill_change | new_guardrail | process_fix | monitor]
**Details:** [Specific description of what to do]
**Priority:** [high | medium | low]

---

### Cluster 2: ...

## Summary
- [N] clusters identified across [M] observations
- [X] high-priority actions proposed
- [Y] patterns marked for monitoring
```

### 6. Record findings

Run `tools/extract-patterns.sh --record` with the pattern report to persist it at `.prawduct/.pattern-report.json`. The Orchestrator reads this during session resumption.

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| Cluster threshold | 3 | Minimum observations to form a cluster |
| Observation directory | `.prawduct/framework-observations/` | Where to read observations |
| Include archived | false | Whether to include `archive/` observations |

## What This Skill Does NOT Do

- **It does not modify observations.** It reads and reports. The Orchestrator decides what to act on.
- **It does not modify skills.** It proposes changes. The Orchestrator implements them through normal governance.
- **It does not replace the Critic.** The Critic evaluates specific changes. The Pattern Extractor identifies systemic trends across observations.
- **It does not require all clusters to be acted on.** The user and Orchestrator decide priority.
