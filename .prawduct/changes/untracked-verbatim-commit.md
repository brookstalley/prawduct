---
schema: 1
type: fix
scope: untracked-verbatim-commit
date: 2026-10-24
title: a review of the working tree names the untracked files a verbatim commit must include
closes: [brookstalley/prawduct#1003]
---
A review anchored on the working tree vouches for the tree `git add -A` would build, so it includes
untracked, non-ignored files. A clean `verify-resolutions` close then said "commit this tree verbatim".
A builder who committed only the tracked files recorded a tree without the stray file. The interval
from the reviewed tree to that commit deletes a judgeable path, which no edge covers, so
`check-cumulative-critic` read `uncovered` and charged another round (#1003).

`evidence.capture_tree` now returns `untracked`, the one listing every consumer reads. `critic-begin`,
in any mode whose anchor is the working tree, names the judgeable untracked files before a reviewer
runs. It says that a verbatim commit must include them (`git add -A`), and that a file which should
not ship has to be excluded now, through `.git/info/exclude` or by deleting it, followed by
`critic-end` and a fresh `critic-begin`. The close's "commit this tree verbatim" names the same files.
The capture itself is unchanged: an un-added new source file is still reviewed.

## Consumer note
- `critic-begin` can print a `PRAWDUCT NOTE` naming untracked files in the reviewed tree. If they
  belong in the commit, commit with `git add -A`. If not, exclude them and re-dispatch before the
  review runs.
