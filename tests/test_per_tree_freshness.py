"""A green run is remembered per tree, across branches and worktrees (#653).

``.test-evidence.json`` holds one record per worktree, so switching branch
replaced it and switching back re-ran a suite whose tree already had a green
run. Freshness now also asks the shared store's ``test-run`` facts, choosing
at most three candidates — the newest fact for the exact tree, for the current
HEAD commit, and for the current branch — and judging each with the same
judgeable tree-diff the per-worktree clause already trusts.

Among the candidates — this worktree's own record included — the newest run
that met the tree decides it, so a red re-run supersedes an earlier green. One
direction is deliberate: the store is only asked after this worktree's own
record declines, so its own green record for this tree is never overruled.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugin"))

from test_plugin_runtime import _git, _run_in  # noqa: E402

from lib import evidence  # noqa: E402

_GREEN = '<testsuites><testsuite name="s" time="1"><testcase classname="c" name="ok"/></testsuite></testsuites>'
_RED = '<testsuites><testsuite name="s" time="1"><testcase classname="c" name="bad"><failure/></testcase></testsuite></testsuites>'


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "pt"
    repo.mkdir()
    (repo / ".prawduct").mkdir()
    (repo / "test_sample.py").write_text("def test_ok():\n    assert True\n")
    _git(repo, "init", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "c1")
    return repo


def _branch(repo: Path, name: str, body: str) -> None:
    _git(repo, "switch", "-q", "-c", name, "main")
    (repo / "mod.py").write_text(body)
    _git(repo, "add", "mod.py")
    _git(repo, "commit", "-q", "-m", name)


def _record(repo: Path, xml: str = _GREEN, *extra: str):
    # The report lives OUTSIDE the repo so it is never part of a captured tree.
    junit = repo.parent / "report.xml"
    junit.write_text('<?xml version="1.0" encoding="utf-8"?>\n' + xml)
    res = _run_in(repo, "test-evidence", "record", "--from-junit", str(junit), *extra)
    assert res.returncode in (0, 1), res.stderr
    return res


def _status(repo: Path):
    return _run_in(repo, "test-status")


class TestSwitchingBackRerunsNothing:
    def test_each_branch_is_current_after_the_other_was_recorded(self, tmp_path):
        """The acceptance scenario: A green, B green, back to A — current,
        tree-valid, and nothing run."""
        repo = _repo(tmp_path)
        _branch(repo, "feat-a", "A = 1\n")
        _record(repo)
        _branch(repo, "feat-b", "B = 2\n")
        _record(repo)
        _git(repo, "switch", "-q", "feat-a")
        res = _status(repo)
        assert res.returncode == 0, res.stdout
        assert res.stdout.startswith("current (tree-valid)")
        assert "recorded on feat-a" in res.stdout
        _git(repo, "switch", "-q", "feat-b")
        assert _status(repo).returncode == 0

    def test_a_tree_nothing_ran_against_is_still_stale(self, tmp_path):
        repo = _repo(tmp_path)
        _branch(repo, "feat-a", "A = 1\n")
        _record(repo)
        _branch(repo, "feat-c", "C = 3\n")
        res = _status(repo)
        assert res.returncode == 1, res.stdout

    def test_a_branch_edited_since_its_run_is_stale(self, tmp_path):
        """The branch candidate is judged by the tree diff, never trusted by
        name: a run on feat-a does not vouch for feat-a's next commit."""
        repo = _repo(tmp_path)
        _branch(repo, "feat-a", "A = 1\n")
        _record(repo)
        _branch(repo, "feat-b", "B = 2\n")
        _record(repo)
        _git(repo, "switch", "-q", "feat-a")
        (repo / "mod.py").write_text("A = 99\n")
        _git(repo, "commit", "-qam", "edit")
        assert _status(repo).returncode == 1


