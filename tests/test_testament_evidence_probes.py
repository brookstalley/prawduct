"""A repo whose tests run on testament records its evidence from a testament run.

The defect this pins: a repo onboarded to testament (`.testament.toml` at its root)
kept a declared `test_command` that runs the suite locally. Agents verified on the
pool, as the repo's agent instructions say, and could not hand that run to the
recorder: its JSON envelope is not JUnit, and `--from-counts` is refused beside a
declared command. So every evidence record ran the whole suite a second time.

Two surfaces answer it: a session-start advisory naming the fix, and the
`--from-counts` refusal, whose text is chosen from the declaration the recorder
resolved. The refusal must never offer one report as the whole suite where several
commands are declared, and the fix it names must be one the recorder accepts.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import advisory_store, probe_families, testament_evidence_probes as tep  # noqa: E402
from lib.advisory_store import ProjectState, clear_registry, make_codebase  # noqa: E402
from test_plugin_runtime import _git, _run_in  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
FIX = "test_command: testament run --junit-xml {junit_xml}\n"


@pytest.fixture(autouse=True)
def _isolated_registry():
    clear_registry()
    yield
    clear_registry()


def _repo(tmp_path: Path, state: str, *, manifest: bool = True) -> Path:
    repo = tmp_path / "product"
    (repo / ".prawduct").mkdir(parents=True)
    (repo / ".prawduct" / "project-state.yaml").write_text(state)
    if manifest:
        (repo / ".testament.toml").write_text('manifest_version = 2\nname = "product"\n')
    return repo


def _probe(repo: Path):
    return tep.probe_declared_command_skips_testament(ProjectState({}), make_codebase(repo))


# The downstream shape that showed the defect: a raster-group pytest declared,
# testament's manifest committed beside it.
_LOCAL = "test_command: uv run --group raster pytest --junit-xml={junit_xml} -q\ntests_dirs: tests\n"
_LIST_LOCAL = (
    "test_commands:\n"
    "  - uv run pytest --junit-xml={junit_xml}\n"
    "  - npm test -- --out={junit_xml}\n"
)
# prawduct's own shape: testament for the pool suite, local runs for the rest.
_LIST_WIRED = (
    "test_commands:\n"
    "  - testament run --junit-xml {junit_xml}\n"
    "  - node --test --test-reporter=junit --test-reporter-destination={junit_xml} t/*.mjs\n"
    "  - uv run pytest -m requires_history --junit-xml={junit_xml}\n"
)


# The wrapper shape from the report: a script that lints, builds, then runs
# testament with the report path it was given.
_WRAPPED = "scripts/test.sh --junit-xml={junit_xml}"
_WRAPPER_BODY = (
    "#!/bin/sh\nset -e\nruff check .\nmake native\n"
    "testament run --junit-xml=\"${1#--junit-xml=}\"\n"
)


def _wrapper(repo: Path, body: str = _WRAPPER_BODY) -> None:
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    (repo / "scripts" / "test.sh").write_text(body)


class TestRunsTestament:
    @pytest.mark.parametrize("command", [
        "testament run --junit-xml {junit_xml}",
        "uv run testament run --junit-xml={junit_xml}",
        "/opt/tools/bin/testament run --junit-xml {junit_xml} -- tests/",
        "testament --coordinator pool:9000 run --junit-xml {junit_xml}",
        "sh -c 'testament run --junit-xml {junit_xml}'",
    ])
    def test_a_command_that_runs_testament(self, command):
        assert tep.runs_testament(command)
        assert tep.records_testament(command)

    @pytest.mark.parametrize("command", [
        "uv run --group raster pytest --junit-xml={junit_xml} -q",
        # The word alone is not a run: a status query, or a path that merely names it.
        "testament status",
        "pytest tests/testament --junit-xml={junit_xml}",
        "testament-run --junit-xml {junit_xml}",
        # Unbalanced quotes cannot be split, so nothing is claimed about them.
        "testament run 'unterminated",
    ])
    def test_a_command_that_does_not(self, command):
        assert not tep.runs_testament(command)

    def test_running_without_the_placeholder_does_not_record(self):
        assert tep.runs_testament("testament run")
        assert not tep.records_testament("testament run")

    def test_a_script_in_the_repo_that_runs_testament(self, tmp_path):
        _wrapper(tmp_path)
        assert tep.runs_testament(_WRAPPED, tmp_path)
        assert tep.records_testament(_WRAPPED, tmp_path)
        # Control: the command's own words do not run testament.
        assert not tep.runs_testament(_WRAPPED)

    def test_a_script_whose_testament_line_is_a_comment_does_not(self, tmp_path):
        _wrapper(tmp_path, body="# testament run --junit-xml=\"$1\" (disabled)\npytest\n")
        assert not tep.runs_testament(_WRAPPED, tmp_path)

    @pytest.mark.parametrize("prefix", [
        "sh", "uv run", "timeout 900", "bash -o pipefail", "env -u CI",
    ])
    def test_a_script_behind_any_prefix_is_read(self, tmp_path, prefix):
        _wrapper(tmp_path)
        assert tep.runs_testament(f"{prefix} scripts/test.sh --junit-xml={{junit_xml}}", tmp_path)

    def test_a_file_a_shell_is_told_to_run_is_a_script(self, tmp_path):
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "test").write_text('testament run --junit-xml="$1"\n')
        assert tep.runs_testament("sh scripts/test {junit_xml}", tmp_path)
        # Control: the same file, not handed to a shell, is not known to be one.
        assert not tep.runs_testament("scripts/test {junit_xml}", tmp_path)

    def test_a_script_known_by_its_shebang_is_read(self, tmp_path):
        (tmp_path / "bin").mkdir()
        (tmp_path / "bin" / "check").write_text('#!/usr/bin/env bash\ntestament run --junit-xml="$1"\n')
        assert tep.runs_testament("bin/check {junit_xml}", tmp_path)

    @pytest.mark.parametrize("line", [
        '[ $# -ge 1 ] && testament run --junit-xml "$1"',  # `$#` is not a comment
        'bash -c "testament run --junit-xml $1"',  # a shell handed a command string
        'eval "testament run --junit-xml $1"',
    ], ids=["dollar-hash", "bash-c", "eval"])
    def test_shell_forms_that_run_testament_are_read(self, tmp_path, line):
        _wrapper(tmp_path, body=f"#!/bin/sh\n{line}\n")
        assert tep.runs_testament(_WRAPPED, tmp_path)

    def test_a_continued_line_is_read_whole(self, tmp_path):
        _wrapper(tmp_path, body='#!/bin/sh\ntestament \\\n  run --junit-xml="$1"\n')
        assert tep.runs_testament(_WRAPPED, tmp_path)

    @pytest.mark.parametrize("body", [
        'echo "next: testament run --junit-xml out.xml"\npytest\n',
        "pytest --junit-xml=\"$1\"  # TODO: switch to testament run\n",
    ], ids=["quoted-string", "trailing-comment"])
    def test_text_that_only_mentions_testament_does_not(self, tmp_path, body):
        _wrapper(tmp_path, body=body)
        assert not tep.runs_testament(_WRAPPED, tmp_path)

    def test_a_file_named_as_an_argument_is_not_read(self, tmp_path):
        """pytest runs the test file; it does not execute it as a wrapper, so a
        test that QUOTES the wired command is not one."""
        (tmp_path / "tests").mkdir()
        # An unquoted docstring line, so only the shell-script check keeps it out.
        (tmp_path / "tests" / "test_x.py").write_text(
            'def test_it():\n    """\n    testament run --junit-xml {junit_xml}\n    """\n')
        assert not tep.runs_testament("pytest tests/test_x.py --junit-xml={junit_xml}", tmp_path)

    def test_a_script_outside_the_repo_is_not_read(self, tmp_path):
        repo = tmp_path / "repo"
        repo.mkdir()
        _wrapper(tmp_path)  # tmp_path/scripts/test.sh, beside the repo, not in it
        assert not tep.runs_testament("../scripts/test.sh --junit-xml={junit_xml}", repo)
        assert tep.runs_testament(_WRAPPED, tmp_path), "control: the same script in its repo"


# Each declaration shape the recorder resolves, with what it does on
# `--from-counts`: "declared" refuses the counts beside commands, "fallback"
# records them (nothing declared), "refused" rejects the declaration itself.
_SHAPES = {
    "absent": ("tests_dirs: tests\n", "fallback", tep.Declared(None, ())),
    "scalar": (_LOCAL, "declared", tep.Declared("test_command", (
        "uv run --group raster pytest --junit-xml={junit_xml} -q",))),
    "list": (_LIST_LOCAL, "declared", tep.Declared("test_commands", (
        "uv run pytest --junit-xml={junit_xml}", "npm test -- --out={junit_xml}"))),
    "empty-flow": ("test_commands: []\n", "refused", None),
    "flow": ("test_commands: [a, b]\n", "refused", None),
    "nested": ("test_commands:\n  path: a\n", "refused", None),
    "empty-block": ("test_commands:\nbase_branch: develop\n", "refused", None),
    "both": (FIX + "test_commands:\n  - npm test -- --out={junit_xml}\n", "refused", None),
}


def _git_repo(tmp_path: Path, state: str, *, manifest: bool = True) -> Path:
    repo = _repo(tmp_path, state, manifest=manifest)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    return repo


def _from_counts(repo: Path):
    return _run_in(repo, "test-evidence", "record", "--from-counts", "passed=3", "failed=0")


class TestResolvedAsTheRecorderResolves:
    """The probe's reader and the recorder's agree on every disputed shape."""

    @pytest.mark.parametrize("label", sorted(_SHAPES))
    def test_parity_with_the_real_recorder(self, label, tmp_path):
        state, outcome, expected = _SHAPES[label]
        repo = _git_repo(tmp_path, state)
        assert tep.resolve_declared(repo / ".prawduct" / "project-state.yaml") == expected
        res = _from_counts(repo)
        if outcome == "fallback":
            assert res.returncode == 0, res.stderr
        elif outcome == "declared":
            assert res.returncode == 2
            assert "--from-counts cannot be combined with a declared" in res.stderr
        else:
            assert res.returncode == 2
            assert "--from-counts cannot be combined" not in res.stderr, res.stderr


class TestProbe:
    def test_fires_on_a_testament_repo_whose_declared_command_runs_locally(self, tmp_path):
        [cand] = _probe(_repo(tmp_path, _LOCAL))
        assert cand.type == tep.PROBE_TYPE
        assert "declare `test_command: testament run --junit-xml {junit_xml}`" in cand.trigger_summary
        assert "uv run --group raster pytest" in cand.trigger_summary
        assert cand.owner_action and "prawduct-hook" not in cand.owner_action
        assert cand.evidence == (
            "declared: uv run --group raster pytest --junit-xml={junit_xml} -q",
        )

    def test_a_declared_wrapper_that_runs_testament_is_wired(self, tmp_path):
        repo = _repo(tmp_path, f"test_command: {_WRAPPED}\n")
        _wrapper(repo)
        assert _probe(repo) == []

    def test_a_wrapper_that_does_not_run_testament_still_fires_hedged(self, tmp_path):
        repo = _repo(tmp_path, f"test_command: {_WRAPPED}\n")
        _wrapper(repo, body="#!/bin/sh\npytest --junit-xml=\"$1\"\n")
        [cand] = _probe(repo)
        assert "as far as prawduct can read" in cand.trigger_summary
        assert "replacing it drops those from test evidence" in cand.owner_action

    def test_following_its_fix_silences_it(self, tmp_path):
        """The recommendation's effect, not its wording: apply it and the advisory goes."""
        repo = _repo(tmp_path, _LOCAL)
        assert _probe(repo)
        (repo / ".prawduct" / "project-state.yaml").write_text(FIX + "tests_dirs: tests\n")
        assert _probe(repo) == []

    def test_a_list_gets_the_list_form_of_the_fix(self, tmp_path):
        """Adding a `test_command` beside a list makes the recorder refuse both."""
        [cand] = _probe(_repo(tmp_path, _LIST_LOCAL))
        assert "replace the `test_commands` entry" in cand.trigger_summary
        assert "declare `test_command:" not in cand.trigger_summary
        assert cand.evidence == (
            "declared: npm test -- --out={junit_xml}",
            "declared: uv run pytest --junit-xml={junit_xml}",
        )

    def test_following_the_list_fix_silences_it_and_the_recorder_accepts_it(self, tmp_path):
        repo = _git_repo(tmp_path, _LIST_LOCAL)
        fixed = _LIST_LOCAL.replace(
            "uv run pytest --junit-xml={junit_xml}", "testament run --junit-xml {junit_xml}")
        (repo / ".prawduct" / "project-state.yaml").write_text(fixed)
        assert _probe(repo) == []
        assert tep.resolve_declared(repo / ".prawduct" / "project-state.yaml") is not None

    def test_fires_when_nothing_is_declared(self, tmp_path):
        """Undeclared means the recorder's local pytest fallback, which skips testament too."""
        [cand] = _probe(_repo(tmp_path, "tests_dirs: tests\n"))
        assert cand.evidence == ("declared: none",)
        assert "local pytest fallback" in cand.trigger_summary

    def test_one_testament_entry_among_several_is_wired(self, tmp_path):
        assert _probe(_repo(tmp_path, _LIST_WIRED)) == []

    def test_silent_without_a_manifest(self, tmp_path):
        assert _probe(_repo(tmp_path, _LOCAL, manifest=False)) == []

    @pytest.mark.parametrize("label", ["empty-flow", "empty-block", "flow", "nested", "both"])
    def test_could_not_look_where_the_recorder_refuses_and_says_so(self, label, tmp_path, capsys):
        assert _probe(_repo(tmp_path, _SHAPES[label][0])) is None
        assert "NOTE: testament evidence probe skipped" in capsys.readouterr().err

    def test_this_repo_does_not_fire(self):
        """The positive control on a real declaration: prawduct's first entry runs testament."""
        assert (REPO_ROOT / ".testament.toml").is_file()
        assert tep.resolve_declared(REPO_ROOT / ".prawduct" / "project-state.yaml").commands
        assert _probe(REPO_ROOT) == []

    def test_registered_at_the_composition_root(self):
        probe_families.register_all()
        assert f"{tep.FEATURE}:{tep.PROBE_TYPE}" in advisory_store._REGISTRY


