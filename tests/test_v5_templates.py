"""Tests for v5 template content, structure, and constraints.

Validates that v5 templates meet the requirements:
- product-claude.md: <2,800 tokens, critical rules at top, all C1-C4 represented
- project-state.yaml: v5 fields present, v4 fields preserved
- critic-review.md: goal-based structure, signal-driven scope
- boundary-patterns.md: template structure correct
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import yaml

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"

# Import setup module for block constants
_SETUP_PATH = Path(__file__).resolve().parent.parent / "tools" / "prawduct-setup.py"
_setup_spec = importlib.util.spec_from_file_location("prawduct_setup", _SETUP_PATH)
_setup_mod = importlib.util.module_from_spec(_setup_spec)
_setup_spec.loader.exec_module(_setup_mod)
BLOCK_BEGIN = _setup_mod.BLOCK_BEGIN
BLOCK_END = _setup_mod.BLOCK_END


def read_template(name: str) -> str:
    """Read a template file and return its content."""
    return (TEMPLATES_DIR / name).read_text()


def estimate_tokens(text: str) -> int:
    """Estimate token count using word-count heuristic."""
    words = len(text.split())
    return int(words * 1.3)


# =============================================================================
# product-claude.md — Structure and Token Budget
# =============================================================================


class TestProductClaudeStructure:
    """Verify structural requirements and token budget of the v5 CLAUDE.md template."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("product-claude.md")

    def test_block_markers(self, template: str):
        """PRAWDUCT:BEGIN and END markers exist in correct order."""
        assert BLOCK_BEGIN in template
        assert BLOCK_END in template
        assert template.index(BLOCK_BEGIN) < template.index(BLOCK_END)

    def test_user_content_areas(self, template: str):
        """User content space before BEGIN; nothing after END."""
        assert "Add project-specific instructions" in template[:template.index(BLOCK_BEGIN)]
        after = template[template.index(BLOCK_END) + len(BLOCK_END):].strip()
        assert len(after) == 0, f"Unexpected content after PRAWDUCT:END: {after[:100]}"

    def test_product_name_placeholder(self, template: str):
        assert "{{PRODUCT_NAME}}" in template

    def test_token_budget(self, template: str):
        """Prawduct block <2,800 tokens; total template <3,500 tokens."""
        begin_idx = template.index(BLOCK_BEGIN)
        end_idx = template.index(BLOCK_END) + len(BLOCK_END)
        block_tokens = estimate_tokens(template[begin_idx:end_idx])
        total_tokens = estimate_tokens(template)
        assert block_tokens <= 2800, f"Block is ~{block_tokens} tokens, budget is 2,800"
        assert total_tokens <= 3500, f"Total is ~{total_tokens} tokens, budget is 3,500"


# =============================================================================
# product-claude.md — Content Requirements (C1-C4)
# =============================================================================


class TestProductClaudeCriticalRules:
    """Critical rules section must exist before principles with all required rules."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("product-claude.md")

    def test_critical_rules_before_principles(self, template: str):
        assert "## Critical Rules" in template
        assert "## Principles" in template
        assert template.index("## Critical Rules") < template.index("## Principles")

    def test_all_critical_rules_present(self, template: str):
        """All critical rules must appear in the Critical Rules section."""
        rules_section = template[
            template.index("## Critical Rules"):template.index("## Principles")
        ].lower()
        assert "never weaken" in rules_section
        assert "silently drop" in rules_section
        assert "alongside" in rules_section
        assert "investigate" in rules_section
        assert "boundar" in rules_section
        assert "update artifacts" in rules_section
        assert "critic" in rules_section
        # Exception handling (swallow or except)
        assert "swallow" in rules_section or "except" in rules_section


class TestProductClaudeGovernance:
    """Verify work-scaled governance (C1), investigated changes (C3), active context (C4)."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("product-claude.md")

    def test_governance_model(self, template: str):
        """Work-scaled governance with size/type levels, no v4 phase references."""
        lower = template.lower()
        assert "## Governance Model" in template
        assert "no phases" in lower or "there are no phases" in lower
        for level in ["trivial", "small", "medium", "large"]:
            assert level in lower
        for wtype in ["feature", "bugfix", "refactor", "hotfix"]:
            assert wtype in lower
        assert "current_phase" not in template

    def test_investigated_changes(self, template: str):
        """Research subagent, boundary patterns, lock-in references."""
        lower = template.lower()
        assert "research subagent" in lower or "research sub" in lower
        assert "boundary-patterns" in template
        assert "lock-in" in lower

    def test_active_context(self, template: str):
        """Learning lifecycle, session briefing, subagent briefing, token budget."""
        lower = template.lower()
        assert "active rules" in lower
        assert "learnings-detail" in lower
        assert "session briefing" in lower
        assert ".subagent-briefing.md" in template
        assert "3,000 tokens" in template or "3K tokens" in template

    def test_critic_section(self, template: str):
        """Critic instructions with goal-based scope and compact instructions."""
        assert "## The Critic" in template
        assert "/critic" in template
        critic_section = template[template.index("## The Critic"):]
        assert "goal" in critic_section.lower() or "signal" in critic_section.lower()
        assert "## Compact Instructions" in template


