"""Tests for the HTTP client + transport seam (``lib/backlog_github.py``) and the
walking-skeleton behavior observed through the command boundary
(``lib/backlog_service_cmd.py``).

Covers request construction (auth/accept/version headers), response normalization,
transport-level error surfacing, the token bootstrap (env precedence + the
list-form ``gh auth token`` subprocess, never ``shell=True``), the token-never-in-
output guarantee, and — through a faked transport built from the captured
``api-notes`` shapes — the ``add`` / ``get`` / ``list`` round-trip and the
never-block floor (fast retryable failure, correct exit code, no traceback,
nothing written locally).
"""

from __future__ import annotations

import json as _json
from pathlib import Path

import pytest

from lib import backlog_github as gh
from lib import backlog_service as svc
from lib import backlog_service_cmd as cmd

TOKEN = "gho_SEKRET_test_token_do_not_leak"
OWNER = "brookstalley"
REPO = "prawduct-backlog-scratch"


def _resp(status, json_obj, headers=None):
    body = _json.dumps(json_obj).encode("utf-8") if json_obj is not None else b""
    return {"status": status, "headers": headers or {}, "body": body}


class FakeTransport:
    """Records requests; returns canned TransportResults (a value, a list by call
    order, or a callable). Same dict shape the real transport returns."""

    def __init__(self, responses):
        self.calls: list[dict] = []
        self._responses = responses

    def __call__(self, method, url, headers, body, timeout):
        self.calls.append(
            {"method": method, "url": url, "headers": headers, "body": body, "timeout": timeout}
        )
        responses = self._responses
        if callable(responses):
            return responses(method, url, headers, body)
        if isinstance(responses, list):
            return responses[len(self.calls) - 1]
        return responses


def _issue_from_create(method, url, headers, body):
    """A create fake that echoes the posted title/body/labels back as an issue —
    a faithful encode -> (server) -> decode round-trip."""
    payload = _json.loads(body)
    issue = {
        "number": 7,
        "node_id": "I_kwDOexample",
        "state": "open",
        "state_reason": None,
        "title": payload["title"],
        "body": payload.get("body", ""),
        "labels": [{"name": name} for name in payload.get("labels", [])],
        "assignees": [],
        "issue_dependencies_summary": {"blocked_by": 0, "total_blocked_by": 0},
        "sub_issues_summary": {"total": 0, "completed": 0},
        "created_at": "2026-07-16T20:00:00Z",
        "updated_at": "2026-07-16T20:00:00Z",
        "html_url": f"https://github.com/{OWNER}/{REPO}/issues/7",
    }
    return _resp(201, issue)


class TestResolveToken:
    def test_gh_token_env_wins(self):
        assert gh.resolve_token({"GH_TOKEN": "from_env"}) == "from_env"

    def test_github_token_alias_when_gh_token_absent(self):
        assert gh.resolve_token({"GITHUB_TOKEN": "ci_alias"}) == "ci_alias"

    def test_gh_token_precedes_github_token(self):
        assert gh.resolve_token({"GH_TOKEN": "primary", "GITHUB_TOKEN": "alias"}) == "primary"

    def test_gh_subprocess_fallback_is_list_form_never_shell(self, monkeypatch):
        recorded = {}

        class _Completed:
            returncode = 0
            stdout = "gho_from_gh_cli\n"

        def fake_run(args, **kwargs):
            recorded["args"] = args
            recorded["kwargs"] = kwargs
            return _Completed()

        monkeypatch.setattr(gh.subprocess, "run", fake_run)
        token = gh.resolve_token({})  # no env tokens -> gh fallback
        assert token == "gho_from_gh_cli"
        assert recorded["args"] == ["gh", "auth", "token"]  # list form
        assert recorded["kwargs"].get("shell") is not True  # never shell=True

    def test_gh_missing_binary_falls_through_to_none(self, monkeypatch):
        def boom(*a, **k):
            raise FileNotFoundError("gh not installed")

        monkeypatch.setattr(gh.subprocess, "run", boom)
        assert gh.resolve_token({}) is None


class TestRequestConstruction:
    def test_headers_and_url(self):
        transport = FakeTransport(_resp(200, {"number": 1, "title": "x", "state": "open"}))
        client = gh.GitHubClient(TOKEN, transport=transport)
        client.get_issue(OWNER, REPO, 1)
        call = transport.calls[0]
        assert call["url"] == f"{gh.API_ROOT}/repos/{OWNER}/{REPO}/issues/1"
        assert call["headers"]["Authorization"] == f"Bearer {TOKEN}"
        assert call["headers"]["Accept"] == "application/vnd.github+json"
        assert call["headers"]["X-GitHub-Api-Version"] == gh.API_VERSION
        assert "User-Agent" in call["headers"]

    def test_post_sets_content_type_and_json_body(self):
        transport = FakeTransport(_resp(201, {"number": 2, "title": "t", "state": "open"}))
        client = gh.GitHubClient(TOKEN, transport=transport)
        client.create_issue(OWNER, REPO, {"title": "t", "body": "b"})
        call = transport.calls[0]
        assert call["method"] == "POST"
        assert call["headers"]["Content-Type"] == "application/json"
        assert _json.loads(call["body"]) == {"title": "t", "body": "b"}

    def test_list_params_encoded_in_query(self):
        transport = FakeTransport(_resp(200, []))
        client = gh.GitHubClient(TOKEN, transport=transport)
        client.list_issues(OWNER, REPO, {"state": "open", "per_page": 100})
        assert "state=open" in transport.calls[0]["url"]
        assert "per_page=100" in transport.calls[0]["url"]


