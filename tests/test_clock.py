"""`lib/clock.py` is the one owner of "now", and the suite runs every actor on one clock.

The Stop gate compares the `.session-start` stamp the hook writes with git's own dates (the
session work span walks the HEAD reflog back to that stamp). The suite pins git's dates, so the
code that writes the stamp has to read the same pinned instant, or a commit made after a session
began reads as made before it and the committed-work path never runs. These tests pin the seam
itself, that it reaches each way the code runs (in-process, and a hook subprocess), and that a
wall-clock read cannot be added beside it without saying why.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN = REPO_ROOT / "plugin"
HOOK = PLUGIN / "bin" / "prawduct-hook"
sys.path.insert(0, str(PLUGIN))

from lib import clock, evidence  # noqa: E402
from conftest import TEST_NOW, TEST_NOW_EPOCH, scrubbed_env, set_suite_clock  # noqa: E402

FROZEN = datetime.fromtimestamp(TEST_NOW_EPOCH, timezone.utc)


class TestTheSeam:
    def test_a_pinned_instant_is_what_now_reads(self, monkeypatch):
        monkeypatch.setenv(clock.FROZEN_ENV, "@1700000000 +0000")
        assert clock.frozen() == datetime(2023, 11, 14, 22, 13, 20, tzinfo=timezone.utc)
        assert clock.now() == clock.frozen()
        assert clock.now_iso() == "2023-11-14T22:13:20Z"

    @pytest.mark.parametrize(
        "value", ["", "1700000000", "@1700000000", "@1700000000 +0100", "@abc +0000", "now"]
    )
    def test_a_value_that_is_not_the_suites_form_is_not_obeyed(self, monkeypatch, value):
        """The variable exists only for the suite, which always writes git's internal form in
        UTC; anything else is someone else's value, and the clock stays real."""
        monkeypatch.setenv(clock.FROZEN_ENV, value)
        assert clock.frozen() is None

    @pytest.mark.uncacheable("its subject is the real clock: unpinned, now reads the wall clock")
    def test_unpinned_the_clock_is_real(self, monkeypatch):
        monkeypatch.delenv(clock.FROZEN_ENV, raising=False)
        before = datetime.now(timezone.utc)
        read = clock.now()
        assert read.tzinfo is not None
        assert before <= read <= datetime.now(timezone.utc)
        assert clock.local_today() == date.today()

    def test_the_name_says_it_is_for_tests_only(self):
        """A consumer's shell or CI never sets it for another reason."""
        assert clock.FROZEN_ENV == "PRAWDUCT_TEST_ONLY_FROZEN_NOW"

    def test_only_the_clock_reads_the_variable(self):
        """One owner: no other plugin file can freeze, or read, a clock of its own."""
        readers = sorted(
            str(path.relative_to(REPO_ROOT))
            for path in PLUGIN.rglob("*")
            if path.is_file() and path.suffix in (".py", "")
            and clock.FROZEN_ENV in path.read_text(encoding="utf-8", errors="replace")
        )
        assert readers == ["plugin/lib/clock.py"]


class TestDatingAFile:
    def test_a_pinned_clock_dates_the_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv(clock.FROZEN_ENV, "@1700000000 +0000")
        marker = tmp_path / "marker"
        marker.write_text("x")
        clock.date_file(marker)
        assert marker.stat().st_mtime == 1700000000

    def test_a_real_clock_leaves_the_file_alone(self, tmp_path, monkeypatch):
        monkeypatch.delenv(clock.FROZEN_ENV, raising=False)
        marker = tmp_path / "marker"
        marker.write_text("x")
        os.utime(marker, (1600000000, 1600000000))
        clock.date_file(marker)
        assert marker.stat().st_mtime == 1600000000


class TestTheLocalCalendar:
    @pytest.fixture
    def pacific(self, monkeypatch):
        if not hasattr(time, "tzset"):
            pytest.skip("no tzset on this platform")
        monkeypatch.setenv("TZ", "America/Los_Angeles")
        time.tzset()
        yield
        monkeypatch.undo()
        time.tzset()

    def test_an_evening_west_of_utc_is_still_that_day(self, monkeypatch, pacific):
        """03:30 UTC on the 26th is 20:30 on the 25th in Los Angeles: the operator's date."""
        evening = datetime(2026, 10, 26, 3, 30, tzinfo=timezone.utc)
        monkeypatch.setenv(clock.FROZEN_ENV, f"@{int(evening.timestamp())} +0000")
        assert clock.now().date() == date(2026, 10, 26)
        assert clock.local_today() == date(2026, 10, 25)

    @pytest.mark.parametrize("zone", [
        "Etc/GMT+11", "America/Los_Angeles", "UTC", "Asia/Tokyo", "Etc/GMT-11",
    ])
    def test_the_suites_instant_is_the_same_day_from_utc_minus_11_to_plus_11(self, monkeypatch, zone):
        """Noon UTC, so a local date read from the suite's clock does not move with the machine
        anywhere in that band. Beyond it the date does move (the control): a test that pins a
        local date compares with the local calendar, not with the UTC one."""
        if not hasattr(time, "tzset"):
            pytest.skip("no tzset on this platform")
        try:
            monkeypatch.setenv("TZ", zone)
            time.tzset()
            assert clock.local_today() == FROZEN.date()
            monkeypatch.setenv("TZ", "Pacific/Kiritimati")  # UTC+14
            time.tzset()
            assert clock.local_today() != FROZEN.date()
        finally:
            monkeypatch.undo()
            time.tzset()


