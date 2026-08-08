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

**Every served payload carries a visible age**, and it is the age of the store's
**coverage** — see :func:`_freshness`, which is the one place that number is
decided and the one place worth reading before trusting it.

The functions here are the consumer query union of Cache Spec §2, and that union
is deliberately small: open-item listing with text, grouping and counting by
``area``, id resolution through aliases including dead items, creation-time
filtering, text search scoped to an area, and two date predicates. Each names
the consumers it serves, so a column no function reads is a dead field and a
function no consumer names is an invention.

One function here serves a consumer Cache Spec §2 does not enumerate:
:func:`ready_items`, whose consumer is ``query.pick``. §2 inventories the readers
that went *dormant* at the cutover, and `pick` never did — it has always run live.
It is named here rather than left implicit because the same rule applies to it as
to the other fifteen: it exists because a consumer asks for it, and if that
consumer stops asking, it goes.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from . import cache, encode, ids
from .core import error, log_diag, ok
from .encode import OPEN_STATUSES, parse_iso

#: What a reader is told when no sync has ever completed for the scope. One
#: spelling, because it is the message that sends an operator to go and fix it.
_NEVER_SYNCED = "the backlog cache has never been synced; run `prawduct-hook backlog sync`"

#: The full item projection — every column a consumer reads, **including the
#: body**. Used by the queries whose consumers read item text: the reconciliation
#: walk, the changed-file intersection, search, and resolution.
_FULL_COLUMNS: tuple[str, ...] = (
    "id",
    "title",
    "body",
    "status",
    "stage",
    "area",
    "effort",
    "impact",
    "source",
    "created_at",
    "updated_at",
    "affected",
    "working_branch",
)

#: The same projection without the body, for the listing and grouping queries.
#: The body is by far the largest column in the store, and a grouping payload
#: carrying one per row would hand a caller counting items by area the entire
#: corpus in memory to do it. Derived from the full set rather than written out
#: again, so a column can never be in one list and missing from the other. This
#: is the only shape difference between payloads here, so it is named rather than
#: left to be discovered.
_BRIEF_COLUMNS: tuple[str, ...] = tuple(c for c in _FULL_COLUMNS if c != "body")


def _select(columns: tuple[str, ...], *, prefix: str = "") -> str:
    return ", ".join(prefix + column for column in columns)


