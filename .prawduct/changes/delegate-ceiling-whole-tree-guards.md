---
schema: 1
type: fix
scope: delegate-ceiling-whole-tree-guards
date: 2026-11-22
title: a delegate's verification ceiling names the whole-tree guards as a class
---
In one batch, two delegates' narrow verification ceilings left out tests that read the whole
tree. Their merges went red on a bare sibling link and a false GitHub closing keyword, in files
the delegates wrote. The learning in `tests.md` already said to name that class in the brief,
but nothing in the brief checklist pointed at it, so it depended on recall and missed both
times. The verification-ceiling item in `delegation.md` "What a brief must say" now names the
whole-tree guards (path references, closing keywords, packaging lint, prose budgets, goldens) as
a class, and the anti-patterns gain its tell: a ceiling that lists test files and names no
whole-tree guard class. `building.md`'s delegation steps restated the ceiling. They now point
at that checklist instead, so the class has one home.

## Consumer note
When you delegate, a subagent's verification ceiling should include your repo's whole-tree guards
(path-reference checks, closing-keyword lint, packaging lint, prose budgets, goldens), named as a
class. A narrow test run never reads the files those guards check.
