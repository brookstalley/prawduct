---
artifact: build-plan
version: 2
scope: ephemeral-worktrees
depends_on: []
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews — enforced at the mutation site, not by tool-restriction alone → **conforms, and this plan is the same pattern one invariant over.** CRT-3X9D guards *who* may write during a review; this guards *where* a write lands when the tree is disposable. Both refuse at the mutation site because the boundary that produced the bad context (a subagent's tool restrictions there, the harness's worktree seeding here) is not something prawduct controls"
      - "authority fails closed; advice fails soft → **conforms, and it decides Chunk 01's central question.** The refusal set is an allowlist of *reads*, so a command added later defaults to refused-inside-an-ephemeral-worktree rather than silently stranding its write. This deliberately inverts the `_DATA_PLANE_COMMANDS` precedent, whose DECIDED comment chose the permissive default; the asymmetry that justified it there is reversed here because the guard fires only inside `.claude/worktrees/agent-*`, so an over-refusal costs one env var while an under-refusal costs the exact silent strand this plan exists to close. Recorded as a divergence, not an oversight — see [DECISION] under Chunk 01"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state, the shared evidence store, and the files it must reconcile → **conforms by subtraction.** Every chunk removes or refuses a write; none adds a target"
      - "prawduct is written in Python and must never be specific to Python → **inapplicable because no chunk touches per-language dispatch.** The predicate reads git and path structure, both language-neutral"
      - "goals and verification bind; prescribed method is advice → conforms. The `Deliverables` lines below were written from reading the sites, not from writing the fix; the Acceptance criteria and the read-only-allowlist posture bind, the routes do not"
      - "every fact has one home; every other mention is a reference to it → **conforms, and it dictates where the predicate lives.** `is_ephemeral_worktree` goes in `gitstate.py` beside `resolve_project_dir` — one home — so issue #221's guard composes with it instead of re-deriving the same detection. No chunk restates the detection signals in a second place"
      - "local-first governance, no network in the governance runtime → conforms; no chunk adds a network call or dependency"
      - "prawduct guides and reviews; it never implements → inapplicable because every chunk edits the framework's own runtime and methodology, not a product's code"
  - artifact: data-model
    dispositions:
      - "governance verdicts are computed from the append-only fact ledger, never from mutable model-written state — no model sits in a fact's write path → **conforms.** Chunk 02 adds a *reader-side classification*; it writes no fact and changes no verdict"
      - "facts are immutable and append-only; a state change is a new fact, never an edit in place → **conforms, and it is why Chunk 02 classifies on read.** Facts already written from ephemeral worktrees stay in the ledger untouched; provenance is derived from the `actor.worktree` they already carry"
      - "derived views are disposable and never authoritative — no gate reads a view to reach a verdict → **conforms, and Chunk 02 must not weaken it.** The ephemeral count is reported by `evidence status`/`list` only. No gate consumes it, and no fact is filtered out of the coverage algebra — tree-keying already makes an ephemeral fact cover nothing, so suppressing it would change gate behaviour rather than describe it"
      - "a fact written by a newer schema than the reader is a loud block, never silently dropped → **inapplicable because no chunk changes the fact schema.** Provenance is read from `actor.worktree`, a field schema 1 already carries, so no version moves"
      - "two stores, two lifetimes: shared committed answers distinct from per-clone gitignored nags → conforms; no chunk moves state between them"
      - "`backlog_service_repo` selects the authoritative backlog store → conforms as process: this work's item was filed and triaged through `/prawduct:backlog` against `brookstalley/prawduct` (#594); the frozen markdown was never consulted"
  - artifact: nonfunctional-requirements
    dispositions:
      - "no probe or gate on the hot path may block or noticeably delay session start → **binds Chunk 01 and constrains the implementation.** The guard runs pre-dispatch on *every* `prawduct-hook` invocation, `clear` and `stop` included. The predicate is therefore ordered so the pure-string path test gates the git probe: a worktree not under `.claude/worktrees/` returns `None` having spawned no subprocess, which is every session outside an agent worktree"
      - "proportionality ratchets both ways — a control names the yield it expects and emits it observably → **EXCEPTION, recorded (was wrongly claimed as conformance).** The yield arm is NOT satisfied: the refusal reaches stderr inside a worktree that is then deleted, and its escalation (\"report this in your final message\") is model-mediated, so nothing countable survives for the janitor Norm Health sweep to retire the guard on. **Trigger to close:** the first time anyone asks whether this guard has ever fired. **Discharge then:** append a firing fact to the shared evidence store, which outlives the worktree via `<git-common-dir>` — the same property Chunk 02 relies on to classify ephemeral facts at all. Deferred now because a control that writes evidence from its own refusal path needs its own design pass, not a line in this one. **Class, not instance:** `_check_binary_skew` (#227, also post-2026-07-29) has the identical shape, so one fix should route through both pre-dispatch guards"
      - "review wall-clock is a P0 constraint → **conforms, and Chunk 02 defends it.** A `/prawduct:critic` run inside an agent worktree spends full review unit-cost on a fact that covers nothing; naming those facts is what makes that waste visible"
      - "state-file growth past its threshold is an advisory warning, never a hard block → inapplicable because no chunk changes a state file's size posture"
