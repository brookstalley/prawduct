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
  - ``skills/learnings/SKILL.md`` and ``skills/critic/review-protocol.md`` → retargeted
    in this file.

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
# /learnings skill — Structure (plugin source-of-truth)
# =============================================================================


class TestLearningsSkill:
    """Verify the plugin /learnings skill has required structure.

    Retargeted from the retired file-sync `templates/skill-learnings.md` to the
    plugin's `skills/learnings/SKILL.md` (M4 Chunk 4)."""

    @pytest.fixture
    def skill(self) -> str:
        return (FRAMEWORK_DIR / "skills" / "learnings" / "SKILL.md").read_text()

    def test_frontmatter_and_references(self, skill: str):
        """Has required frontmatter and references all knowledge files."""
        assert "description:" in skill
        assert "argument-hint:" in skill
        assert "disable-model-invocation:" in skill
        assert "learnings.md" in skill
        assert "learnings-detail.md" in skill
        assert "project-preferences.md" in skill

    def test_behavior(self, skill: str):
        """Has subagent instructions, no-args mode, read-only, token budget."""
        assert "subagent" in skill.lower() or "Agent tool" in skill
        assert "no topic" in skill.lower() or "no topic was provided" in skill.lower()
        assert "read-only" in skill.lower()
        assert "500 tokens" in skill


# =============================================================================
# Place-Once Templates — PBT Content
# =============================================================================


class TestTestSpecificationsPBT:
    """Verify test-specifications.md template includes property-based testing."""

    @pytest.fixture
    def template(self) -> str:
        return read_template("test-specifications.md")

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


# =============================================================================
# docs/upstream-dependency-policy.md — the canonical intake spec
# =============================================================================

#: Ecosystem, tool, and manifest-filename tokens. The list is the FORM-FAMILY of
#: "phrased in terms of a named ecosystem", not one spelling of it: package
#: managers and registries, the two update bots, and — the case that matters most
#: — manifest and lockfile names. Naming manifest filenames is precisely the
#: allowlist trap the requirements reject (an allowlist under-enumerates package
#: managers, and mistakes "package manager" for "delivery mechanism"), so a clause
#: that reached for `package.json` would be the defect even though no tool is named.
#:
#: Tokens whose bare form collides with ordinary English are spelled at their
#: qualified form instead — `go.mod`/`go modules` not `go`, `pub.dev` not `pub`,
#: `hex.pm` not `hex`. A guard that fires on the word "go" gets deleted the first
#: time it cries wolf, and then guards nothing.
_ECOSYSTEM_TOKENS = (
    # Package managers and registries
    "npm", "pnpm", "yarn", "bun", "deno", "PyPI", "pip", "uv", "poetry", "PDM",
    "pipenv", "pixi", "conda", "cargo", "crates.io", "maven", "gradle", "nuget",
    "composer", "packagist", "rubygems", "bundler", "cocoapods", "swiftpm",
    "homebrew", "nix", "cpan", "hex.pm", "pub.dev", "go.mod", "go modules",
    # Update bots
    "dependabot", "renovate", "snyk",
    # Manifests and lockfiles
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "pyproject.toml", "requirements.txt", "uv.lock", "Gemfile", "Cargo.toml",
    "pom.xml", "build.gradle", "composer.json", "mix.exs", "go.sum",
)

_ECOSYSTEM_RE = re.compile(
    r"\b(?:"
    + "|".join(re.escape(t) for t in sorted(_ECOSYSTEM_TOKENS, key=len, reverse=True))
    + r")\b",
    re.IGNORECASE,
)

#: The normative body ends where the appendix begins. Keyed on the NON-NORMATIVE
#: marker rather than the word "Appendix" alone, so an appendix that loses its
#: marker does not silently widen the scanned region — it fails
#: ``test_the_mapping_appendix_is_marked_non_normative`` first.
_APPENDIX_RE = re.compile(r"^##\s+Appendix\b[^\n]*NON-NORMATIVE", re.MULTILINE)

_POLICY_SPEC = "upstream-dependency-policy.md"


