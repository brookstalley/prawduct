"""Tests for lib/backlog/cachequery.py — the consumer query surface.

Cache Spec §2 enumerates fifteen consumers with file pins, and the union of what
they ask is small: open-item listing with text, grouping and counting by ``area``,
id resolution through aliases including dead items, creation-time filtering, text
search scoped to an area, and two date predicates. There is one test per query
here, and each asserts its result **set**, because a query test that only checks
the envelope's shape goes green when nothing was looked at.

Consumers 1 and 6 (the open set with text) are exercised in
``test_backlog_cache.py`` beside the rebuild that fills the store; everything else
in the union is here.

The store-level invariants those queries inherit — unavailable is never empty,
every payload carries a visible age — are asserted once across the whole surface
(``TestTheSurfaceInvariants``) rather than once per function, so a query added
later without going through ``_serve`` fails rather than quietly opting out.

All offline: no ``gh``, no network.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.backlog import cache, cachequery, core, encode, ids, sync  # noqa: E402
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


def _file(fake, *, title, body="b", **facets):
    result = core.file_item(fake, owner=OWNER, repo=REPO, title=title, body=body, facets=facets)
    assert result["status"] == "ok", result
    return result["data"]["id"]


def _raw_issue(fake, item_id: str) -> dict:
    """The fake's stored issue behind a canonical id.

    Reached into directly so a test can set provider timestamps: the fake stamps
    every issue at one instant, and the two date predicates below are precisely
    about telling instants apart."""
    return fake._repo(OWNER, REPO).issues[int(item_id.rsplit("#", 1)[1])]


def _stamp(fake, item_id: str, *, created: datetime | None = None, updated: datetime | None = None):
    issue = _raw_issue(fake, item_id)
    if created is not None:
        issue["created_at"] = created.isoformat().replace("+00:00", "Z")
    if updated is not None:
        issue["updated_at"] = updated.isoformat().replace("+00:00", "Z")


def _blocked_issue(fake, *, title: str, block: dict, body: str = "text") -> str:
    """An issue carrying a hand-built ``prawduct:`` block, and its canonical id.

    Created through the transport rather than through ``core.file_item`` because
    ``id_aliases`` and ``superseded_by`` are block-authoritative fields with no
    ``update`` flag — they arrive from the importer and from ``merge``, neither of
    which this chunk touches. Composing the block directly is what those writers
    would have left behind."""
    issue = fake.create_issue(
        OWNER, REPO, title=title, body=encode.compose_body(body, block), labels=[]
    )
    return f"{OWNER}/{REPO}#{issue['number']}"


def _rebuild(fake, repo_dir, *, now=NOW):
    result = sync.full_rebuild(fake, project_dir=repo_dir, owner=OWNER, repo=REPO, now=now)
    assert result["status"] == "ok", result
    return result


def _ids(result) -> list[str]:
    assert result["status"] == "ok", result
    return [item["id"] for item in result["data"]["items"]]


# --- consumer 2: created since ------------------------------------------------


class TestItemsCreatedSince:
    def test_it_returns_the_items_created_after_the_mark(self, fake, repo_dir):
        old = _file(fake, title="cache: an item filed long ago", area="backlog")
        recent = _file(fake, title="cache: an item filed this week", area="backlog")
        _stamp(fake, old, created=NOW - timedelta(days=30))
        _stamp(fake, recent, created=NOW - timedelta(days=2))
        _rebuild(fake, repo_dir)

        result = cachequery.items_created_since(
            repo_dir, scope=SCOPE, since=(NOW - timedelta(days=7)).isoformat(), now=NOW
        )

        assert _ids(result) == [recent], "the mark must exclude what predates it"

    def test_the_mark_itself_is_included(self, fake, repo_dir):
        """Inclusive, matching the provider's own ``since`` (Cache Spec §6,
        verified live). A caller passing a ref's timestamp means "everything from
        that point", and the two ends of the feature disagreeing about the
        boundary item is the off-by-one nobody notices."""
        boundary = _file(fake, title="cache: the item exactly on the mark", area="backlog")
        mark = NOW - timedelta(days=3)
        _stamp(fake, boundary, created=mark)
        _rebuild(fake, repo_dir)

        result = cachequery.items_created_since(
            repo_dir, scope=SCOPE, since=mark.isoformat(), now=NOW
        )

        assert _ids(result) == [boundary]

    def test_a_locally_spelled_mark_compares_as_an_instant(self, fake, repo_dir):
        """The provider stamps ``...Z`` and Python's ``isoformat()`` writes
        ``...+00:00``, so one moment has two spellings and the lexicographic answer
        between them is not the chronological one. Compared as strings this passes
        by luck on most inputs and fails on the boundary."""
        item = _file(fake, title="cache: an item to compare across spellings", area="backlog")
        _stamp(fake, item, created=NOW - timedelta(days=1))
        _rebuild(fake, repo_dir)

        # `+00:00` on the left, `Z` in the store — the same instant, two spellings.
        result = cachequery.items_created_since(
            repo_dir, scope=SCOPE, since=(NOW - timedelta(days=1)).isoformat(), now=NOW
        )

        assert _ids(result) == [item]

    def test_a_mark_that_is_not_a_timestamp_is_a_validation_error(self, fake, repo_dir):
        _file(fake, title="cache: any item at all", area="backlog")
        _rebuild(fake, repo_dir)

        result = cachequery.items_created_since(
            repo_dir, scope=SCOPE, since="last tuesday", now=NOW
        )

        assert result["status"] == "error"
        assert result["error"]["code"] == "validation"


# --- consumers 3 and 8: grouping and counting by area -------------------------


class TestDatePredicatesCompareInstantsNotDigits:
    """The two date predicates must be right across the **epoch digit boundary**,
    not just across the two ISO spellings.

    `_instant` was written to fix a spelling problem — the provider stamps `...Z`
    while `isoformat()` writes `...+00:00` — and it reintroduced the same class one
    level down: `strftime` returns TEXT, so without a CAST two epoch strings
    compare lexicographically and `'946684800' < '1577836800'` is **false**. Any
    bound before 2001-09-09 has nine digits where a current one has ten, so the
    answer inverts: an empty set for a distant `created-since`, and every open item
    reported stale for a distant `--older-than`.

    These fixtures sit deliberately on either side of that boundary rather than at
    a realistic bound, because the in-tree callers all pass recent dates — which is
    exactly why the defect was latent and why a test with realistic inputs stayed
    green over it.
    """

    PRE_2001 = datetime(1999, 6, 1, tzinfo=timezone.utc)   # 9-digit epoch
    POST_2001 = datetime(2020, 6, 1, tzinfo=timezone.utc)  # 10-digit epoch

    def test_created_since_a_pre_2001_bound_returns_everything(self, fake, repo_dir):
        item = _file(fake, title="cache: an item created in the modern era", area="backlog")
        _stamp(fake, item, created=self.POST_2001)
        _rebuild(fake, repo_dir)

        result = cachequery.items_created_since(
            repo_dir, scope=SCOPE, since=self.PRE_2001.isoformat(), now=NOW
        )

        assert _ids(result) == [item], (
            "a bound 21 years before the item excluded it — the epoch comparison "
            "is lexicographic, not chronological"
        )

    def test_created_since_a_post_2001_bound_still_excludes_what_predates_it(
        self, fake, repo_dir
    ):
        """The other direction, so a CAST that accidentally inverted the whole
        comparison could not pass the test above on its own."""
        old = _file(fake, title="cache: an item created before the boundary", area="backlog")
        _stamp(fake, old, created=self.PRE_2001)
        _rebuild(fake, repo_dir)

        result = cachequery.items_created_since(
            repo_dir, scope=SCOPE, since=self.POST_2001.isoformat(), now=NOW
        )

        assert _ids(result) == []

    def test_a_horizon_reaching_past_2001_does_not_report_everything_stale(
        self, fake, repo_dir
    ):
        """`--older-than` is operator-settable through the janitor's Backlog Health
        block, so a large value is reachable input rather than a hypothetical."""
        item = _file(fake, title="cache: an item touched this week", area="backlog")
        _stamp(fake, item, updated=NOW - timedelta(days=3))
        _rebuild(fake, repo_dir)

        # A cutoff before 2001 — 9 epoch digits against the item's 10.
        horizon = (NOW - self.PRE_2001).days

        result = cachequery.stale_items(
            repo_dir, scope=SCOPE, older_than_days=horizon, now=NOW
        )

        assert _ids(result) == [], (
            "an item edited three days ago was reported untouched for 27 years"
        )


class TestByArea:
    def test_it_groups_and_counts_the_open_items(self, fake, repo_dir):
        first = _file(fake, title="cache: a backlog item", area="backlog")
        second = _file(fake, title="cache: another backlog item", area="backlog")
        other = _file(fake, title="cache: a critic item", area="critic")
        _rebuild(fake, repo_dir)

        result = cachequery.by_area(repo_dir, scope=SCOPE, now=NOW)

        assert result["status"] == "ok", result
        groups = {group["area"]: group for group in result["data"]["groups"]}
        assert groups["backlog"]["count"] == 2
        assert [item["id"] for item in groups["backlog"]["items"]] == sorted([first, second])
        assert [item["id"] for item in groups["critic"]["items"]] == [other]

    def test_an_unfaceted_item_is_a_group_not_a_silence(self, fake, repo_dir):
        """Items with no area are exactly what a dedup or hygiene sweep is looking
        for; dropping them would hide the untended ones from the check that exists
        to find them."""
        bare = _file(fake, title="cache: an item nobody faceted")
        _rebuild(fake, repo_dir)

        result = cachequery.by_area(repo_dir, scope=SCOPE, now=NOW)

        groups = {group["area"]: group for group in result["data"]["groups"]}
        assert [item["id"] for item in groups["(none)"]["items"]] == [bare]

    def test_closed_items_are_out_unless_asked_for(self, fake, repo_dir):
        live = _file(fake, title="cache: a live item", area="backlog")
        done = _file(fake, title="cache: a shipped item", area="backlog")
        assert core.set_status(fake, id_raw=done, target="shipped")["status"] == "ok"
        _rebuild(fake, repo_dir)

        default = cachequery.by_area(repo_dir, scope=SCOPE, now=NOW)
        everything = cachequery.by_area(repo_dir, scope=SCOPE, now=NOW, open_only=False)

        assert _group_ids(default, "backlog") == [live]
        assert _group_ids(everything, "backlog") == sorted([live, done])

    def test_the_grouping_carries_no_bodies(self, fake, repo_dir):
        """The body is the largest column in the store, and a grouping payload
        carrying one per row hands a caller counting items the whole corpus in
        memory to do it."""
        _file(fake, title="cache: an item with a body", body="a great deal of prose", area="backlog")
        _rebuild(fake, repo_dir)

        result = cachequery.by_area(repo_dir, scope=SCOPE, now=NOW)

        item = result["data"]["groups"][0]["items"][0]
        assert "body" not in item
        assert "title" in item, "the brief projection must still be usable"


def _group_ids(result, area: str) -> list[str]:
    assert result["status"] == "ok", result
    for group in result["data"]["groups"]:
        if group["area"] == area:
            return sorted(item["id"] for item in group["items"])
    return []


# --- consumers 1 and 4: the changed-file intersection -------------------------


class TestItemsAffecting:
    def _touching(self, fake, paths: str, *, title="cache: an item that touches code"):
        item_id = _file(fake, title=title, area="backlog")
        assert core.update_item(fake, id_raw=item_id, fields={"affected": paths})["status"] == "ok"
        return item_id

    def test_a_changed_file_finds_the_item_that_claims_its_directory(self, fake, repo_dir):
        item_id = self._touching(fake, "plugin/lib/backlog, docs/x.md")
        _file(fake, title="cache: an item nobody changed", area="critic")
        _rebuild(fake, repo_dir)

        result = cachequery.items_affecting(
            repo_dir, scope=SCOPE, changed_paths=["plugin/lib/backlog/sync.py"], now=NOW
        )

        assert _ids(result) == [item_id]

    def test_it_reports_which_entry_matched(self, fake, repo_dir):
        """A consumer saying "this item looks related" has to be able to say which
        path made it think so."""
        item_id = self._touching(fake, "plugin/lib/backlog, docs/x.md")
        _rebuild(fake, repo_dir)

        result = cachequery.items_affecting(
            repo_dir, scope=SCOPE, changed_paths=["docs/x.md"], now=NOW
        )

        assert result["data"]["items"][0]["id"] == item_id
        assert result["data"]["items"][0]["matched"] == ["docs/x.md"]

    def test_a_sibling_directory_is_not_an_overlap(self, fake, repo_dir):
        """`plugin/lib` must not swallow `plugin/libexec` — a string-prefix match
        would, and it would read as a confident hit rather than as a miss."""
        self._touching(fake, "plugin/lib")
        _rebuild(fake, repo_dir)

        result = cachequery.items_affecting(
            repo_dir, scope=SCOPE, changed_paths=["plugin/libexec/thing.py"], now=NOW
        )

        assert _ids(result) == []

    def test_an_empty_change_set_still_carries_an_age(self, fake, repo_dir):
        """The answer is empty because the *input* was, and a caller cannot tell
        that from an unreachable cache unless the envelope says which."""
        self._touching(fake, "plugin/lib")
        _rebuild(fake, repo_dir)

        result = cachequery.items_affecting(repo_dir, scope=SCOPE, changed_paths=[], now=NOW)

        assert result["status"] == "ok", result
        assert result["data"]["items"] == []
        assert result["data"]["age_seconds"] is not None


# --- consumer 9: text search --------------------------------------------------


class TestSearch:
    def test_it_finds_an_item_by_a_word_in_its_body(self, fake, repo_dir):
        wanted = _file(
            fake, title="cache: the sync watermark", body="about the cursor", area="backlog"
        )
        _file(fake, title="cache: the label taxonomy", body="unrelated", area="backlog")
        _rebuild(fake, repo_dir)

        result = cachequery.search(repo_dir, scope=SCOPE, text="cursor", now=NOW)

        assert _ids(result) == [wanted]

    def test_it_sees_an_item_written_moments_ago(self, fake, repo_dir):
        """QRY-3's cache-served half. GitHub's search index is not
        read-your-writes, and the consumer this serves — "is the item I am about
        to file a duplicate?" — is asked at exactly the moment a just-filed item
        is still invisible to it."""
        _rebuild(fake, repo_dir)
        fresh = _file(fake, title="cache: a brand new distinctive item", area="backlog")
        sync.incremental_sync(fake, project_dir=repo_dir, owner=OWNER, repo=REPO, now=NOW)

        result = cachequery.search(repo_dir, scope=SCOPE, text="distinctive", now=NOW)

        assert _ids(result) == [fresh]

    def test_it_scopes_to_an_area_when_asked(self, fake, repo_dir):
        here = _file(fake, title="cache: a duplicate candidate", area="backlog")
        _file(fake, title="cache: a duplicate candidate", area="critic")
        _rebuild(fake, repo_dir)

        result = cachequery.search(repo_dir, scope=SCOPE, text="duplicate", now=NOW, area="backlog")

        assert _ids(result) == [here]

    def test_a_term_carrying_an_fts_operator_is_a_literal(self, fake, repo_dir):
        """Search text is a caller's arbitrary string — an item title on its way
        to a dedup check. Unquoted, FTS5 reads ``AND``/``NOT``/``*``/``:`` as
        query syntax, so a title containing one either changes the query's meaning
        or fails it with a syntax error the caller could not have anticipated."""
        _file(fake, title="cache: an item about parsing", body="tokens and phrases", area="backlog")
        _rebuild(fake, repo_dir)

        result = cachequery.search(repo_dir, scope=SCOPE, text='AND OR "unbalanced', now=NOW)

        assert result["status"] == "ok", result
        assert result["data"]["items"] == [], "operators must match literals, not steer the query"

    def test_text_with_nothing_searchable_is_a_validation_error(self, fake, repo_dir):
        _file(fake, title="cache: any item at all", area="backlog")
        _rebuild(fake, repo_dir)

        result = cachequery.search(repo_dir, scope=SCOPE, text="--- ...", now=NOW)

        assert result["status"] == "error"
        assert result["error"]["code"] == "validation"

    def test_a_store_without_a_text_index_reports_rather_than_matching_nothing(
        self, fake, repo_dir
    ):
        """A search that silently answered "no matches" on a SQLite without FTS5
        would be the empty-means-clean failure this module exists to prevent."""
        _file(fake, title="cache: an item the index would have found", area="backlog")
        _rebuild(fake, repo_dir)
        path = cache.cache_path(repo_dir)
        raw = sqlite3.connect(str(path))
        raw.execute("DROP TABLE item_fts")
        raw.commit()
        raw.close()

        result = cachequery.search(repo_dir, scope=SCOPE, text="item", now=NOW)

        assert result["status"] == "error"
        assert result["error"]["code"] == "unavailable"
        assert "no text index" in result["error"]["message"]


# --- consumers 10 and 11: the two hygiene predicates --------------------------


class TestStaleItems:
    def test_it_returns_only_what_has_gone_quiet(self, fake, repo_dir):
        quiet = _file(fake, title="cache: an item nobody has touched", area="backlog")
        busy = _file(fake, title="cache: an item edited yesterday", area="backlog")
        _stamp(fake, quiet, updated=NOW - timedelta(days=120))
        _stamp(fake, busy, updated=NOW - timedelta(days=1))
        _rebuild(fake, repo_dir)

        result = cachequery.stale_items(repo_dir, scope=SCOPE, older_than_days=90, now=NOW)

        assert _ids(result) == [quiet]

    def test_a_closed_item_is_not_stale_it_is_finished(self, fake, repo_dir):
        done = _file(fake, title="cache: an item shipped long ago", area="backlog")
        assert core.set_status(fake, id_raw=done, target="shipped")["status"] == "ok"
        _stamp(fake, done, updated=NOW - timedelta(days=200))
        _rebuild(fake, repo_dir)

        result = cachequery.stale_items(repo_dir, scope=SCOPE, older_than_days=90, now=NOW)

        assert _ids(result) == []

    def test_the_cutoff_comes_from_the_callers_clock(self, fake, repo_dir):
        """One clock must age the item and the payload both, or a test that
        injects a clock is measuring against the machine's."""
        item = _file(fake, title="cache: an item from the middle distance", area="backlog")
        _stamp(fake, item, updated=NOW - timedelta(days=10))
        _rebuild(fake, repo_dir)

        near = cachequery.stale_items(repo_dir, scope=SCOPE, older_than_days=30, now=NOW)
        far = cachequery.stale_items(
            repo_dir, scope=SCOPE, older_than_days=30, now=NOW + timedelta(days=60)
        )

        assert _ids(near) == []
        assert _ids(far) == [item]

    def test_a_negative_window_is_a_validation_error(self, fake, repo_dir):
        _file(fake, title="cache: any item at all", area="backlog")
        _rebuild(fake, repo_dir)

        result = cachequery.stale_items(repo_dir, scope=SCOPE, older_than_days=-1, now=NOW)

        assert result["status"] == "error"
        assert result["error"]["code"] == "validation"


