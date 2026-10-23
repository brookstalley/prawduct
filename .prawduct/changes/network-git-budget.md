---
schema: 1
type: fix
scope: network-git-budget
date: 2026-10-23
title: git-tidy's remote calls get a network time budget instead of the local one
---
git-tidy's first real run against this repo failed one `git push --delete` at the 15-second
budget. That budget is priced for local file reads, and the timeout message pointed the reader at
a mounted working tree. Every git call goes through `evidence.run_git`, which now gives a
subcommand that reaches a remote (`fetch`, `push`, `ls-remote`, `pull`, `clone`) a 60-second floor.
git-tidy's `gh` calls (`pr list`, `pr view`, `pr edit --base`) take the same budget, through one
owner, `evidence.network_timeout`. `PRAWDUCT_GIT_TIMEOUT` still raises both budgets but can no
longer push a network call below the floor, and a timeout on a network call now says it was
waiting on the remote.

## Consumer note
- `git-tidy`'s fetch, `ls-remote`, `push --delete` and `gh` calls now wait up to 60 seconds,
  instead of 15, before counting as failed. Set `PRAWDUCT_GIT_TIMEOUT` above 60 to allow longer.
  Setting it below 60 now shortens only local git calls.
