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
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))
from lib import change_fragments, consumer_digest, release_readiness  # noqa: E402


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
    plugin_version: bool = True,
    declaration: str | None = None,
    changelog: str | None = None,
    headline: str | None = None,
    evidence: dict | None = _EVIDENCE_DEFAULT,
    session_start: str | None = "2000-01-01T00:00:00Z",
) -> Path:
    project = tmp_path / "proj"
    # Since #1125 pending work is a fragment and the live log is history, so
    # `entries` is routed the way `migrate-change-log` leaves a repo: each
    # release-pending scoped entry becomes its scope's fragment, and everything
    # else (shipped, untagged) stays in the log. A test about the refusal of a
    # pending legacy entry writes the log itself (`_legacy_log_project`).
    history, pending = _route_entries(entries)
    _write(project / ".prawduct" / "change-log.md", "# Change Log\n\n" + history)
    (project / ".prawduct" / "changes").mkdir(parents=True, exist_ok=True)
    for scope in pending:
        _add_fragment(project, scope)
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
    # `plugin/VERSION` makes a project prawduct-shaped (the version fallback and
    # its hint); `plugin_version=False` builds a governed product instead.
    if plugin_version:
        _write(project / "plugin" / "VERSION", version + "\n")
    # The consumer digest is opt-in: with no `declaration` no state file is
    # written and the digest checks have no subject. `changelog` lands at the
    # root, where the product declarations in these tests point.
    if declaration is not None:
        _write(project / ".prawduct" / "project-state.yaml", declaration)
    if changelog is not None:
        _write(project / "CHANGELOG.md", changelog)
    if headline is not None:
        _write(project / ".prawduct" / "release-headline.md", headline)
    if classification is not None:
        name = f"release-plan-v{version}{plan_suffix}.md"
        _write(
            project / ".prawduct" / "artifacts" / name,
            f"# Release plan v{version}\n\n## Release classification\n\n"
            "| Scope | Disposition | Blocker |\n|---|---|---|\n" + classification,
        )
    return project


def _route_entries(entries: str) -> tuple[str, list[str]]:
    """``(log history, pending scopes)`` for fixture ``entries``.

    A tagged entry with a ``scope=`` and no ``release=`` is pending and becomes
    one fragment per scope; every other entry stays in the log verbatim.
    """
    history: list[str] = []
    pending: list[str] = []
    for block in re.split(r"(?m)^(?=## )", entries):
        tag = re.search(r"<!-- prawduct: (.*?) -->", block)
        scope = re.search(r"\bscope=([^\s|>]+)", tag.group(1)) if tag else None
        if tag and scope and "release=" not in tag.group(1):
            if scope.group(1) not in pending:
                pending.append(scope.group(1))
        else:
            history.append(block)
    return "".join(history), pending


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


class TestReleasePendingEntries:
    """``release_pending_entries`` is the legacy log's one pending predicate,
    kept for the refusal and the size archive; it enumerates no scope (#1022)."""

    def test_release_tagged_entries_are_not_pending(self):
        from lib import change_log

        content = _entry("A", "alpha") + _entry("B", "beta", release="v3.1.2")
        pending = release_readiness.release_pending_entries(change_log.parse_change_log(content))
        assert [e.title for e in pending] == ["A"], "a release= tag means the code already shipped"

    def test_untagged_entries_are_invisible(self):
        from lib import change_log

        content = "## Historical entry\n\nNo tag line at all.\n\n" + _entry("A", "alpha")
        pending = release_readiness.release_pending_entries(change_log.parse_change_log(content))
        assert [e.title for e in pending] == ["A"]


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

    def test_a_mis_encoded_change_log_refuses_with_its_named_reason(self, tmp_path, capsys):
        """`check_releasability` promises every failure path returns 1 with a named
        reason; a traceback is neither."""
        project = _make_project(tmp_path, entries=_entry("A", "alpha"), classification="| alpha | ships | |\n")
        (project / ".prawduct" / "change-log.md").write_bytes(b"# Change Log\n\n\xff\xfe\n")
        assert release_readiness.check_releasability(project) == 1
        assert "no-change-log:" in capsys.readouterr().err

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


