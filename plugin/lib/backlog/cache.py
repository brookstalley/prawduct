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
knows nothing about any **transport** — it is handed already-decoded rows and
never reaches a network. That is the honest form of the claim: it does read two
provider-neutral helpers out of ``encode`` (the block's list format, and the
status vocabulary by way of ``cachequery``), because those are the single home of
a *format*, not of a provider. Should that dependency grow as the query surface
does, the provider-neutral half of ``encode`` wants its own module rather than
this docstring wanting a further softening. ``sync.py`` is the only module
holding both a transport and a store; ``cachequery.py`` reads and never writes.
Errors are return values per project-preferences: nothing here raises across the
boundary.
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
SCHEMA_VERSION = 7

STORE_SUBDIR = "prawduct"
STORE_BASENAME = "backlog-cache.sqlite3"

# How long a writer waits on another writer's lock before giving up. Long enough
# to absorb a whole-portfolio upsert transaction (the longest write this store
# takes), short enough that a wedged holder surfaces as a reported `unavailable`
# rather than an agent that appears to hang — reads degrade, they never block.
BUSY_TIMEOUT_MS = 5_000

# The `item` columns, in schema order. Every one is a projection of a query some
# consumer actually asks, and adding one without a serving query is the defect
# this tuple exists to make visible.
#
# The claim used to read "there are no dead fields here" as a flat assertion, and
# it was false at the time it was written: `etag` sat in this tuple with no
# producer and no consumer. A comment asserting a property of its own design is
# worth exactly what the tree makes true, so it is now stated as the rule the
# tuple enforces rather than as a fact about the moment.
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
    "working_branch",
    "fetched_at",
)

