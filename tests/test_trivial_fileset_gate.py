"""Tests for the `Type: trivial` / doc-only file-set bound (`_classify_trivial_change`).

This is the catastrophic-blast-radius guard: a chunk declaring `Type: trivial`
(or `doc-only`) skips Critic review, so it must NOT be allowed to silently edit
the framework-governance-defining files. Under plugin distribution those live in
`skills/` (the critic/pr/etc. definitions + bundled protocols), `methodology/`,
`templates/`, and `CLAUDE.md`. The pre-2.0 `agents/` tree was removed in the
plugin cutover, so it is no longer a protected class.

These tests are the regression coverage the bound never had — the stale `agents/`
literal had nothing pinning it.
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_loader = importlib.machinery.SourceFileLoader("prawduct_hook_gate", str(_ROOT / "bin" / "prawduct-hook"))
_spec = importlib.util.spec_from_loader("prawduct_hook_gate", _loader)
_hook = importlib.util.module_from_spec(_spec)
_loader.exec_module(_hook)


def _classify(path, *, src_path=None, is_addition=False, is_deletion=False):
    return _hook._classify_trivial_change(
        path=path, src_path=src_path, is_addition=is_addition, is_deletion=is_deletion
    )


class TestProtectedPaths:
    """Editing a catastrophic-blast-radius framework file is never trivial."""

    def test_skills_edit_is_blocked(self):
        # skills/ holds the critic/pr/etc. definitions — editing one changes
        # governance itself, so it must not pass the trivial bound.
        reason = _classify("skills/critic/SKILL.md")
        assert reason == "skill-file-edited: skills/critic/SKILL.md"

    def test_skills_protocol_edit_is_blocked(self):
        reason = _classify("skills/pr/review-protocol.md")
        assert reason == "skill-file-edited: skills/pr/review-protocol.md"

    def test_methodology_edit_is_blocked(self):
        assert _classify("methodology/building.md") == "methodology-edited: methodology/building.md"

    def test_templates_edit_is_blocked(self):
        assert _classify("templates/build-plan.md") == "template-edited: templates/build-plan.md"

    def test_claude_md_edit_is_blocked(self):
        assert _classify("CLAUDE.md") == "claude-md-edited: CLAUDE.md"


class TestAgentsNoLongerSpecial:
    """The pre-2.0 `agents/` tree was removed; it is no longer a protected class.
    (Kept as an explicit contract so a future reader knows the omission is
    intentional, not an oversight.)"""

    def test_agents_path_is_not_blocked(self):
        # A hypothetical agents/ .md edit is now an ordinary doc edit (eligible).
        assert _classify("agents/critic/SKILL.md") is None


class TestNonProtectedChanges:
    def test_ordinary_source_edit_is_eligible(self):
        assert _classify("lib/waivers.py") is None

    def test_metadata_path_is_out_of_scope(self):
        assert _classify(".prawduct/backlog.md") is None
        assert _classify(".claude/settings.json") is None

    def test_new_file_is_blocked(self):
        assert _classify("lib/new_module.py", is_addition=True) == "new-file: lib/new_module.py"

    def test_test_deletion_is_blocked(self):
        assert _classify("tests/test_x.py", is_deletion=True) == "test-file-deleted: tests/test_x.py"

    def test_test_rename_out_is_blocked(self):
        reason = _classify("lib/x.py", src_path="tests/test_x.py")
        assert reason == "test-file-deleted: tests/test_x.py (renamed out)"

    def test_reason_prefix_is_skill_not_agent(self):
        # Guard against regressing to the stale `agent-file-edited` spelling.
        reason = _classify("skills/critic/SKILL.md")
        assert reason is not None and reason.startswith("skill-file-edited")
        assert "agent-file-edited" not in reason
