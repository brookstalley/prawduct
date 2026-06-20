"""Tests for the upstream-bug-reporting receiving-side probe (Chunk 02).

The probe is **inert by absence**: a product repo has no ``incoming-bugs/``
directory, so the nudge never fires there. The fire/inert split is the guarantee,
so both halves are tested first-class. Registry isolation mirrors
``test_backlog_probes.py`` (autouse ``clear_registry``).
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
from lib import upstream_probes as up


@pytest.fixture(autouse=True)
def _isolated_registry():
    clear_registry()
    yield
    clear_registry()


def _cb(tmp_path):
    return Codebase(root=tmp_path)


def _inbox(tmp_path, names=()):
    d = tmp_path / "incoming-bugs"
    d.mkdir()
    for n in names:
        (d / n).write_text("# bug\n", encoding="utf-8")
    return d


def test_inert_when_dir_absent(tmp_path):
    # The product-repo case: no incoming-bugs/ → no nudge, ever.
    assert up.probe_untriaged_upstream_reports(ProjectState({}), _cb(tmp_path)) == []


def test_inert_when_dir_empty(tmp_path):
    _inbox(tmp_path)
    assert up.probe_untriaged_upstream_reports(ProjectState({}), _cb(tmp_path)) == []


def test_fires_with_reports(tmp_path):
    _inbox(tmp_path, ["a-bug.md", "another-bug.md"])
    out = up.probe_untriaged_upstream_reports(ProjectState({}), _cb(tmp_path))
    assert len(out) == 1
    assert out[0].type == "untriaged-upstream-reports"
    assert "2" in out[0].trigger_summary
    assert out[0].recommended_action == "/prawduct:backlog"


def test_ignores_archived_reports(tmp_path):
    inbox = _inbox(tmp_path)
    archive = inbox / "archive"
    archive.mkdir()
    (archive / "old-bug.md").write_text("# old\n", encoding="utf-8")
    # archived reports live in a subdir; the non-recursive glob skips them → inert.
    assert up.probe_untriaged_upstream_reports(ProjectState({}), _cb(tmp_path)) == []


def test_evidence_is_count_independent(tmp_path):
    # Evidence is hashed into the advisory id, so it must NOT carry the count —
    # otherwise the id would churn as reports come and go (D14).
    _inbox(tmp_path, ["a.md"])
    one = up.probe_untriaged_upstream_reports(ProjectState({}), _cb(tmp_path))
    (tmp_path / "incoming-bugs" / "b.md").write_text("# b\n", encoding="utf-8")
    two = up.probe_untriaged_upstream_reports(ProjectState({}), _cb(tmp_path))
    assert one[0].evidence == two[0].evidence
    assert "1" in one[0].trigger_summary and "2" in two[0].trigger_summary


def test_register_runs_in_the_roster(tmp_path):
    _inbox(tmp_path, ["x.md"])
    up.register()
    up.register()  # idempotent — register_probe overwrites
    cands = run_all_probes(ProjectState({}), make_codebase(tmp_path))
    fired = [c for c in cands if c.type == "untriaged-upstream-reports"]
    assert len(fired) == 1
    assert fired[0].feature == "report-bug"