class _Declined(Exception):
    """Internal control flow: a query that cannot run, carrying its reason.

    Turned into this module's ``unavailable`` envelope by :func:`_serve`, and it
    never crosses the module boundary — the project's error-handling preference
    (``lib/`` functions return ``status``/``reason`` dicts) is about what callers
    see, and callers see an envelope. It exists so a query that has to decline
    from *inside* the connection — a text search on a store built without FTS5 —
    can do so without every function here repeating the open, age, close dance
    around its own early return.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class _Reported(Exception):
    """Internal control flow: a query with a finding of its own to return.

    Sibling of :class:`_Declined` for the case where the answer is a specific
    error rather than an unavailability — an ``alias_collision``, where the store
    was read perfectly well and what it holds is the problem. Confusing the two
    would tell an operator to go and sync when the actual repair is on the items.
    """

    def __init__(self, envelope: dict) -> None:
        super().__init__(envelope)
        self.envelope = envelope


def _freshness(conn: sqlite3.Connection, scope: str, *, now: datetime) -> tuple[str, float] | None:
    """``(confirmed_at, age_seconds)`` for the scope, or ``None`` if the scope has
    never been synced.

    **Age answers "how far behind the provider might this store be?", and the
    only honest input is when a sync last confirmed coverage** — the
    ``coverage_confirmed_at`` stamp every successful sync advances, the
    not-modified one included, since a 304 establishes that the provider has
    nothing newer rather than merely that nothing was written.

    The row stamps cannot answer it, and how they stopped being able to is worth
    stating because they *could* while the cache was rebuild-only.
    ``MIN(item.fetched_at)`` was then the age of the whole payload, every row
    having been written by the same sync. Under incremental sync only the window
    is restamped, so that number becomes the fetch time of the least-recently
    **edited** item and grows without bound while syncs keep succeeding: a store
    synced ten seconds ago can honestly report an age of weeks, and a consumer
    would read the cache as abandoned at the moment it was most current.

    The rows stay as the **fallback**, for a store that holds rows but carries no
    cursor row. Today's writers cannot produce one — every write path stamps the
    cursor in the same transaction as the rows — so this is a reader declining to
    claim *never synced* about a store whose rows are visibly there, rather than
    a path with a known producer. ``None`` still means what it says: nothing has
    ever been read into this scope.

    Neither stamp is the sync **cursor**. That is a *provider* timestamp
    recording how far into the provider's history the reads have covered, so a
    repo whose newest item was edited a year ago would report a year-old cache
    one second after a clean sync.
    """
    stamp = cache.coverage_confirmed_at(conn, scope) or cache.oldest_fetched_at(conn)
    if stamp is None:
        return None
    parsed = parse_iso(stamp)
    if parsed is None:
        return None
    return stamp, (now - parsed).total_seconds()


def _serve(project_dir: Path, *, scope: str, now: datetime, query) -> dict:
    """Open the store, age it, run ``query(conn)``, and wrap what comes back.

    Every public function here goes through this, which is what makes the two
    invariants — unavailable is never empty, every payload carries an age — a
    property of the module rather than a habit each function has to remember.
    """
    conn = cache.open_store(project_dir, create=False)
    if isinstance(conn, dict):
        return conn
    try:
        fresh = _freshness(conn, scope, now=now)
        if fresh is None:
            return error("unavailable", _NEVER_SYNCED)
        confirmed_at, age = fresh
        payload = query(conn)
    except _Reported as reported:
        return reported.envelope
    except _Declined as declined:
        return error("unavailable", declined.reason)
    except sqlite3.Error as exc:
        log_diag(f"backlog cache read failed: {type(exc).__name__}: {exc}")
        return error("unavailable", f"the backlog cache could not be read ({type(exc).__name__})")
    finally:
        conn.close()

    return ok({**payload, "scope": scope, "synced_at": confirmed_at, "age_seconds": age})


def _rows(conn: sqlite3.Connection, sql: str, params=()) -> list[dict]:
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _open_placeholders() -> str:
    return ", ".join("?" for _ in OPEN_STATUSES)


# --- consumers 1 and 6: the open set with text -------------------------------


def open_items(project_dir: Path, *, scope: str, now: datetime) -> dict:
    """Every open item with its id, title and body — consumers 1 and 6.

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

    def query(conn: sqlite3.Connection) -> dict:
        return {
            "items": _rows(
                conn,
                f"SELECT {_select(_FULL_COLUMNS)} FROM item "
                f"WHERE status IN ({_open_placeholders()}) ORDER BY id",
                OPEN_STATUSES,
            )
        }

    return _serve(project_dir, scope=scope, now=now, query=query)


# --- consumer 2: created since ------------------------------------------------


def items_created_since(project_dir: Path, *, scope: str, since: str, now: datetime) -> dict:
    """Items created at or after ``since`` — consumer 2 (C-B1 missing metadata).

    The date is the **provider's** ``created_at``, not a block field. Cache Spec
    §2.1's *observable beats stored*: a creation date the provider always sets and
    nobody can forget beats an ``added:`` field with no write path, which is the
    trade that let the same pass delete two other stored dates.

    Inclusive at the boundary, matching the provider's own ``since`` semantics
    (Cache Spec §6, verified live) — a caller passing a ref's timestamp means
    "everything from that point", and the two ends of this feature disagreeing
    about whether the boundary item counts is exactly the off-by-one nobody
    notices.
    """
    if parse_iso(since) is None:
        return error("validation", f"`since` must be an ISO-8601 timestamp, got {since!r}")

    def query(conn: sqlite3.Connection) -> dict:
        return {
            "items": _rows(
                conn,
                f"SELECT {_select(_BRIEF_COLUMNS)} FROM item "
                f"WHERE {_instant('created_at')} >= {_instant('?')} "
                "ORDER BY created_at, id",
                (since,),
            ),
            "since": since,
        }

    return _serve(project_dir, scope=scope, now=now, query=query)


