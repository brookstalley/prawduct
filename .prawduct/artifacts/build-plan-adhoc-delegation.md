---
artifact: build-plan
version: 2
scope: adhoc-delegation
branch: feat/adhoc-delegation
depends_on:
  - artifact: adhoc-delegation-discovery
  - artifact: delegation-and-verification-cost-discovery
governed_by:
  # Seeded with `prawduct-hook jurisdiction --file adhoc-delegation-discovery.md
  # --artifacts-only`, then curated: the ranker's top hits included this plan's own
  # parent discovery (not a norm-carrier) and three release plans (term overlap on
  # `bump`/`ratified`, no Direction section that binds prose placement).
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0; cost = unit-cost x run-count, both levers -> conforms. Nothing
        here enters a reviewer's payload and nothing here can demand a round: Chunk 04's advisory
        fails soft by construction, and the four chunks collapse to three dispatches because 04 is
        `cumulative-final`."
      - "proportionality ratchets both ways — a new control names its expected yield AND emits it
        observably -> ruling needed, at Chunk 04. The advisory IS a new control and the honest
        question is whether the advisory store's per-clone dismissal/resolution record counts as
        observable emission or whether this inherits the bounded exception Health Check #13 and #18
        already hold. Answered in the chunk with the store read, not asserted here."
      - "state-file growth is an advisory warning, never a hard block -> conforms, and doubly so:
        Chunk 04's control is *itself* an advisory. The briefing's standing nags on this repo
        (`project-state.yaml` 41KB, `learnings.md` 89KB) are again deliberately left alone —
        compaction is its own work and folding it into a feature branch is what the advisory
        posture exists to avoid."
      - "context weight is a cost; oversized governance state is a cost -> conforms, and this is the
        norm Chunk 02 is entirely about. The chunk reports what its trim recovered rather than
        assuming, per D6."
      - "SessionStart must be fast; no probe on the hot path may block or noticeably delay it ->
        conforms, measured at Chunk 04. The probe's work is one `git worktree list` plus one stat
        per worktree — bounded by worktree count, not by repo size."
      - "versioning is conservative -> inapplicable because this plan cuts no release; the version
        bump is the release's own decision."
  - artifact: architecture
    dispositions:
      - "authority fails closed; advice fails soft -> conforms. Chunk 04's advisory is advice: it
        names an unintegrated worktree and blocks nothing, and it is inert by absence in every repo
        that has never dispatched one."
      - "every fact has one home; every other mention is a reference -> exception, the standing one
        the injected surface already holds. The block semantics' home is `reflection.md`; the
        digest restates rather than references because its readers never open the guide. Chunk 02
        holds the line the discovery artifact drew (§8.1): a dedup is only valid for readers who
        receive the surface being deduped against, so a clause living ONLY in the digest is not
        trimmable as duplication."
      - "goals and verification bind; prescribed method is advice -> conforms. This plan's chunk
        deliverables name files and sections; a builder who finds a better placement takes it and
        records why."
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state and the
        files it must reconcile -> conforms. R8's brief is written by the *agent* into the
        delegate's own `.prawduct/`, and Chunk 04's `GITIGNORE_ENTRIES` addition writes `.gitignore`,
        which the norm names in its reconcile set."
      - "local-first: governance coordination is process-spawn + atomically-written files + the git
        object DB -> conforms. Chunk 04 reads `git worktree list` and the filesystem; no network,
        no daemon, no new dependency."
      - "prawduct guides and reviews; it never implements -> conforms. Doctrine plus one probe."
      - "an independent reviewer never mutates the session it reviews -> inapplicable because this
        plan touches no reviewer path. Adjacent and worth naming: R6 forbids an ad-hoc delegate any
        governance act, which is the same invariant one level out — Chunk 01 states it as doctrine,
        not as a mechanism, because there is no dispatch site for prawduct to enforce it at."
      - "races are avoided by construction; atomic writes everywhere -> inapplicable because Chunk
        04's probe is read-only and the advisory store it writes through is already atomic."
  - artifact: data-model
    dispositions:
      - "two stores, two lifetimes: shared committed answers vs. per-clone gitignored nags ->
        conforms. The delegate brief (R8) is per-worktree and gitignored — it is the dispatch
        record for a worktree that will be deleted, not a shared answer. The debt that must
        outlive the worktree goes where R-4.6 already puts it: handoff notes, or the backlog
        item's own `accepted-by:` / `status: promoted`."
      - "a governance document reaches a terminal state; it is never deleted -> inapplicable
        because this plan creates no governance document class. The brief is not one: it is
        gitignored per-worktree scratch, and R12's advisory is what stops an abandoned one being
        silent."
      - "facts are immutable and append-only -> inapplicable because this plan writes no facts."
      - "no model sits in a fact's write path -> inapplicable because this plan writes no facts.
        Stated separately from its sibling above because they are two ratified norms, and merging
        them is how one of the pair stops being checked."
      - "derived views are disposable and never authoritative; no gate reads a view to reach a
        verdict -> inapplicable because this plan adds no view and no gate. Chunk 04's advisory is
        the near miss and it lands the right side of the line: an advisory informs, it reaches no
        verdict."
      - "a fact written by a newer schema than the reader is a loud block, never silently dropped
        -> inapplicable because this plan reads no facts."
      - "`backlog_service_repo` selects which backlog store is authoritative; readers reach the
        backlog through the skill -> conforms at Chunk 03, which edits what `/prawduct:backlog add`
        PROPOSES and never reaches around the skill to a store."
      - "every backlog write conforms to the issue standard's title rules -> conforms at Chunk 03
        by not touching the write path: the prompt R14 adds fires BEFORE `add` writes, and changes
        what is proposed, not what is written."
