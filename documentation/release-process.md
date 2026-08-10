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

0. **Confirm it is fit to ship**, not merely that something is unreleased:
   `./plugin/bin/prawduct-hook check-releasability --release vX.Y.Z`. Every release-pending scope
   must be classified `ships`, or `withheld` behind a **named open** blocker, in the
   `## Release classification` table of `.prawduct/artifacts/release-plan-vX.Y.Z.md`. The gate fails
   closed; its withheld count also selects the promotion shape at step 1. Full branch-by-branch
   handling is Phase 0 of `.prawduct/runbooks/cut-and-publish-a-plugin-release.md`.
1. **Merge `develop` → `main`.**
2. **Bump the version** in `plugin/.claude-plugin/plugin.json` `version` **and** `plugin/VERSION` **and** `pyproject.toml`
   (they mirror each other). This is the release trigger — without it, nothing ships.
3. **Tag the shipped entries `release=vX.Y.Z`.** This is the *only* change-log edit the
   release makes. An entry arrives at release-prep with a `scope=` tag and **no
   `release=`**, and that absence IS the release-pending state — `check-releasability`
   enumerates what is pending by looking for it. Adding the tag is what ships the entry:
   ```
   <!-- prawduct: scope=<plan-scope> | release=vX.Y.Z -->
   ```
   Write a real version. Any other value — a placeholder naming the absence, most of all —
   removes the entry's whole scope from the pending set while reading as deliberate;
   `release=unreleased` on six entries hid an entire branch from v3.2.8.

   > ⚠️ **Which entries shipped is the hard part, and it is not answered here.** "Everything
   > above the prior `release=` boundary" is a search hint, not the set: an entry can merge
   > *below* the boundary and still be unreleased, a release bundle spans several scopes, and
   > under a **pruned** release the naive sweep tags withheld work as shipped. Do not re-derive
   > the set from this document. The sound per-candidate test and the scope enumeration command
   > live at Phase 1 step 2 of `.prawduct/runbooks/cut-and-publish-a-plugin-release.md`. Work
   > from there (REL-7D4X).

   Nothing is regenerated from this tag. Build-plan `## Status` checkboxes are hand-authored
   and were ticked by the sessions that finished each chunk; a plan still showing `[ ]` at
   release means that chunk was never closed out, which is a question for its author, not
   something this step fixes.

4. **Archive the plans this release shipped.** On gitflow the closing PR deliberately
   RETAINS the plan and its `active_build_plan` pointer — the work is not released yet — so
   the release is where that retention ends, and without this step the live artifacts
   directory re-accumulates exactly the pile the archive exists to prevent. Step 3 has just
   made the mechanical answer available, so run the sweep rather than picking by hand:
   ```
   prawduct-hook plan-backfill            # preview: names each plan and the release
   prawduct-hook plan-backfill --apply    # one confirmation covers the whole set
   ```
   It archives every live plan whose `scope=` now carries a `release=` tag, stamping each
   with `lifecycle: completed` and `released_in:`. It is a **no-op for anything still
   pending**, so running it on a pruned release cannot archive withheld work: an untagged
   entry is exactly what step 3 left untagged. **Clear `active_build_plan` BEFORE the
   sweep**, not after: the sweep refuses to archive the plan the pointer names — archiving
   it would leave the pointer at a moved file, which every gate reads as "no active build
   plan" and goes quiet rather than failing — so a pointer left set is a plan left live,
   and the run reports it under the plans it kept rather than the ones it moved.
   The preview also lists, separately, plans the change log says shipped but which the
   sweep **refuses** (a name already in the archive, a plan already carrying a terminal
   state, one it cannot read). Read that list before confirming: those need a person, and
   they are the ones that otherwise stay live silently.
   A plan whose work was **descoped** rather than shipped has no `release=` tag and is not
   swept; give it its end of life by hand, naming what replaced it:
   `prawduct-hook archive-plan <path> --state superseded --superseded-by "<what/why>"`.
5. **Write the consumer-facing narrative — two files, not one.** `plugin/CHANGELOG.md` gets a
   `## vX.Y.Z` section every release; `README.md`'s `## Recent Changes` gets refreshed on a
   **minor or major bump only**. Both are written at **Phase 1 step 10** of
   `.prawduct/runbooks/cut-and-publish-a-plugin-release.md` — this checklist names them rather
   than restating them, because the README went eight releases stale precisely while no release
   document named it at all.
