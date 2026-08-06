---
artifact: build-plan
version: 2
scope: gate-as-dispatcher
depends_on:
  - artifact: gate-as-dispatcher-requirements
governed_by:
  # Every norm in each artifact gets a line — "that one doesn't apply" is an
  # interpretation, and it belongs where a reviewer can disagree with it.
  - artifact: architecture
    dispositions:
      - "Authority fails closed; advice fails soft → conforms — the refusal produces no merge verdict, and no uncomputable input can produce a refusal (a failed diff returns an error before the check is reached)"
      - "An independent reviewer never mutates the session it reviews → conforms, and strengthens it — a refusal returns before the marker and the partials sweep, so it mutates strictly less than a dispatch. Chunk 02 adds one append to the clone-shared evidence store, which is not session state: no marker, no manifest, no partials. The partials clause is now proved by SURVIVAL of a planted leftover rather than by its absence — the Chunk 01 form was vacuous"
      - "Goals and verification bind; prescribed method is advice → conforms — the verification structure is unchanged; only the decision to spend a round moves"
      - "Local-first: governance coordination is process-spawn + atomically-written files + the git object database → conforms — the predicate reads a git diff and the local store; no new coordination surface"
      - "The plugin writes nothing into a governed repo except its own .prawduct/ state → conforms. Chunk 01's refusal path wrote nothing at all; Chunk 02 adds ONE append to <git-common-dir>/prawduct/evidence.jsonl, which is inside .git — never committed, no gitignore contract, and already the plugin's own store. Nothing is written to the working tree"
      - "Written in Python, never specific to Python → conforms — the predicate is path-based (is_judgeable_path), language-agnostic by construction"
      - "Prawduct guides and reviews; it never implements → inapplicable because this changes prawduct's own governance plane, not any product's code"
      - "Every fact has one home; every other mention is a reference → conforms — exit 3's meaning is stated once in api-contract.md § Error Model; SKILL.md and the hook docstring cite it"
  - artifact: nonfunctional-requirements
    dispositions:
      - "Review wall-clock is P0: cost = unit-cost x run-count → conforms — this is a run-count lever, the one the norm names first"
      - "Proportionality ratchets both ways; adding a control names its expected yield and emits it observably → conforms as of Chunk 02. Requirements §1 is the recorded yield argument; the 'observably' half is discharged by a `guard-refusal` fact appended to the clone-shared evidence store on every firing, queryable as `prawduct-hook evidence list --kind guard-refusal`. It carries the interval and the free file list, so the question that retires the guard — did it ever refuse a round that turned out to be needed? — is answerable from the record rather than from memory"
      - "State-file growth past its threshold is surfaced as an advisory → conforms as of Chunk 02. No NEW state file is added, but the shared evidence store now takes one line per refusal. Its growth advisory is keyed on distinct TREES, and a refusal contributes none (`distinct_trees` filters to review facts), so refusals grow the file without moving that advisory — a deliberate choice, since the advisory measures composition cost and a refusal adds none"
  - artifact: data-model
    dispositions:
      - "Governance verdicts are computed from the append-only fact ledger, never mutable model-written state → conforms — the predicate reads the interval diff and the store; no model writes to the decision path"
      - "Facts are immutable and append-only → conforms — the refusal appends one immutable `guard-refusal` fact (Chunk 02) and never rewrites one; Chunk 01's refusal wrote none at all"
      - "Derived views are disposable and never authoritative → conforms — nothing here reads .critic-findings.json"
      - "Every issue conforms to the issue standard's §1 title rules → inapplicable because this work writes no backlog issue"
      - "A fact written by a newer schema is a loud block → inapplicable because no fact is read for its schema on this path"
      - "Two stores, two lifetimes → conforms, and the R-26 ruling turns on exactly this norm — the refusal reads the shared evidence store and now appends its `guard-refusal` fact there rather than to the per-worktree governance ledger, because these guards fire in worktrees that are then deleted. The ledger stays untouched"
      - "backlog_service_repo selects the authoritative backlog store → inapplicable because this work touches no backlog store"
  - artifact: api-contract
    # Added 2026-08-06 after the cumulative review's R-12: exit 3 ships on this
    # contract surface, so the artifact governs and its omission here was an
    # unruled departure, not an inapplicable one.
    dispositions:
      - "Exit codes are the contract, on a documented and consistent scheme; new subcommands cite it rather than inventing a return convention → conforms as of the R-12 fix — exit 3 is registered in § Error Model's sentinel list with its fail-direction rationale, and § Operations carries --force"
      - "Additive-first evolution: new subcommands and flags are added; existing exit-code meanings are never repurposed → conforms — 3 was unused on critic-begin, and 0/1/2 keep their meanings exactly"
      - "Whole-surface semver; the internal CLI carries no per-subcommand version → conforms — critic-begin is internal/unstable, outside the two-member stable tier, so no version handle is owed"
