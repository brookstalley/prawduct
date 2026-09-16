---
artifact: build-plan
version: 2
scope: change-log-archive
branch: feature/change-log-archive
partition: serial — one chunk; the archiver, its readers and the probe share one predicate (what may leave the live log), and splitting them would put that predicate's definition and its consumers in different reviews
governed_by:
  - artifact: data-model
    dispositions:
      - "a governance document reaches a terminal state, never deleted → ENGAGED: entries are MOVED verbatim into `.prawduct/change-log-archive/`, never deleted or rewritten; the archive is committed history, same tier as the live log"
      - "facts are immutable and append-only → conforms; an entry's bytes are unchanged by the move"
      - "derived views are disposable and never authoritative → conforms; the archive is not a view, it is the entries' one home once moved"
  - artifact: architecture
    dispositions:
      - "every fact has one home → ENGAGED: a moved entry exists in exactly one file. Every reader that interprets history (plan-backfill, record-lint's scope witness) reads live + archive through ONE loader; the release gate reads only pending entries, which never leave the live file"
      - "authority fails closed; advice fails soft → ENGAGED: the archiver refuses (nothing written) on any tag the release validator rejects, because a malformed `release=` is exactly what would make a pending entry look archivable; the advisory probe fails soft (no advice) on an unreadable file"
      - "the plugin writes nothing into a governed repo except its own state → conforms; the archive lives under `.prawduct/`"
      - "local-first: no network, no daemon → conforms; file reads only"
  - artifact: api-contract
    dispositions:
      - "exit codes are the contract, on a documented scheme → ENGAGED: `archive-change-log` is a state-mutating writer — 0 written or no-op, 1 refused, 2 usage"
      - "commands that decide for themselves which files to touch preview first (dry-run default) → ENGAGED: `--apply` mutates, bare invocation previews"
      - "additive-first evolution → conforms; new subcommand, no existing flag or key repurposed"
  - artifact: nonfunctional-requirements
    dispositions:
      - "state-file growth past its threshold is an advisory, never a hard block → conforms; nothing blocks on size. The advisory gains a command that actually clears it"
      - "review wall-clock is P0 → one chunk, one cumulative review"
last_validated: 2026-09-16
---

# Build plan — bounded change log

## Problem

`.prawduct/change-log.md` grows forever. Nothing trims it at release (CL5 made the `release=` tag the
only release-time edit), so this repo's log is 1.5 MB and every consuming repo's log is on the same
curve. The oversized advisory cannot fix it: its only advice forbids deleting tagged entries, which
here is 97% of the bytes, so it nags with no available action — noise in every product.

## Owner direction (2026-09-16)

"A 1.5 MB changelog is totally unacceptable. Design, build and fix a durable solution — this is
creating noise for consuming repos too." Amends CL5 (see `documentation/governance-artifact-lifecycle-requirements.md`).

## Requirements

- **R1 Bounded live log.** When `.prawduct/change-log.md` exceeds the repo's oversized threshold, one
  command brings it to at most half the threshold (hysteresis: below the threshold it is a no-op, so
  it does not churn on every PR), except where release-pending entries alone exceed that.
- **R2 Lossless.** Moved entries land verbatim in `.prawduct/change-log-archive/YYYY-MM.md`, bucketed
  by the entry's header date, newest-first within a file. Nothing is deleted.
- **R3 Pending never moves.** In a product that versions (any `release=` tag in live or archive), a
  tagged entry with no `release=` stays live. Undated entries stay live (no bucket; fail-safe).
  Selection keeps the newest entries by date; once one does not fit the budget, it and everything
  older moves (no swiss-cheese).
- **R4 Refuse on bad tags.** If the release tag validator reports errors, nothing is written.
- **R5 Readers of history see the whole log.** `plan-backfill` and record-lint's scope witness read
  live + archive through one loader. `check-releasability` stays on the live file:
  [DECISION: its subject is the pending set, which R3 keeps live by construction, and its messages
  cite live-file line numbers that a concatenated read would falsify.] `check-change-log-entry`
  stays on the live file (it asks what this branch added).
- **R6 Durable trigger.** `/prawduct:pr` Step 1d runs `archive-change-log --apply` on every PR (a
  no-op under the threshold), so every consuming repo self-maintains with no owner decision. The
  prawduct release process runs it too. The oversized-change-log advisory names the command as its
  agent action when something is archivable, and says plainly when the bulk is pending work instead.
- **R7 This repo migrated.** The branch applies the archiver to this repo's own log.

## Out of scope

`project-state.yaml` and `learnings.md` size; entry verbosity; `plugin/CHANGELOG.md`; a union merge
attribute for archive files (concurrent archiving is rare and conflicts are in `.prawduct/` prose).

## Requirements Confidence

**Level:** High. The readers were enumerated by grep over `parse_change_log` / `CHANGE_LOG_REL_PATH`.
[ASSUMPTION: no probe id bump — a consumer that already dismissed the change-log advisory keeps it
dismissed and is still covered by R6's PR step.]

## Chunk 01 — archiver, readers, trigger, migration

Type: cumulative-final

**Delivers:** `plugin/lib/change_log_archive.py` (split, select, move, load-all); `prawduct-hook
archive-change-log [--apply] [--json]`; union reads in `plan_backfill` and `record_lint`; oversized-change-log advice rewritten; `/prawduct:pr` Step 1d bullet; release-process
step; CL5 amendment + CL8; api-contract, data-model, project-structure; this repo's log archived.

**Done when:**
- Tests: selection (pending pinned, budget, no swiss-cheese, undated live, non-versioned product
  archives scoped untagged entries, below-threshold no-op), lossless round trip (live + archive
  entry multiset equals the original), bad tags refuse with nothing written, merge into an existing
  bucket file, loaders (`shipped_scopes` over archived releases, scope witness over archive), pending
  entries surviving a re-run after released history has left, CLI exit codes and dry-run writes nothing, advisory text/action.
- Suite green; `archive-change-log --apply` run on this repo leaves only release-pending entries
  live (they alone are ~21 KB, over half the threshold, which R1 allows).
- `/prawduct:critic cumulative` with zero blocking.

## Status

- [ ] Chunk 01 — archiver, readers, trigger, migration
