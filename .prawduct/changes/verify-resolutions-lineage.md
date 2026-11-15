---
schema: 1
type: fix
scope: verify-resolutions-lineage
date: 2026-11-15
title: verify-resolutions finds this branch's review after a branch switch, and refuses up front on a stale or red suite
closes: [brookstalley/prawduct#1150, brookstalley/prawduct#1116, brookstalley/prawduct#724]
---
Three fixes to `critic-begin --mode verify-resolutions` and the findings cache it reads.

**Why the first two broke.** `.prawduct/.critic-findings.json` holds one review: whichever one this
clone last consolidated or ingested, on any branch. Three places asked it "which review is this
branch's?" and got different answers. The ingest path chose by commit range only. So at the merge
base, which every sibling branch shares, it could not tell this branch's review from a sibling's
(#1116). The verify dispatch did not choose at all. It trusted the cached pointer, refused one from
another lineage, and never looked for the review this branch did have (#1150). Mode inference
(rules 1 and 1b of `infer-critic-mode`) read the cache the same way the dispatch did. So after a
branch switch, a bare `/prawduct:critic` never suggested verify-resolutions. It answered `chunk`, or
a full `cumulative` after a committed fix.

**One owner now.** `critic_consolidate.select_branch_review` makes the choice. It is pure and
writes nothing. `derive_branch_cache` renders its answer into the cache. `verify_anchor` asks it
read-only for the verify dispatch and for mode inference:

- **The merge base (#1116).** Among reviews anchored at the merge base, it prefers one whose
  `actor.branch` is the checked-out branch. Further along the branch, a commit belongs to the
  branch, so depth and then time decide, as before. The preference never excludes anything. With
  no review of its own there, a branch still gets the sibling's review, so a renamed branch or a
  review older than `actor.branch` keeps its anchor.
- **The verify dispatch (#1150).** If the cached review is off this lineage, or is a sibling's
  review at the shared merge base, the dispatch asks the owner. The owner re-points the cache, and
  the pass anchors on this branch's newest review. A `PRAWDUCT NOTE:` names both reviews. The pass
  refuses (exit 1, demote) only when the branch has no review, and the refusal still leads with
  the old "another lineage" reason. A cached review that is this branch's is used as before, with
  no extra git calls.
- **Mode inference.** Rules 1 and 1b now judge the review the dispatch would anchor to
  (`critic_mode._verify_prior_record`). When the cache names another branch's review, they judge
  this branch's newest review, rendered the way the dispatch would write it. Where the dispatch
  would refuse, the rules do not fire. A pre-store cache with no `fact_id` is read as written, as
  before. Inference never writes the cache. It is a question asked before a dispatch that may not
  follow (it can answer `deferred` or another mode), and writing would change what the briefing
  shows for a review nobody ran. When verify-resolutions does dispatch, the dispatch writes the
  same answer, because it chooses through the same function.

**Stale or red test evidence (#724).** A verify-resolutions dispatch now asks
`gates.tests_are_current`, the same verdict `prawduct-hook test-status` prints, right after the
in-flight guard and before it derives anything. If saved evidence exists and is stale, failing or
degraded, the dispatch refuses with **exit 7** and prints the verdict and the remedy: run the
suite, then dispatch the same mode again, never a demoted one. It writes no manifest and sets no
marker. It records one `critic-dispatch-stale-evidence` guard-refusal fact, with `reason` from the
closed set `failing` | `degraded` | `not-current` and the verdict's text as `verdict`. If there is
no evidence at all (no `.test-evidence.json` and no whole-suite `test-run` fact in the store), the
dispatch does not refuse, so a product with no test suite can still clear a BLOCKING finding.
`--force` dispatches anyway. `chunk`, `final` and `cumulative` are unchanged. Before this, a
verify round (median about 300s) could spend its whole run reporting a stale suite.

**Exit 7, not 5.** The issue asked for exit 5. But the Error Model in `api-contract.md` records 5
as withdrawn: #167 held it on `develop` until its revert, and the contract left it "unclaimed
rather than given a new meaning". So this refusal takes 7. The skill's exit table, the
`cmd_critic_begin` docstring and the contract's sentinel list all name 7. "verify-resolutions is
never refused" now reads "never refused by the budget" everywhere it appeared (`SKILL.md`,
`begin_review`'s docstring, `docs/project-state-keys.md`, `api-contract.md`).

`tests/test_verify_resolutions_lineage.py` covers the branch switch through the CLI, the merge-base
preference (and that it applies only at the merge base), the preference not excluding a sibling,
the dispatch's re-anchor, and bare inference after a switch. That means rule 1 on an uncommitted
fix, rule 1b on a committed fix after the branch's own `cumulative`, the dispatch the inferred
mode makes, a control where new work outside the review does not infer verify, and inference
leaving the cache unwritten. `tests/test_critic_dispatch_stale_evidence.py` covers each refusal
shape, absent evidence, current evidence, `--force`, the in-flight guard answering first, the
other three modes, and the guard fact's slug. Each fix was seen to fail with its guard removed.
The Critic `SKILL.md` and `review-cycle.md` budgets were raised by declaration (+38 and +69 tokens).

## Consumer note
After you switch branches, `/prawduct:critic verify-resolutions` now anchors on the checked-out
branch's own newest review, not the review the findings cache last named. A bare
`/prawduct:critic` also suggests verify-resolutions there when you are fixing that review's
findings. It also refuses up front
(exit 7) when your saved test evidence is stale or failing. Run your test suite, then run
verify-resolutions again. A repo with no test evidence at all is not affected.
