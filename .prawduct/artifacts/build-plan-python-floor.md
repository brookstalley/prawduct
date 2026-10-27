---
artifact: build-plan
version: 2
scope: python-floor
branch: feature/1097-python-floor
base: develop
working-branches: []
last_validated: 2026-10-27
depends_on:
  - brookstalley/prawduct#1097
governed_by:
  - .prawduct/artifacts/architecture.md
  - .prawduct/artifacts/api-contract.md
  - .prawduct/artifacts/data-model.md
  - .prawduct/artifacts/nonfunctional-requirements.md
partition: serial — Chunk 02 raises the floor that Chunk 01's launcher makes survivable, and must not land without it
---

# Build Plan — Python 3.14 floor; entry points find a qualifying interpreter (#1097)

## Goals

**Response taken:** Proceed, citing #1097 and the owner's ruling on 2026-10-27: "Let's do 3.14 and
bite the bullet. Testament cares about the venv to get timing so it does integrate even if we
don't import it." The issue comment of the same day records the consequences carried here.

**Problem:** prawduct declares `requires-python >= 3.10` and runs every hook under a bare
`python3`, which each consumer machine resolves on its own (pyenv shim, system, Homebrew). This is
prawduct's first floor change. Raising it to 3.14 without more would break hook startup wherever
`python3` resolves lower: about 20 of the 33 governed repos on the owner's machine, including nine
that are not Python projects. Claude Code treats a crashing hook as a non-blocking error, so the
gates would go silent rather than fail.

**Success:**
- Under any `python3` older than 3.14, every entry point (`prawduct-hook`, `test-reference-verify`,
  the `banner.py` and `digest.py` SessionStart hooks) finds a qualifying interpreter and re-runs
  itself under it, with no change to `hooks.json` or to the `python3 plugin/bin/prawduct-hook`
  invocations skills use.
- When none can be found, the failure is loud and attributed, never a traceback and never silent:
  the session-start banner tells the model to tell the user what to install; every other entry
  point prints one `ERROR:` line on stderr naming the interpreter it found, the floor and the fix.
- Each entry point still parses under old interpreters, so the check runs before anything newer
  is read; a test pins that with `ast.parse(..., feature_version=(3, 9))`.
- `requires-python`, the CI matrix and the release-verification workflow all say 3.14.
- `/prawduct:doctor` reports which interpreter the hooks run under and whether it was re-executed.
- The change record's consumer note says every governed machine needs a 3.14 reachable from the
  hooks, including repos that are not Python projects, and how to get one.

**Out of scope:** using 3.14-only features in `lib/` (allowed after this, not required by it);
installing a Python for the user; Windows-specific interpreter discovery (`py -3.14`).

**Inferences (flagged for the boundary review):**
- *Where the check lives.* A shared old-syntax module beside the entry points
  (`plugin/bin/_python_floor.py`), called at the top of each entry point. A shell launcher in
  `hooks.json` was the alternative; it would not cover the 51 `python3 plugin/bin/prawduct-hook`
  invocations in skills, or the `#!/usr/bin/env python3` shebang on PATH.
- *Discovery order.* `python3.14` up to `python3.19` on PATH, then `uv python find '>=3.14'` when uv
  exists. Each candidate is run once to confirm its version, because a pyenv shim named
  `python3.14` exists even where the selected pyenv version cannot serve it.
- *Only when run as a program.* Tests load `prawduct-hook` as a module; the check acts only under
  `__main__`, so an import never re-executes the test process.
- *Loop guard.* The re-exec sets `PRAWDUCT_PYTHON_REEXEC=1`; seeing it under an old interpreter
  fails loudly instead of re-executing again.
- *Stop does not block on a missing interpreter.* Exit 2 at Stop asks the model to fix something
  only the user can, which loops. It exits 1 (non-blocking, shown to the user) with the remedy.
- *Version tier.* Shipped inside 3.8.0 (minor), not a major: a machine with any 3.14 installed keeps
  working unchanged, and the consumer note names the requirement. The owner may override.
- *`tomllib` fallback.* The 3.10 branch in `release_verification` that reports "unverifiable" when
  `tomllib` is missing becomes dead and is removed with its test.

**Decisions made mid-build:**
- Chunk 01: the undeclared-suite pytest fallback (`test-evidence record` with no `test_command`)
  ran `sys.executable -m pytest`. After a re-exec that is the qualifying interpreter the floor
  found, which may lack the project's packages or pytest itself; 64 existing runtime tests went
  red on exactly that on this machine. The re-exec now carries the invoked interpreter in
  `PRAWDUCT_PYTHON_REEXEC`, and the fallback runs pytest under it. The two other
  `sys.executable` launches start prawduct's own entry points, where the qualifying interpreter
  is right. Settled by "do it right": the fallback's contract is "the hook shares the project's
  environment", and the invoked `python3` is that environment.
