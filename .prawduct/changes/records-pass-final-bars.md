---
schema: 1
type: governance
scope: records-pass-final-bars
date: 2026-11-18
title: at final, the Records Pass rates governance records against two bars, not three
closes: [brookstalley/prawduct#1201]
---
#771's fleet run (14 clones, 6296 review facts) put findings whose only subject was a governance
record at 14% of the round-buying findings at the boundary stage and 12% at the inner stage after
the subject/oracle narrowing, over the 10% and 5% bars #771 fixed before the data arrived. The
first remedy its rule names is applied: at `final`, the Records Pass no longer rates a record for
"it misleads into action". It still rates "it ships" and "it must stop the merge" (BLOCKING).
`cumulative` keeps all three bars. `tools/measure-record-findings.py` re-measures the shares.

## Consumer note
A `final` review raises fewer WARNINGs on governance records. Record inaccuracies that would
mislead an operator are still rated at the boundary review.
