---
artifact: build-plan
version: 2
scope: requirements-alignment
branch: feature/requirements-alignment
depends_on:
  - artifact: requirements-alignment-discovery
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms: no review round is added; the alignment pass happens before the plan and costs the owner one batched round, not a reviewer run"
      - "proportionality ratchets both ways; new controls emit their yield → conforms: wave 1 adds guidance, not a control; wave 2's review-against-goals carries the yield measure (mid-build interruptions, post-build corrections)"
      - "state-file growth is advisory only → inapplicable because this plan touches no state file"
      - "review rigor is stage-keyed → conforms: Critic Goal 2 stays a WARNING; nothing new blocks at the inner stage"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session → inapplicable because no reviewer mechanics change"
      - "authority fails closed; advice fails soft → conforms: the alignment pass is advice; no gate is added"
      - "local-first governance → inapplicable because nothing is coordinated"
      - "the plugin writes nothing into a governed repo but its own state → conforms: product repos receive guidance through the digest only"
      - "never specific to Python → inapplicable because the change is language-neutral prose"
      - "prawduct guides and reviews; it never implements → conforms: the pass shapes what the agent asks and records, not what it builds"
      - "goals and verification bind; prescribed method is advice → conforms, and is this work's thesis: the plan opens with goals so method stays advice"
      - "every fact has one home → conforms: near-term and North Star live once in the brief, and the pass cites them; the four responses live once in building.md, and every other surface points there"
partition: serial — every chunk rewrites shared vocabulary (the alignment pass, its four responses, durable-first), and parallel prose edits falsify each other's descriptions
last_validated: 2026-10-09
---

## Goals

**Response taken:** Ask, in one batch. The owner answered across 2026-10-08 and 2026-10-09. The
goals below are theirs except where marked *inferred*. The full record is
`requirements-alignment-discovery.md`.

**Product.** An owner hands work to an agent, including long runs while they are away, and comes
back to what they meant. Every clarification the work needs is asked together, up front, before a
plan is written. During the build the agent decides well on its own, because it has the context.
The audience is expert owners.

**Architecture.**
- Goals outlive the session, written where a cold building agent reads them first.
- The owner's words stay distinguishable from the agent's inferences.
- Goals reach every decision point.

**This wave.** Put the alignment pass and the durable-first mid-build rule into the guidance every
governed repo reads. Make the plan open with its goals. Remove the guidance that steers agents away
from asking before building. *Inferred:* wave 1 is guidance and templates only, and the mechanisms
come in wave 2.

**Constraints.**
- The session digest is full: it is rewritten in place, never grown.
- Token budgets are paid by cutting duplication, not by moving prose between files.
- Mechanical work gets no new step.
- No review round is added.

**Tradeoffs accepted.** Guidance alone relies on recall until wave 2's review-against-goals lands.
That is acceptable for one wave, because the trial in chunk 03 tests the guidance in use.

**Level:** High. The problem, success criteria, and scope are stated above and owner-confirmed.
The open part is wording, which chunk 03 trials.

