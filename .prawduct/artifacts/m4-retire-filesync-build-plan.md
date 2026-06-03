# Build Plan — M4: Retire the file-sync engine & strip pre-2.0 back-compat cruft

Branch: `feat/retire-filesync-engine-m4` (off `develop`). Owner directive 2026-06-03:
*"we DO NOT need backwards compatibility … remove ANY cruft that exists only for back compat to
pre-2.0."* Decisions: **keep** the `/prawduct:migrate` bridge; **strip all** pre-2.0 guards.

Full rationale + verified safety facts: `~/.claude/plans/lucky-plotting-kahn.md` (approved plan).

`Critic mode:` chunk per chunk; `cumulative-final` on Chunk 5.

## Chunks

- **Chunk 1 — DOC-4B2W namespace sweep.** Namespace the 35 bare command invocations in the 6
  plugin-only prose files (`methodology/{building,planning,reflection}.md`,
  `skills/critic/{review-cycle,review-protocol}.md`, `skills/pr/review-protocol.md`) →
  `/prawduct:*`; leave `/clear`, paths, already-namespaced forms. Add `TestPluginDocsNamespacing`
  (assert-absent source-scan over the full skill vocabulary).
  *Done when:* diff reviewed, namespaced forms present + bare absent, full pytest green, `/prawduct:critic chunk` clean.

- **Chunk 2 — Retire the file-sync engine.** SPLIT after discovery: several *kept*
  governance-module unit tests reach their module-under-test THROUGH the engine
  (`prawduct-setup.py` importlib, or `sys.path.insert(tools)` + `from lib import X` → `tools/lib`,
  plus `tools/product-hook` subprocess sections). Those modules live in `lib/` too, so coverage
  must be repointed, not dropped. Verified: `bin/prawduct-hook` exposes the needed subcommands
  (regen-views, infer-critic-mode, audit-learnings, *-operator-verification, …) and
  `from lib import X` resolves to the plugin copy with repo-root on sys.path.
  - **2a — Repoint** the engine-coupled kept tests to the plugin (lib/ + bin/prawduct-hook) WHILE
    `tools/` still exists; verify full suite green (proves the plugin modules carry the coverage).
    Files: `test_advisory_cmd`, `test_advisory_store`, `test_audit_learnings`, `test_backlog_probes`
    (repoint now; removed in Chunk 3), `test_critic_mode_inference`, `test_operator_verification`,
    `test_views`, `test_build_plan_resolution`, `test_pr_reviewer`, `test_v5_templates` (the
    prawduct-setup loader part). Repoint, do NOT delete the subprocess coverage — point it at
    `bin/prawduct-hook`.
  - **2b — Delete the engine:** `tools/` (product-hook, prawduct-setup.py, 3 shims, lib/); the 10
    pure-engine test files (`test_prawduct_{sync,init,migrate,validate}`, `test_product_hook`,
    `test_product_compat`, `test_integration_lifecycle`, `test_coverage_gaps`,
    `test_preferences_lifecycle`, `test_lib_propagation`); relocate `tools/test-reference-verify`
    → `bin/` (+ repoint `test_reference_verifier.py` and doc refs); prune `TestPluginLibParity` +
    orphaned constants from `test_plugin_runtime.py`; fix `tests/preferences/` `tools/` scans
    (`test_sync_only_architecture`, `test_future_annotations`, `test_subprocess_safety`,
    `test_public_function_coverage` — drop/retarget the tools/lib coverage check); de-lock
    `lib/core.py` framing. `test_plugin_migrate.py` creates FAKE tools/ files in a temp repo — keep.
  *Done when:* full pytest green after 2a and after 2b, plugin smoke (clear+stop) passes, `/prawduct:critic chunk` clean.

