"""The paired native review never moves the session checkout's HEAD (#1177).

The incident: during a ``/prawduct:critic`` run the session's checkout went
from its feature branch to a detached HEAD at that branch's own tip. The host's
native ``/code-review``, started by the wrapper the Critic dispatches, ran
``git checkout -q <head>`` in the directory it was forked in — the session's
checkout — to read the source of the range it was handed. Commits made after
that landed on no branch, and a push sent the stale branch.

Two layers, each pinned here:

- **Prevention.** The wrapper is dispatched in a worktree of its own
  (``isolation: "worktree"``) and runs ``native-review prepare`` before the
  review: that refuses when it is standing in the session's checkout, and
  otherwise detaches its OWN tree at the reviewed head, so the review reads the
  reviewed code there and has nothing to check out. The wrapper writes its text
  in that tree (the harness refuses its Write to the session's files), and
  ``record``, run from the session's checkout, copies it across, deletes the
  tree's copy and returns the tree to the commit it started on, so the harness
  can clean it up. A tree left behind anyway is named, with a guarded removal.
- **Detection.** A HEAD that left the review's branch is reported, with the
  command that recovers it, on the surfaces the builder and the wrapper read:
  the review's ``NEXT-ACTION``, ``native-review record``'s output, and
  ``critic-consolidate``'s output.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import core, head_guard, native_review  # noqa: E402
from lib import critic_consolidate as cc  # noqa: E402

DEV = "3.8.2-dev.1"
BRANCH = "feature/thing"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, check=True, timeout=10,
    ).stdout.strip()


def _branch(repo: Path) -> "str | None":
    proc = subprocess.run(
        ["git", "symbolic-ref", "--quiet", "--short", "HEAD"],
        cwd=str(repo), capture_output=True, text=True, timeout=10,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


@pytest.fixture
def branch_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "src").mkdir()
    (repo / "src/app.py").write_text("x = 1\n")
    (repo / ".gitignore").write_text(".claude/\n.prawduct/.native-reviews/\n.prawduct/.critic-partials/\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "--quiet", "-m", "init")
    _git(repo, "switch", "--quiet", "-c", BRANCH)
    (repo / "src/app.py").write_text("x = 2\n")
    _git(repo, "commit", "--quiet", "-am", "feat: change x")
    (repo / ".prawduct").mkdir()
    return repo.resolve()


def _agent_tree(repo: Path, wid: str = "a1b2c3d4e5f60718") -> Path:
    """The tree the harness gives an agent dispatched with ``isolation:
    "worktree"``: an ``agent-<hex>`` directory on a ``worktree-agent-<hex>``
    scratch branch, cut here from ``main`` (the harness's default base is the
    default branch, not the session's HEAD)."""
    dest = repo / ".claude" / "worktrees" / f"agent-{wid}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "--quiet", "-b", f"worktree-agent-{wid}", str(dest), "main")
    return dest.resolve()


def _paired(repo: Path, monkeypatch, mode: str = "cumulative") -> dict:
    monkeypatch.setattr(core, "PRAWDUCT_VERSION", DEV)
    if mode != "cumulative":
        monkeypatch.setattr(cc, "native_review_sampled", lambda _id: True)
        (repo / "src/app.py").write_text("x = 3\n")
    result = cc.begin_review(repo, mode, force=True, session_model="claude-opus-5-5")
    assert result["status"] == "ok", result
    assert "native_review" in result["manifest"], result["notes"]
    return result


def _head(args: str) -> str:
    return args.split()[1].split("...")[1]


def _sidecar(repo: Path, review_id: str) -> dict:
    return json.loads(native_review.sidecar_path(repo / ".prawduct", review_id).read_text())


# --- The dispatch: what the coordinator and the wrapper are handed ------------


class TestDispatchNamesAWorktreeOfItsOwn:
    def test_the_dispatch_line_isolates_the_wrapper(self, branch_repo, monkeypatch):
        line = cc.native_review_line(_paired(branch_repo, monkeypatch)["manifest"])
        assert 'isolation: "worktree"' in line, line
        # Control: the line still names the agent and the prompt it carries.
        assert "general-purpose" in line and "native_review.prompt" in line

    def test_the_prompt_prepares_its_own_tree_before_the_review(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        prompt = result["manifest"]["native_review"]["prompt"]
        prepare = native_review.prepare_command(result["id"], str(branch_repo))
        assert prepare in prompt
        # Order is the contract: prepare refuses in the session's checkout, so it
        # must run before the review that would check out there.
        assert prompt.index(prepare) < prompt.index("Invoke the Skill tool")
        assert "do not invoke the review" in prompt

    def test_the_prompt_forbids_moving_the_sessions_checkout(self, branch_repo, monkeypatch):
        prompt = _paired(branch_repo, monkeypatch)["manifest"]["native_review"]["prompt"]
        sentence = next(s for s in prompt.split(". ") if "is not yours" in s)
        assert f"`{branch_repo}`" in sentence
        for verb in ("checkout", "switch", "reset", "stash", "rebase"):
            assert verb in sentence, (verb, sentence)

    def test_the_record_runs_in_the_sessions_checkout(self, branch_repo, monkeypatch):
        """The wrapper's own tree is disposable: the ephemeral-worktree guard
        refuses a state write from it, and the sidecar is not there. The record
        command says where it runs."""
        result = _paired(branch_repo, monkeypatch)
        command = cc.native_review_record_command(result["id"], str(branch_repo))
        assert command.startswith(f'cd "{branch_repo}" && python3 ')
        assert command in result["manifest"]["native_review"]["prompt"]


# --- prepare: the guard that the isolation took, and the tree it reads -------


class TestPrepare:
    def test_in_the_sessions_checkout_it_refuses_and_moves_nothing(self, branch_repo, monkeypatch):
        """The incident's shape: a wrapper (and the review it forks) standing in
        the session's checkout. Nothing is checked out, and the sidecar says why
        the run did not happen."""
        result = _paired(branch_repo, monkeypatch)
        before = _git(branch_repo, "rev-parse", "HEAD")
        rc, message = native_review.prepare(branch_repo, branch_repo, result["id"])
        assert rc == 1, message
        assert "session's checkout" in message and "do not invoke the review" in message
        assert _branch(branch_repo) == BRANCH
        assert _git(branch_repo, "rev-parse", "HEAD") == before
        assert "session's checkout" in _sidecar(branch_repo, result["id"])["prepare_refused"]

    def test_a_refused_run_is_not_called_running(self, branch_repo, monkeypatch):
        """No review ran and none will land, so the builder's sentence says so
        instead of "may still be running"."""
        result = _paired(branch_repo, monkeypatch)
        assert native_review.prepare(branch_repo, branch_repo, result["id"])[0] == 1
        clause = native_review.next_action_clause(branch_repo / ".prawduct", result["id"])
        assert "did not run" in clause and "session's checkout" in clause
        assert "may still be running" not in clause

    def test_in_its_own_tree_it_detaches_that_tree_at_the_reviewed_head(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        tree = _agent_tree(branch_repo)
        head = _head(result["manifest"]["native_review"]["args"])
        rc, message = native_review.prepare(tree, branch_repo, result["id"])
        assert rc == 0, message
        assert _branch(tree) is None
        assert _git(tree, "rev-parse", "HEAD") == head
        assert (tree / "src/app.py").read_text() == "x = 2\n"  # the reviewed code, on disk
        # The session's checkout is untouched.
        assert _branch(branch_repo) == BRANCH
        recorded = _sidecar(branch_repo, result["id"])["review_tree"]
        assert recorded["path"] == str(tree)
        assert recorded["branch"] == "worktree-agent-a1b2c3d4e5f60718"

    def test_an_inner_review_reads_the_working_tree_it_reviewed(self, branch_repo, monkeypatch):
        """An inner review's head is an unreachable commit over an uncommitted
        tree; its own tree checks that out, which no branch holds."""
        result = _paired(branch_repo, monkeypatch, mode="chunk")
        assert result["manifest"]["native_review"]["synthetic_range"] is True
        tree = _agent_tree(branch_repo)
        rc, message = native_review.prepare(tree, branch_repo, result["id"])
        assert rc == 0, message
        assert (tree / "src/app.py").read_text() == "x = 3\n"
        assert _branch(branch_repo) == BRANCH

    def test_a_tree_on_a_real_branch_is_someones_checkout(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        dest = branch_repo.parent / "sibling"
        _git(branch_repo, "worktree", "add", "--quiet", "-b", "fix/other", str(dest), "main")
        rc, message = native_review.prepare(dest.resolve(), branch_repo, result["id"])
        assert rc == 1 and "fix/other" in message
        assert _branch(dest) == "fix/other"

    def test_a_dirty_tree_is_refused(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        tree = _agent_tree(branch_repo)
        (tree / "src/app.py").write_text("wip\n")
        rc, message = native_review.prepare(tree, branch_repo, result["id"])
        assert rc == 1 and "uncommitted" in message
        assert (tree / "src/app.py").read_text() == "wip\n"

    def test_another_repository_is_refused(self, branch_repo, monkeypatch, tmp_path):
        result = _paired(branch_repo, monkeypatch)
        other = tmp_path / "other"
        other.mkdir()
        _git(other, "init", "--quiet", "-b", "worktree-agent-ffffffffffff")
        _git(other, "-c", "user.email=a@b", "-c", "user.name=a", "commit", "--quiet", "--allow-empty", "-m", "x")
        rc, message = native_review.prepare(other.resolve(), branch_repo, result["id"])
        assert rc == 1 and "same repository" in message

    def test_an_unpaired_review_has_nothing_to_prepare(self, branch_repo):
        tree = _agent_tree(branch_repo)
        rc, message = native_review.prepare(tree, branch_repo, "rev-20990101T000000Z-deadbeef")
        assert rc == 1 and "no paired native review" in message
        assert _branch(tree) == "worktree-agent-a1b2c3d4e5f60718"


class TestPrepareAtTheCli:
    """Pinned at the CLI, from the tree the harness makes: the pre-dispatch
    ephemeral-worktree guard refuses state writes from a disposable tree, and
    ``prepare`` must be the one ``native-review`` op that runs there."""

    def _run(self, cwd: Path, repo: Path, *args: str) -> subprocess.CompletedProcess:
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(repo)}
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        env.pop("PRAWDUCT_ALLOW_EPHEMERAL_WRITES", None)
        return subprocess.run(
            [sys.executable, str(HOOK), *args], cwd=str(cwd),
            capture_output=True, text=True, env=env, timeout=60,
        )

    def test_prepare_runs_in_the_agents_tree(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        tree = _agent_tree(branch_repo)
        proc = self._run(tree, branch_repo, "native-review", "prepare", result["id"], str(branch_repo))
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert _git(tree, "rev-parse", "HEAD") == _head(result["manifest"]["native_review"]["args"])
        assert _branch(branch_repo) == BRANCH

    def test_prepare_from_the_sessions_checkout_exits_nonzero(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        proc = self._run(branch_repo, branch_repo, "native-review", "prepare", result["id"], str(branch_repo))
        assert proc.returncode == 1, proc.stdout + proc.stderr
        assert "session's checkout" in proc.stderr
        assert _branch(branch_repo) == BRANCH

    def test_control_record_is_still_refused_in_the_agents_tree(self, branch_repo, monkeypatch):
        """Control for the classification above: the guard still refuses the
        state write from the disposable tree, which is why the record command
        changes directory first."""
        result = _paired(branch_repo, monkeypatch)
        tree = _agent_tree(branch_repo)
        proc = self._run(tree, branch_repo, "native-review", "record", result["id"])
        assert proc.returncode == 1
        assert "BLOCKED" in proc.stderr or "refus" in proc.stderr.lower(), proc.stderr


# --- record: the tree goes back, and a moved HEAD is reported ----------------


THREE = '[{"file": "a.py", "line": 3, "summary": "s", "failure_scenario": "f"}]\n'


# --- The text handoff: written in the wrapper's tree, copied by record -------


class TestTextHandoffAcrossWorktrees:
    """The first live run (2026-11-15): the wrapper, isolated in its own
    worktree, was told to Write its text to the session checkout's
    ``.native-reviews/``, and the harness refused — "This agent is isolated in
    the worktree <tree>. Edit the worktree copy of this file instead of the
    shared-checkout path." So the text is written in the wrapper's OWN tree,
    and ``record`` (run from the session's checkout) copies it across: a read
    crosses worktrees, a harness-tool write does not."""

    def _prepared(self, branch_repo, monkeypatch) -> "tuple[dict, Path]":
        result = _paired(branch_repo, monkeypatch)
        tree = _agent_tree(branch_repo)
        assert native_review.prepare(tree, branch_repo, result["id"])[0] == 0
        return result, tree

    def test_the_prompt_never_writes_into_the_sessions_checkout(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        native = result["manifest"]["native_review"]
        prompt = native["prompt"]
        assert native["text_path"] not in prompt
        sentence = next(s for s in prompt.split(". ") if "Write tool" in s)
        assert "your own worktree" in sentence and "prepare" in sentence, sentence

    def test_prepare_names_the_path_in_its_own_tree(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        tree = _agent_tree(branch_repo)
        rc, message = native_review.prepare(tree, branch_repo, result["id"])
        assert rc == 0, message
        own = native_review.own_text_path(tree, result["id"])
        assert own.is_relative_to(tree)
        assert f"`{own}`" in message
        assert _sidecar(branch_repo, result["id"])["review_tree"]["text"] == str(own)

    def test_record_copies_the_text_from_the_review_tree(self, branch_repo, monkeypatch):
        """No ``--text-file``: the sidecar says where the wrapper's tree is."""
        result, tree = self._prepared(branch_repo, monkeypatch)
        own = native_review.own_text_path(tree, result["id"])
        own.parent.mkdir(parents=True)
        own.write_text(THREE)
        pd = branch_repo / ".prawduct"
        rc, message = native_review.record(branch_repo, pd, result["id"])
        assert rc == 0, message
        assert "1 finding(s)" in message
        assert native_review.text_path(pd, result["id"]).read_text() == THREE
        assert not own.exists()  # moved, so the tree is unchanged for the harness

    def test_record_takes_an_explicit_text_file(self, branch_repo, monkeypatch, tmp_path):
        """A text saved anywhere else (the live run's scratchpad) is copied and
        left where it was: only a file in the review tree is the record's to move."""
        result, _tree = self._prepared(branch_repo, monkeypatch)
        elsewhere = tmp_path / "scratch" / "native.md"
        elsewhere.parent.mkdir()
        elsewhere.write_text(THREE)
        pd = branch_repo / ".prawduct"
        rc, message = native_review.record(branch_repo, pd, result["id"], text_file=elsewhere)
        assert rc == 0, message
        assert native_review.text_path(pd, result["id"]).read_text() == THREE
        assert elsewhere.read_text() == THREE

    def test_a_relative_or_missing_text_file_is_refused(self, branch_repo, monkeypatch):
        result, _tree = self._prepared(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        rc, message = native_review.record(branch_repo, pd, result["id"], text_file=Path("x.md"))
        assert rc == 1 and "absolute" in message
        rc, message = native_review.record(branch_repo, pd, result["id"], text_file=branch_repo / "nope.md")
        assert rc == 1 and "nope.md" in message
        assert not native_review.text_path(pd, result["id"]).exists()

    def test_no_text_anywhere_names_where_it_was_looked_for(self, branch_repo, monkeypatch):
        result, tree = self._prepared(branch_repo, monkeypatch)
        rc, message = native_review.record(branch_repo, branch_repo / ".prawduct", result["id"])
        assert rc == 1
        assert str(native_review.own_text_path(tree, result["id"])) in message

    def test_at_the_cli_from_the_sessions_checkout(self, branch_repo, monkeypatch):
        """The live shape: ``cd <session> && prawduct-hook native-review record
        <id> --text-file <path in the wrapper's tree>``."""
        result, tree = self._prepared(branch_repo, monkeypatch)
        own = native_review.own_text_path(tree, result["id"])
        own.parent.mkdir(parents=True)
        own.write_text(THREE)
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(branch_repo)}
        env.pop("CLAUDE_PLUGIN_ROOT", None)
        proc = subprocess.run(
            [sys.executable, str(HOOK), "native-review", "record", result["id"], "--text-file", str(own)],
            cwd=str(branch_repo), capture_output=True, text=True, env=env, timeout=60,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert native_review.text_path(branch_repo / ".prawduct", result["id"]).read_text() == THREE
        assert _branch(tree) == "worktree-agent-a1b2c3d4e5f60718"


# --- A review tree the harness left behind -----------------------------------


def _run_sh(command: str, cwd: Path) -> subprocess.CompletedProcess:
    """Run a printed shell one-liner as a person pasting it would."""
    return subprocess.run(["sh", "-c", command], cwd=str(cwd), capture_output=True, text=True, timeout=30)


class TestLeftoverReviewTree:
    """The second failure of the live run: the wrapper's tree outlived it,
    locked. The harness keeps a tree that is not as it made it when its agent
    ends; there, it was still detached because record had failed. Whatever the
    cause, a review tree still on disk once the text has landed is named, with
    a removal command guarded to fire only on a clean tree at its creation
    point — never one holding work."""

    def _recorded(self, branch_repo, monkeypatch) -> "tuple[dict, Path]":
        result = _paired(branch_repo, monkeypatch)
        tree = _agent_tree(branch_repo)
        _git(branch_repo, "worktree", "lock", str(tree))  # as the harness leaves it
        assert native_review.prepare(tree, branch_repo, result["id"])[0] == 0
        native_review.text_path(branch_repo / ".prawduct", result["id"]).write_text(THREE)
        assert native_review.record(branch_repo, branch_repo / ".prawduct", result["id"])[0] == 0
        return result, tree

    def test_a_clean_leftover_is_named_with_its_removal(self, branch_repo, monkeypatch):
        result, tree = self._recorded(branch_repo, monkeypatch)
        clause = native_review.next_action_clause(branch_repo / ".prawduct", result["id"])
        command = native_review.cleanup_command(branch_repo, native_review.leftover_tree(
            branch_repo, _sidecar(branch_repo, result["id"])))
        assert str(tree) in clause and f"`{command}`" in clause
        proc = _run_sh(command, branch_repo)
        assert proc.returncode == 0, proc.stderr
        assert not tree.exists()
        assert "worktree-agent-a1b2c3d4e5f60718" not in _git(branch_repo, "branch", "--list")
        # The session's own branch and checkout are untouched.
        assert _branch(branch_repo) == BRANCH
        # Gone, it is no longer named.
        assert str(tree) not in native_review.next_action_clause(branch_repo / ".prawduct", result["id"])

    def test_record_names_the_removal_too(self, branch_repo, monkeypatch):
        """Record runs inside the wrapper, before the harness's check; its
        output — the wrapper's one-line report — carries the command for the
        case the harness keeps the tree anyway."""
        result = _paired(branch_repo, monkeypatch)
        tree = _agent_tree(branch_repo)
        assert native_review.prepare(tree, branch_repo, result["id"])[0] == 0
        native_review.text_path(branch_repo / ".prawduct", result["id"]).write_text(THREE)
        rc, message = native_review.record(branch_repo, branch_repo / ".prawduct", result["id"])
        assert rc == 0
        assert "git -C" in message and "worktree remove" in message

    def test_a_leftover_with_work_is_named_and_never_removed(self, branch_repo, monkeypatch):
        result, tree = self._recorded(branch_repo, monkeypatch)
        (tree / "notes.txt").write_text("someone's work\n")
        clause = native_review.next_action_clause(branch_repo / ".prawduct", result["id"])
        assert str(tree) in clause
        assert "worktree remove" not in clause
        left = native_review.leftover_tree(branch_repo, _sidecar(branch_repo, result["id"]))
        assert left is not None and left["clean"] is False

    def test_the_guard_refuses_a_tree_that_gained_work_after_it_was_printed(self, branch_repo, monkeypatch):
        """The printed command re-checks when it runs: a commit or a new file
        made since keeps the tree and its branch."""
        result, tree = self._recorded(branch_repo, monkeypatch)
        command = native_review.cleanup_command(branch_repo, native_review.leftover_tree(
            branch_repo, _sidecar(branch_repo, result["id"])))
        (tree / "src/app.py").write_text("y = 9\n")
        _git(tree, "commit", "--quiet", "-am", "work")
        _run_sh(command, branch_repo)
        assert tree.exists()
        assert "worktree-agent-a1b2c3d4e5f60718" in _git(branch_repo, "branch", "--list")
        _git(tree, "reset", "--quiet", "--hard", "HEAD~1")
        (tree / "untracked.txt").write_text("new\n")
        _run_sh(command, branch_repo)
        assert (tree / "untracked.txt").exists()

    def test_the_guard_keeps_a_branch_that_moved_on(self, branch_repo, monkeypatch):
        """HEAD back at the start but the branch elsewhere holding commits: the
        branch delete would lose them, so nothing is removed."""
        result, tree = self._recorded(branch_repo, monkeypatch)
        command = native_review.cleanup_command(branch_repo, native_review.leftover_tree(
            branch_repo, _sidecar(branch_repo, result["id"])))
        start = _git(tree, "rev-parse", "HEAD")
        (tree / "src/app.py").write_text("y = 9\n")
        _git(tree, "commit", "--quiet", "-am", "work")
        _git(tree, "checkout", "--quiet", "--detach", start)
        _run_sh(command, branch_repo)
        assert "worktree-agent-a1b2c3d4e5f60718" in _git(branch_repo, "branch", "--list")

    def test_control_a_run_still_in_flight_names_no_leftover(self, branch_repo, monkeypatch):
        """Before the text lands the wrapper is still working in its tree."""
        result = _paired(branch_repo, monkeypatch)
        tree = _agent_tree(branch_repo)
        assert native_review.prepare(tree, branch_repo, result["id"])[0] == 0
        clause = native_review.next_action_clause(branch_repo / ".prawduct", result["id"])
        assert "may still be running" in clause and str(tree) not in clause

    def test_an_inner_review_names_its_leftover_too(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch, mode="chunk")
        tree = _agent_tree(branch_repo)
        assert native_review.prepare(tree, branch_repo, result["id"])[0] == 0
        native_review.text_path(branch_repo / ".prawduct", result["id"]).write_text(THREE)
        assert native_review.record(branch_repo, branch_repo / ".prawduct", result["id"])[0] == 0
        clause = native_review.next_action_clause(branch_repo / ".prawduct", result["id"])
        assert str(tree) in clause and "work from both lists" not in clause


class TestRecordReturnsTheReviewTree:
    def test_the_review_tree_goes_back_to_its_branch(self, branch_repo, monkeypatch):
        """So the harness finds it as it made it, and cleans it up."""
        result = _paired(branch_repo, monkeypatch)
        tree = _agent_tree(branch_repo)
        assert native_review.prepare(tree, branch_repo, result["id"])[0] == 0
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        rc, message = native_review.record(branch_repo, pd, result["id"])
        assert rc == 0, message
        assert _branch(tree) == "worktree-agent-a1b2c3d4e5f60718"
        assert "returned" in message

    def test_a_review_tree_left_dirty_is_kept_and_named(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        tree = _agent_tree(branch_repo)
        assert native_review.prepare(tree, branch_repo, result["id"])[0] == 0
        (tree / "src/app.py").write_text("edited by the review\n")
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        rc, message = native_review.record(branch_repo, pd, result["id"])
        assert rc == 0, message
        assert _branch(tree) is None
        assert str(tree) in message and "left" in message

    def test_the_tree_is_left_as_the_harness_made_it(self, branch_repo, monkeypatch):
        """The leftover of the first live run: the harness removes an isolated
        agent's worktree only when it is unchanged as the agent ends. After a
        full handoff — text written in the wrapper's own tree, recorded from the
        session's checkout — the tree is back at its creation point with
        nothing in it, ignored files included."""
        result = _paired(branch_repo, monkeypatch)
        tree = _agent_tree(branch_repo)
        created = _git(tree, "rev-parse", "HEAD")
        assert native_review.prepare(tree, branch_repo, result["id"])[0] == 0
        own = native_review.own_text_path(tree, result["id"])
        own.parent.mkdir(parents=True, exist_ok=True)
        own.write_text(THREE)
        rc, message = native_review.record(branch_repo, branch_repo / ".prawduct", result["id"])
        assert rc == 0, message
        assert _git(tree, "rev-parse", "HEAD") == created
        assert _branch(tree) == "worktree-agent-a1b2c3d4e5f60718"
        assert _git(tree, "status", "--porcelain", "--ignored", "--untracked-files=all") == ""
        assert not own.parent.exists()

    def test_a_prepared_run_read_its_own_tree_so_nothing_moved_under_it(self, branch_repo, monkeypatch):
        """``tree_moved`` asks whether the code the native run read changed
        under it. A run that read its own tree at the reviewed head read
        exactly the reviewed code, whatever the builder did meanwhile."""
        result = _paired(branch_repo, monkeypatch, mode="chunk")
        tree = _agent_tree(branch_repo)
        assert native_review.prepare(tree, branch_repo, result["id"])[0] == 0
        (branch_repo / "src/app.py").write_text("x = 4\n")  # the builder's fix
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        assert native_review.record(branch_repo, pd, result["id"])[0] == 0
        events = [json.loads(line) for line in (pd / ".governance-ledger.jsonl").read_text().splitlines()]
        [event] = [e for e in events if e.get("event") == "native.review"]
        assert event["native"]["tree_moved"] is False


def _detach_at_tip(repo: Path) -> str:
    """What the host's review did in the field: ``git checkout -q <head>`` in
    the session's checkout, ``<head>`` being the branch's own tip."""
    tip = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "--quiet", tip)
    assert _branch(repo) is None
    return tip


class TestRecordReportsAMovedHead:
    def test_record_names_the_move_and_the_recovery(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        _detach_at_tip(branch_repo)
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        rc, message = native_review.record(branch_repo, pd, result["id"])
        assert rc == 0, message
        assert f"HEAD LEFT BRANCH `{BRANCH}`" in message
        assert f"git switch {BRANCH}" in message

    def test_control_record_on_the_branch_says_nothing_of_it(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        pd = branch_repo / ".prawduct"
        native_review.text_path(pd, result["id"]).write_text(THREE)
        rc, message = native_review.record(branch_repo, pd, result["id"])
        assert rc == 0 and "HEAD LEFT" not in message


# --- head_guard: the check and its recovery command --------------------------


class TestHeadGuard:
    def test_on_the_branch_nothing_is_reported(self, branch_repo):
        assert head_guard.left_branch(branch_repo, BRANCH) is None

    def test_a_branch_switch_is_the_builders_and_not_reported(self, branch_repo):
        """Scope: the failure is a detached HEAD. A switch to another branch is
        a deliberate act no reviewer has made."""
        _git(branch_repo, "switch", "--quiet", "main")
        assert head_guard.left_branch(branch_repo, BRANCH) is None

    def test_no_branch_at_dispatch_means_nothing_to_compare(self, branch_repo):
        _detach_at_tip(branch_repo)
        assert head_guard.left_branch(branch_repo, None) is None

    def test_detached_at_the_tip_recovers_with_a_switch(self, branch_repo):
        _detach_at_tip(branch_repo)
        left = head_guard.left_branch(branch_repo, BRANCH)
        assert left["recovery"] == f"git switch {BRANCH}"
        self._follow(branch_repo, left)

    def test_commits_on_the_detached_head_are_carried_back(self, branch_repo):
        """The field case: two commits landed on the detached HEAD before
        anyone noticed. The recovery moves the branch to them."""
        _detach_at_tip(branch_repo)
        for n in (1, 2):
            (branch_repo / f"later{n}.txt").write_text("x\n")
            _git(branch_repo, "add", "-A")
            _git(branch_repo, "commit", "--quiet", "-m", f"later {n}")
        detached = _git(branch_repo, "rev-parse", "HEAD")
        left = head_guard.left_branch(branch_repo, BRANCH)
        assert left["recovery"] == f"git branch -f {BRANCH} HEAD && git switch {BRANCH}"
        self._follow(branch_repo, left)
        assert _git(branch_repo, "rev-parse", BRANCH) == detached

    def test_a_head_that_does_not_contain_the_tip_is_not_force_moved(self, branch_repo):
        """``branch -f`` here would drop the branch's own commits, so the
        recovery is a switch, and the message names the commit to carry over."""
        main_tip = _git(branch_repo, "rev-parse", "main")
        _git(branch_repo, "checkout", "--quiet", main_tip)
        left = head_guard.left_branch(branch_repo, BRANCH)
        assert left["recovery"] == f"git switch {BRANCH}"
        assert "branch -f" not in head_guard.message(left)
        assert main_tip[:12] in head_guard.message(left)

    def test_the_message_says_what_breaks(self, branch_repo):
        _detach_at_tip(branch_repo)
        text = head_guard.message(head_guard.left_branch(branch_repo, BRANCH))
        assert text.startswith(f"HEAD LEFT BRANCH `{BRANCH}`")
        assert "no branch" in text and "push" in text

    @staticmethod
    def _follow(repo: Path, left: dict) -> None:
        """An advisory's recovery is tested by its effect: run it as printed.

        Without a shell (the repo bans ``shell=True``): the printed text is
        split on `` && `` and each step run in list form, stopping at the first
        failure, which is what the shell's ``&&`` does."""
        printed = left["recovery"]
        assert f"`{printed}`" in head_guard.message(left)  # what is run is what is printed
        for step in printed.split(" && "):
            argv = shlex.split(step)
            assert argv[0] == "git", step
            proc = subprocess.run(argv, cwd=str(repo), capture_output=True, text=True, timeout=10)
            assert proc.returncode == 0, (step, proc.stderr)
        assert _branch(repo) == BRANCH
        assert head_guard.left_branch(repo, BRANCH) is None


# --- The builder's NEXT-ACTION, and critic-consolidate's own output ----------


def _write_partial(repo: Path, result: dict) -> None:
    manifest = result["manifest"]
    assert manifest["roster"] == ["reviewer"], manifest["roster"]
    partial = {
        "role": "reviewer", "goals": "1-7", "dispatch_id": result["id"],
        "commit_reviewed": manifest["commit_reviewed"], "model": "opus",
        "duration_seconds": 60, "findings": [], "summary": "clean",
    }
    (repo / manifest["rendezvous"]["reviewer"]["partial"]).write_text(json.dumps(partial))


def _next_action(repo: Path) -> str:
    return json.loads((repo / ".prawduct" / ".critic-findings.json").read_text())["next_action"]


class TestNextActionReportsAMovedHead:
    def test_the_incident_is_loud_in_the_review_record(self, branch_repo, monkeypatch):
        """The regression: a paired review, and the session's HEAD detached at
        the branch tip while it ran. The builder's next sentence says so."""
        result = _paired(branch_repo, monkeypatch)
        _write_partial(branch_repo, result)
        _detach_at_tip(branch_repo)
        assert cc.consolidate(branch_repo, trigger="explicit") == 0
        sentence = _next_action(branch_repo)
        assert f"HEAD LEFT BRANCH `{BRANCH}`" in sentence
        assert f"git switch {BRANCH}" in sentence

    def test_control_on_the_branch_the_sentence_is_unchanged(self, branch_repo, monkeypatch):
        result = _paired(branch_repo, monkeypatch)
        _write_partial(branch_repo, result)
        assert cc.consolidate(branch_repo, trigger="explicit") == 0
        sentence = _next_action(branch_repo)
        assert "HEAD LEFT" not in sentence and "native review" in sentence

    def test_an_old_review_does_not_blame_a_later_detach(self, branch_repo, monkeypatch):
        """The record is re-rendered long after the review; a HEAD detached on
        purpose a day later is not this review's doing."""
        result = _paired(branch_repo, monkeypatch)
        path = native_review.sidecar_path(branch_repo / ".prawduct", result["id"])
        sidecar = json.loads(path.read_text())
        sidecar["dispatched_at"] = "2000-01-01T00:00:00Z"
        path.write_text(json.dumps(sidecar))
        _detach_at_tip(branch_repo)
        assert "HEAD LEFT" not in native_review.next_action_clause(branch_repo / ".prawduct", result["id"])

    def test_an_inner_review_reports_it_too(self, branch_repo, monkeypatch):
        """An inner run's findings are not put to the builder; a moved HEAD is
        not a finding, and is."""
        result = _paired(branch_repo, monkeypatch, mode="chunk")
        _detach_at_tip(branch_repo)
        clause = native_review.next_action_clause(branch_repo / ".prawduct", result["id"])
        assert f"HEAD LEFT BRANCH `{BRANCH}`" in clause
        assert "work from both lists" not in clause


class TestConsolidateCommandReportsAMovedHead:
    """``critic-consolidate`` compares the manifest's branch, written at
    dispatch, with HEAD after — any review, paired or not."""

    @pytest.fixture
    def hook(self):
        loader = importlib.machinery.SourceFileLoader("prawduct_hook_head_guard", str(HOOK))
        module = importlib.util.module_from_spec(
            importlib.util.spec_from_loader("prawduct_hook_head_guard", loader)
        )
        loader.exec_module(module)
        return module

    def test_a_detached_head_is_reported_on_stderr(self, hook, branch_repo, monkeypatch, capsys):
        (branch_repo / ".prawduct" / "project-state.yaml").write_text("native_review_pairing: false\n")
        monkeypatch.setattr(core, "PRAWDUCT_VERSION", DEV)
        result = cc.begin_review(branch_repo, "cumulative", force=True, session_model="claude-opus-5-5")
        assert "native_review" not in result["manifest"]  # unpaired: the guard is general
        _write_partial(branch_repo, result)
        _detach_at_tip(branch_repo)
        monkeypatch.chdir(branch_repo)
        assert hook.cmd_critic_consolidate(branch_repo, []) == 0
        err = capsys.readouterr().err
        assert f"HEAD LEFT BRANCH `{BRANCH}`" in err
        assert f"git switch {BRANCH}" in err

    def test_control_on_the_branch_nothing_is_said(self, hook, branch_repo, monkeypatch, capsys):
        (branch_repo / ".prawduct" / "project-state.yaml").write_text("native_review_pairing: false\n")
        monkeypatch.setattr(core, "PRAWDUCT_VERSION", DEV)
        result = cc.begin_review(branch_repo, "cumulative", force=True, session_model="claude-opus-5-5")
        _write_partial(branch_repo, result)
        monkeypatch.chdir(branch_repo)
        assert hook.cmd_critic_consolidate(branch_repo, []) == 0
        assert "HEAD LEFT" not in capsys.readouterr().err
