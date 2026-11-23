---
schema: 1
type: fix
scope: recorder-temp-session-file
date: 2026-11-23
title: the test-evidence recorder's temp file is a session file
closes: [brookstalley/prawduct#1202]
---
`test-evidence record` writes `.prawduct/.test-evidence.json` through a `.tmp` sibling and renames
it. The final name was a session file and the `.tmp` name was not. So a review's tree capture
that landed between the write and the rename read the temp file as a changed tree and refused the
review. A write that died before the rename also left the file untracked, where the next
`git add -A` would pick it up. `.prawduct/.test-evidence.json.tmp` is now in `core.GITIGNORE_ENTRIES`,
in the hook's untrack mirror, and in this repo's `.gitignore`. Its boundary disposition is to
survive: the next write overwrites it, and unlinking it at a boundary could race another session's
recorder between the write and the rename.
