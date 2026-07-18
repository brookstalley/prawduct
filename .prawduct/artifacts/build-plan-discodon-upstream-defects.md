---
artifact: build-plan
version: 2
scope: discodon-upstream-defects
depends_on: []
last_validated: 2026-07-18
---

## Requirements Confidence

**Level:** High

**Why:** Four upstream defects filed by the discodon product were re-verified against current `develop` (v3.1.0) by direct code read plus three independent verification agents. Two already have ready, code-verified parent items in this repo's backlog (CRT-7H2W, BLD-5J8N) whose recommended fix-shapes match the scope the user confirmed; one (CRT-M3F8) is newly filed; one (PDT-WT9K) is hardening on an already-fixed root cause tracked under CRT-6W2N. The three genuine scope forks were confirmed with the user (2026-07-18): PDT-C6R4 → loud + broaden parser; CRT-T9RX → structural fix; PDT-WT9K hardening → in scope.

**Open assumptions / unknowns:** none material. [ASSUMPTION: the `## Chunk N (ID) — Name` heading form is worth first-class support in the ref-check parser rather than forcing product-side template migration | LOW impact | user confirmed "broaden parser"]

## Status

- [ ] Chunk 01: CRT-M3F8 / CRT-4T7M — normalize file-less/blank `files` in critic-consolidate instead of fail-closing
- [ ] Chunk 02: PDT-C6R4 / BLD-5J8N — verify-chunk-refs parses `## Chunk N (ID) — Name` and distinguishes parse-miss from ref-missing
- [ ] Chunk 03: CRT-T9RX / CRT-7H2W — intent-aware verify-resolutions head anchor (structural) + dirty-tree diagnostic
- [ ] Chunk 04: PDT-WT9K — critic-begin worktree visibility + mismatch-detection + refuse-on-unresolvable
Context: Plan on branch fix/discodon-upstream-defects. Chunk 01 built + Critic-passed (chunk mode, 0 blocking, 1 warning addressed) + committed; suite 2344 passed, 6 skipped. Checkboxes stay statusless until merge (release-pending model). Next: Chunk 02. 

## Verification Strategy

Each chunk is a governance-protected change to the Critic/gate machinery. Verification is: (a) a targeted regression test that reproduces the reported failure and now passes; (b) the full `python3 -m pytest tests/` suite green; (c) for chunks touching `bin/prawduct-hook` CLI surface, a direct CLI exercise of the fixed path. Governance-protected code (`lib/critic_consolidate.py`, `lib/gates.py`, `lib/critic_mode.py`, `bin/prawduct-hook`) → `/prawduct:critic` per chunk, cumulative + PR review before merge.

## Build Chunks

### Chunk 01: CRT-M3F8 — normalize file-less/blank findings in critic-consolidate

- **Description:** `critic-consolidate` already tolerates a finding's `files: []`, but a blank/non-string *element* (`files: [""]`) still fails `_str_list` and fail-closes the *entire* consolidation — one reviewer's malformed optional attribution bricks the whole review. `files` is optional attribution that `merge_findings` normalizes away when falsy; extend that normalization to drop blank/non-string elements so a `[""]` degrades to `[]` (dropped) instead of aborting.
- **Depends on:** none
- **Artifacts consumed:** discodon backlog CRT-M3F8 (local **CRT-4T7M**); verified sites `lib/critic_consolidate.py:429-430` (validator), `:571` (`merge_findings` keeps truthy `files` verbatim)
- **Deliverables:** `lib/critic_consolidate.py` (relax `validate_partial` to reject `files` only when it is not a list at all; normalize blank/non-string elements out in `merge_findings`), `tests/test_critic_consolidate.py` (regression: a partial with `files:[""]` on a finding consolidates instead of fail-closing; a `files:"x"` non-list still rejects)
- **Tests:** unit — `validate_partial` accepts `files:[""]`/`files:["", "a.py"]` and still rejects `files:"a.py"` (non-list) and `files:5`; `merge_findings` drops blank/non-string elements so `[""]`→ no `files` key, `["","a.py"]`→`["a.py"]`; consolidation end-to-end no longer returns 1 on a file-less META-finding
- **Acceptance criteria:** a reviewer partial carrying a file-less/blank-element finding consolidates cleanly (exit 0, fact persisted); a genuinely malformed non-list `files` still fails loud
- **Type:** bugfix
- **Critic mode:** chunk
- **Done when:**
  1. Acceptance criteria met and full suite passes
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 02: PDT-C6R4 / BLD-5J8N — verify-chunk-refs header parsing + loud parse-miss

