# Change Log — Prawduct Framework

<!-- Append new entries at the top. Each entry is a ## section.
     Historical entries (pre-2026-03-22) are in project-state.yaml under change_log_history. -->

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
