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

# Import sync module for block constants
_SYNC_PATH = Path(__file__).resolve().parent.parent / "tools" / "prawduct-sync.py"
_sync_spec = importlib.util.spec_from_file_location("prawduct_sync", _SYNC_PATH)
_sync_mod = importlib.util.module_from_spec(_sync_spec)
_sync_spec.loader.exec_module(_sync_mod)
BLOCK_BEGIN = _sync_mod.BLOCK_BEGIN
BLOCK_END = _sync_mod.BLOCK_END


def read_template(name: str) -> str:
    """Read a template file and return its content."""
    return (TEMPLATES_DIR / name).read_text()


def estimate_tokens(text: str) -> int:
    """Estimate token count using word-count heuristic.

    English text averages ~1.3 tokens per word. This is a rough estimate
    but sufficient for budget enforcement.
    """
    words = len(text.split())
    return int(words * 1.3)


# =============================================================================
# product-claude.md — Structure
# =============================================================================


class TestProductClaudeStructure:
    """Verify the structural requirements of the v5 CLAUDE.md template."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("product-claude.md")

    def test_has_block_markers(self, template: str):
        """Template must have PRAWDUCT:BEGIN and PRAWDUCT:END markers."""
        assert BLOCK_BEGIN in template
        assert BLOCK_END in template

    def test_block_markers_in_correct_order(self, template: str):
        """BEGIN must come before END."""
        begin_idx = template.index(BLOCK_BEGIN)
        end_idx = template.index(BLOCK_END)
        assert begin_idx < end_idx

    def test_has_product_name_placeholder(self, template: str):
        """Template must use {{PRODUCT_NAME}} placeholder."""
        assert "{{PRODUCT_NAME}}" in template

    def test_user_content_area_before_begin(self, template: str):
        """There should be space for user content before the PRAWDUCT block."""
        begin_idx = template.index(BLOCK_BEGIN)
        before = template[:begin_idx]
        assert "Add project-specific instructions" in before

    def test_user_content_area_after_end(self, template: str):
        """The END marker should be at or near the end, with space after for user content."""
        end_idx = template.index(BLOCK_END)
        after = template[end_idx + len(BLOCK_END):].strip()
        # After END marker, should be empty or minimal (user adds content here)
        assert len(after) == 0, f"Unexpected content after PRAWDUCT:END: {after[:100]}"


class TestProductClaudeTokenBudget:
    """Verify the v5 CLAUDE.md template stays within token budget."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("product-claude.md")

    def test_under_token_budget(self, template: str):
        """Prawduct block must be <2,800 tokens."""
        begin_idx = template.index(BLOCK_BEGIN)
        end_idx = template.index(BLOCK_END) + len(BLOCK_END)
        block = template[begin_idx:end_idx]
        tokens = estimate_tokens(block)
        assert tokens <= 2800, (
            f"CLAUDE.md Prawduct block is ~{tokens} tokens, budget is 2,800. "
            f"Compress prose or move content to methodology files."
        )

    def test_total_template_under_3500_tokens(self, template: str):
        """Total template (including comments outside block) should be reasonable."""
        tokens = estimate_tokens(template)
        assert tokens <= 3500, (
            f"Total template is ~{tokens} tokens. "
            f"Keep total including comments under 3,500."
        )


# =============================================================================
# product-claude.md — Content: Critical Rules (C2)
# =============================================================================


