"""Subprocess tests for the doctor coverage subcommands — coverage-status and
coverage-scaffold.

These invoke ``bin/prawduct-hook`` the way the doctor skill does (with
``CLAUDE_PLUGIN_ROOT`` + ``CLAUDE_PROJECT_DIR``), exercising the real command
dispatch, the lazy plugin-lib imports, and the shared ``coverage_probes``
expectation table end to end. The status check reports the three-layer chain and
names the single staged layer that owns the nudge; the scaffold helper drops
neutral stubs for the missing expected artifacts on ``--apply`` (dry run by
default, never overwriting, never auto-deciding relevance).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"


def _run(command: str, project_dir: Path, *args: str) -> subprocess.CompletedProcess:
    home = project_dir.parent / "_home"
    home.mkdir(exist_ok=True)
    env = {
        "HOME": str(home),
        "CLAUDE_PLUGIN_ROOT": str(ROOT),
        "CLAUDE_PROJECT_DIR": str(project_dir),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        ["python3", str(HOOK), command, *args],
        capture_output=True, text=True, env=env, timeout=30,
    )


def _write_state(project_dir: Path, structural_block: str) -> None:
    prawduct = project_dir / ".prawduct"
    prawduct.mkdir(parents=True, exist_ok=True)
    (prawduct / "project-state.yaml").write_text(
        "schema_version: 6\nclassification:\n  structural:\n" + structural_block,
        encoding="utf-8",
    )


def _write_artifact(project_dir: Path, name: str, body: str = "# stub\n") -> None:
    d = project_dir / ".prawduct" / "artifacts"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body, encoding="utf-8")


def _write_product_work(project_dir: Path) -> None:
    """Give the fixture a reason to owe discovery.

    Layer 0 is staged behind product-definition work: a repo with no code and no
    ``docs/`` has not started, so "you never said what this is" asks nothing of
    anyone. Every fixture that expects layer 0 to be ACTIVE has to carry this —
    without it the fixture is a freshly-onboarded empty repo, which is exactly the
    state the layer is supposed to stay quiet in.
    """
    (project_dir / "src").mkdir(parents=True, exist_ok=True)
    (project_dir / "src" / "app.py").write_text("def main():\n    ...\n", encoding="utf-8")


# Structural blocks (6-space nested attributes record presence; null does not).
_GATE_OPEN = "    has_human_interface:\n      modality: terminal\n"
_API_RECORDED = "    exposes_programmatic_interface:\n      consumers: external\n"
_ALL_NULL = "".join(
    f"    {c}: null\n"
    for c in (
        "has_human_interface", "runs_unattended", "exposes_programmatic_interface",
        "has_multiple_party_types", "handles_sensitive_data", "multi_process_distributed",
    )
)

_UNIVERSAL = [
    "data-model.md", "security-model.md", "nonfunctional-requirements.md",
    "operational-spec.md", "observability-strategy.md",
]


# ---------------------------------------------------------------------------
# coverage-status — the doctor three-layer report
# ---------------------------------------------------------------------------


class TestCoverageStatus:
    def test_layer0_active_when_characteristics_unrecorded(self, tmp_path):
        # Template-default structural (all null) + product work → layer 0 owns the
        # nudge. The product work is load-bearing, not scenery: layer 0 asks "you
        # never said what this is", which is only a question once there is a "this".
        _write_state(tmp_path, _ALL_NULL)
        _write_product_work(tmp_path)
        result = _run("coverage-status", tmp_path, "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["structural_recorded"] is False
        assert data["discovery_expected"] is True
        assert data["active_layer"] == 0
        assert "discovery" in data["fix"]

    def test_layer1_active_lists_universal_and_triggered(self, tmp_path):
        # Characteristic recorded (gate open) + api characteristic → layer 1 owns
        # it, and the missing set includes the triggered api-contract.
        _write_state(tmp_path, _API_RECORDED)
        result = _run("coverage-status", tmp_path, "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["structural_recorded"] is True
        assert data["active_layer"] == 1
        artifacts = {m["artifact"]: m["characteristic"] for m in data["missing_artifacts"]}
        for name in _UNIVERSAL:
            assert artifacts.get(name) is None
        assert artifacts.get("api-contract.md") == "exposes_programmatic_interface"

    def test_layer2_active_when_artifacts_present_norms_unratified(self, tmp_path):
        # Recorded + every universal artifact present (layer 1 silent) + no
        # ## Direction anywhere → the nudge advances to layer 2 (ratify norms).
        _write_state(tmp_path, _GATE_OPEN)
        for name in _UNIVERSAL:
            _write_artifact(tmp_path, name)
        result = _run("coverage-status", tmp_path, "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["missing_artifacts"] == []
        assert data["norms_unratified"] is True
        assert data["active_layer"] == 2

    def test_human_output_names_the_active_layer(self, tmp_path):
        _write_state(tmp_path, _ALL_NULL)
        _write_product_work(tmp_path)
        result = _run("coverage-status", tmp_path)
        assert result.returncode == 0
        assert "Layer 0" in result.stdout
        assert "Active nudge → Layer 0" in result.stdout


# ---------------------------------------------------------------------------
# The report and the ambient nudge answer for the same repo (#241)
# ---------------------------------------------------------------------------


class TestReportAgreesWithTheNudge:
    """``coverage-status``'s entire claim is that it mirrors the ambient advisory.

    It used to compute layer-0-active as *not recorded*, full stop, while the probe
    it claims to mirror also requires product-definition work — so a freshly
    onboarded empty repo was told its coverage was degraded by a report reading an
    expectation table that was asking it for nothing (#241).

    These assert **agreement between the two surfaces**, not a hardcoded layer per
    fixture: a future staging change that moves both together should keep them
    green, and one that moves only the report should turn them red. The direction of
    the agreement is pinned separately, because "both silent" and "both firing"
    agree equally well and only one of them is right per fixture.
    """

    def _nudged(self, project_dir: Path) -> bool:
        """Does the ambient layer-0 advisory fire on this repo?"""
        from lib import advisory_store, coverage_probes  # noqa: PLC0415

        return bool(
            coverage_probes.probe_discovery_not_captured(
                advisory_store.load_project_state(project_dir),
                advisory_store.make_codebase(project_dir),
            )
        )

    def _reports_layer0(self, project_dir: Path) -> bool:
        result = _run("coverage-status", project_dir, "--json")
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)["active_layer"] == 0

    def test_fresh_repo_with_no_product_work(self, tmp_path):
        # The #241 fixture: onboarded, nothing built. The nudge is silent; before
        # the fix the report said layer 0.
        _write_state(tmp_path, _ALL_NULL)
        assert self._reports_layer0(tmp_path) == self._nudged(tmp_path)
        assert self._nudged(tmp_path) is False

    def test_repo_with_code_and_no_characteristics(self, tmp_path):
        _write_state(tmp_path, _ALL_NULL)
        _write_product_work(tmp_path)
        assert self._reports_layer0(tmp_path) == self._nudged(tmp_path)
        assert self._nudged(tmp_path) is True

    def test_repo_with_docs_only_work(self, tmp_path):
        # docs/ markdown is product-definition work too — a spec-first repo owes
        # discovery exactly like a code-first one.
        _write_state(tmp_path, _ALL_NULL)
        (tmp_path / "docs").mkdir()
        (tmp_path / "docs" / "design.md").write_text("# Design\n", encoding="utf-8")
        assert self._reports_layer0(tmp_path) == self._nudged(tmp_path)
        assert self._nudged(tmp_path) is True

    def test_repo_with_characteristics_recorded(self, tmp_path):
        _write_state(tmp_path, _GATE_OPEN)
        _write_product_work(tmp_path)
        assert self._reports_layer0(tmp_path) == self._nudged(tmp_path)
        assert self._nudged(tmp_path) is False

    def test_layer1_does_not_inherit_a_silenced_layer0(self, tmp_path):
        """The trap the fix had to avoid.

        Layer 1 used to be reached by *falling through* layer 0's condition, so
        gating layer 0 on product work would have handed the fresh repo straight to
        layer 1 — every universal artifact is missing there — while the layer-1
        probe stayed silent behind its own staging gate. Same disagreement, one
        layer down, wearing the fix as a disguise.
        """
        from lib import advisory_store, coverage_probes  # noqa: PLC0415

        _write_state(tmp_path, _ALL_NULL)
        data = json.loads(_run("coverage-status", tmp_path, "--json").stdout)
        codebase = advisory_store.make_codebase(tmp_path)
        state = advisory_store.load_project_state(tmp_path)
        layer1_nudged = bool(
            coverage_probes.probe_strategy_artifact_missing(state, codebase)
        )

        assert data["missing_artifacts"], "fixture is not exercising the trap"
        assert (data["active_layer"] == 1) == layer1_nudged
        assert data["active_layer"] is None

    def test_an_unrecognised_language_is_reported_as_unfound_not_as_absent(self, tmp_path):
        """The population this staging predicate is wrong about.

        `_has_product_definition_work` reads source by suffix allowlist, so a repo
        written entirely in a language the tuple omits (`.cs`, `.tsx`, `.php`, …)
        scans as unstarted. Under-firing is the right direction for a *nudge* —
        silence costs advice, never soundness — but the report renders the same
        predicate as prose, and prose that says "no product work in this repo" to a
        repo full of C# is a new false claim, printed as fact, by the one surface
        that was telling that population the truth before this chunk.

        So the pin is on the CLAIM, not on the classification: the report may say it
        found nothing, and may not say there is nothing. `#561` is the real fix
        (classify by exclusion); this keeps the wording honest until it lands, and
        it is what fails if someone re-tightens the sentence.
        """
        _write_state(tmp_path, _ALL_NULL)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "Program.cs").write_text("class P {}\n", encoding="utf-8")

        result = _run("coverage-status", tmp_path)
        assert result.returncode == 0
        assert "recognises" in result.stdout
        assert "no product work in this repo" not in result.stdout
        # And the report still agrees with the nudge, which is the chunk's invariant
        # — both are wrong about this repo together, which is a filed item, not a
        # disagreement.
        assert self._reports_layer0(tmp_path) == self._nudged(tmp_path)

    def test_human_output_does_not_call_an_unstarted_chain_satisfied(self, tmp_path):
        """The `--json` path never exercises the formatter (learning: a human-mode
        branch that no test reads is where a new result type hides). "Satisfied" and
        "not started" are different answers and must not render alike."""
        _write_state(tmp_path, _ALL_NULL)
        result = _run("coverage-status", tmp_path)
        assert result.returncode == 0
        assert "no product work found yet" in result.stdout
        assert "the coverage chain is satisfied" not in result.stdout
        assert "Active nudge → Layer" not in result.stdout

    def test_a_broken_staging_check_reports_unknown_rather_than_crashing(self, tmp_path):
        """`cmd_coverage_status` promises a report that degrades, never crashes.

        Layer 2 already had that guard; layers 0-1 did not, and this chunk gave them
        a call that walks the tree and lazy-imports `gitstate`. The probes' own
        fail-softness comes from the advisory *runner*, which is not on this path.
        Simulated by making the plugin lib raise on import of the module the staging
        predicate reaches.
        """
        _write_state(tmp_path, _ALL_NULL)
        result = _run_with_broken_staging(tmp_path)
        assert result.returncode == 0, result.stderr
        assert "Traceback" not in result.stderr
        assert "unknown (staging check unavailable)" in result.stdout
        assert "layers 0-1 could not be checked" in result.stdout
        # And it must not silently claim a clean chain while unable to check it.
        assert "the coverage chain is satisfied" not in result.stdout

    def test_layer_2_names_itself_as_unreliable_when_layers_0_1_could_not_be_checked(
        self, tmp_path
    ):
        """The mirror of the case above, and the one that needed a second look.

        With the staging check broken AND the norm registry unratified, layer 2 is
        the only layer that *can* be graded — so the report names it as the active
        nudge. But layer 2 sits DOWNSTREAM of two layers nothing evaluated, and
        "here is your fix" for a chain position no one checked is the same
        overclaim `#241` was filed for. The caveat is the refusal; this fixture is
        what makes deleting it go red, because the sibling assertion above passes
        on both branches.
        """
        _write_state(tmp_path, _ALL_NULL)
        _write_product_work(tmp_path)
        # A strategy-class artifact with no `## Direction` — exists, unratified.
        _write_artifact(tmp_path, "security-model.md", "# Security Model\n\nProse.\n")

        result = _run_with_broken_staging(tmp_path)
        assert result.returncode == 0, result.stderr
        assert "Traceback" not in result.stderr
        assert "Active nudge → Layer 2" in result.stdout
        assert "layers 0-1 could not be checked" in result.stdout
        assert "may not be the first thing owed" in result.stdout


def _run_with_broken_staging(tmp_path: Path) -> subprocess.CompletedProcess:
    """Run `coverage-status` with `coverage_probes.layer_status` raising.

    Shared by the two staging-unavailable cases so they exercise the SAME
    failure, not two hand-rolled approximations of it.
    """
    broken = tmp_path.parent / "_broken_lib"
    broken.mkdir(exist_ok=True)
    # A sitecustomize that lets `lib.coverage_probes` import normally and then
    # breaks the one call the report makes. Poisoning `lib.gitstate` outright
    # would not reach this branch — the hook resolves its project dir through
    # gitstate before dispatching, so the crash would land upstream of the code
    # under test, which is its own lesson about fixtures that never arrive.
    (broken / "sitecustomize.py").write_text(
        "import importlib, importlib.abc, importlib.util, sys\n"
        "TARGET = 'lib.coverage_probes'\n"
        "class _Wrap(importlib.abc.MetaPathFinder, importlib.abc.Loader):\n"
        "    busy = False\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name != TARGET or _Wrap.busy:\n"
        "            return None\n"
        "        return importlib.util.spec_from_loader(name, self)\n"
        "    def create_module(self, spec):\n"
        "        _Wrap.busy = True\n"
        "        try:\n"
        "            mod = importlib.import_module(TARGET)\n"
        "        finally:\n"
        "            _Wrap.busy = False\n"
        "        def _boom(*a, **k):\n"
        "            raise RuntimeError('staging predicate is broken')\n"
        "        mod.layer_status = _boom\n"
        "        return mod\n"
        "    def exec_module(self, module):\n"
        "        pass\n"
        "sys.meta_path.insert(0, _Wrap())\n",
        encoding="utf-8",
    )
    home = tmp_path.parent / "_home"
    home.mkdir(exist_ok=True)
    return subprocess.run(
        ["python3", str(HOOK), "coverage-status"],
        capture_output=True, text=True, timeout=30,
        env={
            "HOME": str(home),
            "CLAUDE_PLUGIN_ROOT": str(ROOT),
            "CLAUDE_PROJECT_DIR": str(tmp_path),
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "PYTHONPATH": str(broken),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )


# ---------------------------------------------------------------------------
# coverage-scaffold — the one-act stub helper
# ---------------------------------------------------------------------------


class TestCoverageScaffold:
    def test_dry_run_creates_nothing(self, tmp_path):
        _write_state(tmp_path, _GATE_OPEN)
        result = _run("coverage-scaffold", tmp_path, "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["applied"] is False
        assert data["created"] == []
        assert not (tmp_path / ".prawduct" / "artifacts").exists()

    def test_apply_creates_stubs_for_missing(self, tmp_path):
        _write_state(tmp_path, _API_RECORDED)
        result = _run("coverage-scaffold", tmp_path, "--apply", "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["applied"] is True
        assert set(data["created"]) == set(_UNIVERSAL) | {"api-contract.md"}
        for name in data["created"]:
            assert (tmp_path / ".prawduct" / "artifacts" / name).is_file()

    def test_stub_is_a_neutral_placeholder_not_a_decision(self, tmp_path):
        # The stub must not pre-decide relevance — it prompts the owner to fill it,
        # offering the (not relevant — …) form as an option, not a verdict.
        _write_state(tmp_path, _GATE_OPEN)
        _run("coverage-scaffold", tmp_path, "--apply")
        body = (tmp_path / ".prawduct" / "artifacts" / "data-model.md").read_text()
        assert "Unwritten stub" in body
        assert "not relevant" in body.lower()  # offered as an option
        assert "# Data Model" in body  # a real, fillable heading

    def test_apply_never_overwrites_existing(self, tmp_path):
        # An authored artifact is excluded from the missing set upstream, so
        # scaffold never touches it: not created, content preserved. The absent
        # siblings ARE created.
        _write_state(tmp_path, _GATE_OPEN)
        _write_artifact(tmp_path, "data-model.md", "# Data Model\n\nreal content\n")
        result = _run("coverage-scaffold", tmp_path, "--apply", "--json")
        data = json.loads(result.stdout)
        assert "data-model.md" not in data["created"]
        assert "security-model.md" in data["created"]
        assert (tmp_path / ".prawduct" / "artifacts" / "data-model.md").read_text() == (
            "# Data Model\n\nreal content\n"
        )

    def test_scaffolded_stub_satisfies_coverage(self, tmp_path):
        # The staged transition: after scaffolding, layer 1 is satisfied and the
        # chain advances (here to layer 2 — norms unratified).
        _write_state(tmp_path, _GATE_OPEN)
        _run("coverage-scaffold", tmp_path, "--apply")
        after = json.loads(_run("coverage-status", tmp_path, "--json").stdout)
        assert after["missing_artifacts"] == []
        assert after["active_layer"] == 2

    def test_apply_idempotent(self, tmp_path):
        _write_state(tmp_path, _GATE_OPEN)
        _run("coverage-scaffold", tmp_path, "--apply")
        second = _run("coverage-scaffold", tmp_path, "--apply")
        assert second.returncode == 0
        assert "coverage is satisfied" in second.stdout.lower()
