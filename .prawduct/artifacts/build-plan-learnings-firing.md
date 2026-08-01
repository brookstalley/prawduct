---
artifact: build-plan
version: 2
scope: learnings-firing
depends_on:
  - artifact: architecture              # the advice-fails-soft / authority-fails-closed split every new print site sits under
  - artifact: observability-strategy    # channel split and severity-prefix vocabulary for the new builder-facing output
  - artifact: api-contract              # additive-first evolution for the new `superseded-by=` metadata key
governed_by:
  - artifact: architecture
    dispositions:
      - "authority fails closed, advice fails soft → conforms — every surface this plan adds is ADVICE printed to the builder. No gate reads it, no exit code changes, and a delivery line that cannot be computed is omitted rather than blocking the record it rides on."
      - "plugin writes only its own .prawduct/ state → conforms — the supersession path writes learnings.md and learnings-detail.md, both already owned by `audit-learnings --apply`."
      - "prawduct guides and reviews, never implements → conforms — the delivery lines pose a question to the builder; none of them inspect or edit product code."
  - artifact: observability-strategy
    dispositions:
      - "stable severity-prefix vocabulary, stdout/stderr channel split → conforms — delivery lines ride stdout beside the confirmation they annotate, exactly as `_BATCH_FIX_DIRECTIVE` already does."
      - "no prawduct-internal identifiers in product-emitted text → conforms — the lines name the builder's own tests and claims, never a prawduct finding id."
  - artifact: api-contract
    dispositions:
      - "additive-first evolution → conforms — `superseded-by=` is a new optional key in an existing optional comment; absent metadata keeps meaning 'active, no lifecycle metadata', and no existing flag or exit code is repurposed."
last_validated: 2026-07-31
---

# Build Plan: Rules That Fire

## Problem

`.prawduct/learnings.md` holds 159 rules. A product repo (discodon) running the latest
prawduct spent one cycle whose retrospective — `documentation/LEARNINGS_VERIFYING_TEST_
INFRASTRUCTURE.md` in that repo — records four false claims and twelve Critic rounds. Every
one of those failures was already covered by a rule in this file.

The decisive evidence is line 292:

> Anything in a durable artifact that one command could check is a CLAIM — including an
> identifier, a count, or a facet value, not just a rationale.

That is the general, upleveled, well-worded rule the corpus supposedly lacks. It exists, it
covers all four failures, and it did not fire. **The corpus does not have an authoring
problem. It has a delivery problem.** A rule stored in a file that is read at session start
and never again competes with the entire rest of the context by the time the claim gets
written.

The design precedent is `_BATCH_FIX_DIRECTIVE` — not stored, but *printed by code at the exact
moment the builder holds a set of findings*, built because the file-stored version of the same
rule was not firing.

**It is a precedent, not evidence.** It lives on the unmerged `feature/clear-signal-and-batch-fix`
branch and has never shipped, so nothing has been observed firing in the field and this plan may
not cite it as proof that delivery works. That branch is also where "warnings and notes gate
nothing" replaces develop's "**Warnings** should be addressed — the Critic only uses WARNING when
confident." Both halves of the round-multiplication fix are in flight there; neither reached
discodon.

Which sharpens the diagnosis rather than softening it. On *shipped* prawduct the round-count
pressure is real and partly instruction-driven: the guidance a builder actually reads pushes
toward addressing warnings, and no code-delivered directive counters it at the moment findings
land. That two independent lines of work — discodon's retrospective and that branch — converged
on the same defect is the strongest signal here that it is structural rather than one builder's
bad day.

## Success

1. At least two rules move from stored to **delivered**: emitted by code at the moment of the
   action they govern, on a trigger narrow enough that they are never noise.
2. Retiring a rule **by supersession** becomes a first-class, auditable operation — the
   historical entry names the rule that replaced it, so a reader who remembers the old rule
   finds a forwarding address rather than a hole.
3. The corpus shrinks. Two near-duplicate families (counted by the commands in Scaffolding,
   never transcribed here — learning 322) collapse into their existing general rules.
4. Six mechanisms from the discodon retrospective land as **two** rules, not six.

## Out of Scope

- Rewriting the ~140 rules outside the two identified families.
- Any change to what the Critic reviews or how gates compose. This plan adds advice, not authority.
- The change-log ledger, and everything on the `record-mechanization` plan.
- Automatic detection of unfalsified claims. The delivery lines *ask*; nothing here judges the answer.

## Requirements Confidence

