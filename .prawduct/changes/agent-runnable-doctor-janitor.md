---
schema: 1
type: fix
scope: agent-runnable-doctor-janitor
date: 2026-11-25
title: An agent can run /prawduct:janitor, and /prawduct:doctor runs the repairs it offers once the owner says yes
---
`/prawduct:janitor` set `disable-model-invocation: true`, so the harness refused an agent's Skill
call and told it to ask the user to type the command. The reason was its `Bash(python3 *)` and
`Bash(npm *)` grants: an interpreter reaches every op an allow-list withholds, including
`python3 plugin/bin/prawduct-hook backlog import`, so a model-invoked janitor could have run it
without a prompt. Those two grants are deleted, and janitor is model-invocable again. Its broad
`Bash(git *)` would then have pre-approved `git push --force`, `git reset --hard` and
`git branch -D` for an agent, so it is narrowed to the read verbs the survey uses (`status`, `log`,
`show`, `diff`, `blame`, `for-each-ref`, `merge-base`, `ls-files`, `check-ignore`). Branch and
worktree removal stays with the granted `git-tidy --apply`. The explicit hook-subcommand grants are
unchanged.

`/prawduct:doctor` was already model-invocable and already granted its repair commands, but its
prose handed the apply step to the owner ("the owner runs `prawduct-hook reanchor --apply`"), so an
agent stopped and asked a human to run a command it was allowed to run. The tripwire, anchor,
coverage-scaffold, norm-index-scaffold, archive-plan and plan-claim repairs now read: show the dry
run, ask once, and on the owner's yes run the `--apply` yourself. Doctor also gains a
`plan bind` grant, so it can correct a plan's branch claim once the owner names the branch. The
owner's judgments stay the owner's: which norms to ratify, which plans are done, a superseded
plan's reason, what a coverage stub says, and delegation policy. So do the edits doctor must not
make: `.gitattributes`, the operator-verification queue, and the plugin cache deletes.

`test_no_model_invocable_skill_grants_an_irreversible_op` now covers janitor with no exemption.
Janitor's row in `_WRITE_REACH_EXEMPT` is gone. New tests pin that doctor and janitor are
model-invocable, that no model-invocable skill grants an interpreter whole, and that janitor's git
grants admit no destructive verb.

## Consumer note
An agent can now invoke `/prawduct:janitor` itself, and `/prawduct:doctor` runs a repair it offers
after you say yes instead of asking you to run it. In default permission mode, janitor's commands
for your product's own toolchain (`python3`, `npm` and the like) and any git command other than its
read verbs now prompt, because the skill no longer pre-approves them. In bypass mode they run as
before.
