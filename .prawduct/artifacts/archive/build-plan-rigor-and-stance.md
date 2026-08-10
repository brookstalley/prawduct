---
artifact: build-plan
version: 2
# Distinct scope. Sharpen the methodology's PRODUCT-MANAGEMENT seams (not infra):
# (1) proportional requirements rigor driven by a stakes / knowledge-confidence /
# volatility self-assessment, with intentional (recorded, vetoable) inference; and
# (2) an explicit agent stance/voice. Owner-directed pivot from infra → methodology.
# Design validated by two research passes (Claude Code capabilities + agent-design
# best practices) — see Requirements Confidence below.
scope: rigor-and-stance
depends_on: []
last_validated: null
lifecycle: completed
archived: 2026-08-10
released_in: v2.0.7
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Requirements Confidence

**Level:** High

**Why:** Owner gave specific guidance for both areas, and the two open design risks were
closed by research: (a) Claude Code placement — verified that a plugin Output Style with
`force-for-plugin` HARD-OVERRIDES (clobbers) a consumer's own style and does not compose, so
the always-on, composable SessionStart digest remains the correct home for behavioral stance;
(b) content patterns — the stance set and the requirements model now align to primary-source
agent-design guidance (Anthropic Constitution / Building Effective Agents, OpenAI Model Spec,
Claude Code best practices) rather than invented-here.

**Open assumptions / unknowns (recorded, vetoable):**
- `[ASSUMPTION | LOW]` Behavioral stance stays in the composable digest/methodology surface; the
  *optional non-forced* output style is a power-user nice-to-have → DEFERRED to backlog, not built.
- `[ASSUMPTION | LOW]` `building.md`'s `test_token_budget` will need a bump; the addition is trimmed
  first and the bump is justified in the test comment (per the evidence-deferral precedent).
- `[ASSUMPTION | MED]` Chunk 3 (digest sweep) ends in an owner ratification gate — the audit + a
  concrete add/condense proposal is produced autonomously; applying digest edits waits for the OK.

**What would raise confidence:** N/A for Chunks 1–2. Chunk 3's proposal is the thing the owner ratifies.

## Status

<!-- Derived view. Mark a chunk shipped by adding a change-log entry tagged
     scope=rigor-and-stance / status=shipped, then run regen-views.
     Do NOT hand-edit the checkboxes. -->

- [x] Chunk 01: Requirements rigor — stakes/knowledge/volatility self-assessment + intentional inference + research triggers
- [x] Chunk 02: Agent stance doc + condensed digest stance section
- [x] Chunk 03: Digest sweep — audit other artifacts for digest-worthy content (propose → ratify → apply)
Context: Plan authored 2026-06-04. Owner-directed pivot (infra foundation judged stable: v2.0.6
shipped, 798 tests green, develop≡main). Built sequentially in the main tree (shared files +
coherent prose — parallel worktrees would manufacture conflicts). Design validated by two research
passes this session. Governance: full suite + `/prawduct:critic` chunk per chunk; cumulative-final
before any PR (PR creation waits for the owner). Chunks 01–03 built + committed; each Critic chunk
clean (0 blocking). 803 tests green. Owner ratified the Chunk-03 digest edit. Cumulative Critic over
`origin/develop...HEAD` is the remaining gate before PR; PR creation waits for the owner.

## Scaffolding

N/A — existing repo. Test runner: `python3 -m pytest`.

## Project Structure

N/A — edits land in methodology guides, templates, the session digest, principles, the methodology
skill index, and their guard tests. Per-chunk surfaces enumerated below.

## Build Chunks

