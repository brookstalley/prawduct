"""Tests for lib/stranded_branch_probes.py — both arms of #843.

Local arm: one advisory per stranded branch, naming it; nothing for a branch a
remote carries or a worktree holds; self-resolving once the branch is pushed or
deleted. Pushed arm: one advisory per finished, pushed, unmerged branch idle a
day, offline. The scan's own edge cases live in test_stranded_work.py; these pin
what reaches the advisory roster.
"""

from __future__ import annotations

import os
import shlex
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from lib import probe_families
from lib import stranded_branch_probes as sbp
from lib.advisory_store import (
    ProjectState,
    clear_registry,
    compute_id,
    make_codebase,
    run_all_probes,
)


@pytest.fixture(autouse=True)
def _isolated_registry():
    clear_registry()
    yield
    clear_registry()


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
         "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *args],
        cwd=str(cwd), capture_output=True, text=True, check=True,
    ).stdout


def shell_words(command: str) -> list[str]:
    """How a POSIX shell splits ``command`` into words and operators — without
    running one (the suite bans shell=True). An operator (`;`, `(`, `)`, `|`,
    `&`) comes back as its own token, so a name that escaped its quoting shows
    up as a split."""
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    return list(lexer)


def commit(repo: Path, name: str) -> None:
    (repo / name).write_text(name)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", name)


@pytest.fixture
def clone(tmp_path):
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", str(origin))
    repo = tmp_path / "repo"
    git(tmp_path, "init", "-q", str(repo))
    commit(repo, "a.txt")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "origin", "main")
    return repo


def strand(repo: Path, branch: str) -> None:
    git(repo, "switch", "-q", "-c", branch)
    commit(repo, f"{branch.replace('/', '-')}.txt")
    git(repo, "switch", "-q", "main")


def probe(repo: Path):
    found = sbp.probe_stranded_branch(ProjectState({}), make_codebase(repo))
    return None if found is None else list(found)


class TestFires:
    def test_one_advisory_per_stranded_branch_naming_it(self, clone):
        strand(clone, "fix/reviewed-never-pushed")
        strand(clone, "feat/other")

        found = probe(clone)

        assert sorted(c.evidence[0].split()[2] for c in found) == [
            "feat/other", "fix/reviewed-never-pushed"
        ]
        assert all(c.type == "stranded-branch" and c.priority == "warn" for c in found)

    def test_the_recommended_command_is_read_only_and_names_the_branch(self, clone):
        strand(clone, "fix/x")
        (c,) = probe(clone)
        assert c.recommended_action == "git log --oneline refs/heads/fix/x --not --remotes"
        # It must actually run and show the stranded commit.
        out = git(clone, *c.recommended_action.split()[1:])
        assert "fix-x.txt" in out

    def test_a_hostile_branch_name_is_quoted_in_the_command(self, clone):
        # git forbids spaces in ref names but allows `$(`, `;` and backticks, and
        # the recommended command runs as given, so the name must stay one word.
        name = "fix/$(touch${IFS}pwned)"
        strand(clone, name)
        (c,) = probe(clone)
        argv = ["git", "log", "--oneline", f"refs/heads/{name}", "--not", "--remotes"]
        assert shell_words(c.recommended_action) == argv
        # Exactly shlex's single-quoting: the tokenizer above treats double quotes
        # alike, but a shell still expands `$(` inside them.
        assert c.recommended_action == shlex.join(argv)
        # And the command runs as that one argv, showing the stranded commit.
        assert "fix-" in git(clone, *argv[1:])
        unquoted = f"git log --oneline refs/heads/{name} --not --remotes"
        assert "(" in shell_words(unquoted), "positive control: unquoted, the shell sees an operator"

    def test_the_id_depends_on_the_branch_alone(self, clone):
        # Two branches are two decisions, so dismissing one must not silence the
        # other; and one branch's id must survive new commits on it.
        strand(clone, "fix/x")
        (first,) = probe(clone)
        git(clone, "switch", "-q", "fix/x")
        commit(clone, "more.txt")
        git(clone, "switch", "-q", "main")
        (again,) = probe(clone)
        id_ = lambda c: compute_id(sbp.FEATURE, c.type, sbp.PROBE_VERSION, c.evidence)  # noqa: E731
        assert id_(first) == id_(again)
        strand(clone, "fix/y")
        ids = {id_(c) for c in probe(clone)}
        assert len(ids) == 2, "a second branch is a second decision"


