---
description: Onboard a repo to Prawduct — scaffold a new or existing repo onto the plugin (the install/setup entry point)
argument-hint: "[target-path]"
user-invocable: true
disable-model-invocation: false
allowed-tools: Bash(prawduct-hook init-product*), Bash(prawduct-hook coverage-scaffold*), Bash(prawduct-hook backlog provision*), Bash(python3 plugin/bin/prawduct-hook backlog provision*), Bash(prawduct-hook check-plugin-active*), Bash(python3 plugin/bin/prawduct-hook check-plugin-active*), Bash(git status*), Bash(git -C * status*), Bash(git add *), Bash(git -C * add *), Bash(git commit *), Bash(git -C * commit *), Read, Glob, Grep
---

You are onboarding a repo onto Prawduct under the **plugin** distribution model. Prawduct is installed as a Claude Code plugin (dev-time governance); a product commits only the install *reference* plus its own `.prawduct/` state — no framework files. Onboarding is the same whether the repo is brand-new or an existing codebase, and it operates on the consumer's own repo — there is no framework checkout to call back to.

(For an already-onboarded repo, health-check / repair / maintenance lives in **`/prawduct:doctor`**, not here.)

## Onboard Flow

Onboarding under the plugin model is plugin-native — there is no file-sync setup script. Pick the shape by inspecting the target:

### A. New or existing repo with no `.prawduct/` yet → **scaffold it**

`prawduct-hook init-product` creates the product-owned state for a plugin repo: `.prawduct/` (project-state.yaml with `distribution: plugin`, backlog.md, change-log.md, artifacts/), the starter rules corpus at `.claude/rules/learnings/core.md`, the thin static CLAUDE.md anchor, and the committed install reference — and **none** of the file-sync machinery (no `tools/`, no committed skills, no sync-manifest). It works identically for an empty repo and one with years of existing code (for existing code, discovery later reads it to infer conventions).

