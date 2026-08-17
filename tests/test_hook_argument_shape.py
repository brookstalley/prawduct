"""`prawduct-hook`'s pre-dispatch argument guard, and `update-gitignore --dry-run`.

A fleet report triggered a live `.gitignore` rewrite by typing
`prawduct-hook update-gitignore --help`. The flag was not *rejected* and it was
not *parsed* — `cmd_update_gitignore` took no `argv` parameter at all, so the
dispatcher dropped the token on the floor and ran the repair. Nothing in the
naming separated that command from `coverage-scaffold`, its sibling on the same
`/prawduct:doctor` flow, which does take `argv` and is `--apply`-gated: the
asymmetry lived in the signatures, where no caller can see it.

The fix is at the dispatcher, because a command that never receives `argv` has
nowhere to put a check of its own — the same reasoning `_check_binary_skew` and
`_check_ephemeral_worktree` already carry in that function. Which makes
`test_the_collections_match_the_dispatch_chain` the load-bearing test in this
file: it derives the argument shape of every subcommand from `_dispatch`'s own
source, so a subcommand added later without an entry fails here rather than
silently re-opening the hole for whichever command nobody thought of.

The second half is the surprise that made the first half worth having:
`update-gitignore` now has the `--dry-run` its siblings taught callers to
expect. It stays **mutating by default** — doctor calls it to repair, and
inverting that would quietly stop fixing the repos that need fixing.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import inspect
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = _ROOT / "bin" / "prawduct-hook"

# The script has a shebang and no `.py` extension; SourceFileLoader is how the
# rest of the suite reaches its internals. The module name is not "__main__",
# so importing does not dispatch.
_hook_loader = importlib.machinery.SourceFileLoader(
    "prawduct_hook_argument_shape", str(HOOK)
)
_hook_spec = importlib.util.spec_from_loader("prawduct_hook_argument_shape", _hook_loader)
_hook = importlib.util.module_from_spec(_hook_spec)
_hook_loader.exec_module(_hook)


def _run(repo: Path, argv: list[str]) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["CLAUDE_PROJECT_DIR"] = str(repo)
    return subprocess.run(
        [sys.executable, str(HOOK), *argv],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


# --- The structural pin ------------------------------------------------------


def _dispatch_branches() -> dict[str, str]:
    """Every `command == "..."` branch in `_dispatch`, mapped to its body.

    Read from the dispatcher's own source rather than from a second list, so
    the guard's collections cannot drift away from the thing they describe.
    """
    branches: dict[str, list[str]] = {}
    current: str | None = None
    for line in inspect.getsource(_hook._dispatch).splitlines():
        opened = re.match(r'\s*(?:el)?if command == "([A-Za-z0-9-]+)":\s*$', line)
        if opened:
            current = opened.group(1)
            branches[current] = []
            continue
        if re.match(r"\s*else:\s*$", line):
            current = None
            continue
        if current is not None:
            branches[current].append(line)
    return {name: "\n".join(body) for name, body in branches.items()}


def test_the_branch_parser_actually_found_the_chain():
    """Positive control. Every assertion below is a set comparison, and an
    empty set compares equal to an empty set — a parser that silently matched
    nothing would make the whole file vacuous."""
    branches = _dispatch_branches()
    assert len(branches) > 30, sorted(branches)
    assert "update-gitignore" in branches
    assert "sys.argv[2:]" in branches["update-gitignore"]


def test_the_collections_match_the_dispatch_chain():
    """The guard's classification IS the dispatch chain's, derived not restated.

    A branch that passes `sys.argv[2:]` hands the command its arguments and can
    refuse them itself. A branch reading `sys.argv[2]` takes one positional and
    drops the rest. A branch mentioning neither gives the command no way to see
    an argument at all — that is the population the dispatcher must speak for,
    and a new one appearing without an entry here is exactly how this defect
    would come back.
    """
    branches = _dispatch_branches()
    takes_argv = {c for c, body in branches.items() if "sys.argv[2:]" in body}
    single = {c for c, body in branches.items() if re.search(r"sys\.argv\[2\]", body)}
    no_argument = set(branches) - takes_argv - single

    assert no_argument == (
        _hook._NO_ARGUMENT_COMMANDS
        | _hook._NO_ARGUMENT_NOTE_ONLY_COMMANDS
        | _hook._NO_ARGUMENT_UNCHECKED_COMMANDS
    )
    assert single == _hook._SINGLE_POSITIONAL_COMMANDS


def test_the_three_no_argument_dispositions_are_disjoint():
    """Refuse / note-only / unchecked are answers to the same question, so a
    command in two of them would get whichever the guard tested first."""
    refuse = _hook._NO_ARGUMENT_COMMANDS
    note = _hook._NO_ARGUMENT_NOTE_ONLY_COMMANDS
    unchecked = _hook._NO_ARGUMENT_UNCHECKED_COMMANDS
    assert not refuse & note
    assert not refuse & unchecked
    assert not note & unchecked


# --- The guard's behavior ----------------------------------------------------


class TestNoArgumentCommands:
    @pytest.mark.parametrize("command", sorted(_hook._NO_ARGUMENT_COMMANDS))
    def test_an_argument_is_refused_and_named(self, command: str, capsys):
        assert _hook._check_argument_shape(command, ["--dry-run"]) == 2
        assert "--dry-run" in capsys.readouterr().err

    @pytest.mark.parametrize("command", sorted(_hook._NO_ARGUMENT_COMMANDS))
    def test_the_bare_invocation_still_passes(self, command: str):
        assert _hook._check_argument_shape(command, []) == 0

    def test_the_message_says_nothing_ran(self, capsys):
        """The caller's next question after a refusal is always "did it do it
        anyway" — a refusal that leaves that open is half a fix."""
        _hook._check_argument_shape("version", ["--help"])
        assert "nothing ran" in capsys.readouterr().err.lower()

    def test_end_to_end_a_flag_on_a_no_argument_command_exits_non_zero(
        self, tmp_path: Path
    ):
        proc = _run(tmp_path, ["version", "--help"])
        assert proc.returncode != 0
        assert "--help" in proc.stderr
        # The command did not also run: `version` prints a bare semver.
        assert proc.stdout.strip() == ""


