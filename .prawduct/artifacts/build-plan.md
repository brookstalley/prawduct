# Build Plan — Framework Refactoring (2026-03-29)

## Status
- [x] Chunk 0: Product repo compat test suite — done (38 tests, 815 total)
- [x] Chunk 1: Quick wins (dead code + template skill deletion) — done (813 tests)
- [x] Chunk 2: Mechanical extraction → tools/lib/ — done (813 tests)
- [x] Chunk 3: DRY improvements within lib/ — done (813 tests)
- [x] Chunk 4: Content deduplication — done (813 tests)
- [x] Chunk 5: Test consolidation — done (647 tests, 11 files)
- [x] Chunk 6: Cleanup, docs, deprecation, canary — done (655 tests)
Context: All 7 chunks complete. V4_GITIGNORE_ENTRIES fixed (3 missing entries), Critic changelog scope rewritten for current-changeset-only checking, v1/v3/partial deprecation warnings added, working-notes archived, docs updated, change_log_history entry added, canary tests pass. Gitignore hygiene: sync removes incorrectly-gitignored managed files and advises user to git-add; validate detects the mismatch.

**Size**: Large | **Type**: Debt paydown + Refactor | **Governance**: Critic per chunk, checkpoints after 0, 2, 3, 6

## Chunk 0: Product Repo Compatibility Test Suite

**What**: Build the safety net BEFORE any changes. Simulate 5 product repo states, verify sync/init/validate work correctly.

Fixtures: fresh_v5, v5_with_local_edits, v5_stale_manifest, v4_pending_migration, v5_old_hook.
Tests: sync completes, local edits preserved, manifest valid, validate passes, CLI JSON output stable.

**Acceptance**: ~30-40 new tests, all passing against pre-refactoring code.

## Chunk 1: Quick Wins

**What**: Delete 4 identical template skill files, remove dead code (is_v1_repo), update MANAGED_FILES to point at .claude/skills/ sources.

**Product impact**: MANAGED_FILES path change auto-repaired by manifest; same content = no product file changes.

## Chunk 2: Mechanical Extraction → tools/lib/

**What**: Move code verbatim into lib/__init__.py, lib/core.py, lib/init_cmd.py, lib/migrate_cmd.py, lib/sync_cmd.py, lib/validate_cmd.py. prawduct-setup.py becomes thin CLI with re-exports.

**Product impact**: None — products call via subprocess, CLI unchanged.

## Chunk 3: DRY Improvements

**What**: Unify merge_settings+replace_settings, write_template+write_template_overwrite, extract load_json helper, skill-placement loop. Compat aliases in re-exports.

**Product impact**: None — internal function signatures only.

## Chunk 4: Content Deduplication

**What**: Settle "tests alongside" wording, restructure build-governance.md as checklist, add role comments to Critic files, add agents/README.md, relocate speculative templates.

**Product impact**: build-governance.md and product-claude.md block update propagate via sync (desired).

## Chunk 5: Test Consolidation

**What**: Merge test_v5_hooks→test_product_hook, test_v5_migration→test_prawduct_migrate, collapse validation tests, remove redundant existence tests. Target: ~500 tests.

**Product impact**: None.

## Chunk 6: Cleanup + Docs + Canary

**What**: Deprecation warnings for v1/v3, update project-state/docs/README/CLAUDE.md, canary test against real products, archive stale working-notes. Plus two product-reported fixes:

1. **Critic changelog scope**: The Critic flags old changelog entries as regressions when they're just superseded history. The "historical records are immutable" instruction is too subtle — the Critic reads the changelog looking for coherence and treats outdated entries as findings. Fix: rewrite the coherence check for change-log.md to scope the Critic to *current session's entries only* — older entries are append-only history, not live documentation.

2. **Session handoff gitignore in V4_GITIGNORE_ENTRIES**: `.session-handoff.md` is in `GITIGNORE_ENTRIES` (new products) but missing from `V4_GITIGNORE_ENTRIES` (migration path). Products that migrated from v4 before sync picked up the new list get merge conflicts on handoff files. Fix: add `.prawduct/.session-handoff.md` to `V4_GITIGNORE_ENTRIES`.