- **Chunk 3 — Strip in-plugin pre-2.0 guards.** Remove `_legacy_filesync_present` coexistence
  nudge, `fallback-no-tools-lib` path, pre-v1.4 evidence acceptance; remove
  `legacy_backlog_format_probe` + its tests; remove `TestPluginCoexistenceNudge`.
  **Scope expansion (discovered 2026-06-03 during impl):** three further pre-2.0 coexistence
  stubs in the SAME "strip in-plugin guards" category, fed only by cmd_clear's inert
  `upgrade_info, sync_advisories, freshness = None, [], None` (line 1966) and passed to
  `assemble_session_briefing` solely to mirror the legacy file-sync briefing signature — the
  `upgrade_info` "Framework: upgraded" line, the `advisories` template-drift line, and the
  `freshness` commit-delta line. All three are unreachable in the plugin runtime and have **zero
  test coverage** (no test passes a non-None value), so they are dead code. Removed with their
  params. No later chunk claims runtime coexistence stubs (Chunk 5 is docs/residue), so deferring
  would orphan them. Also folded in (consequences of the named changes): the `legacy_backlog_format_probe`
  e2e coverage in `test_plugin_runtime.py::TestPluginClearBriefing` (the fires/no-fire pair +
  `_write_legacy_backlog` helper) and the `fallback-no-tools-lib` references in the critic skill
  prose (`SKILL.md` §1, `review-protocol.md` step 1). `infer-critic-mode` ImportError now mirrors
  the sibling `cmd_advisory` (clear incomplete-install message → exit 1; the skill's existing
  "inference failure → final" fail-safe absorbs it). Added a `validate-evidence` regression test
  asserting no-`verifier` evidence is now rejected (encodes the back-compat removal).
  *Done when:* full pytest green, briefing no longer nudges migrate, `/prawduct:critic chunk` clean.

- **Chunk 4 — Remove file-sync-only templates + reconcile registry/tests.** Delete the 7
  `skill-*.md` + the governance templates (`product-claude`, `critic-review`, `pr-review`,
  `build-governance`, `product-settings.json`, `conftest.py`); slim `lib/core.py` (keep MANAGED_FILES
  paths migrate needs, drop sync-only fields/constants); rework `TestNoBareSkillShadowing` +
  `test_v5_templates.py`.
  *Done when:* full pytest green, `init-product` dry-run scaffolds, `/prawduct:critic chunk` clean.

- **Chunk 5 — Clean this-repo residue + docs.** Remove committed `.prawduct/{critic-review,
  pr-review,build-governance}.md`; drop sync-manifest from the gitignore mirror + `.gitignore`;
  refresh `README.md` / `CLAUDE.md` / `docs/project-structure.md` / `docs/release-process.md`;
  M4 change-log entry; mark DOC-4B2W done; reconcile `MIG-M4-REMOVE`.
  *Done when:* full pytest green, no stale engine refs in kept docs/code, `/prawduct:critic cumulative` clean, ready for `/prawduct:pr`.

## Status
- [x] Chunk 1 — DOC-4B2W namespace sweep (49 invocations namespaced; TestPluginDocsNamespacing added; Critic chunk clean; 1817 green)
- [x] Chunk 2 — Retire the file-sync engine (deleted tools/ + 10 engine tests + parity machinery; repointed 11 governance-module tests to lib/+bin; relocated test-reference-verify→bin/; Critic chunk PASS; 714 green)
- [x] Chunk 3 — Strip in-plugin pre-2.0 guards (removed `_legacy_filesync_present` nudge, `fallback-no-tools-lib` path, pre-v1.4 evidence acceptance, `legacy_backlog_format_probe` module+registration+tests, `TestPluginCoexistenceNudge`; folded in the 3 inert sync-stub briefing params; Critic chunk PASS, 0 findings; 700 green)
- [ ] Chunk 4 — Remove file-sync-only templates
- [ ] Chunk 5 — Clean this-repo residue + docs

## Context
Chunks 1-3 committed on `feat/retire-filesync-engine-m4`. The file-sync engine is gone and the
in-plugin pre-2.0 guards are stripped; the plugin runs standalone (700 green, clear+stop smoke clean,
evidence validates against the tightened F4a-always schema). Test count 714→700 (removed 11 backlog-probe
+ 3 coexistence + 2 legacy-backlog e2e; added 2 evidence-schema regression tests). **Next: Chunk 4** —
remove file-sync-only templates + reconcile registry/tests: delete the 7 `skill-*.md` + governance
templates (`product-claude`, `critic-review`, `pr-review`, `build-governance`, `product-settings.json`,
`conftest.py`); slim `lib/core.py` (keep MANAGED_FILES paths migrate needs, drop sync-only
fields/constants — `template:` fields, SKILL_PLACEMENTS, FILE_RENAMES, merge_settings — that
lib/__init__.py re-exports); rework `TestNoBareSkillShadowing` + `test_v5_templates.py`. The `tools/lib`
references in lib/core.py:111/116 + migrate_plugin are migrate's consumer-removal targets (keep, but
reword core.py:111's sync-era rationale). Residual `fallback-no-tools-lib` strings linger only in
file-sync-era `templates/` + `.prawduct/critic-review.md` — Chunk 4/5 targets (Critic-confirmed
out-of-scope for Chunk 3).
