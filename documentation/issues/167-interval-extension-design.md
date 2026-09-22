# #167 — let the next review cover a non-blocking fix, instead of buying a round for it

**Status:** design, awaiting owner approval (2026-09-22). **Parent:** #167 (`stage: design`);
its withdrawn build is recorded in `.prawduct/artifacts/archive/build-plan-review-convergence.md`
§ "Chunk 02 — WITHDRAWN after review". Data: the 2026-09-22 comment on #724.

## The problem, measured

Across the fleet's evidence stores, 242 `verify-resolutions` rounds ran between 2026-09-13 and
2026-09-22 (unique fact ids; a store can hold a fact twice, and its reader dedupes). Classified by the review each one followed:

| Why the round ran | Rounds | Found a new blocker |
|---|---|---|
| A — prior review left a BLOCKING finding (required) | 92 | 27 |
| B — prior review had only warnings/notes | 69 | 10 |
| C — prior review was clean; the round covered later edits | 81 | 7 |

B and C are 150 rounds the protocol never required. Of those, **63 were followed on the same
branch by another full review** (`chunk`, `final` or `cumulative`), and **56 by a `cumulative`
that re-read the same edits** anyway. At the fleet's median verify duration that is roughly two to
four hours of review in nine days. Both counts come from the scripts in the
#724 comment of 2026-09-22 plus its correction, re-runnable against any clone set.

B and C rounds are not worthless: 17 of the 150 (about one in nine) found a blocker, most likely one introduced
by the fix itself. Refusing them loses those catches unless something else reads the same edits.

## What the previous attempt teaches

#167's Chunk 02 refused a `verify-resolutions` dispatch when the delta looked like fix churn. It
was withdrawn on 2026-09-20 for two reasons that bind this design:

1. **A refusal must not leave a gap only a costlier route can close.** The refused delta stayed
   uncovered, so the PR gate demanded a `cumulative` (median 720s) where the refused verify cost
   300s.
2. **Refusing needs content-level evidence that the delta is churn**, and the only evidence
   available is file-level, which is advisory strength.

## The design: extend the next review's interval, don't refuse this one

The obligation to cover a non-blocking fix is real. What is avoidable is paying for it in its own
round. So the design refuses nothing. It moves the fix delta into a review that is going to run
anyway, **by starting that review's interval at the last reviewed tree instead of at HEAD.**

Coverage composes by tree (`coverage_algebra`, D6): a `review` fact contributes the edge
`base_tree → head_tree`. A `chunk` review whose base is the last reviewed tree `T` and whose head is
the working tree therefore spans the committed fix *and* the new chunk in one edge. No gap is left,
so nothing downstream has to buy a `cumulative` to close one, which is the trap that killed Chunk 02.

No refusal means no authority question: the fix delta is still reviewed, by a reviewer reading its
content, one review later.

### Three changes

**1. `critic-begin`: `chunk` and `final` start at the covered frontier.** Today their base is the
HEAD tree. New rule: walk back from HEAD along first-parent history to the newest commit whose tree
composition reaches from the merge-base with zero unresolved blockers — the *covered frontier*. If
the frontier is HEAD, nothing changes. If it is older, and every review fact on the path has zero
unresolved blockers, the base is the frontier's tree and the review spans frontier → working tree.
The manifest and the review fact record `base_extended_from` (the frontier tree, or null), so the
rounds this saves can be counted — this is the change's observable yield.

With unresolved blockers on the path, nothing extends: `verify-resolutions` stays the only route,
because it alone records resolution facts.

**2. The Stop gate defers instead of blocking, when a later review is owed and will extend.** Today
a session that commits a non-blocking fix and ends is blocked until the delta is covered, and that
block is what buys most B/C rounds. New rule: when the session's changes are `uncovered` (not
`blocked`), the path to the frontier carries zero unresolved blockers, and the gate plan still has
an unticked chunk, the gate prints an advisory instead of a blocker: the next chunk's review
extends over this delta. This is the same shape as the short-plan deferral that already exists
(`critic_mode.short_plan_deferral`, `DEFERRED_REVIEW_TOKEN`), with a second trigger. At the last
chunk it blocks exactly as now, because no later review is owed to carry the delta.

**3. Mode inference and the review close stop recommending the round.** After a review with zero
blocking and with chunks still to build, `infer-critic-mode` answers `deferred` for a
committed fix delta (the existing short-plan answer) instead of `verify-resolutions`.
The NEXT-ACTION the close prints leads with "commit and carry on; the next chunk's review extends
over this fix", instead of listing that as a third route after two others. `cost-of-commit` prices
such a commit as riding the next review, not as costing a round.

### What does not change

- The PR gate (`check-cumulative-critic`) is untouched and stays authoritative. If an extended
  review never happens — the plan is abandoned, or an explicit mode skips it — the boundary finds
  the gap and says so, as today.
- BLOCKING findings: unchanged. They still need `verify-resolutions` or a spanning review.
- Short plans (three chunks or fewer) already defer every per-chunk review to the boundary
  `cumulative`. This design matters for longer plans, where per-chunk review is the rule.

