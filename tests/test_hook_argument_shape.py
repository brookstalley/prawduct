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


# Where an argv-taking command's unknown-argument refusal lives, when it is NOT
# a `_reject_unknown_args` call in the `cmd_*` wrapper. Each entry is a reviewed
# answer to "what stops this command reading a token it does not understand as
# absent?" — never a way to skip the question.
#
# This set is the point of the test below, and the reason it exists: the guard
# was twice fixed by naming the commands someone had thought of. `update-gitignore`
# was fixed and `coverage-scaffold` was missed; those two were fixed and
# `migrate-plugin` and `init-product` were missed — the two most destructive
# commands on the surface, both of which scaffold or cut over under `--apply`.
# Enumeration is a list the next command is not on. A NEW argv-taking command
# now fails here until someone records which of the two it is.
# Verified by running each: bare invocation vs the same invocation plus an
# unrecognised token, comparing exit codes. A differing exit is the refusal; a
# matching one would mean the token was swallowed. Checked, not read off a
# comment — the comment above `check-releasability`'s parser says it scans
# explicitly *because* the `in argv` idiom is unsafe, and a comment saying that
# is not the same as a parser doing it.
_REFUSAL_VERIFIED = {
    "verify-records": "exits 2 on an unknown token",
    "classify-diff-risk": "exits 1 on an unknown token",
    "clear": "exits 2 on an unknown token",
    "evidence": "exits 1 on an unknown token",
    "render-dispositions": "exits 2 on an unknown token",
    "cost-of-commit": "exits 1 on an unknown token",
    "review-stats": "exits 1 on an unknown token",
    "check-releasability": "explicit token scan; exits 2",
    "check-released": "explicit token scan; exits 2",
    "plan-backfill": "explicit token scan; exits 2",
}

# Refusing is the wrong behaviour for these, for the same reasons the
# no-argument carve-outs exist.
_REFUSAL_NOT_WANTED = {
    "user-prompt-submit": "harness hook; must exit 0 for any argv or it blocks the session",
    "build-index": "inert — `del argv`; an ignored argument cannot act",
    "regen-views": "deprecated and inert; exit 0 for any input is its contract",
    "infer-critic-mode": "takes free-form $ARGUMENTS by contract; an unrecognised mode "
                         "falling through to inference is the documented behaviour",
    "jurisdiction": "documented fail-open: a bad --file or any other error yields no "
                    "matches rather than an error",
    "verify-chunk-refs": "single positional; covered by _check_argument_shape",
    "init-product": "lib.init_product._parse_argv collects unclaimed tokens; run() exits 2",
    # `migrate-plugin` is deliberately NOT listed. It IS guarded — in its wrapper —
    # and an entry here would have been a courtesy to the reader that silently
    # exempted it from the scan. It was listed once, and removing the guard left
    # this test green: a vacuous guard inside the guard written to stop vacuous
    # guards. An entry in this dict is a claim that the scan must NOT check the
    # wrapper; never add one for a command the scan can verify itself.
}

# Audited (#667), and the audit changed the METHOD as well as the verdict.
#
# These nine error on a BARE invocation — they need a subcommand or a required
# argument — so the bare-vs-bogus exit-code probe used above cannot tell a real
# refusal from that pre-existing error. Worse, for three of them
# (`ledger-append`, `critic-begin`, `critic-restore`) the valid and the
# bogus invocation share an exit code, so an exit-code comparison would have
# recorded a refusal as a swallow whichever way it was run. What separates them
# is the MESSAGE, so :data:`_VALID_INVOCATIONS` gives each a real invocation and
# :class:`TestTheAuditedNineActuallyRefuse` runs it both ways and reads the
# output. Verdicts below are observed exit codes from that run, not read off a
# comment.
_REFUSAL_AUDITED = {
    "backlog": "names the token; exits 2 (valid cache-query exits 6)",
    "test-evidence": "names the token; exits 2 (valid record exits 0)",
    "advisory": "names the token; exits 1 (valid list exits 0)",
    "ledger-append": "names the token; exits 1 — same code as the valid run, message differs",
    "critic-begin": "names the token; exits 1 — same code as the valid run, message differs",
    "critic-restore": "names the token; exits 1 — same code as the valid run, message differs",
    "handoff": "names the token; exits 2 (valid preview exits 0)",
    "disposition": "names the token; exits 2 (valid record exits 1 here)",
    "archive-plan": "names the token; exits 2 (valid --dry-run exits 0)",
}

