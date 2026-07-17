"""Tests for lib/backlog/encode.py — block parse/serialize, soft enums, decode.

Covers the Chunk-01 encoding subset: ENC-1 (soft-enum tolerance), ENC-3
(exactly-one block, last-block-wins), ENC-4 (tolerant parse, unknown keys
preserved verbatim), plus the decode precedence the two-axis keystone builds on.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib.backlog import encode  # noqa: E402


class TestSoftEnumTolerance:
    """ENC-1 — unknown soft value flagged, never rejected; unknown status rejected."""

    def test_unknown_stage_is_warned_not_rejected(self):
        result = encode.check_enum("stage", "brainstorming")
        assert result.ok
        assert result.warning and "brainstorming" in result.warning

    def test_known_stage_is_clean(self):
        result = encode.check_enum("stage", "ready")
        assert result.ok
        assert result.warning is None

    def test_open_facet_accepts_any_value_no_warning(self):
        # `kind` is an open soft enum (scriob's 158 items) — no vocabulary to miss.
        result = encode.check_enum("kind", "anything-goes")
        assert result.ok
        assert result.warning is None

    def test_unknown_status_is_hard_reject(self):
        result = encode.check_enum("status", "frozen")
        assert not result.ok
        assert result.message and "frozen" in result.message

    def test_known_status_ok(self):
        assert encode.check_enum("status", "in-progress").ok


class TestBlockParse:
    """ENC-3 / ENC-4 — last-block-wins, tolerant parse, verbatim round-trip."""

    def test_no_block_is_empty_defaults(self):
        block = encode.parse_block("just a body, no block")
        assert block.fields == {}
        assert block.warnings == []
        assert block.version() == 1
        assert block.id_aliases() == []

    def test_two_blocks_last_wins_and_flags_earlier(self):
        body = (
            "intro\n"
            "```prawduct\n"
            "v: 1\n"
            "id_aliases: [OLD-0001]\n"
            "```\n"
            "middle\n"
            "```prawduct\n"
            "v: 1\n"
            "id_aliases: [NEW-0002]\n"
            "```\n"
        )
        block = encode.parse_block(body)
        assert block.id_aliases() == ["NEW-0002"]
        assert any("prawduct blocks" in w for w in block.warnings)

    def test_unknown_key_preserved_verbatim_on_round_trip(self):
        body = (
            "```prawduct\n"
            "v: 1\n"
            "future_key: some-unrecognized-value\n"
            "id_aliases: [BKL-7M4Q]\n"
            "```\n"
        )
        block = encode.parse_block(body)
        assert block.get("future_key") == "some-unrecognized-value"
        reserialized = block.reserialize()
        assert "future_key: some-unrecognized-value" in reserialized
        # A second parse of the re-serialized block preserves the unknown key.
        again = encode.parse_block(reserialized)
        assert again.get("future_key") == "some-unrecognized-value"

    def test_missing_key_takes_default(self):
        block = encode.parse_block("```prawduct\nid_aliases: [A-1]\n```\n")
        assert block.version() == 1  # 'v' absent → default

    def test_malformed_line_skipped_with_warning_not_error(self):
        block = encode.parse_block(
            "```prawduct\nv: 1\nthis line has no separator\n```\n"
        )
        assert block.version() == 1
        assert any("malformed block line" in w for w in block.warnings)

    def test_value_containing_hash_is_not_truncated(self):
        # `superseded_by` values contain '#'; naive comment-stripping would corrupt them.
        block = encode.parse_block(
            "```prawduct\nv: 1\nsuperseded_by: octo/repo#123\n```\n"
        )
        assert block.get("superseded_by") == "octo/repo#123"


class TestBlockSerialize:
    def test_version_emitted_first(self):
        out = encode.serialize_block({"id_aliases": "[BKL-0001]", "v": "1"})
        lines = out.splitlines()
        assert lines[0] == "```prawduct"
        assert lines[1] == "v: 1"
        assert "id_aliases: [BKL-0001]" in lines
        assert lines[-1] == "```"


class TestDecodeStatus:
    """Decode precedence (Data Model §4) — the basis the self-heal keystone extends."""

    def test_open_no_status_label_is_open(self):
        status, warns = encode.decode_status({"state": "open"}, [])
        assert status == "open"
        assert warns == []

    def test_open_in_progress_label(self):
        status, _ = encode.decode_status({"state": "open"}, ["status:in-progress"])
        assert status == "in-progress"

    def test_open_multiple_status_labels_highest_wins_and_warns(self):
        status, warns = encode.decode_status(
            {"state": "open"}, ["status:submitted", "status:in-progress"]
        )
        assert status == "in-progress"
        assert any("multiple status labels" in w for w in warns)

    def test_closed_completed_is_shipped(self):
        status, _ = encode.decode_status(
            {"state": "closed", "state_reason": "completed"}, []
        )
        assert status == "shipped"

    def test_closed_not_planned_is_dropped(self):
        status, _ = encode.decode_status(
            {"state": "closed", "state_reason": "not_planned"}, []
        )
        assert status == "dropped"

    def test_closed_with_stray_status_label_warns(self):
        status, warns = encode.decode_status(
            {"state": "closed", "state_reason": "completed"}, ["status:in-progress"]
        )
        assert status == "shipped"
        assert any("status: label" in w for w in warns)

    def test_closed_unknown_reason_fails_open(self):
        status, warns = encode.decode_status(
            {"state": "closed", "state_reason": "some_future_reason"}, []
        )
        assert status == "dropped"
        assert any("state_reason" in w for w in warns)


class TestDecodeItem:
    def test_decodes_axes_independently(self):
        issue = {
            "number": 7,
            "node_id": "I_abc",
            "title": "Do the thing",
            "body": "body\n```prawduct\nv: 1\nid_aliases: [BKL-0007]\n```\n",
            "state": "open",
            "labels": [{"name": "stage:ready"}, {"name": "area:backlog"}],
            "html_url": "https://github.com/octo/repo/issues/7",
        }
        item, warns = encode.decode_item(issue, canonical_id="octo/repo#7")
        assert item["id"] == "octo/repo#7"
        assert item["status"] == "open"  # no status label
        assert item["stage"] == "ready"  # independent axis
        assert item["area"] == "backlog"
        assert item["id_aliases"] == ["BKL-0007"]
        assert item["number"] == 7
