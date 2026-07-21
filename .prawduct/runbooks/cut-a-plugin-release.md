---
runbook: cut-and-publish-a-plugin-release
tier: 3
owner: prawduct maintainer
last_verified: null
verified_by: null
---

# Cut and publish a Prawduct plugin release (`develop` → `main`)

## When to use this

`develop` holds everything you mean to ship, and you're publishing it as
`vX.Y.Z` — for example, `v3.2.0`, which the three version files carry without
the `v`, as `3.2.0`. Confirm before you start:

```
git fetch origin && git log --oneline origin/main..origin/develop
```

**Expected:** the commits you mean to release, and nothing you don't.

The reasoning behind every step below is `docs/release-process.md`. You don't
need it to execute this.

## When NOT to use this

- **If you're merging a feature branch into `develop`:** → use `/prawduct:pr`.

## Before you start

**Blast radius:** every repo with the plugin installed and auto-update on picks
this up at its next session start. No staged rollout, and no recall.

**Prerequisites** — check every line before step 1:

- [ ] Everything you mean to ship is merged into `develop` — nothing you
      intended to include is still sitting in an open PR.
- [ ] The version number is decided. Versioning here is conservative: a small
      feature is a **patch** bump, not a minor (`operational-spec.md`). A
      departure from that is a decision you record, not a reflex.
- [ ] `git ls-remote --tags origin` does not already list `refs/tags/vX.Y.Z`.
      Re-shipping a version consumers already resolved is a silent no-op — the
      cache key never changed.
- [ ] Your working tree is clean — `git status` shows nothing to commit. Step
      15 overwrites the worktree.

---

## Phase 1 — Release-prep on `develop`

This order follows `docs/release-process.md`'s "Step 1 mechanics" — prep on
`develop` first, then promote — not the numbering of the checklist above it.

1. Get onto `develop`, current:

   ```
   git checkout develop && git pull
   ```

   **Expected** — any of:
   - `Already up to date.`
   - a fast-forward summary

2. List the change-log entries this release ships:

   ```
   grep -n "<!-- prawduct:" .prawduct/change-log.md | head -30
   ```

   **Expected:** one `<!-- prawduct: … -->` line per entry, newest first, the
   older ones carrying `release=`.
   **If not:** no `release=` anywhere in those 30 → raise the `head` count until
   one appears.

3. In `.prawduct/change-log.md`, take the topmost line from step 2 that carries
   `release=` — that's the previous release's boundary — and append
   ` | release=vX.Y.Z | status=shipped` to every tag line **above** it. All of
   them, statusless and legacy `status=merged` alike. Leave the existing
   `type=` / `scope=` / `chunks=` tags in place.

   *Why: a skipped entry silently never flips its checkboxes and never reaches
   the release notes. Enumerate them; don't sample.*

   Before:

   ```
   <!-- prawduct: type=feature | scope=skills-cutover-awareness | chunks=04 -->
   ```

   After:

   ```
   <!-- prawduct: type=feature | scope=skills-cutover-awareness | chunks=04 | release=v3.2.0 | status=shipped -->
   ```

4. Set the version to `X.Y.Z` — the release number without the leading `v` — in
   all three files:

   - `VERSION` — the whole file is the number
   - `.claude-plugin/plugin.json` — the `"version"` field
   - `pyproject.toml` — the `version` field; it lags behind the other two, and
     its own comment asks to be kept in step even though the release checklist
     names only the first two files

   *Why: `version` is the auto-update cache key — a release that forgets it does
   not ship.*

5. Confirm all three moved:

   ```
   grep -rn "X\.Y\.Z" VERSION .claude-plugin/plugin.json pyproject.toml
   ```

   Substitute your number — for `v3.2.0`, that's `"3\.2\.0"`.

   **Expected:** three lines, one per file.
   **If not:** the missing file is still on its old number → back to step 4.

6. At the top of the version list in `CHANGELOG.md`, add a `## vX.Y.Z` heading
   above the previous one, then a blank line, then a one-paragraph headline.

   *Why: the version-delta banner reads the first non-empty, non-heading line
   under that heading — that paragraph is what consumers see on upgrade.*

7. **If this release adds an enforcing gate:** append it to `hooks/gates.json`
   with `"since": "X.Y.Z"` — the version you're shipping.
   **If it doesn't:** → step 8.

8. Validate the tags before anything is written:

   ```
   python3 bin/prawduct-hook regen-views --check
   ```

   **Expected** — all of:
   - one `[check] …` line per view
   - a final `check passed: tags validate against the plan roster; nothing
     written.`

   **If not:**

   `ERROR: …` lines, then `N validation error(s) — no views written.`
   - fix the tag it names in `.prawduct/change-log.md`, then re-run this step

   `error: regen-views could not import the plugin lib/`
   - you're not at the repo root → change directory and re-run this step

   - Anything else → stop; see *If this doesn't work*.

