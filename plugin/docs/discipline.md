# Discipline Corpus — where the fleet's portable rules live

Ten lessons that governed products learned independently, two to five repos each. None ships as an
always-loaded corpus: each is delivered where rules fire — in code at the moment of the action, in a
Critic goal the review reads, in a methodology sentence at the step that needs it, or in a skill step
when that step runs — and this table records which. A rule enters only if it is stack-agnostic, not
about prawduct internals, and about building software with an agent rather than about one codebase.

`tests/test_discipline_table.py` reads this table and asserts each row's anchor phrase is present in
its surface, so a sentence that moves or goes has to take its row with it.

| # | Rule | Learned by | Channel | Surface | Anchor |
|---|---|---|---|---|---|
| 1 | A mutation must be shown to have applied — a mutant you did not watch go red proved nothing | discodon, samsung, hallucinote | skill step at PR pre-review (boundary) | `skills/pr/SKILL.md` | `a mutation you did not watch go red applied nothing` |
| 2 | A test that passes identically when its subject is broken is vacuous | metallm, samsung, cordyceps, scriob | code directive at `test-evidence record` | `bin/prawduct-hook` | `Green is evidence only about what could have made it red` |
| 3 | A partial run is a verification ceiling, never the verdict — green is claimed only on the suite the repo declares | scriob, metallm, puzzles, discodon | mechanism (`test-evidence record` runs the declared suite) + methodology | `methodology/delegation.md` | `A cost bound, not a rigor discount` |
| 4 | An interface change means a census of every consumer | hallucinote, scriob, discodon, metallm | methodology | `methodology/building.md` | `grep for those consumers across layers` |
| 5 | Retiring a claim is a repo-wide grep — code, tests and the prose describing it | samsung, discodon, hallucinote, trenchant, swordfishing | Critic goal 4 (final/cumulative modes) | `skills/critic/review-protocol.md` | `the citations a renamed or removed term leaves behind` |
| 6 | There is no pre-existing exception; the fix-it half is bounded to BLOCKING findings | metallm, discodon, scriob | session digest + Critic goal 1 | `methodology/session-digest.md` | `"pre-existing" exception` |
| 7 | Built-but-unconsumed is not done | fleet-wide | Critic goal 2 | `skills/critic/goals-1-3.md` | `Built-but-unconsumed` |
| 8 | Test both directions of a contract — the consumer's read of the producer's real signals, not only the type they share | fleet-wide | methodology | `methodology/building.md` | `Both directions` |
| 9 | A stated cause is a hypothesis until reproduced | fleet-wide | methodology | `methodology/reflection.md` | `treat a reported cause as a hypothesis until you reproduce it` |
| 10 | Probe real output — launch it, call it, inspect what it emits; mocks are not verification | TangleClaw, hallucinote | methodology | `methodology/building.md` | `mocks are not verification` |

A Goal 1–3 row appears in both `goals-1-3.md` and `review-protocol.md`, which must agree; a Goal 4
row lives in `review-protocol.md` alone, because only the final and cumulative modes run Goal 4.
