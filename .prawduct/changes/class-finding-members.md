---
schema: 1
type: feature
scope: class-finding-members
date: 2026-11-18
title: a class finding records its members, and a fixed claim that skips one is not recorded
closes: [brookstalley/prawduct#847]
---
A reviewer could rate a finding `class`, list its members in prose, and watch the builder fix the
member it led with: `verify-resolutions` graded the finding, and the next round found the members
nobody touched. On the 2026-09-19 `test-report-scope` branch that cost three rounds where one would
have done.

**Measured first.** `tools/measure-class-member-closure.py` reads every clone's evidence store under
a root (read-only, aggregate output, review facts since 2026-08-04, deduplicated by fact id). It
counts (a) class-framed findings naming two or more sites, and (b) of those, the ones a later
same-scope BLOCKING finding named a listed member of. The decision reading, fixed before the data,
matches on identifier sites; a path-inclusive ceiling and a labelled-class, code-shaped floor are
printed beside it. Run on 2026-11-18 over the fleet (14 clones, 5,389 review facts over 3.5
months; one more clone holding an evidence store is not an onboarded product and was left out
with `--exclude`, and including it moves no figure across the bar): (a) 3,273 of 3,396 class-framed findings (96%); (b) 370, about 105 a month, with the floor at
about 40 a month and the ceiling at about 169. The bar was 3 a month, and even the floor clears it,
so **D2 is built (go)**. Re-derive with `tools/measure-class-member-closure.py --exclude <that clone>
--control-scope test-report-scope`. The positive control is that branch's facts in this repo's store.
The tool counts round 3 to 4 (a class finding's `TestTheClassifier`/`_Config` members raised again)
and round 4 to 5 (`target.parent.mkdir`, the OSError source the fix left outside the `try`). Its
first run missed the second event, because a dotted identifier read as a file name. That was fixed
and pinned before the figures above were taken. (b) is a floor on the incident's shape: the
`ignore_glob` member was listed under an `instance` label, which the tool does not count.

**D1.** A partial finding may carry `scope` (`instance`|`class`|`none`), `closure` (one sentence:
the property that decides membership) and `members` (`[{id, site, note?}]`). They round-trip into
the review fact and `.critic-findings.json`. A malformed part is dropped with a warning and never
refuses the consolidation, and `validate-partial` shows the warning to the reviewer while it can
still fix the file. `FINDING_SCOPE_DIRECTIVE`, `review-protocol.md` and `critic-reviewer.md` ask for
the fields. An old-shape partial merges byte-identically.

**D2.** A `fixed` resolution of a finding with recorded members is appended only when its own
`members` answers every id: `fixed`, or `waived` with a rationale. Otherwise consolidate appends no
resolution fact, the finding keeps blocking, and `NEXT-ACTION` names the unanswered ids. The fact is
withheld rather than marked partial: `coverage_algebra.resolution_index` lifts on any `fixed` fact,
so a partial marker would open the gate under an older plugin. A finding without members, and a
finding-level waiver, resolve as before.

**D3.** The verify dispatch's roll-call lists each carried finding's closure and members by id and
site, and says how a resolution answers them. It shows a `class` finding with no members as
"class, unbounded — closes only by a construction".

## Consumer note
A finding whose reviewer listed `members` now needs every member answered before a `fixed`
resolution is recorded. Until then, consolidate's `NEXT-ACTION` names the unanswered ids. Findings
without members, and every existing record, behave as before.
