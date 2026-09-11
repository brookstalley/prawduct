"""Tests for the Phase 0 releasability gate (REL-8P6M part f).

The gate exists because the release runbook's only precondition asked "is
there anything to ship?", never "is everything *fit* to ship?" — and on v3.1.2
those diverged in a way that would have published four open go-live blockers
to every installed consumer, unrecallably.

So the claims pinned here are the ones that make it a gate rather than a
report: an unclassified scope BLOCKS and is named; a withholding whose blocker
has closed BLOCKS; missing inputs fail CLOSED. A gate that fails open is
indistinguishable from no gate, which is the state this replaces.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))
from lib import release_readiness  # noqa: E402
from lib.release_readiness import _DIGEST_REL_PATH  # noqa: E402


#: Sentinel for "the caller said nothing about test evidence", so `None` can
#: mean "write no record" without collapsing into the default.
_EVIDENCE_DEFAULT: dict = {}


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _evidence(**overrides) -> dict:
    """A schema-valid record of a green suite run.

    The gate refuses when nothing says the code passes, so a fixture that omits
    this is a fixture staging a *red* release — which is a state worth testing
    deliberately and never worth inheriting by accident. Every field here is
    required by ``gates._validate_evidence_schema``; a record missing one is
    rejected for the schema rather than for the thing under test, which reads as
    the same failure and is not.
    """
    record = {
        "timestamp": "2026-01-01T00:00:00Z",
        "passed": 12,
        "failed": 0,
        "skipped": 0,
        "duration_seconds": 1.5,
        "command": "pytest",
        "verifier": "pytest",
        "tests_executed": ["tests/"],
        "changes_referenced": [],
        "coverage_level": "referenced",
    }
    record.update(overrides)
    return record


def _make_project(
    tmp_path: Path,
    *,
    entries: str,
    classification: str | None,
    backlog: str = "",
    version: str = "3.2.0",
    plan_suffix: str = "",
    digest: str | None = None,
    evidence: dict | None = _EVIDENCE_DEFAULT,
    session_start: str | None = "2000-01-01T00:00:00Z",
) -> Path:
    project = tmp_path / "proj"
    _write(project / ".prawduct" / "change-log.md", "# Change Log\n\n" + entries)
    # A green run by default: the gate refuses over the code as well as over the
    # bookkeeping, so every fixture that is not *about* the suite has to state
    # that the suite passed. `evidence=None` writes no record — the missing-
    # evidence refusal. `session_start` is what dates a record: the reader
    # compares the evidence tree against the marker to decide current-vs-stale.
    # It defaults to an ancient marker so a fixture that is not *about* staleness
    # reads as current. Passing `None` writes NO marker, which since #186 reads
    # STALE rather than accepting the run -- an unanchored worktree is exactly
    # the case the gate must not fail open on.
    if evidence is _EVIDENCE_DEFAULT:
        evidence = _evidence()
    if evidence is not None:
        _write(
            project / ".prawduct" / ".test-evidence.json",
            json.dumps(evidence),
        )
    if session_start is not None:
        _write(project / ".prawduct" / ".session-start", session_start)
    _write(project / ".prawduct" / "backlog.md", "# Backlog\n\n## Open\n\n" + backlog)
    _write(project / "plugin" / "VERSION", version + "\n")
    # Absent by default, so a fixture that passes none exercises the degraded
    # NOTE. These projects write `plugin/VERSION`, which makes them
    # prawduct-shaped: a repo publishing no digest at all is a different case
    # with no subject to report on, and it is built by unlinking that file.
    if digest is not None:
        _write(project / "plugin" / "CHANGELOG.md", digest)
    if classification is not None:
        name = f"release-plan-v{version}{plan_suffix}.md"
        _write(
            project / ".prawduct" / "artifacts" / name,
            f"# Release plan v{version}\n\n## Release classification\n\n"
            "| Scope | Disposition | Blocker |\n|---|---|---|\n" + classification,
        )
    return project


def _entry(title: str, scope: str, *, release: str | None = None) -> str:
    tag = f"<!-- prawduct: type=fix | scope={scope}"
    if release:
        tag += f" | release={release} | status=shipped"
    tag += " -->"
    return f"## {title}\n\n{tag}\n\nBody.\n\n"


def _scopeless_entry(title: str, *, release: str | None = None) -> str:
    """A tagged entry carrying no ``scope=`` — the shape the gate could not see."""
    tag = "<!-- prawduct: type=fix"
    if release:
        tag += f" | release={release} | status=shipped"
    tag += " -->"
    return f"## {title}\n\n{tag}\n\nBody.\n\n"


def _open_item(item_id: str) -> str:
    return f"- **[{item_id}]** A blocker\n  `effort: M · impact: L · area: x · status: open`\n\n"


def _shipped_item(item_id: str) -> str:
    return f"- **[{item_id}]** A closed thing\n  `effort: M · impact: L · area: x · status: shipped`\n\n"


class TestReleasePendingScopes:
    def test_release_tagged_entries_are_not_pending(self):
        from lib import change_log

        content = _entry("A", "alpha") + _entry("B", "beta", release="v3.1.2")
        scopes = release_readiness.release_pending_scopes(change_log.parse_change_log(content))
        assert scopes == ["alpha"], "a release= tag means the code already shipped"

    def test_untagged_entries_are_invisible(self):
        from lib import change_log

        content = "## Historical entry\n\nNo tag line at all.\n\n" + _entry("A", "alpha")
        scopes = release_readiness.release_pending_scopes(change_log.parse_change_log(content))
        assert scopes == ["alpha"]


class TestGatePasses:
    def test_all_scopes_classified_passes(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha") + _entry("B", "beta"),
            classification="| alpha | ships | |\n| beta | withheld | BKL-6J2X |\n",
            backlog=_open_item("BKL-6J2X"),
        )
        assert release_readiness.check_releasability(project) == 0
        out = capsys.readouterr().out
        assert "2 release-pending scope(s), 1 shipping, 1 withheld" in out
        assert "beta (blocked by BKL-6J2X)" in out

    def test_nothing_pending_passes_without_a_release_plan(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha", release="v3.1.2"),
            classification=None,
        )
        assert release_readiness.check_releasability(project) == 0
        assert "no release-pending scopes" in capsys.readouterr().out

    def test_plan_filename_suffix_is_tolerated(self, tmp_path):
        # Real plans carry a descriptive suffix (release-plan-v3.1.2-pruned.md);
        # an exact-name lookup would miss every one of them.
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            plan_suffix="-pruned",
        )
        assert release_readiness.check_releasability(project) == 0


class TestGateBlocks:
    def test_unclassified_scope_blocks_and_is_named(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha") + _entry("B", "beta"),
            classification="| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        assert "not-releasable" in err
        assert "unclassified scope(s)" in err
        assert "beta" in err, "the gate must name the scope, not just the count"

    def test_withheld_behind_a_closed_blocker_blocks(self, tmp_path, capsys):
        # The blocker IS the justification: once it closes, the withholding
        # decision is stale and must be re-taken rather than inherited.
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | withheld | BKL-6J2X |\n",
            backlog=_shipped_item("BKL-6J2X"),
        )
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        assert "no longer open" in err
        assert "BKL-6J2X" in err

    def test_withheld_without_a_blocker_id_blocks(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | withheld | |\n",
        )
        assert release_readiness.check_releasability(project) == 1
        assert "requires a blocker item id" in capsys.readouterr().err

    def test_unrecognised_disposition_blocks(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | maybe | |\n",
        )
        assert release_readiness.check_releasability(project) == 1
        assert "unrecognised disposition" in capsys.readouterr().err

    def test_orphan_table_row_blocks(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n| ghost | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 1
        assert "nothing release-pending behind them" in capsys.readouterr().err

    def test_missing_release_plan_fails_closed_and_names_the_scopes(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha") + _entry("B", "beta"),
            classification=None,
        )
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        assert "no-release-plan" in err
        assert "alpha" in err and "beta" in err

    def test_missing_classification_section_fails_closed(self, tmp_path, capsys):
        project = _make_project(
            tmp_path, entries=_entry("A", "alpha"), classification="| alpha | ships | |\n"
        )
        plan = project / ".prawduct" / "artifacts" / "release-plan-v3.2.0.md"
        plan.write_text("# Release plan\n\nNo classification section here.\n", encoding="utf-8")
        assert release_readiness.check_releasability(project) == 1
        assert "no `## Release classification` section" in capsys.readouterr().err

    def test_missing_change_log_fails_closed(self, tmp_path, capsys):
        project = tmp_path / "empty"
        project.mkdir()
        assert release_readiness.check_releasability(project) == 1
        assert "no-change-log" in capsys.readouterr().err

    def test_duplicate_classification_blocks(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n| alpha | withheld | BKL-6J2X |\n",
            backlog=_open_item("BKL-6J2X"),
        )
        assert release_readiness.check_releasability(project) == 1
        assert "classified twice" in capsys.readouterr().err


class TestResolvedSectionBlockerIsNotOpen:
    """The archive move and the status flip are separate edits, so an item in a
    resolved section can still read `status: open`. Treating it as a live
    blocker is the stale-withholding error the gate exists to catch.

    Parametrised over ALL FOUR resolved-section words, not just `Archive`: a
    test that only exercises `## Archive` passes under a naive
    `startswith("archive")` too, so it could not fail on the narrow predicate it
    was written to replace — and only prawduct's own heading hid that."""

    @pytest.mark.parametrize("section", ["Archive", "Resolved", "Done", "Completed"])
    def test_item_in_a_resolved_section_does_not_count_as_open(
        self, tmp_path, capsys, section
    ):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | withheld | BKL-6J2X |\n",
        )
        _write(
            project / ".prawduct" / "backlog.md",
            f"# Backlog\n\n## Open\n\n## {section}\n\n" + _open_item("BKL-6J2X"),
        )
        assert release_readiness.check_releasability(project) == 1
        assert "no longer open" in capsys.readouterr().err

    def test_a_struck_item_is_not_a_live_blocker(self, tmp_path, capsys):
        # Comes free with the public pending_items() query; pinned so a future
        # reimplementation cannot quietly drop it.
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | withheld | BKL-6J2X |\n",
        )
        _write(
            project / ".prawduct" / "backlog.md",
            "# Backlog\n\n## Open\n\n- **[BKL-6J2X]** ~~struck~~\n"
            "  `effort: M · impact: L · area: x · status: open`\n\n",
        )
        assert release_readiness.check_releasability(project) == 1
        assert "no longer open" in capsys.readouterr().err


