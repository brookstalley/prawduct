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
whole point. Harness-invoked hooks run the installed plugin by design and can act
on neither, so they never refuse and the skew is said once per session, by
SessionStart's `clear`, in hook terms; Stop and SubagentStop stay silent on it.

Product repos legitimately run the installed binary, so they must be entirely
unaffected — that is the over-fire case, and the one a careless fix breaks. A
product may still ship a plugin of its own at `plugin/`, so the layout alone does
not identify a checkout; the manifest's name does.
"""

from __future__ import annotations

import functools
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import copy_seam_files  # noqa: E402

ROOT =Path(__file__).resolve().parent.parent / "plugin"
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


def _make_product_with_own_plugin(root: Path, manifest: str) -> Path:
    """A governed product that ships its OWN Claude Code plugin at `plugin/`.

    `manifest` is written verbatim, so a case can be a valid manifest naming
    another plugin or a file that does not parse. No `plugin/bin/prawduct-hook`
    is created: a product's plugin has no reason to carry prawduct's binary.
    """
    manifest_dir = root / "plugin" / ".claude-plugin"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "plugin.json").write_text(manifest, encoding="utf-8")
    (root / ".prawduct").mkdir(exist_ok=True)
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
    # The binary loads its host seam from its own tree, before any `lib/` is
    # chosen, so a real plugin tree always carries it. Only the seam: which
    # `lib/` the rest of the process imports is the LIB axis these tests vary
    # through `$CLAUDE_PLUGIN_ROOT`.
    copy_seam_files(plugin_dir)
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
        assert "$CLAUDE_PLUGIN_ROOT unset" in result.stderr, (
            "an agent CAN re-invoke the repo-local binary, so its note keeps "
            "the remedy the hook note drops"
        )

    @pytest.mark.parametrize(
        "op", [("ingest",), ("sync",), ("configure", "--apply")], ids=["ingest", "sync", "configure"]
    )
    def test_an_evidence_write_refuses_on_a_foreign_binary(self, tmp_path, op):
        """Pinned at the wiring, not the predicate: the guard sees an
        `evidence` op only because `_dispatch` threads the command's argv into
        it. Called without argv, every `evidence` op would read as the bare
        (read) form and append, push or write config on a foreign binary while
        a predicate-level test stayed green."""
        repo = _make_framework_checkout(tmp_path / "fw")
        foreign = _install_binary_at(tmp_path / "installed")

        result = _run(repo, "evidence", *op, binary=foreign)

        assert result.returncode == 1
        assert _SKEW_MARKER in result.stderr
        assert "BLOCKED: refusing `evidence`" in result.stderr

    def test_an_evidence_read_proceeds_on_a_foreign_binary(self, tmp_path):
        """Control for the write case above: the read beside it is noted, not refused."""
        repo = _make_framework_checkout(tmp_path / "fw")
        foreign = _install_binary_at(tmp_path / "installed")

        result = _run(repo, "evidence", "status", binary=foreign)

        assert _SKEW_MARKER in result.stderr
        assert "BLOCKED" not in result.stderr

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
    SessionStart/Stop/SubagentStop — the install cache, which
    inside a framework checkout is foreign BY DESIGN. Refusing there returns 1
    from every SessionStart in every such repo (no briefing, no session reset,
    no marker sweep) and is unactionable besides: a hook cannot be told to run
    a repo-local binary. They never refuse.

    And they report the skew ONCE, at SessionStart, in words a hook can carry.
    The note used to fire on every harness hook and prescribe re-running the
    command with $CLAUDE_PLUGIN_ROOT unset — a remedy no hook can apply,
    repeated on every Stop: a channel produced and never consumed, which the
    framework repo's sessions saw as a stop-hook storm.
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

    def test_stop_does_not_refuse(self, tmp_path):
        """`stop` writes a fact via the abandoned-review self-heal, and is
        still harness-invoked — who invokes it decides whether refusing is
        possible at all, before what it writes decides how loudly to say so."""
        repo = _make_framework_checkout(tmp_path / "fw")
        foreign = _install_binary_at(tmp_path / "installed")
        result = _run(repo, "stop", binary=foreign)
        assert "BLOCKED: refusing `stop`" not in result.stderr

    def test_session_start_reports_the_skew_once_in_hook_words(self, tmp_path):
        """Positive assertion for "neither is silent", on the one hook that speaks.

        Both SessionStart shapes (`startup|clear` and `resume|compact|fork`)
        run `clear --session-start`, so both must carry it. On STDOUT: that is
        how a SessionStart hook's output reaches the agent's context, while
        stderr at exit 0 is only logged — moving the note from Stop to a
        SessionStart stderr line would have moved it where nobody reads. The
        note must not prescribe the agent-side remedy — a hook cannot be re-run
        with an env var unset — and must name what the reader CAN do.
        """
        repo = _make_framework_checkout(tmp_path / "fw")
        foreign = _install_binary_at(tmp_path / "installed")
        for args in (("--session-start",), ("--session-start", "--brief-only")):
            result = _run(repo, "clear", *args, binary=foreign)
            assert result.stdout.count(_SKEW_MARKER) == 1, (
                f"`clear {' '.join(args)}` must report the skew exactly once, on "
                f"stdout; stdout was: {result.stdout!r}"
            )
            assert _SKEW_MARKER not in result.stderr, (
                "stderr at exit 0 is logged, not read — the note belongs on stdout"
            )
            note = next(l for l in result.stdout.splitlines() if _SKEW_MARKER in l)
            assert "$CLAUDE_PLUGIN_ROOT unset" not in note, (
                "a hook cannot be re-run with an env var unset — that remedy is "
                "the agent's, and printing it here is unactionable"
            )
            assert f"--plugin-dir {(repo / 'plugin').resolve()}" in note, (
                "the hook note must name the remedy that IS available: loading "
                "this checkout's plugin for the session"
            )
            hook = _hook_module()
            for command in sorted(hook._DATA_PLANE_COMMANDS):
                assert f"`{command}`" in note, (
                    f"the note says which writes are guarded; `{command}` refuses "
                    "on a foreign binary and must be named"
                )
            for command, ops in hook._DATA_PLANE_WRITE_OPS.items():
                for op in ops:
                    assert f"`{command} {op}`" in note
            for command in sorted(hook._HARNESS_INVOKED_COMMANDS):
                assert f"`{command}`" in note, (
                    f"`{command}` is a hook, so it writes with the installed "
                    "plugin unguarded; a note naming only the guarded writes "
                    "reads as if no foreign code can write, while SubagentStop "
                    "consolidates the agent's own reviews"
                )
            assert "unguarded" in note

    def test_lib_skew_under_session_start_gets_the_agent_note(self, tmp_path):
        """A hook runs its own plugin's script AND lib, so a lib-only skew under
        `--session-start` is someone running the repo script by hand. The hook
        wording ("hooks always run the installed plugin") would contradict the
        lib wording in the same line, so that caller gets the ordinary note,
        on stderr, naming LIB."""
        repo = _make_framework_checkout(tmp_path / "fw")
        local = _install_binary_at(repo / "plugin")
        _install_binary_at(tmp_path / "installed")
        result = _run(
            repo, "clear", "--session-start", "--brief-only",
            binary=local, plugin_root=str(tmp_path / "installed"),
        )
        # The fixture's "installed" plugin has no lib/, so `clear` itself fails
        # after the guard; the guard's verdict is what this test is about.
        assert "BLOCKED: refusing `clear`" not in result.stderr
        assert _SKEW_MARKER not in result.stdout
        assert _SKEW_MARKER in result.stderr and "importing lib/ from" in result.stderr
        assert "Hooks always run the installed plugin" not in result.stderr

    def test_agent_invoked_clear_gets_the_agent_note(self, tmp_path):
        """The carve-out keys on `--session-start`, not on the verb: an agent
        running `clear` itself CAN re-invoke the repo-local binary, so it gets
        the ordinary note with that remedy, not the hook wording."""
        repo = _make_framework_checkout(tmp_path / "fw")
        foreign = _install_binary_at(tmp_path / "installed")
        result = _run(repo, "clear", binary=foreign)
        assert "BLOCKED: refusing `clear`" not in result.stderr
        assert _SKEW_MARKER not in result.stdout
        assert "$CLAUDE_PLUGIN_ROOT unset" in result.stderr

    def test_stop_and_subagent_stop_are_silent_on_skew(self, tmp_path):
        """The storm itself: every Stop repeated the SessionStart note.

        The control (`version`, agent-invoked, same binary, same repo) must
        still speak, so silence here is the harness carve-out and not a
        fixture in which no skew exists.
        """
        repo = _make_framework_checkout(tmp_path / "fw")
        foreign = _install_binary_at(tmp_path / "installed")
        control = _run(repo, "version", binary=foreign)
        assert _SKEW_MARKER in control.stderr, "fixture has no skew — proves nothing"
        for command in ("stop", "subagent-stop"):
            result = _run(repo, command, binary=foreign)
            assert _SKEW_MARKER not in result.stderr, (
                f"`{command}` must not repeat the skew note SessionStart already "
                "gave — it fires every turn and offers nothing to act on"
            )


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


class TestProductShippingItsOwnPluginIsNotACheckout:
    """A product may ship its own plugin at `plugin/`; that does not make it
    prawduct. The checkout test reads the manifest's name, and falls back to
    the presence of prawduct's own binary only when the manifest cannot say."""

    def test_data_plane_write_is_not_refused(self, tmp_path):
        repo = _make_product_with_own_plugin(
            tmp_path / "prod", json.dumps({"name": "other", "version": "1.0.0"})
        )
        foreign = _install_binary_at(tmp_path / "installed")
        result = _run(repo, "critic-consolidate", binary=foreign)
        combined = result.stdout + result.stderr
        assert _SKEW_MARKER not in combined, (
            "a product's own plugin is not a prawduct checkout — refusing here "
            "leaves the product unable to record any Critic review"
        )

    def test_unreadable_manifest_beside_prawducts_binary_still_refuses(self, tmp_path):
        """Authority fails closed: a real checkout whose manifest is broken
        mid-edit must keep refusing a foreign binary."""
        repo = _make_product_with_own_plugin(tmp_path / "fw", "{not json")
        (repo / "plugin" / "bin").mkdir(parents=True)
        (repo / "plugin" / "bin" / "prawduct-hook").write_text("", encoding="utf-8")
        foreign = _install_binary_at(tmp_path / "installed")
        result = _run(repo, "critic-consolidate", binary=foreign)
        assert result.returncode == 1
        assert _SKEW_MARKER in result.stdout + result.stderr

    def test_unreadable_manifest_without_prawducts_binary_is_untouched(self, tmp_path):
        repo = _make_product_with_own_plugin(tmp_path / "prod", "{not json")
        foreign = _install_binary_at(tmp_path / "installed")
        result = _run(repo, "critic-consolidate", binary=foreign)
        assert _SKEW_MARKER not in result.stdout + result.stderr

    def test_both_skew_axes_share_the_answer(self, tmp_path, monkeypatch):
        """`_binary_skew` and `_lib_skew` both ask `_repo_plugin_dir`; pin each
        caller, since a fix inlined into one would leave the other misfiring."""
        hook = _hook_module()
        installed = tmp_path / "installed"
        _install_binary_at(installed)
        monkeypatch.setenv("CLAUDE_PLUGIN_ROOT", str(installed))
        product = _make_product_with_own_plugin(
            tmp_path / "prod", json.dumps({"name": "other"})
        )
        checkout = _make_framework_checkout(tmp_path / "fw")

        assert hook._repo_plugin_dir(product) is None
        assert hook._binary_skew(product) is None
        assert hook._lib_skew(product) is None
        assert hook._repo_plugin_dir(checkout) == (checkout / "plugin").resolve()
        assert hook._lib_skew(checkout) is not None

    def test_manifest_without_a_name_falls_back_to_the_binary(self, tmp_path):
        hook = _hook_module()
        nameless = _make_product_with_own_plugin(tmp_path / "a", json.dumps({"version": "1"}))
        assert hook._repo_plugin_dir(nameless) is None
        (nameless / "plugin" / "bin").mkdir(parents=True)
        (nameless / "plugin" / "bin" / "prawduct-hook").write_text("", encoding="utf-8")
        assert hook._repo_plugin_dir(nameless) == (nameless / "plugin").resolve()