class TestProductClaudeCriticalRules:
    """Critical rules must be at the TOP of the template, before principles."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("product-claude.md")

    def test_critical_rules_section_exists(self, template: str):
        assert "## Critical Rules" in template

    def test_critical_rules_before_principles(self, template: str):
        """Critical rules must appear before principles section."""
        rules_idx = template.index("## Critical Rules")
        principles_idx = template.index("## Principles")
        assert rules_idx < principles_idx, (
            "Critical Rules section must appear before Principles section"
        )

    def test_never_weaken_test_rule(self, template: str):
        """The 'never weaken a test' rule must be in critical rules."""
        rules_section = template[
            template.index("## Critical Rules"):template.index("## Principles")
        ]
        assert "never weaken" in rules_section.lower()

    def test_never_drop_requirement_rule(self, template: str):
        """The 'never drop a requirement' rule must be in critical rules."""
        rules_section = template[
            template.index("## Critical Rules"):template.index("## Principles")
        ]
        assert "silently drop" in rules_section.lower()

    def test_never_swallow_exceptions_rule(self, template: str):
        """The 'never swallow exceptions' rule must be in critical rules."""
        rules_section = template[
            template.index("## Critical Rules"):template.index("## Principles")
        ]
        assert "swallow" in rules_section.lower() or "except" in rules_section.lower()

    def test_tests_alongside_code_rule(self, template: str):
        """The 'tests alongside code' rule must be in critical rules."""
        rules_section = template[
            template.index("## Critical Rules"):template.index("## Principles")
        ]
        assert "alongside" in rules_section.lower()

    def test_investigate_decisions_rule(self, template: str):
        """The 'investigate before committing' rule must be in critical rules."""
        rules_section = template[
            template.index("## Critical Rules"):template.index("## Principles")
        ]
        assert "investigate" in rules_section.lower()

    def test_boundary_check_rule(self, template: str):
        """The 'verify consumers when crossing boundaries' rule must be in critical rules."""
        rules_section = template[
            template.index("## Critical Rules"):template.index("## Principles")
        ]
        assert "boundar" in rules_section.lower()

    def test_update_artifacts_rule(self, template: str):
        """The 'update artifacts' rule must be in critical rules."""
        rules_section = template[
            template.index("## Critical Rules"):template.index("## Principles")
        ]
        assert "update artifacts" in rules_section.lower()

    def test_critic_after_medium_rule(self, template: str):
        """The 'Critic after medium+ work' rule must be in critical rules."""
        rules_section = template[
            template.index("## Critical Rules"):template.index("## Principles")
        ]
        assert "critic" in rules_section.lower()


# =============================================================================
# product-claude.md — Content: Work-Scaled Governance (C1)
# =============================================================================


class TestProductClaudeGovernanceModel:
    """Verify work-scaled governance model is present (C1)."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("product-claude.md")

    def test_no_phases_statement(self, template: str):
        """Template must state there are no phases."""
        assert "no phases" in template.lower() or "there are no phases" in template.lower()

    def test_work_size_levels(self, template: str):
        """All four work size levels must be described."""
        lower = template.lower()
        assert "trivial" in lower
        assert "small" in lower
        assert "medium" in lower
        assert "large" in lower

    def test_work_type_levels(self, template: str):
        """Key work types must be described."""
        lower = template.lower()
        assert "feature" in lower
        assert "bugfix" in lower
        assert "refactor" in lower
        assert "hotfix" in lower

    def test_governance_model_section_exists(self, template: str):
        """Must have a governance model section."""
        assert "## Governance Model" in template

    def test_no_current_phase_reference(self, template: str):
        """Template must not reference current_phase (v4 concept)."""
        assert "current_phase" not in template


# =============================================================================
# product-claude.md — Content: Investigated Changes (C3)
# =============================================================================


class TestProductClaudeInvestigatedChanges:
    """Verify investigated changes pattern is present (C3)."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("product-claude.md")

    def test_research_subagent_mentioned(self, template: str):
        """Research subagent pattern must be mentioned."""
        assert "research subagent" in template.lower() or "research sub" in template.lower()

    def test_boundary_patterns_reference(self, template: str):
        """Must reference boundary-patterns.md artifact."""
        assert "boundary-patterns" in template

    def test_lock_in_mentioned(self, template: str):
        """Lock-in as a decision property must be mentioned."""
        assert "lock-in" in template.lower()


# =============================================================================
# product-claude.md — Content: Active Context (C4)
# =============================================================================


class TestProductClaudeActiveContext:
    """Verify active context management is present (C4)."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("product-claude.md")

    def test_learning_lifecycle_mentioned(self, template: str):
        """Learning lifecycle (tiers) must be mentioned."""
        assert "active rules" in template.lower()
        assert "reference" in template.lower()
        assert "learnings-detail" in template.lower()

    def test_session_briefing_mentioned(self, template: str):
        """Session briefing must be referenced."""
        assert "session briefing" in template.lower()

    def test_subagent_briefing_mentioned(self, template: str):
        """Subagent briefing file must be referenced."""
        assert ".subagent-briefing.md" in template

    def test_token_budget_guidance(self, template: str):
        """Must mention keeping learnings under 3K tokens."""
        assert "3,000 tokens" in template or "3K tokens" in template


