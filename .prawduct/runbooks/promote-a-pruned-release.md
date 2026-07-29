---
runbook: promote-a-pruned-release
tier: 3
owner: prawduct maintainer
last_verified: null
verified_by: null
---

# Promote a pruned release to `main`

## When to use this

You finished Phase 1 of `cut-and-publish-a-plugin-release.md` and some of what is on `develop` is
**withheld** from this release. This document replaces that runbook's Phase 2 (steps 14–20).
Everything before Phase 2 is unchanged and is not repeated here.

Confirm you are in that situation:

```
./plugin/bin/prawduct-hook check-releasability --release vX.Y.Z
```

**Expected:** `releasable: vX.Y.Z — N release-pending scope(s), M shipping, K withheld` where **K is
1 or more**, followed by the withheld list.

**Also valid:** `cannot-verify-blockers: …` after this repo has cut over to the GitHub Issues
backlog. The gate cannot judge blocker liveness from a frozen `backlog.md`, so it refuses rather than
guessing. You are still in the right document — confirm each withholding blocker is open **by hand**,
record that confirmation in the release plan beside the classification table, and proceed to step 1.

**Blocker liveness is the only check that refusal withholds.** Every other one still ran, so any
other `ERROR:` line printed beside it is a real problem and must be fixed first — an unclassified
scope in particular, which is the thing Phase 0 exists to catch.

## When NOT to use this

- **If `K withheld` is 0:** → `cut-and-publish-a-plugin-release.md` Phase 2.
- **If Phase 1 is not finished and pushed:** → `cut-and-publish-a-plugin-release.md`, from the top.

## Before you start

**Blast radius:** every repo with the plugin installed re-resolves `main` at its next session start
and picks this version up on its own. There is no recall — the only way back is another release.

**What is different here.** `main`'s tree is deliberately **not** `develop`'s, so the whole-develop
completion test (`git diff --stat origin/develop HEAD` prints nothing) can never pass and must not be
used. The binding test is the **partition**: every path in `origin/main..origin/develop` accounted
for as shipped or deliberately withheld, nothing unclassified (`operational-spec.md` § Direction,
amended 2026-07-29). Step 10 is that test.

**Prerequisites** — check every line before step 1:

- [ ] Phase 1 complete and pushed: on `develop`, `git status -sb` prints `## develop...origin/develop`
      and no file lines.
- [ ] Push access to `origin` for `main` and for tags.
- [ ] The previous release tag: `git describe --tags --abbrev=0 origin/main`.
- [ ] `.prawduct/artifacts/release-plan-vX.Y.Z.md` exists with its `## Release classification` table
      — Phase 0 required it. You will add the cut point, the collateral, and the conflict
      resolutions to it as you go. Worked example: `release-plan-v3.1.2-pruned.md`.
- [ ] **You accept the collateral.** The prune is by **commit range, not by feature**: everything
      that merged before the cut point waits for a later release, including work unrelated to the
      withheld scopes. Step 3 makes it visible. If you are not willing to hold it, stop — the
      alternative is to ship the withheld scope, which is Phase 0's decision to re-take.

---

## Steps

1. Find the cut point — the newest commit that delivered **withheld** work. Step 0 named the withheld
   scopes; the boundary between them and the ship set is normally a PR merge, since feature work
   arrives that way:

   ```
   git log --oneline --merges <prev-tag>..origin/develop
   ```

   **Expected:** one sha you can name, and the PR title beside it belongs to withheld work. Record it
   in the release plan. (Full history, if the boundary is not a merge:
   `git log --oneline <prev-tag>..origin/develop`.)

2. Confirm nothing withheld would ship — read the range **after** the cut point:

   ```
   git log --oneline <cut-point>..origin/develop
   ```

   **Expected:** every line is work you intend to ship.
   **If a withheld scope's commit appears here:** the two streams interleave and a range prune
   cannot separate them. Go back to Phase 0 and re-take the classification — either withhold the
   shipping scope too, or ship the withheld one. Do **not** try to split by file: on v3.1.2 the ship
   and withhold sets overlapped in 11 files.

