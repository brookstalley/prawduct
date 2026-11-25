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
      - "every fact has one home → conforms: the enabledPlugins rule lives in `plugin_activation.disabled_by` and the managed directories in `MANAGED_SETTINGS_DIRS`; the tripwire's inline copy is the documented exception (it runs when the plugin does not) and a test holds it to the home"
  - artifact: api-contract
    dispositions:
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
  file is passed over; managed drop-ins are read in name order after the managed file. A
  `--settings` file cannot be seen and is not consulted.

## Build Chunks

### Chunk 01: A plugin switched off by enabledPlugins reads as disabled

- **Description:** The tripwire and `check-plugin-active` say when an installed plugin is switched off
  for the repo, naming the settings file.
- **Depends on:** none
- **Deliverables:** `plugin/lib/plugin_activation.py` (`settings_sources`, `disabled_by`,
  `DISABLED`, `MANAGED_SETTINGS_DIRS`, the report wording); `plugin/lib/unloaded_tripwire.py` (the
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