class TestProductClaudePrinciples:
    """All 22 principles must be present."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("product-claude.md")

    @pytest.mark.parametrize("num,name", [
        (1, "Tests Are Contracts"),
        (2, "Complete Delivery"),
        (3, "Living Documentation"),
        (4, "Reasoned Decisions"),
        (5, "Honest Confidence"),
        (6, "Bring Expertise"),
        (7, "Accessibility From the Start"),
        (8, "Visible Costs"),
        (9, "Clean Deployment"),
        (10, "Proportional Effort"),
        (11, "Scope Discipline"),
        (12, "Coherent Artifacts"),
        (13, "Independent Review"),
        (14, "Validate Before Propagating"),
        (15, "Root Cause Discipline"),
        (16, "Automatic Reflection"),
        (17, "Close the Learning Loop"),
        (18, "Evolving Principles"),
        (19, "Infer, Confirm, Proceed"),
        (20, "Structural Awareness"),
        (21, "Governance Is Structural"),
        (22, "Challenge Gently, Defer Gracefully"),
    ])
    def test_principle_present(self, template: str, num: int, name: str):
        assert name in template, f"Principle {num} ({name}) missing from template"


# =============================================================================
# project-state.yaml — v5 Fields
# =============================================================================


class TestProjectStateV5Fields:
    """Verify project-state.yaml has v5 fields and preserves v4 fields."""

    @pytest.fixture
    def state(self) -> dict:
        content = read_template("project-state.yaml")
        return yaml.safe_load(content)

    @pytest.fixture
    def raw(self) -> str:
        return read_template("project-state.yaml")

    def test_v5_additions(self, state: dict):
        """v5 adds health_check with null starting values."""
        assert "health_check" in state
        hc = state["health_check"]
        assert hc["last_full_check"] is None
        assert hc["last_check_findings"] is None

    def test_v6_removals(self, state: dict):
        """v6 removes volatile state: current_phase, work_in_progress, build_plan."""
        assert "current_phase" not in state
        assert "work_in_progress" not in state
        assert "build_plan" not in state

    def test_v4_fields_preserved(self, state: dict):
        """All v4 fields that should persist are present."""
        for field in ["classification", "product_definition", "technical_decisions",
                      "design_decisions", "open_questions", "user_expertise",
                      "build_preferences", "artifact_manifest", "build_state"]:
            assert field in state, f"v4 field '{field}' missing"

    def test_structural_characteristics(self, state: dict):
        """All 6 structural characteristics present."""
        structural = state["classification"]["structural"]
        for char in ["has_human_interface", "runs_unattended",
                     "exposes_programmatic_interface", "has_multiple_party_types",
                     "handles_sensitive_data", "multi_process_distributed"]:
            assert char in structural

    def test_design_decisions_preserved(self, state: dict):
        """Key design decision fields preserved."""
        assert "observability_approach" in state["design_decisions"]
        assert "error_handling_approach" in state["design_decisions"]

    def test_change_log_removed(self, state: dict):
        """change_log now in separate file."""
        assert "change_log" not in state or state.get("change_log") is None

    def test_comments_present(self, raw: str):
        """Template has product name placeholder and descriptive comments."""
        assert "{{PRODUCT_NAME}}" in raw
        assert "staleness" in raw.lower() or "health check" in raw.lower()


# =============================================================================
# critic-review.md — Goal-Based Structure
# =============================================================================


class TestCriticReviewGoalBased:
    """Verify critic-review.md uses goal-based scope, not fixed checklist."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("critic-review.md")

    def test_goal_based_structure(self, template: str):
        """Uses goals instead of numbered checks; signals section present."""
        assert "## Review Goals" in template or "## Goals" in template
        assert "### Spec Compliance\n" not in template
        assert "signal" in template.lower()
        assert "### Signals" in template

    def test_all_goals_present(self, template: str):
        """All seven review goals present."""
        lower = template.lower()
        assert "nothing is broken" in lower
        assert "nothing is missing" in lower
        assert "nothing is unintended" in lower
        assert "coherent" in lower or "coherence" in lower
        assert "deliberate" in lower or "rationale" in lower
        assert "design is sound" in lower

    def test_work_scaling(self, template: str):
        """Work size and type guidance present."""
        lower = template.lower()
        for level in ["trivial", "medium", "large"]:
            assert level in lower
        for wtype in ["feature", "bugfix", "refactor"]:
            assert wtype in lower

    def test_severity_levels(self, template: str):
        """BLOCKING/WARNING/NOTE with correct semantics."""
        assert "BLOCKING" in template
        assert "WARNING" in template
        assert "NOTE" in template
        for line in template.split("\n"):
            if line.startswith("- **NOTE**"):
                assert "ambiguous" in line.lower() or "unsure" in line.lower() or "genuinely" in line.lower()
                break

    def test_references_and_output(self, template: str):
        """References findings JSON, boundary patterns, project preferences, learnings."""
        assert ".critic-findings.json" in template
        assert "boundary" in template.lower() or "contract" in template.lower()
        assert "independent" in template.lower()
        assert "learnings.md" in template
        assert "Learnings Cross-Check" in template
        assert "Backlog Reconciliation" in template

    def test_quality_checks(self, template: str):
        """Security, documentation drift, design details, coordinator pattern present."""
        lower = template.lower()
        assert "injection" in lower
        assert "secret" in lower or "credential" in lower
        assert "documentation drift" in lower
        assert "encapsulation" in lower
        assert "coupling" in lower
        assert "coordinator" in lower
        assert "bidirectional" in lower
        assert "readme" in lower

    def test_project_preferences_blocking(self, template: str):
        """Project preferences violations should be BLOCKING."""
        for line in template.split("\n"):
            if "project-preferences" in line.lower() and "blocking" in line.lower():
                break
        else:
            pytest.fail("project-preferences compliance should be BLOCKING")

    def test_changelog_scope(self, template: str):
        assert "changelog" in template.lower()

    def test_property_based_testing_note(self, template: str):
        """Goal 1 includes a NOTE-level check for property-based testing."""
        lower = template.lower()
        assert "property-based" in lower
        # It should be NOTE severity (advisory, not requirement)
        # Find the PBT sentence and verify it's in Goal 1 context
        goal1_start = template.index("### 1.")
        goal2_start = template.index("### 2.")
        goal1_section = template[goal1_start:goal2_start].lower()
        assert "property-based" in goal1_section
        # NOTE should appear after the last PBT mention (severity comes at end of sentence)
        last_pbt = goal1_section.rfind("property-based")
        after_last_pbt = goal1_section[last_pbt:]
        assert "note" in after_last_pbt[:200]


