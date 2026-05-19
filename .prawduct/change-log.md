# Change Log — Prawduct Framework

<!-- Append new entries at the top. Each entry is a ## section.
     Historical entries (pre-2026-03-22) are in project-state.yaml under change_log_history. -->

## 2026-05-19: Chunk 08 — F4a evidence-schema extension + reference floor verifier

<!-- prawduct: chunks=08 | status=shipped | scope=v1.4 -->

**Why:** Wave 3 opener. The framework's safety claim "tests passed" is currently falsifiable on untested new code — `.test-evidence.json` records pass/fail counts but never asserts that the tests actually *referenced* the code that changed. F4a closes the schema half of this gap: extend the evidence record with four coverage fields (additive, compat-preserving) and ship a reference verifier so products on Python have a working floor implementation. The Critic enforcement that *uses* this data lands in Chunk 09 (F4b); the migration tooling + fingerprint cleanup lands in Chunk 10 (F4c).

**What:** Two surfaces — schema validator + new tool.

1. **Schema extension in `tools/product-hook::_validate_evidence_schema`.** Presence of a `verifier` field is the discriminator. Legacy fingerprint-only evidence (no `verifier`) validates unchanged. When `verifier` IS present, the writer has opted into the coverage schema and `tests_executed` (list), `changes_referenced` (list), and `coverage_level` (enum: `referenced` | `executed`) become conditionally required. Out-of-set `coverage_level` values are rejected with the allowed-set listed. The error precedence (missing > wrong-type > enum) already established for the fingerprint half is preserved.

2. **`tools/test-reference-verify` — floor coverage verifier.** New ~300-line standalone CLI. Resolves a diff base (explicit `--base REV`, else auto-detects `origin/main` → `main` → `HEAD~1`), enumerates changed files (`git diff --name-only BASE` PLUS `git ls-files --others --exclude-standard` so untracked new files participate — the silent-failure mode this exists to catch), extracts Python `def`/`class` symbols via regex (including async-def and shebang-Python scripts without `.py` suffix), greps the test tree for any symbol per changed file, emits the four F4a fields as JSON. Three output modes: stdout (default), `--output PATH` (standalone JSON), `--merge-into PATH` (overlay onto existing fingerprint evidence). Documented in-script as a **floor**, not a default-good-enough — products with non-trivial coverage concerns SHOULD plug in stronger language-native tooling and emit `coverage_level: executed`.

**Template / docs:** `templates/build-governance.md` + `.prawduct/build-governance.md` gain a "Coverage Evidence (v1.4 F4a, opt-in)" section explaining the presence-of-`verifier` discriminator, the enum, the floor caveat, and the `coverage_required` flag (default off). `templates/project-state.yaml` gains a top-level `coverage_required: false` block with comment header; v1.4 default is off because Chunk 09 ships the Critic check that actually enforces it. Framework's own state file mirrors the default.

**Compat:** Strictly additive. Legacy evidence keeps validating with no changes. `coverage_required` default off means existing repos sync the template addition with zero behavior change; opting in is a one-line yaml edit. Schema validator rejects new-shape records that drop a field — a typo like `tests_ran` (vs. `tests_executed`) fails loud instead of silently dropping coverage signal.

**Test coverage:** 1113 passing (+26 over Chunk 07's 1087). New `TestCoverageEvidenceSchema` in `tests/test_product_hook.py` — 7 tests covering: legacy fingerprint-only compat; full coverage evidence accepted; both enum values valid; unknown `coverage_level` rejected with allowed-set listed; `verifier` without companion fields rejected (catches typos); list-type enforcement on `changes_referenced`; empty lists accepted (shape vs. content — content is the Critic's job per Chunk 09). New `tests/test_reference_verifier.py` — 20 tests across 6 classes built on real-git mini-repo fixtures (no mocking): output shape stability, diff-base resolution (explicit / auto / unresolvable), modified-file detection, untracked-file inclusion, untracked-with-test reference matching, unchanged-file exclusion, Python class symbol matching, async-def extraction, shebang-Python script extraction (catches the `tools/foo` CLI-verb pattern), non-Python stem fallback, `--output` writes standalone fields, `--merge-into` preserves fingerprint and overlays F4a, `--output`/`--merge-into` mutual exclusion, missing-file errors, `TestSelfCompat` cross-validates that the verifier's emitted shape satisfies the schema validator (drift catcher).

**Dogfooding:** Verifier run against this chunk's own diff via `python3 tools/test-reference-verify --base HEAD --merge-into .prawduct/.test-evidence.json` produces a `changes_referenced` list of 8 files (all changed files reference some test symbol). `test-status` reports `current`. `validate-evidence` reports `valid` against the merged record.

**Critic chunk review:** 0 BLOCKING, 0 WARNINGs, 3 NOTEs (all resolved in-chunk):

1. Build-plan structure table promised a `templates/project-state.yaml` edit in Chunk 08 — addressed by adding the `coverage_required: false` default now rather than deferring to Chunk 09.
2. `_has_reference` re-opens test files per changed file (O(N*T) I/O) — backlog item filed (`Cache test-file contents in tools/test-reference-verify`).
3. `_extract_symbols` returns empty set when a Python file has no `def`/`class` — docstring updated to flag the floor caveat for next reader.

## 2026-05-19: Chunk 07 — F1c sync auto-enables derived views for existing repos

<!-- prawduct: chunks=07 | status=shipped | scope=v1.4 -->

**Why:** Chunks 05–06 shipped the views pipeline behind `views_enabled: true` with `false` as the template default — products had to opt in via a planned `prawduct-doctor migrate v1.4 --enable-views` migration command. During Chunk 07 planning the user redirected: "all users should get views for free, with no mandatory opt-in. it will be fine." That collapses migration tooling into the sync path (which every existing repo already runs every session) and removes the need for the doctor migration subcommand entirely. The compat shim that matters — untagged legacy entries still render unchanged — already lives in the views.py tag-filtering logic from Chunk 05.

**What:** `tools/lib/migrate_cmd.py::enable_v1_4_views(product_dir, manifest)` — new one-shot helper (~85 lines). Wired into `run_sync()` immediately after `migrate_change_log` / `migrate_backlog`. Behavior:

1. Returns early when `manifest["v1_4_views_enabled"]` is already True (one-shot tracking — first sync flips the flag; subsequent syncs never touch the file, so a user who later sets `views_enabled: false` manually is respected).
2. On `project-state.yaml`, detects the two real-world shapes:
   * **Pre-Chunk-06 v1.3.x bootstrap** (neither key present): appends `scope_rollups: {}` block + `views_enabled: true` block, each with its own comment header matching the new template wording.
   * **Post-Chunk-06 default** (`views_enabled: false` + `scope_rollups: {}` already from template): flips `false` → `true` line-by-line, leaves `scope_rollups: {}` alone.
3. Sets `manifest["v1_4_views_enabled"] = True` regardless of whether the file needed changes — the flag means "this sync has visited the v1.4 migration step," not "we mutated the file." Existing `run_sync` manifest write-back persists it.

**Template changes:** `templates/project-state.yaml` now defaults `views_enabled: true` (was `false`) with updated comment ("enabled by default" → "set to `false` to opt out"). `templates/change-log.md` schema header refreshed to "enabled by default" wording. Framework's own `.prawduct/project-state.yaml` derived-views comment refreshed to match (the value was already `true` for dogfooding).

**Plan revision:** Chunk 07's description in `.prawduct/artifacts/build-plan.md` rewritten — Status line + Context closer + body block. The dropped `prawduct-doctor migrate v1.4 --enable-views` subcommand is captured here, not as deferred work. The maintenance plan F1 compat paragraph + R2 removal-trigger criterion now reflect "auto-enabled, opt-out is explicit." `tools/product-hook cmd_regen_views` docstring updated (Critic NOTE: "opt-in by design" wording was stale).

**Test coverage:** 1087 passing (+10 over Chunk 06 baseline). `TestEnableV1_4Views` in `tests/test_prawduct_sync.py` — 10 tests covering: no project-state no-op; manifest flag short-circuits without reading file; pre-Chunk-06 legacy adds both keys; post-Chunk-06 default flips false→true and preserves scope_rollups; already-on no-edit (flag still records); idempotent second run respects user opt-out; only-scope-missing path; commented-out keys not counted; nested keys not counted (lightweight substring detector intentionally scoped to top level); end-to-end `run_sync` integration confirms manifest flag persists across sessions. `test_every_public_lib_function_referenced_in_some_test` confirms the new function has direct test references.

**Dry-run evidence (discodon + hallucinote):** both repos are v1.3.x bootstraps without either key. Function appends both blocks (~1019 bytes added), sets manifest flag, second pass is byte-identical no-op, and a manual opt-out (setting `false` post-flag) is respected on subsequent passes. Run captured via inline harness against tmp copies — no commits to those repos.

**No regen-views invocation in this chunk** — the F1c work is sync logic only. Each affected repo will see views materialize on the next regen (manual `python3 tools/product-hook regen-views` or chunk-close governance per `methodology/building.md`).