def _instant(expression: str) -> str:
    """``expression`` as an epoch instant, for comparing two timestamps in SQL.

    **Compared as instants, never as strings**, which is the same rule
    ``sync._watermark_from`` records and for the same reason: the provider stamps
    ``...Z`` while Python's ``isoformat()`` writes ``...+00:00``, so one moment
    has two spellings and the lexicographic answer between them is not the
    chronological one. ``strftime`` parses both and yields a number, so a bound
    computed locally and a stamp written by the provider compare correctly.

    It costs the ``item_updated_at`` index, since a function over a column cannot
    use one — a deliberate trade at a corpus of hundreds of rows, where the scan
    is orders of magnitude inside the NFR §4 budget and a wrong answer at the
    boundary would not be. A stamp too malformed to parse yields NULL and drops
    out of the comparison, which is the right answer for a row that cannot
    honestly satisfy a date predicate either way.

    **The CAST is load-bearing, not decoration.** ``strftime`` returns **TEXT**,
    and neither side of these comparisons is a column with numeric affinity, so
    without it SQLite compares two epoch strings *lexicographically* — which is
    the very failure this helper was written to remove, reintroduced one level
    down as a digit-count problem instead of a spelling one. It is wrong whenever
    the two epochs differ in length, i.e. as soon as either side falls before
    2001-09-09 (10 digits becomes 9): ``'946684800' < '1577836800'`` is false.
    The symptom is a confident wrong answer in either direction — an empty set for
    a distant ``created-since`` bound, or every open item reported stale for a
    distant ``--older-than``.
    """
    return f"CAST(strftime('%s', {expression}) AS INTEGER)"


# --- consumers 3 and 8: grouping and counting by area -------------------------


def by_area(project_dir: Path, *, scope: str, now: datetime, open_only: bool = True) -> dict:
    """Items grouped by ``area``, with a count per group — consumers 3 and 8.

    One query for two consumers because they want the same grouping at different
    depths: the Critic's dedup-evidence check (3) reads each group's ``count`` and
    the ids under it to decide whether a new item duplicates an existing one, and
    the janitor's grouped listing (8) reads the items themselves. Serving 8 with a
    second query over the same rows would be the second home the grouping does
    not need.

    **An item with no area is a group, not a silence.** It lands under ``(none)``
    — the spelling ``query.counts`` already uses for a missing stage — because
    unfaceted items are precisely what a dedup or hygiene sweep is looking for,
    and dropping them from a grouping would hide the untended ones from the check
    that exists to find them.
    """

    def query(conn: sqlite3.Connection) -> dict:
        sql = f"SELECT {_select(_BRIEF_COLUMNS)} FROM item"
        params: tuple = ()
        if open_only:
            sql += f" WHERE status IN ({_open_placeholders()})"
            params = tuple(OPEN_STATUSES)
        groups: dict[str, list[dict]] = {}
        for row in _rows(conn, sql + " ORDER BY id", params):
            groups.setdefault(row["area"] or "(none)", []).append(row)
        return {
            "groups": [
                {"area": area, "count": len(items), "items": items}
                for area, items in sorted(groups.items())
            ],
            "open_only": open_only,
        }

    return _serve(project_dir, scope=scope, now=now, query=query)


# --- consumers 1 and 4: the changed-file intersection -------------------------


