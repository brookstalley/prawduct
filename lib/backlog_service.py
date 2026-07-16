"""Core backlog-service ops — the prawduct<->GitHub encoding seam (D7).

Owns everything semantic that the HTTP client (``backlog_github``) deliberately
does not: the ID grammar, the label taxonomy + two-axis state encoding, the
``prawduct:`` body block round-trip, the decode of a raw issue into the curated
item projection, and the mapping of a client result into the stable ``error.kind``
vocabulary. It never speaks HTTP and never formats output — the command layer
(``backlog_service_cmd``) renders; this module returns data.

Scope note: this is the walking-skeleton slice — create / get / list, with the
create/open decode path implemented in full and closed items decoded totally
(a human can close in the GitHub UI, so decode must never crash on one). The
exhaustive status/stage round-trip matrix and the mutation ops (update / close /
comment / claim / verify) land in the mutation-surface slice; the encoding here
is the substrate they build on.
"""

from __future__ import annotations

import re
from typing import Any

# --- ID grammar (data model §4) ---------------------------------------------

# Maturity order for pb:stage — least-mature first; a conflicted item decodes to
# the minimum so it can't spuriously qualify for ready-work.
STAGE_ORDER = ["idea", "research", "requirements", "design", "ready"]

# Soft enum of stage values (advisory validation — DM1). Unknown values are
# flagged, still written, never rejected, never promoted to "known".
KNOWN_STAGES = set(STAGE_ORDER)

# pb: facets that map to labels (vs. stage/status which have dedicated encoding,
# and id which is the migrated-alias label).
FACET_LABELS = ("area", "effort", "impact", "source", "kind", "owner")

_ID_OWNER_REPO_NUM = re.compile(r"^([^/#\s]+)/([^/#\s]+)#(\d+)$")  # owner/repo#N
_ID_REPO_NUM = re.compile(r"^([^/#\s]+)#(\d+)$")  # repo#N
_ID_REPO_SLASH_NUM = re.compile(r"^([^/#\s]+)/(\d+)$")  # repo/N
_ID_BARE_NUM = re.compile(r"^#?\d+$")  # N or #N (rejected)


def normalize_id(raw: str, config_owner: str, config_repo: str) -> "dict[str, Any]":
    """Normalize any accepted ID grammar form to canonical ``owner/repo#N``.

    Returns ``{"ok": True, "canonical", "owner", "repo", "number"}`` for the four
    number-bearing forms, ``{"ok": True, "form": "alias", "alias"}`` for a legacy
    ``PFX-XXXX`` token (resolution to a number needs a live label lookup, done by
    the resolver, not here), or ``{"ok": False, "reason": "ambiguous_id",
    "message"}``. Bare ``N``/``#N`` is rejected — too easy to collide with effort
    counts or PR numbers in prose.
    """
    token = (raw or "").strip()
    if not token:
        return {"ok": False, "reason": "ambiguous_id", "message": "empty id"}

    match = _ID_OWNER_REPO_NUM.match(token)
    if match:
        owner, repo, number = match.group(1), match.group(2), int(match.group(3))
        return _canonical(owner, repo, number)

    if _ID_BARE_NUM.match(token):
        return {
            "ok": False,
            "reason": "ambiguous_id",
            "message": f"bare number '{token}' is ambiguous; use owner/repo#N or repo#N",
        }

    match = _ID_REPO_NUM.match(token)
    if match:
        repo, number = match.group(1), int(match.group(2))
        if repo != config_repo:
            return {
                "ok": False,
                "reason": "ambiguous_id",
                "message": f"cross-repo ref '{token}' must carry its owner (owner/{repo}#{number})",
            }
        return _canonical(config_owner, repo, number)

    match = _ID_REPO_SLASH_NUM.match(token)
    if match:
        repo, number = match.group(1), int(match.group(2))
        if repo != config_repo:
            return {
                "ok": False,
                "reason": "ambiguous_id",
                "message": f"cross-repo ref '{token}' must carry its owner (owner/{repo}#{number})",
            }
        return _canonical(config_owner, repo, number)

    # repo-N: split at the LAST hyphen; right all-digits AND left == configured
    # repo name => a number-bearing ref. Otherwise it is a legacy alias.
    if "-" in token:
        left, _, right = token.rpartition("-")
        if right.isdigit() and left == config_repo:
            return _canonical(config_owner, config_repo, int(right))
        # Any other hyphenated token (REL-3M7K, foo-42 where foo != repo) is a
        # legacy alias, resolved via one label lookup by the caller.
        return {"ok": True, "form": "alias", "alias": token}

    # No hyphen, not a number form -> treat as an alias token (e.g. a bare PFX).
    return {"ok": True, "form": "alias", "alias": token}


