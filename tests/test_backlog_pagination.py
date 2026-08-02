"""Pagination correctness — the two pre-migration transport blockers (L1).

**BKL-2V6N:** ``gh --paginate`` emits each page as a SEPARATE JSON document, so
a single ``json.loads`` fails past one page. ``_api_paged`` replaces it with an
explicit ``per_page``/``page`` loop — these tests pin per-page requests, raw
short-page termination, and the ``transport.MAX_PAGES`` backstop for
``list_labels`` / ``list_timeline`` / ``list_sub_issues``.

**BKL-6W9R:** that loop was one of *four* near-identical ones carrying three
different caps (100/100/1000) and three different cap-trip behaviours, none of
which failed loud — so a truncated result was indistinguishable from a complete
one, worst of all in ``export``, the backup path. All four now route through
``transport.paginate``, and a cap trip raises rather than returning a prefix.

**BKL-5T3J:** the REST issues list interleaves pull requests. The transport now
returns pages RAW (a ``pull_request`` key marks PRs) so every
``len(batch) < per_page`` terminator reads the true page length; PRs leave the
pipeline at the decode boundary (``encode.is_prawduct_issue``) or explicit
guards on label-keyed lookups. These tests seed a PR-heavy fake repo (the real
target's shape: 127+ PRs) and pin that export/counts/list/pick/alias paths see
every page and never mistake a labeled PR for an item.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.backlog import cli, core, encode, migrate, query  # noqa: E402
from lib.backlog import transport as tp  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402

OWNER, REPO = "octo", "backlog"


@pytest.fixture
def fake():
    return FakeGitHub(user={"login": "agent-a", "id": 1})


def _issue_with_alias(fake, pfx: str, *, title: str) -> int:
    fake.seed_labels(OWNER, REPO, [f"id:{pfx}", "stage:ready", "area:cli"])
    issue = fake.create_issue(
        OWNER, REPO,
        title=title,
        body=f"Body.\n\n```prawduct\nv: 1\nid_aliases: [{pfx}]\n```\n",
        labels=[f"id:{pfx}", "stage:ready", "area:cli"],
    )
    return issue["number"]


# --- BKL-2V6N: explicit page loop replaces --paginate ------------------------


class _PagedGh(tp.GhTransport):
    """GhTransport with ``_run`` replaced by an in-memory page server."""

    def __init__(self, dataset: list):
        self.dataset = dataset
        self.requests: list[str] = []

    def _run(self, args, *, input_json=None):
        path = args[1]
        self.requests.append(path)
        query_str = path.split("?", 1)[1]
        params = dict(pair.split("=") for pair in query_str.split("&"))
        per_page = int(params["per_page"])
        page = int(params["page"])
        start = (page - 1) * per_page
        return json.dumps(self.dataset[start : start + per_page])


class TestApiPaged:
    def test_multi_page_collects_everything(self):
        # 150 labels — exactly the shape --paginate could not parse (BKL-2V6N).
        gh = _PagedGh([{"name": f"id:PFX-{i:04d}"} for i in range(150)])
        labels = gh.list_labels(OWNER, REPO)
        assert len(labels) == 150
        assert len(gh.requests) == 2  # full page + short page
        assert "per_page=100&page=1" in gh.requests[0]
        assert "per_page=100&page=2" in gh.requests[1]
        assert "--paginate" not in " ".join(gh.requests)

    def test_exact_page_boundary_needs_one_extra_probe(self):
        gh = _PagedGh([{"name": f"l{i}"} for i in range(100)])
        assert len(gh.list_labels(OWNER, REPO)) == 100
        assert len(gh.requests) == 2  # the second (empty) page is the terminator

    def test_single_short_page_terminates_immediately(self):
        gh = _PagedGh([{"name": "one"}])
        assert len(gh.list_labels(OWNER, REPO)) == 1
        assert len(gh.requests) == 1

    def test_timeline_and_sub_issues_use_the_loop(self):
        events = [{"event": "labeled", "actor": {"login": "a"}, "created_at": "t"}] * 120
        gh = _PagedGh(events)
        assert len(gh.list_timeline(OWNER, REPO, 1)) == 120
        gh2 = _PagedGh(
            [{"number": i, "repository": {"owner": {"login": "o"}, "name": "r"}}
             for i in range(105)]
        )
        assert len(gh2.list_sub_issues(OWNER, REPO, 1)) == 105

    def test_page_cap_raises_rather_than_returning_a_prefix(self):
        """A cap trip is a failure, not a short answer. Returning the collected
        prefix made a truncated result indistinguishable from a complete one —
        a well-formed short list the caller has no way to question."""
        class _Endless(_PagedGh):
            def _run(self, args, *, input_json=None):
                self.requests.append(args[1])
                return json.dumps([{"name": "x"}] * 100)  # always a full page

        gh = _Endless([])
        with pytest.raises(tp.TransportError) as exc:
            gh.list_labels(OWNER, REPO)
        assert len(gh.requests) == tp.MAX_PAGES
        assert exc.value.code == "unavailable"
        assert "truncated" in exc.value.message
        assert exc.value.details["max_pages"] == tp.MAX_PAGES


# --- BKL-5T3J: raw pages + decode-layer PR filtering -------------------------


class TestPrInterleaving:
    def test_is_prawduct_issue_rejects_a_labeled_pr(self):
        pr = {
            "number": 9,
            "labels": [{"name": "stage:ready"}],
            "body": "```prawduct\nv: 1\n```",
            "pull_request": {"url": "..."},
        }
        assert encode.is_prawduct_issue(pr) is False
        without = dict(pr)
        del without["pull_request"]
        assert encode.is_prawduct_issue(without) is True

    def test_export_scan_walks_past_pr_heavy_pages(self, fake, tmp_path):
        # The real target's shape: the oldest ~127 entries are closed PRs, so
        # page 1 raw is PR-dominated. The old filtered terminator stopped there
        # and the MG2 backup silently truncated.
        fake.seed_pull_requests(OWNER, REPO, 127)
        numbers = [
            _issue_with_alias(fake, f"DIS-{i:04d}", title=f"item {i}") for i in range(5)
        ]
        assert numbers[-1] > 100  # the items genuinely live past raw page 1
        result = migrate.export_backlog(fake, owner=OWNER, repo=REPO, dest=tmp_path)
        assert result["status"] == "ok"
        assert result["data"]["count"] == 5  # every item, zero PRs

    def test_counts_sees_all_items_and_no_prs(self, fake):
        fake.seed_pull_requests(OWNER, REPO, 110)
        for i in range(3):
            _issue_with_alias(fake, f"DIS-{i:04d}", title=f"item {i}")
        result = query.counts(fake, owner=OWNER, repo=REPO)
        assert result["data"]["total"] == 3

    def test_pick_excludes_a_stage_ready_labeled_pr(self, fake):
        fake.seed_pull_requests(OWNER, REPO, 1, state="open", labels=["stage:ready"])
        _issue_with_alias(fake, "DIS-0001", title="real ready work")
        result = query.pick(fake, owner=OWNER, repo=REPO)
        refs = [c["id"] for c in result["data"]["candidates"]]
        assert len(refs) == 1
        assert refs[0].endswith("#2")  # the issue, not the PR (#1)

    def test_alias_resolution_ignores_a_labeled_pr(self, fake):
        # A PR wearing the id:PFX alias label must not resolve as the item.
        # (Alphanumeric suffix — an all-digit one reads as the repo#number
        # spelling, and no real prawduct ID has a numeric suffix.)
        fake.seed_pull_requests(OWNER, REPO, 1, labels=["id:DIS-0A1B"])
        number = _issue_with_alias(fake, "DIS-0A1B", title="the real item")
        resolved = core.resolve_ref(
            fake, id_raw="DIS-0A1B", default_owner=OWNER, default_repo=(OWNER, REPO)
        )
        assert resolved.number == number

    def test_import_skip_authority_ignores_a_labeled_pr(self, fake):
        # _find_by_key with a PR carrying the key label: the import must not
        # "skip" the record (believing it exists) — it creates the real issue.
        fake.seed_pull_requests(OWNER, REPO, 1, labels=["id:DIS-0001"])
        source = (
            "# Backlog\n\n## Open\n\n"
            "- **[DIS-0001]** A real item\n"
            "  `area: cli · added: 2026-01-01 · status: open`\n\n  Body.\n"
        )
        result = migrate.import_backlog(fake, owner=OWNER, repo=REPO, content=source)
        assert result["status"] == "ok"
        assert len(result["data"]["created"]) == 1
        assert result["data"]["skipped"] == []

    def test_iter_alias_issues_skips_prs_and_walks_all_pages(self, fake):
        fake.seed_pull_requests(OWNER, REPO, 105, labels=["id:DIS-9999"])
        number = _issue_with_alias(fake, "DIS-0001", title="the item")
        seen = list(core.iter_alias_issues(fake, OWNER, REPO))
        assert [n for n, _pfxs, _labels, _status in seen] == [number]

    def test_iter_alias_issues_yields_the_decoded_status_not_the_raw_state(self, fake):
        """The scan already fetches `state="all"` and already parses each body, so
        the status is free — and it must be the *decoded* one. Raw `state` cannot
        distinguish shipped from dropped (both are `closed`) nor open from
        in-progress, so a consumer given `state` would have to re-implement the
        decoder's rules at a second site where they can drift."""
        shipped = _issue_with_alias(fake, "DIS-0001", title="shipped item")
        core.set_status(fake, id_raw=f"{OWNER}/{REPO}#{shipped}", target="shipped")
        dropped = _issue_with_alias(fake, "DIS-0002", title="dropped item")
        core.set_status(fake, id_raw=f"{OWNER}/{REPO}#{dropped}", target="dropped")
        in_progress = _issue_with_alias(fake, "DIS-0003", title="in-progress item")
        core.set_status(fake, id_raw=f"{OWNER}/{REPO}#{in_progress}", target="in-progress")
        plain = _issue_with_alias(fake, "DIS-0004", title="open item")

        by_number = {
            number: status
            for number, _pfxs, _labels, status in core.iter_alias_issues(fake, OWNER, REPO)
        }
        assert by_number[shipped] == "shipped"
        assert by_number[dropped] == "dropped"  # NOT collapsed with shipped
        assert by_number[in_progress] == "in-progress"  # NOT collapsed with open
        assert by_number[plain] == "open"

    def test_iter_alias_issues_raises_on_a_pathological_repo(self):
        """An alias scan that stopped early would report an existing item as
        missing — the importer would then create a duplicate instead of
        skipping. So the cap raises out of the generator rather than ending it."""
        class _Endless:
            def __init__(self):
                self.pages = 0

            def list_issues(self, owner, repo, *, state, per_page, page, labels=None):
                self.pages += 1
                return [
                    {"number": n, "body": "", "labels": []} for n in range(per_page)
                ]

        endless = _Endless()
        with pytest.raises(tp.TransportError) as exc:
            list(core.iter_alias_issues(endless, OWNER, REPO))
        assert endless.pages == tp.MAX_PAGES
        assert "truncated" in exc.value.message

    def test_list_op_filters_prs_from_items(self, fake):
        fake.seed_pull_requests(OWNER, REPO, 4, state="open", labels=["area:cli"])
        _issue_with_alias(fake, "DIS-0001", title="real item")
        result = query.list_items(fake, owner=OWNER, repo=REPO, filters={})
        assert result["data"]["count"] == 1


