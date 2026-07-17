"""Transport — the sole egress to GitHub, and the primary test seam.

Every network call the adapter makes goes through this module (Test Specs §2.1).
No other module under ``lib/backlog/`` shells out or opens a socket. That makes
this boundary the one place L1 tests swap in the in-process fake (tests/fakes/
fake_github.py) for full determinism, and the one place credentials and raw
subprocess output are handled — so the "no token in any output" guarantee (SEC-1,
Security §4) has a single choke point.

The required transport is ``gh`` (O5, G4): free, portable, and it holds the
credential itself (``~/.config/gh``) so the adapter never manages a token. The
raw-HTTPS fast path is a possible later optimization, not yet implemented.

Design:
- ``GhTransport`` drives ``gh`` as a subprocess — **list-form args, never
  ``shell=True``** (project preference), and **non-interactive always**
  (``GH_PROMPT_DISABLED``, no pager, no update notifier, stdin closed on reads,
  no inherited TTY — INV-2, Security §1a) so there is nothing to hang on.
- Expected ``gh`` failures raise ``TransportError`` carrying a **stable error
  code** built from *known fields* (the operation, the parsed HTTP status) —
  **never** by echoing raw ``gh`` output, which is how a token leaks. The
  ``scrub_secrets`` denylist is the backstop for any string that does flow.
- The authenticated identity is resolved **once per process** and memoized
  (SEC-3/N3): one ``gh api user`` for a whole sweep, not one per mutation.
"""

from __future__ import annotations

import json
import os
import re
import subprocess

# --- Secret scrub (the SEC-1 backstop) ---------------------------------------

_REDACTED = "[REDACTED]"

# Denylist of credential shapes that must never reach any output sink (F2/N4).
# The *primary* control is building errors from known fields (never echoing raw
# output); this is the defense-in-depth backstop for anything that slips through.
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"gh[oprsu]_[A-Za-z0-9]{16,}"),            # gh token classes
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),          # fine-grained PAT
    re.compile(
        r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"
    ),                                                     # JWT (App installation)
    re.compile(r"-----BEGIN[A-Z ]*PRIVATE KEY-----.*?-----END[A-Z ]*PRIVATE KEY-----", re.DOTALL),
    re.compile(r"(?<=://)[^/\s:@]+:[^/\s@]+(?=@)"),        # url-embedded user:pass
    re.compile(r"proxy-injected"),                         # the cloud token literal (N5)
)


def scrub_secrets(text: str | None) -> str:
    """Redact any credential-shaped substring. Idempotent; safe on ``None``."""
    if not text:
        return ""
    out = text
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub(_REDACTED, out)
    return out


# --- Transport error ---------------------------------------------------------

# The stable error-code → transient-vs-permanent hint (API §4). This is the
# single source of truth for the default `retryable` value of every code;
# `core` imports it rather than keeping a second copy (transport is the lowest
# layer, so it cannot import core — the map lives here). A TransportError may
# still override the default per-instance (e.g. a *missing* gh binary is
# "unavailable" but not retryable).
RETRYABLE_DEFAULTS: dict[str, bool] = {
    "validation": False,
    "not_found": False,
    "ambiguous_id": False,
    "alias_collision": False,
    "conflict": True,
    "claim_conflict": True,
    "auth": False,
    "unavailable": True,
    "rate_limited": True,
    "unsupported": False,
}


