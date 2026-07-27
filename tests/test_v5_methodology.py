"""Tests for v5 methodology and Critic updates.

Verifies that methodology files, Critic instructions, and cross-cutting concerns
are internally consistent and reflect v5 concepts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
REPO_ROOT = Path(__file__).resolve().parent.parent


def read_file(rel_path: str) -> str:
    base = REPO_ROOT if rel_path.startswith(".prawduct/") else ROOT
    return (base / rel_path).read_text()


def estimate_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


# =============================================================================
# building.md
# =============================================================================


class TestBuildingMethodology:
    @pytest.fixture(autouse=True)
    def load(self):
        self.content = read_file("methodology/building.md")

    def test_work_scaled_governance(self):
        """Has governance model with size/type levels, no v4 phase references."""
        assert "Work-Scaled Governance" in self.content
        lower = self.content.lower()
        assert "current_phase" not in lower
        assert "phase transition" not in lower
        for level in ["Trivial", "Small", "Medium", "Large"]:
            assert level in self.content
        for wtype in ["Feature", "Bugfix", "Refactor", "Optimization", "Debt", "hotfix"]:
            assert wtype.lower() in lower

    def test_investigated_changes(self):
        """Has boundary investigation, decision research, and research subagent."""
        assert "Investigated Changes" in self.content
        assert "boundary" in self.content.lower()
        assert "contract surface" in self.content.lower()
        assert "Decision Research" in self.content
        assert "lock-in" in self.content.lower()
        assert "research subagent" in self.content.lower() or "research subagent" in self.content

    def test_build_cycle_structure(self):
        """Has build cycle, test discipline, and common traps sections."""
        assert "Build Cycle" in self.content
        assert "Test Discipline" in self.content
        assert "Common Traps" in self.content
        assert "Uninvestigated decisions" in self.content
        assert "Boundary blindness" in self.content

    def test_retrieval_over_generation_anchors(self):
        """The cheap-check gate and its Common Trap survive future token-diet
        trims — Principle 24's operational anchors, pinned so the newest prose
        isn't the silent casualty of the next compression pass."""
        assert "The cheap-check gate" in self.content
        assert "Retrieval Over Generation" in self.content
        assert "Tuning a mechanism you haven't read" in self.content

    def test_references(self):
        """References subagent briefing, boundary patterns, learnings skill."""
        assert ".subagent-briefing.md" in self.content
        assert "boundary-patterns.md" in self.content
        assert "/prawduct:learnings" in self.content

    def test_goal_based_critic(self):
        """References goal-based Critic review."""
        assert "Nothing Is Broken" in self.content
        assert "Design Is Sound" in self.content

    def test_chunk_close_routes_backlog_to_skill(self):
        """The chunk-close sequence routes backlog work through /prawduct:backlog
        (not hand-edits) — workflow wiring, Chunk 09. Guards the routing."""
        assert "/prawduct:backlog" in self.content

    def test_token_budget(self):
        # Lowered 4950 -> 4600 in prose-diet Chunk 02 (MET-3Q8V): the editorial
        # compression pass cut building.md to ~4173 est tokens; the ceiling is
        # post-diet +10% and exists to LOCK THE DIET IN. The bump-history
        # narrative that used to live here is in git; the standing posture is
        # unchanged: prefer trimming over bumping, place canonical detail in
        # the file that owns the concept (discovery.md for rigor, review-cycle
        # for per-mode behavior) and keep building.md to condensed pointers.
        # Norm-lifecycle Chunk 5 (GOV-7Q4N) added the "A Norm Surfaced
        # Mid-Build" tripwire and PAID FOR IT in place: the ceiling held at 4600
        # (the plan's "stay green without raising budgets" success line), the
        # addition offset by compressing the Delegating and Decision-Research
        # guidance (canonical norm detail lives in docs/norms.md). The
        # retrieval-over-generation cycle (2026-07-17, MET-4V8Q) added the
        # cheap-check gate + one Common Trap and PAID FOR THEM the same way:
        # pointer form (detectors live in docs/principles.md #24) plus an
        # editorial pass over redundant phrasing. The wait-side cache-warm
        # guidance (2026-07-20, CRT-8Q6R) qualified "don't check on it" so it
        # cannot be read as "go idle", and PAID FOR IT the same way: the full
        # cadence detail lives in review-cycle.md (the file that owns per-mode
        # behavior), the Resolve-findings step dropped a why that CLAUDE.md
        # already carries, and the "Test corruption" trap went — it restated
        # "Tests never weaken" verbatim, closing sentence included. The
        # session-continuity work (2026-07-27) added chunk-close step 7 (write
        # the forward notes) and rewrote the one sentence describing the /clear
        # hook into the two-files-two-owners paragraph, and PAID FOR BOTH the
        # same way — the additions funded entirely by in-file redundancy rather
        # than by cutting content: three Common Traps that restated
        # rules stated earlier in this same file. Surviving coverage checked per
        # item, not assumed: "Silent requirement dropping" -> Working With
        # Specs' closing line + the digest + CLAUDE.md's principle roster;
        # "Pre-existing dismissal" -> the clean-baseline paragraph + the full
        # digest (NOT the slim one, so a framework session keeps it only in this
        # file); "Ignoring the Critic" -> the Blocking-findings paragraph two
        # sections down, and nowhere else — the thinnest of the three, and the
        # first to restore if the ceiling is ever raised. Plus trailing sentences
        # restating their own bullet (multi-hop, PBT, verification theater) and
        # prose fat in the intro, worktree, PR and Critic-timing paragraphs.
        # 4590 now, one token BELOW where the addition found it. Headroom is a
        # few words BY DESIGN; the next addition trims or relocates first.
        tokens = estimate_tokens(self.content)
        assert tokens < 4600, f"building.md is ~{tokens} tokens, should be <4600"


