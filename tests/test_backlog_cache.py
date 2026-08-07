"""Tests for lib/backlog/cache.py and sync.py — the W1 store and its writers.

The **consumer query surface** over this store lives in
``test_backlog_cachequery.py``: the queries Cache Spec §2 enumerates, and the
invariants they inherit asserted across all of them at once. What stays here is
the store itself — schema, rebuild, sync, and the one query (consumer 1) that has
to work for any of the rest to mean anything.


The load-bearing test here is **rebuild-equivalence** (``TestRebuildEquivalence``):
drop the store, rebuild it from the provider, compare. Any difference is a
cache-only field — data loss on rebuild and a second home for a fact — and the
same test doubles as the provider-adequacy test, so no separate portability
suite is needed.

The rest pin the four properties that are cheap now and expensive to retrofit:
a schema mismatch **discards and rebuilds** rather than migrating; a cache-served
payload always carries a **visible age**; a reader that cannot reach the store
reports **unavailable rather than empty**; and ``sqlite3`` failures come back as
error envelopes rather than escaping as exceptions.

All offline: no ``gh``, no network.
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.backlog import cache, cachequery, core, query, sync  # noqa: E402
from lib.backlog import encode  # noqa: E402
from lib.backlog.encode import parse_iso  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402

OWNER, REPO = "octo", "repo"
SCOPE = f"{OWNER}/{REPO}"
NOW = datetime(2026, 8, 7, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def fake():
    return FakeGitHub(user={"login": "agent-a", "id": 1})


@pytest.fixture
def repo_dir(tmp_path):
    """A real git work tree — ``cache_path`` resolves through ``--git-common-dir``."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def _file(fake, *, title="cache: the item under test", body="b", **facets):
    result = core.file_item(fake, owner=OWNER, repo=REPO, title=title, body=body, facets=facets)
    assert result["status"] == "ok", result
    return result["data"]["id"]


def _corpus(fake):
    """A fixture corpus with the variety the invariant has to survive: facets set
    and unset, a closed item, a migrated item carrying an alias, a plain
    non-prawduct issue, and a pull request.

    **The aliased item is here so the alias index is not compared vacuously.**
    ``_rebuild_snapshot`` compares ``item_alias``, and a corpus in which no item
    has an alias would compare an empty table to an empty table and report the
    invariant satisfied forever — the shape where a fixture that never reaches the
    subject passes no matter what the subject does."""
    ids = [
        _file(fake, title="cache: first item under test", area="backlog", effort="S", impact="L"),
        _file(fake, title="cache: second item under test", area="critic", stage="ready"),
        _file(fake, title="cache: third item under test", body="no facets at all"),
    ]
    migrated = fake.create_issue(
        OWNER,
        REPO,
        title="cache: a migrated item under test",
        body=encode.compose_body("migrated", {"id_aliases": "[BKL-7M4Q]"}),
        labels=[],
    )
    # An open prawduct item like any other — its block is what makes it in scope —
    # so it belongs in `ids`, or every caller asserting over the open set sees one
    # more item than the corpus admits to having.
    ids.append(f"{OWNER}/{REPO}#{migrated['number']}")
    closed = _file(fake, title="cache: closed item under test", area="backlog")
    assert core.set_status(fake, id_raw=closed, target="shipped")["status"] == "ok"
    fake.create_issue(OWNER, REPO, title="a plain repo issue", body="not ours", labels=[])
    issue = fake.create_issue(OWNER, REPO, title="a pull request", body="pr", labels=[])
    fake._repo(OWNER, REPO).issues[issue["number"]]["pull_request"] = {"url": "http://pr"}
    return ids, closed


def _rebuild(fake, repo_dir, *, now=NOW):
    return sync.full_rebuild(fake, project_dir=repo_dir, owner=OWNER, repo=REPO, now=now)


def _domain_rows(repo_dir):
    """Every stored domain field, ordered — everything except cache metadata.

    ``fetched_at`` is excluded deliberately: it records when the fetch happened,
    not what the provider said, so it is the one column that legitimately differs
    across two rebuilds.

    Item rows only — every row carries an ``id``, which is what the callers that
    key by it rely on. The derived index tables are compared by
    :func:`_rebuild_snapshot` instead, because mixing differently-shaped rows into
    one list makes every caller pay for the one comparison that wants them."""
    path = cache.cache_path(repo_dir)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    columns = [c for c in cache.ITEM_COLUMNS if c != "fetched_at"]
    rows = conn.execute(f"SELECT {', '.join(columns)} FROM item ORDER BY id").fetchall()
    conn.close()
    return [dict(row) for row in rows]


def _rebuild_snapshot(repo_dir):
    """Everything a rebuild has to reproduce: the domain rows **and both derived
    index tables**.

    Neither index is a second home for the fact — each is re-derived from a stored
    column in the same transaction, exactly as the text index is — but they *are*
    stored state, and a rebuild that reproduced the columns while leaving an index
    behind would be a difference this invariant exists to catch. `item_alias` is
    included for precisely the reason `item_affected` is, and leaving it out would
    have let the invariant weaken silently the moment a second index appeared."""
    path = cache.cache_path(repo_dir)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    affected = conn.execute(
        "SELECT item_id, path FROM item_affected ORDER BY item_id, path"
    ).fetchall()
    aliases = conn.execute(
        "SELECT item_id, alias, ref FROM item_alias ORDER BY item_id, alias"
    ).fetchall()
    conn.close()
    return {
        "items": _domain_rows(repo_dir),
        "affected": [dict(row) for row in affected],
        "aliases": [dict(row) for row in aliases],
    }


def _affecting(repo_dir, changed_paths):
    """The items whose `affected` list covers any of `changed_paths`.

    The consumer-1/4 intersection, run the way the schema is shaped for it: each
    changed file is expanded into its ancestor directories and matched by
    **equality**, so `item_affected_path` serves it."""
    keys = sorted({key for path in changed_paths for key in encode.path_ancestors(path)})
    conn = sqlite3.connect(str(cache.cache_path(repo_dir)))
    placeholders = ", ".join("?" for _ in keys)
    rows = conn.execute(
        f"SELECT DISTINCT item_id FROM item_affected WHERE path IN ({placeholders}) "
        "ORDER BY item_id",
        keys,
    ).fetchall()
    conn.close()
    return [row[0] for row in rows]


class TestCachePath:
    def test_path_is_inside_the_git_common_dir_never_the_working_tree(self, repo_dir):
        path = cache.cache_path(repo_dir)

        assert path is not None
        assert ".git" in path.parts, f"{path} must live inside .git so it cannot be committed"
        assert path.name == cache.STORE_BASENAME

    def test_path_is_none_outside_a_git_work_tree(self, tmp_path):
        assert cache.cache_path(tmp_path) is None

    def test_open_reports_unavailable_outside_a_git_work_tree(self, tmp_path):
        result = cache.open_store(tmp_path, create=True)

        assert isinstance(result, dict)
        assert result["error"]["code"] == "unavailable"


#: The schema's fingerprint at the version below. Paired with `SCHEMA_VERSION` by
#: the test that follows, so a schema edit cannot land under an unchanged version.
_SCHEMA_DIGEST = "174c4ed14946"


