---
artifact: build-plan
version: 2
scope: retire-clear-verdict
branch: feature/retire-clear-verdict
base: develop
working-branches: []
partition: serial, because it is one Stop check, its sink, its reader and the prose that describes it
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable because no reviewer path changes"
      - "authority fails closed; advice fails soft → conforms; the check becomes advice, and a failed record prints a NOTE and never changes the Stop's exit"
      - "local-first → conforms; the record goes to the clone-local evidence store"
      - "the plugin writes nothing into a governed repo except its own state → conforms; only the evidence store is written"
      - "written in Python, never specific to Python → inapplicable because the check reads the closing block, not product code"
      - "guides and reviews, never implements → inapplicable because no product code is written"
      - "goals and verification bind, method is advice → conforms; the owner's goal (stop blocking, keep measuring) is pinned by tests"
      - "every fact has one home → conforms; the verdict rule stays in stats.SLIP_WHEN_OBSERVED and is reused, and the standing-block rule stays in session-hygiene.md"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms; removes a Stop round-trip and adds no review"
      - "proportionality ratchets both ways → conforms; this is the ratchet's removal arm, decided by the owner on 3.8 data (#1044), and the measurement it keeps is the yield query"
      - "state-file growth is advisory, never a hard block → inapplicable because no state file grows"
      - "review rigor is stage-keyed → conforms; one cumulative review at the boundary"
depends_on:
  - plugin/docs/governance-telemetry.md
  - plugin/methodology/session-hygiene.md
last_validated: 2026-11-10
---

## Goals

**Response taken:** Proceed, on the owner's ruling of 2026-11-10: "Yes retire clear-verdict but
keep measurement" (#1044).

**Product:** A turn that closes `YOUR TURN` or `COMPLETE` with `DO NOT CLEAR` is no longer sent
back. Each such firing is still recorded with its reason and observations, so `stats` keeps
scoring catch and slip and the decision can be revisited.

**Architecture:** Firings go through the existing control sink under a new `stop-observed:`
prefix (`evidence.append_stop_observation`), apart from `stop-gate:` blocks, so a reader counting
blocked Stops never counts a Stop that passed. `stats` reports them under *observed only* with the
same verdict rules. The detection rule is unchanged, including the `YOUR TURN` + observed-work
exemption, so counts compare with 3.8's blocks.

**Decisions made mid-build:**
- `clear-verdict` leaves `hooks/gates.json`. The registry lists gates that block, for attribution
  and the new-gate banner.
- The hook prints nothing on a firing. A message on a Stop that passes would teach the model to
  ignore hook output. *Inferred.*
- Pre-retirement `stop-gate:clear-verdict` facts stay where they are and are read as before, so 3.7
  and 3.8 blocks remain comparable with post-retirement observations.

**Level:** High.

## Build Chunks

### Chunk 01: clear-verdict observes instead of blocking

- **Description:** Stop blocking on the clear-verdict check, record its firings as observations,
  report them in `stats`, and update every surface that says it refuses.
- **Depends on:** none
- **Deliverables:** `append_stop_observation` and `STOP_OBSERVED_PREFIX` in
  `plugin/lib/evidence.py`; the hook records instead of blocking; the *observed only* section in
  `plugin/lib/stats.py`; the registry row removed; `session-hygiene.md`, `governance-telemetry.md`,
  the NFR exception, the digest inventory and the cross-cutting row updated; tests.
- **Tests:** in-process Stop tests with real git pin what each firing records and that it does not
  block; the subprocess tests pin the exit codes; stats tests pin that observations are scored and
  never counted as blocks or refusals. All of them were seen to fail against the old code.
- **Acceptance criteria:** a contradicting close exits 0 and records one `stop-observed:clear-verdict`
  fact with its reason and observations; `stats` shows it under *observed only*; the clear-reason
  gate still blocks.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and the suite passes
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
