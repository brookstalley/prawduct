---
schema: 1
type: fix
scope: fork-project-dir
date: 2026-11-26
title: A forked skill acts on the repo its caller names with --project-dir
closes: [brookstalley/prawduct#1253]
---
A `context: fork` skill invoked by a subagent that works in another repository runs its shell in
the session's launch repo (measured on Claude Code 2.1.332), so `/prawduct:critic` reviewed the
launch repo and reported "nothing to review", and `/prawduct:backlog` or `/prawduct:advisory`
would have written into the launch repo's store. `critic-begin`'s wrong-tree guard (PDT-WT9K)
could not catch it: it compared two directories the fork held itself.

Chunk 01 shipped the whole fix. `prawduct-hook` takes `--project-dir <absolute path>` after any
subcommand and before a bare `--`. `_dispatch` removes it before any command parses, validates it,
`chdir`s there and makes it the project dir over the launch pin and the cwd, so PDT-WT9K compares
one tree. A missing value, two different values or a relative path exits 2; a path that does not
exist, is not a work tree, or is a subdirectory rather than the toplevel exits 1. Each refusal
names itself and runs nothing.

`critic-begin` now prints `PRAWDUCT: tree <toplevel> · <branch> @ <sha12>` first on every outcome
after argument parsing, and the critic skill leads its report with it, so a caller who forgot the
option sees which tree was judged. The three forked skills (critic, backlog, advisory) accept the
argument and pass it to every `prawduct-hook` call, `git -C` and file path; the critic gains
`git -C * <verb>` grants, and each bare hook grant in a forked skill gains its `--project-dir`
form. `methodology/delegation.md` says when a delegate passes it. A test reads every `context:
fork` skill and fails one that does not declare the argument.

## Consumer note
A subagent working in a repository other than the one the session started in can now pass
`--project-dir <that repo's toplevel>` to `/prawduct:critic`, `/prawduct:backlog` or
`/prawduct:advisory`, and the skill acts on that repo. Every critic run's first line now names the
tree it reviewed.
