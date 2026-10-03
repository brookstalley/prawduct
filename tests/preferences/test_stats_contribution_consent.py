"""The stats upload is off unless a product's owner opts in, and sends only what was approved.

The owner's condition for the collector (2026-10-03): "off by default and
consuming repos must affirmatively opt in". So every way the
``Stats contribution`` row can fail to say ``ask`` or ``always`` reads as
``never``, and ``never`` refuses before the transport seam with nothing
recorded. Each refusal is asserted at the seam, because "an error was
returned" and "nothing was sent" are different claims and only the second is
the guarantee. The send path is then driven against a real local HTTP server,
once directly and once through ``HTTPS_PROXY``.
"""

from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2] / "plugin"
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lib import contribution  # noqa: E402
from test_contribution import NOW, _repo_with_store, _reviews  # noqa: E402

#: A second closed week, so a send has two windows to order.
EARLIER_WEEK = "2026-09-23T10:00:00Z"  # ISO 2026-W39


def _repo(tmp_path, row: "str | None"):
    repo = _repo_with_store(tmp_path, _reviews(5) + _reviews(5, ts=EARLIER_WEEK))
    if row is not None:
        prefs = repo / ".prawduct" / "artifacts"
        prefs.mkdir(parents=True, exist_ok=True)
        (prefs / "project-preferences.md").write_text(f"# Preferences\n\n{row}\n")
    return repo


def _digest(repo) -> str:
    sent, _ = contribution.read_sent(repo)
    facts = contribution.evidence.read_facts(repo)["facts"]
    pending = contribution.pending_reports(facts, NOW, sent, contribution.load_schema())
    return contribution.reports_digest([item["report"] for item in pending])


@pytest.fixture
def seam(monkeypatch):
    """Record every POST instead of making it; the endpoint is pinned to a
    placeholder so the endpoint check is not what refuses."""
    calls = []
    monkeypatch.setattr(contribution, "COLLECTOR_ENDPOINT", "https://collector.example/v1/report")
    monkeypatch.setattr(contribution, "_post", lambda url, body: calls.append((url, body)))
    return calls


def _send(repo, *args):
    return contribution.contribute_cmd(repo, ["--send", *args], now=NOW)


class TestPreference:
    @pytest.mark.parametrize(
        "row, state",
        [
            ("- **Stats contribution**: ask", "ask"),
            ("- **Stats contribution**: always (standing consent)", "always"),
            ("* **stats contribution** : `ASK`", "ask"),
            ("- **Stats contribution**: never", "never"),
        ],
    )
    def test_a_written_state_is_read(self, tmp_path, row, state):
        assert contribution.read_preference(_repo(tmp_path, row)) == (state, None)

    def test_an_absent_file_is_never_and_silent(self, tmp_path):
        assert contribution.read_preference(_repo(tmp_path, None)) == ("never", None)

    def test_an_absent_row_is_never_and_silent(self, tmp_path):
        repo = _repo(tmp_path, "- **Upstream filing**: always-file")
        assert contribution.read_preference(repo) == ("never", None)

    @pytest.mark.parametrize("row", ["- **Stats contribution**:", "- **Stats contribution**: (unset — reads as never)"])
    def test_an_unset_row_is_never_and_silent(self, tmp_path, row):
        assert contribution.read_preference(_repo(tmp_path, row)) == ("never", None)

    @pytest.mark.parametrize("row", ["- **Stats contribution**: yes", "- **Stats contribution**: alwyas"])
    def test_an_unrecognised_row_is_never_and_says_so(self, tmp_path, row):
        state, warning = contribution.read_preference(_repo(tmp_path, row))
        assert state == "never" and "reads as never" in warning

    def test_an_unreadable_file_is_never_and_says_so(self, tmp_path):
        repo = _repo(tmp_path, None)
        (repo / ".prawduct" / "artifacts").mkdir(parents=True, exist_ok=True)
        (repo / ".prawduct" / "artifacts" / "project-preferences.md").mkdir()  # reading a dir raises
        state, warning = contribution.read_preference(repo)
        assert state == "never" and "could not be read" in warning

    def test_the_shipped_template_row_is_present_unset_and_reads_never(self, tmp_path):
        from lib import core

        template = (_ROOT / "templates" / "project-preferences.md").read_text(encoding="utf-8")
        prefs = tmp_path / ".prawduct" / "artifacts"
        prefs.mkdir(parents=True)
        (prefs / "project-preferences.md").write_text(template, encoding="utf-8")
        # Present but unset, so the janitor still asks; and through the real
        # reader it is a silent never, so nothing is sent before it does.
        row = core.read_preference_row(tmp_path, contribution.PREFERENCE_LABEL)
        assert (row.state, row.value) == (core.PREF_ROW_PRESENT, "")
        assert contribution.read_preference(tmp_path) == ("never", None)


