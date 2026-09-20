---
description: Migrate this repo from committed file-sync framework files onto the prawduct plugin — one reviewable, reversible commit
argument-hint: ""
user-invocable: true
disable-model-invocation: false
allowed-tools: Bash(prawduct-hook migrate-plugin*), Bash(git status:*), Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(git log:*), Read, Glob
---

You are performing the **file-sync → plugin cutover** for the current repo. This is the
graceful migration that removes the committed framework files (now provided by the plugin)
while preserving **all** product-owned state. It is destructive but reversible — the whole
change lands as **one commit** you can `git revert`.

The plugin governs this repo the moment it is installed (Chunk 8: plugin governs, legacy
yields). This cutover removes the now-redundant committed framework files so the repo commits
zero framework code and stops folding framework drift into its own diffs.

## What gets removed vs. preserved

The cutover engine derives the REMOVE set from the **framework registry** — it never deletes
"any path prawduct ever placed."

- **REMOVED** (registry-derived framework files): the 7 framework skills under
  `.claude/skills/` (critic, pr, janitor, learnings, backlog, prawduct-advisory,
  prawduct-doctor), `tools/product-hook`, framework `tools/lib/*`, the framework protocol docs
  `.prawduct/{critic-review,pr-review,build-governance}.md`, and the now-inert
  `.prawduct/sync-manifest.json`.
- **EDITED in place**: `CLAUDE.md` (the heavy `PRAWDUCT:BEGIN/END` block is stripped and a
  thin **static governance anchor** is inserted in its place — a small, version-free pointer
  to the plugin plus the few hardest rules; the full methodology now lives in the plugin),
  `.claude/settings.json` (prawduct hook wiring + the framework banner removed; the plugin
  install reference added — your own keys/hooks/marketplaces are preserved), and
  `.prawduct/project-state.yaml` (a `distribution: plugin` line appended, and **retired
  framework keys removed** — see below).
- **RETIRED FRAMEWORK KEYS** in `.prawduct/project-state.yaml`: `views_enabled` and
  `scope_rollups` (the retired derived-view model) and `build_state.test_tracking` (a
  hand-maintained test count, plus whatever `assertion_count` / `test_files` / `history`
  bookkeeping sits beside it — the block goes whole). These are framework residue, not product
  content: nothing in the runtime reads them, no template scaffolds them, and the fact
  `test_tracking` copies has a real home in the test evidence store (`prawduct-hook
  test-evidence record`). The dry run names every key it would remove, so your one confirmation
  covers it. A repo that **already** cut over converges the same keys with
  `/prawduct:doctor` — the detection is shared, so the two never disagree about what a retired
  key is.
- **NEVER TOUCHED**: everything else under `.prawduct/` — the rest of `project-state.yaml`,
  any `learnings*.md` the repo still carries, `backlog.md`, `change-log.md`, `artifacts/`,
  `.critic-findings.json` — nor `.claude/rules/learnings/`, and **all** non-framework files:
  the product's own skills, `src/`, `tests/`, MCP server, configs. (Relaying a legacy learnings
  corpus into `.claude/rules/learnings/` is the `learnings-migrate` command's job, not this
  command's.)

## Flow

1. **Confirm a clean working tree.** Run `git status --short`. If there are uncommitted
   changes, tell the user to commit or stash them first — the cutover must land as one clean,
   reviewable commit. Do not proceed with a dirty tree.

2. **Dry run.** Run `prawduct-hook migrate-plugin --json` (no `--apply`). Parse the JSON:
   - If `already_migrated` is true, report "This repo is already on the plugin
     (`distribution: plugin`)." and stop — nothing to do.
   - Otherwise present the plan: the `removed` files, `removed_dirs`, `edited` files, the
     `state_keys_removed` keys, and the `gitignored` marker. Surface that this is destructive
     but reversible.

3. **Confirm intent** with the user before mutating anything. **Name `state_keys_removed` in
   the confirmation** when it is non-empty — it is the one part of the blast radius that lands
   inside a file the product hand-authored, so it is the part an operator would want to have
   been told about rather than to discover in the diff.

4. **Apply.** Run `prawduct-hook migrate-plugin --apply --json`. Relay the result.

5. **Review + commit as one commit.** Run `git status --short` and skim `git diff --stat` to
   confirm the change set matches the plan and that no product file under `.prawduct/`
   (learnings, backlog, change-log, artifacts) was modified. Then:
   ```
   git add -A
   git commit -m "chore(prawduct): migrate to plugin distribution

   Remove committed framework files (now provided by the prawduct plugin);
   add the install reference; record distribution: plugin. Product state and
   all non-framework files are preserved. Reversible via git revert."
   ```

6. **Tell the user** the repo now runs fully on the plugin: governance comes from the plugin's
   Stop hook + SessionStart digest, skills are `/prawduct:*`, and framework updates arrive via
   the marketplace with zero repo diff. If the plugin was loaded via `--plugin-dir` for this
   session, no restart is needed; if they just installed it, a reopen activates it.

## Notes

- **Idempotent.** Re-running after a successful migration is a no-op (`already_migrated`).
- **Reversible.** The single commit can be reverted; the removed framework files return and the
  legacy file-sync hook resumes governing (it stands down only while `distribution: plugin` is
  recorded and/or the plugin is enabled — Chunk 8).
- The engine is plugin-native (`lib/migrate_plugin.py`); it needs no framework checkout, so a
  consumer that committed only the install reference can still migrate.
