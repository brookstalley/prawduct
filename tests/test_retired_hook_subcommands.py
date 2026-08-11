"""Regression pins for subcommands retired from `bin/prawduct-hook` while a
shipped `hooks.json` still registers them.

v3.3.2 deleted ``build-index`` and ``user-prompt-submit`` from both the binary
and ``hooks/hooks.json`` in one commit. Self-consistent within that version —
and still broken in the field, because the harness pins a plugin version **per
project** and updates those pins lazily, so a repo runs an old registration
against a new binary for one update cycle. During that window every product repo
printed usage text and exited 1 on session start (``SessionStart:clear hook
error``) and on every prompt.

The rule these tests pin: **a subcommand any shipped `hooks.json` registers stays
dispatchable when it is retired** — inert, exit 0, per ``docs/norms.md``'s
deprecation norm. Removal defers to a major, by which point no supported install
still registers it.

Silence is load-bearing and is the second thing pinned here. Both hook events
inject a hook's **stdout** into the model's context on exit 0 — SessionStart
prepends it to the session, UserPromptSubmit prepends it to the turn — so a
deprecation notice printed the ordinary way would be read as instruction on every
turn. That is why these two are silent where ``regen-views`` and ``stamp-merged``
warn: those are called by people who can act on the warning, these by a stale
registration that the next plugin update replaces on its own.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent / "plugin"
_HOOK = _ROOT / "bin" / "prawduct-hook"
_HOOKS_JSON = _ROOT / "hooks" / "hooks.json"

# Retired at v3.3.2. Frozen on purpose: this list is the record of what a
# pre-3.3.2 hooks.json invokes, so it must not be re-derived from the current
# hooks.json — which no longer mentions either name, and would make the whole
# file vacuous. Add to it whenever a hook-registered subcommand is retired;
# entries leave only at a major.
RETIRED_HOOK_SUBCOMMANDS = ("build-index", "user-prompt-submit")


def _run(command: str, *args: str, stdin: str = "") -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(_HOOK), command, *args],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
    )


@pytest.mark.parametrize("command", RETIRED_HOOK_SUBCOMMANDS)
class TestRetiredHookSubcommandsStayCallable:
    def test_exits_zero(self, command: str) -> None:
        """The regression itself: a pre-3.3.2 hooks.json invokes this, and a
        non-zero exit surfaces to the user as a hook error every session."""
        proc = _run(command)
        assert proc.returncode == 0, (
            f"{command} exited {proc.returncode}; a retired hook subcommand must "
            f"stay inert-callable. stderr: {proc.stderr[:400]}"
        )

    def test_prints_nothing_to_stdout(self, command: str) -> None:
        """Hook stdout is injected into the model's context on exit 0."""
        assert _run(command).stdout == ""

    def test_prints_nothing_to_stderr(self, command: str) -> None:
        """No audience: the caller is a stale registration, not a person. A
        notice here would be the session-start noise this fix removed, one
        severity quieter."""
        assert _run(command).stderr == ""

    def test_never_prints_usage(self, command: str) -> None:
        """The exact field symptom — a usage dump from the unknown-command
        branch of the dispatcher — on either stream."""
        proc = _run(command)
        assert "Usage: prawduct-hook" not in (proc.stdout + proc.stderr)

    def test_tolerates_unknown_flags(self, command: str) -> None:
        """An older registration may pass flags this binary never had. A command
        that does nothing cannot be misused by them."""
        proc = _run(command, "--force", "--some-flag-that-never-existed")
        assert proc.returncode == 0
        assert proc.stdout == ""

    def test_tolerates_a_hook_payload_on_stdin(self, command: str) -> None:
        """Both events write JSON to stdin; user-prompt-submit's carries the
        prompt. Neither reads it, and neither may choke on it."""
        payload = json.dumps(
            {"session_id": "s1", "prompt": "hello", "transcript_path": "/tmp/t.jsonl"}
        )
        proc = _run(command, stdin=payload)
        assert proc.returncode == 0
        assert proc.stdout == ""


class TestUsageAdvertisesTheRetiredCommands:
    def test_listed_as_deprecated_and_inert(self) -> None:
        """Same shape as regen-views/stamp-merged, so `prawduct-hook` with no
        args tells a reader these exist and do nothing."""
        usage = subprocess.run(
            ["python3", str(_HOOK)], capture_output=True, text=True, timeout=30
        ).stderr
        for command in RETIRED_HOOK_SUBCOMMANDS:
            assert f"{command} [deprecated, inert]" in usage


class TestEveryRegisteredHookCommandDispatches:
    """The forward-looking guard: the next retirement of a hook-registered
    subcommand fails here rather than in the field.

    Reads the commands out of the shipped hooks.json and asserts each one
    dispatches — i.e. does not fall through to the usage branch. Deliberately
    NOT a behavior assertion: `stop` and `clear` do real work, so this checks
    only that the dispatcher knows the name.
    """

    @staticmethod
    def _registered_commands() -> set[str]:
        config = json.loads(_HOOKS_JSON.read_text())
        found: set[str] = set()
        for groups in config["hooks"].values():
            for group in groups:
                for hook in group.get("hooks", []):
                    match = re.search(r'prawduct-hook"?\s+([a-z][a-z-]*)', hook["command"])
                    if match:
                        found.add(match.group(1))
        return found

    def test_hooks_json_registers_something(self) -> None:
        """Guards the parse: a regex that silently matched nothing would make
        the test below vacuously green."""
        assert self._registered_commands() >= {"clear", "stop", "subagent-stop"}

    def test_each_registered_command_is_known_to_the_dispatcher(self) -> None:
        source = _HOOK.read_text()
        for command in self._registered_commands():
            assert f'command == "{command}"' in source, (
                f"hooks.json registers `{command}` but the dispatcher has no "
                f"branch for it — the harness would print usage and exit 1"
            )

    def test_retired_commands_are_still_known_to_the_dispatcher(self) -> None:
        """Retired names leave hooks.json but must stay in the dispatcher until
        a major — older registrations still call them."""
        source = _HOOK.read_text()
        for command in RETIRED_HOOK_SUBCOMMANDS:
            assert f'command == "{command}"' in source

    def test_retired_commands_are_no_longer_registered(self) -> None:
        """The other half: keeping them callable must not resurrect the hooks.
        v3.3.2 was right to unregister them; only the deletion was wrong."""
        assert self._registered_commands().isdisjoint(RETIRED_HOOK_SUBCOMMANDS)
