---
schema: 1
type: fix
scope: free-interval-warnings
date: 2026-11-23
title: a warning no longer keeps a free interval dispatchable
closes: []
---
`critic-begin` refuses a review over an interval with no judgeable file, as the coverage gate already
composes it, unless a finding the review could resolve is still open. That exception exists so a
`blocked` verdict is never wedged: its only remedy is a verify-resolutions pass. It counted warnings
too, so a records-only fix after a review whose open findings were all warnings dispatched a round the
gate did not need. The gate counts no warning, so a warning cannot wedge it, and a warning fixed over a
free interval is recorded with `disposition --fixed --paths` at no review cost. The exception now counts
blocking findings only (owner ruling 2026-11-23, decision 6 of `documentation/issues/1222-1223-design.md`).
Warnings still count as something to verify, so a warning fixed in judgeable code is reviewed as before.

## Consumer note
After a review with only warnings open, a fix confined to `.prawduct/` or non-governance prose now gets
exit 3 (no review needed) from `/prawduct:critic verify-resolutions` instead of a review round. Record the
fixed warnings with `prawduct-hook disposition --fixed --paths`.
