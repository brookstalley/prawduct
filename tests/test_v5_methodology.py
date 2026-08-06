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


def assert_inert_count_cap(text: str, path: str) -> None:
    """Both Critic protocol files cap a finding whose only subject is an inert
    count at NOTE, and both must carry it in the same place: INSIDE the NOTE
    entry of the severity legend.

    **Placement is the substance and is asserted, not assumed.** A reviewer
    resolving "what severity is this?" reads the legend entry for the severity
    it is weighing; a cap parked in its own paragraph is met either before
    there is a finding to apply it to, or not at all. This repo has shipped
    present-and-inert instruction twice with every artifact-measuring guardrail
    green — `SKILL.md`'s header, and the near-miss that drafted the
    verify-resolutions narrowing into `## Severity`, which sits below all three
    goal sections. The legend entry is the right home here for the opposite
    reason: it is a lookup, and it already owns the parent rule (record-only
    prose is a NOTE because rating it WARNING manufactures the next round).

    **The three components are the cap, not decoration.** A bare "rate it NOTE"
    still hands the builder a defect report, and a builder fixes defect
    reports — which is the commit that buys the next round. The finding has to
    say the number is *right to leave alone*, which takes all three: the true
    figure (or the builder cannot check the claim), that nothing reads it, and
    that no edit is wanted.
    """
    note_bullet = next(
        (
            ln for ln in text.split("\n")
            if ln.lstrip().startswith("- **NOTE**") and "ambiguous" in ln
        ),
        None,
    )
    assert note_bullet, f"{path} has no NOTE entry in its severity legend"
    assert "inert count" in note_bullet, (
        f"{path} states the inert-count cap outside the NOTE legend entry (or "
        "not at all) — a reviewer picking a severity reads the entry, not the file"
    )
    for component, why in (
        ("true figure", "the builder cannot check the claim without the number"),
        ("nothing reads it", "'stale' without 'inert' is just a defect report"),
        ("no edit is wanted", "the only clause that stops the fix commit"),
    ):
        assert component in note_bullet, f"{path}'s cap dropped {component!r} — {why}"


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
    "methodology/building.md": 4807,
    "skills/critic/review-protocol.md": 3611,
    "skills/critic/goals-1-3.md": 1998,
    "skills/critic/review-cycle.md": 9586,
    "skills/critic/framework-checks.md": 1116,
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

    def test_an_inert_count_is_not_written(self):
        """The BUILDER half of the contestable-count rule. The reviewer half is
        the NOTE cap in both Critic protocol files; this is the supply side, and
        it is the half that matters — a count that was never written cannot be
        corrected, re-reviewed, or argued about.

        It sits beside the self-contained-comments rule because they are one
        failure with two carriers: a durable artifact holding something that
        decays. A build id dangles when the plan is deleted; a count goes stale
        on the next commit. Both cost a finding, a fix commit, and the round the
        commit buys.

        The pinned content is the TEST, not the prohibition. "Avoid counts"
        would also forbid thresholds, versions and limits, which must stay
        exact — so the rule turns on whether anything branches on the number,
        and that clause is what a trim must not quietly drop.
        """
        assert "a count nothing reads is not worth writing" in self.content
        assert "wrong by two" in self.content, (
            "the rule lost the test that separates an inert count from a "
            "load-bearing one — without it this reads as 'avoid numbers'"
        )
        assert "stay exact" in self.content, "the load-bearing exception is gone"
        # Reader model, not presence. A builder writes the count while INSIDE
        # the build cycle (change-log entry, plan prose, docstring), so the rule
        # has to be in that section — Common Traps sits at the end of the file
        # and is read, if at all, after the prose is already written. This repo
        # has shipped present-and-inert placement before (SKILL.md's header) with
        # every artifact-measuring guardrail green.
        cycle_at = self.content.index("## The Build Cycle")
        rule_at = self.content.index("a count nothing reads")
        next_section = self.content.index("\n## ", cycle_at + 1)
        assert cycle_at < rule_at < next_section, (
            "the count rule left The Build Cycle — a builder meets it after "
            "writing the prose it governs, which is presence without effect"
        )

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
        #
        # 2026-08-04 added the builder-side inert-count rule, from ZERO headroom
        # (+0, the tightest this file has ever started an edit), and PAID FOR IT
        # by the trim-or-relocate rule. Two Common Traps went, each checked
        # rather than assumed:
        #   "Gold plating" -> CLAUDE.md's always-loaded principle roster carries
        #   P12 verbatim, the session digest's stance line says "do what was
        #   asked - no more", and "Working With Specs" closes on it. Covered on a
        #   surface the reader cannot skip, which this file's own history calls a
        #   dedup rather than a cut.
        #   "Verification theater / mock-as-implementation" -> the Verify step in
        #   THIS file, both halves: "Launch it, call it, inspect output" and
        #   "mocks are not verification". A trap restating a rule stated earlier
        #   in the same file is the exact class three earlier traps were cut as.
        # Plus three micro-relocates: the Critic's per-mode wall-clock figures
        # (review-cycle.md owns per-mode behavior and its table has a Target
        # wall-clock row -- this file now points), the gloss on "signals" (the
        # same sentence already routes the reader to review-protocol.md for
        # definitions), and "resets nothing and" in the compaction paragraph,
        # which the session paragraph four lines above states of `compact`.
        # NOT cut, and worth recording because it was the obvious candidate: the
        # `changes_referenced`/`changes_unjudged` parenthetical. doctor/SKILL.md
        # points HERE for the evidence shape, so this file is its referenced
        # home, not a copy of one.
        # RAISED 4660 -> 4810 (2026-08-05, #594). Paid for by ACCEPTING the cost,
        # not by offsetting it, and the attempt to offset is why: the two
        # delegation hazards added here (a worktree-isolated subagent reads HEAD,
        # so uncommitted governing artifacts are invisible; a shared-worktree
        # subagent shares your git INDEX, so a pathspec-less commit takes its
        # staged work) are +146 against 3 tokens of headroom. Three candidate
        # trims were tried and reverted: the standing block and the
        # warnings-gate-nothing rule are both pinned by tests in this class —
        # and `test_standing_block_is_on_every_surface_that_claims_it` records
        # that an EARLIER budget trim was already funded by relocating that
        # rule's rationale, so the redundancy a fresh trim would harvest has
        # been spent once already. One trim DID land and is counted in the +146
        # net: the Modes section lost its restatement of the mode-inference rule
        # that line ~100 already owns. Recorded because "three trims tried and
        # reverted" understated what was harvested, and a budget note that
        # misreports its own accounting is the thing this table exists to stop.
        # Relocating prose to another file was rejected
        # outright: it moves cost between files without reducing the total
        # footprint, which is the only number that matters.
        # What the +146 buys: the shared-index hazard has already produced a
        # real commit that deleted three test files under a message asserting no
        # test was deleted, and the HEAD-snapshot hazard put a subagent's
        # governing artifact in contradiction with its own prompt.
        tokens = estimate_tokens(self.content)
        assert tokens < 4810, f"building.md is ~{tokens} tokens, should be <4810"


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

    def test_an_inert_count_is_capped_at_note(self):
        """The `final`/`cumulative` half of the sink-side cap.

        Both protocol files carry it because both are read by a reviewer that
        can raise the finding, and neither reads the other. `TestCriticGoals13`
        holds the `chunk`/`verify-resolutions` half against the same helper, so
        the two copies cannot drift into disagreeing about the cap.
        """
        assert_inert_count_cap(self.content, "review-protocol.md")

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
        #
        # 3599 -> 3611 (2026-08-02) -- the coordinator prompt template gained
        # the reviewer's FIRST-action liveness marker (`<ROLE>.started`), the
        # signal that stops "no partial yet" reading as reviewer death. Paid by
        # keeping the template line to the bare imperative; the rationale and
        # full instruction live in agents/critic-reviewer.md, which every
        # dispatched reviewer loads anyway. 9 tokens of headroom remain.
        #
        # 3611 -> 3612 (2026-08-04) -- the reviewer must relay consolidate's
        # `NEXT-ACTION:` line, the only carrier of the loop-termination rule
        # with a reader in the BUILDER role. Paid in full by the fourth application of
        # this comment's own first rule: the `resolutions` schema arm was
        # restated here for a mode that does not read this file, and where
        # emitting one FAILS consolidation -- so it was not merely redundant,
        # it invited a fail-closed error.
        #
        # 3612 -> 3589 (2026-08-04) -- the inert-count NOTE cap, funded with room
        # to spare by RELOCATING "Extending This Skill" to review-cycle.md. Fifth
        # application of this comment's own first rule, and the cleanest: that
        # section tells a MAINTAINER how to grow the Critic, and a reviewer never
        # extends the skill while reviewing. Maintainer-facing rationale inside a
        # per-review payload is the same class the goals-1-3.md budget comment
        # records cutting twice. Relocated, not deleted -- review-cycle.md is the
        # maintainer's companion file and carries no ceiling.
        #
        # 3589 -> 3611 (2026-08-05) -- a partial is now bound to the review that
        # dispatched it, not to the commit alone, so the coordinator template
        # carries the review id and the two rendezvous paths, and the single-pass
        # schema carries `dispatch_id`. Two trims paid part of it, both this
        # comment's own first rule: "the coordinator never resumes to aggregate"
        # was the parenthetical form of step 3's own heading, and "never compose
        # the paths yourself" is a REVIEWER instruction whose home is
        # agents/critic-reviewer.md.
        #
        # NOT paid in full, and deliberately so. The obvious remaining cut is
        # step 2's `model:` restatement -- and it must not be taken: that prose
        # is an emergency patch against reviewer-model tiering, pinned by
        # tests/preferences/test_reviewer_model_dispatch_prose.py, and buying
        # tokens by thinning a safety instruction is the wrong trade at any
        # exchange rate. 9 tokens of headroom remain, which is the intended
        # state, not an oversight: the next addition trims or relocates.
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
        # normative-authority block, the longest passage that is not a
        # per-finding severity. (The chunk-`Type:` paragraph was the other
        # standing candidate and has now been spent — see below.)
        #
        # 1960 -> 1992 (2026-08-04) -- the reviewer must relay consolidate's
        # `NEXT-ACTION:` line, the only carrier of the loop-termination rule
        # with a reader in the BUILDER role: measured on a released version, one
        # consumer branch ran ten Critic rounds while the rule sat in two files
        # that branch never opened and in a directive that printed into seven
        # reviewer forks and zero builder contexts. Bought at 32 tokens rather
        # than ~160 by having CODE own the wording (`next_action_line`) and the
        # prose only order the relay -- the ceiling held without a bump, which
        # is this comment's standing rule.
        #
        # Paid twice, because the first version of the relay order sat where the
        # no-findings shorthand swallowed it -- dropping the carrier in exactly
        # the clean-pass case it exists for -- and making it unconditional cost
        # more than the order itself. Funded by compressing the chunk-`Type:`
        # paragraph, and by cutting a regrown instance of the very clause this
        # comment already records cutting once: a rationale addressed to a
        # MAINTAINER ("following a pointer at review time is the payload this
        # file exists to remove") inside the file whose purpose is minimum
        # reviewer payload.
        #
        # 1992 -> 1994 (2026-08-04) -- `verify-resolutions` rates new findings
        # BLOCKING only, so a re-review cannot manufacture the non-blocking work
        # that supplies the next round. Bought at 17 words for the same reason
        # the NEXT-ACTION relay was bought at 32: the worked instances live in
        # CODE (`VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE`, printed at dispatch) and
        # this file carries only the rule. Funded by the standing candidate
        # above -- "Judge jurisdiction yourself; applicability is recorded,
        # never assumed", the most abstract sentence in the normative-authority
        # block and the only one that assigns no verdict -- plus the opening
        # "The complete instruction set for these two modes", which the H1 and
        # the self-contained clause on the same line both already say.
        #
        # It sits in the PREAMBLE, not in `## Severity`, and that is a budget
        # fact as much as a design one: Severity is below all three goal
        # sections, so the cheap placement would have been read after every
        # severity it governs -- paying 17 words for nothing. Ordering beats
        # presence (`test_the_protocol_carries_it_before_any_severity_is_assigned`).
        #
        # 1994 -> 1990 (same day, that chunk's review): the narrowing needed two
        # more clauses to be TRUE, and both were funded with room left over.
        # "record-lint entries included" (+2) resolves a specific-over-general
        # conflict -- the record-lint paragraph 20 lines below assigns WARNING
        # and NOTE imperatively, inside the one mode that records neither, and
        # this is the only protocol file that mode may open. "no observations"
        # (+2) stops the report contract's clean-pass line instructing "No
        # issues found" from a pass that demoted three observations, which
        # would have defeated the cost-bound the whole narrowing rests on.
        # PAID BY the `## Severity` BLOCKING legend's example list (-8):
        # "(broken tests, dropped requirements, security vulnerabilities,
        # unlisted deps)" restates four checks stated in full above it, in the
        # legend that DEFINES the severity -- the definition is "must fix before
        # proceeding" and the examples were a fourth restatement. Generalizes
        # with the two cuts recorded above: a legend that re-lists its own
        # section's contents is paying twice for one instruction.
        #
        # NOTE for the next editor: the two normative-authority blocks (here and
        # review-protocol.md) diverged for the first time with the trim above,
        # and nothing measures the seam. Mandatory in BOTH: every claim that
        # assigns a verdict (what binds, the departure -> BLOCKING/NOTE rule,
        # the stale-registry NOTE). Droppable HERE first: claims that assign
        # none. That is the rule the divergence was chosen under.
        #
        # 1990 -> 1994 (2026-08-04) -- the inert-count NOTE cap, plus dropping
        # `numeric counts` from the doc-only Goal 1 target list (a REMOVAL that
        # part-funds its own addition: the protocol stops asking for the finding
        # the cap then has to rate). Funded the rest by the `## Record your
        # judgment` sentence enumerating what `critic-consolidate` does (appends
        # the fact, regenerates the cache, anchors the ledger, clears the
        # marker) -- mechanism the reviewer neither verifies nor uses; the
        # actionable half ("run it yourself", "You write nothing else") stayed.
        #
        # **The trim tried FIRST was rejected by a guard, and that is the entry
        # worth reading.** The `graded chunk` record-lint entry spells out both
        # guess-paths (chunk inferred from build-plan Status, plan from
        # `active_build_plan`), twenty lines under this file's own instruction
        # that each entry "carries its own explanation - raise it, don't restate
        # it" -- so the surrounding prose appeared to argue for the cut, and it
        # was taken. `test_both_unchecked_shapes_are_graded_on_every_reviewer
        # _surface` in tests/test_record_lint.py failed, and its docstring names
        # this exact edit as the predicted casualty of a token-diet pass on this
        # file. Naming only ONE guess-path leaves the other readable as a clean
        # grade, which is how the assumption shape gets read as BLOCKING -- a
        # false blocker no `--chunk` can clear. The generalization is already in
        # learnings and now has a second instance: prose that reads as redundant
        # may be the only witness to a contract. Uplevel aggressively, then run
        # the suite; the guards decide what was redundant, not the reading.
        #
        # The cap sits in the `## Severity` NOTE legend and the narrowing does
        # NOT, which is not an inconsistency: the narrowing governs whether to
        # report at all, decided continuously while reading the goals, so it had
        # to precede them; a severity cap is a LOOKUP made once at write-up, and
        # the legend entry already owns its parent rule (record prose is a NOTE
        # because rating it WARNING manufactures the next round). Both placements
        # are asserted, not assumed -- `assert_inert_count_cap` requires the cap
        # INSIDE the legend entry, and the ordering pin keeps the narrowing above
        # goal 1.
        #
        # 1994 -> 1998 (2026-08-05) -- +4 across two passes: the
        # write path now points at the manifest's `rendezvous` entry instead of
        # a literal filename, and the schema gained `dispatch_id`. Paid by two
        # cuts of this comment's own kind, and the record here is the SECOND
        # attempt, kept because the first is the more useful lesson.
        #
        # The first attempt funded the addition by compressing the closing
        # "**Either way** your last line is consolidate's `NEXT-ACTION:` ... the
        # clean pass is where it matters most" down to one word. It looked like
        # de-duplication -- the relay order IS stated 30 lines above -- and it
        # was not: `test_goals_1_3_relay_survives_the_clean_pass_shorthand`
        # exists precisely because that sentence's job is to stop the
        # no-findings shorthand swallowing the relay, and it pins "Either way"
        # for that reason. THE LESSON: a sentence that restates a nearby rule in
        # the one place a reader is about to shortcut it is not a copy, it is
        # placement -- and a guard that names a phrase is naming a function.
        # Reverted in full.
        #
        # What paid instead: "read the manifest's `record_lint`, never re-derive
        # it" carried an imperative that the very next sentence carries WITH its
        # reason attached ("never recount what it counted: that is how a record
        # defect buys a review round"), and Goal 2's record-checks bullet ended
        # "raise them at the severities given there" -- a pointer to severities
        # the preamble had already assigned, eight lines up.
        #
        # The +4 is the cumulative review's R-9, paid at face value: the
        # `dispatch_id` / `resolutions[].review_id` disambiguation had landed in
        # agents/critic-reviewer.md, whose reader never writes `resolutions`.
        # THIS file is the only surface whose reader writes both, and they sat
        # eight lines apart with no cue. Three words in the schema example.
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

    def test_an_inert_count_is_capped_at_note(self):
        """The `chunk`/`verify-resolutions` half of the sink-side cap — same
        helper as `TestCriticSkill`, so the two copies cannot disagree."""
        assert_inert_count_cap(self.content, "goals-1-3.md")

    def test_the_doc_only_selector_no_longer_hunts_counts(self):
        """The source side: the protocol stopped ASKING for count findings.

        The doc-only row aimed Goal 1 at "prose and numeric counts", which made
        the contestable-count finding an *instruction* rather than an accident —
        roughly one finding in eleven across the measured window was
        count-shaped. Removing the direction is the cheaper half of R4 and the
        only half that acts before a reviewer has formed an opinion; the NOTE
        cap above only limits the damage once one has.

        Asserted on BOTH carriers because the row exists twice — here (what a
        chunk / verify-resolutions reviewer reads) and `review-cycle.md`'s
        selector table (what every other reader consults). Dropping it from one
        leaves the other instructing the opposite, which is worse than leaving
        both: a reviewer that finds the surviving copy has an explicit mandate.
        """
        doc_only = next(ln for ln in self.content.split("\n") if "`doc-only`:" in ln)
        assert "numeric counts" not in doc_only, (
            "goals-1-3.md still directs doc-only Goal 1 at counts"
        )
        assert "Goal 1 prose only" in doc_only
        row = next(
            ln for ln in read_file("skills/critic/review-cycle.md").split("\n")
            if ln.startswith("| `doc-only`")
        )
        assert "numeric counts" not in row, (
            "review-cycle.md's Per-Chunk Type selector still asks for counts — "
            "the two carriers now instruct opposite things"
        )

    def test_the_narrowing_covers_the_record_lint_entries_below_it(self):
        """A specific-over-general conflict inside one file, and the clause that
        resolves it is unpinned prose until this test exists.

        The record-lint paragraph twenty lines below the narrowing assigns
        **WARNING** and **NOTE** imperatively (`governed-by-gap` → WARNING, and
        so on). In `verify-resolutions` those severities are not findings at
        all, and this is the only protocol file that mode may open — so a
        reviewer reading the specific instruction after the general one records
        exactly the work the narrowing exists to stop. The clause has to be in
        the narrowing, and it has to come FIRST, for the same reason the
        narrowing itself sits in the preamble.
        """
        rule_at = self.content.find("only **BLOCKING** is a finding")
        assert rule_at != -1, "the narrowing is gone — see the ordering pin"
        clause_at = self.content.find("record-lint entries included")
        assert clause_at != -1, (
            "the narrowing no longer says it covers record-lint entries, and "
            "the record-lint paragraph below still assigns WARNING and NOTE "
            "imperatively inside the one mode that records neither"
        )
        assert rule_at < clause_at < self.content.index("`record_lint`"), (
            "the coverage clause moved out of the narrowing or below the "
            "record-lint paragraph it has to govern"
        )

    def test_the_clean_pass_shorthand_does_not_swallow_observations(self):
        """`verify-resolutions` demotes findings into prose, so "no findings" and
        "nothing to report" stopped being the same thing.

        The report contract's shorthand ("No issues found.") is keyed on the
        `findings` array. Left keyed there, a pass that demoted five
        observations reports silence — and the entire cost argument for the
        narrowing is that the builder still READS them. The first real use of
        the rule demoted five, so this is not hypothetical.
        """
        closing = self.content[self.content.index("Then report to the user"):]
        assert "No findings, no observations" in closing, (
            "the clean-pass shorthand is keyed on findings alone again — a pass "
            "that demoted observations now reports 'No issues found', which "
            "deletes the only channel the demotion leaves them"
        )

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

    def test_the_per_mode_scope_line_carries_the_severity_narrowing(self):
        """SKILL.md is the FIRST file the fork reads, and its per-mode scope
        line exists so that no mode has to open `review-cycle.md` for scope.
        The narrowing IS scope, so a summary omitting it is an incomplete
        description of the mode — and this is the only carrier of the rule with
        no other guard.

        Without this pin the next token trim of that already-long line removes
        the narrowing from the fork's first read with CI green, which is the
        plan's own Verification Strategy applied to itself: *prose changes to a
        fork-read protocol are pinned by test, because nothing else can observe
        them.*
        """
        line = next(
            (ln for ln in self.content.split("\n") if "Per-mode scope" in ln), None
        )
        assert line is not None, "SKILL.md no longer summarises per-mode scope"
        assert "BLOCKING only" in line, (
            "SKILL.md's per-mode scope line no longer states that "
            "verify-resolutions rates new findings BLOCKING only — the fork "
            "reads this before its protocol, so the omission is read as "
            "'this mode rates everything'"
        )

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
    def test_token_budget(self):
        # Ceiling 9600. Added 2026-08-04 because this file was the only
        # `final`/`cumulative` payload with no bound, and the gap was being
        # SPENT: `review-protocol.md`'s relocated "Extending This Skill" and the
        # verify-narrowing argument both landed here justified by "review-cycle
        # carries no ceiling", while the ceiling test one file over passed on a
        # token DROP. Relocation across an unguarded boundary is a bump wearing
        # a trim's clothing -- the P0 wall-clock norm is about the payload a
        # reviewer loads, and `SKILL.md` lists this file as part of it (
        # `test_payload_at_most_half_the_full_protocol` counts it too).
        #
        # The ceiling is deliberately loose relative to its siblings: this file
        # is ~2.6x review-protocol.md and a tight bound would force an immediate
        # diet that nothing has argued for. It exists to make the NEXT growth a
        # decision, not to relitigate the current size. Same standing rule as
        # every other budget comment here: THE NEXT ADDITION TRIMS OR RELOCATES,
        # IT DOES NOT BUMP.
        #
        # The first draft of this comment closed with "'relocate to the
        # unbudgeted file' is no longer an available move anywhere in this
        # skill". That was FALSE when written -- `framework-checks.md` is listed
        # at SKILL.md:27 as `final`/`cumulative` payload and had no ceiling
        # either. Caught as an observation by the verify pass over the very
        # commit that added this. It is true now because the sibling test below
        # was added to MAKE it true, which is the only honest way to keep a
        # universal claim: bound the last case, or do not make the claim.
        #
        # 9471 -> 9532 (2026-08-05) -- the manifest key list gained `rendezvous`
        # and the consolidation contract gained the `dispatch_id` binding. Not
        # paid by a trim, and the reason is this file's own role: it is the
        # maintainer's companion and the one home for the manifest's key list,
        # so a key that exists and is not listed here has no home at all. The
        # additions are two clauses on lines that already existed. The last +2
        # is the cumulative review's R-13: the entry called `rendezvous` "the
        # one home for those filenames", which it is not -- `partial_path` and
        # `started_path` own the shape and every reader recomputes from them.
        # A key list that misdescribes what it records is worse than a long one.
        #
        # 9532 -> 9586 (2026-08-06) -- the "close coverage" block now answers the
        # question it raises: dispatch itself refuses a round the gate would not
        # require (exit 3), so a builder standing at that decision asks instead
        # of reasoning about judgeability. This is the decision point the
        # measured waste came from -- 62 of 492 reviews spent on free intervals
        # -- so the file that owns the close-coverage rule is where it belongs.
        # PAID FOR, not spent: the "do not retry in another mode" clause came
        # back out, because SKILL.md's exit-3 step already owns it and that is
        # the surface that reads the exit code. Net of both, +54.
        content = read_file("skills/critic/review-cycle.md")
        tokens = estimate_tokens(content)
        assert tokens < 9600, f"review-cycle.md is ~{tokens} tokens, should be <9600"

    def test_framework_checks_token_budget(self):
        # Ceiling 1150. The last `final`/`cumulative` payload file without one
        # (SKILL.md:27 routes final/cumulative reviewers here for the four
        # Framework-Specific Check definitions, and `review-protocol.md` names
        # the file rather than restating them -- a deliberate relocation that
        # this bound is what keeps honest).
        #
        # Small file, so the ceiling is proportionally looser than its siblings'
        # few-token headroom: the point is that the NEXT addition is a decision,
        # not to force a diet on 87 lines nothing has argued are too many. Same
        # standing rule: THE NEXT ADDITION TRIMS OR RELOCATES, IT DOES NOT BUMP.
        content = read_file("skills/critic/framework-checks.md")
        tokens = estimate_tokens(content)
        assert tokens < 1150, f"framework-checks.md is ~{tokens} tokens, should be <1150"

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

    def test_the_per_mode_table_records_the_severity_narrowing(self):
        """`review-cycle.md` owns per-mode behavior, so the table is where a
        maintainer looks up what a mode rates.

        The reviewer never reads this file (`goals-1-3.md` forbids it), so
        nothing here reaches the actor — which is exactly why it must not
        contradict what does. This pins the row that says `verify-resolutions`
        rates BLOCKING only against the same claim in the reviewer's protocol.
        """
        content = read_file("skills/critic/review-cycle.md")
        row = next(
            (ln for ln in content.split("\n") if "New findings rated" in ln), None
        )
        assert row is not None, (
            "the per-mode table no longer says what each mode rates — a "
            "maintainer reading it learns nothing about the narrowing"
        )
        assert "BLOCKING only" in row, (
            "the table's verify-resolutions cell no longer records the "
            "narrowing the reviewer is actually instructed to apply"
        )
        # Three modes rate everything; only one is narrowed. A row that said
        # "BLOCKING only" everywhere would pass a presence check and describe a
        # framework nobody built.
        assert row.count("Every severity") == 3, (
            "the table no longer distinguishes the narrowed mode from the "
            "three that rate every severity"
        )

    def test_the_supply_side_section_states_the_cost(self):
        """A rule that removes review output has to name what it gives up, or
        the next maintainer re-derives the tradeoff from scratch and reverses it
        on the strength of the risk alone.

        Asserting the parts of the argument, not its wording: the rule, the
        carve-out that keeps it safe, and the admission that an observation is
        not a recorded fact.
        """
        content = read_file("skills/critic/review-cycle.md")
        heading = "### A re-review does not manufacture work"
        assert heading in content, (
            "review-cycle.md no longer carries the supply-side section the "
            "per-mode table points at"
        )
        # Split on the HEADING, not the phrase — the per-mode table cites the
        # section by name, so a phrase split lands in the table and every
        # assertion below then reads the wrong text.
        section = content.split(heading, 1)[1].split("\n### ", 1)[0]
        assert "OBSERVATION" in section, "the section never names where a demoted finding goes"
        assert "fix-by-fudging" in section, (
            "the section states the narrowing without its carve-out — the "
            "classes that stay BLOCKING are what make it safe"
        )
        assert "not a recorded fact" in section or "cannot be" in section, (
            "the section sells the benefit without stating the cost: a demoted "
            "observation leaves no trace in the evidence store"
        )

    def test_the_verify_step_no_longer_rates_a_workaround_warning(self):
        """Per-Chunk Cycle step 3 used to rate "a workaround instead of root
        cause" **WARNING** — inside the one mode that now records no warnings.

        Two things were wrong with it and only one is the contradiction. A
        WARNING gates nothing, so it was also the wrong instrument: when a fix
        works around a root cause the finding named, the honest verdict is that
        the finding is *unresolved*, which is expressed by withholding the
        resolution and fails closed.
        """
        content = read_file("skills/critic/review-cycle.md")
        step = next(
            ln for ln in content.split("\n") if ln.startswith("3. **If BLOCKING")
        )
        assert "workaround instead of root cause (**WARNING**)" not in step, (
            "step 3 rates a fix-by-fudging class WARNING inside "
            "verify-resolutions, which records no warnings — the reviewer is "
            "told two different things by two files it may read in either order"
        )
        assert "resolutions" in step, (
            "step 3 no longer routes fix-by-fudging to the mechanism that "
            "actually holds the gate shut — withholding the resolution"
        )


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