## 2026-05-18: Chunk 06 — F1b remaining views (release-notes + scope-rollups + doctor views)

<!-- prawduct: chunks=06 | status=shipped | scope=v1.4 -->

**Why:** F1a (Chunk 05) shipped the schema, the parser, and one view (build-plan Status). F1's load-bearing premise — *one canonical store, multiple derived views replacing hand-curated summaries* — needs the remaining two views (release notes, scope rollups) before Chunk 07 can ship migration tooling. The doctor `views` subcommand fills the F1 deliverable for ad-hoc inter-commit regen and gives `/prawduct-doctor` users a one-stop dry-run/refresh surface.

**What:** Three views regenerate in one pass via `python3 tools/product-hook regen-views` (or `python3 tools/prawduct-setup.py views <dir> --refresh`):

1. **Status** (existing, from Chunk 05) — build-plan `## Status` checkboxes from `status=shipped` tags.
2. **Release notes** (new) — `.prawduct/release-notes.md` digest, one section per `release=` tag, preserving change-log order (newest first). Multiple change-log entries sharing a release tag merge into one section.
3. **Scope rollups** (new) — `scope_rollups:` top-level block in `project-state.yaml`, listing chunks + releases per `scope=` tag. Alphabetically sorted scopes, deduplicated chunks. Chunk IDs YAML-quoted to preserve leading zeros. Block appended at end-of-file with comment header on first regen; subsequent regens replace the key-and-body in place (preserves surrounding content via `extract_yaml_top_level_block`).

**Shared regen pipeline:** new `views.plan_regen(prawduct_dir) → (enabled, [ViewRegenResult])` + `views.apply_regen(prawduct_dir, results)` helpers consolidate the read/build/write logic so both `product-hook regen-views` and the new doctor `views` subcommand reach the same path. `ViewRegenResult` carries `name` (`status`/`release-notes`/`scope-rollups`), `action` (`noop`/`write`/`create`), `summary`, and the new content — letting the doctor surface dry-run intent without writing.

**Doctor `views` subcommand:** `python3 tools/prawduct-setup.py views <product_dir>` reports per-view freshness (Status / release-notes / scope-rollups) and prompts for `--refresh` when changes would apply. `--refresh` performs the regen. `--json` for scripted consumption. New `tools/lib/views_cmd.py` (~60 lines) wraps `plan_regen` + `apply_regen` with the doctor's payload shape. The /prawduct-doctor skill picks this up via prawduct-setup.py's subparser table.

**Source-of-truth guardrails (broadened from Status to all three views):** Critic Goal 4 ("Derived views" bullet) + templates/critic-review.md + .prawduct/critic-review.md + PR-reviewer SKILL + templates/pr-review.md + .prawduct/pr-review.md + methodology/building.md chunk-close pointer + templates/product-claude.md step 10 all updated. Common message: when `views_enabled: true`, all three views derive from change-log tags via `regen-views`; tag is canonical; any view↔tag mismatch → WARNING ("run regen-views"). Aggressive trim-before-bump kept Critic SKILL.md under the existing 3250 ceiling (broader wording would have grown to 3261; trimmed back to 3243) and templates/product-claude.md block under 3050 (broader wording would have grown to 3061; trimmed back to ≤3050).

**Schema / template changes:** `templates/change-log.md` schema comment expanded to mention the release-notes + scope_rollups outputs (previously only mentioned Status). `templates/project-state.yaml` opt-in comment broadened; `scope_rollups: {}` placeholder added (default empty, populated only on first regen with shipped+scoped entries).

