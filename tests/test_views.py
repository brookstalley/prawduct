"""Tests for tools/lib/views.py + product-hook `regen-views` subcommand.

The views module derives the build-plan `## Status` block from change-log
tagged entries. The product-hook subcommand is a thin wrapper that reads
project-state.yaml for the `views_enabled` opt-in, runs the builder, and
writes back to build-plan.md.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

from lib import views  # noqa: E402

HOOK_PATH = Path(__file__).resolve().parent.parent / "tools" / "product-hook"


# =============================================================================
# Pure-function tests — parser and builder
# =============================================================================


class TestParseTagLine:
    def test_simple_pairs(self):
        tags = views.parse_tag_line("release=v1.4.0 | status=shipped")
        assert tags == {"release": "v1.4.0", "status": "shipped"}

    def test_chunks_split_into_list(self):
        tags = views.parse_tag_line("chunks=00,01,02 | status=shipped")
        assert tags["chunks"] == ["00", "01", "02"]
        assert tags["status"] == "shipped"

    def test_single_chunk_still_a_list(self):
        tags = views.parse_tag_line("chunks=05")
        assert tags["chunks"] == ["05"]

    def test_extra_whitespace_tolerated(self):
        tags = views.parse_tag_line("  chunks = 00 , 01  |  status = shipped  ")
        assert tags["chunks"] == ["00", "01"]
        assert tags["status"] == "shipped"

    def test_unknown_keys_preserved(self):
        tags = views.parse_tag_line("custom=foo | release=v1.4.0")
        assert tags["custom"] == "foo"
        assert tags["release"] == "v1.4.0"

    def test_empty_pairs_skipped(self):
        tags = views.parse_tag_line("status=shipped | | release=v1.4")
        assert tags == {"status": "shipped", "release": "v1.4"}

    def test_malformed_pair_without_equals_skipped(self):
        tags = views.parse_tag_line("status=shipped | broken | release=v1.4")
        assert tags == {"status": "shipped", "release": "v1.4"}


class TestParseChangeLog:
    def test_tag_line_directly_after_h2(self):
        content = textwrap.dedent(
            """\
            # Change Log

            ## 2026-05-18: v1.4 Wave 1 (v1.3.17)
            <!-- prawduct: chunks=00,01 | release=v1.3.17 | status=shipped -->

            **Why:** ...
            """
        )
        entries = views.parse_change_log(content)
        assert len(entries) == 1
        assert entries[0].title.startswith("2026-05-18:")
        assert entries[0].tags["chunks"] == ["00", "01"]
        assert entries[0].tags["status"] == "shipped"

    def test_tag_line_after_blank_line(self):
        content = textwrap.dedent(
            """\
            ## 2026-05-18: Release

            <!-- prawduct: chunks=03 | status=shipped -->

            Body.
            """
        )
        entries = views.parse_change_log(content)
        assert entries[0].tags.get("chunks") == ["03"]

    def test_untagged_entry_has_empty_tags(self):
        content = textwrap.dedent(
            """\
            ## 2026-04-01: Old entry

            **Why:** Pre-tagging era.
            """
        )
        entries = views.parse_change_log(content)
        assert len(entries) == 1
        assert entries[0].tags == {}

    def test_multiple_entries(self):
        content = textwrap.dedent(
            """\
            ## 2026-05-18: New entry
            <!-- prawduct: chunks=05 | status=shipped -->

            ## 2026-05-10: Older entry
            <!-- prawduct: chunks=01 | status=shipped -->

            ## 2026-05-01: Untagged
            """
        )
        entries = views.parse_change_log(content)
        assert len(entries) == 3
        assert entries[0].shipped_chunks == ["05"]
        assert entries[1].shipped_chunks == ["01"]
        assert entries[2].shipped_chunks == []

    def test_body_paragraph_before_tag_line_blocks_parse(self):
        """If a prose paragraph appears before the tag line, the tag line is not
        an entry header — it's later body content. parse_change_log only looks
        forward from the H2 to the first non-blank line."""
        content = textwrap.dedent(
            """\
            ## 2026-05-18: Entry

            **Why:** This entry has no tag line.

            <!-- prawduct: chunks=99 | status=shipped -->
            """
        )
        entries = views.parse_change_log(content)
        assert entries[0].tags == {}

    def test_non_shipped_status_returns_no_chunks(self):
        content = "## X\n<!-- prawduct: chunks=07 | status=in-progress -->\n"
        entries = views.parse_change_log(content)
        assert entries[0].shipped_chunks == []
        assert entries[0].tags["status"] == "in-progress"


class TestCollectShippedChunks:
    def test_aggregates_across_entries(self):
        entries = [
            views.ChangeLogEntry(
                title="a", tags={"chunks": ["00", "01"], "status": "shipped"}
            ),
            views.ChangeLogEntry(
                title="b", tags={"chunks": ["02"], "status": "shipped"}
            ),
            views.ChangeLogEntry(title="c", tags={}),
        ]
        assert views.collect_shipped_chunks(entries) == {"00", "01", "02"}

    def test_ignores_non_shipped(self):
        entries = [
            views.ChangeLogEntry(
                title="a", tags={"chunks": ["05"], "status": "in-progress"}
            ),
            views.ChangeLogEntry(
                title="b", tags={"chunks": ["06"], "status": "deferred"}
            ),
        ]
        assert views.collect_shipped_chunks(entries) == set()


class TestExtractStatusSection:
    def test_finds_section(self):
        content = textwrap.dedent(
            """\
            # Plan
            ## Status
            - [ ] Chunk 00: A
            - [x] Chunk 01: B
            Context: foo.
            ## Next
            irrelevant
            """
        )
        start, end, section = views.extract_status_section(content)
        assert start == 1
        assert end == 5
        assert section[0] == "## Status"
        assert "Chunk 00" in section[1]

    def test_missing_section_returns_negative(self):
        start, end, section = views.extract_status_section("# Plan\n\nNo status here.\n")
        assert start == -1
        assert section == []

    def test_section_to_end_of_file_when_no_following_h2(self):
        content = "## Status\n- [ ] Chunk 00: A\n"
        start, end, section = views.extract_status_section(content)
        assert start == 0
        assert end == 2
        assert section == ["## Status", "- [ ] Chunk 00: A"]


class TestRegenerateStatusSection:
    def test_flips_to_shipped(self):
        section = ["## Status", "- [ ] Chunk 00: A", "- [ ] Chunk 01: B"]
        new, changes = views.regenerate_status_section(section, {"00"})
        assert new == ["## Status", "- [x] Chunk 00: A", "- [ ] Chunk 01: B"]
        assert changes == [("00", " ", "x")]

    def test_flips_back_to_unshipped_when_tag_removed(self):
        section = ["- [x] Chunk 05: A"]
        new, changes = views.regenerate_status_section(section, set())
        assert new == ["- [ ] Chunk 05: A"]
        assert changes == [("05", "x", " ")]

    def test_idempotent_when_already_correct(self):
        section = ["- [x] Chunk 00: A", "- [ ] Chunk 01: B"]
        new, changes = views.regenerate_status_section(section, {"00"})
        assert new == section
        assert changes == []

    def test_preserves_context_and_comments(self):
        section = [
            "## Status",
            "<!-- intro -->",
            "",
            "- [ ] Chunk 00: A",
            "",
            "Context: hand-written notes.",
        ]
        new, _ = views.regenerate_status_section(section, {"00"})
        assert new[0] == "## Status"
        assert new[1] == "<!-- intro -->"
        assert new[2] == ""
        assert new[3] == "- [x] Chunk 00: A"
        assert new[4] == ""
        assert new[5] == "Context: hand-written notes."

    def test_capital_x_normalized(self):
        section = ["- [X] Chunk 00: A"]
        # Capital X means shipped (case-insensitive); if tag set has it, no diff.
        new, changes = views.regenerate_status_section(section, {"00"})
        assert new == ["- [x] Chunk 00: A"]
        assert changes == []  # case normalization doesn't count as a change


class TestBuildStatusView:
    def _scenario(self, *, change_log: str, build_plan: str):
        return views.build_status_view(change_log, build_plan)

    def test_no_change_returns_none(self):
        change_log = (
            "## 2026-05-18: rel\n"
            "<!-- prawduct: chunks=00 | status=shipped -->\n"
        )
        build_plan = "## Status\n- [x] Chunk 00: A\n## Next\n"
        new, changes = self._scenario(change_log=change_log, build_plan=build_plan)
        assert new is None
        assert changes == []

    def test_flips_checkboxes_from_tags(self):
        change_log = (
            "## 2026-05-18: rel\n"
            "<!-- prawduct: chunks=00,01 | status=shipped -->\n"
        )
        build_plan = (
            "## Status\n- [ ] Chunk 00: A\n- [ ] Chunk 01: B\n- [ ] Chunk 02: C\n## End\n"
        )
        new, changes = self._scenario(change_log=change_log, build_plan=build_plan)
        assert new is not None
        assert "- [x] Chunk 00: A" in new
        assert "- [x] Chunk 01: B" in new
        assert "- [ ] Chunk 02: C" in new
        assert {c[0] for c in changes} == {"00", "01"}

    def test_preserves_trailing_newline(self):
        change_log = "## X\n<!-- prawduct: chunks=00 | status=shipped -->\n"
        build_plan = "## Status\n- [ ] Chunk 00: A\n"
        new, _ = self._scenario(change_log=change_log, build_plan=build_plan)
        assert new.endswith("\n")

    def test_missing_status_section_returns_none(self):
        new, changes = self._scenario(change_log="## X\n", build_plan="# No status\n")
        assert new is None
        assert changes == []


class TestIsViewsEnabled:
    def test_true_when_top_level_true(self, tmp_path: Path):
        p = tmp_path / "project-state.yaml"
        p.write_text("classification:\n  domain: util\nviews_enabled: true\n")
        assert views.is_views_enabled(p) is True

    def test_false_when_top_level_false(self, tmp_path: Path):
        p = tmp_path / "project-state.yaml"
        p.write_text("views_enabled: false\n")
        assert views.is_views_enabled(p) is False

    def test_false_when_missing_key(self, tmp_path: Path):
        p = tmp_path / "project-state.yaml"
        p.write_text("classification:\n  domain: util\n")
        assert views.is_views_enabled(p) is False

    def test_false_when_file_missing(self, tmp_path: Path):
        assert views.is_views_enabled(tmp_path / "nope.yaml") is False

    def test_indented_key_ignored(self, tmp_path: Path):
        """A nested `views_enabled: true` under another key must not flip the
        top-level switch — only column-0 keys count."""
        p = tmp_path / "project-state.yaml"
        p.write_text("nested:\n  views_enabled: true\n")
        assert views.is_views_enabled(p) is False

    def test_comments_ignored(self, tmp_path: Path):
        p = tmp_path / "project-state.yaml"
        p.write_text("# views_enabled: true\nviews_enabled: false\n")
        assert views.is_views_enabled(p) is False


# =============================================================================
# Integration tests — product-hook regen-views subcommand
# =============================================================================


def _make_product_repo(
    tmp_path: Path,
    *,
    views_enabled: bool,
    change_log: str,
    build_plan: str,
) -> Path:
    """Build a minimal product repo skeleton for regen-views subcommand tests."""
    product = tmp_path / "product"
    (product / ".prawduct" / "artifacts").mkdir(parents=True)
    state = "views_enabled: true\n" if views_enabled else "views_enabled: false\n"
    (product / ".prawduct" / "project-state.yaml").write_text(state)
    (product / ".prawduct" / "change-log.md").write_text(change_log)
    (product / ".prawduct" / "artifacts" / "build-plan.md").write_text(build_plan)
    return product


def _run_regen(product_dir: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(product_dir)}
    return subprocess.run(
        ["python3", str(HOOK_PATH), "regen-views"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(product_dir),
        timeout=20,
    )


class TestRegenViewsCommand:
    def test_no_op_when_views_disabled(self, tmp_path: Path):
        product = _make_product_repo(
            tmp_path,
            views_enabled=False,
            change_log=(
                "## 2026-05-18: rel\n"
                "<!-- prawduct: chunks=00 | status=shipped -->\n"
            ),
            build_plan="## Status\n- [ ] Chunk 00: A\n",
        )
        result = _run_regen(product)
        assert result.returncode == 0
        assert "disabled" in result.stdout.lower()
        # Build plan untouched.
        assert (
            "- [ ] Chunk 00: A"
            in (product / ".prawduct" / "artifacts" / "build-plan.md").read_text()
        )

    def test_flips_checkboxes_when_enabled(self, tmp_path: Path):
        product = _make_product_repo(
            tmp_path,
            views_enabled=True,
            change_log=(
                "## 2026-05-18: rel\n"
                "<!-- prawduct: chunks=00,01 | status=shipped -->\n"
            ),
            build_plan=(
                "## Status\n"
                "- [ ] Chunk 00: A\n"
                "- [ ] Chunk 01: B\n"
                "- [ ] Chunk 02: C\n"
                "Context: notes.\n"
            ),
        )
        result = _run_regen(product)
        assert result.returncode == 0, result.stderr
        new_plan = (product / ".prawduct" / "artifacts" / "build-plan.md").read_text()
        assert "- [x] Chunk 00: A" in new_plan
        assert "- [x] Chunk 01: B" in new_plan
        assert "- [ ] Chunk 02: C" in new_plan
        assert "Context: notes." in new_plan

    def test_idempotent_second_run_no_changes(self, tmp_path: Path):
        product = _make_product_repo(
            tmp_path,
            views_enabled=True,
            change_log=(
                "## 2026-05-18: rel\n"
                "<!-- prawduct: chunks=00 | status=shipped -->\n"
            ),
            build_plan="## Status\n- [x] Chunk 00: A\n",
        )
        result = _run_regen(product)
        assert result.returncode == 0
        assert "no changes" in result.stdout.lower() or "already" in result.stdout.lower()

    def test_missing_change_log_returns_nonzero(self, tmp_path: Path):
        product = tmp_path / "product"
        (product / ".prawduct" / "artifacts").mkdir(parents=True)
        (product / ".prawduct" / "project-state.yaml").write_text("views_enabled: true\n")
        (product / ".prawduct" / "artifacts" / "build-plan.md").write_text(
            "## Status\n- [ ] Chunk 00: A\n"
        )
        # change-log.md intentionally missing.
        result = _run_regen(product)
        assert result.returncode != 0
        assert "change-log" in result.stderr.lower()

    def test_missing_build_plan_returns_nonzero(self, tmp_path: Path):
        product = tmp_path / "product"
        (product / ".prawduct" / "artifacts").mkdir(parents=True)
        (product / ".prawduct" / "project-state.yaml").write_text("views_enabled: true\n")
        (product / ".prawduct" / "change-log.md").write_text("## x\n")
        result = _run_regen(product)
        assert result.returncode != 0
        assert "build-plan" in result.stderr.lower()

    def test_untagged_entries_treated_as_unshipped(self, tmp_path: Path):
        """A pre-existing `[x]` survives only if a tag line confirms shipped."""
        product = _make_product_repo(
            tmp_path,
            views_enabled=True,
            change_log="## 2026-03-01: untagged historical entry\n\nBody.\n",
            build_plan="## Status\n- [x] Chunk 99: orphan\n",
        )
        result = _run_regen(product)
        assert result.returncode == 0
        new_plan = (product / ".prawduct" / "artifacts" / "build-plan.md").read_text()
        # Tag-derived view: no shipped tag for 99 → checkbox flips to [ ].
        assert "- [ ] Chunk 99: orphan" in new_plan