class TestRefusalsReachNoSeam:
    @pytest.mark.parametrize(
        "row",
        [None, "- **Upstream filing**: ask-user", "- **Stats contribution**: never", "- **Stats contribution**: yes"],
    )
    def test_without_an_opt_in_nothing_is_sent_or_recorded(self, tmp_path, seam, capsys, row):
        repo = _repo(tmp_path, row)
        assert _send(repo) == 2
        assert seam == []
        assert not contribution.sent_record_path(repo).exists()
        assert "is never, so nothing can be sent" in capsys.readouterr().err

    def test_never_refuses_even_with_a_matching_digest(self, tmp_path, seam):
        repo = _repo(tmp_path, "- **Stats contribution**: never")
        assert _send(repo, "--approve", _digest(repo)) == 2
        assert seam == []

    def test_ask_without_a_digest_refuses(self, tmp_path, seam):
        repo = _repo(tmp_path, "- **Stats contribution**: ask")
        assert _send(repo) == 2
        assert seam == [] and not contribution.sent_record_path(repo).exists()

    def test_ask_with_a_digest_of_other_bytes_refuses(self, tmp_path, seam):
        repo = _repo(tmp_path, "- **Stats contribution**: ask")
        stale = _digest(repo)
        contribution._write_sent(repo, {"2026-W39:3.7"})  # the pending set changes under the approval
        assert _send(repo, "--approve", stale) == 2
        assert seam == []

    def test_always_with_a_stale_digest_refuses(self, tmp_path, seam):
        repo = _repo(tmp_path, "- **Stats contribution**: always")
        assert _send(repo, "--approve", "sha256:" + "0" * 64) == 2
        assert seam == []

    def test_no_pinned_endpoint_refuses_and_names_the_collector(self, tmp_path, seam, monkeypatch, capsys):
        monkeypatch.setattr(contribution, "COLLECTOR_ENDPOINT", "")
        repo = _repo(tmp_path, "- **Stats contribution**: always")
        assert _send(repo) == 2
        assert seam == [] and not contribution.sent_record_path(repo).exists()
        assert "prawduct's collector is not deployed yet" in capsys.readouterr().err

    def test_no_emitted_text_names_an_internal_id(self):
        """Operator-facing text names no prawduct-internal identifier, such as a
        backlog number (observability-strategy § Direction). Walks every string
        the module hands to print or a refusal."""
        import ast

        tree = ast.parse((_ROOT / "lib" / "contribution.py").read_text(encoding="utf-8"))
        emitted = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) in ("print", "_refuse"):
                for arg in node.args:
                    for part in ast.walk(arg):
                        if isinstance(part, ast.Constant) and isinstance(part.value, str):
                            emitted.append(part.value)
        assert emitted, "the walk found no emitted strings, so it checked nothing"
        assert not [t for t in emitted if __import__("re").search(r"#\d", t)]

    def test_the_shipped_endpoint_is_empty_or_https(self):
        assert contribution.COLLECTOR_ENDPOINT == "" or contribution.COLLECTOR_ENDPOINT.startswith("https://")


class TestSending:
    def test_ask_with_the_previewed_digest_sends_exactly_the_previewed_bytes(self, tmp_path, seam):
        repo = _repo(tmp_path, "- **Stats contribution**: ask")
        preview = json.loads(_preview_json(repo))
        assert _send(repo, "--approve", preview["digest"]) == 0
        assert [body for _, body in seam] == [
            contribution.canonical_bytes(item["report"]) for item in preview["pending"]
        ]
        assert {url for url, _ in seam} == {contribution.COLLECTOR_ENDPOINT}

    def test_always_sends_without_a_digest(self, tmp_path, seam):
        repo = _repo(tmp_path, "- **Stats contribution**: always")
        assert _send(repo) == 0
        assert len(seam) == 2

    def test_a_sent_window_is_never_sent_again(self, tmp_path, seam, capsys):
        repo = _repo(tmp_path, "- **Stats contribution**: always")
        assert _send(repo) == 0
        assert _send(repo) == 0
        assert len(seam) == 2
        assert "no settled window is waiting" in capsys.readouterr().out

    def test_a_send_that_may_have_arrived_is_not_retried(self, tmp_path, seam, monkeypatch):
        repo = _repo(tmp_path, "- **Stats contribution**: always")

        def times_out(url, body):
            seam.append((url, body))
            raise contribution.MaybeArrived("timed out")

        monkeypatch.setattr(contribution, "_post", times_out)
        assert _send(repo) == 1
        assert _send(repo) == 0
        assert len(seam) == 2  # two windows, each tried once

    def test_a_send_that_never_arrived_stays_pending(self, tmp_path, seam, monkeypatch):
        repo = _repo(tmp_path, "- **Stats contribution**: always")

        def refused(url, body):
            seam.append((url, body))
            raise contribution.NeverArrived("connection refused")

        monkeypatch.setattr(contribution, "_post", refused)
        assert _send(repo) == 1
        assert _send(repo) == 1
        assert len(seam) == 4  # both windows tried on both runs
        assert contribution.read_sent(repo) == (set(), None)

    def test_an_unwritable_record_sends_nothing(self, tmp_path, seam, monkeypatch):
        repo = _repo(tmp_path, "- **Stats contribution**: always")

        def unwritable(project_dir, windows):
            raise OSError("read-only file system")

        monkeypatch.setattr(contribution, "_write_sent", unwritable)
        assert _send(repo) == 1
        assert seam == []


