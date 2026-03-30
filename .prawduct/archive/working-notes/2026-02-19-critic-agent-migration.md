# Critic Agent Migration — Phase 1

Created: 2026-02-19

## Motivation

The Critic skill (6,900 tokens) loaded into the main context creates three problems:
1. **Cognitive interference** — competes with Builder instructions for LLM attention
2. **Self-review conflict** — same LLM that built reviews its own work
3. **Compaction fragility** — Critic instructions lost on compaction, requiring re-read

Moving the Critic to a subagent (Claude Code's Task tool) breaks this cycle: the agent gets clean instructions in its own context, hasn't seen the Builder's reasoning, and doesn't need compaction recovery.

## Plan

### Phase 1: Protocol and references (this session)

1. Add "Critic Agent Protocol" to `skills/orchestrator/protocols.md` — defines when/how to invoke, prompt template, output verification, fallback
2. Update `skills/critic/SKILL.md` — add invocation note explaining this is read by a subagent
3. Update `skills/orchestrator/stage-5-build.md` — step 5 references protocol instead of loading skill
4. Update `skills/orchestrator/stage-6-iteration.md` — Critic references use protocol
5. Update `CLAUDE.md` — simplified compaction recovery, updated Framework Development section
6. Update `tools/governance/reinject.py` — point to protocol not SKILL.md
7. Update `tools/critic-reminder.sh` — error message mentions agent invocation

### Phase 2: Review Lenses agent (future session, after Phase 1 validated)

Deferred per plan. Validate Phase 1 first.

## Key Design Decisions

- **Agent reads SKILL.md from disk** — no need to duplicate Critic instructions. The orchestrator activation marker persists on disk, so the agent can read gated skill files.
- **Prompt template in protocol** — the protocol defines what context to pass (changed files, stage, tradeoffs). The agent reads the full SKILL.md for check definitions.
- **Output verification** — the Orchestrator verifies .critic-findings.json exists, covers all files, and has substantive findings. Rubber-stamp detection prevents a degenerate agent.
- **Same evidence format** — .critic-findings.json format unchanged. Commit gate, stop gate, and tracker all work without modification.
- **Fallback** — if agent verification fails twice, fall back to in-context review.

## Blast Radius

- skills/orchestrator/protocols.md (new section)
- skills/orchestrator/stage-5-build.md (step 5, 6, build completion)
- skills/orchestrator/stage-6-iteration.md (change governance, DCP steps)
- skills/critic/SKILL.md (new invocation section)
- CLAUDE.md (Framework Development, Compaction Recovery)
- tools/governance/reinject.py (pointer update)
- tools/critic-reminder.sh (error message)
- .prawduct/project-state.yaml (change_log, dependency_graph)

## What Does NOT Change

- Hook system (governance-gate, tracker, stop, commit) — same enforcement
- .critic-findings.json format — same evidence
- record-critic-findings.sh — same tool
- Critic checks (1-9) — same checks, same applicability
- Builder skill — stays in main context
- Orchestrator skill — stays in main context
