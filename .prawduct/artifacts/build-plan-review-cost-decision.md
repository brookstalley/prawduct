---
artifact: build-plan
version: 2
scope: review-cost-decision
branch: feature/review-cost-decision
backlog: brookstalley/prawduct#724
depends_on:
  - artifact: review-cost-investigation-2026-09-19
  - artifact: review-loop-nontermination-diagnosis
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0; cost = unit-cost × run-count, both levers → conforms, and this plan IS that norm's work: Chunk 01 and 02 attack run-count at the fix/accept decision, Chunk 03 attacks unit-cost by pricing the reviewer payload that no gate currently sums"
      - "proportionality ratchets both ways; a new control names the yield it expects and emits it observably → engaged by Chunk 03, which adds a BLOCKING ceiling. Its expected yield is stated in the assertion's own docstring with the figure that motivated it (11 budgeted files, 4.6x growth Jul→Sep) and the reading table it sums is dated per entry, so a later session can ask whether it ever refused anything. [DECISION: the ceiling blocks rather than reports, unlike its sibling `LAST_MEASURED_TOKENS` accounting control | engages the norm's why: an accounting control cannot fire-and-annoy because it never refuses, but it also cannot stop the growth this item exists to stop — #850's whole finding is that eleven individually-approved raises summed to 4.6x precisely because nothing refused | user can veto and take the reading-only form]"
      - "state-file growth is an advisory, never a hard block → inapplicable because no chunk touches a `.prawduct/` state file's size threshold; Chunk 03's ceiling governs plugin prose, which is framework source, not product state"
      - "review rigor is stage-keyed; inner blocks only on the inner BLOCKING set → conforms, and Chunk 02 is the prose half of it: bounding the two over-fixing rules to blocking is what makes the inner stage's demotion survive contact with a builder who reads the rules"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable because no chunk touches a reviewer write path"
      - "authority fails closed; advice fails soft → conforms and is load-bearing in Chunk 01: the cost sentence is ADVICE, so an unpriceable repo must render its reason rather than go quiet or default to `free`. `telemetry.round_price` and `coverage.commit_cost` both already return a named degraded state; Chunk 01 renders those reasons and never substitutes a reassuring default"
      - "local-first; no network, no daemon, no third-party runtime dependency → conforms: file reads, one git probe through the existing `gitstate` helpers, and prose"
      - "the plugin writes nothing into a governed repo except its own state → conforms; nothing here writes into a consumer repo at all"
      - "prawduct is Python but never Python-specific → conforms: the reviewer payload Chunk 03 sums is prawduct's own prose, and the cost verdicts in Chunk 01 come from the existing language-agnostic judgeability predicate"
      - "prawduct guides and reviews; it never implements → conforms; no product code is written"
      - "goals and verification bind; prescribed method is advice → engaged: each chunk's Deliverables name the call sites read on 2026-09-19, and a builder who finds the render belongs at a different seam takes it and records why"
      - "every fact has one home → conforms, and it is the main design constraint on Chunk 01. The round price has one home (`telemetry.round_price` / `format_round_price`) and the commit verdict has one home (`coverage.commit_cost`); Chunk 01 CALLS both and restates neither, so no digit is copied into consolidation prose"
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning; persisted data independently schema-versioned → conforms: nothing here changes a persisted schema or a version"
      - "exit codes are the contract; stable severity prefixes; errors attributed → conforms: Chunk 01 changes the TEXT of an existing message at an existing site and no command's exit code moves"
      - "additive-first evolution; `--json` keys never repurposed → conforms: Chunk 01 adds keys to the consolidation payload and repurposes none"
  - artifact: data-model
    dispositions:
      - "verdicts computed from facts, no model in a fact's write path → conforms: the cost verdict is computed by code from the ledger and the git index, and enters no fact"
      - "facts immutable and append-only → inapplicable because no chunk writes a fact"
      - "derived views never authoritative → conforms: the rendered cost sentence is a view and nothing gates on it"
      - "a governance document reaches a terminal state, never deleted → conforms: this plan archives by `archive-plan` when its release ships"
      - "backlog title rules on every write path → conforms: no chunk writes the backlog outside `/prawduct:backlog`"
      - "a fact from a newer schema is a loud block → inapplicable"
      - "two stores, two lifetimes → conforms"
      - "`backlog_service_repo` selects the authoritative store → inapplicable"