# =============================================================================
# discovery.md, planning.md, reflection.md
# =============================================================================


class TestOtherMethodology:
    def test_discovery_continuous(self):
        content = read_file("methodology/discovery.md")
        lower = content.lower()
        assert "continuous" in lower or "isn't a phase" in lower
        for char in ["human interface", "unattended", "programmatic interface",
                      "multiple party", "sensitive data"]:
            assert char in lower

    def test_planning_continuous(self):
        content = read_file("methodology/planning.md")
        lower = content.lower()
        assert "not a one-time phase" in lower or "isn't a one-time phase" in lower or "continuous" in lower
        assert "/prawduct:learnings" in content

    def test_discovery_operationalizes_coverage_expectation(self):
        # Recording structural characteristics is tied to the strategy-class
        # coverage chain — the methodology must not drift from the mechanism.
        content = read_file("methodology/discovery.md")
        lower = content.lower()
        assert "classification.structural" in content
        assert "coverage" in lower
        assert "coverage-scaffold" in content  # the one-act stub helper is named
        assert "not relevant" in lower  # a stub satisfies coverage (the decision)

    def test_planning_cross_references_coverage(self):
        content = read_file("methodology/planning.md")
        assert "strategy-artifact-missing" in content  # the ambient detector
        assert "coverage-scaffold" in content
        assert "/prawduct:doctor" in content

    def test_reflection_learning_lifecycle(self):
        content = read_file("methodology/reflection.md")
        assert "Learning Lifecycle" in content
        for stage in ["Provisional", "Confirmed", "Incorporated"]:
            assert stage in content
        assert "Recurrence escalation" in content or "recurrence escalation" in content
        assert "phase transition" not in content.lower()
        assert "learnings.md" in content
        assert "learnings-detail.md" in content


# =============================================================================
# Methodology prose hygiene (prose-diet Chunk 02)
# =============================================================================


