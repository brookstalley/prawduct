"""``prawduct-hook contribute`` — the anonymous report, before anything is sent.

The allowlist is pinned from both sides: every way a value could carry text or
an identifier is refused by the validator, and the schema itself is walked to
show it admits none. Coarsening, floors and windows are each pinned beside
the case that would falsify them, and the preview is pinned end to end over a
real store, with the network unreachable.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(_ROOT))

from lib import contribution, evidence  # noqa: E402

SCHEMA = contribution.load_schema()
#: A Wednesday. The week that ended three days ago (W41) has not settled yet;
#: the week before it (W40) has.
NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
LAST_WEEK = "2026-09-30T10:00:00Z"  # ISO 2026-W40, settled at NOW
UNSETTLED_WEEK = "2026-10-06T10:00:00Z"  # ISO 2026-W41, ended under SETTLE_DAYS ago


def _fact(kind, body, *, fid, ts=LAST_WEEK, plugin="3.7.1", session="s1"):
    return {
        "schema": 1,
        "kind": kind,
        "id": fid,
        "ts": ts,
        "actor": {"session": session, "worktree": "/w", "plugin": plugin},
        "body": body,
    }


def _reviews(n, *, ts=LAST_WEEK, plugin="3.7.1", scopes=None, findings=()):
    """``n`` reviews, each of its own scope unless ``scopes`` says otherwise."""
    return [
        _fact(
            "review",
            {
                "mode": "chunk",
                "base_tree": f"b{i}",
                "head_tree": f"h{i}",
                "scope": scopes[i] if scopes else f"scope-{i}",
                "findings": list(findings),
                "duration_seconds": 300,
            },
            fid=f"r{i}-{ts}-{plugin}",
            ts=ts,
            plugin=plugin,
        )
        for i in range(n)
    ]


def _sessions(n, *, ts=LAST_WEEK, plugin="3.7.1"):
    return [
        _fact("session-start", {}, fid=f"s{i}-{ts}", ts=ts, plugin=plugin, session=f"s{i}")
        for i in range(n)
    ]


def _pending(facts, sent=frozenset()):
    return contribution.pending_reports(facts, NOW, set(sent), SCHEMA)


def _only_report(facts):
    (item,) = _pending(facts)
    return item["report"]


def _valid_report(**overrides):
    report = {
        "schema": 1, "iso_year": 2026, "iso_week": 40, "plugin_major": 3,
        "plugin_minor": 7, "dev": False, "reviews": "1-9",
    }
    report.update(overrides)
    return report


class TestValidator:
    def test_a_well_formed_report_passes(self):
        assert contribution.validate(_valid_report(blocking_per_review=0.3), SCHEMA) == []

    def test_a_key_outside_the_allowlist_is_refused(self):
        problems = contribution.validate(_valid_report(product="acme"), SCHEMA)
        assert problems == ["product: not in the allowlist"]

    @pytest.mark.parametrize(
        "field, value",
        [
            ("reviews", "lots"),  # band field, text outside the bands
            ("dev", "false"),  # enum of booleans, text lookalike
            ("dev", 0),  # enum of booleans, int lookalike
            ("blocking_per_review", "0.3"),  # number field, text
            ("blocking_per_review", True),  # bool is an int subclass
            ("blocking_per_review", None),
            ("blocking_per_review", [0.3]),
            ("iso_week", 40.0),  # integer field, float
            ("blocking_per_review", float("nan")),
        ],
    )
    def test_a_value_that_is_not_its_fields_type_is_refused(self, field, value):
        assert contribution.validate(_valid_report(**{field: value}), SCHEMA)

    def test_an_off_step_number_is_refused(self):
        assert contribution.validate(_valid_report(blocking_per_review=0.33), SCHEMA)
        assert contribution.validate(_valid_report(blocking_per_review=0.3), SCHEMA) == []

    def test_an_out_of_range_number_is_refused(self):
        assert contribution.validate(_valid_report(red_test_run_share=1.05), SCHEMA)
        assert contribution.validate(_valid_report(iso_week=54), SCHEMA)
        # Outside input could be any JSON integer; a huge one is refused, not raised on.
        assert contribution.validate(_valid_report(iso_week=10**400), SCHEMA)
        assert contribution.validate(_valid_report(red_test_run_share=1), SCHEMA) == []

    def test_a_missing_header_field_is_refused(self):
        report = _valid_report()
        del report["plugin_minor"]
        assert contribution.validate(report, SCHEMA) == ["plugin_minor: required and missing"]

    def test_a_non_object_is_refused(self):
        assert contribution.validate(["schema", 1], SCHEMA)


class TestSchemaAdmitsNoText:
    def test_every_field_is_an_integer_a_stepped_number_or_a_closed_enum(self):
        assert SCHEMA["fields"], "the walk must have fields to walk"
        for name, spec in SCHEMA["fields"].items():
            kind = spec["type"]
            assert kind in ("integer", "number", "enum", "band"), name
            if kind == "number":
                assert spec["step"] > 0 and spec["max"] >= spec["min"], name
            if kind == "enum":
                assert all(isinstance(v, (bool, int)) for v in spec["values"]), name

    def test_bands_are_a_closed_numeric_vocabulary(self):
        for label in SCHEMA["bands"]:
            assert label.replace("-", "").rstrip("+").isdigit(), label

    def test_every_floored_field_names_a_denominator_the_builder_computes(self):
        v = contribution.stats.aggregate(_reviews(1))["3.7"]
        computed = set(contribution._denominators(v))
        floored = {spec["floor_on"] for spec in SCHEMA["fields"].values() if "floor_on" in spec}
        assert floored and floored <= computed

    def test_the_builder_reports_exactly_the_schemas_metrics(self):
        v = contribution.stats.aggregate(_reviews(1))["3.7"]
        metrics = {n for n, s in SCHEMA["fields"].items() if s["type"] == "number"}
        assert set(contribution._metrics(v)) == metrics


class TestCoarsening:
    @pytest.mark.parametrize(
        "count, label", [(0, "0"), (1, "1-9"), (9, "1-9"), (10, "10-49"), (199, "50-199"), (200, "200+"), (9999, "200+")]
    )
    def test_volumes_become_log_bands(self, count, label):
        assert contribution.band(count, SCHEMA["bands"]) == label

    def test_numbers_round_half_up_to_the_step_and_clamp(self):
        share = {"step": 0.05, "min": 0, "max": 1}
        assert contribution.to_step(0.333, share) == 0.35
        assert contribution.to_step(0.324, share) == 0.3
        assert contribution.to_step(1.7, share) == 1
        minutes = {"step": 1, "min": 0, "max": 600}
        assert contribution.to_step(4.5, minutes) == 5 and isinstance(contribution.to_step(4.5, minutes), int)

    def test_the_built_report_is_coarsened(self):
        report = _only_report(_reviews(12) + _sessions(6))
        assert report["reviews"] == "10-49" and report["sessions"] == "1-9"
        assert report["rounds_per_scope_median"] == 1
        assert contribution.validate(report, SCHEMA) == []

    def test_a_dev_build_is_a_flag_and_never_its_build_number(self):
        report = _only_report(_reviews(5, plugin="3.7.1-dev.9871"))
        assert (report["plugin_major"], report["plugin_minor"], report["dev"]) == (3, 7, True)
        assert "9871" not in contribution.canonical_bytes(report).decode()

    def test_a_release_build_reports_dev_false(self):
        assert _only_report(_reviews(5, plugin="3.7.1"))["dev"] is False

    def test_nothing_from_the_facts_text_reaches_the_bytes(self):
        facts = _reviews(6, scopes=["secret-scope"] * 6, findings=[{
            "fid": "f1", "severity": "blocking", "goal": "secret-goal", "title": "secret title",
            "recommendation": "secret",
        }])
        sent = contribution.canonical_bytes(_only_report(facts)).decode()
        assert "secret" not in sent and "/w" not in sent and "s1" not in sent


class TestFloors:
    def test_a_metric_under_its_floor_is_absent(self):
        report = _only_report(_reviews(4))
        assert "estimated_only_review_share" not in report
        assert "blocking_per_review" not in report

    def test_a_metric_at_its_floor_is_present(self):
        report = _only_report(_reviews(5))
        assert report["estimated_only_review_share"] == 1
        assert report["blocking_per_review"] == 0

    def test_each_metric_is_floored_on_its_own_denominator(self):
        # Five reviews but one scope: the per-review metrics clear the floor
        # and the per-scope ones do not.
        report = _only_report(_reviews(5, scopes=["one"] * 5))
        assert "blocking_per_review" in report
        assert "rounds_per_scope_median" not in report
        assert "blocking_fixed_per_scope" not in report

    def test_a_metric_with_no_answer_is_absent_even_above_floor(self):
        # Ten scopes, but no verify-resolutions round: the empty-round share
        # has no denominator and must not be sent as 0.
        report = _only_report(_reviews(10))
        assert "empty_verify_round_share" not in report


class TestWindows:
    def test_only_a_settled_week_is_offered(self):
        pending = _pending(_reviews(5) + _reviews(5, ts=UNSETTLED_WEEK))
        assert [item["window"] for item in pending] == ["2026-W40:3.7"]

    def test_an_open_week_is_not_offered(self):
        facts = _reviews(5, ts="2026-10-13T10:00:00Z")  # ISO 2026-W42, NOW's own week
        assert _pending(facts) == []

    def test_a_week_is_offered_once_it_has_settled(self):
        facts = _reviews(5, ts=UNSETTLED_WEEK)
        settled = NOW + timedelta(days=contribution.SETTLE_DAYS)
        offered = contribution.pending_reports(facts, settled, set(), SCHEMA)
        assert [item["window"] for item in offered] == ["2026-W41:3.7"]

    def test_each_version_in_a_week_is_its_own_window(self):
        facts = _reviews(5, plugin="3.6.2") + _reviews(5, plugin="3.7.0-dev.1")
        assert [item["window"] for item in _pending(facts)] == ["2026-W40:3.6", "2026-W40:3.7-dev"]

    def test_only_the_most_recent_settled_weeks_are_offered(self):
        stamps = [
            (NOW - timedelta(weeks=w)).strftime("%Y-%m-%dT%H:%M:%SZ")
            for w in range(1, contribution.MAX_WEEKS + 4)
        ]
        facts = [f for ts in stamps for f in _reviews(1, ts=ts)]
        pending = _pending(facts)
        assert len(pending) == contribution.MAX_WEEKS
        # NOW is a Wednesday, so the week one week back has not settled and
        # the newest offered is two back.
        newest = (NOW - timedelta(weeks=2)).isocalendar()
        assert pending[-1]["report"]["iso_week"] == newest[1]

    def test_a_sent_window_is_not_offered_again(self):
        facts = _reviews(5) + _reviews(5, plugin="3.6.0")
        pending = _pending(facts, sent={"2026-W40:3.7"})
        assert [item["window"] for item in pending] == ["2026-W40:3.6"]

    def test_a_week_with_only_suite_runs_is_not_a_report(self):
        facts = [_fact("test-run", {"failed": 0}, fid="t1")]
        assert _pending(facts) == []

    def test_a_week_with_sessions_and_no_reviews_is_a_report(self):
        assert [item["window"] for item in _pending(_sessions(2))] == ["2026-W40:3.7"]


class TestDigest:
    def test_the_digest_covers_every_report_and_their_order(self):
        a, b = _valid_report(iso_week=39), _valid_report(iso_week=40)
        assert contribution.reports_digest([a, b]) != contribution.reports_digest([b, a])
        assert contribution.reports_digest([a, b]) != contribution.reports_digest([a])

    def test_bytes_are_canonical(self):
        assert contribution.canonical_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'


def _git(repo, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   cwd=str(repo), check=True, capture_output=True, timeout=15)


def _repo_with_store(tmp_path, facts):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / ".prawduct").mkdir()
    store = evidence.store_path(repo)
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text("".join(json.dumps(f) + "\n" for f in facts))
    return repo


def _last_week_stamp():
    """A stamp in a week that has settled whatever today is: two weeks back
    lands in a week that ended at least SETTLE_DAYS ago."""
    return (datetime.now(timezone.utc) - timedelta(weeks=2)).strftime("%Y-%m-%dT%H:%M:%SZ")


class TestPreviewCommand:
    def _run(self, repo, *args):
        return subprocess.run(
            [sys.executable, str(_ROOT / "bin" / "prawduct-hook"), "contribute", *args],
            cwd=str(repo), capture_output=True, text=True, timeout=60,
            env={"CLAUDE_PROJECT_DIR": str(repo), "CLAUDE_PLUGIN_ROOT": str(_ROOT),
                 "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin", "HOME": str(repo.parent)},
        )

    def test_the_preview_prints_the_exact_bytes_and_their_digest(self, tmp_path):
        repo = _repo_with_store(tmp_path, _reviews(5, ts=_last_week_stamp()))
        result = self._run(repo, "--json")
        assert result.returncode == 0, result.stderr
        preview = json.loads(result.stdout)
        (item,) = preview["pending"]
        assert preview["digest"] == contribution.reports_digest([item["report"]])
        human = self._run(repo)
        assert human.returncode == 0, human.stderr
        assert contribution.canonical_bytes(item["report"]).decode() in human.stdout.splitlines()
        assert f"digest {preview['digest']}" in human.stdout

    def test_nothing_pending_is_an_answer(self, tmp_path):
        result = self._run(_repo_with_store(tmp_path, []))
        assert result.returncode == 0, result.stderr
        assert "no settled window is waiting" in result.stdout

    def test_an_unreadable_sent_record_refuses_rather_than_offering_everything(self, tmp_path):
        repo = _repo_with_store(tmp_path, _reviews(5, ts=_last_week_stamp()))
        contribution.sent_record_path(repo).write_text("{not json")
        result = self._run(repo, "--json")
        assert result.returncode == 1
        assert result.stdout == ""
        assert "could not be read" in result.stderr

    def test_a_recorded_window_is_skipped(self, tmp_path):
        repo = _repo_with_store(tmp_path, _reviews(5, ts=_last_week_stamp()))
        (item,) = json.loads(self._run(repo, "--json").stdout)["pending"]
        contribution.sent_record_path(repo).write_text(
            json.dumps({"schema": contribution.SENT_RECORD_SCHEMA, "sent": [item["window"]]})
        )
        assert json.loads(self._run(repo, "--json").stdout)["pending"] == []

    def test_bad_arguments_exit_1(self, tmp_path):
        assert self._run(_repo_with_store(tmp_path, []), "--send-it").returncode == 1

    def test_a_report_failing_the_allowlist_is_never_offered(self, tmp_path, monkeypatch, capsys):
        repo = _repo_with_store(tmp_path, _reviews(5, ts=_last_week_stamp()))
        real = contribution.build_report
        monkeypatch.setattr(
            contribution, "build_report", lambda *a, **k: {**real(*a, **k), "product": "acme"}
        )
        assert contribution.contribute_cmd(repo, []) == 2
        out = capsys.readouterr()
        assert out.out == ""
        assert "product: not in the allowlist" in out.err

    def test_the_preview_opens_no_socket(self, tmp_path, monkeypatch, capsys):
        repo = _repo_with_store(tmp_path, _reviews(5, ts=_last_week_stamp()))

        def refuse(*args, **kwargs):
            raise AssertionError("the preview opened a socket")

        monkeypatch.setattr(socket, "socket", refuse)
        monkeypatch.setattr(socket, "create_connection", refuse)
        assert contribution.contribute_cmd(repo, []) == 0
        assert "digest sha256:" in capsys.readouterr().out
