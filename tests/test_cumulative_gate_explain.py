"""Both review gates say WHY a span is uncovered (#1000).

An ``uncovered`` verdict used to read the same whether the base advanced, the
branch's own committed head changed since its last review, or an uncommitted
file defeated the transfer's suite match — so a builder ran another cumulative
round blind, or followed a remedy ("run the suite and record") that, repeated
in the same dirty tree, can never reach the state the gate asks for.

One function explains (``coverage.explain_uncovered``), one function renders
(``coverage.format_uncovered_cause``), and both gates print its ``CAUSE:`` line
directly after their uncovered line. Explanation only: every verdict here is
the one the gate reached before this change, and the control cases pin that.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
import sys
from pathlib import Path

from conftest import SHAPED_REFLECTION
from test_cumulative_gate import (
    _advanced_base_repo,
    _branch_repo,
    _commit,
    _fact,
    _git,
    _head,
    _run_gate,
    _tree,
    _write_test_evidence,
)

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))
from lib import coverage, evidence, gates  # noqa: E402

_hook_loader = importlib.machinery.SourceFileLoader(
    "prawduct_hook_gate_explain", str(ROOT / "bin" / "prawduct-hook")
)
_hook = importlib.util.module_from_spec(
    importlib.util.spec_from_loader("prawduct_hook_gate_explain", _hook_loader)
)
_hook_loader.exec_module(_hook)


def _cause_line(err: str) -> str:
    """The one ``CAUSE:`` line, asserting there is exactly one and that it
    sits directly after the line naming the uncovered span."""
    lines = err.splitlines()
    causes = [i for i, ln in enumerate(lines) if ln.lstrip().startswith("CAUSE:")]
    assert len(causes) == 1, err
    i = causes[0]
    prev = lines[i - 1].strip() if i > 0 else ""
    # The PR gate's `uncovered: …` line, or the Stop blocker's span line.
    assert prev.startswith("uncovered:") or prev.startswith("changes"), err
    return lines[i].strip()


def _review_id(repo: Path) -> str:
    facts = [f for f in evidence.read_facts(repo)["facts"] if f.get("kind") == "review"]
    return facts[-1]["id"]


# ---------------------------------------------------------------------------
# PR gate (check-cumulative-critic)
# ---------------------------------------------------------------------------


class TestPrGateCause:
    def test_a_base_advance_and_a_head_change_are_both_named(self, tmp_path, capsys):
        """(a) Reviewed at the tip, the base advanced into the branch AND a
        branch file changed after it. Both causes hold, in the fixed order, and
        the advance's own file is not reported as the branch's change."""
        repo, _pb, _ph = _advanced_base_repo(tmp_path)
        review = _review_id(repo)
        _commit(repo, "feature.py", "y = 2  # touched up\n", "tweak after merge")
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        cause = _cause_line(err)
        head = f"committed head changed since review {review}: feature.py"
        base = f"base advanced since review {review}"
        assert head in cause and base in cause, cause
        assert cause.index(head) < cause.index(base)
        assert "the branch's own diff also changed, so the transfer cannot apply" in cause
        assert "upstream.py" not in cause

    def test_a_base_advance_alone_says_nothing_of_the_head(self, tmp_path, capsys):
        """The control for (a): with the branch's diff untouched, the head
        cause must NOT be printed, and the transfer is not called impossible."""
        repo, _pb, _ph = _advanced_base_repo(tmp_path)
        review = _review_id(repo)
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        cause = _cause_line(err)
        assert cause == f"CAUSE: base advanced since review {review}.", cause

    def test_an_uncommitted_suite_coupled_file_is_named_with_a_remedy_that_reaches(
        self, tmp_path, capsys
    ):
        """(b) Base advanced only, and the suite last ran with a tracked
        suite-coupled file modified and uncommitted. The CAUSE names it as
        uncommitted, the remedy is the stash route — and following it reaches
        the state: restored, re-run, recorded, the same HEAD transfers."""
        repo, _pb, _ph = _advanced_base_repo(tmp_path)
        (repo / "code.py").write_text("x = 1  # local experiment\n")
        _write_test_evidence(repo)  # the run met the DIRTY tree
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        cause = _cause_line(err)
        assert "uncommitted: code.py" in cause, cause
        assert "not part of the PR candidate, and the gate ignores them" in cause
        assert "a suite run in this tree vouches for the working tree, not HEAD" in cause
        assert "git stash push -- code.py" in err
        assert "then `git stash pop`" in err

        head_before = _head(repo)
        _git(repo, "checkout", "--", "code.py")
        _write_test_evidence(repo)
        rc, out, err = _run_gate(repo, capsys)
        assert rc == 0, err
        assert "transferred across base advance" in out
        assert _head(repo) == head_before

    def test_a_clean_tree_near_miss_keeps_the_plain_suite_remedy(self, tmp_path, capsys):
        """The control for (b): nothing uncommitted, so no stash is named — a
        plain suite run in this tree DOES meet HEAD."""
        repo, _pb, prior_head = _advanced_base_repo(tmp_path)
        _write_test_evidence(repo, tree=prior_head)
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "ONLY condition denying the transfer" in err
        assert "git stash" not in err
        assert "uncommitted" not in _cause_line(err)

    def test_an_uncommitted_untracked_file_is_stashed_with_untracked(
        self, tmp_path, capsys
    ):
        """`git stash push -- <path>` refuses a path git does not track, so an
        untracked suite-coupled file gets the flag that makes the remedy run."""
        repo, _pb, _ph = _advanced_base_repo(tmp_path)
        (repo / "scratch.py").write_text("s = 1\n")
        _write_test_evidence(repo)
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        assert "uncommitted: scratch.py" in _cause_line(err)
        assert "git stash push --include-untracked -- scratch.py" in err

    def test_a_staged_rename_lists_both_names_and_the_remedy_reaches(
        self, tmp_path, capsys
    ):
        """Critic O-1: porcelain `git diff` honours `diff.renames`, so a staged
        `git mv code.py moved.py` read as `moved.py` alone, and the stash route
        left the staged deletion of `code.py` behind — the tree still did not
        meet HEAD. Both names are now listed. And because `git stash push --
        <path>` refuses a path the index deleted (git 2.54: "did not match any
        file(s) known to git"), naming both would not run either: the route sets
        the whole tree aside. Following it reaches, and the pop restores."""
        repo, _pb, _ph = _advanced_base_repo(tmp_path)
        _git(repo, "config", "diff.renames", "true")
        _git(repo, "mv", "code.py", "moved.py")
        _write_test_evidence(repo)  # the run met the renamed tree
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        cause = _cause_line(err)
        assert "uncommitted: code.py, moved.py" in cause, cause
        assert (
            "Set the whole working tree aside (`git stash push` — a path list "
            "cannot name code.py, which the index has deleted and `git stash "
            "push -- <path>` refuses), run the suite"
        ) in " ".join(err.split()), err
        assert "git stash push -- code.py" not in err
        assert "git stash push -- moved.py" not in err

        head_before = _head(repo)
        _git(repo, "stash", "push", "-q")
        assert _git(repo, "status", "--porcelain", "--untracked-files=no") == ""
        _write_test_evidence(repo)
        rc, out, err = _run_gate(repo, capsys)
        assert rc == 0, err
        assert "transferred across base advance" in out
        assert _head(repo) == head_before
        _git(repo, "stash", "pop", "-q")
        assert not (repo / "code.py").exists() and (repo / "moved.py").is_file()

    def test_the_whole_tree_route_carries_the_untracked_flag_when_needed(self):
        """The whole-tree route's other rendered branch: an untracked
        suite-coupled path alongside a staged deletion needs the flag too."""
        transfer = {"prior_fact_id": "rev-x", "files": ["code.py"]}
        text = gates.transfer_remedy(
            transfer, "no run met this tree", ["code.py", "new.py"],
            untracked=["new.py"], index_deleted=["code.py"],
        )
        assert (
            "Set the whole working tree aside (`git stash push --include-untracked` "
            "— a path list cannot name code.py, which the index has deleted and "
            "`git stash push -- <path>` refuses), run the suite"
        ) in text, text

    def test_a_staged_deletion_cannot_be_named_to_stash(self, tmp_path):
        """The control behind the route above: the pathspec form the remedy
        no longer prints is refused by git for a staged deletion, so a remedy
        naming it would set nothing aside."""
        repo, _pb, _ph = _advanced_base_repo(tmp_path)
        _git(repo, "rm", "-q", "code.py")
        proc = subprocess.run(
            ["git", "stash", "push", "-q", "--", "code.py"],
            cwd=str(repo), capture_output=True, text=True, timeout=15,
        )
        assert proc.returncode != 0, proc
        assert _git(repo, "status", "--porcelain") == "D  code.py"

    def test_a_branch_with_no_review_says_so(self, tmp_path, capsys):
        repo = _branch_repo(tmp_path)
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        mb = _git(repo, "merge-base", "main", "HEAD")
        assert _cause_line(err) == f"CAUSE: no review on this branch since {mb[:12]}."

    def test_a_reviewed_head_with_nothing_moved_names_the_earlier_gap(
        self, tmp_path, capsys
    ):
        """The newest review stands at HEAD, the base did not move and nothing
        is uncommitted — so none of the three causes holds, and the line says
        where the gap must be rather than printing nothing."""
        repo = _branch_repo(tmp_path)
        _commit(repo, "more.py", "m = 1\n", "f2 (unreviewed)")
        mid = _tree(repo)
        _commit(repo, "last.py", "l = 1\n", "f3")
        review = _fact(repo, mid, _tree(repo), ["last.py"], head_commit=_head(repo))
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        cause = _cause_line(err)
        assert cause.startswith(
            f"CAUSE: review {review} stands at this HEAD with the base unmoved"
        ), cause
        assert "the gap is earlier on the branch" in cause

    def test_more_than_three_paths_are_elided_with_a_count(self, tmp_path, capsys):
        repo, _pb, _ph = _advanced_base_repo(tmp_path)
        for name in ("a.py", "b.py", "c.py", "d.py"):
            (repo / name).write_text("v = 1\n")
        _write_test_evidence(repo)
        _rc, _out, err = _run_gate(repo, capsys)
        assert "uncommitted: a.py, b.py, c.py (+1 more)" in _cause_line(err)

    def test_an_unavailable_explanation_says_so_rather_than_nothing(
        self, tmp_path, capsys, monkeypatch
    ):
        repo, _pb, _ph = _advanced_base_repo(tmp_path)
        real = evidence.run_git

        def _no_rev_list(project_dir, *args, **kwargs):
            if args and args[0] == "rev-list":
                return 1, "", "simulated failure"
            return real(project_dir, *args, **kwargs)

        monkeypatch.setattr(evidence, "run_git", _no_rev_list)
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 1
        cause = _cause_line(err)
        assert cause.startswith("CAUSE: unavailable ("), cause
        assert "simulated failure" in cause

    def test_the_verdict_is_unchanged_by_the_explanation(self, tmp_path, capsys):
        """Explanation only: a span that was covered stays covered and prints
        no CAUSE at all."""
        repo = _branch_repo(tmp_path)
        _fact(repo, _tree(repo, "main"), _tree(repo), ["feature.py"], head_commit=_head(repo))
        rc, _out, err = _run_gate(repo, capsys)
        assert rc == 0, err
        assert "CAUSE:" not in err


class TestExplainUncoveredNeverRaises:
    def test_a_git_failure_degrades_to_unavailable(self, tmp_path):
        repo = tmp_path / "not-a-repo"
        repo.mkdir()
        explained = coverage.explain_uncovered(
            repo, [], "a" * 40, "b" * 40, "c" * 40, lambda a, b: None
        )
        assert explained["status"] == "unavailable"
        assert explained["reason"]

    def test_an_unreadable_store_degrades_to_unavailable(self, tmp_path):
        repo = _branch_repo(tmp_path)
        explained = coverage.explain_uncovered(
            repo, None, _tree(repo, "main"), _tree(repo), _head(repo), lambda a, b: []
        )
        assert explained["status"] == "unavailable"
        assert coverage.format_uncovered_cause(explained, gate="pr").startswith(
            "CAUSE: unavailable ("
        )

    def test_a_raising_diff_degrades_to_unavailable(self, tmp_path):
        repo, _pb, _ph = _advanced_base_repo(tmp_path)

        def _boom(a, b):
            raise RuntimeError("diff exploded")

        mb = _git(repo, "merge-base", "main", "HEAD")
        explained = coverage.explain_uncovered(
            repo,
            evidence.read_facts(repo)["facts"],
            _tree(repo, "main"),
            _tree(repo),
            mb,
            _boom,
        )
        assert explained["status"] == "unavailable"
        assert "diff exploded" in explained["reason"]

    def test_a_passed_tally_is_reused_not_re_walked(self, tmp_path, monkeypatch):
        repo, _pb, _ph = _advanced_base_repo(tmp_path)
        facts = evidence.read_facts(repo)["facts"]
        mb = _git(repo, "merge-base", "main", "HEAD")
        tally = coverage.count_branch_rounds(repo, facts, mb)
        calls: list[str] = []
        real = evidence.run_git

        def _recording(project_dir, *args, **kwargs):
            calls.append(args[0] if args else "")
            return real(project_dir, *args, **kwargs)

        monkeypatch.setattr(evidence, "run_git", _recording)
        explained = coverage.explain_uncovered(
            repo, facts, _tree(repo, "main"), _tree(repo), mb,
            lambda a, b: evidence.tree_diff(repo, a, b), tally=tally,
        )
        assert explained["status"] == "explained", explained
        assert explained["base_moved"] is True
        assert "rev-list" not in calls


# ---------------------------------------------------------------------------
# Stop gate (cmd_stop's critic blocker)
# ---------------------------------------------------------------------------


def _stop_session(tmp_path: Path) -> Path:
    """A feature-branch session whose Stop reaches the Critic gate's
    uncovered block: an active plan, reflection satisfied, and an
    uncommitted judgeable edit nobody reviewed."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / ".gitignore").write_text(".prawduct/.session-*\n")
    _commit(repo, "code.py", "x = 1\n", "c1")
    _git(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "feature.py", "y = 1\n", "f1")
    prawduct = repo / ".prawduct"
    (prawduct / "artifacts").mkdir(parents=True)
    (prawduct / "artifacts" / "build-plan.md").write_text(
        "# Build Plan\n\n## Status\n\n- [ ] Chunk 01: work\n"
    )
    (prawduct / ".session-base-tree").write_text(_tree(repo))
    (prawduct / ".session-reflected").write_text(SHAPED_REFLECTION)
    (repo / "feature.py").write_text("y = 2\n")
    return repo


class TestStopGateCause:
    def test_an_uncommitted_judgeable_file_is_named_in_the_span(self, tmp_path, capsys):
        """(c) The Stop gate composes to the working tree, so an uncommitted
        judgeable file IS in its span — and the line says so in those words,
        not the PR gate's 'the gate ignores them'."""
        repo = _stop_session(tmp_path)
        rc = _hook.cmd_stop(repo, {})
        err = capsys.readouterr().err
        assert rc == 2, err
        cause = _cause_line(err)
        assert "uncommitted: feature.py (in this gate's span)" in cause, cause
        assert "the gate ignores them" not in cause

    def test_a_reviewed_committed_branch_then_edited_names_the_head_and_review(
        self, tmp_path, capsys
    ):
        repo = _stop_session(tmp_path)
        _git(repo, "checkout", "--", "feature.py")
        review = _fact(
            repo, _tree(repo, "main"), _tree(repo), ["feature.py"], head_commit=_head(repo)
        )
        _commit(repo, "feature.py", "y = 3\n", "unreviewed commit")
        (repo / ".prawduct" / ".session-base-tree").write_text(_tree(repo, "HEAD~1"))
        rc = _hook.cmd_stop(repo, {})
        err = capsys.readouterr().err
        assert rc == 2, err
        assert (
            f"committed head changed since review {review}: feature.py"
            in _cause_line(err)
        )

    def test_an_unavailable_stop_explanation_still_prints_a_cause(
        self, tmp_path, capsys, monkeypatch
    ):
        repo = _stop_session(tmp_path)

        def _boom(*_a, **_kw):
            raise RuntimeError("store exploded")

        monkeypatch.setattr(coverage, "explain_uncovered", _boom)
        rc = _hook.cmd_stop(repo, {})
        err = capsys.readouterr().err
        assert rc == 2, err
        cause = _cause_line(err)
        assert cause.startswith("CAUSE: unavailable ("), cause
        assert "store exploded" in cause

    def test_a_covered_session_prints_no_cause(self, tmp_path, capsys):
        repo = _stop_session(tmp_path)
        capture = evidence.capture_tree(repo)
        _fact(repo, _tree(repo), capture["tree"], ["feature.py"])
        rc = _hook.cmd_stop(repo, {})
        err = capsys.readouterr().err
        assert rc == 0, err
        assert "CAUSE:" not in err
        assert gates.session_review_verdict(repo)["status"] == "covered"