class TestSilentOrResolved:
    def test_nothing_when_nothing_is_stranded(self, clone):
        assert probe(clone) == []

    def test_pushing_the_branch_resolves_it(self, clone):
        strand(clone, "fix/x")
        assert probe(clone), "positive control"
        git(clone, "push", "-q", "origin", "fix/x")
        assert probe(clone) == []

    def test_deleting_the_branch_resolves_it(self, clone):
        strand(clone, "fix/x")
        assert probe(clone), "positive control"
        git(clone, "branch", "-q", "-D", "fix/x")
        assert probe(clone) == []

    def test_a_branch_a_live_worktree_holds_is_not_stranded(self, clone, tmp_path):
        git(clone, "worktree", "add", "-q", "-b", "fix/in-use", str(tmp_path / "wt"))
        commit(tmp_path / "wt", "b.txt")
        assert probe(clone) == []

    def test_a_folder_that_is_not_a_repo_stays_quiet(self, tmp_path, capsys):
        plain = tmp_path / "plain"
        plain.mkdir()
        assert probe(plain) == []
        assert capsys.readouterr().err == ""

    def test_inert_with_no_remote(self, tmp_path):
        repo = tmp_path / "solo"
        git(tmp_path, "init", "-q", str(repo))
        commit(repo, "a.txt")
        strand(repo, "side")
        assert probe(repo) == []


class TestDegradesLoudly:
    def test_a_failed_comparison_says_what_was_lost(self, clone, monkeypatch, capsys):
        strand(clone, "fix/x")
        from lib import evidence
        real = evidence.run_git

        def run_git(root, *args, **kwargs):
            if args[:1] == ("rev-list",):
                return 1, "", "fatal: timed out"
            return real(root, *args, **kwargs)
        monkeypatch.setattr(evidence, "run_git", run_git)

        assert probe(clone) is None, "could not look is not nothing to report (#917)"
        err = capsys.readouterr().err
        assert "stranded-branch probe skipped" in err
        assert "would go unreported" in err


class TestRegistered:
    def test_the_roster_runs_it(self, clone):
        strand(clone, "fix/x")
        probe_families.register_all()
        found = [c for c in run_all_probes(ProjectState({}), make_codebase(clone))
                 if c.type == "stranded-branch"]
        assert len(found) == 1
        assert found[0].feature == sbp.FEATURE


# --- the pushed arm: finished, pushed, unmerged, never PR'd (#843) ------------

DAY = 86400


def git_at(cwd: Path, when: float, *args: str) -> str:
    """``git`` with both commit dates pinned to ``when`` (epoch seconds)."""
    stamp = f"@{int(when)} +0000"
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
         "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *args],
        cwd=str(cwd), capture_output=True, text=True, check=True,
        env={**os.environ, "GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp},
    ).stdout


def finished_branch(repo: Path, branch: str, *, age_days: float = 3, push: bool = True) -> None:
    """Cut ``branch`` from main, commit on it ``age_days`` ago, push it, go back."""
    git(repo, "switch", "-q", "-c", branch, "main")
    name = f"{branch.replace('/', '-')}.txt"
    (repo / name).write_text(name)
    git(repo, "add", name)
    git_at(repo, time.time() - age_days * DAY, "commit", "-q", "-m", name)
    if push:
        git(repo, "push", "-q", "origin", branch)
    git(repo, "switch", "-q", "main")


