---
runbook: release-develop-to-main
tier: 3
owner: prawduct maintainer
last_verified: null
verified_by: null
---

# Release — promote `develop` to `main`

## When to use this

`develop` holds work you intend to publish to consumers as `vX.Y.Z`. Confirm before acting:

```sh
git fetch origin && git log --oneline origin/main..origin/develop
```

Every commit listed is work you intend to ship *now*. If any is not, stop — release what is ready
by holding the rest on a feature branch, not by releasing and reverting.

**Choosing `X.Y.Z`:** versioning here is deliberately conservative — a small feature is a patch
bump, not a minor. A departure is a recorded decision, not a reflex (`operational-spec.md`
§Direction).

## When NOT to use this

- **A feature branch → `develop`.** That is `/prawduct:pr`. This procedure only promotes.
- **You are following `docs/release-process.md` step 1 top-down.** That checklist says "Merge
  `develop` → `main`" first; its own "Step 1 mechanics" section forbids a merge and puts the
  version bump *before* promotion. The mechanics section is correct. This runbook follows it.

## Before you start

**Blast radius:** every consuming repo. Consumers pin `ref: "main"` with `autoUpdate: true`, so
pushing to `main` with a bumped `version` publishes to all of them at their next session start.

**Prerequisites** — check every line before step 1:

- [ ] Push access to `origin/main` (this procedure pushes directly, not via PR)
- [ ] `git` and `python3` on PATH, run from the repo root
- [ ] You know the release headline (one line, consumer-facing)
- [ ] No uncommitted work in your tree: `git status --porcelain` prints nothing

---

## Phase 1 — Release prep, committed on `develop`

<!-- All bookkeeping lands on develop first so main inherits it in the tree-set and the two
     stay content-identical. Nothing here touches main. -->

1. Switch to a current `develop`:

   ```sh
   git checkout develop && git pull
   ```

   **Pass:** `git status -sb` shows `## develop...origin/develop` with no `[behind]`.

2. Run the test suite:

   ```sh
   python3 -m pytest tests/ -q
   ```

   **Pass:** exit status 0, no failures.
   **If not:** stop. Do not release a red suite.

   > *Why: the release checklist does not require this; `project-state.yaml` declares a
   > `test_command` and there is no CI to run it for you.*

3. Bump the version in **both** `.claude-plugin/plugin.json` (`version`) and `VERSION`.

   **Pass:** both read `X.Y.Z` and agree:

   ```sh
   grep '"version"' .claude-plugin/plugin.json; cat VERSION
   ```

   > *Why: `version` is the update cache key. A promotion without a bump does not ship — the
   > consumer re-resolves `main`, sees the same string, and keeps the cached copy.*

4. Bump `version` in `pyproject.toml` to the same value.

   > 🚧 **UNVERIFIED — is `pyproject.toml` part of the release?** Its own comment says "keep this
   > in step on release", but the release checklist never mentions it and it has already drifted
   > (`3.0.3` against `VERSION` `3.1.0`). Confirm with the maintainer; skip this step if the
   > answer is no, and fix the comment.

5. Flip every unreleased change-log entry in `.prawduct/change-log.md` to `status=shipped` and add
   the `release=vX.Y.Z` tag:

   ```
   <!-- prawduct: chunks=01,02,… | release=vX.Y.Z | status=shipped | scope=<plan-scope> -->
   ```

   **Pass:** no tagged entry above the previous `release=` boundary is still statusless or
   `status=merged`.

   > *Why: entries arrive statusless by design. One missed here never flips its checkboxes and
   > never reaches release notes — v2.0.14 shipped 8 of 10 entries that way.*

   > ⚠️ `regen-views` recognizes only the exact string `--check`. Any other argument — including a
   > typo or `--help` — is ignored and the command writes for real.

6. Pre-flight the derived views without writing:

   ```sh
   python3 bin/prawduct-hook regen-views --check
   ```

   **Pass:** exit 0 and no `ERROR` lines.
   **If not:** fix the tag named in the ERROR line and re-run. Do not continue on exit 2.

7. Regenerate the derived views for real:

   ```sh
   python3 bin/prawduct-hook regen-views
   ```

   **Pass:** the shipped scopes' build plans report `updated`, and their `## Status` boxes are
   `[x]`. Do not hand-edit a checkbox — the next regen reverts it.

8. Clear `active_build_plan` in `.prawduct/project-state.yaml` (set it to `null`).

   **Pass:** `grep active_build_plan .prawduct/project-state.yaml` shows no plan path.

