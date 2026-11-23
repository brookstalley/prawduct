---
artifact: build-plan
version: 2
scope: chunk-plan-order
branch: fix/chunk-plan-order
base: develop
working-branches: []
partition: "serial — chunks 01 to 04 all edit plugin/lib/plan_status.py and 02 to 04 the prawduct-hook CLI; 05 is disjoint but small, and a delegate's integration debt would cost more than it saves"
governed_by:
  - artifact: data-model
    dispositions:
      - "verdicts computed from facts, no model in the write path → conforms; chunk state is still computed from facts, and the new `chunks_declared` and `chunks_evidence` keys are written at dispatch by code"
      - "facts immutable and append-only → conforms; `plan retract --all` (D7) writes new `chunk-retracted` facts, and nothing rewrites a ledger already in the bad state (D11)"
      - "derived views never authoritative → conforms; the route text (D5) and `ahead_of` (D6) are rendered advice that no gate reads"
      - "a governance document reaches a terminal state → inapplicable because this work archives or deletes no document other than its own plan at the end"
      - "backlog issues conform to the title rules → inapplicable because no backlog write path changes; D10 changes only the version label value"
      - "a newer-schema fact is surfaced, never dropped → conforms; the two new keys are optional and typed by the validator as `chunks_proposed` is; chunk 02 confirms whether SCHEMA_VERSION must move and records the answer"
      - "two stores, two lifetimes → conforms; the fact keys and chunk 02's `guard-refusal` fact go to the shared evidence store, the sink `evidence.append_guard_refusal` names for every pre-dispatch refusal"
      - "backlog_service_repo selects the authoritative store → inapplicable because no backlog read changes"
      - "D1 (chunk state from facts; spans credit by subject only; the #1199 departure) → conforms; owner ruling 2026-11-22 confirmed the design's reading, so D1 and its departure stand unamended"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; persisted data schema-versioned → conforms; everything is additive (a new exit code, flag and JSON key), so this is a patch under the conservative-versioning preference"
      - "exit codes are the contract → conforms; exit 8 `chunks-ambiguous` is new, takes a code that is free (5 is withdrawn), and is documented in the sentinel list and the skill's exit table"
      - "additive-first evolution → conforms; `plan retract --all`, the `ahead_of` JSON key and exit 8 are additions, and `propose_chunks` keeps its signature"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall clock is P0 → conforms; the refusal costs one re-run of `critic-begin` before any reviewer starts, D5 and D6 render with no git (1198-NF1), and D4's deferral reads a field from the pass it already makes"
      - "proportionality ratchets both ways: a new control names its yield and emits it → conforms, by a plan-time addition to the design. D3's refusal is a new control. Expected yield: rare. The store scan found 4 of 180 facts naming out of order, and each refusal is one wrong certification that does not happen. It records one `guard-refusal` fact (guard `critic-dispatch-chunks-ambiguous`), the class's one sink, read by `prawduct-hook evidence list --kind guard-refusal`. D6's flag is not a control, because it gates nothing and `plan status --json` re-derives it"
      - "state-file growth is an advisory → inapplicable because no state file grows beyond one `guard-refusal` fact per refusal"
      - "review rigor is stage-keyed → inapplicable because the blocking sets do not change"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable because no reviewer-side write path changes"
      - "authority fails closed; advice fails soft → conforms; the refusal (D3) and plan order (D1) fail closed and name a remedy; the route text and the flag are advice"
      - "local-first → conforms; no network"
      - "the plugin writes only its own state → conforms"
      - "written in Python, never specific to Python → conforms; nothing dispatches by language"
      - "guides and reviews, never implements → conforms"
      - "goals and verification bind, method is advice → conforms; departures from the design's method are recorded under Decisions made mid-build"
      - "every fact has one home → conforms; plan order lives in `_deliverable_chunks`' certifying branch, and D3, D4, D6 and D8 read its answer rather than recompute it"
depends_on:
  - documentation/issues/1141-1198-design.md
  - documentation/issues/1141-requirements.md
  - documentation/issues/1198-requirements.md
last_validated: 2026-11-22
---

# Build plan: no chunk certified while an earlier one is open (#1141, #1198)

## Goals

**Response taken:** Proceed, citing it. The design `documentation/issues/1141-1198-design.md` states the goals, success criteria and scope-outs. The owner's rulings of 2026-11-22 settle its two open questions (`.prawduct/owner-rulings.md`), and the owner approved this as the next build that day.

**Product:** A chunk's `done` must mean that a review covered that chunk's work. Two reported cases broke this. In #1141, a review named a later chunk because its diff touched that chunk's path. In #1198, a part-merged plan's cumulative-final chunk read done. In both, a builder reading `plan status` trusts a certification that no review earned. The work makes the proposal honest (D1, D3), makes every `done` row say how it became done (D5, D6), and gives the remedy one command (D7).

