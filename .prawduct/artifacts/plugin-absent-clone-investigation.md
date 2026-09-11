---
artifact: discovery
scope: plugin-absent-governance-anchor
date: 2026-08-25
measured_against: Claude Code 2.1.245 / 2.1.246 (darwin)
---

# What a Prawduct-Governed Repo Does On a Machine Without the Plugin

## Why this was investigated

The onboarding contract says a product repo commits only its own `.prawduct/` state plus a small
install *reference* in `.claude/settings.json`, and that governance arrives from the plugin. The
open question was what the next person gets: someone who clones the repo onto a machine where the
prawduct plugin has never been installed. Does governance work, do they get told to install
anything, and does anything error?

## Method

A clean machine was simulated rather than argued about: a fresh `CLAUDE_CONFIG_DIR` (no marketplaces,
no installed plugins), a scratch git repo carrying the exact committed install reference from
`lib/migrate_plugin.py` `INSTALL_REFERENCE`, a `CLAUDE.md` carrying the `PRAWDUCT:ANCHOR` block, and
a `.prawduct/project-state.yaml`. Sessions were run with `claude --debug -p`, and the workspace-trust
flag was seeded to `true` to model a teammate who trusted the folder. Because the API leg of a
headless run exits fast, one run was held open against a socket that accepts and never answers, so
the asynchronous plugin reconcile had time to finish and be observed.

## Findings

### 1. The marketplace registers. The plugin does not install.

After trust, Claude Code clones the marketplace declared in the repo's `.claude/settings.json` and
writes it into the machine-level `known_marketplaces.json`. It stops there.
`installed_plugins.json` stays `{"version": 2, "plugins": {}}`.

```
[DEBUG] [reconcile] 1 marketplace(s): prawduct(install)
[DEBUG] installPluginsForHeadless: installed marketplace prawduct
[DEBUG] Found 0 plugins (0 enabled, 0 disabled)
```

This is documented current behavior, not a defect in the reference. From
`code.claude.com/docs/en/discover-plugins`, "Configure team marketplaces":

> As of Claude Code v2.1.195, adding the marketplace doesn't install plugins that come from an
> external source, on any path that loads plugins. A plugin that only the project's
> `.claude/settings.json` enables, and that comes from an external source such as a GitHub
> repository or npm package, doesn't load until the team member installs it.

The committed install reference is therefore **necessary but no longer sufficient**. It is what makes
the one-line fix possible; it is not what performs it.

### 2. Governance is entirely absent, and the session is silent about it

```
[DEBUG] Skipping orphaned enabledPlugins entry prawduct@prawduct: marketplace not registered
[DEBUG] Registered 0 hooks from 0 plugins
[DEBUG] Total plugin skills loaded: 0
```

No SessionStart briefing, banner, or digest. No Stop hook, so neither the Critic gate nor the
reflection gate exists. No `/prawduct:*` skills. No `critic-reviewer` agent.

**There are no errors and no warnings.** Session stdout measured zero bytes. The single trace is a
`[DEBUG]` line nobody sees without `--debug`, and it disappears on the *second* session once the
marketplace has registered — from then on the repo looks entirely normal while running entirely
ungoverned. Claude Code does report the plugin as not-installed inside the `/plugin` panel, which is
a place nobody opens unprompted.

It never self-corrects. Sessions 2..N are identical.

### 3. The anchor keeps asserting enforcement that is not there

`CLAUDE.md` loads regardless of plugins, so the `PRAWDUCT:ANCHOR` block is the one governance
surface that *does* reach this session. It currently tells that session:

> **Enforcement is structural:** the plugin's Stop hook runs at session end and **blocks** if code
> changed against an active build plan with no Critic findings.

That is false wherever it is read by a session that lacks the plugin — which is exactly the session
that needs the truth. The same block directs the agent to `/prawduct:methodology building` before
writing code and to `/prawduct:critic` after it, both unresolvable, and it never names the command
that would fix any of it.

The failure mode is not absence of governance. It is **silent false assurance**: an agent that
believes a gate is behind it, building against a plan with nothing checking the work.

### 4. The remediation is one command, and nothing points at it

Verified end-to-end against the simulated machine. Once the first open has registered the
marketplace:

```
claude plugin install prawduct@prawduct
```

The next session loads 6 hooks, 14 skills, and 1 agent, and the digest fires. The gap is purely that
nobody is told.

### 5. Three shipped documents assert the retired behavior

- `README.md` — "Anyone who clones the repo gets the same governance (the plugin auto-installs on
  first trusted open)."
- `plugin/skills/onboard/SKILL.md` — "On first trusted open, Claude Code prompts each developer to
  install the marketplace + plugin (one-time, skippable)." There is no prompt at all.
- `documentation/MIGRATION.md` — "Fresh clones auto-activate the plugin on first trusted open,
  thanks to the committed install reference — no setup step for the next person." There is a setup
  step for the next person.

These are the instructions an owner reads when deciding what to tell their team, so each one
actively suppresses the message that would close the gap.

## What is NOT wrong

Worth recording, because the obvious suspects are innocent:

- **The install reference is correct.** Every leaf matches `INSTALL_REFERENCE`; it is what registers
  the marketplace, and without it the teammate would also have to add the marketplace by hand.
- **`enabledPlugins` in a committed project file is legitimate** and is the documented team
  mechanism. It is skipped cleanly when the plugin is absent — no error, no corrupt state.
- **Nothing is broken on a configured machine.** This costs the current operator nothing, which is
  precisely why it survives: the condition is invisible from where it would be noticed.

## Decision taken

Owner-approved 2026-08-25, chosen from three framed options (anchor-only / anchor + committed
SessionStart hook in the consumer repo / docs-only):

**Anchor-only.** The static anchor is the only carrier that reaches a plugin-less session, so it
carries the notice and stops asserting unconditional enforcement. A committed hook in consumer repos
was rejected: it reintroduces committed framework machinery, which the plugin distribution model
exists to eliminate.

**Accepted limitation, stated rather than discovered later:** the anchor is advisory. An agent that
reads it cannot install the plugin itself — installation is a shell command its user approves — so
the anchor degrades to "tell the human." That is a large improvement on silence and is not
enforcement, and no wording makes it enforcement.

## The follow-up this deliberately did not build

**An ambient advisory probe for a stale or lying anchor.** `/prawduct:doctor` is invoked, not
emitting — so under the approved scope a repo whose anchor still promises an unconditional Stop gate
stays silent until somebody thinks to run a health check on a repo that appears to be working. That
is the same "nobody runs a health check on a repo that looks fine" difficulty
`install_reference_probes.py` was written for, and that module is the model to copy: cause-agnostic,
state-not-event, self-resolving, `info` priority so it never reaches the person-facing relay.

It was not built because it is scope the owner did not approve, and the bounded exception is
recorded against the proportionality norm in the build plan's `governed_by` dispositions. **Build it
if the doctor route proves too quiet** — the signal would be repos that stay stale across releases.

## Out of scope

- Changing `INSTALL_REFERENCE` (it is correct).
- Any committed hook, script, or framework file in a consumer repo.
- Making the plugin auto-install; Claude Code deliberately does not, and prawduct must not work
  around a security boundary.