class TestUnstagedItems:
    def test_it_returns_the_items_nobody_triaged(self, fake, repo_dir):
        untriaged = _file(fake, title="cache: an item with no stage", area="backlog")
        _file(fake, title="cache: an item on the ladder", area="backlog", stage="ready")
        _rebuild(fake, repo_dir)

        result = cachequery.unstaged_items(repo_dir, scope=SCOPE, now=NOW)

        assert _ids(result) == [untriaged]

    def test_an_early_stage_is_a_decision_not_an_absence(self, fake, repo_dir):
        """`stage: idea` means somebody looked; no stage means nobody did."""
        _file(fake, title="cache: an item someone called an idea", area="backlog", stage="idea")
        _rebuild(fake, repo_dir)

        result = cachequery.unstaged_items(repo_dir, scope=SCOPE, now=NOW)

        assert _ids(result) == []


# --- ready work: the candidate set behind `pick` ------------------------------


class TestReadyItems:
    def test_it_returns_only_the_open_ready_items(self, fake, repo_dir):
        ready = _file(fake, title="cache: a buildable item", area="backlog", stage="ready")
        _file(fake, title="cache: an item still an idea", area="backlog", stage="idea")
        _file(fake, title="cache: an item nobody staged", area="backlog")
        shipped = _file(fake, title="cache: a finished item", area="backlog", stage="ready")
        assert core.set_status(fake, id_raw=shipped, target="shipped")["status"] == "ok"
        _rebuild(fake, repo_dir)

        assert _ids(cachequery.ready_items(repo_dir, scope=SCOPE, now=NOW)) == [ready]

    def test_a_working_branch_takes_an_item_out_of_the_candidate_set(self, fake, repo_dir):
        free = _file(fake, title="cache: an item nobody is on", area="backlog", stage="ready")
        taken = _file(fake, title="cache: an item someone is on", area="backlog", stage="ready")
        fake.push_branch(OWNER, REPO, "feat/in-flight")
        assert core.update_item(
            fake, id_raw=taken, fields={"working-branch": f"{SCOPE}@feat/in-flight"}
        )["status"] == "ok"
        _rebuild(fake, repo_dir)

        assert _ids(cachequery.ready_items(repo_dir, scope=SCOPE, now=NOW)) == [free]

    def test_include_working_adds_them_back_carrying_their_branch(self, fake, repo_dir):
        """Widens the set rather than inverting it: a caller looking at contested
        work needs the uncontested items in the same answer, and needs to see
        which branch it is contesting with."""
        free = _file(fake, title="cache: an item nobody is on", area="backlog", stage="ready")
        taken = _file(fake, title="cache: an item someone is on", area="backlog", stage="ready")
        fake.push_branch(OWNER, REPO, "feat/in-flight")
        assert core.update_item(
            fake, id_raw=taken, fields={"working-branch": f"{SCOPE}@feat/in-flight"}
        )["status"] == "ok"
        _rebuild(fake, repo_dir)

        result = cachequery.ready_items(repo_dir, scope=SCOPE, now=NOW, include_working=True)

        assert set(_ids(result)) == {free, taken}
        by_id = {item["id"]: item for item in result["data"]["items"]}
        assert by_id[taken]["working_branch"] == f"{SCOPE}@feat/in-flight"

    def test_an_open_but_redirected_item_is_never_ready_work(self, fake, repo_dir):
        """The window between a merge's redirect write and its close. The item is
        merged away; offering it as buildable sends someone at a record that has
        already moved."""
        survivor = _file(fake, title="cache: the surviving item", area="backlog", stage="ready")
        merged = _blocked_issue(
            fake,
            title="cache: the merged-away item",
            block={"v": "1", "superseded_by": survivor},
        )
        fake.add_labels(OWNER, REPO, int(merged.rsplit("#", 1)[1]), ["stage:ready"])
        _rebuild(fake, repo_dir)

        assert _ids(cachequery.ready_items(repo_dir, scope=SCOPE, now=NOW)) == [survivor]

    def test_it_returns_only_this_scopes_rows(self, fake, repo_dir):
        """The one query here that filters on scope, so it needs its own pin
        rather than riding `pick`'s.

        Every other consumer reads the store whole — it holds one repo by design.
        `pick` cannot: it hands a candidate's issue *number* to a live blocker
        read against the caller's repo, so a foreign row would be judged against
        whatever issue this repo has at that number."""
        mine = _file(fake, title="cache: an item in this repo", area="backlog", stage="ready")
        _rebuild(fake, repo_dir)
        conn = cache.open_store(repo_dir, create=False)
        conn.execute(
            "INSERT INTO item (id, title, status, stage, created_at, updated_at, fetched_at) "
            "VALUES ('other/repo#1', 'a foreign item', 'open', 'ready', ?, ?, ?)",
            (NOW.isoformat(), NOW.isoformat(), NOW.isoformat()),
        )
        conn.commit()
        conn.close()

        assert _ids(cachequery.ready_items(repo_dir, scope=SCOPE, now=NOW)) == [mine]

    def test_it_orders_oldest_first(self, fake, repo_dir):
        second = _file(fake, title="cache: the newer buildable item", area="backlog", stage="ready")
        first = _file(fake, title="cache: the older buildable item", area="backlog", stage="ready")
        _stamp(fake, first, created=NOW - timedelta(days=30))
        _stamp(fake, second, created=NOW - timedelta(days=2))
        _rebuild(fake, repo_dir)

        assert _ids(cachequery.ready_items(repo_dir, scope=SCOPE, now=NOW)) == [first, second]


