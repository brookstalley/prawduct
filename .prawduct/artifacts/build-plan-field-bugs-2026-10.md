---
artifact: build-plan
version: 2
scope: field-bugs-2026-10
branch: fix/field-bugs-2026-10
depends_on:
  - artifact: api-contract
  - artifact: architecture
governed_by:
  - artifact: architecture
    dispositions:
      - "authority fails closed; advice fails soft → conforms: Chunk 01 narrows which repos the skew guard (an authority) applies to, but a prawduct checkout whose manifest cannot be read still refuses (see the DECISION in Chunk 01). Chunk 03 is advice: it reports and never deletes"
      - "local-first governance coordination → conforms: Chunk 03 reads local files under the home directory and opens no socket"
      - "the plugin writes nothing into a governed repo except its own state… → conforms: no chunk writes outside `.prawduct/`, and Chunk 03 writes nothing anywhere"
      - "prawduct guides and reviews, it never implements → conforms: Chunk 03 prints the delete commands for the operator to run; it runs none of them"
      - "written in Python, never specific to Python → inapplicable, because no language-dispatched check changes"
      - "an independent reviewer never mutates the session it reviews → inapplicable, because no reviewer path changes"
      - "goals and verification bind; prescribed method is advice → conforms: each chunk's acceptance criteria are the binding half; its Deliverables are a forecast"
      - "every fact has one home → conforms: the checkout predicate stays in one function both skew checks call; the stale-cache rule lives in the new lib module, and doctor and api-contract cite it rather than restating it"
  - artifact: api-contract
    dispositions:
      - "whole-surface semver; no per-subcommand version → conforms: the new subcommand ships at the plugin's version, in the internal tier"
      - "exit codes are the contract, on the documented scheme → conforms: Chunk 03's subcommand uses the existing scheme (0 report, 1 bad arguments or an unreadable input), stated in its usage text and its api-contract entry"
      - "additive-first evolution → conforms: one new subcommand and no repurposed flag, exit code or `--json` key. Chunk 01 changes when the skew refusal fires, not what it says or the exit code it uses"
  - artifact: data-model
    dispositions:
      - "a governance document reaches a terminal state; it is never deleted → conforms: Chunk 02 removes a refusal that kept live plans from reaching their terminal state"
      - "facts are immutable and append-only; verdicts read the ledger → inapplicable, because no chunk writes or reads a fact"
      - "two stores, two lifetimes → inapplicable, because no chunk adds persisted state"
partition: serial — 01 and 03 both edit `plugin/bin/prawduct-hook`, and 02 is too small to repay a delegate's brief
---

# Build Plan: three bugs users hit (#959, #809, #321)

## Problem

Users filed or reproduced three bugs. Each one blocks a prawduct workflow or leaves the user's
machine in a state they cannot see.

- **#959. Product repos that ship their own Claude plugin cannot record a Critic review.**
  `_repo_plugin_dir()` treats any repo that holds `plugin/.claude-plugin/plugin.json` as a
  prawduct checkout. In such a product, the `plugin-binary-skew` guard refuses every data-plane
  command, and it tells the user to run a `plugin/bin/prawduct-hook` that does not exist.
  `--force` does not help, so the Critic gate and the PR gate can never be met there. The only
  workaround is to rename the product's own plugin directory.
- **#809 (with #960 merged in). `archive-plan` and `plan-backfill --apply` refuse a live plan
  whose frontmatter says `lifecycle: active`.** The refusal guard fires on *any* `lifecycle:` value.
  `active` is not an end of life, and the refusal message contradicts itself. Two reporters, three
  weeks apart, had to hand-edit the frontmatter to archive their plans. The writer
  (`apply_completion_frontmatter`) already replaces its own keys in place, so the fix is only the
  guard.
- **#321. Old plugin cache directories pile up in every config profile.** Claude Code keeps every
  version directory under `~/.claude*/plugins/cache/<marketplace>/prawduct/`, and
  `claude plugin prune` does not remove them. Measured on the owner's machine on 2026-10-06:
  `ls -d ~/.claude*/plugins/cache/*/prawduct/* | wc -l` found 77 version directories across 6
  profiles, and `du -sh ~/.claude*/plugins/cache/*/prawduct` totalled about 785 MB. The
  pre-v3.1.1 copies still hold prawduct's own `.prawduct/`, tests and documentation. Nothing
  tells the user any of this.

## Success