class TestSchema:
    def test_create_makes_every_table_the_data_model_specifies(self, repo_dir):
        conn = cache.open_store(repo_dir, create=True)

        names = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        conn.close()

        assert {"item", "item_fts", "cursor"} <= names
        # And NOT a blocker table. `pick` reads dependencies live because a
        # blocker can live in a repo this single-repo store does not hold, so a
        # cached edge could record only that one existed — never whether it is
        # still open. An empty table shaped like that answer is what a later
        # builder would wire the fan-out to.
        assert "relationship" not in names

    def test_the_schema_and_its_version_move_together(self, repo_dir):
        """A missed `SCHEMA_VERSION` bump disables its own repair — the version
        check is the same mechanism that would have rebuilt the store, so it sees
        a matching version and never discards. That has happened here once, when
        a `cursor` column was added under an unchanged version and every sync
        failed permanently with no self-heal.

        Nothing else catches it. The Chunk-03 case was caught only because a
        query broke against the stale store; a change that *removes* something no
        query reads — the blocker table did exactly that — leaves the old store
        working and the bump silently optional, which is how the rule erodes into
        a judgement call made freshly each time.

        So the pair is pinned. This test fails on ANY schema edit, deliberately:
        it is asking one question, *did you bump the version*, and the answer is
        to update both numbers below in the same edit that changes the schema.
        """
        digest = hashlib.sha256(
            "\n".join(cache._SCHEMA_STATEMENTS).encode("utf-8")
        ).hexdigest()[:12]

        assert (cache.SCHEMA_VERSION, digest) == (7, _SCHEMA_DIGEST), (
            "the store's schema changed. Bump `SCHEMA_VERSION` and update the "
            "expected pair here — a schema edit under an unchanged version leaves "
            "every existing store unrepairable by the check that approves it"
        )

    def test_wal_and_busy_timeout_are_configured(self, repo_dir):
        conn = cache.open_store(repo_dir, create=True)

        journal = conn.execute("PRAGMA journal_mode").fetchone()[0]
        timeout = conn.execute("PRAGMA busy_timeout").fetchone()[0]
        conn.close()

        assert journal.lower() == "wal"
        assert timeout == cache.BUSY_TIMEOUT_MS

    def test_schema_version_is_stamped_on_create(self, repo_dir):
        conn = cache.open_store(repo_dir, create=True)

        version = conn.execute("PRAGMA user_version").fetchone()[0]
        conn.close()

        assert version == cache.SCHEMA_VERSION

    def test_item_columns_carry_no_dead_fields(self):
        """`assignee` and `reviewed` are absent by decision, not by oversight —
        each lost its serving query (claim retirement; observable-beats-stored),
        and §6's rule is that every column is a query projection."""
        assert "assignee" not in cache.ITEM_COLUMNS
        assert "reviewed" not in cache.ITEM_COLUMNS
        assert {"id", "title", "body", "status", "stage", "area"} <= set(cache.ITEM_COLUMNS)


class TestSchemaMismatch:
    def test_a_schema_ahead_store_is_discarded_and_rebuilt_by_a_writer(self, fake, repo_dir):
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        path = cache.cache_path(repo_dir)
        raw = sqlite3.connect(str(path))
        raw.execute(f"PRAGMA user_version={cache.SCHEMA_VERSION + 1}")
        raw.commit()
        raw.close()

        conn = cache.open_store(repo_dir, create=True)

        assert not isinstance(conn, dict), conn
        assert conn.execute("PRAGMA user_version").fetchone()[0] == cache.SCHEMA_VERSION
        assert conn.execute("SELECT COUNT(*) FROM item").fetchone()[0] == 0
        conn.close()

    def test_a_schema_ahead_store_reports_rather_than_serving_a_reader(self, fake, repo_dir):
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        path = cache.cache_path(repo_dir)
        raw = sqlite3.connect(str(path))
        raw.execute(f"PRAGMA user_version={cache.SCHEMA_VERSION + 1}")
        raw.commit()
        raw.close()

        result = cachequery.open_items(repo_dir, scope=SCOPE, now=NOW)

        assert result["status"] == "error"
        assert result["error"]["code"] == "unavailable"
        assert "schema" in result["error"]["message"]

    def test_an_unversioned_store_is_rebuilt_never_migrated(self, fake, repo_dir):
        """A store carrying tables but no version stamp is rebuilt from scratch.

        This is the version-0 branch; the schema-behind branch below covers
        0 < version < SCHEMA_VERSION, which became reachable at v3."""
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        path = cache.cache_path(repo_dir)
        raw = sqlite3.connect(str(path))
        raw.execute("PRAGMA user_version=0")
        raw.commit()
        raw.close()

        conn = cache.open_store(repo_dir, create=True)

        assert not isinstance(conn, dict), conn
        assert conn.execute("SELECT COUNT(*) FROM item").fetchone()[0] == 0
        conn.close()

    def test_a_store_one_version_behind_is_discarded_and_rebuilt(self, fake, repo_dir):
        """The branch that only became reachable once a second version existed —
        and the one whose absence let a real defect through.

        `cursor.fetched_at` was added to the v2 schema without bumping past v2.
        A store written by the earlier v2 code therefore matched on version, was
        never discarded, and then failed every `_write_cursor` on the missing
        column — an `unavailable` envelope on every sync, forever, because the
        mechanism that would have rebuilt it is the version check that had just
        pronounced it healthy. The store is old-SHAPED here, not merely
        old-numbered, so the assertion is that the column arrives — a test that
        only re-stamped the version would pass against the bug."""
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        path = cache.cache_path(repo_dir)
        raw = sqlite3.connect(str(path))
        raw.execute("DROP TABLE cursor")
        raw.execute("CREATE TABLE cursor (scope TEXT PRIMARY KEY, since TEXT, etag TEXT)")
        raw.execute(f"PRAGMA user_version={cache.SCHEMA_VERSION - 1}")
        raw.commit()
        raw.close()

        conn = cache.open_store(repo_dir, create=True)

        assert not isinstance(conn, dict), conn
        assert conn.execute("PRAGMA user_version").fetchone()[0] == cache.SCHEMA_VERSION
        columns = {row[1] for row in conn.execute("PRAGMA table_info(cursor)")}
        conn.close()
        assert "coverage_confirmed_at" in columns, (
            "the stale-shaped store survived, so every cursor write would fail forever"
        )

    def test_the_v2_shaped_store_that_actually_shipped_is_discarded(self, fake, repo_dir):
        """**The version literal below is deliberate and must not be replaced by
        `cache.SCHEMA_VERSION - 1`.** `2` is a historical fact — the number a
        real store carrying the pre-`fetched_at` cursor was stamped with — not a
        reference to the current constant. Written relatively, this test moves
        with the constant it exists to police and passes no matter how low
        SCHEMA_VERSION sinks; the first version of it did exactly that and
        survived a mutation back to the defect.

        The failure this pins is total and silent: version matches, so the store
        is never discarded, and every `_write_cursor` then fails on the missing
        column — an `unavailable` on every sync, forever, with the self-heal
        gated behind the check that just approved the store."""
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        path = cache.cache_path(repo_dir)
        raw = sqlite3.connect(str(path))
        raw.execute("DROP TABLE cursor")
        raw.execute("CREATE TABLE cursor (scope TEXT PRIMARY KEY, since TEXT, etag TEXT)")
        raw.execute("PRAGMA user_version=2")  # the shape that shipped as v2
        raw.commit()
        raw.close()

        result = _rebuild(fake, repo_dir)

        assert result["status"] == "ok", result
        assert result["data"]["written"] > 0
        conn = cache.open_store(repo_dir, create=False)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(cursor)")}
        conn.close()
        assert "coverage_confirmed_at" in columns

    def test_the_v3_shaped_store_is_discarded_when_the_item_columns_grew(
        self, fake, repo_dir
    ):
        """The same defect one schema on, and the reason `3` is a literal here for
        the same reason `2` is above: it is the number a store carrying the
        pre-`affected` item shape was stamped with, not a reference to the current
        constant. Written as `SCHEMA_VERSION - 1` it would slide forward on every
        future bump and stop policing this shape at all.

        Without the bump the failure is total: version matches, the store is kept,
        and every `_write_rows` then fails on three missing columns — so a sync
        that used to work reports `unavailable` forever, with the rebuild that
        would fix it gated behind the check that just approved the store."""
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        path = cache.cache_path(repo_dir)
        raw = sqlite3.connect(str(path))
        raw.execute("DROP TABLE item")
        raw.execute(
            "CREATE TABLE item (id TEXT PRIMARY KEY, title TEXT, body TEXT, status TEXT, "
            "stage TEXT, area TEXT, effort TEXT, impact TEXT, source TEXT, created_at TEXT, "
            "updated_at TEXT, etag TEXT, fetched_at TEXT NOT NULL)"
        )
        raw.execute("PRAGMA user_version=3")  # the shape that shipped as v3
        raw.commit()
        raw.close()

        result = _rebuild(fake, repo_dir)

        assert result["status"] == "ok", result
        assert result["data"]["written"] > 0
        conn = cache.open_store(repo_dir, create=False)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(item)")}
        conn.close()
        # `tags` was among the columns v4 grew and is deliberately not among v5's:
        # no consumer query read it from the cache, so the no-dead-fields rule
        # took it. The two that stay are the two with serving queries.
        assert {"affected", "working_branch"} <= columns
        assert "tags" not in columns

    def test_a_corrupt_store_reports_unavailable_rather_than_raising(self, repo_dir):
        path = cache.cache_path(repo_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"this is definitely not a sqlite database" * 64)

        result = cache.open_store(repo_dir, create=False)

        assert isinstance(result, dict)
        assert result["error"]["code"] == "unavailable"

    def test_a_corrupt_store_is_rebuilt_by_a_writer(self, fake, repo_dir):
        path = cache.cache_path(repo_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"this is definitely not a sqlite database" * 64)
        _corpus(fake)

        result = _rebuild(fake, repo_dir)

        assert result["status"] == "ok", result
        assert result["data"]["written"] > 0


