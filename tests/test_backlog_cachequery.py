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
