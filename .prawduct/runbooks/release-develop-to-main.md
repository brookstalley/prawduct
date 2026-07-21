---
runbook: release-develop-to-main
tier: 3
owner: prawduct maintainer
last_verified: null
verified_by: null
---

# Release — promote `develop` to `main`

## When to use this

`develop` holds work you want to publish to consumers as a new version — written below as
`vX.Y.Z`, meaning a real version like `v3.1.1`. Before you start anything, look at what you'd
be shipping:

```sh
git fetch origin && git log --oneline origin/main..origin/develop
```

Everything listed should be work you mean to ship right now. If something in there isn't ready,
stop here — hold it back on a feature branch. Don't release it and revert.

**Picking the number.** Versioning here is deliberately conservative: a small feature is a patch
bump (`v3.1.0` → `v3.1.1`), not a minor. If you think this release deserves a minor or major bump,
that's a decision worth writing down rather than a reflex (`operational-spec.md` §Direction).

## When NOT to use this

<!-- Maintainer note, not for the reader: docs/release-process.md's numbered checklist opens with
     "Merge develop -> main", which its own "Step 1 mechanics" section then forbids. The mechanics
     section is right. That contradiction belongs in an issue against that doc, not in this
     runbook's prose. -->

- **If you're merging a feature branch into `develop`:** → that's `/prawduct:pr`. Come back here
  when `develop` is ready to publish.
- **If you're about to merge `develop` into `main`:** → don't. This procedure sets `main`'s tree
  instead of merging, because a merge reports conflicts that aren't real. Go to step 11.
- **If you only want to see what a release would contain:** → the `git log` command above answers
  that on its own. Nothing here is needed.

## Before you start

**Blast radius:** every consuming repo. Consumers pin `ref: "main"` with `autoUpdate: true`, so
once you push to `main` with a bumped version, they'll pick it up at their next session start.

**Check these before step 1** — finding out at step 15 that you can't push is expensive:

