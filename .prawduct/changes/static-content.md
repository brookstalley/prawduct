---
schema: 1
type: feature
scope: static-content
date: 2026-11-24
title: A repo can declare static content, which is still reviewed but costs no suite re-run and no third reviewer
closes: [brookstalley/prawduct#1239]
---
A branch made of static documents (stylesheets, static example pages, a file of design values)
paid the whole code path at the PR boundary: a fresh whole-suite run and a three-reviewer boundary
review, though nothing executes or parses those files. A repo can now declare those paths under
`static_content_prefixes:` in `project-state.yaml`.

Declared static content is still reviewed: it still needs review coverage, the doc-only fast path
still refuses it, and it still needs a change record (owner ruling 2026-11-24). A path a test
reads as data (`suite_coupled_prefixes`) is never static, and neither is governance-protected
prose.

### Chunk 01: suite evidence and the coverage floor
A change confined to declared static content leaves recorded suite evidence `current`, so the
suite is not re-run for it. The same holds when a JUnit report is ingested, and in the PR gate's
explanation of an uncovered span. The coverage floor asks no test to reference a static file.
A declaration the reader cannot read whole declares nothing static, so a typo costs the full
path, never a lighter one, and the `test-status` reason says the declaration was refused. Every
check reads the declarations from the tree it judges, and a static prefix counts only once the
integration branch carries it too, so no branch lightens its own checks by declaring.

### Chunk 02: the boundary review's roster
Declared static content does not count toward the boundary review's volume escalator (12
judgeable files), so a static-heavy branch takes one reviewer instead of three. A static file on
a risk surface still takes the coordinator. The roster reads the declaration from the tree it
reviews, and its rationale says how many files it did not count.

## Consumer note
To stop a static-document branch paying for a suite run and a three-reviewer boundary review, list the directories that hold such files
under `static_content_prefixes:` in `.prawduct/project-state.yaml` (a block sequence of path
prefixes; see `/prawduct:methodology project-state`). Do not list a path your tests read as data.
Put that one under `suite_coupled_prefixes:`, which wins any overlap. The declaration takes effect
once it is on the integration branch: the branch that adds it pays the full path itself. Nothing
changes for a repo that declares nothing.
