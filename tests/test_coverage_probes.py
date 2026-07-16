"""Tests for the structural-coverage post-sync advisory probes.

The coverage chain makes *absence* detectable — a strategy-class artifact that was
never created is invisible to the reactive Critic/probe machinery. Layer 1's
``strategy-artifact-missing`` probe fires when an expected artifact file does not
exist. The expectation table is the seven strategy-class artifacts: five
*universal* (always expected) and two *characteristic-triggered* (api-contract ←
``exposes_programmatic_interface``; architecture ← ``multi_process_distributed``),
required only when the characteristic is recorded present in
``classification.structural``. Coverage is satisfied by the file EXISTING, whatever
its content: a deliberate ``(not relevant — <reason>)`` stub is as valid as a full
spec, so there is one mechanism (presence) and no separate decline list. A final
repo-coupled test asserts the probe FIRES against THIS repo's committed state — the
live-fixture proof the coverage fix exists to demonstrate (the inverse of the norm
suite's zero-fire tripwire): the moment this repo adds ``data-model.md`` (real or
stub), that test flips, which is the forcing function working as designed.
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


def _state() -> ProjectState:
    # ProjectState is a top-level-scalar view; the triggered arms read the raw
    # project-state.yaml on disk (nested classification.structural), so tests
    # drive them via _write_state, not this object.
    return ProjectState({})


def _write_artifact(tmp_path, name: str, body: str = "# artifact\n") -> None:
    d = tmp_path / ".prawduct" / "artifacts"
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(body, encoding="utf-8")


def _write_all_universal(tmp_path) -> None:
    for name in cp.UNIVERSAL_ARTIFACTS:
        _write_artifact(tmp_path, name)


def _structural_body(characteristics: dict) -> str:
    """Render a ``classification.structural`` block. Each value is either ``None``
    (the ``null`` sentinel), a ``dict`` (a nested attribute block → recorded
    present), or a scalar string (``true`` / ``false`` / …)."""
    lines = []
    for key, value in characteristics.items():
        if value is None:
            lines.append(f"    {key}: null")
        elif isinstance(value, dict):
            lines.append(f"    {key}:")
            for k, v in value.items():
                lines.append(f"      {k}: {v}")
        else:
            lines.append(f"    {key}: {value}")
    return "\n".join(lines)


def _write_state(tmp_path, characteristics: dict | None = None) -> None:
    """Write a realistic project-state.yaml whose classification.structural block
    records ``characteristics``. Sibling keys around the block (domain,
    domain_characteristics, risk_profile) exercise the scanner's boundary logic."""
    body = _structural_body(characteristics or {})
    content = (
        "schema_version: 6\n"
        "classification:\n"
        "  # Product domain.\n"
        "  domain: utility\n"
        "  structural:\n"
        "    # Structural characteristics — architectural facts.\n"
        f"{body}\n"
        "  domain_characteristics: []\n"
        "  risk_profile:\n"
        "    overall: low\n"
    )
    d = tmp_path / ".prawduct"
    d.mkdir(parents=True, exist_ok=True)
    (d / "project-state.yaml").write_text(content, encoding="utf-8")


# --- positive fire: universal -------------------------------------------------


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


def test_lists_all_five_universal_when_none_exist(tmp_path):
    # No narrowing to the common case: every universal artifact appears, not just
    # the first one wired ([[the COMMON / AVAILABLE instance silently narrows the
    # requirement to itself]]).
    out = cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path))
    summary = out[0].trigger_summary
    for name in cp.UNIVERSAL_ARTIFACTS:
        assert name in summary


# --- silence: coverage is existence, content is irrelevant --------------------


def test_silent_when_all_universal_present(tmp_path):
    _write_all_universal(tmp_path)
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


# --- characteristic-triggered arms --------------------------------------------


def test_api_contract_required_when_interface_recorded(tmp_path):
    # exposes_programmatic_interface recorded (nested block) + api-contract absent
    # → the triggered arm fires, annotated with the characteristic that requires it.
    _write_all_universal(tmp_path)
    _write_state(tmp_path, {"exposes_programmatic_interface": {"consumers": "external"}})
    out = cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path))
    assert len(out) == 1
    summary = out[0].trigger_summary
    assert "api-contract.md" in summary
    assert "exposes_programmatic_interface" in summary
    assert "architecture.md" not in summary  # its characteristic is unrecorded