### Chunk 01: Requirements rigor & research triggers
**Type:** doc-only
**Acceptance criteria:**
- `methodology/discovery.md` (CANONICAL home — has token headroom, owns "what to build"): carries
  the full requirements-rigor self-assessment that DRIVES rigor — **stakes** (consequence of getting
  it wrong), **knowledge-confidence** ("do I know enough to design this *well*?" → plan/decompose),
  and **volatility/recency** ("does correctness depend on timely / post-training-cutoff / fast-moving
  data?" → web research) — with the concrete cross-domain examples (rapidly-evolving language e.g.
  Zig; fast-moving product e.g. Claude Code; volatile facts e.g. recent scores, current
  prices/versions/availability) and the proportionality guard (*timely facts you'll assert as current
  → verify ≈regardless of cost; design decisions → scale research to stakes × implementation cost; if
  you cannot verify → flag possible staleness, don't silently guess*); plus **intentional inference**
  (fill what you can, record each as a vetoable `[ASSUMPTION: … | HIGH/MED/LOW | correct·override·defer]`,
  surface only consequential unknowns and surface them **early**, naming the **cost of asking**).
- `methodology/building.md` (BUDGET-BOUND, ~35-word headroom — CONDENSED pointers only, no bump if
  avoidable): "Before You Build" gains a terse intentional-inference clause (fill + record assumption;
  surface consequential unknowns early) + a **Plan Mode** pointer; "Decision Research" adds
  **volatility/recency** alongside the existing lock-in/pervasiveness/structural/external triggers and
  the knowledge-vs-volatility remedy split, deferring examples + full model to `discovery.md`. Keep
  the existing `lock-in` and `research subagent` strings (guard test `test_investigated_changes`).
- `methodology/planning.md`: "Requirements Confidence" gains the explicit **Assumptions** element
  (the recorded inferred-vs-asked list, `[ASSUMPTION: …]` + impact + disposition).
- `templates/build-plan.md`: Requirements Confidence block documents the Assumptions element/format.
- `CLAUDE.md`: light alignment of the "Before Building: Requirements Clarity" block to the
  self-assessment + intentional-inference framing (no bloat; stays an instruction file).
- Guard: keep `methodology/building.md` within `tests/test_v5_methodology.py::test_token_budget`
  (trim the addition to fit; bump with in-test rationale only if unavoidable).
**Done when:** docs coherent; full suite green; `/prawduct:critic` (chunk) clean of blocking findings;
committed and Status updated.

### Chunk 02: Agent stance doc + condensed digest stance section
**Type:** doc-only
**Acceptance criteria:**
- new `methodology/agent-stance.md`: the stance set, expanded from the owner's 6 to ~9 by adding the
  primary-sourced gaps — **verify your own work before declaring done** ("show evidence, don't assert
  success"), **scope discipline / anti-over-engineering** (the counterweight to "offer simpler
  alternatives"), and **calibrated uncertainty** (label confidence when proceeding under it). Each
  stance written as a **positive, testable directive** (so the Critic can check it), cross-linked to
  the principle(s) it operationalizes, with honesty-related stances anchored to Anthropic's
  honesty-dimension taxonomy. Stance #4 references the **AskUserQuestion** tool as the decision-prompt
  mechanism; the research/verify stance generalizes to the Chunk-1 volatility trigger (kept coherent).
- `methodology/session-digest.md`: a CONDENSED stance section (~9 one-line directives + a pointer to
  the full doc), the always-on composable home (a `force-for-plugin` output style would clobber a
  consumer's own style — verified). [Decision (Chunk 02): no offsetting condensation made — the digest
  sits at ~4770/10000 chars with ample headroom and the stance section duplicates no existing prose;
  trimming unrelated prose to "pay" would violate Scope Discipline. The always-on stance is justified
  growth, well under the inline-spill limit.]
- `docs/principles.md`: cross-link to `methodology/agent-stance.md`; note which principles each stance
  operationalizes (no new principles — stance is a different register: voice/communication).
- `skills/methodology/SKILL.md`: add `agent-stance` to the topic map + `argument-hint` + read-on-demand.
- DEFERRED (backlog, not built): an optional *non-forced* `output-styles/` style power users may select.
- Guard: `tests/test_plugin_methodology_digest.py` (digest token budget + single-canonical-copy) stays
  green; add a presence/reference test for `methodology/agent-stance.md` matching the other methodology
  files' pattern.
**Done when:** docs coherent; full suite green; `/prawduct:critic` (chunk) clean of blocking findings;
committed and Status updated.

### Chunk 03: Digest sweep (audit → propose → ratify → apply)
**Type:** doc-only
**Acceptance criteria:**
- Audit existing artifacts/docs (methodology guides, principles, CLAUDE.md, templates) for content
  that *should* reach every session via the digest but currently doesn't.
- Produce a concrete proposal: each candidate addition paired with the **condensation/cut that pays
  for it** (the digest is budget-bound — net cost must be justified). Decide whether the Chunk-1
  self-assessment earns its own digest line.
- **Owner ratification gate:** present the proposal; apply digest edits only on the OK.
- Apply ratified changes within the digest budget; tests green.
**Done when:** proposal presented + (on ratification) applied; full suite green; `/prawduct:critic`
(chunk) clean; then `/prawduct:critic cumulative` over `origin/develop...HEAD` before any PR.

## Governance Checkpoints

- **Per chunk:** full suite + `/prawduct:critic` chunk; resolve blocking findings before committing.
- **Before PR:** `/prawduct:critic cumulative` over `origin/develop...HEAD` gates `/pr create`
  (which waits for the owner to ask).

## Release note

At merge this becomes a release-pending plan (`status=merged`) under the gitflow batched-release
model; the next `develop→main` release flips it to `status=shipped` and runs `regen-views`. Retain
the plan + `active_build_plan` pointer until then (per the "KEEP the build plan" learning + PR-7Q3M).
