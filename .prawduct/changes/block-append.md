---
schema: 1
type: fix
scope: block-append
date: 2026-10-28
title: A Stop block says how to answer it
closes: [brookstalley/prawduct#1095]
---

#1095. After a Stop-hook block, the model rewrote its whole turn close instead of adding the line
the gate asked for. In the 3.8.0-dev survey every blocked turn (22 of 22) wrote a second STATE /
YOUR TURN block after its full answer, and operators read that as the hook firing twice.

Every Stop block now opens with one line, right after its heading, saying how to answer it: do
only what the items ask, end with a short note, and do not repeat the answer. A closing block is
written again only when the one above would now be wrong, because the gates read the close from
the last message only. That covers an item faulting the close itself (the clear-verdict and
clear-reason gates) and a turn that must close `RUNNING` / `DO NOT CLEAR`: to keep a deferral of
the session-end gates, or because its fix started work a clear would kill, such as a review.
`_stop_block_opening` in `prawduct-hook` is the only place either Stop block (a gate's, or an
unknown host's) gets its opening, and a test pins the line on each. `session-hygiene.md` says the
same in one sentence.

Whether blocked turns stop carrying a second close is measured by the next field survey, not by
this change's tests.

## Consumer note
- When the Stop hook blocks a turn, its message now says to add only what the blocking items ask
  for, without repeating the answer. Write a closing block again only when the one above would
  now be wrong: an item faults it, or you must close `RUNNING` / `DO NOT CLEAR`.
