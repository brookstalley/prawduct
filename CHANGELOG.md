# Prawduct Changelog

Consumer-facing release notes for the Prawduct governance plugin. The
version-delta banner (a SessionStart hook) shows the headline for each version a
repo crosses since it was last opened — so an auto-update is always visible,
never silent. This file ships **inside the plugin**: it never lands in a
consuming repo's tree, so it creates zero commit/merge noise downstream.

The full internal development log (with blast-radius and rationale) lives in the
Prawduct repo's `.prawduct/change-log.md`; this file is the public digest. The
release process keeps the two in sync (one headline per shipped release).

## v2.0.1
Default to **no commit/PR attribution trailers** (`Co-Authored-By`, `Signed-off-by`, "Generated with …"). Opt in per repo via `project-preferences.md` (`Commit attribution: none → co-authored`). The default is carried by the always-injected session digest, so it reaches every governed repo — including migrated ones whose only governance surface is the thin anchor.

## v2.0.0
Plugin distribution: Prawduct ships as a Claude Code plugin instead of files synced into each repo. Consuming repos commit **zero** framework files and get always-latest governance via marketplace auto-update — no stash/pop/merge papercuts. Mutable state stays in each repo's `.prawduct/`. Existing v1 file-sync repos keep working and migrate when ready (`/prawduct:migrate`).

## v1.8.1
Bugfix: phantom "rebase in progress" from a stale `.git/REBASE_HEAD` marker.

## v1.8.0
Governance-tax reduction: pure benefit, almost no tax.

## v1.7.0
Backlog system (lean core): a structured `/backlog` skill plus the first production advisory probe.

## v1.6.0
Post-sync advisory infrastructure plus a configurable build-plan path.

## v1.5.2
Stop-hook waiver discoverability — gates name their escape hatch.

## v1.5.1
Backlog follow-ups.

## v1.5.0
Critic proportionality — review depth scales to the work.

## v1.4.0
`/pr` doc-only fast-path — documentation PRs skip the heavy gates.

## v1.3.17
Proportional Critic, the cumulative-Critic gate, and foreign-API verification.

## v1.3.16
The Janitor skill becomes model-invocable.