class TestNormalize:
    def test_2xx_parses_json(self):
        transport = FakeTransport(_resp(200, {"number": 1}))
        result = gh.GitHubClient(TOKEN, transport=transport).get_issue(OWNER, REPO, 1)
        assert result["ok"] and result["json"] == {"number": 1}

    def test_http_error_carries_status_and_message(self):
        transport = FakeTransport(_resp(404, {"message": "Not Found", "status": "404"}))
        result = gh.GitHubClient(TOKEN, transport=transport).get_issue(OWNER, REPO, 999)
        assert not result["ok"] and result["status"] == 404 and result["message"] == "Not Found"

    def test_network_failure_has_no_status(self):
        transport = FakeTransport({"status": None, "network_reason": "dns", "message": "no route"})
        result = gh.GitHubClient(TOKEN, transport=transport).get_issue(OWNER, REPO, 1)
        assert not result["ok"] and result["status"] is None and result["network_reason"] == "dns"


class TestParseNextLink:
    def test_extracts_next(self):
        header = '<https://api.github.com/x?after=abc&page=2>; rel="next", <https://…>; rel="last"'
        assert gh.parse_next_link(header) == "https://api.github.com/x?after=abc&page=2"

    def test_none_when_no_next(self):
        assert gh.parse_next_link('<https://…>; rel="prev"') is None
        assert gh.parse_next_link(None) is None


class TestRoundTripThroughClient:
    """add / get / list through the real client + faked transport (captured shapes)."""

    def test_add_round_trips_body_block_intact(self):
        transport = FakeTransport(_issue_from_create)
        client = gh.GitHubClient(TOKEN, transport=transport)
        result = svc.create_item(
            client, OWNER, REPO, "New item", body="Some body.", stage="ready", added="2026-07-13"
        )
        assert result["ok"]
        item = result["item"]
        assert item["id"] == f"{OWNER}/{REPO}#7"
        assert item["stage"] == "ready"
        assert item["added"] == "2026-07-13"  # the block survived encode -> server -> decode

    def test_get_rejects_pull_request(self):
        pr_obj = {"number": 4, "title": "a PR", "state": "open", "pull_request": {"url": "…"}}
        client = gh.GitHubClient(TOKEN, transport=FakeTransport(_resp(200, pr_obj)))
        result = svc.get_item(client, OWNER, REPO, 4)
        assert not result["ok"] and result["error"]["kind"] == "not_found"

    def test_list_drops_prs_and_follows_link_cursor(self):
        page1 = [
            {"number": 1, "title": "one", "state": "open", "updated_at": "2026-07-16T10:00:00Z"},
            {"number": 4, "title": "pr", "state": "open", "pull_request": {}},
        ]
        page2 = [
            {"number": 2, "title": "two", "state": "open", "updated_at": "2026-07-16T12:00:00Z"}
        ]
        responses = [
            _resp(200, page1, headers={"link": '<https://api.github.com/next>; rel="next"'}),
            _resp(200, page2),
        ]
        client = gh.GitHubClient(TOKEN, transport=FakeTransport(responses))
        result = svc.list_items(client, OWNER, REPO)
        assert result["ok"]
        data = result["data"]
        assert data["count"] == 2  # PR dropped, both pages merged
        assert data["cursor"] == "2026-07-16T12:00:00Z"  # max updated_at

    def test_list_limit_truncates(self):
        page = [
            {"number": n, "title": str(n), "state": "open", "updated_at": f"2026-07-16T1{n}:00:00Z"}
            for n in range(1, 5)
        ]
        client = gh.GitHubClient(TOKEN, transport=FakeTransport(_resp(200, page)))
        result = svc.list_items(client, OWNER, REPO, limit=2)
        assert result["ok"] and result["data"]["count"] == 2