# =============================================================================
# boundary-patterns.md — Template Structure
# =============================================================================


class TestBoundaryPatternsTemplate:
    """Verify boundary-patterns.md template structure."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("boundary-patterns.md")

    def test_structure(self, template: str):
        """Has product name placeholder, contract surfaces, and test levels."""
        assert "{{PRODUCT_NAME}}" in template
        assert "## Contract Surfaces" in template
        assert "## Test Levels" in template
        assert "<!-- " in template
        assert "Example:" in template

    def test_contract_surface_sections(self, template: str):
        """All contract surface types present."""
        assert "### API Endpoints" in template
        assert "### Database Schemas" in template
        assert "### Inter-Process Communication" in template
        assert "### Frontend/Backend" in template
        assert "### Configuration" in template

    def test_test_level_tiers(self, template: str):
        """All four test level tiers present."""
        for tier in ["Unit", "Integration", "Contract", "End-to-end"]:
            assert tier in template


# =============================================================================
# Cross-Template Consistency
# =============================================================================


class TestBuildGovernancePBT:
    """Verify build-governance.md includes property-based testing guidance."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("build-governance.md")

    def test_pbt_in_test_discipline(self, template: str):
        """Build governance mentions PBT in the test-writing step."""
        lower = template.lower()
        assert "property-based" in lower
        # Should be in the "Write tests" step context, not in rules or session end
        test_step_line = [
            line for line in template.split("\n")
            if "Write tests alongside code" in line
        ]
        assert len(test_step_line) == 1
        assert "property-based" in test_step_line[0].lower()

    def test_pbt_references_test_specifications(self, template: str):
        """PBT guidance points to test-specifications for details."""
        for line in template.split("\n"):
            if "property-based" in line.lower():
                assert "test-specifications" in line.lower()
                break
        else:
            pytest.fail("PBT guidance line not found")


