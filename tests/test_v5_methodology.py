"""Tests for v5 methodology and Critic updates.

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

    def test_references(self):
        """References subagent briefing, boundary patterns, learnings skill."""
        assert ".subagent-briefing.md" in self.content
        assert "boundary-patterns.md" in self.content
        assert "/learnings" in self.content

    def test_goal_based_critic(self):
        """References goal-based Critic review."""
        assert "Nothing Is Broken" in self.content
        assert "Design Is Sound" in self.content

    def test_token_budget(self):
        # Bumped from 3900 → 4100 in v1.3.13 (proportional Critic / chunk vs.
        # final modes). The Modes subsection, mode-aware Critic invocation, and
        # "Skipping final mode" Common Trap add ~120 tokens of essential
        # documentation after aggressive trimming. If this test fails again,
        # prefer trimming over another bump.
        #
        # Bumped from 4100 → 4250 in v1.3.15 (Requirements Precede Code).
        # The new "Before You Build: Confidence Check" section anchors
        # Principle 6 in the build cycle — three questions, three response
        # options. Trimmed to ~100 tokens (5 sentences) before bumping.
        # Further trimming would lose the pedagogical structure the section
        # depends on. If this test fails again, prefer trimming over another
        # bump.
        #
        # Bumped from 4250 → 4275 in v1.4 Chunk 05 (F1a derived views). The
        # chunk-close step gains a one-clause pointer that Status may be a
        # derived view (~13 tokens) — needed so methodology readers know the
        # full guidance lives in change-log.md schema and product-claude.md
        # step 10. Trimmed to a parenthetical before bumping.
        #
        # Bumped from 4275 → 4375 in v1.4 Chunk 09 (F4b — Critic symbol-coverage
        # check + methodology principle). The chunk's spec required a new
        # paragraph under Test Discipline naming the floor verifier, the
        # `coverage_level` contract, and the `verify-coverage` Critic check
        # (~75 tokens after aggressive trimming — the floor-vs-executed
        # distinction is the chunk's reason for existing). If this test
        # fails again, prefer trimming over another bump.
        #
        # Bumped from 4375 → 4400 in v1.4 Chunk 14 (F10 — operator-verification
        # queue + /pr BLOCKING gate). The chunk-close step gains a one-sentence
        # pointer naming the queue file, the `Visual change:` declaration, and
        # the `operator_verification_required` flag — trimmed to ~30 tokens
        # before bumping by 25. The new chunk-close step is required by the
        # v1.4 maintenance plan (methodology pipeline coverage); folding it
        # into "Update build plan Status" was rejected because the enqueue
        # action is conceptually separate from marking the chunk shipped.
        #
        # Bumped from 4400 → 4450 in v1.5 Chunk 03 (`/critic` no-arg mode
        # inference). The Critic-review step gains the inference invocation
        # contract — name the helper (`tools/product-hook infer-critic-mode`),
        # the persisted field (`mode_chosen_by`), the override path, and the
        # failure fallback (`final`). Trimmed to ~20-token delta over the
        # original phrasing before bumping; further trimming would lose
        # either the helper name or the override-reporting protocol that
        # makes inference tunable. If this test fails again, prefer trimming
        # over another bump.
        tokens = estimate_tokens(self.content)
        assert tokens < 4450, f"building.md is ~{tokens} tokens, should be <4450"


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
        assert "/learnings" in content

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
        # Bumped from 3500 → 3700 in v1.3.13 (proportional Critic / chunk vs.
        # final modes). The Modes section, activation step, goal preamble, and
        # JSON `mode` field add ~150 tokens of essential documentation for the
        # new feature.
        #
        # Tightened from 3700 → 3200 in v1.4 Chunk 00 (SKILL.md trim-pass).
        # The Coordinator Pattern was deduplicated, Goal 7's state-modeling
        # paragraph was condensed, and final-mode-only sections (Learnings
        # Cross-Check, Backlog Reconciliation) moved to review-cycle.md.
        # The 500-token reduction in ceiling (not slack — actual slack
        # against <3200 is small) is reserved for v1.4's F2/F3/F4/F6 Critic
        # protocol additions. Future Critic prose additions should prefer
        # `review-cycle.md` (per-mode behavior) or `framework-checks.md`
        # (framework-only checks). If this test fails again, prefer trimming
        # over another bump — the Critic skill is loaded fresh on every
        # invocation and the budget bounds that cost.
        #
        # Bumped from 3200 → 3250 in v1.4 Chunk 05 (F1a derived views). Goal 4
        # gains a "Derived views" bullet that pins the Critic's behavior when
        # `views_enabled` is true — the change-log tag line, not the regenerated
        # Status checkbox, is canonical. The check is structural (not a check
        # the per-product critic-review.md can carry alone, since framework
        # Critic reviews read SKILL.md directly), and was trimmed to ~35
        # tokens before bumping.
        #
        # Bumped from 3250 → 3325 in v1.4 Chunk 09 (F4b — Critic symbol-coverage
        # check). Goal 1 gains a `verify-coverage` bullet that maps the helper's
        # exit codes and stderr-line format to BLOCKING findings, scaled to
        # `coverage_level` (~50 tokens after aggressive trimming). This is one
        # of the F4 protocol additions the Chunk 00 trim-pass explicitly
        # reserved budget for. If this test fails again, prefer trimming over
        # another bump.
        #
        # Lowered from 3325 → 3050 in v1.5 Chunk 00 (Critic proportionality
        # release). 524-token trim across When-You-Are-Activated, Goal 1,
        # Goal 4, Goal 7 ("Unmodeled state-based problems" reduced from
        # ~325 → ~95 tokens), Severity Levels, and Coordinator dispatch
        # prompt — compression only, no content removed.
        #
        # Raised 3050 → 3120 in v2.0.0 Chunk 13: this now measures the plugin's
        # `skills/critic/review-protocol.md` (the canonical Critic protocol; the
        # legacy `agents/critic/SKILL.md` was removed when this repo cut over to
        # the plugin). Its content is identical to the old file; the ~12-token
        # delta is purely longer plugin-native path strings (`prawduct-hook` vs
        # `tools/product-hook`, `${CLAUDE_SKILL_DIR}/../../docs/principles.md` vs
        # `docs/principles.md`) — a one-time structural cost, not content bloat.
        # ~50-token headroom retained. Continue preferring trim over bump.
        tokens = estimate_tokens(self.content)
        assert tokens < 3120, f"review-protocol.md is ~{tokens} tokens, should be <3120"


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