def plan(repo: Path, branch: str, *, name: str = "build-plan-unit.md", ticked: bool = True) -> Path:
    """A build plan claiming ``branch`` with base ``main``, its one chunk ticked
    or not. Untracked, as plans are read from disk."""
    box = "x" if ticked else " "
    artifacts = repo / ".prawduct" / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (repo / ".prawduct" / "changes").mkdir(exist_ok=True)
    path = artifacts / name
    path.write_text(
        f"---\nartifact: build-plan\nscope: {name[:-3]}\nbranch: {branch}\nbase: main\n---\n\n"
        "# Build Plan\n\n## Build Chunks\n\n### Chunk 01: c01\n\n"
        f"## Status\n\n- [{box}] Chunk 01\n"
    )
    return path


def unlanded(repo: Path):
    found = sbp.probe_finished_branch_unlanded(ProjectState({}), make_codebase(repo))
    return None if found is None else list(found)


@pytest.fixture
def gh_log(tmp_path, monkeypatch):
    """A ``gh`` first on PATH that logs every call it receives."""
    d = tmp_path / "fakegh"
    d.mkdir()
    log = d / "calls.log"
    exe = d / "gh"
    exe.write_text(
        f"#!{sys.executable}\nimport sys\n"
        f"open({str(log)!r}, 'a').write(' '.join(sys.argv[1:]) + '\\n')\nprint('[]')\n"
    )
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{d}{os.pathsep}{os.environ['PATH']}")
    return log


class TestPushedArmFires:
    def test_a_finished_pushed_unmerged_branch_is_named_with_its_plan(self, clone):
        finished_branch(clone, "fix/landed-nowhere")
        plan(clone, "fix/landed-nowhere")

        (c,) = unlanded(clone)

        assert c.type == "finished-branch-unlanded"
        assert c.evidence == ("branch fix/landed-nowhere",)
        assert "build-plan-unit.md" in c.trigger_summary
        assert "3d ago" in c.trigger_summary, "how long it has sat"
        assert c.recommended_action == "prawduct-hook worktrees --prs"
        assert c.priority == "info"

    def test_it_asks_no_network_at_session_start(self, clone, gh_log):
        finished_branch(clone, "fix/x")
        plan(clone, "fix/x")
        assert unlanded(clone), "positive control: the probe fired"
        assert not gh_log.exists(), "a probe runs at every session start: no gh call"
        # The fake is reachable, so the absence above is the probe's, not the PATH's.
        subprocess.run(["gh", "pr", "list"], capture_output=True, check=True)
        assert gh_log.read_text() == "pr list\n"

    def test_the_branch_checked_out_here_is_not_exempt(self, clone):
        # #843 Decision 3: the cost example was a finished branch its own session
        # had moved on from; "wherever I stand" is no pass.
        finished_branch(clone, "fix/x")
        plan(clone, "fix/x")
        git(clone, "switch", "-q", "fix/x")
        assert [c.evidence for c in unlanded(clone)] == [("branch fix/x",)]

    def test_the_id_depends_on_the_branch_alone(self, clone):
        finished_branch(clone, "fix/x")
        plan(clone, "fix/x")
        (first,) = unlanded(clone)
        plan(clone, "fix/x", name="build-plan-second.md")
        (again,) = unlanded(clone)
        id_ = lambda c: compute_id(sbp.FEATURE, c.type, sbp.PROBE_VERSION, c.evidence)  # noqa: E731
        assert id_(first) == id_(again)
        assert "build-plan-second.md" in again.trigger_summary