# --- consumers 5, 7, 14 and 15: resolution ------------------------------------


class TestResolve:
    def test_a_live_id_resolves_with_the_status_its_consumers_ask_for(self, fake, repo_dir):
        item = _file(fake, title="cache: a live item", area="backlog", stage="ready")
        _rebuild(fake, repo_dir)

        result = cachequery.resolve(repo_dir, scope=SCOPE, id_raw=item, now=NOW)

        assert result["status"] == "ok", result
        data = result["data"]
        assert (data["resolved"], data["id"], data["via"]) == (True, item, "id")
        assert data["status"] == "open" and data["dead"] is False
        assert data["updated_at"] is not None, "consumer 15 reads a date floor off this"

    def test_a_dead_item_resolves_and_says_so(self, fake, repo_dir):
        """Consumer 14 asks *is it dead*, which a store answering "no such item"
        cannot distinguish from a typo. The full rebuild holds closed items for
        exactly this."""
        item = _file(fake, title="cache: an item that shipped", area="backlog")
        assert core.set_status(fake, id_raw=item, target="shipped")["status"] == "ok"
        _rebuild(fake, repo_dir)

        result = cachequery.resolve(repo_dir, scope=SCOPE, id_raw=item, now=NOW)

        assert result["data"]["resolved"] is True
        assert result["data"]["dead"] is True
        assert result["data"]["status"] == "shipped"

    def test_a_hand_minted_alias_resolves(self, fake, repo_dir):
        item = _blocked_issue(
            fake, title="cache: a migrated item", block={"id_aliases": "[BKL-7M4Q]"}
        )
        _rebuild(fake, repo_dir)

        result = cachequery.resolve(repo_dir, scope=SCOPE, id_raw="BKL-7M4Q", now=NOW)

        assert result["data"]["resolved"] is True
        assert result["data"]["id"] == item
        assert result["data"]["via"] == "alias"

    def test_an_id_resolving_to_nothing_is_an_answer_not_an_error(self, fake, repo_dir):
        """Consumer 5's entire finding is the miss. Returning an error would make
        the dangling-id check indistinguishable from an unreachable cache."""
        _file(fake, title="cache: some other item", area="backlog")
        _rebuild(fake, repo_dir)

        result = cachequery.resolve(repo_dir, scope=SCOPE, id_raw=f"{SCOPE}#9999", now=NOW)

        assert result["status"] == "ok", result
        assert result["data"]["resolved"] is False
        assert result["data"]["id"] is None

    def test_a_malformed_spelling_carries_the_reason_it_was_rejected(self, fake, repo_dir):
        """"No such item" and "that is not an id" send a reader to two different
        places."""
        _file(fake, title="cache: some other item", area="backlog")
        _rebuild(fake, repo_dir)

        result = cachequery.resolve(repo_dir, scope=SCOPE, id_raw="not an id at all", now=NOW)

        assert result["data"]["resolved"] is False
        assert result["data"]["reason"], "a rejected spelling must say why"

    def test_two_claimants_are_a_reported_collision_never_a_pick(self, fake, repo_dir):
        """Alias uniqueness is an integrity constraint (Data Model §5). Choosing
        one of two would be a resolution nobody could audit — and the store has to
        be able to *hold* the violation to report it, which is why the index
        carries no UNIQUE."""
        _blocked_issue(fake, title="cache: the first claimant", block={"id_aliases": "[BKL-7M4Q]"})
        _blocked_issue(fake, title="cache: the second claimant", block={"id_aliases": "[BKL-7M4Q]"})
        _rebuild(fake, repo_dir)

        result = cachequery.resolve(repo_dir, scope=SCOPE, id_raw="BKL-7M4Q", now=NOW)

        assert result["status"] == "error"
        assert result["error"]["code"] == "alias_collision"

    def test_a_typo_in_the_alias_list_claims_nothing(self, fake, repo_dir):
        """`id_aliases` is hand-editable text. An entry that is neither a PFX nor
        a tagged provider id is a typo, and indexing it would let the typo claim a
        resolution."""
        _blocked_issue(
            fake, title="cache: an item with a bad alias", block={"id_aliases": "[not-an-alias!]"}
        )
        _rebuild(fake, repo_dir)

        result = cachequery.resolve(repo_dir, scope=SCOPE, id_raw="not-an-alias!", now=NOW)

        assert result["data"]["resolved"] is False