class TestPostCutoverFailsClosed:
    """`data-model.md` § Direction: once `backlog_service_repo` is set the
    markdown is frozen history and every item archived at cutover still parses
    as open. Reading it anyway would make a closed blocker look open — the gate
    certifying the exact staleness it exists to catch."""

    def _cut_over(self, project: Path) -> None:
        _write(
            project / ".prawduct" / "project-state.yaml",
            "backlog_service_repo: acme/backlog\n",
        )

    def test_withheld_scope_blocks_post_cutover(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | withheld | BKL-6J2X |\n",
            backlog=_open_item("BKL-6J2X"),
        )
        self._cut_over(project)
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        assert "cannot-verify-blockers" in err
        assert "alpha" in err

    def test_unreadable_state_is_NOT_diagnosed_as_a_cutover(
        self, tmp_path, capsys, monkeypatch
    ):
        # Both causes fail closed, but they need different remedies. Told
        # "this repo has cut over (`backlog_service_repo` set)", an operator
        # whose project-state merely failed to load goes looking for a scalar
        # that is unset and finds nothing — a wrong remedy is worse than a bare
        # failure. The refusal must name the cause it actually established.
        #
        # Patched rather than fixtured: `load_project_state` is a column-0
        # scanner with no YAML parser, and it swallows OSError/UnicodeDecodeError
        # itself, so no file content reaches this branch. The broad `except` is
        # there because that loader's failure modes are not enumerable from here
        # — which is exactly the contract under test.
        import lib.advisory_store as _store

        def _boom(_dir):
            raise RuntimeError("state loader exploded")

        monkeypatch.setattr(_store, "load_project_state", _boom)
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | withheld | BKL-6J2X |\n",
            backlog=_open_item("BKL-6J2X"),
        )
        assert release_readiness.check_releasability(project, "v3.2.0") == 1
        err = capsys.readouterr().err
        assert "unreadable-project-state" in err
        assert "state loader exploded" in err, "the cause must reach the operator"
        assert "backlog_service_repo" not in err, (
            "the cutover cause was never established, so it must not be asserted"
        )
        assert "alpha" in err, "the withheld scopes still need naming"

    def test_an_unclassified_scope_is_STILL_named_post_cutover(self, tmp_path, capsys):
        # The runbooks tell the operator to hand-verify blocker liveness and
        # continue. If the refusal returned before the other checks ran, that
        # instruction would route them past an unclassified scope on the way to
        # an unrecallable publish — the exact v3.1.2 near-miss this gate exists
        # for, re-entered through its own remedy. The frozen backlog withholds
        # blocker LIVENESS and nothing else.
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha") + _entry("B", "unclassified-scope"),
            classification="| alpha | withheld | BKL-6J2X |\n",
            backlog=_open_item("BKL-6J2X"),
        )
        self._cut_over(project)
        assert release_readiness.check_releasability(project, "v3.2.0") == 1
        err = capsys.readouterr().err
        assert "cannot-verify-blockers" in err, "the liveness refusal still stands"
        assert "unclassified-scope" in err, (
            "the check the gate exists to perform must survive the one it cannot"
        )

    def test_unverifiable_liveness_is_not_reported_as_a_closed_blocker(
        self, tmp_path, capsys
    ):
        # An unread backlog yields an empty open-id set, so a naive check reads
        # every blocker as closed and tells the operator to re-take a decision
        # that may be perfectly sound — a wrong remedy, worse than a bare failure.
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | withheld | BKL-6J2X |\n",
            backlog=_open_item("BKL-6J2X"),
        )
        self._cut_over(project)
        assert release_readiness.check_releasability(project, "v3.2.0") == 1
        err = capsys.readouterr().err
        assert "which is not open" not in err, (
            "liveness was unverifiable, so 'not open' is a claim the gate cannot make"
        )

    def test_contradiction_does_not_call_a_blocker_closed_post_cutover(
        self, tmp_path, capsys
    ):
        # The contradiction branch names blocker liveness inline, on its own
        # `open_ids` read. Post-cutover that set is empty because the backlog was
        # never opened — so without the guard this prints "no longer open" about
        # a blocker whose state is simply unknown, which is the wrong-remedy
        # defect the branch was written to eliminate, re-entered one line down.
        # The sibling contradiction test above never cuts over, so it cannot
        # reach this.
        # `beta` keeps the pending set non-empty — with every entry tagged the
        # gate returns early and never reaches the contradiction branch at all.
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha", release="v3.2.0") + _entry("B", "beta"),
            classification="| alpha | withheld | BKL-6J2X |\n| beta | ships | |\n",
            backlog=_shipped_item("BKL-6J2X"),
        )
        self._cut_over(project)
        assert release_readiness.check_releasability(project, "v3.2.0") == 1
        err = capsys.readouterr().err
        assert "already tagged release=v3.2.0" in err, "the contradiction still fires"
        assert "no longer open" not in err, (
            "liveness was unverifiable, so the contradiction must not claim it"
        )

    def test_no_withheld_scope_still_passes_post_cutover(self, tmp_path):
        # Proportionality: a release that withholds nothing needs no blocker
        # liveness check, so cutover must not block it.
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
        )
        self._cut_over(project)
        assert release_readiness.check_releasability(project) == 0