class TestEachCandidateFindsWhatOnlyItCan:
    """Three candidates, and each one reaches a run the other two cannot, so
    each is pinned by a case where it alone is the route."""

    def test_the_branch_finds_a_run_after_a_docs_only_commit(self, tmp_path):
        # A later commit moves HEAD and the exact tree, but touches only docs,
        # so the branch's run still met this tree by the judgeable diff.
        repo = _repo(tmp_path)
        _branch(repo, "feat-a", "A = 1\n")
        _record(repo)
        (repo / "NOTES.md").write_text("docs only\n")
        _git(repo, "add", "NOTES.md")
        _git(repo, "commit", "-qm", "docs")
        _branch(repo, "feat-b", "B = 2\n")
        _record(repo)
        _git(repo, "switch", "-q", "feat-a")
        res = _status(repo)
        assert res.returncode == 0, res.stdout
        assert "recorded on feat-a" in res.stdout

    def test_the_exact_tree_finds_a_run_from_a_different_commit(self, tmp_path):
        # Same content committed twice: a different commit, no shared branch,
        # and a detached worktree — only the tree itself matches.
        repo = _repo(tmp_path)
        _branch(repo, "feat-a", "A = 1\n")
        _record(repo)  # first record: no prior evidence file in the tree
        _branch(repo, "feat-a2", "A = 1\n")
        wt = tmp_path / "wt2"
        _git(repo, "worktree", "add", "-q", "--detach", str(wt), "feat-a2")
        (wt / ".prawduct").mkdir(exist_ok=True)
        res = _status(wt)
        assert res.returncode == 0, res.stdout


class TestASecondWorktreeReusesTheRun:
    def test_a_detached_worktree_at_the_same_commit_is_current(self, tmp_path):
        repo = _repo(tmp_path)
        _branch(repo, "feat-a", "A = 1\n")
        _record(repo)
        wt = tmp_path / "wt2"
        _git(repo, "worktree", "add", "-q", "--detach", str(wt), "feat-a")
        (wt / ".prawduct").mkdir(exist_ok=True)
        # An untracked note makes the tree differ byte-wise, and a detached
        # worktree has no branch: the commit is the only candidate that finds
        # the run, and the judgeable diff then clears the note.
        (wt / "scratch-notes.md").write_text("mine\n")
        res = _status(wt)
        assert res.returncode == 0, res.stdout
        assert res.stdout.startswith("current (tree-valid)")


class TestTheNewestRunDecides:
    def test_a_red_rerun_on_the_same_tree_supersedes_the_green(self, tmp_path):
        repo = _repo(tmp_path)
        _branch(repo, "feat-a", "A = 1\n")
        _record(repo)
        _record(repo, _RED)
        _branch(repo, "feat-b", "B = 2\n")
        _record(repo)
        _git(repo, "switch", "-q", "feat-a")
        assert _status(repo).returncode == 1

    def test_the_worktree_record_counts_even_when_its_fact_was_lost(self, tmp_path):
        """A red run whose fact append failed is still the newest run for its
        tree: the per-worktree record says so, and an older green fact on the
        same tree must not vouch past it."""
        repo = _repo(tmp_path)
        _branch(repo, "feat-a", "A = 1\n")
        _record(repo)
        store = repo / ".git" / "prawduct" / "evidence.jsonl"
        saved = store.read_bytes()
        _record(repo, _RED)
        store.write_bytes(saved)  # the red run's fact never landed
        res = _status(repo)
        assert res.returncode == 1, res.stdout

    def test_a_degraded_fact_never_vouches(self, tmp_path):
        repo = _repo(tmp_path)
        _branch(repo, "feat-a", "A = 1\n")
        _record(repo, _GREEN, "--degraded", "a shard never reported")
        _branch(repo, "feat-b", "B = 2\n")
        _record(repo)
        _git(repo, "switch", "-q", "feat-a")
        assert _status(repo).returncode == 1


class TestTheStoreNeverLoosensAVerdict:
    def test_an_unreadable_store_falls_back_to_the_worktree_record(self, tmp_path):
        repo = _repo(tmp_path)
        _branch(repo, "feat-a", "A = 1\n")
        _record(repo)
        _branch(repo, "feat-b", "B = 2\n")
        _record(repo)
        store = repo / ".git" / "prawduct" / "evidence.jsonl"
        store.write_bytes(b"\xff\xfe not utf-8\n")
        assert _status(repo).returncode == 0  # feat-b's own record still vouches
        _git(repo, "switch", "-q", "feat-a")
        assert _status(repo).returncode == 1  # and nothing else does


class TestTheFactNamesItsCommit:
    def test_a_fact_records_the_head_commit(self, tmp_path):
        repo = _repo(tmp_path)
        _branch(repo, "feat-a", "A = 1\n")
        _record(repo)
        (run,) = evidence.facts_of_kind(evidence.read_facts(repo), "test-run")
        head = _git(repo, "rev-parse", "HEAD").stdout.strip()
        assert run["body"]["head"] == head


