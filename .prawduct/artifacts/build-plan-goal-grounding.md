---
artifact: build-plan
version: 2
scope: goal-grounding
branch: feat/goal-grounding
depends_on:
  - artifact: goal-grounding-discovery
  - artifact: requirements-alignment-discovery
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms: no review round, reviewer, mode or gate is added; the boundary review's existing goals check gains one word (hedged)"
      - "proportionality ratchets both ways; new controls emit their yield → conforms: chunk 03 extends the alignment yield measure with the owner-raised product-level questions the discovery names as this control's yield"
      - "state-file growth is advisory only → inapplicable because this plan touches no state file"
      - "review rigor is stage-keyed → conforms: a hedged goal rates like an inferred one, WARNING at boundary only"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session → conforms: the reviewer's goals check still only reads and reports"
      - "authority fails closed; advice fails soft → conforms: every grounding and drift judgment is advice in the agent's voice; no new gate"
      - "local-first governance → conforms: the measure script reads local transcripts with the stdlib"
      - "the plugin writes nothing into a governed repo but its own state → conforms: the backfill runs per product in its own session after merge, not from here"
      - "never specific to Python → conforms: the guidance is language-neutral; the script is a maintainer tool"
      - "prawduct guides and reviews; it never implements → conforms: the check asks the owner; it decides nothing about product code"
      - "goals and verification bind; prescribed method is advice → conforms, and is this plan's thesis: grounding is about the goals under the work, not a method"
      - "every fact has one home → conforms: the grounding check, the hedged provenance and the drift tiers live once, in discovery.md beside intentional inference and characteristic flips; building.md, planning.md, the digest, the brief template and review-protocol point there"
partition: serial for 01-03 — 01 and 02 share discovery.md's provenance passage and the vocabulary (grounded, hedged) that 03's counter and the review read; 04 delegated, one fresh read-only agent per replay case, because the cases are independent and each reads a different transcript
last_validated: 2026-10-21
---

## Goals

**Response taken:** Proceed, citing #1029 and the owner-settled design in
`goal-grounding-discovery.md` (§ Proposed design A–D, § Settled 2026-10-20, § Calibration). The
owner answered the three choices it left open on 2026-10-21: prose only in this wave, with the
replay deciding whether signal 2 is mechanised later; the acceptance replays run inside this
plan, delegated; the backfill runs as per-product sessions after merge.

**Product:** Prawduct's own users (product owners governed by it) stop being the only one who asks
"what are we really trying to achieve". The agent checks the goals under any investment decision,
says when they are not grounded in a sentence, and calls out drift by tier.

**Architecture:** Ambient, not ceremony (owner, 2026-10-20): no new named step, checklist, gate or
review round. The check lives in how the agent writes a plan's `## Goals` and its response line,
and in its ordinary voice mid-build.

**Constraints:** The session digest is full, so it gains no net words (owner's token-budget rule:
simplify first, never relocate). Mechanical work gets no slower. The fork tier must stay rare.
Signal 3 and the product-vs-solution filter stay judgment, never word-matching.

**Tradeoffs accepted:** Signals 1 and 2 ship as prose read at plan approval, not mechanised. They
are the concrete ones, so prose may miss them. Revisit if chunk 04's replay misses the Arrt
triggers or the testament join token. *Inferred:* the yield counter is a lexical lead read by
hand, like the existing `corrections` count, not a verdict.

**Decisions made mid-build:**
- Chunk 01: the grounding check's home is `discovery.md`, not `building.md`. building.md sat at
  its ceiling with no duplication left to pay ~330 tokens, and the owner's budget rule is
  simplify first, raise second. Grounded, hedged and inferred are one provenance judgment, and
  discovery.md already owned intentional inference. building.md keeps a one-line pointer in
  "Before You Build". Not settled by the goals (they name no file): an alignment-pass miss in
  the plan's own deliverable list, corrected here and in chunk 01's deliverables and criterion.
- Chunk 02: drift tiers sit beside discovery.md's "A structural characteristic flipped", same
  reason; reflection.md describes no record updates, so that deliverable is dropped.

**Level:** High. The design is settled and calibrated on four products. The uncertainty is
whether prose alone changes behaviour, and chunk 04 measures that directly.

## Status

- [x] Chunk 01: The grounding check and the hedged answer
- [ ] Chunk 02: Drift, by tier, read at plan approval
- [ ] Chunk 03: The control's yield — owner-raised goal questions
- [ ] Chunk 04: Replay testament and Arrt against the new guidance
Context: Plan written 2026-10-21 after the owner settled scope. Chunk 01 committed (e8acb2b3)
and reviewed; its acceptance criterion was reworded when the check moved to discovery.md (see
Decisions made mid-build), awaiting the owner's one-line confirmation. Next: Chunk 02. After merge and a
prawduct-live advance, the backfill runs as one session per governed product (testament,
discodon, hallucinote, Arrt); it is outside this plan's acceptance.

## Verification Strategy

Prose changes are verified by behaviour, not by reading: chunk 04 hands each replay case to a
fresh agent briefed with this branch's emitted digest verbatim, the way w1's guidance trial did
(subagents never receive the SessionStart digest, so the brief must carry it). Chunk 03's counter
is verified red first against a fixture transcript that contains a goal question.