class TestIdempotentAcrossItsOwnRunbook:
    """Phase 0 must survive being re-run after Phase 1. Phase 1 step 3 stamps
    `release=` on the shipping entries, which removes those scopes from the
    pending set — so a naive orphan check would report every successfully
    classified scope as a stale table row on the second run, and the gate would
    block the release it just approved."""

    def test_the_fully_stamped_rerun_says_WHY_it_is_empty(self, tmp_path, capsys):
        # The shape the idempotency work above does not reach: Phase 1 stamped
        # EVERY scope, so `pending` is empty and the gate returns 0 before it
        # opens a release plan at all — a green line having validated nothing,
        # and one that names no `K withheld` for Phase 2's routing to read.
        # It cannot be made to fail (nothing is pending, which is honest), so
        # the requirement is that its denominator distinguishes the causes:
        # "everything already shipped in past releases" from "Phase 1 just ran".
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha", release="v3.2.0")
            + _entry("B", "beta", release="v3.2.0"),
            classification="| alpha | ships | |\n| beta | ships | |\n",
        )
        assert release_readiness.check_releasability(project, "v3.2.0") == 0
        out = capsys.readouterr().out
        assert "no release-pending scopes" in out
        assert "2 scope(s) already tagged release=v3.2.0" in out, (
            "without this the operator cannot tell a re-run after Phase 1 from "
            "a change log the parser could not read"
        )

    def test_scope_tagged_for_this_release_is_not_an_orphan(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha", release="v3.2.0") + _entry("B", "beta"),
            classification="| alpha | ships | |\n| beta | ships | |\n",
        )
        assert release_readiness.check_releasability(project, "v3.2.0") == 0, capsys.readouterr().err

    def test_a_WITHHELD_scope_tagged_for_this_release_is_not_exempt(self, tmp_path, capsys):
        # Withheld-then-shipped is a contradiction, and the exemption must not
        # swallow it: the scope would be absent from `pending`, absent from the
        # orphan list and absent from the withheld summary, so the gate would
        # print `releasable:` without ever mentioning the withholding.
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha", release="v3.2.0") + _entry("B", "beta"),
            classification="| alpha | withheld | BKL-6J2X |\n| beta | ships | |\n",
            backlog=_open_item("BKL-6J2X"),
        )
        assert release_readiness.check_releasability(project, "v3.2.0") == 1
        err = capsys.readouterr().err
        assert "the table and the change log disagree" in err
        assert "Do NOT delete the row" in err, (
            "the orphan wording's remedy would ship the withheld scope"
        )
        assert "nothing release-pending behind them" not in err

    def test_contradiction_also_reports_a_closed_blocker(self, tmp_path, capsys):
        # Both defects at once. The contradiction branch short-circuits the
        # stale-blocker check, so without this the remedy "the withholding
        # stands" would be offered for a blocker that has closed — an
        # unavailable option, the same wrong-remedy defect the branch fixes.
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha", release="v3.2.0") + _entry("B", "beta"),
            classification="| alpha | withheld | BKL-6J2X |\n| beta | ships | |\n",
            backlog=_shipped_item("BKL-6J2X"),
        )
        assert release_readiness.check_releasability(project, "v3.2.0") == 1
        err = capsys.readouterr().err
        # Assert the full string only the contradiction branch can produce.
        # A bare "no longer open" would discriminate here only by accident of
        # the fixture: `alpha` short-circuits before the stale-blocker append
        # and `beta` ships, so that header cannot fire. Add a third scope
        # withheld behind a closed blocker and it fires, and the bare phrase
        # stops distinguishing the branches. Discrimination belongs to the
        # assertion, not to which scopes the fixture happens to contain.
        assert "BKL-6J2X, which is no longer open" in err
        assert "already tagged release=v3.2.0" in err

    def test_scope_tagged_for_a_DIFFERENT_release_is_still_an_orphan(self, tmp_path, capsys):
        # The exemption is scoped to the release under test — a row left over
        # from an older release is still stale.
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha", release="v3.1.0") + _entry("B", "beta"),
            classification="| alpha | ships | |\n| beta | ships | |\n",
        )
        assert release_readiness.check_releasability(project, "v3.2.0") == 1
        assert "nothing release-pending behind them" in capsys.readouterr().err


class TestCliWiring:
    """R-1: the dispatch, `--release` parsing and usage string had no test at
    all, and the parse silently graded a different release than the operator
    named."""

    def _run(self, project: Path, *args: str):
        import subprocess

        return subprocess.run(
            [sys.executable, str(ROOT / "bin" / "prawduct-hook"), "check-releasability", *args],
            cwd=str(project),
            capture_output=True,
            text=True,
            timeout=60,
        )

    def _project(self, tmp_path: Path) -> Path:
        # VERSION deliberately DIFFERS from the --release value the tests pass.
        # With them equal, the pre-fix ignore-and-fall-back path satisfied the
        # assertion too, so the regression test could not fail on the bug.
        return _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            version="3.1.0",
        )

    def test_dispatch_reaches_the_gate(self, tmp_path):
        proc = self._run(self._project(tmp_path))
        assert proc.returncode == 0, proc.stderr
        assert "releasable:" in proc.stdout

    def test_the_VERSION_fallback_announces_itself(self, tmp_path):
        # The fallback is wrong by construction during Phase 0 — VERSION is
        # bumped later, at Phase 1 step 7 — so the NOTE is the only thing
        # standing between an operator and a silently misgraded release.
        # Asserted POSITIVELY on purpose: the sibling test above can only say
        # the NOTE is absent when --release IS passed, which stays true if the
        # print is deleted outright. Verified by mutation — dropping the
        # print(...) in _resolve_version fails this test and nothing else.
        proc = self._run(self._project(tmp_path))  # no --release
        assert "no --release given" in proc.stderr
        assert "v3.1.0" in proc.stderr, "the NOTE must name the version it fell back to"
        # The PROPERTY, not the old spelling. This asserted "PREVIOUS release"
        # until Phase 3 falsified it: develop now carries a `-dev` marker all
        # cycle, so the fallback names something that is not any release rather
        # than the previous one. Pinning the sentence would have kept a test
        # green on a message that had become false — the failure this whole
        # branch's review kept finding. What must survive is that the NOTE says
        # the fallback is NOT the release being graded.
        assert "not a release" in proc.stderr.lower() or "previous release" in proc.stderr.lower(), (
            "naming the fallback without saying it is the wrong thing to grade "
            "is the silent-misgrade this NOTE exists to prevent"
        )

    @pytest.mark.parametrize("form", ["--release=v3.2.0", "--release v3.2.0"])
    def test_both_release_forms_are_honoured(self, tmp_path, form):
        # `--release=v3.2.0` previously fell through to plugin/VERSION and
        # graded a DIFFERENT release without saying so.
        proc = self._run(self._project(tmp_path), *form.split(" "))
        combined = proc.stdout + proc.stderr
        # Reaches the no-release-plan path (the fixture only has a v3.1.0 plan),
        # which is still a decisive proof that the FLAG was parsed: the message
        # names the version it looked for.
        assert "no-release-plan" in combined
        assert "v3.2.0" in combined, "the named release must be the one graded"
        assert "no --release given" not in combined, (
            "falling back to plugin/VERSION means the flag was silently ignored"
        )
        assert "v3.1.0" not in combined, "v3.1.0 is the fixture's VERSION, not the ask"

    @pytest.mark.parametrize("bad", ["v3.2.0", "--relase", "--extra"])
    def test_unknown_tokens_are_usage_errors_not_ignored(self, tmp_path, bad):
        proc = self._run(self._project(tmp_path), bad)
        assert proc.returncode == 2, f"{bad!r} must be a usage error, not silently ignored"
        assert "unknown argument" in proc.stderr

    def test_release_without_a_value_is_a_usage_error(self, tmp_path):
        proc = self._run(self._project(tmp_path), "--release")
        assert proc.returncode == 2
        assert "requires a version argument" in proc.stderr

    def test_command_is_listed_in_usage(self):
        text = (ROOT / "bin" / "prawduct-hook").read_text(encoding="utf-8")
        assert "check-releasability" in text.split("_USAGE")[1][:4000]


