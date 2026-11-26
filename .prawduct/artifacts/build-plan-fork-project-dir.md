---
artifact: build-plan
version: 2
scope: fork-project-dir
branch: fix/fork-project-dir
base: develop
working-branches: []
last_validated: 2026-11-26
depends_on:
  - artifact: architecture
  - artifact: api-contract
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → conforms: the Critic fork reviews the tree its caller names and writes only that tree's `.prawduct/` state, as it does today for its own toplevel"
      - "authority fails closed; advice fails soft → conforms: a `--project-dir` that is relative, missing or not a work-tree toplevel refuses by name and runs nothing; the tree line is advice and changes no exit"
      - "local-first: process-spawn, atomic files, the git object database → conforms: one local `git rev-parse` validates the path; no network"
      - "the plugin writes nothing into a governed repo but its own state → conforms: the option changes WHICH repo's `.prawduct/` a command reads and writes, never what it writes"
      - "never specific to Python → inapplicable because this is framework CLI plumbing; a product's language is not involved"
      - "prawduct guides and reviews; it never implements → inapplicable because this is framework code"
      - "goals and verification bind; prescribed method is advice → conforms: the measured repro and the refusals bind; the dispatch-site placement is a forecast"
      - "every fact has one home → conforms: the option is parsed once, in `_dispatch`, before any command runs; skills pass it, never re-derive the repo"
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning; CLI subcommands carry no per-subcommand version → conforms: one new dispatcher-level option, minor-tier within the release"
      - "exit codes are the contract → conforms: every refusal exits 1, never 2, which `critic-begin` already means as scope-widened (boundary review N2); no existing code changes meaning"
      - "additive-first evolution → conforms: a new option no subcommand defines today (`grep -- --project-dir` returns none); callers that omit it are unchanged"
partition: serial — one chunk
---

## Goals

**Response taken:** Proceed, citing #1253 and its design comment (issue comment 7195098961, posted
2026-11-26). The owner ordered it after #1232 (`.prawduct/owner-rulings.md`, 2026-11-26).

**Product:** A subagent working in another repository calls `/prawduct:critic`, `/prawduct:backlog`
or `/prawduct:advisory`. Today the skill silently acts on the session's launch repo: it reviews the
wrong tree, or files into the wrong backlog, and reports "nothing to review" or success. Success:
the caller can name its repo and the skill acts there, and a critic run always names the tree it
used, so a caller who forgot can see it.

**Cause (measured, Claude Code 2.1.332, 2026-11-26):** a `context: fork` skill invoked by a subagent
(no isolation) that works in a second repo via `cd <other> && …` runs its shell in the launch repo.
Its environment names nothing of the caller, and its arguments do reach it. #221's 2.1.296
measurement still holds for `EnterWorktree` and `isolation: "worktree"`; neither reaches a different
repository. `critic-begin`'s PDT-WT9K guard compares the fork's cwd with the fork's resolved tree,
which are the same launch repo, so it cannot catch this.

**Architecture:** `prawduct-hook` takes `--project-dir <absolute path>` anywhere after the
subcommand and before a bare `--`. `_dispatch` pops it before `_check_argument_shape`, validates it,
`chdir`s there, and resolves the project dir to it over the launch pin and the cwd. Every command
then sees one tree, PDT-WT9K included. Hooks never pass it. The forked skills accept the same
argument and pass it to each `prawduct-hook` call, each `git -C`, and each file path they read or write.

**Decisions (inferred, mine, open for the owner at the boundary review):**
- *Placement after the subcommand*, so the skills' existing grants (`Bash(prawduct-hook critic-begin*)`)
  still match. A leading global flag would need every grant rewritten.
- *Validation:* the value must be absolute, and `git -C <p> rev-parse --show-toplevel` must resolve to
  `<p>` itself. A subdirectory is refused, not walked up to its toplevel, because the caller named a
  repo and a silent walk-up is the class of guess this fixes.
