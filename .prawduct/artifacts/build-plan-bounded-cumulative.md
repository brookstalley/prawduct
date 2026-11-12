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

- Chunk 01 result, 2026-11-11, re-derivable with `python3 tools/measure-repeat-cumulative-yield.py <repo>`;
  `--until 2026-09-22T23:00:00Z` gives the dated reading.
  - **The dated table reproduces.** Same-base blocking old-only matches exactly: 3 of 54, 7 of 25,
    3 of 35. The subject-file cut on same-base repeats now reads −58% on discodon and −32% on
    prawduct from the ledger alone, and −60% and −37% with the evidence store, which the ledger
    undercounts.
  - **The 33 old-only blockers are mostly not losses.** Only 13 sit on same-base rows; the other 20
    are on new-branch or base-advanced rows, which run full-span under conditions 2 and 4. On
    same-base rows the split is 4 stale prose, 3 code already seen, and 6 machine relays.
    Decision 3 covers record-lint, but not the 2 test-evidence relays among those 6. With no sweep
    catches, the expected same-base blocking loss is about 7 in 114 (about 6%), not about 1%.
  - **Decision 2's sweep fails its test.** As designed (vanished tokens, `git grep -F`, capped), it
    reaches the finding's file through a token the finding names in 0 of the nine stale-prose
    losses. It reaches the file by accident in 2. A 4-word phrase variant catches 2 of the nine,
    both on new-branch rows. Two causes:
    - masking: a retired name still appears in the delta's own plan, change-log and tests, so it
      never "vanishes";
    - hard-wrapping: wrapped markdown defeats a whole-string grep.
  - **Decision 4 (v2):** about 10–19% of a base-advanced repeat's rated files overlap the advance.
    The per-file version would transfer more than half the rated files on discodon.
  - By the design's own rule ("If it catches few, Decision 2 reopens before any build"), Decision 2
    goes back to the owner, and Chunk 02 is held until it is ruled.
- **Owner re-ruling, 2026-11-11** (`.prawduct/owner-rulings.md` on `feature/gate-clarity`): "yes,
  follow your recommendation".
  - No vanished-token sweep is built.
  - Every machine relay (record-lint, plus the test-evidence relays Decision 3 did not name) keeps
    grading merge-base → HEAD while the review is bounded.
  - Chunk 04 measures the real same-base blocking loss against the falsifier.
  - Chunk 02 is unblocked.
- **Chunk 01 fix round, 2026-11-11** (67bb137b): the removed-line parse now follows hunk state, and
  `--vanished-in source` selects the design's literal "gone from those files" reading. On the
  dated window (`--until 2026-09-22T23:00:00Z`), the nine stale-prose losses come out like this:
  - **Default reading** (`changed`): 0 reached through a token the finding names, and 2 reached
    by accident. This is the reading Decision 2 was re-ruled on.
  - **Literal reading** (`source`): 1 real catch through the finding's own words, or 2 with 4-word
    phrases. Two more look named, but they hit only because a build plan was renamed. All of these
    are on prior-in-base rows. Those are new-branch rows, which run full-span, so no sweep would
    run on them. As built, this reading counts a renamed file's old path as gone, so the path's
    tokens flood the token budget; a literal sweep would have to follow renames.
  - **Same-base rows**, the only rows a bounded review runs on: the sweep reaches 0 of the 4
    stale-prose losses through a named token, under either reading. The re-ruling stands, and
    nothing goes back to the owner.
  - The literal reading's other extra hits are mostly common words (`Never`, `chose`, `Since`).
