---
artifact: build-plan
version: 2
scope: empty-verify-rounds
branch: fix/empty-verify-rounds
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 (unit-cost × run-count) → conforms: every chunk removes runs (A, B) or makes their yield measurable (C); no review, reviewer or mode is added"
      - "proportionality ratchets both ways; a new control names its yield → conforms: no control is added; B narrows what a verify pass may emit, and C makes the empty-round count honest so the ratchet reads true numbers"
      - "state-file growth is advisory only → inapplicable because no state file grows beyond one more resolution fact per confirmed observation fix"
      - "review rigor is stage-keyed; the inner stage blocks only on the inner BLOCKING set → conforms: nothing that blocks today stops blocking; B narrows only what the inner stage reports below BLOCKING"
  - artifact: data-model
    dispositions:
      - "verdicts come from the append-only fact ledger, no model in a fact's write path → conforms: observation resolutions are written by critic-consolidate from a validated partial, like finding resolutions"
      - "facts are immutable and append-only → conforms: a confirmed observation fix is a new resolution fact"
      - "derived views are never authoritative → conforms: no gate reads an observation resolution; coverage_algebra keys on fid and ignores them"
      - "a fact from a newer schema is a loud block → conforms: an observation resolution reuses the existing `fid` slot with an `O-n` id, so an older reader's resolution index skips it rather than misreading it; no schema bump"
      - "a governance document reaches a terminal state, never deleted → inapplicable because no document's lifecycle is touched"
      - "backlog issue titles conform to the issue standard → inapplicable because nothing is written to the backlog store"
      - "two stores, two lifetimes: shared answers vs per-clone nags → inapplicable because no answer or nag is added"
      - "backlog_service_repo selects the authoritative backlog → inapplicable because no backlog reader is touched"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session → inapplicable because no reviewer gains a write"
      - "authority fails closed; advice fails soft → conforms: every new deferral predicate answers 'no deferral' on any read failure (the Stop gate stays in force), and an off-topic verify observation is dropped from the record with a printed note rather than refusing the consolidation"
      - "local-first, no third-party deps → conforms: stdlib only"
      - "writes nothing into a governed repo but its own state → conforms"
      - "never specific to Python → conforms: nothing reads product files"
      - "guides and reviews, never implements → inapplicable because no product code is touched"
      - "goals and verification bind; method is advice → conforms"
      - "every fact has one home → conforms: 'a later review is owed' gets one owner in critic_mode, read by inference, the Stop gate and the close directive"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; evidence store independently versioned → conforms: the evidence-store change is additive"
      - "exit codes are the contract → conforms: no exit code changes; `deferred` is an existing inference answer"
      - "additive-first evolution → conforms: an `O-n` id in a resolution's existing `fid` slot, and `about` on an observation, are additive"
partition: serial — 01 and 02 both edit critic_consolidate.py, and 03 reuses 02's target validation
last_validated: 2026-10-13
---

# Build Plan: Stop buying verify rounds that have nothing to verify

## Goals

**Response taken:** Ask, in one batch. The owner answered on 2026-10-13: "yes ABC as one plan". That
followed the sibling-repo audit and the investigation that diagnosed three causes (A, B, C below).

**Product.** In sibling repos on 3.7.x, 20–24% of `verify-resolutions` rounds had no open blocking
or warning finding to verify, against about 5% before. 28 of the 32 such rounds followed a clean
review that raised only notes or observations. Each costs a review round (about 1.5–2.5 min,
self-reported) plus a builder turn. The owner called it a significant tax. Success means a builder
stops being told, or allowed, to buy those rounds, and the empty-round metric counts only rounds
that truly verified nothing. Re-derive the population with the cohort scripts described in
`.prawduct/.handoff-notes.md` (evidence stores of discodon, samsung-frame-art-loader, fabulous and
puzzles; verify rounds whose scope had no open blocking or warning finding at dispatch).