class TransportError(Exception):
    """An expected transport failure, mapped to a stable code (never raw output).

    ``message`` and ``details`` are already scrubbed and built from known fields;
    raw ``gh`` stderr is never carried here.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool | None = None,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = (
            retryable if retryable is not None else RETRYABLE_DEFAULTS.get(code, False)
        )
        self.details = details or {}


# --- Non-interactive environment (INV-2, Security §1a) -----------------------


def build_env(base: dict | None = None) -> dict:
    """Return the environment for a ``gh`` call — non-interactive, no pager.

    Mechanized, not asserted (N1): nothing to hang on. Kept a pure function so
    the non-interactive contract is unit-testable without spawning ``gh``.
    """
    env = dict(base if base is not None else os.environ)
    env["GH_PROMPT_DISABLED"] = "1"      # never prompt
    env["GH_NO_UPDATE_NOTIFIER"] = "1"   # no background update chatter
    env["GH_PAGER"] = ""                 # no pager (would hang on no TTY)
    env["PAGER"] = ""
    env["CLICOLOR"] = "0"
    return env


# --- The transport interface (the seam contract) -----------------------------


class Transport:
    """The GitHub operations the adapter uses. ``GhTransport`` and the L1 fake
    both implement this; core depends only on this surface."""

    def get_authenticated_user(self) -> dict:
        raise NotImplementedError

    def create_issue(
        self, owner: str, repo: str, *, title: str, body: str, labels: list[str]
    ) -> dict:
        raise NotImplementedError

    def get_issue(self, owner: str, repo: str, number: int) -> dict:
        raise NotImplementedError

    def list_labels(self, owner: str, repo: str) -> list[dict]:
        raise NotImplementedError

    def create_label(
        self, owner: str, repo: str, *, name: str, color: str, description: str
    ) -> dict:
        raise NotImplementedError


class GhTransport(Transport):
    """The real transport: drives ``gh`` as a subprocess."""

    def __init__(self, *, timeout: float = 30.0) -> None:
        self._timeout = timeout
        self._user: dict | None = None  # memoized identity (SEC-3/N3)

    # -- identity ----------------------------------------------------------

    def get_authenticated_user(self) -> dict:
        if self._user is None:
            self._user = self._api(["api", "user"])
        return self._user

    # -- issues ------------------------------------------------------------

    def create_issue(
        self, owner: str, repo: str, *, title: str, body: str, labels: list[str]
    ) -> dict:
        payload = {"title": title, "body": body, "labels": labels}
        return self._api(
            ["api", f"repos/{owner}/{repo}/issues", "--method", "POST", "--input", "-"],
            input_json=json.dumps(payload),
        )

    def get_issue(self, owner: str, repo: str, number: int) -> dict:
        return self._api(["api", f"repos/{owner}/{repo}/issues/{number}"])

    def list_labels(self, owner: str, repo: str) -> list[dict]:
        result = self._api(
            ["api", f"repos/{owner}/{repo}/labels", "--paginate"]
        )
        return result if isinstance(result, list) else []

    def create_label(
        self, owner: str, repo: str, *, name: str, color: str, description: str
    ) -> dict:
        payload = {"name": name, "color": color, "description": description}
        return self._api(
            ["api", f"repos/{owner}/{repo}/labels", "--method", "POST", "--input", "-"],
            input_json=json.dumps(payload),
        )

    # -- subprocess plumbing ----------------------------------------------

    def _api(self, args: list[str], *, input_json: str | None = None):
        """Run ``gh <args>`` and parse JSON stdout, or raise ``TransportError``."""
        stdout = self._run(args, input_json=input_json)
        try:
            return json.loads(stdout) if stdout.strip() else {}
        except json.JSONDecodeError:
            # A JSON call returned non-JSON — build a known-field error, never
            # echo the raw body (SEC-1).
            raise TransportError(
                "unavailable",
                "GitHub returned an unparseable response",
                details={"operation": " ".join(args[:2])},
            )

    def _run(self, args: list[str], *, input_json: str | None = None) -> str:
        cmd = ["gh", *args]
        env = build_env()
        try:
            proc = subprocess.run(  # noqa: S603 — list-form, no shell (project preference)
                cmd,
                input=input_json,
                stdin=None if input_json is not None else subprocess.DEVNULL,
                capture_output=True,
                text=True,
                env=env,
                timeout=self._timeout,
            )
        except FileNotFoundError:
            raise TransportError(
                "unavailable",
                "the 'gh' CLI is required but was not found on PATH",
                retryable=False,
                details={"transport": "gh"},
            )
        except subprocess.TimeoutExpired:
            raise TransportError(
                "unavailable",
                f"'gh' timed out after {self._timeout:g}s",
                details={"operation": " ".join(args[:2])},
            )
        if proc.returncode != 0:
            raise self._map_failure(args, proc.returncode, proc.stderr)
        return proc.stdout

    def _map_failure(self, args: list[str], returncode: int, stderr: str) -> TransportError:
        """Map a non-zero ``gh`` exit to a stable code — from known fields only.

        The raw ``stderr`` is scrubbed and inspected for a signal (HTTP status,
        rate-limit, auth, network), but it is **never** placed in the message or
        details — the error is built from the mapped code + the operation.
        """
        scrubbed = scrub_secrets(stderr).lower()
        operation = " ".join(args[:2])
        # `returncode` is a non-secret integer — safe to surface for field
        # debugging of an otherwise-opaque `gh` failure.
        details: dict = {"operation": operation, "returncode": returncode}

        # gh's own exit 4 = auth-required (C10).
        if returncode == 4:
            return TransportError("auth", "GitHub authentication is required or invalid", details=details)

        http = _extract_http_status(scrubbed)
        if http is not None:
            details["http_status"] = http

        if "rate limit" in scrubbed or http == 429 or (http == 403 and "rate" in scrubbed):
            return TransportError(
                "rate_limited",
                "GitHub rate limit reached",
                details=details,
            )
        if http in (401, 403) or "authentication" in scrubbed or "must authenticate" in scrubbed:
            return TransportError("auth", "GitHub authentication is required or invalid", details=details)
        if http == 404:
            return TransportError("not_found", "the requested GitHub resource was not found", details=details)
        if http == 422:
            return TransportError("validation", "GitHub rejected the request as invalid", details=details)
        if _looks_like_network(scrubbed):
            return TransportError("unavailable", "GitHub is unreachable", details=details)
        # Unknown non-zero exit — degrade to the never-block floor.
        return TransportError(
            "unavailable",
            "the GitHub request failed",
            details=details,
        )


_HTTP_RE = re.compile(r"http[/ ](?:\d\.\d )?(\d{3})")
_NETWORK_SIGNALS = (
    "could not resolve host",
    "connection refused",
    "network is unreachable",
    "no such host",
    "dial tcp",
    "i/o timeout",
    "timeout",
    "connection reset",
    "eof",
)


def _extract_http_status(stderr_lower: str) -> int | None:
    match = _HTTP_RE.search(stderr_lower)
    return int(match.group(1)) if match else None


def _looks_like_network(stderr_lower: str) -> bool:
    return any(signal in stderr_lower for signal in _NETWORK_SIGNALS)
