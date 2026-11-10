---
artifact: build-plan
version: 2
scope: audit-guidance
branch: feature/audit-guidance
base: develop
working-branches: []
partition: "01-03 delegated to three Opus builders in isolated worktrees, disjoint by file and section; 04 and all integration by the coordinator on this branch. Seams the coordinator owns - session-digest.md outside its closing section, the prose budget tests, the change fragment."
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms; the new delegate guard refuses governance commands from a build delegate and changes no reviewer path"
      - "authority fails closed; advice fails soft → conforms; the close is advice the Stop hook reads, an unreadable close defers nothing, and the delegate guard is an authority refusal that fails closed"
      - "local-first → conforms; nothing new leaves the machine"
      - "the plugin writes nothing into a governed repo except its own state → conforms; the rulings record is written by the agent as product state, never by the plugin"
      - "written in Python, never specific to Python → inapplicable because no product code is read"
      - "guides and reviews, never implements → conforms; every change is guidance or a refusal"
      - "goals and verification bind, method is advice → conforms; the delegation rewrite states five things that hold and leaves the arrangement to the coordinator"
      - "every fact has one home → conforms; the close's shape lives in session-hygiene.md, delegation in delegation.md, and the digest points at both"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms; no review is added, and one Stop block class is removed"
      - "proportionality ratchets both ways → conforms; clear-reason leaves the blocking set on 60-day data (#1044), and its firings stay recorded"
      - "state-file growth is advisory, never a hard block → inapplicable because no state file grows"
      - "review rigor is stage-keyed → conforms; chunk reviews at the inner stage, one cumulative at the boundary"
depends_on:
  - plugin/methodology/session-hygiene.md
  - plugin/methodology/delegation.md
  - plugin/methodology/discovery.md
last_validated: 2026-11-10
---

## Goals

**Response taken:** Proceed, citing it. The owner ruled on each item on 2026-11-10 in reply to the
audit's decision list, and the three backlog items carry the requirements and quote the rulings:
#1131 ("Cut to one line", and the ask must sit "where the user will actually see it"), #1133 ("Yes
to delegation draft"), #1135 ("Yes adopt").

**Product:** Three changes to what every governed session is told.
- A turn ends with one line, and a turn that needs the user ends with the asks themselves.
- Delegation is the default when it shortens wall clock without collision, with five things that
  hold however the coordinator arranges it.
- Requirements guidance covers the four ways governed work was measured to go wrong after the
  alignment pass: a late first look, a lost ruling, an agent-originated rule, no convergence.

**Architecture:** Guidance changes, two small code changes. `standing_block` reads a one-line close
and keeps reading the three-paragraph one, because sessions on an older digest still write it.
Governance commands refuse a build delegate. No new gate, no new fact kind beyond what
`clear-reason` needs to record instead of block.

**Constraints:**
- The session digest has a 10,000-character wall. Chunk 01 shortens its closing section; chunks 02
  and 03 add nothing to it themselves (owner of the seam: the coordinator, Chunk 04).
- No new gate (owner, 2026-09-19: "We default to adding tax everywhere").
- Reviewers still inherit the session model. The norm index pins it, and changing it is the
  owner's ruling to make, not this plan's.
- Natural language over schema: the rulings record is prose with no parser.

**Inferences, for the owner to veto at the boundary:**
- `clear-reason` records instead of blocking. Built as an inference from "I think we already
  moved clear-verdict to non-blocking" (true of its sibling only); the owner then ruled on it the
  same day: "Yes clear-reason to stop blocking".
- *Inferred:* the one-line close keeps the existing labels (`RUNNING`, `YOUR TURN`, `COMPLETE`,
  `SAFE TO CLEAR`, `DO NOT CLEAR`), so the Stop hook's deferral rule and old transcripts keep
  their meaning.
- *Inferred:* the rulings record's file name and template are the builder's proposal in Chunk 03.

**Tradeoffs accepted:** The approved delegation draft says a review-shaped piece of delegated work
takes the stronger model. That is about delegates, not the Critic or PR reviewers; the guide says
so in a clause rather than reopening the reviewer-model norm.

**Decisions made mid-build:**
- Chunk 02 — the delegate guard already existed (`_check_ephemeral_worktree` refuses
  `critic-begin` from a harness scratch worktree), so the code change is the refusal naming the
  coordinator. A delegate sharing the coordinator's worktree, or on a named branch, is still not
  refused: no reliable predicate separates it from the coordinator. Settled by the plan's own
  instruction to stop rather than ship a guess; the guide carries that case.