def _canonical(owner: str, repo: str, number: int) -> "dict[str, Any]":
    return {
        "ok": True,
        "form": "number",
        "owner": owner,
        "repo": repo,
        "number": number,
        "canonical": f"{owner}/{repo}#{number}",
    }


# --- Body block round-trip (data model §3) ----------------------------------

_FENCE = "```"
_BLOCK_LANG = "prawduct"


def parse_body_block(body: "str | None") -> "tuple[str, dict[str, str], list[str]]":
    """Split a body into (verbatim-body-above, block-dict, warnings).

    The block is a single fenced ```` ```prawduct ```` code block of flat
    ``key: value`` lines. If a human introduces a second, the first wins and
    ``multiple_prawduct_blocks`` is flagged. Everything before the first block is
    the item body verbatim (MG1 byte-fidelity).
    """
    text = body or ""
    lines = text.split("\n")
    blocks: list[tuple[int, int]] = []  # (open_idx, close_idx) inclusive of fences
    i = 0
    while i < len(lines):
        if lines[i].strip() == _FENCE + _BLOCK_LANG:
            for j in range(i + 1, len(lines)):
                if lines[j].strip() == _FENCE:
                    blocks.append((i, j))
                    i = j
                    break
            else:
                break  # unterminated fence -> not a block
        i += 1

    warnings: list[str] = []
    if not blocks:
        return text.rstrip("\n"), {}, warnings
    if len(blocks) > 1:
        warnings.append("multiple_prawduct_blocks")

    open_idx, close_idx = blocks[0]
    block: dict[str, str] = {}
    for line in lines[open_idx + 1 : close_idx]:
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        if key:
            block[key] = value.strip()
    body_above = "\n".join(lines[:open_idx]).rstrip("\n")
    return body_above, block, warnings


def render_body(body_above: str, block: "dict[str, str]") -> str:
    """Render body text + a trailing ``prawduct`` block (omitted if block empty)."""
    if not block:
        return body_above
    block_lines = [f"{key}: {value}" for key, value in block.items()]
    rendered = _FENCE + _BLOCK_LANG + "\n" + "\n".join(block_lines) + "\n" + _FENCE
    if body_above.strip():
        return body_above.rstrip("\n") + "\n\n" + rendered + "\n"
    return rendered + "\n"


# --- Create encoding (data model §1-§3) -------------------------------------

def encode_create(
    title: str,
    body: "str | None" = None,
    stage: "str | None" = None,
    labels: "list[str] | None" = None,
    added: "str | None" = None,
) -> "tuple[dict[str, Any], list[str]]":
    """Encode create inputs into a GitHub issue payload + advisory warnings.

    One-call create: ``title`` suffices (AG2). ``stage`` becomes a ``pb:stage:``
    label (unknown values flagged, still written — tolerant validator, DM1).
    ``added`` (the item's original date) rides in the body block because GitHub's
    ``created_at`` is only the create/migration date.
    """
    warnings: list[str] = []
    label_set: list[str] = list(labels or [])
    if stage:
        if stage not in KNOWN_STAGES:
            warnings.append(f"unknown_stage_value: {stage}")
        stage_label = f"pb:stage:{stage}"
        if stage_label not in label_set:
            label_set.append(stage_label)

    block: dict[str, str] = {}
    if added:
        block["added"] = added

    payload: dict[str, Any] = {"title": title, "body": render_body(body or "", block)}
    if label_set:
        payload["labels"] = label_set
    return payload, warnings


