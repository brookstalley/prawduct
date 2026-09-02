---
artifact: build-plan
version: 2
scope: learnings-v2-core
branch: feature/learning-system-v2
backlog: brookstalley/prawduct#744
depends_on:
  - artifact: learning-system-v2-discovery
  - artifact: learning-system-audit-2026-09-01
governed_by:
  - artifact: data-model
    dispositions:
      - "verdicts computed from facts, no model in the write path → conforms: the budget gate compares two byte counts against a declared number"
      - "facts immutable & append-only → inapplicable because this plan writes no ledger facts (Wave 2 adds the two events)"
      - "derived views never authoritative → conforms: the rules files ARE the record; nothing derives from them and nothing is derived into them"
      - "a governance document reaches a terminal state, never deleted; archival moves it → exception (owner-ruled 2026-09-02, audit §8.7): Chunk 05 deletes learnings-detail.md and learnings-history.md outright; git history is the archive and nothing will read them after Wave 2"
      - "every backlog write conforms to the title rules → inapplicable because this plan writes no backlog items"
      - "a fact written by a newer schema is a loud block → inapplicable because no facts are written"
      - "two stores, two lifetimes: committed answers vs gitignored nags → conforms: the rules files are committed answers; the UNMIGRATED directive is emitted at session start and stored nowhere"
      - "backlog_service_repo selects the authoritative backlog store → inapplicable because no reader of the backlog changes"
  - artifact: security-model
    dispositions:
      - "untrusted governance state (learnings included) is data, not instructions → conforms: the briefing line prints counts and sizes, never rule text; the migrate command copies content without interpreting it; the Critic reads the files as evidence"
      - "a destructive or irreversible operation requires owner approval at the operation level → exception (owner-ruled 2026-09-02, audit §8.7): the agent runs `learnings-migrate --apply` without a per-repo prompt because the operation is git-reversible (three tracked files, one commit), the dry run names every write and delete, and the command refuses on a dirty tree; the owner's control point is the migration commit"
      - "no upstream content egress → inapplicable because nothing in this plan sends anything off the repo"
  - artifact: observability-strategy
    dispositions:
      - "stable severity-prefix vocabulary with the stdout/stderr channel split → conforms: the Stop floor emits a `BLOCKED —` blocker on the existing channel; the briefing line uses the briefing; the migrate dry run reports on stdout"
      - "the ledger has a single writer → inapplicable because this plan appends nothing to the ledger"
      - "no prawduct-internal ids in operator-emitted text → conforms: the UNMIGRATED directive and the budget finding name files and commands, never ids"
partition: >-
  01 and 05 serial (coordinator). 02, 03, 04 delegated to three opus subagents in isolated
  worktrees, partitioned by FILE TREE because 02–04 share nothing but `bin/prawduct-hook`, where
  each edits one named function and one dispatch line and the coordinator merges. 02 owns
  `lib/learnings_migrate.py`, `cmd_learnings_migrate`, `tests/test_learnings_migrate.py` and its
  fixtures; 03 owns `lib/record_lint.py`, `templates/project-state.yaml`, `tests/test_record_lint.py`;
  04 owns `lib/briefing.py`, `cmd_stop`, `lib/gates.py`, the five Critic/PR prose files, and their
  tests. Precedent read: `build-plan-instruction-surface-truth.md` delegated four ways by file tree
  at the owner's request; the owner asked for multi-subagent execution here, so no approval round.
last_validated: 2026-09-02
---

## Requirements Confidence

**Level:** High

**Why:** Every requirement is numbered in the discovery (R1–R5, R11) with its proof; the harness
behaviour the layout depends on was verified against current docs on 2026-09-02; the code each
chunk extends was read before the chunk was drawn.

**Open assumptions / unknowns:**
[ASSUMPTION: directory is `.claude/rules/learnings/` (discovery D3) | LOW impact — a rename is one
constant | user can override]
[ASSUMPTION: the budget gate covers only `learnings/` files, not every rules file (D4) | LOW impact |
user can override]
[ASSUMPTION: `paths:` globs are root-relative and `**` spans directories (discovery §6) | MED
impact — the resolver's matcher must agree with the harness's, or a file the harness loads is
one the Critic does not read | user can correct]

