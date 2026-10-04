"""``prawduct-hook aggregate-stats`` — local products and contributed reports, one view.

A local product's reports are pinned to the contribution client's own builder,
so local and contributed numbers share one definition. Each way a named input
can fail is pinned beside a product that still reports, bundle lines are
pinned as untrusted (refused lines counted, duplicates kept), and versions are
pinned never to pool.
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(_ROOT))

from lib import aggregate, contribution, evidence  # noqa: E402

SCHEMA = contribution.load_schema()
#: A Wednesday; ISO 2026-W40 and every week before it have settled.
NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
W40 = "2026-09-30T10:00:00Z"
W39 = "2026-09-23T10:00:00Z"
#: Thirteen weeks back: outside the client's eight-week offer window.
W27 = "2026-07-01T10:00:00Z"


def _fact(kind, body, *, fid, ts, plugin):
    return {
        "schema": 1,
        "kind": kind,
        "id": fid,
        "ts": ts,
        "actor": {"session": "s1", "worktree": "/w", "plugin": plugin},
        "body": body,
    }


def _reviews(n, *, ts=W40, plugin="3.7.1", seconds=300):
    return [
        _fact(
            "review",
            {
                "mode": "chunk",
                "base_tree": f"b{i}",
                "head_tree": f"h{i}",
                "scope": f"scope-{i}",
                "findings": [],
                "duration_seconds": seconds,
            },
            fid=f"r{i}-{ts}-{plugin}",
            ts=ts,
            plugin=plugin,
        )
        for i in range(n)
    ]


def _git(repo, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   cwd=str(repo), check=True, capture_output=True, timeout=15)


def _repo(tmp_path, name, facts=None):
    """A git repo; with ``facts``, a store holding them."""
    repo = tmp_path / name
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    if facts is not None:
        store = evidence.store_path(repo)
        store.parent.mkdir(parents=True, exist_ok=True)
        store.write_text("".join(json.dumps(f) + "\n" for f in facts))
    return repo


def _report(**overrides):
    report = {
        "schema": 1, "iso_year": 2026, "iso_week": 39, "plugin_major": 3,
        "plugin_minor": 7, "dev": False, "reviews": "1-9",
    }
    report.update(overrides)
    return report


def _bundle(path, reports):
    path.write_text("".join(contribution.canonical_bytes(r).decode() + "\n" for r in reports))
    return path


def _run(argv, capsys):
    code = aggregate.aggregate_stats_cmd([str(a) for a in argv], now=NOW)
    out = capsys.readouterr()
    return code, out.out, out.err


def _json(argv, capsys):
    code, out, err = _run([*argv, "--json"], capsys)
    assert code == 0, err
    return json.loads(out)


class TestLocalProducts:
    def test_a_local_report_is_byte_for_byte_what_the_product_would_contribute(self, tmp_path):
        facts = _reviews(6) + _reviews(5, ts=W39, plugin="3.6.2")
        repo = _repo(tmp_path, "a", facts)
        local = aggregate.read_local([str(repo)], NOW, SCHEMA, exclude_sent=False)
        expected = contribution.weekly_reports(facts, NOW, SCHEMA, max_weeks=None)
        assert len(expected) == 2
        assert [contribution.canonical_bytes(r) for r in local["reports"]] == [
            contribution.canonical_bytes(item["report"]) for item in expected
        ]

    def test_local_history_is_not_capped_at_the_clients_offer_window(self, tmp_path):
        facts = _reviews(5) + _reviews(5, ts=W27)
        repo = _repo(tmp_path, "a", facts)
        weeks = {r["iso_week"] for r in aggregate.read_local([str(repo)], NOW, SCHEMA, False)["reports"]}
        assert weeks == {27, 40}
        # The control: the client's own offer drops week 27.
        assert {i["report"]["iso_week"] for i in contribution.pending_reports(facts, NOW, set(), SCHEMA)} == {40}

    def test_each_unreadable_product_is_skipped_with_its_reason_and_the_rest_report(self, tmp_path):
        good = _repo(tmp_path, "good", _reviews(5))
        plain = tmp_path / "plain"
        plain.mkdir()
        bare = _repo(tmp_path, "bare")
        broken = _repo(tmp_path, "broken", [])
        evidence.store_path(broken).write_bytes(b"\xff\xfe not utf-8\n")
        local = aggregate.read_local(
            [str(good), str(tmp_path / "missing"), str(plain), str(bare), str(broken)],
            NOW, SCHEMA, exclude_sent=False,
        )
        reasons = {Path(s["path"]).name: s["reason"] for s in local["skipped"]}
        assert reasons == {
            "missing": "invalid-path",
            "plain": "not-a-git-repo",
            "bare": "no-store",
            "broken": "unreadable-store",
        }
        assert [Path(s["path"]).name for s in local["sources"]] == ["good"]
        assert len(local["reports"]) == 1

    def test_two_paths_into_one_clone_count_once(self, tmp_path):
        repo = _repo(tmp_path, "a", _reviews(5))
        _git(repo, "commit", "-q", "--allow-empty", "-m", "init")
        worktree = tmp_path / "a-wt"
        _git(repo, "worktree", "add", "-q", str(worktree))
        local = aggregate.read_local([str(repo), str(worktree)], NOW, SCHEMA, exclude_sent=False)
        assert len(local["reports"]) == 1
        (skip,) = local["skipped"]
        assert skip["reason"] == "same-store" and skip["as"] == str(repo.resolve())

    def test_facts_from_a_newer_plugin_are_reported_not_hidden(self, tmp_path):
        ahead = {**_reviews(1)[0], "schema": 99, "id": "ahead"}
        repo = _repo(tmp_path, "a", _reviews(5) + [ahead])
        (source,) = aggregate.read_local([str(repo)], NOW, SCHEMA, exclude_sent=False)["sources"]
        assert source["schema_ahead"] == 1


class TestSentWindows:
    def _sent(self, repo, windows):
        contribution.sent_record_path(repo).write_text(
            json.dumps({"schema": contribution.SENT_RECORD_SCHEMA, "sent": windows})
        )

    def test_with_contributed_data_a_sent_window_is_left_out_and_counted(self, tmp_path, capsys):
        repo = _repo(tmp_path, "a", _reviews(5) + _reviews(5, ts=W39))
        self._sent(repo, ["2026-W40:3.7"])
        bundle = _bundle(tmp_path / "b.jsonl", [])
        report = _json([repo, "--bundles", bundle], capsys)
        (source,) = report["sources"]["local"]
        assert (source["reports"], source["already_contributed"]) == (1, 1)
        assert report["by_version"]["3.7"]["weeks"] == {"first": "2026-W39", "last": "2026-W39"}

    def test_without_contributed_data_every_window_counts(self, tmp_path, capsys):
        repo = _repo(tmp_path, "a", _reviews(5) + _reviews(5, ts=W39))
        self._sent(repo, ["2026-W40:3.7"])
        (source,) = _json([repo], capsys)["sources"]["local"]
        assert (source["reports"], source["already_contributed"]) == (2, 0)

    def test_an_unreadable_sent_record_skips_the_product_only_when_it_matters(self, tmp_path, capsys):
        repo = _repo(tmp_path, "a", _reviews(5))
        contribution.sent_record_path(repo).write_text("{not json")
        bundle = _bundle(tmp_path / "b.jsonl", [])
        with_bundles = _json([repo, "--bundles", bundle], capsys)
        assert [s["reason"] for s in with_bundles["sources"]["local_skipped"]] == ["unreadable-sent-record"]
        # Without contributed data the record is never read, so nothing skips.
        assert _json([repo], capsys)["sources"]["local_skipped"] == []


class TestBundles:
    def test_a_line_that_does_not_parse_or_fails_the_allowlist_is_refused_and_counted(self):
        text = "\n".join([
            contribution.canonical_bytes(_report()).decode(),
            "{not json",
            json.dumps(_report(product="acme")),
            json.dumps(_report(blocking_per_review=0.33)),
            "",
        ])
        reports, lines, refused = aggregate.parse_bundle(text, SCHEMA)
        assert (len(reports), lines, refused) == (1, 4, 3)

    def test_identical_lines_are_distinct_contributions(self):
        line = contribution.canonical_bytes(_report()).decode()
        reports, lines, refused = aggregate.parse_bundle(f"{line}\n{line}\n", SCHEMA)
        assert (len(reports), lines, refused) == (2, 2, 0)

    def test_a_directory_is_every_bundle_in_it(self, tmp_path, capsys):
        bundles = tmp_path / "bundles"
        bundles.mkdir()
        _bundle(bundles / "2026-10-01.jsonl", [_report()])
        _bundle(bundles / "2026-10-02.jsonl", [_report(), _report(iso_week=38)])
        (bundles / "index.json").write_text('{"days": []}')
        report = _json(["--bundles", bundles], capsys)
        assert report["sources"]["contributed"] == {"bundles": 2, "lines": 3, "refused": 0}
        assert report["by_version"]["3.7"]["reports"] == {"local": 0, "contributed": 3}

    def test_a_named_bundle_that_does_not_exist_exits_1(self, tmp_path, capsys):
        code, out, err = _run(["--bundles", tmp_path / "nope.jsonl"], capsys)
        assert code == 1 and out == ""
        assert "no such file or directory" in err


class TestAggregation:
    def test_versions_never_pool(self):
        local = [_report(review_minutes_median=10)]
        contributed = [
            _report(review_minutes_median=20),
            _report(plugin_minor=6, review_minutes_median=99),
            _report(dev=True, review_minutes_median=500),
        ]
        by_version = aggregate.aggregate(local, contributed, SCHEMA)
        assert list(by_version) == ["3.6", "3.7", "3.7-dev"]
        assert by_version["3.7"]["metrics"]["review_minutes_median"] == {
            "n": 2, "median": 15, "trimmed_mean": 15,
        }
        assert by_version["3.7"]["reports"] == {"local": 1, "contributed": 1}
        assert by_version["3.6"]["metrics"]["review_minutes_median"]["median"] == 99
        assert by_version["3.7-dev"]["metrics"]["review_minutes_median"]["median"] == 500

    def test_versions_sort_numerically(self):
        by_version = aggregate.aggregate(
            [_report(plugin_minor=10), _report(plugin_minor=9)], [], SCHEMA
        )
        assert list(by_version) == ["3.9", "3.10"]

    def test_the_trimmed_mean_drops_a_tenth_from_each_end(self):
        values = [0] * 8 + [10, 10, 100]
        stats = aggregate.robust(values)
        # Eleven values drop one from each end: 0 and 100.
        assert stats == {"n": 11, "median": 0, "trimmed_mean": round(20 / 9, 4)}
        # The control: under ten values nothing is trimmed.
        assert aggregate.robust([0, 0, 90])["trimmed_mean"] == 30

    def test_a_metric_left_out_under_its_floor_is_absent_not_zero(self):
        by_version = aggregate.aggregate(
            [_report(blocking_per_review=0.5), _report(blocking_per_review=0.7), _report()], [], SCHEMA
        )
        metric = by_version["3.7"]["metrics"]["blocking_per_review"]
        assert metric["n"] == 2 and metric["median"] == 0.6
        assert "warning_per_review" not in by_version["3.7"]["metrics"]

    def test_volume_counts_reports_per_band(self):
        by_version = aggregate.aggregate(
            [_report(reviews="1-9"), _report(reviews="10-49"), _report(reviews="10-49", sessions="0")],
            [], SCHEMA,
        )
        volume = by_version["3.7"]["volume"]
        assert volume["reviews"] == {"1-9": 1, "10-49": 2}
        assert volume["sessions"] == {"0": 1}
        assert volume["scopes"] == {}


class TestCommand:
    def test_no_source_exits_1(self, capsys):
        code, out, err = _run([], capsys)
        assert code == 1 and out == ""
        assert "name at least one product or bundle source" in err

    @pytest.mark.parametrize("argv", [["--bogus"], ["--bundles"], ["--from-file"]])
    def test_a_bad_argument_exits_1(self, argv, capsys):
        code, out, err = _run(argv, capsys)
        assert code == 1 and out == ""
        assert "usage: aggregate-stats" in err

    def test_from_file_names_products_and_skips_comments(self, tmp_path, capsys):
        repo = _repo(tmp_path, "a", _reviews(5))
        listing = tmp_path / "products.txt"
        listing.write_text(f"# my products\n\n{repo}\n")
        (source,) = _json(["--from-file", listing], capsys)["sources"]["local"]
        assert source["path"] == str(repo.resolve())

    def test_json_is_deterministic_and_versioned(self, tmp_path, capsys):
        repo = _repo(tmp_path, "a", _reviews(5) + _reviews(5, ts=W39, plugin="3.6.0"))
        bundle = _bundle(tmp_path / "b.jsonl", [_report(review_minutes_median=7)])
        first = _run([repo, "--bundles", bundle, "--json"], capsys)
        second = _run([repo, "--bundles", bundle, "--json"], capsys)
        assert first == second
        report = json.loads(first[1])
        assert report["schema_version"] == aggregate.REPORT_SCHEMA_VERSION == 1
        assert set(report) == {"schema_version", "generated_at", "sources", "by_version"}

    def test_the_human_report_names_sources_versions_and_numbers(self, tmp_path, capsys):
        repo = _repo(tmp_path, "a", _reviews(5))
        bundle = _bundle(
            tmp_path / "b.jsonl",
            [_report(review_minutes_median=7), _report(review_minutes_median=9)],
        )
        code, out, err = _run([repo, tmp_path / "missing", "--bundles", bundle], capsys)
        assert code == 0, err
        lines = out.splitlines()
        assert f"local: {repo.resolve()} — 1 report(s)" in lines
        assert f"skipped: {tmp_path / 'missing'} — invalid-path" in lines
        assert "contributed: 2 line(s) in 1 bundle(s), 0 refused by the allowlist" in lines
        assert "3.7 — 3 report(s): 1 local, 2 contributed; 2026-W39 to 2026-W40" in lines
        assert (
            "each report is one product-week for one plugin version; "
            "every number below is over reports, never across versions"
        ) in lines
        # The local week's review time is a self-estimate, which is never a
        # measurement, so only the two contributed reports carry this metric.
        assert "  review_minutes_median: median 8, trimmed mean 8 (n=2)" in lines

    def test_no_reports_is_an_answer(self, tmp_path, capsys):
        code, out, _ = _run([_repo(tmp_path, "a", [])], capsys)
        assert code == 0
        assert "no settled weeks to report" in out


def test_the_hook_dispatches_the_command(tmp_path):
    """The wiring, end to end: the hook runs the lib body on a real store."""
    stamp = (datetime.now(timezone.utc) - timedelta(weeks=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    repo = _repo(tmp_path, "a", _reviews(5, ts=stamp))
    result = subprocess.run(
        [sys.executable, str(_ROOT / "bin" / "prawduct-hook"), "aggregate-stats", str(repo), "--json"],
        cwd=str(tmp_path), capture_output=True, text=True, timeout=60,
        env={"CLAUDE_PLUGIN_ROOT": str(_ROOT), "HOME": str(tmp_path),
             "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"},
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["sources"]["local"][0]["reports"] == 1
    assert list(report["by_version"]) == ["3.7"]


class TestInputErrors:
    def test_a_from_file_that_cannot_be_read_exits_1(self, tmp_path, capsys):
        code, out, err = _run(["--from-file", tmp_path / "nope.txt"], capsys)
        assert code == 1 and out == ""
        assert "--from-file" in err and "cannot be read" in err

    def test_a_bundle_that_is_not_utf8_exits_1(self, tmp_path, capsys):
        bad = tmp_path / "b.jsonl"
        bad.write_bytes(b"\xff\xfe\n")
        code, out, err = _run(["--bundles", bad], capsys)
        assert code == 1 and out == ""
        assert "cannot be read" in err

    def test_a_deeply_nested_line_is_refused_not_a_traceback(self):
        reports, lines, refused = aggregate.parse_bundle("[" * 100_000 + "\n", SCHEMA)
        assert (reports, lines, refused) == ([], 1, 1)


class _Collector(BaseHTTPRequestHandler):
    """Serves ``routes``: path → (status, body, location)."""

    routes: dict = {}
    seen: list = []

    def do_GET(self):
        type(self).seen.append((self.path, self.headers.get("User-Agent")))
        status, body, location = type(self).routes.get(self.path, (404, b"", None))
        self.send_response(status)
        if location:
            self.send_header("Location", location)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


@pytest.fixture
def collector(monkeypatch):
    """A local collector the pinned endpoint points at, with no proxy between."""
    for name in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"):
        monkeypatch.delenv(name, raising=False)
    _Collector.routes, _Collector.seen = {}, []
    httpd = HTTPServer(("127.0.0.1", 0), _Collector)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{httpd.server_address[1]}"
    monkeypatch.setattr(contribution, "COLLECTOR_ENDPOINT", f"{origin}/v1/report")
    yield origin
    httpd.shutdown()
    httpd.server_close()


def _publish(days: dict) -> None:
    _Collector.routes["/bundles/index.json"] = (200, json.dumps({"days": sorted(days)}).encode(), None)
    for day, reports in days.items():
        body = "".join(contribution.canonical_bytes(r).decode() + "\n" for r in reports).encode()
        _Collector.routes[f"/bundles/{day}.jsonl"] = (200, body, None)


class TestCollectorFetch:
    def test_every_listed_bundle_is_fetched_with_the_prawduct_user_agent(self, collector, capsys):
        _publish({"2026-10-04": [_report()], "2026-10-05": [_report(), _report(iso_week=38)]})
        report = _json(["--collector"], capsys)
        assert report["sources"]["contributed"] == {"bundles": 2, "lines": 3, "refused": 0}
        assert [path for path, _ in _Collector.seen] == [
            "/bundles/index.json", "/bundles/2026-10-04.jsonl", "/bundles/2026-10-05.jsonl",
        ]
        assert {agent for _, agent in _Collector.seen} == {contribution.USER_AGENT}

    def test_no_index_yet_is_zero_bundles_not_a_failure(self, collector, capsys):
        report = _json(["--collector"], capsys)
        assert report["sources"]["contributed"] == {"bundles": 0, "lines": 0, "refused": 0}

    def test_collector_data_leaves_out_windows_the_clone_already_sent(self, tmp_path, collector, capsys):
        repo = _repo(tmp_path, "a", _reviews(5))
        contribution.sent_record_path(repo).write_text(
            json.dumps({"schema": contribution.SENT_RECORD_SCHEMA, "sent": ["2026-W40:3.7"]})
        )
        (source,) = _json([repo, "--collector"], capsys)["sources"]["local"]
        assert (source["reports"], source["already_contributed"]) == (0, 1)

    def test_a_redirect_is_refused_not_followed(self, collector, capsys):
        _Collector.routes["/bundles/index.json"] = (302, b"", f"{collector}/elsewhere")
        _Collector.routes["/elsewhere"] = (200, b'{"days": []}', None)
        code, out, err = _run(["--collector"], capsys)
        assert code == 1 and out == ""
        assert "HTTP 302" in err
        assert [path for path, _ in _Collector.seen] == ["/bundles/index.json"]

    def test_an_oversized_response_exits_1(self, collector, capsys, monkeypatch):
        _publish({"2026-10-04": [_report()] * 20})
        monkeypatch.setattr(aggregate, "MAX_RESPONSE_BYTES", 200)
        code, out, err = _run(["--collector"], capsys)
        assert code == 1 and out == ""
        assert "larger than 200 bytes" in err

    def test_an_unreachable_collector_exits_1(self, monkeypatch, capsys):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        monkeypatch.setattr(contribution, "COLLECTOR_ENDPOINT", f"http://127.0.0.1:{port}/v1/report")
        code, out, err = _run(["--collector"], capsys)
        assert code == 1 and out == ""
        assert "could not be fetched" in err

    @pytest.mark.parametrize("day", ["../claims/current", "2026-10-04/../../x", "２０２６-10-04"])
    def test_an_index_naming_something_other_than_a_day_is_never_requested(self, collector, capsys, day):
        _Collector.routes["/bundles/index.json"] = (200, json.dumps({"days": [day]}).encode(), None)
        code, out, err = _run(["--collector"], capsys)
        assert code == 1 and out == ""
        assert "not a day" in err
        assert [path for path, _ in _Collector.seen] == ["/bundles/index.json"]

    def test_a_listed_bundle_that_is_missing_exits_1(self, collector, capsys):
        _Collector.routes["/bundles/index.json"] = (200, b'{"days": ["2026-10-04"]}', None)
        code, out, err = _run(["--collector"], capsys)
        assert code == 1 and out == ""
        assert "listed in the index but not published" in err

    def test_without_collector_no_socket_is_opened(self, tmp_path, monkeypatch, capsys):
        repo = _repo(tmp_path, "a", _reviews(5))
        bundle = _bundle(tmp_path / "b.jsonl", [_report()])

        def refuse(*args, **kwargs):
            raise AssertionError("aggregate-stats opened a socket")

        monkeypatch.setattr(socket, "socket", refuse)
        monkeypatch.setattr(socket, "create_connection", refuse)
        code, out, err = _run([repo, "--bundles", bundle], capsys)
        assert code == 0, err
        assert "3.7 — 2 report(s)" in out
