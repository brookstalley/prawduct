---
runbook: cut-and-publish-a-plugin-release
tier: 3
owner: prawduct maintainer
last_verified: null
verified_by: null
---

# Cut and publish a new Prawduct plugin release (`develop` → `main`)

## When to use this

You want to publish the work sitting on `develop` as a new plugin version. Check that there is
something to publish:

```
git fetch && git diff --stat origin/main origin/develop
```

**Expected:** a list of changed files.
**If not:** nothing printed means `main` already carries develop's content — there is no release to
cut. Stop.

## When NOT to use this

- **If you are merging a feature branch into `develop`:** → use `/prawduct:pr` instead.

## Before you start

**Blast radius:** this publishes. Every repo with the plugin installed pins `ref: "main"` and
re-resolves it at session start, so the new version reaches all of them on their next restart.
Nothing you do before step 18 is visible to any consumer.

**Prerequisites** — check every line before step 1:

- [ ] Push access to `github.com/brookstalley/prawduct` — you push `develop`, `main`, and a tag
- [ ] A clean working tree: `git status --short` prints nothing
- [ ] The new version decided, written here as `vX.Y.Z` (for example, `v3.2.0`). Patch for a
      fix-only release; minor for new capability; major for a break in the stable CLI or state
      surface, or the removal of a deprecated subcommand (`.prawduct/artifacts/api-contract.md`,
      "Deprecation & Compatibility").
  > 🚧 **UNVERIFIED** — this repo has no written minor-vs-patch policy; that split is read off
  > `CHANGELOG.md` precedent · confirm with the owner before choosing.

---

## Phase 1 — Prepare the release on `develop`

1. Switch to `develop` and bring it up to date:

   ```
   git checkout develop && git pull
   ```

   **Expected — all of:**
   - `Switched to branch 'develop'`, or `Already on 'develop'`
   - `Already up to date.`, or a summary of the files that came down

2. List the change-log's tagged entries:

   ```
   grep -n '<!-- prawduct:' .prawduct/change-log.md
   ```

   **Expected:** numbered `<!-- prawduct: … -->` lines. The topmost one carrying `release=` is the
   previous release.

3. In `.prawduct/change-log.md`, add `| release=vX.Y.Z | status=shipped` to every tag line step 2
   listed *above* that boundary line. Each one, including any already carrying `status=merged`:

   ```
   before:  <!-- prawduct: type=feature | scope=skills-cutover-awareness | chunks=04 -->
   after:   <!-- prawduct: type=feature | scope=skills-cutover-awareness | chunks=04 | release=v3.2.0 | status=shipped -->
   ```

   > *Why: separate the fields with `|`. Spaces parse as nothing, and the entry silently drops out
   > of the release with its chunks unflipped.*

3a. List them again:

   ```
   grep -n '<!-- prawduct:' .prawduct/change-log.md
   ```

   **Expected:** every line above the previous release's boundary now carries
   `| release=vX.Y.Z | status=shipped`.
   **If not:** any bare line you skipped ships nothing and flips no checkbox → go back to step 3.

4. In `VERSION`, put the new version with no `v` prefix. The whole file is that one line —
   `3.1.0` today, `3.2.0` after.

5. In `.claude-plugin/plugin.json`, set `version` to the same bare string (`3.2.0`).

   > *Why: `version` is the update cache key. A release that leaves it unchanged does not ship —
   > consumers keep the cached copy.*

6. In `pyproject.toml`, set `version` to that same string. It reads `3.0.3` today — it has drifted,
   and nothing ships from it.

7. Confirm the two shipping version strings agree:

   ```
   python3 -m pytest tests/test_plugin_manifest.py -q
   ```

   **Expected:** a summary line ending `passed`, with no `failed` in it.
   **If not:** `test_version_mirrors_VERSION_file` failing means `VERSION` and `plugin.json`
   disagree → redo steps 4 and 5.

8. In `CHANGELOG.md`, add a `## vX.Y.Z` heading above the topmost `## v` heading, and one paragraph
   under it saying what shipped.

   > *Why: the SessionStart banner shows that first paragraph to every consumer who crosses this
   > version, so it is the release note they actually read.*

