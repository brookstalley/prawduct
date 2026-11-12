# Native review paired with the Critic — the experiment (#1130)

On a development build of the plugin (a `-dev` version), every `cumulative` Critic review also
starts the host's native `/code-review` at `high` over the same range, unless the repo sets
`native_review_pairing: false`. Each native run is recorded as a `review.native` ledger event, and
its text is kept per clone in `.prawduct/.native-reviews/`. The build plan and its decisions are
`.prawduct/artifacts/build-plan-native-review-paired.md`. The host facts the design rests on are in
`host-facts-2026-11-12.md`, which `fork_costs.py` re-derives.

## Monthly comparison

1. Run the script over every repo that takes `../prawduct-live` as its plugin:

       python3 -I .prawduct/research/native-review-paired/compare.py <repo> [<repo> ...] \
           --out <scratch dir> [--transcripts <a session's subagents dir> ...]

   It prints, per Critic goal, the findings both raised, only the Critic raised, and only the
   native review raised; each instrument's wall clock; native fork tokens when given transcripts;
   and progress toward the stop condition. With `--out` it writes `blind-sheet.json` and
   `blind-key.json`.
2. Hand `blind-sheet.json` alone to a verifier that has not seen the key. A fresh subagent is
   enough: have it read the code at each finding's location and answer each item's `ask`. That is
   "same defect?" for a pair the file match proposed, "real defect?" for a unique finding, and,
   for a native-only finding, which Critic goal it falls under.
3. Join the answers to `blind-key.json` and fill in the decision table below.

## Decision table (#1130 step 6)

A goal is ceded to the native review when the native review raised most of that goal's
verified-real findings, **and** that goal's unique verified-real yield per review is small against
its cost. The thresholds are the owner's to set when they read the table; this file does not
pre-commit them.

## Stop

The experiment stops after four weeks or sixty paired reviews, whichever is later. `compare.py`
prints `stop: True` once both hold. Record the table and the owner's decision on #1130, then
remove the pairing (or keep it, if the owner rules so).