@functools.lru_cache(maxsize=1)
def _hook_module():
    """The extensionless hook script, imported so its predicates can be called
    directly. Its module name is not ``__main__``, so the CLI does not run."""
    loader = importlib.machinery.SourceFileLoader("prawduct_hook_skew", str(HOOK))
    spec = importlib.util.spec_from_loader("prawduct_hook_skew", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


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

    def _hook_invocations(self) -> dict[str, list[list[str]]]:
        """Per hooks.json event, each prawduct-hook call as [verb, *args]."""
        import json as _json

        data = _json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        found: dict[str, list[list[str]]] = {}
        for event, entries in data.get("hooks", {}).items():
            for entry in entries:
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "")
                    if "bin/prawduct-hook" not in cmd:
                        continue
                    # The verb is the token right after the binary path.
                    parts = cmd.split()
                    for idx, tok in enumerate(parts):
                        if "prawduct-hook" in tok and idx + 1 < len(parts):
                            found.setdefault(event, []).append(
                                [t.strip('"') for t in parts[idx + 1:]]
                            )
                            break
        return found

    def _hook_commands(self) -> set[str]:
        return {
            call[0] for calls in self._hook_invocations().values() for call in calls
        }

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

    def test_the_skew_reporting_hook_is_a_session_start_entry_point(self):
        """The one harness call allowed to report skew must be what EVERY
        SessionStart entry runs — and nothing the other events run. Renaming
        the verb or dropping the flag would silence the report everywhere, the
        defect one severity down; pointing it at `stop` would bring the storm
        back."""
        hook = _hook_module()
        verb, flag = hook._SKEW_REPORTING_HOOK
        assert verb in hook._HARNESS_INVOKED_COMMANDS
        by_event = self._hook_invocations()
        session_start = by_event.get("SessionStart")
        assert session_start, "parsed no SessionStart call — the test is blind"
        for call in session_start:
            assert call[0] == verb and flag in call, (
                f"SessionStart runs {call}, which would not report the skew"
            )
        others = [c for e, calls in by_event.items() if e != "SessionStart" for c in calls]
        assert others, "parsed no other event's call — the test is blind"
        for call in others:
            assert not (call[0] == verb and flag in call), (
                f"{call} would repeat the SessionStart skew note every turn"
            )
