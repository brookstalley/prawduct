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
dispatchable when it is retired** — inert, exit 0, per the deprecation norm in
``.prawduct/artifacts/api-contract.md`` § Direction (additive-first evolution),
which also records why its v3.3.2 warrant was falsified. Removal defers to a
major, by which point no supported install still registers it.

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
import os
import re
import subprocess
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent / "plugin"
_HOOK = _ROOT / "bin" / "prawduct-hook"
_HOOKS_JSON = _ROOT / "hooks" / "hooks.json"

# Every command any SHIPPED hooks.json has ever registered. Append-only, and
# that property is the whole guard: v3.3.2's mistake was dropping a registration
# and its dispatcher branch in ONE commit, after which a set derived from the
# current hooks.json no longer mentions the name and asserts nothing. Deriving
# the retired set by SUBTRACTION from this constant means un-registering cannot
# shrink what is checked — the name simply moves from "registered" to "retired"
# and stays covered either way.
#
# Entries never leave before a major. Adding a NEW hook command without listing
# it here fails `test_no_registered_command_is_unrecorded` rather than silently
# widening the unguarded surface.
EVER_REGISTERED_HOOK_COMMANDS = frozenset(
    {
        # Currently registered (plugin/hooks/hooks.json).
        "clear",
        "stop",
        "subagent-stop",
        # Registered up to 3.3.1; retired at v3.3.2, inert since v3.3.3.
        "build-index",
        "user-prompt-submit",
    }
)


def _registered_commands() -> set[str]:
    """The commands the CURRENT hooks.json registers."""
    config = json.loads(_HOOKS_JSON.read_text())
    found: set[str] = set()
    for groups in config["hooks"].values():
        for group in groups:
            for hook in group.get("hooks", []):
                match = re.search(r'prawduct-hook"?\s+([a-z][a-z-]*)', hook["command"])
                if match:
                    found.add(match.group(1))
    return found


# Derived, not hand-maintained: whatever this checkout ships minus what it still
# registers. Sorted so parametrised test ids are stable.
RETIRED_HOOK_SUBCOMMANDS = tuple(
    sorted(EVER_REGISTERED_HOOK_COMMANDS - _registered_commands())
)


