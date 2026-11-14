---
schema: 1
type: fix
scope: blind-sheet
date: 2026-11-14
title: the Critic-vs-native blind sheet no longer tells the verifier which instrument raised a finding
closes: [brookstalley/prawduct#1169]
---
The blind sheet `compare.py` builds for #1130's verification named the instrument in two ways,
both found running the first blind pass on 2026-11-14. A Critic-only finding was asked "real
defect?" and a native-only one "real defect? and which goal?". And in every proposed pair the
Critic's finding came first. Every unique finding now gets one question, and each pair's order
is shuffled, with the key's `first_source` saying which side came first.

Each item now also names its `repo` and the `base_tree` and `head_tree` its review read, taken
from the native review's ledger event. The verifier can then read the code as reviewed; read
from the current checkout, findings that were fixed after review look false. A re-raise item
also names the earlier review's `earlier_head_tree`, and the items of a review whose working
tree moved before the native run landed are marked `tree_moved`. The README says how. The two
instruments still word findings differently, so the sheet hides the source as far as the words
allow.

## Consumer note
none: affects only the #1130 experiment's comparison script in this repo's research directory