# --- BKL-5R2K: redirect-follow consumers (get + pick) ------------------------


class TestRedirectFollow:
    def _merged_pair(self, fake):
        a = core.file_item(fake, owner=OWNER, repo=REPO, title="dup A", body="b")
        b = core.file_item(fake, owner=OWNER, repo=REPO, title="keep B", body="b")
        a_id, b_id = a["data"]["id"], b["data"]["id"]
        merged = migrate.merge(fake, source_raw=a_id, target_raw=b_id)
        assert merged["status"] == "ok", merged
        return a_id, b_id

    def test_get_on_merged_source_surfaces_survivor(self, fake):
        a_id, b_id = self._merged_pair(fake)
        result = core.get_item(fake, id_raw=a_id)
        assert result["status"] == "ok"
        assert result["data"]["superseded_by"] == b_id
        assert result["data"]["resolves_to"] == b_id
        assert any("superseded by" in w for w in result["warnings"])

    def test_get_follows_a_redirect_chain(self, fake):
        a_id, b_id = self._merged_pair(fake)
        c = core.file_item(fake, owner=OWNER, repo=REPO, title="keep C", body="b")
        c_id = c["data"]["id"]
        assert migrate.merge(fake, source_raw=b_id, target_raw=c_id)["status"] == "ok"
        result = core.get_item(fake, id_raw=a_id)
        assert result["data"]["superseded_by"] == b_id  # the direct redirect
        assert result["data"]["resolves_to"] == c_id    # the chain's survivor

    def test_get_on_a_live_item_carries_no_resolves_to(self, fake):
        b = core.file_item(fake, owner=OWNER, repo=REPO, title="live", body="b")
        result = core.get_item(fake, id_raw=b["data"]["id"])
        assert result["status"] == "ok"
        assert "resolves_to" not in result["data"]

    def test_pick_excludes_open_but_redirected_item(self, fake):
        # The CRASH-2 window: redirect written, close crashed. Reopen a merged
        # source to model it; pick must not surface merged-away work.
        fake.seed_labels(OWNER, REPO, ["stage:ready"])
        a = core.file_item(
            fake, owner=OWNER, repo=REPO, title="dup A", body="b",
            facets={"stage": "ready"},
        )
        b = core.file_item(fake, owner=OWNER, repo=REPO, title="keep B", body="b")
        a_id, b_id = a["data"]["id"], b["data"]["id"]
        assert migrate.merge(fake, source_raw=a_id, target_raw=b_id)["status"] == "ok"
        number = int(a_id.rsplit("#", 1)[1])
        fake.update_issue(OWNER, REPO, number, fields={"state": "open"})  # crash-window model
        result = query.pick(fake, owner=OWNER, repo=REPO)
        refs = [c["id"] for c in result["data"]["candidates"]]
        assert a_id not in refs

    def test_get_human_mode_prints_survivor_breadcrumb(self, fake, capsys, tmp_path):
        a_id, b_id = self._merged_pair(fake)
        code = cli.run(str(tmp_path), ["get", a_id], transport=fake)
        assert code == 0
        out = capsys.readouterr().out
        assert "superseded_by \u2192" in out
        assert f"survivor: {b_id}" in out


