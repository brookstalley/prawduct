---
artifact: build-plan
version: 2
scope: clear-cadence
branch: fix/clear-cadence
depends_on: []
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms, and Chunk 01 REPAIRS it. The norm's named mechanism is `prawduct-hook clear` refusing while a review is active; that refusal reads `.critic-active`, and the SessionStart `clear` path deletes that marker unconditionally. Chunk 01 stops the delete for a marker that is still plausibly live, so the guard stays armed across the event most likely to strand a live reviewer"
      - "authority fails closed; advice fails soft → conforms — the marker is an input to a governance verdict, so Chunk 01 moves the uncertain case toward keeping the marker (blocking) rather than deleting it (passing). Deleting a live marker is the fail-OPEN direction and is what the current code does"
      - "every fact has one home; every other mention is a reference to it → **DEPARTED and corrected in-chunk** (Critic R-5/R-13). Chunk 01 as first built shipped the sweep's asymmetry argument in six places, and the norm's own prediction came true inside a single commit — the hook comment's TTL bound already contradicted the docstring it deferred to. Repriced to one home: `critic_marker.py`'s module docstring owns the asymmetry and its cost, `architecture.md` owns the boundary taxonomy and references it, and the call site states only what is local to it. Recorded rather than silently fixed because the disposition claimed conformance before the code existed"
      - "goals and verification bind; prescribed method is advice → this plan's Deliverables are its author's guess; a builder who finds a better route at the call site takes it and records why. Explicitly anticipated in Chunk 01, where the Deliverables name a liveness-gated sweep but the code may support a cleaner seam"
      - "local-first governance coordination, no network or third-party runtime deps → conforms trivially — Chunk 01 is stdlib file reads already in the hot path; Chunks 02-04 are prose and tests"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state and the files it must reconcile → inapplicable: no chunk here adds a write path into a governed repo"
      - "Python, but never specific to Python → inapplicable — the marker is prawduct's own state file and the budgets measure framework prose payloads; nothing dispatches on a product language"
      - "prawduct guides and reviews, it never implements → inapplicable — no product code, and no check duplicating an ecosystem linter"
  - artifact: nonfunctional-requirements
    dispositions:
      - "proportionality ratchets both ways — a new control names its expected yield AND emits it observably → BINDS Chunk 04, which is the only chunk that could add a control. It is discharged there by DECIDING rather than by building: #688's own acceptance permits a recorded decision that on-demand guides stay unbudgeted, and this norm is the reason that branch is live rather than a dodge. Chunks 01-03 add no control (Chunk 01 narrows an existing act; 02-03 are prose)"
      - "state-file growth past its size threshold is advisory, never a hard block → inapplicable — Chunk 04 concerns SHIPPED PROSE PAYLOADS, which the 2026-08-19 owner ruling already put in the hard-ceiling class, not `.prawduct/` state files"
      - "review wall-clock is P0; unit-cost is the reviewer's payload, per-mode and reducible → conforms — Chunk 03 spends against a 5-token headroom on the always-injected framework shape and must trim or ratchet in the same commit, never bump silently"
  - artifact: project-preferences
    dispositions:
      - "a new preference or norm assigns a mechanism and an audit home; a named mechanism that does not yet exist is filed as backlog work at the norm's birth → BINDS Chunk 02. The cession it records has no mechanism home: `documentation/purpose.md` names a **responsibility ledger** as the instrument for re-pricings and says outright it is not yet built (Cycle 3). The record therefore lands in the durable change-log entry, and the gap is filed rather than papered over"
      - "model floor and coherence pass → conforms — this session runs on Opus; no sub-Fable stage to compensate for"
last_validated: 2026-08-19
---

## Requirements Confidence

**Level:** Medium

**Why:** The problem and the sites are established by reading, not inference — `building.md:114` is verbatim unchanged, the injected and on-demand carriers were read end to end, and the sweep's premise mismatch was traced through `prawduct-hook:945-987` → `critic_marker.py` → `architecture.md` § What counts as a session boundary. What is *not* established is one empirical fact and one policy call, both named below.

**Open assumptions / unknowns:**

