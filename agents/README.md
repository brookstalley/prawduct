# Agents

Prawduct uses independent agents for quality governance. Each agent runs in a separate context (`context: fork`) so it cannot see the builder's reasoning — that structural independence is the point.

## Critic (`critic/`)

Reviews each chunk of work against 7 prioritized goals (correctness, completeness, coherence, design). Invoked via `/critic` after every medium+ chunk. The stop hook enforces invocation.

- `SKILL.md` — Complete instruction set (goals, signals, severity, coordinator pattern)
- `framework-checks.md` — Additional checks for framework changes (generality, instruction clarity, cumulative health, pipeline coverage)
- `review-cycle.md` — Per-chunk review lifecycle and format

## PR Reviewer (`pr-reviewer/`)

Assesses release readiness of the full changeset before merge. Complements the Critic's per-chunk reviews with a fresh-eyes look at the whole diff. Invoked via `/pr`.

- `SKILL.md` — Review goals, merge criteria, output format

## Product Instances

Products receive condensed versions of agent instructions via sync:
- `.prawduct/critic-review.md` — from `templates/critic-review.md`
- `.prawduct/pr-review.md` — from `templates/pr-review.md`
- `.claude/skills/critic/SKILL.md` — from `templates/skill-critic.md`

The framework agents (`agents/`) are the source of truth. Product templates are condensed derivatives kept in sync manually when agent instructions evolve.
