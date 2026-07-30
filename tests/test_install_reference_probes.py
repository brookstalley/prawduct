"""Tests for the committed install-reference contract-drift probe.

Two inert states carry as much weight as the firing one, so all three are
first-class here: a repo matching the contract says nothing, a repo with **no**
prawduct entry says nothing (doctor's Health Check #1 owns absence — a probe
firing there would nag every un-onboarded repo), and a drifted repo fires once.

The load-bearing property is that the contract is *read* from
``migrate_plugin.INSTALL_REFERENCE`` rather than transcribed — pinned by
``test_contract_is_read_not_transcribed``, because a transcribed copy is exactly
how this check would outlive a change to the value prawduct writes. Registry
isolation mirrors ``test_gitignore_probes.py`` (autouse ``clear_registry``).
"""

from __future__ import annotations

import json

import pytest

from lib.advisory_store import (
    Codebase,
    ProjectState,
    clear_registry,
    make_codebase,
    run_all_probes,
)
from lib.migrate_plugin import INSTALL_REFERENCE, install_reference_drift
from lib import install_reference_probes as irp


@pytest.fixture(autouse=True)
def _isolated_registry():
    clear_registry()
    yield
    clear_registry()


def _cb(tmp_path):
    return Codebase(root=tmp_path)


def _write_settings(tmp_path, entry, *, extra_top_level=None):
    """Write ``.claude/settings.json`` with ``entry`` as the prawduct marketplace entry.

    ``entry=None`` writes a settings file with no prawduct entry at all.
    """
    data = dict(extra_top_level or {})
    if entry is not None:
        data["extraKnownMarketplaces"] = {"prawduct": entry}
    d = tmp_path / ".claude"
    d.mkdir(parents=True, exist_ok=True)
    (d / "settings.json").write_text(json.dumps(data, indent=2), encoding="utf-8")


def _contract_entry():
    """A deep copy of the contract's own prawduct entry."""
    return json.loads(json.dumps(INSTALL_REFERENCE["extraKnownMarketplaces"]["prawduct"]))


# --- inert states ------------------------------------------------------------


def test_inert_when_reference_matches_contract(tmp_path):
    _write_settings(tmp_path, _contract_entry())
    assert irp.probe_install_reference_drift(ProjectState({}), _cb(tmp_path)) == []


def test_inert_when_no_prawduct_entry(tmp_path):
    # An un-onboarded repo has nothing to have drifted — absence is doctor's finding.
    _write_settings(tmp_path, None, extra_top_level={"hooks": {}})
    assert irp.probe_install_reference_drift(ProjectState({}), _cb(tmp_path)) == []


def test_inert_when_settings_file_absent(tmp_path):
    assert irp.probe_install_reference_drift(ProjectState({}), _cb(tmp_path)) == []


def test_inert_when_settings_unparseable(tmp_path):
    # A malformed file is not evidence of drift; guessing is how a nudge earns dismissal.
    d = tmp_path / ".claude"
    d.mkdir(parents=True)
    (d / "settings.json").write_text("{ not json", encoding="utf-8")
    assert irp.probe_install_reference_drift(ProjectState({}), _cb(tmp_path)) == []


# --- firing states -----------------------------------------------------------


def test_fires_on_pinned_ref(tmp_path):
    # The observed field condition: a repo pinned to a fixed release ref.
    entry = _contract_entry()
    entry["source"]["ref"] = "v2.1.5"
    _write_settings(tmp_path, entry)
    out = irp.probe_install_reference_drift(ProjectState({}), _cb(tmp_path))
    assert len(out) == 1
    assert out[0].type == "contract-drift"
    assert out[0].recommended_action == "/prawduct:doctor"
    assert "source.ref is 'v2.1.5'" in out[0].trigger_summary
    assert "will not receive framework updates" in out[0].trigger_summary