def test_architecture_required_when_multi_process_recorded(tmp_path):
    _write_all_universal(tmp_path)
    _write_state(tmp_path, {"multi_process_distributed": {"topology": "pipeline"}})
    out = cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path))
    assert len(out) == 1
    summary = out[0].trigger_summary
    assert "architecture.md" in summary
    assert "multi_process_distributed" in summary
    assert "api-contract.md" not in summary


def test_triggered_scalar_true_records_characteristic(tmp_path):
    # A truthy scalar (not only a nested block) records presence.
    _write_all_universal(tmp_path)
    _write_state(tmp_path, {"exposes_programmatic_interface": "true"})
    out = cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path))
    assert len(out) == 1
    assert "api-contract.md" in out[0].trigger_summary


def test_triggered_silent_when_characteristic_null(tmp_path):
    # Unrecorded (template null) → the triggered artifact is NOT required; that gap
    # (uncaptured characteristics) is layer 0's nudge, not this probe's.
    _write_all_universal(tmp_path)
    _write_state(tmp_path, {"exposes_programmatic_interface": None, "multi_process_distributed": None})
    assert cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path)) == []


def test_triggered_silent_when_characteristic_false(tmp_path):
    # An explicit negative records "not this characteristic" → artifact not required.
    _write_all_universal(tmp_path)
    _write_state(tmp_path, {"exposes_programmatic_interface": "false"})
    assert cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path)) == []


def test_triggered_silent_when_artifact_present(tmp_path):
    # Characteristic recorded but the artifact exists (even a stub) → silent.
    _write_all_universal(tmp_path)
    _write_artifact(tmp_path, "api-contract.md", "# API Contract\n\n(Not relevant — internal only.)\n")
    _write_state(tmp_path, {"exposes_programmatic_interface": {"consumers": "internal"}})
    assert cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path)) == []


def test_triggered_silent_when_no_structural_block(tmp_path):
    # No classification block at all (this repo's shape) → nothing recorded → the
    # triggered arms stay silent; only universal absence can fire.
    _write_all_universal(tmp_path)
    (tmp_path / ".prawduct").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".prawduct" / "project-state.yaml").write_text(
        "schema_version: 6\nproduct_identity:\n  name: x\n", encoding="utf-8"
    )
    assert cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path)) == []


# --- the structural-characteristic scanner (unit) -----------------------------


def test_structural_recorded_reads_nested_and_scalar(tmp_path):
    _write_state(
        tmp_path,
        {
            "has_human_interface": None,
            "exposes_programmatic_interface": {"consumers": "external"},
            "multi_process_distributed": "true",
        },
    )
    cb = _cb(tmp_path)
    assert cp._structural_recorded(cb, "exposes_programmatic_interface") is True
    assert cp._structural_recorded(cb, "multi_process_distributed") is True
    assert cp._structural_recorded(cb, "has_human_interface") is False  # null sentinel
    assert cp._structural_recorded(cb, "handles_sensitive_data") is False  # key absent


def test_structural_recorded_false_on_missing_file(tmp_path):
    # No project-state.yaml → unreadable → fail toward silence.
    assert cp._structural_recorded(_cb(tmp_path), "exposes_programmatic_interface") is False


def test_structural_recorded_ignores_matching_comment_text(tmp_path):
    # A comment mentioning the characteristic name must not be read as a set value
    # (the template carries exactly such comment lines above each key).
    (tmp_path / ".prawduct").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".prawduct" / "project-state.yaml").write_text(
        "classification:\n"
        "  structural:\n"
        "    # exposes_programmatic_interface: consumers internal|external|both\n"
        "    exposes_programmatic_interface: null\n",
        encoding="utf-8",
    )
    assert cp._structural_recorded(_cb(tmp_path), "exposes_programmatic_interface") is False


# --- breadth: all seven, no narrowing -----------------------------------------


def test_all_seven_strategy_class_covered_when_everything_missing(tmp_path):
    # Every characteristic recorded, no artifacts present → the missing set is all
    # seven strategy-class artifacts. Guards against a triggered arm silently
    # narrowing to the universal common case.
    _write_state(
        tmp_path,
        {
            "exposes_programmatic_interface": {"consumers": "external"},
            "multi_process_distributed": {"topology": "microservices"},
        },
    )
    out = cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path))
    assert len(out) == 1
    summary = out[0].trigger_summary
    for name in cp.STRATEGY_CLASS_ARTIFACTS:
        assert name in summary
    assert len(cp.STRATEGY_CLASS_ARTIFACTS) == 7