last_validated: 2026-08-06
---

## Requirements Confidence

**Level:** High

**Why:** The predicate was derived from measurement, not intuition, and validated retroactively
against seven real review rounds on a merged branch — it refuses exactly rounds 3/4/5 and dispatches
1/2/6/7. Problem, success criteria and scope are each statable in one sentence
(`gate-as-dispatcher-requirements.md` §1, §3, §5).

**Open assumptions / unknowns:** carried from requirements §8 —
`[ASSUMPTION: exit code 3 signals "no review needed" | MED impact | user can override]`,
`[ASSUMPTION: override spelled --force | LOW impact | user can rename]`,
`[ASSUMPTION: the rule is mode-uniform, not verify-resolutions-only | MED impact | user can narrow]`.
One genuine unknown — requirements §9, the `learnings-detail.md` CRT-7M2D vs `METADATA_PREFIXES`
contradiction over whether `change-log.md` is judgeable. Chunk 01 step 0 closes it before anything
leans on the predicate.

**What would raise confidence:** N/A — §9 is a step, not a gap.

## Status

- [x] Chunk 01: The dispatcher asks the gate before it spends a reviewer
- [ ] Chunk 02: The refusal is observable, and the prose stops teaching the treadmill
Context: **Chunk 01 built and committed at `586ae1d`**, suite green (the count lives in
`.prawduct/.test-evidence.json`; `prawduct-hook test-status` is the reader — a figure transcribed
here goes stale silently and nothing consults it).
Step 0 settled against the code by owner ruling: `change-log.md` is correctly non-judgeable, and
`learnings-detail.md`'s CRT-7M2D bullet was wrong on three of its five named files — corrected there.
The refusal is mutation-verified on both conjuncts, and the retroactive replay refuses exactly rounds
3/4/5 of `fix/backlog-import-title-boundary` while dispatching 1/2/6/7. Chunk 01 is CLOSED: the cumulative
(`rev-20260806T204908Z-8a18af57`, 2 blocking / 13 warning / 11 note) and its verify pass
(0/0/0, 11 resolutions) both landed, and `check-cumulative-critic` is satisfied at HEAD. Four of the
verify pass's demoted observations ride into Chunk 02 — see its carried-in block. Next: Chunk 02,
starting by reading #596 to settle the telemetry sink BEFORE writing it. Requirements in
`.prawduct/artifacts/gate-as-dispatcher-requirements.md` — read it first, it carries the
measurements, the safety argument, and the withdrawn layers. `active_build_plan` still points at
`artifacts/build-plan-critic-review-identity.md` and **must not be repointed** until the
`develop`→`main` release ships (gitflow rule, `methodology/planning.md` "Plan lifecycle").

## Verification Strategy

Tests carry most of this, but two things tests cannot say:

