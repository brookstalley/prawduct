---
artifact: build-plan
version: 2
scope: instruction-surface-truth
branch: fix/instruction-surface-truth
depends_on: []
governed_by:
  # Seeded by reading each artifact's `## Direction` section directly (the `jurisdiction`
  # subcommand produced no output on this tree). Four artifacts carry Direction norms that
  # could bind a batch of instruction-surface corrections; three of them do.
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0; cost = unit-cost x run-count, both levers -> conforms, and
        Chunk 04 acts on the unit-cost lever directly: `skills/critic/SKILL.md` is payload every
        Critic mode loads and it carries no ceiling, so nothing today would notice it growing.
        Run-count: the whole batch takes ONE `cumulative` review rather than four chunk reviews
        (`Critic mode:` below), because the four chunks are independent single-file corrections
        with no shared design surface for a per-chunk review to protect."
      - "proportionality ratchets both ways — a new control names its expected yield AND emits it
        observably -> conforms. This batch adds four mechanical checks and each names its catch at
        the pin: the grant/instruction pin (Chunk 01) catches a skill instructing a command it may
        not run; the `${CLAUDE_PLUGIN_ROOT}` pin (Chunk 01) catches a prose read that cannot
        resolve; the adapter-surface pin (Chunk 02) catches the `--help` referent going missing
        again; the SKILL.md ceiling (Chunk 04) catches unbudgeted payload growth. All four are
        assertions inside test files that already exist for exactly this class — no new control
        surface, no new advisory, nothing added to the hot path."
      - "state-file growth is an advisory warning, never a hard block -> conforms; the standing
        briefing nags (`project-state.yaml` 41KB, `learnings.md` 91KB) are deliberately untouched.
        Compaction is its own work and folding it into a defect batch is what the advisory posture
        exists to avoid."
  - artifact: api-contract
    dispositions:
      - "whole-surface semver on the plugin; the internal CLI subcommand surface carries no
        per-subcommand version -> conforms. Chunk 02 adds `--help` output to existing backlog
        subcommands and changes no flag name, no exit-code meaning and no `--json` key."
      - "exit codes are the contract; errors are attributed, never raised as stack traces ->
        conforms, and Chunk 02 REPAIRS an instance: `--help` currently exits 2 `unknown flag`,
        which is an exit code carrying the wrong contract. It becomes usage on stdout at exit 0."
      - "additive-first evolution: flags are added, never repurposed -> conforms. `--help` is
        additive; nothing existing changes meaning."
      - "deprecation is signalled, never silent -> inapplicable because this plan deprecates
        nothing."
  - artifact: architecture
    dispositions:
      - "authority fails closed; advice fails soft -> conforms. Every check this batch adds is a
        test assertion (CI authority, fails closed at the right place); no advisory is added and
        no session-time behaviour changes."
      - "local-first; which call sites may egress is enumerated in this artifact ->
        inapplicable because no chunk adds or moves an egress call site. Chunk 02 touches
        `lib/backlog/cli.py` argument parsing only, not `transport.py`."
partition: >-
  delegated, four ways, at the user's explicit request ("use subagents ... and solve them",
  Principle 23). The partition is drawn by FILE TREE rather than by theme, because the delegates
  share one working tree: Chunk 01 owns `plugin/skills/{doctor,janitor,runbook,pr}/`, Chunk 02
  owns `plugin/skills/backlog/` + `plugin/lib/backlog/`, Chunk 03 owns the `.prawduct/` records
  and `documentation/release-process.md`, Chunk 04 owns `.prawduct/artifacts/api-contract.md` +
  `tests/test_v5_methodology.py`. Two items that theme together were deliberately NOT put in
  different chunks for that reason — #219 is a `pr/SKILL.md` prose defect and sits with the skill
  chunk, not the docs chunk, because Chunk 01 already edits that file's frontmatter for #174.
  The delegates do the build half only: no commits, no `.prawduct/` bookkeeping, no full suite,
  no Critic. This session owns integration, the combined run, the review and all governance.
Critic mode: cumulative-final
last_validated: 2026-08-23
---

## Requirements Confidence

**Level:** High