class TestResolutionAcrossAMigration:
    """Cache Spec §4 rule 3 — the defect this chunk fixes.

    A stored reference like ``#618``'s ``related: [brookstalley/prawduct#249, …]``
    parsed at read time as live provider coordinates means a migration must
    rewrite every edge, and a missed rewrite breaks the graph *silently* because
    the citation still looks like a valid id.
    """

    def _migrated(self, fake):
        """A record that carries a retired id as a tagged alias — what a migration
        leaves behind. The old id is not a live issue any more; only the alias
        remembers it."""
        retired = f"{SCOPE}#404"
        survivor = _blocked_issue(
            fake,
            title="cache: the record that survived the migration",
            block={"id_aliases": f"[{ids.provider_alias(retired)}]"},
        )
        return retired, survivor

    def test_a_historical_citation_still_resolves(self, fake, repo_dir):
        retired, survivor = self._migrated(fake)
        _rebuild(fake, repo_dir)

        result = cachequery.resolve(repo_dir, scope=SCOPE, id_raw=retired, now=NOW)

        assert result["data"]["resolved"] is True, "the citation stopped resolving"
        assert result["data"]["id"] == survivor
        assert result["data"]["via"] == "alias"

    def test_the_tagged_spelling_resolves_too(self, fake, repo_dir):
        """The untagged citation is what a change-log carries; the tagged one is
        what the record stores. Both have to reach the same item, or a caller has
        to know which spelling to try."""
        retired, survivor = self._migrated(fake)
        _rebuild(fake, repo_dir)

        result = cachequery.resolve(
            repo_dir, scope=SCOPE, id_raw=ids.provider_alias(retired), now=NOW
        )

        assert result["data"]["id"] == survivor

    def test_the_related_edge_is_never_rewritten(self, fake, repo_dir):
        """The point of resolving through aliases: the edge itself stays exactly as
        written. A migration that had to rewrite every edge would break the ones it
        missed, and this is the assertion that no rewrite is required."""
        retired, survivor = self._migrated(fake)
        citing = _blocked_issue(
            fake, title="cache: an item citing the retired id", block={"related": f"[{retired}]"}
        )
        _rebuild(fake, repo_dir)

        conn = cache.open_store(repo_dir, create=False)
        body = conn.execute("SELECT body FROM item WHERE id = ?", (citing,)).fetchone()[0]
        conn.close()
        edge = encode.parse_block(body).fields["related"]

        assert edge == f"[{retired}]", "the stored edge was rewritten"
        assert (
            cachequery.resolve(repo_dir, scope=SCOPE, id_raw=retired, now=NOW)["data"]["id"]
            == survivor
        )


