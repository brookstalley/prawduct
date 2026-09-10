"""Tests for `lib/change_log_archive.py` and the `archive-change-log` subcommand.

The change-log's end of life. The properties under test are the ones the
lifecycle rests on: **only shipped entries move**, nothing is deleted, the
release-pending set is identical across a run, and the command refuses rather
than reports when it would not be.

The last one carries the most weight. Every other failure here is visible — a
missing entry, a bad exit code — while an entry that leaves the release-pending
set leaves no trace at all: `check-releasability` simply enumerates a smaller
set and calls it clean. That is the shape this whole module exists to prevent,
so it is asserted against a doctored log rather than trusted to the selection
rule that is supposed to make it impossible.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib import change_log, change_log_archive  # noqa: E402
from lib.release_readiness import release_pending_entries  # noqa: E402

_HOOK_PATH = _REPO_ROOT / "bin" / "prawduct-hook"

HEADER = (
    "# Change Log — Demo\n"
    "\n"
    "<!-- Append new entries at the top. -->\n"
    "\n"
)


def _entry(title: str, tag: str | None, body: str = "Some prose.\n") -> str:
    out = f"## {title}\n\n"
    if tag is not None:
        out += f"<!-- prawduct: {tag} -->\n\n"
    return out + body + "\n"


def _log(*entries: str) -> str:
    return HEADER + "".join(entries)


def _project(tmp_path: Path, content: str, version: str = "3.4.1-dev.2") -> Path:
    (tmp_path / ".prawduct").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".prawduct" / "change-log.md").write_text(content, encoding="utf-8")
    (tmp_path / "plugin").mkdir(parents=True, exist_ok=True)
    (tmp_path / "plugin" / "VERSION").write_text(version + "\n", encoding="utf-8")
    return tmp_path


def _run_hook(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_HOOK_PATH), "archive-change-log", *args],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=60,
    )


def _live(project: Path) -> str:
    return (project / ".prawduct" / "change-log.md").read_text(encoding="utf-8")


def _history(project: Path) -> str:
    return (project / ".prawduct" / "change-log-history.md").read_text(encoding="utf-8")


# =============================================================================
# Selection — what may leave, and the three ways to stay
# =============================================================================


class TestSelection:
    """Only a parseable `release=` below the kept line is eligible."""

    def test_the_boundary_is_the_kept_line_itself(self):
        pairs = change_log_archive.split_entries(
            _log(
                _entry("2026-01-01: old", "scope=a | release=v3.3.4"),
                _entry("2026-02-01: current", "scope=b | release=v3.4.0"),
            )
        )[1]
        moving, staying = change_log_archive.select_for_archive(
            pairs, change_log_archive.MinorLine(3, 4)
        )
        assert [e.title for e, _t in moving] == ["2026-01-01: old"]
        assert [e.title for e, _t in staying] == ["2026-02-01: current"]

    def test_a_patch_release_on_the_kept_line_stays(self):
        """Retention is per LINE — `v3.4.7` is the kept line, not above it."""
        pairs = change_log_archive.split_entries(
            _log(_entry("2026-02-01: patch", "scope=b | release=v3.4.7"))
        )[1]
        moving, staying = change_log_archive.select_for_archive(
            pairs, change_log_archive.MinorLine(3, 4)
        )
        assert not moving and len(staying) == 1

    @pytest.mark.parametrize(
        "tag",
        [
            None,  # pre-convention history: no tag line at all
            "scope=b",  # tagged, no release= — THE release-pending marker
            "scope=b | release=unreleased",  # a placeholder, not a version
            "scope=b | release=",  # empty
            "scope=b | release=v3",  # not a version this module will parse
        ],
    )
    def test_everything_that_is_not_a_shipped_version_stays(self, tag):
        """Refused, never guessed. Each of these moving is work unshipped."""
        pairs = change_log_archive.split_entries(
            _log(_entry("2026-01-01: keep me", tag))
        )[1]
        moving, _staying = change_log_archive.select_for_archive(
            pairs, change_log_archive.MinorLine(3, 4)
        )
        assert not moving

    def test_a_prerelease_suffix_on_a_real_version_still_reads(self):
        pairs = change_log_archive.split_entries(
            _log(_entry("2026-01-01: rc", "scope=a | release=v3.2.0-rc.1"))
        )[1]
        moving, _staying = change_log_archive.select_for_archive(
            pairs, change_log_archive.MinorLine(3, 4)
        )
        assert len(moving) == 1


# =============================================================================
# The invariant — the refusal, asserted against a log that would break it
# =============================================================================


class TestPendingSetIsPreserved:
    def test_a_run_that_would_drop_a_pending_entry_is_refused(
        self, tmp_path: Path, monkeypatch
    ):
        """The guard, exercised by breaking the rule it guards.

        `select_for_archive` is what makes this impossible, so the test forces
        the failure past it: a selection that also takes a release-pending entry
        is exactly the silent unship, and the command must write NOTHING rather
        than report a smaller clean number.
        """
        content = _log(
            _entry("2026-01-01: shipped", "scope=a | release=v3.3.4"),
            _entry("2026-02-01: pending", "scope=b"),
        )

        def _greedy(pairs, keep_from):
            return list(pairs), []

        monkeypatch.setattr(change_log_archive, "select_for_archive", _greedy)
        result = change_log_archive.archive_or_refuse(
            content, None, change_log_archive.MinorLine(3, 4)
        )

        assert result.refused_titles == ["2026-02-01: pending"]

    def test_a_clean_run_refuses_nothing(self, tmp_path: Path):
        content = _log(
            _entry("2026-01-01: shipped", "scope=a | release=v3.3.4"),
            _entry("2026-02-01: pending", "scope=b"),
        )
        result = change_log_archive.archive_or_refuse(
            content, None, change_log_archive.MinorLine(3, 4)
        )
        assert result.refused_titles == []
        assert len(result.moved) == 1

    def test_the_real_selection_preserves_the_fingerprint(self):
        content = _log(
            _entry("2026-01-01: shipped", "scope=a | release=v3.3.4"),
            _entry("2026-02-01: pending", "scope=b"),
            _entry("2026-02-02: untagged", None),
        )
        new_live, _h, moved = change_log_archive.compose(
            content, None, change_log_archive.MinorLine(3, 4)
        )
        assert len(moved) == 1
        assert change_log_archive.pending_fingerprint(
            content
        ) == change_log_archive.pending_fingerprint(new_live)

    def test_the_pending_entry_is_still_pending_afterwards(self):
        """Not just 'the fingerprint matched' — the gate's own reader agrees."""
        content = _log(
            _entry("2026-01-01: shipped", "scope=a | release=v3.3.4"),
            _entry("2026-02-01: pending", "scope=b"),
        )
        new_live, _h, _m = change_log_archive.compose(
            content, None, change_log_archive.MinorLine(3, 4)
        )
        titles = [
            e.title
            for e in release_pending_entries(change_log.parse_change_log(new_live))
        ]
        assert titles == ["2026-02-01: pending"]