- `[ASSUMPTION: a forked Critic review subagent survives a /clear | HIGH impact | user can correct]` — #687 raises this and it is unverified. **Chunk 01 is deliberately designed not to need the answer.** If subagents survive, today's unconditional sweep destroys a live marker (a silent governance failure). If they die, the marker is stale and the liveness test sweeps it anyway. The chunk keys on the marker's own freshness rather than on the source, so it is correct in both worlds — which is the reason to build it rather than run the experiment first.
- `[CORRECTED 2026-08-19 by Critic rev-20260819T145554Z-9e408ad8 (R-11/R-2/R-12) — the original assumption was recorded as VERIFIED and was false.]` It read: *"verified that `critic-begin` does not refuse on an existing marker (`write_marker` overwrites), so a surviving marker cannot block a new review."* I read `write_marker` — the **reader** — and never reached `critic_consolidate.begin_review`, the **consumer**, which refuses on `active or roster_state == "complete"` *before* `write_marker` is called and is **not** gated on `--force`. The true residual cost has two parts and neither is TTL-bounded in the way the original claimed: a dead-but-fresh marker **blocks the next `/prawduct:critic`** until the TTL expires, and the Stop backstop reads `marker_present()`, which has **no TTL** and keeps firing past it. Both are loud and recoverable by a command the refusal prints (`critic-end`, `critic-discard`), which is what keeps retention the cheaper error — but "at most the TTL" was wrong and is not restated anywhere. This is `learnings.md:35` (*ask the CONSUMER, not the reader*) firing against a claim I had labelled verified.
- `[ASSUMPTION: #688's premise is wrong and the honest question is a class question | MED impact | user can correct]` — #688 says `reflection.md` is "the only on-demand methodology guide with no entry in `LAST_MEASURED_TOKENS`". Measured: `discovery.md` (4752) and `planning.md` (4301) are also unbudgeted, and `discovery.md` is *larger than budgeted `building.md`*. So the real state is that on-demand guides are unbudgeted as a class with `building.md` the lone exception. Chunk 04 answers the class question and feeds the correction back to the issue.

**What would raise confidence:** Chunk 01's step 0 — read the Stop hook's abandoned-review backstop at its call site and state the residual cost from the code, before changing the sweep. That is why it is a step, not a promise.

## Scope

**In:** the buildable half of #687 (the re-pricing, the clear-verdict extension, the live-review verdict), its load-bearing prerequisite (the marker sweep), and #688.

**Out, explicitly:**

- **Any numeric threshold**, and any context-fullness gate. #687 scopes this out until rebuild cost and per-turn growth are measured from real `/clear`s, and that measurement is not in this plan. The computed live-review deadline is not an exception: it is derived from `.critic-active`'s own `started_at` and the `review-stats` medians, so it reports what *is* rather than asserting a tuned constant.
- **The long-session quality-drift question.** Parked as unmeasured with the owner's 2026-08-19 read recorded (cost, not quality, is the binding constraint). Chunk 02 records the park; it does not answer it.
- **#560** (nothing observes whether a handoff note was written). Owner decision this session: stays for 3.3.6. Chunk 03 therefore ships a prose rule knowing it is unobserved, and says so rather than implying a mechanism.

## Backlog routing — this plan splits #687

`/prawduct:backlog pick` correctly refused #687 as `stage: research`/`kind: spike` and routed it to discovery. The label is stale against the body: the issue carries a full 2026-08-19 design session with a **Delivery vehicle** ("no new gate, no context-percentage trigger, no self-measurement — extend the standing block's existing clear-safety paragraph") and a **Revised acceptance** list. One acceptance item is genuinely research-gated — the measurement — and that item is scoped out above.

So the disposition is a split, not an override: the design-complete half advances to `stage: ready` and is built here; the measurement half stays research. Chunk 02 performs the split on the issue so the labels stop disagreeing with the body.

## Scaffolding

None. This plan edits shipped prose, one hook dispatch path, and their guarding tests.

### Verification Strategy

Chunk 01 is code and verifies by behaviour at the boundary: a fresh marker survives a boundary, an expired one is swept, a continuation sweeps neither, and `--force` sweeps unconditionally wherever a sweep is licensed. Assert the *direction*, not only the state — a test that only pins today's outcome passes against a revert that swaps the sources.

Chunks 02-04 are prose and budgets, where the suite *is* the executable contract (the surface pins and the ceilings). Each closes by re-reading the changed file end to end against #687's revised acceptance, plus a re-measurement, because the deliverable is a number as much as a change. Chunk 03 additionally checks the rendered digest a real session receives, not only the source file — the two ceilings that bind it are computed over the injected set, and a source-file reading is not what a session pays.

