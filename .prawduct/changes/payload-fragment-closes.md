---
schema: 1
type: fix
scope: payload-fragment-closes
date: 2026-10-20
title: The PR reviewer sees a fragment's closes list as a closure claim
---
`pr-review-payload` scanned the change record's raw text for closing keywords, and neither
spelling a record uses reached that scan: a fragment's `closes: [owner/repo#N]` puts a bracket
between the keyword and the id, and a cut archive entry writes `closes=a,b`. So on every repo
recording fragments, the branch's own closure claims read as "mentioned only" and the reviewer's
check that each claimed item is actually closed (R-2) was silently skipped. Found by the PR
reviewer on #1026. The payload now renders the record owner's parsed `closes` list
(`RecordedChange.closes`) as a claim line, for fragments and archive entries alike.

## Consumer note
In products that record changes as fragments, the PR reviewer now checks that every item a fragment's `closes:` list names is really closed.
