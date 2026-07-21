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

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
# _classify_trivial_change + _TRIVIAL_PROTECTED_PATHS moved to lib/buildplan_refs
# (STH-9V4K ch.3); test the code where it now lives, not via the hook.
from lib import buildplan_refs as _bpr  # noqa: E402


def _classify(path, *, src_path=None, is_addition=False, is_deletion=False):
    return _bpr._classify_trivial_change(
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


class TestProtectedPathsConstant:
    """STH-1W5N: the unconditional protected-path bounds are centralized in the
    module-level `_TRIVIAL_PROTECTED_PATHS` constant — the single source of truth
    referenced by `_classify_trivial_change`. These assertions pin that the
    constant (not a stale inline literal) is what the classifier consults."""

    def test_constant_is_non_empty_frozenset(self):
        assert isinstance(_bpr._TRIVIAL_PROTECTED_PATHS, frozenset)
        assert _bpr._TRIVIAL_PROTECTED_PATHS, "the protected-path bound list must be non-empty"

    def test_constant_contains_documented_paths(self):
        # The four catastrophic-blast-radius classes the bound has always covered.
        paths = {entry[0] for entry in _bpr._TRIVIAL_PROTECTED_PATHS}
        assert {"skills/", "methodology/", "templates/", "CLAUDE.md"} <= paths

    def test_claude_md_is_exact_match_not_prefix(self):
        # CLAUDE.md is an exact-match bound (a nested foo/CLAUDE.md is ordinary
        # product doc); the others are prefix bounds. The flag in the constant
        # is what drives that distinction.
        by_path = {entry[0]: entry[1] for entry in _bpr._TRIVIAL_PROTECTED_PATHS}
        assert by_path["CLAUDE.md"] is True
        assert by_path["skills/"] is False

    def test_classifier_reads_the_constant(self):
        # Every entry in the constant must actually produce a violation from the
        # classifier with the constant's own reason label — proving the constant
        # is the source of truth, not a parallel copy that could drift.
        for protected, is_exact, reason_label in _bpr._TRIVIAL_PROTECTED_PATHS:
            sample = protected if is_exact else protected + "x.md"
            reason = _classify(sample)
            assert reason == f"{reason_label}: {sample}", (
                f"constant entry {protected!r} did not drive the classifier"
            )

    def test_protected_path_violation_helper_shared_with_pr_gate(self):
        # PR-5K8D: the extracted helper is the seam the PR doc-only gate
        # consults — same labels, same exact/prefix semantics.
        assert (
            _bpr.protected_path_violation("skills/pr/SKILL.md")
            == "skill-file-edited: skills/pr/SKILL.md"
        )
        assert _bpr.protected_path_violation("CLAUDE.md") == "claude-md-edited: CLAUDE.md"
        assert _bpr.protected_path_violation("foo/CLAUDE.md") is None
        assert _bpr.protected_path_violation("docs/notes.md") is None
