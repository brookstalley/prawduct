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
        src = _read(JANITOR)
        assert "Health-Check #8" in src, (
            f"{JANITOR}'s Version Control Hygiene theme must route the prawduct gitignore "
            "contract to /prawduct:doctor Health-Check #8"
        )

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
