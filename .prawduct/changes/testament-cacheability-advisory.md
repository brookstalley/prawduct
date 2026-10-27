---
schema: 1
type: feature
scope: testament-cacheability-advisory
date: 2026-10-26
title: Tests testament cannot cache are surfaced as an advisory
---

testament's result cache never reuses a result from a test process that did something it cannot
replay, such as reading the live clock or running a subprocess. A cause that blocks every test in
a process is easy to write and invisible from inside the suite. In this repo one clock read in a
run-level hook kept about 300k of 577k executions uncacheable for a week, and nothing said so.

### Chunk 01: the probe

- `lib/testament_cache_probes.py` reads testament's per-worktree cacheability snapshot
  (testament#287): it lists `*.json` under testament's state directory (`$TESTAMENT_HOME/client/cacheability/`,
  else `~/.local/share/testament/...`) and keeps envelopes whose `root` is this worktree. No
  network and no process. Where testament is not used the directory is absent and the probe
  returns at once.
- It raises one `testament-cache:uncacheable-tests` advisory per suite whose full, current
  snapshot names a cause that is the sole blocker of some tests. Evidence is one `suite kind site scope`
  line per cause, sorted by its text and never by count, so a dismissal holds until the set of causes changes.
- A narrowed-only snapshot, an unknown envelope version, an unreadable file, or a commit outside
  this branch's history means the probe could not look, so an open advisory stays open.
- Only checked tokens reach the briefing: kinds and scopes as plain words, sites as
  `path:function`. testament's hints and the project's `why` strings are not carried.
- Registered in `probe_families.register_all`.

### Chunk 02: this change record

Built against testament#287's agreed envelope before testament has shipped it. Until a testament release
writes snapshots, the advisory is inert.

## Consumer note
If your tests run through testament, the session briefing can now tell you which causes keep
your test results from being cached, and how many tests each one alone is blocking. For each
cause you either fix it, or declare it expected in testament's configuration so it stops being
reported. Dismissing the advisory hides it until the set of causes changes. Nothing changes for
repos that don't use testament, or until a testament release writes the snapshot this reads.