**The three causes, and the chunk that answers each:**
- **A, Chunk 01.** About 7 rounds were redundant. On `Type: cumulative-final` plans the builder ran
  `final` (inferred, because the last chunk was uncommitted), then a verify over observation fixes,
  then the `cumulative` the plan owed anyway. All four inspected plans (fabulous ×3, puzzles) were
  `cumulative-final`. Two things don't know a boundary review is still owed:
  - `critic_consolidate._plan_owes_a_later_review` only counts 2+ unticked chunks;
  - inference rule 3 ignores the chunk's `Type:`.
- **B, Chunk 03.** About 10 rounds were a treadmill. A verify pass raises observations about its own
  fix delta (around 3 per pass), the builder fixes them, and that buys another verify. In 3.7.x,
  verify-round observations were accepted 273 times and recorded as fixed 4 times.
- **C, Chunk 02.** Observations have no resolution path. A verify pass that confirms an observation
  fix cannot record it (`_RESOLUTION_DISPOSITIONS` targets `fid` only). Such rounds count as empty,
  and the fix is recorded as accepted or undispositioned.

**Architecture.**
- "A later review is owed" gets one owner in `lib/critic_mode.py`. Three surfaces read it:
  inference, the Stop gate's extension deferral, and the close directive's `rides_next_review`.
  Today each derives it from `later_review_owed(progress)` alone.
- Observation resolutions reuse the existing resolution fact, with the `O-n` id in `fid`. Gates never
  read them: `coverage_algebra.resolution_index` keys on `fid`.

**Constraints.**
- Nothing that blocks today stops blocking.
- No new review mode, reviewer or gate.
- An off-topic verify observation is advice, so it fails soft: it is dropped from the fact with a
  printed note, and the consolidation is not refused.

