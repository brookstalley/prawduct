<!-- Build Plan — retire the PR-boundary trivial fast-path. -->
---
artifact: build-plan
version: 2
scope: retire-pr-trivial-fast-path
depends_on: []
last_validated: null
---

## Requirements Confidence

**Level:** High

**Why:** Root cause is known and verified against the code (incoming-bug
`check-pr-trivial-passes-feature-clusters-that-only-touch-existing-files`).
`check-pr-trivial` (`lib/coverage.py:303` → `_pr_diff_is_trivial`) decides
trivial-eligibility from the **fileset alone** — every commit on `merge-base..HEAD`
clearing `_classify_trivial_change`'s path bounds — with **no link to a
`Type: trivial` declaration**. Exit 0 makes `/prawduct:pr` Step 1c skip BOTH the
cumulative-Critic gate and the independent PR reviewer. So a substantial multi-chunk
**feature** that only modifies existing files (the common case) is reported `trivial`
and skips the two core review gates. The fileset bounds were designed as the
*enforcement* of a per-chunk `Type: trivial` declaration (the stop hook checks them
only when `chunk_type == "trivial"` — `bin/prawduct-hook:763`), not as a *detector* of
triviality at the bundle boundary. A necessary condition is standing in for a
sufficient one.

**Decision (user-chosen):** Retire the PR-boundary trivial fast-path entirely.
Rationale: (a) the doc-only fast-path is structurally sound (all-`.md` = no code to
review) and stays; the trivial fast-path is *semantically* unsound as an
auto-detector. (b) The only correct case it serves — a branch of all-`Type: trivial`
chunks, each chunk-mode-reviewed — is narrow; a genuinely trivial code change is cheap
to review anyway. (c) Gating on the declaration instead (the alternative) needs
multi-chunk, git-aware build-plan parsing that does not exist yet (overlaps CRT-3D9K)
and would *still* not help true one-liners, which typically have no build plan. Lowest
risk, removes the unsound predicate, aligns with Governance-Is-Structural.

**Open assumptions / unknowns:**
- `[ASSUMPTION: the stop-hook *chunk-level* Type: trivial enforcement (_is_trivial_fileset_eligible + _classify_trivial_change) stays — it is correctly gated on a Type: trivial declaration and is NOT the bug | HIGH confidence | user can veto]`
- `[ASSUMPTION: the doc-only fast-path (check-pr-doc-only / Step 1b / Gate-3 doc-only exemption) is unaffected and correct | HIGH confidence]`
- `[ASSUMPTION: backlog PR-9T4M (trivial fast-path omits bin/lib from protected paths) is rendered moot at the PR boundary by this removal — it is superseded, not separately fixed | MED | user can veto]`

**What would raise confidence:** N/A (High).

## Status

- [x] Chunk 01: Remove the PR-boundary trivial fast-path (runtime + skill + regression test)
Context: **Done on branch** (`fix/retire-pr-trivial-fast-path`, commit subject `Chunk 01:`). Removed `_pr_diff_is_trivial`/`check_pr_trivial` (`lib/coverage.py`), `cmd_check_pr_trivial` + dispatch + usage token + the stop-hook Gate-3 `pr_is_trivial` branch (`bin/prawduct-hook`), Step 1c + gate-summary bullet + allowed-tool (`skills/pr/SKILL.md`); re-anchored the `_classify_trivial_change` co-consumer doc-comments (`lib/gates.py`, `lib/buildplan_refs.py`). Regression test added (`tests/test_pr_reviewer.py::test_stop_blocks_fileset_eligible_code_pr_no_trivial_skip`). Critic `final`: **0 blocking**, 1 warning (stale evidence — resolved by `test-evidence record`, 1013 pass), 2 backlog notes (PR-9T4M shipped; PR-5K8D re-anchored, stays open). Checkbox stays `[ ]` (derived view; flips at release). **Next:** `/prawduct:critic cumulative` + change-log entry (`status=merged`) + `regen-views` happen at PR-merge — awaiting user decision on PR.

## Build Chunks

### Chunk 01: Remove the PR-boundary trivial fast-path

- **Description:** Delete the trivial fast-path at the PR boundary and at the
  symmetric session-end PR-evidence gate, so a fileset-eligible code PR can no longer
  skip the cumulative-Critic and PR-reviewer gates. Keep the chunk-level `Type: trivial`
  enforcement and the doc-only fast-path — both are sound and out of scope.
- **Deliverables:**
  - `lib/coverage.py`: remove `_pr_diff_is_trivial` and `check_pr_trivial`; drop the
    `check_pr_trivial` mention from the module docstring.
  - `bin/prawduct-hook`: remove `cmd_check_pr_trivial`, its dispatch branch, and the
    `check-pr-trivial` token from the usage string. In the stop-hook Gate 3
    (PR-review-evidence) block, remove the `pr_is_trivial` branch so **only** a
    doc-only PR is evidence-exempt; update the explanatory comment. Update the
    decomposition comment that lists `_pr_diff_is_trivial` as a `lib.coverage` export.
  - `skills/pr/SKILL.md`: remove Step 1c (Trivial-code fast-path) and the
    Trivial-code fast-path bullet in the gate summary; change Step 1b's exit-1 branch
    from "Proceed to Step 1c" to "Proceed to Step 2"; drop
    `Bash(prawduct-hook check-pr-trivial)` from `allowed-tools`.
  - `lib/gates.py`, `lib/buildplan_refs.py`: update the doc-comments that name
    `_pr_diff_is_trivial` as a co-consumer of `_classify_trivial_change` (now the sole
    consumer is `_is_trivial_fileset_eligible`) — keep documentation honest.
  - `tests/test_pr_reviewer.py`: add a regression test asserting that a **fileset-
    eligible** code PR (commits that only modify existing non-`.md` files — the exact
    bug scenario) still BLOCKS at Gate 3 for missing review evidence. This is the test
    the retired fast-path never had.
- **Tests:** the regression test above; the two existing Gate-3 tests
  (`test_stop_skips_pr_gate_when_pr_diff_is_doc_only`,
  `test_stop_still_blocks_when_pr_diff_includes_code`) must still pass unchanged; full
  suite green.
- **Acceptance criteria:** `prawduct-hook check-pr-trivial` no longer exists (dispatch
  removed; not in usage). A code PR that only modifies existing files is no longer
  evidence-exempt at session end — Gate 3 blocks (exit 2, "PR REVIEW") absent evidence.
  Doc-only fast-path behavior unchanged. Chunk-level `Type: trivial` enforcement
  unchanged. Full suite green.
- **Critic mode:** final
- **Type:** code
- **Done when:** 1. Acceptance + tests pass · 2. `/prawduct:critic final` blocking resolved · 3. committed + Status updated (views: change-log + regen-views) · 4. `/prawduct:critic cumulative` (the `/prawduct:pr` gate).