class TestListHasMore:
    """The public `list` pagination signal derives from the RAW page (BKL-5T3J):
    an all-PR page yields items=[] but has_more=True, so a caller's walk
    continues to the pages holding real items."""

    def test_all_pr_page_reports_has_more(self, fake):
        fake.seed_pull_requests(OWNER, REPO, 100, state="open")
        _issue_with_alias(fake, "DIS-0A1B", title="real item on page 2")
        page1 = query.list_items(
            fake, owner=OWNER, repo=REPO, filters={}, per_page=100, page=1
        )
        assert page1["data"]["items"] == []      # all PRs decode out
        assert page1["data"]["has_more"] is True  # ...but the raw page was full
        page2 = query.list_items(
            fake, owner=OWNER, repo=REPO, filters={}, per_page=100, page=2
        )
        assert page2["data"]["count"] == 1
        assert page2["data"]["has_more"] is False

    def test_short_raw_page_ends_the_walk(self, fake):
        _issue_with_alias(fake, "DIS-0A1B", title="only item")
        result = query.list_items(fake, owner=OWNER, repo=REPO, filters={})
        assert result["data"]["has_more"] is False


class TestTransportRawPassthrough:
    def test_gh_list_issues_returns_prs_raw(self):
        # Pins the root-cause line: re-adding the client-side PR filter fails
        # this test (the transport must hand back the raw page).
        entries = [
            {"number": 1, "pull_request": {"url": "x"}, "labels": []},
            {"number": 2, "labels": []},
        ]
        gh = _PagedGh(entries)
        page = gh.list_issues(OWNER, REPO, state="all", per_page=100, page=1)
        assert len(page) == 2
        assert "pull_request" in page[0]