9. Regenerate the derived views for real:

   ```
   python3 bin/prawduct-hook regen-views
   ```

   **Expected** — all of:
   - a `Release notes: write release-notes.md` line
   - for each scope you tagged, a
     `Status (artifacts/<plan>.md): N chunk(s) flipped — shipped [01, 02, …]`
     line whose N equals the number of chunks you tagged in step 3

   **If not:** fewer flipped than tagged → your `chunks=` numbering doesn't
   match that plan's `## Status` headings (`chunks=1` does not match
   `Chunk 01`). Align the tag to the headings; don't renumber the plan.

10. In `.prawduct/project-state.yaml`, set `active_build_plan:` to `null`.

    *Why: do this after step 9 — an unscoped plan resolves only through this
    pointer, so clearing it first makes the regen fail.*

11. Run the two release-hygiene test files:

    ```
    python3 -m pytest tests/test_plugin_manifest.py tests/test_plugin_version_banner.py -q
    ```

    **Expected:** the last line reads `N passed`, with no `failed`.
    **If not:** the assertion message names what's missing — a `VERSION` /
    `plugin.json` mismatch sends you to step 4, an absent changelog headline to
    step 6.

12. Commit the prep:

    ```
    git commit -am "chore(release): vX.Y.Z release-prep — version bump, change-log status flips, regen views"
    ```

    **Expected:** `[develop <sha>] chore(release): vX.Y.Z release-prep …`

13. Push it:

    ```
    git push origin develop
    ```

    **Expected:** a line ending `develop -> develop`.

    *Why: step 15 reads `origin/develop`, not your local branch. Skip this and
    you promote the un-prepped tree.*

### Checkpoint — before Phase 2

`origin/develop` now carries the release-prep commit, and **nothing is
published yet**. Everything so far is undone with a `git revert` on `develop`.
Stopping here is safe; pick it up later from step 14.

---

## Phase 2 — Promote to `main`

14. Get onto `main`, current:

    ```
    git checkout main && git pull
    ```

    **Expected** — any of:
    - `Already up to date.`
    - a fast-forward summary

> ⚠️ **Step 15 overwrites your working tree from `origin/develop`.** Any
> uncommitted work sitting on `main` is gone, in place.

15. Set `main`'s index and worktree to `develop`'s tree:

    ```
    git read-tree --reset -u origin/develop
    ```

    **Expected:** no output.

16. Commit it on `main` as a single-parent release commit, reusing the headline
    you wrote in step 6:

    ```
    git commit -m "release: vX.Y.Z — <headline>"
    ```

    **Expected:** `[main <sha>] release: vX.Y.Z — …`

17. Confirm `main` and `develop` are content-identical:

    ```
    git diff --stat origin/develop HEAD
    ```

    **Expected:** no output.
    **If not:** any file listed → do **not** push. Go to step 15.

> ⚠️ **IRREVERSIBLE — step 18 publishes to every installed consumer.**
> **Proceed only if:** step 17 printed nothing.
> **Abort if:** step 17 printed any file → go to step 15. Aborting costs
> nothing; nothing is published until the push.
> **Recovery after this point:** forward only — fix on `develop` and cut a
> higher patch release. An installed copy cannot be recalled.

18. Publish:

    ```
    git push origin main
    ```

    **Expected:** a line ending `main -> main`.

19. Tag the release:

    ```
    git tag vX.Y.Z && git push origin vX.Y.Z
    ```

    **Expected:** a line ending `vX.Y.Z -> vX.Y.Z`.

20. **Next session:** open a repo governed by the installed plugin and start
    Claude Code.

    **Expected:** the banner's delta line — the previous version, an arrow, then
    `vX.Y.Z` — followed by your step 6 headline.
    **If not:** still showing the old version → auto-update stages on one start
    and applies on the next, so start a second session, or run
    `claude plugin update`.

---

## Done when

- `git log --oneline -1 origin/main` shows `release: vX.Y.Z — <headline>`
- `git diff --stat origin/develop origin/main` prints nothing
- `git ls-remote --tags origin` includes a line ending `refs/tags/vX.Y.Z`

## If this doesn't work

- **If `check-cumulative-critic` fails during release-prep:** expected and
  benign — release-prep necessarily touches non-`.md` files. Do nothing. Don't
  re-run the Critic over version bumps, and don't write `.gates-waived`.
- **If a release you already pushed is broken:** fix it on `develop` and cut a
  higher patch release. Don't try to un-publish.

  > 🚧 **UNVERIFIED** — whether *lowering* `version` on `main` pulls consumers
  > back · the 2026-06-02 spike confirmed only that bumps ship. Ship forward.

- **If a step doesn't make sense, stop.** Nothing is published until step 18,
  so anything before that keeps overnight. That's a defect in this document,
  not in you.
- **Escalate to:** nobody — this repo has one maintainer. "Escalate" here means
  stop and look at it tomorrow.
