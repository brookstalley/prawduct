"""Cache — the persisted read-through store the dormant backlog readers query.

**A cache, never truth.** The provider is the home of every fact here; this
store originates nothing. That claim is mechanical rather than aspirational:
:func:`replace_items` rebuilds the whole content from provider rows, so a field
that does not survive a drop-and-rebuild is a cache-only field — data loss on
rebuild, and a second home for a fact. The same drop/rebuild/compare is also the
provider-adequacy test: a backend the cache rebuilds completely from is a
backend whose mapping is complete.

**Location.** ``<git-common-dir>/prawduct/backlog-cache.sqlite3`` — the same
clone-shared directory the evidence store and the counts snapshot use
(``lib/evidence.py``, ``snapshot.py``), and for the same reasons: one location
every worktree of a clone already shares, **never committed** (it lives inside
``.git``, so there is no ``.gitignore`` contract to get wrong), and isolated
between unrelated repos by construction. Being inside ``.git`` is also what
makes the content-borne-secret concern structural rather than policy: a body
carrying a pasted credential cannot reach a commit from here even with
``add -f``.

**One repo per store.** Entries come from exactly the repo named in
``backlog_service_repo``. Authorization happens at *fetch* time by the fetching
identity, not at *read* time by the reading identity, so a store holding several
repos could let a broad-identity fetch be read back by a narrower one. Holding
one repo makes that exposure vacuous rather than mitigated. Widening this is a
design change (entries scoped to the fetching identity's access set, cross-repo
entries revalidated on read), never a config flag.

**Concurrency is the normal case**, not an edge: several agents across several
worktrees of one clone share this file by construction. WAL plus a busy timeout
are therefore deliberate configuration — without them concurrent access produces
lock errors and corruption rather than a rare interleaving.

**Schema versioning.** The store carries its version in SQLite's native
``PRAGMA user_version``. A mismatch in *either* direction means discard and
rebuild-from-the-provider — never a migration. A cache is derived, so dropping
one costs a re-fetch rather than data, which is exactly why rebuild is the safe
answer here and would not be for the evidence store.

**Layering.** This module owns the connection, the schema and the writes, and
knows nothing about any provider — it is handed already-decoded, provider-neutral
rows. ``sync.py`` is the only module holding both a transport and a store;
``cachequery.py`` reads and never writes. Errors are return values per
project-preferences: nothing here raises across the boundary.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from .core import error, log_diag, ok

# The persisted-format version. A mismatch discards and re-derives; bumped only
# when a store written by another version cannot be read correctly by this one.
#
# **Bump on any column change, including one made before release.** v2 was minted
# for `cursor(etag)` and then `cursor(fetched_at)` was added under the same
# number. Nothing detected it: `_ensure_schema` sees a matching version and so
# never discards, while every `_write_cursor` fails on the missing column — an
# `unavailable` envelope on every sync, permanently, with no self-heal, because
# the one mechanism that would rebuild the store is the version check that just
# said the store was fine. That is not a hypothetical; it happened on this
# machine during the chunk that introduced the column, and read as an empty
# result rather than as an error. "Unreleased, so nobody has an old store" is a
# claim about other people's machines, not about the format.
SCHEMA_VERSION = 4

STORE_SUBDIR = "prawduct"
STORE_BASENAME = "backlog-cache.sqlite3"

# How long a writer waits on another writer's lock before giving up. Long enough
# to absorb a whole-portfolio upsert transaction (the longest write this store
# takes), short enough that a wedged holder surfaces as a reported `unavailable`
# rather than an agent that appears to hang — reads degrade, they never block.
BUSY_TIMEOUT_MS = 5_000

# The `item` columns, in schema order. Every one is a projection of a query some
# consumer actually asks — there are no dead fields here, and adding one without
# a serving query is the defect this tuple exists to make visible.
ITEM_COLUMNS: tuple[str, ...] = (
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
    "tags",
    "working_branch",
    "etag",
    "fetched_at",
)

# `affected` and `working_branch` are read by the change-overlap intersection
# (`item_affected` below) and by ready-work's working-branch exclusion. `tags` is
# the ONE column here whose justification is not a consumer query, and saying so
# is better than letting a reader assume one exists: it is carried because
# rebuild-equivalence doubles as the **provider-adequacy** test — a domain field
# the cache never stores is a field that test never exercises, so a backend
# unable to represent tags would pass it. It is therefore the first column the
# no-dead-fields rule should take if no cache-served tag query ever appears.

_SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE item (
        id         TEXT PRIMARY KEY,
        title      TEXT,
        body       TEXT,
        status     TEXT,
        stage      TEXT,
        area       TEXT,
        effort     TEXT,
        impact     TEXT,
        source     TEXT,
        created_at TEXT,
        updated_at TEXT,
        affected   TEXT,
        tags       TEXT,
        working_branch TEXT,
        etag       TEXT,
        fetched_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX item_status_area ON item(status, area)",
    "CREATE INDEX item_updated_at ON item(updated_at)",
    # The `affected` index — a table, not an index on `item.affected`, and both
    # exist for the same reason `item_fts` exists beside `item.title`/`item.body`.
    #
    # `item.affected` is the verbatim domain value: what the item says, what
    # rebuild-equivalence compares, what a reader sees. It cannot serve the query,
    # though, because the intersection runs entry-contains-changed-file
    # (`plugin/lib` matches `plugin/lib/sync.py`) and phrasing that as
    # `WHERE ? LIKE affected || '%'` puts the variable on the side no index can
    # help. Exploding the list into one row per path lets the caller expand each
    # changed file into its ancestor directories (`encode.path_ancestors`) and
    # match by equality, which this index does serve.
    #
    # Derived from the column in the same transaction, never written
    # independently, so the two can no more disagree than the text index can.
    """
    CREATE TABLE item_affected (
        item_id TEXT NOT NULL,
        path    TEXT NOT NULL,
        PRIMARY KEY (item_id, path)
    )
    """,
    "CREATE INDEX item_affected_path ON item_affected(path)",
    """
    CREATE TABLE comment (
        item_id    TEXT NOT NULL,
        body       TEXT,
        author     TEXT,
        created_at TEXT
    )
    """,
    "CREATE INDEX comment_item ON comment(item_id)",
    """
    CREATE TABLE relationship (
        src  TEXT NOT NULL,
        kind TEXT NOT NULL,
        dst  TEXT NOT NULL,
        PRIMARY KEY (src, kind, dst)
    )
    """,
    """
    CREATE TABLE cursor (
        scope      TEXT PRIMARY KEY,
        since      TEXT,
        etag       TEXT,
        fetched_at TEXT
    )
    """,
)

# Full-text search is a compile-time SQLite option, not a guarantee. When it is
# missing the store is still fully functional for every other consumer, so this
# is created separately and its absence is *reported* rather than fatal — a
# search that cannot run must say so, never return an empty result set.
_FTS_STATEMENT = "CREATE VIRTUAL TABLE item_fts USING fts5(item_id UNINDEXED, title, body)"


def cache_path(project_dir: Path) -> Path | None:
    """The clone-shared cache path, or ``None`` outside a git work tree.

    Keyed off ``--git-common-dir`` so every worktree of a clone shares one store
    (mirrors ``evidence.store_path`` and ``snapshot.snapshot_path``, so the
    location rule keeps a single home). ``None`` when ``project_dir`` is not in a
    git work tree — the caller reports unavailable, never crashes."""
    from .. import gitstate  # noqa: PLC0415 — lazy: only the resolver needs git

    common = gitstate.git_common_dir(project_dir)
    if common is None:
        return None
    return common / STORE_SUBDIR / STORE_BASENAME


def _configure(conn: sqlite3.Connection) -> None:
    """WAL + busy timeout: the deliberate concurrency configuration.

    WAL lets readers proceed while a writer holds the store, which is what makes
    several agents on one clone workable; the busy timeout bounds how long a
    second writer waits before the call reports unavailable. ``synchronous`` is
    NORMAL rather than FULL because this store is rebuildable — the crash window
    it accepts costs a re-fetch, not data.

    **The WAL switch does not honour the busy timeout, so it is retried by hand.**
    Changing journal mode takes an exclusive lock and SQLite returns `SQLITE_BUSY`
    immediately rather than invoking the busy handler for it — so two processes
    opening a fresh store at the same instant cannot both win, and the loser would
    otherwise report the store unavailable at the exact moment concurrency is
    supposed to be working. WAL is a persistent property of the file, so the loser
    only has to wait for the winner: re-read the mode, and if it is now WAL there
    is nothing left to do."""
    conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
    _enable_wal(conn)
    conn.execute("PRAGMA synchronous=NORMAL")


def _enable_wal(conn: sqlite3.Connection) -> bool:
    """Put the store in WAL mode, tolerating a concurrent opener's exclusive lock.

    Returns whether WAL is in force. A store that never reaches WAL still works —
    it just serializes readers against writers — so this reports rather than
    fails: losing concurrency is a degradation, not a corruption."""
    for attempt in range(5):
        try:
            row = conn.execute("PRAGMA journal_mode=WAL").fetchone()
            if row and str(row[0]).lower() == "wal":
                return True
        except sqlite3.OperationalError:
            pass  # another connection holds the switch; it sets WAL for us
        time.sleep(0.05 * (attempt + 1))
    row = conn.execute("PRAGMA journal_mode").fetchone()
    if row and str(row[0]).lower() == "wal":
        return True
    log_diag("backlog cache could not enter WAL mode; concurrent access will serialize")
    return False


def _schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("PRAGMA user_version").fetchone()
    return int(row[0]) if row else 0


def has_fts(conn: sqlite3.Connection) -> bool:
    """Whether this store has a usable full-text index.

    False means this Python's SQLite was built without FTS5 — a fact a text
    search must surface as unavailable rather than absorb into an empty
    result."""
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='item_fts'"
    ).fetchone()
    return row is not None


def create_schema(conn: sqlite3.Connection) -> bool:
    """Create every table and stamp the version, inside the caller's transaction.

    Returns whether the full-text index was created; a store without it is still
    complete for every non-search consumer. The caller owns the transaction
    because creating the schema and stamping the version have to land together —
    a store carrying tables but not its version would be rebuilt from scratch by
    the next opener, and one carrying its version but not its tables would be
    read as empty."""
    for statement in _SCHEMA_STATEMENTS:
        conn.execute(statement)
    fts = True
    try:
        conn.execute(_FTS_STATEMENT)
    except sqlite3.OperationalError as exc:
        fts = False
        log_diag(f"SQLite built without FTS5; text search will report unavailable ({exc})")
    conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    return fts


def _ensure_schema(conn: sqlite3.Connection, path: Path, version: int) -> dict | None:
    """Bring the store to the current schema, safely against other openers.

    **The version is re-read after taking the write lock, and that is the whole
    point of this function.** Two agents opening a fresh store both read version
    0 outside any transaction; without the re-read, the second one would drop and
    recreate the schema the first had already filled, silently destroying its
    rows. ``BEGIN IMMEDIATE`` serializes them, and the loser finds the winner's
    stamped version and does nothing."""
    if version == SCHEMA_VERSION:
        return None
    try:
        conn.execute("BEGIN IMMEDIATE")
        settled = _schema_version(conn)
        if settled == SCHEMA_VERSION:
            conn.execute("COMMIT")
            return None
        if settled != 0:
            log_diag(
                f"backlog cache is schema v{settled}, expected v{SCHEMA_VERSION}; "
                "discarding and rebuilding (a cache is derived, so this loses nothing)"
            )
        _drop_objects(conn)
        create_schema(conn)
        conn.execute("COMMIT")
    except sqlite3.Error as exc:
        log_diag(f"could not build the backlog cache schema at {path.name}: {type(exc).__name__}")
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        conn.close()
        return error("unavailable", "the backlog cache schema could not be built")
    return None


def _drop_objects(conn: sqlite3.Connection) -> None:
    """Drop every table and index, leaving an empty database in place.

    Dropping in place rather than unlinking the file keeps other worktrees' open
    connections valid — unlinking would leave them reading a store with no
    directory entry, which is the shape that turns a rebuild here into a silent
    empty result somewhere else."""
    for name, kind in conn.execute(
        "SELECT name, type FROM sqlite_master "
        "WHERE type IN ('table','index') AND name NOT LIKE 'sqlite_%'"
    ).fetchall():
        # An FTS5 shadow table disappears with its virtual table, and an index on
        # an already-dropped table is already gone — tolerate both.
        verb = "TABLE" if kind == "table" else "INDEX"
        try:
            conn.execute(f'DROP {verb} IF EXISTS "{name}"')
        except sqlite3.OperationalError:
            continue


def open_store(project_dir: Path, *, create: bool = False) -> sqlite3.Connection | dict:
    """Open the store, or return an error **envelope** to bubble up.

    With ``create=False`` this is the reader's door: an absent, unreadable, or
    wrong-version store yields ``unavailable`` with a reason naming which — never
    an empty store that a caller would read as "nothing matched". With
    ``create=True`` it is the writer's: a missing store is created, and one whose
    version does not match is **dropped and recreated**, because a cache is
    derived and rebuilding it is always safe.

    The version check accepts no mismatch in either direction. A store written by
    a newer plugin may hold columns this one cannot interpret; one written by an
    older may be missing columns this one requires. Both resolve to rebuild."""
    path = cache_path(project_dir)
    if path is None:
        return error(
            "unavailable",
            "not inside a git work tree, so the backlog cache has no home",
        )
    if not create and not path.exists():
        return error(
            "unavailable",
            "the backlog cache has not been built yet; run `prawduct-hook backlog sync`",
        )
    opened = _open_configured(path, create=create)
    if isinstance(opened, dict):
        # **Only genuine corruption is discarded, never a busy store.** A writer
        # treats an unreadable store as the disposable derived artifact it is,
        # but a lock contended by another agent is not unreadable — deleting on
        # `database is locked` would let one agent destroy another's store at the
        # moment concurrency is working. `_open_configured` marks the difference.
        corrupt = (opened.get("error") or {}).get("details", {}).get("corrupt")
        if not create or not corrupt:
            return opened
        log_diag(f"backlog cache at {path.name} is unreadable; discarding and rebuilding")
        if _discard(path) is not None:
            return opened
        opened = _open_configured(path, create=True)
        if isinstance(opened, dict):
            return opened
    conn, version = opened

    if version == SCHEMA_VERSION:
        return conn
    if not create:
        conn.close()
        if version == 0:
            return error(
                "unavailable",
                "the backlog cache has not been built yet; run `prawduct-hook backlog sync`",
            )
        return error(
            "unavailable",
            f"the backlog cache is schema v{version}, this plugin reads v{SCHEMA_VERSION}; "
            "it will be rebuilt on the next sync",
        )

    failure = _ensure_schema(conn, path, version)
    return conn if failure is None else failure


def _open_configured(
    path: Path, *, create: bool
) -> tuple[sqlite3.Connection, int] | dict:
    """Connect, configure, and read the schema version — or an error envelope.

    Reading the version doubles as the corruption probe: it is the first
    statement to touch the file, so a non-database surfaces here rather than
    later inside a caller's transaction."""
    try:
        if create:
            path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        _configure(conn)
        return conn, _schema_version(conn)
    except sqlite3.OperationalError as exc:
        # Busy, locked, or otherwise transient: the file is fine, this moment is
        # not. Distinguished from corruption because a caller acts on the
        # difference — one is retried, the other is deleted.
        log_diag(f"could not open the backlog cache: {type(exc).__name__}: {exc}")
        return error("unavailable", f"the backlog cache could not be opened ({type(exc).__name__})")
    except sqlite3.DatabaseError as exc:
        log_diag(f"the backlog cache is not a readable database: {type(exc).__name__}: {exc}")
        return error(
            "unavailable",
            f"the backlog cache could not be opened ({type(exc).__name__})",
            details={"corrupt": True},
        )
    except OSError as exc:
        log_diag(f"could not open the backlog cache: {type(exc).__name__}: {exc}")
        return error("unavailable", "the backlog cache directory is not writable")


