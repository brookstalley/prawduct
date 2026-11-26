"""Guard the doctor↔janitor scope boundary (GOV-9K2T).

The boundary is documented in three places that must stay coherent: the canonical
`docs/doctor-vs-janitor.md`, and a mirrored `## Scope & boundary` summary in each of
`skills/doctor/SKILL.md` and `skills/janitor/SKILL.md` that points back to it. These
tests pin the structural invariants — the canonical doc exists, both skills carry the
summary and the pointer, and the two genuinely-shared concerns (API versioning, gitignore)
are cross-referenced in both directions — so a future edit can't silently drop one place
and leave the other dangling. They assert structure, not exact prose.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"

CANONICAL = "docs/doctor-vs-janitor.md"
DOCTOR = "skills/doctor/SKILL.md"
JANITOR = "skills/janitor/SKILL.md"
METHODOLOGY = "skills/methodology/SKILL.md"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class TestCanonicalDoc:
    def test_exists(self):
        assert (ROOT / CANONICAL).is_file(), f"{CANONICAL} (canonical boundary doc) is missing"

    def test_names_both_skills_and_placement_rule(self):
        src = _read(CANONICAL)
        assert "/prawduct:doctor" in src and "/prawduct:janitor" in src, (
            f"{CANONICAL} must name both skills"
        )
        assert "Placement rule" in src, (
            f"{CANONICAL} must carry the placement rule for where a new concern belongs"
        )

    def test_covers_the_two_shared_concerns(self):
        src = _read(CANONICAL).lower()
        assert "api versioning" in src, f"{CANONICAL} must cover the API-versioning shared concern"
        assert "gitignore" in src, f"{CANONICAL} must cover the gitignore shared concern"


class TestSkillMirrors:
    def test_doctor_has_scope_block_and_pointer(self):
        src = _read(DOCTOR)
        assert "## Scope & boundary" in src, f"{DOCTOR} must carry a `## Scope & boundary` summary"
        assert CANONICAL in src, f"{DOCTOR} must point to the canonical {CANONICAL}"
        assert "/prawduct:janitor" in src, f"{DOCTOR}'s scope block must route craft work to janitor"

    def test_janitor_has_scope_block_and_pointer(self):
        src = _read(JANITOR)
        assert "## Scope & boundary" in src, f"{JANITOR} must carry a `## Scope & boundary` summary"
        assert CANONICAL in src, f"{JANITOR} must point to the canonical {CANONICAL}"
        assert "/prawduct:doctor" in src, f"{JANITOR}'s scope block must route governance work to doctor"

    def test_methodology_index_lists_both_with_pointer(self):
        src = _read(METHODOLOGY)
        assert "/prawduct:doctor" in src and "/prawduct:janitor" in src, (
            f"{METHODOLOGY} overview must place both maintenance/health skills on the map"
        )
        assert CANONICAL in src, f"{METHODOLOGY} must point to the canonical {CANONICAL}"


class TestReconcileTaxonomy:
    """Both skills ask an owner to settle a batch of judgment calls, and they must
    ask the same way. Doctor's Norm Ratification Flow shipped the surface-by-exception
    taxonomy; janitor's Step 3 kept a flat "single confirm-or-correct block", which is
    the failure that taxonomy exists to prevent — a mature survey yields dozens of
    divergences and a flat wall gets a blanket yes (#239).
    """

    TIERS = ("clear-to-ratify", "needs-a-ruling")

    def test_doctor_still_carries_the_taxonomy_it_is_the_source_of(self):
        """The port has a source; if the source goes, this pair is no longer a pair."""
        src = _read(DOCTOR)
        for tier in self.TIERS:
            assert tier in src, (
                f"{DOCTOR}'s Norm Ratification Flow must carry the `{tier}` tier — "
                f"it is where this taxonomy is defined"
            )
        assert "Surface by exception" in src

    def test_janitor_reconcile_uses_the_same_two_tiers(self):
        src = _read(JANITOR)
        for tier in self.TIERS:
            assert tier in src, (
                f"{JANITOR}'s Step 3 must tag findings `{tier}` — the same names "
                f"doctor uses, so the taxonomy has one vocabulary rather than two"
            )
        assert "Surface by exception" in src, (
            f"{JANITOR}'s Step 3 must surface by exception, not as one flat block"
        )
        assert "confirm-or-correct block" not in src or "never a flat" in src, (
            f"{JANITOR} must not still instruct a flat confirm-or-correct block"
        )

    def test_the_janitor_bulk_confirm_states_a_count(self):
        """A bulk confirm without a count asks for a yes to an unstated quantity.

        Doctor's version names them compactly ("these N ... norms"); the port has
        to carry that guard, not just the tier names — the count is what tells an
        owner whether they are agreeing to three things or thirty.
        """
        src = _read(JANITOR)
        bulk = [
            line for line in src.splitlines() if "bulk-confirm" in line or "bulk confirm" in line
        ]
        assert bulk, f"{JANITOR}'s Step 3 must offer a bulk confirm for the clear tier"
        assert any("count" in line for line in bulk), (
            f"{JANITOR}'s bulk-confirm line must require the COUNT of what is being "
            f"confirmed; without it the owner cannot tell what they are agreeing to"
        )

    def test_an_unconfirmable_finding_is_filed_not_dropped(self):
        """Step 3 → Step 7 was open at the unresolved end (#285).

        A divergence the user cannot settle in-session had no stated destination,
        so it ended the run in conversation only — and the next janitor pays the
        survey cost to find it again, with nothing recording that anyone looked.
        """
        src = _read(JANITOR)
        assert "/prawduct:backlog" in src
        assert "cannot confirm" in src, (
            f"{JANITOR}'s Step 3 must say what happens when the user cannot "
            f"confirm — the finding becomes a backlog item, it does not evaporate"
        )


class TestGitignoreCrossReference:
    """The gitignore concern lives in both skills (doctor = prawduct contract, janitor =
    general hygiene); each must cross-reference the other so the split is discoverable."""

    def test_doctor_points_general_hygiene_to_janitor(self):
        src = _read(DOCTOR)
        assert "Version Control Hygiene" in src, (
            f"{DOCTOR}'s gitignore check must route general hygiene to the janitor's "
            "Version Control Hygiene theme"
        )

    def test_janitor_points_contract_to_doctor(self):
        src = _read("skills/janitor/themes.md")  # the theme taxonomy's companion file
        # Named, not numbered: doctor's list renumbers, and an ordinal then routes the
        # reader to the wrong check while this assertion stays green.
        assert "*Gitignore contract* check" in src, (
            "janitor themes.md's Version Control Hygiene theme must route the prawduct gitignore "
            "contract to /prawduct:doctor's Gitignore contract check, by name"
        )
        assert "Health-Check #8" not in src

    def test_the_health_check_grades_on_the_dry_run(self):
        """A read-only report must not be graded by a command that writes (#666).

        ``update-gitignore`` is mutating by default — deliberately, because its
        other callers want the repair applied — so a health check that runs it
        bare reconciles the file it was asked to inspect. The operator then
        cannot tell which findings were true before the check ran. The step must
        name ``--dry-run`` as what it grades on, and the grant must be able to
        pass the flag: ``Bash(prawduct-hook update-gitignore)`` is an exact
        match that cannot.
        """
        src = _read(DOCTOR)
        assert "update-gitignore --dry-run" in src, (
            f"{DOCTOR}'s gitignore check must grade on `update-gitignore --dry-run`; "
            "the bare command writes, and a health check that repairs silently "
            "destroys the evidence for its own report"
        )
        grant = next(
            line for line in src.splitlines() if line.startswith("allowed-tools:")
        )
        assert "Bash(prawduct-hook update-gitignore*)" in grant, (
            f"{DOCTOR} must grant `Bash(prawduct-hook update-gitignore*)` — the "
            "house grant form (star attached, no space). A bare grant is an exact "
            "match that cannot pass `--dry-run`, and a spaced star cannot run the "
            "repair form; only the attached star covers both."
        )


def _doctor_check(number: int) -> str:
    """The text of doctor's Health Check ``number``, up to the next numbered check."""
    src = _read(DOCTOR)
    start = src.index(f"\n{number}. **")
    nxt = src.find(f"\n{number + 1}. **", start)
    return src[start:nxt if nxt != -1 else len(src)]


def _doctor_flow(heading: str) -> str:
    src = _read(DOCTOR)
    start = src.index(f"## {heading}")
    nxt = src.find("\n## ", start + 1)
    return src[start:nxt if nxt != -1 else len(src)]


class TestDoctorRunsRepairsOnTheOwnersYes:
    """Doctor runs the repairs it offers once the owner says yes
    (`.prawduct/owner-rulings.md`, 2026-11-26). So each repair's failure output
    reaches the agent, and every text that describes doctor must say who acts."""

    #: A repair doctor runs -> (the failure line its handler prints, the file that
    #: prints it). Each line is asserted in that file too, so a renamed refusal
    #: fails here rather than leaving doctor naming a line nothing prints.
    FAILURE_LINES = {
        "archive-plan": ("not-archived:", "bin/prawduct-hook"),
        "coverage-scaffold": ("NOTE: could not write", "bin/prawduct-hook"),
        "lifecycle-repair": ("could not write", "bin/prawduct-hook"),
        "reanchor": ('STATUS_UNWRITABLE = "unwritable"', "lib/anchor_repair.py"),
    }

    def test_doctor_names_each_repairs_failure_line(self):
        src = _read(DOCTOR)
        for command, (source_line, origin) in self.FAILURE_LINES.items():
            line = source_line.split('"')[1] if '"' in source_line else source_line
            assert f"prawduct-hook {command}" in src, f"control: doctor runs `{command}`"
            assert source_line in _read(origin), f"{origin} no longer prints `{line}`; re-derive this row"
            assert line in src, f"{DOCTOR} runs `{command}` but never names its failure `{line}`"
        assert "never retry the repair" in src, (
            f"{DOCTOR} must say a failed repair is relayed, not retried around"
        )

    def test_coverage_scaffold_says_its_note_is_a_failure_under_exit_zero(self):
        check = _doctor_check(11)
        assert "coverage-scaffold" in check, "control: Check #11 was found"
        assert "NOTE: could not write" in check and "exits 0" in check, (
            "Check #11 must say `coverage-scaffold --apply` exits 0 while a stub went unwritten"
        )

    def test_a_vanished_claim_is_re_pointed_by_hand_not_by_plan_bind(self):
        """`plan_mint.bind` refuses a plan that already claims a branch, which is
        every plan Check #24 reports missing, so `plan bind` cannot be the repair."""
        check = _doctor_check(24)
        assert "plan check-claims" in check, "control: Check #24 was found"
        assert "prawduct-hook plan bind" not in check, (
            "Check #24 routes a re-point through `plan bind`, which refuses a claimed plan"
        )
        assert "plan-claims-other-branch" in check and "by hand" in check
        mint = (ROOT / "lib" / "plan_mint.py").read_text(encoding="utf-8")
        assert '"plan-claims-other-branch"' in mint, "the refusal Check #24 cites is gone from plan_mint"
        assert "plan bind" not in _read(DOCTOR).split("---", 2)[1], (
            "doctor still grants `plan bind`, which no step can use"
        )

    def test_archive_plan_is_previewed_before_the_owner_is_asked(self):
        for where, text in (("Check #24", _doctor_check(24)),
                            ("Lifecycle Convergence Flow", _doctor_flow("Lifecycle Convergence Flow"))):
            assert "archive-plan" in text, f"control: {where} runs archive-plan"
            assert "--dry-run" in text, f"{where} archives a plan without showing its --dry-run first"

    def test_the_boundary_doc_says_doctor_repairs_on_the_owners_yes(self):
        src = _read(CANONICAL)
        row = next(line for line in src.splitlines() if line.startswith("| **Action model**"))
        assert "owner's yes" in row, row
        for stale in ("owner-invoked", "auto-fix", "reported-and-guided"):
            assert stale not in src, f"{CANONICAL} still says doctor's repairs are {stale!r}"
        assert "reports-and-guides rather than fixes" not in _read(JANITOR)
