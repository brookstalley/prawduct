# Migrating a Product Repo: file-sync (v1.x) → plugin (v2.0)

This guide is for **existing Prawduct product repos** — repos that were set up with
`prawduct-setup.py` and carry committed framework files. It walks you from the v1.x
file-sync model to the v2.0 plugin model with a single, reversible command.

If you are starting a **new** product, you don't need this — install the plugin and go.
This guide is only about moving an existing file-sync repo onto the plugin.

> **Status (read first).** The plugin install path depends on the prawduct **marketplace**
> being published, which is the final step of the v2.0 rollout and is still pending. Until
> then you can migrate today using the `--plugin-dir` developer path (below). The cutover
> mechanics (`/prawduct:migrate`) are complete and tested; only the marketplace publish is
> outstanding. This note will be removed once the marketplace is live.

## Why migrate

In v1.x, the framework was **copied into your repo** and kept in sync by a script. That
caused the papercuts v2.0 removes:

- Framework files were committed in your tree, so every framework update produced a diff
  you had to fold into your own commits (stash/pop/merge churn).
- Synced files could be locally edited and silently drift from the framework.
- There was no clean version signal — the framework version lived in `sync-manifest.json`
  after a successful pull.

In v2.0 the framework ships as a **Claude Code plugin**. Your repo commits *zero* framework
files — only a small install reference. The framework code lives out-of-tree in the plugin
cache and updates with zero repo diff.

## Before / after

| Concern | v1.x (file-sync) | v2.0 (plugin) |
|---|---|---|
| Framework code location | committed in your repo | `~/.claude/plugins/cache/` (out of tree) |
| Update mechanism | `sync` + auto-commit, leaves drift | marketplace update, **zero repo diff** |
| Framework checkout tracking | repo tracks a path to the framework checkout — `PRAWDUCT_FRAMEWORK_DIR` env, then `framework_source` in `.prawduct/sync-manifest.json`, then a sibling `../prawduct` | **none** — there is no framework checkout to locate |
| Mutable product state | repo `.prawduct/` | repo `.prawduct/` (**unchanged**) |
| Version source | `sync-manifest.json` after a pull | plugin's own `plugin.json` (offline-safe) |
| Skill names | `/critic`, `/pr`, `/prawduct-doctor`, … | `/prawduct:critic`, `/prawduct:pr`, `/prawduct:doctor`, … |
| Stash/pop/merge papercuts | structural | **eliminated** |

The key shift in one line: v1 tracked *where the framework lives on disk*; v2 doesn't need to,
because the framework is no longer in your tree at all.

## Prerequisites

1. **Install the prawduct plugin.**
   - **Marketplace (target path, once published):** add the prawduct marketplace and enable
     the plugin — Claude Code prompts you on first trusted open. The install reference the
     cutover commits to `.claude/settings.json` is what makes this automatic for every
     developer who clones your repo:
     ```jsonc
     {
       "extraKnownMarketplaces": {
         "prawduct": { "source": { "source": "github", "repo": "brookstalley/prawduct", "ref": "main" }, "autoUpdate": true }
       },
       "enabledPlugins": { "prawduct@prawduct": true }
     }
     ```
   - **Developer path (available today):** clone the prawduct repo and launch Claude Code with
     `claude --plugin-dir /path/to/prawduct` from your product repo. This loads the plugin for
     the session without a marketplace.
2. **A clean working tree.** The cutover lands as one reviewable commit, so commit or stash any
   in-progress work first.

## The cutover — one command

From your product repo, run **`/prawduct:migrate`**. It performs a dry-run first, shows you
exactly what will change, asks for confirmation, applies, and commits — all in one reversible
commit. Concretely:

1. **Clean-tree check** — refuses to proceed on a dirty tree.
2. **Dry run** — `prawduct-hook migrate-plugin --json` (no changes); presents the plan
   (files removed, dirs removed, files edited, the gitignored marker). If the repo is already
   on the plugin (`distribution: plugin` present), it reports a no-op and stops.
3. **Confirm** — you approve before anything is mutated.
4. **Apply** — `prawduct-hook migrate-plugin --apply`.
5. **Commit** — one `chore(prawduct): migrate to plugin distribution` commit.

The engine is plugin-native, so it needs no framework checkout — a repo that committed only the
install reference can still migrate.

## Exactly what it changes

The cutover derives the remove-set from the **framework registry** — it never deletes "any path
prawduct ever placed," only known framework files.

**Removed** (now provided by the plugin):
- The framework skills under `.claude/skills/` — `critic`, `pr`, `janitor`, `learnings`,
  `backlog`, `prawduct-advisory`, `prawduct-doctor`
- `tools/product-hook` and the framework `tools/lib/*` runtime
- The framework protocol docs `.prawduct/critic-review.md`, `.prawduct/pr-review.md`,
  `.prawduct/build-governance.md` (the plugin's bundled protocols + `/prawduct:building` govern now)
- The now-inert `.prawduct/sync-manifest.json`

**Edited in place** (your content preserved):
- `CLAUDE.md` — the heavy `<!-- PRAWDUCT:BEGIN/END -->` block is replaced by a thin, version-free
  **static governance anchor** (a pointer to the plugin plus the few hardest rules). Your own
  product-specific instructions, above and below the block, are untouched.
- `.claude/settings.json` — the prawduct hook wiring and framework banner are removed and the
  plugin install reference is merged in. Your own keys, hooks, and marketplaces are preserved.
- `.prawduct/project-state.yaml` — a single `distribution: plugin` line is appended (the signal
  that tells the frozen legacy hook to stand down).

**Never touched** (product-owned, mutable):
- Everything else under `.prawduct/` — `project-state.yaml` content, `learnings.md`,
  `learnings-detail.md`, `backlog.md`, `change-log.md`, `artifacts/`, `.critic-findings.json`,
  reflections.
- **All** non-framework files — your own skills, `src/`, `tests/`, MCP servers, configs.

## After migrating

- **Verify.** Run `/prawduct:doctor` for a health check — it confirms the repo is on the plugin
  and the governance surface is intact.
- **Governance** now comes from the plugin: the Stop hook's Critic + reflection gates, the
  SessionStart briefing + banner + guidance digest. Skills are `/prawduct:*`.
- **Updates** arrive via the marketplace with zero repo diff. The version banner shows the
  current version and, on a bump, what changed.
- If you loaded the plugin via `--plugin-dir` for this session, no restart is needed. If you
  just installed it via the marketplace, reopen the repo to activate it.

## Rollback

The whole cutover is a single commit. To undo it:

```bash
git revert <migrate-commit-sha>
```

The removed framework files return and the legacy file-sync hook resumes governing (it stood
down only while `distribution: plugin` was recorded and/or the plugin was enabled). Re-running
`/prawduct:migrate` after a successful migration is a no-op.

## Coexistence (during the transition)

A repo can have both the plugin enabled and the old committed file-sync hook present — for
example, right before you migrate. There is no double-governance: **the plugin governs and the
legacy hook yields** whenever it detects the plugin (`distribution: plugin` in
`project-state.yaml`, or prawduct in `enabledPlugins`). The detection is conservative — any
missing file or parse error means the legacy hook keeps governing — so a pure, un-migrated
file-sync repo behaves exactly as it always did.
