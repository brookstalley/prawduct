---
artifact: build-plan
version: 2
scope: reviewer-model-fallback
depends_on: []
last_validated: 2026-06-12
lifecycle: completed
archived: 2026-08-10
released_in: v2.1.5
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

# Build Plan — Reviewer Model Fallback (graceful handling of model changes)

**Problem.** The reviewer-dispatch logic pins concrete model aliases as literals
in skill prose: `escalate` → `model: fable`, `standard` → `model: opus`
(`skills/critic/review-protocol.md` Coordinator Pattern step 2,
`skills/critic/SKILL.md` step 6, `skills/pr/SKILL.md` step 3). Fable was
temporarily withdrawn (2026-06-12). When the harness no longer lists `fable` as a
valid model — or errors when a dispatch selects it — every `escalate`-tier review
breaks, with **no fallback**. Worse, a withdrawn subagent `model:` override does
not fail loudly: per Claude Code docs a blocked/unavailable override "falls back
to the inherited or default model" — i.e. it silently resolves to the *session*
model, not the tier we intended, so the escalate tier could quietly run on
whatever the session is.

**Success.** Each model-dispatching review surface expresses an **ordered
preference chain** per tier and a documented resolution rule: dispatch on the
first model in the chain the harness currently lists as valid; if the preferred
model is withdrawn/unrecognized or a dispatch errors selecting it, fall to the
next in the chain — and never pass an unconfirmed model and rely on silent
substitution. A withdrawn `fable` therefore degrades gracefully to `opus`
(depth tier collapses to the default tier) instead of breaking or silently
mis-tiering the review. The contract test that pins the escalation tier is
evolved to also require a documented fallback (not weakened).

**Out of scope (declared with the user, 2026-06-12 — "prose-only ordered fallbacks").**
- No new code, hook, or `prawduct-hook` subcommand; no automated model-availability
  probe (a Python hook cannot see the harness's live valid-model set — only the
  runtime dispatching agent can, so resolution is prose-driven by design).
- No doctor/janitor drift check, no single-source-of-truth registry/config file —
  considered and declined for proportionality; if model churn recurs, revisit
  (deferred as backlog item REL-5K8M).
- The open-6 model-tier *registry* (`documentation/research/open-6-model-tier-registry.md`)
  is a separate surface (the Critic classifying a *product's* models for review
  applicability) — untouched.
- The main session model is unchanged. The Critic fork frontmatter (`skills/critic/SKILL.md`
  `model: opus`) is left as-is: it is already pinned to the fallback tier (`opus`,
  not `fable`), so fable withdrawal does not affect it, and a single frontmatter
  value cannot express a chain.

## Requirements Confidence

**Level:** High

**Open assumptions:**
- [ASSUMPTION: the depth-tier fallback is `opus` and the default-tier fallback is
  `sonnet` — grounded in `reviewer-model-ab-2026-06-10.md` (opus = efficiency
  frontier and proven-adequate default; sonnet below the quality floor, used only
  to keep a review running if opus itself vanishes) | LOW impact | user can re-rank]
- [ASSUMPTION: "withdrawn/unrecognized" model behaves like the docs' "blocked"
  override (silent fallback to session/default), so the prose must have the agent
  pick a *confirmed-valid* model rather than pass-and-hope | MED impact |
  conservative either way — the rule works whether the harness errors or substitutes]

**Verified capability facts (claude-code-guide, 2026-06-12, code.claude.com/docs):**
- Per-call Agent `model` param and `context: fork` skill frontmatter `model:` each
  take a **single value** — no list/fallback syntax. Fallback must be prose-driven
  (caller picks) or via session-level `--fallback-model`/`fallbackModel` (out of scope).
- A blocked/unavailable subagent or advisor `model` override "falls back to the
  inherited or default model rather than failing the request" (silent substitution
  to the session model is the hazard the resolution rule guards against).
- Subagent model resolution order: `CLAUDE_CODE_SUBAGENT_MODEL` > per-call param >
  agent-definition frontmatter > session model.

## Status

- [x] Chunk 01: Fallback-aware tier chains across the three dispatch surfaces + test

Context: single work cycle, 2026-06-12, branch `fix/reviewer-model-fallback`.
`views_enabled: true` — the checkbox flips at release via the
`scope=reviewer-model-fallback` change-log tag.

## Chunks

### Chunk 01: Fallback-aware tier chains + evolved contract test

Replace the literal `model: fable` / `model: opus` mappings at all three dispatch
surfaces with ordered tier chains and the withdrawn-model resolution rule. The
canonical statement lives in `skills/critic/review-protocol.md` (Coordinator
Pattern step 2); `skills/critic/SKILL.md` step 6 summarizes and points there;
`skills/pr/SKILL.md` step 3 carries a self-contained copy with the same core
wording (separate skill, separate fork — it must be self-contained). Evolve
`tests/preferences/test_risk_escalation_prose.py::test_escalation_tier_declared`
to assert the escalate surface declares the depth tier (`model: fable`) **and**
documents the withdrawn-model fallback — the new contract, not a weakening of the
old "escalate has a distinct higher tier" guard.

- **Type:** doc-only prose + one test (skill prose/frontmatter is behavioral for
  governance, so full Critic review applies).
- **Done when:** all three surfaces carry the chain + resolution rule; the contract
  test asserts the new two-part contract and passes; full suite green;
  `/prawduct:critic` run and blocking findings resolved; reflection captured.

**Token-budget offset (review-protocol.md).** `review-protocol.md` was at its
`<3120` token ceiling (`tests/test_v5_methodology.py::TestCriticSkill::test_token_budget`),
so the necessary fallback rule was offset by removing redundancy — not by bumping
the budget (the trim-not-bump norm). Two genuine redundancies removed, no review
check dropped: (1) the top-of-file `<!-- Role: … -->` comment, a verbatim duplicate
of `skills/critic/SKILL.md`'s and restated by line 5 + Goal 1; (2) a self-restating
clause in the Simplification goal's backwards-compat bullet ("…no existing
deployment to migrate. If nobody asked for backwards compatibility, it's
unnecessary complexity" → "…with no existing deployment to migrate"). The protocol
carries the terse chain + rule; the PR skill (not budget-capped) carries the fuller
rule incl. the silent-substitution rationale.

## Verification Strategy

`tests/preferences/test_risk_escalation_prose.py` is the structural instrument: it
proves each surface still consults `classify-diff-risk`, declares the depth tier,
and (new) documents the fallback. Full suite must stay green (no behavioral code
changed). The Critic reviews the prose for coherence: that the resolution rule is
correct against the verified harness behavior, the three surfaces tell one
consistent story, and the fallback chains match the `reviewer-model-ab-2026-06-10.md`
evidence.
