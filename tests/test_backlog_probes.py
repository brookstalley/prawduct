"""Tests for the backlog post-sync advisory probes (Chunk 06).

Each probe is a pure ``ProbeFn(state, codebase)``; tests drive trigger and
resolution conditions directly, plus the ``register()`` + ``run_all_probes``
integration (feature/probe_version stamping).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from lib.advisory_store import Codebase, ProjectState, clear_registry, make_codebase, run_all_probes
from lib import backlog_probes as bp


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_registry()
    yield
    clear_registry()


def _write_backlog(tmp_path, body: str):
    d = tmp_path / ".prawduct"
    d.mkdir(parents=True, exist_ok=True)
    (d / "backlog.md").write_text(body, encoding="utf-8")


def _cb(tmp_path) -> Codebase:
    return Codebase(root=tmp_path)


class TestExternalBacklogProbe:
    def test_fires_on_unaudited_external_file(self, tmp_path):
        (tmp_path / "TODO.md").write_text("- do a thing\n")
        out = bp.probe_external_backlog(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1
        assert out[0].type == "external-backlog-detected"
        assert "TODO.md" in out[0].evidence

    def test_github_subdir_detected(self, tmp_path):
        (tmp_path / ".github").mkdir()
        (tmp_path / ".github" / "BACKLOG.md").write_text("- x\n")
        out = bp.probe_external_backlog(ProjectState({}), _cb(tmp_path))
        assert out and ".github/BACKLOG.md" in out[0].evidence

    def test_resolved_when_recorded(self, tmp_path):
        (tmp_path / "TODO.md").write_text("- do a thing\n")
        state = ProjectState({"backlog_external_imports": "TODO.md"})
        assert bp.probe_external_backlog(state, _cb(tmp_path)) == []

    def test_no_external_file(self, tmp_path):
        assert bp.probe_external_backlog(ProjectState({}), _cb(tmp_path)) == []


class TestLegacySectionSchemaProbe:
    def test_fires_on_legacy_headings(self, tmp_path):
        _write_backlog(tmp_path, "# Backlog\n## Active — next up\n- a\n## Queue\n- b\n")
        out = bp.probe_legacy_section_schema(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1 and out[0].type == "legacy-section-schema"

    def test_resolved_by_format_version(self, tmp_path):
        _write_backlog(tmp_path, "# Backlog\n## Queue\n- b\n")
        state = ProjectState({"backlog_format_version": 2})
        assert bp.probe_legacy_section_schema(state, _cb(tmp_path)) == []

    def test_modern_schema_no_fire(self, tmp_path):
        _write_backlog(tmp_path, "# Backlog\n## Open\n- a\n## Promoted\n## Archive\n")
        assert bp.probe_legacy_section_schema(ProjectState({}), _cb(tmp_path)) == []

    def test_no_backlog_file(self, tmp_path):
        assert bp.probe_legacy_section_schema(ProjectState({}), _cb(tmp_path)) == []


def _backlog_with_open(n: int) -> str:
    items = "".join(f"- **[X-{i:03d}]** item {i}\n  `area: x · status: open`\n" for i in range(n))
    return f"# Backlog\n## Open\n{items}"


class TestOverdueGroomingProbe:
    def test_fires_large_and_never_groomed(self, tmp_path):
        _write_backlog(tmp_path, _backlog_with_open(bp.GROOMING_MIN_OPEN_ITEMS + 1))
        out = bp.probe_overdue_grooming(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1 and out[0].type == "backlog-overdue-grooming"

    def test_small_backlog_no_fire(self, tmp_path):
        _write_backlog(tmp_path, _backlog_with_open(bp.GROOMING_MIN_OPEN_ITEMS))  # not > threshold
        assert bp.probe_overdue_grooming(ProjectState({}), _cb(tmp_path)) == []

    def test_recently_groomed_no_fire(self, tmp_path):
        _write_backlog(tmp_path, _backlog_with_open(bp.GROOMING_MIN_OPEN_ITEMS + 5))
        recent = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        state = ProjectState({"backlog_last_groomed_at": recent})
        assert bp.probe_overdue_grooming(state, _cb(tmp_path)) == []

    def test_stale_groomed_fires(self, tmp_path):
        _write_backlog(tmp_path, _backlog_with_open(bp.GROOMING_MIN_OPEN_ITEMS + 5))
        state = ProjectState({"backlog_last_groomed_at": "2000-01-01T00:00:00Z"})
        assert len(bp.probe_overdue_grooming(state, _cb(tmp_path))) == 1

    def test_unparseable_timestamp_degrades_safe(self, tmp_path):
        _write_backlog(tmp_path, _backlog_with_open(bp.GROOMING_MIN_OPEN_ITEMS + 5))
        state = ProjectState({"backlog_last_groomed_at": "not-a-date"})
        assert bp.probe_overdue_grooming(state, _cb(tmp_path)) == []


class TestRegistration:
    def test_register_adds_three_probes(self):
        from lib import advisory_store
        bp.register()
        keys = set(advisory_store._REGISTRY)
        assert keys == {
            "backlog:external-backlog-detected",
            "backlog:legacy-section-schema",
            "backlog:backlog-overdue-grooming",
        }

    def test_run_all_probes_stamps_feature_and_version(self, tmp_path):
        (tmp_path / "TODO.md").write_text("- x\n")
        bp.register()
        cands = run_all_probes(ProjectState({}), make_codebase(tmp_path))
        ext = [c for c in cands if c.type == "external-backlog-detected"]
        assert ext and ext[0].feature == "backlog" and ext[0].probe_version == bp.PROBE_VERSION

    def test_faulty_probe_isolation_unaffected(self, tmp_path):
        # A registered probe that raises must not block the others (run_all_probes
        # swallows per-probe errors). Sanity-check our probes coexist cleanly.
        bp.register()
        cands = run_all_probes(ProjectState({}), make_codebase(tmp_path))
        assert isinstance(cands, list)  # no crash with an empty repo
