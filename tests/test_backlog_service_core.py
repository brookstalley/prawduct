"""Tests for the backlog-service core encoding (``lib/backlog_service.py``).

Pins the prawduct<->GitHub seam the walking skeleton and every later chunk build
on: the ID grammar, the create encoding, the ``prawduct:`` body-block round-trip,
the raw-issue decode, and the mapping of a client result into the stable
``error.kind`` vocabulary. Encoding facts (label shapes, ``state_reason`` cycle,
list-item field inventory) trace to the captured shapes in
``api-notes-github-issues.md``.
"""

from __future__ import annotations

from lib import backlog_service as svc

OWNER = "brookstalley"
REPO = "prawduct-backlog-scratch"


# A representative captured issue object (api-notes "Issue object").
def _raw_issue(**overrides):
    raw = {
        "number": 1,
        "id": 4904408044,
        "node_id": "I_kwDOTasGxM8AAAABJFNT7A",
        "state": "open",
        "state_reason": None,
        "title": "Probe item one",
        "body": "Item body line.\n\n```prawduct\nadded: 2026-07-13\nrelated: prawduct#40, SOL-K3PN\n```\n",
        "labels": [
            {"name": "pb:stage:ready", "color": "0e8a16"},
            {"name": "pb:area:hooks", "color": "1d76db"},
            {"name": "good first issue", "color": "7057ff"},
        ],
        "assignees": [{"login": "brookstalley"}],
        "issue_dependencies_summary": {"blocked_by": 0, "total_blocked_by": 1},
        "sub_issues_summary": {"total": 1, "completed": 0},
        "created_at": "2026-07-16T17:19:30Z",
        "updated_at": "2026-07-16T18:00:00Z",
        "html_url": "https://github.com/brookstalley/prawduct-backlog-scratch/issues/1",
    }
    raw.update(overrides)
    return raw


class TestNormalizeId:
    def test_owner_repo_number_canonical(self):
        result = svc.normalize_id("brookstalley/prawduct#42", OWNER, REPO)
        assert result["ok"] and result["canonical"] == "brookstalley/prawduct#42"
        assert result["number"] == 42 and result["owner"] == "brookstalley"

    def test_repo_short_form_resolves_owner_from_config(self):
        result = svc.normalize_id(f"{REPO}#7", OWNER, REPO)
        assert result["ok"] and result["canonical"] == f"{OWNER}/{REPO}#7"

    def test_repo_slash_number(self):
        result = svc.normalize_id(f"{REPO}/9", OWNER, REPO)
        assert result["ok"] and result["number"] == 9

    def test_repo_hyphen_number_when_left_is_configured_repo(self):
        result = svc.normalize_id(f"{REPO}-42", OWNER, REPO)
        assert result["ok"] and result["form"] == "number" and result["number"] == 42

    def test_bare_number_rejected_as_ambiguous(self):
        for token in ("42", "#42"):
            result = svc.normalize_id(token, OWNER, REPO)
            assert not result["ok"] and result["reason"] == "ambiguous_id"

    def test_short_form_cross_repo_is_ambiguous(self):
        result = svc.normalize_id("otherrepo#5", OWNER, REPO)
        assert not result["ok"] and result["reason"] == "ambiguous_id"

    def test_legacy_alias_detected_not_mistaken_for_number(self):
        # REL-3M7K: right side of the last hyphen is not all-digits -> alias.
        result = svc.normalize_id("REL-3M7K", OWNER, REPO)
        assert result["ok"] and result["form"] == "alias" and result["alias"] == "REL-3M7K"

    def test_hyphen_number_with_foreign_left_is_alias(self):
        # foo-42: right is digits but left != configured repo -> a legacy alias,
        # not a number-bearing ref (grammar §4).
        result = svc.normalize_id("foo-42", OWNER, REPO)
        assert result["ok"] and result["form"] == "alias" and result["alias"] == "foo-42"

    def test_empty_rejected(self):
        assert not svc.normalize_id("", OWNER, REPO)["ok"]


class TestBodyBlockRoundTrip:
    def test_render_then_parse_recovers_fields_and_body(self):
        body_above = "First line.\n\nSecond paragraph."
        block = {"added": "2026-07-13", "verified": "2026-07-16 brookstalley"}
        rendered = svc.render_body(body_above, block)
        parsed_above, parsed_block, warnings = svc.parse_body_block(rendered)
        assert parsed_above == body_above
        assert parsed_block == block
        assert warnings == []

    def test_empty_block_renders_body_only(self):
        assert svc.render_body("just a body", {}) == "just a body"

    def test_body_without_block_parses_to_empty(self):
        above, block, warnings = svc.parse_body_block("plain body, no block")
        assert above == "plain body, no block" and block == {} and warnings == []

    def test_second_block_is_flagged_first_wins(self):
        body = (
            "```prawduct\nadded: 2026-07-13\n```\n\n"
            "```prawduct\nadded: 2099-01-01\n```\n"
        )
        _above, block, warnings = svc.parse_body_block(body)
        assert block["added"] == "2026-07-13"
        assert "multiple_prawduct_blocks" in warnings

    def test_unterminated_fence_is_not_a_block(self):
        _above, block, _warnings = svc.parse_body_block("```prawduct\nadded: x")
        assert block == {}


