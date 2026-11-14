---
schema: 1
type: feature
scope: gate-clarity
date: 2026-11-11
title: the Stop hook stops slowing with history, both gates say why a span is uncovered, the Stop gate stops judging imported history, and out-of-remit paths stop reading as unjudged
closes: [brookstalley/prawduct#937, brookstalley/prawduct#1000, brookstalley/prawduct#1098, brookstalley/prawduct#682]
---
Four frictions a governed product's builder paid at the gates.

**The base-advance diagnosis no longer scales with the store (#937).** Its condition 2 asked git
for one pathspec-limited diff per distinct prior review endpoint, on every warm Stop, so the cost
grew with every review a repo ever recorded. It now sends every (candidate, anchor) pair to git in
one `git diff-tree --stdin` call through the new `evidence.tree_diffs`, and persists nothing.

Every failure is asked again one pair at a time through `tree_diff`, so an unreadable tree still
degrades and denies exactly as before. That covers a pair git skips, a malformed tree id, a batch
that fails or cannot be parsed, and a path set holding a newline. A mode-only change still denies
the transfer.

Measured on the diagnosis alone, warm, with the same command before and after (2026-11-11):

| Repo, span | Before | After |
|---|---|---|
| this repo, PR-sized | 3.0–4.6 s, 137 git calls | 0.15 s, 4 calls |
| this repo, release-sized | about 24 s, 860 calls | about 0.85 s, 3 calls |
| discodon | about 9 s, 200 calls | under 0.9 s, 5 calls |

The verdict was identical before and after in every case.

**Both gates say why a span is uncovered (#1000).** `coverage.explain_uncovered` names the causes
that hold, and both the PR gate (`check-cumulative-critic`) and the Stop gate's Critic blocker
render them as one `CAUSE:` line after the `uncovered:` line. The causes are:
- the committed head changed since the last review on this branch, with up to three files;
- the base advanced since that review, and whether the branch's own diff also changed, which
  rules out the transfer;
- uncommitted paths, which the PR gate ignores but a suite run in that tree vouches for;
- no review on this branch at all.

It never raises. It renders `CAUSE: unavailable (<reason>)` when it cannot tell. When suite-coupled
paths are uncommitted, the transfer near-miss remedy now gives a route that reaches the state: set
them aside with `git stash push`, run and record the suite, re-run the gate, then `git stash pop`.
Both names of a staged rename are listed. When the index has deleted a path, which
`git stash push -- <path>` refuses, the route sets the whole working tree aside instead. No verdict
changes.

**The Stop gate does not demand review of history the session did not write (#1098).** A
relax-only third arm in `gates.session_review_verdict` uses a new
`coverage_algebra.excused_gap_verdict` to find the session span's unreviewed intervals. When none
of their judgeable files is one this session authored, the verdict is covered and a NOTE names the
excused files. Authorship comes from the same reflog read the firing span uses, and when that read
cannot be completed the verdict is unchanged. Whenever the arm declines for a reason other than the
session's own unreviewed files, the block's reason ends with `imported-history excuse not applied:`
and the reason. The arm relaxes only `uncovered`, never `blocked`, and
a blocker anywhere on the excused path still blocks. Every untracked file counts as authored, a
file both authored and imported stays required, and its search cap can only deny. The PR gate is
unchanged.

**Out-of-remit paths stop reading as unjudged (#682).** `test-reference-verify` now reports changed
non-Python paths in `changes_out_of_remit`, with a record-level `changes_out_of_remit_reason`.
`changes_unjudged` keeps only Python files with no symbols and deleted files. With
`changes_referenced` and `changes_unreferenced`, the four lists partition the changed set. The
gate and the green-is-evidence trigger read both lists, so a record written before the split still
reads correctly. `changes_unchecked`, the same list under its old name, stays as a deprecated alias
until a major release.

The tests are new `tests/test_base_advance_diagnosis_cost.py` and
`tests/test_cumulative_gate_explain.py`, new classes in `tests/test_coverage_algebra.py` and
`tests/test_session_critic_gate.py`, and updates to the verifier and coverage-gate tests. Each
rendered message has an assertion on its text.

## Consumer note
- **The Stop hook is faster on repos with a long review history.** The base-advance diagnosis no
  longer grows with the number of past reviews.
- **An `uncovered` verdict says why.** Both `check-cumulative-critic` and the Stop gate now print a
  `CAUSE:` line naming whether the base advanced, the branch's head changed, or uncommitted files
  are in the way. When uncommitted suite-coupled files are the cause, follow the remedy's
  `git stash push` route instead of running another review.
- **Syncing or switching branches no longer drags imported files into the Stop gate's demand.**
  The Stop gate judges the files this session wrote and names the ones it excused. The PR gate
  still requires review of the whole branch.
- **Readers of the test-evidence record should also read `changes_out_of_remit`.** Non-Python
  changed files now land there instead of in `changes_unjudged`. `changes_unchecked` still carries
  the same list under its old name, until a major release.
