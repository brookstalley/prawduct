"""``prawduct-hook stats`` — governance cost and yield per plugin version.

Each metric is pinned against a hand-built fact list, with the case that would
falsify it beside the case that satisfies it: a verify round that confirmed a
fix is not empty; a self-estimate is never summed as measured time; a later
accept cannot un-fix a fixed finding; a deferred-gate Stop block does not exist
to count. The CLI is pinned end to end over a real store.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(_ROOT))

from lib import evidence, stats  # noqa: E402


def _fact(kind, body, *, fid="f", ts="2026-10-01T10:00:00Z", plugin="3.7.1-dev.2", session="s1"):
    return {
        "schema": 1,
        "kind": kind,
        "id": fid,
        "ts": ts,
        "actor": {"session": session, "worktree": "/w", "plugin": plugin},
        "body": body,
    }


def _review(rid, mode="chunk", *, findings=(), base="b0", head="h1", scope="feat", **kw):
    body = {
        "mode": f"{mode} (whatever)",
        "base_tree": base,
        "head_tree": head,
        "scope": scope,
        "findings": list(findings),
        "duration_seconds": kw.pop("estimate", 300),
    }
    if "dispatched_at" in kw:
        body["dispatched_at"] = kw.pop("dispatched_at")
    return _fact("review", body, fid=rid, **kw)


def _finding(fid, severity, goal="Nothing Is Broken"):
    return {"fid": fid, "severity": severity, "goal": goal, "title": "t", "recommendation": "r"}


def _resolution(rid, fid, disposition="fixed", *, by="v1"):
    return _fact(
        "resolution",
        {"finding": {"review_id": rid, "fid": fid}, "disposition": disposition, "verified_by": by},
        fid=f"res-{rid}-{fid}-{by}",
    )


def _disposition(rid, fid, action, n=1):
    return _fact(
        "disposition",
        {"finding": {"review_id": rid, "fid": fid}, "action": action},
        fid=f"disp-{rid}-{fid}-{n}",
    )


def _block(gate, stop, session="s1"):
    return _fact(
        "guard-refusal",
        {"guard": f"{evidence.STOP_GATE_PREFIX}{gate}", "gate": gate, "stop": stop, "co_gates": []},
        fid=f"g-{gate}-{stop}",
        session=session,
    )


def _v(facts, version="3.7", **kw):
    return stats.aggregate(facts, **kw)[version]


class TestVersionBucket:
    @pytest.mark.parametrize(
        ("plugin", "bucket"),
        [("3.7.1-dev.2", "3.7"), ("3.7.0", "3.7"), ("2.0.16", "2.0"), ("3.10", "3.10"),
         (None, "unknown"), ("", "unknown"), ("dev", "unknown")],
    )
    def test_buckets_by_major_minor(self, plugin, bucket):
        assert stats.version_bucket(plugin) == bucket

    def test_facts_from_two_versions_report_apart(self):
        report = stats.aggregate([_review("r1", plugin="3.6.2"), _review("r2", plugin="3.7.0")])
        assert sorted(report) == ["3.6", "3.7"]


class TestFindingOutcome:
    """The rule is `dispositions.finding_state`, shared with render-dispositions."""

    def _outcome(self, facts, key=("r1", "R-1")):
        return stats.finding_outcome({"facts": facts})(key)

    def test_a_resolution_outranks_a_later_disposition(self):
        facts = [_resolution("r1", "R-1"), _disposition("r1", "R-1", "accept")]
        assert self._outcome(facts) == "fixed"

    def test_the_newest_disposition_wins(self):
        facts = [_disposition("r1", "R-1", "accept"), _disposition("r1", "R-1", "file", 2)]
        assert self._outcome(facts) == "filed"

    def test_a_fix_nobody_reviewed_is_kept_apart(self):
        assert self._outcome([_disposition("r1", "R-1", "fixed")]) == "fixed_unreviewed"

    def test_a_waiver_is_its_own_outcome(self):
        assert self._outcome([_resolution("r1", "R-1", "waived")]) == "waived"

    def test_an_unanswered_finding_is_undispositioned(self):
        assert self._outcome([]) == "undispositioned"

    def test_agrees_with_render_dispositions(self):
        from lib import dispositions
        facts = [_disposition("r1", "R-1", "accept"), _resolution("r1", "R-1", "waived")]
        store = {"facts": facts}
        state = dispositions.finding_state(
            ("r1", "R-1"), dispositions.disposition_index(store),
            dispositions.resolution_detail_index(store),
        )
        assert state == "waived" and self._outcome(facts) == "waived"


class TestBenefit:
    def test_findings_by_outcome_and_acted_on_rate(self):
        facts = [
            _review("r1", findings=[_finding("R-1", "blocking"), _finding("R-2", "warning"),
                                    _finding("R-3", "warning"), _finding("R-4", "note")]),
            _resolution("r1", "R-1"),
            _disposition("r1", "R-2", "file"),
            _disposition("r1", "R-3", "accept"),
        ]
        f = _v(facts)["findings"]
        assert f["blocking"]["raised"] == 1 and f["blocking"]["fixed"] == 1
        assert f["warning"]["filed"] == 1 and f["warning"]["accepted"] == 1
        assert f["warning"]["acted_on_rate"] == 0.5
        # Unanswered findings are counted, never read as a verdict either way.
        assert f["note"]["undispositioned"] == 1 and f["note"]["acted_on_rate"] is None
        # The denominator is exported, so a reader flooring on it uses this count.
        assert f["warning"]["answered"] == 2 and f["note"]["answered"] == 0
        assert f["blocking"]["answered"] == 1

    def test_blocking_fixed_by_goal_and_per_scope(self):
        facts = [
            _review("r1", findings=[_finding("R-1", "blocking", "Nothing Is Missing")], scope="a"),
            _review("r2", findings=[_finding("R-1", "blocking")], scope="b", head="h2"),
            _resolution("r1", "R-1"),
        ]
        v = _v(facts)
        assert v["blocking_fixed_by_goal"] == {"Nothing Is Missing": 1}
        assert v["blocking_fixed_per_scope"] == 0.5

    def test_warnings_fixed_per_scope_counts_unreviewed_fixes(self):
        facts = [
            _review("r1", findings=[_finding("R-1", "warning"), _finding("R-2", "warning")], scope="a"),
            _review("r2", scope="b", head="h2"),
            _resolution("r1", "R-1"),
            _disposition("r1", "R-2", "fixed"),
        ]
        assert _v(facts)["warnings_fixed_per_scope"] == 1.0

    def test_a_malformed_finding_is_counted_not_crashed_on(self):
        facts = [_review("r1", findings=[{"fid": ["R-1"], "severity": "warning"}]),
                 _fact("disposition", {"finding": ["r1", "R-1"], "action": "accept"}, fid="d")]
        assert _v(facts)["findings"]["warning"]["other"] == 1

    def test_red_suite_runs(self):
        facts = [_fact("test-run", {"failed": 0}, fid="t1"), _fact("test-run", {"failed": 2}, fid="t2")]
        assert _v(facts)["test_runs"] == {"total": 2, "red": 1}


class TestCost:
    def test_rounds_per_scope(self):
        facts = [_review(f"r{i}", scope="a", head=f"h{i}") for i in range(3)] + [_review("r9", scope="b", head="h9")]
        assert _v(facts)["rounds_per_scope"]["median"] == 2.0
        assert _v(facts)["rounds_per_scope"]["max"] == 3

    def test_an_estimate_is_never_summed_as_measured(self):
        facts = [
            _review("r1", ts="2026-10-01T10:02:00Z", dispatched_at="2026-10-01T10:00:00Z", estimate=600),
            _review("r2", head="h2", estimate=900),
        ]
        secs = _v(facts)["review_seconds"]
        assert secs["measured"] == {
            "reviews": 1, "total": 120, "median": 120.0,
            "per_scope": {"n": 1, "median": 120.0, "p90": 120.0, "max": 120.0},
        }
        assert secs["estimated"] == {"reviews": 1, "total": 900}

    def test_a_verify_round_that_confirmed_a_fix_is_not_empty(self):
        facts = [
            _review("r1", findings=[_finding("R-1", "blocking")]),
            _review("v1", mode="verify-resolutions", head="h2"),
            _resolution("r1", "R-1", by="v1"),
            _review("v2", mode="verify-resolutions", head="h3"),
        ]
        assert _v(facts)["verify_rounds"] == {"total": 2, "empty": 1}

    def test_a_verify_round_raising_a_warning_is_not_empty(self):
        facts = [_review("v1", mode="verify-resolutions", findings=[_finding("R-1", "warning")])]
        assert _v(facts)["verify_rounds"]["empty"] == 0

    def test_rereviews(self):
        facts = [
            _review("r1", base="b0", head="h1"),
            _review("r2", base="b0", head="h1"),   # same interval
            _review("r3", base="b9", head="h1"),   # same head, wider base
            _review("r4", base="b0", head="h2"),   # new tree
        ]
        assert _v(facts)["rereviews"] == {"same_interval": 1, "same_head_tree": 2}

    def test_stop_blocks_per_session_by_gate_and_loops(self):
        facts = [
            _fact("session-start", {}, fid="s-1", session="s1"),
            _fact("session-start", {}, fid="s-2", session="s2"),
            _block("reflection", "x1"), _block("clear-verdict", "x1"),
            _block("reflection", "x2"), _block("reflection", "x3"),
        ]
        sb = _v(facts)["stop_blocks"]
        assert sb["blocks"] == 4 and sb["stops_blocked"] == 3
        assert sb["stops_blocked_per_session"] == 1.5
        assert sb["by_gate"] == {"reflection": 3, "clear-verdict": 1}
        assert sb["loops"] == 1

    def test_guard_refusals_exclude_stop_blocks(self):
        facts = [
            _fact("guard-refusal", {"guard": "critic-dispatch-free-interval"}, fid="g1"),
            _block("reflection", "x1"),
        ]
        g = _v(facts)["guard_refusals"]
        assert g["by_guard"] == {"critic-dispatch-free-interval": 1}
        assert g["per_session"] is None  # no session-start facts: no denominator, no rate

    def test_a_transfer_grant_is_a_pass_not_a_refusal(self):
        facts = [
            _fact("session-start", {}, fid="s"),
            _fact("guard-refusal", {"guard": "critic-dispatch-free-interval"}, fid="g1"),
            _fact("guard-refusal", {"guard": evidence.TRANSFER_GRANT_GUARD}, fid="g2"),
            _fact("guard-refusal", {"guard": evidence.TRANSFER_GRANT_GUARD}, fid="g3"),
        ]
        v = _v(facts)
        assert v["guard_refusals"]["by_guard"] == {"critic-dispatch-free-interval": 1}
        assert v["guard_refusals"]["per_session"] == 1
        assert v["transfer_grants"] == {"total": 2, "per_session": 2}

    def test_the_grant_guard_is_the_one_gates_records(self):
        from lib import gates

        assert gates._TRANSFER_GUARD == evidence.TRANSFER_GRANT_GUARD == "base-advance-transfer"

    def test_per_session_rates_count_only_sessions_that_recorded_their_start(self):
        """A block from a session older than the session-start fact has no
        denominator; counting it against the sessions that do inflates the rate."""
        facts = [
            _fact("session-start", {}, fid="s-2", session="s2"),
            _block("reflection", "x1", session="s1"),
            _block("reflection", "x2", session="s2"),
        ]
        sb = _v(facts)["stop_blocks"]
        assert sb["stops_blocked"] == 2 and sb["stops_blocked_per_session"] == 1.0


class TestPopulation:
    def test_p90_is_nearest_rank(self):
        assert stats._population([1, 9])["p90"] == 9
        assert stats._population(list(range(1, 11)))["p90"] == 9
        assert stats._population([5])["p90"] == 5


class TestWindow:
    def test_window_scopes_by_fact_time(self):
        facts = [_review("r1", ts="2026-09-01T00:00:00Z"), _review("r2", ts="2026-10-01T00:00:00Z", head="h2")]
        assert _v(facts, since="2026-09-15")["reviews"]["total"] == 1

    def test_a_review_before_the_window_still_makes_a_later_one_a_rereview(self):
        facts = [_review("r1", ts="2026-09-01T00:00:00Z"), _review("r2", ts="2026-10-01T00:00:00Z")]
        v = _v(facts, since="2026-09-15")
        assert v["reviews"]["total"] == 1
        assert v["rereviews"] == {"same_interval": 1, "same_head_tree": 1}

    def test_a_disposition_outside_the_window_still_answers_an_inside_finding(self):
        facts = [
            _review("r1", ts="2026-10-01T00:00:00Z", findings=[_finding("R-1", "blocking")]),
            {**_resolution("r1", "R-1"), "ts": "2026-10-05T00:00:00Z"},
        ]
        assert _v(facts, until="2026-10-02")["findings"]["blocking"]["fixed"] == 1


def _git(repo, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   cwd=str(repo), check=True, capture_output=True, timeout=15)


class TestCli:
    def _repo(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        (repo / ".prawduct").mkdir()
        # A session boundary writes this marker before it records its fact; the
        # fact's session identity is read from it.
        (repo / ".prawduct" / ".session-start").write_text("2026-10-03T00:00:00Z")
        return repo

    def _run(self, repo, *args):
        return subprocess.run(
            [sys.executable, str(_ROOT / "bin" / "prawduct-hook"), "stats", *args],
            cwd=str(repo), capture_output=True, text=True, timeout=60,
            env={"CLAUDE_PROJECT_DIR": str(repo), "CLAUDE_PLUGIN_ROOT": str(_ROOT),
                 "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(repo.parent)},
        )

    def test_json_contract(self, tmp_path):
        repo = self._repo(tmp_path)
        evidence.append_session_start(repo)
        result = self._run(repo, "--json")
        assert result.returncode == 0, result.stderr
        report = json.loads(result.stdout)
        assert report["schema_version"] == stats.REPORT_SCHEMA_VERSION
        assert report["window"] == {"since": None, "until": None}
        (version,) = report["by_version"]
        assert report["by_version"][version]["sessions"] == 1

    def test_the_human_report_renders_each_version(self, tmp_path):
        repo = self._repo(tmp_path)
        evidence.append_session_start(repo)
        evidence.append_stop_block(repo, ["reflection"])
        result = self._run(repo)
        assert result.returncode == 0, result.stderr
        assert "1 session(s)" in result.stdout
        assert "stops blocked      1 (1 per recorded session)" in result.stdout
        assert "reflection 1" in result.stdout
        assert "acted on" in result.stdout

    def test_the_human_report_says_when_newer_facts_were_left_out(self):
        base = {"project": "p", "window": {"since": None, "until": None}, "by_version": {}}
        assert "newer plugin are not counted" in stats.render_human({**base, "schema_ahead": 3})
        assert "newer plugin" not in stats.render_human({**base, "schema_ahead": 0})

    def test_empty_store_is_an_answer(self, tmp_path):
        result = self._run(self._repo(tmp_path))
        assert result.returncode == 0
        assert "no governance history" in result.stdout

    @pytest.mark.parametrize("args", [["--since"], ["--since", "last tuesday"], ["--bogus"]])
    def test_bad_arguments_exit_1(self, tmp_path, args):
        assert self._run(self._repo(tmp_path), *args).returncode == 1
