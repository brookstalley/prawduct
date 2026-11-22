---
schema: 1
type: fix
scope: delegate-scratch-and-revisit-wording
date: 2026-11-22
title: delegate briefs name a scratch subdirectory, and the revisit-due advisory names both kinds of date
closes: [brookstalley/prawduct#1210]
---
Parallel delegates all used the session's one scratch directory, and the delegation guide's brief
checklist never mentioned it. Delegates running at the same time overwrote each other's
same-named files, including the backups a mutate-and-restore check depends on. The
ownership-boundary item in `delegation.md` "What a brief must say" now includes the delegate's own
scratch subdirectory, and the anti-patterns gain its tell: two briefs in one wave that name no
scratch location, or the same one.

The `revisit-due` advisory called every past `revisit:` date an expired exception and asked the
owner to renew it or let it lapse. The field also carries dated re-checks, such as a measurement
booked for a date (#981), and for those the answer is to do the work. The advisory's summary and
owner line now name both kinds of date, and so does every description of the field: the backlog
skill, the scaffolded backlog legend and the backlog data model. The advisory's evidence line is
unchanged, so its id is stable and an open advisory is not re-minted.

## Consumer note
When you delegate to parallel subagents, give each one its own scratch subdirectory in its brief.
The `revisit-due` advisory now says a past `revisit:` date may be work scheduled for that date
rather than an expired exception. Its id is unchanged, so a dismissal still holds.
