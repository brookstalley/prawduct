"""Tests for lib/git_hygiene_probes.py — the `tidy-available` advisory."""

from __future__ import annotations

import re
import subprocess
import time
from pathlib import Path

import pytest

from lib import git_hygiene, git_hygiene_probes as ghp, probe_families
from lib.advisory_store import (
    ProjectState,
    clear_registry,
    compute_id,
    make_codebase,
    run_all_probes,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / "plugin" / "bin" / "prawduct-hook"
DAY = 86400


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


def commit(repo: Path, name: str) -> None:
    (repo / name).write_text(name)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", name)


def merged(repo: Path, name: str) -> None:
    git(repo, "checkout", "-q", "-b", name)
    commit(repo, name.replace("/", "-") + ".txt")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "--no-ff", "-m", f"merge {name}", name)


@pytest.fixture
def clone(tmp_path):
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", str(origin))
    repo = tmp_path / "repo"
    git(tmp_path, "init", "-q", str(repo))
    commit(repo, "a.txt")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "-u", "origin", "main")
    return repo


def probe(repo: Path):
    found = ghp.probe_tidy_available(ProjectState({}), make_codebase(repo))
    return None if found is None else list(found)


def prefs(repo: Path, text: str) -> None:
    d = repo / ".prawduct" / "artifacts"
    d.mkdir(parents=True, exist_ok=True)
    (d / "project-preferences.md").write_text(text)


def id_of(c) -> str:
    return compute_id(ghp.FEATURE, c.type, ghp.PROBE_VERSION, c.evidence)


class TestFires:
    def test_one_advisory_for_the_whole_set(self, clone):
        merged(clone, "feat/a")
        merged(clone, "feat/b")
        (c,) = probe(clone)
        assert c.type == "tidy-available" and c.priority == "info"
        assert c.evidence == ("delete-branch feat/a", "delete-branch feat/b")
        assert "2 merged local branches" in c.trigger_summary
        assert c.recommended_action == "prawduct-hook git-tidy"

    def test_counts_read_naturally_for_one_of_a_kind(self, clone, tmp_path):
        merged(clone, "feat/a")
        gone = tmp_path / "gone"
        git(clone, "worktree", "add", "-q", "--detach", str(gone))
        subprocess.run(["rm", "-rf", str(gone)], check=True)
        (c,) = probe(clone)
        assert c.trigger_summary.startswith("1 dead worktree entry, 1 merged local branch can")

    def test_following_its_recommendation_shows_the_same_set(self, clone, tmp_path):
        """The recommended command ships to every repo, so test its effect: run it
        and find each proposed removal in its output, with the command to do it."""
        merged(clone, "feat/a")
        (c,) = probe(clone)
        result = subprocess.run(
            ["python3", str(HOOK), *c.recommended_action.split()[1:]], cwd=str(clone),
            capture_output=True, text=True, timeout=60, env={"PATH": "/usr/bin:/bin", "HOME": str(tmp_path / "h")},
        )
        assert result.returncode == 0, result.stderr
        for line in c.evidence:
            kind, target = line.split(" ", 1)
            assert target in result.stdout
        assert "git branch -d -- feat/a" in result.stdout

    def test_copy_names_no_internal_identifier(self, clone):
        merged(clone, "feat/a")
        (c,) = probe(clone)
        for text in (c.trigger_summary, c.owner_action):
            assert not re.search(r"#\d+|\bR\d+\b|\bChunk\b|\bO-\d+", text), text
        assert c.trigger_summary and c.owner_action, "control: the copy exists"


class TestIdentity:
    def test_the_id_holds_for_an_unchanged_set_and_moves_with_it(self, clone):
        merged(clone, "feat/a")
        (first,) = probe(clone)
        (again,) = probe(clone)
        assert id_of(first) == id_of(again)
        merged(clone, "feat/b")
        (grown,) = probe(clone)
        assert id_of(grown) != id_of(first), "a new removal is a new question"


class TestPolicy:
    @pytest.mark.parametrize("row", ["off", "OFF", "`off` (no proposals here)"])
    def test_off_silences_it(self, clone, row):
        merged(clone, "feat/a")
        prefs(clone, f"- **Branch cleanup**: {row}\n")
        assert probe(clone) == []

    @pytest.mark.parametrize("text", [
        "- **Branch cleanup**: propose\n",
        "- **Branch cleanup**: sometimes\n",
        "- **Branch cleanup**: (unset)\n",
        "nothing relevant here\n",
    ], ids=["propose", "unrecognised", "unset", "absent"])
    def test_anything_but_off_proposes(self, clone, text):
        merged(clone, "feat/a")
        prefs(clone, text)
        assert probe(clone), "only an explicit off silences it"


class TestSilentOrUnchecked:
    def test_nothing_to_tidy_is_silent(self, clone):
        assert probe(clone) == []

    def test_tidying_resolves_it(self, clone):
        merged(clone, "feat/a")
        assert probe(clone), "positive control"
        git(clone, "branch", "-d", "feat/a")
        assert probe(clone) == []

    def test_git_failing_is_could_not_look_not_nothing(self, clone, monkeypatch, capsys):
        from lib import gitstate
        merged(clone, "feat/a")
        monkeypatch.setattr(gitstate, "worktree_records", lambda _d: None)
        assert probe(clone) is None
        assert "tidy probe skipped" in capsys.readouterr().err


class TestSiblings:
    def test_a_finished_sibling_is_named_only_after_a_quiet_week(self, clone, tmp_path, monkeypatch):
        wt = tmp_path / "side"
        git(clone, "worktree", "add", "-q", "-b", "feat/side", str(wt))
        commit(wt, "side.txt")
        git(clone, "merge", "-q", "--no-ff", "-m", "merge side", "feat/side")
        assert probe(clone) == [], "just used: not proposed"
        real = time.time
        monkeypatch.setattr(git_hygiene.time, "time", lambda: real() + 8 * DAY)
        (c,) = probe(clone)
        assert f"remove-worktree {wt.resolve()}" in c.evidence


class TestNoNetwork:
    def test_the_probe_starts_no_network_process(self, clone, monkeypatch):
        """The cost the requirement names is the network call, so the assertion is
        on every process the probe starts, not on a proxy."""
        merged(clone, "feat/a")
        git(clone, "push", "-q", "origin", "feat/a")
        git(clone, "push", "-q", "origin", "main")
        git(clone, "remote", "set-url", "origin", "https://unreachable.invalid/x.git")
        started: list[list[str]] = []
        real_run = subprocess.run

        def recording_run(args, *a, **k):
            started.append(list(args))
            return real_run(args, *a, **k)
        monkeypatch.setattr(subprocess, "run", recording_run)
        (c,) = probe(clone)
        assert "delete-remote-branch origin/feat/a" in c.evidence, "the remote leg was reached"
        assert started, "the recorder saw the probe's git calls"
        network = [a for a in started if a[0] == "gh" or (a[0] == "git" and set(a) & {"fetch", "push", "ls-remote", "pull"})]
        assert network == []


class TestRoster:
    def test_registered_at_the_composition_root_and_run_by_the_roster(self, clone):
        merged(clone, "feat/a")
        probe_families.register_all()
        found = [c for c in run_all_probes(ProjectState({}), make_codebase(clone)) if c.type == "tidy-available"]
        assert len(found) == 1
