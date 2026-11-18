---
schema: 1
type: fix
scope: git-tidy-submodule-worktrees
date: 2026-11-18
title: git-tidy removes a merged worktree that holds submodules, once their commits are published
closes: [brookstalley/prawduct#1187]
---
Git refuses to remove any worktree that holds submodules unless forced, so `git-tidy --reap`, and
`--apply` for an idle sibling, failed on a delegate that had added one. Forcing it is not safe in
general: a submodule's repository lives under the worktree's own git directory, so a forced removal
deletes any submodule commit that no remote has, even though the superproject's merge still points
at it. git-tidy now removes such a worktree with `--force` only after a further proof: each
submodule is clean, read with `--ignore-submodules=none` so that a `submodule.*.ignore` setting
cannot hide changes, and nothing any of its refs reaches (branches, tags, its stash, HEAD) is
missing from its remote-tracking branches. Absorbed, embedded and deinitialised submodules are all
checked. If the proof fails, the worktree is kept, and the reason names the submodule and, for work
already published under a tag, the command to remove the worktree by hand. A worktree without submodules
is never forced. This departs from #1041's rule that worktrees are never forced; the departure is
recorded in its requirements, awaiting the owner's confirmation.

## Consumer note
`prawduct-hook git-tidy --reap <worktree>` now removes a merged, clean delegate worktree that
contains submodules, instead of failing with git's "working trees containing submodules cannot be
moved or removed". When a submodule holds commits none of its remote-tracking branches reach, it
keeps the worktree and says to push or drop them, or, if they are already published (a release tag),
to remove the worktree by hand with the command it prints.
