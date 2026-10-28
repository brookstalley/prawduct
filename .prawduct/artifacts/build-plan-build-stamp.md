---
artifact: build-plan
version: 2
scope: build-stamp
branch: feature/1086-build-stamp
base: develop
working-branches: []
last_validated: 2026-10-27
depends_on:
  - brookstalley/prawduct#1086
governed_by:
  - .prawduct/artifacts/architecture.md
  - .prawduct/artifacts/api-contract.md
  - .prawduct/artifacts/data-model.md
partition: Chunks 01-02 delegated to one isolated-worktree agent; the coordinator integrates, runs the suite, Critic and PR
---

# Build Plan — Facts tell dev builds apart (#1086)

## Goals

**Response taken:** Proceed, citing #1086. The owner asked on 2026-10-27 for it to land in 3.8.0.
The issue has a repro and acceptance criteria.

**Problem:** every evidence fact's `actor.plugin` reads `3.8.0-dev` (now `3.8.0-dev.2`) for every
develop build and feature-branch head, so a beta comparison blends builds. A per-merge `-dev.N`
bump was tried as a workaround (#1105). It costs a change record, two boundary reviews and a full
suite run per bump, and gives no rule for what develop does when a beta branch takes a higher
pre-release number. So the fix is a stamp, not a bump policy.

**Success (#1086's acceptance):**
- Two facts recorded by different dev builds of the same `major.minor` are distinguishable in
  `prawduct-hook stats`.
- The contribution payload (`plugin/lib/contribution.py`) still carries only `major.minor` plus the
  `dev` flag; the build stamp never leaves the clone through it.

**Design decision (coordinator):** an additive `actor.build` field on the fact envelope
(`plugin/lib/evidence.py`, where `actor.plugin` and `actor.branch` are set), following
`actor.branch`'s rule: OMITTED, never null, when it cannot be read. Its value is the plugin root's
git commit sha (12 hex characters), with a `+dirty` suffix when the plugin tree has uncommitted
changes. A marketplace install is not a git checkout, so it records no `build` and its released
version already identifies it. Read once per process. No schema version moves.

**Persisted format — the questions the field must answer** (its consumers' queries):
1. Which exact plugin build recorded this fact? (sha)
2. Group a version's facts by build. (sha as the key)
3. Did store X run a different build from store Y over the same days? (sha, compared across
   stores)
4. Was the build an exact commit or a working tree? (`+dirty`)

**Out of scope:** changing the version stamp scheme; the banner (#1104).

**Level:** High.

**Decisions made mid-build:** *(appended while building)*
- Chunk 01: "dirty" counts untracked-unignored files under the plugin tree as well as modified tracked ones (new code runs too); ignored files (bytecode caches) and changes outside the plugin directory do not. Alignment-pass miss: the plan said "uncommitted changes" without saying which.
- Chunk 01: a plugin root counts as a checkout only when its own `VERSION` is a tracked file there, so a copy under an unrelated repository (a version-controlled home directory) records no build instead of borrowing that repository's sha. Inferred, not in the plan.
- Chunk 01: git's repository-locating variables (`GIT_DIR`, `GIT_WORK_TREE`, `GIT_INDEX_FILE`, …) are stripped for the stamp's calls, because a hook run under a product's git hook would otherwise stamp the product's commit. Inferred.
- Chunk 01: sha and dirtiness come from one `git status --porcelain=v2 --branch -- .` call plus one `ls-files` check; if either fails, no build is recorded rather than a sha of unknown dirtiness. Measured cost on this machine: about 35 ms warm, about 125 ms cold, paid once per process (the result, `None` included, is memoised).
- Chunk 01: `actor.build` travels in the notes transport like `actor.branch` (only `actor.session` is dropped there), so it reaches the product's remote with the transported facts. The plan bounded only the contribution payload; this was left as is because the build is no more identifying than the branch, and a clone that ingests the fact can then still say which build wrote it (Goals questions 1 and 3). Flagged for the owner.
- Chunk 02: `stats --by-build` is a flag that adds a `by_build` key (`{major.minor: {build: body}}`) beside an unchanged `by_version`, rather than re-keying `by_version`; the default shape is unchanged, so `REPORT_SCHEMA_VERSION` stays at 2. With the flag, the human report prints one block per build in place of one per version.
- Chunk 02: within a version, builds are listed in the order the store first saw them (append order, close to run order), because sorting shas puts them in no useful order. A non-string or empty `actor.build` counts as `unstamped`.
- Chunk 02: `contribution.py` needed no change, because it buckets through its own `contribution_bucket` and never reads `actor.build`. Two tests now pin that: one on the payload and one end to end through `contribute --json` over a store whose facts carry a build.

## Chunks

### Chunk 01: actor.build is written

- **Description:** Stamp `actor.build` in `evidence.py` as the design decision says. Find the
  plugin root the same way `_plugin_version()` does. Every git call goes through the existing
  timeout-bounded helper and fails to "omit", never to an exception or a null.
- **Depends on:** none
- **Deliverables:** `plugin/lib/evidence.py`; the envelope description in `api-contract.md` and
  `data-model.md` (wherever `actor.branch` is described)
- **Tests:** clean checkout → sha; dirty plugin tree → `+dirty`; non-git plugin root → field absent;
  git failure → field absent
- **Acceptance criteria:** the tests; existing evidence tests unchanged and green
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed

### Chunk 02: stats reads it; contribution does not

- **Description:** `plugin/lib/stats.py` can split a version bucket by `actor.build` (a flag or
  sub-bucket; follow the command's existing option style). Facts without `build` group as one
  "unstamped" build. Pin with a test that `contribution.py`'s payload never includes `build`.
- **Depends on:** Chunk 01
- **Deliverables:** `plugin/lib/stats.py`, its CLI help, the docs that describe `stats` output
- **Tests:** two facts, same `plugin`, different `build` → two rows; contribution payload has no
  `build`
- **Acceptance criteria:** #1086's two acceptance boxes
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed

### Chunk 03: change record

- **Type:** cumulative-final
- **Description:** `.prawduct/changes/build-stamp.md`: narrative and consumer note,
  `closes: [brookstalley/prawduct#1086]`.
- **Deliverables:** `.prawduct/changes/build-stamp.md`
- **Done when:**
  1. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
