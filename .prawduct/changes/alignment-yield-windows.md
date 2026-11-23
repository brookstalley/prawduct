---
schema: 1
type: fix
scope: alignment-yield-windows
date: 2026-11-23
title: the alignment yield measure survives compaction summaries and transcript pruning
closes: [brookstalley/prawduct#1211]
---
`tools/measure-alignment-yield.py` counted Claude Code's compaction summaries (user records
flagged `isCompactSummary`) as owner turns. In the 2026-11 re-run of #981 they were 26 of 44
correction leads and 20 of 992 substantive requests, and none appeared in the baseline window.
They are no longer owner turns and open no turn; work after one stays with the request it
continues.

The health line was tallied over every transcript whatever the window, so two windows printed the
same line and #981 step 2 could not be read from the output. Health and the `transcripts` count
now cover the transcripts a window selects: those whose first timestamped record falls in it. A
transcript with no timestamp, or an unreadable one, is tallied into every window and named
(`transcripts_without_timestamp`, `transcripts_unreadable`). Owner turns are still windowed turn
by turn, so no request count moves except by the compaction fix. The JSON gains
`transcripts_on_disk`.

Claude Code's 30-day retention pruned the 2026-10-09 baseline to 442 of 963 substantive requests.
`--save-baseline` now writes a window's governed and ungoverned totals and its health, once, to
`.prawduct/research/alignment-yield/baselines.json` (counts only, no text, paths or project
names; a window already saved is kept, and an unreadable file is an error, never replaced). A run
of a saved window reports its live counts against the saved ones and says when they fall short,
so the saved counts are the baseline to cite. `--baseline-file ''` ignores the file. The committed
file is seeded from the figures `requirements-alignment-discovery.md` records for the 2026-10-09
baseline (substantive 963, asked_first 140, mid_build_asks 349, corrections 18, governed); the
figures it does not record are null. Tests feed a compaction-summary record and assert it is not
an owner turn, give two windows different health, and pin the write-once, no-leak, pruned and
min-chars-mismatch behaviour and the committed seed.

## Consumer note
None. `tools/measure-alignment-yield.py` and its saved baseline are this repository's own measurement; nothing ships in the plugin.
