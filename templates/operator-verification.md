# Operator Verification Queue

<!-- Append-only queue of pre-merge human-verification items for visual /
     live-integration changes that automated tests can't fully cover.

     Each entry is a level-2 heading: `## VRF-<id> — <Chunk N> — <one-line title>`.
     The first non-blank body line MUST be `**Status:** pending | verified | accepted`.

     When `operator_verification_required: true` is set in project-state.yaml,
     `/pr create` BLOCKS if any entry has `**Status:** pending`. Drain entries
     via `prawduct-hook verify-operator-verification <VRF-id>`, or
     override for the current PR with `/pr create
     --accept-pending-verification "rationale"` (the rationale is recorded
     into each entry as an `**Accepted:**` line — this file is the work-log).

     This file is append-only history. Entries stay forever after they're
     verified or accepted; don't delete them.

     To opt the project in: set `operator_verification_required: true` in
     `.prawduct/project-state.yaml`. -->

<!-- New entries go below this line. Suggested format:

## VRF-001 — Chunk N — Short title

**Status:** pending
**Added:** YYYY-MM-DD (Chunk N, F-id)
**Where to verify:** <screen, CLI invocation, dashboard URL, etc.>

**Verify:**
- <observable behavior 1>
- <observable behavior 2>

-->