# --- Decode: raw issue -> curated item projection (api-contract item shape) --

def decode_issue(raw: "dict[str, Any]", owner: str, repo: str) -> "tuple[dict[str, Any], list[str]]":
    """Decode a raw GitHub issue into the curated item projection + warnings.

    Total over every GitHub state (a human can edit in the UI), per the data
    model's decode rules. Returns the item dict and any advisory warnings
    (conflicting labels, close reason gaps) — warnings never fail an operation.
    """
    warnings: list[str] = []
    number = int(raw.get("number"))
    label_names = [lbl.get("name", "") for lbl in (raw.get("labels") or [])]
    pb_labels = [name for name in label_names if name.startswith("pb:")]
    labels_other = [name for name in label_names if not name.startswith("pb:")]

    stage, stage_warn = _decode_stage(pb_labels)
    warnings.extend(stage_warn)

    state = raw.get("state", "open")
    state_reason = raw.get("state_reason")
    status, status_warn = _decode_status(state, state_reason, pb_labels)
    warnings.extend(status_warn)

    facets: dict[str, str] = {}
    alias: "str | None" = None
    for name in pb_labels:
        parts = name.split(":", 2)
        if len(parts) < 3:
            continue
        facet, value = parts[1], parts[2]
        if facet in ("stage", "status"):
            continue
        if facet == "id":
            alias = value if alias is None else alias
            continue
        if facet in FACET_LABELS:
            facets[facet] = value  # last write wins; per-project facets pass through

    body_above, block, block_warn = parse_body_block(raw.get("body"))
    warnings.extend(block_warn)
    related = [ref.strip() for ref in (block.get("related", "").split(",")) if ref.strip()]

    deps = raw.get("issue_dependencies_summary") or {}
    subs = raw.get("sub_issues_summary") or {}

    item = {
        "id": f"{owner}/{repo}#{number}",
        "number": number,
        "node": raw.get("node_id"),
        "title": raw.get("title"),
        "status": status,
        "stage": stage,
        "facets": facets,
        "labels_other": labels_other,
        "assignees": [a.get("login") for a in (raw.get("assignees") or [])],
        "alias": alias,
        "verified": block.get("verified"),
        "added": block.get("added"),
        "closed_by_handle": block.get("closed-by"),
        "related": related,
        "blocked_by_count": deps.get("blocked_by", 0),
        "sub_issues": {
            "total": subs.get("total", 0),
            "completed": subs.get("completed", 0),
        },
        "state_reason": state_reason,
        "url": raw.get("html_url"),
        "created_at": raw.get("created_at"),
        "updated_at": raw.get("updated_at"),
        "body": raw.get("body"),
    }
    return item, warnings


def _decode_stage(pb_labels: "list[str]") -> "tuple[str | None, list[str]]":
    stages = [n.split(":", 2)[2] for n in pb_labels if n.startswith("pb:stage:") and n.count(":") >= 2]
    if not stages:
        return None, []
    if len(stages) > 1:
        # Minimum by maturity is the conservative choice; unknown values sort last.
        chosen = min(stages, key=lambda s: STAGE_ORDER.index(s) if s in STAGE_ORDER else len(STAGE_ORDER))
        return chosen, ["conflicting_stage_labels"]
    return stages[0], []