[ASSUMPTION: a product may gitignore `.claude/` (common), which would make `resolve()` report
`new` from an untracked, never-committed rules tree | MED impact — Critic finding, Chunk 01 final
review 2026-09-02 | disposition: guarded in Chunk 02 (migrate refuses an ignored destination) and
Chunk 04 (briefing names the ignored state); the resolver itself stays a pure filesystem reader]

**What would raise confidence:** one probe in Chunk 01 — a rules file with `paths: ["plugin/lib/**"]`
in this worktree, read a matching file, confirm the rule text arrives. Five minutes; do it before
writing the matcher.

## Status

- [x] Chunk 01: Resolver, layout and scaffold — the keystone every reader uses
- [ ] Chunk 02: `learnings-migrate` — lossless relayout of any fleet format
- [ ] Chunk 03: Budget gate — over-and-grew blocks the next addition
- [ ] Chunk 04: Detection, directive, Stop floor, and the cross-check re-pointed
- [ ] Chunk 05: Migrate this repo with its own command
Context: Plan drawn 2026-09-02 from discovery §8.2. Harness probe done 2026-09-02 (coordinator
session): a `.claude/rules/zz-probe.md` with `paths: ["plugin/lib/**"]` injected its rule text on
the first Read of `plugin/lib/onboarding_probes.py` — root-relative, `**` spans directories,
loaded lazily on the matching read; the §6 assumption holds. Chunk 01 done 2026-09-02 (03662deb;
final review rev-20260902T120140Z-ba4c090d + verify-resolutions rev-20260902T121546Z-91cf4260, clean).
02–04 dispatched together 2026-09-02 to three opus delegates (worktrees prawduct-w1a/w1b/w1c,
branches wave1/chunk02-migrate, chunk03-budget, chunk04-detect); coordinator merges each `--no-ff`
then reviews. 05 after all three are merged.

## Scaffolding

### Project Initialization

None — existing plugin. New module `plugin/lib/learnings_files.py`, new module
`plugin/lib/learnings_migrate.py`, new test files named per chunk.

### Dependencies

None added. Standard library only (`fnmatch` is not enough for `**`; the matcher translates
globs to regex itself — see Chunk 01).

### Build & Test Configuration

`uv run pytest -q` runs the suite (`-n 5 --dist loadfile` from `pyproject.toml`). A delegate's
ceiling is its own test files plus `tests/preferences/`: e.g. `uv run pytest -q
tests/test_learnings_migrate.py tests/preferences`. The coordinator runs the full suite at each
merge and records it with `prawduct-hook test-evidence record`.

### Scaffold Verification

`uv run pytest -q tests/test_learnings_files.py` passes after Chunk 01.

### Verification Strategy

Beyond tests, two live checks. After Chunk 01, the harness probe named under "What would raise
confidence". After Chunk 05, `/clear` in this worktree and confirm the briefing's learnings line
reads the new layout and nothing says UNMIGRATED. Chunk 02 additionally dry-runs the command
against a scratch copy of discodon's `.prawduct/learnings.md` (copied into the session
scratchpad, never the real repo) and reads the proposed map and the output sizes by eye — that
file is the fleet's hardest case and the fixture set is derived from it.

## Project Structure

```
plugin/lib/learnings_files.py      # resolver: layout state, file list, glob ∩ diff, scaffold  (01)
plugin/lib/learnings_migrate.py    # relayout: parse old formats → new files, map proposal    (02)
plugin/lib/record_lint.py          # + _check_learnings_budget                                (03)
plugin/lib/briefing.py             # learnings line: three states + directive; nudge removed  (04)
plugin/bin/prawduct-hook           # cmd_learnings_migrate (02); cmd_stop floor (04)
plugin/skills/critic/*.md, plugin/agents/critic-reviewer.md, plugin/skills/pr/review-protocol.md  (04)
tests/test_learnings_files.py, tests/test_learnings_migrate.py, tests/fixtures/learnings_migrate/
tests/preferences/test_learnings_single_resolver.py
```

