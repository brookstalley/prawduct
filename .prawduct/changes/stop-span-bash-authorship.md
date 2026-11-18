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
call or `!` command running, before the commit was made. The time is read from the file in the checkout: its modification
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

Two cases are still judged on the commit's moment and the edit tools alone: a file written
again since, by anyone, and a deleted file, which leaves no time to read.

Each dropped commit is now recorded once per session as an `other-session-commit` stop
observation (`gates.record_dropped_commits`; `evidence.append_stop_observation` takes a
`dedupe_key` and `known_facts`). It carries the sha and how many files the commit touched, never their names.
`prawduct-hook stats` counts it, and `prawduct-hook evidence list --kind guard-refusal` lists
it. The stderr line stays, and it still rides the block text when another gate blocks.

`tests/test_reflection_gate.py` (`TestAFileThisSessionWroteByAnyMeans`) pins these cases: a
terminal commit of a file written during a Bash call or a delegate's call stays counted; the
same file written between calls is dropped; a renamed file counts by its inode change; a drop
seen at two Stops is recorded once and `stats` counts it; each record that does not land is named;
and the telemetry doc's row names the check and reason. The first three and the dedupe were seen
red before the fix. The inode-change read, the dedupe and the Stop call site were each removed in
turn and seen to fail.

Review fixes. The first cut read a file's last write wherever it fell. This session rewriting
the other session's committed file later moved that time into one of its calls: `git
checkout`, `git stash pop`, a formatter, or `cp` over the file. The other session's commit then
came back into this session's span, which is #1071's error again. A write now counts only when
it came before the commit, because a write after a commit cannot be what the commit recorded.
Both times come from this machine's clock, so no allowance for skew is needed beyond git's
whole-second commit stamps. The cost: if this session later rewrites its own committed file with
the same bytes, that commit is judged on its moment and the edit tools alone. It is then
dropped, and the drop is named and recorded.

The record of a dropped commit was deduped on the `.session-start` stamp. Every session in a
checkout writes that one marker, and only a session sharing its checkout drops a commit. So a
second session's drop of the same commit deduped away, and `stats` undercounted. The record is
now deduped on the session's transcript path, which is hashed into the record's id and not
stored. With no transcript, nothing is recorded and the stderr note says so. No drop is made
without a transcript, so in practice this does not happen. Recording also read the whole
clone-wide evidence store once per dropped commit at every Stop. It now reads it once per Stop.

The note for a record that did not land stays on stderr, and it rides the block text when
another gate blocks. The user cannot act on a missed telemetry record, and the note would repeat
at every Stop until the record lands. The Stop hook handles its other telemetry misses the same
way (`learning.written`, `_record_stop_observation`).

New tests in the same class: their commit's file, rewritten by this session after the commit, is
still dropped; two sessions dropping one commit leave two records; the store is read once per
Stop; with no session identity nothing is recorded and the note says so; and an unreadable
store names each commit and raises nothing. Each was seen red
with its fix removed, including the `known_facts` pass-through in `evidence` and the transcript
path at the `cmd_stop` call site.

## Consumer note
If you run two Claude Code sessions in the same checkout, a file a session wrote through Bash,
a delegate subagent or a background command now counts as its own work when you commit it from
a terminal, as long as that write came before the commit. Before, that commit was left out, and
the reflection and Critic Stop gates did not ask about it. A commit left out as the other session's is now also recorded, once, as an
`other-session-commit` observation that `prawduct-hook stats` counts.
