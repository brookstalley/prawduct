---
artifact: build-plan
version: 2
scope: test-status-clause
branch: fix/767-test-status-clause
depends_on:
  - artifact: issue-767-design
governed_by:
  - artifact: api-contract
    dispositions:
      - "exit codes are the contract (`api_error_model_approach`) → conforms: exit 0/1 are unchanged in both value and meaning; the change is additive stdout text only"
      - "`test-status` sits in the stable, allowlistable surface tier → conforms: the three skill files that read it are corrected in this same change, so no skill shipped in this plugin version reads a claim the command does not deliver"
      - "message vocabulary (`CRITICAL:`/`WARNING:`/`NOTE:`/`PRAWDUCT:`/`BLOCKED —`) → inapplicable because `test-status` prints a verdict line (`current:`/`stale:`), not a diagnostic in that vocabulary; the change extends the existing verdict prefix and introduces no new vocabulary"
  - artifact: data-model
    dispositions:
      - "verdicts computed from the append-only fact ledger, no model in a fact's write path → inapplicable because this plan writes no fact and adds no verdict; it reads `.test-evidence.json`, which that norm's Status explicitly scopes OUT of the store (`test-run` is reserved, not ratified)"
      - "facts are immutable and append-only → inapplicable because this plan appends no fact"
      - "derived views are disposable and never authoritative → conforms: the new `clause` is computed per call from the record and the tree, never persisted, so no gate can come to read a stored view of it"
      - "a governance document reaches a terminal state, never deletion → inapplicable because this plan deletes no document"
      - "every backlog issue conforms to the issue standard's §1 title rules → inapplicable because this plan writes no backlog item (the close of #767 is bookkeeping at merge, not a deliverable here)"
      - "a fact from a newer schema is a loud block, never silently dropped → inapplicable because no schema version changes: `evidence_tree` is read, not written, and `.test-evidence.json`'s shape is untouched"
      - "two stores, two lifetimes — shared committed answers vs per-clone gitignored nags → conforms: `.test-evidence.json` stays the per-clone gitignored artifact it already is, and nothing moves across that line"
      - "`backlog_service_repo` selects the authoritative backlog store → inapplicable because this plan reads no backlog store"
      - "tree-keying: facts reference git tree SHAs → conforms: this reads `evidence_tree` through the existing `_test_evidence_tree_valid` helper and stores nothing new"
partition: serial — one chunk, one reviewer roster
last_validated: 2026-09-18
---

## Requirements Confidence

**Level:** High

**Why:** The requirements work was done on the issue itself (`#767#issuecomment-5625111162`, 2026-09-10) — root cause confirmed by inspection at `plugin/lib/gates.py:210-211`, scope corrected twice, and the remedy named as an explicit either/or. `documentation/issues/767-design.md` (`2c3d0027`) resolves that either/or as (b) and specifies every file, decision and test case. Nothing here is being designed at build time.

**Open assumptions / unknowns:** none open. The design's two grounding claims were re-verified in this planning pass: `plugin/lib/gates*` is a declared `risk_surfaces:` entry (`project-state.yaml:636-637`), and `test-status` is in the api-contract's stable allowlistable tier (`api-contract.md:688`) — both tightened this plan rather than changing the design.

**What would raise confidence:** N/A

## Status

- [x] Chunk 01: `test-status` says which disjunct answered, and the three call sites claim only that

Context: Built 2026-09-18 on `fix/767-test-status-clause` (cut from `develop` at `ded04e89`), two commits: the chunk, then the fix for the cumulative review's six warnings. Reviewed `cumulative` (coordinator roster — `plugin/lib/gates*` is a declared risk surface) then `verify-resolutions`, which came back 0 blocking / 0 warning with 3 observations, all answered on the record and all fixed rather than accepted.

Two departures from `767-design.md`, both made at the review's direction and both recorded above: the labels became `lib.gates` constants so prose can be pinned to them by import, and the tree clause is asked FIRST and unconditionally rather than only on the timestamp-stale path. The second is the substantive one — the design's Decision 1 specified it, the first build silently narrowed it, and the review caught that the records still carried the design's rationale. Asking it costs ~0.12s here and ~0.36s on a 42k-file worktree, against the multi-minute re-run an under-claim invites.

Next: nothing within this plan. The branch is PR-ready — `check-cumulative-critic` composes across `develop..HEAD` — and `/prawduct:pr` should close #767, descoping `plugin/skills/critic/review-protocol.md` from its `affected:` list explicitly (it was read; it does not claim tree coverage). **Not** `plugin/methodology/building.md` — the chunk-close commit edited it, so it belongs on `affected:` and descoping it would hide a changed file from `backlog affecting <path>`.