def _preview_json(repo) -> str:
    import contextlib
    import io

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert contribution.contribute_cmd(repo, ["--json"], now=NOW) == 0
    return out.getvalue()


class _Recorder(BaseHTTPRequestHandler):
    seen: list = []
    status = 204
    location = None
    reply = b""

    def _record(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        type(self).seen.append((self.command, self.path, dict(self.headers), body))
        self.send_response(type(self).status)
        if type(self).location:
            self.send_header("Location", type(self).location)
        self.send_header("Content-Length", str(len(type(self).reply)))
        self.end_headers()
        self.wfile.write(type(self).reply)

    do_POST = do_GET = do_CONNECT = _record

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    _Recorder.seen, _Recorder.status, _Recorder.location, _Recorder.reply = [], 204, None, b""
    httpd = HTTPServer(("127.0.0.1", 0), _Recorder)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


class TestTransport:
    def test_the_bytes_that_arrive_are_the_canonical_bytes_and_name_no_runtime(
        self, tmp_path, server, monkeypatch
    ):
        monkeypatch.delenv("HTTP_PROXY", raising=False)
        monkeypatch.delenv("http_proxy", raising=False)
        monkeypatch.setattr(contribution, "COLLECTOR_ENDPOINT", f"{server}/v1/report")
        repo = _repo(tmp_path, "- **Stats contribution**: always")
        preview = json.loads(_preview_json(repo))
        assert _send(repo) == 0
        assert [body for *_, body in _Recorder.seen] == [
            contribution.canonical_bytes(item["report"]) for item in preview["pending"]
        ]
        method, path, headers, _ = _Recorder.seen[0]
        assert (method, path) == ("POST", "/v1/report")
        assert headers["User-Agent"] == contribution.USER_AGENT
        assert "Python" not in json.dumps(headers)

    def test_https_proxy_is_honoured(self, tmp_path, server, monkeypatch):
        monkeypatch.setenv("HTTPS_PROXY", server)
        monkeypatch.setenv("https_proxy", server)
        monkeypatch.delenv("NO_PROXY", raising=False)
        monkeypatch.delenv("no_proxy", raising=False)
        _Recorder.status = 403  # the proxy declines the tunnel
        monkeypatch.setattr(contribution, "COLLECTOR_ENDPOINT", "https://collector.invalid/v1/report")
        repo = _repo(tmp_path, "- **Stats contribution**: always")
        assert _send(repo) == 1
        assert ("CONNECT", "collector.invalid:443") in [(m, p) for m, p, *_ in _Recorder.seen]
        # A tunnel the proxy declined carried no byte of the report, so the
        # window stays pending rather than being spent.
        assert contribution.read_sent(repo) == (set(), None)

    def test_a_redirect_is_refused_not_followed(self, tmp_path, server, monkeypatch):
        monkeypatch.delenv("HTTP_PROXY", raising=False)
        monkeypatch.delenv("http_proxy", raising=False)
        # 302 is the redirect urllib's default handler follows for a POST (as a
        # GET), so only the pinned-endpoint guard can stop it. A 307 would not
        # tell the guard from its absence.
        _Recorder.status, _Recorder.location = 302, f"{server}/elsewhere"
        monkeypatch.setattr(contribution, "COLLECTOR_ENDPOINT", f"{server}/v1/report")
        repo = _repo(tmp_path, "- **Stats contribution**: always")
        assert _send(repo) == 1
        assert [p for _, p, *_ in _Recorder.seen] == ["/v1/report", "/v1/report"]

    def test_a_refused_connection_never_arrived(self):
        # Bind a port and close it, so nothing is listening there.
        probe = __import__("socket").socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        with pytest.raises(contribution.NeverArrived):
            contribution._post(f"http://127.0.0.1:{port}/v1/report", b"{}")

    def test_a_garbled_reply_is_a_failed_send_not_a_crash(self, tmp_path, monkeypatch):
        import socket as socket_mod

        listener = socket_mod.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(4)

        def serve():
            for _ in range(2):
                conn, _ = listener.accept()
                conn.recv(65536)
                conn.sendall(b"garbage that is not HTTP\r\n\r\n")
                conn.close()

        threading.Thread(target=serve, daemon=True).start()
        monkeypatch.delenv("HTTP_PROXY", raising=False)
        monkeypatch.delenv("http_proxy", raising=False)
        port = listener.getsockname()[1]
        monkeypatch.setattr(contribution, "COLLECTOR_ENDPOINT", f"http://127.0.0.1:{port}/v1/report")
        repo = _repo(tmp_path, "- **Stats contribution**: always")
        try:
            assert _send(repo) == 1
        finally:
            listener.close()
        assert _send(repo) == 0  # recorded: it may have arrived

    @pytest.mark.parametrize("status, body, stays_pending, says", [
        (400, b'{"refused":"unknown-key"}', True, "refused: unknown-key"),
        (503, b"", True, "HTTP 503"),
        (500, b"", False, "may or may not have arrived"),
    ])
    def test_the_collectors_reply_decides_whether_a_window_is_spent(
        self, tmp_path, server, monkeypatch, capsys, status, body, stays_pending, says
    ):
        monkeypatch.delenv("HTTP_PROXY", raising=False)
        monkeypatch.delenv("http_proxy", raising=False)
        _Recorder.status, _Recorder.reply = status, body
        monkeypatch.setattr(contribution, "COLLECTOR_ENDPOINT", f"{server}/v1/report")
        repo = _repo(tmp_path, "- **Stats contribution**: always")
        assert _send(repo) == 1
        assert says in capsys.readouterr().err
        assert (contribution.read_sent(repo)[0] == set()) is stays_pending



class TestCommandSurface:
    def test_approve_without_send_refuses_and_records_nothing(self, tmp_path, seam, capsys):
        repo = _repo(tmp_path, "- **Stats contribution**: ask")
        assert contribution.contribute_cmd(repo, ["--approve", _digest(repo)], now=NOW) == 1
        assert seam == [] and not contribution.sent_record_path(repo).exists()
        out = capsys.readouterr()
        assert out.out == "" and "--approve only means something with --send" in out.err

    def test_send_with_json_refuses(self, tmp_path, seam, capsys):
        repo = _repo(tmp_path, "- **Stats contribution**: always")
        assert contribution.contribute_cmd(repo, ["--send", "--json"], now=NOW) == 1
        assert seam == [] and not contribution.sent_record_path(repo).exists()
        assert "--json is a preview format" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "row, line",
        [
            (None, "is never, so nothing can be sent"),
            ("- **Stats contribution**: ask", "Sending needs `contribute --send --approve <digest>`"),
            ("- **Stats contribution**: always", "`contribute --send` sends without a digest"),
        ],
    )
    def test_the_human_preview_ends_with_its_consent_line(self, tmp_path, capsys, row, line):
        repo = _repo(tmp_path, row)
        assert contribution.contribute_cmd(repo, [], now=NOW) == 0
        last = capsys.readouterr().out.rstrip("\n").splitlines()[-1]
        assert last.startswith("consent: ") and line in last



