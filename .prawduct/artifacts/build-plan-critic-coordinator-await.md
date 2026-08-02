---
artifact: build-plan
version: 2
scope: critic-coordinator-await
depends_on: []
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0; cost = unit-cost × run-count, both levers → conforms. Neither factor moves: the same three reviewers cover the same goals over the same interval, and `run_in_background: false` does not serialise them because the Agent tool declares itself concurrency-safe, so three dispatches in one message still run concurrently. What changes is only *who waits for them* — the fork instead of nobody. No chunk adds a reviewer, a goal, or a mode"
      - "proportionality ratchets both ways; a control added after 2026-07-29 names its expected yield and emits it observably → **conforms, and this plan exercises the REMOVAL arm rather than the addition arm.** Chunk 02 retires `_CACHE_WARM_DIRECTIVE`, a control that has fired on every incomplete consolidate since it shipped and has never produced a finding — because it never could: it advises a waiting session, and after Chunk 01 no session waits. Removing it is the norm's default, not an exception to it. No chunk adds a control"
      - "state-file growth surfaced as an advisory, never a hard block → inapplicable because no chunk changes a size threshold"
  - artifact: observability-strategy
    dispositions:
      - "stable severity-prefix vocabulary with a stdout/stderr channel split → conforms. Chunk 02 rewrites the body of an existing `no-op:` message on its existing channel; it introduces no prefix and moves nothing between stdout and stderr"
      - "the governance ledger has a single writer; agents never hand-author it → conforms, and Chunk 01 is the place it could have been broken. The coordinator gains a `critic-consolidate` call, which is the *existing* single writer being invoked — the fork still authors no fact, no ledger line, and no findings file"
      - "text emitted into a governed product names no prawduct-internal identifier → **conforms, and it binds Chunk 02's rewrite.** The replacement no-op text names the mechanism in plain language (the reviewing fork, its reviewers, what to wait for) and no issue, chunk, or backlog id"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → **conforms, and this is the invariant most worth stating.** The coordinator fork is not one of the reviewers under either protocol — the three `critic-reviewer` subagents are, and their own tools allow-list still binds them to read-only plus `Write`. The fork's new `critic-consolidate` call is the review's terminal step, identical to what the single-pass path has always done, and the mutation-site guard on `prawduct-hook clear` is untouched"
      - "authority fails closed; advice fails soft → conforms. No chunk changes a verdict, an exit code, or the fail-closed posture; Chunk 02 changes what an existing no-op *says*, never what it decides"
      - "local-first governance, no network in the governance runtime → inapplicable because no chunk adds a network call"
      - "the plugin writes nothing into a governed repo except its own state → inapplicable because no chunk adds a write path into a governed repo"
      - "Python but never Python-specific → inapplicable because no chunk touches per-language gate dispatch"
      - "prawduct guides and reviews; it never implements → inapplicable because every chunk edits the framework's own runtime and instructions, not a product's code"
      - "goals and verification bind; prescribed method is advice → conforms. Every `Deliverables` line below is a pre-code guess made from a grep; a builder who finds a better route takes it and records why. The Acceptance criteria and these dispositions bind"
      - "every fact has one home; every other mention is a reference to it → **conforms VIA A RECORDED EXCEPTION, not cleanly — see [DECISION] under Chunk 01.** The *sequence* (wait → consolidate → report) is one fact with one home, `review-protocol.md` § Coordinator Pattern; `SKILL.md` step 7 points at it and Chunk 03 propagates by citing that heading. The *two dispatch flags* are deliberately carried on both surfaces, which is a departure this plan inherits rather than introduces: `TestCoordinatorDispatchIsConcurrent` already pinned the single-message instruction on both, on the recorded ground that an instruction pinned once reverts silently. The exception is bounded to two tokens and guarded by an absence assertion on the SKILL side, so the norm's actual failure mode — needing N edits to change one fact — is closed for everything except those two. The failure this norm names is exactly the one #207 records: the async model was restated across eight surfaces, so no single edit could correct it"
  - artifact: data-model
    dispositions:
      - "governance verdicts computed from the append-only fact ledger, never from mutable model-written state → conforms. No model enters a fact's write path; the coordinator invokes the deterministic consolidator and reports what it returns"
      - "facts are immutable and append-only → conforms (no chunk edits or deletes a fact)"
      - "derived views are disposable and never authoritative; no gate reads a view to reach a verdict → **conforms, and Chunk 01 approaches the line deliberately.** The coordinator may read `.critic-findings.json` to *report* counts when the `SubagentStop` trigger consolidated first. That is a reviewer describing a review, not a gate reaching a verdict — every gate still composes over the evidence store"
      - "a fact written by a newer schema is surfaced as a loud block → inapplicable because no chunk changes the fact schema"
      - "two stores, two lifetimes → inapplicable because no chunk moves state between the committed and gitignored stores"
      - "`backlog_service_repo` selects the authoritative store → conforms; CRT-3F7M is read and updated through `/prawduct:backlog`, never by editing the frozen markdown"
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning; no per-subcommand version → conforms (patch-level change to existing surface)"
      - "exit codes are the contract; message severity is a stable prefix vocabulary; errors are attributed → conforms. Chunk 02 changes message text only; no exit code changes meaning"
      - "additive-first evolution; flag names, exit-code meanings and `--json` keys never repurposed → conforms. No chunk adds, removes, or repurposes a flag or a `--json` key"
  - artifact: operational-spec
    dispositions:
      - "versioning is conservative — a small feature is a patch bump → conforms"
      - "gitflow: features branch off `develop` and merge back → conforms (`fix/critic-coordinator-await` is off `develop` at `fd9edea`)"
  - artifact: security-model
    dispositions:
      - "untrusted governance state is data, not instructions → conforms. The coordinator reports consolidated counts; reviewer-authored partial content gains no instruction force it did not already have"
      - "a destructive or irreversible operation requires owner approval at the operation level → inapplicable because no chunk performs one"
      - "a governed product's content never leaves its own repository and owner → inapplicable because no chunk adds an outbound path"
