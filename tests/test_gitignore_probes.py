"""Tests for the session-file ``.gitignore`` contract-drift probe.

The probe is **inert when the contract is satisfied** — the steady state for
every correctly-onboarded repo — and fires on drift from any cause (missing
session entries, a wrongly-ignored committed file, or an absent ``.gitignore``).
Both halves are the guarantee, so both are tested first-class. The load-bearing
invariant (the probe fires IFF ``update_gitignore`` would modify the file) is
pinned in ``test_gitignore_management.py`` where the fixer lives. Registry
isolation mirrors ``test_upstream_probes.py`` (autouse ``clear_registry``).
"""

from __future__ import annotations

import pytest

from lib.advisory_store import (
    Codebase,
    ProjectState,
    clear_registry,
    make_codebase,
    run_all_probes,
)
from lib.core import GITIGNORE_ENTRIES, MANAGED_FILES
from lib import gitignore_probes as gp


@pytest.fixture(autouse=True)
def _isolated_registry():
    clear_registry()
    yield
    clear_registry()


def _cb(tmp_path):
    return Codebase(root=tmp_path)


def _write_gitignore(tmp_path, entries):
    (tmp_path / ".gitignore").write_text("\n".join(entries) + "\n", encoding="utf-8")


def test_inert_when_contract_satisfied(tmp_path):
    # A repo whose .gitignore carries every session entry → nothing to say.
    _write_gitignore(tmp_path, GITIGNORE_ENTRIES)
    assert gp.probe_gitignore_contract_drift(ProjectState({}), _cb(tmp_path)) == []


def test_fires_when_entries_missing(tmp_path):
    # Post-upgrade drift: the contract grew and .gitignore is behind by one.
    _write_gitignore(tmp_path, GITIGNORE_ENTRIES[:-1])
    out = gp.probe_gitignore_contract_drift(ProjectState({}), _cb(tmp_path))
    assert len(out) == 1
    assert out[0].type == "contract-drift"
    assert out[0].recommended_action == "prawduct-hook update-gitignore"
    assert out[0].alternative_actions == ("/prawduct:doctor",)
    assert "1 session entry missing" in out[0].trigger_summary


def test_fires_when_gitignore_absent(tmp_path):
    # No .gitignore at all → every session entry is missing (reads as empty).
    out = gp.probe_gitignore_contract_drift(ProjectState({}), _cb(tmp_path))
    assert len(out) == 1
    assert f"{len(GITIGNORE_ENTRIES)} session entries missing" in out[0].trigger_summary


def test_fires_when_managed_file_ignored(tmp_path):
    # A committed managed file wrongly listed in .gitignore, contract otherwise met.
    managed = sorted(MANAGED_FILES)[0]
    _write_gitignore(tmp_path, [*GITIGNORE_ENTRIES, managed])
    out = gp.probe_gitignore_contract_drift(ProjectState({}), _cb(tmp_path))
    assert len(out) == 1
    assert "1 committed file wrongly ignored" in out[0].trigger_summary


def test_evidence_is_count_independent(tmp_path):
    # Evidence is hashed into the advisory id, so it must NOT carry the count —
    # otherwise the id would churn as the drift set shrinks under a partial fix.
    _write_gitignore(tmp_path, GITIGNORE_ENTRIES[:-1])
    one = gp.probe_gitignore_contract_drift(ProjectState({}), _cb(tmp_path))
    _write_gitignore(tmp_path, GITIGNORE_ENTRIES[:-3])
    three = gp.probe_gitignore_contract_drift(ProjectState({}), _cb(tmp_path))
    assert one[0].evidence == three[0].evidence
    assert "1 session entry missing" in one[0].trigger_summary
    assert "3 session entries missing" in three[0].trigger_summary


def test_register_runs_in_the_roster(tmp_path):
    # No .gitignore → the probe fires; assert it is wired with the right feature.
    gp.register()
    gp.register()  # idempotent — register_probe overwrites
    cands = run_all_probes(ProjectState({}), make_codebase(tmp_path))
    fired = [c for c in cands if c.type == "contract-drift"]
    assert len(fired) == 1
    assert fired[0].feature == "gitignore"
    assert fired[0].probe_version == gp.PROBE_VERSION