# `affected` and `working_branch` are read by the change-overlap intersection
# (`item_affected` below) and by ready-work's working-branch exclusion.
#
# **`tags` was here and is gone**, and the removal is the no-dead-fields rule
# being applied rather than argued around. It shipped with its justification
# stated as *not* a consumer query: it was carried because rebuild-equivalence
# doubles as the provider-adequacy test, so a field the cache never stores is one
# that test never exercises. Its own comment named the trigger — the first
# release of the query surface that ships no cache-served tag query takes the
# column — and that is this one: every tag read there is, `list --tag`, is served
# **live** off the provider's label filter, and none of the enumerated consumers
# asks about a tag. Two things make removal the cheap side of the trade rather
# than the brave one: a cache is rebuildable, so re-adding a column later costs a
# version bump and a re-fetch rather than a migration; and the adequacy claim it
# backed is the weakest one available for this field, since `tags` → labels is
# the mapping every candidate provider satisfies most trivially, and the live
# `--tag` filter exercises it end to end anyway.

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
        working_branch TEXT,
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
    # The alias index — Cache Spec §4 rule 3's "all resolution goes through the
    # alias table", made a table so the resolution is a lookup rather than a scan
    # that parses every body.
    #
    # Same derived-index shape as `item_affected` and `item_fts`: re-derived from
    # the stored `item.body` in the same transaction, never written on its own, so
    # it is not a second home for the fact. The input is the body rather than a
    # column of its own because `id_aliases` is a block field and the block is
    # what a rebuild reproduces verbatim — a parallel column would be a second
    # spelling that could drift from it.
    #
    # **No UNIQUE on `alias`, deliberately.** Alias uniqueness is an integrity
    # constraint (Data Model §5), not a storage one, and a store that refused to
    # hold a violation could not report it: a second claimant has to be *visible*
    # as `alias_collision` rather than silently dropped or crashing the sync that
    # mirrors it. The composite key indexes `alias` on its own by prefix, so the
    # lookup by the stored spelling needs no further index.
    #
    # **`ref` is the untagged canonical id a provider alias carries**, NULL for a
    # hand-minted PFX (which has no provider coordinates). It exists because the
    # two ends of a resolution are spelled differently on purpose: an alias is
    # stored tagged (`github:owner/repo#249` — Cache Spec §4, since
    # `owner/repo#number` is not GitHub-unique), while a historical citation in a
    # change-log or a commit message is written untagged. Matching the untagged
    # one against the tagged column would take `LIKE '%:' || ?`, whose leading
    # wildcard no index can serve — the same unindexable direction
    # `item_affected` exists to invert, and inverted the same way: derive the
    # equality-matchable key at write time. Two providers' aliases sharing one
    # untagged ref both come back, which is the honest answer — that citation
    # genuinely is ambiguous, and the tag is what lets a caller say which it
    # meant.
    """
    CREATE TABLE item_alias (
        alias   TEXT NOT NULL,
        ref     TEXT,
        item_id TEXT NOT NULL,
        PRIMARY KEY (alias, item_id)
    )
    """,
    "CREATE INDEX item_alias_ref ON item_alias(ref)",
    # **A `comment` table stood here, and its own trigger fired.** It was kept when
    # `tags` went on the reasoning that nothing forbade a comment-reading consumer
    # from arriving — with the trigger written down: *if the consumer surface
    # settles with no comment-reading query, this table is dead weight and goes*.
    # The surface has now settled, at plan completion, with none. It had no writer
    # either, so it could only ever have answered a consumer with an empty set,
    # which is the silent-empty failure this store exists to prevent.
    #
    # **`item.etag` went with it, for a sharper reason.** Its intended producer was
    # retired by this same work: the per-item validator was deferred to "a
    # decision-path read that issues a single-item request", and `pick` instead
    # revalidates through the *list* validator on `cursor.etag` — so the read that
    # would have populated it was never built. `sync` wrote `None` into it on every
    # row. A later builder wiring a conditional single-item request against it would
    # miss on every request and see something that looked like it was working.
    # (`cursor.etag` is a different column and is live — it is the list validator
    # the incremental sync's 304 rides on.)
    # **A `relationship` table stood here and is gone**, and it is worth saying why
    # rather than leaving the absence to be noticed and re-added.
    #
    # It was the natural home for blocker edges, and blocker edges are the one
    # thing ready-work reads that this store must never answer. A blocker may live
    # in a *different* repo; this cache holds exactly one repo by design, so a
    # cached edge could only ever record that a cross-repo blocker existed, never
    # whether it is still open. `pick` therefore reads dependencies live, and a
    # stale store must not be able to let a blocked item through — the negative
    # this project asserts directly rather than assumes.
    #
    # So the table could not gain the consumer it was shaped for, and an empty
    # table shaped like the answer is worse than no table: the next builder wires
    # the fan-out to it and the cross-repo case fails silently, which is the one
    # failure mode that costs two people one item. The no-dead-fields rule and the
    # correctness argument point the same way here.
    # `coverage_confirmed_at` is the local stamp of the last sync that CONFIRMED
    # this scope — which includes a not-modified sync, the one that reads nothing
    # and writes no rows. It was `fetched_at` (the stamp of the sync that wrote
    # the row) through schema v4, and that column was correct only while every
    # sync rewrote every row. See `_write_cursor` and `confirm_coverage` for why
    # the widening matters more than the rename.
    """
    CREATE TABLE cursor (
        scope                 TEXT PRIMARY KEY,
        since                 TEXT,
        etag                  TEXT,
        coverage_confirmed_at TEXT
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
        # **Only a missing module is a degradation; anything else is a broken
        # build.** FTS5 is a compile-time SQLite option, so "no such module" is a
        # fact about this Python that the store legitimately works around. Every
        # other DDL failure here means the schema did not come out as written, and
        # treating those alike is how a half-dropped store once reported itself as
        # a SQLite without full-text search — a false diagnosis that sends whoever
        # reads it to rebuild their interpreter.
        if "no such module" not in str(exc).lower():
            raise
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
        survivors = _drop_objects(conn)
        if survivors:
            # Building a fresh schema over a half-dropped one produces a store
            # that is part old and part new, and reports success. Refusing leaves
            # the previous store intact and says so, which a rebuild-on-next-open
            # can still recover from.
            raise sqlite3.OperationalError(
                f"the backlog cache could not be cleared; {', '.join(survivors)} survived"
            )
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


def _drop_objects(conn: sqlite3.Connection) -> list[str]:
    """Drop every table and index, leaving an empty database in place. Returns
    whatever survived — empty on success.

    Dropping in place rather than unlinking the file keeps other worktrees' open
    connections valid — unlinking would leave them reading a store with no
    directory entry, which is the shape that turns a rebuild here into a silent
    empty result somewhere else.

    **Virtual tables go first, and the order is load-bearing rather than tidy.**
    ``sqlite_master`` lists an FTS5 table *after* its own shadow tables
    (``item_fts_data``, ``…_config``, …), so a loop that simply walks that
    listing drops the shadows first — and FTS5's constructor reads
    ``item_fts_config`` to instantiate, so the virtual table it then reaches can
    no longer be opened at all: ``vtable constructor failed``. What it leaves
    behind is worse than a failure, because it still *looks* like success — a
    surviving ``item_fts`` entry that :func:`has_fts` reports as present and every
    query against it raises on. Dropped in this order the shadows disappear with
    their table and never have to be named.

    Failures are collected rather than swallowed. ``IF EXISTS`` already covers the
    only benign case (an object something else disposed of on the way past), so an
    error that still reaches here is real, and the caller must not build a fresh
    schema on top of a half-dropped one."""
    objects = conn.execute(
        "SELECT name, type FROM sqlite_master "
        "WHERE type IN ('table','index') AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    virtual = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND sql LIKE 'CREATE VIRTUAL TABLE%'"
        ).fetchall()
    }
    ordered = sorted(objects, key=lambda row: row[0] not in virtual)
    for name, kind in ordered:
        verb = "TABLE" if kind == "table" else "INDEX"
        try:
            conn.execute(f'DROP {verb} IF EXISTS "{name}"')
        except sqlite3.OperationalError as exc:
            log_diag(f"could not drop {name} from the backlog cache: {exc}")
    return [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type IN ('table','index') AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    ]


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
        _write_aliases(conn, row)


def _write_aliases(conn: sqlite3.Connection, row: dict) -> None:
    """Re-derive one item's ``item_alias`` rows from its stored body block.

    **Parsed from the body, not from a decoded field handed in beside it**, for
    the same single-input reason :func:`_write_affected` parses from its column:
    the body is what a rebuild reproduces verbatim, so an index derived from it
    can no more disagree with the item than the text index can. The delete is
    unconditional, because an alias removed from a body must stop resolving — a
    surviving row would answer a resolution with a confident wrong item, which is
    worse than answering nothing.

    Malformed entries are dropped rather than indexed. ``id_aliases`` is
    hand-editable text, and an entry that is neither a hand-minted ``PFX`` nor a
    tagged provider id (Cache Spec §4) is a typo; indexing it would let the typo
    claim a resolution.

    A tagged entry also lands its untagged canonical id in ``ref``, which is what
    lets an untagged historical citation resolve by equality — see the table's own
    comment for why that key is derived here rather than matched for at read time.
    """
    from .encode import parse_block  # noqa: PLC0415 — lazy, matches the import shape above
    from . import ids  # noqa: PLC0415

    item_id = row.get("id")
    conn.execute("DELETE FROM item_alias WHERE item_id = ?", (item_id,))
    for alias in parse_block(row.get("body")).id_aliases():
        if not ids.is_alias_token(alias):
            continue
        tagged = ids.parse_provider_alias(alias)
        conn.execute(
            "INSERT OR IGNORE INTO item_alias (alias, ref, item_id) VALUES (?, ?, ?)",
            (alias.strip(), tagged[1] if tagged else None, item_id),
        )


def _write_affected(conn: sqlite3.Connection, row: dict) -> None:
    """Re-derive one item's ``item_affected`` rows from its ``affected`` column.

    **Parsed from the column, not from a second field on the row**, so the index
    and the value it indexes have exactly one input and cannot drift apart. The
    delete is unconditional: an item whose paths were removed must lose its
    index rows, and an upsert that only ever inserted would leave the old set
    matching forever — the failure mode is a stale *positive*, which is worse
    than a miss because it reads as a confident answer.
    """
    # `parse_list` is a pure block-list *format* helper, not provider knowledge,
    # so reading the column through it does not breach this module's
    # provider-neutrality — and `cachequery.py` already reaches into `encode` for
    # the same class of helper. Parsing it inline instead would put a second
    # spelling of the `[a, b]` format here, which is the drift the single-input
    # rule above exists to prevent.
    from .encode import parse_list  # noqa: PLC0415 — lazy, matches cachequery's import shape

    item_id = row.get("id")
    conn.execute("DELETE FROM item_affected WHERE item_id = ?", (item_id,))
    for path in parse_list(row.get("affected")):
        conn.execute(
            "INSERT OR IGNORE INTO item_affected (item_id, path) VALUES (?, ?)",
            (item_id, path),
        )


def _delete_items(conn: sqlite3.Connection, item_ids: list[str], *, fts: bool) -> int:
    """Remove items and every derived row that hangs off them; return how many
    rows were **actually** removed.

    Every index the store keeps has to be swept here, or the item disappears from
    the table a reader lists while still answering a text search or a
    changed-file intersection — a stale positive wearing the shape of a hit.

    The count is `rowcount`, not `len(item_ids)`, and the difference is not
    cosmetic: most out-of-scope ids in a sync window are ordinary repo issues
    that were never cached at all, so counting candidates would report an
    eviction on every sync of any repo that has non-prawduct issues — a number
    that looks like the cache shedding items when nothing happened."""
    removed = 0
    for item_id in item_ids:
        removed += conn.execute("DELETE FROM item WHERE id = ?", (item_id,)).rowcount
        conn.execute("DELETE FROM item_affected WHERE item_id = ?", (item_id,))
        conn.execute("DELETE FROM item_alias WHERE item_id = ?", (item_id,))
        if fts:
            conn.execute("DELETE FROM item_fts WHERE item_id = ?", (item_id,))
    return removed


def apply_incremental(
    conn: sqlite3.Connection,
    rows: list[dict],
    *,
    scope: str,
    since: str,
    etag: str | None,
    fetched_at: str,
    evict: list[str] | None = None,
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
    construction rather than by expiry.

    ``evict`` names ids seen in this window that are **no longer items** — an
    issue whose block and labels were stripped. It rides the same transaction as
    the upserts for the same reason the watermark does: a window is applied whole
    or not at all, and a half-applied one leaves the store asserting something
    the provider does not. This is not the deletion sweep Cache Spec §6 declines
    to schedule; nothing is searched for here, and the evidence was already in
    the page that was fetched anyway."""
    fts = has_fts(conn)
    try:
        with conn:
            _write_rows(conn, rows, fetched_at=fetched_at, fts=fts)
            evicted = _delete_items(conn, evict or [], fts=fts)
            _write_cursor(conn, scope, since, etag, fetched_at)
    except sqlite3.Error as exc:
        log_diag(f"backlog cache incremental write failed: {type(exc).__name__}: {exc}")
        return error("unavailable", f"the backlog cache write failed ({type(exc).__name__})")
    return ok(
        {
            "written": len(rows),
            "evicted": evicted,
            "fts": fts,
            "scope": scope,
            "since": since,
        }
    )