3. Confirm nothing shipping would be withheld, and record the collateral — read the range **at and
   before** the cut point:

   ```
   git log --oneline <prev-tag>..<cut-point>
   ```

   **Expected:** every line is either a withheld scope's work or collateral you are willing to hold.
   Write the collateral into the release plan by name — it is what makes "what is a consumer
   missing?" answerable later.
   **If a shipping scope's commit appears here:** that scope would ship partially. Back to step 2's
   remedy.

4. Create the candidate worktree on the previous release's tree:

   ```
   git worktree add --detach ../prawduct-candidate <prev-tag>
   ```

   **Expected:** `Preparing worktree (detached HEAD <sha>)`, then `HEAD is now at <sha> release: …`.

5. Apply the ship set onto it:

   ```
   git diff <cut-point> origin/develop > /tmp/ship.patch
   git -C ../prawduct-candidate apply --3way /tmp/ship.patch
   ```

   **Expected:** `Applied patch to '<path>' cleanly.` lines, `Falling back to direct application…`
   lines, and — normally — some `U <path>` lines. Conflicts here are routine, not a fault.

   > ⚠️ **A clean apply is not evidence of a sound tree.** On v3.1.2 `git apply` reported
   > `plugin/lib/briefing.py` applied cleanly and the result raised `NameError: name 'sys' is not
   > defined` with 11 tests failing. The ship set used `sys.stderr`; `import sys` had been added by
   > the **withheld** work. Steps 7 and 8 exist for exactly that class, and neither is optional.

6. List the conflicted paths:

   ```
   git -C ../prawduct-candidate diff --name-only --diff-filter=U
   ```

   **Expected:** the `U` paths from step 5, one per line.

   - 6a. Resolve each path in that list: keep the ship set's additions, and take the **previous
     release's** side for anything the withheld work introduced. For this repo's own state files
     (`.prawduct/backlog.md`, `.prawduct/change-log.md`), resolve so the file describes the tree it
     ships with, not `develop`'s.
   - 6b. Write every resolved path and its resolution into the release plan. Step 10a reads that
     list — a resolution you did not record will read there as dropped work.

7. Find imports the prune removed from code that still uses them:

   ```
   git diff --name-only <cut-point> origin/develop -- '*.py' | while read -r f; do
     [ -f "../prawduct-candidate/$f" ] || continue
     m=$(comm -23 <(git show "origin/develop:$f" 2>/dev/null | grep -E '^ *(import|from) ' | sort -u) \
                  <(grep -E '^ *(import|from) ' "../prawduct-candidate/$f" | sort -u))
     [ -n "$m" ] && printf '%s\n%s\n' "$f" "$m"
   done
   ```

   **Expected:** zero or more file paths, each followed by the import lines `develop` has and the
   candidate lacks.

   - 7a. For each file listed, open the candidate's copy and find whether its own code uses the
     missing import.

     **If only the withheld code used it:** the prune was correct — nothing to do.
     **If the candidate's own code uses it:** add that import to the candidate by hand, and record it
     in the release plan. It is shipped code that exists in no reviewed commit, so it must be visible.

8. Run the suite on the candidate tree:

   ```
   (cd ../prawduct-candidate && python3 -m pytest -q)
   ```

   > *In a subshell on purpose: steps 9–14 all address the candidate as
   > `../prawduct-candidate`, and a bare `cd` here would silently repoint every one of them.*

   **Expected:** `NNNN passed`, and **fewer than `develop`'s count** — the withheld subsystem's own
   tests do not exist in this tree. On v3.1.2: 2131 passed, 1 skipped, against 2683 on `develop`.
   **If anything fails:** the tree is wrong, not the tests. Back to step 6.

