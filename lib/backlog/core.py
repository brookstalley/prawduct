"""Core — deterministic CRUD and the return-value envelope (G1, API §3/§4).

Core holds all the operation logic; the CLI and MCP fronts are thin over it
(Test Specs §1.1). It **never** touches a model client (INV-1): no module under
``lib/backlog/`` imports or calls a model — the scrub's model step lives in the
skill/workflow layer, never here. Errors are **return-value based** (the project
convention): every op returns an envelope, never raises into a caller; the only
exceptions caught here are the boundary ``TransportError`` (expected transport
failures) and unexpected ``OSError``/``JSONDecodeError`` from the transport,
which are mapped and logged, never swallowed (ERR-6).

Implemented ops: ``file``, ``get``, the two-axis ``set-status`` transition,
``update`` (optimistic CAS + mass-assignment guard), ``comment``, and the minimal
``provision``.
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


# --- status (set-status: the crash-safe two-axis transition) -----------------


def set_status(
    transport: Transport,
    *,
    id_raw: str,
    target: str,
    default_owner: str | None = None,
) -> dict:
    """Idempotent, crash-safe two-axis status transition (Data Model §4 B1, CC1/M5).

    Canonical write order so a crashed client never half-writes:
      1. **state authority first** — for a *closed* target set closed +
         ``state_reason`` (that alone makes the decoded status correct even if steps
         2–3 never run); for an *open* target reopen if needed (clearing any stale
         close reason);
      2. **add** the target's ``status:`` label *before* removing any other — never a
         zero-label window (this step exists only for the open sub-states, whose one
         encoding is the label; ``open``/``shipped``/``dropped`` have no such label);
      3. remove every *other* ``status:`` label (the losers / stale sub-state).
    Each step is guarded (skipped when already satisfied), so a re-run — including
    the re-run after an injected mid-transition crash — is a no-op and converges.

    (For a closed target this reduces to state-first-then-strip-labels — there is no
    ``status:shipped``/``status:dropped`` label in the taxonomy, and the closed
    ``state_reason`` is the authority the decoder reads regardless of any transient
    label, so there is never an unreadable window. ``closed_by`` recording — native
    timeline handle + the manual ``--closed-by`` block stamp, Data Model §1.1 /
    API §2.6 — is deferred, tracked as a NOTE.)
    """
    if target not in encode.STATUS_VALUES:
        return error(
            "validation",
            f"unknown status {target!r}; expected one of {', '.join(encode.STATUS_VALUES)}",
        )
    nid = ids.normalize_id(id_raw, default_owner=default_owner)
    if not nid.ok:
        return error(nid.error or "validation", nid.message or f"bad ID {id_raw!r}")

    target_state, target_reason, target_label = encode.encode_status(target)
    warnings: list[str] = []
    try:
        issue = transport.get_issue(nid.owner, nid.repo, nid.number)

        # Step 1 — move the state authority first.
        cur_state = (issue.get("state") or "open").lower()
        cur_reason = issue.get("state_reason")
        needs_state = cur_state != target_state or (
            target_state == "closed" and cur_reason != target_reason
        )
        if needs_state:
            # A close sets the reason; a (re)open clears any stale close reason.
            fields = {
                "state": target_state,
                "state_reason": target_reason if target_state == "closed" else None,
            }
            issue = transport.update_issue(nid.owner, nid.repo, nid.number, fields=fields)

        # Steps 2–3 — reconcile the status: labels toward the target: add the
        # target's label BEFORE removing any loser (never a zero-label window),
        # then strip the losers (remove is idempotent).
        present = encode.status_labels_present(encode.label_names(issue))
        to_add, to_remove = encode.reconcile_status_labels(present, target_label)
        for name in to_add:
            prov = provision.ensure_labels(transport, nid.owner, nid.repo, [name])
            warnings.extend(prov.warnings)
            transport.add_labels(nid.owner, nid.repo, nid.number, [name])
        for name in to_remove:
            transport.remove_label(nid.owner, nid.repo, nid.number, name)

        issue = transport.get_issue(nid.owner, nid.repo, nid.number)
    except TransportError as exc:
        return _from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        _log(f"unexpected transport failure on status: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    item, decode_warnings = encode.decode_item(issue, canonical_id=nid.canonical)
    warnings.extend(decode_warnings)
    return ok(item, warnings)


# --- update (field-wise edit; optimistic CAS + mass-assignment guard) ---------

# The ONLY fields `update` may write (SEC-2 allowlist). `status` goes through
# set-status, `assignee` through claim; native/protected fields are never writable
# from request input.
_UPDATE_DIRECT: tuple[str, ...] = ("title", "body")
_UPDATE_FACETS: tuple[str, ...] = ("stage", "kind", "area", "effort", "impact", "source")


def update_item(
    transport: Transport,
    *,
    id_raw: str,
    fields: dict,
    expected_updated_at: str | None = None,
    default_owner: str | None = None,
) -> dict:
    """Field-wise edit with optimistic CAS (CC2) and a mass-assignment guard (SEC-2).

    Writes **only** the documented item fields the caller named — ``title``,
    ``body``, and the soft-enum facets (``stage``/``kind``/``area``/``effort``/
    ``impact``/``source``). ``status`` goes through set-status, ``assignee`` through
    claim; any other key — a native/protected field (``node_id``, ``number``,
    ``state``, ``history``), an ``automated:`` marker, foreign attribution — is
    **rejected**, never written from request input (attribution comes only from the
    API identity). When ``expected_updated_at`` is supplied, a live ``updated_at``
    mismatch returns a **retryable ``conflict``** (the lost-update guard) so the
    caller re-reads and retries.
    """
    if not fields:
        return error("validation", "update requires at least one field to change")
    # SEC-2 — reject any field off the allowlist. Reject (not silently ignore) so a
    # mass-assignment attempt or a caller typo is surfaced, never quietly dropped.
    allowed = set(_UPDATE_DIRECT) | set(_UPDATE_FACETS)
    rejected = sorted(key for key in fields if key not in allowed)
    if rejected:
        return error(
            "validation",
            f"update cannot write field(s) {rejected}; writable fields are {sorted(allowed)}",
            details={"rejected": rejected},
        )
    nid = ids.normalize_id(id_raw, default_owner=default_owner)
    if not nid.ok:
        return error(nid.error or "validation", nid.message or f"bad ID {id_raw!r}")

    warnings: list[str] = []
    try:
        issue = transport.get_issue(nid.owner, nid.repo, nid.number)

        # CC2 — optimistic CAS on updated_at (only when the caller supplied one).
        if expected_updated_at is not None and issue.get("updated_at") != expected_updated_at:
            return error(
                "conflict",
                "the item changed since you last read it; re-fetch and retry",
                details={
                    "expected_updated_at": expected_updated_at,
                    "actual_updated_at": issue.get("updated_at"),
                },
            )

        # Direct fields (title/body) — one PATCH; labels are untouched by this.
        patch = {key: fields[key] for key in _UPDATE_DIRECT if key in fields}
        if patch:
            issue = transport.update_issue(nid.owner, nid.repo, nid.number, fields=patch)

        # Facet edits — each is a label swap (add the new value before removing the
        # old, same never-empty-window discipline as set-status). Facets are
        # independent prefixes, so each reads its own present set off `issue`.
        for facet in _UPDATE_FACETS:
            if facet not in fields:
                continue
            value = fields[facet]
            check = encode.check_enum(facet, value)
            if not check.ok:
                return error("validation", check.message or f"invalid {facet}")
            if check.warning:
                warnings.append(check.warning)
            new_label = f"{facet}:{value}"
            present = [n for n in encode.label_names(issue) if n.startswith(f"{facet}:")]
            if new_label not in present:
                prov = provision.ensure_labels(transport, nid.owner, nid.repo, [new_label])
                warnings.extend(prov.warnings)
                transport.add_labels(nid.owner, nid.repo, nid.number, [new_label])
            for old in present:
                if old != new_label:
                    transport.remove_label(nid.owner, nid.repo, nid.number, old)

        issue = transport.get_issue(nid.owner, nid.repo, nid.number)
    except TransportError as exc:
        return _from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        _log(f"unexpected transport failure on update: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    item, decode_warnings = encode.decode_item(issue, canonical_id=nid.canonical)
    warnings.extend(decode_warnings)
    return ok(item, warnings)


# --- comment -----------------------------------------------------------------


def comment_item(
    transport: Transport,
    *,
    id_raw: str,
    body: str,
    default_owner: str | None = None,
) -> dict:
    """Add a native, attributed comment (DM5). Not idempotent. Attribution is the
    **API identity** (GitHub stamps the authenticated user), never caller-supplied.
    """
    if not body or not body.strip():
        return error("validation", "comment body is required")
    nid = ids.normalize_id(id_raw, default_owner=default_owner)
    if not nid.ok:
        return error(nid.error or "validation", nid.message or f"bad ID {id_raw!r}")
    try:
        comment = transport.create_comment(nid.owner, nid.repo, nid.number, body=body)
    except TransportError as exc:
        return _from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        _log(f"unexpected transport failure on comment: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    data = {
        "id": comment.get("id"),
        "item": nid.canonical,
        "url": comment.get("html_url"),
        "actor": (comment.get("user") or {}).get("login"),
    }
    return ok(data)


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