def absorb_rows(
    conn: sqlite3.Connection,
    rows: list[dict],
    *,
    fetched_at: str,
    evict: list[str] | None = None,
) -> dict:
    """Mirror locally-written rows into the store **without touching the cursor**.

    The adapter's own writes are a staleness source the watermark cannot help
    with: the interval between a write and the next read is a single agent's next
    command, and the store would spend it answering questions about a state this
    process already changed. This is the write side of read-your-writes — the
    property the data model defines the cache by.

    **Why this is a separate function from :func:`apply_incremental` rather than a
    flag on it.** That one writes the watermark *because* it must: a sync window
    and the cursor claiming to cover it are one atomic fact. A mirror is the
    opposite kind of event — evidence about one item and about nothing else. The
    cursor records what a FETCH established, and a mirror is not a fetch: it saw
    one issue because it just wrote it, and learned nothing whatever about the
    other four hundred. Advancing ``since`` would skip everything edited in the
    window it never read; stamping ``coverage_confirmed_at`` would report an age
    the store has not earned, and a store that lies about freshness is worse than
    one that is visibly stale, because visible age is the only signal a consumer
    has. A `write_cursor=False` parameter would put both of those failures one
    typo away, so the safe path is the only path this function has.

    The direction it errs is the safe one: a mirrored store is *more* current than
    its reported age implies, never less.

    ``evict`` drops ids that are no longer items, on the same terms
    :func:`apply_incremental` does — a stale open row is a confident wrong answer
    rather than a gap. Everything commits in one transaction so a reader never
    observes a row without its derived index rows.
    """
    fts = has_fts(conn)
    try:
        with conn:
            _write_rows(conn, rows, fetched_at=fetched_at, fts=fts)
            evicted = _delete_items(conn, evict or [], fts=fts)
    # Wider than the `sqlite3.Error` its siblings catch, and deliberately so.
    # `_write_rows` also re-derives the alias and path indexes, whose `parse_block`
    # / `parse_list` work raises value errors rather than database ones. A sync can
    # afford to let one escape — it is attributed to a sync command the caller
    # chose to run. A mirror cannot: it runs after a provider write has ALREADY
    # landed, so anything escaping here turns a successful write into a failed
    # command and invites the caller to retry a mutation that is already done.
    # The transaction rolls back either way, so the store is unharmed.
    except (sqlite3.Error, ValueError, TypeError, KeyError, AttributeError) as exc:
        log_diag(f"backlog cache mirror write failed: {type(exc).__name__}: {exc}")
        return error("unavailable", f"the backlog cache write failed ({type(exc).__name__})")
    return ok({"written": len(rows), "evicted": evicted, "fts": fts})


