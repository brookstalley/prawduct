"""Tests for the shared build-plan walkers + consolidation pins (STH-2K8R / BLD-6Q1N).

Three concerns:

1. Direct unit coverage of the canonical walkers in ``lib.buildplan_refs`` —
   ``_iter_status_section_lines`` / ``_iter_status_section_items`` (the one
   Status-section reader walk) and ``_chunk_section_lines`` (the one
   chunk-section walk) — plus the helpers built on them
   (``_count_build_plan_chunks``).

2. Consolidation pins: the duplicate bodies deleted from ``lib.critic_mode``
   and ``lib.gates`` must STAY deleted — a consolidated walk must stay
   SINGULAR. A source-scan asserts the walk skeletons' anchor literals
   don't reappear in the consumer modules.

3. Porcelain edge cases through ``critic_mode._get_uncommitted_code_files``'s
   consolidated parse path (``gitstate.parse_porcelain_line``): quoted paths
   with spaces and rename destinations — cases the old inline parse handled
   implicitly and must keep handling.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from lib import buildplan_refs, critic_mode, gates, gitstate, plan_index
from lib.buildplan_refs import (
    _chunk_id_from_item_text,
    _chunk_section_lines,
    _count_build_plan_chunks,
    _current_chunk_id_from_status,
    _iter_status_section_items,
    _iter_status_section_lines,
)

LIB_DIR = Path(__file__).resolve().parent.parent / "plugin" / "lib"


# ---------------------------------------------------------------------------
# Fixture helpers (sterile-git idiom shared with test_critic_mode_inference)
# ---------------------------------------------------------------------------


def _git_env(repo: Path) -> dict[str, str]:
    """Sterile env for git calls; HOME outside the repo (see the inference
    tests' helper for why — OS caches must not appear as untracked files)."""
    return {
        "HOME": str(repo.parent / "_home"),
        "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_CONFIG_SYSTEM": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
    }


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=_git_env(repo),
        check=True,
        timeout=10,
    )


