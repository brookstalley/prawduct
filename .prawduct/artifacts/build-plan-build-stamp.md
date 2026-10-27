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