## Build Chunks

### Chunk 01: `test-status` says which disjunct answered, and the three call sites claim only that

- **Description:** `gates.tests_are_current` returns on the session-fresh disjunct before `evidence_tree` is ever read, so within one session `test-status` exits 0 for any tree however far HEAD has advanced. Three governing skill files tell their readers that exit 0 means the evidence covers the current *tree*, which is what that disjunct does not establish. This chunk makes the command disclose which disjunct answered and corrects the three claims to match. Exit codes do not change and no new suite run is forced. The tree check is asked on BOTH paths, which the session path previously short-circuited past: that costs one git tree-diff per call (~0.1s here, ~0.4s on a 42k-file worktree) and buys the stronger answer whenever it is available, because reporting only "session-fresh" of evidence that is also tree-identical under-claims, and an under-claim is what sends a caller to re-run the suite.

- **Depends on:** none

- **Artifacts consumed:** `documentation/issues/767-design.md` (Decisions 1–4 and the files-touched table). Its quoted call-site wording is a PRE-BUILD SNAPSHOT and is no longer the text to use: the build departed from it twice, at the review's direction — the labels became `lib.gates` constants, and `reason`'s text did change on the session path, which that document says it would not. Take the wording from the shipped files.

- **Deliverables:**
  - `plugin/lib/gates.py` — `tests_are_current` asks the tree clause unconditionally and returns `tuple[bool, str, str]`, the third element `clause` being `"session"` / `"tree"` / `"none"`; `test_status` prints `CURRENT_TREE_LABEL`, `CURRENT_SESSION_LABEL` (both module constants, so prose can be pinned to them) or `stale: …`
  - `plugin/lib/release_readiness.py` — `_suite_verdict` drops the new third element before returning; its own 2-tuple contract to its one caller is unchanged
  - `plugin/skills/pr/SKILL.md` — correct line 53's tree-coverage claim
  - `plugin/skills/critic/SKILL.md` — correct line 65's tree-coverage claim
  - `plugin/skills/pr/review-protocol.md` — correct line 69's tree-coverage claim
  - `tests/test_plugin_runtime.py`, `tests/test_release_readiness.py` — the five cases below

- **Tests:** the design's Decision 4 matrix, each red-verified against the pre-change source before it is believed —
  1. session-fresh evidence on an advanced judgeable tree → exit 0 **and** stdout carries `CURRENT_SESSION_LABEL`
  2. tree-valid evidence → exit 0, stdout carries `CURRENT_TREE_LABEL`; and evidence that is BOTH session-fresh and tree-identical takes the tree label, which is the under-claim guard
  2b. the corrected skill prose contains the two labels, derived by import from `lib.gates` rather than retyped
  3. the existing degraded and no-marker `stale:` cases re-asserted verbatim — the `stale` branch and its `reason` text are untouched
  4. unit on `tests_are_current` — one case per disjunct, asserting the `clause` field rather than parsing `reason`
  5. `release_readiness._suite_verdict` — its two print strings byte-identical after the caller update (new coverage; nothing exercises it directly today)

- **Acceptance criteria:**
  - `prawduct-hook test-status` names which disjunct answered on both exit-0 paths, and a reader of any of the three corrected call sites cannot conclude from them that exit 0 proves tree coverage
  - exit codes unchanged: every existing test asserting on `test-status`'s exit code or on a `reason` substring still passes untouched
  - the declared suite passes

- **Type:** cumulative-final
  <!-- Single-chunk plan on a declared risk surface (`plugin/lib/gates*`), so the
       short-plan deferral does not apply and the roster is the coordinator one.
       One `cumulative` at the end is this chunk's review and the PR gate's evidence. -->

- **Done when:**
  1. Acceptance criteria met and the declared suite passes
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
  3. Chunk marked `[x]` in Status

## Governance Checkpoints

**Commit & PR cadence:** one commit, then the `cumulative` review, then `/prawduct:pr` when the user asks. The review's fact is what `check-cumulative-critic` composes for the PR gate.

**One thing for the reviewer to weigh.** `spike-tree-validated-test-evidence.md` §8 and §9a record that the review protocols needed no prose change, because they key off the exit code (GOV-7T2M). That held for the tree-validity clause it shipped and is what left the overclaiming prose standing: the exit code's *meaning* did not change, but three files describe it in terms of a guarantee only one disjunct provides. This chunk corrects the prose without touching the exit-code-is-the-signal rule — the corrected wording keeps it explicitly. The spike is a record, not a norm, so this is a note for the review rather than an amendment.
