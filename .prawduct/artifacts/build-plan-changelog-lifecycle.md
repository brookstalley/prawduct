<!-- Build Plan — change-log lifecycle hardening (REL-9F2T)
     Closes the silent-drop family in the statusless → merged → shipped state
     machine. All four failures were observed live; reproductions are on the
     archived REL-2N8K / REL-6C3W / VWS-4D8J backlog items.
-->
---
artifact: build-plan
version: 2
scope: changelog-lifecycle
depends_on: []
last_validated: 2026-06-10
---

## Requirements Confidence

**Level:** High

**Why:** All four broken transitions are observed-live failures with filed
reproductions, and the fix-shape was written and groomed on the backlog item
(REL-9F2T); the remaining decisions are implementation semantics, recorded
below as vetoable assumptions.

**Open assumptions / unknowns:**

- [ASSUMPTION: `stamp-merged` stamps **every** statusless *tagged* entry on the
  integration branch, not only the just-merged branch's entries — idempotent and
  self-healing (retroactively repairs previously missed stamps). Entries with no
  tag line at all (historical, pre-convention) are never touched. | MED impact |
  user can override]
- [ASSUMPTION: multiple tag lines per entry are **unioned** (chunks lists
  merged, order-preserving dedup; scalar keys first-wins) with a WARNING, rather
  than rejected — regen keeps working on an imperfect log while the author is
  told to fix it. | LOW impact | user can override]
- [ASSUMPTION: the missing-entry probe gates at **PR create** (`/prawduct:pr`
  Step 1 area), is exempt for doc-only (`.md`-only) diffs, and **fails closed**
  (un-evaluable git state → exit non-zero with a named reason, same posture as
  `check-pr-doc-only`). | MED impact | user can override]
- [ASSUMPTION: the probe requires a **new H2 entry added** in the branch's
  change-log diff (a `+## ` line), not merely any edit touching
  `change-log.md`. | LOW impact | user can defer]

**What would raise confidence:** N/A.

## Status

- [ ] Chunk 01: Multi-tag-line parsing — union + warning
- [ ] Chunk 02: Statusless lifecycle — stamp-merged + statusless scope validation
- [ ] Chunk 03: Missing-entry probe at the PR boundary
Context: Chunk 01 done 2026-06-10 (parse_change_log consumes consecutive tag
lines, chunks-union + first-wins scalars, validate_tag_line_multiplicity wired
into regen-views stderr; Critic chunk-mode passed — its one WARNING, missing
hook-level stderr test, resolved via TestRegenViewsMultiTagLineWarning).
Next: Chunk 02 (stamp-merged + statusless scope validation).

## Scaffolding

Not applicable — mature repo; existing pytest suite (`python3 -m pytest -q`),
existing `lib/` + `bin/prawduct-hook` structure. No new dependencies.

### Verification Strategy

Beyond unit tests: run the touched hook commands against **this real repo**
(`prawduct-hook regen-views`, `stamp-merged`, `check-change-log-entry`) and
against synthetic git fixtures (the pattern in `tests/test_cumulative_gate.py`).
The real change-log is the richest fixture — any new warning it emits is
triaged as part of acceptance (true positives get the change-log fixed).

## Project Structure

No new modules. Change-log parsing/mutation stays in `lib/views.py` (it owns
the change-log canonical-store logic); diff-base/file-set probes stay in
`lib/coverage.py` (it owns diff-base resolution); `bin/prawduct-hook` gets thin
`cmd_*` wrappers only, keeping its top level lib-free.

## Build Chunks

### Chunk 01: Multi-tag-line parsing — union + warning (VWS-4D8J)

- **Description:** `parse_change_log` currently settles tag-vs-no-tag at the
  first non-blank line under an entry's H2 and ignores everything after — a
  second `<!-- prawduct: ... -->` line is silently dropped (live: the
  reviewer-model-tiering `chunks=02` tag nearly shipped unflipped at v2.1.0).
  Change the entry-body scan to consume **all consecutive tag lines** (blank
  lines between them tolerated, same leniency as before the first tag line;
  the first non-blank non-tag line still ends the scan). Union semantics:
  `chunks` lists are concatenated with order-preserving dedup; scalar keys are
  first-wins, with any conflicting later value recorded. `ChangeLogEntry`
  gains `tag_line_count: int` and `tag_conflicts: list[str]` fields. A new
  pure validator `validate_tag_line_multiplicity(entries)` (mirroring
  `validate_status_values`) returns a WARNING string per multi-tag entry —
  naming the union applied and any first-wins conflicts — and
  `cmd_regen_views` surfaces it on stderr next to the status-typo warnings.