# Empty, and it must stay that way by argument rather than by neglect: an entry
# here is a command nobody has run both ways. #667 emptied it; a new one is a
# claim that needs its own audit.
_REFUSAL_NOT_AUDITED: dict[str, str] = {}

_REFUSAL_DELEGATED_TO_LIB = {
    **_REFUSAL_VERIFIED,
    **_REFUSAL_NOT_WANTED,
    **_REFUSAL_AUDITED,
    **_REFUSAL_NOT_AUDITED,
}

#: One VALID invocation per audited command — the thing the bare-invocation
#: probe could not construct. Every one is offline and cheap: `backlog` reads the
#: local cache (never the network), and `test-evidence` supplies counts rather
#: than running a suite, because a test that runs the suite inside the suite is
#: not a test anyone will keep.
_VALID_INVOCATIONS = {
    "backlog": ["backlog", "cache-query", "open", "--repo", "octo/x"],
    "test-evidence": [
        "test-evidence", "record", "--from-counts", "passed=1", "failed=0", "skipped=0",
    ],
    "advisory": ["advisory", "list"],
    "ledger-append": ["ledger-append", "--event", "review.critic"],
    "critic-begin": ["critic-begin", "--mode", "chunk"],
    "critic-restore": ["critic-restore", "rev-20260101T000000Z-abcdef12"],
    "handoff": ["handoff", "preview"],
    "disposition": ["disposition", "rev-1", "F-1", "--accept", "why"],
    "archive-plan": ["archive-plan", ".prawduct/artifacts/build-plan.md", "--dry-run"],
}

_UNKNOWN_TOKEN = "--zzz-unrecognised-token"


def test_every_argv_taking_command_refuses_what_it_cannot_read():
    """The gap the pre-dispatch guard cannot close, pinned.

    `_check_argument_shape` speaks for commands that take NO argv. A command
    that receives `sys.argv[2:]` can see its arguments and must refuse the ones
    it does not know — the `"--flag" in argv` idiom reads an unrecognised token
    as *absent*, which is how a `--dry-run` came to mutate. Nothing structural
    covered this bucket, and the hole was refilled twice by enumeration.

    A command passes by calling `_reject_unknown_args` in its wrapper, or by
    carrying a recorded reason above. Adding one without either fails here.
    """
    source = HOOK.read_text(encoding="utf-8")
    branches = _dispatch_branches()
    takes_argv = {c for c, body in branches.items() if "sys.argv[2:]" in body}
    assert takes_argv, "parser found no argv-taking branches — the test would be vacuous"

    unguarded = []
    for command in sorted(takes_argv):
        if command in _REFUSAL_DELEGATED_TO_LIB:
            continue
        handler = re.search(r"return (cmd_\w+)\(", branches[command])
        if handler is None:
            unguarded.append(f"{command} (no cmd_* handler found)")
            continue
        body = re.search(
            rf"\ndef {handler.group(1)}\(.*?(?=\ndef )", source, re.S
        )
        if body is None or "_reject_unknown_args(" not in body.group(0):
            unguarded.append(f"{command} -> {handler.group(1)}")

    assert not unguarded, (
        "argv-taking command(s) with no unknown-argument refusal and no recorded "
        f"reason: {unguarded}. Add `_reject_unknown_args` to the wrapper, or record "
        "where the refusal lives in _REFUSAL_DELEGATED_TO_LIB."
    )


