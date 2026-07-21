---
runbook: cut-and-publish-a-plugin-release
tier: 3
owner: prawduct maintainer
last_verified: null
verified_by: null
---

# Cut and publish a Prawduct plugin release

## When to use this

You're ready to publish what's on `develop` to everyone running the plugin.
Confirm you're actually in that situation before step 1:

```
git fetch origin
```

```
git diff --stat origin/main origin/develop
```

**Expected:** at least one changed file — that's the unreleased content.
**If not:** it prints nothing, so `main` and `develop` are already
content-identical. The last release is out and there's nothing to cut. Stop.

## When NOT to use this

- **If you're merging a feature branch into `develop`:** → use `/prawduct:pr`.
- **If you're about to open a `develop` → `main` PR:** → don't. Phase 2 below
  replaces it. Close any such PR with a note that you promoted directly.

## Before you start

**Blast radius:** every repo with the plugin installed re-resolves `main` at its
next session start and picks this version up on its own. There is no recall —
the only way back is another release.

**Prerequisites** — check every line before step 1:

- [ ] Push access to `origin` for both `develop` and `main`. The promotion
      commits straight to `main`; no PR is involved.
- [ ] You're on `develop` with nothing uncommitted and nothing unpushed:
      `git status -sb` prints `## develop...origin/develop` and no file lines.
- [ ] The new version number, decided. The tag is `vX.Y.Z` (for example,
      `v3.2.0`); the version files carry it without the `v` (`3.2.0`).

      **The rule is a ratified norm** — `.prawduct/artifacts/operational-spec.md`
      `## Direction` (2026-07-17), pointer row in `project-preferences.md`:
      *versioning is conservative — a small feature is a patch bump, not a
      minor-per-feature.* A break in gate semantics or state formats is a major
      bump. Everything else, including a small new capability, is a patch.

      It is a **judgment norm**: there is no mechanical size test, so "small" is
      your call. A departure in either direction — a minor bump for a small
      change, or a patch for a large one — is a recorded decision, not a reflex.
      Record it in the release plan or the change-log entry.

---

## Phase 1 — Release prep on `develop`

1. List the tagged change-log entries, newest first:

   ```
   grep -n "<!-- prawduct:" .prawduct/change-log.md | head -20
   ```

   **Expected:** numbered tag lines, newest first, at least one carrying
   `release=v...`.

2. Find the boundary — the topmost line whose tag carries `release=`. That's
   the previous release.

   **Expected:** one line number and a version, like
   `745:<!-- prawduct: type=fix | release=v3.1.0 | status=shipped -->`.

   > ⚠️ **The boundary narrows the search. It does NOT define the set — do not
   > flip "everything above it" (REL-7D4X).** An entry lands where it merged,
   > not above the last release, so a genuinely unreleased entry can sit
   > *below* the boundary and a positional sweep drops it silently. This
   > happened at v3.1.1: `2026-07-14: Stale remote-base diagnostics` sits below
   > and had to be flipped.
   >
   > **The sound test is per candidate:** an entry is release-pending iff it
   > carries no `release=` tag **and** its code is absent from the previous
   > release's tree (`git show <prev-tag>:<path>`). Walk every untagged entry
   > and apply it. Entries predating the tag convention (roughly pre-2026-06)
   > are untagged but shipped — the code test is what separates them.

3. Append ` | release=vX.Y.Z | status=shipped` to every tag line that passed the
   step-2 test, keeping the keys already there and the ` | ` separator:

   ```diff
   - <!-- prawduct: type=feature | scope=skills-cutover-awareness | chunks=04 -->
   + <!-- prawduct: type=feature | scope=skills-cutover-awareness | chunks=04 | release=v3.2.0 | status=shipped -->
   ```

   > *Why: a tag line left statusless ships nothing — no checkbox flip, no
   > release-notes entry — and nothing downstream complains.*

4. Re-run the enumeration and read down to the boundary:

   ```
   grep -n "<!-- prawduct:" .prawduct/change-log.md | head -20
   ```

   **Expected:** every line above the step 2 boundary now carries
   `| release=vX.Y.Z | status=shipped`.

5. Pre-flight the tags. This writes nothing:

   ```
   prawduct-hook regen-views --check
   ```

   **Expected:** `check passed: tags validate against the plan roster; nothing
   written.`
   **If not:** it ends with `N validation error(s) — no views written.` and one
   `ERROR:` line per bad tag → fix those tags in `.prawduct/change-log.md` and
   re-run this step.

6. Regenerate the derived views:

   ```
   prawduct-hook regen-views
   ```

   **Expected — all of:**
   - one `Status (artifacts/<plan>.md): N chunk(s) flipped — shipped [...]`
     line per release-pending plan
   - `Release notes: write release-notes.md`
   - a `Scope rollups: ...` line

   **If not:** a `Status (...): up to date` line where you expected a flip means
   that plan's `chunks=` tags matched nothing → back to step 3.

   > *Why: the build-plan checkboxes, release notes and scope rollups are all
   > derived here — hand-edit them and the next regen reverts you.*

