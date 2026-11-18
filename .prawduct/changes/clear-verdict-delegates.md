---
schema: 1
type: fix
scope: clear-verdict-delegates
date: 2026-11-18
title: an in-flight delegate is safe to clear once the forward notes say what it is doing and why
closes: [brookstalley/prawduct#1190]
---
The session-hygiene guide said a delegate "dies with the session", so any delegate kept the
session at `DO NOT CLEAR`, and agents justified the hold with a claim they could not back. A clear
stops no background agent, and its completion still arrives. What a clear loses is the context: the
completion lands in a session that no longer knows what the agent was for. The clear verdict's
delegate rule now keys on that. A delegate holds the session only while the conversation is the
sole record of what it is doing and why. It is `SAFE TO CLEAR` once the forward notes carry, for each
delegate, what it is working on and why (the goal its brief served, not a task number), its worktree
and branch, where its result lands, and what integration it owes. The guide defines "work a clear
would kill" as work whose result a clear loses, not a process a clear stops. The live-review rule
keeps `DO NOT CLEAR`, now for the reason that holds: the review is not recorded until it is
consolidated.

## Consumer note
Agents in governed repos may now close `SAFE TO CLEAR` while delegates are still running, provided
`.prawduct/.handoff-notes.md` says what each one is doing and why, where its result lands and what
integration it owes. A live Critic review still keeps the session open.
