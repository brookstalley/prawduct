"""Guards for `tools/measure-review-window.py`.

The script's one job is to put each review fact in the right cohort and to say
how big every cell is. So what is pinned here is the three ways it could report
a window it does not have: ordering versions wrongly (a `-dev` build counted as
the release it precedes), pooling facts that cannot say whether they found
nothing into an empty rate, and losing the clock join.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOL = REPO_ROOT / "tools" / "measure-review-window.py"
UTC = dt.timezone.utc
SINCE = dt.datetime(2026, 9, 1, tzinfo=UTC)


def _load():
    spec = importlib.util.spec_from_file_location("measure_review_window", _TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["measure_review_window"] = module
    spec.loader.exec_module(module)
    return module


tool = _load()


def _fact(fid, *, version="3.6.0", mode="verify-resolutions (delta review)", scope="s1",
          findings=(), observations=None, ts="2026-09-20T12:00:00Z", kind="review"):
    body = {"mode": mode, "scope": scope, "findings": [{"severity": s} for s in findings]}
    if observations is not None:
        body["observations"] = [{"oid": f"O-{i}"} for i in range(observations)]
    return {"schema": 1, "kind": kind, "id": fid, "ts": ts,
            "actor": {"plugin": version}, "body": body}


def _write_store(path: Path, facts: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(f) + "\n" for f in facts))
    return path


class TestVersionOrder:
    def test_a_prerelease_sorts_before_its_release(self):
        order = ["3.5.1-dev.2", "3.6.0-dev", "3.6.0", "3.6.1-dev", "3.6.1-dev.1",
                 "3.6.1-dev.2", "3.6.1-dev.10", "3.6.1"]
        keys = [tool.version_key(v) for v in order]
        assert keys == sorted(keys), "semver order broken"

    def test_prerelease_numbers_compare_as_numbers(self):
        """Red if `dev.10` sorts before `dev.2`, which a string compare does."""
        assert tool.version_key("3.6.1-dev.10") > tool.version_key("3.6.1-dev.2")

    def test_a_dev_build_of_the_cut_is_before_it(self):
        """`3.6.0-dev` ran code that 3.6.0 later changed, so it is not 'after'."""
        cut = tool.version_key("3.6.0")
        assert tool.cohort_of("3.6.0-dev", cut) == "before"
        assert tool.cohort_of("3.6.0", cut) == "after"
        assert tool.cohort_of("3.6.1-dev.1", cut) == "after"

    def test_a_missing_or_malformed_version_is_unknown_not_before(self):
        cut = tool.version_key("3.6.0")
        for bad in (None, "", "dev", "3.6", 3.6):
            assert tool.cohort_of(bad, cut) == "unknown", bad


class TestReadFacts:
    def test_only_review_facts_inside_the_window_are_read(self, tmp_path):
        store = _write_store(tmp_path / "evidence.jsonl", [
            _fact("r1"),
            _fact("r2", ts="2026-08-31T23:59:59Z"),
            _fact("d1", kind="disposition"),
        ])
        rows = tool.read_facts(store, "p", SINCE, {})
        assert [r["version"] for r in rows] == ["3.6.0"]
        assert len(rows) == 1

    def test_the_clock_joins_by_fact_id(self, tmp_path):
        store = _write_store(tmp_path / "evidence.jsonl", [_fact("r1"), _fact("r2")])
        rows = tool.read_facts(store, "p", SINCE, {"r2": 240.0})
        assert {r["clock"] for r in rows} == {None, 240.0}

    def test_an_absent_observations_field_stays_absent(self, tmp_path):
        """None, not 0: a fact written before the field existed cannot say it
        demoted nothing."""
        store = _write_store(tmp_path / "evidence.jsonl", [
            _fact("r1"), _fact("r2", observations=0), _fact("r3", observations=2),
        ])
        assert [r["observations"] for r in tool.read_facts(store, "p", SINCE, {})] == [None, 0, 2]


class TestSummarise:
    def _rows(self, tmp_path, facts, clocks=None):
        store = _write_store(tmp_path / "evidence.jsonl", facts)
        return tool.read_facts(store, "p", SINCE, clocks or {})

    def test_empty_rates_exclude_facts_that_do_not_record_observations(self, tmp_path):
        rows = self._rows(tmp_path, [
            _fact("a", observations=0),                      # nothing at all
            _fact("b", observations=3),                      # notes only
            _fact("c", observations=1, findings=["blocking"]),
            _fact("d"), _fact("e"),                          # unrecorded
        ])
        out = tool.summarise(rows, min_cell=30)
        assert out["verify_nothing_gating"]["n"] == 3
        assert out["verify_nothing_gating"]["share"] == 2 / 3
        assert out["verify_nothing_at_all"]["share"] == 1 / 3
        assert out["verify_unrecorded"] == 2
        assert out["verify_blocking_rate"] == {"n": 5, "share": 1 / 5, "thin": True}

    def test_a_cell_below_min_cell_is_thin_and_one_at_it_is_not(self, tmp_path):
        rows = self._rows(tmp_path, [_fact(f"r{i}") for i in range(3)])
        assert tool.summarise(rows, min_cell=3)["verify_share_of_runs"]["thin"] is False
        assert tool.summarise(rows, min_cell=4)["verify_share_of_runs"]["thin"] is True

    def test_repeat_cumulatives_count_runs_past_the_first_per_scope(self, tmp_path):
        cum = "cumulative (bundle review)"
        rows = self._rows(tmp_path, [
            _fact("a", mode=cum, scope="s1"), _fact("b", mode=cum, scope="s1"),
            _fact("c", mode=cum, scope="s1"), _fact("d", mode=cum, scope="s2"),
        ])
        out = tool.summarise(rows, min_cell=1)["repeat_cumulative_share"]
        assert (out["n"], out["share"]) == (4, 2 / 4)

    def test_only_clocked_rows_enter_a_clock_median(self, tmp_path):
        rows = self._rows(tmp_path, [_fact("a"), _fact("b"), _fact("c")],
                          clocks={"a": 100.0, "b": 300.0})
        out = tool.summarise(rows, min_cell=30)["clock_verify"]
        assert (out["n"], out["median_s"]) == (2, 200.0)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(repo), check=True, capture_output=True, timeout=10,
                   env={"HOME": str(repo.parent), "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
                        "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"})


class TestBuildEndToEnd:
    def test_a_fleet_of_one_is_cohorted_and_its_clock_joined(self, tmp_path):
        """The whole path: ledger discovery, clone grouping, the store under the
        clone's git dir, the ledger-to-fact clock join, and the cohort split."""
        repo = tmp_path / "root" / "product"
        repo.mkdir(parents=True)
        _git(repo, "init", "--quiet")
        _write_store(repo / ".git" / "prawduct" / "evidence.jsonl", [
            _fact("old", version="3.5.1-dev.2", observations=0),
            _fact("new", version="3.6.1-dev.1", observations=1),
        ])
        ledger = repo / ".prawduct" / ".governance-ledger.jsonl"
        ledger.parent.mkdir()
        ledger.write_text(json.dumps({
            "event": "review.critic", "ts": "2026-09-20T12:05:00Z",
            "dispatched_at": "2026-09-20T12:00:00Z", "review": {"fact_id": "new"},
        }) + "\n" + json.dumps({
            "event": "review.pr", "ts": "2026-09-20T13:00:00Z",
            "dispatched_at": "2026-09-20T12:50:00Z",
            "review_written_at": "2026-09-20T12:55:00Z", "review": {},
        }) + "\n")

        report = tool.build(tmp_path / "root", SINCE, "3.6.0", min_cell=30)
        before, after = report["cohorts"]["before"], report["cohorts"]["after"]
        assert before["reviews"] == 1 and after["reviews"] == 1
        assert after["clock_verify"] == {"n": 1, "median_s": 300.0, "thin": True}
        assert before["clock_verify"]["n"] == 0
        assert report["pr"] == {"reviews": 1, "clocked": 1}
        assert report["stores_missing"] == []
        assert report["clones"] == 1
