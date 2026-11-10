---
schema: 1
type: governance
scope: retire-clear-verdict
date: 2026-11-10
title: The clear-verdict check records a contradicting close instead of blocking it
---
The `clear-verdict` Stop check blocked a turn that closed `YOUR TURN` or `COMPLETE` with
`DO NOT CLEAR`. On 3.8 it was scored about as often wrong as right. The harm it guards against is
a session kept open needlessly, so a block on every such turn cost more than it saved. The owner
retired it from blocking on 2026-11-10 (#1044) and kept the measurement.

The check now records each firing as a `stop-observed:clear-verdict` fact
(`evidence.append_stop_observation`), with the same reason and observations a block carried, and
lets the Stop through. `prawduct-hook stats` reports these under *observed only*, scored by the
same catch/slip rule and never counted as Stops blocked or guard refusals. Blocks recorded before
this change are read as before. The detection rule is unchanged. `clear-verdict` leaves the gate
registry, since it no longer blocks. `clear-reason` still blocks, and the standing-block rule
("`COMPLETE` never says `DO NOT CLEAR`") stays in the methodology.

## Consumer note
A turn that ends `YOUR TURN` or `COMPLETE` with `DO NOT CLEAR` is no longer sent back by the Stop
hook. Each one is still counted, and `prawduct-hook stats` lists them under "observed only".
