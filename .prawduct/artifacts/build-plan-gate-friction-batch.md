---
artifact: build-plan
version: 2
scope: gate-friction-batch
depends_on: []
last_validated: 2026-07-09
---

## Requirements Confidence

**Level:** High

**Why:** Every chunk has a concrete, field-reported fix-shape and a grounded surface (functions located by file:line before planning). Three of four defects were observed in the wild (COV-2P7F/CRT-5D8Q gate deadlock; PR-7T2K dropped commits; CRT-9K7T cross-repo, corroborated by discodon's CRT-8F3K including the cumulative variant). No fast-moving or post-cutoff dependencies — this is the framework's own gate logic.

**Open assumptions / unknowns:**
- [ASSUMPTION: `.prawduct/**` non-`.md` state (`.governance-ledger.jsonl`, `.test-evidence.json`, backlog/state churn) is genuinely non-behavioral for the doc-only / change-log / coverage fast-paths — it is product-owned state by definition, and framework behavioral code lives in `lib/`, `bin/`, `skills/`, `methodology/`, `templates/`, root `CLAUDE.md` (the bound list already guards those) | LOW impact | builder can veto per-gate]
- [ASSUMPTION: requiring a `review.critic` ledger anchor at HEAD on `critic-end` is valid for ALL critic modes, since SKILL step 7 runs `ledger-append` for every mode | MED impact | builder can veto if a mode legitimately skips the ledger]
- [ASSUMPTION: "pushed" means `origin/<branch>` resolves to exactly local HEAD (not merely an ancestor) — an unpushed local commit is the failure PR-7T2K reports | LOW impact | user can override to ancestor-check]
- [ASSUMPTION: Chunk 4 merge-awareness = suppress the delete-plan nudge unless the plan's completion is an ancestor of the release base (`git merge-base --is-ancestor`) | MED impact | builder pins exact predicate against BRF-6K2D]

**What would raise confidence:** N/A (High).

## Status

- [ ] Chunk 01: Unify the governance-metadata doc-only predicate across all PR fast-paths (keystone)
- [ ] Chunk 02: PR merge push-completeness guard (`check-branch-pushed`)
- [ ] Chunk 03: Critic coordinator writeback reliability — exit-time assertion
- [ ] Chunk 04: Merge-aware "delete the plan" nudge (cumulative-final)
Context: On branch `feature/gate-friction-batch` off `develop`. Chunks 01–03 DONE on-branch (01: shared metadata predicate, +7 gate tests; 02: check-branch-pushed merge guard, +6 tests; 03: critic-end persistence assertion + synchronous-writeback prose, +6 tests) — checkboxes stay `[ ]` until v-release stamps `status=shipped`. Baseline caveat: 2 pre-existing xdist cross-file-pollution flakes in `test_pr_reviewer.py::TestStopPrReviewGate` (pass alone / as a file — TST-6H2Q, NOT introduced here). Next: Chunk 04 (merge-aware delete-plan nudge, cumulative-final).

## Why one plan / one PR

Chunk-mode reviews are cheap (local diff). One plan → per-chunk `chunk` reviews + one `cumulative` (Chunk 04) + one PR-reviewer pass. Four separate PRs would cost four PR-reviewer passes — this structure minimizes review wall-clock (P0). The keystone (Chunk 01) reconciles a predicate the later chunks don't touch, so ordering is for coherence, not hard dependency.

## Scaffolding

### Build & Test Configuration

Existing repo. `python3 -m pytest -q` (config in `pyproject.toml`: `testpaths=["tests"]`, xdist `-n` + `--dist loadfile`). Verify framework `lib/`/`bin/` changes with the **repo-local** `python3 bin/prawduct-hook`, never the PATH plugin-cache copy (learning).

### Verification Strategy

Per chunk: (1) run the affected test files **in isolation** (`pytest tests/test_X.py` — deterministically green, sidesteps the pre-existing cross-file flake) for a trustworthy signal on the changed behavior; (2) exercise the actual gate via repo-local `python3 bin/prawduct-hook <cmd>` against a scratch fixture where the defect reproduced. The final cumulative run is the full suite; NEW failures (beyond the 2 known flakes) are mine to fix.

## Build Chunks

### Chunk 01: Unify the governance-metadata doc-only predicate across all PR fast-paths

- **Description:** Today three fast-paths judge "not code" by pure `.md` suffix while three others use `gitstate._is_metadata_path` (`.prawduct/` + `.claude/settings.json`). The disagreement is the CRT-5D8Q deadlock: a branch whose entire diff is `.prawduct/` state is simultaneously "stale, re-run" (per `_record_covers_head`, `.md`-only) and "empty delta, nothing changed" (per `_compute_verify_resolutions_scope`, metadata-aware). Teach ONE shared predicate — *a file is non-behavioral iff `f.endswith(".md") or gitstate._is_metadata_path(f)`; a diff qualifies for a doc/metadata fast-path iff every file is non-behavioral AND no file triggers `buildplan_refs.protected_path_violation(f)`* — and route every fast-path through it. The `protected_path_violation` guard is load-bearing: it keeps `skills/**/*.md`, `methodology/`, `templates/`, root `CLAUDE.md` classified as code even though they are `.md`/adjacent (COV-2P7F guard clause).
- **Depends on:** none
- **Deliverables:**
  - New shared predicate in `lib/gitstate.py` beside `_is_metadata_path` (promote to a documented, importable helper — e.g. `diff_is_metadata_or_doc(files, protected_check)` or a per-file `is_nonbehavioral_path`), so `coverage.py` and `gates.py` consume one definition. Do NOT re-implement the composition three times.
  - `lib/coverage.py::_pr_diff_is_doc_only` (`:165`, `:175-177`) — broaden the `.md`-only test to metadata-aware; keep the existing `protected_path_violation` guard.
  - `lib/coverage.py::check_change_log_entry` (`:231`) — broaden to metadata-aware AND add the `protected_path_violation` guard it currently lacks (so a `.prawduct/`-only branch needs no change-log entry, but a `skills/**/*.md` edit still does).
  - `lib/gates.py::_record_covers_head` (`:1025`) — broaden `non_doc` to exclude metadata paths AND add the protected guard, so a `.prawduct/`-state delta since review reads as *covered*. This is the half of CRT-5D8Q that disagrees with the scope helper.
  - Reconcile the internal inconsistency in `lib/gates.py::_evaluate_pr_gate_record`: the chain scope-gap (`:1362-1367`) already combines both filters; align `_record_covers_head` (called `:1248`, `:1305`) onto the same shared predicate so one record isn't judged by two boundaries within one function.
- **Cross-surface cascade (prose that names the old boundary):** `skills/pr/SKILL.md` and `skills/critic/review-cycle.md` (`:70`, `:72`) + `skills/critic/review-protocol.md` describe the gate as "doc-only / all-`.md`" — update to "governance-metadata-or-doc" so docs match behavior (Living Documentation). Grep both skills + `methodology/` for "doc-only" / "all `.md`" / ".md-only" and reconcile wording where it describes THIS predicate.
- **Tests:** `tests/test_cumulative_gate.py`, `tests/test_change_log_entry_gate.py`, `tests/test_gitstate_porcelain.py`, `tests/test_trivial_fileset_gate.py`. Add the currently-missing coverage:
  - `_record_covers_head` treats a `.prawduct/**` non-`.md` delta since review as **covered** (none exists today — Explore confirmed).
  - `check_change_log_entry` exempts a `.prawduct/**`-only (non-`.md`) branch.
  - **Negative regression per broadened fast-path (mandatory, learning "give every skip-gate a regression test that a non-eligible case still BLOCKS"):** a `skills/*.md` edit and a real `lib/*.py` change each still fail doc-only / still require a change-log entry / still stale the record. The `protected_path_violation` guard must be proven, not assumed.
- **Acceptance criteria:** the CRT-5D8Q scenario (branch diff entirely under `.prawduct/`) resolves consistently across `_record_covers_head` and `_compute_verify_resolutions_scope` — no deadlock; all four test files pass in isolation; every negative-regression test BLOCKS.
- **Critic mode:** final
  <!-- Override: keystone. The predicate's coherence is across coverage.py + gates.py + gitstate.py + skill prose — a cross-file property the chunk-mode diff can't see. -->
- **Done when:**
  1. Acceptance criteria met; affected test files green in isolation
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked (change-log entry tagged `gate-friction-batch` + regen-views, since `views_enabled`)

### Chunk 02: PR merge push-completeness guard

- **Description:** `/prawduct:pr` Merge Flow squash-merges `origin/<branch>`, but the PR gates validate *local* HEAD. A commit made after the last push is silently dropped from the merge (PR-7T2K). Add a structural pre-merge assertion.
- **Depends on:** none (independent of Chunk 01)
- **Deliverables:**
  - New `prawduct-hook check-branch-pushed`: resolves `origin/<current-branch>` and asserts it equals local HEAD; exit non-zero with an actionable message ("N local commit(s) not pushed — `git push` before merge") on any gap or missing upstream. Body in a `lib/` sibling (per repo pattern — thin `bin` wrapper), fail-loud not fail-soft (a merge that drops commits is worse than a false block). Add to the dispatch table + usage string in `bin/prawduct-hook` (`:2644-2649` region).
  - Wire into `skills/pr/SKILL.md` Merge Flow (`## Merge Flow`, `:122`+) as a hard step **before** the squash (`:129`).
- **Tests:** new `tests/test_check_branch_pushed.py` — upstream == HEAD passes; unpushed local commit fails; no upstream configured fails closed with a clear reason; detached/edge states fail closed.
- **Acceptance criteria:** `python3 bin/prawduct-hook check-branch-pushed` exits 0 on a pushed branch and non-zero (named reason) with an unpushed commit, in a scratch git fixture.
- **Done when:**
  1. Acceptance criteria met; test file green in isolation
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked (tagged change-log entry + regen-views)

### Chunk 03: Critic coordinator writeback reliability — exit-time assertion

- **Description:** In forked/coordinator mode (and, per discodon's CRT-8F3K corroboration, the **cumulative** variant too), fork-and-return hands control back to the caller before the monitor's all-reviewers-complete consolidation runs. If that step is skipped/errors, **two** writes never land: `.prawduct/.critic-findings.json` stays frozen at a prior commit, AND the `review.critic` event is never appended to `.prawduct/.governance-ledger.jsonl`. The ledger anchor is what `check-cumulative-critic` gates on → `chain-missing-anchor`, deadlocking the PR gate; recovery is a full ~3-reviewer re-run. It is silent (caller only learns via the red gate) and non-deterministic (repro: first cumulative dropped the writes, an identical second run persisted correctly). Make completion **structurally verified at exit** rather than trusted: convert the silent race into an immediate loud failure the coordinator must resolve before the SKILL returns success. One invariant — *both writes landed for HEAD* — enforced at one exit point.
- **Depends on:** none
- **Deliverables:**
  - `cmd_critic_end` (`bin/prawduct-hook:739-745`, body likely to a `lib/critic_marker` sibling): **always clear `.critic-active` first** (never leave the session wedged), then assert BOTH for current HEAD and exit non-zero with an actionable message if either is missing:
    1. `.prawduct/.critic-findings.json` `commit_reviewed == HEAD`;
    2. the latest `review.critic` ledger event's envelope `git.head == HEAD`.
  - New read-only helper in `lib/ledger.py` to fetch the latest `review.critic` event's `git.head` (the envelope already carries `git: {head, base}` — `:12`). Read-only; no schema change (no new persisted format → no lock-in).
  - `skills/critic/SKILL.md` (step 7 `:54-59`, step 8 `:60`): make the writeback ordering explicit — land BOTH `.critic-findings.json` and the `ledger-append` **before** `critic-end`; document that `critic-end` now fails loud if either write for HEAD is absent, and that the fix is to re-run the writeback (not to hand-author either file). Mirror the note into `skills/critic/review-protocol.md` (`:177-198`) where the writeback is specified.
- **Tests:** new `tests/test_critic_end_assertion.py` — both writes at HEAD → exit 0, marker cleared; stale `.critic-findings.json` (commit_reviewed != HEAD) → non-zero, marker STILL cleared; missing/stale `review.critic` ledger anchor → non-zero, marker cleared; no findings file at all → non-zero. Assert the marker is cleared on every path (a failed assertion must not wedge the next session).
- **Acceptance criteria:** in a scratch fixture reproducing the defect (findings frozen at a prior commit / no ledger anchor for HEAD), `python3 bin/prawduct-hook critic-end` exits non-zero with a message naming which write is missing, and `.critic-active` is gone afterward.
- **Done when:**
  1. Acceptance criteria met; test file green in isolation
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked (tagged change-log entry + regen-views)

### Chunk 04: Merge-aware "delete the plan" nudge

- **Description:** `lib/briefing.py`'s stale-plan finding (`:154-157`) fires "all chunks complete — delete the plan" whenever Status is fully checked, regardless of whether the plan's feature branch has merged. On `develop` with an unmerged feature branch (or when `active_build_plan` must stay pointed until the release ships — plan-lifecycle-on-gitflow), that nudge is premature (BRF-6K2D). Gate it on merge state.
- **Depends on:** none
- **Deliverables:**
  - `lib/briefing.py` (`:154-157`, and the sibling `:163-166`): before appending the delete-plan finding, add an is-ancestor gate — suppress the nudge unless the plan's completion is an ancestor of the release base (`git merge-base --is-ancestor`, base via the existing `gates`/`resolve-base` machinery already imported here). Best-effort inside the existing `try/except` (`:167`) — a git failure falls through to current behavior, never crashes the scan.
- **Tests:** `tests/test_briefing*.py` (or new) — all-chunks-complete on an UNMERGED feature branch → no delete nudge; same plan once merged into the release base → nudge fires; git-unavailable → falls back to current behavior (no crash).
- **Acceptance criteria:** the nudge is silent on the unmerged feature branch and fires post-merge, in a scratch fixture.
- **Type:** cumulative-final
  <!-- Last chunk: its review IS the one `/prawduct:critic cumulative` against merge-base...HEAD, which also gates `/prawduct:pr create`. Commit first, run cumulative once, no separate `final`. -->
- **Done when:**
  0. Acceptance criteria met; test file green in isolation
  1. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  2. Chunk marked (tagged change-log entry + regen-views)

## Governance Checkpoints

**Commit & PR cadence:** commit per chunk after its Critic review passes (per-chunk commit scopes `chunk`-mode reviews). Chunk 01 lands `final` (keystone coherence). Chunk 04's `cumulative` review makes the branch PR-ready — `/prawduct:pr create` is gated on it and runs only when the user asks.

- After Chunk 01: confirm all six predicate call-sites resolve the `.prawduct/`-only diff consistently before building the rest.
- After Chunk 04 (cumulative): full-bundle review; verify no fast-path was broadened without a paired negative-regression test, and that the skill/methodology prose matches the new predicate.