class TestRedirectDegrade:
    def test_mid_chain_failure_fail_opens_at_the_last_resolvable_node(self, fake):
        # A TransportError on a downstream hop lands at the last node the chain
        # could resolve — a's own block already names b, so b is surfaced.
        a = core.file_item(fake, owner=OWNER, repo=REPO, title="dup A", body="b")
        b = core.file_item(fake, owner=OWNER, repo=REPO, title="keep B", body="b")
        a_id, b_id = a["data"]["id"], b["data"]["id"]
        assert migrate.merge(fake, source_raw=a_id, target_raw=b_id)["status"] == "ok"
        real_get = fake.get_issue
        a_number = int(a_id.rsplit("#", 1)[1])

        def flaky_get(owner, repo, number):
            if number != a_number:
                raise tp.TransportError("unavailable", "backend flake")
            return real_get(owner, repo, number)

        fake.get_issue = flaky_get
        result = core.get_item(fake, id_raw=a_id)
        assert result["status"] == "ok"
        assert result["data"]["resolves_to"] == b_id

    def test_get_degrades_when_the_follow_itself_fails(self, fake):
        # The ERR-6 net: an unexpected OSError inside the follow (after the main
        # read succeeded) degrades to no enrichment — never a failed get.
        a = core.file_item(fake, owner=OWNER, repo=REPO, title="dup A", body="b")
        b = core.file_item(fake, owner=OWNER, repo=REPO, title="keep B", body="b")
        a_id, b_id = a["data"]["id"], b["data"]["id"]
        assert migrate.merge(fake, source_raw=a_id, target_raw=b_id)["status"] == "ok"
        real_get = fake.get_issue
        seen = {"count": 0}

        def once_then_broken(owner, repo, number):
            seen["count"] += 1
            if seen["count"] > 1:
                raise OSError("socket torn down")  # the follow's re-read
            return real_get(owner, repo, number)

        fake.get_issue = once_then_broken
        result = core.get_item(fake, id_raw=a_id)
        assert result["status"] == "ok"
        assert result["data"]["superseded_by"] == b_id
        assert "resolves_to" not in result["data"]


