# Prawduct Changelog

Consumer-facing release notes for the Prawduct governance plugin. The
version-delta banner (a SessionStart hook) shows the headline for each version a
repo crosses since it was last opened — so an auto-update is always visible,
never silent. This file ships **inside the plugin**: it never lands in a
consuming repo's tree, so it creates zero commit/merge noise downstream.

The full internal development log (with blast-radius and rationale) lives in the
Prawduct repo's `.prawduct/change-log.md`; this file is the public digest. The
release process keeps the two in sync (one headline per shipped release).

## v2.0.6
Internal release/build-tooling fixes (REL-4T8N + three adjacent items). `regen-views` now regenerates **every** release-pending build plan in one pass — it enumerates each change-log `scope=` and resolves it to its plan file via frontmatter, so a batched multi-scope release no longer needs the `active_build_plan` pointer aimed at each plan in turn (it also no longer hard-fails when no single plan resolves). The derived `release-notes.md` renders each distinct scope of a batched release as its own sub-section instead of mis-aggregating them under one. `verify-chunk-refs` stops false-positiving on `` `path::symbol` `` references (it checks the path only). The `/prawduct:pr` merge flow now keeps the build plan when a feature→`develop` merge lands ahead of a batched `develop→main` release (deleting it only when the merge *is* the release). And the structural test suite ignores leftover `.claude/worktrees/` workflow checkouts. Plugin-governed repos: no behavioral change.

## v2.0.5
Internal quality + governance hardening, batched from four development scopes (roi-batch, roi-batch-2, evidence-deferral, cleanup-batch). Most visible to plugin users: a new `prawduct-hook test-evidence record` command that runs the suite and writes the `.test-evidence.json` the freshness gate reads (closing a reader-without-a-writer gap); the Stop gate now treats in-flight background work as "wait, don't waive" so it never silently skips the Critic; and the Critic flags substring assertions on "no behavior change" refactors. The rest is silent-degradation guards (regen-views exit codes, advisory-corruption surfacing), parser/gate hardening, behavior-preserving refactors, and added test coverage. Plugin-governed repos: no behavioral change beyond the new gate guidance.

## v2.0.4
New `prawduct:allow <scope>/<rule-id> -- reason` intentional-waiver pragma — one durable, language-agnostic way to mark a reviewed, intentional violation of a named principle (generalizing `prawduct:ok-broad-except`, which still works); `project/*`-scoped waivers stay opaque to the framework so plugin updates never break them. Also closes a governance-gate hole (the trivial/doc-only file-set bound now protects `skills/`, not the removed `agents/`) and clears 2.0 doc/coherence staleness. Plugin-governed repos: no behavioral change.

## v2.0.3
The v1 file-sync engine is fully retired. Governance now ships entirely from the plugin — no frozen sibling service, no committed framework templates, no sync machinery. Plugin-governed repos are unaffected (the engine they don't use is gone); any remaining v1 file-sync repo migrates onto the plugin with `/prawduct:migrate`.

## v2.0.2
Advisory probes run again in the plugin runtime. The `legacy-backlog-format` nudge (and every other post-sync advisory) was silently dead in v2 plugin repos — probe evaluation had been coupled to the removed file-sync `sync` step — so session-start never surfaced the prompt to run `/prawduct:backlog migrate`. The plugin SessionStart now evaluates the probe roster directly (local, fail-soft). Also: the file-sync→plugin **migration guide** now leads with the two-step action and the real install commands instead of burying them under background.

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
