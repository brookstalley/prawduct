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
without a prompt. Those two grants are deleted, and janitor is model-invocable again
(`owner-rulings.md`, 2026-11-26).

The same reach was open in other model-invocable skills, so the grant rails now test what a grant
can reach rather than how it is spelled. One probe set of commands that must prompt runs against
every model-invocable skill's grants and every agent's tool list: interpreters (`python3 -c`,
`bash -c`, `node -e`, `uv run`, `npm run`, `npx`), `find -exec`, `git -c alias.x='!cmd'`,
`git difftool -x`, `git rebase --exec`, destructive git (`push --force`, `reset --hard`,
`branch -D`, `clean -fdx`, `checkout -- .`, `worktree remove --force`, each also behind `-C .`),
the irreversible backlog ops in both spellings and behind a leading-star grant, `git-tidy --apply`
and `--reap`, a plan archive, and `git log|diff|show --output=<file>`. A `!Bash(...)` entry is a
deny and is no longer read as a grant. The rail caught and this change narrows:

- **janitor**: `git status|log|show|diff|blame|for-each-ref|merge-base|ls-files|check-ignore*`
  become space-terminated (`git diff*` admitted `git difftool -x <cmd>`), plus `git rev-parse *`,
  `git branch --list *`, `git worktree list *` and `git stash list`, the reads its themes need.
  `git-tidy*` becomes its four dry-run forms, and `archive-plan*` becomes `archive-plan * --dry-run`,
  in both spellings.
- **pr**: `Bash(git *)` becomes the verbs its body runs: `branch --show-current`, `status`, `log`,
  `symbolic-ref --short refs/remotes/origin/HEAD`, `merge-base`, `rev-parse`, `merge`, `add`,
  and `commit`. Its `archive-plan*` grant is gone.
- **runbook**: `Bash(find *)` is gone. Its body names no `find`, and Glob covers the search.
- **onboard**: `git -C * status*`, `git -C * add *` and `git -C * commit *` are gone. The star
  before the verb admitted `git -C . -c alias.x='!cmd' x status`.

Three reaches are kept, each with its reason beside the test (`_REACH_EXEMPT`): a read verb's
`--output=<file>`, which no prefix grant can exclude; the critic reviewer's `git -C * <verb> *`,
which must name the project directory; and doctor's `archive-plan*`, whose flow takes one
confirmation for the whole act.

`/prawduct:doctor` was already model-invocable and already granted its repair commands, but its
prose handed the apply step to the owner ("the owner runs `prawduct-hook reanchor --apply`"), so an
agent stopped and asked a human to run a command it was allowed to run. The tripwire, anchor,
coverage-scaffold and norm-index-scaffold repairs now read: show the dry run, ask once, and on the
owner's yes run the `--apply` yourself. An archive shows `archive-plan --dry-run` first, then runs
on the yes. A failed repair is relayed verbatim and not retried around: a non-zero exit, a
`refused:`, `not-archived:`, `unwritable` or `could not write` line, or coverage-scaffold's
`NOTE: could not write`, which exits 0. A plan whose claimed branch vanished is re-pointed by hand,
once the owner names the branch: `plan bind` refuses a plan that already claims one, so doctor
gains no grant for it. The owner's judgments stay the owner's: which norms to ratify, which plans
are done, a superseded plan's reason, what a coverage stub says, and delegation policy. So do the
edits doctor must not make: `.gitattributes`, the operator-verification queue, and the plugin cache
deletes. `docs/doctor-vs-janitor.md` now says doctor repairs on the owner's yes.

## Consumer note
An agent can now invoke `/prawduct:janitor` itself, and `/prawduct:doctor` runs a repair it offers
after you say yes instead of asking you to run it. In default permission mode, these now prompt
because no skill pre-approves them: janitor's commands for your product's own toolchain (`python3`,
`npm` and the like), any git command beyond its reads, `git-tidy --apply` and `--reap`, and a plan
archive; in `/prawduct:pr`, `git push` (a prefix grant that admits `git push` also admits
`git push --force`), `git rebase`, `git fetch`, the `git clean` of its PR-body file and the plan
archive; in `/prawduct:onboard`, its `git -C <target>` status, add and commit. Each prompt is the
consent for that step. In bypass mode they run as before.
