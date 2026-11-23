---
schema: 1
type: feature
scope: pick-log-names-item
date: 2026-11-23
title: backlog pick flags a ready item whose number the base branch's log already names
closes: [brookstalley/prawduct#1204]
---
`pick` offered an item as ready when two of its three legs had already shipped on the base
branch, because the issue stayed open for the third and nothing at pick time looked at the code
history. A builder was dispatched and spent its run finding that out.

`pick` now runs one `git log -E --grep` per candidate over the checkout's integration base (the
same resolver the gates use: a configured `base_branch:`, else `origin/HEAD` outside the main
family, else `main`). A candidate that commits already name carries a `base_history` field and,
in human output, a `history:` line: "N commit(s) on <base> already name this item: <short
shas>; check what is left before building". It is advice only: no item is hidden or restaged.

The match is a whole reference. `#12` does not match `#123` or `#1204`, because the boundary is
spelled out in extended-regex form (`\b` is a GNU extension); another repo's `other/repo#12` does
not match either, while this tracker's own `owner/repo#12` does. Only a checkout's own tracker
is checked: when `--repo` is not the checkout's `origin` (a separate `backlog_service_repo`, or no
readable `origin`), commit numbers belong to another number space and nothing is annotated.

The check is bounded: one `git log` per candidate, for the first ten candidates, at most twenty
commits each, five short shas shown, ten seconds per call. It fails soft: an unresolvable base or
a failed `git log` leaves candidates unannotated and prints one `warning:` on stderr naming the
cause. The two git reads live in `lib/backlog/transport.py`, the package's one subprocess owner.

## Consumer note
`/prawduct:backlog pick` may now show a `history:` line under a candidate. Read it before
building: some of the item may already be on your base branch. If your backlog lives in a repo
other than the code's `origin`, you will not see it.
