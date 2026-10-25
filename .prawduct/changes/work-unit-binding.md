---
schema: 1
type: governance
scope: work-unit-binding
date: 2026-10-24
closes: [brookstalley/prawduct#1007]
title: a plan claims its branch, one resolver answers bound, unbound or broken, and no fallback borrows a plan for a checkout that never claimed it
---
Which plan governs a checkout had four answers: a plan claiming the branch, the `active_build_plan`
pointer, the conventional `artifacts/build-plan.md`, and a branch-name match against plan scopes.
Each consumer walked them its own way, so a gate, a Critic review and a ledger event could name
different plans for one checkout, and a finished plan could come back into force on a branch that
never claimed it.

`work_unit.resolve()` is now the only walker, and every consumer takes its `Binding`:

- A plan claims a branch with `branch:` and may list `working-branches:`, branches that merge into
  its branch and bind to it. At most one live plan claims a checkout.
- The answer is **bound** (one claimant), **unbound** (none) or **broken** (two claimants, or a
  plan-shaped file that cannot be read). Unbound is normal and borrows no plan. A broken binding
  fails closed: it blocks what bound would have blocked and advises what it would have advised.
- A harness scratch worktree is unbound by construction, and so is a detached HEAD.
- Reviews, ledger events and gate decisions record the unit they were about, or none. Nothing
  substitutes a scope inferred from the branch name.

`prawduct-hook plan new <scope>` mints the plan and its change fragment together, so the scope is
written to both in one act. `prawduct-hook plan bind <path> --branch <name>` claims a branch for an
existing plan. `prawduct-hook plan resolve` prints the Binding for the current checkout.

Where the scope is written is validated. A fragment whose scope a plan spells differently is refused
at the place it is read, rather than first noticed by the release check. A backlog item's
`closed-by` takes `scope:<slug>`, a PR or a release tag, and refuses an unknown scope or a branch
name; a bare slug that is a known scope is accepted and stored as `scope:<slug>`.

## Consumer note
- The `active_build_plan` pointer and the `artifacts/build-plan.md` default path are deprecated.
  They are served only in a legacy window, for a repo in which no live plan declares `branch:`, and
  only for a plan that itself declares none. The `plan-unbound-legacy` advisory fires there and names
  the migration: `prawduct-hook plan bind <path> --branch <name>`.
- The window closes no earlier than two minor releases later, and only after
  `plan-unbound-legacy` has fired on no known consumer for a release.
- A detached HEAD now binds nothing: a checkout that resolved a plan by branch name or pointer
  before resolves to none, and gates keyed to the plan do not arm there.
- `closed-by` is validated: a branch name or an unknown `scope:` value is refused where it is written.
- A fragment whose scope near-misses a plan's is refused where it is read.
- Base-branch resolution for the gates, `check-cumulative-critic` and the PR payload consults the
  bound plan's `base:` first (then the repo's `base_branch:`, then the remote default): a stacked
  branch whose plan declares `base: feature/A` reviews against `feature/A`, not the integration
  branch. A plan declaring no `base:` resolves exactly as before.
- `verify-chunk-refs` with a chunk named but no plan bound, or a broken binding, exits 1
  `cannot-verify` instead of a false 0; with no chunk named on an unbound checkout it prints `ok`
  with the reason.
- `critic-begin` records `scope_chosen_by` as one of `binding`, `legacy-pointer`, `legacy-default`,
  `explicit-args` or `none`; `branch-name` and `not-resolved` are no longer written, and history
  that carries them still reads. A consumer filtering on `binding` alone misses every
  legacy-window and every unbound review.
- `prawduct-hook plan resolve --json` carries `case` and `base` beside the Binding's other keys. The
  `core.resolve_build_plan_path` and `buildplan_refs.resolve_branch_plan` shims are removed, not
  kept for a release.