9. Add the one-line release headline for `vX.Y.Z` to `CHANGELOG.md`.

   **Pass:** the top entry names `vX.Y.Z`.

10. Commit and push release prep:

    ```sh
    git add -A && git commit -m "release: prep vX.Y.Z" && git push origin develop
    ```

    **Pass:** `git status -sb` shows no `[ahead]`.

### Checkpoint

`origin/develop` now contains the exact tree you intend to publish: bumped version, shipped
change-log entries, regenerated views, cleared plan pointer. Nothing has been published yet, and
everything to this point is revertible by an ordinary commit on `develop`. **It is safe to stop
here** and resume at step 11 later.

---

## Phase 2 — Promote to `main`

<!-- develop and main hold divergent histories with identical content, so a PR reports phantom
     conflicts. Set main's tree to develop's instead. Never back-merge main into develop. -->

11. Switch to a current `main`:

    ```sh
    git checkout main && git pull
    ```

    **Pass:** `git status -sb` shows `## main...origin/main` with no `[behind]`.

12. Set `main`'s tree equal to `develop`'s:

    ```sh
    git read-tree --reset -u origin/develop
    ```

    **Pass:** `git status --porcelain` lists staged changes (empty means `main` was already current
    — stop and confirm the release is not already out).

13. Commit the release on `main`:

    ```sh
    git commit -m "release: vX.Y.Z — <headline>"
    ```

    **Pass:** `git log --oneline -1` shows the release commit.

14. Verify `main` is content-identical to `develop`:

    ```sh
    git diff --stat origin/develop HEAD
    ```

    **Pass:** output is **completely empty**. This is the invariant the whole gitflow model rests
    on, and it is the last check before anything reaches a consumer.
    **If not empty:** abort — go to *If this doesn't work*. Nothing has shipped yet.

> ⚠️ **IRREVERSIBLE — step 15 publishes to every consuming repo.**
> **Proceed only if:** step 14 printed empty output, and step 6 exited 0.
> **Abort if:** either is false, or you cannot name what is in this release → stop; `main` is
> unchanged and no consumer has seen anything.
> **Cost of aborting:** none. Everything so far lives on `develop`.
> **Recovery after this point:** forward-only. A published version cannot be recalled — consumers
> that auto-updated already have it. Recovery is to fix on `develop` and cut `vX.Y.Z+1`.

15. Publish:

    ```sh
    git push origin main
    ```

    **Pass:** push reports `main -> main` with the new commit.

16. Tag the release:

    ```sh
    git tag vX.Y.Z && git push origin vX.Y.Z
    ```

    **Pass:** `git ls-remote --tags origin vX.Y.Z` returns a ref.

    > *Why: tags do not drive consumer updates — the marketplace resolves the branch HEAD. The tag
    > is the human record, and it is the step that silently gets skipped: `v3.0.2` has a changelog
    > entry and no tag.*

---

## Done when

```sh
git diff --stat origin/develop origin/main   # empty
git show origin/main:VERSION                 # X.Y.Z
git ls-remote --tags origin vX.Y.Z           # one ref
```

All three hold, and the next session opened against a consuming repo shows the version-delta
banner `v(old) → vX.Y.Z`.

## Close-out

- [ ] Repoint `active_build_plan` in `.prawduct/project-state.yaml` at the next pending build plan.
      Step 8 cleared it deliberately; leaving it null means the next session's Critic gate sees no
      active plan.

## If this doesn't work

- **A `develop` → `main` PR reports "merge conflict cannot be cleanly created":** expected, and it
  is why this procedure exists. The conflicts are bookkeeping artifacts of divergent history with
  identical content. Use the tree-set above. **Do not back-merge `main` into `develop`.**
- **`git diff --stat origin/develop HEAD` is not empty at step 14:** someone committed to `main`
  outside this procedure, or `develop` moved under you. Re-run step 12 against a freshly fetched
  `origin/develop`; if it is still non-empty, stop and investigate before pushing.
- **`prawduct-hook check-cumulative-critic` exits non-zero during release:** expected and benign.
  Release prep touches non-`.md` files, which the coverage gate reads as unreviewed code. Do not
  re-run the Critic over version bumps and do not write `.gates-waived`.
- **Escalate to:** this is a solo-maintained repo. "Escalate" means stop and resume tomorrow with
  a clear head. A half-promoted release is safe as long as you have not run step 15 — everything
  before it lives on `develop`.

## Maintenance

**Last executed or rehearsed:** never — this runbook has not been validated by execution.
**Validated by:** pending. It is not trustworthy until someone runs it end to end for a real
release and corrects what they stumble on.