class TestTheSuiteRunsOneClock:
    def test_git_and_the_plugin_read_the_same_instant(self):
        assert os.environ[clock.FROZEN_ENV] == TEST_NOW
        assert os.environ["GIT_COMMITTER_DATE"] == TEST_NOW
        assert os.environ["GIT_AUTHOR_DATE"] == TEST_NOW
        assert clock.now() == FROZEN

    def test_in_process_code_stamps_records_on_it(self, tmp_path):
        """An in-process call inherits this process's environment, the seam included."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        result = evidence.append_fact(repo, "session-start", "session-start-x", {})
        assert result["status"] == "appended", result
        (fact,) = evidence.facts_of_kind(evidence.read_facts(repo), "session-start")
        assert fact["ts"] == FROZEN.strftime("%Y-%m-%dT%H:%M:%SZ")

    def test_a_hook_subprocess_stamps_the_session_on_it(self, tmp_path):
        """A scrubbed child gets the seam from `scrubbed_env`; the stamp's text and its mtime
        (which `evidence._session_epoch` reads) both say the suite's instant."""
        repo = tmp_path / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        (repo / ".prawduct").mkdir()
        proc = subprocess.run(
            [sys.executable, str(HOOK), "clear", "--session-start"],
            cwd=repo, capture_output=True, text=True, timeout=60,
            env=scrubbed_env(tmp_path / "_home", CLAUDE_PROJECT_DIR=str(repo),
                             CLAUDE_PLUGIN_ROOT=str(PLUGIN)),
        )
        assert proc.returncode == 0, proc.stderr
        marker = repo / ".prawduct" / ".session-start"
        assert marker.read_text().strip() == FROZEN.strftime("%Y-%m-%dT%H:%M:%SZ")
        assert marker.stat().st_mtime == TEST_NOW_EPOCH

    def test_a_suite_setting_a_test_removed_stays_out_of_a_scrubbed_child(self, monkeypatch, tmp_path):
        """A test that lifts one of the suite's settings with `delenv` (the global-excludes
        tests lift `GIT_CONFIG_GLOBAL`) lifts it for the children it scrubs too."""
        monkeypatch.delenv("GIT_CONFIG_GLOBAL")
        env = scrubbed_env(tmp_path / "_home")
        assert "GIT_CONFIG_GLOBAL" not in env
        assert env["GIT_CONFIG_NOSYSTEM"] == "1", "control: the settings left in place still reach it"

    def test_moving_the_clock_moves_both(self, monkeypatch, tmp_path):
        instant = set_suite_clock(monkeypatch, 90)
        assert instant == f"@{TEST_NOW_EPOCH + 90} +0000"
        assert os.environ["GIT_COMMITTER_DATE"] == instant
        assert clock.now().timestamp() == TEST_NOW_EPOCH + 90
        assert scrubbed_env(tmp_path / "_home")[clock.FROZEN_ENV] == instant


# Each plugin file that still reads the wall clock directly, how many times, and why it does not
# read `lib.clock`. A new read is either routed through the seam or added here with its reason,
# so "which clock does this read" is a decision someone made, not a default. The decision is per
# COMPARISON: a read stays real only when everything it is compared with is real too (a file's
# mtime, another process's start, a stamp this same read's clock minted). A stamp that is
# persisted or returned and then compared with one `lib.clock` wrote reads `lib.clock`.
LEFT_ON_THE_REAL_CLOCK = {
    "plugin/lib/stranded_work.py": (3, (
        "a worktree's liveness ages file mtimes (transcripts, the reflog, edits), which the"
        " filesystem dates; the third read carries the `.session-start` stamp onto that clock."
        " Commit dates age on `lib.clock`, the clock git's agrees with")),
    "plugin/lib/git_hygiene.py": (1, "passes `now` to stranded_work's worktree scan, which ages file mtimes"),
    "plugin/lib/host.py": (1, "an ordering key for the transcript cache, compared with no stamp"),
    "plugin/lib/briefing.py": (1, "a handoff file's age, from its mtime"),
    "plugin/lib/contribution.py": (1, "a send lock's age, from its mtime"),
    "plugin/lib/critic_marker.py": (2, (
        "a running review's liveness: the marker's `started_at` is minted and aged here and"
        " nowhere else, else its mtime")),
    "plugin/lib/record_progress.py": (3, "a running recorder's liveness, against the OS's process start"),
    "plugin/lib/critic_consolidate.py": (5, (
        "a review id's stamp and dispatch_age_minutes's default `now`, which ages only that stamp:"
        " dispatched reviewers' real elapsed time; a started marker's age from its mtime; an"
        " archive directory's fallback name, compared with nothing; the superseded-at notice,"
        " which a reader is shown and no code compares")),
    "plugin/bin/prawduct-hook": (1, "the recorder's in-progress stamp, which record_progress ages"),
}
_WALL_CLOCK = re.compile(
    r"datetime\.now\(|datetime\.utcnow\(|\bdate\.today\(\)|\b_date\.today\(\)|\btime\.time\(\)"
)


def test_every_direct_wall_clock_read_is_accounted_for():
    found: dict[str, int] = {}
    for path in sorted(PLUGIN.rglob("*")):
        if not path.is_file() or path.suffix not in (".py", "") or "__pycache__" in path.parts:
            continue
        rel = str(path.relative_to(REPO_ROOT))
        if rel == "plugin/lib/clock.py":
            continue
        count = sum(
            1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines()
            if _WALL_CLOCK.search(line) and not line.lstrip().startswith("#")
        )
        if count:
            found[rel] = count
    # The scan reads what it claims to: the clock's own real-clock fallback is the shape it hunts.
    assert _WALL_CLOCK.search((PLUGIN / "lib" / "clock.py").read_text())
    assert found == {path: count for path, (count, _why) in LEFT_ON_THE_REAL_CLOCK.items()}