class TestUnavailableIsNotEmpty:
    def test_an_absent_store_reports_unavailable_never_an_empty_set(self, repo_dir):
        result = cachequery.open_items(repo_dir, scope=SCOPE, now=NOW)

        assert result["status"] == "error"
        assert result["error"]["code"] == "unavailable"
        assert "data" not in result

    def test_a_store_deleted_after_a_build_reports_unavailable(self, fake, repo_dir):
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        cache.cache_path(repo_dir).unlink()

        result = cachequery.open_items(repo_dir, scope=SCOPE, now=NOW)

        assert result["status"] == "error"
        assert result["error"]["code"] == "unavailable"

    def test_a_never_synced_store_reports_rather_than_serving_zero_items(self, repo_dir):
        conn = cache.open_store(repo_dir, create=True)
        conn.close()

        result = cachequery.open_items(repo_dir, scope=SCOPE, now=NOW)

        assert result["status"] == "error"
        assert "never been synced" in result["error"]["message"]

    def test_sqlite_failures_come_back_as_envelopes_not_exceptions(self, fake, repo_dir):
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        conn = cache.open_store(repo_dir, create=True)
        conn.execute("DROP TABLE item")
        conn.commit()

        result = cache.apply_incremental(
            conn, [{"id": "x"}], scope=SCOPE, since=NOW.isoformat(), etag=None,
            fetched_at=NOW.isoformat(),
        )
        conn.close()

        assert result["status"] == "error"
        assert result["error"]["code"] == "unavailable"


class TestVisibleAge:
    def test_every_served_payload_carries_a_non_null_age(self, fake, repo_dir):
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"

        result = cachequery.open_items(repo_dir, scope=SCOPE, now=NOW + timedelta(hours=3))

        assert result["status"] == "ok", result
        assert result["data"]["age_seconds"] is not None
        assert result["data"]["age_seconds"] == pytest.approx(3 * 3600, abs=2)
        assert result["data"]["synced_at"] is not None

    def test_age_is_reported_even_when_the_open_set_is_empty(self, fake, repo_dir):
        closed = _file(fake, title="cache: the only item under test", area="backlog")
        assert core.set_status(fake, id_raw=closed, target="shipped")["status"] == "ok"
        assert _rebuild(fake, repo_dir)["status"] == "ok"

        result = cachequery.open_items(repo_dir, scope=SCOPE, now=NOW + timedelta(hours=1))

        assert result["status"] == "ok", result
        assert result["data"]["items"] == []
        assert result["data"]["age_seconds"] == pytest.approx(3600, abs=2)

    def test_a_synced_but_empty_scope_reports_its_age_not_never_synced(self, fake, repo_dir):
        """"Empty" and "never synced" are different claims, and only the second
        should send an operator off to run a sync. With no rows there is no
        `item.fetched_at` to age, so the cursor's own stamp answers — which is
        the one place a successful sync of an empty scope leaves a trace."""
        assert _rebuild(fake, repo_dir)["status"] == "ok"  # a repo with no items at all

        result = cachequery.open_items(repo_dir, scope=SCOPE, now=NOW + timedelta(hours=2))

        assert result["status"] == "ok", result
        assert result["data"]["items"] == []
        assert result["data"]["age_seconds"] == pytest.approx(2 * 3600, abs=2), (
            "a synced-but-empty store reported as never synced"
        )

    def test_a_never_synced_store_reports_rather_than_serving(self, repo_dir):
        """The other side of the same coin — the empty-store fallback must not
        manufacture an age for a store that has genuinely never been filled. That
        one still refuses to serve, and says which command fixes it."""
        conn = cache.open_store(repo_dir, create=True)
        conn.close()

        result = cachequery.open_items(repo_dir, scope=SCOPE, now=NOW)

        assert result["status"] == "error"
        assert result["error"]["code"] == "unavailable"
        assert "never been synced" in result["error"]["message"]

    def test_the_served_age_is_the_coverage_stamp_not_the_oldest_row(self, repo_dir):
        """**This reverses what the store used to promise, deliberately.**

        The age was `MIN(item.fetched_at)` — the worst row in the payload — which
        was the honest answer while every sync rewrote every row. Incremental sync
        restamps only its window, so that number became the fetch time of the
        least-recently-*edited* item and grew without bound while syncs kept
        succeeding: the setup below is a store that is fully current and would
        have reported itself five hours stale.

        What replaced it is not the newest row either — that would understate
        staleness the other way. It is the coverage stamp: when a sync last
        established that the store is level with the provider, which is the
        question a consumer reading an age is actually asking.

        Asserted through ``cachequery``, the path that serves the age, rather than
        by calling the helper: reading the helper only proves the helper works,
        and the defect worth catching is a server that stops calling it."""
        conn = cache.open_store(repo_dir, create=True)
        cache.replace_items(
            conn,
            [{"id": "a"}],
            scope=SCOPE,
            fetched_at=(NOW - timedelta(hours=5)).isoformat(),
            cursor_since=(NOW - timedelta(hours=5)).isoformat(),
        )
        cache.apply_incremental(
            conn, [{"id": "b"}], scope=SCOPE, since=NOW.isoformat(), etag=None,
            fetched_at=NOW.isoformat(),
        )
        conn.close()

        result = cachequery.open_items(repo_dir, scope=SCOPE, now=NOW)

        assert result["status"] == "ok", result
        assert result["data"]["age_seconds"] == pytest.approx(0, abs=2), (
            "the oldest row's stamp reported a five-hour-old cache that had just synced"
        )

    def test_a_not_modified_sync_resets_the_age(self, fake, repo_dir):
        """The 304 path is where the over-reporting was worst, and it is the
        steady state rather than an edge: a quiet interval means every sync comes
        back not-modified, writes nothing, and — before the coverage stamp — left
        no trace at all, so a store confirmed current one second ago went on
        ageing as if nobody had looked."""
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        # Twice: a rebuild leaves no validator, so the first incremental sync asks
        # unconditionally and is the one that stores one. Only the second can come
        # back not-modified, which is the path under test.
        assert _sync(fake, repo_dir, now=NOW)["status"] == "ok"

        later = NOW + timedelta(hours=6)
        quiet = _sync(fake, repo_dir, now=later)

        assert quiet["status"] == "ok", quiet
        assert quiet["data"]["not_modified"] is True, "the window must be quiet for this test"
        result = cachequery.open_items(repo_dir, scope=SCOPE, now=later)
        assert result["data"]["age_seconds"] == pytest.approx(0, abs=2), (
            "a store the provider just confirmed current reported itself six hours stale"
        )

    def test_a_304_that_cannot_stamp_reports_it_without_failing_the_sync(self, fake, repo_dir):
        """The branch is small and the reason it matters is not: it is the one
        place a *successful* sync says its bookkeeping did not land. The sync did
        succeed — the provider confirmed the store is current — so failing it over
        an unwritten stamp would trade a real success for a housekeeping step. But
        the cost is an age that keeps over-reporting, which is the exact defect
        this stamp exists to fix, so it cannot be silent either."""
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        assert _sync(fake, repo_dir, now=NOW)["status"] == "ok"  # stores the validator

        with mock.patch.object(
            cache,
            "confirm_coverage",
            return_value=core.error("unavailable", "the store is read-only"),
        ):
            quiet = _sync(fake, repo_dir, now=NOW + timedelta(hours=6))

        assert quiet["status"] == "ok", "a good sync must not fail on its bookkeeping"
        assert quiet["data"]["not_modified"] is True
        assert any("coverage stamp" in w for w in quiet["warnings"]), (
            "an age that will keep over-reporting must not be reported silently"
        )

    def test_rows_still_age_a_store_whose_cursor_is_gone(self, repo_dir):
        """The fallback. No writer produces this state — every write path stamps
        the cursor in the same transaction as the rows — so this pins a *reader*
        that must not claim `never synced` about a store whose rows are visibly
        there."""
        conn = cache.open_store(repo_dir, create=True)
        cache.replace_items(
            conn,
            [{"id": "a"}],
            scope=SCOPE,
            fetched_at=(NOW - timedelta(hours=4)).isoformat(),
            cursor_since=(NOW - timedelta(hours=4)).isoformat(),
        )
        conn.execute("DELETE FROM cursor")
        conn.commit()
        conn.close()

        result = cachequery.open_items(repo_dir, scope=SCOPE, now=NOW)

        assert result["status"] == "ok", result
        assert result["data"]["age_seconds"] == pytest.approx(4 * 3600, abs=2)