- *The tree line:* `critic-begin` prints `PRAWDUCT: tree <toplevel> · <branch or detached> @ <sha12>` first,
  on every outcome after argument parsing, and the critic skill's report leads with it. Backlog and
  advisory writes name their store where they do not already (Issues ids already carry the repo).
- *Out of scope:* detecting a forgotten `--project-dir` (a Skill hook sees the subagent's cwd, which
  is also the launch dir), and the harness-side fix (reported to Claude Code as feedback).

**Decisions made mid-build (inferred, open for the owner at the boundary review):**
- The same tree twice (after `os.path.normpath`) is one tree; two different trees are refused.
  The critic forwards its arguments to `infer-critic-mode` and also appends the option, so a strict
  refusal would fire on a correct call. `--project-dir=<p>` is the same option. Every refusal exits
  1, never the usage error 2, because `critic-begin` already reads 2 as "scope widened, re-dispatch"
  (boundary review, native N2).
- Usage errors are refused before the shape check, path checks after it, so nothing runs before a
  git probe. Validation fails closed when `lib/` will not import, unlike the rest of dispatch.
- No `CLAUDE_PROJECT_DIR` rewrite for child processes (it would be a host-variable write outside the
  host seam); the `chdir` plus the override cover in-process readers.
- The tree line goes to stdout, on the not-onboarded path too; a non-git tree reads
  `(not a git work tree)`, an empty repo `(no commits)`.
- Each bare hook grant in a forked skill, and in `critic-reviewer`, gains a `--project-dir *` form
  rather than becoming a starred grant, so no grant widens past its command.
- Coordinator gap (builder-found, fixed by the coordinator): the SubagentStop hook runs in the
  launch repo and never merges a three-reviewer review in another tree, so under `--project-dir`
  the coordinator consolidates itself, and the reviewer prompt passes the option to every probe.
- Budget raises declared in the pins: critic SKILL.md +108 (frontmatter grants +104), coordinator.md
  +29, the reviewer payload routes +12 to +137, delegation.md +24.

## Build Chunks

### Chunk 01: A forked skill acts on the repo its caller names

- **Description:** `--project-dir` on `prawduct-hook` and on the three forked skills. `critic-begin`
  names its tree on every outcome. `delegation.md` says when a delegate passes it.
- **Depends on:** none
- **Deliverables:** `plugin/bin/prawduct-hook` (`_dispatch` option, validation, the `get_project_dir`
  override, the `critic-begin` tree line, PDT-WT9K against the named tree);
  `plugin/lib/gitstate.py` if the override belongs in `resolve_project_dir`;
  `plugin/skills/critic/SKILL.md` (argument-hint, step 0, `git -C * <verb> *` grants),
  `plugin/skills/critic/coordinator.md` if its `[dir]` wording changes;
  `plugin/skills/backlog/SKILL.md`, `plugin/skills/advisory/SKILL.md`;
  `plugin/methodology/delegation.md` (one sentence beside "a skill forks in the session's own directory");
  `.prawduct/artifacts/api-contract.md` (Operations: the dispatcher option; Conventions);
  `.prawduct/changes/fork-project-dir.md` (closes #1253); tests.
- **Tests:** through the real CLI:
  - from a cwd in repo A with `CLAUDE_PROJECT_DIR` set to A, `--project-dir B` makes a read and a write
    command act on B;
  - each refusal (missing value, relative, nonexistent, a subdirectory, not a repo), exit code and message;
  - `--` keeps a later `--project-dir` for the passthrough command;
  - PDT-WT9K passes with the option and still refuses without it;
  - the tree line on each `critic-begin` exit path (dispatch, 3, 4, 7, 8, error).
  - A guard: every `context: fork` skill declares `--project-dir` in its argument-hint and mentions it
    in its body, read from the real skill files.
  - Each new test seen red first.
- **Acceptance criteria:** the measured repro's shape (a cwd and env pin in A, the option naming B)
  reviews or writes B, and the critic's first line names B. Without the option the line names A.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