def read_doc(name: str) -> str:
    """Read a shipped ``plugin/docs/`` spec file."""
    return (FRAMEWORK_DIR / "docs" / name).read_text(encoding="utf-8")


def read_file_under_plugin(rel_path: str) -> str:
    """Read any shipped plugin file by its plugin-relative path."""
    return (FRAMEWORK_DIR / rel_path).read_text(encoding="utf-8")


def extract_section(text: str, heading: str) -> str:
    """Return one section, from its heading to the next heading of the same or a
    higher level (or EOF).

    Anchored at LINE START, which is load-bearing rather than fussy: prose
    routinely *names* a heading mid-sentence — this template's own Direction
    comment says "the `## Upstream Dependencies` section below" — and a plain
    ``str.index`` binds to that mention instead, silently scanning a region that
    starts in the wrong place. The bug is invisible because the wrong region
    usually still contains the right text, so every assertion keeps passing.

    The terminator is derived from the heading's own level rather than fixed at
    ``## ``, because the surfaces differ: ``goals-1-3.md`` puts each goal at
    ``## `` while ``review-protocol.md`` nests them under ``### ``. A fixed
    ``## `` terminator would run a ``### `` section on through its five
    siblings, which is the same silently-widened region this docstring's first
    paragraph is about — the scan would then be reporting on prose the surface
    does not own.
    """
    match = re.search(rf"^{re.escape(heading)}\s*$", text, re.MULTILINE)
    assert match, f"section {heading!r} not found as a heading"
    level = len(heading) - len(heading.lstrip("#"))
    assert level, f"{heading!r} is not a markdown heading"
    rest = text[match.end():]
    nxt = re.search(rf"^#{{1,{level}}} ", rest, re.MULTILINE)
    return heading + (rest[: nxt.start()] if nxt else rest)


#: Every surface that STATES the intake policy to a reader, paired with the
#: section that does the stating. The spec is the home; these cite it.
#:
#: Requirement 1 of the appendix binds "no policy statement, gate, or check",
#: which is broader than the spec file alone — so the guards below sweep every
#: surface that exists today rather than only the one this chunk created. The
#: doctor check, the janitor theme and the advisory probe each joined as they
#: landed.
#:
#: The two Critic entries are the "gate, or check" arm of that requirement: the
#: Goal 2 bullet is what actually enforces the policy, and it exists twice
#: because the two files are the two roster paths (`goals-1-3.md` serves
#: `chunk`/`verify-resolutions`, `review-protocol.md` serves
#: `final`/`cumulative`). A guard on one of them would leave the check's wording
#: free to drift in whichever mode was not swept.
#:
#: NOT here, deliberately, and each for a different reason:
#:
#: * `templates/build-plan.md`'s `**Dependency change:**` field. That is the
#:   author's *declaration* that trips the check, not a statement of the policy
#:   or a check on it — the same reason the `**Exposed API:**` field is not a
#:   surface of the versioning decision. It is still written ecosystem-neutrally;
#:   nothing but this note stops a later editor reading its absence as an
#:   oversight.
#: * `docs/doctor-vs-janitor.md`'s "legitimately both" entry. It describes what
#:   the two checks each ask; it neither states the policy nor enforces it, and
#:   it cites the spec as a *sibling* path (both files live in `docs/`), which
#:   `test_every_policy_surface_cites_the_spec` — which asserts the `docs/`
#:   prefix a reader elsewhere in the plugin needs — would fail for a reason that
#:   has nothing to do with the property being guarded.
#:
#: The third element is the scope the two NEGATIVE guards police:
#:
#: ``section`` — a DEDICATED policy section, where every line states the policy,
#:   so scanning the whole region is exactly right.
#: ``bullet``  — the policy is ONE bullet (or one long numbered check) inside a
#:   general-purpose section. Only the declaring line(s) are scanned, because the
#:   rest of that section is unrelated prose a future author may legitimately
#:   write with a manifest name or an interval in days in it — and the Critic
#:   protocol is the likeliest place in the plugin for exactly such an
#:   illustration. Scanning the whole Goal 2 section would fail that edit with a
#:   message claiming it restated the policy, and the next author would either
#:   weaken the guard or contort the prose. The doctor and janitor surfaces sit
#:   in general-purpose files too — one numbered governance check inside a flow
#:   of them, one maintenance theme inside a list of them — so they take
#:   ``bullet`` as well.
#: ``module``  — the surface is not markdown and has no heading to anchor on, so
#:   the FILE is the region and its second element is ``None``. The advisory
#:   probe is the case: what it states to a reader is a handful of Python string
#:   literals plus the docstring that says why it has no detector, and those are
#:   read in every session briefing of every product — the widest-read statement
#:   of this policy anywhere in the plugin. Scanning the whole file is honest
#:   only because the file exists for nothing else, which is exactly what the
#:   scope test below insists on.
#:
#: Which of the three applies is not left to taste: see
#: ``test_the_declared_scope_follows_whether_the_region_is_dedicated``.
_POLICY_SURFACES = (
    ("methodology/discovery.md", "## Surface Upstream Dependency Policy", "section"),
    ("templates/security-model.md", "## Upstream Dependencies", "section"),
    ("skills/critic/review-protocol.md", "### 2. Nothing Is Missing", "bullet"),
    ("skills/critic/goals-1-3.md", "## 2. Nothing Is Missing", "bullet"),
    ("skills/doctor/SKILL.md", "## Health Check Flow (current dir is a product repo)", "bullet"),
    ("skills/janitor/SKILL.md", "### Dependency Health", "bullet"),
    ("lib/dependency_policy_probes.py", None, "module"),
)


