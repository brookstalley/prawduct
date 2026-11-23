"""`pick` annotates a candidate that commits on the base branch already name.

A batch once picked an item as ready whose legs had shipped on develop days
earlier: the issue stayed open because one leg remained, the labels and body are
records, and nothing at pick time looked at the code history. These tests pin the
advice (a note on the candidate, never a hidden or restaged one) and the
properties that make it safe to leave on: a whole-number match (#12 is not #123),
this-checkout-only, bounded, and fail-soft.

All offline: a real `git init` fixture, the transport-seam fake for the provider.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent / "plugin"
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.backlog import cli, core, query, transport  # noqa: E402
from lib.backlog.transport import TransportError  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402

OWNER, REPO = "octo", "repo"
NOW = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)


def _git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd, check=True, capture_output=True,
    )


def _commit(cwd, message):
    _git(cwd, "commit", "--allow-empty", "-q", "-m", message)


@pytest.fixture
def repo_dir(tmp_path):
    """A work tree on `main` whose `origin` is octo/repo, the tracker `pick` reads."""
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "remote", "add", "origin", f"https://github.com/{OWNER}/{REPO}.git")
    _commit(tmp_path, "initial")
    return tmp_path


@pytest.fixture
def fake():
    """A provider holding 13 issues: #1-#11 plain (out of scope), #12 and #13 ready."""
    gh = FakeGitHub(user={"login": "agent-a", "id": 1})
    for n in range(1, 12):
        gh.create_issue(OWNER, REPO, title=f"plain issue {n}", body="x", labels=[])
    for title in ("pick: the twelfth item under test", "pick: the thirteenth item under test"):
        done = core.file_item(
            gh, owner=OWNER, repo=REPO, title=title, body="b", facets={"stage": "ready"}
        )
        assert done["status"] == "ok", done
    assert [c for c in (f"{OWNER}/{REPO}#12", f"{OWNER}/{REPO}#13")] == sorted(
        f"{OWNER}/{REPO}#{i['number']}" for i in gh._repo(OWNER, REPO).issues.values() if i["number"] > 11
    )
    return gh


def _pick(fake, repo_dir, **kwargs):
    return query.pick(
        fake, project_dir=repo_dir, owner=OWNER, repo=REPO, now=NOW, limit=5, **kwargs
    )


def _by_id(result):
    assert result["status"] == "ok", result
    return {c["id"]: c for c in result["data"]["candidates"]}


ID12, ID13 = f"{OWNER}/{REPO}#12", f"{OWNER}/{REPO}#13"


