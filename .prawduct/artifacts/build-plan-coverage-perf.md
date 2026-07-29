---
artifact: build-plan
version: 1
scope: coverage-perf
governed_by:
  - artifact: nonfunctional-requirements
    dispositions:
      - "Run-count is the lever for review wall-clock → this plan's whole subject. The measured gate spends 316 s of a 318 s verdict inside 5,597 `git diff` subprocesses. Chunk 01 replaces the pairwise probe with one `git ls-tree` per tree (O(n) run-count), Chunk 02 makes the steady state O(new trees). The norm is satisfied by engineering the run-count out, not by accepting the cost."
      - "State-file growth is an advisory warning that prompts compaction — never a hard block → governs the deliberately-deferred compaction work. `evidence.jsonl` is 2.3 MB / 672 facts and grows forever. Once free-edge probing is O(n), store size stops being a latency cliff and becomes ordinary growth, which this norm says to *advise* on, not gate. Compaction is therefore FILEd with a trigger (§ Compaction) rather than built here."
  - artifact: architecture
    dispositions:
      - "Authority fails closed; advice fails soft → conforms, and it constrains the optimisation. A tree whose key cannot be computed (missing object, git failure) must yield NO free edge, exactly as a `diff_fn` returning `None` does today. Speed may never buy a free pass; the fast path must fail in the same direction as the slow one."
      - "Local-first: process-spawn + files + git, no network, no third-party dependencies → conforms. `git ls-tree` and a stdlib `hashlib` digest; the Chunk 02 cache is a JSON sidecar beside the store it serves."
last_validated: 2026-07-29
---

# Build Plan — the composed-coverage gate stops being quadratic

The PR-path gate `check-cumulative-critic` takes **5 min 12 s** on this branch and
returns `uncovered`. This plan makes it fast without changing a single verdict,
then strengthens the session-boundary discipline that a slow gate was eroding.

## Requirements Confidence

**Level:** High. The defect is measured, not inferred.

- **Problem.** `coverage_algebra._find_path` probes free edges *pairwise*: for every
  dequeued node it shells `git diff --name-only` to every unvisited node. Measured on
  the live store — 672 facts, 293 distinct trees — that is **5,597 subprocesses and
  316 s of the 318 s verdict (99.4%)**. `_cached_diff_fn` memoises repeat *pairs*
  only; the count is inherently O(n²) in nodes. The store is append-only, shared by
  every worktree of the clone, and never pruned, so this degrades monotonically. It
  gates `/prawduct:pr create`, so the realistic outcome is a **waived** gate — worse
  than no gate, because a waiver reads as satisfied.
- **Success.** The same verdict — `covered` / `blocked` / `uncovered`, same path, same
  attribution — in seconds rather than minutes, with the run-count linear in trees.
  `tests/test_coverage_algebra.py` passes unmodified: it is the behavioural contract,
  and this is an optimisation, so the tests must not move (Principle 1).
- **Out of scope.** Pruning or compacting `evidence.jsonl` (§ Compaction — deferred
  deliberately, with a trigger). Splitting `is_judgeable_path` (§ Rejected). Any
  change to what counts as judgeable.

## The insight: free edges are an equivalence relation, not a pairwise question

A free edge `a → b` exists iff `diff(a, b)` contains no judgeable path — iff the two
trees agree on **every judgeable (path, blob)**. That is an equality of per-tree
values, so it never needed a pairwise probe:

```
key(tree) = sha256 over sorted "<blob-sha> <path>" for judgeable paths in tree
key(a) == key(b)  ⟺  a → b is a free edge
```

Free-edge connectivity collapses to grouping nodes by key: every key-class is a
clique, and the search treats a class as one node. One `git ls-tree -r` per tree
(measured **27.5 ms**, 393 files) replaces the pairwise diffs — **~8 s uncached for
293 trees, versus 316 s**, with identical semantics because the predicate is
identical.

Three constraints this must respect:

