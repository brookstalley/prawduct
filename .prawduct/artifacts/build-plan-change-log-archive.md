---
artifact: build-plan
version: 2
scope: change-log-archive
branch: feature/change-log-archive
partition: serial — one chunk; the archiver, its readers and the probe share one predicate (what may leave the live log), and splitting them would put that predicate's definition and its consumers in different reviews
related_issues:
  - "brookstalley/prawduct#802 — plan-backfill strands a refused plan once its release= tag leaves the live log. RESOLVED here by R5: plan-backfill reads live + archive, so the tag never leaves its sight and the checklist ordering constraint the prior design needed is gone"
  - "brookstalley/prawduct#793 — a product's release moment never runs the archiver. RESOLVED here by R6: /prawduct:pr Step 1d runs it on every PR, for trunk and gitflow alike"
governed_by:
  - artifact: data-model
    dispositions:
      - "verdicts computed from the append-only fact ledger, never mutable model-written state → inapplicable, because nothing here touches the Critic data plane"
      - "facts are immutable and append-only → conforms; an entry's bytes are unchanged by the move"
      - "derived views are disposable and never authoritative → conforms; the archive is not a view, it is the entries' one home once moved"
      - "a governance document reaches a terminal state, never deleted → ENGAGED: entries are MOVED verbatim into `.prawduct/change-log-archive/`, never deleted or rewritten; the archive is committed history, same tier as the live log"
      - "every issue written to the backlog store conforms to §1 title rules → inapplicable, because no backlog item is written"
      - "a newer-schema fact surfaces as a loud block → inapplicable, because no fact schema changes"
      - "two stores, two lifetimes → ENGAGED: the archive is a committed answer, never a gitignored cache — which is why the command refuses when git would ignore it while tracking the live log"
      - "`backlog_service_repo` selects the authoritative store → inapplicable, because no chunk reads the backlog"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable, because no review path changes"
      - "authority fails closed; advice fails soft → ENGAGED: the archiver refuses (nothing written) on a malformed tag, on any difference the release gate's own readers would see, and on an archive git would ignore; the advisory probe fails soft (no advice) on an unreadable file"
      - "local-first: process-spawn + atomically-written files + git → conforms; the move is written all-or-nothing through `core.write_all_or_none`"
      - "the plugin writes nothing into a governed repo except its own `.prawduct/` state → conforms; the archive lives under `.prawduct/`"
      - "Python but never Python-specific → conforms; no product file is classified"
      - "prawduct guides and reviews; it never implements → conforms; it moves its own records, never product code"
      - "goals and verification bind; prescribed method is advice → conforms; the prior design's method (version-line retention) was weighed against the binding goal (a bounded live log) and lost on it — see Decision"
      - "every fact has one home → ENGAGED: a moved entry exists in exactly one file. Readers of history (plan-backfill, record-lint's scope witness, the release gate's tagged-for-this-release lookup) read live + archive through one loader; the archiver keeps live exactly what `release_readiness.release_pending_entries` calls pending, by calling it"
  - artifact: api-contract
    dispositions:
      - "exit codes are the contract, on a documented scheme → ENGAGED: `archive-change-log` is a state-mutating writer — 0 written or no-op, 1 refused, 2 usage"
      - "commands that decide for themselves which files to touch preview first (dry-run default) → ENGAGED: `--apply` mutates, bare invocation previews"
      - "additive-first evolution → conforms; new subcommand, no existing flag or key repurposed"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → one chunk, one cumulative review"
      - "proportionality ratchets both ways → conforms; no control is added that blocks a session — the refusals are on an explicit --apply"
      - "state-file growth past its threshold is an advisory, never a hard block → conforms; nothing blocks on size. The advisory gains a command that actually clears it"
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

## Decision — this design over the two prior ones

**Prior work, missed when this plan was first written and found by its cumulative review.** An
unmerged branch, `fix/change-log-lifecycle` (three chunks, complete and Critic-clean 2026-09-10),
built `archive-change-log` into one `.prawduct/change-log-history.md`, moving only `release=` entries
below the current minor line, with a per-file size ceiling (768 KB for this log). The draft
`documentation/issues/802-design.md` (2026-09-14) chose the same single file. #802 and #793 were
filed against that design's gaps.

**Why this one ships (owner asked for the audit, 2026-09-16):**
- **It bounds the log; the prior design relocates most of it.** Keeping the current minor line
  leaves 326 KB live today (measured over develop's log at keep-3.5) — 8x the default threshold,
  which is why that branch also had to raise the ceiling to 768 KB. The owner's bar is that 1.5 MB is
  unacceptable; 326 KB with a raised ceiling does not meet it. Size-based hysteresis leaves 23 KB,
  all release-pending.
- **It works in every product.** Version-line retention needs declared version files and never
  archives in a product that does not tag releases; size selection needs neither.
- **It closes #802 and #793 instead of inheriting them.** History readers load live + archive, so no
  release tag leaves their sight and no checklist ordering is load-bearing; the PR step runs it in
  every repo.
- **Monthly files over one history file:** each move touches the month files it fills, not a
  1.5 MB file that every archive run rewrites.

**Ported from the prior branch, because they were better:**
- The **result invariant** — re-read the log the run would leave with the release gate's own
  predicates (pending set, unclassifiable set, diagnostics with line numbers normalised) and refuse
  on any difference, rather than trusting the selection rule.
- **`core.write_all_or_none`** and its tests — rollback across every file written, including on
  Ctrl-C, naming any file a failed rollback left behind.
- **Entry boundaries from the parser's own line numbers**, not a second header regex.

**Not ported:** version-line retention and `--keep-minor` (see above); the per-file ceiling
`oversized_file_thresholds_kb` (a log bounded at half the default threshold does not need one).

**The prior branch** is superseded by this plan and kept until the owner rules on deleting it.
`documentation/issues/802-design.md` is marked superseded.

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
- **R4 Refuse rather than guess.** Nothing is written when the release tag validator reports
  errors, when the release gate's own readers would see the resulting live log differently (pending
  set, unclassifiable set, a new diagnostic), or when git tracks the live log but would ignore the
  archive. The write itself is all-or-nothing across every file.
- **R5 Readers of history see the whole log.** `plan-backfill`, record-lint's scope witness and the
  release gate's "already tagged for this release" lookup read live + archive through one loader. `check-releasability` stays on the live file:
  Its pending questions stay on the live file:
  [DECISION: their subject is the pending set, which R3 keeps live by construction, and its messages
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
