---
artifact: build-plan
version: 2
# Explicit scope (NOT null). Tag the change-log entry `scope=release-tooling`
# when shipping so `regen-views` (the very tool Chunk 01 fixes) flips the
# checkboxes below correctly. Do NOT hand-edit the checkboxes.
scope: release-tooling
depends_on: []
last_validated: null
lifecycle: completed
archived: 2026-08-10
released_in: v2.0.6
maintained: false
---

> **Archived — no longer maintained.** This plan records what was built, not what will be. Do not edit it to reflect later changes; write those where they are true.

## Requirements Confidence

**Level:** High

**Why:** Five pre-triaged backlog items, each with an implementation-ready design produced by a
parallel read-only investigation (5 agents, all high-confidence). REL-4T8N's open question
("how does regen map a `scope=` to its build-plan FILE?") is answered: every batched plan already
carries `scope:` frontmatter and `lib/views.py` already parses it — so the map is a frontmatter
scan over `artifacts/*.md`, no new convention. The release-notes bug, the verify-chunk-refs
false-positive, the PR step-7 model mismatch, and the test-collection worktree hazard are each a
single, well-bounded change with named files and behavioral tests.

**Open assumptions / unknowns:** None material. Decisions taken on the investigation's open
questions: (a) multi-scope regen enumerates entries with `status ∈ {shipped, merged}`;
(b) duplicate-scope → warn + keep first by sorted filename (non-fatal); (c) skipped/duplicate-scope
warnings via a separate pure diagnostic fn (mirrors `validate_status_values`) — `plan_regen`'s
`(enabled, results)` signature is UNCHANGED (9 call sites preserved); (d) status-result de-dupe key
= resolved plan Path; (e) release-notes multi-entry sub-heading from `scope=` with title fallback,
shared trailer once per release, `**Scope:**` omitted in multi-entry sub-sections (the `###` heading
carries it); (f) BLD-8F2Q splits on `::` and existence-checks only the path part, symbol stays
deferred (BLD-5V8F); (g) PR step-7 branches on `resolve-base` (base=main → delete+clear pointer;
base=develop → retain); (h) TST-9K4W excludes the whole `.claude/` path component, Layer-2
`norecursedirs` SKIPPED as redundant (collection is already scoped by `testpaths=["tests"]`).

**What would raise confidence:** N/A.

## Status

<!-- Derived view. Mark a chunk shipped by adding a change-log entry tagged
     scope=release-tooling / status=shipped, then run `prawduct-hook regen-views`.
     Do NOT hand-edit the checkboxes. Chunks are built sequentially in the main
     tree (they share lib/views.py, bin/prawduct-hook, docs/release-process.md);
     parallel worktree builds were rejected as conflict-prone for ~zero gain. -->