**Out of scope (wave 2, filed):**
- The Critic judging against goals, and listing mid-build decisions at the boundary.
- Brief coherence (#974).
- A committed script for the yield measure.

## Status

- [x] Chunk 01: The alignment pass and durable-first decisions in the build cycle
- [ ] Chunk 02: Every repo hears it — discovery, principles, brief, digest, and the sweep
- [ ] Chunk 03: Guidance trial on replayed audit requests

## Build Chunks

### Chunk 01: The alignment pass and durable-first decisions in the build cycle

- **Type:** doc-only
- **Description:** `building.md`'s Confidence Check becomes the alignment pass. Mid-build decisions
  get the durable-first order, and plans open with their goals.
- **Depends on:** none
- **Artifacts consumed:** `requirements-alignment-discovery.md` § Goals and § Proposed Design
- **Deliverables:**
  - `building.md`
    - "Before You Build" now describes the alignment pass: the four responses (proceed; proceed
      citing a backlog item or spec; ask in one batch, leading with the agent's own reading; hold
      up, offering discussion or best judgment). The response taken is always acknowledged in a
      line, and the written form scales with the response.
    - A new "Deciding Mid-Build" section: do it right; align with the product's other choices,
      searching the backlog for direction; stop and ask only when the choice is irreversible,
      spends real money, takes on large debt, or costs work out of proportion. Each decision is
      recorded in a line naming what settled it. A decision the goals did not settle is flagged
      for the boundary as a miss by the alignment pass.
    - The existing "A Requirement Surfaced Mid-Build" tripwire is reconciled with it: writing the
      parent requirement is still the move, and the requirement is marked as inferred.
  - `planning.md`: "Requirements Confidence" becomes "Goals". It covers product and architecture
    goals, constraints, tradeoffs accepted, the response taken, and what the owner said versus
    what the agent inferred. The `[ASSUMPTION …]` notation gives way to plainly worded inferences.
  - `templates/build-plan.md`: the Pantry example opens with a `## Goals` section.
  - Critic `review-protocol.md` § 2 and `goals-1-3.md` check for the Goals section: the response
    named, and inferred goals visible. Still a WARNING.
- **Tests:** existing budget and prose tests stay green. A ceiling raised or lowered carries its
  reason in the test.
- **Acceptance criteria:**
  - A falsifying grep for "Confidence Check" and "Requirements Confidence" across `plugin/`,
    `documentation/` (excluding archives), and `tests/` returns only deliberate historical
    mentions, or surfaces chunk 02 owns (`discovery.md`, the digest, the work-model docs).
  - Each of the four responses is defined in exactly one place, `building.md`.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed and chunk marked `[x]` in Status (a short plan: review is deferred to the boundary)

### Chunk 02: Every repo hears it — discovery, principles, brief, digest, and the sweep

- **Type:** doc-only
- **Description:** Remove the language that sets the bar for asking against the owner, give the
  product a prose near-term and North Star that every alignment pass cites, and land the pass in
  the digest, the only surface every onboarded repo re-reads, inside its budget.
- **Depends on:** Chunk 01
- **Deliverables:**
  - `discovery.md`
    - Rework "Infer aggressively", the "consequential and genuinely unverifiable" bar, and
      "erring toward action is usually correct". The owner's intent is never verifiable by the
      agent. Goal and high-stakes questions go in one batch, before building. Inferring is still
      right when the agent says that it inferred.
    - Feature-level discovery points at the alignment pass rather than restating three questions.
    - Product definition gains the near-term and the North Star in prose, such as "home use now,
      thousands of anonymous users eventually".
  - `docs/principles.md`: Principle 20's body is rewritten. Ask together and up front; say what
    you inferred; never interrupt a build for what the goals settle. The name stays, because the
    digest roster carries it. Principle 6's "proceed with declared low confidence" is aligned with
    Hold up.
  - `templates/product-brief.md` (Vision) and `templates/project-state.yaml`: near-term and North
    Star live as prose in the brief, and project-state points there. `scope.accommodate` is kept,
    now described as the list every alignment pass checks.
  - `CLAUDE.md` "Before Building": shortened to a pointer at the alignment pass.
  - `session-digest.md`
    - The rigor paragraph is rewritten in place: the alignment pass before building, and mid-build
      decisions made against the goals with the durable choice first.
    - "Closing the turn" is reconciled. A question from the alignment pass is the case where "only
      the user can unblock it".
    - The emitted digest stays within its working budget.
  - Every remaining surface that describes the old model is swept: `documentation/work-model*.md`
    (current, not archived), skill prose, and the backlog `pick` route (an item that already
    answers the questions is "proceed, citing it"). Each is found by searching for the claim, not
    only the tokens edited.
- **Tests:** `test_plugin_methodology_digest.py` stays green. Lower a pinned ceiling in the same
  commit wherever a trim lands under it.
- **Acceptance criteria:**
  - Falsifying greps for "Infer aggressively", "genuinely unverifiable", and "cost of asking too
    many" return nothing in `plugin/`.
  - Principle 20 and `building.md` do not contradict each other.
  - The digest states the pass and durable-first.
  - A sweep for the old claims returns only deliberate history.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed and chunk marked `[x]` in Status

### Chunk 03: Guidance trial on replayed audit requests

- **Type:** doc-only
- **Description:** Prove the guidance changes behaviour in use, not on analysis. Each fresh agent
  reads only the new plugin guidance plus a short fixture of product context, and reports what
  it would do before building and how it would make one mid-build decision. Subagents never
  receive the SessionStart digest, and the digest is the surface product repos actually see, so
  each trial agent's brief begins with the emitted digest text, verbatim, from this branch.
- **Depends on:** Chunk 02
- **Deliverables:**
  - The trial: six cases, each with its expected response.
    - A large mechanical bug fix with a repro: proceed.
    - A backlog item that already answers the goal questions: proceed, citing it.
    - postarr's "split player and server" with a household near-term and many-TV North Star:
      ask in one batch, and the batch includes the use-case and deployment fork.
    - puzzles' "more creative interlocks" with a reference image: ask, and no example promoted to
      a rule.
    - A vague, large "make art discovery better": hold up.
    - A mid-build fork between a quick reversible patch and the durable design that matches a
      backlog item: the durable choice, recorded in a line.
  - Results recorded in this plan's Trial section. Guidance is fixed where a case fails, and the
    failing cases are rerun.
- **Acceptance criteria:**
  - All six cases produce the expected response.
  - No case shows an agent stopping mid-build for something the goals settle.
- **Done when:**
  1. Acceptance criteria met
  2. `/prawduct:critic cumulative` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status