1. **Retroactive replay.** After Chunk 01, replay the predicate against the seven recorded rounds of
   `fix/backlog-import-title-boundary` (they are in `.git/prawduct/evidence.jsonl`) and confirm it
   refuses 3/4/5 and dispatches 1/2/6/7. This is the acceptance evidence for the whole plan — a
   predicate that cannot reproduce the split it was derived from is wrong regardless of unit tests.
2. **Live exercise.** Make a `.prawduct/`-only edit, run `/prawduct:critic verify-resolutions`, and
   watch it return in under a second with a readable message rather than spawning a reviewer. Then
   add one `.py` edit and watch the same command dispatch.

## Build Chunks

### Chunk 01: The dispatcher asks the gate before it spends a reviewer

- **Description:** Insert the refusal predicate into review dispatch. `begin_review` already derives
  `files_changed` uniformly and already calls `coverage_algebra.judgeable_files` a few lines later in
  `_derive_roster`, so the predicate is in scope at exactly the right point; and an empty-diff refusal
  already sits at that spot, giving the new refusal an existing shape to match. Refuse **iff** the
  interval holds no judgeable file **AND** no unresolved blocking finding exists that this review
  could resolve. Both conjuncts are load-bearing — dropping the second deadlocks the gate, because a
  `blocked` verdict's only remedy is the very `verify-resolutions` pass that would be refused.
- **Depends on:** none
- **Artifacts consumed:** `gate-as-dispatcher-requirements.md` §2 (the predicate), §3 (success
  criteria), §4 (the safety argument)
- **Deliverables:**
  - the predicate + refusal in `plugin/lib/critic_consolidate.py` (`begin_review`), returning a
    distinct status the CLI maps to a new exit code
  - exit-code 3 handling and the `--force` flag in `plugin/bin/prawduct-hook` (`cmd_critic_begin`)
  - `plugin/skills/critic/SKILL.md` reads exit 3 and reports "no review needed" instead of proceeding
  - new `tests/test_critic_dispatch_refusal.py`
- **Tests:** the adversarial set, because a skip-gate needs the most adversarial coverage — this is
  the explicit lesson of the retired PR trivial fast-path (recorded on `#292`), which shipped with
  none and was withdrawn. Each must be red-verified against the code that ships:
  - one judgeable file among 50 non-judgeable → **dispatches** (fails closed)
  - a governance-protected `.md` (`skills/`, `methodology/`, `templates/`, root `CLAUDE.md`) →
    judgeable → **dispatches**; this is the trap, since it is a `.md` that must not read as free
  - a free interval **with** an unresolved blocking finding → **dispatches** (the anti-deadlock case)
  - a free interval with a clean prior fact → **refuses** (rounds 3/4/5)
  - `tree_diff` returns `None` / unreadable tree / absent evidence store → **dispatches**
  - `--force` over a free interval → **dispatches**
  - refusal leaves no critic-active marker, no manifest, and no partial reset — a refusal must not
    disturb any state a real dispatch would
- **Acceptance criteria:** full suite green; the retroactive replay in Verification Strategy §1
  reproduces the 3/4/5 vs 1/2/6/7 split; `check-cumulative-critic` returns an identical verdict to
  today for a branch with and without the change (the refusal must not widen what can merge).
- **Done when:**
  0. Resolve requirements §9 — read `gitstate.METADATA_PREFIXES` and `coverage_algebra`
     against `learnings-detail.md`'s CRT-7M2D claim, decide which is correct, and correct the losing
     one. **Read the mechanism; do not assume the learning is stale because it is inconvenient.**
     Nothing else in this chunk may be built before this is settled.
  1. Acceptance criteria met and tests pass
  2. **Commit first**, then `/prawduct:critic cumulative`, and resolve blocking findings.
     <!-- Not the template's default order (review the dirty tree, then commit). `chunk`/`final`
          both diff HEAD against the WORKING tree, so on a clean tree their interval is empty and
          the dispatch is refused; only `cumulative` reads `merge-base...HEAD`, which is where
          committed work lives. Both chunks of this plan land in one PR, so `cumulative` is the
          right mode for each — and ordering it after the commit means the reviewed tree IS the
          commit's tree. Corrected 2026-08-06 after the first dispatch refused for exactly this. -->
  3. Chunk marked `[x]` in Status