class TestPushedArmSilent:
    def test_a_plan_with_a_chunk_left_is_not_finished(self, clone):
        finished_branch(clone, "fix/x")
        plan(clone, "fix/x", ticked=False)
        assert unlanded(clone) == []

    def test_one_open_claimant_among_several_keeps_it_quiet(self, clone):
        finished_branch(clone, "fix/x")
        plan(clone, "fix/x")
        assert unlanded(clone), "positive control"
        plan(clone, "fix/x", name="build-plan-open.md", ticked=False)
        assert unlanded(clone) == []

    def test_a_branch_no_plan_claims_has_no_reading_of_finished(self, clone):
        finished_branch(clone, "fix/x")
        plan(clone, "fix/other")
        assert unlanded(clone) == []

    def test_a_branch_finished_within_a_day_is_not_yet_a_problem(self, clone):
        finished_branch(clone, "fix/x", age_days=0.5)
        plan(clone, "fix/x")
        assert unlanded(clone) == []
        finished_branch(clone, "fix/y", age_days=1.1)
        plan(clone, "fix/y", name="build-plan-y.md")
        assert [c.evidence for c in unlanded(clone)] == [("branch fix/y",)], "control: past a day it fires"

    def test_an_unpushed_branch_is_the_local_arms_not_this_ones(self, clone):
        finished_branch(clone, "fix/x", push=False)
        plan(clone, "fix/x")
        assert unlanded(clone) == []
        assert [c.type for c in probe(clone)] == ["stranded-branch"], "control: the local arm has it"

    def test_a_merged_branch_has_landed(self, clone):
        finished_branch(clone, "fix/x")
        plan(clone, "fix/x")
        assert unlanded(clone), "positive control"
        git(clone, "merge", "-q", "--no-ff", "-m", "merge fix/x", "fix/x")
        git(clone, "push", "-q", "origin", "main")
        assert unlanded(clone) == []

    def test_a_long_lived_branch_is_never_a_pull_requests_head(self, clone):
        # A plan may claim a release branch; nobody opens a PR from one.
        finished_branch(clone, "release/1.0")
        plan(clone, "release/1.0")
        assert unlanded(clone) == []
        finished_branch(clone, "relief/1.0")
        plan(clone, "relief/1.0", name="build-plan-relief.md")
        assert [c.evidence for c in unlanded(clone)] == [("branch relief/1.0",)], "control"

    def test_a_branch_another_worktree_holds_is_left_alone(self, clone, tmp_path):
        finished_branch(clone, "fix/x")
        plan(clone, "fix/x")
        assert unlanded(clone), "positive control"
        git(clone, "worktree", "add", "-q", str(tmp_path / "wt"), "fix/x")
        assert unlanded(clone) == []

    def test_deleting_the_branch_resolves_it(self, clone):
        finished_branch(clone, "fix/x")
        plan(clone, "fix/x")
        assert unlanded(clone), "positive control"
        git(clone, "branch", "-q", "-D", "fix/x")
        assert unlanded(clone) == []

    def test_a_folder_that_is_not_a_repo_stays_quiet(self, tmp_path, capsys):
        plain = tmp_path / "plain"
        plain.mkdir()
        plan(plain, "fix/x")
        assert unlanded(plain) == []
        assert capsys.readouterr().err == ""


class TestPushedArmDegradesLoudly:
    def test_a_failed_worktree_listing_says_what_was_lost(self, clone, monkeypatch, capsys):
        finished_branch(clone, "fix/x")
        plan(clone, "fix/x")
        from lib import gitstate
        monkeypatch.setattr(gitstate, "worktree_records", lambda _root: None)
        assert unlanded(clone) is None, "could not look is not nothing to report (#917)"
        err = capsys.readouterr().err
        assert "finished-branch probe skipped" in err
        assert "would go unreported" in err


class TestPushedArmRegistered:
    def test_the_roster_runs_it(self, clone):
        finished_branch(clone, "fix/x")
        plan(clone, "fix/x")
        probe_families.register_all()
        found = [c for c in run_all_probes(ProjectState({}), make_codebase(clone))
                 if c.type == "finished-branch-unlanded"]
        assert len(found) == 1
        assert found[0].feature == sbp.FEATURE
