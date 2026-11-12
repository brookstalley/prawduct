---
artifact: build-plan
version: 2
scope: review-round-cost
branch: feature/review-round-cost
base: develop
working-branches: []
partition: "01 (Sonnet-class, high) and 02 (Opus-class, high) delegated to two builders in isolated worktrees. Seams: critic_consolidate.validate_partial's body belongs to 02, which adds the `failed_tests` field, and 01 only calls it from the new check_partial; in consolidate, the per-partial read loop belongs to 01 and the block after the review fact is appended belongs to 02; the dispatcher's usage line and command sets in prawduct-hook belong to 01 (the new verb), and cmd_test_evidence's run fact belongs to 02. The coordinator integrates, runs the suite once, writes Chunk 03 and governs"
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms; 01 turns a lost round into one reviewer re-dispatch, and 02 removes a verify-resolutions round from every branch with an inherited red base"
      - "proportionality ratchets both ways → conforms; no control is added that blocks, and the new verb is a reviewer-side check whose refusal is the existing fail-closed consolidation, met earlier"
      - "state-file growth is advisory, never a hard block → inapplicable because no state file's growth rule changes; the run fact gains at most the 100 ids the evidence record already caps"
      - "review rigor is stage-keyed → conforms; an inherited failure is still rated BLOCKING (owner ruling 2026-10-21 on #900), and only its waiver is automated"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms; the reviewer gains a read-only check of its own output, and no write to anything else"
      - "authority fails closed; advice fails soft → conforms; consolidation stays fail-closed on any unreadable partial, and the waiver fails closed when no base-tree run lists every id"
      - "local-first → conforms; the classifier reads the clone-shared store and git, nothing networked"
      - "the plugin writes nothing into a governed repo except its own state → conforms; the waiver is a fact in the shared evidence store, and nothing else is written"
      - "written in Python, never specific to Python → conforms; test ids are opaque strings from whatever JUnit report the suite wrote"
      - "guides and reviews, never implements → conforms; no product code, config or tooling is written"
      - "goals and verification bind, method is advice → conforms; Chunk 01 departed from the issue's grant spelling to the house form, recorded below"
      - "every fact has one home → conforms; 01 has one check_partial that both the verb and consolidate call, and 02 has one classifier for inherited failures"
  - artifact: data-model
    dispositions:
      - "verdicts computed from facts, no model in the write path → conforms; the waiver is written by consolidate from the base-tree run fact, and the reviewer only names the ids it rated"
      - "facts immutable and append-only → conforms; the waiver is a new resolution fact with a deterministic id"
      - "derived views never authoritative → conforms; the findings cache shows waived findings, and no gate reads it"
      - "a governance document reaches a terminal state and is never deleted → inapplicable because no plan or record is deleted"
      - "backlog issues conform to the title rules → inapplicable because no backlog write path changes"
      - "a newer-schema fact is surfaced, never dropped → conforms; `failed_tests` on a run fact and `origin`/`base_run` on a resolution fact are additive, and the classifier fails closed on a run fact it cannot parse"
      - "two stores, two lifetimes → conforms; the waiver is a fact in the clone-shared store, and nothing per-clone becomes an answer"
      - "backlog_service_repo selects the authoritative backlog store → inapplicable because no backlog read changes"
      - "a resolution fact requires a verify-resolutions origin (the constraint in the data model's body) → amended by owner ruling; the owner ruled auto-waive on 2026-10-21 (#900), and the constraint gains the inherited-baseline origin as that item specifies"
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning → conforms; no subcommand gains a version of its own"
      - "exit codes are the contract → conforms; validate-partial exits 0 ok, 1 with the reason, 2 on a usage error"
      - "additive-first evolution → conforms; one new read-only verb, one optional finding field, and two additive fact fields"
depends_on:
  - plugin/lib/critic_consolidate.py
  - plugin/lib/evidence.py
  - plugin/bin/prawduct-hook
  - plugin/agents/critic-reviewer.md
  - plugin/skills/critic/SKILL.md
  - .prawduct/artifacts/data-model.md
