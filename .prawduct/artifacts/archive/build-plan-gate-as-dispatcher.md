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
lifecycle: completed
archived: 2026-08-10
released_in: v3.2.7
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

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
- [x] Chunk 02: The refusal is observable, and the prose stops teaching the treadmill
Context: **BOTH CHUNKS COMPLETE — the empty boxes above are correct and must stay empty.**
`views_enabled: true`, so `## Status` is a DERIVED VIEW, not a record: `regen-views` rewrites every
checkbox from the change-log's shipped set, and this branch's entry is deliberately statusless because
its base is `develop` (statusless IS the release-pending state on gitflow). Hand-flipping them to `[x]`
— which this plan did until the PR review caught it — buys nothing and is silently reverted at the
release: `regenerate_status_section(lines, set())` returns `[('01','x',' '), ('02','x',' ')]`, verified
rather than assumed. Completion is recorded HERE in prose and by the tagged change-log entry; the
`develop`→`main` release flips the entry to `status=shipped` and regen fills the boxes in one pass.
(The chunks' own Done-when step 3 says "mark `[x]` in Status" — copied verbatim from
`plugin/templates/build-plan.md`, which is where the framework contradicts `views_enabled`. Left
as-is: it is a template defect, not this bundle's to fix.) Chunk 01 at `586ae1d`; Chunk 02 from `e55b6e3` (the feature)
through `165f08a` — `git log --oneline 586ae1d..HEAD` is the enumeration, because a list written here
stops growing the moment a commit edits this paragraph without adding itself (which `e1cf61c` did). Suite green — the count lives in `.prawduct/.test-evidence.json`
and `prawduct-hook test-status` is the reader; a figure transcribed here goes stale silently.
`check-cumulative-critic` is SATISFIED at HEAD — run it rather than trusting a tally written here; it recomputes, and a transcribed count is stale the next time anything lands.

Step 0 settled by owner ruling: `change-log.md` is correctly non-judgeable, and `learnings-detail.md`'s
CRT-7M2D bullet was wrong on three of its five named files. The refusal is mutation-verified on both
conjuncts and refuses exactly rounds 3/4/5 of `fix/backlog-import-title-boundary` while dispatching
1/2/6/7.

**Chunk 02's R-26 ruling: #596's sink, not the `ledger-append` this plan proposed** — reasons on
`evidence.append_guard_refusal` and now on #596 itself, so the next reader does not re-litigate it.
Two deliverables changed on their merits: the `coverage.py` remedy line was WITHDRAWN (an `uncovered`
verdict entails the span is not free, so it would have taught a false rule), and the "unconditional
verify-resolutions" the plan wanted replaced turned out to be the BLOCKING arm's, which is correct.

**What the review rounds cost, and what came of it.** Read the count and the spend from
`prawduct-hook review-stats` and the branch tally in `check-cumulative-critic`'s output — a figure
typed here is stale by the next round, which is the rule stated fourteen lines above and then broken
here in the first draft. What does not go stale: the dominant finding class was not judgment but
REGISTRATION — a primitive added to an enumerated set in code while
the registry documenting that set went stale (four times: api-contract § Error Model, data-model kinds,
the concerns row, the waivers vocabulary). Three of those cost a round each. Both underlying framework
defects are fixed in `8ba8b3e` per the owner's standing rule (fix in place, never file):
`tests/preferences/test_registry_completeness.py` makes the class a suite-time set-difference — for the
two instances that HAVE an enumerated set in code (waiver rule ids, evidence fact kinds); exit codes and
concerns rows have no left-hand side to difference and stay reviewer work, stated in the test's own
docstring so a green suite is not read as full coverage. And the verify-mode severity directive now
separates "the tree must not move" from "this fix is owed" — pinned structurally in
`tests/test_critic_consolidate.py` by `8664bc8`, because `8ba8b3e` shipped the clause with no test and
the next round caught it.

`active_build_plan` still points at `artifacts/build-plan-critic-review-identity.md` and **must not be
repointed** until the `develop`→`main` release ships (gitflow, `methodology/planning.md`
"Plan lifecycle"). No PR yet — the user has not asked for one.

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
    <!-- prawduct:allow prawduct/chunk-ref-missing -- the next line NAMES a path that never existed on any branch; that absence is the recorded defect, so the reference must stay broken -->
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
