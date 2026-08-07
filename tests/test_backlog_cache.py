"""Tests for lib/backlog/cache.py, sync.py and cachequery.py — the W1 store.

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

import sqlite3
import subprocess
import sys
import textwrap
from datetime import datetime, timedelta, timezone
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.backlog import cache, cachequery, core, sync  # noqa: E402
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
    and unset, a closed item, a plain non-prawduct issue, and a pull request."""
    ids = [
        _file(fake, title="cache: first item under test", area="backlog", effort="S", impact="L"),
        _file(fake, title="cache: second item under test", area="critic", stage="ready"),
        _file(fake, title="cache: third item under test", body="no facets at all"),
    ]
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
    across two rebuilds."""
    path = cache.cache_path(repo_dir)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    columns = [c for c in cache.ITEM_COLUMNS if c != "fetched_at"]
    rows = conn.execute(f"SELECT {', '.join(columns)} FROM item ORDER BY id").fetchall()
    conn.close()
    return [dict(row) for row in rows]


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


class TestSchema:
    def test_create_makes_every_table_the_data_model_specifies(self, repo_dir):
        conn = cache.open_store(repo_dir, create=True)

        names = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        conn.close()

        assert {"item", "item_fts", "comment", "relationship", "cursor"} <= names

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

        This is the version-0 branch. The symmetric *schema-behind* branch
        (0 < version < SCHEMA_VERSION) has no reachable value while
        SCHEMA_VERSION is 1 and becomes testable at v2; the discard-and-rebuild
        path it shares is covered by the schema-ahead test above."""
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

        result = cache.upsert_items(conn, [{"id": "x"}], fetched_at=NOW.isoformat())
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

    def test_the_served_age_is_the_oldest_row_not_the_newest(self, repo_dir):
        """An age is a promise about the whole payload, so the honest promise is
        the worst row in it — the newest stamp would understate staleness.

        Asserted through ``cachequery``, the path that actually serves the age,
        rather than by calling ``oldest_fetched_at`` directly: reading the
        helper only proves the helper works, and the defect worth catching is a
        server that stops calling it. A partial sync is exactly how the two
        stamps come apart in the field — most rows old, the freshly-upserted
        window new — so the store is set up that way here."""
        conn = cache.open_store(repo_dir, create=True)
        cache.replace_items(
            conn,
            [{"id": "a"}],
            scope=SCOPE,
            fetched_at=(NOW - timedelta(hours=5)).isoformat(),
            cursor_since=(NOW - timedelta(hours=5)).isoformat(),
        )
        cache.upsert_items(conn, [{"id": "b"}], fetched_at=NOW.isoformat())
        conn.close()

        result = cachequery.open_items(repo_dir, scope=SCOPE, now=NOW)

        assert result["status"] == "ok", result
        assert result["data"]["age_seconds"] == pytest.approx(5 * 3600, abs=2), (
            "the newest row's stamp would have reported a cache that is 0s old"
        )


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
        since = cache.get_cursor(conn, SCOPE)
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
        before = _domain_rows(repo_dir)
        assert before, "an empty corpus would make this invariant vacuously true"

        cache.cache_path(repo_dir).unlink()
        assert _rebuild(fake, repo_dir, now=NOW + timedelta(days=2))["status"] == "ok"

        assert _domain_rows(repo_dir) == before

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
                result = cache.upsert_items(
                    conn, [{{"id": tag + str(i), "title": tag, "body": "b"}}], fetched_at=stamp
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
        assert result["data"]["pages_fetched"] == 0
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
        assert cursor_twice == cursor_once, "a quiet re-run must not move the watermark"

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

    def test_sync_never_writes_a_list_validator_into_an_item_row(self, fake, repo_dir):
        """A list ETag replayed against `GET /issues/{n}` returns 200, not 304 —
        so storing one in `item.etag` would make every per-item revalidation miss
        while looking like it worked. `item.etag` stays NULL until a read that
        actually issues a single-item request populates it."""
        _corpus(fake)
        assert _rebuild(fake, repo_dir)["status"] == "ok"
        assert _sync(fake, repo_dir)["status"] == "ok"
        assert core.update_item(
            fake, id_raw=_corpus(fake)[0][0], fields={"stage": "ready"}
        )["status"] == "ok"
        assert _sync(fake, repo_dir)["status"] == "ok"

        path = cache.cache_path(repo_dir)
        conn = sqlite3.connect(str(path))
        etags = [row[0] for row in conn.execute("SELECT etag FROM item").fetchall()]
        cursor_etag = conn.execute("SELECT etag FROM cursor").fetchone()
        conn.close()

        assert etags, "an empty store would make this vacuous"
        assert all(value is None for value in etags)
        assert cursor_etag[0] is not None, "the list validator belongs on the cursor"
