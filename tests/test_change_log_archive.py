"""The change-log archive: bounded live log, lossless move, whole-history readers.

The claims each test pins, in the order a reader of the module meets them:

* nothing moves below the threshold, and above it the live log is cut to half;
* release-pending entries never move in a product that versions — including
  after a first run has archived every released entry out of the live log;
* an unversioned product's tagged entries age out like any other;
* undated entries and entries with an unparsed tag line stay live;
* newest first, and once one entry does not fit, everything older moves;
* the move is lossless: live + archive holds exactly the original entries;
* a malformed tag refuses with nothing written, and so does a selection the
  release gate's own readers would see differently, or an archive git would ignore;
* a failed write restores every file;
* readers that interpret history (plan-backfill, record-lint's scope witness)
  see archived entries.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from lib import change_log, change_log_archive as cla, plan_backfill, record_lint

_HOOK_PATH = Path(__file__).resolve().parent.parent / "plugin" / "bin" / "prawduct-hook"

HEADER = "# Change Log\n\n<!-- Append new entries at the top. -->\n\n"


def _entry(date: str, title: str, tags: str | None = None, body_bytes: int = 300) -> str:
    tag = f"<!-- prawduct: {tags} -->\n\n" if tags else ""
    return f"## {date}: {title}\n\n{tag}" + ("prose " * (body_bytes // 6)) + "\n\n"


def _titles(text: str) -> list[str]:
    return [e.title for e in change_log.parse_change_log(text)]


def _repo(tmp_path: Path, log: str, threshold_kb: int = 2) -> Path:
    prawduct = tmp_path / ".prawduct"
    prawduct.mkdir(parents=True)
    (prawduct / "project-state.yaml").write_text(
        f"project: demo\noversized_file_threshold_kb: {threshold_kb}\n", encoding="utf-8"
    )
    (prawduct / "change-log.md").write_text(log, encoding="utf-8")
    return prawduct


def _archive(prawduct: Path) -> dict[str, str]:
    directory = prawduct / cla.ARCHIVE_DIR_NAME
    if not directory.is_dir():
        return {}
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(directory.glob("*.md"))}


def _run(prawduct: Path) -> None:
    text = (prawduct / "change-log.md").read_text(encoding="utf-8")
    versions = cla.product_versions(text, prawduct / cla.ARCHIVE_DIR_NAME)
    selection = cla.select(text, threshold=2000, versions=versions)
    cla.apply(prawduct, selection)


# A versioned log: two pending entries on top, released history below.
VERSIONED = (
    HEADER
    + _entry("2026-09-10", "pending newest", "scope=gamma")
    + _entry("2026-09-09", "pending second", "scope=gamma")
    + _entry("2026-09-01", "released recent", "scope=beta | release=v1.2.0")
    + _entry("2026-08-20", "released august", "scope=beta | release=v1.1.0")
    + _entry("2026-07-15", "released july", "scope=alpha | release=v1.0.0")
    + _entry("2026-07-01", "untagged july")
)


class TestSelection:
    def test_nothing_moves_at_or_below_the_threshold(self) -> None:
        selection = cla.select(VERSIONED, threshold=len(VERSIONED.encode()), versions=True)
        assert selection.moved == []

    def test_above_the_threshold_the_live_log_is_cut_to_half(self) -> None:
        selection = cla.select(VERSIONED, threshold=2000, versions=True)
        assert selection.moved
        assert selection.kept_bytes + len(cla.ARCHIVE_POINTER) + 2 <= 1000

    def test_pending_entries_never_move_in_a_versioned_product(self) -> None:
        selection = cla.select(VERSIONED, threshold=500, versions=True)
        kept = [b.entry.title for b in selection.kept]
        assert "2026-09-10: pending newest" in kept
        assert "2026-09-09: pending second" in kept
        assert all(b.entry.tags.get("release") or not b.entry.tag_line_count
                   for b in selection.moved)

    def test_an_unversioned_products_tagged_entries_age_out(self) -> None:
        log = HEADER + "".join(
            _entry(f"2026-0{m}-01", f"work {m}", f"scope=s{m}") for m in range(9, 1, -1)
        )
        selection = cla.select(log, threshold=2000, versions=False)
        assert selection.moved
        assert selection.kept[0].entry.title == "2026-09-01: work 9"

    def test_undated_and_unparsed_tag_entries_stay_live(self) -> None:
        log = (
            HEADER
            + _entry("2026-09-01", "new", body_bytes=900)
            + "## Some undated heading\n\nold prose\n\n"
            + _entry("2026-01-01", "merge debris", "scope=a | release=v0.1.0")
            .replace("prose ", "prose\n<!-- prawduct: release=v0.2.0 -->\n", 1)
            + _entry("2026-01-02", "plain old", body_bytes=900)
        )
        selection = cla.select(log, threshold=1500, versions=True)
        kept = [b.entry.title for b in selection.kept]
        assert "Some undated heading" in kept
        assert "2026-01-01: merge debris" in kept
        assert "2026-01-02: plain old" in [b.entry.title for b in selection.moved]

    def test_once_an_entry_does_not_fit_everything_older_moves(self) -> None:
        log = (
            HEADER
            + _entry("2026-09-03", "small new", body_bytes=100)
            + _entry("2026-09-02", "big middle", body_bytes=3000)
            + _entry("2026-09-01", "small old", body_bytes=100)
        )
        selection = cla.select(log, threshold=2000, versions=False)
        assert [b.entry.title for b in selection.kept] == ["2026-09-03: small new"]

    def test_a_malformed_release_tag_refuses(self) -> None:
        log = VERSIONED + _entry("2026-06-01", "placeholder", "scope=x | release=unreleased")
        with pytest.raises(cla.ArchiveRefused):
            cla.select(log, threshold=500, versions=True)


class TestApply:
    def test_the_move_is_lossless_and_bucketed_by_month(self, tmp_path: Path) -> None:
        prawduct = _repo(tmp_path, VERSIONED)
        original = sorted(_titles(VERSIONED))
        _run(prawduct)

        live = (prawduct / "change-log.md").read_text(encoding="utf-8")
        archive = _archive(prawduct)
        assert set(archive) <= {"2026-07.md", "2026-08.md", "2026-09.md"}
        assert archive
        everything = _titles(live) + [t for text in archive.values() for t in _titles(text)]
        assert sorted(everything) == original
        assert cla.ARCHIVE_POINTER in live
        for name, text in archive.items():
            assert all(t.startswith(name[:7]) for t in _titles(text))

    def test_entry_bytes_are_unchanged_by_the_move(self, tmp_path: Path) -> None:
        prawduct = _repo(tmp_path, VERSIONED)
        _run(prawduct)
        archived = "".join(_archive(prawduct).values())
        july = _entry("2026-07-15", "released july", "scope=alpha | release=v1.0.0")
        assert july.rstrip("\n") in archived

    def test_a_second_run_merges_into_existing_buckets_newest_first(self, tmp_path: Path) -> None:
        prawduct = _repo(tmp_path, VERSIONED)
        _run(prawduct)
        live = prawduct / "change-log.md"
        text = live.read_text(encoding="utf-8")
        head, _, rest = text.partition("## ")
        live.write_text(
            head + _entry("2026-09-12", "released later", "scope=gamma | release=v1.3.0",
                          body_bytes=2500)
            + "## " + rest,
            encoding="utf-8",
        )
        _run(prawduct)
        september = _titles(_archive(prawduct)["2026-09.md"])
        assert september == sorted(september, reverse=True)
        assert len(september) == len(set(september))

    def test_pending_work_survives_a_rerun_after_released_history_left(self, tmp_path: Path) -> None:
        """The failure the archive scan in `product_versions` exists for: after the
        first run, the live log may hold no `release=` tag at all."""
        prawduct = _repo(tmp_path, VERSIONED)
        _run(prawduct)
        live = prawduct / "change-log.md"
        text = live.read_text(encoding="utf-8")
        assert not any(e.tags.get("release") for e in change_log.parse_change_log(text))
        live.write_text(text + _entry("2026-09-11", "more pending", "scope=gamma",
                                      body_bytes=3000), encoding="utf-8")
        _run(prawduct)
        remaining = _titles(live.read_text(encoding="utf-8"))
        assert {"2026-09-10: pending newest", "2026-09-09: pending second",
                "2026-09-11: more pending"} <= set(remaining)

    def test_an_entry_already_in_its_month_file_is_not_archived_twice(self, tmp_path: Path) -> None:
        """A live log restored over an applied run (a revert, a bad merge) holds
        entries its month files already have. Re-running must leave one copy of
        each: gone from the live log, present once in the archive."""
        prawduct = _repo(tmp_path, VERSIONED)
        selection = cla.select(VERSIONED, threshold=2000, versions=True)
        cla.apply(prawduct, selection)
        moved = {b.entry.title for b in selection.moved}
        (prawduct / "change-log.md").write_text(VERSIONED, encoding="utf-8")
        _run(prawduct)
        archived = [t for s in _archive(prawduct).values() for t in _titles(s)]
        assert sorted(archived) == sorted(moved)
        assert not moved & set(_titles((prawduct / "change-log.md").read_text(encoding="utf-8")))

    def test_a_failed_write_restores_every_file(self, tmp_path: Path, monkeypatch) -> None:
        from lib import core

        prawduct = _repo(tmp_path, VERSIONED)
        real = core.atomic_write_text
        calls: list = []

        def _full(path, text, *args, **kwargs):
            calls.append(path)
            if len(calls) == 2:
                raise OSError(28, "No space left on device")
            return real(path, text, *args, **kwargs)

        monkeypatch.setattr(core, "atomic_write_text", _full)
        selection = cla.select(VERSIONED, threshold=2000, versions=True)
        assert len(selection.buckets) >= 2, "fixture must make the second write an archive file"
        with pytest.raises(OSError):
            cla.apply(prawduct, selection)
        assert (prawduct / "change-log.md").read_text(encoding="utf-8") == VERSIONED
        assert _archive(prawduct) == {}

    def test_a_stale_month_file_header_is_rewritten(self, tmp_path: Path) -> None:
        prawduct = _repo(tmp_path, VERSIONED)
        (prawduct / cla.ARCHIVE_DIR_NAME).mkdir()
        (prawduct / cla.ARCHIVE_DIR_NAME / "2026-07.md").write_text(
            "# wrong header naming the wrong reader\n\n", encoding="utf-8"
        )
        _run(prawduct)
        july = _archive(prawduct)["2026-07.md"]
        assert july.startswith("# Change log archive — 2026-07")
        assert "wrong reader" not in july


class TestTheReleaseGateChecksTheResult:
    """The selection keeps pending entries by construction; the invariant is the
    check that does not trust the construction."""

    def test_a_selection_that_would_drop_pending_work_refuses(self, monkeypatch) -> None:
        monkeypatch.setattr(cla, "_pinned", lambda block, versions: block.bucket is None)
        with pytest.raises(cla.ArchiveRefused, match="release-pending entries would leave"):
            cla.select(VERSIONED, threshold=500, versions=True)

    def test_an_unversioned_product_has_no_pending_set_to_protect(self) -> None:
        log = HEADER + "".join(
            _entry(f"2026-0{m}-01", f"work {m}", f"scope=s{m}") for m in range(9, 1, -1)
        )
        assert cla.invariant_violations(log, HEADER, versions=False) == []
        assert cla.invariant_violations(log, HEADER, versions=True)

    def test_a_diagnostic_that_only_moved_line_is_not_new(self) -> None:
        doubled = _entry("2026-09-05", "two tag lines", "scope=z").replace(
            "-->\n\n", "-->\n<!-- prawduct: type=fix -->\n\n", 1
        )
        before = HEADER + _entry("2026-09-06", "above", body_bytes=600) + doubled
        after = HEADER + doubled
        assert cla.invariant_violations(before, after, versions=True) == []

    def test_the_release_gate_still_finds_scopes_tagged_for_an_archived_release(
        self, tmp_path: Path
    ) -> None:
        from lib import release_readiness

        prawduct = _repo(tmp_path, VERSIONED)
        _run(prawduct)
        live = change_log.parse_change_log((prawduct / "change-log.md").read_text(encoding="utf-8"))
        assert release_readiness.scopes_tagged_for(live, "v1.0.0") == set()
        history = release_readiness._history_entries(tmp_path, live)
        assert release_readiness.scopes_tagged_for(history, "v1.0.0") == {"alpha"}


class TestWholeHistoryReaders:
    def test_plan_backfill_sees_a_release_that_was_archived(self, tmp_path: Path) -> None:
        prawduct = _repo(tmp_path, VERSIONED)
        (prawduct / "artifacts").mkdir()
        (prawduct / "artifacts" / "build-plan-alpha.md").write_text(
            "---\nartifact: build-plan\nscope: alpha\n---\n\n## Status\n\n- [x] Chunk 01: done\n",
            encoding="utf-8",
        )
        _run(prawduct)
        assert "alpha" not in plan_backfill.shipped_scopes(
            (prawduct / "change-log.md").read_text(encoding="utf-8")
        )
        shipped = plan_backfill.survey(prawduct)["shipped"]
        assert [(i["scope"], i["release"]) for i in shipped] == [("alpha", "v1.0.0")]

    def test_the_scope_witness_reads_the_archive(self, tmp_path: Path) -> None:
        prawduct = _repo(tmp_path, VERSIONED)
        _run(prawduct)
        assert record_lint._scope_declared_in_change_log(prawduct, "alpha") is True
        assert record_lint._scope_declared_in_change_log(prawduct, "nope") is False

    def test_load_all_text_is_none_when_the_live_log_is_unreadable(self, tmp_path: Path) -> None:
        assert cla.load_all_text(tmp_path) is None


def _cli(prawduct: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_HOOK_PATH), "archive-change-log", *args],
        cwd=str(prawduct.parent), capture_output=True, text=True, timeout=60,
    )


class TestCommand:
    def test_dry_run_writes_nothing(self, tmp_path: Path) -> None:
        prawduct = _repo(tmp_path, VERSIONED)
        proc = _cli(prawduct)
        assert proc.returncode == 0, proc.stderr
        assert "would move" in proc.stdout
        assert _archive(prawduct) == {}
        assert (prawduct / "change-log.md").read_text(encoding="utf-8") == VERSIONED

    def test_apply_moves_and_reports_json(self, tmp_path: Path) -> None:
        prawduct = _repo(tmp_path, VERSIONED)
        proc = _cli(prawduct, "--apply", "--json")
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        assert payload["applied"] is True
        assert payload["product_versions"] is True
        assert payload["moved"] == sum(payload["buckets"].values())
        assert _archive(prawduct)

    def test_below_threshold_is_a_no_op(self, tmp_path: Path) -> None:
        prawduct = _repo(tmp_path, VERSIONED, threshold_kb=40)
        proc = _cli(prawduct, "--apply")
        assert proc.returncode == 0
        assert "nothing to move" in proc.stdout
        assert _archive(prawduct) == {}

    def test_a_malformed_tag_refuses_with_exit_1(self, tmp_path: Path) -> None:
        log = VERSIONED + _entry("2026-06-01", "bad", "scope=x | release=unreleased")
        prawduct = _repo(tmp_path, log)
        proc = _cli(prawduct, "--apply")
        assert proc.returncode == 1
        assert proc.stderr.startswith("refused:")
        assert _archive(prawduct) == {}
        assert (prawduct / "change-log.md").read_text(encoding="utf-8") == log

    def test_an_archive_git_would_ignore_refuses(self, tmp_path: Path) -> None:
        """Committing the live log's removals without the month files they moved
        to would drop history from git with no error anywhere."""
        prawduct = _repo(tmp_path, VERSIONED)
        env = {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
               "HOME": str(tmp_path), "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"}

        def git(*args: str) -> None:
            subprocess.run(["git", *args], cwd=str(tmp_path), check=True,
                           capture_output=True, env=env)

        git("init", "-q", "-b", "main")
        (tmp_path / ".gitignore").write_text(
            ".prawduct/*\n!.prawduct/change-log.md\n!.prawduct/project-state.yaml\n",
            encoding="utf-8",
        )
        git("add", ".gitignore", ".prawduct/change-log.md", ".prawduct/project-state.yaml")
        git("-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "init")

        proc = _cli(prawduct, "--apply")
        assert proc.returncode == 1, proc.stdout
        assert "would ignore" in proc.stderr
        assert _archive(prawduct) == {}
        assert (prawduct / "change-log.md").read_text(encoding="utf-8") == VERSIONED

    def test_unknown_argument_is_a_usage_error(self, tmp_path: Path) -> None:
        assert _cli(_repo(tmp_path, VERSIONED), "--force").returncode == 2
