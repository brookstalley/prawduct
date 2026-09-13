---
description: Post-sync advisory management — list, inspect, dismiss, undismiss, or resolve the advisories surfaced in the session briefing
argument-hint: "list [--state=active|dismissed|resolved|all] [--feature=<name>] | show <id> | dismiss <id> [--reason \"...\"] | undismiss <id> | resolve <id>"
user-invocable: true
disable-model-invocation: false
context: fork
allowed-tools: Read, Bash(prawduct-hook advisory*)
---

You are managing **post-sync advisories** — the "this project should probably do X, but we won't force it" nudges that sync probes raise and the session briefing surfaces under `ADVISORIES (post-sync, N active)`. They are informational, never gates.

All work goes through one command: `prawduct-hook advisory <subcommand>`. Do not edit `.prawduct/.advisories.json` by hand — it is the per-clone nag log, owned by the advisory store.

## Subcommands

| Invocation | What it does |
|---|---|
| `prawduct-hook advisory list` | List **active** advisories (default). |
| `prawduct-hook advisory list --state=active\|dismissed\|resolved\|all` | Filter by lifecycle state. `all` shows every state. |
| `prawduct-hook advisory list --feature=<name>` | Filter to one feature (e.g. `--feature=backlog`). Combines with `--state`. |
| `prawduct-hook advisory show <id>` | Full detail on one advisory. For a resolved/dismissed (compact) entry it **re-runs the probe** to reconstruct the full evidence list. |
| `prawduct-hook advisory dismiss <id> [--reason "..."]` | Dismiss (sticky — won't re-surface even if the trigger persists). Reason optional but encouraged. |
| `prawduct-hook advisory undismiss <id>` | Clear a dismissal — returns to active if the probe still fires on next sync. |
| `prawduct-hook advisory resolve <id>` | Manually mark resolved now (rare — usually a probe or the recommended action does this). |

## How to use this skill

1. Parse `$ARGUMENTS` into a subcommand + args. If empty, run `list` (active) as the default and show the result.
2. Run the matching `prawduct-hook advisory ...` command and relay its output.
3. For `dismiss`/`undismiss`/`resolve`, confirm the id exists first if the user is unsure — run `list --state=all` and check. A `not found` result means the id is wrong or the advisory was already garbage-collected.
4. Resolution normally happens automatically: run the advisory's `agent →` line (`recommended_action`), and the next sync clears it (the probe stops firing once the project-state fact is set). Prefer that path over manual `resolve`.
5. **Every advisory addresses two readers, and the output labels which is which.** The `owner →` line is what the *person* decides, approves or supplies; the `agent →` line is the command *you* run. Relay the owner line to the user in your own words and never hand them a command to type — the commands are yours. An advisory with no `agent →` line is owner-only: there is nothing to run, and waiting on their answer is the correct next step, not a gap to fill.

$ARGUMENTS
