# Migrating a Product Repo: file-sync (v1.x) → plugin (v2.0)

This guide is for **existing Prawduct repos** — set up with `prawduct-setup.py` and carrying
committed framework files. It moves them onto the v2 plugin in **two steps: one reversible
commit, all your product state preserved.**

(Starting a *new* product, or already on the plugin? You don't need this — see the
[README](../README.md).)

## Migrate in two steps

### 1. Install the plugin

Run these in a shell — once per machine; they work for all your repos:

```bash
claude plugin marketplace add brookstalley/prawduct
claude plugin install prawduct@prawduct
```

This gives *you* the `/prawduct:*` skills (needed for step 2). Step 2 then commits a per-repo
install reference, so everyone who clones the repo gets the plugin automatically — no flags, no
framework files in the tree.

> **Developing the framework itself?** Skip the install and load your working copy instead:
> `claude --plugin-dir /path/to/prawduct/plugin --add-dir /path/to/prawduct`. The `--add-dir` (same
> path) lets methodology-reading skills (`/prawduct:methodology building`, `/prawduct:critic`) load their
> bundled guides out-of-tree. `--plugin-dir` alone is enough for `/prawduct:migrate`; a real
> marketplace install needs neither flag.

### 2. Run the cutover

From the product repo, on a **clean working tree** (commit or stash in-progress work first —
the cutover must land as one clean commit):

```bash
cd ~/your-product
claude
> /prawduct:migrate
```

It does a dry run, shows you exactly what will change, asks you to confirm, then applies and
commits — all as **one `git revert`-able commit**.

**That's it.** Verify with `/prawduct:doctor`.

---

*Everything below is reference — you don't need it to migrate.*

## What `/prawduct:migrate` does

1. **Clean-tree check** — refuses to proceed on a dirty tree.
2. **Dry run** — `prawduct-hook migrate-plugin --json` (no changes); presents the plan (files
   removed, dirs removed, files edited, the retired state keys removed, the gitignored marker). If
   the repo is already on the plugin (`distribution: plugin` present), it reports a no-op and stops.
3. **Confirm** — nothing is mutated until you approve. The state keys are the part worth reading
   twice: they are the only deletions that land *inside* a file your product hand-authored.
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
  `.prawduct/build-governance.md` (the plugin's bundled protocols + `/prawduct:methodology building` govern now)
- The now-inert `.prawduct/sync-manifest.json`

**Edited in place** (your content preserved):
- `CLAUDE.md` — the heavy `<!-- PRAWDUCT:BEGIN/END -->` block is replaced by a thin, version-free
  **static governance anchor** (a pointer to the plugin plus the few hardest rules). Your own
  product-specific instructions, above and below the block, are untouched.
- `.claude/settings.json` — the prawduct hook wiring and framework banner are removed and the
  plugin install reference is merged in. Your own keys, hooks, and marketplaces are preserved.
  This is the per-repo reference that auto-activates the plugin for everyone who clones the repo:
  ```jsonc
  {
    "extraKnownMarketplaces": {
      "prawduct": { "source": { "source": "github", "repo": "brookstalley/prawduct", "ref": "main" }, "autoUpdate": true }
    },
    "enabledPlugins": { "prawduct@prawduct": true }
  }
  ```
- `.prawduct/project-state.yaml` — a `distribution: plugin` line is appended (the signal
  that tells the frozen legacy hook to stand down), and **retired framework keys are removed**:
  `views_enabled`, `scope_rollups` (the retired derived-view model) and `build_state.test_tracking`
  (a hand-maintained test count, removed with whatever `assertion_count` / `test_files` / `history`
  bookkeeping shares its block). These are framework residue, not product content — nothing in the
  runtime reads them, no template scaffolds them, and what `test_tracking` copies has a real home in
  the test evidence store. The dry run names every key it would remove, so the one confirmation
  covers it. An already-migrated repo converges the same keys with `/prawduct:doctor`.

**Never touched** (product-owned, mutable):
- The rest of `.prawduct/` — everything in `project-state.yaml` other than the keys above,
  any `learnings*.md` the repo still carries (a legacy corpus `learnings-migrate` relayouts), `backlog.md`, `change-log.md`, `artifacts/`,
  `.critic-findings.json`.
- **All** non-framework files — your own skills, `src/`, `tests/`, MCP servers, configs.

## After migrating

- **Verify.** `/prawduct:doctor` confirms the repo is on the plugin and the governance surface
  is intact.
- **Governance** now comes from the plugin: the Stop hook's Critic + reflection gates, the
  SessionStart briefing + banner + guidance digest. Skills are `/prawduct:*`.
- **Updates** arrive via the marketplace with zero repo diff. The version banner shows the
  current version and, on a bump, what changed.
- **Fresh clones** auto-activate the plugin on first trusted open, thanks to the committed
  install reference — no setup step for the next person.

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

## Background: why v2 moved to a plugin

You don't need this to migrate — it's here if you want the reasoning.

In v1.x, the framework was **copied into your repo** and kept in sync by a script. That caused
the papercuts v2.0 removes:

- Framework files were committed in your tree, so every framework update produced a diff you had
  to fold into your own commits (stash/pop/merge churn).
- Synced files could be locally edited and silently drift from the framework.
- There was no clean version signal — the framework version lived in `sync-manifest.json` after
  a successful pull.

In v2.0 the framework ships as a **Claude Code plugin**. Your repo commits *zero* framework
files — only the small install reference. The framework code lives out-of-tree in the plugin
cache and updates with zero repo diff.

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
