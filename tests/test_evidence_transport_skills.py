"""The doctor and onboard skills set up and explain the notes transport (#1052).

Review facts travel between clones on ``refs/notes/prawduct``. ``/prawduct:pr``
pushes them (pinned in ``test_pr_reviewer.py``); these pin the other two
skills' share, read in the order an agent reads them:

- ``doctor`` Health Check #25 runs ``evidence configure`` — the preview the
  module that writes the keys prints — and offers ``--apply`` when it lists
  changes, rather than re-deriving "configured" in prose from ``git config``
  reads (R-5); #23 no longer tells the owner imported facts are stuck in this
  clone; #24 quotes the release-pending line the hook prints.
- ``onboard`` runs ``evidence configure --apply`` after its commit, only where
  the session runs in the target, and relays configure's own reason when it
  changes nothing (no remote).

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
    """Renegotiated (R-5): #25 read `git remote` and two `git config` keys and
    judged "configured" in prose — a second copy of `configure`'s own
    decision, which already drifted once (it kept naming the exact refspec
    `configure` replaced). It now runs `configure`'s preview and relays it."""

    def _check(self) -> str:
        return _health_checks(DOCTOR.read_text(encoding="utf-8"))[25]

    def test_it_runs_the_preview_and_offers_the_apply_when_it_lists_changes(self):
        check = self._check()
        preview = check.index("`prawduct-hook evidence configure`")
        apply = check.index("`prawduct-hook evidence configure --apply`")
        assert preview < apply, "the preview is run first, the apply offered after"
        # Offered, never applied unasked: it writes `.git/config`.
        assert "on the owner's yes" in check
        assert "nothing to change" in check, "the configured state is the preview's own line"

    def test_it_does_not_re_derive_configured_from_git_config_reads(self):
        check = self._check()
        assert "git config" not in check, check
        assert "git remote" not in check, check
        assert "+refs/notes/prawduct:refs/notes/" not in check, "no exact refspec is ever named"

    def test_a_repo_without_a_remote_is_not_a_finding(self):
        assert "no remote" in self._check()

    def test_what_it_runs_is_granted_and_the_read_grants_are_gone(self):
        frontmatter = _frontmatter(DOCTOR.read_text(encoding="utf-8"))
        assert "Bash(prawduct-hook evidence configure*)" in frontmatter
        for gone in (
            "Bash(git remote)",
            "Bash(git config --get-all remote.*)",
            "Bash(git config --get notes.rewriteRef)",
        ):
            assert gone not in frontmatter, gone


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
        """Renegotiated (R-5): the no-remote skip was a prose test
        (`git -C <target> remote`) ahead of the run; configure reports it
        itself, so the step relays configure's line instead."""
        finish = self._finish()
        at = finish.index("prawduct-hook evidence configure --apply")
        step = " ".join(finish[at - 600: finish.index("**2. Report in a few lines")].split())
        assert "no remote" in step
        assert "nothing to change" in step
        assert "git -C <target> remote" not in step
        assert "from another directory" in step
        assert "Health Check #25" in step

    def test_what_it_runs_is_granted(self):
        frontmatter = _frontmatter(ONBOARD.read_text(encoding="utf-8"))
        assert "Bash(prawduct-hook evidence configure*)" in frontmatter
        assert "Bash(git -C * remote)" not in frontmatter, "no prose remote test is left to need it"