1. Confirm the target directory with the user (it should be a git repo), and note whether it is **this session's own working directory** — that decides how onboarding ends (see Finish).
2. **Settle the backlog backend** — GitHub Issues unless there's a reason not to (*Choosing the backlog backend*, below). It has to be settled *before* the scaffold, because that is the only time `--backlog-repo` is honored.
3. **Dry-run** the scaffold and present the plan: `prawduct-hook init-product <target> --name "<Product Name>" [--backlog-repo <owner/repo>] --json` (no `--apply`). Surface that it creates only product-owned state + the install reference, and which backlog backend it records. Note which paths in the result's `edited` list `git -C <target> status --porcelain --ignored -- <those paths>` already lists in any state (modified, staged, untracked or ignored) — they hold the owner's own content, and the commit step needs to know. Name the paths: a bare `status` shows a wholly untracked `.claude/` only as `?? .claude/`, so its `settings.json` reads clean, and without `--ignored` an ignored file is not listed at all.
4. **Confirm**, then apply with the same flags plus `--apply`. On the Issues backend, provision the labels next (that section's step 2).
5. **Check that the plugin will load there** (the mandatory step below).
6. **Offer to commit the scaffold** — one ask, one commit (Finish).
7. **Go into discovery, or hand over the one step to it** (Finish).

### B. Existing pre-2.0 file-sync repo (committed `tools/product-hook`, framework `.claude/skills/`, `.prawduct/sync-manifest.json`) → **migrate it**

Have them run **`/prawduct:migrate`** in the target: it commits the install reference, strips the committed framework files, drops the legacy hook wiring, and records `distribution: plugin` — one reversible commit.

### Choosing the backlog backend — recommend GitHub Issues

**Recommend GitHub Issues from day one** — say so as your recommendation, then let the owner decide. Onboarding is the cheap moment to adopt it. After the scaffold, `--backlog-repo` is ignored, and moving a markdown backlog onto Issues becomes a cutover: the `/prawduct:backlog scrub` runbook, which imports every item as an issue. A markdown backlog is also the one the framework nudges away from. Once it holds structured items, every session carries a `backlog-service-migration-required` warning until the product migrates or declines to.

State what each choice costs before the owner picks — the price is qualitative, so name the kind of thing, not a tally:

- **GitHub Issues** needs a GitHub repo the owner can file issues in and `gh` authenticated. Items are real issues, visible to everyone who can see that repo — **a public repo means a public backlog** — and GitHub has no ordinary issue delete. Backlog reads go through a local cache that syncs from GitHub. From the first session, the advisories that watch the markdown file stand down, since there is no live file for them to watch. A backlog check with no Issues-backend path says so where it runs, rather than going quiet. The scaffolded `.prawduct/backlog.md` stays in the repo inert — the backlog skill never reads it on this backend.
- **Markdown** (`.prawduct/backlog.md`) needs no GitHub, no `gh`, not even a git remote, and works entirely offline. It is the right call when the product has no GitHub home (another forge, air-gapped, no remote) or the owner does not want an Issues tracker. If that is permanent, it gets recorded with `/prawduct:backlog decline-migration <reason>`, which must run in the target's own session. When onboarding runs there, run it before the commit so the record lands in it. From another directory, it goes in the closing report. Without it, the migration warning above starts once the backlog holds structured items, and it can never resolve.

For Issues, onboard **owns provisioning for this entry path** (scrub owns it at migration; doctor owns the reconcile-as-repair) — two steps, in order:

1. **Record the backend** as part of the scaffold — pass the confirmed target to `init-product`:
   `prawduct-hook init-product <target> --name "<Product Name>" --backlog-repo <owner/repo> --apply --json`
   **Ask the owner which repo holds the backlog.** It is usually the product's own repo, but it may be a dedicated backlog repo or an org repo. Have them confirm the exact `owner/repo`, and never infer it from a git remote: a wrong guess files issues into a repo nobody chose, and they cannot be deleted. Recording is validated shape-only and offline — the repo need not exist on GitHub yet, and the current directory need not be a git repo. On an *already-scaffolded* repo this flag is ignored (recording the backend then is a cutover, `/prawduct:backlog scrub`, not a re-scaffold).
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
  On first trusted open, Claude Code adds the marketplace from this reference without prompting — but it **does not install the plugin**, because it never auto-installs one sourced from a repository. So tell the owner plainly: **every contributor runs `claude plugin install prawduct@prawduct` once**, and until they do, their clone runs with no hooks, no `/prawduct:*` and no gates, and Claude Code says nothing about it. The `CLAUDE.md` anchor is what tells such a session to raise it — do not describe onboarding as making governance automatic for the next person, because it does not.
- **Integration base branch.** When the target's `origin/HEAD` names a branch outside `main`/`master` — a repo whose remote default is `develop` — the scaffold (and `/prawduct:migrate`) records `base_branch: <b>` in `project-state.yaml`, and reports it as `base_branch` in the JSON result. That scalar is what every diff-base gate anchors to: coverage, the cumulative Critic, and the PR gates. A trunk repo gets no key and needs none; a branch the remote names but has never fetched is deliberately not recorded (an unresolvable `base_branch:` fails those gates closed). **The remote's default is a good guess, not the truth.** If features merge onto a branch the remote does not default to — `origin/HEAD` says `main` while the team integrates on `develop`, the case detection cannot see — say so and have the owner set `base_branch:` by hand. Unset, the gates guess `main`, and a gitflow repo then reviews the whole `develop..main` promotion delta on every feature.
- `/prawduct:doctor` health-checks the install anytime after onboarding.

### Prove the plugin will actually load there — MANDATORY

**Run `prawduct-hook check-plugin-active --path <target>` before you report success.**

Writing the install reference is *not* what loads the plugin. The harness also needs a
`prawduct@prawduct` record whose `projectPath` is the target, and a repo missing one starts every
session with **no banner, no `/prawduct:*` skills, and no Stop-hook gates** — and unless its
`CLAUDE.md` anchor carries the plugin-absent notice (`/prawduct:doctor` Check #4 brings an older one
up to date), nothing tells the agent so and it proceeds ungoverned. This is the one failure the target
repo cannot detect about itself: the probes
and `/prawduct:doctor` that would report it are delivered by the plugin that did not load. **This
session is the only one that can ask**, which is why the check is here and not in `doctor`.

Route on the status, not on the exit code alone — there are three answers, and two of them exit 0:

| Status | What to do |
|---|---|
| `active` | Continue to Finish. |
| `inactive` (exit 1) | **Do not report success.** Relay the command's own output — it names the consequence, the exact `claude plugin install` line, and which other paths the plugin *is* installed for. The operator runs it; onboarding is not finished until they do. |
| `unknown` (exit 3) | The check could not run — a harness-internal file was missing or unreadable. Say that it **was not established**, never that it passed. Tell them to confirm by opening the target and looking for the prawduct session briefing. |

**Exit 3 is not a failure of onboarding** — it is the same *unverified* sentinel `check-released`
carries, and it means the question went unanswered rather than answered badly. Do not treat it as
`inactive` and do not treat it as `active`; relay the command's own text, which says both what was
attempted and what remains unknown.

## Finish: commit, then discovery

Onboarding scaffolds the *governance* skeleton — it does **not** capture what is being built.
`project-state.yaml` ships all-`null` (classification, product definition, structural
characteristics) and `project-preferences.md` ships as a blank template. Until discovery fills them,
governance can't calibrate rigor and the build gates can't engage. So onboarding is not done at the
scaffold. It ends *in* discovery, or one step from it — never on a checklist that leaves the owner
asking "so what now?".

**1. Commit the scaffold.** On a markdown backlog the owner means to keep, onboarded in the target's own
session, run `/prawduct:backlog decline-migration <reason>` first — it writes
`.prawduct/project-state.yaml`, so the record rides this commit. Show the paths the commit will hold
(below) and ask once. On yes, commit them
as one commit (`chore: onboard to Prawduct`). The commit holds onboarding's own paths only: the
result's `created` and `edited` lists (`.gitignore` among them when it changed), and any path in its `unignored` list that exists
on disk (a stale ignore line was stripped, so the file is now meant to be tracked). `git -C <target>
add -- <paths>`, then `git -C <target> commit -m "…" -- <paths>`. The trailing pathspec keeps
anything the owner had already staged out of the commit. A pathspec commit takes each named file
whole, though, so if the dry-run step found any `edited` path not clean, say that the owner's own
content in it would ride along, and let them choose. If git refuses (not a git repo, a hook rejects it, no identity configured), relay its
message and report the scaffold as **uncommitted** — never as committed. On no, say the scaffold is
uncommitted and go on.

**2. Report in a few lines, not a manifest.** Lead with the outcome — onboarded, where the backlog
lives, committed or not. Then add only what the owner must act on or would be surprised by:

- the plugin check was `inactive` or `unknown` (the table above);
- `base_branch` was recorded, or there is evidence of gitflow the detection could not see (a
  `develop` branch while the remote defaults to `main`);
- the labels are still pending because `gh` or the repo wasn't there yet;
- a markdown backlog the owner means to keep, onboarded from another directory: `decline-migration` is owed in the target's session;
- when others work in the repo, that each contributor runs `claude plugin install
  prawduct@prawduct` once.

Leave out everything else unless asked: file inventories, label counts, what was not touched,
settings-precedence notes. The next step goes last in the report, and there is only one.

**3. Route on where this session runs:**

| This session is… | Then |
|---|---|
| **in the target** (its working directory) | **Go straight into discovery** — after relaying an `inactive` or `unknown` check result as the table above says. This session has the plugin loaded either way, so discovery can run here; on `inactive`, the report still calls onboarding unfinished until the install runs. Read `/prawduct:methodology discovery` and start it now, without asking whether to — the first discovery question *is* the next turn. When the repo already has code or docs, discovery runs in its reconciliation mode: read the README, docs and code first, then open with your own read of what the product is for, who it serves and what success looks like. Confirm that with the owner, ask only what the material leaves open, then write `project-state.yaml` and the preferences — a product vision the owner has confirmed, not one transcribed from the docs. |
| **anywhere else** (onboarded `../foo` from another repo) | **End on one next step:** open the target in Claude Code (`claude <target>`) and start discovery there with `/prawduct:methodology discovery` — the install command comes first when the check said `inactive`. Don't run discovery from here: this session's hooks and gates govern its own directory, not the target. |

When discovery finishes in the target's session, close by recommending `/clear`. This session
started before `.prawduct/` existed, and the session-start hooks stay silent in a repo without one —
no briefing, no governance digest — so the next session is the first fully governed one.

**During discovery, for products that want minimal documentation** — say so up front: the coverage chain is
satisfied cheaply and permanently in three steps (record the structural characteristics
during discovery; `prawduct-hook coverage-scaffold --apply` for the expected strategy
artifacts, where a one-line "(not relevant — <reason>)" per artifact IS coverage; record
"none to ratify" through `/prawduct:doctor`'s Ratification Flow). After that the chain is
silent. Prawduct is opinionated that absence be a recorded decision — not that
documentation be voluminous.
