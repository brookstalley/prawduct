---
schema: 1
type: chore
scope: native-review-paired
date: 2026-11-18
title: the Critic-vs-native blind verification join is committed as research tooling
closes: [brookstalley/prawduct#1197]
---
The 2026-11-18 third blind check rebuilt its join of verifier answers to the blind key by hand in
untracked scratch. `join.py` now sits beside `compare.py`: it takes the key, the answers files and
the governed repos as arguments, joins by item id, and prints per goal the native share beside the
non-minor native share, plus per stage, per Critic severity and the re-raise candidates. Every rate
is over the frozen sheet's reviews, not a live re-load of pairs. Pointed at the 2026-11-18 inputs it
reproduces that check's figures (Design Is Sound 62% native, 39% non-minor). The README documents
inputs, outputs and the denominator rule.

## Consumer note
none: affects only the #1130 experiment's research directory in this repo
