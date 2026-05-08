"""Critic skill structure: mode definitions exist in the canonical instruction files.

When the proportional-Critic feature landed (v1.3.13), the skill split into two
modes: `chunk` (per-chunk fast review, goals 1-3 only) and `final` (full review).
The mode definitions live in three source files — one for the framework Critic,
one for product-repo Critic, and one for the per-chunk lifecycle. If any of them
loses the mode terminology, the build cycle silently falls back to ambiguous
behavior (and the fail-safe default `final` masks the regression by always
running the full review, hiding the proportionality benefit).

This is a structural assertion, not a content audit: it checks that the files
*name* both modes and *advertise* the mode-aware behavior. It does not check
that the descriptions are correct — that's the Critic's job (Goal 4: Coherence).

Detection: literal substring search in each file. The substrings are chosen
to match the section headings and short tokens used throughout the rest of
the framework, so renaming a heading without updating the rest of the
ecosystem will fail this test before it ships.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Each file must contain BOTH short tokens (`chunk` and `final` as identifiers)
# AND the named section that defines them. The section name varies: the Critic
# skill files name it `## Modes`; the per-chunk lifecycle file names it
# `## Mode Selection` (it references the modes rather than defining them).
_FRAMEWORK_SKILL = REPO_ROOT / "agents" / "critic" / "SKILL.md"
_PRODUCT_TEMPLATE = REPO_ROOT / "templates" / "critic-review.md"
_REVIEW_CYCLE = REPO_ROOT / "agents" / "critic" / "review-cycle.md"


@pytest.mark.parametrize(
    "path,required_section",
    [
        (_FRAMEWORK_SKILL, "## Modes"),
        (_PRODUCT_TEMPLATE, "## Modes"),
        (_REVIEW_CYCLE, "## Mode Selection"),
    ],
    ids=["framework_skill", "product_template", "review_cycle"],
)
class TestCriticModeDocumentation:
    def test_file_exists(self, path: Path, required_section: str) -> None:
        assert path.is_file(), f"Critic instruction file missing: {path}"

    def test_named_section_present(self, path: Path, required_section: str) -> None:
        content = path.read_text()
        assert required_section in content, (
            f"{path.relative_to(REPO_ROOT)} is missing the `{required_section}` section. "
            "The proportional-Critic feature requires this heading; without it the "
            "build cycle has no documented mode-selection contract."
        )

    def test_chunk_mode_referenced(self, path: Path, required_section: str) -> None:
        content = path.read_text()
        assert "`chunk`" in content, (
            f"{path.relative_to(REPO_ROOT)} does not reference the `chunk` mode token. "
            "Mode terminology must stay consistent across all Critic instruction files."
        )

    def test_final_mode_referenced(self, path: Path, required_section: str) -> None:
        content = path.read_text()
        assert "`final`" in content, (
            f"{path.relative_to(REPO_ROOT)} does not reference the `final` mode token. "
            "Mode terminology must stay consistent across all Critic instruction files."
        )


class TestCriticVerboseModeStrings:
    """The verbose-form mode strings must appear in the source-of-truth skill files.

    These exact strings are written to `.prawduct/.critic-findings.json` and
    surfaced in session briefings. Drift between the documented strings and
    the strings the validator accepts (in `tools/product-hook`) breaks both
    the validator and the gate WARNING text. Pin them.
    """

    CHUNK_VERBOSE = "chunk (lighter pass, not ready for push)"
    FINAL_VERBOSE = "final (full review, ready for push)"

    @pytest.mark.parametrize(
        "path",
        [_FRAMEWORK_SKILL, _PRODUCT_TEMPLATE],
        ids=["framework_skill", "product_template"],
    )
    def test_chunk_verbose_string_present(self, path: Path) -> None:
        content = path.read_text()
        assert self.CHUNK_VERBOSE in content, (
            f"{path.relative_to(REPO_ROOT)} is missing the verbose chunk-mode string "
            f"`{self.CHUNK_VERBOSE}`. The validator in tools/product-hook accepts "
            "this exact string; drift here means the docs and validator disagree."
        )

    @pytest.mark.parametrize(
        "path",
        [_FRAMEWORK_SKILL, _PRODUCT_TEMPLATE],
        ids=["framework_skill", "product_template"],
    )
    def test_final_verbose_string_present(self, path: Path) -> None:
        content = path.read_text()
        assert self.FINAL_VERBOSE in content, (
            f"{path.relative_to(REPO_ROOT)} is missing the verbose final-mode string "
            f"`{self.FINAL_VERBOSE}`. Drift here means docs and validator disagree."
        )


class TestProportionalCriticMethodology:
    """The proportional-Critic feature spans Critic skill files AND methodology files.

    Chunk 02 of the proportional-Critic build plan extended mode documentation
    into `methodology/planning.md` (heuristic for choosing per-chunk modes) and
    `methodology/building.md` (runtime behavior — how the build cycle reads the
    mode and invokes /critic). The build-plan and build-governance templates
    were updated to surface the field at the right level.

    Drift detection: if any of these files loses the mode terminology, the
    documented contract for proportional Critic invocation breaks down. A
    builder reading the build plan template won't know to declare a mode; a
    builder reading the build cycle won't know to read it. Pin the load-bearing
    headings and field placeholders.
    """

    PLANNING_MD = REPO_ROOT / "methodology" / "planning.md"
    BUILDING_MD = REPO_ROOT / "methodology" / "building.md"
    BUILD_PLAN_TEMPLATE = REPO_ROOT / "templates" / "build-plan.md"
    BUILD_GOVERNANCE_TEMPLATE = REPO_ROOT / "templates" / "build-governance.md"

    def test_planning_has_critic_mode_per_chunk_heading(self) -> None:
        content = self.PLANNING_MD.read_text()
        assert "### Critic Mode Per Chunk" in content, (
            "methodology/planning.md is missing `### Critic Mode Per Chunk`. "
            "Without the heuristic, plan authors won't know to declare modes."
        )

    def test_planning_documents_heuristic(self) -> None:
        content = self.PLANNING_MD.read_text()
        assert "single-chunk plan" in content.lower(), (
            "methodology/planning.md must spell out the single-chunk-plan rule "
            "(uses `final`)."
        )
        assert "multi-chunk plan" in content.lower(), (
            "methodology/planning.md must spell out the multi-chunk-plan rule "
            "(first N-1 `chunk`, last `final`)."
        )

    def test_building_has_modes_subsection(self) -> None:
        content = self.BUILDING_MD.read_text()
        assert "### Modes" in content, (
            "methodology/building.md is missing the `### Modes` subsection under "
            "## The Critic. Without it, the build cycle has no documented "
            "per-mode behavior in the methodology guide."
        )

    def test_building_cycle_references_mode_from_build_plan(self) -> None:
        content = self.BUILDING_MD.read_text()
        assert "Critic mode:" in content, (
            "methodology/building.md must reference `Critic mode:` so the "
            "build cycle reads the field from the build plan."
        )

    def test_build_plan_template_has_critic_mode_placeholder(self) -> None:
        content = self.BUILD_PLAN_TEMPLATE.read_text()
        assert "**Critic mode:**" in content, (
            "templates/build-plan.md chunk template must declare a `**Critic mode:**` "
            "field. Plans authored from this template won't carry the mode otherwise."
        )

    def test_build_plan_template_has_commit_pr_cadence(self) -> None:
        content = self.BUILD_PLAN_TEMPLATE.read_text()
        assert "Commit & PR cadence" in content, (
            "templates/build-plan.md Governance Checkpoints must include a "
            "`Commit & PR cadence:` line. Per-chunk commit is the contract that "
            "makes `chunk`-mode Critic reviews work; spell it out."
        )

    def test_build_governance_references_mode(self) -> None:
        content = self.BUILD_GOVERNANCE_TEMPLATE.read_text()
        assert "Critic mode:" in content or "/critic chunk" in content or "/critic final" in content, (
            "templates/build-governance.md (synced into product repos) must "
            "reference the mode field or the mode-aware /critic invocation. "
            "Without it, products don't get the per-mode contract."
        )


class TestCriticSkillEntryPoints:
    """Slash-command entry points expose the mode argument.

    Both the framework `.claude/skills/critic/SKILL.md` and the product
    `templates/skill-critic.md` must:
    1. Declare `argument-hint: chunk | final` in frontmatter so the user sees
       valid options on tab-completion.
    2. Reference `$ARGUMENTS` parsing in the body so the Critic agent knows to
       read the mode from the slash-command argument.
    """

    @pytest.mark.parametrize(
        "path",
        [
            REPO_ROOT / ".claude" / "skills" / "critic" / "SKILL.md",
            REPO_ROOT / "templates" / "skill-critic.md",
        ],
        ids=["framework_entry", "product_entry"],
    )
    def test_argument_hint_in_frontmatter(self, path: Path) -> None:
        content = path.read_text()
        assert "argument-hint: chunk | final" in content, (
            f"{path.relative_to(REPO_ROOT)} is missing `argument-hint: chunk | final` "
            "in frontmatter. Without it, slash-command users have no signal that "
            "the Critic accepts a mode argument."
        )

    @pytest.mark.parametrize(
        "path",
        [
            REPO_ROOT / ".claude" / "skills" / "critic" / "SKILL.md",
            REPO_ROOT / "templates" / "skill-critic.md",
        ],
        ids=["framework_entry", "product_entry"],
    )
    def test_arguments_parsing_referenced(self, path: Path) -> None:
        content = path.read_text()
        assert "$ARGUMENTS" in content, (
            f"{path.relative_to(REPO_ROOT)} does not reference `$ARGUMENTS`. The "
            "Critic agent reads the mode from this placeholder; without an explicit "
            "instruction to parse it, the agent will fall back to its default."
        )