- **Chunk 02 decisions, 2026-11-11** (made while reading the code, before building):
  - `boundary_frontier` lives in `gates.py` beside `covered_frontier`, not in `coverage.py`. The
    plan's `coverage.` prefix was a slip: the governed-by disposition already says "next to
    gates.covered_frontier", and the store and diff helpers it needs live in `gates`.
  - Condition 2 compares the fact's bundle base: the tree of its `base_reviewed` commit when it
    records one, else its `base_tree`. A bounded fact's `base_tree` is its own frontier, so reading
    `base_tree` alone would refuse every second bounded repeat.
  - The walk skips a newer fact that fails condition 2 or 3 (another lineage, an older base). It
    declines on the newest candidate's condition 4 or 5 and never falls back to an older frontier,
    which would bound around that blocker.
  - "Machine relays grade merge-base → HEAD" in code: record-lint and the chunk proposal run on the
    bundle's files and trees, exactly as a full span would. The test-evidence relays are the
    reviewer's own `test-status`, which reads the HEAD tree whatever the span. So for those, the
    manifest carries the bundle span, and Chunk 03's protocol says they are rated regardless of
    subject.
  - The `full` override: `/prawduct:critic cumulative full` reaches `infer-critic-mode` verbatim,
    and it answers the rationale `explicit-args full`. `begin_review` reads that rationale from
    `--chosen-by`, which the skill already forwards verbatim. There is no new flag and no new
    skill step.
  - **Corrected in Chunk 03:** the rest of the bundle rides as `files_context`, not `files_oracle`.
    The Records Pass rates the oracle at the boundary stage, so handing the bundle over as oracle
    would have re-rated its records and put its code through a records-only pass. That is the
    whole-bundle review this span exists to stop buying. Found while writing the protocol: the
    `begin_review` comment "The Records Pass at `final`/`cumulative` is what rates this set".
  - A bounded delta with no judgeable file meets the existing free-interval refusal (exit 3).
    That is correct: the frontier's edge plus a free edge already compose.
  - The fact also carries `span_reason`: the declined condition's short code when the span is
    full, or null when it is bounded. Chunk 04's measurement needs to know why reviews ran full,
    so it is recorded where it is known. Chunk 04's `review-stats` split is the first reader of
    `span`, and it reads a fact without one as full.

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

- **Description:** The design's Build shape item 2, as amended by the owner's 2026-11-11 re-ruling
  of Decision 2. It builds:
  - `coverage.boundary_frontier` (conditions 1–5, each declining with a reason);
  - the bounded branch in `begin_review`;
  - `span` and `bounded_from` on the manifest, fact and ledger;
  - the `full` override token in `infer-critic-mode`;
  - record-lint and the test-evidence relays grading the bundle span merge-base → HEAD.

  The vanished-token sweep is not built.
- **Depends on:** 01
- **Deliverables:** `plugin/lib/gates.py` (`boundary_frontier`), `plugin/lib/critic_consolidate.py`
  (the bounded branch, manifest validation, fact and findings-cache fields), `plugin/lib/critic_mode.py`
  (the `full` token), new `tests/test_bounded_cumulative.py`.
- **Tests:** Red first, on real git repos with facts written through `evidence.append_fact`:
  - each frontier condition declining on its own, with its reason: no boundary review; base moved;
    head not an ancestor; head already reviewed; path to the frontier blocked;
  - a sibling lineage's newer boundary fact is skipped, not taken;
  - a blocker on the newest boundary review forces a full span, not an older frontier;
  - a bounded dispatch's manifest: interval frontier → HEAD, `span: bounded`, `bounded_from`, subject
    is the delta, the rest of the bundle rides as oracle, roster from the delta, and record-lint and
    the chunk proposal graded on the bundle span;
  - its fact composes with the frontier's to a passing PR gate (`check_cumulative_critic`);
  - `span`/`bounded_from` reach the fact and the findings cache (which the ledger copies);
  - `cumulative full` answers explicit-args full, and that dispatch is full-span with its reason.
- **Acceptance criteria:**
  - A repeat cumulative on an unchanged base, with a clean path to the last boundary review, reviews
    only the delta, and the PR gate's verdict is unchanged.
  - Every declined condition falls back to the full span and says why on the dispatch's notes.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 03: Protocol

- **Description:** The design's Build shape item 3, without the sweep: the bounded-mode sentence
  in `review-protocol.md`, the Per-Mode table row and a bounded-repeat paragraph in
  `review-cycle.md`, the `full` override where the skill and the precedence list name the modes,
  and the reviewer prompt naming the span and its frontier. The prompt is the code-rendered
  `Signals:` line, which ends `Span: bounded from <id>` or `Span: full` on a cumulative. It also
  corrects every sentence Chunk 02 made false by claiming a cumulative spans merge-base...HEAD.
- **Depends on:** 02
- **Deliverables:** `plugin/skills/critic/review-protocol.md`, `plugin/skills/critic/review-cycle.md`,
  `plugin/skills/critic/SKILL.md`, `plugin/methodology/planning.md`, `plugin/skills/pr/SKILL.md`,
  `plugin/lib/critic_consolidate.py` (`signals_line`, `files_context`), `tests/test_bounded_cumulative.py`.
- **Done when:** the prose and the code it names are pinned to each other, the budgets that price
  reviewer payload say what the span cost, and the change is committed. It is reviewed at the plan
  boundary.

### Chunk 04: Measure, and the boundary review

- **Description:** The design's Build shape item 4. The change record goes in
  `.prawduct/changes/bounded-cumulative.md`, and one cumulative Critic names every chunk.
- **Type:** cumulative-final
- **Depends on:** 03
