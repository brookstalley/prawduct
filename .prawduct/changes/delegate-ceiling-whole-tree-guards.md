---
schema: 1
type: fix
scope: delegate-ceiling-whole-tree-guards
date: 2026-11-22
title: a delegate's verification ceiling adds the whole-tree guards as a class
---
In one batch, two delegates' narrow verification ceilings left out tests that read the whole
tree. Their merges went red on a bare sibling link and a false GitHub closing keyword, in files
the delegates wrote. The learning in `tests.md` already said to name that class in the brief,
but nothing in the brief checklist pointed at it, so it depended on recall and missed both times.

The verification-ceiling item in `delegation.md` "What a brief must say" now sets the ceiling in
two parts. The narrow run comes from the `Delegate verification` row, or, absent that row, the
narrowest run covering the delegate's own change. To it, either way, are added the tests that read
files outside any one change (reference and link checks, size budgets, goldens, record schemas),
named as a class. The anti-patterns gain its tell: a ceiling that lists test files and names no
whole-tree guard class.

`building.md` describes a delegate's ceiling in two places, and both now agree. The shared ceiling
paragraph says a delegate runs the ceiling its brief names, not the builder's touched-files run.
The delegation `How:` line names the row, the narrow run and the guards. Tests pin all three
sentences, and each test was seen red when its sentence was removed.

## Consumer note
When you delegate, a subagent's verification ceiling is its narrow run (your `Delegate
verification` row, or the narrowest run covering its change) plus your repo's tests that read
files outside any one change, such as link checks, size budgets, goldens and schema validators,
named as a class. A narrow test run never reads the files those tests check.
