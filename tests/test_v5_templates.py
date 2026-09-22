"""Tests for the surviving template content + the plugin skills that the retired
file-sync mirror-templates used to validate.

After M4 Chunk 4 retired the file-sync product templates (``product-claude.md``,
``critic-review.md``, ``build-governance.md``, the ``skill-*.md``, ``conftest.py``),
the content those mirror-tests guarded is now checked against its plugin
source-of-truth elsewhere:
  - methodology content (principles, governance model, critic goals/severity/PBT)
    → ``test_v5_methodology.py`` (``TestBuildingMethodology`` / ``TestCriticSkill`` /
    ``TestMethodologyPBT``) plus the always-injected session digest
    (``test_plugin_methodology_digest.py``);
  - ``skills/critic/review-protocol.md`` → retargeted in this file. (The learnings
    lookup skill it sat beside was deleted with the rest of the lookup path: rules
    are ``.claude/rules/`` files the harness loads, so nothing reads them for you.)

What remains here validates the place-once / planning templates that
``init_product`` still renders or that planning authors scaffold from
(project-state.yaml, backlog.md, boundary-patterns.md, test-specifications.md,
project-preferences.md).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

FRAMEWORK_DIR = Path(__file__).resolve().parent.parent / "plugin"
TEMPLATES_DIR = FRAMEWORK_DIR / "templates"


def read_template(name: str) -> str:
    """Read a template file and return its content."""
    return (TEMPLATES_DIR / name).read_text()


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

    def test_api_decision_fields(self, state: dict, raw: str):
        """api-design adds the recorded API decisions under design_decisions, and
        the api_versioning_decided answer-store fact stays commented-out (absent
        live, documented in a comment) per the resolution-fact convention."""
        dd = state["design_decisions"]
        assert dd["api_versioning_approach"] is None
        assert dd["api_error_model_approach"] is None
        assert "api_versioning_decided" not in state   # commented-out, not a live key
        assert "api_versioning_decided" in raw         # documented in a comment

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

    def test_backlog_resolution_fields_documented(self, raw: str):
        """v1.7 backlog resolution-condition fields are documented (commented,
        unset by default — absent means legacy/unmigrated)."""
        for field in ["backlog_format_version", "backlog_prefixes",
                      "backlog_external_imports", "backlog_last_groomed_at"]:
            assert field in raw, f"backlog field '{field}' not documented in template"
        # Shipped commented (default = unset = legacy), so YAML must not load them.
        loaded = yaml.safe_load(raw)
        assert "backlog_format_version" not in loaded


# =============================================================================
# backlog.md — Structured format (v1.7+)
# =============================================================================


class TestBacklogTemplate:
    """Verify the v1.7 structured-backlog place-once template."""

    @pytest.fixture
    def raw(self) -> str:
        return read_template("backlog.md")

    def test_three_sections(self, raw: str):
        """Open / Promoted / Archive sections in order."""
        i_open = raw.index("## Open")
        i_promoted = raw.index("## Promoted")
        i_archive = raw.index("## Archive")
        assert i_open < i_promoted < i_archive

    def test_title_and_placeholder(self, raw: str):
        """Backlog title carries the product-name placeholder."""
        assert "# Backlog — {{PRODUCT_NAME}}" in raw
        assert "Backlog" in raw  # /backlog validate check

    def test_id_and_metadata_spec(self, raw: str):
        """Item-shape spec documents the [PFX-XXXX] id and metadata bar fields."""
        assert "[PFX-XXXX]" in raw
        for field in ["effort:", "impact:", "area:", "source:", "added:", "status:"]:
            assert field in raw, f"metadata field '{field}' not documented"

    def test_legacy_items_remain_valid(self, raw: str):
        """Template states legacy (unmetadata'd) items stay valid — D5."""
        assert "Legacy items" in raw or "legacy" in raw.lower()


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
# build-plan.md — Filled-example template (prose-diet Chunk 01)
# =============================================================================


class TestBuildPlanTemplate:
    """The build-plan template is a FILLED EXAMPLE, not a placeholder skeleton.

    The prose-diet rewrite (MET-3Q8V Chunk 01, pre-delivering MET-2X6F) replaced
    ~200 bracketed placeholders with a realistic small product so plan authors
    copy working shapes instead of decoding field comments. Guard the two
    properties that rewrite established."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("build-plan.md")

    def test_chunk_01_is_filled(self, template: str):
        """`### Chunk 01:` exists and its heading carries real content, not a
        `[Name]`-style bracket placeholder."""
        idx = template.index("### Chunk 01:")
        heading = template[idx:].split("\n", 1)[0]
        rest = heading[len("### Chunk 01:"):].strip()
        assert rest, "Chunk 01 heading is empty"
        assert not rest.startswith("["), f"Chunk 01 heading is a placeholder: {heading!r}"

    def test_no_parser_bug_narrative(self, template: str):
        """The v1.5.1 `_detect_active_scope` caveat story must not ride inside
        the starter template (implementation narration ≠ template guidance)."""
        assert "_detect_active_scope" not in template

    def test_no_acceptance_criterion_names_a_test_runner(self, template: str):
        """The example must read the same for a Swift, C#, JS or Python product.

        Bounded by the PROPERTY, not by a location: every
        `**Acceptance criteria:**` line, wherever it sits, because an acceptance
        criterion is the chunk's own bar and a runner named there is a bar in
        one ecosystem's vocabulary. The Scaffolding section is deliberately NOT
        in scope — that is where the example product DECLARES its suite, which
        is the thing "the declared suite passes" then refers to; a check that
        banned the name there would be banning the declaration.

        Paired with a positive: the criterion still names a suite bar at all,
        because deleting the clause passes any negative test.
        """
        criteria = [
            ln for ln in template.splitlines()
            if ln.strip().startswith("- **Acceptance criteria:**")
        ]
        assert criteria, "no acceptance-criteria lines found — the check read nothing"
        runners = re.compile(
            r"\b(pytest|uv run|npm (?:test|run)|yarn|jest|vitest|cargo test|go test"
            r"|swift test|dotnet test|gradle|mvn|rspec|phpunit)\b",
            re.I,
        )
        for line in criteria:
            hit = runners.search(line)
            assert not hit, (
                f"an acceptance criterion names the runner {hit.group(0)!r}: "
                f"{line.strip()!r} — say \"the declared suite passes\" instead, "
                "so the example reads the same in every toolchain"
            )
        assert any("the declared suite passes" in ln for ln in criteria), (
            "no acceptance criterion states a suite bar at all — the "
            "language-neutral rewrite must not become a deletion"
        )

    def test_the_short_plan_rule_is_pointed_at_from_the_chunk_fields(self, template: str):
        """The rule has ONE canonical statement; the template points at it.

        Both places a plan author decides review frequency — the chunk-field
        reference that governs every "Done when", and the `cumulative-final`
        worked example — name `review-cycle.md`'s row rather than restating the
        conditions. The conditions are asserted absent on the exact predicates
        that carry them.

        The example plan itself is NOT short-plan eligible (Chunk 02 declares a
        `Critic mode:`), and the template says so — a worked example that
        silently contradicted the rule it points at would teach the wrong
        reading.
        """
        row = '"When Review Is Required"'
        fields = template.split("## Build Chunks", 1)
        assert len(fields) == 2, "the Build Chunks section is gone"
        fields = fields[1].split("### Chunk 01:", 1)[0]
        assert row in fields, (
            "the chunk-field reference no longer points at the short-plan rule, "
            "so a plan author reads \"Done when\" as one review per chunk"
        )
        cumulative = template.split("- **Type:** cumulative-final", 1)
        assert len(cumulative) == 2, "the cumulative-final example is gone"
        cumulative = cumulative[1].split("- **Foreign API:**", 1)[0]
        assert row in cumulative, (
            "the cumulative-final example does not reach the short-plan rule"
        )
        assert "Chunk 02 declares a `Critic mode:`" in cumulative, (
            "the example no longer says why the short-plan rule does not apply "
            "to it — a reader takes the pointer as describing this plan"
        )
        for restated in ("at most 3 chunks", "no risk surface"):
            assert restated not in template, (
                f"the template restates the short-plan condition ({restated!r}) "
                "instead of pointing at it"
            )

    def test_pinned_field_labels_survive(self, template: str):
        """Field labels the Critic substring-matches stay string-identical."""
        for label in [
            "**Description:**", "**Depends on:**", "**Deliverables:**",
            "**Tests:**", "**Acceptance criteria:**", "**Done when:**",
            "**Critic mode:**", "**Type:**", "**Foreign API:**",
            "**Visual change:**", "**Level:**",
            "**Open assumptions / unknowns:**",
        ]:
            assert label in template, f"field label {label} missing from template"


# =============================================================================
# Critic skill — PBT check (plugin source-of-truth)
# =============================================================================


class TestCriticSkillPBT:
    """Verify framework Critic review-protocol includes PBT check."""

    @pytest.fixture
    def skill(self) -> str:
        return (FRAMEWORK_DIR / "skills" / "critic" / "review-protocol.md").read_text()

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


# =============================================================================
# Place-Once Templates — PBT Content
# =============================================================================


class TestTestSpecificationsPBT:
    """Verify test-specifications.md template includes property-based testing."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("test-specifications.md")

    def test_the_testing_floor_is_a_product_floor_not_a_per_chunk_bar(self, template: str):
        """Why a reviewer was reading "one E2E per core flow" as a chunk bar.

        Asserted INSIDE the testing-floor block, bounded by the next risk-tier
        heading: the qualification only does its job where the floor is stated,
        and a whole-file search would pass on the same words parked anywhere.
        Paired positively — the floor's own bullets must survive, since
        deleting them would also stop the misreading.
        """
        floor = template.split("**Testing floor (all products):**", 1)
        assert len(floor) == 2, "the testing floor block is gone"
        floor = floor[1].split("**Low-risk:**", 1)[0]
        assert "At least one E2E test per core flow" in floor, (
            "the floor lost the bullet this qualification is about"
        )
        assert "PRODUCT floor" in floor, (
            "the floor no longer says whose floor it is, so a reviewer reads it "
            "as a per-chunk bar again"
        )
        assert "never a per-chunk bar" in floor, (
            "the qualification dropped the reading it exists to refuse"
        )
        assert "the tests that prove its" in floor, (
            "nothing says what a chunk DOES owe, which leaves the reviewer no "
            "bar at all instead of the right one"
        )

    def test_pbt_section_exists(self, template: str):
        """Property-Based Tests section present between Edge Cases and State Transitions."""
        assert "## Property-Based Tests" in template
        edge_pos = template.index("Edge Cases")
        pbt_pos = template.index("## Property-Based Tests")
        state_pos = template.index("## State Transition Tests")
        assert edge_pos < pbt_pos < state_pos

    def test_pbt_section_has_guidance(self, template: str):
        """PBT section explains when to include and common property types."""
        pbt_start = template.index("## Property-Based Tests")
        state_start = template.index("## State Transition Tests")
        pbt_section = template[pbt_start:state_start].lower()
        assert "round-trip" in pbt_section
        assert "invariant" in pbt_section
        assert "equivalence" in pbt_section

    def test_pbt_section_has_format(self, template: str):
        """PBT section includes the property definition format."""
        pbt_start = template.index("## Property-Based Tests")
        state_start = template.index("## State Transition Tests")
        pbt_section = template[pbt_start:state_start]
        assert "**Property:" in pbt_section
        assert "Strategy:" in pbt_section

    def test_pbt_is_conditional(self, template: str):
        """PBT section explains when to skip (CRUD, UI-only)."""
        pbt_start = template.index("## Property-Based Tests")
        state_start = template.index("## State Transition Tests")
        pbt_section = template[pbt_start:state_start].lower()
        assert "skip" in pbt_section or "not applicable" in pbt_section


class TestProjectPreferencesPBT:
    """Verify project-preferences.md template includes testing strategies field."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("project-preferences.md")

    def test_testing_strategies_field(self, template: str):
        """Testing strategies field present in the Testing section."""
        assert "Testing strategies" in template

    def test_testing_strategies_between_coverage_and_location(self, template: str):
        """Testing strategies field positioned between coverage and test location."""
        coverage_pos = template.index("Coverage expectations")
        strategies_pos = template.index("Testing strategies")
        location_pos = template.index("Test location")
        assert coverage_pos < strategies_pos < location_pos

    def test_testing_strategies_has_examples(self, template: str):
        """Testing strategies field includes PBT library examples."""
        for line in template.split("\n"):
            if "Testing strategies" in line:
                lower = line.lower()
                assert "hypothesis" in lower or "proptest" in lower
                break


# =============================================================================
# api-contract.md — the artifact for a product's OWN exposed API (api-design)
# =============================================================================


class TestApiContractTemplate:
    """Guards the api-contract artifact template: the three recorded decisions,
    transport-agnostic framing (NOT HTTP-only), and the surfaced breadth."""

    def setup_method(self):
        self.content = read_template("api-contract.md")

    def test_frontmatter(self):
        assert "artifact: api-contract" in self.content

    def test_gated_decisions_present(self):
        # The three recorded decisions the Critic and advisory track.
        assert "## Versioning" in self.content
        assert "## Error Model" in self.content
        assert "Deprecation" in self.content
        # Mirrored into project-state design_decisions.
        assert "api_versioning_approach" in self.content
        assert "api_error_model_approach" in self.content

    def test_force_the_decision_not_mandate(self):
        # Stance: a recorded "none — internal-only" / dated deferral satisfies it.
        assert "internal-only" in self.content
        assert "deferral" in self.content.lower()

    def test_transport_agnostic_not_http_only(self):
        # Must cover non-network surfaces, not just HTTP/REST (do not regress).
        lower = self.content.lower()
        assert "library" in lower and "sdk" in lower
        assert "cli" in lower
        assert "on-device" in lower or "platform" in lower
        assert "not just an http" in lower or "don't assume http" in lower
        # ...while still naming the network protocols as examples.
        for proto in ["REST", "GraphQL", "gRPC"]:
            assert proto in self.content

    def test_surfaced_breadth(self):
        # Breadth carried as prose, not gates.
        assert "OWASP" in self.content and "BOLA" in self.content  # API-specific security
        assert "stability" in self.content.lower()                  # surface inventory / tiers
        assert "ISO-8601" in self.content                           # wire conventions
        assert "tolerant reader" in self.content.lower()            # evolution rules