last_validated: 2026-08-02
---

## Requirements Confidence

**Level:** High

**Why:** The problem, the mechanism, and the fix were established by reading the installed
Claude Code 2.1.220 binary rather than by inference from symptoms — which is what every prior
attempt on this item lacked and why it sat at `stage: research` for twelve days. The parent
requirement is CRT-3F7M (#207), whose acceptance criteria this plan discharges in full. The
one design choice that could have gone either way — whether the caller blocks — was put to
the owner and answered on 2026-08-02: keep the skill backgrounded, make the fork await.

**Open assumptions / unknowns:** none open — the one that mattered is **RESOLVED, in the
negative**, 2026-08-02 by Chunk 01's `verify-resolutions` pass.

[RESOLVED-ASSUMPTION: an edited `plugin/skills/critic/SKILL.md` is picked up by an
already-running session without a restart → **FALSE.** The reviewing fork's own skill body
matched `git show fd9edea:plugin/skills/critic/SKILL.md` byte-for-byte — still ending
`and **STOP**` / `there is no resume-to-aggregate` — while HEAD carried the rewrite. The
marketplace installs from this working directory (`known_marketplaces.json` →
`source: directory, path: /Users/brookstalley/source/prawduct`), so no copy step explains it:
skill bodies are cached **per session**, and edits reach a fork only after a session boundary.
Impact is confined to validation, not to the fix: a `verify-resolutions` routes identically
under either body, which is why Chunk 01's review was unaffected. But Chunk 03's `cumulative`
is this plan's live acceptance test, and run from an unrestarted session it would
dispatch-and-return — burning 7-9 minutes on a result that cannot tell "await-in-fork does not
work" from "this session never loaded the fix." That ambiguity is exactly the failure mode
#207 spent twelve days in, so the restart is a **precondition** on Chunk 03, not advice.]

**What would raise confidence:** Chunk 03's own `cumulative` review is the live validation —
see Verification Strategy.

## Status

- [ ] Chunk 01: The coordinator awaits its reviewers and consolidates in-turn
- [ ] Chunk 02: Retire the cache-warm stopgap and re-true the wait-side messages
- [ ] Chunk 03: Propagate the corrected model to the governance surfaces
Context: Plan written 2026-08-02 on branch `fix/critic-coordinator-await` off `develop` at
`fd9edea`. Current suite counts live in `.prawduct/.test-evidence.json`, not here — a total
restated in prose is stale the moment a chunk adds a test. Research is complete and recorded on
#207.

**All three chunks are BUILT; the plan is not complete.** Chunks 01 (`fd0bd59`) and 02
(`e08f7b1`) are committed and each carries a clean Critic round — 01 verified 0 blocking, 02
returned 0 blocking with its 3 warnings fixed in the same pass. Chunk 03's edits are built and
green.

**What remains is Chunk 03's Done-when step 0, and it cannot be done from the session that
built this.** Skill bodies are cached per session and prawduct's `SessionStart` hook does not
request `reloadSkills`, so **`/clear` is not enough — the CLI must be restarted.** Then run
`/prawduct:critic cumulative`; that review is this plan's live acceptance test.

**Read the result this way, because the ambiguity the plan originally feared is gone.** The
harness source already establishes that a `run_in_background: false` dispatch blocks. So if the
fork returns having merely dispatched, that is evidence about the *session*, not about the fix
— restart and re-run. The result that validates is a fork report carrying consolidated finding
counts.

## Verification Strategy

Tests cover the instruction surfaces and the message text. They cannot cover the thing that
actually failed, which is whether a `context: fork` coordinator blocks on a synchronous
`Agent` dispatch — no unit test can reach that.

**Chunk 03's `cumulative` review IS the acceptance test for the whole plan.** It runs the
edited protocol against a genuine multi-file diff, which is the 7-9 minute coordinator review
#207 asks for by name. Three observations settle it, and all three must be recorded in the
reflection:

1. The fork's returned report carries **consolidated finding counts**, not "three reviewers
   dispatched" — this is the whole fix.
2. Wall-clock from dispatch to the fork's return is one review, not three (the previously
   measured coordinator roster ran 9m11s to first partial and 9m44s to all three; three
   *serialised* reviewers would show ~27 min, which would falsify the concurrency reading).
3. `prawduct-hook critic-consolidate` run afterward reports an already-consolidated review,
   not a pending manifest.

If the fork instead returns immediately having dispatched, the SKILL.md edit did not reach the
running session — restart and re-run before concluding anything about await-in-fork.

## Build Chunks

### Chunk 01: The coordinator awaits its reviewers and consolidates in-turn

- **Description:** Replace dispatch-and-STOP with dispatch-await-consolidate-report on the
  coordinator path. The three reviewers go out in one message (concurrency) with
  `run_in_background: false` (the await); when they return the fork runs the existing
  consolidator and reports the counts, so the consolidated result reaches the invoking session
  as the fork's own task notification instead of depending on the `SubagentStop` trigger or
  the session-end backstop. Both of those stay as backstops — this changes which path is
  primary, not which paths exist.
- **Depends on:** none
- **Artifacts consumed:** CRT-3F7M (#207) — problem statement, acceptance criteria, and the
  recorded research outcome
- **Deliverables:** `plugin/skills/critic/review-protocol.md` § Coordinator Pattern (the one
  home for the dispatch contract — rewritten step 3, plus the two-part reason the flags
  matter); `plugin/skills/critic/SKILL.md` step 7 coordinator branch (routes to that heading
  and carries the two dispatch flags, nothing further — see [DECISION] below);
  `plugin/agents/critic-reviewer.md` (the closing decoupling claim, which asserts the opposite
  of what will now be true)
- **Tests:** `tests/test_critic_skill_metadata.py` and `tests/test_critic_reviewer_agent.py` —
  assert both surfaces name `run_in_background: false` and single-message dispatch; assert
  `review-protocol.md` directs an in-turn consolidate and a findings-carrying final message;
  assert no critic instruction surface still tells the coordinator to stop without
  aggregating. Guard the one-home split **as an absence**: the SKILL coordinator bullet must
  cite the Coordinator Pattern and must NOT restate the consolidate step — a positive
  assertion cannot catch accretion, and accretion is the direction this drifts

- **[DECISION: `SKILL.md` keeps the two dispatch flags rather than becoming a pure pointer.]**
  This plan's first draft said "trimmed to a pointer, not a second copy," and the first build
  did the opposite without recording why — the Critic caught the bullet at 131 words restating
  the whole contract, and caught the plan asserting one-home conformance about a diff that
  departed from it. Both were right. The resolution is neither of the two obvious ones.
  *Alternative A — obey the plan literally* (pure pointer) would delete
  `test_skill_routing_bullet_demands_one_message`, a guard that predates this work and encodes
  a deliberate finding: an instruction pinned on one of two surfaces reverts silently, and the
  framework has already watched the ambient batching behaviour differ between sessions.
  Reversing a standing recorded decision is not this chunk's business.
  *Alternative B — keep the full restatement* leaves the sequence needing two edits to change,
  which is the exact defect #207 documents.
  **Chosen: split by what actually reverts.** The two flags are single tokens whose loss costs
  a whole review and which no downstream reader can infer — pinned twice, guarded twice. The
  sequence is prose a reviewer reads in full at step 2 — one home, and the SKILL side guards
  its own silence. Trade-off accepted: two tokens now live in two files, so a future change to
  *which flags* the dispatch uses costs two edits. That is the bounded cost of the standing
  anti-reversion decision, not a new licence to duplicate.
- **Acceptance criteria:** suite green; the three instruction surfaces agree with each other
  and with the harness behaviour recorded on #207; grep finds no surviving "there is no
  resume-to-aggregate" or equivalent
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk recorded via a tagged change-log entry

### Chunk 02: Retire the cache-warm stopgap and re-true the wait-side messages

- **Description:** Dispose of `_CACHE_WARM_INTERVAL_MINUTES = 4` and `_CACHE_WARM_DIRECTIVE`
  — the inherited CRT-8Q6R clock, which binds this item's resolution and which Chunk 01
  resolves in the *retire* direction rather than the re-size direction: the directive advises
  a session waiting on partials, and after Chunk 01 the waiting happens inside the fork, where
  no advice is needed and no prompt cache is idling. Separately, `_incomplete_noop_message`'s
  coordinator branch tells the caller that "reviewers run in the BACKGROUND after the
  dispatching fork returns", which Chunk 01 makes false — rewrite it to describe the fork that
  is holding them.
- **Depends on:** Chunk 01
- **Artifacts consumed:** CRT-3F7M's inherited `revisit:` clause (the two-edit cost is
  deliberate, not a surprise)
- **Deliverables:** `plugin/lib/critic_consolidate.py` — delete both constants and the
  rationale block above them, drop the two `line += _CACHE_WARM_DIRECTIVE` sites, rewrite the
  coordinator branch of `_incomplete_noop_message`; `plugin/skills/critic/review-cycle.md`
  § Prep work before invoking cumulative (the operator-facing 4-minute prose the constant is
  bound to); `tests/test_critic_consolidate.py` — retire
  `test_wait_side_directs_a_periodic_readout` and
  `test_review_cycle_prose_matches_the_code_cadence`, replacing them with assertions on the
  corrected wording; `tests/test_v5_methodology.py` (the token-budget narrative names the
  directive as the funding source for a since-relocated clause — the note becomes false when
  the symbol goes); `plugin/lib/critic_consolidate.py`'s `_BATCH_FIX_DIRECTIVE` docstring,
  which cross-references the retired symbol by `:data:` role;
  `.prawduct/artifacts/architecture.md` — **both** sites, moved here from Chunk 03 (see
  [DECISION] below)

- **[DECISION: `architecture.md` moves from Chunk 03 to Chunk 02.]** The plan assigned both of
  its sites to Chunk 03's propagation pass. But one of them *names the symbol this chunk
  deletes*, and the other states the falsified rationale ("the coordinator cannot reliably
  resume to aggregate") that Chunk 01 already disproved. Leaving either until Chunk 03 means
  shipping a commit whose governing artifact cites a symbol that no longer exists and explains
  a decision by a mechanism that was measured false — a state no reader could distinguish from
  a genuine defect. A reference dies in the same commit as its referent. Chunk 03 keeps the
  rest of its propagation list; only this file moved. This also discharges R-4 of
  `rev-20260802T174556Z-b9290989`, which was accepted as a deferral to Chunk 03.
- **Tests:** the retired tests are replaced, not merely deleted — the wait-side pair asserts
  that neither variant tells a caller to poll on a cadence, a positive pin asserts the
  coordinator variant names the fork as the holder of the reviewers, the guide-binding test
  inverts to forbid any cadence literal in `review-cycle.md`, and the stale-dispatch test keeps
  its liveness half. One assertion walks **every `.py` and `.md` under `plugin/`** for
  `_CACHE_WARM`, so the retirement cannot be called done while a cross-reference dangles
  outside the module that defined it
- **Acceptance criteria:** suite green; `_CACHE_WARM` survives nowhere under `plugin/`. Two
  scopes are deliberately exempt and neither is a loophole: `.prawduct/` history (backlog,
  change-log, migration records — they must keep naming what they retired) and the absence
  guard itself in `tests/`, since a test that forbids a symbol has to spell it. The no-op
  message read cold describes the current mechanism
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk recorded via a tagged change-log entry

### Chunk 03: Propagate the corrected model to the governance surfaces

- **Description:** Six surfaces describe the coordinator's asynchrony, and each is now wrong
  in a different degree. The standing-block rule stays *true* — the invoking session's turn
  still ends before the review lands, because the skill itself is still a background fork —
  but its stated mechanism ("the fork returns immediately") becomes false, and a rule whose
  reason is wrong is a rule that gets edited away by the next reader. Correct the mechanism
  everywhere it is stated, cite the one home for the dispatch contract, and record the change.
- **Depends on:** Chunk 02
- **Artifacts consumed:** `architecture.md` § Direction (the one-home norm governs how this
  chunk is allowed to propagate — cite, never restate)
- **Deliverables:** `plugin/methodology/reflection.md` (the coordinator case under "Outstanding
  means in flight"); `plugin/methodology/session-digest.md` and
  `plugin/methodology/session-digest-slim.md` (the consolidate-before-read line and the
  standing-block clause); `CLAUDE.md` § The Critic; `plugin/methodology/building.md`
  § Resolve findings; `.prawduct/change-log.md` (entries tagged `critic-coordinator-await` for
  all three chunks). **`architecture.md` is NOT in this list** — both its sites moved into
  Chunk 02, where the symbol they cite is deleted; see that chunk's [DECISION].
- **Tests:** existing prose-coherence and token-budget tests cover these files; extend
  `tests/test_cutover_prose_coherence.py` (or the nearest equivalent) so a surface claiming
  the fork returns without aggregating fails the suite. Token budgets are ceilings, not
  targets — this chunk must not raise one; fund additions by trimming, per the standing rule
- **Acceptance criteria:** suite green including token budgets with no ceiling raised; every
  surface's *mechanism* matches the harness; CRT-3F7M's acceptance boxes are both discharged
- **Type:** cumulative-final
- **Done when:**
  0. **PRECONDITION — run the `cumulative` from a session started AFTER Chunk 01 landed.**
     Skill bodies are cached per session (see RESOLVED-ASSUMPTION above); a fork launched from
     an older session serves the pre-fix `SKILL.md` and will dispatch-and-return no matter how
     correct the tree is. Confirm before invoking: the reviewing fork must be running a body
     whose coordinator bullet names `run_in_background: false`. Without this the review is not
     evidence about anything.
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run — **this review is the plan's live
     validation; record the three Verification Strategy observations in the reflection**
  3. Blocking findings resolved; chunk recorded via a tagged change-log entry
  4. CRT-3F7M updated through `/prawduct:backlog` with the validation result

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic review passes. Chunk 03's
`cumulative` review makes the branch PR-ready and doubles as the acceptance test; `/prawduct:pr`
runs only when the user asks.

- After Chunk 01: the instruction surfaces are the product here — confirm they read correctly
  cold, by someone who has not seen this plan, before widening to the runtime.
- After Chunk 03 (cumulative): the review's own behaviour is evidence. If it behaves the old
  way, the plan has not shipped, whatever the tests say.