- **Description:** The Goal-2 deliverable gate (`verify-chunk-refs`) locates chunk sections only by the `### Chunk NN:` (H3, colon) form. A `## Chunk N (ID) — Name` heading (H2, em-dash, colon-less) never matches, so the hook exits 1 as a *"chunk not found"* — indistinguishable from a real missing-deliverable failure, habituating reviewers to dismiss the exit and leaving the deliverable check silently inert. Broaden the chunk-heading/ Status parsers to accept `^#{2,3}\s+Chunk\s+<id>\s*[:—–-]` (H2/H3, colon or en/em-dash, optional `(ID)`), AND give the hook a distinct exit contract so a genuine parse-miss ("could not locate/parse the chunk section") is reported loudly as gate-could-not-run, never as a passed or a deliverable-missing check.
- **Depends on:** none
- **Artifacts consumed:** discodon backlog PDT-C6R4; local BLD-5J8N (fix-shape) and GOV-8N4V (same parser gap at the mode-inference/current-chunk layer — verify both readers)
- **Deliverables:** `lib/buildplan_refs.py` (`_chunk_section_lines`, `_chunk_id_from_item_text`, `_current_chunk_id_from_status`, and the sibling field parsers — accept the broadened heading form; leading-zero + parenthetical-ID tolerant), `bin/prawduct-hook` (`cmd_verify_chunk_refs` Status current-chunk parse + a parse-miss-vs-ref-missing exit distinction), `tests/` (regression: an `## Chunk 1 (RES-K3QP) — Name` plan resolves its section and the deliverable check runs; a truly absent chunk reports the loud parse-miss form)
- **Tests:** unit — `_chunk_section_lines` locates sections under `## Chunk 1 (ID) — Name`, `### Chunk 01: Name`, and `## Chunk 01 — Name`; `cmd_verify_chunk_refs` runs the deliverable check (not a parse-exit) for the H2 form and distinguishes "could not parse any chunk heading" from "ref missing"; leading-zero tolerance preserved
- **Acceptance criteria:** a research build-plan using the `## Chunk N (ID) — Name` form has its Goal-2 deliverable check actually execute; an unparseable/absent chunk yields a loud, distinct signal rather than a silent generic exit-1
- **Type:** bugfix
- **Critic mode:** chunk
- **Done when:**
  1. Acceptance criteria met and full suite passes
  2. Direct CLI exercise: `verify-chunk-refs` against a fixture plan of each heading form
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status

### Chunk 03: CRT-T9RX / CRT-7H2W — intent-aware verify-resolutions head anchor + diagnostic

- **Description:** `verify-resolutions` records `head_tree = capture["tree"]` (the WORKING tree, WIP included) while the cumulative/PR gate targets the COMMITTED HEAD tree; a dirty tree carrying *judgeable* uncommitted files (e.g. `.devcontainer/*`, any `.py`) leaves `check-cumulative-critic` `uncovered` even though verify-resolutions reported success, with an undocumented `git stash` as the only remedy. Apply the STRUCTURAL fix from CRT-7H2W: make the head anchor intent-aware in `begin_review`'s verify-resolutions branch — when a COMMITTED delta exists since the prior review's `commit_reviewed` (builder committed the fix; PR-gate case), anchor `head_tree = capture["head_tree"]` (committed HEAD) and note-and-exclude WIP exactly like the cumulative branch; when there is no committed delta (fix-in-progress against a dirty subset of prior `files_reviewed`), keep the working-tree anchor so the Stop-hook gate composes and the PR gate correctly can't pass until the fix is committed. Preserves CRT-4J8W's dirty-tree-verify capability. Also ship the cheap diagnostic: verify-resolutions WARNs when it anchors a dirty tree carrying judgeable WIP, and `check-cumulative-critic`'s `uncovered` remedy gains a dirty-tree branch.
- **Depends on:** none (independent of Chunks 01–02)
- **Artifacts consumed:** discodon backlog CRT-T9RX; local CRT-7H2W (recommended layered-pair fix, exact sites); `lib/coverage_algebra.py:5-8` (two-target design); `lib/critic_mode.py:452` (`_committed_files_since`)
- **Deliverables:** `lib/critic_consolidate.py` (verify-resolutions branch ~`:239-290` — intent-aware head anchor; dirty-judgeable-WIP WARNING), `lib/gates.py` (`check_cumulative_critic` `uncovered` remedy ~`:969-979` — dirty-tree hint), `tests/test_critic_consolidate.py` (update the pinning test at ~`:340-345` that fixes the current dirty-tree/no-head_commit behavior), `tests/test_cumulative_gate.py` (regression: committed fix + judgeable uncommitted WIP → gate covered after verify-resolutions; docs-only WIP boundary still covered)
- **Tests:** unit + integration — verify-resolutions with a committed delta anchors committed HEAD and the PR gate composes with a judgeable uncommitted file present; verify-resolutions with no committed delta keeps the working-tree anchor (Stop-hook composes, PR gate legitimately pending); the dirty-judgeable-WIP WARNING fires; docs-only WIP free-edge case unchanged
- **Acceptance criteria:** the PR #1472-class scenario (cumulative → commit fix → verify-resolutions with a stray judgeable uncommitted file) reaches `covered` without a stash dance; the fix-in-progress semantics and CRT-4J8W dirty-tree-verify capability are preserved
- **Type:** bugfix
- **Critic mode:** final
  <!-- Governance-protected coverage/consolidation core with existing pinning tests; the head-anchor
       change is behavior-shifting across two gate targets — worth the full 7-goal review at this chunk. -->
