"""Tests for lib/stranded_branch_probes.py — the local-only arm of #843.

One advisory per stranded branch, naming it; nothing for a branch a remote
carries or a worktree holds; self-resolving once the branch is pushed or
deleted. The scan's own edge cases live in test_stranded_work.py; these pin
what reaches the advisory roster.
"""

from __future__ import annotations

import shlex
import subprocess
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
    return list(sbp.probe_stranded_branch(ProjectState({}), make_codebase(repo)))


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

        assert probe(clone) == []
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
