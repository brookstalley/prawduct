---
schema: 1
type: feature
scope: python-floor
date: 2026-10-27
title: prawduct needs Python 3.14, and its hooks find one when `python3` is older (#1097)
---
prawduct's first Python floor change: `requires-python` moves from 3.10 to 3.14, to share a floor
with testament, which needs the project's 3.14 environment to collect test timing.

Every hook and CLI entry point is started by a bare `python3`, which each machine and directory
resolves on its own. A hook that crashes on an old interpreter is a non-blocking error in Claude
Code, so raising the floor alone would have silenced governance rather than stopped it. So each
entry point (`prawduct-hook`, `test-reference-verify`, and the banner and digest SessionStart
hooks) now checks the floor before importing anything else. Below it, the entry point re-runs the
same command under a qualifying interpreter. It tries `python3.14` and newer names on PATH, probing
each one because a pyenv shim can name a version it cannot serve, then `uv python find`. When none
exists it fails loudly and never blocks. The session banner tells the agent to tell you what to
install. Every other entry point prints one `ERROR:` line naming the interpreter it found and the
fix. The Stop hook exits 1, because exit 2 would hand the agent a problem only you can fix, every
turn.

After a re-exec, `test-evidence record`'s pytest fallback (used when no `test_command` is declared)
still runs under the `python3` you invoked, not the interpreter found for the hook. The new
`prawduct-hook python-floor` reports the hooks' interpreter and any re-exec, and
`/prawduct:doctor` relays it as check 26. The CI matrix and the release-verification workflow run
3.14, and the `tomllib` fallback for 3.10 is gone.

## Consumer note
- **Every machine that opens a governed repo needs Python 3.14 or newer**, including repos that are
  not Python projects, because prawduct's hooks are Python. Install one so `python3.14` runs from the
  repo: `brew install python@3.14` or `uv python install 3.14`. Under pyenv, `pyenv install 3.14`
  is not enough where a `.python-version` pins an older version; also make 3.14 selectable there,
  e.g. `pyenv local <current> 3.14`. The error names any `python3.14` it found that would not run.
- Nothing else changes where `python3` already resolves to 3.14. Where it resolves lower, hooks
  re-run themselves under the 3.14 they find, at the cost of a probe and a re-exec per hook call.
  To avoid that, make `python3` resolve to 3.14 in the repo (for example a pyenv
  `.python-version`). `/prawduct:doctor` shows which case you are in.
- With no qualifying interpreter, the session opens with "PRAWDUCT GOVERNANCE IS OFF THIS
  SESSION", and no gate, review or briefing runs until one is installed and Claude Code restarts.
- If you record tests without a declared `test_command`, the pytest fallback still runs your
  invoked `python3`. Declaring `test_command` remains the robust choice.
