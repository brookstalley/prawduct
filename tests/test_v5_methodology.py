"""Tests for v5 methodology and Critic updates.

Verifies that methodology files, Critic instructions, and cross-cutting concerns
are internally consistent and reflect v5 concepts.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
REPO_ROOT = Path(__file__).resolve().parent.parent


def read_file(rel_path: str) -> str:
    base = REPO_ROOT if rel_path.startswith(".prawduct/") else ROOT
    return (base / rel_path).read_text()


def estimate_tokens(text: str) -> int:
    return int(len(text.split()) * 1.3)


#: The ACTUAL token count of each budgeted file, as last measured. The per-file
#: `test_token_budget` assertions are *ceilings*; this is the reading, and one
#: test below pins it.
#:
#: **Why a table instead of a number in the accounting prose.** Each budgeted
#: file carries a comment narrating what an edit cost and what paid for it, and
#: those narratives kept going stale: on 2026-07-30 a single chunk shipped a
#: post-trim figure that was 4 tokens off, then took its *starting* figure from
#: the previous entry's ending figure — which two earlier chunks had already
#: invalidated by editing the file without updating it. A stale tally propagated
#: into a fresh tally that was wrong for a second reason.
#:
#: This is `record_lint`'s `suite-total-claim` rule applied one level in: do not
#: keep a prose copy of a figure a mechanism can own. The narratives stay (they
#: record *why* an edit was affordable, which no test can); the current reading
#: lives here, where a wrong number fails instead of misleading.
LAST_MEASURED_TOKENS = {
    "methodology/building.md": 4659,
    "skills/critic/review-protocol.md": 3610,
    "skills/critic/goals-1-3.md": 1960,
}


@pytest.mark.parametrize("rel_path", sorted(LAST_MEASURED_TOKENS))
def test_recorded_token_count_matches_the_file(rel_path):
    """A budgeted file's recorded size is the file's actual size.

    Fails the moment a budgeted file changes without its reading being updated,
    and the message carries the number to write — so the figure is never
    re-derived by hand, copied from an adjacent line, or predicted.
    """
    actual = estimate_tokens(read_file(rel_path))
    expected = LAST_MEASURED_TOKENS[rel_path]
    assert actual == expected, (
        f"{rel_path} is ~{actual} tokens; LAST_MEASURED_TOKENS says {expected}. "
        f"Update the entry to {actual} (and say in that file's budget comment "
        f"what paid for the change — the ceiling is not a budget to spend)."
    )


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

    def test_resolve_findings_dispositions_rather_than_mandating_fixes(self):
        """The guide half of the disposition rule, pinned like the runtime half.

        `TestBatchFixDirective` in tests/test_critic_consolidate.py pins
        `_BATCH_FIX_DIRECTIVE`; nothing pinned this file's copy, and this
        surface took the regression twice on one branch — "Fix them ALL" in
        the runtime string, then "Fix them all in ONE commit" here — both
        caught by a reviewer, neither by a test. The defect is specifically a
        SELF-contradiction: the reflexive-fix instruction sits ~two paragraphs
        above the rule saying warnings and notes gate nothing, so both halves
        are asserted together and the pair is what fails.
        """
        assert "Disposition them ALL in ONE pass" in self.content
        assert "Warnings and notes gate nothing" in self.content
        # The exact phrasings the runtime's own comment records rejecting.
        assert "Fix them all in ONE commit" not in self.content
        assert "Fix them ALL" not in self.content

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

    def test_handoff_is_prepared_never_proposed(self):
        """After sustained work the handoff is PREPARED, not proposed.

        Asking "should I write handoff notes?" costs the user a round-trip and,
        if they stepped away while the work ran, replays a large context into a
        cold cache — the exact cost the handoff exists to prevent. Preparing
        unasked costs little and they may continue in place, so the asymmetry
        makes the default unconditional.

        Pinned on all three surfaces because this must be framework behaviour a
        consuming product inherits, not a prawduct-local habit: building.md is
        read on demand, session-digest.md is injected into every product
        session, and the slim digest is what framework sessions get.
        """
        assert "never *ask* whether to prepare a handoff" in self.content
        digest = read_file("methodology/session-digest.md")
        slim = read_file("methodology/session-digest-slim.md")
        assert "never ask whether to prepare" in digest
        assert "Never ask whether to prepare one" in slim
        # The why travels with the always-injected surface, not the on-demand one.
        assert "cold cache" in digest

    def test_standing_block_is_on_every_surface_that_claims_it(self):
        """State / Next / Clear, the in-flight rule, and one shared trigger.

        Four prose copies carry this rule, and the split is deliberate — the
        injected digests reach product sessions, the guides are read on demand.
        But `building.md`'s token budget was FUNDED by relocating this rule's
        rationale into the digests and `reflection.md`, and that funding argument
        only holds while the destinations actually carry it. Without this pin, a
        later trim of any destination silently unfunds a trim already taken here.

        Also pins the trigger, which shipped undefined: "every stopping-place
        turn" appeared nowhere else in the plugin, and since every assistant turn
        hands control back, one reasonable reading was "every turn" — which
        appends the block to trivial Q&A and reproduces by volume the burying it
        exists to prevent.
        """
        surfaces = {
            "methodology/building.md": self.content,
            "methodology/reflection.md": read_file("methodology/reflection.md"),
            "methodology/session-digest.md": read_file("methodology/session-digest.md"),
            "methodology/session-digest-slim.md": read_file(
                "methodology/session-digest-slim.md"
            ),
        }
        for name, text in surfaces.items():
            assert "standing block" in text, f"{name} no longer names the standing block"
            # The labels are backticked, not bolded: a code span is the only
            # coloured token near the bottom of a turn, so the eye finds it
            # without reading. Owner-requested 2026-07-31 — the block was
            # correct and complete and still scanned as prose.
            for label in ("`STATE`", "`NEXT`", "`CLEAR`"):
                assert label in text, f"{name} dropped the {label} line"
            # Deliberately NOT asserting `**State**` is absent. `reflection.md`
            # keeps a bolded "what each line owes" list that *explains* the
            # three lines rather than being the emitted shape, and forbidding
            # the string would delete useful structure to satisfy a proxy. The
            # positive assertion above already fails on a revert: drop the
            # backticked labels and it goes red.
            # The SHAPE is the deliverable, not only the words. Three answers
            # run together stop being separately findable, which is most of
            # what the block is for — so every surface has to say so.
            assert "separate paragraph" in text or "three paragraphs" in text, (
                f"{name} no longer requires the three lines to be separate "
                "paragraphs — without that they render as one run-on block"
            )
            # The `---` rule: the only horizontal break in the turn, so it
            # separates the block from the wall of text above before the reader
            # has parsed a word. Owner-requested 2026-07-31, and pinned on every
            # surface because the DIGESTS are what reach product sessions — a
            # rule that lived only in the on-demand guides would be a one-off
            # for this repo.
            assert "`---`" in text, (
                f"{name} dropped the `---` rule that precedes the block"
            )
            # NOT asserting the word "backtick". Every surface already shows the
            # labels backticked and the assertion above checks that literal, so
            # requiring the word too is a second statement of one fact — the
            # thing `architecture.md`'s one-home norm exists to stop, and it
            # would fail a surface that demonstrates the shape instead of
            # narrating it.
            assert "Safe to `/clear`." in text, f"{name} dropped the safe line"
            assert "Not safe to `/clear` yet" in text, f"{name} dropped the unsafe line"
            # Outstanding includes work that is RUNNING, not merely unstarted —
            # the reported failure was signalling safe while reviewers were live.
            assert "in flight" in text, f"{name} dropped the in-flight rule"
            # One trigger, stated the same way, or the surfaces disagree about
            # when the block is owed.
            assert "work outstanding" in text, f"{name} states a different trigger"

    def test_handoff_notes_are_reconciled_not_appended(self):
        """A handoff is reconciled against reality on every write, not grown.

        The failure this pins is second-batch accretion: a session prepares
        notes, the user keeps going instead of clearing, and the next close
        stacks a fresh section on top. The reader then has to guess which layer
        is live — and the layer that reads most current is usually the one the
        later work already discharged. Observed in this repo's own
        `.handoff-notes.md`, which carried three stacked sections, one of them
        annotated with a hand-written "still applies" comment because prose was
        doing the job the reconciliation should have done.
        """
        assert "reconcile" in self.content.lower()
        assert "Never blind-append" in self.content
        for surface in ("session-digest.md", "session-digest-slim.md"):
            assert "never blind-append" in read_file(
                f"methodology/{surface}"
            ).lower(), surface

    def test_handoff_notes_are_read_before_being_rewritten(self):
        """Reconciling requires READING first, and that had to be said.

        Only `/clear` consumes `.handoff-notes.md`, so within one session a
        second batch finds the first batch's notes still on disk. An agent
        told to "reconcile" but not to read goes straight to a write and
        deletes live items it never saw — the same loss the channel exists to
        prevent, arriving by the door the fix opened. The instruction to write
        these notes long predated any instruction to read them.
        """
        assert "read `.prawduct/.handoff-notes.md` before rewriting it" in self.content
        for surface in ("session-digest.md", "session-digest-slim.md"):
            content = read_file(f"methodology/{surface}")
            assert "before rewriting it" in content, surface
            # The why belongs on the injected surfaces, not the on-demand one.
            assert "/clear` consumes" in content, surface

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
        # The trims took it to 4590 — one token BELOW the 4591 the addition
        # found — and the review then required step 7 to say what to write when
        # there is nothing to add (silence there fires the next session's
        # no-forward-note notice on every clean close). That cost 5, paid down
        # from 8 by compressing the same paragraph. 4595 now. Headroom is a few
        # words BY DESIGN; the next addition trims or relocates first.
        #
        # 4600 -> 4660 (2026-07-28, OWNER RULING) — the same ruling that raised
        # review-protocol.md 3530 -> 3620; full rationale lives there, in
        # TestCriticSkill.test_token_budget. What landed here is the builder's
        # half of the same rule: once zero blocking findings remain, FILE the
        # rest rather than fixing them, and re-run the gate instead of
        # inferring another round from stale output.
        #   SUPERSEDED 2026-07-29 — filing-as-default was reversed the same
        #   week it landed. building.md now reads "fix, accept, or file; never
        #   file by default" and review-cycle.md makes FILE the narrowest
        #   disposition, requiring a named trigger. Kept as the budget's
        #   accounting history, NOT as guidance: open items went 50 -> 180 in
        #   26 days under the rule this paragraph records. The two halves are
        # demand-side (here) and supply-side (the Critic's severity contract);
        # landing only one leaves the other half of the loop running, which is
        # why this file could not simply point at review-cycle.md.
        #
        # The trim-or-relocate rule above stands — overridden once, on the
        # record. Headroom is again a few words by design.
        #
        # 2026-07-29 (coverage-perf Chunk 03) added the never-ask-whether-to-
        # prepare-a-handoff prohibition and PAID FOR IT by the trim-or-relocate
        # rule, ending BELOW where it started: 4655 -> 4639, headroom 5 -> 21.
        # The rule landed as a clause on the existing chunk-close header; its
        # *rationale* (a round-trip, and a cold-cache context replay if the user
        # stepped away) went to session-digest.md, which is always injected, so
        # every session carries the why without building.md paying for it. The
        # funding was step 7's "nothing beyond the plan is a valid answer"
        # sentence, which both digests already state verbatim — checked, not
        # assumed: full digest lines 46-52, slim lines 21-23. That makes this a
        # dedup rather than a cut; a reader who never opens building.md still
        # gets the guidance, from a surface they cannot skip.
        #
        # 2026-07-30 (record-mechanization Chunk 04) restated the coordinator
        # roster rule on two lines — it is no longer a file count but "a risk
        # surface, or 12+ judgeable files". Measured chain, every figure from
        # estimate_tokens rather than from the line above it:
        # 4657 at branch HEAD (headroom 3) -> 4672 on the first wording, OVER
        # -> 4669 after tightening both restatements -> 4648 after the trim
        # below. Headroom 3 -> 12 at that point; a later commit in the same
        # branch removed the restatements entirely (they were false for any
        # undeclared product), landing where LAST_MEASURED_TOKENS records.
        # **That table is the current reading — this narrative is history and
        # must not be read as a live figure.**
        #
        # Note for the next editor: the 2026-07-29 entry above ends at "4639,
        # headroom 21", and this change did NOT start there — Chunks 02-03 of
        # record-mechanization edited this file without updating that figure.
        # The first draft of this note inherited 4639 and its arithmetic did
        # not close. **Measure the file; do not read the previous entry's
        # ending number as your starting one.**
        # PAID FOR by the trim-or-relocate rule, not a raise. The
        # funding was the cache-warming clause of "The Critic takes time"
        # ("don't go silent either, or your prompt cache expires…"), which
        # `critic_consolidate._CACHE_WARM_DIRECTIVE` emits verbatim into the
        # consolidate no-op the caller reads WHILE waiting — checked, not
        # assumed. So the guidance now reaches the reader from the runtime at
        # the moment it applies, instead of from a guide read hours earlier;
        # a relocate whose destination already existed. 4669 -> 4648,
        # headroom 21 -> 12.
        #
        # 2026-07-31 replaced the one-line "Safe to /clear" close with the
        # three-line standing block (State / Next / Clear) and added the
        # batch-fix clause. Owner report, and it reshaped the requirement
        # twice: the rule already existed, but agents were burying a correct
        # signal mid-summary, and what a user wants after a 30-120 minute wait
        # is not a safety verdict alone — it is state, the next action and who
        # owns it, then the verdict. PAID FOR by the trim-or-relocate rule, not
        # a raise: 4652 -> 4725 on the first draft, then back under budget with
        # room to spare (the live figure is in LAST_MEASURED_TOKENS above; this
        # chain deliberately stops short of it, because an endpoint written here
        # is a hand-maintained copy of a machine-held number and goes stale on
        # the next edit — which is what happened twice in this branch alone).
        # Fundings, each a
        # relocate to a surface the reader cannot skip rather than a cut:
        # (1) the block's RATIONALE (why three lines, the three failure modes,
        # what counts as "outstanding") went to reflection.md, which owns the
        # work-cycle boundary, and to BOTH digests, which are always injected —
        # this file keeps the three line-labels and a pointer; (2) the
        # fix-strategy detail (which writes stay free mid-review) went to
        # `critic_consolidate._BATCH_FIX_DIRECTIVE`, which the runtime emits
        # with the findings themselves, so this file keeps one clause;
        # (3) "Two session files" dropped the rescued-hop gloss that
        # session-digest.md states, and step 7 its blind-append gloss that both
        # digests state — checked, not assumed; (4) the evidence-model paragraph
        # condensed to a pointer at review-cycle.md, the file that owns it;
        # (5) the Verify/Code bullet dropped a parenthetical re-listing the
        # ingest flags named one clause earlier, and Persist-plans a clause
        # that line 11 already states. Two trims were REVERTED because tests
        # pinned them as contracts (the seven goal names, "Never blind-append")
        # — the funding was found elsewhere rather than the tests weakened.
        # One correction rode along and cost nothing: the Blocking/Warnings
        # paragraph said warnings "should be addressed", which review-cycle.md
        # § "The review loop terminates" names BY FILE as the cause of the
        # round pump — it now says warnings and notes gate nothing and are
        # dispositioned. The next addition trims or relocates — read the live
        # headroom off LAST_MEASURED_TOKENS against the assertion below rather
        # than from this narrative, which is history. A figure written here was
        # stale twice in one branch (4655 survived a trim to 4646, and this line
        # said "Headroom 5" above an assertion permitting 14) — the same
        # copy-forward this table was built to end.
        tokens = estimate_tokens(self.content)
        assert tokens < 4660, f"building.md is ~{tokens} tokens, should be <4660"


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
        # Ceiling 3620. This file is the `final` / `cumulative` payload, and the
        # prose-diet audit found it LEAN -- every goal bullet is a specific,
        # severity-mapped check, so there is no slack to reclaim by rewording.
        #
        # The standing rule, and the only part of this comment that decides
        # anything: THE NEXT ADDITION TRIMS OR RELOCATES, IT DOES NOT BUMP.
        # Raising the ceiling requires showing the framework is provably better
        # for the raise AND that no headroom remains in upleveling -- cutting
        # detail, dates, worked examples, and definitions the reader never
        # applies. The ceiling has been raised exactly once, by owner ruling,
        # for a rule that removes more review work than it costs; every other
        # addition has been funded in place.
        #
        # Three cuts that funded real additions, kept because they generalize:
        # a definition another file owns and the reader is told to open is not
        # worth restating here (Framework-Specific Checks now names the four
        # checks and points at framework-checks.md); a message the reviewer can
        # compose is not worth quoting verbatim; and history -- what a mechanism
        # USED to do -- is never worth carrying in an instruction payload.
        #
        # One trap, learned twice: Goal 4's `**Norms**` bullet READS as a pure
        # restatement of the Normative-authority preamble and is not safe to
        # delete. test_project_preferences_blocking contracts on a single LINE
        # carrying both "project-preferences" and "blocking", and that bullet is
        # the only line that satisfies it. Two separate editors have cut it and
        # put it back.
        tokens = estimate_tokens(self.content)
        assert tokens < 3620, f"review-protocol.md is ~{tokens} tokens, should be <3620"


# =============================================================================
# goals-1-3.md — the chunk / verify-resolutions payload
# =============================================================================


class TestCriticGoals13:
    """`chunk` and `verify-resolutions` read this file INSTEAD of
    review-protocol.md + review-cycle.md.

    Why the split exists, measured over all 267 review facts carrying a
    duration: `chunk` missed its 1-2 min target in 30 of 30 recorded runs and
    `verify-resolutions` in 148 of 155, while `final` — loading the same
    protocol for more than twice the goals — sat INSIDE its target 85% of the
    time. The 96 smallest verify runs (<=5 changed files) still took a median
    240s, so the floor is not diff size; it is what gets loaded before a single
    changed line is read.
    """

    @pytest.fixture(autouse=True)
    def load(self):
        self.content = read_file("skills/critic/goals-1-3.md")
        self.protocol = read_file("skills/critic/review-protocol.md")

    def test_payload_at_most_half_the_full_protocol(self):
        """The chunk's acceptance criterion, pinned: measured payload for these
        modes drops by at least half.

        Compared against what these modes loaded BEFORE — review-protocol.md
        plus review-cycle.md, which the protocol pointed at eight times, so a
        reviewer following its pointers read both. SKILL.md is common to every
        mode and cancels out of the comparison."""
        cycle = read_file("skills/critic/review-cycle.md")
        before = estimate_tokens(self.protocol) + estimate_tokens(cycle)
        after = estimate_tokens(self.content)
        assert after * 2 <= before, (
            f"goals-1-3.md is ~{after} tokens against a ~{before}-token predecessor "
            f"({100 * after // before}%) — the split must at least halve the payload"
        )

    def test_token_budget(self):
        # Ceiling 2000. This file is the chunk / verify-resolutions payload and
        # orders its reader to open nothing else, so every pointer-chase it
        # would cause has to be inlined here instead -- which is why it is long,
        # and why the ceiling is the thing that governs rather than a line count.
        #
        # The standing rule, and the only part of this comment that decides
        # anything: THE NEXT ADDITION TRIMS OR RELOCATES, IT DOES NOT BUMP. A
        # check belonging to goals 1-3 is funded by compressing prose here,
        # never by dropping a check and never by raising the ceiling. Raising it
        # requires showing the framework is provably better for the raise AND
        # that no headroom is left in upleveling -- cutting detail, dates,
        # worked examples and definitions the reader never applies.
        #
        # Two cuts that paid for real additions, kept because they generalize:
        # a definition the machine already emits is not worth restating (the
        # reviewer is told to read `record_lint`'s own message and raise it), and
        # neither is a rationale explaining why this file is short, addressed to
        # a maintainer, inside the file whose purpose is minimum reviewer
        # payload.
        #
        # Standing trim candidates when the next editor needs room: the
        # chunk-`Type:` paragraph, which restates a table `review-cycle.md` owns,
        # and the normative-authority block, the longest passage that is not a
        # per-finding severity.
        tokens = estimate_tokens(self.content)
        assert tokens < 2000, f"goals-1-3.md is ~{tokens} tokens, should be <2000"

    def test_is_self_contained(self):
        """No follow-the-pointer reads at review time — the acceptance criterion
        the line count was traded for. A reviewer in these modes reads this file
        and stops.

        The rule is about *directives*, not the strings: the file names the two
        protocol files precisely once, to forbid opening them, and a concrete
        prohibition instructs better than "don't read the others." So every line
        mentioning one must be that prohibition — which also means a future edit
        cannot smuggle a read-directive back in under the same filename."""
        pointers = ("review-protocol.md", "review-cycle.md", "framework-checks.md")
        offenders = [
            ln for ln in self.content.split("\n")
            if any(p in ln for p in pointers) and "do not open" not in ln
        ]
        assert not offenders, f"goals-1-3.md sends the reviewer elsewhere: {offenders}"

    def test_no_check_from_goals_1_3_was_dropped(self):
        """The distillation must lose no check. Every check in the protocol is
        severity-mapped, so a dropped one shows up as a missing verdict — this
        counts them rather than trusting the prose, and anchors the named checks
        that a recount alone would not catch.

        **This test is also what makes the duplication safe.** Goals 1-3 now
        exist in two files, which is real duplication and the obvious objection
        to the split. It is deliberate and policed rather than tolerated: the
        count invariant below is directional (`got >= src`), so adding a check
        to review-protocol.md's goals 1-3 without adding it here FAILS — the two
        copies cannot drift apart in the direction that matters, which is a
        check the chunk-mode reviewer never sees.

        The alternative considered and rejected: delete goals 1-3 from
        review-protocol.md and have `final`/`cumulative` read both files. That
        removes the duplication outright, but it re-splits the seven-goal
        payload across two files to fix a problem this test already closes, and
        the plan scopes `final`/`cumulative` to keep the full protocol. Revisit
        if the anchor list below starts needing maintenance every time a goal
        changes — that would mean the coupling had become the cost.
        """
        goals = self.protocol[
            self.protocol.index("### 1. Nothing Is Broken"):
            self.protocol.index("### 4. Everything Is Coherent")
        ]
        # Compare goal section to goal section. Counting the WHOLE of
        # goals-1-3.md against a protocol *slice* silently bought slack: the
        # inlined record-lint table, the normative-authority preamble and the
        # `## Severity` legend all carry verdicts of their own and have no
        # counterpart inside the slice, which left room for two unmirrored
        # WARNING checks — and WARNING is the modal severity here. Slack in a
        # drift detector is indistinguishable from the drift it is watching for.
        mine = self.content[
            self.content.index("## 1. Nothing Is Broken"):
            self.content.index("## Severity")
        ]
        for sev in ("BLOCKING", "WARNING", "NOTE"):
            src = goals.count(f"**{sev}**")
            got = mine.count(f"**{sev}**")
            assert got >= src, (
                f"goals-1-3.md's goal sections carry {got} {sev} verdicts against the "
                f"protocol's {src} — a check was added to one copy and not the other"
            )
        for anchor in (
            "test-status", "verify-coverage", "missing-coverage:", "pre-existing",
            "exact-match", "property-based", "injection", "hardcoded secrets",
            "trust boundaries", "explicitly descoped", "observable behavior",
            "Requirements Confidence", "record_lint", "project-preferences.md",
            "accessibility", "infrastructure_dependencies", "Foreign API",
            "Exposed API", "api_error_model_approach", "operator-verification",
            "unlisted dependencies", "undocumented architectural", "broad exception",
            "prawduct:allow", "Trivial because",
        ):
            assert anchor.lower() in self.content.lower(), f"goals-1-3.md dropped check anchor {anchor!r}"

    def test_carries_what_the_pointers_used_to_fetch(self):
        """Self-containment is only real if the inlined content is here. These
        are the four pointer-chases the old payload forced."""
        assert "chunk-ref-missing" in self.content and "governed-by-gap" in self.content
        assert "unchecked" in self.content            # record-lint's not-a-pass rule
        assert "designer-handoff" in self.content     # the chunk `Type:` selector
        assert "Normative authority" in self.content  # Goal 3's binding preamble
        assert '"resolutions"' in self.content        # the verify-resolutions schema arm

    def test_never_runs_anything(self):
        """The no-execution rule is load-bearing and must survive distillation."""
        lower = self.content.lower()
        assert "never run tests" in lower or "do not run tests" in lower

    def test_does_not_carry_the_final_only_payload(self):
        """The split is only worth its cost if the seven-goal content is gone —
        a copy that regrew into the full protocol would pass every test above."""
        for absent in (
            "Everything Is Coherent", "Decisions Were Deliberate",
            "The Design Is Sound", "Coordinator Pattern",
            "Framework-Specific Checks", "Backlog Reconciliation",
        ):
            assert absent not in self.content, f"goals-1-3.md regrew {absent!r} — that is final-mode payload"


class TestCriticSkillRoutesByMode:
    """SKILL.md step 2 selects the payload; without this the new file exists and
    nothing reads it."""

    @pytest.fixture(autouse=True)
    def load(self):
        self.content = read_file("skills/critic/SKILL.md")

    def test_step_2_names_both_payloads(self):
        line = next(ln for ln in self.content.split("\n") if ln.startswith("2. "))
        assert "goals-1-3.md" in line
        assert "review-protocol.md" in line
        for mode in ("chunk", "verify-resolutions", "final", "cumulative"):
            assert mode in line, f"SKILL step 2 does not route {mode}"

    def test_header_scopes_every_final_only_file_it_names(self):
        """The header is the FIRST instruction in the skill body, so it beats
        step 2 on reading order — an agent obeys it before it knows its mode.

        It used to say `review-protocol.md` "(read this first)" and not mention
        `goals-1-3.md` at all, so a chunk-mode review loaded the entire
        10,519-token predecessor payload before step 2 told it not to. The split
        was correct on disk and inert on the instruction path, and every
        size-measuring guardrail stayed green through it.

        Asserting the class, not that one instance: pinning the literal string
        "read this first" would pass the moment someone reworded the directive.
        Every header bullet naming a final-only file must scope itself to the
        modes that read it, which no rewording escapes."""
        header = self.content.split("## Structural Constraints", 1)[0]
        assert "goals-1-3.md" in header, "the header omits the fast-mode protocol file"
        assert "after step 1" in header.lower() or "only after" in header.lower(), (
            "the header must state that the protocol read follows mode resolution"
        )
        # The file-list BULLETS are the routing; the surrounding prose is not
        # (one line names `review-cycle.md` as an example of resolving a bare
        # sibling path, which is a rule about where files live, not an
        # instruction to read one).
        unscoped = [
            ln.strip()[:110] for ln in header.split("\n")
            if ln.lstrip().startswith("- ")
            and any(f in ln for f in ("review-protocol.md", "review-cycle.md", "framework-checks.md"))
            and not any(m in ln for m in ("final", "cumulative"))
        ]
        assert not unscoped, f"header lists a final-only file without scoping it: {unscoped}"

    def test_the_single_pass_bullet_never_cites_a_final_only_file(self):
        """The single-pass roster bullet is the fast path's write-up
        instruction, and everything it needs is in goals-1-3.md.

        This is its own test because a line-level check cannot police it: the
        bullet permanently contains the words "small `final`/`cumulative`" (it
        describes when small final reviews go single-pass), so any rule that
        excuses a line for mentioning `final` excuses THIS line unconditionally
        — and it is the exact line that carried the `(schema: review-protocol.md
        …)` pointer a blocking round was spent removing. Zero citations here."""
        bullet = next(
            ln for ln in self.content.split("\n")
            if 'Roster `["reviewer"]`' in ln
        )
        for cited in ("review-protocol.md", "review-cycle.md"):
            assert cited not in bullet, (
                f"the single-pass bullet cites {cited} — that read is the payload "
                f"the split removed, and goals-1-3.md already carries it"
            )

    def test_fast_path_steps_never_send_the_reviewer_to_a_final_only_file(self):
        """Steps 1-7 run in EVERY mode, so an unqualified citation there is a
        read a chunk-mode reviewer will make.

        Judged per *clause*, not per line: a qualifier anywhere on a long line
        used to excuse a citation elsewhere on it.

        **No line-level exemptions.** The coordinator bullet used to be skipped
        wholesale — legitimate in itself (that roster only exists in
        `final`/`cumulative`) but an escape hatch excusing anything later
        appended to that line, which is the same shape as the defect this test
        was written to catch. Its prose now qualifies its own citation
        (`the final/cumulative "Coordinator Pattern" in review-protocol.md`), so
        the skip was deleted rather than documented."""
        steps = self.content.split("## Getting Started", 1)[1]
        offenders = []
        for ln in steps.split("\n"):
            for clause in re.split(r"(?<=\.)\s|[;()]", ln):
                if "review-protocol.md" not in clause and "review-cycle.md" not in clause:
                    continue
                if any(q in clause for q in ("final", "cumulative", "goals-1-3.md")):
                    continue
                offenders.append(clause.strip()[:110])
        assert not offenders, f"fast-path steps cite a final-only file unqualified: {offenders}"

    def test_review_cycle_table_records_the_routing(self):
        """`review-cycle.md` owns per-mode behavior, so the routing is recorded
        there too — a reader who checks the mode table must not learn a
        different answer from the one SKILL.md acts on."""
        cycle = read_file("skills/critic/review-cycle.md")
        row = next((ln for ln in cycle.split("\n") if "Protocol read" in ln), None)
        assert row is not None, "review-cycle.md's per-mode table has no protocol-read row"
        assert row.count("goals-1-3.md") == 2, "chunk and verify-resolutions both read goals-1-3.md"
        assert row.count("review-protocol.md") == 2, "final and cumulative both read review-protocol.md"


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