def _discard(path: Path) -> dict | None:
    """Delete the store and its WAL sidecars. ``None`` on success."""
    for target in (path, path.with_name(path.name + "-wal"), path.with_name(path.name + "-shm")):
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            log_diag(f"could not discard the backlog cache: {type(exc).__name__}: {exc}")
            return error("unavailable", "the unreadable backlog cache could not be discarded")
    return None


def _row_values(row: dict, fetched_at: str) -> tuple:
    values = []
    for column in ITEM_COLUMNS:
        values.append(fetched_at if column == "fetched_at" else row.get(column))
    return tuple(values)


def _write_rows(conn: sqlite3.Connection, rows: list[dict], *, fetched_at: str, fts: bool) -> None:
    """Upsert rows and their text index. **Caller-transactional on purpose** —
    every caller has to decide what else commits alongside these rows, and for
    the incremental path the answer is "the watermark that claims to cover
    them" (see :func:`apply_incremental`)."""
    placeholders = ", ".join("?" for _ in ITEM_COLUMNS)
    columns = ", ".join(ITEM_COLUMNS)
    for row in rows:
        conn.execute(
            f"INSERT OR REPLACE INTO item ({columns}) VALUES ({placeholders})",
            _row_values(row, fetched_at),
        )
        if fts:
            conn.execute("DELETE FROM item_fts WHERE item_id = ?", (row.get("id"),))
            conn.execute(
                "INSERT INTO item_fts (item_id, title, body) VALUES (?, ?, ?)",
                (row.get("id"), row.get("title"), row.get("body")),
            )
        _write_affected(conn, row)