1. **Unreadable trees yield no free edge.** `ls-tree` failure ⇒ `key = None` ⇒ the
   node joins no class — the same direction as today's `diff_fn → None`.
2. **`files` on a `free` path step is still owed.** The verdict's path steps carry the
   interval's file list for attribution. Compute it lazily via the existing `diff_fn`
   for the O(path-length) free steps actually returned — not for all n².
3. **The key depends on the judgeability predicate, which changes.** It changed today.
   Any persisted key must be invalidated when the rules move (Chunk 02).

## Chunks

### Chunk 01 — the tree-key free-edge oracle

**Type:** code

Replace pairwise probing with key-class grouping.

- `evidence.tree_entries(project_dir, tree) -> list[tuple[str, str]] | None` — `(blob,
  path)` pairs from `git ls-tree -r -z --full-tree` (`-z` because git quotes paths with
  special characters, and this codebase has already been bitten by quoted-path parsing
  in `parse_porcelain_line`). Returns `None` on any git failure. Pure I/O; no policy.
- `coverage_algebra`: `_find_path` and `coverage_verdict` accept an optional
  `key_fn(tree) -> str | None`. When supplied, free neighbours come from the key class;
  when absent, today's pairwise probe is retained so the injected-table tests keep
  exercising the reference implementation.
- `gates._tree_key_fn(project_dir)` builds `key_fn` from `evidence.tree_entries` +
  `coverage_algebra.is_judgeable_path`, memoised per invocation. Wire into both
  `check_cumulative_critic` and `session_review_verdict`.

**Done when:**
- `tests/test_coverage_algebra.py` passes **unmodified**.
- A new equivalence test asserts the two oracles return the same verdict and the same
  path kinds over a generated tree/fact table — the property that makes the fast path
  trustworthy rather than merely fast.
- A test pins constraint 1 (unreadable tree ⇒ no free edge) and constraint 2 (`free`
  steps still carry `files`).
- Re-measured on the live store: subprocess count and wall-clock recorded here beside
  the 5,597 / 316 s baseline.
- Full suite green; `/prawduct:critic`.

**Measured 2026-07-29, same store (672 facts, 293 trees), same `uncovered` verdict:**

| | before | after |
|---|---|---|
| `git diff` subprocesses | 5,597 | **0** |
| `git ls-tree` subprocesses | 0 | **294** |
| verdict wall-clock | 316 s | **7.4 s** |
| `check-cumulative-critic` end-to-end | 5 min 12 s | **7.95 s** |

19× fewer subprocesses, 43× faster, identical verdict. Diffs fall to zero because an
`uncovered` search returns no path, so no free step needs attribution — the deferral in
`_attribute_free_steps` is doing exactly what it was written for. Suite: 2795 passed,
7 skipped. `tests/test_coverage_algebra.py` unmodified at 25 passing, plus 5 new
equivalence/regression tests.

### Chunk 02 — the key cache, and the predicate fingerprint that guards it

**Type:** code — **DEFERRED 2026-07-29, not started.**

Chunk 01 took the gate from 5 min 12 s to 7.95 s; this chunk would take it to roughly
0.2 s warm. That is a real gain at every session end, fleet-wide — but it is an
optimisation of an optimisation, and it was never part of the request that opened this
work. Shipping the 43× and stopping keeps the reviewable diff small and honest
(Principle 11). **Trigger to pick it up:** a warm `check-cumulative-critic` exceeding
5 s, which is the same threshold § Compaction watches — by then the store has roughly
doubled and the linear cost is what is left to attack. The design below is complete
enough to build from as written; nothing was learned in Chunk 01 that invalidates it.

Trees are immutable, so a key is permanently cacheable — the steady state should be
O(new trees), not O(all trees).

- Sidecar `<git-common-dir>/prawduct/tree-keys.json`:
  `{"schema": 1, "predicate": "<digest>", "keys": {"<tree>": "<key>"}}`.