class TestAnIssuesBlockerCanBeNamed:
    """#1033 — a `withheld` row may name its blocker as `#N` or `owner/repo#N`,
    and post-cutover its liveness comes from the local backlog cache."""

    SCOPE = "acme/backlog"

    def _project(self, tmp_path, blocker, *, cut_over=True):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification=f"| alpha | withheld | {blocker} |\n",
        )
        if cut_over:
            _write(
                project / ".prawduct" / "project-state.yaml",
                f"backlog_service_repo: {self.SCOPE}\n",
            )
        return project

    def _cache(self, project, *, close_first=False):
        """A synced cache holding two items, #1 and #2; ``close_first`` ships #1."""
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from fakes.fake_github import FakeGitHub
        from lib.backlog import core, sync

        # The store lives under `git --git-common-dir`, so the project is a work tree.
        subprocess.run(["git", "init", "-q"], cwd=project, check=True)
        fake = FakeGitHub()
        owner, repo = self.SCOPE.split("/")
        for title in ("release: the first item under test", "release: the second item under test"):
            assert core.file_item(fake, owner=owner, repo=repo, title=title, body="b")["status"] == "ok"
        if close_first:
            assert core.set_status(fake, id_raw=f"{self.SCOPE}#1", target="shipped")["status"] == "ok"
        assert sync.full_rebuild(fake, project_dir=project, owner=owner, repo=repo)["status"] == "ok"

    @pytest.mark.parametrize("cell", ["#12", "acme/backlog#12", "`#12` (go-live)"])
    def test_the_issues_spellings_parse(self, cell):
        classification, errors = release_readiness.parse_classification(
            f"## Release classification\n\n| alpha | withheld | {cell} |\n"
        )
        assert errors == []
        assert classification["alpha"][0] == release_readiness.WITHHELD
        assert classification["alpha"][1] in {"#12", "acme/backlog#12"}

    @pytest.mark.parametrize("cell", ["repo#12", "12", "#twelve"])
    def test_a_spelling_naming_no_repo_or_number_is_still_refused(self, cell):
        _classification, errors = release_readiness.parse_classification(
            f"## Release classification\n\n| alpha | withheld | {cell} |\n"
        )
        assert any("requires a blocker item id" in e for e in errors)

    @pytest.mark.parametrize("blocker", ["#1", "acme/backlog#1"])
    def test_an_open_issues_blocker_stands(self, tmp_path, capsys, blocker):
        project = self._project(tmp_path, blocker)
        self._cache(project)
        assert release_readiness.check_releasability(project, "v3.2.0") == 0
        assert f"alpha (blocked by {blocker})" in capsys.readouterr().out

    def test_a_closed_issues_blocker_is_stale(self, tmp_path, capsys):
        project = self._project(tmp_path, "#1")
        self._cache(project, close_first=True)
        assert release_readiness.check_releasability(project, "v3.2.0") == 1
        err = capsys.readouterr().err
        assert "alpha (withheld behind #1, which is not open)" in err

    def test_an_unreadable_cache_is_unverifiable_never_releasable(self, tmp_path, capsys):
        project = self._project(tmp_path, "#1")  # cut over, no cache synced
        assert release_readiness.check_releasability(project, "v3.2.0") == 1
        captured = capsys.readouterr()
        assert "cannot-verify-blockers: the backlog cache could not be read" in captured.err
        assert "which is not open" not in captured.err
        assert "releasable:" not in captured.out

    def test_an_id_the_cache_does_not_hold_is_unverifiable(self, tmp_path, capsys):
        project = self._project(tmp_path, "#9")
        self._cache(project)
        assert release_readiness.check_releasability(project, "v3.2.0") == 1
        err = capsys.readouterr().err
        assert f"the backlog cache for {self.SCOPE} holds no item #9" in err
        assert "which is not open" not in err

    def test_the_markdown_backend_accepts_the_row_and_cannot_verify_it(self, tmp_path, capsys):
        project = self._project(tmp_path, "#1", cut_over=False)
        assert release_readiness.check_releasability(project, "v3.2.0") == 1
        captured = capsys.readouterr()
        assert "requires a blocker item id" not in captured.err
        assert "cannot say whether the GitHub issue #1 is still open" in captured.err
        assert "releasable:" not in captured.out


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
    """The guard that hid a branch from v3.2.8, under the fragments-only gate.

    A ``release=`` that is not a version (``release=unreleased``) makes an
    unshipped legacy entry look shipped, so a reader keyed on the absence of
    ``release=`` cannot see it. Before #1125 the gate refused it as
    ``bad-change-log-tag``; now the live log is read only to refuse what is
    still pending there, and this shape is refused under the same
    ``legacy-pending-entry`` code, through the migration's own converter.
    """

    def test_placeholder_release_is_refused_and_named(self, tmp_path, capsys):
        project = _legacy_log_project(
            tmp_path,
            _entry("A", "alpha").replace("| scope=alpha", "| scope=alpha | release=unreleased"),
            classification="| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        line = next(x for x in err.splitlines() if "unreleased-placeholder" in x)
        assert line.startswith("legacy-pending-entry:")
        assert "'unreleased'" in line
        assert "delete the tag" in line

    def test_the_placeholder_would_otherwise_read_as_nothing_to_cut(self):
        """Why the refusal runs the migration's converter as well as the
        pending predicate: the predicate alone is blind to this entry."""
        from lib import change_log

        content = _entry("A", "alpha").replace("| scope=alpha", "| scope=alpha | release=unreleased")
        assert release_readiness.release_pending_entries(change_log.parse_change_log(content)) == []
        refusals = release_readiness.legacy_pending_refusals(content)
        assert any("unreleased-placeholder" in r for r in refusals), refusals

    def test_a_real_version_still_passes(self, tmp_path):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha") + _entry("B", "beta", release="v3.1.2"),
            classification="| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 0

    def test_a_four_part_product_releases(self, tmp_path):
        """History stamped with four-part versions, and a four-part release
        being cut: the history reader and the already-shipped match accept it."""
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha")
            + _entry("B", "beta", release="v1.2.3.4")
            + _entry("C", "gamma", release="v1.2.3.3-rc.1"),
            classification="| alpha | ships | |\n| beta | ships | |\n",
            version="1.2.3.4",
        )
        assert release_readiness.check_releasability(project) == 0

    def test_a_five_part_release_is_refused_and_named(self, tmp_path, capsys):
        project = _legacy_log_project(
            tmp_path,
            _entry("A", "alpha").replace("| scope=alpha", "| scope=alpha | release=v1.2.3.4.5"),
            classification="| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        assert "legacy-pending-entry:" in err
        assert "v1.2.3.4.5" in err

    def test_this_repos_own_change_log_passes_the_guard(self):
        """Sixty-plus entries of real history, so the guard cannot fail closed."""
        from lib import change_log, change_log_archive

        # Live log plus archive: released history moves to the archive, and the
        # guard must pass over every real entry, not only the pending ones left live.
        text = change_log_archive.load_all_text(Path(__file__).resolve().parents[1] / ".prawduct")
        if text is None:
            pytest.skip("no .prawduct/change-log.md in this checkout")
        entries = change_log.parse_change_log(text)
        assert [e for e in entries if e.tags.get("release")], "no release tags parsed"
        errors, _warnings = change_log.validate_change_log_tags(entries)
        assert errors == [], errors


class TestScopelessPendingEntryIsRefused:
    """A release-pending entry with no ``scope=`` stays visible.

    It reaches no row of a scope-keyed table, so it was refused as
    ``unclassifiable-pending-entry`` while the gate read the legacy log. The gate
    now reads fragments only and refuses every release-pending legacy entry, so a
    scopeless one is refused by the same ``legacy-pending-entry`` line, by name.
    """

    def test_a_scopeless_pending_entry_refuses_and_is_named(self, tmp_path, capsys):
        project = _legacy_log_project(
            tmp_path,
            _scopeless_entry("An unscoped change"),
            fragments=("alpha",),
            classification="| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        line = next(x for x in err.splitlines() if "An unscoped change" in x)
        # Named, because the remedy is mechanical only if the operator knows
        # which entry to move. A count alone sends them reading the whole log.
        assert line.startswith("legacy-pending-entry: 'An unscoped change'")
        assert ".prawduct/change-log.md line" in line

    def test_it_refuses_where_the_gate_would_otherwise_certify_a_pass(self, tmp_path, capsys):
        """The blindness itself: the scopeless entry is the only unreleased work,
        the fragment set is empty, and the no-pending return must not be reached."""
        project = _legacy_log_project(
            tmp_path,
            _entry("A", "alpha", release="v3.1.2") + _scopeless_entry("The only unreleased work"),
        )
        assert release_readiness.check_releasability(project) == 1
        captured = capsys.readouterr()
        assert "nothing to classify" not in captured.out
        assert "The only unreleased work" in captured.err

    def test_every_offending_entry_is_named_not_just_the_first(self, tmp_path, capsys):
        """'Refuse and name them' is worth nothing if it names one of three."""
        project = _legacy_log_project(
            tmp_path,
            _scopeless_entry("First unscoped")
            + _scopeless_entry("Second unscoped")
            + _scopeless_entry("Third unscoped"),
        )
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        named = [x for x in err.splitlines() if x.startswith("legacy-pending-entry: '")]
        assert len(named) == 3, err
        assert "First unscoped" in err and "Second unscoped" in err and "Third unscoped" in err

    def test_the_refusal_uses_exit_1_not_3(self, tmp_path, capsys):
        """3 means the gate's SUBJECT could not be read. Here it read fine: the
        message can only print a title and a line number by having parsed it."""
        project = _legacy_log_project(tmp_path, _scopeless_entry("An unscoped change"))
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        assert "An unscoped change" in err
        # A real line number, not the dataclass default.
        assert re.search(r"change-log\.md line [1-9]\d*\)", err)

    def test_a_scoped_only_log_refuses_nothing(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha") + _entry("B", "beta"),
            classification="| alpha | ships | |\n| beta | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 0
        assert "legacy-pending-entry" not in capsys.readouterr().err

    def test_a_scopeless_entry_that_already_shipped_is_not_pending(self, tmp_path, capsys):
        """`release=` settles it, scope or no scope: refusing shipped history
        would fail the gate on every past release forever."""
        project = _legacy_log_project(
            tmp_path,
            _scopeless_entry("Ancient history", release="v1.0.0"),
            fragments=("alpha",),
            classification="| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 0, capsys.readouterr().err

    def test_an_untagged_entry_is_still_invisible(self, tmp_path, capsys):
        """Predating the tag convention is not being tagged wrong."""
        project = _legacy_log_project(
            tmp_path,
            "## Historical entry\n\nNo tag line at all.\n\n",
            fragments=("alpha",),
            classification="| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 0, capsys.readouterr().err

    def test_the_pending_branch_names_fragments_and_history(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha") + _entry("C", "beta", release="v3.1.2"),
            classification="| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 0
        out = capsys.readouterr().out
        assert (
            "scanned: 1 change fragment(s) in .prawduct/changes/, 1 release-pending scope(s); "
            "1 .prawduct/change-log.md entries read as shipped history." in out
        )

    def test_the_no_pending_branch_names_the_same_denominator(self, tmp_path, capsys):
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha", release="v3.1.2"),
            classification=None,
        )
        assert release_readiness.check_releasability(project) == 0
        out = capsys.readouterr().out
        assert "releasable: no release-pending scopes — nothing to classify" in out
        assert "0 change fragment(s) in .prawduct/changes/" in out
        assert "1 .prawduct/change-log.md entries read as shipped history" in out


class TestReconciliationAgainstTheRealChangeLog:
    """One test reads this repo's real log, and it asserts the INVARIANT, not the
    phase: every release-pending entry the predicate finds is named by the
    refusal. Whether there are any is the repo's state, not this test's claim."""

    def test_every_pending_entry_is_named_by_the_refusal(self):
        from lib import change_log

        log = Path(__file__).resolve().parents[1] / ".prawduct" / "change-log.md"
        if not log.is_file():
            pytest.skip("no .prawduct/change-log.md in this checkout")
        text = log.read_text(encoding="utf-8")
        entries = change_log.parse_change_log(text)
        assert entries, "the change log parsed to zero entries — the parser, not the log"
        assert any(e.tag_line_count > 0 for e in entries), "no tagged entries parsed"

        refusals = release_readiness.legacy_pending_refusals(text, entries)
        for entry in release_readiness.release_pending_entries(entries):
            assert any(f"{entry.title!r} (" in r for r in refusals), entry.title


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

    def test_an_unscoped_plan_caveats_the_sentence_without_moving_the_verdict(
        self, tmp_path, capsys
    ):
        """The warning was flatly FALSE for an unscoped plan, not merely thin.

        The map is keyed on frontmatter `scope:`, so a perfectly good plan that
        omits the key is absent from it — and the gate then told an operator
        that work is shipping undocumented about a plan sitting in the same
        directory. This is the v3.3.4 recurrence exactly.

        The verdict does not move, and that is deliberate: which scope an
        unscoped plan belongs to is precisely what nothing here can know, so
        suppressing the warning would trade a false positive for a false
        negative.
        """
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
        )
        _write(
            project / ".prawduct" / "artifacts" / "build-plan-mystery.md",
            "---\nartifact: build-plan\n---\n\n## Status\n\n- [ ] Chunk 01: a\n",
        )
        assert release_readiness.check_releasability(project) == 0
        err = capsys.readouterr().err
        assert "no build-plan file" in err, "the warning itself must survive"
        assert "declare no `scope:`" in err, "and it must say the lookup was partial"

    def test_without_one_the_sentence_carries_no_caveat(self, tmp_path, capsys):
        """Without this the assertion above passes on a clause that always
        prints, and a caveat that never goes quiet is one nobody reads."""
        project = _make_project(
            tmp_path,
            entries=_entry("A", "alpha"),
            classification="| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 0
        err = capsys.readouterr().err
        assert "no build-plan file" in err
        assert "declare no `scope:`" not in err

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


#: A product's declaration: a root `CHANGELOG.md`, so every message naming it
#: can be told apart from prawduct's own `plugin/CHANGELOG.md`.
_PRODUCT_DECLARATION = "consumer_digest:\n  path: CHANGELOG.md\n  headline: required\n"
_CHANGELOG = "# Changelog\n\n## [Unreleased]\n\n## v1.3.0\n\nOld news.\n"
_HEADLINE = "Release notes now reach the changelog.\n"

#: Prawduct's own declaration values. `TestPrawductDeclaresItsOwnDigest` pins
#: that the committed `.prawduct/project-state.yaml` parses to exactly this,
#: so the banner test below renders what the real cut will render.
_PRAWDUCT_DECLARATION = consumer_digest.Declaration(
    path="plugin/CHANGELOG.md", heading="## {version}", headline="required", layout="paragraphs"
)


def _declared_project(
    tmp_path: Path,
    *,
    declaration: str | None = _PRODUCT_DECLARATION,
    changelog: str | None = _CHANGELOG,
    headline: str | None = _HEADLINE,
    entries: str | None = None,
    classification: str = "| alpha | ships | |\n",
    plugin_version: bool = False,
    **kwargs,
) -> Path:
    """A governed product — no `plugin/VERSION` — releasing v1.4.0.

    Every argument defaults to the healthy case, so a test states only the one
    thing it breaks.
    """
    return _make_project(
        tmp_path,
        entries=entries if entries is not None else _entry("A", "alpha"),
        classification=classification,
        version="1.4.0",
        plugin_version=plugin_version,
        declaration=declaration,
        changelog=changelog,
        headline=headline,
        **kwargs,
    )


def _digest_warnings(err: str, phrase: str) -> list[str]:
    """The WARNING lines carrying ``phrase`` — the smallest span a check owns.

    The fixture's scope has no build plan, so a plan-coverage warning prints
    beside these; matching the whole of stderr would let it satisfy an
    assertion about the digest.
    """
    return [line for line in err.splitlines() if line.startswith("WARNING: ") and phrase in line]


def _notes(err: str) -> list[str]:
    return [line for line in err.splitlines() if line.startswith("NOTE: ")]


def _assert_names_the_declared_path(line: str) -> None:
    assert "CHANGELOG.md" in line, f"the message must name the declared path: {line}"
    assert "plugin/CHANGELOG.md" not in line, f"prawduct's own path leaked into a product: {line}"


class TestTheHeadlineFileIsChecked:
    """Under `headline: required`, the release's headline is a pending file.

    The cut moves `.prawduct/release-headline.md` into the release's section,
    whose first line is what the version-delta banner shows every upgrading
    repo. The cut refuses `no-headline` without it; Phase 0 says so first,
    while it is still a one-line fix rather than a refused cut.
    """

    def test_an_absent_headline_file_warns_naming_the_declared_path(self, tmp_path, capsys):
        project = _declared_project(tmp_path, headline=None)
        assert release_readiness.check_releasability(project, release="v1.4.0") == 0
        out = capsys.readouterr()
        [warning] = _digest_warnings(out.err, "release-headline.md")
        assert "is absent" in warning
        assert "no-headline" in warning, "the warning must name the refusal it pre-empts"
        _assert_names_the_declared_path(warning)
        assert "  digest headline: none." in out.out

    def test_a_blank_headline_file_warns(self, tmp_path, capsys):
        project = _declared_project(tmp_path, headline="\n   \n\n")
        release_readiness.check_releasability(project, release="v1.4.0")
        [warning] = _digest_warnings(capsys.readouterr().err, "release-headline.md")
        assert "is empty" in warning
        _assert_names_the_declared_path(warning)

    def test_a_headline_that_is_a_heading_warns(self, tmp_path, capsys):
        """The banner reads no headline from a section that opens on a heading."""
        project = _declared_project(tmp_path, headline="\n# Big news\n\nThe real sentence.\n")
        release_readiness.check_releasability(project, release="v1.4.0")
        [warning] = _digest_warnings(capsys.readouterr().err, "release-headline.md")
        assert "starts with a heading ('# Big news')" in warning
        _assert_names_the_declared_path(warning)

    def test_an_unreadable_headline_file_warns_rather_than_crashing(self, tmp_path, capsys):
        project = _declared_project(tmp_path)
        (project / ".prawduct" / "release-headline.md").write_bytes(b"\xff\xfe not utf-8\n")
        assert release_readiness.check_releasability(project, release="v1.4.0") == 0
        [warning] = _digest_warnings(capsys.readouterr().err, "release-headline.md")
        assert "cannot be read" in warning
        _assert_names_the_declared_path(warning)

    def test_a_real_headline_is_silent_and_printed_back(self, tmp_path, capsys):
        project = _declared_project(tmp_path, headline="\n  Release notes now reach the changelog.  \nMore.\n")
        assert release_readiness.check_releasability(project, release="v1.4.0") == 0
        out = capsys.readouterr()
        assert _digest_warnings(out.err, "release-headline.md") == []
        assert (
            "  digest headline: 'Release notes now reach the changelog.' "
            "(.prawduct/release-headline.md → CHANGELOG.md)." in out.out
        )

    def test_headline_none_owes_no_headline(self, tmp_path, capsys):
        project = _declared_project(
            tmp_path, declaration="consumer_digest:\n  path: CHANGELOG.md\n  headline: none\n", headline=None
        )
        assert release_readiness.check_releasability(project, release="v1.4.0") == 0
        out = capsys.readouterr()
        assert _digest_warnings(out.err, "release-headline.md") == []
        assert "  digest headline: none." in out.out, "the yield prints whatever the mode"


class TestAPresentHeadlineFileIsCheckedInEitherMode:
    """The cut uses a present headline file whatever `headline:` says, so Phase 0
    checks one whatever it says; only its absence is owed solely under `required`."""

    _NONE = "consumer_digest:\n  path: CHANGELOG.md\n  headline: none\n"

    def test_a_heading_first_headline_warns_under_none(self, tmp_path, capsys):
        project = _declared_project(tmp_path, declaration=self._NONE, headline="# Big news\n")
        release_readiness.check_releasability(project, release="v1.4.0")
        [warning] = _digest_warnings(capsys.readouterr().err, "release-headline.md")
        assert "starts with a heading" in warning

    def test_an_unreadable_headline_file_warns_under_none(self, tmp_path, capsys):
        project = _declared_project(tmp_path, declaration=self._NONE)
        (project / ".prawduct" / "release-headline.md").write_bytes(b"\xff\xfe not utf-8\n")
        release_readiness.check_releasability(project, release="v1.4.0")
        [warning] = _digest_warnings(capsys.readouterr().err, "release-headline.md")
        assert "cannot be read" in warning and "no-headline" in warning


class TestAnAlreadyCutReleaseAsksNothing:
    """After the cut, the release file exists, the headline file is consumed and
    the section is the cut's own. Asking again would tell the operator to remove
    the section the cut just wrote, which a re-cut would not restore."""

    def test_the_checks_step_aside_with_a_note(self, tmp_path, capsys):
        project = _declared_project(
            tmp_path, headline=None,
            changelog="# Changelog\n\n## [1.4.0] - 2026-10-25\n\n- New.\n\n## [1.3.0]\n\n- Old.\n",
        )
        _write(project / ".prawduct" / "releases" / "v1.4.0.md", "## [1.4.0] - 2026-10-25\n\n- New.\n")
        assert release_readiness.check_releasability(project, release="v1.4.0") == 0
        out = capsys.readouterr()
        assert _digest_warnings(out.err, "release-headline.md") == []
        assert _digest_warnings(out.err, "is already a section") == []
        assert any("v1.4.0 is already cut" in line for line in _notes(out.err)), out.err
        assert "  digest: v1.4.0 already cut (.prawduct/releases/v1.4.0.md → CHANGELOG.md)." in out.out

    def test_without_the_release_file_the_same_state_warns(self, tmp_path, capsys):
        """The control: the warnings the step-aside suppresses do fire without it."""
        project = _declared_project(
            tmp_path, headline=None,
            changelog="# Changelog\n\n## [1.4.0] - 2026-10-25\n\n- New.\n",
        )
        release_readiness.check_releasability(project, release="v1.4.0")
        err = capsys.readouterr().err
        assert _digest_warnings(err, "release-headline.md") and _digest_warnings(err, "is already a section")


class TestAnUnreadableStateFileIsNotUndeclared:
    def test_it_warns_rather_than_falling_silent(self, tmp_path, capsys):
        project = _declared_project(tmp_path, declaration=None)
        (project / ".prawduct" / "project-state.yaml").mkdir()
        assert release_readiness.check_releasability(project, release="v1.4.0") == 0
        [warning] = [l for l in capsys.readouterr().err.splitlines() if "cannot be read" in l and "project-state" in l]
        assert "did not run" in warning


class TestEveryCutRefusalIsWarnedAboutFirst:
    """Phase 0 warns on each condition `consumer_digest.preflight` finds, the
    same list the cut refuses from, so it cannot fall behind the cut. These two
    were refusals Phase 0 once had no copy of."""

    def test_a_missing_marker_warns(self, tmp_path, capsys):
        project = _declared_project(
            tmp_path, declaration=_PRODUCT_DECLARATION + "  marker: <!-- releases below -->\n"
        )
        assert release_readiness.check_releasability(project, release="v1.4.0") == 0
        [warning] = _digest_warnings(capsys.readouterr().err, "`marker-missing`")
        _assert_names_the_declared_path(warning)

    def test_release_files_git_would_ignore_warn(self, tmp_path, capsys):
        project = _declared_project(tmp_path)
        _write(project / ".gitignore", ".prawduct/releases/\n")
        for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "base"]):
            subprocess.run(
                ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
                cwd=str(project), capture_output=True, check=True, timeout=15,
            )
        assert release_readiness.check_releasability(project, release="v1.4.0") == 0
        assert _digest_warnings(capsys.readouterr().err, "`releases-ignored`")


class TestASectionForTheReleaseIsReportedEarly:
    """The cut writes the release's section, so one already there is refused.

    `release-in-changelog` is the cut's refusal; this is the same condition,
    reported at Phase 0 through the same predicate (`consumer_digest.names_release`).
    """

    @pytest.mark.parametrize(
        "heading, fires",
        [
            ("## v1.4.0", True),
            ("## [1.4.0] - 2026-10-25", True),
            ("## v1.4.0-rc.1", False),
            ("## v1.4.0-dev", False),
            ("## v1.4.0.1", False),
            ("### v1.4.0", False),
        ],
    )
    def test_only_the_exact_release_fires(self, tmp_path, capsys, heading, fires):
        """A published `-rc.1` section is history and must not block the cut it previewed."""
        changelog = f"# Changelog\n\n{heading}\n\nWritten by hand.\n\n## v1.3.0\n\nOld news.\n"
        project = _declared_project(tmp_path, changelog=changelog)
        assert release_readiness.check_releasability(project, release="v1.4.0") == 0
        warnings = _digest_warnings(capsys.readouterr().err, "is already a section")
        if not fires:
            assert warnings == []
            return
        [warning] = warnings
        assert f"line 3 ({heading!r}) is already a section for v1.4.0" in warning
        assert "release-in-changelog" in warning
        assert "release-headline.md" in warning, "the remedy names where the text can go"
        _assert_names_the_declared_path(warning)

    def test_a_bare_release_number_is_normalized(self, tmp_path, capsys):
        project = _declared_project(tmp_path, changelog="# Changelog\n\n## v1.4.0\n\nHand.\n")
        release_readiness.check_releasability(project, release="1.4.0")
        assert len(_digest_warnings(capsys.readouterr().err, "is already a section for v1.4.0")) == 1

    def test_no_release_is_a_note_that_the_check_did_not_run(self, tmp_path, capsys):
        project = _declared_project(tmp_path, changelog="# Changelog\n\n## v1.4.0\n\nHand.\n")
        release_readiness.check_releasability(project)
        err = capsys.readouterr().err
        assert _digest_warnings(err, "is already a section") == []
        # Bound to the digest's own note: without `plugin/VERSION` there is no
        # fallback NOTE here, but the sibling test below has one, and both say
        # "no --release given".
        [note] = [n for n in _notes(err) if "release-in-changelog" in n]
        assert "no --release given" in note
        _assert_names_the_declared_path(note)

    def test_the_VERSION_fallback_is_never_taken_as_the_release(self, tmp_path, capsys):
        """`plugin/VERSION` names a `-dev` marker guessed low, not a release.

        The fixture makes the fallback name exactly the version a section is
        written for, so a check that took it would warn here.
        """
        project = _declared_project(
            tmp_path, plugin_version=True, changelog="# Changelog\n\n## v1.4.0\n\nHand.\n"
        )
        release_readiness.check_releasability(project)
        err = capsys.readouterr().err
        assert "falling back to plugin/VERSION (v1.4.0)" in err, "the fixture must reach the fallback"
        assert _digest_warnings(err, "is already a section") == []
        [note] = [n for n in _notes(err) if "release-in-changelog" in n]
        assert "no --release given" in note, "the fallback's own NOTE must not stand in for this one"

    def test_a_missing_changelog_warns_naming_the_refusal(self, tmp_path, capsys):
        """A condition the cut refuses on is a warning, like every other one."""
        project = _declared_project(tmp_path, changelog=None)
        assert release_readiness.check_releasability(project, release="v1.4.0") == 0
        [warning] = _digest_warnings(capsys.readouterr().err, "is not a file")
        assert "`digest-missing`" in warning
        _assert_names_the_declared_path(warning)

    def test_an_unreadable_changelog_warns_rather_than_crashing(self, tmp_path, capsys):
        project = _declared_project(tmp_path)
        (project / "CHANGELOG.md").write_bytes(b"# Changelog\n\n## v1.4.0\n\n\xff\xfe\n")
        assert release_readiness.check_releasability(project, release="v1.4.0") == 0
        [warning] = _digest_warnings(capsys.readouterr().err, "cannot be read")
        assert "`digest-unreadable`" in warning
        _assert_names_the_declared_path(warning)


class TestTheDeclarationGatesTheChecks:
    """Opt-in: undeclared is silence, and invalid is never read as undeclared."""

    _BROKEN = {"headline": None, "changelog": "# Changelog\n\n## v1.4.0\n\nHand.\n"}

    def test_an_undeclared_repo_prints_nothing_new(self, tmp_path, capsys):
        """The control is the same fixture declared: it prints the digest lines."""
        declared = _declared_project(tmp_path / "declared", **self._BROKEN)
        release_readiness.check_releasability(declared, release="v1.4.0")
        declared_out = capsys.readouterr()
        assert "digest headline:" in declared_out.out
        assert _digest_warnings(declared_out.err, "release-headline.md")

        undeclared = _declared_project(tmp_path / "undeclared", declaration=None, **self._BROKEN)
        assert release_readiness.check_releasability(undeclared, release="v1.4.0") == 0
        out = capsys.readouterr()
        assert "releasable:" in out.out, "the run must reach the verdict"
        for text in (out.out, out.err):
            assert "digest" not in text
            assert "release-headline" not in text
            assert "CHANGELOG" not in text

    def test_a_state_file_with_other_keys_is_undeclared(self, tmp_path, capsys):
        project = _declared_project(
            tmp_path, declaration="product_identity:\n  name: demo\n", **self._BROKEN
        )
        assert release_readiness.check_releasability(project, release="v1.4.0") == 0
        out = capsys.readouterr()
        assert "releasable:" in out.out
        assert "digest" not in out.out + out.err

    def test_an_invalid_declaration_warns_and_checks_nothing(self, tmp_path, capsys):
        project = _declared_project(
            tmp_path,
            declaration="consumer_digest:\n  path: CHANGELOG.md\n  headline: required\n  layout: sideways\n",
            **self._BROKEN,
        )
        assert release_readiness.check_releasability(project, release="v1.4.0") == 0
        out = capsys.readouterr()
        [warning] = _digest_warnings(out.err, "consumer_digest:")
        assert "layout: 'sideways'" in warning
        assert warning.endswith("; the consumer digest checks did not run")
        assert _digest_warnings(out.err, "release-headline.md") == []
        assert _digest_warnings(out.err, "is already a section") == []
        assert "digest headline:" not in out.out


class TestTheDigestAdvisoryNeverMovesTheVerdict:
    """Advice fails soft: every digest condition at once, and the exit code holds.

    Each pair runs the same release with a healthy digest and with the
    warnings firing; comparing the two exit codes is the claim itself.
    """

    _NOISY = {"headline": None, "changelog": "# Changelog\n\n## v1.4.0\n\nHand.\n"}

    def test_a_passing_verdict_stays_passing(self, tmp_path, capsys):
        clean = _declared_project(tmp_path / "clean")
        assert release_readiness.check_releasability(clean, release="v1.4.0") == 0
        clean_out = capsys.readouterr()
        assert "releasable: v1.4.0" in clean_out.out
        assert _digest_warnings(clean_out.err, "release-headline.md") == []

        noisy = _declared_project(tmp_path / "noisy", **self._NOISY)
        assert release_readiness.check_releasability(noisy, release="v1.4.0") == 0
        out = capsys.readouterr()
        assert _digest_warnings(out.err, "release-headline.md"), "the fixture must fire"
        assert _digest_warnings(out.err, "is already a section"), "the fixture must fire"
        assert "releasable: v1.4.0" in out.out

    def test_an_invalid_declaration_leaves_a_pass_a_pass(self, tmp_path, capsys):
        project = _declared_project(tmp_path, declaration="consumer_digest:\n  path: ../out.md\n")
        assert release_readiness.check_releasability(project, release="v1.4.0") == 0
        out = capsys.readouterr()
        assert _digest_warnings(out.err, "the consumer digest checks did not run")
        assert "releasable: v1.4.0" in out.out

    def test_a_failing_verdict_stays_failing(self, tmp_path, capsys):
        two = {"entries": _entry("A", "alpha") + _entry("B", "beta")}
        clean = _declared_project(tmp_path / "clean", **two)
        assert release_readiness.check_releasability(clean, release="v1.4.0") == 1
        assert "unclassified scope(s)" in capsys.readouterr().err

        noisy = _declared_project(tmp_path / "noisy", **two, **self._NOISY)
        assert release_readiness.check_releasability(noisy, release="v1.4.0") == 1
        err = capsys.readouterr().err
        assert _digest_warnings(err, "release-headline.md"), "the fixture must fire"
        assert "unclassified scope(s)" in err, "the refusal is the pre-existing one"


class TestPrawductDeclaresItsOwnDigest:
    """Prawduct's changelog is one declared value, read through the one reader."""

    def test_this_repos_declaration_is_valid_and_names_its_changelog(self):
        decl, invalid = consumer_digest.read_declaration(ROOT.parent)
        assert invalid is None, invalid
        assert decl is not None, "prawduct must declare its own consumer digest"
        assert decl.path == "plugin/CHANGELOG.md"
        assert decl == _PRAWDUCT_DECLARATION

    def test_the_banner_shows_the_headline_the_operator_wrote(self, tmp_path):
        """What the operator writes in the headline file is what consumers see.

        The section is rendered by the cut's own renderer from prawduct's
        declaration and parsed by the real banner. The heading-first headline is
        the control: the banner shows nothing for it, and that is exactly the
        case Phase 0 warns about.
        """
        spec = importlib.util.spec_from_file_location("prawduct_banner", ROOT / "hooks" / "banner.py")
        banner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(banner)
        fragment = change_fragments.parse_fragment(
            "---\nschema: 1\ntype: fix\nscope: alpha\ndate: 2026-10-19\ntitle: alpha title\n---\n"
            "What changed.\n\n## Consumer note\nAlpha now does the thing.\n",
            filename="alpha.md",
        )

        for headline, shown in (
            ("Release notes now reach the changelog.\nA second line.", "Release notes now reach the changelog."),
            ("# Big news\n\nThe sentence under it.", ""),
        ):
            root = tmp_path / f"root{len(headline)}"
            section = consumer_digest.render_section(
                _PRAWDUCT_DECLARATION, "v9.9.9", "2026-10-25", headline, [fragment]
            )
            _write(root / "CHANGELOG.md", "# Changelog\n\n" + "\n".join(section) + "\n\n## v9.9.8\n\nOld.\n")
            assert dict(banner.parse_changelog(root)).get("9.9.9") == shown, (
                f"the banner shows something other than the headline file's first line for {headline!r}"
            )
            _write(root / ".prawduct" / "release-headline.md", headline + "\n")
            _write(root / ".prawduct" / "project-state.yaml", _PRODUCT_DECLARATION)
            # No release, so the section check (which would find the section
            # just written) stays out of it: what is left judges the headline.
            warnings, _note, _emissions = release_readiness._digest_advisories(root, None)
            assert bool(warnings) == (shown == ""), (
                f"Phase 0 and the banner disagree about {headline!r}"
            )

    def test_the_deleted_section_machinery_stays_deleted(self):
        """CD13: the coverage check and the open-section reader have no subject.

        Scanned across every lib module and the hook, not only this one: a
        copy of the old reader or a second path constant reappearing anywhere
        is the two-homes shape #733 removed (the cut kept one until it moved
        onto `consumer_digest`).
        """
        sources = {p: p.read_text(encoding="utf-8") for p in sorted((ROOT / "lib").glob("*.py"))}
        sources[ROOT / "bin" / "prawduct-hook"] = (ROOT / "bin" / "prawduct-hook").read_text(encoding="utf-8")
        assert len(sources) > 20, "the control: the scan reads the real tree"
        for name in (
            "_DIGEST_REL_PATH", "_DIGEST_SECTION_RE", "_read_digest", "_open_digest_section",
            "_section_headline", "_headline_advisory", "_coverage_advisory", "_digest_mentions",
            "_SEEDED_HEADLINE", "legacy_pending",
            "_names_release", "_digest_write", "render_consumer_section",
        ):
            hits = [p.name for p, text in sources.items() if re.search(rf"\b{name}\b", text)]
            assert not hits, f"{name} is back in {hits}"
        assert "_digest_advisories" in sources[ROOT / "lib" / "release_readiness.py"], (
            "the control: the scan reads the real module"
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
            **kwargs,
        )

    def test_a_green_run_passes_and_names_the_evidence(self, tmp_path, capsys):
        project = self._project(tmp_path)
        assert release_readiness.check_releasability(project) == 0
        out = capsys.readouterr().out
        assert "suite: green" in out, "the passing run must emit its own yield"
        assert "releasable:" in out

    def test_the_verdict_forwards_the_reason_and_nothing_about_the_clause(self, tmp_path):
        """`_suite_verdict` drops the reader's clause element; its own shape holds.

        `gates.tests_are_current` names which of its two disjuncts answered, so
        a surface can avoid implying tree coverage it does not have. This gate
        makes no such claim — its docstring states session-freshness as the
        correct bound at this phase — so it drops that element rather than
        forwarding it, and its one caller keeps destructuring a pair. A
        three-element return reaching that caller is a ValueError at release
        time, which is the worst moment to find one.
        """
        project = self._project(tmp_path)
        verdict = release_readiness._suite_verdict(project)
        assert len(verdict) == 2, "the caller destructures a pair"
        is_current, reason = verdict
        assert is_current is True
        assert reason and "clause" not in reason, \
            "the reason is the reader's prose, carried through verbatim"

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
        and that the release has no headline. A bare early return would buy one
        problem per round trip.
        """
        project = _declared_project(
            tmp_path,
            entries=_entry("A", "alpha") + _entry("B", "beta"),
            headline=None,
            evidence=None,
        )
        assert release_readiness.check_releasability(project, release="v1.4.0") == 1
        out = capsys.readouterr()
        err = out.err
        assert "unproven-suite:" in err
        assert "unclassified scope(s)" in err, "the classification check must still have run"
        assert _digest_warnings(err, "release-headline.md"), "the digest check must still have run"
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
            evidence=None,
        )
        assert release_readiness.check_releasability(project) == 0
        out = capsys.readouterr()
        assert "no release-pending scopes" in out.out
        assert "unproven-suite" not in out.err

    def test_no_path_returns_0_while_the_suite_is_red(self, tmp_path, capsys):
        """The property the report-here/return-there split rests on.

        Everything else about this fixture passes — the scope is classified and
        the release plan exists — so the ONLY thing between the verdict and a 0
        is the return at the bottom. That is what makes this a
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
        suite: at v2.1.6 a version with no digest section was precisely what
        `test_changelog_has_current_version_entry` failed on, so the missing
        headline WAS the red suite — and the release path read no test result,
        so it shipped anyway. The fixture states that redness rather than
        deriving it.
        """
        project = _declared_project(tmp_path, headline=None, evidence=_evidence(failed=1))
        assert release_readiness.check_releasability(project, release="v1.4.0") == 1
        err = capsys.readouterr().err
        assert _digest_warnings(err, "release-headline.md is absent"), (
            "the operator must be told what to write"
        )
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


def _fragment(scope: str, *, note: str = "A consumer-facing note.", date: str = "2026-10-19") -> str:
    """A valid change fragment for ``scope`` (the format `lib/change_fragments.py` owns)."""
    return (
        f"---\nschema: 1\ntype: fix\nscope: {scope}\ndate: {date}\ntitle: {scope} title\n---\n"
        f"What changed.\n\n## Consumer note\n{note}\n"
    )


def _add_fragment(project: Path, scope: str, text: str | None = None) -> None:
    _write(project / ".prawduct" / "changes" / f"{scope}.md", text or _fragment(scope))


class TestFragmentsJoinThePendingSet:
    """The fragments are the pending set (#1125). Each test here pins one way a
    fragment, or the record beside it, changes the verdict."""

    def test_an_unclassified_fragment_scope_is_refused_by_name(self, tmp_path, capsys):
        project = _make_project(tmp_path, entries=_entry("A", "alpha"), classification="| alpha | ships | |\n")
        _add_fragment(project, "beta")
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        assert "unclassified scope(s)" in err and "beta" in err

    def test_an_invalid_fragment_refuses_before_any_verdict(self, tmp_path, capsys):
        project = _make_project(tmp_path, entries="", classification="| alpha | ships | |\n")
        _add_fragment(project, "alpha", _fragment("alpha").replace("type: fix", "type: bugfix"))
        assert release_readiness.check_releasability(project) == 1
        captured = capsys.readouterr()
        assert "bad-change-fragment: alpha.md: bad-type" in captured.err
        assert "releasable" not in captured.out

    def test_a_scope_pending_as_a_fragment_and_a_legacy_entry_refuses_the_entry(self, tmp_path, capsys):
        """Was `scope-in-both-shapes`. The fragment is the record; the legacy
        entry is a pending entry no release reads, refused like any other."""
        project = _legacy_log_project(
            tmp_path, _dated_entry("alpha again", "alpha"), fragments=("alpha",),
            classification="| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        assert "legacy-pending-entry: '2026-10-18: alpha again'" in err
        assert "scope-in-both-shapes" not in err

    def test_a_fragments_only_repo_needs_no_single_file_log(self, tmp_path, capsys):
        project = _make_project(tmp_path, entries="", classification="| alpha | ships | |\n")
        (project / ".prawduct" / "change-log.md").unlink()
        _add_fragment(project, "alpha")
        assert release_readiness.check_releasability(project) == 0
        assert "1 change fragment(s)" in capsys.readouterr().out

    def test_no_log_and_no_fragment_directory_is_still_a_missing_input(self, tmp_path, capsys):
        project = _make_project(tmp_path, entries="", classification=None)
        (project / ".prawduct" / "change-log.md").unlink()
        (project / ".prawduct" / "changes").rmdir()
        assert release_readiness.check_releasability(project) == 1
        assert "no-change-log:" in capsys.readouterr().err


class TestPendingScopesIsTheOneOwner:
    """`pending_scopes` is what every reader of the pending set calls (#1012 D6)."""

    def test_the_scopes_are_the_fragments_and_nothing_else(self, tmp_path):
        project = _make_project(
            tmp_path, entries=_entry("A", "alpha") + _entry("B", "beta", release="v3.1.0"), classification=None
        )
        _add_fragment(project, "gamma")
        pending = release_readiness.pending_scopes(project)
        assert pending.fragment_scopes == ["alpha", "gamma"]
        assert pending.scopes == ["alpha", "gamma"]
        assert pending.refusals == [] and pending.read_error is None

    def test_both_kinds_of_untrustworthy_set_are_refusals(self, tmp_path):
        project = _legacy_log_project(tmp_path, _dated_entry("old", "alpha"))
        _add_fragment(project, "beta", _fragment("beta").replace("schema: 1", "schema: 9"))
        refusals = release_readiness.pending_scopes(project).refusals
        assert any(r.startswith("bad-change-fragment: beta.md: schema-ahead") for r in refusals)
        assert any(r.startswith("legacy-pending-entry: '2026-10-18: old'") for r in refusals)

    def test_an_unreadable_log_is_a_read_error_even_beside_fragments(self, tmp_path):
        project = _make_project(tmp_path, entries="", classification=None)
        (project / ".prawduct" / "change-log.md").write_bytes(b"\xff\xfe not utf-8")
        _add_fragment(project, "alpha")
        assert release_readiness.pending_scopes(project).read_error is not None


def _dated_entry(title: str, scope: str, *, release: str | None = None) -> str:
    """A legacy entry in the shape `migrate-change-log` converts (dated header)."""
    tag = f"<!-- prawduct: type=fix | scope={scope}"
    if release:
        tag += f" | release={release}"
    tag += " -->"
    return f"## 2026-10-18: {title}\n\n{tag}\n\nBody.\n\n"


def _legacy_log_project(tmp_path: Path, log_entries: str, *, fragments=(), classification=None) -> Path:
    """A project whose live log holds ``log_entries`` verbatim, beside ``fragments``."""
    project = _make_project(tmp_path, entries="", classification=classification)
    _write(project / ".prawduct" / "change-log.md", "# Change Log\n\n" + log_entries)
    for scope in fragments:
        _add_fragment(project, scope)
    return project


class TestALegacyPendingEntryIsRefused:
    """A repo with a release-pending legacy entry gets a refusal naming
    `/prawduct:doctor`, and the entry is never counted, never dropped."""

    def test_a_pending_legacy_entry_beside_a_fragment_refuses_naming_it_and_doctor(self, tmp_path, capsys):
        project = _legacy_log_project(
            tmp_path,
            _dated_entry("old way", "oldway"),
            fragments=("alpha",),
            classification="| alpha | ships | |\n| oldway | ships | |\n",
        )
        assert release_readiness.check_releasability(project, "v3.2.0") == 1
        captured = capsys.readouterr()
        line = next(x for x in captured.err.splitlines() if x.startswith("legacy-pending-entry:"))
        assert "'2026-10-18: old way'" in line and "line 3" in line
        assert "/prawduct:doctor" in line and "migrate-change-log" in line
        # Refused before any verdict: no scope list, no pass.
        assert "releasable" not in captured.out
        assert "scanned:" not in captured.out

    def test_a_pending_legacy_entry_alone_is_not_nothing_to_cut(self, tmp_path, capsys):
        """The silent-drop direction: with fragments read only, a legacy-only
        pending set would otherwise read as empty and pass."""
        project = _legacy_log_project(tmp_path, _dated_entry("old way", "oldway"))
        assert release_readiness.check_releasability(project) == 1
        captured = capsys.readouterr()
        assert "nothing to classify" not in captured.out
        assert "legacy-pending-entry:" in captured.err

    def test_a_scopeless_pending_entry_is_refused_the_same_way(self, tmp_path, capsys):
        project = _legacy_log_project(tmp_path, _scopeless_entry("An unscoped change"))
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        assert "legacy-pending-entry: 'An unscoped change'" in err

    def test_every_pending_entry_is_named_not_just_the_first(self, tmp_path, capsys):
        project = _legacy_log_project(
            tmp_path,
            _dated_entry("first", "one") + _dated_entry("shipped", "two", release="v3.1.0")
            + _dated_entry("third", "three"),
        )
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        assert "'2026-10-18: first'" in err and "'2026-10-18: third'" in err
        assert "'2026-10-18: shipped'" not in err

    @pytest.mark.parametrize("placeholder", ["release=unreleased", "release=v1.2.3.4.5"])
    def test_a_placeholder_release_tag_is_refused_not_read_as_shipped(self, tmp_path, capsys, placeholder):
        """The v3.2.8 shape: a `release=` that is not a version hides pending work.
        It is refused under the same code, with the migration's own reason."""
        entry = _dated_entry("hidden", "hidden").replace("scope=hidden", f"scope=hidden | {placeholder}")
        project = _legacy_log_project(tmp_path, entry)
        assert release_readiness.check_releasability(project) == 1
        captured = capsys.readouterr()
        assert "nothing to classify" not in captured.out
        line = next(x for x in captured.err.splitlines() if x.startswith("legacy-pending-entry:"))
        assert "unreleased-placeholder" in line and "/prawduct:doctor" in line

    def test_shipped_and_untagged_history_is_no_refusal(self, tmp_path, capsys):
        project = _legacy_log_project(
            tmp_path,
            "## Historical entry\n\nNo tag line at all.\n\n"
            + _dated_entry("shipped", "two", release="v3.1.0")
            + _scopeless_entry("Ancient history", release="v1.0.0"),
            fragments=("alpha",),
            classification="| alpha | ships | |\n",
        )
        assert release_readiness.check_releasability(project) == 0, capsys.readouterr().err

    def test_pending_scopes_carries_no_legacy_scopes(self, tmp_path):
        project = _legacy_log_project(tmp_path, _dated_entry("old way", "oldway"), fragments=("alpha",))
        pending = release_readiness.pending_scopes(project)
        assert pending.scopes == ["alpha"]
        assert not hasattr(pending, "legacy_scopes")
        assert [r.split(":", 1)[0] for r in pending.refusals] == ["legacy-pending-entry"]


class TestAFragmentsOnlyRepoReleasesAsToday:
    def test_shipping_and_withholding_fragments_pass(self, tmp_path, capsys):
        project = _make_project(
            tmp_path, entries="", classification="| alpha | ships | |\n| beta | withheld | BKL-6J2X |\n",
            backlog=_open_item("BKL-6J2X"),
        )
        (project / ".prawduct" / "change-log.md").unlink()
        _add_fragment(project, "alpha")
        _add_fragment(project, "beta")
        assert release_readiness.check_releasability(project) == 0
        out = capsys.readouterr().out
        assert "releasable: v3.2.0 — 2 release-pending scope(s), 1 shipping, 1 withheld" in out
        assert "scanned: 2 change fragment(s)" in out


# ---------------------------------------------------------------------------
# #1024: a collateral scope is declared, withheld behind its parent's blocker,
# and refused if classified `ships`.
# ---------------------------------------------------------------------------


def _collateral_project(tmp_path: Path, classification: str, *, backlog: str | None = None) -> Path:
    project = _make_project(
        tmp_path, entries="", classification=classification,
        backlog=_open_item("BKL-6J2X") if backlog is None else backlog,
    )
    _add_fragment(project, "big-feature")
    _add_fragment(project, "small-fix")
    return project


class TestCollateralIsDeclared:
    def test_shipping_a_declared_collateral_scope_is_refused_naming_both_and_the_remedy(self, tmp_path, capsys):
        project = _collateral_project(
            tmp_path,
            "| big-feature | withheld | BKL-6J2X |\n| small-fix | ships | collateral-of big-feature |\n",
        )
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        line = next(x for x in err.splitlines() if "collateral-of" in x)
        assert "small-fix" in line and "big-feature" in line
        assert "withheld | collateral-of big-feature" in line

    def test_a_withheld_collateral_row_passes_behind_its_parents_blocker(self, tmp_path, capsys):
        project = _collateral_project(
            tmp_path,
            "| big-feature | withheld | BKL-6J2X |\n| small-fix | withheld | collateral-of big-feature |\n",
        )
        assert release_readiness.check_releasability(project) == 0, capsys.readouterr().err
        out = capsys.readouterr().out
        assert "2 release-pending scope(s), 0 shipping, 2 withheld" in out
        assert "small-fix (collateral of big-feature, blocked by BKL-6J2X)" in out

    def test_the_row_order_does_not_matter(self, tmp_path):
        project = _collateral_project(
            tmp_path,
            "| small-fix | withheld | collateral-of big-feature |\n| big-feature | withheld | BKL-6J2X |\n",
        )
        assert release_readiness.check_releasability(project) == 0

    def test_the_tuple_shape_is_unchanged_and_the_map_is_exposed(self):
        content = (
            "## Release classification\n\n| Scope | Disposition | Blocker |\n|---|---|---|\n"
            "| big-feature | withheld | BKL-6J2X |\n| small-fix | withheld | collateral-of big-feature |\n"
        )
        classification, errors = release_readiness.parse_classification(content)
        assert errors == []
        assert classification["small-fix"] == (release_readiness.WITHHELD, "BKL-6J2X")
        assert release_readiness.parse_collateral(content) == {"small-fix": "big-feature"}

    @pytest.mark.parametrize(
        "rows,phrase",
        [
            ("| small-fix | withheld | collateral-of big-feature |\n", "not in the table"),
            (
                "| big-feature | ships | |\n| small-fix | withheld | collateral-of big-feature |\n",
                "is not `withheld`",
            ),
            (
                "| big-feature | withheld | BKL-6J2X |\n| mid | withheld | collateral-of big-feature |\n"
                "| small-fix | withheld | collateral-of mid |\n",
                "itself collateral",
            ),
        ],
        ids=["missing-parent", "parent-not-withheld", "collateral-of-collateral"],
    )
    def test_each_bad_declaration_is_its_own_error_naming_both_scopes(self, rows, phrase):
        content = "## Release classification\n\n| Scope | Disposition | Blocker |\n|---|---|---|\n" + rows
        _classification, errors = release_readiness.parse_classification(content)
        matching = [e for e in errors if phrase in e]
        assert len(matching) == 1, errors
        assert "small-fix" in matching[0]
        assert ("big-feature" in matching[0]) or ("mid" in matching[0])

    def test_a_closed_parent_blocker_is_stale_for_the_collateral_scope_too(self, tmp_path, capsys):
        project = _collateral_project(
            tmp_path,
            "| big-feature | withheld | BKL-6J2X |\n| small-fix | withheld | collateral-of big-feature |\n",
            backlog=_shipped_item("BKL-6J2X"),
        )
        assert release_readiness.check_releasability(project) == 1
        err = capsys.readouterr().err
        stale = next(x for x in err.splitlines() if "no longer open" in x)
        assert "small-fix (withheld as collateral of big-feature, behind BKL-6J2X" in stale
        assert "big-feature (withheld behind BKL-6J2X" in stale