# =============================================================================
# product-claude.md — Content: Critic (preserved)
# =============================================================================


class TestProductClaudeCritic:
    """Verify Critic instructions are preserved and updated."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("product-claude.md")

    def test_critic_section_exists(self, template: str):
        assert "## The Critic" in template

    def test_critic_invocation_instructions(self, template: str):
        """Must include how to invoke the Critic."""
        assert "critic-review.md" in template
        assert "Task tool" in template or "separate agent" in template

    def test_critic_goal_based(self, template: str):
        """Critic description should mention goal-based scope, not fixed checklist."""
        critic_section = template[template.index("## The Critic"):]
        assert "goal" in critic_section.lower() or "signal" in critic_section.lower()

    def test_compact_instructions_section(self, template: str):
        """Compact instructions section must exist."""
        assert "## Compact Instructions" in template


# =============================================================================
# product-claude.md — Content: All 22 Principles Present
# =============================================================================


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
        """Each principle must appear in the template."""
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

    def test_no_current_phase_field(self, state: dict):
        """v5 removes current_phase."""
        assert "current_phase" not in state

    def test_has_work_in_progress(self, state: dict):
        """v5 adds work_in_progress section."""
        assert "work_in_progress" in state
        wip = state["work_in_progress"]
        assert "description" in wip
        assert "size" in wip
        assert "type" in wip

    def test_work_in_progress_starts_null(self, state: dict):
        """work_in_progress fields start as null."""
        wip = state["work_in_progress"]
        assert wip["description"] is None
        assert wip["size"] is None
        assert wip["type"] is None

    def test_has_health_check(self, state: dict):
        """v5 adds health_check section."""
        assert "health_check" in state
        hc = state["health_check"]
        assert "last_full_check" in hc
        assert "last_check_findings" in hc

    def test_health_check_starts_null(self, state: dict):
        """health_check fields start as null."""
        hc = state["health_check"]
        assert hc["last_full_check"] is None
        assert hc["last_check_findings"] is None

    # v4 fields preserved
    def test_has_classification(self, state: dict):
        assert "classification" in state

    def test_has_product_definition(self, state: dict):
        assert "product_definition" in state

    def test_has_technical_decisions(self, state: dict):
        assert "technical_decisions" in state

    def test_has_design_decisions(self, state: dict):
        assert "design_decisions" in state

    def test_has_open_questions(self, state: dict):
        assert "open_questions" in state

    def test_has_user_expertise(self, state: dict):
        assert "user_expertise" in state

    def test_has_build_preferences(self, state: dict):
        assert "build_preferences" in state

    def test_has_artifact_manifest(self, state: dict):
        assert "artifact_manifest" in state

    def test_has_build_plan(self, state: dict):
        assert "build_plan" in state

    def test_has_build_state(self, state: dict):
        assert "build_state" in state

    def test_has_change_log(self, state: dict):
        assert "change_log" in state

    def test_structural_characteristics_preserved(self, state: dict):
        """All 6 structural characteristics must still be present."""
        structural = state["classification"]["structural"]
        assert "has_human_interface" in structural
        assert "runs_unattended" in structural
        assert "exposes_programmatic_interface" in structural
        assert "has_multiple_party_types" in structural
        assert "handles_sensitive_data" in structural
        assert "multi_process_distributed" in structural

    def test_observability_approach_preserved(self, state: dict):
        """observability_approach must still be in design_decisions."""
        assert "observability_approach" in state["design_decisions"]

    def test_error_handling_approach_preserved(self, state: dict):
        """error_handling_approach must still be in design_decisions."""
        assert "error_handling_approach" in state["design_decisions"]


# =============================================================================
# project-state.yaml — Comments Preserved
# =============================================================================


class TestProjectStateComments:
    """Verify that project-state.yaml retains helpful comments."""

    @pytest.fixture
    def raw(self) -> str:
        return read_template("project-state.yaml")

    def test_has_header_comment(self, raw: str):
        """Template should have a descriptive header."""
        assert "{{PRODUCT_NAME}}" in raw

    def test_work_in_progress_has_comments(self, raw: str):
        """work_in_progress section should have explanatory comments."""
        assert "governance level" in raw.lower() or "work type" in raw.lower()

    def test_health_check_has_comments(self, raw: str):
        """health_check section should have explanatory comments."""
        assert "staleness" in raw.lower() or "health check" in raw.lower()


# =============================================================================
# critic-review.md — Goal-Based Structure (C1 + C3)
# =============================================================================


class TestCriticReviewGoalBased:
    """Verify critic-review.md uses goal-based scope, not fixed checklist."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("critic-review.md")

    def test_has_signals_section(self, template: str):
        """Must describe signals that guide review scope."""
        assert "signal" in template.lower()

    def test_has_work_size_guidance(self, template: str):
        """Must describe how work size affects review depth."""
        assert "trivial" in template.lower()
        assert "medium" in template.lower()
        assert "large" in template.lower()

    def test_has_work_type_guidance(self, template: str):
        """Must describe how work type affects review emphasis."""
        assert "feature" in template.lower()
        assert "bugfix" in template.lower()
        assert "refactor" in template.lower()

    def test_goals_not_fixed_checklist(self, template: str):
        """Should use goals, not numbered checks."""
        assert "## Review Goals" in template or "## Goals" in template
        # Should NOT have the v4-style named check sections
        assert "### Spec Compliance\n" not in template

    def test_goal_nothing_broken(self, template: str):
        """Must have a 'nothing is broken' goal."""
        assert "nothing is broken" in template.lower()

    def test_goal_nothing_missing(self, template: str):
        """Must have a 'nothing is missing' goal."""
        assert "nothing is missing" in template.lower()

    def test_goal_nothing_unintended(self, template: str):
        """Must have a 'nothing is unintended' goal."""
        assert "nothing is unintended" in template.lower()

    def test_goal_coherence(self, template: str):
        """Must have a coherence goal."""
        assert "coherent" in template.lower() or "coherence" in template.lower()

    def test_goal_deliberate_decisions(self, template: str):
        """Must check for deliberate decisions (C3)."""
        assert "deliberate" in template.lower() or "rationale" in template.lower()

    def test_bidirectional_freshness(self, template: str):
        """Must include bidirectional artifact freshness check."""
        assert "bidirectional" in template.lower()

    def test_boundary_check(self, template: str):
        """Must check for boundary investigation (C3)."""
        assert "boundary" in template.lower() or "contract" in template.lower()

    def test_exception_handling_check(self, template: str):
        """Must check for broad exception handling."""
        assert "exception" in template.lower()

    def test_severity_levels_preserved(self, template: str):
        """Must preserve blocking/warning/note severity levels."""
        assert "BLOCKING" in template
        assert "WARNING" in template
        assert "NOTE" in template

    def test_findings_json_format(self, template: str):
        """Must specify .critic-findings.json output format."""
        assert ".critic-findings.json" in template

    def test_independent_reviewer_statement(self, template: str):
        """Must state the Critic is independent."""
        assert "independent" in template.lower()

    def test_output_includes_signals(self, template: str):
        """Output format should include signals section."""
        assert "### Signals" in template

    def test_goal_design_is_sound(self, template: str):
        """Must have a 'design is sound' goal."""
        assert "design is sound" in template.lower()

    def test_has_security_checks(self, template: str):
        """Must include security review items."""
        assert "injection" in template.lower()
        assert "secret" in template.lower() or "credential" in template.lower()

    def test_has_documentation_drift(self, template: str):
        """Must check for documentation drift beyond artifacts."""
        assert "documentation drift" in template.lower()

    def test_has_design_details(self, template: str):
        """Must include encapsulation, coupling, simplification, deduplication."""
        assert "encapsulation" in template.lower()
        assert "coupling" in template.lower()

    def test_has_coordinator_pattern(self, template: str):
        """Must include coordinator pattern for parallel review."""
        assert "coordinator" in template.lower()

    def test_note_severity_is_ambiguous(self, template: str):
        """NOTE severity should indicate genuine ambiguity."""
        for line in template.split("\n"):
            if line.startswith("- **NOTE**"):
                assert "ambiguous" in line.lower() or "unsure" in line.lower() or "genuinely" in line.lower()
                break

    def test_project_preferences_blocking(self, template: str):
        """Project preferences violations should be BLOCKING."""
        for line in template.split("\n"):
            if "project-preferences" in line.lower() and "blocking" in line.lower():
                break
        else:
            pytest.fail("project-preferences compliance should be BLOCKING in product template")

    def test_readme_active_check(self, template: str):
        """Critic should actively check README."""
        assert "readme" in template.lower()

    def test_historical_records_immutable(self, template: str):
        """Historical records should not be flagged."""
        assert "historical" in template.lower() or "immutable" in template.lower()


