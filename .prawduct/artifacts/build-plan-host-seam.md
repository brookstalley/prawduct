---
artifact: build-plan
version: 2
scope: host-seam
branch: feature/1037-host-seam
base: develop
working-branches: []
last_validated: 2026-10-26
depends_on:
  - brookstalley/prawduct#1037
  - documentation/issues/928-requirements.md
governed_by:
  - .prawduct/artifacts/architecture.md
  - .prawduct/artifacts/api-contract.md
  - .prawduct/artifacts/nonfunctional-requirements.md
partition: serial — Chunk 02 refactors exactly the entry points Chunk 01's goldens pin, and Chunk 03's parity sweep runs Chunk 02's code
---

# Build Plan — One host seam for hook payloads and roots (#1037)

## Goals

**Response taken:** Proceed, citing #1037. The issue states the problem, the module shape, host
selection (marked Decided), the callers, acceptance boxes and a scope-out. The owner asked on
2026-10-26 to build it "so we can test with it and make sure it works in our local repos", which
adds a verification goal: the refactored hooks behave identically on the owner's real onboarded
repos, not only on fixtures.

**Product:** #928's portable host adapters. This item is the seam a Codex adapter (#1038,
assigned to an outside contributor) builds on; Claude behaviour must not move (R-3), and every
host-shaped read and write must live in one module (R-2).

**Architecture:** `plugin/lib/host.py` imports nothing from `lib`, so `banner.py` and `digest.py`
can load it file-relative before `lib` is on the path, and `prawduct-hook`'s pre-dispatch code can
use it without the `lib/` ImportError fallback it needs for every other module. Must stay
possible: a second host implementation behind `PRAWDUCT_HOST` with no caller changes.

**Constraints:** byte-identical stdout, stderr and exit code for the SessionStart, Stop and
SubagentStop entry points (R-3, the golden test lands first, in its own commit). `hooks.json` is
unchanged (scope-out).

