---
artifact: build-plan
version: 2
scope: hot-path-git-batching
depends_on: []
last_validated: 2026-06-21
lifecycle: completed
archived: 2026-08-10
released_in: v2.1.8
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

# Build Plan — Hot-Path Git Batching (STH-6Q9D)

**Problem.** The SessionStart (`clear`) and Stop (`stop`) hooks fan out more git
subprocesses than they need. Measured on a 20-source-file repo with one
accidentally-committed session file (instrumented `git` shim counting argv):

| Command | git call | count | cause |
|---|---|---|---|
| `clear` | `ls-files --error-unmatch` | **15** | `_untrack_session_files` issues one per session path |
| `clear` | `branch --show-current` | 4 | briefing `_get_current_branch` re-run across functions |
| `clear` | `status --porcelain` | 3 | re-run by each status-family probe |
| `clear` | `worktree list` / `rm --cached` / `rev-parse` | 1 each | — |
| `stop` | `status --porcelain` | **2** | `git_has_session_changes` + `_session_changes_are_doc_only` |

`clear` totals **25** git subprocesses (~940ms measured; 5–10s risk on
monorepos where each `git` invocation is dominated by repo-scan latency). Two
non-git costs compound it: `_has_product_code` (`lib/gitstate.py`) walks the
**entire** tree via `rglob("*")` — descending into `node_modules/` and `.git/`
before the filter excludes them — and that path fires exactly when a JS repo with
a large `node_modules` is being onboarded (pre-prefs / pre-discovery).

**Success.** The three groomed redundancies are removed without changing any
observable behavior:
1. `_untrack_session_files` finds tracked session paths in **one** batched
   `git ls-files -- <paths>` and untracks them in **one** `git rm --cached`,
   down from 15 `ls-files` + N `rm`.
2. The dense `status --porcelain` re-runs are captured once and threaded down via
   an optional parameter: `clear`'s `_check_previous_session_gates` collapses its
   3 probe re-runs to 1 capture, and `stop`'s preamble shares 1 capture across its
   2 probes (total `stop` status calls 3 → 2 — the third is an out-of-scope
   `lib/gates.py` call this changeset doesn't touch). Backward-compatible (param
   defaults to compute).
3. `_has_product_code` prunes `node_modules/`, `.git/`, `.prawduct/` at the
   directory level (pruned `os.walk`) and short-circuits on the first match,
   instead of enumerating the whole tree first.

Verified by re-running the instrumented harness with the full suite green and
every status/untracking behavior preserved. **Measured result:** `clear` drops
**25 → 11** git subprocesses — the headline being `ls-files` 15 → 1. The three
remaining `status --porcelain` calls on a *clean* harness are each a single,
legitimate call (the gate, the handoff, the post-mutation baseline); the gate's
own 3 → 1 collapse only shows on a *dirty* session (confirmed separately: with
real changes the gate captures porcelain exactly once, was three). `stop` is
3 → 2 on a session with changes (capture-once across its two probes; unchanged at
2 on a clean session because the second probe was already skipped). The
`branch --show-current` ×4 remains (out of scope — see below).

**Out of scope.**
- **`branch --show-current` ×4 in `clear`** (newly measured, not in the groomed
  STH-6Q9D targets). It spans three *separate* top-level briefing functions
  (`staleness_scan`, `assemble_session_briefing`, `_parse_wip`), so "capture once"
  there is a cross-function thread, not a local change — a different shape from the
  three groomed targets. Filed as **STH-3K7M** (cross-linked to STH-6Q9D) rather
  than folded in (scope discipline; the local status capture already removes the
  denser cluster).
- **Clear-wide status caching.** `cmd_clear` *mutates* the git index mid-flow
  (`_untrack_session_files` `rm --cached` at ~L452, then the deliberate
  post-mutation baseline capture at ~L603). A process-wide status cache would
  serve a stale snapshot across that mutation. "Capture once" is therefore scoped
  to *read-only regions* (the gate function, the stop preamble), never clear-wide;
  the L603 baseline stays its own post-mutation read.
- No new `prawduct-hook` subcommand, no behavior change, no signature change to any
  *caller* outside the two threaded hot paths (the new param is optional).

## Requirements Confidence

**Level:** High — this is a measured optimization with behavior-preservation as the
contract; the groomed item (STH-6Q9D) names the three targets and the affected files.

**Open assumptions:**
- [ASSUMPTION: `git ls-files -- <pathspecs>` with multiple bare paths returns only
  the tracked subset (untracked/absent paths print nothing, exit 0) — the standard
  pathspec contract, so the batched call replaces the per-path
  `--error-unmatch` probe loop without a behavior change | LOW impact | covered by
  a multi-tracked-file test]
