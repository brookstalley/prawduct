"""Tests for the structured backlog parser (``lib/backlog.py``, Chunk 01).

Pins the parse contract the later chunks build on, and the briefing-count
parity that makes Chunk 01 a pure substrate refactor (no behavior change):
``pending_items()`` must reproduce the old line-scan count exactly.
"""

from __future__ import annotations

from pathlib import Path

from lib.backlog.legacy import BacklogItem, parse_backlog, parse_metadata_bar


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
