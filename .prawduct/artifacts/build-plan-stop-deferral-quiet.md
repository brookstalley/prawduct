---
artifact: build-plan
version: 2
scope: stop-deferral-quiet
branch: fix/stop-deferral-quiet
base: develop
working-branches: []
last_validated: 2026-10-27
governed_by:
  - .prawduct/artifacts/architecture.md
  - .prawduct/artifacts/api-contract.md
partition: serial — Chunk 02 is the change record for Chunk 01
---

# Build Plan — Stop's deferred-review notice stays out of the transcript at exit 0

## Goals

**Response taken:** Proceed. The owner, on 2026-10-27, on the notice as seen in a governed repo:
"seems like pure noise?", then "1 now".

**Problem:** On a non-blocking Stop, the Critic gate's two deferral notices (the review-interval
extension and the short-plan non-final chunk) are delivered as a `systemMessage`. That channel
reaches only the user, every turn the deferral holds, with a status the user cannot act on
("none is owed now… Commit and carry on"); the model never sees exit-0 output.

**Success:** at exit 0 both notices go to the hook's stderr log only, and no `systemMessage`
carries them; when another gate blocks, they still ride the exit-2 block text beside the
blockers; every other advisory is delivered as before.

**Out of scope:** the deferral logic itself; the handoff-note advisory, which tells the user
something they can act on.

**Decisions made mid-build:**
- Chunk 01: the two tests that pinned the `systemMessage` delivery (#822's design) are
  renegotiated in the open on the owner's ruling; their content assertions move to stderr.

## Norm reconciliation (`governed_by`)

- `architecture.md` "Authority fails closed; advice fails soft" — **conforms**: advice only; no
  gate's verdict changes.
- `api-contract.md` "Additive-first evolution" — **conforms**: no exit code or `--json` key
  changes; a transcript message stops being emitted.
- Other norms — **inapplicable**: no write path, schema or network change.

## Build Chunks

### Chunk 01: Deferral notices are log-only at exit 0

- **Description:** A `_LogOnlyAdvisory` marker the exit-0 delivery keeps out of `systemMessage`.
- **Depends on:** none
- **Deliverables:** `plugin/bin/prawduct-hook` (`_LogOnlyAdvisory`, `_deliver_stop_advisories`,
  both deferral appends); the two deferral test files.
- **Tests:** exit 0 → no `systemMessage` carries `deferred-boundary-review`, stderr does; exit 2
  → it rides the block (existing test).
- **Acceptance criteria:** the success line above.
- **Done when:**
  1. Tests pass.
  2. Committed.

### Chunk 02: Change record

- **Description:** The fragment for this unit.
- **Depends on:** Chunk 01
- **Deliverables:**
  - `.prawduct/changes/stop-deferral-quiet.md`
- **Tests:** none: prose.
- **Acceptance criteria:** the fragment validates.
- **Type:** cumulative-final
- **Done when:**
  1. Declared suite recorded green.
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved.