def items_affecting(
    project_dir: Path, *, scope: str, changed_paths, now: datetime, open_only: bool = True
) -> dict:
    """Items whose ``affected`` list covers any of ``changed_paths`` — consumers 1
    and 4, and the one capability this cache adds rather than restores.

    C-B3 and the reconciliation walk previously required a reviewer to read item
    text and infer whether the diff touched it. This is that inference as a set
    intersection, which is the whole argument for splitting ``affected`` out of
    free-text ``refs`` (Cache Spec §2.2).

    **The direction of the match is why the schema looks the way it does.** An
    entry *contains* a changed file — ``plugin/lib`` matches
    ``plugin/lib/sync.py`` — and phrasing that over the stored column runs
    ``WHERE ? LIKE affected || '%'``, whose variable is on the side no index can
    help. So each changed file is expanded into its ancestor directories
    (``encode.path_ancestors``) and matched by **equality** against
    ``item_affected``, which the index does serve. Write it the natural way and
    you get a table scan *and* a ``plugin/lib`` that swallows ``plugin/libexec``.

    Each returned item carries ``matched`` — the entries of its own list that the
    change touched — because a consumer reporting "this item looks related" has to
    be able to say which path made it think so.
    """
    # Materialize FIRST: `changed_paths` is walked three times (here, then
    # `encode.affected_matches` and `list(...)` inside `query`). A generator would
    # exhaust on this line and leave the rest reading empty — `keys` correct,
    # every `matched` empty, `changed_paths: []`, and `status: ok`. That is a
    # confident wrong answer, which is the exact failure this module exists to
    # avoid; no caller passes an iterator today, and this keeps it that way.
    changed_paths = list(changed_paths)
    keys = sorted({key for path in changed_paths for key in encode.path_ancestors(path)})

    def query(conn: sqlite3.Connection) -> dict:
        # An empty changed set intersects nothing, and the store is still opened
        # and aged to say so: the answer is empty because the *input* was, and a
        # caller cannot tell that from an unreachable cache unless the envelope
        # says which.
        items: list[dict] = []
        if keys:
            placeholders = ", ".join("?" for _ in keys)
            sql = (
                f"SELECT {_select(_FULL_COLUMNS)} FROM item WHERE id IN "
                f"(SELECT item_id FROM item_affected WHERE path IN ({placeholders}))"
            )
            params = list(keys)
            if open_only:
                sql += f" AND status IN ({_open_placeholders()})"
                params.extend(OPEN_STATUSES)
            items = _rows(conn, sql + " ORDER BY id", params)
            for item in items:
                item["matched"] = encode.affected_matches(
                    encode.parse_list(item.get("affected")), changed_paths
                )
        return {"items": items, "changed_paths": list(changed_paths), "open_only": open_only}

    return _serve(project_dir, scope=scope, now=now, query=query)


# --- consumer 9: text search within an area ----------------------------------

#: A search term has to contain something a tokenizer would index. A term of pure
#: punctuation survives quoting as an empty phrase, which FTS5 tolerates or not
#: depending on its build — dropping it here keeps that out of the query.
_SEARCHABLE = re.compile(r"[^\W_]", re.UNICODE)


def _match_expression(text: str) -> str | None:
    """``text`` as an FTS5 MATCH expression, or ``None`` if nothing is searchable.

    **Every term is quoted into a phrase, which neutralizes FTS5's query
    operators.** Search text is a caller's arbitrary string — an item title on its
    way to a dedup check — and unquoted it is a small language: ``AND``, ``NOT``,
    ``*``, ``^``, ``:`` and parentheses all mean something there, so a title
    containing one either quietly changes the query's meaning or fails it with a
    syntax error the caller could not have anticipated. Quoting turns each term
    back into the literal the caller meant. Terms are joined by FTS5's implicit
    AND, so a two-word search finds the items carrying both.
    """
    terms = [term for term in text.split() if _SEARCHABLE.search(term)]
    if not terms:
        return None
    return " ".join('"' + term.replace('"', '""') + '"' for term in terms)


