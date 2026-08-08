"""Tests for the write-path mirror — the wiring, end to end through the CLI.

The mirror *primitive* (`cache.absorb_rows`, `sync.absorb_issue`) and its
invariants live in ``test_backlog_cache.py``: rebuild-equivalence, the cursor it
must not move, the stores it must refuse. What lives here is the question that
one cannot answer — **does a write actually reach it**, for each op that changes
cached state, when driven the way a caller drives it.

That split matters because the two halves fail differently. A correct primitive
nobody calls is exactly the state this branch shipped in W1: the store was
written by `sync` and the session-start warm and by nothing else, while the data
model asserted read-your-writes. So the assertions here are deliberately made
through `cli.run` against a real store rather than by calling `core` directly —
calling `core` with a callback I construct in the test would prove my callback
works, not that the CLI binds one.

All offline: no ``gh``, no network.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent / "plugin"
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.backlog import cache, cachequery, cli, core, sync  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402
from fixtures.backlog_fixtures import DISCODON_MINI  # noqa: E402

OWNER, REPO_NAME = "octo", "repo"
SCOPE = f"{OWNER}/{REPO_NAME}"


@pytest.fixture
def fake():
    return FakeGitHub(user={"login": "agent-a", "id": 1})


@pytest.fixture
def repo_dir(tmp_path):
    """A real git work tree — ``cache_path`` resolves through ``--git-common-dir``."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def _run(repo_dir, argv, fake):
    return cli.run(str(repo_dir), argv, transport=fake)


def _warm(repo_dir, fake):
    """A synced store — the precondition every mirror has, since a mirror refuses
    to run against a store no sync has covered."""
    result = sync.full_rebuild(fake, project_dir=repo_dir, owner=OWNER, repo=REPO_NAME)
    assert result["status"] == "ok", result
    return result


def _cached(repo_dir, item_id):
    """One item's stored row, or ``None``.

    Read straight off `item` rather than through `cachequery.resolve`, which
    answers a different question than these tests ask: `resolve` follows the
    `superseded_by` redirect to the survivor and returns a resolution payload
    (`resolved`/`via`/`status`) with no `body`. Both matter here — the merge test
    asserts about the *source* it just redirected, and two tests assert on the
    mirrored body. Going through `resolve` would have quietly asserted about the
    wrong item."""
    import sqlite3

    conn = sqlite3.connect(str(cache.cache_path(repo_dir)))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM item WHERE id = ?", (item_id,)).fetchone()
    finally:
        conn.close()
    return dict(row) if row is not None else None


def _resolves(repo_dir, item_id):
    """Whether the id resolves through the query surface a consumer actually uses
    — the C-B4 dangling-id question."""
    resolved = cachequery.resolve(
        repo_dir, scope=SCOPE, now=_now(), id_raw=item_id, default_owner=OWNER
    )
    assert resolved["status"] == "ok", resolved
    return bool(resolved["data"].get("resolved"))


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc)


def _open_ids(repo_dir):
    served = cachequery.open_items(repo_dir, scope=SCOPE, now=_now())
    assert served["status"] == "ok", served
    return [item["id"] for item in served["data"]["items"]]


