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
``update`` (optimistic CAS + mass-assignment guard), ``comment``, ``claim`` /
``unclaim`` (atomic take-and-verify + visible staleness), ``link`` / ``unlink``
(typed relationship edges), and the minimal ``provision``. The read side
(``list`` / ``pick`` / ``counts``) lives in the sibling ``query`` module, which
reuses this module's envelope helpers.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone

from . import encode, ids, provision
from .transport import RETRYABLE_DEFAULTS, Transport, TransportError

# The default claim-staleness TTL (CC3/M11). No upstream artifact pins a number,
# so this is a build-time default: longer than any single agent work-cycle (a
# claim is never reaped out from under live work) yet short enough that a claim
# orphaned by a died fleet agent frees within a day so ``pick`` cannot starve.
# Overridable per call (``claim_ttl_seconds``) — human policy stays the authority.
# `query.pick` imports this so the reap threshold is defined once.
DEFAULT_CLAIM_TTL_SECONDS: int = 24 * 60 * 60

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


def from_transport_error(exc: TransportError) -> dict:
    return error(exc.code, exc.message, retryable=exc.retryable, details=exc.details)


def log_diag(message: str) -> None:
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
    automated: bool = False,
    worker: str | None = None,
) -> dict:
    """Create one item (AG2): ``title`` + ``body`` suffice; every facet optional.

    Returns the new item's ID immediately (dedup is advisory-async and deferred).
    Attribution is the resolved **API identity** (SEC-3), never the git-push
    identity. New items default to ``open`` (no ``status:`` label — Data Model §4).

    When ``automated`` (an **unattended** run — Security §1a/SEC-6), the block is
    stamped ``automated: true`` + a ``worker`` marker so a background sweep is not
    misattributed to the human. The front resolves the unattended context (see
    ``context.py``); ``core`` just records what it is told.
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
        full_body = _body_with_block(body, automated=automated, worker=worker)
        issue = transport.create_issue(
            owner, repo, title=title, body=full_body, labels=labels
        )
    except TransportError as exc:
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6 — unexpected boundary
        log_diag(f"unexpected transport failure on file: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    canonical = f"{owner}/{repo}#{issue.get('number')}"
    item, decode_warnings = encode.decode_item(issue, canonical_id=canonical)
    warnings.extend(decode_warnings)
    item["actor"] = actor
    return ok(item, warnings)


def _body_with_block(body: str, *, automated: bool = False, worker: str | None = None) -> str:
    """Append a minimal ``prawduct:`` block (``v: 1``) to the issue body.

    An unattended create stamps ``automated: true`` + a ``worker`` marker (CC4/
    SEC-6) so a background sweep is not misattributed to the human."""
    fields = {"v": "1"}
    if automated:
        fields["automated"] = "true"
        if worker:
            fields["worker"] = worker
    block = encode.serialize_block(fields)
    text = body.rstrip("\n")
    if text:
        return f"{text}\n\n{block}\n"
    return f"{block}\n"


def _body_update_preserving_block(old_body: str, new_body: str) -> str:
    """Apply a caller's body edit while **preserving the existing ``prawduct:``
    block**.

    The block carries body-authoritative fields (``id_aliases``, ``verified``,
    ``superseded_by`` …) that live ONLY in the body (Data Model §2) — a naive
    full-body replacement would silently drop them (an MG2 / permanent-alias-loss
    footgun). So: re-parse the existing block, strip any block the caller pasted
    into the new text (the block is edited through its own fields, not free-text
    ``--body``), and re-append the preserved block. No existing block → a fresh
    ``v: 1`` (same as ``file``).
    """
    block = encode.parse_block(old_body)
    human = encode.strip_block(new_body)
    rendered = block.reserialize() if block.fields else encode.serialize_block({"v": "1"})
    if human:
        return f"{human}\n\n{rendered}\n"
    return f"{rendered}\n"


# --- get ---------------------------------------------------------------------


def get_item(
    transport: Transport,
    *,
    id_raw: str,
    default_owner: str | None = None,
    settle_retries: int = 0,
    sleeper=None,
) -> dict:
    """Fetch one item by any accepted ID spelling; decode into the item shape.

    ``settle_retries`` handles the **observed** brief post-create replication
    window (QRY-1): reading *your own just-written item* can 404 momentarily. It
    is opt-in and **only** for a read-your-own-write (create/claim verify) — a
    plain ``get`` keeps ``settle_retries=0`` so a genuine not-found stays fast and
    the never-block floor is never diluted with retries on real absences.
    """
    nid = ids.normalize_id(id_raw, default_owner=default_owner)
    if not nid.ok:
        return error(nid.error or "validation", nid.message or f"bad ID {id_raw!r}")
    try:
        issue = _get_issue_settling(
            transport, nid.owner, nid.repo, nid.number, settle_retries, sleeper
        )
    except TransportError as exc:
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        log_diag(f"unexpected transport failure on get: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    item, warnings = encode.decode_item(issue, canonical_id=nid.canonical)
    return ok(item, warnings)


def _get_issue_settling(
    transport: Transport,
    owner: str,
    repo: str,
    number: int,
    settle_retries: int,
    sleeper,
) -> dict:
    """``get_issue`` with a bounded retry on ``not_found`` (the post-create
    replication window). Raises the last ``TransportError`` if it never settles."""
    sleep = sleeper if sleeper is not None else _default_settle_sleep
    attempt = 0
    while True:
        try:
            return transport.get_issue(owner, repo, number)
        except TransportError as exc:
            if exc.code == "not_found" and attempt < settle_retries:
                sleep(attempt)
                attempt += 1
                continue
            raise


def _default_settle_sleep(attempt: int) -> None:
    time.sleep(0.25 * (attempt + 1))


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
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        log_diag(f"unexpected transport failure on status: {type(exc).__name__}")
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

        # Direct fields — one PATCH; labels are untouched by this. A body edit
        # preserves the existing prawduct: block (block-authoritative fields live
        # only in the body — Data Model §2); other direct fields pass through.
        patch: dict = {k: fields[k] for k in _UPDATE_DIRECT if k in fields and k != "body"}
        if "body" in fields:
            patch["body"] = _body_update_preserving_block(issue.get("body") or "", fields["body"])
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
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        log_diag(f"unexpected transport failure on update: {type(exc).__name__}")
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
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        log_diag(f"unexpected transport failure on comment: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    data = {
        "id": comment.get("id"),
        "item": nid.canonical,
        "url": comment.get("html_url"),
        "actor": (comment.get("user") or {}).get("login"),
    }
    return ok(data)


# --- claim / unclaim (atomic take-and-verify + visible staleness) ------------


def claim(
    transport: Transport,
    *,
    id_raw: str,
    default_owner: str | None = None,
    claim_ttl_seconds: int = DEFAULT_CLAIM_TTL_SECONDS,
    now: datetime | None = None,
    sleeper=None,
) -> dict:
    """Atomically take an item (CC3/M11): set the assignee to the **API identity**
    and stamp ``claimed_at`` (block-authoritative visible staleness), then
    **verify** by re-reading. A different actor's **live** claim (within the TTL)
    yields a non-fatal ``claim_conflict``; a claim aged past the TTL is reaped
    (taken). A lost take-and-verify race also returns ``claim_conflict`` so the
    caller re-picks. Idempotent for the same actor (re-stamps the heartbeat).
    """
    nid = ids.normalize_id(id_raw, default_owner=default_owner)
    if not nid.ok:
        return error(nid.error or "validation", nid.message or f"bad ID {id_raw!r}")
    now = now or datetime.now(timezone.utc)

    warnings: list[str] = []
    try:
        actor = transport.get_authenticated_user().get("login")
        issue = transport.get_issue(nid.owner, nid.repo, nid.number)
        current, _ = encode.decode_item(issue, canonical_id=nid.canonical)

        holder = current.get("assignee")
        if holder and holder != actor:
            claimed_at = encode.parse_iso(current.get("claimed_at"))
            # No stamp → cannot age it → treat as a live (human/UI) claim, never
            # reaped out from under someone. Only a stamp past the TTL is reaped.
            live = claimed_at is None or (now - claimed_at).total_seconds() <= claim_ttl_seconds
            if live:
                return error(
                    "claim_conflict",
                    f"{nid.canonical} is claimed by {holder}",
                    details={"holder": holder, "claimed_at": current.get("claimed_at")},
                )

        # Take it in ONE atomic PATCH — the assignee *and* the claimed_at stamp
        # together. Two separate writes could crash between them and strand an
        # assignee-set/no-stamp item, which decodes as a *live* claim no TTL reap
        # can free (the exact M11 never-starve gap, since a died agent never
        # re-runs to converge). GitHub's issue PATCH sets `assignees` and `body`
        # in a single request, so no torn intermediate state exists.
        new_body = encode.upsert_block_field(
            issue.get("body") or "", "claimed_at", now.isoformat()
        )
        transport.update_issue(
            nid.owner,
            nid.repo,
            nid.number,
            fields={"assignees": [actor], "body": new_body},
        )

        # Take-and-verify: re-read (settling the post-write window) and confirm we
        # hold it — a concurrent claimant that won surfaces here as a conflict.
        verify = _get_issue_settling(transport, nid.owner, nid.repo, nid.number, 3, sleeper)
    except TransportError as exc:
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        log_diag(f"unexpected transport failure on claim: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    item, decode_warnings = encode.decode_item(verify, canonical_id=nid.canonical)
    warnings.extend(decode_warnings)
    if item.get("assignee") != actor:
        return error(
            "claim_conflict",
            f"lost the claim race for {nid.canonical}; re-pick",
            details={"holder": item.get("assignee")},
        )
    return ok(item, warnings)


def unclaim(
    transport: Transport,
    *,
    id_raw: str,
    default_owner: str | None = None,
) -> dict:
    """Release a claim (idempotent): clear the assignee and the ``claimed_at``
    stamp. Unclaiming an already-free item is a near-no-op (no redundant writes)."""
    nid = ids.normalize_id(id_raw, default_owner=default_owner)
    if not nid.ok:
        return error(nid.error or "validation", nid.message or f"bad ID {id_raw!r}")
    try:
        issue = transport.get_issue(nid.owner, nid.repo, nid.number)
        current, _ = encode.decode_item(issue, canonical_id=nid.canonical)
        # One atomic PATCH clears assignee + stamp together (same crash-safety as
        # claim). Empty when already free — an unclaimed item takes no writes.
        old_body = issue.get("body") or ""
        new_body = encode.upsert_block_field(old_body, "claimed_at", None)
        patch: dict = {}
        if current.get("assignee"):
            patch["assignees"] = []
        if new_body != old_body:
            patch["body"] = new_body
        if patch:
            transport.update_issue(nid.owner, nid.repo, nid.number, fields=patch)
        result = transport.get_issue(nid.owner, nid.repo, nid.number)
    except TransportError as exc:
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        log_diag(f"unexpected transport failure on unclaim: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    item, warnings = encode.decode_item(result, canonical_id=nid.canonical)
    return ok(item, warnings)


# --- link / unlink (typed relationship edges) --------------------------------

# The typed edges `link`/`unlink` set (API §2.3). `blocks`/`blocked-by` are native
# dependencies (so a blocker is queryable — DM3, the ready-work predicate);
# `parent`/`child` are native sub-issues; `related` has no native GitHub edge, so
# it lives in the block as a `related: [ids]` list (block-authoritative, Data
# Model §2 — parallel to `id_aliases`).
_EDGE_TYPES: tuple[str, ...] = ("blocks", "blocked-by", "parent", "child", "related")


def link(
    transport: Transport,
    *,
    id_raw: str,
    edge: str,
    target_raw: str,
    default_owner: str | None = None,
) -> dict:
    """Set a typed edge from an item to a target (idempotent). ``edge`` is one of
    ``blocks``/``blocked-by``/``parent``/``child``/``related``."""
    return _mutate_edge(transport, id_raw, edge, target_raw, default_owner, add=True)


def unlink(
    transport: Transport,
    *,
    id_raw: str,
    edge: str,
    target_raw: str,
    default_owner: str | None = None,
) -> dict:
    """Clear a typed edge from an item to a target (idempotent)."""
    return _mutate_edge(transport, id_raw, edge, target_raw, default_owner, add=False)


def _mutate_edge(
    transport: Transport,
    id_raw: str,
    edge: str,
    target_raw: str,
    default_owner: str | None,
    *,
    add: bool,
) -> dict:
    if edge not in _EDGE_TYPES:
        return error(
            "validation",
            f"unknown edge {edge!r}; expected one of {', '.join(_EDGE_TYPES)}",
        )
    nid = ids.normalize_id(id_raw, default_owner=default_owner)
    if not nid.ok:
        return error(nid.error or "validation", nid.message or f"bad ID {id_raw!r}")
    tid = ids.normalize_id(target_raw, default_owner=default_owner)
    if not tid.ok:
        return error(tid.error or "validation", tid.message or f"bad target ID {target_raw!r}")
    if nid.canonical == tid.canonical:
        return error("validation", "an item cannot be linked to itself")

    try:
        if edge == "blocked-by":
            _dep(transport, nid, tid, add=add)
        elif edge == "blocks":
            # A blocks B ⇔ B is blocked-by A.
            _dep(transport, tid, nid, add=add)
        elif edge == "parent":
            # target is the parent ⇒ this item is target's sub-issue.
            _sub(transport, tid, nid, add=add)
        elif edge == "child":
            _sub(transport, nid, tid, add=add)
        else:  # related — block-list machinery
            _related(transport, nid, tid.canonical, add=add)
    except TransportError as exc:
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        verb = "link" if add else "unlink"
        log_diag(f"unexpected transport failure on {verb}: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    return ok(
        {"item": nid.canonical, "edge": edge, "target": tid.canonical, "linked": add}
    )


def _dep(transport: Transport, blocked, blocker, *, add: bool) -> None:
    """Add/remove a native dependency: ``blocked`` is blocked-by ``blocker``."""
    fn = transport.add_blocked_by if add else transport.remove_blocked_by
    fn(
        blocked.owner,
        blocked.repo,
        blocked.number,
        blocker_owner=blocker.owner,
        blocker_repo=blocker.repo,
        blocker_number=blocker.number,
    )


def _sub(transport: Transport, parent, child, *, add: bool) -> None:
    """Add/remove a native sub-issue edge: ``child`` under ``parent``."""
    fn = transport.add_sub_issue if add else transport.remove_sub_issue
    fn(
        parent.owner,
        parent.repo,
        parent.number,
        child_owner=child.owner,
        child_repo=child.repo,
        child_number=child.number,
    )


def _related(transport: Transport, nid, target_canonical: str, *, add: bool) -> None:
    """Add/remove a ``related`` ref in the item's block list (no native edge)."""
    issue = transport.get_issue(nid.owner, nid.repo, nid.number)
    block = encode.parse_block(issue.get("body"))
    current = set(encode.parse_list(block.get("related")))
    if add:
        current.add(target_canonical)
    else:
        current.discard(target_canonical)
    value = encode.format_list(sorted(current)) if current else None
    old_body = issue.get("body") or ""
    new_body = encode.upsert_block_field(old_body, "related", value)
    if new_body != old_body:
        transport.update_issue(nid.owner, nid.repo, nid.number, fields={"body": new_body})


