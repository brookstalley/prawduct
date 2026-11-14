# Native review paired with the Critic — the experiment (#1130)

On a development build of the plugin (a `-dev` version), every `cumulative` Critic review, and one
in six `chunk` and `verify-resolutions` reviews (#1166), also starts the host's native `/code-review`
at `high` over the same interval, unless the repo sets `native_review_pairing: false`. Each native
run is recorded as a `native.review` ledger event, and its text is kept per clone in
`.prawduct/.native-reviews/`. A boundary run's findings are put to the builder; an inner run's are
not. The build plans and their decisions are `.prawduct/artifacts/build-plan-native-review-paired.md`
and `build-plan-native-review-inner.md`. The host facts the design rests on are in
`host-facts-2026-11-12.md`, which `fork_costs.py` re-derives.

## Monthly comparison

1. Run the script over every repo that takes `../prawduct-live` as its plugin:

       python3 -I .prawduct/research/native-review-paired/compare.py <repo> [<repo> ...] \
           --out <scratch dir> [--transcripts <a session's subagents dir> ...]

   It prints, per Critic goal, the findings both raised (and, apart, native findings matching a
   Critic observation), only the Critic raised, and only the native review raised; the same per
   stage and Critic severity (blocking, warning, observation —
   a native finding is matched against the Critic's observations too, since the Critic rated
   that defect, only lower); each instrument's wall clock per stage; native fork tokens when given
   transcripts; per stage, how many native findings name a file outside the Critic's interval (a
   high share at the inner stage means the native review read more than the Critic did); each
   instrument's re-raise candidates; and progress toward the stop condition, which counts boundary
   pairs only. With `--out` it writes `blind-sheet.json` and
   `blind-key.json`. Read before the table: the `count check` line (each text against what the
   ledger recorded; a disagreement means the parse changed or a text was edited since) and every
   `WARNING` line the script prints. The comparison assumes each native run matched its Critic
   review's level and model and read the tree the Critic read, and each warning names runs where
   that failed (a model mismatch, a recipe other than `high`, a tree that moved before the run
   landed) — investigate those before trusting the table.
2. Hand `blind-sheet.json` alone to a verifier that has not seen the key. A fresh subagent is
   enough: have it read the code at each finding's location **as reviewed**, from the item's
   `repo` at its `head_tree` (`git -C <repo> show <head_tree>:<path>`, and `git -C <repo> diff
   <base_tree> <head_tree>` for the change), not the current checkout, where many findings are already
   fixed. Then have it answer each item's `ask`. That is
   "same defect?" for a pair the file match proposed; "real defect? and which goal?" for every
   unique finding, whichever instrument raised it; and, for a re-raise candidate,
   whether the finding repeats one of the earlier findings listed with it. A candidate is
   proposed by file, against what the Critic would have been handed as prior dispositions (and
   earlier boundary runs' native findings, by the same rules), so most are different defects; only
   the confirmed ones are re-raises. No item carries a line number, since only native findings
   have one.
   An item marked `tree_moved` came from a review whose working tree changed before the native
   run landed, so the code at `head_tree` may differ a little from what was read. A re-raise
   item's `earlier` findings are read at `earlier_head_tree`. The two instruments still word
   findings differently (a native finding names one file and reads "summary — scenario"), so the
   sheet hides the source as far as the words allow, not completely.
3. Join the answers to `blind-key.json` and fill in the decision table below. A pair's order on
   the sheet is shuffled; its key entry's `first_source` says whether the Critic's or the native
   finding came first.

## Decision table (#1130 step 6)

A goal is ceded to the native review when the native review raised most of that goal's
verified-real findings, **and** that goal's unique verified-real yield per review is small against
its cost. The thresholds are the owner's to set when they read the table; this file does not
pre-commit them. Three columns bear on handing the native review a gate rather than a goal
(#1164-#1166): whether it raised the Critic's verified-real **blocking** findings, and not only its
warnings; whether that holds at the **inner** stage, where most correctness review happens; and its
confirmed **re-raise** rate against the Critic's, since a gate that re-raises settled findings
does not terminate.

## Stop

The experiment stops after four weeks or sixty paired reviews, whichever is later. `compare.py`
prints `stop: True` once both hold. Record the table and the owner's decision on #1130, then
remove the pairing (or keep it, if the owner rules so).
