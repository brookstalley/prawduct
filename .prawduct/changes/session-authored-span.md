---
schema: 1
type: fix
scope: session-authored-span
date: 2026-10-27
title: a pull, merge or branch switch is not session work for the Stop gates (#1071)
---
`gates.session_work_span` decided what a session changed by diffing its base tree (`HEAD^{tree}`
at session start) against the working tree. A `git pull`, a merge, a branch switch or a reset
moved HEAD onto history the session never wrote, and those files landed in the span. The
reflection gate then blocked sessions that wrote no code. Under an active plan, the Critic Stop
gate demanded review coverage for the imported files too. Across governed repos on 3.8.0-dev,
reflection blocks rose from about one session in ten to one in six, and about half of the new ones
came from sessions whose only change was a sync.

The span now drops history OLDER than the session that a move brought in. Every commit HEAD
reaches that was made since `.session-start` counts, so a worktree delegate's branch merged back
still fires the gates. So do the commits HEAD's reflog records the session making, the paths of a
merge it concluded by hand, and uncommitted and untracked work. The span never holds more than the
base-tree diff did. If the reflog does not reach back past the session start, holds an entry the
classifier does not recognise, or git fails, the whole base-tree span is used. The extra git calls
happen only when the span is non-empty: one `rev-parse` when HEAD's tree is unmoved, four or five
more when it moved.

## Consumer note
- A session that only syncs (`git pull`, merging the base branch in, switching branches) is no
  longer blocked for a reflection or a Critic review of history older than the session. Code the
  session commits or leaves uncommitted fires the gates as before.
- Commits made by anyone after the session started still count when a pull, merge or checkout
  brings them in, including another session's in a shared checkout: the rule is by age, so a
  delegate's merged-back work is never lost.