partition: >-
  serial — 01/02 are one rule stated in three coupled files (delegation.md, reflection.md,
  session-digest.md) and would collide; 03 and 04 are genuinely independent of each other, but two
  delegates is not less wall clock than doing two small chunks inline, and each brief would cost
  more than its chunk changes. Precedent read, not asserted: `build-plan-delegation.md` is the only
  plan in this repo carrying a partition line and it chose serial, and `project-preferences.md`
  carries no Delegation row — so this project has no delegation history to lean on either way.
last_validated: 2026-08-21
---

## Requirements Confidence

**Level:** High

**Why:** R1–R15 are written and D1–D6 are owner-ruled in `adhoc-delegation-discovery.md`. The
problem (work that is not this cycle's gets an explicit three-way decision), success (the decision
is made once, out loud, with its cost stated, and the debt is on disk before the session ends) and
scope (§6 out-of-scope, closed) each state in one sentence. Nothing here is fast-moving or
post-cutoff.

**Open assumptions / unknowns:**

- [RESOLVED at Chunk 02: the digest trim recovers materially less than the two edits need, so a
  declared raise is required] — held. The trim recovered **22 tokens** against **55** of additions;
  the raise is +22 framework / +25 product and its counter-case is recorded at the ceiling. The
  user can still veto it: reverting the optional half (the mid-chunk trigger) is a three-line cut
  that lands back under the old ceilings. What the assumption did NOT anticipate is that the token
  ceiling is not the digest's binding budget at all — the hard 10,000-character `additionalContext`
  limit is, and it had 216 free against 228 wanted. See the Context block.
