"""#594 — a disposable agent worktree must not silently strand governance state.

Claude Code gives a subagent dispatched with ``isolation: "worktree"`` its own
git worktree forked from HEAD, of which only the code commit is merged back.
``lib.gitstate.is_ephemeral_worktree`` is the predicate that recognizes one, and
``bin/prawduct-hook``'s pre-dispatch guard turns every ``.prawduct/`` write from
inside one into a loud refusal instead of a write that dies at merge.

The load-bearing tests here are the NEGATIVE ones. ``EnterWorktree`` creates
legitimate, user-requested, long-lived session worktrees under the SAME
``.claude/worktrees/`` parent, and the source bug report proposed detecting on
exactly that parent — which would have silenced governance in every one of them.
A false positive is strictly worse than the bug being fixed, so the
EnterWorktree-shaped cases are pinned as regressions.

Real ``git`` repos, sterile env, mirroring ``tests/test_project_dir_resolution.py``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"


# ---------------------------------------------------------------------------
# Helpers (real git, sterile env)
# ---------------------------------------------------------------------------


def _git_env(repo: Path) -> dict[str, str]:
    home = repo.parent / "_home"
    home.mkdir(exist_ok=True)
    return {
        "HOME": str(home),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True,
        env=_git_env(repo), check=True, timeout=10,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    prawduct = repo / ".prawduct"
    prawduct.mkdir(exist_ok=True)
    (prawduct / "project-state.yaml").write_text("product_name: Test\n")
    (prawduct / "backlog.md").write_text("# Backlog\n")
    (repo / "seed.txt").write_text("seed\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init", "--quiet")


def _add_worktree(repo: Path, dest: Path, branch: str) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-q", "-b", branch, str(dest), "HEAD")
    return dest.resolve()


def _agent_worktree(repo: Path, wid: str = "a287823214767feaa") -> Path:
    """The shape Claude Code's Agent tool produces, as observed in the field."""
    return _add_worktree(
        repo, repo / ".claude" / "worktrees" / f"agent-{wid}", f"worktree-agent-{wid}"
    )


@pytest.fixture
def gitstate():
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from lib import gitstate as gs
    return gs


def _hook_env(repo: Path, env_extra: dict[str, str] | None = None) -> dict[str, str]:
    """The sterile env every hook invocation in this file must use.

    Extracted because hand-building it drifted vacuous TWICE: an inherited
    `PRAWDUCT_ALLOW_EPHEMERAL_WRITES` makes a "not refused" assertion pass for
    the wrong reason, and an inherited `CLAUDE_PLUGIN_ROOT` makes the hook print
    BLOCKED from the *skew* guard rather than this one. Both failures look like
    a passing test. One helper, so a third caller cannot diverge.
    """
    env = {**os.environ}
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env.pop("PRAWDUCT_ALLOW_EPHEMERAL_WRITES", None)
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    env.update(env_extra or {})
    return env


def _run(repo: Path, *args: str, env_extra: dict[str, str] | None = None):
    env = _hook_env(repo, env_extra)
    return subprocess.run(
        [sys.executable, str(HOOK), *args],
        cwd=str(repo), capture_output=True, text=True, env=env, timeout=60,
    )


# ---------------------------------------------------------------------------
# The predicate
# ---------------------------------------------------------------------------


class TestPredicatePositive:
    def test_agent_worktree_detected(self, tmp_path, gitstate):
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _agent_worktree(primary)
        assert gitstate.is_ephemeral_worktree(wt) == "agent"

    def test_workflow_checkout_detected(self, tmp_path, gitstate):
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _add_worktree(
            primary, primary / ".claude" / "worktrees" / "wf_abc123", "wf-branch"
        )
        assert gitstate.is_ephemeral_worktree(wt) == "workflow"

    def test_branch_signal_survives_a_directory_rename(self, tmp_path, gitstate):
        """The dir shape is the primary signal; the branch is the fallback, so a
        harness change to directory naming degrades to one more signal rather
        than to silence."""
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _add_worktree(
            primary,
            primary / ".claude" / "worktrees" / "renamed-by-a-future-harness",
            "worktree-agent-a287823214767feaa",
        )
        assert gitstate.is_ephemeral_worktree(wt) == "agent"


