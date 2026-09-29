---
artifact: build-plan
version: 1
scope: opus-55-w3b-review-cycle-split
branch: feature/opus-55-w3b-review-cycle-split
partition: serial — C-8 and C-20 both edit `skills/critic/SKILL.md`'s routing and `review-protocol.md`, and share `test_reviewer_payload_budget.py` and `test_v5_methodology.py`, so two delegates would fight over every file
depends_on:
  - artifact: opus-55-prompt-audit-2026-09
  - artifact: build-plan-opus-55-w3-review-machinery
governed_by:
  - artifact: architecture
    dispositions:
      - "every fact has one home → conforms, and it is the point: each moved section keeps one home (the new file), and every former location becomes a one-line pointer rather than a copy"
      - "goals and verification bind; prescribed method is advice → conforms: text moves verbatim and no goal, severity or check changes"
      - "an independent reviewer never mutates the session it reviews → inapplicable, because no reviewer tool or write path changes"
      - "authority fails closed; advice fails soft → inapplicable, because no gate verdict changes"
      - "prawduct guides and reviews, it never implements → inapplicable"
      - "the plugin writes nothing into a governed repo except… → inapplicable"
      - "local-first governance coordination → inapplicable"
      - "written in Python, never specific to Python → inapplicable"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall clock is P0 → conforms: every dispatched reviewer stops loading about 6k words of builder/maintainer lifecycle, so the payload it reads shrinks. One chunk gets one boundary review"
      - "proportionality ratchets both ways → conforms: text moves out of a per-review payload, and no control is added"
      - "review rigor is stage-keyed → inapplicable, because no severity rule changes"
      - "state-file growth is an advisory, never a block → inapplicable"
  - artifact: program-purpose-and-cession
    dispositions:
      - "prose-test taxonomy: a doc test pins budgets, refs, interface tokens and render consistency, never a sentence → conforms: tests that read a moved section are re-pointed at the file that now holds it, with the same assertions. The new file gets its own budget"
      - "model plan (Fable coherence before the cycle lands) → conforms: owed once, before W6 lands"
---

# Build Plan: Opus 5.5 prompt audit — W3b, the review-cycle split

## Problem

- **C-8.** Every `final`/`cumulative` reviewer loads `skills/critic/review-cycle.md` whole, and a
  coordinator roster loads it three times. About two-thirds of that file is builder and maintainer
  lifecycle material that no reviewer acts on: mode selection, the evidence model, dispositions,
  the census, the round budget, the ledger, and extending the skill.
- **C-20.** Each dispatched `critic-reviewer` also loads `review-protocol.md`'s Coordinator Pattern,
  which holds the fork's instructions for dispatching that reviewer itself.

The evidence and replacement text are in `opus-55-prompt-audit-2026-09/slice-C.md` (C-8, C-20).
Its line numbers are pre-W3, so each span is located by its heading. The owner ruled on 2026-09-28.
W3's plan split these two decisions out as W3b.

## Success

- A new `plugin/skills/critic/cross-checks.md` holds, verbatim:
  - "Per-Chunk Type Protocol Selector";
  - "Final-Mode Cross-Checks" through "Governing-Artifact Reconciliation" (the Learnings
    Cross-Check, Backlog Reconciliation, Records Pass and Record-Lint);
  - the reviewer-addressed paragraph "Reviewers: never name the backlog as a finding's destination".
  
  `review-cycle.md` keeps a one-line pointer where each moved section was.
- `critic/SKILL.md` routes `cross-checks.md` for `final`/`cumulative` in place of `review-cycle.md`.
  Each reviewer-facing citation of a moved section points at `cross-checks.md`. That covers
  `review-protocol.md`, `critic-reviewer.md`, `pr/review-protocol.md`, `backlog/cache-reads.md`,
  `planning.md`'s Type table, `templates/build-plan.md` and `docs/governance-telemetry.md`. A
  citation of a section that stays (for example "Severity is stage-keyed") keeps pointing at
  `review-cycle.md`.
