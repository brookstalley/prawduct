---
schema: 1
type: feature
scope: asks-last
date: 2026-11-11
title: A turn that needs the user now ends with its asks, under a fixed header after the closing line
---
The owner ruled on 2026-11-11 (`.prawduct/owner-rulings.md`) that anything the user must act on
is the last thing a turn shows, and prominent. They had read a turn that listed its one ask and
then closed `YOUR TURN` · `DO NOT CLEAR` with the reason "The one ask above is for you.", and
found it hard to parse.

**The shape.** The one-line close keeps its labels. When the turn needs the user, the close comes
first, then a blank line, then the asks block, which ends the turn: `**Needs you:**` on a line of
its own, then each ask in full, numbered, with a recommendation. The close's reason never points
at the asks by position ("above", "below"). A turn with no asks still ends on the close. Changed
in `methodology/session-hygiene.md`, the session digest's closing section,
`methodology/building.md` and the methodology skill's guide index.

**The reader.** `lib/standing_block.py` is the one code home for the header (`ASKS_HEADER`)
and the one reader of the close, so the Stop hook's deferral (`gates.turn_declares_in_flight`)
and its two clear checks (`clear-verdict`, `clear-reason`) need no change of their own. A turn
with an asks block is read from the line just before the header. The reading stays narrow,
because a `RUNNING` · `DO NOT CLEAR` close defers the reflection and Critic gates:

- Only a line that leads with `Needs you:` opens the block. Markdown emphasis, code ticks or a
  blockquote marker may come first, the same decoration a label may carry.
- The close must be the last non-blank line before the header.
- Nothing inside the block is read, not even a close-shaped last line.
- Two header lines, or a header with nothing before it, give no verdict.
- When a header is present, the older three-paragraph form is not read.

Without this change, the new shape would have read as "no verdict", which turns off the deferral
and both checks without any sign.

**After a Stop block.** A blocked turn is told not to repeat its answer. The one exception, which
the owner confirmed: a turn that ended with an asks block ends its answer with that block again,
unchanged, so the asks stay the last thing the user sees. A close written again goes before the
asks. The hook's answer line (`STOP_BLOCK_ANSWER`) and the guide's "Answering a block" sentence
both say so, and one test reads both. The six Stop-block goldens under
`tests/fixtures/host_seam_golden/` carry the answer line, so each changed by that string alone.

**A close that points.** A new Stop check, `close-pointer`, records a close whose reason points
at the turn by position ("the one ask above is for you", "see below"), under any disposition, and
never blocks. It follows `clear-reason`: one matcher in `standing_block`
(`positional_pointer_match`, kinds in `POSITIONAL_POINTER_KINDS`), one wrapper in `gates`
(`turn_positional_pointer`), and one record in `cmd_stop` with the same three observations. It
records the kind (`points-above` or `points-below`), never the phrase. A comparative ("coverage
is above the floor"), a hyphenated compound, and a positional word in the turn's body or its asks
are not matched, and a close the reader cannot place records nothing. The check has no
catch-or-slip rule in `stats`, so its firings are counted by kind only. `docs/governance-telemetry.md`
gains its row, and a test pins the row's kinds to the constant in both directions.

`tests/test_stop_verdict_defer.py` pins each guard. Every guard test was seen to fail with that
guard removed, and a mutant that changes nothing survived as the control. The file also pins the
header end to end through `prawduct-hook stop`, with a control that has no header, and pins it to
both prose carriers in both directions. `tests/test_v5_methodology.py` and
`tests/test_plugin_methodology_digest.py` now pin the new placement instead of the old one, "just
above". The digest went from 9412 to 9358 characters. The cost was paid in its own closing section
by cutting a clause that restated the three dispositions defined in the next sentence.

## Consumer note
When a turn needs you to decide, approve or supply something, those asks are now the last thing
in the turn. They appear under a **Needs you:** header after the one-line status close, not above
it, and they are repeated after the agent answers a Stop-hook block. The close keeps its labels,
and a turn with nothing for you still ends on the close. `prawduct-hook stats` gains a
`close-pointer` row under *observed only*, counting closes whose reason pointed "above" or
"below" instead of saying what the asks were.
