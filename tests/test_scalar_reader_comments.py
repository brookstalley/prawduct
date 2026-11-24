"""The product-name, work-in-progress and plan-frontmatter readers take a value
through core's comment-then-quote pair (``strip_scalar_comment``, then
``unquote_scalar``), so an annotated line reads as its value.

Owners annotate these lines. One repo declared ``name: "acme"  # Owner ruling …``,
and the product-name reader's bare quote strip kept the comment, so every
ledger event the repo wrote carried the comment as the product's label. The
siblings below had the same bug, or its mirror: cutting at the first ``#``
truncated a legal ``fix/#123`` branch.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from lib import briefing, gitstate, plan_index
from lib.release_verification import _read_declaration


def _state(tmp_path: Path, text: str) -> Path:
    prawduct = tmp_path / ".prawduct"
    prawduct.mkdir()
    (prawduct / "project-state.yaml").write_text(text, encoding="utf-8")
    return prawduct


@pytest.mark.parametrize(
    "line, expected",
    [
        ('  name: "acme"          # Owner ruling 2026-11-17. Identifier stem x.acme.', "acme"),
        ("  name: Acme Widgets  # working name", "Acme Widgets"),
        ('  name: "Fix #12 Co"', "Fix #12 Co"),
        ("  name: null  # not yet chosen", None),
        ("  name: ~  # not yet chosen", None),
        ("  name: Null", None),
    ],
)
def test_the_declared_product_name_drops_an_inline_comment(tmp_path, line, expected):
    prawduct = _state(tmp_path, f"product_identity:\n{line}\n")
    assert gitstate.declared_product_name(prawduct) == expected


def test_work_in_progress_fields_drop_an_inline_comment(tmp_path):
    prawduct = _state(
        tmp_path,
        "work_in_progress:\n"
        "  feature/x:\n"
        '    description: "the thing"  # see the plan\n'
        "    size: medium  # owner's call\n",
    )
    assert briefing._parse_wip(prawduct, branch="feature/x") == {
        "description": "the thing", "size": "medium",
    }
    assert briefing._parse_all_wip_branches(prawduct) == {
        "feature/x": {"description": "the thing", "size": "medium"},
    }


def test_work_in_progress_comment_lines_are_neither_keys_nor_fields(tmp_path):
    """A comment on a branch-key line, or a comment-only line among the fields,
    is not content: the branch still matches and no `# note` field appears."""
    prawduct = _state(
        tmp_path,
        "work_in_progress:\n"
        "  feature/x:  # mine\n"
        "    # todo: split chunk\n"
        "    size: medium\n",
    )
    assert briefing._parse_wip(prawduct, branch="feature/x") == {"size": "medium"}
    assert briefing._parse_all_wip_branches(prawduct) == {"feature/x": {"size": "medium"}}


def test_flat_work_in_progress_fields_drop_an_inline_comment(tmp_path):
    prawduct = _state(
        tmp_path,
        "work_in_progress:\n"
        '  description: "legacy"  # flat form\n',
    )
    assert briefing._parse_wip(prawduct, branch="any") == {"description": "legacy"}
    assert briefing._parse_all_wip_branches(prawduct) == {"_flat": {"description": "legacy"}}


def test_a_release_version_file_entry_drops_an_inline_comment():
    """Here the block reader (``core.read_yaml_block``) strips the comment before
    entry assembly sees the line; this pins that layer, not the scalar pair."""
    files = _read_declaration(
        "release_version_files:\n"
        '  - path: "VERSION"  # the one the tag reads\n'
        "    format: bare  # whole file\n"
    )
    assert [(f.path, f.fmt) for f in files] == [("VERSION", "bare")]


@pytest.mark.parametrize(
    "line, expected",
    [
        ("branch: fix/#123", "fix/#123"),
        ("branch: feature/x  # the claim", "feature/x"),
        ('branch: "feature/y"  # quoted, then a comment', "feature/y"),
    ],
)
def test_a_plan_branch_claim_reads_by_the_yaml_comment_rule(line, expected):
    assert plan_index.parse_build_plan_frontmatter_branch(f"---\n{line}\n---\n# Plan\n") == expected
