# Discipline Corpus — where the fleet's portable rules live

Ten lessons that governed products learned independently, two to five repos each (learning-system
audit 2026-09-01 §3.5). None ships as an always-loaded corpus: each is delivered where the evidence
says rules fire — **in code at the moment of the action**, **in a Critic goal** the review reads, or
**in a methodology sentence** at the step that needs it — and this table records which. A rule
enters only if it passes all three of the promotion tests the owner ratified (#343): stack-agnostic;
not about prawduct internals; about building software with an agent rather than about one codebase.
A product that writes one of these as its own rule has paid for a rule it already inherited; its
reflection guide says so (`methodology/reflection.md`, Step 4).

`tests/test_discipline_table.py` reads this table and asserts each row's anchor phrase is present in
its surface, so a sentence that moves or goes has to take its row with it.

| # | Rule | Learned by | Channel | Surface | Anchor |
|---|---|---|---|---|---|
| 1 | A mutation must be shown to have applied — a mutant you did not watch go red proved nothing | discodon, samsung, hallucinote | code directive at `test-evidence record` | `bin/prawduct-hook` | `a mutation you did not watch go red applied nothing` |
| 2 | A test that passes identically when its subject is broken is vacuous | metallm, samsung, cordyceps, scriob | code directive at `test-evidence record` | `bin/prawduct-hook` | `Green is evidence only about what could have made it red` |
| 3 | Run the canonical full suite before claiming green; a subset is a ceiling, not a verdict | scriob, metallm, puzzles, discodon | methodology | `methodology/building.md` | `Run the full suite. Every test must pass` |
| 4 | An interface change means a census of every consumer | hallucinote, scriob, discodon, metallm | methodology | `methodology/building.md` | `grep for consumers across layers` |
| 5 | Retiring a claim is a repo-wide grep — code, tests and the prose describing it | samsung, discodon, hallucinote, trenchant, swordfishing | Critic goal 2 | `skills/critic/goals-1-3.md` | `Removal or rename is repo-wide` |
| 6 | There is no pre-existing exception | metallm, discodon, scriob | session digest + Critic goal 1 | `methodology/session-digest.md` | `There is no "pre-existing" exception` |
| 7 | Built-but-unconsumed is not done | fleet-wide (audit §3.5) | Critic goal 2 | `skills/critic/goals-1-3.md` | `Built-but-unconsumed` |
| 8 | Test both directions of a contract — the consumer's read of the producer's real signals, not only the type they share | fleet-wide (audit §3.5) | methodology | `methodology/building.md` | `Both directions` |
| 9 | A stated cause is a hypothesis until reproduced | fleet-wide (audit §3.5) | methodology | `methodology/reflection.md` | `A reported cause is a hypothesis until you reproduce it` |
| 10 | Probe real output — launch it, call it, inspect what it emits; mocks are not verification | TangleClaw, hallucinote | methodology | `methodology/building.md` | `mocks are not verification` |

Rows 5, 7 and 9 and the second clause of row 1 were added by this table's first entry (learnings v2,
2026-09); the rest already lived where the row says. The Critic-goal rows appear in both
`goals-1-3.md` and `review-protocol.md`, which must agree; the anchor is checked in the first.
