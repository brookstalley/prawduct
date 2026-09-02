"""Tests for lib/backlog/cli.py — the CLI front, driven with the L1 fake.

Covers ERR-2 (JSON is the sole stdout content; diagnostics to stderr), ERR-1 (each
error code → a stable non-zero exit class), the file/get/provision happy paths
through the runner, and INV-2 (non-interactive — never reads stdin).
"""

from __future__ import annotations

import ast
import io
import json
import re
import subprocess
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
# The plugin lives in plugin/, not at the repo root — `lib.backlog` imports and the
# source reads below both resolve against it.
_REPO_ROOT = _TESTS_DIR.parent / "plugin"
for _p in (str(_REPO_ROOT), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest  # noqa: E402

from lib.backlog import cache, cli, core  # noqa: E402
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
            ["file", "--repo", REPO, "--title", "cli: the Do X item under test", "--body", "why", "--json"], fake, capsys
        )
        assert code == 0
        payload = json.loads(out)  # ERR-2: stdout parses as JSON, nothing else
        assert payload["status"] == "ok"
        assert payload["data"]["id"] == "octo/repo#1"

    def test_file_human_mode_prints_id(self, capsys):
        fake = FakeGitHub()
        code, out, err = _run(
            ["file", "--repo", REPO, "--title", "cli: the Do X item under test", "--body", "why"], fake, capsys
        )
        assert code == 0
        assert "octo/repo#1" in out

    def test_key_equals_value_flag_form(self, capsys):
        fake = FakeGitHub()
        code, out, err = _run(
            ["file", "--repo=" + REPO, "--title=cli: the T item under test", "--body=B", "--json"], fake, capsys
        )
        assert code == 0
        assert json.loads(out)["data"]["title"] == "cli: the T item under test"

    def test_lint_findings_go_to_stderr_never_block(self, capsys):
        # A terse, kind-less item lints — findings print to stderr as `lint: …`,
        # stdout stays clean, and the exit code is still 0 (WARN-only, never blocks).
        fake = FakeGitHub()
        code, out, err = _run(["file", "--repo", REPO, "--title", "cli: the fix item under test", "--body", "b"], fake, capsys)
        assert code == 0
        assert "lint:" in err
        assert "no kind:" in err  # a specific §4 finding surfaced
        assert "lint:" not in out  # stdout carries no lint narration

    def test_lint_findings_ride_inside_json_envelope(self, capsys):
        fake = FakeGitHub()
        code, out, err = _run(
            ["file", "--repo", REPO, "--title", "cli: the fix item under test", "--body", "b", "--json"], fake, capsys
        )
        payload = json.loads(out)  # stdout is a single JSON document
        assert payload["status"] == "ok"
        assert any(f["rule"] == "no-kind" for f in payload["lint"])


