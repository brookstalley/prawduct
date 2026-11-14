---
schema: 1
type: fix
scope: native-review-parse
date: 2026-11-12
title: the native review's counts hold when the wrapper keeps the host header, and compare checks them
closes: [brookstalley/prawduct#1161]
---
Three data-quality gaps in the paired native review (#1130), found by the verify pass on its build.
None of them blocked anything, but each could have put a wrong number into the comparison the
owner decides on.

- **Parsing.** The parser now drops the host's whole result header before it reads a `(none)` line
  as an empty run. That covers a `Result:` line the wrapper was told to drop but may keep, a
  `(none)` under it or beside it, and blank lines between them, so the answer no longer depends on
  layout. Before this, `Result:\n(none)\n\n<prose>` counted as zero findings.
- **NEXT-ACTION wording.** A native text that has landed but cannot be counted is now described as
  `landed, not countable`, and one that exists but cannot be read as `text unreadable`. Neither is
  `it may still be running` any more.
- **compare.py.** It cross-checks each text against what the ledger recorded when the run landed.
  The check compares which findings, not just how many, and treats a run whose countability changed
  as a disagreement, not a skip. It names each run where the two differ. It also warns when a native
  run and its Critic review ran on different model families. With `--transcripts`, it prints one
  model per fork beside the recipe each fork ran, and warns about a recipe that differs from the
  level its run recorded.

Most of these were found by the paired native review of this branch's own boundary review, the
second live paired run. The Critic raised one of them; the native review raised that one and eight
more.

## Consumer note
none: affects only development builds' paired native review records and the experiment's
comparison script; no gate, verdict or command changes
