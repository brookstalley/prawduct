---
schema: 1
type: fix
scope: agent-runnable-doctor-janitor
date: 2026-11-25
title: An agent can run /prawduct:janitor, and /prawduct:doctor runs the repairs it offers once the owner says yes
---
`/prawduct:janitor` set `disable-model-invocation: true`, so the harness refused an agent's Skill
call and told it to ask the user to type the command. The reason given was its `Bash(python3 *)`
grant, which also admits `python3 plugin/bin/prawduct-hook backlog import`. Janitor is
model-invocable again with its grants unchanged (`owner-rulings.md`, 2026-11-26): `allowed-tools`
cuts prompts for a competent model and is not a security boundary. The test that read every
model-invocable skill's wildcards for that reach is replaced by a literal check: no skill's
`allowed-tools` names `backlog import`, `backlog merge` or `backlog file-upstream` in either
spelling. A broad grant that merely admits them does not count.

`/prawduct:doctor` was already model-invocable and already granted its repair commands, but its
prose handed the apply step to the owner ("the owner runs `prawduct-hook reanchor --apply`"), so an
agent stopped and asked a human to run a command it was allowed to run. The tripwire, anchor,
coverage-scaffold and norm-index-scaffold repairs now read: show the dry run, ask once, and on the
owner's yes run the `--apply` yourself. An archive shows `archive-plan --dry-run` first, then runs
on the yes. A failed repair is relayed verbatim and not retried around: a non-zero exit, a
`refused:`, `not-archived:`, `unwritable` or `could not write` line, or coverage-scaffold's
`NOTE: could not write`, which exits 0. A plan whose claimed branch vanished is re-pointed by hand,
once the owner names the branch: `plan bind` refuses a plan that already claims one. The owner's
judgments stay the owner's: which norms to ratify, which plans are done, a superseded plan's
reason, what a coverage stub says, and delegation policy. So do the edits doctor must not make:
`.gitattributes`, the operator-verification queue, and the plugin cache deletes.
`docs/doctor-vs-janitor.md` now says doctor repairs on the owner's yes, and janitor's stale-plan
cleanup shows the archive's dry run, asks the owner, and archives on their yes.

## Consumer note
An agent can now invoke `/prawduct:janitor` itself. `/prawduct:doctor` asks before a repair and
then runs it on your yes, instead of asking you to run it. Nothing new prompts.