# =============================================================================
# boundary-patterns.md — Template Structure
# =============================================================================


class TestBoundaryPatternsTemplate:
    """Verify boundary-patterns.md template structure."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("boundary-patterns.md")

    def test_has_product_name_placeholder(self, template: str):
        assert "{{PRODUCT_NAME}}" in template

    def test_has_contract_surfaces_section(self, template: str):
        assert "## Contract Surfaces" in template

    def test_has_api_endpoints_section(self, template: str):
        assert "### API Endpoints" in template

    def test_has_database_schemas_section(self, template: str):
        assert "### Database Schemas" in template

    def test_has_ipc_section(self, template: str):
        assert "### Inter-Process Communication" in template

    def test_has_frontend_backend_section(self, template: str):
        assert "### Frontend/Backend" in template

    def test_has_configuration_section(self, template: str):
        assert "### Configuration" in template

    def test_has_test_levels_section(self, template: str):
        assert "## Test Levels" in template

    def test_test_levels_table(self, template: str):
        """Test levels table should include all four tiers."""
        assert "Unit" in template
        assert "Integration" in template
        assert "Contract" in template
        assert "End-to-end" in template

    def test_has_html_comments_with_guidance(self, template: str):
        """Template should have HTML comments with fill-in guidance."""
        assert "<!-- " in template
        assert "Example:" in template


# =============================================================================
# Cross-Template Consistency
# =============================================================================


class TestCrossTemplateConsistency:
    """Verify templates reference each other correctly."""

    def test_claude_references_critic_review(self):
        """CLAUDE.md must reference critic-review.md."""
        template = read_template("product-claude.md")
        assert "critic-review.md" in template

    def test_claude_references_boundary_patterns(self):
        """CLAUDE.md must reference boundary-patterns.md."""
        template = read_template("product-claude.md")
        assert "boundary-patterns" in template

    def test_claude_references_subagent_briefing(self):
        """CLAUDE.md must reference .subagent-briefing.md."""
        template = read_template("product-claude.md")
        assert ".subagent-briefing.md" in template

    def test_claude_references_learnings_detail(self):
        """CLAUDE.md must reference learnings-detail.md."""
        template = read_template("product-claude.md")
        assert "learnings-detail" in template

    def test_claude_references_project_preferences(self):
        """CLAUDE.md must reference project-preferences.md."""
        template = read_template("product-claude.md")
        assert "project-preferences" in template

    def test_critic_references_boundary_patterns(self):
        """critic-review.md must reference boundary-patterns.md."""
        template = read_template("critic-review.md")
        assert "boundary-patterns" in template

    def test_critic_references_project_preferences(self):
        """critic-review.md must reference project-preferences.md."""
        template = read_template("critic-review.md")
        assert "project-preferences" in template

    def test_critic_references_findings_json(self):
        """critic-review.md must reference .critic-findings.json."""
        template = read_template("critic-review.md")
        assert ".critic-findings.json" in template

    def test_claude_methodology_self_contained(self):
        """Product CLAUDE.md must NOT reference framework methodology files (products are self-contained)."""
        template = read_template("product-claude.md")
        assert "methodology/discovery.md" not in template
        assert "methodology/planning.md" not in template
        assert "methodology/building.md" not in template
        assert "methodology/reflection.md" not in template