def cursor_scopes(conn: sqlite3.Connection) -> list[str]:
    """Every scope this store has a cursor row for — that is, every scope some
    sync has actually covered. Empty on any read failure, which is the safe
    direction: callers treat "no scope" as "not synced" and decline to write.

    The existence of the row is the signal, not its contents: ``since`` is legitimately
    NULL after a rebuild that found no provider timestamp to take, so a caller
    asking "has this scope ever been synced?" cannot ask :func:`get_cursor_state`
    and read the answer off ``since``."""
    try:
        return [row[0] for row in conn.execute("SELECT scope FROM cursor ORDER BY scope")]
    except sqlite3.Error as exc:
        log_diag(f"could not read the backlog cache cursor scopes: {type(exc).__name__}: {exc}")
        return []


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
            conn.execute("DELETE FROM item_alias")
            if fts:
                conn.execute("DELETE FROM item_fts")
            _write_rows(conn, rows, fetched_at=fetched_at, fts=fts)
            _write_cursor(conn, scope, cursor_since, None, fetched_at)
    except sqlite3.Error as exc:
        log_diag(f"backlog cache rebuild failed: {type(exc).__name__}: {exc}")
        return error("unavailable", f"the backlog cache rebuild failed ({type(exc).__name__})")
    # `evicted` is 0 rather than absent: every sync exit emits the same key set,
    # or a consumer reading it works on one path and raises on another. A
    # rebuild evicts nothing because it discarded everything first.
    return ok(
        {
            "written": len(rows),
            "evicted": 0,
            "fts": fts,
            "scope": scope,
            "since": cursor_since,
        }
    )


