# Backlog — prawduct

<!-- Structured backlog (format v2). Managed via the /backlog skill.
     Each item: an ID line + a backticked metadata bar + optional free-form body.
     Sections: ## Open (pickable) · ## Promoted (in an active build plan) · ## Archive (shipped/dropped).
     Items move between sections only via explicit `/backlog update` calls. -->

## Open

- **[CRT-9V4T]** Verify (or harden) interactive enforcement of the Critic fork-skill's `allowed-tools` cap
  `effort: M · impact: M · area: critic · source: builder · added: 2026-06-01 · status: open · reviewed: 2026-06-01`

  Surfaced during v2.0.0 Chunk 4 empirical verification. The Critic's structural "no pytest / read-only git" guarantee rests on a `context: fork` skill with a pure-allow `allowed-tools` list (pytest unmatchable). `test_critic_skill_metadata.py` pins the *list shape* (no allow pattern matches pytest), and CLAUDE.md calls the constraint "structural, not behavioral." But a Chunk-4 probe found that under headless `claude -p`, a fork-skill with `allowed-tools: Read, Bash(git status *)` still ran a NON-allow-listed `echo` (marker printed) — i.e. headless `-p` did not enforce the allow-list as a hard cap. This does NOT prove a hole: the real Critic runs **interactively** (forked from a `/critic` invocation), where the cap is designed to apply, and the probe couldn't exercise that path. But it means the interactive enforcement is **assumed, not hermetically verified**, and the "structural" claim is only as strong as that assumption. Pre-existing — affects today's file-sync Critic identically; Chunk 4 introduced no regression (frontmatter byte-identical). Relates to memory `feedback_critic_no_test_execution` and learning CRT-2M5P. Fix-shapes: (a) an interactive-mode verification (manual or scripted) that confirms a forked `/critic` is actually denied a non-allow-listed Bash command — establishes whether the cap is structural or merely prompt-suppression; (b) if (a) shows it's not a hard cap, add a belt-and-suspenders **PreToolUse guard hook** in the plugin `hooks/hooks.json` that blocks pytest/`git checkout`/tree-mutation specifically when the calling agent is the critic (needs the hook to be able to scope to the subagent — itself unverified); (c) at minimum, soften the "structural, not behavioral" wording in CLAUDE.md to match what's actually verified. Open question: does Claude Code treat skill `allowed-tools` as a hard deny-cap in interactive mode, or as a no-prompt allow-list with a separate ask-fallback for unlisted tools? Resolve (a) before relying further on the claim. Filed from Chunk 4 verification on 2026-06-01. (builder)

