---
schema: 1
type: refactor
scope: post-fix-rule-one-home
date: 2026-11-18
title: the rule for what closes a coverage gap after a fix is now written in one place
closes: [brookstalley/prawduct#723]
---
The rule covering a fix made after a review was written out in five places: what closes the
coverage gap, and which tree a `verify-resolutions` pass graded. The places were two gate messages,
the PR skill, the Critic skill and `building.md`. The fix for #722 shipped a wrong version of it in
two of them at once. Now each half of the rule is written once:

- **Which tree a pass grades** is explained only in `review-cycle.md` § Verify-resolutions
  anchoring and demotion, beside the code that decides it.
- **What the operator does next** is one string, `gates.POST_FIX_COVERAGE`. The blocking remedy
  (shared by the PR gate and the Stop hook) and the PR gate's `uncovered` remedy both print it. It
  reads what a pass printed about the work it left out (`NOT REVIEWED:`, `NOT in the reviewed
  scope`), and it never predicts which tree the pass graded. So a change to how that tree is chosen
  does not touch it.

The PR skill and `building.md` link to the explanation instead of repeating it. The Critic skill's
exit-3 qualifier now says only that the work it names is outside what the pass graded. That file
is what every reviewer loads, so it does not send them to `review-cycle.md`. `building.md` names
`gates.FIX_ORDER` rather than copying it, so changing the fix order is a one-file edit as well.
`gates.FIX_ORDER_AFTER_CUMULATIVE` no longer explains how a commit moves the anchor either.

`tests/preferences/test_free_interval_prose.py` tests the structure instead of five separate
phrasings. No prose carrier may repeat the anchoring rule: a control feeds the old sentences back in
to prove the check catches them. Both code carriers must print the shared string, and when the
string is replaced at runtime, both gate messages show the new text.

## Consumer note
The `uncovered` and `blocking` messages from `check-cumulative-critic` and the Stop hook word the
post-fix step differently. They no longer try to predict which tree a `verify-resolutions` pass
graded. They tell you to commit the tree the pass graded exactly as it was, or, if the pass listed
files it left out, to commit those files and verify the new changes. No exit code or verdict changes.