class TestOutputDiscipline:
    """ERR-2 — warnings ride inside the JSON envelope; human warnings go to stderr."""

    def test_json_warning_is_inside_envelope_not_loose_on_stdout(self, capsys):
        fake = FakeGitHub()
        code, out, err = _run(
            ["file", "--repo", REPO, "--title", "cli: the T item under test", "--body", "B", "--stage", "weird", "--json"],
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
            ["file", "--repo", REPO, "--title", "cli: the T item under test", "--body", "B", "--stage", "weird"],
            fake,
            capsys,
        )
        assert "weird" in err  # warning narration on stderr
        assert "warning" not in out.lower()  # stdout stays clean

    def test_error_envelope_warnings_reach_stderr(self, capsys):
        # BKL-9V2W: a resumable error envelope (e.g. a mid-run import failure)
        # carries the audit warnings accrued before the cut. The human error path
        # must surface them like the ok path — else the carried audit line stays
        # invisible to the operator running the migration.
        result = {
            "status": "error",
            "error": {
                "code": "unavailable",
                "message": "backend failed",
                "details": {"resumable": True},
            },
            "warnings": ["restored missing alias label id:DIS-0001 on octo/repo#4"],
        }
        code = cli._emit(result, json_mode=False)
        err = capsys.readouterr().err
        assert code != 0
        assert "error [unavailable]" in err
        assert "restored missing alias label" in err

    def test_string_details_are_NAMED_not_counted(self, capsys):
        """The completeness gate's lists ARE the payload, unlike import's entries.

        `missing`/`unaliasable`/`collisions` are the ids that stranded the run,
        and the documented remedy — give each a real prefix in the SOURCE before
        importing — cannot be followed against the number 3. The runbook drives
        this path without `--json`, so the named form has no other route to the
        operator. Asserted at the CLI layer on purpose: the library-level test
        passes on the envelope while the human surface says `missing: 3`.
        """
        result = {
            "status": "error",
            "error": {
                "code": "conflict",
                "message": "source and target disagree",
                "details": {
                    "missing": ["ADR-0007", "ADR-0009"],
                    "unaliasable": ["a stranded title"],
                },
            },
        }
        cli._emit(result, json_mode=False)
        err = capsys.readouterr().err
        assert "missing: ADR-0007, ADR-0009" in err
        assert "unaliasable: a stranded title" in err
        assert "missing: 2" not in err

    def test_long_string_details_are_capped(self, capsys):
        result = {
            "status": "error",
            "error": {
                "code": "conflict",
                "message": "x",
                "details": {"missing": [f"ID-{n:04d}" for n in range(25)]},
            },
        }
        cli._emit(result, json_mode=False)
        err = capsys.readouterr().err
        assert "ID-0000" in err and "ID-0019" in err
        assert "(+5 more)" in err
        assert "ID-0024" not in err, "the cap must actually bound the output"

    def test_error_envelope_details_reach_stderr_as_counts(self, capsys):
        # The sibling of the warnings case above. A cut mid-import carries how far
        # it got, and human mode printed none of it — so the operator of an
        # irreversible ~900-issue migration learned only that it broke, on the very
        # path the scrub runbook drives (Step 4 invokes import WITHOUT --json).
        # Counts, not the raw entry lists: the dicts are the wrong thing to show
        # someone deciding whether to resume.
        result = {
            "status": "error",
            "error": {
                "code": "unavailable",
                "message": "backend failed",
                "details": {
                    "created": [{"key": "a"}, {"key": "b"}, {"key": "c"}],
                    "skipped": [{"key": "d"}],
                    "collisions": [],
                    "resumable": True,
                    "pacing": {"rest_points_charged": 812},
                },
            },
        }
        cli._emit(result, json_mode=False)
        err = capsys.readouterr().err
        assert "created: 3" in err and "skipped: 1" in err and "collisions: 0" in err
        assert "resumable: True" in err
        assert "key" not in err, "entry dicts must not be dumped into the operator's face"
        # The floor marker matters MORE here than on the ok path, not less: the
        # meter charges per transport method call, so the figure is a floor
        # (BKL-3H7W), and a cut is when someone sizes the rest of an irreversible
        # run off it. A bare 812 reads exact. Pinned because the first version of
        # this fix printed the raw dict and lost the marker.
        assert "pacing: ≥812 REST points" in err
        assert "rest_points_charged" not in err, "the raw pacing dict must not leak"

    def test_cut_path_pacing_reports_the_throttle_breakdown(self, capsys):
        # The other half of what R-1 said the cut path lacked. This branch renders
        # only on a run that actually hit a budget — which is the run whose
        # operator is deciding whether to resume, so it is the one that matters
        # most and was the one with no coverage in the tree.
        result = {
            "status": "error",
            "error": {
                "code": "unavailable",
                "message": "backend failed",
                "details": {
                    "pacing": {
                        "rest_points_charged": 812,
                        "rest_point_waits": 2,
                        "rest_point_wait_seconds": 9.4,
                        "content_creation_waits": 1,
                        "content_creation_wait_seconds": 30.0,
                        "rate_limit_pauses": 0,
                        "rate_limit_paused_seconds": 0.0,
                    }
                },
            },
        }
        cli._emit(result, json_mode=False)
        err = capsys.readouterr().err
        assert "≥812 REST points" in err, "the floor marker survives the throttled branch too"
        assert "THROTTLED 3× for 39s total" in err
        assert "(2 rest-point, 1 content-cap, 0 rate-limit)" in err


