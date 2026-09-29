---
artifact: build-plan
version: 1
scope: opus-55-w4-methodology-templates
branch: feature/opus-55-w4-methodology-templates
partition: "01's template half (`plugin/templates/**`, plus `test_v5_templates.py` and `test_operator_verification.py`) goes to one isolated-worktree delegate, in parallel with the main agent's methodology half. The two halves touch disjoint prose files. Every other test either half breaks belongs to the integrator, and the delegate reports the edits it needs there instead of making them. The probes run in a second background agent that writes only to the scratchpad. W3 set the precedent."
depends_on:
  - artifact: opus-55-prompt-audit-2026-09
governed_by:
  - artifact: architecture
    dispositions:
      - "every fact has one home → conforms, and it is the point of B-10/B-11, B-14, B-24, B-34, B-36, B-38, B-39 and B-40: a second copy of a fact becomes a pointer to its home, or goes"
      - "goals and verification bind; prescribed method is advice → conforms, and it is #341's point: B-17, B-18 and B-19 restate chunk shape, file-list deliverables and phase choreography as advice, and keep acceptance criteria as the contract"
      - "the plugin writes nothing into a governed repo except… → conforms: templates change for new scaffolds only. Onboarded repos keep what they have, as the owner ruled for A-16"
      - "an independent reviewer never mutates the session it reviews → inapplicable, because no reviewer surface changes"
      - "authority fails closed; advice fails soft → inapplicable, because no gate verdict, exit code or advisory changes; only prose and its test pins move"
      - "prawduct guides and reviews, it never implements → inapplicable"
      - "local-first governance coordination → inapplicable"
      - "written in Python, never specific to Python → inapplicable"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall clock is P0 → conforms: one chunk, one boundary review"
      - "proportionality ratchets both ways → conforms: the wave deletes text and adds no control"
      - "review rigor is stage-keyed → inapplicable, because no severity rule changes"
      - "state-file growth is an advisory, never a block → inapplicable"
  - artifact: program-purpose-and-cession
    dispositions:
      - "prose-test taxonomy: a doc test pins budgets, refs, interface tokens and render consistency, never a sentence → conforms: a pin on a sentence this wave rewrites is retired, or re-anchored on structure or on the interface token it protects. Any absence guard kept is a recorded [DECISION], as W3's were"
      - "model plan (Fable coherence before the cycle lands) → conforms: owed once, before W6 lands"
---

# Build Plan: Opus 5.5 prompt audit — W4, methodology and templates

## Problem

