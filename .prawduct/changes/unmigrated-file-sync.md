---
schema: 1
type: fix
scope: unmigrated-file-sync
date: 2026-10-27
title: A file-sync repo running under the plugin without /prawduct:migrate now gets an advisory
closes: [brookstalley/prawduct#1090]
---
A repo onboarded under the pre-2.0 file-sync install, with the plugin installed but
`/prawduct:migrate` never run, keeps its legacy sync hook wired in `.claude/settings.json`. That
hook stands down once `distribution: plugin` is recorded, which only migrate writes. A hook synced
at v2.0.0 or later also stands down when the repo's own settings enable the plugin. Short of either,
it runs at every session start beside the plugin's; a plugin installed at user scope is the common
case. Syncing from a framework checkout older than the repo, it silently reverts committed
governance files. Nothing said so: the never-onboarded probe is silent on these repos by design,
because the sync manifest proves an onboard once ran.

A new `unmigrated-file-sync` advisory fires when the sync manifest is present and
`distribution: plugin` is not, and recommends `/prawduct:migrate`. It is `urgent` when the legacy
sync can still run: the hook is wired on SessionStart and does not stand down. It names the hook
events it runs on. In every other state it is `warn` and says why nothing reverts at session start.
The repo still carries framework files the plugin has replaced.
`migrate_plugin.legacy_hook_events` reads the wiring with the same predicate migrate uses to strip
it, and `legacy_sync_stands_down` mirrors the v2.0+ hook's settings check.

## Consumer note
- A repo still on the pre-2.0 file-sync install now sees an advisory recommending
  `/prawduct:migrate` at session start. It is urgent while the legacy sync hook can still run at
  session start. Once migrated, the advisory stops firing.