7. In `VERSION`, replace `3.1.0` with the new number without the `v` — `3.2.0`
   for a `v3.2.0` release.

8. In `.claude-plugin/plugin.json`, replace `"version": "3.1.0"` with the same
   number.

   > *Why: that string is the update cache key. A release that forgets it does
   > not ship, however clean the push.*

9. In `pyproject.toml`, replace `version = "3.0.3"` with the same number.

   > *Adjudicated, not derived: the file's own comment asks for this bump;
   > `docs/release-process.md` step 2 doesn't name it.*

10. In `CHANGELOG.md`, add a `## vX.Y.Z` section directly above `## v3.1.0`,
    with the consumer-facing headline as the first non-empty line under it.

    > *Why: the version-delta banner shows exactly that first line to every repo
    > crossing this version.*

11. In `.prawduct/project-state.yaml`, set `active_build_plan:` to `null`.

12. Commit the prep:

    ```
    git commit -am "release: prep vX.Y.Z"
    ```

    **Expected:** `[develop <sha>] release: prep v3.2.0`.

13. Push it:

    ```
    git push origin develop
    ```

    **Expected:** a line ending `develop -> develop`.

    > *Why: Phase 2 builds `main` from `origin/develop`. Anything still local
    > won't be in the release.*

### Checkpoint

`origin/develop` now holds the whole release: bumped version, shipped
change-log tags, regenerated views, cleared plan pointer. Nothing is published
yet. Everything up to here is undone by an ordinary commit on `develop`, so
this is a safe place to stop and come back.

---

## Phase 2 — Promote `develop` to `main`

14. Switch to the release surface and bring it up to date:

    ```
    git checkout main && git pull
    ```

    **Expected — both:**
    - `Switched to branch 'main'` (or `Already on 'main'`)
    - then `Already up to date.`, or a fast-forward summary

    > *Chained on purpose: if the checkout fails, the pull must not run.*

> ⚠️ **`git read-tree --reset -u` overwrites `main`'s index and working tree in
> place.** Anything uncommitted on `main` is gone.

15. Set `main`'s tree to `develop`'s:

    ```
    git read-tree --reset -u origin/develop
    ```

    **Expected:** no output.

16. Commit it on `main`, using the headline you wrote at step 10:

    ```
    git commit -m "release: vX.Y.Z — <headline>"
    ```

    **Expected:** `[main <sha>] release: v3.2.0 — <headline>`.

17. Confirm `main` is content-identical to `develop`:

    ```
    git diff --stat origin/develop HEAD
    ```

    **Expected:** no output.
    **If not:** any output at all means the tree-set didn't take → go to step 15.

18. Confirm the commit actually carries the bump:

    ```
    git show HEAD:VERSION
    ```

    **Expected:** the new number, `3.2.0` — not `3.1.0`.
    **If not:** the bump never reached `develop`. Discard this commit with
    `git reset --hard origin/main`, fix it at step 7, then come back to step 14.

> ⚠️ **IRREVERSIBLE — step 19 publishes to every installed consumer.**
> **Proceed only if:** step 17 printed nothing and step 18 printed the new
> number.
> **Abort if:** either one disagrees, or you aren't sure → stop. Nothing on
> `origin/main` has moved yet; aborting costs only the time to redo Phase 2.
> **Recovery after this point:** none — repos that have already re-resolved
> `main` keep what they got. Recovery is forward-only: fix on `develop`, bump
> the version again, and run this runbook again.

19. Publish:

    ```
    git push origin main
    ```

    **Expected:** a line ending `main -> main`.

20. Tag the release and publish the tag:

    ```
    git tag vX.Y.Z && git push origin vX.Y.Z
    ```

    **Expected:** `* [new tag]  v3.2.0 -> v3.2.0`.

    > *Chained on purpose: if the tag already exists, `git tag` fails and the
    > push must not run.*

---

## Done when

- After `git fetch origin`, `git diff --stat origin/main origin/develop` prints
  nothing.
- `git ls-remote --tags origin` shows a line ending `refs/tags/vX.Y.Z`.

## If this doesn't work

- **If a step doesn't match what you're seeing:** stop where you are.
  Everything before step 19 is undoable, so stopping costs nothing but time,
  and a step that doesn't make sense is a defect in this document, not in you.
- **Escalate to:** this repo has one maintainer, so escalating means stopping —
  leave `develop` as it is and come back to it. An unfinished release is
  invisible to consumers.
- **Act immediately if:** you pushed `main` and then found something wrong.
  Consumers pick `main` up at their next session start, so the fix is a new
  release with a higher version — a revert without a version bump does not
  ship.
