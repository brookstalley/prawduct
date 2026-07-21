"""Tests for lib/views.py + the plugin runtime's `regen-views` subcommand.

The views module derives the build-plan `## Status` block from change-log
tagged entries. The prawduct-hook subcommand is a thin wrapper that reads
project-state.yaml for the `views_enabled` opt-in, runs the builder, and
writes back to build-plan.md.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib import core  # noqa: E402
from lib import views  # noqa: E402

HOOK_PATH = _REPO_ROOT / "bin" / "prawduct-hook"

# plugin-runtime inline mirror via SourceFileLoader (extensionless shebang script)
_hook_loader = importlib.machinery.SourceFileLoader("prawduct_hook_views", str(HOOK_PATH))
_hook_spec = importlib.util.spec_from_loader("prawduct_hook_views", _hook_loader)
_hook = importlib.util.module_from_spec(_hook_spec)
_hook_loader.exec_module(_hook)


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


class TestParseChangeLogMultiTagLines:
    """Multiple consecutive tag lines per entry are unioned, not dropped.

    VWS-4D8J: the historical parse settled tag-vs-no-tag at the FIRST non-blank
    line, so a second `<!-- prawduct: ... -->` line was silently ignored — at
    the v2.1.0 release the reviewer-model-tiering `chunks=02` tag nearly
    shipped unflipped. Consecutive tag lines now merge (chunks union,
    first-wins scalars) and the multiplicity is recorded for the validator.
    """

    def test_consecutive_tag_lines_union_chunks(self):
        content = textwrap.dedent(
            """\
            ## 2026-06-09: Reviewer model tiering
            <!-- prawduct: chunks=01 | status=shipped | scope=tiering -->
            <!-- prawduct: chunks=02 | status=shipped | scope=tiering -->

            Body.
            """
        )
        entries = views.parse_change_log(content)
        assert entries[0].tags["chunks"] == ["01", "02"]
        assert entries[0].shipped_chunks == ["01", "02"]
        assert entries[0].tag_line_count == 2
        assert entries[0].tag_conflicts == []

    def test_duplicate_chunk_ids_deduped_order_preserving(self):
        content = (
            "## X\n"
            "<!-- prawduct: chunks=02,01 -->\n"
            "<!-- prawduct: chunks=01,03 -->\n"
        )
        entries = views.parse_change_log(content)
        assert entries[0].tags["chunks"] == ["02", "01", "03"]

    def test_conflicting_scalar_keeps_first_and_records_conflict(self):
        content = (
            "## X\n"
            "<!-- prawduct: chunks=01 | status=shipped -->\n"
            "<!-- prawduct: chunks=02 | status=merged -->\n"
        )
        entries = views.parse_change_log(content)
        assert entries[0].tags["status"] == "shipped"
        assert entries[0].tags["chunks"] == ["01", "02"]
        assert entries[0].tag_conflicts == ["status: kept 'shipped', ignored 'merged'"]

    def test_same_scalar_value_on_both_lines_is_not_a_conflict(self):
        content = (
            "## X\n"
            "<!-- prawduct: chunks=01 | scope=v9 -->\n"
            "<!-- prawduct: chunks=02 | scope=v9 -->\n"
        )
        entries = views.parse_change_log(content)
        assert entries[0].tag_conflicts == []

    def test_new_key_on_second_line_adopted(self):
        content = (
            "## X\n"
            "<!-- prawduct: chunks=01 | status=shipped -->\n"
            "<!-- prawduct: release=v2.1.0 -->\n"
        )
        entries = views.parse_change_log(content)
        assert entries[0].tags["release"] == "v2.1.0"

    def test_blank_line_between_tag_lines_tolerated(self):
        content = textwrap.dedent(
            """\
            ## X

            <!-- prawduct: chunks=01 -->

            <!-- prawduct: chunks=02 -->

            Body.
            """
        )
        entries = views.parse_change_log(content)
        assert entries[0].tags["chunks"] == ["01", "02"]
        assert entries[0].tag_line_count == 2

    def test_tag_line_after_prose_still_not_consumed(self):
        content = textwrap.dedent(
            """\
            ## X
            <!-- prawduct: chunks=01 -->

            **Why:** body prose.

            <!-- prawduct: chunks=99 -->
            """
        )
        entries = views.parse_change_log(content)
        assert entries[0].tags["chunks"] == ["01"]
        assert entries[0].tag_line_count == 1

    def test_tag_line_count_zero_for_untagged_entry(self):
        entries = views.parse_change_log("## X\n\nBody only.\n")
        assert entries[0].tag_line_count == 0

    def test_next_h2_ends_the_tag_block(self):
        content = (
            "## Newer\n"
            "<!-- prawduct: chunks=01 -->\n"
            "## Older\n"
            "<!-- prawduct: chunks=02 -->\n"
        )
        entries = views.parse_change_log(content)
        assert len(entries) == 2
        assert entries[0].tags["chunks"] == ["01"]
        assert entries[1].tags["chunks"] == ["02"]


class TestValidateTagLineMultiplicity:
    def test_single_tag_line_silent(self):
        entries = views.parse_change_log(
            "## X\n<!-- prawduct: chunks=01 | status=shipped -->\n"
        )
        assert views.validate_tag_line_multiplicity(entries) == []

    def test_untagged_entry_silent(self):
        entries = views.parse_change_log("## X\n\nBody.\n")
        assert views.validate_tag_line_multiplicity(entries) == []

    def test_multi_tag_entry_warns_with_title_and_count(self):
        entries = views.parse_change_log(
            "## 2026-06-09: Tiering\n"
            "<!-- prawduct: chunks=01 -->\n"
            "<!-- prawduct: chunks=02 -->\n"
        )
        warnings = views.validate_tag_line_multiplicity(entries)
        assert len(warnings) == 1
        assert "2026-06-09: Tiering" in warnings[0]
        assert "2 prawduct tag lines" in warnings[0]
        assert "unioned" in warnings[0]

    def test_conflicts_not_in_multiplicity_warning(self):
        # Conflicting scalars are validate_tag_conflicts' job now (VWS-6R4T);
        # the multiplicity warning covers only the style problem.
        entries = views.parse_change_log(
            "## X\n"
            "<!-- prawduct: status=shipped -->\n"
            "<!-- prawduct: status=merged -->\n"
        )
        warnings = views.validate_tag_line_multiplicity(entries)
        assert len(warnings) == 1
        assert "first-wins" not in warnings[0]

    def test_one_warning_per_multi_tag_entry(self):
        entries = views.parse_change_log(
            "## A\n<!-- prawduct: chunks=01 -->\n<!-- prawduct: chunks=02 -->\n"
            "## B\n<!-- prawduct: chunks=03 -->\n"
            "## C\n<!-- prawduct: chunks=04 -->\n<!-- prawduct: chunks=05 -->\n"
        )
        warnings = views.validate_tag_line_multiplicity(entries)
        assert len(warnings) == 2


class TestValidateTagConflicts:
    def test_conflicting_scalars_are_errors(self):
        entries = views.parse_change_log(
            "## X\n"
            "<!-- prawduct: status=shipped -->\n"
            "<!-- prawduct: status=merged -->\n"
        )
        errors = views.validate_tag_conflicts(entries)
        assert len(errors) == 1
        assert "first-wins" in errors[0]
        assert "ignored 'merged'" in errors[0]

    def test_union_without_conflict_is_clean(self):
        # Multiple tag lines whose scalars AGREE (or don't overlap) union
        # cleanly — multiplicity is a warning elsewhere, not a conflict.
        entries = views.parse_change_log(
            "## X\n"
            "<!-- prawduct: chunks=01 | status=shipped -->\n"
            "<!-- prawduct: chunks=02 | status=shipped -->\n"
        )
        assert views.validate_tag_conflicts(entries) == []

    def test_single_tag_line_is_clean(self):
        entries = views.parse_change_log(
            "## X\n<!-- prawduct: chunks=01 | status=shipped -->\n"
        )
        assert views.validate_tag_conflicts(entries) == []


class TestNormalizeChunkId:
    def test_numeric_zero_padding(self):
        assert views.normalize_chunk_id("01") == views.normalize_chunk_id("1")
        assert views.normalize_chunk_id("007") == views.normalize_chunk_id("7")
        assert views.normalize_chunk_id("0") == "0"

    def test_case_insensitive(self):
        assert views.normalize_chunk_id("A") == views.normalize_chunk_id("a")

    def test_separators_unify(self):
        assert views.normalize_chunk_id("foo_bar") == views.normalize_chunk_id(
            "foo-bar"
        )

    def test_mixed_ids_keep_digits_verbatim(self):
        # Zero-strip applies only to purely-numeric IDs: "01a" must NOT
        # collide with "1a".
        assert views.normalize_chunk_id("01a") == "01a"
        assert views.normalize_chunk_id("01a") != views.normalize_chunk_id("1a")

    def test_whitespace_stripped(self):
        assert views.normalize_chunk_id(" 01 ") == "1"


class TestValidateChunkRoster:
    def _arrange(self, tmp_path, plan_content: str) -> "Path":
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        (artifacts / "build-plan-feat.md").write_text(
            "---\nartifact: build-plan\nscope: feat\n---\n" + plan_content
        )
        return artifacts

    def test_miss_names_entry_id_and_roster(self, tmp_path):
        artifacts = self._arrange(
            tmp_path, "## Status\n- [ ] Chunk 01: A\n- [ ] Chunk 02: B\n"
        )
        errors = views.validate_chunk_roster(
            "## E\n<!-- prawduct: chunks=03 | scope=feat | status=merged -->\n",
            artifacts,
        )
        assert len(errors) == 1
        assert "chunks=03" in errors[0]
        assert "01, 02" in errors[0]
        assert "build-plan-feat.md" in errors[0]

    def test_tolerant_match_suppresses_zero_padding_miss(self, tmp_path):
        # The historical false miss: chunks=1 against a `Chunk 01:` roster.
        artifacts = self._arrange(tmp_path, "## Status\n- [ ] Chunk 01: A\n")
        errors = views.validate_chunk_roster(
            "## E\n<!-- prawduct: chunks=1 | scope=feat | status=shipped -->\n",
            artifacts,
        )
        assert errors == []

    def test_shipped_entries_validated_too(self, tmp_path):
        # Release-prep flips to shipped BEFORE running regen-views, so
        # shipped entries with a resolvable plan are inside the contract.
        artifacts = self._arrange(tmp_path, "## Status\n- [ ] Chunk 01: A\n")
        errors = views.validate_chunk_roster(
            "## E\n<!-- prawduct: chunks=09 | scope=feat | status=shipped -->\n",
            artifacts,
        )
        assert len(errors) == 1

    def test_scope_without_plan_file_skipped(self, tmp_path):
        # Historical/retired plans: no file to validate against — the
        # unreleased subset is diagnose_scope_plan_coverage's job.
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        errors = views.validate_chunk_roster(
            "## E\n<!-- prawduct: chunks=01 | scope=gone | status=shipped -->\n",
            artifacts,
        )
        assert errors == []

    def test_scopeless_entry_skipped(self, tmp_path):
        # Legacy unfiltered single-plan repos: no scope= → no roster to
        # resolve against; outside the contract.
        artifacts = self._arrange(tmp_path, "## Status\n- [ ] Chunk 01: A\n")
        errors = views.validate_chunk_roster(
            "## E\n<!-- prawduct: chunks=99 | status=shipped -->\n",
            artifacts,
        )
        assert errors == []

    def test_empty_roster_with_chunks_is_error(self, tmp_path):
        artifacts = self._arrange(tmp_path, "## Status\nContext: no boxes.\n")
        errors = views.validate_chunk_roster(
            "## E\n<!-- prawduct: chunks=01 | scope=feat | status=merged -->\n",
            artifacts,
        )
        assert len(errors) == 1
        assert "empty" in errors[0]

    def test_clean_change_log_no_errors(self, tmp_path):
        artifacts = self._arrange(
            tmp_path, "## Status\n- [x] Chunk 01: A\n- [ ] Chunk 02: B\n"
        )
        errors = views.validate_chunk_roster(
            "## E1\n<!-- prawduct: chunks=01 | scope=feat | status=shipped -->\n"
            "## E2\n<!-- prawduct: chunks=02 | scope=feat | status=merged -->\n",
            artifacts,
        )
        assert errors == []


class TestTolerantStatusFlip:
    """VWS-6R4T: chunk-ID matching is normalized on both sides of the flip."""

    def test_unpadded_tag_flips_padded_roster(self):
        section = ["## Status", "- [ ] Chunk 01: A", "- [ ] Chunk 02: B"]
        new_lines, changes = views.regenerate_status_section(section, {"1"})
        assert "- [x] Chunk 01: A" in new_lines
        assert "- [ ] Chunk 02: B" in new_lines
        assert changes == [("01", " ", "x")]

    def test_case_and_separator_variants_flip(self):
        section = ["## Status", "- [ ] Chunk Foo_Bar: A", "- [ ] Chunk B: b"]
        new_lines, _ = views.regenerate_status_section(section, {"foo-bar", "b"})
        assert "- [x] Chunk Foo_Bar: A" in new_lines
        assert "- [x] Chunk B: b" in new_lines

    def test_exact_match_still_flips(self):
        section = ["## Status", "- [ ] Chunk 01: A"]
        new_lines, _ = views.regenerate_status_section(section, {"01"})
        assert "- [x] Chunk 01: A" in new_lines


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

    def test_scope_filter_includes_only_matching(self):
        entries = [
            views.ChangeLogEntry(
                title="v1.4 chunk 05",
                tags={"chunks": ["05"], "status": "shipped", "scope": "v1.4"},
            ),
            views.ChangeLogEntry(
                title="v1.5 chunk 02",
                tags={"chunks": ["02"], "status": "shipped", "scope": "v1.5"},
            ),
            views.ChangeLogEntry(
                title="v1.5 chunk 05",
                tags={"chunks": ["05"], "status": "shipped", "scope": "v1.5"},
            ),
        ]
        assert views.collect_shipped_chunks(entries, scope="v1.5") == {"02", "05"}
        assert views.collect_shipped_chunks(entries, scope="v1.4") == {"05"}

    def test_scope_none_preserves_legacy_unfiltered_union(self):
        entries = [
            views.ChangeLogEntry(
                title="v1.4 chunk 05",
                tags={"chunks": ["05"], "status": "shipped", "scope": "v1.4"},
            ),
            views.ChangeLogEntry(
                title="v1.5 chunk 05",
                tags={"chunks": ["05"], "status": "shipped", "scope": "v1.5"},
            ),
        ]
        assert views.collect_shipped_chunks(entries, scope=None) == {"05"}
        assert views.collect_shipped_chunks(entries) == {"05"}  # default

    def test_scope_filter_excludes_untagged_entries(self):
        entries = [
            views.ChangeLogEntry(
                title="untagged",
                tags={"chunks": ["00"], "status": "shipped"},  # no scope=
            ),
            views.ChangeLogEntry(
                title="v1.5 chunk 01",
                tags={"chunks": ["01"], "status": "shipped", "scope": "v1.5"},
            ),
        ]
        assert views.collect_shipped_chunks(entries, scope="v1.5") == {"01"}


class TestValidateStatusValues:
    """VWS-3K7P: surface change-log `status=` typos as non-fatal warnings.

    An unrecognized status (e.g. `status=shippd`) parses fine but silently fails
    to flip any checkbox — the typo guard turns that into a visible warning.
    """

    def test_typo_yields_one_warning(self):
        entries = [
            views.ChangeLogEntry(
                title="2026-06-04: typo", tags={"chunks": ["01"], "status": "shippd"}
            )
        ]
        warnings = views.validate_status_values(entries)
        assert len(warnings) == 1
        assert "shippd" in warnings[0]

    def test_valid_shipped_yields_none(self):
        entries = [
            views.ChangeLogEntry(
                title="2026-06-04: ok", tags={"chunks": ["01"], "status": "shipped"}
            )
        ]
        assert views.validate_status_values(entries) == []

    def test_valid_merged_yields_none(self):
        entries = [
            views.ChangeLogEntry(
                title="2026-06-04: ok", tags={"chunks": ["01"], "status": "merged"}
            )
        ]
        assert views.validate_status_values(entries) == []

    def test_absent_status_yields_none(self):
        entries = [
            views.ChangeLogEntry(title="2026-06-04: untagged", tags={}),
            views.ChangeLogEntry(
                title="2026-06-04: chunks-only", tags={"chunks": ["02"]}
            ),
        ]
        assert views.validate_status_values(entries) == []

    def test_one_warning_per_bad_entry(self):
        entries = [
            views.ChangeLogEntry(title="a", tags={"status": "shippd"}),
            views.ChangeLogEntry(title="b", tags={"status": "shipped"}),
            views.ChangeLogEntry(title="c", tags={"status": "in-progress"}),
        ]
        warnings = views.validate_status_values(entries)
        assert len(warnings) == 2  # shippd + in-progress (shipped is valid)


class TestParseBuildPlanFrontmatterScope:
    def test_scope_field_present(self):
        content = (
            "---\n"
            "artifact: build-plan\n"
            "scope: v1.5\n"
            "version: 2\n"
            "---\n"
            "## Status\n"
        )
        assert views._parse_build_plan_frontmatter_scope(content) == (True, "v1.5")

    def test_scope_field_quoted(self):
        content = '---\nscope: "v1.5.1"\n---\n'
        assert views._parse_build_plan_frontmatter_scope(content) == (True, "v1.5.1")

    def test_scope_field_null_or_empty_is_present_with_no_value(self):
        # YAML null literals are the documented explicit opt-out: the key is
        # PRESENT (present=True) but carries no value (None). Distinguishing
        # this from key-absent is what lets _detect_active_scope suppress
        # change-log inference rather than silently inheriting a prior scope
        # (BLD-4Q9X).
        assert views._parse_build_plan_frontmatter_scope("---\nscope: null\n---\n") == (True, None)
        assert views._parse_build_plan_frontmatter_scope("---\nscope: NULL\n---\n") == (True, None)
        assert views._parse_build_plan_frontmatter_scope("---\nscope: ~\n---\n") == (True, None)
        # Empty value is likewise an explicit opt-out (key present, no value).
        assert views._parse_build_plan_frontmatter_scope("---\nscope:\n---\n") == (True, None)
        assert views._parse_build_plan_frontmatter_scope("---\nscope: \n---\n") == (True, None)

    def test_scope_field_with_inline_comment(self):
        content = "---\nscope: v1.5  # active version\n---\n"
        assert views._parse_build_plan_frontmatter_scope(content) == (True, "v1.5")

    def test_no_frontmatter_is_absent(self):
        assert views._parse_build_plan_frontmatter_scope("# Plan\nNo frontmatter.\n") == (
            False,
            None,
        )

    def test_frontmatter_without_scope_is_absent(self):
        content = "---\nartifact: build-plan\nversion: 2\n---\n"
        assert views._parse_build_plan_frontmatter_scope(content) == (False, None)

    def test_scope_after_closing_frontmatter_marker_ignored(self):
        """A `scope:` line outside the frontmatter is not the frontmatter scope."""
        content = "---\nartifact: build-plan\n---\n## Notes\nscope: shouldnotmatch\n"
        assert views._parse_build_plan_frontmatter_scope(content) == (False, None)

    def test_indented_scope_ignored(self):
        """Only column-0 `scope:` counts; nested keys don't."""
        content = "---\ndepends_on:\n  scope: nested-not-frontmatter\n---\n"
        assert views._parse_build_plan_frontmatter_scope(content) == (False, None)

    def test_leading_html_comment_tolerated(self):
        """Every real build-plan starts with an HTML comment header; the
        parser must skip it before the opening ``---``."""
        content = (
            "<!-- Build Plan: v1.5.1\n"
            "     Tier: 1 (Source of Truth)\n"
            "-->\n"
            "---\n"
            "artifact: build-plan\n"
            "scope: v1.5.1\n"
            "---\n"
            "## Status\n"
        )
        assert views._parse_build_plan_frontmatter_scope(content) == (True, "v1.5.1")

    def test_leading_single_line_html_comment_tolerated(self):
        content = "<!-- one-liner -->\n---\nscope: v2\n---\n"
        assert views._parse_build_plan_frontmatter_scope(content) == (True, "v2")

    def test_leading_blank_lines_before_comment_tolerated(self):
        content = "\n\n<!-- header -->\n\n---\nscope: v3\n---\n"
        assert views._parse_build_plan_frontmatter_scope(content) == (True, "v3")

    def test_html_comment_without_frontmatter_is_absent(self):
        """Comment header but no frontmatter at all → key absent."""
        content = "<!-- header -->\n# Plan\nNo frontmatter.\n"
        assert views._parse_build_plan_frontmatter_scope(content) == (False, None)

    def test_unclosed_html_comment_is_handled_leniently(self):
        """VWS-8M2Q (v1.5.1 R5): a leading HTML comment that is never closed
        (no ``-->``) must not raise or misparse. The comment scan walks to EOF,
        no ``---`` opener is found, and the result is the safe ``(False, None)``
        absent reading — the documented lenient handling of malformed input."""
        content = (
            "<!-- Build Plan: this header is never closed\n"
            "     no terminator on any line\n"
            "---\n"
            "scope: v9.9\n"
            "---\n"
            "## Status\n"
        )
        # The `---`/`scope:` lines are swallowed by the unterminated comment scan,
        # so the frontmatter is unreachable → (False, None), no exception.
        assert views._parse_build_plan_frontmatter_scope(content) == (False, None)

    def test_unclosed_html_comment_only_input(self):
        """An input that is nothing but an unclosed comment also degrades to
        absent rather than raising (empty/EOF edge of the lenient path)."""
        content = "<!-- open and never closed\nstill open\n"
        assert views._parse_build_plan_frontmatter_scope(content) == (False, None)


