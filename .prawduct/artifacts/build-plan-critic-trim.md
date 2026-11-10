---
artifact: build-plan
version: 2
scope: critic-trim
branch: feature/critic-trim
base: develop
working-branches: []
partition: "serial inside one Opus builder in an isolated worktree - the protocol files, the consolidation schema and the record-lint path interlock; the coordinator integrates, runs the suite once and governs"
governed_by:
  - artifact: data-model
    dispositions:
      - "verdicts computed from facts, no model in the write path → conforms; record-lint results reach the gate from code, which removes a model from that path"
      - "facts immutable and append-only → conforms; old note-severity findings stay as written and readable"
      - "derived views never authoritative → conforms; the findings cache stays a view"
      - "a newer-schema fact is surfaced, never dropped → conforms; a boundary fact carrying observations is an additive field readers already know from the inner stage"
      - "two stores, two lifetimes → inapplicable because no store changes"
      - "backlog_service_repo selects the authoritative backlog store → inapplicable because the reviewer's backlog walk is removed, not repointed"
      - "backlog issues conform to the title rules → inapplicable because no write path changes"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms; removes reviewer work and the disposition of notes"
      - "proportionality ratchets both ways → conforms; this is the removal arm, on 60-day yield (#1128)"
      - "state-file growth is advisory, never a hard block → inapplicable because no state file grows"
      - "review rigor is stage-keyed → conforms; the boundary keeps every blocking and warning rating and loses only the note severity, which becomes an observation as at the inner stage"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms; reviewers write less, not more"
      - "authority fails closed; advice fails soft → conforms; a record-lint blocking result still blocks, and consolidation still refuses a malformed partial"
      - "local-first → conforms"
      - "the plugin writes nothing into a governed repo except its own state → conforms"
      - "written in Python, never specific to Python → inapplicable because no product code is read"
      - "guides and reviews, never implements → conforms"
      - "goals and verification bind, method is advice → conforms"
      - "every fact has one home → conforms; a record-lint result has one producer and is no longer restated by a reviewer"
depends_on:
  - plugin/skills/critic/review-protocol.md
  - plugin/skills/critic/cross-checks.md
last_validated: 2026-11-10
---

## Goals

**Response taken:** Proceed, citing it. #1128 carries the requirement and the measurements, and
the owner's ruling of 2026-11-10 on deleting the model-relayed checks and notes-as-findings:
"Yes delete those".

**Product:** A Critic review stops producing output nobody acts on. The backlog walk, the
learnings cross-check and the `priors:` acknowledgement leave the reviewer. Record-lint results
reach the builder from the code that computes them. Nothing is rated NOTE as a finding at any
stage; what a reviewer would have rated NOTE is an observation, and an observation needs no
disposition.

**Architecture:** The reviewer protocol loses three passes. Consolidation accepts `observations`
from a boundary dispatch, as it already does from an inner one, and refuses a `note`-severity
finding. Record-lint findings are appended to the review's result by `critic-consolidate` from the
manifest's `record_lint`, at the severity the lint assigns, so a blocking record result blocks
exactly where it did.

**Constraints:**
- Goals 4-7 and the security check are untouched. Their fate waits on the paired native-review
  run (#1130).
- The PR reviewer is untouched (#1129).
- Evidence already written stays readable: `stats`, `review-stats` and the findings view still
  read old `note` findings.
- No new gate.

**Inferences, for the owner to veto at the boundary:**
- *Inferred:* the mid-build decisions list is printed by `critic-consolidate` from the plan's
  Goals section, where the builder relays the review's result, and is no longer a finding.
- *Inferred:* the norm-index rows that named the retired checks as their mechanism say what now
  holds them: backlog filing keeps Critic Goal 3 (norm departures); nothing else replaces the
  backlog walk.

**Decisions made mid-build:** *(appended while building)*

**Level:** High on what to remove. Medium on the record-lint path: the builder confirms from the
code where a relayed lint finding gets its blocking force today before moving it, and stops to
report if a gate reads it only through a reviewer's finding.

## Verification Strategy

The builder runs the test files covering the critic data plane and the protocol prose pins. The
declared suite runs once, on this branch, by the coordinator. The boundary review of this branch
runs on the installed plugin, which still has the old protocol, so its own output is the last
sample of what is being removed.

## Build Chunks

### Chunk 01: Notes become observations at every stage

- **Description:** Consolidation accepts `observations` from a boundary dispatch and refuses a
  `note`-severity finding with a message naming `observations`. The protocol files, the reviewer
  agent definition and the output schema say so. No surface asks the builder to disposition an
  observation.
- **Depends on:** none
- **Deliverables:** the schema change in `plugin/lib/critic_consolidate.py`; the severity text in
  `plugin/skills/critic/review-protocol.md`, `goals-1-3.md`, `review-cycle.md` and
  `plugin/agents/critic-reviewer.md`; the NEXT-ACTION copy that tells a builder to answer
  observations on the record; tests.
- **Tests:** Red first: a boundary partial with an `observations` array consolidates; a partial
  with a `note` finding is refused; an old fact with `note` findings still renders and still
  counts in `stats`.
- **Acceptance criteria:** as the tests state; no prose instructs a NOTE finding.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed

### Chunk 02: The reviewer stops relaying and cross-checking

- **Description:** Remove Backlog Reconciliation, the Learnings Cross-Check and the `priors:` note
  from the protocol, the roster and the reviewer's tool list where a tool existed only for them.
  Deliver record-lint results from consolidation. Print the mid-build decisions list from the
  plan instead of raising it.
- **Depends on:** Chunk 01
- **Deliverables:** `plugin/skills/critic/cross-checks.md`, `review-protocol.md`,
  `coordinator.md`, `SKILL.md` and `plugin/agents/critic-reviewer.md` without the three passes;
  record-lint findings in the consolidated result with no reviewer in the path; the plan-rendered
  decisions list; tests.
- **Tests:** Red first: the lint reports a blocking record, no partial mentions it, and the
  consolidated review blocks on it. A review whose partials raise no backlog or learnings finding
  consolidates clean.
- **Acceptance criteria:** no protocol file instructs a backlog walk, a learnings cross-check or a
  `priors:` note; a record-lint blocking result blocks the gate it blocked before.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed

### Chunk 03: Every description of the removed checks agrees

- **Description:** Sweep for the claim, not the tokens: methodology, docs, templates, the norm
  index, the cross-cutting registry and tests that describe a backlog walk, a learnings
  cross-check, a relayed record lint or a NOTE finding as live. Delete superseded sentences. Write
  the change fragment.
- **Depends on:** Chunk 02
- **Deliverables:** the swept surfaces; the norm-index rows updated; the change fragment with a
  consumer note saying what a builder will stop seeing.
- **Tests:** the prose pins and registry-completeness tests for the files touched.
- **Acceptance criteria:** the falsifying greps for each removed check return only history
  (change-log, archives) and this plan.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and the suite passes
  2. `/prawduct:critic cumulative` run and blocking findings resolved
  3. Committed
