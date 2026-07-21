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
spec, so there is one mechanism (presence) and no separate decline list.

**Staging (layer 0 vs layer 1).** The whole probe stays silent until the product
records at least one structural characteristic
(:func:`~lib.coverage_probes.structural_characteristics_recorded`). Until then the
product has not told governance what it *is*, so the upstream nudge — layer 0
(:func:`~lib.coverage_probes.probe_discovery_not_captured`, an advisory-store probe;
hook wiring exercised in ``test_discovery_capture_nudge``) — owns it, and this probe
holds back so exactly one layer nudges. The staged layer-0 → layer-1 transition is pinned by a fixture-based
before/after test on prawduct's own reconciled structural profile (the reference
product dogfooding this chain), kept decoupled from the live ``project-state.yaml``
so the proof re-runs whatever this repo records — an earlier repo-coupled zero-fire
assertion tied the test to the live pre-capture state and broke the moment that
state advanced.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Self-sufficient on sys.path — don't depend on another test module having
# inserted the repo root first (under parallel file distribution a worker may run
# only lib-importing files that all assume it, and none inserts it). Mirrors the
# idiom in tests/test_advisory_store.py / test_advisory_cmd.py.
_REPO_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.advisory_store import (  # noqa: E402
    Codebase,
    ProjectState,
    clear_registry,
    compute_id,
    run_all_probes,
)
from lib import coverage_probes as cp  # noqa: E402


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


# ``has_human_interface`` is a NON-triggered characteristic (it implies no specific
# strategy artifact), so recording it opens the staging gate — the probe now
# speaks — without contributing a triggered arm to the missing set. The universal
# arms are what fire, in isolation, on top of it.
_GATE_OPEN = {"has_human_interface": {"modality": "terminal"}}


def _open_gate(tmp_path, extra: dict | None = None) -> None:
    """Write a state that records >=1 structural characteristic so the layer-1
    staging gate is open. ``extra`` records additional characteristics on top."""
    chars = dict(_GATE_OPEN)
    if extra:
        chars.update(extra)
    _write_state(tmp_path, chars)


# --- positive fire: universal (staging gate open) -----------------------------


def test_fires_when_universal_artifact_absent(tmp_path):
    _open_gate(tmp_path)
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
    _open_gate(tmp_path)
    out = cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path))
    summary = out[0].trigger_summary
    for name in cp.UNIVERSAL_ARTIFACTS:
        assert name in summary


# --- silence: coverage is existence, content is irrelevant --------------------
# (gate open in each — these isolate the existence predicate, not the staging gate)


def test_silent_when_all_universal_present(tmp_path):
    _open_gate(tmp_path)
    _write_all_universal(tmp_path)
    assert cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path)) == []


def test_not_relevant_stub_satisfies_coverage(tmp_path):
    # A one-line "(not relevant)" stub is a valid recorded decision — the probe
    # checks presence, not content; decision quality is the Critic's concern.
    _open_gate(tmp_path)
    for name in cp.UNIVERSAL_ARTIFACTS:
        _write_artifact(tmp_path, name, "# Security Model\n\n(Not relevant — offline single-file CLI.)\n")
    assert cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path)) == []


def test_empty_stub_file_still_satisfies_coverage(tmp_path):
    # Even an empty file counts — existence is the whole predicate. (A content-quality
    # bar, if wanted, belongs to the Critic, not this probe.)
    _open_gate(tmp_path)
    for name in cp.UNIVERSAL_ARTIFACTS:
        _write_artifact(tmp_path, name, "")
    assert cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path)) == []


# --- staging gate: layer 1 stays silent until structural characteristics recorded


def test_silent_when_no_structural_recorded_even_with_universal_missing(tmp_path):
    # THE staging gate: universal artifacts are absent, but no structural
    # characteristic is recorded, so layer 0 owns the nudge and this probe holds
    # back — no double-nag. (Distinct from "all present" silence above: here the
    # artifacts are MISSING and the probe is still silent.)
    assert cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path)) == []  # no state file at all


def test_silent_when_structural_block_all_null(tmp_path):
    # Template-default structural (every characteristic null) reads as unrecorded —
    # the never-captured state layer 0 owns.
    _write_state(tmp_path, {c: None for c in cp.STRUCTURAL_CHARACTERISTICS})
    assert cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path)) == []


