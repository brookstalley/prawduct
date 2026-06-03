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

  **Scope expansion (discovered 2026-06-03 during impl — same coupling pattern as Chunks 2/3).**
  Grepping the deleted templates' distinctive paths surfaced FIVE more affected test files the
  plan's two-file enumeration (`TestNoBareSkillShadowing` + `test_v5_templates.py`) missed:
  `test_pr_reviewer.py`, `test_critic_skill_metadata.py`, `tests/preferences/test_critic_skill_structure.py`,
  and prose/list refs in `test_plugin_init.py` (kept — its `FORBIDDEN` list asserts init NEVER
  creates the protocol docs; reads no template) and `test_plugin_runtime.py`.
  - **Reconciliation principle:** the deleted `templates/*` files were the file-sync *mirror*; the
    plugin's `skills/` + `methodology/` are the source of truth now. Where a template-content test
    is a redundant mirror of an EXISTING plugin-source test → **delete** (no contract lost). Where
    it is the SOLE guard of a surviving plugin file → **retarget** to that file. Delete only
    genuinely file-sync-specific assertions (block markers, synced-CLAUDE token budget,
    self-containment, Framework-Freshness briefing, sync-manifest, conftest place-once).
  - **Coverage proof (no orphaned contract):** `test_v5_methodology.py::TestCriticSkill` already
    guards `skills/critic/review-protocol.md` (goals/severity/signals/quality/PBT/framework-checks)
    — a near-exact duplicate of `test_v5_templates.py::TestCriticReviewGoalBased`; `TestBuildingMethodology`
    guards `methodology/building.md`; the 23 principles live in `docs/principles.md` + framework
    `CLAUDE.md`; the methodology digest (`test_plugin_methodology_digest.py`) carries the
    every-session guidance. So the `product-claude`/`critic-review`/`build-governance` content tests
    in `test_v5_templates.py` are redundant → delete.
  - **Per-file actions:**
    - `test_v5_templates.py`: DELETE the product-claude/critic-review/build-governance/conftest classes
      (`TestProductClaude*`, `TestCriticReviewGoalBased`, `TestBuildGovernancePBT`,
      `TestCrossTemplateConsistency`, `TestConftestPBT`, `TestProductClaudeFreshnessSection`,
      `TestJanitorSkillTemplateCurrency`). RETARGET `TestLearningsSkillTemplate` → `skills/learnings/SKILL.md`.
      KEEP the still-existing-template classes (`TestProjectStateV5Fields`, `TestBacklogTemplate`,
      `TestBoundaryPatternsTemplate`, `TestTestSpecificationsPBT`, `TestProjectPreferencesPBT`,
      `TestCriticSkillPBT`).
    - `test_pr_reviewer.py`: RETARGET `templates/pr-review.md`→`skills/pr/review-protocol.md`,
      `templates/skill-pr.md`→`skills/pr/SKILL.md`; drop the now-duplicate framework-vs-product /pr
      gate test + the vacated skill-vs-template cross-check; DELETE the two `product-claude.md`
      discoverability tests (synced-CLAUDE discoverability is file-sync). KEEP the stop-gate +
      methodology/framework-CLAUDE tests.
    - `test_critic_skill_metadata.py`: drop the `templates/skill-critic.md` surface; keep the plugin
      `skills/critic/SKILL.md` surface (simplify the surfaces list + the legacy/plugin tool branch;
      drop the now-single-surface parity test).
    - `tests/preferences/test_critic_skill_structure.py`: drop the `critic-review.md` / `skill-critic.md`
      / `build-governance.md` parametrize entries + `test_build_governance_references_mode`; keep the
      plugin skill + review-cycle + methodology entries; fix the stale `tools/product-hook` validator
      reference in the docstring.
    - `test_plugin_runtime.py::TestNoBareSkillShadowing`: drop `test_source_lives_in_templates`
      (asserted template existence — obsolete) ; keep the anti-shadow guard; update docstring.
    - `test_plugin_methodology_digest.py::TestCommitAttributionDefault`: fix the dangling docstring
      ref to the deleted `TestProductClaudeStructure.test_token_budget`.
  - **core.py slim is larger than the 4 named symbols:** Chunk 2 deleted `tools/` (the sync/init/
    validate commands), leaving the entire file-sync helper layer in `lib/core.py` dead (0 consumers,
    0 tests). Remove: `effective_managed_files`, `create_manifest`, `PLACE_ONCE_TEMPLATES`,
    `PLACE_ONCE_COPY`, `FILE_RENAMES`, `SKILL_PLACEMENTS`, `merge_settings`, `replace_settings`,
    `write_template_overwrite`, `copy_hook`, `compute_hash`, `compute_block_hash`, `detect_version`,
    `infer_product_name`, `untrack_gitignored_files`, `_resolve_framework_dir`, `_try_pull_framework`,
    `load_json`, `ensure_dir`, `V1/V3/V4_GITIGNORE_ENTRIES`, `V1_SESSION_FILES`; reshape `MANAGED_FILES`
    from `{path:{template,strategy,description}}` (the `template:` values point at deleted files) to a
    `frozenset` path registry (migrate/`update_gitignore` iterate keys only); reword the stale
    sync-era comments + module docstring; prune the `lib/__init__.py` re-export list to surviving
    symbols. KEEP (live governance consumers): `MANAGED_FILES`/`MANAGED_DIRS`, `GITIGNORE_ENTRIES`,
    `write_template`/`render_template`, `update_gitignore`, `extract_block`, `read_str_yaml_key`,
    `resolve_build_plan_path`, the block/version/dir constants, `log`.
  - **Deferred (flagged, not silently dropped):** `skills/janitor/SKILL.md`'s "Template Currency"
    theme still teaches the file-sync sync-manifest/place-once workflow (obsolete under plugin
    distribution). Out of scope for "remove templates"; `TestJanitorSkillTemplateCurrency` is deleted
    here (it mirrored the deleted template + pinned that stale content). Backlogged for a janitor-skill
    plugin-era rewrite + fresh coverage; candidate for Chunk 5 (docs/residue) if cheap.

