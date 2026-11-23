---
schema: 1
type: feature
scope: pick-log-names-item
date: 2026-11-23
title: backlog pick flags a ready item whose number a base-branch commit subject already names
closes: [brookstalley/prawduct#1204]
---
`pick` offered an item as ready when two of its three legs had already shipped on the base
branch, because the issue stayed open for the third and nothing at pick time looked at the code
history. A builder was dispatched and spent its run finding that out.

`pick` now reads the checkout's integration base once and flags each candidate whose number a
commit subject names. The base is the repo's (`coverage.repo_base_branch`: a configured
`base_branch:`, else `origin/HEAD` outside the main family, else `main`), not a bound plan's
`base:` as the gates use, because the question is what has shipped, and a plan's base can be an
unshipped stack branch. The moving `HEAD~1` fallback is refused (the branch's own commits would
read as shipped, as `chain_bound` already holds), so the check is skipped with a `warning:`.
A candidate that commit subjects already name carries a `base_history` field and, in human
output, a `history:` line: "N commit(s) on <base> already name this item: <short shas>; check
what is left before building". It is advice only: no item is hidden or restaged. The result
also carries a top-level `base_history` indicator, `{checked: true, base, walked, capped}` or
`{checked: false, reason}`, so a check that never ran (another tracker, no origin, no base, git
failed) is not mistaken for one that found nothing.

The match is a whole reference, read in Python over each subject. `#12` does not match `#123` or
`#1204`; another repo's `other/repo#12` does not match, and neither does `xowner/repo#12`, while
this tracker's own `owner/repo#12` does, in any letter case (GitHub names are case-insensitive).
Only a checkout's own tracker is checked: when `--repo` is not the checkout's `origin` (a
separate `backlog_service_repo`, or no readable `origin`), commit numbers belong to another
number space and nothing is annotated.

The check is bounded by one walk, not one per candidate: a single
`git log --max-count=1000` of the base's newest commits (ten seconds), matched against every
candidate in Python. The first version ran a `git log --grep` per candidate, which stops after N
matches, so for an item few messages name each call walked the whole history. This departs from
the issue's per-candidate method because its goal is a bounded cost, which one walk serves
better. 1000 commits is weeks of a busy integration branch, the horizon in which legs ship while
an issue stays open; an item named only further back is an undercount accepted for advice, and
when the window was full the note says "in the last 1000 commits" and `capped` is true. It fails
soft: an unresolvable base or a failed `git log` leaves candidates unannotated and prints one
`warning:` on stderr naming the cause. The git reads live in `lib/backlog/transport.py`, the
package's one subprocess owner.

## Consumer note
`/prawduct:backlog pick` may now show a `history:` line under a candidate. Read it before
building: some of the item may already be on your base branch. If your backlog lives in a repo
other than the code's `origin`, you will not see it.
