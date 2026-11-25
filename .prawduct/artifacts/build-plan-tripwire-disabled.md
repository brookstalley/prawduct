---
artifact: build-plan
version: 2
scope: tripwire-disabled
branch: fix/tripwire-disabled
base: develop
working-branches: []
last_validated: 2026-11-25
depends_on:
  - artifact: architecture
  - artifact: api-contract
governed_by:
  - artifact: architecture
    dispositions:
      - "an independent reviewer never mutates the session it reviews → inapplicable because this changes an activation check and a project hook, which no reviewer runs"
      - "authority fails closed; advice fails soft → conforms: the tripwire and check-plugin-active are advice; an unreadable settings file is passed over, and a non-boolean value never reads as disabled, so neither claims governance is off on a guess"
      - "local-first: process-spawn, atomic files, the git object database → conforms: reads local settings files only"
      - "the plugin writes nothing into a governed repo but its own state → conforms: the tripwire stays the one hook in `.claude/settings.json`; this changes its text, rewritten only by `install-tripwire --apply`"
      - "never specific to Python → conforms: the hook's python3 dependency is unchanged and still degrades to the could-not-verify line"
      - "prawduct guides and reviews; it never implements → inapplicable because this is framework code"
      - "goals and verification bind; prescribed method is advice → conforms: the report's repro and the agreement test bind; the chunk route is a forecast"
      - "every fact has one home → conforms: the enabledPlugins rule lives in `plugin_activation.disabled_by` and the managed directories in `MANAGED_SETTINGS_DIR_BY_PLATFORM` (one directory per OS); the tripwire's inline copy is the documented exception (it runs when the plugin does not) and a test holds it to the home"
  - artifact: api-contract
    dispositions:
      - "whole-surface semantic versioning; CLI subcommands carry no per-subcommand version → conforms: a new status value on an existing subcommand, and a changed tripwire hook text that `install-tripwire --apply` replaces; patch-level within the release's own tier"
      - "exit codes are the contract → conforms: `disabled` exits 1, beside `inactive`, an existing code meaning 'will not load'; no code changes meaning"
      - "additive-first evolution → conforms: a new `status` value and a new `disabled_by` key in `--json`; existing values and keys are unchanged"
partition: serial — one chunk
---

## Goals

**Response taken:** Proceed, citing #1246. The owner ruled on 2026-11-25 that it ships in the next
release (`.prawduct/owner-rulings.md`). The report defines success: an installed plugin set to
`false` in the repo's `enabledPlugins` makes the tripwire speak.

**Product:** The tripwire exists to announce a session that runs ungoverned. A plugin switched off
by `enabledPlugins` is that case, and the tripwire was silent on it.

**Architecture:** `plugin_activation.disabled_by` resolves `enabledPlugins` key by key over the
documented settings precedence (code.claude.com plugins/loading, "find where a plugin is enabled",
read 2026-11-25). `plugin_activation_status` returns `disabled` for an installed plugin it names;
the tripwire's inline verdict carries the same rule.

**Decisions made (inferred, mine, open for the owner at the boundary review):**
- *The tripwire's tone for `disabled`:* its own line, naming the file, telling the agent to work
  without governance if the opt-out was deliberate and to tell the user otherwise. Not the
  not-installed accusation, because `/prawduct:repo-disable` writes this setting on purpose.
- *The class, not the instance:* `check-plugin-active` had the same blind spot, so the rule has one
  home in `plugin_activation` and both callers use it. `disabled` exits 1 like `inactive`.
- *Precedence edge cases:* a non-boolean value never reads as disabled; an unreadable settings
  file is passed over. A `--settings` file, and managed policy from MDM or a remote source, cannot
  be seen by a file read and are not consulted.

**Decisions made mid-build:**
- Boundary review (rev-20261125T230216Z-7af05777), checked against code.claude.com
  managed-settings (read 2026-11-25): Claude Code merges `managed-settings.json` first and each
  `managed-settings.d/*.json` over it in name order, later winning, ignoring hidden and
  non-`.json` files, and reads only its own OS's directory. Both copies had the managed tier
  backwards and read both OS directories. Now: drop-ins in reverse name order, then the base; one
  directory per OS (`sys.platform` in the lib, `uname` in the shell, held equal by a test that runs
  every shell branch). The inline copy reads settings as UTF-8, as the lib does.
- The disabled line tells the agent to say so in one line and let the user decide, since the
  agent cannot judge intent at session start, and carries the `--plugin-dir` escape the
  not-installed line has. Doctor grades `disabled` as degraded (the plugin loaded another way to run
  doctor at all), and every later step of the onboard, doctor and migrate skills names it.

## Build Chunks

### Chunk 01: A plugin switched off by enabledPlugins reads as disabled

- **Description:** The tripwire and `check-plugin-active` say when an installed plugin is switched off
  for the repo, naming the settings file.
- **Depends on:** none
- **Deliverables:** `plugin/lib/plugin_activation.py` (`settings_sources`, `disabled_by`,
  `DISABLED`, `MANAGED_SETTINGS_DIR_BY_PLATFORM` (one directory per OS), the report wording); `plugin/lib/unloaded_tripwire.py` (the
  inline rule, `DISABLED_MESSAGE`); `plugin/bin/prawduct-hook` (exit 1); the onboard, doctor and
  migrate skills; `.prawduct/artifacts/api-contract.md`; `tests/test_plugin_activation.py`,
  `tests/test_unloaded_tripwire.py`
- **Tests:** through a real shell — the report's repro, each precedence pair, an unreadable file,
  not-installed-and-disabled; the inline verdict with a managed directory; the agreement of the
  inline verdict with `plugin_activation_status` over every case, installed and not. Unit — the
  precedence walk, report wording per context, the CLI's exit 1 and `--json` status.
- **Acceptance criteria:** the report's repro prints the disabled line naming the file; a `true`
  in the same file is silent
- **Type:** cumulative-final
- **Done when:**
  1. Acceptance criteria met and tests pass
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved
