"""Sync — the only module that holds both a transport and a store.

``cache.py`` knows nothing about any provider and ``cachequery.py`` never
writes; this is where provider issues become provider-neutral cache rows. The
boundary is the same shape that makes ``transport.py`` the sole egress: one
module to read when asking "what does this cache know about GitHub?".

**The rebuild is the whole of W1's first step**: fetch every issue in scope,
decode it into prawduct vocabulary, and replace the store's contents in one
transaction. Incremental sync — the cursor watermark and conditional
revalidation — layers on top of this later; the rebuild path stays as the answer
to a first build, a schema bump, and a corrupt store.

**Scope is one repo.** The store holds items from exactly the repo named in
``backlog_service_repo`` (see ``cache.py`` on why widening that is a design
change rather than a flag).

Errors are return values: a fetch that fails leaves the previous store contents
untouched and reports why, because a rebuild that half-ran and reported success
would be indistinguishable from a backlog that shrank.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from . import cache, encode
from .core import error, log_diag, ok
from .query import all_issues
from .transport import Transport


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
        written = cache.replace_items(conn, rows, scope=f"{owner}/{repo}", fetched_at=stamp)
        if written.get("status") != "ok":
            return written
    finally:
        conn.close()

    data = dict(written.get("data") or {})
    data.update({"fetched_at": stamp, "rebuilt": True})
    warnings = [] if data.get("fts") else ["text search is unavailable: SQLite has no FTS5"]
    return ok(data, warnings)