class TestThePrGateAsksTheStoreToo:
    def test_suite_vouches_for_a_tree_a_sibling_branch_ran(self, tmp_path):
        from lib import gates

        repo = _repo(tmp_path)
        _branch(repo, "feat-a", "A = 1\n")
        _record(repo)
        _branch(repo, "feat-b", "B = 2\n")
        _record(repo)
        _git(repo, "switch", "-q", "feat-a")
        target = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        vouches, reason = gates.suite_vouches_for_tree(repo, target)
        assert vouches, reason
        assert "recorded on feat-a" in reason


class TestARefusedRecordIsAFloor:
    """This worktree's own record is its latest word. When it refuses to vouch,
    a run recorded BEFORE it must not overrule it — only a strictly newer run
    may — and a record that cannot be validated lets nothing through."""

    def test_a_failing_record_with_no_tree_still_blocks_an_older_green(self, tmp_path):
        # `--from-counts` names no tree, so it could never compete by tree; an
        # older green at the same commit would otherwise vouch past it.
        repo = _repo(tmp_path)
        _branch(repo, "feat-a", "A = 1\n")
        _record(repo)
        _run_in(repo, "test-evidence", "record", "--from-counts",
                "passed=1", "failed=2", "skipped=0")
        res = _status(repo)
        assert res.returncode == 1, res.stdout
        assert "2 test(s) failing" in res.stdout

    def test_a_schema_invalid_record_lets_nothing_through(self, tmp_path):
        repo = _repo(tmp_path)
        _branch(repo, "feat-a", "A = 1\n")
        _record(repo)
        path = repo / ".prawduct" / ".test-evidence.json"
        ev = json.loads(path.read_text())
        ev["degraded"] = True  # the schema wants a reason string
        path.write_text(json.dumps(ev))
        res = _status(repo)
        assert res.returncode == 1, res.stdout

    def test_a_strictly_newer_green_from_a_sibling_still_vouches(self, tmp_path):
        import time

        repo = _repo(tmp_path)
        _branch(repo, "feat-a", "A = 1\n")
        _record(repo, _RED)
        time.sleep(1.1)  # store and record timestamps are to the second
        wt = tmp_path / "wt2"
        _git(repo, "worktree", "add", "-q", "--detach", str(wt), "feat-a")
        (wt / ".prawduct").mkdir(exist_ok=True)
        _record(wt)
        res = _status(repo)
        assert res.returncode == 0, res.stdout
        assert "evidence store" in res.stdout


class TestARedRunElsewhereDoesNotBlockAGreenHere:
    def test_switching_away_from_a_red_branch_to_a_green_one_is_current(self, tmp_path):
        """The everyday case this fallback exists for: A was green, work on B
        is mid-fix and red, and switching back to A re-runs nothing. B's red
        record is about B's tree, so it sets no floor over A."""
        repo = _repo(tmp_path)
        _branch(repo, "feat-a", "A = 1\n")
        _record(repo)
        _branch(repo, "feat-b", "B = 2\n")
        _record(repo, _RED)
        _git(repo, "switch", "-q", "feat-a")
        res = _status(repo)
        assert res.returncode == 0, res.stdout
        assert "recorded on feat-a" in res.stdout


class TestAnUndecodableRecordIsStale:
    def test_non_utf8_evidence_reads_stale_without_a_traceback(self, tmp_path):
        repo = _repo(tmp_path)
        _branch(repo, "feat-a", "A = 1\n")
        _record(repo)
        (repo / ".prawduct" / ".test-evidence.json").write_bytes(b"\xff\xfe not utf-8 {")
        res = _status(repo)
        assert res.returncode == 1, res.stdout
        assert res.stdout.startswith("stale: unreadable evidence"), res.stdout
        assert "Traceback" not in res.stderr


def _feat_a_green_then_b(tmp_path):
    """feat-a green, feat-b recorded, still on feat-b — switching to feat-a
    now would be current by the store (the baseline each test below perturbs)."""
    repo = _repo(tmp_path)
    _branch(repo, "feat-a", "A = 1\n")
    _record(repo)
    head_a = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _branch(repo, "feat-b", "B = 2\n")
    _record(repo)
    return repo, head_a