- **Depends on:** none
- **Artifacts consumed:** this plan; archived VWS-4D8J body in
  `.prawduct/backlog.md` Archive
- **Deliverables:** `lib/views.py` (`parse_change_log`, `ChangeLogEntry`, new
  `validate_tag_line_multiplicity`), `bin/prawduct-hook` (`cmd_regen_views`
  warning surface), tests in `tests/test_views.py`
- **Tests:** single-tag-line entries parse identically (regression); two tag
  lines union `chunks` across both; conflicting scalar (e.g. two different
  `status=`) keeps first + records conflict; validator warns on multi-tag and
  is silent on single-tag; tag line after intervening prose is still NOT
  consumed (spec preserved); blank line between consecutive tag lines
  tolerated; regen-views stderr carries the new warning (hook-level test if an
  existing harness covers regen-views stderr, else lib-level).
- **Acceptance criteria:** `python3 -m pytest -q` passes; `prawduct-hook
  regen-views` against this repo's real change-log emits no NEW unexplained
  warnings (any multi-tag warning it does emit is triaged and the change-log
  fixed if a true positive).
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run (inferred `chunk` mode) and blocking findings resolved
  3. Committed and Context updated in Status

### Chunk 02: Statusless lifecycle — stamp-merged + statusless scope validation (REL-2N8K + audit finding d)