# =============================================================================
# Nothing is deleted — the two files together are the original
# =============================================================================


class TestNothingIsLost:
    def test_every_entry_survives_the_move(self):
        content = _log(
            _entry("2026-01-01: a", "scope=a | release=v3.2.0"),
            _entry("2026-01-02: b", "scope=b | release=v3.3.0"),
            _entry("2026-02-01: c", "scope=c"),
        )
        new_live, new_history, _m = change_log_archive.compose(
            content, None, change_log_archive.MinorLine(3, 4)
        )
        titles = {e.title for e in change_log.parse_change_log(content)}
        after = {e.title for e in change_log.parse_change_log(new_live)} | {
            e.title for e in change_log.parse_change_log(new_history)
        }
        assert after == titles

    def test_a_moved_entry_keeps_its_tag_line(self):
        """History is a redirect: an entry arrives whole, tag included."""
        content = _log(_entry("2026-01-01: a", "scope=a | release=v3.2.0"))
        _live_after, new_history, _m = change_log_archive.compose(
            content, None, change_log_archive.MinorLine(3, 4)
        )
        moved = change_log.parse_change_log(new_history)
        assert moved[0].tags["release"] == "v3.2.0"
        assert moved[0].tags["scope"] == "a"

    def test_a_second_run_appends_rather_than_replacing(self):
        first = _log(_entry("2026-01-01: a", "scope=a | release=v3.2.0"))
        _l1, history, _m = change_log_archive.compose(
            first, None, change_log_archive.MinorLine(3, 4)
        )
        second = _log(_entry("2026-01-02: b", "scope=b | release=v3.3.0"))
        _l2, history2, _m2 = change_log_archive.compose(
            second, history, change_log_archive.MinorLine(3, 4)
        )
        assert [e.title for e in change_log.parse_change_log(history2)] == [
            "2026-01-02: b",
            "2026-01-01: a",
        ]

    def test_the_live_header_is_not_carried_into_history(self):
        content = _log(_entry("2026-01-01: a", "scope=a | release=v3.2.0"))
        new_live, new_history, _m = change_log_archive.compose(
            content, None, change_log_archive.MinorLine(3, 4)
        )
        assert new_live.startswith("# Change Log — Demo")
        assert "Change Log — History" in new_history
        assert "# Change Log — Demo" not in new_history


