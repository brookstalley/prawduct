---
description: Onboard a repo to Prawduct — scaffold a new or existing repo onto the plugin (the install/setup entry point)
argument-hint: "[target-path]"
user-invocable: true
disable-model-invocation: false
allowed-tools: Bash(prawduct-hook init-product *), Read, Glob
---

You are onboarding a repo onto Prawduct under the **plugin** distribution model. Prawduct is installed as a Claude Code plugin (dev-time governance); a product commits only the install *reference* plus its own `.prawduct/` state — no framework files. Onboarding is the same whether the repo is brand-new or an existing codebase, and it operates on the consumer's own repo — there is no framework checkout to call back to.

(For an already-onboarded repo, health-check / repair / maintenance lives in **`/prawduct:doctor`**, not here.)

## Onboard Flow

Onboarding under the plugin model is plugin-native — there is no file-sync setup script. Pick the shape by inspecting the target:

### A. New or existing repo with no `.prawduct/` yet → **scaffold it**

`prawduct-hook init-product` creates the product-owned state for a plugin repo: `.prawduct/` (project-state.yaml with `distribution: plugin`, learnings.md, backlog.md, change-log.md, artifacts/), the thin static CLAUDE.md anchor, and the committed install reference — and **none** of the file-sync machinery (no `tools/`, no committed skills, no sync-manifest). It works identically for an empty repo and one with years of existing code (for existing code, discovery later reads it to infer conventions).

1. Confirm the target directory with the user (it should be a git repo).
2. **Dry-run** the scaffold and present the plan: `prawduct-hook init-product <target> --name "<Product Name>" --json` (no `--apply`). Surface that it creates only product-owned state + the install reference.
3. **Confirm**, then apply: `prawduct-hook init-product <target> --name "<Product Name>" --apply`.
4. Tell the user to commit the result.

### B. Existing pre-2.0 file-sync repo (committed `tools/product-hook`, framework `.claude/skills/`, `.prawduct/sync-manifest.json`) → **migrate it**

Have them run **`/prawduct:migrate`** in the target: it commits the install reference, strips the committed framework files, drops the legacy hook wiring, and records `distribution: plugin` — one reversible commit.

### Either way

- The committed install *reference* (project scope) in `.claude/settings.json` is the only prawduct content the repo commits, and it never drifts — `init-product` writes it for new repos, `/prawduct:migrate` for existing file-sync ones:
  ```json
  {
    "extraKnownMarketplaces": { "prawduct": { "source": { "source": "github", "repo": "brookstalley/prawduct", "ref": "main" }, "autoUpdate": true } },
    "enabledPlugins": { "prawduct@prawduct": true }
  }
  ```
  On first trusted open, Claude Code prompts each developer to install the marketplace + plugin (one-time, skippable).
- Governance activates only in the target's OWN session: **"Open `<target>` in a new Claude Code session — the hooks and the session briefing won't fire until then."**
- After onboarding, run **`/prawduct:doctor`** in the repo anytime to health-check the install.