class TestDetectActiveScope:
    def test_frontmatter_wins_over_inference(self):
        build_plan = "---\nscope: v1.5\n---\n## Status\n"
        change_log = (
            "## 2026-05-22: latest\n"
            "<!-- prawduct: chunks=00 | status=shipped | scope=v1.4 -->\n"
        )
        assert views._detect_active_scope(build_plan, change_log) == "v1.5"

    def test_infers_from_most_recent_change_log_entry(self):
        build_plan = "---\nartifact: build-plan\n---\n## Status\n"
        change_log = (
            "## 2026-05-22: newer\n"
            "<!-- prawduct: chunks=00 | status=shipped | scope=v1.5 -->\n"
            "\n"
            "## 2026-05-01: older\n"
            "<!-- prawduct: chunks=00 | status=shipped | scope=v1.4 -->\n"
        )
        assert views._detect_active_scope(build_plan, change_log) == "v1.5"

    def test_returns_none_when_no_signal(self):
        build_plan = "---\nartifact: build-plan\n---\n## Status\n"
        change_log = "## 2026-05-22: untagged\nNo prawduct tag line.\n"
        assert views._detect_active_scope(build_plan, change_log) is None

    def test_returns_none_when_change_log_not_provided(self):
        build_plan = "---\nartifact: build-plan\n---\n## Status\n"
        assert views._detect_active_scope(build_plan, None) is None

    def test_explicit_null_scope_suppresses_change_log_inference(self):
        """BLD-4Q9X: an explicit ``scope: null`` is the author's opt-out and
        MUST NOT inherit a prior change-log ``scope=`` tag via inference.

        Regression: previously ``scope: null`` was indistinguishable from a
        missing key, so detection fell through to change-log inference and
        silently picked up the prior ``scope=v1.4`` — wrongly scope-filtering a
        fresh plan and flipping its chunks to shipped. With the opt-out
        respected, the result is ``None`` (legacy unfiltered union)."""
        build_plan = "---\nartifact: build-plan\nscope: null\n---\n## Status\n"
        change_log = (
            "## 2026-05-22: prior release\n"
            "<!-- prawduct: chunks=01,02,03 | status=shipped | scope=v1.4 -->\n"
        )
        # Inference is suppressed: must NOT inherit scope=v1.4.
        assert views._detect_active_scope(build_plan, change_log) is None

    def test_empty_scope_suppresses_change_log_inference(self):
        """An empty ``scope:`` value is the same explicit opt-out as ``null``."""
        build_plan = "---\nartifact: build-plan\nscope:\n---\n## Status\n"
        change_log = (
            "## 2026-05-22: prior release\n"
            "<!-- prawduct: chunks=01 | status=shipped | scope=v1.4 -->\n"
        )
        assert views._detect_active_scope(build_plan, change_log) is None

    def test_absent_scope_key_still_infers_from_change_log(self):
        """Contrast with the opt-out: when the ``scope:`` key is genuinely
        ABSENT, inference still falls back to the most-recent change-log
        ``scope=`` tag — the legacy behavior is preserved for that case."""
        build_plan = "---\nartifact: build-plan\n---\n## Status\n"
        change_log = (
            "## 2026-05-22: prior release\n"
            "<!-- prawduct: chunks=01,02,03 | status=shipped | scope=v1.4 -->\n"
        )
        assert views._detect_active_scope(build_plan, change_log) == "v1.4"


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


