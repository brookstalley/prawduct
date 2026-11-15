---
schema: 1
type: feature
scope: release-fragments-only
date: 2026-11-15
title: releases read change fragments only and refuse a change log with unreleased entries, and a pruned release declares its collateral before the cut
closes: [brookstalley/prawduct#1125, brookstalley/prawduct#1022, brookstalley/prawduct#1024]
---
Two changes to the release tooling.

### Releases read fragments only (#1125, folding in #1022)

`check-releasability` and `cut-change-log` now take the pending set from `.prawduct/changes/` and
nothing else. Before, they also read release-pending entries from `.prawduct/change-log.md`, so
nothing pushed a repo to move onto fragments, and the legacy reader could not be retired.

A repo whose change log still holds an entry that has not shipped is refused, with one
`legacy-pending-entry:` line per entry. Each line names the entry's title and line number, and the
way out: `/prawduct:doctor`, whose check #22 runs `migrate-change-log`. Nothing is dropped
silently. A `release=` value that is not a version (`release=unreleased`, the shape that hid a
branch from v3.2.8) is refused the same way, with the migration's own reason. A repo that already
records changes as fragments releases exactly as before.

The legacy reader is gone. `PendingSet.legacy_scopes`, `release_pending_scopes`,
`unclassifiable_pending_entries`, the cut's legacy-shipping line, and the gate's
`scope-in-both-shapes`, `unclassifiable-pending-entry` and `bad-change-log-tag` refusals are
removed. `plugin/templates/change-log.md` is deleted. `release_pending_entries` stays, as the
refusal's detector and the size archive's rule for keeping a pending entry in the live log, where
the refusal and the migration both look for it. The gate's `scanned:` line now counts fragments
and the log entries it read as history.

The `change-log-fragments-available` advisory moves from `info` to `warn`, and says that releases
now refuse the old log. Its id is unchanged.

### A pruned release declares its collateral before the cut (#1024)

On a pruned release, work that merged at or before the cut point stays on `develop` with the
withheld work. If the classification table said `ships` for it, the cut archived it as shipped in a
release that did not carry it. Collateral was only identified later, in the pruned runbook's
Phase 2, after the damage.

A `withheld` row may now say `collateral-of <scope>` instead of a blocker. The row is held by its
parent's blocker, so the cut keeps its fragment pending and the stale-blocker check covers it. A
collateral row written `ships`, a missing parent, a parent that is not `withheld`, and a parent that
is itself collateral are each refused, naming both scopes. The release runbook's Phase 0 gains
step 0a, which finds the collateral when anything is withheld (the pruned runbook's new *Before
Phase 1* section) and declares it before the cut. The pruned runbook's steps 1 to 3 now confirm
that work. For collateral already archived by mistake, they name a recovery: a `reopens:` fragment
that ships with the release that carries the code.

## Consumer note
Move your change record onto fragments before your next release. If `.prawduct/change-log.md`
still holds an entry that has not shipped, `check-releasability` and `cut-change-log` now refuse
with a `legacy-pending-entry:` line for each one, naming `/prawduct:doctor`. Run it (check #22),
review the dry run, and apply: each unreleased entry becomes its own file in
`.prawduct/changes/`, and released history stays where it is. The session briefing's
`change-log-fragments-available` advisory now shows at `warn` until you do.