class TestAnnotation:
    def test_a_commit_naming_12_annotates_12_and_not_13(self, fake, repo_dir):
        _commit(repo_dir, "feat: legs 2 and 3 of #12")
        cands = _by_id(_pick(fake, repo_dir))
        assert set(cands) == {ID12, ID13}  # the control: both were offered
        hist = cands[ID12]["base_history"]
        assert hist["base"] == "main" and hist["count"] == 1
        assert len(hist["shas"]) == 1
        note = hist["note"]
        assert note == (
            f"1 commit(s) on main already name this item: {hist['shas'][0]}; "
            "check what is left before building"
        )
        assert "base_history" not in cands[ID13]

    def test_a_body_only_mention_is_not_a_commit_naming_the_item(self, fake, repo_dir):
        """Bodies mention items in passing ("why #12 stayed deferred"); only a
        subject names the item the commit is work on. The annotation is read as
        'someone already built part of this', so a passing mention is noise."""
        _commit(repo_dir, "docs: record the design\n\nwhy #12 stayed deferred, and #13 too")
        result = _pick(fake, repo_dir)
        assert all("base_history" not in c for c in _by_id(result).values())
        # Control: the same mention in a subject annotates, so the verdict above
        # is the subject rule and not a repo the check never reached.
        _commit(repo_dir, "feat: legs 2 and 3 of #12\n\nbody text")
        cands = _by_id(_pick(fake, repo_dir))
        assert cands[ID12]["base_history"]["count"] == 1
        assert "base_history" not in cands[ID13]

    def test_subject_matches_behind_many_body_only_mentions_are_still_found(self, fake, repo_dir):
        _commit(repo_dir, "feat: leg 1 of #12")
        for i in range(30):
            _commit(repo_dir, f"docs: note {i}\n\nwhy #12 stayed deferred")
        hist = _by_id(_pick(fake, repo_dir))[ID12]["base_history"]
        assert hist["count"] == 1  # the 30 body mentions are not counted

    def test_a_qualified_reference_in_another_case_still_annotates(self, fake, repo_dir):
        _commit(repo_dir, "feat: legs 2 and 3 of OCTO/REPO#12")
        cands = _by_id(_pick(fake, repo_dir))
        assert cands[ID12]["base_history"]["count"] == 1
        assert "base_history" not in cands[ID13]

    def test_another_repos_qualified_reference_ending_in_this_one_does_not(self, fake, repo_dir):
        _commit(repo_dir, "feat: legs of xocto/repo#12")
        assert all("base_history" not in c for c in _by_id(_pick(fake, repo_dir)).values())

    def test_the_annotation_is_advice_only_nothing_is_hidden_or_restaged(self, fake, repo_dir):
        before = _by_id(_pick(fake, repo_dir))
        _commit(repo_dir, "feat: #12 and #13")
        after = _by_id(_pick(fake, repo_dir))
        assert set(after) == set(before)
        for cid, cand in after.items():
            assert cand["stage"] == before[cid]["stage"] == "ready"
            assert cand["status"] == before[cid]["status"]

    def test_no_commit_naming_either_item_means_no_annotation(self, fake, repo_dir):
        _commit(repo_dir, "chore: unrelated, mentions #1 and #120")
        cands = _by_id(_pick(fake, repo_dir))
        assert all("base_history" not in c for c in cands.values())

    def test_only_the_base_branch_is_read_not_other_branches(self, fake, repo_dir):
        _git(repo_dir, "checkout", "-q", "-b", "feature/x")
        _commit(repo_dir, "wip: #12 on a branch that has not landed")
        _git(repo_dir, "checkout", "-q", "main")
        cands = _by_id(_pick(fake, repo_dir))
        assert "base_history" not in cands[ID12]

    def test_a_configured_base_branch_is_the_branch_read(self, fake, repo_dir):
        _git(repo_dir, "checkout", "-q", "-b", "develop")
        _commit(repo_dir, "feat: leg 1 of #13")
        _git(repo_dir, "checkout", "-q", "main")
        state = repo_dir / ".prawduct" / "project-state.yaml"
        state.parent.mkdir()
        state.write_text("base_branch: develop\n")
        cands = _by_id(_pick(fake, repo_dir))
        assert cands[ID13]["base_history"]["base"] == "develop"
        assert "base_history" not in cands[ID12]

    def test_the_cli_prints_the_note_and_json_carries_the_field(self, fake, repo_dir, capsys):
        _commit(repo_dir, "feat: legs 2 and 3 of #12")
        assert cli.run(repo_dir, ["pick", "--repo", "octo/repo", "--limit", "5"], transport=fake) == 0
        out = capsys.readouterr().out
        assert "history: 1 commit(s) on main already name this item:" in out
        assert out.count("history:") == 1  # #13 carries none

        cli.run(repo_dir, ["pick", "--repo", "octo/repo", "--limit", "5", "--json"], transport=fake)
        env = json.loads(capsys.readouterr().out)
        by_id = {c["id"]: c for c in env["data"]["candidates"]}
        assert by_id[ID12]["base_history"]["count"] == 1


class TestPatternIsAWholeReference:
    """`\\b` is a GNU extension, so the boundary is spelled out and tested."""

    def _names(self, repo_dir, number, scope=f"{OWNER}/{REPO}"):
        rows = transport.git_log_subjects(repo_dir, "main", max_count=100)
        return query._history_matches(rows, scope, number)

    def test_12_does_not_match_123_or_1204(self, repo_dir):
        _commit(repo_dir, "fix: closes #123")
        _commit(repo_dir, "fix: closes #1204 and more")
        _commit(repo_dir, "fix: closes #120")
        assert self._names(repo_dir, 12) == []
        # The instrument returns non-empty for the number actually named, so the
        # empty answer above is a verdict and not a pattern that matches nothing.
        assert len(self._names(repo_dir, 123)) == 1
        assert len(self._names(repo_dir, 1204)) == 1

    def test_12_matches_at_every_boundary_it_should(self, repo_dir):
        for message in (
            "#12 leads the subject",
            "ends with #12",
            "(#12) parenthesised",
            "fixes #12.",
            "follows a comma: #7,#12",
            "qualified octo/repo#12 form",
        ):
            _commit(repo_dir, message)
        assert len(self._names(repo_dir, 12)) == 6

    def test_another_repos_issue_12_is_not_this_item(self, repo_dir):
        _commit(repo_dir, "see other/repo#12 upstream")
        _commit(repo_dir, "see brookstalley/prawduct#12")
        assert self._names(repo_dir, 12) == []

    def test_the_qualified_form_is_case_insensitive_and_has_a_leading_boundary(self, repo_dir):
        """`pick --repo BrooksTalley/Prawduct` must still see a lower-case
        `brookstalley/prawduct#12` (GitHub owners and repos are case-insensitive), and
        `xocto/repo#12` is another repo's issue, as `x#12` is not this item's."""
        _commit(repo_dir, "see OCTO/REPO#12 upstream")
        _commit(repo_dir, "see xocto/repo#12")
        _commit(repo_dir, "see foo-octo/repo#12")
        _commit(repo_dir, "see (octo/repo#12)")
        assert len(self._names(repo_dir, 12)) == 2
        assert len(self._names(repo_dir, 12, scope="Octo/Repo")) == 2

    def test_a_regex_dot_in_the_repo_name_is_literal(self, repo_dir):
        _commit(repo_dir, "see octo/reXpo#12")
        rows = transport.git_log_subjects(repo_dir, "main", max_count=100)
        assert query._history_matches(rows, "octo/re.po", 12) == []