class TestRegenViewsScopeFilter:
    """End-to-end: build-plan frontmatter `scope:` filters change-log entries.

    Regression coverage for the v1.5 chunk-numbering collision: v1.4's
    `chunks=05 | scope=v1.4 | status=shipped` must NOT flip v1.5's chunk 05.
    """

    def test_scoped_plan_ignores_other_scope_entries(self):
        change_log = (
            "## 2026-05-22: v1.5 chunk 01 shipped\n"
            "<!-- prawduct: chunks=01 | status=shipped | scope=v1.5 -->\n"
            "\n"
            "## 2026-05-19: v1.4 chunk 14 shipped (claims chunks 05,06,07,14)\n"
            "<!-- prawduct: chunks=05,06,07,14 | status=shipped | scope=v1.4 -->\n"
        )
        build_plan = (
            "---\n"
            "artifact: build-plan\n"
            "scope: v1.5\n"
            "version: 2\n"
            "---\n"
            "## Status\n"
            "- [ ] Chunk 01: A\n"
            "- [ ] Chunk 05: B\n"  # would flip [x] under legacy unfiltered union
            "- [ ] Chunk 06: C\n"  # same
            "- [ ] Chunk 07: D\n"  # same
            "## End\n"
        )
        new, changes = views.build_status_view(change_log, build_plan)
        assert new is not None
        assert "- [x] Chunk 01: A" in new
        assert "- [ ] Chunk 05: B" in new  # NOT flipped — v1.4's claim ignored
        assert "- [ ] Chunk 06: C" in new
        assert "- [ ] Chunk 07: D" in new
        assert {c[0] for c in changes} == {"01"}

    def test_unscoped_plan_falls_back_to_legacy_behavior(self):
        """Plan without `scope:` and change-log without `scope=` tags →
        unfiltered union (legacy behavior preserved)."""
        change_log = (
            "## 2026-05-22: rel\n"
            "<!-- prawduct: chunks=00,01 | status=shipped -->\n"
        )
        build_plan = "## Status\n- [ ] Chunk 00: A\n- [ ] Chunk 01: B\n## End\n"
        new, changes = views.build_status_view(change_log, build_plan)
        assert new is not None
        assert "- [x] Chunk 00: A" in new
        assert "- [x] Chunk 01: B" in new

    def test_production_shape_html_comment_then_frontmatter(self):
        """End-to-end with the exact shape every real build-plan uses: leading
        HTML comment block, then ``---`` frontmatter with ``scope:``. Guards
        against the parser silently failing on production files (which is what
        the v1 implementation did)."""
        change_log = (
            "## 2026-05-22: v1.5.1 chunk 01 shipped\n"
            "<!-- prawduct: chunks=01 | status=shipped | scope=v1.5.1 -->\n"
            "\n"
            "## 2026-05-19: v1.4 historical\n"
            "<!-- prawduct: chunks=01,05 | status=shipped | scope=v1.4 -->\n"
        )
        build_plan = (
            "<!-- Build Plan: Prawduct v1.5.1\n"
            "     Tier: 1 (Source of Truth)\n"
            "-->\n"
            "---\n"
            "artifact: build-plan\n"
            "version: 2\n"
            "scope: v1.5.1\n"
            "---\n"
            "\n"
            "## Status\n"
            "- [ ] Chunk 01: A\n"
            "- [ ] Chunk 05: B\n"  # v1.4's chunks=05 must NOT flip this
            "## End\n"
        )
        new, changes = views.build_status_view(change_log, build_plan)
        assert new is not None
        assert "- [x] Chunk 01: A" in new
        assert "- [ ] Chunk 05: B" in new
        assert {c[0] for c in changes} == {"01"}

    def test_scoped_plan_with_no_matching_entries_leaves_all_unshipped(self):
        """Plan declares ``scope: v1.5.1`` but no v1.5.1 entries shipped yet —
        the situation when Chunk 01 first lands. All checkboxes stay ``[ ]``;
        v1.5/v1.4 entries do not bleed through."""
        change_log = (
            "## 2026-05-22: v1.5.0 final\n"
            "<!-- prawduct: chunks=01,02,03 | status=shipped | scope=v1.5 -->\n"
        )
        build_plan = (
            "<!-- header -->\n"
            "---\n"
            "scope: v1.5.1\n"
            "---\n"
            "## Status\n"
            "- [ ] Chunk 01: A\n"
            "- [ ] Chunk 02: B\n"
            "- [ ] Chunk 03: C\n"
            "## End\n"
        )
        new, changes = views.build_status_view(change_log, build_plan)
        assert new is None
        assert changes == []

    def test_inferred_scope_filters_when_frontmatter_absent(self):
        """Plan without frontmatter but change-log carries `scope=` tags →
        infer scope from most-recent tagged entry and filter accordingly."""
        change_log = (
            "## 2026-05-22: latest, v1.5\n"
            "<!-- prawduct: chunks=01 | status=shipped | scope=v1.5 -->\n"
            "\n"
            "## 2026-05-19: older, v1.4\n"
            "<!-- prawduct: chunks=05 | status=shipped | scope=v1.4 -->\n"
        )
        build_plan = "## Status\n- [ ] Chunk 01: A\n- [ ] Chunk 05: B\n## End\n"
        new, changes = views.build_status_view(change_log, build_plan)
        assert new is not None
        assert "- [x] Chunk 01: A" in new
        assert "- [ ] Chunk 05: B" in new  # v1.4's chunk-05 ignored via inference


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


