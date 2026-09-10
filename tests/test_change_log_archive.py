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


def _product(
    tmp_path: Path, content: str, declaration: str, version_files: dict[str, str]
) -> Path:
    """A repo shaped like a governed PRODUCT, not like prawduct.

    `_project` writes `plugin/VERSION`, which is prawduct's own layout — so
    every test using it goes down the fallback and the declaration read, which
    is the thing that makes this command portable, is never exercised.
    """
    (tmp_path / ".prawduct").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".prawduct" / "change-log.md").write_text(content, encoding="utf-8")
    (tmp_path / ".prawduct" / "project-state.yaml").write_text(
        declaration, encoding="utf-8"
    )
    for rel, text in version_files.items():
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return tmp_path


def _run_hook(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_HOOK_PATH), "archive-change-log", *args],
        cwd=str(project),
        capture_output=True,
        text=True,
        timeout=60,
    )


def _load_hook():
    """`prawduct-hook` as a module.

    The script has a shebang and no `.py` extension; SourceFileLoader is how the
    rest of the suite reaches its internals. Needed here because the refusal
    this command prints cannot be provoked across a subprocess boundary — the
    selection rule makes the state unreachable from any input, which is the
    point of the rule and the reason the branch would otherwise ship ungraded.
    """
    import importlib.machinery
    import importlib.util

    loader = importlib.machinery.SourceFileLoader(
        "prawduct_hook_archive", str(_HOOK_PATH)
    )
    spec = importlib.util.spec_from_loader("prawduct_hook_archive", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


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
            # The two that separate this module's reading from the change-log's
            # own. Both moved before the readings were unified; both are values
            # `validate_change_log_tags` calls malformed, and archiving on a
            # laxer reading of a value neither owns is how the two drift apart.
            "scope=b | release=3.2.0",  # no `v` — the validator rejects it
            "scope=b | release=v3.2.0+b",  # build metadata — likewise
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

    def test_a_run_that_would_CREATE_a_diagnostic_is_refused(self, monkeypatch):
        """The other half of the guard, and the half no input can reach.

        Moving whole entries cannot change how the ones left behind parse — so
        if it ever does, the split found a boundary the parser disagrees with,
        and the remaining log is now malformed in a way the next release gate
        discovers instead of this command. Provoked the same way its sibling is,
        because `_compose` is what makes it unreachable.
        """
        content = _log(
            _entry("2026-01-01: shipped", "scope=a | release=v3.3.4"),
            _entry("2026-02-01: pending", "scope=b"),
        )

        real = change_log_archive._compose

        def _corrupting(live, hist, keep):
            new_live, new_history, moved = real(live, hist, keep)
            # A second tag line under the surviving entry: parseable, and a
            # diagnostic the original log did not carry.
            return (
                new_live + "\n<!-- prawduct: scope=b | release=v9.9.9 -->\n",
                new_history,
                moved,
            )

        monkeypatch.setattr(change_log_archive, "_compose", _corrupting)
        result = change_log_archive.archive_or_refuse(
            content, None, change_log_archive.MinorLine(3, 4)
        )

        assert result.refused_titles, "a created diagnostic did not refuse the run"
        assert any("new diagnostic" in r for r in result.refused_titles)

    def test_the_real_selection_preserves_the_fingerprint(self):
        content = _log(
            _entry("2026-01-01: shipped", "scope=a | release=v3.3.4"),
            _entry("2026-02-01: pending", "scope=b"),
            _entry("2026-02-02: untagged", None),
        )
        result = change_log_archive.archive_or_refuse(
            content, None, change_log_archive.MinorLine(3, 4)
        )
        new_live, moved = result.new_live, result.moved
        assert len(moved) == 1
        assert result.refused_titles == []
        assert change_log_archive.pending_fingerprint(
            content
        ) == change_log_archive.pending_fingerprint(new_live)

    def test_the_pending_entry_is_still_pending_afterwards(self):
        """Not just 'the fingerprint matched' — the gate's own reader agrees."""
        content = _log(
            _entry("2026-01-01: shipped", "scope=a | release=v3.3.4"),
            _entry("2026-02-01: pending", "scope=b"),
        )
        new_live = change_log_archive.archive_or_refuse(
            content, None, change_log_archive.MinorLine(3, 4)
        ).new_live
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
        result = change_log_archive.archive_or_refuse(
            content, None, change_log_archive.MinorLine(3, 4)
        )
        new_live, new_history = result.new_live, result.new_history
        titles = {e.title for e in change_log.parse_change_log(content)}
        after = {e.title for e in change_log.parse_change_log(new_live)} | {
            e.title for e in change_log.parse_change_log(new_history)
        }
        assert after == titles

    def test_a_moved_entry_keeps_its_tag_line(self):
        """History is a redirect: an entry arrives whole, tag included."""
        content = _log(_entry("2026-01-01: a", "scope=a | release=v3.2.0"))
        new_history = change_log_archive.archive_or_refuse(
            content, None, change_log_archive.MinorLine(3, 4)
        ).new_history
        moved = change_log.parse_change_log(new_history)
        assert moved[0].tags["release"] == "v3.2.0"
        assert moved[0].tags["scope"] == "a"

    def test_a_second_run_appends_rather_than_replacing(self):
        first = _log(_entry("2026-01-01: a", "scope=a | release=v3.2.0"))
        history = change_log_archive.archive_or_refuse(
            first, None, change_log_archive.MinorLine(3, 4)
        ).new_history
        second = _log(_entry("2026-01-02: b", "scope=b | release=v3.3.0"))
        history2 = change_log_archive.archive_or_refuse(
            second, history, change_log_archive.MinorLine(3, 4)
        ).new_history
        assert [e.title for e in change_log.parse_change_log(history2)] == [
            "2026-01-02: b",
            "2026-01-01: a",
        ]

    def test_the_live_header_is_not_carried_into_history(self):
        content = _log(_entry("2026-01-01: a", "scope=a | release=v3.2.0"))
        result = change_log_archive.archive_or_refuse(
            content, None, change_log_archive.MinorLine(3, 4)
        )
        new_live, new_history = result.new_live, result.new_history
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

    def test_a_products_own_declaration_is_what_is_read(self, tmp_path: Path):
        """The portability property, on a repo with no `plugin/` directory."""
        content = _log(
            _entry("2026-01-01: a", "scope=a | release=v2.0.9"),
            _entry("2026-02-01: b", "scope=b | release=v2.1.3"),
        )
        project = _product(
            tmp_path,
            content,
            "release_version_files:\n  - path: src/version.txt\n    format: bare\n",
            {"src/version.txt": "2.1.3\n"},
        )
        result = _run_hook(project, "--apply")
        assert result.returncode == 0, result.stderr
        assert "2026-01-01: a" in _history(project)
        assert "2026-02-01: b" in _live(project)

    def test_a_declared_empty_list_is_honoured_rather_than_guessed_past(
        self, tmp_path: Path
    ):
        """`[]` is a product saying it ships no version file — a DECLARATION.

        Falling back to prawduct's layout here is the layout-over-declaration
        defect wearing the fix for itself: the repo below carries a
        `plugin/VERSION` that would answer, and it must not be consulted.
        """
        content = _log(_entry("2026-01-01: a", "scope=a | release=v2.0.9"))
        project = _product(
            tmp_path,
            content,
            "release_version_files: []\n",
            {"plugin/VERSION": "3.4.1\n"},
        )
        result = _run_hook(project, "--apply")
        assert result.returncode == 1, result.stdout
        assert "no-version" in result.stderr
        assert _live(project) == content

    def test_an_undeclared_product_falls_back_to_the_guess(self, tmp_path: Path):
        """The third outcome, and the only one the guess is for."""
        content = _log(_entry("2026-01-01: a", "scope=a | release=v2.0.9"))
        project = _product(
            tmp_path, content, "some_other_key: 1\n", {"plugin/VERSION": "3.4.1\n"}
        )
        result = _run_hook(project, "--apply")
        assert result.returncode == 0, result.stderr
        assert "2026-01-01: a" in _history(project)

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

    def test_the_refusal_reaches_the_operator_and_writes_nothing(
        self, tmp_path: Path, monkeypatch, capsys
    ):
        """The CLI half of the guard, driven in-process.

        The library refusing is tested above; this asserts the command ACTS on
        it — exit 1, the entry named, and neither file touched. A guard whose
        caller ignores it is not a guard, and no input can reach this branch
        from outside, so a subprocess test would be asserting nothing.
        """
        content = _log(
            _entry("2026-01-01: shipped", "scope=a | release=v3.3.4"),
            _entry("2026-02-01: pending", "scope=b"),
        )
        project = _project(tmp_path, content)
        hook = _load_hook()
        archive = hook._change_log_archive()
        monkeypatch.setattr(
            archive,
            "archive_or_refuse",
            lambda live, hist, keep: archive.ArchiveResult(
                "", "", [], ["2026-02-01: pending"]
            ),
        )

        code = hook.cmd_archive_change_log(project, ["--apply"])

        assert code == 1
        assert "refused" in capsys.readouterr().err
        assert _live(project) == content
        assert not (project / ".prawduct" / "change-log-history.md").exists()

    def test_json_reports_what_happened_not_what_was_asked(self, tmp_path: Path):
        """`applied` is read after the write, so a dry run cannot claim one."""
        import json as json_mod

        content = _log(_entry("2026-01-01: a", "scope=a | release=v3.2.0"))
        project = _project(tmp_path, content)

        dry = json_mod.loads(_run_hook(project, "--json").stdout)
        assert dry["applied"] is False
        assert dry["moved"] == 1
        assert dry["titles"] == ["2026-01-01: a"]
        assert _live(project) == content

        wet = json_mod.loads(_run_hook(project, "--json", "--apply").stdout)
        assert wet["applied"] is True
        assert "2026-01-01: a" in _history(project)

    def test_a_failed_second_write_leaves_both_files_untouched(
        self, tmp_path: Path, monkeypatch
    ):
        """Entries MOVE between the two files, so a half-applied pair holds
        every entry twice — and re-running duplicates them into an append-only
        record. Write both or neither."""
        content = _log(
            _entry("2026-01-01: a", "scope=a | release=v3.2.0"),
            _entry("2026-02-01: b", "scope=b"),
        )
        project = _project(tmp_path, content)
        hook = _load_hook()
        core = hook._core()

        real_write = core.atomic_write_text
        calls = {"n": 0}

        def _explode(path, text, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("disk full")
            return real_write(path, text, **kwargs)

        monkeypatch.setattr(core, "atomic_write_text", _explode)

        with pytest.raises(OSError):
            hook.cmd_archive_change_log(project, ["--apply"])

        assert _live(project) == content
        assert not (project / ".prawduct" / "change-log-history.md").exists()

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

    Every case above is a shape someone thought of. This one is the entries that
    actually exist, with tag lines written by hand over six months.

    **The kept line is derived from the corpus, never from today's version.**
    Asserting against `current_minor_line` would pin the repo's current PHASE:
    this plan's next chunk archives everything below v3.4, and a test demanding
    that something below v3.4 remains eligible goes red the moment the work it
    is supposed to protect actually happens. One minor above the highest release
    the log mentions keeps every shipped entry eligible in every phase, which is
    the property — not the number.
    """
    repo = Path(__file__).resolve().parent.parent
    live = (repo / ".prawduct" / "change-log.md").read_text(encoding="utf-8")
    entries = change_log.parse_change_log(live)

    lines = [
        line
        for line in (
            change_log_archive.release_minor_line(e.tags.get("release"))
            for e in entries
        )
        if line is not None
    ]
    assert lines, "no entry carries a parseable release= — the corpus moved"
    highest = max(lines)
    keep_from = change_log_archive.MinorLine(highest.major, highest.minor + 1)

    result = change_log_archive.archive_or_refuse(live, None, keep_from)

    assert result.refused_titles == [], result.refused_titles
    assert result.moved, "every shipped entry was ineligible — selection broke"
    assert change_log_archive.pending_fingerprint(
        live
    ) == change_log_archive.pending_fingerprint(result.new_live)

    before = {e.title for e in entries}
    after = {e.title for e in change_log.parse_change_log(result.new_live)} | {
        e.title for e in change_log.parse_change_log(result.new_history)
    }
    assert after == before, "an entry was neither kept nor archived"

    for entry in change_log.parse_change_log(result.new_history):
        assert entry.tags.get("release"), (
            f"{entry.title!r} reached history with no release= — only shipped "
            "entries may leave the live log"
        )


def test_the_live_log_still_parses_after_this_repos_entries_are_archived():
    """The rewrite must not change how what REMAINS reads.

    Moving whole entries cannot alter the diagnostics of the ones left behind —
    if it does, the split found a boundary the parser disagrees with, and the
    guard says so rather than the next release gate.
    """
    repo = Path(__file__).resolve().parent.parent
    live = (repo / ".prawduct" / "change-log.md").read_text(encoding="utf-8")
    keep_from = change_log_archive.current_minor_line(repo)
    assert keep_from is not None

    result = change_log_archive.archive_or_refuse(live, None, keep_from)

    assert change_log_archive.new_diagnostics(live, result.new_live) == []
