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


_ENABLED_KEY = "prawduct@prawduct"


def _write_settings(tmp_path, entry, *, extra_top_level=None, enabled=True):
    """Write ``.claude/settings.json`` with ``entry`` as the prawduct marketplace entry.

    ``entry=None`` writes a settings file with no prawduct entry at all.
    ``enabled`` is the ``enabledPlugins["prawduct@prawduct"]`` half of the contract:
    ``True`` matches it, ``False`` is governance switched off, ``None`` omits the key.
    It defaults to the contract value so that every test writing a contract entry
    describes a fully contract-satisfying repo — otherwise each would carry an
    unrelated second drift and the inert cases could not be expressed at all.
    """
    data = dict(extra_top_level or {})
    if entry is not None:
        data["extraKnownMarketplaces"] = {"prawduct": entry}
    if enabled is not None:
        data["enabledPlugins"] = {_ENABLED_KEY: enabled}
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
    # The consequence is the clone, not this machine — a configured machine resolves
    # the plugin and the committed entry never gets a vote (measured, #120). Pinned
    # because the overstatement it replaces reads as more urgent and is wrong.
    assert "fresh clone" in out[0].trigger_summary
    assert "will not receive framework updates" not in out[0].trigger_summary


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


def test_evidence_states_the_clone_cost_not_a_machine_coupling(tmp_path):
    # The committed reference and the machine-level file are DECOUPLED — measured
    # in #120, where a repo pinned to v2.1.5 ran a clean v3.2.2 session. So the
    # advisory must not claim a repo-only repair can be undone by the machine (an
    # earlier draft did); it must name the real cost, which is what a fresh clone
    # seeds from. Asserting the consequence and not just the filename is the point:
    # the filename alone also appeared in the wording this replaced.
    entry = _contract_entry()
    entry["source"]["ref"] = "v2.1.5"
    _write_settings(tmp_path, entry)
    out = irp.probe_install_reference_drift(ProjectState({}), _cb(tmp_path))
    # Both claims must ride the SAME line. Two separate any() checks passed while
    # this line still carried the falsified "repairing only this repo can be undone
    # by it" — a *different* line happened to say "clone", so the assertion never
    # reached the one under test. Mutation-checked: reverting this line now fails.
    machine_line = [e for e in out[0].evidence if "known_marketplaces.json" in e]
    assert len(machine_line) == 1
    assert "inert" in machine_line[0]
    assert "clone" in machine_line[0]
    assert "can be undone by it" not in machine_line[0]


def test_contract_is_read_not_transcribed(tmp_path, monkeypatch):
    # Repoint the contract; the drift check must follow it with no edit here.
    # monkeypatch.setitem rather than a try/finally global swap: the restore is
    # registered before the assertions run, so it survives paths a finally block
    # has to be remembered for (an early return, a second mutation added later).
    entry = _contract_entry()
    _write_settings(tmp_path, entry)
    assert install_reference_drift(tmp_path)["drifted"] == []

    source = INSTALL_REFERENCE["extraKnownMarketplaces"]["prawduct"]["source"]
    original = source["ref"]
    monkeypatch.setitem(source, "ref", "release")

    drift = install_reference_drift(tmp_path)
    assert [d["field"] for d in drift["drifted"]] == ["source.ref"]
    assert drift["drifted"][0]["expected"] == "release"
    assert drift["drifted"][0]["actual"] == original


