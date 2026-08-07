"""Cachequery — the consumer surface over the store. Reads, never writes.

Consumers (norm probes, skills, ``pick``) call this module and never open a
connection themselves, the same way nothing but ``transport.py`` reaches the
network. That is what keeps the store's two invariants enforceable in one place
rather than restated at every call site:

**Unavailable is never empty.** A consumer that cannot reach the cache reports
``unavailable`` with a reason. It never returns an empty result set, because a
silent reader and a clean bill of health are indistinguishable to whoever reads
the output — which is the exact failure the dormant checks were made to announce
rather than commit.

**Every served payload carries a visible age**, and it is the age of the *rows*:
the oldest ``fetched_at`` in the store, because an age is a promise about the
whole payload and the honest promise is the worst row in it. The scope's sync
cursor is deliberately **not** the source — that is a provider timestamp
recording how far the reads have covered, so a repo whose newest item was edited
a year ago would report a year-old cache one second after a clean sync. The one
case with no rows to age is a scope that synced and legitimately holds nothing;
there the cursor's own ``fetched_at`` answers, since "empty" and "never synced"
are different claims and only the second should send an operator to go and sync.
A store with neither has never been synced, and says so rather than serving.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from . import cache
from .core import error, log_diag, ok
from .encode import OPEN_STATUSES, parse_iso


def _freshness(conn: sqlite3.Connection, scope: str, *, now: datetime) -> tuple[str, float] | None:
    """``(fetched_at, age_seconds)`` for the scope, or ``None`` if there is
    nothing to age.

    **Age comes from ``fetched_at``, never from the cursor**, and the two are not
    interchangeable even though both are timestamps. ``fetched_at`` records when
    *this machine last read a row*; the cursor records *how far into the
    provider's history the reads have covered*, and it is a provider timestamp.
    Asking the cursor how old the cache is answers a different question in the
    provider's clock domain — a repo whose newest item was edited a year ago
    would report a year-old cache one second after a successful sync.

    **The empty store still has an age.** With no rows there is nothing to take a
    row stamp from, but a scope that synced cleanly and genuinely holds zero
    items is not the same as one that has never synced — and only the second
    should tell an operator to go and sync. So the fallback is the cursor's own
    ``fetched_at``, which records the sync rather than the rows. ``None`` now
    means what it says: no sync has ever completed for this scope.
    """
    stamp = cache.oldest_fetched_at(conn) or cache.last_synced_at(conn, scope)
    if stamp is None:
        return None
    parsed = parse_iso(stamp)
    if parsed is None:
        return None
    return stamp, (now - parsed).total_seconds()


def open_items(project_dir: Path, *, scope: str, now: datetime) -> dict:
    """Every open item with its id, title and body — consumer 1 (and 6).

    The Critic's backlog-reconciliation walk and the PR reviewer's resolved-items
    check both need the full open set with text, which is the query that made a
    persisted cache worth building: it is one scan of local rows rather than a
    paginated fetch on every review.

    **Open means every non-terminal status, not the literal ``open`` one.**
    ``submitted`` and ``in-progress`` items are live — an in-progress item is
    precisely the one a PR reviewer is looking for when asking whether this
    branch resolves something — and filtering on ``status = 'open'`` would drop
    them while still reporting success. The predicate comes from
    ``encode.OPEN_STATUSES``, which derives from the status encoding's single
    source of truth, so a new sub-state is included here the day it is added
    rather than the day someone notices it missing."""
    conn = cache.open_store(project_dir, create=False)
    if isinstance(conn, dict):
        return conn
    try:
        fresh = _freshness(conn, scope, now=now)
        if fresh is None:
            return error(
                "unavailable",
                "the backlog cache has never been synced; run `prawduct-hook backlog sync`",
            )
        synced_at, age = fresh
        placeholders = ", ".join("?" for _ in OPEN_STATUSES)
        rows = conn.execute(
            "SELECT id, title, body, status, stage, area, effort, impact, source, "
            f"created_at, updated_at FROM item WHERE status IN ({placeholders}) ORDER BY id",
            OPEN_STATUSES,
        ).fetchall()
    except sqlite3.Error as exc:
        log_diag(f"backlog cache read failed: {type(exc).__name__}: {exc}")
        return error("unavailable", f"the backlog cache could not be read ({type(exc).__name__})")
    finally:
        conn.close()

    return ok(
        {
            "items": [dict(row) for row in rows],
            "scope": scope,
            "synced_at": synced_at,
            "age_seconds": age,
        }
    )
