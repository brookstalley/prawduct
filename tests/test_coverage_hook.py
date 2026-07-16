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

ROOT = Path(__file__).resolve().parent.parent
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
        # Template-default structural (all null) → layer 0 owns the nudge.
        _write_state(tmp_path, _ALL_NULL)
        result = _run("coverage-status", tmp_path, "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["structural_recorded"] is False
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
        result = _run("coverage-status", tmp_path)
        assert result.returncode == 0
        assert "Layer 0" in result.stdout
        assert "Active nudge → Layer 0" in result.stdout


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