- Chunk 01: 49 test launches across 31 files started the hook with a bare `python3`, many under
  a stripped `PATH=/usr/bin:/bin`, so they had been running the hook on the machine's system
  interpreter — the de-facto floor of about 3.9. Under the 3.14 floor that is correctly refused,
  so those launches now use `sys.executable`, the suite's own interpreter. What each test asserts
  is unchanged; which interpreter a hook runs under is `tests/test_python_floor.py`'s subject,
  including one launch through a real older `python3`. The suite now needs a 3.14 interpreter,
  as `requires-python` will say (Chunk 02); the local `.venv` was rebuilt on 3.14.
- Chunk 01: ruff's E402 on the imports after the floor check in `banner.py`/`digest.py` is
  waived per line with the reason; the plugin's lint count is back to its baseline.

## Norm reconciliation (`governed_by`)

- `architecture.md` "Authority fails closed; advice fails soft" — **conforms, with the Stop case
  argued**. With no qualifying interpreter no gate can run at all; the closed answer would be an
  exit-2 block the agent cannot discharge. The loud non-blocking error is the attributable failure
  the architecture asks for, and the session-start notice puts it in front of the user.
- `architecture.md` "zero external dependencies" / stdlib-only — **conforms**. uv is used only
  when already installed, to find an interpreter; nothing is imported.
- `architecture.md`, other norms (reviewer never mutates, local-first, writes only `.prawduct/`,
  guides-not-implements, goals bind) — **inapplicable**: no reviewer path, network call or repo
  write.
- `architecture.md` "language-agnostic" — **conforms, at a cost recorded in the consumer note**:
  a non-Python repo now needs a 3.14 interpreter on the machine, not only some `python3`.
- `api-contract.md` "Exit codes are the contract" and "Additive-first evolution" — **conforms**.
  No subcommand changes meaning; the below-floor failure is a new `ERROR:` on stderr with exit 1,
  the generic failure every subcommand already uses.
- `data-model.md` — **inapplicable**: no fact kind or schema changes.
- `nonfunctional-requirements.md` "Review wall-clock is P0" — **conforms**. On a 3.14 `python3`
  the check is one version comparison. Below it, each invocation pays candidate probes and one
  re-exec (tens of milliseconds), which the consumer note names.

## Build Chunks

### Chunk 01: Entry points find a qualifying interpreter

- **Description:** A shared old-syntax floor check that re-executes the entry point under a
  qualifying interpreter, or fails loudly by role.
- **Depends on:** none
- **Deliverables:**
  - new `plugin/bin/_python_floor.py`: the floor, discovery, re-exec, loop guard and per-role
    failure messages.
  - `plugin/bin/prawduct-hook`, `plugin/bin/test-reference-verify`, `plugin/hooks/banner.py`,
    `plugin/hooks/digest.py`: call the check before any other import.
- **Tests:** new `tests/test_python_floor.py`:
  - every entry point and `_python_floor.py` parse at `feature_version=(3, 9)`;
  - discovery skips a candidate whose probe fails (the pyenv-shim case) and takes the next;
  - re-exec argv and environment carry the entry point, its arguments and the loop guard;
  - the loop guard fails loudly instead of re-executing;
  - each role's failure output (banner stdout notice; stderr `ERROR:` line; exit codes);
  - imported as a module, the check does nothing;
  - integration, where an older `python3` exists on the machine: `prawduct-hook --help` under it
    succeeds by re-executing (skipped with a named reason where none exists).
- **Acceptance criteria:** the first three success lines above.
- **Done when:**
  1. Tests pass.
  2. Committed.

### Chunk 02: The floor is 3.14 everywhere it is declared

- **Description:** Raise the declared floor and make every surface that states it agree.
- **Depends on:** Chunk 01
- **Deliverables:**
  - `pyproject.toml` `requires-python = ">=3.14"`; `.github/workflows/tests.yml` matrix `["3.14"]`
    and its comments; `.github/workflows/verify-release.yml` gets a 3.14 interpreter and its
    comment says why.
  - `plugin/lib/release_verification.py`: the `tomllib`-missing branch and its test removed.
  - `README.md` requirements line; `/prawduct:doctor` reports the hooks' interpreter.
  - Sweep: every surface stating the floor or "Python 3" as the requirement agrees.
- **Tests:** `tests/preferences/test_ci_workflow_conventions.py` stays green against the new
  floor; the doctor report's interpreter line is pinned.
- **Acceptance criteria:** success lines four and five.
- **Done when:**
  1. Tests pass.
  2. Committed.

### Chunk 03: Change record

- **Description:** The fragment for this unit, with the consumer note.
- **Depends on:** Chunk 02
- **Deliverables:**
  - `.prawduct/changes/python-floor.md`
- **Tests:** none: prose.
- **Acceptance criteria:** the fragment validates; the consumer note says what every machine needs
  and how to get it.
- **Type:** cumulative-final
- **Done when:**
  1. Declared suite recorded green.
  2. Committed, then `/prawduct:critic cumulative` run and blocking findings resolved.
