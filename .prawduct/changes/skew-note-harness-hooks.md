---
schema: 1
type: fix
scope: skew-note-harness-hooks
date: 2026-10-20
title: The plugin-binary-skew note fires once per session, not on every Stop
---
In a framework checkout, every harness hook runs the installed plugin, so the binary-skew guard
noted a foreign binary on SessionStart, on every Stop and on every Critic SubagentStop — and the
note told the reader to re-run the command with `$CLAUDE_PLUGIN_ROOT` unset, which no hook can do.
The framework repo's sessions saw it as a stop-hook storm: the same unactionable line each turn.
The skew is a property of the session, so now SessionStart's `clear` reports it once, in hook
terms (agent-invoked governance writes are guarded and refuse on a foreign binary; `claude
--plugin-dir <repo>/plugin` loads the checkout's plugin for a session), and Stop and SubagentStop
stay silent on it. `_SKEW_REPORTING_HOOK` names that one entry point, and a test pins it to what
`hooks.json` runs at SessionStart and to nothing the other events run. The refusal for agent-invoked
data-plane writes and the note for other agent-invoked commands are unchanged; product repos never
see the guard.