**Architecture:** Plan order lives in the one predicate that already rations path credit (`_deliverable_chunks`, certifying branch). Every other surface reads its answer. Facts are read exactly as before, and nothing rewrites history (D11). What must stay possible is delegated plans building out of order: words still certify out of order, and paths do not (D2).

**Constraints:** Additive CLI evolution only (api-contract). No migration of ledgers already in the bad state (D11; data-model append-only). The Stop-path cost does not grow (1198-NF1).

**Tradeoffs accepted:**
- Adjacent path credit in whole-plan modes stays open (design Risks, first bullet). D5 makes it diagnosable. Revisit if a `plan status` route line shows a wrong adjacent certification in practice.
- A delegated chunk with unscoped subjects, reviewed before an earlier chunk lands, stays open until it is named. It fails closed, and the dispatch note names `--chunks`.

**Inferred (not in the design):** D3's refusal records its firing, because the proportionality norm requires a new control to emit its yield, and the design names neither the yield nor an emission. It is one `guard-refusal` fact carrying the review mode, the proposed ids, the plan scope and the branch, and no paths. *Corrected in Chunk 02:* the plan first said a governance-ledger event. `evidence.append_guard_refusal`'s docstring records the #596 ruling that every pre-dispatch refusal has this one sink, and that a ledger route is what that ruling forbids.

