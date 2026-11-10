---
artifact: build-plan
version: 2
scope: revisit-due-issues
branch: fix/revisit-due-issues
base: develop
working-branches: []
partition: serial, because it is one probe, its tests and the prose that describes it
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable because no reviewer path changes"
      - "authority fails closed; advice fails soft → conforms; this is advice, and an unreadable store is reported (CouldNotLook), never read as nothing due"
      - "local-first → conforms; the probe reads the local backlog cache and makes no network call"
      - "the plugin writes nothing into a governed repo except its own state → conforms; the probe only reads"
      - "written in Python, never specific to Python → inapplicable because the probe reads backlog metadata, not product code"
      - "guides and reviews, never implements → inapplicable because no product code or config is written"
      - "goals and verification bind, method is advice → conforms; the acceptance criteria are behavioural and red-verified"
      - "every fact has one home → conforms; `revisit:` stays in the issue's prawduct block, read and not copied; stale restatements were corrected, not added beside"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → conforms; one short chunk, one cumulative review"
      - "proportionality ratchets both ways (a control names its expected yield) → conforms; the yield is dated `revisit:` clocks passing on open items, six of them in this repo on 2026-11-10, two due within ten days"
      - "state-file growth is advisory, never a hard block → inapplicable because no state file grows"
      - "review rigor is stage-keyed → conforms; the boundary review ran as cumulative"
depends_on:
  - plugin/docs/norms.md
  - documentation/backlog-service-cache-spec.md
last_validated: 2026-11-10
lifecycle: completed
archived: 2026-11-10
released_in: v3.8.1
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Goals

**Response taken:** Proceed. This is a bug with a repro. On the GitHub Issues backend a dated
`revisit:` never fires, though `docs/norms.md` § Exceptions expire says dated clocks fire
mechanically, and #987 named the `revisit-due` advisory as the prompt for a run due 2026-11-10.
The owner approved the fix on 2026-11-10 ("Yes to revisit").

**Product:** A past-dated `revisit:` on an open item raises the `revisit-due` advisory on both
backends.

**Architecture:** The probe selects its backend the way `dead-why` and `stalled-transition` do
(`_live_scope`). After the move to Issues it reads each open item's block field through
`cachequery.open_items` and `encode.parse_block`. When the store cannot answer, it returns the
shared `backlog-cache-unreadable` advisory as `CouldNotLook`.

**Decisions made mid-build:**
- The cache spec §2.1 retirement named its own lifting condition (a write path for the field).
  #564 met that condition, so this restores the probe under a ruling dated 2026-11-10 instead of
  overriding the spec.
- `TestSilentAgainstThisRepo` leaves `revisit-due` out of its silence claim. After the move to
  Issues the probe's input is the live tracker's dates, not committed state, and keeping it in
  would turn the suite red on a calendar day. *Inferred; the owner confirmed both decisions on 2026-11-10.*

**Level:** High.

## Build Chunks

### Chunk 01: revisit-due reads the backlog cache after the move to Issues

- **Description:** Add the cache arm to `probe_revisit_due`, declare its shared outage advisory,
  and update every surface that described it as retired.
- **Depends on:** none
- **Deliverables:** the cache arm in `plugin/lib/norm_probes.py`; tests in `tests/test_norm_probes.py`
  (it fires on an open past-due issue; it is quiet on a future date, an event trigger or a closed
  item; it reports an unreadable store; one outage advisory across three probes); the restoration
  recorded in the cache spec, the post-sync advisory spec, the API contract and the
  `backlog_probes.post_cutover` docstring; the change fragment.
- **Tests:** unit with a real cache built from the transport fake; red-verified against the old probe.
- **Acceptance criteria:** the new tests pass and fail on the old code; run against this repo's
  live cache, the probe returns #987 for 2026-11-11 and nothing for 2026-11-10.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and the suite passes
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