class TestPredicateNegative:
    """A false positive silences governance in a worktree someone is really
    working in — strictly worse than the stranding this predicate prevents."""

    def test_enter_worktree_session_is_not_ephemeral(self, tmp_path, gitstate):
        """THE regression. `EnterWorktree` sites its worktrees under the same
        `.claude/worktrees/` parent; matching on that parent alone (what the
        source report proposed) would refuse every governance write in a
        legitimate, user-requested session worktree."""
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _add_worktree(
            primary, primary / ".claude" / "worktrees" / "my-feature", "feat/my-feature"
        )
        assert gitstate.is_ephemeral_worktree(wt) is None

    def test_enter_worktree_with_nested_name_is_not_ephemeral(self, tmp_path, gitstate):
        """`EnterWorktree` names may carry `/` segments, so the ancestor test must
        not be the whole test at any depth."""
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _add_worktree(
            primary, primary / ".claude" / "worktrees" / "brooks" / "spike", "spike"
        )
        assert gitstate.is_ephemeral_worktree(wt) is None

    def test_named_sibling_worktree_is_not_ephemeral(self, tmp_path, gitstate):
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _add_worktree(primary, tmp_path / "wt-feature", "feature")
        assert gitstate.is_ephemeral_worktree(wt) is None

    def test_primary_checkout_is_not_ephemeral(self, tmp_path, gitstate):
        primary = tmp_path / "primary"
        _init_repo(primary)
        assert gitstate.is_ephemeral_worktree(primary.resolve()) is None

    def test_non_git_directory_does_not_raise(self, tmp_path, gitstate):
        plain = tmp_path / "plain"
        plain.mkdir()
        assert gitstate.is_ephemeral_worktree(plain) is None

    def test_agent_shaped_dir_outside_claude_worktrees_is_not_ephemeral(
        self, tmp_path, gitstate
    ):
        """The `.claude/worktrees` ancestor is necessary as well as insufficient —
        a product is free to have a directory called `agent-<hex>`."""
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _add_worktree(primary, tmp_path / "agent-a287823214767feaa", "feature")
        assert gitstate.is_ephemeral_worktree(wt) is None


class TestPredicateIsCheapOffThePath:
    def test_no_subprocess_when_path_test_fails(self, tmp_path, gitstate, monkeypatch):
        """The guard runs pre-dispatch on EVERY hook invocation, `clear` and
        `stop` included, and NFR § Direction forbids noticeable session-start
        delay. The pure-string ancestor test must therefore gate the git probe:
        outside `.claude/worktrees/` the predicate spawns nothing."""
        def _explode(*args, **kwargs):  # pragma: no cover - must never run
            raise AssertionError("is_ephemeral_worktree spawned a subprocess")

        monkeypatch.setattr(gitstate.subprocess, "run", _explode)
        assert gitstate.is_ephemeral_worktree(tmp_path / "some" / "repo") is None


# ---------------------------------------------------------------------------
# The pre-dispatch guard
# ---------------------------------------------------------------------------