class TestWritesReachTheCache:
    """One test per op that changes cached state, driven through the CLI."""

    def test_file_makes_the_new_item_immediately_resolvable(self, fake, repo_dir):
        """The sharpest case in the defect report: C-B4 resolves a citation
        against a store that predates the item and reports *no such item*, which
        reads as a dangling id rather than as a stale cache."""
        _warm(repo_dir, fake)

        code = _run(
            repo_dir,
            ["file", "--repo", SCOPE, "--title", "backlog: the item under test here",
             "--body", "filed after the warm", "--json"],
            fake,
        )

        assert code == 0
        assert _resolves(repo_dir, f"{SCOPE}#1"), "the just-filed id reads as dangling"
        assert f"{SCOPE}#1" in _open_ids(repo_dir)

    def test_status_is_reflected(self, fake, repo_dir):
        """The `done` path: `update status=shipped` followed by the PR-time
        closes/status check reading the item as still open."""
        core.file_item(fake, owner=OWNER, repo=REPO_NAME,
                       title="backlog: the item under test here", body="b")
        _warm(repo_dir, fake)
        assert f"{SCOPE}#1" in _open_ids(repo_dir)

        code = _run(repo_dir, ["status", f"{SCOPE}#1", "--to", "shipped", "--json"], fake)

        assert code == 0
        assert _cached(repo_dir, f"{SCOPE}#1")["status"] == "shipped"
        assert f"{SCOPE}#1" not in _open_ids(repo_dir)

    def test_update_reflects_fields_and_the_derived_path_index(self, fake, repo_dir):
        """`affected` is the one field with a derived index behind it, so it is the
        one that would silently keep answering the old intersection."""
        core.file_item(fake, owner=OWNER, repo=REPO_NAME,
                       title="backlog: the item under test here", body="b")
        _warm(repo_dir, fake)

        code = _run(
            repo_dir,
            ["update", f"{SCOPE}#1", "--stage", "ready", "--area", "critic",
             "--affected", "plugin/lib/backlog", "--json"],
            fake,
        )

        assert code == 0
        row = _cached(repo_dir, f"{SCOPE}#1")
        assert row["stage"] == "ready"
        affecting = cachequery.items_affecting(
            repo_dir, scope=SCOPE, now=_now(),
            changed_paths=["plugin/lib/backlog/sync.py"], open_only=True,
        )
        assert affecting["status"] == "ok"
        assert f"{SCOPE}#1" in [item["id"] for item in affecting["data"]["items"]]

    def test_link_related_is_mirrored_and_the_native_edges_are_not(self, fake, repo_dir):
        """`related` lives in the body block, which the store holds and indexes.
        `blocks`/`parent` are native GitHub edges with no column here at all — so
        this asserts a mirror on one and, on the other, that nothing was written
        rather than that something was."""
        core.file_item(fake, owner=OWNER, repo=REPO_NAME,
                       title="backlog: the first item under test", body="b")
        core.file_item(fake, owner=OWNER, repo=REPO_NAME,
                       title="backlog: the second item under test", body="b")
        _warm(repo_dir, fake)
        before_blocked = _cached(repo_dir, f"{SCOPE}#1")["body"]

        assert _run(
            repo_dir,
            ["link", f"{SCOPE}#1", "--edge", "related", "--to", f"{SCOPE}#2", "--json"],
            fake,
        ) == 0
        assert f"{SCOPE}#2" in _cached(repo_dir, f"{SCOPE}#1")["body"]

        # A native edge changes nothing the store holds, so the body must not move.
        after_related = _cached(repo_dir, f"{SCOPE}#1")["body"]
        assert _run(
            repo_dir,
            ["link", f"{SCOPE}#1", "--edge", "blocked-by", "--to", f"{SCOPE}#2", "--json"],
            fake,
        ) == 0
        assert _cached(repo_dir, f"{SCOPE}#1")["body"] == after_related
        assert before_blocked != after_related, "the `related` write must have moved the body"

    def test_merge_mirrors_the_source_it_closes_and_redirects(self, fake, repo_dir):
        """`migrate.merge` calls `core.set_status` itself, so it does not inherit
        the callback from the CLI's `status` handler — it has to thread one. One
        mirror covers both halves: `set_status` ends on a `get_issue` that reflects
        the `superseded_by` redirect written a step earlier."""
        core.file_item(fake, owner=OWNER, repo=REPO_NAME,
                       title="backlog: the duplicate under test", body="b")
        core.file_item(fake, owner=OWNER, repo=REPO_NAME,
                       title="backlog: the survivor under test", body="b")
        _warm(repo_dir, fake)

        code = _run(repo_dir, ["merge", f"{SCOPE}#1", "--into", f"{SCOPE}#2", "--json"], fake)

        assert code == 0
        source = _cached(repo_dir, f"{SCOPE}#1")
        assert source["status"] == "dropped"
        assert f"{SCOPE}#2" in source["body"], "the redirect must be mirrored, not only the close"