def _write_cursor(
    conn: sqlite3.Connection,
    scope: str,
    since: str | None,
    etag: str | None,
    confirmed_at: str,
) -> None:
    """Stamp the watermark, its list-query validator, and the coverage stamp.
    **Caller-transactional on purpose** — see :func:`replace_items`. Never call
    this outside a transaction that also contains the rows the watermark claims
    to cover.

    ``since`` and ``etag`` are written together because a validator that outlived
    its ``since`` would be replayed against a *different* query, where it can only
    mislead: it would never match, so every revalidation would pay a full request
    while looking like it was working.

    ``confirmed_at`` is the local instant at which a sync last **confirmed
    coverage** of this scope — "everything the provider had up to here has been
    read". It is what a served payload's visible age is measured from, and it has
    two readers no other stamp can serve. The obvious one: a successful sync of an
    **empty** scope leaves no ``item.fetched_at`` to age, and reporting *never
    synced* for a backlog that is simply empty is a different claim from the true
    one. The load-bearing one: under incremental sync the rows' own stamps stop
    answering the question at all, because only the window gets restamped — see
    :func:`confirm_coverage`, which is the other half of keeping this honest."""
    conn.execute(
        "INSERT OR REPLACE INTO cursor (scope, since, etag, coverage_confirmed_at) "
        "VALUES (?, ?, ?, ?)",
        (scope, since, etag, confirmed_at),
    )