class TestPerPageClamp:
    def test_oversized_per_page_is_clamped_so_has_more_stays_honest(self, fake):
        # GitHub clamps per_page to 100 server-side; an unclamped local value
        # would make len(raw) == per_page never true and end walks early.
        fake.seed_pull_requests(OWNER, REPO, 100, state="open")
        _issue_with_alias(fake, "DIS-0A1B", title="page-2 item")
        result = query.list_items(
            fake, owner=OWNER, repo=REPO, filters={}, per_page=150, page=1
        )
        assert result["data"]["has_more"] is True


# --- BKL-6W9R: ONE shared paginator, converged bounds, loud cap trip ---------


class _EndlessIssues:
    """A backend that never returns a short page — the pathological shape the
    cap exists for."""

    def __init__(self):
        self.pages = 0

    def list_issues(self, owner, repo, *, state, per_page, page, labels=None):
        self.pages += 1
        return [{"number": n, "body": "", "labels": []} for n in range(per_page)]


class TestSharedPaginator:
    """Four near-identical loops with three different caps and three different
    cap-trip behaviours became one function. These pin the shared contract and
    that each of the four call sites actually routes through it."""

    def test_terminates_on_a_short_raw_page(self):
        pages = [[1] * 100, [1] * 100, [1] * 7]
        seen = []

        def fetch(page, size):
            seen.append(page)
            return pages[page - 1]

        assert len(list(tp.paginate(fetch))) == 207
        assert seen == [1, 2, 3]

    def test_a_full_final_page_costs_one_more_probe(self):
        """An exactly-per_page result is indistinguishable from a truncated one
        until the next page comes back empty — so the walk must not stop early."""
        pages = [[1] * 100, []]
        assert list(tp.paginate(lambda p, s: pages[p - 1])) == [1] * 100

    def test_non_list_page_raises_rather_than_reading_as_end_of_results(self):
        """Unreadable is not empty. Coercing a non-list page to `[]` satisfies
        the short-page terminator, so the walk ends and returns a prefix
        indistinguishable from a complete result — the exact failure this
        function exists to stop, one line below the docstring saying so."""
        with pytest.raises(tp.TransportError) as exc:
            list(tp.paginate(lambda p, s: {"message": "Not Found"}))
        assert exc.value.code == "unavailable"
        assert "not a list" in exc.value.message
        assert exc.value.details["page"] == 1

    def test_a_non_list_page_mid_walk_does_not_silently_shorten(self):
        pages = [[1] * 100, {"message": "Server Error"}]
        with pytest.raises(tp.TransportError) as exc:
            list(tp.paginate(lambda p, s: pages[p - 1]))
        assert exc.value.details["page"] == 2

    def test_cap_is_shared_not_per_call_site(self):
        """The bug was divergence: 100 / 100 / 1000 / 100 with three different
        cap-trip behaviours. One constant is the fix, so pin that it is one."""
        assert tp.MAX_PAGES == 1000
        assert tp.PAGE_SIZE == 100

    def test_query_scan_cap_becomes_an_error_envelope(self):
        """``counts``/``pick`` return envelopes, so the raise converts at the
        boundary — an incomplete scan reports unavailable rather than publishing
        a smaller backlog than the repo actually has."""
        result = query.counts(_EndlessIssues(), owner=OWNER, repo=REPO)
        assert result["status"] == "error"
        assert result["error"]["code"] == "unavailable"
        assert "truncated" in result["error"]["message"]

    def test_export_scan_cap_becomes_an_error_envelope(self, tmp_path):
        """``export`` is the backup path — the one place a silently short result
        is worst, because a truncated backup is a backup that lies."""
        result = migrate.export_backlog(
            _EndlessIssues(), owner=OWNER, repo=REPO, dest=tmp_path / "out"
        )
        assert result["status"] == "error"
        assert "truncated" in result["error"]["message"]
