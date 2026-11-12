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

- **Parsing.** The parser now drops the host's whole result header, including a `Result:` line the
  wrapper was told to drop but may keep, before it reads a `(none)` line as an empty run. Before
  this, `Result:\n(none)\n\n<prose>` counted as zero findings.
- **NEXT-ACTION wording.** A native text that has landed but cannot be counted is now described as
  `landed, not countable`, not `it may still be running`.
- **compare.py.** With `--transcripts`, it now prints each fork's model beside its recipe and warns
  about any fork that ran a recipe other than `high`. On every run it also cross-checks its own
  count of each text against the count the ledger recorded when the run landed, and names any run
  where the two differ.

## Consumer note
none: affects only development builds' paired native review records and the experiment's
comparison script; no gate, verdict or command changes
