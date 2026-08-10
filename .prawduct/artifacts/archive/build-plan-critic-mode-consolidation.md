<!-- Build Plan — critic-mode-consolidation (STH-2K8R + BLD-6Q1N, closes CRT-3D9K)
     One consolidation pass deleting lib/critic_mode.py's now-unjustified mirrors
     onto lib/buildplan_refs + lib/gitstate, plus the BLD-6Q1N shared Status-section
     walker. Branch feature/critic-mode-consolidation. For HOW to build
     (governance, test discipline, Critic review), read /prawduct:building.
-->
---
artifact: build-plan
version: 2
scope: critic-mode-consolidation
depends_on:
  - artifact: project-preferences
last_validated: 2026-06-10
lifecycle: completed
archived: 2026-08-10
released_in: v2.1.4
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Requirements Confidence

**Level:** High

**Why:** Both items are audited backlog entries at `stage: ready`; the 2026-06-10 groom
re-confirmed every code site against HEAD, and pre-plan reads this session re-verified all
of them at v2.1.3 (`lib/critic_mode.py` L437-474/520-531/559-600/640-682/744-784,
`lib/gates.py` L694-734, `lib/buildplan_refs.py` L31-109/505-520, `lib/gitstate.py`
L58-102/290-304). The parity-pin learning was applied during planning: the one test-pinned
deliberate mirror (`_chain_extendable_anchor` ↔ `gates._chain_anchor` +
the verbose mode constants, `TestChainAnchorParity`) is explicitly OUT of scope.

**Open assumptions / unknowns:**
- [ASSUMPTION: the shared Status-section walker's exact shape (line iterator vs item
  iterator) is an implementation choice, bounded by "all five reader call sites fold onto
  it" — BLD-6Q1N's `_iter_status_section_items` name is a suggestion, not a contract |
  LOW impact | user can defer]
- [ASSUMPTION: ships as one PR to `develop` on `feature/critic-mode-consolidation` |
  LOW impact | user can override]
- [ASSUMPTION: `gitstate.git_status_output` stays as-is; `critic_mode` keeps its own
  `git status --porcelain --untracked-files=all` subprocess call (the `-uall` flag is
  load-bearing — `test_wins_for_no_plan_medium_plus_work`) and folds only the LINE PARSING
  onto `gitstate.parse_porcelain_line` | LOW impact | user can correct]

**What would raise confidence:** N/A.

## Status