- Chunk 02 — "always name the model at dispatch; never inherit a stronger one by default" joined
  the guide and the digest, on the owner's ruling of 2026-11-10: "we need to be very careful to
  not accidentally spam fable subagents anywhere, given the cost". Capping the reviewers is its
  own item (#1136).
- Chunk 03 — the rulings record is `.prawduct/owner-rulings.md`, from
  `plugin/templates/owner-rulings.md`. *Inferred* (the builder's proposal): the `.prawduct/` root
  because it is a running record like the operator-verification queue, and "owner-" because
  "ruling" already names a norm-boundary ruling in `docs/norms.md`.
- Chunk 03 — `building.md`'s size ceiling is raised, declared: about two thirds of the new
  guidance was paid in place, and the rest is kept rather than cutting the backwards-compatibility
  trap, the owner's standing rule and the only copy a delegate reads.
- Chunk 04 — the digest sentences were paid in place rather than spending its reserve: the
  tangent bullet's three-way choice (the guide owns it), the handoff bullet's round-trip clause,
  and two parentheticals. The builder's proposed alignment paragraph was not taken, because it
  dropped the owner-ratified mid-build order and "fast-moving data is verified, not recalled".
  An alignment-pass miss: the plan expected Chunk 01 to free more of the digest than it did.

**Level:** High.

## Verification Strategy

Each builder runs only the test files that cover what it changed. The declared suite runs once, on
this branch, after the three chunks are merged (Chunk 04). Guidance is also tried, not only read:
Chunk 04 hands the new text to fresh agents on three small tasks and checks what they do.

## Build Chunks

### Chunk 01: The close is one line and ends with the ask

- **Description:** #1131. Rewrite the close's rule in `session-hygiene.md` and the digest's closing
  section: one line, last, carrying disposition, clear verdict and a short reason; a turn that
  needs the user restates every ask in full immediately above it, numbered, never "see above".
  `standing_block` reads the one-line form and the old three-paragraph form. `clear-reason`
  records instead of blocking, through the same sink `clear-verdict` uses.
- **Depends on:** none
- **Deliverables:** the rule in `plugin/methodology/session-hygiene.md`; the closing section of
  `plugin/methodology/session-digest.md`, shorter than before; one-line parsing in
  `plugin/lib/standing_block.py`; the Stop hook no longer blocks on the close's wording; every
  other surface that describes the three-paragraph block or says `clear-reason` refuses agrees
  with the new rule; tests.
- **Tests:** unit: disposition and verdict read from a one-line close, from the old form, and from
  a turn with labels quoted mid-prose (must yield none). Red first: the Stop hook defers
  reflection and Critic on a one-line `RUNNING` + `DO NOT CLEAR` close; a self-citing close is
  recorded and does not block.
- **Acceptance criteria:** a session following the digest closes in one line; a hand-over turn
  ends with its asks restated; no Stop gate blocks on the close's wording; `stats` still reports
  `clear-reason` firings.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed

### Chunk 02: Delegation by default, with five things that hold

- **Description:** #1133. `delegation.md` opens with the owner-approved draft, verbatim from the
  item, and the rest becomes trimmed reference beneath it. `building.md` § Delegating and
  `planning.md` § Partition stop saying merges and integration always stay with the main agent,
  and the closed list of reasons to ask for approval goes. Preferences keep `Delegation` and
  `Delegate verification`; `Delegation approval` is retired from the template and the doctor
  flow. `critic-begin` and the state-writing commands refuse a build delegate.
- **Depends on:** none
- **Deliverables:** the rewritten guide; the two methodology sections; the preferences template
  rows and the doctor flow; the delegate guard with its refusal message; tests; a proposed
  two-line digest sentence in the builder's report (not an edit to the digest).
- **Tests:** Red first: `critic-begin` run by a subagent from a harness scratch worktree refuses
  and names the coordinator; the same command from the coordinator's checkout is unchanged.
  Existing prose pins updated only where the rule they pin changed, each named in the report.
- **Acceptance criteria:** no surface contradicts the guide on who may integrate; the guide says
  the coordinator may set a delegate's model and effort; `Delegation: off` is still honoured
  without ceremony.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed

### Chunk 03: Requirements guidance for looked-at output, rulings, originated rules, convergence

- **Description:** #1135. Four additions, each stated once in the guide that owns it: see it first
  (`discovery.md`, with the plan's verification strategy in `planning.md`); a ruling is written to
  the product's rulings record before the reply (`building.md`, with a template naming the
  record); an agent-originated rule is labelled, names whose need it serves, and is offered with
  "don't have this" first (`discovery.md`, and the alignment pass in `building.md` for
  agent-proposed work); the third fix on one surface stops for a definition, and an acceptance
  loop ratifies a checklist once (`building.md`).
- **Depends on:** none
- **Deliverables:** the four additions; a rulings-record template under `plugin/templates/`; each
  guide inside its prose budget, paid for in place; a proposed digest sentence in the builder's
  report (not an edit to the digest).
- **Tests:** the methodology prose budget tests for the files touched; a template-presence test if
  the templates are enumerated by one.
- **Acceptance criteria:** each of the four appears once, in the guide that owns it, as guidance
  an expert agent can apply by judgment; nothing reads as a gate, a checklist to fill, or a
  schema.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed

### Chunk 04: Integration, the digest, and trying the guidance

- **Description:** Merge 01-03 on this branch. Add the delegation and requirements sentences to
  the digest inside its wall. Run the declared suite once. Hand the new text to fresh agents on
  three small tasks: a three-chunk plan with two independent chunks (does it disclose the
  fan-out, name models, and keep the suite off the delegates?); a request for a report over an
  existing data source (does it propose a rendered specimen first?); an owner ruling given
  mid-conversation (is it written to the record before the reply?). Write the change fragment.
- **Depends on:** Chunk 01, Chunk 02, Chunk 03
- **Deliverables:** the merged branch; the digest sentences; the trial results recorded in the
  change fragment; suite green.
- **Tests:** the digest wall and budget tests; the declared suite.
- **Acceptance criteria:** the three trials behave as the guidance says, or the guidance is
  changed until they do; the digest is inside its wall; suite green.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and the suite passes
  2. `/prawduct:critic cumulative` run and blocking findings resolved
  3. Committed