class TestHarnessInvokedCommands:
    """`stop` and `subagent-stop` are the harness's own calls, invoked as bare
    literals by every `hooks.json` prawduct has shipped. A usage error there
    does not protect a caller — it blocks the session and feeds the refusal
    back as a turn. So the argument is named and the gate still runs."""

    @pytest.mark.parametrize("command", sorted(_hook._NO_ARGUMENT_NOTE_ONLY_COMMANDS))
    def test_a_stray_argument_is_named_but_not_fatal(self, command: str, capsys):
        assert _hook._check_argument_shape(command, ["--force"]) == 0
        err = capsys.readouterr().err
        assert "--force" in err
        assert command in err


class TestRetiredInertCommands:
    """`stamp-merged` promises exit 0 for any input so a copied release script
    keeps working (`test_deprecated_inert_commands.py`). An inert command
    cannot act on an argument it ignored, so there is no surprise to prevent."""

    @pytest.mark.parametrize("command", sorted(_hook._NO_ARGUMENT_UNCHECKED_COMMANDS))
    def test_any_argument_passes_the_guard_silently(self, command: str, capsys):
        assert _hook._check_argument_shape(command, ["--a-flag-that-never-existed"]) == 0
        assert capsys.readouterr().err == ""

    def test_end_to_end_the_deprecation_contract_survives(self, tmp_path: Path):
        proc = _run(tmp_path, ["stamp-merged", "--a-flag-that-never-existed"])
        assert proc.returncode == 0, proc.stdout + proc.stderr


