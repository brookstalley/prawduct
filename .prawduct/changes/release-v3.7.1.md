---
schema: 1
type: chore
scope: release-v3.7.1
date: 2026-10-19
title: v3.7.1 is cut, and develop reopens on 3.7.2-dev
---
**27 scopes and 27 change-log entries. `K = 0`, so this took the whole-develop promotion path with
nothing withheld.** Tag `v3.7.1` was published with the CHANGELOG section as its Release notes.
`check-released v3.7.1` reports 3 of 3 verified, and the hand-dispatched `verify-release` run and
the tag-push run are both green. To re-derive the scope set, grep for `release=v3.7.1` in
`change-log.md` and `change-log-archive/`.

**A patch, by owner decision over the agent's 3.8.0 recommendation.** The alignment pass and the
default-on `clear-reason` gate matched the minor-tier precedent. The owner chose the ratified
conservative-versioning norm instead. `.prawduct/artifacts/release-plan-v3.7.1.md` records both
sides. Two field-bug PRs merged ahead of the cut (#1018 for #1011, and #1019 for #217, #1004,
#1005 and #1006). The cut wrote consumer notes for ten scopes the open CHANGELOG section did not
name, archived 13 shipped plans, and moved 18 shipped entries into `change-log-archive/2026-10.md`.
Step 11a's suite run on the prep tree was green the first time.

## Consumer note
none: release mechanics for v3.7.1, whose notes are already published
