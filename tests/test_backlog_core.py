"""Tests for lib/backlog/core.py — file / get / provision via the L1 fake.

Covers the envelope (ERR-3/ERR-4), the file→get round-trip, SEC-3 attribution
(API identity, resolved once), ERR-6 boundary-exception handling, and PROV-1
(namespaced labels created without colliding).
"""

from __future__ import annotations

import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.backlog import core  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402

OWNER, REPO = "octo", "repo"


@pytest.fixture
def fake():
    return FakeGitHub()


class TestFileItem:
    def test_returns_ok_envelope_with_immediate_id(self, fake):
        result = core.file_item(fake, owner=OWNER, repo=REPO, title="Do X", body="why")
        assert result["status"] == "ok"
        assert result["data"]["id"] == "octo/repo#1"
        assert result["data"]["number"] == 1
        assert result["data"]["node_id"]
        assert result["warnings"] == []

    def test_new_item_defaults_to_open(self, fake):
        result = core.file_item(fake, owner=OWNER, repo=REPO, title="X", body="b")
        assert result["data"]["status"] == "open"  # no status: label

    def test_stage_facet_provisioned_and_applied(self, fake):
        result = core.file_item(
            fake, owner=OWNER, repo=REPO, title="X", body="b", facets={"stage": "ready"}
        )
        assert result["status"] == "ok"
        assert result["data"]["stage"] == "ready"
        assert "stage:ready" in {name for name in fake.repos[(OWNER, REPO)].labels}

    def test_unknown_stage_warns_but_succeeds(self, fake):
        # ENC-1 at the op level — flagged, not rejected.
        result = core.file_item(
            fake, owner=OWNER, repo=REPO, title="X", body="b", facets={"stage": "brainstorm"}
        )
        assert result["status"] == "ok"
        assert result["data"]["stage"] == "brainstorm"
        assert any("brainstorm" in w for w in result["warnings"])

    def test_missing_title_is_validation(self, fake):
        result = core.file_item(fake, owner=OWNER, repo=REPO, title="  ", body="b")
        assert result["status"] == "error"
        assert result["error"]["code"] == "validation"

    def test_body_carries_prawduct_block(self, fake):
        core.file_item(fake, owner=OWNER, repo=REPO, title="X", body="the body")
        issue = fake.repos[(OWNER, REPO)].issues[1]
        assert "```prawduct" in issue["body"]
        assert "v: 1" in issue["body"]
        assert "the body" in issue["body"]


class TestAttribution:
    """SEC-3 — actor is the API identity, resolved once across a sweep."""

    def test_actor_is_api_identity(self, fake):
        result = core.file_item(fake, owner=OWNER, repo=REPO, title="X", body="b")
        assert result["data"]["actor"] == fake.user["login"]

    def test_identity_resolved_once_across_a_sweep(self, fake):
        for n in range(3):
            core.file_item(fake, owner=OWNER, repo=REPO, title=f"X{n}", body="b")
        # One resolution for the whole sweep — not one per mutation.
        assert fake.user_resolutions == 1


class TestGetItem:
    def test_file_then_get_round_trip(self, fake):
        filed = core.file_item(
            fake, owner=OWNER, repo=REPO, title="Round trip", body="b", facets={"stage": "ready"}
        )
        got = core.get_item(fake, id_raw=filed["data"]["id"])
        assert got["status"] == "ok"
        assert got["data"]["id"] == "octo/repo#1"
        assert got["data"]["title"] == "Round trip"
        assert got["data"]["stage"] == "ready"

    def test_get_short_form_with_default_owner(self, fake):
        core.file_item(fake, owner=OWNER, repo=REPO, title="X", body="b")
        got = core.get_item(fake, id_raw="repo#1", default_owner=OWNER)
        assert got["status"] == "ok"
        assert got["data"]["id"] == "octo/repo#1"

    def test_get_missing_is_not_found(self, fake):
        got = core.get_item(fake, id_raw="octo/repo#999")
        assert got["status"] == "error"
        assert got["error"]["code"] == "not_found"

    def test_get_bad_id_is_validation(self, fake):
        got = core.get_item(fake, id_raw="not-an-id-at-all")
        assert got["status"] == "error"
        assert got["error"]["code"] == "validation"


class TestBoundaryExceptions:
    """ERR-6 — an unexpected transport OSError is caught and mapped, not swallowed."""

    def test_unexpected_oserror_maps_to_unavailable(self, fake):
        class Broken(FakeGitHub):
            def create_issue(self, *a, **k):
                raise OSError("socket exploded")

        result = core.file_item(Broken(), owner=OWNER, repo=REPO, title="X", body="b")
        assert result["status"] == "error"
        assert result["error"]["code"] == "unavailable"


class TestProvision:
    """PROV-1 — namespaced labels created without colliding; existing untouched."""

    def test_creates_base_taxonomy(self, fake):
        result = core.provision_labels(fake, owner=OWNER, repo=REPO)
        assert result["status"] == "ok"
        created = set(result["data"]["created"])
        assert "stage:ready" in created
        assert "status:in-progress" in created

    def test_existing_non_prawduct_label_untouched(self, fake):
        fake.seed_labels(OWNER, REPO, ["bug"])
        before = dict(fake.repos[(OWNER, REPO)].labels["bug"])
        result = core.provision_labels(fake, owner=OWNER, repo=REPO)
        assert "bug" not in result["data"]["created"]
        assert fake.repos[(OWNER, REPO)].labels["bug"] == before  # not modified

    def test_provision_is_idempotent(self, fake):
        first = core.provision_labels(fake, owner=OWNER, repo=REPO)
        second = core.provision_labels(fake, owner=OWNER, repo=REPO)
        assert second["data"]["created"] == []
        assert set(second["data"]["existing"]) == set(first["data"]["created"])


class TestEnvelopeShape:
    """ERR-3 / ERR-4 — uniform ok/error/warnings structure."""

    def test_ok_shape(self):
        env = core.ok({"a": 1}, ["heads up"])
        assert env == {"status": "ok", "data": {"a": 1}, "warnings": ["heads up"]}

    def test_error_shape_and_retryable_default(self):
        env = core.error("unavailable", "down")
        assert env["status"] == "error"
        assert env["error"]["code"] == "unavailable"
        assert env["error"]["retryable"] is True  # from the vocabulary default
        assert env["error"]["details"] == {}

    def test_validation_is_not_retryable(self):
        assert core.error("validation", "bad")["error"]["retryable"] is False