def _decode_status(
    state: str, state_reason: "str | None", pb_labels: "list[str]"
) -> "tuple[str, list[str]]":
    status_values = [n.split(":", 2)[2] for n in pb_labels if n.startswith("pb:status:") and n.count(":") >= 2]
    if state == "open":
        if not status_values:
            return "open", []
        if len(set(status_values)) > 1:
            # in-progress wins: the costly mistake is routing an actively-worked
            # item back into triage, not the reverse.
            return "in-progress", ["conflicting_status_labels"]
        return status_values[0], []
    # closed
    warnings: list[str] = []
    if status_values:
        warnings.append("stale_status_label")  # our close removes it; a UI close doesn't
    if state_reason == "not_planned":
        return "dropped", warnings
    if state_reason == "completed":
        return "shipped", warnings
    # null / "reopened"-era value on a closed issue -> shipped is the benign default.
    warnings.append("closed_without_reason")
    return "shipped", warnings


# --- Error kind mapping (api-contract error model) --------------------------

# Kinds -> (retryable, exit code). Exit: 0 success · 1 operational · 2 usage · 3 retryable.
_KIND_EXIT = {
    "usage": 2,
    "auth": 1,
    "not_found": 1,
    "validation": 1,
    "conflict": 1,
    "internal": 1,
    "network": 3,
    "rate_limited": 3,
    "server": 3,
}
_RETRYABLE_KINDS = {"network", "rate_limited", "server"}


def exit_code_for(kind: str) -> int:
    return _KIND_EXIT.get(kind, 1)


def make_error(
    kind: str,
    message: str,
    status: "int | None" = None,
    retry_after: "int | None" = None,
    detail: "dict[str, Any] | None" = None,
) -> "dict[str, Any]":
    error: dict[str, Any] = {
        "kind": kind,
        "message": message,
        "retryable": kind in _RETRYABLE_KINDS,
        "status": status,
    }
    if retry_after is not None:
        error["retry_after"] = retry_after
    if detail:
        error["detail"] = detail
    return error


def classify_error(result: "dict[str, Any]") -> "dict[str, Any]":
    """Map a non-ok ``backlog_github`` result into a stable ``error`` dict.

    Implements the api-contract's status/header -> kind table. The rate-limit
    discriminator matters: a bare 403 is an auth/permission failure; a 403 is
    ``rate_limited`` only when a ``retry-after`` header is present or
    ``x-ratelimit-remaining`` is 0 (rate headers ride on every response).
    """
    if result.get("status") is None:
        return make_error(
            "network",
            result.get("message") or "network error",
            status=None,
        )
    status = int(result["status"])
    headers = result.get("headers", {}) or {}
    message = result.get("message") or f"HTTP {status}"
    detail = _request_id_detail(headers)

    if status == 401:
        return make_error("auth", message or "bad credentials", status=status, detail=detail)
    if status == 404:
        return make_error("not_found", message or "not found", status=status, detail=detail)
    if status == 422:
        return make_error("validation", message or "validation failed", status=status, detail=detail)
    if status == 429:
        return make_error(
            "rate_limited", message or "rate limited", status=status,
            retry_after=_retry_after(headers), detail=detail,
        )
    if status == 403:
        if _is_rate_limited_403(headers):
            return make_error(
                "rate_limited", message or "rate limited", status=status,
                retry_after=_retry_after(headers), detail=detail,
            )
        return make_error("auth", message or "permission denied", status=status, detail=detail)
    if 500 <= status < 600:
        return make_error("server", message or "server error", status=status, detail=detail)
    # Any other unexpected status: non-retryable operational error.
    return make_error("validation", message or f"unexpected HTTP {status}", status=status, detail=detail)


def _is_rate_limited_403(headers: "dict[str, str]") -> bool:
    if "retry-after" in headers:
        return True
    return str(headers.get("x-ratelimit-remaining", "")).strip() == "0"


def _retry_after(headers: "dict[str, str]") -> "int | None":
    value = headers.get("retry-after")
    if value and str(value).strip().isdigit():
        return int(str(value).strip())
    return None


