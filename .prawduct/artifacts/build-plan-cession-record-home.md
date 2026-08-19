---
artifact: build-plan
version: 2
scope: cession-record-home
branch: docs/cession-record-home
depends_on:
  - artifact: architecture
governed_by:
  # Seeded via `prawduct-hook jurisdiction --artifacts-only` 2026-08-19. A prose-only
  # cycle: only the coherence norms reach it.
  - artifact: architecture
    dispositions:
      - "every fact has one home → conforms, and this cycle IS an application of it — the fact 'where a cession is recorded' currently has no home at all, which is why the first cession had to explain its own placement inside a change-log entry. This plan gives the fact one home and leaves the change-log entry pointing at it."
      - "goals and verification bind; prescribed method is advice → conforms — the Deliverables below read as advisory; the acceptance criteria bind."
      - "prawduct guides and reviews; it never implements → inapplicable because this cycle ships prose only, and edits prawduct's own north-star document."
      - "an independent reviewer never mutates the session it reviews → inapplicable because this cycle changes no reviewer and no mutation site."
      - "authority fails closed; advice fails soft → inapplicable because this cycle produces no gate, command, or verdict."
      - "local-first governance coordination → inapplicable because this cycle adds no network, daemon, or dependency."
      - "the plugin writes nothing into a governed repo except its own state and reconciled seams → inapplicable because no plugin writer changes; `documentation/purpose.md` is this repo's own framework-internal document and ships to no product."
      - "prawduct is written in Python and must never be specific to Python → inapplicable because this cycle ships prose only."
last_validated: 2026-08-19
---

## Requirements Confidence

**Level:** High

**Why:** The gap is stated precisely by the reporter and verified against the document this
session: `documentation/purpose.md` names the responsibility ledger as the instrument for
recording a cession and says outright it is not yet built (Cycle 3), so it reads as an
instrument in waiting — with no statement of what a ceder does *meanwhile*. When the first
deliberate cession happened (the work-cycle limit's compaction rationale, 2026-08-19,
backlog #687), the record landed in `.prawduct/change-log.md`, which is a log of *changes*,
not a register of who holds what under which assumption.

Backlog item: **#691**, `tag:3.3.5-era`. This plan is the second of two delaying the
v3.3.5 cut, by owner decision 2026-08-19.

**Scope note — this plan does NOT build the responsibility ledger.** That is Cycle 3 of the
cession program and this item explicitly does not pre-empt its design. The deliverable is a
*decision about the interim regime*, written where the next ceder will look.

**Open assumptions / unknowns:**

- [DECISION 2026-08-19: the interim regime is live — cessions ride the change-log until
  Cycle 3 lands; the ledger is NOT pulled forward into this release. Owner ruling, on the
  stated ground that the cheapest thing that ships wins while prawduct's own repo is
  mid-build. This was the one decision the chunk turned on; it is now closed, and the
  chunk is buildable.]
- [DECISION 2026-08-19: the acceptance criterion "no other prose in the repo now
  contradicts the stated regime" is bounded to the surfaces a cascade-search over the
  ledger / re-pricing / cession vocabulary actually reaches. Owner ruling: perfect
  coverage is not owed while the repo is mid-build. A missed surface is a later fix, not
  a reason to widen this chunk.]
- [ASSUMPTION: `documentation/purpose.md` remains the right home for the statement, since
  it is where the reader who needs it is already standing | LOW impact | user can override]

## Status

- [ ] Chunk 01: The interim cession regime is stated where a ceder will look

Context: Plan authored 2026-08-19; nothing built yet.

## Verification Strategy

Prose deliverable — verification is coherence, not execution. The chunk closes by reading
`purpose.md` end-to-end as a would-be ceder: someone who has just decided to cede a
mechanism and is looking for where to write it down. The test is whether that reader
finds an answer without having to infer one. The suite runs because the token-budget and
document-pinning tests are the executable contract on this file.

## Build Chunks

### Chunk 01: The interim cession regime is stated where a ceder will look

- **Description:** `purpose.md` presents the responsibility ledger as the instrument for
  re-pricing a mechanism, parenthesised "not yet built", and stops there. The absence
  reads as *pending* rather than as *unhandled*, which is what kept the gap invisible until
  a cession actually needed it. State which of the two regimes is live — the ledger, or
  the change-log — so the next ceder does not rediscover this. Then make the 2026-08-19
  cession reachable from whatever surface the statement names, so the regime has a worked
  first case rather than only a rule.

  **Cascade-search the claim, not just the code.** The relevant learning is that a
  mechanism change must be chased through the sentences that *describe* it, in the
  vocabulary a describing sentence would use — here, prose elsewhere that speaks of the
  ledger, of re-pricing, or of where a cession is recorded, which would silently contradict
  the new statement. `project-preferences.md` requires a norm's named-but-absent mechanism
  to be filed at the norm's birth; this chunk is that filing, one cycle late, so it should
  also leave the birth-filing obligation visibly satisfied.

  **Write no present-tense state claim.** "The ledger does not exist" is a fact that
  expires the day Cycle 3 lands, and a durable document must not carry one — phrase the
  statement so it stays true across that transition, or date it and name what supersedes it.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/program-purpose-and-cession.md` (the
  ratified four-cycle program that defines what Cycle 3 is), `.prawduct/change-log.md`
  (the 2026-08-19 cession entry that becomes the worked first case)
- **Deliverables:** `documentation/purpose.md` — the interim regime stated in the
  operating-rules list where the ledger is named; the 2026-08-19 cession reachable from it
- **Tests:** the existing document-pinning and token-budget tests over
  `documentation/purpose.md` must stay green; if the addition pushes a budget, the ceiling
  is ratcheted as part of this cut and not deferred — and only after cutting the class
  rather than the words
- **Acceptance criteria:** a reader of `purpose.md` alone can tell where to record a
  cession today; the statement survives Cycle 3 landing without becoming false; the
  2026-08-19 work-cycle cession is reachable from the named surface; no other prose in the
  repo now contradicts the stated regime
- **Type:** doc-only
- **Done when:**
  1. Acceptance criteria met and the suite passes
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status