### Chunk 02: The refusal is observable, and the prose stops teaching the treadmill

- **Description:** A silent skip is indistinguishable from a broken gate, and the governing norm
  ("proportionality ratchets both ways") requires the yield claim to stay falsifiable. Record each
  refusal so "how many rounds did this save, and did any of them turn out to be needed?" is a query,
  not a memory. Then fix the three prose surfaces that instruct the treadmill — these are
  governance-protected and therefore judgeable, so they are code for review purposes.
- **Depends on:** Chunk 01
- **Artifacts consumed:** `gate-as-dispatcher-requirements.md` §7 (the prose surfaces), §4 (the
  proportionality norm)
- **Carried in from the Chunk 01 cumulative review** (`rev-20260806T204908Z-8a18af57`) — riding a
  commit already being made, not deferred to a later round:
  - **R-19** — the refusal fires with no record. Three surfaces independently require one: the NFR
    "proportionality ratchets both ways" norm (disposed PARTIAL above precisely because of this),
    the opt-out-must-be-a-recorded-artifact learning, and issue **#596**.
  - **R-26** — **settle the sink before writing it.** #596 already owns pre-dispatch-guard telemetry
    *as a class* and disagrees with the `ledger-append` sink named below. Read #596 first and either
    adopt its sink or record why this one differs; do not add a second telemetry path for the same
    class of event by default. This is a real decision, not a formality — the ledger is gitignored
    and per-worktree, so a yield question spanning clones cannot be answered from it.
- **Carried in from the Chunk 01 verify pass** (`verify-resolutions` over `991417b..c287b88`, which
  returned 0/0/0 — these are its demoted observations, deliberately left out of its `resolutions`
  because the reviewer could not settle them from the tree). Riding this chunk's commit; each is
  small, and none is worth a round of its own:
  - **The `_assert_no_dispatch_state` partial-reset clause is asserted VACUOUSLY** — the highest-value
    item here. It checks the partials dir holds no `*.json` and no archive exists, but
    `_archive_leftovers` returns before creating anything when there are no children, and every
    fixture calling the helper has already had its partials removed by consolidate. So all three call
    sites pass regardless of what the refusal does. **Fix by seeding a leftover partial that must
    SURVIVE the refusal** — absence of a thing that was never there proves nothing. This is the third
    instance of that shape in one session (the `plugin/tests` scan root, the governance-`.md` mutation
    escape, this) and it is now a durable rule in `learnings.md`.
  - **`--force` is wired 2 of 4.** SKILL.md step 4's instruction and the printed remedy are done;
    still missing from the skill's `argument-hint` frontmatter and from step 4's command template
    (which shows `[--scope] [--chunk]` with no `[--force]` slot).
  - **`_USAGE` residue** — `plugin/bin/prawduct-hook` `_USAGE` still spells `critic-begin --mode <m>`
    with no `[--force]`. The docstring is already corrected; this is the other half.
- **R-26 RULING (2026-08-06): adopt #596's sink — the clone-shared evidence store, kind
  `guard-refusal` — and NOT the `ledger-append` path this plan proposed.** Four reasons, recorded in
  full on `evidence.append_guard_refusal` so the next reader meets them at the code:
  1. *Durability.* The ledger lives in the worktree (`.prawduct/.governance-ledger.jsonl`); the
     guards in this class fire in worktrees that are then deleted. The evidence store is at the
     clone's git common dir.
  2. *A reader already exists.* `prawduct-hook evidence list --kind guard-refusal` is the yield
     query today. `review-stats` reads `review.*` only, so the ledger needed a new kind AND a new
     reader.
  3. *Envelope fit.* The ledger's envelope is review-cost-shaped (`duration_seconds`, `actor.model`,
     roster); a refusal has none of those and would be a mostly-null row. The evidence envelope's
     `actor.worktree` also makes `is_ephemeral_fact` classify these for free.
  4. *One path per class.* #596 owns pre-dispatch-guard telemetry as a class and names this sink.
  **Correction to this plan's own stated reason:** it argued the ledger cannot answer a *cross-clone*
  yield question. True — but the evidence store cannot either; it lives inside `.git` and is never
  committed. The axis is cross-*worktree* durability plus an existing reader, not cross-clone reach.
  A cross-clone question still needs an exporter nobody has built.
  **Scope line:** this builds the shared sink and routes THIS guard through it. `_check_ephemeral_worktree`
  and `_check_binary_skew` remain #596's own work — the sink they were blocked on now exists.