def test_fires_on_autoupdate_disabled(tmp_path):
    entry = _contract_entry()
    entry["autoUpdate"] = False
    _write_settings(tmp_path, entry)
    out = irp.probe_install_reference_drift(ProjectState({}), _cb(tmp_path))
    assert len(out) == 1
    assert "autoUpdate is False" in out[0].trigger_summary


def test_fires_once_naming_both_drifted_fields(tmp_path):
    # The real-world shape (ref pin + autoUpdate off) is ONE advisory, not two.
    entry = _contract_entry()
    entry["source"]["ref"] = "v2.1.5"
    entry["autoUpdate"] = False
    _write_settings(tmp_path, entry)
    out = irp.probe_install_reference_drift(ProjectState({}), _cb(tmp_path))
    assert len(out) == 1
    assert "source.ref" in out[0].trigger_summary
    assert "autoUpdate" in out[0].trigger_summary


def test_fires_when_ref_key_missing_entirely(tmp_path):
    entry = _contract_entry()
    del entry["source"]["ref"]
    _write_settings(tmp_path, entry)
    out = irp.probe_install_reference_drift(ProjectState({}), _cb(tmp_path))
    assert len(out) == 1
    assert "source.ref is absent" in out[0].trigger_summary


# --- properties --------------------------------------------------------------


def test_evidence_is_drift_set_independent(tmp_path):
    # Evidence is hashed into the advisory id, so it must not carry the specifics —
    # otherwise the id churns when a partial fix repairs one of the two fields.
    entry = _contract_entry()
    entry["source"]["ref"] = "v2.1.5"
    entry["autoUpdate"] = False
    _write_settings(tmp_path, entry)
    both = irp.probe_install_reference_drift(ProjectState({}), _cb(tmp_path))
    entry["autoUpdate"] = True
    _write_settings(tmp_path, entry)
    one = irp.probe_install_reference_drift(ProjectState({}), _cb(tmp_path))
    assert both[0].evidence == one[0].evidence
    assert both[0].trigger_summary != one[0].trigger_summary


def test_evidence_names_the_machine_level_file(tmp_path):
    # The probe sees one end of a two-ended condition (#120). Repairing only the
    # repo can be undone by the machine-level pin, so the advisory must say so.
    entry = _contract_entry()
    entry["source"]["ref"] = "v2.1.5"
    _write_settings(tmp_path, entry)
    out = irp.probe_install_reference_drift(ProjectState({}), _cb(tmp_path))
    assert any("known_marketplaces.json" in e for e in out[0].evidence)


def test_contract_is_read_not_transcribed(tmp_path):
    # Repoint the contract; the drift check must follow it with no edit here.
    entry = _contract_entry()
    _write_settings(tmp_path, entry)
    assert install_reference_drift(tmp_path)["drifted"] == []

    original = INSTALL_REFERENCE["extraKnownMarketplaces"]["prawduct"]["source"]["ref"]
    INSTALL_REFERENCE["extraKnownMarketplaces"]["prawduct"]["source"]["ref"] = "release"
    try:
        drift = install_reference_drift(tmp_path)
        assert [d["field"] for d in drift["drifted"]] == ["source.ref"]
        assert drift["drifted"][0]["expected"] == "release"
        assert drift["drifted"][0]["actual"] == original
    finally:
        INSTALL_REFERENCE["extraKnownMarketplaces"]["prawduct"]["source"]["ref"] = original


def test_drift_reports_present_false_without_entry(tmp_path):
    _write_settings(tmp_path, None)
    assert install_reference_drift(tmp_path) == {"present": False, "drifted": []}


def test_register_runs_in_the_roster(tmp_path):
    entry = _contract_entry()
    entry["source"]["ref"] = "v2.1.5"
    _write_settings(tmp_path, entry)
    irp.register()
    irp.register()  # idempotent — register_probe overwrites
    cands = run_all_probes(ProjectState({}), make_codebase(tmp_path))
    fired = [c for c in cands if c.type == "contract-drift"]
    assert len(fired) == 1
    assert fired[0].feature == "install-reference"
    assert fired[0].probe_version == irp.PROBE_VERSION