class TestSinglePositionalCommands:
    @pytest.mark.parametrize("command", sorted(_hook._SINGLE_POSITIONAL_COMMANDS))
    def test_a_flag_shaped_value_is_refused(self, command: str, capsys):
        """The reported defect one step removed: the flag is not ignored, it is
        read as the id (or rationale) the command wanted."""
        assert _hook._check_argument_shape(command, ["--dry-run"]) == 2
        assert "--dry-run" in capsys.readouterr().err

    @pytest.mark.parametrize("command", sorted(_hook._SINGLE_POSITIONAL_COMMANDS))
    def test_extra_positionals_are_refused_rather_than_dropped(
        self, command: str, capsys
    ):
        assert _hook._check_argument_shape(command, ["VRF-001", "and", "more"]) == 2
        assert "'and'" in capsys.readouterr().err

    @pytest.mark.parametrize("command", sorted(_hook._SINGLE_POSITIONAL_COMMANDS))
    def test_one_value_passes(self, command: str):
        assert _hook._check_argument_shape(command, ["VRF-001"]) == 0

    def test_verify_operator_verification_refuses_a_flag_as_an_id(
        self, tmp_path: Path
    ):
        """End to end, and asserted on the queue rather than on the exit code:
        the entry must still be pending."""
        (tmp_path / ".prawduct").mkdir()
        queue = tmp_path / ".prawduct" / "operator-verification.md"
        queue.write_text(
            "# Operator Verification\n\n"
            "## VRF-001: a thing\n- Status: pending\n- Visual change: yes\n"
        )
        before = queue.read_bytes()

        proc = _run(tmp_path, ["verify-operator-verification", "--dry-run"])

        assert proc.returncode != 0
        assert "--dry-run" in proc.stderr
        assert queue.read_bytes() == before

    def test_the_command_itself_refuses_a_flag_shaped_id(self, tmp_path: Path, capsys):
        """The function is callable on its own, and the argument it validates
        is its own — so the dispatcher's refusal is not its only guard."""
        (tmp_path / ".prawduct").mkdir()
        assert _hook.cmd_verify_operator_verification(tmp_path, "--dry-run") == 1
        assert "--dry-run" in capsys.readouterr().err


def test_documented_invocations_are_not_refused(capsys):
    """Every real invocation form found in the skills, hooks and docs.

    The guard's failure mode is over-refusal, and over-refusal breaks the
    governance flows that call these commands. Exercised against the guard
    directly rather than as subprocesses because the question is only whether
    the shape is accepted — what each command then does is its own test's.
    """
    documented = [
        ("clear", ["--session-start"]),
        ("clear", ["--session-start", "--brief-only"]),
        ("clear", ["--force"]),
        ("critic-begin", ["--mode", "chunk"]),
        ("critic-begin", ["--mode", "final", "--force"]),
        ("critic-end", []),
        ("critic-discard", []),
        ("critic-restore", ["rev-abc"]),
        ("critic-consolidate", []),
        ("subagent-stop", []),
        ("stop", []),
        ("jurisdiction", ["--file", "plan.md"]),
        ("jurisdiction", ["some", "plan", "text"]),
        ("jurisdiction", ["--artifacts-only"]),
        ("test-status", []),
        ("validate-evidence", []),
        ("test-evidence", ["record", "--no-rerun"]),
        ("test-evidence", ["record", "--from-counts", "passed=1", "failed=0"]),
        ("check-cumulative-critic", []),
        ("verify-chunk-refs", []),
        ("verify-chunk-refs", ["01"]),
        ("verify-records", ["--base", "a", "--head", "b", "--json"]),
        ("verify-coverage", []),
        ("ledger-append", ["--event", "review.pr"]),
        ("handoff", ["preview"]),
        ("review-stats", ["--json"]),
        ("classify-diff-risk", ["main"]),
        ("cost-of-commit", ["--json", "a.py", "b.py"]),
        ("check-operator-verification", []),
        ("accept-operator-verification", ["because the screenshot matched"]),
        ("verify-operator-verification", ["VRF-001"]),
        ("check-change-log-entry", []),
        ("check-releasability", ["--release", "v1.2.3"]),
        ("archive-plan", ["p.md", "--state", "completed", "--release", "v1.2.3"]),
        ("check-released", ["v1.2.3", "--json"]),
        ("check-pr-doc-only", []),
        ("stamp-merged", []),
        ("build-index", []),
        ("user-prompt-submit", []),
        ("regen-views", ["--check"]),
        ("infer-critic-mode", ["cumulative"]),
        ("resolve-base", []),
        ("disposition", ["rev-9", "F1", "--accept", "reason"]),
        ("render-dispositions", ["--json"]),
        ("evidence", ["list", "--kind", "review"]),
        ("bug-inbox", []),
        ("version", []),
        ("print-install-reference", []),
        ("advisory", ["list", "--state=active"]),
        ("backlog", ["list", "--repo", "o/r", "--json"]),
        ("coverage-status", ["--json"]),
        ("coverage-scaffold", ["--apply", "--json"]),
        ("migrate-plugin", ["--apply", "--json"]),
        ("init-product", ["/tmp/x", "--name", "X", "--apply"]),
        ("update-gitignore", []),
        ("update-gitignore", ["--dry-run"]),
        ("audit-learnings", ["--apply", "--json"]),
        ("norm-index-scaffold", ["--apply", "--json"]),
        ("learnings-obligation", ["--apply", "--json"]),
        ("lifecycle-repair", ["--apply", "--json"]),
        ("plan-backfill", ["--apply", "--date", "2026-01-01"]),
        ("repo-disable", ["--local", "--apply"]),
    ]
    for command, argv in documented:
        assert _hook._check_argument_shape(command, argv) == 0, (
            f"the guard refused a documented invocation: {command} {argv}"
        )
    # `stop`/`subagent-stop` are bare here, so no note should have fired either.
    assert capsys.readouterr().err == ""


