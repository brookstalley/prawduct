---
artifact: build-plan
version: 2
scope: reviewer-model-tiering
depends_on: []
last_validated: 2026-06-10
---

# Build Plan — Reviewer Model Tiering

**Problem.** The Critic (`context: fork` skill) and PR reviewer (Agent-tool spawn) inherit the
main session's model. When the session runs a top-tier model (fable), every independent review
pays top-tier cost for work the user judges adequately served by a smaller model ("don't think
they need anything more than opus, and maybe even sonnet").

**Success.** (1) Empirical: a captured, reproducible same-input comparison of sonnet vs opus vs
fable on a real review bundle, with findings quality + token/time costs recorded in a tracked
artifact. (2) Mechanism: the Critic fork and PR-reviewer/coordinator-subagent spawns run on a
declared smaller model by default, chosen from the experiment's evidence.

**Out of scope.** Per-product model configuration for the Critic fork (skill frontmatter is
static per plugin version; revisit if products ask); changing the MAIN session's model; haiku
(below the floor the user named).

**Verified capability facts (claude-code-guide, 2026-06-10, code.claude.com/docs):** skill
frontmatter `model:` applies to `context: fork` skills (aliases sonnet/opus/haiku/fable, full
IDs, `inherit`); Agent-tool calls take a per-call `model` param; subagent resolution order is
`CLAUDE_CODE_SUBAGENT_MODEL` env > per-call param > agent-definition frontmatter > session model.

## Requirements Confidence

**Level:** High

**Open assumptions:**
- [ASSUMPTION: one bundle-sized review (this branch, 20 files) is an adequate first sample —
  directional evidence, not a benchmark; the captured harness makes repeats cheap | MED impact |
  user can defer more samples]
- [ASSUMPTION: default lands on opus unless the experiment shows sonnet parity on
  blocking/warning recall | LOW impact | user decides the final default]

## Status

- [ ] Chunk 01: Captured A/B/C experiment — same review input, sonnet/opus/fable
- [ ] Chunk 02: Mechanism — Critic fork + PR-reviewer model defaults
Context: Plan authored 2026-06-10 mid-session on user request, while gate-soundness is
PR-pending (active_build_plan stays on gate-soundness per planning.md "Plan lifecycle on
gitflow").

## Chunks

### Chunk 01: Captured A/B/C experiment

Spawn three general-purpose agents in parallel — `model: sonnet|opus|fable` — each given the
IDENTICAL prompt: read `skills/critic/review-protocol.md`, review the gate-soundness bundle
(`ed2dcb6...HEAD`) against all 7 goals, READ-ONLY (no test runs, no file writes, no
critic-begin/end markers — the real review's evidence must not be touched), return findings as
structured text. Record in new `.prawduct/artifacts/reviewer-model-ab-2026-06-10.md`: the
verbatim prompt (the captured input), each model's findings, token/duration from the harness,
and a recall/precision comparison against the session's real fable cumulative review (4 known
findings) plus cross-model novel findings.

- **Type:** doc-only (the experiment writes one tracked .md artifact; no code changes)
- **Done when:** artifact recorded with all three runs + comparison; reflection captured.

### Chunk 02: Mechanism — model defaults for independent reviewers

From the experiment's evidence + user confirmation of the default tier:
- `skills/critic/SKILL.md` frontmatter gains `model: <chosen>` (applies to the fork).
- `skills/critic/SKILL.md` / `review-protocol.md` coordinator dispatch: Agent calls declare
  `model: <chosen>` explicitly (don't rely on inherit).
- `skills/pr/SKILL.md` Step 3: the reviewer Agent spawn declares `model: <chosen>`.
- All three sites carry the same one-line rationale pointing at the experiment artifact.

- **Type:** doc-only (skill prose/frontmatter — behavioral for governance, so full Critic
  review still applies; .md-only keeps the gate-soundness cumulative record valid)
- **Done when:** Critic review run and blocking findings resolved; committed with tagged
  change-log entry (`chunks=02 | scope=reviewer-model-tiering`).

## Verification Strategy

Chunk 01 IS the verification instrument. For chunk 02: invoke `/prawduct:critic` after the
frontmatter change and confirm (a) the review completes on the declared model and (b) findings
quality is consistent with the experiment's expectation for that tier.