def test_fires_once_structural_recorded_and_universal_missing(tmp_path):
    # Gate opens the moment one characteristic is recorded — then the missing
    # universal artifacts fire (the layer-0 → layer-1 transition Chunk 05 dogfoods).
    _open_gate(tmp_path)
    out = cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path))
    assert len(out) == 1
    assert "data-model.md" in out[0].trigger_summary


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
    # Gate open (has_human_interface recorded), but the triggered characteristics
    # are null → their artifacts are NOT required; that gap is layer 0's, not this
    # arm's. (Gate opened via a non-triggered characteristic so this isolates
    # triggered-arm silence from the staging gate.)
    _write_all_universal(tmp_path)
    _open_gate(tmp_path, {"exposes_programmatic_interface": None, "multi_process_distributed": None})
    assert cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path)) == []


def test_triggered_silent_when_characteristic_false(tmp_path):
    # An explicit negative records "not this characteristic" → artifact not required.
    _write_all_universal(tmp_path)
    _open_gate(tmp_path, {"exposes_programmatic_interface": "false"})
    assert cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path)) == []


def test_triggered_silent_when_artifact_present(tmp_path):
    # Characteristic recorded but the artifact exists (even a stub) → silent.
    _write_all_universal(tmp_path)
    _write_artifact(tmp_path, "api-contract.md", "# API Contract\n\n(Not relevant — internal only.)\n")
    _write_state(tmp_path, {"exposes_programmatic_interface": {"consumers": "internal"}})
    assert cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path)) == []


def test_silent_when_no_structural_block_present(tmp_path):
    # No classification block at all (THIS repo's shape) → nothing recorded → the
    # staging gate holds the whole probe back (even the universal arms), because
    # layer 0 owns a product that has not yet recorded what it is.
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


# --- the shared staging predicate (layer-0 / layer-1 boundary) -----------------


def _state_path(tmp_path) -> Path:
    return tmp_path / ".prawduct" / "project-state.yaml"


def test_characteristics_recorded_true_when_any_present(tmp_path):
    # >=1 present (a non-triggered one here) → recorded → gate open.
    _write_state(tmp_path, {"has_human_interface": {"modality": "terminal"}})
    assert cp.structural_characteristics_recorded(_state_path(tmp_path)) is True


def test_characteristics_recorded_false_when_all_null(tmp_path):
    # Template default (every characteristic null) → unrecorded → layer 0 owns it.
    _write_state(tmp_path, {c: None for c in cp.STRUCTURAL_CHARACTERISTICS})
    assert cp.structural_characteristics_recorded(_state_path(tmp_path)) is False


def test_characteristics_recorded_false_when_block_absent(tmp_path):
    # No classification block at all (this repo's shape) → unrecorded.
    (tmp_path / ".prawduct").mkdir(parents=True, exist_ok=True)
    _state_path(tmp_path).write_text(
        "schema_version: 6\nproduct_identity:\n  name: x\n", encoding="utf-8"
    )
    assert cp.structural_characteristics_recorded(_state_path(tmp_path)) is False


def test_characteristics_recorded_false_when_file_missing(tmp_path):
    # No project-state.yaml → unreadable → fail toward silence (layer 0 guards
    # is_file() separately; the predicate must not raise).
    assert cp.structural_characteristics_recorded(_state_path(tmp_path)) is False


def test_characteristics_recorded_covers_all_six(tmp_path):
    # Every one of the six characteristics, recorded alone, opens the gate — no
    # narrowing to only the two triggered ones.
    for characteristic in cp.STRUCTURAL_CHARACTERISTICS:
        _write_state(tmp_path, {characteristic: "true"})
        assert cp.structural_characteristics_recorded(_state_path(tmp_path)) is True, characteristic
    assert len(cp.STRUCTURAL_CHARACTERISTICS) == 6


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


# --- the shared expectation-table helper (missing_expected_artifacts) ----------
# One answer to "what does this product owe?", consumed by the probe, the
# coverage-status doctor check, and the coverage-scaffold helper (single-homed).


def test_missing_expected_lists_universal_when_none_recorded(tmp_path):
    # Independent of the staging gate: with no characteristic recorded, the five
    # universal artifacts are still the expected-and-absent set (the scaffold can
    # offer them pre-capture), and no triggered arm (characteristics unrecorded).
    _write_state(tmp_path, {c: None for c in cp.STRUCTURAL_CHARACTERISTICS})
    out = cp.missing_expected_artifacts(_cb(tmp_path))
    assert [name for name, _ in out] == list(cp.UNIVERSAL_ARTIFACTS)
    assert all(characteristic is None for _, characteristic in out)


