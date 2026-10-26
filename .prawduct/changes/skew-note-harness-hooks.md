---
schema: 1
type: fix
scope: skew-note-harness-hooks
date: 2026-10-25
title: The plugin-binary-skew note fires once per session, not on every Stop
closes: [brookstalley/prawduct#1059]
---
In a framework checkout, every harness hook runs the installed plugin, so the binary-skew guard
noted a foreign binary on SessionStart, on every Stop and on every Critic SubagentStop — and the
note told the reader to re-run the command with `$CLAUDE_PLUGIN_ROOT` unset, which no hook can do.
The framework repo's sessions saw it as a stop-hook storm: the same unactionable line each turn.
The skew is a property of the session, so it is now reported once, by `clear --session-start` (the
two SessionStart entries that run the hook), on stdout: that is how a SessionStart hook's output
reaches the agent, while stderr at exit 0 is only logged. Stop and SubagentStop stay silent on it.

The note is worded for a hook's reader. The hooks themselves write governance state with the
installed plugin, unguarded: SubagentStop consolidates a three-reviewer Critic review, and Stop can
record an abandoned one. Commands the agent runs are guarded and refuse on a foreign binary. To have
the checkout's code do the hooks' writes, start the session with `claude --plugin-dir <repo>/plugin`.
Both lists in the note are rendered from the sets the guard decides by.

An agent running `clear` itself, and a lib-only skew under `--session-start` (which no hook can
produce), still get the ordinary note with its remedy. `_SKEW_REPORTING_HOOK` names the one reporting
call, and a test pins it to the `hooks.json` SessionStart entries that run the hook and to nothing the
other events run. The refusal for agent-invoked data-plane writes and the note for other
agent-invoked commands are unchanged.

## Consumer note
none: product repos never see the binary-skew guard.