def test_every_dispatched_command_appears_in_the_documented_list():
    """The list above is only evidence if it covers the chain. A command absent
    from both is one nobody checked against the guard."""
    listed = {
        "clear", "critic-begin", "critic-end", "critic-discard", "critic-restore",
        "critic-consolidate", "subagent-stop", "stop", "jurisdiction", "test-status",
        "validate-evidence", "test-evidence", "check-cumulative-critic",
        "verify-chunk-refs", "verify-records", "verify-coverage", "ledger-append",
        "handoff", "review-stats", "classify-diff-risk", "cost-of-commit",
        "check-operator-verification", "accept-operator-verification",
        "verify-operator-verification", "check-change-log-entry",
        "check-releasability", "archive-plan", "check-released", "check-pr-doc-only",
        "stamp-merged", "build-index", "user-prompt-submit", "regen-views",
        "infer-critic-mode", "resolve-base", "disposition", "render-dispositions",
        "evidence", "bug-inbox", "version", "print-install-reference", "advisory",
        "backlog", "coverage-status", "coverage-scaffold", "migrate-plugin",
        "init-product", "update-gitignore", "audit-learnings", "norm-index-scaffold",
        "learnings-obligation", "lifecycle-repair", "plan-backfill", "repo-disable",
    }
    assert set(_dispatch_branches()) == listed


# --- `update-gitignore` ------------------------------------------------------

BUILD_PLAN_REL = ".prawduct/artifacts/build-plan.md"


