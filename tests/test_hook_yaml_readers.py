"""The one block-sequence reader, and the hook's inline mirror of it (#590).

Four hand-rolled column-0 minimal-YAML readers had drifted, and two returned
**silently wrong** answers on inputs the others handled:

* a column-0 comment inside a block truncated the list in ``risk`` and
  ``release_verification`` (the declaration continues below it, and everything
  after was dropped while the record claimed a full read);
* flow style (``key: [a, b]``) read as ``[]`` — *declared empty* — in the same
  two, and ``risk_surfaces:`` honours declared-empty **exclusively**, so a real
  declaration resolved to zero risk surfaces and a governance gate relaxed on a
  syntax slip.

The parsing is ``core.read_yaml_block`` / ``core.read_block_sequence`` now. What
legitimately differs per key is the POLICY on the third outcome, and that is
asserted here too — because "one reader, or N with a written contract" is only
half met if the contract is written and nothing checks it.

The hook keeps its own inline copy (import-light hot path). That copy was the
one that was RIGHT, and it sat UNPINNED beside a pinned scalar sibling, which is
how the drift went unseen; :class:`TestHookYamlListReaderParity` is the pin the
waiver comment now names.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path

import pytest

from lib.core import (
    YAML_ABSENT,
    YAML_DECLARED,
    YAML_UNPARSEABLE,
    read_block_sequence,
    read_yaml_block,
    yaml_top_level_key_present,
)

_HOOK_PATH = Path(__file__).resolve().parents[1] / "plugin" / "bin" / "prawduct-hook"


# Loaded via SourceFileLoader — `prawduct-hook` is an extensionless shebang
# script, the same idiom `test_build_plan_resolution.py` uses for its mirror.
_hook_loader = importlib.machinery.SourceFileLoader("prawduct_hook_yaml", str(_HOOK_PATH))
_hook_spec = importlib.util.spec_from_loader("prawduct_hook_yaml", _hook_loader)
_hook = importlib.util.module_from_spec(_hook_spec)
_hook_loader.exec_module(_hook)


#: The inputs the four readers disagreed on, plus the ones they agreed on, as
#: ``(label, yaml)``. Kept as one table so a new reader can be held to the whole
#: set rather than to whichever cases its author happened to think of.
CASES = {
    "absent": "base_branch: develop\n",
    "block": "risk_surfaces:\n  - a\n  - b\n",
    "block_with_column_zero_comment": "risk_surfaces:\n  - a\n# a column-0 comment\n  - b\n",
    "block_with_indented_comment": "risk_surfaces:\n  - a\n  # indented\n  - b\n",
    "block_with_blank_line": "risk_surfaces:\n  - a\n\n  - b\n",
    "block_quoted": "risk_surfaces:\n  - \"a\"\n  - 'b'\n",
    "block_trailing_comment": "risk_surfaces:  # hot spots\n  - a  # why\n  - b\n",
    "terminated_by_next_key": "risk_surfaces:\n  - a\nbase_branch: develop\n",
    "commented_out_key": "# risk_surfaces:\n#   - a\n",
    "inline_empty": "risk_surfaces: []\n",
    "flow_style": "risk_surfaces: [a, b]\n",
    "scalar_under_list_key": "risk_surfaces: a\n",
    "bare_dash": "risk_surfaces:\n  -\n",
    "empty_item": "risk_surfaces:\n  - \n",
    "nested_mapping": "risk_surfaces:\n  path: a\n",
    "empty_block": "risk_surfaces:\nbase_branch: develop\n",
}

#: ``(status, items)`` the canonical reader must produce for each case above.
EXPECTED = {
    "absent": (YAML_ABSENT, ()),
    "block": (YAML_DECLARED, ("a", "b")),
    "block_with_column_zero_comment": (YAML_DECLARED, ("a", "b")),
    "block_with_indented_comment": (YAML_DECLARED, ("a", "b")),
    "block_with_blank_line": (YAML_DECLARED, ("a", "b")),
    "block_quoted": (YAML_DECLARED, ("a", "b")),
    "block_trailing_comment": (YAML_DECLARED, ("a", "b")),
    "terminated_by_next_key": (YAML_DECLARED, ("a",)),
    "commented_out_key": (YAML_ABSENT, ()),
    "inline_empty": (YAML_DECLARED, ()),
    "flow_style": (YAML_UNPARSEABLE, ()),
    "scalar_under_list_key": (YAML_UNPARSEABLE, ()),
    "bare_dash": (YAML_UNPARSEABLE, ()),
    "empty_item": (YAML_UNPARSEABLE, ()),
    "nested_mapping": (YAML_UNPARSEABLE, ()),
    "empty_block": (YAML_DECLARED, ()),
}


class TestTheCanonicalReader:
    @pytest.mark.parametrize("label", sorted(CASES))
    def test_every_disputed_input_has_one_answer(self, label):
        assert read_block_sequence(CASES[label], "risk_surfaces") == EXPECTED[label], label

    def test_a_column_zero_comment_does_not_truncate_the_block(self):
        # The exact repro from #590. Two readers returned one entry here, so a
        # declaration silently lost everything below the comment.
        status, items = read_block_sequence(
            CASES["block_with_column_zero_comment"], "risk_surfaces"
        )
        assert (status, items) == (YAML_DECLARED, ("a", "b"))

    def test_flow_style_is_unparseable_not_empty(self):
        # The other repro. "Declared empty" is honoured EXCLUSIVELY by
        # `risk_surfaces:`, so reading a filled-in flow list as empty resolved a
        # real declaration to zero surfaces.
        assert read_block_sequence(CASES["flow_style"], "risk_surfaces")[0] == YAML_UNPARSEABLE
        # ...and the deliberate opt-out is still readable as itself.
        assert read_block_sequence(CASES["inline_empty"], "risk_surfaces") == (YAML_DECLARED, ())

    def test_an_anomaly_is_never_a_partial_list(self):
        # A partial list is the dangerous answer: it drops part of what an
        # operator declared while every downstream record claims otherwise.
        text = "risk_surfaces:\n  - a\n  nested: mapping\n  - b\n"
        assert read_block_sequence(text, "risk_surfaces") == (YAML_UNPARSEABLE, ())

    def test_the_block_form_keeps_mapping_lines_for_its_caller(self):
        # `release_version_files:` items are mappings, not plain strings, so the
        # shared layer stops at "these are the block's lines".
        text = "release_version_files:\n  - path: VERSION\n    format: bare\n"
        assert read_yaml_block(text, "release_version_files") == (
            YAML_DECLARED, ("- path: VERSION", "format: bare"),
        )

    def test_presence_is_not_shape(self):
        assert yaml_top_level_key_present(CASES["flow_style"], "risk_surfaces")
        assert not yaml_top_level_key_present(CASES["absent"], "risk_surfaces")
        assert not yaml_top_level_key_present(CASES["commented_out_key"], "risk_surfaces")


class TestHookYamlListReaderParity:
    """The hook's inline ``_read_str_list_yaml_key`` against the lib reader.

    Same discipline as ``TestProductHookMirrorParity`` does for the scalar
    sibling. The hook narrows the three-way status to ``list | None`` because its
    call site converts None-but-present into a loud refusal — so the mapping
    asserted here is ``DECLARED and non-empty → the items, everything else →
    None``, not raw equality.
    """

    @staticmethod
    def _expected_hook_answer(label):
        status, items = EXPECTED[label]
        return list(items) if status == YAML_DECLARED and items else None

    @pytest.mark.parametrize("label", sorted(CASES))
    def test_the_mirror_agrees_with_lib_on_every_disputed_input(self, label, tmp_path):
        path = tmp_path / "project-state.yaml"
        path.write_text(CASES[label], encoding="utf-8")
        assert _hook._read_str_list_yaml_key(path, "risk_surfaces") == (
            self._expected_hook_answer(label)
        ), label

    @pytest.mark.parametrize("label", sorted(CASES))
    def test_the_presence_probe_agrees_with_lib(self, label, tmp_path):
        path = tmp_path / "project-state.yaml"
        path.write_text(CASES[label], encoding="utf-8")
        assert _hook._yaml_top_level_key_present(path, "risk_surfaces") == (
            yaml_top_level_key_present(CASES[label], "risk_surfaces")
        ), label

    def test_the_mirror_is_declared_as_one(self):
        # The waiver comment is the only thing that stops the duplication check
        # from flagging this, and it names THIS class. An unpinned mirror beside a
        # pinned one is exactly how #590 happened.
        source = _HOOK_PATH.read_text(encoding="utf-8")
        marker = source.index("def _read_str_list_yaml_key")
        preceding = source[:marker].rsplit("\n\n", 1)[-1]
        assert "prawduct:allow prawduct/duplication" in preceding
        assert "TestHookYamlListReaderParity" in preceding


class TestThePerKeyPolicyOnUnparseable:
    """Parsing is shared; what an unparseable declaration COSTS is per key, and
    the differences are deliberate. Asserted so the written contract has a
    checker."""

    def test_risk_surfaces_refuses_rather_than_guessing(self, tmp_path):
        from lib import risk

        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(CASES["flow_style"], encoding="utf-8")
        surfaces, source = risk.resolve_surfaces(prawduct)
        assert (surfaces, source) == ([], risk.SOURCE_UNPARSEABLE)
        # Neither of the two guesses is available to a caller: declared-empty
        # relaxes the gate to nothing, absent ignores what the operator wrote.
        assert source not in (risk.SOURCE_DECLARED, risk.SOURCE_DERIVED)

    def test_the_pathwise_entry_point_escalates_since_it_cannot_refuse(self, tmp_path):
        from lib import risk

        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(CASES["flow_style"], encoding="utf-8")
        touched, why = risk.paths_touch_risk_surface(prawduct, ["some/file.py"])
        assert touched is True
        assert "cannot parse" in why

    def test_declared_empty_is_still_the_opt_out_it_was(self, tmp_path):
        from lib import risk

        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(CASES["inline_empty"], encoding="utf-8")
        assert risk.resolve_surfaces(prawduct) == ([], risk.SOURCE_DECLARED)

    def test_release_version_files_reports_the_shape_not_emptiness(self):
        from lib import release_verification as rv

        assert rv.declaration_status("release_version_files: [a, b]\n") == YAML_UNPARSEABLE
        assert rv.declaration_status("release_version_files: []\n") == YAML_DECLARED
        assert rv.declaration_status("base_branch: develop\n") == YAML_ABSENT

    def test_release_version_files_still_cannot_fail_a_release_on_a_shape(self):
        # The policy difference, stated: this key's unparseable outcome is a loud
        # UNVERIFIABLE rather than a refusal, because the fallback here is a GUESS
        # and a guess must never be able to FAIL a release.
        from lib import release_verification as rv

        assert rv._read_declaration("release_version_files: [a, b]\n") == []
        assert rv._read_declaration("base_branch: develop\n") is None
