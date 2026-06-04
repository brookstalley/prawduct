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

_REPO_ROOT = Path(__file__).resolve().parent.parent
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

    def test_multiple_entries_same_release_merged(self):
        change_log = (
            "## 2026-05-18: first part (v1.3.17)\n"
            "<!-- prawduct: chunks=00,01 | release=v1.3.17 | status=shipped -->\n"
            "## 2026-05-18: second part (v1.3.17)\n"
            "<!-- prawduct: chunks=02,03 | release=v1.3.17 | status=shipped -->\n"
        )
        out = views.build_release_notes_view(change_log)
        assert out is not None
        # One section per release version.
        assert out.count("## v1.3.17") == 1
        # Chunks from both entries unioned + sorted.
        assert "**Chunks shipped:** 00, 01, 02, 03" in out

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


class TestRegenViewsStatusTypoWarning:
    """VWS-3K7P: a change-log `status=` typo is surfaced on stderr as a
    NON-fatal warning — regen still succeeds (exit 0) and still flips the
    valid entries; only the typoed entry fails to flip (as it always did)."""

    def test_typo_warns_on_stderr_non_fatal(self, tmp_path: Path):
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
        # Non-fatal: command still succeeds.
        assert result.returncode == 0, result.stderr
        # Warning surfaced on stderr, naming the bad value.
        assert "shippd" in result.stderr
        assert "warning" in result.stderr.lower()
        new_plan = (product / ".prawduct" / "artifacts" / "build-plan.md").read_text()
        # Valid entry flipped; typoed entry did NOT flip (flip rule unchanged).
        assert "- [x] Chunk 00: A" in new_plan
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
