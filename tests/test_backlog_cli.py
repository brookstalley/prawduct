"""Tests for lib/backlog/cli.py — the CLI front, driven with the L1 fake.

Covers ERR-2 (JSON is the sole stdout content; diagnostics to stderr), ERR-1 (each
error code → a stable non-zero exit class), the file/get/provision happy paths
through the runner, and INV-2 (non-interactive — never reads stdin).
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _TESTS_DIR.parent
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.backlog import cli  # noqa: E402
from lib.backlog.transport import TransportError  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402

REPO = "octo/repo"


def _run(argv, fake, capsys):
    code = cli.run(".", argv, transport=fake)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


class TestFileCli:
    def test_file_json_ok(self, capsys):
        fake = FakeGitHub()
        code, out, err = _run(
            ["file", "--repo", REPO, "--title", "Do X", "--body", "why", "--json"], fake, capsys
        )
        assert code == 0
        payload = json.loads(out)  # ERR-2: stdout parses as JSON, nothing else
        assert payload["status"] == "ok"
        assert payload["data"]["id"] == "octo/repo#1"

    def test_file_human_mode_prints_id(self, capsys):
        fake = FakeGitHub()
        code, out, err = _run(
            ["file", "--repo", REPO, "--title", "Do X", "--body", "why"], fake, capsys
        )
        assert code == 0
        assert "octo/repo#1" in out

    def test_key_equals_value_flag_form(self, capsys):
        fake = FakeGitHub()
        code, out, err = _run(
            ["file", "--repo=" + REPO, "--title=T", "--body=B", "--json"], fake, capsys
        )
        assert code == 0
        assert json.loads(out)["data"]["title"] == "T"

    def test_lint_findings_go_to_stderr_never_block(self, capsys):
        # A terse, kind-less item lints — findings print to stderr as `lint: …`,
        # stdout stays clean, and the exit code is still 0 (WARN-only, never blocks).
        fake = FakeGitHub()
        code, out, err = _run(["file", "--repo", REPO, "--title", "fix", "--body", "b"], fake, capsys)
        assert code == 0
        assert "lint:" in err
        assert "no kind:" in err  # a specific §4 finding surfaced
        assert "lint:" not in out  # stdout carries no lint narration

    def test_lint_findings_ride_inside_json_envelope(self, capsys):
        fake = FakeGitHub()
        code, out, err = _run(
            ["file", "--repo", REPO, "--title", "fix", "--body", "b", "--json"], fake, capsys
        )
        payload = json.loads(out)  # stdout is a single JSON document
        assert payload["status"] == "ok"
        assert any(f["rule"] == "no-kind" for f in payload["lint"])


class TestOutputDiscipline:
    """ERR-2 — warnings ride inside the JSON envelope; human warnings go to stderr."""

    def test_json_warning_is_inside_envelope_not_loose_on_stdout(self, capsys):
        fake = FakeGitHub()
        code, out, err = _run(
            ["file", "--repo", REPO, "--title", "T", "--body", "B", "--stage", "weird", "--json"],
            fake,
            capsys,
        )
        payload = json.loads(out)  # stdout is still pure JSON (a single document)
        assert payload["warnings"]  # the advisory rides inside the envelope
        # ...and no *loose* human narration line ("warning: ...") leaked to stdout.
        assert not any(line.startswith("warning:") for line in out.splitlines())

    def test_human_warning_goes_to_stderr_not_stdout(self, capsys):
        fake = FakeGitHub()
        code, out, err = _run(
            ["file", "--repo", REPO, "--title", "T", "--body", "B", "--stage", "weird"],
            fake,
            capsys,
        )
        assert "weird" in err  # warning narration on stderr
        assert "warning" not in out.lower()  # stdout stays clean


class TestExitClasses:
    """ERR-1 — each error code maps to a stable non-zero exit class."""

    def test_missing_repo_is_validation_exit_2(self, capsys):
        code, out, err = _run(["file", "--title", "T", "--body", "B"], FakeGitHub(), capsys)
        assert code == 2

    def test_missing_body_flag_is_validation_exit_2(self, capsys):
        # Only title+body are required to file (API §3); an omitted --body is invalid.
        code, out, err = _run(["file", "--repo", REPO, "--title", "T"], FakeGitHub(), capsys)
        assert code == 2

    def test_empty_body_value_is_allowed(self, capsys):
        code, out, err = _run(
            ["file", "--repo", REPO, "--title", "T", "--body", "", "--json"], FakeGitHub(), capsys
        )
        assert code == 0

    def test_unknown_op_is_validation_exit_2(self, capsys):
        code, out, err = _run(["frobnicate"], FakeGitHub(), capsys)
        assert code == 2

    def test_get_missing_id_is_validation_exit_2(self, capsys):
        code, out, err = _run(["get"], FakeGitHub(), capsys)
        assert code == 2

    def test_not_found_is_exit_3(self, capsys):
        code, out, err = _run(["get", "octo/repo#999"], FakeGitHub(), capsys)
        assert code == 3

    def test_auth_is_exit_5(self, capsys):
        class AuthFail(FakeGitHub):
            def get_issue(self, *a, **k):
                raise TransportError("auth", "auth required")

        code, out, err = _run(["get", "octo/repo#1"], AuthFail(), capsys)
        assert code == 5

    def test_unavailable_is_exit_6(self, capsys):
        class Down(FakeGitHub):
            def get_issue(self, *a, **k):
                raise TransportError("unavailable", "down")

        code, out, err = _run(["get", "octo/repo#1"], Down(), capsys)
        assert code == 6


class TestGetAndProvisionCli:
    def test_file_then_get_round_trip(self, capsys):
        fake = FakeGitHub()
        _run(["file", "--repo", REPO, "--title", "RT", "--body", "b", "--json"], fake, capsys)
        code, out, err = _run(["get", "octo/repo#1", "--json"], fake, capsys)
        assert code == 0
        assert json.loads(out)["data"]["title"] == "RT"

    def test_provision_cli(self, capsys):
        fake = FakeGitHub()
        code, out, err = _run(["provision", "--repo", REPO, "--json"], fake, capsys)
        assert code == 0
        assert "stage:ready" in json.loads(out)["data"]["created"]


class TestNonInteractive:
    """INV-2 — the runner never reads stdin (nothing to hang on)."""

    def test_never_reads_stdin(self, capsys, monkeypatch):
        class Exploding(io.StringIO):
            def read(self, *a, **k):
                raise AssertionError("CLI read stdin — must be non-interactive")

            def readline(self, *a, **k):
                raise AssertionError("CLI read stdin — must be non-interactive")

        monkeypatch.setattr(sys, "stdin", Exploding())
        code, out, err = _run(
            ["file", "--repo", REPO, "--title", "T", "--body", "B", "--json"],
            FakeGitHub(),
            capsys,
        )
        assert code == 0


class TestBoundaryGuard:
    """SEC-1 hardening — an unforeseen exception becomes a clean, token-free envelope."""

    def test_unexpected_exception_is_scrubbed_and_enveloped(self, capsys):
        class Exploding(FakeGitHub):
            def get_issue(self, *a, **k):
                # A non-TransportError, non-OSError escape carrying a token.
                raise ValueError("boom leaked ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345")

        code, out, err = _run(["get", "octo/repo#1", "--json"], Exploding(), capsys)
        assert code == 6  # unavailable
        payload = json.loads(out)  # stdout is still a clean JSON envelope
        assert payload["status"] == "error"
        assert "ghp_" not in out  # no token on stdout
        assert "ghp_" not in err  # scrubbed on stderr too
        assert "[REDACTED]" in err  # surfaced (not swallowed), but redacted


def _file(fake, capsys, **flags):
    """File one item through the CLI and return its id (JSON path)."""
    argv = ["file", "--repo", REPO, "--title", "t", "--body", "b", "--json"]
    for key, value in flags.items():
        argv += [f"--{key}", value]
    code, out, _ = _run(argv, fake, capsys)
    assert code == 0
    return json.loads(out)["data"]["id"]


class TestStatusCli:
    def test_status_transition_json(self, capsys):
        fake = FakeGitHub()
        item_id = _file(fake, capsys)
        code, out, err = _run(["status", item_id, "--to", "in-progress", "--json"], fake, capsys)
        assert code == 0
        payload = json.loads(out)  # ERR-2: pure JSON on stdout
        assert payload["data"]["status"] == "in-progress"

    def test_status_requires_target(self, capsys):
        fake = FakeGitHub()
        item_id = _file(fake, capsys)
        code, out, err = _run(["status", item_id, "--json"], fake, capsys)
        assert code == 2  # validation exit class
        assert json.loads(out)["error"]["code"] == "validation"

    def test_status_unknown_target_is_validation_exit(self, capsys):
        fake = FakeGitHub()
        item_id = _file(fake, capsys)
        code, out, err = _run(["status", item_id, "--to", "frozen", "--json"], fake, capsys)
        assert code == 2

    def test_status_requires_id(self, capsys):
        fake = FakeGitHub()
        code, out, err = _run(["status", "--to", "shipped", "--json"], fake, capsys)
        assert code == 2


class TestUpdateCli:
    def test_update_title_json(self, capsys):
        fake = FakeGitHub()
        item_id = _file(fake, capsys)
        code, out, err = _run(["update", item_id, "--title", "renamed", "--json"], fake, capsys)
        assert code == 0
        assert json.loads(out)["data"]["title"] == "renamed"

    def test_update_hyphenated_if_updated_at_flag_parses(self, capsys):
        # The --if-updated-at flag (hyphen in the name) parses and drives the CAS.
        fake = FakeGitHub()
        item_id = _file(fake, capsys)
        code, out, err = _run(
            ["update", item_id, "--title", "x", "--if-updated-at", "1999-01-01T00:00:00Z", "--json"],
            fake, capsys,
        )
        assert code == 4  # conflict exit class (stale)
        assert json.loads(out)["error"]["code"] == "conflict"

    def test_update_no_fields_is_validation(self, capsys):
        fake = FakeGitHub()
        item_id = _file(fake, capsys)
        code, out, err = _run(["update", item_id, "--json"], fake, capsys)
        assert code == 2


class TestCommentCli:
    def test_comment_json(self, capsys):
        fake = FakeGitHub()
        item_id = _file(fake, capsys)
        code, out, err = _run(["comment", item_id, "--body", "a note", "--json"], fake, capsys)
        assert code == 0
        assert json.loads(out)["data"]["actor"] == "octocat"

    def test_comment_human_mode(self, capsys):
        fake = FakeGitHub()
        item_id = _file(fake, capsys)
        code, out, err = _run(["comment", item_id, "--body", "hi"], fake, capsys)
        assert code == 0
        assert "commented on" in out

    def test_comment_requires_body(self, capsys):
        fake = FakeGitHub()
        item_id = _file(fake, capsys)
        code, out, err = _run(["comment", item_id, "--json"], fake, capsys)
        assert code == 2