- **Deliverables:**
  - refusal telemetry into the evidence store per the R-26 ruling above, carrying the interval and
    the free file list — enough to answer the yield question later
  - the `NEXT-ACTION` text's 0-blocking arms: *asking is free — dispatch exits 3 rather than spending
    a reviewer*. **Two corrections to this plan as written.** (a) The text lives in
    `plugin/lib/critic_consolidate.py` (`next_action_line`), not in `review-protocol.md`, which only
    relays it. (b) The "unconditional then run ONE verify-resolutions" this plan proposed replacing
    is the **BLOCKING** arm's, and it is CORRECT — a blocking finding is cleared only by the
    resolution facts a verify pass records, which is precisely why the refusal predicate's second
    conjunct exists. Replacing it would wedge the gate. The 0-blocking arms are the ones that carry
    the condition, and they keep it.
  - ~~`plugin/lib/coverage.py` — `check-cumulative-critic`'s remedy text names the free-interval
    check~~ **WITHDRAWN: the premise is false.** `coverage_verdict` already grants a direct free edge
    between the two endpoint trees whenever their diff holds no judgeable path, and both are always
    graph nodes — so an `uncovered` verdict *entails* the span is not free, and there is no
    free-interval check to name there. `cumulative`'s dispatch interval is that same span, so the
    dispatcher will not refuse it either. Writing the line would have taught a false rule.
  - `plugin/skills/critic/review-cycle.md` — the "before running another pass to close coverage"
    block, which IS a live decision point, gets the answer instead
  - `plugin/skills/pr/SKILL.md` — Step 2's sequencing paragraph, same correction
- **Tests:** a preference-style test pinning that the surfaces deciding whether a round is spent
  carry the free-interval answer (the same shape as
  `tests/preferences/test_critic_skill_structure.py`); a test that a refusal appends exactly one
  `guard-refusal` fact and that a dispatch — and a `--force` override — append none. Plus a proof
  the fact cannot compose as coverage, driven through `coverage_algebra` with a body deliberately
  shaped like an edge (it must read `covered` under kind `review` and `uncovered` as itself, or the
  test is vacuous).
- **Acceptance criteria:** full suite green; a refusal is queryable as
  `prawduct-hook evidence list --kind guard-refusal`, WITH its guard and free-file payload rendered
  (a listing that shows only "a refusal happened, at this time" does not answer the retirement
  question, and the R-26 "a reader already exists" claim would be false); no prose surface still
  instructs an unconditional post-fix review round.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## What this plan deliberately does not build

Recorded here so a later reader does not "restore" them (full reasoning in requirements §5):

- **Scoping the review payload to the judgeable subset** — withdrawn on evidence. Round 6 of the
  merged branch caught a change-log sentence asserting coverage the code did not have; a reviewer
  handed only the `.py` files could not have found it.
- **Taking prose review off the blocking path** — Chunk 01 captures 100% of the measured waste, so
  this waits for evidence it is still needed.
- **Refusing when a prior fact already covers a judgeable interval** — strictly broader, unmeasured.
  Measure before building.
- **Any relaxation of `is_judgeable_path`** — already built and reverted once; see requirements §6.