class TestRedirects:
    def test_a_two_hop_chain_resolves_to_the_survivor(self, fake, repo_dir):
        """`superseded_by` is what ``merge``/``transfer`` leave behind, and a chain
        of them is a record that moved twice."""
        final = _file(fake, title="cache: the item everything merged into", area="backlog")
        middle = _blocked_issue(
            fake, title="cache: the middle hop", block={"superseded_by": final}
        )
        first = _blocked_issue(fake, title="cache: the first hop", block={"superseded_by": middle})
        _rebuild(fake, repo_dir)

        result = cachequery.resolve(repo_dir, scope=SCOPE, id_raw=first, now=NOW)

        assert result["data"]["id"] == final
        assert result["data"]["redirected_from"] == first

    def test_the_provenance_of_the_first_match_survives_the_redirect(self, fake, repo_dir):
        """A consumer chasing a bad edge needs to know both which spelling matched
        and that it then moved — so the redirect is reported beside ``via`` rather
        than overwriting it."""
        final = _file(fake, title="cache: the survivor", area="backlog")
        source = _blocked_issue(
            fake,
            title="cache: a merged-away record with an alias",
            block={"id_aliases": "[BKL-7M4Q]", "superseded_by": final},
        )
        _rebuild(fake, repo_dir)

        result = cachequery.resolve(repo_dir, scope=SCOPE, id_raw="BKL-7M4Q", now=NOW)

        assert result["data"]["id"] == final
        assert result["data"]["via"] == "alias"
        assert result["data"]["redirected_from"] == source

    def test_a_redirect_the_store_cannot_follow_is_reported_not_swallowed(self, fake, repo_dir):
        """Following it would resolve to nothing, and reading that as "no such
        item" would lose the redirect the body plainly records."""
        source = _blocked_issue(
            fake, title="cache: a record pointing off the edge",
            block={"superseded_by": f"{SCOPE}#9999"},
        )
        _rebuild(fake, repo_dir)

        result = cachequery.resolve(repo_dir, scope=SCOPE, id_raw=source, now=NOW)

        assert result["data"]["resolved"] is True
        assert result["data"]["id"] == source
        assert result["data"]["unresolved_redirect"] == f"{SCOPE}#9999"

    def test_a_cycle_terminates(self, fake, repo_dir):
        """A human A→B, B→A edit. Fail open at the node reached rather than
        looping forever."""
        first = _blocked_issue(fake, title="cache: one half of a cycle", block={"v": "1"})
        second = _blocked_issue(
            fake, title="cache: the other half", block={"superseded_by": first}
        )
        issue = _raw_issue(fake, first)
        issue["body"] = encode.upsert_block_field(issue["body"], "superseded_by", second)
        _rebuild(fake, repo_dir)

        result = cachequery.resolve(repo_dir, scope=SCOPE, id_raw=first, now=NOW)

        assert result["status"] == "ok", result
        assert result["data"]["resolved"] is True


# --- the invariants the whole surface inherits --------------------------------


def _every_query(repo_dir):
    """One call per public query, so a function added later without going through
    ``_serve`` fails these rather than quietly opting out of them."""
    return {
        "open_items": lambda: cachequery.open_items(repo_dir, scope=SCOPE, now=NOW),
        "items_created_since": lambda: cachequery.items_created_since(
            repo_dir, scope=SCOPE, since=(NOW - timedelta(days=7)).isoformat(), now=NOW
        ),
        "by_area": lambda: cachequery.by_area(repo_dir, scope=SCOPE, now=NOW),
        "items_affecting": lambda: cachequery.items_affecting(
            repo_dir, scope=SCOPE, changed_paths=["plugin/lib/backlog/sync.py"], now=NOW
        ),
        "search": lambda: cachequery.search(repo_dir, scope=SCOPE, text="item", now=NOW),
        "stale_items": lambda: cachequery.stale_items(
            repo_dir, scope=SCOPE, older_than_days=90, now=NOW
        ),
        "unstaged_items": lambda: cachequery.unstaged_items(repo_dir, scope=SCOPE, now=NOW),
        "resolve": lambda: cachequery.resolve(
            repo_dir, scope=SCOPE, id_raw=f"{SCOPE}#1", now=NOW
        ),
        "ready_items": lambda: cachequery.ready_items(repo_dir, scope=SCOPE, now=NOW),
    }