The methodology guides and the artifact templates misfire on Opus 5.5 in five ways. The evidence
and the replacement text are in `opus-55-prompt-audit-2026-09/slice-B.md`, and the owner ruled on
2026-09-28 (the audit's § Rulings):

- **Early stops.** Three lines license ending the turn when there is work in hand: the "just go"
  shade of `YOUR TURN` (B-9), a chunk boundary read as the end of the turn (B-16), and a "hard
  stop" that means "run the review first" (B-35). W1's A-1 now contradicts them.
- **Self-verification.** The builder is told to scrub its own diff while the Critic runs (B-1),
  to review every artifact phase through five perspectives (B-19), to "verify artifacts are
  current" as its own step (B-36), and to redo a delegate's sweep (B-10 to B-12).
- **Delegation as the default.** Tangents are "offered first" to a delegate (B-13), a third
  copy of the default re-asks it of every backlog candidate (B-14), independence alone counts as
  the ordinary yes (B-15), and a subagent is mandated for a consumer grep (B-2).
- **Method written as binding (#341).** Chunk shape (B-17), file-list deliverables in the
  template (B-18) and phase choreography (B-19).
- **Fossils and register.** Issue ids, incident stories, dead component names and version
  fossils ship into every product's artifacts (B-3 to B-8, B-30 to B-33, B-38 to B-40). Bold and
  caps carry emphasis in most sentences (B-27, B-28, B-37). A duplicated constant drifts (B-34).
  Wave 3's weaker-model scaffolding carries its own contradiction (B-23, B-25, B-26).

## Success

- **Every decision carries its slice-B replacement, or a recorded departure.** The Decisions line
  below lists them. Each replacement is located by its `evidence:` string, not by line number,
  because W1 to W3b moved lines.
- **The handoff's carried W4 items are done:**
  - `building.md`'s "Disposition them ALL in ONE pass…" takes W2's de-shout, matching
    `gates.FIX_ORDER` ("run one … in one commit"). The slice's "leave it" rested on the runtime
    directive still shouting, and W2 changed that.
  - `delegation.md`'s brief checklist names the budgets the owned files sit under.
  - The template's "Commit & PR cadence" line points at `planning.md`'s short-plan tick rule.
- **B-21 and B-22 are decided by the probe** (P2 below). They are applied if the new text keeps
  every critical domain concern the old text surfaced. Otherwise they stay held, with the result
  recorded in the audit.
- **Ceilings are lowered in the same commit** for each trimmed guide in
  `test_v5_methodology.py`. `.claude/rules/learnings/authoring.md` stays under its
  `learnings_budgets` entry after B-20's list lands there.
- **The suite passes.**
  - Every sentence pin a rewrite breaks is retired or re-pointed, per the prose-test taxonomy.
  - Each `"<lit>" not in` assertion in `tests/` is checked against the edited files at
    `origin/develop`. A negative pin on a phrase this wave deletes goes vacuously green.
  - After each deletion, `plugin/` and `documentation/` are grepped for the deleted section's
    heading and lead phrases, and for any other surface stating the same rule (by the state, not
    the words). A sentence another wave owns is fixed now only if this wave made it false.
- **#341 is closed** (`/prawduct:backlog update 341 status=shipped`) when this wave merges.
- **The probes have run, each confirming the model id it ran on** from `modelUsage` in
  `claude -p --output-format json`. The Agent tool's `sonnet` alias cannot reach Sonnet 5.5, and
  `claude -p --model claude-sonnet-5-5` can (checked 2026-09-28). Each probe has an old-text
  control, and a control that doesn't show the targeted failure is recorded as "no regression":
  - **P1, the owed W3 rerun on Sonnet 5.5.** W3's two reviewer probes (C-1 PR reviewer; C-22/C-23
    Critic reviewer), with W3's scenarios. Old text from `7cec305a`; new text from `develop` at
    `fa235fe0`, which is what ships.
  - **P2, the B-21/B-22 discovery probe on Sonnet 5.5.** One high-risk idea and one low-risk
    idea, old `discovery.md` against `discovery.md` with B-21 and B-22 applied. The critical
    concerns for each idea are listed before the runs. The failure targeted is a critical
    domain concern the old text raised and the new text missed, or a low-risk interview that
    balloons without the quotas.
  - **P3, the delegate floor probe on Sonnet 5.5.** A delegate gets a removal task under a brief
    written to the old and to the new `delegation.md` checklist (B-12). The failure targeted is a
    "Done" returned with no falsifying evidence.
  - **P4, the early-stop probe on the session model** (Opus 5.5; main-agent surface). A scratch
    repo carries a three-chunk short plan whose reviews are deferred to the boundary. The old and
    new `building.md` and `session-hygiene.md` ride the system prompt. The failure targeted is a
    turn that ends at a chunk boundary with the next chunk ready. This is the longer multi-step
    task W1's probe could not run. If its control also fails to stop early, per-wave probing is
    re-examined in the audit.

## Out of scope

- B-41, a flag. B-21 and B-22 if P2 does not release them.
- The session digest (`methodology/session-digest.md`, W1's) and every skill (W5). A skill
  sentence is fixed now only if this wave made it false.
- Any change to what a gate decides, to a severity rule, or to a parsed field's format.
- F6's rounds-per-PR comparison. Too few PRs have shipped since W3 to measure it.

## Requirements Confidence: High

Every decision has replacement text and a ruling. These are the inferences:

- [DECISION: one chunk, with the template half delegated inside it | methodology isn't a risk
  surface, so the plan would be short either way. One chunk gives one boundary review, and review
  run count is the P0 lever | owner can veto]
- [DECISION: P1's new text is `develop` at `fa235fe0`, not `deb4cf71` as the handoff says |
  `deb4cf71` predates W3's review fixes and W3b's split, so it is not what ships | owner can veto]
- [DECISION: B-21 and B-22 are applied in this wave if P2 shows no loss of critical domain
  coverage on Sonnet 5.5, without a second sitting | the F5 ruling holds them "until a Sonnet 5.5
  discovery probe, which W4's plan carries", which reads as the probe releasing them | owner can
  veto and hold them regardless]
- [DECISION: `delegation.md`'s brief checklist gains a budgets clause, which the audit does not
  enumerate | W3's delegate edited files under ceilings it was never told about, and the handoff
  carried the fix to this wave | owner can veto]
- [ASSUMPTION: `claude -p` with `--append-system-prompt-file` is a fair stand-in for a governed
  session reading the guide, for P4 | MED impact: a real session gets the digest and the hooks too,
  so P4 measures the guide text alone | owner can correct]

## Found while applying

(Filled while building.)

## Status

- [ ] Chunk 01: methodology and templates (B-1 to B-20, B-23 to B-40, the handoff's W4 items, P1 to P4)

## Chunk 01: methodology and templates

**Type:** cumulative-final
**Decisions:**
- **Methodology (main agent):** B-1, B-2, B-8, B-9, B-10, B-11, B-12, B-13, B-14, B-15, B-16,
  B-17, B-19, B-20, B-23, B-24, B-25, B-26, B-27, B-28, B-31, B-33, B-34, B-35, B-36, B-39, B-40,
  and [B-21, B-22 on P2's result]. Also the handoff's `building.md` FIX_ORDER de-shout and
  delegation budgets clause.
- **Templates (delegate):** B-3, B-4, B-5, B-6, B-7, B-18, B-29, B-30, B-32, B-37, B-38, and the
  handoff's cadence-line pointer.

**Files:**
- Methodology: `plugin/methodology/building.md`, `plugin/methodology/planning.md`,
  `plugin/methodology/discovery.md`, `plugin/methodology/reflection.md`,
  `plugin/methodology/delegation.md`, `plugin/methodology/session-hygiene.md`,
  `.claude/rules/learnings/authoring.md` (B-20's list).
- Templates: `plugin/templates/build-plan.md`, `plugin/templates/backlog.md`,
  `plugin/templates/change-log.md`, `plugin/templates/operator-verification.md`,
  `plugin/templates/runbook.md`, `plugin/templates/project-preferences.md`, and the eight
  artifact templates B-3 and B-29 list.

**Tests:** find them by running, not by reading notes. Grep `tests/` for each edited file's name
and each rewritten phrase, then run what the grep finds **without `-x`**. A pin can be built
from a constant, and a literal grep can't see it. So far the grep finds these:
- Delegate-owned: `test_v5_templates.py`, `test_operator_verification.py`.
- Integrator-owned: `test_v5_methodology.py`, `test_short_plan_deferral.py`,
  `test_critic_consolidate.py`, `test_cutover_prose_coherence.py`,
  `test_plugin_methodology_digest.py`, `test_path_reference_resolution.py`, and every other test
  the run turns red.

**Done when:**
1. Each Success bullet holds, and the suite passes.
2. P1 to P4 have run. Results are recorded in this plan and in the audit's § Rulings (P1, P2).
3. Committed, then one `/prawduct:critic cumulative` over the branch, with blocking findings
   resolved.
4. Chunk marked `[x]`.
