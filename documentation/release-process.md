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
not ship.** Always bump `version` in `plugin/.claude-plugin/plugin.json` (and `plugin/VERSION`, which it mirrors, plus `pyproject.toml`) as part of the release.

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
> **Install-correctness finding — the marketplace entry's plugin `source` must be a *relative path*,
> not a `{ "source": "github", … }` object.** For prawduct's single-repo plugin+marketplace, the
> `github` source form makes Claude Code **re-clone the repo over SSH** (`git@github.com:…`) to fetch
> the plugin — which fails with "Permission denied (publickey)" on any machine without SSH keys (i.e.
> most HTTPS/`gh`-auth users), *even for a public repo*. A relative source reuses the marketplace's
> own (HTTPS) checkout — one clone, no SSH dependency — and inherits the marketplace's pinned `ref`.
>
> **The relative path is `"./plugin"`, not `"./"` (v3.1.1).** `"./"` distributed the entire
> repository, putting prawduct's own backlog, learnings, build plans, tests and internal
> requirements into every consumer's plugin cache. `plugin/` is a curated root holding the distributed files directly (real files, never symlinks -- a symlink farm installs inert on a core.symlinks=false checkout)
> holding only what consumers run; the installer dereferences them into real content. The SSH
> argument above is unaffected — both are relative paths. `tests/test_plugin_packaging.py` pins the
> boundary; see **GOV-4H7T** for why there is no exclusion mechanism to use instead.

## Release checklist (`develop` → `main`)

When `develop` is ready to release as `vX.Y.Z`:

1. **Merge `develop` → `main`.**
2. **Bump the version** in `plugin/.claude-plugin/plugin.json` `version` **and** `plugin/VERSION` **and** `pyproject.toml`
   (they mirror each other). This is the release trigger — without it, nothing ships.
3. **Flip the change-log entries** for the shipped work to `status=shipped` — **every
   unreleased entry, statusless OR legacy `status=merged`**. Entries arrive at release-prep
   **statusless by design**: a feature PR adds its entry with no `status=`, and that
   statusless tagged entry IS the release-pending state (no post-merge stamp exists —
   requiring one forced protected-branch repos into bookkeeping-only PRs). A statusless
   entry silently skipped here never flips its checkboxes and never reaches release notes
   (v2.0.14 shipped 8 of 10 entries that way — REL-2N8K). Enumerate ALL tagged entries
   above the prior `release=vX` boundary; also add the `release=vX.Y.Z` tag (the `scope=`
   tag normally already exists from the build):
   ```
   <!-- prawduct: chunks=01,02,… | release=vX.Y.Z | status=shipped | scope=<plan-scope> -->
   ```
4. **Regenerate derived views:** run `prawduct-hook regen-views --check` first — the
   pre-flight validates every change-log tag against the plan roster without writing
   anything (exit 2 + ERROR lines name any tag that would fail to flip); fix errors, then
   run `prawduct-hook regen-views` for real. With `views_enabled`, the build
   plans' `## Status` checkboxes, release notes, and `scope_rollups` are a *derived view* of
   the change-log's `status=shipped` entries — they flip to `[x]` only at this release step.
   Do **not** hand-edit the checkboxes; `regen-views` would revert the edit.
   **Batched releases (multiple scopes in one version):** a single `regen-views` now regenerates
   the `## Status` of **every** release-pending plan in one pass — it enumerates each distinct
   `scope=` in the change-log (`status` ∈ {`shipped`, `merged`}) and resolves it to its build-plan
   file via that plan's frontmatter `scope:` (REL-4T8N). Validation is fail-closed (VWS-6R4T):
   an unrecognized `status=`, a `chunks=` ID missing from its plan's `## Status` roster, an
   unreleased scope with no matching plan file, a duplicate `scope:` across plan files, or
   conflicting tag lines aborts the whole regen (exit 2, nothing written) — no silent partial
   flips. Chunk-ID matching is tolerant (`chunks=1` flips `Chunk 01`; case and `-`/`_`
   variants match).
5. **Tag the release:** `git tag vX.Y.Z` (and push the tag).
6. **Confirm the banner.** On the next session against the new `main`, the version-delta banner
   shows `v(old) → vX.Y.Z` plus the crossed releases' change-log highlights, and announces any
   gate newly active in the range.