class TestNeverBlockFloorAndSecurity:
    """The G2 floor + the token-never-in-output guarantee, at the command boundary."""

    def _run_cmd(self, tmp_path, argv, monkeypatch, transport, token=TOKEN):
        monkeypatch.setenv("GH_TOKEN", token)
        monkeypatch.setattr(gh, "urllib_transport", transport)
        return cmd.run(tmp_path, argv)

    def test_network_cut_add_fails_fast_retryable_no_local_write(self, tmp_path, monkeypatch, capsys):
        cut = FakeTransport(
            lambda m, u, h, b: {"status": None, "network_reason": "connect", "message": "connection refused"}
        )
        argv = ["add", "--title", "X", "--repo", f"{OWNER}/{REPO}", "--json"]
        exit_code = self._run_cmd(tmp_path, argv, monkeypatch, cut)
        out = capsys.readouterr().out
        envelope = _json.loads(out)
        assert exit_code == 3  # retryable, the shell-visible never-block signal
        assert envelope["ok"] is False
        assert envelope["error"]["kind"] == "network" and envelope["error"]["retryable"] is True
        # nothing half-written: the P0 slice keeps no local store
        assert list(tmp_path.iterdir()) == []

    def test_no_traceback_on_operational_failure(self, tmp_path, monkeypatch, capsys):
        argv = ["get", f"{OWNER}/{REPO}#999", "--repo", f"{OWNER}/{REPO}", "--json"]
        transport = FakeTransport(_resp(404, {"message": "Not Found"}))
        exit_code = self._run_cmd(tmp_path, argv, monkeypatch, transport)
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "Traceback" not in captured.err
        assert _json.loads(captured.out)["error"]["kind"] == "not_found"

    def test_token_never_appears_in_output_on_auth_failure(self, tmp_path, monkeypatch, capsys):
        argv = ["get", f"{OWNER}/{REPO}#1", "--repo", f"{OWNER}/{REPO}", "--json"]
        transport = FakeTransport(_resp(401, {"message": "Bad credentials"}))
        exit_code = self._run_cmd(tmp_path, argv, monkeypatch, transport)
        captured = capsys.readouterr()
        assert exit_code == 1
        assert TOKEN not in captured.out and TOKEN not in captured.err

    def test_missing_token_is_auth_error_never_prompts(self, tmp_path, monkeypatch, capsys):
        monkeypatch.delenv("GH_TOKEN", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setattr(gh, "resolve_token", lambda env=None: None)
        exit_code = cmd.run(tmp_path, ["get", f"{OWNER}/{REPO}#1", "--repo", f"{OWNER}/{REPO}", "--json"])
        envelope = _json.loads(capsys.readouterr().out)
        assert exit_code == 1 and envelope["error"]["kind"] == "auth"


class TestArgValidation:
    def test_bad_flag_rejects_before_any_mutation(self, tmp_path, monkeypatch, capsys):
        # A mutating command must validate leftover flags BEFORE calling the API,
        # so a bogus flag never orphans a created issue behind a usage error.
        transport = FakeTransport(_issue_from_create)
        monkeypatch.setenv("GH_TOKEN", TOKEN)
        monkeypatch.setattr(gh, "urllib_transport", transport)
        exit_code = cmd.run(
            tmp_path, ["add", "--title", "X", "--bogus", "--repo", f"{OWNER}/{REPO}", "--json"]
        )
        envelope = _json.loads(capsys.readouterr().out)
        assert exit_code == 2 and envelope["error"]["kind"] == "usage"
        assert transport.calls == []  # no create was attempted

    def test_since_flag_is_deferred_not_supported(self, tmp_path, monkeypatch, capsys):
        transport = FakeTransport(_resp(200, []))
        monkeypatch.setenv("GH_TOKEN", TOKEN)
        monkeypatch.setattr(gh, "urllib_transport", transport)
        exit_code = cmd.run(
            tmp_path, ["list", "--since", "2026-07-16T00:00:00Z", "--repo", f"{OWNER}/{REPO}", "--json"]
        )
        envelope = _json.loads(capsys.readouterr().out)
        assert exit_code == 2 and envelope["error"]["kind"] == "usage"
        assert transport.calls == []  # rejected before the query


class TestCommandRendering:
    def test_json_add_envelope_shape(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("GH_TOKEN", TOKEN)
        monkeypatch.setattr(gh, "urllib_transport", FakeTransport(_issue_from_create))
        exit_code = cmd.run(
            tmp_path, ["add", "--title", "Hello", "--stage", "ready", "--repo", f"{OWNER}/{REPO}", "--json"]
        )
        envelope = _json.loads(capsys.readouterr().out)
        assert exit_code == 0 and envelope["v"] == 1 and envelope["ok"] is True
        assert envelope["data"]["id"] == f"{OWNER}/{REPO}#7"

    def test_human_list_line_format(self, tmp_path, monkeypatch, capsys):
        page = [{
            "number": 1, "title": "A task", "state": "open",
            "labels": [{"name": "pb:stage:ready"}, {"name": "pb:area:hooks"}],
            "updated_at": "2026-07-16T10:00:00Z",
        }]
        monkeypatch.setenv("GH_TOKEN", TOKEN)
        monkeypatch.setattr(gh, "urllib_transport", FakeTransport(_resp(200, page)))
        exit_code = cmd.run(tmp_path, ["list", "--repo", f"{OWNER}/{REPO}"])
        out = capsys.readouterr().out
        assert exit_code == 0
        assert f"{OWNER}/{REPO}#1" in out and "[stage:ready]" in out and "A task" in out
