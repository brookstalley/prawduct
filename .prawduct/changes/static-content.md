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
path, never a lighter one.

## Consumer note
To stop a static-document branch paying for a suite run, list the directories that hold such files
under `static_content_prefixes:` in `.prawduct/project-state.yaml` (a block sequence of path
prefixes; see `/prawduct:methodology project-state`). Do not list a path your tests read as data.
Put that one under `suite_coupled_prefixes:`, which wins any overlap. The declaration takes effect
once committed. Nothing changes for a repo that declares nothing.
