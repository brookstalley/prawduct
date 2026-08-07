"""Tests for lib/backlog/transport.py — the egress seam.

Covers the transport obligations: SEC-1 (no token in any output, scrub
backstop + build-from-known-fields), INV-2 (non-interactive env), the gh-failure
→ stable-code mapping (ERR-1 classes at the transport layer), and SEC-3's
resolve-identity-once-per-process memoization mechanism.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest  # noqa: E402

from lib.backlog import transport as tp  # noqa: E402

# One planted secret of each scrub class (Test Specs `token-bait` fixture).
_TOKEN_BAIT = {
    "classic_pat": "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
    "oauth": "gho_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
    "server": "ghs_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
    "refresh": "ghr_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345",
    "fine_pat": "github_pat_11ABCDEFG0abcdefghijklmnopqrstuvwxyz012345",
    "jwt": "eyJhbGciOiJSUzI1NiJ9.eyJpc3MiOiIxMjM0In0.c2lnbmF0dXJl",
    "url_cred": "https://user:s3cr3tpass@github.com/o/r.git",
    "proxy": "proxy-injected",
}
_APP_KEY = "-----BEGIN RSA PRIVATE KEY-----\nMIIabc123\n-----END RSA PRIVATE KEY-----"


def _leaks_secret(text: str) -> bool:
    if not text:
        return False
    for value in _TOKEN_BAIT.values():
        if value in text:
            return True
    if "MIIabc123" in text or "BEGIN RSA PRIVATE KEY" in text:
        return True
    return False


class TestScrubSecrets:
    """SEC-1 — every token class is redacted (the denylist backstop)."""

    @pytest.mark.parametrize("name,secret", list(_TOKEN_BAIT.items()))
    def test_each_token_class_redacted(self, name, secret):
        scrubbed = tp.scrub_secrets(f"noise {secret} more noise")
        assert secret not in scrubbed
        assert "[REDACTED]" in scrubbed

    def test_app_private_key_block_redacted(self):
        scrubbed = tp.scrub_secrets(f"leaked:\n{_APP_KEY}\nend")
        assert "BEGIN RSA PRIVATE KEY" not in scrubbed
        assert "MIIabc123" not in scrubbed

    def test_scrub_is_idempotent_and_none_safe(self):
        assert tp.scrub_secrets(None) == ""
        once = tp.scrub_secrets(f"x {_TOKEN_BAIT['oauth']} y")
        assert tp.scrub_secrets(once) == once


class TestNonInteractiveEnv:
    """INV-2 — the gh env can never prompt, page, or notify."""

    def test_env_disables_prompts_and_pager(self):
        env = tp.build_env({"PATH": "/usr/bin"})
        assert env["GH_PROMPT_DISABLED"] == "1"
        assert env["GH_NO_UPDATE_NOTIFIER"] == "1"
        assert env["GH_PAGER"] == ""
        assert env["PATH"] == "/usr/bin"  # inherits the base


class TestFailureMapping:
    """The gh-exit → stable-code mapping, built from known fields, token-free."""

    def setup_method(self):
        self.t = tp.GhTransport()

    def _map(self, returncode, stderr):
        return self.t._map_failure(["api", "repos/o/r/issues"], returncode, stderr)

    def test_gh_exit_4_is_auth(self):
        err = self._map(4, "authentication required")
        assert err.code == "auth"
        assert err.retryable is False

    def test_http_404_is_not_found(self):
        err = self._map(1, "gh: HTTP 404: Not Found")
        assert err.code == "not_found"

    def test_http_422_is_validation(self):
        err = self._map(1, "gh: HTTP 422: Validation Failed")
        assert err.code == "validation"

    def test_rate_limit_is_rate_limited(self):
        err = self._map(1, "gh: API rate limit exceeded")
        assert err.code == "rate_limited"
        assert err.retryable is True

    def test_rate_limit_surfaces_retry_after_when_present(self):
        # BKL-3K9N — when gh echoes the header, thread it through so the importer
        # honors the server's pause hint instead of guessing a backoff.
        err = self._map(1, "gh: HTTP 429: too many requests (Retry-After: 42)")
        assert err.code == "rate_limited"
        assert err.details["retry_after"] == 42

    def test_rate_limit_without_retry_after_omits_the_key(self):
        # The common case (gh rarely surfaces the header) → no key → the importer
        # falls back to exponential backoff.
        err = self._map(1, "gh: API rate limit exceeded")
        assert "retry_after" not in err.details

    def test_network_is_unavailable(self):
        err = self._map(1, "could not resolve host: api.github.com")
        assert err.code == "unavailable"
        assert err.retryable is True

    def test_unknown_failure_degrades_to_unavailable(self):
        err = self._map(1, "something weird happened")
        assert err.code == "unavailable"

    def test_returncode_surfaced_in_details(self):
        err = self._map(7, "some opaque failure")
        assert err.details["returncode"] == 7

    def test_error_never_leaks_a_token(self):
        # SEC-1: even when raw stderr carries every token class, the mapped
        # error (message + details) is built from known fields and stays clean.
        dirty = (
            "gh: HTTP 401 Unauthorized while using "
            + " ".join(_TOKEN_BAIT.values())
            + "\n"
            + _APP_KEY
        )
        err = self._map(1, dirty)
        assert not _leaks_secret(err.message)
        assert not _leaks_secret(json.dumps(err.details))


class TestRunErrorBranches:
    """The ``_run``/``_api`` failure branches raise a stable-code ``TransportError``
    built from known fields — gh-missing, timeout, and an unparseable JSON body —
    without shelling out (``subprocess.run`` is mocked) and without echoing raw output.
    """

    def test_gh_not_on_path_is_unavailable_not_retryable(self, monkeypatch):
        # FileNotFoundError (gh absent from PATH) → unavailable, retryable=False.
        def _boom(*args, **kwargs):
            raise FileNotFoundError(2, "No such file or directory: 'gh'")

        monkeypatch.setattr(tp.subprocess, "run", _boom)
        t = tp.GhTransport()
        with pytest.raises(tp.TransportError) as excinfo:
            t._run(["api", "user"])
        err = excinfo.value
        assert err.code == "unavailable"
        assert err.retryable is False
        assert err.details.get("transport") == "gh"
        assert not _leaks_secret(err.message)

    def test_timeout_is_unavailable_with_operation(self, monkeypatch):
        # subprocess.TimeoutExpired → unavailable; the operation (never the body)
        # is surfaced in details.
        def _slow(*args, **kwargs):
            raise subprocess.TimeoutExpired(cmd=["gh"], timeout=kwargs.get("timeout", 1))

        monkeypatch.setattr(tp.subprocess, "run", _slow)
        t = tp.GhTransport()
        with pytest.raises(tp.TransportError) as excinfo:
            t._run(["api", "repos/o/r/issues"])
        err = excinfo.value
        assert err.code == "unavailable"
        assert err.details.get("operation") == "api repos/o/r/issues"
        assert not _leaks_secret(err.message)

    def test_unparseable_json_body_is_unavailable_and_not_echoed(self, monkeypatch):
        # _api parses _run's stdout; a non-JSON body maps to a known-field error
        # (SEC-1) and the raw body is never placed in the message.
        raw_body = "<html>502 Bad Gateway</html>"
        monkeypatch.setattr(
            tp.GhTransport, "_run", lambda self, args, input_json=None: raw_body
        )
        t = tp.GhTransport()
        with pytest.raises(tp.TransportError) as excinfo:
            t._api(["api", "repos/o/r/issues/1"])
        err = excinfo.value
        assert err.code == "unavailable"
        assert "unparseable" in err.message.lower()
        assert raw_body not in err.message
        assert raw_body not in json.dumps(err.details)

    def test_empty_stdout_parses_to_empty_dict(self, monkeypatch):
        # A blank (whitespace-only) body is not an error — it decodes to {} so a
        # 204-style response doesn't raise (the ``stdout.strip()`` guard).
        monkeypatch.setattr(
            tp.GhTransport, "_run", lambda self, args, input_json=None: "   \n"
        )
        t = tp.GhTransport()
        assert t._api(["api", "repos/o/r/labels"]) == {}


class TestIdentityMemoization:
    """SEC-3 — the API identity is resolved exactly once per process."""

    def test_get_authenticated_user_resolves_once(self, monkeypatch):
        t = tp.GhTransport()
        api_calls: list[list[str]] = []

        def fake_api(args, input_json=None):
            api_calls.append(args)
            return {"login": "octocat", "id": 1}

        monkeypatch.setattr(t, "_api", fake_api)
        for _ in range(5):
            assert t.get_authenticated_user()["login"] == "octocat"
        user_reads = [c for c in api_calls if c[:2] == ["api", "user"]]
        assert len(user_reads) == 1


class _FakeProc:
    """A finished ``gh`` process, as ``_spawn`` would return one."""

    def __init__(self, *, returncode: int, stdout: str = "", stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class _ProbeGh(tp.GhTransport):
    """GhTransport with ``_spawn`` replaced, so everything above it is real.

    Overriding ``_spawn`` rather than ``_run`` is the point: the conditional path
    is ``get_issues_validator`` → ``_run_conditional`` → ``_parse_head``, none of
    which ``_run`` touches. A fake seated at ``_run`` (or at the transport
    interface, as ``FakeGitHub`` is) leaves that whole stack unexecuted."""

    def __init__(self, proc: _FakeProc):
        super().__init__()
        self.proc = proc
        self.calls: list[list[str]] = []

    def _spawn(self, args, *, input_json=None):
        self.calls.append(args)
        return self.proc


_HEADERS_200 = (
    "HTTP/2.0 200 OK\r\n"
    'Etag: W/"abc123"\r\n'
    "X-Ratelimit-Used: 41\r\n"
    "\r\n"
    "[]\r\n"
)
_HEADERS_304 = 'HTTP/2.0 304 Not Modified\r\nEtag: W/"abc123"\r\n\r\n'


class TestParseHead:
    """`gh api -i` writes the status line and headers to STDOUT — including on a
    304, which is what lets the status be read rather than inferred from stderr
    text (a human-facing string, not a contract)."""

    def test_status_and_headers_come_off_stdout(self):
        status, headers = tp._parse_head(_HEADERS_200)

        assert status == 200
        assert headers["etag"] == 'W/"abc123"'

    def test_header_names_are_lowercased_so_callers_need_not_guess_the_casing(self):
        _status, headers = tp._parse_head("HTTP/2.0 200 OK\r\nETag: W/\"x\"\r\n\r\n")

        assert headers["etag"] == 'W/"x"'

    def test_a_304_is_read_as_a_status_not_as_an_absence(self):
        status, _headers = tp._parse_head(_HEADERS_304)

        assert status == 304

    def test_an_unreadable_response_yields_no_status_which_callers_read_as_changed(self):
        """The safe direction. A misparse that reports "unchanged" would serve a
        stale cache forever; one that reports "changed" costs a single fetch."""
        status, headers = tp._parse_head("not a response at all\r\n\r\n")

        assert status is None
        assert headers == {}

    def test_the_body_after_the_blank_line_is_not_scanned_for_headers(self):
        """A JSON body containing a colon would otherwise be parsed as a header."""
        _status, headers = tp._parse_head(
            'HTTP/2.0 200 OK\r\nEtag: W/"a"\r\n\r\n[{"title": "not: a header"}]'
        )

        assert set(headers) == {"etag"}


class TestConditionalRequest:
    """`gh` EXITS 1 ON A 304 — verified against the live API. Treating that as a
    failure would turn the cheapest successful outcome in the sync path into a
    hard error, so every warm sync would report unavailable."""

    def test_a_304_with_exit_1_is_a_successful_not_modified(self):
        gh = _ProbeGh(_FakeProc(returncode=1, stdout=_HEADERS_304, stderr="gh: HTTP 304"))

        result = gh.get_issues_validator(
            "o", "r", state="all", since="2026-01-01T00:00:00Z", etag='W/"abc123"'
        )

        assert result.changed is False
        assert result.etag == 'W/"abc123"', "a 304 keeps the validator it was asked with"

    def test_a_200_reports_changed_and_returns_the_new_validator(self):
        gh = _ProbeGh(_FakeProc(returncode=0, stdout=_HEADERS_200))

        result = gh.get_issues_validator(
            "o", "r", state="all", since="2026-01-01T00:00:00Z", etag='W/"stale"'
        )

        assert result.changed is True
        assert result.etag == 'W/"abc123"'

    def test_a_real_failure_still_raises_rather_than_reading_as_not_modified(self):
        """Exit 1 is only forgiven when the status line actually says 304."""
        gh = _ProbeGh(
            _FakeProc(returncode=1, stdout="HTTP/2.0 500 Internal Server Error\r\n\r\n",
                      stderr="gh: HTTP 500")
        )

        with pytest.raises(tp.TransportError):
            gh.get_issues_validator("o", "r", state="all", since="2026-01-01T00:00:00Z", etag=None)

    def test_a_response_with_no_etag_reports_changed_rather_than_a_null_validator(self):
        gh = _ProbeGh(_FakeProc(returncode=0, stdout="HTTP/2.0 200 OK\r\n\r\n[]"))

        result = gh.get_issues_validator(
            "o", "r", state="all", since="2026-01-01T00:00:00Z", etag=None
        )

        assert result.changed is True
        assert result.etag is None

    def test_the_stored_validator_is_sent_as_if_none_match(self):
        gh = _ProbeGh(_FakeProc(returncode=1, stdout=_HEADERS_304))

        gh.get_issues_validator("o", "r", state="all", since="2026-01-01T00:00:00Z", etag='W/"e"')

        args = gh.calls[0]
        assert "-i" in args, "headers are unreadable without -i"
        assert 'If-None-Match: W/"e"' in args

    def test_no_conditional_header_is_sent_when_nothing_is_stored(self):
        gh = _ProbeGh(_FakeProc(returncode=0, stdout=_HEADERS_200))

        gh.get_issues_validator("o", "r", state="all", since="2026-01-01T00:00:00Z", etag=None)

        assert not any("If-None-Match" in token for token in gh.calls[0])

    def test_the_probe_query_is_the_one_that_makes_one_row_sufficient(self):
        """Ordered `updated_at` descending: any touched item becomes the single
        row returned, so a byte-identical response means nothing was touched."""
        gh = _ProbeGh(_FakeProc(returncode=0, stdout=_HEADERS_200))

        gh.get_issues_validator("o", "r", state="all", since="2026-01-01T00:00:00Z", etag=None)

        path = gh.calls[0][2]
        assert "sort=updated" in path
        assert "direction=desc" in path
        assert f"per_page={tp.PROBE_PAGE_SIZE}" in path
        assert "state=all" in path
        assert "since=2026-01-01T00%3A00%3A00Z" in path


class TestListIssuesSince:
    def test_since_reaches_the_query_string_url_encoded(self):
        gh = _ProbeGh(_FakeProc(returncode=0, stdout="[]"))

        gh.list_issues("o", "r", state="all", since="2026-01-01T00:00:00Z")

        path = gh.calls[0][1]
        assert "since=2026-01-01T00%3A00%3A00Z" in path

    def test_no_since_parameter_is_sent_when_none_is_given(self):
        gh = _ProbeGh(_FakeProc(returncode=0, stdout="[]"))

        gh.list_issues("o", "r", state="all")

        assert "since=" not in gh.calls[0][1]


class TestBranchExists:
    """The pushed-ref probe behind `working-branch`, exercised through the real
    `GhTransport` stack — `FakeGitHub` sits at the transport *interface*, so it
    cannot reach `_api`/`_run`/`_map_failure`, which is where this lives.

    Endpoint verified live against the backing repo rather than recalled:
    `GET /repos/{owner}/{repo}/branches/{branch}` answers 200 for a pushed branch,
    including a slash-bearing name un-escaped in the path, and 404 `Branch not
    found` otherwise.
    """

    def test_a_pushed_branch_is_true(self):
        gh = _ProbeGh(_FakeProc(returncode=0, stdout='{"name": "main"}'))

        assert gh.branch_exists("o", "r", "main") is True
        assert gh.calls[0] == ["api", "repos/o/r/branches/main"]

    def test_a_slash_bearing_branch_goes_into_the_path_unescaped(self):
        """Verified live: the endpoint takes `feature/backlog-service` directly in
        the path. Percent-encoding the slash would 404 every branch that has one,
        which is most of them."""
        gh = _ProbeGh(_FakeProc(returncode=0, stdout='{"name": "feat/a/b"}'))

        gh.branch_exists("o", "r", "feat/a/b")

        assert gh.calls[0] == ["api", "repos/o/r/branches/feat/a/b"]

    def test_a_missing_branch_is_false_not_an_error(self):
        gh = _ProbeGh(
            _FakeProc(returncode=1, stdout="", stderr="gh: Branch not found (HTTP 404)")
        )

        assert gh.branch_exists("o", "r", "ghost") is False

    def test_an_auth_failure_still_raises_rather_than_answering_no(self):
        """"I could not ask" is not "it is not there" — collapsing the two would
        let an expired token silently refuse every `working-branch` write as if
        the branch had never been pushed."""
        gh = _ProbeGh(_FakeProc(returncode=4, stdout="", stderr="gh: auth required"))

        with pytest.raises(tp.TransportError) as excinfo:
            gh.branch_exists("o", "r", "main")

        assert excinfo.value.code == "auth"

    def test_an_unreachable_provider_still_raises(self):
        gh = _ProbeGh(
            _FakeProc(returncode=1, stdout="", stderr="dial tcp: could not resolve host")
        )

        with pytest.raises(tp.TransportError) as excinfo:
            gh.branch_exists("o", "r", "main")

        assert excinfo.value.code == "unavailable"
