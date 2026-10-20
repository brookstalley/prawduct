# Issue #1024 — release: a pruned release can archive collateral work as shipped: Requirements

`status: draft · stage: requirements · area: release · added: 2026-10-20 · source: scheduled
backlog session · issue: https://github.com/brookstalley/prawduct/issues/1024`

Related: #169 (named by the issue; not re-read here). #1012 (the wave-1 cumulative review that
found this). `.prawduct/runbooks/promote-a-pruned-release.md` (step 3 is where collateral is
recorded).

## Problem

A pruned release withholds a commit range, not a feature (runbook, "Before you start"). Work that
merged before the cut point but is not itself a withheld scope is **collateral**: it stays off
`main` because it cannot be separated from the withheld work. Phase 0 classifies scopes in the
release plan's `## Release classification` table as `ships` or `withheld`; nothing in that table
lets a human say "this scope is collateral". A collateral scope classified `ships` is therefore
stamped `release=vX.Y.Z` and archived by `cut-change-log` as shipped while its code stays on
`develop`. The archive is append-only, so after the prep commit there is no clean undo and "what
did vX.Y.Z ship?" reads wrong permanently. This predates fragments: the legacy flow stamped
`release=` the same way.

## Grounding facts

Checked against `develop` at `d9df436f` (2026-10-20).

- The table grammar is two dispositions only: `SHIPS`/`WITHHELD` (`release_readiness.py:50`);
  `withheld` requires a blocker id, and the gate checks that blocker is still open
  (`release_readiness.py:962-1032`). A collateral scope has no blocker of its own — its reason to
  be held is *another scope's* blocker — so today the only honest row is `withheld | <that
  scope's blocker>`, and nothing tells the operator that is the rule.
- The gate is a pure function of the table and the change-log entries. It never looks at commits,
  so it cannot tell that a `ships` scope's code sits at or before the cut point. The cut point
  exists only in the release plan prose and runbook steps 1–3.
- The runbook already makes the operator inspect the pre-cut range (step 3) and "write the
  collateral into the release plan by name", but the instruction ends there: no step reclassifies
  the collateral, and the issue reports the step detects the problem with no remedy.
- `cut-change-log` is named in the issue but is not present in the `develop` tree at this commit
  (`grep -r cut-change-log` finds nothing outside `.git`). The archive path that exists is
  `change_log_archive.py`, which pins exactly what `release_pending_entries` calls pending
  (`:152`). Requirement 4 below therefore binds to whichever command stamps/archives, to be
  located in design.

## Requirements

1. **Collateral is a classification, not prose.** A scope held only because it is inseparable from
   a withheld scope is recorded in the release classification table as `withheld`, with the
   withholding scope's blocker id (or the withheld scope's name) as its reason. The release-plan
   template and Phase 0 instructions say so.
2. **Shipping a collateral scope is refused.** `check-releasability` fails when a scope is
   classified `ships` while it is declared collateral of a withheld scope. The failure names both
   scopes and the remedy (reclassify the collateral `withheld`, or ship the blocker's scope).
3. **The runbook step 3 has a remedy.** When step 3 finds a `ships` scope's commits at or before
   the cut point, it directs the operator to reclassify and re-run `check-releasability` before
   continuing, rather than only to "go back to step 2's remedy".
4. **No collateral is archived as shipped.** The stamp/archive step does not mark `release=vX.Y.Z`
   on a scope the table withholds (the existing contradiction check, `release_readiness.py:
   1003-1020`, already covers a withheld scope that carries the tag; the new requirement is that
   the *collateral* reaches that check as withheld, which requirement 1 provides).
5. **A wrong archive has a documented recovery.** Since the archive is append-only, the runbook
   states what an operator does after the prep commit if a collateral scope was archived anyway
   (candidate: a corrective `release=` rewrite recorded in the release plan; to be decided).

## Acceptance

- [ ] A release plan with scope A (`ships`) declared collateral of withheld scope B fails
      `check-releasability` with a message naming A, B, and the remedy.
- [ ] The same plan with A reclassified `withheld` passes, and `cut-change-log` / the archive does
      not stamp or move A.
- [ ] Red-verified: the new check is shown failing on the issue's repro before it passes.
- [ ] Runbook step 3 and the release-plan template carry the rule; no sentence elsewhere still says
      collateral is "recorded by name" without classifying it.

## Open decisions (owner)

The issue flags "owner decision needed on the rule". Recommendation first:

1. **How does the gate learn a scope is collateral?** Recommended: an explicit third cell value on
   the table row — `| scope | ships | | collateral-of=SCOPE |` or a `collateral` disposition that
   requires a named withheld scope — so the declaration is data the gate can check, and a
   collateral row can never be `ships`. Alternative: keep two dispositions and only document that
   collateral rows are `withheld` (cheap, but unenforced — a recall-only rule).
2. **Should the gate infer collateral from commits?** Recommended: no. It would need the cut point
   and a scope→commit map the repo does not keep; the declaration in (1) plus the runbook's
   step-3 range read is proportionate.
3. **Recovery for an already-archived collateral scope** (requirement 5): corrective rewrite vs.
   accepting and annotating the archive entry.

## Scope-out

- Splitting a pruned release by file or feature (the runbook records that ship/withhold sets
  overlapped in 11 files on v3.1.2).
- Changing the blocker-liveness behaviour for frozen backlogs.
- Any change to non-pruned releases, where K withheld is 0.
