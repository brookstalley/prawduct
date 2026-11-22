---
schema: 1
type: feature
scope: late-requirement-capture
date: 2026-11-18
title: a requirement that surfaces mid-build now has a one-line record, a home, and an impact walk
closes: [brookstalley/prawduct#1034]
---
A requirement that surfaced mid-build had no home, so it was usually gone by the next session. The
governance ROI study found late requirements to be the largest cause of rework that was not a fix,
and most of them could not have been known in advance, so this makes them cheap to absorb rather
than trying to find them earlier.

`building.md` § "A Requirement Surfaced Mid-Build" now says where the record goes: a
`## Late requirements` section in the governing requirements artifact `prawduct-hook jurisdiction`
ranks first, or the active build plan when the product has none. It gives the one-line shape
`- **LR-<n>** (<date> · why: <operating|new-consumer|owner-change|constraint> · surfaced: <chunk or sha>) — <sentence>.`,
and says a contradicted record gains `SUPERSEDED <date>: <reason>` instead of being edited. It adds
two triggers: an owner statement that changes behaviour, and a defect whose root cause is a missing
requirement. It also describes the impact walk: under the record, list each candidate site as
`change` or `checked, unaffected`, drawing candidates from `jurisdiction`, from plan chunks and
backlog items that name the area, and from `git grep`. The section also states what the walk cannot
find, which is a paraphrased restatement.

`plugin/lib/late_requirements.py` is the one parser for that shape (`parse`, `scan`, `LateReq`). The
new `late-requirement-record` record-lint check uses it. The check grades only the lines a change
added: all four fields present, `why` from the fixed set, and the id unique across the product. It
is rated WARNING and reaches the Critic through the existing record-lint relay. It searches the
product for the section only when the diff added a record, so a product that captures none pays
nothing and sees nothing.

## Consumer note
none: a methodology step; its check fires only on lines inside a `## Late requirements` section, which no product has until it writes one
