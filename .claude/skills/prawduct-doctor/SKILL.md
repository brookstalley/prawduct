---
description: Product repo setup, health check, and repair
argument-hint: "[target-path] [--name NAME]"
user-invocable: true
disable-model-invocation: false
allowed-tools: Bash(python3 *), Read, Glob
---

You are managing prawduct product repo setup and health. Detect the current context and take the appropriate action.

## Context Detection

1. Check if an explicit target path was provided as an argument
2. Check if the current directory has `.prawduct/` (is a product repo)
3. Check if `tools/prawduct-setup.py` exists locally (framework repo)

Then route:

| Context | Action |
|---|---|
| Explicit target path provided | **Onboard**: set up the target as a product repo |
| Current dir is a product repo (has `.prawduct/`) | **Health check**: validate and offer repair. If health is good, mention available per-feature migrations (`migrate --enable-coverage`, `migrate --enable-settings-layout`) when relevant. |
| User asks "enable coverage" / "turn on F4" / "stamp settings layout" / "run migrate-settings" / similar | **Migrate**: see Migrate Flow below |
| Current dir is the framework repo (has `tools/prawduct-setup.py`) and no target | Ask what the user wants to do |

## Onboard Flow (target path provided)

1. Confirm the target directory and product name with the user
2. Run: `python3 tools/prawduct-setup.py setup <target> --name "<name>" --json`
   - If running from a product repo, resolve the framework path first:
     check `.prawduct/sync-manifest.json` for `framework_source`, or use `PRAWDUCT_FRAMEWORK_DIR`, or try `../prawduct`
3. Parse the JSON result and report what was done
4. Tell the user: **"Open `<target>` in a new Claude Code session for governance to activate. Hooks and the session briefing won't fire until then."**

## Health Check Flow (current dir is a product repo)

1. Resolve the framework path from `.prawduct/sync-manifest.json` `framework_source`, or `PRAWDUCT_FRAMEWORK_DIR` env var, or sibling `../prawduct`
2. Run: `python3 <framework>/tools/prawduct-setup.py validate "$CLAUDE_PROJECT_DIR" --json`
3. Parse the JSON result and present findings:
   - **healthy**: "All checks pass. Your prawduct setup is healthy."
   - **degraded**: List warnings, explain implications, offer fixes
   - **broken**: List failures, recommend repair
4. If `needs_restart` is true: **"Restart Claude Code to pick up updated settings/CLAUDE.md."**
5. If framework is unreachable: advise setting `PRAWDUCT_FRAMEWORK_DIR` or cloning framework as `../prawduct`
6. If repair needed: offer to run `python3 <framework>/tools/prawduct-setup.py setup "$CLAUDE_PROJECT_DIR" --json`

## Migrate Flow (per-feature v1.4 opt-ins)

The `migrate` subcommand surfaces v1.4 features that require explicit user intent. Two flags exist; each requires its own invocation (the subcommand rejects multiple flags in one call).

### `--enable-coverage` (F4 — symbol-coverage enforcement)

Workflow commitment: once enabled, the Critic's Goal 1 BLOCKS on changed files missing from `.test-evidence.json`'s `changes_referenced`. Use when the user asks to "enable coverage", "turn on F4", "switch to executed coverage", or similar.

1. Resolve the framework path the same way as Health Check (manifest `framework_source`, env, sibling).
2. Confirm intent with the user — surface the BLOCKING consequence.
3. Run: `python3 <framework>/tools/prawduct-setup.py migrate --enable-coverage "$CLAUDE_PROJECT_DIR" --json`
4. Relay both `actions` (file mutations) and `notes` (deprecation + next-step guidance). The "next-PR consequence" note is the most important.
5. If notes mention legacy evidence shape, point the user at `python3 tools/test-reference-verify --merge-into .prawduct/.test-evidence.json` (Python floor) or stronger language-native tools for `coverage_level: executed`.

### `--enable-settings-layout` (F5 — canonical settings.json)

Mostly a signal operation: stamps `v1_4_settings_migrated: true` in the manifest as the explicit user opt-in for the canonical minimal `.claude/settings.json` layout. For products already on the minimal shape (single-line `python3 product-hook <event>` dispatches), the file mutation is a no-op; for older repos with v1/v3 markers, it runs an aggressive cleanup pass. v1.4.1's Critic surfaces a NOTE on products lacking this flag — running migrate now silences that NOTE in advance. Use when the user asks to "stamp settings layout", "run migrate-settings", "opt into the new settings", or similar.

1. Resolve the framework path the same way as Health Check.
2. Confirm intent — note this is mostly a no-op for products that have synced regularly, but the flag is the v1.4.1 NOTE quieting signal.
3. Run: `python3 <framework>/tools/prawduct-setup.py migrate --enable-settings-layout "$CLAUDE_PROJECT_DIR" --json`
4. Relay `actions` and `notes`. The "already on the canonical minimal layout" note is the common case and confirms the no-op outcome.

### `--force` (both migrations)

Re-runs the migration even when the manifest tracks it as complete. Use cases:
- `--enable-coverage --force`: re-surface evidence-shape NOTEs after wiring up a verifier.
- `--enable-settings-layout --force`: re-normalize settings.json after a hand-edit.

## Important Notes

- The `setup` subcommand auto-detects repo state (new, v1/v3/v4/v5) and routes to the correct action
- Setup is idempotent — running it twice produces no changes on the second run
- The `migrate` subcommand is one-shot per feature (tracked in `sync-manifest.json`) and idempotent without `--force`
- Hooks and governance only activate in the target's own Claude Code session, not the current one
- The `validate` subcommand makes no changes — it's read-only
