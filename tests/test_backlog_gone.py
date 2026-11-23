"""#1080 — a hard-deleted issue is a terminal ``not_found``, and ``get`` evicts it.

GitHub answers a deleted issue with **410 Gone**. ``transport`` mapped only 404 to
``not_found``, so a 410 fell through to the retryable ``unavailable`` floor and the
cached row for the deleted issue stayed open forever (incremental sync never sees a
deletion). Two layers are pinned here: the status mapping, and the ``get`` that
evicts the ghost it just proved is gone.

All offline: no ``gh``, no network.
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent / "plugin"
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.backlog import cache, cachequery, cli, core, sync  # noqa: E402
from lib.backlog import transport as tp  # noqa: E402
from lib.backlog.transport import TransportError  # noqa: E402
from fakes.fake_github import FakeGitHub, own_tracker  # noqa: E402

OWNER, REPO = "octo", "repo"
SCOPE = f"{OWNER}/{REPO}"


class _GoneGitHub(FakeGitHub):
    """A FakeGitHub where some numbers were hard-deleted: reads answer 410, the
    way the REST API does, rather than the 404 a never-existed number gets."""

    def __init__(self, *a, **k):
        super().__init__(*a, **k)
        self.deleted: set[int] = set()

    def get_issue(self, owner, repo, number):
        if number in self.deleted:
            raise TransportError(
                "not_found",
                "the requested GitHub resource was not found",
                details={"operation": f"api repos/{owner}/{repo}/issues/{number}", "http_status": 410},
            )
        return super().get_issue(owner, repo, number)


@pytest.fixture
def fake():
    return _GoneGitHub(user={"login": "agent-a", "id": 1})


@pytest.fixture
def repo_dir(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    own_tracker(tmp_path, SCOPE)
    return tmp_path


def _cached_ids(repo_dir):
    conn = sqlite3.connect(str(cache.cache_path(repo_dir)))
    try:
        return {r[0] for r in conn.execute("SELECT id FROM item")}
    finally:
        conn.close()


def _file(fake, title):
    result = core.file_item(fake, owner=OWNER, repo=REPO, title=title, body="b")
    assert result["status"] == "ok", result
    return result["data"]["id"]


class TestStatusMapping:
    def setup_method(self):
        self.t = tp.GhTransport()

    def _map(self, stderr):
        return self.t._map_failure(["api", "repos/o/r/issues/985"], 1, stderr)

    def test_http_410_is_a_terminal_not_found(self):
        err = self._map("gh: This issue was deleted (HTTP 410)")
        assert err.code == "not_found"
        assert err.retryable is False
        assert err.details["http_status"] == 410

    def test_http_410_says_the_resource_is_gone(self):
        """Not the generic 404 message: a deleted issue and a never-existed number
        are different facts for the operator reading the envelope."""
        err = self._map("gh: This issue was deleted (HTTP 410)")
        assert "gone" in err.message or "deleted" in err.message

    def test_http_404_still_maps_as_before(self):
        err = self._map("gh: HTTP 404: Not Found")
        assert (err.code, err.retryable) == ("not_found", False)


class TestGetEvictsTheGhost:
    def test_get_of_a_410_is_not_found_and_not_retryable(self, fake, repo_dir, capsys):
        ref = _file(fake, "gone: the ghost item under test")
        sync.full_rebuild(fake, project_dir=repo_dir, owner=OWNER, repo=REPO)
        fake.deleted.add(int(ref.split("#")[1]))

        code = cli.run(str(repo_dir), ["get", ref, "--json"], transport=fake)
        payload = json.loads(capsys.readouterr().out)

        assert code == 3, payload
        assert payload["error"]["code"] == "not_found"
        assert payload["error"]["retryable"] is False

    def test_get_of_a_410_evicts_the_cached_row(self, fake, repo_dir, capsys):
        ghost = _file(fake, "gone: the ghost item under test")
        live = _file(fake, "gone: the surviving item under test")
        sync.full_rebuild(fake, project_dir=repo_dir, owner=OWNER, repo=REPO)
        assert {ghost, live} <= _cached_ids(repo_dir)
        fake.deleted.add(int(ghost.split("#")[1]))

        cli.run(str(repo_dir), ["get", ghost, "--json"], transport=fake)
        capsys.readouterr()

        assert ghost not in _cached_ids(repo_dir), "the ghost row survived a 410"
        assert live in _cached_ids(repo_dir), "eviction must touch only the deleted item"

    def test_an_evicted_ghost_no_longer_lists_as_open(self, fake, repo_dir, capsys):
        ghost = _file(fake, "gone: the ghost item under test")
        sync.full_rebuild(fake, project_dir=repo_dir, owner=OWNER, repo=REPO)
        fake.deleted.add(int(ghost.split("#")[1]))
        cli.run(str(repo_dir), ["get", ghost, "--json"], transport=fake)
        capsys.readouterr()

        served = cachequery.open_items(repo_dir, scope=SCOPE, now=datetime.now(timezone.utc))
        assert served["status"] == "ok", served
        assert ghost not in [i["id"] for i in served["data"]["items"]]

    def test_a_plain_404_does_not_evict(self, fake, repo_dir, capsys):
        """404 is ambiguous (no access to a private repo reads the same), so it is
        reported but never destroys a cached row; only the definitive 410 does."""
        item = _file(fake, "gone: the maybe-hidden item under test")
        sync.full_rebuild(fake, project_dir=repo_dir, owner=OWNER, repo=REPO)
        fake.repos[(OWNER, REPO)].issues.pop(int(item.split("#")[1]))  # a 404, not a 410

        code = cli.run(str(repo_dir), ["get", item, "--json"], transport=fake)
        capsys.readouterr()

        assert code == 3
        assert item in _cached_ids(repo_dir)

    def test_a_failed_eviction_is_a_warning_not_a_changed_verdict(self, fake, repo_dir, capsys):
        """The 410 verdict stands whatever the cache does; an eviction that cannot
        run says so on the envelope rather than going silent."""
        ghost = _file(fake, "gone: the ghost item under test")
        sync.full_rebuild(fake, project_dir=repo_dir, owner=OWNER, repo=REPO)
        fake.deleted.add(int(ghost.split("#")[1]))

        def _boom(*a, **k):
            raise RuntimeError("store exploded")

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(sync, "evict_gone", _boom)
            code = cli.run(str(repo_dir), ["get", ghost, "--json"], transport=fake)
        payload = json.loads(capsys.readouterr().out)

        assert code == 3
        assert any("cache" in w and "stale" in w for w in payload["warnings"]), payload

    def test_no_store_means_no_noise(self, fake, repo_dir, capsys):
        """A repo that never built a cache has nothing to evict and nothing to say."""
        ghost = _file(fake, "gone: the ghost item under test")
        fake.deleted.add(int(ghost.split("#")[1]))
        code = cli.run(str(repo_dir), ["get", ghost, "--json"], transport=fake)
        payload = json.loads(capsys.readouterr().out)
        assert code == 3
        assert not payload.get("warnings")
