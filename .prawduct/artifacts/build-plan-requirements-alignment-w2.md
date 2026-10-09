---
artifact: build-plan
version: 2
scope: requirements-alignment-w2
branch: feature/requirements-alignment-w2
depends_on:
  - artifact: requirements-alignment-discovery
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms: the goals check rides the existing boundary review and its correctness reviewer; no round, reviewer or mode is added"
      - "proportionality ratchets both ways; new controls emit their yield → conforms: chunk 03 commits the yield measure for the alignment pass and the review-against-goals"
      - "state-file growth is advisory only → inapplicable because this plan touches no state file"
      - "review rigor is stage-keyed → conforms: the goals check rates at `boundary` only; at `inner` it is an observation like every non-BLOCKING verdict"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session → conforms: the reviewer reads the plan and brief, writes only its partial"
      - "authority fails closed; advice fails soft → conforms: an unconfirmed goal is a WARNING, because only the owner can discharge it and the owner may be away"
      - "the plugin writes nothing into a governed repo but its own state → conforms: the measure script lives in this repo's tools/, not the plugin"
      - "local-first governance, no third-party governance dependencies → conforms: the script reads local transcripts with the stdlib and sends nothing anywhere"
      - "prawduct guides and reviews; it never implements → conforms: the review lists decisions and inferences for the owner; it changes no product code"
      - "never specific to Python → conforms: the guidance is language-neutral; the script is a framework-maintainer tool"
      - "goals and verification bind; prescribed method is advice → conforms, and is this wave's thesis: review judges against goals"
      - "every fact has one home → conforms: the goals check lives once, in review-protocol.md Goal 5; the brief rules live once, in discovery.md, with the template pointing there"
partition: serial — chunks 01 and 02 share vocabulary (inferred vs owner-said, confirmed lines) that the Critic check reads; chunk 03 is disjoint but small, and a delegate's integration cost (plan, change-log) exceeds its wall-clock saving
last_validated: 2026-10-09
---

## Goals

**Response taken:** Proceed, citing #975, #974 and #978, which carry the goals, acceptance and
scope-outs, under the owner-settled design in `requirements-alignment-discovery.md` (§ Proposed
Design, § Settled 2026-10-09). Everything below the items' own text is *inferred* and listed so the
boundary review shows it.

**Product.** The owner comes back from a long run and sees, in one place, what the agent decided
on their behalf and which goals it built on without confirming. The brief, which every pass reads,
never contradicts itself and never passes off an inference as the owner's word.

**Architecture.** Goals reach the review: the boundary review reads the plan's Goals and the
brief, not only the chunks. The alignment pass emits observable yield.

**Constraints.** No new review round, reviewer or mode. The reviewer payload ceilings sit one over
their reading, so any added protocol text is paid by cutting duplication first. No schema field for
what an owner would say in a sentence.

**Inferred decisions (for the boundary):**
- *Inferred:* mid-build decisions reach the owner as one boundary-review NOTE with `scope: none`,
  the precedent the backlog reconciliation set, so no partial-schema change; the PR description's
  findings summary carries it to where the owner looks on return.
- *Inferred:* an inferred, never-confirmed goal is a WARNING at `boundary`. A goal the work
  contradicts that the owner *did* state is already a dropped requirement, BLOCKING under Goal 2.
- *Inferred, revised mid-build:* the goals check is a Goal 5 bullet ("Decisions Were Deliberate"),
  run by the sustainability reviewer on a coordinator roster, not a new cross-check. Planned for
  Goal 2; moved because Goals 1-3 are mirrored into chunk mode's `goals-1-3.md` under a parity
  test, and a boundary-only check has no place in the inner-stage file. Goal 5 already asks whether
  each capability traces to a requirement, which is the same question one level up.
- *Inferred, changes #978's acceptance:* the audit's 24/138 rests on a hand-selected subset of
  build turns (114 of the 180 a length-and-built filter yields), so no script reproduces it. The
  committed script defines "substantive" mechanically, and its own figures on the window before
  2026-10-09 become the baseline the November re-run compares like with like. Recorded in the
  change-log and the PR that closes #978.