### Module Boundaries

Every plugin reader of learnings goes through `learnings_files.resolve()`; no other module
names `learnings.md` or the rules directory. `learnings_migrate` is the one exception — it names
the legacy path because reading it is its job. The preference test in Chunk 01 pins this with an
allowlist that Wave 2 shrinks to the migrate module and `CHANGELOG.md`.

## Build Chunks

### Chunk 01: Resolver, layout and scaffold — the keystone every reader uses

- **Description:** The thin slice: one module answers "where are the rules, which state is this
  repo in, which files apply to these paths", and onboarding scaffolds the new layout. Built
  serially and reviewed `final` because 02–04 all read it.
- **Depends on:** none
- **Artifacts consumed:** discovery R1, R11, §6 assumptions; audit §8.3 (harness semantics)
- **Deliverables:**
  - new `plugin/lib/learnings_files.py`: constants `RULES_DIR_REL = ".claude/rules/learnings"`,
    `CORE_NAME = "core.md"`, `LEGACY_REL = ".prawduct/learnings.md"`, `CORE_HEADER` (title plus
    the two-sentence descent obligation: reading a rule is not applying it; name the rule you
    applied or the reason you did not). `parse_frontmatter(text) -> tuple[list[str], str]` for
    the YAML subset the harness documents (`paths:` as a block list or inline list, quoted or
    bare, brace expansion `{a,b}` expanded here). `glob_to_regex(pattern) -> re.Pattern`
    (`**/` → `(?:.*/)?`, `**` → `.*`, `*` → `[^/]*`, `?` → `[^/]`, anchored, forward-slash paths,
    root-relative). `@dataclass Layout(state, core, areas, files)` with `state` one of
    `new | legacy | both | none` and `areas: list[AreaFile(path, globs)]`.
    `resolve(project_dir) -> Layout`. `files_for_paths(layout, changed) -> list[Path]` — core
    first, then every area with any glob matching any changed path, in name order.
    `scaffold_core(project_dir) -> Path` writes `CORE_HEADER` when the file is absent, never
    overwrites.
  - `plugin/lib/init_product.py`: scaffold new `.claude/rules/learnings/core.md` via
    `scaffold_core`; stop writing `.prawduct/learnings.md`; drop the `learnings_obligation`
    import (the module stays until Wave 2 deletes it).
  - `plugin/lib/onboarding_probes.py`: expect `core.md`, not `learnings.md`.
  - new `tests/test_learnings_files.py`; updates to `tests/test_plugin_init.py`,
    `tests/test_onboarding_probes.py`.
  - new `tests/preferences/test_learnings_single_resolver.py`: no non-test file under
    `plugin/` contains the string `learnings.md` except an explicit allowlist. The allowlist at
    this chunk is every Wave-2 deletion site (discovery R6) plus `learnings_migrate.py` and
    `CHANGELOG.md`; each entry carries the wave that removes it.