last_validated: 2026-11-11
---

## Goals

**Response taken:** Proceed, citing it. The owner chose these items on 2026-11-11 (the ruling is in
`.prawduct/owner-rulings.md` on `feature/gate-clarity`; their words: "Yes please for 937, 890,
961, 900, 1000, 682, and 1098 using subagents, opus or sonnet, each with appropriate effort level
and following our delegation protocol"). #961 and #900 are `stage:ready`, and each carries its
problem, proposed change, decisions and acceptance. #900 also carries the owner's ruling of
2026-10-21: auto-waive.

**Product:** a review round costs a consumer minutes each time. Two causes waste a whole round:
- #961: one malformed reviewer partial (an unescaped quote) throws away every reviewer's valid
  work. 4.5 minutes were lost and the round was re-run.
- #900: a branch whose base is already red pays a verify-resolutions round to waive a failure it
  did not cause.

Governed products have each written themselves a rule that "each fix commit buys another review
round". This plan removes two rounds that buy nothing.

**Architecture:** fail-closed consolidation stays as it is: a review never persists with a role
missing. The inherited failure stays BLOCKING in the record, and its waiver is a fact that cites
the base-tree run.

**Constraints:**
- Each item's scope-outs bind.
- #961: no automatic repair of malformed JSON, and no automatic re-dispatch from a hook.
- #900: matching is on the tree, not the head, and the cap of 100 ids fails closed.

**Decisions made mid-build:** (appended while building)

- Chunk 02: `next_action_line` and `fact_to_cache_record` take the waived findings and take them out
  of the open blocking count. The NEXT-ACTION line names them first, and the review fact's `counts`
  are unchanged. Settled by the goal: telling the builder to fix a waived finding buys the very
  round #900 removes. This edit is outside the block the partition assigned to Chunk 02, but it
  does not touch Chunk 01's per-partial loop.
- Chunk 02: the classifier skips narrowed runs, matching `_store_run_vouching`, and a test pins it.
  A degraded base run still supplies failing ids. Settled by matching the product's other choices
  about what a run vouches for.
- Chunk 02: a `failed_tests` that is a bare string fails validation, as #900's acceptance says.
  That is stricter than `hook-surface.md`'s tolerance for a model-written field. Chunk 01's
  `validate-partial` lets the reviewer catch it before returning. Not settled by the goals: the
  issue's acceptance outranked the learnings rule here, and the boundary review should weigh it.
- Chunk 02: the methodology budget raises were declared with reasons in `test_v5_methodology.py`
  (`building.md` +37, `goals-1-3.md` +13, `review-cycle.md` +71). Dated records that state the old
  rule are left as history: the loop-nontermination diagnosis, an archived plan, and the #167
  design.
- Chunk 01: `check_partial` keeps the `(ok, reason)` signature. Its body is `_load_partial`, which
  returns the parsed record, so `consolidate` reads each file once and gets one verdict on it. The
  check also refuses a file that is not the review's keyed partial path. That condition is always
  true inside consolidate, and it is what makes the verb refuse a stray file. The verb resolves a
  relative path against the project, not the caller's working directory.
- Chunk 01: the grants use the house form with the star attached to the word
  (`validate-partial*`), as `test_skill_command_grants.py` enforces, rather than the issue's
  spaced form. The spaced form would not cover the bare call.
- Chunk 01: an inline single-pass fork (roster `reviewer` and no `reviewer_model`) is told to
  rewrite its partial and re-run consolidate, because it has no reviewer to re-dispatch.
- Integration: both chunks added functions at the same place in `critic_consolidate.py`, and the
  merge keeps both. The payload budget takes Chunk 02's declared +13 on the three inner routes, on
  top of Chunk 01's raises.

**Level:** High. Both items name their functions, their acceptance and their red-first tests.

## Verification Strategy

Each chunk's tests are red first at the behaviour it adds, and each names the input that must trip
it. 01: the two valid partials are byte-identical after a failed consolidate, and the verb and
consolidate return the same verdict for the same file. 02: the waiver's five no-waiver cases and
the idempotent re-run. 02 is a sweep of a stated rule, so it returns the falsifying grep for "only
verify-resolutions may write a resolution fact", in more than one phrasing. The full suite runs
once, on the integrated branch.

## Build Chunks

### Chunk 01: One unreadable partial costs one reviewer, not the round (#961)

- **Description:** #961's proposed change, in full:
  - A new read-only verb `prawduct-hook validate-partial <path>`, whose body is a new
    `critic_consolidate.check_partial(prawduct_dir, manifest, role, path) -> (ok, reason)`. The
    per-partial checks in `consolidate`'s loop are factored out into it, so both callers use it.
  - The reviewer validates its own partial before it returns. The verb goes in
    `critic-reviewer.md`'s `tools:` and the Critic `SKILL.md` `allowed-tools`, and the write step
    gains one sentence.
  - On a failed check, consolidate's stderr names the role, says the other partials passed and are
    kept, and gives the one-reviewer re-dispatch remedy. `SKILL.md` and `coordinator.md` each
    carry that remedy in one sentence.
- **Depends on:** none
- **Exposed API:** `prawduct-hook` CLI
- **Deliverables:** `plugin/lib/critic_consolidate.py` (new `check_partial`, and the partial loop
  in `consolidate`), `plugin/bin/prawduct-hook` (the verb, its usage line and its read-only
  classification), `plugin/agents/critic-reviewer.md`, `plugin/skills/critic/SKILL.md`,
  `plugin/skills/critic/coordinator.md`, the verb's entry in `.prawduct/artifacts/api-contract.md`,
  and tests in `tests/test_critic_consolidate.py`.
- **Tests:** #961's acceptance, red first.
- **Acceptance criteria:** #961's checklist, including `tests/test_reviewer_payload_budget.py`
  green, or its budget raised with the reason recorded.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 02: An inherited red baseline is waived by consolidate, not by a round (#900)

- **Description:** #900's proposed change, all five steps:
  - Run facts carry `failed_tests`.
  - Findings may name the `failed_tests` they rate, validated in `validate_partial`, and
    `goals-1-3.md` gains one sentence saying so.
  - One classifier, `evidence.inherited_failures`, matches the merge-base tree.
  - Consolidate writes a `waived` resolution fact with `origin: inherited-baseline` when every id
    is in the base run's set.
  - The records that describe the old rule are swept, and `building.md` gains the
    clean-merge-base run step.
- **Depends on:** none
- **Deliverables:** `plugin/bin/prawduct-hook` (`cmd_test_evidence`'s run fact),
  `plugin/lib/evidence.py`, `plugin/lib/critic_consolidate.py` (`validate_partial`, and the block
  after the review fact is appended), `plugin/skills/critic/goals-1-3.md`,
  `plugin/skills/critic/review-cycle.md`, `plugin/methodology/building.md`,
  `.prawduct/artifacts/data-model.md`, `tests/test_test_run_facts.py` and
  `tests/test_critic_consolidate.py`.
- **Tests:** #900's acceptance, red first.
- **Acceptance criteria:** #900's checklist, with the falsifying grep output in the report.
- **Done when:**
  1. Acceptance criteria met and the chunk's own tests pass
  2. Committed (reviewed at the plan boundary)

### Chunk 03: The record, the seams, and the boundary review

- **Description:** The coordinator merges both builder branches, resolves the `consolidate` and
  `prawduct-hook` seams, runs the suite once, writes `.prawduct/changes/review-round-cost.md`, and
  runs one cumulative Critic naming 01 to 03.
- **Type:** cumulative-final
- **Depends on:** 01, 02
- **Done when:**
  1. Suite green on the integrated head, recorded
  2. Cumulative review with no unresolved blocking finding