def test_strategy_class_set_is_union_and_deduped_across_modules():
    # The list lives in ONE place: norm_probes imports it, not transcribes it.
    from lib import norm_probes

    expected = set(cp.UNIVERSAL_ARTIFACTS) | {name for name, _ in cp.TRIGGERED_ARTIFACTS}
    assert set(cp.STRATEGY_CLASS_ARTIFACTS) == expected
    assert len(cp.STRATEGY_CLASS_ARTIFACTS) == len(set(cp.STRATEGY_CLASS_ARTIFACTS))  # no dupes
    assert norm_probes.STRATEGY_CLASS_ARTIFACTS is cp.STRATEGY_CLASS_ARTIFACTS  # same object


# --- advisory-id stability ----------------------------------------------------


def test_advisory_id_is_stable_and_evidence_is_invariant(tmp_path):
    # evidence must not enumerate the volatile missing set (compute_id hashes it),
    # so the advisory keeps one identity across sessions and as the set shrinks.
    out = cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path))
    ev = out[0].evidence
    assert "data-model" not in "\n".join(ev)  # specifics live in trigger_summary, not evidence
    id_a = compute_id(cp.FEATURE, out[0].type, cp.PROBE_VERSION, ev)
    id_b = compute_id(cp.FEATURE, out[0].type, cp.PROBE_VERSION, ev)
    assert id_a == id_b
    assert id_a.startswith("structural-coverage-strategy-artifact-missing-")


def test_advisory_id_invariant_across_missing_set(tmp_path):
    # A universal-only fixture and a universal+triggered fixture must yield the
    # SAME advisory id — the missing set is trigger_summary, not evidence.
    id_universal = compute_id(
        cp.FEATURE, "strategy-artifact-missing", cp.PROBE_VERSION,
        cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path))[0].evidence,
    )
    other = tmp_path / "other"
    _write_all_universal(other)
    _write_state(other, {"exposes_programmatic_interface": {"consumers": "external"}})
    id_triggered = compute_id(
        cp.FEATURE, "strategy-artifact-missing", cp.PROBE_VERSION,
        cp.probe_strategy_artifact_missing(_state(), _cb(other))[0].evidence,
    )
    assert id_universal == id_triggered


def test_registered_probe_runs_through_roster(tmp_path):
    cp.register()
    results = run_all_probes(_state(), _cb(tmp_path))
    assert any(c.type == "strategy-artifact-missing" for c in results)
    # feature/probe_version are stamped by the roster from registration
    adv = next(c for c in results if c.type == "strategy-artifact-missing")
    assert adv.feature == cp.FEATURE
    assert adv.probe_version == cp.PROBE_VERSION


# --- dogfood: the live empty fixture ------------------------------------------


def test_fires_exactly_once_against_this_repo_composed_with_all_families():
    """Live-fixture proof: this repo has no strategy-class artifacts, so the
    coverage probe fires here — the reference repo's blind spot, now visible.
    Composed with the full probe roster (mirroring bin/prawduct-hook cmd_clear),
    it emits EXACTLY ONE strategy-artifact-missing advisory (not a churn), and its
    characteristics are unrecorded so only the universal arms contribute. This is a
    deliberate tripwire: adding data-model.md (a real spec or a (not relevant)
    stub) shrinks the list, and filling every strategy-class artifact flips the
    test, which is the forcing function working."""
    from lib.backlog_probes import register as reg_backlog
    from lib.upstream_probes import register as reg_upstream
    from lib.api_versioning_probes import register as reg_api
    from lib.gitignore_probes import register as reg_gitignore
    from lib.norm_probes import register as reg_norm

    reg_backlog()
    reg_upstream()
    reg_api()
    reg_gitignore()
    reg_norm()
    cp.register()

    codebase = Codebase(root=REPO_ROOT)
    results = run_all_probes(_state(), codebase)
    coverage_hits = [c for c in results if c.type == "strategy-artifact-missing"]
    assert len(coverage_hits) == 1
    summary = coverage_hits[0].trigger_summary
    assert "data-model.md" in summary
    # This repo records no structural characteristics, so the triggered arms stay
    # silent — only the universal artifacts drive the nudge.
    assert "(required" not in summary
