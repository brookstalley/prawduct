---
artifact: build-plan
version: 2
scope: post-cumulative-pr-coverage
branch: feature/post-cumulative-pr-coverage
depends_on:
  - artifact: nonfunctional-requirements
  - artifact: data-model
  - artifact: architecture
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0, cost = unit-cost × run-count → conforms: this cuts run-count at the boundary, where 100 of 106 3.6-era verify rounds ran"
      - "the two boundary reviews run in parallel → conforms: dispatch stays concurrent; only what a PR re-review covers changes"
      - "proportionality ratchets both ways; a control names its yield and emits it observably → conforms: review-stats counts pr-review coverage extensions and PR delta blocking findings, so the trade can be measured and reversed"
      - "state-file growth is advisory → inapplicable, because no state file's size changes"
      - "review rigor is stage-keyed; the PR review is boundary-stage and runs the full table → ruling needed, recorded as a decision below: the PR reviewer gains an inner-set (ships-broken) duty on the post-cumulative fix delta while keeping its release-readiness goals over the bundle. The Critic still owns code soundness for everything the cumulative saw"
  - artifact: data-model
    dispositions:
      - "verdicts come from code-written facts, no model in a fact's write path → conforms: the pr-review fact is minted by code at ledger-append from the validated evidence file, as critic-consolidate mints review facts from partials"
      - "facts are immutable and append-only → conforms"
      - "derived views are never authoritative → conforms: .prawduct/.pr-reviews/*.json becomes the reviewer's input to the minting step; no gate reads it for coverage"
      - "a governance document reaches a terminal state → inapplicable, because no document lifecycle changes"
      - "backlog titles conform to the issue standard → inapplicable, because no backlog write path changes"
      - "a fact from a newer schema is a loud block → conforms: the new kind is added to the known set, and older readers already refuse unknown kinds loudly"
      - "two stores, two lifetimes → conforms: the fact goes to the shared evidence store; the per-worktree ledger keeps its review.pr event"
      - "backlog_service_repo selects the authoritative store → inapplicable"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms: the PR reviewer still writes only its evidence file; the fact is minted by the builder's ledger-append"
      - "authority fails closed, advice fails soft → conforms: a pr-review fact whose tree cannot be verified against the dispatch mark mints nothing, and any unreadable input leaves the gate uncovered"
      - "local-first, no network → conforms"
      - "the plugin writes nothing outside its own state → conforms"
      - "written in Python, never Python-specific → inapplicable, because no language-dispatched check changes"
      - "guides and reviews, never implements → conforms"
      - "goals and verification bind, method is advice → conforms: Success binds, Deliverables are guesses"
      - "every fact has one home → conforms: the extension predicate lives in coverage_algebra and every surface asks it, the lesson of the interval-extension build"
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning; persisted data schema-versioned → conforms: a new fact kind in the evidence store is a minor-release change, recorded in the change-log"
      - "exit codes are the contract → conforms: no exit code is repurposed"
      - "additive-first evolution → conforms: new fact kind, new payload section, new --json keys only"
partition: serial — every chunk after 01 composes over the fact 01 mints, and 03-04 share the gate modules
last_validated: 2026-09-24
---

# Build plan — after the cumulative, the PR re-review covers a non-blocking fix

## Requirements Confidence

