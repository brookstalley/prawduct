"""Tests for the structural-coverage post-sync advisory probes.

The coverage chain makes *absence* detectable — a strategy-class artifact that was
never created is invisible to the reactive Critic/probe machinery. Layer 1's
``strategy-artifact-missing`` probe fires when an expected artifact file does not
exist. Coverage is satisfied by the file EXISTING, whatever its content: a
deliberate ``(not relevant — <reason>)`` stub is as valid as a full spec, so there
is one mechanism (presence) and no separate decline list. Per probe we drive the
positive fire, silence when the artifact exists (full spec AND bare stub), and
advisory-id stability. A final repo-coupled test asserts the probe FIRES against
THIS repo's committed state — the live-fixture proof the coverage fix exists to
demonstrate (the inverse of the norm suite's zero-fire tripwire): the moment this
repo adds ``data-model.md`` (real or stub), this test flips, which is the forcing
function working as designed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.advisory_store import (
    Codebase,
    ProjectState,
    clear_registry,
    compute_id,
    run_all_probes,
)
from lib import coverage_probes as cp

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


# --- fixtures / helpers -------------------------------------------------------


def _cb(tmp_path) -> Codebase:
    return Codebase(root=tmp_path)


def _state(**scalars) -> ProjectState:
    return ProjectState(dict(scalars))


def _write_artifact(tmp_path, name: str, body: str = "# artifact\n") -> None:
    d = tmp_path / ".prawduct" / "artifacts"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body, encoding="utf-8")


# --- positive fire ------------------------------------------------------------


def test_fires_when_universal_artifact_absent(tmp_path):
    out = cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path))
    assert len(out) == 1
    adv = out[0]
    assert adv.type == "strategy-artifact-missing"
    assert "data-model.md" in adv.trigger_summary
    # the resolution guidance names both paths: author, or record a stub
    assert "not relevant" in adv.trigger_summary
    assert adv.recommended_action == "/prawduct:methodology planning"
    assert adv.priority == "info"


# --- silence: coverage is existence, content is irrelevant --------------------


def test_silent_when_artifact_present(tmp_path):
    for name in cp.UNIVERSAL_ARTIFACTS:
        _write_artifact(tmp_path, name)
    assert cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path)) == []


def test_not_relevant_stub_satisfies_coverage(tmp_path):
    # A one-line "(not relevant)" stub is a valid recorded decision — the probe
    # checks presence, not content; decision quality is the Critic's concern.
    for name in cp.UNIVERSAL_ARTIFACTS:
        _write_artifact(tmp_path, name, "# Security Model\n\n(Not relevant — offline single-file CLI.)\n")
    assert cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path)) == []


def test_empty_stub_file_still_satisfies_coverage(tmp_path):
    # Even an empty file counts — existence is the whole predicate. (A content-quality
    # bar, if wanted, belongs to the Critic, not this probe.)
    for name in cp.UNIVERSAL_ARTIFACTS:
        _write_artifact(tmp_path, name, "")
    assert cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path)) == []


# --- advisory-id stability ----------------------------------------------------


def test_advisory_id_is_stable_and_evidence_is_invariant(tmp_path):
    # evidence must not enumerate the volatile missing set (compute_id hashes it),
    # so the advisory keeps one identity across sessions.
    out = cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path))
    ev = out[0].evidence
    assert "data-model" not in "\n".join(ev)  # specifics live in trigger_summary, not evidence
    id_a = compute_id(cp.FEATURE, out[0].type, cp.PROBE_VERSION, ev)
    id_b = compute_id(cp.FEATURE, out[0].type, cp.PROBE_VERSION, ev)
    assert id_a == id_b
    assert id_a.startswith("structural-coverage-strategy-artifact-missing-")


def test_registered_probe_runs_through_roster(tmp_path):
    cp.register()
    results = run_all_probes(_state(), _cb(tmp_path))
    assert any(c.type == "strategy-artifact-missing" for c in results)
    # feature/probe_version are stamped by the roster from registration
    adv = next(c for c in results if c.type == "strategy-artifact-missing")
    assert adv.feature == cp.FEATURE
    assert adv.probe_version == cp.PROBE_VERSION


# --- dogfood: the live empty fixture ------------------------------------------


def test_fires_against_this_repo_missing_data_model():
    """Live-fixture proof: this repo has no data-model.md, so the coverage probe
    fires here — the reference repo's blind spot, now visible. This is a deliberate
    tripwire: adding data-model.md (a real spec or a (not relevant) stub) flips it,
    which is the forcing function working."""
    out = cp.probe_strategy_artifact_missing(_state(), Codebase(root=REPO_ROOT))
    assert any(c.type == "strategy-artifact-missing" for c in out)
