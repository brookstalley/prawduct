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


#: Page size for every paged list read. GitHub's REST maximum.
PAGE_SIZE = 100

#: The one page-loop backstop, shared by every paged read (1000 × 100 = 100k
#: entries). Purely a runaway guard: it exists so a pathological endpoint or a
#: server that never returns a short page cannot spin forever, NOT to bound
#: results — hitting it raises, so the bound can no longer silently shorten an
#: answer. It is set at the most permissive of the four values it replaced
#: (``export``'s), because lowering a cap that trips loudly would turn repos
#: that work today into hard failures, while raising one costs nothing: a real
#: repo terminates on a short page thousands of pages earlier.
MAX_PAGES = 1000


def paginate(fetch_page, *, per_page: int = PAGE_SIZE, max_pages: int = MAX_PAGES, what: str = "results"):
    """Yield every item of a paged GitHub list endpoint, page by page.

    ``fetch_page(page, per_page)`` returns one **raw** page. The one paginator
    the whole backlog service shares — it replaced four near-identical loops
    that had drifted to three different caps and three different cap-trip
    behaviours, none of which failed loud.

    **A cap trip raises rather than returning a prefix.** A truncated result
    that is indistinguishable from a complete one is the failure worth naming:
    ``export`` is the backup path, so a silently short backup is a backup that
    lies, and a caller cannot detect it because the short list is a perfectly
    well-formed short list. Every caller already converts ``TransportError``
    into an attributed envelope at its boundary, so the loud path costs no new
    error plumbing — it reuses the one that was already there.

    **Termination is on a short RAW page.** Callers filter (pull requests
    interleave the REST issues list; non-prawduct issues are out of scope), and
    a filtered view can be short while the real page was full — terminating on
    it would silently drop every later page. So this yields raw items and the
    caller filters downstream, never the reverse.
    """
    page = 1
    while page <= max_pages:
        batch = fetch_page(page, per_page)
        if not isinstance(batch, list):
            batch = []
        yield from batch
        if len(batch) < per_page:
            return
        page += 1
    raise TransportError(
        "unavailable",
        f"{what} truncated at the {max_pages}-page read limit — "
        f"the result is incomplete and has not been returned",
        retryable=False,
        details={"max_pages": max_pages, "per_page": per_page},
    )


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
    both implement this; core depends only on this surface.

    **Method names are load-bearing.** The pacing decorator classifies every
    call as a read or a write from its name prefix alone — ``get_``/``list_``
    read, ``create_``/``update_``/``add_``/``remove_`` write — and *raises* on a
    name it cannot classify rather than let the call escape the rate budget. So
    a new method must carry one of those prefixes, or the decorator has to learn
    it in the same change. A name like ``fetch_labels`` imports cleanly, passes
    its own unit tests, and then fails at the first paced run.
    """

    def get_authenticated_user(self) -> dict:
        raise NotImplementedError

    def create_issue(
        self, owner: str, repo: str, *, title: str, body: str, labels: list[str]
    ) -> dict:
        raise NotImplementedError

    def get_issue(self, owner: str, repo: str, number: int) -> dict:
        raise NotImplementedError

    def list_issues(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "open",
        labels: list[str] | None = None,
        assignee: str | None = None,
        sort: str = "created",
        direction: str = "asc",
        per_page: int = 100,
        page: int = 1,
    ) -> list[dict]:
        raise NotImplementedError

    def list_blocked_by(self, owner: str, repo: str, number: int) -> list[dict]:
        raise NotImplementedError

    def add_blocked_by(
        self,
        owner: str,
        repo: str,
        number: int,
        *,
        blocker_owner: str,
        blocker_repo: str,
        blocker_number: int,
    ) -> None:
        raise NotImplementedError

    def remove_blocked_by(
        self,
        owner: str,
        repo: str,
        number: int,
        *,
        blocker_owner: str,
        blocker_repo: str,
        blocker_number: int,
    ) -> None:
        raise NotImplementedError

    def add_sub_issue(
        self,
        owner: str,
        repo: str,
        number: int,
        *,
        child_owner: str,
        child_repo: str,
        child_number: int,
    ) -> None:
        raise NotImplementedError

    def remove_sub_issue(
        self,
        owner: str,
        repo: str,
        number: int,
        *,
        child_owner: str,
        child_repo: str,
        child_number: int,
    ) -> None:
        raise NotImplementedError

    def list_sub_issues(self, owner: str, repo: str, number: int) -> list[dict]:
        """The child issues under ``number`` (native sub-issues) — what ``export``
        serializes for the sub-issue tree. Returns ``[{owner, repo, number, ref}]``."""
        raise NotImplementedError

    def list_timeline(self, owner: str, repo: str, number: int) -> list[dict]:
        """The native timeline/events for ``number`` (audit history, CC4) — what
        ``export`` serializes and GV3/`closed_by` reads. Returns a list of
        ``{event, actor, created_at, ...}`` dicts (the shape ``verify-api`` pins)."""
        raise NotImplementedError

    def list_labels(self, owner: str, repo: str) -> list[dict]:
        raise NotImplementedError

    def create_label(
        self, owner: str, repo: str, *, name: str, color: str, description: str
    ) -> dict:
        raise NotImplementedError

    def update_issue(
        self, owner: str, repo: str, number: int, *, fields: dict
    ) -> dict:
        raise NotImplementedError

    def add_labels(
        self, owner: str, repo: str, number: int, labels: list[str]
    ) -> list[dict]:
        raise NotImplementedError

    def remove_label(self, owner: str, repo: str, number: int, name: str) -> None:
        raise NotImplementedError

    def create_comment(
        self, owner: str, repo: str, number: int, *, body: str
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

    def list_issues(
        self,
        owner: str,
        repo: str,
        *,
        state: str = "open",
        labels: list[str] | None = None,
        assignee: str | None = None,
        sort: str = "created",
        direction: str = "asc",
        per_page: int = 100,
        page: int = 1,
    ) -> list[dict]:
        """List issues off the REST list endpoint — the ready-work query's engine
        (Q1-structured, strongly consistent in practice). ``labels`` is an AND
        filter; ``assignee`` accepts a login, ``"none"`` (unassigned), or ``"*"``
        (any). The REST issues list also returns pull requests — they are
        returned RAW (a ``pull_request`` key marks them) so pagination
        terminators can read the true page length (BKL-5T3J: dropping them here
        made every ``len(batch) < per_page`` check see a filtered count and stop
        scans early in PR-bearing repos). Filtering is the decode layer's job —
        ``encode.is_prawduct_issue`` rejects PRs (PROV-2), and label-keyed
        lookups guard ``pull_request`` explicitly."""
        from urllib.parse import urlencode  # noqa: PLC0415 — only list builds a query string

        params: list[tuple[str, str]] = [("state", state)]
        if labels:
            params.append(("labels", ",".join(labels)))
        if assignee:
            params.append(("assignee", assignee))
        params += [
            ("sort", sort),
            ("direction", direction),
            ("per_page", str(per_page)),
            ("page", str(page)),
        ]
        path = f"repos/{owner}/{repo}/issues?{urlencode(params)}"
        result = self._api(["api", path])
        if not isinstance(result, list):
            return []
        return [issue for issue in result if isinstance(issue, dict)]

    # -- relationships (native dependencies + sub-issues) ------------------
    #
    # Endpoint shapes for issue dependencies (GA 2025-08-21) and sub-issues are
    # confirmed live by the pre-migration verify-api spike (which records the
    # real dependency/sub-issue shapes); the L1 suite exercises them through
    # the fake. The seam is ref-based (owner/repo/number) so it is cross-repo
    # capable — a blocker in another repo is judged from a live read (Data Model
    # §4). Should the real payload key differ, only these bodies change.

    def list_blocked_by(self, owner: str, repo: str, number: int) -> list[dict]:
        """The issues that block ``number`` — each with its live ``state`` so the
        ``pick`` fan-out can judge "all blockers closed" in one fetch per
        candidate. Returns ``[{owner, repo, number, state, ref}]``."""
        result = self._api(
            ["api", f"repos/{owner}/{repo}/issues/{number}/dependencies/blocked_by"]
        )
        out: list[dict] = []
        for dep in result if isinstance(result, list) else []:
            repo_info = dep.get("repository") or {}
            dep_owner = (repo_info.get("owner") or {}).get("login") or owner
            dep_repo = repo_info.get("name") or repo
            dep_number = dep.get("number")
            out.append(
                {
                    "owner": dep_owner,
                    "repo": dep_repo,
                    "number": dep_number,
                    "state": (dep.get("state") or "open").lower(),
                    "ref": f"{dep_owner}/{dep_repo}#{dep_number}",
                }
            )
        return out

    def add_blocked_by(
        self,
        owner: str,
        repo: str,
        number: int,
        *,
        blocker_owner: str,
        blocker_repo: str,
        blocker_number: int,
    ) -> None:
        blocker = self.get_issue(blocker_owner, blocker_repo, blocker_number)
        self._api(
            [
                "api",
                f"repos/{owner}/{repo}/issues/{number}/dependencies/blocked_by",
                "--method",
                "POST",
                "--input",
                "-",
            ],
            input_json=json.dumps({"issue_id": blocker.get("id") or blocker.get("node_id")}),
        )

    def remove_blocked_by(
        self,
        owner: str,
        repo: str,
        number: int,
        *,
        blocker_owner: str,
        blocker_repo: str,
        blocker_number: int,
    ) -> None:
        blocker = self.get_issue(blocker_owner, blocker_repo, blocker_number)
        blocker_id = blocker.get("id") or blocker.get("node_id")
        try:
            self._api(
                [
                    "api",
                    f"repos/{owner}/{repo}/issues/{number}/dependencies/blocked_by/{blocker_id}",
                    "--method",
                    "DELETE",
                ]
            )
        except TransportError as exc:
            if exc.code == "not_found":  # already unlinked — idempotent
                return
            raise

    def add_sub_issue(
        self,
        owner: str,
        repo: str,
        number: int,
        *,
        child_owner: str,
        child_repo: str,
        child_number: int,
    ) -> None:
        child = self.get_issue(child_owner, child_repo, child_number)
        self._api(
            [
                "api",
                f"repos/{owner}/{repo}/issues/{number}/sub_issues",
                "--method",
                "POST",
                "--input",
                "-",
            ],
            input_json=json.dumps({"sub_issue_id": child.get("id") or child.get("node_id")}),
        )

    def remove_sub_issue(
        self,
        owner: str,
        repo: str,
        number: int,
        *,
        child_owner: str,
        child_repo: str,
        child_number: int,
    ) -> None:
        child = self.get_issue(child_owner, child_repo, child_number)
        child_id = child.get("id") or child.get("node_id")
        try:
            self._api(
                [
                    "api",
                    f"repos/{owner}/{repo}/issues/{number}/sub_issue",
                    "--method",
                    "DELETE",
                    "--input",
                    "-",
                ],
                input_json=json.dumps({"sub_issue_id": child_id}),
            )
        except TransportError as exc:
            if exc.code == "not_found":  # already unlinked — idempotent
                return
            raise

    def list_sub_issues(self, owner: str, repo: str, number: int) -> list[dict]:
        """The child issues under ``number`` (native sub-issues) — for ``export``'s
        graph dump. Ref-based so it is cross-repo capable. Shape recorded by the
        pre-migration ``verify-api`` spike; the L1 suite exercises it through the fake."""
        result = self._api_paged(f"repos/{owner}/{repo}/issues/{number}/sub_issues")
        out: list[dict] = []
        for child in result:
            repo_info = child.get("repository") or {}
            c_owner = (repo_info.get("owner") or {}).get("login") or owner
            c_repo = repo_info.get("name") or repo
            c_number = child.get("number")
            out.append(
                {"owner": c_owner, "repo": c_repo, "number": c_number,
                 "ref": f"{c_owner}/{c_repo}#{c_number}"}
            )
        return out

    def list_timeline(self, owner: str, repo: str, number: int) -> list[dict]:
        """The native timeline for ``number`` (audit history, CC4) — for ``export``'s
        graph dump and (later) GV3/`closed_by`. Returns the raw event dicts, each
        reduced to the non-secret fields the dump keeps. Shape recorded by the
        pre-migration ``verify-api`` spike; behavior (event *ordering*) is an L5-owed
        re-check CONTRACT-1 cannot see (Test Specs §6)."""
        result = self._api_paged(f"repos/{owner}/{repo}/issues/{number}/timeline")
        out: list[dict] = []
        for event in result:
            if not isinstance(event, dict):
                continue
            out.append(
                {
                    "event": event.get("event"),
                    "actor": (event.get("actor") or {}).get("login"),
                    "created_at": event.get("created_at"),
                }
            )
        return out

    def list_labels(self, owner: str, repo: str) -> list[dict]:
        return self._api_paged(f"repos/{owner}/{repo}/labels")

    def create_label(
        self, owner: str, repo: str, *, name: str, color: str, description: str
    ) -> dict:
        payload = {"name": name, "color": color, "description": description}
        return self._api(
            ["api", f"repos/{owner}/{repo}/labels", "--method", "POST", "--input", "-"],
            input_json=json.dumps(payload),
        )

    # -- mutations (the state-machine write path) --------------------------

    def update_issue(
        self, owner: str, repo: str, number: int, *, fields: dict
    ) -> dict:
        """PATCH the issue with **only the named fields** (``state``,
        ``state_reason``, ``title``, ``body``, ``assignees``). Core decides which
        fields reach here — the ``update`` op's mass-assignment guard (SEC-2)
        restricts user-driven edits to ``title``/``body``/facets; ``claim`` sets
        ``assignees`` + the ``body`` stamp in one atomic PATCH. The transport does
        not second-guess a field it was handed."""
        return self._api(
            [
                "api",
                f"repos/{owner}/{repo}/issues/{number}",
                "--method",
                "PATCH",
                "--input",
                "-",
            ],
            input_json=json.dumps(fields),
        )

    def add_labels(
        self, owner: str, repo: str, number: int, labels: list[str]
    ) -> list[dict]:
        """POST labels — **additive**, leaving already-present labels untouched, so
        ``set-status`` can add the target label *before* removing the loser and
        never open a zero-label window (Data Model §4 B1). Returns the full set."""
        result = self._api(
            [
                "api",
                f"repos/{owner}/{repo}/issues/{number}/labels",
                "--method",
                "POST",
                "--input",
                "-",
            ],
            input_json=json.dumps({"labels": labels}),
        )
        return result if isinstance(result, list) else []

    def remove_label(self, owner: str, repo: str, number: int, name: str) -> None:
        """DELETE one label. **Idempotent**: a label already absent 404s, and that
        *is* the desired end state, so a ``not_found`` is swallowed — a re-run of a
        half-applied transition converges rather than erroring."""
        from urllib.parse import quote  # noqa: PLC0415 — only the delete path needs it

        try:
            self._api(
                [
                    "api",
                    f"repos/{owner}/{repo}/issues/{number}/labels/{quote(name, safe='')}",
                    "--method",
                    "DELETE",
                ]
            )
        except TransportError as exc:
            if exc.code == "not_found":
                return
            raise

    def create_comment(
        self, owner: str, repo: str, number: int, *, body: str
    ) -> dict:
        """Add a native issue comment. Attribution is the API identity (GitHub
        stamps the authenticated user), never a caller-supplied author."""
        return self._api(
            [
                "api",
                f"repos/{owner}/{repo}/issues/{number}/comments",
                "--method",
                "POST",
                "--input",
                "-",
            ],
            input_json=json.dumps({"body": body}),
        )

    # -- subprocess plumbing ----------------------------------------------

    def _api_paged(self, path: str, *, per_page: int = PAGE_SIZE) -> list:
        """Fetch every page of a REST **list** endpoint with an explicit page loop.

        NOT ``gh --paginate``: that flag emits each page as a **separate JSON
        document**, so a single ``json.loads`` over the concatenation fails the
        moment a result exceeds one page (BKL-2V6N — fatal for ``list_labels``
        once a migrated repo carries hundreds of ``id:PFX`` aliases). Paging
        itself is :func:`paginate`, shared with the three whole-repo scans, so
        the terminator and the cap trip behave identically everywhere.
        ``per_page`` is injectable so a live spike can force multi-page
        behavior against a small real dataset."""
        sep = "&" if "?" in path else "?"

        def fetch(page: int, size: int):
            return self._api(["api", f"{path}{sep}per_page={size}&page={page}"])

        return list(paginate(fetch, per_page=per_page, what=f"{path} results"))

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
            retry_after = _extract_retry_after(scrubbed)
            if retry_after is not None:
                # A non-secret integer; surfaced so the importer honors the server's
                # pause hint instead of guessing a backoff (BKL-3K9N).
                details["retry_after"] = retry_after
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
# A server ``Retry-After`` (seconds) when gh surfaces the header in stderr. gh does
# NOT reliably print it, so the common case is a miss (→ the importer's exponential
# backoff); when it IS present, honoring it beats guessing (BKL-3K9N).
_RETRY_AFTER_RE = re.compile(r"retry[- ]after[:\s]+(\d+)")
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


def _extract_retry_after(stderr_lower: str) -> int | None:
    """Best-effort parse of a ``Retry-After`` seconds value from gh's stderr, or
    ``None`` when gh did not surface one (the common case — the caller then falls
    back to bounded exponential backoff)."""
    match = _RETRY_AFTER_RE.search(stderr_lower)
    return int(match.group(1)) if match else None


def _looks_like_network(stderr_lower: str) -> bool:
    return any(signal in stderr_lower for signal in _NETWORK_SIGNALS)


# --- Detached process spawn (the D6 briefing-refresh warm) -------------------


def spawn_detached(argv: list[str], *, cwd, env: dict | None = None, popen=None) -> bool:
    """Fire a **detached**, fire-and-forget subprocess and return immediately.

    The one place under ``lib/backlog/`` that may spawn a process besides the
    ``gh`` calls (egress discipline — all subprocess use funnels through this
    module, held to the same **list-form, no ``shell=True``** safety). Used for the
    D6 briefing-refresh warm: the child runs in its **own session**
    (``start_new_session`` — not killed when the parent session ends) with stdio to
    ``/dev/null``, so the parent never blocks and no asyncio is involved. Returns
    ``True`` if the spawn was issued, ``False`` on an OS error (never raises — a
    failed warm is non-fatal). ``popen`` is injectable for tests."""
    import subprocess as _sp  # noqa: PLC0415 — module already owns subprocess; local alias for the seam

    launcher = popen or _sp.Popen
    try:
        launcher(  # noqa: S603 — list-form argv, no shell (project preference)
            argv,
            cwd=str(cwd),
            env=env,
            stdin=_sp.DEVNULL,
            stdout=_sp.DEVNULL,
            stderr=_sp.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return False
    return True
