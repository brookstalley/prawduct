# Observation Triage

The Observation Triage agent analyzes active framework observations, the deferred backlog, and pattern reports to propose priority assignments and archive candidates. It produces structured JSON recommendations that the Orchestrator reviews and applies. This agent is read-only — it does NOT write files, move observations, or update project-state.yaml.

## Invocation

This skill is invoked as a **separate agent** (via Claude Code's Task tool, `subagent_type: "general-purpose"`). The Orchestrator spawns a triage agent during session resumption (when active observations exist), after Pattern Extractor runs, or on user request. This file is the agent's complete instruction set.

## Input

The Orchestrator provides these paths in the agent prompt:

- **Observation directory:** `.prawduct/framework-observations/` — read all `.yaml` files (skip `archive/`, `README.md`, `schema.yaml`)
- **Project state:** `.prawduct/project-state.yaml` — read `observation_backlog` section
- **Pattern report:** `.prawduct/.pattern-report.json` (if exists) — cluster membership data
- **Deferred backlog:** `.prawduct/observation-backlog-deferred.yaml` (if exists) — deferred items with priorities

## Process

### 1. Read all active observations

For each `.yaml` file in the observation directory (excluding `archive/`, `README.md`, `schema.yaml`):

- Extract all observation entries and their statuses
- Note the file path, observation types, severities, and statuses
- Record the file's date prefix for age calculation

### 2. Identify archive candidates

A file is an archive candidate when **ALL** observation entries in that file have terminal status:
- `acted_on`
- `wont_fix`
- `duplicate`

Files with ANY non-terminal entry (`noted`, `triaged`, `requires_pattern`, `monitoring`) are NOT archive candidates.

### 3. Assess priorities

For each non-terminal observation, assign a priority score based on:

1. **Severity tier** (highest weight):
   - `blocking` = 3
   - `warning` = 2
   - `note` = 1

2. **Age** (older = higher priority):
   - > 4 weeks = +2
   - 2-4 weeks = +1
   - < 2 weeks = +0

3. **Pattern cluster membership** (if pattern report exists):
   - Observation belongs to a cluster with `priority: high` = +2
   - Observation belongs to any cluster = +1
   - No cluster membership = +0

Select the top 5 observations by score as `priority: next` items. If fewer than 5 non-terminal observations exist, include all of them.

### 4. Identify stale backlog entries

Check the deferred backlog for entries that are:
- Older than 4 weeks (based on `deferred_date` or file date)
- Have had no status changes or activity since deferral

These are stale — they should be re-evaluated or archived.

### 5. Produce output

Return a single JSON object to stdout:

```json
{
  "archive_recommendations": [
    {
      "file": "path/to/observation-file.yaml",
      "reason": "All 2 entries have status acted_on"
    }
  ],
  "priority_items": [
    {
      "file": "path/to/observation-file.yaml",
      "observation_index": 0,
      "type": "process_friction",
      "severity": "warning",
      "score": 5,
      "summary": "Brief description of the observation",
      "rationale": "Why this is high priority: blocking severity + in pattern cluster X"
    }
  ],
  "stale_backlog_entries": [
    {
      "item_description": "Brief description",
      "deferred_since": "2026-01-15",
      "recommendation": "Re-evaluate or archive"
    }
  ],
  "summary": "3 active files, 1 archive candidate, 2 priority items, 0 stale backlog entries"
}
```

## Constraints

- **Read-only.** Do NOT write files, move observations, update project-state.yaml, or run any tools that modify state.
- **Max 5 priority items.** The Orchestrator presents these during session orientation — more than 5 creates noise.
- **Archive recommendations must be safe.** Only recommend archiving files where ALL entries are terminal. One non-terminal entry means the file stays active.
- **No fabrication.** Every recommendation must reference a real file that exists on disk. Every observation index must correspond to an actual entry in that file.
- **JSON only.** Output must be valid JSON. No markdown, no narrative — the Orchestrator parses this programmatically.
