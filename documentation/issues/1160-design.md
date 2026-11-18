# Issue #1160 — critic: stranded blocker can't clear after budget is spent: Design

`status: draft · stage: design · area: critic · added: 2026-11-16 · source: scheduled design pass ·
issue: https://github.com/brookstalley/prawduct/issues/1160`

Related: #711 (the same stranding, one hop earlier; its fix is the mechanism this design widens),
#847 (a class finding closed at the instance it named), #1170 (one defect listed as several
findings, which is how a verify pass comes to raise B instead of resolving A).

Everything under "What the code does today" was read from `develop` at `36827191`. None of it was
run: the reported sequence was traced through the code, not reproduced. The first build step is a
failing test that reproduces it.

## Summary

A `verify-resolutions` pass is only ever shown the unresolved blockers of the **one review it
anchors to**. A blocker that survives a pass which also raises a finding of its own therefore drops
out of every later pass's brief, although it still blocks both gates. The gate then sends the
builder to a `cumulative`, and the round budget refuses that review.

The fix is to widen one set. The blockers a verify pass must answer become **every unresolved
blocker on the chain of reviews its anchor stands on**, not the anchor's alone. One function owns
that set, and the four places that ask "what is still open behind this pass" read it. No new
command, no new fact kind, no budget exemption, and no new way to weaken a gate: consolidation
already accepts a resolution for any recorded finding.

## What the code does today

The reported sequence, by the function that decides each step.

