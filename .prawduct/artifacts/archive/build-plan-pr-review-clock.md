---
artifact: build-plan
version: 2
scope: pr-review-clock
branch: fix/845-pr-review-clock
backlog: brookstalley/prawduct#845
depends_on:
  - artifact: data-model
governed_by:
  - artifact: data-model
    dispositions:
      - "no model sits in a fact's write path → conforms, and is why the interval ends at the evidence file's mtime rather than the reviewer's `timestamp`: the model writes the field, the filesystem writes the mtime. The ledger is observability, not the Critic data plane, but the same reasoning applies to a code-read clock"
      - "facts are immutable and append-only → conforms: one append per review, no edit in place. The new key is written once, at append"
      - "derived views are never authoritative → inapplicable because this plan touches no gate and no derived view; the clock is telemetry that no verdict reads"
      - "a governance document reaches a terminal state, never deleted → inapplicable because this plan archives or deletes no governance document"
      - "backlog issue titles follow the issue standard on every write path → inapplicable because this plan writes nothing to the backlog store"
      - "a fact from a newer schema is a loud block → inapplicable because this plan writes no evidence-store fact, and the ledger key it adds is optional and ignored by older readers (the ledger's `schema_version` is unchanged)"
      - "two stores, two lifetimes → conforms: the markers and the ledger stay per-clone and gitignored"
      - "`backlog_service_repo` selects the authoritative backlog → inapplicable because this plan does not read the backlog"
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning; persisted data independently schema-versioned → conforms: one optional envelope key is added, readers fall back to `ts` when it is absent, so every existing ledger row reads exactly as before and no schema bump is needed"
      - "exit codes are the contract; stable severity prefixes; errors attributed → conforms: `ledger-append` keeps exit 0 on every clock outcome, as before. A refused measurement is a named `duration:` reason, never an error"
      - "additive-first evolution → conforms: no flag, exit code or `--json` key changes meaning. The `duration:` line gains new reasons and a longer measured sentence, which begins with the same words as before"
partition: serial — two chunks, independent files, run by one agent
last_validated: 2026-09-21
lifecycle: completed
archived: 2026-09-24
released_in: v3.6.1
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

# Build plan — the PR review clock survives its findings being fixed, plus the window's readout

## Requirements Confidence

**Level:** High

**Why:** #845 records the mechanism (three reproductions), rules out relaxing the tree check, and
names two candidate anchors, `commit_reviewed` and the evidence write time. This plan uses both. The
owner approved building it on 2026-09-21, while sibling repos are collecting the measurement window
v3.6.1 is waiting on.

`[DECISION: interval end = the evidence file's mtime, not the reviewer's `timestamp` field | the
reviewer writes `timestamp` itself, so using it would put a model back in the write path of a
code-read clock (data-model: governance numbers come from code-written facts). The mtime comes
from the filesystem. Only `pr_number` may be edited afterwards, and that edit happens after the
append (Create Step 5). If some other edit moves the mtime, the interval gets longer and stays
under the plausibility bound; it never gets shorter | vetoable]`

`[DECISION: an evidence file whose mtime is earlier than the mark is not this dispatch's review →
not measured, with a named reason | an older review's file left in place by a dispatch that never
wrote one would otherwise attest a negative or wrong interval]`

## Chunk 1: PR clock anchors on the reviewed tree and the evidence write

**Delivers:** for `review.pr`, `ledger-append` checks the mark against the evidence's
`commit_reviewed` (resolved to a full sha) instead of HEAD, and ends the interval at the evidence
file's mtime, which it writes as `review_written_at`. `review.critic` is unchanged. The readers
(review-stats, pr-review-yield, measure-consumer-overhead) end the interval at `review_written_at`
when it is present and at `ts` otherwise, through one helper in `review_dispatch`.

**Done when:**
- A PR review marked at tree A, whose findings are fixed in commit B before the append, records
  `dispatched_at` and `review_written_at`, and every reader measures write minus mark.
- A mark from a tree other than `commit_reviewed` is still refused.
- An evidence file that predates the mark is refused with a named reason.
- The three readers agree on an event carrying `review_written_at` (one-home test).
- `data-model.md` records the decision; the pr SKILL's Step 3/4 prose no longer says the interval
  runs to the append.
- Targeted tests green; `/prawduct:critic`.

## Chunk 2: measurement-window readout

**Delivers:** a script that answers the question v3.6.1 is waiting on, written before the data is
seen: fleet review rows split by plugin version around the 2026-09-19/20 interventions, clocked rows
only, with the size of every cell printed so a thin cell reads as thin.

**Carried in from Chunk 1's review (O-4, accepted onto this commit):** `review_dispatch.py`'s module
docstring says the HEAD check "threw away the measurement of every PR review that found something".
That is history. Drop the clause so the sentence states the mechanism.

**Done when:** the script runs against the fleet today and reports how many clocked rows each cell
holds; `/prawduct:critic`.

## Status

- [x] Chunk 1: PR clock anchors on the reviewed tree and the evidence write
- [x] Chunk 2: measurement-window readout