partition: >-
  Serial, coordinator only. Three chunks, and two of them edit the same four Critic prose files
  (`review-cycle.md`, `review-protocol.md`, `goals-1-3.md`, `SKILL.md`), every one of which sits
  at or near a token ceiling that a second author would blow blind — the exact seam Wave 2 of the
  learnings-v2 program paid five integration conflicts for. Chunk 03 then asserts a ceiling over
  the very files Chunks 01–02 edit, so it must run last and in the same head.
last_validated: 2026-09-19
---

## Requirements Confidence

**Level:** High

**Why:** All three items carry filed requirements with acceptance criteria (#831, #833, #850), a
shared measured warrant (the 2026-09-18 ledger scan, re-derived independently on 2026-09-19), and
an owner-recorded design steer in #832's closure: prefer levers that ADD cost information over
levers that suppress finding content. Each chunk's mechanism was read at its call site on
2026-09-19 rather than inferred — `critic_consolidate._IF_YOU_FIX_SOME`, `coverage.cost_of_commit`,
`telemetry.round_price`, and the `LAST_MEASURED_TOKENS` table.

**Open assumptions / unknowns:**

- [ASSUMPTION: "am I already making a judgeable commit?" is answered by pricing the CURRENT WORKING
  TREE (`commit_cost(project_dir, None)`), not by pricing the files the findings name | MED impact |
  user can correct]. #831's text states the mechanical question in the builder's voice; the tree is
  what makes it answerable without guessing which findings the builder intends to fix. Pricing the
  finding files instead would answer a different question — "what would fixing ALL of these cost" —
  which is not the one the issue asks.
- [ASSUMPTION: the reviewer payload set for Chunk 03's ceiling is the five `skills/critic/` files
  plus `agents/critic-reviewer.md` | MED impact | user can correct]. Derived from the artifact's §4
  list; the chunk's first step re-derives it from the dispatch path rather than trusting the list.

**What would raise confidence:** N/A — the two assumptions above are cheap to correct in-chunk and
neither changes the plan's shape.

## Status

- [x] Chunk 01: The zero-blocking close leads with the computed cost and a recommendation (#831)
- [x] Chunk 02: The two over-fixing rules carry a severity bound (#833)
- [ ] Chunk 03: The reviewer payload gets an aggregate ceiling (#850)
Context: Plan written 2026-09-19 on `feature/review-cost-decision`, cut from `develop` at 9224a55e.
Chunk 01 built and committed; its mutation sweep ran seven mutants, six dying and the one predicted
to survive surviving. Chunk 02 landed the full-reach amendment the owner directed (ten carriers, consumer
CLAUDE.md text included), and surfaced a consumer regression in the process: the v3.5.0 anchor is
now archived as `ANCHOR_V4`. Next: Chunk 03. This plan is the first of two covering the review-cost
program; the convergence half (#640 re-apply, #847, #167) is `build-plan-review-convergence.md`.

## Verification Strategy

Tests carry the mechanisms. What tests cannot speak to here is whether the rendered message reads
as a decision aid rather than as more prose to skim — so each of Chunks 01 and 02 ends by rendering
the real message against this repo's own ledger and reading it as a builder would, at the moment
the decision is actually made. Chunk 01 declares `Visual change: yes` for that reason: the whole
deliverable is a sentence a human acts on.

## Build Chunks

### Chunk 01: The zero-blocking close leads with the computed cost and a recommendation

- **Description:** Today the zero-blocking NEXT-ACTION block *tells the builder to go run*
  `cost-of-commit` and quotes what a round costs. It never answers the question itself, so the
  decision is made ~30 times a branch without it (measured 2026-09-19 across two branches). Compute
  both facts at consolidation and lead with them, plus the recommendation they imply. This is #831,
  and it is the direction #832's closure endorses — it adds cost information rather than
  suppressing finding content.
- **Depends on:** none
- **Artifacts consumed:** `review-cost-investigation-2026-09-19.md` §5.1 item 1,
  `review-loop-nontermination-diagnosis.md` Option B
- **Deliverables:** a cost-verdict helper in `plugin/lib/critic_consolidate.py` that calls
  `coverage.commit_cost` for the working tree and `telemetry.round_price`, and renders one leading
  sentence naming the verdict, the price, and the recommended disposition; the zero-blocking arm of
  `next_action_line` leads with it; `_IF_YOU_FIX_SOME` loses whatever the new lead now states, so
  the message does not say the same thing twice
- **Tests:** unit — the three verdicts (`free` / `costs-a-round` / `unknown`) each render their own
  lead and recommendation; the degraded paths (unreadable ledger, thin sample, degraded git) render
  their REASON and never a reassuring default; the lead is absent when blocking findings remain, so
  the blocking arm is untouched. Red-verify each by mutation, and include one mutant expected to
  SURVIVE so the sweep is shown able to report one
- **Acceptance criteria:** a zero-blocking consolidation on this repo prints, as its first
  sentence, whether fixing buys a round, what a round costs here, and which disposition is
  recommended — with no digit restated in `critic_consolidate.py`; every number is asked for
- **Visual change:** yes — the deliverable is a sentence a builder acts on; queue an entry naming
  what to read and where
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. The real message rendered against this repo's ledger and read at the decision point
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: The two over-fixing rules carry a severity bound

- **Description:** "There is no pre-existing exception" and "deep context on a small problem is a
  FIX signal" are both correct about blockers and actively harmful about notes — they are the pull
  that Chunk 01 prices. Bound each to blocking severity at every surface that carries it. This is
  #833, and it is an AMENDMENT to ratified rules, not doc-drift: it needs a recorded decision and a
  witness that is not the amendment itself.
- **Depends on:** Chunk 01 — the bound is only safe once the price is visible, and #833's own
  Scope-out pairs them in that order
- **Artifacts consumed:** `review-cost-investigation-2026-09-19.md` §5.1 item 2
- **Deliverables:** the severity bound added at all six surfaces carrying the two rules —
  `plugin/skills/critic/goals-1-3.md`, `plugin/skills/critic/review-protocol.md`,
  `plugin/methodology/building.md`, `plugin/methodology/session-digest.md`,
  `plugin/skills/critic/review-cycle.md`, `.claude/rules/learnings/core.md` — enumerated by grep at
  build time rather than from this list, which is a candidate set; the recorded decision in
  `.prawduct/change-log.md` with the ledger measurement as its witness
- **Tests:** the bound is pinned in the module that reads the surfaces carrying it, asserted as the
  PROPERTY rather than one spelling, and verified red against a DIFFERENT phrasing than the one
  shipped; the token-ceiling tests for every edited file are re-run and any ceiling the edit
  legitimately moves is ratcheted in the same commit
- **Acceptance criteria:** neither rule appears at any surface without its severity bound — proven
  by a falsifying grep over two vocabularies sharing no word, not by a count of sites fixed; the
  amendment's witness is the filed measurement, not the amendment
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. The decision recorded with its external witness
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: The reviewer payload gets an aggregate ceiling

- **Description:** Every governance prose file carries a token budget; every budget is green;
  nothing prices the sum, and the sum is what a reviewer pays before it sees one line of diff.
  Eleven individually-approved raises summed to 4.6x between July and September. Sum the reviewer's
  own file set and assert a ceiling, with a raise required to price the SUM rather than the file.
  This is #850 — prevention, not relief: it shrinks nothing today and stops 4.6x becoming 9x.
- **Depends on:** Chunks 01–02, whose edits land inside the set this chunk then bounds
- **Artifacts consumed:** `review-cost-investigation-2026-09-19.md` §4
- **Deliverables:** an aggregate assertion in `tests/test_v5_methodology.py` over the reviewer's
  payload set, modelled on the existing injected-session aggregate ("the total is the budget") —
  its own test, with a docstring naming what turns it red, what it deliberately does not cover, and
  the yield the NFR norm requires it to emit; the raise rule stated where a raiser meets it
- **Tests:** the aggregate goes red when any member file grows past the sum, verified by mutating
  the real corpus rather than a fixture; a member added to the reviewer set with no entry in the
  sum is caught, because a ceiling over a hand-listed set is a prefix of the real set wherever the
  set can grow
- **Acceptance criteria:** the reviewer payload set is derived from the dispatch path and shown to
  be non-empty and to contain what the check names; the ceiling is red against a corpus one token
  over and green at the ceiling
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status