def _write_affected(conn: sqlite3.Connection, row: dict) -> None:
    """Re-derive one item's ``item_affected`` rows from its ``affected`` column.

    **Parsed from the column, not from a second field on the row**, so the index
    and the value it indexes have exactly one input and cannot drift apart. The
    delete is unconditional: an item whose paths were removed must lose its
    index rows, and an upsert that only ever inserted would leave the old set
    matching forever — the failure mode is a stale *positive*, which is worse
    than a miss because it reads as a confident answer.
    """
    from .encode import parse_list  # noqa: PLC0415 — lazy: cache.py is provider-neutral

    item_id = row.get("id")
    conn.execute("DELETE FROM item_affected WHERE item_id = ?", (item_id,))
    for path in parse_list(row.get("affected")):
        conn.execute(
            "INSERT OR IGNORE INTO item_affected (item_id, path) VALUES (?, ?)",
            (item_id, path),
        )


def apply_incremental(
    conn: sqlite3.Connection,
    rows: list[dict],
    *,
    scope: str,
    since: str,
    etag: str | None,
    fetched_at: str,
) -> dict:
    """Upsert one sync window's rows **and advance its watermark**, atomically.

    This is the incremental sibling of :func:`replace_items`, and it exists for
    the same reason: the watermark asserts "everything up to ``since`` is in this
    store", and committing it apart from the rows it covers opens a window where
    that claim is false. A crash inside that window leaves a store permanently
    missing items, because the next sync starts *after* them and no actor is
    guaranteed to re-run this particular transition — the case where being
    idempotent on re-run is not enough and the write has to be atomic instead.

    ``since`` must come from provider timestamps, never the local clock: a
    machine clock running ahead of the provider's would advance the watermark
    past items it never saw, and the loss would be silent and permanent.

    ``etag`` is the **list-query** validator for the query this window came from
    — not an item validator. It is stored beside ``since`` because ``since`` is
    what fixes that query's identity: advance one and the other is void by
    construction rather than by expiry."""
    fts = has_fts(conn)
    try:
        with conn:
            _write_rows(conn, rows, fetched_at=fetched_at, fts=fts)
            _write_cursor(conn, scope, since, etag, fetched_at)
    except sqlite3.Error as exc:
        log_diag(f"backlog cache incremental write failed: {type(exc).__name__}: {exc}")
        return error("unavailable", f"the backlog cache write failed ({type(exc).__name__})")
    return ok({"written": len(rows), "fts": fts, "scope": scope, "since": since})