def surface_region(rel_path: str, heading: str | None, scope: str) -> str:
    """The whole region a surface owns, before the negative guards narrow it.

    Markdown surfaces own one section; a ``module`` surface owns its whole file.
    Split out from :func:`policed_text` because the citation guard asks about the
    region and the negative guards ask about the policed subset of it, and the
    two questions were drifting apart in a single function.
    """
    text = read_file_under_plugin(rel_path)
    if scope == "module":
        return text
    return extract_section(text, heading)


def policed_text(rel_path: str, heading: str | None, scope: str) -> str:
    """The region the negative guards scan, per the surface's declared scope.

    For ``bullet`` scope the declaring lines are found by their citation of the
    spec, and their absence is an assertion rather than an empty scan: a
    parametrized guard over zero text passes and proves nothing, which is the
    same failure ``test_the_sweep_covers_the_surfaces_that_exist`` exists to
    prevent one level up.
    """
    region = surface_region(rel_path, heading, scope)
    if scope in ("section", "module"):
        return region
    assert scope == "bullet", f"unknown surface scope {scope!r}"
    declaring = [line for line in region.split("\n") if _POLICY_SPEC in line]
    assert declaring, (
        f"{rel_path}'s {heading!r} carries no line citing {_POLICY_SPEC} — the "
        "negative guards would scan nothing and pass vacuously"
    )
    return "\n".join(declaring)