- **[STH-7K2A]** Stop-hook structural loop-detection counter (defense-in-depth on top of v1.5.2's discoverability fix)
  `effort: M · impact: M · area: stop-hook · source: reflection · added: 2026-05-23 · status: open · closes: v1.5.2 discoverability half · reviewed: 2026-05-29`

  v1.5.2 (2026-05-23) shipped the discoverability piece: all four blocker stderr messages now name `.gates-waived`, the JSON shape, and `build-governance.md` so agents stuck in unsatisfiable gate states can declare a waiver. The structural piece is still open. Pathology: even with the escape hatch named in the blocker text, an agent can in principle ignore it and continue re-firing the same gate. Defense-in-depth fix-shape: track stop-hook fire count per session in a new `.prawduct/.stop-fire-count` file recording `{count, blocker_signature, ts}`. On the Nth (e.g., 3rd) consecutive fire with the same signature and no progress (no new Critic findings, no new waiver, no diff change since last fire), either (a) escalate the blocker text to name the loop explicitly and force-surface the waiver mechanism above the existing prose, or (b) auto-downgrade to advisory (stderr-only) on the assumption that the agent has seen the gate and made an informed call. (a) is conservative; (b) is firmer about not burning tokens. Auto-clear on session start. Open design questions: per-blocker counter or session-wide? what counts as "progress" (any diff change or only changes that materially address the gate)? should the counter persist if the blocker signature changes mid-session? Filed from v1.5.2 release (2026-05-23) as the deferred structural half of the original infinite-loop bug; the original "discoverability" half is shipped and the backlog entry closes against v1.5.2's change-log entry. (reflection)

- **[BLD-4Q9X]** `scope: null` in build-plan frontmatter does not suppress change-log inference
  `effort: M · impact: M · area: build-plan · source: critic · added: 2026-05-23 · status: open · reviewed: 2026-05-29`

  Surfaced by v1.5.1 Chunk 05 cumulative Critic. The template ships `scope: null` as the documented opt-out form, and `_parse_build_plan_frontmatter_scope` correctly returns `None` for null literals. But `_detect_active_scope` then treats "key present with null" identically to "key absent" — it falls through to change-log inference, picking up the most-recent `scope=` tag. Result: a product with a tagged release in change-log.md (e.g. `scope=v1.5`) plus a fresh `scope: null` build-plan with new chunks 01/02/03 will see `regen-views` flip those chunks to `[x]` because v1.5's tagged entries claim chunks 01/02/03. Author's explicit-null intent ("don't filter") is overridden silently. Fix-shape: distinguish "key absent" from "key present with null/empty" in `_parse_build_plan_frontmatter_scope` (return a sentinel or change to `tuple[bool, str | None]`); have `_detect_active_scope` skip inference when key was explicitly null. Doesn't bite the framework's own v1.5.1 plan (sets `scope: v1.5.1` explicitly). Filed from /critic cumulative WARNING on 2026-05-23 (v1.5.1 Chunk 05). (critic)

- **[CRT-1F7N]** Re-enable cumulative inference mid-build by recording per-HEAD cumulative records
  `effort: M · impact: S · area: critic · source: builder · added: 2026-05-22 · status: open · reviewed: 2026-05-29`

  Chunk 03's rule 2 (cumulative) added a clean-tree guard so it doesn't over-fire mid-chunk-N. Side effect: even after the user commits chunk N, rule 2 still doesn't fire because the helper has no record that cumulative was already run for THIS HEAD — but in practice cumulative IS expensive and the user typically only wants it pre-PR. The current behavior matches the proportionality intent, but loses some signal: if the user committed and is about to PR, inference doesn't surface "you should run cumulative" — it returns `chunk` (or `final` if last chunk). Fix-shape: when the working tree is clean AND ≥2 commits ahead, return `cumulative` even though it'd take 4-10 min — the cleanness is the signal the user has stopped editing and is about to merge. Risk: false-positives on chunk boundaries where the user clean-committed but isn't about to PR. Validate against a few real chunk boundaries before changing. Filed from Chunk 03 work on 2026-05-22. (builder)

- **[MIG-6B0R]** Recommend gitflow as the default git strategy + strip prawduct artifacts on deploy-to-main
  `effort: L · impact: M · area: migration · source: builder · added: 2026-05-19 · status: open · reviewed: 2026-05-29`

  Two coupled proposals:
  1. **Recommend gitflow** (`develop` for ongoing work, `main` as the deployed/released branch, feature/release/hotfix branches off `develop`) as the prawduct-recommended workflow. Captured in `project-preferences.md` (or a new `methodology/git-strategy.md`) with rationale: prawduct's session-artifacts churn pattern fits gitflow's "develop is mutable, main is immutable releases" split much better than trunk-based flow, where every session-edit lands on the deployable branch.
  2. **In gitflow repos, strip prawduct artifacts from `main` when promoting `develop` → `main`** (or when pushing directly to `main`). Filter scope:
     - **Strip:** `.prawduct/` contents — `backlog.md`, `build-plan.md`, `artifacts/`, `learnings.md`, `learnings-detail.md`, `change-log.md`, `.session-*`, `.critic-findings.json`, `.test-evidence.json`, etc. (governance bookkeeping, not deployment payload).
     - **Strip:** prawduct-owned hooks/skills — `tools/product-hook`, `.claude/skills/{critic,pr,janitor,learnings,prawduct-doctor}/SKILL.md`, framework-managed `.claude/settings.json` hook entries.
     - **Keep:** `docs/` and `documentation/` (real product documentation, not governance artifacts).
     - **Keep:** project-owned skills/hooks (anything in `.claude/skills/` that's NOT in the prawduct-managed set — user-authored skills stay).
  Fix-shape: probably a `prawduct-doctor deploy-to-main` (or `prawduct-deploy`) subcommand that performs a filtered merge/squash — strips the listed paths from a temp index, commits the cleaned tree to `main`, leaves `develop` intact. Alternative: a git pre-receive hook recipe in `methodology/git-strategy.md` that products copy into their own remote. Need to decide which paths are framework-canonical (centralizable in `core.py`'s MANAGED_FILES + a new `DEPLOY_STRIP_PATHS` set) vs. project-configurable. Open question: does the filter run on every push to main, or only on explicit `prawduct-doctor deploy` invocations? Filed from user request on 2026-05-19. (builder)

- **[SYN-3D8K]** Align `enable_v1_4_views` detector/mutator on inline-comment forms
  `effort: S · impact: S · area: sync · source: critic · added: 2026-05-19 · status: open · reviewed: 2026-05-29`

  Same pattern Chunk 10 fixed in `enable_v1_4_coverage`: `is_views_enabled`-style detection strips inline comments via `split('#', 1)`, but `enable_v1_4_views`'s flip uses exact `line.strip() == "views_enabled: false"`. A user line like `views_enabled: false  # opt-out` is detected as present-and-off but never flipped → silent no-op (manifest flag still set, file unchanged). Edge case (templates emit bare values), but the asymmetry will keep biting until both helpers use the same shape-aware match. Apply the Chunk-10 fix-shape: iterate lines, skip indented, compare comment-stripped value, re-attach inline comment on rewrite. Filed from /critic chunk NOTE on 2026-05-19 (Chunk 10) — the views variant was left alone in-chunk to keep diff scope tight. (critic)

- **[SYN-9C4T]** Extract shared `read_bool_yaml_key(state_path, key)` from `views.py::is_views_enabled` and product-hook's `_read_bool_yaml_key`
  `effort: S · impact: S · area: sync · source: critic · added: 2026-05-19 · status: open · reviewed: 2026-05-29`

  Both perform the same column-0 boolean scan against `project-state.yaml`, intentionally duplicated to keep product-hook flat (one inline 10-line helper vs. a new lib import). Two callers is the borderline; a third opt-in YAML flag (Chunk 11's F5 `auto_sync_commit`, or a future operator-verification toggle from F10) would push this to extraction. Move to `tools/lib/project_state.py::read_bool_yaml_key(path, key) -> bool` and call from both sites. Filed from /critic chunk NOTE on 2026-05-19 (Chunk 09). (critic)

- **[TST-5W1J]** Cache test-file contents in `tools/test-reference-verify` to drop O(N*T) re-reads
  `effort: S · impact: S · area: tests · source: critic · added: 2026-05-19 · status: open · reviewed: 2026-05-29`

  `_has_reference` re-opens every test file once per changed file. Sub-second on framework scale (~20 test files × small chunk diffs) but a stronger verifier or larger product would feel it. Fix-shape: discover_tests reads all test contents into a dict once, then `_has_reference` runs substring across the cached text. Filed from /critic chunk NOTE on 2026-05-19 (Chunk 08). (critic)

- **[BLD-0G6V]** Backfill Done-when blocks on Chunks 05-14 of v1.4 build plan
  `effort: S · impact: S · area: build-plan · source: critic · added: 2026-05-18 · status: open · reviewed: 2026-05-29`

  Chunks 00-04 each carry a Done-when block; Chunks 05-14 do not. Not a chunk-close blocker (chunk-mode Critic still fires on declared `**Critic mode:**`), but worth backfilling for consistency before Chunk 06 starts. Filed from /critic chunk NOTE on 2026-05-18 (Chunk 05). (critic)

- **[BLD-7A2E]** Capture pre-commit-regen scope-shift in Wave 2 retrospective / change-log
  `effort: S · impact: S · area: build-plan · source: critic · added: 2026-05-18 · status: open · reviewed: 2026-05-29`

  F1 plan line 234 promises "pre-commit regen of build-plan Status from work-log"; Chunk 05 shipped on-demand `regen-views` plus methodology docs that tell users to invoke manually (Chunk 06 plan note confirms this is deliberate as "ad-hoc regen between commits"). The deliverable line was flagged "high level — to be expanded before chunk starts" so this is not silent, but the Wave-2 release entry / retrospective should record the explicit decision: pre-commit hook (deferred to Chunk 07's migration tooling or Wave-3) vs. on-demand `regen-views` (shipped now). Filed from /critic chunk NOTE on 2026-05-18 (Chunk 05). (critic)

- **[BLD-3X9M]** Resolve `status=shipped` semantic — per-chunk merge vs. tagged release
  `effort: S · impact: M · area: build-plan · source: builder · added: 2026-05-18 · status: open · reviewed: 2026-05-29`

  Chunk 05 dogfooding raised an open question: does `status=shipped` on a change-log tag line mean "merged to mainline" (per-chunk timing — Status flips `[x]` when the chunk commits) or "in a tagged release" (wave timing — Status flips when a release entry covers it)? Current state: Chunk 05 left `[ ]` pending Wave 2 release entry. The Critic check (mismatch → WARNING) is symmetric, so either interpretation is internally consistent once chosen. Decide before Wave 2 release; document the chosen semantic in `templates/change-log.md` schema doc. Filed from Chunk 05 work, 2026-05-18. (builder)

- **[MET-4K8Z]** 8-surface cascade pattern — anticipate token-budget pressure in chunk plans
  `effort: S · impact: M · area: methodology · source: reflection · added: 2026-05-18 · status: open · reviewed: 2026-05-29`

  Chunk 05's source-of-truth guardrail threading touched 8 surfaces (product-claude / Critic SKILL / 2 critic-review / 2 pr-review / methodology / build-plan template). Same pattern Requirements Precede Code (v1.3.15) hit. When a chunk introduces a project-wide structural concept, the plan should enumerate the surface count up front so token-budget bumps (and the aggressive trim that precedes them) are anticipated, not discovered. Worth promoting to methodology after one more datapoint; until then, captured as observation. Filed from Chunk 05 reflection, 2026-05-18. (reflection)

- **[DOC-6P3Q]** v1.4 release-readiness: document the new `/pr create` gate before tagging
  `effort: S · impact: M · area: docs · source: critic · added: 2026-05-18 · status: open · reviewed: 2026-05-29`

  F2 ships hard enforcement: `check-cumulative-critic` blocks `/pr create` without a fresh cumulative-mode findings file. Product owners who sync v1.4 without reading the change-log will hit the gate cold and read it as a regression. Before tagging v1.4 (after all waves merge): add a change-log entry naming the new gate, a `prawduct-doctor` migration prompt if relevant, and a Compatibility-Strategy line in the release notes (the cumulative gate is new structural enforcement, not a behavior tweak). Filed from /critic cumulative NOTE on 2026-05-18. (critic)

- **[MET-1T5W]** Document the `new \`path\`` forward-ref convention in methodology prose
  `effort: S · impact: S · area: methodology · source: critic · added: 2026-05-18 · status: open · reviewed: 2026-05-29`

  `verify-chunk-refs` (F3) supports `new \`path/to/file\`` syntax to mark forward-references for not-yet-created files; this is implemented, tested, and documented inside `templates/build-plan.md`'s inline HTML comment, but not in `methodology/planning.md` prose. Authors who write plans without copying the template won't know the keyword exists and will get spurious BLOCKING ref-drift findings for chunks creating new files. Fix-shape: add a one-paragraph "Forward-references" note to planning.md near the build-plan-structure section. Filed from /critic cumulative NOTE on 2026-05-18. (critic)

- **[MET-8N2C]** Tighten F8 worked-example numbering language for consistency
  `effort: S · impact: S · area: methodology · source: critic · added: 2026-05-18 · status: open · reviewed: 2026-05-29`

  `methodology/planning.md:118` describes the `verify-api` step as "the first item in its Done-when", while the worked example a few lines down uses "step 0" (`0. verify-api: ...`). Both true, but the terminology is inconsistent. Fix-shape: change line 118 to "prepended as step 0 in its Done-when (so existing step numbering is preserved across chunks with and without a foreign API)". One-line tweak. Filed from /critic cumulative NOTE on 2026-05-18. (critic)

- **[TST-2R7H]** Add fixture coverage for `cumulative-final`/`cleanup` Type fall-through to default gate
  `effort: S · impact: M · area: tests · source: critic · added: 2026-05-18 · status: open · reviewed: 2026-05-29`

  Code analysis confirms only `designer-handoff` skips the Critic gate; the other Type values (`code`, `doc-only`, `cleanup`, `cumulative-final`) all fall through to the default gate path. But no dedicated test fixture pins this — `TestDesignerHandoffSkipsCriticGate` only covers the explicit skip branch. A refactor that accidentally broadens the skip list (e.g. `if chunk_type in {"designer-handoff", "doc-only"}`) would silently regress. Fix-shape: add a parametrized `TestNonHandoffTypesFallThroughToGate` covering the four fall-through Types. Filed from /critic cumulative NOTE on 2026-05-18. (critic)

- **[DOC-9J4B]** F8: add Foreign-API example to hallucinote product repo
  `effort: S · impact: S · area: docs · source: critic · added: 2026-05-18 · status: open · reviewed: 2026-05-29`

  v1.4 Chunk 04 (F8) acceptance criterion called for "at least one product-repo example added (hallucinote's Ableton Live MCP work is the obvious reference)." The Ableton-MCP example was shipped as a worked illustration inside the framework (planning.md "Foreign API Verification" section + templates/build-plan.md inline example), satisfying the spirit but not the literal product-repo touch. Defer the hallucinote-side update — `**Foreign API:** ableton-live-mcp` on the relevant build-plan chunk + `verify-api` step in Done-when — to the next hallucinote session. Filed from /critic NOTE on 2026-05-18. (critic)

- **[BLD-5V8F]** F3: extend `verify-chunk-refs` beyond file paths
  `effort: M · impact: M · area: build-plan · source: critic · added: 2026-05-18 · status: open · reviewed: 2026-05-29`

  v1.4 Chunk 02 (F3) shipped file-path verification only; the original plan also called for symbol (function/class names) and backlog-ID verification. Deferred during build because (a) symbols in prose are often approximate (`parse_func` vs implementation's `_parse_func`) so strict grep produces false positives requiring fuzzy match; (b) this project's backlog has no formal IDs (bullet titles, not e.g. `BL-123`), so the check would be inert here and need per-project ID convention. Add when a project surfaces a concrete need: define matching rules (substring grep across configured source roots for symbols; project-preferences `backlog_id_pattern` regex for backlog refs) and extend `_parse_build_plan_chunk_refs` to return `symbols` and `backlog_refs` lists alongside `file_paths`. Note: this project now HAS formal backlog IDs (`[PFX-XXXX]`) post-migration, so the backlog-ID half is newly actionable. Filed from /critic NOTE on 2026-05-18. (critic)

- **[SYN-7L0D]** Remove dead `if rel_path in ("CLAUDE.md",)` lines in sync_cmd.py `template`-strategy branch
  `effort: S · impact: S · area: sync · source: critic · added: 2026-05-08 · status: open · reviewed: 2026-05-29`

  Two pre-existing branches (`force=True` overwrite + `current_hash != stored_hash` skip) emit a "re-read CLAUDE.md" note guarded by `if rel_path in ("CLAUDE.md",)`. CLAUDE.md uses `block_template`, not `template`, so it can never reach these branches. Dead since the strategy split. Remove or document. Filed from /critic chunk on 2026-05-08 — flagged after the same dead pattern was caught in the new stale-clean branch (already removed there). Two-line cleanup; defer until next sync_cmd.py touch. (critic)

- **[SYN-3F6P]** Sync: skip-summary line counts + `--diff` preview flag
  `effort: M · impact: M · area: sync · source: reflection · added: 2026-05-08 · status: open · reviewed: 2026-05-29`

  When sync skips a file as "local edits," it gives no signal about the size or shape of the divergence — the user must `--force` blind or manually diff. Add to the skip note: `+N lines / -M lines vs current template`. Add a `--diff` flag that prints the unified diff(s) of would-be skips (or all would-be changes) without writing anything. For `block_template`, also note that content outside markers won't change. Lets users decide whether to force without a separate investigation. (reflection)

- **[BLD-6Q1N]** Extract `_iter_status_section_items` shared parser for build-plan Status
  `effort: S · impact: S · area: build-plan · source: critic · added: 2026-05-08 · status: open · reviewed: 2026-05-29`

  `_count_build_plan_chunks` (tools/product-hook lines ~2073-2113, added v1.3.13) duplicates the Status-section parsing skeleton of `_parse_build_plan_status` (lines ~1021-1099): same `## Status` detection, same HTML-comment skip, same exit on next `## ` heading. Two callers is borderline; if a third caller appears (e.g., a future stop-hook check that needs chunk metadata), extract to `_iter_status_section_items(prawduct_dir) -> Iterator[StatusItem]` and refactor both call sites. Filed from /critic NOTE on 2026-05-08. (critic)

- **[CRT-2H8K]** `.critic-findings.json` cumulative-state file
  `effort: M · impact: S · area: critic · source: builder · added: 2026-05-05 · status: open · reviewed: 2026-05-29`

  Would let `final` reviews focus on emergent cross-chunk concerns by remembering what each `chunk` review already covered. Useful but not necessary for proportionality MVP (v1.3.13). Revisit if `final` reviews still feel slow after live use. Filed during proportional-Critic build plan as out-of-scope. (builder)

- **[PRR-4M9T]** Trim PR-reviewer goals to remove Critic overlap
  `effort: S · impact: S · area: pr-reviewer · source: builder · added: 2026-05-05 · status: open · reviewed: 2026-05-29`

  PR reviewer Goals 1, 2, 4, 5, 6 in `agents/pr-reviewer/SKILL.md` overlap with Critic. Now that the layering is explicit (Critic-chunk = local; Critic-final = synthesis; PR reviewer = release readiness), PR reviewer goals could be trimmed to release-specific concerns (narrative, scope, merge hygiene, simplification). Filed during proportional-Critic build plan as out-of-scope. (builder)

- **[TST-1D5W]** Tighten `_validate_evidence_schema` against bool-as-int
  `effort: S · impact: S · area: tests · source: critic · added: 2026-05-05 · status: open · reviewed: 2026-05-29`

  Python's `bool` is a subclass of `int`, so `{"passed": True}` slips through `isinstance(v, int)` in the test-evidence validator. No real test runner emits booleans for these fields, so impact is theoretical, but the loophole is real. If addressed: add `or isinstance(v, bool)` exclusion to the type check (with a comment), and add a `TestValidateEvidenceSchema::test_bool_rejected_for_int_field` case. Filed from /critic NOTE on 2026-05-05. (critic)

- **[TST-8B3X]** Audit public-function coverage exemptions in `tests/preferences/test_public_function_coverage.py`
  `effort: M · impact: S · area: tests · source: builder · added: 2026-05-05 · status: open · reviewed: 2026-05-29`

  Four functions in `tools/lib/` are exercised transitively but never directly referenced as a function call (under the tightened detection that requires `Attribute.attr` or `Name` in `Call.func`): `core.py::log`, `core.py::load_json`, `migrate_cmd.py::strip_test_tracking`, `migrate_cmd.py::generate_sync_manifest`. For each, decide: (a) add a direct unit test class, or (b) rename to `_<name>` (private-by-convention) and remove from the exemption list. Rationale captured inline in `EXEMPT_FROM_DIRECT_COVERAGE`. (builder)

- **[SYN-5G2J]** Extract `_git_run` helper for fw-dir git lookups
  `effort: S · impact: S · area: sync · source: critic · added: 2026-05-01 · status: open · reviewed: 2026-05-29`

  `_get_framework_head_commit`, `_get_template_last_change` (sync_cmd.py), and the inline `git log -1` inside `_compute_framework_freshness` (product-hook) share the same try/except + subprocess.run + timeout=10 + broad-except + None-on-failure pattern. Three is the minimum-viable case for extraction. If a fourth fw-dir git lookup gets added, factor into `tools/lib/core.py` as `_git_run(fw_dir, args, timeout=10) -> str | None`. Currently small and well-commented; not urgent. (critic, 2026-05-01)

- **[MET-9K4R]** Workflow-values schema/validator
  `effort: S · impact: S · area: methodology · source: critic · added: 2026-05-01 · status: open · reviewed: 2026-05-29`

  Workflow preferences (`Branching: direct`, `PR creation: wait_for_user`, `PR merge: wait_for_user`) are read by `building.md` and `/pr` but have no allowed-vocabulary or shape check. A typo or unknown value would silently default. Candidate: small Critic checklist line ("Workflow values must be one of X / Y / Z") OR a tiny config-presence test. Low priority — current values are stable. (critic, 2026-05-01)

- **[MET-3P7B]** Lift "assign a mechanism per preference" pattern into methodology
  `effort: M · impact: M · area: methodology · source: critic · added: 2026-05-01 · status: open · reviewed: 2026-05-29`

  The Enforcement section added to `project-preferences.md` (and the template, 2026-05-01) encodes a methodology insight: every preference must be assigned to Linter / Test / Critic when it's captured, with a false-confidence guardrail that escalates weak tests to Critic. Currently lives only in the artifact + template. Candidate: weave into `methodology/discovery.md` (when capturing preferences) and `methodology/planning.md` (when designing test specs). Validate the pattern against 2-3 more preferences first before promoting. (critic)

- **[CRT-6T1V]** Critic check: test helpers duplicating production logic
  `effort: M · impact: M · area: critic · source: reflection · added: 2026-04-16 · status: open · reviewed: 2026-05-29`

  Cross-product reflection audit (Apr 16) surfaced a recurring drift hazard in discodon: test files re-implement production calculations (LogQL builders, SDK result parsing) rather than importing the shared helper, so tests keep passing while production drifts. Evidence: discodon/reflections.md §2026-04-14 "Pattern worth keeping". Candidate: extend Goal 1 or Goal 7 in critic/SKILL.md — when a test performs a calculation/parsing operation that exists in production, flag as WARNING unless the test is deliberately testing the helper itself. Needs design work on detection heuristic (string-matching is noisy; AST match is heavier). (reflection)

- **[CRT-4W8M]** Critic check: byte-exact assertions for "no behavior change" refactors
  `effort: S · impact: M · area: critic · source: reflection · added: 2026-04-16 · status: open · reviewed: 2026-05-29`

  When a refactor's explicit bar is "no behavior change," substring-level test assertions are insufficient. Discodon graph_ops refactor (Apr 16) had two silent text drifts (double-prefix, error message wrapper) that substring assertions missed and Critic caught only by reading the code. Evidence: discodon/reflections.md §2026-04-16 graph_ops. Candidate: add to critic-review.md template for Refactor work type — "If the chunk claims no behavior change, are output assertions exact-match (not substring/contains)? If not, flag WARNING." (reflection)

- **[CRT-1B6Q]** Critic check: stateful objects in shared_kwargs need lifecycle cleanup
  `effort: M · impact: M · area: critic · source: reflection · added: 2026-04-15 · status: open · reviewed: 2026-05-29`

  Discodon's multi-tool coordinator pattern passes stateful objects (PendingVoiceSlot, prior voice_getter closures) via `shared_kwargs` to multiple tools. Critic caught lifecycle bugs (missed_intro false-positives when idle) only after complex state interactions emerged. Evidence: discodon/reflections.md §2026-04-15 V0.5-5. Candidate: extend Goal 6 (The System Can Be Understood) — when an object with enter/exit/close methods is shared across tools, verify owner tool's stop() drains/closes it. Generalizes beyond discodon's specific pattern to any DI/coordinator framework. (reflection)

- **[MET-7H2D]** Testing guidance: multi-hop edge-case tests
  `effort: S · impact: M · area: methodology · source: reflection · added: 2026-04-08 · status: open · reviewed: 2026-05-29`

  When a data structure or state machine's correctness depends on what happens on the NEXT invocation (accumulator, coordinator, cursor, stateful retry), tests that only check post-state miss multi-hop bugs. Discodon has repeatedly shipped bugs caught only by the next cycle (Apr 8 accumulator, Apr 15 V0.5-7a timestamp collision under prune). Evidence: discodon/reflections.md §2026-04-08 "What I'd do differently". Candidate: add a bullet to methodology/building.md §Test Discipline — "When tested behavior depends on subsequent invocations (next cycle, next call, next prune), exercise at least one additional step beyond the immediate post-state." Broadly applicable; no detection heuristic needed. (reflection)

- **[CRT-5N3F]** Critic false positives from fork-context limits
  `effort: L · impact: M · area: critic · source: reflection · added: 2026-04-16 · status: open · reviewed: 2026-05-29`

  Discodon archive (Feb–Apr 2026) has 4 confirmed cases where Critic misread code: Mar 24 shutdown event closure, Mar 25 eval doc merge (3 of 4 prior findings false), Mar 28 ARIA A1/A2 missed an existing `model_config = ConfigDict(str_strip_whitespace=False)` override, plus branch-switching confusion. Root cause: `context: fork` can't see overrides spanning files / inheritance / closures. Investigate whether Critic's research phase needs a wider read budget for inheritance chains, or whether prompt engineering can compensate. (reflection)

- **[CRT-8D2W]** Critic-in-worktree as structural fix for session-file conflicts
  `effort: L · impact: M · area: critic · source: reflection · added: 2026-03-25 · status: open · reviewed: 2026-05-29`

  v1.3.3 gitignored build-plan.md and v1.3.4 added `_untrack_session_files()`, but the user explicitly suggested running Critic in a separate worktree to avoid touching session files in the active tree at all. Mar 25 discodon avatar_description session captured this when branch-switching during Critic review caused merge conflicts on `.session-handoff.md` and backlog. Worth designing as a follow-up to the gitignore approach. (reflection)

- **[SYN-6J0R]** WIP tracking goes stale when branches merge piecemeal
  `effort: M · impact: M · area: sync · source: reflection · added: 2026-03-23 · status: open · reviewed: 2026-05-29`

  Mar 23 discodon doc audit found 3 WIP branches were already merged into develop via other PRs but project-state.yaml still listed them in-progress. No mechanism reflects branch completion back to project-state.yaml when PRs merge. Consider git-based detection (branch existence on remote) or a post-merge sync step. (reflection)

- **[STH-9V4K]** product-hook decomposition
  `effort: L · impact: M · area: stop-hook · source: janitor · added: 2026-04-16 · status: open · reviewed: 2026-05-29`

  Split 2,240-line monolith (grew from 1,757 since original filing) into logical modules (_gates.py, _briefing.py, _yaml_parser.py). Currently working and well-tested, but 5 distinct concerns in one file hinders readability. (janitor)

- **[SYN-3T7B]** run_sync() decomposition
  `effort: M · impact: M · area: sync · source: janitor · added: 2026-04-16 · status: open · reviewed: 2026-05-29`

  Extract per-strategy logic (template, block_template, always_update, merge_settings) from 337-line function in sync_cmd.py. (janitor)

- **[TST-4P8H]** Flaky tests under parallel execution (xdist)
  `effort: M · impact: M · area: tests · source: builder · added: 2026-04-16 · status: open · reviewed: 2026-05-29`

  Several tests fail intermittently with `-n10` but pass sequentially: `TestClear::test_appends_multiple_reflections`, `TestClear::test_skips_empty_reflection`, `TestStopPrReviewGate::test_stop_clean_without_pr`, `TestNewProject::test_warning_disappears_after_filling`, `TestTrySyncFrameworkDiscovery::test_manifest_framework_source`, `TestMatchHistoricalRender::test_depth_cap_respected`. The depth_cap test creates 111 git subprocess commits in a loop — when 9 other xdist workers are simultaneously doing similar subprocess-heavy work, the system runs out of fork resources / hits IO contention and the test times out. Passes 100% of the time when run in isolation or with reduced parallelism. Root cause likely race conditions in the subprocess-based hook tests sharing process-level state or temp dir contention. (builder)

- **[TST-1M6V]** Pre-existing timeout flakes in test_product_hook.py
  `effort: M · impact: S · area: tests · source: builder · added: 2026-04-16 · status: open · reviewed: 2026-05-29`

  `TestStopCriticGate::test_no_build_plan_anywhere_skips_critic` and `TestCanaryDepNoRationale::test_no_manifest_file_no_flag` intermittently hit the 15s timeout. May need investigation into why the product-hook subprocess hangs in certain test configurations. (builder)

- **[STH-7B5N]** Session lock file for concurrent session detection
  `effort: M · impact: M · area: stop-hook · source: builder · added: 2026-04-16 · status: open · reviewed: 2026-05-29`

  Advisory lock file in product-hook clear/stop to warn when another Claude session is active on the same project. Agreed on non-blocking approach with staleness timeout (~4 hours). (builder)

- **[MET-2D9K]** `methodology/planning.md` parallel section for the `Visual change:` build-plan field
  `effort: S · impact: S · area: methodology · source: critic · added: 2026-05-18 · status: open · reviewed: 2026-05-29`

  F8 added a "Foreign API Verification" section to planning.md when introducing `**Foreign API:**`. F10 (Chunk 14) added `**Visual change:**` to the build-plan template with inline-comment guidance but no parallel planning.md section. The build-plan template's HTML comment is sufficient discoverability for v1.4.0; consider a v1.5 enhancement (~50 tokens) to align with the F8 precedent and pre-empt the asymmetry NOTE the Critic emitted. Filed from /critic Chunk 14 final review NOTE. (critic)

<!-- v1.7.0 deferred scope — the backlog feature shipped its lean core (the /backlog skill + the single
     legacy-backlog-format probe). The items below are real requirements scope (backlog-system-requirements.md,
     post-sync-advisory-spec.md §8.2) held back on proportionality grounds: low-risk internal markdown tool,
     no current consumer. Add each when a real product needs it. Filed from the v1.7.0 release chunk (2026-05-29). -->

- **[BKL-2F7K]** Ship the three remaining §8.2 backlog probes (`external-backlog-detected`, `legacy-section-schema`, `backlog-overdue-grooming`)
  `effort: L · impact: M · area: backlog · source: builder · added: 2026-05-29 · status: open`

  v1.7.0 shipped only `legacy-backlog-format` (the first production probe). The other three §8.2 probes are deferred — no product today has an external backlog file, an old-section-schema backlog, or a stale-grooming signal worth nagging. Build when one does. Each registers against the v1.6.0 advisory infrastructure via `register_probe("backlog", …)` in `tools/lib/backlog_probes.py` (the idempotent `register_backlog_probes()` already there) and resolves off a `project-state.yaml` fact: `external-backlog-detected` → `backlog_external_imports` (set by `/backlog import`); `legacy-section-schema` → reuse `backlog_format_version: 2` (migration folds the old `## Active`/`## Queue` headings); `backlog-overdue-grooming` → `backlog_last_groomed_at` + the 90-day window (spec §8.2). Tune the >5-item / >20-item / 90-day thresholds against a real product's backlog before shipping. (builder)

- **[BKL-5H9M]** `/backlog import <path>` — convert an external TODO/BACKLOG file into structured items
  `effort: M · impact: M · area: backlog · source: builder · added: 2026-05-29 · status: open`

  Requirements §4.3/§8.4. Resolves the `external-backlog-detected` probe ([BKL-2F7K]) by writing `backlog_external_imports` to `project-state.yaml`. Heuristically converts each bullet/list item in the named file into a `[PFX-XXXX]` entry (`source: user`, `status: open`, area inferred), always confirming before writing. Deferred with its probe — this repo has no external file to import. Build alongside [BKL-2F7K]'s `external-backlog-detected`. (builder)

- **[BKL-3R8P]** `/backlog dedup` — surface and merge near-duplicate items
  `effort: M · impact: M · area: backlog · source: builder · added: 2026-05-29 · status: open`

  Requirements §4.3. A subcommand that finds candidate duplicate items (title/area/keyword overlap) and proposes merges, preserving both bodies. Not on the path to the §1 user-facing test ("pick a high-value item in 30 min"), so deferred from lean core. The `add` subcommand already does inline dedup-on-create; this is the after-the-fact sweep. (builder)

- **[JNT-7T1W]** Janitor Step 2.5 — Backlog Triage (incl. Q2 archive-split)
  `effort: M · impact: M · area: janitor · source: builder · added: 2026-05-29 · status: open`

  Requirements §6. Add a backlog-triage step to the janitor: flag stale `status: open` items (`reviewed`/`added` >90d), surface neglected `## Promoted` items whose owning chunk shipped, and — the Q2 decision — when `## Archive` exceeds ~200 entries, propose splitting it to `backlog-archive.md` (with `/backlog find` spanning both files). Deferred from lean core; build when a product's backlog is large enough that grooming friction is real. (builder)

- **[CRT-3K9P]** The four backlog Critic checks C-B1–C-B4
  `effort: M · impact: S · area: critic · source: builder · added: 2026-05-29 · status: open`

  Requirements §7. Four soft NOTE-level Critic checks for backlog hygiene (e.g. C-B3: a chunk touches an area with open backlog items but its Done-when has no backlog-hygiene step). Decision D1 made them NOTE-level; deferred because adding governance friction to *every* product's Critic run before there's evidence of need is the least proportional piece of the feature (success criterion S6 watches for fatigue). Build when backlog-hygiene drift actually shows up in reviews. (builder)

- **[BKL-4N6X]** `/backlog dismiss-advisory` per-feature alias
  `effort: S · impact: S · area: backlog · source: builder · added: 2026-05-29 · status: open`

  Requirements §8.2. A convenience alias that forwards to the existing unified `/prawduct-advisory dismiss`. The unified command already works, so this is pure ergonomics — deferred until the alias's discoverability is worth the extra surface. (builder)

- **[BKL-6L3Q]** Build-plan hygiene-step guidance in `templates/build-plan.md` + `methodology/building.md`
  `effort: S · impact: M · area: backlog · source: builder · added: 2026-05-29 · status: open`

  Requirements §5.3, decision D9. Document the backlog-hygiene step (at chunk close, review open items in the chunk's area and update status explicitly — the framework never infers status from plans/change-logs, per D4) in the build-plan template's Done-when prose and in `methodology/building.md`. Cheap, but no probe or check depends on it in lean core, so filed rather than shipped. The v1.7.0 plan already dogfoods the step informally (chunk close-out includes "backlog hygiene"); this makes it a documented standard. (builder)

- **[BKL-1V8J]** prawduct-doctor setup-time external-backlog report
  `effort: S · impact: S · area: backlog · source: builder · added: 2026-05-29 · status: open`

  Requirements/advisory-spec §8.3. At setup/health-check time, `prawduct-doctor` reports any external backlog files (`TODO.md`, `BACKLOG.md`) found in repo root + `.github/`. Redundant with the `external-backlog-detected` probe ([BKL-2F7K]); deferred with it — build both together or decide one supersedes the other. (builder)

## Promoted

_None._

## Archive

- **[CRT-2M5P]** Critic skill `Bash(git *)` allowed-tools is too broad — permits state-mutating git verbs (checkout/stash/reset/branch)
  `effort: S · impact: M · area: critic · source: critic · added: 2026-05-23 · status: shipped · closed-by: reduce-governance-tax Chunk E · reviewed: 2026-05-29`

  Observed v1.5.1 Chunk 05 verify-resolutions: the Critic ran `git checkout d2b8af4` (mid-review!), corrupted the working tree to a detached HEAD state, and recovered via stash+pop. All my modified files survived but only because the Critic chose to restore them. The skill `allowed-tools` entry `Bash(git *)` permits every git subcommand including ones that mutate the working tree. Read-only verbs are sufficient for Critic's review purpose. Fix-shape: replace `Bash(git *)` with an explicit allow-list of read-only verbs — `Bash(git diff *)`, `Bash(git log *)`, `Bash(git status *)`, `Bash(git show *)`, `Bash(git ls-files *)`, `Bash(git rev-parse *)`, `Bash(git merge-base *)`, `Bash(git branch --show-current)`, `Bash(git for-each-ref *)`. Or, more concise, add a deny-list (subject to the same v1.5.1 Chunk 02 caveat that skill-frontmatter denies may not enforce). Filed from /critic verify-resolutions NOTE on 2026-05-23 (v1.5.1 Chunk 05). (critic)

  **Resolved (reduce-governance-tax Chunk E):** The Critic's `allowed-tools` now grants explicit read-only git verbs (diff/log/status/show/ls-files/rev-parse/merge-base/branch --show-current/for-each-ref) instead of the broad `Bash(git *)`, so a review can no longer run `git checkout`/`reset`/`stash` and corrupt the tree. Applied to `.claude/skills/critic/SKILL.md`, `templates/skill-critic.md`, and the `critic-test` shadow skill; pinned by `test_critic_skill_metadata.py::test_git_is_read_only`.

- **[CRT-8H3D]** v1.5.1 Chunk 02's `!Bash(pytest*)` deny patterns in skill `allowed-tools` do NOT structurally block pytest invocation
  `effort: M · impact: M · area: critic · source: critic · added: 2026-05-23 · status: shipped · closed-by: reduce-governance-tax Chunk E · reviewed: 2026-05-29`

  Confirmed by v1.5.1 Chunk 04 Critic WARNING: the Critic agent ran `python3 -m pytest` despite the four deny patterns in `.claude/skills/critic/SKILL.md` `allowed-tools`. The patterns appear to be documentation-only; Claude Code's skill `allowed-tools` field is allow-list semantics and the `!`-prefixed deny syntax is not honored there (or is overridden by project-level `settings.local.json` `permissions.allow: ["Bash(python3:*)"]`). Fix-shape options: (1) move deny patterns to `.claude/settings.json` `permissions.deny` (project-wide block — but would also block the *builder* from running pytest, which is wrong); (2) scope deny via a wrapper command or use a tool-namespace filter the harness actually enforces; (3) accept that the constraint is prose-and-allow-list only (the allow-list IS restrictive — `Bash(python3 tools/product-hook ...)` exact-strings shouldn't match pytest in pure-allow mode), and soften the v1.5.1 change-log / memory rule claim of "structurally enforced". Add a deliberate negative-path probe test before claiming structural enforcement. Filed from /critic chunk WARNING on 2026-05-23 (v1.5.1 Chunk 04). (critic)

  **Resolved (reduce-governance-tax Chunk E):** Structural enforcement is the PURE-ALLOW list (the `!Bash(...pytest*)` entries are documented as non-functional). Added the negative-path probe the item asked for: `test_critic_skill_metadata.py::test_no_allow_pattern_permits_pytest` asserts no allow pattern can match a pytest invocation. The skill comment already softens the 'structurally enforced' claim to name the allow-list as the real mechanism.

- **[SYN-2K9N]** Template drift advisory dismiss/acknowledge mechanism
  `effort: M · impact: M · area: sync · source: critic · added: 2026-04-16 · status: shipped · closed-by: reduce-governance-tax Chunk B · reviewed: 2026-05-30`

  **Resolved** by the template-drift fire-once fix (Chunk B of the governance-tax reduction): a drift advisory now surfaces exactly once per template change, then sync refreshes the stored template hash so it self-resolves — directly fixing the "nags every session" pathology. This is a cleaner fix than the proposed `dismissed_advisories` list / `/janitor dismiss` flow: place-once files are user-owned ("surface the change once, then it's yours"), so auto-resolving after one surfacing matches the semantics without new dismiss machinery. The user's place-once file is never overwritten. (critic)

- **[BLD-9R3K]** `infer-critic-mode` does not detect a build plan living in `.prawduct/artifacts/`
  `effort: M · impact: M · area: build-plan · source: critic · added: 2026-05-29 · status: shipped · closed-by: v1.6.0 Chunk 06 · reviewed: 2026-05-29`

  During v1.6.0 Chunk 02 the helper returned `rule-4 final: no active build plan ... fail-safe to thoroughness` even though `.prawduct/artifacts/v1.6.0-advisory-infrastructure-plan.md` is the active plan. **Resolved** by Chunk 06's `active_build_plan:` pointer (project-state.yaml) + the shared `core.resolve_build_plan_path` resolver, mirrored inline in product-hook and used by `infer-critic-mode`, `regen-views`, the stop-hook gates, `verify-chunk-refs`, and `check-pr-trivial`. The chosen shape is the explicit pointer (not the `*plan*.md` glob the original fix-shape proposed — a glob is ambiguous when multiple scope-named plans accumulate, which this repo demonstrates). Validated against both the framework repo (pointer → scope-named plan) and the back-compat default (no pointer → `build-plan.md`). Filed from /critic NOTE on 2026-05-29 (v1.6.0 Chunk 02); closed 2026-05-29 (v1.6.0 Chunk 06). (critic)
