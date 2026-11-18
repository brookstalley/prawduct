---
schema: 1
type: fix
scope: testament-evidence-wrapper-scripts
date: 2026-11-18
title: the testament evidence advisory counts a declared wrapper script that runs testament, and hedges what it cannot read
closes: [brookstalley/prawduct#1189]
---
When a repo's declared `test_command` was a script that itself calls `testament run`, the session
advisory still said the command "runs the suite a second time, locally" and recommended replacing
it with `testament run --junit-xml {junit_xml}`. Following that advice would silently drop whatever
else the script runs (a lint, a native build) from test evidence. The probe and the recorder's
`--from-counts` refusal now read the in-repo shell script a declared command runs (known by a shell
shebang or a `.sh`/`.bash` suffix, behind any prefix such as `uv run` or `timeout`), one level deep,
and count a command in it that runs `testament run`, including through `bash -c` or `eval`. A
comment or an echoed string does not count. A wrapper prawduct cannot read (a make target, a script
outside the repo or in another language, or one called by another script) still fires the advisory. Its text now says
"as far as prawduct can read", and the owner action says to check what a wrapper runs besides tests
before replacing it.

## Consumer note
A repo with `.testament.toml` whose declared suite command is an in-repo script that runs
`testament run` no longer sees the `declared-command-skips-testament` advisory. Where the advisory
still fires, its wording is hedged and warns that replacing a wrapper drops its other checks. The
advisory id does not change.
