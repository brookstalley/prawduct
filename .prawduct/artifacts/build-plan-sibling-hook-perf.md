---
artifact: build-plan
version: 1
scope: sibling-hook-perf
branch: fix/sibling-hook-perf-and-friction
partition: serial — two small chunks in distinct files; one builder is cheaper than briefing a delegate on the coverage-cache contract
depends_on:
  - artifact: data-model
  - artifact: nonfunctional-requirements
governed_by:
  - artifact: data-model
    dispositions:
      - "verdicts are computed from the append-only fact ledger, never from mutable model-written state → conforms: the tree-key memo holds no fact and no model writes it; deterministic code computes each key from a git tree"
      - "facts are immutable and append-only → inapplicable, because no fact is written or changed"
      - "derived views are disposable and never authoritative → conforms, by the argument verdict_cache.py already makes: the memo is keyed by every input the key is a function of (an immutable tree SHA, plus the code identity of the judgeable-path classifier). A hit therefore replays a computation whose inputs have not changed, and deleting the file loses nothing but time"
      - "a governance document reaches a terminal state → conforms: this plan is archived at merge"
      - "issue-standard title rules → conforms: #931–#936 were filed through /prawduct:backlog"
      - "a newer-schema fact is a loud block → inapplicable, because the memo is not a fact; a schema mismatch is a cache miss"
      - "two stores, two lifetimes → conforms: the memo sits beside verdict-cache.json in the per-clone, gitignored <git-common-dir>/prawduct/"
      - "backlog_service_repo is authoritative → conforms"
  - artifact: nonfunctional-requirements
    dispositions:
      - "review wall-clock is P0 → inapplicable, because no reviewer payload changes; hook wall-clock is what improves"
      - "proportionality ratchets both ways → conforms: canary check 1 has fired on every session that changes code without a test, and it produced no blocking finding; #164 (owner, ready) rules it deleted, with Critic Goal 1 as its covering surface"
      - "state-file growth is an advisory, never a block → conforms: the memo is capped, and a full memo evicts; it never refuses"
      - "review rigor is stage-keyed → inapplicable, because no review stage changes"
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session → inapplicable"
      - "authority fails closed; advice fails soft → conforms: an unreadable tree is never memoised, so it still denies a free edge; an unreadable or mismatched memo is a miss, never a grant"
      - "local-first governance coordination → conforms: one more atomically written file beside the evidence store"
      - "the plugin writes nothing into a governed repo except its own state → conforms: the memo lives in the shared evidence store's directory"
      - "written in Python, never specific to Python → conforms: deleting canary check 1 removes a Python/JS-shaped test-file classifier; the api-versioning walk stays suffix- and name-based"
      - "prawduct guides and reviews, never implements → inapplicable"
      - "goals and verification bind; method is advice → conforms"
      - "every fact has one home → conforms: the clear-verdict rule's home stays session-hygiene.md; the digest and the gate message restate the trigger in one clause and point there"
---

# Build Plan: sibling-repo hook latency and governance friction

## Problem

The 2026-09-30 investigation of sibling repos found two things. The full numbers are in the issue
bodies.

