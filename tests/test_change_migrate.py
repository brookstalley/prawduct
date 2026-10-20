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

    @pytest.mark.parametrize(
        "legacy, normalised",
        [("feat", "feature"), ("bugfix", "fix"), ("improvement", "feature"), ("tooling", "chore"),
         ("optimization", "perf"), ("debt-paydown", "refactor"), ("documentation", "docs")],
    )
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
    # A union merge's shape: two versions of one entry's tag line, each over prose.
    (_entry("2026-10-19: same scope", "type=fix | scope=t", "Body.\n\n<!-- prawduct: type=feature | scope=t -->\n\nMore."), "multi-tag-line"),
    # Prose quoting a tag line, then two changes: which the prose belongs to is unknown.
    ("## 2026-10-19: inline\n\nSee <!-- prawduct: type=fix | scope=t --> here.\n\n<!-- prawduct: type=fix | scope=u -->\n\nB.\n\n<!-- prawduct: type=fix | scope=v -->\n\nC.\n\n", "stranded-tag-line"),
    ("## 2026-10-19: inline only\n\nSee <!-- prawduct: type=fix | scope=t --> here.\n\n", "stranded-tag-line"),
    # The shipped section would come back pending, or the pending one stay unseen.
    (_entry("2026-10-19: mixed", "type=fix | scope=t", "A.\n\n<!-- prawduct: type=fix | scope=u | release=v1.0.0 -->\n\nB."), "mixed-release"),
    (_entry("2026-10-19: mixed", "type=fix | scope=t | release=v1.0.0", "A.\n\n<!-- prawduct: type=fix | scope=u -->\n\nB."), "mixed-release"),
    (_entry("2026-10-19: placeholder below", "type=fix | scope=t | release=v1.0.0", "A.\n\n<!-- prawduct: type=fix | scope=u | release=unreleased -->\n\nB."), "unreleased-placeholder"),
    ("## 2026-10-19: prose first\n\nLead.\n\n<!-- prawduct: type=fix | scope=t -->\n\nA.\n\n", "stranded-tag-line"),
    (_entry("2026-10-19: conflict", "type=fix | scope=a | scope=b"), "conflicting-tags"),
    (_entry("2026-10-19: no scope", "type=fix"), "missing-scope"),
    (_entry("2026-10-19: no type", "scope=nt"), "missing-type"),
    (_entry("no date here", "type=fix | scope=nd"), "bad-header"),
    (_entry("2026-10-19: odd type", "type=methodology | scope=ot"), "bad-type"),
    (_entry("2026-10-19: bad slug", "type=fix | scope=Bad_Slug"), "bad-scope-slug"),
    (_entry("2026-10-19: empty", "type=fix | scope=em", ""), "empty-narrative"),
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

    def test_a_shipped_entry_sharing_a_pending_scope_is_not_a_duplicate(self):
        log = PREAMBLE + _entry("2026-10-19: reopen", "type=fix | scope=same") + _entry(
            "2026-10-18: first", "type=fix | scope=same | release=v3.7.1"
        )
        assert [s for s, _ in change_fragments.legacy_entries_as_fragments(log).fragments] == ["same"]

    def test_an_entry_whose_changes_all_shipped_is_history_and_stays(self):
        log = PREAMBLE + _entry(
            "2026-10-19: both shipped", "type=fix | scope=t | release=v1.0.0",
            "A.\n\n<!-- prawduct: type=fix | scope=u | release=v1.0.0 -->\n\nB.",
        )
        result = change_fragments.legacy_entries_as_fragments(log)
        assert result.refusals == () and result.fragments == () and result.remaining == log

    def test_a_shipped_tag_line_below_the_prose_is_history_and_stays(self):
        log = PREAMBLE + "## 2026-10-19: prose first\n\nLead.\n\n<!-- prawduct: type=fix | scope=t | release=v1.0.0 -->\n\n"
        result = change_fragments.legacy_entries_as_fragments(log)
        assert result.refusals == () and result.fragments == () and result.remaining == log


