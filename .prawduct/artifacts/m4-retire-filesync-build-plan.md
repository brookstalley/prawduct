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

- **Chunk 2 — Retire the file-sync engine (source + its tests, together).** Delete `tools/`
  (product-hook, prawduct-setup.py, 3 shims, lib/); relocate `tools/test-reference-verify` →
  `bin/`; delete the 10 engine test files; prune `TestPluginLibParity` + orphaned constants from
  `test_plugin_runtime.py`; fix `tests/preferences/` `tools/` scans; de-lock `lib/core.py` framing.
  *Done when:* full pytest green, plugin smoke (clear+stop) passes, `/prawduct:critic chunk` clean.

- **Chunk 3 — Strip in-plugin pre-2.0 guards.** Remove `_legacy_filesync_present` coexistence
  nudge, `fallback-no-tools-lib` path, pre-v1.4 evidence acceptance; remove
  `legacy_backlog_format_probe` + its tests; remove `TestPluginCoexistenceNudge`.
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
- [ ] Chunk 2 — Retire the file-sync engine
- [ ] Chunk 3 — Strip in-plugin pre-2.0 guards
- [ ] Chunk 4 — Remove file-sync-only templates
- [ ] Chunk 5 — Clean this-repo residue + docs

## Context
Chunk 1 committed on `feat/retire-filesync-engine-m4` (1817 passed). Next: **Chunk 2** — the big
engine deletion (`tools/` + 10 engine test files + prune TestPluginLibParity + relocate
test-reference-verify→bin/). Source and its tests must land in the same commit to keep the suite green.