def test_missing_expected_adds_triggered_when_recorded(tmp_path):
    # A recorded characteristic adds its triggered artifact, annotated, AFTER the
    # universal ones (stable order for every consumer).
    _write_state(tmp_path, {"exposes_programmatic_interface": {"consumers": "external"}})
    out = cp.missing_expected_artifacts(_cb(tmp_path))
    assert [name for name, _ in out] == list(cp.UNIVERSAL_ARTIFACTS) + ["api-contract.md"]
    assert out[-1] == ("api-contract.md", "exposes_programmatic_interface")


def test_missing_expected_empty_when_all_present(tmp_path):
    _open_gate(tmp_path)
    _write_all_universal(tmp_path)
    assert cp.missing_expected_artifacts(_cb(tmp_path)) == []


def test_missing_expected_excludes_present_files(tmp_path):
    # Present files (spec or stub) drop out of the missing set; absent ones remain.
    _write_state(tmp_path, {"exposes_programmatic_interface": {"consumers": "external"}})
    _write_artifact(tmp_path, "data-model.md")
    _write_artifact(tmp_path, "api-contract.md")
    names = [name for name, _ in cp.missing_expected_artifacts(_cb(tmp_path))]
    assert "data-model.md" not in names and "api-contract.md" not in names
    assert "security-model.md" in names


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
    _open_gate(tmp_path)
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
    _open_gate(tmp_path)
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
    _open_gate(tmp_path)
    cp.register()
    results = run_all_probes(_state(), _cb(tmp_path))
    assert any(c.type == "strategy-artifact-missing" for c in results)
    # feature/probe_version are stamped by the roster from registration
    adv = next(c for c in results if c.type == "strategy-artifact-missing")
    assert adv.feature == cp.FEATURE
    assert adv.probe_version == cp.PROBE_VERSION


# --- dogfood: prawduct's own staged transition (fixture, not live-coupled) -----

# Prawduct's reconciled structural profile (methodology/discovery.md § Reconciling
# an Existing Product): four characteristics recorded present, two absent. Kept as a
# fixture — a decoupled copy of what the live project-state.yaml records — so the
# transition proof re-runs regardless of the live file. Both triggered arms are lit
# (api-contract ← exposes_programmatic_interface, architecture ←
# multi_process_distributed), so prawduct owes the full seven-artifact set.
_PRAWDUCT_PROFILE = {
    "has_human_interface": {"modality": "terminal", "platform": "cross-platform"},
    "runs_unattended": {"trigger": "event-driven"},
    "exposes_programmatic_interface": {"consumers": "both"},
    "has_multiple_party_types": None,
    "handles_sensitive_data": None,
    "multi_process_distributed": {"topology": "monolith-with-workers"},
}


def test_prawduct_profile_stages_layer0_to_layer1(tmp_path):
    """The staged transition dogfooded on prawduct's OWN reconciled profile.

    BEFORE — characteristics unrecorded (template-default null): layer 1 holds back,
    the nudge is layer 0's (discovery-not-captured, tested in
    ``test_discovery_capture_nudge``). AFTER — prawduct's profile recorded: layer 0
    clears and layer 1 names exactly the seven strategy-class artifacts — the five
    universal plus both triggered arms, because prawduct records both triggering
    characteristics. Fixture-based on purpose: the earlier form asserted this repo's
    live pre-capture state and broke the moment that state advanced.
    """
    # BEFORE: all-null structural → unrecorded → layer 1 silent (layer 0 owns it).
    _write_state(tmp_path, {c: None for c in cp.STRUCTURAL_CHARACTERISTICS})
    assert cp.structural_characteristics_recorded(_state_path(tmp_path)) is False
    assert cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path)) == []

    # AFTER: prawduct's profile recorded → layer 0 clears, layer 1 names all seven.
    _write_state(tmp_path, _PRAWDUCT_PROFILE)
    assert cp.structural_characteristics_recorded(_state_path(tmp_path)) is True
    out = cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path))
    assert len(out) == 1
    summary = out[0].trigger_summary
    for name in cp.STRATEGY_CLASS_ARTIFACTS:
        assert name in summary
    # both triggered arms fire, each annotated with the characteristic that requires it
    assert "api-contract.md (required — exposes_programmatic_interface recorded)" in summary
    assert "architecture.md (required — multi_process_distributed recorded)" in summary
    assert len(cp.STRATEGY_CLASS_ARTIFACTS) == 7


# --- staging: exactly one layer speaks per fixture ----------------------------
# The three layers stage on the shared structural-recorded boundary and layer 2's
# artifact-existence gate: layer 0 (discovery-not-captured) owns "characteristics
# unrecorded"; layer 1 (this probe) owns "recorded, artifacts missing"; layer 2
# (norm-registry-unratified) owns "artifacts exist, norms unratified". On a fixture
# sitting cleanly at one stage, exactly that layer fires — no double-nag.


