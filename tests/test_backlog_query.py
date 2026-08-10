"""Tests for lib/backlog/query.py — list / pick / counts (Chunk 03, L1).

Covers the ready-work read side against the transport-seam fake:
- QRY-1 structured, online, strongly-consistent-in-practice ``list`` + the
  observed 404-after-create replication window (bounded settle-retry).
- QRY-2 ``pick`` cache-then-fan-out: the candidate set off the local store
  (open ∧ stage:ready ∧ no working branch, scoped), the **live** blocker
  predicate including the cross-repo case, ranking, and the negative — a stale
  store must not let a blocked item through.
- QRY-4 ``counts`` derived on read.
- PROV-2 non-prawduct issues are out-of-scope (ignored, not malformed).

All offline: no ``gh``, no network (Build & Test Config — the default suite stays
green without a live GitHub).
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.backlog import cache, cli, core, encode, query, sync  # noqa: E402
from lib.backlog.transport import TransportError  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402

OWNER, REPO = "octo", "repo"
NOW = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)
NOSLEEP = lambda _attempt: None  # noqa: E731 — deterministic no-wait settle in tests


@pytest.fixture
def fake():
    return FakeGitHub(user={"login": "agent-a", "id": 1})


@pytest.fixture
def repo_dir(tmp_path):
    """A real git work tree — `cache_path` resolves through `--git-common-dir`,
    which is also what makes the store shared by every worktree of a clone."""
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def _file(fake, *, title="query: the t item under test", body="b", owner=OWNER, repo=REPO, **facets):
    """File a prawduct item through core (labels auto-provisioned); return its id."""
    result = core.file_item(fake, owner=owner, repo=repo, title=title, body=body, facets=facets)
    assert result["status"] == "ok", result
    return result["data"]["id"]


def _plain(fake, *, title="query: the plain item under test", body="just a normal issue", owner=OWNER, repo=REPO):
    """Create a non-prawduct issue (no block, no namespaced label) — out of scope."""
    issue = fake.create_issue(owner, repo, title=title, body=body, labels=[])
    return f"{owner}/{repo}#{issue['number']}"


def _assign(fake, id_raw, *, login):
    """Assign an item on the provider directly. Prawduct no longer writes
    `assignee` — the claim op that did is retired — so a test that wants an
    assigned item reaches past the adapter, which is also the only way the field
    is set in the field now (GitHub's own UI)."""
    _owner, _repo, number = _split(id_raw)
    fake.update_issue(_owner, _repo, number, fields={"assignees": [login]})


def _stamp_created(fake, id_raw, when):
    """Set an item's provider `created_at`. The fake stamps every issue at one
    instant, and ready-work's ranking is precisely about telling them apart."""
    _owner, _repo, number = _split(id_raw)
    fake._repo(_owner, _repo).issues[number]["created_at"] = (
        when.isoformat().replace("+00:00", "Z")
    )


def _split(id_raw):
    owner_repo, _, number = id_raw.partition("#")
    owner, _, repo = owner_repo.partition("/")
    return owner, repo, int(number)


def _sync(fake, repo_dir):
    """Warm the store without going through `pick` — for a test that needs the
    cache populated *before* it changes something on the provider."""
    result = sync.full_rebuild(fake, project_dir=repo_dir, owner=OWNER, repo=REPO, now=NOW)
    assert result["status"] == "ok", result


def _pick(fake, repo_dir, **kwargs):
    return query.pick(fake, project_dir=repo_dir, owner=OWNER, repo=REPO, now=NOW, **kwargs)


# --- QRY-1: list -------------------------------------------------------------


class TestList:
    def test_structured_filter_returns_matching_prawduct_items(self, fake):
        _file(fake, title="query: the ready one item under test", stage="ready")
        _file(fake, title="query: the ready two item under test", stage="ready")
        _file(fake, title="query: the in design item under test", stage="design")

        result = query.list_items(fake, owner=OWNER, repo=REPO, filters={"stage": "ready"})
        assert result["status"] == "ok"
        assert result["data"]["count"] == 2
        assert {i["title"] for i in result["data"]["items"]} == {"query: the ready one item under test", "query: the ready two item under test"}

    def test_tag_filter_returns_the_tagged_items(self, fake):
        tagged = _file(fake, title="query: the tagged item under test")
        other = _file(fake, title="query: the untagged item under test")
        core.update_item(fake, id_raw=tagged, fields={"tags": "perf,api"})

        result = query.list_items(fake, owner=OWNER, repo=REPO, filters={"tag": "perf"})

        assert result["status"] == "ok"
        assert [i["id"] for i in result["data"]["items"]] == [tagged]
        assert other not in {i["id"] for i in result["data"]["items"]}

    def test_the_tag_filter_selects_one_of_an_item_s_several_tags(self, fake):
        """`tag` rides the label-facet mechanism but is the one multi-valued
        facet, so filtering picks items carrying that tag among others — it does
        not select an item's single value the way `area` does."""
        tagged = _file(fake, title="query: the multiply tagged item under test")
        core.update_item(fake, id_raw=tagged, fields={"tags": "perf,api,cli"})

        for one in ("perf", "api", "cli"):
            result = query.list_items(fake, owner=OWNER, repo=REPO, filters={"tag": one})
            assert [i["id"] for i in result["data"]["items"]] == [tagged], one

    def test_read_your_writes_item_appears_immediately(self, fake):
        new_id = _file(fake, title="query: the fresh item under test")
        result = query.list_items(fake, owner=OWNER, repo=REPO, filters={"state": "all"})
        assert new_id in {i["id"] for i in result["data"]["items"]}

    def test_status_filter_refines_closed_shipped_vs_dropped(self, fake):
        shipped = _file(fake, title="query: the done item under test")
        dropped = _file(fake, title="query: the abandoned item under test")
        core.set_status(fake, id_raw=shipped, target="shipped")
        core.set_status(fake, id_raw=dropped, target="dropped")

        only_shipped = query.list_items(fake, owner=OWNER, repo=REPO, filters={"status": "shipped"})
        assert [i["id"] for i in only_shipped["data"]["items"]] == [shipped]
        only_dropped = query.list_items(fake, owner=OWNER, repo=REPO, filters={"status": "dropped"})
        assert [i["id"] for i in only_dropped["data"]["items"]] == [dropped]

    def test_unknown_status_filter_is_a_hard_reject(self, fake):
        result = query.list_items(fake, owner=OWNER, repo=REPO, filters={"status": "bogus"})
        assert result["status"] == "error"
        assert result["error"]["code"] == "validation"

    def test_assignee_none_and_star(self, fake):
        free = _file(fake, title="query: the free item under test")
        taken = _file(fake, title="query: the taken item under test")
        _assign(fake, taken, login="agent-a")

        unassigned = query.list_items(fake, owner=OWNER, repo=REPO, filters={"assignee": "none"})
        assert [i["id"] for i in unassigned["data"]["items"]] == [free]
        assigned = query.list_items(fake, owner=OWNER, repo=REPO, filters={"assignee": "*"})
        assert [i["id"] for i in assigned["data"]["items"]] == [taken]

    def test_pagination_slices_the_result(self, fake):
        ids = [_file(fake, title=f"query: the item {n} item under test") for n in range(3)]
        page1 = query.list_items(fake, owner=OWNER, repo=REPO, per_page=2, page=1)
        page2 = query.list_items(fake, owner=OWNER, repo=REPO, per_page=2, page=2)
        assert [i["id"] for i in page1["data"]["items"]] == ids[:2]
        assert [i["id"] for i in page2["data"]["items"]] == ids[2:]

    def test_sort_direction_desc(self, fake):
        ids = [_file(fake, title=f"query: the n{n} item under test") for n in range(3)]
        result = query.list_items(fake, owner=OWNER, repo=REPO, direction="desc")
        assert [i["id"] for i in result["data"]["items"]] == list(reversed(ids))


# --- QRY-1 edge: the observed 404-after-create replication window -------------


class TestSettleAfterCreate:
    def test_plain_get_does_not_retry_a_replication_404(self, fake):
        new_id = _file(fake, title="query: the fresh item under test")
        _owner, _repo, number = _split(new_id)
        fake.arm_replication_window(_owner, _repo, number, misses=1)
        # A plain get treats a 404 as not-found *now* (never dilutes the floor).
        result = core.get_item(fake, id_raw=new_id)
        assert result["status"] == "error" and result["error"]["code"] == "not_found"

    def test_settle_read_finds_item_after_bounded_retry(self, fake):
        new_id = _file(fake, title="query: the fresh item under test")
        _owner, _repo, number = _split(new_id)
        fake.arm_replication_window(_owner, _repo, number, misses=2)
        result = core.get_item(fake, id_raw=new_id, settle_retries=3, sleeper=NOSLEEP)
        assert result["status"] == "ok"
        assert result["data"]["id"] == new_id

    def test_settle_exhausted_surfaces_not_found(self, fake):
        new_id = _file(fake, title="query: the fresh item under test")
        _owner, _repo, number = _split(new_id)
        fake.arm_replication_window(_owner, _repo, number, misses=10)
        result = core.get_item(fake, id_raw=new_id, settle_retries=2, sleeper=NOSLEEP)
        assert result["status"] == "error" and result["error"]["code"] == "not_found"


# --- QRY-2: pick (cache-then-fan-out) ----------------------------------------


class TestPick:
    def test_returns_ready_work_with_a_why(self, fake, repo_dir):
        _file(fake, title="query: the ready item under test", stage="ready")
        _file(fake, title="query: the idea item under test", stage="idea")

        result = _pick(fake, repo_dir)
        assert result["status"] == "ok"
        cand = result["data"]["candidates"][0]
        assert cand["stage"] == "ready"
        # "no open blockers" → "no blockers recorded": the old wording reported an
        # empty dependency read as a verified all-clear. Not a relaxed assertion —
        # the distinction it used to blur is pinned by the two tests below.
        assert "no working branch" in cand["why"] and "no blockers recorded" in cand["why"]

    def test_why_says_recorded_not_clear_when_no_dependencies_exist(self, fake, repo_dir):
        """An empty native-dependency read is *absence of data*, never a clean
        bill of health.

        The markdown→Issues importer carries `related:` in the body and maps
        **nothing** to native `blocked_by`, so every migrated item reads back
        zero dependencies forever. A `why` that says "no open blockers" turns
        that guaranteed silence into a confident all-clear across an entire
        migrated backlog."""
        _file(fake, title="query: the ready item under test", stage="ready")
        cand = _pick(fake, repo_dir)["data"]["candidates"][0]
        assert "no blockers recorded" in cand["why"]
        assert "no open blockers" not in cand["why"]

    def test_why_distinguishes_a_genuinely_cleared_blocker(self, fake, repo_dir):
        """The other side of the same contract: when dependencies *were*
        recorded and are now closed, that IS a verified all-clear and must read
        differently from the no-data case above."""
        candidate = _file(fake, title="query: the was blocked item under test", stage="ready")
        blocker = _file(fake, title="query: the blocker item under test", stage="ready")
        core.link(fake, id_raw=candidate, edge="blocked-by", target_raw=blocker)
        core.set_status(fake, id_raw=blocker, target="shipped")

        picked = _pick(fake, repo_dir, limit=5)["data"]["candidates"]
        cleared = next(c for c in picked if c["id"] == candidate)
        assert "1 blocker closed" in cleared["why"]
        assert "no blockers recorded" not in cleared["why"]

    @pytest.mark.parametrize("backlog_size", [3, 12])
    def test_the_candidate_walk_does_not_grow_with_the_backlog(self, fake, repo_dir, backlog_size):
        """#230, which is what moved `pick` onto the store: the candidate set used
        to be a paginated scan of every open issue on *every* call, decoded in
        full to rank — measured at ~12.4s against ~209 issues, ~6x the latency
        floor.

        Two sizes, one number: the provider list traffic is the revalidation
        window and nothing else, so it is independent of how big the backlog is.
        Wall-clock is a build probe's business; what a unit test can pin is that
        the walk stopped scaling."""
        for i in range(backlog_size):
            _file(fake, title=f"query: the ready-{i} item under test", stage="ready")
        _sync(fake, repo_dir)  # the store is warm before the call under test

        fake.calls.clear()
        result = _pick(fake, repo_dir, limit=1)
        assert result["data"]["count"] == 1

        pages = [c for c in fake.calls if c[0] == "list_issues"]
        assert len(pages) == 1, f"expected only the revalidation window, got {pages}"
        # And it is the revalidation, not a ready-work query: `pick` never asks
        # the provider which items are ready.
        assert all("stage:ready" not in (page[4] or ()) for page in pages), pages

    def test_dependency_fanout_is_bounded_by_limit_not_by_backlog_size(self, fake, repo_dir):
        """PROBE-LAT / the N+1: `pick` must not pay one dependency read per
        *eligible* item when it was asked for one candidate. Ranking does not
        depend on blocker state, so the reads are taken lazily in rank order."""
        for i in range(12):
            _file(fake, title=f"query: the ready-{i} item under test", stage="ready")

        fake.calls.clear()
        result = _pick(fake, repo_dir, limit=1)
        assert result["data"]["count"] == 1

        fanout = [c for c in fake.calls if c[0] == "list_blocked_by"]
        assert len(fanout) == 1, f"expected one dependency read for limit=1, got {len(fanout)}"

    def test_fanout_still_walks_past_blocked_candidates_to_fill_the_limit(self, fake, repo_dir):
        """The laziness must not under-fill: if the top-ranked candidate is
        blocked, `pick` keeps reading down the ranking until `limit` is met."""
        blocked = _file(fake, title="blocked-and-first", stage="ready")
        blocker = _file(fake, title="query: the the blocker item under test", stage="ready")
        core.link(fake, id_raw=blocked, edge="blocked-by", target_raw=blocker)
        free = _file(fake, title="query: the free item under test", stage="ready")

        result = _pick(fake, repo_dir, limit=2)
        picked = [c["id"] for c in result["data"]["candidates"]]
        assert blocked not in picked
        assert len(picked) == 2 and free in picked and blocker in picked

    def test_failed_dependency_read_on_a_selected_candidate_still_errors(self, fake, repo_dir):
        """If the blocker predicate cannot be evaluated for a candidate `pick` is
        about to return, the call fails rather than returning it as ready. The
        predicate is never *assumed* for a returned candidate."""
        _file(fake, title="query: the ready item under test", stage="ready")

        def _boom(*_a, **_kw):
            raise OSError("dependency endpoint unreachable")

        fake.list_blocked_by = _boom
        result = _pick(fake, repo_dir, limit=1)
        assert result["status"] == "error"
        assert result["error"]["code"] == "unavailable"

    def test_failed_dependency_read_below_the_limit_does_not_fail_the_call(self, fake, repo_dir):
        """A dependency read that fails on an issue ranked below what `limit`
        needed is never taken, so it cannot fail the call."""
        first = _file(fake, title="query: the first item under test", stage="ready")
        for i in range(5):
            _file(fake, title=f"query: the later-{i} item under test", stage="ready")

        _real = fake.list_blocked_by
        _first_number = _split(first)[2]

        def _boom_except_first(owner, repo, number):
            if number != _first_number:
                raise OSError("dependency endpoint unreachable")
            return _real(owner, repo, number)

        fake.list_blocked_by = _boom_except_first
        result = _pick(fake, repo_dir, limit=1)
        assert result["status"] == "ok"
        assert [c["id"] for c in result["data"]["candidates"]] == [first]

    def test_ignores_non_ready_stage(self, fake, repo_dir):
        _file(fake, title="query: the idea item under test", stage="idea")
        _file(fake, title="query: the design item under test", stage="design")
        assert _pick(fake, repo_dir)["data"]["count"] == 0

    def test_open_blocker_excludes_candidate(self, fake, repo_dir):
        candidate = _file(fake, title="query: the blocked item under test", stage="ready")
        blocker = _file(fake, title="query: the blocker item under test", stage="ready")
        core.link(fake, id_raw=candidate, edge="blocked-by", target_raw=blocker)
        picked = {c["id"] for c in _pick(fake, repo_dir, limit=5)["data"]["candidates"]}
        assert candidate not in picked  # its blocker is open
        assert blocker in picked

    def test_closed_blocker_restores_candidate(self, fake, repo_dir):
        candidate = _file(fake, title="query: the was blocked item under test", stage="ready")
        blocker = _file(fake, title="query: the blocker item under test", stage="ready")
        core.link(fake, id_raw=candidate, edge="blocked-by", target_raw=blocker)
        core.set_status(fake, id_raw=blocker, target="shipped")
        picked = {c["id"] for c in _pick(fake, repo_dir, limit=5)["data"]["candidates"]}
        assert candidate in picked  # blocker now closed

    def test_cross_repo_open_blocker_is_judged_live_and_excludes(self, fake, repo_dir):
        candidate = _file(fake, title="query: the cross-blocked item under test", stage="ready")
        blocker = _file(fake, title="other-repo blocker", owner=OWNER, repo="other", stage="ready")
        core.link(fake, id_raw=candidate, edge="blocked-by", target_raw=blocker)

        picked = {c["id"] for c in _pick(fake, repo_dir, limit=5)["data"]["candidates"]}
        assert candidate not in picked  # cross-repo blocker open → not ready

        core.set_status(fake, id_raw=blocker, target="shipped")  # close it in the other repo
        picked_after = {c["id"] for c in _pick(fake, repo_dir, limit=5)["data"]["candidates"]}
        assert candidate in picked_after  # judged from a live read

    def test_a_stale_cache_cannot_let_a_blocked_item_through(self, fake, repo_dir):
        """QRY-2's negative, asserted directly. This is the whole reason the
        blocker predicate stayed live when the candidate predicate moved local.

        The cache is deliberately frozen after the blocker edge is added — no
        revalidation runs at all — so the store still holds the candidate exactly
        as it was when it was pickable. It is excluded anyway, because the edge is
        read from the provider and never from the store."""
        candidate = _file(fake, title="query: the blocked item under test", stage="ready")
        blocker = _file(fake, title="query: the blocker item under test", stage="ready")
        _sync(fake, repo_dir)  # the store learns both items while both are free
        core.link(fake, id_raw=candidate, edge="blocked-by", target_raw=blocker)

        def _no_revalidation(*_a, **_kw):
            raise TransportError("unavailable", "the provider is unreachable")

        fake.list_issues = _no_revalidation
        fake.list_issues_conditional = _no_revalidation
        result = _pick(fake, repo_dir, limit=5)

        assert result["status"] == "ok"
        assert candidate not in {c["id"] for c in result["data"]["candidates"]}
        assert any("not revalidated" in w for w in result["warnings"]), result["warnings"]

    def test_a_second_scopes_rows_are_never_offered_as_this_repos_ready_work(self, fake, repo_dir):
        """The QRY-2 negative failing by a second route, and the reason `pick` is
        the one query here that filters on scope.

        A candidate's issue *number* is handed to a live blocker read against the
        caller's owner/repo. A row from another repo would therefore be judged
        against whatever issue THIS repo happens to have at that number — and a
        genuinely blocked item can come back clear. The store holds one repo by
        design, but `replace_items` deletes all rows while leaving other scopes'
        cursor rows intact, so a two-scope store is three commands away."""
        mine = _file(fake, title="query: the item in this repo under test", stage="ready")
        other = _file(
            fake, title="query: the item in another repo", owner=OWNER, repo="other", stage="ready"
        )
        blocker = _file(fake, title="query: the blocker item under test", stage="ready")
        core.link(fake, id_raw=other, edge="blocked-by", target_raw=blocker)
        _sync(fake, repo_dir)
        # Force the two-scope store the eviction path allows.
        conn = cache.open_store(repo_dir, create=False)
        conn.execute(
            "INSERT OR REPLACE INTO item (id, title, status, stage, created_at, updated_at, fetched_at) "
            "VALUES (?, 'the other repo item', 'open', 'ready', ?, ?, ?)",
            (other, NOW.isoformat(), NOW.isoformat(), NOW.isoformat()),
        )
        conn.commit()
        conn.close()

        picked = [c["id"] for c in _pick(fake, repo_dir, limit=5)["data"]["candidates"]]

        assert other not in picked
        assert mine in picked and blocker in picked

    def test_an_unreachable_store_reports_unavailable_never_an_empty_pick(self, fake, repo_dir):
        """"Nothing to work on" and "I could not look" are the same output to a
        reader unless the envelope separates them."""
        _file(fake, title="query: the ready item under test", stage="ready")

        def _no_revalidation(*_a, **_kw):
            raise TransportError("unavailable", "the provider is unreachable")

        fake.list_issues = _no_revalidation
        result = _pick(fake, repo_dir)  # nothing ever synced AND nothing reachable

        assert result["status"] == "error"
        assert result["error"]["code"] == "unavailable"

    def test_every_answer_carries_the_stores_visible_age(self, fake, repo_dir):
        _file(fake, title="query: the ready item under test", stage="ready")
        result = _pick(fake, repo_dir)
        assert any("read from the backlog cache, confirmed" in w for w in result["warnings"])

    def test_a_working_branch_excludes_an_item_and_include_working_shows_it(self, fake, repo_dir):
        free = _file(fake, title="query: the free item under test", stage="ready")
        taken = _file(fake, title="query: the taken item under test", stage="ready")
        fake.push_branch(OWNER, REPO, "feat/in-flight")
        assert core.update_item(
            fake, id_raw=taken, fields={"working-branch": f"{OWNER}/{REPO}@feat/in-flight"}
        )["status"] == "ok"

        assert [c["id"] for c in _pick(fake, repo_dir, limit=5)["data"]["candidates"]] == [free]

        widened = _pick(fake, repo_dir, limit=5, include_working=True)["data"]["candidates"]
        by_id = {c["id"]: c for c in widened}
        assert set(by_id) == {free, taken}
        # The branch is NAMED, not merely flagged: naming it is what lets a reader
        # judge whether the work is live, which is the whole of the expiry policy
        # this field replaced.
        assert f"{OWNER}/{REPO}@feat/in-flight" in by_id[taken]["why"]

    def test_a_legacy_claimed_at_stamp_is_inert_and_never_excludes(self, fake, repo_dir):
        """ENC-4, asserted rather than assumed. Bodies written before the claim
        retirement still carry a `claimed_at` key; it is preserved as an unknown
        block field forever, and nothing keys on it — so an item whose only mark
        is a stale claim is ordinary ready work."""
        item = _file(fake, title="query: the legacy claimed item under test", stage="ready")
        _owner, _repo, number = _split(item)
        body = encode.upsert_block_field(
            fake.get_issue(_owner, _repo, number).get("body") or "",
            "claimed_at",
            (NOW - timedelta(hours=1)).isoformat(),
        )
        fake.update_issue(_owner, _repo, number, fields={"assignees": ["agent-b"], "body": body})

        assert [c["id"] for c in _pick(fake, repo_dir, limit=5)["data"]["candidates"]] == [item]

        # And the key survives a later write untouched (source order preserved).
        assert core.update_item(fake, id_raw=item, fields={"title": "query: the renamed item under test"})["status"] == "ok"
        after = encode.parse_block(fake.get_issue(_owner, _repo, number).get("body"))
        assert after.fields.get("claimed_at")

    def test_ranking_is_oldest_first(self, fake, repo_dir):
        newer = _file(fake, title="query: the newer item under test", stage="ready")
        older = _file(fake, title="query: the older item under test", stage="ready")
        _stamp_created(fake, newer, NOW - timedelta(days=2))
        _stamp_created(fake, older, NOW - timedelta(days=30))

        order = [c["id"] for c in _pick(fake, repo_dir, limit=5)["data"]["candidates"]]
        assert order == [older, newer]

    def test_limit_caps_candidates(self, fake, repo_dir):
        for n in range(3):
            _file(fake, title=f"query: the r{n} item under test", stage="ready")
        assert _pick(fake, repo_dir, limit=2)["data"]["count"] == 2

    def test_ignores_non_prawduct_ready_looking_issue(self, fake, repo_dir):
        _file(fake, title="query: the real ready item under test", stage="ready")
        fake.seed_labels(OWNER, REPO, ["stage:ready"])
        fake.create_issue(OWNER, REPO, title="query: the not ours item under test", body="plain", labels=[])
        result = _pick(fake, repo_dir, limit=5)
        assert {c["title"] for c in result["data"]["candidates"]} == {"query: the real ready item under test"}


# --- QRY-4: counts -----------------------------------------------------------


class TestCounts:
    def test_counts_by_status_and_stage_on_read(self, fake):
        _file(fake, title="query: the a item under test", stage="ready")
        _file(fake, title="query: the b item under test", stage="ready")
        shipped = _file(fake, title="query: the c item under test", stage="design")
        core.set_status(fake, id_raw=shipped, target="shipped")

        result = query.counts(fake, owner=OWNER, repo=REPO)
        assert result["status"] == "ok"
        assert result["data"]["total"] == 3
        assert result["data"]["by_status"] == {"open": 2, "shipped": 1}
        assert result["data"]["by_stage"] == {"design": 1, "ready": 2}

    def test_counts_report_non_prawduct_as_untriaged_rather_than_dropping_them(self, fake):
        # PROV-2 still governs `list`/decode — a plain issue is not an ITEM. But
        # on the repo nominated as the backlog service it is still backlog, and
        # dropping it from the rollup made the pending figure irreconcilable
        # with `gh issue list` while hiding the least-triaged work.
        _file(fake, title="query: the ours item under test", stage="ready")
        _plain(fake, title="query: the not ours item under test")
        result = query.counts(fake, owner=OWNER, repo=REPO)
        assert result["data"]["total"] == 2
        assert result["data"]["untriaged"] == 1


# --- PROV-2 ------------------------------------------------------------------


class TestProv2:
    def test_native_filed_item_with_no_facets_is_prawduct(self, fake):
        # A plain `file` (no facets) carries the prawduct block but no namespaced
        # label — the block is the marker.
        new_id = _file(fake, title="query: the no facets item under test")
        listed = query.list_items(fake, owner=OWNER, repo=REPO)
        assert new_id in {i["id"] for i in listed["data"]["items"]}

    def test_namespaced_label_marks_prawduct(self, fake):
        fake.seed_labels(OWNER, REPO, ["stage:ready"])
        issue = fake.create_issue(OWNER, REPO, title="query: the labelled item under test", body="no block", labels=["stage:ready"])
        assert encode.is_prawduct_issue(issue) is True

    def test_plain_issue_is_out_of_scope(self, fake):
        issue = fake.create_issue(OWNER, REPO, title="query: the plain item under test", body="just text", labels=[])
        assert encode.is_prawduct_issue(issue) is False
        listed = query.list_items(fake, owner=OWNER, repo=REPO, filters={"state": "all"})
        assert listed["data"]["count"] == 0  # ignored, not surfaced as malformed


# --- CLI front (thin) --------------------------------------------------------


class TestQueryCli:
    @pytest.fixture(autouse=True)
    def _project_dir(self, repo_dir):
        """Every CLI call runs against a real work tree: `pick` reaches the
        clone-shared store, so `project_dir` is no longer ignorable here."""
        self._dir = repo_dir

    def _run(self, fake, argv, capsys):
        import json

        code = cli.run(self._dir, [*argv, "--json"], transport=fake)
        out = capsys.readouterr().out
        return code, json.loads(out)

    def test_untriaged_flag_reaches_the_query_layer(self, fake, capsys):
        """The flag wiring itself — `--untriaged` must become
        filters["untriaged"], not be parsed and dropped."""
        _file(fake, title="query: the ours item under test", stage="ready")
        plain_id = _plain(fake, title="query: the human report item under test")
        code, env = self._run(fake, ["list", "--repo", "octo/repo", "--untriaged"], capsys)
        assert code == 0
        assert [i["id"] for i in env["data"]["items"]] == [plain_id]

    def test_untriaged_refuses_an_explicit_page_request(self, fake, capsys):
        """It always full-scans, so honouring --page is impossible; returning
        the whole set to someone who asked for page 2 would be a confident
        wrong answer, so it refuses instead of ignoring."""
        for flag in (["--page", "2"], ["--per-page", "10"]):
            code, env = self._run(
                fake, ["list", "--repo", "octo/repo", "--untriaged", *flag], capsys
            )
            assert code == 2, flag
            assert env["error"]["code"] == "validation"
            assert "--untriaged" in env["error"]["message"]

    def test_counts_human_output_prints_a_runnable_drill_down(self, fake, capsys):
        """The emitted command is copy-pasted by an operator, so it carries the
        binary name. `backlog list …` alone is not a command."""
        _plain(fake, title="query: the human report item under test")
        cli.run(None, ["counts", "--repo", "octo/repo"], transport=fake)
        out = capsys.readouterr().out
        assert "untriaged: 1 issue(s)" in out
        assert "prawduct-hook backlog list --repo octo/repo --untriaged" in out

    def test_counts_human_output_stays_silent_with_nothing_untriaged(self, fake, capsys):
        """Surface by exception: a zero line is noise on every future run."""
        _file(fake, title="query: the ours item under test", stage="ready")
        cli.run(None, ["counts", "--repo", "octo/repo"], transport=fake)
        assert "untriaged" not in capsys.readouterr().out

    def test_list_requires_repo(self, fake, capsys):
        code, env = self._run(fake, ["list"], capsys)
        assert code == 2 and env["error"]["code"] == "validation"

    def test_list_and_pick_and_counts_round_trip(self, fake, capsys):
        _file(fake, title="query: the ready item under test", stage="ready")
        code, listed = self._run(fake, ["list", "--repo", "octo/repo", "--stage", "ready"], capsys)
        assert code == 0 and listed["data"]["count"] == 1
        code, picked = self._run(fake, ["pick", "--repo", "octo/repo"], capsys)
        assert code == 0 and picked["data"]["count"] == 1
        code, counted = self._run(fake, ["counts", "--repo", "octo/repo"], capsys)
        assert code == 0 and counted["data"]["total"] == 1

    def test_bad_int_flag_is_validation_error(self, fake, capsys):
        code, env = self._run(fake, ["pick", "--repo", "octo/repo", "--limit", "xx"], capsys)
        assert code == 2 and env["error"]["code"] == "validation"


class TestUntriagedIssuesAreCounted:
    """An issue with no prawduct label and no ``prawduct:`` block used to be
    absent from the rollup entirely, so the pending figure could not be
    reconciled against ``gh issue list --state open`` — and the items nobody had
    triaged were the only ones the tooling could not see. Human-filed reports
    and reports from consuming products arrive in exactly that shape.
    """

    def test_untriaged_issue_is_counted_not_skipped(self, fake):
        _file(fake, title="query: the ours item under test", stage="ready")
        _plain(fake, title="filed by a human")
        data = query.counts(fake, owner=OWNER, repo=REPO)["data"]
        assert data["total"] == 2
        assert data["by_status"]["open"] == 2
        assert data["untriaged"] == 1

    def test_untriaged_is_a_subset_of_by_status_never_an_addend(self, fake):
        """Double-counting would make the figure wrong in the other direction —
        these issues have a real GitHub state and decode like any other."""
        for i in range(3):
            _plain(fake, title=f"query: the untriaged {i} item under test")
        data = query.counts(fake, owner=OWNER, repo=REPO)["data"]
        assert data["untriaged"] == 3
        assert sum(data["by_status"].values()) == data["total"] == 3

    def test_no_untriaged_issues_reports_zero_not_absent(self, fake):
        _file(fake, title="query: the ours item under test", stage="ready")
        assert query.counts(fake, owner=OWNER, repo=REPO)["data"]["untriaged"] == 0

    def test_pull_requests_are_never_untriaged_items(self, fake):
        """PRs interleave the REST issues list and carry no block either — a
        naive "no block means untriaged" count would report every PR in the
        repo as backlog."""
        fake.seed_pull_requests(OWNER, REPO, 4, state="open")
        _file(fake, title="query: the ours item under test", stage="ready")
        data = query.counts(fake, owner=OWNER, repo=REPO)["data"]
        assert data["untriaged"] == 0
        assert data["total"] == 1

    def test_untriaged_issue_does_not_produce_decode_warnings(self, fake):
        """It has no encoding, so it cannot have a malformed one — warning here
        would report every ordinary GitHub issue as damaged."""
        _plain(fake, title="query: the human report item under test")
        assert query.counts(fake, owner=OWNER, repo=REPO)["warnings"] == []

    def test_closed_untriaged_issues_are_not_counted_as_awaiting_triage(self):
        """`untriaged` counts OPEN issues only, while total/by_status span every
        state. A closed issue has been dispositioned — nobody needs to triage
        it — and counting it would inflate a number whose whole meaning is
        "work waiting", and disagree with the drill-down command printed one
        line beneath it, which defaults to open."""
        class _Fake:
            def list_issues(self, owner, repo, *, state, per_page, page, labels=None, **kw):
                if page > 1:
                    return []
                return [
                    {"number": 1, "body": "no block", "labels": [], "state": "open"},
                    {"number": 2, "body": "no block", "labels": [], "state": "closed"},
                ]

        data = query.counts(_Fake(), owner=OWNER, repo=REPO)["data"]
        assert data["total"] == 2       # both counted in the corpus
        assert data["untriaged"] == 1   # only the open one awaits triage

    def test_list_untriaged_scans_every_page_not_just_the_first(self, fake):
        """Untriaged items are typically the NEWEST, so an ascending first page
        is exactly where they are not. Returning page 1 would answer "nothing
        to triage" while items waited on page 2 — a short answer
        indistinguishable from a complete one."""
        for i in range(120):  # push the untriaged issue past raw page 1
            _file(fake, title=f"query: the ours {i} item under test", stage="ready")
        plain_id = _plain(fake, title="filed last, invisible on page 1")

        first_page = query.list_items(
            fake, owner=OWNER, repo=REPO, filters={}, per_page=100, page=1
        )
        assert plain_id not in [i["id"] for i in first_page["data"]["items"]]

        result = query.list_items(fake, owner=OWNER, repo=REPO, filters={"untriaged": True})
        assert [i["id"] for i in result["data"]["items"]] == [plain_id]
        assert result["data"]["has_more"] is False

    def test_list_untriaged_shows_exactly_what_list_drops(self, fake):
        _file(fake, title="query: the ours item under test", stage="ready")
        plain_id = _plain(fake, title="query: the human report item under test")
        fake.seed_pull_requests(OWNER, REPO, 2, state="open")

        normal = query.list_items(fake, owner=OWNER, repo=REPO, filters={})
        untriaged = query.list_items(
            fake, owner=OWNER, repo=REPO, filters={"untriaged": True}
        )
        assert [i["id"] for i in untriaged["data"]["items"]] == [plain_id]
        assert plain_id not in [i["id"] for i in normal["data"]["items"]]
        assert untriaged["data"]["count"] == 1  # no PRs


class TestTheUncollectedCallersStayBound:
    """`tests/spikes/` is hand-run `__main__` code pytest never collects, so a
    signature change there fails at the moment an operator runs the measurement —
    not in CI, and not in the commit that caused it.

    That matters for `pick` specifically because `backlog-service-nfr.md` §§3.5
    and 9 name S2 as the owner of the fan-out measurement and explicitly schedule
    a re-run. A green suite is not evidence about it, so the binding is asserted
    here instead: parse the call, bind its keywords against the live signature.
    Binding, not grepping — a grep for `project_dir` would pass on a call that
    passed it positionally or misspelled another argument.
    """

    def _pick_calls(self):
        import ast

        spikes = sorted((Path(__file__).resolve().parent / "spikes").glob("*.py"))
        assert spikes, "no spike scripts found — this guard would pass vacuously"
        for path in spikes:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "pick":
                    yield path.name, node

    def test_every_spike_call_to_pick_binds_the_current_signature(self):
        import inspect

        signature = inspect.signature(query.pick)
        calls = list(self._pick_calls())
        assert calls, "no `pick` call found in tests/spikes — the guard is vacuous"
        for name, node in calls:
            kwargs = {kw.arg: object() for kw in node.keywords if kw.arg}
            positional = [object()] * len(node.args)
            signature.bind(*positional, **kwargs)  # raises TypeError on a stale call