last_validated: 2026-08-05
---

## Requirements Confidence

**Level:** High

**Why:** The problem arrived as a field bug report with measured evidence rather than a
hypothesis (issue #594), and every claim in it was re-verified against this checkout before
this plan was written — including three that turned out to be **wrong**, each of which
changed the design rather than merely being noted. Problem, success and scope are each
statable in one sentence.

**Open assumptions / unknowns:**

- `[ASSUMPTION: EnterWorktree's generated worktree names are not shaped like agent-<hex> | HIGH impact | mechanically bounded]`
  — `EnterWorktree` creates its worktrees under the same `.claude/worktrees/` parent as
  Agent-tool isolation, and generates a random name when none is given. Its exact name
  format is undocumented and was not observable from this session. A collision would make
  the guard refuse governance writes in a **legitimate, user-requested, long-lived session
  worktree** — the worst outcome available to this change. Bounded three ways rather than
  assumed away: the predicate requires the literal `agent-` prefix plus a hex tail (not a
  bare `.claude/worktrees/` ancestor, which is what the source report proposed and which
  would have false-positived on every EnterWorktree session); the refusal always prints its
  override; and Chunk 01's tests pin the negative case for a plausibly-named EnterWorktree
  worktree. If the assumption is ever falsified the failure is loud and one env var wide.
- `[ASSUMPTION: the read-only allowlist is complete as of this plugin version | MED impact | verified per command, not inferred]`
  — Chunk 01's fail-closed posture means a read command omitted from the allowlist starts
  refusing inside agent worktrees. Each membership is to be established by reading that
  command's implementation for a write, never from the command's name — `verify-*` and
  `learnings-obligation` in particular have write-bearing ops whose names read as pure reads.

**What would raise confidence:** an observed `EnterWorktree` worktree name (resolves the
first assumption outright). Not blocking — the assumption's failure mode is loud and
overridable, and the bound holds without it.

## Status

- [ ] Chunk 01: The ephemeral-worktree predicate and the pre-dispatch refusal
- [ ] Chunk 02: Evidence facts carry visible worktree provenance
- [ ] Chunk 03: Delegation guidance states the snapshot and the shared index
Context: Built 2026-08-05 from issue #594, on `fix/ephemeral-agent-worktrees` off
`develop@b994bfa`. Chunk 01 committed (`5fd2f45`), reviewed clean. Chunk 02 built and
reviewed. Chunks 02-03 committed (`493b5e0`). Status checkboxes stay `[ ]` on purpose —
`views_enabled` regenerates them at the develop→main promotion, not at merge.
Next: the `cumulative` review Chunk 03's `Type: cumulative-final` owes.

Dispatch note: pass `--scope ephemeral-worktrees` to `/prawduct:critic` on this branch. The
branch name does not name the scope, so record-lint otherwise resolves the graded plan from
the `active_build_plan` pointer and reports that assumption on every dispatch.

Sibling work in flight: `documentation/issues/221-requirements.md` (landed on `develop`
this morning) specifies a *different* guard for a *different* predicate — a cross-worktree
mismatch, needing a session-scoped persisted marker (WT1-WT6). This plan's predicate ("this
worktree is disposable") is true of the session's correctly-resolved active worktree and
needs no persisted state. The two compose; this plan satisfies none of WT1-WT5 and must not
be read as preempting that design. Its only obligation to #221 is to put the predicate in
`gitstate.py`, the module WT1 names as the choke point.

## Build Chunks

### Chunk 01: The ephemeral-worktree predicate and the pre-dispatch refusal

- **Description:** Give prawduct a representation of "this worktree is disposable," and
  make every AGENT-invoked `.prawduct/`-mutating command refuse loudly inside one.
  Harness-invoked commands (`clear`, `stop`, `subagent-stop`, `user-prompt-submit`,
  `build-index`) are deliberately exempt — their writes DO strand here, but refusing one
  breaks the session rather than protecting it, and the exposure is bounded upstream:
  `critic-begin` is refused, so no review can be active for a `subagent-stop` to
  consolidate. Stated because an undocumented carve-out reads as an oversight.
  Converts a silent
  strand — an agent correctly following `/prawduct:backlog` whose entry dies at merge —
  into a self-explaining stop that names the override.
- **Depends on:** none
- **Artifacts consumed:** issue #594; `documentation/issues/221-requirements.md` (WT1's
  choke-point reasoning, adopted for placement only)