9. Commit the candidate:

   ```
   git -C ../prawduct-candidate add -A
   git -C ../prawduct-candidate commit -m "release: vX.Y.Z — <headline>"
   ```

   **Expected:** `[detached HEAD <candidate-sha>] release: vX.Y.Z — <headline>`. Its parent is
   `<prev-tag>`, not `develop` — that single parent is the promotion.

10. List the shipping paths that still differ from `develop`:

    ```
    comm -12 <(git diff --name-only <cut-point> origin/develop | sort) \
             <(git diff --name-only <candidate-sha> origin/develop | sort)
    ```

    **Expected:** a list of paths, normally under 15. It is a shortlist to read, not a pass.

    - 10a. Read each path on that list:

      ```
      git diff <candidate-sha> origin/develop -- <path>
      ```

      **Expected:** every hunk is withheld code, or a resolution you recorded at step 6b.
      **If a hunk is neither:** it is shipping work the prune silently dropped → back to step 6a.

    > *This replaces the whole-develop test (`git diff --stat origin/develop HEAD` prints nothing).
    > Here the trees differ by design, so an empty diff would mean the withheld work shipped.*

11. Confirm the candidate carries the bump:

    ```
    git show <candidate-sha>:plugin/VERSION
    ```

    **Expected:** the new number — not the previous release's.
    **If not:** the bump never reached `develop`. Discard the candidate with
    `git worktree remove --force ../prawduct-candidate`, fix it at Phase 1 step 7, push, and start
    again from step 4.

> ⚠️ **IRREVERSIBLE — step 12 publishes to every installed consumer.**
> **Proceed only if:** step 8 passed, step 10's list held no unexplained hunk, and step 11 printed
> the new number.
> **Abort if:** any of those disagrees, or you are unsure → stop. Nothing on `origin` has moved yet,
> so aborting costs only the time to redo steps 4–11.
> **Recovery after this point:** none. Repos that have re-resolved `main` keep what they got.
> Recovery is forward-only: fix on `develop`, bump the version again, and run the release again.

12. Publish by ref:

    ```
    git push origin <candidate-sha>:refs/heads/main
    ```

    **Expected:** a line ending `-> main`.

    > *Why by ref rather than checking `main` out: `main` is checked out in a sibling worktree, where
    > `git checkout main` cannot run at all, and moving the ref under it would leave that worktree's
    > index inconsistent with its HEAD. Pushing by ref touches no other worktree.*

13. Tag the release and publish the tag:

    ```
    git tag vX.Y.Z <candidate-sha> && git push origin vX.Y.Z
    ```

    **Expected:** `* [new tag]  vX.Y.Z -> vX.Y.Z`.

    > *Chained on purpose: if the tag already exists, `git tag` fails and the push must not run.*

14. Remove the candidate worktree:

    ```
    git worktree remove ../prawduct-candidate
    ```

    **Expected:** no output. `git worktree list` no longer shows it.

---

## Done when

- `git show origin/main:plugin/VERSION` prints the new number.
- `git ls-remote --tags origin` shows a line ending `refs/tags/vX.Y.Z`.
- `git diff --stat origin/main origin/develop` is **non-empty**, and what it lists is the withheld
  work plus step 3's collateral, nothing else. *Unlike a whole-develop promotion, an empty diff here
  means the withheld work shipped.*

## If this doesn't work

- **If a step doesn't match what you're seeing:** stop where you are. Everything before step 12 is
  undoable — `git worktree remove --force ../prawduct-candidate` and nothing on `origin` has moved.
  A step that doesn't make sense is a defect in this document, not in you.
- **Escalate to:** this repo has one maintainer, so escalating means stopping — leave `develop` as it
  is and come back to it. An unfinished release is invisible to consumers.
- **Act immediately if:** you pushed `main` and then found something wrong. Consumers pick `main` up
  at their next session start, so the fix is a new release with a higher version — a revert without a
  version bump does not ship.