class TestFullRebuild:
    def test_prawduct_items_are_stored_and_foreign_issues_are_not(self, fake, repo_dir):
        ids, closed = _corpus(fake)

        result = _rebuild(fake, repo_dir)

        assert result["status"] == "ok", result
        stored = {row["id"] for row in _domain_rows(repo_dir)}
        assert stored == set(ids) | {closed}, "plain issues and PRs are not backlog items"

    def test_closed_items_are_stored_so_dead_ids_still_resolve(self, fake, repo_dir):
        _ids, closed = _corpus(fake)
        _rebuild(fake, repo_dir)

        rows = {row["id"]: row for row in _domain_rows(repo_dir)}

        assert closed in rows, "consumers 5 and 14 ask whether an id is dead"
        assert rows[closed]["status"] == "shipped"

    def test_only_open_items_are_served_to_consumer_one(self, fake, repo_dir):
        ids, closed = _corpus(fake)
        _rebuild(fake, repo_dir)

        result = cachequery.open_items(repo_dir, scope=SCOPE, now=NOW)

        served = {item["id"] for item in result["data"]["items"]}
        assert served == set(ids), "consumer 1 asks for the open set"
        assert closed not in served
        assert all(item["title"] and item["body"] is not None for item in result["data"]["items"])

    def test_in_progress_and_submitted_items_count_as_open(self, fake, repo_dir):
        """A live item is any non-terminal status. Filtering on the literal
        ``open`` would drop exactly the items a PR reviewer is looking for, and
        would do it while still reporting success."""
        working = _file(fake, title="cache: the in-progress item under test", area="backlog")
        assert core.set_status(fake, id_raw=working, target="in-progress")["status"] == "ok"
        triage = _file(fake, title="cache: the submitted item under test", area="backlog")
        assert core.set_status(fake, id_raw=triage, target="submitted")["status"] == "ok"
        _rebuild(fake, repo_dir)

        result = cachequery.open_items(repo_dir, scope=SCOPE, now=NOW)

        served = {item["id"] for item in result["data"]["items"]}
        assert working in served, "an in-progress item is live work, not resolved"
        assert triage in served, "a submitted item is awaiting triage, not closed"

    def test_provider_timestamps_are_stored_for_the_date_predicates(self, fake, repo_dir):
        _corpus(fake)
        _rebuild(fake, repo_dir)

        rows = _domain_rows(repo_dir)

        assert rows, "the corpus is not empty, so a green empty set would mean nothing was read"
        assert all(row["created_at"] for row in rows), "consumer 2 filters on creation time"
        assert all(row["updated_at"] for row in rows), "consumers 10 and 15 filter on updated_at"

    def test_a_failed_fetch_leaves_the_previous_store_intact(self, fake, repo_dir):
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        before = _domain_rows(repo_dir)
        fake.set_unreachable(True)

        result = _rebuild(fake, repo_dir)

        assert result["status"] == "error"
        assert _domain_rows(repo_dir) == before, "a half-run rebuild would read as a shrunken backlog"

    def test_rebuilding_twice_is_idempotent(self, fake, repo_dir):
        _corpus(fake)
        _rebuild(fake, repo_dir)
        first = _domain_rows(repo_dir)

        _rebuild(fake, repo_dir, now=NOW + timedelta(hours=1))

        assert _domain_rows(repo_dir) == first

    def test_rows_and_watermark_commit_together_or_not_at_all(self, fake, repo_dir):
        """The watermark claims "everything up to this stamp is in the store".
        If the rows land and the cursor does not — or the reverse — that claim is
        false, and a crash in the gap leaves a store that will never re-fetch
        what it is missing. Forcing the cursor write to fail must roll the rows
        back with it."""
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        before = _domain_rows(repo_dir)
        conn = cache.open_store(repo_dir, create=True)
        conn.execute("DROP TABLE cursor")
        conn.commit()

        result = cache.replace_items(
            conn,
            [{"id": "only-row"}],
            scope=SCOPE,
            fetched_at=NOW.isoformat(),
            cursor_since=NOW.isoformat(),
        )
        conn.close()

        assert result["status"] == "error"
        assert _domain_rows(repo_dir) == before, "the rows rolled back with the failed watermark"

    def test_the_watermark_is_a_provider_stamp_never_the_local_clock(self, fake, repo_dir):
        """The watermark is handed straight back to the provider as ``since`` on
        the next sync, so it has to live in the provider's clock domain. Deriving
        it from the local clock means a machine running fast asks for changes
        after a moment the provider has not reached, and every item stamped in
        the gap is skipped — silently, and permanently, because the watermark
        only moves forward.

        The corpus is stamped well before ``NOW`` precisely so the two clocks
        cannot be confused for one another."""
        _corpus(fake)
        _rebuild(fake, repo_dir)

        conn = cache.open_store(repo_dir, create=False)
        since, _etag = cache.get_cursor_state(conn, SCOPE)
        conn.close()

        # Compared as instants: `...00Z` sorts ABOVE `...00.000001Z` as a string
        # while being the earlier moment, so a string max here would quietly pick
        # the wrong issue and assert against it.
        newest = max(
            parse_iso(i["updated_at"]) for i in fake.list_issues(OWNER, REPO, state="all")
        )
        assert since is not None
        assert since != NOW.isoformat(), "the local clock leaked into the watermark"
        assert parse_iso(since) <= newest, (
            "the watermark ran ahead of the newest thing the provider actually showed us"
        )
        assert parse_iso(since) == newest - sync.CURSOR_OVERLAP, (
            "the watermark should sit one overlap margin behind the newest stamp seen"
        )


class TestRebuildEquivalence:
    """Drop the store, rebuild from the provider, compare.

    A difference means a field lives only in the cache — which is data loss on
    rebuild and a second home for a fact. The same comparison is the
    provider-adequacy test: a backend this rebuilds completely from is a backend
    whose mapping is complete."""

    def test_dropping_and_rebuilding_reproduces_every_domain_field(self, fake, repo_dir):
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        before = _rebuild_snapshot(repo_dir)
        assert before["items"], "an empty corpus would make this invariant vacuously true"
        assert before["aliases"], (
            "the corpus must carry an alias, or the alias index compares empty to empty"
        )

        cache.cache_path(repo_dir).unlink()
        assert _rebuild(fake, repo_dir, now=NOW + timedelta(days=2))["status"] == "ok"

        assert _rebuild_snapshot(repo_dir) == before

    def test_a_field_written_only_into_the_cache_is_caught(self, fake, repo_dir):
        """Red-verify the invariant itself: a cache-only edit must make it fail,
        otherwise the test above passes for the wrong reason."""
        _corpus(fake)
        _rebuild(fake, repo_dir)
        path = cache.cache_path(repo_dir)
        raw = sqlite3.connect(str(path))
        raw.execute("UPDATE item SET area = 'invented-in-the-cache'")
        raw.commit()
        raw.close()
        tampered = _domain_rows(repo_dir)

        _rebuild(fake, repo_dir)

        assert _domain_rows(repo_dir) != tampered