- In a governed product that ships its own `plugin/` with any manifest name other than
  `prawduct`, `critic-begin` succeeds, and the skew guard still refuses a foreign binary inside a
  real prawduct checkout.
- `archive-plan --state completed` archives a plan that says `lifecycle: active`, and the result
  carries exactly one `lifecycle:` line, the terminal one. A plan that already says `completed`
  or `superseded` is still refused, and the refusal names that value.
- `/prawduct:doctor` reports, for every config profile on the machine, the prawduct cache
  version directories that no install record uses, with their sizes and the command to delete
  each one. It deletes nothing itself.

## Out of scope

- **#182** (record which trigger consolidated a review). It is the next impact-L item by
  effort, but it touches the Critic data plane and the ledger's closed argument set. Its body
  also leaves two design details open: the trigger vocabulary, and whether the field is
  required. Its `stage: ready` label overstates where it is. It needs its own plan.
- Deleting caches automatically, or adding an ambient advisory for them. Cleanup stays an
  explicit operator act, because a session already running in another profile may be using a
  directory the install records no longer name.
- `lifecycle-repair` learning to rewrite `lifecycle: active`. Once the guard stops refusing it,
  nothing needs repairing.

## Requirements Confidence

**Level:** High

**Why:** Each bug has a reproduction, and I checked each root cause against develop at
`e0b79018`. #959: `plugin/bin/prawduct-hook` `_repo_plugin_dir` tests only that the manifest
exists. #809: `plan_archive.refusal_reason` refuses `if existing:`. #321: the measurement
above. The fixes are local, and the only design choice not settled by its issue is recorded
below as a vetoable decision.

**Open assumptions / unknowns:**
- [ASSUMPTION: "highest priority" means user-reported bugs that break a workflow, ranked by impact and then by low effort, not the 20 `ready` impact-L items as a whole, which would be a program of several plans | HIGH impact | user can override]
- [ASSUMPTION: a cache version directory is "in use" if any `installed_plugins.json` record on the machine names it, either by its resolved `installPath` or, for a record whose path does not exist on this host (a devcontainer path such as `/home/vscode/...`), by its `version` within the same config root | MED impact | user can correct]
- [ASSUMPTION: a session already running in a profile can still be using a directory its install record no longer names, so the report warns the user to close sessions in that profile before deleting | LOW impact | user can override]

**What would raise confidence:** N/A

## Status