class TestCriticSkillPBT:
    """Verify framework Critic SKILL.md includes PBT check."""

    @pytest.fixture
    def skill(self) -> str:
        return (FRAMEWORK_DIR / "agents" / "critic" / "SKILL.md").read_text()

    def test_pbt_in_goal1(self, skill: str):
        """Framework Critic Goal 1 includes property-based testing check."""
        goal1_start = skill.index("### 1.")
        goal2_start = skill.index("### 2.")
        goal1_section = skill[goal1_start:goal2_start].lower()
        assert "property-based" in goal1_section

    def test_pbt_is_note_severity(self, skill: str):
        """PBT check is NOTE severity (advisory, not blocking)."""
        for line in skill.split("\n"):
            if "property-based" in line.lower():
                assert "note" in line.lower()
                break


class TestCrossTemplateConsistency:
    """Verify templates reference each other correctly."""

    def test_claude_references(self):
        """CLAUDE.md references all required artifacts and skills."""
        template = read_template("product-claude.md")
        assert "/critic" in template or "critic-review.md" in template
        assert "boundary-patterns" in template
        assert ".subagent-briefing.md" in template
        assert "learnings-detail" in template
        assert "project-preferences" in template
        assert "/learnings" in template

    def test_claude_is_self_contained(self):
        """Product CLAUDE.md must NOT reference framework methodology files."""
        template = read_template("product-claude.md")
        for f in ["methodology/discovery.md", "methodology/planning.md",
                   "methodology/building.md", "methodology/reflection.md"]:
            assert f not in template

    def test_critic_references(self):
        """critic-review.md references required artifacts."""
        template = read_template("critic-review.md")
        assert "boundary-patterns" in template
        assert "project-preferences" in template
        assert ".critic-findings.json" in template

    def test_pbt_consistency_across_synced_templates(self):
        """All synced governance files mention property-based testing."""
        build_gov = read_template("build-governance.md").lower()
        critic = read_template("critic-review.md").lower()
        critic_skill = (FRAMEWORK_DIR / "agents" / "critic" / "SKILL.md").read_text().lower()
        for name, content in [
            ("build-governance.md", build_gov),
            ("critic-review.md", critic),
            ("agents/critic/SKILL.md", critic_skill),
        ]:
            assert "property-based" in content, f"{name} missing PBT guidance"


# =============================================================================
# learnings skill — Template Structure
# =============================================================================

FRAMEWORK_DIR = Path(__file__).resolve().parent.parent


class TestLearningsSkillTemplate:
    """Verify /learnings skill has required structure."""

    @pytest.fixture
    def template(self) -> str:
        return (FRAMEWORK_DIR / ".claude" / "skills" / "learnings" / "SKILL.md").read_text()

    def test_frontmatter_and_references(self, template: str):
        """Has required frontmatter and references all knowledge files."""
        assert "description:" in template
        assert "argument-hint:" in template
        assert "disable-model-invocation:" in template
        assert "learnings.md" in template
        assert "learnings-detail.md" in template
        assert "project-preferences.md" in template

    def test_behavior(self, template: str):
        """Has subagent instructions, no-args mode, read-only, token budget."""
        assert "subagent" in template.lower() or "Agent tool" in template
        assert "no topic" in template.lower() or "no topic was provided" in template.lower()
        assert "read-only" in template.lower()
        assert "500 tokens" in template