class TestPartitionIsExact:
    """The gate's whole claim is that the classification PARTITIONS the
    release-pending set. A subset comparison satisfies "every classified scope
    is pending" while silently permitting an unclassified one — which is the
    exact shape of the v3.1.2 near-miss. Pinned in both directions."""

    @pytest.mark.parametrize(
        "classification,expected",
        [
            ("| alpha | ships | |\n", 1),  # missing beta -> blocks
            ("| alpha | ships | |\n| beta | ships | |\n", 0),  # exact -> passes
            (
                "| alpha | ships | |\n| beta | ships | |\n| gamma | ships | |\n",
                1,
            ),  # superset -> blocks
        ],
    )
    def test_only_an_exact_cover_passes(self, tmp_path, classification, expected):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha") + _entry("B", "beta"),
            classification=classification,
        )
        assert release_readiness.check_releasability(project) == expected


class TestChangeLogTagsAreRefusedHere:
    """The rehomed tag checks — the guard that hid a branch from v3.2.8.

    `release_pending_scopes` skips any entry carrying a `release=` value and
    cannot tell a version from a placeholder, so `release=unreleased` removes
    its whole scope from the pending set and this gate answers "nothing to cut"
    while the work never ships. The check existed, but its only caller was the
    derived-view regenerator — a command a release does not run. These tests
    pin it to the gate that a release DOES run.
    """

    def test_placeholder_release_is_refused_and_named(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha").replace(
                "| scope=alpha", "| scope=alpha | release=unreleased"
            ),
            classification="| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        assert "bad-change-log-tag" in err
        assert "unreleased" in err
        assert "delete the tag" in err

    def test_the_placeholder_would_otherwise_read_as_nothing_to_cut(self, tmp_path, capsys):
        """The failure this prevents, demonstrated rather than asserted.

        Without the guard the same change log produces exit 0 and the words
        "nothing to classify" — a green gate on a branch that never ships. The
        test pins the *shape* of that failure by showing the pending set is
        empty once the malformed tag is accepted.
        """
        from lib import change_log

        content = _entry("A", "alpha").replace(
            "| scope=alpha", "| scope=alpha | release=unreleased"
        )
        entries = change_log.parse_change_log(content)
        assert release_readiness.release_pending_scopes(entries) == []
        errors, _warnings = change_log.validate_change_log_tags(entries)
        assert len(errors) == 1

    def test_a_real_version_still_passes(self, tmp_path):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha") + _entry("B", "beta", release="v3.1.2"),
            classification="| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 0

    def test_this_repos_own_change_log_passes_the_guard(self):
        """Sixty-plus entries of real history, so the guard cannot fail closed."""
        from lib import change_log

        log = Path(__file__).resolve().parents[1] / ".prawduct" / "change-log.md"
        if not log.is_file():
            pytest.skip("no .prawduct/change-log.md in this checkout")
        entries = change_log.parse_change_log(log.read_text(encoding="utf-8"))
        assert [e for e in entries if e.tags.get("release")], "no release tags parsed"
        errors, _warnings = change_log.validate_change_log_tags(entries)
        assert errors == [], errors