**Inferred decisions (for the boundary):**
- *Inferred, beyond the owner's literal A:* inference on the last chunk of a `cumulative-final`
  plan, with that chunk uncommitted, answers `deferred` ("commit, then `/prawduct:critic`, which
  infers the cumulative"). It no longer answers `final`.
  - Same root as A: the machinery doesn't know a cumulative is owed.
  - The documented flow already says "Don't run a separate `final` first" (`review-cycle.md`,
    planning.md `cumulative-final`). Inference was the one surface contradicting it.
  - The inferred `final` (4–10 min) is a larger cost than the verify it led to.
  - An explicit `/prawduct:critic final` still runs.
- *Inferred:* a short plan's last chunk also owes its boundary `cumulative`, so the same predicate
  covers it. This is the plan shape `short_plan_deferral` already names.
- *Inferred:* B's scoping is mechanical, not prose-only. In `verify-resolutions`, an observation
  must carry `about: {review_id, fid}` (an `R-n` or `O-n` id) naming an existing prior finding or observation whose fix
  it is about. One without it is dropped from the fact (counted in the consolidation output). The
  reviewer prompt says to report only those. Prose alone is the weak form (core rule on mechanising
  rules recall misses).

**Decisions made mid-build:**
- Chunk 01: on a clean, committed tree, the boundary arm must not defer. There the owed
  `cumulative` is the review to run now, not one to defer to. A new test caught the first draft
  inferring `deferred` instead of `cumulative` after the commit. So `extension_deferral_owed`
  returns the kind, and rule 2 defers only on a later-chunk kind. Settled by the plan's own goal:
  the boundary review still runs exactly once.
- Chunk 01: the clean-verify cost lead's "the next edit after it, judgeable or not, needs its own
  verify" is left alone. It was a deliberate wording (#851, pinned by a test), and none of the 32
  measured rounds was a non-judgeable edit, so it is not a cause here. *Not settled by the goals.*
  Flagged for the boundary review as a claim worth re-checking against the free-edge rule.
- Chunk 01 review (rev-20261013T161914Z-bf769839): one blocking finding, the short-plan arm was
  untested, now pinned. Its O-2 was fixed too: rule 3 now asks `review_owed_after` over the newest
  review's chain, so it stops deferring once the cumulative has run. That observation fix has no way
  onto the record until Chunk 02 lands, which is cause C in miniature.
- Chunk 02: an observation resolution names the `O-n` id in the existing `finding.fid` slot, not a
  new `oid` key as this plan first said. Dispositions already store an observation there, and `R-n`
  and `O-n` never collide. So every reader keeps working, an older plugin misreads nothing, and
  there is no new key to version. Gates are unaffected because they filter blocking findings, which
  carry `R-n`. The verify dispatch needed no change: `.critic-findings.json` already lists the prior
  review's observations with their ids. Settled by "every fact has one home" and additive-first
  evolution.
- Chunk 03: the verify dispatch directive was the treadmill's source. It explicitly invited
  observations about "a name you would have chosen differently, prose that could be tighter, a test
  you would have structured another way". That list is replaced by "only one that judges a NAMED
  fix", and the sentence "the builder still reads your observations and can act on them", which the
  scoping made false, is cut (net +2 tokens, declared on its pin).
- Chunk 03: `SKILL.md`'s per-mode summary and `review-protocol.md`'s schema line still describe
  observations without the verify-only `about` rule. Both stay true at the level they speak, and
  the verify dispatch directive states the rule at the moment the reviewer acts. They are not edited
  because both sit at pinned budgets. *Not settled by the goals*; flagged for the boundary review.
- Chunk 03 is declared `Type: cumulative-final`, dogfooding Chunk 01: commit, then one `cumulative`
  that is both its review and the plan's boundary review, instead of final → verify → cumulative.

**Level:** Medium. The causes are measured, but the rates come from about 32 rounds in four repos.
What would raise it: re-running the cohort scripts two weeks after release, to confirm the share of
verify rounds with nothing open falls back toward the pre-3.7 ~5%.

## Status

- [x] Chunk 01: an owed boundary review counts as a later review (A)
- [x] Chunk 02: a verify pass can confirm an observation fix (C)
- [ ] Chunk 03: a verify pass reports observations only about the fixes it verifies (B)
Context: Chunks 01 and 02 are built, reviewed and committed. Chunk 03 is built and red-verified (two mutations, each caught). It will be committed, then reviewed by one `cumulative`, which is also the plan's boundary review; its box is ticked after that passes.

## Verification Strategy

Each chunk is verified by unit tests over fact lists and plan fixtures, as the neighbouring tests do
(`tests/` for `critic_mode`, `critic_consolidate`, `dispositions`, `stats`). Beyond tests:
- Chunk 01: run `infer-critic-mode` and a dry consolidation close against a fixture repo holding a
  `cumulative-final` plan.
- Chunk 02: re-run `stats` on a sibling store copy and confirm the verify rounds behind an
  observation fix are no longer counted empty.
- Chunk 03: read the rendered dispatch directive for a `verify-resolutions` round.

## Chunk 01: an owed boundary review counts as a later review (A)

**Type:** code

**Delivers.**
- A single predicate in `plugin/lib/critic_mode.py` answering why a review is still owed on this
  branch after the newest one, or `None`. It is owed when either holds:
  - 2+ unticked chunks (today's `later_review_owed`); or
  - the plan's boundary review is a `cumulative` (the last unticked chunk declares
    `Type: cumulative-final`, or `short_plan_deferral` defers) and no `cumulative` is on the review
    chain yet.

  It fails closed (`None`) on any read failure.
- `extension_deferral` uses it, so the Stop gate defers a non-blocking fix after a `final` on a
  `cumulative-final` plan, naming the cumulative.
- `critic_consolidate._plan_owes_a_later_review` uses it.
  - The `_RIDES_NEXT_REVIEW_LEAD` text names which review will carry the fix: the next chunk's
    review, or the plan's boundary cumulative.
  - It never claims a chunk review that isn't coming.
- Inference: on the last unticked chunk of a `cumulative-final` plan with uncommitted code, rule 3
  answers `deferred` while that boundary `cumulative` has not yet run. Rule 4, which handles a
  record-only diff, is unchanged. The rationale is to commit, then run `/prawduct:critic` for the
  cumulative. An explicit `final` still runs.
- The Stop gate's block message for an uncovered `cumulative-final` last chunk names
  "commit, then `/prawduct:critic`" (as the short-plan `last_chunk_note` does), so the gate and
  inference agree.
- Prose that describes the old sequencing is updated: `review-cycle.md` (the `cumulative-final`
  paragraph saying inference infers `final` mid-chunk), and `planning.md` if it restates it.

**Done when:**
1. Tests pin each arm of the predicate: later chunks; `cumulative-final` with no cumulative;
   `cumulative-final` after a cumulative (not owed); short plan's last chunk; unreadable plan (fails
   closed).
