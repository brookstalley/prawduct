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