def _refusal(repo: Path) -> str:
    res = _from_counts(repo)
    assert res.returncode == 2, res.stderr
    assert not (repo / ".prawduct" / ".test-evidence.json").exists()
    assert "--from-counts cannot be combined with a declared" in res.stderr.splitlines()[0]
    return res.stderr


class TestFromCountsRefusal:
    def test_unwired_single_command_names_the_testament_route_and_the_scalar_fix(self, tmp_path):
        err = _refusal(_git_repo(tmp_path, _LOCAL))
        assert "No declared command runs testament" in err
        assert "`testament run --junit-xml <report>` ingested with `--from-junit <report>`" in err
        assert FIX.strip() in err

    def test_unwired_list_says_each_other_command_owes_its_report_and_gives_the_list_fix(
        self, tmp_path,
    ):
        err = _refusal(_git_repo(tmp_path, _LIST_LOCAL))
        assert "the other declared commands still owe their own reports" in err
        assert "replace the `test_commands` entry" in err
        assert "test_command:" not in err

    def test_wired_single_command_leads_with_a_bare_record(self, tmp_path):
        err = _refusal(_git_repo(tmp_path, FIX))
        assert "A bare `test-evidence record` runs the declared command on testament" in err
        assert FIX.strip() not in err

    def test_a_declared_wrapper_that_runs_testament_reads_as_wired(self, tmp_path):
        repo = _git_repo(tmp_path, f"test_command: {_WRAPPED}\n")
        _wrapper(repo)
        err = _refusal(repo)
        assert "A bare `test-evidence record` runs the declared command on testament" in err
        assert "No declared command runs testament" not in err

    def test_a_wrapper_given_no_report_path_is_named(self, tmp_path):
        repo = _git_repo(tmp_path, "test_command: scripts/test.sh\n")
        _wrapper(repo)
        err = _refusal(repo)
        assert "The declared testament command has no `{junit_xml}` placeholder" in err

    def test_wired_list_never_offers_the_testament_report_as_the_whole_suite(self, tmp_path):
        """prawduct's own shape: one report would record a third of the suite as green."""
        err = _refusal(_git_repo(tmp_path, _LIST_WIRED))
        assert "runs all 3 declared commands" in err
        assert "one `--from-junit <report>` for each of the 3 declared commands" in err
        assert "a testament report alone covers only its own entry" in err

    def test_a_testament_command_without_the_placeholder_is_named(self, tmp_path):
        err = _refusal(_git_repo(tmp_path, "test_command: testament run\n"))
        assert "has no `{junit_xml}` placeholder" in err
        assert "A bare `test-evidence record` runs" not in err

    def test_no_testament_keeps_the_generic_routes(self, tmp_path):
        """The control: without a manifest nothing names testament."""
        err = _refusal(_git_repo(tmp_path, _LOCAL, manifest=False))
        assert "testament" not in err
        assert "ingest with `--from-junit <report>`" in err
        assert "a bare `test-evidence record` runs the declared command and" in err

    def test_no_testament_list_asks_for_a_report_per_command(self, tmp_path):
        err = _refusal(_git_repo(tmp_path, _LIST_LOCAL, manifest=False))
        assert "one `--from-junit <report>` for each of the 2 declared commands" in err
