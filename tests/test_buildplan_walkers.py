"""Tests for the shared build-plan walkers + consolidation pins (STH-2K8R / BLD-6Q1N).

Three concerns:

1. Direct unit coverage of the canonical walkers in ``lib.buildplan_refs`` —
   ``_iter_status_section_lines`` / ``_iter_status_section_items`` (the one
   Status-section reader walk) and ``_chunk_section_lines`` (the one
   chunk-section walk) — plus the helpers built on them
   (``_count_build_plan_chunks``, ``_chunk_ids_in_status_order``).

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

from lib import buildplan_refs, critic_mode, gates, gitstate
from lib.buildplan_refs import (
    _chunk_id_from_item_text,
    _chunk_ids_in_status_order,
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

    def test_chunk_ids_in_status_order(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        _write_plan(prawduct, PLAN)
        assert _chunk_ids_in_status_order(prawduct) == ["01", "02", "03"]

    def test_non_chunk_items_are_skipped_in_ids(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        _write_plan(
            prawduct,
            "## Status\n- [ ] Chunk 01: a\n- [ ] tidy the docs\n- [x] Chunk 02: b\n",
        )
        assert _chunk_ids_in_status_order(prawduct) == ["01", "02"]


class TestChunkSectionLines:
    def test_leading_zero_tolerance_both_directions(self):
        # Plan heading "### Chunk 1:" found via id "01"; "### Chunk 02:" via "2".
        found, lines = _chunk_section_lines(PLAN, "01")
        assert found
        assert any("**Critic mode:** chunk" in ln for _n, ln in lines)
        found2, lines2 = _chunk_section_lines(PLAN, "2")
        assert found2
        assert any("**Type:** doc-only" in ln for _n, ln in lines2)

    def test_fenced_block_is_dropped(self):
        found, lines = _chunk_section_lines(PLAN, "1")
        assert found
        body = [ln for _n, ln in lines]
        assert not any("cumulative" in ln for ln in body)
        assert any("body line after fence" in ln for ln in body)

    def test_stops_at_sibling_chunk(self):
        _found, lines = _chunk_section_lines(PLAN, "1")
        assert not any("doc-only" in ln for _n, ln in lines)

    def test_stops_at_next_h2(self):
        _found, lines = _chunk_section_lines(PLAN, "02")
        assert not any("not a status item" in ln for _n, ln in lines)

    def test_not_found(self):
        found, lines = _chunk_section_lines(PLAN, "42")
        assert not found
        assert lines == []

    def test_line_numbers_are_one_based_into_content(self):
        _found, lines = _chunk_section_lines(PLAN, "1")
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
        found, lines = _chunk_section_lines(PLAN_H2, "1")
        assert found
        body = [ln for _n, ln in lines]
        assert any("lib/research_trace.py" in ln for ln in body)

    def test_leading_zero_tolerance_on_h2_form(self):
        # "## Chunk 2 (…)" located via id "02".
        found, lines = _chunk_section_lines(PLAN_H2, "02")
        assert found
        assert any("docs/obs.md" in ln for _n, ln in lines)

    def test_notes_subheading_does_not_end_section(self):
        # "### Chunk 1 build-session decisions" has no separator after the id,
        # so it is body, not a sibling boundary — chunk 1 keeps its later refs.
        _found, lines = _chunk_section_lines(PLAN_H2, "1")
        body = [ln for _n, ln in lines]
        assert any("lib/still_chunk_one.py" in ln for ln in body)
        # …but the genuine sibling "## Chunk 2" still ends it.
        assert not any("docs/obs.md" in ln for ln in body)

    def test_h2_sibling_boundary_still_stops(self):
        _found, lines = _chunk_section_lines(PLAN_H2, "2")
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
        # Takes the PROJECT dir, not `.prawduct/` — resolving "current" is
        # git-aware on a views_enabled repo (BLD-7K3Q), so the repo root is
        # part of the question.
        _write_plan(tmp_path / ".prawduct", PLAN_H2)
        assert _current_chunk_id_from_status(tmp_path) == "1"

    def test_chunk_ids_in_status_order_h2(self, tmp_path: Path):
        prawduct = tmp_path / ".prawduct"
        _write_plan(prawduct, PLAN_H2)
        assert _chunk_ids_in_status_order(prawduct) == ["1", "2"]


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
        "_chunk_ids_in_status_order",
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
        ``lib/buildplan_refs.py`` (and ``lib/views.py``'s index-based Status
        REWRITER, which is deliberately separate)."""
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