6. **Publish the GitHub Release — the tag is not the release, and this one step creates both.**
   A pushed tag lands on `/tags`; the Releases page is a separate surface and it stayed empty for
   every tag this repo had ever pushed, which is what consumers reported as "no tag on GitHub".

   ```
   awk '/^## vX.Y.Z$/{f=1;next} /^## v/{f=0} f' plugin/CHANGELOG.md > /tmp/notes-vX.Y.Z.md
   gh release create vX.Y.Z --target "$(git rev-parse main)" \
     --title vX.Y.Z --notes-file /tmp/notes-vX.Y.Z.md
   ```

   **One call, not `git tag` and then a publish.** `.github/workflows/verify-release.yml` fires on
   a tag push and one of the three things it asks is whether a Release exists — which a later
   publish step has not yet made true. At v3.2.4 the job reached that check 9 seconds after the
   publish landed, a margin defended by nothing but how fast the operator typed. Creating both in
   one call means no instant exists at which the tag is there without its Release, and it sharpens
   what a red tag-push run means: a tag that arrived by some route other than this step.

7. **Verify what actually shipped:** `git fetch origin --tags` (the tag was created on the remote,
   so your clone does not have it yet), then `./plugin/bin/prawduct-hook check-released vX.Y.Z`.
   Exit **0** verified · **1** a check failed · **3** nothing failed but a check could not run.
   **A 3 is not a pass.**

8. **Run the same check in CI:** `gh workflow run verify-release.yml -f tag=vX.Y.Z`, then read the
   run. It runs step 7's command with a token and goes red on any non-zero, so it is the backstop
   for the release nobody verified by hand. **Dispatch it by hand** — a tag created through the
   Releases API is expected to emit `create` and `release` events, not `push`, so nothing fires
   the workflow on this path. CI verifies; it never publishes.

   > 🚧 **UNVERIFIED** — the no-`push`-event half is reasoned from GitHub's event model and has
   > not been measured here; v3.2.4 was tagged the old way. The dispatch is correct either way,
   > and a push-triggered run appearing alongside it is not an error. Confirm at the next release
   > and correct this — the same note sits at step 21 of
   > `.prawduct/runbooks/cut-and-publish-a-plugin-release.md`, and both should be settled together.
9. **Confirm the banner.** On the next session against the new `main`, the version-delta banner
   shows `v(old) → vX.Y.Z` plus the crossed releases' change-log highlights, and announces any
   gate newly active in the range.

### Two states, carried by the presence or absence of `release=`

- **Release-pending** — tagged `scope=`, **no `release=`**. The entry merged to `develop`
  inside its feature PR, and the entry's presence on the integration branch IS the proof of
  merge: no stamp is needed and none is applied (the old post-merge `stamp-merged` chore
  commit forced consumers with protected integration branches into a second,
  bookkeeping-only PR, so it was retired). `check-releasability` enumerates the entry's
  `scope=` as pending and advises when that scope resolves to no plan file — work shipping
  with nothing describing it. The plan and the `active_build_plan` pointer are **retained**
  until the release, because that pairing is what the gate reads; the `/prawduct:pr` merge
  flow honors this (a feature→`develop` merge retains both — merge-flow step 7), while on a
  trunk repo the closing PR itself carries the `release=`-tagged entry and the plan
  retirement (create-flow Step 1d).
- **Shipped** — `release=vX.Y.Z` present. Step 3 adds it, and adding it is the whole
  transition.

**A legacy `status=` tag is inert.** Older logs carry `status=merged` and `status=shipped`
from the retired derived-views mechanism. Nothing reads them, no value of them means
anything, and they are neither rewritten nor removed — rewriting 21 repos' history is churn
with no consumer. Read the `release=` tag, never the `status=` one.

On a repo whose integration branch is **protected** (commits land only by PR), release-prep
itself rides in a PR — that one release PR is the only bookkeeping vehicle the flow ever
needs; no per-feature housekeeping commit exists anywhere in the lifecycle.

### The `release=` tag names a version, or it is absent

There is no placeholder. The unreleased set is every entry tagged `scope=` with **no**
`release=`, so *any* value marks the entry already-released — a placeholder that names the
absence (`release=unreleased`) reads as deliberate while removing that entry's whole scope
from the release-pending set. `check-releasability` then answers "no release-pending scopes
— nothing to classify" and the work never ships, which is REL-2N8K's failure with a more
convincing disguise (six entries hid a whole branch from v3.2.8 that way). A `release=`
that is not `vMAJOR.MINOR.PATCH` (optionally `-suffix`) is therefore a **validation error**
that fails closed — an unevaluable release state must never read as "fine". Release-pending
is the tag's absence; step 3 adds it, and that is the only edit.