- *Decided mid-build, departs from Constraints:* Goal 5's bullet could not be paid inside the
  reviewer payload ceilings by cutting duplication; the three full-review ceilings
  (`single-pass-full`, `dispatched-reviewer`, `coordinator-fork`) and `review-protocol.md`'s rise
  by +104 tokens, declared with its price in `tests/test_reviewer_payload_budget.py` and the
  change-log. What settled it: the check reads the one level no other check reads (goals the plan
  misread, where the audit's rework sorted), so +104 per full review is the cheaper side.

**Level:** High. All three items carry acceptance criteria and scope-outs under a settled design.

## Status

- [x] Chunk 01: The brief reads as current and says who said what (#974)
- [x] Chunk 02: The boundary review judges against goals (#975)
- [x] Chunk 03: Commit the alignment pass's yield measure (#978)

## Build Chunks

### Chunk 01: The brief reads as current and says who said what (#974)

- **Type:** doc-only
- **Depends on:** none
- **Deliverables:**
  - `plugin/methodology/discovery.md`: the brief is the product-level goals statement; an
    amendment rewrites the affected part of the body (history is git and the change log); a line
    the agent wrote without the owner saying so reads as an inference, in plain language.
  - `plugin/templates/product-brief.md`: the template states the rule once for the whole brief
    (today only Vision carries it) and shows one inferred line and how it reads once confirmed.
- **Acceptance criteria:** #974's two boxes.
- **Done when:** criteria met, tests pass, committed, ticked.

### Chunk 02: The boundary review judges against goals (#975)

- **Type:** doc-only
- **Depends on:** Chunk 01 (the confirmed-line form is what the reviewer reads)
- **Deliverables:**
  - `plugin/skills/critic/review-protocol.md` Goal 5 (see the revised inference above): judge the work against the
    plan's `## Goals` and the brief's near-term and North Star; list the plan's mid-build decisions
    for the owner in one NOTE; an inferred goal still unconfirmed is a WARNING; a decision marked
    as an alignment-pass miss is listed as such. Planned inside the payload ceilings;
    shipped as a declared +104 raise (Inferred decisions, last entry).
  - `plugin/methodology/reflection.md`: a mid-build decision that went against the owner's intent
    is an alignment-pass miss, and the reflection says what the pass should have asked.
  - Every surface describing what the boundary review judges is swept for the claim (review-cycle,
    building.md, the PR protocol, the w1 plan's "Tradeoffs accepted").
    Swept at the boundary (2026-10-09): none of the four states what the boundary review judges in
    terms Goal 5 contradicts, so none changed.
- **Acceptance criteria:** #975's four boxes. The fixture box is met by a trial: a fresh agent
  given the protocol and a fixture plan with one unconfirmed inferred goal and two mid-build
  decisions reports the WARNING and the decisions NOTE. Results recorded under Trial below.
- **Done when:** criteria met, tests pass, committed, ticked.

### Chunk 03: Commit the alignment pass's yield measure (#978)

- **Type:** code
- **Depends on:** none
- **Deliverables:**
  - `tools/measure-alignment-yield.py`, stdlib only, reading `~/.claude*/projects/*/*.jsonl`:
    per project and window, substantive requests, asked-before-build, mid-build AskUserQuestion
    calls, and correction-like owner turns (a lead, not a verdict).
  - A test over a synthetic transcript fixture covering each measure, including a negative case.
  - The baseline on the window before 2026-10-09, recorded in the change-log as the command plus
    its output and carried into the PR that closes #978. Governance is read from the session
    digest in the transcript, because deleted worktrees and cloud containers fail a disk check.
- **Acceptance criteria:** the revised #978 criterion above; the test passes and has been seen red.
- **Done when:** criteria met; `/prawduct:critic cumulative` run and blocking findings resolved;
  committed, ticked.

## Trial

Run 2026-10-09 for #975. A fresh agent read `review-protocol.md` and ran Goal 5 at `boundary` over
a fixture: a brief with one inferred line, a plan with one inferred architecture goal and two
recorded mid-build decisions (one settled by the brief, one marked an alignment-pass miss that
changed the owner's "next three days" goal to per-category windows).

| Expected | Got | Verdict |
|---|---|---|
| WARNING naming the plan's unconfirmed inferred goal | WARNING, with the design it would force a rebuild of | pass |
| One NOTE (`scope: none`) listing both decisions, what settled each, the miss flagged | One NOTE, both decisions, the miss flagged and tied to the goal it departs from | pass |
| — | A `scope-trace:` WARNING on the per-category thresholds (no parent requirement, nothing writes them) | correct, from the existing scope pressure-test |

The reviewer named one ambiguity: the protocol said "missing" an owner-stated goal, and the miss
*altered* one. It chose not to rate BLOCKING. Fixed: the bullet now reads "drops or alters". The
brief's own inferred line went into the NOTE rather than its own WARNING because nothing in the
changeset rested on it, which is the Severity Levels consequence test working as intended.