## Expected yield and its limits

- **Removes** B/C rounds that run mid-plan with a later review still owed: up to the 63 above.
- **Keeps** their catches: the extended review reads the same edits, one review later.
- **Does not touch** B/C rounds that are the last coverage before a PR (87 of 150). Each is the
  PR gate's cheapest close, and deferring it would only move it.
- **Costs** a somewhat larger diff for the next chunk reviewer: the fix delta, typically a few
  lines.

## Risks and open questions

A boundary investigation (2026-09-22) read every consumer that could assume a `chunk`/`final`
review starts at HEAD. No validator requires `base_commit == commit_reviewed`, so the manifest and
fact accept an older base as they stand. Keep `commit_reviewed` at the dispatch commit:
`consolidate` matches each partial against it. Set `base_commit` from the prior fact's
`head_commit`, never its `dispatch_commit`, because for a dirty-tree review that commit's tree is
not its `base_tree`.

**One consumer breaks, and fixing it is part of Chunk 1.** The Stop gate composes coverage from
the *session's* base tree to the working tree. When the fix was committed in an earlier session,
the session starts at H (the unreviewed fix commit), and an extended edge `T → W` has no path from
H. The gate would block. `cost-of-commit` (`gates.commit_coverage`) asks the same kind of question
from HEAD and would over-price the next commit in the same way.

The fix is one additive condition on both: **also accept coverage composing from the branch's
merge-base to the working tree.** That is sound on its own terms. If merge-base → W composes, every
line of W either equals a tree already covered or was read by the extended review, so W is vouched
for. The condition only relaxes: nothing that passes today stops passing. It is the PR gate's own
question, asked earlier.

**Answers that change, and are meant to:**

- Mode inference redirects a clean tree to `cumulative` on the assumption that `chunk`/`final`
  have an empty interval there (`_clean_tree_redirect`, rule 4). Under this design, a clean tree
  mid-plan after a non-blocking fix answers `deferred`, and the extension happens at the next
  chunk's review, which is dirty by definition. The redirect stays right at the last chunk.
- `_widened_fallback_mode` says `final` "cannot see committed work" and so recommends `cumulative`.
  With an extended base it can see it. Update the logic and its strings together.
- `critic-begin`'s empty-diff and free-interval refusals fire less often, and a `final` roster can
  escalate to the coordinator on a larger file count. Record-lint measures from the older base.
  All intended; each needs a test that pins the new answer.
- `diagnose_fix_churn` has only ever read `verify-resolutions` and `cumulative` facts as anchors. A
  chunk fact with an extended base now has a `head_commit` and becomes a candidate, so the churn
  logic needs a test on that input.
- Review-stats groups `chunk` durations by mode, so chunk medians will start to mix in wider
  intervals. The yield field (`base_extended_from`) lets a reader separate them.

**Prose that becomes false** (the cascade to carry in the docs chunk): the `chunk`/`final` interval
description in `review-cycle.md` (the interval table row, and the lines stating what `chunk`
covers), `SKILL.md` (the "uncommitted diff" descriptions and the demotion-property sentence),
`review-protocol.md` (`final`: the uncommitted diff), and the docstrings and comments in
`critic_consolidate.py` (`stage_of`, `begin_review`, the empty-diff refusal text) and
`critic_mode.py` (module docstring, rule-4 comment, `_clean_tree_redirect`). Several of these files
sit under reviewer-payload token ceilings, so reword in place rather than add.

**Open questions for the owner:**

1. Should the extension be limited to deltas whose judgeable files a prior review named (fix churn)?
   Recommendation: no. The extension reviews the content, so it needs no churn evidence, and
   limiting it would leave committed but unreviewed chunk work paying for its own cumulative.
2. Should `final` extend as well as `chunk`? Recommendation: yes. The last chunk's `final` is the
   natural carrier for a fix made after the previous chunk's review.

## Norms this engages

- **Authority fails closed; advice fails soft** — conforms: nothing that decides a verdict weakens;
  the Stop gate's block becomes advice only where a later review is owed, and the PR gate still
  decides.
- **Proportionality ratchets both ways** — conforms: the change names its yield
  (`base_extended_from` on each fact; the deferral token on each advisory).
- **Review rigor is stage-keyed** — to be dispositioned in the build plan: an extended `chunk`
  review covers a committed fix delta at the inner stage, which is what `verify-resolutions`
  already does for the same delta today.
- **Review wall-clock is P0** — this is its purpose.

## Proposed build shape

Three chunks, one plan, `cumulative-final`:
1. The interval extension in `critic-begin`, with the fact field, **plus the merge-base condition
   on the Stop gate's coverage question and on `cost-of-commit`**. Without that condition the
   extension blocks the Stop gate, so the two cannot ship apart. A thin slice: prove, end to end,
   that a `chunk` fact with an older base closes a real gap for both gates.
2. The Stop gate advisory, the `deferred` inference answer, and the NEXT-ACTION and
   `cost-of-commit` wording.
3. The docs: `review-cycle.md`, the Critic `SKILL.md`, `building.md`'s "Resolve findings". Watch the
   token ceilings on these.
