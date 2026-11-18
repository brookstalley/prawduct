"""Tests for the late-requirement record reader (#1034).

One parser for the record shape, so the lint that grades a new record today and
the binding and measurement that read records later agree on what a record is:

    - **LR-<n>** (<YYYY-MM-DD> · why: <reason> · surfaced: <chunk|sha>) — <sentence>.

with an optional trailing ``SUPERSEDED <date>: <reason>``. The pins here are the
round trip of every field, the problems a malformed item reports (which the
lint relays verbatim), what is and is not inside the section, and that
:func:`scan` finds records wherever the product keeps the section.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))
from lib import late_requirements  # noqa: E402
from lib.late_requirements import LateReq, Supersession  # noqa: E402

WELL_FORMED = (
    "- **LR-3** (2026-11-18 · why: new-consumer · surfaced: 09) — "
    "Exports also carry the unit of measure."
)


def _doc(*items: str, heading: str = "## Late requirements") -> str:
    return "# Product brief\n\nIntro.\n\n" + heading + "\n\n" + "\n".join(items) + "\n"


class TestParseRoundTrip:
    def test_every_field_of_a_well_formed_record(self):
        [rec] = late_requirements.parse(_doc(WELL_FORMED), path="brief.md")
        assert rec == LateReq(
            id="LR-3",
            date="2026-11-18",
            why="new-consumer",
            surfaced="09",
            statement="Exports also carry the unit of measure.",
            superseded=None,
            path="brief.md",
            line=7,
            problems=(),
        )
        assert rec.where == "brief.md:7"

    def test_a_superseded_record_keeps_its_line_and_gains_the_marker(self):
        line = WELL_FORMED + " SUPERSEDED 2026-12-01: the export format moved to LR-7."
        [rec] = late_requirements.parse(_doc(line))
        assert rec.statement == "Exports also carry the unit of measure."
        assert rec.superseded == Supersession(
            date="2026-12-01", reason="the export format moved to LR-7."
        )
        assert rec.problems == ()

    @pytest.mark.parametrize("why", sorted(late_requirements.WHY))
    def test_every_reason_in_the_fixed_set_parses(self, why):
        line = f"- **LR-1** (2026-11-18 · why: {why} · surfaced: abc1234) — It must."
        [rec] = late_requirements.parse(_doc(line))
        assert rec.why == why and rec.surfaced == "abc1234" and rec.problems == ()

    def test_the_fixed_set_is_the_four_study_reasons(self):
        assert late_requirements.WHY == frozenset(
            {"operating", "new-consumer", "owner-change", "constraint"}
        )

    def test_an_en_dash_or_hyphen_separator_is_tolerated(self):
        for sep in ("–", "-", "--"):
            line = f"- **LR-1** (2026-11-18 · why: operating · surfaced: 02) {sep} It must."
            [rec] = late_requirements.parse(_doc(line))
            assert rec.statement == "It must." and rec.problems == (), sep


class TestParseProblems:
    def _problems(self, line: str) -> tuple[str, ...]:
        [rec] = late_requirements.parse(_doc(line))
        return rec.problems

    def test_a_missing_why_is_named(self):
        problems = self._problems("- **LR-2** (2026-11-18 · surfaced: 03) — It must.")
        assert len(problems) == 1 and "`why`" in problems[0]

    def test_a_missing_surfaced_is_named(self):
        problems = self._problems("- **LR-2** (2026-11-18 · why: operating) — It must.")
        assert len(problems) == 1 and "`surfaced`" in problems[0]

    def test_a_missing_date_is_named(self):
        problems = self._problems("- **LR-2** (why: operating · surfaced: 03) — It must.")
        assert len(problems) == 1 and "date" in problems[0]

    def test_an_impossible_date_is_named(self):
        problems = self._problems(
            "- **LR-2** (2026-13-40 · why: operating · surfaced: 03) — It must."
        )
        assert len(problems) == 1 and "2026-13-40" in problems[0]

    def test_a_missing_statement_is_named(self):
        problems = self._problems("- **LR-2** (2026-11-18 · why: operating · surfaced: 03)")
        assert len(problems) == 1 and "sentence" in problems[0]

    def test_a_why_outside_the_fixed_set_is_named(self):
        problems = self._problems(
            "- **LR-2** (2026-11-18 · why: hunch · surfaced: 03) — It must."
        )
        assert len(problems) == 1
        assert "`why: hunch`" in problems[0] and "owner-change" in problems[0]

    def test_an_item_with_no_id_is_not_a_record(self):
        [rec] = late_requirements.parse(_doc("- Exports carry units."))
        assert rec.id is None
        assert rec.problems and "LR-<n>" in rec.problems[0]

    def test_a_malformed_supersession_is_named(self):
        problems = self._problems(WELL_FORMED + " SUPERSEDED because it moved")
        assert len(problems) == 1 and "SUPERSEDED" in problems[0]

    def test_the_well_formed_control_has_no_problems(self):
        assert self._problems(WELL_FORMED) == ()


class TestSectionBounds:
    def test_no_section_yields_nothing(self):
        text = "# Brief\n\n" + WELL_FORMED + "\n"
        assert late_requirements.parse(text) == []

    def test_the_section_ends_at_the_next_peer_heading(self):
        text = _doc(WELL_FORMED) + "\n## Next\n\n- **LR-9** junk outside\n"
        assert [r.id for r in late_requirements.parse(text)] == ["LR-3"]

    def test_a_deeper_heading_does_not_end_the_section(self):
        text = _doc(WELL_FORMED, "", "### Earlier", "",
                    "- **LR-4** (2026-11-19 · why: constraint · surfaced: 04) — Also.")
        assert [r.id for r in late_requirements.parse(text)] == ["LR-3", "LR-4"]

    def test_impact_walk_sub_items_are_not_records(self):
        text = _doc(WELL_FORMED, "  - `plugin/lib/export.py` — change",
                    "  - `docs/api.md` — checked, unaffected")
        [rec] = late_requirements.parse(text)
        assert rec.id == "LR-3"

    def test_a_fenced_example_is_not_a_record_or_a_heading(self):
        text = (
            "# Doc\n\n```\n## Late requirements\n\n- **LR-1** (bad\n```\n"
        )
        assert late_requirements.parse(text) == []
        fenced_inside = _doc("```", "- **LR-1** (bad", "```", WELL_FORMED)
        assert [r.id for r in late_requirements.parse(fenced_inside)] == ["LR-3"]

    def test_the_heading_mentioned_in_prose_opens_nothing(self):
        text = "# Doc\n\nPut it under `## Late requirements`.\n\n" + WELL_FORMED + "\n"
        assert late_requirements.parse(text) == []

    def test_section_ranges_report_line_spans(self):
        text = _doc(WELL_FORMED) + "\n## Next\n"
        [(start, end)] = late_requirements.section_ranges(text)
        lines = text.splitlines()
        # 1-based and inclusive: the heading through the line before the next
        # peer heading, so the closing heading itself is outside.
        assert lines[start - 1] == "## Late requirements"
        assert lines[end] == "## Next"


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo), capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


class TestScan:
    def _repo(self, tmp_path: Path) -> Path:
        repo = tmp_path / "repo"
        (repo / ".prawduct" / "artifacts").mkdir(parents=True)
        (repo / ".prawduct" / "artifacts" / "product-brief.md").write_text(_doc(WELL_FORMED))
        (repo / "docs").mkdir()
        (repo / "docs" / "requirements.md").write_text(
            _doc("- **LR-5** (2026-11-20 · why: owner-change · surfaced: 05) — More.")
        )
        (repo / "README.md").write_text("# Readme\n\nNo section here.\n")
        _git(repo, "init", "-q")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "c1")
        return repo

    def test_finds_records_in_every_file_holding_the_section(self, tmp_path):
        repo = self._repo(tmp_path)
        found = late_requirements.scan(repo)
        assert sorted((r.id, r.path) for r in found) == [
            ("LR-3", ".prawduct/artifacts/product-brief.md"),
            ("LR-5", "docs/requirements.md"),
        ]

    def test_an_untracked_file_in_the_working_tree_is_scanned(self, tmp_path):
        repo = self._repo(tmp_path)
        (repo / "plan.md").write_text(
            _doc("- **LR-6** (2026-11-21 · why: constraint · surfaced: 06) — New.")
        )
        assert "LR-6" in {r.id for r in late_requirements.scan(repo)}

    def test_a_tree_is_scanned_as_committed_not_as_on_disk(self, tmp_path):
        repo = self._repo(tmp_path)
        tree = _git(repo, "rev-parse", "HEAD^{tree}")
        (repo / "docs" / "requirements.md").write_text("# Gone\n")
        found = late_requirements.scan(repo, tree=tree)
        assert {r.id for r in found} == {"LR-3", "LR-5"}
        assert {r.id for r in late_requirements.scan(repo)} == {"LR-3"}

    def test_a_repo_with_no_section_scans_empty(self, tmp_path):
        repo = tmp_path / "empty"
        repo.mkdir()
        (repo / "README.md").write_text("# x\n")
        _git(repo, "init", "-q")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "c1")
        assert late_requirements.scan(repo) == []

    def test_outside_a_repo_the_scan_says_it_could_not_read(self, tmp_path):
        with pytest.raises(late_requirements.ScanError):
            late_requirements.scan(tmp_path, tree="0" * 40)


# ---------------------------------------------------------------------------
# building.md names the home, the shape, the triggers and the walk (#1034)
# ---------------------------------------------------------------------------


def _building_section(heading: str) -> str:
    text = (ROOT / "methodology" / "building.md").read_text()
    start = text.index(heading) + len(heading)
    nxt = re.search(r"^#{1,6} ", text[start:], re.MULTILINE)
    return text[start:start + nxt.start()] if nxt else text[start:]


class TestTheBuildingStepNamesTheCapture:
    SECTION = "### A Requirement Surfaced Mid-Build"

    def test_the_home_is_named(self):
        section = _building_section(self.SECTION)
        assert "`## Late requirements`" in section
        assert "`prawduct-hook jurisdiction` ranks first" in section
        assert "active build plan" in section

    def test_the_shape_in_the_step_is_the_shape_the_parser_reads(self):
        """The template sentence, filled in, must parse clean — a shape the prose
        teaches and the lint rejects is two definitions of one record."""
        section = _building_section(self.SECTION)
        shape = re.search(r"`(- \*\*LR-<n>\*\* \(.*?\) — <one sentence>\.)`", section)
        assert shape, "building.md no longer carries the record shape"
        filled = (
            shape.group(1)
            .replace("<n>", "7")
            .replace("<YYYY-MM-DD>", "2026-11-18")
            .replace("<operating|new-consumer|owner-change|constraint>", "constraint")
            .replace("<chunk id or short sha>", "09")
            .replace("<one sentence>", "It must")
        )
        [rec] = late_requirements.parse("## Late requirements\n\n" + filled + "\n")
        assert rec.problems == () and rec.why == "constraint"
        # Every reason the prose offers is one the parser accepts, and none is missing.
        offered = re.search(r"why: <([a-z|-]+)>", shape.group(1)).group(1).split("|")
        assert set(offered) == late_requirements.WHY
        assert "SUPERSEDED <date>: <reason>" in section

    def test_the_two_added_triggers_are_named(self):
        section = _building_section(self.SECTION)
        assert "an owner statement that changes behaviour" in section
        assert "a defect whose root cause is a missing requirement" in section

    def test_the_walk_names_its_sources_and_its_limit(self):
        section = _building_section(self.SECTION)
        walk = section[section.index("**Then walk its impact:**"):]
        for source in ("`prawduct-hook jurisdiction`", "plan chunks whose refs or acceptance",
                       "backlog items", "`git grep`", "the receiving artifact included"):
            assert source in walk, source
        assert "`change` or `checked, unaffected`" in walk
        assert "paraphrased restatement" in walk

