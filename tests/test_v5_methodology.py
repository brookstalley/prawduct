"""Tests for v5 methodology and Critic updates (Chunk 4).

Verifies that methodology files, Critic instructions, and cross-cutting concerns
are internally consistent and reflect v5 concepts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def read_file(rel_path: str) -> str:
    return (ROOT / rel_path).read_text()


def estimate_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


# =============================================================================
# building.md
# =============================================================================


class TestBuildingMethodology:
    @pytest.fixture(autouse=True)
    def load(self):
        self.content = read_file("methodology/building.md")

    def test_has_work_scaled_governance(self):
        assert "Work-Scaled Governance" in self.content

    def test_no_phase_references(self):
        lower = self.content.lower()
        # Should not reference fixed phases
        assert "current_phase" not in lower
        assert "phase transition" not in lower

    def test_has_size_levels(self):
        for level in ["Trivial", "Small", "Medium", "Large"]:
            assert level in self.content

    def test_has_type_levels(self):
        for wtype in ["Feature", "Bugfix", "Refactor", "Optimization", "Debt", "hotfix"]:
            assert wtype.lower() in self.content.lower()

    def test_has_investigated_changes_section(self):
        assert "Investigated Changes" in self.content

    def test_has_boundary_investigation(self):
        assert "boundary" in self.content.lower()
        assert "contract surface" in self.content.lower()

    def test_has_decision_research(self):
        assert "Decision Research" in self.content
        assert "lock-in" in self.content.lower()

    def test_has_research_subagent(self):
        assert "research subagent" in self.content.lower() or "research subagent" in self.content

    def test_has_subagent_briefing_reference(self):
        assert ".subagent-briefing.md" in self.content

    def test_has_boundary_patterns_reference(self):
        assert "boundary-patterns.md" in self.content

    def test_has_goal_based_critic(self):
        assert "Nothing Is Broken" in self.content
        assert "Design Is Sound" in self.content

    def test_has_build_cycle(self):
        assert "Build Cycle" in self.content

    def test_has_test_discipline(self):
        assert "Test Discipline" in self.content

    def test_has_common_traps(self):
        assert "Common Traps" in self.content

    def test_has_uninvestigated_decisions_trap(self):
        assert "Uninvestigated decisions" in self.content

    def test_has_boundary_blindness_trap(self):
        assert "Boundary blindness" in self.content

    def test_token_budget(self):
        tokens = estimate_tokens(self.content)
        assert tokens < 3800, f"building.md is ~{tokens} tokens, should be <3800"


# =============================================================================
# discovery.md
# =============================================================================


class TestDiscoveryMethodology:
    @pytest.fixture(autouse=True)
    def load(self):
        self.content = read_file("methodology/discovery.md")

    def test_continuous_discovery(self):
        assert "continuous" in self.content.lower() or "isn't a phase" in self.content.lower()

    def test_structural_characteristics_present(self):
        for char in ["human interface", "unattended", "programmatic interface", "multiple party", "sensitive data"]:
            assert char in self.content.lower()


# =============================================================================
# planning.md
# =============================================================================


class TestPlanningMethodology:
    @pytest.fixture(autouse=True)
    def load(self):
        self.content = read_file("methodology/planning.md")

    def test_continuous_planning(self):
        lower = self.content.lower()
        assert "not a one-time phase" in lower or "isn't a one-time phase" in lower or "continuous" in lower


# =============================================================================
# reflection.md
# =============================================================================


class TestReflectionMethodology:
    @pytest.fixture(autouse=True)
    def load(self):
        self.content = read_file("methodology/reflection.md")

    def test_has_learning_lifecycle(self):
        assert "Learning Lifecycle" in self.content

    def test_has_provisional_stage(self):
        assert "Provisional" in self.content

    def test_has_confirmed_stage(self):
        assert "Confirmed" in self.content

    def test_has_incorporated_stage(self):
        assert "Incorporated" in self.content

    def test_has_recurrence_escalation(self):
        assert "Recurrence escalation" in self.content or "recurrence escalation" in self.content

    def test_no_phase_transition_language(self):
        assert "phase transition" not in self.content.lower()

    def test_has_two_tier_learnings(self):
        assert "learnings.md" in self.content
        assert "learnings-detail.md" in self.content


# =============================================================================
# SKILL.md (Critic)
# =============================================================================


class TestCriticSkill:
    @pytest.fixture(autouse=True)
    def load(self):
        self.content = read_file("agents/critic/SKILL.md")

    def test_has_signals_section(self):
        assert "Signals That Guide Your Review" in self.content

    def test_has_work_size_guidance(self):
        for level in ["Trivial", "Small", "Medium", "Large"]:
            assert level in self.content

    def test_has_work_type_guidance(self):
        assert "Feature" in self.content
        assert "Bugfix" in self.content

    def test_has_goal_based_structure(self):
        for goal in [
            "Nothing Is Broken",
            "Nothing Is Missing",
            "Nothing Is Unintended",
            "Everything Is Coherent",
            "Decisions Were Deliberate",
            "System Can Be Understood",
            "Design Is Sound",
        ]:
            assert goal in self.content

    def test_has_boundary_check(self):
        assert "boundary-patterns.md" in self.content or "contract surface" in self.content.lower()

    def test_has_decision_investigation_check(self):
        assert "alternatives considered" in self.content.lower()

    def test_has_severity_levels(self):
        assert "BLOCKING" in self.content
        assert "WARNING" in self.content
        assert "NOTE" in self.content

    def test_has_findings_json_format(self):
        assert ".critic-findings.json" in self.content

    def test_has_framework_specific_checks(self):
        assert "Framework-Specific Checks" in self.content
        assert "Generality" in self.content
        assert "Instruction Clarity" in self.content

    def test_output_includes_signals(self):
        # Output format should have signals section
        assert "### Signals" in self.content

    def test_output_uses_goal_key(self):
        # JSON format uses "goal" not "check"
        assert '"goal"' in self.content

    def test_independent_reviewer_statement(self):
        assert "independent" in self.content.lower()

    def test_has_security_checks(self):
        assert "injection" in self.content.lower()
        assert "hardcoded secrets" in self.content.lower() or "credentials" in self.content.lower()
        assert "auth" in self.content.lower()

    def test_has_documentation_drift(self):
        assert "documentation drift" in self.content.lower() or "doc" in self.content.lower()
        assert "comments" in self.content.lower()

    def test_has_design_goal_details(self):
        assert "encapsulation" in self.content.lower()
        assert "coupling" in self.content.lower()
        assert "simplification" in self.content.lower() or "simpler" in self.content.lower()
        assert "deduplication" in self.content.lower() or "duplicated" in self.content.lower()

    def test_has_coordinator_pattern(self):
        assert "coordinator" in self.content.lower()
        assert "correctness reviewer" in self.content.lower()
        assert "design reviewer" in self.content.lower()
        assert "sustainability reviewer" in self.content.lower()

    def test_note_severity_is_ambiguous(self):
        """NOTE severity should indicate genuine ambiguity, not minor suggestions."""
        for line in self.content.split("\n"):
            if line.startswith("- **NOTE**"):
                assert "ambiguous" in line.lower() or "unsure" in line.lower() or "genuinely" in line.lower()
                break

    def test_project_preferences_blocking(self):
        """Project preferences violations should be BLOCKING."""
        assert "project-preferences.md" in self.content
        # Find the preferences line and verify BLOCKING severity
        for line in self.content.split("\n"):
            if "project-preferences" in line.lower() and "blocking" in line.lower():
                break
        else:
            pytest.fail("project-preferences compliance should be BLOCKING")

    def test_readme_active_check(self):
        """Critic should actively check README, not just detect passive drift."""
        assert "readme" in self.content.lower()
        # Should mention actively reading the README
        assert "actively read" in self.content.lower() or "read the" in self.content.lower()

    def test_historical_records_immutable(self):
        """Changelog and historical entries should not be flagged for stale terminology."""
        assert "historical" in self.content.lower()
        assert "immutable" in self.content.lower() or "changelog" in self.content.lower()

    def test_token_budget(self):
        tokens = estimate_tokens(self.content)
        assert tokens < 3500, f"SKILL.md is ~{tokens} tokens, should be <3500"


# =============================================================================
# review-cycle.md
# =============================================================================


class TestReviewCycle:
    @pytest.fixture(autouse=True)
    def load(self):
        self.content = read_file("agents/critic/review-cycle.md")

    def test_work_scaled_review(self):
        for level in ["Trivial", "Small", "Medium", "Large"]:
            assert level in self.content

    def test_goal_based_references(self):
        assert "goal-based" in self.content.lower() or "Goal" in self.content

    def test_findings_json_reference(self):
        assert ".critic-findings.json" in self.content


# =============================================================================
# Cross-cutting concerns
# =============================================================================


class TestCrossCuttingConcerns:
    @pytest.fixture(autouse=True)
    def load(self):
        self.content = read_file(".prawduct/cross-cutting-concerns.md")

    def test_has_boundary_coherence(self):
        assert "Boundary coherence" in self.content

    def test_has_subagent_governance(self):
        assert "Subagent governance" in self.content

    def test_references_v5_goals(self):
        assert "Goal" in self.content
        assert "Nothing Is Broken" in self.content or "Nothing Is Missing" in self.content

    def test_references_boundary_patterns(self):
        assert "boundary-patterns.md" in self.content

    def test_references_subagent_briefing(self):
        assert "subagent-briefing.md" in self.content

    def test_references_compliance_canary(self):
        assert "compliance canary" in self.content.lower() or "canary" in self.content.lower()


# =============================================================================
# Cross-file consistency
# =============================================================================


class TestMethodologyConsistency:
    """Verify methodology files reference each other correctly."""

    @pytest.fixture(autouse=True)
    def load(self):
        self.building = read_file("methodology/building.md")
        self.discovery = read_file("methodology/discovery.md")
        self.planning = read_file("methodology/planning.md")
        self.reflection = read_file("methodology/reflection.md")
        self.critic = read_file("agents/critic/SKILL.md")

    def test_building_references_critic_review(self):
        assert "critic-review.md" in self.building

    def test_building_references_subagent_briefing(self):
        assert ".subagent-briefing.md" in self.building

    def test_critic_references_boundary_patterns(self):
        assert "boundary-patterns.md" in self.critic

    def test_critic_references_project_preferences(self):
        assert "project-preferences.md" in self.critic

    def test_reflection_references_learnings_detail(self):
        assert "learnings-detail.md" in self.reflection

    def test_all_methodology_files_exist(self):
        for f in ["methodology/building.md", "methodology/discovery.md",
                   "methodology/planning.md", "methodology/reflection.md"]:
            assert (ROOT / f).is_file(), f"{f} missing"

    def test_all_critic_files_exist(self):
        for f in ["agents/critic/SKILL.md", "agents/critic/review-cycle.md"]:
            assert (ROOT / f).is_file(), f"{f} missing"

    def test_no_files_reference_old_check_names(self):
        """v5 uses goal names, not check names."""
        for content in [self.building, self.critic]:
            # Old check names should not appear as section headers
            assert "### Check 1:" not in content
            assert "### Check 2:" not in content
            assert "### Check 3:" not in content
