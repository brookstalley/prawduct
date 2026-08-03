---
artifact: build-plan
# Distinct scope from the start — never null (a null scope inherits another
# scope's shipped checkbox flips at regen-views) and never a version (that
# would collide with the release plans).
version: 2
scope: silent-gates
depends_on: []
governed_by:
  - artifact: architecture
    dispositions:
      - "authority fails closed; advice fails soft → **conforms, and it is the organising norm of this plan.** Every item in scope is a check that reports health it never measured. Chunk 01 is the fail-closed half: `verify-resolutions` produces a *verdict* (a resolution fact lifts a BLOCKING finding), and it currently computes that verdict over an interval pointing the wrong way — the fix restores fail-closed by refusing to treat an anchor that is AHEAD of HEAD as a committed delta. Chunk 02 is the fail-soft half, and it engages the learnings rule that sharpens this norm: *advice fails soft is not advice fails silent*. A probe that returns `[]` because its guard short-circuited is not degrading to a note, it is manufacturing the false success it exists to prevent"
      - "prawduct is written in Python and must never be specific to Python; a language with no populated rules is reported as *unchecked*, never silently passed → **conforms, and Chunk 02 is the same defect shape one domain over.** The norm's `never silently passed` clause is exactly what `probe_norm_health_sweep_overdue`'s heading guard violates for a repo that homes its norms in the preferences Enforcement table — a legitimate homing under `docs/norms.md` § Where Norms Live. Chunk 03's `sys.executable` fix is the norm's runtime-assumption arm: hardcoded `python3` assumes the interpreter running the framework is the one on the product's PATH"
      - "every fact has one home; every other mention is a reference to it — a fact includes **a path** and **a rule statement** → **conforms, and this plan pays a debt to it.** Two of the four source issues cite line numbers that are already stale (#554 says `critic_consolidate.py:577`, the site is `:670`; #154 says `audit_learnings_cmd.py:167`, the site is `:346`). Every Deliverable below therefore names its change site by **structural pattern** — the symbol or the literal — never by address, per `methodology/planning.md` § Common Traps"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state, the shared evidence store, and the files it must reconcile → conforms. Chunk 03 changes the *encoding* of writes through the shared writer; it adds no write target, and the one caller whose target is a product-authored file (`learnings_obligation.repair`) already passes `encoding=\"utf-8\"` explicitly and is unaffected by the default flip"
      - "goals and verification bind; prescribed method is advice → conforms. Every `Deliverables` line is a pre-code guess made from reading the sites, not from writing the fix; a builder who finds a better route takes it and records why. The Acceptance criteria, the red-verification requirement, and these dispositions bind"
      - "an independent reviewer never mutates the session it reviews — enforced at the mutation site → **inapplicable because no chunk touches the mutation guard.** Stated rather than skipped because Chunk 01 edits `critic_consolidate.py`, which *hosts* the review lifecycle the guard keys on (`critic-begin` … `critic-consolidate`): the chunk changes which trees a fact names, never who may write during a review"
      - "local-first governance, no network in the governance runtime → inapplicable because no chunk adds a network call or a third-party dependency"
      - "prawduct guides and reviews; it never implements → inapplicable because every chunk edits the framework's own runtime, not a product's code"
  - artifact: data-model
    dispositions:
      - "governance verdicts on the Critic data plane are computed from the append-only fact ledger, never from mutable model-written state — no model sits in a fact's write path → **conforms, and Chunk 01 is entirely inside that deterministic write path.** The fix reads two fields the prior fact already carries (`head_commit`, `commit_reviewed`) and adds no model judgment; the discriminator is present in the fact and simply not read today"
      - "facts are immutable and append-only; a state change is expressed as a new fact, never an edit or delete in place → **conforms, with a consequence recorded rather than repaired.** The wrongly-anchored resolution facts already written on `fix/drift-burndown` (`rev-20260802T191628Z-ddd15904` and its four resolutions) stay in the ledger. Chunk 01 does not rewrite them and must not — see [DECISION] under Chunk 01"
      - "a fact written by a newer schema than the reader is surfaced as a loud block, never silently dropped → **inapplicable because no chunk changes the fact schema.** Chunk 01 changes which tree hashes populate existing fields, not the field set, so no schema version moves and no reader needs to block"
      - "derived views are disposable and never authoritative — no gate reads a view to reach a verdict → conforms; no chunk makes a gate read `.critic-findings.json`"
      - "two stores, two lifetimes: shared committed answers kept distinct from per-clone gitignored nags and caches → conforms; no chunk moves state between the two"
      - "`backlog_service_repo` selects which backlog store is authoritative; once set, `.prawduct/backlog.md` is frozen history → conforms as *process*: all four items were read and triaged through `/prawduct:backlog` against `brookstalley/prawduct`, and the frozen markdown was never consulted"
  - artifact: nonfunctional-requirements
    dispositions:
      - "proportionality ratchets both ways — a control names the yield it expects **and emits that yield observably**, so there is something to measure it against later → **conforms, and it is the second reason Chunk 02 matters.** A probe silenced by a short-circuited guard emits no yield at all, so it can never be retired on evidence, only defended on principle — the exact state this norm forbids. Chunk 02 restores the sweep reminder to a state where its yield is observable — and with it the janitor sweep that covers what the other two probes read"
      - "review wall-clock is a P0 constraint: cost = unit-cost × run-count, and both factors are levers → **conforms, and Chunk 01 reduces run-count.** The inverted interval makes `record_lint` report findings already discharged on disk, which costs a re-review round per occurrence"
      - "no probe or gate on the hot path may block or noticeably delay session start → **binds Chunk 02 and constrains the fix.** The norm probes run on the advisory hot path; the widened guard must not add a filesystem walk beyond the artifact reads already performed. `_artifact_paths` is already read once per probe pass — the fix reuses it, and the Enforcement-table read is one additional file at most"
      - "state-file growth past its size threshold is surfaced as an advisory warning, never a hard block → inapplicable because no chunk changes a state file's size posture"
