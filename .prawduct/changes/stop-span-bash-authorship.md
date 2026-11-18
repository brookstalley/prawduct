---
schema: 1
type: fix
scope: stop-span-bash-authorship
date: 2026-11-18
title: a file this session wrote with Bash or a delegate stays its own work when you commit it from a terminal beside another session
closes: [brookstalley/prawduct#1184]
---
When a second session was writing in the same checkout, the Stop span dropped a commit made
while this session ran no tool call, unless one of its files was named by this session's Edit,
Write, MultiEdit or NotebookEdit calls. A file the session wrote another way did not count: with
Bash (`sed -i`, a heredoc, a code generator), through a delegate subagent, or from a background
command. A terminal commit of such a file was dropped, so the reflection and Critic Stop gates
did not fire on the session's own work. The drop's only trace was a stderr line at a clean Stop,
which nobody reads.

A commit is now also kept when one of its files was last written while this session had a tool
call or `!` command running. The time is read from the file in the checkout: its modification
time, and on POSIX its inode change time, which a rename moves. This is the same test the
commit's own moment already got, applied to the moment its file was written. It covers every
way a session writes, because each write happens inside one of its calls.

#1071's protection still holds. A file another session wrote while this one ran nothing is not
this session's, and that session's commit of it is still dropped. A file written at a moment
both sessions were acting cannot be told apart, and it stays counted, as a commit made at such a
moment already did. The reviewer's other proposal was to keep any file that was uncommitted at
one of this session's earlier Stops. It was not taken: both sessions share one working tree, so
the other session's uncommitted files show at this session's Stops too. Keeping them would
attribute nearly every commit the other session made, which is the error #1071 fixed.

Two cases are still judged on the commit's moment and the edit tools alone: a file someone else
wrote again after this session, and a deleted file, which leaves no time to read.

Each dropped commit is now recorded once per session as an `other-session-commit` stop
observation (`gates.record_dropped_commits`; `evidence.append_stop_observation` takes a
`dedupe_key`). It carries the sha and how many files the commit touched, never their names.
`prawduct-hook stats` counts it, and `prawduct-hook evidence list --kind guard-refusal` lists
it. The stderr line stays, and it still rides the block text when another gate blocks.

`tests/test_reflection_gate.py` (`TestAFileThisSessionWroteByAnyMeans`) pins these cases: a
terminal commit of a file written during a Bash call or a delegate's call stays counted; the
same file written between calls is dropped; a renamed file counts by its inode change; a drop
seen at two Stops is recorded once and `stats` counts it; each record that does not land is named;
and the telemetry doc's row names the check and reason. The first three and the dedupe were seen
red before the fix. The inode-change read, the dedupe and the Stop call site were each removed in
turn and seen to fail.

## Consumer note
If you run two Claude Code sessions in the same checkout, a file a session wrote through Bash,
a delegate subagent or a background command now counts as its own work when you commit it from
a terminal. Before, that commit was left out, and the reflection and Critic Stop gates did not
ask about it. A commit left out as the other session's is now also recorded, once, as an
`other-session-commit` observation that `prawduct-hook stats` counts.