class TestWhatRealLogsCarry:
    """Shapes the onboarded repos' logs hold (dry run over 22 of them, 2026-10-20).

    Renegotiated from refusals: each loses nothing when converted, and refusing
    them left 17 of those repos with no usable migration.
    """

    def test_keys_a_fragment_cannot_hold_move_into_the_narrative(self):
        log = PREAMBLE + _entry("2026-10-19: retired", "type=fix | scope=r | status=shipped | chunks=01, 02 | issues=#5", "Body.")
        result = change_fragments.legacy_entries_as_fragments(log)
        assert result.refusals == ()
        (_scope, text), = result.fragments
        fragment = change_fragments.check_fragment_text(text, Path("r.md")).fragment
        assert fragment.narrative == "Body.\n\nLegacy tags: chunks=01, 02; issues=#5; status=shipped"

    @pytest.mark.parametrize("separator", [" — ", " – ", " - "])
    def test_a_dash_header_reads_like_a_colon_one(self, separator):
        log = PREAMBLE + _entry(f"2026-10-19{separator}Wave 1: done", "type=fix | scope=d")
        (_scope, text), = change_fragments.legacy_entries_as_fragments(log).fragments
        fragment = change_fragments.check_fragment_text(text, Path("d.md")).fragment
        assert (fragment.date, fragment.title) == ("2026-10-19", "Wave 1: done")

    def test_a_hyphenated_title_is_not_split_at_its_hyphen(self):
        log = PREAMBLE + _entry("2026-10-19-follow-up work", "type=fix | scope=h")
        assert [p.code for p in change_fragments.legacy_entries_as_fragments(log).refusals] == ["bad-header"]

    def test_pending_entries_sharing_a_scope_become_its_one_fragment(self):
        log = (
            PREAMBLE
            + _entry("2026-10-19: newest", "type=fix | scope=same", "Second pass.")
            + _entry("2026-10-18: shipped elsewhere", "type=fix | scope=other | release=v1.0.0", "Old.")
            + _entry("2026-10-17: first", "type=feature | scope=same", "First pass.")
        )
        result = change_fragments.legacy_entries_as_fragments(log)
        assert result.refusals == ()
        (scope, text), = result.fragments
        fragment = change_fragments.check_fragment_text(text, Path("same.md")).fragment
        assert (scope, fragment.date, fragment.title, fragment.type) == ("same", "2026-10-19", "newest", "fix")
        assert fragment.narrative == (
            "### 2026-10-19: newest\n\nSecond pass.\n\n"
            "### 2026-10-17: first\n\nFirst pass.\n\nLegacy tags: type=feature"
        )
        assert "scope=same" not in result.remaining and "scope=other" in result.remaining

    def test_an_entry_holding_several_changes_becomes_one_fragment_each(self):
        # cordyceps' shape: one header, each change a tag line over its own paragraph.
        log = PREAMBLE + _entry(
            "2026-10-19: two fixes", "type=bugfix | scope=first | status=merged",
            "First why.\n\n<!-- prawduct: type=docs | scope=second -->\n\nSecond why.",
        )
        result = change_fragments.legacy_entries_as_fragments(log)
        assert result.refusals == ()
        fragments = {
            scope: change_fragments.check_fragment_text(text, Path(f"{scope}.md")).fragment
            for scope, text in result.fragments
        }
        assert {s: (f.type, f.title, f.narrative) for s, f in fragments.items()} == {
            "first": ("fix", "two fixes", "First why.\n\nLegacy tags: status=merged"),
            "second": ("docs", "two fixes", "Second why."),
        }
        assert result.split == ("second",)
        assert result.remaining == PREAMBLE.rstrip("\n") + "\n"

    def test_a_separated_change_merges_with_its_scope_elsewhere_and_takes_the_default(self):
        # faidh's shape: no types, and a separated scope another entry also holds.
        log = (
            PREAMBLE
            + _entry("2026-10-19: chunk", "chunks=26 | scope=a", "A why.\n\n<!-- prawduct: scope=b -->\n\nB why.")
            + _entry("2026-10-18: earlier", "type=fix | scope=b", "B before.")
        )
        assert [p.code for p in change_fragments.legacy_entries_as_fragments(log).refusals] == ["missing-type"]
        result = change_fragments.legacy_entries_as_fragments(log, default_type="chore")
        assert result.refusals == () and result.defaulted == (("a", ""),)
        fragments = dict(result.fragments)
        b = change_fragments.check_fragment_text(fragments["b"], Path("b.md")).fragment
        assert b.type == "fix"
        assert result.split == ()  # `b` was already pending, under its own entry
        assert b.narrative == "### 2026-10-19: chunk\n\nB why.\n\n### 2026-10-18: earlier\n\nB before."

    @pytest.mark.parametrize("tags, legacy", [("scope=u", ""), ("type=mixed | scope=u", "mixed")])
    def test_a_default_type_is_one_named_decision(self, tags, legacy):
        log = PREAMBLE + _entry("2026-10-19: untyped", tags)
        assert change_fragments.legacy_entries_as_fragments(log).refusals
        result = change_fragments.legacy_entries_as_fragments(log, default_type="chore")
        (_scope, text), = result.fragments
        assert change_fragments.check_fragment_text(text, Path("u.md")).fragment.type == "chore"
        assert result.defaulted == (("u", legacy),)
        narrative = change_fragments.check_fragment_text(text, Path("u.md")).fragment.narrative
        assert narrative.endswith("Legacy tags: type=mixed") == bool(legacy)

    def test_an_older_entrys_valid_type_wins_over_the_default(self):
        log = PREAMBLE + _entry("2026-10-19: untyped", "scope=m") + _entry("2026-10-17: typed", "type=perf | scope=m")
        result = change_fragments.legacy_entries_as_fragments(log, default_type="chore")
        (_scope, text), = result.fragments
        assert change_fragments.check_fragment_text(text, Path("m.md")).fragment.type == "perf"
        assert result.defaulted == ()

    def test_a_typed_entry_never_takes_the_default(self):
        log = PREAMBLE + _entry("2026-10-19: typed", "type=bugfix | scope=t")
        result = change_fragments.legacy_entries_as_fragments(log, default_type="chore")
        (_scope, text), = result.fragments
        assert change_fragments.check_fragment_text(text, Path("t.md")).fragment.type == "fix"
        assert result.defaulted == ()


