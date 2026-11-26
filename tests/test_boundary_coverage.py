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
        assert "recorded its base-advance transfer grant" in entry.reason, entry

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
        base = _branch(repo, "f")
        _commit(repo, {"src/a.py": "a = 1\n", **_fragment("f")}, "work")
        _review(repo, base, _tree(repo), CUMULATIVE)
        _git(repo, "checkout", "-q", "main")
        _git(repo, "merge", "-q", "--squash", "f")
        _git(repo, "commit", "-q", "-m", "squash f")
        entry = _classify(repo, _git(repo, "rev-parse", "HEAD"))
        assert entry.classification == bc.DIRECT and "squash" in entry.reason, entry


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

    def test_the_v3_9_0_release_commit_on_develop_is_direct(self):
        """Git alone answers this one: a single-parent commit changing judgeable
        files, whatever the store holds."""
        entry = bc.classify_merge(ROOT, "95308783")
        assert entry.classification == bc.DIRECT, entry

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