**Why:** Every item in this batch is an already-triaged backlog issue at `stage:ready` (except
#583 and #175, which are at `ready` too — verified on the tracker) carrying its own
Problem / Repro / Actual / Expected / Evidence sections. Those sections **are** the requirement:
the problem is observable, the expected state is specific, and the evidence names the verified
sites. Nothing here is fast-moving or post-cutoff — every claim is checkable against this tree.

**The three questions, once for the batch:**

- **Problem:** eleven instruction surfaces — skill frontmatter, skill prose, adapter docs, process
  docs, contract artifacts and test comments — assert something about this system that is false or
  unresolvable. Each one is read by an agent as licence to act.
- **Success:** each surface states what is true, and where the class can regenerate, a test pins it
  so the next edit that reopens it fails in CI rather than in a consumer's repo.
- **Out of scope:** the *features* several of these items sit next to. #175 documents a retry
  budget; it does not build a retry loop. #699 corrects the doc; #550 still owns the missing
  `closed-by` write path. #589 budgets `SKILL.md`; it does not relocate payload out of it.
  #178 name-anchors stale step references; it does not renumber the runbook.

**Open assumptions / unknowns:**

- [ASSUMPTION: the four delegates' file trees are genuinely disjoint, so a shared working tree is
  safe | MEDIUM impact | verified at integration by `git diff --stat` against the declared
  ownership boundaries] — the partition was drawn from the issues' `refs:` and verified by reading
  the tree, not from the issue text alone. The one near-collision found and designed around:
  `plugin/skills/backlog/migration-scrub.md` is Chunk 02's file and Chunk 01 needs to *assert*
  against it (#174's second leg), so Chunk 01 reads it and writes only its test.
- [ASSUMPTION: #178's acceptance query cannot literally return empty | LOW impact | resolved in
  Chunk 03 and reported honestly either way] — several stale references live in frozen records
  (`.prawduct/backlog.md`'s migration snapshot, `artifacts/archive/`,
  `migration-restructure-plan.json`), which CLAUDE.md exempts as bookkeeping that records the
  work. The chunk fixes live durable prose and reports the refined query.

**What would raise confidence:** nothing cheaper than building it. Each item is small enough that
the fix is the investigation.

## Status

- [ ] Chunk 01: The skill surface says what it can run and points where it can read
- [ ] Chunk 02: The backlog adapter describes its own contract
- [ ] Chunk 03: Nine documentation claims stop being false
- [ ] Chunk 04: The exposed API and the unbudgeted payload are both accounted

Context: Batch drawn 2026-08-23 from the GitHub Issues backlog by scanning `effort:S` +
`stage:ready` for a single theme, on the user's "about 10 thematically aligned, high-ROI" ask.
Eleven items selected under one lens — **an instruction surface that misdescribes the runtime**.
Branched off `origin/develop` at `f1d78cc5`. The unrelated `fix/676-manifest-state-diagnosis`
branch (6 commits, reviewed clean, unpushed) is left intact and is NOT part of this plan.

## Scaffolding

### Build & Test Configuration

Nothing new. Python 3.10+, pytest via `pyproject.toml` (`-n 5 --dist loadfile`). No new
dependency, no new test file — every pin lands in a test file that already exists for its class.

### Verification Strategy

**Delegate ceiling** (`project-preferences.md` carries no `Delegate verification` row, so this
plan sets one): each delegate runs **only the test files it edits**, by path, and nothing else.
Rationale is the delegation guide's *unattributable green* — four agents each running the full
suite on one 10-core box under a `-n 5` config is four contended runs whose totals cannot be
attributed, and the coordinator has to run the suite once at integration regardless.

**Integration verification is this session's**, in this order: combined full suite → `git diff
--stat` against the declared ownership boundaries → one `cumulative` Critic → commit per chunk.

## Build Chunks

### Chunk 01: The skill surface says what it can run and points where it can read

- **Description:** Four defects in the non-backlog skill surfaces, all one class — the file tells
  an agent to do something the file itself makes impossible or ambiguous.
  - **#210** — `janitor/SKILL.md` instructs `prawduct-hook review-stats` and grants only the bare
    form (verified against the tree: the grant exists but carries no trailing `*` and has no
    `python3 plugin/bin/…` sibling). Audit the file for *every* hook subcommand it instructs and
    grant each in both invocation forms; `skills/backlog/SKILL.md:7` is the house precedent.
  - **#174** — `85753fd` narrowed `pr/SKILL.md`'s `Bash(gh *)` to `Bash(gh pr *)` and nothing
    asserts it, so restoring the wildcard leaves the suite green. Close the **class**: no bare
    `Bash(gh *)` in any skill frontmatter. Second leg, a missing test not a missing fix: every
    `--repo` in `skills/backlog/migration-scrub.md` is followed by `<target>`, and Step 6's
    cutover scalar reuses that bound value.
  - **#583** — `${CLAUDE_PLUGIN_ROOT}` does not expand in skill *prose* (it substitutes only into
    `hooks.json` commands). Every prose read through it hands the agent an unresolvable path.
    Repoint to the `${CLAUDE_SKILL_DIR}/../../…` form `doctor/SKILL.md:69` already uses. The
    issue enumerates the affected sites AND the not-affected ones — honour both lists.
  - **#219** — `pr/SKILL.md` tells a doc-only PR to "skip Steps 2, 2b, 3, and 4" and then to
    "jump straight to Step 5", and the two halves disagree about Step 1c, which is a STOP. One
    rule, skip-list and jump target agreeing.
- **Depends on:** none
- **Deliverables:** corrected frontmatter and prose in `plugin/skills/{janitor,pr,doctor,runbook}/SKILL.md`
  and `plugin/docs/runbook-authoring.md`; new assertions in `tests/test_skill_command_grants.py`
  and `tests/test_path_reference_resolution.py`
- **Tests:** `tests/test_skill_command_grants.py`, `tests/test_path_reference_resolution.py`
- **Acceptance criteria:** every hook subcommand any of these skills *instructs* is granted in
  both invocation forms, asserted by rule rather than by instance; no skill frontmatter carries a
  bare `Bash(gh *)`, asserted; no shipped skill prose instructs a read through
  `${CLAUDE_PLUGIN_ROOT}`, asserted, with the four documented non-sites untouched; a doc-only PR
  has exactly one reading of which steps it skips
- **Type:** bugfix
- **Done when:** acceptance criteria met · owned tests pass · handed back to the coordinator

### Chunk 02: The backlog adapter describes its own contract

- **Description:** Two items against the surface that bounds the model's backlog mutations.
  - **#175** — `adapter-mode.md` bounds the model with *"the adapter exposes exactly the ops in
    the usage table"* and **no usage table exists**. A bound that cannot be resolved is not a
    bound, and it fails in the worst direction: a model that cannot find the table falls back to
    its own notion of the op set. Four parts: (1) `--help` prints usage at **exit 0** — this is
    the missing referent, currently exit 2 `unknown flag`; (2) an explicit **retry budget** in the
    error-envelope docs — against a run of GitHub 503s a forked skill retried 23 times over 5+
    minutes, and the adapter is innocent (`transport.py` returns immediately, no retry loop), so
    it is the prose that failed to bound the model; (3) an explicit statement that the
    `prawduct:` block is **adapter-owned** and hand-writing one is prohibited; (4) all of it
    pinned in `tests/test_backlog_instruction_surface.py`.
  - **#699** — `adapter-mode.md` says a close "records `closed_by` natively", which reads as
    covering `update`'s `closed-by=<scope>` argument. It does not: `_run_status` parses only
    `{"repo", "to"}`, and `core.py`'s `set_status` docstring already records the deferral. Correct
    the doc to state the scope is not recorded and where it should go. #550 owns the write path;
    do not build it.
- **Depends on:** none
- **Deliverables:** `plugin/skills/backlog/adapter-mode.md` corrected on both counts;
  `--help` implemented in `plugin/lib/backlog/cli.py`; new assertions in
  `tests/test_backlog_instruction_surface.py`
- **Tests:** `tests/test_backlog_instruction_surface.py`, `tests/test_backlog_cli.py`
- **Acceptance criteria:** `prawduct-hook backlog <op> --help` prints that op's usage on stdout
  and exits 0, for every op; the sentence that cites a usage table names a referent that resolves;
  the retry budget states max attempts *and* a give-up rule; block ownership is stated as a
  prohibition; the `closed_by` claim matches `_run_status`'s actual flag set
- **Type:** bugfix
- **Done when:** acceptance criteria met · owned tests pass · handed back to the coordinator

### Chunk 03: Nine documentation claims stop being false

- **Description:** Three items, nine verified-false claims in durable prose.
  - **#204** — `documentation/release-process.md` omits three prep steps that get rediscovered
    every release: `pyproject.toml` carries a version and went stale at `3.0.3` through three
    releases; `CHANGELOG.md` is what the version-delta banner actually reads and is named nowhere;
    `active_build_plan` is never cleared, so the shipped tree misdirects every session opening
    against it. Cross-link the CHANGELOG half rather than duplicating it.
  - **#178** — the migration-scrub runbook was renumbered 0–5 → 0–6 and the citing references are
    stale. **Name-anchor them, never renumber** — several point at a `2c` the runbook has no
    lettered sub-steps for, so the obvious fix produces a differently-wrong pointer that looks
    right. The closure condition is a query that returns empty, not a count.
  - **#190** — five single-line corrections, each independently verified: (a) a change-log entry
    names the wrong function among four; (b) three prose pins under `tests/preferences/` landed
    and the norm index's Enforcement table gained rows for two; (c) a concerns cell names a build
    plan that will be deleted, in the same table as the ephemeral-ref firewall row it violates;
    (d) `cmd_clear`'s docstring keeps a quantifier its own change-log entry records as falsified;
    (e) a test comment says the clear hook is "excluded on compact" and it fires on compact now.
    The issue's Scope-out forbids one tempting non-fix for (e) — read it.
- **Depends on:** none
- **Deliverables:** `documentation/release-process.md`; name-anchored references at the live
  sites; the five corrections at their five sites
- **Tests:** none new — these are prose corrections at sites no test asserts. Where an existing
  test in `tests/preferences/` covers a touched claim, run it.
- **Acceptance criteria:** all three release-prep steps are in the process doc; the migration-scrub
  closure query is stated and its result reported honestly, with exempt frozen records named
  rather than silently skipped; all five #190 corrections landed, (b) as a roster row rather than
  a re-statement
- **Type:** bugfix
- **Done when:** acceptance criteria met · handed back to the coordinator

### Chunk 04: The exposed API and the unbudgeted payload are both accounted

- **Description:** Two items about a claim that is false because a set grew under it.
  - **#198** — the backlog-service build plan declares `prawduct-hook backlog` an
    **Exposed API** — the marker whose whole purpose is routing a chunk through versioning and
    error-model review — and `.prawduct/artifacts/api-contract.md` does not mention the surface.
    Add a section at the level the artifact uses for its other entries, stating the versioning and
    error-model position and **referencing** `documentation/backlog-service-api-contract.md` for
    detail; do not duplicate the detail, since duplication is a second drift source. The issue
    asks a second question in the same pass: is any *other* `**Exposed API:**` declaration
    likewise missing from the artifact? Answer it.
  - **#589** — `skills/critic/SKILL.md` is payload every Critic mode loads, it carries no
    `test_token_budget` ceiling and no `LAST_MEASURED_TOKENS` entry, and two comments in
    `tests/test_v5_methodology.py` assert a **closed set over an open one** ("no unbudgeted
    relocation target remains" / "the last payload file without one"). Both claims are false while
    SKILL.md is unbudgeted. The issue prefers remedy (2) and warns that doing only (1) reproduces
    the defect — a third ceiling makes the sentence true only until a sixth payload file appears.
    Do both: give SKILL.md a ceiling **and** replace the universal claim with the bounded fact.
- **Depends on:** none
- **Deliverables:** a backlog-surface section in `.prawduct/artifacts/api-contract.md`; a
  `skills/critic/SKILL.md` ceiling + `LAST_MEASURED_TOKENS` entry; both false comments replaced
- **Tests:** `tests/test_v5_methodology.py`
- **Acceptance criteria:** a reader asking "what does prawduct expose, and under what promise?"
  gets a complete answer from the artifact; the `**Exposed API:**` sweep's result is stated;
  `skills/critic/SKILL.md` has a ceiling whose reading is measured, not copied; neither remaining
  comment asserts a universal over a set that can grow
- **Type:** bugfix
- **Done when:** acceptance criteria met · owned tests pass · handed back to the coordinator