class TestReadBoolYamlKey:
    """The shared scan extracted from ``is_views_enabled`` /
    bin/prawduct-hook's ``_read_bool_yaml_key`` (SYN-9C4T)."""

    def test_true_value(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("classification:\n  domain: util\ncoverage_required: true\n")
        assert core.read_bool_yaml_key(p, "coverage_required") is True

    def test_false_value(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("coverage_required: false\n")
        assert core.read_bool_yaml_key(p, "coverage_required") is False

    def test_missing_key(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("views_enabled: true\n")
        assert core.read_bool_yaml_key(p, "coverage_required") is False

    def test_missing_file(self, tmp_path: Path):
        assert core.read_bool_yaml_key(tmp_path / "nope.yaml", "coverage_required") is False

    def test_indented_line_ignored(self, tmp_path: Path):
        """A nested ``key: true`` must not flip the top-level switch — only
        column-0 keys count."""
        p = tmp_path / "s.yaml"
        p.write_text("nested:\n  coverage_required: true\n")
        assert core.read_bool_yaml_key(p, "coverage_required") is False

    def test_comment_only_line_ignored(self, tmp_path: Path):
        p = tmp_path / "s.yaml"
        p.write_text("# coverage_required: true\ncoverage_required: false\n")
        assert core.read_bool_yaml_key(p, "coverage_required") is False

    def test_quoted_true_reads_false(self, tmp_path: Path):
        """Quotes are not stripped (unlike ``read_str_yaml_key``): a quoted
        ``"true"`` does not equal the bare ``true`` sentinel."""
        p = tmp_path / "s.yaml"
        p.write_text('coverage_required: "true"\n')
        assert core.read_bool_yaml_key(p, "coverage_required") is False


class TestBoolKeyCallSiteParity:
    """Both extracted call sites delegate to the same scan: ``is_views_enabled``
    (lib) and the inline ``_read_bool_yaml_key`` mirror (prawduct-hook, kept
    import-light on the hot path), pinned to ``core.read_bool_yaml_key``."""

    def test_is_views_enabled_delegates(self, tmp_path: Path):
        p = tmp_path / "project-state.yaml"
        p.write_text("views_enabled: true\n")
        assert views.is_views_enabled(p) == core.read_bool_yaml_key(p, "views_enabled")

    def test_hook_mirror_parity_true(self, tmp_path: Path):
        p = tmp_path / "project-state.yaml"
        p.write_text("coverage_required: true\n")
        assert _hook._read_bool_yaml_key(p, "coverage_required") == core.read_bool_yaml_key(
            p, "coverage_required"
        )

    def test_hook_mirror_parity_missing_and_indented(self, tmp_path: Path):
        # missing file
        gone = tmp_path / "nope.yaml"
        assert _hook._read_bool_yaml_key(gone, "coverage_required") == core.read_bool_yaml_key(
            gone, "coverage_required"
        )
        # indented (must not flip)
        p = tmp_path / "project-state.yaml"
        p.write_text("nested:\n  coverage_required: true\n")
        assert _hook._read_bool_yaml_key(p, "coverage_required") == core.read_bool_yaml_key(
            p, "coverage_required"
        )


# =============================================================================
# Pure-function tests — new F1b helpers (scope + release-notes views)
# =============================================================================


class TestExtractYamlTopLevelBlock:
    def test_finds_single_line_block(self):
        content = "views_enabled: true\n# next section\nother: 1\n"
        start, end, block = views.extract_yaml_top_level_block(content, "views_enabled")
        assert start == 0
        assert end == 1
        assert block == ["views_enabled: true"]

    def test_finds_multi_line_block(self):
        content = (
            "scope_rollups:\n"
            "  v1.4:\n"
            "    chunks: [\"00\"]\n"
            "\n"
            "# next\n"
            "other: 1\n"
        )
        start, end, block = views.extract_yaml_top_level_block(content, "scope_rollups")
        assert start == 0
        # Trailing blank line excluded (belongs to next block).
        assert end == 3
        assert block == ["scope_rollups:", "  v1.4:", '    chunks: ["00"]']

    def test_block_at_end_of_file(self):
        content = "other: 1\nviews_enabled: true\n"
        start, end, block = views.extract_yaml_top_level_block(content, "views_enabled")
        assert start == 1
        assert end == 2
        assert block == ["views_enabled: true"]

    def test_missing_key_returns_negative(self):
        content = "other: 1\nfoo: bar\n"
        start, end, block = views.extract_yaml_top_level_block(content, "missing")
        assert (start, end, block) == (-1, -1, [])

    def test_comment_header_terminates_block(self):
        content = (
            "scope_rollups:\n"
            "  v1.4:\n"
            "    chunks: []\n"
            "# === DEPRECATED TERMS ===\n"
            "deprecated_terms: []\n"
        )
        start, end, block = views.extract_yaml_top_level_block(content, "scope_rollups")
        assert start == 0
        assert end == 3
        assert block == ["scope_rollups:", "  v1.4:", "    chunks: []"]

    def test_indented_key_not_matched(self):
        """A nested `scope_rollups:` under another key must not be treated as
        the top-level block."""
        content = (
            "parent:\n"
            "  scope_rollups:\n"
            "    foo: bar\n"
            "scope_rollups:\n"
            "  v1.4:\n"
            "    chunks: []\n"
        )
        start, end, block = views.extract_yaml_top_level_block(content, "scope_rollups")
        # Should match the column-0 one (line 3), not the indented one (line 1).
        assert start == 3
        assert block[0] == "scope_rollups:"


class TestBuildScopeView:
    BASE_STATE = "classification:\n  domain: util\nviews_enabled: true\n"

    def test_appends_block_when_absent(self):
        change_log = (
            "## 2026-05-18: rel\n"
            "<!-- prawduct: chunks=00,01 | release=v1.3.17 | status=shipped | scope=v1.4 -->\n"
        )
        new, scopes = views.build_scope_view(change_log, self.BASE_STATE)
        assert new is not None
        assert "scope_rollups:" in new
        assert "v1.4:" in new
        assert '"00"' in new
        assert '"01"' in new
        assert '"v1.3.17"' in new
        assert scopes == {"v1.4": {"chunks": ["00", "01"], "releases": ["v1.3.17"]}}

    def test_replaces_existing_block(self):
        state = (
            "views_enabled: true\n"
            "scope_rollups:\n"
            "  v1.4:\n"
            '    chunks: ["00"]\n'
            "    releases: []\n"
            "deprecated_terms: []\n"
        )
        change_log = (
            "## 2026-05-18: rel\n"
            "<!-- prawduct: chunks=00,01 | status=shipped | scope=v1.4 -->\n"
        )
        new, scopes = views.build_scope_view(change_log, state)
        assert new is not None
        # Block content replaced — both chunks now present.
        assert '"00"' in new and '"01"' in new
        # Surrounding content preserved.
        assert "deprecated_terms: []" in new
        assert "views_enabled: true" in new

    def test_idempotent_when_existing_block_matches(self):
        # Build once to get the canonical block, then feed it back.
        change_log = (
            "## 2026-05-18: rel\n"
            "<!-- prawduct: chunks=00,01 | status=shipped | scope=v1.4 -->\n"
        )
        first, _ = views.build_scope_view(change_log, self.BASE_STATE)
        assert first is not None
        second, _ = views.build_scope_view(change_log, first)
        assert second is None

    def test_empty_scopes_when_no_scope_tags(self):
        change_log = (
            "## 2026-05-18: rel\n"
            "<!-- prawduct: chunks=00 | release=v1.3.17 | status=shipped -->\n"
        )
        new, scopes = views.build_scope_view(change_log, self.BASE_STATE)
        assert scopes == {}
        # Block appended with `{}` body.
        assert new is not None
        assert "scope_rollups: {}" in new

    def test_multiple_scopes_sorted(self):
        change_log = (
            "## 2026-06-01: w\n"
            "<!-- prawduct: chunks=06 | status=shipped | scope=v1.4 -->\n"
            "## 2026-07-01: x\n"
            "<!-- prawduct: chunks=10 | status=shipped | scope=v1.5 -->\n"
        )
        new, scopes = views.build_scope_view(change_log, self.BASE_STATE)
        assert list(scopes.keys()) == ["v1.4", "v1.5"]
        # v1.4 appears before v1.5 in output.
        v14_pos = new.index("v1.4:")
        v15_pos = new.index("v1.5:")
        assert v14_pos < v15_pos

    def test_in_progress_and_deferred_excluded(self):
        change_log = (
            "## 2026-05-18: a\n"
            "<!-- prawduct: chunks=00 | status=shipped | scope=v1.4 -->\n"
            "## 2026-05-19: b\n"
            "<!-- prawduct: chunks=07 | status=in-progress | scope=v1.4 -->\n"
            "## 2026-05-20: c\n"
            "<!-- prawduct: chunks=99 | status=deferred | scope=v1.4 -->\n"
        )
        _, scopes = views.build_scope_view(change_log, self.BASE_STATE)
        assert scopes == {"v1.4": {"chunks": ["00"], "releases": []}}

    def test_chunks_deduplicated_and_sorted(self):
        change_log = (
            "## 2026-05-18: a\n"
            "<!-- prawduct: chunks=02,01 | status=shipped | scope=v1.4 -->\n"
            "## 2026-05-19: b\n"
            "<!-- prawduct: chunks=01,03 | status=shipped | scope=v1.4 -->\n"
        )
        _, scopes = views.build_scope_view(change_log, self.BASE_STATE)
        assert scopes["v1.4"]["chunks"] == ["01", "02", "03"]

    def test_malformed_chunk_id_does_not_corrupt_yaml(self):
        """VWS-8M2Q: a chunk ID with a quote/special char must NOT produce
        unparseable scope_rollups YAML. The unsafe ID is dropped (it falls
        outside the CHUNK_ID_SAFE charset); the well-formed sibling survives and
        the emitted block round-trips through a real YAML parser."""
        import yaml

        # `01"a` (embedded quote) and `0 2` (space) are malformed; `03` is fine.
        change_log = (
            '## 2026-06-04: malformed\n'
            '<!-- prawduct: chunks=01"a,0 2,03 | status=shipped | scope=v1.4 -->\n'
        )
        new, scopes = views.build_scope_view(change_log, self.BASE_STATE)
        # Only the safe ID survived into the aggregated mapping.
        assert scopes == {"v1.4": {"chunks": ["03"], "releases": []}}
        assert new is not None
        # The emitted project-state.yaml (with the scope_rollups block) is valid
        # YAML — the embedded quote did not corrupt the document.
        parsed = yaml.safe_load(new)
        assert parsed["scope_rollups"]["v1.4"]["chunks"] == ["03"]

    def test_collect_scope_rollups_drops_unsafe_ids_directly(self):
        """Unit-level guard on the collector: unsafe chunk IDs are filtered out
        before they ever reach the formatter."""
        entries = [
            views.ChangeLogEntry(
                title="x",
                tags={
                    "chunks": ['"', "}", "ok-1", "ok_2"],
                    "status": "shipped",
                    "scope": "s",
                },
            )
        ]
        rollups = views._collect_scope_rollups(entries)
        assert rollups == {"s": {"chunks": ["ok-1", "ok_2"], "releases": []}}


class TestBuildReleaseNotesView:
    def test_none_when_no_releases(self):
        change_log = "## 2026-05-18: untagged\n\nBody.\n"
        assert views.build_release_notes_view(change_log) is None

    def test_none_when_only_unshipped_releases(self):
        change_log = (
            "## 2026-05-18: rel\n"
            "<!-- prawduct: chunks=00 | release=v1.4.0 | status=in-progress -->\n"
        )
        assert views.build_release_notes_view(change_log) is None

    def test_single_release_section(self):
        change_log = (
            "## 2026-05-18: v1.4 Wave 1 (v1.3.17)\n"
            "<!-- prawduct: chunks=00,01,02 | release=v1.3.17 | status=shipped | scope=v1.4 -->\n"
        )
        out = views.build_release_notes_view(change_log)
        assert out is not None
        assert out.startswith("# Release Notes")
        assert "## v1.3.17" in out
        assert "**Chunks shipped:** 00, 01, 02" in out
        assert "**Scope:** v1.4" in out
        assert "2026-05-18: v1.4 Wave 1" in out  # title
        # Single-entry release renders FLAT — no ### sub-section (byte-compatible).
        assert "### " not in out

    def test_multiple_releases_preserve_changelog_order(self):
        # Change-log convention: newest first.
        change_log = (
            "## 2026-05-18: newer (v1.3.17)\n"
            "<!-- prawduct: chunks=00 | release=v1.3.17 | status=shipped -->\n"
            "## 2026-04-01: older (v1.3.16)\n"
            "<!-- prawduct: chunks=99 | release=v1.3.16 | status=shipped -->\n"
        )
        out = views.build_release_notes_view(change_log)
        assert out is not None
        pos_newer = out.index("## v1.3.17")
        pos_older = out.index("## v1.3.16")
        assert pos_newer < pos_older

    def test_multiple_entries_same_release_render_separately_no_union(self):
        # REL-4T8N: two entries share one release version but are distinct.
        # They must render as separate sub-sections, NOT collapse into one with
        # a union'd chunk list. (No scope= tags -> ### heading from the title.)
        change_log = (
            "## 2026-05-18: first part (v1.3.17)\n"
            "<!-- prawduct: chunks=00,01 | release=v1.3.17 | status=shipped -->\n"
            "## 2026-05-18: second part (v1.3.17)\n"
            "<!-- prawduct: chunks=02,03 | release=v1.3.17 | status=shipped -->\n"
        )
        out = views.build_release_notes_view(change_log)
        assert out is not None
        # One ## section per release version; two ### sub-sections under it.
        assert out.count("## v1.3.17") == 1
        assert out.count("### ") == 2
        chunks_lines = [ln for ln in out.splitlines() if ln.startswith("**Chunks shipped:**")]
        # Each entry keeps its OWN chunks — NOT the union.
        assert "**Chunks shipped:** 00, 01" in chunks_lines
        assert "**Chunks shipped:** 02, 03" in chunks_lines
        # The mis-aggregated union must NOT appear on any single line.
        assert all("00, 01, 02, 03" not in ln for ln in chunks_lines)
        # No scope= -> ### heading falls back to the entry title.
        assert "### 2026-05-18: first part (v1.3.17)" in out
        # One shared trailer for the whole release block.
        assert out.count("See `.prawduct/change-log.md` for full details.") == 1

    def test_four_scope_batched_release_v2_0_5_regression(self):
        # The exact v2.0.5 shape that exposed the bug: four scopes, one version.
        change_log = (
            "## 2026-06-04: cleanup-batch — 6 fixes (shipped v2.0.5)\n"
            "<!-- prawduct: chunks=01,02,03,04,05,06 | release=v2.0.5 | status=shipped | scope=cleanup-batch -->\n"
            "## 2026-06-04: evidence-deferral (shipped v2.0.5)\n"
            "<!-- prawduct: chunks=01,02 | release=v2.0.5 | status=shipped | scope=evidence-deferral -->\n"
            "## 2026-06-04: roi-batch-2 (shipped v2.0.5)\n"
            "<!-- prawduct: chunks=01,02,03,04,05,06,07,08,09 | release=v2.0.5 | status=shipped | scope=roi-batch-2 -->\n"
            "## 2026-06-04: roi-batch (shipped v2.0.5)\n"
            "<!-- prawduct: chunks=01,02,03,04,05 | release=v2.0.5 | status=shipped | scope=roi-batch -->\n"
        )
        out = views.build_release_notes_view(change_log)
        assert out is not None
        assert out.count("## v2.0.5") == 1
        for scope in ("cleanup-batch", "evidence-deferral", "roi-batch-2", "roi-batch"):
            assert f"### {scope}" in out
        # Change-log order preserved (cleanup-batch first).
        assert out.index("### cleanup-batch") < out.index("### roi-batch")
        chunks_lines = [ln for ln in out.splitlines() if ln.startswith("**Chunks shipped:**")]
        # cleanup-batch keeps ITS 01-06, not the cross-scope union 01-09.
        assert "**Chunks shipped:** 01, 02, 03, 04, 05, 06" in chunks_lines
        assert "**Chunks shipped:** 01, 02" in chunks_lines  # evidence-deferral
        assert "**Chunks shipped:** 01, 02, 03, 04, 05" in chunks_lines  # roi-batch
        # The old union ran 01..09 under one scope — that line must not exist
        # except as roi-batch-2's OWN legitimate 01-09.
        union = "**Chunks shipped:** 01, 02, 03, 04, 05, 06, 07, 08, 09"
        assert chunks_lines.count(union) == 1  # only roi-batch-2 owns 01-09
        # One shared trailer for the whole v2.0.5 block.
        assert out.count("See `.prawduct/change-log.md` for full details.") == 1

    def test_multi_scope_idempotent(self):
        change_log = (
            "## 2026-06-04: a\n"
            "<!-- prawduct: chunks=01 | release=v2 | status=shipped | scope=a -->\n"
            "## 2026-06-04: b\n"
            "<!-- prawduct: chunks=02 | release=v2 | status=shipped | scope=b -->\n"
        )
        first = views.build_release_notes_view(change_log)
        assert first == views.build_release_notes_view(change_log)

    def test_multiple_entries_same_scope_collapse_to_one_block(self):
        # Two change-log entries share BOTH release= AND scope= (the real v1.4.0
        # shape). They must collapse to ONE flat block with union'd chunks — NOT
        # two identical "### v1.4" sub-headings (regression the cumulative Critic
        # caught: scope is not unique within a release, so render groups by scope).
        change_log = (
            "## 2026-03-01: v1.4 wave 1 (v1.4.0)\n"
            "<!-- prawduct: release=v1.4.0 | status=shipped | scope=v1.4 -->\n"
            "## 2026-03-02: v1.4 wave 2 (v1.4.0)\n"
            "<!-- prawduct: chunks=05,06 | release=v1.4.0 | status=shipped | scope=v1.4 -->\n"
        )
        out = views.build_release_notes_view(change_log)
        assert out is not None
        assert out.count("## v1.4.0") == 1
        assert "### " not in out  # same scope -> single flat block, no sub-headings
        assert "**Chunks shipped:** 05, 06" in out  # chunks union'd under one block
        assert "**Scope:** v1.4" in out
        assert "v1.4 wave 1" in out  # first entry's title is the block title

    def test_mixed_same_scope_and_distinct_scope_in_one_release(self):
        # A release with TWO entries of scope=a (collapse) + one entry scope=b
        # renders exactly TWO sub-sections (### a with union'd chunks, ### b).
        change_log = (
            "## d1: a part 1\n"
            "<!-- prawduct: chunks=01 | release=v3 | status=shipped | scope=a -->\n"
            "## d2: b\n"
            "<!-- prawduct: chunks=09 | release=v3 | status=shipped | scope=b -->\n"
            "## d3: a part 2\n"
            "<!-- prawduct: chunks=02 | release=v3 | status=shipped | scope=a -->\n"
        )
        out = views.build_release_notes_view(change_log)
        assert out is not None
        assert out.count("### ") == 2  # scope a (merged) + scope b
        assert "### a" in out and "### b" in out
        chunks_lines = [ln for ln in out.splitlines() if ln.startswith("**Chunks shipped:**")]
        assert "**Chunks shipped:** 01, 02" in chunks_lines  # a's two entries union'd
        assert "**Chunks shipped:** 09" in chunks_lines  # b alone

    def test_idempotent_against_own_output(self):
        change_log = (
            "## 2026-05-18: rel\n"
            "<!-- prawduct: chunks=00 | release=v1.3.17 | status=shipped -->\n"
        )
        first = views.build_release_notes_view(change_log)
        # Feeding the same input twice produces identical content.
        second = views.build_release_notes_view(change_log)
        assert first == second

    def test_entries_without_release_tag_excluded(self):
        change_log = (
            "## 2026-05-18: with release\n"
            "<!-- prawduct: chunks=00 | release=v1.3.17 | status=shipped -->\n"
            "## 2026-05-19: no release\n"
            "<!-- prawduct: chunks=05 | status=shipped | scope=v1.4 -->\n"
        )
        out = views.build_release_notes_view(change_log)
        assert out is not None
        # Only the release-tagged entry appears.
        assert "## v1.3.17" in out
        assert "**Chunks shipped:** 00" in out
        # The unreleased shipped chunk does not appear in any Chunks line.
        chunks_lines = [ln for ln in out.splitlines() if ln.startswith("**Chunks shipped:**")]
        assert all("05" not in ln for ln in chunks_lines)


# =============================================================================
# Pure-function tests — shared plan_regen / apply_regen helpers
# =============================================================================


def _make_prawduct_dir(
    tmp_path: Path,
    *,
    views_enabled: bool = True,
    change_log: str = "",
    build_plan: str = "## Status\n",
    extra_state: str = "",
) -> Path:
    """Build a minimal `.prawduct/` skeleton for plan_regen/apply_regen tests."""
    prawduct_dir = tmp_path / ".prawduct"
    (prawduct_dir / "artifacts").mkdir(parents=True)
    state = ("views_enabled: true\n" if views_enabled else "views_enabled: false\n") + extra_state
    (prawduct_dir / "project-state.yaml").write_text(state)
    (prawduct_dir / "change-log.md").write_text(change_log)
    (prawduct_dir / "artifacts" / "build-plan.md").write_text(build_plan)
    return prawduct_dir


class TestPlanRegen:
    def test_disabled_returns_empty(self, tmp_path: Path):
        prawduct_dir = _make_prawduct_dir(tmp_path, views_enabled=False)
        enabled, results = views.plan_regen(prawduct_dir)
        assert enabled is False
        assert results == []

    def test_enabled_returns_three_results(self, tmp_path: Path):
        prawduct_dir = _make_prawduct_dir(
            tmp_path,
            change_log=(
                "## 2026-05-18: rel\n"
                "<!-- prawduct: chunks=00 | release=v1.3.17 | status=shipped | scope=v1.4 -->\n"
            ),
            build_plan="## Status\n- [ ] Chunk 00: A\n",
        )
        enabled, results = views.plan_regen(prawduct_dir)
        assert enabled is True
        names = [r.name for r in results]
        assert names == ["status", "release-notes", "scope-rollups"]
        # Status would flip; release-notes would be created; scope would be written.
        actions = {r.name: r.action for r in results}
        assert actions["status"] == "write"
        assert actions["release-notes"] == "create"
        assert actions["scope-rollups"] == "write"

    def test_idempotent_after_apply_regen(self, tmp_path: Path):
        prawduct_dir = _make_prawduct_dir(
            tmp_path,
            change_log=(
                "## 2026-05-18: rel\n"
                "<!-- prawduct: chunks=00 | release=v1.3.17 | status=shipped | scope=v1.4 -->\n"
            ),
            build_plan="## Status\n- [ ] Chunk 00: A\n",
        )
        # First plan + apply.
        _, results = views.plan_regen(prawduct_dir)
        views.apply_regen(prawduct_dir, results)
        # Second plan: every view should now be a noop.
        _, second_results = views.plan_regen(prawduct_dir)
        assert all(r.action == "noop" for r in second_results)

    def test_missing_change_log_raises(self, tmp_path: Path):
        prawduct_dir = tmp_path / ".prawduct"
        (prawduct_dir / "artifacts").mkdir(parents=True)
        (prawduct_dir / "project-state.yaml").write_text("views_enabled: true\n")
        (prawduct_dir / "artifacts" / "build-plan.md").write_text("## Status\n")
        with pytest.raises(FileNotFoundError):
            views.plan_regen(prawduct_dir)

    def test_active_build_plan_pointer_targets_scope_named_plan(self, tmp_path: Path):
        """With `active_build_plan:` set, regen resolves and flips the scope-named
        plan — not a phantom build-plan.md (v1.6.0 Chunk 06)."""
        prawduct_dir = tmp_path / ".prawduct"
        (prawduct_dir / "artifacts").mkdir(parents=True)
        (prawduct_dir / "project-state.yaml").write_text(
            "views_enabled: true\n"
            "active_build_plan: artifacts/v1.6.0-foo-plan.md\n"
        )
        (prawduct_dir / "change-log.md").write_text(
            "## 2026-05-29: rel\n"
            "<!-- prawduct: chunks=01 | release=v1.6.0 | status=shipped | scope=v1.6.0 -->\n"
        )
        # Scope-named plan with matching frontmatter scope; no build-plan.md exists.
        (prawduct_dir / "artifacts" / "v1.6.0-foo-plan.md").write_text(
            "---\nartifact: build-plan\nscope: v1.6.0\n---\n\n## Status\n- [ ] Chunk 01: A\n"
        )
        enabled, results = views.plan_regen(prawduct_dir)
        assert enabled is True
        status = next(r for r in results if r.name == "status")
        assert status.path_relative == "artifacts/v1.6.0-foo-plan.md"
        assert status.action == "write"
        views.apply_regen(prawduct_dir, results)
        flipped = (prawduct_dir / "artifacts" / "v1.6.0-foo-plan.md").read_text()
        assert "- [x] Chunk 01: A" in flipped
        # No phantom build-plan.md was created.
        assert not (prawduct_dir / "artifacts" / "build-plan.md").exists()


class TestApplyRegen:
    def test_writes_files_for_non_noop_results(self, tmp_path: Path):
        prawduct_dir = _make_prawduct_dir(
            tmp_path,
            change_log=(
                "## 2026-05-18: rel\n"
                "<!-- prawduct: chunks=00 | release=v1.3.17 | status=shipped | scope=v1.4 -->\n"
            ),
            build_plan="## Status\n- [ ] Chunk 00: A\n",
        )
        _, results = views.plan_regen(prawduct_dir)
        views.apply_regen(prawduct_dir, results)
        # All three outputs landed.
        assert (prawduct_dir / "release-notes.md").exists()
        plan = (prawduct_dir / "artifacts" / "build-plan.md").read_text()
        assert "- [x] Chunk 00: A" in plan
        state = (prawduct_dir / "project-state.yaml").read_text()
        assert "scope_rollups:" in state

    def test_noops_dont_touch_files(self, tmp_path: Path):
        """apply_regen with a list of noop-only results must not mutate any file."""
        prawduct_dir = _make_prawduct_dir(
            tmp_path,
            change_log="## 2026-05-18: untagged\n",
            build_plan="## Status\n- [ ] Chunk 00: A\n",
        )
        _, results = views.plan_regen(prawduct_dir)
        # Capture pre-state.
        before_plan = (prawduct_dir / "artifacts" / "build-plan.md").read_text()
        before_state = (prawduct_dir / "project-state.yaml").read_text()
        views.apply_regen(prawduct_dir, [r for r in results if r.action == "noop"])
        assert (prawduct_dir / "artifacts" / "build-plan.md").read_text() == before_plan
        assert (prawduct_dir / "project-state.yaml").read_text() == before_state
        assert not (prawduct_dir / "release-notes.md").exists()


class TestPlanRegenNoResolvablePlan:
    """VWS-7N3K: a clean release boundary — change-log has release/shipped
    entries but no build plan resolves — must regenerate the plan-independent
    release-notes + scope-rollups views, NOT abort the whole regen. The hard
    FileNotFoundError fires only when a plan is genuinely expected (an
    explicitly-pinned but missing ``active_build_plan``)."""

    @staticmethod
    def _dir(tmp_path: Path, state: str, change_log: str) -> Path:
        prawduct_dir = tmp_path / ".prawduct"
        (prawduct_dir / "artifacts").mkdir(parents=True)
        (prawduct_dir / "project-state.yaml").write_text(state)
        (prawduct_dir / "change-log.md").write_text(change_log)
        # Deliberately NO build-plan.md and no scope-tagged plan file on disk.
        return prawduct_dir

    _CHANGE_LOG = (
        "## 2026-06-24: ship\n"
        "<!-- prawduct: chunks=01 | release=v1.6.1 | status=shipped | scope=aud -->\n"
    )

    def test_null_pointer_no_plan_regenerates_independent_views(self, tmp_path: Path):
        # The exact reported scenario: active_build_plan: null, no resolvable plan.
        prawduct_dir = self._dir(
            tmp_path,
            "views_enabled: true\nactive_build_plan: null\n",
            self._CHANGE_LOG,
        )
        enabled, results = views.plan_regen(prawduct_dir)  # must NOT raise
        assert enabled is True
        names = [r.name for r in results]
        assert "status" not in names  # no status view when no plan resolves
        assert "release-notes" in names and "scope-rollups" in names
        # The consumer-facing release-notes view DOES regenerate (was the symptom).
        rn = next(r for r in results if r.name == "release-notes")
        assert rn.action == "create"

    def test_unset_pointer_no_plan_does_not_raise(self, tmp_path: Path):
        # Pointer entirely absent (not even null) — same legitimate no-op.
        prawduct_dir = self._dir(
            tmp_path, "views_enabled: true\n", self._CHANGE_LOG
        )
        enabled, results = views.plan_regen(prawduct_dir)  # must NOT raise
        assert enabled is True
        assert "status" not in [r.name for r in results]
        assert "release-notes" in [r.name for r in results]

    def test_explicitly_pinned_missing_plan_still_raises(self, tmp_path: Path):
        # A SET pointer to a missing file is a genuine misconfiguration — the
        # loud FileNotFoundError must survive (keeps STH-5P2W's guard meaningful).
        prawduct_dir = self._dir(
            tmp_path,
            "views_enabled: true\nactive_build_plan: artifacts/gone-plan.md\n",
            "## 2026-06-24: untagged note\n",
        )
        with pytest.raises(FileNotFoundError):
            views.plan_regen(prawduct_dir)

    def test_null_pointer_with_existing_default_plan_still_regenerates_status(
        self, tmp_path: Path
    ):
        # Regression guard for the historical single-plan path: a null pointer
        # with an EXISTING artifacts/build-plan.md still regenerates that plan's
        # status (the no-op only applies when nothing resolves).
        prawduct_dir = self._dir(
            tmp_path,
            "views_enabled: true\nactive_build_plan: null\n",
            self._CHANGE_LOG,
        )
        (prawduct_dir / "artifacts" / "build-plan.md").write_text(
            "## Status\n- [ ] Chunk 01: A\n"
        )
        enabled, results = views.plan_regen(prawduct_dir)
        assert enabled is True
        assert "status" in [r.name for r in results]


# =============================================================================
# Multi-scope regen (REL-4T8N): scope→plan map, scope enumeration, diagnostics,
# and plan_regen flipping every release-pending plan in one pass.
# =============================================================================


def _write_scoped_plan(
    artifacts_dir: Path, filename: str, scope: str | None, chunk_ids: list[str]
) -> None:
    """Write a minimal scope-tagged build plan with the given chunk lines."""
    front = "---\nartifact: build-plan\n"
    if scope is not None:
        front += f"scope: {scope}\n"
    front += "---\n\n## Status\n"
    body = "".join(f"- [ ] Chunk {cid}: work\n" for cid in chunk_ids)
    (artifacts_dir / filename).write_text(front + body)


class TestBuildScopeToPlanMap:
    def test_maps_each_scope_to_its_plan_file(self, tmp_path: Path):
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        _write_scoped_plan(artifacts, "build-plan-alpha.md", "alpha", ["01"])
        _write_scoped_plan(artifacts, "build-plan-beta.md", "beta", ["01"])
        mapping = views.build_scope_to_plan_map(artifacts)
        assert set(mapping) == {"alpha", "beta"}
        assert mapping["alpha"].name == "build-plan-alpha.md"
        assert mapping["beta"].name == "build-plan-beta.md"

    def test_excludes_plans_without_scope_frontmatter(self, tmp_path: Path):
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        _write_scoped_plan(artifacts, "build-plan-alpha.md", "alpha", ["01"])
        _write_scoped_plan(artifacts, "build-plan.md", None, ["01"])  # no scope
        (artifacts / "project-preferences.md").write_text("# prefs, not a plan\n")
        mapping = views.build_scope_to_plan_map(artifacts)
        assert set(mapping) == {"alpha"}

    def test_duplicate_scope_keeps_first_by_sorted_filename(self, tmp_path: Path):
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        _write_scoped_plan(artifacts, "b-plan.md", "dup", ["01"])
        _write_scoped_plan(artifacts, "a-plan.md", "dup", ["02"])
        mapping = views.build_scope_to_plan_map(artifacts)
        assert mapping["dup"].name == "a-plan.md"  # first by sorted filename

    def test_missing_dir_returns_empty(self, tmp_path: Path):
        assert views.build_scope_to_plan_map(tmp_path / "nope") == {}


class TestCollectReleasePendingScopes:
    def test_includes_shipped_and_merged_newest_first_deduped(self):
        change_log = (
            "## 2026-06-04: c (newest)\n"
            "<!-- prawduct: chunks=01 | status=shipped | scope=gamma -->\n"
            "## 2026-06-03: b\n"
            "<!-- prawduct: chunks=01 | status=merged | scope=beta -->\n"
            "## 2026-06-02: a (dup scope=gamma)\n"
            "<!-- prawduct: chunks=02 | status=shipped | scope=gamma -->\n"
        )
        scopes = views.collect_release_pending_scopes(views.parse_change_log(change_log))
        assert scopes == ["gamma", "beta"]  # newest-first, deduped

    def test_excludes_untagged_and_other_status(self):
        change_log = (
            "## 2026-06-04: untagged\n\nBody.\n"
            "## 2026-06-03: in-progress\n"
            "<!-- prawduct: chunks=01 | status=in-progress | scope=wip -->\n"
            "## 2026-06-02: no-scope shipped\n"
            "<!-- prawduct: chunks=01 | status=shipped -->\n"
        )
        scopes = views.collect_release_pending_scopes(views.parse_change_log(change_log))
        assert scopes == []  # wip status excluded; shipped-without-scope contributes no scope

    def test_statusless_tagged_scope_is_release_pending(self):
        """single-pr-bookkeeping: a statusless tagged entry IS the
        release-pending state — no stamp-merged pass required for its scope
        to be enumerated at a batched release."""
        change_log = (
            "## 2026-07-10: statusless (newest)\n"
            "<!-- prawduct: chunks=01 | scope=delta -->\n"
            "## 2026-07-09: merged (legacy stamp)\n"
            "<!-- prawduct: chunks=01 | status=merged | scope=beta -->\n"
        )
        scopes = views.collect_release_pending_scopes(views.parse_change_log(change_log))
        assert scopes == ["delta", "beta"]

    def test_statusless_without_scope_and_typo_status_still_excluded(self):
        change_log = (
            "## 2026-07-10: statusless, no scope\n"
            "<!-- prawduct: chunks=01 -->\n"
            "## 2026-07-09: typoed status\n"
            "<!-- prawduct: chunks=01 | status=shippd | scope=typo -->\n"
        )
        scopes = views.collect_release_pending_scopes(views.parse_change_log(change_log))
        assert scopes == []  # no scope to contribute; typo is the typo-guard's finding


class TestDiagnoseScopePlanCoverage:
    def test_merged_scope_without_plan_file_warns(self, tmp_path: Path):
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        change_log = (
            "## 2026-06-04: pending\n"
            "<!-- prawduct: chunks=01 | status=merged | scope=orphan -->\n"
        )
        warnings = views.diagnose_scope_plan_coverage(change_log, artifacts)
        assert len(warnings) == 1
        assert "orphan" in warnings[0] and "release-pending" in warnings[0]

    def test_shipped_scope_without_plan_file_is_silent(self, tmp_path: Path):
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        change_log = (
            "## 2026-06-04: historical\n"
            "<!-- prawduct: chunks=01 | status=shipped | scope=v1.0 -->\n"
        )
        assert views.diagnose_scope_plan_coverage(change_log, artifacts) == []

    def test_merged_scope_with_plan_file_is_clean(self, tmp_path: Path):
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        _write_scoped_plan(artifacts, "build-plan-ok.md", "ok", ["01"])
        change_log = (
            "## 2026-06-04: pending\n"
            "<!-- prawduct: chunks=01 | status=merged | scope=ok -->\n"
        )
        assert views.diagnose_scope_plan_coverage(change_log, artifacts) == []

    def test_duplicate_scope_warns(self, tmp_path: Path):
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        _write_scoped_plan(artifacts, "a-plan.md", "dup", ["01"])
        _write_scoped_plan(artifacts, "b-plan.md", "dup", ["02"])
        warnings = views.diagnose_scope_plan_coverage("", artifacts)
        assert any("duplicate scope" in w and "dup" in w for w in warnings)

    # --- statusless extension (REL-9F2T audit finding d) ---

    def test_statusless_tagged_scope_without_plan_file_warns(self, tmp_path: Path):
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        change_log = (
            "## 2026-06-04: unstamped\n"
            "<!-- prawduct: chunks=01 | scope=orphan -->\n"
        )
        warnings = views.diagnose_scope_plan_coverage(change_log, artifacts)
        assert len(warnings) == 1
        assert "orphan" in warnings[0]
        assert "statusless" in warnings[0]
        # single-pr-bookkeeping: statusless is the expected release-pending
        # state, not a missed stamp — the label must not blame the author.
        assert "release-pending" in warnings[0]
        assert "stamp" not in warnings[0]

    def test_statusless_tagged_scope_with_plan_file_is_clean(self, tmp_path: Path):
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        _write_scoped_plan(artifacts, "build-plan-ok.md", "ok", ["01"])
        change_log = (
            "## 2026-06-04: unstamped\n"
            "<!-- prawduct: chunks=01 | scope=ok -->\n"
        )
        assert views.diagnose_scope_plan_coverage(change_log, artifacts) == []

    def test_typo_status_scope_without_plan_file_is_silent(self, tmp_path: Path):
        """A typoed status= is the typo-guard's finding, not this diagnostic's —
        one warning per failure, no double-reporting."""
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        change_log = (
            "## 2026-06-04: typoed\n"
            "<!-- prawduct: chunks=01 | status=shippd | scope=orphan -->\n"
        )
        assert views.diagnose_scope_plan_coverage(change_log, artifacts) == []

    def test_statusless_and_merged_same_scope_warn_once(self, tmp_path: Path):
        artifacts = tmp_path / "artifacts"
        artifacts.mkdir()
        change_log = (
            "## 2026-06-04: merged half\n"
            "<!-- prawduct: chunks=01 | status=merged | scope=orphan -->\n"
            "## 2026-06-03: unstamped half\n"
            "<!-- prawduct: chunks=02 | scope=orphan -->\n"
        )
        warnings = views.diagnose_scope_plan_coverage(change_log, artifacts)
        assert len(warnings) == 1


class TestStampMerged:
    """stamp_merged: the statusless→merged transition, applied mechanically.

    REL-2N8K: the lifecycle documents the stamp but nothing applied it, so
    most entries reached release-prep statusless and a literal reading of
    release-process step 3 silently dropped them (v2.0.14: 8 of 10).
    """

    def test_statusless_tagged_entry_stamped_preserving_tags(self):
        content = (
            "## 2026-06-04: new work\n"
            "<!-- prawduct: type=fix | chunks=01,02 | scope=alpha -->\n"
            "\n"
            "**Why:** body.\n"
        )
        new_content, stamped = views.stamp_merged(content)
        assert stamped == ["2026-06-04: new work"]
        assert (
            "<!-- prawduct: type=fix | chunks=01,02 | scope=alpha | status=merged -->"
            in new_content
        )
        assert "**Why:** body.\n" in new_content

    def test_untagged_entry_untouched(self):
        content = "## 2026-04-01: historical\n\n**Why:** pre-tagging era.\n"
        new_content, stamped = views.stamp_merged(content)
        assert stamped == []
        assert new_content == content

    def test_shipped_and_merged_entries_untouched(self):
        content = (
            "## A\n<!-- prawduct: chunks=01 | status=shipped | scope=x -->\n"
            "## B\n<!-- prawduct: chunks=02 | status=merged | scope=x -->\n"
        )
        new_content, stamped = views.stamp_merged(content)
        assert stamped == []
        assert new_content == content

    def test_typoed_status_untouched(self):
        """A present-but-typoed status= belongs to the typo-guard; stamping
        over it would mask the typo instead of surfacing it."""
        content = "## A\n<!-- prawduct: chunks=01 | status=shippd -->\n"
        new_content, stamped = views.stamp_merged(content)
        assert stamped == []
        assert new_content == content

    def test_idempotent(self):
        content = "## A\n<!-- prawduct: chunks=01 | scope=x -->\n"
        once, stamped_once = views.stamp_merged(content)
        twice, stamped_twice = views.stamp_merged(once)
        assert stamped_once == ["A"]
        assert stamped_twice == []
        assert twice == once

    def test_stamps_every_statusless_entry_convergent(self):
        content = (
            "## newest\n<!-- prawduct: chunks=03 | scope=c -->\n"
            "## already merged\n<!-- prawduct: chunks=02 | status=merged -->\n"
            "## missed by an earlier merge\n<!-- prawduct: chunks=01 | scope=a -->\n"
        )
        new_content, stamped = views.stamp_merged(content)
        assert stamped == ["newest", "missed by an earlier merge"]
        assert new_content.count("status=merged") == 3

    def test_multi_tag_entry_stamped_on_first_line_only(self):
        content = (
            "## A\n"
            "<!-- prawduct: chunks=01 -->\n"
            "<!-- prawduct: chunks=02 -->\n"
        )
        new_content, stamped = views.stamp_merged(content)
        assert stamped == ["A"]
        assert "<!-- prawduct: chunks=01 | status=merged -->" in new_content
        assert "<!-- prawduct: chunks=02 -->" in new_content

    def test_multi_tag_entry_with_status_on_second_line_untouched(self):
        content = (
            "## A\n"
            "<!-- prawduct: chunks=01 -->\n"
            "<!-- prawduct: chunks=02 | status=shipped -->\n"
        )
        new_content, stamped = views.stamp_merged(content)
        assert stamped == []
        assert new_content == content

    def test_tag_after_prose_is_body_content_not_stamped(self):
        content = (
            "## A\n\nProse first.\n\n<!-- prawduct: chunks=01 -->\n"
        )
        new_content, stamped = views.stamp_merged(content)
        assert stamped == []
        assert new_content == content


class TestMultiScopePlanRegen:
    def _prawduct_dir(self, tmp_path: Path, change_log: str) -> Path:
        prawduct_dir = tmp_path / ".prawduct"
        (prawduct_dir / "artifacts").mkdir(parents=True)
        (prawduct_dir / "project-state.yaml").write_text("views_enabled: true\n")
        (prawduct_dir / "change-log.md").write_text(change_log)
        return prawduct_dir

    def test_flips_every_plan_in_one_pass_no_cross_scope_leak(self, tmp_path: Path):
        change_log = (
            "## 2026-06-04: alpha\n"
            "<!-- prawduct: chunks=01,02 | release=v9 | status=shipped | scope=alpha -->\n"
            "## 2026-06-04: beta\n"
            "<!-- prawduct: chunks=01 | release=v9 | status=shipped | scope=beta -->\n"
        )
        prawduct_dir = self._prawduct_dir(tmp_path, change_log)
        artifacts = prawduct_dir / "artifacts"
        # Both plans CONTAIN a Chunk 02; only alpha shipped 02. beta's 02 must
        # stay unshipped — proving the per-plan scope filter blocks leakage.
        _write_scoped_plan(artifacts, "build-plan-alpha.md", "alpha", ["01", "02"])
        _write_scoped_plan(artifacts, "build-plan-beta.md", "beta", ["01", "02"])

        enabled, results = views.plan_regen(prawduct_dir)
        assert enabled is True
        status = [r for r in results if r.name == "status"]
        assert {r.path_relative for r in status} == {
            "artifacts/build-plan-alpha.md",
            "artifacts/build-plan-beta.md",
        }
        views.apply_regen(prawduct_dir, results)

        alpha = (artifacts / "build-plan-alpha.md").read_text()
        beta = (artifacts / "build-plan-beta.md").read_text()
        assert "- [x] Chunk 01: work" in alpha and "- [x] Chunk 02: work" in alpha
        assert "- [x] Chunk 01: work" in beta
        assert "- [ ] Chunk 02: work" in beta  # NO leak from alpha's shipped 02

    def test_merged_scope_plan_regenerated_but_chunks_stay_unshipped(self, tmp_path: Path):
        change_log = (
            "## 2026-06-04: pending\n"
            "<!-- prawduct: chunks=01 | status=merged | scope=gamma -->\n"
        )
        prawduct_dir = self._prawduct_dir(tmp_path, change_log)
        artifacts = prawduct_dir / "artifacts"
        _write_scoped_plan(artifacts, "build-plan-gamma.md", "gamma", ["01"])
        # Pre-mark [x] to prove a merged (not shipped) scope flips it BACK to [ ].
        p = artifacts / "build-plan-gamma.md"
        p.write_text(p.read_text().replace("- [ ] Chunk 01", "- [x] Chunk 01"))

        _, results = views.plan_regen(prawduct_dir)
        views.apply_regen(prawduct_dir, results)
        assert "- [ ] Chunk 01: work" in p.read_text()  # merged does not flip to [x]

    def test_scope_without_plan_file_skipped_not_fatal(self, tmp_path: Path):
        change_log = (
            "## 2026-06-04: alpha\n"
            "<!-- prawduct: chunks=01 | status=shipped | scope=alpha -->\n"
            "## 2026-06-04: orphan (no plan file)\n"
            "<!-- prawduct: chunks=01 | status=merged | scope=orphan -->\n"
        )
        prawduct_dir = self._prawduct_dir(tmp_path, change_log)
        _write_scoped_plan(prawduct_dir / "artifacts", "build-plan-alpha.md", "alpha", ["01"])

        enabled, results = views.plan_regen(prawduct_dir)  # must NOT raise
        assert enabled is True
        status_paths = {r.path_relative for r in results if r.name == "status"}
        assert status_paths == {"artifacts/build-plan-alpha.md"}  # orphan skipped

    def test_pointer_plan_regenerated_even_when_scope_not_release_pending(self, tmp_path: Path):
        # An in-progress pinned plan (its scope NOT yet in the change-log) is
        # still regenerated, alongside a separate release-pending scope.
        change_log = (
            "## 2026-06-04: shipped scope\n"
            "<!-- prawduct: chunks=01 | status=shipped | scope=alpha -->\n"
        )
        prawduct_dir = tmp_path / ".prawduct"
        (prawduct_dir / "artifacts").mkdir(parents=True)
        (prawduct_dir / "project-state.yaml").write_text(
            "views_enabled: true\n"
            "active_build_plan: artifacts/build-plan-wip.md\n"
        )
        (prawduct_dir / "change-log.md").write_text(change_log)
        artifacts = prawduct_dir / "artifacts"
        _write_scoped_plan(artifacts, "build-plan-alpha.md", "alpha", ["01"])
        _write_scoped_plan(artifacts, "build-plan-wip.md", "wip", ["01"])  # not in change-log

        _, results = views.plan_regen(prawduct_dir)
        status_paths = {r.path_relative for r in results if r.name == "status"}
        assert status_paths == {
            "artifacts/build-plan-alpha.md",
            "artifacts/build-plan-wip.md",
        }

    def test_idempotent_second_pass_all_status_noop(self, tmp_path: Path):
        change_log = (
            "## 2026-06-04: alpha\n"
            "<!-- prawduct: chunks=01 | status=shipped | scope=alpha -->\n"
            "## 2026-06-04: beta\n"
            "<!-- prawduct: chunks=01 | status=shipped | scope=beta -->\n"
        )
        prawduct_dir = self._prawduct_dir(tmp_path, change_log)
        artifacts = prawduct_dir / "artifacts"
        _write_scoped_plan(artifacts, "build-plan-alpha.md", "alpha", ["01"])
        _write_scoped_plan(artifacts, "build-plan-beta.md", "beta", ["01"])
        _, results = views.plan_regen(prawduct_dir)
        views.apply_regen(prawduct_dir, results)
        _, second = views.plan_regen(prawduct_dir)
        assert all(r.action == "noop" for r in second if r.name == "status")


# =============================================================================
# Integration tests — prawduct-hook regen-views subcommand
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


def _run_regen(
    product_dir: Path, *extra_args: str
) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(product_dir)}
    return subprocess.run(
        ["python3", str(HOOK_PATH), "regen-views", *extra_args],
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
        out = result.stdout.lower()
        # Status view reports its idempotent state with one of these phrases.
        assert "up to date" in out or "no changes" in out

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

    def test_unset_pointer_missing_plan_returns_zero_and_regenerates_views(
        self, tmp_path: Path
    ):
        # VWS-7N3K (contract change): with NO pointer and no resolvable plan, a
        # clean release boundary must regenerate the plan-independent views and
        # exit 0 — NOT abort the whole regen. This replaces the prior
        # `test_missing_build_plan_returns_nonzero`, which pinned the buggy
        # contract where an absent plan took down release-notes + scope-rollups.
        product = tmp_path / "product"
        (product / ".prawduct" / "artifacts").mkdir(parents=True)
        (product / ".prawduct" / "project-state.yaml").write_text("views_enabled: true\n")
        (product / ".prawduct" / "change-log.md").write_text(
            "## 2026-06-24: ship\n"
            "<!-- prawduct: chunks=01 | release=v1.6.1 | status=shipped | scope=aud -->\n"
        )
        # No build-plan.md, no scope-tagged plan for `aud` → nothing resolves.
        result = _run_regen(product)
        assert result.returncode == 0, result.stderr
        # The consumer-facing release-notes view regenerated despite no plan.
        assert (product / ".prawduct" / "release-notes.md").exists()

    def test_pinned_missing_plan_returns_nonzero(self, tmp_path: Path):
        # The genuine-misconfiguration case is preserved: an EXPLICITLY-pinned
        # `active_build_plan` that resolves to no file is a loud error (exit 2),
        # keeping the STH-5P2W briefing guard meaningful.
        product = tmp_path / "product"
        (product / ".prawduct" / "artifacts").mkdir(parents=True)
        (product / ".prawduct" / "project-state.yaml").write_text(
            "views_enabled: true\nactive_build_plan: artifacts/gone-plan.md\n"
        )
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


class TestRegenViewsAllThree:
    """End-to-end: a single regen-views invocation produces all three views."""

    def test_three_views_in_one_pass(self, tmp_path: Path):
        product = _make_product_repo(
            tmp_path,
            views_enabled=True,
            change_log=(
                "## 2026-05-18: v1.4 Wave 1 (v1.3.17)\n"
                "<!-- prawduct: chunks=00,01,02 | release=v1.3.17 | status=shipped | scope=v1.4 -->\n"
            ),
            build_plan=(
                "## Status\n"
                "- [ ] Chunk 00: A\n"
                "- [ ] Chunk 01: B\n"
                "- [ ] Chunk 02: C\n"
            ),
        )
        result = _run_regen(product)
        assert result.returncode == 0, result.stderr

        # 1) Status view applied.
        plan = (product / ".prawduct" / "artifacts" / "build-plan.md").read_text()
        assert "- [x] Chunk 00: A" in plan
        assert "- [x] Chunk 02: C" in plan

        # 2) Release-notes view created.
        rn_path = product / ".prawduct" / "release-notes.md"
        assert rn_path.exists()
        rn = rn_path.read_text()
        assert "# Release Notes" in rn
        assert "## v1.3.17" in rn
        assert "**Chunks shipped:** 00, 01, 02" in rn

        # 3) Scope-rollups appended to project-state.yaml.
        state = (product / ".prawduct" / "project-state.yaml").read_text()
        assert "scope_rollups:" in state
        assert "v1.4:" in state
        assert '"v1.3.17"' in state

        # Output summarizes all three.
        out = result.stdout.lower()
        assert "status" in out
        assert "release notes" in out
        assert "scope" in out

    def test_idempotent_three_views(self, tmp_path: Path):
        product = _make_product_repo(
            tmp_path,
            views_enabled=True,
            change_log=(
                "## 2026-05-18: rel\n"
                "<!-- prawduct: chunks=00 | release=v1.3.17 | status=shipped | scope=v1.4 -->\n"
            ),
            build_plan="## Status\n- [x] Chunk 00: A\n",
        )
        first = _run_regen(product)
        assert first.returncode == 0
        # Capture file mtimes/contents after first regen.
        rn_after_first = (product / ".prawduct" / "release-notes.md").read_text()
        state_after_first = (product / ".prawduct" / "project-state.yaml").read_text()
        plan_after_first = (product / ".prawduct" / "artifacts" / "build-plan.md").read_text()

        # Second run: should report up-to-date and produce identical content.
        second = _run_regen(product)
        assert second.returncode == 0
        assert (product / ".prawduct" / "release-notes.md").read_text() == rn_after_first
        assert (product / ".prawduct" / "project-state.yaml").read_text() == state_after_first
        assert (product / ".prawduct" / "artifacts" / "build-plan.md").read_text() == plan_after_first
        # And output reflects no work done.
        assert "up to date" in second.stdout.lower() or "no changes" in second.stdout.lower()


class TestRegenViewsImportError:
    """STH-2J9F: a broken/incomplete install (lib/ unimportable) must fail
    honestly with exit 1 — a state-mutating command must not report success
    when its machinery is absent (mirrors accept/verify-operator-verification).
    """

    def test_import_error_returns_exit_1(self, tmp_path: Path):
        product = _make_product_repo(
            tmp_path,
            views_enabled=True,
            change_log=(
                "## 2026-05-18: rel\n"
                "<!-- prawduct: chunks=00 | status=shipped -->\n"
            ),
            build_plan="## Status\n- [ ] Chunk 00: A\n",
        )
        # Point CLAUDE_PLUGIN_ROOT at an empty dir with no lib/ package so
        # `from lib import views` raises ImportError. The script's own dir is
        # bin/, which has no lib/ either, so the import genuinely fails.
        empty_root = tmp_path / "empty_plugin_root"
        empty_root.mkdir()
        env = {
            **os.environ,
            "CLAUDE_PROJECT_DIR": str(product),
            "CLAUDE_PLUGIN_ROOT": str(empty_root),
        }
        result = subprocess.run(
            ["python3", str(HOOK_PATH), "regen-views"],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(product),
            timeout=20,
        )
        assert result.returncode == 1, (result.stdout, result.stderr)
        assert "could not import" in result.stderr.lower()
        # Build plan was NOT silently regenerated under the broken install.
        assert (
            "- [ ] Chunk 00: A"
            in (product / ".prawduct" / "artifacts" / "build-plan.md").read_text()
        )


class TestRegenViewsStatusTypoError:
    """VWS-3K7P → VWS-6R4T: a change-log `status=` typo is now FATAL. The
    typoed entry would silently never flip, so regen fails closed — exit 2,
    ERROR on stderr, and NOTHING written (not even the valid entries — a
    partial flip is the failure class the fail-closed contract forbids)."""

    def test_typo_errors_and_writes_nothing(self, tmp_path: Path):
        product = _make_product_repo(
            tmp_path,
            views_enabled=True,
            change_log=(
                "## 2026-06-04: good entry\n"
                "<!-- prawduct: chunks=00 | status=shipped -->\n"
                "\n"
                "## 2026-06-04: typoed entry\n"
                "<!-- prawduct: chunks=01 | status=shippd -->\n"
            ),
            build_plan=(
                "## Status\n"
                "- [ ] Chunk 00: A\n"
                "- [ ] Chunk 01: B\n"
            ),
        )
        result = _run_regen(product)
        assert result.returncode == 2, result.stdout + result.stderr
        assert "shippd" in result.stderr
        assert "ERROR" in result.stderr
        assert "no views written" in result.stderr
        new_plan = (product / ".prawduct" / "artifacts" / "build-plan.md").read_text()
        # Fail closed: NOTHING flipped, valid entry included.
        assert "- [ ] Chunk 00: A" in new_plan
        assert "- [ ] Chunk 01: B" in new_plan

    def test_no_warning_when_all_valid(self, tmp_path: Path):
        product = _make_product_repo(
            tmp_path,
            views_enabled=True,
            change_log=(
                "## 2026-06-04: shipped entry\n"
                "<!-- prawduct: chunks=00 | status=shipped -->\n"
                "\n"
                "## 2026-06-04: merged entry\n"
                "<!-- prawduct: chunks=01 | status=merged -->\n"
            ),
            build_plan="## Status\n- [ ] Chunk 00: A\n- [ ] Chunk 01: B\n",
        )
        result = _run_regen(product)
        assert result.returncode == 0, result.stderr
        assert "WARNING" not in result.stderr


class TestRegenViewsMultiTagLineWarning:
    """VWS-4D8J end-to-end: an entry with two tag lines is unioned (both
    chunks flip) AND surfaced on stderr as a NON-fatal warning telling the
    author to merge the lines — regen still succeeds (exit 0)."""

    def test_multi_tag_entry_warns_on_stderr_and_unions(self, tmp_path: Path):
        product = _make_product_repo(
            tmp_path,
            views_enabled=True,
            change_log=(
                "## 2026-06-04: two-line entry\n"
                "<!-- prawduct: chunks=00 | status=shipped -->\n"
                "<!-- prawduct: chunks=01 | status=shipped -->\n"
            ),
            build_plan=(
                "## Status\n"
                "- [ ] Chunk 00: A\n"
                "- [ ] Chunk 01: B\n"
                "- [ ] Chunk 02: C\n"
            ),
        )
        result = _run_regen(product)
        assert result.returncode == 0, result.stderr
        assert "warning" in result.stderr.lower()
        assert "2 prawduct tag lines" in result.stderr
        new_plan = (product / ".prawduct" / "artifacts" / "build-plan.md").read_text()
        # The union is the fix: BOTH lines' chunks flip (the second was
        # silently dropped by the historical first-line-only parse).
        assert "- [x] Chunk 00: A" in new_plan
        assert "- [x] Chunk 01: B" in new_plan
        assert "- [ ] Chunk 02: C" in new_plan


def _make_scoped_product_repo(
    tmp_path: Path, *, change_log: str, plan_status: str, scope: str = "feat"
) -> Path:
    """Product repo whose build plan declares a frontmatter scope (VWS-6R4T)."""
    product = tmp_path / "product"
    (product / ".prawduct" / "artifacts").mkdir(parents=True)
    (product / ".prawduct" / "project-state.yaml").write_text("views_enabled: true\n")
    (product / ".prawduct" / "change-log.md").write_text(change_log)
    (product / ".prawduct" / "artifacts" / f"build-plan-{scope}.md").write_text(
        f"---\nartifact: build-plan\nscope: {scope}\n---\n{plan_status}"
    )
    return product


class TestRegenViewsFailClosed:
    """VWS-6R4T: any tag validation error aborts the whole regen — exit 2,
    ERROR on stderr, NOTHING written (no silent partial flips)."""

    def test_roster_miss_errors_and_writes_nothing(self, tmp_path: Path):
        product = _make_scoped_product_repo(
            tmp_path,
            change_log=(
                "## 2026-07-02: good\n"
                "<!-- prawduct: chunks=01 | scope=feat | status=shipped |"
                " release=v1.0.0 -->\n"
                "\n"
                "## 2026-07-02: bad chunk id\n"
                "<!-- prawduct: chunks=07 | scope=feat | status=shipped -->\n"
            ),
            plan_status="## Status\n- [ ] Chunk 01: A\n- [ ] Chunk 02: B\n",
        )
        result = _run_regen(product)
        assert result.returncode == 2, result.stdout + result.stderr
        assert "chunks=07" in result.stderr
        assert "never flip" in result.stderr
        # Fail closed across ALL views: plan untouched, release-notes absent.
        plan = (
            product / ".prawduct" / "artifacts" / "build-plan-feat.md"
        ).read_text()
        assert "- [ ] Chunk 01: A" in plan
        assert not (product / ".prawduct" / "release-notes.md").exists()

    def test_tolerant_id_variant_is_not_an_error_and_flips(self, tmp_path: Path):
        # chunks=1 against a `Chunk 01:` roster: the exact case the tolerant
        # matcher exists for — validates clean AND flips.
        product = _make_scoped_product_repo(
            tmp_path,
            change_log=(
                "## 2026-07-02: unpadded\n"
                "<!-- prawduct: chunks=1 | scope=feat | status=shipped -->\n"
            ),
            plan_status="## Status\n- [ ] Chunk 01: A\n",
        )
        result = _run_regen(product)
        assert result.returncode == 0, result.stderr
        plan = (
            product / ".prawduct" / "artifacts" / "build-plan-feat.md"
        ).read_text()
        assert "- [x] Chunk 01: A" in plan

    def test_conflicting_tag_lines_error(self, tmp_path: Path):
        product = _make_scoped_product_repo(
            tmp_path,
            change_log=(
                "## 2026-07-02: conflicted\n"
                "<!-- prawduct: chunks=01 | scope=feat | status=shipped -->\n"
                "<!-- prawduct: status=merged -->\n"
            ),
            plan_status="## Status\n- [ ] Chunk 01: A\n",
        )
        result = _run_regen(product)
        assert result.returncode == 2
        assert "conflicting" in result.stderr.lower()
        plan = (
            product / ".prawduct" / "artifacts" / "build-plan-feat.md"
        ).read_text()
        assert "- [ ] Chunk 01: A" in plan

    def test_unreleased_scope_without_plan_errors(self, tmp_path: Path):
        # Promoted from WARNING (REL-4T8N warn-and-skip): a merged scope with
        # no plan file means its Status can never regenerate — fatal now.
        product = _make_scoped_product_repo(
            tmp_path,
            change_log=(
                "## 2026-07-02: merged into develop\n"
                "<!-- prawduct: chunks=01 | scope=ghost | status=merged -->\n"
            ),
            plan_status="## Status\n- [ ] Chunk 01: A\n",
        )
        result = _run_regen(product)
        assert result.returncode == 2
        assert "ghost" in result.stderr
        assert "no matching build-plan file" in result.stderr

    def test_shipped_scope_without_plan_still_exempt(self, tmp_path: Path):
        # Historical/retired plans stay exempt — a shipped scope with no file
        # is expected (predates scope: frontmatter or plan was retired).
        product = _make_scoped_product_repo(
            tmp_path,
            change_log=(
                "## 2026-07-02: historical\n"
                "<!-- prawduct: chunks=01 | scope=old | status=shipped |"
                " release=v0.9.0 -->\n"
            ),
            plan_status="## Status\n- [ ] Chunk 01: A\n",
        )
        result = _run_regen(product)
        assert result.returncode == 0, result.stderr

    def test_duplicate_scope_across_plans_errors(self, tmp_path: Path):
        product = _make_scoped_product_repo(
            tmp_path,
            change_log=(
                "## 2026-07-02: e\n"
                "<!-- prawduct: chunks=01 | scope=feat | status=merged -->\n"
            ),
            plan_status="## Status\n- [ ] Chunk 01: A\n",
        )
        (product / ".prawduct" / "artifacts" / "build-plan-second.md").write_text(
            "---\nartifact: build-plan\nscope: feat\n---\n## Status\n"
        )
        result = _run_regen(product)
        assert result.returncode == 2
        assert "duplicate scope" in result.stderr.lower()


class TestRegenViewsCheckFlag:
    """`regen-views --check`: validate + report, never write (VWS-6R4T)."""

    def test_check_clean_exits_zero_and_writes_nothing(self, tmp_path: Path):
        product = _make_scoped_product_repo(
            tmp_path,
            change_log=(
                "## 2026-07-02: pending flip\n"
                "<!-- prawduct: chunks=01 | scope=feat | status=shipped |"
                " release=v1.0.0 -->\n"
            ),
            plan_status="## Status\n- [ ] Chunk 01: A\n",
        )
        result = _run_regen(product, "--check")
        assert result.returncode == 0, result.stderr
        assert "check passed" in result.stdout
        # Pending writes are REPORTED (not errors) and NOT applied.
        assert "[check]" in result.stdout
        plan = (
            product / ".prawduct" / "artifacts" / "build-plan-feat.md"
        ).read_text()
        assert "- [ ] Chunk 01: A" in plan  # unflipped
        assert not (product / ".prawduct" / "release-notes.md").exists()

    def test_check_with_violation_exits_two_and_writes_nothing(
        self, tmp_path: Path
    ):
        product = _make_scoped_product_repo(
            tmp_path,
            change_log=(
                "## 2026-07-02: bad\n"
                "<!-- prawduct: chunks=09 | scope=feat | status=shipped -->\n"
            ),
            plan_status="## Status\n- [ ] Chunk 01: A\n",
        )
        result = _run_regen(product, "--check")
        assert result.returncode == 2
        assert "chunks=09" in result.stderr
        assert not (product / ".prawduct" / "release-notes.md").exists()


# =============================================================================
# Integration tests — prawduct-hook stamp-merged subcommand
# =============================================================================


def _make_git_product_repo(
    tmp_path: Path, *, branch: str, base_branch: str | None, change_log: str
) -> Path:
    """Minimal git-backed product repo for stamp-merged's branch guard."""
    repo = tmp_path / "repo"
    (repo / ".prawduct").mkdir(parents=True)
    state = f"base_branch: {base_branch}\n" if base_branch else "views_enabled: true\n"
    (repo / ".prawduct" / "project-state.yaml").write_text(state)
    (repo / ".prawduct" / "change-log.md").write_text(change_log)
    subprocess.run(
        ["git", "init", "-q", "-b", branch], cwd=repo, check=True, timeout=20
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.email=t@example.com",
            "-c",
            "user.name=t",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "init",
        ],
        cwd=repo,
        check=True,
        timeout=20,
    )
    return repo


def _run_stamp_merged(product_dir: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(product_dir)}
    return subprocess.run(
        ["python3", str(HOOK_PATH), "stamp-merged"],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(product_dir),
        timeout=20,
    )


class TestStampMergedCommand:
    _CHANGE_LOG = (
        "## 2026-06-04: new work\n"
        "<!-- prawduct: chunks=01 | scope=alpha -->\n"
    )

    def test_stamps_on_configured_integration_branch(self, tmp_path: Path):
        repo = _make_git_product_repo(
            tmp_path, branch="develop", base_branch="develop",
            change_log=self._CHANGE_LOG,
        )
        result = _run_stamp_merged(repo)
        assert result.returncode == 0, result.stderr
        assert "stamped status=merged: 2026-06-04: new work" in result.stdout
        assert (
            "status=merged"
            in (repo / ".prawduct" / "change-log.md").read_text()
        )
        # single-pr-bookkeeping: no flow runs this anymore — the command
        # still works (harmless, convergent) but says so.
        assert "deprecated" in result.stderr

    def test_refuses_on_feature_branch(self, tmp_path: Path):
        repo = _make_git_product_repo(
            tmp_path, branch="feature/x", base_branch="develop",
            change_log=self._CHANGE_LOG,
        )
        result = _run_stamp_merged(repo)
        assert result.returncode == 1
        assert "refusing" in result.stderr
        assert "feature/x" in result.stderr
        # Change-log untouched.
        assert (
            "status=merged"
            not in (repo / ".prawduct" / "change-log.md").read_text()
        )

    def test_defaults_to_main_when_knob_unset(self, tmp_path: Path):
        repo = _make_git_product_repo(
            tmp_path, branch="main", base_branch=None,
            change_log=self._CHANGE_LOG,
        )
        result = _run_stamp_merged(repo)
        assert result.returncode == 0, result.stderr
        assert "stamped status=merged" in result.stdout

    def test_strips_origin_prefix_from_configured_base(self, tmp_path: Path):
        """REL-7P3X: an `origin/develop` base_branch (project-state.yaml's own
        'preferred' remote-tracking form) normalizes to the local `develop`
        branch and stamps, instead of refusing permanently. The guard compares
        LOCAL branch names by design (deliberate divergence from resolve-base)."""
        repo = _make_git_product_repo(
            tmp_path, branch="develop", base_branch="origin/develop",
            change_log=self._CHANGE_LOG,
        )
        result = _run_stamp_merged(repo)
        assert result.returncode == 0, result.stderr
        assert "stamped status=merged" in result.stdout

    def test_nothing_to_stamp_is_a_clean_no_op(self, tmp_path: Path):
        repo = _make_git_product_repo(
            tmp_path, branch="develop", base_branch="develop",
            change_log=(
                "## A\n<!-- prawduct: chunks=01 | status=merged -->\n"
            ),
        )
        before = (repo / ".prawduct" / "change-log.md").read_text()
        result = _run_stamp_merged(repo)
        assert result.returncode == 0, result.stderr
        assert "nothing to stamp" in result.stdout
        assert (repo / ".prawduct" / "change-log.md").read_text() == before

    def test_refuses_outside_a_git_repo(self, tmp_path: Path):
        product = tmp_path / "plain"
        (product / ".prawduct").mkdir(parents=True)
        (product / ".prawduct" / "project-state.yaml").write_text(
            "base_branch: develop\n"
        )
        (product / ".prawduct" / "change-log.md").write_text(self._CHANGE_LOG)
        result = _run_stamp_merged(product)
        assert result.returncode == 1
        assert "refusing" in result.stderr