2. Tests pin the close lead's two variants and the inference answer on a `cumulative-final` last
   chunk, both uncommitted and committed (committed still answers `cumulative`).
3. The Stop gate message test covers the new note.
4. Every prose surface that describes inference's `final` on a `cumulative-final` last chunk is
   found by grep and agrees.
5. A Critic chunk review has run, with no open blocker.

## Chunk 02: a verify pass can confirm an observation fix (C)

**Type:** code

**Delivers.**
- In `verify-resolutions`, a partial's `resolutions` entry may target a prior observation:
  `{review_id, fid: "O-n", disposition: "fixed"}` (see Decisions made mid-build). `waived` is meaningless for an observation, which gates
  nothing, so it is refused.
- `critic_consolidate` validates that the target observation exists in the store (fail-closed, like
  finding targets) and writes a resolution fact whose `finding` is `{review_id, fid: "O-n"}`.
- Readers:
  - `dispositions._observation_row` reports a resolved observation as `fixed`, and
    `resolution_detail_index` / `_target` key it unchanged.
  - `stats` counts the round as having verified something (`verified_by`).
  - `coverage_algebra.resolution_index` is unchanged and ignores the new facts. A test pins that no
    gate verdict moves.
- The verify dispatch lists the prior review's observations as well as its findings, so the
  reviewer can judge the ones the builder fixed. Where the prior-findings payload is built is to be
  located in `critic_consolidate` / `bin/prawduct-hook`.
- Docs: `data-model.md` (resolution fact body) and `goals-1-3.md` (`resolutions` schema).

**Done when:**
1. Tests cover the round trip: partial → fact → census row `fixed`.
2. Tests cover the refusals: an unknown observation id, and `waived` on an observation.
3. A test shows `resolution_index` and the Stop/PR verdicts unchanged by observation resolutions.
4. A `stats` test shows a verify round confirming only an observation is not empty.
5. A Critic chunk review has run, with no open blocker.

## Chunk 03: a verify pass reports observations only about the fixes it verifies (B)

**Type:** cumulative-final

**Delivers.**
- In `verify-resolutions`, an observation must carry `about: {review_id, fid}` (an `R-n` or `O-n` id) naming an
  existing finding or observation. It uses the same target validation as Chunk 02.
- An observation without a valid `about` is dropped from the review fact.
  - The consolidation prints how many were dropped and why.
  - The NEXT-ACTION observation count excludes them.
  - Other modes are unchanged.
- The verify dispatch directive (`VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE` or its sibling) and
  `goals-1-3.md` tell the reviewer that an observation in this mode is about whether a named fix is
  right or complete. Anything else waits for the boundary review.
- `review-cycle.md` § "A re-review does not manufacture work" records the narrowing and its cost.
  The fix delta's own content gets BLOCKING-only review plus fix-scoped observations, and the
  boundary review re-reads it at full severity.

**Done when:**
1. Tests cover: a verify observation with a valid `about` is kept; one without `about` is dropped
   with a printed count; one with an unknown target is dropped; a `chunk`/`final` observation needs
   no `about`.
2. The NEXT-ACTION count is pinned.
3. Prose surfaces describing verify-pass observations are found by grep and agree.
4. The final Critic review runs over the whole plan (`cumulative`, as the boundary), with no open
   blocker.