class TestGuardRefusesWrites:
    def test_backlog_write_refuses_and_writes_nothing(self, tmp_path):
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _agent_worktree(primary)
        before = (wt / ".prawduct" / "backlog.md").read_text()

        result = _run(wt, "backlog", "file", "--title", "T", "--body", "B")

        assert result.returncode == 1
        assert "BLOCKED" in result.stderr
        assert "ephemeral agent worktree" in result.stderr
        assert (wt / ".prawduct" / "backlog.md").read_text() == before

    def test_service_backed_backlog_write_is_allowed(self, tmp_path):
        """The other half of the backlog branch, and the reason it exists.

        On the Issues backend every live-backlog op is a network write against
        `--repo owner/repo`. It lands on the server and outlives the worktree,
        so it cannot strand — refusing it would be the false refusal this
        change treats as its worst available outcome. Only the markdown
        backend, which writes `.prawduct/backlog.md` in THIS tree, is refused
        (covered by `test_backlog_write_refuses_and_writes_nothing`).
        """
        primary = tmp_path / "primary"
        _init_repo(primary)
        state = primary / ".prawduct" / "project-state.yaml"
        state.write_text(state.read_text() + "backlog_service_repo: owner/repo\n")
        _git(primary, "add", "-A")
        _git(primary, "commit", "-m", "service backend", "--quiet")
        wt = _agent_worktree(primary)

        assert "BLOCKED" not in _run(wt, "backlog", "file", "--title", "T").stderr

    @pytest.mark.parametrize("op", ["refresh-counts", "export", "restructure-preview"])
    def test_service_backed_local_write_ops_still_refuse(self, tmp_path, op):
        """"Issues backend ⇒ every backlog op is a network call" is FALSE.

        `lib/backlog/cli.py` documents `refresh-counts` as "a read + a local
        snapshot write", and `export`/`restructure-preview` write their output
        into this tree. The service-backed allowance must not cover them, or it
        reintroduces the strand it was carved out to avoid.
        """
        primary = tmp_path / "primary"
        _init_repo(primary)
        state = primary / ".prawduct" / "project-state.yaml"
        state.write_text(state.read_text() + "backlog_service_repo: owner/repo\n")
        _git(primary, "add", "-A")
        _git(primary, "commit", "-m", "service backend", "--quiet")
        wt = _agent_worktree(primary)

        assert "BLOCKED" in _run(wt, "backlog", op, "--repo", "owner/repo").stderr

    def test_refusal_names_the_consequence_and_the_override(self, tmp_path):
        """A refusal that does not explain itself just moves the confusion."""
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _agent_worktree(primary)

        stderr = _run(wt, "test-evidence", "record").stderr

        assert "discarded when it merges" in stderr
        # The message must not overclaim: a review or disposition persists to the
        # clone-shared evidence store and survives the worktree — it covers no
        # branch rather than vanishing, and saying otherwise would teach an agent
        # to distrust a store that did keep its fact.
        assert "clone-shared evidence store" in stderr
        assert "PRAWDUCT_ALLOW_EPHEMERAL_WRITES=1" in stderr

    @pytest.mark.parametrize(
        "argv",
        [
            ("critic-begin", "--mode", "chunk"),
            ("advisory", "dismiss", "some-id"),
            ("disposition", "rev-x", "F1", "--accept", "why"),
            ("learnings-obligation", "--apply"),
        ],
    )
    def test_state_writers_refuse(self, tmp_path, argv):
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _agent_worktree(primary)

        result = _run(wt, *argv)

        # Assert the MESSAGE, not just the exit code. Every command here also
        # exits 1 for its own reasons (missing args, no active review), so a
        # returncode assertion passes with the guard removed entirely and
        # proves nothing — caught by red-verifying this file against a
        # disabled guard.
        assert result.returncode == 1
        assert "BLOCKED" in result.stderr
        assert "ephemeral agent worktree" in result.stderr

    def test_unknown_command_refuses_fail_closed(self, tmp_path):
        """The allowlist is of READS, so a command added later defaults to
        refused here rather than to a silent strand."""
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _agent_worktree(primary)
        result = _run(wt, "some-future-write-command")
        assert result.returncode == 1
        assert "BLOCKED" in result.stderr


class TestGuardAllowsReads:
    @pytest.mark.parametrize("argv", [("version",), ("evidence", "status")])
    def test_read_commands_proceed(self, tmp_path, argv):
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _agent_worktree(primary)
        assert "BLOCKED" not in _run(wt, *argv).stderr

    @pytest.mark.parametrize(
        "command",
        [
            "audit-learnings",
            "coverage-scaffold",
            "learnings-obligation",
            "norm-index-scaffold",
        ],
    )
    def test_read_only_flag_form_proceeds(self, tmp_path, command):
        """These four mutate only under `--apply`; the dry run is a report.

        Parametrized over the whole family because two of them shipped missing
        from the allowlist: their dry runs were refused with a message asserting
        a discarded write, about commands that write nothing. That is the false
        refusal the guard's own comment says it must never produce, and it is
        the fail-closed default's most exposed edge — so the family is pinned
        rather than one representative of it.
        """
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _agent_worktree(primary)
        assert "BLOCKED" not in _run(wt, command).stderr

    @pytest.mark.parametrize(
        "command", ["audit-learnings", "coverage-scaffold", "learnings-obligation"]
    )
    def test_apply_form_still_refuses(self, tmp_path, command):
        """The other half of the same branch — `--apply` is the writing form."""
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _agent_worktree(primary)
        assert "BLOCKED" in _run(wt, command, "--apply").stderr

    def test_allowed_command_carries_the_head_snapshot_notice(self, tmp_path):
        """The silence that produced the source report: an isolated agent reads
        every tracked file as a fork-point snapshot. This is the only channel
        that reaches it without the dispatcher's cooperation."""
        stderr = _run(_agent_worktree(_seeded(tmp_path)), "version").stderr
        assert "snapshot of the commit it was forked from" in stderr
        assert "your prompt is newer" in stderr


