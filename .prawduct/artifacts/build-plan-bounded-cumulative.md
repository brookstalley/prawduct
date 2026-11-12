---
artifact: build-plan
version: 2
scope: bounded-cumulative
branch: feature/bounded-cumulative
base: develop
working-branches: []
partition: "01 (Opus-class, high) delegated to one builder in an isolated worktree; it owns tools/ and its tests and touches nothing in plugin/. 02-04 serial after 01's report, because 01's result can reopen Decision 2 before any build (design, § The interaction sweep), and 02 and 03 share critic_consolidate.begin_review and the protocol prose. The coordinator integrates and governs"
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms; a repeat cumulative on an unchanged base reviews the delta, not the bundle"
      - "proportionality ratchets both ways → conforms; Chunk 04 measures the yield, and the falsifier below says what retires the lever"
      - "state-file growth is advisory, never a hard block → inapplicable because no state file's growth rule changes; Chunk 01 writes nothing outside its report"
      - "review rigor is stage-keyed → conforms; a bounded cumulative is still a boundary review with all seven goals, and record-lint keeps grading merge-base → HEAD (Decision 3)"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms; the reviewer's subject narrows and it gains no write"
      - "authority fails closed; advice fails soft → conforms; any frontier condition that declines falls back to the full span, with its reason"
      - "local-first → conforms; the sweep is `git grep -F`, local, and Chunk 01 reads local ledgers and git"
      - "the plugin writes nothing into a governed repo except its own state → conforms; the tool reads a consumer repo read-only and writes only its report"
      - "written in Python, never specific to Python → conforms; the vanished-token sweep is plain text search over any file type (design, § The interaction sweep)"
      - "guides and reviews, never implements → conforms"
      - "goals and verification bind, method is advice → conforms"
      - "every fact has one home → conforms; the frontier is one function next to gates.covered_frontier"
  - artifact: data-model
    dispositions:
      - "verdicts computed from facts, no model in the write path → conforms; composition and the PR gate are unchanged (design, § Unchanged)"
      - "facts immutable and append-only → conforms; `span` and `bounded_from` are additive fields on new facts"
      - "derived views never authoritative → conforms"
      - "a governance document reaches a terminal state and is never deleted → conforms; the design doc moves from an unmerged branch onto this one rather than being redrawn"
      - "backlog issues conform to the title rules → inapplicable because no backlog write path changes"
      - "a newer-schema fact is surfaced, never dropped → conforms; old facts read as `span: full`"
      - "two stores, two lifetimes → conforms; the new fields ride the shared review fact"
      - "backlog_service_repo selects the authoritative backlog store → inapplicable because no backlog read changes"
depends_on:
  - .prawduct/artifacts/bounded-cumulative-design.md
  - plugin/lib/critic_consolidate.py
  - plugin/lib/coverage.py
  - plugin/lib/gates.py
last_validated: 2026-11-11
---

## Goals

**Response taken:** Proceed, citing it. #890 is `stage:ready`. Its design is
`.prawduct/artifacts/bounded-cumulative-design.md`, brought onto this branch from `fb2cee1b`
(drawn 2026-09-22, never merged). The design records six owner decisions, all from 2026-09-22.
The owner chose to build it on 2026-11-11 (the ruling is in `.prawduct/owner-rulings.md` on
`feature/gate-clarity`). The design said not to build until #885 and a consumer re-baseline were
in. #885 has since been dropped, and Chunk 01 is the re-baseline: it re-derives the table on
today's ledgers before anything is built.

**Product:** a long-lived branch's repeat cumulative reviews what changed since the last
boundary review, not the whole bundle again. A measured example from the design: discodon
covered 70, 110 and 128 files where 65, 56 and 35 had changed. Same-base repeats cut subject
files by 32–46% on three repos.

**Architecture:** the design, § Design and § Unchanged. Coverage composition and the PR gate do
not change.

**Constraints:**
- The six decisions in the design bind.
- This repository is public. A tool that reads a consumer's ledger commits no consumer data: its
  output goes into the builder's report, not into a tracked file. The design's dated reading
  follows existing practice, aggregate counts with product names.

**Decisions made mid-build:** (appended while building)

**Level:** Medium. Whether the vanished-token sweep catches enough of the nine stale-prose losses
is not measured (the design says so). The cheapest step that would raise the level is Chunk 01's
replay of the sweep on those nine.

**Falsifier (from the design):** the lever is retired if either holds:
- bounded rows on discodon do not come in well under the full rows of similar total bundle size;
- bounded rows whose later full span or PR review finds blockers on old-only files do so at a rate
  well above the ~1% measured.

## Verification Strategy

Chunk 01 is measurement. Its tests run the tool on a synthetic ledger and git history whose
answer is known. A fixture must trip each classification: delta, old-only and no-files. Its
report carries the re-derived table for this repo and the consumers named in the design, the
sweep's catch count on the nine stale-prose losses, and the overlap rate on base-advanced repeats.
The coordinator reads that report against Decision 2 before Chunk 02 is dispatched. Chunks 02–03
are verified as the design's Build shape says. The full suite runs once, on the integrated branch.

## Build Chunks

### Chunk 01: The trade is re-derivable, and Decision 2 is tested before any build

- **Description:** The design's Build shape item 1. new `tools/measure-repeat-cumulative-yield.py`,
  with tests, is the method in § Measured trade, landed as a tool. For every cumulative in a
  ledger, it finds the newest earlier cumulative whose reviewed commit is an ancestor. It then
  splits this review's findings into delta, old-only and no-files, and reports the same-base and
  all-repeat tables. It also reports two more things:
  - for each of the nine stale-prose losses, whether a vanished-token scan (§ The interaction
    sweep, steps 2–3) would have caught it;
  - the file-overlap rate on base-advanced repeats (Decision 4's v2).

  It takes a repo path and reads that repo's ledger and git history read-only.
- **Depends on:** none
- **Deliverables:** new `tools/measure-repeat-cumulative-yield.py`,
  new `tests/test_measure_repeat_cumulative_yield.py`, and this plan's design doc (brought in with
  the plan).
- **Tests:** Red first, on a synthetic repo built in a temporary directory. These cases trip the
  classification:
  - a finding on a file changed since the prior cumulative is delta;
  - a finding on a file only the prior one rated is old-only;
  - a finding with no file is no-files;
  - a non-ancestor prior is not used;
  - a base-advanced repeat is counted apart from the same-base ones.

  A corrupt ledger line is skipped and counted, not fatal.
- **Acceptance criteria:**
  - The tool runs on this repo and on each consumer the design names that exists on this machine,
    and the report carries its output.
  - The nine stale-prose cases are named, each with caught or missed and the tokens that would
    have hit.
  - No consumer data is committed.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 02: Frontier and interval

- **Description:** The design's Build shape item 2. Built after the coordinator reads Chunk 01's
  report. If the sweep catches few of the nine, Decision 2 goes back to the owner first.
- **Depends on:** 01

### Chunk 03: Protocol

- **Description:** The design's Build shape item 3.
- **Depends on:** 02

### Chunk 04: Measure, and the boundary review

- **Description:** The design's Build shape item 4. The change record goes in
  `.prawduct/changes/bounded-cumulative.md`, and one cumulative Critic names every chunk.
- **Type:** cumulative-final
- **Depends on:** 03