- **Hook latency grows with the age of the evidence store.** It does not depend on the plugin
  version. Every SessionStart and every Stop re-keys every tree the store mentions, running one
  `git ls-tree` per tree, and the memo lasts only for the process. On a puzzles snapshot that is
  about 4 s of a 6.4 s hook, and it was the same for every cached version from 3.5.1-dev.2 to
  3.7.0-dev.2. discodon, with 1,743 trees, reached a Stop p90 of 62 s (#931). On top of that,
  SessionStart spends about 1.1 s in an api-versioning probe that rglobs the whole tree four
  times, walking into `.venv` and `node_modules` before filtering them out (#936).
- **Four smaller governance defects:**
  - The `clear-verdict` gate fires because the model treats processes that run on their own as
    work a clear would kill (#932).
  - The ledger names a project after the directory the session runs in, so devcontainer sessions
    record `venv` (#933).
  - `**Type:** bugfix`, which borrows the work-type vocabulary from `building.md`, is rejected
    (#934).
  - Canary check 1 fires on research scripts (#935). The owner has already ruled this check
    deleted in #164.

## Success

- A second SessionStart or Stop over an unchanged store runs no `git ls-tree` for trees it has
  already keyed, and none for trees git no longer holds. On the puzzles snapshot the coverage
  verdict's warm cost no longer depends on the store's size (4.1 s down to 0.05 s).
  [DECISION: the plan's first target, a warm Stop under 1.5 s, is replaced by this one. Measured,
  the warm Stop is about 2.1 s. The remainder is about 68 git calls spread across other gates,
  which do not grow with the store, plus the base-advance diagnosis's per-candidate diffs, which
  do. A batch replacement for those diffs cannot see mode-only changes, so it would fail open. They
  are filed as a follow-up rather than forced into this plan.]
- An unreadable tree still denies a free edge. A memo that is corrupt, of the wrong schema, or
  written under a different code identity gives a miss, never a grant.
- `Codebase` walks the tree once, pruning `_SCAN_SKIP_DIRS` as it descends, and every scan
  primitive filters that one listing.
- The ledger and review-stats label a devcontainer or worktree session with the origin remote's
  repo name.
- `**Type:** bugfix`, and the other work types in `building.md`, parse as `code`.
- Canary check 1 is gone. Its tests are replaced by a test pinning its absence, and #935 closes
  under #164's ruling.
- The clear-verdict teaching text in the digest, the gate message and session-hygiene says that a
  process which runs on its own survives a clear.

## Out of scope

- Relabelling discodon's existing `venv` ledger rows.
- The rest of #164: ruff, check 3, `test-reference-verify`, the manifest table and canary ledger
  facts.
- Changing any coverage semantics. `is_judgeable_path` and the free-edge relation are untouched.

## Requirements Confidence: High

The owner asked for every issue to be filed, prioritized and fixed on 2026-09-30. Each item
carries its measured evidence. The only direction that changed after filing is #935: #164 already
rules its check deleted, so that is the fix used here.
[ASSUMPTION: the origin remote's repo name is the right project label | LOW impact | the label only groups telemetry] Resolved at build: the committed `product_identity.name` comes first and the origin second. The label changes this causes for three checkouts are recorded as a [DECISION] in the change-log entry.

## Status

- [x] Chunk 01: hook latency — persistent tree-key memo (#931) and a single pruned codebase walk (#936)
- [ ] Chunk 02: friction — clear-verdict text (#932), ledger project name (#933), `bugfix` alias (#934), canary check 1 removed (#935, part of #164)
Context: Chunk 01 committed 2026-09-30 (ticked at commit, as a short plan does). Chunk 02 is built and committed; its box waits for the boundary cumulative review, which is every chunk's review on this short plan. Both chunks get their review from the one cumulative review at the boundary (a short plan).

## Chunk 01: hook latency

**Type:** code
**Files:** `plugin/lib/tree_key_memo.py` (new), `plugin/lib/gates.py` (`_tree_key_fn`),
`plugin/lib/advisory_store.py` (`Codebase`), the docstrings that describe the cost
(`verdict_cache.py`, `evidence.py` near `TREE_COUNT_ADVISORY`), `.gitignore` mirrors if the
store's directory needs a new entry, `tests/test_tree_key_memo.py`, and
`tests/test_advisory_store*.py`.
**Done when:** the memo tests cover hit, miss, a corrupt file, a code-identity change, `None` never
memoised, the cap, and concurrent entries surviving a flush. A walk test pins the pruning. The
benchmark on the scratch snapshot is re-run and its warm number is recorded in the change-log.
Committed and ticked at commit.

## Chunk 02: friction fixes

**Type:** code
**Files:** `plugin/bin/prawduct-hook` (clear-verdict message), `plugin/methodology/session-digest.md`,
`plugin/methodology/session-hygiene.md`, `plugin/lib/ledger.py`, `plugin/lib/telemetry.py`,
`plugin/lib/core.py` or `gitstate.py` (one project-label owner), `plugin/lib/buildplan_refs.py`
(type aliases), `plugin/lib/compliance.py` (check 1 removed), and their tests.
**Done when:** each fix has a test that fails without it. The suite passes. The cumulative
Critic review has run and its blocking findings are resolved.
