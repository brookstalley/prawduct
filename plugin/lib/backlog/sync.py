"""Sync — the only module that holds both a transport and a store.

``cache.py`` knows nothing about any provider and ``cachequery.py`` never
writes; this is where provider issues become provider-neutral cache rows. The
boundary is the same shape that makes ``transport.py`` the sole egress: one
module to read when asking "what does this cache know about GitHub?".

**Two paths, and the watermark is what chooses between them.** The rebuild
fetches every issue in scope, decodes it, and replaces the store's contents in
one transaction; the incremental sync fetches only what the provider says has
changed since the watermark and upserts it. A missing watermark means rebuild,
which is what makes rebuild the safe default rather than a special case — it is
also the answer to a first build, a schema bump, and a corrupt store, and it is
never a deletion sweep (Cache Spec §6).

**Scope is one repo.** The store holds items from exactly the repo named in
``backlog_service_repo`` (see ``cache.py`` on why widening that is a design
change rather than a flag).

Errors are return values: a fetch that fails leaves the previous store contents
untouched and reports why, because a rebuild that half-ran and reported success
would be indistinguishable from a backlog that shrank.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import cache, encode
from .core import error, from_transport_error, log_diag, ok
from .encode import parse_iso
from .query import all_issues
from .transport import Transport, TransportError, Validator

#: How far back the watermark is rewound before it is handed to the provider.
#:
#: ``since`` is already inclusive, so the boundary item is re-read without this;
#: the margin buys cover for what inclusivity does not — an item committed
#: server-side at the same second the scan read past it, or provider clock skew
#: between the node that stamped ``updated_at`` and the one that answered the
#: query. Re-reading is free of consequence because upserts are idempotent, so
#: the margin is priced in wasted rows rather than in risk; the reverse mistake
#: is silent permanent loss. Two minutes is enough for both causes and still
#: leaves a warm sync reading nothing on almost every run.
CURSOR_OVERLAP = timedelta(minutes=2)


def _rows_from_issues(issues: list[dict], owner: str, repo: str) -> list[dict]:
    """Decode provider issues into cache rows.

    In-scope means what ``list``/``pick`` already mean by it: an issue carrying a
    prawduct label or body block. Plain repo issues and pull requests are not
    backlog items and are dropped by the same predicate the live path uses — a
    cache that disagreed with the live path about what counts as an item would
    fail rebuild-equivalence for a reason that has nothing to do with caching.

    This pairs each decoded item with the raw issue it came from, which is why
    it does not reuse ``query``'s decode helper: the provider's ``created_at``
    and ``updated_at`` are on the issue, not on the decoded item, and consumers
    2, 10 and 15 are all date predicates over exactly those two."""
    rows: list[dict] = []
    for issue in issues:
        if not encode.is_prawduct_issue(issue):
            continue
        canonical = f"{owner}/{repo}#{issue.get('number')}"
        item, _warnings = encode.decode_item(issue, canonical_id=canonical)
        rows.append(
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "body": item.get("body"),
                "status": item.get("status"),
                "stage": item.get("stage"),
                "area": item.get("area"),
                "effort": item.get("effort"),
                "impact": item.get("impact"),
                "source": item.get("source"),
                "created_at": issue.get("created_at"),
                "updated_at": issue.get("updated_at"),
                "etag": None,
            }
        )
    return rows


def full_rebuild(
    transport: Transport,
    *,
    project_dir: Path,
    owner: str,
    repo: str,
    now: datetime | None = None,
) -> dict:
    """Rebuild the whole store from the provider.

    Every issue in the repo, open and closed alike: consumers 5 and 14 ask
    whether an id resolves and whether it is dead, and a store holding only open
    items answers "no such item" to both — the wrong answer, and one a reader
    cannot tell from the right one.

    **Fetch first, write second.** The store is replaced only once the whole
    fetch has succeeded, so a transport failure part-way through leaves the
    previous contents in place rather than a truncated store that reads as a
    shrunken backlog."""
    stamp = (now or datetime.now(timezone.utc)).isoformat()

    issues = all_issues(transport, owner, repo, state="all", labels=None)
    if isinstance(issues, dict):
        return issues  # an error envelope from the transport — bubble it up

    try:
        rows = _rows_from_issues(issues, owner, repo)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        log_diag(f"could not decode issues for the backlog cache: {type(exc).__name__}: {exc}")
        return error("unavailable", "the backlog cache could not decode the fetched issues")

    conn = cache.open_store(project_dir, create=True)
    if isinstance(conn, dict):
        return conn
    try:
        written = cache.replace_items(
            conn,
            rows,
            scope=f"{owner}/{repo}",
            fetched_at=stamp,
            cursor_since=_watermark_from(issues, floor=None),
        )
        if written.get("status") != "ok":
            return written
    finally:
        conn.close()

    data = dict(written.get("data") or {})
    # Same key set as every other sync exit — the values differ, the shape must
    # not, or a consumer reading `data["not_modified"]` works on one path and
    # raises on another.
    data.update({"fetched_at": stamp, "rebuilt": True, "not_modified": False})
    warnings = [] if data.get("fts") else ["text search is unavailable: SQLite has no FTS5"]
    return ok(data, warnings)


def _watermark_from(issues: list[dict], *, floor: str | None) -> str | None:
    """The watermark a fetch of ``issues`` earns, rewound by the overlap margin.

    Taken over the **raw** issues rather than the decoded rows: a non-prawduct
    issue in the window still proves the window was read up to its timestamp, and
    an issue that later becomes a backlog item does so by being edited, which
    moves its ``updated_at`` past any watermark set here. Filtering first would
    advance the watermark only as far as the newest *item*, re-reading everything
    between that and the newest *issue* on every subsequent sync — correct, but
    needlessly.

    ``floor`` keeps the watermark monotonic. A window that returns nothing new
    must leave it exactly where it was, or a no-op sync would rewind the cursor
    by the overlap margin on every run and walk it steadily backwards."""
    stamps = [issue.get("updated_at") for issue in issues if issue.get("updated_at")]
    parsed = [value for value in (parse_iso(stamp) for stamp in stamps) if value is not None]
    if not parsed:
        return floor
    rewound = max(parsed) - CURSOR_OVERLAP
    # Compared as instants, never as strings: the provider stamps `...Z` while
    # `isoformat()` writes `...+00:00`, so the same moment has two spellings and
    # the lexicographic answer between them is not the chronological one.
    floor_at = parse_iso(floor) if floor else None
    if floor_at is not None and rewound < floor_at:
        return floor
    return rewound.isoformat()


def incremental_sync(
    transport: Transport,
    *,
    project_dir: Path,
    owner: str,
    repo: str,
    now: datetime | None = None,
) -> dict:
    """Bring the store up to date by fetching only what changed.

    Three outcomes, and the cheap one is the common one. With no watermark this
    delegates to :func:`full_rebuild`. With a watermark it first asks the
    provider whether the window changed at all — a conditional request that costs
    **zero rate-limit points** when the answer is no — and returns without
    fetching a page. Only when something did change does it scan the window and
    upsert.

    **``state="all"`` is load-bearing, not defensive.** ``since`` and ``state``
    are independent filters on the provider (verified live, Cache Spec §6), so
    the ``state="open"`` default would drop exactly the closed items whose
    disappearance the cache has no other way to learn about — Cache Spec §6
    accepts having no deletion sweep *because* ``since`` catches closes, and it
    only does under this argument.

    **Ordered ``updated_at`` ascending**, which is what makes the scan safe
    against writes landing during it. An item edited mid-scan moves toward the
    end of the ordering, so it is either seen again in this pass (harmless —
    upserts are idempotent) or left beyond the last page with an ``updated_at``
    newer than the watermark this pass earns, so the next pass fetches it.
    Descending would move it behind the read cursor instead, and it would be
    skipped by exactly the pages already read.
    """
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    scope = f"{owner}/{repo}"

    conn = cache.open_store(project_dir, create=True)
    if isinstance(conn, dict):
        return conn
    # Never raises — an unreadable cursor reports "not synced" (cache.py), which
    # routes to the rebuild below rather than to an error.
    since, etag = cache.get_cursor_state(conn, scope)
    if since is None:
        # Never synced, or a rebuild that found nothing to take a provider
        # timestamp from. Either way there is no window to be incremental about.
        conn.close()
        return full_rebuild(transport, project_dir=project_dir, owner=owner, repo=repo, now=now)

    try:
        validator = _revalidate(transport, owner, repo, since=since, etag=etag)
        if isinstance(validator, dict):
            return validator  # a transport error envelope — bubble it up
        if not validator.changed:
            return ok(
                {
                    "written": 0,
                    "fts": cache.has_fts(conn),
                    "scope": scope,
                    "since": since,
                    "fetched_at": stamp,
                    "rebuilt": False,
                    "not_modified": True,
                }
            )

        issues = all_issues(
            transport,
            owner,
            repo,
            state="all",
            labels=None,
            sort="updated",
            direction="asc",
            since=since,
        )
        if isinstance(issues, dict):
            return issues

        try:
            rows = _rows_from_issues(issues, owner, repo)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            log_diag(f"could not decode issues for the backlog cache: {type(exc).__name__}: {exc}")
            return error("unavailable", "the backlog cache could not decode the fetched issues")

        advanced = _watermark_from(issues, floor=since)
        written = cache.apply_incremental(
            conn,
            rows,
            scope=scope,
            since=advanced,
            # The validator belongs to the query at the OLD watermark. If the
            # watermark moved, that query no longer exists and its validator can
            # only ever miss — storing it would look like a live optimisation
            # while buying nothing. Dropping it says "ask unconditionally next
            # time", which is what actually happens either way; the difference is
            # that the stored pair stays honest, and `_write_cursor`'s invariant
            # stays true instead of aspirational.
            etag=validator.etag if advanced == since else None,
            fetched_at=stamp,
        )
    finally:
        conn.close()

    if written.get("status") != "ok":
        return written
    data = dict(written.get("data") or {})
    data.update({"fetched_at": stamp, "rebuilt": False, "not_modified": False})
    warnings = [] if data.get("fts") else ["text search is unavailable: SQLite has no FTS5"]
    return ok(data, warnings)


def _revalidate(
    transport: Transport, owner: str, repo: str, *, since: str, etag: str | None
):
    """The conditional pre-flight, or an error envelope.

    A transport that does not implement the probe at all is treated as "changed"
    rather than as a failure: revalidation is an optimisation, and a provider or
    a fake without it should sync normally instead of refusing to sync."""
    try:
        return transport.get_issues_validator(owner, repo, state="all", since=since, etag=etag)
    except NotImplementedError:
        # The base `Transport` defines this method, so a `getattr` guard would
        # find it and then raise from inside — the check has to be on the CALL,
        # not on the attribute. A provider without a conditional-request path
        # syncs unconditionally; it does not fail to sync.
        return Validator(changed=True, etag=None)
    except TransportError as exc:
        return from_transport_error(exc)