- **Deliverables:** `is_ephemeral_worktree` in `plugin/lib/gitstate.py`, beside
  `resolve_project_dir`; `_check_ephemeral_worktree` in `plugin/bin/prawduct-hook`, invoked
  pre-dispatch in `main()` immediately after `_check_binary_skew`; a read-only command
  allowlist with per-op sets for the mixed commands (`backlog`, `advisory`, `evidence`,
  `test-evidence`, `handoff`, `learnings-obligation`); `PRAWDUCT_ALLOW_EPHEMERAL_WRITES`
  override; new `tests/test_ephemeral_worktree.py`
- **Added during build** (scope evolved; recorded here per "Persist plans immediately"
  rather than left in the diff): **(a)** the HEAD-snapshot NOTE on *allowed* commands.
  Symptom 1 was assigned to Chunk 03's prose, but prose only reaches an agent that was told
  to read it — and the file the delegation instruction names does not exist in an isolated
  worktree. The hook is the only channel that reaches such an agent with no cooperation from
  its dispatcher. One static line, no git probe, so it stays distinct from the scoped-out S3
  staleness comparison, which needs one. **(b)** backend-awareness for `backlog`: on the
  Issues backend a backlog write is a network call that outlives the worktree and therefore
  cannot strand, so refusing it would be exactly the false refusal this plan's Requirements
  Confidence names as the worst outcome available.
- **Tests:** unit — the predicate against real `git worktree add` trees: an `agent-<hex>`
  worktree (positive), a `wf_*` workflow checkout (positive), a plausibly-named
  EnterWorktree-style worktree under the same `.claude/worktrees/` parent (**negative — the
  regression this plan's central correction exists to prevent**), a named sibling worktree
  outside it (negative), the primary checkout (negative), a non-git directory (negative,
  no raise); unit — the predicate spawns no subprocess when the path test fails (the
  hot-path norm, asserted rather than assumed); integration — a write command refuses
  non-zero inside an agent worktree, a read command does not, a harness-invoked command
  does not, and the override reverses the refusal
- **Acceptance criteria:** `prawduct-hook backlog file …` run inside an `agent-<hex>`
  worktree exits non-zero naming the worktree, the consequence, and the override, and writes
  nothing; the same command in a `.claude/worktrees/<name>` worktree that is *not*
  agent-shaped runs normally; full suite passes
- **Critic mode:** chunk
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

`[DECISION]` **Fail-closed here, against the fail-open precedent 40 lines up.**
`_DATA_PLANE_COMMANDS` carries an explicit DECIDED comment choosing an allowlist of *writes*
— permissive default — on the grounds that "the read-only set is the larger, faster-moving
one," so a restrictive default would silently break new report commands "inside every
framework checkout." That reasoning is sound where it sits and does not transfer: the binary
skew guard fires in every framework checkout, whereas this one fires only inside
`.claude/worktrees/agent-*`. Getting the restrictive default wrong there costs one command's
worth of loud, overridable refusal inside a disposable tree; getting the permissive default
wrong costs a silently stranded governance write, which is the defect under repair. The
alternative was rejected on that reversed asymmetry, not by overlooking the precedent.

### Chunk 02: Evidence facts carry visible worktree provenance

- **Description:** A `/prawduct:critic` run inside an agent worktree spends full review cost
  on a fact that covers nothing, and today reads in `evidence status` exactly like a review
  that covers the branch. Name them. Tree-keying already makes them cover nothing — this is
  the false-reassurance half, not a correctness fix.
- **Depends on:** Chunk 01 (reuses the predicate)
- **Artifacts consumed:** `plugin/lib/evidence.py` (the `actor.worktree` field, schema 1)
- **Deliverables:** provenance classification in `plugin/lib/evidence.py` derived from the
  `actor.worktree` path each fact already carries; the count surfaced in `evidence status`
  and `evidence list`; tests in `tests/` alongside the existing evidence suite
- **Added during build** (same convention as Chunk 01): the per-fact predicate
  `is_ephemeral_fact` is public rather than internal, so `evidence list` marks rows by
  asking about a fact instead of matching `id()` against a set built by another call —
  correct only while both sides hold the same dict objects, silently wrong the moment
  anything normalizes one. Two edits belonging to Chunk 01 also landed here, recorded
  rather than left in the diff: a comment correction in `plugin/bin/prawduct-hook` (Chunk 01
  justified `verify-migration` as read-only "because it takes no `project_dir`", which
  `export`/`restructure-preview` falsify), and the extraction of `_hook_env` in
  `tests/test_ephemeral_worktree.py` after a hand-built subprocess env drifted vacuous a
  second time. `gitstate.is_ephemeral_worktree` was also reordered to run its
  `.claude/worktrees` ancestor test once instead of twice — behaviour-identical, and it
  now shares `_EPHEMERAL_DIR_PATTERNS` with `ephemeral_worktree_kind_of_path` rather
  than delegating to it.
- **Tests:** unit — a store containing facts from an agent worktree, a workflow checkout and
  a normal worktree reports the ephemeral count and leaves the fact list unfiltered;
  unit — no gate's composed coverage changes in the presence of ephemeral facts (the
  derived-views norm, asserted directly)
