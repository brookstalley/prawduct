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

REPO_ROOT = Path(__file__).resolve().parents[1]

# The invariant tail of the dormancy NOTE. Only the leading subject differs per
# surface ("Backlog reconciliation unavailable" / "Backlog Health unavailable"),
# so the tail is what must be byte-identical.
NOTE_TAIL = (
    "this project is on the GitHub Issues backend and these checks have no "
    "Issues-mode path yet; they return when the backlog read-through cache lands."
)

# Every surface that emits the dormancy NOTE, and the subject it leads with.
NOTE_SURFACES = {
    "skills/critic/review-cycle.md": "Backlog reconciliation unavailable",
    "skills/pr/review-protocol.md": "Backlog reconciliation unavailable",
    "skills/janitor/SKILL.md": "Backlog Health unavailable",
}

# Internal identifiers that must not reach an operator's screen. Not an
# exhaustive vocabulary — prefixes are open-ended, which is exactly why the
# durable enforcement is the Critic's judgment and this list only pins the
# copies a past changeset actually got wrong.
FORBIDDEN_IDS = ("GV8", "W1", "W2", "GV7")


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text()


class TestDormancyNoteCopiesAgree:
    """The NOTE is copied, not referenced — so its copies need a pin."""

    @pytest.mark.parametrize(("rel", "subject"), sorted(NOTE_SURFACES.items()))
    def test_surface_emits_the_invariant_note_tail(self, rel, subject):
        content = _read(rel)
        # Prose wraps at the author's discretion, so compare on collapsed
        # whitespace rather than demanding a particular line break.
        flat = " ".join(content.split())
        assert subject in flat, f"{rel} no longer leads the dormancy NOTE with its subject"
        assert NOTE_TAIL in flat, (
            f"{rel}'s dormancy NOTE has drifted from the shared tail. Update every "
            f"surface in NOTE_SURFACES together, or the three readers start telling "
            f"an operator three different things about one backend state."
        )

    @pytest.mark.parametrize(("rel", "subject"), sorted(NOTE_SURFACES.items()))
    def test_surface_note_names_no_internal_id(self, rel, subject):
        """`observability-strategy.md` § Direction: emitted text carries the
        reason, not the id. The NOTE used to end "(GV8; restored with the
        read-through cache)" — a pointer into a requirements register the
        downstream operator reading the finding has no access to."""
        flat = " ".join(_read(rel).split())
        start = flat.index(subject)
        note = flat[start : start + len(subject) + len(NOTE_TAIL) + 8]
        for internal_id in FORBIDDEN_IDS:
            assert internal_id not in note, (
                f"{rel}'s dormancy NOTE names {internal_id}. Internal ids belong in "
                f"comments, tests, and build plans — not in text an operator reads."
            )

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
        assert "read `backlog_service_repo` first" in protocol, (
            "review-protocol.md dropped its summary of the gate, so a reviewer "
            "reading only this file gets no signal that the walk is conditional."
        )

    def test_every_note_surface_is_in_the_advisory_enumeration(self):
        """The advisory's stated value is that anyone dismissing it knows what
        they are choosing to run without. That rests on an enumeration which,
        being hand-maintained, can silently fall behind the readers it names —
        under-reporting, which is this bundle's own failure class one layer down.

        So: a surface that emits a dormancy NOTE must appear in
        `DORMANT_CHECKS`, and the advisory's count must derive from it rather
        than being written out.
        """
        from lib import backlog_probes as bp

        enumerated = {rel for surfaces, _ in bp.DORMANT_CHECKS for rel in surfaces}
        missing = sorted(set(NOTE_SURFACES) - enumerated)
        assert not missing, (
            f"These surfaces state dormancy but are absent from the advisory's "
            f"enumeration: {missing}. Add them to `DORMANT_CHECKS` in "
            f"`lib/backlog_probes.py` — the advisory is the operator's only list of "
            f"what a cut-over repo is running without."
        )

    def test_no_surface_emits_the_note_without_being_declared(self):
        """The coupling above runs off `NOTE_SURFACES`, a hand-maintained
        constant — so a *fourth* production surface emitting the NOTE would
        satisfy every test here while never reaching the advisory's enumeration.
        This closes the other direction: any prose file carrying the tail must be
        declared, which forces the enumeration check to see it."""
        undeclared = []
        for root in TestNoUngatedBacklogFileReaders.PROSE_ROOTS:
            for path in sorted((REPO_ROOT / root).rglob("*.md")):
                rel = path.relative_to(REPO_ROOT).as_posix()
                if rel in NOTE_SURFACES:
                    continue
                if NOTE_TAIL in " ".join(path.read_text().split()):
                    undeclared.append(rel)
        assert not undeclared, (
            f"These surfaces emit the dormancy NOTE but are not in NOTE_SURFACES: "
            f"{undeclared}. Declare them, and add them to `DORMANT_CHECKS` — an "
            f"undeclared surface is a check the advisory never tells anyone is dark."
        )

    def test_advisory_count_and_evidence_derive_from_one_list(self):
        from lib import backlog_probes as bp
        from lib.advisory_store import Codebase, ProjectState

        candidate = bp.probe_checks_dormant(
            ProjectState({"backlog_service_repo": "acme/widgets"}),
            Codebase(root=REPO_ROOT),
        )[0]
        assert (
            f"{len(bp.DORMANT_CHECKS)} backlog checks are dormant" in candidate.trigger_summary
        )
        for _, name in bp.DORMANT_CHECKS:
            assert name in candidate.evidence[0], (
                f"{name!r} is enumerated but never reaches the operator's evidence line."
            )

    def test_advisory_enumeration_names_no_internal_check_label(self):
        """`observability-strategy.md` § Direction, applied to the string this
        bundle itself wrote: the evidence line named `C-B1-C-B4` and `R-1`/`R-2`,
        which an operator downstream cannot resolve any better than `GV8`."""
        from lib import backlog_probes as bp
        from lib.advisory_store import Codebase, ProjectState

        candidate = bp.probe_checks_dormant(
            ProjectState({"backlog_service_repo": "acme/widgets"}),
            Codebase(root=REPO_ROOT),
        )[0]
        emitted = (
            candidate.evidence[0] + candidate.trigger_summary + candidate.recommended_action
        )
        for label in ("C-B1", "C-B4", "R-1", "R-2", *FORBIDDEN_IDS):
            assert label not in emitted, (
                f"the dormancy advisory emits the internal label {label!r}"
            )

    def test_note_states_the_resolution_not_just_the_dormancy(self):
        """Dropping the id must not drop the resolution: an operator told a check
        is dormant with no stated end-state reads it as permanent breakage.

        Asserted against the files, not against this module's own constant — an
        assertion about `NOTE_TAIL` cannot fail for any production edit.
        """
        for rel in NOTE_SURFACES:
            flat = " ".join(_read(rel).split())
            assert "they return when the backlog read-through cache lands" in flat, (
                f"{rel}'s dormancy NOTE states the gap without its end-state."
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

    # The exact wording `skills/pr/SKILL.md` carried until `ef34dfc`. Kept as a
    # literal alongside the shape match below, because a shape match is the thing
    # that quietly stops covering its own motivating case.
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
            match = self.BAN_SHAPE.search(flat)
            assert match is None, (
                f"{rel} restates the blanket ban that `data-model.md` § Direction "
                f"rejected — the rule is a backend gate. Offending text: "
                f"{match.group(0)!r}"
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
        "docs/project-structure.md": "directory-layout diagram — names the file, instructs no read",
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

    def test_adapter_mode_find_note_is_id_free(self):
        """The NOTE the adapter path emits when `find` is unavailable is
        operator-facing text and was naming an internal milestone id.

        Scoped to the *quoted* NOTE, not the whole section: the surrounding
        instruction prose still says "dedup is W2" and legitimately may — the
        norm governs what a skill emits, not what it reads.
        """
        flat = " ".join(_read("skills/backlog/adapter-mode.md").split())
        opening = "full-text search is not available on the Issues backend yet"
        assert opening in flat, "the emitted find NOTE no longer states the unavailability"
        start = flat.index(opening)
        end = flat.index('"', start)  # the NOTE's closing quote
        note = flat[start:end]
        assert "W2" not in note, "the emitted find NOTE names an internal id"