def test_every_contract_leaf_is_compared(tmp_path):
    """Corrupt each contract leaf in turn; each must produce exactly its own drift.

    This is the property the "reads the contract" claim actually rests on, and the
    one a hand-transcribed check cannot hold: the first revision compared
    ``source.ref`` and ``autoUpdate`` only, so ``enabledPlugins`` — governance off
    entirely — and a repointed ``source.repo`` were both silent while the docstring
    claimed parity with ``core.gitignore_contract_drift``. Adding a leaf to
    INSTALL_REFERENCE with no coverage now fails here rather than shipping unchecked.

    Asserting equality (not membership) also pins the converse: corrupting one leaf
    must not report any other as drifted.
    """
    from lib.migrate_plugin import _contract_leaves, _field_label

    leaves = _contract_leaves(INSTALL_REFERENCE)
    assert len(leaves) >= 5, "contract shrank unexpectedly; this test's premise is stale"

    for leaf_path, _expected in leaves:
        data = {
            "extraKnownMarketplaces": {"prawduct": _contract_entry()},
            "enabledPlugins": {_ENABLED_KEY: True},
        }
        node = data
        for key in leaf_path[:-1]:
            node = node[key]
        node[leaf_path[-1]] = "___corrupted___"

        d = tmp_path / ".claude"
        d.mkdir(parents=True, exist_ok=True)
        (d / "settings.json").write_text(json.dumps(data), encoding="utf-8")

        drift = install_reference_drift(tmp_path)
        assert drift["present"] is True, leaf_path
        assert [x["field"] for x in drift["drifted"]] == [_field_label(leaf_path)], leaf_path


def test_fires_when_governance_is_switched_off(tmp_path):
    # enabledPlugins: false is a repo with NO governance — strictly worse than a
    # version pin, and the case the two-field check could not see at all.
    _write_settings(tmp_path, _contract_entry(), enabled=False)
    out = irp.probe_install_reference_drift(ProjectState({}), _cb(tmp_path))
    assert len(out) == 1
    assert "enabledPlugins" in out[0].trigger_summary
    # "stranded at that reference" is the WRONG consequence here — nothing is
    # pinned to a version; the clone gets no governance at all. One sentence
    # cannot honestly cover both harms, so the summary branches.
    assert "governance switched off" in out[0].trigger_summary
    assert "stranded" not in out[0].trigger_summary


def test_version_drift_outranks_governance_drift_in_the_summary(tmp_path):
    # Both drifted: stranding is the more specific claim and wins. Pinned because
    # the branch is easy to invert and both strings look plausible either way.
    entry = _contract_entry()
    entry["source"]["ref"] = "v2.1.5"
    _write_settings(tmp_path, entry, enabled=False)
    out = irp.probe_install_reference_drift(ProjectState({}), _cb(tmp_path))
    assert "stranded at that reference" in out[0].trigger_summary
    assert "governance switched off" not in out[0].trigger_summary


def test_fires_when_enabled_plugins_key_is_absent(tmp_path):
    # Absent reads as drift here (unlike an absent marketplace entry, which means
    # "not onboarded"): the repo IS onboarded, it just won't turn the plugin on.
    _write_settings(tmp_path, _contract_entry(), enabled=None)
    out = irp.probe_install_reference_drift(ProjectState({}), _cb(tmp_path))
    assert len(out) == 1
    assert "enabledPlugins" in out[0].trigger_summary


def test_drift_reports_present_false_without_entry(tmp_path):
    _write_settings(tmp_path, None)
    assert install_reference_drift(tmp_path) == {"present": False, "drifted": []}


def test_probe_is_wired_into_the_composition_root(tmp_path):
    """The probe must fire through ``register_all()``, not just its own ``register()``.

    ``test_register_runs_in_the_roster`` calls ``irp.register()`` directly, so it
    stays green if the two ``probe_families.register_all()`` lines are deleted and
    the probe is dead in production — which is the incident ``probe_families.py``'s
    own docstring records. Nothing asserted the wiring until this test.
    """
    from lib.probe_families import register_all

    entry = _contract_entry()
    entry["source"]["ref"] = "v2.1.5"
    _write_settings(tmp_path, entry)
    register_all()
    fired = [
        c
        for c in run_all_probes(ProjectState({}), make_codebase(tmp_path))
        if c.feature == irp.FEATURE and c.type == "contract-drift"
    ]
    assert len(fired) == 1


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