def _init_repo(repo: Path) -> None:
    _git(repo, "init", "--quiet", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


def _write(repo: Path, rel: str, content: str) -> Path:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def _write_plan(prawduct: Path, content: str) -> None:
    plan = prawduct / "artifacts" / "build-plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(content)


PLAN = """# Build Plan — Walker Fixture (2026-06-10)

**Size**: small | **Type**: refactor

## Status

<!-- A multi-line comment
     - [ ] Chunk 99: decoy inside comment
     spanning lines -->
- [x] Chunk 01: first
- [X] Chunk 02: second (capital X)
- [ ] Chunk 03: third
Context: mid-plan.

## Build Chunks

### Chunk 1: first

- **Type:** code
- **Critic mode:** chunk

```text
- **Critic mode:** cumulative
inside a fence — field lines here are not load-bearing prose
```

- body line after fence

### Chunk 02: second

- **Type:** doc-only

## Notes

- [ ] not a status item (outside Status)
"""


# ---------------------------------------------------------------------------
# 1. Walker unit tests
# ---------------------------------------------------------------------------


class TestIterStatusSection:
    def test_yields_only_status_section_lines(self):
        lines = list(_iter_status_section_lines(PLAN))
        assert "- [x] Chunk 01: first" in lines
        assert "Context: mid-plan." in lines
        # Stops at the next ## heading — Build Chunks content never appears.
        assert not any("Type:" in ln for ln in lines)
        assert "- [ ] not a status item (outside Status)" not in lines

    def test_html_comment_span_is_skipped(self):
        lines = list(_iter_status_section_lines(PLAN))
        assert not any("decoy" in ln for ln in lines)

    def test_no_status_section_yields_nothing(self):
        assert list(_iter_status_section_lines("# Plan\n\n## Other\n- [ ] x\n")) == []

    def test_items_carry_checked_state_and_text(self):
        items = list(_iter_status_section_items(PLAN))
        assert items == [
            (True, "Chunk 01: first"),
            (True, "Chunk 02: second (capital X)"),
            (False, "Chunk 03: third"),
        ]


class TestCountAndIds:
    def test_count_build_plan_chunks(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        _write_plan(prawduct, PLAN)
        assert _count_build_plan_chunks(prawduct) == (3, 2)

    def test_count_missing_plan_is_zero(self, tmp_path: Path):
        assert _count_build_plan_chunks(tmp_path / ".prawduct") == (0, 0)


class TestChunkSectionLines:
    def test_leading_zero_tolerance_both_directions(self):
        # Plan heading "### Chunk 1:" found via id "01"; "### Chunk 02:" via "2".
        found, lines, _unparsed = _chunk_section_lines(PLAN, "01")
        assert found
        assert any("**Critic mode:** chunk" in ln for _n, ln in lines)
        found2, lines2, _unparsed2 = _chunk_section_lines(PLAN, "2")
        assert found2
        assert any("**Type:** doc-only" in ln for _n, ln in lines2)

    def test_fenced_block_is_dropped(self):
        found, lines, _unparsed = _chunk_section_lines(PLAN, "1")
        assert found
        body = [ln for _n, ln in lines]
        assert not any("cumulative" in ln for ln in body)
        assert any("body line after fence" in ln for ln in body)

    def test_stops_at_sibling_chunk(self):
        _found, lines, _unparsed = _chunk_section_lines(PLAN, "1")
        assert not any("doc-only" in ln for _n, ln in lines)

    def test_stops_at_next_h2(self):
        _found, lines, _unparsed = _chunk_section_lines(PLAN, "02")
        assert not any("not a status item" in ln for _n, ln in lines)

    def test_not_found(self):
        found, lines, _unparsed = _chunk_section_lines(PLAN, "42")
        assert not found
        assert lines == []

    def test_line_numbers_are_one_based_into_content(self):
        _found, lines, _unparsed = _chunk_section_lines(PLAN, "1")
        content_lines = PLAN.splitlines()
        for line_num, line in lines:
            assert content_lines[line_num - 1] == line


# The H2 / em-dash research-plan heading form (`## Chunk N (ID) — Name`) with
# colon-less Status items — previously unparseable, which silently disabled the
# Goal-2 deliverable check and per-chunk mode scoping for the WHOLE plan
# (BLD-5J8N / PDT-C6R4). The `### Chunk 1 build-session decisions` sub-heading
# (no separator after the id) must NOT be mistaken for chunk 1's boundary.
PLAN_H2 = """# Build Plan — H2 Fixture (2026-07-18)

## Status

- [ ] Chunk 1 (RES-K3QP) — inner-agent budget transparency
- [ ] Chunk 2 (RES-W8ND) — eval observability
Context: mid-plan.

## Build Chunks

## Chunk 1 (RES-K3QP) — inner-agent budget transparency

- **Type:** code
- Deliverable: `lib/research_trace.py`

### Chunk 1 build-session decisions (2026-07-18, finalized)

- a notes sub-heading; its body must stay inside chunk 1
- Deliverable: `lib/still_chunk_one.py`

## Chunk 2 (RES-W8ND) — eval observability

- **Type:** doc-only
- Deliverable: `docs/obs.md`
"""


class TestH2ChunkHeadingForm:
    def test_h2_paren_id_section_located(self):
        found, lines, _unparsed = _chunk_section_lines(PLAN_H2, "1")
        assert found
        body = [ln for _n, ln in lines]
        assert any("lib/research_trace.py" in ln for ln in body)

    def test_leading_zero_tolerance_on_h2_form(self):
        # "## Chunk 2 (…)" located via id "02".
        found, lines, _unparsed = _chunk_section_lines(PLAN_H2, "02")
        assert found
        assert any("docs/obs.md" in ln for _n, ln in lines)

    def test_notes_subheading_does_not_end_section(self):
        # "### Chunk 1 build-session decisions" has no separator after the id,
        # so it is body, not a sibling boundary — chunk 1 keeps its later refs.
        _found, lines, _unparsed = _chunk_section_lines(PLAN_H2, "1")
        body = [ln for _n, ln in lines]
        assert any("lib/still_chunk_one.py" in ln for ln in body)
        # …but the genuine sibling "## Chunk 2" still ends it.
        assert not any("docs/obs.md" in ln for ln in body)

    def test_h2_sibling_boundary_still_stops(self):
        _found, lines, _unparsed = _chunk_section_lines(PLAN_H2, "2")
        body = [ln for _n, ln in lines]
        assert any("docs/obs.md" in ln for ln in body)
        assert not any("research_trace" in ln for ln in body)


class TestChunkIdFromItemText:
    def test_colon_form(self):
        assert _chunk_id_from_item_text("Chunk 02: second") == "02"

    def test_em_dash_paren_id_form(self):
        assert _chunk_id_from_item_text("Chunk 2 (RES-K3QP) — eval") == "2"

    def test_em_dash_no_paren_form(self):
        assert _chunk_id_from_item_text("Chunk 01 — first") == "01"

    def test_bare_id_form(self):
        assert _chunk_id_from_item_text("Chunk 3") == "3"

    def test_non_chunk_item_is_none(self):
        assert _chunk_id_from_item_text("tidy the docs") is None
        # A word starting with "Chunk" but not the chunk form is not a match.
        assert _chunk_id_from_item_text("Chunky monkey business") is None

    def test_current_chunk_id_from_h2_status(self, tmp_path: Path):
        # Takes the PROJECT dir, not `.prawduct/`. Resolving "current" was once
        # git-aware, which is where the signature came from; it now reads the
        # checkboxes alone, and the project dir is what locates the plan
        # (BLD-7K3Q).
        _write_plan(tmp_path / ".prawduct", PLAN_H2)
        assert _current_chunk_id_from_status(tmp_path) == "1"


# ---------------------------------------------------------------------------
# 1b. The dotted-id and leading-checkbox heading forms, and the third state
#     an unparseable heading has to produce.
# ---------------------------------------------------------------------------


# Five heading forms in one plan, in the order that makes the bleed visible: the
# unparseable ones follow a parseable one, so a section that fails to close
# swallows them. Chunk A is the victim, not the culprit — its deliverable set
# comes back NON-empty and wrong, which is the shape nobody notices.
PLAN_FORMS = """# Build Plan — Heading Forms

## Status

- [ ] Chunk 01: colon form
- [ ] Chunk 2 (RES-K3QP) — paren form
- [ ] **Chunk A** — bold form
- [ ] Chunk 1.2: dotted form
- [ ] Chunk 7: checkbox form

## Build Chunks

### Chunk 01: colon form

- **Deliverables:** `plugin/lib/core.py`

### Chunk 2 (RES-K3QP) — paren form

- **Deliverables:** `plugin/lib/plan_index.py`

### **Chunk A** — bold form

- **Deliverables:** `plugin/lib/waivers.py`

### Chunk 1.2: dotted form

- **Deliverables:** `plugin/lib/gates.py`

### [ ] Chunk 7: checkbox form

- **Deliverables:** `plugin/lib/critic_mode.py`
"""


class TestWidenedChunkHeadingForms:
    """Dotted ids and a leading checkbox parse; nothing that parsed stops."""

    @pytest.mark.parametrize(
        "heading,expected",
        [
            # Previously working — every one must keep working.
            ("### Chunk 01: Name", "01"),
            ("## Chunk 2 (RES-K3QP) — Name", "2"),
            ("### **Chunk A** — Name", "A"),
            ("### Chunk 01 – Name", "01"),
            ("### Chunk 01 - Name", "01"),
            ("### Chunk A3", "A3"),
            # Newly accepted.
            ("### Chunk 1.2: Name", "1.2"),
            ("## Chunk 1.2 — Name", "1.2"),
            ("### **Chunk 1.2** — Name", "1.2"),
            ("### Chunk 1.2.3: Name", "1.2.3"),
            ("### [ ] Chunk 7: Name", "7"),
            ("### [x] Chunk 7 — Name", "7"),
            ("### - [ ] Chunk 7: Name", "7"),
            ("### - [X] Chunk 1.2: Name", "1.2"),
        ],
    )
    def test_heading_matcher_accepts(self, heading: str, expected: str):
        m = buildplan_refs._CHUNK_HEADING_RE.match(heading)
        assert m is not None and m.group(1) == expected

    @pytest.mark.parametrize(
        "heading",
        [
            # A notes sub-heading: a WORD after the id, so still not a boundary.
            "### Chunk 1 build-session decisions",
            # A sentence period is not a dotted id.
            "### Chunk 1. Name",
            # Depth outside `#{2,3}` still silently defeats the parser — which is
            # exactly what the unparsed-heading signal below now reports.
            "#### Chunk 01: Name",
            "Chunky monkey business",
        ],
    )
    def test_heading_matcher_still_rejects(self, heading: str):
        assert buildplan_refs._CHUNK_HEADING_RE.match(heading) is None

    @pytest.mark.parametrize(
        "item,expected",
        [
            ("Chunk 1.2: A", "1.2"),
            ("Chunk 1.2 — A", "1.2"),
            ("**Chunk 1.2** — A", "1.2"),
            ("[ ] Chunk 7: A", "7"),
            ("- [x] Chunk 1.2 — A", "1.2"),
            # Unchanged forms.
            ("Chunk 01: A", "01"),
            ("Chunk 2 (RES-K3QP) — eval", "2"),
            ("Chunk 3", "3"),
        ],
    )
    def test_item_matcher_accepts_the_same_vocabulary(self, item: str, expected: str):
        assert _chunk_id_from_item_text(item) == expected

    @pytest.mark.parametrize(
        "form", ["Chunk 1.2: A", "**Chunk 1.2** — A", "Chunk 7: A", "Chunk A3"]
    )
    def test_the_pair_agrees(self, form: str):
        """The heading matcher and the Status-item matcher are one contract read
        twice. A form one accepts and the other does not is the split-brain that
        made a plan read as having no current chunk while its section resolved —
        so they are asserted against the same strings, not separate lists."""
        heading = buildplan_refs._CHUNK_HEADING_RE.match(f"### {form}")
        assert heading is not None
        assert _chunk_id_from_item_text(form) == heading.group(1)

    def test_dotted_and_checkbox_sections_resolve_end_to_end(self):
        for chunk_id, deliverable in (("1.2", "gates.py"), ("7", "critic_mode.py")):
            section = _chunk_section_lines(PLAN_FORMS, chunk_id)
            assert section.found, chunk_id
            assert any(deliverable in ln for _n, ln in section.lines), chunk_id

    def test_a_widened_heading_closes_the_section_before_it(self):
        """The bleed, stated as the property that fixes it: chunk A's body ends
        at chunk 1.2's heading. Before the widening it ran to the end of the
        plan and chunk A answered with `gates.py` and `critic_mode.py`."""
        section = _chunk_section_lines(PLAN_FORMS, "A")
        body = [ln for _n, ln in section.lines]
        assert any("waivers.py" in ln for ln in body)
        assert not any("gates.py" in ln for ln in body)
        assert not any("critic_mode.py" in ln for ln in body)

    def test_the_whole_status_roster_resolves(self):
        ids = [
            _chunk_id_from_item_text(text)
            for _checked, text in _iter_status_section_items(PLAN_FORMS)
        ]
        assert ids == ["01", "2", "A", "1.2", "7"]


# A heading form still outside the matcher (wrong depth), placed after a
# parseable chunk so it bleeds. This is the shape part 2 exists for: whatever
# form arrives next, it must not be silent.
PLAN_UNPARSED = """# Build Plan — Unreadable Heading

## Status

- [ ] Chunk 01: first
- [ ] Chunk 09: unreadable heading

## Build Chunks

### Chunk 01: first

- **Type:** doc-only
- **Trivial because:** it is one line
- **Critic mode:** chunk
- **Deliverables:** `plugin/lib/core.py`

#### Chunk 09: unreadable heading

- **Type:** code
- **Critic mode:** final
- **Deliverables:** `plugin/lib/gates.py`
"""

PLAN_NO_CHUNKS = """# Build Plan — No Chunk Headings

## Status

- [ ] tidy the docs

## Notes

- nothing here announces a chunk
"""


class TestUnparsedChunkHeadingsAreLoud:
    """An unreadable chunk heading must not be reportable as a pass — and an
    absence of chunk headings must stay quiet. Same rule `incompleteness_reason`
    and `_has_unfinished_chunk` apply to an unreadable roster."""

    def test_unparsed_is_reported_for_every_lookup_in_the_plan(self):
        # Including the lookup that SUCCEEDS: chunk 01 is the section that
        # absorbs the unreadable one, so its answer is the corrupted one.
        found_section = _chunk_section_lines(PLAN_UNPARSED, "01")
        assert found_section.found
        assert [text for _n, text in found_section.unparsed] == [
            "#### Chunk 09: unreadable heading"
        ]
        missing_section = _chunk_section_lines(PLAN_UNPARSED, "09")
        assert not missing_section.found
        assert missing_section.unparsed == found_section.unparsed

    def test_a_plan_with_no_chunk_headings_stays_quiet(self):
        section = _chunk_section_lines(PLAN_NO_CHUNKS, "01")
        assert not section.found
        assert section.unparsed == []
        assert buildplan_refs.unparsed_chunk_heading_reason(section) is None

    def test_a_clean_plan_stays_quiet(self):
        assert (
            buildplan_refs.unparsed_chunk_heading_reason(
                _chunk_section_lines(PLAN_FORMS, "01")
            )
            is None
        )

    def test_the_shared_gate_passes_only_a_clean_located_section(self):
        gate = buildplan_refs.chunk_section_gap
        assert gate("01", _chunk_section_lines(PLAN_FORMS, "01")) is None
        # Absent chunk, readable plan: an answer, not a parser failure.
        assert gate("42", _chunk_section_lines(PLAN_FORMS, "42")) == (
            "chunk '42' not found in build-plan"
        )
        # Located, unreadable plan: refused, and it says which line to fix.
        located = gate("01", _chunk_section_lines(PLAN_UNPARSED, "01"))
        assert located is not None and "Chunk 09" in located

    def test_the_reason_names_the_line(self):
        reason = buildplan_refs.unparsed_chunk_heading_reason(
            _chunk_section_lines(PLAN_UNPARSED, "01")
        )
        assert reason is not None
        line_num = PLAN_UNPARSED.splitlines().index("#### Chunk 09: unreadable heading") + 1
        assert f"line {line_num}" in reason and "Chunk 09" in reason

    @pytest.mark.parametrize(
        "line",
        [
            # Possessive prose about a chunk, not a heading for one.
            "## Chunk 01's review, and what rides into Chunk 02",
            # The notes sub-heading form, which is body by design.
            "### Chunk 1 build-session decisions (2026-07-18, finalized)",
            # Not a heading at all.
            "- [ ] Chunk 1.2: a Status item",
        ],
    )
    def test_prose_is_not_an_unparsed_heading(self, line: str):
        plan = f"## Build Chunks\n\n### Chunk 01: a\n\n{line}\n"
        assert _chunk_section_lines(plan, "01").unparsed == []

    def test_a_fenced_example_heading_is_not_an_unparsed_heading(self):
        plan = (
            "## Build Chunks\n\n### Chunk 01: a\n\n"
            "```text\n#### Chunk 09: an example of the wrong depth\n```\n"
        )
        assert _chunk_section_lines(plan, "01").unparsed == []


class TestUnparsedHeadingReachesEveryCaller:
    """The signal is only worth what it reaches. Each consumer of the walk is
    checked at the boundary the rest of the runtime reads."""

    def _plan(self, tmp_path: Path, content: str) -> tuple[Path, Path]:
        prawduct = tmp_path / ".prawduct"
        _write_plan(prawduct, content)
        return prawduct, prawduct / "artifacts" / "build-plan.md"

    def test_ref_parse_refuses_a_resolved_but_untrustworthy_section(
        self, tmp_path: Path
    ):
        prawduct, plan = self._plan(tmp_path, PLAN_UNPARSED)
        refs = buildplan_refs._parse_build_plan_chunk_refs(prawduct, "01", plan)
        assert refs["error"] and "Chunk 09" in refs["error"]
        # And it must not hand back the absorbed chunk's deliverable as its own.
        assert refs["file_paths"] == []

    def test_ref_parse_distinguishes_absent_from_unreadable(self, tmp_path: Path):
        prawduct, plan = self._plan(tmp_path, PLAN_FORMS)
        refs = buildplan_refs._parse_build_plan_chunk_refs(prawduct, "42", plan)
        assert refs["error"] == "chunk '42' not found in build-plan"

    def test_ref_parse_still_passes_a_clean_plan(self, tmp_path: Path):
        prawduct, plan = self._plan(tmp_path, PLAN_FORMS)
        refs = buildplan_refs._parse_build_plan_chunk_refs(prawduct, "1.2", plan)
        assert refs["error"] is None
        assert [entry["ref"] for entry in refs["file_paths"]] == ["plugin/lib/gates.py"]

    def test_type_reader_refuses_rather_than_defaulting(self, tmp_path: Path):
        prawduct, plan = self._plan(tmp_path, PLAN_UNPARSED)
        chunk_type, error = buildplan_refs._parse_build_plan_chunk_type(
            prawduct, "01", plan
        )
        assert chunk_type is None
        assert error and "Chunk 09" in error

    def test_trivial_rationale_reader_refuses(self, tmp_path: Path):
        prawduct, plan = self._plan(tmp_path, PLAN_UNPARSED)
        rationale, error = buildplan_refs._parse_build_plan_chunk_trivial_rationale(
            prawduct, "01", plan
        )
        assert rationale is None
        assert error and "Chunk 09" in error

    def test_critic_mode_reader_declines_rather_than_reading_a_neighbour(
        self, tmp_path: Path
    ):
        """Chunk 01 declares `chunk`; the absorbed chunk 09 declares `final`.
        The reader must return neither — an override it cannot attribute is not
        an override.

        But it must not merely decline, either: a bare "no override" sends
        inference down to rule 4 and a confident `chunk`, on a plan nobody could
        read. So the read carries the reason, and the caller escalates on it.
        """
        prawduct, plan = self._plan(tmp_path, PLAN_UNPARSED)
        read = critic_mode._critic_mode_for_chunk(prawduct, "01", plan)
        assert read.mode is None
        assert read.unreadable and "do not parse as one" in read.unreadable

    def test_critic_mode_reader_still_reads_a_clean_plan(self, tmp_path: Path):
        prawduct, plan = self._plan(tmp_path, PLAN)
        read = critic_mode._critic_mode_for_chunk(prawduct, "01", plan)
        assert read.mode == "chunk"
        assert read.unreadable is None

    def test_critic_mode_reader_reports_a_value_it_did_not_recognise(
        self, tmp_path: Path
    ):
        """The wiring, not just the wording.

        A value the author typed and the reader discarded is a THIRD state: it
        must not escalate the way `unreadable` does (a typo'd mode is no reason
        to spend a heavier review) and must not stay silent the way an absent
        field does (an absent field carries no intent to contradict). Without
        this test the note function could be perfect and never reached.
        """
        prawduct, plan = self._plan(
            tmp_path, PLAN.replace("**Critic mode:** chunk", "**Critic mode:** cumluative")
        )
        read = critic_mode._critic_mode_for_chunk(prawduct, "01", plan)
        assert read.mode is None
        assert read.unreadable is None, "a typo must not escalate to `final`"
        assert read.unrecognized == "cumluative"

    def test_critic_mode_reader_stays_silent_on_an_absent_field(
        self, tmp_path: Path
    ):
        """Absent carries no intent, so it earns no note."""
        prawduct, plan = self._plan(
            tmp_path, PLAN.replace("- **Critic mode:** chunk\n", "")
        )
        read = critic_mode._critic_mode_for_chunk(prawduct, "01", plan)
        assert read.unrecognized is None


# ---------------------------------------------------------------------------
# 2. Consolidation pins — the deleted mirrors must stay deleted
# ---------------------------------------------------------------------------


class TestConsolidationPins:
    """A consolidated walk must stay singular: a copy quietly reintroduced
    in a consumer module is the regression this class exists to catch
    (STH-2K8R)."""

    CONSOLIDATED_OUT_OF_CRITIC_MODE = (
        "_METADATA_PREFIXES",
        "METADATA_PREFIXES",
        "_is_metadata_path",
        "_git_head_sha",
        "_current_chunk_id_from_status",
        "_count_build_plan_chunks",
    )

    def test_critic_mode_defines_no_consolidated_helpers(self):
        for name in self.CONSOLIDATED_OUT_OF_CRITIC_MODE:
            assert name not in vars(critic_mode), (
                f"lib.critic_mode regrew {name!r}; the canonical copy lives in "
                "lib.gitstate / lib.buildplan_refs (STH-2K8R)"
            )

    def test_gates_defines_no_chunk_counter(self):
        assert "_count_build_plan_chunks" not in vars(gates), (
            "lib.gates regrew _count_build_plan_chunks; the canonical copy "
            "lives in lib.buildplan_refs (BLD-6Q1N)"
        )

    def test_walk_skeleton_literals_stay_out_of_consumers(self):
        """The Status / chunk-section walk skeletons are recognizable by their
        anchor literals. Readers in consumer modules must go through the
        shared walkers, so the literals may appear only in
        ``lib/buildplan_refs.py``. The one module that was previously exempt —
        an index-based Status REWRITER, which needed positions rather than a
        reader's view — went with the derived views it regenerated, so the rule
        is now without exception."""
        for mod in ("critic_mode.py", "gates.py"):
            src = (LIB_DIR / mod).read_text()
            assert '"## Status"' not in src, f"lib/{mod} regrew a Status walk"
            assert '"### Chunk "' not in src, f"lib/{mod} regrew a chunk-section walk"

    def test_canonical_helpers_are_what_consumers_reach(self):
        # The names critic_mode now resolves are the canonical objects.
        assert critic_mode.buildplan_refs is buildplan_refs
        assert critic_mode.gitstate is gitstate


# ---------------------------------------------------------------------------
# 3. Porcelain edge cases through the consolidated parse path
# ---------------------------------------------------------------------------


class TestUncommittedCodeFilesPorcelainEdges:
    def test_quoted_path_with_spaces_is_unquoted(self, tmp_path: Path):
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-m", "initial", "--quiet")

        _write(tmp_path, "my doc file.py", "# spaces\n")
        files = critic_mode._get_uncommitted_code_files(tmp_path)
        assert "my doc file.py" in files
        assert not any(f.startswith('"') for f in files)

    def test_rename_yields_destination(self, tmp_path: Path):
        _init_repo(tmp_path)
        _write(tmp_path, "old_name.py", "# code\n")
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-m", "initial", "--quiet")

        _git(tmp_path, "mv", "old_name.py", "new_name.py")
        files = critic_mode._get_uncommitted_code_files(tmp_path)
        assert "new_name.py" in files
        assert "old_name.py" not in files

    def test_metadata_paths_are_excluded(self, tmp_path: Path):
        _init_repo(tmp_path)
        _write(tmp_path, "README.md", "x\n")
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-m", "initial", "--quiet")

        _write(tmp_path, ".prawduct/.session-start", "t\n")
        _write(tmp_path, "src/app.py", "# code\n")
        files = critic_mode._get_uncommitted_code_files(tmp_path)
        assert files == {"src/app.py"}


class TestStatusSectionBoundsStaySingular:
    """The Status-section BOUNDS rule has one home (BLD-6Q1N, extended).

    `lifecycle_repair` grew a second walker with its own heading regex and its
    own next-heading regex. It agreed with the canonical one on every plan in
    the corpus — which is the state the previous FIVE copies were in before they
    diverged, so agreement today is the reason to merge them, not evidence that
    merging is unnecessary. The bounds are what the two readers genuinely share:
    one wants the body with comments skipped, the other wants the comment spans
    by index, and neither can reuse the other's body handling.
    """

    def test_lifecycle_repair_declares_no_status_heading_pattern_of_its_own(self):
        source = (LIB_DIR / "lifecycle_repair.py").read_text(encoding="utf-8")
        for anchor in ("_STATUS_HEADING_RE", "_NEXT_H2_RE"):
            assert anchor not in source, (
                f"lifecycle_repair defines {anchor} again — the Status-section "
                "bounds rule belongs to buildplan_refs.status_section_bounds"
            )

    def test_lifecycle_repair_delegates_to_the_canonical_bounds(self):
        from lib import lifecycle_repair

        assert (
            lifecycle_repair._status_section_span.__module__
            == "lib.lifecycle_repair"
        )
        plan = (
            "# Plan\n\n## Status\n\n- [x] Chunk 01: a\n- [ ] Chunk 02: b\n\n"
            "## Chunks\n\n### Chunk 01: a\n"
        )
        lines = plan.splitlines()
        assert lifecycle_repair._status_section_span(
            lines
        ) == buildplan_refs.status_section_bounds(lines)

    def test_a_h3_chunk_heading_does_not_close_the_status_section(self):
        """Both readers relied on this and neither stated it: `### Chunk 01` is
        not a `## ` heading, so a plan whose Status block is followed by chunk
        H3s keeps its whole roster."""
        lines = "## Status\n- [ ] a\n### Chunk 01: x\n- [ ] b\n## Next\n- [ ] c".splitlines()
        start, end = buildplan_refs.status_section_bounds(lines)
        assert lines[start:end] == ["- [ ] a", "### Chunk 01: x", "- [ ] b"]

    def test_no_status_section_reads_as_absent_not_as_the_whole_document(self):
        assert buildplan_refs.status_section_bounds("# Plan\n- [ ] x".splitlines()) is None


class TestChunkIdFormsReachTheWalk:
    """Two defects, one file, both about an id the code could not accept.

    The dotted-id sort: `unticked_committed_chunk_notice` sorted with `key=int`
    under a comment asserting every id is a digit string. Widening the commit
    and Status matchers falsified both halves, so `int('1.2')` became reachable
    outside the caller's except-set. The first pin written for it was VACUOUS —
    it called the helper directly and asserted `int('1.2')` raises, a property
    of the stdlib — so it stayed green with the fix reverted. This one drives
    the notice.

    The label form: `--chunk "Chunk 01"`, the string the plan's own heading
    prints, never matched a matcher that captures a bare id, and record-lint
    rates an unrunnable deliverable check BLOCKING — so a correct plan bought a
    whole extra review round.
    """

    def test_a_dotted_chunk_id_does_not_raise_through_the_notice(self, tmp_path: Path):
        repo = tmp_path / "repo"
        repo.mkdir()
        (tmp_path / "_home").mkdir()
        _init_repo(repo)
        _write(repo, ".prawduct/project-state.yaml", "base_branch: main\n")
        _write_plan(
            repo / ".prawduct",
            "---\nartifact: build-plan\nscope: dotted\n---\n\n## Status\n\n"
            "- [ ] Chunk 1.2: the dotted one\n",
        )
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "chore: plan")
        _git(repo, "checkout", "-b", "feature/x", "--quiet")
        _write(repo, "src/x.py", "x = 1\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "feat(dotted): land it (Chunk 1.2)")
        # With key=int this raises ValueError instead of returning. The assertion
        # matters as much as the call: `sorted()` never invokes the key on an empty
        # set, so a fixture that stopped producing an intersection would go green
        # while testing nothing.
        notice = buildplan_refs.unticked_committed_chunk_notice(repo)
        assert notice is not None and "1.2" in notice

    def test_dotted_ids_sort_numerically(self):
        """Restored: the deleted pin's non-vacuous half. A string key passes
        everything else green while ordering 1.10 before 1.2."""
        from lib.buildplan_refs import _chunk_sort_key
        assert sorted(["1.10", "1.2", "2", "01"], key=_chunk_sort_key) == [
            "01", "1.2", "1.10", "2"
        ]

    def test_the_normalizer_is_total_on_the_dotted_grammar(self):
        """A leading zero on ANY component, not just the first token.

        `lstrip("0")` read the id as one string, so `"0.2"` normalized to `".2"`
        — truthy, so the `or "0"` fallback could not fire — and `_chunk_sort_key`
        then evaluated `int("")` and raised past an except-set of
        `(OSError, subprocess.SubprocessError)` that cannot catch a ValueError.
        Two of the three callers are unguarded, so a plan numbering `Chunk 0.1`
        tracebacked where the error model promises a diagnostic.

        Every case here is asserted THROUGH the sort as well as the normalizer:
        normalizing correctly and still raising downstream is the failure that
        actually reached users, and a pin on the string alone would not see it.
        """
        from lib.buildplan_refs import _chunk_sort_key, _normalize_chunk_id

        for raw, norm, key in (
            ("0.2", "0.2", (0, 2)),
            ("00.2", "0.2", (0, 2)),
            ("1.02", "1.2", (1, 2)),
            ("Chunk 0.1", "0.1", (0, 1)),
            ("00", "0", (0,)),
            ("01", "1", (1,)),
            ("1.10", "1.10", (1, 10)),
        ):
            got = _normalize_chunk_id(raw)
            assert got == norm, f"{raw!r} normalized to {got!r}, expected {norm!r}"
            assert _chunk_sort_key(got) == key, (
                f"{raw!r} normalizes to {got!r} which does not sort — the "
                "normalizer and the sort disagree about the id grammar"
            )

    def test_one_normalizer_owns_the_zero_trim(self):
        """The docstring claims to be the only chunk-id normalizer in the tree;
        this is what makes the claim true rather than aspirational.

        Two callers had `lstrip("0") or "0"` inline, so both sides of the
        `unticked & committed` intersection agreed on a wrong answer — agreement
        that reads as corroboration. A second copy is how the class comes back.
        """
        source = (
            Path(buildplan_refs.__file__).read_text(encoding="utf-8").split("\n")
        )
        offenders = [
            (i + 1, ln.strip())
            for i, ln in enumerate(source)
            if 'lstrip("0")' in ln and "def _normalize_chunk_id" not in ln
        ]
        # The one legitimate site is inside _normalize_chunk_id's own body.
        outside = [
            (num, text) for num, text in offenders
            if not text.startswith("return \".\".join(")
            and not text.startswith("``lstrip")
        ]
        assert not outside, (
            f"a second zero-trim exists outside the one normalizer: {outside}. "
            "Route the caller through _normalize_chunk_id instead."
        )

    def test_the_type_error_discriminator_is_producer_owned(self, tmp_path):
        """The session-end surfacing recognizes BOTH producers' real output.

        `cmd_stop` used to match `"do not parse as one" in type_error` and
        `type_error.startswith("unknown type:")` — a cross-module coupling on two
        literal prose substrings, with nothing that fails when the prose is
        reworded. Both messages are long, narrative, and edited whenever the
        parser's advice improves; rewording either silently disabled the ONLY
        session-end surfacing of a plan heading nothing can parse, and the author
        of the broken plan never learned which line to fix.

        **The strings here are PRODUCED, never written by hand.** A test that
        hand-writes the sentence it expects re-creates the coupling one layer up:
        it goes green against a producer that has drifted, because the fixture
        drifted with the assertion instead of with the code.
        """
        from lib.buildplan_refs import (
            ChunkSection,
            _parse_build_plan_chunk_type,
            is_reportable_type_error,
            unparsed_chunk_heading_reason,
        )

        unparsed = unparsed_chunk_heading_reason(
            ChunkSection(False, [], [(7, "### Chunk 02 & 03 — combined")])
        )
        assert unparsed, "the fixture stopped producing an unparsed reason"
        assert is_reportable_type_error(unparsed), (
            "the predicate no longer recognizes its own module's unparsed-heading "
            "reason — the session-end surfacing is silently off"
        )

        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        plan = prawduct / "plan.md"
        plan.write_text(
            "### Chunk 01: a chunk\n\n- **Type:** nonsense-value\n",
            encoding="utf-8",
        )
        chunk_type, type_error = _parse_build_plan_chunk_type(
            prawduct, "01", plan_path=plan
        )
        assert chunk_type is None and type_error, (
            "the fixture stopped producing an unknown-type error"
        )
        assert is_reportable_type_error(type_error), (
            "the predicate no longer recognizes an unrecognized Type: value"
        )

        # And it stays quiet on the states that are not authoring defects, or the
        # surfacing becomes noise at every session end and gets muted wholesale.
        assert not is_reportable_type_error(None)
        assert not is_reportable_type_error("")

    def test_the_hook_asks_the_predicate_rather_than_the_prose(self):
        """Where the rule is enforced is the substance, so it is pinned.

        The predicate only helps if the consumer calls it; a hook that keeps its
        own substring match is unaffected by the producer owning the string.
        """
        hook = (
            Path(__file__).resolve().parent.parent
            / "plugin" / "bin" / "prawduct-hook"
        ).read_text(encoding="utf-8")
        assert "is_reportable_type_error(" in hook, (
            "the stop hook no longer asks buildplan_refs whether a Type: error is "
            "reportable — it is back to matching prose it does not own"
        )
        for literal in ('"do not parse as one"', '"unknown type:"'):
            assert literal not in hook, (
                f"the hook matches {literal} directly again; the producer owns "
                "that string and the consumer must ask, not grep"
            )

    def test_the_heading_label_is_an_accepted_chunk_id(self):
        """`--chunk "Chunk 01"` must find what `--chunk 01` finds."""
        bare = _chunk_section_lines(PLAN, "01")
        labelled = _chunk_section_lines(PLAN, "Chunk 01")
        assert labelled.found and labelled.found == bare.found
        assert [ln for _n, ln in labelled.lines] == [ln for _n, ln in bare.lines]
        assert _chunk_section_lines(PLAN, "chunk 2").found


class TestDeliverableCheckGaps:
    """#642 — a plan the chunk deliverable check cannot grade must SAY SO at dispatch.

    Two routes disabled the check for a plan's whole life, and the reason it
    stayed open through one fix is that they fail differently. A plan with no
    frontmatter `scope:` reports `chunk-ref-missing unchecked — …` into the
    dispatch manifest, which is real but reads as a pass to anyone who does not
    also read the caveat line. A plan whose chunks are list items under a
    `## Chunks` heading matches no heading pattern at all, so there is no
    offending line to name and the check reports *nothing*.

    Either is sufficient alone, which is why both are asserted separately rather
    than through one composite fixture: fixing one and calling the item closed is
    exactly what happened the first time.
    """

    _CONFORMING = (
        "---\n"
        "artifact: build-plan\n"
        "scope: some-scope\n"
        "---\n\n"
        "## Status\n\n"
        "- [ ] Chunk 01: Do the thing\n\n"
        "## Build Chunks\n\n"
        "### Chunk 01: Do the thing\n\n"
        "- **Deliverables:** `plugin/lib/thing.py`\n"
    )

    def _plan(self, tmp_path: Path, content: str) -> Path:
        plan = tmp_path / "build-plan-x.md"
        plan.write_text(content)
        return plan

    def test_conforming_plan_is_silent(self, tmp_path: Path):
        """The no-false-positive case, first: a signal whose first firing is
        wrong is one its readers learn to ignore."""
        plan = self._plan(tmp_path, self._CONFORMING)
        assert buildplan_refs.deliverable_check_gaps(tmp_path, plan) == []

    def test_missing_frontmatter_scope_is_named(self, tmp_path: Path):
        plan = self._plan(
            tmp_path, self._CONFORMING.replace("scope: some-scope\n", "")
        )
        gaps = buildplan_refs.deliverable_check_gaps(tmp_path, plan)
        assert len(gaps) == 1, gaps
        assert "`scope:`" in gaps[0]
        assert "build-plan-x.md" in gaps[0], "name the file that would be graded"

    def test_list_item_chunks_are_named(self, tmp_path: Path):
        """The wholly-silent route: `- Chunk 01: …` under `## Chunks` matches
        neither the heading nor the announce pattern, so nothing downstream has
        a line to report."""
        plan = self._plan(
            tmp_path,
            "---\nartifact: build-plan\nscope: some-scope\n---\n\n"
            "## Status\n\n- [ ] Chunk 01: Do the thing\n\n"
            "## Chunks\n\n"
            "- Chunk 01: Do the thing\n"
            "  - Deliverables: `plugin/lib/thing.py`\n",
        )
        gaps = buildplan_refs.deliverable_check_gaps(tmp_path, plan)
        assert len(gaps) == 1, gaps
        assert "no parseable chunk heading" in gaps[0]

    def test_both_routes_reported_together(self, tmp_path: Path):
        """Either cause is sufficient alone, so a plan with both gets both —
        fixing one and re-dispatching must not look like progress to a clean
        result."""
        plan = self._plan(
            tmp_path,
            "## Status\n\n- [ ] Chunk 01: Do the thing\n\n"
            "## Chunks\n\n- Chunk 01: Do the thing\n",
        )
        assert len(buildplan_refs.deliverable_check_gaps(tmp_path, plan)) == 2

    def test_absent_or_unreadable_plan_is_not_this_check_s_business(
        self, tmp_path: Path
    ):
        """The resolver reports a plan it could not find; this must not add a
        second, differently-worded complaint about the same absence."""
        assert buildplan_refs.deliverable_check_gaps(tmp_path, None) == []
        assert buildplan_refs.deliverable_check_gaps(tmp_path, tmp_path / "nope.md") == []

    def test_unresolvable_plan_is_found_by_the_fallback_scan(self, tmp_path: Path):
        """The main case, and the one an earlier draft of this missed entirely.

        A plan declaring neither `scope:` nor `branch:` does not RESOLVE — because
        of the very gap being reported. Checking only the resolver's answer means
        `None` comes back and the signal goes quiet exactly where #642 says it
        must fire. Verified against a real dispatch before this test was written:
        the note was absent.
        """
        prawduct = tmp_path / ".prawduct"
        (prawduct / "artifacts").mkdir(parents=True)
        (prawduct / "artifacts" / "build-plan-thing.md").write_text(
            "## Chunks\n\n- Chunk 01: Do it\n"
        )
        gaps = buildplan_refs.deliverable_check_gaps(prawduct, None)
        assert len(gaps) == 2, gaps
        assert any("build-plan-thing.md" in g for g in gaps), (
            "an unresolved plan must still be named, or the operator cannot act"
        )

    def test_a_nested_unresolvable_plan_is_reported_by_name(self, tmp_path: Path):
        """The fallback scan, end to end, on a layout the flat glob could not see.

        This is the fixture the review named as required: `TestDeliverableCheckGaps`
        wrote only flat plans, which the old `artifacts.glob("build-plan-*.md")`
        also found, so nothing separated the fix from the code it replaced.
        """
        prawduct = tmp_path / ".prawduct"
        nested = prawduct / "artifacts" / "plans" / "007" / "build-plan.md"
        nested.parent.mkdir(parents=True)
        nested.write_text("## Chunks\n\n- Chunk 01: Do it\n")

        gaps = buildplan_refs.deliverable_check_gaps(prawduct, None)
        assert len(gaps) == 2, gaps
        assert all("plans/007/build-plan.md" in g for g in gaps), (
            "a nested plan must be named by its PATH — recursion makes "
            f"`build-plan.md` a near-certain collision: {gaps}"
        )

    def test_an_unreadable_plan_is_reported_at_the_dispatch_channel(
        self, tmp_path: Path
    ):
        """Nothing else on this path reports it.

        An earlier version swallowed the decode error, reasoning that
        `plan_index.unreadable_candidates` covers the case. It does — for the
        doctor, its only caller. `begin_review` never calls it, so at the
        dispatch channel an undecodable plan was reported by no one.
        """
        prawduct = tmp_path / ".prawduct"
        (prawduct / "artifacts").mkdir(parents=True)
        (prawduct / "artifacts" / "build-plan-binary.md").write_bytes(
            b"\xff\xfe\x00\x00not utf-8"
        )
        gaps = buildplan_refs.deliverable_check_gaps(prawduct, None)
        assert len(gaps) == 1, gaps
        assert "could not be read" in gaps[0]
        assert "build-plan-binary.md" in gaps[0]

    def test_no_plan_at_all_is_silent(self, tmp_path: Path):
        """An absent plan is the resolver's report to make, not this one's — two
        differently-worded complaints about one absence is noise."""
        prawduct = tmp_path / ".prawduct"
        (prawduct / "artifacts").mkdir(parents=True)
        assert buildplan_refs.deliverable_check_gaps(prawduct, None) == []
        assert buildplan_refs.deliverable_check_gaps(tmp_path / "nothing", None) == []


class TestChunkRefGapForUnparseablePlan:
    """#642 Route 2, at the manifest — the half `deliverable_check_gaps` does not cover.

    The dispatch note tells the OPERATOR at `critic-begin`. This is the other
    reader: `record_lint` rides the manifest into the review itself, and its
    `chunk_id is None` branch returned `[], None, None, None` — a null count
    indistinguishable from a healthy plan whose chunks are all ticked. Unlike
    every other failure on that path it emitted no `unchecked` line at all, so
    nothing downstream had a word to carry.

    Both causes of "no chunk in scope" must stay distinguishable: a finished
    plan is silent, an unparseable one is not.
    """

    def _plan(self, tmp_path: Path, content: str) -> Path:
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        plan = artifacts / "build-plan-x.md"
        plan.write_text(content)
        return plan

    def test_a_finished_plan_stays_silent(self, tmp_path: Path):
        """The no-false-positive half, and the reason this is a predicate rather
        than an unconditional complaint: every chunk ticked is a normal, healthy
        end state that must not start reporting a gap."""
        plan = self._plan(
            tmp_path,
            "---\nartifact: build-plan\nscope: s\n---\n\n"
            "## Status\n\n- [x] Chunk 01: Done\n\n"
            "## Build Chunks\n\n### Chunk 01: Done\n\n- **Deliverables:** none\n",
        )
        assert buildplan_refs.plan_has_parseable_chunk_heading(plan) is True

    def test_an_unparseable_plan_is_distinguishable(self, tmp_path: Path):
        plan = self._plan(
            tmp_path, "## Status\n\n- [x] Chunk 01: Done\n\n## Chunks\n\n- Chunk 01: Done\n"
        )
        assert buildplan_refs.plan_has_parseable_chunk_heading(plan) is False

    def test_unreadable_is_a_third_answer_not_a_verdict(self, tmp_path: Path):
        """`None`, never `False`. Collapsing them would report a confident
        structural claim about a file that was never opened — and the caller
        branches on `is False` precisely so it cannot."""
        assert buildplan_refs.plan_has_parseable_chunk_heading(None) is None
        assert buildplan_refs.plan_has_parseable_chunk_heading(
            tmp_path / "absent.md"
        ) is None


class TestIterLivePlanFiles:
    """`plan_index.iter_live_plan_files` — four behaviours, none of which a flat
    fixture can tell apart from the glob it replaced.

    That is the point of this class. A flat fixture cannot distinguish this
    function from the flat `artifacts.glob("build-plan-*.md")` it replaced, so
    every case below is nested, scoped, or archived on purpose.
    `display_path`'s own docstring records the same lesson from the same module:
    "every fixture here is flat, so no fixture could have shown it."
    """

    def _plan(self, path: Path, scope: str | None = "s") -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        fm = f"---\nartifact: build-plan\n{f'scope: {scope}' if scope else ''}\n---\n"
        path.write_text(fm + "\n## Build Chunks\n\n### Chunk 01: Do it\n")
        return path

    def test_finds_a_nested_plan_a_flat_glob_would_miss(self, tmp_path: Path):
        """The regression the function exists for: repos laying plans out as
        `artifacts/plans/<id>/build-plan.md`. A flat glob sees none of them, and
        the surveyed fleet carries 16 nested plans per repo."""
        self._plan(tmp_path / "plans" / "007" / "build-plan.md")
        found = plan_index.iter_live_plan_files(tmp_path)
        assert [p.name for p in found] == ["build-plan.md"]
        assert "007" in str(found[0]), "the nested path must be preserved"

    def test_never_descends_an_archive_subtree(self, tmp_path: Path):
        """An archived plan is history, not a live assertion — and it must not
        be reported as a live plan with gaps."""
        self._plan(tmp_path / "build-plan-live.md")
        self._plan(tmp_path / "archive" / "build-plan-old.md")
        self._plan(tmp_path / "plans" / "9" / "archive" / "build-plan-nested-old.md")
        names = {p.name for p in plan_index.iter_live_plan_files(tmp_path)}
        assert names == {"build-plan-live.md"}

    def test_typed_by_frontmatter_or_filename_but_not_by_body_text(
        self, tmp_path: Path
    ):
        """Both routes are needed and a body scan is not one of them.

        A plan with NO frontmatter has no declared type — and that is exactly
        the shape being hunted — so the filename convention is the fallback. But
        a body substring scan pulled in two design notes in this repo that merely
        MENTION the string, so typing reads frontmatter only.
        """
        (tmp_path / "build-plan-no-frontmatter.md").write_text("## Chunks\n\n- Chunk 01\n")
        self._plan(tmp_path / "oddly-named-plan.md")
        (tmp_path / "design-note.md").write_text(
            "# Note\n\nWe considered `artifact: build-plan` here but chose otherwise.\n"
        )
        names = {p.name for p in plan_index.iter_live_plan_files(tmp_path)}
        assert "build-plan-no-frontmatter.md" in names, "filename fallback"
        assert "oddly-named-plan.md" in names, "declared type wins over the name"
        assert "design-note.md" not in names, "a body mention is not a declaration"

    def test_a_file_declaring_another_artifact_type_is_excluded(self, tmp_path: Path):
        """On its own word, regardless of a plan-shaped filename."""
        (tmp_path / "build-plan-not-really.md").write_text(
            "---\nartifact: discovery\nscope: s\n---\n\n# Not a plan\n"
        )
        assert plan_index.iter_live_plan_files(tmp_path) == []

    def test_an_unreadable_plan_is_retained_for_the_caller_to_report(
        self, tmp_path: Path
    ):
        """Unreadable is not 'not a plan'. Retaining it is only worth doing
        because `_plan_gaps` now reports it — an earlier pairing retained the
        file and then returned [] for it, so the stated intent was dead."""
        bad = tmp_path / "build-plan-binary.md"
        bad.write_bytes(b"\xff\xfe\x00\x00not utf-8 at all")
        assert [p.name for p in plan_index.iter_live_plan_files(tmp_path)] == [
            "build-plan-binary.md"
        ]

    def test_absent_artifacts_dir_is_empty_not_an_error(self, tmp_path: Path):
        assert plan_index.iter_live_plan_files(tmp_path / "nothing") == []