def _run(
    command: str,
    *args: str,
    stdin: str = "",
    project_dir: Path | None = None,
    plugin_root: Path | None = None,
) -> subprocess.CompletedProcess:
    """Run the hook with the plugin root pinned to this checkout.

    Pinning it matters for the silence assertions. `_check_binary_skew` runs
    before dispatch and, in a *framework checkout* whose `$CLAUDE_PLUGIN_ROOT`
    points elsewhere, prints a NOTE to stderr for any non-data-plane command —
    correct behavior belonging to a different subsystem, but it would make
    "this command prints nothing" pass or fail on the ambient environment
    instead of on the command. A test run from inside a Claude Code session
    inherits a `$CLAUDE_PLUGIN_ROOT` aimed at the installed plugin, which is
    exactly that skewed pairing; CI inherits none. Set it, and both agree.
    """
    env = dict(os.environ)
    env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root or _ROOT)
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return subprocess.run(
        ["python3", str(_HOOK), command, *args],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
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


@pytest.mark.parametrize("command", RETIRED_HOOK_SUBCOMMANDS)
class TestTheFieldScenarioIsSilent:
    """The exact shape that produced the bug: a product repo whose pinned plugin
    version is older than the binary the harness resolves.

    Distinct from the class above, which pins the command in isolation. Here the
    pre-dispatch guards run against a genuinely skewed `$CLAUDE_PLUGIN_ROOT`, and
    the assertion is that they stay out of the way: `_check_binary_skew` only
    speaks in a *framework checkout* (one carrying `plugin/.claude-plugin/`), so
    a product repo — every consumer of this fix — gets silence rather than a NOTE
    it can do nothing about.
    """

    @staticmethod
    def _product_repo(tmp_path: Path) -> Path:
        repo = tmp_path / "product"
        (repo / ".prawduct").mkdir(parents=True)
        subprocess.run(["git", "init", "-q"], cwd=str(repo), timeout=15, check=True)
        return repo

    def test_silent_and_zero_under_a_skewed_plugin_root(
        self, command: str, tmp_path: Path
    ) -> None:
        repo = self._product_repo(tmp_path)
        # A plugin root that is not this checkout — the field pairing.
        proc = _run(
            command,
            project_dir=repo,
            plugin_root=tmp_path / "some-other-installed-version",
        )
        assert proc.returncode == 0
        assert proc.stdout == ""
        assert proc.stderr == ""

    def test_the_skew_guard_is_reachable_and_still_exits_zero(
        self, command: str, tmp_path: Path
    ) -> None:
        """Paired with the test above, which would pass even if the guard could
        never fire — a product repo is exactly the shape `_check_binary_skew`
        stays quiet in, so on its own it proves silence without proving the
        fixture reaches anything.

        Here the same skew is put in a *framework checkout*, where the guard does
        speak. Two things follow, and both matter: the guard is genuinely
        reachable on this path (so the silence above is a property of the repo
        shape, not of a dead code path), and a retired command still exits 0 when
        it fires — a NOTE is advisory, and turning it into the exit 1 this whole
        fix removes would reintroduce the bug in the framework repo alone.
        """
        checkout = tmp_path / "framework"
        (checkout / "plugin" / ".claude-plugin").mkdir(parents=True)
        (checkout / "plugin" / ".claude-plugin" / "plugin.json").write_text(
            json.dumps({"name": "prawduct", "version": "9.9.9"}), encoding="utf-8"
        )
        (checkout / ".prawduct").mkdir()
        proc = _run(
            command,
            project_dir=checkout,
            plugin_root=tmp_path / "some-other-installed-version",
        )
        assert proc.returncode == 0
        assert proc.stdout == ""
        assert "plugin-binary-skew" in proc.stderr, (
            "the guard did not fire, so this fixture proves nothing about it"
        )
        assert "Usage: prawduct-hook" not in proc.stderr


class TestUsageAdvertisesTheRetiredCommands:
    def test_listed_as_deprecated_and_inert(self) -> None:
        """Same shape as regen-views/stamp-merged, so `prawduct-hook` with no
        args tells a reader these exist and do nothing."""
        usage = subprocess.run(
            ["python3", str(_HOOK)], capture_output=True, text=True, timeout=30
        ).stderr
        for command in RETIRED_HOOK_SUBCOMMANDS:
            assert f"{command} [deprecated, inert]" in usage


class TestEveryEverRegisteredCommandDispatches:
    """The forward-looking guard, and the reason it keys on `EVER_REGISTERED`
    rather than on the current hooks.json.

    A guard derived from the *current* registrations fires only when a command
    is deleted from the binary while still registered — which is not what
    happened. v3.3.2 removed the registration and the dispatcher branch in one
    commit, so a current-registrations set would no longer contain either name,
    assert nothing, stay green, and let the field break. Subtracting from an
    append-only constant closes that: un-registering moves a name from one
    checked bucket to the other instead of out of the check.
    """

    def test_hooks_json_registers_something(self) -> None:
        """Guards the parse: a regex that silently matched nothing would make
        the tests below vacuously green."""
        assert _registered_commands() >= {"clear", "stop", "subagent-stop"}

    def test_no_registered_command_is_unrecorded(self) -> None:
        """The forcing function. A new hook command must be added to
        `EVER_REGISTERED_HOOK_COMMANDS` when it is registered — otherwise it
        enters the shipped surface unguarded, and the day it is retired this
        file has no record that it was ever callable."""
        unrecorded = _registered_commands() - EVER_REGISTERED_HOOK_COMMANDS
        assert not unrecorded, (
            f"hooks.json registers {sorted(unrecorded)}, which is missing from "
            f"EVER_REGISTERED_HOOK_COMMANDS — add it there so the guard covers "
            f"it now and survives its eventual retirement"
        )

    def test_every_ever_registered_command_is_known_to_the_dispatcher(self) -> None:
        """The assertion that would have caught v3.3.2. Covers registered and
        retired names alike — a shipped registration exists for both."""
        source = _HOOK.read_text()
        for command in sorted(EVER_REGISTERED_HOOK_COMMANDS):
            assert f'command == "{command}"' in source, (
                f"a shipped hooks.json registers `{command}` but the dispatcher "
                f"has no branch for it — the harness prints usage and exits 1"
            )

    def test_the_retired_set_is_non_empty(self) -> None:
        """Pins that subtraction actually yields the retired pair. If it went
        empty — say hooks.json re-registered them — every parametrised class in
        this file would silently run zero cases."""
        assert set(RETIRED_HOOK_SUBCOMMANDS) == {"build-index", "user-prompt-submit"}

    def test_retired_commands_are_no_longer_registered(self) -> None:
        """The other half: keeping them callable must not resurrect the hooks.
        v3.3.2 was right to unregister them; only the deletion was wrong."""
        assert _registered_commands().isdisjoint(RETIRED_HOOK_SUBCOMMANDS)


class TestTheInertTierIsEphemeralWorktreeSafe:
    """`main()` runs `_check_ephemeral_worktree` BEFORE dispatch, and that guard
    is fail-closed: any command not positively known to be read-only counts as a
    write and is refused with exit 1 inside a disposable worktree.

    So membership in `_EPHEMERAL_SAFE_COMMANDS` is what makes "exits 0
    everywhere" true. Without it the two hook-invoked members reproduce the exact
    session-start hook error they were restored to remove, in the one environment
    prawduct itself creates. `regen-views` and `stamp-merged` carried the same
    gap and the same false docstring claim, so all four are pinned together —
    one classification, not four decisions.
    """

    INERT_TIER = ("build-index", "user-prompt-submit", "regen-views", "stamp-merged")

    def test_every_inert_command_is_ephemeral_safe(self) -> None:
        source = _HOOK.read_text()
        block = source.split("_EPHEMERAL_SAFE_COMMANDS = frozenset", 1)[1].split("})", 1)[0]
        for command in self.INERT_TIER:
            assert f'"{command}"' in block, (
                f"`{command}` is inert but missing from _EPHEMERAL_SAFE_COMMANDS "
                f"— the fail-closed guard would refuse it with exit 1 inside a "
                f"disposable worktree"
            )


# ---------------------------------------------------------------------------
# The general form of what this module pins by hand
# ---------------------------------------------------------------------------


class TestTheHandMaintainedSetHasAGeneralForm:
    """`EVER_REGISTERED_HOOK_COMMANDS` closed v3.3.2's instance for one surface.

    It generalises to no consumer: any other product with a recorded
    removal-defers-to-a-major policy gets no check at all, because the guard is
    this repo's own literal set of hook command names. `api_versioning_probes.
    conformance_departures` is the declaration-driven form — the same question
    asked of whatever surface an api-contract artifact DECLARES — and these tests
    are the join: the general leg, run over this repo's own incident, reports
    what the hand-maintained set reports.

    The two are not redundant. This module also pins that the retired commands
    stay *dispatchable and silent*, which is the remedy; the leg below only
    detects that the promise was broken.
    """

    _CONTRACT = (
        "# API Contract\n\n"
        "## Deprecation & Compatibility\n\n"
        "Retention: additive-first evolution; removal defers to a major.\n\n"
        "## Surface Inventory & Stability Tiers\n\n"
        "- `clear` — stable\n"
        "- `stop` — stable\n"
        "- `subagent-stop` — stable\n"
        "- `build-index` — deprecated\n"
        "- `user-prompt-submit` — deprecated\n"
    )

    def _departures(self, present):
        from lib import api_versioning_probes as av  # noqa: PLC0415

        return av.conformance_departures(self._CONTRACT, present)

    def test_the_v3_3_2_deletion_replays_as_two_departures(self):
        """The measured incident: both commands deleted from the binary in the
        same commit that dropped their registration. Every guardrail was green,
        because "a versioning decision is recorded" was true throughout."""
        v332 = {"clear", "stop", "subagent-stop"}
        out = self._departures(v332)
        assert {d.member for d in out} == {"build-index", "user-prompt-submit"}
        assert {d.kind for d in out} == {"removed"}

    def test_the_shipped_binary_is_conformant(self):
        """v3.3.3's remedy — retired but dispatchable — reads as conformance,
        which is what makes the check a regression guard rather than a standing
        complaint."""
        assert self._departures(set(EVER_REGISTERED_HOOK_COMMANDS)) == ()

    def test_the_general_leg_and_the_hand_set_agree_on_this_repo(self):
        """The join. Anything `EVER_REGISTERED_HOOK_COMMANDS` still lists is a
        member the declaration-driven leg must also treat as owed."""
        declared = {
            m.member for m in self._departures(set())
        }
        assert declared <= set(EVER_REGISTERED_HOOK_COMMANDS), (
            "the fixture declares a member this module does not consider ever "
            "registered — the two guards disagree about the same surface"
        )