class TestMethodologyProseHygiene:
    """Methodology guides teach the method; implementation narration belongs in
    git history. Two classes the prose-diet removed and this test keeps out:
    internal bug-ID citations (CRT-/STH-/TST-style tags meaningless to product
    builders) and set-theory glyphs weaker models parse unreliably. Scope is
    methodology/*.md only — skills/critic may keep operational IDs where a gate
    message names them (e.g. the CRT-4J8W chain)."""

    METHODOLOGY_GUIDES = [
        "methodology/building.md",
        "methodology/discovery.md",
        "methodology/planning.md",
        "methodology/reflection.md",
    ]

    @pytest.mark.parametrize("rel_path", METHODOLOGY_GUIDES)
    def test_no_bug_id_citations(self, rel_path: str):
        import re
        content = read_file(rel_path)
        hits = re.findall(r"\b(?:CRT|STH|TST|MET|STN|PRW|REL)-[0-9A-Z]{4}\b", content)
        assert not hits, f"{rel_path} carries internal bug-ID citations: {hits}"

    @pytest.mark.parametrize("rel_path", METHODOLOGY_GUIDES)
    def test_no_set_theory_glyphs(self, rel_path: str):
        content = read_file(rel_path)
        glyphs = [g for g in ("∪", "⊇", "⊆", "∈", "∅") if g in content]
        assert not glyphs, f"{rel_path} carries set-theory glyphs: {glyphs}"


# =============================================================================
# SKILL.md (Critic)
# =============================================================================


class TestCriticSkill:
    @pytest.fixture(autouse=True)
    def load(self):
        self.content = read_file("skills/critic/review-protocol.md")

    def test_signals_and_work_scaling(self):
        """Has signals section and work size/type guidance."""
        assert "Signals That Guide Your Review" in self.content
        for level in ["Trivial", "Small", "Medium", "Large"]:
            assert level in self.content
        assert "Feature" in self.content
        assert "Bugfix" in self.content

    def test_goal_based_structure(self):
        """All seven goals present."""
        for goal in [
            "Nothing Is Broken", "Nothing Is Missing", "Nothing Is Unintended",
            "Everything Is Coherent", "Decisions Were Deliberate",
            "System Can Be Understood", "Design Is Sound",
        ]:
            assert goal in self.content

    def test_severity_and_output(self):
        """Severity levels, findings JSON, signals in output, goal key."""
        assert "BLOCKING" in self.content
        assert "WARNING" in self.content
        assert "NOTE" in self.content
        assert ".critic-findings.json" in self.content
        assert "### Signals" in self.content
        assert '"goal"' in self.content
        assert "independent" in self.content.lower()

    def test_quality_checks(self):
        """Security, documentation, design, coordinator pattern, preferences."""
        lower = self.content.lower()
        assert "injection" in lower
        assert "hardcoded secrets" in lower or "credentials" in lower
        assert "auth" in lower
        assert "documentation drift" in lower or "doc" in lower
        assert "encapsulation" in lower
        assert "coupling" in lower
        assert "coordinator" in lower
        assert "correctness reviewer" in lower
        assert "design reviewer" in lower
        assert "sustainability reviewer" in lower
        assert "project-preferences.md" in self.content
        assert "boundary-patterns.md" in self.content or "contract surface" in lower
        assert "alternatives considered" in lower

    def test_note_severity_semantics(self):
        """NOTE severity indicates genuine ambiguity."""
        for line in self.content.split("\n"):
            if line.startswith("- **NOTE**"):
                assert "ambiguous" in line.lower() or "unsure" in line.lower() or "genuinely" in line.lower()
                break

    def test_project_preferences_blocking(self):
        for line in self.content.split("\n"):
            if "project-preferences" in line.lower() and "blocking" in line.lower():
                break
        else:
            pytest.fail("project-preferences compliance should be BLOCKING")

    def test_readme_and_changelog_scope(self):
        """Critic checks README and scopes changelog review to current changeset."""
        lower = self.content.lower()
        assert "readme" in lower
        assert "actively read" in lower or "read the" in lower
        assert "changelog" in lower
        assert "history" in lower or "current changeset" in lower

    def test_framework_specific_checks(self):
        assert "Framework-Specific Checks" in self.content
        assert "Generality" in self.content
        assert "Instruction Clarity" in self.content

    def test_token_budget(self):
        # Ceiling 3530 (was 3450, was 3350). The prose-diet audit found this
        # file LEAN -- every goal bullet is a specific, severity-mapped check.
        # 3450 held until the norm-lifecycle consolidation (2026-07-16,
        # owner-approved GOV-7Q4N): the Normative-authority block landed in the
        # Review Goals preamble, PAID FOR partly by deleting Goal 6's
        # observability-strategy line and merging Goal 4's preferences check
        # into it (four scattered divergence checks became one rule; canonical
        # detail lives in docs/norms.md, this file carries only the pointer
        # form). Net ~3524 est (words x1.3). Ceiling 3530 -- still UNDER the
        # diet's own post-diet +10% formula (~3533), so the diet stays locked,
        # with near-zero headroom BY DESIGN: the next addition must trim or
        # relocate, not bump past the formula.
        tokens = estimate_tokens(self.content)
        assert tokens < 3530, f"review-protocol.md is ~{tokens} tokens, should be <3530"