def replace_items(
    conn: sqlite3.Connection,
    rows: list[dict],
    *,
    scope: str,
    fetched_at: str,
    cursor_since: str | None,
) -> dict:
    """Replace the whole item set **and its watermark** — the rebuild path.

    Atomic against readers: the delete and the inserts share one transaction, so
    no reader ever observes the empty window between them. That window is the
    difference between "the cache is being rebuilt" and "the backlog is empty",
    and only one of those is true.

    **The cursor is written inside that same transaction, and this is the
    correctness argument rather than a tidiness one.** The watermark asserts
    "everything up to `fetched_at` is in this store"; committing it separately
    from the rows it covers creates a window where the claim is false, and a
    crash inside that window leaves a store that will never re-fetch the items it
    is missing — no later actor is guaranteed to re-run *that* transition, so
    idempotent-re-run convergence does not save it. The two writes are one write
    or the guarantee is not a guarantee. Incremental sync inherits the same rule:
    advance the cursor with the upserts it covers, never before them.

    ``cursor_since`` is the watermark the rebuild leaves behind, and it is an
    explicit argument rather than ``fetched_at`` because the two are different
    kinds of timestamp. ``fetched_at`` is a local-clock stamp answering "how old
    is this row?"; the watermark is a **provider** timestamp answering "what have
    I already seen?", and the next incremental sync hands it straight back to the
    provider as ``since``. Deriving it from the local clock would mean a machine
    running fast skips every item the provider stamped in the gap — silently, and
    forever. ``None`` means "no usable watermark" (an empty corpus has no
    provider timestamp to take one from), which correctly routes the next sync
    back through this rebuild path."""
    fts = has_fts(conn)
    try:
        with conn:
            conn.execute("DELETE FROM item")
            conn.execute("DELETE FROM item_affected")
            if fts:
                conn.execute("DELETE FROM item_fts")
            _write_rows(conn, rows, fetched_at=fetched_at, fts=fts)
            _write_cursor(conn, scope, cursor_since, None, fetched_at)
    except sqlite3.Error as exc:
        log_diag(f"backlog cache rebuild failed: {type(exc).__name__}: {exc}")
        return error("unavailable", f"the backlog cache rebuild failed ({type(exc).__name__})")
    return ok({"written": len(rows), "fts": fts, "scope": scope, "since": cursor_since})