def _write_code(tmp_path) -> None:
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")


def _layer0_fires(tmp_path) -> bool:
    # The real layer-0 probe (advisory-store delivery), not a re-derived predicate.
    return cp.probe_discovery_not_captured(_state(), _cb(tmp_path)) != []


def _layer1_fires(tmp_path) -> bool:
    return cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path)) != []


def _layer2_fires(tmp_path) -> bool:
    from lib import norm_probes

    return norm_probes.probe_norm_registry_unratified(_state(), _cb(tmp_path)) != []


def test_stage_layer0_only_when_characteristics_unrecorded(tmp_path):
    # Product work + domain filled but no structural characteristic recorded, no
    # artifacts → only layer 0.
    _write_code(tmp_path)
    _write_state(tmp_path, {c: None for c in cp.STRUCTURAL_CHARACTERISTICS})
    assert (_layer0_fires(tmp_path), _layer1_fires(tmp_path), _layer2_fires(tmp_path)) == (True, False, False)


def test_stage_layer1_only_when_recorded_and_artifacts_missing(tmp_path):
    # Structural recorded (gate open), no strategy artifacts → only layer 1. Layer 2
    # is silent because no strategy-class artifact exists yet (its existence gate).
    _write_code(tmp_path)
    _open_gate(tmp_path)
    assert (_layer0_fires(tmp_path), _layer1_fires(tmp_path), _layer2_fires(tmp_path)) == (False, True, False)


def test_stage_layer2_only_when_artifacts_exist_unratified(tmp_path):
    # Structural recorded + every expected artifact present (so layer 1 is silent) +
    # no `## Direction` anywhere → only layer 2 (ratify the norms).
    _write_code(tmp_path)
    _open_gate(tmp_path)  # has_human_interface → expected set is the 5 universal
    _write_all_universal(tmp_path)  # stubs, no Direction sections
    assert (_layer0_fires(tmp_path), _layer1_fires(tmp_path), _layer2_fires(tmp_path)) == (False, False, True)


def test_layer1_and_layer2_overlap_during_partial_authoring(tmp_path):
    # The honest limit of "one nudge at a time": layer 2's gate is INDEPENDENT (any
    # strategy artifact exists + registry unratified), so it does NOT wait for layer 1
    # to clear. While authoring is partial — one strategy artifact written, the rest
    # still owed, no `## Direction` yet — layer 1 (author the rest) and layer 2 (ratify
    # what exists) BOTH speak: two distinct asks, not a double-nag on one. Only the
    # 0↔1 boundary is an exact complement (docs/norms.md § Structural-coverage staging).
    _write_code(tmp_path)
    _open_gate(tmp_path)  # characteristics recorded → layer 0 clears
    _write_artifact(tmp_path, "security-model.md", "# Security Model\n\nProse, no Direction.\n")
    assert (_layer0_fires(tmp_path), _layer1_fires(tmp_path), _layer2_fires(tmp_path)) == (False, True, True)


# --- indent tolerance: recorded is recorded, whatever the step width -----------
# The scanner tracks the file's OWN indent levels (first child level under
# classification:, first key level under structural:) instead of hard-coding the
# template's 2/4-space steps. The failure this pins: a reformatted-but-recorded
# state reading as "unrecorded" would fire the layer-0 discovery advisory forever
# on a repo whose owner already answered.


def _write_state_reindented(tmp_path, step: int) -> None:
    """A recorded state using ``step``-space indentation throughout."""
    i1, i2, i3 = " " * step, " " * (2 * step), " " * (3 * step)
    content = (
        "schema_version: 6\n"
        "classification:\n"
        f"{i1}domain: utility\n"
        f"{i1}structural:\n"
        f"{i2}has_human_interface:\n"
        f"{i3}modality: terminal\n"
        f"{i2}runs_unattended: null\n"
        f"{i2}exposes_programmatic_interface: true\n"
        f"{i1}risk_profile:\n"
        f"{i2}overall: low\n"
    )
    d = tmp_path / ".prawduct"
    d.mkdir(parents=True, exist_ok=True)
    (d / "project-state.yaml").write_text(content, encoding="utf-8")