# =============================================================================
# review-cycle.md
# =============================================================================


class TestReviewCycle:
    def test_structure(self):
        content = read_file("skills/critic/review-cycle.md")
        for level in ["Trivial", "Small", "Medium", "Large"]:
            assert level in content
        assert "goal-based" in content.lower() or "Goal" in content
        assert ".critic-findings.json" in content

    def test_backlog_hygiene_checks_present(self):
        """The four backlog-hygiene checks (CRT-3K9P) must stay in Backlog
        Reconciliation — guards against a silent trim deleting them (the same
        regression-guard pattern as the PR-reviewer dropped-goal test)."""
        content = read_file("skills/critic/review-cycle.md")
        for check in ("C-B1", "C-B2", "C-B3", "C-B4"):
            assert check in content, f"review-cycle.md missing backlog check {check}"


# =============================================================================
# Cross-cutting concerns
# =============================================================================


class TestCrossCuttingConcerns:
    def test_content(self):
        content = read_file(".prawduct/cross-cutting-concerns.md")
        assert "Boundary coherence" in content
        assert "Subagent governance" in content
        assert "Goal" in content
        assert "Nothing Is Broken" in content or "Nothing Is Missing" in content
        assert "boundary-patterns.md" in content
        assert "subagent-briefing.md" in content
        assert "compliance canary" in content.lower() or "canary" in content.lower()


# =============================================================================
# Cross-file consistency
# =============================================================================


class TestMethodologyConsistency:
    """Verify methodology files reference each other correctly."""

    @pytest.fixture(autouse=True)
    def load(self):
        self.building = read_file("methodology/building.md")
        self.reflection = read_file("methodology/reflection.md")
        self.critic = read_file("skills/critic/review-protocol.md")

    def test_cross_references(self):
        """Key cross-references between methodology files."""
        # building.md points readers to the Critic protocol — now the plugin's
        # bundled skills/critic/review-protocol.md (was .prawduct/critic-review.md
        # under file-sync; repointed in the v2.0.0 Chunk-14 docs sweep).
        assert "review-protocol.md" in self.building
        assert ".subagent-briefing.md" in self.building
        assert "boundary-patterns.md" in self.critic
        assert "project-preferences.md" in self.critic
        assert "learnings-detail.md" in self.reflection

    def test_no_old_check_names(self):
        """v5 uses goal names, not check names."""
        for content in [self.building, self.critic]:
            assert "### Check 1:" not in content
            assert "### Check 2:" not in content
            assert "### Check 3:" not in content


