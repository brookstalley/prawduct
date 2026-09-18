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

- [ ] Chunk 01: `test-status` says which disjunct answered, and the three call sites claim only that

Context: Plan written 2026-09-18 against `documentation/issues/767-design.md`. Branch `fix/767-test-status-clause` cut from `develop` at `ded04e89`. Nothing built yet.

## Build Chunks

### Chunk 01: `test-status` says which disjunct answered, and the three call sites claim only that

- **Description:** `gates.tests_are_current` returns on the session-fresh disjunct before `evidence_tree` is ever read, so within one session `test-status` exits 0 for any tree however far HEAD has advanced. Three governing skill files tell their readers that exit 0 means the evidence covers the current *tree*, which is what that disjunct does not establish. This chunk makes the command disclose which disjunct answered and corrects the three claims to match. Exit codes do not change and no new suite run is forced — the tree check it piggybacks on is a git diff already computed on the other code path.

- **Depends on:** none

- **Artifacts consumed:** `documentation/issues/767-design.md` (Decisions 1–4, the files-touched table, and the corrected call-site wording, which is quoted there in full and is the text to use)

- **Deliverables:**
  - `plugin/lib/gates.py` — `tests_are_current` returns `tuple[bool, str, str]`, the third element `clause` being `"session"` / `"tree"` / `"none"`; `test_status` prints `current (tree-valid): …`, `current (session-fresh, tree not verified): …`, or `stale: …`
  - `plugin/lib/release_readiness.py` — `_suite_verdict` drops the new third element before returning; its own 2-tuple contract to its one caller is unchanged
  - `plugin/skills/pr/SKILL.md` — correct line 53's tree-coverage claim
  - `plugin/skills/critic/SKILL.md` — correct line 65's tree-coverage claim
  - `plugin/skills/pr/review-protocol.md` — correct line 69's tree-coverage claim
  - `tests/test_plugin_runtime.py`, `tests/test_release_readiness.py` — the five cases below

- **Tests:** the design's Decision 4 matrix, each red-verified against the pre-change source before it is believed —
  1. session-fresh evidence on an advanced judgeable tree → exit 0 **and** stdout carries `session-fresh, tree not verified`
  2. tree-valid evidence → exit 0, stdout carries `tree-valid` and not `tree not verified`
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