# --- provision ---------------------------------------------------------------


def provision_labels(transport: Transport, *, owner: str, repo: str) -> dict:
    """Create/reconcile the base namespaced taxonomy (minimal — PROV-1)."""
    try:
        result = provision.ensure_labels(
            transport, owner, repo, provision.base_labels()
        )
    except TransportError as exc:
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        log_diag(f"unexpected transport failure on provision: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    data = {
        "repo": f"{owner}/{repo}",
        "created": result.created,
        "existing": result.existing,
    }
    return ok(data, result.warnings)


def reconcile_labels(transport: Transport, *, owner: str, repo: str) -> dict:
    """Reconcile the full namespaced taxonomy (GV6): create any missing base
    label, leave every existing/foreign label untouched, and report the
    coexistence picture. Idempotent and collision-free (Data Model §3, PROV-1)."""
    try:
        result = provision.reconcile(transport, owner, repo)
    except TransportError as exc:
        return from_transport_error(exc)
    except (OSError, json.JSONDecodeError) as exc:  # ERR-6
        log_diag(f"unexpected transport failure on reconcile-labels: {type(exc).__name__}")
        return error("unavailable", "the backend request failed unexpectedly")

    data = {
        "repo": f"{owner}/{repo}",
        "created": result.created,
        "existing": result.existing,
        "foreign_untouched": result.foreign_untouched,
    }
    return ok(data, result.warnings)