# =============================================================================
# Property-based testing across methodology
# =============================================================================


class TestMethodologyPBT:
    """Verify PBT guidance flows through discovery, building, and cross-cutting concerns."""

    def test_discovery_mentions_domain_driven_testing_strategies(self):
        """Discovery methodology mentions testing strategies tied to domains."""
        discovery = read_file("methodology/discovery.md")
        assert "property-based" in discovery.lower()
        assert "test-specifications" in discovery.lower()

    def test_building_has_test_strategies_principle(self):
        """Building methodology has 'test strategies match the domain' principle."""
        building = read_file("methodology/building.md")
        assert "Test strategies match the domain" in building

    def test_building_pbt_in_test_discipline(self):
        """PBT is mentioned in Test Discipline section."""
        building = read_file("methodology/building.md")
        td_start = building.index("## Test Discipline")
        critic_start = building.index("## The Critic")
        td_section = building[td_start:critic_start]
        assert "property-based" in td_section.lower()

    def test_cross_cutting_concerns_updated(self):
        """Cross-cutting concerns registry reflects PBT pipeline coverage."""
        ccc = read_file(".prawduct/cross-cutting-concerns.md")
        lower = ccc.lower()
        assert "pbt" in lower or "property-based" in lower
        assert "testing strategies" in lower


# =============================================================================
# docs/principles.md — the 24 principles (canonical source)
# =============================================================================


class TestPrinciplesDoc:
    """All 24 principles are present, named, and numbered in the canonical source.

    Before M4 this contract was held by `test_v5_templates.py::TestProductClaudePrinciples`
    against the file-sync `product-claude.md` template *copy*. Chunk 4 deleted that
    template (and its test) as file-sync residue; this re-anchors the contract to the
    real source of truth — `docs/principles.md` — so an accidental drop or rename of a
    principle fails loud (M4 cumulative-Critic NOTE 1).
    """

    PRINCIPLES = [
        (1, "Tests Are Contracts"),
        (2, "Complete Delivery"),
        (3, "Living Documentation"),
        (4, "Reasoned Decisions"),
        (5, "Honest Confidence"),
        (6, "Requirements Precede Code"),
        (7, "Bring Expertise"),
        (8, "Accessibility From the Start"),
        (9, "Visible Costs"),
        (10, "Clean Deployment"),
        (11, "Proportional Effort"),
        (12, "Scope Discipline"),
        (13, "Coherent Artifacts"),
        (14, "Independent Review"),
        (15, "Validate Before Propagating"),
        (16, "Root Cause Discipline"),
        (17, "Automatic Reflection"),
        (18, "Close the Learning Loop"),
        (19, "Evolving Principles"),
        (20, "Infer, Confirm, Proceed"),
        (21, "Structural Awareness"),
        (22, "Governance Is Structural"),
        (23, "Challenge Gently, Defer Gracefully"),
        (24, "Retrieval Over Generation"),
    ]

    @pytest.mark.parametrize("num,name", PRINCIPLES, ids=[f"{n}-{name}" for n, name in PRINCIPLES])
    def test_principle_present_and_numbered(self, num: int, name: str):
        principles = read_file("docs/principles.md")
        assert f"### {num}. {name}" in principles, (
            f"docs/principles.md is missing the `### {num}. {name}` heading — "
            "the 24 principles are the framework's foundation; a drop or renumber must fail loud."
        )

    def test_exactly_24_numbered_principles(self):
        """No principle is added/removed without updating this contract.
        24 (Retrieval Over Generation) added 2026-07-17 — MET-4V8Q, per Principle 19."""
        import re
        principles = read_file("docs/principles.md")
        headings = re.findall(r"^### (\d+)\. ", principles, re.MULTILINE)
        assert [int(h) for h in headings] == list(range(1, 25)), (
            f"expected principle headings 1..24 in order, found {headings}"
        )
