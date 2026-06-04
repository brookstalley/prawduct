---
artifact: build-plan
version: 2
# Explicit scope (NOT null, and DISTINCT from `roi-batch`) — distinct scope keeps
# this batch's chunk-ID namespace (01–09) from colliding with the still-pending
# roi-batch plan's chunks 01–05 at regen time (collect_shipped_chunks is
# scope-filtered). Tag change-log entries `scope=roi-batch-2` when shipping.
scope: roi-batch-2
depends_on: []
last_validated: null
---

## Requirements Confidence

**Level:** High

**Why:** Nine backlog items, all from the 2026-06-04 rough-edges hunt + one older re-verified
item, each verified real before filing with a written fix-shape and a named file set. Two are
silent-degradation correctness bugs (STH-2J9F exit code, ADV-9K2T corruption swallow), one is a
release-process footgun (VWS-3K7P typo-guard), the rest are gate-precision, a refactor-to-constant,
and pure test coverage. Scope is closed.

**Open assumptions / unknowns:** None material. STH-6B4R's two gate sites are anchored by
grep (`findings_mtime > session_start` and the cumulative-critic equivalent); the agent confirms
the exact lines before editing (the backlog's line numbers predate recent edits).

**What would raise confidence:** N/A.

## Status

<!-- Derived view. Mark a chunk shipped by adding a change-log entry tagged
     scope=roi-batch-2 / status=shipped, then run `prawduct-hook regen-views`.
     Do NOT hand-edit the checkboxes. Chunks are INDEPENDENT (no depends-on) and
     are built by ONE workflow with three file-disjoint lanes (see Build model). -->

- [ ] Chunk 01: VWS-3K7P — validate change-log status= values + reconcile views.py docstring
- [ ] Chunk 02: STH-2J9F — regen-views returns exit 1 (not 0) on ImportError
- [ ] Chunk 03: VWS-8M2Q — harden views.py tag/frontmatter parsers
- [ ] Chunk 04: STH-6B4R — gate freshness timestamp comparison precision + tie rule
- [ ] Chunk 05: STH-1W5N — centralize trivial-change protected-path bounds into a documented constant
- [ ] Chunk 06: TST-1D5W — tighten _validate_evidence_schema against bool-as-int
- [ ] Chunk 07: TST-7Q3D — stop-gate regression coverage gaps (3 cases)
- [ ] Chunk 08: ADV-9K2T — advisory_store surfaces corruption via a .corrupt sentinel
- [ ] Chunk 09: TST-4H8M — unit coverage for migrate _collapse_blank_runs edge cases
Context: Plan authored 2026-06-04. Built by ONE workflow, three file-disjoint lanes:
HOOK (bin/prawduct-hook + lib/views.py + their tests; chunks 01–07, run as two sequential
sub-agents A=01–03, B=04–07 because both touch bin/prawduct-hook), ADV (lib/advisory_store.py;
chunk 08), MIG (tests/test_plugin_migrate.py; chunk 09). The workflow does the BUILD half only
(fix + regression test + SCOPED test run, no commit, no Critic). The launching session does the
governance half: full suite → single `/prawduct:critic cumulative` → commit → `/prawduct:pr`
→ archive the 9 backlog items + change-log.

## Scaffolding

N/A — existing repo, no scaffold. Test runner: `python3 -m pytest`.

## Project Structure

N/A — edits land in existing trees: `lib/views.py`, `lib/advisory_store.py`, `bin/prawduct-hook`,
`tests/`.

## Build Chunks

<!-- Build model: the chunks are independent. ONE background workflow builds them across three
     file-disjoint lanes against a single feature branch (`fix/roi-batch-2`). File sets are
     disjoint across CONCURRENT agents by construction, so the shared working tree never sees a
     same-file race. The HOOK lane's two sub-agents (A then B) both touch bin/prawduct-hook, so
     they run SEQUENTIALLY within the lane. Per-chunk "Done when" Critic steps are satisfied ONCE,
     cumulatively, by the launching session after the workflow finishes — see Governance. -->

### Lane HOOK-A (owns lib/views.py, bin/prawduct-hook::cmd_regen_views, tests/test_views.py)

#### Chunk 01: VWS-3K7P — validate change-log `status=` values + reconcile docstring
**Type:** code
**Acceptance criteria:**
- New pure helper `validate_status_values(entries) -> list[str]` in `lib/views.py` returns a
  warning string for every change-log entry whose `status=` tag is present but not in
  `{shipped, merged}` (e.g. `status=shippd`). Empty list when all are valid/absent.
- `bin/prawduct-hook::cmd_regen_views` calls it and prints each warning to stderr (NON-fatal —
  does not change the exit code or the flip rule).
- The `lib/views.py` module docstring (~line 19) status enum reconciled from
  `shipped | in-progress | deferred` to `shipped | merged` (note: only `shipped` flips checkboxes;
  `merged` is the release-pending intermediate). The flip rule itself is UNCHANGED — only `shipped`
  ever flips.
- Tests in `tests/test_views.py`: a typo `status=shippd` yields one warning; valid `shipped`/`merged`
  yield none; absent status yields none.
**Done when:** scoped `pytest tests/test_views.py` green; `/prawduct:critic` (cumulative, by launching session).

#### Chunk 02: STH-2J9F — regen-views returns exit 1 on ImportError
**Type:** code
**Acceptance criteria:**
- `cmd_regen_views`'s `except ImportError:` branch returns **1** (honest-failure), matching
  `accept-operator-verification`/`verify-operator-verification`'s ImportError handling — a
  state-mutating command must not report success on a broken install.
- The disabled-by-config path (`if not enabled: return 0`) and the success path stay **0**.
- Test asserts ImportError path → exit 1 (in `tests/test_views.py`).
**Done when:** scoped tests green; cumulative Critic.

#### Chunk 03: VWS-8M2Q — harden views.py tag/frontmatter parsers
**Type:** code
**Acceptance criteria:**
- `parse_tag_line` (or the scope-rollup formatter) no longer emits unparseable YAML when a chunk
  ID contains a quote/special char — validate chunk IDs against the safe charset (mirror
  `CHUNK_LINE_RE`'s `[A-Za-z0-9_-]`) and drop/skip invalid ones, OR `yaml.safe_dump` the rollup
  block. A malformed chunk ID must not corrupt `scope_rollups:`.
- `_parse_build_plan_frontmatter_scope`: an UNCLOSED HTML comment is handled explicitly — either
  flag it or document the leniency in the docstring; add the malformed-frontmatter test the
  v1.5.1 R5 note asked for and never landed.
- Tests in `tests/test_views.py` for both corners.
**Done when:** scoped tests green; cumulative Critic.

### Lane HOOK-B (owns bin/prawduct-hook gate/trivial/evidence regions, tests/test_plugin_runtime.py, tests/test_trivial_fileset_gate.py)

#### Chunk 04: STH-6B4R — gate freshness timestamp comparison precision + tie rule
**Type:** code
**Acceptance criteria:**
- The stop-hook Critic gate (`findings_mtime > session_start`, ~L1796–1804) and the
  check-cumulative-critic equivalent compare timestamps at IDENTICAL precision
  (`%Y-%m-%dT%H:%M:%SZ` both sides) OR via numeric epoch seconds — no lexicographic mismatch.
- The tie case is DEFINED and tested: `findings_mtime == session_start` is treated as NOT fresh
  (rejected) for the Critic-gate sites (consistent with the existing strict `>`). Document the
  tie-breaking rule in a comment.
- Regression test for the tie (findings mtime exactly == session-start → gate not satisfied).
**Done when:** scoped `pytest tests/test_plugin_runtime.py` green; cumulative Critic.
NOTE: Do not change the evidence-freshness `>=` site (`_test_status`, ~L466–477) unless needed —
its `>=` is a deliberately different convention; if touched, preserve its semantics and test it.

#### Chunk 05: STH-1W5N — centralize trivial-change protected-path bounds
**Type:** code
**Acceptance criteria:**
- The Type:trivial / doc-only fileset bounds (skills/, methodology/, templates/, CLAUDE.md,
  test deletions, new files) currently inline in `_classify_trivial_change` /
  `_is_trivial_fileset_eligible` (~L3111–3180) are extracted to a documented module-level
  constant (e.g. `_TRIVIAL_PROTECTED_PATHS` frozenset) with a one-line rationale per path,
  referenced from every call site. Behavior-preserving refactor.
- An existing trivial-fileset test still passes; add a test asserting the constant is the source
  of truth (the bound list is non-empty and contains the documented paths).
**Done when:** scoped `pytest tests/test_trivial_fileset_gate.py tests/test_plugin_runtime.py` green; cumulative Critic.

#### Chunk 06: TST-1D5W — tighten _validate_evidence_schema against bool-as-int
**Type:** code
**Acceptance criteria:**
- `_validate_evidence_schema` (~L535) rejects a bool where an int is required (Python `bool` is a
  subclass of `int`, so `{"passed": True}` currently slips through `isinstance(v, int)`). Add
  `and not isinstance(v, bool)` (with a comment) to the int-field checks.
- New test `TestValidateEvidenceSchema::test_bool_rejected_for_int_field` in
  `tests/test_plugin_runtime.py`.
**Done when:** scoped tests green; cumulative Critic.

#### Chunk 07: TST-7Q3D — stop-gate regression coverage gaps (test-only)
**Type:** code
**Acceptance criteria:** add three regression cases to `TestPluginStopGate`
(`tests/test_plugin_runtime.py`), NO runtime change:
- (a) verify-resolutions mode out-of-scope file blocking: findings with `files_reviewed=[a.py]`,
  diff modifies `[a.py, b.py]` → assert exit 2 / out-of-scope reason.
- (b) Type:trivial chunk modifying files outside the allowed bounds → assert exit 2 / fileset reason.
- (c) gate-waiver unknown key → assert stderr diagnostic WITHOUT blocking.
**Done when:** scoped `pytest tests/test_plugin_runtime.py` green; cumulative Critic.

### Lane ADV (owns lib/advisory_store.py, tests/test_advisory_store.py)

#### Chunk 08: ADV-9K2T — advisory_store surfaces corruption via a .corrupt sentinel
**Type:** code
**Acceptance criteria:**
- In `read_store`, when an EXISTING `.advisories.json` fails to parse (`json.JSONDecodeError`) or
  parses to the wrong shape (not a dict / `advisories` not a list), preserve the corrupt content
  aside as `.advisories.json.corrupt` (best-effort) BEFORE returning the empty default, so the
  corruption is surfaced for user recovery instead of silently swallowed. A MISSING file stays the
  normal first-run empty path (no sentinel). An `OSError` (unreadable) stays empty, no sentinel
  (can't read it to preserve it). Remains non-raising / best-effort.
- Tests in `tests/test_advisory_store.py`: corrupt JSON → empty store returned AND `.corrupt`
  sentinel written with the original bytes; wrong-shape JSON → sentinel written; missing file →
  no sentinel; valid file → no sentinel.
**Done when:** scoped `pytest tests/test_advisory_store.py` green; cumulative Critic.

### Lane MIG (owns tests/test_plugin_migrate.py)

#### Chunk 09: TST-4H8M — unit coverage for migrate _collapse_blank_runs edge cases (test-only)
**Type:** code
**Acceptance criteria:** add `TestCollapseBlankRuns` in `tests/test_plugin_migrate.py` exercising
`lib/migrate_plugin.py::_collapse_blank_runs` directly (NO runtime change): 3/4/5/7+ consecutive
newlines collapse to exactly 2; only-newlines input; empty string; and while-loop convergence
(`a\n\n\nb\n\n\nc` → `a\n\nb\n\nc`).
**Done when:** scoped `pytest tests/test_plugin_migrate.py` green; cumulative Critic.

## Governance Checkpoints

- **Per-chunk Critic:** satisfied ONCE, cumulatively, by the launching session after the workflow
  finishes (matches the roi-batch precedent — independent fixes, disjoint files, one cumulative pass).
- **Cumulative Critic** over `origin/develop...HEAD` gates `/prawduct:pr create`.
- **Full suite** (`python3 -m pytest`) run by the launching session on the integrated tree before
  the Critic — the workflow agents run only their own SCOPED test files.

## Release note (two release-pending plans)

This is the SECOND release-pending plan: `build-plan-roi-batch.md` (scope=roi-batch, chunks 01–05,
status=merged) is still pending its develop→main release. At that release, `regen-views` must run
once PER plan/scope (it resolves a single plan via the `active_build_plan` pointer): regen with the
pointer at roi-batch, then at roi-batch-2, before clearing the pointer. The `active_build_plan`
comment in `project-state.yaml` records both. (If this two-plan regen proves fiddly in practice,
it's a candidate backlog item against the release tooling.)
