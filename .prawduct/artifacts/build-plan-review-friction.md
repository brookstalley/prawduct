---
artifact: build-plan
version: 1
scope: review-friction
branch: fix/review-friction
depends_on:
  - artifact: nonfunctional-requirements
  - artifact: cumulative-latency-discovery
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review rigor is stage-keyed; the inner stage is any review of an uncommitted diff → ruling needed before Chunk 01, recorded beneath the clause: the stage is keyed on WHERE IN THE CYCLE the review sits, not on whether the builder committed first. A mid-plan review of the unreviewed interval (covered frontier → working tree, committed or not) is inner stage; the boundary is merge-base…HEAD at the PR point. The norm's own why (an inner-stage review run at boundary rigor is a defect priced in minutes and rounds) is what 33 mid-plan cumulatives since 09-20 violate"
      - "review wall-clock is P0 → conforms: Chunks 01 and 02 exist to cut rounds and blocked turns"
      - "unsure defaults to the inner-stage review of whatever interval exists → conforms: Chunk 01 makes the router follow it on a clean tree too"
      - "proportionality ratchets both ways → conforms: no control is added. The verdict deferral narrows an existing gate to the turns where it yields, and the mid-plan chunk removes mid-plan boundary reviews"
      - "state-file growth is an advisory warning, never a hard block → inapplicable, because no state-file size behaviour changes"
  - artifact: architecture
    dispositions:
      - "authority fails closed, advice fails soft → conforms: Chunk 02 defers only on a clearly present DO NOT CLEAR label. A missing, unreadable or ambiguous last message blocks as today"
      - "every fact has one home → conforms: the standing-block labels had no code home, only prose (session-digest.md, session-hygiene.md). Chunk 02 creates `plugin/lib/standing_block.py` as the one home and pins both prose carriers to it with a test"
      - "an independent reviewer never mutates the session it reviews → inapplicable, because no reviewer path changes; the Stop hook reads the builder's own last message"
      - "local-first, no network → conforms: the verdict comes from the Stop payload, and durations from the ledger and the evidence store"
      - "the plugin writes nothing into a governed repo except its own state, the shared evidence store and reconciled files → conforms: Chunk 03's clock rides the review fact in the evidence store the norm names"
      - "written in Python, never specific to Python → conforms: verdict labels, review intervals and review clocks are language-free"
      - "prawduct guides and reviews, it never implements → conforms: every change is to prawduct's own routing, gates and telemetry"
      - "goals and verification bind, prescribed method is advice → conforms: the Success list binds; chunk Deliverables are best guesses and the delegates' departures are recorded"
  - artifact: api-contract
    dispositions:
      - "exit codes are the contract → conforms: a deferred Stop exits 0 through the existing STH-3W7F path; no new exit code"
      - "whole-surface semantic versioning → conforms: the behaviour changes ship under the next patch version at release, and persisted additions are optional fields"
      - "additive-first evolution; persisted data independently schema-versioned → conforms if 03 bumps review-stats --json schema_version when its headline duration changes meaning, and fact-body fields are optional"
  - artifact: data-model
    dispositions:
      - "persisted formats are lock-in decisions → ruling needed (Chunk 03 only): #882 option 1 adds a dispatch interval to the review fact body. Additive and optional; older facts stay estimate-only"
      - "governance verdicts come from the append-only fact ledger → conforms: the mid-plan router reads facts through covered_frontier; the verdict deferral reads no stored state at all"
      - "facts are immutable and append-only → conforms: Chunk 03 adds fields when a fact is minted; no fact is edited"
      - "derived views are never authoritative → conforms: no gate reads .critic-findings.json; review-stats is a report, not a gate"
      - "a governance document reaches a terminal state and is never deleted → conforms: this plan is archived when its work ships"
      - "backlog issues conform to the title rules → inapplicable, because nothing here writes the backlog"
      - "a newer-schema fact is a loud block → conforms: unchanged; optional fields are read only where present"
      - "two stores, two lifetimes → conforms: the review clock rides the shared fact (an answer), and the dispatch mark stays a per-worktree gitignored file"
      - "backlog_service_repo selects the authoritative store → inapplicable, because no backlog read or write changes"
