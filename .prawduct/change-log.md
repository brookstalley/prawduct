# Change Log — Prawduct Framework

<!-- Append new entries at the top. Each entry is a ## section.
     Historical entries (pre-2026-03-22) are in project-state.yaml under change_log_history. -->

## 2026-04-13: Property-based testing guidance + template drift advisory system (v1.4.0)

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