class TestNewDomainFields:
    """`affected` and `working-branch` in the store — and `tags` deliberately not.

    Zero cache-only fields: both stored fields are written on the provider, in the
    body block, so the rebuild-equivalence invariant above stops being trivially
    satisfiable and starts carrying them.

    `tags` is the third field of the same family and the cache does not hold it.
    It has no consumer query — `list --tag` is served live off the provider's
    label filter — so under the every-column-is-a-Q-projection rule it is a dead
    field, and the rule took it. The test below asserts the removal from *both*
    ends, because half of it would be indistinguishable from the field having been
    lost: absent from the store, still present on the provider.
    """

    def _tagged_item(self, fake):
        item_id = _file(fake, title="cache: an item carrying every new field", area="backlog")
        fake.push_branch(OWNER, REPO, "feat/live")
        assert core.update_item(
            fake,
            id_raw=item_id,
            fields={
                "affected": "plugin/lib/backlog, docs/x.md",
                "tags": "perf,api",
                "working-branch": f"{OWNER}/{REPO}@feat/live",
            },
        )["status"] == "ok"
        return item_id

    def test_the_two_with_serving_queries_reach_the_store(self, fake, repo_dir):
        item_id = self._tagged_item(fake)

        _rebuild(fake, repo_dir)

        conn = cache.open_store(repo_dir, create=False)
        row = conn.execute(
            "SELECT affected, working_branch FROM item WHERE id = ?", (item_id,)
        ).fetchone()
        conn.close()
        assert row["affected"] == "[plugin/lib/backlog, docs/x.md]"
        assert row["working_branch"] == f"{OWNER}/{REPO}@feat/live"

    def test_tags_stay_on_the_provider_and_out_of_the_cache(self, fake, repo_dir):
        """Both halves, because either alone would mislead.

        A missing column with the tag also gone would be a field silently lost;
        a tag still filterable with a column still there would be the dead field
        the removal exists to end. The claim is precisely: the cache stopped being
        a reader of tags, and nothing else changed about them."""
        item_id = self._tagged_item(fake)

        _rebuild(fake, repo_dir)

        conn = cache.open_store(repo_dir, create=False)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(item)")}
        conn.close()
        assert "tags" not in columns

        live = query.list_items(fake, owner=OWNER, repo=REPO, filters={"tag": "perf"})
        assert live["status"] == "ok", live
        assert [item["id"] for item in live["data"]["items"]] == [item_id]

    def test_an_item_with_neither_stores_null_not_an_empty_list(self, fake, repo_dir):
        """`[]` and "no value" would be two spellings of one state, and every
        reader would have to know both."""
        item_id = _file(fake, title="cache: an item carrying none of them")

        _rebuild(fake, repo_dir)

        conn = cache.open_store(repo_dir, create=False)
        row = conn.execute(
            "SELECT affected, working_branch FROM item WHERE id = ?", (item_id,)
        ).fetchone()
        conn.close()
        assert row["affected"] is None
        assert row["working_branch"] is None

    def test_they_survive_a_write_drop_rebuild_cycle(self, fake, repo_dir):
        """The Chunk-01 invariant becoming load-bearing rather than trivial."""
        self._tagged_item(fake)
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        before = _domain_rows(repo_dir)
        assert any(row.get("affected") for row in before), (
            "the corpus must exercise the new fields"
        )

        cache.cache_path(repo_dir).unlink()
        assert _rebuild(fake, repo_dir, now=NOW + timedelta(days=2))["status"] == "ok"

        assert _domain_rows(repo_dir) == before

    def test_an_item_intersects_a_changed_file_set(self, fake, repo_dir):
        item_id = self._tagged_item(fake)
        _file(fake, title="cache: an unrelated item nobody changed", area="critic")
        _rebuild(fake, repo_dir)

        assert _affecting(repo_dir, ["plugin/lib/backlog/sync.py"]) == [item_id]
        assert _affecting(repo_dir, ["docs/x.md"]) == [item_id]
        assert _affecting(repo_dir, ["plugin/bin/prawduct-hook"]) == []

    def test_a_sibling_directory_is_not_an_overlap(self, fake, repo_dir):
        """`plugin/lib` must not swallow `plugin/libexec` — a string-prefix match
        would, and it would read as a confident hit rather than as a miss."""
        self._tagged_item(fake)
        _rebuild(fake, repo_dir)

        assert _affecting(repo_dir, ["plugin/lib-other/x.py"]) == []

    def test_removing_a_path_removes_its_index_row(self, fake, repo_dir):
        """An upsert that only ever inserted would leave the old set matching
        forever — a stale *positive*, which reads as an answer rather than as a
        gap."""
        item_id = self._tagged_item(fake)
        _rebuild(fake, repo_dir)
        assert _affecting(repo_dir, ["docs/x.md"]) == [item_id]

        assert core.update_item(
            fake, id_raw=item_id, fields={"affected": "plugin/lib/backlog"}
        )["status"] == "ok"
        _sync(fake, repo_dir, now=NOW + timedelta(hours=1))

        assert _affecting(repo_dir, ["docs/x.md"]) == []
        assert _affecting(repo_dir, ["plugin/lib/backlog/sync.py"]) == [item_id]

    def test_the_index_and_the_column_cannot_disagree(self, fake, repo_dir):
        """Both come from one input — the column — so there is no second field to
        drift out of step with."""
        item_id = self._tagged_item(fake)
        _rebuild(fake, repo_dir)

        conn = cache.open_store(repo_dir, create=False)
        column = conn.execute("SELECT affected FROM item WHERE id = ?", (item_id,)).fetchone()[0]
        indexed = [
            row[0]
            for row in conn.execute(
                "SELECT path FROM item_affected WHERE item_id = ? ORDER BY path", (item_id,)
            ).fetchall()
        ]
        conn.close()
        assert sorted(encode.parse_list(column)) == indexed


class TestFullTextIndex:
    def test_the_index_is_populated_alongside_the_items(self, fake, repo_dir):
        _corpus(fake)
        _rebuild(fake, repo_dir)

        conn = cache.open_store(repo_dir, create=False)
        indexed = conn.execute("SELECT COUNT(*) FROM item_fts").fetchone()[0]
        items = conn.execute("SELECT COUNT(*) FROM item").fetchone()[0]
        conn.close()

        assert indexed == items > 0

    def test_availability_is_reported_so_a_search_can_say_so(self, fake, repo_dir):
        _corpus(fake)

        result = _rebuild(fake, repo_dir)

        assert result["data"]["fts"] is True
        assert result["warnings"] == []