**Level:** Medium. The owner chose this design on 2026-09-24 ("PR re-review covers it", then "Full
design" once it was sized at about four chunks). The mechanics below are inferred.

**Problem:** of the 106 3.6-era `verify-resolutions` rounds whose scope had a prior review, 100
followed a `cumulative` and 66 followed a review with no BLOCKING finding. At that point the PR
reviewer already ran beside the cumulative (`/prawduct:pr` Step 2), and any judgeable fix after it
triggers a PR re-review anyway (Step 4, Update Flow). So each post-cumulative fix pays for two
reviews: a Critic verify pass and a PR re-review. 43 of those rounds followed a review that had
said "THE REVIEW IS OVER", and found 4 findings between them. The precedent,
`documentation/issues/167-interval-extension-design.md`, deliberately left this population alone,
the "87 of 150 rounds that are the last coverage before a PR".

**What must not be lost:** that same design measured that 17 of 150 non-required verify rounds
found a blocker, most likely one the fix introduced. The PR re-review's check of the fix delta is
what replaces them, so it has to look for exactly that.

**Success:**
1. After a `cumulative` whose chain holds no open blocker, a committed judgeable fix plus a PR
   re-review make `check-cumulative-critic` pass. No Critic `verify-resolutions` runs.
2. The PR review's evidence becomes a code-written `pr-review` fact in the shared evidence store
   (#748, the fact route). Its tree is `commit_reviewed^{tree}`, checked against the code-written
   dispatch mark. A mismatch mints nothing and says why.
3. A `pr-review` fact extends coverage only from a tree covered by a chain that holds a
   `cumulative` and no open blocker, and only over the fix delta its payload named. It never
   originates coverage from the merge-base and never substitutes for the Critic.
4. The PR reviewer checks that fix delta against the inner BLOCKING set (ships-broken). A BLOCKING
   finding there gates like any blocker. Its non-blocking findings on the delta are recorded and
   never presented as work to do, so the loop cannot move from the Critic to the PR reviewer.
5. Fixes to a BLOCKING finding still need `verify-resolutions`. That is unchanged.
6. An uncommitted post-cumulative fix with no open blocker gets an advisory at Stop ("rides the PR
   re-review"), not a block.
7. No surface recommends a post-cumulative verify pass when the chain has no open blocker: mode
   inference, NEXT-ACTION, `cost-of-commit`, the gate's remedy text and the skills. An explicit
   `/prawduct:critic verify-resolutions` still runs if asked.
8. `review-stats` reports how often a `pr-review` fact extended coverage and how many blockers the
   delta check found, so the 17-in-150 catch rate can be compared.

**Out of scope:**
- Repeat cumulatives (`docs/bounded-cumulative-design`, #672).
- Pre-cumulative rounds (the interval extension already covers them).
- The PR reviewer's learnings exposure (#888).
- Changing what the PR reviewer checks over the whole bundle.

**Open assumptions:**
- `[ASSUMPTION: the fact is minted inside ledger-append's review.pr path, which already validates the evidence and consumes the dispatch mark | MED | user can correct]`
- `[ASSUMPTION: the fix delta is from the newest cumulative's head tree on the chain to HEAD^{tree}, computed by code into the PR payload, never by the reviewer | HIGH — it decides what the delta check sees | user can correct]`
- `[ASSUMPTION: a PR-delta BLOCKING finding clears when a later review covering its fix records a resolution — a PR re-review or a Critic verify pass, whichever the builder runs; the builder designs the resolution path against the node-blocker algebra (CRT-5H2D) | HIGH | user can correct]`
- `[ASSUMPTION: the PR reviewer's delta check is read-only (it cannot run tests), and the declared suite at the boundary is what catches failures the reading misses | MED | user can override]`

**What would raise confidence:** Chunk 01's fact on a real PR review in this repo, and an
enumeration (by grep) of every `review_edges` consumer before Chunk 03 widens the edge set.
Learnings on this: "Surveying a shared thing takes TWO searches", and "a reader guard added … its
consumers".

`[DECISION: the PR reviewer owns ships-broken on the post-cumulative fix delta | the stage-keyed norm assigns the PR review boundary rigor over the bundle; this adds an inner-set duty on a narrow delta the Critic never saw, keeping the norm's point — someone independent reads every shipped line at the rigor its stage owes — at one review instead of two. Recorded under the norm in Chunk 05 | user can veto]`

## Status

- [ ] Chunk 01: The PR review becomes a code-written fact
- [ ] Chunk 02: The PR reviewer checks the fix delta for ships-broken
- [ ] Chunk 03: Coverage composes over the pr-review fact, restricted
- [ ] Chunk 04: Every surface stops pricing a post-cumulative verify pass
- [ ] Chunk 05: Flow and prose — one review per post-cumulative fix
Context: Plan written 2026-09-24 in the learnings session and committed on this branch in its own
worktree (`../wt-prawduct-post-cumulative`), so that a session launched here owns this stream's
gates. Nothing built yet. Next: Chunk 01, after reading `/prawduct:methodology building`.

## Build Chunks

### Chunk 01: The PR review becomes a code-written fact

- **Description:** Implement #748's fact route. `ledger-append` on a `review.pr` event already
  validates the evidence file and consumes the dispatch mark. It now also mints a `pr-review`
  fact in `evidence.jsonl`:
  - the reviewed tree (from `commit_reviewed`, verified against the mark's `head`), head commit,
    base, branch and findings;
  - a `delta` block when the payload carried one (Chunk 02 fills it);
  - `dispatched_at`.
  Add `pr-review` to `evidence.KNOWN_KINDS`. It is not a verdict input yet: this chunk ships
  nothing that changes a gate. Fix the stale `KNOWN_KINDS` list in `pr/SKILL.md` Merge Flow step 8.
- **Depends on:** none
- **Deliverables:** `plugin/lib/ledger.py`, `plugin/lib/evidence.py`, `plugin/lib/review_dispatch.py`
  (if the mark check needs it), `.prawduct/artifacts/data-model.md` (the fact body: its consumers'
  queries first — Chunk 03's edge, Chunk 04's surfaces, `review-stats` — per the persisted-format
  rule).
- **Tests:**
  - Minted on a valid append.
  - Not minted, and named, on a mark/tree mismatch, a missing mark or malformed evidence.
  - Idempotent on re-append.
  - Old readers refuse loudly.
  - `evidence list` shows it.
  - Port the relevant cases from `tests/test_governance_ledger.py` `TestLedgerAppendReviewPr`.
- **Acceptance criteria:** a real PR review in this repo produces a fact whose tree equals the
  dispatched HEAD's tree.
- **Done when:**
  1. Acceptance criteria met and the affected test files pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: The PR reviewer checks the fix delta for ships-broken

- **Description:**
  - **Payload.** `lib/pr_payload.py` gains a fix-delta section when the chain holds a `cumulative`
    whose head tree differs from HEAD's: base tree, file list, and the exact diff command.
  - **Protocol.** `skills/pr/review-protocol.md` gains the delta goal. It checks only the inner
    BLOCKING set (the NFR norm's list, cited rather than restated). Any finding on the delta
    carries `delta: true`, and only BLOCKING ones are actionable. The "do not re-derive code
    soundness" sentence is scoped to the bundle, not deleted.
  - **Agent.** `agents/pr-reviewer.md` gets the same instructions.
  - **Evidence.** The schema carries the delta block, and Chunk 01's minting copies it.
- **Depends on:** Chunk 01
- **Deliverables:** `plugin/lib/pr_payload.py`, `plugin/skills/pr/review-protocol.md`,
  `plugin/agents/pr-reviewer.md`, `plugin/lib/ledger.py` (the evidence validator), the reviewer
  payload budget test.
- **Tests:**
  - Payload delta present, absent, and absent on an unreadable chain (fail closed: no delta means
    no extension later).
  - The protocol pins, and the existing `test_protocol_scopes_off_code_soundness_without_claiming_a_verdict`
    and `test_findings_carry_their_cost…` renegotiated in the open.
- **Acceptance criteria:** a PR review dispatched after a cumulative plus a fix commit records a
  delta block naming exactly the fix's files.
- **Done when:**
  1. Acceptance criteria met and the affected test files pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: Coverage composes over the pr-review fact, restricted

- **Description:** `coverage_algebra` admits `pr-review` as a verdict input, with a conditional
  edge. The edge runs from the fact's delta base tree to its head tree, and exists only when both
  of these hold:
  - the delta base tree is reached by a chain holding a `cumulative` with no open blocker;
  - every judgeable file in the delta is in the fact's delta file list.
  Delta BLOCKING findings sit on the head node like any review's.
  - Before editing, enumerate every reader of review facts and edges by grep:
    `_verify_anchor_id`, `review_chain`, `_newest_branch_review`, `diagnose_fix_churn`, transfer
    candidates, `count_branch_rounds`, `covered_frontier`, the round budget. Decide for each
    whether a `pr-review` fact is visible to it, and write the decision in its docstring. Most
    should not see it.
  - Blocker resolution per the open assumption.
- **Depends on:** Chunk 02
- **Deliverables:** `plugin/lib/coverage_algebra.py`, `plugin/lib/gates.py`
  (`_branch_coverage`, `branch_coverage_verdict`, the session verdict), and the readers the
  enumeration names.
- **Tests:**
  - Covered after cumulative plus fix plus PR re-review.
  - Uncovered without the PR re-review.
  - Uncovered when the chain's cumulative left an open blocker.
  - Never an edge from the merge-base (a PR fact alone covers nothing).
  - A delta file outside the fact's list gives no edge.
  - A PR-delta BLOCKING finding blocks.
  - A second post-cumulative fix needs a second PR re-review.
  - Mutate each conjunct separately and watch its own test go red.
  - One scenario test on a real repo fixture.
- **Acceptance criteria:** Success 1, 3 and 5 at the gate.
- **Done when:**
  1. Acceptance criteria met and the affected test files pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: Every surface stops pricing a post-cumulative verify pass

- **Description:** One predicate — "the next PR re-review covers this" — owned by one function and
  asked by every surface. This is the interval-extension build's lesson: five carriers, one
  construction. Surfaces:
  - `critic_mode` rule 1b stops inferring `verify-resolutions` when the chain has no open blocker;
  - `cost_of_commit` answers `free — rides the PR re-review`;
  - the `cmd_stop` Critic gate gets an advisory arm for an uncommitted fix (Success 6);
  - `critic_consolidate` NEXT-ACTION: `_IF_YOU_FIX_SOME`, `_BATCH_FIX_DIRECTIVE`, `cost_lead` and
    the clean-close arms after a cumulative;
  - the gate's `uncovered` remedy, and the `diagnose_fix_churn` note, which names the PR re-review;
  - `review-stats` counts (Success 8).
- **Depends on:** Chunk 03
- **Deliverables:** `plugin/lib/critic_mode.py`, `plugin/lib/coverage.py`, `plugin/lib/critic_consolidate.py`,
  `plugin/lib/gates.py`, `plugin/bin/prawduct-hook`, `plugin/lib/telemetry.py`.
- **Tests:**
  - Each surface's post-cumulative, no-blocker arm.
  - Each surface still names verify-resolutions when a blocker is open.
  - The retired strings pinned absent in the no-blocker arm: `tests/preferences/test_free_interval_prose.py`
    pins "ONLY if that commit touched judgeable files" — renegotiate.
  - `review-stats` counts.
- **Acceptance criteria:** Success 6–8.
- **Done when:**
  1. Acceptance criteria met and the affected test files pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 05: Flow and prose — one review per post-cumulative fix

- **Description:**
  - **Rewrite `/prawduct:pr`.** Step 2's "for any fix AFTER the cumulative: fix, then
    verify-resolutions" becomes: fix, commit, re-run the PR reviewer, and the gate passes on its
    fact. The Step 2 → Step 4 ordering changes accordingly: the gate passes after the re-review, not
    before Step 4. Update Step 4 and the Update Flow.
  - **Update the other carriers.** `skills/critic/review-cycle.md` (each place stating the old
    route), `skills/critic/SKILL.md`, `skills/pr/review-protocol.md`'s cost paragraph and
    relationship table, and `methodology/building.md` "Resolve findings".
  - **Record the decision and contract.** The `[DECISION]` goes under the NFR stage-keyed norm.
    `api-contract.md` gets the fact kind. `plugin/CHANGELOG.md` and the change-log entry get the
    consumer-visible change.
  - **Enumerate before editing.** Find carriers by two vocabularies ("after the cumulative",
    "verify-resolutions" beside "fix") and grep each file you edit first. Pin every carrier plus
    the retired wording's absence in one test.
- **Depends on:** Chunk 04
- **Type:** cumulative-final
- **Deliverables:** the files named, `tests/test_v5_methodology.py` and `tests/test_reviewer_payload_budget.py`
  (re-measure, ratchet), and a new carrier test.
- **Tests:** the carrier pin; the declared suite (boundary).
- **Acceptance criteria:** Success 7 in prose; this branch's own PR is the first to land through
  the new flow. Dogfood it: fix a cumulative warning, re-run the PR reviewer, and watch the gate
  pass with no verify pass.
- **Done when:**
  1. Acceptance criteria met and the declared suite passes
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its review. PR after Chunk 05, when the owner asks.

- After Chunk 01: the fact's body is a persisted format. Confirm its fields answer Chunk 03–04's
  queries before building on it.
- After Chunk 03: owner look at the restriction. It is the only thing standing between a PR review
  and Critic-free coverage.
- Chunk 05: the dogfood run is the acceptance.