- [x] Chunk 01: REL-4T8N-A — regen-views handles MULTIPLE release-pending plans (scope→file map, enumerate all scopes)
- [x] Chunk 02: REL-4T8N-B — release-notes.md renders ALL entries sharing a `release=` tag (no scope collapse / chunk union)
- [x] Chunk 03: BLD-8F2Q — verify-chunk-refs existence-checks only the pre-`::` path of a `path::symbol` token
- [x] Chunk 04: PR-7Q3M — PR merge-flow step 7 branches: delete-at-release vs retain-while-release-pending
- [x] Chunk 05: TST-9K4W — structural test collectors exclude the `.claude/` worktree subtree
Context: Plan authored 2026-06-04. Bundles REL-4T8N (both symptoms) with three adjacent
release/build-tooling fixes that cohere in one PR (this repo's roi-batch/cleanup-batch pattern).
Investigation via a 5-agent read-only workflow (run wf_4ee7d42a-761). Build is sequential in the
main tree; one cumulative Critic gates the PR; one squash merge to develop. The four v2.0.5 plans
are already `[x]` (shipped), so the Chunk-01 dogfood of multi-scope regen is IDEMPOTENT on them
(proves no cross-scope leakage / no regression); the flip itself is proven by synthetic fixtures.

## Scaffolding

N/A — existing repo, no scaffold. Test runner: `python3 -m pytest` (xdist; use `-n0` to isolate a
file when diagnosing the known TST-4P8H worker-crash flake).

## Build Chunks

### Chunk 01: REL-4T8N-A — multi-scope regen-views

- **Type:** code
- **Done when:**
  1. `lib/views.py` gains `build_scope_to_plan_map(artifacts_dir) -> dict[str, Path]` (frontmatter
     `scope:` scan via the existing `_parse_build_plan_frontmatter_scope`; duplicate scope → keep
     first by sorted filename) and `collect_release_pending_scopes(entries) -> list[str]` (distinct
     `scope=` from `status ∈ {shipped, merged}` entries, newest-first, deduped).
  2. The status-view block of `plan_regen` is refactored to emit ONE status `ViewRegenResult` per
     release-pending plan (de-duped by resolved Path), each re-detecting its own scope via
     `build_status_view`. Backward-compat fallback preserved EXACTLY: when no scope resolves to a
     plan file, resolve via `resolve_build_plan_path` and raise `FileNotFoundError` as today. The
     `active_build_plan` pointer's plan is always included even if its scope isn't release-pending.
  3. A pure diagnostic fn (e.g. `diagnose_scope_plan_coverage(change_log, artifacts_dir) -> list[str]`)
     surfaces "scope=X has no matching plan file — skipped" and duplicate-scope warnings;
     `cmd_regen_views` prints them on stderr (mirroring the `validate_status_values` loop). No
     exit-code change for a skipped scope (warn + skip). `plan_regen` signature unchanged.
  4. `docs/release-process.md` step 4 updated: `regen-views` now regenerates ALL release-pending
     plans in one pass — the manual "point the pointer at each plan in turn" workaround is removed.
  5. Tests in `tests/test_views.py` cover: scope→plan map (multi/duplicate/no-frontmatter);
     four-scope multi-plan flip with no cross-scope leakage; scope-with-no-plan warns+skips;
     single-plan/no-scope back-compat byte-identical; idempotent second pass; pointer'd no-scope
     plan still regenerated. Full suite green.
  6. `/prawduct:critic` (chunk) run; blocking findings resolved. Committed; chunk marked `[x]` via
     change-log tag + regen-views (not hand-edited).

### Chunk 02: REL-4T8N-B — release-notes renders all entries per release

- **Type:** code
- **Visual change:** yes  (the regenerated `release-notes.md` digest is a human-facing artifact)
- **Done when:**
  1. `_collect_releases` stops collapsing: returns `list[{release, entries:[{title, chunks, scope}]}]`
     keeping each contributing entry's OWN title + OWN (sorted, de-duped) chunks — no union.
  2. `build_release_notes_view` renders single-entry releases FLAT (byte-identical to today) and
     multi-entry releases with one `### <scope|title>` sub-section per entry (its own
     `**Chunks shipped:**`), a shared `See .prawduct/change-log.md …` trailer once per release.
     Signature `(change_log_content) -> str | None` unchanged; None-when-empty preserved.
  3. `tests/test_views.py` `TestBuildReleaseNotesView` updated: the union-asserting
     `test_multiple_entries_same_release_merged` is rewritten to assert per-scope sub-sections
     (chunks NOT unioned); add the four-scope v2.0.5 regression; single-entry/ordering/idempotent/
     no-release tests still pass.
  4. Run `prawduct-hook regen-views` (now working via Chunk 01) to regenerate
     `.prawduct/release-notes.md`; verify the `## v2.0.5` section shows four `###` sub-sections with
     correct per-scope chunks; verify NO unintended changes to the four shipped plans (idempotent).
  5. Full suite green; `/prawduct:critic` (chunk); committed; marked `[x]`.

### Chunk 03: BLD-8F2Q — verify-chunk-refs `path::symbol`

- **Type:** code
- **Done when:**
  1. In `bin/prawduct-hook` `_parse_build_plan_chunk_refs`: derive `path_part = token.split("::", 1)[0]`,
     run `_looks_like_file_path` on `path_part`, store `path_part` as the ref AND in the dedup key.
     `new `-qualifier exclusion (matches on token start offset) still composes. Docstring updated.
  2. Symbol verification stays DEFERRED (BLD-5V8F) — out of scope here.
  3. `templates/build-plan.md` HTML comment notes `path::symbol` is tolerated (only the path is
     existence-checked). (`methodology/planning.md` left untouched — proportional; budget-bound file.)
  4. Net-new tests (natural home: `tests/test_build_plan_resolution.py`, else a focused new file):
     existing `path::symbol` → no missing-ref / exit 0; non-existent `path::symbol` → reported as
     the path portion only; `new ` + `::` forward-ref → skipped; same-line dup → one check; plain
     path unchanged; degenerate `::onlysymbol` (no `/`) → skipped.
  5. Full suite green; `/prawduct:critic` (chunk); committed; marked `[x]`.

### Chunk 04: PR-7Q3M — PR merge-flow step 7 conditioning

- **Type:** doc-only  (skill prose; no executable code)
- **Done when:**
  1. `skills/pr/SKILL.md` Merge-Flow step 7 rewritten to branch on `prawduct-hook resolve-base`:
     base=main (ships now / release surface) → delete the plan resolved via the `active_build_plan`
     pointer (NOT the hardcoded literal) AND clear the pointer; base=develop (release-pending) →
     RETAIN both plan file and pointer until the develop→main release flips `status=shipped`. The
     latent hardcoded-`build-plan.md` path bug is fixed in the same edit. Cross-references
     `docs/release-process.md` status values + the learnings KEEP-the-build-plan entry.
  2. `docs/release-process.md`: one cross-link sentence in the `status=merged` bullet pointing at
     the PR step-7 retain branch (coherent with Chunk 01's step-4 edit — same file, one pass).
  3. `/prawduct:critic` (chunk, doc-only protocol); committed; marked `[x]`.

### Chunk 05: TST-9K4W — test collectors skip `.claude/` worktrees

- **Type:** code  (test-support code; the deliverable is the hardened collectors + regression tests)
- **Done when:**
  1. `tests/preferences/test_test_location.py`: add `.claude` to `EXCLUDED_DIRS`; refactor
     `_all_test_files` to accept an optional `root` param for testability; docstring names `.claude/`.
  2. `tests/test_plugin_methodology_digest.py`: the canonical-copy rglob also excludes paths with a
     `.claude` component (factored into a small testable helper).
  3. Regression tests: a synthetic `.claude/worktrees/wf_X/tests/.../test_dummy.py` is NOT flagged
     misplaced; a synthetic `.claude/worktrees/wf_X/methodology/session-digest.md` is NOT counted a
     duplicate. Layer-2 `norecursedirs`/`--ignore` SKIPPED (redundant given `testpaths=["tests"]`)
     — rationale recorded in the chunk/reflection.
  4. Full suite green; `/prawduct:critic` (chunk); committed; marked `[x]`.
  5. **Cumulative-final:** after Chunk 05, run `/prawduct:critic cumulative` (gates `/prawduct:pr create`).

## Verification Strategy

- **Per chunk:** full `python3 -m pytest` (xdist), plus the chunk's own new behavioral tests.
- **Dogfood (Chunks 01–02):** run `prawduct-hook regen-views` against this real repo — it must
  (a) not error (proving the can't-run-without-a-single-plan defect is fixed), (b) leave the four
  shipped v2.0.5 plans untouched (idempotent — `git diff` empty for them), (c) rewrite
  `release-notes.md` with four correct `### ` sub-sections under `## v2.0.5`.
- **Bundle:** one `/prawduct:critic cumulative` over `merge-base...HEAD` before the PR.
- **Adversarial verification:** a parallel workflow re-checks the riskiest claims (back-compat
  preserved, no cross-scope leakage, dogfood output correct) while/after the Critic runs.
