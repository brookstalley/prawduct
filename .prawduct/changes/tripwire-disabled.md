---
schema: 1
type: fix
scope: tripwire-disabled
date: 2026-11-25
title: "The unloaded-plugin tripwire and check-plugin-active see a plugin switched off by enabledPlugins (#1246)"
closes: [brookstalley/prawduct#1246]
---
The tripwire hook in a governed repo's `.claude/settings.json` decided "will prawduct load here" from
`installed_plugins.json` alone. A plugin installed at user scope but set to `false` in the repo's
`enabledPlugins` read as active, so the session ran with no banner, skills or Stop gates and nothing
said so. `check-plugin-active`, which onboarding, doctor and migrate run, answered the same question
the same way.

Both now resolve `enabledPlugins` the way Claude Code documents it: key by key, the highest-precedence
settings file that names the plugin decides. That is managed settings for this OS (its
`managed-settings.d` drop-ins, later names winning, over `managed-settings.json`), then the project's
`settings.local.json`, its `settings.json`, then the user's `settings.json` in the config home. Only
a literal `false` disables, an unreadable file is passed over, and files are read as UTF-8. A
`--settings` file, and managed policy delivered by MDM or a remote source, are invisible to a file
read and are not consulted. The rule has one home, `plugin_activation.disabled_by`; the tripwire
inlines a copy, because it must run when the plugin does not, and a test holds the two to the same
verdicts over the precedence cases, managed drop-ins and an unreadable file included.

An installed plugin that a setting switches off is now `disabled`. The tripwire prints its own line
naming the settings file. It is not the not-installed accusation, because `/prawduct:repo-disable`
writes exactly this setting on purpose: the agent is told to say so in one line and let the user
decide, and to ignore the line when it loaded the plugin with `--plugin-dir`. `check-plugin-active` reports `disabled` with
`disabled_by` and exits 1, as `inactive` does, since both load nothing. The onboard, doctor and
migrate skills route the new status. A plugin that is not installed still gets the not-installed
line, since installing is the first fix.

## Consumer note
The tripwire hook's text changed, so `/prawduct:doctor` reports it `stale` until you run `prawduct-hook install-tripwire --apply`, which replaces only that hook. After that, a session in a repo where `enabledPlugins` sets prawduct to `false` says so at session start, naming the file, instead of running ungoverned in silence.