**Inferences and deviations (flagged for the boundary review):**
- *Session boundary is not in `HostEvent`.* The issue defines a `session_boundary` field that the
  Claude implementation never fills and nothing reads; core.md's rule is that a channel produced
  and never consumed is a defect. The Codex spike (#1038) adds the field together with its first
  reader, which is additive. Inferred; owner can veto.
- *`background_tasks` is normalized, not passed through.* `gates.background_tasks_in_flight` reads
  `agent_type`, `name`, `command` … inside each task entry, which is Claude's payload shape too.
  `HostEvent.background_tasks` is therefore a list of `<type>:<ident>` labels (`None` when the
  payload had no such key), and the label policy moves into `host`. The gate's ladder is
  unchanged: no labels, no deferral.
- *Null versus absent* is kept by `HostEvent.fields_present` (the payload keys present), not a
  sentinel value, so `last_assistant_message` stays `str | None` for every reader.
- *Config roots.* Three readers want two different answers: the primary config home (banner,
  plugin activation) and every candidate home (stranded work's transcript and plugin-cache
  scan). `host` exposes `config_home()` and `config_roots()`; the existence filtering and
  de-duplication stay in `stranded_work`, because they are that probe's policy, not the host's.
- *Unknown `PRAWDUCT_HOST`* is refused per event by the hook that receives it: `stop` blocks
  (exit 2, reason names the variable), as the issue decides; `subagent-stop`, `clear`, `banner.py`
  and `digest.py` print a one-line NOTE naming the variable and do nothing else, because none of
  them can block and each must never break session start or a subagent (`architecture.md`
  "Authority fails closed; advice fails soft").
- *Exit 2 scope.* "`block()` is the only writer of exit 2" is read as the hook *block* response.
  Exit 2 is also the CLI's usage-error code (`_reject_unknown_args`, `_check_argument_shape`), which
  is not a host response shape and stays where it is.
- *Plain-stdout briefing.* `clear --session-start` prints its briefing as plain stdout, which
  Claude injects as context. The issue's response-shape list does not name it, so it is not routed
  here; #1038's briefing work decides its shape. Noted on #1037 at the boundary.

**Decisions made mid-build:**
- Chunk 01: the goldens normalize five exact run facts, not two: the temp path, plugin root, plugin
  version, the checkout's `ref@sha[+dirty]`, and the digest text. No output carries a timestamp. The
  test's docstring lists them. Settled by "do it right": without `+dirty`, every run during
  development fails; without the version, a release bump rewrites every golden. (Not settled by
  the goals; the issue named two normalizations.)
- Chunk 01: a session-start case with a populated `CLAUDE_CONFIG_DIR` was added and recorded before
  the refactor (Critic O-4), because the config readers otherwise only ever saw an empty home. Its
  control showed the worktree reading active from its fresh reflog, so the reflog is backdated and
  the transcript is the only recent signal.
- Chunk 02: test fixtures that copy the hook binary into a fake plugin tree now copy `lib/host.py`
  beside it, as every real plugin tree has. A fallback for a missing seam was rejected: it would
  have to read the host's variables outside the seam. Settled by R-2.
- Chunk 02: `banner.managed_plugin_home` now expands `~` in `CLAUDE_CONFIG_DIR`, like the other two
  readers already did, because all three now ask `host.config_home`. The only visible difference
  is for a literal `~` in the variable. Settled by "one home".
  `plugin_activation.DEFAULT_PLUGINS_FILE` is gone: it was a second spelling of `~/.claude`.
- Chunk 02: `test_short_plan_deferral`'s exit pin matched the literal `return 2`. It is renegotiated
  in its docstring: the blocking exit returns what `host.block` gave, and it still has to deliver
  the advisories. The gate tests that passed raw dicts now route them through `host.read_event`,
  the path production takes, with every assertion unchanged.

**Level:** High — the sites are enumerated by grep, the behaviour is pinned by goldens before any
refactor, and no foreign API is touched.

## Norm reconciliation (`governed_by`)

- `architecture.md` "Every fact has one home" — **conforms**; this plan exists to give host reads
  one home.
- `architecture.md` "Authority fails closed; advice fails soft" — **conforms**; an unknown host
  blocks the Stop gate (authority) and only notes on SessionStart/SubagentStop (advice).
- `architecture.md` "Goals and verification bind; prescribed method is advice" — **conforms**; the
  deviations above are recorded with their reasons.
- `architecture.md` reviewer-never-mutates, local-first, writes-only-`.prawduct/`,
  language-agnostic, guides-not-implements — **inapplicable**: no reviewer path, network, repo
  write, language dispatch or product code changes.
- `api-contract.md` "Exit codes are the contract" and "Additive-first evolution" — **conforms**: exit
  2 keeps its meaning on Stop, and `PRAWDUCT_HOST` is a new, additive variable.
- `api-contract.md` whole-surface semver — **inapplicable**: no version bump in this unit.
- `nonfunctional-requirements.md` "Review wall-clock is P0" — **conforms**: the Stop path gains one
  dict normalization and no subprocess.
- `nonfunctional-requirements.md` proportionality, state growth, stage-keyed rigor — **inapplicable**:
  no new control, state file or review mode.

## Build Chunks

### Chunk 01: Golden output of the hook entry points

- **Description:** Pin today's exact stdout, stderr and exit code of every hook entry point before
  anything moves, so Chunk 02 is checked against recorded bytes, not memory.
- **Depends on:** none
- **Deliverables:**
  - new `tests/test_host_seam_golden.py` and its recorded goldens under new
    `tests/fixtures/host_seam_golden/`, regenerated only by an explicit flag.
  - Cases: `banner.py`, `digest.py`, `clear --session-start`, `clear --session-start --brief-only`,
    `stop` (clean; blocking; advisory at exit 0 — each with and without `background_tasks` and
    `last_assistant_message`), `subagent-stop` (reviewer and non-reviewer `agent_type`).
  - The test names its only normalizations: the temp path and timestamps.
- **Tests:** the file itself; it passes on develop's code.
- **Acceptance criteria:** goldens pass on this commit; red-verified by perturbing one emitted
  byte (a test that cannot fail proves nothing).
- **Critic mode:** chunk
- **Done when:**
  1. Goldens pass and the red check has been seen to fail.
  2. `/prawduct:critic` run and blocking findings resolved.
  3. Committed alone, before any refactor.

### Chunk 02: `host.py` and every caller routed through it

- **Description:** One module owns host payload reads, `CLAUDE_*` root reads and hook response
  writes; every site routes through it; an unknown `PRAWDUCT_HOST` fails closed.
- **Depends on:** Chunk 01
- **Deliverables:**
  - new `plugin/lib/host.py`: `HostEvent`, `read_event`, `plugin_root`, `project_dir_hint`,
    `config_home`, `config_roots`, `emit_session_context`, `emit_stop_advisory`, `block`, and the
    `PRAWDUCT_HOST` selection.
  - `plugin/bin/prawduct-hook`: project-dir and plugin-root resolution, the worktree-redirect
    note, `cmd_subagent_stop`, `cmd_stop` (event read, advisory delivery, the block exit).
  - `plugin/lib/gates.py`: the payload readers take a `HostEvent`.
  - `plugin/hooks/banner.py`, `plugin/hooks/digest.py`, `plugin/lib/plugin_activation.py`,
    `plugin/lib/stranded_work.py`: root reads through `host`.
  - `documentation/issues/928-requirements.md` § "Next step": R-8(a) satisfied by the posted
    receipt; this item, then #1038, are next.
- **Tests:**
  - Chunk 01's goldens pass unchanged.
  - new `tests/test_host_seam.py`: the one-place grep (R-2) over `plugin/bin`, `plugin/lib`,
    `plugin/hooks`, red-verified by restoring one site; `read_event` units (null vs absent message,
    absent `background_tasks`, `{}`, non-string `agent_type`); `PRAWDUCT_HOST=bogus` makes `stop`
    exit 2 naming the variable, and makes the SessionStart/SubagentStop hooks note and exit 0.
  - Existing gate tests move from raw dicts to `host.read_event(...)` with unchanged assertions.
- **Acceptance criteria:** #1037's acceptance boxes.
- **Done when:**
  1. Chunk-scoped tests pass (the goldens, the seam tests, the touched gate tests).
  2. `/prawduct:critic` run and blocking findings resolved.
  3. Committed.

### Chunk 03: Parity on the owner's repos, and the change record

- **Description:** Prove the seam changes nothing where it runs for real: every local onboarded
  repo, copied, run through develop's plugin and this branch's plugin with the same payloads,
  outputs compared. Then the change fragment.
- **Depends on:** Chunk 02
- **Deliverables:**
  - The parity sweep's script and its result, committed as a runnable script so the claim cites a
    command (authoring.md: a spike's numbers stay falsifiable only as a script).
  - `.prawduct/changes/host-seam.md` written.
- **Tests:** the declared suite, recorded green at this boundary.
- **Acceptance criteria:** every repo in the sweep matches byte-for-byte after path normalization,
  or each difference is explained; the fragment validates.
- **Type:** cumulative-final
- **Done when:**
  1. Declared suite recorded green.
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved.

## Verification Strategy

Goldens pin fixture behaviour (Chunk 01). Chunk 03's sweep pins real-repo behaviour: each repo is
copied copy-on-write into the scratchpad so the Stop gate's evidence writes never reach the real
repo, and both plugin trees run against identical copies. After the PR, the owner can point their
live plugin checkout at the branch to run real sessions on it.

## Governance Checkpoints

- After Chunk 01: goldens are the contract; any golden change in Chunk 02 is a regression, not an
  update.
- Chunk 03 (cumulative): full-bundle review, the parity result, and the deviations above shown to
  the owner.
