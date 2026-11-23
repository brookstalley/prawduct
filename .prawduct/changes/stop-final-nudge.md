---
schema: 1
type: fix
scope: stop-final-nudge
date: 2026-11-23
title: the Stop hook stops asking for a final after a verify pass closes a cumulative
---
A plan whose boundary `cumulative` raised findings, fixed and closed by one clean
`verify-resolutions` pass, ended with a Stop-hook NOTE to run `/prawduct:critic final` for
end-of-cycle synthesis. That review was not owed, and obeying the NOTE cost a full review round.
It fired four times on 2026-11-23, on two plans. Gate 2.5
(`gates._critic_session_satisfies_gate`) read only the latest review's mode. A verify pass
resolves an earlier review's findings and does not undo that review's synthesis, so the mode of
the pass was the wrong thing to ask.

The advisory now judges the review the latest pass verifies. It walks back over verify passes by
the recorded link: a pass's `base_tree` is the `head_tree` of the review it verifies
(`coverage_algebra.prior_review`, the same hop `carried_blocking` takes). It does not walk by
store position, which gives a different answer whenever another review was recorded in between.
The NOTE still fires when the review at the end of that walk is a `chunk`, including a `chunk`
recorded after the `cumulative`. It also fires when a pass links to no review on record. When the
deciding review is not the latest one, the NOTE now says so: "a verify-resolutions pass over a
'chunk …' review". Tests pin each case on the predicate and on the Stop hook's printed advisories.

## Consumer note
Closing a `cumulative` or `final` that raised findings with a clean `/prawduct:critic
verify-resolutions` no longer prints a NOTE asking for `/prawduct:critic final`. If you got that
NOTE after such a close, you did not owe the review. The NOTE still appears when the last review
before your verify pass was a `chunk`.
