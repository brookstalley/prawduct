---
artifact: build-plan
version: 2
scope: unloaded-tripwire
branch: feature/1078-unloaded-tripwire
base: develop
working-branches: []
last_validated: 2026-10-27
depends_on:
  - brookstalley/prawduct#1078
governed_by:
  - .prawduct/artifacts/architecture.md
  - .prawduct/artifacts/api-contract.md
  - .prawduct/artifacts/nonfunctional-requirements.md
partition: Chunks 01-02 delegated to one isolated-worktree agent; the coordinator integrates, runs the suite, Critic and PR
---

# Build Plan — An unloaded plugin says so at session start (#1078)

## Goals

**Response taken:** Proceed, citing #1078. The owner asked on 2026-10-27 for it to land in 3.8.0.
The issue names the failure, a repro environment and a three-part proposal; the owner's choice
among the parts is inferred below.

**Problem:** when Claude Code loads no prawduct plugin for a governed repo (seen: a fresh
`CLAUDE_CONFIG_DIR` profile whose `plugins/installed_plugins.json` is `{"plugins": {}}`, while the
repo's committed `.claude/settings.json` enables `prawduct@prawduct`), there is no banner, no Stop
gate, no skill, and nothing says so. A whole day of work ran ungoverned. Everything prawduct ships
that could notice is delivered BY the plugin, so it cannot run. `plugin/lib/plugin_activation.py`
already detects this state, but only from `/prawduct:onboard`, which runs outside the repo.

**Success:**
- In a governed repo whose session loads no prawduct plugin, the session start puts a loud line in
  the agent's context saying governance is not active in this profile and how to install it.
- When the plugin is loaded, the tripwire prints nothing.
- It never accuses falsely: a record it cannot read is "could not verify" (quiet, or a soft line),
  never "not installed" — the stance `plugin_activation.py` already takes.
- New repos get it from `/prawduct:onboard`; already-onboarded repos get it from
  `/prawduct:doctor` (or the existing install-reference repair path) without hand edits.
- The governance anchor carries one line for repos that have not re-run setup: if no Prawduct
  session banner appeared, say so to the user before any work, and do not imitate the gates by
  reading the plugin's files.

**Design decisions (coordinator, inferred from #1078's proposal):**
- Items 1 and 2 of the proposal are in scope; item 3 (a doctor report) is in scope only as far as
  doctor installing the hook into an existing repo. *Inferred.*
- The tripwire is a **project-level SessionStart hook** in the product repo's committed
  `.claude/settings.json`, because project hooks run whether or not the plugin loads. Its command
  must be self-contained: product repos commit no framework files, and the plugin cannot be called
  because the case is that it is absent. Keep it to a command that runs anywhere Claude Code hooks
  run, with no dependency on the plugin's Python floor (#1097). If a `python3 -c` one-liner is
  chosen, a missing interpreter must also end up visible, not silent.
- The check reads `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/plugins/installed_plugins.json` the way
  `plugin_activation.plugin_activation_status` does (verified on this machine 2026-10-27: version 2,
  `plugins["prawduct@prawduct"]` is a list of records with `scope` `user` | `project` | `local` and
  `projectPath` on the latter two). A `user`-scope record, or a record whose `projectPath` is the
  repo, means installed. That file is a Claude Code internal, so the hook's verdict has the same
  three outcomes as the module (active / inactive / unknown), and only a clean read lacking a
  record says "inactive".
- *Inferred:* a session launched with `--plugin-dir` and no install record will see the warning.
  The message says so, so a framework developer can ignore it; that is cheaper than a false
  silence.

**Out of scope:** detecting a plugin that is installed but disabled; Codex/other hosts (#928).

**Level:** Medium — the harness behaviour of project-level SessionStart hooks beside a plugin's
(order, whether stdout reaches context) is fast-moving. What raises it: Chunk 01's verify step.

**Decisions made mid-build:** *(appended while building)*
- Step 0, checked 2026-10-27 against current docs: (a) hooks in a project's `.claude/settings.json` are their own location, apart from a plugin's `hooks/hooks.json` ("When a plugin is enabled, its hooks merge with your user and project hooks"), and they run even before folder trust is accepted or under `-p` (https://code.claude.com/docs/en/hooks "Hook locations"; https://code.claude.com/docs/en/permissions "What runs before you trust a folder"). (b) SessionStart's plain stdout on exit 0 is added to Claude's context, and Claude's first response waits for SessionStart hooks (https://code.claude.com/docs/en/hooks, SessionStart). (c) Hooks get `CLAUDE_PROJECT_DIR` and inherit the parent environment, so `CLAUDE_CONFIG_DIR` is there only when the user set it; the hook falls back to `$HOME/.claude`. Command hooks run through `sh -c` on macOS/Linux (bash by default; PowerShell on Windows without Git Bash). Hooks for one event run in parallel, so the tripwire cannot read the banner's markers.
- The command is POSIX sh plus a `python3 -c` verdict that mirrors `plugin_activation` and uses nothing newer than Python 3.0; if `python3` is absent or fails (the macOS shim), sh prints the could-not-verify line. A test checks the verdict against `plugin_activation_status` on the same fixtures.
- A missing manifest gets the soft could-not-verify line, following the module's rule (`unknown`). Loud only for `inactive`.
- Matcher `startup|resume|clear|compact|fork`, the banner's own, so "no banner" and "the tripwire would have spoken" cover the same starts. Timeout 10s.
- The hook is kept out of `INSTALL_REFERENCE`. That contract is merged shallowly per top key and compared leaf by leaf, and a hook list is neither, so `print-install-reference` and the `contract-drift` probe are unchanged. One owner, `lib/unloaded_tripwire.py`, holds the text; it is found by a leading `: prawduct-unloaded-tripwire v1` no-op line and replaced in place when stale.
- Writers: `transform_settings` (so `init-product` and `/prawduct:migrate`) and a new `prawduct-hook install-tripwire [--apply] [--json]`, which doctor Check #1 runs. `repo_toggle` writes only `enabledPlugins` and needs nothing. *Not settled by the plan:* adding a subcommand rather than having doctor hand-edit the JSON.
- *Not settled by the plan:* a second advisory, `install-reference` / `tripwire-missing` (info, routes to `/prawduct:doctor`), fires on an onboarded repo whose settings lack the current hook. Without it nothing tells an already-onboarded repo to run doctor.
- Chunk 02: the anchor's Claude Code signal is now the session banner (replacing "`/prawduct:*` commands are available", since the banner is already in context and the commands take a call to check), and its plugin-off sentence now says "before any work" and "don't … imitate its gates from its files". The product shape's injected footprint was at its ceiling (2198 of 2199), so the line is paid for in place by trimming the intro, the "With it loaded" lead and the enforcement sentence. The reading stays 2198. The Hardest rules are untouched.
- Chunk 02: the shipped v3.7.1–v3.7.2 anchor is archived as `ANCHOR_V6` so `reanchor` offers the update. A third `anchor_repair.SUBSTANCE` row (`session banner`, "the no-banner rule") makes it grade `stale` with that one sentence named, instead of `ok`. *Not settled by the plan:* this also grades an owner-edited anchor without the phrase as `stale-modified`; doctor Check #4's prose lists the new sentence.

## Chunks

### Chunk 01: the tripwire hook, written by onboard and doctor

- **Description:** The project-level SessionStart hook and its message; the writers that put it in
  a product repo's `.claude/settings.json` (find them: `init_product.py`, `migrate_plugin.py`,
  `install_reference_probes.py`, `repo_toggle.py` and the onboard/doctor skills all touch that
  file — grep for the settings writer, do not assume). The writer merges into existing settings and
  is idempotent. The install-reference probes accept the new hook as part of a correct reference.
- **Depends on:** none
- **Deliverables:** the hook command (one owner for its text), its writers, its probe
- **Tests:** the hook run against fixture `installed_plugins.json` files — empty plugins →
  inactive line; user-scope record → silent; project record for this repo → silent; record for a
  different repo only → inactive; unparseable file → unknown, no "not installed" claim; missing
  file → per the module's rule. Writer: fresh settings, existing settings with other hooks, and a
  second run (no duplicate).
- **Acceptance criteria:** Success bullets 1-4
- **Done when:**
  0. verify-api — confirm against current Claude Code docs that a project `.claude/settings.json`
     SessionStart hook runs when the plugin is not loaded and that its stdout reaches the agent's
     context; record what was confirmed and where in "Decisions made mid-build"
  1. Acceptance criteria met and tests pass
  2. Committed

### Chunk 02: the anchor line

- **Description:** One line in the governance anchor template (Success bullet 5), and wherever the
  anchor's text is pinned or budgeted. Mind the anchor's size budget tests.
- **Depends on:** none
- **Deliverables:** the anchor template and its tests
- **Done when:**
  1. Tests pass
  2. Committed

### Chunk 03: change record

- **Type:** cumulative-final
- **Description:** `.prawduct/changes/unloaded-tripwire.md`: narrative and consumer note (tell
  product owners to run `/prawduct:doctor` to get the hook), `closes: [brookstalley/prawduct#1078]`.
- **Deliverables:** `.prawduct/changes/unloaded-tripwire.md`
- **Done when:**
  1. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
