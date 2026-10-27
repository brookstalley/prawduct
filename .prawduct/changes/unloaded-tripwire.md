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
  means installed. In a linked git worktree (`claude --worktree`), a record naming the main
  checkout counts too. The hook finds the main checkout from the worktree's `.git` file and its
  `commondir`, without running git. `plugin_activation` gained the same rule (`checkout_paths`),
  so `check-plugin-active` stops calling such a worktree inactive.
  - When the plugin is installed, it prints nothing.
  - When the file reads cleanly and has no such record, it prints a loud "PRAWDUCT GOVERNANCE IS
    NOT ACTIVE IN THIS SESSION" line with the install command.
  - Anything else prints a softer "could not verify" line, and never "not installed". That covers
    an unreadable or missing file and a malformed record. It also covers `python3` that is not on
    `PATH` or that exits non-zero, and the line names which of the two it was.
- One owner for the text: `plugin/lib/unloaded_tripwire.py`. The writers (`init-product`,
  `/prawduct:migrate`'s `transform_settings`, and a new `prawduct-hook install-tripwire [--apply]
  [--json]` that `/prawduct:doctor` runs) merge it idempotently. A stale copy is removed and the
  current group appended. The hook is found by the no-op `: prawduct-unloaded-tripwire` line at the
  head of the command, and any copy that is not exactly the current one counts as stale.
  - `"hooks": null` reads as no hooks.
  - A `hooks` shape the writers will not edit, such as `hooks` as an array or `hooks.SessionStart`
    as an object, is left alone and reported: `init-product` adds a warning, `/prawduct:migrate` a
    note, and `install-tripwire` exits 1 naming the shape.
- The plugin id comes from the install contract (`migrate_plugin.PLUGIN_ID`).
- The hook's matcher is pinned to the banner hook's, so a missing banner and a silent tripwire
  cover the same session starts.
- A new info advisory, `install-reference` / `tripwire-missing`, routes an already-onboarded repo
  without the hook to `/prawduct:doctor`. It also fires on a `hooks` shape the writers will not
  edit, and names that shape in its evidence. The hook is not part of `INSTALL_REFERENCE`, which is
  compared field by field, so the `contract-drift` probe and `print-install-reference` are
  unchanged.
- The descriptions of what a governed repo commits now name the hook. These are
  `architecture.md` (Design Intent #5, Distribution, and a recorded decision under the
  "writes nothing into a governed repo" norm, whose wording is left as ratified), the README, the
  project structure, the operational spec, the migration guide, and the onboard and doctor
  skills.

### Chunk 02: the anchor line

- The governance anchor now says Claude Code is loaded if its session banner appeared, not if
  `/prawduct:*` commands are available. It also says to tell the user before any work, and not to
  imitate the gates from the plugin's files. This covers repos that have not re-run setup.
- The previous anchor is archived as `ANCHOR_V6`, so `reanchor` offers the update. "Session banner"
  joins `anchor_repair.SUBSTANCE`, so an owner-edited anchor without it now grades
  `stale-modified`. The anchor was reworded in place to stay under its injected-size ceiling.

### Test infrastructure, found while recording this branch's suite

- `tests/conftest.py` gains `pytest_make_parametrize_id`. A string parameter whose generated id
  has a newline, a leading or trailing space, a tab, non-ASCII text or more than 80 characters
  now gets a stable `<argname>-<sha1 prefix>` id. On the testament pool one runner collects and
  another runs the id it was handed, and those ids did not survive the hand-off, so tests that
  pass were reported as errors. This hit three of this batch's four branches. Every other id is
  unchanged.

## Consumer note
Run `/prawduct:doctor` once in each governed repo. It adds a SessionStart hook to the repo's
`.claude/settings.json` (commit it) that prints a warning when a session starts in a Claude Code
profile where prawduct is not installed, and stays silent otherwise. New repos get it from
`/prawduct:onboard`. Doctor also offers the updated governance anchor, which tells agents that a
missing Prawduct session banner means governance is off. On Windows without Git Bash the hook does
not run, and nothing warns.

To opt out, delete the one `hooks.SessionStart` group in `.claude/settings.json` whose command
starts with `: prawduct-unloaded-tripwire`. Then dismiss the `tripwire-missing` advisory with
`/prawduct:advisory dismiss`. A dismissal stays put through later syncs, but it is recorded per
clone, so each clone dismisses it once. Re-running `/prawduct:onboard` or `/prawduct:migrate` on
an onboarded repo does not add the hook back: both do nothing once `distribution: plugin` is
recorded. `/prawduct:doctor` Check #1 still reports the hook as missing and offers
`install-tripwire --apply`. Decline that offer, or it writes the hook again.
