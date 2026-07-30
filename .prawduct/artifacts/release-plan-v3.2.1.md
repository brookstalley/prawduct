# Release Plan — v3.2.1, Whole-Develop Promotion

**Status:** **NOT YET SHIPPED — plan authored 2026-07-29.** Phase 0 of
`runbooks/cut-and-publish-a-plugin-release.md` reads the classification table below.

**Version:** v3.2.1 — **patch**, and the call is recorded rather than reflexive because the tier is
genuinely close. The ratified norm (`operational-spec.md` `## Direction`, 2026-07-17) is
*"Versioning is conservative: a small feature is a patch bump, not a minor-per-feature."* Against
that, this bundle is one small additive capability plus fixes. But the runbook's **unratified**
precedent reads a *substantial* new capability as a minor and warns against treating "not a major" as
"therefore a patch" — and a new fact kind with two subcommands and a methodology change is arguably
substantial.

**Maintainer decision, 2026-07-29: patch (+0.0.1), framed as a critical consumer fix.** The tension
was raised before cutting and the maintainer set the number; recorded here because the norm requires a
departure-or-close-call in either direction to be a recorded decision rather than a reflex.

Supporting the patch reading: no gate semantics change, and no persisted format changes. The new fact
kind is additive, and the store's `KNOWN_KINDS` filter already makes unknown kinds coexist-but-never-
satisfy by construction, so a 3.2.0 reader meeting a 3.2.1-written store skips what it does not know
instead of failing. No subsystem goes live.

## Release classification

| scope | disposition | blocker |
|---|---|---|
| record-mechanization | ships |  |

One release-pending scope, and it is this bundle — `check-releasability --release v3.2.1` named it.

## What ships

**The consumer-facing fixes — why this is worth cutting rather than waiting.** Both reach every
installed repo through the Critic's review data plane:

1. **The coordinator's three reviewers were never told to run concurrently.** The instruction never
   existed in any version; the fan-out rode an ambient harness default that varies between sessions
   (this repo's own run fanned out in a 67-second spread while other sessions saw serial dispatch
   consistently in the same period). Consumers whose sessions land on serial behaviour pay the
   coordinator pattern's full cost — three agents, three context loads, a consolidation step — for a
   third of the benefit, on every `final`/`cumulative` review at 5+ changed files. Now stated in both
   dispatch surfaces, with a mutation-proved guardrail so it cannot silently revert.

2. **The governance ledger could anchor one review twice.** `ledger_append` had no idempotency key and
   no dedupe while `review-stats` counts its lines, so a review could be counted twice in the
   instrument review proportionality is judged by. It reproduced live. `review_event_exists` now
   probes before appending: **replay is closed; overlap is narrowed, not closed** — the probe is
   read-then-write with no lock, and mandating concurrent dispatch made overlap more reachable. Stated
   precisely so a maintainer who sees it recur looks for the lock rather than a third caller.
   Historical impact: of the 143 `review.*` events carrying a `fact_id`, 142 are distinct — one
   surplus (`rev-20260729T233201Z-d91acd9e`), still on disk. A further 140 events carry no `fact_id`
   — 100 `review.critic` events predating the field, plus 40 `review.pr` events whose payload has no
   such field at all, so that blind spot is permanent and grows with every PR review. The follow-up
   item's trigger (CRT-8L3Q) is therefore keyed on *duplicated ids*, never on a
   total-minus-distinct subtraction.

**Also shipping — additive, and inert unless invoked.** The `disposition` fact kind plus
`prawduct-hook disposition` / `render-dispositions`: a review's ACCEPT/FILE answers become facts so its
census is derived rather than hand-written, including the count nothing measured before — findings
still undispositioned. And advisory duplicate-finding detection, which reports likely double-counted
findings and never drops or merges one.

## Promotion shape

`K = 0` withheld scopes → **whole-develop promotion** (Phase 2's default shape).

## Recorded deviations

**Phase 1 cannot check out `develop` in this checkout.** `develop` is held by another worktree
(`wt-prawduct-backlog`) whose session owns it. Release prep therefore runs in a fresh temporary
worktree off `origin/develop` and lands with `git push origin HEAD:develop`, which fast-forwards
because the prep commit is a descendant of `origin/develop`. Nothing in the other worktree is read or
written; its local ref simply becomes behind.

**Phase 1 step 11 (`active_build_plan: null`) is NOT performed — deviation, with reasoning.** The
runbook nulls the pointer unconditionally, which is right when a release retires a completed plan.
This release ships **Chunk 01 of 5**; Chunks 02–05 are unbuilt and the plan file is retained. Nulling
the pointer would strand the next session with no resume target, and `/prawduct:pr`'s own gitflow rule
says the opposite for this case ("**RETAIN** both the plan file and the `active_build_plan` pointer"
when the base is `develop`). The runbook step has no conditional for a mid-plan release — a genuine
gap in it, recorded here rather than silently followed or silently ignored. A "consider deleting idle
plan" advisory may surface until the plan completes; that is expected.

**Phase 2 step 14's `git checkout main` is skipped, exactly as v3.2.0 recorded.** The promotion uses a
detached temporary worktree at `origin/main` with `read-tree --reset -u origin/develop`, then
`git push origin HEAD:main` — identical commit shape (single parent, `develop`'s tree), and it does not
mutate a live checkout mid-promotion. Two releases have now needed this branch; the runbook still lacks
it.

## Verification evidence

| check | state at 2026-07-29 |
|---|---|
| test suite | 2913 passed / 0 failed / 7 skipped |
| `regen-views --check` | passes |
| `check-cumulative-critic` | satisfied on the Chunk 01 bundle (3 review facts, 0 unresolved blocking); re-confirmed at merge |
| `check-releasability --release v3.2.1` | blocked on this file's absence — re-run after it lands |
| Critic coverage | `rev-20260729T230420Z-71b7f129` (final, 25 findings → 17 fixed / 8 accepted / 0 undispositioned), then two `verify-resolutions` passes |
