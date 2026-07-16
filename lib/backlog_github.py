"""Sync stdlib-HTTP GitHub Issues client — the only module that speaks HTTP.

This is the D7 transport seam: it knows nothing of prawduct semantics (labels in,
labels out, JSON in, JSON out). Callers hand it a method + path + params + body
and get back a normalized result dict; it never raises on an operational failure
(network or HTTP-error), matching the project's return-value error convention.
The prawduct<->GitHub encoding and the stable ``error.kind`` vocabulary live one
layer up in ``backlog_service`` — nothing here interprets a status as an
"auth"/"rate_limited"/"validation" kind, so GitHub never colonizes the interface.

Transport is injected (``GitHubClient(transport=...)``) so tests fake it with the
captured shapes in ``api-notes-github-issues.md`` — the fakes are built *after*
live capture, never from recalled shapes. The real transport (``urllib_transport``)
is the single place stdlib ``urllib`` is touched; both real and fake transports
return the same ``TransportResult`` dict shape, so no exception ever crosses the
seam.

Token resolution (``resolve_token``) implements the security model's order:
``GH_TOKEN`` -> ``GITHUB_TOKEN`` -> ``gh auth token`` (list-form subprocess, never
``shell=True``) -> None. The token rides only in the ``Authorization`` header — it
is never placed in argv, a URL, a log line, or any returned dict.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

API_ROOT = "https://api.github.com"
API_VERSION = "2022-11-28"
USER_AGENT = "prawduct-backlog"

# Default socket timeout (seconds). stdlib ``urllib`` exposes a single timeout for
# connect+read rather than the api-contract's connect/total split; a genuinely cut
# network fails via a DNS/connect error well under this, satisfying the never-block
# floor, and a connected-but-hung server is bounded by it. The connect/total split
# is a P1 refinement that arrives with a custom transport.
DEFAULT_TIMEOUT = 10.0

# A transport maps a request to a TransportResult dict. HTTP that produced *any*
# response (2xx..5xx) -> {"status": int, "headers": {lowercased}, "body": bytes}.
# A network failure (no response) -> {"status": None, "network_reason": str,
# "message": str}. No exception crosses this boundary.
TransportResult = dict[str, Any]
Transport = Callable[[str, str, dict[str, str], "bytes | None", float], TransportResult]


def resolve_token(env: "dict[str, str] | None" = None) -> "str | None":
    """Resolve a GitHub token per the security model; None if none is available.

    Order (first hit wins), performed per invocation, nothing persisted:
      1. ``GH_TOKEN``; if unset, ``GITHUB_TOKEN`` (the CI-conventional alias).
      2. ``gh auth token`` — list-form argv, 2 s timeout, never ``shell=True``;
         a missing ``gh`` binary or any failure falls through to None.
    The caller turns None into the ``auth`` error that names the fix (never a
    prompt — AG1).
    """
    environ = os.environ if env is None else env
    for var in ("GH_TOKEN", "GITHUB_TOKEN"):
        token = (environ.get(var) or "").strip()
        if token:
            return token
    try:
        completed = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    token = (completed.stdout or "").strip()
    return token or None


def _classify_urlerror(err: BaseException) -> str:
    """Map a urllib/socket transport exception to a coarse network reason."""
    reason = getattr(err, "reason", err)
    if isinstance(reason, socket.timeout) or isinstance(err, socket.timeout):
        return "timeout"
    if isinstance(reason, socket.gaierror):
        return "dns"
    if isinstance(reason, (ConnectionError, TimeoutError)):
        return "connect"
    return "connect"


def urllib_transport(
    method: str,
    url: str,
    headers: "dict[str, str]",
    body: "bytes | None",
    timeout: float,
) -> TransportResult:
    """The real transport: the single place stdlib ``urllib`` is exercised.

    Returns a TransportResult dict for both HTTP responses (including 4xx/5xx via
    ``HTTPError``, which *is* a response) and network failures. Never raises for
    an operational failure; a genuine bug would surface as an unexpected exception
    at the ``bin/`` boundary.
    """
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return {
                "status": response.status,
                "headers": {k.lower(): v for k, v in response.headers.items()},
                "body": response.read(),
            }
    except urllib.error.HTTPError as err:  # a 4xx/5xx response, not a failure to reach
        return {
            "status": err.code,
            "headers": {k.lower(): v for k, v in (err.headers or {}).items()},
            "body": err.read(),
        }
    except urllib.error.URLError as err:
        return {"status": None, "network_reason": _classify_urlerror(err), "message": str(err.reason)}
    except socket.timeout:
        return {"status": None, "network_reason": "timeout", "message": "timed out"}
    except OSError as err:
        return {"status": None, "network_reason": "connect", "message": str(err)}


class GitHubClient:
    """Thin sync client over the GitHub REST Issues API.

    Holds the token + injected transport; builds requests (auth header, Accept,
    API version, User-Agent, JSON body) and normalizes every response into a
    result dict:

      * success (2xx): ``{"ok": True, "status", "json", "headers"}``
      * HTTP error:    ``{"ok": False, "status": int, "json", "headers", "message"}``
      * network:       ``{"ok": False, "status": None, "network_reason", "message"}``

    The ``json`` value is the parsed body (or None for an empty/non-JSON body).
    ``backlog_service.classify_error`` maps these into the stable ``error.kind``
    vocabulary — this client stays kind-agnostic.
    """

    def __init__(
        self,
        token: str,
        transport: "Transport | None" = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._token = token
        self._transport = transport or urllib_transport
        self._timeout = timeout

    def _headers(self, has_body: bool) -> "dict[str, str]":
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": USER_AGENT,
        }
        if has_body:
            headers["Content-Type"] = "application/json"
        return headers

    def request(
        self,
        method: str,
        path: str,
        params: "dict[str, Any] | None" = None,
        json_body: "Any | None" = None,
    ) -> "dict[str, Any]":
        """Issue a request against a ``/…`` API path (query from ``params``)."""
        url = API_ROOT + path
        if params:
            query = urllib.parse.urlencode(
                {k: v for k, v in params.items() if v is not None}
            )
            if query:
                url = f"{url}?{query}"
        return self.request_url(method, url, json_body=json_body)

    def request_url(
        self, method: str, url: str, json_body: "Any | None" = None
    ) -> "dict[str, Any]":
        """Issue a request against an absolute URL (used to follow ``Link`` cursors)."""
        body = None
        if json_body is not None:
            body = json.dumps(json_body).encode("utf-8")
        result = self._transport(
            method, url, self._headers(body is not None), body, self._timeout
        )
        return self._normalize(result)

    @staticmethod
    def _normalize(result: TransportResult) -> "dict[str, Any]":
        if result.get("status") is None:
            return {
                "ok": False,
                "status": None,
                "network_reason": result.get("network_reason", "connect"),
                "message": result.get("message", ""),
            }
        status = int(result["status"])
        headers = result.get("headers", {})
        raw = result.get("body", b"") or b""
        parsed: Any = None
        if raw:
            try:
                parsed = json.loads(raw)
            except (ValueError, TypeError):
                parsed = None
        if 200 <= status < 300:
            return {"ok": True, "status": status, "json": parsed, "headers": headers}
        message = ""
        if isinstance(parsed, dict):
            message = str(parsed.get("message", "") or "")
        return {
            "ok": False,
            "status": status,
            "json": parsed,
            "headers": headers,
            "message": message,
        }

    # --- Issue operations (P0 walking skeleton: create / get / list) ---------

    def create_issue(self, owner: str, repo: str, payload: "dict[str, Any]") -> "dict[str, Any]":
        return self.request("POST", f"/repos/{owner}/{repo}/issues", json_body=payload)

    def get_issue(self, owner: str, repo: str, number: int) -> "dict[str, Any]":
        return self.request("GET", f"/repos/{owner}/{repo}/issues/{number}")

    def list_issues(
        self, owner: str, repo: str, params: "dict[str, Any] | None" = None
    ) -> "dict[str, Any]":
        return self.request("GET", f"/repos/{owner}/{repo}/issues", params=params)


def parse_next_link(link_header: "str | None") -> "str | None":
    """Return the ``rel="next"`` URL from a GitHub ``Link`` header, or None.

    GitHub's pagination is cursor-form (``…&after=…``); the URL is followed
    verbatim, never reconstructed from page math (captured).
    """
    if not link_header:
        return None
    for part in link_header.split(","):
        segments = part.split(";")
        if len(segments) < 2:
            continue
        url = segments[0].strip().strip("<>")
        for meta in segments[1:]:
            meta = meta.strip()
            if meta in ('rel="next"', "rel=next"):
                return url
    return None