class TestUpstreamDependencyPolicySpec:
    """Guards the canonical intake spec: the governing sentence, the six clauses,
    the three tiers, and — the load-bearing one — that no normative statement is
    phrased in terms of a named ecosystem.

    The agnosticism guard is what makes the governing sentence *enforceable*
    rather than aspirational. Without it, "this policy is about dependencies, not
    package managers" is a sentence anyone can contradict two paragraphs later.
    """

    def setup_method(self):
        self.content = read_doc(_POLICY_SPEC)
        #: Whitespace-normalized. Every prose assertion below runs against this,
        #: because these files are hard-wrapped: a phrase that reads as one
        #: sentence is routinely split across a newline plus indentation, and a
        #: raw substring check then fails for a reason that has nothing to do
        #: with the property it is guarding. The line-numbered scans keep using
        #: the raw text — they report positions.
        self.flat = " ".join(self.content.split())

    def test_states_the_governing_sentence(self):
        # The one sentence every other rule in the file answers to.
        assert "dependencies, not package managers" in self.flat
        # ...and the reason it is not merely a slogan: the delivery mechanism is
        # what varies, so the scope is defined by who controls the release.
        assert "independent of delivery mechanism" in self.flat

    def test_names_the_non_manifest_intake_surfaces(self):
        """The governing sentence is only meaningful if the file shows what it
        excludes an allowlist from missing. CI actions are the sharpest case —
        upstream code running with the repository's credentials, in no manifest."""
        lower = self.flat.lower()
        for surface in ("base image", "ci action", "submodule", "vendored", "model weight"):
            assert surface in lower, f"the spec stopped naming {surface!r} as an intake surface"

    def test_all_six_clauses_are_stated(self):
        for n in range(1, 7):
            assert f"**Clause {n} —" in self.flat, f"clause {n} is missing"

    def test_the_three_enforcement_tiers_and_their_rules(self):
        for tier in ("1 — Declarative", "2 — Bot", "3 — Agent-mediated"):
            assert tier in self.flat, f"tier {tier!r} is missing"
        lower = self.flat.lower()
        # Rule 2 is the honesty rule: record the tier REACHED, never assume it.
        assert "record the tier actually reached" in lower
        # Rule 3 keeps tier 3 from reading as a consolation prize.
        assert "not a consolation prize" in lower

    def test_the_mapping_appendix_is_marked_non_normative(self):
        """A mapping table WILL go stale. It is only safe to ship if a reader
        cannot mistake it for the policy."""
        assert _APPENDIX_RE.search(self.content), (
            "the mapping appendix must carry an explicit NON-NORMATIVE marker in "
            "its heading — the agnosticism guard's scan boundary keys on it"
        )
        assert "This appendix is non-normative" in self.flat

    def test_the_appendix_carries_its_three_consequences(self):
        """The three requirements that make a stale table harmless."""
        lower = self.flat.lower()
        assert "may be phrased in terms of a named ecosystem" in lower
        assert "absent from this table is fully covered" in lower
        assert "documentation defect, never a coverage gap" in lower

    # -- the agnosticism guard ------------------------------------------------

    def test_no_normative_statement_names_an_ecosystem(self):
        """THE guard. Every policy statement above the appendix must be stated in
        terms of dependencies, never of a named toolchain or manifest file."""
        match = _APPENDIX_RE.search(self.content)
        assert match, "cannot scope the guard without the appendix marker"
        normative = self.content[: match.start()]

        offenders = []
        for line_num, line in enumerate(normative.splitlines(), start=1):
            for hit in _ECOSYSTEM_RE.finditer(line):
                offenders.append(f"  line {line_num}: {hit.group(0)!r} in {line.strip()[:90]!r}")
        assert not offenders, (
            "a normative statement in docs/" + _POLICY_SPEC + " names an ecosystem. "
            "The policy governs dependencies, not package managers; move the naming "
            "into the non-normative appendix:\n" + "\n".join(offenders)
        )

    def test_the_agnosticism_guard_is_not_vacuous(self):
        """Green above must mean *the property holds*, not *the regex is broken*.

        The same detector, run over the same file's appendix, must fire — and fire
        on several distinct tokens. This is the check that would have caught a
        typo'd character class or a `\\b` that never matches.
        """
        match = _APPENDIX_RE.search(self.content)
        assert match
        appendix = self.content[match.start():]
        found = {hit.group(0).lower() for hit in _ECOSYSTEM_RE.finditer(appendix)}
        assert len(found) >= 5, (
            "the detector found fewer than 5 distinct ecosystem names in the very "
            f"appendix that exists to name them (found: {sorted(found)}) — the scan "
            "over the normative body cannot be trusted"
        )

    @pytest.mark.parametrize(
        "planted",
        [
            # Deliberately DIFFERENT phrasings from anything in the file today —
            # a guard verified red only against the wording that prompted it is a
            # copy of that wording, not a check on the property.
            "**Clause 1 — Minimum release age.** Set `minimumReleaseAge` to 7 in pnpm.",
            "Adding a dependency means editing package.json and committing the lockfile.",
            "The update bot must be Renovate, configured with a cooldown.",
            "For Python products, pin with uv.lock; Gemfile.lock is the equivalent elsewhere.",
            "Tier 1 is only reachable where Cargo.toml or pyproject.toml can express it.",
        ],
    )
    def test_the_agnosticism_guard_is_red_on_a_planted_statement(self, planted):
        assert _ECOSYSTEM_RE.search(planted), (
            f"the detector missed a named ecosystem in {planted!r} — it would not "
            "have caught this clause being rewritten"
        )

    @pytest.mark.parametrize(
        "benign",
        [
            # Prose that TALKS ABOUT the rule, or states the policy correctly,
            # must not trip it. A guard that cannot tell a prohibition from an
            # instance gets deleted the first time it cries wolf.
            "This policy is about dependencies, not package managers.",
            "An upstream release is not adopted until it has been publicly available.",
            "No policy statement may be phrased in terms of a named ecosystem.",
            "Prefer the strongest tier the ecosystem allows.",
            "Upstream code is not granted arbitrary execution at install time.",
            "The resolved dependency set is committed and authoritative.",
            "Go ahead and record the tier reached for each intake surface.",
        ],
    )
    def test_the_agnosticism_guard_ignores_correct_policy_prose(self, benign):
        hit = _ECOSYSTEM_RE.search(benign)
        assert not hit, (
            f"the detector fired on {hit.group(0)!r} in correct policy prose: {benign!r}"
        )


