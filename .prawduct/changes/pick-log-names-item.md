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

`pick` now runs one `git log -E --grep` per candidate over the checkout's integration base (the
same resolver the gates use: a configured `base_branch:`, else `origin/HEAD` outside the main
family, else `main`). Only a commit's subject line counts: git's grep reads the whole message, and
bodies mention items in passing ("why #165 stayed deferred"), so the same pattern is re-applied to
each returned subject and body-only matches are dropped, so a flag means work on the item and not
a passing mention. A candidate that commit subjects already name carries a `base_history` field
and, in human output, a `history:` line: "N commit(s) on <base> already name this item: <short
shas>; check what is left before building". It is advice only: no item is hidden or restaged.

The match is a whole reference. `#12` does not match `#123` or `#1204`, because the boundary is
spelled out in a form git's extended regex and Python's `re` read identically (`\b` is a GNU
extension), and one pattern serves both; another repo's `other/repo#12` does
not match either, while this tracker's own `owner/repo#12` does. Only a checkout's own tracker
is checked: when `--repo` is not the checkout's `origin` (a separate `backlog_service_repo`, or no
readable `origin`), commit numbers belong to another number space and nothing is annotated.

The check is bounded: one `git log` per candidate, for the first ten candidates, reading at most
a hundred message matches and counting at most twenty subject matches each, with five short shas
shown and ten seconds per call. An item mentioned in the bodies of more than a hundred newer
commits can have an older subject match missed; that undercount is accepted for advice. It fails
soft: an unresolvable base or a failed `git log` leaves candidates unannotated and prints one `warning:` on stderr naming the
cause. The two git reads live in `lib/backlog/transport.py`, the package's one subprocess owner.

## Consumer note
`/prawduct:backlog pick` may now show a `history:` line under a candidate. Read it before
building: some of the item may already be on your base branch. If your backlog lives in a repo
other than the code's `origin`, you will not see it.
