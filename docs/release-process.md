# Release Process (v2.0 plugin)

How a Prawduct change goes from a feature branch to something consumers actually receive.
This is for **contributors to the framework**, not product-repo users.

## Branch model — gitflow

- **`develop`** — the integration branch. Feature branches (`feature/…`, `fix/…`) branch off
  `develop` and merge back into `develop`. Nothing here ships to consumers.
- **`main`** — the **release surface**. `main` only ever holds releases. Promoting `develop`
  → `main` is what publishes a new version.

Consumers pin the plugin + marketplace to **`ref: "main"`** (see the install reference in
`documentation/MIGRATION.md`). They never reference `develop`, so in-progress integration work
is invisible to them. Pinning `main` explicitly — rather than the bare repo — also avoids a
footgun: a bare repo silently follows GitHub's *default-branch* setting, which would ship
`develop` if that default ever changed.

## The version is the release trigger — not cosmetic

Claude Code resolves a plugin's version from `plugin.json` `version` first. With
`autoUpdate: true`, the consumer re-resolves `main` at session start, but **`version` is the
update cache key**: if you promote a commit to `main` without bumping `version`, `autoUpdate`
sees the same string and keeps the cached copy — **a release that forgets the version bump does
not ship.** Always bump `version` (and the `VERSION` file it mirrors) as part of the release.

