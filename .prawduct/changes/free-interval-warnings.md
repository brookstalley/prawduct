---
schema: 1
type: fix
scope: free-interval-warnings
date: 2026-11-23
title: only a blocker the gate counts keeps a free interval dispatchable
closes: []
---
`critic-begin` refuses a review over an interval with no judgeable file, because the coverage gate
already composes it, unless something the review could resolve is still open. That exception exists so a
`blocked` verdict is never wedged: its only remedy is a verify-resolutions pass. It counted the prior
review's warnings and its raw blocker count, so it dispatched rounds the gate did not need: after a
review whose open findings were all warnings, and after one whose blocker had since been waived or
resolved. It now counts one thing, the blockers the gate still counts at the prior review's tree (that
review's own and an earlier round's), for both the free-interval refusal and the nothing-to-verify
answer. A warning cannot wedge the gate, because the gate counts none (owner ruling 2026-11-23, decision
6 of `documentation/issues/1222-1223-design.md`). A warning fixed in judgeable code is still reviewed,
because that delta is not free. A warning fixed over a free interval is recorded with
`prawduct-hook disposition <review-id> <fid> --fixed <path>[,<path>...]` at no review cost, and the
refusal now names the prior review and its warnings so the builder learns that route where it applies.

## Consumer note
After a review whose only open findings are warnings, or whose blockers the gate no longer counts, a fix
confined to `.prawduct/` or non-governance prose now gets exit 3 (no review needed) from
`/prawduct:critic verify-resolutions` instead of a review round. The exit-3 output lists the open
warnings; record each fix with `prawduct-hook disposition <review-id> <fid> --fixed <path>[,<path>...]`,
or accept it with `--accept "<reason>"`.