## Build Chunks

### Chunk 01: The grounding check and the hedged answer

- **Type:** doc-only
- **Description:** Sections A, B and D. The alignment pass learns to judge the goals under the
  work, not only the request: at any investment decision (plan, design artifact, architectural
  choice, spending, outward commitment), which product goals does this rest on, and is each
  grounded (owner-stated without a hedge, and still true)? Cost is investment × irreversibility;
  the product-vs-solution filter decides whether a hedge matters; audience is checked first;
  pushback is a sentence. A hedged owner answer stays an open question with a revisit trigger and
  the cheap hedges taken now, as a third provenance beside said and inferred. The agent opens
  discovery and every fork by restating what the product is for and how this work serves it.
- **Depends on:** none
- **Deliverables:**
  - `methodology/discovery.md`: the grounding test, cost ranking, filter, audience-first and
    pushback shape (see Decisions made mid-build); the hedged provenance and how it is recorded
    (open question, revisit trigger, cheap hedges), never `null` or a `never` item; D's
    restatement.
  - `methodology/building.md` "Before You Build": a one-line pointer, inside the existing four
    responses rather than a fifth.
  - `methodology/planning.md` Goals: the response line names any ungrounded goal the plan rests
    on; `Hedged:` marked like `Inferred:`. Points to discovery.md, does not restate it.
  - `templates/product-brief.md`: one hedged-line example beside the inferred one.
  - `skills/critic/review-protocol.md` goals check: a goal still hedged rates like one still
    inferred.
  - Every other surface describing the alignment pass agrees (search the claim, not the tokens:
    `templates/build-plan.md`, `methodology/session-digest.md`, `docs/principles.md`).
- **Acceptance criteria:** a cold reader following building.md's alignment pass reaches, in one
  hop, text that tells a product hedge from a solution hedge and gives the shape of the stop;
  the digest's word count does not grow.
- **Done when:**
  1. Acceptance criteria met and the suite passes
  2. Committed and chunk marked `[x]` in Status (review per inference)

### Chunk 02: Drift, by tier, read at plan approval

- **Type:** doc-only
- **Description:** Section C. Record / heads-up / fork, with the three adjusting rules (record lag
  is a heads-up; irreversibility raises the tier and publishing is a hard stop; someone else's
  ownership is the strongest signal). Signals 1 and 2 are read at plan approval: acts that
  contradict the record's own text, and open revisit triggers set against the plan. Drift is not a
  defect; the fork tier's output is the question "do we update the goals?".
- **Depends on:** Chunk 01
- **Deliverables:**
  - `methodology/discovery.md`: the tiers and rules, beside "A structural characteristic
    flipped"; `methodology/building.md` "Deciding Mid-Build" points there.
  - `methodology/planning.md`: at plan approval, read the brief's open revisit triggers and the
    record's scope words against the plan. One sentence pointing to discovery.md.
- **Acceptance criteria:** the three rules and both signals are stated once; every pointer
  resolves; the suite passes.
- **Done when:**
  1. Acceptance criteria met and the suite passes
  2. Committed and chunk marked `[x]` in Status (review per inference)

### Chunk 03: The control's yield — owner-raised goal questions

- **Description:** The NFR norm says every new control emits its yield, and the discovery names
  this one's: owner-raised product-level questions, which the change should reduce. Extend the
  existing alignment yield measure rather than writing a second tool.
- **Depends on:** none
- **Deliverables:**
  - `tools/measure-alignment-yield.py`: an `owner_goal_questions` lead count (owner turns asking
    what the product or work is for), documented as a lead read by hand, in the human and JSON
    output.
  - A test that fails without the counter (red first) and passes with it.
- **Acceptance criteria:** the baseline window (before this merge) prints a number, and the docstring says how to compare it after.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed and chunk marked `[x]` in Status (review per inference)

### Chunk 04: Replay testament and Arrt against the new guidance

- **Type:** cumulative-final
- **Description:** The discovery's acceptance. Each case goes to a fresh read-only agent briefed
  with this branch's emitted digest verbatim and on-demand access to the plugin guides, without
  sight of the expected response.
- **Depends on:** Chunks 01–02
- **Deliverables:**
  - Cases and their expected responses:
    - Testament discovery ("might be used by others… scope that out for now"): fork, at
      discovery, audience first.
    - Testament 10-17, the agent about to mint the second person's join token: fork tier,
      ownership signal.
    - Negative control, "AWS or Azure, not sure yet" planted in the same discovery: a recorded
      default, no flag.
    - Arrt's October public-service plan: both armed revisit triggers fire at plan approval.
    - Record lag (hallucinote going public, said out loud): a heads-up, not a fork.
  - Results in this plan's Replay section. A failing case fixes the guidance and reruns; a miss on
    signals 1 or 2 after one fix is filed as the mechanism item the Tradeoffs line names.
- **Acceptance criteria:** all five cases produce the expected response.
- **Done when:**
  1. Acceptance criteria met
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Replay

*(filled by chunk 04)*

## Governance Checkpoints

Commit per chunk. The branch touches `plugin/skills/` (a declared risk surface), so review
inference decides per-chunk depth; chunk 04's cumulative review gates the PR, which runs when the
owner asks.