class TestEncodeCreate:
    def test_title_only(self):
        payload, warnings = svc.encode_create("Just a title")
        assert payload["title"] == "Just a title"
        assert "labels" not in payload
        assert warnings == []

    def test_stage_becomes_label_and_added_rides_in_block(self):
        payload, warnings = svc.encode_create(
            "T", body="Body.", stage="ready", added="2026-07-13"
        )
        assert "pb:stage:ready" in payload["labels"]
        assert "```prawduct" in payload["body"] and "added: 2026-07-13" in payload["body"]
        assert warnings == []

    def test_unknown_stage_flagged_but_still_written(self):
        payload, warnings = svc.encode_create("T", stage="bogus")
        assert "pb:stage:bogus" in payload["labels"]  # tolerant validator: still written
        assert any(w.startswith("unknown_stage_value") for w in warnings)

    def test_explicit_labels_preserved(self):
        payload, _ = svc.encode_create("T", labels=["pb:area:hooks", "good first issue"])
        assert "pb:area:hooks" in payload["labels"] and "good first issue" in payload["labels"]


class TestDecodeIssue:
    def test_open_item_full_projection(self):
        item, warnings = svc.decode_issue(_raw_issue(), OWNER, REPO)
        assert item["id"] == f"{OWNER}/{REPO}#1"
        assert item["status"] == "open" and item["stage"] == "ready"
        assert item["facets"] == {"area": "hooks"}
        assert item["labels_other"] == ["good first issue"]
        assert item["assignees"] == ["brookstalley"]
        assert item["added"] == "2026-07-13"
        assert item["related"] == ["prawduct#40", "SOL-K3PN"]
        assert item["blocked_by_count"] == 0
        assert item["node"] == "I_kwDOTasGxM8AAAABJFNT7A"
        assert warnings == []

    def test_in_progress_status_from_label(self):
        raw = _raw_issue(labels=[{"name": "pb:status:in-progress"}])
        item, _ = svc.decode_issue(raw, OWNER, REPO)
        assert item["status"] == "in-progress"

    def test_closed_completed_is_shipped(self):
        raw = _raw_issue(state="closed", state_reason="completed")
        item, warnings = svc.decode_issue(raw, OWNER, REPO)
        assert item["status"] == "shipped" and warnings == []

    def test_closed_not_planned_is_dropped(self):
        raw = _raw_issue(state="closed", state_reason="not_planned")
        item, _ = svc.decode_issue(raw, OWNER, REPO)
        assert item["status"] == "dropped"

    def test_closed_without_reason_defaults_shipped_with_flag(self):
        raw = _raw_issue(state="closed", state_reason="reopened")
        item, warnings = svc.decode_issue(raw, OWNER, REPO)
        assert item["status"] == "shipped" and "closed_without_reason" in warnings

    def test_conflicting_stage_labels_pick_minimum_and_flag(self):
        raw = _raw_issue(labels=[{"name": "pb:stage:ready"}, {"name": "pb:stage:design"}])
        item, warnings = svc.decode_issue(raw, OWNER, REPO)
        assert item["stage"] == "design"  # minimum by maturity
        assert "conflicting_stage_labels" in warnings

    def test_conflicting_status_labels_pick_in_progress_and_flag(self):
        raw = _raw_issue(
            labels=[{"name": "pb:status:submitted"}, {"name": "pb:status:in-progress"}]
        )
        item, warnings = svc.decode_issue(raw, OWNER, REPO)
        assert item["status"] == "in-progress" and "conflicting_status_labels" in warnings

    def test_alias_label_decoded(self):
        raw = _raw_issue(labels=[{"name": "pb:id:BKL-5D2C"}])
        item, _ = svc.decode_issue(raw, OWNER, REPO)
        assert item["alias"] == "BKL-5D2C"


class TestClassifyError:
    def _err(self, status, headers=None, message=""):
        return svc.classify_error(
            {"ok": False, "status": status, "headers": headers or {}, "message": message}
        )

    def test_network_is_retryable(self):
        err = svc.classify_error({"ok": False, "status": None, "network_reason": "timeout"})
        assert err["kind"] == "network" and err["retryable"] is True

    def test_401_is_auth(self):
        assert self._err(401, message="Bad credentials")["kind"] == "auth"

    def test_404_is_not_found(self):
        assert self._err(404)["kind"] == "not_found"

    def test_422_is_validation(self):
        assert self._err(422)["kind"] == "validation"

    def test_429_is_rate_limited(self):
        err = self._err(429, headers={"retry-after": "42"})
        assert err["kind"] == "rate_limited" and err["retry_after"] == 42 and err["retryable"]

    def test_403_with_rate_headers_is_rate_limited(self):
        err = self._err(403, headers={"x-ratelimit-remaining": "0"})
        assert err["kind"] == "rate_limited" and err["retryable"]

    def test_bare_403_is_auth_not_rate_limited(self):
        # A permission 403 without rate signals must not be mistaken for a rate limit.
        err = self._err(403, headers={"x-ratelimit-remaining": "4999"})
        assert err["kind"] == "auth" and err["retryable"] is False

    def test_5xx_is_server_retryable(self):
        err = self._err(503)
        assert err["kind"] == "server" and err["retryable"]

    def test_request_id_surfaced_in_detail(self):
        err = self._err(500, headers={"x-github-request-id": "ABC:123"})
        assert err["detail"]["github_request_id"] == "ABC:123"

    def test_exit_codes(self):
        assert svc.exit_code_for("usage") == 2
        assert svc.exit_code_for("auth") == 1
        assert svc.exit_code_for("network") == 3
        assert svc.exit_code_for("rate_limited") == 3
