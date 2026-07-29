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


def _open_item(item_id: str) -> str:
    return f"- **[{item_id}]** A blocker\n  `effort: M · impact: L · area: x · status: open`\n\n"


def _shipped_item(item_id: str) -> str:
    return f"- **[{item_id}]** A closed thing\n  `effort: M · impact: L · area: x · status: shipped`\n\n"


class TestReleasePendingScopes:
    def test_release_tagged_entries_are_not_pending(self):
        from lib import views

        content = _entry("A", "alpha") + _entry("B", "beta", release="v3.1.2")
        scopes = release_readiness.release_pending_scopes(views.parse_change_log(content))
        assert scopes == ["alpha"], "a release= tag means the code already shipped"

    def test_untagged_entries_are_invisible(self):
        from lib import views

        content = "## Historical entry\n\nNo tag line at all.\n\n" + _entry("A", "alpha")
        scopes = release_readiness.release_pending_scopes(views.parse_change_log(content))
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
