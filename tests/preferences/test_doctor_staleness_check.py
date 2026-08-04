"""Doctor Health Check #15 (running plugin vs. what the marketplace offers).

This is the one health check whose subject sits outside the governed repo, which
makes it structurally fragile in ways the other fourteen are not:

* It reads **machine-level** files. Every other check reads the repo. If doctor's
  tool grant is ever narrowed to the project directory — a reasonable-looking
  tightening — the prose survives review while becoming an instruction its reader
  cannot execute. That exact failure has shipped here once already (Health Check
  #9's prose implied a grep its tool grant lacked), so the grant is asserted
  rather than assumed.
* Its inputs live under a config home that is **not** always ``~/.claude``. The
  machine this was written on runs three. A regression to a hardcoded path grades
  a different install than the one governing the session and reports healthy while
  doing it.
* Three of its five outcomes are *not* "healthy", and two of those are easy to
  collapse into one during an edit: a ``directory:`` marketplace is **ungradeable**
  (the comparison is a tree against itself) and a failed read is **degraded because
  ungraded**. Either collapsing into "healthy" reintroduces the silence the check
  exists to break.

These assert properties, not phrasing. Each was verified red against a mutation
that a reviewer would plausibly wave through — see the docstring on each test for
the specific mutation used.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent.parent.parent / "plugin"
DOCTOR = PLUGIN / "skills" / "doctor" / "SKILL.md"

_FLOW_HEADING = "## Health Check Flow"
_CLASSIFY = "Classify and report:"


def _doctor_text() -> str:
    return DOCTOR.read_text(encoding="utf-8")


def _flow_body(text: str) -> str:
    """The numbered-check list only, between its heading and the classify block."""
    start = text.index(_FLOW_HEADING)
    end = text.index(_CLASSIFY, start)
    return text[start:end]


def _check_block(text: str, number: int) -> str:
    """One numbered check's full body, including its indented sub-bullets."""
    body = _flow_body(text)
    match = re.search(rf"^{number}\. \*\*.*?(?=^\d+\. \*\*|\Z)", body, re.MULTILINE | re.DOTALL)
    assert match, f"Health Check #{number} not found in the flow"
    return match.group(0)


def _allowed_tools() -> list[str]:
    """The skill's declared tool grant, as written in its YAML frontmatter."""
    text = _doctor_text()
    match = re.search(r"^allowed-tools:\s*(.+)$", text, re.MULTILINE)
    assert match, "doctor SKILL.md has no allowed-tools line"
    return [entry.strip() for entry in match.group(1).split(",")]


class TestCheckIsPresentAndNumbered:
    def test_flow_numbering_is_consecutive(self) -> None:
        """Gaps or duplicates mean an insert landed wrong.

        Verified red by renumbering #15 to #16 (leaving a gap at 15).
        """
        numbers = [int(n) for n in re.findall(r"^(\d+)\. \*\*", _flow_body(_doctor_text()), re.MULTILINE)]
        assert numbers == list(range(1, len(numbers) + 1)), (
            f"Health Check Flow numbering is not consecutive: {numbers}"
        )

    def test_staleness_check_exists(self) -> None:
        """Verified red by deleting the check."""
        block = _check_block(_doctor_text(), 15)
        assert "marketplace" in block.lower(), (
            "Health Check #15 must be the running-plugin-vs-marketplace check"
        )

    def test_classify_block_accounts_for_a_behind_install(self) -> None:
        """A check whose outcome no grade mentions cannot change the report.

        Verified red by deleting the 'running plugin behind' clause from the
        degraded bullet while leaving the check itself intact.
        """
        text = _doctor_text()
        degraded = next(
            line for line in text.splitlines() if line.startswith("- **degraded**")
        )
        assert "behind" in degraded, (
            "the degraded grade must enumerate a running plugin behind its marketplace, "
            "or Check #15's central finding maps to no reportable grade"
        )


class TestReaderCanActuallyRunIt:
    """The doctor #9 precedent: prose must not outrun the tool grant."""

    def test_read_is_granted_unrestricted(self) -> None:
        """Check #15 reads paths outside the repo; a scoped Read grant breaks it.

        Verified red by rewriting the grant's bare ``Read`` to
        ``Read(.prawduct/**)`` — the plausible tightening this guards against.
        """
        assert "Read" in _allowed_tools(), (
            "doctor's allowed-tools must grant Read unrestricted — Health Check #15 "
            "reads machine-level files outside the project directory, and a "
            "path-scoped grant would make its prose unexecutable"
        )


class TestOutcomesThatAreNotHealthy:
    @pytest.fixture
    def block(self) -> str:
        return _check_block(_doctor_text(), 15)

    def test_config_home_is_resolved_not_hardcoded(self, block: str) -> None:
        """Verified red by replacing the CLAUDE_CONFIG_DIR sentence with '~/.claude'."""
        assert "CLAUDE_CONFIG_DIR" in block, (
            "Check #15 must resolve the config home via CLAUDE_CONFIG_DIR; hardcoding "
            "~/.claude grades a different install than the one governing the session"
        )

    def test_directory_source_is_not_graded(self, block: str) -> None:
        """A `directory:` marketplace compares a tree against itself.

        Verified red by changing that bullet's verdict from 'not graded' to
        'healthy' — the collapse this guards against, which would report a
        maintainer's checkout as a verified-current install.
        """
        directory_bullet = next(
            (line for line in block.splitlines() if "`directory`" in line), None
        )
        assert directory_bullet is not None, (
            "Check #15 must handle a directory-source marketplace explicitly"
        )
        assert "not graded" in directory_bullet, (
            "a directory-source marketplace must route to *not graded*, never healthy: "
            "installLocation is the checkout itself, so the comparison answers nothing"
        )

    def test_failed_reads_are_ungraded_never_healthy(self, block: str) -> None:
        """Verified red by deleting 'degraded because ungraded' from the bullet."""
        assert "degraded because ungraded" in block, (
            "Check #15 must grade an unreadable input as degraded-because-ungraded, "
            "matching Checks #11, #13 and #14 — a check that could not run is otherwise "
            "indistinguishable from one that ran and found nothing"
        )


class TestLimitationIsStated:
    def test_cache_key_blind_spot_is_disclosed(self) -> None:
        """The check cannot see a release that shipped without bumping `version`.

        That is the failure the release runbook warns about hardest, and the field
        this check reads is precisely the one that did not change. Claiming
        coverage it does not have is worse than the gap.

        Verified red by deleting the limitation paragraph.
        """
        block = _check_block(_doctor_text(), 15)
        assert "cache key" in block, (
            "Check #15 must disclose that `version` is the update cache key, and that a "
            "release which shipped a new tree without bumping it is invisible here"
        )

    def test_expected_yield_is_named(self) -> None:
        """Proportionality (nonfunctional-requirements.md § Direction) requires a new
        control to name the yield it expects, so it can later be retired on evidence
        rather than defended on principle.

        Verified red by deleting the expected-yield paragraph.
        """
        block = _check_block(_doctor_text(), 15)
        assert "Expected yield" in block, (
            "a new doctor check must name its expected yield — it inherits Check #13's "
            "bounded exception to the *emission* arm, not to the naming arm"
        )