> **Spike results (Chunk 2, empirically confirmed 2026-06-02 on a throwaway public plugin+marketplace repo).**
> The model holds — no fallback needed:
> - **`version` is the cache key — confirmed.** A commit pushed to `main` that changed plugin
>   content but kept `version` the same did **not** ship (`plugin update` reported "already at the
>   latest version"; the cached copy was untouched). Bumping `version` shipped on the next update.
>   *A release that forgets the version bump does not ship.*
> - **Resolution tracks the branch HEAD, not the latest tag — confirmed.** Every version bump
>   shipped from an **untagged** `main` HEAD. Tags are irrelevant to a branch-pinned marketplace,
>   so the `ref: "vX.Y.Z"` tag-pin fallback is **not** required (it remains available if a future
>   Claude Code release changes this).
> - **`ref: "main"` must be pinned explicitly — confirmed footgun.** A marketplace added without a
>   `ref` (e.g. `claude plugin marketplace add <repo>`, or an `extraKnownMarketplaces` source with
>   no `ref`) records no ref and **follows the repo's default branch**. The committed install
>   reference pins `ref: "main"` precisely to avoid this — keep it.
> - **`develop` is isolated — confirmed.** A *higher* version pushed to `develop` was never consumed
>   by a `main`-pinned consumer.
> - **autoUpdate stages, then applies on restart.** At session start `autoUpdate` re-resolves `main`
>   and downloads a newer `version` into the plugin cache, but the *active* copy flips on the next
>   start (or an explicit `claude plugin update`). The version-delta banner makes the applied version
>   visible. (Initial install is active immediately — no lag on first open.)
> - **First flag-free open needs an interactive marketplace-trust approval.** A new marketplace can't
>   be trusted headlessly, so a consumer's first `claude` open (without `--plugin-dir`) prompts to
>   trust the prawduct marketplace, then installs. Expected Claude Code security behavior.
>
> **Install-correctness finding — the marketplace entry's plugin `source` must be `"./"`, not a
> `{ "source": "github", … }` object.** For prawduct's single-repo plugin+marketplace, the `github`
> source form makes Claude Code **re-clone the repo over SSH** (`git@github.com:…`) to fetch the
> plugin — which fails with "Permission denied (publickey)" on any machine without SSH keys (i.e.
> most HTTPS/`gh`-auth users), *even for a public repo*. A relative `"source": "./"` reuses the
> marketplace's own (HTTPS) checkout — one clone, no SSH dependency — and inherits the marketplace's
> pinned `ref`. `marketplace.json` therefore uses `"./"`.

## Release checklist (`develop` → `main`)

When `develop` is ready to release as `vX.Y.Z`:

1. **Merge `develop` → `main`.**
2. **Bump the version** in `.claude-plugin/plugin.json` `version` **and** the `VERSION` file
   (they mirror each other). This is the release trigger — without it, nothing ships.
3. **Flip the change-log entries** for the shipped work from `status=merged` to
   `status=shipped`, and add the `release=vX.Y.Z` and `scope=vX.Y.Z` tags to the entry's
   tag line:
   ```
   <!-- prawduct: chunks=01,02,… | release=vX.Y.Z | status=shipped | scope=vX.Y.Z -->
   ```
4. **Regenerate derived views:** `prawduct-hook regen-views`. With `views_enabled`, the build
   plans' `## Status` checkboxes, release notes, and `scope_rollups` are a *derived view* of
   the change-log's `status=shipped` entries — they flip to `[x]` only at this release step.
   Do **not** hand-edit the checkboxes; `regen-views` would revert the edit.
   **Batched releases (multiple scopes in one version):** a single `regen-views` now regenerates
   the `## Status` of **every** release-pending plan in one pass — it enumerates each distinct
   `scope=` in the change-log (`status` ∈ {`shipped`, `merged`}) and resolves it to its build-plan
   file via that plan's frontmatter `scope:` (REL-4T8N). You no longer point `active_build_plan` at
   each plan in turn and re-run per scope. A `status=merged` scope with no matching plan file is
   reported on stderr and skipped (not fatal).
5. **Tag the release:** `git tag vX.Y.Z` (and push the tag).
6. **Confirm the banner.** On the next session against the new `main`, the version-delta banner
   shows `v(old) → vX.Y.Z` plus the crossed releases' change-log highlights, and announces any
   gate newly active in the range.

### Change-log `status=` values

Two values are meaningful to the release flow:

- **`status=merged`** — the work is merged to `develop` but **not yet in a tagged release**
  (release-pending). `regen-views` does **not** flip checkboxes for `merged` entries, so the
  build plan's `## Status` stays `[ ]` and the `active_build_plan` pointer is retained until the
  release (see "KEEP the build plan" in `learnings.md` and the `active_build_plan` note in
  `project-state.yaml`). This is the develop-phase intermediate that step 3 flips to `shipped`.
  The `/prawduct:pr` merge flow honors this: a feature→`develop` merge **retains** the plan and
  pointer (merge-flow step 7), while a merge whose base is the release surface deletes them.
- **`status=shipped`** — the work is in a tagged release. This is the **only** value that
  `regen-views` flips to `[x]` (in `## Status`, release notes, and `scope_rollups`).

Any other `status=` value (including a typo) is currently treated like "not shipped" — the entry
is silently ignored by the derived views with no warning. Authors editing tag lines by hand should
double-check the spelling; a misspelled `status=shipped` will never flip its checkboxes. (The
`lib/views.py` docstring's legacy `in-progress`/`deferred` names predate the `merged` convention
and are not emitted today; reconciling the docstring + adding a typo-guard warning is tracked in
the backlog.)

## Step 1 mechanics — promoting when `develop` and `main` have diverged

Because releases land on `main` as **squash/single-parent** commits (not back-merged into
`develop`), `develop` and `main` accumulate divergent histories even though their *content* stays
identical at each release. Consequence: a `develop` → `main` PR will report **"merge conflict
cannot be cleanly created"** once more than one release has passed — the conflicts are bookkeeping
artifacts (same final content reached by different commits), not real disagreements. Do **not**
resolve this by back-merging `main` into `develop` (it pollutes `develop` with the squash commits
and is the "no back-merge" rule's whole point).

Instead, promote by setting `main`'s tree equal to `develop`'s and committing directly to `main`
(the practice used for v2.0.0 / v2.0.1 / v2.0.4):

```sh
git checkout main && git pull
git read-tree --reset -u origin/develop      # main's index+worktree := develop's tree
git commit -m "release: vX.Y.Z — <headline>" # single-parent commit on main, develop's tree
git diff --stat origin/develop HEAD          # MUST be empty (content-identical)
git push origin main
git tag vX.Y.Z && git push origin vX.Y.Z
```

Close any develop→main PR that was opened with a note that the release was promoted directly. The
empty `git diff origin/develop HEAD` is the content-identical invariant the gitflow model promises.

Note on **step 2 ordering**: the version bump + change-log/CHANGELOG/release-notes updates +
`active_build_plan` clear are done as a **release-prep commit on `develop`** *before* the promotion
above (so `main` inherits them in the tree-set), not as edits on `main` after the merge. That keeps
`main` and `develop` content-identical. Since REL-4T8N, `regen-views` (step 4) resolves each
scope-tagged plan from the change-log rather than the single `active_build_plan` pointer, so clearing
the pointer no longer strands the regen for scope-tagged plans — run `regen-views` either before or
after clearing it. The pointer's fallback still matters only when **no** scope-tagged plan resolves
(e.g. a repo with a single unscoped `artifacts/build-plan.md`). For a patch release with no
`scope=`/`chunks=` tag (nothing for it to flip), `regen-views` still touches no plan; the
`release-notes.md` digest self-heals on the next release's regen (or add the entry by hand).

## Why the checkboxes stay `[ ]` during development

Because the Status checkboxes derive from `status=shipped` change-log entries, a chunk completed
on a feature branch stays `[ ]` until the `develop` → `main` release flips its change-log entry
to `shipped` and `regen-views` runs. During feature-branch development, the build plan's Context
line and git history are the progress record — not the checkboxes.