- **Description:** Two halves of the same hole — statusless entries are
  invisible to the lifecycle. (1) **Stamping:** new pure function
  `lib/views.py::stamp_merged(content)` returning `(new_content,
  stamped_titles)` — for every entry that HAS a tag line and NO `status=` key,
  insert `status=merged` into the tag line, preserving the other tags and
  their order; entries with no tag line, or with `status=shipped`/`merged`,
  are untouched; idempotent. New hook command `prawduct-hook stamp-merged`
  with a branch guard: refuses (exit 1, named reason) unless the current
  branch IS the integration base (the `base_branch:` knob, falling back to
  the default candidates) — stamping on a feature branch would lie. Exit 0
  with "nothing to stamp" on a no-op. (2) **Validation:**
  `diagnose_scope_plan_coverage` extends its no-plan-file check to statusless
  entries that carry a `scope=` tag (message distinguishes "statusless
  (unreleased)" from `status=merged`); `status=shipped` stays excluded.
  (3) **Prose:** `skills/pr/SKILL.md` Merge Flow gains a step after
  step 5 (switch to base + pull): run `prawduct-hook stamp-merged` and commit
  the stamp (small `chore:` commit, no attribution trailers).
  `docs/release-process.md` step 3 reworded to flip **every unreleased
  entry — statusless OR `status=merged`** — to `status=shipped` (the v2.0.14
  incident: 8 of 10 entries reached release statusless and were silently
  dropped by the literal reading); the "Change-log `status=` values" section
  documents `stamp-merged` as the stamping mechanism and that a statusless
  entry on the integration branch means the stamp was missed, not that the
  work is unmerged.
- **Depends on:** Chunk 01 (tag-line parsing semantics settled first)
- **Artifacts consumed:** this plan; archived REL-2N8K body; `docs/release-process.md`
- **Deliverables:** `lib/views.py` (`stamp_merged`,
  `diagnose_scope_plan_coverage`), `bin/prawduct-hook` (new `cmd_stamp_merged`
  + usage), `skills/pr/SKILL.md`, `docs/release-process.md`, tests in
  `tests/test_views.py` (+ hook-level branch-guard test where the existing
  fixtures support it)
- **Tests:** stamp: statusless tagged entry gains `status=merged` with other
  tags/order preserved; untagged entry untouched; shipped/merged untouched;
  idempotent (second run = no-op); multi-tag entry (post-Chunk-01) stamps
  without corruption. Branch guard: non-base branch refused with named
  reason; base branch proceeds. Diagnose: statusless + `scope=` + no plan
  file warns; statusless without `scope=` silent; shipped + no plan still
  silent; merged behavior unchanged. Guardrail: `tests/test_pr_reviewer.py`
  flow checks still pass after the SKILL.md edit.
- **Acceptance criteria:** `python3 -m pytest -q` passes; `prawduct-hook
  stamp-merged` dry-run against this repo (on the feature branch) is refused
  by the branch guard; `diagnose_scope_plan_coverage` against the real
  change-log triaged as in Chunk 01.
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. `/prawduct:critic` run (inferred `chunk` mode) and blocking findings resolved
  3. Committed and Context updated in Status

### Chunk 03: Missing-entry probe at the PR boundary (REL-6C3W)

- **Description:** A code-changing branch can merge with no change-log entry
  at all and nothing flags it (CRT-7B4M/#82, reconstructed at the v2.0.16
  release). New gate `lib/coverage.py::check_change_log_entry(project_dir)`:
  resolve the diff base via the existing `_coverage_resolve_base`; diff
  `base...HEAD --name-only`. All-`.md` diff → exit 0 (doc-only work needs no
  entry to flip). Any non-`.md` file changed → require
  `.prawduct/change-log.md` among the changed files AND a new H2 added in its
  diff (a `+## ` line in `git diff base...HEAD --
  .prawduct/change-log.md`); otherwise exit 1 with a named reason
  (`no-entry: ...` / `entry-edited-not-added: ...`). Un-evaluable state
  (`no-base`, `git-failed`) exits 1 with the named reason — fail closed,
  mirroring `check_pr_doc_only`. Thin `cmd_check_change_log_entry` wrapper in
  `bin/prawduct-hook` + usage line. `skills/pr/SKILL.md` Create flow gains
  the probe alongside the Step 1 checks: if it exits non-zero, STOP and add
  the entry before proceeding (manual judgment on `no-base`/`git-failed`).
- **Depends on:** Chunk 02
- **Artifacts consumed:** this plan; archived REL-6C3W body; `lib/coverage.py`
- **Deliverables:** `lib/coverage.py` (`check_change_log_entry`),
  `bin/prawduct-hook` (wrapper + usage), `skills/pr/SKILL.md`, new
  `tests/test_change_log_entry_gate.py` (git-fixture pattern from
  `tests/test_cumulative_gate.py`)
- **Tests:** code change + new entry → 0; code change, change-log untouched →
  1 (`no-entry`); code change, change-log edited but no new H2 → 1
  (`entry-edited-not-added`); doc-only diff, no entry → 0; empty diff → 0
  (nothing to require); unresolvable base → 1 with named reason. Guardrail:
  PR-skill flow tests still pass.
- **Acceptance criteria:** `python3 -m pytest -q` passes; `prawduct-hook
  check-change-log-entry` run live on this branch exits 0 once this work's
  own change-log entry exists (it is its own first consumer).
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass; this branch's change-log entry
     written (scope=changelog-lifecycle, chunks=01,02,03 — statusless on the
     feature branch per the lifecycle this very plan hardens)
  2. Committed, then `/prawduct:critic cumulative` run against
     `merge-base...HEAD` (this chunk's review IS the PR gate; no separate
     `final`) and blocking findings resolved
  3. Chunk marked done in Context; backlog REL-9F2T updated via
     `/prawduct:backlog` at PR merge

## Early Feedback Milestone

**Milestone chunk:** 01
**What the user can do:** run `prawduct-hook regen-views` and see multi-tag
entries unioned + warned instead of silently half-parsed.

## Governance Checkpoints

**Commit & PR cadence:** Commit per chunk after `/prawduct:critic` passes; PR
via `/prawduct:pr` after Chunk 03's one `/prawduct:critic cumulative` (its
review AND the PR gate) passes.

- After Chunk 01: chunk-mode review — parser semantics are the keystone the
  other two chunks build on; escalate to `final` only if the Critic flags
  coherence risk.
- After Chunk 03: cumulative review over `merge-base...HEAD` (declared
  `Type: cumulative-final` above).