9. Pre-flight the derived views — this validates and writes nothing:

   ```
   python3 bin/prawduct-hook regen-views --check
   ```

   **Expected:** `check passed: tags validate against the plan roster; nothing written.`
   **If not:** `ERROR:` lines naming the offending tag → fix those tags and re-run step 9.

   > *Why repo-local: the bare `prawduct-hook` on PATH is the installed plugin cache, not this
   > working tree, so it would validate with the released `lib/views.py`. `docs/release-process.md`
   > writes it bare; this overrides that.*

10. Regenerate them for real:

    ```
    python3 bin/prawduct-hook regen-views
    ```

    **Expected:** one line per view, including a `Status (…): N chunk(s) flipped — shipped [...]`
    line naming the chunks you tagged in step 3.
    **If not:** `Status (…): up to date` when you expected a flip means step 3 missed that entry →
    go back to step 3. Do not hand-edit the checkboxes; the next regen reverts them.

11. In `.prawduct/project-state.yaml`, clear the value after `active_build_plan:`, leaving the key
    with nothing after the colon.

12. Commit the release prep:

    ```
    git commit -a -m "release-prep(vX.Y.Z): <one-line summary>"
    ```

    **Expected:** a `[develop <sha>] release-prep(vX.Y.Z): …` line, then `N files changed`.

13. Push it:

    ```
    git push origin develop
    ```

    **Expected:** a line ending `develop -> develop`.

    > *Why: step 15 reads `origin/develop`, not your local branch.*

### Checkpoint

`develop` now carries the entire release and `main` is untouched. If you stop here, you resume at
step 14 — or amend and re-push `develop` at no cost.

---

## Phase 2 — Promote to `main` and publish

14. Switch to `main` and bring it up to date:

    ```
    git checkout main && git pull
    ```

    **Expected — all of:**
    - `Switched to branch 'main'`
    - `Already up to date.`, or a summary of the files that came down

> ⚠️ **Step 15 overwrites your working tree and index on `main` in place** with `develop`'s
> content. Anything uncommitted there is gone.

15. Set `main`'s tree to `develop`'s:

    ```
    git read-tree --reset -u origin/develop
    ```

    **Expected:** no output.

16. Commit the promotion:

    ```
    git commit -m "release: vX.Y.Z — <one-line summary>"
    ```

    **Expected:** a `[main <sha>] release: vX.Y.Z …` line, then `N files changed`.

17. Confirm `main` and `develop` are content-identical:

    ```
    git diff --stat origin/develop HEAD
    ```

    **Expected:** no output at all.

> ⚠️ **IRREVERSIBLE — step 18 publishes to every consumer.**
> **Proceed only if:** step 17 printed nothing.
> **Abort if:** step 17 printed any file → stop, and see "If this doesn't work".
> **Cost of aborting:** nothing. The remote `main` is still the previous release; your local commit
> can be discarded and remade.
> **Recovery after this point:** forward only. Consumers cache by `version`, so a bad release is
> corrected by cutting the next one — not by reverting or force-pushing `main`.

18. Publish:

    ```
    git push origin main
    ```

    **Expected:** a line ending `main -> main`.

19. Tag the release:

    ```
    git tag vX.Y.Z && git push origin vX.Y.Z
    ```

    **Expected:** `* [new tag]` followed by `vX.Y.Z -> vX.Y.Z`.

## Done when

- `git diff --stat origin/develop origin/main` prints nothing
- `git tag --points-at HEAD` prints `vX.Y.Z`
- `python3 bin/prawduct-hook version` prints the new version, bare (`3.2.0`)

## If this doesn't work

- **If step 17 lists files:** the tree-set did not reproduce `develop`'s content and this procedure
  has stopped applying. Do not push. Re-read `docs/release-process.md`, "Step 1 mechanics".
- **If a cumulative-Critic gate fires during phase 1:** expected and benign — release prep touches
  non-`.md` files. Do not re-run the Critic and do not write `.gates-waived`
  (`docs/release-process.md`, "`/prawduct:pr` is not the release vehicle").
- **If a step doesn't make sense:** stop. That is a defect in this document, not in you.
- **Escalate:** nobody is on call for this — it is a solo project. Stop and pick it up tomorrow.
  Before step 18 that costs nothing.
