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
        assert report.branches[0].unique_commits is None, "counted only on request"
        assert _scan(clone, count_commits=True).branches[0].unique_commits == 1

    def test_a_branch_named_like_a_directory_still_counts(self, clone):
        # Without `refs/heads/`, `git rev-list docs` is ambiguous when a `docs/`
        # directory exists, and the count silently becomes "?".
        (clone / "docs").mkdir()
        (clone / "docs" / "x.md").write_text("x")
        git(clone, "add", "docs")
        git(clone, "commit", "-q", "-m", "docs dir")
        git(clone, "push", "-q", "origin", "main")
        git(clone, "switch", "-q", "-c", "docs")
        commit(clone, "b.txt")
        git(clone, "switch", "-q", "main")
        rows = _scan(clone, count_commits=True).branches
        assert [(b.name, b.unique_commits) for b in rows] == [("docs", 1)]

    def test_a_deleted_worktree_does_not_hide_its_branch(self, clone, tmp_path):
        # git still lists a deleted worktree (prunable) and its branch, but nobody
        # can be working there; counting it as checked out would hide exactly the
        # unpushed work a deleted tree leaves behind.
        wt = tmp_path / "wt"
        git(clone, "worktree", "add", "-q", "-b", "fix/abandoned", str(wt))
        commit(wt, "b.txt")
        subprocess.run(["rm", "-rf", str(wt)], check=True)
        assert [b.name for b in _scan(clone).branches] == ["fix/abandoned"]

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

    def test_an_unreadable_worktree_is_unknown_not_missing(self, clone, tmp_path, monkeypatch):
        # A permission error says nothing about whether the tree exists, and
        # "missing" would tell the reader to prune it.
        wt = tmp_path / "wt"
        git(clone, "worktree", "add", "-q", "-b", "side", str(wt))
        real_is_dir = Path.is_dir

        def is_dir(self):
            if self == wt.resolve():
                raise PermissionError("denied")
            return real_is_dir(self)
        monkeypatch.setattr(Path, "is_dir", is_dir)

        row = next(w for w in _scan(clone).worktrees if Path(w.path) == wt.resolve())

        assert row.state == UNKNOWN

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
    """Every git call that can fail, failing: the report names it and nothing
    raises. Faked at the shared runner, the one door every call goes through."""

    @staticmethod
    def _fail(monkeypatch, first_arg, rc=1, err="fatal: timed out"):
        from lib import evidence
        real = evidence.run_git

        def run_git(root, *args, **kwargs):
            if args[:1] == (first_arg,):
                return rc, "", err
            return real(root, *args, **kwargs)
        monkeypatch.setattr(evidence, "run_git", run_git)

    def test_a_failed_worktree_listing_is_not_checked_not_nothing_found(self, clone, monkeypatch):
        self._fail(monkeypatch, "worktree")
        report = _scan(clone)
        assert report.worktrees_checked is False
        assert "could not list worktrees" in report.problems
        line = sw.briefing_line(report)
        assert line is not None and "could not check" in line, "silence would read as all-clear"

    def test_a_failed_remote_listing_is_named(self, clone, monkeypatch):
        self._fail(monkeypatch, "for-each-ref")
        assert "could not list remote-tracking refs" in _scan(clone).problems

    def test_a_failed_branch_walk_is_named(self, clone, monkeypatch):
        self._fail(monkeypatch, "rev-list")
        assert "could not compare local branches with the remotes" in _scan(clone).problems

    def test_a_failed_status_leaves_the_dirty_count_unknown(self, clone, tmp_path, monkeypatch):
        git(clone, "worktree", "add", "-q", "-b", "side", str(tmp_path / "wt"))
        self._fail(monkeypatch, "status", err="output is not valid UTF-8: ...")
        rows = [w for w in _scan(clone).worktrees if not w.is_current]
        assert rows and all(w.dirty is None for w in rows)

    def test_a_blown_budget_reports_the_rest_unchecked(self, clone, tmp_path):
        for name in ("a", "b"):
            git(clone, "worktree", "add", "-q", "-b", name, str(tmp_path / name))
        report = _scan(clone, budget_seconds=-1)
        assert all(w.state == UNKNOWN for w in report.worktrees)
        assert any("scan budget" in p for p in report.problems)
        line = sw.briefing_line(report)
        assert line is not None and "not checked within" in line

    def test_an_unresolvable_home_yields_no_roots(self, monkeypatch):
        def no_home():
            raise RuntimeError("Could not determine home directory.")
        monkeypatch.setattr(sw.Path, "home", staticmethod(no_home))
        assert sw.config_roots(env={}) == []