class TestConcurrentWriters:
    """``--dist loadfile`` puts one file's tests on one worker, so a test that
    asserts two writers do not corrupt the store has to spawn its own processes —
    relying on xdist for the contention would produce a test that passes because
    nothing concurrent happened."""

    def test_two_writer_processes_leave_a_readable_store(self, repo_dir):
        program = textwrap.dedent(
            f"""
            import sys, datetime
            sys.path.insert(0, {str(_REPO_ROOT / "plugin")!r})
            from pathlib import Path
            from lib.backlog import cache

            tag = sys.argv[1]
            stamp = datetime.datetime(2026, 8, 7, 12, 0, tzinfo=datetime.timezone.utc).isoformat()
            conn = cache.open_store(Path({str(repo_dir)!r}), create=True)
            if isinstance(conn, dict):
                raise SystemExit("could not open: " + repr(conn))
            for i in range(150):
                result = cache.apply_incremental(
                    conn, [{{"id": tag + str(i), "title": tag, "body": "b"}}],
                    scope=tag, since=stamp, etag=None, fetched_at=stamp,
                )
                if result["status"] != "ok":
                    raise SystemExit("write failed: " + repr(result))
            conn.close()
            """
        )
        script = repo_dir / "writer.py"
        script.write_text(program)

        procs = [
            subprocess.Popen(  # noqa: S603 — fixed argv, no shell
                [sys.executable, str(script), tag],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for tag in ("a", "b")
        ]
        results = [(p.wait(timeout=25), p.communicate()) for p in procs]

        for code, (_out, err) in results:
            assert code == 0, err
        conn = cache.open_store(repo_dir, create=False)
        count = conn.execute("SELECT COUNT(*) FROM item").fetchone()[0]
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        conn.close()
        assert integrity == "ok"
        assert count == 300, "both writers' rows survived"


def _sync(fake, repo_dir, *, now=NOW):
    return sync.incremental_sync(fake, project_dir=repo_dir, owner=OWNER, repo=REPO, now=now)


def _list_calls(fake):
    return [c for c in fake.calls if c[0] == "list_issues"]


class TestIncrementalSync:
    """QRY-5 — the cursor watermark and the conditional revalidation over it.

    The provider semantics these lean on were verified against the live API
    before the fake modelled them (Cache Spec §6): `since` filters `updated_at`
    inclusively, `state` is an independent AND, and the list endpoint answers
    `If-None-Match` with a rate-free 304."""

    def test_with_no_watermark_it_rebuilds_rather_than_asking_for_a_window(self, fake, repo_dir):
        """An absent cursor means "nothing is known", and a `since`-scoped fetch
        against that would quietly build a store containing only recent items
        while reporting success."""
        _corpus(fake)

        result = _sync(fake, repo_dir)

        assert result["status"] == "ok", result
        assert result["data"]["rebuilt"] is True
        assert all(call[6] is None for call in _list_calls(fake)), (
            "a rebuild must not be scoped by `since`"
        )

    def test_a_quiet_interval_fetches_no_pages_at_all(self, fake, repo_dir):
        """The acceptance criterion, and the reason the validator is stored with
        the cursor: an unadvanced watermark re-issues a byte-identical query, so
        the provider can answer 304 — which costs zero rate-limit points."""
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        assert _sync(fake, repo_dir)["status"] == "ok"  # first pass stores the validator
        fake.calls.clear()

        result = _sync(fake, repo_dir)

        assert result["status"] == "ok", result
        assert result["data"]["not_modified"] is True
        assert result["data"]["written"] == 0
        assert _list_calls(fake) == [], "a not-modified answer must not fetch a page"

    def test_an_edit_since_the_watermark_arrives_with_its_new_state(self, fake, repo_dir):
        ids, _closed = _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        assert _sync(fake, repo_dir)["status"] == "ok"

        assert core.update_item(
            fake, id_raw=ids[0], fields={"stage": "ready"}
        )["status"] == "ok"
        result = _sync(fake, repo_dir)

        assert result["status"] == "ok", result
        assert result["data"]["not_modified"] is False
        stored = {row["id"]: row for row in _domain_rows(repo_dir)}
        assert stored[ids[0]]["stage"] == "ready"

    def test_a_close_is_observed_because_the_window_is_not_state_scoped(self, fake, repo_dir):
        """The single most load-bearing fact from verify-api. `since` and `state`
        are independent filters, so `state="open"` would match the closed item's
        timestamp and then drop the row — leaving the cache asserting `open`
        forever. Cache Spec §6 accepts having no deletion sweep *because* `since`
        catches closes, and it only does under `state="all"`."""
        ids, _closed = _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        assert _sync(fake, repo_dir)["status"] == "ok"

        assert core.set_status(fake, id_raw=ids[1], target="shipped")["status"] == "ok"
        assert _sync(fake, repo_dir)["status"] == "ok"

        stored = {row["id"]: row for row in _domain_rows(repo_dir)}
        assert stored[ids[1]]["status"] == "shipped", (
            "a state-scoped window would have filtered the close out of its own notification"
        )
        assert all(call[3] == "all" for call in _list_calls(fake))

    def test_syncing_twice_over_the_same_window_changes_nothing(self, fake, repo_dir):
        """Idempotent double-upsert. The overlap margin guarantees rows are
        re-read on the very next pass, so re-application has to be a no-op or
        every sync would corrupt what the last one wrote."""
        ids, _closed = _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        assert core.update_item(fake, id_raw=ids[0], fields={"stage": "ready"})["status"] == "ok"

        assert _sync(fake, repo_dir)["status"] == "ok"
        once = _domain_rows(repo_dir)
        conn = cache.open_store(repo_dir, create=False)
        cursor_once = cache.get_cursor_state(conn, SCOPE)
        conn.close()

        assert _sync(fake, repo_dir, now=NOW + timedelta(hours=1))["status"] == "ok"

        conn = cache.open_store(repo_dir, create=False)
        cursor_twice = cache.get_cursor_state(conn, SCOPE)
        conn.close()
        assert _domain_rows(repo_dir) == once
        assert cursor_twice[0] == cursor_once[0], "a quiet re-run must not move the watermark"

    def test_a_validator_is_stored_only_for_the_window_it_actually_validates(
        self, fake, repo_dir
    ):
        """A validator belongs to the query it was issued against, and `since` is
        what fixes that query's identity. So a sync that MOVES the watermark must
        not keep the old validator: it would be replayed against a query that no
        longer exists, miss every time, and cost a full request while looking
        like a live optimisation. A sync that leaves the watermark alone may keep
        it — that is the case the 304 exists for."""
        ids, _closed = _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        assert core.update_item(fake, id_raw=ids[0], fields={"stage": "ready"})["status"] == "ok"

        assert _sync(fake, repo_dir)["status"] == "ok"
        conn = cache.open_store(repo_dir, create=False)
        moved_since, moved_etag = cache.get_cursor_state(conn, SCOPE)
        conn.close()

        assert _sync(fake, repo_dir)["status"] == "ok"
        conn = cache.open_store(repo_dir, create=False)
        settled_since, settled_etag = cache.get_cursor_state(conn, SCOPE)
        conn.close()

        assert moved_etag is None, "the watermark moved, so the old validator was void"
        assert settled_since == moved_since, "nothing new arrived; the watermark held"
        assert settled_etag is not None, "a held watermark keeps its validator"

        # ...and that stored validator is what buys the free sync.
        fake.calls.clear()
        result = _sync(fake, repo_dir)
        assert result["data"]["not_modified"] is True
        assert _list_calls(fake) == []

    def test_the_window_reaches_back_past_the_newest_stamp_seen(self, fake, repo_dir):
        """Boundary-overlap re-read. `since` being inclusive re-reads the exact
        boundary item; the margin covers what inclusivity cannot — a write
        committed server-side at the instant the scan read past it."""
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        newest = max(
            parse_iso(i["updated_at"]) for i in fake.list_issues(OWNER, REPO, state="all")
        )

        conn = cache.open_store(repo_dir, create=False)
        since, _etag = cache.get_cursor_state(conn, SCOPE)
        conn.close()

        assert parse_iso(since) == newest - sync.CURSOR_OVERLAP
        assert parse_iso(since) < newest, "the watermark must not sit on the newest stamp"

    def test_a_crash_between_fetch_and_commit_loses_nothing_on_re_run(self, fake, repo_dir):
        """The chunk's correctness argument, asserted rather than documented.

        The watermark claims "everything up to here is stored". If it advances
        and the rows do not, the next sync starts *after* items that were never
        written, and nothing will ever go back for them — no actor is guaranteed
        to re-run this particular transition, so being idempotent on re-run is
        not enough. The write has to be atomic, and this cuts it exactly there:
        the row write fails, and the watermark must not have moved."""
        ids, _closed = _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        assert _sync(fake, repo_dir)["status"] == "ok"
        conn = cache.open_store(repo_dir, create=False)
        before = cache.get_cursor_state(conn, SCOPE)
        conn.close()

        assert core.update_item(fake, id_raw=ids[0], fields={"stage": "ready"})["status"] == "ok"
        path = cache.cache_path(repo_dir)
        broken = sqlite3.connect(str(path))
        broken.execute("DROP TABLE item")
        broken.commit()
        broken.close()

        result = _sync(fake, repo_dir)

        assert result["status"] == "error"
        conn = cache.open_store(repo_dir, create=False)
        after = cache.get_cursor_state(conn, SCOPE)
        conn.close()
        assert after == before, (
            "the watermark advanced past rows that were never written — those items "
            "would never be fetched again"
        )

    def test_a_transport_failure_leaves_the_store_and_the_watermark_alone(self, fake, repo_dir):
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        assert _sync(fake, repo_dir)["status"] == "ok"
        before_rows = _domain_rows(repo_dir)
        conn = cache.open_store(repo_dir, create=False)
        before_cursor = cache.get_cursor_state(conn, SCOPE)
        conn.close()

        fake.set_unreachable(True)
        result = _sync(fake, repo_dir)

        assert result["status"] == "error"
        conn = cache.open_store(repo_dir, create=False)
        after_cursor = cache.get_cursor_state(conn, SCOPE)
        conn.close()
        assert _domain_rows(repo_dir) == before_rows
        assert after_cursor == before_cursor


class TestLeavingScope:
    """An item stripped of its block and labels stops being an item.

    An upsert-only sync has no other way to learn that, so the row would sit in
    the store as an open item forever and reach the consumers that walk the open
    set — a stale *positive*, an answer rather than a gap. Unlike hard deletion
    and transfer-out (the two invisible cases Cache Spec §6 accepts), the sync
    window already carries the evidence, so there is nothing to accept.
    """

    def _strip_from_scope(self, fake, item_id):
        number = int(item_id.rsplit("#", 1)[1])
        issue = fake.get_issue(OWNER, REPO, number)
        for name in list(encode.label_names(issue)):
            fake.remove_label(OWNER, REPO, number, name)
        fake.update_issue(OWNER, REPO, number, fields={"body": "no block any more"})

    def test_a_de_scoped_item_is_evicted_by_the_next_incremental_sync(self, fake, repo_dir):
        item_id = _file(fake, title="cache: an item that will leave scope", area="backlog")
        _file(fake, title="cache: an item that stays", area="backlog")
        _rebuild(fake, repo_dir)
        assert item_id in {row["id"] for row in _domain_rows(repo_dir) if "id" in row}

        self._strip_from_scope(fake, item_id)
        result = _sync(fake, repo_dir, now=NOW + timedelta(hours=1))

        assert result["status"] == "ok"
        assert result["data"]["evicted"] == 1
        assert item_id not in {row["id"] for row in _domain_rows(repo_dir) if "id" in row}

    def test_eviction_sweeps_the_derived_indexes_too(self, fake, repo_dir):
        """An item gone from `item` but still answering a text search or a
        changed-file intersection is the same stale positive wearing a hit's
        shape."""
        item_id = _file(fake, title="cache: an indexed item that leaves scope", area="backlog")
        assert core.update_item(
            fake, id_raw=item_id, fields={"affected": "plugin/lib/backlog"}
        )["status"] == "ok"
        _rebuild(fake, repo_dir)
        assert _affecting(repo_dir, ["plugin/lib/backlog/sync.py"]) == [item_id]

        self._strip_from_scope(fake, item_id)
        _sync(fake, repo_dir, now=NOW + timedelta(hours=1))

        assert _affecting(repo_dir, ["plugin/lib/backlog/sync.py"]) == []
        conn = cache.open_store(repo_dir, create=False)
        indexed = conn.execute(
            "SELECT COUNT(*) FROM item_fts WHERE item_id = ?", (item_id,)
        ).fetchone()[0]
        conn.close()
        assert indexed == 0

    def test_issues_that_were_never_items_evict_nothing(self, fake, repo_dir):
        """The corpus carries a pull request and a plain repo issue, and neither
        was ever cached. Counting candidate ids instead of rows actually removed
        would report an eviction on every sync of any repo with ordinary
        issues — a number that looks like the cache shedding items."""
        _corpus(fake)
        _rebuild(fake, repo_dir)

        result = _sync(fake, repo_dir, now=NOW + timedelta(hours=1))

        assert result["data"]["evicted"] == 0


class TestListQueryValidator:
    """The list validator is not the item validator, and the whole conditional
    path rests on that distinction (verified live — Cache Spec §6)."""

    def test_an_unchanged_window_reports_unchanged(self, fake):
        _corpus(fake)
        first = fake.get_issues_validator(OWNER, REPO, state="all", since=None, etag=None)

        again = fake.get_issues_validator(OWNER, REPO, state="all", since=None, etag=first.etag)

        assert first.changed is True, "no stored validator means ask unconditionally"
        assert again.changed is False
        assert again.etag == first.etag

    def test_a_touched_item_invalidates_the_window(self, fake):
        ids, _closed = _corpus(fake)
        first = fake.get_issues_validator(OWNER, REPO, state="all", since=None, etag=None)

        assert core.update_item(fake, id_raw=ids[0], fields={"stage": "ready"})["status"] == "ok"
        after = fake.get_issues_validator(OWNER, REPO, state="all", since=None, etag=first.etag)

        assert after.changed is True
        assert after.etag != first.etag

    def test_the_validator_lives_on_the_cursor_and_nowhere_else(self, fake, repo_dir):
        """A list ETag replayed against `GET /issues/{n}` returns 200, not 304, so
        a list validator stored per item would make every per-item revalidation
        miss *while looking like it worked*.

        This used to assert `item.etag` stayed NULL on every row. **The column is
        now gone**, so the property is structural rather than maintained: the
        wrong place to put a validator does not exist. The assertion follows it —
        the column's absence is what makes the mistake unavailable, and a
        re-added `item.etag` (whose only intended producer, a decision-path
        single-item read, was never built) fails here.
        """
        ids, _closed = _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        assert core.update_item(fake, id_raw=ids[0], fields={"stage": "ready"})["status"] == "ok"
        # Twice: the first sync moves the watermark, the second settles it, and
        # only a settled watermark carries a validator (see the validator-scope
        # test above).
        assert _sync(fake, repo_dir)["status"] == "ok"
        assert _sync(fake, repo_dir)["status"] == "ok"

        path = cache.cache_path(repo_dir)
        conn = sqlite3.connect(str(path))
        item_columns = {row[1] for row in conn.execute("PRAGMA table_info(item)")}
        cursor_etag = conn.execute("SELECT etag FROM cursor").fetchone()
        rows = conn.execute("SELECT COUNT(*) FROM item").fetchone()[0]
        conn.close()

        assert rows, "an empty store would make this vacuous"
        assert "etag" not in item_columns, (
            "`item.etag` is back. It has no producer — `pick` revalidates through "
            "the LIST validator on `cursor.etag` — so a conditional single-item "
            "read against it would miss every time and look correct."
        )
        assert cursor_etag[0] is not None, "the list validator belongs on the cursor"


class TestSyncEnvelopeShape:
    def test_every_sync_exit_emits_the_same_keys(self, fake, repo_dir):
        """The values differ by path; the shape must not. A consumer reading
        `data["not_modified"]` should not work on a quiet sync and raise on a
        rebuild."""
        _corpus(fake)
        rebuilt = _rebuild(fake, repo_dir)
        fetched = _sync(fake, repo_dir)
        quiet = _sync(fake, repo_dir)
        while not quiet["data"]["not_modified"]:  # settle the watermark
            quiet = _sync(fake, repo_dir)

        shapes = [set(r["data"]) for r in (rebuilt, fetched, quiet)]
        assert shapes[0] == shapes[1] == shapes[2], shapes
        assert {"written", "fts", "scope", "since", "fetched_at", "rebuilt",
                "not_modified"} <= shapes[0]


class TestTransportWithoutTheProbe:
    """A provider with no conditional-request path must sync unconditionally —
    it must not fail to sync.

    Pinned by execution rather than by reading the base class, which is the
    distinction the fix itself turned on: the guard used to test the ATTRIBUTE,
    and `Transport` defines the method, so `getattr` always found it and the
    `NotImplementedError` escaped. Nothing but a transport that actually lacks
    the override can tell those two implementations apart."""

    class _NoProbe(FakeGitHub):
        def get_issues_validator(self, *args, **kwargs):
            # Exactly what a subclass that never overrode it does.
            return sync.Transport.get_issues_validator(self, *args, **kwargs)

    def test_sync_degrades_to_an_unconditional_fetch_rather_than_failing(self, repo_dir):
        fake = self._NoProbe(user={"login": "agent-a", "id": 1})
        ids, _closed = _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        assert core.update_item(fake, id_raw=ids[0], fields={"stage": "ready"})["status"] == "ok"

        result = _sync(fake, repo_dir)

        assert result["status"] == "ok", result
        assert result["data"]["not_modified"] is False
        stored = {row["id"]: row for row in _domain_rows(repo_dir)}
        assert stored[ids[0]]["stage"] == "ready", "the unconditional path still syncs"

    def test_it_never_reports_a_free_sync_it_cannot_actually_verify(self, repo_dir):
        """The dangerous degradation is the other one: reporting not-modified
        because the probe is missing would serve a frozen cache forever."""
        fake = self._NoProbe(user={"login": "agent-a", "id": 1})
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"

        for _ in range(3):
            assert _sync(fake, repo_dir)["data"]["not_modified"] is False


class TestTheCostSurface:
    """**OPS-1 — cost is O(1) in project count** (→ NF1/G4, NFR §2).

    Carried from Chunk 01 to the chunk where the adapter's surface is finally
    cache-backed, because the claim is about what an *Nth* onboarded project adds
    and only now is there a full answer.

    The assertion is structural rather than financial, because a test cannot read
    an invoice: onboarding the Nth project must add **no recurring resource** — no
    per-project server, queue or paid service — so the whole per-project footprint
    has to be local files that a `rm -rf` reclaims. Two independent projects are
    built and their footprints compared: the same two files each, each inside its
    own clone, and nothing shared, global or outside them.
    """

    def _project(self, tmp_path, name):
        from fakes.fake_github import FakeGitHub
        from lib.backlog import core as backlog_core, snapshot, sync

        root = tmp_path / name
        root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        fake = FakeGitHub(user={"login": "agent-a", "id": 1})
        assert backlog_core.file_item(
            fake, owner=OWNER, repo=name, title=f"cost: an item in {name}", body="b"
        )["status"] == "ok"
        assert sync.full_rebuild(
            fake, project_dir=root, owner=OWNER, repo=name
        )["status"] == "ok"
        snapshot.write(snapshot.snapshot_path(root), f"{OWNER}/{name}", {"total": 1})
        return root

    def test_the_nth_project_adds_only_local_files_inside_its_own_clone(self, tmp_path):
        first = self._project(tmp_path, "alpha")
        second = self._project(tmp_path, "beta")  # the Nth

        footprints = []
        for root in (first, second):
            store_dir = root / ".git" / cache.STORE_SUBDIR
            entries = sorted(p.name for p in store_dir.iterdir())
            footprints.append(entries)
            # Inside the clone, never in the working tree — so it cannot be
            # committed, and deleting the clone reclaims all of it.
            assert store_dir.is_dir()
            assert not any(
                p.name.startswith("backlog-") for p in root.iterdir() if p.name != ".git"
            ), "a backlog artifact escaped into the working tree"

        # The Nth project's footprint is the same KIND and SIZE as the first's:
        # nothing accumulates in a shared place as projects are added.
        assert footprints[0] == footprints[1], footprints
        assert set(footprints[0]) == {cache.STORE_BASENAME, "backlog-counts.json"}, footprints[0]

    def test_every_local_artifact_is_rebuildable_from_the_provider(self, tmp_path):
        """The other half of "disk, not dollars": deleting the whole footprint
        costs a re-fetch, not data. A per-project artifact that could NOT be
        rebuilt would be state, and state is what turns into a hosted resource."""
        from fakes.fake_github import FakeGitHub
        from lib.backlog import core as backlog_core, cachequery, sync

        root = tmp_path / "gamma"
        root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        fake = FakeGitHub(user={"login": "agent-a", "id": 1})
        assert backlog_core.file_item(
            fake, owner=OWNER, repo="gamma", title="cost: a rebuildable item", body="b"
        )["status"] == "ok"
        assert sync.full_rebuild(fake, project_dir=root, owner=OWNER, repo="gamma")["status"] == "ok"

        shutil.rmtree(root / ".git" / cache.STORE_SUBDIR)

        gone = cachequery.open_items(root, scope=f"{OWNER}/gamma", now=NOW)
        assert gone["status"] == "error"  # reported, never silently empty
        assert sync.full_rebuild(fake, project_dir=root, owner=OWNER, repo="gamma")["status"] == "ok"
        back = cachequery.open_items(root, scope=f"{OWNER}/gamma", now=NOW)
        assert back["status"] == "ok" and len(back["data"]["items"]) == 1


class TestNothingDetachedEverRan:
    """**OPS-3 — no server required for correctness** (→ NF2, NFR §8).

    Carried from Chunk 05 to the chunk that builds the store's detached-spawn
    trigger, because writing it earlier would have asserted a property of a
    component that did not exist: with nothing spawning a sync at all, "correctness
    does not depend on the detached refresh" was true for the uninteresting reason.

    The claim is that the trigger is an **optimisation of freshness, never a
    prerequisite for correctness**. So the whole surface — CRUD write, sync, every
    cache query, `pick` — runs in one process with the spawn boundary poisoned, and
    a spawn attempt is a test failure rather than a silent background helper making
    the result look better than it is.
    """

    def _poisoned_spawn(*args, **kwargs):  # pragma: no cover - reaching it IS the failure
        raise AssertionError(
            "something spawned a detached child during the correctness surface; "
            "OPS-3 says no supervised process is required for correctness"
        )

    # Poisoned at `transport.spawn_detached` — the detached-spawn boundary — and
    # NOT at `subprocess.Popen`. Popen is what `subprocess.run` is built on, so
    # poisoning it takes out the `git rev-parse` that resolves the store's own
    # path, and the test then fails for a reason that has nothing to do with the
    # claim. The boundary this row is about is the one module that spawns.

    def test_the_full_surface_is_correct_with_no_detached_process(self, tmp_path):
        from fakes.fake_github import FakeGitHub
        from lib.backlog import cachequery, core as backlog_core, query, sync

        root = tmp_path / "solo"
        root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=root, check=True)
        fake = FakeGitHub(user={"login": "agent-a", "id": 1})
        now = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)

        with mock.patch("lib.backlog.transport.spawn_detached", self._poisoned_spawn):
            # CRUD, through the same path an operator uses.
            filed = backlog_core.file_item(
                fake, owner="octo", repo="repo",
                title="ops: an item filed with nothing running",
                body="b", facets={"area": "ops", "stage": "ready"},
            )
            assert filed["status"] == "ok", filed
            item = filed["data"]["id"]

            assert sync.full_rebuild(
                fake, project_dir=root, owner="octo", repo="repo", now=now
            )["status"] == "ok"

            # Every query answers, and answers about the item just written.
            for result in (
                cachequery.open_items(root, scope="octo/repo", now=now),
                cachequery.by_area(root, scope="octo/repo", now=now),
                cachequery.unstaged_items(root, scope="octo/repo", now=now),
                cachequery.stale_items(root, scope="octo/repo", older_than_days=90, now=now),
                cachequery.search(root, scope="octo/repo", text="filed", now=now),
                cachequery.ready_items(root, scope="octo/repo", now=now),
                cachequery.resolve(root, scope="octo/repo", id_raw=item, now=now),
            ):
                assert result["status"] == "ok", result

            assert item in [i["id"] for i in cachequery.open_items(
                root, scope="octo/repo", now=now)["data"]["items"]]

            picked = query.pick(fake, project_dir=root, owner="octo", repo="repo", limit=3)
            assert picked["status"] == "ok", picked
            assert item in [i["id"] for i in picked["data"]["candidates"]], (
                "the item is ready and unblocked, so a correct `pick` returns it "
                "without anything having refreshed the store in the background"
            )

    def test_the_trigger_is_detached_incremental_and_unattended(self, tmp_path):
        """The trigger itself, asserted where OPS-3 asserts its absence — the two
        claims are one decision seen from both sides. It must never be waited on
        (session start does not block on the network), and never `--rebuild` (the
        steady state is a rate-free 304; a rebuild every session would refetch the
        whole backlog to learn nothing changed)."""
        from lib.backlog import sync

        calls = []

        class _Recorder:
            def __call__(self, argv, **kwargs):
                calls.append((argv, kwargs))
                return self

            def wait(self, *a, **k):  # pragma: no cover - reaching this IS the failure
                raise AssertionError("the cache warm was waited on")

            communicate = wait
            poll = wait

        recorder = _Recorder()
        assert sync.spawn_sync(
            ["python3", "hook"], tmp_path, "octo/repo", popen=recorder, env={}
        )

        argv, kwargs = calls[0]
        assert argv[-4:] == ["backlog", "sync", "--repo", "octo/repo"]
        assert "--rebuild" not in argv
        assert kwargs["start_new_session"] is True
        assert kwargs["env"]["PRAWDUCT_UNATTENDED"] == "1"

    def test_a_failed_warm_is_not_an_error(self, tmp_path):
        """A warm that cannot start costs a staler next read, which every consumer
        already reports as a visible age — so it must never raise into the briefing
        path that fired it."""
        from lib.backlog import sync

        def _refuses(*_a, **_k):
            raise OSError("no fork for you")

        assert sync.spawn_sync(
            ["python3", "hook"], tmp_path, "octo/repo", popen=_refuses, env={}
        ) is False