def search(
    project_dir: Path, *, scope: str, text: str, now: datetime, area: str | None = None
) -> dict:
    """Full-text search over titles and bodies, optionally scoped to an ``area`` —
    consumer 9 (janitor dedup candidates).

    **Cache-served rather than delegated, because the provider's search is not
    read-your-writes.** An item written seconds ago is not in GitHub's search index
    yet, and the consumer this serves — "is the item I am about to file a
    duplicate of one already here?" — is asked at exactly that moment. A dedup
    check that cannot see the last thing filed is one that lets consecutive
    duplicates through (Data Model §6, QRY-3).

    A store built without FTS5 reports ``unavailable`` rather than returning
    nothing: SQLite's full-text index is a compile-time option, and a search that
    silently answered "no matches" on a Python whose SQLite lacks it would be the
    empty-means-clean failure this module exists to prevent.
    """
    expression = _match_expression(text)
    if expression is None:
        return error("validation", f"nothing searchable in {text!r}")

    def query(conn: sqlite3.Connection) -> dict:
        if not cache.has_fts(conn):
            # States what is known, not why. The absence has more than one cause —
            # a SQLite built without FTS5 is the expected one, but a store whose
            # index was dropped or failed to build reaches here identically, and
            # `has_fts` only ever looked for the table. Naming the likely cause as
            # though it were the observed one is how a reader gets sent to rebuild
            # a perfectly good interpreter, which is exactly the false diagnosis
            # this chunk had to unpick one layer down.
            raise _Declined(
                "the backlog cache has no text index (no FTS5 table), so search cannot run; "
                "a sync rebuilds it where SQLite supports FTS5"
            )
        sql = (
            f"SELECT {_select(_FULL_COLUMNS, prefix='item.')} "
            "FROM item_fts JOIN item ON item.id = item_fts.item_id "
            "WHERE item_fts MATCH ?"
        )
        params: list = [expression]
        if area is not None:
            sql += " AND item.area = ?"
            params.append(area)
        return {
            "items": _rows(conn, sql + " ORDER BY rank, item.id", params),
            "text": text,
            "area": area,
        }

    return _serve(project_dir, scope=scope, now=now, query=query)


# --- consumers 10 and 11: the two hygiene predicates --------------------------


def stale_items(project_dir: Path, *, scope: str, older_than_days: int, now: datetime) -> dict:
    """Open items untouched for longer than ``older_than_days`` — consumer 10.

    The date is the provider's ``updated_at``, which Cache Spec §2.1 moved this
    consumer onto: always present, free, and impossible to forget, where the
    ``reviewed:`` field it replaced needed a write path nobody had. The semantics
    genuinely differ — ``updated_at`` moves on any edit where ``reviewed`` meant
    deliberate re-confirmation — and for a staleness *nag* the derived signal is
    the better of the two, since an item somebody edited last week is not
    neglected whatever its review history says.

    The cutoff is computed from the caller's ``now`` rather than SQLite's, so one
    clock ages the item and the payload both — a test that injects a clock and
    gets the machine's back is measuring two different times.
    """
    if older_than_days < 0:
        return error("validation", f"`older_than_days` must not be negative, got {older_than_days}")
    cutoff = (now - timedelta(days=older_than_days)).isoformat()

    def query(conn: sqlite3.Connection) -> dict:
        return {
            "items": _rows(
                conn,
                f"SELECT {_select(_BRIEF_COLUMNS)} FROM item "
                f"WHERE status IN ({_open_placeholders()}) "
                f"AND {_instant('updated_at')} < {_instant('?')} "
                "ORDER BY updated_at, id",
                (*OPEN_STATUSES, cutoff),
            ),
            "cutoff": cutoff,
            "older_than_days": older_than_days,
        }

    return _serve(project_dir, scope=scope, now=now, query=query)


def unstaged_items(project_dir: Path, *, scope: str, now: datetime) -> dict:
    """Open items carrying no ``stage`` — consumer 11.

    An item with no stage has never been triaged onto the idea → ready ladder,
    which is a different condition from being early on it: ``stage: idea`` is a
    decision, an absent stage is the absence of one. The empty string counts as
    absent alongside NULL — a label facet that decoded to nothing is the same
    silence, and letting one of the two spellings escape would make the finding
    depend on how the item happened to be written.
    """

    def query(conn: sqlite3.Connection) -> dict:
        return {
            "items": _rows(
                conn,
                f"SELECT {_select(_BRIEF_COLUMNS)} FROM item "
                f"WHERE status IN ({_open_placeholders()}) "
                "AND (stage IS NULL OR stage = '') ORDER BY id",
                OPEN_STATUSES,
            )
        }

    return _serve(project_dir, scope=scope, now=now, query=query)


# --- ready work: the candidate set behind `pick` ------------------------------