class TestANewerSchemaStopsTheStore:
    """A fact written by a newer plugin may be the freshest run, and this
    reader cannot interpret it — so the store vouches for nothing, loudly."""

    def _ahead(self, repo: Path) -> None:
        store = repo / ".git" / "prawduct" / "evidence.jsonl"
        with store.open("a") as fh:
            fh.write(json.dumps({"schema": 2, "kind": "test-run", "id": "tr-ahead",
                                 "ts": "2099-01-01T00:00:00Z", "actor": {}, "body": {}}) + "\n")

    def test_test_status_is_stale_and_says_why(self, tmp_path):
        repo, _ = _feat_a_green_then_b(tmp_path)
        _git(repo, "switch", "-q", "feat-a")
        assert _status(repo).returncode == 0  # the baseline vouches
        self._ahead(repo)
        res = _status(repo)
        assert res.returncode == 1, res.stdout
        assert "evidence store not consulted" in res.stdout
        assert "newer than this plugin" in res.stdout

    def test_the_pr_gate_is_denied_too(self, tmp_path):
        from lib import gates

        repo, _ = _feat_a_green_then_b(tmp_path)
        _git(repo, "switch", "-q", "feat-a")
        target = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        assert gates.suite_vouches_for_tree(repo, target)[0]
        self._ahead(repo)
        vouches, reason = gates.suite_vouches_for_tree(repo, target)
        assert not vouches
        assert "evidence store not consulted" in reason


class TestCannotTellIsNeverAWaiver:
    def test_a_red_run_whose_tree_cannot_be_compared_denies(self, tmp_path):
        """A newer red run at feat-a's commit, whose tree object is missing so
        no diff can place it: it may be this tree's newest word, so it denies —
        even though feat-a's older green would otherwise vouch by branch."""
        repo, head_a = _feat_a_green_then_b(tmp_path)
        evidence.append_test_run(repo, {
            "tree": "f" * 40, "head": head_a, "passed": 0, "failed": 1,
            "skipped": 0, "duration_seconds": 1.0, "source": "run",
        })
        _git(repo, "switch", "-q", "feat-a")
        res = _status(repo)
        assert res.returncode == 1, res.stdout


class TestAMalformedCountNeverVouches:
    def _fact(self, repo: Path, head: str, failed) -> None:
        tree = evidence.capture_tree(repo)["tree"]
        evidence.append_test_run(repo, {
            "tree": tree, "head": head, "passed": 1, "failed": failed,
            "skipped": 0, "duration_seconds": 1.0, "source": "run",
        })

    def test_a_string_count_is_refused_end_to_end(self, tmp_path):
        repo, head_a = _feat_a_green_then_b(tmp_path)
        _git(repo, "switch", "-q", "feat-a")
        self._fact(repo, head_a, "0")
        res = _status(repo)
        assert res.returncode == 1
        assert res.stdout.startswith("stale:"), res.stdout  # refused, not crashed
        assert "Traceback" not in res.stderr

    def test_an_integer_zero_is_the_control(self, tmp_path):
        repo, head_a = _feat_a_green_then_b(tmp_path)
        _git(repo, "switch", "-q", "feat-a")
        self._fact(repo, head_a, 0)
        assert _status(repo).returncode == 0


class TestRunRefusal:
    def test_each_malformed_count_refuses(self):
        from lib import gates

        for failed in (None, "0", True, 0.0):
            run = {} if failed is None else {"failed": failed}
            assert gates.run_refusal(run) == "the saved run carries no valid failure count", failed

    def test_a_clean_run_is_not_refused(self):
        from lib import gates

        assert gates.run_refusal({"failed": 0}) == ""
        assert "degraded" in gates.run_refusal({"failed": 0, "degraded": "x"})
        assert "1 test(s) failing" in gates.run_refusal({"failed": 1})


class TestHandTypedCountsNeverVouch:
    def test_a_green_record_naming_no_tree_proves_nothing(self, tmp_path):
        """``--from-counts`` names no tree, so nothing can show the counts
        covered this one: through the store it can deny, never vouch."""
        repo = _repo(tmp_path)
        _branch(repo, "feat-b", "B = 2\n")
        _record(repo)  # one fact in the store, for another tree
        _branch(repo, "feat-a", "A = 1\n")
        _run_in(repo, "test-evidence", "record", "--from-counts",
                "passed=5", "failed=0", "skipped=0")
        res = _status(repo)
        assert res.returncode == 1, res.stdout
