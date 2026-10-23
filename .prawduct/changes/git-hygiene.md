---
schema: 1
type: feature
scope: git-hygiene
date: 2026-10-22
title: Merged branches and dead worktrees are cleaned up, on proof that nothing is lost
closes: [brookstalley/prawduct#1041]
---
Prawduct used to notice merged branches, stranded work and idle worktrees and clean up none of
it. The merge flow's one line of cleanup failed in a linked worktree. Now prawduct removes a
branch or worktree only when what it holds is provably carried by a long-lived branch (`main`,
`develop`, `release/*`, the remote's default branch, the configured base, and any names in a new
`Long-lived branches` preference row). For a squash or rebase merge, the proof is instead a merged
pull request whose head was this exact commit. Age and inactivity are never proof.

`prawduct-hook git-tidy` is a dry run of every such removal. Each line shows the commit, its proof
and the exact command, and the run ends with a fingerprint. `git-tidy --apply <fingerprint>`
removes exactly that set. It re-checks each proof first, deletes local branches by
compare-and-delete, and changes nothing if the set has changed. It keeps any remote branch an open
pull request uses, a dirty or locked worktree, and a detached checkout, such as the install a
plugin runs from. It never uses `-D` or `--force`.

At session start, one `tidy-available` advisory proposes the dry run, offline, and the agent
applies it on the owner's yes. `/prawduct:pr` merge now ends with
`git-tidy --after-merge <branch>`. It retargets stacked pull requests, deletes both copies of the
branch, and moves a linked worktree onto the updated base. It keeps the local branch when that
branch holds commits the merge did not take. Delegate reaping uses `git-tidy --reap <worktree>`. A
product that wants none of this sets `Branch cleanup: off`. Under a squash or rebase strategy, the
merge flow still deletes the merged branch, because those branches are single-use.

## Consumer note
- A repo with merged branches or dead worktrees sees one new advisory at session start,
  `tidy-available`. It changes nothing until the owner approves the dry run. Dismissing it holds
  until the set of removals changes. To turn it off, set `Branch cleanup: off` in
  `project-preferences.md`.
- `/prawduct:pr` merge now deletes the merged branch and its remote copy itself, and it works
  from a linked worktree. A local branch holding commits the merge did not take is kept and named.
- An environment branch kept level with `main`, such as `staging`, reads as merged. List it in a
  `Long-lived branches` row, and the dry run's note says so when it sees one.
- The online dry run fetches with `--prune` and calls `gh pr list` against the product's own
  repo. Without `gh`, remote deletions are listed as unchecked and not performed.
