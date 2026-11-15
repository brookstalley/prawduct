---
schema: 1
type: fix
scope: review-never-moves-head
date: 2026-11-15
title: the paired native review runs in its own worktree, so it can no longer detach your branch during a Critic review
closes: [brookstalley/prawduct#1177]
---
During a Critic review on a development build, the session's checkout could go from its feature
branch to a detached HEAD at that branch's own tip. Commits made after that landed on no branch,
and a push sent the old branch. The cause was the paired native review. The host's
`/code-review` checks out the commit it is reviewing, and it ran in the session's own checkout.

The native review's wrapper is now dispatched with `isolation: "worktree"`. Its first step,
`native-review prepare`, refuses to go on if it is standing in the session's checkout, or in any
tree but a clean, disposable one of the same repository. Otherwise it detaches the wrapper's own
worktree at the reviewed head, so the review reads the reviewed code there and has nothing to
check out. A run that read its own tree records `tree_moved: false`, because nothing could change
under it.

The wrapper writes the review's text inside its own worktree, at the path `prepare` prints. The
host refuses an isolated agent's Write to the session's files, and the first live run lost its
text that way. `native-review record` runs from the session's checkout. It copies the text into
the session's `.prawduct/.native-reviews/` and deletes the copy in the review's worktree, then
puts that worktree back on the commit it was made at. The host removes an agent's worktree only
when it is unchanged as the agent ends. `--text-file <absolute path>` records a text saved
anywhere else. If the review's worktree is still on disk after its text has landed, the review's
`NEXT-ACTION` names it. When the worktree is unchanged, it also gives a removal command that
checks again before it acts, so it never removes a worktree or branch that gained work since.

A detection guard backs this up for any cause. If HEAD has been detached from the branch a review
began on, three places say so and give the recovery command. They are the review's `NEXT-ACTION`
(within an hour of the dispatch), `critic-consolidate`'s output and `native-review record`'s
output. The command is `git branch -f <branch> HEAD && git switch <branch>` when commits landed
on the detached HEAD.

## Consumer note
none: the native review pairs only on development builds; a released plugin never runs it