class TestTheMirrorCostsNothingAndBreaksNothing:
    def test_no_additional_provider_request_is_spent(self, fake, repo_dir):
        """Measured against a control rather than against a number I typed: run
        the same write with the mirror reachable and with it absent, and compare.

        The claim is that the mirror reuses an issue the write already holds. If
        it ever went and fetched one, this gap would open."""
        core.file_item(fake, owner=OWNER, repo=REPO_NAME,
                       title="backlog: the item under test here", body="b")
        _warm(repo_dir, fake)
        before = len(fake.calls)
        assert _run(repo_dir, ["status", f"{SCOPE}#1", "--to", "shipped", "--json"], fake) == 0
        with_mirror = len(fake.calls) - before

        # The control: an unsynced project, so the mirror declines before writing.
        other = repo_dir / "control"
        other.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=other, check=True)
        before = len(fake.calls)
        assert _run(other, ["status", f"{SCOPE}#1", "--to", "open", "--json"], fake) == 0
        without_mirror = len(fake.calls) - before

        assert with_mirror == without_mirror, (
            f"the mirror spent {with_mirror - without_mirror} extra provider request(s)"
        )

    def test_the_stores_first_query_cannot_escape_the_guard(self, fake, repo_dir):
        """`absorb_rows`' first statement to touch the connection is `has_fts`, and
        it once sat OUTSIDE the function's own `try` — so an unreadable-at-that-
        moment store (no WAL, a concurrent writer past the busy timeout) raised
        there and nowhere else, escaping every frame up to the CLI boundary.

        Asserted by making that exact call raise, because that is the line the
        defect was on. A read-only store does *not* reproduce it — reads succeed on
        one, so the failure lands later, inside the guard, and the test would pass
        against the defect."""
        _warm(repo_dir, fake)
        conn = cache.open_store(repo_dir, create=False)
        try:
            with pytest.MonkeyPatch.context() as patch:
                patch.setattr(
                    cache, "has_fts",
                    lambda _conn: (_ for _ in ()).throw(sqlite3.OperationalError("locked")),
                )
                result = cache.absorb_rows(conn, [], fetched_at="2026-08-08T00:00:00Z")
        finally:
            conn.close()

        assert result["status"] == "error"
        assert result["error"]["code"] == "unavailable"

    def test_a_raise_anywhere_in_the_mirror_never_fails_the_write(self, fake, repo_dir, capsys):
        """The structural half. Every function in the mirror chain is written not
        to raise, and one of them stopped being true once — so the seam catches
        rather than trusting the chain, and a landed provider write is reported as
        the success it is.

        End to end through `cli.run`: exit 0, with the failure surfaced as a
        warning rather than swallowed."""
        core.file_item(fake, owner=OWNER, repo=REPO_NAME,
                       title="backlog: the item under test here", body="b")
        _warm(repo_dir, fake)

        def _explode(*a, **k):
            raise RuntimeError("the mirror blew up")

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(sync, "absorb_issue", _explode)
            code = _run(repo_dir, ["status", f"{SCOPE}#1", "--to", "shipped", "--json"], fake)
            captured = capsys.readouterr()

        assert code == 0, "a raising mirror turned a landed provider write into a failed command"
        # **Degraded AND said so.** This assertion is what makes the broad-except
        # waiver's "nothing is silenced" claim true rather than merely stated:
        # without it, deleting the `warnings.append` in that handler leaves the
        # suite green, and a swallowed failure is exactly what the pragma promises
        # not to be. The other failure test takes the pre-existing return-an-envelope
        # path, so it does not reach this handler at all.
        payload = json.loads(captured.out)
        assert any("was not updated" in w for w in payload["warnings"])
        assert "RuntimeError" in captured.err, "the raised type must reach the diagnostic log"

    def test_a_mirror_failure_is_reported_as_a_warning(self, fake, repo_dir):
        """The other half of the same contract: degraded, and *said* so."""
        core.file_item(fake, owner=OWNER, repo=REPO_NAME,
                       title="backlog: the item under test here", body="b")
        _warm(repo_dir, fake)

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(
                sync, "absorb_issue",
                lambda *a, **k: core.error("unavailable", "the backlog cache write failed"),
            )
            result = cli._with_mirror(
                str(repo_dir),
                lambda absorb: core.set_status(
                    fake, id_raw=f"{SCOPE}#1", target="shipped", absorb=absorb
                ),
            )

        assert result["status"] == "ok"
        assert any("was not updated" in w for w in result["warnings"])

    def test_an_absent_store_is_silent(self, fake, repo_dir):
        """A repo with no cache is not a degraded mirror, it is a repo not using
        one — and every read already reports that with the command that fixes it.
        Warning on each write would restate a known condition where nothing is
        wrong and nothing is lost."""
        core.file_item(fake, owner=OWNER, repo=REPO_NAME,
                       title="backlog: the item under test here", body="b")
        assert not cache.cache_path(repo_dir).exists()

        result = cli._with_mirror(
            str(repo_dir),
            lambda absorb: core.set_status(
                fake, id_raw=f"{SCOPE}#1", target="shipped", absorb=absorb
            ),
        )

        assert result["status"] == "ok"
        assert not [w for w in result["warnings"] if "cache" in w]

    def test_core_still_works_with_no_mirror_bound(self, fake):
        """`absorb=None` is the default on every threaded signature, so `core`
        stays usable — and testable — with no store anywhere."""
        filed = core.file_item(fake, owner=OWNER, repo=REPO_NAME,
                               title="backlog: the item under test here", body="b")
        assert filed["status"] == "ok"
        assert core.set_status(fake, id_raw=filed["data"]["id"], target="shipped")["status"] == "ok"

    def test_core_does_not_import_the_store(self):
        """The seam's whole point: `core` is invoked by the mirror but does not
        know it. If this fails, the callback was replaced by a direct import and
        the dependency now points the wrong way."""
        source = (Path(_REPO_ROOT) / "lib" / "backlog" / "core.py").read_text()
        assert "import cache" not in source
        assert "from .cache" not in source
        assert "import sync" not in source
        assert "from .sync" not in source


