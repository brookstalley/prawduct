"""Tests for lib/backlog/query.py — list / pick / counts (Chunk 03, L1).

Covers the ready-work read side against the transport-seam fake:
- QRY-1 structured, online, strongly-consistent-in-practice ``list`` + the
  observed 404-after-create replication window (bounded settle-retry).
- QRY-2 ``pick`` list-then-fan-out: blocker (incl. **cross-repo**) + claim-TTL
  predicates, ranking, and the ``--claim`` take.
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

from lib.backlog import cli, core, encode, query  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402

OWNER, REPO = "octo", "repo"
NOW = datetime(2026, 7, 17, 12, 0, 0, tzinfo=timezone.utc)
NOSLEEP = lambda _attempt: None  # noqa: E731 — deterministic no-wait settle in tests


@pytest.fixture
def fake():
    return FakeGitHub(user={"login": "agent-a", "id": 1})


def _file(fake, *, title="t", body="b", owner=OWNER, repo=REPO, **facets):
    """File a prawduct item through core (labels auto-provisioned); return its id."""
    result = core.file_item(fake, owner=owner, repo=repo, title=title, body=body, facets=facets)
    assert result["status"] == "ok", result
    return result["data"]["id"]


def _plain(fake, *, title="plain", body="just a normal issue", owner=OWNER, repo=REPO):
    """Create a non-prawduct issue (no block, no namespaced label) — out of scope."""
    issue = fake.create_issue(owner, repo, title=title, body=body, labels=[])
    return f"{owner}/{repo}#{issue['number']}"


def _stamp_claim(fake, id_raw, *, login, when):
    """Directly stamp an assignee + claimed_at on an item (bypass the claim op) so
    pick/claim TTL behaviour can be exercised at a controlled age."""
    _owner, _repo, number = _split(id_raw)
    issue = fake.get_issue(_owner, _repo, number)
    body = encode.upsert_block_field(issue.get("body") or "", "claimed_at", when.isoformat())
    fake.update_issue(_owner, _repo, number, fields={"assignees": [login], "body": body})


def _split(id_raw):
    owner_repo, _, number = id_raw.partition("#")
    owner, _, repo = owner_repo.partition("/")
    return owner, repo, int(number)


# --- QRY-1: list -------------------------------------------------------------


class TestList:
    def test_structured_filter_returns_matching_prawduct_items(self, fake):
        _file(fake, title="ready one", stage="ready")
        _file(fake, title="ready two", stage="ready")
        _file(fake, title="in design", stage="design")

        result = query.list_items(fake, owner=OWNER, repo=REPO, filters={"stage": "ready"})
        assert result["status"] == "ok"
        assert result["data"]["count"] == 2
        assert {i["title"] for i in result["data"]["items"]} == {"ready one", "ready two"}

    def test_read_your_writes_item_appears_immediately(self, fake):
        new_id = _file(fake, title="fresh")
        result = query.list_items(fake, owner=OWNER, repo=REPO, filters={"state": "all"})
        assert new_id in {i["id"] for i in result["data"]["items"]}

    def test_status_filter_refines_closed_shipped_vs_dropped(self, fake):
        shipped = _file(fake, title="done")
        dropped = _file(fake, title="abandoned")
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
        free = _file(fake, title="free")
        taken = _file(fake, title="taken")
        _stamp_claim(fake, taken, login="agent-a", when=NOW)

        unassigned = query.list_items(fake, owner=OWNER, repo=REPO, filters={"assignee": "none"})
        assert [i["id"] for i in unassigned["data"]["items"]] == [free]
        assigned = query.list_items(fake, owner=OWNER, repo=REPO, filters={"assignee": "*"})
        assert [i["id"] for i in assigned["data"]["items"]] == [taken]

    def test_pagination_slices_the_result(self, fake):
        ids = [_file(fake, title=f"item {n}") for n in range(3)]
        page1 = query.list_items(fake, owner=OWNER, repo=REPO, per_page=2, page=1)
        page2 = query.list_items(fake, owner=OWNER, repo=REPO, per_page=2, page=2)
        assert [i["id"] for i in page1["data"]["items"]] == ids[:2]
        assert [i["id"] for i in page2["data"]["items"]] == ids[2:]

    def test_sort_direction_desc(self, fake):
        ids = [_file(fake, title=f"n{n}") for n in range(3)]
        result = query.list_items(fake, owner=OWNER, repo=REPO, direction="desc")
        assert [i["id"] for i in result["data"]["items"]] == list(reversed(ids))


# --- QRY-1 edge: the observed 404-after-create replication window -------------


class TestSettleAfterCreate:
    def test_plain_get_does_not_retry_a_replication_404(self, fake):
        new_id = _file(fake, title="fresh")
        _owner, _repo, number = _split(new_id)
        fake.arm_replication_window(_owner, _repo, number, misses=1)
        # A plain get treats a 404 as not-found *now* (never dilutes the floor).
        result = core.get_item(fake, id_raw=new_id)
        assert result["status"] == "error" and result["error"]["code"] == "not_found"

    def test_settle_read_finds_item_after_bounded_retry(self, fake):
        new_id = _file(fake, title="fresh")
        _owner, _repo, number = _split(new_id)
        fake.arm_replication_window(_owner, _repo, number, misses=2)
        result = core.get_item(fake, id_raw=new_id, settle_retries=3, sleeper=NOSLEEP)
        assert result["status"] == "ok"
        assert result["data"]["id"] == new_id

    def test_settle_exhausted_surfaces_not_found(self, fake):
        new_id = _file(fake, title="fresh")
        _owner, _repo, number = _split(new_id)
        fake.arm_replication_window(_owner, _repo, number, misses=10)
        result = core.get_item(fake, id_raw=new_id, settle_retries=2, sleeper=NOSLEEP)
        assert result["status"] == "error" and result["error"]["code"] == "not_found"


# --- QRY-2: pick (list-then-fan-out) -----------------------------------------


class TestPick:
    def test_returns_ready_unassigned_with_a_why(self, fake):
        _file(fake, title="ready", stage="ready")
        result = query.pick(fake, owner=OWNER, repo=REPO, now=NOW)
        assert result["status"] == "ok"
        cand = result["data"]["candidates"][0]
        assert cand["stage"] == "ready"
        assert cand["reap_eligible"] is False
        # "no open blockers" → "no blockers recorded": the old wording reported an
        # empty dependency read as a verified all-clear. Not a relaxed assertion —
        # the distinction it used to blur is now pinned by the two tests below.
        assert "unassigned" in cand["why"] and "no blockers recorded" in cand["why"]

    def test_why_says_recorded_not_clear_when_no_dependencies_exist(self, fake):
        """An empty native-dependency read is *absence of data*, never a clean
        bill of health.

        The markdown→Issues importer carries `related:` in the body and maps
        **nothing** to native `blocked_by`, so every migrated item reads back
        zero dependencies forever. A `why` that says "no open blockers" turns
        that guaranteed silence into a confident all-clear across an entire
        migrated backlog."""
        _file(fake, title="ready", stage="ready")
        cand = query.pick(fake, owner=OWNER, repo=REPO, now=NOW)["data"]["candidates"][0]
        assert "no blockers recorded" in cand["why"]
        assert "no open blockers" not in cand["why"]

    def test_why_distinguishes_a_genuinely_cleared_blocker(self, fake):
        """The other side of the same contract: when dependencies *were*
        recorded and are now closed, that IS a verified all-clear and must read
        differently from the no-data case above."""
        candidate = _file(fake, title="was blocked", stage="ready")
        blocker = _file(fake, title="blocker", stage="ready")
        core.link(fake, id_raw=candidate, edge="blocked-by", target_raw=blocker)
        core.set_status(fake, id_raw=blocker, target="shipped")

        picked = query.pick(fake, owner=OWNER, repo=REPO, limit=5, now=NOW)["data"]["candidates"]
        cleared = next(c for c in picked if c["id"] == candidate)
        assert "1 blocker closed" in cleared["why"]
        assert "no blockers recorded" not in cleared["why"]

    def test_dependency_fanout_is_bounded_by_limit_not_by_backlog_size(self, fake):
        """PROBE-LAT / the N+1: `pick` must not pay one dependency read per
        *eligible* item when it was asked for one candidate.

        The fan-out used to run over every eligible issue before `limit` was
        applied, so a 170-item migrated backlog cost 170 REST calls on every
        pick regardless of `--limit`. Ranking does not depend on blocker state,
        so the reads can be taken lazily in rank order."""
        for i in range(12):
            _file(fake, title=f"ready-{i}", stage="ready")

        fake.calls.clear()
        result = query.pick(fake, owner=OWNER, repo=REPO, limit=1, now=NOW)
        assert result["data"]["count"] == 1

        fanout = [c for c in fake.calls if c[0] == "list_blocked_by"]
        assert len(fanout) == 1, f"expected one dependency read for limit=1, got {len(fanout)}"

    def test_fanout_still_walks_past_blocked_candidates_to_fill_the_limit(self, fake):
        """The laziness must not under-fill: if the top-ranked candidate is
        blocked, `pick` keeps reading down the ranking until `limit` is met."""
        blocked = _file(fake, title="blocked-and-first", stage="ready")
        blocker = _file(fake, title="the blocker", stage="ready")
        core.link(fake, id_raw=blocked, edge="blocked-by", target_raw=blocker)
        free = _file(fake, title="free", stage="ready")

        result = query.pick(fake, owner=OWNER, repo=REPO, limit=2, now=NOW)
        picked = [c["id"] for c in result["data"]["candidates"]]
        assert blocked not in picked
        assert len(picked) == 2 and free in picked and blocker in picked

    def test_failed_dependency_read_on_a_selected_candidate_still_errors(self, fake):
        """The property that must NOT have changed with the lazy fan-out: if the
        blocker predicate cannot be evaluated for a candidate `pick` is about to
        return, the call fails rather than returning it as ready. The predicate
        is never *assumed* for a returned candidate."""
        _file(fake, title="ready", stage="ready")

        def _boom(*_a, **_kw):
            raise OSError("dependency endpoint unreachable")

        fake.list_blocked_by = _boom
        result = query.pick(fake, owner=OWNER, repo=REPO, limit=1, now=NOW)
        assert result["status"] == "error"
        assert result["error"]["code"] == "unavailable"

    def test_failed_dependency_read_below_the_limit_does_not_fail_the_call(self, fake):
        """The deliberate semantics change riding with the lazy fan-out: a
        dependency read that fails on an issue ranked below what `limit` needed
        is never taken, so it cannot fail the call. Previously any eligible
        issue's unreachable dependency failed the whole pick — including issues
        the caller was never going to see."""
        first = _file(fake, title="first", stage="ready")
        for i in range(5):
            _file(fake, title=f"later-{i}", stage="ready")

        _real = fake.list_blocked_by
        _first_number = _split(first)[2]

        def _boom_except_first(owner, repo, number):
            if number != _first_number:
                raise OSError("dependency endpoint unreachable")
            return _real(owner, repo, number)

        fake.list_blocked_by = _boom_except_first
        result = query.pick(fake, owner=OWNER, repo=REPO, limit=1, now=NOW)
        assert result["status"] == "ok"
        assert [c["id"] for c in result["data"]["candidates"]] == [first]

    def test_ignores_non_ready_stage(self, fake):
        _file(fake, title="idea", stage="idea")
        _file(fake, title="design", stage="design")
        result = query.pick(fake, owner=OWNER, repo=REPO, now=NOW)
        assert result["data"]["count"] == 0

    def test_open_blocker_excludes_candidate(self, fake):
        candidate = _file(fake, title="blocked", stage="ready")
        blocker = _file(fake, title="blocker", stage="ready")
        core.link(fake, id_raw=candidate, edge="blocked-by", target_raw=blocker)
        picked = {c["id"] for c in query.pick(fake, owner=OWNER, repo=REPO, limit=5, now=NOW)["data"]["candidates"]}
        assert candidate not in picked  # its blocker is open
        assert blocker in picked

    def test_closed_blocker_restores_candidate(self, fake):
        candidate = _file(fake, title="was blocked", stage="ready")
        blocker = _file(fake, title="blocker", stage="ready")
        core.link(fake, id_raw=candidate, edge="blocked-by", target_raw=blocker)
        core.set_status(fake, id_raw=blocker, target="shipped")
        picked = {c["id"] for c in query.pick(fake, owner=OWNER, repo=REPO, limit=5, now=NOW)["data"]["candidates"]}
        assert candidate in picked  # blocker now closed

    def test_cross_repo_open_blocker_is_judged_live_and_excludes(self, fake):
        candidate = _file(fake, title="cross-blocked", stage="ready")
        blocker = _file(fake, title="other-repo blocker", owner=OWNER, repo="other", stage="ready")
        core.link(fake, id_raw=candidate, edge="blocked-by", target_raw=blocker)

        picked = {c["id"] for c in query.pick(fake, owner=OWNER, repo=REPO, limit=5, now=NOW)["data"]["candidates"]}
        assert candidate not in picked  # cross-repo blocker open → not ready

        core.set_status(fake, id_raw=blocker, target="shipped")  # close it in the other repo
        picked_after = {c["id"] for c in query.pick(fake, owner=OWNER, repo=REPO, limit=5, now=NOW)["data"]["candidates"]}
        assert candidate in picked_after  # judged from a live read

    def test_live_claim_excludes_stale_claim_reap_eligible(self, fake):
        live = _file(fake, title="live claim", stage="ready")
        stale = _file(fake, title="stale claim", stage="ready")
        _stamp_claim(fake, live, login="agent-b", when=NOW - timedelta(hours=1))
        _stamp_claim(fake, stale, login="agent-b", when=NOW - timedelta(days=2))

        result = query.pick(fake, owner=OWNER, repo=REPO, limit=5, now=NOW)
        by_id = {c["id"]: c for c in result["data"]["candidates"]}
        assert live not in by_id  # a live claim is not ready work
        assert stale in by_id and by_id[stale]["reap_eligible"] is True
        assert "stale claim by agent-b" in by_id[stale]["why"]

    def test_ranking_prefers_free_then_oldest(self, fake):
        free_new = _file(fake, title="free new", stage="ready")
        free_old = _file(fake, title="free old", stage="ready")
        stale = _file(fake, title="stale", stage="ready")
        _stamp_claim(fake, stale, login="agent-b", when=NOW - timedelta(days=2))
        # File order is #1 free_new, #2 free_old, #3 stale; ranking = free before
        # reap, then issue-number asc.
        order = [c["id"] for c in query.pick(fake, owner=OWNER, repo=REPO, limit=5, now=NOW)["data"]["candidates"]]
        assert order == [free_new, free_old, stale]

    def test_limit_caps_candidates(self, fake):
        for n in range(3):
            _file(fake, title=f"r{n}", stage="ready")
        result = query.pick(fake, owner=OWNER, repo=REPO, limit=2, now=NOW)
        assert result["data"]["count"] == 2

    def test_ignores_non_prawduct_ready_looking_issue(self, fake):
        _file(fake, title="real ready", stage="ready")
        # A plain issue that happens to carry a stage:ready label but no prawduct
        # marker block is still ours (label is a marker) — so instead assert a
        # truly-unmarked issue is ignored even if listed.
        fake.seed_labels(OWNER, REPO, ["stage:ready"])
        fake.create_issue(OWNER, REPO, title="not ours", body="plain", labels=[])
        result = query.pick(fake, owner=OWNER, repo=REPO, limit=5, now=NOW)
        assert {c["title"] for c in result["data"]["candidates"]} == {"real ready"}

    def test_claim_option_takes_top_candidate(self, fake):
        _file(fake, title="take me", stage="ready")
        result = query.pick(fake, owner=OWNER, repo=REPO, claim=True, now=NOW, default_owner=OWNER)
        top = result["data"]["candidates"][0]
        assert top["claimed"] is True
        assert top["assignee"] == "agent-a"
        assert top["claimed_at"]  # fresh stamp reflected in the returned candidate

    def test_claim_option_conflict_surfaces_for_repick(self, fake):
        target = _file(fake, title="contended", stage="ready")
        _stamp_claim(fake, target, login="agent-b", when=NOW)  # a live claim by another
        result = query.pick(fake, owner=OWNER, repo=REPO, claim=True, now=NOW, default_owner=OWNER)
        # The only ready item is live-claimed → not a candidate → nothing to claim.
        assert result["data"]["count"] == 0


# --- QRY-4: counts -----------------------------------------------------------


class TestCounts:
    def test_counts_by_status_and_stage_on_read(self, fake):
        _file(fake, title="a", stage="ready")
        _file(fake, title="b", stage="ready")
        shipped = _file(fake, title="c", stage="design")
        core.set_status(fake, id_raw=shipped, target="shipped")

        result = query.counts(fake, owner=OWNER, repo=REPO)
        assert result["status"] == "ok"
        assert result["data"]["total"] == 3
        assert result["data"]["by_status"] == {"open": 2, "shipped": 1}
        assert result["data"]["by_stage"] == {"design": 1, "ready": 2}

    def test_counts_ignore_non_prawduct(self, fake):
        _file(fake, title="ours", stage="ready")
        _plain(fake, title="not ours")
        result = query.counts(fake, owner=OWNER, repo=REPO)
        assert result["data"]["total"] == 1


# --- PROV-2 ------------------------------------------------------------------


class TestProv2:
    def test_native_filed_item_with_no_facets_is_prawduct(self, fake):
        # A plain `file` (no facets) carries the prawduct block but no namespaced
        # label — the block is the marker.
        new_id = _file(fake, title="no facets")
        listed = query.list_items(fake, owner=OWNER, repo=REPO)
        assert new_id in {i["id"] for i in listed["data"]["items"]}

    def test_namespaced_label_marks_prawduct(self, fake):
        fake.seed_labels(OWNER, REPO, ["stage:ready"])
        issue = fake.create_issue(OWNER, REPO, title="labelled", body="no block", labels=["stage:ready"])
        assert encode.is_prawduct_issue(issue) is True

    def test_plain_issue_is_out_of_scope(self, fake):
        issue = fake.create_issue(OWNER, REPO, title="plain", body="just text", labels=[])
        assert encode.is_prawduct_issue(issue) is False
        listed = query.list_items(fake, owner=OWNER, repo=REPO, filters={"state": "all"})
        assert listed["data"]["count"] == 0  # ignored, not surfaced as malformed


# --- CLI front (thin) --------------------------------------------------------


class TestQueryCli:
    def _run(self, fake, argv, capsys):
        import json

        code = cli.run(None, [*argv, "--json"], transport=fake)
        out = capsys.readouterr().out
        return code, json.loads(out)

    def test_list_requires_repo(self, fake, capsys):
        code, env = self._run(fake, ["list"], capsys)
        assert code == 2 and env["error"]["code"] == "validation"

    def test_list_and_pick_and_counts_round_trip(self, fake, capsys):
        _file(fake, title="ready", stage="ready")
        code, listed = self._run(fake, ["list", "--repo", "octo/repo", "--stage", "ready"], capsys)
        assert code == 0 and listed["data"]["count"] == 1
        code, picked = self._run(fake, ["pick", "--repo", "octo/repo"], capsys)
        assert code == 0 and picked["data"]["count"] == 1
        code, counted = self._run(fake, ["counts", "--repo", "octo/repo"], capsys)
        assert code == 0 and counted["data"]["total"] == 1

    def test_bad_int_flag_is_validation_error(self, fake, capsys):
        code, env = self._run(fake, ["pick", "--repo", "octo/repo", "--limit", "xx"], capsys)
        assert code == 2 and env["error"]["code"] == "validation"