class TestExitClasses:
    """ERR-1 — each error code maps to a stable non-zero exit class."""

    def test_missing_repo_is_validation_exit_2(self, capsys):
        code, out, err = _run(["file", "--title", "cli: the T item under test", "--body", "B"], FakeGitHub(), capsys)
        assert code == 2

    def test_missing_body_flag_is_validation_exit_2(self, capsys):
        # Only title+body are required to file (API §3); an omitted --body is invalid.
        code, out, err = _run(["file", "--repo", REPO, "--title", "cli: the T item under test"], FakeGitHub(), capsys)
        assert code == 2

    def test_empty_body_value_is_allowed(self, capsys):
        code, out, err = _run(
            ["file", "--repo", REPO, "--title", "cli: the T item under test", "--body", "", "--json"], FakeGitHub(), capsys
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
        _run(["file", "--repo", REPO, "--title", "cli: the RT item under test", "--body", "b", "--json"], fake, capsys)
        code, out, err = _run(["get", "octo/repo#1", "--json"], fake, capsys)
        assert code == 0
        assert json.loads(out)["data"]["title"] == "cli: the RT item under test"

    def test_provision_cli(self, capsys):
        fake = FakeGitHub()
        code, out, err = _run(["provision", "--repo", REPO, "--json"], fake, capsys)
        assert code == 0
        assert "stage:ready" in json.loads(out)["data"]["created"]

    def test_get_json_carries_the_comment_thread(self, capsys):
        fake = FakeGitHub()
        _run(["file", "--repo", REPO, "--title", "cli: the thread item under test", "--body", "b", "--json"], fake, capsys)
        _run(["comment", "octo/repo#1", "--body", "scope narrowed — CLI only", "--json"], fake, capsys)
        code, out, err = _run(["get", "octo/repo#1", "--json"], fake, capsys)
        assert code == 0
        data = json.loads(out)["data"]
        assert data["comments_count"] == 1
        assert data["comments"][0]["body"] == "scope narrowed — CLI only"
        assert data["comments"][0]["author"] == "octocat"

    def test_get_human_mode_renders_the_thread(self, capsys):
        fake = FakeGitHub()
        _run(["file", "--repo", REPO, "--title", "cli: the thread item under test", "--body", "b", "--json"], fake, capsys)
        _run(["comment", "octo/repo#1", "--body", "see the fix in #99", "--json"], fake, capsys)
        code, out, err = _run(["get", "octo/repo#1"], fake, capsys)
        assert code == 0
        assert "1 comment(s):" in out
        assert "octocat" in out
        assert "see the fix in #99" in out


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
            ["file", "--repo", REPO, "--title", "cli: the T item under test", "--body", "B", "--json"],
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
    argv = ["file", "--repo", REPO, "--title", "cli: the t item under test", "--body", "b", "--json"]
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
        code, out, err = _run(["update", item_id, "--title", "cli: the renamed item under test", "--json"], fake, capsys)
        assert code == 0
        assert json.loads(out)["data"]["title"] == "cli: the renamed item under test"

    def test_update_hyphenated_if_updated_at_flag_parses(self, capsys):
        # The --if-updated-at flag (hyphen in the name) parses and drives the CAS.
        fake = FakeGitHub()
        item_id = _file(fake, capsys)
        code, out, err = _run(
            ["update", item_id, "--title", "cli: the x item under test", "--if-updated-at", "1999-01-01T00:00:00Z", "--json"],
            fake, capsys,
        )
        assert code == 4  # conflict exit class (stale)
        assert json.loads(out)["error"]["code"] == "conflict"

    def test_update_no_fields_is_validation(self, capsys):
        fake = FakeGitHub()
        item_id = _file(fake, capsys)
        code, out, err = _run(["update", item_id, "--json"], fake, capsys)
        assert code == 2


class TestNewFieldFlagsCli:
    """The CLI half of `affected` / `tags` / `working-branch`.

    `--tags` (plural) sets the whole set on `update`; `--tag` (singular) filters
    on `list`. Two spellings for two verbs, which is worth a test precisely
    because they look like a typo for each other.
    """

    def test_update_tags_affected_and_working_branch_in_one_call(self, capsys):
        fake = FakeGitHub()
        item_id = _file(fake, capsys)
        fake.push_branch("octo", "repo", "feat/live")

        code, out, _err = _run(
            [
                "update", item_id,
                "--tags", "perf,api",
                "--affected", "plugin/lib",
                "--working-branch", "octo/repo@feat/live",
                "--json",
            ],
            fake, capsys,
        )

        assert code == 0
        data = json.loads(out)["data"]
        assert data["tags"] == ["api", "perf"]
        assert data["affected"] == ["plugin/lib"]
        assert data["working_branch"] == "octo/repo@feat/live"

    def test_an_unpushed_working_branch_exits_validation(self, capsys):
        fake = FakeGitHub()
        item_id = _file(fake, capsys)

        code, out, _err = _run(
            ["update", item_id, "--working-branch", "octo/repo@feat/ghost", "--json"],
            fake, capsys,
        )

        assert code == 2
        assert json.loads(out)["error"]["code"] == "validation"

    def test_list_filters_on_one_tag(self, capsys):
        fake = FakeGitHub()
        item_id = _file(fake, capsys)
        _run(["update", item_id, "--tags", "perf", "--json"], fake, capsys)
        _file(fake, capsys)

        code, out, _err = _run(["list", "--repo", REPO, "--tag", "perf", "--json"], fake, capsys)

        assert code == 0
        assert [i["id"] for i in json.loads(out)["data"]["items"]] == [item_id]

    def test_the_human_view_shows_a_populated_working_branch(self, capsys):
        """Visibility is the field's only job — a claim the default view omits is
        the invisible claim it exists to prevent."""
        fake = FakeGitHub()
        item_id = _file(fake, capsys)
        fake.push_branch("octo", "repo", "feat/live")
        _run(["update", item_id, "--working-branch", "octo/repo@feat/live", "--json"], fake, capsys)

        _code, out, _err = _run(["get", item_id], fake, capsys)

        assert "working-branch=octo/repo@feat/live" in out

    def test_an_unset_working_branch_adds_no_noise(self, capsys):
        fake = FakeGitHub()
        item_id = _file(fake, capsys)

        _code, out, _err = _run(["get", item_id], fake, capsys)

        assert "working-branch" not in out

    def test_the_help_names_all_three_new_flags(self):
        for flag in ("--tags", "--affected", "--working-branch", "--tag T"):
            assert flag in cli._HELP, flag
class TestBlockFieldFlagsCli:
    """The block-field flags reach `core` through the front (#550).

    `core` is covered directly in test_backlog_core.py; what these pin is the
    wiring — that each flag is *parsed* rather than rejected as unknown, since a
    flag missing from the `valued`/`boolean` sets is exactly how these writes were
    unreachable in the first place.
    """

    def _body_of(self, fake, item_id):
        owner_repo, number = item_id.split("#")
        owner, repo = owner_repo.split("/")
        return fake.get_issue(owner, repo, int(number))["body"]

    @pytest.mark.parametrize("flag,value", [
        ("--refs", "documentation/x.md"),
        ("--revisit", "2027-01-01"),
        ("--closed-by", "fix/some-branch"),
    ])
    def test_each_valued_block_flag_parses_and_writes(self, capsys, flag, value):
        fake = FakeGitHub()
        item_id = _file(fake, capsys)
        code, out, err = _run(["update", item_id, flag, value, "--json"], fake, capsys)
        assert code == 0
        assert f"{flag[2:]}: {value}" in self._body_of(fake, item_id)

    def test_file_refs_flag_parses(self, capsys):
        fake = FakeGitHub()
        code, out, err = _run(
            ["file", "--repo", REPO, "--title", "cli: the refs item under test", "--body", "b",
             "--refs", "documentation/x.md", "--json"],
            fake, capsys,
        )
        assert code == 0
        assert "refs: documentation/x.md" in self._body_of(fake, json.loads(out)["data"]["id"])


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


class TestHelpAdvertisesHonoredFlags:
    """Every op that *honors* ``--archive-scope`` must also *advertise* it (MG4b).

    MG4 makes archive scope "an explicit owner-confirmed choice surfaced at scrub
    time, not a silent default." A flag the parser accepts but ``--help`` never
    names is silent by construction: the operator cannot choose what they cannot
    see. Both ops shipped honoring the flag while neither listed it.

    Derived, not hardcoded — the honoring set is read off the source (which
    handlers resolve the selector) and mapped through the dispatch chain, so a
    third op that starts honoring it inherits the assertion instead of quietly
    reopening the gap.
    """

    @staticmethod
    def _honoring_handlers_and_dispatch() -> tuple[set[str], dict[str, str], set[str]]:
        src = (_REPO_ROOT / "lib" / "backlog" / "cli.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        honoring = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and any(
                isinstance(inner, ast.Call)
                and getattr(inner.func, "id", None) == "_archive_scope_flag"
                for inner in ast.walk(node)
            )
        }
        # Ops mapped by the single-literal dispatch shape this derivation understands.
        mapped = dict(re.findall(r'op == "([\w-]+)":\s*\n\s*result = (_run_\w+)\(', src))
        # EVERY dispatched handler, whatever the match shape (`op in ("a","b")` included).
        dispatched = set(re.findall(r"result = (_run_\w+)\(", src))
        return honoring, mapped, dispatched

    def test_no_honoring_handler_escapes_the_derivation(self):
        """The orphan check: a handler that honors the flag but is dispatched in a
        shape the op-mapping regex cannot read would be silently dropped from the
        reviewed set, leaving the suite green while covering fewer ops.

        `cli.py` already dispatches two ops as `op in ("get","show")` /
        `op in ("link","unlink")`, so this is a live shape, not a hypothetical.
        Fail loudly and demand the derivation be extended rather than degrade.
        """
        honoring, mapped, dispatched = self._honoring_handlers_and_dispatch()
        unreachable = (honoring & dispatched) - set(mapped.values())
        assert not unreachable, (
            f"{sorted(unreachable)} honor --archive-scope but are dispatched in a "
            "shape `_honoring_handlers_and_dispatch` cannot map to an op name; "
            "extend that helper's `mapped` regex or these ops go unchecked"
        )

    @classmethod
    def _ops_honoring_archive_scope(cls) -> set[str]:
        # Delegates rather than re-deriving: a second copy would drift from the
        # one the orphan check reads, so widening the derivation to fix a real
        # gap could fail the orphan check against the un-widened twin.
        honoring, mapped, _dispatched = cls._honoring_handlers_and_dispatch()
        return {op for op, handler in mapped.items() if handler in honoring}

    def test_the_honoring_set_is_non_empty(self):
        # Guards the derivation itself: if the introspection silently matched
        # nothing, every assertion below would vacuously pass.
        assert self._ops_honoring_archive_scope() >= {"import", "restructure-preview"}

    def test_every_honoring_op_advertises_the_flag(self):
        help_lines = cli._HELP.splitlines()
        for op in sorted(self._ops_honoring_archive_scope()):
            line = next((ln for ln in help_lines if ln.startswith(f"  {op} ")), None)
            assert line is not None, f"{op} honors --archive-scope but has no help entry"
            assert "--archive-scope" in line, (
                f"`{op}` accepts --archive-scope but does not advertise it; an "
                "owner cannot make an explicit choice they cannot discover (MG4b)"
            )