- The Coordinator Pattern moves out of `review-protocol.md` into a new `plugin/skills/critic/coordinator.md`, which only
  the coordinator fork reads. `critic/SKILL.md` step 7's coordinator bullet points at it instead of
  restating it. `review-protocol.md` keeps one line saying the coordinator dispatches the reviewer
  and its contract is its agent definition. (See the [DECISION] on C-20's destination.)
- `test_reviewer_payload_budget.py`'s routes load `cross-checks.md` instead of `review-cycle.md`.
  The route readings and ceilings drop with the payload, and `cross-checks.md` gets its own
  per-file budget in `test_v5_methodology.py`. Every test that reads a moved section reads it from
  its new home, with unchanged assertions.
- **No live pointer into a moved section is left naming its old file.** That is checked by
  grepping each moved heading across `plugin/`, `documentation/`, `tests/` and `.claude/rules/`.
- The suite passes.

## Out of scope

- Rewording any moved text. It moves verbatim, and W3 already applied its prose decisions.
- W4 to W6, and the Sonnet 5.5 probe rerun, which rides W4.
- No behavioural probe: the change is a move with no wording change, so a probe could not tell the
  two versions apart.

## Requirements Confidence: High

Slice C names the spans, the destination and the pointers. W3 already mapped the pointers again
against the current tree.

- [DECISION: C-20's destination is a new `coordinator.md`, not `SKILL.md` step 7 as the slice
  wrote | `SKILL.md` is loaded by every Critic mode, so the slice's destination would have added
  about 500 tokens to the cheap `chunk`/`verify-resolutions` route (the most frequent reviews) to
  remove them from the dispatched reviewer. A file only the coordinator fork reads removes them
  from the reviewer without taxing the cheap route. It is priced as a new `coordinator-fork`
  payload route | owner can veto and fold it into `SKILL.md`]
- [DECISION: no per-wave behavioural probe for W3b | the audit asks for one per wave, but this wave
  changes no instruction text, only which file holds it and who loads it. The payload-route tests
  are its verification | owner can veto]

## Found while applying

- **Payload effect, from the route tests:**
  - A dispatched reviewer drops from 18,704 to 10,861 tokens, which is about 23.5k per
    three-reviewer review.
  - Single-pass `final`/`cumulative` drops from 19,285 to 11,430.
  - The cheap route drops from 5,818 to 5,806.
  - The new coordinator-fork route is 12,024.
- **The cheap-route relation test** asserted cheap < 1/2 of full. The full route shrank by 7.9k
  from C-8, so the ratio broke while the cheap route itself fell. The bound moves to 11/20, with the
  reason in the test. The cheap route's own exact ratchet still pins its size.
- **The fast-path qualifier test** treated `review-cycle.md` as a final-only file. After C-8, no
  review mode opens it, so "no reviewer loads" now counts as a qualifier.
- **The absence query was too narrow.** It grepped the moved *headings*, and it came back clean
  while eight tests still read moved text by *file path*. The cumulative review found them (R-1/R-6),
  and a file-path query (`git grep review-cycle.md review-protocol.md`) found the rest. Two
  hand-kept file lists missed the new files: `_SURFACE_GRANTS` and the bare-command sweep's `DOCS`.
  Both are now derived from disk. Deriving `_SURFACE_GRANTS` at once surfaced a real gap: the
  dispatched reviewer now reads `cross-checks.md`'s `backlog sync` remedy text, and it is exempted
  for the same reason as the fork. The negative-pin scan found no pin made vacuous by the move.

## Status

- [ ] Chunk 01: split review-cycle.md and move the Coordinator Pattern (C-8, C-20)

## Chunk 01: split review-cycle.md and move the Coordinator Pattern

**Type:** cumulative-final
**Decisions:** C-8, C-20.
**Files:** new `plugin/skills/critic/cross-checks.md`, new `plugin/skills/critic/coordinator.md`, `plugin/skills/critic/review-cycle.md`,
`plugin/skills/critic/SKILL.md`, `plugin/skills/critic/review-protocol.md`,
`plugin/agents/critic-reviewer.md`, `plugin/skills/pr/review-protocol.md`,
`plugin/skills/backlog/cache-reads.md`, `plugin/methodology/planning.md`,
`plugin/templates/build-plan.md`, `plugin/docs/governance-telemetry.md`.
**Tests:** `tests/test_reviewer_payload_budget.py`, `tests/test_v5_methodology.py`,
`tests/test_control_yield_tokens.py`, `tests/preferences/test_critic_skill_structure.py`,
`tests/test_critic_reviewer_agent.py`, `tests/test_learning_events.py`,
`tests/test_path_reference_resolution.py`, plus every test the full suite shows reads a moved
section. Run the reading tests without `-x`.
**Done when:** each Success bullet holds and the suite passes. The review is one
`/prawduct:critic cumulative` over the branch.
