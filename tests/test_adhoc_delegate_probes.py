"""Tests for the unintegrated-ad-hoc-delegate advisory probe (R12).

The probe's whole claim is that an abandoned delegate worktree stops being
silent, so the cases are written as the *state* the coordinator is in rather
than as branches of the implementation:

* it fires when a worktree holds a dispatch brief on a branch nothing has
  merged — the only state R12 names;
* it goes quiet again when the coordinator does what the advisory asked, and
  each remedy is exercised by *doing* it on the fixture (merge the branch,
  remove the worktree) and re-probing, with the un-remedied fixture as the
  control — an advisory whose recommendation is never followed in a test is an
  advisory whose recommendation is untested;
* it is silent in every state a repo that has never delegated can be in, which
  is the "inert by absence" property that lets it ship to every consumer;
* it stats the brief and never reads it, because the worktree it points at
  belongs to another session.

Registry isolation mirrors ``test_stale_base_probes.py`` (autouse
``clear_registry``).
"""

from __future__ import annotations

import builtins
import subprocess
from pathlib import Path

import pytest

from lib import adhoc_delegate_probes as adp
from lib import gitstate
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


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def _commit(repo: Path, rel: str, content: str, msg: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)


def _repo(tmp_path: Path) -> Path:
    """A one-commit repo on ``main`` — the coordinator's checkout."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, "code.py", "x = 1\n", "c1")
    return repo


def _delegate(
    repo: Path,
    name: str = "delegate-a",
    *,
    brief: bool = True,
    commit: bool = True,
    rel_dir: str | None = None,
) -> Path:
    """Add a worktree on its own branch, optionally with a brief and a commit.

    ``rel_dir`` defaults to the harness's own shape
    (``.claude/worktrees/agent-<name>``) so the fixture looks like what an
    ``isolation: "worktree"`` dispatch actually produces.
    """
    rel = rel_dir or f".claude/worktrees/agent-{name}"
    path = repo / rel
    _git(repo, "worktree", "add", "-q", "-b", name, str(path))
    if brief:
        (path / adp.BRIEF_REL).parent.mkdir(parents=True, exist_ok=True)
        (path / adp.BRIEF_REL).write_text("# Brief\nOwns: the tangent.\n")
    if commit:
        _commit(path, f"{name}.py", "y = 2\n", f"{name}: work")
    return path


def _probe(root: Path):
    return list(
        adp.probe_unintegrated_delegate_worktree(ProjectState({}), make_codebase(root))
    )


# ---------------------------------------------------------------------------
# The state R12 names
# ---------------------------------------------------------------------------


class TestFires:
    def test_fires_on_unmerged_worktree_holding_a_brief(self, tmp_path):
        repo = _repo(tmp_path)
        _delegate(repo)
        found = _probe(repo)
        assert len(found) == 1
        cand = found[0]
        assert cand.type == "unintegrated-delegate-worktree"
        assert cand.priority == "warn"
        # Names the branch — the acceptance criterion's first half.
        assert "delegate-a" in cand.trigger_summary
        assert "delegate-a" in cand.evidence[0]
        # ...and what it owes — the second half.
        assert "integrate" in cand.trigger_summary
        assert "abandon" in cand.trigger_summary

    def test_worktree_path_is_named_so_it_can_be_removed(self, tmp_path):
        repo = _repo(tmp_path)
        _delegate(repo)
        cand = _probe(repo)[0]
        assert ".claude/worktrees/agent-delegate-a" in cand.trigger_summary
        assert any("git worktree remove" in a for a in cand.alternative_actions)

    def test_recommended_action_shows_what_the_branch_carries(self, tmp_path):
        repo = _repo(tmp_path)
        _delegate(repo)
        cand = _probe(repo)[0]
        assert cand.recommended_action == "git log --oneline HEAD..delegate-a"
        # And it runs, in the coordinator's checkout, naming the delegate's commit.
        out = _git(repo, *cand.recommended_action.split()[1:])
        assert "delegate-a: work" in out

    def test_one_advisory_per_worktree_with_distinct_ids(self, tmp_path):
        repo = _repo(tmp_path)
        _delegate(repo, "delegate-a")
        _delegate(repo, "delegate-b")
        found = _probe(repo)
        assert len(found) == 2
        ids = {
            compute_id(adp.FEATURE, c.type, adp.PROBE_VERSION, c.evidence) for c in found
        }
        assert len(ids) == 2, "dismissing one abandoned delegate must not silence the other"

    def test_detached_worktree_is_named_by_its_commit(self, tmp_path):
        repo = _repo(tmp_path)
        path = _delegate(repo)
        sha = _git(path, "rev-parse", "HEAD")
        _git(path, "checkout", "-q", "--detach")
        cand = _probe(repo)[0]
        assert sha[:12] in cand.trigger_summary
        assert sha[:12] in cand.evidence[0]


# ---------------------------------------------------------------------------
# Following the advice actually silences it (the control is TestFires above)
# ---------------------------------------------------------------------------


class TestRemediesWork:
    def test_merging_the_branch_clears_it(self, tmp_path):
        repo = _repo(tmp_path)
        _delegate(repo)
        assert _probe(repo), "control: fires before the merge"
        _git(repo, "merge", "-q", "--no-ff", "-m", "integrate delegate-a", "delegate-a")
        assert _probe(repo) == [], "integrating is the resolution the advisory names"

    def test_removing_the_worktree_clears_it(self, tmp_path):
        repo = _repo(tmp_path)
        path = _delegate(repo)
        assert _probe(repo), "control: fires before the removal"
        _git(repo, "worktree", "remove", "--force", str(path))
        assert _probe(repo) == []

    def test_merged_into_the_integration_base_clears_it(self, tmp_path):
        """HEAD is not the only place a delegate can have landed."""
        repo = _repo(tmp_path)
        _delegate(repo)
        _git(repo, "merge", "-q", "--no-ff", "-m", "integrate delegate-a", "delegate-a")
        _git(repo, "checkout", "-q", "-b", "unrelated", "HEAD~1")
        _commit(repo, "later.py", "z = 3\n", "unrelated work")
        # HEAD (branch `unrelated`) does not contain the delegate; base `main` does.
        assert _probe(repo) == []


# ---------------------------------------------------------------------------
# Inert by absence — every state a repo that never delegated can be in
# ---------------------------------------------------------------------------


class TestInert:
    def test_silent_with_no_linked_worktrees(self, tmp_path):
        assert _probe(_repo(tmp_path)) == []

    def test_silent_when_the_worktree_holds_no_brief(self, tmp_path):
        repo = _repo(tmp_path)
        _delegate(repo, brief=False)
        assert _probe(repo) == [], "an ordinary feature worktree is not a delegate"

    def test_silent_when_the_delegate_committed_nothing(self, tmp_path):
        repo = _repo(tmp_path)
        _delegate(repo, commit=False)
        assert _probe(repo) == [], "nothing to integrate is nothing to nag about"

    def test_silent_about_the_sessions_own_worktree(self, tmp_path):
        """A brief in your own tree is this session's dispatch record, not a debt.

        Falls out of the integration test rather than a special case: the tree
        you are standing in is always reachable from its own HEAD.
        """
        repo = _repo(tmp_path)
        path = _delegate(repo)
        assert _probe(path) == []

    def test_silent_on_a_non_git_directory(self, tmp_path):
        plain = tmp_path / "plain"
        plain.mkdir()
        assert _probe(plain) == []


# ---------------------------------------------------------------------------
# The worktree boundary
# ---------------------------------------------------------------------------


class TestWorktreeBoundary:
    def test_the_brief_is_stat_ed_and_never_read(self, tmp_path, monkeypatch):
        """Presence is the whole signal; the contents belong to the other session."""
        repo = _repo(tmp_path)
        path = _delegate(repo)
        brief = (path / adp.BRIEF_REL).resolve()

        # Every route to the bytes, not just the two the probe happens not to
        # use: a guard that pins only today's spelling stays green through the
        # edit it exists to catch.
        opened: list[str] = []

        for owner, name in ((Path, "open"), (Path, "read_text"), (Path, "read_bytes")):
            real = getattr(owner, name)

            def _tracking(self, *args, _real=real, **kwargs):
                opened.append(str(Path(self).resolve()))
                return _real(self, *args, **kwargs)

            monkeypatch.setattr(owner, name, _tracking)

        real_builtin_open = builtins.open

        def _tracking_builtin_open(file, *args, **kwargs):
            opened.append(str(Path(file).resolve()))
            return real_builtin_open(file, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", _tracking_builtin_open)
        assert _probe(repo), "control: the probe did fire, so it did look"
        assert str(brief) not in opened


# ---------------------------------------------------------------------------
# Registration — the roster call site, not the module
# ---------------------------------------------------------------------------


class TestRegistration:
    def test_registered_probe_produces_a_stamped_candidate(self, tmp_path):
        repo = _repo(tmp_path)
        _delegate(repo)
        adp.register()
        produced = run_all_probes(ProjectState({}), make_codebase(repo))
        assert len(produced) == 1
        assert produced[0].feature == "delegation"
        assert produced[0].probe_version == adp.PROBE_VERSION

    def test_in_the_production_roster(self, tmp_path):
        from lib import probe_families

        probe_families.register_all()
        repo = _repo(tmp_path)
        _delegate(repo)
        produced = run_all_probes(ProjectState({}), make_codebase(repo))
        assert any(
            c.type == "unintegrated-delegate-worktree" for c in produced
        ), "a probe missing from the composition root reaches no call site"


# ---------------------------------------------------------------------------
# It reaches the surface a human actually sees, and leaves it again
# ---------------------------------------------------------------------------


class TestReachesTheBriefing:
    def test_surfaces_in_the_briefing_and_clears_when_integrated(self, tmp_path):
        from lib import briefing
        from lib.advisory_store import run_sync_advisories

        repo = _repo(tmp_path)
        (repo / ".prawduct").mkdir(exist_ok=True)
        _delegate(repo)
        adp.register()

        run_sync_advisories(repo)
        text = briefing.assemble_session_briefing(repo, [])
        assert "ADVISORIES" in text
        assert "delegate-a is unintegrated" in text
        # `warn` is what makes the briefing tell the user rather than leaving it
        # to the agent — abandoning a delegate is the owner's call.
        assert briefing.ADVISORY_RELAY_MARKER in text

        raised = [
            a
            for a in gitstate._read_advisory_store(repo / ".prawduct")["advisories"]
            if a.get("type") == "unintegrated-delegate-worktree"
        ]
        assert len(raised) == 1
        advisory_id = raised[0]["id"]

        _git(repo, "merge", "-q", "--no-ff", "-m", "integrate delegate-a", "delegate-a")
        run_sync_advisories(repo)
        # Looked up by id, not by type: a resolved entry is compacted down to
        # its id and terminal state, so type is gone by the time it matters.
        after = {
            a["id"]: a
            for a in gitstate._read_advisory_store(repo / ".prawduct")["advisories"]
        }
        assert after[advisory_id]["state"] == "resolved"
        assert after[advisory_id]["resolved_by"] == "sync"
        assert "delegate-a is unintegrated" not in briefing.assemble_session_briefing(repo, [])


class TestDisplayPath:
    def test_a_worktree_inside_the_clone_is_named_relatively(self, tmp_path, monkeypatch):
        """Even when the probe is rooted at a relative path, as `.` is."""
        repo = _repo(tmp_path)
        _delegate(repo)
        monkeypatch.chdir(repo)
        cand = _probe(Path("."))[0]
        assert ".claude/worktrees/agent-delegate-a" in cand.trigger_summary
        assert str(repo) not in cand.trigger_summary


# ---------------------------------------------------------------------------
# Fails soft, never silent
# ---------------------------------------------------------------------------


class TestDegradesLoudly:
    def test_a_failed_worktree_list_says_what_was_lost(self, tmp_path, monkeypatch, capsys):
        repo = _repo(tmp_path)
        _delegate(repo)
        real = adp.evidence.run_git

        def _fail_worktree_list(root, *args, **kwargs):
            if args[:1] == ("worktree",):
                return 1, "", "fatal: timed out"
            return real(root, *args, **kwargs)

        monkeypatch.setattr(adp.evidence, "run_git", _fail_worktree_list)
        assert _probe(repo) == []
        err = capsys.readouterr().err
        assert "delegate-worktree probe skipped" in err
        assert "would go unreported" in err

    def test_a_non_git_directory_stays_quiet(self, tmp_path, capsys):
        """The ordinary case for a probe that can be pointed anywhere."""
        plain = tmp_path / "plain"
        plain.mkdir()
        assert _probe(plain) == []
        assert capsys.readouterr().err == ""

    def test_an_unresolvable_base_names_the_over_fire_risk(self, tmp_path, monkeypatch, capsys):
        repo = _repo(tmp_path)
        _delegate(repo)
        from lib import coverage

        monkeypatch.setattr(
            coverage, "_resolve_base_branch", lambda root: (None, "configured base_branch 'nope' not found")
        )
        assert _probe(repo), "still fires — HEAD alone answers the ordinary case"
        err = capsys.readouterr().err
        assert "integration base unresolved" in err
        assert "may be reported unintegrated" in err