class TestSecurityModelUpstreamDependencies:
    """The product-facing home: the template must POINT at the spec and tell the
    author what belongs *here*, never carry a second copy of the clauses.

    `architecture.md`'s *every fact has one home* norm is the live constraint —
    "a reader who can act on your text without following the pointer is holding a
    copy." These tests are that norm made mechanical for this one pair of files.
    """

    def setup_method(self):
        self.content = read_template("security-model.md")
        self.section = extract_section(self.content, "## Upstream Dependencies")
        # Hard-wrapped prose — see the note in TestUpstreamDependencyPolicySpec.
        self.flat = " ".join(self.section.split())

    def test_points_at_the_canonical_spec(self):
        assert f"docs/{_POLICY_SPEC}" in self.flat, (
            "the section must cite the canonical spec — it is the only home for "
            "the clauses, the tiers, and the mapping"
        )

    def test_tells_the_author_not_to_restate_the_clauses(self):
        assert "Do NOT restate them here" in self.flat

    def test_does_not_carry_a_second_copy_of_the_clauses(self):
        """The enumeration itself is the thing that must not be duplicated."""
        assert "Clause 1" not in self.flat and "Clause 2" not in self.flat

    # The numeric-default guard that used to sit here is gone, not weakened:
    # `test_no_policy_surface_restates_the_numeric_default` sweeps this exact
    # file and heading as one of `_POLICY_SURFACES`, with the same
    # `\d+\s*days?` property. Keeping both meant one surface carried two copies
    # of one guard while three others carried one — which reads as this file
    # being the guarded one and is how a roster stops being read as the roster.

    def test_asks_for_what_belongs_here(self):
        """Three things are the product's own, not the framework's."""
        lower = self.flat.lower()
        assert "chosen values" in lower                     # its answers
        assert "each with its why" in lower                 # the trusted register
        assert "tier record" in lower and "reached" in lower  # the honest tier

    def test_routes_the_policy_to_direction_as_a_norm(self):
        """It BINDS future work, so it is a norm, not loose prose."""
        assert "norm-shaped" in self.flat
        assert "## Direction" in self.flat

    def test_the_direction_guidance_names_the_intake_policy(self):
        """The routing has to be discoverable from the Direction comment too — an
        author who reads top-down meets that comment before the section."""
        head = self.content[: self.content.index("## Authentication")]
        assert "upstream dependency intake policy" in head.lower()

    def test_stays_proportionate_to_risk_like_its_siblings(self):
        lower = self.flat.lower()
        assert "proportionate to risk" in lower
        for band in ("low-risk", "medium-risk", "high-risk"):
            assert band in lower

    def test_a_product_with_no_upstream_code_can_record_that(self):
        """Force the decision, don't mandate the answer."""
        assert "no upstream code records that in one line" in self.flat

    def test_the_pointer_is_qualified_for_a_reader_in_their_own_repo(self):
        """This template is instantiated as a PRODUCT's own artifact, where no
        `docs/` directory exists. A bare `docs/…` path reads as a repo-relative
        one and resolves nowhere — and the whole section's routing depends on the
        author actually going and reading it. `templates/runbook.md` sets the
        precedent for the one other template aimed at an author standing in their
        own repo: qualify it as living in the plugin."""
        assert "in the prawduct plugin" in self.flat


