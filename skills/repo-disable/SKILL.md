---
description: Disable the Prawduct plugin for THIS repo — write a per-repo enabledPlugins override (committed for the whole team, or local just for you) that turns off the /prawduct:* commands, hooks, and banner here. Re-enabling is a manual file edit. Use when a repo shouldn't be governed by Prawduct.
argument-hint: "[local|committed]"
user-invocable: true
disable-model-invocation: true
allowed-tools: Bash(prawduct-hook repo-disable *), Read
---

You are turning Prawduct **off in the current repo only**. Prawduct installs at the
**user** level, so its hooks and `/prawduct:*` commands load in every repo the user
opens. A per-repo `enabledPlugins` override disables it just here — it beats the
user-scope enable in Claude Code's settings hierarchy.

(As of v2.0.11 the SessionStart hooks are already silent in a repo with no
`.prawduct/`. This skill goes further: it removes the `/prawduct:*` commands and the
version banner too, by disabling the plugin outright for this repo.)

## Flow

### 1. Pick the scope
Two choices — confirm which the user wants (use the `local`/`committed` argument if
given; otherwise ask):

- **committed** → `.claude/settings.json` (git-committed). Disables Prawduct for
  **everyone** who clones this repo. Use when "this repo isn't a Prawduct project."
- **local** → `.claude/settings.local.json` (Claude Code auto-gitignores it).
  Disables Prawduct **just for this user**, leaving any committed install reference
  intact for teammates. Use when "I personally don't want it here."

If the repo is onboarded (has `.prawduct/` and a committed install reference),
flag that committed-scope disable turns governance off for the whole team —
**local** is usually what's wanted there.

### 2. Dry-run and confirm
Show the plan without writing (add `--local` for local scope):

```
prawduct-hook repo-disable [--local]
```

Present the target file. Confirm with the user.

### 3. Apply
```
prawduct-hook repo-disable [--local] --apply
```

The command preserves every other setting in the file (permissions, env, hooks,
other plugins, and prawduct's own marketplace reference — left intact so re-enabling
is a one-line edit). It aborts without writing if the file exists but isn't valid
JSON.

### 4. Tell the user what happens next — REQUIRED
After applying, relay both of these clearly:

- **It takes effect after `/reload-plugins` (this session) or a restart.** Until
  then Prawduct stays active.
- **There is no `/prawduct:repo-enable`** — once disabled, the `/prawduct:*`
  commands (including this one) won't load in this repo, so nothing inside Prawduct
  could turn it back on. **To re-enable later, edit the file by hand:**
  1. Open the settings file you chose (`.claude/settings.json` or
     `.claude/settings.local.json`).
  2. Under `"enabledPlugins"`, set `"prawduct@prawduct": true` — or delete that
     entry entirely (which falls back to the user-scope setting).
  3. Run `/reload-plugins`, or restart Claude Code.

  (Alternatively, Claude Code's native `/plugin` menu can re-enable it from the
  Installed tab.)
