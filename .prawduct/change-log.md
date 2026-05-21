# Change Log — Prawduct Framework

<!-- Append new entries at the top. Each entry is a ## section.
     Historical entries (pre-2026-03-22) are in project-state.yaml under change_log_history. -->

## 2026-05-21: Chunk 02 — `/critic verify-resolutions` mode + stop-hook gate awareness

<!-- prawduct: chunks=02 | status=shipped | scope=v1.5 -->

**Why:** v1.5 thread C — the "Critic flagged 1-2 BLOCKING findings, builder fixed them, re-review pays full chunk-mode latency to confirm a one-line change" friction motivated this work (backlog entry 2026-05-20). Chunk 01 added the `commit_reviewed` anchor; this chunk lands the mode that uses it.

**What:**

1. **Fourth Critic mode `verify-resolutions`.** Goals 1-3 against the union of (prior `files_reviewed`) ∪ (files changed since prior `commit_reviewed`). Target wall-clock 1-2 min, same as `chunk`. The verbose persisted form is `"verify-resolutions (delta review, prior findings only)"`; bare token rejected by the schema validator.

2. **`_compute_verify_resolutions_scope` helper.** Reads the prior findings file, extracts the anchor, runs `git diff --name-only <commit_reviewed>` + `git ls-files --others --exclude-standard`, filters `_is_metadata_path` from the delta (so incidental `.prawduct/` and other metadata churn doesn't inflate the threshold — symmetric with `_verify_resolutions_gate_check`), applies the widening demotion `len(delta) > 2 * prior + 5`, and returns the scope union. Fail-closed for missing findings, missing/unresolvable `commit_reviewed`, no actionable findings, or scope-widening — every demotion category returns `(empty_list, categorized_reason)` so callers fall through to `/critic chunk` or `/critic final`.

3. **Stop-hook gate awareness.** A `verify-resolutions` findings file clears the Critic gate only when current chunk diff is a subset of the findings' `files_reviewed` (`_verify_resolutions_gate_check`). Out-of-scope chunk diff produces a specific BLOCKER message naming the out-of-scope files. Other modes (chunk/final/cumulative) bypass the subcheck — the standard gate logic applies.

4. **End-of-cycle advisory extended.** `_critic_session_satisfies_gate` now treats both `_CRITIC_MODE_CHUNK` and `_CRITIC_MODE_VERIFY_RESOLUTIONS` as partial-coverage modes (`_CRITIC_MODE_GOALS_1_3_ONLY`). Closing a plan with verify-resolutions fires the same WARNING as closing with chunk — Goals 4-7 + Learnings Cross-Check + Backlog Reconciliation still need a `/critic final`.

5. **Docs propagated across all four Critic surfaces.** `agents/critic/SKILL.md` Modes section (one line, ≤2918 tokens — well under the 3050 budget), `agents/critic/review-cycle.md` per-mode table (new column + new "Verify-resolutions scope and demotion" subsection with demotion-criteria table), `templates/critic-review.md` (full mode bullet with scope/demotion/gate behavior), `.prawduct/critic-review.md` (sync-propagated; manifest hash refreshed), `.claude/skills/critic/SKILL.md` (argument-hint + step 1 expansion).

**Dogfood validation:** Chunk-mode Critic surfaced 2 WARNINGs (advisory-gate gap + metadata-filtering gap) and 1 NOTE (defense-in-depth, deferred to Chunk 03 per the NOTE's own recommendation). After fixing both warnings, `/critic verify-resolutions` against the same chunk completed in single-pass against the 7-file scope and confirmed both resolutions with 0 findings — the user-feedback motivation ("re-review at full latency for a one-line fix") empirically resolved on first use. First framework-side proof the mode delivers its claimed proportionality.

**Test coverage:** 1316 passing (+21 over Chunk 01's 1295). New `TestVerifyResolutionsMode` class (20 tests) covers: validator accepts verbose form / rejects bare token, helper fail-safe modes (missing findings, unreadable JSON, missing `commit_reviewed`, no actionable findings, NOTE-only findings, unresolved commit, scope widening at threshold boundary, metadata filtering), gate-check (other modes bypass, in-scope passes, out-of-scope rejects with named file, metadata-path session changes ignored, fail-closed on unreadable findings), and end-to-end stop-hook integration (in-scope accept, out-of-scope reject with specific BLOCKER message). Extended `TestCriticModeGate` with the verify-resolutions advisory case and a cumulative-satisfies case.

**Backlog:** N1 (expose `_compute_verify_resolutions_scope` as a CLI subcommand so the Critic agent's invocation path also enforces the widening threshold — currently the agent reimplements it from the SKILL.md prose) deferred to Chunk 03 per the NOTE's own recommendation.

## 2026-05-19: `/pr` doc-only fast-path

<!-- prawduct: release=v1.4.0 | status=shipped | scope=v1.4 -->

**Why:** Pain-point audit (this session) found `/pr create` runs the full cumulative-Critic + PR-reviewer gates even when the entire `merge-base...HEAD` diff is `.md` — a one-line `.prawduct/backlog.md` edit on a protected branch was a 10-minute ordeal. The stop hook already exempts session-end doc-only changes (`_session_changes_are_doc_only`), but `/pr` did not inherit that proportionality. Audit verdicts captured the gap; this entry closes it for the create flow.

**What:** New `check-pr-doc-only` product-hook subcommand mirrors the stop hook's exemption at the PR boundary, computing the diff over `merge-base...HEAD` (not the session baseline — semantically required because a PR can span multiple sessions). Base resolution uses the same `origin/main` → `main` → `HEAD~1` precedence as `_coverage_resolve_base`, so the gate sees the same diff surface as the cumulative-Critic flow. `.claude/skills/pr/SKILL.md` gains a Step 1b that calls the new subcommand; exit 0 skips Steps 2 (cumulative-Critic), 2b (operator-verification), 3 (PR reviewer), and 4 (review evidence gate), jumping straight to Step 5 (Create PR). Exit 1 (any reason — non-`.md` file present, empty diff, no resolvable base, git failure) falls through to the full review path. The gate fails closed by design.

**Scope deferred:** The other three pain points surfaced in the audit are not addressed here. (1) Small-bugfix proportionality (no code-change escape hatch) — open. (2) Many-small-chunks Critic overhead — partially mitigated via wave-batching + chunk-mode already; no further work. (3) develop→main artifact stripping — backlog item filed 2026-05-19, not implemented. The doc-only fast-path was the cheapest win and the most acute friction.

**Test coverage:** 1284 passing (+6 over Chunk 14's 1278). `TestCheckPrDocOnlySubcommand` (6 tests) covers: all-`.md` exits 0; mixed `.md`+code exits 1 with the offending path in stderr; code-only exits 1; `.yaml` in `.prawduct/` (governance file, not docs) exits 1; empty diff exits 1 (fail-closed: no diff ≠ doc-only); no resolvable base exits 1 (fail-closed: cannot evaluate). Tests use a real git repo per the `_init_real_git_repo` pattern — the subcommand calls real `git diff`, mocking it would just re-test the mock.

**Version:** v1.4.0 (was 1.3.17). Joins the v1.4 release alongside the F10 operator-verification gate (Chunk 14) and the earlier wave work. The fast-path is the closing piece of v1.4's "PR-boundary proportionality" theme.

## 2026-05-19: Chunk 14 — F10 operator-verification queue + `/pr` BLOCKING gate

<!-- prawduct: chunks=05,06,07,08,09,10,11,12,13,14 | release=v1.4.0 | status=shipped | scope=v1.4 -->

**Why:** Final v1.4 chunk. Visual / live-integration changes have always shipped with ad-hoc "user-side smoke test recommended" caveats — no tracking, no enforcement, no work-log of why a change merged before its human verification was complete. F10 closes the gap: an append-only queue (`.prawduct/operator-verification.md`), a `/pr create` BLOCKING gate when `operator_verification_required: true`, an explicit override (`/pr create --accept-pending-verification "rationale"`) that records the bypass into the queue file itself (the queue *is* the work-log), and a deliberate user-action drain (`prawduct-setup verify <dir> <VRF-id>`). Per the Chunk 10 learning *Auto-enable belongs with visibility, not enforcement*, the gate ships **off by default** in v1.4.0 — explicit opt-in via `migrate --enable-operator-verification` (deviating from the maintenance-plan's "default true" because BLOCKING enforcement must be a workflow commitment users see before it bites). The migration runner is the third entry in the Wave-3 per-feature opt-in trio (coverage, settings-layout, operator-verification).

**What:** Six surfaces — new lib module, new product-hook commands, new prawduct-setup subcommand + migrate flag, new template, new `/pr` skill step, Critic Goal 2 + methodology + build-plan-template hooks.

1. **`tools/lib/operator_verification.py`.** New ~330-line module. Parser: scans for `## VRF-<id>` headings, captures first non-blank body line as `**Status:** pending|verified|accepted`. Missing/unknown status defaults to `pending` (the "Escape hatches in classification create silent failures" learning — unknown is the blocking branch). Mutators (`mark_verified`, `mark_accepted`) preserve every body line outside the status, append `**Verified:** YYYY-MM-DD` or `**Accepted:** YYYY-MM-DD — rationale: <text>`, and refuse the wrong direction (verifying an `accepted` entry would erase the override rationale — raises ValueError). Runners (`run_check_operator_verification`, `run_verify_entry`, `run_accept_pending`) return the standard `{product_dir, ..., actions, notes}` dict shape used by other prawduct-setup runners. Column-0 YAML scanner (`is_operator_verification_required`) mirrors the F4/F5 inline-comment-tolerant pattern.

2. **`tools/product-hook` — `check-operator-verification` and `accept-operator-verification "<rationale>"` subcommands.** `check` mirrors `check-cumulative-critic` semantics: exit 0 when the gate is satisfied (flag off OR no pending entries); exit 1 with stderr message naming the first pending VRF-id and suggesting next steps when blocked. `accept` flips every pending entry to accepted with the rationale recorded into each entry (the override is per-PR; future PRs reblock if new pending entries appear). Missing or whitespace-only rationale rejected — the rationale is the work-log entry, refusing it would leave a silent override trail.

3. **`tools/lib/migrate_cmd.py::enable_v1_4_operator_verification` + `run_migrate_operator_verification`.** Modeled on `enable_v1_4_coverage`, NOT `enable_v1_4_settings_layout`: flips `operator_verification_required: false → true` in project-state.yaml (or appends a documented block when key absent), places the queue template from `templates/operator-verification.md` if absent (queue file must exist before the gate can read it), sets `manifest['v1_4_operator_verification_enabled'] = True` for one-shot tracking. `force=True` bypasses the one-shot check. Existing queue file content is NEVER overwritten (place-once-style — user-authored append history is sacred).

4. **`tools/prawduct-setup.py`.** New `--enable-operator-verification` migrate flag added to the existing per-feature-opt-in CLI (extends the feature-flag list from Chunk 12). New `verify` subcommand: `prawduct-setup verify <product_dir> <VRF-id> [--json]` — drains a single pending entry. Refuses to verify an `accepted` entry with an actionable error message.

5. **`templates/operator-verification.md`.** New queue template (placed by migration, not init). Documents the schema, the gate behavior, the drain UX, and the override semantics in an HTML comment. Format-by-example below the comment.

6. **`.claude/skills/pr/SKILL.md` — Step 2b: Operator-verification gate.** New mandatory step inserted between cumulative-Critic gate (Step 2) and Independent reviewer (Step 3). Detects `--accept-pending-verification "rationale"` in `$ARGUMENTS`; runs `check-operator-verification`; on exit 1, either invokes `accept-operator-verification "<rationale>"` (override path) or blocks with the two-option message (verify-each path). Allowed-tools updated for both new product-hook subcommands.

7. **Critic Goal 2 + methodology + build-plan template hooks.** `agents/critic/SKILL.md` and `templates/critic-review.md` Goal 2 each gain a one-line NOTE check: when `operator_verification_required: true` AND chunk declares `Visual change: yes`, queue must reference the chunk → NOTE. `methodology/building.md` chunk-close step gains a 2-sentence Operator-verification pointer (~30 tokens after aggressive trimming + a +25 token budget bump to 4400 with a justifying comment; the maintenance plan's pipeline-coverage requirement is the load-bearing constraint). `templates/build-plan.md` gains an optional `**Visual change:** yes` field, peer to `**Type:**` and `**Foreign API:**`. `templates/project-state.yaml` and `.prawduct/project-state.yaml` each gain the documented `operator_verification_required: false` block. `.claude/skills/prawduct-doctor/SKILL.md` gains a Verify Flow section and `--enable-operator-verification` Migrate Flow subsection.

**Framework default: gate disabled.** The framework's own `.prawduct/project-state.yaml` ships `operator_verification_required: false` — the framework is a CLI/developer-tool with no human-facing UI surface to verify pre-merge. Product repos that ship visual changes opt in via `migrate --enable-operator-verification` after evaluating the workflow consequence.

**Compat:** Strictly additive. Existing repos keep working unchanged — the gate is opt-in, the template field is optional, the Critic NOTE only fires when both the flag is on AND the chunk declares `Visual change: yes`. No sync changes (the queue is placed by the migration, not init). No deprecation pressure: shim removal trigger (per maintenance plan R2) "F10 removes when all known products that ship visual changes run `migrate --enable-operator-verification`" — currently none, since this is v1.4.0 release day.

**Test coverage:** 1278 passing (+54 over Chunk 13's 1224). New `tests/test_operator_verification.py` (54 tests across 11 classes). `TestParseOperatorVerification` (8 tests) covers segmentation: empty/preamble-only, single/multiple entries, unrelated `## Heading` treated as preamble (the parser is lenient on non-VRF headings), missing-Status defaults to pending (silent-failure guard), unknown-status defaults to pending (same), round-trip preserves body verbatim. `TestMarkVerified` (3 tests) covers pending→verified flip, already-verified no-op, accepted→verify refuses with raise. `TestMarkAccepted` (5 tests) covers pending→accepted with rationale, empty / whitespace-only rationale rejected, already-accepted no-op, already-verified no-op (drained states are sacrosanct). `TestPendingHelpers` (1 test) covers count_pending + pending_entries. `TestIsOperatorVerificationRequired` (6 tests) covers the column-0 YAML scanner: missing file/key, true/false values, indented occurrence ignored, **inline-comment tolerance** (Chunk 10 detector/mutator asymmetry lesson reapplied). `TestRunCheckOperatorVerification` (6 tests) covers all return shapes: gate off → satisfied; gate on + no queue file → satisfied (with explanatory message); gate on + empty queue → satisfied; gate on + 1 pending → blocking with first_pending; gate on + 2 pending → pluralized message; drained entries (verified+accepted) don't block. `TestRunVerifyEntry` (5 tests) covers no-`.prawduct/`-dir error, no-queue-file error, unknown-ID error (with known-ID listing), pending→verified (file written back), already-verified no-op, accepted-refused. `TestRunAcceptPending` (3 tests) covers empty-rationale rejection, no-pending clean return, multi-entry flip (only pending entries touched). `TestEnableV1_4OperatorVerification` (7 tests) covers the migration policy: one-shot short-circuit, flip existing-false key, append block when key absent, place queue from template if absent, existing queue NEVER overwritten (user append-history sacrosanct), already-on no-op, inline-comment tolerated. `TestRunMigrateOperatorVerification` (4 tests) covers the runner: no-`.prawduct/` error, missing-manifest error, happy-path persists manifest, result shape stable. `TestProductHookCommands` (3 subprocess tests) and `TestPrawductSetupCLI` (2 subprocess tests) verify CLI/hook dispatch wiring — kept intentionally minimal after the first pass tripped pre-existing parallel-xdist resource contention (`TestMatchHistoricalRender::test_depth_cap_respected` flake; backlog updated).

**Dogfooding:** The framework itself ships with the gate **off** (`operator_verification_required: false`) — Prawduct has no human-facing UI surface to verify pre-merge, and turning the gate on during this chunk would be circular (Chunk 14 would need to declare itself a visual change and enqueue an entry, but its delivery is governance plumbing, not a visual change). Migration tested against synthetic fixtures (`TestRunMigrateOperatorVerification`) demonstrates: missing-key path appends a documented block; existing false-key flip preserves inline comments; manifest one-shot tracks "we ran the migration" while project-state ground truth is re-read on each report. The queue template is placed by the migration when absent and untouched when present (user-edit preservation verified by `test_existing_queue_not_overwritten`).

**Token budgets:** `methodology/building.md` bumped 4375 → 4400 (justified inline at the test comment; +25 for the chunk-close pointer, trimmed to ~30 tokens from an initial ~125 before bumping). `agents/critic/SKILL.md` held at 3324 / 3325 (Goal 2 bullet condensed to a single line; no budget bump). `templates/critic-review.md` and `templates/build-plan.md` are not under separate token budgets.

**Wave 3 complete.** v1.4 build plan: 15 chunks shipped (Chunk 00 + Wave 1 (01-04) + Wave 2 (05-10) + Wave 3 (11-14)). The cumulative-Critic + PR gates ride along — Chunk 14 is itself the trigger for the v1.4.0 release PR.

## 2026-05-19: Chunk 13 — F9 learnings lifecycle sentinel tracker

<!-- prawduct: chunks=13 | status=shipped | scope=v1.4 -->

**Why:** Learnings accumulate in `.prawduct/learnings.md` faster than they retire. By the time a rule's failure mode is structurally enforced by a test, the rule itself is still consuming active-rules attention; the file grows until grep-for-relevance stops working. F9 closes the lifecycle gap with three signals (confirmations, created, sentinel) that let the audit identify candidates for promotion (advisory), retirement (sentinel-pass entries moved to historical detail), and stale flags (>90 days, single-confirmation entries). The point isn't to automate retirement — it's to surface what's mechanically eligible so the user makes deliberate keep-or-retire calls instead of letting the file drift.

**What:** Three surfaces — new audit module, CLI subcommand, doctor-skill flow.

1. **`tools/lib/audit_learnings_cmd.py::audit_learnings(product_dir, *, apply, today, run_sentinels) -> dict`.** New ~250-line module. Schema is a single-line HTML comment placed immediately after each `## Title`: `<!-- prawduct-learning: confirmations=N; created=YYYY-MM-DD; sentinel=path::test -->`. All three fields optional — absence means "active, no lifecycle metadata" and the entry is left alone in every audit run. Parser enforces strict placement (metadata must be on the first non-blank body line) so entries that quote example metadata in their prose don't hijack their own classification. Unknown keys are preserved harmlessly for forward compat; malformed pairs (no `=`) are dropped silently to tolerate manual-edit slips. Promotion is advisory only (no file mutation regardless of `apply`) because `learnings.md` doesn't have a sectioned active/promoted split — the count surfaces in the report. Retirement is the only mutation: when `apply=True` AND the sentinel passes, the entry is removed from `learnings.md` and appended to `learnings-detail.md` under a "Historical (structurally enforced)" section (created if absent). Failing sentinels surface in both `retirements` (with `passed=False`, `applied=False`) and `errors` (so users see "fix me" without scanning every retirement record). The `today` and `run_sentinels` parameters are test seams — production uses real wall clock and runs `python3 -m pytest <sentinel> -q` as subprocess; tests can short-circuit via `run_sentinels=False` for hermetic coverage.

2. **`tools/lib/audit_learnings_cmd.py::run_audit_learnings(product_dir, *, apply=False) -> dict`.** Runner shaped like the other `run_*` commands (init/sync/validate/views/migrate_*). Returns `{"error": "..."}` only for structural problems (no `.prawduct/` directory) — a missing `learnings.md` is a clean empty result, not an error. Sentinel subprocess failures are absorbed into per-entry `errors` entries; the runner itself never raises. The module's filename uses the `_cmd.py` convention (mirroring `migrate_cmd.py`, `sync_cmd.py`, etc.) to avoid the function-vs-submodule shadowing trap when `lib/__init__.py` re-exports both.

3. **`tools/prawduct-setup.py audit-learnings` CLI.** New subparser peer to `migrate` and `validate`. Default dry-run reports per-list summaries with status markers (`pending --apply` / `sentinel FAIL` / etc.); `--apply` performs retirement mutations; `--json` emits the stable result dict for downstream tooling. The human-mode output uses `log()` → stderr (matching other prawduct-setup subcommands), JSON mode writes to stdout. Exit 0 on success including empty results; exit 1 only on structural errors so shell-pipeline callers can branch reliably.

4. **`.claude/skills/prawduct-doctor/SKILL.md` — new Audit Learnings Flow.** Routing table grew a fourth flow next to Onboard / Health / Migrate. Trigger phrases ("audit learnings", "retire structurally-enforced learnings", "check lifecycle metadata") and the `--apply` consequence are spelled out. The skill body explains the schema with a concrete example so users don't need to read the module docstring to annotate their first entry.

**Compat:** Strictly additive. Existing `learnings.md` files keep working unchanged — entries without the metadata comment are treated as "active, no lifecycle metadata" and never appear in any audit list. No sync changes; the audit is user-invoked only. `learnings-detail.md` is created only when `--apply` retires at least one entry; the historical section header is created idempotently (running again finds it and appends rather than duplicating). The `LearningEntry` dataclass + parser are new public surface (re-exported from `lib/__init__.py`) but nothing depends on them yet.

**Test coverage:** 1224 passing (+40 over Chunk 12's 1184). New `tests/test_audit_learnings.py` (40 tests across 6 test classes). `TestParseLearningMetadata` (8 tests) covers the single-line parser: well-formed all-fields, absent comment returns None, partial metadata, whitespace tolerance, trailing semicolons, unknown keys preserved (forward compat), non-prawduct comments ignored, malformed pairs dropped. `TestParseLearningsFile` (6 tests) covers segmentation: empty file, preamble-only, single entry with and without metadata, mixed annotated/unannotated entries, strict placement rule (metadata must be first non-blank body line), round-trip preserves body verbatim. `TestAuditLearnings` (13 tests) covers classification: empty file no-op, promotion candidate surfaces at confirmations≥2, single confirmation not promoted, stale flag at >90 days + confirmations≤1, recent entry not stale, confirmed entry not stale even when old, malformed-date error, malformed-confirmations error, sentinel skip when `run_sentinels=False`, `apply=False` doesn't mutate, `apply=True` with passing sentinel moves entry (uses monkeypatch on the module's `run_sentinel`), `apply=True` appends to existing detail without duplicating the historical header, failing sentinel surfaces as error AND keeps entry in learnings.md, unannotated entries untouched, result shape stable. `TestRunAuditLearnings` (3 tests) covers the runner: no `.prawduct/` returns error, missing `learnings.md` returns clean empty, result shape stable on success. `TestRunSentinel` (3 tests) exercises the real subprocess path against synthetic passing/failing/nonexistent tests in a tmp_path — pins the contract that the subprocess wrapper does NOT raise on common failure modes. `TestAuditLearningsCLI` (3 tests) covers the dispatch wiring: JSON output keys are stable, human mode emits to stderr (Critic NOTE-equivalent: callers that filter for JSON on stdout aren't confused by status text), no-prawduct exits 1.

**Dogfooding:** Annotated two existing entries in `.prawduct/learnings.md` to verify the schema round-trips and the audit classifies correctly. Entry "Coherence cascades require checking summaries" got `<!-- prawduct-learning: confirmations=2; created=2026-01-30 -->` reflecting the "Reinforced 2026-02-22 with identical miss" note in its body — surfaces as a promotion candidate. Entry "Framework ownership follows the write strategy" got `confirmations=1; created=2026-05-19; sentinel=tests/test_prawduct_sync.py::TestAutoCommitSafety::test_user_authored_place_once_edits_treated_as_wip` — the sentinel test was added in Chunk 11 specifically as a regression for the failure mode this learning warns about, making it the canonical structurally-enforced check. `prawduct-setup.py audit-learnings .` returns the entry as a retirement candidate (sentinel passes); JSON mode emits the stable shape with `applied: false`. Did NOT run `--apply` against the live framework — the learning is too recent (Chunk 11) to retire, and the unit tests cover the apply path against synthetic fixtures. The dogfood demonstrates the audit correctly identifies the candidate; whether to retire is a deliberate later decision.

## 2026-05-19: Chunk 12 — F5b settings-layout migration command + product-repo dry-run

<!-- prawduct: chunks=12 | status=shipped | scope=v1.4 -->

**Why:** Wave 3 closes F5 with the user-facing opt-in pair to F5a's silent auto-commit. F5a quarantines framework-managed drift to single `chore(sync):` markers on every sync; F5b stamps the product as explicitly on the canonical minimal settings.json layout so v1.4.1's planned Critic NOTE on un-stamped repos has a single state bit to read. The chunk is mostly a *signal* operation: for products that have been syncing regularly (the framework template's hook block has been at the canonical minimal shape — single-line `python3 product-hook <event>` dispatches — since v1.3.x), the migration is a no-op file-wise. For older repos with v1/v3 hook markers (`framework-path`, `governance-hook`, `prawduct-statusline`) that normal sync skipped, the migration runs an aggressive `legacy_cleanup=True` pass and strips them. The manifest flag is the contract; the file mutation is the side-effect when applicable.

**What:** Three surfaces — migration policy in lib, runner with framework resolution, CLI dispatch flag + skill flow.

1. **`tools/lib/migrate_cmd.py::enable_v1_4_settings_layout(product_dir, template_path, subs, manifest, *, force=False) -> (actions, notes)`.** Pure policy function: refuses to run when manifest already carries `v1_4_settings_migrated: True` (without `force`); reads `.claude/settings.json` and short-circuits cleanly if absent (returns empty without setting the flag — the flag means "I migrated," not "I tried and found nothing"); parse-validates the JSON before mutation so an unparseable settings.json surfaces a diagnostic NOTE and refuses to flip the flag (silent advertising of a never-actually-ran migration is the failure mode this guards against); invokes `merge_settings(..., legacy_cleanup=True)`; reports either "Normalized..." (file changed) or "already on the canonical minimal layout" (no-op) so users can tell the migration succeeded vs. silently failed. Always appends the v1.4.1-NOTE-quieting note as the load-bearing user-facing signal. Manifest flag is set *after* the cleanup pass succeeds, never before — guards against parse-failure paths advertising completion.

2. **`tools/lib/migrate_cmd.py::run_migrate_settings_layout(product_dir, *, force=False) -> dict`.** User-facing runner mirroring `run_migrate_coverage` shape: loads sync-manifest.json, resolves framework via the same `_resolve_framework_dir(manifest, None, product_path)` call sync uses (so error wording — "set `PRAWDUCT_FRAMEWORK_DIR` or clone the framework as a sibling" — is identical across commands), constructs `{{PRODUCT_NAME}}` / `{{PRAWDUCT_VERSION}}` subs from `infer_product_name(product_dir)` ∪ manifest cache ∪ directory name fallback (the same priority chain `run_sync` uses, picked up via `infer_product_name` from core), invokes the policy function, persists manifest. Result shape: `{product_dir, migrated, force, actions, notes}` (or `{error}`) — fixed keys so JSON-mode callers don't branch.

3. **`tools/prawduct-setup.py migrate` CLI.** New `--enable-settings-layout` flag on the existing `migrate` subparser. Dispatch is now a feature-flag list — exactly one flag must be set; both flags rejected with explicit "Run them as separate commands" error rather than auto-chained, because two migrations in one invocation would mask interleaved failure modes. Success-label, on/off-field, and on/off-label are parameterized per active flag so the human-output formatting (`{label}: no changes ({path})\n  v1_4_settings_migrated is ON in manifest.`) generalizes for the F10 operator-verification flag the maintenance plan reserves a slot for. `--force` documentation expanded to cover both use cases (re-surface coverage NOTEs after wiring a verifier, re-normalize hand-edited settings).

**`.claude/skills/prawduct-doctor/SKILL.md` — Migrate Flow.** Split the prior single-flag section into two subsections (`--enable-coverage` and `--enable-settings-layout`), each naming its trigger phrases ("turn on F4", "stamp settings layout", "run migrate-settings"), the workflow consequence (BLOCKING vs. NOTE-quieting), and the user-confirmation step. Dropped a single shared `--force` paragraph at the end so the flag's two use cases are spelled out (coverage: re-surface evidence NOTEs after wiring a verifier; settings: re-normalize after hand-edit).

**Test coverage:** 1184 passing (+15 over Chunk 11's 1169). New `TestEnableV1_4SettingsLayout` (8 tests) covers the policy function: missing settings.json no-op (no flag set); already-minimal sets flag only with explanatory NOTE; legacy v1 markers stripped with `governance-hook` regression assertion; user-authored Stop hook preserved alongside prawduct hook through legacy cleanup; non-prawduct top-level keys (customSetting, permissions) preserved verbatim; manifest one-shot short-circuits without `force`; `force=True` bypasses one-shot; bad JSON → diagnostic NOTE without flag flip (the silent-success failure mode). New `TestRunMigrateSettingsLayout` (7 tests) covers the runner: no `.prawduct/` returns error; missing manifest returns error naming `prawduct-setup setup` as next step; framework_source pointing nowhere returns actionable error; manifest flag persisted after successful run; second invocation without `--force` short-circuits even when settings.json has been hand-mutated to a bad shape; `--force` re-runs and re-normalizes; result shape is stable across all branches (keys `product_dir`, `migrated`, `force`, `actions`, `notes` always present). All tests use real-filesystem `tmp_path` fixtures with synthetic framework checkouts; no subprocess mocking.

**Dogfooding:** Synthetic dry-run against `discodon` and `hallucinote` in ephemeral `/tmp/migrate_settings_dryrun/` clones (no commits to source repos). **Discodon** (last synced at v1.3.16): exactly one file change — `companyAnnouncements` banner version-bumped to v1.3.17 (framework-managed banner is always-update by design). Hooks unchanged; the layout was already minimal. **Hallucinote** (synced at v1.3.17): true no-op; settings.json byte-identical before and after, `actions == []`, single NOTE "already on the canonical minimal layout." Both produced `v1_4_settings_migrated: True` in their sync-manifest.json. Second-run without `--force` is a fast short-circuit (no actions, no notes); second-run with `--force` re-walks the cleanup pass and produces the same already-minimal NOTE — confirms idempotence. JSON output (`--json --force`) emits the stable result shape verbatim. Pattern confirms F5b's intent: most active products see only a flag flip; the legacy_cleanup pass is the safety net for stale repos.

**Compat:** Strictly additive. The migration is opt-in (no auto-flip from sync), one-shot per product (manifest flag), and idempotent without `--force`. Existing settings.json files keep working unchanged on every sync — `merge_settings(..., legacy_cleanup=False)` continues to be the sync-path call, so products that never run the migration see no behavior change in v1.4.0. Critic NOTE on un-stamped products is reserved for v1.4.1 (`maintenance-plan.md` F5 Compat line), not this chunk — Chunk 12 ships only the user-facing path. Shim removal trigger (per maintenance plan): "F5 removes when all known products run `migrate-settings`."

## 2026-05-19: Chunk 11 — F5a sync auto-commit + protected-branch preconditions

<!-- prawduct: chunks=11 | status=shipped | scope=v1.4 -->

**Why:** Every framework upgrade left product repos with framework-managed drift co-mingled in unrelated chunk commits — three downstream repos showed banner-rename + product-hook drift mixed with chunk diffs every release, generating Critic NOTEs that the chunk owner had no business addressing. F5a quarantines framework drift to one dated marker commit per upgrade so chunk diffs stop carrying upstream churn. The chunk also lands the precondition-gated safety surface that lets the auto-commit ship default-on without surprising users: WIP, protected branches, and in-progress git ops each block the commit and surface a marker the next session sees.

**What:** Five surfaces — sync-side auto-commit, precondition gates, project-state config block, session marker, and briefing surfacing.

1. **`tools/lib/sync_cmd.py::_try_auto_commit(product, *, actions, notes, manifest)`.** New ~150-line helper called at the tail of `run_sync()`, after all file mutations and the manifest write. Reads `git status --porcelain -z`, partitions changes via `_framework_known_paths(manifest)` (manifest `files` ∪ `{.prawduct/sync-manifest.json, .prawduct/project-state.yaml, .gitignore}`), and if all changes are framework-known + preconditions pass, stages just those paths and runs `git commit -m "chore(sync): prawduct vX.Y.Z"`. `PLACE_ONCE_TEMPLATES` / `PLACE_ONCE_COPY` are *deliberately excluded* from the framework-known set (Critic chunk-mode finding 1): place-once files (`.prawduct/change-log.md`, `.prawduct/backlog.md`, `tests/conftest.py`) are user-authored after creation, and including them would have swept user chunk-close appends into the very `chore(sync):` commits F5a aims to prevent. Trade-off: a freshly created place-once file leaves an untracked file in the working tree for the user to commit deliberately, which is appropriate for first-time initialization moments. Contract is best-effort: any subprocess failure or unexpected state degrades to "skip auto-commit, leave drift in working tree" — sync itself must never fail because of this step.

2. **Preconditions (each a single helper, each independently testable).** `_current_branch` (returns empty on detached HEAD, treated as protected to avoid unreachable commits); `_git_op_in_progress` (checks `MERGE_HEAD`, `REBASE_HEAD`, `CHERRY_PICK_HEAD`, `REVERT_HEAD`, plus `rebase-merge/` and `rebase-apply/` directories for interactive rebase); `_branch_is_protected` (fnmatch globs, so `release/*` works without regex weight); the WIP check falls out of the `_classify_changes` partition — any porcelain entry not in the framework-known set is user WIP and blocks the commit.

3. **`.prawduct/project-state.yaml` `sync:` block.** New optional section parsed by `_read_sync_config` (column-0 YAML scanner mirroring `views.py::is_views_enabled` and the Chunk 09/10 `_read_bool_yaml_key` pattern — no PyYAML dependency, inline-comment tolerant after Chunk 10's asymmetry lesson). Defaults: `auto_commit: true`, `protected_branches: [main, master, "release/*"]`. Empty `protected_branches:` (no list entries) falls back to defaults rather than meaning "no protection" — likelier to be a YAML mistake than an intentional opt-out; `protected_branches: []` is the explicit empty form. Templates and the framework's own state file ship unchanged for v1.4 — the block is read with defaults when absent, so existing products auto-get F5a behavior on next sync without a migration step (the Chunk 12 migrate-settings shim handles the settings.json half).

4. **`.prawduct/.sync-pending` marker (gitignored).** Written when preconditions block; JSON shape `{reason, blocked_by, version, ts}`. Added to `tools/lib/core.py::GITIGNORE_ENTRIES`, the framework's own `.gitignore`, and `tools/product-hook::_SESSION_GITIGNORED_PATHS` (the three-way mirror has a coverage-gap test that catches drift — caught and fixed during chunk implementation). Cleared on successful auto-commit so stale markers don't lie about pending state.

5. **`tools/product-hook::assemble_session_briefing` surfacing.** Reads `.sync-pending` when present and emits a one-line `Framework sync pending (vX.Y.Z): <reason>` block. Corrupt JSON degrades to a "marker present but unreadable" pointer rather than crashing the briefing — `briefing must never block session start` is the load-bearing invariant the existing prawduct:ok-broad-except markers enforce on this path.

**Settings.json minimization (the other half of F5a's title):** No-op deliberately. The maintenance plan's F5 Critic note had foreseen this: "the 'settings.json minimization' half is mostly cosmetic in current product repos — hook bodies are already one-line `python3 tools/product-hook ...` dispatches." Inspecting `templates/product-settings.json` confirmed the prediction — `SessionStart` and `Stop` are already single-line command dispatches; the schema fields (`type`, `command`, `statusMessage`, `matcher`) are required by Claude Code's hook config, not framework cruft. Documenting the no-op here so the next reader doesn't grep for missing work.

**Compat:** Strictly additive on the framework side; safe-by-default on the product side. Existing repos that never ran the migration still pass the porcelain partition (managed paths derived from the *manifest* files list, which sync keeps current). The default `protected_branches` covers `main`/`master`/`release/*` — for the framework itself (always on `main`), auto-commit never fires; drift stays in the working tree for deliberate commit. Products typically work on `feature/...` branches and see auto-commit as the happy path. No deprecation pressure on existing settings.json layouts — Chunk 12 ships the migrate-settings command for the explicit opt-in.

**Test coverage:** 1169 passing (+26 over Chunk 10's 1143). New `TestReadSyncConfig` (6 tests) covers the YAML scanner: defaults when project-state absent / no sync block; explicit disable; custom protected branches; **inline-comment tolerance on the value line** (mirrors the Chunk 10 detector/mutator asymmetry fix — the lesson stuck, the test names it explicitly); malformed YAML falls back to defaults. `TestBranchIsProtected` (3 tests) covers exact match, glob match, detached-HEAD-treated-as-protected. `TestAutoCommitHappyPath` (4 tests) covers single-commit creation, marker clearing on success, clean working tree after commit, version-pinned message. `TestAutoCommitPreconditions` (6 tests) covers each precondition independently — protected branch, WIP, rebase-merge, MERGE_HEAD, CHERRY_PICK_HEAD, explicit auto_commit=false (no marker because disable is a choice not a failure). `TestAutoCommitSafety` (4 tests) covers not-a-git-repo silent no-op, stale-marker clearing on no-drift sync, managed-only commit content, plus `test_user_authored_place_once_edits_treated_as_wip` (regression for the in-chunk Critic finding 1: a user append to `.prawduct/change-log.md` must NOT be swept into the chore(sync) commit). `TestSessionBriefing` gains 3 tests: marker surfaces in briefing, absent marker is silent, corrupt-JSON marker degrades to a usable warning. All tests use real-filesystem `tmp_path` fixtures with `git init` — no `subprocess` mocking, matching the test-prawduct-sync style.

**Dogfooding:** `python3 tools/prawduct-setup.py sync .` against the framework itself produces the briefing's `PRAWDUCT SYNC: Framework updated\n  + Refreshed manifest for ...` lines plus a clean `git status` because the framework is on `main` (protected by default) — the safe-path verifying detached-HEAD protection by branch-name. The `.prawduct/.sync-pending` marker file is NOT produced in this case because the framework has no framework-managed drift to commit (only the manifest refresh, which the sync wrote as a refresh action with no porcelain diff). Synthetic dry-run across four scenarios in ephemeral `/tmp/dbg*` repos confirms the happy path: fresh feature-branch sync with framework drift produces one `chore(sync): prawduct vX.Y.Z` commit; subsequent sync with no drift is a clean no-op; planting WIP blocks the commit and writes the marker; protected-branch (`main`) blocks the commit with `"branch 'main' is protected"` in `blocked_by`.

**Critic chunk review:** 0 BLOCKING, 2 WARNINGs, 1 NOTE. (1) WARNING — `_framework_known_paths` included `PLACE_ONCE_TEMPLATES` / `PLACE_ONCE_COPY`, which would sweep user-authored change-log/backlog appends into chore(sync) marker commits (the exact co-mingling F5a aims to prevent). **Fixed in-chunk** by dropping the place-once sources from the partition set and adding `test_user_authored_place_once_edits_treated_as_wip` regression. Docstring updated to explain the deliberate exclusion. (2) WARNING — docstring cited `.prawduct/learnings.md` as a framework-known place-once file but it isn't in any registry (behavior was correct; only the example was wrong). **Fixed in-chunk** by removing the misleading mention. (3) NOTE — `test_managed_paths_committed_wip_excluded` accepts `.gitignore` only because the fixture writes the current `GITIGNORE_ENTRIES`, so `update_gitignore` finds nothing to drift; future chunks adding a gitignore entry will trip the assertion. **Filed to backlog** as a fixture-stability hardening item. The auto-commit happy path + six independent precondition gates + best-effort degraded paths are all covered; F5a's anti-co-mingling intent is now enforced by test, not just docstring.

## 2026-05-19: Chunk 10 — F4c migration tooling + fingerprint terminology cleanup

<!-- prawduct: chunks=10 | status=shipped | scope=v1.4 -->

**Why:** Wave 3 closer. Chunks 08/09 shipped the F4 schema (`verifier`-discriminated coverage fields) and Critic enforcement (`verify-coverage` BLOCKING per missing file). Chunk 10 closes the loop with a user-facing opt-in path so products can move from "schema dogfooded, enforcement off" to "enforcement on" deliberately — not silently on sync (which would surprise downstream products with sudden BLOCKING findings). Also folds in the v1.5-deprecation signaling for legacy evidence shape and a terminology cleanup of "fingerprint" — the tree-hash mechanism that name referred to was removed pre-v1.4, but the word lingered in 5 spots where it was actively misleading.

**What:** Four surfaces — new migration helper, new CLI subcommand, doctor-skill flow, terminology refresh.

1. **`tools/lib/migrate_cmd.py::enable_v1_4_coverage(product_dir, manifest, *, force=False) -> (actions, notes)`.** New ~110-line helper modeled on `enable_v1_4_views` but with three deliberate divergences: (a) returns `(actions, notes)` instead of just actions — the deprecation guidance is a first-class output, not a side channel; (b) NOT auto-called from `run_sync()` — coverage enforcement is a workflow commitment, not a silent upgrade like derived views were; (c) `force=True` parameter re-runs the read-and-NOTE pass for users who want to re-check evidence shape after wiring up a verifier. Mutates `project-state.yaml` (flip `false → true`, or append a documented block when key absent), mutates `manifest['v1_4_coverage_enabled']` (one-shot tracking — accidental re-invocations short-circuit). Inspects `.test-evidence.json` to surface deprecation NOTEs: missing file → "run the verifier first"; legacy shape (no `verifier`) → v1.5-removal warning pointing at `tools/test-reference-verify`; modern shape → no NOTE (don't cry wolf at products already on the new schema).

2. **`tools/lib/migrate_cmd.py::run_migrate_coverage(product_dir, *, force=False) -> dict`.** Thin runner shaped like the other `run_*` commands (init/sync/validate/views) — loads manifest, calls the helper, persists, re-reads on-disk `coverage_required` to report ground truth (the manifest flag tracks "we ran the migration"; the YAML may have been hand-edited between runs). Returns `{product_dir, enabled, force, actions, notes}` for both human and JSON output.

3. **`tools/prawduct-setup.py migrate` subparser.** New `migrate --enable-coverage <product_dir>` subcommand with `--force` and `--json` flags. Missing-feature-flag path exits 1 with usage help — `migrate <dir>` alone is treated as user-uncertainty, not silent success. Per-feature opt-in pattern extends naturally to future flags (e.g. `--enable-operator-verification` for Chunk 14's F10).

4. **`.claude/skills/prawduct-doctor/SKILL.md` — new Migrate Flow.** Doctor skill gains explicit routing for "enable coverage" / "turn on F4" / similar user requests. The flow confirms intent before running (coverage is a workflow commitment, not a doc tweak), surfaces both actions and notes prominently, and points the user at the verifier if legacy-shape evidence is detected.

5. **Terminology cleanup (5 sites).** "Fingerprint" was the old name for a tree-hash freshness mechanism removed pre-v1.4; lingering uses were actively misleading new readers into looking for a hash-based system that doesn't exist. Updated:
   - `tools/test-reference-verify` shebang docs: "fingerprint record produced by pytest" → "pytest-emitted v1.3.x-shape evidence record (the 'legacy' shape — pre-F4a fields)" with note that "fingerprint" was the old name from when freshness relied on tree-hash.
   - `tools/product-hook::tests_are_current` docstring: "No fingerprinting or content hashing" → "No tree-hashing or content fingerprinting (those mechanisms were removed pre-v1.4 after chronic false positives from metadata churn)".
   - `tools/product-hook::_validate_evidence_schema` docstring: "Legacy fingerprint-only evidence" → "Legacy evidence (pre-F4a shape: no `verifier` field — historically called 'fingerprint' though the tree-hash mechanism it referred to was removed pre-v1.4)" with v1.5-removal reference to Chunk 10's migration NOTE.
   - `templates/build-governance.md` + `.prawduct/build-governance.md` (lockstep): same prose updated, plus a bolded **v1.5 removal warning** pointing users at the new migrate subcommand. The line about "Critic enforcement is opt-in" now names the actual command users should run.

**Compat:** Strictly additive. No existing behavior changes — the migration is user-invoked only, never auto-fired from sync. Legacy evidence keeps validating. The manifest gets a new optional key (`v1_4_coverage_enabled`); products that never run migrate just don't have it set.

**Test coverage:** 1143 passing (+17 over Chunk 09's 1126). New `TestEnableV1_4Coverage` (11 tests) covers the helper: missing project-state no-op, pre-v1.4 append, false→true flip, already-on no-rewrite, one-shot manifest short-circuit, `--force` bypasses one-shot, legacy-evidence deprecation note, modern-evidence no-cry-wolf, unparseable-evidence diagnostic, indented-key-doesn't-count-as-top-level, inline-comment-preserved-on-flip (regression for Chunk-10 Critic NOTE on detector/mutator asymmetry). New `TestRunMigrateCoverage` (6 tests) covers the runner: error paths (no .prawduct, no manifest), manifest persistence, ground-truth on-disk reporting, force-flag bypass, stable result shape.

**Dogfooding / synthetic dry-run:** Smoke-tested against four scenarios in `/tmp/mig_test*` repos: (1) fresh enable with no evidence → append block, surface "no evidence" + "next-PR consequence" notes; (2) idempotent re-run → manifest short-circuits, "no changes"; (3) flip `coverage_required: false → true` with legacy evidence + --force → "already-true" note + v1.5-deprecation note; (4) error paths (no .prawduct/, no manifest) → exit 1 with actionable messages. Framework's own `coverage_required` stays `false` — the schema is dogfooded (every chunk's evidence carries F4a fields) but enforcement is held until v1.5 per the maintenance plan's Wave-3 framing. The /tmp dry-runs stand in for real-product (discodon, hallucinote) runs the chunk plan asked for; those follow in their own sessions when product owners opt in.

**Critic chunk review:** 0 BLOCKING, 0 WARNINGs, 3 NOTEs. (1) Detector/mutator asymmetry on inline-commented `coverage_required: false  # comment` → fixed in-chunk with `test_flip_preserves_inline_comment` regression; backlog entry filed for the same pattern in `enable_v1_4_views`. (2) Build-plan stub still named `prawduct-doctor migrate v1.4 --enable-coverage` (pre-unification language from the maintenance plan) → corrected in build-plan.md Description line to `prawduct-setup migrate --enable-coverage` with /prawduct-doctor wrapping; build-plan.md is gitignored, but the change-log entry (this entry) is the canonical record. (3) Product-repo dry-run not captured → addressed by the Dogfooding section above naming the four /tmp scenarios; real-product dry-runs deferred to the products' own sessions.

## 2026-05-19: Chunk 09 — F4b Critic symbol-coverage check + methodology principle

<!-- prawduct: chunks=09 | status=shipped | scope=v1.4 -->

**Why:** Chunk 08 shipped the F4a schema (every chunk now emits `verifier` / `tests_executed` / `changes_referenced` / `coverage_level`) but no enforcement read it. F4b closes the loop: when a project opts in via `coverage_required: true`, the Critic's Goal 1 cross-checks the diff against `changes_referenced` and emits BLOCKING per missing file, with language scaled to the declared `coverage_level` — floor (`referenced`) explicitly disclaims execution; `executed` does not. The chunk's other half is the methodology principle in `building.md` that names what the floor doesn't prove, so authors don't treat "verifier reported clean" as "tests cover this change."

**What:** Three surfaces — new product-hook subcommand, Critic instruction, methodology paragraph.

1. **`tools/product-hook verify-coverage`.** New ~110-line subcommand backed by helpers `_read_bool_yaml_key` (column-0 YAML scanner mirroring `views.py::is_views_enabled`), `_coverage_resolve_base` (matches `tools/test-reference-verify`'s base-resolution so reader and writer agree on diff set), and `_coverage_changed_files` (union of `git diff --name-only BASE` and `git ls-files --others --exclude-standard` — untracked-file inclusion is the silent-failure mode the check exists to catch). Exit semantics: 0 = skipped (`coverage_required: false`, the v1.4 default) or all covered; 1 = preconditions failed (missing/invalid evidence, no `verifier` field, unresolved diff base) or per-file missing coverage. stderr emits one `missing-coverage: PATH (coverage_level: LEVEL) — SUFFIX` line per missing file with `SUFFIX` scaled to level (`floor check — does not prove execution.` vs. `has no executing test.`); the Critic quotes the line verbatim in BLOCKING findings.

2. **Critic Goal 1 (three files in lockstep — `agents/critic/SKILL.md`, `templates/critic-review.md`, `.prawduct/critic-review.md`).** Goal 1 gains one sentence mapping `verify-coverage` exit codes to BLOCKING per file, with explicit instruction not to soften the per-level wording (the wording IS the distinction the chunk introduces). Other exit-1 reasons (missing evidence, no `verifier`, schema invalid) are also BLOCKING — the project opted in, so failing-to-evaluate is real failure, not silent skip.

3. **`methodology/building.md` Test Discipline.** New "Idiomatic tooling, honest coverage" paragraph — language-native incremental/cached runners avoid re-running unchanged tests, the framework asserts the contract (changes covered) not a specific verifier, the reference verifier is a *floor* (catches untested new code, cannot prove execution), and products that need real coverage SHOULD plug in language-native tooling and emit `coverage_level: executed`. This is the F4c methodology principle the maintenance plan called for.

**Compat:** Strictly opt-in. `coverage_required` defaults `false` in v1.4 (set in Chunk 08), so existing projects keep their current Critic behavior — verify-coverage exits 0 with "skipped" and the Critic moves on. Framework dogfoods the schema (every chunk's evidence carries the F4a fields) but doesn't enforce it on itself yet — flag stays off until v1.5 sweep.

**Test coverage:** 1126 passing (+13 over Chunk 08's 1113). New `TestVerifyCoverageSubcommand` in `tests/test_product_hook.py` — 13 tests on real-git mini-repo fixtures (no mocking, matching `test_reference_verifier.py` style since the subcommand's contract is its git interaction): skip-default-false, skip-key-absent, indented-key-doesn't-satisfy-flag, missing-evidence, legacy-evidence-no-verifier, invalid-schema, all-covered-clean, missing-at-referenced-floor-language, missing-at-executed-stronger-language (asserts floor language is NOT emitted at executed level — the per-level distinction is the chunk's reason for existing), multiple-files-listed-individually, untracked-treated-as-missing, no-changes-clean, unresolvable-base-errors. Token-budget tests in `tests/test_v5_methodology.py` bumped: building.md 4275 → 4375 (~75 tokens for the new paragraph after aggressive trimming), SKILL.md 3250 → 3325 (~50 tokens for the Goal-1 bullet — explicitly drawing from the F4 protocol-additions budget the Chunk 00 trim-pass reserved). Both bump-comments instruct future readers to prefer trimming over another bump.

**Dogfooding:** `python3 tools/product-hook verify-coverage` against this chunk's own diff reports `skipped: coverage_required is false (default in v1.4)` — by design (framework holds off until v1.5 to keep template parity with downstream products that need a migration window). The verifier still runs and `.test-evidence.json` carries the F4a fields, so the day enforcement flips on, this chunk is already covered.

**Critic chunk review:** 0 BLOCKING, 0 WARNINGs, 1 NOTE (deferred to backlog — `_read_bool_yaml_key` duplicates the column-0 scanner in `views.py::is_views_enabled`; intentional inline duplication is documented, extraction earns a backlog candidacy when a third caller appears).

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