- **Tests:** unit — frontmatter parse (block list, inline list, quoted, brace expansion, absent);
  glob matcher against the harness doc's own table (`**/*.ts`, `src/**/*`, `*.md`,
  `src/components/*.tsx`) plus discodon/eval/** vs discodon/eval/report.py (match) and
  discodon/evaluate.py (must not match); `resolve` in all four states; `files_for_paths`
  ordering and the empty-changed case (core only); `scaffold_core` idempotence.
- **Acceptance criteria:** `uv run pytest -q tests/test_learnings_files.py tests/test_plugin_init.py
  tests/test_onboarding_probes.py tests/preferences` passes; the harness probe under "What
  would raise confidence" confirmed and its result written into this chunk's Context line.
- **Critic mode:** final
  <!-- Keystone: three delegates build on the matcher's semantics. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: `learnings-migrate` — lossless relayout of any fleet format

- **Description:** The one-time transform every repo runs once. Mechanical, lossless, refuses on
  a dirty learnings file, idempotent. Delegate W1-A.
- **Depends on:** Chunk 01
- **Artifacts consumed:** discovery R3, audit §8.1 (the two discodon formats), §3.5 (five fleet
  formats)
- **Deliverables:**
  - new `plugin/lib/learnings_migrate.py`: `parse_legacy(text) -> list[Section]` handling the
    three shapes — `## Topic` with `- **rule**` bullets; `## <long paragraph rule>` with an
    optional body; and mixed. Everything before the first `## ` is preamble and is dropped.
    `strip_links(text)` removes `[detail](learnings-detail.md#…)`, `(detail in
    learnings-detail.md…)`, `→ detail.`, and `<!-- prawduct-learning: … -->` lines. `slug(title)`.
    `propose_map(project_dir, sections) -> dict[str, list[str]]`: for each topic section, tokens
    of the title matched case-insensitively against top-level directories and second-level
    directories of the largest top-level package; unmatched → no entry (goes to core).
    `plan(project_dir, map) -> Plan` and `apply(project_dir, plan)`: topic sections with a map
    entry → `<slug>.md` with `paths:` frontmatter; topic sections without → appended to `core.md`
    under their own heading; paragraph rules → `core.md` under `## Unsorted`; `core.md` opens
    with `learnings_files.CORE_HEADER`; then delete `.prawduct/learnings.md`,
    `learnings-detail.md`, `learnings-history.md` where present. Refuse (exit 2, named reason)
    when `git status --porcelain` shows any of those three paths modified. Refuse (exit 2,
    named reason: the destination is gitignored, unignore the rules directory first) when
    `git check-ignore -q .claude/rules/learnings/core.md` succeeds — otherwise `--apply` would
    delete a tracked file and write an untracked one. On a `new` layout report "nothing to do"
    (exit 0); on `both`, refuse and point at the R4 fold directive.
  - `plugin/bin/prawduct-hook`: `cmd_learnings_migrate(project_dir, argv)` with `--apply`,
    `--map <path>` (a `slug: [glob, …]` file, one per line), `--propose-map` (print the proposal
    in that format and exit), `--json`; dispatch line and usage entry. Dry run prints the plan:
    each output file, its byte size, and its rule count.
  - new `tests/test_learnings_migrate.py` with fixtures under
    `tests/fixtures/learnings_migrate/` (subtrees topic, paragraph, mixed) — `mixed` is a 30-rule excerpt
    of discodon's file with both shapes, links, and a metadata comment.
- **Tests:** unit — each fixture round-trips; **byte accounting**: every rule line of the source,
  after `strip_links`, appears verbatim in the concatenated output; refuse-on-dirty; idempotence
  (second run reports nothing); `both` refuses; gitignored destination refuses; `--propose-map` on a fixture tree with
  an eval directory under a discodon package proposes `eval-model-bake-offs: [discodon/eval/**]`; hook-argument-shape
  test for the new verb (`tests/test_hook_argument_shape.py` pattern).
- **Acceptance criteria:** `uv run pytest -q tests/test_learnings_migrate.py tests/preferences`
  passes; a dry run against the scratch copy of discodon's file reports output totals that sum
  to the source's rule bytes.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Branch and report handed to the coordinator; coordinator merges and runs `/prawduct:critic`
     on the merged chunk, blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: Budget gate — over-and-grew blocks the next addition

- **Description:** The curation mechanism. One `record_lint` check: a rules file over its budget
  that grew this session is a BLOCKING finding carrying the payment rule. Delegate W1-B.
- **Depends on:** Chunk 01
- **Artifacts consumed:** discovery R2, D4; audit §8.8 Q1–Q2
- **Deliverables:**
  - `plugin/lib/record_lint.py`: `_check_learnings_budget(project_dir, prawduct_dir, base_tree)`
    registered beside the existing checks. For each file in `learnings_files.resolve().files`:
    `now = size in the working tree`, `base = git cat-file -s <base_tree>:<path>` (0 when absent),
    `budget = budgets.get(name, 16 * 1024)`. Finding `learnings-over-budget`, severity BLOCKING,
    when `now > budget and now > base`; text: the file, both sizes, the budget, and "pay from
    genuine duplication (merge or delete in this commit), or raise `learnings_budgets.<name>` in
    project-state.yaml with a reason — never trim a rule to fit". Finding
    `learnings-budget-unreasoned`, BLOCKING, for any `learnings_budgets` entry lacking `reason`.
    Registered in the degraded-to-unchecked path the same way `suite-total-claim` is.
  - `plugin/templates/project-state.yaml`: `learnings_budgets:` documented (`core.md: {kb: 16,
    reason: "…"}`), replacing the `sentinel_command` block's comment with nothing (Wave 2 deletes
    the keys).
  - `tests/test_record_lint.py`: `TestLearningsBudget`.
- **Tests:** over-and-grew blocks; over-and-shrank passes; under passes; absent-at-base counts
  as grew; override raises the budget; override without reason blocks; legacy layout → no
  finding (the state is R4's problem, not this check's).
- **Acceptance criteria:** `uv run pytest -q tests/test_record_lint.py tests/preferences` passes.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Branch and report to the coordinator; coordinator merges, runs `/prawduct:critic`, blocking
     findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: Detection, directive, Stop floor, and the cross-check re-pointed

- **Description:** The new plugin version tells the truth about an unmigrated repo, directs the
  agent to migrate, and reads rules only through the resolver in the one place they fire.
  Delegate W1-C.
- **Depends on:** Chunk 01
- **Artifacts consumed:** discovery R4, R5; audit §8.7 (why a directive, not an advisory)
- **Deliverables:**
  - `plugin/lib/briefing.py`: replace the learnings count + size-nudge block with three states
    from `learnings_files.resolve()`. `new`: `Learnings: core.md (<n>KB) + <k> area files —
    loaded by the harness; rules apply, cite the one you applied`. `legacy`: `Learnings:
    UNMIGRATED — not loaded` and an `agent →` line: `run prawduct-hook learnings-migrate
    --propose-map, edit the map, run --apply --map <file>, commit "chore(learnings): migrate to
    .claude/rules/learnings (prawduct <version>)" — before other work`. `both`: `agent → fold
    .prawduct/learnings.md into .claude/rules/learnings/ by hand and delete it`. `none`: nothing.
    In the `new` and `both` states, when `git check-ignore -q` accepts the rules directory, append
    ` — GITIGNORED: the rules tree is not committed; unignore .claude/rules/` to the line (the
    harness still loads it, but nothing survives a clone).
    No advisory id, no dismiss. The `.subagent-briefing.md` learnings embedding is untouched
    here (Wave 2 removes it).
  - `plugin/bin/prawduct-hook` `cmd_stop`: when the layout state is `legacy` or `both` and the
    session changed judgeable code, emit blocker `learnings-unmigrated` with the same directive
    text; waivable via `.gates-waived` key `learnings` (added to `KNOWN_WAIVER_KEYS`).
  - `plugin/lib/gates.py`: the Critic gate text that names the Learnings Cross-Check reads the
    resolver's file list for the session's changed paths.
  - Prose: `skills/critic/review-protocol.md`, `review-cycle.md`, `goals-1-3.md`,
    `agents/critic-reviewer.md`, `skills/pr/review-protocol.md` — every "read `learnings.md`"
    becomes "read `.claude/rules/learnings/core.md` plus each area file whose `paths:` intersect
    the diff (`prawduct-hook learnings-files --for-diff` prints the list)"; add that verb to
    `learnings_files` as a thin `cmd_learnings_files`. Add the R5 goal to the cross-check:
    *rules added or changed this cycle — duplicate of an existing rule, wrong area file, or
    discipline/framework content that belongs upstream?* Add the `learnings-over-budget`
    severity row (BLOCKING) to `review-cycle.md`'s table beside `learnings-entry-shape` (which
    Wave 2 removes).
  - Tests: `tests/test_briefing_functions.py` (three states, directive text carries no id),
    new `tests/test_learnings_cutover_gate.py` (Stop floor: legacy + code → blocks; legacy +
    doc-only → passes; new → passes; waiver key), `tests/preferences/test_critic_skill_structure.py`
    and `tests/test_pr_reviewer.py` updated for the new phrasing, `tests/test_hook_argument_shape.py`
    for `learnings-files`.
- **Tests:** as listed; plus `test_observability`-style assertion that no emitted line contains
  an advisory-id-shaped token; plus the gitignored-rules-dir briefing suffix (present when
  ignored, absent when tracked).
- **Acceptance criteria:** `uv run pytest -q tests/test_briefing_functions.py
  tests/test_learnings_cutover_gate.py tests/test_pr_reviewer.py tests/preferences` passes.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Branch and report to the coordinator; coordinator merges, runs `/prawduct:critic`, blocking
     findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 05: Migrate this repo with its own command

- **Description:** Dogfood before release: the framework repo is the first fleet member through
  the cutover, using Chunk 02's command exactly as a consumer would. Serial, coordinator.
- **Depends on:** Chunks 02, 03, 04 merged
- **Artifacts consumed:** discovery R13 (self-migration), §9 (metadata-carrying rules)
- **Deliverables:** `prawduct-hook learnings-migrate --propose-map` → edited map (areas expected:
  `critic` → `plugin/skills/critic/**, plugin/lib/critic_*.py, plugin/agents/**`; `backlog` →
  `plugin/lib/backlog/**, plugin/skills/backlog/**`; `gates-hooks` → `plugin/bin/**, plugin/hooks/**,
  plugin/lib/gates.py`; `methodology` → `plugin/methodology/**, plugin/docs/**`; `pr-release` →
  `plugin/skills/pr/**, documentation/**`; the rest to core) → `--apply --map`; delete
  `learnings-detail.md` and `learnings-history.md` (the command does it); `CLAUDE.md` Reference
  line repointed to the new directory (one line; the CLAUDE.md budget test must stay green);
  `.prawduct/change-log.md` entry tagged `scope=learnings-v2-core`; the migration commit in the
  exact message form the briefing directive prescribes.
- **Tests:** none new — the full suite, and `prawduct-hook verify-records` clean including the
  new budget check (core.md will be over 16KB and **not grown**, so it must pass; assert that
  by reading the lint output, and record the size in the change-log entry).
- **Acceptance criteria:** fresh session in this worktree shows the `new` learnings line;
  `git grep -l 'learnings.md' -- plugin` returns only the Chunk 01 allowlist; full suite green
  and recorded.
- **Type:** cumulative-final
  <!-- Last chunk: its review IS the one `/prawduct:critic cumulative` — commit first, run once. -->
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status; `.prawduct/.handoff-notes.md` names Wave 2 as next and
     states that this repo's lookup skill is dark until Wave 2 deletes it

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** drop a rules file with `paths:` into this worktree and see the harness
load it on a matching read — the whole premise, proven before the plan widens.

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its review. Delegates commit on their branches;
the coordinator merges each with `--no-ff`, runs the full suite, and records the evidence. No PR
until Wave 3 closes the release; `/prawduct:pr create` is gated on Wave 3's cumulative review.

- After chunk 01: the matcher's semantics against the harness's — the one thing three
  delegates will build on and the one thing a test cannot prove without the probe.
- After chunks 02–04 merge: the grep-clean re-derivation of every "reads learnings.md" site
  W1-C claimed to repoint, before Chunk 05 removes the file they would otherwise still read.
- After chunk 05 (cumulative): the branch is a working new-layout plugin on a migrated repo;
  everything the lookup skill and nudge still say is Wave 2's to delete.