class TestSyncCli:
    """The cache's writer has to be reachable from the CLI, because three
    ``unavailable`` messages in ``cache.py``/``cachequery.py`` already tell the
    operator to run exactly this op. A cache with no reachable writer is a cache
    that can only ever report being empty."""

    def test_sync_is_a_known_op_and_fills_the_store(self, tmp_path, capsys):
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        fake = FakeGitHub()
        core.file_item(
            fake, owner="octo", repo="repo",
            title="cli: the sync item under test", body="b", facets={},
        )

        code = cli.run(str(tmp_path), ["sync", "--repo", REPO, "--json"], transport=fake)
        out = capsys.readouterr().out

        assert code == 0, out
        payload = json.loads(out)
        assert payload["status"] == "ok"
        assert payload["data"]["written"] == 1

    def _health(self, project_dir):
        """``(last_attempt_at, last_error)`` straight from the store."""
        conn = cache.open_store(project_dir, create=False)
        assert not isinstance(conn, dict), conn
        try:
            return cache.sync_health(conn, REPO)
        finally:
            conn.close()

    def test_a_failing_sync_records_itself_on_a_warmed_scope(self, tmp_path, capsys):
        """The wiring half of #625: a sync that fails must stamp the attempt, not
        just return the envelope. The session-start warm is detached with its
        stderr discarded, so a sync that records nothing leaves no trace at all.

        **The transport is broken the way a revoked credential breaks it** — by
        raising a real `TransportError`, which `sync` catches and converts to an
        error ENVELOPE. An earlier version of this test raised `TransportError`
        with one argument; its `__init__` takes two, so what actually escaped was
        a `TypeError`, the test drove the exception path instead, and the envelope
        branch it was written to cover had no coverage at all while passing.
        """
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        fake = FakeGitHub()
        core.file_item(
            fake, owner="octo", repo="repo",
            title="cli: the sync item under test", body="b", facets={},
        )
        cli.run(str(tmp_path), ["sync", "--repo", REPO, "--json"], transport=fake)  # warm it
        capsys.readouterr()

        class AuthFail(FakeGitHub):
            def list_issues(self, *a, **k):
                raise TransportError("auth", "auth required")

        cli.run(str(tmp_path), ["sync", "--repo", REPO, "--rebuild", "--json"], transport=AuthFail())
        out = capsys.readouterr().out
        assert json.loads(out)["status"] == "error", out  # the envelope path, not the raise

        attempted_at, last_error = self._health(tmp_path)
        assert last_error, "a failing sync left no record on a warmed scope"
        assert "TypeError" not in last_error, f"drove the exception path, not the envelope: {last_error}"
        assert "auth" in last_error, last_error
        assert attempted_at

    def test_a_recovering_sync_clears_the_record_through_the_cli(self, tmp_path, capsys):
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        fake = FakeGitHub()
        core.file_item(
            fake, owner="octo", repo="repo",
            title="cli: the sync item under test", body="b", facets={},
        )
        cli.run(str(tmp_path), ["sync", "--repo", REPO, "--json"], transport=fake)

        class AuthFail(FakeGitHub):
            def list_issues(self, *a, **k):
                raise TransportError("auth", "auth required")

        cli.run(str(tmp_path), ["sync", "--repo", REPO, "--rebuild", "--json"], transport=AuthFail())
        cli.run(str(tmp_path), ["sync", "--repo", REPO, "--json"], transport=fake)  # recovered
        capsys.readouterr()

        assert self._health(tmp_path)[1] is None, "a recovered sync left a stale failure behind"

    def test_an_unexpected_exception_is_recorded_before_it_propagates(self, tmp_path, capsys):
        # The other exit. `TransportError` becomes an envelope (above); an
        # UNEXPECTED exception reaches the CLI boundary handler instead, and that
        # is exactly when a record is most wanted. Distinct from the envelope test
        # on purpose — conflating them is what let the arity bug hide.
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        fake = FakeGitHub()
        core.file_item(
            fake, owner="octo", repo="repo",
            title="cli: the sync item under test", body="b", facets={},
        )
        cli.run(str(tmp_path), ["sync", "--repo", REPO, "--json"], transport=fake)
        capsys.readouterr()

        class Exploding(FakeGitHub):
            def list_issues(self, *a, **k):
                raise RuntimeError("something nobody anticipated")

        cli.run(str(tmp_path), ["sync", "--repo", REPO, "--rebuild", "--json"], transport=Exploding())
        capsys.readouterr()

        _attempted_at, last_error = self._health(tmp_path)
        assert last_error, "an unexpected exception left no record"
        assert "RuntimeError" in last_error, last_error

    def test_every_sync_caller_stamps_the_health_beside_the_coverage(self, tmp_path, capsys):
        """R-6: the health stamps must move wherever the coverage stamp moves.

        `confirm_coverage` lives inside `sync`, so every caller advances it. While
        the health stamps were written by `_run_sync` alone, `pick`'s revalidating
        sync and the post-import warm advanced the coverage stamp WITHOUT clearing
        the failure beside it — so a stale `SYNC FAILING` banner outlived the sync
        that fixed it and printed under a newer `synced_at`.
        """
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        fake = FakeGitHub()
        core.file_item(
            fake, owner="octo", repo="repo",
            title="cli: the sync item under test", body="b", facets={},
        )
        cli.run(str(tmp_path), ["sync", "--repo", REPO, "--json"], transport=fake)

        class AuthFail(FakeGitHub):
            def list_issues(self, *a, **k):
                raise TransportError("auth", "auth required")

        cli.run(str(tmp_path), ["sync", "--repo", REPO, "--rebuild", "--json"], transport=AuthFail())
        capsys.readouterr()

        # Pin the precondition. Without it this test passes when NOTHING records
        # at all — "cleared correctly" and "never written" look identical at the
        # end state, which is the same vacuity that hid the `TransportError`
        # arity bug in the test above.
        assert self._health(tmp_path)[1], "setup did not record a failure to clear"

        # A caller that is NOT `sync`: `pick` revalidates through the same path.
        cli.run(str(tmp_path), ["pick", "--repo", REPO, "--json"], transport=fake)
        capsys.readouterr()

        assert self._health(tmp_path)[1] is None, (
            "a successful sync through `pick` advanced the coverage stamp but left "
            "the failure beside it — the two must move together"
        )

    def test_the_error_strings_that_name_this_op_now_name_a_real_one(self):
        """`cache.py` and `cachequery.py` tell the operator to run
        `prawduct-hook backlog sync`. That string is only useful if the op
        exists — this pins the two together so neither drifts alone."""
        assert "sync" in cli._ALL_OPS

    def test_rebuild_forces_the_full_scan(self, tmp_path, capsys):
        subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        fake = FakeGitHub()
        core.file_item(
            fake, owner="octo", repo="repo",
            title="cli: the rebuild item under test", body="b", facets={},
        )
        cli.run(str(tmp_path), ["sync", "--repo", REPO, "--json"], transport=fake)
        capsys.readouterr()

        cli.run(str(tmp_path), ["sync", "--repo", REPO, "--rebuild", "--json"], transport=fake)
        payload = json.loads(capsys.readouterr().out)

        assert payload["data"]["rebuilt"] is True

    def test_sync_without_a_repo_is_a_validation_error(self, capsys):
        fake = FakeGitHub()
        code, _out, _err = _run(["sync"], fake, capsys)

        assert code == 2