### Change-log `status=` values

Three states are meaningful to the release flow:

- **Statusless (tagged)** — the normal **release-pending** state: the entry merged to
  `develop` inside its feature PR (the entry's presence on the integration branch IS the
  proof of merge — no stamp needed, and none is applied; the old post-merge
  `stamp-merged` chore commit forced consumers with protected integration branches into a
  second, bookkeeping-only PR, so it was retired). Step 3 flips it to `shipped` at
  release; `regen-views` enumerates its `scope=` as release-pending and fails loudly
  (exit 2) when that scope resolves to no plan file. It does **not** flip checkboxes, so
  the build plan's `## Status` stays `[ ]` and the plan + `active_build_plan` pointer are
  retained until the release (see "KEEP the build plan" in `learnings.md`). The
  `/prawduct:pr` merge flow honors this: a feature→`develop` merge **retains** the plan
  and pointer (merge-flow step 7), while on a trunk repo the closing PR itself carries the
  `status=shipped` entry and the plan retirement (create-flow Step 1d).
- **`status=merged`** — **legacy** synonym of the statusless state, applied by the retired
  merge-flow stamp step (`prawduct-hook stamp-merged`, now deprecated). Accepted
  indefinitely — older logs carry it — and treated identically to statusless by step 3 and
  by the regen diagnostics.
- **`status=shipped`** — the work is in a tagged release. This is the **only** value that
  `regen-views` flips to `[x]` (in `## Status`, release notes, and `scope_rollups`).

On a repo whose integration branch is **protected** (commits land only by PR), release-prep
itself rides in a PR — that one release PR is the only bookkeeping vehicle the flow ever
needs; no per-feature housekeeping commit exists anywhere in the lifecycle.

Any other `status=` value (including a typo) is a **fatal validation error** (VWS-6R4T,
promoting the VWS-3K7P typo-guard): `regen-views` exits 2 with an ERROR line and writes
nothing, as it does for a `chunks=` ID missing from its plan's roster, an unreleased scope
with no plan file, duplicate scopes, or conflicting tag lines. Entries with multiple
non-conflicting tag lines are still unioned with a stderr WARNING (VWS-4D8J) — fix the
format, but the output is correct. Run `regen-views --check` before tagging; it must exit 0.

## Step 1 mechanics — promoting when `develop` and `main` have diverged