def _row(path, state, *, current=False, dirty=0, branch="b"):
    return sw.WorktreeRow(path=path, branch=branch, is_current=current, ephemeral=None,
                          state=state, dirty=dirty)


class TestBriefingLine:
    SECRET_PATH = "/src/secret-worktree-path"
    SECRET_BRANCH = "feature/secret-branch-name"

    def test_silent_when_nothing_to_say(self):
        report = sw.Report(worktrees=[_row("/here", ACTIVE, current=True), _row("/x", RECENT)])
        assert sw.briefing_line(report) is None

    def test_counts_worktrees_and_names_nothing(self):
        report = sw.Report(
            worktrees=[
                _row("/here", ACTIVE, current=True),
                _row(self.SECRET_PATH, IDLE, dirty=3, branch=self.SECRET_BRANCH),
                _row("/src/other", IDLE),
                _row("/src/live", ACTIVE),
            ],
            branches=[sw.BranchRow(self.SECRET_BRANCH, 0.0, 2)],
        )

        line = sw.briefing_line(report)

        assert line is not None, "positive control: there is something to say"
        assert line.startswith("Worktrees: 2 idle 7+ days (1 with uncommitted changes)")
        assert "1 other with an agent active" in line
        assert "prawduct-hook worktrees" in line
        assert "branch" not in line, "stranded branches travel as advisories now"
        for name in (self.SECRET_PATH, self.SECRET_BRANCH, "/src/other", "/src/live", "secret"):
            assert name not in line, f"the briefing named {name!r} (#410)"

    def test_it_defers_to_the_user_and_to_advisories(self):
        # The delegate-worktree advisory legitimately directs cleaning up another
        # worktree; a flat "never touch" here contradicted it.
        line = sw.briefing_line(sw.Report(worktrees=[_row("/x", IDLE)]))
        assert "only when the user or an advisory asks" in line
        assert "never" not in line

    def test_the_current_worktree_is_never_counted(self):
        report = sw.Report(worktrees=[_row("/here", IDLE, current=True, dirty=5)])
        assert sw.briefing_line(report) is None

    def test_an_active_sibling_alone_is_worth_a_line(self):
        line = sw.briefing_line(sw.Report(worktrees=[_row("/here", ACTIVE, current=True), _row("/x", ACTIVE)]))
        assert line is not None and "1 other with an agent active" in line

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

    def test_json_keys_are_the_documented_contract(self, clone, capsys):
        """api-contract.md lists these keys. They come from dataclass field
        names, so a rename would change the published payload silently."""
        git(clone, "switch", "-q", "-c", "fix/orphan")
        commit(clone, "b.txt")
        git(clone, "switch", "-q", "main")
        assert sw.worktrees_cmd(clone, ["--json"]) == 0
        payload = json.loads(capsys.readouterr().out)
        assert set(payload) == {"schema_version", "worktrees", "branches", "worktrees_checked",
                                "has_remotes", "problems"}
        assert set(payload["worktrees"][0]) == {"path", "branch", "is_current", "ephemeral",
                                                "state", "last_activity", "dirty"}
        assert set(payload["worktrees"][0]["last_activity"]) == {"source", "at"}
        assert set(payload["branches"][0]) == {"name", "last_commit", "unique_commits"}
        assert payload["branches"][0]["unique_commits"] == 1, "the table asks for counts"

    def test_table_warns_that_liveness_is_inferred(self, clone, capsys):
        assert sw.worktrees_cmd(clone, []) == 0
        out = capsys.readouterr().out
        assert "this session" in out
        assert "looks idle" in out, "the reader is told liveness is inferred"
        # Deferring to advisories, not a flat "never adopt": the delegate-worktree
        # advisory legitimately directs cleanup of another worktree.
        assert "only when the user or an advisory asks" in out

    def test_unknown_argument_is_a_usage_error(self, clone, capsys):
        assert sw.worktrees_cmd(clone, ["--all"]) == 2
        assert "usage" in capsys.readouterr().err