class TestUpdateRefusesAStrayPositional:
    """`update` must not silently ignore a second positional (#550, cumulative R-15).

    The arrival that matters is `update <id> status=shipped` — the markdown
    spelling still instructed by `skills/pr` and the Critic's review-cycle. It
    parsed as a stray positional `_run_update` dropped: exit 0, nothing written,
    no diagnostic. A wrong result with a success code is worse than any error,
    because nothing prompts the caller to look.
    """

    def test_a_field_value_positional_is_rejected(self, capsys):
        fake = FakeGitHub()
        item_id = _file(fake, capsys)
        code, out, err = _run(
            ["update", item_id, "status=shipped", "--json"], fake, capsys
        )
        assert code == 2
        assert "named flags" in json.loads(out)["error"]["message"]

    def test_the_stray_argument_writes_nothing(self, capsys):
        # The exit code is not the property that matters — that nothing was
        # written is.
        fake = FakeGitHub()
        item_id = _file(fake, capsys)
        owner_repo, number = item_id.split("#")
        owner, repo = owner_repo.split("/")
        before = fake.get_issue(owner, repo, int(number))["body"]
        _run(["update", item_id, "status=shipped", "--json"], fake, capsys)
        assert fake.get_issue(owner, repo, int(number))["body"] == before

    def test_the_single_positional_form_still_works(self, capsys):
        fake = FakeGitHub()
        item_id = _file(fake, capsys)
        code, _, _ = _run(["update", item_id, "--refs", "docs/x.md", "--json"], fake, capsys)
        assert code == 0


