---
schema: 1
type: fix
scope: merged-plan-chunk-state
date: 2026-10-25
title: a merged plan's chunks stay done after the merge deletes its branch
closes: [brookstalley/prawduct#1065]
---
`plan_status.chunk_states` placed a review fact's anchor commit only on the plan's claimed
`branch:` and `working-branches:`. `/prawduct:pr merge` deletes the claimed branch, so from that
moment every chunk of a merged plan read `open` ("its commit is not on `feature/x`") on the same
output whose lifecycle line said merged-unreleased with the anchor in the base's history. The
briefing's staleness scan then told the operator to "fix the frontmatter, or create the branch"
for plans that `plan check-claims` graded release-pending, and the two instruments disagreed on
one plan. Seen on this repo's two retained plans and on a consumer repo the day it merged one.

The probe now asks where the claimed branches are, once per call and only after a probe by name
refused: a branch present only on a remote is probed by its tracking ref, and a plan whose claimed
branches are all gone is probed against its base (the plan's `base:`, else the repo's integration
base). On the base path a review anchored at its own `base_commit` certifies nothing, the rule the
lifecycle observer already applies to the merge question. The exact-name rule for "is this ref
that branch" moved to `gitstate.ref_is_branch`, so the lifecycle observer and the chunk-state
probe agree on whether a branch is present. The common path costs what it did: one `merge-base`
per anchor.

## Consumer note
- A build plan whose branch the merge deleted now reads its chunks as done from the base's
  history. The session-start staleness line "has chunks left and declares `branch: X`, which is
  not a branch in this repo" stops firing for such a plan once its chunks are certified; it
  still fires for a merged plan with a chunk no review certified, which `lifecycle-repair`
  names.
- `plan status` reason text for an unplaceable commit changes shape when the branch is gone:
  "its commit is not on `develop` (`feature/x` is on no local or remote branch, so the base it
  merged into is asked)".
