---
schema: 1
type: fix
scope: branch-claimed-plan-no-fallback
date: 2026-10-25
title: a plan declaring branch governs that branch only, never another branch through the fallback
---
`core.resolve_build_plan_path` answers with the plan claiming the checked-out branch, else the
`active_build_plan` pointer, else the conventional `artifacts/build-plan.md`. The two fallbacks
never asked whether their plan declared a `branch:` of its own. So a finished plan retained live
on gitflow until its release went back into force on every branch no plan claimed: the Stop
hook's gates armed against it, the briefing nagged to archive it, and Critic reviews and ledger
events recorded its scope. The one observed: a review of `fix/plan-archive-scope-name` was
recorded in the ledger as `scope=review-stats-dispositions`. Clearing the pointer, the prescribed
remedy, could not end it when the plan sat at the conventional path.

The resolver now returns `None` when the fallback plan's `branch:` names a branch other than the
one checked out. On a detached HEAD or outside a work tree the fallback stands as before, because
there is nothing to compare. Every caller treats `None` as "no active plan". The
`pointer-claims-other` diagnosis reads the refused candidate through the new
`core.fallback_plan_path`. The PR skill's Merge Flow, the planning guide, the release process and
the PR review protocol no longer prescribe clearing the pointer for a branch-declaring plan.

## Consumer note
- A build plan whose frontmatter declares `branch: X` is no longer the active plan on any other
  branch, even when `active_build_plan` names it or it lives at `artifacts/build-plan.md`. A plan
  declaring no `branch:` resolves exactly as before.
- After a branch-declaring plan merges on gitflow there is no pointer step: the plan stays live
  and inactive until the release archives it.