class TestExtractSectionTerminator:
    """`extract_section` stops at the next heading of the SAME OR HIGHER level.

    Pinned directly because the sweep cannot pin it: only one `_POLICY_SURFACES`
    entry uses a `###` heading, and neither negative guard has a single hit
    anywhere in that file — so under the old fixed `^## ` terminator the region
    silently widened to Goals 2-7 and all three sweeps passed identically. A
    property nothing can fail is not a guarded property.
    """

    DOC = "## Top\nintro\n\n### A\nalpha\n\n#### A-sub\nnested\n\n### B\nbeta\n\n## Next\nouter\n"

    def test_a_subheading_does_not_terminate_the_section(self):
        assert "nested" in extract_section(self.DOC, "### A")

    def test_a_same_level_heading_terminates_the_section(self):
        section = extract_section(self.DOC, "### A")
        assert "beta" not in section, "### A ran on into its sibling ### B"

    def test_a_higher_level_heading_terminates_the_section(self):
        section = extract_section(self.DOC, "### B")
        assert "beta" in section and "outer" not in section

    def test_a_top_level_section_still_stops_at_its_sibling(self):
        section = extract_section(self.DOC, "## Top")
        assert "alpha" in section and "outer" not in section

    def test_a_non_heading_anchor_is_rejected(self):
        with pytest.raises(AssertionError):
            extract_section("not a heading\n", "not a heading")