class TestUpdateGitignoreDryRun:
    def test_an_unrecognised_flag_is_refused_and_changes_nothing(self, tmp_path: Path):
        """The reported defect, verbatim: `--help` used to run the repair."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(f"{BUILD_PLAN_REL}\n")
        before = gitignore.read_bytes()

        proc = _run(tmp_path, ["update-gitignore", "--help"])

        assert proc.returncode != 0
        assert "--help" in proc.stderr
        assert gitignore.read_bytes() == before

    def test_dry_run_leaves_the_file_byte_identical(self, tmp_path: Path):
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(f"{BUILD_PLAN_REL}\n# mine\n")
        before = gitignore.read_bytes()

        proc = _run(tmp_path, ["update-gitignore", "--dry-run"])

        assert proc.returncode == 0, proc.stderr
        assert gitignore.read_bytes() == before

    def test_dry_run_reports_both_halves_of_what_it_would_do(self, tmp_path: Path):
        """Removals and additions are separate passes in the reconcile, and a
        preview that showed one of them would understate the change."""
        (tmp_path / ".gitignore").write_text(f"{BUILD_PLAN_REL}\n")

        out = _run(tmp_path, ["update-gitignore", "--dry-run"]).stdout

        assert f"would un-ignore: {BUILD_PLAN_REL}" in out
        assert "would ignore: .prawduct/.critic-findings.json" in out
        assert "would update .gitignore" in out
        # Nothing in the preview may read as having happened.
        assert "unignored:" not in out
        assert "updated .gitignore" not in out.replace("would update .gitignore", "")

    def test_dry_run_does_not_create_a_missing_gitignore(self, tmp_path: Path):
        """The no-file case writes the whole session set, so it is the largest
        mutation the command has — and the easiest one to leak past a dry run
        that only guards the rewrite path."""
        proc = _run(tmp_path, ["update-gitignore", "--dry-run"])

        assert proc.returncode == 0, proc.stderr
        assert not (tmp_path / ".gitignore").exists()

    def test_dry_run_on_a_conformant_repo_is_quiet(self, tmp_path: Path):
        _run(tmp_path, ["update-gitignore"])

        out = _run(tmp_path, ["update-gitignore", "--dry-run"]).stdout

        assert "no changes needed" in out
        assert "would" not in out

    def test_without_the_flag_it_still_reconciles(self, tmp_path: Path):
        """Mutate-by-default is the intended contract — doctor calls this as a
        repair step, and a preview-by-default would stop fixing the repos that
        need fixing."""
        gitignore = tmp_path / ".gitignore"
        gitignore.write_text(f"{BUILD_PLAN_REL}\n")

        proc = _run(tmp_path, ["update-gitignore"])

        assert proc.returncode == 0, proc.stderr
        assert f"unignored: {BUILD_PLAN_REL}" in proc.stdout
        lines = gitignore.read_text().splitlines()
        assert BUILD_PLAN_REL not in lines
        assert ".prawduct/.critic-findings.json" in lines

    def test_the_dry_run_prediction_matches_what_applying_does(self, tmp_path: Path):
        """The preview earns trust only by agreeing with the fixer. Both come
        from one body in `lib.core.update_gitignore`; this is the assertion that
        keeps it that way."""
        preview_repo = tmp_path / "preview"
        apply_repo = tmp_path / "apply"
        for repo in (preview_repo, apply_repo):
            repo.mkdir()
            (repo / ".gitignore").write_text(f"{BUILD_PLAN_REL}\n# mine\n")

        predicted = _run(preview_repo, ["update-gitignore", "--dry-run"]).stdout
        _run(apply_repo, ["update-gitignore"])

        applied = set((apply_repo / ".gitignore").read_text().splitlines())
        for line in predicted.splitlines():
            if line.startswith("would ignore: "):
                assert line[len("would ignore: ") :] in applied
            if line.startswith("would un-ignore: "):
                assert line[len("would un-ignore: ") :].split(" ")[0] not in applied
        # The preview left its own repo untouched while predicting all that.
        assert (preview_repo / ".gitignore").read_text() == f"{BUILD_PLAN_REL}\n# mine\n"


def test_an_argv_taking_command_still_refuses_its_own_unknown_flags(tmp_path: Path):
    """The dispatcher speaks only for commands that cannot speak for
    themselves; `_reject_unknown_args` is unchanged and still the guard for the
    ones that can."""
    proc = _run(tmp_path, ["audit-learnings", "--a-flag-that-never-existed"])

    assert proc.returncode == 2
    assert "--a-flag-that-never-existed" in proc.stderr