- **Acceptance criteria:** `prawduct-hook evidence status` reports the ephemeral-origin
  count distinctly and states that those facts cover no branch; no schema version moves; no
  gate verdict changes
- **Critic mode:** chunk
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: Delegation guidance states the snapshot and the shared index

- **Description:** The methodology recommends both worktree-isolated and shared-worktree
  subagents while stating neither's hazard, and — in the same paragraph — sends every
  subagent to a file that does not exist in an isolated worktree. Fix all three.
- **Depends on:** Chunks 01-02 (the guidance describes shipped behaviour, so it lands last)
- **Artifacts consumed:** `plugin/methodology/building.md` §§ "Delegating Work to
  Subagents", "The Build Cycle" (Persist plans immediately)
- **Deliverables:** in `plugin/methodology/building.md` — the dangling
  `.prawduct/.subagent-briefing.md` instruction corrected (the file is gitignored and
  force-untracked, so it is absent from every worktree-isolated subagent); HEAD-snapshot
  semantics and the prompt-outranks-the-file rule; the do-not-write-`.prawduct/` rule with
  its now-mechanical backing; the shared-index pathspec rule (`git add <paths>` does not
  scope the `git commit` that follows); a cross-reference from "Persist plans immediately",
  the instruction that manufactures the uncommitted-artifact state in the first place
- **Tests:** none — prose. Covered by the structural doc suite already asserting
  `building.md`'s shape
- **Acceptance criteria:** the delegation section names both hazards and points at no
  nonexistent file; full suite passes
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic review passes. Chunk 03's
`cumulative` review makes the branch PR-ready; `/prawduct:pr create` runs when the user asks.

- After Chunk 01: confirm the predicate's negative cases before anything else composes with
  it — a false positive here silences governance in a legitimate worktree, which is strictly
  worse than the bug being fixed.
- After Chunk 03 (cumulative): full-bundle review.

## Scope-out

- **The staleness warning** (source report's S3): warn when an agent worktree's HEAD is
  behind the branch it forked from and governing artifacts differ. Deferred — it needs a git
  probe on every hook invocation, which the hot-path norm makes a design question rather
  than an implementation detail. Filed on #594.
- **Upstream Claude Code asks** (source report's S6): an env var identifying an agent
  worktree *and its dispatcher*, and a documented guarantee about seed-from-HEAD semantics.
  Both would make this predicate exact rather than pattern-matched. Filed on #594; prawduct
  does not block on them.
- **Issue #221's cross-worktree mismatch guard** (WT1-WT6) — a different predicate needing a
  session-scoped marker. Explicitly not started here.
