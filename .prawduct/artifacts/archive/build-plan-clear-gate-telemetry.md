---
artifact: build-plan
version: 2
scope: clear-gate-telemetry
branch: fix/clear-gate-telemetry
base: develop
working-branches: []
last_validated: 2026-10-29
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable because no reviewer path changes"
      - "authority fails closed; advice fails soft → conforms: the clear-verdict narrowing passes only on an observed work_live True; None blocks"
      - "local-first governance coordination → conforms: no network; one git diff the Stop hook already runs"
      - "the plugin writes nothing into a governed repo but its own state → conforms: one more key on an existing fact"
      - "never specific to Python → inapplicable because no language dispatch changes"
      - "guides and reviews, never implements → inapplicable because no product code is touched"
      - "goals and verification bind; prescribed method is advice → conforms"
      - "every fact has one home → conforms: the observation key is named once in evidence.py and read through it by the hook and stats"
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning → conforms: ships in the next release; no evidence-store schema bump, since an observed key is additive"
      - "exit codes are the contract → conforms: Stop's exit codes keep their meanings; one more case exits 0"
      - "additive-first evolution → conforms: one new observed key; no --json key removed or repurposed"
partition: serial — both chunks edit the Stop hook's clear-gate block and the same telemetry doc
lifecycle: completed
archived: 2026-10-30
released_in: v3.8.0
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

# Build Plan — Clear gates: honest catch/slip, and YOUR TURN may hold a live clear

## Goals

**Response taken:** Proceed. On 2026-10-29 the owner reviewed the 3.8.0-dev field survey and
answered "yes to all" to three proposals: fix the catch/slip classifier, narrow `clear-verdict`
for the live-work case now (even though #1044 says to wait for its quarter of data), and comment
the classifier point on #1044.

**Problem:**
- `clear-reason` firings are counted as a **catch** whenever no handoff notes are on disk. In the
  survey, testrouter accounted for 10 of the 11 firings in 3.8. They were question or diagnosis
  turns in sessions that changed nothing. The observation can't tell those apart from a lost
  decision, so #1044's data leans towards keeping the gate.
- `clear-verdict` refuses `YOUR TURN` + `DO NOT CLEAR` even when work a clear would kill is
  running. 7 of the 10 3.8 firings that recorded observations were exactly that case. Each cost
  a round trip that only relabelled the disposition.

**Success:**
- A clear-gate firing records `session_changed`.
- `stats` calls a `clear-reason` firing a catch only when the session changed something and no
  notes were present. A read-only session's firing is unclassified, and so is a pre-existing fact
  without the observation.
- The Stop hook no longer refuses `YOUR TURN` + `DO NOT CLEAR` while harness background work or a
  live Critic review is observed. `COMPLETE` + `DO NOT CLEAR` and the unobservable case still block.
- The norm prose (digest, session-hygiene) says the same thing.

**Out of scope:**
- Changing `clear-reason`'s behaviour. It waits for honest data under #1044.
- Detecting unreaped delegates.

**Decisions made mid-build:**
- A read-only session's `clear-reason` firing is **unclassified**, not slip. Whether clearing a
  diagnosis loses anything is a judgment this instrument can't observe (Honest Confidence).

## Norm reconciliation (`governed_by`)

- `architecture.md` "Authority fails closed; advice fails soft" — **conforms**: the narrowing
  passes only on an observed `work_live is True`. An unreadable observation (None) still blocks.
- `api-contract.md` "Additive-first evolution" — **conforms**: one new `observed` key. The stats
  JSON shape is unchanged; only the verdict counts are re-derived.
- Other norms — **inapplicable**: no write path, network or schema version change.

## Build Chunks

### Chunk 01: The clear-reason verdict reads whether the session changed anything

- **Description:** Add a `session_changed` observation (from `gates.session_work_span`). The
  `stats` verdict rule becomes per gate.
- **Depends on:** none
- **Deliverables:** `plugin/lib/evidence.py` (key constant), `plugin/bin/prawduct-hook`
  (`_clear_observations`), `plugin/lib/stats.py` (verdict rule), `plugin/docs/governance-telemetry.md`,
  tests in `tests/test_stats.py` and `tests/test_stop_block_facts.py`.
- **Tests:** a read-only firing without notes is unclassified; one that changed files is a catch;
  notes present is a slip; a fact without `session_changed` is unclassified; the hook records the key.
- **Acceptance criteria:** the first two success bullets.
- **Done when:**
  1. Tests pass.
  2. Committed.

### Chunk 02: YOUR TURN may say DO NOT CLEAR while observed work runs

- **Description:** The Stop hook skips the `clear-verdict` refusal for `YOUR TURN` when
  `work_live` is observed True. The norm prose and the gate's own block text follow.
- **Depends on:** Chunk 01
- **Deliverables:** `plugin/bin/prawduct-hook`, `plugin/lib/gates.py` / `plugin/lib/standing_block.py`
  docstrings, `plugin/methodology/session-digest.md`, `plugin/methodology/session-hygiene.md`,
  `plugin/docs/governance-telemetry.md`, `tests/test_stop_verdict_defer.py`, and the change
  fragment `.prawduct/changes/clear-gate-telemetry.md`.
- **Tests:** YOUR TURN + DO NOT CLEAR with a live background task passes; with nothing live it
  blocks; COMPLETE + DO NOT CLEAR with a live task still blocks.
- **Acceptance criteria:** the last two success bullets.
- **Type:** cumulative-final
- **Done when:**
  1. Declared suite recorded green.
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved.