class TestTheSurfaceInvariants:
    def test_the_public_surface_is_the_consumer_union(self):
        """The module's functions and Cache Spec §2's queries are one list. A
        function nothing enumerates is an invention; a consumer with no function
        is a gap — and both are easier to see here than in a diff."""
        public = {
            name
            for name in vars(cachequery)
            if not name.startswith("_") and callable(getattr(cachequery, name))
            and getattr(getattr(cachequery, name), "__module__", "") == cachequery.__name__
        }

        assert public == set(_every_query(Path("."))), (
            "a query was added or removed without the consumer inventory moving with it"
        )

    @pytest.mark.parametrize("name", sorted(_every_query(Path("."))))
    def test_an_absent_store_reports_unavailable_never_an_empty_set(self, name, repo_dir):
        """A silent reader and a clean bill of health are indistinguishable to
        whoever reads the output — the exact failure the dormant checks were made
        to announce rather than commit."""
        result = _every_query(repo_dir)[name]()

        assert result["status"] == "error", f"{name} served an answer with no store"
        assert result["error"]["code"] == "unavailable"

    @pytest.mark.parametrize("name", sorted(_every_query(Path("."))))
    def test_every_served_payload_carries_a_visible_age(self, name, fake, repo_dir):
        item = _file(fake, title="cache: an item every query can find", area="backlog")
        assert core.update_item(
            fake, id_raw=item, fields={"affected": "plugin/lib/backlog"}
        )["status"] == "ok"
        _rebuild(fake, repo_dir, now=NOW - timedelta(hours=2))

        result = _every_query(repo_dir)[name]()

        assert result["status"] == "ok", result
        assert result["data"]["age_seconds"] == pytest.approx(2 * 3600, abs=2)
        assert result["data"]["synced_at"] is not None
        assert result["data"]["scope"] == SCOPE


class TestTheTextIndexSurvivesASchemaRebuild:
    def test_a_version_bump_leaves_a_working_text_index(self, fake, repo_dir):
        """**A regression test for a defect that made search fail forever after any
        schema bump.** ``sqlite_master`` lists an FTS5 table *after* its own shadow
        tables, so a drop loop walking that listing deletes ``item_fts_config``
        first — and FTS5's constructor reads it, so the virtual table it then
        reaches can no longer be opened at all. The loop's ``except … continue``
        swallowed the failure, ``create_schema`` reported the consequence as "this
        SQLite has no FTS5", and what survived was an ``item_fts`` that
        ``has_fts`` called present and every query raised on.

        Asserted through ``search`` rather than through ``has_fts``, because
        ``has_fts`` is precisely what returned the wrong answer."""
        _file(fake, title="cache: an item with a distinctive word", area="backlog")
        _rebuild(fake, repo_dir)
        path = cache.cache_path(repo_dir)
        raw = sqlite3.connect(str(path))
        raw.execute(f"PRAGMA user_version={cache.SCHEMA_VERSION - 1}")
        raw.commit()
        raw.close()

        _rebuild(fake, repo_dir)  # the version mismatch forces drop-and-recreate

        result = cachequery.search(repo_dir, scope=SCOPE, text="distinctive", now=NOW)

        assert result["status"] == "ok", result
        assert len(result["data"]["items"]) == 1

    def test_a_clearing_that_leaves_anything_behind_refuses_rather_than_building_over_it(
        self, fake, repo_dir
    ):
        """Seam 2 of the same fix. Dropping is what makes the fresh schema fresh,
        so a drop that half-worked must not be built on: the result would be a
        store part old and part new that reports success. Refusing rolls the whole
        thing back — the drops are inside the transaction — so the previous store
        survives intact and a later open can still rebuild it.

        **The stand-in has to leave a survivor the schema build would otherwise
        step over**, or the test passes for the wrong reason: a stub that drops
        nothing at all makes `create_schema` fail on `item` already existing, which
        returns the same `unavailable` envelope whether or not the refusal is
        there. So this drops everything for real and then leaves one stray table
        behind — with the refusal, the transaction rolls back and the rows survive;
        without it, `create_schema` succeeds over an emptied store, commits, and
        the rows are gone. The row comparison is what tells those apart."""
        _file(fake, title="cache: an item worth not destroying", area="backlog")
        _rebuild(fake, repo_dir)
        before = _item_ids(repo_dir)
        assert before, "an empty store would make the survival assertion vacuous"
        path = cache.cache_path(repo_dir)
        raw = sqlite3.connect(str(path))
        raw.execute(f"PRAGMA user_version={cache.SCHEMA_VERSION - 1}")
        raw.commit()
        raw.close()

        real_drop = cache._drop_objects

        def leaves_a_survivor(conn):
            real_drop(conn)
            conn.execute("CREATE TABLE leftover (x TEXT)")
            return ["leftover"]

        with mock.patch.object(cache, "_drop_objects", side_effect=leaves_a_survivor):
            opened = cache.open_store(repo_dir, create=True)

        assert isinstance(opened, dict), "a half-cleared store must not be opened for writing"
        assert opened["error"]["code"] == "unavailable"
        assert _item_ids(repo_dir) == before, "the refusal must leave the old store intact"

    def test_a_schema_failure_that_is_not_a_missing_module_is_not_called_one(self, repo_dir):
        """Seam 3. FTS5 is a compile-time option, so `no such module` is a real
        degradation the store works around by reporting search unavailable. Every
        *other* DDL failure means the schema did not come out as written, and
        treating the two alike is how a half-dropped store once reported itself as
        a SQLite without full-text search — a false diagnosis that sends whoever
        reads it off to rebuild their interpreter."""
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE TABLE item_fts (x TEXT)")  # the name is already taken

        with pytest.raises(sqlite3.OperationalError, match="already exists"):
            cache.create_schema(conn)

        conn.close()

    def test_a_sqlite_genuinely_without_fts5_degrades_instead(self, repo_dir):
        """The other half of seam 3, so the re-raise cannot be read as "any DDL
        failure is fatal": a genuinely missing module still returns a usable store
        with search reporting unavailable."""
        conn = sqlite3.connect(":memory:")

        fts = cache.create_schema(_WithoutFts5(conn))

        assert fts is False, "a missing module must degrade, not raise"
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master")}
        assert "item" in tables, "the rest of the schema must still be built"
        conn.close()