partition: >-
  00 serial and first, done by the coordinator (it changes the owner's machine config, and every later
  chunk would leak to siblings without it). 01 and 02 are delegated to two opus subagents in isolated
  worktrees. They share no module: 01 is lib/critic_mode.py, critic_consolidate and methodology prose;
  02 is the Stop path in bin/prawduct-hook and lib/gates.py. 03 is serial after them because it
  edits bin/prawduct-hook, as 02 does. The coordinator owns every shared file: CHANGELOG, the version bump
  and the token-budget tests. At integration it re-reads each delegate's prose against the other's code,
  because disjoint files do not keep one agent's claims true about a mechanism the other changed.
last_validated: 2026-09-25
---

# Build plan — reviews and Stop blocks cost what they earn

## Requirements Confidence

**Level:** High for 00 and 03, Medium for 01 and 02. The problem is measured, and the owner ruled on every
fork on 2026-09-25 (below). What remains open is two mechanics the builders verify first: the chunk
interval from a committed frontier (01) and what the Stop payload carries (02).

**Problem** (measured 2026-09-25 across all Claude config dirs and the ledgers of puzzles, discodon,
hallucinote, swordfishing, bankmachine, faidh and prawduct):
1. **Mid-plan cumulatives.** Since 09-20 there have been 74 `cumulative` reviews against 16
   `chunk`/`final` reviews. Cumulatives average ~11 findings each against ~0.5, and they feed 101
   `verify-resolutions` rounds. 33 cumulatives were chosen by rule 2 or rule 4 on a clean tree in the
   middle of a plan, not at a PR. Swordfishing ran them at 12, 17, 27 and 31 commits ahead on one
   branch. Cause: three surfaces give three orderings. `building.md:121` says "1. Commit
   2. Critic", `review-cycle.md:46` says chunk mode runs "before committing", and the consolidate
   directive (`critic_consolidate._BATCH_FIX_DIRECTIVE`) says "ONE commit, then verify". A builder who
   commits first leaves a clean tree, so `critic_mode` rule 2 fires. `extension_deferral` does not
   rescue it because the chunk just committed has not been reviewed.
2. **Stop blocks on turns that are not session ends.** The block rate on Stop events has gone from
   ~0.25% (09-01..13) to ~1.5% (09-14..20) to ~3.5% (09-21..25). Since 09-14, 17 of 32 critic/reflection
   blocks landed on turns whose standing block said DO NOT CLEAR, for example "press the button, then
   tell me", or "the review is still running" (puzzles 09-25 20:29). The Stop hook fires at every
   turn end, but the gate's message and its rationale are about session end.
3. **Siblings run this checkout live.** The user-level `prawduct` marketplace in `~/.claude` and
   `~/.claude-noun` is a `directory` source at `~/source/prawduct`. That overrides each repo's pinned
   GitHub source, and `CLAUDE_PLUGIN_ROOT` resolves to the working tree. puzzles sessions ran
   `feature/learnings-one-line@810dfbf+dirty`, and 3 `learnings-rule-body` blocks came from a gate that
   exists only on that unmerged branch. The devcontainer (discodon) uses GitHub `develop` and was not
   affected.
