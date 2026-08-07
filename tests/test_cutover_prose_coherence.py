"""Coherence tripwires for the post-cutover backlog contract.

Three surfaces state the same contract in prose, a chunk apart, in files no
single reviewer opens together: the Critic's Backlog Reconciliation, the PR
reviewer's R-1/R-2, and the janitor's Backlog Health. Prose has no compiler, so
the copies drift silently — and every defect this contract exists to prevent is
itself a *consistency* defect between two surfaces rather than a bug inside one.
These tests are the pin.

Two rules are adjudicated here rather than assumed, each with a `## Direction`
norm as its owner:

* **No prawduct-internal ids in operator-emitted text**
  (`observability-strategy.md`). An operator in a downstream product cannot
  resolve them.
* **`backlog_service_repo` selects the authoritative store; a direct read of the
  frozen markdown file is gated on that scalar, not banned outright**
  (`data-model.md`).

The `backlog.md`-mention sweep at the bottom is the re-greppable half: a reader
added later that names the file without knowing about the gate fails here
instead of shipping confident findings about items closed at cutover.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# Every surface this module reads — skills/, methodology/, docs/, lib/ — lives
# under plugin/, not at the repo root, and the paths in NOTE_SURFACES are written
# relative to it.
REPO_ROOT = Path(__file__).resolve().parents[1] / "plugin"

# The one home for the query mechanics the three readers share. Stating them per
# surface is what produced the drift these tests exist to catch, so the pin is now
# that each surface ROUTES here rather than that its copy matches the others'.
CACHE_READS = "skills/backlog/cache-reads.md"

# Every surface that reads the backlog cache at review time, and the subject it
# leads its unavailable-notice with. The subjects still differ per surface (each
# names its own block); what must not differ is the rule behind them.
NOTE_SURFACES = {
    "skills/critic/review-cycle.md": "Backlog reconciliation unavailable",
    "skills/pr/review-protocol.md": "Backlog reconciliation unavailable",
    "skills/janitor/SKILL.md": "Backlog Health unavailable",
}

# The dormancy NOTE these surfaces emitted while the checks were dark. The readers
# are restored and the advisory that enumerated them is retired, so a surviving
# copy of this text is a surface still telling operators to wait for something that
# has already landed.
RETIRED_NOTE_TAIL = (
    "these checks have no Issues-mode path yet; they return when the backlog "
    "read-through cache lands"
)

# Internal identifiers that must not reach an operator's screen. Not an
# exhaustive vocabulary — prefixes are open-ended, which is exactly why the
# durable enforcement is the Critic's judgment and this list only pins the
# copies a past changeset actually got wrong.
FORBIDDEN_IDS = ("GV8", "W1", "W2", "GV7")


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text()


class TestTheThreeReadersShareOneContract:
    """The Critic's reconciliation walk, the PR reviewer's R-1/R-2, and the
    janitor's Backlog Health all read the backlog cache, in files no single
    reviewer opens together. Prose has no compiler, so copies drift silently — and
    every defect this contract exists to prevent is itself a *consistency* defect
    between two surfaces rather than a bug inside one.

    **These tests were re-aimed, not rewritten around, when the readers came back
    on the cache.** They used to pin three byte-identical copies of a dormancy
    NOTE. The mechanics those copies shared now live in one file and the surfaces
    route to it, so the pin moved with them: routing, plus the two rules each
    surface must still carry in its own words because each decides what its own
    block emits.
    """

    @pytest.mark.parametrize("rel", sorted(NOTE_SURFACES))
    def test_surface_routes_to_the_one_home(self, rel):
        flat = " ".join(_read(rel).split())
        assert CACHE_READS in flat, (
            f"{rel} reads the backlog cache but no longer routes to {CACHE_READS}, "
            f"where the invocation and the failure contract live. A surface that "
            f"restates them instead is the first of three copies."
        )

    @pytest.mark.parametrize(("rel", "subject"), sorted(NOTE_SURFACES.items()))
    def test_surface_says_unavailable_is_not_empty(self, rel, subject):
        """The one rule that cannot be delegated: each surface decides what its own
        block emits when the store cannot be read, and reporting nothing is
        indistinguishable from a clean bill of health — the exact failure these
        readers were made to announce rather than commit."""
        flat = " ".join(_read(rel).split())
        assert subject in flat, f"{rel} no longer leads its unavailable notice with its subject"
        assert "exit 6" in flat.lower(), (
            f"{rel} does not name the exit code that distinguishes 'could not read' "
            f"from 'nothing matched'."
        )
        assert "prawduct-hook backlog sync" in flat, (
            f"{rel} reports the gap without the command that closes it."
        )

    @pytest.mark.parametrize("rel", sorted(NOTE_SURFACES))
    def test_surface_restates_the_item_text_treatment(self, rel):
        """Cached issue bodies re-enter agent-read prose at these three sites, and
        the exposure is wider than it was: every open body, not the items a reader
        happened to open. The security norm is restated AT each site rather than
        inherited by routing, because the routed file is guidance a reader may skim
        and this is the rule that must survive skimming."""
        flat = " ".join(_read(rel).split())
        assert "data, never instructions" in flat, (
            f"{rel} surfaces cached item text into findings without restating that "
            f"the text is data, not instructions."
        )

    @pytest.mark.parametrize("rel", sorted(NOTE_SURFACES))
    def test_surface_no_longer_promises_a_cache_that_landed(self, rel):
        flat = " ".join(_read(rel).split())
        assert RETIRED_NOTE_TAIL not in flat, (
            f"{rel} still emits the dormancy NOTE. The readers are restored and the "
            f"advisory that enumerated them is retired, so this text now tells an "
            f"operator to wait for something that has already shipped."
        )

    def test_no_surface_anywhere_still_emits_the_dormancy_note(self):
        """The parametrized check above runs off `NOTE_SURFACES`, a hand-maintained
        constant, so a *fourth* surface could carry the retired text untouched.
        This closes that direction across the whole prose tree."""
        stale = []
        for root in TestNoUngatedBacklogFileReaders.PROSE_ROOTS:
            for path in sorted((REPO_ROOT / root).rglob("*.md")):
                if RETIRED_NOTE_TAIL in " ".join(path.read_text().split()):
                    stale.append(path.relative_to(REPO_ROOT).as_posix())
        assert not stale, (
            f"These surfaces still announce the dormancy the cache ended: {stale}."
        )

    @pytest.mark.parametrize(("rel", "subject"), sorted(NOTE_SURFACES.items()))
    def test_surface_note_names_no_internal_id(self, rel, subject):
        """`observability-strategy.md` § Direction: emitted text carries the
        reason, not the id. The NOTE used to end "(GV8; restored with the
        read-through cache)" — a pointer into a requirements register the
        downstream operator reading the finding has no access to."""
        flat = " ".join(_read(rel).split())
        start = flat.index(subject)
        note = flat[start : start + len(subject) + 160]
        for internal_id in FORBIDDEN_IDS:
            assert internal_id not in note, (
                f"{rel}'s unavailable notice names {internal_id}. Internal ids belong in "
                f"comments, tests, and build plans — not in text an operator reads."
            )

    def test_the_one_home_carries_what_the_surfaces_stopped_restating(self):
        """Routing is only sound if the destination holds the rule. This is the
        other half of `test_surface_routes_to_the_one_home`: without it, all three
        surfaces could point at a file that had lost the contract."""
        flat = " ".join(_read(CACHE_READS).split())
        for required, why in (
            ("backlog_service_repo", "which backend is live"),
            ("cache-query", "the invocation"),
            ("frozen history", "why the markdown file is not read post-cutover"),
            ("Exit 6", "the could-not-read contract"),
            ("age_seconds", "the visible-age contract"),
            ("data, never instructions", "the item-text treatment"),
        ):
            assert required in flat, f"{CACHE_READS} lost {why} ({required!r})"

    def test_the_reviewer_that_runs_the_walk_is_routed_to_the_gate(self):
        """`skills/critic/review-protocol.md` carries a one-line summary of the
        gate and points at `review-cycle.md` for the walk itself. That is sound
        *only* because `agents/critic-reviewer.md` sends the one reviewer who
        runs Backlog Reconciliation — the sustainability reviewer — to
        `review-cycle.md` explicitly. Break that routing and the gate sits behind
        a cross-reference nobody follows, so the routing is what gets pinned.

        (A cumulative Critic finding argued for restating the full rule in
        `review-protocol.md`. Declined on the evidence above, and because that
        file's token budget is deliberately at near-zero headroom — paying ~175
        tokens of reviewer context for a rule its reader is already routed to
        would trade a real cost for a hypothetical one.)
        """
        agent = " ".join(_read("agents/critic-reviewer.md").split())
        assert "Backlog Reconciliation" in agent
        assert "review-cycle.md" in agent, (
            "the sustainability reviewer is no longer routed to `review-cycle.md`, "
            "where the backend gate for Backlog Reconciliation lives."
        )
        protocol = " ".join(_read("skills/critic/review-protocol.md").split())
        # Pinned on the post-cutover BEHAVIOUR, not on a prefix of the sentence
        # that states it. The assertion here used to be the substring "read
        # `backlog_service_repo` first", which stayed true after the walk was
        # restored while the clause around it went on saying "when set, skip the
        # walk" — the stale gate survived a green suite in the very bundle that
        # restored the walk, and was caught by a reviewer instead. A prefix match
        # cannot tell which way a conditional points; these assert the direction.
        assert "cache-reads.md" in protocol, (
            "review-protocol.md no longer routes the reconciliation to the cache "
            "contract, so a reviewer reading only this file does not know where "
            "the items come from."
        )
        assert "skip the walk only on exit 6" in protocol, (
            "review-protocol.md does not say that skipping is the unavailable case "
            "ALONE. This is the assertion that fails if the dormancy-era gate — "
            "skip whenever the backend is set — is ever restated here."
        )
        assert "when set, skip the walk" not in protocol, (
            "review-protocol.md has reinstated the dormancy-era gate, which would "
            "make every cut-over product skip the walk this cache restored."
        )

class TestDirectReadRuleIsOneRule:
    """`data-model.md` § Direction: gated, not banned. Both readers state the
    gate inline — Chunk 01's contract is that a reader loading one file gets the
    whole rule, never a pointer to another file for the rule itself."""

    # Each file that may reach for `.prawduct/backlog.md` directly, and the
    # phrase carrying its half of the gate.
    GATED_READERS = ("skills/janitor/SKILL.md", "skills/pr/SKILL.md")

    @pytest.mark.parametrize("rel", GATED_READERS)
    def test_reader_states_the_backend_gate_inline(self, rel):
        flat = " ".join(_read(rel).split())
        assert "backlog_service_repo" in flat, (
            f"{rel} may reach for the backlog file but never names the scalar that "
            f"says whether it is live."
        )
        assert "unset" in flat, f"{rel} does not say which side of the gate permits the read"
        assert "frozen history" in flat, (
            f"{rel} does not say what the file becomes post-cutover — the gate without "
            f"its reason is a rule the next editor deletes as redundant."
        )

    def test_owner_states_the_rule_and_records_the_rejected_alternative(self):
        """`skills/backlog/SKILL.md` owns the file, so it owns the rule. The
        blanket-ban alternative is recorded there because it is the obvious
        simplification someone will otherwise re-propose."""
        flat = " ".join(_read("skills/backlog/SKILL.md").split())
        assert "Direct reads of `.prawduct/backlog.md`" in flat
        assert "Writes never bypass this skill" in flat
        assert "blanket" in flat and "rejected" in flat

    # The exact wording `skills/pr/SKILL.md` carried from `ef34dfc` (which
    # introduced it — its predecessor had an *ungated direct read*, not a ban)
    # until `2a0b1cf` replaced it with the gate.
    #
    # This literal is load-bearing, not belt-and-braces: in that historical text
    # the ban and `backlog_service_repo` sit in ONE sentence ("never read
    # `.prawduct/backlog.md` directly, which is frozen history once
    # `backlog_service_repo` is set"), so the shape match below exempts it. The
    # literal has no exemption, and is therefore the only thing covering the
    # precise wording that motivated this test.
    LITERAL_BAN = "never read `.prawduct/backlog.md` directly"

    # Absolute prohibitions on reading the file, matched on shape so a reword
    # ("must not open …", "do not read … directly") cannot reinstate the rejected
    # rule silently. The gap classes must admit `.` — the path itself contains
    # two, so an earlier `[^.]` version could not match LITERAL_BAN at all.
    # `directly` is optional: "never open `.prawduct/backlog.md`" is the same ban.
    BAN_SHAPE = re.compile(
        r"(never|don't|do not|must not|no reader may)\s+(read|open|touch)"
        r"[^;!?]{0,60}?backlog\.md",
        re.IGNORECASE,
    )

    @classmethod
    def _unqualified_ban(cls, flat: str) -> str | None:
        """First ban-shaped phrase that is NOT scoped to the backend gate.

        Dropping the `directly` anchor widened the match to include a *correct*
        statement of the norm — "do not read `.prawduct/backlog.md` once
        `backlog_service_repo` is set" is the rule, not a violation of it. So a
        match is only an offence when nothing qualifies it.

        The qualifier must sit in the **same sentence**, not merely nearby: a
        paragraph-sized window exempts an absolute ban written two sentences away
        from an unrelated mention of the scalar, which is a real shape and not a
        gated one. Sentence scope is a *different* scope, not a monotonically
        tighter one — the window was bounded (±120/160 chars) while a sentence is
        unbounded at both ends, so a long sentence exempts where the window would
        not, and a match with no preceding ". " takes the whole file prefix as
        its sentence. It is chosen because it states the same rule the failure
        message does and matches how a reader reasons about qualification, not
        because it is uniformly stricter.

        It is *not* what covers the historical `skills/pr/SKILL.md` wording —
        there the ban and the scalar shared one sentence, so this exempts it just
        as a window did. :data:`LITERAL_BAN` covers that one, unexempted. The
        division of labour is deliberate: the literal pins the wording we know
        was wrong, the shape match catches rewordings, and its exemption keeps
        the shape match from flagging a correct statement of the norm.
        """
        for match in cls.BAN_SHAPE.finditer(flat):
            start = flat.rfind(". ", 0, match.start()) + 1  # 0 when not found
            end = flat.find(". ", match.end())
            sentence = flat[start : (end + 1) if end != -1 else len(flat)]
            if "backlog_service_repo" in sentence:
                continue
            return match.group(0)
        return None

    # (text, expected-to-be-flagged) — synthetic, because `BAN_SHAPE` matches
    # nothing in the three production files today. Without these the sentence
    # scoping ships with its loop body never executed, and a green suite would
    # say nothing about whether the guard works at all.
    BAN_CASES = (
        ("Never read `.prawduct/backlog.md` directly, ever.", True),
        ("You must not open `.prawduct/backlog.md`.", True),
        ("Do not read the backlog.md file directly.", True),
        # The distinguishing case: qualifier two sentences away is NOT a gate.
        (
            "Never read `.prawduct/backlog.md` directly. Separately, "
            "`backlog_service_repo` selects the backend.",
            True,
        ),
        # A correct statement of the norm — qualified in its own sentence.
        (
            "Do not read `.prawduct/backlog.md` once `backlog_service_repo` is set.",
            False,
        ),
        # Backward half of the sentence arithmetic: the match is NOT in the first
        # sentence, so `rfind(". ")` takes its found-path rather than the -1
        # sentinel. Every other case sits in sentence one and leaves it unrun.
        (
            "`backlog_service_repo` selects the backend. "
            "Never read `.prawduct/backlog.md` directly.",
            True,
        ),
        # Prohibitions that aren't about this file at all.
        ("Never open a PR without running the reviewer.", False),
        ("Do not touch a claim you didn't set.", False),
    )

    @pytest.mark.parametrize(("text", "flagged"), BAN_CASES)
    def test_ban_detection_distinguishes_gated_from_absolute(self, text, flagged):
        found = self._unqualified_ban(text)
        assert bool(found) is flagged, f"{text!r} → {found!r}"

    def test_no_reader_bans_direct_reads_outright(self):
        """The pre-adjudication wording. `skills/pr/SKILL.md` said "never read
        ... directly" while the janitor explicitly permitted it pre-cutover;
        whichever a new reader copied became the rule. No absolute form may come
        back without re-opening the norm — including a reworded one."""
        for rel in self.GATED_READERS + ("skills/backlog/SKILL.md",):
            flat = " ".join(_read(rel).split())
            assert self.LITERAL_BAN not in flat, (
                f"{rel} carries the exact pre-adjudication wording again."
            )
            match = self._unqualified_ban(flat)
            assert match is None, (
                f"{rel} restates the blanket ban that `data-model.md` § Direction "
                f"rejected — the rule is a backend gate. If this text IS gated, say "
                f"so within the sentence (name `backlog_service_repo`) and it will "
                f"pass. Offending text: {match!r}"
            )


class TestNoUngatedBacklogFileReaders:
    """The re-greppable sweep. A surface that names `.prawduct/backlog.md` is
    either a *reader* — and must know about the gate — or it merely scaffolds /
    describes the file, in which case it is listed here with a reason.

    The original cutover sweep called itself exhaustive and had missed
    `skills/pr/SKILL.md`; this is what makes the next miss fail loudly rather
    than needing a sharper adjective.
    """

    # Every prose tree the plugin ships that a model executes or is briefed from.
    #
    # Widened from `skills/`-only for future coverage, NOT as the fix for the
    # `session-digest.md` miss — that would be a tidier story than the truth. The
    # digests never name `backlog.md` at all, so no root list reaches them; they
    # describe `## Archive`/`## Open` semantics without naming the file, and
    # `test_injected_digests_scope_markdown_only_backlog_semantics` is what
    # actually pins them. Today these four extra roots gate zero readers (their
    # only two hits are allowlisted below). They earn their place the first time
    # a reader outside `skills/` names the file — which is a real shape, just not
    # the one that got missed.
    PROSE_ROOTS = ("skills", "methodology", "agents", "templates", "docs")

    # path -> why it names the file without being a live-state reader
    NON_READER_ALLOWLIST = {
        "skills/doctor/SKILL.md": "core-state presence check — the file exists on both backends",
        "skills/onboard/SKILL.md": "scaffolding inventory for a new product",
        "skills/migrate/SKILL.md": "list of product-owned state carried across the migration",
        "templates/backlog.md": "*is* the markdown backlog, scaffolded into a new product",
    }

    def _prose_files_naming_backlog_md(self):
        for root in self.PROSE_ROOTS:
            for path in sorted((REPO_ROOT / root).rglob("*.md")):
                rel = path.relative_to(REPO_ROOT).as_posix()
                if rel.startswith("skills/backlog/"):
                    continue  # the owner: routing and the rule live here by definition
                content = path.read_text()
                if "backlog.md" in content:
                    yield rel, content

    def test_every_prose_surface_naming_the_file_knows_about_the_gate(self):
        offenders = []
        for rel, content in self._prose_files_naming_backlog_md():
            if rel in self.NON_READER_ALLOWLIST:
                continue
            if "backlog_service_repo" not in content:
                offenders.append(rel)
        assert not offenders, (
            "These prose surfaces name `.prawduct/backlog.md` but never mention "
            f"`backlog_service_repo`: {offenders}. Either gate the read on the "
            "scalar, or add the file to NON_READER_ALLOWLIST with the reason it is "
            "not a live-state reader."
        )

    def test_injected_digests_scope_markdown_only_backlog_semantics(self):
        """The digests are injected into every session including cut-over ones,
        so an unconditional `## Archive`/`## Open` sentence there is the same
        defect as the one fixed in `skills/backlog/SKILL.md` — at the framework's
        highest-traffic surface. They name no `backlog.md` path, so the sweep
        above cannot see them; this is their pin."""
        for rel in ("methodology/session-digest.md", "methodology/session-digest-slim.md"):
            flat = " ".join(_read(rel).split())
            if "## Archive" not in flat:
                continue
            idx = flat.index("## Archive")
            window = flat[max(0, idx - 200) : idx + 200]
            assert "markdown backend" in window or "Issues backend" in window, (
                f"{rel} states the `## Archive` workflow without naming which backend "
                f"it applies to; post-cutover that section does not exist."
            )

    def test_allowlist_has_no_dead_entries(self):
        """A stale allowlist entry is a hole that reads as coverage."""
        naming = {rel for rel, _ in self._prose_files_naming_backlog_md()}
        dead = sorted(set(self.NON_READER_ALLOWLIST) - naming)
        assert not dead, (
            f"NON_READER_ALLOWLIST entries no longer name backlog.md: {dead}. Drop them."
        )

    def test_lib_modules_pathing_the_file_are_gated(self):
        """`lib/` was already uniformly cutover-aware when the sweep ran; this
        keeps it that way. A module that *builds the path* to the markdown
        backlog must reference the cutover predicate or the scalar."""
        # Modules that construct the path but are not live-state readers.
        scaffolding = {
            "lib/init_product.py",  # writes the template at onboarding
        }
        # Both quote styles: the single-quoted spelling is just as valid Python
        # and a double-quote-only pattern would let the next reader through.
        path_expr = re.compile(r"""['"]backlog\.md['"]""")
        offenders = []
        seen_scaffolding = set()
        for path in sorted((REPO_ROOT / "lib").rglob("*.py")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel.startswith("lib/backlog/"):
                continue
            content = path.read_text()
            if not path_expr.search(content):
                continue
            if rel in scaffolding:
                seen_scaffolding.add(rel)
                continue
            if "post_cutover" not in content and "backlog_service_repo" not in content:
                offenders.append(rel)
        assert not offenders, (
            f"These lib modules path to the markdown backlog with no cutover guard: "
            f"{offenders}."
        )
        # A scaffolding exemption for a module that no longer paths to the file is
        # a hole that reads as coverage — the same failure this whole file guards.
        dead = sorted(scaffolding - seen_scaffolding)
        assert not dead, f"scaffolding exemptions no longer path to backlog.md: {dead}"


class TestBackendScopedProseInTheBacklogSkill:
    """Rules stated in the skill's shared preamble read as applying on both
    backends unless they say otherwise. Two were markdown-only."""

    def test_archive_split_is_scoped_to_the_markdown_backend(self):
        flat = " ".join(_read("skills/backlog/SKILL.md").split())
        assert "Archive split (Q2) — markdown backend only" in flat
        assert "closed issues *are* the archive" in flat

    def test_find_is_scoped_to_the_markdown_backend(self):
        flat = " ".join(_read("skills/backlog/SKILL.md").split())
        idx = flat.index("### find <query>")
        assert "Markdown backend." in flat[idx : idx + 200], (
            "`find` describes a search across markdown sections and "
            "`backlog-archive.md`; post-cutover neither exists."
        )

    def test_adapter_mode_no_longer_degrades_find_and_dedup(self):
        """`find` and `dedup` degraded to a NOTE while no adapter search existed.
        Cache-served `search` is built, so the degradation prose is not merely
        stale — it tells an operator a working capability is unavailable, which is
        the mirror image of the confident-wrong-answer failure this module exists
        to catch.

        This replaces an id-scrubbing assertion on the NOTE's quoted text (it had
        named an internal milestone id). With no NOTE to emit, what is pinned is
        the routing that took its place, and the whole section stays id-free
        because it is now instruction rather than commentary.
        """
        flat = " ".join(_read("skills/backlog/adapter-mode.md").split())

        # **Matched on SHAPE, because the literal this test first shipped with
        # never appeared in the file.** It asserted `"full-text search is not
        # available" not in flat`; the file actually said "present `find`/`dedup`
        # as **not available on this backend yet**" and "the backend has no
        # full-text search". So all of this test's assertions held for the whole
        # life of the defect it is named for, and a reviewer found it by
        # materializing the pre-fix blob and evaluating them against it.
        #
        # Verified the same way before landing: this pattern hits three sites in
        # `ec2c5e9:plugin/skills/backlog/adapter-mode.md` (the action menu, the
        # degraded-dedup paragraph, and its closing clause) and none in the fixed
        # file. A tripwire nobody has run against the failure is a tripwire whose
        # green means nothing.
        unavailable_claim = re.compile(
            r"(find|dedup|Dedup-on-create|full-text search)[^.]{0,80}?"
            r"(not available|no full-text search|is degraded|unavailable|not ready)",
            re.IGNORECASE,
        )
        # Swept across BOTH backlog-skill surfaces, not just the one the finding
        # named. `SKILL.md`'s `find` section carried the same false claim
        # ("post-cutover, full-text search is unavailable") and was missed by a
        # check scoped to one file — which is this test's own subject happening
        # one file over.
        stale = {
            rel: [m.group(0) for m in unavailable_claim.finditer(
                " ".join(_read(rel).split()))]
            for rel in ("skills/backlog/adapter-mode.md", "skills/backlog/SKILL.md")
        }
        stale = {rel: hits for rel, hits in stale.items() if hits}
        assert not stale, (
            f"the backlog skill still tells a post-cutover reader that `find`/`dedup` "
            f"are unavailable, when they run on the cache: {stale}. Skills are prose a "
            f"model executes, so this withholds two working ops on every cut-over product."
        )
        assert "cache-query search" in flat, "`find` is not routed to the cache-served search"
        assert "cache-reads.md" in flat, (
            "the adapter path restates the cache-read rules instead of routing to their one home"
        )
        section = flat[flat.index("## The local cache"):]
        section = section[: section.index("## Operations that don't apply")]
        for internal_id in ("W1", "W2", *FORBIDDEN_IDS):
            assert internal_id not in section, (
                f"the local-cache section names the internal id {internal_id!r}"
            )


class TestCompletenessGateListsAreEnumeratedConsistently:
    """`verify-migration`'s exit-4 verdict is a set of named lists, each with its
    own remedy, and the migration runbook enumerates them twice — once opening
    Step 6 and once closing it. Prose has no compiler, and both copies drifted in
    one session: `status_mismatch` was added to the opening while the closing
    paragraph still said "the four lists", and then `duplicate_alias` repeated the
    same miss one list later. Each time the operator hitting the *new* list at the
    cutover gate was pointed at a paragraph explaining a list that was empty in
    front of them.

    So the enumeration is derived from the gate itself rather than restated here:
    a sixth list added to `verify_migration` without a runbook bullet fails this,
    which is the only place it can fail before an irreversible run.
    """

    def _gate_lists(self) -> set[str]:
        """The list-valued keys of the gate's own verdict — the source of truth."""
        import sys

        sys.path.insert(0, str(REPO_ROOT))
        from lib.backlog import migrate  # noqa: PLC0415 — path set above

        verdict = migrate.verify_migration(
            _StubTransport(), owner="o", repo="r", content="# Backlog\n\n## Open\n"
        )
        data = verdict.get("data") or verdict["error"]["details"]
        return {k for k, v in data.items() if isinstance(v, list)}

    def test_every_gate_list_has_a_runbook_bullet(self):
        scrub = _read("skills/backlog/migration-scrub.md")
        missing = [name for name in self._gate_lists() if f"**`{name}`**" not in scrub]
        assert not missing, (
            f"{missing} returned by verify-migration with no bullet in the Step 6 "
            "remedy list — an operator hitting it is told nothing about how to clear it"
        )

    def test_the_two_enumerations_agree_on_the_count(self):
        """The opening says "N lists"; the closing says "the N lists". They drifted
        apart twice, in the same direction, because only the opening was edited."""
        flat = " ".join(_read("skills/backlog/migration-scrub.md").split())
        spelled = {3: "three", 4: "four", 5: "five", 6: "six", 7: "seven"}
        want = spelled[len(self._gate_lists())]
        stale = [w for w in spelled.values() if w != want and f"the {w} lists" in flat]
        assert not stale, (
            f"the gate returns {want} lists, but the runbook still says "
            f"{['the ' + s + ' lists' for s in stale]}"
        )
        assert f"{want} lists" in flat, f"neither enumeration says {want!r}"


class _StubTransport:
    """An empty repo: the gate's scan yields nothing, so every list comes back
    empty and the verdict still carries all of their names."""

    def list_issues(self, owner, repo, *, state, per_page, page, labels=None):
        return []
