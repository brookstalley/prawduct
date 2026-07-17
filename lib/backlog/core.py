"""Core — deterministic CRUD and the return-value envelope (G1, API §3/§4).

Core holds all the operation logic; the CLI and MCP fronts are thin over it
(Test Specs §1.1). It **never** touches a model client (INV-1): no module under
``lib/backlog/`` imports or calls a model — the scrub's model step lives in the
skill/workflow layer, never here. Errors are **return-value based** (the project
convention): every op returns an envelope, never raises into a caller; the only
exceptions caught here are the boundary ``TransportError`` (expected transport
failures) and unexpected ``OSError``/``JSONDecodeError`` from the transport,
which are mapped and logged, never swallowed (ERR-6).

Chunk-01 ops: ``file``, ``get``, and the minimal ``provision``.
"""

from __future__ import annotations

import json
import sys

from . import encode, ids, provision
from .transport import RETRYABLE_DEFAULTS, Transport, TransportError

# --- The envelope (API §3/§4) ------------------------------------------------
#
# The stable error-code → `retryable` default table is owned by `transport`
# (`RETRYABLE_DEFAULTS`) — the single source of truth, imported here rather than
# copied, so the CLI-generated and transport-generated errors can never drift.


def ok(data, warnings: list[str] | None = None) -> dict:
    return {"status": "ok", "data": data, "warnings": warnings or []}


def error(
    code: str,
    message: str,
    *,
    retryable: bool | None = None,
    details: dict | None = None,
) -> dict:
    return {
        "status": "error",
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable if retryable is not None else RETRYABLE_DEFAULTS.get(code, False),
            "details": details or {},
        },
    }


def _from_transport_error(exc: TransportError) -> dict:
    return error(exc.code, exc.message, retryable=exc.retryable, details=exc.details)


def _log(message: str) -> None:
    print(f"backlog: {message}", file=sys.stderr)


# --- file --------------------------------------------------------------------

# The soft-enum facets `file` accepts as flags → their label facet name.
_FILE_FACETS: tuple[str, ...] = ("stage", "kind", "area", "effort", "impact", "source")


def file_item(
    transport: Transport,
    *,
    owner: str,
    repo: str,
    title: str,
    body: str,
    facets: dict[str, str] | None = None,
) -> dict:
    """Create one item (AG2): ``title`` + ``body`` suffice; every facet optional.

    Returns the new item's ID immediately (dedup is advisory-async and deferred).
    Attribution is the resolved **API identity** (SEC-3), never the git-push
    identity. New items default to ``open`` (no ``status:`` label — Data Model §4).
    """
    facets = facets or {}
    if not title or not title.strip():
        return error("validation", "title is required")
    if body is None:
        return error("validation", "body is required (may be empty text, not omitted)")

    warnings: list[str] = []
    labels: list[str] = []
    for facet in _FILE_FACETS:
        value = facets.get(facet)
        if value is None:
            continue
        check = encode.check_enum(facet, value)
        if not check.ok:
            return error("validation", check.message or f"invalid {facet}")
        if check.warning:
            warnings.append(check.warning)
        labels.append(f"{facet}:{value}")

    try:
        actor = transport.get_authenticated_user().get("login")
        # Provision the labels this create references, so the create never names a
        # non-existent label (the create is the authority; provisioning first is
        # correct regardless of GitHub's auto-create behavior).
        if labels:
            prov = provision.ensure_labels(transport, owner, repo, labels)
            warnings.extend(prov.warnings)
        full_body = _body_with_block(body)
        issue = transport.create_issue(
            owner, repo, title=title, body=full_body, labels=labels
        )
    except TransportError as exc:
        return _from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6 — unexpected boundary
        _log(f"unexpected transport failure on file: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    canonical = f"{owner}/{repo}#{issue.get('number')}"
    item, decode_warnings = encode.decode_item(issue, canonical_id=canonical)
    warnings.extend(decode_warnings)
    item["actor"] = actor
    return ok(item, warnings)


def _body_with_block(body: str) -> str:
    """Append a minimal ``prawduct:`` block (``v: 1``) to the issue body."""
    block = encode.serialize_block({"v": "1"})
    text = body.rstrip("\n")
    if text:
        return f"{text}\n\n{block}\n"
    return f"{block}\n"


# --- get ---------------------------------------------------------------------


def get_item(
    transport: Transport,
    *,
    id_raw: str,
    default_owner: str | None = None,
) -> dict:
    """Fetch one item by any accepted ID spelling; decode into the item shape."""
    nid = ids.normalize_id(id_raw, default_owner=default_owner)
    if not nid.ok:
        return error(nid.error or "validation", nid.message or f"bad ID {id_raw!r}")
    try:
        issue = transport.get_issue(nid.owner, nid.repo, nid.number)
    except TransportError as exc:
        return _from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        _log(f"unexpected transport failure on get: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    item, warnings = encode.decode_item(issue, canonical_id=nid.canonical)
    return ok(item, warnings)


# --- provision ---------------------------------------------------------------


def provision_labels(transport: Transport, *, owner: str, repo: str) -> dict:
    """Create/reconcile the base namespaced taxonomy (minimal — PROV-1)."""
    try:
        result = provision.ensure_labels(
            transport, owner, repo, provision.base_labels()
        )
    except TransportError as exc:
        return _from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        _log(f"unexpected transport failure on provision: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    data = {
        "repo": f"{owner}/{repo}",
        "created": result.created,
        "existing": result.existing,
    }
    return ok(data, result.warnings)