class TestUpstreamPolicyAgnosticismAcrossSurfaces:
    """The agnosticism and one-home guards, swept over every surface that states
    the policy — not just the file this chunk created.

    The blocking finding this closes: `discovery.md` restated the 7-day default,
    the clause substances and the tier model in a form a reader could act on
    without following the pointer, and the copies had ALREADY diverged from the
    spec on day one — nine intake surfaces there, seven here, "extensions" versus
    "plugins". A norm violated in the same chunk that added a guard against it on
    two neighbouring files is the inconsistency, so the guard now covers all of
    them rather than the number being removed from whichever file was noticed.
    """

    @pytest.mark.parametrize("rel_path,heading,scope", _POLICY_SURFACES)
    def test_no_policy_surface_names_an_ecosystem(self, rel_path, heading, scope):
        section = policed_text(rel_path, heading, scope)
        offenders = [hit.group(0) for hit in _ECOSYSTEM_RE.finditer(section)]
        assert not offenders, (
            f"{rel_path}'s policy section names {offenders!r}. Requirement 1 binds "
            "every policy statement, not only the spec: the naming belongs in the "
            "spec's non-normative appendix."
        )

    @pytest.mark.parametrize("rel_path,heading,scope", _POLICY_SURFACES)
    def test_no_policy_surface_restates_the_numeric_default(self, rel_path, heading, scope):
        """The single most copy-prone fact in this feature, and the one that was
        actually copied. Matched as a property so a change from 7 to 10 cannot
        slip through, and swept across surfaces so removing it from one file does
        not just relocate the defect to the next."""
        section = policed_text(rel_path, heading, scope)
        hit = re.search(r"\d+\s*days?\b", section)
        assert not hit, (
            f"{rel_path}'s policy section states a numeric default ({hit.group(0)!r}); "
            f"docs/{_POLICY_SPEC} owns it — cite the spec instead so the two cannot drift."
        )

    @pytest.mark.parametrize("rel_path,heading,scope", _POLICY_SURFACES)
    def test_every_policy_surface_cites_the_spec(self, rel_path, heading, scope):
        """The other half of one-home: a surface that neither states the facts nor
        points at them has simply dropped the reader.

        The `docs/` prefix is part of the assertion, matching the sibling
        message. A bare basename is not a path the reader can follow from where
        these files are read, and asserting only the basename would let one
        through — every surface carries the prefix today, so this pins the
        current state rather than asking for a change."""
        section = surface_region(rel_path, heading, scope)
        assert f"docs/{_POLICY_SPEC}" in section, (
            f"{rel_path}'s policy section must cite docs/{_POLICY_SPEC} — it is the "
            "only home for the clauses, the defaults and the tiers"
        )

    @pytest.mark.parametrize("rel_path,heading,scope", _POLICY_SURFACES)
    def test_the_declared_scope_follows_whether_the_region_is_dedicated(
        self, rel_path, heading, scope
    ):
        """The scope *choice* was the unpinned half of this roster.

        Both values were live in the tuple, the comment above explained which to
        pick, and flipping any entry to the other value failed nothing — the
        reasoning was advice, not a contract. That is the shape of a rule that
        holds only while the person who wrote it is still reading: the cost of
        getting it wrong lands much later, on an unrelated edit, as a negative
        guard accusing its author of restating a policy they never mentioned.

        So the choice is derived from the one property that actually decides it
        and is decidable by reading: **a region is dedicated when its name says
        so.** Every ``section`` surface is titled after the policy; every
        ``bullet`` surface sits under a heading about something else and merely
        carries a policy line or two. A dedicated section whose title avoids the
        word is the one shape this misjudges — rename the heading (which its
        readers want anyway) or widen the rule here deliberately, but do not
        silently flip the third element to route around it.

        A ``module`` surface has no heading, so the same question is asked of the
        thing that does name its region: the filename. Whole-file scanning is
        only honest for a file that exists for this policy alone, and a module
        named after something else would be one whose unrelated code the negative
        guards were about to police.
        """
        if scope == "module":
            assert heading is None, (
                f"{rel_path} is declared 'module' but carries a heading — a module "
                "surface's region is the whole file, so a heading would be ignored"
            )
            stem = rel_path.rsplit("/", 1)[-1]
            assert "dependency_policy" in stem, (
                f"{rel_path} is scanned whole, but its name does not say it is "
                "about this policy — either it is the wrong scope or the file "
                "holds unrelated code the negative guards would police"
            )
            return
        assert heading is not None, (
            f"{rel_path} declares scope {scope!r}, which anchors on a heading, but "
            "has none — a non-markdown surface takes 'module'"
        )
        dedicated = "upstream" in heading.lower()
        expected = "section" if dedicated else "bullet"
        assert scope == expected, (
            f"{rel_path}'s {heading!r} is declared {scope!r} but its heading "
            f"{'names' if dedicated else 'does not name'} the policy, so the "
            f"whole region {'is' if dedicated else 'is not'} the policy and the "
            f"negative guards should scan {expected!r}"
        )

    def test_the_sweep_covers_the_surfaces_that_exist(self):
        """Guards against the roster silently emptying — a parametrized sweep over
        an empty tuple passes and proves nothing."""
        assert len(_POLICY_SURFACES) >= 7
        for rel_path, heading, scope in _POLICY_SURFACES:
            text = read_file_under_plugin(rel_path)
            if heading is None:
                # No anchor to lose; what a `module` surface can lose instead is
                # the file itself — `read_file_under_plugin` has already raised
                # if so, and an emptied one is caught by the region check below.
                assert scope == "module"
            else:
                assert re.search(rf"^{re.escape(heading)}\s*$", text, re.MULTILINE), (
                    f"{rel_path} no longer carries {heading!r} — the sweep is scanning nothing"
                )
            # And that the region actually policed is non-empty, which for a
            # `bullet` surface is a different question from the heading existing.
            assert policed_text(rel_path, heading, scope).strip()
