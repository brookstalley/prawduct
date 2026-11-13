---
schema: 1
type: feature
scope: testament-evidence-wiring
date: 2026-11-13
title: a repo on testament is told when its evidence runs the suite a second time
closes: [brookstalley/prawduct#1167]
---
A repo onboarded to testament kept a declared `test_command` that ran the suite locally. Its
agents ran the tests with `testament run`, as the repo's instructions said, and could not
hand that run to the evidence recorder, so every evidence record ran the whole suite a second
time on the local machine.

- **A new advisory at session start,** `testament-evidence:declared-command-skips-testament`.
  It fires when `.testament.toml` is at the repo root and no declared `test_command` or
  `test_commands` entry runs `testament run`. It names the declared commands and the fix in the
  repo's own form: `test_command: testament run --junit-xml {junit_xml}`, or that command in place
  of the matching `test_commands` entry. The owner approves the change and nothing edits the file
  for them. One testament entry among several counts as wired.
- **The `--from-counts` refusal names the route that works.** Its text is chosen from the
  declaration the recorder resolved. Where a declared command runs testament, it leads with a bare
  `record`. Where none does, it gives the `testament run --junit-xml <report>` route and the fix.
  Where several commands are declared, it asks for one `--from-junit` report per command, in every
  repo, so one report is never offered as the whole suite. The recorder still refuses exactly what
  it refused before.
- **`building.md` stops claiming** that `--from-counts` ingests beside a declared command,
  which the recorder refuses. `project-state-keys.md` gives the testament declaration.

## Consumer note
A repo with `.testament.toml` and a declared command that doesn't run testament sees one new
dismissable advisory. In every repo, the `--from-counts` refusal's wording changes; what it refuses
does not.