class TestListHumanModeSurfacesTruncation:
    """A truncated page must not read as the complete set (#549).

    `list_items` computes `has_more` correctly and `--json` receives it; the
    human formatter dropped it, so `99 item(s)` + exit 0 was indistinguishable
    from a backlog of 99 when it held 160 — and every count derived from that
    page was wrong while looking well-formed. A `--json`-only test cannot see
    this: the defect lives one layer above the data the JSON tests read.
    """

    def _seeded(self, capsys, how_many):
        fake = FakeGitHub()
        for n in range(how_many):
            _run(
                ["file", "--repo", REPO, "--title", f"cli: the page item {n} under test",
                 "--body", "b", "--json"],
                fake, capsys,
            )
        return fake

    def test_a_truncated_page_says_so_and_names_the_remedy(self, capsys):
        fake = self._seeded(capsys, 3)

        code, out, _err = _run(
            ["list", "--repo", REPO, "--per-page", "3", "--page", "1"], fake, capsys
        )

        assert code == 0
        assert "3 item(s)" in out
        assert "MORE AVAILABLE" in out
        assert "--page 2" in out, "the signal names no way to see the rest"

    def test_a_complete_result_stays_silent(self, capsys):
        # The signal has to be by exception, or it stops meaning anything.
        fake = self._seeded(capsys, 2)

        code, out, _err = _run(
            ["list", "--repo", REPO, "--per-page", "10", "--page", "1"], fake, capsys
        )

        assert code == 0
        assert "2 item(s)" in out
        assert "MORE AVAILABLE" not in out

    def test_the_human_signal_agrees_with_the_json_envelope(self, capsys):
        """The two views must not disagree — the whole defect was one honest
        surface and one silent one over the same fact."""
        fake = self._seeded(capsys, 3)
        argv = ["list", "--repo", REPO, "--per-page", "3", "--page", "1"]

        _code, human, _ = _run(argv, fake, capsys)
        _code, envelope, _ = _run([*argv, "--json"], fake, capsys)

        assert json.loads(envelope)["data"]["has_more"] is ("MORE AVAILABLE" in human)