- `predicate` is a digest over `_TRIVIAL_PROTECTED_PATHS` **and** `METADATA_PREFIXES`.
  A mismatch drops the whole cache. This is the load-bearing half: today's widening
  changed judgeability, and a stale key would silently assert a free edge that no
  longer exists — a fail-*open*, the one direction this system may not fail.
- Read-through, write-back once per invocation; any I/O failure degrades to uncached
  (correct, merely slower).

**Done when:**
- Tests: cold miss populates; warm hit avoids `ls-tree`; predicate change invalidates;
  unreadable/corrupt cache degrades to uncached without error.
- Re-measured warm wall-clock recorded.
- Full suite green; `/prawduct:critic`.

### Chunk 03 — a handoff is prepared, never proposed

**Type:** code

**This amends an existing norm rather than inventing one.** `session-digest.md:46-51`
already says to write forward notes "at each chunk close, not when the user asks to
clear," and `building.md` § Session Scope Discipline already lists writing them as step
7 of 7. Neither *prohibits* asking. The amendment closes that gap.

The rule: **after sustained work, never ask whether to prepare a handoff — prepare it,
say so, and state that `/clear` is safe.** The user may continue in place; that costs a
few tokens. Asking costs the user a round-trip *and*, if they have stepped away, a
large context replayed into a cold cache — which is the exact cost the handoff exists
to avoid. Asymmetric, so the default is unconditional.

- `plugin/methodology/building.md` § Session Scope Discipline — the prohibition, stated
  once, in the existing steps 1-7 block.
- `plugin/methodology/session-digest.md` — the always-injected surface, so every
  consuming product inherits it rather than it being a prawduct-local habit.
- `plugin/methodology/reflection.md` if the boundary protocol needs the mirror.

**Token budget is the binding constraint.** `building.md` has ~5 tokens of headroom and
`session-digest.md` is budget-tested too. Measure with
`tests/test_v5_methodology.py::estimate_tokens` and **trim before adding** — never
raise a budget to fit a rule in.

**Done when:**
- `tests/test_v5_methodology.py` green *without* raised budgets.
- The digest change is verified to reach a consuming repo (the digest is injected, not
  read on demand).
- `/prawduct:critic`; change-log entry tagged `scope=coverage-perf`.

## Compaction — deferred, with a trigger

The store is 2.3 MB / 672 facts / 293 trees and grows forever. **Pruning is not the fix
for the latency and must not be sold as one**: 293 nodes is a trivial graph, pruning
buys a linear factor against a quadratic, and the facts are both the audit trail and
the substance coverage composes from — deleting them to make a gate fast is how a
fail-open gets shipped. After Chunks 01-02 the cost is linear and cached, which buys
roughly two orders of magnitude of headroom.

**FILE with trigger:** revisit compaction when either the store exceeds ~10,000 trees
or a warm `check-cumulative-critic` exceeds 5 s. Design constraint for whoever picks it
up: a fact may only be dropped if no surviving fact's path can traverse it — reachability
from the current merge-base, not age.

## Rejected: splitting `is_judgeable_path`

The prior session proposed splitting the predicate on the theory that widening
`protected_path_violation` to segment-match `plugin/skills/**` had retroactively
invalidated accumulated review edges. **Measured against the live store: 0 edges lost** —
240 valid review edges under both the old root-anchored and the new segment predicate,
because reviewers record `files_reviewed ⊇ files_changed`, so widening judgeability
cannot invalidate an edge.

What the widening does do is remove the doc-only *free edge* for skills-prose intervals,
so a one-line skill prose fix now demands review. That is PR-5K8D's intended semantics,
not a defect — skill prose is behavioural logic here. The pain was never the trigger; it
was that triggering cost five minutes, which Chunks 01-02 remove.

Splitting would also rebuild the deadlock the module exists to have ended:
`coverage_algebra`'s docstring records that `cmd_stop`, `_pr_diff_is_doc_only` and
`_record_covers_head` once answered this question three divergent ways, and their
disagreement over the metadata boundary *was* CRT-5D8Q. Re-fragmenting it to fix a
problem the evidence says is absent is a bad trade.