Because releases land on `main` as **squash/single-parent** commits (not back-merged into
`develop`), `develop` and `main` accumulate divergent histories. Consequence: a `develop` → `main`
PR will report **"merge conflict cannot be cleanly created"** once more than one release has passed
— the conflicts are bookkeeping artifacts, not real disagreements. Do **not** resolve this by
back-merging `main` into `develop` (it pollutes `develop` with the squash commits and is the
"no back-merge" rule's whole point). Promote directly to `main` instead, and close any develop→main
PR that was opened with a note saying so.

**Two promotion shapes exist**, and which one applies is decided by Phase 0 of
`.prawduct/runbooks/cut-and-publish-a-plugin-release.md`, not by preference: if any release-pending
scope is classified `withheld`, the promotion is pruned. `main`'s tree is a *deliberately chosen and
fully classified* snapshot of `develop` — every path shipped or withheld behind a named open
blocker, nothing unaccounted (`operational-spec.md` § Direction, amended 2026-07-29). Content
identity is the expected **outcome** of the whole-develop shape, not the rule both shapes obey.

**Whole-develop** — nothing withheld. `main`'s tree is set equal to `develop`'s and committed
directly (the practice used for v2.0.0 / v2.0.1 / v2.0.4):

```sh
git checkout main && git pull
git read-tree --reset -u origin/develop      # main's index+worktree := develop's tree
git commit -m "release: vX.Y.Z — <headline>" # single-parent commit on main, develop's tree
git diff --stat origin/develop HEAD          # MUST be empty — this shape only, see below
git push origin main
git tag vX.Y.Z && git push origin vX.Y.Z
```

**Pruned** — used for **v3.1.1 and v3.1.2**. The candidate is built as the previous release's tree
plus `git diff <cut-point>..develop` applied with `--3way`, published by ref
(`git push origin <sha>:refs/heads/main`) rather than by checking `main` out. `main`'s tree
deliberately differs from `develop`'s, so the content-identity line above **can never pass and must
not be used** — an empty diff there would mean the withheld work shipped. Its completion test is the
**partition**: every path in `origin/main..origin/develop` accounted for as shipped or deliberately
withheld. Two further checks are mandatory and are not optional hygiene — on the v3.1.2 candidate a
*clean* `git apply` produced a `NameError` in a shipped path and 11 failing tests, because the ship
set depended on an import the withheld set had added: run the suite on the candidate tree, and diff
each shipped Python file's imports against its `develop` counterpart.

The executable procedure is `.prawduct/runbooks/promote-a-pruned-release.md`; the worked example is
`.prawduct/artifacts/release-plan-v3.1.2-pruned.md`.

Note on **step 2 ordering**: the version bump + change-log/CHANGELOG/release-notes updates +
`active_build_plan` clear are done as a **release-prep commit on `develop`** *before* the promotion
above, not as edits on `main` after the merge. That puts the release bookkeeping inside the promoted
tree under **either** shape — the whole-develop tree-set inherits it, and the pruned candidate picks
it up because the release-prep commit is the tip of the ship-set range. Since REL-4T8N, `regen-views` (step 4) resolves each
scope-tagged plan from the change-log rather than the single `active_build_plan` pointer, so for a
**scope-tagged** plan you may run `regen-views` either before or after clearing the pointer. The
pointer's fallback still matters when **no** scope-tagged plan resolves — a single unscoped plan
(the conventional `artifacts/build-plan.md`, or an off-convention pointer-named plan with no
frontmatter `scope:`). In that unscoped case `regen-views` finds the plan only via the pointer, so
run it **before** clearing the pointer (clearing first makes the fallback resolve to a missing
`artifacts/build-plan.md` and raise). For a patch release with no
`scope=`/`chunks=` tag (nothing for it to flip), `regen-views` still touches no plan; the
`release-notes.md` digest self-heals on the next release's regen (or add the entry by hand).

## `/prawduct:pr` is not the release vehicle

The promotion above is a **manual** tree-set — do **not** drive a `develop`→`main` release with
`/prawduct:pr`. That skill is shaped for **feature→`develop`** PRs; its Create flow now detects a
release/integration context (current branch is `develop` or `main`) and redirects here instead of
running its feature-PR gates (REL-8K3M).

If you nonetheless reach the cumulative-Critic gate during a release — e.g. you run `prawduct-hook
check-cumulative-critic` by hand against the release-prep commit — a non-zero exit is **expected and
benign**, not a gate to satisfy:

- **Why it fires:** release-prep necessarily touches non-`.md` files (the `version` strings in
  `plugin/.claude-plugin/plugin.json` + `plugin/VERSION` + `pyproject.toml`, and the `regen-views`-regenerated `scope_rollups` in
  `project-state.yaml`). The CRT-7M2D coverage gate only excuses a doc-only (`.md`) delta since the
  recorded review, so these version/derived-view edits read as "code changed since review" → exit 1.
- **Why it's benign:** the operative pre-release reviews already happened — each feature had a clean
  cumulative Critic at its feature→`develop` merge, and the release-readiness PR reviewer ran on each
  feature PR. The release adds no new behavior, only version bookkeeping.
- **What to do:** nothing for this gate. Do **not** re-run `/prawduct:critic cumulative` over version
  bumps (zero added signal — the CRT-7M2D treadmill), and do **not** write `.gates-waived` — a waiver
  means "this gate cannot be satisfied this session," which is false here (the gate is perfectly
  satisfiable in a feature context; it simply isn't the release's gate). The stop hook also stands
  down on its own: release-prep clears `active_build_plan`, so its Critic gate sees no active plan.
  The operative pre-promotion check is the one that matches the promotion shape: the empty
  `git diff --stat origin/develop HEAD` for a whole-develop promotion, or the path partition for a
  pruned one.

## Why the checkboxes stay `[ ]` during development

Because the Status checkboxes derive from `status=shipped` change-log entries, a chunk completed
on a feature branch stays `[ ]` until the `develop` → `main` release flips its change-log entry
to `shipped` and `regen-views` runs. During feature-branch development, the build plan's Context
line and git history are the progress record — not the checkboxes.
