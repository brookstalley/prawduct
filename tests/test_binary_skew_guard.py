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

    The guard keys on the running script's own location, so a test that only
    varies `$CLAUDE_PLUGIN_ROOT` pins the wrong thing entirely — it exercises
    the env-var implementation that was the chunk's blocking defect. Copying
    the actual binary means "foreign" and "repo-local" are decided the same way
    the guard decides them: by where the file lives.
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

    `plugin_root` still sets `$CLAUDE_PLUGIN_ROOT` — kept so the tests can prove
    the guard IGNORES it, which is the whole content of the identity decision.
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

    def test_env_var_cannot_condemn_the_repo_local_binary(self, tmp_path):
        """The mirror: the correct invocation must not refuse because of the env.

        `$CLAUDE_PLUGIN_ROOT` is exported into the Bash tool env whenever the
        plugin is enabled, so an env-keyed guard would refuse the very command
        its own error message tells you to run.
        """
        repo = _make_framework_checkout(tmp_path / "fw")
        local = _install_binary_at(repo / "plugin")
        # A real elsewhere-plugin: `version` reads its manifest through
        # `_plugin_root()`, so pointing the env at an empty path would fail the
        # command for an unrelated reason and prove nothing about the guard.
        _install_binary_at(tmp_path / "installed")

        result = _run(
            repo, "version", binary=local, plugin_root=str(tmp_path / "installed"),
        )
        assert result.returncode == 0
        assert _SKEW_MARKER not in result.stderr, (
            "the repo's own binary is never foreign, whatever the env says"
        )

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