1. **`cumulative` records blocker A.** Nothing unusual.
2. **Verify pass 1 leaves A open and raises B.** `critic_consolidate.carried_blocking` finds the
   anchor by one structural hop (the review whose `head_tree` is this pass's `base_tree`) and
   returns A. The close therefore says NOT DONE and tells the builder to fix this pass's findings,
   re-run `verify-resolutions`, and "give each finding above its own entry".
3. **That instruction cannot be followed.** Verify pass 2 anchors on pass 1. Its roll-call
   (`account_for_prior_blockers_directive`) is built from the same one-hop `carried_blocking`, so it
   lists B and not A. The reviewer is never shown A again. This is the defect: the remedy the #711
   fix prints is unreachable whenever the pass that carries a blocker also raises one.
4. **The gate keeps reading A.** `coverage_algebra._unresolved_at_nodes` reports every unresolved
   blocker at a tree on the composed path, and marks one `superseded` when its review is not the
   newest on the path (`_verify_anchor_id`). `gates.blocking_remedy_lines` then prints "no
   verify-resolutions pass will name again … run /prawduct:critic cumulative".
5. **Each route then refuses, each for a locally sound reason.**
   - `cumulative`: `_round_budget_verdict` counts six full rounds in scope and exits 4.
   - `verify-resolutions`: `begin_review` computes `pending_actionable` from the **anchor's
     recorded counts** (`prior_body["counts"]`), which are zero for the clean pass 3. With an empty
     delta that is "no review needed", exit 3.
   - `disposition --fixed`: `dispositions.record` refuses judgeable paths, because a FIXED on them
     would record a review nobody ran. Its message says to run `verify-resolutions`.

Two facts make the fix small.

- **The write side already allows it.** `critic-consolidate` checks a reviewer's resolution against
  `_known_findings_index(store)`: any `(review_id, fid)` the store holds, not the anchor's. A verify
  pass that named A would have its resolution fact written today. What is missing is only that the
  reviewer is told about A and that the dispatch is not refused as a no-op.
- **The chain walk already exists.** `critic_mode.review_chain` walks `base_tree → head_tree` links
  to the end, and `critic_mode._open_blocker_on_chain` already asks "is any blocker open anywhere on
  this chain". Its docstring states the fact this design relies on: a verify pass "does not copy
  forward the ones it leaves open, so the newest review can be clean while one it stands on is not".

## Design

### D1 — one owner for "blockers still open behind this pass"

Add `chain_open_blockers(facts, anchor) -> list[dict]`: for every review on
`review_chain(facts, anchor)`, its `unresolved_blocking` findings, each as
`{review_id, fid, title, files}`, oldest review first. `carried_blocking` keeps its signature and
becomes "find the anchor by the structural hop, then return `chain_open_blockers`".
`_open_blocker_on_chain` becomes `bool(chain_open_blockers(...))`.

`review_chain` reads only fact bodies, so it and the new function belong in `coverage_algebra`
beside `unresolved_blocking`. That placement is what lets D4 use it: `critic_mode` already imports
`coverage_algebra`, and the reverse import would be a cycle.

Because `carried_blocking` is the single reader behind the roll-call, the consolidation close and
the findings-cache record (`branch_review_record`), widening it widens all three at once.

### D2 — the roll-call names every blocker on the chain

`account_for_prior_blockers_directive` needs no logic change, only wording: "the round you are
verifying left these" becomes "the rounds behind this pass left these", since an entry may now sit
several reviews back. Each line already carries `review_id/fid`, which is what the reviewer writes
in `resolutions`.

The reviewer also needs to be able to *judge* an older finding, and today cannot:

- **The finding's text.** `goals-1-3.md` tells a verify reviewer to take `(review_id, fid)` "from
  the prior findings record". That record is built from the newest review
  (`branch_review_record`), where a carried blocker is its id, title and files and no more. The
  manifest gains
  `carried_blockers`: the full recorded finding (description, files, severity) for each entry of
  `chain_open_blockers`. The roll-call points at it.
- **The finding's files.** Verify scope is the anchor's `files_reviewed` plus the delta. A's files
  may be in neither. They join the manifest's subject set, so the reviewer may open them. A carried
  blocker's files are read to return a verdict on that blocker; the existing rule that a new finding
  in this mode is BLOCKING or not a finding is unchanged.

### D3 — an open chain blocker is something this mode can resolve

`begin_review` sets `pending_actionable` from the anchor's recorded counts. Change it to
`anchor counts + len(chain_open_blockers(...))`. An empty-delta verify pass then dispatches when a
chain blocker is open, and still exits 3 when none is. This is the conjunct the code already calls
"what keeps the gate from deadlocking"; it was reading a count taken at record time where the
question is about the store now.

Read the count from the store rather than from `counts` for the anchor too only if that falls out
free. A resolved anchor finding still counted as actionable costs one dispatched pass, not a
deadlock, and changing it is outside this bug.

### D4 — the gate's advice follows what a verify pass can now reach

`_unresolved_at_nodes` marks an entry `superseded` when its review is not the path's newest. After
D1–D3 that is no longer the test. An entry is unreachable only when its review is **not on the
chain of the path's newest review**. `superseded` is recomputed that way, and the two readers of the
flag keep working unchanged:

- on-chain (the reported case): `blocking_remedy_lines` prints the standard remedy, which now works;
- off-chain: it still leads with the spanning `cumulative`.

Three sentences state the old world and are deleted or rewritten, not added beside:

- the consolidation close's "Act now: once a newer review supersedes that round, no verify pass will
  name these again and only a spanning cumulative can clear them";
- `_verify_anchor_id`'s docstring claim that a blocker on any other fact is one no verify pass will
  ever name;
- `blocking_remedy_lines`'s "Three cases" docstring, where "superseded" changes meaning.

### D5 — the budget refusal names what is left

`SKILL.md`'s exit-4 row already says "Any BLOCKING it names: fix, then verify-resolutions (never
refused by the budget)". After D1–D3 that sentence is true for every on-chain blocker. No exemption
is added: the budget still can end a loop and never open a gate.

One residual remains: an off-chain blocker with the budget spent. A verify pass cannot reach it and
the budget refuses the review that can. It is rarer than the reported case and needs a ruling
(Q1), so this design makes it visible and no more. When `_refuse_over_budget` runs and the gate's
verdict holds an off-chain blocker, the refusal names it and says `--force` is the route, with the
user's authorization, as today.

### Not doing

- **Letting `disposition --fixed` accept a later review as its warrant.** It would make the builder
  the one who asserts which review verified which fix. That judgment belongs to a reviewer; D2 gives
  it to one.