- **Done when:**
  1. Acceptance criteria met and full suite passes
  2. `/prawduct:critic` run and blocking findings resolved
  3. Committed and chunk marked `[x]` in Status

### Chunk 04: PDT-WT9K — critic-begin worktree visibility, mismatch-detection, refuse-on-unresolvable

- **Description:** The dangerous silent-wrong-tree root cause is already fixed (cwd-follow via `resolve_project_dir`), but the three named hardening asks remain. (a) Visibility: `cmd_critic_begin` prints the worktree path, branch, and base ref it resolved (and `cmd_infer_critic_mode` emits the resolved worktree+branch on stderr, leaving stdout `<mode>|<rationale>` unchanged for the skill parser); the manifest gains nullable `worktree`/`branch` fields. (b) Mismatch-detection: before dispatch, cross-check `git worktree list` — if the branch under review is checked out on a *different* worktree, or the session's cwd toplevel differs from the resolved `project_dir`, block loudly naming both paths. (c) Refuse-on-unresolvable: keep `resolve_project_dir` fail-open (lib convention), but add a refusal at the dispatch boundary when `_git_toplevel(cwd)` is non-None and differs from the resolved `project_dir`.
- **Depends on:** none (independent; `begin_review` manifest changes coordinate with Chunk 03's file but different function region — sequence after 03 to avoid churn)
- **Artifacts consumed:** discodon backlog PDT-WT9K; local CRT-6W2N (general worktree-workflow gap); `lib/briefing.py:385-434` (`_detect_worktrees`), `lib/gitstate.py:79-117` (`resolve_project_dir`)
- **Deliverables:** `lib/critic_consolidate.py` (`begin_review` — add `worktree`/`branch` to the manifest), `lib/critic_consolidate.py` (`validate_manifest` — nullable `worktree`/`branch`), `bin/prawduct-hook` (`cmd_critic_begin` visibility print + mismatch-detection + refuse; `cmd_infer_critic_mode` stderr worktree line), `tests/` (regression: manifest carries worktree+branch; a branch checked out elsewhere is detected; a cwd/project_dir toplevel mismatch refuses)
- **Tests:** unit — manifest includes `worktree`/`branch`; `validate_manifest` accepts them nullable; mismatch-detection flags a foreign-worktree branch and a cwd-vs-resolved-toplevel divergence; the common in-worktree case still dispatches cleanly
- **Acceptance criteria:** critic-begin surfaces the tree it will review (path/branch/base); a branch-under-review checked out elsewhere, or a cwd/resolved-dir mismatch, blocks with a clear message rather than silently reviewing the wrong tree; the normal single-worktree flow is unaffected
- **Type:** bugfix
- **Critic mode:** chunk
- **Done when:**
  1. Acceptance criteria met and full suite passes
  2. Direct CLI exercise: `critic-begin` prints the resolved worktree/branch/base
  3. `/prawduct:critic` run and blocking findings resolved
  4. Committed and chunk marked `[x]` in Status; run `final`/`cumulative` for the plan before PR
