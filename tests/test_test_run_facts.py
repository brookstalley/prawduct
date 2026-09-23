"""Every recorded suite run leaves a ``test-run`` fact on the shared store (#653).

``.test-evidence.json`` holds ONE record per worktree, so switching branch
replaces it and switching back re-runs a suite whose tree already had a green
run. The store is shared by every worktree of the clone and keyed by tree, so a
fact per run is what lets a later freshness check find that run again.

Two properties matter as much as the append itself:

- **A failed append never changes ``record``'s answer.** The run happened and
  the per-worktree record was written; losing the index entry costs a later
  re-run, never a wrong verdict, so it is attributed on stderr and nothing else.
- **An observational append does not cold-start the coverage gates.** The
  verdict cache keys on a fingerprint of the store; hashing lines the verdict
  never reads would make every recorded run invalidate every cached verdict.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "plugin"))

from test_plugin_runtime import _git, _run_in  # noqa: E402

from lib import evidence, verdict_cache  # noqa: E402


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "tr"
    repo.mkdir()
    (repo / ".prawduct").mkdir()
    (repo / "test_sample.py").write_text("def test_ok():\n    assert True\n")
    _git(repo, "init", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "c1")
    return repo


def _store(repo: Path) -> Path:
    return repo / ".git" / "prawduct" / "evidence.jsonl"


def _test_runs(repo: Path) -> list[dict]:
    return evidence.facts_of_kind(evidence.read_facts(repo), "test-run")


def _record_junit(repo: Path, xml: str, *extra: str):
    junit = repo / "report.xml"
    junit.write_text('<?xml version="1.0" encoding="utf-8"?>\n' + xml)
    return _run_in(repo, "test-evidence", "record", "--from-junit", str(junit), *extra)


_GREEN = '<testsuites><testsuite name="s" time="2.5"><testcase classname="c" name="ok"/></testsuite></testsuites>'
_RED = '<testsuites><testsuite name="s" time="1"><testcase classname="c" name="bad"><failure/></testcase></testsuite></testsuites>'


def _record_file(repo: Path) -> dict:
    return json.loads((repo / ".prawduct" / ".test-evidence.json").read_text())


class TestEachRecordAppendsOneFact:
    def test_an_ingested_report_appends_a_fact_for_the_tree_it_recorded(self, tmp_path):
        repo = _repo(tmp_path)
        res = _record_junit(repo, _GREEN)
        assert res.returncode == 0, res.stderr
        runs = _test_runs(repo)
        assert len(runs) == 1
        body = runs[0]["body"]
        assert body["tree"] == _record_file(repo)["evidence_tree"]
        assert (body["passed"], body["failed"], body["skipped"]) == (1, 0, 0)
        assert body["duration_seconds"] == 2.5
        assert body["source"] == "from-junit"
        assert "degraded" not in body
        assert runs[0]["actor"]["branch"] == "main"

    def test_a_real_run_is_source_run(self, tmp_path):
        repo = _repo(tmp_path)
        res = _run_in(repo, "test-evidence", "record")
        assert res.returncode == 0, res.stderr
        assert [f["body"]["source"] for f in _test_runs(repo)] == ["run"]

    def test_a_restamp_is_its_own_fact_and_says_it_measured_nothing(self, tmp_path):
        repo = _repo(tmp_path)
        _record_junit(repo, _GREEN)
        res = _run_in(repo, "test-evidence", "record", "--no-rerun")
        assert res.returncode == 0, res.stderr
        assert [f["body"]["source"] for f in _test_runs(repo)] == ["from-junit", "restamp"]

    def test_from_counts_captures_no_tree_so_appends_no_fact(self, tmp_path):
        repo = _repo(tmp_path)
        res = _run_in(repo, "test-evidence", "record", "--from-counts",
                      "passed=3", "failed=0", "skipped=0")
        assert res.returncode == 0, res.stderr
        assert _test_runs(repo) == []

    def test_a_failing_run_is_recorded_so_it_can_supersede_a_green_one(self, tmp_path):
        repo = _repo(tmp_path)
        _record_junit(repo, _RED)
        (run,) = _test_runs(repo)
        assert run["body"]["failed"] == 1

    def test_a_degraded_run_carries_its_reason(self, tmp_path):
        repo = _repo(tmp_path)
        _record_junit(repo, _GREEN, "--degraded", "a worker died under load")
        (run,) = _test_runs(repo)
        assert run["body"]["degraded"] == "a worker died under load"


class TestAFailedAppendIsSoft:
    def test_the_record_and_its_exit_survive_an_unwritable_store(self, tmp_path):
        repo = _repo(tmp_path)
        # A directory where the store file should be: os.open fails, so
        # append_fact returns an error rather than raising.
        _store(repo).mkdir(parents=True)
        res = _record_junit(repo, _GREEN)
        assert res.returncode == 0, res.stderr
        assert _record_file(repo)["passed"] == 1
        assert "test-run fact not recorded" in res.stderr


class TestTheListerShowsARun:
    def test_a_test_run_row_carries_its_tree_counts_and_source(self, tmp_path):
        repo = _repo(tmp_path)
        _record_junit(repo, _RED)
        tree = _record_file(repo)["evidence_tree"]
        res = _run_in(repo, "evidence", "list", "--kind", "test-run")
        assert res.returncode == 0, res.stderr
        (row,) = res.stdout.strip().splitlines()
        assert f"tree={tree[:12]}" in row
        assert "passed=0 failed=1 skipped=0" in row
        assert "source=from-junit" in row


def _append_line(repo: Path, record: dict | str) -> None:
    line = record if isinstance(record, str) else json.dumps(record)
    with _store(repo).open("a") as fh:
        fh.write(line + "\n")


def _envelope(kind: str, fact_id: str, schema: int = 1) -> dict:
    return {"schema": schema, "kind": kind, "id": fact_id, "ts": "2026-09-23T00:00:00Z",
            "actor": {}, "body": {}}


class TestTheCoverageFingerprint:
    """The verdict cache's key: every store line EXCEPT a well-formed schema-1
    line of a kind the coverage verdict never reads."""

    def _prints(self, repo: Path) -> tuple[str, str]:
        read = evidence.read_facts(repo)
        return read["fingerprint"], read["coverage_fingerprint"]

    def _seeded(self, tmp_path: Path) -> Path:
        repo = _repo(tmp_path)
        _store(repo).parent.mkdir(parents=True)
        _append_line(repo, _envelope("review", "rev-1"))
        return repo

    def test_observational_appends_leave_it_unchanged(self, tmp_path):
        repo = self._seeded(tmp_path)
        whole, coverage = self._prints(repo)
        _append_line(repo, _envelope("test-run", "tr-1"))
        _append_line(repo, _envelope("guard-refusal", "g-1"))
        whole_after, coverage_after = self._prints(repo)
        assert whole_after != whole  # the whole-file print still sees them
        assert coverage_after == coverage

    def test_every_other_line_changes_it(self, tmp_path):
        cases = [
            _envelope("review", "rev-2"),
            _envelope("resolution", "res-1"),
            _envelope("disposition", "d-1"),
            _envelope("some-future-kind", "x-1"),
            _envelope("test-run", "tr-ahead", schema=2),
            '{"schema": 1, "kind": "test-run"',  # malformed
        ]
        for i, line in enumerate(cases):
            (tmp_path / str(i)).mkdir()
            repo = self._seeded(tmp_path / str(i))
            _, before = self._prints(repo)
            _append_line(repo, line)
            _, after = self._prints(repo)
            assert after != before, line

    def test_it_is_absent_exactly_when_the_whole_file_print_is(self, tmp_path):
        repo = _repo(tmp_path)
        read = evidence.read_facts(repo)
        assert read["fingerprint"] is None and read["coverage_fingerprint"] is None

    def test_the_verdict_cache_survives_a_recorded_run(self, tmp_path):
        """The end-to-end property: a verdict memoized before a suite run is
        still a hit after it, and a review append still invalidates it."""
        repo = self._seeded(tmp_path)

        def ask() -> verdict_cache.VerdictCache:
            read = evidence.read_facts(repo)
            cache = verdict_cache.VerdictCache.for_read(repo, read)
            cache.verdict(read["facts"], "a" * 40, "b" * 40,
                          lambda a, b: None, lambda t: None)
            cache.flush()
            return cache

        assert ask().misses == 1
        _append_line(repo, _envelope("test-run", "tr-1"))
        assert ask().hits == 1
        _append_line(repo, _envelope("review", "rev-2"))
        assert ask().misses == 1