class TestCommand:
    def test_untyped_entries_name_the_flag_and_the_flag_lists_each_guess(self, tmp_path):
        project = _project(tmp_path, MIXED + _entry("2026-10-15: untyped", "scope=u"))
        before = _snapshot(project)
        refused = _migrate(project, "--apply")
        assert refused.returncode == 1 and "--default-type TYPE" in refused.stderr
        assert _snapshot(project) == before
        dry = _migrate(project, "--default-type", "chore")
        assert dry.returncode == 0, dry.stderr
        assert "u: type=chore (was untyped)" in dry.stdout
        assert _snapshot(project) == before
        assert _migrate(project, "--default-type", "chore", "--apply").returncode == 0
        assert (project / ".prawduct" / "changes" / "u.md").is_file()

    @pytest.mark.parametrize("args", [["--default-type"], ["--default-type", "tooling"]])
    def test_a_default_type_outside_the_closed_set_is_a_usage_error(self, tmp_path, args):
        assert _migrate(_project(tmp_path, MIXED), *args).returncode == 2

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

    def test_separated_changes_are_named_and_join_the_pending_set(self, tmp_path):
        several = _entry(
            "2026-10-15: two", "type=fix | scope=delta", "D.\n\n<!-- prawduct: type=fix | scope=epsilon -->\n\nE."
        )
        project = _project(tmp_path, MIXED + several)
        before = release_readiness.pending_scopes(project)
        assert sorted(before.legacy_scopes) == ["alpha", "delta", "gamma"]
        dry = _migrate(project)
        assert dry.returncode == 0, dry.stderr
        assert "epsilon: recorded under another change's header" in dry.stdout and "delta: recorded" not in dry.stdout
        assert _migrate(project, "--apply").returncode == 0
        after = release_readiness.pending_scopes(project)
        assert sorted(after.fragment_scopes) == ["alpha", "delta", "epsilon", "gamma"]

    def test_a_second_run_is_a_no_op(self, tmp_path):
        project = _project(tmp_path, MIXED)
        assert _migrate(project, "--apply").returncode == 0
        after_first = _snapshot(project)
        run = _migrate(project, "--apply")
        assert run.returncode == 0 and "nothing to do" in run.stdout
        assert _snapshot(project) == after_first

    def test_a_log_with_nothing_pending_still_adopts_fragments(self, tmp_path):
        shipped = PREAMBLE + _entry("2026-10-18: shipped fix", "type=fix | scope=beta | release=v3.7.1", "Beta shipped.")
        project = _project(tmp_path, shipped)
        dry = _migrate(project)
        assert dry.returncode == 0 and ".prawduct/changes/.gitkeep" in dry.stdout
        assert not (project / ".prawduct" / "changes").exists()
        assert _migrate(project, "--apply").returncode == 0
        assert (project / ".prawduct" / "changes" / ".gitkeep").is_file()
        assert (project / ".prawduct" / "change-log.md").read_text() == shipped
        again = _migrate(project, "--apply")
        assert again.returncode == 0 and "nothing to do" in again.stdout

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
        writes, _defaulted, _split = change_migrate.plan_migration(project)
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


class TestInstallPin:
    """A clone pinned to a pre-fragment release must not be stranded by the migration."""

    def _pinned(self, tmp_path: Path, ref: str | None) -> Path:
        import json

        project = _project(tmp_path, MIXED)
        if ref is not None:
            settings = project / ".claude" / "settings.json"
            settings.parent.mkdir()
            settings.write_text(json.dumps({
                "extraKnownMarketplaces": {"prawduct": {"source": {"source": "github", "repo": "brookstalley/prawduct", "ref": ref}}}
            }))
        return project

    def test_the_first_release_with_fragment_readers_is_pinned(self):
        # A historical fact, pinned absolutely: v3.7.2 is the first release whose
        # readers accept fragments (wave 1 of #1012).
        assert change_migrate.FRAGMENT_READERS_RELEASE == (3, 7, 2)

    @pytest.mark.parametrize("ref", ["v3.7.1", "3.6.0", "v2.9.10"])
    def test_an_older_pinned_release_is_refused(self, tmp_path, ref):
        project = self._pinned(tmp_path, ref)
        before = _snapshot(project)
        run = _migrate(project, "--apply")
        assert run.returncode == 1 and "plugin-pin-too-old" in run.stderr and ref in run.stderr
        assert _snapshot(project) == before

    @pytest.mark.parametrize("ref", ["main", "develop", "v3.7.2", "v3.10.0", "4.0.0", "0123abcd", None])
    def test_a_branch_a_newer_release_or_no_reference_passes(self, tmp_path, ref):
        assert _migrate(self._pinned(tmp_path, ref), "--apply").returncode == 0
