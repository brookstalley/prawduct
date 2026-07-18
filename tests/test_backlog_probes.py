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


def _legacy_backlog(n: int) -> str:
    """A backlog of ``n`` unstructured (id-less) legacy items."""
    items = "".join(f"- legacy item {i} (critic)\n" for i in range(n))
    return f"# Backlog\n## Open\n{items}"


class TestLegacyBacklogFormatProbe:
    def test_fires_on_legacy_items(self, tmp_path):
        _write_backlog(tmp_path, _legacy_backlog(bp.LEGACY_FORMAT_MIN_ITEMS + 1))  # > floor
        out = bp.probe_legacy_backlog_format(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1
        assert out[0].type == "legacy-backlog-format"
        assert out[0].recommended_action == "/prawduct:backlog migrate"
        # Live count in the summary; evidence is count-independent (id-stable).
        assert str(bp.LEGACY_FORMAT_MIN_ITEMS + 1) in out[0].trigger_summary

    def test_resolved_by_format_version(self, tmp_path):
        _write_backlog(tmp_path, _legacy_backlog(bp.LEGACY_FORMAT_MIN_ITEMS + 3))
        state = ProjectState({"backlog_format_version": 2})
        assert bp.probe_legacy_backlog_format(state, _cb(tmp_path)) == []

    def test_partial_migration_no_fire(self, tmp_path):
        # Any structured item means migration is mid-flight — backlog_format_version
        # is the authoritative done-signal, so the id-less-count trigger stands down.
        body = (
            "# Backlog\n## Open\n"
            + "".join(f"- legacy item {i} (critic)\n" for i in range(6))
            + "- **[X-001]** a structured one\n  `area: x · status: open`\n"
        )
        _write_backlog(tmp_path, body)
        assert bp.probe_legacy_backlog_format(ProjectState({}), _cb(tmp_path)) == []

    def test_small_backlog_no_fire(self, tmp_path):
        _write_backlog(tmp_path, _legacy_backlog(bp.LEGACY_FORMAT_MIN_ITEMS))  # == floor, not >
        assert bp.probe_legacy_backlog_format(ProjectState({}), _cb(tmp_path)) == []

    def test_no_backlog_file(self, tmp_path):
        assert bp.probe_legacy_backlog_format(ProjectState({}), _cb(tmp_path)) == []

    def test_comment_bullets_not_counted(self, tmp_path):
        # The header legend comment carries example bullets; parse_backlog excludes
        # them, so they must not inflate the count past the floor on their own.
        comment_bullets = "".join(f"- example {i}\n" for i in range(10))
        body = (
            f"# Backlog\n<!--\nlegend:\n{comment_bullets}-->\n## Open\n"
            + "".join(f"- legacy item {i} (critic)\n" for i in range(3))  # 3 real ≤ floor
        )
        _write_backlog(tmp_path, body)
        assert bp.probe_legacy_backlog_format(ProjectState({}), _cb(tmp_path)) == []


def _structured_backlog(n_open: int, *, archived: int = 0) -> str:
    """A structured backlog: ``n_open`` open (pending) items + ``archived`` shipped
    items under ``## Archive``. Every item carries a ``[PFX-XXXX]`` id, so the file
    is in the structured format (the migration-required, not legacy-format, case)."""
    open_items = "".join(
        f"- **[SVC-{i:03d}]** open item {i}\n  `area: x · status: open`\n" for i in range(n_open)
    )
    arch_items = "".join(
        f"- **[SVC-9{i:02d}]** shipped item {i}\n  `area: x · status: shipped`\n"
        for i in range(archived)
    )
    return f"# Backlog\n## Open\n{open_items}## Archive\n{arch_items}"


class TestMigrationRequiredProbe:
    def test_fires_on_structured_unmigrated_backlog(self, tmp_path):
        _write_backlog(tmp_path, _structured_backlog(3))
        out = bp.probe_migration_required(ProjectState({}), _cb(tmp_path))
        assert len(out) == 1
        assert out[0].type == "backlog-service-migration-required"
        assert out[0].priority == "warn"
        assert out[0].recommended_action == "/prawduct:backlog scrub"
        # Live count in the summary; evidence is count-independent (id-stable).
        assert "3 pending" in out[0].trigger_summary
        assert "3" not in out[0].evidence[0]

    def test_pre_structured_file_defers_to_legacy_format(self, tmp_path):
        # No item carries a [PFX-XXXX] id → legacy-backlog-format owns the nudge,
        # so this probe stands down (the two partition the space).
        _write_backlog(tmp_path, _legacy_backlog(bp.LEGACY_FORMAT_MIN_ITEMS + 2))
        assert bp.probe_migration_required(ProjectState({}), _cb(tmp_path)) == []

    def test_partition_is_exclusive(self, tmp_path):
        # A fully-structured backlog trips migration-required and NOT legacy-format;
        # the inverse (pre-structured) is covered above. At most one fires.
        _write_backlog(tmp_path, _structured_backlog(4))
        assert bp.probe_migration_required(ProjectState({}), _cb(tmp_path))
        assert bp.probe_legacy_backlog_format(ProjectState({}), _cb(tmp_path)) == []

    def test_frozen_all_archived_no_fire(self, tmp_path):
        # A structured file whose items are all archived has nothing live to migrate.
        _write_backlog(tmp_path, _structured_backlog(0, archived=3))
        assert bp.probe_migration_required(ProjectState({}), _cb(tmp_path)) == []

    def test_no_backlog_file(self, tmp_path):
        assert bp.probe_migration_required(ProjectState({}), _cb(tmp_path)) == []

    def test_surfaced_through_registered_roster(self, tmp_path):
        _write_backlog(tmp_path, _structured_backlog(2))
        bp.register()
        cands = run_all_probes(ProjectState({}), make_codebase(tmp_path))
        nudge = [c for c in cands if c.type == "backlog-service-migration-required"]
        assert nudge and nudge[0].recommended_action == "/prawduct:backlog scrub"
        assert nudge[0].feature == "backlog" and nudge[0].probe_version == bp.PROBE_VERSION


class TestRegistration:
    def test_register_adds_five_probes(self):
        from lib import advisory_store
        bp.register()
        keys = set(advisory_store._REGISTRY)
        assert keys == {
            "backlog:legacy-backlog-format",
            "backlog:backlog-service-migration-required",
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

    def test_run_all_probes_surfaces_legacy_backlog_migrate_nudge(self, tmp_path):
        # The regression that motivated this fix: a legacy-format backlog must
        # surface the /prawduct:backlog migrate nudge through the *registered*
        # roster (register() + run_all_probes), not just the probe in isolation —
        # the original gap was the probe being absent from register().
        _write_backlog(tmp_path, _legacy_backlog(bp.LEGACY_FORMAT_MIN_ITEMS + 2))
        bp.register()
        cands = run_all_probes(ProjectState({}), make_codebase(tmp_path))
        nudge = [c for c in cands if c.type == "legacy-backlog-format"]
        assert nudge and nudge[0].recommended_action == "/prawduct:backlog migrate"
        assert nudge[0].feature == "backlog" and nudge[0].probe_version == bp.PROBE_VERSION

    def test_faulty_probe_isolation_unaffected(self, tmp_path):
        # A registered probe that raises must not block the others (run_all_probes
        # swallows per-probe errors). Sanity-check our probes coexist cleanly.
        bp.register()
        cands = run_all_probes(ProjectState({}), make_codebase(tmp_path))
        assert isinstance(cands, list)  # no crash with an empty repo


class TestPostCutoverRetirement:
    """Once ``backlog_service_repo`` is set (migration cutover), the probes whose
    premise is 'the markdown file IS the live backlog' retire — a frozen file
    must not generate nudges. external-backlog keeps its independent premise."""

    _CUTOVER = {"backlog_service_repo": "octo/backlog"}

    def test_legacy_format_probe_retires(self, tmp_path):
        _write_backlog(tmp_path, "# Backlog\n" + "".join(f"- item {i}\n" for i in range(9)))
        assert bp.probe_legacy_backlog_format(ProjectState(dict(self._CUTOVER)), _cb(tmp_path)) == []

    def test_section_schema_probe_retires(self, tmp_path):
        _write_backlog(tmp_path, "# Backlog\n## Active — next up\n- a\n## Queue\n- b\n")
        assert bp.probe_legacy_section_schema(ProjectState(dict(self._CUTOVER)), _cb(tmp_path)) == []

    def test_overdue_grooming_probe_retires(self, tmp_path):
        _write_backlog(tmp_path, "# Backlog\n## Open\n" + "".join(
            f"- **[X-{i:04d}]** item {i}\n" for i in range(40)))
        assert bp.probe_overdue_grooming(ProjectState(dict(self._CUTOVER)), _cb(tmp_path)) == []

    def test_migration_required_probe_retires(self, tmp_path):
        # Once cut over, the structured file is frozen history — the migrate-onward
        # nudge is done (its whole premise was "not yet on the service").
        _write_backlog(tmp_path, _structured_backlog(3))
        assert bp.probe_migration_required(ProjectState(dict(self._CUTOVER)), _cb(tmp_path)) == []

    def test_external_backlog_probe_survives_cutover(self, tmp_path):
        (tmp_path / "TODO.md").write_text("- do a thing\n", encoding="utf-8")
        out = bp.probe_external_backlog(ProjectState(dict(self._CUTOVER)), _cb(tmp_path))
        assert len(out) == 1 and out[0].type == "external-backlog-detected"
