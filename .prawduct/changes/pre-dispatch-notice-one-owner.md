---
schema: 1
type: fix
scope: pre-dispatch-notice-one-owner
date: 2026-11-15
title: A session in an agent worktree is told once, at SessionStart, that its files are a snapshot, and no longer on every Stop
closes: [brookstalley/prawduct#1067]
---
The ephemeral-worktree notice ("this is an agent worktree; every tracked file is a snapshot of the
commit it was forked from") was printed on stderr for every command that proceeded, harness hooks
included. A session inside a `.claude/worktrees/agent-*` tree got it on every Stop, repeated each
turn with nothing to act on, and at SessionStart on stderr, which the harness only logs: SessionStart
injects stdout.

How a pre-dispatch notice behaves on a harness-invoked hook now has one owner,
`_emit_pre_dispatch_notice`, and both pre-dispatch guards (binary skew and ephemeral worktree) say
their notes through it. At `clear --session-start` the notice is said once on stdout. On `stop` and
`subagent-stop` it is silent. A command the agent runs itself, including `clear` without
`--session-start`, still prints it on stderr, as before. The ephemeral refusal is unchanged. The
guard's docstring, which called stderr "the only channel that reaches such an agent", now agrees
with the skew guard's comment.

## Consumer note
Inside an agent worktree, the snapshot notice now appears in the SessionStart context instead of on
Stop's stderr. Nothing else changes.
