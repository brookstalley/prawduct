"""The doctor and onboard skills set up and explain the notes transport (#1052).

Review facts travel between clones on ``refs/notes/prawduct``. ``/prawduct:pr``
pushes them (pinned in ``test_pr_reviewer.py``); these pin the other two
skills' share, read in the order an agent reads them:

- ``doctor`` Health Check #25 detects an unconfigured clone (no notes fetch
  refspec on the remote, or no ``notes.rewriteRef``) and offers
  ``evidence configure --apply``; #23 no longer tells the owner imported facts
  are stuck in this clone; #24 quotes the release-pending line the hook prints.
- ``onboard`` runs ``evidence configure --apply`` after its commit, only where
  it can reach the target and there is a remote, and says why when it skips.

The numbering pin is here because check numbers are cross-referenced by name
(``Health Check #24``) from the classification paragraph and other files.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
DOCTOR = ROOT / "skills" / "doctor" / "SKILL.md"
ONBOARD = ROOT / "skills" / "onboard" / "SKILL.md"


def _frontmatter(text: str) -> str:
    return text.split("---", 2)[1]


def _health_checks(text: str) -> "dict[int, str]":
    """Each numbered item of the Health Check Flow, by its number."""
    flow = text.split("## Health Check Flow", 1)[1].split("\n## ", 1)[0]
    items = re.split(r"(?m)^(\d+)\. ", flow)[1:]
    return {int(items[i]): items[i + 1] for i in range(0, len(items), 2)}


class TestDoctorNumbering:
    #: Retired checks keep their number unused: other files cite checks by
    #: number, so a renumbering would silently repoint every citation past it.
    #: #13 (learnings shape) went with the learnings verbs.
    RETIRED = {13}

    def test_a_new_check_appends_and_no_check_is_renumbered(self):
        checks = _health_checks(DOCTOR.read_text(encoding="utf-8"))
        assert sorted(checks) == [n for n in range(1, 26) if n not in self.RETIRED], sorted(checks)

    def test_check_25_is_the_notes_transport(self):
        check = _health_checks(DOCTOR.read_text(encoding="utf-8"))[25]
        assert check.startswith("**Notes transport configured")


class TestDoctorCheck25:
    def _check(self) -> str:
        return _health_checks(DOCTOR.read_text(encoding="utf-8"))[25]

    def test_it_detects_with_the_two_config_reads_and_offers_the_apply(self):
        check = self._check()
        assert "git config --get-all remote.<r>.fetch" in check
        assert "git config --get notes.rewriteRef" in check
        assert "+refs/notes/prawduct:refs/notes/<r>/prawduct" in check
        assert "prawduct-hook evidence configure --apply" in check
        # Offered, never applied unasked: it writes `.git/config`.
        assert "on the owner's yes" in check

    def test_a_repo_without_a_remote_is_not_a_finding(self):
        assert "no remote" in self._check()

    def test_what_it_reads_and_runs_is_granted(self):
        frontmatter = _frontmatter(DOCTOR.read_text(encoding="utf-8"))
        for grant in (
            "Bash(git remote)",
            "Bash(git config --get-all remote.*)",
            "Bash(git config --get notes.rewriteRef)",
            "Bash(prawduct-hook evidence configure*)",
        ):
            assert grant in frontmatter, grant


class TestDoctorCheck23And24:
    def test_23_no_longer_keeps_imported_facts_in_this_clone(self):
        check = _health_checks(DOCTOR.read_text(encoding="utf-8"))[23]
        assert "until #1052" not in check
        assert "refs/notes/prawduct" in check
        # The block's removal is now the advice: offered with the apply.
        at = check.index("--remove-block")
        assert "offer" in check[max(0, at - 200): at + 200].lower()

    def test_24_quotes_the_release_pending_line_the_hook_prints(self):
        check = _health_checks(DOCTOR.read_text(encoding="utf-8"))[24]
        assert (
            "`<plan>: <field> claims <branch>, which no longer exists; merged-unreleased "
            "(<reason>) — archive at the release`"
        ) in check
        assert "its fragment is pending release" not in check


class TestOnboardConfiguresTheTransport:
    def _finish(self) -> str:
        return ONBOARD.read_text(encoding="utf-8").split("## Finish: commit, then discovery", 1)[1]

    def test_it_runs_after_the_commit_and_before_the_report(self):
        finish = self._finish()
        commit = finish.index("**1. Commit the scaffold.**")
        configure = finish.index("prawduct-hook evidence configure --apply")
        report = finish.index("**2. Report in a few lines")
        assert commit < configure < report

    def test_it_says_why_when_it_skips(self):
        finish = self._finish()
        at = finish.index("prawduct-hook evidence configure --apply")
        step = " ".join(finish[at - 600: finish.index("**2. Report in a few lines")].split())
        assert "no remote" in step
        assert "from another directory" in step
        assert "Health Check #25" in step

    def test_what_it_runs_is_granted(self):
        frontmatter = _frontmatter(ONBOARD.read_text(encoding="utf-8"))
        assert "Bash(prawduct-hook evidence configure*)" in frontmatter
        assert "Bash(git -C * remote)" in frontmatter
