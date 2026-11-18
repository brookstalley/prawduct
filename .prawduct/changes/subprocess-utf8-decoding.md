---
schema: 1
type: fix
scope: subprocess-utf8-decoding
date: 2026-11-18
title: one non-UTF-8 byte in a repo no longer makes prawduct's git reads fail
closes: [brookstalley/prawduct#1188]
---
Every subprocess the plugin runs used to decode its output with the locale's codec and strict
errors, so one byte of a legacy encoding in git output made the call fail. A vendored C header with
Windows-1251 comments, for example, turned the whole branch diff into "could not be read", so
`check-pr-hygiene` exited 3 and checked no other file for credentials.

Every such call (git, gh and the interpreter probe) now decodes as UTF-8 without failing:
`surrogateescape`, which keeps the original bytes so a pathname survives the trip back into a git
argument, or `replace` where the output is only displayed (the plugin banner). The encoding side
follows the same rule, so the failure does not just move to the first write. Files the plugin writes
use `backslashreplace` and stay valid UTF-8, with such a byte shown as `\udce9`. The session's
`git status` baseline keeps git's exact bytes, because the Stop gate compares it with fresh
output. Hashes keep the bytes too. `prawduct-hook` and `test-reference-verify` print such a byte as
`\udce9` instead of crashing. A test reads every subprocess call, text write and `.encode()` in the
plugin, and fails on one that would raise on a byte that is not UTF-8 or that it cannot read.

## Consumer note
A branch whose diff carries non-UTF-8 content is now checked by `check-pr-hygiene`, so
`/prawduct:pr create` no longer stops on it, and a credential elsewhere on that branch is now
reported. In a repo with `core.quotePath=false`, a changed file whose name is not UTF-8 no longer
stops session start or the handoff; the handoff lists it with the byte escaped. Any other command
that hit such content (a review's diff, a file shown from HEAD) now reads it instead of reporting
the read as failed.
