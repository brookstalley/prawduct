---
artifact: build-plan
version: 2
scope: change-log-lifecycle
branch: fix/change-log-lifecycle
depends_on: []
last_validated: 2026-09-10
lifecycle: active
maintained: true
---

## Requirements Confidence

**Level:** High. The defect was measured, not inferred: 1,531 KB across 387 entries, 312 of them
carrying `release=`. Both causes were read out of the file and the code rather than guessed, and the
owner ruled on the two open parameters (retention boundary, threshold shape) before this plan was
written.

## What Problem This Solves

**The change-log has no lifecycle.** Every other durable record here has one — `learnings.md`
retires rules to `learnings-history.md` through `audit-learnings --apply`, build plans move to
`archive/` through `archive-plan` — and the change-log has a header comment telling authors to
append at the top and nothing that ever takes an entry out. It grew monotonically for six months.

The one archive that ever happened proves the shape of the failure rather than disproving it:
pre-2026-03-22 entries were hand-moved into `project-state.yaml` under `change_log_history`, which
is a live contributor to *that* file's own oversized advisory. A relocation is not a lifecycle.

**A second, independent cause:** mean entry size went 781 B in March to ~4–5 KB now. This plan does
not address that (see Out of Scope) — but it is why the fix cannot be "get under 40 KB".

## What Success Looks Like

1. `prawduct-hook archive-change-log` exists and moves shipped entries out of the live log into
   `.prawduct/change-log-history.md`, leaving a forwarding pointer. Re-runnable, `--apply`-gated.
2. **No gate's answer changes.** The release-pending set, the unclassifiable-pending set, and the
   tag-validation verdict are identical before and after an archive run — asserted by the command
   itself, which refuses rather than reports when they differ.
3. The live log holds release-pending + untagged + the current minor line (v3.4.x); v1.x–v3.3.x is
   in history. ~1.1 MB moves.
4. The change-log has a **per-file threshold** that a bounded live file can meet, so the advisory
   fires when the lifecycle has stopped running rather than permanently.
5. The release process runs the archiver, so this happens again without anyone deciding to.

## Out of Scope

- **Entry size.** Shrinking how entries are written, or splitting narrative into a detail file, was
  offered and not chosen. The archiver bounds the file by release cadence; entry prose is untouched.
- **`project-state.yaml`'s `change_log_history` block.** It has its own advisory and its own
  decision; folding it in here would repeat the relocation this plan exists to end.
- **The `merge=union` gitattributes advisory** on the same file — adjacent, separate.
- **Backfilling `release=` onto untagged historical entries.** Untagged is not mistagged; the gate
  has never claimed authority over pre-convention history, and this plan does not give it any.

## Status

- [x] Chunk 01: The archiver, and the invariant that makes it safe
- [ ] Chunk 02: Run it — the one-time cut, and the live log's own lifecycle statement
- [ ] Chunk 03: A threshold that means something, and a release step that runs the archiver

### Chunk 01: The archiver, and the invariant that makes it safe

- **Depends on:** —  ·  **Type:** code  ·  **Critic mode:** chunk
- **Description:** `prawduct-hook archive-change-log [--keep-minor X.Y] [--apply] [--json]`.
  Selects entries carrying a `release=` whose version falls below the kept minor line, moves them to
  `.prawduct/change-log-history.md` (newest first, same format, append-only), and rewrites nothing
  else. Default `--keep-minor` is the current version's line, read from the version files
  `project-state.yaml` already declares — never hardcoded.
- **The safety invariant is the deliverable, not a bonus.** Before and after, the command computes
  `release_pending_entries`, `unclassifiable_pending_entries` and `validate_change_log_tags` over
  the live log. If any of the three differ, it writes nothing and exits non-zero naming what moved.
  An entry with no `release=` is never selected — that absence is the release-pending marker, and
  dropping one unships work silently. This is the same silent-drop family as #450.
- **Tests:** unit — selection by version line, including the boundary (`v3.3.4` moves, `v3.4.0`
  stays) and a malformed `release=` value (refuse, don't guess); the invariant firing on a doctored
  log that would drop a pending entry; idempotence (a second run moves nothing); `--apply` absent
  means no write. Integration — the real 387-entry log, asserting the pending set is byte-identical
  across the run.
- **Acceptance criteria:** `archive-change-log` with no `--apply` reports the move set and writes
  nothing; with `--apply` the two files together contain every entry the original did, and
  `check-releasability` returns the same verdict before and after.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: Run it — the one-time cut, and the live log's own lifecycle statement

- **Depends on:** Chunk 01  ·  **Type:** cleanup  ·  **Critic mode:** chunk
- **Description:** Run the archiver for real (`--keep-minor 3.4 --apply`), moving ~312 entries and
  ~1.1 MB into `change-log-history.md`. Then rewrite the live log's header comment: today it says
  "append new entries at the top" and names `project-state.yaml` as where history went. It must
  instead state the lifecycle — what stays, what leaves, what moves them, and that history is a
  redirect rather than a hole.
- **Tests:** the integration test from Chunk 01 covers the real corpus; no new test is owed for
  running a tested command. The header is prose and is graded by reading.
- **Acceptance criteria:** `check-releasability` verdict unchanged from the pre-run capture;
  `check-change-log-entry` still passes on this branch; the history file's entry count plus the live
  file's equals 387.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 03: A threshold that means something, and a release step that runs the archiver

- **Depends on:** Chunk 02  ·  **Type:** code  ·  **Critic mode:** final
- **Description:** Two halves of "it does not come back". (a) A per-file threshold so the change-log
  is measured against a ceiling a bounded live file can meet, rather than the global 40 KB it can
  never meet — the probe's advice text changes with it, since "older entries can go" is now a
  command, not a hand edit. (b) `documentation/release-process.md` gains the archiver beside the
  existing *Archive the plans this release shipped* step, which is the trigger that makes this a
  lifecycle rather than a thing I did once.
- **Tests:** unit — the per-file threshold is read where the global one was, a file with no per-file
  entry still uses the global, and the change-log probe fires above its own ceiling and not below.
- **Acceptance criteria:** the oversized-change-log advisory is absent at the post-Chunk-02 size and
  present when the file exceeds its own threshold; the release process names the command.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status