**High** on the problem and on Chunks 01–02. The delivery thesis is backed by a natural
experiment inside this repo: the one rule that was moved from storage to code-delivery is the
one rule whose sibling failure mode (round multiplication) still recurred only in the half the
directive does not address (*entering* a round versus batching *within* one).

**Medium** on Chunk 03's collapse ratio.

- [ASSUMPTION: the ~14-rule assertion family collapses into line 292 without losing a distinction
  worth keeping | HIGH impact | user can override] — three members carry second-order points a
  merge could silently drop: 298 (the falsifying query can itself carry the defect it hunts),
  27 (a completeness claim must never be a count of sites fixed), and 286 (a rationale you
  *reached for* is the one to verify). Chunk 03 resolves this per-rule with an explicit
  keep/merge call, and the collapse does not proceed until the map is approved.
- [ASSUMPTION: printing a delivery line on a narrow trigger reads as help rather than nagging
  | MED impact | user can override] — mitigated by conditioning each line on state the builder
  just changed, never on every invocation.

## Status

- [ ] Chunk 01: Deliver the two rules at their moment
- [ ] Chunk 02: Supersession as a lifecycle event
- [ ] Chunk 03: Collapse the two families, add the two new rules

## Scaffolding

**Family membership is derived, never transcribed.** Both counts in this plan come from
`scripts/learning-families.py` (added in Chunk 03), which classifies by heading text and prints
the roster. Cite the command, never the digits.

## Verification Strategy

- **Chunk 01** — unit tests over the two print sites: the line appears when its trigger holds,
  is absent when it does not, and its absence never changes an exit code. Each assertion is
  mutation-proved: invert the trigger, watch the test go red.
- **Chunk 02** — unit tests over `audit_learnings`: an entry with `superseded-by=` and no
  sentinel retires under `--apply`; the historical entry carries the forwarding pointer; a
  `superseded-by=` naming a heading that does not exist is an error, not a silent retirement.
- **Chunk 03** — the collapse is executed *through* Chunk 02's mechanism, which dogfoods it.
  `scripts/learning-families.py` re-run after the collapse is the completeness check.

## Build Chunks

### Chunk 01: Deliver the two rules at their moment

- **Description:** Move two rules from storage to code-delivery, each on a trigger narrow enough
  to never be noise.

  **(a) Green is evidence only about what could have made it red.** The moment is
  `prawduct-hook test-evidence record` (`plugin/bin/prawduct-hook:2025`) — where the builder
  stamps "the suite is green" into the record the gates read. Trigger: the record's
  `changes_referenced` is non-empty, i.e. the builder just added or changed judged code. The
  line names the check, not the virtue: *for each new test, what change would turn it red? A
  fixture that never reaches the subject, an assertion that cannot tell the two orderings
  apart, and a branch that depends on a file that happens to exist locally all pass
  identically.* Silent when nothing judged changed — a restamp or a docs-only cycle prints
  nothing.

  **(b) A claim needs its falsifier run.** The moment is `critic-consolidate`, beside
  `_BATCH_FIX_DIRECTIVE`. Trigger: the review recorded resolutions (i.e. the builder is about to
  write "fixed" somewhere). The line: *a resolution is a claim about the tree. Say which command
  you ran, not that you are confident.*

  **(b) is BLOCKED on a branch decision and is not built until it resolves.** The constant it
  sits beside does not exist on `develop`; it lives on the unmerged
  `feature/clear-signal-and-batch-fix`. Building (b) here would either duplicate that constant or
  conflict with it on merge. (a) touches `bin/prawduct-hook` only and is unaffected — it proceeds
  on `develop` now.

- **Depends on:** (b) only — the clear-signal branch landing, or this branch rebasing onto it
- **Artifacts consumed:** `observability-strategy.md` (channel split), `architecture.md` (advice fails soft)
- **Deliverables:** two module-level directive constants beside `_BATCH_FIX_DIRECTIVE`; both
  print sites; tests
- **Tests:** `tests/test_critic_consolidate.py`, `tests/test_test_evidence.py` — trigger-on,
  trigger-off, and exit-code-unchanged for each
- **Acceptance criteria:** each line appears exactly on its trigger; neither changes any exit
  code; both are mutation-proved (invert the trigger → red)
- **Type:** code
- **Done when:**
  1. Acceptance criteria met
  2. `/prawduct:critic` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

### Chunk 02: Supersession as a lifecycle event