class TestScopelessPendingEntryIsRefused:
    """A release-pending entry with no ``scope=`` stops being invisible.

    The gate enumerates *scopes*, and an entry carrying none contributes nothing
    to enumerate: it reaches no row of the classification table, so it can be
    neither shipped nor withheld, and Phase 0 certified `releasable` over work it
    had never seen. The code already knew — the no-pending branch named this
    blindness in a comment and returned 0 anyway. What is pinned here is that the
    accounting now exists on BOTH branches and that the mismatch REFUSES: this is
    a releasability verdict over unclassifiable work, and an authority gate fails
    closed.
    """

    def test_a_scopeless_pending_entry_refuses_and_is_named(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha") + _scopeless_entry("An unscoped change"),
            classification="| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        assert "unclassifiable-pending-entry" in err
        # Named, because the remedy is mechanical only if the operator knows
        # which entry to edit. A count alone sends them reading 364 entries.
        assert "An unscoped change" in err
        assert "change-log line" in err
        assert "`scope=`" in err

    def test_it_refuses_where_the_gate_would_otherwise_certify_a_pass(self, tmp_path, capsys):
        """The blindness itself, not a variation on it.

        When the scopeless entry is the ONLY release-pending work, the pending
        set is empty, so the old code took the no-pending return and printed
        `releasable: … nothing to classify` — a green verdict over unclassified
        work, with no release plan ever opened. That is why the reconciliation
        runs BEFORE that return and not after it.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha", release="v3.1.2")
            + _scopeless_entry("The only unreleased work"),
            classification=None,
        )
        assert release_readiness.check_releasability(project) == 1
        captured = capsys.readouterr()
        assert "nothing to classify" not in captured.out
        assert "The only unreleased work" in captured.err

    def test_every_offending_entry_is_named_not_just_the_first(self, tmp_path, capsys):
        """'Refuse and name them' is worth nothing if it names one of three.

        The remedy is per-entry, so a message that stops at the first sends the
        operator through as many re-runs as there are entries — and each re-run
        looks like a fresh failure.
        """
        project = _make_project(
            tmp_path,
            entries=_scopeless_entry("First unscoped")
            + _entry("A", "alpha")
            + _scopeless_entry("Second unscoped")
            + _scopeless_entry("Third unscoped"),
            classification="| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        assert "First unscoped" in err
        assert "Second unscoped" in err
        assert "Third unscoped" in err
        assert "3 release-pending change-log entries" in err
        assert "4 change-log entries, 4 tagged, 4 release-pending across 1 scope(s), 3 unclassifiable" in err

    def test_the_refusal_uses_exit_1_not_3(self, tmp_path, capsys):
        """3 means the gate's SUBJECT could not be read. Here it read fine.

        The change log parsed, the entry parsed, its tag line parsed — which is
        what the message *demonstrates* by naming the entry and its line number,
        and what makes 3 the wrong code. What cannot be evaluated is the WORK,
        and that is what exit 1 already means everywhere else in this gate;
        `no-release-plan` reaches it the same way. A new code would split one
        meaning across two values.
        """
        project = _make_project(
            tmp_path,
            entries=_scopeless_entry("An unscoped change"),
            classification=None,
        )
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        # The subject read fine, and this is the evidence: the gate could only
        # print a title and a line number by having parsed the entry.
        assert "An unscoped change" in err
        # A real line number, not the dataclass default: an entry the parser
        # never located would print 0 and read as parsed anyway.
        assert re.search(r"change-log line [1-9]\d*\)", err)
        assert "1 release-pending change-log entry with no `scope=`" in err

    def test_a_scoped_only_log_refuses_nothing(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha") + _entry("B", "beta"),
            classification="| alpha | ships | |\n| beta | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 0
        assert "unclassifiable-pending-entry" not in capsys.readouterr().err

    def test_a_scopeless_entry_that_already_shipped_is_not_pending(self, tmp_path, capsys):
        """`release=` settles it, scope or no scope.

        Historical entries predating the `scope=` convention carry a release tag
        and nothing else; this repo has dozens. Refusing on those would fail the
        gate on every past release forever, which is the difference between a
        control and an obstacle.
        """
        project = _make_project(
            tmp_path,
            entries=_scopeless_entry("Ancient history", release="v1.0.0")
            + _entry("A", "alpha"),
            classification="| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 0, capsys.readouterr().err

    def test_an_untagged_entry_is_still_invisible(self, tmp_path, capsys):
        """Predating the tag convention is not being tagged wrong.

        The gate has never claimed authority over untagged history, and this
        refusal must not quietly extend it there — an entry with no tag line is
        not a release-pending entry missing its scope.
        """
        project = _make_project(
            tmp_path,
            entries="## Historical entry\n\nNo tag line at all.\n\n" + _entry("A", "alpha"),
            classification="| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 0, capsys.readouterr().err

    def test_the_pending_branch_reports_entries_AND_scopes(self, tmp_path, capsys):
        """The accounting the branch never had: two entries, one scope.

        Entry count and scope count differ for an ordinary reason — several
        entries per scope — so the emission has to carry both or it cannot show
        the gap the reconciliation exists to measure.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha") + _entry("B", "alpha") + _entry("C", "beta", release="v3.1.2"),
            classification="| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 0
        out = capsys.readouterr().out
        assert "3 change-log entries, 3 tagged, 2 release-pending across 1 scope(s), 0 unclassifiable" in out

    def test_the_no_pending_branch_accounting_is_unchanged(self, tmp_path, capsys):
        """The branch that always had the accounting keeps it verbatim.

        This chunk adds an emission to the other branch; it does not renegotiate
        this one. The re-run diagnosis that depends on it — `N scope(s) already
        tagged` — is pinned separately in TestIdempotentAcrossItsOwnRunbook.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha", release="v3.1.2"),
            classification=None,
        )
        assert release_readiness.check_releasability(project) == 0
        out = capsys.readouterr().out
        assert "releasable: no release-pending scopes — nothing to classify" in out
        assert "1 change-log entries scanned, 1 tagged" in out


class TestReconciliationAgainstTheRealChangeLog:
    """One test reads this repo's real log, and it asserts the INVARIANT.

    Six `TestAgainstTheReal*` guards died together at v3.3.0 because they pinned
    the repo's current release PHASE — and a release is the event that ends that
    phase, so they went red under exactly the pressure that makes relaxing them
    tempting. So this states WHICH emptiness it rejects: a change log that
    parsed to nothing. An empty *pending* set is not rejected — that is what a
    just-tagged release looks like, and it is a pass.
    """

    def _entries(self):
        from lib import change_log

        log = Path(__file__).resolve().parents[1] / ".prawduct" / "change-log.md"
        if not log.is_file():
            pytest.skip("no .prawduct/change-log.md in this checkout")
        return change_log.parse_change_log(log.read_text(encoding="utf-8"))

    def test_entries_and_scopes_reconcile(self):
        entries = self._entries()
        assert entries, "the change log parsed to zero entries — the parser, not the log"
        assert any(e.tag_line_count > 0 for e in entries), "no tagged entries parsed"

        pending = release_readiness.release_pending_entries(entries)
        scopes = release_readiness.release_pending_scopes(entries)
        unclassifiable = release_readiness.unclassifiable_pending_entries(entries)

        # Entries >= scopes always: several entries share one scope, and never
        # the reverse. A scope count that outran the entries would mean the two
        # collectors disagree about what release-pending means.
        assert len(pending) >= len(scopes)

        unclassifiable_ids = {id(e) for e in unclassifiable}
        classified = [e for e in pending if id(e) not in unclassifiable_ids]
        assert len(classified) + len(unclassifiable) == len(pending)
        assert {e.tags["scope"] for e in classified} == set(scopes), (
            "every classified pending entry's scope must be one the gate enumerates"
        )


class TestPlanCoverageIsReportedNotFatal:
    """A release-pending scope with no build plan is a Principle 6 signal.

    Rehomed from the same retiring caller. Reported rather than fatal: the gate
    fails closed on state it cannot EVALUATE, and a missing build plan does not
    make the release state unevaluable — the classification table still
    classifies the scope. Escalating it here would be a new gate semantic.
    """

    def test_scope_with_no_plan_warns_but_passes(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 0
        err = capsys.readouterr().err
        assert "no build-plan file" in err
        assert "alpha" in err

    def test_an_archived_plan_counts_as_coverage(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
        )
        _write(
            project / ".prawduct" / "artifacts" / "archive" / "build-plan-alpha.md",
            "---\nartifact: build-plan\nscope: alpha\n---\n\n## Status\n",
        )
        assert release_readiness.check_releasability(project) == 0
        assert "no build-plan file" not in capsys.readouterr().err

    def test_duplicate_scope_is_reported(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
        )
        for name in ("build-plan-a.md", "build-plan-b.md"):
            _write(
                project / ".prawduct" / "artifacts" / name,
                "---\nartifact: build-plan\nscope: alpha\n---\n\n## Status\n",
            )
        assert release_readiness.check_releasability(project) == 0
        assert "duplicate scope" in capsys.readouterr().err

    def test_a_duplicate_scope_is_reported_with_nothing_release_pending(
        self, tmp_path, capsys
    ):
        """**The case that was silent.** Rehoming this check put it behind the
        no-pending early return, so a repo between releases — the state most
        repos are in most of the time, and the cheapest moment to fix a malformed
        plan — never ran it. The question it asks is about repo *structure*, not
        about the pending set, so it is not the early return's business.

        Fixing it here is cheap; discovering it mid-release, when scope→plan
        resolution has just become load-bearing, is the expensive order.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha", release="v3.2.0"),
            classification=None,
        )
        for name in ("build-plan-a.md", "build-plan-b.md"):
            _write(
                project / ".prawduct" / "artifacts" / name,
                "---\nartifact: build-plan\nscope: alpha\n---\n\n## Status\n",
            )
        assert release_readiness.check_releasability(project) == 0
        out = capsys.readouterr()
        assert "no release-pending scopes" in out.out, (
            "the fixture must exercise the no-pending path, or this tests nothing"
        )
        assert "duplicate scope" in out.err

    def test_the_missing_plan_half_stays_scoped_to_the_pending_set(
        self, tmp_path, capsys
    ):
        """Only the duplicate-scope half hoists. "A release-pending scope has no
        plan" is a statement ABOUT the pending set, so on an empty one it has
        nothing to say and must stay quiet rather than reach for a denominator
        it does not have."""
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha", release="v3.2.0"),
            classification=None,
        )
        assert release_readiness.check_releasability(project) == 0
        assert "no build-plan file" not in capsys.readouterr().err


def _digest(section_body: str, *, heading: str = "## v9.9.9", older: str = "") -> str:
    """A consumer digest whose OPEN section is the topmost one."""
    return (
        "# Digest\n\nPreamble prose that belongs to no section.\n\n"
        f"{heading}\n\n{section_body}\n" + older
    )


def _warned_scopes(err: str) -> set[str]:
    """Scopes named by a digest-coverage warning.

    Reads the machine-stable part of the message — ``scope='name'`` — rather
    than the sentence around it, so rewording the advice does not silently turn
    these assertions green against a check that stopped working.
    """
    return set(re.findall(r"could not find release-pending scope='([^']+)'", err))