class TestTheAuditedNineActuallyRefuse:
    """#667's audit, executed rather than asserted.

    The nine were exempted with the reason "not audited" because a BARE
    invocation of each already errors, so the bare-vs-bogus exit-code probe
    could not tell a refusal from that pre-existing error. Constructing a valid
    invocation is what closes it — and doing so exposed that exit codes alone
    are the wrong instrument here: three of the nine refuse with the SAME exit
    code as their valid run and differ only in the message. An exit-code
    comparison would have filed those three as swallows.

    So the contract asserted is the one that actually matters: an unrecognised
    token must never be absorbed into the run. It is refused, and the refusal
    says which token — otherwise the operator is left re-reading their own
    command line for the difference. The ``"--flag" in argv`` idiom reads an
    unrecognised token as *absent*, which is the defect class that reached a
    live `.gitignore` rewrite.
    """

    @staticmethod
    def _repo(tmp_path: Path) -> Path:
        (tmp_path / ".prawduct" / "artifacts").mkdir(parents=True)
        (tmp_path / ".prawduct" / "project-state.yaml").write_text(
            "product_name: t\n", encoding="utf-8"
        )
        (tmp_path / ".prawduct" / "artifacts" / "build-plan.md").write_text(
            "# Plan\n", encoding="utf-8"
        )
        subprocess.run(["git", "init", "-q", "."], cwd=tmp_path, capture_output=True)
        return tmp_path

    def test_the_audit_covers_exactly_the_nine_it_claims_to(self):
        # The record and the invocations are two lists of the same set; letting
        # them drift is how a command gets a verdict nobody ran.
        assert set(_REFUSAL_AUDITED) == set(_VALID_INVOCATIONS)

    def test_nothing_is_left_unaudited(self):
        assert _REFUSAL_NOT_AUDITED == {}, (
            "a command exempted as 'not audited' is one nobody has run both ways — "
            f"run it and record the verdict: {sorted(_REFUSAL_NOT_AUDITED)}"
        )

    @pytest.mark.parametrize("command", sorted(_VALID_INVOCATIONS))
    def test_an_unknown_token_is_refused_and_named(self, command: str, tmp_path: Path):
        repo = self._repo(tmp_path)
        argv = _VALID_INVOCATIONS[command]
        valid = _run(repo, argv)
        bogus = _run(repo, [*argv, _UNKNOWN_TOKEN])
        assert bogus.returncode != 0, (
            f"{command} completed with an unrecognised token in argv — it was "
            f"swallowed:\n{bogus.stdout}\n{bogus.stderr}"
        )
        assert _UNKNOWN_TOKEN in (bogus.stderr + bogus.stdout), (
            f"{command} refused but did not say what it refused:\n{bogus.stderr}"
        )
        # ...and the refusal is about the token, not about the invocation being
        # broken in some other way — the valid form gets a different answer.
        assert (valid.returncode, valid.stderr) != (bogus.returncode, bogus.stderr), command


def test_the_delegation_record_names_only_real_commands():
    """A stale entry would exempt a command that no longer exists, and silently
    stop covering one that does."""
    branches = _dispatch_branches()
    assert set(_REFUSAL_DELEGATED_TO_LIB) <= set(branches)


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
        ("check-plugin-active", []),
        ("check-plugin-active", ["--path", "/tmp/x", "--json"]),
        ("check-plugin-active", ["--path", "/tmp/x", "--context", "doctor"]),
        ("check-plugin-active", ["--context", "onboard"]),
        ("check-learnings-pairing", []),
        ("check-learnings-pairing", ["--json"]),
        ("learnings-migrate", []),
        ("learnings-migrate", ["--propose-map"]),
        ("learnings-migrate", ["--apply", "--map", "/tmp/map.txt", "--json"]),
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
        "check-plugin-active",
        "check-learnings-pairing", "learnings-migrate",
        "stamp-merged", "build-index", "user-prompt-submit", "regen-views",
        "infer-critic-mode", "resolve-base", "disposition", "render-dispositions",
        "evidence", "bug-inbox", "version", "print-install-reference", "advisory",
        "backlog", "coverage-status", "coverage-scaffold", "migrate-plugin",
        "init-product", "update-gitignore", "audit-learnings", "norm-index-scaffold",
        "learnings-files",
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


def test_learnings_files_takes_argv_and_refuses_what_it_cannot_read(tmp_path: Path):
    """The new read-only verb, on both halves of this file's contract.

    It is dispatched WITH `sys.argv[2:]` — so it is the wrapper's job, not the
    pre-dispatch guard's, to refuse an unrecognised token — and its wrapper does
    that job. The specific hazard is the one that reached a live `.gitignore`
    rewrite: `--for-diff` is detected with `"--flag" in argv`, so a typo'd
    `--fordiff` read as *absent* would silently print the WHOLE rules corpus to
    a reviewer who asked for the diff's subset, which is a wider read that looks
    exactly like a correct one.
    """
    branches = _dispatch_branches()
    assert "sys.argv[2:]" in branches["learnings-files"]

    proc = _run(tmp_path, ["learnings-files", "--fordiff"])
    assert proc.returncode == 2
    assert "--fordiff" in proc.stderr
