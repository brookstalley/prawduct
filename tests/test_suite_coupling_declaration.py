"""This repo's `suite_coupled_prefixes` against the files its own tests read.

`affects_test_outcome` is an ALLOWLIST: a path is assumed unable to change what
the suite says unless some prefix declares it. That is fail-open, so a test that
starts reading a new real-repo file silently re-opens the hole — the freshness
gate keeps answering `current` over a tree that is already red, and CI is the
first thing to notice.

It happened on 2026-09-19. A reworded sentence in `.prawduct/artifacts/data-model.md`
dropped the plan citation `test_the_amendment_points_outside_itself_for_its_authority`
requires; the local suite had been recorded minutes earlier, `test-status` reported
`current` over the edited tree, the branch was pushed, and both CI matrices went red
on a file the declaration called untestable.

**What turns this red:** deleting one of the declared entries from
`project-state.yaml`, or widening the declaration so far that the held-out
control below becomes coupled. Both are verified by mutation, not assumed.

**The honest limit — this is a FLOOR, not a census.** The registry below is
hand-maintained, and a hand-maintained list is exactly the thing that drifted.
It cannot discover a real-repo read that some future test adds. Deriving the set
statically was tried and abandoned: it is a strict PREFIX of the truth, because
a test can reach a real file through a helper that builds the path itself
(`TestAgainstTheRealChangeLog` reads the log via `change_log_archive.load_all_text`,
spelling no path at all) or through a resolver's own constants
(`TestAgainstTheRealCorpus`, via `learnings_files.RULES_DIR_REL`). A guard built
on that scan would go green while blind to precisely the reads it exists to
catch. The sound close is evidence that records what the run actually read; until
that exists, this pins the reads we know about so that at least THEY cannot be
dropped by an edit to the declaration.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "plugin"))
from lib import core, coverage_algebra as ca  # noqa: E402

#: Real-repo files a test reads, mapped to the test that reads them. Each entry
#: is a path whose edit can flip this suite red, so evidence recorded before
#: that edit does not vouch for the tree after it. The reader is named because
#: an entry with no reader is one nobody can re-verify — and re-verifying is how
#: an entry gets removed honestly rather than because it looked unused.
READ_BY_A_REAL_REPO_TEST = {
    ".prawduct/artifacts/data-model.md":
        "tests/test_governance_ledger.py::TestTheMarkerNormKeepsItsReason",
    ".prawduct/operator-verification.md":
        "tests/test_operator_verification.py (LIVE_QUEUE)",
    ".claude/rules/learnings/core.md":
        "tests/test_learnings_files.py::TestAgainstTheRealCorpus",
}

#: The control. This artifact is NOT read by any real-repo test, and coupling it
#: would tax every architecture edit with a full suite re-run — the same cost
#: argument `project-state.yaml` makes for keeping the build-plan prefix narrow.
#: Without it, "every path is coupled" passes every assertion above.
MUST_STAY_UNCOUPLED = ".prawduct/artifacts/architecture.md"


def _declared() -> tuple[str, ...]:
    return core.suite_coupled_prefixes(REPO / ".prawduct")


class TestTheDeclarationCoversWhatTheSuiteReads:
    def test_the_declaration_is_readable_and_non_empty(self):
        """The reachability assert. Every assertion below is satisfied by an
        empty registry or an unreadable declaration, so neither may pass
        silently: a guard whose subject is a SET must say the set was reached."""
        declared = _declared()
        assert declared, (
            f"{REPO / '.prawduct/project-state.yaml'} declares no "
            "`suite_coupled_prefixes` — every assertion below would pass "
            "vacuously against an empty allowlist"
        )
        assert READ_BY_A_REAL_REPO_TEST, "the registry is empty"

    @pytest.mark.parametrize("path", sorted(READ_BY_A_REAL_REPO_TEST))
    def test_each_file_a_real_repo_test_reads_is_on_disk(self, path: str):
        """A registry entry naming a file that does not exist pins nothing: the
        coupling assertion below would still pass, and the reader it cites could
        have been deleted years ago."""
        assert (REPO / path).exists(), (
            f"{path} is in the registry but not in the tree — either the file "
            f"moved (update the entry and {READ_BY_A_REAL_REPO_TEST[path]}) or "
            "the reader is gone and the entry should be removed"
        )

    @pytest.mark.parametrize("path", sorted(READ_BY_A_REAL_REPO_TEST))
    def test_each_file_a_real_repo_test_reads_is_suite_coupled(self, path: str):
        """The property, asked of the real predicate rather than of the YAML.

        A substring check against `project-state.yaml` would pass for any
        spelling that happens to contain the path and would not notice that
        `affects_test_outcome` never consults it.
        """
        assert ca.affects_test_outcome(path, _declared()) is True, (
            f"{path} is read by {READ_BY_A_REAL_REPO_TEST[path]} but this repo's "
            "`suite_coupled_prefixes` does not cover it — an edit to it can turn "
            "the suite red while `test-status` reports stale evidence as `current`"
        )

    def test_the_declaration_has_not_been_widened_into_everything(self):
        """The control, and the reason the assertions above discriminate.

        Declaring `.prawduct/` (or `.prawduct/artifacts/`) satisfies every
        coupling assertion above and buys a four-minute suite re-run on every
        artifact edit. The cost argument against that is recorded in
        `project-state.yaml` beside the build-plan prefix; this is the assertion
        that notices when someone takes the shortcut anyway.
        """
        assert ca.affects_test_outcome(MUST_STAY_UNCOUPLED, _declared()) is False, (
            f"{MUST_STAY_UNCOUPLED} became suite-coupled — the declaration was "
            "widened past the files a test actually reads, which taxes every "
            "artifact edit with a full suite run. Name the file, not its parent."
        )

    def test_the_held_out_change_log_is_still_held_out(self):
        """`.prawduct/change-log.md` IS read by a real-repo test and is
        deliberately excluded on cost — a priced decision pinned by
        `test_the_held_out_bookkeeping_files_are_recorded_as_a_residual`.

        Asserted HERE too, because this file is where someone fixing a
        freshness miss will be working, and the registry above is a standing
        invitation to add it. Coupling it is a deliberate edit in both places,
        never a line quietly added to the declaration.
        """
        assert ca.affects_test_outcome(".prawduct/change-log.md", _declared()) is False, (
            "`.prawduct/change-log.md` became suite-coupled. That overturns a "
            "recorded cost decision — flip it there, with its reason, rather "
            "than here"
        )