- [ASSUMPTION: an ad-hoc delegate's brief belongs at `.prawduct/.delegate-brief.md` in the
  delegate's own worktree, untracked | LOW impact | user can override the location] — resolved
  during Chunk 01 rather than left open, because the alternative had a live failure mode: an agent
  running `git add -A` in its worktree commits an untracked brief onto the delegate branch and it
  arrives in the merge. Untracked therefore means *ignored*, which means one entry in
  `lib/core.py`'s `GITIGNORE_ENTRIES` — and that entry propagates by firing the gitignore-drift
  advisory once in every governed repo. That is the contract's designed propagation path, and it
  is the honest price. The entry lands in Chunk 04 with the probe that depends on the path, not in
  Chunk 01, which only names it.

**What would raise confidence:** running the trim (Chunk 02), which converts the first assumption
into a number. Nothing cheaper does.

## Status

- [x] Chunk 01: The doctrine has one home
- [x] Chunk 02: The clear verdict accounts for a delegate
- [ ] Chunk 03: The backlog instinct gets the third option
- [ ] Chunk 04: An abandoned worktree is not silent

Context: Plan written 2026-08-21 against `adhoc-delegation-discovery.md`, all six rulings recorded
there in §7. D6 (trim first, declare the shortfall) was ruled when this plan was drawn, and §8.1
was corrected at the same time: the "mandatory" R10 amendment was drafted expecting a near-zero
rewording and measures **+14** against 12 and 9 tokens of headroom, so the trim is owed whether or
not the optional trigger ships. One retrieval bears on Chunk 02's budget argument and belongs here
rather than only in the chunk: `build-plan-delegation.md`'s Chunk 01 records that the injected
ceilings were **deliberately not ratcheted** with the cut that funded delegation's first digest
mention, and that the headroom was reserved for exactly this promotion ("start this way and
dogfood, and if we need to promote to more tokens in CLAUDE.md we will"). So the 12/9 is not
generic slack the ratchet forbids spending.

Chunk 01 done 2026-08-21. The doctrine landed as `delegation.md` § Work no plan anticipated, and
`building.md` **shrank by 5 tokens while gaining the trigger** — the pointer's own table of contents
enumerated the headings of a file the same sentence tells you to open, and that clause funded the
addition with room over (ceiling ratcheted 4762 → 4757 with the cut, not banked). `delegation.md`
1531 → 2467, a READING with no ceiling, which is the growth that rule was written for: nobody pays
it who is not already about to delegate a tangent. The brief-path assumption was **resolved rather
than carried** — `.prawduct/.delegate-brief.md`, untracked, with the `GITIGNORE_ENTRIES` line moved
into Chunk 04 beside the probe that depends on it; the reasoning is at the assumption above.
Review: 0 blocking, 1 warning, 2 notes, all three fixed in the chunk's own commit because every one
of them landed in a file already being committed.

Chunk 02 done 2026-08-21. `reflection.md` carries reaping as the close's first step and the clear
verdict now names the **general test** — recovery cost, does a clear leave the work alone? — rather
than only the live-review special case it had, which is the gap §8.2 recorded after this repo got
that verdict wrong twice in one session in opposite directions. The digest carries the amended
standing-block clause and the mid-chunk trigger.

**D6's number, which was the point of running the trim first: it recovered 17 words / 22 tokens**,
against 42 words / 55 tokens of additions — so the plan's ASSUMPTION held and the shortfall is a
declared raise, +22 framework and +25 product, the first this table has taken. The trim cut a class
rather than words: prohibitions restating what the same bullet already requires positively
("burying" is the anti-burying rule "last, after every other word"; "collapsing" is "three separate
paragraphs"). An in-place dedup, the only honest kind here — funding a digest cut against an
on-demand guide is a deletion for the reader who never opens one.

**What the plan did not know, and the next digest edit must: the token ceiling was never the
binding budget.** The digest ships as SessionStart `additionalContext`, which Claude Code spills to
a file above a hard 10,000 characters — pinned in `test_plugin_methodology_digest.py`, unraisable
by any declaration. It had 216 free at branch point; this chunk wanted 228 and the first draft went
12 over with every assertion in the token module green. The additions were shaved to fit (9987 of
10,000) and both the reading and the raise comments now name the wall, because the raise comment is
what tells the next builder a ceiling can be declared past. **Chunk 03 adds no injected prose and
Chunk 04 adds none either — but any later digest edit has ~13 characters, not a token budget.**

Review: 0 blocking, 1 warning, 2 notes. The warning was the char-limit gap above, found
independently during the scrub and improved by the Critic's placement argument; both notes were
already moot or fixed by the same figure corrections. Next: Chunk 03. Two of them were about THIS plan's `governed_by`
block — `data-model` had 8 ratified norms and 4 dispositions, and the `architecture` disposition's
stated reason was falsified by the same amendment that moved the gitignore line. Both are now
correct, so Chunk 04 inherits a curated block rather than a stale one. Next: Chunk 02.

## Scaffolding

No scaffolding. Every carrier this plan writes into already exists — the methodology guides, the
always-injected digest, the backlog skill, and the advisory probe registry — which is D4 ("doctrine
plus one small mechanism") in its structural form. The one new file is Chunk 04's probe module,
which follows `plugin/lib/upstream_probes.py` exactly: a module, a `register()`, and a line at the
composition root.

### Build & Test Configuration

`python3 -m pytest tests/ -q` runs everything; the two budget guards this plan repeatedly touches
are `tests/test_v5_methodology.py` and `tests/test_plugin_methodology_digest.py`, each ~0.5s.
**Never read a piped suite's exit status** — a `| tail` reports the pager's status, not pytest's
(`learnings.md`).

### Verification Strategy

Three of the four chunks ship prose that is read by an agent, not executed, so the guard tests
prove size and linkage and cannot prove meaning. What substitutes for execution, per chunk:

- **Prose chunks (01–03):** re-read the edited surface *as the reader who receives it* — for the
  digest, that means checking the rule is actionable without opening the guide it points at, since
  that reader by construction never does. The Critic is the independent half.
- **Chunk 04:** exercise the probe for real — create a scratch worktree with a brief in it, run the
  session-start path, see the advisory; resolve it and see the advisory clear. A probe verified only
  by unit test is a probe verified against its own fixture.
- **Whole-plan:** the injected-footprint reading is re-measured at Chunk 02 and again at the
  cumulative review, because a digest edit lands on both shapes and an edit that updated only the
  shape being worked on is the defect that pin exists to catch.

## Build Chunks

### Chunk 01: The doctrine has one home

- **Description:** The whole judgment layer, in the guide that already owns delegation judgment —
  R1–R9. The three-way decision and its delegation-first default (R1, R2), the disclosure contract
  (R3), the requirements bar with exactly four paths and the *proposed*-requirements edge (R4, R5),
  what an ad-hoc delegate does and does not do under the parent's unchanged contract (R6, R7), the
  brief-in-the-worktree as the dispatch record (R8), and session-boundedness as a reapability test
  (R9). Plus §4.2's considerations and §4.3's six anti-patterns-with-tells, which are the form this
  guide already uses. `building.md` gains a pointer only (R13).
  **This chunk is deliberately not a vertical slice**, and the reason is the architecture: the
  norm here is *one home, N pointers*, so the home has to exist before any pointer has a target.
  Establishing it is what "validate the path before widening it" means for a doctrine feature.
- **Depends on:** none
- **Artifacts consumed:** `adhoc-delegation-discovery.md` §4.1–§4.7 and §5 (R1–R9, R13)
- **Deliverables:** a new section in `plugin/methodology/delegation.md` covering R1–R9; the
  brief-location decision named there (the assumption above); a pointer line in
  `plugin/methodology/building.md`; both readings re-pinned in `tests/test_v5_methodology.py`
- **Tests:** the guide-accounting and reading pins in `tests/test_v5_methodology.py`
  (`methodology/delegation.md` is a READING with no ceiling, so it re-pins rather than gates;
  `methodology/building.md` carries a ratcheted ceiling at 4760 and the pointer must fit under it
  or trim for itself)
- **Acceptance criteria:** an agent reading only `delegation.md` can make the three-way decision,
  state what it must disclose, and name which of the four requirements paths it is on; no rule from
  the parent guide is restated (§2 of the discovery artifact forbids it); `building.md` grew by a
  pointer, not by doctrine
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: The clear verdict accounts for a delegate

- **Description:** R10, R11, R15 — and the budget. `reflection.md`'s work-cycle-boundary rule
  gains the reaping step (R11: at a boundary, never as a mid-flow interrupt) and the delegate's
  block semantics (R10), stated on the **recovery-cost** test that §8.2 established rather than as
  a blanket on-disk rule — the guide already says `RUNNING` alongside `SAFE TO CLEAR` is emittable,
  and a delegate fails that test where a regenerable background job passes it. Then the digest:
  a trim pass whose **actual recovery is reported, not assumed** (D6), the R10 amendment (+14
  measured), and the mid-chunk tangent trigger (+22 measured, the only carrier that reaches the
  first moment in §1). The shortfall is a declared raise naming its amount and its reason in the
  test comment.
  **The surfaces, enumerated,** because this chunk changes a project-wide concept:
  `plugin/methodology/reflection.md`, `plugin/methodology/session-digest.md`,
  `tests/test_v5_methodology.py` (the `methodology/reflection.md` reading, and BOTH shapes of
  `LAST_MEASURED_INJECTED_TOKENS` + `INJECTED_FOOTPRINT_CEILINGS`), and
  `tests/test_plugin_methodology_digest.py` (its phrase assertions must still hold after a trim).
  The digest is a member of both injected shapes and `CLAUDE.md` of one, so an edit that updates a
  single shape's reading is the error to avoid.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `adhoc-delegation-discovery.md` §2.3, §5 (R10, R11, R15), §8.1, §8.2
- **Deliverables:** the boundary rule in `plugin/methodology/reflection.md` carrying reaping and
  the recovery-cost verdict; the amended standing-block bullet and the tangent trigger in
  `plugin/methodology/session-digest.md`; the trim itself; re-pinned readings and, where the trim
  falls short, deliberately raised ceilings in `tests/test_v5_methodology.py` with the departure's
  reason written at the pin
- **Tests:** `tests/test_v5_methodology.py` (per-file reading + both injected shapes + both
  ceilings), `tests/test_plugin_methodology_digest.py` (the four phrase assertions and the inline
  limit)
- **Acceptance criteria:** the trim's recovery is stated as a number in the commit and at the pin,
  not implied; no clause on §8.1's ~15-item at-risk list is lost — each is either still in the
  digest or demonstrably reachable by a reader who never opens a guide; a reader of the digest
  alone can produce the right clear verdict for an unreaped delegate; a ceiling raised is a raise
  the comment justifies, and a ceiling left unratcheted after a cut says why
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: The backlog instinct gets the third option

- **Description:** R14 — the second moment in the ask, at the only stopping point that already
  fires for it. When `/prawduct:backlog add` is about to file an item describing work **in this
  repo that is ready to build**, it raises the three-way decision instead of filing silently. The
  ready-to-build qualifier is the whole guard against §8.3's defensive-asking failure: an
  idea-stage capture is not a delegation candidate and must stay a one-line entry, because a prompt
  that fires on every `add` is a prompt people route around.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `adhoc-delegation-discovery.md` §5 (R14), §8.3
- **Deliverables:** the prompt in `plugin/skills/backlog/SKILL.md`'s `add` path, pointing at Chunk
  01's doctrine rather than restating it; a guard test asserting the prompt exists and is bounded
  by the ready-to-build qualifier
- **Tests:** a new case in the backlog skill's existing test module; the skill's own size guard if
  it carries one
- **Acceptance criteria:** filing an idea-stage item is unchanged and unprompted; filing a
  ready-to-build item in this repo surfaces the three options with the delegate's cost stated; the
  prompt is silent where `project-preferences.md` sets `Delegation: off` (R2)
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: An abandoned worktree is not silent

- **Description:** R12 — the one mechanism D4 allows. A post-sync advisory probe fires when a git
  worktree of this clone holds a delegate brief and its branch is unmerged: compute spent, result
  unread, and nothing else in the system remembers. Resolved by integrating it, or by abandoning it
  with the reason recorded. **Inert by absence** in every repo that has never dispatched one, on
  `upstream_probes.py`'s pattern.
  Two things this chunk decides rather than assumes. First, the **worktree boundary**: the probe
  reads `git worktree list` metadata and stats one path — it does not read another session's brief,
  because "other worktrees belong to their own sessions" is a rule the framework states and must
  therefore obey. Second, the **proportionality ruling** the `governed_by` block defers to here:
  whether the advisory store's per-clone resolution record is the observable yield the norm demands,
  or whether this takes the bounded exception #13 and #18 already hold. Read the store before
  deciding.
- **Depends on:** Chunk 01 (the brief location is its input)
- **Artifacts consumed:** `adhoc-delegation-discovery.md` §4.5, §4.6, §5 (R12)
- **Deliverables:** new `plugin/lib/adhoc_delegate_probes.py` (probe + `register()`); its
  registration at the runtime composition root in `plugin/bin/prawduct-hook`;
  new `tests/test_adhoc_delegate_probes.py`;
  new `.prawduct/.delegate-brief.md` as the brief path, added to `GITIGNORE_ENTRIES` in
  `plugin/lib/core.py` and to this repo's own `.gitignore`; the norm
  disposition recorded in this plan's `governed_by` block, amended in place with what the store
  actually showed
- **Tests:** unit — fires on an unmerged worktree holding a brief, silent on a merged one, silent
  with no brief, silent with no worktrees at all; integration — the advisory reaches the session
  briefing and clears when resolved
- **Acceptance criteria:** the advisory names the branch and what it owes; a repo that has never
  delegated sees nothing; the probe adds no measurable time to session start (measured against the
  NFR's hot-path norm, not asserted); no other worktree's file contents are read
- **Type:** cumulative-final
  <!-- Last chunk: its review IS the one `/prawduct:critic cumulative` over
       merge-base...HEAD — commit first, run it once, no separate `final`. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Verified for real: scratch worktree + brief → advisory appears → resolve → advisory clears
  3. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  4. Chunk marked `[x]` in Status

## Early Feedback Milestone

**Milestone chunk:** 02 — the first chunk whose effect the owner experiences directly, because the
digest is injected into their next session whether or not they read this plan. Chunk 01's doctrine
is only felt when a guide is opened.
