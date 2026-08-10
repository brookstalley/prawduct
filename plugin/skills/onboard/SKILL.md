---
description: Onboard a repo to Prawduct — scaffold a new or existing repo onto the plugin (the install/setup entry point)
argument-hint: "[target-path]"
user-invocable: true
disable-model-invocation: false
allowed-tools: Bash(prawduct-hook init-product *), Bash(prawduct-hook coverage-scaffold *), Bash(prawduct-hook backlog provision *), Bash(python3 plugin/bin/prawduct-hook backlog provision *), Read, Glob
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
4. Tell the user to commit the result. If the result's `unignored` list is non-empty (stale ignore lines stripped — e.g. a gitignored build plan, now a tracked artifact), name those paths and advise `git add` on any that exist on disk.

### B. Existing pre-2.0 file-sync repo (committed `tools/product-hook`, framework `.claude/skills/`, `.prawduct/sync-manifest.json`) → **migrate it**

Have them run **`/prawduct:migrate`** in the target: it commits the install reference, strips the committed framework files, drops the legacy hook wiring, and records `distribution: plugin` — one reversible commit.

### Adopting the GitHub Issues backlog backend at onboard (optional)

**The default backlog backend is the markdown file** — a new repo needs no GitHub, no `gh`, not even a git remote, and the coverage/gates work entirely offline. Only offer this when the owner explicitly wants their backlog on **GitHub Issues from day one** (the alternative, and the common path for an existing repo, is to stay on markdown and migrate later with `/prawduct:backlog scrub`).

When they do want it, onboard **owns provisioning for this entry path** (scrub owns it at migration; doctor owns the reconcile-as-repair) — two steps, in order:

1. **Record the backend** as part of the scaffold — pass the confirmed target to `init-product`:
   `prawduct-hook init-product <target> --name "<Product Name>" --backlog-repo <owner/repo> --apply`
   This records `backlog_service_repo: <owner/repo>` (validated shape-only, offline — the repo need not exist on GitHub yet, and the current directory need not be a git repo). The `owner/repo` is **owner-named**, never inferred from the current directory's git remote. On an *already-scaffolded* repo this flag is ignored (recording the backend then is a cutover, `/prawduct:backlog scrub`, not a re-scaffold).
2. **Provision the label taxonomy** against that repo (needs `gh` authenticated, and the repo to exist on GitHub):
   `prawduct-hook backlog provision --repo <owner/repo>`
   Idempotent and collision-free — it creates only the `<facet>:`-namespaced base labels it does not find and never touches the repo's existing labels. If `gh` isn't available or the repo doesn't exist yet, say so and have the owner run this step once it does — the backend is recorded either way; only the labels wait.

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

## Next: capture discovery

Onboarding scaffolds the *governance* skeleton — it does **not** capture what you're
building. `project-state.yaml` ships all-`null` (classification, product definition,
structural characteristics) and `project-preferences.md` ships as a blank template. Until
discovery fills them, governance can't calibrate rigor and the build gates can't engage —
and once the repo shows product work, the session briefing nudges every session
(**DISCOVERY NOT CAPTURED**).

So tell the user the first thing to do in the product's own session is **`/prawduct:methodology discovery`**:

- **New / empty repo** → a normal discovery pass captures classification, product
  definition, and preferences into `project-state.yaml`.
- **Existing codebase, or requirements / architecture / vision docs already written** →
  discovery runs in **reconciliation mode**: it reads what's already there and backfills
  `project-state.yaml` (keeping `docs/` as the detailed source) rather than starting over.
  See `methodology/discovery.md` "Reconciling an Existing or Docs-First Product".

This is the seam the docs-first onboarding path slips through if it's not named: a repo can
accrue rich requirements/architecture with an empty source-of-truth, and prawduct only
governs what discovery has captured.

**Products that want minimal documentation** — say so up front: the coverage chain is
satisfied cheaply and permanently in three steps (record the structural characteristics
during discovery; `prawduct-hook coverage-scaffold --apply` for the expected strategy
artifacts, where a one-line "(not relevant — <reason>)" per artifact IS coverage; record
"none to ratify" through `/prawduct:doctor`'s Ratification Flow). After that the chain is
silent. Prawduct is opinionated that absence be a recorded decision — not that
documentation be voluminous.