**Test coverage:** 1077 passing (+36 over Chunk 05's 1041). New tests/test_views.py classes: TestExtractYamlTopLevelBlock (6 — find/missing/multi-line/comment-terminated/indented-not-matched/end-of-file), TestBuildScopeView (7 — append/replace/idempotent/empty/multi-sort/non-shipped-excluded/dedup-sort), TestBuildReleaseNotesView (6 — none/in-progress-excluded/single/multi-order/merge/no-release-tag-excluded), TestPlanRegen (4), TestApplyRegen (2), TestRunViewsCommand (3 direct), TestRegenViewsAllThree (2 integration), TestDoctorViewsSubcommand (5 subprocess + 1 JSON-shape). Public-function coverage test (`test_every_public_lib_function_referenced_in_some_test`) confirms `plan_regen`/`apply_regen`/`run_views_command` have direct test references, not just transitive.

**Dogfooded:** regen-views against the framework's own change-log produced `.prawduct/release-notes.md` with v1.3.17 + v1.3.16 sections and appended `scope_rollups:` to `.prawduct/project-state.yaml` with `v1.4` listing chunks 00-05 + release v1.3.17. Idempotent second run reports `Status: up to date / Release notes: up to date / Scope rollups: up to date`.

**Methodology decision recorded in change-log entry as well as in the maintenance plan:** pre-commit regen for views is *deferred* to Chunk 07 (per the F1 plan line that originally promised it). v1.4 ships **on-demand regen only** — via `product-hook regen-views` (run manually or by chunk-close governance per methodology/building.md) and `prawduct-setup.py views <dir> --refresh` (manual). The backlog note filed during Chunk 05's Critic capturing this scope-shift is now consolidated here.

## 2026-05-18: Chunk 05 — F1a derived views (work-log schema + Status view)

<!-- prawduct: chunks=05 | status=shipped | scope=v1.4 -->

**Why:** F1's load-bearing premise (one canonical store, derived views replacing hand-curated summaries) needs a working derived-view pipeline before the remaining views (release notes, scope) can land in Chunk 06 and migration tooling in Chunk 07. Chunk 05 ships the schema, the parser, the first view (build-plan Status), and the source-of-truth guardrails threaded across Critic + PR-reviewer + methodology surfaces.

**What:** New `tools/lib/views.py` (HTML-comment tag-line parser + Status-section view builder + `views_enabled` reader, stdlib-only ~216 lines). New `product-hook regen-views` subcommand reads change-log + build-plan, rewrites Status checkboxes from `status=shipped` tags. Tagged-entry schema documented in `templates/change-log.md`. Status marker added to `templates/build-plan.md`. `views_enabled` opt-in field added to `templates/project-state.yaml` (default false) and `.prawduct/project-state.yaml` (true — dogfooding). v1.3.17 and v1.3.16 entries backfilled with tag lines so the first regen against current Status is a no-op. Source-of-truth guardrails added at 8 surfaces — when `views_enabled` is true, the change-log tag is canonical and Status is derived; Critic/PR reviewer flag mismatches as WARNING. Test suite: 39 new tests in `tests/test_views.py`, 1041 total.

**Status semantic decided (2026-05-18):** `status=shipped` means "merged to mainline" — per-chunk timing. A chunk's checkbox flips `[x]` the moment its merge commit lands, independent of whether a tagged release has consolidated it yet. Release inclusion is tracked separately via the `release=vN.M.P` tag on a per-chunk or per-wave entry.

## 2026-05-18: v1.4 Wave 1 — proportional Critic + cumulative gate + foreign-API verification (v1.3.17)

<!-- prawduct: chunks=00,01,02,03,04 | release=v1.3.17 | status=shipped | scope=v1.4 -->

**Why:** Five recurring quality-governance gaps surfaced across recent product work: (F2) per-chunk Critics passed clean but cross-chunk integration cracks (helper introduced in chunk N misbehaving against prose in chunk M) only emerged at merge time, with no structural gate to catch them; (F3) build plans drift from real file paths as a chunk's scope evolves, and the Critic had no mechanical way to detect references to files that no longer exist; (F6) the Critic ran the full 7-goal protocol against every chunk regardless of work type — wasteful for docs/cleanup chunks, occasionally missing the right goals for designer-handoff chunks; (F8) chunks wrapping foreign APIs (vendor SDKs, MCP servers) routinely shipped against assumed signatures that didn't match the real surface, found at integration time. Each gap had been surfaced as a learning or backlog item over the prior quarter; v1.4's first wave addresses them in one bundle.

**What:** Five chunks delivering four new mechanisms, plus three remediation rounds dogfooded against the cumulative-Critic gate they introduce.

1. **Chunk 00 — SKILL.md trim-pass.** `agents/critic/SKILL.md` reduced 3500→3196 tokens (4-token slack against the 3200 ceiling), reclaiming headroom for the new goals added by F6/F8. No behavioral change.

2. **Chunk 01 — F2: cumulative-Critic gate (`mode: cumulative`).** New Critic mode whose scope is `git merge-base main...HEAD` rather than the chunk's own diff. Invoked via `/critic cumulative`. Records findings with mode `cumulative (bundle review, ready for merge)` to `.prawduct/.critic-findings.json`. New `tools/product-hook check-cumulative-critic` subcommand provides the structural gate that `/pr` calls before opening a PR — requires the findings file to exist, be schema-valid, be from the current session, be in cumulative mode, and have no unresolved BLOCKING findings. Pr skill (`pr/SKILL.md` Step 2) invokes this gate.

3. **Chunk 02 — F3: build-plan ref drift verification.** New `tools/product-hook verify-chunk-refs [chunk_id]` subcommand parses backticked file-path references from a chunk's `### Chunk NN:` section and verifies each path exists on disk. Critic Goal 2 invokes it; non-zero exit → BLOCKING per missing path. Supports `new \`path\`` forward-ref syntax for chunks creating new files. Scope this wave is file paths only; symbol and backlog-ID extraction backlogged.

4. **Chunk 03 — F6: chunk-Type axis for proportional Critic.** Build plans gain a `**Type:**` field (`code` | `doc-only` | `cleanup` | `designer-handoff` | `cumulative-final`, default `code`). Critic goal selection modulates by Type — `doc-only` skips test-coverage goals, `designer-handoff` skips the gate entirely (artifact-only chunks have no code to review), `cumulative-final` triggers the cumulative pass. Unknown Type falls closed to `code` (the fully-armed protocol) — escape-hatches-fail-closed default per existing learning.

5. **Chunk 04 — F8: Foreign API verification as methodology default.** Build plans gain an optional `**Foreign API:** <name>` field declared on chunks wrapping vendor APIs/SDKs whose surface the project doesn't own. Critic Goal 2 requires such chunks to include a `verify-api` step prepended as Done-when step 0 — meaning: read foreign source, run discovery probes against a live instance, or document the docs source consulted and flag Requirements Confidence: Medium. Captures the hallucinote Ableton-MCP rework pattern as a framework default.

**Remediation rounds (cumulative-Critic dogfooding itself):**

- **Round 1 (W2/W3):** Cumulative pass against the 5-chunk bundle caught two regressions chunk-Critics missed. W2: `_looks_like_file_path` (F3) emitted BLOCKING false-positive ref-drift findings on slash-command tokens (`/pr`, `/learnings`, `/critic`) — tightened the heuristic to exclude single-segment `/<cmd>` tokens with no further `/` and no `.`. W3: `Foreign API` field name diverged between methodology (`foreign_api:` snake_case in prose) and build-plan template (`**Foreign API:**` title-case) — aligned 8 surfaces on title-case (matching the existing build-plan field convention: `**Type:**`, `**Critic mode:**`, `**Requirements Confidence:**`). Two new learnings captured: cumulative-Critic finds first-use regressions chunk-Critic can't; build-plan fields use Title Case (snake_case is the YAML-key namespace in `project-state.yaml`, a different surface).

- **Round 2 (W4/W5):** Cumulative-Critic round-2 caught a fail-open contract in the gate that round-1 introduced (W4: missing `.session-start` silently bypassed freshness check, function returned 0 on any non-blocking findings — inverted to fail closed with actionable message + new test pinning the contract) and a missing-row deficit in `.prawduct/cross-cutting-concerns.md` (W5: added four rows for the new pipeline-spanning mechanisms: Foreign API verification, Cumulative-Critic gate, Build-plan ref drift, Chunk Type / proportional review).

- **Round 3:** Cumulative-Critic round-3 caught a one-cell typo in the W5 registry row (`cumulative-bump` should be `cumulative-final` — same namespace-divergence class as W3, recapitulated one row over). Fixed.

- **Round 4:** Cumulative-Critic round-4 returned 0 blocking + 0 warnings + 6 advisory notes ("Ready to merge"). Five notes filed to backlog (release-readiness gate documentation, chunk-Type error surfacing, forward-ref convention prose, F8 numbering language, fall-through fixture coverage). The dogfooding chain validated F2's premise four cycles deep.

**Test coverage:** 1002 passing (+3 over pre-wave baseline of 999). New test classes: `TestDesignerHandoffSkipsCriticGate`, `TestCheckCumulativeCriticSubcommand` (8 tests, including the W4 fail-closed regression pin), `TestParseBuildPlanChunkRefs`, `TestVerifyChunkRefsSubcommand`, `TestParseBuildPlanChunkType`. Test evidence fresh in-session.

**Compatibility — read before syncing:** The `check-cumulative-critic` gate is new structural enforcement. After syncing v1.3.17, the next `/pr create` in any product repo will require a fresh `cumulative`-mode Critic record (produced by `/critic cumulative`) covering `merge-base...HEAD` — the gate refuses to open the PR without one. This is a real behavior change at the PR boundary: workflows that previously ran chunk-Critics and went straight to `/pr` now have an additional cumulative pass before PR creation. Day-to-day chunk work is unchanged; only the PR-creation step gains the gate. The backlog item "v1.4 release-readiness: document the new `/pr create` gate before tagging" tracks adding a `prawduct-doctor` migration prompt and full release-notes section before the v1.4 minor bump consolidates this and subsequent waves.

## 2026-05-10: Janitor skill becomes model-invocable (v1.3.16)

<!-- prawduct: release=v1.3.16 | status=shipped -->

**Why:** The janitor skill shipped with `disable-model-invocation: true` in its frontmatter, which prevented the agent from launching it via the Skill tool. It still appeared in the user's slash-command list (because `user-invocable: true`), so users saw it but the agent couldn't run it — confusing asymmetry. The intent was always for the agent to be able to drive periodic maintenance, not just respond when the user types `/janitor`.

**What:** Removed the `disable-model-invocation: true` line from `.claude/skills/janitor/SKILL.md` frontmatter. `user-invocable: true` and the `allowed-tools` allowlist remain unchanged. After sync, product repos pick up the same change (the framework's janitor SKILL.md is the source for product instances per `tools/lib/core.py`).

**Also:** Bundles dogfood re-syncs of `.prawduct/build-governance.md` and `.prawduct/critic-review.md` that the session start hook applied automatically when upgrading to v1.3.15 templates (the framework repo is its own product instance, so its `.prawduct/` files lag template changes by one session-start cycle).

## 2026-05-09: Requirements Precede Code — visible/assessed requirements clarity (v1.3.15)

**Why:** Recurring quality issues across products using Prawduct trace to a common root: both user and agent get excited and start design/code before requirements are clear. The previous framework had no friction at the right boundary — Critic and PR review fire *after* code exists, by which point design is committed. Discovery was treated as a one-time phase, with each new feature implicitly skipping its own micro-discovery. The agent had no trigger to pause when the user said "build X." The cure couldn't be heavy gates (too straitjacketing) or pure principle (history shows judgment alone won't interrupt momentum) — it needed light, distributed friction that surfaces requirements clarity at multiple places without blocking.

**What:** Six interlocking changes, all in service of the same idea: make requirements clarity a visible, assessed property at every appropriate boundary.

1. **New Quality principle: Requirements Precede Code (#6).** "Code built on unclear requirements is debt the moment it's written." Sits beside Honest Confidence (#5): one is about what you know; this is about whether you understand the problem. Old principles 6-22 renumbered to 7-23; active by-number references swept across `methodology/`, `templates/`, learnings, registry, and test scenarios in both "Principle N" and "(#N)" forms. Historical files (changelog, reflections, change_log_history) left frozen per the framework's existing rule.

2. **Requirements Confidence field on build plans.** `templates/build-plan.md` now has a required section between YAML frontmatter and Status: Level (High | Medium | Low), Why (one sentence), Open assumptions / unknowns, What would raise confidence. The field is honest self-assessment, not a gate. `methodology/planning.md` documents the semantics under Build Planning.

3. **Pre-build readiness check.** `methodology/building.md` gains a "Before You Build: Confidence Check" section before The Build Cycle — three questions in one sentence each (problem, success, out-of-scope), three response options when unclear (close the gap, sketch and confirm, proceed knowingly).

4. **Recursive discovery framing.** `methodology/discovery.md` promotes "Discovery Recurs" from a buried trailing paragraph to a top-of-file section. Distinguishes initial discovery (project foundation) from feature-level discovery (the same three questions at smaller scale, captured in the Confidence field).

5. **Agent-side trigger in CLAUDE.md.** Both framework `CLAUDE.md` and `templates/product-claude.md` now have "Before Building: Requirements Clarity" sections that fire when the user says "build X" / "implement Y" / "let's add Z." Three questions, cheap close, don't interrogate (pairs with Principle 20 — Infer, Confirm, Proceed).

6. **Critic Goal 2 checks.** `agents/critic/SKILL.md` and `templates/critic-review.md` Goal 2 (Nothing Is Missing) gain two new checks: (a) acceptance criteria as observable behavior, not implementation ("function X exists" is implementation; "user can submit form and see confirmation" is behavior) → WARNING; (b) Requirements Confidence field present, with open assumptions listed if Medium/Low → WARNING. Catches overstated confidence after the fact, creating downstream pressure on the upstream framing.

**Bootstrap demonstration:** the build plan for this work itself used the new Requirements Confidence field before Chunk 02 codified it (declared "High" with an Open Assumption about exact prose for new Critic bullets). That uncertainty held: the prose got refined under token-budget pressure during Chunk 04. Useful proof that the field surfaces unresolved bits without blocking progress.

**Behavioral notes:**
- The check sits before methodology, not as a gate. No stop-hook or other enforcement blocks low-confidence plans. The forcing function is honest self-assessment plus downstream Critic visibility.
- "Don't interrogate" disclaimer in both CLAUDE.md sections explicitly pairs the check with Principle 20 (Infer, Confirm, Proceed). One inference to confirm > five questions.
- Discovery's existing closing paragraph (which mentioned recurrence) was reduced to a pointer at "Discovery Recurs" earlier in the file, avoiding duplication.
- Two token-budget bumps: `methodology/building.md` 4100 → 4250 (Before-You-Build section, ~100 tokens after aggressive trim); `templates/product-claude.md` block 2900 → 3050 (Before-Building section, ~110 tokens). Both bumps documented in test rationale matching prior bump pattern.
- `templates/skill-critic.md` is a thin launcher pointing at `.prawduct/critic-review.md`; product Critic instructions reach product repos through `templates/critic-review.md` (already updated). No edit needed there.

**Files:**

- `docs/principles.md`: new Principle 6 inserted after Honest Confidence; principles 6-22 renumbered to 7-23
- `CLAUDE.md`: inline-numbered Quality list gains entry at 6; Product/Process/Learning/Judgment clusters renumbered; new "Before Building: Requirements Clarity" section between Sessions and Methodology
- `methodology/building.md`: new "Before You Build: Confidence Check" section before The Build Cycle; principle-by-number references updated (Principle 11 → 12, 22 → 23)
- `methodology/discovery.md`: new "Discovery Recurs" section after Risk Calibration; trailing recurrence paragraph reduced to pointer; principle-by-number references updated (Principle #6 → #7, 7 → 8, 8 → 9)
- `methodology/planning.md`: new "Requirements Confidence" subsection under Build Planning
- `templates/build-plan.md`: new "Requirements Confidence" section between frontmatter and Status; principle-by-number reference updated (Principle #9 → #10)
- `templates/build-governance.md`: condensed mirror of the readiness check before the Build Cycle steps
- `templates/product-claude.md`: new "Before Building: Requirements Clarity" section in framework-managed block; Quality principle list gains "Requirements Precede Code"
- `agents/critic/SKILL.md`: Goal 2 (Nothing Is Missing) gains two bullets — acceptance criteria as observable behavior, Requirements Confidence field present
- `templates/critic-review.md`: matching dense-paragraph form for product Critic instructions
- `.prawduct/cross-cutting-concerns.md`: principle-by-number references updated (Principle 7 → 8, 9 → 10); new "Requirements clarity" row added with full pipeline coverage
- `.prawduct/learnings.md`, `.prawduct/learnings-detail.md`: `(#N)` references swept (#21→#22, #17→#18, #16→#17, #14→#15, #13→#14, #12→#13, #10→#11, #9→#10)
- `tests/scenarios/family-utility.md`, `background-data-pipeline.md`, `terminal-arcade-game.md`: principle-by-number references updated (Principle 7→8, 10→11, 22→23)
- `tests/test_v5_methodology.py`: building.md token budget 4100 → 4250 with rationale
- `tests/test_v5_templates.py`: product-claude.md block budget 2900 → 3050, total 3500 → 3650, with rationale; TestProductClaudePrinciples parametrize updated to enumerate all 23 principles (adds Principle 6, shifts subsequent)
- `README.md`: four occurrences of "22 principles" → "23 principles"
- `docs/project-structure.md`: two occurrences of "22 principles" → "23 principles"
- `.prawduct/backlog.md`: token-budget-bumps item promoted from Queue to "Active — next up" (third bump trigger fired this release)
- `VERSION`: 1.3.14 → 1.3.15
- `.claude/settings.json`: banner v1.3.14 → v1.3.15

**Post-/critic-final fixes:** the README/project-structure/test-parametrize/cross-cutting-row/backlog-promotion edits in this list landed in response to three warnings and one note from `/critic final`. The Critic catching the "22 principles" drift in user-facing docs and the test-contract drift in the principles parametrize was a clean illustration of why final-mode is needed: chunk-mode reviews scope to changed files; final-mode reads cross-cutting summaries (README, registry, test enumerations) that drift silently when a sweep misses them.

## 2026-05-08: Stale-clean detection auto-resolves false-edit syncs (v1.3.14)

**Why:** When a product repo gitignores `sync-manifest.json` (the convention for several large client projects), every fresh clone bootstraps the manifest from current on-disk hashes. After a few framework releases, those hashes drift from what current templates would produce — so `template`-strategy files look "locally edited" to sync, even when no human ever touched them. Empirically: 5 of 6 currently-stale files across `discodon` and `discodon-brooks2` were stale-clean, hiding the one file with a real edit under `--force` advice noise. The conservative skip behavior was hostile to upgrade UX precisely when the framework released improvements.

**What:** Sync now detects stale-clean files via historical template render. When a `template`-strategy file's hash doesn't match the manifest's stored hash AND doesn't match the current rendered template, sync walks the framework's git history of that template (with `--follow` for renames, capped at 100 commits, with per-sync render caching). If any historical render matches the current file content, the file is framework-produced from an older version → safe to overwrite without `--force`. Auto-resolved files emit `Auto-resolved {file} (stale-clean from {short_sha})`. Files matching no historical render fall through to the existing skip-with-`--force` behavior — no change in handling for genuine local edits.

The same classification powers `prawduct-doctor`'s `framework_currency` check, which now reports per-file class (`stale-clean` / `local-edit` / `missing`) with an action-oriented detail string and recommends the appropriate next step.

**Behavioral notes:**
- Stale-clean detection runs *before* the `--force` fallback. When a file is both stale-clean and `--force` is set, the action label is `Auto-resolved` (truer to what happened) rather than `Force-updated`. The user's `--force` intent is preserved for genuine local edits, where it's still required.
- `block_template` files (CLAUDE.md) and `always_update` files always overwrite on sync per their existing strategy — doctor classifies any drift as `stale-clean` for those. This piggybacks on the v1.3.13 marker contract change (framework owns content inside `PRAWDUCT:BEGIN/END`).
- Briefing's `Drifted templates` header renamed to `Place-once template advisories` to clarify it's about the place-once template set (project-preferences, boundary-patterns, change-log, backlog, conftest.py) — files the user owns where the framework template has evolved. Distinguishes from doctor's `framework_currency` lens, which covers the managed file set sync actively maintains.

**Files:**

- `tools/lib/sync_cmd.py`: new `_HISTORICAL_RENDER_DEPTH_CAP = 100` constant. New `_match_historical_render(fw_dir, template_rel, target_hash, subs, cache=None)` helper — walks `git log --follow --format=%H --name-only` and pairs each historical SHA with the file's path at that commit, so renamed templates are findable via `git show <sha>:<historical-path>`. Cache keyed by `(sha, historical_path)`. `run_sync()` `template`-strategy branch declares a per-sync `historical_render_cache` and calls the helper between the existing autofix and the local-edits skip.
- `tools/lib/__init__.py`, `tools/prawduct-setup.py`: re-export `_match_historical_render` and `_HISTORICAL_RENDER_DEPTH_CAP` for the legacy importlib test surface.
- `tools/lib/validate_cmd.py`: `framework_currency` refactored to classify each stale file as `stale-clean` / `local-edit` / `missing`. Detail string format: `"<N> files differ — <K1> auto-resolve on next sync (X, Y); <K2> have local edits (Z — review diff or sync --force); <K3> missing (W — sync will create)"`. Recommendations are action-oriented per class. Restart files only listed when they will actually change.
- `tools/product-hook`: briefing label renamed `Drifted templates` → `Place-once template advisories`.
- `VERSION`: `1.3.13` → `1.3.14`.
- `.claude/settings.json`: banner string `Built with Prawduct v1.3.13` → `v1.3.14`.
- `tests/test_prawduct_sync.py`: new `TestMatchHistoricalRender` (7 tests covering HEAD/mid-history match, no-match, --follow across renames, no-git fallback, depth-cap, cache hit). New `TestStaleCleanDetection` (6 tests covering auto-resolve happy path with manifest refresh, genuine-edit skip preservation, --force still works for genuine edits, stale-clean precedence over --force, mixed-batch per-file outcome, per-sync cache populated).
- `tests/test_product_compat.py`: new `TestDoctorClassification` (4 tests covering stale-clean classification, local-edit classification, mixed-class aggregation, happy path unchanged).

## 2026-05-08: `block_template` — framework owns content inside markers

**Why:** Discodon sync from v1.3.5 → v1.3.13 reported `Skipped CLAUDE.md — block has local edits` even though the local block had no user customization — it was just stale framework content from the previous sync. Investigation showed the same false-edit signal would fire on every framework upgrade for repos that gitignore `sync-manifest.json` (which bootstraps fresh per clone, recording on-disk hashes that don't match what the current template renders). The marker convention already promises "framework-owned region" (the `<!-- PRAWDUCT:BEGIN -->` / `<!-- PRAWDUCT:END -->` markers exist for exactly that purpose) but sync was treating in-block content as co-edited shared space.

**What:** `block_template` strategy now always overwrites content between the markers on sync. Content **outside** the markers (before/after) is preserved verbatim, as it always was. The `--force` flag is now a no-op for `block_template` (kept on the CLI for `template`-strategy files).

**Backwards-compat note:** Product repos with hand-edited content **inside** the markers will lose those edits on the next sync. The marker convention has always implied this contract; this change aligns sync behavior with the convention. User customization should live outside the markers.

**Files:**

- `tools/lib/sync_cmd.py`: `block_template` branch simplified from ~90 to ~50 lines. Removed the `stored_hash != product_block_hash` skip-and-`--force` codepath and the separate "Restored" drift-repair branch (those cases now collapse into a single always-overwrite splice).
- `tests/test_prawduct_sync.py`: `test_skips_user_edited_block` → `test_overwrites_user_edits_inside_block`; `test_user_edited_block_skipped` → `test_user_edits_inside_block_overwritten`; `test_force_overwrites_user_edited_block` → `test_force_flag_no_op_for_block_template`; `test_restores_drifted_block` updated to match the unified action label.
- `tests/test_coverage_gaps.py`: `test_block_template_force_overwrites` → `test_block_template_overwrites_user_edits`; `test_drifted_block_restored` updated to match the unified action label.
- `README.md`: sync section now distinguishes whole-file template behavior (skip + `--force`) from block-template behavior (always overwrite inside markers, customize outside).
- `.prawduct/backlog.md`: added two follow-ups for the `template`-strategy false-edit problem (stale-clean detection via historical render; sync skip-summary line counts + `--diff` preview). Removed the now-obsolete `block_template` 3-way merge item.

## 2026-05-08: Proportional Critic — `chunk` and `final` modes (v1.3.13)

**Why:** Per-chunk Critic reviews were redoing repo-wide checks (Coherence, Design, Learnings Cross-Check, Backlog Reconciliation, README/docs scan, Framework-Specific Checks 7-10) on every chunk of a multi-chunk build plan, each taking 4-10 min on large repos. A 5-chunk plan paid 25-50 minutes of Critic time, then `/pr` invoked the PR reviewer to do most of the same checks again over the full diff. Most of that work was redundant: chunk-local correctness (Goals 1-3) catches the high-frequency failures (fix-by-fudging, dropped requirements, broad exceptions) and is cheap; the cross-cutting goals need the full session diff to do their job and belong at end-of-cycle, not on every chunk.

**What:** Two named Critic modes, declared per chunk in the build plan:

- **`chunk`** — Goals 1-3 only, single-pass, scoped to the chunk's uncommitted diff. Skips coordinator pattern, Learnings Cross-Check, Backlog Reconciliation, README scan, Framework-Specific Checks. Target 1-2 min.
- **`final`** — all 7 goals + cross-checks + Framework-Specific Checks. Coordinator pattern eligible for medium/large work. Target 4-10 min.

**Caller-side / persisted-side split:** The slash-command argument and build plan field use the short token (`chunk` / `final`) for ergonomics. The `mode` field persisted in `.prawduct/.critic-findings.json` uses the verbose form (`"chunk (lighter pass, not ready for push)"` / `"final (full review, ready for push)"`) so session briefings, gate WARNINGs, and anyone reading the JSON sees the implication without consulting docs. The hook validator rejects bare short tokens in the persisted form so writer drift surfaces immediately.

**Files:**

- `agents/critic/SKILL.md`, `templates/critic-review.md`: new `## Modes` section, mode-aware activation steps, JSON schema example with verbose `mode`.
- `agents/critic/review-cycle.md`: `## Mode Selection` and `## Per-Mode Behavior` sections; updated "When Review Is Required" matrix.
- `.claude/skills/critic/SKILL.md`, `templates/skill-critic.md`: `argument-hint: chunk | final` in frontmatter; `$ARGUMENTS` parsing in body; default-to-`final` rule.
- `templates/build-plan.md`: chunk template adds `**Critic mode:** [pick one: chunk or final]`; standard Done-When step 2 reads `/critic <mode>`; Governance Checkpoints adds `**Commit & PR cadence:**`.
- `methodology/planning.md`: new `### Critic Mode Per Chunk` subsection (heuristic, per-chunk-commit contract, fail-safe default).
- `methodology/building.md`: build-cycle Critic step reads `Critic mode:`; new `### Modes` subsection under `## The Critic`; new "Skipping `final` mode" Common Trap.
- `templates/build-governance.md`: build-cycle Critic step references the mode field for product repos.
- `tools/product-hook`: module-level constants `_CRITIC_MODE_CHUNK`, `_CRITIC_MODE_FINAL`, `_CRITIC_MODE_VALUES`. `validate_critic_findings()` accepts records with verbose `mode` (chunk or final) or no mode field; rejects bare short tokens, unknown strings, non-string values. New `_count_build_plan_chunks(prawduct_dir)` helper. New `_critic_session_satisfies_gate(prawduct_dir)` helper — returns `(False, reason)` when a multi-chunk plan has all chunks `[x]` but the latest review was chunk-mode. `cmd_stop` wires the helper as Gate 2.5 (advisory NOTE on stderr, not blocking).
- `VERSION`: `1.3.12` → `1.3.13`.
- `tests/preferences/test_critic_skill_structure.py`: new file with 27 structure tests across `TestCriticModeDocumentation`, `TestCriticVerboseModeStrings`, `TestCriticSkillEntryPoints`, and `TestProportionalCriticMethodology`.
- `tests/test_product_hook.py`: new `TestCriticModeGate` class (15 tests covering the satisfies-gate helper, `validate_critic_findings` mode validation, and end-to-end stop-hook advisory output).
- `tests/test_v5_methodology.py`: SKILL.md token budget bumped 3500 → 3700; building.md token budget bumped 3900 → 4100. Both with in-line rationale comments and a "prefer trimming next time" reminder.

**Verification:** 894 → 937 tests passing, 0 failed (43 new). All three chunks of the proportional-Critic build plan shipped under the new modes (Chunks 01-02 used `chunk` mode at 3-4 min each; Chunk 03 will use `final` mode for end-of-cycle synthesis). The mode contract is self-applied: this build plan declared `Critic mode:` per chunk before the field was formalized in the template, and the template change in Chunk 02 retroactively conformed.

**Backwards-compat note:** Existing product repos see no breakage. Build plans without a `Critic mode:` field default to `final` (fail-safe to thoroughness). Legacy `.critic-findings.json` records without a `mode` key are still valid (the validator continues to accept them; the gate helper treats them as final). Slash-command invocation `/critic` (no argument) still works — the Critic agent defaults to `final` when `$ARGUMENTS` is empty or unrecognized. The advisory gate is non-blocking, so even product repos that miss the mode contract entirely continue to pass governance — they just won't get the speedup.

## 2026-05-05: Test-evidence schema validator + field rename `test_command` → `command` (v1.3.12)

**Why:** `tests_are_current()` in `tools/product-hook` reads `.prawduct/.test-evidence.json` via `.get()`, so writer typos like `ran_at` for `timestamp` or `num_passed` for `passed` parsed silently as "no failures, no timestamp" — failing the freshness check for the wrong reason and burying the actual bug. A discodon-brooks2 build session (commit `3403d23`) added a schema validator to its local product-hook to catch this loud, then asked for the change to be upstreamed so the framework's per-session sync would stop reverting it. Audit also surfaced a documentation/code split: `templates/build-governance.md` documented the field as `test_command`, but the validator (and 3 of 4 sampled real product repos) used `command`. Reconciled to `command`.

**What:**
- `tools/product-hook`: new `_EVIDENCE_REQUIRED_FIELDS` table (`timestamp: str`, `passed: int`, `failed: int`, `skipped: int`, `duration_seconds: int|float`, `command: str`) and `_validate_evidence_schema()` helper. Wired into `tests_are_current()` between the JSON-parse check and the existing fail/timestamp checks, so `test-status` surfaces missing-field and wrong-type errors by name. New `validate-evidence` subcommand exposes the schema check standalone for CI / pre-commit usage; exit 0 = `valid`, exit 1 prefixes stderr with `missing:` / `unreadable:` / `invalid:` / "evidence is not a JSON object" depending on the failure mode. Missing-field check returns before wrong-type check so a single fix-it pass addresses higher-priority repairs first.
- `templates/build-governance.md`: JSON example renamed `test_command` → `command`. New "Required vs. recommended" sentence distinguishes validator-required fields from recommended metadata (`git_sha`, `total`) and free-form extras (`chunk`, `branch`, `notes`) which remain allowed.
- `tests/test_product_hook.py`: existing `TestTestStatus` fixtures updated to include `skipped`, `duration_seconds`, `command` (the new strict schema rejects evidence missing any of them). New `test_schema_violation_surfaces_in_test_status` confirms the schema check fires before the freshness fallback. Two new classes — `TestValidateEvidenceSchema` (8 cases: full-valid, extra-fields-allowed, float duration, single missing field, multiple missing fields sorted+joined, single wrong type, multiple wrong types semicolon-joined, missing-takes-precedence-over-wrong-type ordering) and `TestValidateEvidenceSubcommand` (5 cases: missing file, unreadable JSON, non-dict root, schema-invalid, valid). Helper `_valid_evidence()` produces a fully-schema-valid baseline so tests construct the violation case rather than the whole dict.
- `VERSION`: `1.3.11` → `1.3.12`.

**Verification:** 880 → 894 tests passing, 0 failed (14 new). Smoke tests pass: a `.test-evidence.json` with `"ran_at"` (typo) instead of `"timestamp"` → `python3 tools/product-hook test-status` exits 1 with `stale: evidence missing required field(s): timestamp`; the framework's own freshly-written `.test-evidence.json` validates clean via `validate-evidence`.

**Backwards-compat note:** Product repos with an existing `.test-evidence.json` written under the old documented schema (`test_command` instead of `command`) will report stale on the first session post-upgrade because `command` is now required. Recovery is one re-run of the test suite — no migration tooling is shipped because the cost is low and the alternative (auto-rewriter at sync time) adds permanent surface for a one-time event. Products that already use `command` (verified: discodon, discodon-evals, discodon-brooks2) see zero impact.

## 2026-05-01: Structured Framework Freshness briefing block + anti-conflation guidance

**Why:** A discodon session (running against this prawduct dir) was asked "is prawduct updated?" and produced a wrong answer: it claimed `last_sync 2026-04-23 predates v1.3.10 (committed 2026-04-21)` (logically inverted), and conflated commit-level drift (today's unversioned commit `5885600`) with version-level drift (which didn't exist — discodon already had v1.3.10). Three independent facts (last_sync timestamp, framework version, template advisory) got synthesized into one wrong narrative. The briefing's existing `Advisories: 1 template(s) have new content` line gave the agent only enough information to improvise — and it improvised badly.

**What:** The fix has two parts that reinforce each other:

(1) **Structured freshness facts in the session briefing** — replaces the one-line advisory with a `Framework freshness:` block that pre-computes and presents:
- Framework HEAD short SHA + date + version
- Last-sync commit + date + version (read from manifest)
- Commit delta (computed via `git rev-list --count last_sync_commit..HEAD`, or "unknown" for legacy manifests without `framework_commit`)
- Version delta (when versions differ)
- Drifted templates with their causing commit, date, and subject

The agent now reads facts, doesn't derive them. Surfaces only when there's drift to reason about (commits behind, version delta, or drifted templates) — silent when in sync.

To support this, sync now records `framework_commit` (short SHA of fw HEAD) in `sync-manifest.json` at sync time. Old manifests will populate the field on next sync. Template-drift advisories are enriched with `last_changed_commit`, `last_changed_date`, and `last_changed_subject` via `git log -1 -- <template>` against the framework dir. All git lookups degrade gracefully — when fw_dir isn't a git repo or git is unavailable, fields are empty strings or None, and the briefing renders an "unknown" delta or falls back to the simple advisory list.

(2) **Anti-conflation section in `templates/product-claude.md`** — a new `Framework Freshness` subsection names the three drift dimensions (version / commit / template) explicitly and warns against synthesizing them into "on/off latest". Adds ~50 tokens; required bumping the block budget from 2,800 to 2,900 (deliberate revision, documented inline in the test).

**Verification:** 851 → 880 tests passing, 0 failed. 17 genuinely new tests + 12 inherited reruns (the two new sync test classes inherit `TestRunSyncPlaceOnce`'s 6 setup-validation tests, matching the existing `TestRunSyncTemplateDrift` pattern):
- `TestComputeFrameworkFreshness` (4 new) — manifest extraction, legacy-manifest handling, malformed-JSON guard
- `TestBriefingFreshnessBlock` (6 new) — in-sync silence, commit delta, version delta, drifted-template rendering with commit info, legacy fallback, no-freshness fallback
- `TestSyncRecordsFrameworkCommit` (2 new + 6 inherited) — manifest field written when fw is git, omitted when not
- `TestAdvisoryEnrichment` (2 new + 6 inherited) — last-changed-commit fields populated when fw is git, empty when not
- `TestProductClaudeFreshnessSection` (3 new) — section present, names three dimensions, warns against synthesizing

**Known gap caught during build:** Initial pass missed three early-return paths inside `try_sync` that still returned 2-tuples; subprocess-based hook tests caught it via `ValueError: not enough values to unpack`. Fix was mechanical — converting all returns to 3-tuples — but the lesson is that signature changes need a grep-the-callsites step that's local to the function being changed, not just at import boundaries.

## 2026-05-01: Project-preferences enforcement framework — first generators (batches 1 + 2)

**Why:** Project preferences quietly become aspirational when nothing checks them. Audited prawduct's own `project-preferences.md` against the codebase, found drift (overstated `__future__` rule, stale test-mirroring example, missing Workflow / Parallelization / Testing-strategies fields, no `tools/lib/` mention). After updating the file to current reality, built the first eight enforcement artifacts in two batches to validate the four-mechanism model (Test / Linter / Critic / Session config) on a diverse set of preference shapes.

**What:**
- Updated `.prawduct/artifacts/project-preferences.md`: corrected drifted claims; added Workflow / Parallelization / Testing-strategies fields; expanded File organization to call out `tools/lib/`; sharpened the Error-handling preference with concrete "boundary" examples for Critic adjudication; added explicit Subprocess safety preference (no `shell=True`) under Tooling; added explicit public-function coverage expectation under Testing; added an Enforcement section that maps each preference to its mechanism (Test / Linter / Critic / Session config).
- Added `tests/preferences/` with six tier-2 enforcement tests (13 test cases total) spanning six different shapes:
  - `test_future_annotations.py` — every implementation file in `tools/` and `tests/` begins with `from __future__ import annotations`. Shims auto-detected via the `Backward-compat shim` docstring marker; `__init__.py` and `tests/conftest.py` are explicit exceptions. Self-guards by asserting exception list still references real files. *Shape: AST first-statement check.*
  - `test_parallelization_config.py` — verifies `pyproject.toml` addopts contain `-n auto` and `--dist loadfile`, plus `tests/conftest.py` defines `pytest_collection_modifyitems` and applies `xdist_group` markers. *Shape: TOML/text presence check.*
  - `test_sync_only_architecture.py` — no `async def`, no `import asyncio` anywhere in `tools/` or `tests/`. *Shape: AST recursive walk.*
  - `test_subprocess_safety.py` — no `subprocess.{run,check_output,check_call,call,Popen}(..., shell=True)`. Security-relevant. *Shape: AST call-pattern (Attribute func + keyword args).*
  - `test_test_location.py` — no `test_*.py` files outside `tests/`. Catches files that pyproject's `testpaths` would silently skip. *Shape: file-tree walk.*
  - `test_public_function_coverage.py` — every public function in `tools/lib/` is referenced in at least one test. Exemption list (currently `log`, `load_json`, `strip_test_tracking`, `generate_sync_manifest`) for transitively-tested helpers, with documented resolution path. *Shape: cross-file consistency check.*
- Added matching Enforcement section stub to `templates/project-preferences.md` so new product repos inherit the discipline.
- Critic-enforced preferences (naming, error-handling, class-based grouping, etc.) live in the body of `project-preferences.md` and are adjudicated via the existing Critic Goal 4 (Project Preferences) check.

**How mechanisms were chosen:**
- Tier 1 (Linter) — naming. Prawduct has no linter configured; classifier escalates these to Critic rather than generating a weak AST test that mimics ruff `N` rules. Demonstrates the refusal path.
- Tier 2 (Test) — six preferences spanning six AST/filesystem shapes (above). The `test_public_function_coverage.py` test was tightened mid-implementation after the Critic flagged identifier-bag heuristics as a false-confidence trap; final detection requires `Attribute.attr` or `Name` in `Call.func` position only, with explicit limitations documented in the test docstring. Demonstrates the framework's own guardrail biting back during validation.
- Tier 3 (Critic) — error handling, naming, class-based grouping. "Boundary" / "appropriate" / "sensible grouping" require judgment.
- Tier 4 (Session config) — Workflow values (Branching, PR creation, PR merge) read by `building.md` / `/pr` at decision points. Not test-enforced because they govern session behavior, not code shape.

**Verification:** `python3 -m pytest tests/` → 851 passed, 0 failed (838 baseline + 13 new across `tests/preferences/`). `tools/product-hook test-status` → exit 0.

**Out of scope / backlog:**
- Audit public-function coverage exemptions (4 entries) — decide rename-to-private vs add-direct-test for each.
- Lift "assign a mechanism per preference" pattern from the artifact + template into `methodology/discovery.md` / `planning.md`.
- Workflow values are documented but lack a schema/validator (e.g., allowed values for `Branching`).

## 2026-04-21: Self-heal stale product_name on every sync + Critic/Janitor state-machine guidance (v1.3.10)

**Why:** Two separate issues.

(1) v1.3.9 fixed bootstrap but not ongoing sync — legacy manifests (bootstrapped before v1.3.9, or whose `product_identity.name` was renamed after init) kept the wrong cached `product_name` forever because `run_sync` read from the manifest and never re-consulted the committed `project-state.yaml`. Old clones that pulled v1.3.9 still saw banner churn on every sync. The manifest had two sources of truth for the product name (the cache and the committed identity block) with no reconciliation.

(2) Cross-product reflection surfaced a recurring anti-pattern: Claude repeatedly implements state-based problems (phases, modes, lifecycle stages, views, connection status, workflow steps) through interdependent booleans and scattered conditionals without making the states, transitions, or invariants explicit — producing code where invalid combinations are reachable and recovery paths have no known-good condition to return to. The framework had no check for this.

**Changes:**
- `tools/lib/sync_cmd.py` — `run_sync` now computes `product_name` as `infer_product_name(product) or manifest.get("product_name") or product.name`, making `project-state.yaml` the source of truth and the manifest cache a fallback for legacy manifests without an identity block. When the cache diverges from the committed identity, sync overwrites the manifest entry and emits an action so the correction is visible and persisted.
- Three regression tests in `tests/test_prawduct_sync.py`: self-heal corrects divergence, no-op when manifest and identity agree, fallback to manifest when identity is absent.
- `agents/critic/SKILL.md` and `templates/critic-review.md` — Goal 7 (The Design Is Sound) gains an **Unmodeled state-based problems** bullet. Framed around recognizing when a problem is inherently state-based (discrete conditions govern valid operations; correctness requires every reader to agree on the current condition) and what must be explicit (enumerated conditions, valid/invalid transitions, single source of truth for "what condition are we in"). Implementation-agnostic — enum, class, protocol, reducer, type, schema, or doc all qualify. Severity thresholds: BLOCKING when invalid combinations are reachable and cause correctness/safety failures, WARNING when ≥3 interdependent state signals span multiple call sites with no central model, NOTE for borderline cases (backlog candidates).
- `.claude/skills/janitor/SKILL.md` — Code Health theme gains a parallel bullet for surfacing these patterns during periodic maintenance.
- `methodology/building.md` — pulled back under its 3900-token budget (4062 → 3877) by removing a redundant "no pre-existing exception" paragraph (the same rule is stated in the Clean Baseline bullet, Test Discipline section, and Common Traps entry), tightening Context Compaction, Session Scope Discipline, and Critic-section prose. No rule removed; same meaning in fewer words. The budget overflow had been shipping since v1.3.8 and was surfacing as a test-suite failure across product repos.

**Blast radius:** `tools/lib/sync_cmd.py`, `tests/test_prawduct_sync.py`, `agents/critic/SKILL.md`, `templates/critic-review.md`, `.claude/skills/janitor/SKILL.md`, `methodology/building.md`. 838 tests pass, 0 failing.

## 2026-04-19: Fix banner churn across repo clones with different directory names (v1.3.9)

**Why:** Users working in multiple clones of the same product repo (e.g. `my-app` and `my-app-feature`) saw `.claude/settings.json` get rewritten to a different product-name banner on every session start, producing a permanent dirty diff that had to be ignored or repeatedly reverted. Root cause: `.prawduct/sync-manifest.json` is gitignored, so bootstrapping ran on every fresh clone; the bootstrap product-name parser scanned for a top-level `product_name:` key that never existed in the template (the actual layout is `product_identity.name:`), so it silently fell back to the directory name and baked that into the `{{PRODUCT_NAME}}` banner substitution.

**Changes:**
- `_bootstrap_manifest` in `tools/lib/sync_cmd.py` now calls the existing `infer_product_name()` helper, which correctly reads `product_identity.name` from the committed `project-state.yaml`. Directory-name fallback is preserved for repos missing the identity block.
- Updated `test_bootstrap_infers_product_name_from_state` to use the real `product_identity.name` layout with a regression comment; the product dir and identity now deliberately differ so the test pins the fix.

**Blast radius:** `tools/lib/sync_cmd.py`, `tests/test_prawduct_sync.py`. 832 tests pass.

## 2026-04-17: Session-timestamp freshness + lag warning for stale product-hooks (v1.3.8)

**Why:** Two related session-start staleness defenses. (1) The old fingerprint system (HEAD SHA + dirty file content hashes) caused chronic false positives: any commit — even metadata-only — invalidated test evidence, wasting cycles on re-runs and "benign fingerprint drift" warnings. (2) Discodon session today showed `fingerprint drift (55ae5158c4e1 -> b27c1100a6db)` despite the framework having replaced fingerprints — the product was pinned at v1.3.7 and its local `tools/product-hook` was the old code, but nothing warned about it. Product repos can silently run stale hook code when the session-start auto-sync doesn't apply.

**Changes:**
- **Trust-the-cycle freshness check** — Removed `compute_test_fingerprint()`, `hashlib` import, and ~70 lines of hashing logic from `tools/product-hook`. Evidence is current if it was recorded during the current session with all tests passing. 10 doc/template files updated to teach the new model; 3 moot backlog items removed.
- **Bidirectional framework version check** — `_check_framework_version` in `tools/product-hook` now also warns when the framework's `VERSION` is *newer* than the manifest's `framework_version` (previously it only warned in the stale-framework direction). Message names both versions and prints the exact `prawduct-setup.py sync` command so the fix is copy-paste. Fires when auto-sync at session start didn't apply for any reason (sync failed, framework unreachable, manifest not updated).
- **Test** — `test_product_lags_framework_warns` in `tests/test_coverage_gaps.py` covers the new direction using a no-op sync script so the manifest stays stale, mirroring the existing `test_stale_framework_warns` pattern.

**Blast radius:** `tools/product-hook`, `tests/test_product_hook.py`, `tests/test_coverage_gaps.py`, 10 doc/template files. 832 tests pass.

## 2026-04-15: Shift reflection cadence to work boundaries (v1.3.7)

**Why:** Product sessions were hitting friction when the user said "ready to /clear" — Claude almost always replied "wait a minute, let me write the reflection" and kept the user waiting. The old cadence ("reflect before session end") also produced rushed reflections written under time pressure.

**Changes:**
- `methodology/reflection.md` — "When to Reflect" reframed around work boundaries (chunk-end after Critic, bug fix, error recovery, judgment call, PR merge). Session-end becomes synthesis, not from-scratch. Capture step now distinguishes `.session-reflected` (per-cycle narrative) from `learnings.md` (durable rules).
- `methodology/building.md` — Build cycle "Reflect" step says "now, not at session end." Session Scope Discipline checklist step 6 is "reflection synthesis" over a file that's already populated.
- `CLAUDE.md` — Learning Loop section leads with the work-boundary cadence.
- `tools/product-hook` — Reflection-missing blocker message teaches the new cadence.
- Templates (`templates/product-claude.md`, `templates/build-governance.md`) — same reframing propagated to product repos via sync.

Hook behavior is unchanged — it already checked `.session-reflected` exists with ≥50 chars. The fix is methodological: when reflection happens at chunk boundaries, the file is already populated by the time the user asks for `/clear`, and handoff becomes fast.

**Blast radius:** 5 framework files + 2 product templates. 832 tests pass. Token-budget tests caught bloat twice and enforced tighter prose.

## 2026-04-15: Fix chronic "stale test evidence" false positive (v1.3.6)

**Why:** 8+ product sessions reported the Critic almost always warning "stale test evidence SHA — expected timing". Root cause: `compute_test_fingerprint()` hashed every dirty path from `git status --porcelain` without filtering framework/session metadata. Between the Verify step (fingerprint written) and the Critic step (fingerprint re-checked), the builder routinely touches `.prawduct/.critic-findings.json`, `.prawduct/backlog.md`, `.prawduct/artifacts/build-plan.md`, `.claude/settings.json`, etc. — normal build-cycle churn that has no bearing on test results. The fingerprint changed, the Critic flagged it, every time.

**Changes:**
- `compute_test_fingerprint()` in `tools/product-hook` now skips paths matching `_is_metadata_path()` (the same filter already used by `git_has_session_changes()` and `_session_changes_are_doc_only()`). Prefixes: `.prawduct/`, `.claude/settings.json`, `.claude/skills/`, `tools/product-hook`.
- New regression test `test_metadata_changes_do_not_invalidate_fingerprint` in `tests/test_product_hook.py` asserts identical fingerprints for (src-only dirty) vs (src + multiple metadata files dirty).

**Blast radius:** 2 files (product-hook, test file). 832 tests pass.

## 2026-04-13: Property-based testing guidance + template drift advisory system (v1.3.5)

**Why:** Property-based testing guidance was orphaned in a single test scenario file — no PBT knowledge flowed to product repos through templates, sync, or governance. Separately, the framework had no mechanism to notify existing products when place-once templates improved (test-specifications, project-preferences, conftest.py were fire-and-forget).

**Changes:**
- PBT guidance added to synced templates (build-governance, critic-review, Critic SKILL) — NOTE-level check in Goal 1, domain-conditional guidance in build cycle
- PBT content added to place-once templates (test-specifications Property-Based Tests section, project-preferences Testing strategies field, conftest.py Hypothesis config block)
- Template drift advisory system: place-once template hashes tracked in sync manifest, drift detection on each sync, advisories surfaced in session briefing
- Janitor skill: new Template Currency investigation theme, framework health pre-check, hash-update guidance after review, `templates` scope shorthand
- Methodology: discovery surfaces domain-driven testing strategies, building.md "Test strategies match the domain" principle, cross-cutting concerns updated
- Place-once mapping constants extracted to core.py (PLACE_ONCE_TEMPLATES, PLACE_ONCE_COPY)

**Blast radius:** 18 files. Templates (6), tools (3), tests (5), methodology (2), agents (1), cross-cutting concerns (1). 43 new tests, 831+ total.

## 2026-04-07: Doc-only gates, gate waivers, test fingerprint, defensive untrack, worktree awareness (v1.3.4)

**Why:** Four user-reported friction points: (1) docs-only sessions were tripping the Critic and PR gates even though there was no code to review; (2) tests were being re-run unnecessarily by builders, the Critic, and the PR reviewer because saved evidence used `git_sha` alone, which can't track uncommitted edits; (3) `.session-handoff.md` and other session files were causing merge conflicts in product repos when they had been accidentally committed before being gitignored — sync had a fix but only on next sync; (4) agents working in git worktrees reported that `git_has_code_changes()` ignored the session baseline and that the hook was not surfacing worktree state.

**Changes:**
- **Doc-only skip + waivers:** `cmd_stop` now skips Critic and PR gates when all changed files are `.md` (using the existing `_session_changes_are_doc_only`). Agents can also write `.prawduct/.gates-waived` (JSON: `{"critic": "reason", "pr": "reason", "reflection": "reason"}`) to declare a gate N/A for the current session. Empty reasons are rejected as a guardrail. The file is auto-deleted on `cmd_clear` so waivers never carry across sessions. The hook prints `GATE WAIVERS:` and the reason for each skipped gate in stderr.
- **Test fingerprint:** `compute_test_fingerprint()` returns sha256 of (HEAD SHA + sorted dirty file paths + each dirty file's content hash). `.prawduct/.test-evidence.json` gets a new `fingerprint` field. New subcommand `python3 tools/product-hook test-status` prints `current` (exit 0) or `stale: <reason>` (exit 1) — single source of truth for builders, the Critic, and the PR reviewer to decide whether re-running the suite is necessary. Falls back to git_sha-only comparison for older evidence as long as the working tree is clean.
- **Defensive untrack:** `cmd_clear` now runs `_untrack_session_files()` on every session start, mirroring `untrack_gitignored_files()` from `tools/lib/core.py`. This means product repos that have an accidentally-committed session file get cleaned up at session start regardless of whether sync ran. List is duplicated in `_SESSION_GITIGNORED_PATHS` (product-hook is intentionally standalone); a parity test in `test_coverage_gaps.py` keeps the two lists in sync.
- **Worktree fixes:** `git_has_code_changes()` now delegates to `git_has_session_changes()` so it consults the session baseline and skips pre-existing dirty state — previously it treated every non-`.prawduct/` line as a "code change" since session start, which fired the Critic gate against pre-existing dirt. New `_detect_worktrees()` helper inspects `git worktree list --porcelain` and surfaces a "Worktrees:" line in the session briefing when more than one worktree is attached, naming the active branch+path and listing the others. Agents are warned that gates only see the active worktree.
- **Docs:** `templates/build-governance.md`, `templates/critic-review.md`, `templates/pr-review.md`, `agents/critic/SKILL.md`, `agents/pr-reviewer/SKILL.md`, `templates/skill-critic.md`, and `.claude/skills/pr/SKILL.md` updated to teach the `test-status` check and the waiver pattern.
- **Tests:** Added `TestDocOnlySkipsCriticGate`, `TestGatesWaived`, `TestTestStatus`, `TestDefensiveUntrackOfSessionFiles`, `TestGitHasCodeChangesUsesBaseline`, `TestWorktreeBriefing`, plus `TestProductHookGitignoreMirror` (parity guard).

## 2026-04-04: Fix overzealous stop hook and build plan git tracking (v1.3.3)

**Why:** The stop hook was firing the Critic gate against completed plans (all `[x]` chunks) and against housekeeping changes that shouldn't trigger a code review. Build plans were also tracked in git despite being ephemeral working artifacts, causing merge conflicts when multiple branches each wrote to the same path.

**Changes:**
- Gitignored `build-plan.md` in this repo and all product repos via `GITIGNORE_ENTRIES` — build plans are ephemeral working artifacts, not permanent specs
- Stop hook Critic gate now checks for *active* (incomplete) chunks instead of file existence — completed plans (all `[x]`) and housekeeping changes no longer trigger false blocks
- Added `_has_active_build_plan_file()` helper; updated both clear and stop hook gate checks
- Updated tests to use plans with real Status sections; added `test_completed_build_plan_skips_critic`
- VERSION bump was missed in the original commit (a4696d6) and is backfilled here

## 2026-04-03: Stop tracking test counts as static artifacts (v1.3.2)

**Why:** Test count is derived data — it changes every time a test is added or removed. Storing it in static artifacts (project-state.yaml, CLAUDE.md, learnings.md) creates constant reconciliation work: the Critic flags discrepancies, and developers spend real time updating numbers that have no value over the hook's dynamic count.

**Changes:**
- Removed "test counts" from the artifact-update guidance in `methodology/building.md` and `build-governance.md` (template + instance)
- Removed "test counts" from the Critic's bidirectional freshness check (`agents/critic/SKILL.md`)
- Removed "update test count" from the janitor's task list (`.claude/skills/janitor/SKILL.md`)
- Removed `build_state.test_tracking` from the framework's own `project-state.yaml`
- Added `strip_test_tracking()` migration step to `tools/lib/migrate_cmd.py` — removes stale `test_tracking` from existing product repos on next migrate/sync

## 2026-04-01: Embed Critic review in build plan chunks (v1.3.1)

**Why:** Critic review was being skipped or offered as optional despite explicit behavioral instructions in CLAUDE.md. Behavioral instructions degrade under context pressure; the build plan — which Claude actively follows step by step — had no Critic step at all.

**Changes:**
- Build plan template: each chunk now has "Done when" steps (acceptance + `/critic` + commit)
- Removed "do not ask, do not offer" behavioral instructions from CLAUDE.md, product-claude.md, build-governance.md
- Replaced with plan-following instruction: "Follow the plan — the Critic step is there"
- Stop hook blocker message now references the build plan's "Done when" steps
- Build governance step 9 ties chunk `[x]` marking to "Done when" completion

## 2026-03-30: Extracted lib modules, framework version tracking, reflection gate improvements (v1.3.0)

**Why:** The monolithic setup script was difficult to test and maintain. Framework version tracking was needed so product repos can detect when they're out of sync. The mandatory reflection gate was blocking exploratory/Q&A sessions that had no build work to reflect on.

**Changes:**
- Extracted `tools/lib/` modules (core, init, migrate, sync, validate) from monolithic setup script
- Framework version tracking — sync records `framework_version` in manifest; session start warns if `../prawduct` is stale relative to last sync
- Reflection gate is now advisory (not blocking) when no build plan is active — exploratory/Q&A sessions no longer require mandatory reflection
- Comprehensive test coverage for all user onboarding journeys (750 tests)
- V4_GITIGNORE_ENTRIES now matches GITIGNORE_ENTRIES (adds `.session-handoff.md`, `.test-evidence.json`, `.pr-reviews/`)
- Critic changelog scope — only checks entries from current changeset, not historical entries
- Gitignore hygiene — sync removes managed files from .gitignore if incorrectly added
- Deprecation warnings when migrating v1/v3/partial repos

**Classification:** structural

## 2026-03-28: Structural Critic tool restrictions, test evidence, and auto-invocation (v1.2.9)

**Why:** The Critic repeatedly ran the full test suite (10K+ tests) despite instructions not to — behavioral constraints lose to safety goals when the agent has unrestricted Bash access. Additionally, builders treated Critic review as optional, offering it as a user choice rather than running it automatically.

**Changes:**
- Critic is now a proper Claude Code skill (`.claude/skills/critic/SKILL.md`) with `allowed-tools` that structurally prevent running tests, builds, or executables. Uses `context: fork` for independent review.
- Test evidence mechanism: builder records results to `.prawduct/.test-evidence.json` during Verify; Critic reads evidence instead of re-running tests.
- Strengthened Critic invocation language: "Run `/critic` now — do not ask the user, do not offer it as an option."
- Stop hook skips reflection gate for doc-only (.md) changes.

**Classification:** governance

## 2026-03-22: Make project-state.yaml merge-friendly

**Why:** Multiple agents/developers working in parallel branches frequently conflict on project-state.yaml. Agents resolve by taking "ours," losing other branches' progress.

**Changes:** Branch-scoped WIP (keyed by git branch name), change_log split to separate .prawduct/change-log.md, test_count computed instead of tracked, merge conflict guidance added.

**Classification:** structural

## 2026-03-22: Consolidate init/migrate/sync into unified prawduct-setup.py

**Why:** Three scripts with importlib cross-imports, a 6-step prose detection algorithm in CLAUDE.md, no post-setup validation, and no health check tool.

**Changes:** Unified into one script with subcommands (setup, sync, validate). Added /prawduct-setup skill. Old scripts replaced with import-safe backward-compat shims. 725 total tests.

**Classification:** structural