class TestSendLock:
    def test_a_live_lock_sends_nothing(self, tmp_path, seam, capsys):
        repo = _repo(tmp_path, "- **Stats contribution**: always")
        lock = contribution.sent_record_path(repo).with_name(contribution.SEND_LOCK_BASENAME)
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("")
        assert _send(repo) == 1
        assert seam == [] and "another session on this clone is sending" in capsys.readouterr().err
        assert lock.exists()  # someone else's lock is not ours to remove

    def test_a_stale_lock_is_taken_over_and_released(self, tmp_path, seam):
        import os

        repo = _repo(tmp_path, "- **Stats contribution**: always")
        lock = contribution.sent_record_path(repo).with_name(contribution.SEND_LOCK_BASENAME)
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text("")
        old = lock.stat().st_mtime - contribution.STALE_LOCK_SECONDS - 1
        os.utime(lock, (old, old))
        assert _send(repo) == 0
        assert len(seam) == 2 and not lock.exists()

    def test_a_window_sent_by_another_session_since_the_preview_is_skipped(self, tmp_path, seam, monkeypatch):
        repo = _repo(tmp_path, "- **Stats contribution**: always")
        real = contribution._send_locked

        def other_session_sent_one_first(project_dir, pending):
            contribution._write_sent(project_dir, {pending[0]["window"]})
            return real(project_dir, pending)

        monkeypatch.setattr(contribution, "_send_locked", other_session_sent_one_first)
        assert _send(repo) == 0
        assert len(seam) == 1


def test_a_failed_tls_handshake_never_arrived(server):
    """https against a plain-HTTP listener fails in the handshake, before any
    byte of the report is written, so the window must stay pending."""
    plain = server.replace("http://", "https://")
    with pytest.raises(contribution.NeverArrived):
        contribution._post(f"{plain}/v1/report", b"{}")