@pytest.mark.parametrize("step", [2, 3, 4])
def test_structural_recorded_tolerates_indent_width(tmp_path, step):
    _write_state_reindented(tmp_path, step)
    sp = _state_path(tmp_path)
    assert cp.structural_characteristics_recorded(sp) is True
    # nested-block form and scalar form both read as present at any width
    assert cp._structural_recorded_at(sp, "has_human_interface") is True
    assert cp._structural_recorded_at(sp, "exposes_programmatic_interface") is True
    # explicit null still reads as absent at any width
    assert cp._structural_recorded_at(sp, "runs_unattended") is False
    # keys outside structural (risk_profile children) never leak in
    assert cp._structural_recorded_at(sp, "overall") is False


def test_absent_values_include_zero(tmp_path):
    # `exposes_programmatic_interface: 0` is an explicit negative, not a recorded
    # presence — it must not require an api-contract.
    _write_state(tmp_path, {"exposes_programmatic_interface": "0", "has_human_interface": {"modality": "terminal"}})
    out = cp.probe_strategy_artifact_missing(_state(), _cb(tmp_path))
    assert len(out) == 1
    assert "api-contract.md" not in out[0].trigger_summary


# --- layer 0 probe: discovery-not-captured (advisory delivery) -----------------


def _write_docs(tmp_path) -> None:
    d = tmp_path / "docs"
    d.mkdir(exist_ok=True)
    (d / "vision.md").write_text("# Vision\n", encoding="utf-8")


def test_layer0_probe_fires_on_unrecorded_with_work(tmp_path):
    _write_code(tmp_path)
    _write_state(tmp_path, {c: None for c in cp.STRUCTURAL_CHARACTERISTICS})
    out = cp.probe_discovery_not_captured(_state(), _cb(tmp_path))
    assert len(out) == 1
    adv = out[0]
    assert adv.type == "discovery-not-captured"
    assert adv.priority == "warn"
    assert "DISCOVERY NOT CAPTURED" in adv.trigger_summary
    assert adv.recommended_action == "/prawduct:methodology discovery"


def test_layer0_probe_silent_without_product_work(tmp_path):
    # A just-scaffolded repo (state file, no code, no docs) is not nagged.
    _write_state(tmp_path, {c: None for c in cp.STRUCTURAL_CHARACTERISTICS})
    assert cp.probe_discovery_not_captured(_state(), _cb(tmp_path)) == []


def test_layer0_probe_silent_without_state_file(tmp_path):
    # No project-state.yaml at all → not a prawduct repo in the relevant sense;
    # fail toward silence (the onboarding path owns that case).
    _write_code(tmp_path)
    assert cp.probe_discovery_not_captured(_state(), _cb(tmp_path)) == []


def test_layer0_probe_silent_once_recorded(tmp_path):
    _write_code(tmp_path)
    _open_gate(tmp_path)
    assert cp.probe_discovery_not_captured(_state(), _cb(tmp_path)) == []


def test_layer0_probe_docs_only_work_counts(tmp_path):
    # Docs-first products (no code yet) still get the nudge — the exact phase the
    # code-gated project-preferences CRITICAL is blind to.
    _write_docs(tmp_path)
    _write_state(tmp_path, {c: None for c in cp.STRUCTURAL_CHARACTERISTICS})
    assert len(cp.probe_discovery_not_captured(_state(), _cb(tmp_path))) == 1


def test_layer0_probe_id_stable_across_variants(tmp_path):
    # Both message variants share one advisory identity (fixed evidence), so a
    # dismissal survives the state evolving from never-ran to structural-only.
    _write_code(tmp_path)
    never_ran = (
        "classification:\n  domain: null\nproduct_definition:\n  vision: null\n"
    )
    d = tmp_path / ".prawduct"
    d.mkdir(parents=True, exist_ok=True)
    (d / "project-state.yaml").write_text(never_ran, encoding="utf-8")
    (first,) = cp.probe_discovery_not_captured(_state(), _cb(tmp_path))
    _write_state(tmp_path, {c: None for c in cp.STRUCTURAL_CHARACTERISTICS})
    (second,) = cp.probe_discovery_not_captured(_state(), _cb(tmp_path))
    assert first.evidence == second.evidence
    assert first.trigger_summary != second.trigger_summary


def test_layer0_probe_registered_in_roster(tmp_path):
    _write_code(tmp_path)
    _write_state(tmp_path, {c: None for c in cp.STRUCTURAL_CHARACTERISTICS})
    cp.register()
    results = run_all_probes(_state(), _cb(tmp_path))
    assert any(c.type == "discovery-not-captured" for c in results)
    # staging: the layer-1 probe held back while layer 0 speaks
    assert not any(c.type == "strategy-artifact-missing" for c in results)
