"""Tests for the structured backlog parser (``lib/backlog.py``, Chunk 01).

Pins the parse contract the later chunks build on, and the briefing-count
parity that makes Chunk 01 a pure substrate refactor (no behavior change):
``pending_items()`` must reproduce the old line-scan count exactly.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib.backlog.legacy import (
    GITHUB_TITLE_HARD_CAP,
    BacklogItem,
    parse_backlog,
    parse_metadata_bar,
)


# A representative structured item with the full v0.3 metadata bar.
STRUCTURED = (
    "# Backlog — demo\n"
    "\n"
    "## Open\n"
    "\n"
    "- **[CRT-6F2N]** Fix the thing\n"
    "  `effort: M · impact: L · area: critic · source: builder · added: 2026-06-08 · "
    "status: open · stage: ready · accepted-by: @brooks (2026-06-08) · "
    "refs: requirements-x.md#5, arch-y.md · related: CRT-3X9D, STH-9V4K`\n"
    "\n"
    "  Free-form body paragraph one.\n"
    "\n"
    "  Body paragraph two.\n"
)


class TestMetadataBar:
    def test_dot_separated_key_value(self):
        meta = parse_metadata_bar("effort: M · impact: L · area: critic · status: open")
        assert meta == {
            "effort": "M",
            "impact": "L",
            "area": "critic",
            "status": "open",
        }

    def test_value_may_contain_spaces_and_parens(self):
        meta = parse_metadata_bar("accepted-by: @brooks (2026-06-08) · status: open")
        assert meta["accepted-by"] == "@brooks (2026-06-08)"
        assert meta["status"] == "open"

    def test_empty_bar(self):
        assert parse_metadata_bar("") == {}

    def test_segment_without_colon_skipped(self):
        assert parse_metadata_bar("garbage · status: open") == {"status": "open"}


class TestItemParse:
    def test_structured_item_full_fields(self):
        bl = parse_backlog(STRUCTURED)
        assert len(bl.items) == 1
        item = bl.items[0]
        assert item.item_id == "CRT-6F2N"
        assert item.title == "[CRT-6F2N] Fix the thing"
        assert item.section == "Open"
        assert item.status == "open"
        assert item.area == "critic"
        assert item.stage == "ready"
        assert item.is_legacy is False
        assert item.struck is False

    def test_v03_fields(self):
        item = parse_backlog(STRUCTURED).items[0]
        assert item.accepted_by == "@brooks (2026-06-08)"
        assert item.is_claimed is True
        assert item.refs == ["requirements-x.md#5", "arch-y.md"]
        assert item.related == ["CRT-3X9D", "STH-9V4K"]

    def test_revisit_field(self):
        # `revisit:` (norm-lifecycle exceptions/stopgaps, docs/norms.md): the
        # typed accessor surfaces both the dated and event-trigger forms; absent
        # -> None. probe_revisit_due consumes the accessor, not raw metadata.
        bl = parse_backlog(
            "## Open\n"
            "- [GOV-1A2B] Dated exception\n"
            "  `effort: S · impact: S · area: governance · source: user · "
            "added: 2026-07-01 · status: open · revisit: 2026-08-01`\n"
            "- [GOV-3C4D] Event-bound stopgap\n"
            "  `effort: S · impact: S · area: governance · source: user · "
            "added: 2026-07-01 · status: open · revisit: when Y reaches subsystem Q`\n"
            "- [GOV-5E6F] No clock\n"
            "  `effort: S · impact: S · area: governance · source: user · "
            "added: 2026-07-01 · status: open`\n"
        )
        assert bl.items[0].revisit == "2026-08-01"
        assert bl.items[1].revisit == "when Y reaches subsystem Q"
        assert bl.items[2].revisit is None

    def test_body_excludes_metadata_bar(self):
        item = parse_backlog(STRUCTURED).items[0]
        assert "Free-form body paragraph one." in item.body
        assert "Body paragraph two." in item.body
        assert "effort:" not in item.body  # the bar is metadata, not body

    def test_legacy_item_has_no_metadata(self):
        bl = parse_backlog("## Open\n- A legacy one-liner with no metadata bar\n")
        item = bl.items[0]
        assert item.is_legacy is True
        assert item.area == "untagged"
        assert item.status is None
        assert item.stage is None
        assert item.is_claimed is False

    def test_unclaimed_and_unstaged_defaults(self):
        bl = parse_backlog(
            "## Open\n- **[A-1]** x\n  `area: misc · status: open`\n"
        )
        item = bl.items[0]
        assert item.accepted_by is None
        assert item.is_claimed is False
        assert item.stage is None
        assert item.refs == []

    def test_lenient_legacy_id(self):
        bl = parse_backlog("## Open\n- [A-1] one\n")
        assert bl.items[0].item_id == "A-1"

    @pytest.mark.parametrize(
        "marker", ["MIG-M4-REMOVE", "AUD-TIMBRE-CALIB", "ENG-9V2K-F", "A-1-2-3"]
    )
    def test_multi_segment_id_is_absorbed(self, marker):
        """An id carrying two or more hyphens is an ordinary hand-minted id, not a
        malformed one — roughly a fifth of real backlogs have one. Parsing it as
        unidentified is what strands it: no ``id:`` alias, so nothing keys it back
        to the source and the import-completeness gate blocks the cutover."""
        bl = parse_backlog(f"## Open\n- **[{marker}]** one\n")
        assert bl.items[0].item_id == marker

    @pytest.mark.parametrize(
        "marker", ["2026-07-28", "-1234", "TODO", "FOO_BAR", "FOO.BAR", "FOO-", "FOO--BAR"]
    )
    def test_non_id_bracket_stays_unidentified(self, marker):
        """The widening to multi-segment ids does not reach these: a bracketed date
        is the case the leading-letter rule exists to reject, and the rest are not
        ID-shaped at all. They stay unidentified, so the gate keeps its teeth."""
        bl = parse_backlog(f"## Open\n- **[{marker}]** one\n")
        assert bl.items[0].item_id is None


class TestSectionsAndStruck:
    BACKLOG = (
        "# Backlog\n"
        "## Open\n"
        "- **[O-1]** open one\n"
        "- ~~**[O-2]** struck~~\n"
        "## Promoted\n"
        "- **[P-1]** promoted one\n"
        "## Archive\n"
        "- **[A-1]** shipped one\n"
        "  `status: shipped`\n"
    )

    def test_section_assignment(self):
        bl = parse_backlog(self.BACKLOG)
        assert [i.item_id for i in bl.open_items()] == ["O-1", "O-2"]
        assert [i.item_id for i in bl.promoted_items()] == ["P-1"]
        assert [i.item_id for i in bl.archived_items()] == ["A-1"]

    def test_struck_detected(self):
        bl = parse_backlog(self.BACKLOG)
        struck = [i for i in bl.items if i.struck]
        assert [i.item_id for i in struck] == ["O-2"]

    def test_items_by_area(self):
        bl = parse_backlog(
            "## Open\n"
            "- **[C-1]** a\n  `area: critic · status: open`\n"
            "- **[C-2]** b\n  `area: critic · status: open`\n"
            "- **[S-1]** c\n  `area: sync · status: open`\n"
        )
        grouped = bl.items_by_area()
        assert {k: len(v) for k, v in grouped.items()} == {"critic": 2, "sync": 1}


class TestPendingItemsParity:
    """`pending_items()` must reproduce the briefing's pre-parser count exactly:
    top-level non-struck items in any NON-resolved/archive section (so Open AND
    Promoted count). These mirror the two pinned briefing tests."""

    def test_open_items_counted(self):
        bl = parse_backlog("# Backlog\n## Open\n- [A-1] one\n- [A-2] two\n")
        assert len(bl.pending_items()) == 2

    def test_excludes_resolved_section_and_strikethrough(self):
        bl = parse_backlog(
            "# Backlog\n## Open\n- [A-1] keep\n- ~~[A-2] struck~~\n"
            "## Resolved\n- [A-3] done\n"
        )
        assert len(bl.pending_items()) == 1
        assert bl.pending_items()[0].title == "[A-1] keep"

    def test_promoted_counts_as_pending(self):
        bl = parse_backlog(
            "## Open\n- **[O-1]** o\n## Promoted\n- **[P-1]** p\n"
            "## Archive\n- **[A-1]** a\n"
        )
        # Open + Promoted are pending; Archive is not.
        ids = {i.item_id for i in bl.pending_items()}
        assert ids == {"O-1", "P-1"}

    def test_done_completed_archive_words_excluded(self):
        for heading in ("Done", "Completed", "Archive", "Resolved"):
            bl = parse_backlog(f"## Open\n- **[O-1]** o\n## {heading}\n- **[X-1]** x\n")
            assert {i.item_id for i in bl.pending_items()} == {"O-1"}, heading


class TestRobustness:
    def test_code_block_items_ignored(self):
        bl = parse_backlog(
            "## Open\n```\n- **[FAKE-1]** inside a fence\n```\n- **[REAL-1]** real\n"
        )
        assert [i.item_id for i in bl.items] == ["REAL-1"]

    def test_html_comment_items_ignored(self):
        bl = parse_backlog(
            "## Open\n<!--\n- **[FAKE-1]** inside a comment\n-->\n- **[REAL-1]** real\n"
        )
        assert [i.item_id for i in bl.items] == ["REAL-1"]

    def test_indented_bullets_are_body_not_items(self):
        bl = parse_backlog(
            "## Open\n- **[O-1]** parent\n  `status: open`\n\n  - a sub-bullet in the body\n"
        )
        assert len(bl.items) == 1
        assert "a sub-bullet in the body" in bl.items[0].body

    def test_empty_file(self):
        assert parse_backlog("").items == []

    def test_body_may_contain_fenced_code_block(self):
        # The item format permits code blocks in bodies (requirements §4.1). A
        # fence — even one containing heading-/bullet-looking lines — must not
        # truncate the item or leak into the next.
        bl = parse_backlog(
            "## Open\n"
            "- **[O-1]** has a code body\n"
            "  `status: open`\n"
            "\n"
            "  Example:\n"
            "  ```\n"
            "  ## not a heading\n"
            "  - not an item\n"
            "  ```\n"
            "  trailing prose\n"
            "- **[O-2]** next item\n"
        )
        assert [i.item_id for i in bl.items] == ["O-1", "O-2"]
        body = bl.items[0].body
        assert "## not a heading" in body
        assert "- not an item" in body
        assert "trailing prose" in body


class TestRealBacklogSmoke:
    """The parser must handle this repo's own (mutable) backlog without loss.
    Assertions are structural (resilient to content churn), not count-based."""

    def test_parses_repo_backlog(self):
        repo_backlog = Path(__file__).resolve().parents[1] / ".prawduct" / "backlog.md"
        if not repo_backlog.is_file():
            return  # not in a prawduct repo checkout; skip silently
        bl = parse_backlog(repo_backlog.read_text(encoding="utf-8"))
        assert len(bl.items) > 0
        # Every parsed item carries the section it was found under.
        assert all(isinstance(i, BacklogItem) and i.section for i in bl.items)
        # The known structured items resolve their IDs.
        ids = {i.item_id for i in bl.items}
        assert "REL-2N8K" in ids


class TestTitleBoundary:
    """The title boundary rule, and the two ways it can lose data.

    `_parse_title_line` used to return the whole bullet line as the title. That is
    correct for products writing body prose on the FOLLOWING lines and catastrophic
    for one writing provenance, title, areas and body on a single line: parsed
    titles reached 2319 chars, GitHub rejects anything over 256, and the importer
    treated that rejection as fatal for a whole 396-item migration.

    These tests exist because the first cut of the fix shipped two silent losses of
    its own — the marker span discarded, and a marker-led bullet cut to an empty
    title that `migrate._records_from_backlog` then skips. Both are pinned below;
    neither was caught by the suite, because none of this had a test at all.
    """

    def _item(self, bullet: str):
        return parse_backlog(f"## Open\n\n{bullet}\n").items[0]

    def test_cuts_the_title_at_an_inline_areas_marker(self):
        item = self._item(
            "- **[CI-L0SB]** (orig #980, pr-reviewer 2026-05-10) Move token-generation "
            "into the build script. [areas: ci, deploy] The deploy break is fixed but "
            "the mismatch is latent elsewhere."
        )
        assert item.title == "[CI-L0SB] Move token-generation into the build script."
        assert item.item_id == "CI-L0SB"

    def test_the_marker_span_itself_reaches_the_body(self):
        """The span is authored text, so it moves — it does not evaporate.

        Slicing around the match (`[:start]` + `[end:]`) drops it into neither
        field. Nothing downstream recovers it: `migrate._block_for` preserves only
        the backtick metadata bar.
        """
        item = self._item("- **[X-1]** Short title [areas: ci, deploy] trailing prose")
        assert "[areas: ci, deploy]" in item.body
        assert "trailing prose" in item.body

    def test_a_marker_led_bullet_keeps_a_title_rather_than_vanishing(self):
        """A cut that empties the title would delete the item from a migration.

        `migrate._records_from_backlog` skips on `not item.title`, with no collision
        record and no diagnostic — a silent drop. A long title is a lint finding; a
        dropped item is data loss, so the line stays whole.
        """
        item = self._item("- [areas: ci] body prose with no authored title")
        assert item.title, "marker-led bullet parsed to an empty title — it would be silently dropped"

    def test_a_leading_provenance_parenthetical_is_not_part_of_the_title(self):
        item = self._item("- **[X-2]** (orig #12, critic 2026-05-01) The real title")
        assert item.title == "[X-2] The real title"

    def test_a_parenthetical_that_does_not_lead_is_ordinary_title_prose(self):
        item = self._item("- **[X-3]** Fix the thing (orig behaviour) properly")
        assert "(orig behaviour)" in item.title

    def test_no_title_can_exceed_githubs_hard_cap(self):
        """256 is GitHub's 422 boundary, not the authoring norm (that is 72, and it
        lives in `issuefmt.TITLE_MAX`). Exceeding it fails the write."""
        item = self._item("- **[X-4]** " + ("word " * 200))
        assert len(item.title) <= GITHUB_TITLE_HARD_CAP

    def test_the_cap_budgets_for_the_id_prefix(self):
        """The prefix is re-added after the split and counts against the same 256.

        Budgeting only the remainder is an off-by-a-prefix that leaves the exact
        items this fix exists for still over the cap — which is what the first cut
        of this fix did.
        """
        item = self._item("- **[LONGISH-PREFIX-9999]** " + ("word " * 200))
        assert len(item.title) <= GITHUB_TITLE_HARD_CAP

    def test_capped_overflow_is_moved_to_the_body_not_dropped(self):
        tail = "DISTINCTIVETAILTOKEN"
        item = self._item("- **[X-5]** " + ("word " * 200) + tail)
        assert tail in item.body

    def test_an_ordinary_title_is_untouched(self):
        """The rule is a MARKER rule, not a length rule. Products author
        legitimately long titles with no marker; truncating those to repair a
        different product's run-on lines would damage the working shape."""
        item = self._item("- **[X-6]** A perfectly ordinary one-line title")
        assert item.title == "[X-6] A perfectly ordinary one-line title"
        assert item.body == ""

    def test_the_pfx_marker_stays_in_the_title(self):
        """Contract, not incidental: it is the display string consumers expect, and
        `migrate.py` strips it downstream where the id lives in the alias."""
        item = self._item("- **[CRT-6F2N]** Fix the thing [areas: critic] and prose")
        assert item.title.startswith("[CRT-6F2N] ")

    def test_a_pfx_less_item_still_parses_with_a_title(self):
        """`ImportRecord.key_label` falls back to `sha256(title + body)` for an item
        with no PFX, so a title change moves its idempotency key and a re-import
        duplicates. Zero such items exist in either measured corpus, but the shape
        is legal — the discovery artifact requires this guarded rather than left to
        luck."""
        item = self._item("- A legacy item with no id at all [areas: misc] and prose")
        assert item.item_id is None
        assert item.title
