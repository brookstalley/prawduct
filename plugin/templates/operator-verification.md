# Operator Verification Queue

<!-- Append-only queue of pre-merge human-verification items for visual /
     live-integration changes that automated tests can't fully cover.

     Each entry is a level-2 heading: `## VRF-<id> — <Chunk N> — <one-line title>`.
     The first non-blank body line MUST be `**Status:** pending | verified | accepted`.

     That shape is the ONLY one recognised. Anything else — bullets, or a single
     `## Pending` heading with items beneath it — parses as preamble, not as
     entries. When `check-operator-verification` finds a file holding content it
     could not parse as a single entry, it REFUSES rather than reporting an
     empty queue: a queue nobody could read is not a queue with nothing in it,
     and reporting the second leaves the gate blocking on nothing while entries
     pile up unseen.

     When `operator_verification_required: true` is set in project-state.yaml,
     `/pr create` BLOCKS if any entry has `**Status:** pending`. Drain entries
     via `prawduct-hook verify-operator-verification <VRF-id>`, or
     override for the current PR with `/pr create
     --accept-pending-verification "rationale"` (the rationale is recorded
     into each entry as an `**Accepted:**` line — this file is the work-log).

     `**Status:**` takes the BARE token and nothing else. The parser reads one
     word and treats anything after it as malformed, failing CLOSED to `pending`
     — so `verified (2026-07-17, throwaway repo foo)` counts as PENDING and the
     gate blocks on work that is done. Put the detail on the `**Verified:**` /
     `**Accepted:**` line beneath, which is where the tooling writes it anyway.
     `superseded`, `n/a`, `wontfix` are not statuses: an entry that must NOT be
     drained by running its steps is `accepted`, with that as its rationale.

     This file is append-only history. Entries stay forever after they're
     verified or accepted; don't delete them.

     SPLIT THE DEFERRAL BEFORE YOU WRITE THE ENTRY. This is the rule this queue
     cost the most to learn, and it belongs at the moment of deferral rather
     than at the moment of drainage. Every claim you are about to defer splits
     in two:

       1. CAN THIS BE TRUE IN PRINCIPLE? — static, decidable today, from the
          code and the documented rules. A matcher's ability to match a given
          agent type. Whether a grant's spelling can cover the call the prose
          writes. Whether an exit code is mapped.
       2. DOES THE HARNESS ACTUALLY DO IT? — delivery. Does the event fire, does
          the session render it, does the real API behave as the fake does.

     ONLY THE SECOND HALF BELONGS IN THIS QUEUE. The first half is a test you
     can write now, and writing it now is the whole point: a deferral that
     carries a statically-decidable claim along with it launders an untested
     assertion into a queue nobody reads. That is not hypothetical — one entry
     here deferred three integration facts together on the grounds that "matcher
     semantics vary by version". True of two of them. False of the third, which
     was decidable that day, was broken, and sat unexamined for seventeen days
     while the entry that named it waited on a live session.

     The tell that you have split badly: a "why a human check" paragraph that
     argues from the hardest fact in the entry and then covers the easy ones by
     association. Write the reason PER FACT, and any fact whose reason is really
     "I have not checked" goes back to being work, not a queue item.

     A DEFERRAL NEEDS AN OWNER AND A TRIGGER, not just a status. An entry no
     machine this project has can ever discharge is not pending work — it is a
     permanent resident, and it makes a full queue indistinguishable from a
     stalled one. Name whose harness answers it and when you will ask; if the
     answer is "nobody's, ever", `accepted` with that stated is the honest
     status, not `pending` forever.

     To opt the project in: set `operator_verification_required: true` in
     `.prawduct/project-state.yaml`. **Drain before you flip.** The flag turns
     the queue into a blocking gate on the next PR, so a queue with pending
     entries that need harnesses nobody has scheduled will stop work rather than
     start it. Give every entry a disposition first — verify, accept with a
     rationale, or re-scope — and check what the parser counts, not what you
     count: `prawduct-hook check-operator-verification` is the number the gate
     will use. -->

<!-- New entries go below this line. Suggested format:

## VRF-001 — Chunk N — Short title

**Status:** pending
**Added:** YYYY-MM-DD (Chunk N, F-id)
**Where to verify:** <screen, CLI invocation, dashboard URL, etc.>

**Verify:**
- <observable behavior 1>
- <observable behavior 2>

-->