## Build Chunks

### Chunk 01: The `/clear` sweep stops deleting a plausibly-live marker

- **Description:** `#687`'s load-bearing prerequisite, and a defect in its own right. The boundary/continuation table in `architecture.md` divides `SessionStart` sources on one question — **was the transcript restored?** — and sorts the critic-active marker sweep onto the boundary side. But the premise that licenses deleting a marker someone else wrote is narrower: **the dispatching process is gone.** For `startup` both answers agree. For `clear` they diverge — the transcript is discarded but the process is not — so the sweep is sorted by a proxy for the question it actually asks. The same reasoning already excluded `compact` and `fork`; `clear` was missed because it fails the transcript test that the other two pass.

  The fix keys on the marker rather than the source, at **both** boundary sources: sweep only a marker that already fails the liveness test, and leave a fresh one alone. This preserves the crashed-Critic rescue the sweep exists for — a stale marker is still swept — while never deleting one that is plausibly live. What it costs is priced once in `plugin/lib/critic_marker.py`'s module docstring and deliberately not restated here; the short form is that retention is the *loud* error and sweeping a live marker the *silent* one. See the `[DECISION: ...]` under Deliverables for why this is boundary-wide rather than a per-source split, and the `[CORRECTED ...]` assumption above for what the cost actually is.

  Cascade surfaces: the dispatch path, the module docstring that states the lifecycle, `architecture.md` § What counts as a session boundary (descriptive — it *tracks* the code, so it is updated, not amended), and the tests pinning the split.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/architecture.md` § Direction (reviewer non-mutation; authority fails closed) and § What counts as a session boundary
- **Deliverables:** liveness-gated sweep at the session **boundary** in `plugin/bin/prawduct-hook`; corrected premise in `plugin/lib/critic_marker.py`'s module docstring and in `architecture.md`'s boundary section — stating that the sweep's question is process death and that `clear` is where that diverges from the table's transcript test; the residual cost named where the next reader meets it

  `[DECISION: gate the whole BOUNDARY branch on the marker's TTL rather than splitting startup from clear | this deliverable originally said "with `startup` unchanged", which the code cannot express: hooks.json gives `startup|clear` ONE entry (`clear --session-start`) carrying no source, so a source split would require a finer matcher. It would also buy nothing — keying on the marker's own age answers the sweep's real question (is the dispatching process gone?) at every source, where the source is only ever a proxy for it. `startup` loses nothing but the delay: a marker there is either stale, and swept, or fresh and belonging to a concurrent session in the same worktree, where retaining it is right. Recorded under the architecture norm that method is advice and a better route found at the call site is taken and explained | user can veto/override]`
- **Tests:** boundary behaviour in the marker/session-boundary suite — a fresh marker survives a boundary, an expired one is swept, a continuation sweeps neither, and `--force` still sweeps unconditionally. Assert against a marker whose age is set by its embedded `started_at`, not by touching mtime, so the test exercises the real freshness signal rather than the fallback. Pair each retention assertion with proof the boundary still *ran*, or it also passes if `clear` were silently demoted to a continuation
- **Acceptance criteria:** suite green; the four cases above hold; reverting the dispatch change turns the retention cases red and nothing else
- **Type:** code
- **Done when:**
  0. Read the Stop hook's abandoned-review backstop at its call site and state the residual cost from the code (the confidence step above)
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: `building.md` re-prices the work-cycle limit

- **Description:** `plugin/methodology/building.md:114` states one rule on two rationales with different expiry dates. The review-scope half survives and is re-expressed as **diff size**, which is the honest unit and the one the coordinator roster rule already keys on ("a risk surface, or 12+ judgeable files"). The compaction half is **ceded** — not because compaction became survivable, but because the answer is to never approach the window, which is a cadence question and not a chunk-count one. The chunk-count number itself retires: it was a proxy for both and neither needs it now.

  This is the framework's first deliberate Principle 26 re-pricing, and it has **no mechanism home** — `documentation/purpose.md` names a responsibility ledger as the instrument and says outright it is not yet built (Cycle 3). The cession is therefore recorded in the durable change-log entry, and the missing home is filed rather than left implied. Also record the parked question: long-session quality drift stays unmeasured, with the owner's 2026-08-19 read attached, so a later reader finds a park rather than a silence.

  Budget: `building.md` sits at 4720 against a hard 4730. This chunk should net **down** — it retires a number and cedes a clause — and if it does, the ceiling ratchets in the same commit. Ratcheting is part of a cut, not a follow-up; unratcheted slack is a loan the next edit collects silently and green.
- **Depends on:** Chunk 01 (no code dependency; ordered so the plan's one code change lands and is reviewed before three prose chunks)
- **Artifacts consumed:** `documentation/purpose.md` (the re-pricing rule and the ledger's absence); `plugin/docs/principles.md` § 26
- **Deliverables:** re-priced sentence in `plugin/methodology/building.md` § Session Scope Discipline stating only the rationale that still holds, in diff-size terms;

  `[DECISION: the /clear-between-work-cycles line ships UNCHANGED | it was listed here as "carrying its actual reason rather than a bare recommendation", and a draft of that edit was written and then reverted. The reason it would carry is the cadence answer — should you clear, and by when — which Chunk 03 puts on the standing block. Stating it in both places creates a second home for one fact, the exact defect `governance-surface-dedup` spent four chunks removing and that this plan was already found departing from once. A deliverable that should not ship is recorded as a decision, not silently skipped | user can veto/override]`
 a `.prawduct/change-log.md` entry recording the cession — what was ceded, what broke its assumption, and what survives; updated `LAST_MEASURED_TOKENS` reading and a ratcheted ceiling if the file shrank; #687 split on the tracker (`stage: ready` for the built half, the measurement half stated as remaining research); a backlog item for the cession record's missing mechanism home
- **Tests:** the existing `building.md` budget pin and ceiling; a pin that the surviving sentence names diff size rather than a chunk count, asserted on the discriminating content — a reader must be able to tell which rule they are under, so pinning the mere absence of "1-3" would pass against a sentence that names nothing
- **Acceptance criteria:** suite green; #687 acceptance item 1 satisfied (only rationales that still hold, ceded one recorded as a cession); acceptance item 5 satisfied as an explicit park; the reading and ceiling agree with the file
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: The clear line answers *should you*, and a live review moves the verdict

- **Description:** Two gaps on one surface. **First**, the standing block's clear line answers *can you clear* and never *should you, or by when* — the cadence answer #687 relocates here after retiring the chunk count. **Second, and this is the live defect:** the in-flight rule binds only the *disposition* line (`RUNNING`, never `COMPLETE`); nothing binds the *clear* line, so `RUNNING` + `SAFE TO CLEAR` is a reachable and currently-correct emission. That is exactly what the 2026-08-19 session emitted three times with a Critic review in flight.

  A live review therefore moves the **verdict** to `DO NOT CLEAR`, not merely the copy. The magnitude is what makes it binding rather than a caveat: this repo's own ledger puts an opus `cumulative` round at a 660s median over 135 rounds, across a three-reviewer roster, and a clear at minute ten discards the most expensive artifact the session has produced. And it is *computable*, which is what makes it a verdict rather than the "encouraged" recommendation the label design already rejected as unknowable — elapsed from `.critic-active`'s `started_at`, roster from the per-role markers, expected total from `review-stats`. The label carries the verdict; the copy carries the magnitude and the deadline.

  Both surfaces that carry the block are in scope: `reflection.md` is canonical and owns the reasoning; `session-digest.md` is injected into every session and must carry the binding in its shortest true form. **The digest has 5 tokens of headroom on the `framework` shape and is charged twice** (both injected shapes contain it), so the digest edit is surgical — the existing in-flight sentence already names the case and can bind the second line — or the ceilings ratchet up in the same commit with what bought the raise recorded at the assertion. Do not fund it by moving prose to `reflection.md`: relocation reduces no total, and that accounting is disavowed.
- **Depends on:** Chunk 02
- **Artifacts consumed:** `.prawduct/artifacts/architecture.md` § Direction (one home per fact)
- **Deliverables:** extended clear-line guidance in `plugin/methodology/reflection.md` — a live Critic review is `DO NOT CLEAR`, with the copy owing elapsed / roster / expected and the deadline; the *should you* half, keyed to what a clear costs rather than to any threshold; the same binding in `plugin/methodology/session-digest.md` in its shortest true form, paid for in place or with both injected ceilings ratcheted and justified at the assertion
- **Tests:** extend the standing-block surface pin so both carriers state that a live review moves the *clear* verdict, asserted on the discriminating content (the verdict moves, not merely that a review is mentioned) — a pin that only checks for the word "review" passes against the copy-only phrasing this chunk exists to replace; the injected-footprint ceilings and the per-file readings
- **Acceptance criteria:** suite green; #687 acceptance item 2 satisfied on both carriers; the `RUNNING` + `SAFE TO CLEAR` combination is no longer emittable under the written rule; the rendered digest a real session receives is measured, not just the source file
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: Settle the on-demand guides' budget policy (#688)

- **Description:** #688 asks why `reflection.md` has no reading or ceiling, and correctly identifies the tension: the guide is **read on demand**, which is precisely why the standing block's full shape was moved there rather than into the always-injected digest. A ceiling that discourages putting detail in the cheap place inverts the incentive four chunks of `governance-surface-dedup` were spent building.

  Its premise needs correcting first, and the correction changes the answer. Measured this session: `discovery.md` (4752) and `planning.md` (4301) are **also** unbudgeted, and `discovery.md` is larger than budgeted `building.md`. So `reflection.md` is not the exception — on-demand guides are unbudgeted as a class, and `building.md` is the lone member with a ceiling. The question is therefore a policy question about the class, not a bookkeeping line about one file, and answering it for one file would leave two larger ones in the state the issue objects to.

  Either answer discharges #688's acceptance, and the NFR proportionality norm is what makes the second a real option rather than a dodge: a new control must name its expected yield, make it observable, and say what would retire it. If those cannot be stated honestly for a file whose cost is paid only by sessions that open it, the recorded decision *is* the deliverable. Land this chunk **after** 02 and 03 so any reading is taken post-growth, not re-priced a chunk later.
- **Depends on:** Chunks 02, 03
- **Artifacts consumed:** `.prawduct/artifacts/nonfunctional-requirements.md` § Direction (proportionality ratchets both ways)
- **Deliverables:** a decision recorded where the next reader meets it — either readings and ceilings for the on-demand class with the yield, observability and retirement evidence stated, or a comment at `LAST_MEASURED_TOKENS` explaining why on-demand guides are deliberately unbudgeted and what would change that; the premise correction fed back to #688 so the issue does not keep asserting a fact the tree contradicts
- **Tests:** whatever the decision implies — readings and ceilings if they land, and in either case a check that the recorded policy and the table agree, so a future guide added to the class cannot silently fall outside the answer
- **Acceptance criteria:** suite green; #688's two acceptance criteria satisfied under whichever branch is taken; the decision addresses `discovery.md` and `planning.md`, not `reflection.md` alone
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 05: Two friction fixes found by building this plan

- **Description:** Owner-approved mid-plan (2026-08-19) after the session hit both while running the governed path. Neither is speculative — each has a reproduction in this branch's own history.

  **`backlog file` silently drops metadata.** It appends its own ```` ```prawduct ```` block to a body that already has one, then warns *"issue body carries 2 prawduct blocks; using the last and ignoring the earlier one(s)"* — so the earlier block's content is **discarded**. All three items filed this session (#690, #691, #692) lost their `related:` edges that way, and the warning reads as cosmetic while the data loss is real. Fix at the point where the block is composed, not by asking filers to omit theirs.

  **`test-evidence record --no-rerun` restamps a count that may be stale.** It reused the prior record's counts and printed them as a `recorded: N passed` line — a **three-test gap** against the tree it was stamping, because tests had been added since the run it was reusing. (Those figures are this defect's signature, not a claim about any current suite.) The restamp is documented as an operator assertion that test-relevant content is unchanged, and there is deliberately no tree hash (removed pre-v1.4 for false positives). But **`test-status` already classifies judgeable paths**, and test files changing is precisely when the assertion is false. The fix is not a hash: it is refusing (or loudly warning) when the judgeable set has moved since the recorded run. The output line is the defect surface — a restamp that prints `recorded: N passed` is indistinguishable from a fresh measurement.
- **Depends on:** Chunk 04
- **Artifacts consumed:** none
- **Deliverables:** single-metadata-block composition in the backlog filing path; a judgeability guard on `--no-rerun` with output that distinguishes a restamp from a measurement
- **Tests:** a body already carrying a metadata block yields exactly one, with the filer's own fields preserved; a restamp after a test-file change does not silently succeed; a restamp with no judgeable change still does
- **Acceptance criteria:** suite green; filing an item with `related:` in its body preserves those edges; the stale-count-reported-as-recorded reproduction cannot recur silently
- **Type:** code
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

## Governance Checkpoints

- **After Chunk 01** — the only code change and the one that repairs a ratified norm's mechanism. Confirm the sweep's new premise is stated where a reader meets it and that the residual cost is named rather than elided.
- **After Chunk 03** — the trajectory check. Chunks 02 and 03 together are #687's answer; read them as one before Chunk 04 prices the file they grew.

## Status

- [x] Chunk 01: The `/clear` sweep stops deleting a plausibly-live marker
- [x] Chunk 02: `building.md` re-prices the work-cycle limit
- [x] Chunk 03: The clear line answers *should you*, and a live review moves the verdict
- [ ] Chunk 04: Settle the on-demand guides' budget policy (#688)
- [ ] Chunk 05: Two friction fixes found by building this plan

## Context

Plan authored 2026-08-19 on `fix/clear-cadence` off `develop`, closing #687 (buildable half) and #688 for the 3.3.5 release. Owner set the scope this session: #687 plus the marker-sweep prerequisite plus #688; **#560 explicitly deferred to 3.3.6**.

Two of #687's five acceptance items were already shipped by `governance-surface-dedup` Chunk 04 and are not re-done here — the findings-only rule and the write-notes-before-the-wait obligation both live at `plugin/methodology/reflection.md`.

**Chunk 01 closed 2026-08-19.** Commits `32f3473f` (change), `48d9e3fd` (findings fix), `15e1050e`
(budget). Critic `cumulative` rev-20260819T145554Z-9e408ad8 → 1 blocking / 8 warnings / 8 notes,
all 17 dispositioned (14 fixed, R-3 filed as #690, R-16/R-17 accepted); `verify-resolutions`
rev-20260819T152802Z-583aea58 → 0/0/0, gate satisfied. Suite green, evidence from a real JUnit run.

The chunk's most useful output was not the fix: the plan had recorded a **false "verified"** (see
the `[CORRECTED ...]` assumption above), and that is now a sharpened rule in `learnings.md`.
Governance dispositions written at plan time are predictions — re-check them at chunk close rather
than inheriting them as passes; the one-home disposition claimed conformance before the code existed
and was wrong within one commit.

**Chunk 03 closed 2026-08-19.** `1ba185cf` (the two carriers) + `622ae77e` (self-scrub) +
`a3dcd2c8` (findings fix). Critic `cumulative` rev-20260819T165646Z-1854a3ce → **0 blocking** / 4
warnings / 11 notes, all 15 dispositioned (8 fixed, 6 accepted, R-14 filed). Suite green
4807/10 skipped from a real JUnit run.

**The plan's own problem statement was wrong, and the chunk shipped the corrected version.** This
entry says so because the Deliverables were built against it: the description asserts "nothing binds
the *clear* line", but `building.md` already required "nothing outstanding, in flight included". The
real defect is narrower — the **always-injected** carrier bound only the disposition line, so an
agent that never opens a guide received no clear-line binding at all. That is a coverage gap, and
coverage is what the surface pin now asserts. A build plan's problem statement is an author's claim
like its Deliverables are; it gets verified at the chunk that implements it, not transcribed.

Both injected ceilings **ratcheted down** (3325→3322, 2248→2245) because the funding cut ran past
the addition — three section headings whose parentheticals restated the preamble or their own body.

**Chunk 02 closed 2026-08-19.** `97c71645` (re-pricing) + `234dfc10` (findings fix). Critic
`cumulative` rev-20260819T154846Z-54e5b56b → 0 blocking / 8 warnings / 13 notes, all dispositioned
(6 fixed, #692 filed from R-14, rest accepted); `verify-resolutions` rev-20260819T163259Z-512a14be
→ 0/0/0, all six tree-verifiable findings confirmed resolved.

The review caught a regression the *fix commit* introduced: collapsing the sweep's control flow made
`--force` a no-op at a boundary, because the flag had one behaviour tested across two call-shapes and
the refactor hit the untested one. `building.md` finished at 4708 — below where the branch started —
with the ceiling ratcheted 4730 → 4718.

Release context: 12 scopes are release-pending for 3.3.5. `check-releasability`'s four "no build-plan file" warnings are advisory by the release runbook's own triage table, not blockers.