def _like_prefix(value: str) -> str:
    """``value`` escaped for use as a literal LIKE prefix.

    A repo name cannot contain ``%`` or ``_`` today, so this guards a case that
    cannot arise — which is the point: the alternative is a scope filter whose
    correctness depends on a fact about GitHub's naming rules that nothing here
    checks and no provider is bound by.
    """
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def ready_items(
    project_dir: Path, *, scope: str, now: datetime, include_working: bool = False
) -> dict:
    """Open ``stage: ready`` items, oldest first — the candidate set ``pick`` ranks.

    This is the query that discharges `pick`'s cost problem. The predicate it
    replaces was a paginated full scan of every open issue on every invocation,
    measured at ~12.4s against ~209 issues; here it is one indexed read of local
    rows, and `pick`'s remaining network cost is the blocker fan-out alone, taken
    lazily and bounded by the caller's limit.

    **What is NOT here is the point of it.** There is no blocker predicate: a
    blocker may live in another repo, this store holds exactly one, and a cached
    edge could record only that a dependency existed — never whether it is still
    open. `pick` reads dependencies live and this query deliberately cannot help
    it, which is why no table here holds them.

    **``working_branch`` populated means someone is on it**, so such items are out
    of the candidate set by default. There is no expiry: the branch's own commit
    history is the activity signal, and `pick` surfaces the branch name so a human
    judges whether a three-week-old branch is abandoned. Ageing the branch inside
    this query would put a git call — against a ref in a possibly-different,
    possibly-unfetched repo — inside the hot path this query exists to empty, and
    would rebuild the stored-expiry policy the branch field replaced. The
    asymmetry backs the default: a wrongly-excluded item costs one
    ``include_working=True`` re-run, a wrongly-included one costs two people one
    item.

    ``include_working=True`` widens the set rather than inverting it — the excluded
    items are added back, each still carrying its ``working_branch``, because a
    caller asking to see contested work needs to see who it is contested with.

    **Open-but-redirected items are dropped**, which is why this is the one
    listing query that reads bodies. An item merged away carries ``superseded_by``
    in its block and stays briefly open — the window between a merge's redirect
    write and its close — and offering it as ready work sends someone to build
    against a record that has already moved. The block is the only place that
    fact lives, so the body has to come back with the row; the set is small
    (``stage: ready`` alone), so this is cheap where it would not be on the
    corpus-wide listings.
    """

    def query(conn: sqlite3.Connection) -> dict:
        # **Scoped to `scope`, unlike every other query here, and the asymmetry is
        # deliberate.** The `item` table has no scope column — the store holds one
        # repo by design (Cache Spec F4) — so the other consumers read it whole and
        # `_serve` uses `scope` only to age the answer. `pick` cannot afford that
        # assumption, because it hands each candidate's issue *number* to a live
        # blocker read against the caller's owner/repo: a row from another scope
        # would be judged against whatever issue this repo happens to have at that
        # number, and a blocked item could come back clear. That is the QRY-2
        # negative failing by a second route, so the predicate is applied rather
        # than assumed. Ids are canonical (`owner/repo#number`) by construction, so
        # the prefix match is exact.
        sql = (
            f"SELECT {_select(_FULL_COLUMNS)} FROM item "
            f"WHERE id LIKE ? ESCAPE '\\' "
            f"AND status IN ({_open_placeholders()}) AND stage = ?"
        )
        if not include_working:
            sql += " AND (working_branch IS NULL OR working_branch = '')"
        # Oldest first, which is the tie-break `pick` ranks on. Ordered as an
        # instant rather than as a string for the reason `_instant` records: one
        # moment has two spellings and the lexicographic answer between them is
        # not the chronological one.
        rows = _rows(
            conn,
            sql + f" ORDER BY {_instant('created_at')}, id",
            (_like_prefix(scope) + "#%", *OPEN_STATUSES, encode.READY_STAGE),
        )
        return {
            "items": [r for r in rows if not encode.parse_block(r.get("body")).superseded_by()],
            "include_working": include_working,
        }

    return _serve(project_dir, scope=scope, now=now, query=query)


# --- consumers 5, 7, 14 and 15: resolution through the alias table -------------