class TestDigestCoverageIsAdvisory:
    """A release-pending scope can reach the tag with no consumer-facing note.

    It happened at the v3.4.0 cut: `scope=tactical-efficiency` carried nine
    `release=v3.4.0` entries and no mention in the digest. The failure is
    asymmetric — a section full of good notes reads as finished, so the missing
    scope is invisible exactly when the digest looks healthiest.

    Everything here is a fixture. The claim under test is about *this check*,
    and pinning it against this repo's live digest would pin the repo's current
    release phase as an invariant — the way six `TestAgainstTheReal*` guards
    died at v3.3.0.
    """

    def test_a_scope_absent_from_the_open_section_warns(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest=_digest("Notes about something else entirely."),
        )
        assert release_readiness.check_releasability(project) == 0
        assert _warned_scopes(capsys.readouterr().err) == {"alpha"}

    def test_a_scope_named_in_the_open_section_does_not_warn(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest=_digest("**alpha now does the thing.** Consumers can rely on it."),
        )
        assert release_readiness.check_releasability(project) == 0
        assert _warned_scopes(capsys.readouterr().err) == set()

    def test_writing_the_note_is_what_stops_the_warning(self, tmp_path, capsys):
        """**The advisory's EFFECT, not that it fires.**

        This recommendation ships to every consumer's repo, so the promise it
        makes — *write a note and this stops* — has to be known to work rather
        than known to print. The un-written case is kept as the control in the
        same test, because a treatment observed without one proves only that
        the fixture differs somehow.
        """
        control = _make_project(
            tmp_path / "control",
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest=_digest("Nothing about the shipped work."),
        )
        assert release_readiness.check_releasability(control) == 0
        assert "alpha" in _warned_scopes(capsys.readouterr().err), (
            "the control must warn, or the treatment below proves nothing"
        )

        treatment = _make_project(
            tmp_path / "treatment",
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest=_digest("**alpha ships.** Here is what it means for you."),
        )
        assert release_readiness.check_releasability(treatment) == 0
        assert _warned_scopes(capsys.readouterr().err) == set()

    def test_the_advisory_never_changes_a_passing_verdict(self, tmp_path, capsys):
        """Asserted as a DIFFERENCE, not as `== 0`.

        `== 0` on an uncovered fixture would still pass if the check one day
        started refusing on a *covered* one. Running the same project under both
        digests and comparing the two exit codes is the claim itself: whatever
        the verdict is, this check is not part of it.
        """
        covered = _make_project(
            tmp_path / "covered",
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest=_digest("**alpha ships.**"),
        )
        uncovered = _make_project(
            tmp_path / "uncovered",
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest=_digest("Unrelated."),
        )
        assert release_readiness.check_releasability(covered) == 0
        assert release_readiness.check_releasability(uncovered) == 0
        assert "alpha" in _warned_scopes(capsys.readouterr().err), (
            "the uncovered run must actually warn, or the equality is vacuous"
        )

    def test_the_advisory_never_changes_a_failing_verdict(self, tmp_path, capsys):
        """The same difference on the branch where the gate refuses.

        A warning that quietly upgraded a refusal's *reason* would be invisible
        to the passing-case test above, and this gate's exit code is a contract
        that skills bind to.
        """
        entries = _entry("A", "alpha") + _entry("B", "beta")
        covered = _make_project(
            tmp_path / "covered",
            entries=entries,
            classification="| alpha | ships | |\n",
            digest=_digest("**alpha** and **beta** both explained."),
        )
        uncovered = _make_project(
            tmp_path / "uncovered",
            entries=entries,
            classification="| alpha | ships | |\n",
            digest=_digest("Unrelated."),
        )
        assert release_readiness.check_releasability(covered) == 1
        assert release_readiness.check_releasability(uncovered) == 1
        err = capsys.readouterr().err
        assert _warned_scopes(err) == {"alpha", "beta"}
        assert "unclassified scope(s)" in err, (
            "the refusal must be the pre-existing one, not something this check caused"
        )

    def test_an_unreadable_digest_names_its_own_consequence(self, tmp_path, capsys):
        """**Advice fails soft is not advice fails silent.**

        A skipped check that says nothing is indistinguishable from one that
        passed, so the degraded path states what went unchecked and what that
        costs — otherwise it manufactures the false all-clear it exists to
        prevent. A product repo lives on this path permanently: the digest
        ships inside the plugin and never lands downstream.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest=None,
        )
        assert release_readiness.check_releasability(project) == 0
        err = capsys.readouterr().err
        assert "digest coverage not checked" in err
        assert "would not be reported here" in err, (
            "the note must name the consequence, not only the cause"
        )
        assert _warned_scopes(err) == set()

    def test_a_digest_with_no_section_names_its_own_consequence(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest="# Digest\n\nProse, but no version section anywhere.\n",
        )
        assert release_readiness.check_releasability(project) == 0
        err = capsys.readouterr().err
        assert "digest coverage not checked" in err
        assert "would not be reported here" in err
        assert "headline every upgrading repo is shown went unread" in err, (
            "both questions share this read, so the note owes both consequences "
            "— a headline that went unchecked is the one a consumer actually sees"
        )
        assert _warned_scopes(err) == set()

    def test_a_mis_encoded_digest_reports_rather_than_crashing(self, tmp_path, capsys):
        """A bad byte must reach the NOTE, not the operator's terminal.

        `read_text` raises `UnicodeDecodeError` — a `ValueError`, not an
        `OSError` — so a reader catching only the latter turns the one arm that
        must fail soft into a traceback, and takes the authority gate beside it
        down on the way. The refusing reads in this module share the widened
        catch for the mirror reason: they promise a named reason on every
        failure path.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest="# Digest\n\n## v9.9.9\n\n**alpha** ships.\n",
        )
        (project / _DIGEST_REL_PATH).write_bytes(b"# Digest\n\n## v9.9.9\n\n\xff\xfe not utf-8\n")
        assert release_readiness.check_releasability(project) == 0
        err = capsys.readouterr().err
        assert "digest coverage not checked" in err
        assert "cannot read" in err

    def test_a_mis_encoded_change_log_refuses_with_its_named_reason(
        self, tmp_path, capsys
    ):
        """The refusing half of the same class.

        `check_releasability` promises every failure path returns 1 with a named
        reason; a traceback is neither.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest=_digest("**alpha** ships."),
        )
        (project / ".prawduct" / "change-log.md").write_bytes(b"# Change Log\n\n\xff\xfe\n")
        assert release_readiness.check_releasability(project) == 1
        assert "no-change-log:" in capsys.readouterr().err

    def test_only_the_open_section_counts_as_coverage(self, tmp_path, capsys):
        """A note in a SHIPPED section is not a note for this release.

        The digest accumulates every past release, so a whole-file search would
        report a scope as covered on the strength of prose written for a version
        that shipped months ago — a false all-clear on exactly the scope most
        likely to be a repeat area of work.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest=_digest(
                "This release's notes, silent on the shipped work.",
                older="\n## v1.0.0\n\n**alpha** was described here, one release ago.\n",
            ),
        )
        assert release_readiness.check_releasability(project) == 0
        assert _warned_scopes(capsys.readouterr().err) == {"alpha"}

    def test_a_heading_that_is_not_a_version_still_delimits(self, tmp_path, capsys):
        """The section boundary is `## `, deliberately looser than a version match.

        A stricter pattern would let a heading it cannot parse fail to *delimit*:
        the section below would merge into the open one and its prose would read
        as this release's coverage. That is a false pass produced by the
        strictness itself, in a check whose whole job is noticing absence.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest=_digest(
                "This release's notes, silent on the shipped work.",
                older="\n## Unreleased (not a version)\n\n**alpha** lives down here.\n",
            ),
        )
        assert release_readiness.check_releasability(project) == 0
        assert _warned_scopes(capsys.readouterr().err) == {"alpha"}

    def test_a_composed_slug_does_not_cover_its_shorter_sibling(self, tmp_path, capsys):
        """`adhoc-delegation` is not a note about `delegation`.

        Slugs compose, and both halves ship different work. A word-boundary
        match breaks on the hyphen and would mark the shorter scope covered on
        the strength of the longer one's note — the silent pass, one character
        narrower than the substring bug it replaced.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "delegation") + _entry("B", "adhoc-delegation"),
            classification="| delegation | ships | |\n| adhoc-delegation | ships | |\n",
            digest=_digest("**adhoc-delegation** is explained at length here."),
        )
        assert release_readiness.check_releasability(project) == 0
        assert _warned_scopes(capsys.readouterr().err) == {"delegation"}

    def test_prose_spelling_the_slug_as_words_counts_as_coverage(self, tmp_path, capsys):
        """Consumer prose says "manifest state diagnosis", never the slug.

        Matching the slug alone would report nearly every scope as uncovered,
        which is how a fuzzy advisory becomes noise nobody reads.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "manifest-state-diagnosis"),
            classification="| manifest-state-diagnosis | ships | |\n",
            digest=_digest("**Manifest state diagnosis** now tells you what it found."),
        )
        assert release_readiness.check_releasability(project) == 0
        assert _warned_scopes(capsys.readouterr().err) == set()

    def test_nothing_release_pending_reads_no_digest(self, tmp_path, capsys):
        """"A pending scope has no note" has nothing to say about an empty set.

        Scoped to the pending set the way the missing-build-plan half is, and
        for the same reason: on an empty one it must stay quiet rather than
        reach for a denominator it does not have.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha", release="v3.2.0"),
            classification=None,
            digest=None,
        )
        assert release_readiness.check_releasability(project) == 0
        out = capsys.readouterr()
        assert "no release-pending scopes" in out.out, (
            "the fixture must exercise the no-pending path, or this tests nothing"
        )
        assert "digest coverage" not in out.err
        assert "digest coverage" not in out.out

    def test_a_repo_that_publishes_no_digest_says_nothing_at_all(self, tmp_path, capsys):
        """A product repo has no consumer digest to be *missing*.

        Every `plugin/…` path this module prints names prawduct's own layout,
        and the module ships inside `plugin/` to every product — so downstream
        those paths cannot exist. Reporting one as unread would describe a file
        the reader has no way to have, on every run, forever.

        **Silence here is not the fail-silent this check otherwise refuses.**
        That rule governs a check that ran and could not answer; this one has no
        subject, and the two are different states. The degraded NOTE is still
        mandatory wherever the digest is a thing this repo publishes, which is
        what the neighbouring tests pin.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            version="1.0.0",
            digest=None,
        )
        (project / "plugin" / "VERSION").unlink()
        assert release_readiness.check_releasability(project, release="v1.0.0") == 0
        out = capsys.readouterr()
        assert "digest coverage" not in out.err + out.out
        assert _DIGEST_REL_PATH not in out.err + out.out, (
            "a product repo must never be shown prawduct's own layout"
        )

    def test_a_subsection_does_not_truncate_the_open_section(self, tmp_path, capsys):
        """`### ` is not a section boundary — only `## ` is.

        A digest that organises a release under subsections would otherwise end
        its open section at the first one, and every scope described below that
        point would read as absent. The boundary is loose about what follows
        `## `, and strict about the marker itself.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest=_digest("Opening prose.\n\n### Fixes\n\n**alpha** is described here."),
        )
        assert release_readiness.check_releasability(project) == 0
        assert _warned_scopes(capsys.readouterr().err) == set()

    def test_the_yield_is_reported_even_when_every_scope_is_covered(
        self, tmp_path, capsys
    ):
        """A control heard from only when it fires can never be retired.

        The one honest argument for dropping this check later is a run of it
        finding nothing — which requires it to have counted out loud, against a
        denominator, on the runs where it found nothing.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha") + _entry("B", "beta"),
            classification="| alpha | ships | |\n| beta | ships | |\n",
            digest=_digest("**alpha** and **beta** are both described."),
        )
        assert release_readiness.check_releasability(project) == 0
        out = capsys.readouterr()
        assert _warned_scopes(out.err) == set()
        assert "digest coverage: 2 of 2" in out.out


class TestTheHeadlineIsChecked:
    """The consumer-facing headline is a hand step, and it gets forgotten.

    The version-delta banner shows a section's first non-empty line to every
    repo crossing that version, so the headline IS the release as far as a
    consumer is concerned. v2.1.6 was tagged and version-bumped with no section
    at all; v3.4.0 had one and still led with the seed the previous cut wrote,
    after eight weeks of good notes had accumulated underneath it.

    Fixtures throughout, for the reason the neighbouring class states: pinning
    this against the live digest would pin this repo's current release phase as
    an invariant, and a release is the event that ends that phase.
    """

    def test_a_section_with_no_headline_warns(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest="# Digest\n\n## v9.9.9\n\n## v1.0.0\n\nOld news.\n",
        )
        assert release_readiness.check_releasability(project) == 0
        err = capsys.readouterr().err
        assert "has no headline" in err
        assert "## v9.9.9" in err, "the warning must name the section it read"

    def test_a_heading_is_not_a_headline(self, tmp_path, capsys):
        """A section opening on a subsection has no headline, not a `###` one.

        The banner stops at the first heading rather than rendering it, so a
        digest organised as `## v9.9.9` / `### Fixes` shows consumers a blank.
        Reading the subheading as the headline here would report a section the
        banner renders empty as perfectly healthy.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest=_digest("### Fixes\n\n**alpha** is described here."),
        )
        assert release_readiness.check_releasability(project) == 0
        assert "has no headline" in capsys.readouterr().err

    def test_the_seeded_placeholder_warns(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest=_digest(
                "**Prerelease under test — this build is the develop branch "
                "ahead of the next release.**\n\n**alpha** ships."
            ),
        )
        assert release_readiness.check_releasability(project) == 0
        assert "still leads with the seeded placeholder" in capsys.readouterr().err

    def test_a_real_headline_is_silent(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest=_digest("**alpha now does the thing.** Consumers can rely on it."),
        )
        assert release_readiness.check_releasability(project) == 0
        err = capsys.readouterr().err
        assert "headline" not in err

    def test_writing_the_headline_is_what_stops_the_warning(self, tmp_path, capsys):
        """**The advisory's EFFECT, with the un-written case as the control.**

        The recommendation this prints — replace the seed and this stops — has
        to be known to work rather than known to fire, because it ships to every
        repo that runs the gate. A treatment observed without a control proves
        only that the two fixtures differ somehow.
        """
        seed = (
            "**Prerelease under test — this build is the develop branch ahead "
            "of the next release.**"
        )
        control = _make_project(
            tmp_path / "control",
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest=_digest(seed + "\n\n**alpha** ships."),
        )
        assert release_readiness.check_releasability(control) == 0
        assert "seeded placeholder" in capsys.readouterr().err, (
            "the control must warn, or the treatment below proves nothing"
        )

        treatment = _make_project(
            tmp_path / "treatment",
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest=_digest("**alpha ships.** Here is what it means for you."),
        )
        assert release_readiness.check_releasability(treatment) == 0
        assert "headline" not in capsys.readouterr().err

    def test_the_headline_is_reported_even_when_it_is_fine(self, tmp_path, capsys):
        """A control heard from only when it fires can never be retired.

        And the yield here is the headline itself, not a count of them: the
        failure mode is a line nobody looked at, so putting that exact line in
        front of the operator is what the emission is for.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest=_digest("**alpha ships.** Here is what it means for you."),
        )
        assert release_readiness.check_releasability(project) == 0
        out = capsys.readouterr().out
        assert "digest headline: '**alpha ships.** Here is what it means for you.'" in out

    def test_the_advisory_never_changes_the_exit_code(self, tmp_path, capsys):
        """Coverage, not authority — the same disposition the scope check holds.

        Phase 0 runs BEFORE the step that writes the headline, so on a correct
        release this fires once and is then fixed. A refusal here would block a
        release for a condition the release is on its way to fixing.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest="# Digest\n\n## v9.9.9\n",
        )
        assert release_readiness.check_releasability(project) == 0
        out = capsys.readouterr()
        assert "has no headline" in out.err
        assert "releasable: v3.2.0 — 1 release-pending scope(s)" in out.out, (
            "the advisory must leave the pass verdict exactly as it found it"
        )

    def test_a_repo_that_publishes_no_digest_is_asked_no_headline_question(
        self, tmp_path, capsys
    ):
        """Downstream there is no `plugin/CHANGELOG.md` to have a headline in.

        Same predicate as the coverage check beside it, and deliberately the
        same one rather than a second `.exists()`: every `plugin/…` path this
        module can print names prawduct's own layout, and asking a product user
        about a file they have no way to have is an instruction they can only
        fail. This is the third message that would have entered that class.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            version="1.0.0",
            digest=None,
        )
        (project / "plugin" / "VERSION").unlink()
        assert release_readiness.check_releasability(project, release="v1.0.0") == 0
        out = capsys.readouterr()
        assert "headline" not in out.err + out.out

    def test_the_line_this_judges_is_the_line_the_banner_shows(self, tmp_path):
        """The two implementations must agree about EMPTINESS.

        The banner is a hook and `lib/` never imports from a hook, so the
        headline rule is stated twice. What has to hold is not that the two
        strip emphasis alike but that they agree on the only thing this check
        claims: a section the banner renders blank is a section this warns
        about, and one it renders is one this leaves alone. Asserting the
        weaker property is what keeps this test from failing on a cosmetic
        difference while missing the divergence that matters.
        """
        spec = importlib.util.spec_from_file_location(
            "prawduct_banner", ROOT / "hooks" / "banner.py"
        )
        banner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(banner)

        for body, renders in (
            ("**alpha ships.** Details.", True),
            ("", False),
            ("### Fixes\n\n**alpha** is described here.", False),
        ):
            root = tmp_path / f"root{renders}{len(body)}"
            _write(root / "CHANGELOG.md", _digest(body))
            shown = dict(banner.parse_changelog(root)).get("9.9.9", "")
            section = release_readiness._open_digest_section(
                (root / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
            )
            judged = release_readiness._section_headline(section[1])
            assert bool(shown) == renders, f"banner disagrees about {body!r}"
            assert (judged is not None) == renders, (
                f"the gate and the banner disagree about {body!r} — one of them "
                "is reporting a headline the consumer never sees"
            )


class TestTheSuiteMustBeProvenGreen:
    """A release must not proceed on code nothing has said passes.

    v2.1.6 shipped on a red suite: the release path read no test result at all,
    so the redness was visible only to whoever happened to run the suite. This
    is a verdict about whether the release may proceed, so unlike the digest
    advisories beside it, it fails closed.

    **What it does not claim.** The predicate is `gates.tests_are_current`,
    whose session-freshness disjunct asks when a run happened rather than which
    tree it met. That is the honest bound at this phase — Phase 0 runs before
    the release rewrites four files, so nothing checkable here can vouch for the
    tree the tag will carry.
    """

    def _project(self, tmp_path, **kwargs):
        return _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest=_digest("**alpha ships.** What it means for you."),
            **kwargs,
        )

    def test_a_green_run_passes_and_names_the_evidence(self, tmp_path, capsys):
        project = self._project(tmp_path)
        assert release_readiness.check_releasability(project) == 0
        out = capsys.readouterr().out
        assert "suite: green" in out, "the passing run must emit its own yield"
        assert "releasable:" in out

    def test_missing_evidence_refuses(self, tmp_path, capsys):
        project = self._project(tmp_path, evidence=None)
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        assert "unproven-suite:" in err
        assert "no .test-evidence.json" in err, "the refusal must say which condition failed"

    def test_a_failing_run_refuses(self, tmp_path, capsys):
        project = self._project(tmp_path, evidence=_evidence(failed=3))
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        assert "unproven-suite:" in err
        assert "3 test(s) failing" in err

    def test_a_degraded_run_refuses_rather_than_reading_as_a_pass(
        self, tmp_path, capsys
    ):
        """A contended run reports a plausible total and covers less than it says.

        Nothing in the counts can tell it apart from a clean pass, which is why
        the record carries the observation rather than deriving it — and why a
        release must read it as "no run", not as "a green run".
        """
        project = self._project(
            tmp_path,
            evidence=_evidence(degraded="a worker died; ~half never reported"),
        )
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        assert "unproven-suite:" in err
        assert "a worker died" in err

    def test_stale_evidence_refuses(self, tmp_path, capsys):
        """A run that predates this session and cannot say which tree it met.

        The record carries no `evidence_tree`, so the tree-validity clause that
        would otherwise rescue it has nothing to compare — which is exactly the
        `--from-counts` shape as well as the pre-clause one.
        """
        project = self._project(
            tmp_path,
            evidence=_evidence(timestamp="2026-01-01T00:00:00Z"),
            session_start="2026-06-01T00:00:00Z",
        )
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        assert "unproven-suite:" in err
        assert "predates session" in err

    def test_recording_a_green_run_is_what_lifts_the_refusal(self, tmp_path, capsys):
        """**The refusal's EFFECT, with the un-recorded case as the control.**

        The remedy this prints — run the suite, record it, re-run — has to be
        known to work. It names the next step, and the gate that judges that
        step is the one asked here rather than a cheaper proxy.
        """
        control = self._project(tmp_path / "control", evidence=None)
        assert release_readiness.check_releasability(control) == 1
        assert "unproven-suite:" in capsys.readouterr().err, (
            "the control must refuse, or the treatment below proves nothing"
        )

        treatment = self._project(tmp_path / "treatment")
        assert release_readiness.check_releasability(treatment) == 0
        assert "unproven-suite" not in capsys.readouterr().err

    def test_the_refusal_still_lets_every_other_check_report(self, tmp_path, capsys):
        """One command, every problem — the property this gate holds elsewhere.

        The verdict is returned at the bottom and reported at the top, so an
        operator whose suite is red still learns that a scope is unclassified
        and that a shipping scope has no consumer note. A bare early return
        would buy one problem per round trip.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha") + _entry("B", "beta"),
            classification="| alpha | ships | |\n",
            digest=_digest("Notes about nothing in particular."),
            evidence=None,
        )
        assert release_readiness.check_releasability(project) == 1
        out = capsys.readouterr()
        err = out.err
        assert "unproven-suite:" in err
        assert "unclassified scope(s)" in err, "the classification check must still have run"
        assert _warned_scopes(err) == {"alpha", "beta"}, "the digest check must still have run"
        assert "scanned:" in out.out, "the accounting must still have printed"

    def test_nothing_to_cut_is_not_refused_on_the_suite(self, tmp_path, capsys):
        """No release is proceeding, so there is no release to refuse.

        The no-pending branch answers "there is nothing to cut" and the runbook
        reads it as *stop*. Refusing it on an unproven suite would attach a
        remedy to a state that needs none.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha", release="v3.2.0"),
            classification=None,
            digest=None,
            evidence=None,
        )
        assert release_readiness.check_releasability(project) == 0
        out = capsys.readouterr()
        assert "no release-pending scopes" in out.out
        assert "unproven-suite" not in out.err

    def test_no_path_returns_0_while_the_suite_is_red(self, tmp_path, capsys):
        """The property the report-here/return-there split rests on.

        Everything else about this fixture passes — the scope is classified, the
        digest names it, the headline is real — so the ONLY thing between the
        verdict and a 0 is the return at the bottom. That is what makes this a
        pin rather than a duplicate: a `return 0` added anywhere between where
        `suite_ok` is computed and where it is consumed would drop a fail-closed
        verdict silently, and this is the test that would notice.
        """
        project = self._project(tmp_path, evidence=_evidence(failed=2))
        assert release_readiness.check_releasability(project, release="v3.2.0") == 1, (
            "a red suite must not reach a 0 by any route"
        )

    def test_the_v2_1_6_scenario_is_refused(self, tmp_path, capsys):
        """Version bumped, no headline — and the release stops.

        Both halves of this chunk meet here, and which one refuses is the
        design. The missing headline is caught by the advisory, which warns so
        the operator fixes it before the cut. What *stops* the release is the
        suite: a version with no digest section is precisely what
        `test_changelog_has_current_version_entry` fails on, so at v2.1.6 the
        missing headline WAS the red suite — and the release path read no test
        result, so it shipped anyway. The fixture states that redness rather
        than deriving it; the derivation lives in the guard named above.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
            digest="# Digest\n\n## v9.9.9\n\n## v1.0.0\n\nOld news.\n",
            evidence=_evidence(failed=1),
        )
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        assert "has no headline" in err, "the operator must be told what to write"
        assert "unproven-suite:" in err, "and the release must not proceed"


