"""Tests for the governance-protected path bounds (`protected_path_violation`).

A change under `skills/` (the critic/pr/etc. definitions + bundled protocols),
`methodology/`, `templates/`, `agents/` (a subagent's own system prompt), or to
root `CLAUDE.md` / `AGENTS.md` edits the framework's own governance. Through
`coverage_algebra.is_judgeable_path` that makes it judgeable even as pure `.md`,
so it never rides a doc-only fast path past the reviewers.

These bounds began as the `Type: trivial` file-set gate's path rules. That gate
was retired (#301); its conditional bounds (new files, test deletions) went with
it, and the path list stayed because the doc-only classification reads it.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from lib import buildplan_refs as _bpr  # noqa: E402

_violation = _bpr.protected_path_violation


class TestProtectedPaths:
    """Editing a framework-governance file is always a protected edit."""

    def test_skills_edit_is_protected(self):
        assert _violation("skills/critic/SKILL.md") == "skill-file-edited: skills/critic/SKILL.md"

    def test_skills_protocol_edit_is_protected(self):
        assert (
            _violation("skills/pr/review-protocol.md")
            == "skill-file-edited: skills/pr/review-protocol.md"
        )

    def test_methodology_edit_is_protected(self):
        assert _violation("methodology/building.md") == "methodology-edited: methodology/building.md"

    def test_templates_edit_is_protected(self):
        assert _violation("templates/build-plan.md") == "template-edited: templates/build-plan.md"

    def test_claude_md_edit_is_protected(self):
        assert _violation("CLAUDE.md") == "claude-md-edited: CLAUDE.md"

    def test_agents_md_edit_is_protected(self):
        """Root AGENTS.md carries the governance anchor every host reads, and
        CLAUDE.md imports it, so it is the same contract under a second name."""
        assert _violation("AGENTS.md") == "agents-md-edited: AGENTS.md"

    def test_nested_contract_files_are_ordinary_docs(self):
        # CLAUDE.md and AGENTS.md are exact-match bounds.
        assert _violation("foo/CLAUDE.md") is None
        assert _violation("foo/AGENTS.md") is None

    def test_ordinary_files_are_unprotected(self):
        assert _violation("docs/notes.md") is None
        assert _violation("lib/waivers.py") is None

    def test_reason_prefix_is_skill_not_agent(self):
        # Guard against regressing to the stale `agent-file-edited` spelling.
        reason = _violation("skills/critic/SKILL.md")
        assert reason is not None and reason.startswith("skill-file-edited")
        assert "agent-file-edited" not in reason


class TestAgentsAreProtected:
    """`agents/` is a protected class again, because the tree came back.

    It was dropped when the pre-2.0 `agents/` tree was removed, and the
    contract recorded then said so. The plugin now ships `agents/` again, and
    what is in it is a review subagent's own system prompt — behavioural logic
    by exactly the argument `skills/` makes for fork-skill prose, and the one
    whose unreviewed edit compounds, since it decides what every later review
    looks at.
    """

    def test_agents_path_is_protected(self):
        assert (
            _violation("agents/critic-reviewer.md")
            == "agent-file-edited: agents/critic-reviewer.md"
        )

    def test_a_nested_plugin_agents_path_is_protected(self):
        # Segment match, like every other directory bound: a repo that keeps its
        # plugin under `plugin/` is the ordinary layout, not an escape.
        assert _violation("plugin/agents/critic-reviewer.md") is not None


class TestProtectedPathsConstant:
    """STH-1W5N: the bounds are centralized in the module-level
    `_GOVERNANCE_PROTECTED_PATHS` constant — the single source of truth
    `protected_path_violation` consults. These assertions pin that the
    constant (not a stale inline literal) is what the predicate reads."""

    def test_constant_is_non_empty_frozenset(self):
        assert isinstance(_bpr._GOVERNANCE_PROTECTED_PATHS, frozenset)
        assert _bpr._GOVERNANCE_PROTECTED_PATHS, "the protected-path bound list must be non-empty"

    def test_constant_contains_documented_paths(self):
        paths = {entry[0] for entry in _bpr._GOVERNANCE_PROTECTED_PATHS}
        assert {
            "skills/", "methodology/", "templates/", "agents/", "CLAUDE.md", "AGENTS.md",
        } <= paths

    def test_claude_md_is_exact_match_not_prefix(self):
        # The flag in the constant is what drives exact-vs-segment matching.
        by_path = {entry[0]: entry[1] for entry in _bpr._GOVERNANCE_PROTECTED_PATHS}
        assert by_path["CLAUDE.md"] is True
        assert by_path["skills/"] is False

    def test_predicate_reads_the_constant(self):
        # Every entry must produce a violation carrying its own reason label —
        # proving the constant is the source of truth, not a parallel copy.
        for protected, is_exact, reason_label in _bpr._GOVERNANCE_PROTECTED_PATHS:
            sample = protected if is_exact else protected + "x.md"
            assert _violation(sample) == f"{reason_label}: {sample}", (
                f"constant entry {protected!r} did not drive the predicate"
            )


class TestProtectedPathsMatchTheSegmentNotTheRoot:
    """Root-anchored bounds stopped matching when the framework moved under
    `plugin/`, so every `plugin/skills/**.md` edit read as non-judgeable and a
    skills-only session skipped the reviewers entirely. The failure mode was
    silence, which is why no test caught it for the whole relocation.
    """

    def test_relocated_skill_prose_is_protected(self):
        assert (
            _violation("plugin/skills/backlog/SKILL.md")
            == "skill-file-edited: plugin/skills/backlog/SKILL.md"
        )

    def test_relocated_methodology_and_templates_are_protected(self):
        assert _violation("plugin/methodology/building.md")
        assert _violation("plugin/templates/build-plan.md")

    def test_root_level_still_protected(self):
        assert _violation("skills/pr/SKILL.md")

    def test_segment_boundary_is_respected(self):
        # Over-including is the safe direction, but not at the cost of matching
        # any directory whose NAME merely ends in a protected token.
        assert _violation("myskills/foo.md") is None
        assert _violation("src/skillset/a.py") is None

    def test_ordinary_code_is_still_unprotected(self):
        assert _violation("plugin/lib/core.py") is None
