# Issue #1067 — hooks: ephemeral-worktree notice fires on every harness hook via stderr: Requirements

`status: draft · stage: requirements · area: hooks · added: 2026-11-02 · source: critic (cumulative review rev-20261025T234659Z-fc07633e, R-2) · issue: https://github.com/brookstalley/prawduct/issues/1067`

Related: #1059 (the skew guard's reporting policy), #563, #648 (durable agent worktrees still get the notice).

## Problem

`_check_ephemeral_worktree` (`plugin/bin/prawduct-hook`) runs before dispatch for every command and
calls `_print_ephemeral_notice` — which writes the fork-point "this tree is a snapshot" note to
**stderr** — on every path that proceeds. That includes the three harness-invoked commands
(`_HARNESS_INVOKED_COMMANDS` = `clear`, `stop`, `subagent-stop`). Two consequences for a session
inside a `.claude/worktrees/agent-*` tree:

1. **Stop / SubagentStop repeat it every turn.** The note describes a property of the tree, not of
   the turn; there is nothing for the agent to act on after the first time.
2. **SessionStart says it on the wrong channel.** The harness injects a SessionStart hook's
   *stdout* into the agent's context and only logs stderr at exit 0. So `clear --session-start`
   emits the note where nobody reads it.

The sibling guard, `_check_binary_skew`, was just given a deliberate policy for exactly this
(`_SKEW_REPORTING_HOOK = ("clear", "--session-start")`): say it once, on stdout, at session start;
`stop`/`subagent-stop` stay silent. The ephemeral guard does not consult it. Its docstring ("this is
the only channel that reaches such an agent without its cooperation") also now contradicts the skew
guard's comment, which names stdout-at-SessionStart as the channel that reaches the agent.

The defect is a class — *how a pre-dispatch notice behaves when the caller is a harness hook* — with
two owners deciding it independently. A third pre-dispatch notice would make a third decision.

## Goals

- G1. A harness hook inside an agent worktree produces the fork-point note **at most once per
  session**, at session start, on the channel that reaches the agent.
- G2. Non-hook callers (an agent running `backlog`, `test-evidence record`, etc. in the tree) keep
  today's stderr note on every proceeding command — that is the cooperation-free channel the
  docstring describes, and it is correct for that caller.
- G3. One owner decides "how a pre-dispatch notice behaves for a harness hook"; both guards call it.
- G4. The ephemeral docstring and the skew comment stop contradicting each other.

## Non-goals

- The ephemeral **refusal** (which commands are blocked) — unchanged.
- The note's wording, and the durable-worktree variant (`kind is None`, #648) beyond routing.
- Changing `_HARNESS_INVOKED_COMMANDS` membership.
- Making SessionStart stdout carry anything beyond the one note (no new briefing section).

## Requirements

- R1. **One policy helper.** Introduce a single function (working name `_pre_dispatch_notice_route(command, argv)`) returning one of `stdout` / `stderr` / `silent`:
  - `clear` with `--session-start` → `stdout` (once per session start);
  - any other member of `_HARNESS_INVOKED_COMMANDS` (`stop`, `subagent-stop`, `clear` without the flag) → `silent` for a hook caller, but see R3 for `clear` without the flag;
  - everything else → `stderr` (today's behaviour).
  Both `_check_binary_skew` and `_check_ephemeral_worktree` obtain their channel from it. The skew guard's existing outputs must not change (its tests pin them).
- R2. **Keyed on the invocation shape, not the verb**, as the skew guard already does: an agent may run `clear` itself without `--session-start`, and that caller can act on a stderr note. The helper reuses `_SKEW_REPORTING_HOOK` rather than restating the pair; rename it if its name now overclaims (it reports more than skew).
- R3. `clear` without `--session-start` and `stop`/`subagent-stop`: decide explicitly. Recommendation: `stop`/`subagent-stop` silent; `clear` without the flag → `stderr`, because a non-hook `clear` caller is an agent. (Open question Q1: `stop` cannot be told apart from an agent-run `stop`; silent is accepted.)
- R4. **Both notice variants route.** The ephemeral notice is emitted from four sites (read-only command, dispatcher override, harness carve-out, durable worktree). All four go through the helper's channel decision; none prints to stderr directly. The durable-worktree path (`kind is None`) is the one that sits *before* the `_HARNESS_INVOKED_COMMANDS` branch, so it must route too.
- R5. **Exit code and refusal untouched.** Routing a notice to stdout must not change the return value of either guard, and the `BLOCKED:` refusal text stays on stderr.
- R6. **Docs agree.** Rewrite the `_check_ephemeral_worktree` docstring and the long comment inside its `_HARNESS_INVOKED_COMMANDS` branch so they state the shared policy, drop the "only channel" claim, and keep the (accurate) point that the briefing file is absent in an isolated worktree. Search the claim, not the tokens: `grep -rn "only channel\|stderr" plugin/bin/prawduct-hook` over pre-dispatch guards, and the "four callers" wording in `_print_ephemeral_notice`.
- R7. **Sweep the class.** List every `print(..., file=sys.stderr)` reachable before dispatch for a command in `_HARNESS_INVOKED_COMMANDS` (the issue's own search). Each is either routed through the helper or recorded, in a comment beside it, as an intentional exception with its reason. The sweep result goes in the PR description as a table.

## Tests (each red-verified against current code)

- T1. `clear --session-start` in an `agent-*` ephemeral worktree: note on **stdout**, stderr free of it.
- T2. `stop` and `subagent-stop` in the same tree: neither stdout nor stderr carries the note.
- T3. A non-hook command (`test-evidence record --from-counts …`) in the tree: note on stderr, unchanged (existing `test_a_durable_agent_worktree_still_gets_the_snapshot_notice` family stays green).
- T4. Durable agent worktree (named branch) variants of T1–T3, since that path returns before the harness branch.
- T5. Skew and ephemeral together (a foreign-binary session inside an agent tree): `clear --session-start` emits each note once, both on stdout; `stop` emits neither.
- T6. A mechanical pin: the helper is the only place that chooses a channel for a pre-dispatch notice (a source check that neither guard calls `print(..., file=sys.stderr)` for a `NOTE:` directly), so a third guard cannot decide separately.

## Acceptance

- A session started inside a `.claude/worktrees/agent-*` tree sees the fork-point note once, in its context, and never again on any Stop.
- An agent running a governance command by hand in that tree still gets the note on stderr.
- `grep` for the old "only channel that reaches such an agent" claim returns nothing.
- Full suite green (`testament run`).

## Open questions for the owner

- Q1. `stop`/`subagent-stop` silence: acceptable that an *agent-run* `stop` also loses the note? (Recommendation: yes — it already learned it at session start or from its first non-hook command.)
- Q2. SessionStart stdout for a *subagent* worktree: `subagent-stop` is silent, but does a subagent's own SessionStart run `clear --session-start`? If subagents do not run SessionStart, the agent-worktree population this note was written for (isolated subagents) would never see it on stdout and would lose its only signal. This needs a check of the harness behaviour before R1 is final; if true, the note must remain on stderr for non-session-start `clear`/first-proceeding command, or ride another hook.
- Q3. The issue's "Unknowns" asks how often Stop runs inside an agent worktree. Is a quick count from `.prawduct` telemetry worth taking, or does the policy stand regardless? (Recommendation: stands regardless.)

## Next step

Resolve Q2 first (it can invalidate R1's SessionStart-only delivery), then write the design: helper
signature and placement, and how the four emit sites in `_check_ephemeral_worktree` collapse onto it.