class TestOnlyThisCheckoutsTracker:
    def test_a_service_repo_that_is_not_origin_is_not_annotated_and_stays_quiet(self, fake, repo_dir):
        _git(repo_dir, "remote", "set-url", "origin", "https://github.com/octo/product-code.git")
        _commit(repo_dir, "feat: #12 in the code repo's own number space")
        result = _pick(fake, repo_dir)
        assert all("base_history" not in c for c in _by_id(result).values())
        assert not any("history" in w for w in result["warnings"])

    def test_origin_is_compared_case_insensitively(self, fake, repo_dir):
        _git(repo_dir, "remote", "set-url", "origin", "https://github.com/Octo/Repo.git")
        _commit(repo_dir, "feat: #12")
        assert "base_history" in _by_id(_pick(fake, repo_dir))[ID12]

    def test_a_checkout_with_no_origin_is_not_annotated(self, fake, repo_dir):
        _git(repo_dir, "remote", "remove", "origin")
        _commit(repo_dir, "feat: #12")
        result = _pick(fake, repo_dir)
        assert all("base_history" not in c for c in _by_id(result).values())


class TestFailSoft:
    def test_an_unresolvable_base_adds_one_note_and_no_annotation(self, fake, repo_dir, monkeypatch):
        _commit(repo_dir, "feat: #12")
        monkeypatch.setattr(query, "resolve_base_ref", lambda _d: (None, "no base candidate resolved"))
        result = _pick(fake, repo_dir)
        assert all("base_history" not in c for c in _by_id(result).values())
        notes = [w for w in result["warnings"] if "base-branch history not checked" in w]
        assert len(notes) == 1 and "no base candidate resolved" in notes[0]

    def test_a_failed_git_log_stops_the_pass_with_one_note(self, fake, repo_dir, monkeypatch):
        calls = []

        def broken(*args, **kwargs):
            calls.append(args)
            raise TransportError("unavailable", "'git log' exited 128: bad revision")

        monkeypatch.setattr(query, "git_log_subjects", broken)
        result = _pick(fake, repo_dir)
        assert all("base_history" not in c for c in _by_id(result).values())
        assert len(calls) == 1  # a broken git is not retried per candidate
        notes = [w for w in result["warnings"] if "base-branch history not checked" in w]
        assert len(notes) == 1 and "exited 128" in notes[0]

    def test_the_note_reaches_stderr_in_human_mode(self, fake, repo_dir, monkeypatch, capsys):
        monkeypatch.setattr(query, "resolve_base_ref", lambda _d: (None, "nothing resolved"))
        assert cli.run(repo_dir, ["pick", "--repo", "octo/repo"], transport=fake) == 0
        err = capsys.readouterr().err
        assert "warning: base-branch history not checked (nothing resolved)" in err

    def test_git_log_subjects_maps_each_failure_to_a_transport_error(self, repo_dir, tmp_path):
        with pytest.raises(TransportError):  # a ref that does not exist: git exits non-zero
            transport.git_log_subjects(repo_dir, "no-such-ref", max_count=1)
        with pytest.raises(TransportError):  # not a repository
            transport.git_log_subjects(tmp_path / "missing", "main", max_count=1)
        with pytest.raises(TransportError):  # an option-shaped ref is refused, not run
            transport.git_log_subjects(repo_dir, "--all", max_count=1)

    def test_a_timeout_is_a_transport_error(self, repo_dir, monkeypatch):
        def slow(*_a, **kw):
            assert kw["timeout"] == transport.GIT_READ_TIMEOUT_S
            raise subprocess.TimeoutExpired(cmd="git", timeout=kw["timeout"])

        monkeypatch.setattr(transport.subprocess, "run", slow)
        with pytest.raises(TransportError, match="timed out"):
            transport.git_log_subjects(repo_dir, "main", max_count=1)

    def test_resolve_base_ref_never_raises_on_an_unrunnable_git(self, repo_dir, monkeypatch):
        from lib import coverage

        def boom(_dir):
            raise subprocess.TimeoutExpired(cmd="git", timeout=1)

        monkeypatch.setattr(coverage, "repo_base_branch", boom)
        ref, reason = transport.resolve_base_ref(repo_dir)
        assert ref is None and "TimeoutExpired" in reason