class TestOptimizeIsBestEffort:
    """`cache.optimize` swallows `sqlite3.Error` on purpose — and this chunk's
    headline defect *was* a swallowed `sqlite3.Error` hiding a broken store, so
    the swallow needs to be shown working rather than assumed.

    The distinction that makes it right here: `optimize` is housekeeping that runs
    after the rows have already landed and committed. Failing a good sync because
    a `VACUUM` lost a lock race to a concurrent agent would trade a real success
    for a tidiness step."""

    def test_a_failure_is_swallowed_rather_than_failing_a_good_sync(self, fake, repo_dir):
        _file(fake, title="cache: an item that synced fine", area="backlog")
        _rebuild(fake, repo_dir)
        locked = _Locked()

        cache.optimize(locked)  # must not raise

        assert locked.attempted, "the test proves nothing if optimize never tried"
        assert _item_ids(repo_dir), "the store must survive a failed optimize"

    def test_the_rebuild_still_succeeds_when_optimize_cannot_run(self, fake, repo_dir):
        """The property that actually matters to a caller: the sync's verdict does
        not depend on the housekeeping."""
        _file(fake, title="cache: an item that synced fine", area="backlog")

        with mock.patch.object(
            cache, "optimize", side_effect=sqlite3.OperationalError("database is locked")
        ):
            with pytest.raises(sqlite3.OperationalError):
                # Guard against the test passing because `optimize` was never
                # called at all: the patch has to be reached to prove anything.
                sync.full_rebuild(
                    fake, project_dir=repo_dir, owner=OWNER, repo=REPO, now=NOW
                )

        with mock.patch.object(cache, "optimize", return_value=None):
            result = sync.full_rebuild(
                fake, project_dir=repo_dir, owner=OWNER, repo=REPO, now=NOW
            )

        assert result["status"] == "ok", result


def _item_ids(repo_dir) -> list[str]:
    conn = sqlite3.connect(str(cache.cache_path(repo_dir)))
    rows = [row[0] for row in conn.execute("SELECT id FROM item ORDER BY id")]
    conn.close()
    return rows


