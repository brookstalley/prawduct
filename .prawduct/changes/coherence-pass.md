---
schema: 1
type: fix
scope: coherence-pass
date: 2026-11-16
title: The tech-debt cycle's surfaces agree with each other and with the code
closes: []
---
A whole-result coherence pass over the tech-debt cycle (#1185) found seams where pieces built
separately disagreed. Each is fixed through one owner:

- **A suite in flight is never a review finding.** The Critic's protocol (goals 1–3, the review
  protocol, the skill) reads `running:` as "wait, or note it", and a `(running)` void from
  `verify-coverage` blocks nothing; the Critic and its reviewer agent are granted `test-status*`,
  so the printed `test-status --wait` remedy is runnable.
- **A suite refusal prints its remedy once.** The gate verdicts return the finding only;
  `test-status` joins finding and remedy, and exit 7, the release check's `unproven-suite` line and
  the coverage-transfer note each print the finding plus `suite_remedy` once.
- **`check-operator-verification` speaks in the voice of its state.** With the requirement off, an
  unreadable queue prints a note that says nothing is blocked; a `lib/` that will not load exits 3
  ("could not evaluate") instead of passing silently. The PR skill's exit-3 row names every state.
- **The `.prawduct/` ignore advice is safe to follow and has one owner.** It leads with replacing a
  wholesale rule by the printed lines; deleting the rule says "then run `prawduct-hook
  update-gitignore`" in the same sentence, so no session file is exposed. The PR gate, the PR
  skill and `archive-change-log` point at `prawduct-hook update-gitignore --dry-run` instead of
  spelling their own partial lines. `contract-ignored-by-rule` is a `warn` and its evidence no
  longer names internal code.
- **The PR gate refuses what the release refuses.** With the change log untracked,
  `check-change-log-entry` reads the on-disk log and refuses its pending legacy entries, as
  `check-releasability` does.
- **A missing findings-cache pointer heals like a wrong one.** No cache, an undecodable cache, no
  `fact_id` or a fact missing from the store all ask the branch-review owner before demoting a
  verify round; a fresh worktree of a reviewed branch keeps its review. An undecodable cache no
  longer crashes `infer-critic-mode`. When no review anchors on this branch, the briefing says so
  plainly and shows none of another branch's counts.
- **The chunk-shim retirement finishes.** `begin_review(chunk=…)` is gone, the review manifest
  writes only `chunks`, and the ledger event reads the first of them; the unread
  `native_review.text_path` manifest key is removed.
- **Head-detach detection runs wherever a review consolidates** — the explicit command, the
  SubagentStop hook and the Stop backstop — through `consolidate` itself.
- **Prose names doctor checks, never their numbers**, and a test keeps every shipped prose file and
  printed string that way.

## Consumer note

`contract-ignored-by-rule` is now a warning and its advisory id changes, so a dismissal of the old
advisory no longer applies; it re-surfaces once. A script that parsed the old `test-status` or
exit-7 text should expect the remedy once, after the finding. A review manifest no longer carries
`chunk` or `native_review.text_path`; read `chunks`.