- [x] Chunk 01: Consolidate critic_mode mirrors onto buildplan_refs/gitstate + shared Status walker
Context: Chunk 01 built and committed 2026-06-10 (9acb8c3). Suite 1331 passed / 0 failed
(evidence recorded). Cumulative Critic: 0 blocking / 1 warning / 0 notes — the warning
(verify-chunk-refs false positives on extension-less module paths in this plan's prose)
is fixed in-place; refs verify clean. Ready for PR when the user asks. Checkbox flips at
release via the scope=critic-mode-consolidation change-log tag (views enabled).

## Scaffolding

Existing repo — no scaffold. Tests run via `python3 -m pytest tests/ -q` from the repo
root (evidence via `prawduct-hook test-evidence record`). No new dependencies.

### Verification Strategy

Two layers: (1) the full pytest suite — this refactor's safety net is the existing
behavioral coverage in `tests/test_critic_mode_inference.py`, `tests/test_cumulative_gate.py`,
and `tests/test_gitstate_porcelain.py`, which must pass UNCHANGED (tests are contracts; a
consolidation that needs a test edit is a behavior change to stop and examine); (2) exercise
the real surface — run `prawduct-hook infer-critic-mode` on this repo mid-chunk (dirty tree,
active plan) and at chunk-end, and confirm the rationale/mode output is sane against the
known git state.

## Project Structure

No new modules. Direction of consolidation follows the existing lib DAG
(`gitstate` ← `buildplan_refs` ← consumers): shared helpers land in `lib/buildplan_refs.py`
(Status-section walking, chunk-section walking) and `lib/gitstate.py` (already hosts the
canonical `_is_metadata_path` / `parse_porcelain_line` / `_git_head_sha`); `lib/critic_mode.py`
and `lib/gates.py` become importers. `critic_mode` must NOT import `gates` (that is the
pinned mirror's rationale — see out-of-scope).

## Build Chunks

### Chunk 01: Consolidate critic_mode mirrors onto buildplan_refs/gitstate + shared Status walker

- **Description:** Delete `lib/critic_mode.py`'s mirror implementations and fold all
  Status-section reader parsing onto one shared walker, in one pass (NOT
  behavior-preserving by construction — it collapses parity relationships, so it gets its
  own tests and Critic review):
  1. **`_is_metadata_path` + `_METADATA_PREFIXES`** (`lib/critic_mode.py`) → import from
     `lib/gitstate.py`; update `gitstate`'s "(Mirrored in `lib/critic_mode.py`.)" comment.
  2. **Inline porcelain parse** in `_get_uncommitted_code_files` → keep the
     `--untracked-files=all` subprocess call, parse each line via
     `gitstate.parse_porcelain_line` (rename-dst + quote handling become canonical; the
     near-duplicate noted by the review-fixes Chunk 1 Critic goes away).
  3. **`_git_head_sha`** (`lib/critic_mode.py`) → import from `lib/gitstate.py` (same
     semantics; gitstate's adds the standard subprocess-failure guard).
  4. **`_current_chunk_id_from_status`** (`lib/critic_mode.py`) → import from
     `lib/buildplan_refs.py` (pre-verified output-equivalent: first `- [ ]` item,
     comment-aware, `None` on missing plan/section/non-`Chunk NN:` form).
  5. **BLD-6Q1N:** extract the shared Status-section walker into `lib/buildplan_refs.py`
     (comment-aware, next-`## `-stop — the skeleton currently copied in 5 readers), then
     fold onto it: a single `_count_build_plan_chunks` in `buildplan_refs` replacing BOTH
     duplicates (`lib/gates.py` ~L694 — keep its broad-except gate posture at the call
     site or inside the shared helper, behavior identical — and `lib/critic_mode.py`
     ~L744); `critic_mode._chunk_ids_in_status_order`; and
     `buildplan_refs._parse_build_plan_status`'s own Status loop.
  6. **Chunk-section discovery:** extract the shared chunk-section walker
     (`### Chunk <id>:` name-anchored, leading-zero-tolerant, fence-skipping,
     sibling/`## `-stop) into `lib/buildplan_refs.py` and fold its 4 copies onto it:
     `_parse_build_plan_chunk_refs`, `_parse_build_plan_chunk_type`,
     `_parse_build_plan_chunk_trivial_rationale` (all in `buildplan_refs`), and
     `critic_mode._critic_mode_for_chunk` (the "chunk-`Type:` parser" mirror named in
     STH-2K8R's original body — it stays in `critic_mode` as the `**Critic mode:**`
     field reader but uses the shared walker for section discovery).
  7. **Docstrings:** delete the manual-sync/mirror claims that this pass makes false —
     `critic_mode`'s module-docstring rationale ("helpers intentionally re-implemented
     here"), the per-function "Mirrors `bin/prawduct-hook`'s …" notes on deleted bodies.
     The hook-side rationale is dead since STH-9V4K (v2.0.14): the canonical helpers live
     in lib siblings `critic_mode` already imports from (`core`, `coverage`).
  - **Out of scope (deliberate):** (a) `critic_mode._chain_extendable_anchor` +
    `_MODE_*_VERBOSE` constants ↔ `gates._chain_anchor` + `_CRITIC_MODE_*` — a deliberate,
    test-pinned mirror (`TestChainAnchorParity`) whose rationale (keep `gates` out of the
    shim's import graph) still holds; the parity test keeps enforcing it. (b)
    `lib/views.py::extract_status_section` — an index-based REWRITER (needs line indices
    to splice), not a reader; folding it would contort the walker. (c) `bin/prawduct-hook`'s
    import-light pinned mirrors (`_read_bool_yaml_key` etc.). (d) `critic_mode`'s other
    git helpers (`_commit_resolves`, `_commits_ahead_of_base`, `_committed_files_since`,
    `_committed_chunk_ids`) — single implementations, not mirrors.
- **Depends on:** none
- **Artifacts consumed:** `.prawduct/artifacts/project-preferences.md`, backlog entries
  STH-2K8R / BLD-6Q1N / archived CRT-3D9K
- **Deliverables:** consolidated `lib/critic_mode.py`, `lib/buildplan_refs.py`,
  `lib/gates.py`, `lib/gitstate.py` (comment only); new tests in `tests/`
- **Tests:** ALL existing tests pass unchanged (the behavioral contract). New: direct
  unit tests on the shared Status-section walker (comment skip, next-section stop, both
  checkbox states, missing section) and the shared chunk-section walker (leading-zero
  tolerance, fence skip, sibling-chunk stop, section-not-found); a consolidation pin
  asserting the duplicate bodies are GONE (e.g. `critic_mode._count_build_plan_chunks is
  buildplan_refs._count_build_plan_chunks` / `gates._count_build_plan_chunks is` the same,
  or absence-of-def checks) so the mirrors can't quietly come back — the anti-divergence
  analogue of `TestChainAnchorParity`, inverted: those two must stay EQUAL, these must
  stay SINGULAR; a porcelain edge-case test through `_get_uncommitted_code_files`'s new
  path (quoted path with spaces, rename) that the old inline parse handled implicitly.
- **Acceptance criteria:** full suite green with zero edits to existing test assertions;
  exactly one Status-section reader walker and one chunk-section walker remain in `lib/`
  (grep-verifiable: the `== "## Status"` / `startswith("### Chunk ")` scan skeletons
  appear once each in lib readers, `views.py` rewriter aside); `lib/critic_mode.py` no
  longer defines `_is_metadata_path`, `_METADATA_PREFIXES`, `_git_head_sha`,
  `_current_chunk_id_from_status`, or `_count_build_plan_chunks`; `critic_mode` still does
  not import `gates`; live `prawduct-hook infer-critic-mode` run on this repo returns a
  sane mode + rationale.
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass (evidence recorded)
  2. Committed, then `/prawduct:critic cumulative` run against `merge-base...HEAD`
     (single-chunk plan shipping as one PR — this one review IS the chunk review, the
     end-of-cycle synthesis, and the `/prawduct:pr create` gate) and blocking findings
     resolved
  3. Chunk marked `[x]` in Status (via tagged change-log entry — views enabled)
  4. Backlog: STH-2K8R + BLD-6Q1N → `status=shipped` with `closed-by:` anchors (CRT-3D9K
     already archived; its closure rides STH-2K8R's anchor)

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** N/A in the product-UI sense — internal consolidation. After the
chunk, `lib/` has one canonical implementation per helper and the drift hazard class the
2026-06-09 Critic flagged (third porcelain parser) is closed.

## Governance Checkpoints

**Commit & PR cadence:** Single chunk, `Type: cumulative-final` — commit after the suite
is green, then one `/prawduct:critic cumulative` serves as chunk review + PR gate
(one review run total — review wall-clock is P0). PR to `develop` via `/prawduct:pr`
when the user asks.