def resolve(
    project_dir: Path,
    *,
    scope: str,
    id_raw: str,
    now: datetime,
    default_owner: str | None = None,
) -> dict:
    """Resolve any id spelling — live, aliased, or historical — to the item it
    names. Consumers 5, 7, 14 and 15.

    Four consumers, one query, because they ask four questions of the same lookup:
    *does this id resolve at all* (5, the dangling-id check), *what is its status*
    (7, the PR reviewer's closes/status disagreement), *is it dead* (14, the
    ``dead-why`` probe), and *is it live and how long since it moved* (15,
    ``stalled-transition``). Splitting them would be four resolutions of one id.

    **This is the defect Cache Spec §4 rule 3 names, not a convenience.** A stored
    reference — an item's ``related: [owner/repo#249, …]`` — parsed at read time
    as live provider coordinates means a provider migration has to rewrite every
    edge in the graph, and a missed rewrite breaks it silently, since the citation
    still *looks* like a valid id. Resolved through the alias table those strings
    keep working untouched, because the migrated record carries the old id as an
    alias.

    The resolution order is deterministic and reported in ``via``, never a silent
    guess:

    1. **The stored alias spelling** — a hand-minted ``PFX``, or a fully tagged
       ``github:owner/repo#249``. An exact, uniqueness-checked match outranks
       reading the same token as a live coordinate, which is the precedence
       ``core.resolve_ref`` documents for the digit-suffix ambiguity (``ADR-12``
       is both a PFX and the shell ``repo-number`` spelling). The **order** is
       kept identical so the two resolvers cannot disagree about which reading
       wins. They are not identical in **matching**: this is an exact SQL
       comparison, while the live resolver's label search is case-insensitive, so
       ``bkl-7m4q`` resolves there and misses here. Narrow and worth stating
       rather than implying parity — a stored alias is written once by the
       importer in the case the source used, and a human retyping one in a
       different case is the case that diverges.
    2. **The live id**, once the spelling normalizes.
    3. **The untagged historical citation** — that same canonical id carried as
       *someone's* alias. This is the migration case, and the reason the alias
       index derives an untagged ``ref`` at write time.
    4. **The redirect** — ``superseded_by`` followed to the survivor of a merge or
       transfer, bounded and cycle-guarded by ``ids.resolve_redirect``.

    An id claimed by two items is an ``alias_collision`` error rather than a pick:
    the §5 uniqueness invariant has broken, and choosing one would be a resolution
    nobody could audit. **A miss is a successful answer**, not an error — it is
    the entire finding for consumer 5 — so an unresolvable id returns ``ok`` with
    ``resolved: false``, and only an unreachable cache is ``unavailable``.
    """
    raw = (id_raw or "").strip()
    if not raw:
        return error("validation", "no ID given")
    # **A bare `#621` is qualified with the store's own scope**, which
    # `normalize_id` alone cannot do — it takes a `default_owner` and still needs
    # a repo, so `#621` fails as "malformed repo". That is the spelling nearly
    # every citation actually uses: this repo's change-log writes 259 bare refs
    # against 5 qualified ones, and `closes: #621` is the shape the PR reviewer's
    # closes/status check reads. Left unqualified, the checks restored on this
    # query would resolve almost nothing and report it as "no such item" — a
    # reader matching nothing, which is the failure the whole cache exists to end.
    #
    # It is unambiguous **because the store holds exactly one repo by design**
    # (Security §3's single-repo scoping), so there is no second candidate for the
    # number to mean. If that ever stops holding, this qualification stops being
    # sound and has to become an error rather than a guess.
    spelled = f"{scope}{raw}" if raw.startswith("#") and "/" in scope else raw

    def query(conn: sqlite3.Connection) -> dict:
        found, via = None, None
        # The alias lookup keeps the caller's own spelling: aliases are stored
        # strings, and a hand-minted `PFX` never wore a scope to begin with.
        claimants = _claimants(conn, "alias", raw)
        if claimants:
            found, via = claimants[0], "alias"

        nid = ids.normalize_id(spelled, default_owner=default_owner)
        if found is None and nid.ok:
            if _item(conn, nid.canonical) is not None:
                found, via = nid.canonical, "id"
            else:
                claimants = _claimants(conn, "ref", nid.canonical)
                if claimants:
                    found, via = claimants[0], "alias"

        if found is None:
            return {
                "requested": raw,
                "resolved": False,
                "id": None,
                "via": None,
                # `normalize_id`'s complaint, when the spelling itself was the
                # problem. "No such item" and "that is not an id" send a reader to
                # two different places.
                "reason": None if nid.ok else nid.message,
            }

        final = ids.resolve_redirect(found, fetch=_redirect_fetch(conn))
        row = _item(conn, final)
        if row is None:
            # Unreachable by construction — an alias row is derived from a stored
            # item and swept with it, the live-id branch has already read the row,
            # and the redirect walk only follows targets it found. Guarded anyway
            # because the alternative to a guard here is not a wrong answer, it is
            # an `AttributeError` crossing the module boundary as a stack trace,
            # which is the one thing this layer promises never to do.
            log_diag(f"backlog cache resolved {raw!r} to {final!r}, which it does not hold")
            raise _Declined(f"the backlog cache resolved {raw!r} to an item it does not hold")
        dangling = encode.parse_block(row.get("body")).superseded_by()
        return {
            "requested": raw,
            "resolved": True,
            "id": row["id"],
            # How the FIRST match happened; the redirect, if one was followed, is
            # reported beside it rather than overwriting it. A consumer chasing a
            # bad edge needs to know both which spelling matched and that it then
            # moved.
            "via": via,
            "redirected_from": found if final != found else None,
            "status": row["status"],
            # Dead is the complement of the open set, taken from the same single
            # source of truth the open queries use rather than a list of terminal
            # statuses written out again here.
            "dead": row["status"] not in OPEN_STATUSES,
            "stage": row["stage"],
            "area": row["area"],
            "title": row["title"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            # A redirect target this store does not hold: the item says it was
            # superseded and the survivor is not here. Reported rather than
            # followed, because following it would resolve to nothing, and reading
            # that as "no such item" would lose the redirect the body plainly
            # records.
            "unresolved_redirect": dangling if dangling and _item(conn, dangling) is None else None,
        }

    return _serve(project_dir, scope=scope, now=now, query=query)


def _claimants(conn: sqlite3.Connection, column: str, value: str) -> list[str]:
    """Item ids claiming ``value`` in the alias index, by stored spelling
    (``alias``) or by untagged ref (``ref``). Two claimants is a reported
    collision, never a pick.

    ``column`` is one of two literals chosen by this module and never a caller's
    string, which is the only reason interpolating it is safe — both call sites
    pass a constant."""
    rows = conn.execute(
        f"SELECT item_id FROM item_alias WHERE {column} = ? ORDER BY item_id", (value,)
    ).fetchall()
    claimants = [row[0] for row in rows]
    if len(claimants) > 1:
        raise _Reported(
            error(
                "alias_collision",
                f"{value!r} resolves to {len(claimants)} items "
                f"({', '.join(claimants)}) — alias uniqueness violated",
            )
        )
    return claimants


def _item(conn: sqlite3.Connection, canonical: str) -> dict | None:
    row = conn.execute(
        f"SELECT {_select(_FULL_COLUMNS)} FROM item WHERE id = ?", (canonical,)
    ).fetchone()
    return dict(row) if row else None


def _redirect_fetch(conn: sqlite3.Connection):
    """The ``superseded_by`` reader :func:`ids.resolve_redirect` walks with.

    **Stops at the last item this store holds.** A target the cache does not have
    is not followed, because following it would land the resolution on nothing and
    lose the source item that did resolve; the dangling target is reported on the
    payload instead. The normalization is not optional either — a hand-written
    ``superseded_by`` may carry any accepted spelling, and an unnormalized one
    would simply fail to match a stored id and look like the end of the chain."""

    def fetch(canonical: str) -> str | None:
        row = conn.execute("SELECT body FROM item WHERE id = ?", (canonical,)).fetchone()
        if row is None:
            return None
        target = encode.parse_block(row[0]).superseded_by()
        if not target:
            return None
        nid = ids.normalize_id(target)
        if not nid.ok or _item(conn, nid.canonical) is None:
            return None
        return nid.canonical

    return fetch