- **Chunk 5 — Clean this-repo residue + docs.** Remove committed `.prawduct/{critic-review,
  pr-review,build-governance}.md`; drop sync-manifest from the gitignore mirror + `.gitignore`;
  refresh `README.md` / `CLAUDE.md` / `docs/project-structure.md` / `docs/release-process.md`;
  M4 change-log entry; mark DOC-4B2W done; reconcile `MIG-M4-REMOVE`.
  *Done when:* full pytest green, no stale engine refs in kept docs/code, `/prawduct:critic cumulative` clean, ready for `/prawduct:pr`.

## Status
- [x] Chunk 1 — DOC-4B2W namespace sweep (49 invocations namespaced; TestPluginDocsNamespacing added; Critic chunk clean; 1817 green)
- [x] Chunk 2 — Retire the file-sync engine (deleted tools/ + 10 engine tests + parity machinery; repointed 11 governance-module tests to lib/+bin; relocated test-reference-verify→bin/; Critic chunk PASS; 714 green)
- [x] Chunk 3 — Strip in-plugin pre-2.0 guards (removed `_legacy_filesync_present` nudge, `fallback-no-tools-lib` path, pre-v1.4 evidence acceptance, `legacy_backlog_format_probe` module+registration+tests, `TestPluginCoexistenceNudge`; folded in the 3 inert sync-stub briefing params; Critic chunk PASS, 0 findings; 700 green)
- [x] Chunk 4 — Remove file-sync-only templates (deleted 13 templates; slimmed lib/core.py to the surviving governance helpers + reshaped MANAGED_FILES→frozenset path registry; pruned __init__ re-exports; reconciled 7 test files — 5 more than the plan named — by retarget-to-plugin-source-of-truth or delete-redundant-mirror; Critic chunk PASS, 0 findings; 700→615 green; init-product dry-run + clear/digest/banner smoke clean)
- [ ] Chunk 5 — Clean this-repo residue + docs

## Context
Chunks 1-4 committed on `feat/retire-filesync-engine-m4`. The file-sync engine, its in-plugin pre-2.0
guards, AND its template + helper layer are gone; the plugin runs standalone (615 green, clear/digest/
banner smoke clean, init-product dry-run scaffolds, evidence validates). Test count 700→615 (removed
~85 redundant file-sync template-mirror + file-sync-specific tests; every deleted content contract is
either retargeted to its live plugin source-of-truth or already guarded by `test_v5_methodology.py` /
the methodology digest — verified by name, no orphaned contract). `lib/core.py` is now ~6 governance
helpers (the sync helper layer was dead after Chunk 2 deleted `tools/`); `MANAGED_FILES` is a frozenset
path registry migrate derives its REMOVE set from.

**Next: Chunk 5 — Clean this-repo residue + docs (Critic mode: `cumulative` then `final`).** Targets:
(1) the COMMITTED file-sync residue in THIS repo — `.prawduct/{critic-review,pr-review,build-governance}.md`
(if present), the sync-manifest gitignore-mirror entry + `.gitignore`; (2) stale engine refs in KEPT
CODE the Chunk-4 Critic + scans surfaced — `bin/prawduct-hook` prose comments referencing
`untrack_gitignored_files()` / the sync command (lines ~348-351, ~1794-1799) and the `tools/lib/core.py`
"inline mirror"/"Mirrors GITIGNORE_ENTRIES in tools/lib/core.py" / "Ensure tools/ is on sys.path"
comments (lines ~115, ~300, ~3632); (3) stale doc/active-file refs — `.prawduct/cross-cutting-concerns.md:28`
(`templates/pr-review.md`), `.prawduct/backlog.md:332` (`templates/skill-critic.md`), README / CLAUDE.md /
`docs/project-structure.md` / `docs/release-process.md`; (4) the `MIG-M4-REMOVE` cleanup rider — repoint
`lib/audit_learnings_cmd.py::run_audit_learnings` docstring off the legacy `prawduct-setup audit-learnings`
path (the byte-parity lock to `tools/lib/` dissolved when Chunk 2 deleted it); (5) M4 change-log entry;
mark DOC-4B2W done; reconcile `MIG-M4-REMOVE` → resolved. Backlog: `JAN-4F7M` (janitor skill Template
Currency rewrite) may fold in here if cheap. *Done when:* full pytest green, no stale engine refs in kept
docs/code, `/prawduct:critic cumulative` clean, ready for `/prawduct:pr`.