**Decisions made mid-build:**
- Chunk 01: tests (f) and (g) live in `tests/test_review_interval_extension.py`, not `test_critic_mode_inference.py`, because that file's fixture builds plans with Deliverables paths (settled by: match the product's choices). (g) is green on develop as well: it pins mutant M5, as the design says. (f) went red on develop only once its shared path existed at review time. Before that, a missing-Deliverable finding kept chunk 1 open and the test never reached the deferral.
- Chunk 01: beyond the design's six fixtures, six tests in `tests/test_critic_consolidate.py` (`_st8_repo` and the stub-dispatch control) proposed 03 or 04 with an earlier chunk open. They were renegotiated in the open: the ST8 work now touches the adjacent 01 and 02, and the stub-dispatch control asserts the withheld note. Each docstring says why.
- Chunk 02: the refusal is recorded as a `guard-refusal` fact, not a ledger event (the #596 one-sink ruling; Goals). The SKILL.md exit-8 row is a declared raise of +22 tokens, net of cutting step 4's restated proposal definition for a pointer to `planning.md`. The two ST8 tests that dispatched `chunk` with two chunks proposed (`test_omitted_flags_declare_the_proposal`, `test_no_declared_chunks_grades_the_whole_proposal`) now dispatch `final`: they pin default naming, which every whole-plan mode shares.
- Chunk 02: `evidence.SCHEMA_VERSION` stays 1. `chunks_declared` and `chunks_evidence` are optional review-body keys, as `chunks_proposed` was when it was added under schema 1. An older reader ignores them, and a fact without them renders "route not recorded". So no reader can misread a fact, and the schema-ahead block has nothing to guard.
- Chunk 03: D8's clause is silent for the one chunk the newest review named, and for one the builder named with `--chunks`. It speaks for a chunk a several-chunk proposal named. The design's control (h), a fix to the reviewed chunk printing nothing, and its 1141 sequence (i), a clause for the 04 that same review named, conflict if every named chunk is excluded, and the route is what tells them apart. *Not settled by the design; inferred.* *Revised in Chunk 07:* the deferral fired on this branch's own integration commit and questioned chunk 01, which `--chunks 01` had named. So the exclusion now covers any chunk certified by the builder's words (`--chunks`, or a span's scoped subject), not only one the newest review named. The rule is: only the code's own naming (a proposal, or a route that predates the record) is questioned. That case is pinned by `test_a_later_chunk_editing_a_chunk_the_builder_named_says_nothing`, which is red under the first rule.
- Chunk 03: `_route` reads a fact with `chunks` but no `chunks_proposed` as "route not recorded". The first draft read the missing key as an empty proposal and claimed `--chunks`, and `test_plan_hook_cmd.py`'s fixture caught it. The by-span `ahead_of` test lives in `test_critic_consolidate.py`, where a real consolidation writes the spanning edge.
- Chunk 03, verification: `prawduct-hook plan status .prawduct/artifacts/archive/build-plan-backlog-roi-2026-11-18.md` (2026-11-23) prints, under chunk 11, "named; whether by --chunks or the proposal is not recorded (fact predates #1141)" and "done ahead of open chunk 02 — if chunk 11's work is not built, `prawduct-hook plan retract 11 --all --reason …`". That is D6's first wording, as predicted.
- Chunk 04: test (q), the span half, lives in `test_critic_consolidate.py`, beside the by-span `ahead_of` test, because only a real consolidation writes a spanning edge. (r) to (t) are in `test_plan_retract.py`. The single-fact path now writes through the same `write()` as `--all`, so the CLI has one append-and-note owner. Mutant M8 seen red.
- Chunk 05: `evidence list` showed no fact body, so the narrowest read is `--id <fact>` plus `--json`. The build is `evidence.read_plugin_build`'s answer (#1086), the reader every fact's `actor.build` comes from. It refuses an unrelated enclosing repository's commit, and it marks uncommitted plugin changes `+dirty`. Two drafts went wrong first. One shelled out from `lib/backlog/upstream.py`, which the whole-tree egress and codec guards refused. The other was a second reader, `gitstate.work_tree_commit`, which the chunk 05 review refused: it borrowed a home repository's commit and missed `+dirty`. Retrieval before generation; it was deleted.
- Chunk 06: D9's falsifying query, widened to every prose description of the proposal under `plugin/methodology`, `plugin/skills`, `plugin/docs`, `plugin/templates` and `documentation/`, returns no stale hit. Shipped history (`plugin/CHANGELOG.md`, released plans) is left as written. `planning.md` grows +150, a declared reading: drafted at +260 and cut. The 1198-A4 end-to-end test is in `test_critic_consolidate.py::TestAPlanShippedInTwoParts`. It also carries chunk 05's O-1: the report-bug skill no longer says the chunk fields are only ids.
- Chunk 01: the change fragment is written now, not in 06, because `plan new`'s stub fails the live-fragment guard (`test_change_fragments.py`) once it is committed. 06 completes it.

**Level:** High. The design reproduced both bugs on develop, prototyped the rule against every fixture shape, and named the six fixtures it changes. Two items were read and not run: the Stop-path deferral (D4) and the `critic-begin` dispatch order. Chunks 01 and 02 run both first.

## Verification Strategy

Beyond the tests: after 01, run `plan status` and `prawduct-hook infer-critic-mode` on a scratch repo built with `tests/test_plan_status.py`'s helpers in 1198's six-chunk shape. After 02, run a real `critic-begin --mode chunk` over the adjacency shape and confirm exit 8 leaves nothing on disk. After 03, read `plan status` on this repo's live bad ledger (`build-plan-backlog-roi-2026-11-18.md`): chunk 11 should show D6's first wording.

## Build Chunks

### Chunk 01: Plan order in the proposal

- **Description:** D1 and D4. Withhold a chunk proposed by path alone while an earlier open chunk is left out. Keep chunks named by words. Give the Stop-path deferral the touched set, so withheld work is not deferred.
- **Depends on:** none
- **Artifacts consumed:** `documentation/issues/1141-1198-design.md` D1, D2, D4, Test plan
- **Deliverables:** `plugin/lib/plan_status.py` (`_deliverable_chunks` gains `kept_by_words`; `_PathAnswer.withheld`; `ChunkProposal.withheld`, `.touched` and `.evidence`; `chunk_proposal` runs the subject walk first, and each withheld chunk gets a note); `plugin/lib/critic_mode.py` (`extension_deferral_owed` reads `touched`); tests (a) to (g), (l) and (m), with mutants M1 to M5; the six renegotiated fixtures, each with its sibling assertion
- **Tests:** first, run the six non-`plan_status` files the design's Research names (`test_critic_consolidate.py`, `test_chunk_state_table.py`, `test_critic_mode_inference.py`, `test_plan_retract.py`, `test_bounded_cumulative.py`, `test_review_interval_extension.py`) against the change, and add every red one to the renegotiated list in the open
- **Acceptance criteria:** (a), (b) and (d) are red on develop and green after; (c) and (e) are green on both; each mutant turns its test red; the six fixtures are renegotiated with docstrings saying why
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed as `fix(chunk-plan-order): … (Chunk 01)`

### Chunk 02: Chunk-mode refusal and the recorded route

- **Description:** D3 and D5's recording half. A `chunk` dispatch whose proposal holds two chunks exits 8 before writing anything. The manifest and the fact record `chunks_declared` and `chunks_evidence`.
- **Depends on:** Chunk 01
- **Artifacts consumed:** design D3, D5; `.prawduct/artifacts/api-contract.md` "Special sentinels"
- **Deliverables:** `plugin/lib/critic_consolidate.py` (the refusal just after `_proposed_chunks` in `begin_review`; `chunks_declared` and `chunks_evidence` on the manifest, validator and `_fact_chunk_fields`; one `guard-refusal` fact per refusal, per the Goals inference); `plugin/bin/prawduct-hook` (the exit 8 mapping); `plugin/skills/critic/SKILL.md` (the exit table row for 8, and step 4's "Omit the flag" sentence); tests (j) with mutant M6, and (k); a test that the refusal appends one `guard-refusal` fact and writes nothing else
- **Acceptance criteria:** exit 8 with both re-run lines on stdout and no manifest, marker or archive; `--chunks 03` and `final` over the same diff still dispatch; the validator refuses a non-bool and a non-dict; the decision on SCHEMA_VERSION is recorded under Decisions made mid-build
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed as `… (Chunk 02)`

### Chunk 03: Legible rows and the flag

- **Description:** D5's rendering half, D6 and D8. Every review-done row says its route. A done row with an open chunk before it is flagged. The deferral message names a done chunk that the work touches.
- **Depends on:** Chunk 02
- **Artifacts consumed:** design D5 (the route table), D6, D8
- **Deliverables:** `plugin/lib/plan_status.py` (`ChunkState.ahead_of`, the route `reason`, `render_table`, and new `done_chunks_touched`); `plugin/bin/prawduct-hook` (`plan status --json` gains `ahead_of`); `plugin/lib/critic_mode.py` (the D8 clause); tests (h), (i) and (n) to (p), with mutant M7; the briefing and PR-payload assertions this churns, renegotiated in the open
- **Acceptance criteria:** one test per row of D5's table; (p) renders through `render_table`, the `/clear` handoff and `--json`; on this repo's backlog-roi plan, `plan status` shows D6's first wording under chunk 11
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed as `… (Chunk 03)`

### Chunk 04: `plan retract --all`

- **Description:** D7. Withdraw every certification of a chunk, spans included, in one command that converges when re-run.
- **Depends on:** Chunk 01
- **Artifacts consumed:** design D7
- **Deliverables:** `plugin/lib/plan_status.py` (`retraction_plan`); `plugin/bin/prawduct-hook` (`_cmd_plan_retract` `--all`, its help text, and the "or withdraw every certification" line); tests (q) to (t), with mutant M8
- **Acceptance criteria:** (q) writes three facts and ends `open`; `--all --fact` exits 2; a ticked box refuses before any write; a failed append partway exits 1, and the re-run converges
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed as `… (Chunk 04)`

### Chunk 05: Bug-report intake

- **Description:** D10. The report-bug skill asks for the affected row and the certifying fact's chunk fields. On a `-dev` build, the upstream version label carries the plugin tree's short commit id.
- **Depends on:** Chunk 03
- **Artifacts consumed:** design D10
- **Deliverables:** `plugin/skills/report-bug/SKILL.md`; `plugin/lib/backlog/upstream.py` (`version_label`); their tests. First confirm that `prawduct-hook evidence list` shows a fact's body, or add the narrowest read that does
- **Acceptance criteria:** a released version's label is unchanged; a `-dev` version in a git work tree gains the short id; the skill's ask names `plan status --json` and the five fact fields
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed as `… (Chunk 05)`

### Chunk 06: Methodology and descriptions

- **Description:** D9. Rewrite `planning.md` "Chunk state" and add the "A plan may ship in parts" Plan Shape bullet. Update every description of the proposal, then run D9's falsifying query clean.
- **Depends on:** Chunks 01 to 05
- **Artifacts consumed:** design D9 and its falsifying query
- **Deliverables:** `plugin/methodology/planning.md`; `.prawduct/artifacts/api-contract.md` (`critic-begin`, the sentinel list, `plan retract --all`, `ahead_of`); `.prawduct/artifacts/data-model.md` (descriptive entries only; D1's ruled clause is not edited); `plugin/skills/critic/review-cycle.md` (manifest keys); the docstrings D9 lists; the 1198-A4 end-to-end test with its squash control; the change fragment, which closes #1141 and #1198
- **Acceptance criteria:** D9's query, widened to the concept and not only its tokens (core: "a coverage claim holds only when its falsifying query returns nothing"), returns no stale hit; the budget tests move with a stated reason, and a trim lowers its ceiling
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed as `… (Chunk 06)`

### Chunk 07: Boundary review

- **Description:** Integration, one run of the declared suite, and the cumulative review over the branch.
- **Depends on:** Chunks 01 to 06
- **Deliverables:** suite green through `test-evidence record`; the boundary `cumulative`, paired with the native review (#1130)
- **Type:** cumulative-final
- **Done when:**
  1. Suite recorded green
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk, review per chunk (seven chunks, so this is not a short plan). The PR goes through `/prawduct:pr` when the owner asks.

- After chunk 01: confirm that D4's deferral behaves as read, by running `infer-critic-mode` on the fixture, before 02 builds the refusal on the proposal.
- After chunk 07: the whole bundle; check that the six renegotiated fixtures each still pin their own subject.
