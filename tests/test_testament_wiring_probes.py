"""A repo whose tests run on testament records its evidence from a testament run.

The defect this pins: a repo onboarded to testament (`.testament.toml` at its root)
kept a declared `test_command` that runs the suite locally. Agents verified on the
pool, as the repo's agent instructions say, and could not hand that run to the
recorder: its JSON envelope is not JUnit, and `--from-counts` is refused beside a
declared command. So every evidence record ran the whole suite a second time.

Two surfaces answer it from one predicate: a session-start advisory naming the
one-line fix, and the `--from-counts` refusal, which leads with the testament
route where testament is present.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import advisory_store, probe_families, testament_wiring_probes as twp  # noqa: E402
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
    return twp.probe_declared_command_skips_testament(ProjectState({}), make_codebase(repo))


# The downstream shape that showed the defect: a raster-group pytest declared,
# testament's manifest committed beside it.
_LOCAL = "test_command: uv run --group raster pytest --junit-xml={junit_xml} -q\ntests_dirs: tests\n"


class TestRunsTestament:
    @pytest.mark.parametrize("command", [
        "testament run --junit-xml {junit_xml}",
        "uv run testament run --junit-xml={junit_xml}",
        "/opt/tools/bin/testament run --junit-xml {junit_xml} -- tests/",
    ])
    def test_a_command_that_runs_testament(self, command):
        assert twp.runs_testament(command)

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
        assert not twp.runs_testament(command)


class TestProbe:
    def test_fires_on_a_testament_repo_whose_declared_command_runs_locally(self, tmp_path):
        [cand] = _probe(_repo(tmp_path, _LOCAL))
        assert cand.type == twp.PROBE_TYPE
        assert "testament run --junit-xml {junit_xml}" in cand.trigger_summary
        assert "uv run --group raster pytest" in cand.trigger_summary
        assert cand.owner_action and "prawduct-hook" not in cand.owner_action
        assert cand.evidence == (
            "declared: uv run --group raster pytest --junit-xml={junit_xml} -q",
        )

    def test_following_its_fix_silences_it(self, tmp_path):
        """The recommendation's effect, not its wording: apply it and the advisory goes."""
        repo = _repo(tmp_path, _LOCAL)
        assert _probe(repo)
        (repo / ".prawduct" / "project-state.yaml").write_text(FIX + "tests_dirs: tests\n")
        assert _probe(repo) == []

    def test_fires_when_nothing_is_declared(self, tmp_path):
        """Undeclared means the recorder's local pytest fallback, which skips testament too."""
        [cand] = _probe(_repo(tmp_path, "tests_dirs: tests\n"))
        assert cand.evidence == ("declared: none",)

    def test_one_testament_entry_among_several_is_wired(self, tmp_path):
        """prawduct's own shape: testament for the pool suite, local runs for the rest."""
        state = (
            "test_commands:\n"
            "  - testament run --junit-xml {junit_xml}\n"
            "  - node --test --test-reporter=junit --test-reporter-destination={junit_xml} t/*.mjs\n"
        )
        assert _probe(_repo(tmp_path, state)) == []

    def test_a_list_with_no_testament_entry_fires_and_names_each(self, tmp_path):
        state = "test_commands:\n  - uv run pytest --junit-xml={junit_xml}\n  - npm test -- --out={junit_xml}\n"
        [cand] = _probe(_repo(tmp_path, state))
        assert cand.evidence == (
            "declared: npm test -- --out={junit_xml}",
            "declared: uv run pytest --junit-xml={junit_xml}",
        )

    def test_silent_without_a_manifest(self, tmp_path):
        assert _probe(_repo(tmp_path, _LOCAL, manifest=False)) == []

    def test_could_not_look_when_test_commands_is_unparseable(self, tmp_path):
        """The recorder refuses this shape outright; the probe says nothing rather than guess."""
        assert _probe(_repo(tmp_path, "test_commands: [a, b]\n")) is None

    def test_this_repo_does_not_fire(self):
        """The positive control on a real declaration: prawduct's first entry runs testament."""
        assert (REPO_ROOT / ".testament.toml").is_file()
        assert _probe(REPO_ROOT) == []

    def test_registered_at_the_composition_root(self):
        probe_families.register_all()
        assert f"{twp.FEATURE}:{twp.PROBE_TYPE}" in advisory_store._REGISTRY


def _git_repo(tmp_path: Path, state: str, *, manifest: bool = True) -> Path:
    repo = _repo(tmp_path, state, manifest=manifest)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    return repo


def _refusal(repo: Path) -> str:
    res = _run_in(repo, "test-evidence", "record", "--from-counts", "passed=3", "failed=0")
    assert res.returncode == 2, res.stderr
    assert not (repo / ".prawduct" / ".test-evidence.json").exists()
    return res.stderr


class TestFromCountsRefusal:
    def test_unwired_testament_repo_leads_with_the_testament_route(self, tmp_path):
        err = _refusal(_git_repo(tmp_path, _LOCAL))
        first = err.splitlines()[0]
        assert "--from-counts cannot be combined with a declared" in first
        # The route that works for a caller who just ran `testament run`, before
        # the generic "ingest a report" advice.
        lead = err.index("testament run --junit-xml <report>")
        assert lead < err.index("bare `test-evidence record`")
        assert "--from-junit <report>" in err
        assert FIX.strip() in err

    def test_wired_testament_repo_says_bare_record_runs_testament(self, tmp_path):
        err = _refusal(_git_repo(tmp_path, FIX))
        assert "testament run --junit-xml <report>" in err
        assert "already runs testament" in err
        assert FIX.strip() not in err

    def test_no_testament_keeps_the_generic_routes(self, tmp_path):
        """The control: without a manifest nothing names testament."""
        err = _refusal(_git_repo(tmp_path, _LOCAL, manifest=False))
        assert "testament" not in err
        assert "--from-junit <report>" in err
        assert "bare `test-evidence record`" in err
