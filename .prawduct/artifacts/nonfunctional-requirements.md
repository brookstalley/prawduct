---
artifact: nonfunctional-requirements
version: 1
depends_on:
  - artifact: product-brief
depended_on_by:
  - artifact: operational-spec
  - artifact: scheduling-spec
  - artifact: monitoring-alerting-spec
last_validated: 2026-02-16
---

# Non-Functional Requirements

<!-- sourced: docs/requirements.md § R1-R7, 2026-02-16 -->
<!-- sourced: .prawduct/project-state.yaml § product_definition.nonfunctional, 2026-02-16 -->
<!-- sourced: docs/skill-authoring-guide.md § H1, 2026-02-16 -->

## Performance

Prawduct runs within an LLM session — there is no server, no network latency, no database. Performance means:

- **Conversational responsiveness:** Each stage transition should feel immediate to the user. The framework should not pause for long processing — if a step takes multiple tool calls, keep the user informed.
- **Context window budget:** The framework's always-loaded instructions (CLAUDE.md + Orchestrator SKILL.md + one stage sub-file) should stay under ~25% of the context window to leave room for project state, artifacts, and conversation history.
- **Skill file size:** Per H1 guideline — focused skills 100-200 lines, moderate skills 200-400 lines, complex skills 300-600 lines. Exceeding scope guideline by >25% triggers review. Orchestrator main file + one sub-file should total <260 lines in-context.
- **Artifact generation latency:** Full artifact set (7 universal + structural-characteristic-specific) should be generatable in a single Stage 3 pass without requiring user re-engagement.

## Scalability

- **Per-session:** One project at a time per LLM session. No multi-project concurrent support needed.
- **Across sessions:** Framework improvements benefit all future sessions. Observations accumulate across sessions and projects.
- **Project complexity:** Must handle projects from a 3-screen family utility to a multi-party B2B platform without framework changes.
- **Observation volume:** Pattern detection must remain performant with 100+ observation files (file-based, parsed by tools/session-health-check.sh).
- **Growth that requires architectural change:** Multi-user collaboration, concurrent multi-project sessions, cross-user observation sharing.

## Availability

Not applicable in the traditional sense — Prawduct runs within the user's local LLM session. There is no infrastructure to go down.

- **Session continuity:** If a session is interrupted (context compaction, user closes terminal), the framework must recover state from files on disk. Hooks survive compaction; skill files can be re-read.
- **Governance state recovery:** `.session-governance.json` is recreated from `project-state.yaml` if missing mid-build. SessionStart hook clears stale state on new sessions.

## Cost Constraints

- **Framework itself:** Zero operational cost. Framework is instruction files, not infrastructure. Users pay for Claude API/subscription.
- **Governance overhead:** Governance (hooks, Critic reviews, observation capture) must be proportionate to change impact. A cosmetic fix should not require the same process as a structural reform. The 3-tier DCP (mechanical/enhancement/structural) enforces this.
- **Context budget:** Every line of skill instruction competes with project content for context window space. Instructions must earn their place — unused or rarely-triggered instructions should be moved to on-demand sub-files.
