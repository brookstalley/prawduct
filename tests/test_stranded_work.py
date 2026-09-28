"""Tests for lib/stranded_work.py — stranded branches and worktree liveness.

The briefing line must NAME nothing (owner ruling on #410): every test of it
pairs the no-names assertion with a positive control that the line exists, so
an implementation that simply returns nothing cannot pass.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import pytest

from lib import stranded_work as sw
from lib.stranded_work import ACTIVE, IDLE, MISSING, RECENT, UNKNOWN, Signal

DAY = 86400


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
         "-c", "commit.gpgsign=false", "-c", "init.defaultBranch=main", *args],
        cwd=str(cwd), capture_output=True, text=True, check=True,
    )
    return result.stdout


def commit(repo: Path, name: str, text: str = "x") -> None:
    (repo / name).write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", name)


@pytest.fixture
def clone(tmp_path):
    """A clone of a bare origin with `main` pushed. Returns the clone path."""
    origin = tmp_path / "origin.git"
    git(tmp_path, "init", "-q", "--bare", str(origin))
    repo = tmp_path / "repo"
    git(tmp_path, "init", "-q", str(repo))
    commit(repo, "a.txt")
    git(repo, "remote", "add", "origin", str(origin))
    git(repo, "push", "-q", "origin", "main")
    git(repo, "fetch", "-q", "origin")
    return repo


def _scan(repo: Path, **kw):
    kw.setdefault("roots", [])
    return sw.scan(repo, **kw)


# --- pure classification ------------------------------------------------------


class TestClassify:
    NOW = 1_000_000_000.0

    @pytest.mark.parametrize("age, expected", [
        (0, ACTIVE),
        (sw.ACTIVE_WITHIN_SECONDS, ACTIVE),
        (sw.ACTIVE_WITHIN_SECONDS + 1, RECENT),
        (sw.IDLE_AFTER_SECONDS - 1, RECENT),
        (sw.IDLE_AFTER_SECONDS, IDLE),
    ])
    def test_boundaries(self, age, expected):
        assert sw.classify(Signal("reflog", self.NOW - age), self.NOW) == expected

    def test_no_signal_is_unknown_never_idle(self):
        # Absence of evidence is not evidence of abandonment.
        assert sw.classify(None, self.NOW) == UNKNOWN

    @pytest.mark.parametrize("winner", ["transcript", "reflog", "session-start", "file-edit"])
    def test_the_newest_signal_wins_whatever_its_source(self, winner):
        sources = ["transcript", "reflog", "session-start", "file-edit"]
        signals = [Signal(s, 100.0 + (50 if s == winner else sources.index(s))) for s in sources]
        assert sw.newest(signals + [None]).source == winner

    def test_newest_of_nothing_is_none(self):
        assert sw.newest([None, None]) is None


class TestEncoding:
    def test_slashes_and_dots_become_dashes(self):
        # Observed on real roots: `.claude/worktrees` appears as `--claude-worktrees`.
        assert (sw.encode_project_dir("/Users/a/src/p/.claude/worktrees/x")
                == "-Users-a-src-p--claude-worktrees-x")

    def test_letters_and_digits_survive(self):
        assert sw.encode_project_dir("/tmp/Ab9") == "-tmp-Ab9"


# --- config roots and transcripts ---------------------------------------------


def _root(home: Path, name: str) -> Path:
    root = home / name
    (root / "projects").mkdir(parents=True)
    return root


def _transcript(root: Path, worktree: Path, name: str, at: float) -> Path:
    d = root / "projects" / sw.encode_project_dir(worktree)
    d.mkdir(parents=True, exist_ok=True)
    f = d / name
    f.write_text("{}\n")
    os.utime(f, (at, at))
    return f


class TestConfigRoots:
    def test_every_account_root_with_projects_is_found(self, tmp_path):
        a = _root(tmp_path, ".claude")
        b = _root(tmp_path, ".claude-second")
        c = _root(tmp_path, ".claude-second-devcontainer")
        (tmp_path / ".claude-empty").mkdir()  # no projects/: not a transcript root
        roots = sw.config_roots(env={}, home=tmp_path)
        assert set(roots) == {a, b, c}

    def test_config_dir_env_is_included_and_not_doubled(self, tmp_path):
        a = _root(tmp_path, ".claude")
        elsewhere = _root(tmp_path / "x", "cfg")
        roots = sw.config_roots(env={"CLAUDE_CONFIG_DIR": str(elsewhere)}, home=tmp_path)
        assert set(roots) == {a, elsewhere}
        roots = sw.config_roots(env={"CLAUDE_CONFIG_DIR": str(a)}, home=tmp_path)
        assert roots == [a], "the env var usually names one of the home roots"


class TestTranscriptSignal:
    def test_newest_across_every_root_wins(self, tmp_path):
        # Several accounts keep transcripts of different ages for one worktree;
        # only the newest across all of them says anything about now.
        wt = tmp_path / "wt"
        old, new = _root(tmp_path, ".claude"), _root(tmp_path, ".claude-second")
        _transcript(old, wt, "s1.jsonl", 1000.0)
        _transcript(new, wt, "s2.jsonl", 5000.0)
        assert sw.transcript_signal(wt, [old, new]) == Signal("transcript", 5000.0)
        assert sw.transcript_signal(wt, [old]) == Signal("transcript", 1000.0), (
            "positive control: one root alone answers with its own age"
        )

    def test_subagent_and_non_transcript_files_do_not_count(self, tmp_path):
        wt = tmp_path / "wt"
        root = _root(tmp_path, ".claude")
        _transcript(root, wt, "s1.jsonl", 1000.0)
        nested = root / "projects" / sw.encode_project_dir(wt) / "s1" / "subagents"
        nested.mkdir(parents=True)
        (nested / "agent.jsonl").write_text("{}")
        os.utime(nested / "agent.jsonl", (9000.0, 9000.0))
        other = root / "projects" / sw.encode_project_dir(wt) / "notes.txt"
        other.write_text("x")
        os.utime(other, (9000.0, 9000.0))
        assert sw.transcript_signal(wt, [root]) == Signal("transcript", 1000.0)

    def test_no_transcripts_is_no_signal(self, tmp_path):
        assert sw.transcript_signal(tmp_path / "wt", [_root(tmp_path, ".claude")]) is None


# --- stranded branches --------------------------------------------------------


class TestStrandedBranches:
    def test_a_local_only_branch_checked_out_nowhere_is_stranded(self, clone):
        git(clone, "switch", "-q", "-c", "fix/orphan")
        commit(clone, "b.txt")
        git(clone, "switch", "-q", "main")

        report = _scan(clone)

        assert [b.name for b in report.branches] == ["fix/orphan"]
        assert report.branches[0].unique_commits == 1

    def test_a_fresh_branch_is_stranded_too(self, clone):
        # The motivating branch was 18 hours old when it was missed; an age
        # floor would have excluded it. A commit made seconds ago still counts.
        git(clone, "switch", "-q", "-c", "fix/just-now")
        commit(clone, "b.txt")
        git(clone, "switch", "-q", "main")
        assert [b.name for b in _scan(clone).branches] == ["fix/just-now"]

    def test_a_pushed_branch_is_not(self, clone):
        git(clone, "switch", "-q", "-c", "fix/pushed")
        commit(clone, "b.txt")
        git(clone, "push", "-q", "origin", "fix/pushed")
        git(clone, "switch", "-q", "main")
        assert _scan(clone).branches == []

    def test_a_branch_some_OTHER_remote_ref_contains_is_not(self, clone):
        # main and develop diverge by SHA here; a branch whose commits reached
        # origin/main but not origin/develop is carried, not stranded.
        git(clone, "switch", "-q", "-c", "release-copy")
        commit(clone, "b.txt")
        git(clone, "push", "-q", "origin", "release-copy:other")
        git(clone, "fetch", "-q", "origin")
        git(clone, "switch", "-q", "main")
        assert _scan(clone).branches == []

    def test_a_branch_checked_out_in_a_worktree_is_not(self, clone, tmp_path):
        git(clone, "worktree", "add", "-q", "-b", "fix/in-use", str(tmp_path / "wt"))
        commit(tmp_path / "wt", "b.txt")
        assert _scan(clone).branches == []

    def test_a_repo_with_no_remotes_reports_none(self, tmp_path):
        repo = tmp_path / "solo"
        git(tmp_path, "init", "-q", str(repo))
        commit(repo, "a.txt")
        git(repo, "switch", "-q", "-c", "side")
        commit(repo, "b.txt")
        git(repo, "switch", "-q", "main")

        report = _scan(repo)

        assert report.has_remotes is False
        assert report.branches == [], "with no remote, every branch would qualify and say nothing"


# --- worktrees ----------------------------------------------------------------


class TestWorktrees:
    def test_the_current_worktree_is_marked(self, clone, tmp_path):
        git(clone, "worktree", "add", "-q", "-b", "side", str(tmp_path / "wt"))
        rows = {Path(w.path).name: w for w in _scan(clone).worktrees}
        assert rows["repo"].is_current and not rows["wt"].is_current
        assert not {Path(w.path).name: w for w in _scan(tmp_path / "wt").worktrees}["repo"].is_current

    def test_an_untouched_worktree_goes_idle_and_counts_its_changes(self, clone, tmp_path):
        wt = tmp_path / "wt"
        git(clone, "worktree", "add", "-q", "-b", "side", str(wt))
        (wt / "wip.txt").write_text("unsaved thought")

        later = time.time() + 8 * DAY
        row = next(w for w in _scan(clone, now=later).worktrees if Path(w.path) == wt.resolve())

        assert row.state == IDLE
        assert row.dirty == 1
        assert row.last_activity is not None

    def test_a_fresh_edit_makes_it_active(self, clone, tmp_path):
        wt = tmp_path / "wt"
        git(clone, "worktree", "add", "-q", "-b", "side", str(wt))
        old = time.time() - 30 * DAY
        for p in [wt / "a.txt", Path(git(wt, "rev-parse", "--absolute-git-dir").strip()) / "logs" / "HEAD"]:
            os.utime(p, (old, old))
        (wt / "a.txt").write_text("edited now")

        row = next(w for w in _scan(clone).worktrees if Path(w.path) == wt.resolve())

        assert row.state == ACTIVE
        assert row.last_activity.source == "file-edit"

    def test_a_fresh_commit_on_a_clean_tree_is_seen_through_the_reflog(self, clone, tmp_path):
        # Clean tree, no transcript, no governed session: the commit is the only
        # trace an agent left, and only the reflog carries it.
        wt = tmp_path / "wt"
        git(clone, "worktree", "add", "-q", "-b", "side", str(wt))
        commit(wt, "b.txt")

        row = next(w for w in _scan(clone).worktrees if Path(w.path) == wt.resolve())

        assert row.dirty == 0
        assert (row.state, row.last_activity.source) == (ACTIVE, "reflog")

    def test_a_transcript_in_any_root_makes_it_active(self, clone, tmp_path):
        wt = tmp_path / "wt"
        git(clone, "worktree", "add", "-q", "-b", "side", str(wt))
        old = time.time() - 30 * DAY
        os.utime(Path(git(wt, "rev-parse", "--absolute-git-dir").strip()) / "logs" / "HEAD", (old, old))
        root = _root(tmp_path / "home", ".claude-second")
        _transcript(root, wt.resolve(), "s.jsonl", time.time())

        row = next(w for w in _scan(clone, roots=[root]).worktrees if Path(w.path) == wt.resolve())

        assert (row.state, row.last_activity.source) == (ACTIVE, "transcript")

    def test_a_deleted_worktree_is_missing_not_idle(self, clone, tmp_path):
        wt = tmp_path / "wt"
        git(clone, "worktree", "add", "-q", "-b", "side", str(wt))
        subprocess.run(["rm", "-rf", str(wt)], check=True)
        states = {w.state for w in _scan(clone).worktrees if not w.is_current}
        assert states == {MISSING}

    def test_observing_a_sibling_never_rewrites_its_index(self, clone, tmp_path):
        """The index mtime would report the probe itself as activity, so the
        scan must not refresh it. Made stat-stale first, so a plain `git
        status` WOULD rewrite it — the positive control below proves that."""
        wt = tmp_path / "wt"
        git(clone, "worktree", "add", "-q", "-b", "side", str(wt))
        index = Path(git(wt, "rev-parse", "--absolute-git-dir").strip()) / "index"

        def make_stale():
            old = time.time() - 5 * DAY
            os.utime(index, (old, old))
            os.utime(wt / "a.txt", None)  # tracked file newer than the index
            return index.stat().st_mtime

        before = make_stale()
        _scan(clone)
        assert index.stat().st_mtime == before

        before = make_stale()
        git(wt, "status", "--porcelain")
        assert index.stat().st_mtime != before, "positive control: a plain status does rewrite it"


# --- degradation --------------------------------------------------------------


class TestDegradation:
    def test_no_git_is_a_named_problem_not_an_exception(self, clone, monkeypatch):
        def boom(*a, **k):
            raise FileNotFoundError("git")
        monkeypatch.setattr(sw.subprocess, "run", boom)

        report = _scan(clone)

        assert report.problems == ["could not list worktrees"]
        assert sw.briefing_line(report) is None

    def test_a_timeout_degrades_the_same_way(self, clone, monkeypatch):
        def slow(*a, **k):
            raise subprocess.TimeoutExpired(cmd="git", timeout=5)
        monkeypatch.setattr(sw.subprocess, "run", slow)
        assert _scan(clone).problems == ["could not list worktrees"]


# --- briefing line ------------------------------------------------------------


def _row(path, state, *, current=False, dirty=0, branch="b"):
    return sw.WorktreeRow(path=path, branch=branch, is_current=current, ephemeral=None,
                          state=state, dirty=dirty)


class TestBriefingLine:
    SECRET_PATH = "/src/secret-worktree-path"
    SECRET_BRANCH = "feature/secret-branch-name"

    def test_silent_when_nothing_to_say(self):
        report = sw.Report(worktrees=[_row("/here", ACTIVE, current=True), _row("/x", RECENT)])
        assert sw.briefing_line(report) is None

    def test_counts_everything_and_names_nothing(self):
        report = sw.Report(
            worktrees=[
                _row("/here", ACTIVE, current=True),
                _row(self.SECRET_PATH, IDLE, dirty=3, branch=self.SECRET_BRANCH),
                _row("/src/other", IDLE),
                _row("/src/live", ACTIVE),
            ],
            branches=[sw.BranchRow(self.SECRET_BRANCH, 0.0, 2), sw.BranchRow("fix/b", 0.0, 1)],
        )

        line = sw.briefing_line(report)

        assert line is not None, "positive control: there is something to say"
        assert "2 local branches" in line
        assert "2 worktrees idle 7+ days (1 with uncommitted changes)" in line
        assert "1 other worktree has an agent active" in line
        assert "prawduct-hook worktrees" in line
        for name in (self.SECRET_PATH, self.SECRET_BRANCH, "/src/other", "/src/live", "fix/b", "secret"):
            assert name not in line, f"the briefing named {name!r} (#410)"

    def test_the_current_worktree_is_never_counted(self):
        report = sw.Report(worktrees=[_row("/here", IDLE, current=True, dirty=5)])
        assert sw.briefing_line(report) is None

    def test_an_active_sibling_alone_is_worth_a_line(self):
        line = sw.briefing_line(sw.Report(worktrees=[_row("/here", ACTIVE, current=True), _row("/x", ACTIVE)]))
        assert line is not None and "leave it alone" in line

    def test_unknown_and_missing_are_not_called_idle(self):
        report = sw.Report(worktrees=[_row("/a", UNKNOWN), _row("/b", MISSING)])
        assert sw.briefing_line(report) is None


# --- command ------------------------------------------------------------------


class TestCommand:
    def test_json_is_versioned_and_parses(self, clone, capsys):
        assert sw.worktrees_cmd(clone, ["--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["schema_version"] == sw.SCHEMA_VERSION
        assert payload["worktrees"][0]["is_current"] is True

    def test_table_warns_that_liveness_is_inferred(self, clone, capsys):
        assert sw.worktrees_cmd(clone, []) == 0
        out = capsys.readouterr().out
        assert "this session" in out
        assert "never adopt" in out

    def test_unknown_argument_is_a_usage_error(self, clone, capsys):
        assert sw.worktrees_cmd(clone, ["--all"]) == 2
        assert "usage" in capsys.readouterr().err