4. **Durations are presented as estimates.** The `review-stats` headline median uses reviewers'
   self-estimates (puzzles: 420s headline against 209s measured). The gate's round tally does the
   same (#882).

**Success:**
1. With a plan whose chunks remain unticked beyond the current one, `/prawduct:critic` with no
   arguments never answers `cumulative`, whether the builder committed first or not. It answers an
   inner-stage `chunk` over the unreviewed interval (covered frontier → working tree, or merge-base
   when nothing on the branch is covered). At the PR point (plan complete, or its last chunk
   committed) it still answers `cumulative`. A replay of the 33 mid-plan cases in tests answers `chunk`.
   *Departure (recorded 2026-09-25, cumulative review R-3):* the 33-case replay is not in tests.
   Most of those states do not reproduce outside their origin repo, because their plan, evidence
   store and base-branch refs live there. What stands instead: synthetic tests at 1, 2, 12 and 31
   commits ahead (`tests/test_mid_plan_mode.py`), plus a scratch-clone replay of 8 real puzzles
   states. 4 of the 8 reproduced; the old router answered `cumulative` for all 4, and the new one answers `chunk` for 3 and
   `deferred` for 1 (plan Context, 01 merge note).
2. Every surface that states the chunk-close order states one order, and the router gives the same
   answer under either order. One grep for the claim, run in two vocabularies, returns only
   consistent sites.
3. A Stop whose last assistant message carries a DO NOT CLEAR verdict defers the session-end gates
   (reflection, critic-review), as STH-3W7F does for background work: exit 0, with a one-line note.
   SAFE TO CLEAR, COMPLETE, no label, or an unreadable transcript all block exactly as today. The
   gate then checks the agent's own completion claim.
4. The puzzles 20:29 case is explained: a block while a review was reported in flight. It is either
   covered by Success 3, or fixed at its own cause.
5. Sibling sessions' banners show the plugin at `develop@<sha>` (or at the ref the owner picks),
   never at a feature branch or `+dirty`. The update step is written down where the release process is.
6. The `review-stats` headline duration and the gate's round tally use clocked time wherever a clock
   exists, and label estimates as estimates.

**Out of scope:**
- Bounding the span of repeat cumulatives (#890, blocked on data). This plan cuts how often they run,
  and #890 cuts what each one reviews.
- Post-cumulative verify rounds (`feature/post-cumulative-pr-coverage`, its own worktree). It also
  edits `lib/critic_mode.py` (rule 1b and the NEXT-ACTION), so whichever merges second rebases.
- Explicit `cumulative` invocations (39 since 09-20). The chunk measures them after 01 lands, before
  anything is changed about them.
- The `learnings-rule-body` behaviour on uncompacted corpora. It is by design: the learnings-one-line
  plan freezes an uncompacted corpus. Once 00 stops the leak, it reaches siblings only when that
  branch ships.
- A banner warning when a product runs a dev-branch plugin. The banner already names the branch.
  00 removes the cause, and a warning line would be permanent tax for a one-person setup.

**Open assumptions:**
- `[ASSUMPTION: the "mid-plan" test is later_review_owed (2+ unticked chunks) plus a plan resolved for the branch; a branch with no plan keeps rule 2 as today | MED — branches with no plan still escalate | user can correct]`
- `[ASSUMPTION: the chunk interval can start at a committed covered frontier, or at the merge-base, on a clean tree; the rule-4 comment says so, and 01 opens critic_consolidate.begin_review to confirm it before building on it | HIGH | builder verifies]`
- `[ASSUMPTION: the Stop payload gives the last assistant message (a field, or transcript_path), and the standing-block label can be parsed from it | HIGH — the whole of 02 | builder verifies (Foreign API)]`

**What would raise confidence:** 01 opening `begin_review`, and 02's verify-api step.

**Owner rulings (2026-09-25, answered in the planning conversation; each picked the recommended option):**
- `[DECISION: inner stage = a mid-plan review of the unreviewed interval, committed or not; the boundary is merge-base…HEAD at the PR point | reads NFR:96's "uncommitted diff" by its own why (an inner review at boundary rigor is a defect priced in rounds); Chunk 01 records this beneath the clause and leaves the clause alone | owner: "Yes, key on cycle position"]`
- `[DECISION: a DO NOT CLEAR turn defers BOTH session-end gates (reflection and critic-review); SAFE TO CLEAR, COMPLETE, no label or an unreadable transcript block as today | the label is a required, user-facing claim, so misusing it is visible; a session that exits on DO NOT CLEAR loses that session's reflection | owner: "Defer both"]`
- `[DECISION: #882 option 1, an additive optional dispatch interval on the review fact body | the evidence store is clone-shared, and a ledger join undercounts parallel worktree work | owner: "On the fact body"]`
- `[DECISION: siblings follow origin/develop through the pinned worktree; the coordinator sets it up and repoints both user-level marketplaces, backing up the config first | same ref the devcontainer already uses | owner: "develop"]`

## Status

- [x] Chunk 00: Siblings run a pinned plugin, not this checkout
- [x] Chunk 01: The router picks the mode from what is unreviewed, not from whether the builder committed
- [x] Chunk 02: A DO NOT CLEAR turn defers the session-end gates
- [x] Chunk 03: Durations are clocked where a clock exists
Context: Plan written 2026-09-25 from the sibling survey. **00 done 2026-09-25:** `~/source/prawduct-live`
is detached at origin/develop a2288858, the marketplace file points at it (backup beside it as
`known_marketplaces.json.bak-2026-09-25-review-friction`), and a fresh headless session's banner read
`plugin · detached@a228885`. It is ticked on its Done-when. Its doc paragraph gets its review in the final
cumulative (doc-only; a per-chunk round for one paragraph is the rigor-for-rounds trade the NFR prices).
The build runs in `.claude/worktrees/review-friction` on `fix/review-friction`.
**02 merged 2026-09-25 (843e1e8b).** verify-api found the Stop payload carries `last_assistant_message`
(Claude Code 2.1.282), so the detector reads that field and never the transcript. A client without it
blocks as before. The coordinator's positive control replayed every critic/reflection block since 09-14
through `clear_verdict`: 14 of 14 DO NOT CLEAR turns defer, all 13 SAFE TO CLEAR turns and the 1 unlabelled
turn still block. The puzzles 20:29 block was correct: the review had finished and recorded a real
blocker, and the agent's "still running" was stale. `[DECISION: the verdict-deferral note goes to stderr at exit 0, like the
STH-3W7F note, so neither reader sees it | surfacing it would add a message to nearly every mid-work turn,
the friction this chunk removes; the gate fires at the next turn not closing on DO NOT CLEAR | coordinator,
owner can veto]`
`[DECISION: Chunks 00–02 get ONE review after 01 merges, not one per chunk | on this branch's pre-01 router,
only `cumulative` can see committed merge work with no reviewed state behind it, so a review now plus a
review after 01 would be two boundary-rigor rounds over overlapping spans. One review of 00–02 is one round,
and it leaves the reviewed state that 03's `chunk` review starts from | coordinator, owner can veto]`
**01 merged 2026-09-25 (2fa1b228, integration a8f0d61d).** The positive control rebuilt real puzzles
states in a scratch clone. Four of eight reproduced the historical `cumulative`, and the new router
answers `chunk` for three and `deferred` for one: a 61-file cumulative that had found 0 blocking
findings. The combined suite: 1 failure inherited from develop, recorded `--degraded`, and fixed on
its own branch `fix/suite-at-boundary-note-window` (8cbf38af). The 00–02 review is the router's own
answer on this branch: `rule-2 mid-plan chunk` from the merge-base.
`[DECISION: 03 builds in parallel with the 00–02 review, in its own worktree off 59af2969 | the
partition kept 03 serial only because 01 and 02 were editing its files; both have merged, and a
review reads its own tree snapshot, so a separate worktree cannot void it | coordinator, owner can veto]`
**00–02 review (rev-20260925T215533Z-3948de9f, `chunk` from the merge-base): 1 blocking, 4 observations.**
R-1 is the inherited failure in the test evidence. Asking to WAIVE it: it is red on a clean
develop checkout (prawduct-live a2288858), the record is `--degraded` saying so, and the fix is on
`fix/suite-at-boundary-note-window` (8cbf38af), kept off this branch per `building.md:68`. O-1 is
fixed (every governing norm now has a disposition; record-lint is clean). O-2 is fixed as a class:
`gates.covered_frontier` names which clean `None` it returned (`FRONTIER_ABSENT_*`), and
`critic_consolidate.merge_base_start_reason` is the one renderer for the router's rationale and
`critic-begin`'s note. An open blocker is named with its remedy, never called "nothing reviewed". The
stale base-sync sentence is gone. There are four new tests, red before the change, and a mutation of
the blocked code turns three of them red. O-3 and O-4 are recorded ACCEPT, O-3 raised with the owner.
**Verify pass rev-20260925T220901Z-ca876f81: 0 blocking, R-1 waived.** 01 and 02 were ticked at e53f220b. Its two
observations ride 03's review: a test for the third `absent` state (free edges only), and two docstrings reworded to the present tense.
**03 merged 2026-09-25 (23ef4d04), with one departure from its Deliverables text:** the fact body carries
`dispatched_at` only, not "the measured seconds" too. The interval ends at the fact's own `ts`, the ledger's
shape, so a stored seconds value would be a second copy of a number two stamps already fix (`[DECISION]`
recorded in `data-model.md`). `review-cycle.md`'s ledger-envelope line ("`duration_seconds` … nullable,
never invented") is left as it was. 03 did not change the envelope, the line is not false, and the fact's
home is `governance-telemetry.md`, which now says `duration_seconds` is an estimate. A clause there would add tokens
to every reviewer payload to restate it.
**Cumulative rev-20260925T221925Z-733f5be1: 1 blocking, 3 warnings, 5 notes.** Resolutions, all uncommitted for
ONE verify pass:
- R-1: WAIVE. The same inherited failure is still red on a clean develop; the evidence is `--degraded` and the fix is 8cbf38af, tracked in #900.
- R-4: fixed by construction. `critic_mode._mid_plan_verdict` is the one owner of the mid-plan question. Inference and an explicit token both map it, so an explicit `chunk`/`final` with nothing unreviewed stands (honest empty-interval refusal) instead of becoming a mid-plan `cumulative`. The new test was red before the fix.
- R-2 and R-5: one class, fixed by construction. `_FIX_ORDER` is the one fix-order sentence, and `_BATCH_FIX_DIRECTIVE`, `_IF_YOU_FIX_SOME` and the blocking arm all compose it. The post-cumulative exception is stated once. `TestOneFixOrderEverywhere` pins the rendered order, with a positive control on the old wording. The Stop gate's committed-work remedy now says to run `/prawduct:critic` with no mode, not `cumulative`; the test for it was red before the fix. Three tests that pinned "ONLY if that commit touched judgeable files" were renegotiated openly to "ONLY if the fixes touch judgeable files": the same conditional property.
- R-3: the departure is recorded under Success 1. R-9: the `reviews.md` rule now points at the interval owner. R-6: ACCEPT. R-7 and R-8: #882, #878 and #815 are updated through `/prawduct:backlog`; #882 ships at merge.
**Verify rev-20260925T223758Z-eaf49419: 0 blocking, committed verbatim as 6e7abc15.** It left R-4 half-closed. The
router no longer redirects, but the empty-interval refusal in `critic-begin` still named `cumulative`, so the
whole-branch round happened one step later. The fix, uncommitted, for ONE more verify pass: `begin_review` records the
interval's origin, and an empty `chunk`/`final` interval whose start is HEAD_COVERED returns `no-review-needed`
(exit 3, which the skill stops on). The R-4 test now drives the dispatch too and was red before. O-2: the batch
directive now says the verify pass is owed only when no later review the plan owes will carry the fix, so it
agrees with the mid-plan NEXT-ACTION. O-3: `_MID_PLAN_UNREACHABLE` is a third verdict, so a short plan whose
interval cannot reach the commits still defers. The new test was red with the verdict mutated away. O-5 and O-6
are ACCEPTED. O-4, owner sign-off on Success 1's descope, is asked of the owner.
**Verify rev-20260925T225130Z-f895e82c: 0 blocking, R-4 fixed.** 03 is ticked. RIDE-ALONG, owed by the next commit the PR
flow makes (O-1): three strings still say `critic-begin` "refuses" the empty interval it now answers with exit 3. They are the
`_explicit_mode` docstring and the "will refuse it" rationale string in `critic_mode.py`, and the docstring of
`test_a_named_mode_with_nothing_unreviewed_stands_rather_than_redirecting`. Its own assertion is exit 3. O-2 to O-5 are ACCEPTED. The numbers and method are in
`.prawduct/.handoff-notes.md`, and the scripts are re-derivable from each repo's ledger and the
transcripts' `stop_hook_summary` records.

### Chunk 00: Siblings run a pinned plugin, not this checkout

**Type:** doc-only
**Why first:** the moment this plan's branch is checked out here, every sibling runs it.

**Deliverables:**
- A worktree at `~/source/prawduct-live`, detached at `origin/develop` (detached, so it never holds
  the `develop` branch lock).
- The `prawduct` entry in `~/.claude/plugins/known_marketplaces.json` and in
  `~/.claude-noun/plugins/known_marketplaces.json` points at that worktree. Back up both files first,
  and restart one sibling session to confirm.
- `documentation/release-process.md` gains a short "Maintainer dogfooding" section. It says never to
  point a directory marketplace at the checkout you develop in, and gives the update step
  (`git -C ~/source/prawduct-live fetch && git -C ~/source/prawduct-live checkout --detach origin/develop`)
  and where it runs (after each merge to develop).

**Done when:** a new puzzles session's banner reads `(plugin · detached@<origin/develop sha>)` with no `+dirty`,
and a switch of this checkout's branch changes nothing a sibling runs.

### Chunk 01: The router picks the mode from what is unreviewed, not from whether the builder committed

**Type:** code
**Governed by:** the stage ruling above.

**Deliverables:**
- `lib/critic_mode.py`: rule 2 and rule 4's clean-tree redirect do not fire mid-plan (branch plan
  resolved, `later_review_owed`). They answer `chunk` over covered frontier → tree, falling back to
  the merge-base when nothing is covered. The rationale says which. Explicit `chunk`/`final` on a
  clean tree mid-plan follows the same route instead of redirecting to `cumulative`.
- Open `critic_consolidate.begin_review` (the interval `chunk` mode captures) before the change. If it
  cannot start at a committed frontier on a clean tree, extend it there. It is the one owner of the
  interval.
- One chunk-close order stated everywhere: review the chunk, fix, then commit, which
  `planning.md:180` already calls the contract. Enumerate the claim by grep in two vocabularies
  ("commit … critic/review", "before/after committing", "ONE commit, then") across `plugin/`
  (methodology, skills, docs, templates, hooks digest) and `critic_consolidate` directives. Fix
  `building.md:121`, reconcile `_BATCH_FIX_DIRECTIVE` and `review-cycle.md:320` with `building.md:107`
  (the post-cumulative case, where commit-then-verify is rule 1b, stays explicit), and grep the
  module docstring's rule list.
- The owner's ruling recorded BENEATH NFR:96 as a dated `[DECISION]`, with the owner quoted. The clause's own words are left alone in this commit: editing a norm's statement in the commit whose code it would bless is the amend-to-match tell.
- `review-cycle.md` mode table and the `planning.md` heuristic list updated to match.

**Tests:** `tests/` for `critic_mode`. A mid-plan committed chunk (tree clean, 2+ unticked, covered
frontier) → `chunk`. The same with no frontier → `chunk` from the merge-base. Last chunk committed →
`cumulative`. Plan complete → `cumulative`. No plan → rule 2 unchanged. Explicit `final` mid-plan on
a clean tree → `chunk` interval, not `cumulative`. Each is red-verified against the pre-change module.

**Done when:** tests are green and seen red, `/prawduct:critic`, then reflect.

### Chunk 02: A DO NOT CLEAR turn defers the session-end gates

**Type:** code
**Foreign API:** Claude Code Stop-hook payload
**Governed by:** the Stop ruling above.

**Done when:**
0. verify-api: capture a real Stop payload from this Claude Code version and record whether it
   carries the last assistant message, or only `transcript_path`. Build against what it carries.
1. `lib/gates.py` gains `turn_declares_in_flight(stop_input)`, beside `background_tasks_in_flight`
   and on the same degradation ladder: permissive only on a clearly present DO NOT CLEAR verdict in
   the last assistant text, blocking on anything uncertain. The label strings come from the module
   that owns the standing-block vocabulary.
2. `cmd_stop` defers reflection and critic-review on that signal through the existing STH-3W7F
   deferral path. The note names the verdict. Other blockers (learnings, PR, trivial bounds) are
   unaffected unless the ruling says otherwise.
3. Explain the puzzles 09-25 20:29 block. Did `background_tasks` arrive empty while a review ran? Fix
   it at its cause if it is not the DO NOT CLEAR case.
4. The digest's Enforcement paragraph and `session-hygiene.md` say that the gate enforces on the
   agent's clear verdict, and what a DO NOT CLEAR turn defers. Count the digest's characters as
   well as its tokens: SessionStart context spills to a file above 10,000.
5. Tests: DO NOT CLEAR defers; SAFE TO CLEAR, COMPLETE, no label, an unreadable transcript and a
   garbage payload block; a label quoted inside earlier text does not count. Each is red-verified.
   Then `/prawduct:critic` and reflect.

### Chunk 03: Durations are clocked where a clock exists

**Type:** code
**Governed by:** the #882 ruling above. Closes #882.

**Deliverables:**
- `review-stats`: the headline duration total and median use the measured population where one
  exists and label the rest as self-reported. Every consumer of `duration_seconds` is found by grep
  (`coverage.count_branch_rounds`, `telemetry.round_price`, the ledger readers, `review-stats`), not
  by this list.
- Per the ruling: the review fact body carries `dispatched_at` and the measured seconds when known
  (option 1, additive and optional; `data-model.md` row and change-log contract note), or the tally
  joins the ledger (option 2).
- The gate's round tally reads clocked time and labels estimates.

**Tests:** the headline reads measured when the two populations disagree. A mixed branch tally
labels both. An old fact without the field still counts as an estimate. Each is red-verified. Then
`/prawduct:critic` (the final chunk's cumulative), and reflect.

## After merge: measure

Re-run the survey one week after siblings pick up the release: the cumulative-to-chunk ratio, the
verify-resolutions count, and the Stop block rate split by clear verdict. Compare against the
09-20..25 baseline above. If the mid-plan cumulative count is not near zero, 01 missed a path.