class _WithoutFts5:
    """A connection on a SQLite compiled without FTS5.

    A stub rather than a patch because ``sqlite3.Connection.execute`` is
    read-only and cannot be replaced on an instance. Everything but the virtual
    table goes through to a real connection, so the assertion that the *rest* of
    the schema still builds is a fact about the real DDL."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, statement, *args):
        if "fts5" in statement.lower():
            raise sqlite3.OperationalError("no such module: fts5")
        return self._conn.execute(statement, *args)


class _Locked:
    """A connection whose every statement loses a lock race — what a concurrent
    agent's open reader looks like to ``VACUUM``. ``attempted`` is what keeps the
    test honest: a swallow that swallowed because nothing ran would pass too."""

    def __init__(self) -> None:
        self.attempted = False

    def execute(self, *_args):
        self.attempted = True
        raise sqlite3.OperationalError("database is locked")

    def commit(self):  # pragma: no cover — never reached; execute raises first
        raise sqlite3.OperationalError("database is locked")


# --- the CLI door: `prawduct-hook backlog cache-query` ------------------------


def _cq(repo_dir, *args, json_mode=True):
    """Run the op in-process and return ``(exit_code, envelope)``.

    In-process rather than by subprocess because the store lives under this
    ``repo_dir``'s git-common-dir and the envelope is what consumers bind to;
    spawning would test argv plumbing this module does not own. The subprocess
    shape is covered where it matters — `TestNothingDetachedEverRan` below.
    """
    import io
    import json as _json
    from contextlib import redirect_stdout

    from lib.backlog import cli

    argv = [*args, "--repo", SCOPE] + (["--json"] if json_mode else [])
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = cli.run(str(repo_dir), ["cache-query", *argv])
    out = buf.getvalue().strip()
    return code, (_json.loads(out) if json_mode and out else out)


class TestTheCacheQueryOp:
    """The agent-facing door onto ``cachequery``.

    Every consumer bound before this one was in-process Python, so the query
    surface needed no CLI. These consumers are agents — the Critic's
    reconciliation walk, the PR reviewer's checks, the janitor's Backlog Health —
    and an agent reaches a Python module only by running something.
    """

    #: Every sub-query and a valid argument list for it. Parametrized rather than
    #: written out per test so a query added to `_CACHE_QUERIES` without a case
    #: here fails the surface test below — the same shape `_every_query` gives the
    #: library surface one layer down.
    CASES = {
        "open": [],
        "unstaged": [],
        "by-area": [],
        "stale": [],
        "created-since": ["2026-01-01T00:00:00+00:00"],
        "search": ["item"],
        "affecting": ["plugin/lib/backlog/sync.py"],
        "resolve": [f"{SCOPE}#1"],
    }

    def test_every_dispatched_query_has_a_case_here(self):
        from lib.backlog import cli

        assert set(cli._CACHE_QUERIES) == set(self.CASES), (
            "a sub-query was added or removed without its case moving with it, so "
            "it is dispatched but never exercised"
        )

    def test_ready_is_not_exposed(self):
        """`ready_items` has exactly one consumer — `pick`, which is already an op
        — so exposing it here would give one query two operator-facing doors."""
        from lib.backlog import cli

        assert "ready" not in cli._CACHE_QUERIES
        assert "ready_items" in _every_query(Path("."))  # still on the library surface

    @pytest.mark.parametrize("name", sorted(CASES))
    def test_it_answers_from_a_populated_store(self, name, fake, repo_dir):
        _file(fake, title="cache: an item the queries can find", area="backlog",
              affected="plugin/lib/backlog/sync.py")
        _rebuild(fake, repo_dir)

        code, envelope = _cq(repo_dir, name, *self.CASES[name])

        assert code == 0, envelope
        assert envelope["status"] == "ok"
        # The store-level invariants ride out through the op unchanged; a door
        # that dropped them would be a consumer opting out of both at once.
        assert "age_seconds" in envelope["data"]
        assert envelope["data"]["scope"] == SCOPE

    @pytest.mark.parametrize("name", sorted(CASES))
    def test_an_absent_store_exits_6_rather_than_reporting_nothing(
        self, name, repo_dir
    ):
        """**The contract these consumers actually depend on.** A reader that
        cannot reach the store must be able to say so, and an exit code says it
        without the caller parsing prose. Reporting an empty set instead would
        rebuild, in a new costume, the silent-reader failure the dormant checks
        were made to announce."""
        code, envelope = _cq(repo_dir, name, *self.CASES[name])

        assert code == 6, (name, envelope)
        assert envelope["status"] == "error"
        assert envelope["error"]["code"] == "unavailable"
        assert "sync" in envelope["error"]["message"]

    def test_it_never_reaches_the_provider(self, fake, repo_dir):
        """No transport is resolved at all: the op takes no `transport` argument
        and imports nothing that egresses. Asserted by running with the network
        boundary poisoned, because "it reads locally" is the property the Critic
        reviewer's tool grant rests on."""
        _file(fake, title="cache: a locally answerable item", area="backlog")
        _rebuild(fake, repo_dir)

        with mock.patch("lib.backlog.transport.GhTransport.__init__",
                        side_effect=AssertionError("cache-query reached the provider")):
            code, envelope = _cq(repo_dir, "open")

        assert code == 0 and envelope["status"] == "ok"

    def test_it_writes_nothing(self, fake, repo_dir):
        """The other half of the grant's premise. `open_store(create=False)` means
        a query cannot even bring a store into being, so a reviewer holding this op
        cannot leave a trace in the tree it is reviewing."""
        _file(fake, title="cache: an item to read back", area="backlog")
        _rebuild(fake, repo_dir)
        before = {p: p.stat().st_mtime_ns for p in repo_dir.rglob("*") if p.is_file()}

        assert _cq(repo_dir, "open")[0] == 0

        after = {p: p.stat().st_mtime_ns for p in repo_dir.rglob("*") if p.is_file()}
        assert after == before

    def test_a_bare_issue_ref_resolves_against_the_stores_own_scope(self, fake, repo_dir):
        """`#621` is how citations are nearly always written — this repo's
        change-log carries 259 bare refs against 5 qualified ones, and `closes:
        #621` is the shape the PR reviewer's R-2 reads. `normalize_id` cannot
        qualify one on its own (it takes an owner and still needs a repo), so
        without this the restored checks would resolve almost nothing and report it
        as "no such item"."""
        item = _file(fake, title="cache: an item cited bare", area="backlog")
        _rebuild(fake, repo_dir)
        number = item.rsplit("#", 1)[1]

        code, envelope = _cq(repo_dir, "resolve", f"#{number}")

        assert code == 0
        assert envelope["data"]["resolved"] is True
        assert envelope["data"]["id"] == item

    def test_an_unresolvable_id_is_a_successful_answer(self, fake, repo_dir):
        """A miss is consumer 5's entire finding, so it must not arrive as an
        error — a dangling-id check that could not tell "no such item" from "the
        store is unreachable" would be exactly as blind as the one it replaced."""
        _file(fake, title="cache: some other item", area="backlog")
        _rebuild(fake, repo_dir)

        code, envelope = _cq(repo_dir, "resolve", f"{SCOPE}#999999")

        assert code == 0
        assert envelope["data"]["resolved"] is False

    def test_an_unknown_query_names_the_ones_that_exist(self, repo_dir):
        code, envelope = _cq(repo_dir, "nonesuch")
        assert code == 2
        assert "open" in envelope["error"]["message"]

    def test_a_missing_query_is_a_validation_error(self, repo_dir):
        assert _cq(repo_dir, )[0] == 2

    @pytest.mark.parametrize("name", ["open", "stale", "resolve", "search"])
    def test_all_is_refused_where_it_does_not_apply(self, name, repo_dir):
        """Refused rather than ignored. `--all` widens the two groupings that
        default to open-only; on a query whose predicate already IS a status,
        silently accepting it would hand back an unwidened answer the caller
        believes was widened."""
        code, envelope = _cq(repo_dir, name, *TestTheCacheQueryOp.CASES[name], "--all")
        assert code == 2
        assert name in envelope["error"]["message"]

    def test_all_widens_the_groupings_that_take_it(self, fake, repo_dir):
        live = _file(fake, title="cache: a live item", area="backlog")
        done = _file(fake, title="cache: a shipped item", area="backlog")
        assert core.set_status(fake, id_raw=done, target="shipped")["status"] == "ok"
        _rebuild(fake, repo_dir)

        default = _cq(repo_dir, "by-area")[1]["data"]
        widened = _cq(repo_dir, "by-area", "--all")[1]["data"]

        def _all_ids(payload):
            return {i["id"] for g in payload["groups"] for i in g["items"]}

        assert _all_ids(default) == {live}
        assert _all_ids(widened) == {live, done}

    @pytest.mark.parametrize(
        ("argv", "why"),
        [
            (["stale", "60"], "a bare 60 reads as --older-than 60 and would silently answer 90"),
            (["open", "extra"], "an unexpected positional"),
            (["by-area", "stray"], "an unexpected positional on a zero-arg query"),
            (["open", "--area", "governance"], "a valued flag this query does not read"),
            (["search", "foo", "--older-than", "3"], "a valued flag belonging to another query"),
            (["resolve", "a", "b"], "two ids where the query takes one"),
        ],
    )
    def test_it_refuses_what_a_query_does_not_take(self, argv, why, repo_dir):
        """**Refused, never ignored** — the same policy `--all` already had, applied
        to the rest of the surface. One dispatcher holding two opposite policies is
        how `cache-query stale 60` came to return the 90-day set as `status: ok`:
        a wrong answer that looks right, which is the failure this whole surface
        exists to prevent."""
        code, envelope = _cq(repo_dir, *argv)
        assert code == 2, (argv, why, envelope)
        assert envelope["error"]["code"] == "validation"

    def test_every_query_has_an_arity_and_a_flag_set(self):
        """The two tables are data beside `_CACHE_QUERIES`, so a query added
        without an entry raises at dispatch rather than silently accepting
        anything — which is the failure mode the tables were added to fix."""
        from lib.backlog import cli

        assert set(cli._CACHE_QUERY_ARITY) == set(cli._CACHE_QUERIES)
        assert set(cli._CACHE_QUERY_FLAGS) == set(cli._CACHE_QUERIES)

    @pytest.mark.parametrize("name", sorted(CASES))
    def test_human_mode_renders_every_shape_with_its_age(self, name, fake, repo_dir):
        """`boundary-patterns.md` records "Result Envelopes" as a contract surface
        with TWO consumers — the `--json` passthrough and the human formatters —
        and its recurring defect is that a `--json`-only test never runs the
        second. It did so again: `unstaged` printed its items and then `0 item(s)`,
        a `resolve` miss printed `status=None`, and `by-area` dumped raw JSON. So
        human mode is exercised here for every shape.
        """
        _file(fake, title="cache: an item every shape can render", area="backlog",
              affected="plugin/lib/backlog/sync.py")
        _rebuild(fake, repo_dir)

        code, text = _cq(repo_dir, name, *TestTheCacheQueryOp.CASES[name], json_mode=False)

        assert code == 0
        assert not text.lstrip().startswith("{"), (
            f"{name} fell through to a raw JSON dump in human mode"
        )
        assert "cache:" in text, (
            f"{name}'s human output drops the visible age — the invariant every "
            f"payload carries, and the one `cache-reads.md` tells readers to name"
        )

    def test_human_mode_counts_the_rows_it_printed(self, fake, repo_dir):
        item = _file(fake, title="cache: an item with no stage at all", area="backlog")
        _rebuild(fake, repo_dir)

        _code, text = _cq(repo_dir, "unstaged", json_mode=False)

        assert item in text
        assert "1 item(s)" in text, "the printed rows and the count disagreed"
        assert "0 item(s)" not in text

    def test_human_mode_reports_a_resolve_miss_as_a_miss(self, fake, repo_dir):
        """A miss is consumer 5's whole finding. Printing `status=None` for it
        loses both that it was a miss and why — and a reader cannot tell "no such
        item" from "that is not an id", which send them to different repairs."""
        _file(fake, title="cache: some unrelated item", area="backlog")
        _rebuild(fake, repo_dir)

        _code, text = _cq(repo_dir, "resolve", f"{SCOPE}#999999", json_mode=False)

        assert "unresolved" in text
        assert "status=None" not in text

    def test_the_ephemeral_guard_classifies_it_read_only(self):
        """An op missing from the guard's classification is ALLOWED on a
        service-backed repo, because the service-backed early return fires before
        the per-op set — precisely the stranded write that guard exists to refuse.
        So the classification is asserted, not assumed."""
        import importlib.util

        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_loader("_hook", loader=None)
        hook = importlib.util.module_from_spec(spec)
        exec(  # noqa: S102 — the hook is a script, not an importable module
            compile((root / "plugin" / "bin" / "prawduct-hook").read_text(),
                    "prawduct-hook", "exec"),
            hook.__dict__,
        )
        assert "cache-query" in hook._EPHEMERAL_READ_ONLY_OPS["backlog"]
        assert "cache-query" not in hook._BACKLOG_LOCAL_WRITE_OPS