**Where the refusal now happens.** `check-releasability` itself refuses it — exit 1 with a
`bad-change-log-tag:` line naming the entry and its line number. It used to be checked only by
the derived-views regenerator, which a release did not run — which is why the v3.2.8 placeholder
reached a release at all: the guard existed and nothing on the release path called it. Rehoming
it onto the gate that acts on the field is the durable fix, and it is the reason this validator
survived the retirement of the five around it. The gate also
reports two **advisories** that do not change its exit code — a release-pending scope with no
build-plan file (work shipping with nothing describing it), and two plans declaring one scope.

Entries with multiple non-conflicting tag lines are unioned with a stderr WARNING
(VWS-4D8J) — fix the format, but the reading is correct. Run `check-releasability` before
tagging and read its exit code; a `bad-change-log-tag:` refusal is the release blocker.

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

# One call creates the tag AND the Release — see below for why not `git tag` first.
awk '/^## vX.Y.Z$/{f=1;next} /^## v/{f=0} f' plugin/CHANGELOG.md > /tmp/notes-vX.Y.Z.md
gh release create vX.Y.Z --target "$(git rev-parse main)" \
  --title vX.Y.Z --notes-file /tmp/notes-vX.Y.Z.md
git fetch origin --tags                            # the tag was created on the remote
./plugin/bin/prawduct-hook check-released vX.Y.Z   # exit 0 = released; 3 = a check could not run
gh workflow run verify-release.yml -f tag=vX.Y.Z   # the same check with a token; dispatch by hand
```

**The tag is not the release.** A pushed tag lands on `/tags`; the Releases page is a separate
surface, and it stayed empty for every tag the repository had ever pushed. That is what consumers see and
what they report as "no tag on GitHub" — so the publish step is part of the procedure, not an
optional flourish. `check-released` verifies all of it (version files agreeing at the tag's own
tree, the tag contained in `origin/main`, the Release present) and is the one command to run
afterwards. Note the exit codes: **0** verified, **1** something failed, **3** nothing failed but a
check could not run — a `3` is not a pass. **Repo-local on purpose:** at this moment the *installed*
plugin is the previous release, and a bare `prawduct-hook` resolves to it — an unknown subcommand
there exits 1, which is this command's own code for *not-released*. `gh workflow run
verify-release.yml -f tag=vX.Y.Z` runs the same check in CI with a token and is the backstop for the
release nobody verified by hand; it never publishes a Release, by owner ruling. The workflow also
triggers on a tag push, but that route is not expected to fire for a release cut this way, since the
tag now comes into being through the Releases API — so treat the dispatch as the run that counts
(step 8 above carries the unverified half of that claim).

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

Note on **step 2 ordering**: the version bump + change-log/CHANGELOG updates +
`active_build_plan` clear are done as a **release-prep commit on `develop`** *before* the promotion
above, not as edits on `main` after the merge. That puts the release bookkeeping inside the promoted
tree under **either** shape — the whole-develop tree-set inherits it, and the pruned candidate picks
it up because the release-prep commit is the tip of the ship-set range. Nothing in the step reads a
build plan, so the `active_build_plan` clear can happen anywhere in the prep commit.

## `/prawduct:pr` is not the release vehicle

The promotion above is **manual** — a tree-set for the whole-develop shape, a `--3way` apply
published by ref for the pruned one — and neither is driven with `/prawduct:pr`. Do **not** drive a
`develop`→`main` release with it. That skill is shaped for **feature→`develop`** PRs; its Create flow now detects a
release/integration context (current branch is `develop` or `main`) and redirects here instead of
running its feature-PR gates (REL-8K3M).

If you nonetheless reach the cumulative-Critic gate during a release — e.g. you run `prawduct-hook
check-cumulative-critic` by hand against the release-prep commit — a non-zero exit is **expected and
benign**, not a gate to satisfy:

- **Why it fires:** release-prep necessarily touches non-`.md` files (the `version` strings in
  `plugin/.claude-plugin/plugin.json` + `plugin/VERSION` + `pyproject.toml`). The CRT-7M2D coverage
  gate only excuses a doc-only (`.md`) delta since the recorded review, so these version edits read
  as "code changed since review" → exit 1.
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

## The checkboxes are ticked during development, not at release

A chunk's box is ticked by the session that finished the chunk, right after its Critic review
passes. The release does not touch them and no command regenerates them — the boxes, the Context
line, and git history are one progress record, not a derived view and its source.

This is the reverse of the rule that stood here until 2026-08-08, when Status was regenerated from
`status=shipped` change-log entries at release. That mechanism is retired: it meant a plan spent
its entire build reading as untouched, so the boxes were documented as untrustworthy and every
reader was told to look elsewhere — which is a strange thing to keep a tool for. A plan still
showing `[ ]` at release now means the chunk was never closed out.
