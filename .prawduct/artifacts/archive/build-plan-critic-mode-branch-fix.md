<!-- Build Plan — infer-critic-mode branch-progress fix (CRT-7B4M). -->
---
artifact: build-plan
version: 2
scope: critic-mode-branch-fix
depends_on: []
last_validated: null
lifecycle: completed
archived: 2026-08-10
released_in: v2.0.16
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Requirements Confidence

**Level:** High

**Why:** Root cause is known and verified (CRT-7B4M analysis): on a `views_enabled` feature branch the build-plan `## Status` checkboxes are a derived view that only flips at release, so `_current_chunk_id_from_status` always returns the first chunk and `_count_build_plan_chunks` always reports `complete=0`. The plan-override then reads Chunk 01's mode for every chunk, and rule-3's last-chunk detection can't fire. Fix shape (Option A, user-chosen): derive committed-chunk progress from git when the checkboxes are an unflipped derived view.

**Open assumptions / unknowns:**
- `[ASSUMPTION: committed chunks are counted from commit subjects matching "Chunk <n>" on merge-base..HEAD | MED impact | user can correct — this is the robust form of "git commit count"; it degrades to the current checkbox behavior (never worse) when commits don't reference chunks]`
- `[ASSUMPTION: the bin/prawduct-hook mirror of these helpers (used by the stop-gate for chunk-TYPE detection) is OUT of scope — it has the same latent branch issue but a different symptom; noted, not fixed here | LOW impact | user can veto to widen scope]`

**What would raise confidence:** N/A (High).

## Status

- [x] Chunk 01: Git-derived chunk progress when Status checkboxes are an unflipped derived view
Context: **Done** (Critic final: 0 blocking, 3 warnings — all resolved, + 3 notes). `lib/critic_mode.py`: git-aware `_git_aware_progress` + `_committed_chunk_ids` + `_chunk_ids_in_status_order`; `_current_chunk_critic_mode`→`_critic_mode_for_chunk(id)`; `_rule_final_fires` threaded `(total,complete)`. **Critic WARNING-1 fix (scope-expanded, deliberate):** replaced the main-first `_detect_base_branch` with the canonical `_resolve_base_branch` (honors `base_branch:`) at BOTH call sites (my new code AND the pre-existing rule-cumulative use — same gitflow bug class), and removed `_detect_base_branch`. Docstring drift fixed. Gitflow divergence test added. `tests/test_critic_mode_inference.py` +7 (TestBranchProgressCRT7B4M). 1012 tests pass. NOTE: total/complete desync (left — safe, degrades to chunk); STH-2K8R parity (net-reduced — removed a mirrored helper).

## Build Chunks

### Chunk 01: Git-derived chunk progress when Status checkboxes are an unflipped derived view

- **Description:** When the build-plan Status checkboxes are a non-flipping derived view (`views_enabled` true) and HEAD is on a pre-release feature branch (a base branch resolves and HEAD is ahead of it), determine "completed chunks" and "current chunk" from **git** instead of the `[ ]`/`[x]` checkboxes. This makes the plan-override read the *current* chunk's `Critic mode:` (not always Chunk 01's) and lets rule-3 detect the genuine last chunk. Degrades to the existing checkbox behavior whenever the git signal doesn't apply (no `views_enabled`, no base, not ahead, or no chunk-referencing commits) — never worse than today.
- **Deliverables:**
  - `lib/critic_mode.py`:
    - new `_committed_chunk_ids(project_dir, base)` — the (normalized) chunk ids referenced by `Chunk <n>` in commit subjects on `base..HEAD` (a set, so multi-commit-per-chunk and out-of-order are handled).
    - new `_chunk_ids_in_status_order(prawduct_dir)` — all chunk ids in Status order (both states).
    - new `_git_aware_progress(project_dir, prawduct_dir, total)` — returns `(complete, current_chunk_id)` from git when applicable, else `None`.
    - refactor `_current_chunk_critic_mode` to resolve the current chunk id via the git-aware progress (fall back to first-`[ ]`); `_rule_final_fires` to consume the git-aware `complete`.
    - `infer_mode` computes `(total, complete, current_chunk_id)` once and threads it.
  - `tests/test_critic_mode_inference.py` (extend): a views-enabled branch with all-`[ ]` checkboxes + N chunk-referencing commits → the plan-override reads chunk N+1's mode (not Chunk 01's); last-chunk → `final`; mid-chunk with no per-chunk override → `chunk`; degradation cases (no views / no base / no chunk commits → existing behavior).
- **Tests:** the above; full suite green.
- **Acceptance criteria:** on a simulated views-enabled branch, a multi-chunk plan whose Chunk 01 declares `final` no longer forces `final` on chunk 3+ — chunk 3 (mid, no override) infers `chunk`, the last chunk infers `final`, and a chunk that declares its own `final` still gets `final`. Degradation paths unchanged. Suite green.
- **Critic mode:** final
- **Type:** code
- **Done when:** 1. Acceptance + tests pass · 2. `/prawduct:critic final` blocking resolved · 3. committed + `[x]` · 4. `/prawduct:critic cumulative` (the `/prawduct:pr` gate).
