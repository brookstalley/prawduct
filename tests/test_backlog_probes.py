"""Tests for the backlog post-sync advisory probes (Chunk 06).

Each probe is a pure ``ProbeFn(state, codebase)``; tests drive trigger and
resolution conditions directly, plus the ``register()`` + ``run_all_probes``
integration (feature/probe_version stamping).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from lib.advisory_store import (
    Codebase,
    ProjectState,
    clear_registry,
    load_project_state,
    make_codebase,
    run_all_probes,
)
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

    def test_surfaces_through_the_live_roster(self, tmp_path):
        # The probe was wired to a no-op for several releases while the migration
        # path was unproven, so a direct-call assertion alone would have passed the
        # whole time it reached nobody. Assert the ROSTER, which is what a real
        # session reads.
        _write_backlog(tmp_path, _structured_backlog(2))
        bp.register()
        cands = run_all_probes(ProjectState({}), make_codebase(tmp_path))
        surfaced = [c for c in cands if c.type == "backlog-service-migration-required"]
        assert len(surfaced) == 1
        assert surfaced[0].recommended_action == "/prawduct:backlog scrub"

    def test_surfaces_at_warn_so_it_trips_the_relay(self, tmp_path):
        # The advisory routes toward an irreversible bulk write, so it must reach a
        # person, not just the model. The briefing relays `warn`/`urgent` only —
        # demoting this to `info` would silently restore the unreachable state the
        # lift was meant to end.
        _write_backlog(tmp_path, _structured_backlog(2))
        bp.register()
        cands = run_all_probes(ProjectState({}), make_codebase(tmp_path))
        surfaced = [c for c in cands if c.type == "backlog-service-migration-required"]
        assert surfaced[0].priority == "warn"

    def test_stays_quiet_post_cutover_through_the_roster(self, tmp_path):
        # Live now, so the "already migrated" case has to be proven at the roster
        # too: a repo on the Issues backend must not be nudged to migrate again.
        _write_backlog(tmp_path, _structured_backlog(2))
        bp.register()
        cands = run_all_probes(
            ProjectState({"backlog_service_repo": "acme/widgets"}), make_codebase(tmp_path)
        )
        assert not [c for c in cands if c.type == "backlog-service-migration-required"]


class TestTerminalMarkdownDeclaration:
    """#197 / TM1-TM4 — a product that will never migrate has a committed way to
    say so, and saying so silences THIS probe and nothing else.

    Absence of the field means undecided, and that is the default: it is pinned by
    `test_fires_on_structured_unmigrated_backlog` above, which runs an empty
    `ProjectState` against exactly this backlog.
    """

    def test_declared_markdown_stays_quiet_through_the_roster(self, tmp_path):
        # Through the roster, not the direct call: what a real session reads.
        _write_backlog(tmp_path, _structured_backlog(3))
        bp.register()
        cands = run_all_probes(
            ProjectState({"backlog_backend": "markdown"}), make_codebase(tmp_path)
        )
        assert not [c for c in cands if c.type == "backlog-service-migration-required"]

    def test_an_undeclared_value_does_not_resolve(self, tmp_path):
        # `markdown` is the only defined value (TM1). A typo or a value from some
        # future backend must not silence the nudge by accident — silence is what
        # this probe exists to prevent.
        _write_backlog(tmp_path, _structured_backlog(3))
        out = bp.probe_migration_required(
            ProjectState({"backlog_backend": "something-else"}), _cb(tmp_path)
        )
        assert len(out) == 1

    def test_an_actual_cutover_beats_a_stale_declaration(self, tmp_path):
        # TM4, and it falls out of the check ORDER rather than a comparison — this
        # asserts the combination is not its own path that could regress alone.
        _write_backlog(tmp_path, _structured_backlog(3))
        bp.register()
        cands = run_all_probes(
            ProjectState(
                {"backlog_service_repo": "acme/widgets", "backlog_backend": "markdown"}
            ),
            make_codebase(tmp_path),
        )
        assert not [c for c in cands if c.type == "backlog-service-migration-required"]

    def test_the_sibling_markdown_nudges_are_untouched(self, tmp_path):
        """TM3 — the whole reason this is a second, narrower predicate rather than a
        widening of `post_cutover()`. A product staying on the file needs its
        format/schema/grooming hygiene MORE than a migrating one, not less; folding
        the check into the shared predicate would have made it second-class."""
        _write_backlog(tmp_path, _legacy_backlog(bp.LEGACY_FORMAT_MIN_ITEMS + 2))
        bp.register()
        declared = run_all_probes(
            ProjectState({"backlog_backend": "markdown"}), make_codebase(tmp_path)
        )
        absent = run_all_probes(ProjectState({}), make_codebase(tmp_path))
        assert {c.type for c in declared} == {c.type for c in absent}, (
            "declaring terminal markdown changed which advisories fire beyond "
            "backlog-service-migration-required"
        )
        assert "legacy-backlog-format" in {c.type for c in declared}


class TestTheDormancyAdvisoryIsRetired:
    """The `backlog-checks-dormant` advisory and its `DORMANT_CHECKS` roster are
    gone (W1 Chunk 06), and these tests are what stops them coming back by accident.

    They are the *inverse* of the tests that stood here. Those asserted the
    dormancy was said out loud, because a reader returning nothing is
    indistinguishable from a clean bill of health. That risk has not gone away —
    it moved: each restored reader now reports an unreadable store at the point of
    use (`skills/backlog/cache-reads.md`), which is a better place to say it than a
    session-start advisory. What must not happen is the roster emptying while the
    probe survives, firing an advisory that names nothing.
    """

    def test_the_probe_and_its_roster_are_gone(self):
        # Both, because either alone is a half-retirement: a surviving probe over an
        # empty roster fires an advisory naming no checks, and a surviving roster
        # with no probe is a list nothing reads.
        assert not hasattr(bp, "probe_checks_dormant")
        assert not hasattr(bp, "DORMANT_CHECKS")

    def test_nothing_registers_to_announce_backlog_dormancy(self, tmp_path):
        # The durable form of "no advisory promises these checks return". It moved
        # here from `test_norm_probes.py`, which used to make the claim as an
        # assertion about `DORMANT_CHECKS` membership and lost its subject when the
        # roster went.
        from lib import advisory_store
        bp.register()
        assert not [k for k in advisory_store._REGISTRY if "dormant" in k]

    def test_no_advisory_fires_post_cutover_against_this_repo(self):
        # Repo-coupled tripwire (deliberately NOT hermetic), inverted from the one
        # that stood here. This repo is post-cutover, so it is the live case: if any
        # backlog probe starts nagging on the far side of the switch, this catches
        # it against real state rather than a fixture.
        #
        # `external-backlog-detected` is the deliberate exception and is excluded by
        # name: stray TODO.md files are a problem wherever the real backlog lives.
        repo_root = Path(__file__).resolve().parents[1]
        state = load_project_state(repo_root)
        assert bp.post_cutover(state), (
            "this repo is expected to be post-cutover since v3.2.0 Chunk 06; if the "
            "cutover was deliberately reverted, this test is what should tell you."
        )
        bp.register()
        fired = [
            c.type
            for c in run_all_probes(state, Codebase(root=repo_root))
            if c.type != "external-backlog-detected"
        ]
        assert fired == [], (
            f"a backlog advisory fired post-cutover: {fired}. Every markdown-premised "
            "probe retires at this switch and the dormancy advisory is retired "
            "outright, so anything here is reading frozen history as live state."
        )


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
