---
schema: 1
type: feature
scope: round-tally-at-next-action
date: 2026-11-18
title: a review's next action now says how many rounds the branch has already bought
closes: [brookstalley/prawduct#815]
---
The question "what will round N+1 do differently?" reached the builder only from the coverage gate,
after the round had been bought. Below the round budget, nothing told the builder how many rounds
the branch had already bought at the moment they decided to fix, and verify rounds were never shown
a count. Consolidation now counts the branch's rounds once, with the same lineage walk the gate uses
(`coverage.count_branch_rounds`) over the store it just wrote this review into. It renders the
count as `coverage.branch_rounds_clause` and passes it into `next_action_line` the way the round
price is passed. The cache's `next_action` and the relayed `NEXT-ACTION:` line therefore say the
same thing.

The clause appears from the second recorded round, which is when round 3 is being decided. It sits
on the blocking arm and on the fix tail, after the price. It is not added to a clean close or under
a fix that rides the plan's next review. It is also absent on an empty span (a trunk-shaped repo),
where no round can be attributed. When the count cannot be derived, the clause says so.

## Consumer note
After a branch's second Critic round, the review's next action ends with "This branch has recorded
N review rounds since the merge-base …; name what round N+1 will do differently before you spend
it." The count includes the review just recorded, so it matches what the coverage gate prints.
