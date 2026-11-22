---
schema: 1
type: docs
scope: gate-review-concurrency
date: 2026-11-18
title: building.md now says the test gate and a Critic review may run together, and where they reconcile
closes: [brookstalley/prawduct#678]
---
Nothing said whether the suite and a review could overlap, so builders ran them one after the
other. The open question was whether recording the suite during a live review voids the review,
because `critic-begin` snapshots the working tree. It does not. The recorder writes only
`.prawduct/.test-evidence.json`, the test report and its scope record, which are session files that
consolidation exempts by path, plus the evidence store under the git directory. A reviewer that
reads `test-status` during the run sees `running:`, which the protocol treats as never a finding.

`building.md` § The Critic now says to start `test-evidence record` first and then dispatch. Two
orderings still hold. A suite that leaves behind any file git does not ignore moves the reviewed
tree, and consolidation refuses the review. `verify-resolutions` refuses to dispatch while a record
is in flight, so it runs after the record. Both reconcile at `/prawduct:pr` Steps 1-2 (`test-status`,
then the coverage gate), not inside the review.

## Consumer note
none: guidance on ordering; neither the gate nor the review changed
