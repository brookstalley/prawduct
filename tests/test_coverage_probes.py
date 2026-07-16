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
(discovery-not-captured, emitted from ``bin/prawduct-hook``, exercised in
``test_discovery_capture_nudge``) — owns it, and this probe holds back so exactly one
layer nudges. THIS repo is in that pre-capture state (no ``classification.structural``
block), so the layer-1 probe is SILENT here — the coverage nudge for this repo is
layer 0's. Once characteristics are recorded the probe takes over; the final
repo-coupled test pins the silence, and it flips the moment this repo records its
characteristics (the staged transition Chunk 05 dogfoods).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Self-sufficient on sys.path — don't depend on another test module having
# inserted the repo root first (under parallel file distribution a worker may run
# only lib-importing files that all assume it, and none inserts it). Mirrors the
# idiom in tests/test_advisory_store.py / test_advisory_cmd.py.
_REPO_ROOT = Path(__file__).resolve().parent.parent
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


# --- dogfood: the live pre-capture fixture ------------------------------------


def test_layer1_silent_against_this_repo_pending_structural_capture():
    """Live-fixture proof of the staging: THIS repo records no structural
    characteristics (no ``classification.structural`` block), so layer 1 is SILENT
    here — the coverage nudge for this repo is layer 0's (discovery-not-captured,
    tested in ``test_discovery_capture_nudge``). Composed with the full probe roster
    (mirroring bin/prawduct-hook cmd_clear) it emits ZERO strategy-artifact-missing
    advisories. This is a deliberate staged tripwire: the moment this repo records
    its characteristics (the Chunk 05 dogfood), layer 0 clears and this flips to
    firing the missing universal artifacts — the forcing function advancing one
    staged nudge at a time."""
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

    # Guard the premise: if this repo ever records a structural characteristic, the
    # staging flips and this test's expectation must be revisited (fail loud here,
    # not silently pass on a stale premise).
    assert cp.structural_characteristics_recorded(
        REPO_ROOT / ".prawduct" / "project-state.yaml"
    ) is False, "this repo now records structural characteristics — layer 1 staging flips; update this dogfood"

    codebase = Codebase(root=REPO_ROOT)
    results = run_all_probes(_state(), codebase)
    coverage_hits = [c for c in results if c.type == "strategy-artifact-missing"]
    assert coverage_hits == []


# --- staging: exactly one layer speaks per fixture ----------------------------
# The three layers stage on the shared structural-recorded boundary and layer 2's
# artifact-existence gate: layer 0 (discovery-not-captured) owns "characteristics
# unrecorded"; layer 1 (this probe) owns "recorded, artifacts missing"; layer 2
# (norm-registry-unratified) owns "artifacts exist, norms unratified". On a fixture
# sitting cleanly at one stage, exactly that layer fires — no double-nag.


def _write_code(tmp_path) -> None:
    (tmp_path / "app.py").write_text("print('hi')\n", encoding="utf-8")


def _layer0_fires(tmp_path) -> bool:
    # The hook's layer-0 fire decision (bin/prawduct-hook), evaluated on its inputs.
    from lib import gitstate

    sp = _state_path(tmp_path)
    return bool(
        sp.is_file()
        and gitstate._has_product_definition_work(tmp_path)
        and not cp.structural_characteristics_recorded(sp)
    )


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