- [ ] You can push to `origin/main` directly (this procedure doesn't go through a PR)
- [ ] `git` and `python3` are on your PATH, and you're in the repo root
- [ ] You know the one-line release headline you want consumers to see
- [ ] Your tree is clean: `git status --porcelain` prints nothing

---

## Phase 1 — Release prep, committed on `develop`

<!-- All the bookkeeping lands on develop first, so main inherits it in the tree-set and the two
     stay content-identical. Nothing in this phase touches main. -->

1. Get onto a current `develop`:

   ```sh
   git checkout develop && git pull
   ```

   **Pass:** `git status -sb` shows `## develop...origin/develop` with no `[behind]`.

2. Run the tests:

   ```sh
   python3 -m pytest tests/ -q
   ```

   **Pass:** exit status 0, no failures.
   **If not:** stop. Don't release a red suite.

   > *Why: the release checklist doesn't ask for this, and there's no CI to catch it for you.
   > `project-state.yaml` declares the test command; nothing runs it automatically.*

3. Bump the version in **both** `.claude-plugin/plugin.json` (the `version` field) and `VERSION`.

   **Pass:** they agree, and both show the new version:

   ```sh
   grep '"version"' .claude-plugin/plugin.json; cat VERSION
   ```

   > *Why: `version` is the update cache key. Promote without bumping it and nothing ships — the
   > consumer re-resolves `main`, sees a string it already has, and keeps its cached copy. The two
   > files mirror each other, so updating one and forgetting the other is the failure to watch for.*

4. Bump `version` in `pyproject.toml` to the same number.

   > 🚧 **UNVERIFIED — check whether `pyproject.toml` is really part of a release.** The file's own
   > comment says "keep this in step on release", but the release checklist never mentions it and
   > it's already drifted (`3.0.3` while `VERSION` says `3.1.0`). Ask the maintainer. If the answer
   > is no, skip this step and fix that misleading comment.

5. In `.prawduct/change-log.md`, flip every unreleased entry to `status=shipped` and add the
   release tag:

   ```
   <!-- prawduct: chunks=01,02,… | release=vX.Y.Z | status=shipped | scope=<plan-scope> -->
   ```

   **Pass:** nothing tagged above the previous `release=` line is still statusless or
   `status=merged`.

   > *Why: entries arrive statusless on purpose, so "statusless" is what release-pending looks
   > like. Miss one and it never flips its checkboxes and never reaches the release notes —
   > v2.0.14 shipped 8 of 10 entries that way.*

   > ⚠️ `regen-views` only recognizes the exact string `--check`. Anything else — a typo, `--help` —
   > is ignored, and the command writes for real.

6. Dry-run the derived views:

   ```sh
   python3 bin/prawduct-hook regen-views --check
   ```

   **Pass:** exit 0, and no `ERROR` lines in the output.
   **If not:** fix whatever tag the ERROR line names, then run it again. Don't continue past an
   exit 2 — it's telling you a tag won't resolve.

7. Regenerate them for real:

   ```sh
   python3 bin/prawduct-hook regen-views
   ```

   **Pass:** the shipped scopes' build plans report `updated`, and their `## Status` boxes now show
   `[x]`. Don't hand-edit a checkbox — the next regen will just revert it.

8. Set `active_build_plan` to `null` in `.prawduct/project-state.yaml`.

9. Add your one-line headline for this release to `CHANGELOG.md`.

10. Commit the prep and push it:

    ```sh
    git add -A && git commit -m "release: prep vX.Y.Z" && git push origin develop
    ```

    **Pass:** `git status -sb` shows no `[ahead]`.

### Checkpoint

`origin/develop` now holds exactly the tree you want to publish — version bumped, change-log
entries shipped, views regenerated, plan pointer cleared. Nothing has reached a consumer yet, and
everything so far is undoable with an ordinary commit.

**This is a good place to stop** if you're interrupted. Pick up at step 11.

---

## Phase 2 — Promote to `main`

<!-- develop and main carry divergent histories with identical content, so a PR between them
     reports phantom conflicts. Set main's tree to develop's instead. Never back-merge main
     into develop. -->

11. Get onto a current `main`:

    ```sh
    git checkout main && git pull
    ```

    **Pass:** `git status -sb` shows `## main...origin/main` with no `[behind]`.

12. Point `main`'s tree at `develop`'s:

    ```sh
    git read-tree --reset -u origin/develop
    ```

    **Pass:** `git status --porcelain` lists staged changes. If it's empty, `main` already matches
    `develop` — stop and work out whether this release is already out.

13. Commit the release on `main`:

    ```sh
    git commit -m "release: vX.Y.Z — <your headline>"
    ```

14. Confirm `main` and `develop` really are identical:

    ```sh
    git diff --stat origin/develop HEAD
    ```

    **Pass:** the output is **completely empty**. That's the invariant the whole branch model rests
    on, and it's your last chance to catch a bad promotion before anyone sees it.
    **If not empty:** stop and go to *If this doesn't work*. Nothing has shipped.

> ⚠️ **IRREVERSIBLE — step 15 publishes to every consuming repo.**
> **Go ahead only if:** step 14 printed nothing at all, and step 6 exited 0.
> **Stop if:** either of those isn't true, or you can't say out loud what's in this release.
> **Cost of stopping:** nothing. It all still lives on `develop`, and `main` is untouched.
> **After this point:** there's no rollback. Consumers on `autoUpdate` may already have the new
> version, and you can't recall it. Recovery is forward only — fix on `develop` and cut the next
> patch version.

15. Publish:

    ```sh
    git push origin main
    ```

    **Pass:** the push reports `main -> main` with your new commit.

16. Tag it:

    ```sh
    git tag vX.Y.Z && git push origin vX.Y.Z
    ```

    **Pass:** `git ls-remote --tags origin vX.Y.Z` comes back with a ref.

    > *Why: tags don't drive consumer updates — the marketplace resolves the branch HEAD — so
    > skipping this fails silently and you won't notice. `v3.0.2` has a changelog entry and no tag.*

---

## Done when

```sh
git diff --stat origin/develop origin/main   # nothing
git show origin/main:VERSION                 # your new version
git ls-remote --tags origin vX.Y.Z           # one ref
```

All three hold, and the next session opened in a consuming repo shows the version-delta banner
going from the old version to yours.

## Close-out

- [ ] Point `active_build_plan` in `.prawduct/project-state.yaml` at the next build plan you're
      working on. Step 8 cleared it deliberately, and leaving it null means the next session's
      Critic gate sees no active plan.

## If this doesn't work

- **A `develop` → `main` PR says "merge conflict cannot be cleanly created":** that's expected, and
  it's the reason this procedure exists. Those conflicts are bookkeeping artifacts — the content
  matches, the history doesn't. Use the tree-set in step 12. **Don't back-merge `main` into
  `develop`** to make it go away; that pollutes `develop` permanently.
- **Step 14's diff isn't empty:** either something landed on `main` outside this procedure, or
  `develop` moved while you were working. Fetch again and redo step 12. If it's still not empty,
  stop and find out why before you push anything.
- **`prawduct-hook check-cumulative-critic` exits non-zero during a release:** expected, and safe
  to ignore. Release prep touches non-`.md` files, which that gate reads as unreviewed code. Don't
  re-run the Critic over version bumps, and don't write `.gates-waived` — nothing is actually wrong.
- **You're stuck and it's late:** this repo has one maintainer, so there's nobody to escalate to.
  Stop and come back to it tomorrow. As long as you haven't run step 15, everything is still on
  `develop` and nothing has shipped.

## Maintenance

**Last executed or rehearsed:** never — nobody has run this yet.
**Validated by:** nobody yet. Treat it as untrusted until someone uses it for a real release and
fixes whatever trips them up.
