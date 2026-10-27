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

The span now keeps only paths the session authored. HEAD's reflog since the session started
(bounded by the base-tree marker's mtime) says why HEAD moved. The session's own commits count,
including rebased ones. A merge the session concluded by hand counts only the paths it resolved.
Uncommitted and untracked work counts as before. Pulls, automatic merges, checkouts and resets do
not count. The span never holds more than the base-tree diff did. If any reflog entry cannot be
classified, or git fails, the whole base-tree span is used. The extra git calls happen only when
the span is non-empty: one `rev-parse` when HEAD's tree is unmoved, three more when it moved.

## Consumer note
- A session that only syncs (`git pull`, merging the base branch in, switching branches) is no
  longer blocked for a reflection or a Critic review of the history it brought in. Code the
  session commits or leaves uncommitted fires the gates as before.
- Another session's commits made in the same checkout still count as this session's work, because
  they are commits in the same reflog.