# =============================================================================
# The command — dry run by default, and idempotent
# =============================================================================


class TestCommand:
    def test_without_apply_nothing_is_written(self, tmp_path: Path):
        content = _log(_entry("2026-01-01: a", "scope=a | release=v3.2.0"))
        project = _project(tmp_path, content)
        result = _run_hook(project)
        assert result.returncode == 0, result.stderr
        assert "would archive" in result.stdout
        assert _live(project) == content
        assert not (project / ".prawduct" / "change-log-history.md").exists()

    def test_apply_writes_both_files(self, tmp_path: Path):
        content = _log(
            _entry("2026-01-01: a", "scope=a | release=v3.2.0"),
            _entry("2026-02-01: b", "scope=b"),
        )
        project = _project(tmp_path, content)
        result = _run_hook(project, "--apply")
        assert result.returncode == 0, result.stderr
        assert "2026-01-01: a" not in _live(project)
        assert "2026-02-01: b" in _live(project)
        assert "2026-01-01: a" in _history(project)

    def test_a_second_apply_moves_nothing(self, tmp_path: Path):
        content = _log(
            _entry("2026-01-01: a", "scope=a | release=v3.2.0"),
            _entry("2026-02-01: b", "scope=b"),
        )
        project = _project(tmp_path, content)
        _run_hook(project, "--apply")
        live_after_first = _live(project)
        history_after_first = _history(project)

        result = _run_hook(project, "--apply")

        assert result.returncode == 0, result.stderr
        assert "nothing to archive" in result.stdout
        assert _live(project) == live_after_first
        assert _history(project) == history_after_first

    def test_the_kept_line_comes_from_the_version_file(self, tmp_path: Path):
        """Never hardcoded — a repo on v2.1 keeps v2.1.x, not v3.4.x."""
        content = _log(
            _entry("2026-01-01: a", "scope=a | release=v2.0.9"),
            _entry("2026-02-01: b", "scope=b | release=v2.1.3"),
        )
        project = _project(tmp_path, content, version="2.1.3")
        result = _run_hook(project, "--apply")
        assert result.returncode == 0, result.stderr
        assert "2026-01-01: a" in _history(project)
        assert "2026-02-01: b" in _live(project)

    def test_an_unreadable_version_refuses_rather_than_guessing(self, tmp_path: Path):
        content = _log(_entry("2026-01-01: a", "scope=a | release=v3.2.0"))
        project = _project(tmp_path, content)
        (project / "plugin" / "VERSION").unlink()
        result = _run_hook(project, "--apply")
        assert result.returncode == 1
        assert "no-version" in result.stderr
        assert _live(project) == content

    def test_an_unreadable_keep_minor_is_a_usage_error(self, tmp_path: Path):
        project = _project(tmp_path, _log(_entry("2026-01-01: a", "scope=a")))
        result = _run_hook(project, "--keep-minor", "banana", "--apply")
        assert result.returncode == 2
        assert "unreadable --keep-minor" in result.stderr

    def test_an_unknown_flag_is_a_usage_error(self, tmp_path: Path):
        project = _project(tmp_path, _log(_entry("2026-01-01: a", "scope=a")))
        result = _run_hook(project, "--force")
        assert result.returncode == 2
        assert "unknown argument" in result.stderr


# =============================================================================
# The real corpus — the only test that proves this is safe on THIS repo
# =============================================================================


def test_this_repos_own_change_log_archives_without_moving_a_pending_entry():
    """The corpus, not a fixture.

    Every case above is a shape someone thought of. This one is the 387 entries
    that actually exist, and the property it asserts is the one the run must not
    break: the release-pending set the release gate would enumerate is the same
    before and after. A fixture cannot prove that about a file whose tag lines
    were written by hand over six months.
    """
    repo = Path(__file__).resolve().parent.parent
    live = (repo / ".prawduct" / "change-log.md").read_text(encoding="utf-8")
    keep_from = change_log_archive.current_minor_line(repo)
    assert keep_from is not None, "plugin/VERSION did not yield a release line"

    new_live, new_history, moved = change_log_archive.compose(live, None, keep_from)

    assert moved, "no entry was eligible — the corpus moved, or selection broke"
    assert change_log_archive.pending_fingerprint(
        live
    ) == change_log_archive.pending_fingerprint(new_live)

    before = {e.title for e in change_log.parse_change_log(live)}
    after = {e.title for e in change_log.parse_change_log(new_live)} | {
        e.title for e in change_log.parse_change_log(new_history)
    }
    assert after == before, "an entry was neither kept nor archived"

    for entry in change_log.parse_change_log(new_history):
        assert entry.tags.get("release"), (
            f"{entry.title!r} reached history with no release= — only shipped "
            "entries may leave the live log"
        )
