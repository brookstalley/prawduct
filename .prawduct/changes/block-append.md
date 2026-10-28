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
only what the items ask, end with a short note, and do not repeat the answer or its closing
block. There are two exceptions. A `RUNNING` / `DO NOT CLEAR` close has to be written again,
because the gates read the close from the last message only, and a continuation without one
would lose the deferral. A close is also written again when an item says to change it, as the
clear-verdict gate does. `_stop_block_opening` in `prawduct-hook` is the only place either Stop
block (a gate's, or an unknown host's) gets its opening, and a test pins the line on each.

Whether blocked turns stop carrying a second close is measured by the next field survey, not by
this change's tests.

## Consumer note
- When the Stop hook blocks a turn, its message now says to add only what the blocking item asks
  for, without repeating the answer or its closing block. Re-state the close only to keep a
  `RUNNING` / `DO NOT CLEAR` close, or where an item asks you to change it.
