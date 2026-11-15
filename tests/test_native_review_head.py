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
  reviewed code there and has nothing to check out. ``record`` returns that tree
  to the commit it started on, so the harness can clean it up.
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
        """An advisory's recovery is tested by its effect: run it as printed."""
        subprocess.run(left["recovery"], shell=True, cwd=str(repo), check=True,
                       capture_output=True, timeout=10)
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
