---
schema: 1
type: feature
scope: pushed-branch-never-prd
date: 2026-11-18
title: a finished, pushed branch that never merged is named at session start
closes: [brookstalley/prawduct#843]
---
A new `branch-landing:finished-branch-unlanded` advisory names a branch when every build plan
claiming it is finished, its tip is pushed, it has not merged into its base, and its last commit is
a day old or more. A branch another worktree has checked out is left alone; the one checked out here
is not exempt. The advisory is offline, like every probe, so it cannot ask whether a pull request
was ever opened. It recommends `prawduct-hook worktrees --prs`, which asks `gh pr list --state all`
once per such branch, oldest first, at most eight a run, and names any left unchecked. A failed
lookup reads "could not ask", never "no pull request". It is `info`, dismissible, and resolves when
the branch merges or is deleted. A finished branch whose pull request is open and waiting fires
until it merges; dismiss it with that reason.

The lookup is `git_hygiene.any_pr_for`, on the same `gh` seam as `git-tidy`, so there is no new
egress site. `project-state.yaml`'s `egress_boundary` names the new caller. The Stop hook's own
`gh pr list`, which #843's design planned to share, was already gone (removed with the PR reviewer),
so there was nothing to extract. The local arm, `stranded-branch`, is unchanged.

## Consumer note
A new advisory may appear for a finished branch that was pushed but never merged. Run
`prawduct-hook worktrees --prs` to see whether it ever had a pull request. Then land it, or dismiss
the advisory with the reason.