def _write_cursor(
    conn: sqlite3.Connection,
    scope: str,
    since: str | None,
    etag: str | None,
    fetched_at: str,
) -> None:
    """Stamp the watermark and its list-query validator. **Caller-transactional
    on purpose** — see :func:`replace_items`. Never call this outside a
    transaction that also contains the rows the watermark claims to cover.

    Both columns are written together because a validator that outlived its
    ``since`` would be replayed against a *different* query, where it can only
    mislead: it would never match, so every revalidation would pay a full request
    while looking like it was working.

    ``fetched_at`` is the local stamp of the sync that wrote this row, and it is
    the *only* place a successful sync of an **empty** scope leaves a trace: with
    no rows there is no ``item.fetched_at`` to age, and reporting "never synced"
    for a backlog that is simply empty is a different claim from the true one."""
    conn.execute(
        "INSERT OR REPLACE INTO cursor (scope, since, etag, fetched_at) VALUES (?, ?, ?, ?)",
        (scope, since, etag, fetched_at),
    )


def get_cursor_state(conn: sqlite3.Connection, scope: str) -> tuple[str | None, str | None]:
    """``(since, etag)`` for the scope — the watermark and the validator of the
    query that produced it. Either may be ``None``: no sync yet, or a sync whose
    response carried no validator. A ``None`` etag means *ask unconditionally*,
    never *nothing changed*."""
    try:
        row = conn.execute(
            "SELECT since, etag FROM cursor WHERE scope = ?", (scope,)
        ).fetchone()
    except sqlite3.Error as exc:
        log_diag(f"could not read the backlog cache cursor: {type(exc).__name__}")
        return None, None
    return (row[0], row[1]) if row else (None, None)


def last_synced_at(conn: sqlite3.Connection, scope: str) -> str | None:
    """When this scope last synced successfully, or ``None`` if it never has.

    Distinct from :func:`oldest_fetched_at`, which ages the *rows*. This ages the
    *sync*, and it is the only answer available for a scope that synced cleanly
    and legitimately holds nothing — where there are no rows to age and "never
    synced" would be a false claim rather than a missing one."""
    try:
        row = conn.execute(
            "SELECT fetched_at FROM cursor WHERE scope = ?", (scope,)
        ).fetchone()
    except sqlite3.Error as exc:
        log_diag(f"could not read the backlog cache sync stamp: {type(exc).__name__}")
        return None
    return row[0] if row else None


def oldest_fetched_at(conn: sqlite3.Connection) -> str | None:
    """The oldest ``fetched_at`` in the store, or ``None`` when it is empty.

    The *oldest* rather than the newest deliberately: an age is a promise about
    the whole payload, and the honest promise is the worst row in it."""
    try:
        row = conn.execute("SELECT MIN(fetched_at) FROM item").fetchone()
    except sqlite3.Error as exc:
        log_diag(f"could not read backlog cache age: {type(exc).__name__}")
        return None
    return row[0] if row else None
