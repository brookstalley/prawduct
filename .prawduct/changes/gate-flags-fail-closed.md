---
schema: 1
type: fix
scope: gate-flags-fail-closed
date: 2026-11-15
title: A project-state.yaml that cannot be read no longer switches your opt-in gates off
closes: [brookstalley/prawduct#777]
---
`coverage_required` and `operator_verification_required` are opt-in: a missing file or a missing
key means the gate is off, and that has not changed. But a `project-state.yaml` that exists and
cannot be read (no permission, or not valid UTF-8) used to read as "off" too, so a repo that had
turned a gate on lost it silently, with exit 0 and no message.

`check-operator-verification` now refuses in that case with exit 3 and names the file. An
unreadable or non-UTF-8 `operator-verification.md` is handled the same way instead of crashing
with a Python traceback: the check exits 3, and `verify-operator-verification` and
`accept-operator-verification` print an `error:` line and exit 1 without touching the file.

The shared reader is `core.read_bool_flag`, which reports `ok` or `unreadable`. `verify-coverage`
uses it too: with `coverage_required: true` and an unreadable state file it now prints an `error:`
line naming the file and exits 1, instead of skipping the gate. The older bool-only
`read_bool_yaml_key` and the hook's unused copy of it are gone.

## Consumer note
If `check-operator-verification` or `verify-coverage` starts failing with "cannot read
.prawduct/project-state.yaml", fix that file's permissions or encoding (it must be UTF-8). The gate
was not being enforced before; now it says so.
