"""Critic skill structure: mode definitions exist in the canonical instruction files.

When the proportional-Critic feature landed (v1.3.13), the skill split into two
modes: `chunk` (per-chunk fast review, goals 1-3 only) and `final` (full review).
The mode definitions live in two source files — the plugin Critic skill
(review-protocol) and the per-chunk lifecycle (review-cycle). (The file-sync
product-repo template carried a third copy until M4 Chunk 4 retired it.) If
either loses the mode terminology, the build cycle silently falls back to
ambiguous behavior (and the fail-safe default `final` masks the regression by
always running the full review, hiding the proportionality benefit).

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

REPO_ROOT = Path(__file__).resolve().parent.parent.parent / "plugin"

# Each file must contain BOTH short tokens (`chunk` and `final` as identifiers)
# AND the named section that defines them. The section name varies: the Critic
# skill files name it `## Modes`; the per-chunk lifecycle file names it
# `## Mode Selection` (it references the modes rather than defining them).
_FRAMEWORK_SKILL = REPO_ROOT / "skills" / "critic" / "review-protocol.md"
_REVIEW_CYCLE = REPO_ROOT / "skills" / "critic" / "review-cycle.md"

# Critic entry-point skill — the actual file Claude Code loads when the user
# types `/critic <mode>`. It must enumerate every recognized mode token in
# `argument-hint` and the Getting-Started step that reads `$ARGUMENTS`.
# v1.4 F2 added `cumulative` and Chunk 01 missed updating it; the drift produced
# an end-to-end-unusable feature (cumulative invocation silently downgraded to
# final, then the new gate rejected the resulting record). The Critic caught it;
# this test pins it so the next mode addition can't repeat.
_FRAMEWORK_ENTRY_SKILL = REPO_ROOT / "skills" / "critic" / "SKILL.md"


@pytest.mark.parametrize(
    "path,required_section",
    [
        (_FRAMEWORK_SKILL, "## Modes"),
        (_REVIEW_CYCLE, "## Mode Selection"),
    ],
    ids=["framework_skill", "review_cycle"],
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

    def test_cumulative_mode_referenced(self, path: Path, required_section: str) -> None:
        """v1.4 F2: the cumulative mode reviews `merge-base...HEAD` for the /pr gate."""
        content = path.read_text()
        assert "`cumulative`" in content, (
            f"{path.relative_to(REPO_ROOT)} does not reference the `cumulative` mode token. "
            "v1.4 F2 added this mode and the `/pr create` gate depends on it being "
            "consistently named across the framework + product Critic instruction files."
        )


class TestCriticVerboseModeStrings:
    """The verbose-form mode strings must appear in the source-of-truth instruction file.

    These exact strings are written to `.prawduct/.critic-findings.json` and
    surfaced in session briefings. Drift between the documented strings and the
    strings the validator accepts (in `bin/prawduct-hook` / `lib`) breaks both
    the validator and the gate WARNING text. Pin them.

    The verbose forms live in `skills/critic/review-cycle.md` — per-mode behavior
    was relocated there (v1.4 Chunk 00 SKILL.md trim-pass) so SKILL.md stays a
    focused orchestrator, retaining the short tokens (chunk | final | cumulative)
    and pointing to review-cycle.md for verbose forms. (The file-sync product
    template `templates/critic-review.md` carried inline copies until M4 Chunk 4
    retired it.)
    """

    CHUNK_VERBOSE = "chunk (lighter pass, not ready for push)"
    FINAL_VERBOSE = "final (full review, ready for push)"
    CUMULATIVE_VERBOSE = "cumulative (bundle review, ready for merge)"

    def test_chunk_verbose_string_present(self) -> None:
        content = _REVIEW_CYCLE.read_text()
        assert self.CHUNK_VERBOSE in content, (
            f"{_REVIEW_CYCLE.relative_to(REPO_ROOT)} is missing the verbose chunk-mode "
            f"string `{self.CHUNK_VERBOSE}`. The validator accepts this exact string; "
            "drift here means the docs and validator disagree."
        )

    def test_final_verbose_string_present(self) -> None:
        content = _REVIEW_CYCLE.read_text()
        assert self.FINAL_VERBOSE in content, (
            f"{_REVIEW_CYCLE.relative_to(REPO_ROOT)} is missing the verbose final-mode "
            f"string `{self.FINAL_VERBOSE}`. Drift here means docs and validator disagree."
        )

    def test_cumulative_verbose_string_present(self) -> None:
        """v1.4 F2: the cumulative verbose form must match what `validate_critic_findings` accepts."""
        content = _REVIEW_CYCLE.read_text()
        assert self.CUMULATIVE_VERBOSE in content, (
            f"{_REVIEW_CYCLE.relative_to(REPO_ROOT)} is missing the verbose cumulative-mode "
            f"string `{self.CUMULATIVE_VERBOSE}`. The validator accepts this exact string; "
            "drift here means the docs and validator disagree."
        )


@pytest.mark.parametrize(
    "path",
    [_FRAMEWORK_ENTRY_SKILL],
    ids=["framework_entry_skill"],
)
class TestCriticEntrySkillEnumeratesAllModes:
    """The `/critic` entry-point skill file must enumerate every recognized mode.

    This is the file Claude Code reads when the user types `/critic <mode>`.
    The `argument-hint` advertises the valid arguments; the Getting-Started step
    that parses `$ARGUMENTS` decides which mode to run. If a new mode is added
    to `skills/critic/review-protocol.md` but the entry skill isn't updated, the
    slash invocation silently downgrades to `final`, breaking any downstream gate
    that requires the new mode.

    v1.4 Chunk 01 (F2) added `cumulative`; this test prevents the same drift
    on the next mode addition.
    """

    def test_argument_hint_enumerates_all_modes(self, path: Path) -> None:
        content = path.read_text()
        # Locate the argument-hint line and assert every recognized mode
        # appears in it. Substring matching on the full form (e.g.
        # "argument-hint: chunk | final | cumulative") would over-pin the
        # exact ordering / decoration — v1.5 Chunk 03 prefixed
        # "(omit for inference) | " to advertise no-arg inference, which
        # would break a strict match without changing the contract that
        # every mode is enumerated. Per-token check preserves the contract.
        hint_lines = [
            line for line in content.splitlines()
            if line.startswith("argument-hint:")
        ]
        assert len(hint_lines) == 1, (
            f"{path.relative_to(REPO_ROOT)} must have exactly one "
            f"`argument-hint:` line in frontmatter; found {len(hint_lines)}."
        )
        hint = hint_lines[0]
        # Both framework and product entry template must enumerate all four
        # modes (v1.5 Chunk 06 propagated `verify-resolutions` into
        # `templates/skill-critic.md`, closing the Chunk 02 gap that the
        # per-file required-set carve-out was tracking).
        required = ("chunk", "final", "cumulative", "verify-resolutions")
        for mode in required:
            assert mode in hint, (
                f"{path.relative_to(REPO_ROOT)} `argument-hint` line "
                f"({hint!r}) does not enumerate mode {mode!r}. Slash "
                "invocation drops modes the hint doesn't advertise."
            )

    def test_getting_started_recognizes_cumulative(self, path: Path) -> None:
        content = path.read_text()
        assert "cumulative" in content, (
            f"{path.relative_to(REPO_ROOT)} does not mention `cumulative` in its "
            "Getting-Started instructions. The $ARGUMENTS parser must recognize "
            "the token, otherwise it silently downgrades to `final` and the "
            "/pr cumulative-Critic gate rejects the resulting record."
        )


class TestProportionalCriticMethodology:
    """The proportional-Critic feature spans Critic skill files AND methodology files.

    Chunk 02 of the proportional-Critic build plan extended mode documentation
    into `methodology/planning.md` (heuristic for choosing per-chunk modes) and
    `methodology/building.md` (runtime behavior — how the build cycle reads the
    mode and invokes /critic). The build-plan template was updated to surface the
    field at the right level. (A `templates/build-governance.md` copy carried the
    contract for synced product repos until M4 Chunk 4 retired it; the plugin's
    `methodology/building.md` is now the sole carrier, checked above.)

    Drift detection: if any of these files loses the mode terminology, the
    documented contract for proportional Critic invocation breaks down. A
    builder reading the build plan template won't know to declare a mode; a
    builder reading the build cycle won't know to read it. Pin the load-bearing
    headings and field placeholders.
    """

    PLANNING_MD = REPO_ROOT / "methodology" / "planning.md"
    BUILDING_MD = REPO_ROOT / "methodology" / "building.md"
    BUILD_PLAN_TEMPLATE = REPO_ROOT / "templates" / "build-plan.md"

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


class TestCriticSkillEntryPoints:
    """Slash-command entry point exposes the mode argument.

    The plugin `skills/critic/SKILL.md` must:
    1. Declare `argument-hint: chunk | final` in frontmatter so the user sees
       valid options on tab-completion.
    2. Reference `$ARGUMENTS` parsing in the body so the Critic agent knows to
       read the mode from the slash-command argument.
    """

    @pytest.mark.parametrize(
        "path",
        [REPO_ROOT / "skills" / "critic" / "SKILL.md"],
        ids=["framework_entry"],
    )
    def test_argument_hint_in_frontmatter(self, path: Path) -> None:
        content = path.read_text()
        # Per-token check (parallel to TestCriticEntrySkillEnumeratesAllModes)
        # rather than substring match — v1.5 Chunk 03 added "(omit for
        # inference) | " as a prefix; the contract is still "argument-hint
        # advertises chunk and final" but the exact form evolved.
        hint_lines = [
            line for line in content.splitlines()
            if line.startswith("argument-hint:")
        ]
        assert len(hint_lines) == 1, (
            f"{path.relative_to(REPO_ROOT)} must have exactly one "
            f"`argument-hint:` line in frontmatter; found {len(hint_lines)}."
        )
        hint = hint_lines[0]
        for mode in ("chunk", "final"):
            assert mode in hint, (
                f"{path.relative_to(REPO_ROOT)} `argument-hint` line "
                f"({hint!r}) does not advertise mode {mode!r}. Without "
                "it, slash-command users have no signal that the Critic "
                "accepts a mode argument."
            )

    @pytest.mark.parametrize(
        "path",
        [REPO_ROOT / "skills" / "critic" / "SKILL.md"],
        ids=["framework_entry"],
    )
    def test_arguments_parsing_referenced(self, path: Path) -> None:
        content = path.read_text()
        assert "$ARGUMENTS" in content, (
            f"{path.relative_to(REPO_ROOT)} does not reference `$ARGUMENTS`. The "
            "Critic agent reads the mode from this placeholder; without an explicit "
            "instruction to parse it, the agent will fall back to its default."
        )


class TestAMetaNoteIsNotAFinding:
    """An observation whose subject is another finding is folded in, not filed.

    Measured in review ``rev-20260729T230420Z-71b7f129`` (mode `final`,
    coordinator roster, 25 findings / 16 notes): R-23 was Learnings Cross-Check
    bookkeeping ABOUT R-20, and R-25 restated R-1's consequence. The honest
    distinct count was ~13 of 16. Counts are read as review thoroughness — the
    builder budgets remediation against them and every inflated note is one
    someone must read, judge and dispose of.

    The reporting half shipped (``critic_consolidate`` renders a
    likely-duplicate view and a distinct count). This is the protocol half, and
    the two are not substitutes: consolidation can flag a resemblance after the
    fact, but only the reviewer holding the observation knows that its subject
    IS a finding.

    **The recognition test is the load-bearing part, and it is pinned as a
    property rather than a phrase.** A coordinator reviewer cannot see the other
    partials, so any test shaped "does this duplicate R-13?" is unanswerable
    where it is most needed — the rule has to be answerable from one partial
    alone, which "is a finding the subject of this one?" is.
    """

    _CARRIERS = (
        ("review-protocol.md", REPO_ROOT / "skills" / "critic" / "review-protocol.md"),
        ("goals-1-3.md", REPO_ROOT / "skills" / "critic" / "goals-1-3.md"),
        ("critic-reviewer.md", REPO_ROOT / "agents" / "critic-reviewer.md"),
    )

    @pytest.mark.parametrize("name,path", _CARRIERS, ids=[n for n, _ in _CARRIERS])
    def test_every_reviewer_surface_carries_the_rule(self, name, path):
        """All three, because the three reviewer shapes read different files:
        `final`/`cumulative` single-pass reads review-protocol.md, `chunk` and
        `verify-resolutions` read goals-1-3.md, and a dispatched coordinator
        reviewer reads its agent definition. A rule on two of them is a rule the
        third reviewer never meets."""
        text = path.read_text()
        assert "subject is never another finding" in text.lower(), (
            f"{name} does not state that a finding's subject is never another "
            f"finding — a reviewer reading only this file will keep filing "
            f"meta-notes as findings"
        )

    @pytest.mark.parametrize("name,path", _CARRIERS, ids=[n for n, _ in _CARRIERS])
    def test_the_rule_names_its_two_observed_shapes(self, name, path):
        """Bookkeeping about a finding (R-23) and restating a consequence
        (R-25). A bare "don't duplicate" catches neither: both are true,
        independent-looking observations."""
        text = path.read_text().lower()
        assert "consequence" in text, f"{name} omits the restated-consequence shape"
        assert "learnings" in text, f"{name} omits the cross-check-bookkeeping shape"

    @pytest.mark.parametrize("name,path", _CARRIERS, ids=[n for n, _ in _CARRIERS])
    def test_the_recognition_test_works_from_one_partial(self, name, path):
        """The property, not the wording: the rule must say the reviewer applies
        it to its OWN findings. Phrased against another reviewer's partial it is
        unrunnable in the coordinator pattern, which is where the measured
        duplication happened."""
        text = path.read_text().lower()
        assert "your own" in text or "own partial" in text, (
            f"{name} does not scope the recognition test to the reviewer's own "
            f"partial — the other reviewers' are not visible to it"
        )

    def test_the_rule_lives_in_the_severity_legend(self):
        """Placement is substance. A reviewer resolving "what severity is this?"
        reads the legend; a rule parked elsewhere is met either before there is
        an observation to apply it to, or not at all. Same argument the
        inert-count cap is placed by."""
        text = (REPO_ROOT / "skills" / "critic" / "review-protocol.md").read_text()
        legend = text.split("## Severity Levels", 1)[1]
        assert "subject is never another finding" in legend.lower()


class TestTheLearningsReadListIsComputed:
    """Every Critic surface names the post-cutover read list, and the command.

    Learnings are ordinary `.claude/rules/` files now, so the HARNESS decides
    which of them a session held: `core.md` always, plus each area file whose
    `paths:` globs matched something the session read. That set is computed, not
    written down — and a reviewer told to "read the learnings" with no way to
    enumerate them opens `core.md` and silently misses every area rule the
    session actually had in context. That silence is the one failure this layout
    could introduce (discovery R5), which is why the command is pinned on each
    surface rather than left to the reviewer's globbing.
    """

    _SURFACES = (
        ("review-protocol.md", REPO_ROOT / "skills" / "critic" / "review-protocol.md"),
        ("review-cycle.md", REPO_ROOT / "skills" / "critic" / "review-cycle.md"),
        ("critic-reviewer.md", REPO_ROOT / "agents" / "critic-reviewer.md"),
    )

    @pytest.mark.parametrize("name,path", _SURFACES, ids=[n for n, _ in _SURFACES])
    def test_the_surface_names_core_and_the_enumerating_command(self, name, path):
        text = path.read_text()
        assert ".claude/rules/learnings/core.md" in text, (
            f"{name} does not name the always-loaded rules file"
        )
        assert "learnings-files --for-diff" in text, (
            f"{name} does not name the command that enumerates the area files — "
            f"a reviewer reading only this file cannot know which ones applied"
        )

    def test_the_dispatched_reviewer_is_granted_the_command_it_is_told_to_run(self):
        """The grant, not just the instruction. A mandated probe the reviewer
        cannot issue produces either a permission prompt in a subagent that
        cannot answer one, or a silently-skipped check — the same gap
        `verify-coverage` had, in the same place."""
        tools = (REPO_ROOT / "agents" / "critic-reviewer.md").read_text()
        assert "Bash(prawduct-hook learnings-files*)" in tools

    def test_no_critic_surface_still_sends_a_reviewer_to_the_old_path(self):
        """The read list moved; a surface still pointing at `.prawduct/learnings.md`
        sends a reviewer to a path that, post-migration, does not exist.

        Scoped to the PATH, not the bare filename: `review-cycle.md`'s
        `learnings-entry-shape` row describes a check that still runs against the
        old corpus and is deleted with that check in Wave 2, and folding it into
        this assertion would make it fail for a reason it is not about.
        """
        stale = [
            name
            for name, path in self._SURFACES
            if ".prawduct/learnings.md" in path.read_text()
        ]
        assert not stale, f"these Critic surfaces still point at the old corpus: {stale}"

    def test_the_budget_finding_carries_its_severity_on_both_mode_paths(self):
        """`learnings-over-budget` is computed at dispatch for EVERY mode, so
        both reader shapes need its severity: `final`/`cumulative` read
        `review-cycle.md`'s record-lint table, `chunk`/`verify-resolutions` read
        `goals-1-3.md`'s one-line mapping. A severity on one of them is a
        BLOCKING finding half the reviews rate for themselves."""
        cycle = (REPO_ROOT / "skills" / "critic" / "review-cycle.md").read_text()
        row = next(
            (ln for ln in cycle.splitlines() if ln.startswith("| `learnings-over-budget`")),
            None,
        )
        assert row is not None, "review-cycle.md's record-lint table has no budget row"
        assert "**BLOCKING**" in row
        goals = (REPO_ROOT / "skills" / "critic" / "goals-1-3.md").read_text()
        assert "`learnings-over-budget` → **BLOCKING**" in " ".join(goals.split())

    def test_the_new_cross_check_goal_is_stated_once(self):
        """R5's added goal — a new rule can be a duplicate, in the wrong area
        file, or framework content that belongs upstream. Once: a goal stated
        twice is two goals to keep in step, and the second copy is where the
        drift lands."""
        cycle = (REPO_ROOT / "skills" / "critic" / "review-cycle.md").read_text()
        assert cycle.count("Rules added or changed this cycle") == 1
