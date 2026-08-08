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
import os
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

#: ``details["mirror"]`` on the envelopes that mean *there is no local mirror to
#: update here* — no store built, or one holding no scope yet. Distinct from a
#: mirror that exists and failed, which is what a write-site warning is for.
MIRROR_ABSENT = "absent"


def _rows_from_issues(issues: list[dict], owner: str, repo: str) -> tuple[list[dict], list[str]]:
    """Decode provider issues into cache rows, and name the ones that are not ours.

    In-scope means what ``list``/``pick`` already mean by it: an issue carrying a
    prawduct label or body block. Plain repo issues and pull requests are not
    backlog items and are dropped by the same predicate the live path uses — a
    cache that disagreed with the live path about what counts as an item would
    fail rebuild-equivalence for a reason that has nothing to do with caching.

    **The out-of-scope ids are returned rather than discarded**, and that second
    list is the whole reason for the tuple. An issue whose block and labels are
    stripped stops being an item, and an upsert-only sync has no other way to
    learn it: the row would sit in the store as an open item forever, reaching
    the consumers that walk the open set. That is a stale *positive* — an answer
    rather than a gap — and unlike hard deletion and transfer-out (Cache Spec §6's
    two accepted invisible cases) the window already carries the evidence, so
    there is nothing to accept.

    This pairs each decoded item with the raw issue it came from, which is why
    it does not reuse ``query``'s decode helper: the provider's ``created_at``
    and ``updated_at`` are on the issue, not on the decoded item, and consumers
    2, 10 and 15 are all date predicates over exactly those two."""
    rows: list[dict] = []
    out_of_scope: list[str] = []
    for issue in issues:
        if not encode.is_prawduct_issue(issue):
            # A pull request was never an item, so it cannot have stopped being
            # one — only a real issue can leave scope, and only that is worth a
            # delete.
            if not encode.is_pull_request(issue):
                out_of_scope.append(f"{owner}/{repo}#{issue.get('number')}")
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
                # Two of the three fields Cache Spec §3 adds. They decode from
                # the block, so they rebuild from the provider like everything
                # else here. `affected` is stored in the block's own `[a, b]`
                # spelling (`None` when empty, so a reader never has to tell `[]`
                # from "no value") — which is what lets `cache._write_affected`
                # re-derive the path index from the column instead of from a
                # parallel field that could drift.
                #
                # `tags` is the third and is deliberately NOT stored: no consumer
                # query reads it from the cache and `list --tag` is served live
                # off the provider's label filter, so a column for it would be
                # the dead field `cache.ITEM_COLUMNS` forbids. It still decodes,
                # and it still round-trips through the provider; the cache simply
                # is not one of its readers.
                "affected": _list_column(item.get("affected")),
                "working_branch": item.get("working_branch"),
            }
        )
    return rows, out_of_scope


def _list_column(values: list[str] | None) -> str | None:
    """A decoded list as its stored column value, or ``None`` when empty."""
    return encode.format_list(values) if values else None


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
        # The rebuild discards the whole store first, so an issue that left
        # scope simply does not come back — no eviction list is needed here, and
        # that asymmetry with the incremental path is the point rather than an
        # oversight.
        rows, _out_of_scope = _rows_from_issues(issues, owner, repo)
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
        # After the rows land and before the connection goes: the store has just
        # been rewritten wholesale and nothing is waiting on a query, which is the
        # cheap moment to reclaim what a `DELETE`-based rebuild leaves behind.
        cache.optimize(conn)
    finally:
        conn.close()

    data = dict(written.get("data") or {})
    # Same key set as every other sync exit — the values differ, the shape must
    # not, or a consumer reading `data["not_modified"]` works on one path and
    # raises on another.
    data.update({"fetched_at": stamp, "rebuilt": True, "not_modified": False})
    warnings = [] if data.get("fts") else ["text search is unavailable: SQLite has no FTS5"]
    return ok(data, warnings)


