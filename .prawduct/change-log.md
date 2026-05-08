# Change Log — Prawduct Framework

<!-- Append new entries at the top. Each entry is a ## section.
     Historical entries (pre-2026-03-22) are in project-state.yaml under change_log_history. -->

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
