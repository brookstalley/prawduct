---
schema: 1
type: feature
scope: unloaded-tripwire
date: 2026-10-27
title: An unloaded plugin says so at session start
closes: [brookstalley/prawduct#1078]
---

#1078. When Claude Code loaded no prawduct plugin for a governed repo, for example a fresh
`CLAUDE_CONFIG_DIR` profile with no install record, there was no banner, no Stop gate and no skill,
and nothing said so. A day of work ran ungoverned. Everything prawduct ships is delivered by the
plugin, so none of it could notice its own absence.

### Chunk 01: the tripwire hook

- A project-level SessionStart hook in the product's committed `.claude/settings.json`. Project
  hooks run whether or not any plugin loads, and a SessionStart hook's stdout reaches the agent's
  context. Both were confirmed against the Claude Code hooks documentation on 2026-10-27.
- The hook is POSIX sh around a `python3 -c` verdict that needs nothing newer than Python 3.0, so it
  does not depend on the plugin's Python floor. It reads
  `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins/installed_plugins.json` by the same rule
  `plugin_activation` uses: a user-scope record, or a record whose `projectPath` is this repo,
  means installed.
  - When the plugin is installed, it prints nothing.
  - When the file reads cleanly and has no such record, it prints a loud "PRAWDUCT GOVERNANCE IS
    NOT ACTIVE IN THIS SESSION" line with the install command.
  - Anything else prints a softer "could not verify" line, and never "not installed". That covers
    an unreadable or missing file, a malformed record, and `python3` that cannot run.
- One owner for the text: `plugin/lib/unloaded_tripwire.py`. The writers (`init-product`,
  `/prawduct:migrate`'s `transform_settings`, and a new `prawduct-hook install-tripwire [--apply]`
  that `/prawduct:doctor` runs) merge it idempotently and replace a stale copy in place. It is found
  by the no-op `: prawduct-unloaded-tripwire v1` line at the head of the command.
- A new info advisory, `install-reference` / `tripwire-missing`, routes an already-onboarded repo
  without the hook to `/prawduct:doctor`. The hook is not part of `INSTALL_REFERENCE`, which is
  compared field by field, so the `contract-drift` probe and `print-install-reference` are
  unchanged.

### Chunk 02: the anchor line

- The governance anchor now says Claude Code is loaded if its session banner appeared, not if
  `/prawduct:*` commands are available. It also says to tell the user before any work, and not to
  imitate the gates from the plugin's files. This covers repos that have not re-run setup.
- The previous anchor is archived as `ANCHOR_V6`, so `reanchor` offers the update. "Session banner"
  joins `anchor_repair.SUBSTANCE`, so an owner-edited anchor without it now grades
  `stale-modified`. The anchor was reworded in place to stay under its injected-size ceiling.

## Consumer note
Run `/prawduct:doctor` once in each governed repo. It adds a SessionStart hook to the repo's
`.claude/settings.json` (commit it) that prints a warning when a session starts in a Claude Code
profile where prawduct is not installed, and stays silent otherwise. New repos get it from
`/prawduct:onboard`. Doctor also offers the updated governance anchor, which tells agents that a
missing Prawduct session banner means governance is off. On Windows without Git Bash the hook does
not run, and nothing warns.
