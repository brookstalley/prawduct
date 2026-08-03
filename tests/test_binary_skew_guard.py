"""#227 — a stale PATH `prawduct-hook` must not silently no-op the data plane.

Inside a framework-repo worktree, a bare `prawduct-hook` on `$PATH` resolves to
whatever plugin the environment installed — the plugin cache, or (as in this
clone) a sibling worktree's checkout. The observed consequence was the worst
failure mode this system has: `critic-begin` ran the foreign binary and wrote
**no** kernel-v3 manifest, with no error, and the `SubagentStop`-triggered
`critic-consolidate` no-opped the same way, leaving reviews unpersisted.

**The guard keys on binary IDENTITY, not version equality.** #227 proposed
comparing self-reported versions against the repo's expected lineage; that test
is blind in the common case, because a checkout is routinely ahead of its own
manifest between releases. Live proof at the time of writing: the installed
plugin and this worktree both report `3.2.3` while the worktree's `lib/` has
diverged substantially. "Am I the binary this repo carries" is exact and needs
no lineage bookkeeping.

Identity has **two axes** and closing one leaves the defect standing: which
script is executing (`__file__`), and whose `lib/` it will import
(`_plugin_root()`, which prefers `$CLAUDE_PLUGIN_ROOT`). The repo-local script
running another plugin's governance code is #227's consequence surviving on the
exact command the binary-skew refusal prescribes, so both are reported, with
different messages because they have different fixes.

Posture follows what the command produces (`architecture.md` § Direction —
authority fails closed, advice fails soft): a governance **write** refuses, and
everything else degrades to a loud stderr note. Neither is silent, which is the
whole point.

Product repos carry no `plugin/.claude-plugin/plugin.json` and legitimately run
the installed binary, so they must be entirely unaffected — that is the
over-fire case, and the one a careless fix breaks.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

# The guard's own marker. Every assertion keys on THIS rather than on an exit
# code or a path substring, because both are reachable by accident — see the
# note in test_data_plane_write_refuses_loudly.
_SKEW_MARKER = "plugin-binary-skew"


def _make_framework_checkout(root: Path, version: str = "9.9.9") -> Path:
    """A repo shaped like a prawduct framework checkout: it carries a plugin."""
    manifest_dir = root / "plugin" / ".claude-plugin"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "plugin.json").write_text(
        json.dumps({"name": "prawduct", "version": version}), encoding="utf-8"
    )
    (root / "plugin" / "bin").mkdir(parents=True, exist_ok=True)
    (root / ".prawduct").mkdir(exist_ok=True)
    return root


def _make_product_repo(root: Path) -> Path:
    """A repo with no plugin of its own — the ordinary governed product."""
    (root / ".prawduct").mkdir(parents=True, exist_ok=True)
    return root


def _install_binary_at(plugin_dir: Path, version: str = "9.9.9") -> Path:
    """Materialise a REAL runnable hook under `plugin_dir`, and return it.

    The BINARY axis keys on the running script's own location, so a test that
    only varies `$CLAUDE_PLUGIN_ROOT` pins the wrong thing entirely — it
    exercises the env-var implementation that was the chunk's blocking defect.
    Copying the actual binary means "foreign" and "repo-local" are decided the
    same way the guard decides them: by where the file lives. The env var
    remains meaningful on the separate LIB axis.
    """
    (plugin_dir / "bin").mkdir(parents=True, exist_ok=True)
    (plugin_dir / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (plugin_dir / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "prawduct", "version": version}), encoding="utf-8"
    )
    binary = plugin_dir / "bin" / "prawduct-hook"
    shutil.copy2(HOOK, binary)
    return binary


def _run(repo: Path, *args: str, binary: Path | None = None,
         plugin_root: str | None = None):
    """Run `binary` (default: this worktree's hook) with cwd inside `repo`.

    `plugin_root` still sets `$CLAUDE_PLUGIN_ROOT`. It is NOT true that the
    guard ignores it — that was this harness's original claim and two tests
    here now disprove it. The var cannot decide whether the *binary* is
    foreign (that is `__file__`), but it does decide which `lib/` the process
    imports, and `_lib_skew` reports that separately. Two axes, two messages.
    """
    env = {**os.environ}
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    if plugin_root is not None:
        env["CLAUDE_PLUGIN_ROOT"] = plugin_root
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    return subprocess.run(
        [sys.executable, str(binary or HOOK), *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=env,
    )


class TestFrameworkCheckoutSkew:
    def test_data_plane_write_refuses_loudly(self, tmp_path):
        """A governance write from a foreign binary must fail closed."""
        repo = _make_framework_checkout(tmp_path / "fw")
        foreign = _install_binary_at(tmp_path / "installed")

        result = _run(repo, "critic-consolidate", binary=foreign)

        assert result.returncode == 1, (
            "a data-plane write on a foreign binary must refuse, not proceed — "
            "the defect being fixed is that it proceeded and wrote nothing"
        )
        combined = result.stdout + result.stderr
        # Keyed on the guard's OWN marker, not on any exit-1: the first cut of
        # this test passed against unguarded code because the command crashed
        # with ModuleNotFoundError and the traceback contained the binary path.
        # An exit code is not evidence of WHY.
        assert _SKEW_MARKER in combined, (
            "the refusal must be the skew guard's, not an incidental failure"
        )
        assert "Traceback" not in combined, (
            "the guard must refuse cleanly, before the command crashes on an "
            "import it was never going to resolve"
        )
        assert "plugin/bin/prawduct-hook" in combined, (
            "the refusal must name the binary to run instead; a refusal you "
            "cannot act on is its own dead end"
        )

    def test_refusal_survives_identical_versions(self, tmp_path):
        """The discriminator is identity — equal versions must NOT excuse it.

        The case #227's proposed version comparison waves through, and the
        common one: a checkout ahead of its own manifest.
        """
        repo = _make_framework_checkout(tmp_path / "fw", version="3.2.3")
        foreign = _install_binary_at(tmp_path / "installed", version="3.2.3")

        result = _run(repo, "critic-consolidate", binary=foreign)
        combined = result.stdout + result.stderr
        assert result.returncode == 1 and _SKEW_MARKER in combined, (
            "equal versions must not excuse a foreign binary — identical "
            "manifests with divergent lib/ is the case that bit"
        )

    def test_env_var_cannot_excuse_a_foreign_binary(self, tmp_path):
        """`$CLAUDE_PLUGIN_ROOT` must not be able to launder identity.

        This is the exact inversion the first implementation shipped: it read
        the env var instead of the running script, so pointing the var at the
        repo made a foreign binary compare EQUAL and pass silently — #227
        wearing the guard as a disguise.
        """
        repo = _make_framework_checkout(tmp_path / "fw")
        foreign = _install_binary_at(tmp_path / "installed")

        result = _run(
            repo, "critic-consolidate",
            binary=foreign, plugin_root=str(repo / "plugin"),
        )
        combined = result.stdout + result.stderr
        assert result.returncode == 1 and _SKEW_MARKER in combined, (
            "the env var must not be able to vouch for a binary that is not "
            "the one this repo carries"
        )

    def test_env_var_does_not_condemn_the_binary_but_lib_skew_is_reported(
        self, tmp_path
    ):
        """The repo-local script with a foreign `lib/` is reported as LIB skew.

        An earlier cut of this test asserted plain silence here, on the reasoning
        that "the repo's own binary is never foreign whatever the env says".
        That was half right and dangerous: the binary is indeed not foreign, but
        `_plugin_root()` seeds `sys.path`, so this invocation runs the repo's
        script over ANOTHER plugin's governance code — #227's consequence
        surviving on the exact command the binary-skew refusal prescribes.

        So: not condemned as a foreign binary, and not silent either.
        """
        repo = _make_framework_checkout(tmp_path / "fw")
        local = _install_binary_at(repo / "plugin")
        _install_binary_at(tmp_path / "installed")

        result = _run(
            repo, "version", binary=local, plugin_root=str(tmp_path / "installed"),
        )
        assert result.returncode == 0, "an advisory command still runs"
        assert _SKEW_MARKER in result.stderr, (
            "importing another plugin's lib/ must not pass silently"
        )
        assert "importing lib/ from" in result.stderr, (
            "and it must say LIB, not blame the binary — the two have different "
            "fixes, and naming the wrong one sends the reader to the wrong place"
        )

    def test_repo_local_script_and_lib_is_wholly_silent(self, tmp_path):
        """Both halves right: no noise. The guard must not nag correct use."""
        repo = _make_framework_checkout(tmp_path / "fw")
        local = _install_binary_at(repo / "plugin")
        result = _run(
            repo, "version", binary=local, plugin_root=str(repo / "plugin"),
        )
        assert result.returncode == 0
        assert _SKEW_MARKER not in result.stderr

    def test_advisory_command_notes_but_proceeds(self, tmp_path):
        """Advice fails soft: loud, but not a refusal."""
        repo = _make_framework_checkout(tmp_path / "fw")
        foreign = _install_binary_at(tmp_path / "installed")

        result = _run(repo, "version", binary=foreign)
        assert result.returncode == 0, "a read-only command must still run"
        assert _SKEW_MARKER in result.stderr, (
            "it must still SAY the binary is foreign — silence here is the "
            "defect one severity down"
        )

    def test_repo_local_binary_is_silent(self, tmp_path):
        """No skew, no noise: the guard must not nag the correct invocation."""
        repo = _make_framework_checkout(tmp_path / "fw")
        local = _install_binary_at(repo / "plugin")
        result = _run(repo, "version", binary=local)
        assert result.returncode == 0
        assert _SKEW_MARKER not in result.stderr


class TestHarnessInvokedHooksNeverRefuse:
    """The over-fire that would have broken every framework checkout.

    `hooks/hooks.json` invokes `${CLAUDE_PLUGIN_ROOT}/bin/prawduct-hook` for
    SessionStart/Stop/SubagentStop/UserPromptSubmit — the install cache, which
    inside a framework checkout is foreign BY DESIGN. Refusing there returns 1
    from every SessionStart in every such repo (no briefing, no session reset,
    no marker sweep) and is unactionable besides: a hook cannot be told to run
    a repo-local binary. They get the note; they never refuse.
    """

    def test_session_start_clear_does_not_refuse(self, tmp_path):
        repo = _make_framework_checkout(tmp_path / "fw")
        foreign = _install_binary_at(tmp_path / "installed")
        result = _run(repo, "clear", "--session-start", binary=foreign)
        assert "BLOCKED: refusing `clear`" not in result.stderr, (
            "refusing SessionStart breaks every framework checkout"
        )

    def test_subagent_stop_does_not_refuse(self, tmp_path):
        repo = _make_framework_checkout(tmp_path / "fw")
        foreign = _install_binary_at(tmp_path / "installed")
        result = _run(repo, "subagent-stop", binary=foreign)
        assert "BLOCKED: refusing `subagent-stop`" not in result.stderr

    def test_harness_hook_still_says_it_is_foreign(self, tmp_path):
        """Positive assertion for "neither is silent".

        The exclusion tests all check that a refusal is ABSENT, which cannot
        distinguish "noted and proceeded" from "said nothing at all" — and
        saying nothing is precisely the defect #227 is about, one severity down.
        """
        repo = _make_framework_checkout(tmp_path / "fw")
        foreign = _install_binary_at(tmp_path / "installed")
        result = _run(repo, "subagent-stop", binary=foreign)
        assert _SKEW_MARKER in result.stderr, (
            "a harness hook must still report the skew even though it proceeds"
        )

    def test_stop_does_not_refuse(self, tmp_path):
        """`stop` writes a fact via the abandoned-review self-heal, and is
        still harness-invoked — who invokes it decides whether refusing is
        possible at all, before what it writes decides how loudly to say so."""
        repo = _make_framework_checkout(tmp_path / "fw")
        foreign = _install_binary_at(tmp_path / "installed")
        result = _run(repo, "stop", binary=foreign)
        assert "BLOCKED: refusing `stop`" not in result.stderr


class TestProductRepoUnaffected:
    """Product repos carry no plugin of their own and legitimately run the
    installed binary — if the guard fires there, every governed repo breaks."""

    def test_data_plane_write_is_not_refused(self, tmp_path):
        repo = _make_product_repo(tmp_path / "prod")
        foreign = _install_binary_at(tmp_path / "installed")
        result = _run(repo, "critic-consolidate", binary=foreign)
        combined = result.stdout + result.stderr
        assert _SKEW_MARKER not in combined, (
            "a product repo has no plugin of its own — running the installed "
            "binary is CORRECT there and must not be flagged"
        )

    def test_advisory_command_is_silent(self, tmp_path):
        repo = _make_product_repo(tmp_path / "prod")
        foreign = _install_binary_at(tmp_path / "installed")
        result = _run(repo, "version", binary=foreign)
        assert result.returncode == 0
        assert _SKEW_MARKER not in result.stderr


class TestLibSkewRefusesOnTheDataPlane:
    """The repo-local script importing a foreign `lib/` is still a skew.

    `_lib_skew` was added to close a review finding and initially had only an
    advisory-command test, so dropping its data-plane refusal left the file
    green. This is the half that can refuse the very invocation the plan's
    Verification Strategy prescribes, which makes it the half most worth pinning.
    """

    def test_data_plane_refuses_when_lib_comes_from_elsewhere(self, tmp_path):
        repo = _make_framework_checkout(tmp_path / "fw")
        local = _install_binary_at(repo / "plugin")
        _install_binary_at(tmp_path / "installed")

        result = _run(
            repo, "critic-consolidate",
            binary=local, plugin_root=str(tmp_path / "installed"),
        )
        combined = result.stdout + result.stderr
        assert result.returncode == 1, (
            "the script is this repo's, but the governance code it would "
            "execute is not — that must fail closed like any other skew"
        )
        assert _SKEW_MARKER in combined
        assert "importing lib/ from" in combined, (
            "and it must name LIB, not the binary — different fixes"
        )


class TestCommandSetsAgreeWithTheirSourceOfTruth:
    """`_HARNESS_INVOKED_COMMANDS` hand-transcribes `hooks/hooks.json`.

    Two reviewers flagged this independently. A hand-maintained copy of another
    file's contents is the defect this whole scope is about — it agrees today
    and drifts on the first edit, and the drift is silent in the *unsafe*
    direction: a hook entry point that falls out of the set starts REFUSING, and
    a refusal a hook cannot act on breaks SessionStart in every framework
    checkout. Derived from the file rather than restated.
    """

    def _hook_commands(self) -> set[str]:
        import json as _json

        data = _json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        found = set()
        for entries in data.get("hooks", {}).values():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "")
                    if "bin/prawduct-hook" not in cmd:
                        continue
                    # The verb is the token right after the binary path.
                    parts = cmd.split()
                    for idx, tok in enumerate(parts):
                        if "prawduct-hook" in tok and idx + 1 < len(parts):
                            found.add(parts[idx + 1].strip('"'))
                            break
        return found

    def test_every_hooks_json_entry_point_is_exempt_from_refusal(self):
        import re as _re

        src = (ROOT / "bin" / "prawduct-hook").read_text(encoding="utf-8")
        block = _re.search(
            r"_HARNESS_INVOKED_COMMANDS = frozenset\(\{(.*?)\}\)", src, _re.S
        )
        assert block, "the harness-invoked set moved or was renamed"
        declared = set(_re.findall(r'"([^"]+)"', block.group(1)))

        from_hooks = self._hook_commands()
        assert from_hooks, "parsed no commands out of hooks.json — the test is blind"
        missing = from_hooks - declared
        assert not missing, (
            f"hooks.json invokes {sorted(missing)}, which the guard would REFUSE. "
            "A hook cannot be told to run a repo-local binary, so refusing there "
            "breaks SessionStart in every framework checkout."
        )
