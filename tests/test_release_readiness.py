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

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))
from lib import release_readiness  # noqa: E402


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_project(
    tmp_path: Path,
    *,
    entries: str,
    classification: str | None,
    backlog: str = "",
    version: str = "3.2.0",
    plan_suffix: str = "",
) -> Path:
    project = tmp_path / "proj"
    _write(project / ".prawduct" / "change-log.md", "# Change Log\n\n" + entries)
    _write(project / ".prawduct" / "backlog.md", "# Backlog\n\n## Open\n\n" + backlog)
    _write(project / "plugin" / "VERSION", version + "\n")
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