def absorb_issue(
    project_dir: Path,
    *,
    owner: str,
    repo: str,
    issue: dict,
    now: datetime | None = None,
) -> dict:
    """Mirror one just-written provider issue into the store. Never raises.

    Called by the adapter's write paths with the authoritative issue they already
    hold — a create response, or the ``get_issue`` a status/field write ends on —
    so mirroring spends **no additional provider request**.

    **The issue is decoded by the same function a full fetch uses**, which is what
    makes a mirrored row equal to the row a rebuild would write. The alternative
    shape — patching the one column the caller knows changed — is wrong twice: it
    silently skips every other column the provider moved (a status write also
    moves ``updated_at``, and a body write moves the alias and path indexes), and
    it makes the store an author rather than a mirror, which is the property
    rebuild-equivalence exists to deny.

    **An unsynced store stays unsynced, and the test is a cursor row rather than a
    file.** A store conjured or half-filled by a write would hold exactly one item
    and answer ``open-items`` with it — authoritative-looking and wrong by the size
    of the backlog. ``create=False`` stops the first case but not the second:
    ``_ensure_schema`` commits the schema in its own transaction, so a rebuild
    whose ``replace_items`` step then fails leaves a **schema-only store** — file
    present, ``item`` and ``cursor`` both empty. That store today reads as
    never-synced because ``cachequery._freshness`` finds no coverage stamp and no
    row stamps; one mirrored row into it would produce a payload of one item aged
    seconds, which is the freshness lie this whole section exists to prevent.
    Requiring a ``cursor`` row is what makes "the store was actually synced" the
    condition, instead of "a file is there".

    (``create=False`` governs *creation*, not write permission — an existing store
    opens read-write either way — which is why a writer reaching for what
    :func:`cache.open_store` calls the reader's door is deliberate.)

    **The same row check answers a second question: whether this item belongs
    here at all.** An id carries its own ``owner/repo`` and ``--repo`` is only a
    default, so a single-id write can target a repo this store does not hold, and
    mirroring it would write a row no rebuild would reproduce. The check is made
    against the scope the **store** holds rather than against the caller's
    ``--repo``, which a command run wholly against another backlog would satisfy
    vacuously. A store that holds some other scope skips silently — that is a
    correct write to an item this cache was never meant to hold, not a degraded
    one — while a store that holds no scope at all is the unsynced case above and
    says so.

    An issue that no longer decodes as an item is evicted rather than upserted. It
    is barely reachable through the write ops (none of them can strip the block or
    the labels), which is exactly why it is handled here rather than assumed away:
    the cost is one branch, and the failure it prevents is a row that answers the
    open-item walk forever.
    """
    stamp = (now or datetime.now(timezone.utc)).isoformat()

    # Tagged so a caller can tell "there is no mirror here" from "the mirror is
    # broken" without matching on message text. The first is silent at the write
    # site — every read already reports it, with the command that fixes it — and
    # the second is worth saying, because a store that answers reads and refuses
    # writes is the surprising case.
    absent = cache.cache_path(project_dir)
    if absent is None or not absent.exists():
        return error(
            "unavailable",
            "the backlog cache has not been built yet; run `prawduct-hook backlog sync`",
            details={"mirror": MIRROR_ABSENT},
        )

    try:
        rows, out_of_scope = _rows_from_issues([issue], owner, repo)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        log_diag(
            f"could not decode a written issue for the backlog cache: "
            f"{type(exc).__name__}: {exc}"
        )
        return error("unavailable", "the backlog cache could not decode the written issue")

    conn = cache.open_store(project_dir, create=False)
    if isinstance(conn, dict):
        return conn  # absent, unreadable, or schema-mismatched — say so, build nothing
    try:
        scope = f"{owner}/{repo}"
        covered = cache.cursor_scopes(conn)
        if covered is None:
            # Readable enough to open, not readable enough to answer. Saying
            # "run a sync" here would send an operator to repair a store whose
            # problem a sync does not address.
            return error("unavailable", "the backlog cache could not be read")
        if scope not in covered:
            if not covered:
                return error(
                    "unavailable",
                    "the backlog cache has not been synced yet; "
                    "run `prawduct-hook backlog sync`",
                    details={"mirror": MIRROR_ABSENT},
                )
            # The store is fine and this item simply is not its business.
            # Same key set as the mirror's other ok exits, plus the reason —
            # a consumer reading `written` must not have to know which exit it got.
            return ok(
                {"written": 0, "evicted": 0, "fts": cache.has_fts(conn),
                 "skipped": "out-of-scope"}
            )
        return cache.absorb_rows(conn, rows, fetched_at=stamp, evict=out_of_scope)
    finally:
        conn.close()


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
            # **A 304 is a positive result and it is recorded as one.** The
            # provider has just said there is nothing newer than the watermark,
            # which establishes that the store is level with it — a stronger
            # claim than "no rows were written", and the one a reader's visible
            # age is asking about. Returning here without stamping it, which is
            # what this path did before, meant the cheapest and most common
            # successful sync left no trace and the age it should have reset
            # went on growing.
            failed = cache.confirm_coverage(conn, scope, stamp)
            warnings = []
            if failed is not None:
                # The sync itself succeeded; only the bookkeeping did not. The
                # cost is an age that keeps over-reporting, which errs toward
                # "staler than it is" — worth saying out loud, not worth failing
                # a good sync over.
                warnings.append(
                    "the cache is current, but its coverage stamp could not be written: "
                    f"{(failed.get('error') or {}).get('message')}"
                )
            return ok(
                {
                    "written": 0,
                    "evicted": 0,
                    "fts": cache.has_fts(conn),
                    "scope": scope,
                    "since": since,
                    "fetched_at": stamp,
                    "rebuilt": False,
                    "not_modified": True,
                },
                warnings,
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
            rows, out_of_scope = _rows_from_issues(issues, owner, repo)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            log_diag(f"could not decode issues for the backlog cache: {type(exc).__name__}: {exc}")
            return error("unavailable", "the backlog cache could not decode the fetched issues")

        advanced = _watermark_from(issues, floor=since)
        written = cache.apply_incremental(
            conn,
            rows,
            # Issues in this window that are no longer backlog items. Evicted in
            # the same transaction as the upserts, for the same reason the
            # watermark rides with them: a window is applied whole or not at all.
            evict=out_of_scope,
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


def spawn_sync(
    hook_cmd: list[str],
    project_dir: Path,
    scope: str,
    *,
    popen=None,
    env: dict | None = None,
) -> bool:
    """Warm the cache in a **detached** subprocess — the only automatic SYNC trigger.

    Not the store's only writer: every eligible backlog write mirrors itself into
    the store as it goes (Cache Spec §6.1). This is what pulls in what someone
    ELSE changed.

    Until this existed, the only writer reachable from outside a test was a human
    typing ``prawduct-hook backlog sync``: nothing scheduled it and no hook spawned
    it, so every consumer's freshness had an owner in principle and none in
    practice — age visible, nothing making it small. That gap is sharpest for the
    consumers this trigger was added for, which are **restricted-tool agents** (the
    Critic's reconciliation walk, the PR reviewer's checks): ``cachequery``'s
    "run ``prawduct-hook backlog sync``" reaches a reader who cannot run anything
    that writes.

    Deliberately the same shape as ``snapshot.spawn_refresh`` — fire-and-forget,
    own session, ``PRAWDUCT_UNATTENDED=1``, returns immediately — rather than a new
    mechanism, because session start must never block on the network and one
    detached-spawn *policy* shape beside one detached-Popen *mechanism*
    (``transport.spawn_detached``, the sole subprocess egress) is what keeps that
    property checkable in one place.

    **Incremental, never ``--rebuild``.** The steady state is a conditional request
    that takes a rate-free 304, so the recurring cost of the trigger is one
    unauthenticated-cheap round trip per session; a rebuild on every session start
    would refetch the whole backlog to learn nothing changed. The incremental path
    already falls back to a rebuild by itself when no watermark exists, so a first
    run still fills the store.

    Returns ``True`` if the spawn was issued (never raises — a failed warm just
    means the next read is staler and says so, which is the visible-age contract
    doing its job)."""
    from .transport import spawn_detached  # noqa: PLC0415 — lazy; transport owns egress

    child_env = dict(env if env is not None else os.environ)
    child_env["PRAWDUCT_UNATTENDED"] = "1"
    argv = [*hook_cmd, "backlog", "sync", "--repo", scope]
    return spawn_detached(argv, cwd=project_dir, env=child_env, popen=popen)