def _many_ready_items(count):
    gh = FakeGitHub(user={"login": "agent-a", "id": 1})
    for i in range(count):
        done = core.file_item(
            gh, owner=OWNER, repo=REPO, title=f"pick: ready item number {i} under test",
            body="b", facets={"stage": "ready"},
        )
        assert done["status"] == "ok", done
    return gh


class TestBounded:
    def test_one_bounded_walk_serves_every_candidate(self, repo_dir, monkeypatch):
        """The cost is the walk, so the test counts walks: a per-candidate `git log
        --grep` stops after N MATCHES, so for an item few messages name it reads the
        whole history, once per candidate. One walk, capped by commits, is the bound."""
        gh = _many_ready_items(13)
        _commit(repo_dir, "feat: leg 1 of #7")
        walks = []
        real = subprocess.run

        def spy(argv, *a, **kw):
            if isinstance(argv, list) and argv[:2] == ["git", "log"]:
                walks.append(argv)
            return real(argv, *a, **kw)

        monkeypatch.setattr(transport.subprocess, "run", spy)
        result = query.pick(gh, project_dir=repo_dir, owner=OWNER, repo=REPO, now=NOW, limit=13)
        assert result["data"]["count"] == 13  # no candidate dropped
        assert len(walks) == 1, walks
        argv = walks[0]
        assert "--max-count=1000" in argv  # absolute: the chosen window, not a constant echoing itself
        assert not any(a.startswith("--grep") for a in argv)  # the match is not left to git
        by_id = _by_id(result)
        assert set(c for c, v in by_id.items() if "base_history" in v) == {f"{OWNER}/{REPO}#7"}

    def test_the_walk_reads_at_most_the_newest_commits_and_says_so(self, repo_dir, monkeypatch):
        monkeypatch.setattr(query, "_HISTORY_WALK_COMMITS", 3)
        gh = _many_ready_items(13)
        _commit(repo_dir, "feat: the oldest leg of #12")
        _commit(repo_dir, "chore: filler 1")
        _commit(repo_dir, "chore: filler 2")
        _commit(repo_dir, "feat: a newer leg of #13")
        result = query.pick(gh, project_dir=repo_dir, owner=OWNER, repo=REPO, now=NOW, limit=13)
        by_id = _by_id(result)
        assert "base_history" not in by_id[ID12]  # past the window: an accepted undercount
        newer = by_id[ID13]["base_history"]
        assert newer["capped"] is True
        assert "in the last 3 commits on main" in newer["note"]
        assert result["data"]["base_history"] == {
            "checked": True, "base": "main", "walked": 3, "capped": True,
        }

    def test_a_walk_inside_the_window_is_not_marked_capped(self, fake, repo_dir):
        _commit(repo_dir, "feat: #12")
        result = _pick(fake, repo_dir)
        hist = _by_id(result)[ID12]["base_history"]
        assert hist["capped"] is False and "in the last" not in hist["note"]
        assert result["data"]["base_history"]["capped"] is False

    def test_shas_listed_are_capped_and_the_remainder_is_exact(self, fake, repo_dir):
        for i in range(8):
            _commit(repo_dir, f"feat: part {i} of #12")
        hist = _by_id(_pick(fake, repo_dir))[ID12]["base_history"]
        assert hist["count"] == 8 and len(hist["shas"]) == query._HISTORY_SHAS_LISTED
        assert "8 commit(s)" in hist["note"] and "and 3 more" in hist["note"]

    def test_a_capped_walk_never_prints_an_inexact_remainder(self, repo_dir, monkeypatch):
        """With the window full, the matches in it are all counted: '10 ... and 5
        more' is exact for that window and says which window, rather than a '20+'
        beside a remainder computed from an already-truncated list."""
        monkeypatch.setattr(query, "_HISTORY_WALK_COMMITS", 10)
        gh = _many_ready_items(13)
        for i in range(15):
            _commit(repo_dir, f"feat: part {i} of #12")
        result = query.pick(gh, project_dir=repo_dir, owner=OWNER, repo=REPO, now=NOW, limit=13)
        hist = _by_id(result)[ID12]["base_history"]
        assert hist["capped"] is True and hist["count"] == 10
        assert "10 commit(s) in the last 10 commits on main" in hist["note"]
        assert "and 5 more" in hist["note"]


