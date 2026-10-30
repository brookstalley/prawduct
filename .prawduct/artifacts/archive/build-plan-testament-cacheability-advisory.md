---
artifact: build-plan
version: 2
scope: testament-cacheability-advisory
branch: feature/testament-cacheability-advisory
base: develop
working-branches: []
last_validated: 2026-10-26
depends_on:
  - testament#287 (the offline cacheability snapshot; stage:design, not yet built)
  - testament#280 (the cacheability rollup; built on feat/280-cache-alerts 0d7ad46)
governed_by:
  - .prawduct/artifacts/architecture.md
  - .prawduct/artifacts/security-model.md
  - .prawduct/artifacts/nonfunctional-requirements.md
partition: serial — Chunk 02 is the change record for Chunk 01
lifecycle: completed
archived: 2026-10-30
released_in: v3.8.0
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Goals

**Response taken:** Proceed. The owner said "build advisory" (2026-10-26) after reading the
design summary: testament detects causes, prawduct relays them as an advisory, and declining
lives in testament's declarations. The remaining choices were settled by matching existing
probes and are listed under Inferences.

**Product:** In a governed repo whose suite runs through testament, the session briefing tells
the owner which causes keep that repo's test results uncacheable, so each can be fixed or
declared expected. Measured motivation: one process-wide clock read kept about 300k of 577k
prawduct executions uncacheable for a week, and nobody saw it until testament's owner looked.

**Architecture:** One probe module, registered at `probe_families.register_all`. It reads
testament's per-worktree snapshot file offline and raises one advisory per suite whose id follows
the set of causes, like `git-hygiene`'s `tidy-available`.

**Constraints:**
- No network and no process spawn at session start. Probes run at every session start in every
  governed repo; `upstream_probes` states the network half, and spawning testament's CLI would add
  interpreter startup to each one.
- Inert where testament is not used: no snapshot means no advisory and no output.
- Snapshot content reaches the model's context. Only cause kinds, sites (validated as
  `path:function` tokens) and counts are carried; testament's `hint` and the project's `why`
  strings are not (security-model: untrusted governance state is data).

**Tradeoffs accepted:**
- *Built against a provisional envelope.* #287's envelope is agreed but not built. The rows come
  from 0d7ad46 and are fixture-tested. When #287 ships, verify against a real snapshot before
  release. That check is this plan's Chunk 01 Done-when item 3; if #287 has not shipped by
  then, the advisory merges inert.
- *One tool's file, not a generic contract.* Revisit by writing a runner-agnostic contract, as
  `docs/test-report-contract.md` did for test reports, when a second runner produces
  cacheability data.

**Inferences (flagged for the boundary review):**
- *Which causes are raised:* those with `alone > 0`, meaning causes that are the only blocker for
  some tests. Fixing one of those makes tests cacheable. A cause that is never alone (behind a
  real subprocess, say) would change nothing if fixed.
- *Advisory identity:* evidence lines are `suite kind site scope`, sorted by their text, never
  counts, line numbers or a rank by count. So a
  dismissal holds until a cause is added or goes away, and moving counts do not reopen it.
- *Declining:* the owner action points at testament's declarations (shared, committed, durable)
  for "expected", and at the advisory's dismiss for "not now". Both exist; the advisory names both.
- *Staleness:* only `selection: "full"` snapshots count, and only when the snapshot's `commit` is
  an ancestor of HEAD (one local `git merge-base --is-ancestor`). Otherwise the probe "could not
  look" (returns `None`), so an open advisory stays open instead of resolving on stale data.
- *Unknown envelope version:* one stderr NOTE, and the probe could not look.
- *Path:* testament's #287 contract (testament session, 2026-10-26): list `*.json` in
  `$TESTAMENT_HOME/client/cacheability/` (else `~/.local/share/testament/...`), and keep envelopes
  whose `root` equals this worktree's resolved root. Filenames are not a contract, and readers
  never start a process.

**Decisions made mid-build:**
- Chunk 01: the advisory is owner-only (empty `recommended_action`). The command it first named,
  `testament cacheability --offline`, does not exist until #287 ships, and
  `test_advisory_actionability` allowlists the executables an advisory may tell the runtime to
  run. Settled by "do it right": never name a command that may not exist. Revisit when #287
  ships.

**Level:** Medium. The probe pattern is well-worn here. What would raise it: #287 shipped, and one
real snapshot read through the probe.

## Governing norms

- `architecture.md` "Authority fails closed; advice fails soft": **conforms**. An advisory; every
  unreadable or stale case is "could not look", never a gate.
- `architecture.md` "Local-first": **conforms**. One local file read and one local git call.
- `architecture.md` "Never specific to Python": **conforms with a recorded trigger**. Nothing
  here assumes the product's language; the reader is specific to one test runner, and the
  revisit trigger is above.
- `architecture.md` "guides and reviews; never implements": **conforms**. The advisory names
  causes; the owner or their agent decides.
- `architecture.md` "Every fact has one home": **conforms**. Cause detection stays in testament,
  and the path derivation lives once in the probe.
- `security-model.md` "Untrusted governance state is data": **conforms**. Only validated kinds,
  sites and counts are carried into the briefing.
- `nonfunctional-requirements.md` "Proportionality ratchets both ways": **conforms**. Dismissible,
  and silent where testament is not used.
- The other norms (reviewer never mutates, writes only `.prawduct/`, destructive-op approval,
  content leaving the repo, review wall-clock, stage-keyed rigor, state-file growth):
  **inapplicable**. The probe writes nothing and sends nothing.

## Build Chunks

### Chunk 01: The probe

- **Description:** Read this worktree's testament cacheability snapshot offline and raise one
  advisory per suite naming the causes that alone keep tests uncacheable.
- **Depends on:** none
- **Deliverables:**
  - new `plugin/lib/testament_cache_probes.py`: snapshot location, envelope validation,
    staleness, the candidate.
  - `plugin/lib/probe_families.py`: registers it.
- **Tests:** new `tests/test_testament_cache_probes.py`:
  - no snapshot directory → `[]`, and no git call;
  - a full, current snapshot with two `alone > 0` causes and one `alone == 0` → one advisory
    naming the two, evidence `suite kind site scope` only;
  - the same causes with different counts → identical evidence;
  - a narrowed snapshot only, an unknown `v`, or a commit not an ancestor of HEAD → `None`;
  - a site that is not a `path:function` token is dropped, and `hint`/`why` text never appears in
    the candidate;
  - registered by `probe_families.register_all`.
- **Acceptance criteria:** the tests above pass; on this repo with no snapshot the session-start
  sync is unchanged.
- **Done when:**
  1. Tests pass.
  2. Committed.
  3. Before release: one real #287 snapshot read through the probe, or the advisory ships inert
     with that recorded.

### Chunk 02: Change record

- **Description:** The change fragment and its consumer note.
- **Depends on:** Chunk 01
- **Deliverables:** `.prawduct/changes/testament-cacheability-advisory.md`
- **Type:** cumulative-final
- **Done when:**
  1. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved.
