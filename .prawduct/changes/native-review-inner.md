---
schema: 1
type: feature
scope: native-review-inner
date: 2026-11-13
title: the paired native review samples inner reviews, and the comparison reads severity, stage and re-raises
closes: [brookstalley/prawduct#1164, brookstalley/prawduct#1165, brookstalley/prawduct#1166]
---
Three measurements #1130's comparison could not make. Each one bears on whether the native review
could own bug-hunting as a gate, rather than only on whether it finds things.

- **Inner reviews pair, on a sample.** On a development build, one in six `chunk` and
  `verify-resolutions` reviews, chosen by review id, now pairs a native review. Before this, only
  boundary reviews did. A working-tree interval is handed to the native review as two unreachable
  commits over the reviewed trees, so its diff is exactly the Critic's interval. No ref, index or
  file changes, and `git gc` collects the commits. An inner run's findings are not put to the
  builder, because a second list beside an inner pass would add review rounds. They stay readable
  with `native-review show`. The ledger event now carries the paired review's mode and stage,
  whether the range was synthetic, and whether a judgeable reviewed file moved before the run
  landed.
- **Severity and stage.** `compare.py` now matches a native finding against the Critic's
  observations as well as its findings, so a defect the Critic rated lower no longer counts as
  native-only. On the first five paired reviews, six findings moved from native-only to shared. It
  also tallies per stage and Critic severity. The stop condition still counts boundary pairs only.
- **Re-raises.** For both instruments, `compare.py` proposes re-raise candidates: findings that
  name a file an earlier, still-standing finding names. The reach is the one the Critic's own
  prior dispositions use: same plan scope, and a cited file the later review changes. Each
  candidate goes to the blind sheet with every earlier finding it might repeat.

## Consumer note
none: affects only development builds' paired native review records and the experiment's
comparison script; no gate, verdict or command changes