def confirm_coverage(conn: sqlite3.Connection, scope: str, confirmed_at: str) -> dict | None:
    """Record that a sync confirmed this scope's coverage without changing it.
    ``None`` on success, an error envelope on failure.

    **The not-modified sync is a real answer, and this is where it is recorded.**
    A conditional request that comes back 304 has established something specific
    and valuable: the provider has nothing newer than the watermark, so the store
    is *current* — not merely un-refreshed. Returning from that path without
    touching the store, which is what the incremental sync did before this
    existed, meant the cheapest and most common successful sync left no trace, and
    the visible age it should have reset instead kept growing.

    Only the coverage stamp moves. ``since`` did not advance (nothing came back to
    advance it) and its validator is still the one for that query, so rewriting
    either would be a lie about a request that was never made."""
    try:
        with conn:
            conn.execute(
                "UPDATE cursor SET coverage_confirmed_at = ? WHERE scope = ?",
                (confirmed_at, scope),
            )
    except sqlite3.Error as exc:
        log_diag(f"could not stamp backlog cache coverage: {type(exc).__name__}: {exc}")
        return error("unavailable", f"the backlog cache coverage stamp failed ({type(exc).__name__})")
    return None


def optimize(conn: sqlite3.Connection) -> None:
    """Compact the store after a rebuild. Best-effort, never fatal.

    A rebuild empties the tables with ``DELETE`` rather than dropping the file —
    which is what keeps another worktree's open connection valid — so the pages it
    frees stay in the file and FTS5's incremental segments accumulate across every
    rebuild a long-lived clone does. Neither costs correctness, and both are
    self-healing enough that no consumer would ever notice; a rebuild is simply
    the one moment when the store is already being rewritten and nobody is waiting
    on a query, which makes it the cheap moment to do it.

    Failure is logged and swallowed on purpose, and it is the one place in this
    module where that is right: ``VACUUM`` takes an exclusive lock, so a
    concurrent agent's open reader will lose it a race sometimes. A rebuild that
    reported unavailable because it could not tidy up afterwards would fail a
    successful sync for a housekeeping step."""
    try:
        if has_fts(conn):
            conn.execute("INSERT INTO item_fts (item_fts) VALUES ('optimize')")
            conn.commit()
        conn.execute("VACUUM")
    except sqlite3.Error as exc:
        log_diag(f"backlog cache optimize skipped: {type(exc).__name__}: {exc}")


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


def coverage_confirmed_at(conn: sqlite3.Connection, scope: str) -> str | None:
    """When a sync last confirmed this scope's coverage, or ``None`` if none ever
    has.

    Distinct from :func:`oldest_fetched_at`, which ages the *rows*. This ages the
    **coverage** — how recently anything established that the store is level with
    the provider — and it is the number a served payload's visible age is
    measured from (see ``cachequery._freshness``, which explains why the row
    stamps cannot answer it under incremental sync)."""
    try:
        row = conn.execute(
            "SELECT coverage_confirmed_at FROM cursor WHERE scope = ?", (scope,)
        ).fetchone()
    except sqlite3.Error as exc:
        log_diag(f"could not read the backlog cache sync stamp: {type(exc).__name__}")
        return None
    return row[0] if row else None


def oldest_fetched_at(conn: sqlite3.Connection) -> str | None:
    """The oldest ``fetched_at`` in the store, or ``None`` when it is empty.

    The *oldest* rather than the newest deliberately: as a statement about the
    rows, the honest promise is the worst one in the payload."""
    try:
        row = conn.execute("SELECT MIN(fetched_at) FROM item").fetchone()
    except sqlite3.Error as exc:
        log_diag(f"could not read backlog cache age: {type(exc).__name__}")
        return None
    return row[0] if row else None