last_validated: null
---

## Requirements Confidence

**Level:** High

**Why:** All four defects are field-verified with repros, and three of the four name their own
fix in the issue body. Each site was read in this worktree and located by structural pattern
before the plan was written — not taken from the issue's line numbers, two of which are stale.
Problem, success, and scope are each statable in one sentence.

**Open assumptions / unknowns:**

- `[ASSUMPTION: "a Direction entry exists" means "a Why:-bearing entry exists" | MED impact | user can override]`
  — the reporter *suggested* a `Why:` line as the minimum; this plan adopts it because
  `docs/norms.md` § Anatomy of a Norm makes **Why required** ("a norm captured without its why
  is unenforceable at the edges and immortal at the center") while Status is optional and the
  bold Statement is not mechanically distinguishable from any bold roadmap bullet. Grounded in
  the spec rather than in the suggestion, but it is still an interpretation of what the spec
  makes machine-checkable.
- `[ASSUMPTION: widening the sweep guard is fleet-visible and that is intended | MED impact | user can veto]`
  — Chunk 02 makes `norm-health-sweep-overdue` reachable in repos that home norms only in the
  preferences Enforcement table. Those repos are silent today and will begin seeing an `info`
  advisory. That is the defect being fixed, not a side effect; recorded because "a previously
  quiet fleet starts talking" is the owner's call, not the builder's, and the v3.2.3 release
  gate already recorded one accepted advisory-amplification risk (`BKL-8W2M` / #197).
- `[ASSUMPTION: no in-scope fix needs a schema or format change | LOW impact | user can defer]`
  — verified by reading: Chunk 01 repopulates existing fact fields, Chunk 02 changes trigger
  conditions only, Chunk 03 changes an encoding default and an argv element.

**What would raise confidence:** N/A (High).

## Status

<!-- Derived view (`views_enabled: true`). Mark a chunk shipped by adding a change-log entry
     tagged scope=silent-gates / status=shipped, then run regen-views.
     Do NOT hand-flip the checkboxes. Stays [ ] on this branch until the release ships. -->

- [ ] Chunk 01: The inverted verify-resolutions interval (#554)
- [ ] Chunk 02: Direction detection — a heading is not a registry, and its absence is not health (#567)
- [ ] Chunk 03: The mechanical tail — one encoding default, one interpreter (#562, #154)
Context: Plan authored 2026-08-03 on `fix/silent-gates`, cut from `develop` at `596d761` after
v3.2.3 shipped. Scope chosen by the owner from a `/prawduct:backlog pick` roster; the theme is
**a check that reports health it did not measure**, which is what unifies the four items rather
than their file locations. #556 was offered in the same roster and **deliberately excluded** —
its own issue body says the fix is either an evidence-record schema change or a git diff on the
`test-evidence record` hot path, "larger design calls than a trigger widening," so it is a design
question wearing an `effort:S` label.

**ALL THREE CHUNKS ARE BUILT** (2026-08-03). Chunk 01 `5bc1d31`, Chunk 02 `3bfd4bf`, Chunk 03
`b3f2880`, plus `ed4456f` / `a388720` for record and learnings corrections. Each of 01 and 02 ran
its `chunk` review and a `verify-resolutions` round: Chunk 01 closed 1 blocking + 1 note, verify
0/0/0; Chunk 02 closed 1 blocking + 3 notes, verify 0/0/0 with all four resolutions recorded. All
four tracker items are closed by the change-log entries — #554, #567, #562, #154.

`develop` was merged in **before** the cumulative (`bacef70`, clean — one new doc file), which is
this plan's own governance checkpoint and the thing #565 exists to make automatic. Chunk 03 is
`Type: cumulative-final`, so its `/prawduct:critic cumulative` is the plan's single final review and
also the `/prawduct:pr create` gate — there is no separate `final` outstanding.

Two findings were filed rather than absorbed: **#568** (`record_lint.direction_norm_count` counts
Direction norms by bullet while `norm_probes` counts them by `Why:` — two definitions in one
codebase) and **#569** (`**Why:**` makes a norm invisible to all four norm probes; current behaviour
pinned by a near-miss test so a deliberate widening turns it red).

**Next: the cumulative review, then a PR only if the user asks.**

`active_build_plan` names this plan. The slot was **empty**, not occupied: v3.2.3's Phase 1
step 11 cleared it to `null` and left the instruction "next work comes from
`/prawduct:backlog pick`, which sets this" — which is exactly the route this plan arrived by.
It is therefore the first set since the clear and inherits none of the staleness the three
recorded pointer incidents describe. The gates resolve this branch's plan by `scope:` regardless,
which is what made the cleared state survivable in the first place.

## Scaffolding

Not applicable — this plan changes four sites in an existing, fully scaffolded repo. `pytest -q`
from the repo root runs everything; the suite stood at 3297 passing on the predecessor branch.

### Verification Strategy

Tests are the primary evidence, and **every guard added in this plan is red-verified in the same
pass that adds it** — write the test, revert the specific guard, watch that test and no other go
red, restore. This is not ceremony: the predecessor branch had three of four review rounds catch
an under-tested guard, twice in code written to close a finding, and its own forward notes name
red-verification as the rule that would have caught it.

Beyond tests, two of the three chunks need the framework exercised rather than unit-tested:

- **Chunk 01** — reproduce the defect end-to-end before fixing it: run a `chunk`-mode review with
  a dirty tree, fix findings without committing, run `verify-resolutions`, and confirm the
  manifest interval comes out swapped. The fix is verified when the same sequence produces a
  working-tree anchor and a forward delta.
- **Chunk 02** — exercise both defects against scratch repos: one whose only `## Direction`
  section is a roadmap (arm (a) must now fire), and one that homes norms solely in the
  Enforcement table (the sweep reminder must now be reachable).

**Invoke the worktree, not the PATH binary.** `prawduct-hook` on `$PATH` is the *installed*
plugin cache, not this checkout — every live verification runs `python3 plugin/bin/prawduct-hook`
from the repo root. A green run of the PATH binary is evidence about the installed plugin and
nothing else.

## Build Chunks

### Chunk 01: The inverted verify-resolutions interval (#554)

- **Description:** `verify-resolutions` cannot distinguish "a commit landed after the prior
  review" from "the prior review anchored AHEAD of HEAD and nothing has been committed since" —
  the normal shape after a `chunk`-mode review of a dirty tree. The interval comes out with base
  and head **swapped**, so `files_changed` describes the chunk's deletion, `record_lint` grades
  pre-fix content, and — the load-bearing consequence — **resolution facts are persisted against
  a tree in which none of the fixes exist**. Resolutions weaken a gate, so a BLOCKING finding can
  be lifted on pre-fix evidence. This is the only item in the plan that is unsound rather than
  noisy, which is why it goes first.
- **Depends on:** none
- **Artifacts consumed:** `data-model.md` § Direction (fact write path, immutability),
  `architecture.md` § Direction (authority fails closed)
- **Deliverables:**
  - `plugin/lib/critic_consolidate.py` — the `verify-resolutions` branch of the interval
    computation, at the `committed_differs` assignment (currently `capture["head_tree"] !=
    base_tree`): treat "no commit landed" as the discriminator the prior fact already carries.
    When the prior fact records `head_commit: null` **and** the dispatch commit equals the prior
    fact's `commit_reviewed`, nothing was committed since — take the working-tree branch. The
    existing comment block enumerates one direction of this problem carefully and misses its
    mirror image; extend it to name both, so the next reader sees a pair rather than a case.
  - `tests/test_critic_consolidate.py` — the dirty-tree-anchor case, red-verified: prior fact
    with `head_commit: null`, unchanged HEAD, and an assertion that the interval runs
    `base → head` **forward** (the prior fact's `head_tree` as base, the captured working tree as
    head), not swapped. Include the mirror case the existing comment already protects — a
    vouching commit that changes no content — so the fix cannot be made by breaking it.
- **Tests:** unit — the four-way matrix over (prior fact clean/dirty) × (commit landed / not);
  regression — the vouching-commit case from the existing comment must still take the
  working-tree branch. Mock the filesystem and subprocess per the project's coverage preference.
- **Acceptance criteria:** `pytest -q` passes; the manual repro in § Verification Strategy
  produces a forward interval where it previously produced a swapped one; no fact schema field
  is added, removed, or retyped.
- **Done when:**
  1. Acceptance criteria met and tests pass, each new guard red-verified
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and the change-log entry tagged `scope=silent-gates`

`[DECISION: the wrongly-anchored resolution facts already in the ledger are left in place | the
data-model norm says facts are immutable and append-only — a state change is a new fact, never an
edit; rewriting history to make the ledger look correct would break the one property that makes
the ledger evidence at all, and the affected review (rev-20260802T191628Z-ddd15904, drift-burndown
Chunk 02) has since been superseded by a clean cumulative and a 0/0/0 verify on the same branch |
user can override and ask for a corrective fact to be appended instead]`

### Chunk 02: Direction detection — a heading is not a registry, and its absence is not health (#567)

- **Description:** Two defects in `plugin/lib/norm_probes.py`, pulling in opposite directions and
  both rooted in treating a `## Direction` **heading** as proof that a norm registry exists.
  *Defect 1:* `_has_direction_heading` matches on heading text alone, so a section with no entries
  under it satisfies `probe_norm_registry_unratified`'s first arm — a repo whose only `## Direction`
  section was a roadmap of undone work certified as a ratified registry, and doctor check #10 would
  have reported findings against that roadmap indefinitely. *Defect 2:* `_any_direction` gates
  `probe_norm_health_sweep_overdue`, and `_direction_lines` starves `probe_dead_why` and
  `probe_stalled_transition`, so a repo that homes its norms entirely in the preferences
  Enforcement table — a legitimate homing under `docs/norms.md` § Where Norms Live — gets **no
  time-domain norm audit at all, ever, with no signal that it is missing.** The field session hit
  both in sequence, the second while fixing the first: renaming the misleading section would have
  silenced all three probes permanently, in the same commit that created the norm those probes
  exist to audit.
- **Depends on:** none (independent of Chunk 01; ordered second because Chunk 01 is the unsound one)
- **Artifacts consumed:** `architecture.md` § Direction (advice fails soft; never silently passed),
  `nonfunctional-requirements.md` § Direction (observable yield; session-start hot path),
  `docs/norms.md` § Anatomy of a Norm, § Where Norms Live
- **Deliverables:**
  - `plugin/lib/norm_probes.py` — a Direction-**entry** predicate distinct from the existing
    heading predicate: an entry is a `Why:`-bearing logical line inside a `## Direction` section,
    which `_direction_lines` already yields (it excludes heading lines and joins soft-wraps, so
    the required `Why:` is reachable without new parsing). `probe_norm_registry_unratified`'s
    first arm keys on the entry predicate instead of the heading predicate.
  - `plugin/lib/norm_probes.py` — a norms-exist-by-**either**-homing predicate replacing
    `_any_direction` at the `probe_norm_health_sweep_overdue` guard: Direction entries **or**
    norm rows in the preferences Enforcement table. The table is already located by
    `_norm_index_lacks_columns` via its `Preference`-prefixed header row; the new reader answers
    "does it carry a populated norm row", reusing that location rather than re-deriving it.

    **Corrected 2026-08-03, before building.** This deliverable originally also said to "close
    `probe_dead_why` and `probe_stalled_transition` on the same predicate." That is incoherent: a
    predicate answers *whether* norms exist, and those two probes are starved for want of *lines to
    scan*, not for want of a guard — no predicate can feed them. The plan was written from #567's
    Problem section without reconciling it against the issue's own Scope section, which already
    settles it: *"The janitor sweep already covers table rows, so the **coverage** exists; only the
    **reminder** is gated on a heading."* So the single guard is the whole fix, and those two probes
    correctly need nothing. What remains true is that a table-homed repo gets no *probe-level*
    dead-why or stalled-transition signal — that is the janitor sweep's job, and the sweep is what
    the restored reminder sends you to.
  - `tests/test_norm_probes.py` — red-verified cases for both defects: a roadmap-only Direction
    section (arm (a) must fire), a Why-bearing entry (arm (a) must stay quiet), a repo with zero
    Direction headings but populated Enforcement norm rows (the sweep reminder reachable), and a
    repo with neither homing (legitimately quiet — the fix must not turn a genuine
    absence into a nag).
- **Tests:** unit — the homing matrix (Direction entries / Enforcement rows / both / neither)
  × the sweep reminder, plus the arm-(a) entry-vs-heading pair. The "neither" row is the one that
  keeps this from becoming an over-fire, and it is the case a careless fix breaks.
- **Acceptance criteria:** `pytest -q` passes; the two scratch-repo exercises in § Verification
  Strategy behave as described; a repo with no norms under either homing still sees nothing.
- **Done when:**
  1. Acceptance criteria met and tests pass, each new guard red-verified
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and the change-log entry tagged `scope=silent-gates`

### Chunk 03: The mechanical tail — one encoding default, one interpreter (#562, #154)

- **Description:** Two independent one-site fixes, batched because neither justifies a chunk and
  both are the same class — a runtime assumption that is invisible where it was written and wrong
  elsewhere. *#562:* `core.atomic_write_text` writes at `locale.getpreferredencoding(False)` while
  every reader opens `encoding="utf-8"`; on a non-UTF-8 locale the round trip is lossy and
  non-ASCII raises `UnicodeEncodeError` at the write. *#154:* the audit-learnings sentinel runner
  spawns a hardcoded `python3`, so under a venv every learning sentinel falsely reports failing.
- **Depends on:** none
- **Artifacts consumed:** `project-preferences.md` (subprocess safety — list args, never
  `shell=True`; UTF-8 decoding convention), `architecture.md` § Direction (Python-runtime
  assumptions)
- **Deliverables:**
  - `plugin/lib/core.py` — `atomic_write_text`'s `encoding` parameter defaults to `"utf-8"`
    rather than `None`. **Verified safe across all seven call sites before the change is made:**
    five write JSON at `ensure_ascii=True` (ASCII either way), `learnings_obligation.repair`
    already passes `encoding="utf-8"` explicitly, and `briefing.py`'s `.session-handoff.md` write
    is the live latent bug — that file routinely carries em-dashes. `newline` stays `None`:
    line-ending translation is a separate concern with one deliberate opt-out, and flipping both
    at once would bundle an unrequested change. The docstring currently forward-references this
    issue ("`#562` tracks making utf-8 the default"); that sentence describes the old state and
    is removed with it.
  - `plugin/lib/audit_learnings_cmd.py` — the sentinel runner's argv uses `sys.executable` in
    place of the literal `"python3"`, matching the convention already applied elsewhere under
    `plugin/`. List-form args are preserved; no shell.
  - `tests/test_audit_learnings.py` — the sentinel runner spawns the running interpreter, asserted
    against `sys.executable` rather than a hardcoded name.
  - `tests/` — an `atomic_write_text` round-trip carrying non-ASCII content under a forced
    non-UTF-8 locale preference, red-verified against the current default.
- **Tests:** unit — non-ASCII round trip through the shared writer; the explicit-`encoding`
  caller still gets what it asked for; the sentinel runner's argv[0]. Mock subprocess and the
  filesystem per the coverage preference.
- **Acceptance criteria:** `pytest -q` passes; no caller's observable output changes except the
  two bugs being fixed.
- **Type:** cumulative-final
  <!-- Last chunk: its review IS the one `/prawduct:critic cumulative` over
       merge-base..HEAD — commit first, run it once, no separate `final`. -->
- **Done when:**
  1. Acceptance criteria met and tests pass, each new guard red-verified
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. The change-log entry tagged `scope=silent-gates`

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic review passes — per-chunk commit is
what scopes `chunk`-mode reviews, and batching would give the mid-plan reviews an unbounded diff.
Chunk 03's `cumulative` makes the branch PR-ready; `/prawduct:pr create` runs when the user asks.

**Sync base before reviewing, not after.** The predecessor branch paid a full extra cumulative
round for the opposite order: the review passed, the PR reviewer then found a `change-log.md`
conflict with `develop`, and merging `develop` moved the coverage graph's start node so the whole
composed chain went `uncovered`. Filed as #565 against `/prawduct:pr` itself; until that lands,
this plan does it by hand — check `develop` before Chunk 03's cumulative, not after it.

- After Chunk 01: confirm the interval fix composes with the gates that read the resulting facts
  (`check-cumulative-critic`, the Stop-hook gate) before widening into the probe work.
- After Chunk 02: confirm the widened guard has not turned a genuine absence of norms into a
  standing nag — the "neither homing" case is the one to look at.
- After Chunk 03 (cumulative): full-bundle review; confirm the encoding default did not change
  any caller's bytes except the two intended.