- **Exempting a "bookkeeping" cumulative from the budget.** The dispatch cannot tell a review whose
  only purpose is to clear a stranded blocker from any other cumulative, and a self-declared
  exemption is the lever every over-budget loop would pull.
- **Minting A's resolution from pass 3's clean result.** A clean later pass never judged A. The
  data model forbids a resolution nobody made, and #711 recorded why.

## Changes by site

| Site | Change |
|---|---|
| `coverage_algebra` | `review_chain` moves here; new `chain_open_blockers`; `_unresolved_at_nodes` computes `superseded` as off-chain; `_verify_anchor_id` docstring |
| `critic_mode` | imports `review_chain`; `_open_blocker_on_chain` delegates |
| `critic_consolidate.carried_blocking` | returns the chain's set |
| `critic_consolidate.begin_review` | `pending_actionable` adds chain blockers; manifest `carried_blockers`; carried files join the subject set; manifest validator accepts the key |
| `critic_consolidate` close and roll-call | wording per D2 and D4 |
| `critic_consolidate._refuse_over_budget` | names an off-chain blocker and its route |
| `gates.blocking_remedy_lines` | docstring only; behaviour follows the flag |
| `skills/critic/review-cycle.md` | § Verify-resolutions anchoring: what the pass must answer; "Not a demotion" exit-3 sentence; the manifest key list |
| `skills/critic/goals-1-3.md` | where a verify reviewer finds a carried blocker's text |
| `tests/test_carried_blocking_findings.py`, `tests/test_cumulative_gate.py` | below |

A sweep for the retired claim ("no verify pass will name", "only a spanning cumulative can clear")
across `plugin/` and `tests/` closes the change, searched by meaning and not only by those words.

## Tests

Each is written to fail on today's `develop` first.

1. **The reported sequence, end to end at the dispatch door.** Facts: cumulative with A; verify 1
   resolving nothing and raising B; verify 2 resolving nothing and raising C; verify 3 resolving B
   and C. Assert: `begin_review("verify-resolutions")` on an empty delta dispatches (not exit 3);
   its directives name A; its manifest carries A's text and files.
2. **The resolution lands and the gate clears.** A partial resolving A by `review_id/fid` of the
   cumulative consolidates, and `coverage_verdict` over the same path returns `covered`.
3. **The gate's advice.** With A open on-chain, `blocking_remedy_lines` gives the standard remedy.
   With a blocker on a review off the newest review's chain, it leads with the spanning review.
   Both branches pinned, since the flag changed meaning.
4. **Exit 3 still fires.** Empty delta, anchor clean, chain clean: no dispatch. This is the control
   that shows test 1 is not passing because the no-op guard was removed.
5. **Budget unchanged.** With the budget spent, `cumulative` still exits 4 and
   `verify-resolutions` still dispatches.
6. **A second review of one tree does not hide the first** in `chain_open_blockers`, matching
   `review_chain`'s existing rule.

## Open questions for the owner

- **Q1 — the off-chain residual.** A blocker on a review that is on the gate's path but not on the
  newest review's chain stays reachable only by a `cumulative`. Proposed: leave it on `--force` and
  have the budget refusal say so (D5). The alternative is to build the roll-call from the gate's own
  set (unresolved blockers at the nodes of the composed path) so nothing is ever off the brief. That
  is the more exact set, but it makes dispatch depend on a coverage verdict that may be `uncovered`
  at that moment, and needs a fallback. Which do you want?
- **Q2 — how far back.** The chain is walked to its end. On a long branch that can bring a blocker
  from many rounds ago, with files the fix has since moved. Proposed: no cap, since an old open
  blocker blocks the gate exactly as hard as a new one. Confirm.
- **Q3 — verify 1's behaviour.** The stranding starts when a pass raises B "on the same subject"
  where A was left open. Whether that should have been A left open with a note, not a new finding,
  is #1170's question (one defect listed as several findings). This design does not depend on the
  answer. Confirm it stays there.

The stage label stays at `stage:design` until Q1 is answered; Q2 and Q3 only confirm defaults.