class TestIndicator:
    """A skipped check and 'checked, nothing matched' must not read the same."""

    def test_checked_and_nothing_matched(self, fake, repo_dir):
        _commit(repo_dir, "chore: unrelated")
        result = _pick(fake, repo_dir)
        assert all("base_history" not in c for c in _by_id(result).values())
        assert result["data"]["base_history"] == {
            "checked": True, "base": "main", "walked": 2, "capped": False,
        }

    def test_a_scope_that_is_not_origin_reports_why_it_was_skipped(self, fake, repo_dir):
        _git(repo_dir, "remote", "set-url", "origin", "https://github.com/octo/product-code.git")
        result = _pick(fake, repo_dir)
        ind = result["data"]["base_history"]
        assert ind["checked"] is False and "origin" in ind["reason"]
        assert not any("history" in w for w in result["warnings"])  # still quiet on stderr

    def test_no_readable_origin_reports_why(self, fake, repo_dir):
        _git(repo_dir, "remote", "remove", "origin")
        ind = _pick(fake, repo_dir)["data"]["base_history"]
        assert ind["checked"] is False and "origin" in ind["reason"]

    def test_an_unresolvable_base_or_failed_git_reports_why(self, fake, repo_dir, monkeypatch):
        with monkeypatch.context() as m:
            m.setattr(query, "resolve_base_ref", lambda _d: (None, "no base candidate resolved"))
            ind = _pick(fake, repo_dir)["data"]["base_history"]
        assert ind == {"checked": False, "reason": "no base candidate resolved"}

        def broken(*_a, **_k):
            raise TransportError("unavailable", "'git log' exited 128: bad revision")

        monkeypatch.setattr(query, "git_log_subjects", broken)
        ind = _pick(fake, repo_dir)["data"]["base_history"]
        assert ind["checked"] is False and "exited 128" in ind["reason"]

    def test_json_output_carries_it(self, fake, repo_dir, capsys):
        cli.run(repo_dir, ["pick", "--repo", "octo/repo", "--limit", "5", "--json"], transport=fake)
        env = json.loads(capsys.readouterr().out)
        assert env["data"]["base_history"]["checked"] is True


class TestMovingFallbackIsNotABase:
    """`coverage.repo_base_branch` can end on the moving `HEAD~1`. As a 'shipped
    history' it would report the branch's OWN commits as already on the base."""

    def _trunk_repo(self, repo_dir):
        _git(repo_dir, "branch", "-m", "main", "trunk")  # no main, no origin/main, no base_branch
        _commit(repo_dir, "feat: the branch's own leg of #12")

    def test_resolve_base_ref_refuses_the_fallback(self, repo_dir):
        self._trunk_repo(repo_dir)
        ref, reason = transport.resolve_base_ref(repo_dir)
        assert ref is None and "HEAD~1" in reason

    def test_pick_skips_the_annotation_with_a_warning(self, fake, repo_dir):
        self._trunk_repo(repo_dir)
        result = _pick(fake, repo_dir)
        assert all("base_history" not in c for c in _by_id(result).values())
        notes = [w for w in result["warnings"] if "base-branch history not checked" in w]
        assert len(notes) == 1 and "HEAD~1" in notes[0]
        assert result["data"]["base_history"]["checked"] is False

    def test_control_the_same_repo_with_a_real_base_is_annotated(self, fake, repo_dir):
        self._trunk_repo(repo_dir)
        _git(repo_dir, "branch", "main")  # a real base now exists and holds the commit
        cands = _by_id(_pick(fake, repo_dir))
        assert cands[ID12]["base_history"]["base"] == "main"


def test_the_egress_boundary_still_holds_for_the_new_git_reads():
    """The subprocess lives in transport.py; the annotation logic in query.py
    reaches git only through it."""
    src = (_REPO_ROOT / "lib" / "backlog" / "query.py").read_text()
    assert "subprocess" not in src
