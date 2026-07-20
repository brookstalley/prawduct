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

    def test_reviewer_loaded_protocol_states_the_gate_inline(self):
        """`skills/critic/review-protocol.md` is the file the Critic's reviewer
        subagents actually load — `review-cycle.md` may never be opened. It
        carries the gate itself rather than deferring to the other file for it."""
        flat = " ".join(_read("skills/critic/review-protocol.md").split())
        assert "backlog_service_repo" in flat
        assert "unavailable" in flat

    def test_note_says_what_restores_the_checks(self):
        """Dropping the id must not drop the resolution: an operator told a check
        is dormant with no stated end-state reads it as permanent breakage."""
        assert "read-through cache" in NOTE_TAIL


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

    def test_no_reader_bans_direct_reads_outright(self):
        """The pre-adjudication wording. `skills/pr/SKILL.md` said "never read
        ... directly" while the janitor explicitly permitted it pre-cutover;
        whichever a new reader copied became the rule. Neither absolute form may
        come back without re-opening the norm."""
        for rel in self.GATED_READERS + ("skills/backlog/SKILL.md",):
            flat = " ".join(_read(rel).split())
            assert "never read `.prawduct/backlog.md` directly" not in flat, (
                f"{rel} restates the blanket ban that `data-model.md` § Direction "
                f"rejected — the rule is a backend gate."
            )


class TestNoUngatedBacklogFileReaders:
    """The re-greppable sweep. A surface that names `.prawduct/backlog.md` is
    either a *reader* — and must know about the gate — or it merely scaffolds /
    describes the file, in which case it is listed here with a reason.

    The original cutover sweep called itself exhaustive and had missed
    `skills/pr/SKILL.md`; this is what makes the next miss fail loudly rather
    than needing a sharper adjective.
    """

    # path -> why it names the file without being a live-state reader
    NON_READER_ALLOWLIST = {
        "skills/doctor/SKILL.md": "core-state presence check — the file exists on both backends",
        "skills/onboard/SKILL.md": "scaffolding inventory for a new product",
        "skills/migrate/SKILL.md": "list of product-owned state carried across the migration",
    }

    def _skill_files_naming_backlog_md(self):
        for path in sorted((REPO_ROOT / "skills").rglob("*.md")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel.startswith("skills/backlog/"):
                continue  # the owner: routing and the rule live here by definition
            if "backlog.md" in path.read_text():
                yield rel, path.read_text()

    def test_every_skill_naming_the_file_knows_about_the_gate(self):
        offenders = []
        for rel, content in self._skill_files_naming_backlog_md():
            if rel in self.NON_READER_ALLOWLIST:
                continue
            if "backlog_service_repo" not in content:
                offenders.append(rel)
        assert not offenders, (
            "These skill surfaces name `.prawduct/backlog.md` but never mention "
            f"`backlog_service_repo`: {offenders}. Either gate the read on the "
            "scalar, or add the file to NON_READER_ALLOWLIST with the reason it is "
            "not a live-state reader."
        )

    def test_allowlist_has_no_dead_entries(self):
        """A stale allowlist entry is a hole that reads as coverage."""
        naming = {rel for rel, _ in self._skill_files_naming_backlog_md()}
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
            "lib/migrate_plugin.py",  # carries product state across migration
        }
        path_expr = re.compile(r'"backlog\.md"')
        offenders = []
        for path in sorted((REPO_ROOT / "lib").rglob("*.py")):
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel.startswith("lib/backlog/") or rel in scaffolding:
                continue
            content = path.read_text()
            if not path_expr.search(content):
                continue
            if "post_cutover" not in content and "backlog_service_repo" not in content:
                offenders.append(rel)
        assert not offenders, (
            f"These lib modules path to the markdown backlog with no cutover guard: "
            f"{offenders}."
        )


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