class TestImportRefreshesTheCache:
    """`import` is the one write op with no single issue to mirror.

    It creates through the transport directly, hundreds of times, so the per-write
    seam does not apply and re-fetching each issue to feed it would spend a request
    per item to save one. An incremental sync is the mechanism already built for
    "the provider moved a lot" — every created issue has an `updated_at` past the
    watermark.
    """

    #: The suite's own representative legacy backlog, rather than one written here
    #: — a hand-rolled source encodes my belief about the parser's shape, which is
    #: exactly the belief a fixture cannot check.
    SOURCE = DISCODON_MINI

    def test_an_import_into_a_warm_store_leaves_the_items_visible(self, fake, repo_dir):
        _warm(repo_dir, fake)
        assert _open_ids(repo_dir) == [], "the store must start empty, or this counts fixtures"
        source = repo_dir / "backlog.md"
        source.write_text(self.SOURCE)

        code = _run(
            repo_dir, ["import", "--repo", SCOPE, "--from", str(source), "--json"], fake
        )

        assert code == 0
        cached = _open_ids(repo_dir)
        assert cached, f"the imported items never reached the cache: {cached}"

    def test_an_import_with_no_store_creates_none(self, fake, repo_dir):
        """`import` is the command most likely to run BEFORE a first sync — it is
        how a repo becomes a backlog at all — so the refusal to build a store here
        matters more than anywhere else."""
        source = repo_dir / "backlog.md"
        source.write_text(self.SOURCE)

        code = _run(
            repo_dir, ["import", "--repo", SCOPE, "--from", str(source), "--json"], fake
        )

        assert code == 0
        assert not cache.cache_path(repo_dir).exists()


class TestEveryWriteOpIsClassified:
    """A future op added without a mirror decision fails here rather than shipping
    a silently stale read.

    The same shape the ephemeral-worktree guard already uses on this exact op
    surface: enumerate, partition, and make an unclassified addition fail
    something. A comment saying "remember to consider the cache" would not.
    """

    #: Every op in `cli._WRITE_OPS`, and whether it changes state the cache holds.
    #: The reason is carried here because it is the thing a future reader needs —
    #: the classification alone would just be a list to copy.
    MIRRORS: dict[str, str] = {
        "file": "creates the row",
        "status": "moves `status`; also carries `merge`, which closes through set_status",
        "update": "every writable column plus the derived `affected` and alias indexes",
        "link": "`related` only — a body write; the native edges are not cached",
        "unlink": "same as `link`",
        "merge": "redirect in the body plus the close, mirrored through set_status",
        "import": "bulk create with no single issue in hand — covered by a sync after the run",
    }
    DOES_NOT: dict[str, str] = {
        "comment": "the `comment` table was removed at schema v7",
        "provision": "repo label definitions, not items",
        "reconcile-labels": "the alias index derives from the block body, not from the "
                            "`id:PFX` labels this restores",
    }

    def test_the_partition_covers_every_write_op(self):
        classified = set(self.MIRRORS) | set(self.DOES_NOT)
        assert classified == set(cli._WRITE_OPS), (
            "a write op is unclassified for the cache — decide whether it changes "
            "cached state and record the reason: "
            f"{set(cli._WRITE_OPS) ^ classified}"
        )

    def test_the_two_halves_do_not_overlap(self):
        assert not (set(self.MIRRORS) & set(self.DOES_NOT))

    def test_every_mirroring_op_has_a_reason_recorded(self):
        for op, reason in {**self.MIRRORS, **self.DOES_NOT}.items():
            assert reason.strip(), f"{op} is classified with no reason"
