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

        Both tokens are required rather than the bare word "behind", which the
        degraded bullet could plausibly carry for an unrelated reason.

        Verified red by deleting the 'running plugin behind' clause from the
        degraded bullet while leaving the check itself intact.
        """
        text = _doctor_text()
        degraded = next(
            line for line in text.splitlines() if line.startswith("- **degraded**")
        )
        assert "behind" in degraded and "marketplace" in degraded, (
            "the degraded grade must enumerate a running plugin behind its marketplace, "
            "or Check #15's central finding maps to no reportable grade"
        )


class TestReaderCanActuallyRunIt:
    """The doctor #9 precedent: prose must not outrun the tool grant.

    Both halves of Check #15's input path are covered here, because the first
    review of this check found the second half broken — the prose told the reader
    to consult ``$CLAUDE_CONFIG_DIR`` under a heading promising no Bash was
    needed, and doctor grants no general Bash, so the step had no execution path
    on any machine where the answer mattered.
    """

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

    def test_config_dir_lookup_has_an_execution_path(self) -> None:
        """The config home cannot be resolved by Read/Glob alone.

        ``$CLAUDE_CONFIG_DIR`` is an environment variable, not a load-time prose
        placeholder like ``${CLAUDE_SKILL_DIR}``, so reading it takes a Bash call
        that the grant must actually permit.

        Verified red by removing the ``Bash(printenv CLAUDE_CONFIG_DIR)`` grant.
        """
        grants = _allowed_tools()
        assert any("CLAUDE_CONFIG_DIR" in g and g.startswith("Bash(") for g in grants), (
            "Check #15 must be able to read CLAUDE_CONFIG_DIR, which needs a Bash grant — "
            "without one the reader can only assume ~/.claude, which the check forbids "
            "and which grades a different install than the one governing the session"
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
        assert "not graded" in directory_bullet.lower(), (
            "a directory-source marketplace must route to *not graded*, never healthy: "
            "installLocation is the checkout itself, so the comparison answers nothing"
        )

    def test_ungradeable_cases_are_decided_before_the_comparison(self, block: str) -> None:
        """Ordering is the property, not presence.

        A ``directory:`` marketplace makes the two versions equal *by
        construction*, so if ``Equal -> healthy`` is reachable before the
        not-graded gate, a reader executing top-down reports healthy and never
        arrives at the bullet that forbids it. Presence of both bullets is not
        enough; the gate has to come first.

        Verified red by moving the directory gate back below the comparison
        outcomes — the exact arrangement the first review caught.
        """
        directory_at = block.find("`directory`")
        equal_at = block.find("Equal")
        assert directory_at != -1 and equal_at != -1, (
            "Check #15 must contain both the directory-source gate and the equal outcome"
        )
        assert directory_at < equal_at, (
            "the directory-source gate must be decided BEFORE the equal/healthy outcome: "
            "a directory marketplace compares a tree against itself and is equal by "
            "construction, so a reader going in order would stop at healthy"
        )

    def test_both_versions_are_tied_to_one_install(self, block: str) -> None:
        """Reading two unrelated installs and comparing them is a wrong answer.

        ``${CLAUDE_SKILL_DIR}`` names the plugin that loaded the skill;
        ``known_marketplaces.json`` names whatever the marketplace installed.
        Under ``--plugin-dir`` alongside an enabled marketplace install those are
        different trees, and comparing them can report "behind" to someone
        running newer code.

        Verified red by deleting the same-install gate.
        """
        assert "is_managed_install" in block, (
            "Check #15 must establish that the running plugin and the marketplace entry "
            "describe the SAME install before comparing their versions — banner.py's "
            "is_managed_install() is the path comparison that settles it"
        )

    def test_failed_reads_are_ungraded_never_healthy(self, block: str) -> None:
        """Verified red by deleting 'degraded because ungraded' from the bullet."""
        assert "degraded because ungraded" in block, (
            "Check #15 must grade an unreadable input as degraded-because-ungraded, "
            "matching Checks #11, #13 and #14 — a check that could not run is otherwise "
            "indistinguishable from one that ran and found nothing"
        )


class TestComparisonMechanics:
    """The three properties that decide whether the answer is right, not just present."""

    @pytest.fixture
    def block(self) -> str:
        return _check_block(_doctor_text(), 15)

    def test_snapshot_plugin_dir_is_read_from_the_manifest(self, block: str) -> None:
        """Hardcoding `plugin/` is the failure Check #1 already paid for.

        The snapshot's plugin directory is declared by the marketplace manifest's
        `source` field; it is not a fixed path prawduct may transcribe.

        Verified red by rewriting the step to read `<installLocation>/plugin/`
        directly and dropping the marketplace.json lookup.
        """
        assert "marketplace.json" in block and "source" in block, (
            "Check #15 must find the snapshot's plugin directory through the DECLARED "
            "`source` in marketplace.json, never a hardcoded plugin/ path"
        )

    def test_version_comparison_is_numeric(self, block: str) -> None:
        """`3.10.0` vs `3.9.0` is where a string compare silently inverts.

        This is the one arithmetic claim in an otherwise structural check, and it
        fails in the direction that reports a behind install as current.

        Verified red by deleting the numeric-comparison sentence.
        """
        assert "numerically" in block, (
            "Check #15 must specify a numeric semver comparison — a string comparison "
            "ranks 3.9.0 above 3.10.0 and would report a behind install as ahead"
        )

    def test_snapshot_stale_is_a_distinct_finding(self, block: str) -> None:
        """Running-newer is not the same finding as running-behind.

        Collapsing it into "you are behind" sends an operator to update an install
        that is already ahead of what the marketplace holds.

        Verified red by deleting the running-newer bullet.
        """
        assert "snapshot" in block and "stale" in block, (
            "Check #15 must report an install NEWER than its snapshot as a stale-snapshot "
            "finding, distinct from the behind-install one"
        )


class TestExceptionIsNotSelfGranted:
    def test_proportionality_relief_points_outward(self) -> None:
        """A control may not grant itself an exception to a ratified norm.

        The first review of this check escalated exactly this past WARNING: the
        claim to hold Check #13's bounded exception was written inside the check
        that benefited, making the change its own only witness. The relief now
        lives in the norm's own registry and in a vetoable decision block; this
        pins that the check *defers* rather than *asserts*.

        Verified red by restoring the original wording ("inherits Check #13's
        recorded bounded exception ... rather than re-arguing it").
        """
        block = _check_block(_doctor_text(), 15)
        assert "inherits Check #13" not in block, (
            "Check #15 must not claim to inherit Check #13's bounded exception — that "
            "exception is scoped to #13 alone and cannot be extended by the control "
            "that would benefit from it"
        )
        norm = (
            Path(__file__).resolve().parent.parent.parent
            / ".prawduct" / "artifacts" / "nonfunctional-requirements.md"
        ).read_text(encoding="utf-8")
        live_exception = next(
            line for line in norm.splitlines() if line.strip().startswith("Live exception:")
        )
        assert "#15" in live_exception, (
            "Health Check #15 must be named on the Proportionality norm's Live exception "
            "line — otherwise the Norm Health sweep discharges #13 against #563 and never "
            "learns #15 holds an exception, so its named yield is never measured"
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
