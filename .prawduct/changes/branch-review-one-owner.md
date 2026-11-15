---
schema: 1
type: fix
scope: branch-review-one-owner
date: 2026-11-15
title: The review deferral and the session briefing now pick this branch's review the way the verify dispatch does
closes: [brookstalley/prawduct#1179, brookstalley/prawduct#1180]
---
"Which review is this branch's" already had one answer for the findings cache, the
`verify-resolutions` dispatch and mode inference: `critic_consolidate.select_branch_review`, which
places each review by the commit it anchors on along the branch. Two readers still answered it on
their own. Both now ask the same function.

**The deferral stands on the review that covers this branch's lineage (#1180).** Two checks
choose a review and then relax on it. The interval-extension deferral lets a fix wait for a later
chunk's review. The boundary check treats the plan's `cumulative` as already run. Both took the
newest review whose recorded branch NAME matched the checked-out branch. That missed a delegate
branch's review merged into this one and a review recorded with no branch name (a pre-3.8 fact, a
detached HEAD). It also picked up an old review when a branch name was reused on another lineage,
and on that review it could defer a review that was still owed. `critic_mode._newest_branch_review`
now asks `critic_consolidate.settled_branch_review`, which returns the owner's answer only when that
answer settles the question. A review past the merge base belongs to this branch whatever name it
carries. At the merge base, which every sibling branch shares, only a review recorded on this
branch counts. The owner keeps a sibling's merge-base review as a fallback verify anchor, but that
review does not show this lineage was reviewed. When no branch range resolves, no review anchors
on it, or only that fallback answers, the result is "no review" and the review stays owed.

**The session briefing summarizes this branch's review (#1179).** The handoff's `## Critic
Findings` section read `.prawduct/.critic-findings.json` as written. That cache is a single slot
and survives a branch switch, so after a switch the handoff showed the other branch's review. When
the cached record names a review fact, the briefing now asks `verify_anchor`, the read-only
question the verify dispatch asks. If the answer is a different review, the briefing shows that
review, rendered the way the cache writer renders it (`branch_review_record`, pinned against
`derive_branch_cache`). It names the review it shows and the review the cache holds. When no
review of this branch can be confirmed, it shows the record as written and says it may be another
branch's. The briefing writes nothing; the dispatch and ingest still re-point the cache.

Tests: `tests/test_review_interval_extension.py`. Hand-built facts there now anchor on a stubbed
branch range instead of carrying only a branch name, and new cases cover a reused name, a merged
delegate, a nameless fact, the merge base and no range, at the deferral and at the boundary.
`tests/test_briefing_branch_review.py` covers the briefing on real git.
Docs: `review-cycle.md`'s findings-cache paragraph.

## Consumer note
After you switch branches, the session handoff's Critic findings are the checked-out branch's own
review. When the findings cache still holds another branch's review, the handoff names both.
`/prawduct:critic` may now answer `deferred` for a fix after a review that a merged delegate branch
recorded. It no longer defers on a review recorded under a reused branch name on another lineage,
or on one the branch lost to a rebase. In those cases it asks for the review.