- [x] Chunk 01: The skew guard recognises prawduct by its manifest name (#959)
- [ ] Chunk 02: Only a terminal lifecycle blocks a re-archive (#809)
- [ ] Chunk 03: Doctor reports stale plugin cache directories (#321)
Context: Approved 2026-10-06. Chunk 01 built, reviewed (0 findings) and committed. Next: Chunk 02. All three chunks touch a declared risk surface (`plugin/bin/*hook*`, `plugin/skills/`), so this is not a short plan: chunks 01 and 02 get a `chunk` review each, and Chunk 03's `cumulative` is the boundary review.

## Verification Strategy

Each fix is checked the way the user hit it, in addition to its tests:
- **01:** a scratch git repo with `.prawduct/` and `plugin/.claude-plugin/plugin.json` set to
  `{"name":"other"}`. Run `critic-begin` there and confirm it is not refused. Then run the
  installed `prawduct-live` binary inside this checkout and confirm it still refuses.
- **02:** a scratch plan with `lifecycle: active` in a temp artifacts directory. Run
  `archive-plan --dry-run`, then the real archive, and read the frontmatter of the result.
- **03:** run the new subcommand on this machine. The numbers it reports must match `ls` and
  `du` over the same directories, and it must list no directory that an install record names.

## Build Chunks

### Chunk 01: The skew guard recognises prawduct by its manifest name (#959)

- **Description:** `_repo_plugin_dir()` should treat a repo as a prawduct checkout only when
  the repo's plugin manifest names `prawduct`. Both `_binary_skew` and `_lib_skew` call that one
  function, so fixing it there fixes both checks.
- **Depends on:** none
- **Deliverables:** the predicate change in `plugin/bin/prawduct-hook`; its docstring corrected,
  because its claim that product repos "hold none" is the false premise behind #959; tests in
  the existing binary-skew test module; a change-log entry under `scope=field-bugs-2026-10`.
- **Decision:** [DECISION: a manifest that parses and names anything other than `prawduct` means
  the repo is not a checkout. If the manifest cannot be read or parsed, fall back to whether
  `plugin/bin/prawduct-hook` exists | the guard is an authority and must fail closed in a real
  prawduct checkout whose manifest is broken mid-edit. A product with its own plugin has no
  `prawduct-hook` binary, so the fallback cannot misfire there | user can veto]
- **Tests:** each test is red-verified against develop first.
  - A repo whose manifest names `other`: the data-plane command is not refused.
  - A repo whose manifest names `prawduct`, run by a foreign binary: still refused.
  - A malformed manifest with `plugin/bin/prawduct-hook` present: refused.
  - A malformed manifest with no such binary: untouched.
  - At least one case reaches the predicate through `_lib_skew`, so both callers are pinned.
- **Acceptance criteria:**
  - #959's reproduction (manifest `{"name": "other"}`, then `critic-begin`) is not refused.
  - Every existing skew test stays green.
  - Running `rg -n 'claude-plugin' plugin/lib plugin/bin plugin/hooks` finds no other place that
    decides "framework checkout" from the directory layout alone. As of 2026-10-06 the other hits
    read prawduct's own install root.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: Only a terminal lifecycle blocks a re-archive (#809)

- **Description:** `refusal_reason` should refuse only when the existing lifecycle value is in
  `TERMINAL_STATES`. A non-terminal value is replaced by the stamping that already happens. The
  refusal message names the value it found. This fixes `plan-backfill --apply` as well, because
  it reaches the same guard.
- **Depends on:** none
- **Deliverables:** the guard change in `plugin/lib/plan_archive.py`; a corrected docstring on
  `read_completion`, whose consumer is this guard; tests; a change-log entry under the same scope.
- **Tests:** each test is red-verified against develop first.
  - `lifecycle: active` archives, and the result holds exactly one `lifecycle:` line.
  - `completed` and `superseded` are each still refused, with the value named in the reason.
  - `plan-backfill --apply` moves an `active` plan that it previously classed as `blocked`.
  - An unrecognised value (for example `draft`) is treated as non-terminal and replaced.
- **Acceptance criteria:** both reproductions in #809 and #960 archive without a hand edit,
  and #809 can be closed as shipped (#960 is already merged into it).
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: Doctor reports stale plugin cache directories (#321)

- **Description:** a read-only `prawduct-hook` subcommand lists every prawduct cache version
  directory, in every config root on the machine, that no install record uses. For each one it
  gives the size and a delete command, and it ends with a warning to close sessions in that
  profile first. `/prawduct:doctor` gets a Health Check that runs it and passes the result to
  the user. Rules:
  - Config roots are deduplicated by resolved path, because profiles here share `plugins/`
    through symlinks.
  - A root with no `installed_plugins.json` is reported as unknown, never as "all stale".
- **Depends on:** none
- **Deliverables:**
  - A new module under `plugin/lib/` that owns the stale-cache rule. It reuses the root
    enumeration in `plugin/lib/stranded_work.py` `config_roots` (given a different marker
    subdirectory) and the manifest reading in `plugin/lib/plugin_activation.py`, rather than copying
    either.
  - The subcommand, with `--json`.
  - A new Health Check in `plugin/skills/doctor/SKILL.md`.
  - An entry in the api-contract § Operations list (internal tier).
  - A change-log entry under the same scope.
- **Tests:** a fake home with three config roots: one in use, one symlinked to it, and one
  devcontainer root whose install path does not exist on the host. Cases:
  - stale versions are listed, and in-use versions are not;
  - the symlinked root is counted once;
  - the devcontainer record keeps its version by name;
  - a root with an unreadable or missing manifest is reported as unknown;
  - the command writes and deletes nothing: the fake tree is byte-identical before and after.
- **Acceptance criteria:**
  - On this machine, the listed directories exactly equal the version directories minus those
    named by install records.
  - Every reported size matches `du` for that directory.
  - Doctor's Health Check output shows the per-profile totals and the delete commands.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status; #959 and #321 marked shipped through `/prawduct:backlog` when
     the PR merges

## Governance Checkpoints

**Commit & PR cadence:** commit each chunk after its review passes. Chunk 03 commits first, and
its `cumulative` review makes the branch ready for a PR. `/prawduct:pr create` runs when the
owner asks for one.

- After Chunk 01: confirm the fallback in the DECISION holds in this checkout. Run the
  installed binary here with the manifest temporarily made unparseable; it must refuse.
- After Chunk 03 (cumulative): review the whole bundle. Once it merges, advance
  `~/source/prawduct-live` as usual.