- **Description:** `audit_learnings_cmd.py` models exactly one retirement reason — a declared
  `sentinel=` test that now passes ("structurally enforced"). It has no concept of a rule
  retired because a *broader rule* replaced it, which is what every consolidation is. Today that
  leaves consolidation as an unauditable hand-edit, which is precisely why a corpus reaches 159
  rules with two near-duplicate families in it: adding is cheap and merging is not.

  Add `superseded-by=<heading-prefix>` to the recognized metadata keys. An entry carrying it
  retires under `--apply` with no sentinel run, and its historical entry records the forwarding
  pointer. A `superseded-by=` whose target heading does not resolve in `learnings.md` is an
  `errors` entry and the retirement does **not** apply — the same fail-closed posture the
  failing-sentinel path already takes, and the direct analogue of learning 31 (an absence-claim
  must cite a path that resolves).

- **Depends on:** nothing (parallel with 01)
- **Artifacts consumed:** `api-contract.md` (additive-first evolution)
- **Deliverables:** `superseded-by` in `_KNOWN_METADATA_KEYS`; retirement path; forwarding
  pointer in the historical section; `--json` shape extended additively
- **Tests:** `tests/test_audit_learnings.py` — retires without a sentinel; forwarding pointer
  present; unresolvable target errors and does not apply; sentinel path unchanged
- **Acceptance criteria:** the four cases above pass and are mutation-proved; no existing
  audit-learnings behavior changes
- **Type:** code
- **Done when:**
  1. Acceptance criteria met
  2. `/prawduct:critic` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

### Chunk 03: Collapse the two families, add the two new rules

- **Description:** Two parts, in order.

  **(a) The two genuinely-new rules from the discodon retrospective.** Six mechanisms, two
  rules — the rest are already-covered instances.

  1. *Green is evidence only about what could have made it red* — absorbs mechanisms 1 (the
     fixture never reaches the subject), 2 (machine state as an undeclared input), 4 (a
     load-dependent race in test setup), 5 (silent-by-construction properties: a stage whose
     value is speed needs a test that fails when it stops being fast), and 6 (mutation testing
     is one-directional — reverting removes the damage alongside the fix, so it is blind to
     what your change broke beside it; pair it with branch coverage of the function you
     touched). Existing line 15 becomes an instance and retires into it via Chunk 02.
  2. *A text-anchored edit changes a neighborhood, not a point* — mechanism 3, plus mechanism
     6's concrete defect. Inserting at a `def` line lands the new function between the next one
     and its decorator; restructuring `try/except` into `try/except/else` strands the fallback
     inside `else`. Both compile, both stay green. This is the defect class the agent's own
     text-anchored Edit tool manufactures, and nothing in the corpus covers it.

  **(b) The collapse.** Write `scripts/learning-families.py` to classify the corpus, then
  produce a per-rule keep/merge map for both families. The assertion family merges into
  existing line 292; the discriminating-test family merges into the new rule (1) above.
  **The map is presented for approval before any retirement is applied** — three members carry
  second-order points that a merge could silently drop (see Requirements Confidence).

- **Depends on:** Chunk 02 (the mechanism the collapse executes through)
- **Artifacts consumed:** the discodon retrospective; `learnings.md`; `learnings-detail.md`
- **Deliverables:** two new rules with narratives in `learnings-detail.md`;
  `scripts/learning-families.py`; the approved collapse applied via `audit-learnings --apply`
- **Tests:** the family script re-run post-collapse is the completeness check; the retirement
  path is already tested by Chunk 02
- **Acceptance criteria:** both new rules present with narratives; every retired rule carries a
  resolvable forwarding pointer; the family script reports both families reduced to their
  general rule plus whatever the map explicitly kept
- **Type:** code
- **Done when:**
  1. Acceptance criteria met
  2. Collapse map approved by the user before `--apply` runs
  3. `/prawduct:critic final` run and blocking findings resolved
  4. Chunk marked `[x]` in Status

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** run `prawduct-hook test-evidence record` after a chunk that touched
judged code and see the green-is-evidence line fire — then run it on a docs-only change and see
it stay silent.

## Governance Checkpoints

- Chunk 01 and 02 are independent and may be built in either order or in parallel.
- Chunk 03(b) has a **hard stop** before `--apply`: the collapse map is approved by the user
  first. Collapsing a rule the project earned is not a call this plan makes unilaterally.

## Related open backlog items

To be reconciled at Chunk 03 — the "confirmed by mutation names its own falsifier" idea from
the retrospective's structural candidate #1 is folded into Chunk 01(a)'s delivery line rather
than filed separately.
