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
     `/prawduct:pr create` BLOCKS if any entry has `**Status:** pending`. Drain
     entries via `prawduct-hook verify-operator-verification <VRF-id>`, or
     override for the current PR with `/prawduct:pr create
     --accept-pending-verification "rationale"` (the rationale is recorded
     into each entry as an `**Accepted:**` line — this file is the work-log).

     `**Status:**` takes the BARE token and nothing else. The parser reads one
     word and treats anything after it as malformed, failing CLOSED to `pending`
     — so `verified (2026-07-17, throwaway repo foo)` counts as PENDING and the
     gate blocks on work that is done. Put the detail on the `**Verified:**` /
     `**Accepted:**` line beneath, which is where the tooling writes it anyway.
     `superseded`, `n/a`, `wontfix` are not statuses: an entry that must NOT be
     drained by running its steps is `accepted`, with that as its rationale.

     It also sits on a line of its own: the entry's first non-blank body line,
     holding nothing but `**Status:** <word>`. A compact header that runs the
     status in with other metadata —

         **Chunk:** <chunk> - **Raised:** <date> - **Status:** pending

     — is the shape an agent naturally writes, and it is not read as a status:
     the entry keeps counting as pending until the line is split. The strict
     shape is deliberate; the parser will not accept a second one.

     This file is append-only history. Entries stay forever after they're
     verified or accepted; don't delete them.

     SPLIT THE DEFERRAL BEFORE YOU WRITE THE ENTRY. Every claim you are about
     to defer splits in two:

       1. CAN THIS BE TRUE IN PRINCIPLE? — static, decidable today from the code
          and the documented rules (can a matcher match this agent type; is this
          exit code mapped).
       2. DOES THE HARNESS ACTUALLY DO IT? — delivery: does the event fire, does
          the session render it, does the real API behave as the fake does.

     ONLY THE SECOND HALF BELONGS IN THIS QUEUE. The first half is a test you
     can write now. Give each fact its own reason; a fact whose reason is really
     "I have not checked" is work, not a queue item.

     A deferral needs an owner and a trigger: name whose harness answers it and
     when you will ask. If the answer is "nobody's, ever", the honest status is
     `accepted` with that stated.

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