class TestGuardScope:
    def test_normal_worktree_is_unaffected(self, tmp_path):
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _add_worktree(primary, tmp_path / "wt-feature", "feature")
        result = _run(wt, "backlog", "list")
        assert "BLOCKED" not in result.stderr
        assert "ephemeral" not in result.stderr

    def test_enter_worktree_session_governs_normally_end_to_end(self, tmp_path):
        """The chunk's acceptance criterion, proved THROUGH the guard.

        `TestPredicateNegative` proves the predicate returns None for an
        EnterWorktree-shaped worktree; that is not the same claim as "the
        command actually runs". This exercises the whole path — a worktree
        living under `.claude/worktrees/` with a non-agent name must be
        governed exactly like the primary checkout, refusal and notice alike.
        """
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _add_worktree(
            primary, primary / ".claude" / "worktrees" / "my-feature", "feat/my-feature"
        )

        result = _run(wt, "backlog", "file", "--title", "T", "--body", "B")

        assert "BLOCKED" not in result.stderr
        assert "ephemeral" not in result.stderr

    def test_read_only_backlog_alias_is_not_refused(self, tmp_path):
        """`show` is `get`'s alias; refusing it told a pure read that its write
        had been discarded."""
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _agent_worktree(primary)
        assert "BLOCKED" not in _run(wt, "backlog", "show", "ABC-1234").stderr

    def test_override_env_reverses_the_refusal_but_keeps_the_notice(self, tmp_path):
        """The override waives permission to write, not the staleness warning.

        They answer different questions — "may I write here" versus "how old is
        what I am reading" — and a dispatcher who deliberately opted into writing
        has not thereby learned that every tracked file it reads is a fork-point
        snapshot. Silencing both on one env var loses the half nobody opted out of.
        """
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _agent_worktree(primary)
        stderr = _run(
            wt, "test-evidence", "record",
            env_extra={"PRAWDUCT_ALLOW_EPHEMERAL_WRITES": "1"},
        ).stderr
        assert "BLOCKED" not in stderr
        assert "snapshot of the commit it was forked from" in stderr

    def test_fails_open_when_lib_is_unimportable(self, tmp_path):
        """Bootstrap resilience — the contract `get_project_dir` documents.

        The guard runs BEFORE command dispatch, so a broken or absent plugin
        `lib/` must not crash there. An unguarded `_gitstate()` call here took
        down `test_views`'s import-error path and five binary-skew tests, all of
        which run the hook with no importable `lib/`; failing open is also the
        right answer on the merits, since an install too broken to import cannot
        be classified as ephemeral either.
        """
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _agent_worktree(primary)
        empty_plugin = tmp_path / "no_lib"
        empty_plugin.mkdir()

        result = _run(wt, "version", env_extra={"CLAUDE_PLUGIN_ROOT": str(empty_plugin)})

        assert "Traceback" not in result.stderr
        assert "ModuleNotFoundError" not in result.stderr

    def test_harness_invoked_commands_are_never_refused(self, tmp_path):
        """`stop`/`clear` are the harness's, not the agent's. Refusing one would
        break the session rather than protect it."""
        primary = tmp_path / "primary"
        _init_repo(primary)
        wt = _agent_worktree(primary)
        # Shares `_run`'s env construction rather than rebuilding it — a
        # hand-built copy here drifted vacuous twice before.
        result = subprocess.run(
            [sys.executable, str(HOOK), "stop"],
            cwd=str(wt), capture_output=True, text=True, input="{}",
            env=_hook_env(wt), timeout=60,
        )
        assert "BLOCKED" not in result.stderr


def _seeded(tmp_path: Path) -> Path:
    primary = tmp_path / "primary"
    _init_repo(primary)
    return primary
