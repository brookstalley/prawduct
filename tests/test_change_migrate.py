"""Tests for the legacy change log → fragments migration (#1012, FRG7).

The migration moves a repo's pending record from one file into many, so what it
must never do is pinned beside what it does: convert a shipped or untagged entry,
guess at an entry its author has to decide about, write anything when it refuses,
or leave the release gate seeing a different pending set afterwards.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_PLUGIN = Path(__file__).resolve().parent.parent / "plugin"
if str(_PLUGIN) not in sys.path:
    sys.path.insert(0, str(_PLUGIN))

from lib import change_fragments, change_migrate, release_readiness  # noqa: E402

HOOK = _PLUGIN / "bin" / "prawduct-hook"
PREAMBLE = "# Change Log\n\n<!-- Newest first. -->\n\n"


def _entry(title: str, tags: str | None, body: str = "What changed.") -> str:
    tag = f"<!-- prawduct: {tags} -->\n\n" if tags is not None else ""
    return f"## {title}\n\n{tag}{body}\n\n"


def _project(tmp_path: Path, log: str | None) -> Path:
    project = tmp_path / "proj"
    (project / ".prawduct").mkdir(parents=True)
    if log is not None:
        (project / ".prawduct" / "change-log.md").write_text(log)
    return project


def _snapshot(project: Path) -> dict[str, str]:
    return {
        str(p.relative_to(project)): p.read_text()
        for p in sorted(project.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(project).parts
    }


def _migrate(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(HOOK), "migrate-change-log", *args],
        cwd=str(project), capture_output=True, text=True, timeout=60,
        env={"PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": str(project), "HOME": str(project.parent)},
    )


MIXED = (
    PREAMBLE
    + _entry("2026-10-19: pending feature", "type=feat | scope=alpha", "Alpha narrative.\n\n- a bullet")
    + _entry("2026-10-18: shipped fix", "type=fix | scope=beta | release=v3.7.1", "Beta shipped.")
    + _entry("2026-10-17: untagged note", None, "Old prose.")
    + _entry("2026-10-16: pending fix", "type=bugfix | scope=gamma", "Gamma narrative.")
)


class TestConversion:
    def test_an_empty_log_converts_nothing(self):
        result = change_fragments.legacy_entries_as_fragments(PREAMBLE)
        assert result.fragments == () and result.refusals == ()
        assert result.remaining == PREAMBLE

    def test_a_pending_only_log_becomes_fragments_and_keeps_its_preamble(self):
        log = PREAMBLE + _entry("2026-10-19: only one", "type=chore | scope=solo", "Solo narrative.")
        result = change_fragments.legacy_entries_as_fragments(log)
        assert [scope for scope, _ in result.fragments] == ["solo"]
        assert result.remaining == PREAMBLE.rstrip("\n") + "\n"

    def test_mixed_converts_only_pending_entries_and_leaves_the_rest_verbatim(self):
        result = change_fragments.legacy_entries_as_fragments(MIXED)
        assert result.refusals == ()
        assert [scope for scope, _ in result.fragments] == ["alpha", "gamma"]
        expected = (
            PREAMBLE
            + _entry("2026-10-18: shipped fix", "type=fix | scope=beta | release=v3.7.1", "Beta shipped.")
            + _entry("2026-10-17: untagged note", None, "Old prose.")
        ).rstrip("\n") + "\n"
        assert result.remaining == expected

    def test_each_fragment_is_valid_and_carries_the_entry(self):
        result = change_fragments.legacy_entries_as_fragments(MIXED)
        texts = dict(result.fragments)
        alpha = change_fragments.check_fragment_text(texts["alpha"], Path("alpha.md"))
        assert alpha.ok, alpha.problems
        fragment = alpha.fragment
        assert (fragment.type, fragment.date, fragment.title) == ("feature", "2026-10-19", "pending feature")
        assert fragment.narrative == "Alpha narrative.\n\n- a bullet"
        assert fragment.none_reason and "migrated" in fragment.none_reason
        gamma = change_fragments.check_fragment_text(texts["gamma"], Path("gamma.md"))
        assert gamma.ok and gamma.fragment.type == "fix"

    @pytest.mark.parametrize("legacy, normalised", [("feat", "feature"), ("bugfix", "fix"), ("improvement", "feature")])
    def test_type_synonyms_are_normalised(self, legacy, normalised):
        log = PREAMBLE + _entry("2026-10-19: t", f"type={legacy} | scope=s")
        (_scope, text), = change_fragments.legacy_entries_as_fragments(log).fragments
        assert change_fragments.check_fragment_text(text, Path("s.md")).fragment.type == normalised

    @pytest.mark.parametrize(
        "title",
        ["closes #1020 and #1021", "[bracketed] title ends]", '"quoted" start', "a 'single' and \"double\" #1"],
    )
    def test_a_title_reads_back_exactly(self, title):
        log = PREAMBLE + _entry(f"2026-10-19: {title}", "type=fix | scope=s")
        result = change_fragments.legacy_entries_as_fragments(log)
        assert result.refusals == ()
        (_scope, text), = result.fragments
        assert change_fragments.check_fragment_text(text, Path("s.md")).fragment.title == title


#: One legacy entry per refusal code the conversion emits, each refused beside a
#: valid neighbour. `test_change_fragments` checks every code has a row here.
REFUSALS = [
    (_entry("2026-10-19: placeholder", "type=fix | scope=p | release=unreleased"), "unreleased-placeholder"),
    (
        "## 2026-10-19: two lines\n\n<!-- prawduct: type=fix -->\n<!-- prawduct: scope=t -->\n\nBody.\n\n",
        "multi-tag-line",
    ),
    (_entry("2026-10-19: stray", "type=fix | scope=t", "Body.\n\n<!-- prawduct: scope=u -->"), "multi-tag-line"),
    (_entry("2026-10-19: conflict", "type=fix | scope=a | scope=b"), "conflicting-tags"),
    (_entry("2026-10-19: retired", "type=fix | scope=r | chunks=01"), "unconvertible-key"),
    (_entry("2026-10-19: no scope", "type=fix"), "missing-scope"),
    (_entry("2026-10-19: no type", "scope=nt"), "missing-type"),
    (_entry("no date here", "type=fix | scope=nd"), "bad-header"),
    (_entry("2026-10-19: odd type", "type=methodology | scope=ot"), "bad-type"),
    (_entry("2026-10-19: bad slug", "type=fix | scope=Bad_Slug"), "bad-scope-slug"),
    (_entry("2026-10-19: empty", "type=fix | scope=em", ""), "empty-narrative"),
    (_entry("2026-10-19: one", "type=fix | scope=dup") + _entry("2026-10-18: two", "type=fix | scope=dup"), "duplicate-scope"),
    # Both quote characters and a spaced `#`: no quoting reads it back whole.
    (_entry("2026-10-19: it's \"x\" #1", "type=fix | scope=ur"), "unrepresentable"),
]


class TestRefusals:
    """Each refusal leaves the log as given and converts nothing, even its valid neighbours."""

    @pytest.mark.parametrize("entry, code", REFUSALS, ids=[code for _, code in REFUSALS])
    def test_refused(self, entry, code):
        log = PREAMBLE + _entry("2026-10-20: valid neighbour", "type=fix | scope=ok") + entry
        result = change_fragments.legacy_entries_as_fragments(log)
        assert code in [p.code for p in result.refusals], result.refusals
        assert result.fragments == () and result.remaining == log

    def test_two_pending_entries_sharing_a_scope_are_refused(self):
        log = PREAMBLE + _entry("2026-10-19: one", "type=fix | scope=same") + _entry("2026-10-18: two", "type=fix | scope=same")
        result = change_fragments.legacy_entries_as_fragments(log)
        assert [p.code for p in result.refusals] == ["duplicate-scope"]

    def test_a_shipped_entry_sharing_a_pending_scope_is_not_a_duplicate(self):
        log = PREAMBLE + _entry("2026-10-19: reopen", "type=fix | scope=same") + _entry(
            "2026-10-18: first", "type=fix | scope=same | release=v3.7.1"
        )
        assert [s for s, _ in change_fragments.legacy_entries_as_fragments(log).fragments] == ["same"]


class TestCommand:
    def test_dry_run_writes_nothing(self, tmp_path):
        project = _project(tmp_path, MIXED)
        before = _snapshot(project)
        run = _migrate(project)
        assert run.returncode == 0, run.stderr
        assert ".prawduct/changes/alpha.md" in run.stdout and "Nothing was written" in run.stdout
        assert _snapshot(project) == before

    def test_apply_writes_fragments_and_the_release_gate_sees_the_same_pending_set(self, tmp_path):
        project = _project(tmp_path, MIXED)
        before = release_readiness.pending_scopes(project)
        assert before.legacy_scopes and not before.fragment_scopes
        run = _migrate(project, "--apply")
        assert run.returncode == 0, run.stderr
        after = release_readiness.pending_scopes(project)
        assert after.refusals == [] and after.read_error is None
        assert sorted(after.fragment_scopes) == sorted(before.legacy_scopes) == ["alpha", "gamma"]
        assert after.legacy_scopes == []
        assert all(f.ok for f in change_fragments.load_pending(project))

    def test_a_second_run_is_a_no_op(self, tmp_path):
        project = _project(tmp_path, MIXED)
        assert _migrate(project, "--apply").returncode == 0
        after_first = _snapshot(project)
        run = _migrate(project, "--apply")
        assert run.returncode == 0 and "nothing to do" in run.stdout
        assert _snapshot(project) == after_first

    def test_no_log_is_nothing_to_do(self, tmp_path):
        project = _project(tmp_path, None)
        run = _migrate(project, "--apply")
        assert run.returncode == 0 and "nothing to do" in run.stdout

    def test_a_refusal_exits_1_and_writes_nothing(self, tmp_path):
        project = _project(tmp_path, MIXED + _entry("2026-10-15: placeholder", "type=fix | scope=p | release=unreleased"))
        before = _snapshot(project)
        run = _migrate(project, "--apply")
        assert run.returncode == 1
        assert "unreleased-placeholder" in run.stderr and "Nothing was written" in run.stderr
        assert _snapshot(project) == before

    def test_an_existing_fragment_for_a_converted_scope_is_refused(self, tmp_path):
        project = _project(tmp_path, MIXED)
        existing = project / ".prawduct" / "changes" / "alpha.md"
        existing.parent.mkdir(parents=True)
        existing.write_text("hand-written\n")
        before = _snapshot(project)
        run = _migrate(project, "--apply")
        assert run.returncode == 1 and "fragment-exists" in run.stderr
        assert _snapshot(project) == before

    def test_an_ignored_fragment_directory_is_refused_when_the_log_is_tracked(self, tmp_path):
        project = _project(tmp_path, MIXED)
        (project / ".gitignore").write_text(".prawduct/changes/\n")
        git = ["git", "-C", str(project), "-c", "user.email=t@t", "-c", "user.name=t"]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "add", "-A"], check=True)
        subprocess.run([*git, "commit", "-qm", "init"], check=True)
        before = _snapshot(project)
        run = _migrate(project, "--apply")
        assert run.returncode == 1 and "fragments-ignored" in run.stderr
        assert _snapshot(project) == before

    def test_an_unknown_token_is_a_usage_error(self, tmp_path):
        project = _project(tmp_path, MIXED)
        assert _migrate(project, "--aply").returncode == 2

    def test_plan_migration_writes_the_log_last(self, tmp_path):
        project = _project(tmp_path, MIXED)
        writes = change_migrate.plan_migration(project)
        assert writes[-1][0] == project / ".prawduct" / "change-log.md"
        assert [p.name for p, _ in writes[:-1]] == ["alpha.md", "gamma.md", ".gitkeep"]

    def test_the_fragment_directory_outlives_a_release_that_ships_every_fragment(self, tmp_path):
        project = _project(tmp_path, MIXED)
        assert _migrate(project, "--apply").returncode == 0
        keep = project / ".prawduct" / "changes" / ".gitkeep"
        assert keep.is_file()
        for fragment in (project / ".prawduct" / "changes").glob("*.md"):
            fragment.unlink()  # what the cut does to every shipped fragment
        git = ["git", "-C", str(project), "-c", "user.email=t@t", "-c", "user.name=t"]
        subprocess.run([*git, "init", "-q"], check=True)
        subprocess.run([*git, "add", "-A"], check=True)
        tracked = subprocess.run([*git, "ls-files"], check=True, capture_output=True, text=True).stdout
        assert ".prawduct/changes/.gitkeep" in tracked.splitlines()