- [ASSUMPTION: a pruned `os.walk` skipping `node_modules`/`.git`/`.prawduct` yields
  the same product-code verdict as the current rglob+filter, because those are
  exactly the directories the filter already excludes (plus the per-file
  `_is_framework_tooling` and `conftest.py` checks, retained) | LOW impact |
  covered by detect/exclude tests]

## Baseline Measurement (optimization discipline)

- Suite: **1351 passed, 1 skipped** on `feature/hot-path-git-batching` (off
  `develop`, with the cherry-picked v2.1.6 CHANGELOG baseline repair) — this is the
  *pre-change* baseline. After the +13 new tests in this chunk the suite is **1365
  passed, 0 failed** (the env-conditional skip ran this session); that is the figure
  the change-log and test-evidence record carry.
- git-call counts above are the pre-change baseline. Post-change measured:
  `clear` **25 → 11** (`ls-files` 15 → 1); gate status **3 → 1** on a dirty
  session; `stop` status **3 → 2** on a session with changes. The regression
  instrument is `tests/test_hot_path_git_batching.py` (batched-call counts +
  capture-once + prune contracts), not a wall-clock number (too noisy to gate on).

## Status

- [x] Chunk 01: Batch untracking + capture-once status + pruned product-code walk

Context: chunk 01 BUILT and merge-ready (2026-06-21, single work cycle, branch
`feature/hot-path-git-batching` off `develop`; the sibling
`feature/hook-cli-robustness` bundle stays merge-ready and untouched). Cumulative
Critic clean (0 blocking / 0 warning / 4 note, all resolved); verify-resolutions
chain extends to HEAD; 1365 pass / 0 fail. PR not yet created (user chose backlog
work, didn't ask to PR). `views_enabled: true` — the checkbox flips at release via
the `scope=hot-path-git-batching` change-log tag.

## Chunks

### Chunk 01: Batch untracking + capture-once status + pruned product-code walk

Three independent, behavior-preserving optimizations on the shared `clear`/`stop`
hot-path surface — bundled into one chunk (one cumulative Critic review) because
they share the surface and the "no observable behavior change" contract.

**D1 — Batch `_untrack_session_files`** (`bin/prawduct-hook`). Replace the
per-path `git ls-files --error-unmatch` + `git rm --cached` loop with: one
`git ls-files -- <all session paths>` to learn which are tracked, then (only if
any matched) one `git rm --cached --quiet -r -- <matched paths>`. Preserve every
current contract: returns the list of untracked paths, never raises, early-returns
on a non-repo (`rev-parse --git-dir` guard stays), and untracks the same set.
15 `ls-files` + N `rm` → 1 + (0 or 1).

**D2 — Capture-once `git status --porcelain`** (`lib/gitstate.py` +
`lib/briefing.py` + `bin/prawduct-hook`). Add an optional
`status_output: str | None = None` parameter to the status-family probes
(`git_has_session_changes`, `_session_changes_are_doc_only`, `git_has_code_changes`,
`_get_session_changed_files`): when provided, use it; when `None`, compute via
`git_status_output` (unchanged default → every existing caller and test is
unaffected). Thread a single capture at the two dense callers:
`_check_previous_session_gates` (`lib/briefing.py`, its 3 probe re-runs → 1
capture) and the `cmd_stop` preamble (`bin/prawduct-hook` ~L690–691, its 2 probes
share 1 capture).

**D3 — Prune `_has_product_code` walk** (`lib/gitstate.py`). Replace
`project_dir.rglob("*")` with a pruned `os.walk` that removes `node_modules`,
`.git`, and `.prawduct` from `dirnames` in place (so the walk never descends into
them) and returns `True` on the first product-code file found (short-circuit).
Keep the per-file exclusions (`conftest.py`, `_is_framework_tooling`). Same verdict,
no full-tree enumeration.

- **Type:** code (optimization). Full Critic review applies.
- **Done when:** all three deliverables landed; new tests cover batched-call counts
  + preserved behavior for each; full suite green; the instrumented harness confirms
  `clear` 25 → 11 git calls (`ls-files` 15 → 1) and the gate captures status once
  on a dirty session; `/prawduct:critic` run and blocking findings resolved;
  reflection captured; build plan Status updated.

## Verification Strategy

- **Behavior preservation (the contract).** Unit tests assert, for each
  deliverable, that the observable result is unchanged: `_untrack_session_files`
  untracks exactly the tracked session files (and only those), handles a non-repo,
  and handles multiple tracked files in one batch; the status-family probes return
  identical results whether `status_output` is passed or computed; `_has_product_code`
  still returns `True` for product source and `False` for a node_modules-only /
  framework-tooling-only / `.prawduct`-only tree.
- **Subprocess-count regression.** A test (or the committed harness) monkeypatches
  / shims `git` to count invocations and pins the new counts, so a future change
  that reintroduces fan-out fails loudly.
- **Full suite** must stay green — no existing status/untracking/product-code test
  may change (behavior is preserved; tests are contracts).