def _request_id_detail(headers: "dict[str, str]") -> "dict[str, Any] | None":
    request_id = headers.get("x-github-request-id")
    if request_id:
        return {"github_request_id": request_id}
    return None


# --- Operations (walking skeleton: create / get / list) ---------------------

def create_item(
    client: Any,
    owner: str,
    repo: str,
    title: str,
    body: "str | None" = None,
    stage: "str | None" = None,
    labels: "list[str] | None" = None,
    added: "str | None" = None,
) -> "dict[str, Any]":
    """Create one item; return ``{"ok", "item"/"error", "warnings"}``."""
    payload, warnings = encode_create(title, body=body, stage=stage, labels=labels, added=added)
    result = client.create_issue(owner, repo, payload)
    if not result.get("ok"):
        return {"ok": False, "error": classify_error(result), "warnings": warnings}
    item, decode_warn = decode_issue(result["json"], owner, repo)
    return {"ok": True, "item": item, "warnings": warnings + decode_warn}


def get_item(client: Any, owner: str, repo: str, number: int) -> "dict[str, Any]":
    """Fetch one item by number; reject a PR-numbered id (not a backlog item)."""
    result = client.get_issue(owner, repo, number)
    if not result.get("ok"):
        return {"ok": False, "error": classify_error(result), "warnings": []}
    raw = result["json"] or {}
    if "pull_request" in raw:
        return {
            "ok": False,
            "error": make_error(
                "not_found",
                f"#{number} is a pull request, not a backlog item",
                status=result.get("status"),
            ),
            "warnings": [],
        }
    item, warnings = decode_issue(raw, owner, repo)
    return {"ok": True, "item": item, "warnings": warnings}


def list_items(
    client: Any,
    owner: str,
    repo: str,
    state: str = "open",
    labels: "list[str] | None" = None,
    assignee: "str | None" = None,
    since: "str | None" = None,
    limit: "int | None" = None,
    full: bool = False,
) -> "dict[str, Any]":
    """List items (auto-follows ``Link`` cursors, bounded by ``limit``).

    Defensively drops any object carrying a ``pull_request`` key — the captured
    behavior is that PRs no longer appear in the issues list, and this keeps a
    version drift from silently injecting a PR as a backlog item.
    """
    from lib import backlog_github  # noqa: PLC0415 — link-cursor helper; keeps import graph shallow

    params: dict[str, Any] = {"state": state, "per_page": 100}
    if labels:
        params["labels"] = ",".join(labels)
    if assignee:
        params["assignee"] = assignee
    if since:
        params["since"] = since

    items: list[dict[str, Any]] = []
    warnings: list[str] = []
    cursor: "str | None" = None
    result = client.list_issues(owner, repo, params)
    while True:
        if not result.get("ok"):
            return {"ok": False, "error": classify_error(result), "warnings": warnings}
        for raw in result.get("json") or []:
            if not isinstance(raw, dict) or "pull_request" in raw:
                continue
            item, item_warn = decode_issue(raw, owner, repo)
            warnings.extend(item_warn)
            if item.get("updated_at"):
                cursor = item["updated_at"] if cursor is None else max(cursor, item["updated_at"])
            if not full:
                item = {k: v for k, v in item.items() if k != "body"}
            items.append(item)
            if limit is not None and len(items) >= limit:
                return _list_result(items[:limit], cursor, warnings)
        next_url = backlog_github.parse_next_link(result.get("headers", {}).get("link"))
        if not next_url:
            break
        result = client.request_url("GET", next_url)
    return _list_result(items, cursor, warnings)


def _list_result(
    items: "list[dict[str, Any]]", cursor: "str | None", warnings: "list[str]"
) -> "dict[str, Any]":
    return {
        "ok": True,
        "data": {"items": items, "count": len(items), "cursor": cursor},
        "warnings": warnings,
    }