class TestReleasePlanSurvivesArchival:
    """BP8: archiving a shipped release plan must not make this gate fail closed.

    `_find_release_plan` globs one directory. Once release plans reach their end
    of life and move, a re-run against an already-cut version would report
    `no-release-plan` and refuse a release that demonstrably happened.
    """

    def test_an_archived_release_plan_is_found(self, tmp_path):
        project = _make_project(
            tmp_path, entries=_entry("A", "alpha"), classification=None
        )
        _write(
            project / ".prawduct" / "artifacts" / "archive" / "release-plan-v3.2.0.md",
            "# Release plan v3.2.0\n\n## Release classification\n\n"
            "| Scope | Disposition | Blocker |\n|---|---|---|\n| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 0

    def test_a_live_release_plan_wins_over_an_archived_namesake(self, tmp_path, capsys):
        # Ordering, not merely coverage: an archived plan for a version being
        # re-cut must never shadow the live one that supersedes it.
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha") + _entry("B", "beta"),
            classification="| alpha | ships | |\n| beta | ships | |\n",
        )
        _write(
            project / ".prawduct" / "artifacts" / "archive" / "release-plan-v3.2.0.md",
            "# Stale\n\n## Release classification\n\n"
            "| Scope | Disposition | Blocker |\n|---|---|---|\n| alpha | ships | |\n",
        )
        # The discriminator: the archived plan classifies only `alpha`, so if it
        # won, `beta` would come back unclassified and the gate would exit 1.
        assert release_readiness.check_releasability(project) == 0
        assert "unclassified" not in capsys.readouterr().err
