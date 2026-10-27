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
hook stands down only once `distribution: plugin` is recorded, and only migrate records it, so it
runs at every session start beside the plugin's. Syncing from a framework checkout older than the
repo, it silently reverts committed governance files. Nothing said so: the never-onboarded probe
is silent on these repos by design, because the sync manifest proves an onboard once ran.

A new `unmigrated-file-sync` advisory fires when the sync manifest is present and
`distribution: plugin` is not, and recommends `/prawduct:migrate`. It is `urgent` when the legacy
hook is still wired, and names the hook events it runs on. It is `warn` when it is not wired: the
repo still carries framework files, but nothing reverts at session start.
`migrate_plugin.legacy_hook_events` reads the wiring with the same predicate migrate uses to strip it.

## Consumer note
- A repo still on the pre-2.0 file-sync install now sees an advisory recommending
  `/prawduct:migrate` at session start. It is urgent if the legacy sync hook is still wired. Once
  migrated, the advisory stops firing.
