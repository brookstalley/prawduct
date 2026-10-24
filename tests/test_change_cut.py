"""Tests for `lib/change_cut.py` — the release cut over change fragments (#1012).

The cut writes history that is never edited afterwards, so the tests pin what a
cut must never do as much as what it does: write anything when it refuses, ship
a withheld or unclassified scope, duplicate an entry or a note on a re-run, or
lose a fragment that the archive does not hold.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

_PLUGIN = Path(__file__).resolve().parent.parent / "plugin"
if str(_PLUGIN) not in sys.path:
    sys.path.insert(0, str(_PLUGIN))

from lib import change_cut, change_log, change_log_archive, core, release_readiness  # noqa: E402

HOOK = _PLUGIN / "bin" / "prawduct-hook"
DIGEST = "plugin/CHANGELOG.md"
HEADLINE = "**This release does three things.** And says so in one line."


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _fragment(scope: str, *, note: str | None = None, date: str = "2026-10-19") -> str:
    note = note if note is not None else f"The {scope} change, for users."
    return (
        f"---\nschema: 1\ntype: fix\nscope: {scope}\ndate: {date}\ntitle: {scope} title\n---\n"
        f"What {scope} changed.\n\n## Consumer note\n{note}\n"
    )


def _project(tmp_path: Path, *, fragments: dict[str, str], table: str | None, digest: str | None = None) -> Path:
    project = tmp_path / "proj"
    _write(project / ".prawduct" / "change-log.md", "# Change Log\n\n")
    for scope, text in fragments.items():
        _write(project / ".prawduct" / "changes" / f"{scope}.md", text)
    if table is not None:
        _write(
            project / ".prawduct" / "artifacts" / "release-plan-v3.8.0.md",
            "# Release plan\n\n## Release classification\n\n| Scope | Disposition | Blocker |\n|---|---|---|\n"
            + table,
        )
    if digest is not None:
        _write(project / DIGEST, digest)
    return project


def _digest(body: str = HEADLINE) -> str:
    return f"# Changelog\n\nPreamble.\n\n## v3.8.0-dev\n\n{body}\n\n**`older`**: an older note.\n\n## v3.7.1\n\nOld.\n"


def _snapshot(project: Path) -> dict[str, str]:
    return {
        str(p.relative_to(project)): p.read_text()
        for p in sorted(project.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(project).parts
    }


def _cut(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(HOOK), "cut-change-log", *args],
        cwd=str(project), capture_output=True, text=True, timeout=60,
        env={"PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": str(project), "HOME": str(project.parent)},
    )


class TestApply:
    def test_a_dry_run_writes_nothing(self, tmp_path):
        project = _project(tmp_path, fragments={"alpha": _fragment("alpha")}, table="| alpha | ships | |\n", digest=_digest())
        before = _snapshot(project)
        result = _cut(project, "--release", "v3.8.0")
        assert result.returncode == 0, result.stderr
        assert "1 fragment(s) ship in v3.8.0: alpha" in result.stdout
        assert "Nothing was written" in result.stdout
        assert _snapshot(project) == before

    def test_apply_archives_notes_and_removes(self, tmp_path):
        project = _project(
            tmp_path,
            fragments={"alpha": _fragment("alpha"), "beta": _fragment("beta", note="none: test-only")},
            table="| alpha | ships | |\n| beta | ships | |\n",
            digest=_digest(),
        )
        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 0, result.stderr
        assert "none: beta — test-only" in result.stdout

        bucket = (project / ".prawduct" / "change-log-archive" / "2026-10.md").read_text()
        entries = change_log.parse_change_log(bucket)
        assert sorted(e.tags["scope"] for e in entries) == ["alpha", "beta"]
        assert all(e.tags["release"] == "v3.8.0" for e in entries)
        assert change_log.validate_change_log_tags(entries) == ([], [])

        digest = (project / DIGEST).read_text().splitlines()
        # The note sits under the headline, above the notes already there, and
        # inside the open section. A `none:` note contributes nothing.
        assert digest.index(HEADLINE) < digest.index("**`alpha`**: The alpha change, for users.")
        assert digest.index("**`alpha`**: The alpha change, for users.") < digest.index("**`older`**: an older note.")
        assert not any("beta" in line for line in digest)

        assert not list((project / ".prawduct" / "changes").glob("*.md"))
        # The release gate now reads alpha as shipped in this release, not pending.
        pending = release_readiness.pending_scopes(project)
        assert pending.scopes == []
        history = release_readiness._history_entries(project, pending.entries)
        assert release_readiness.scopes_tagged_for(history, "v3.8.0") >= {"alpha", "beta"}

    def test_withheld_scopes_stay_pending(self, tmp_path):
        project = _project(
            tmp_path,
            fragments={"alpha": _fragment("alpha"), "beta": _fragment("beta")},
            table="| alpha | ships | |\n| beta | withheld | BKL-6J2X |\n",
            digest=_digest(),
        )
        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 0, result.stderr
        assert "kept pending (withheld): beta" in result.stdout
        assert [p.name for p in (project / ".prawduct" / "changes").glob("*.md")] == ["beta.md"]

    def test_named_scopes_cut_exactly_those_without_a_release_plan(self, tmp_path):
        project = _project(tmp_path, fragments={"alpha": _fragment("alpha"), "beta": _fragment("beta")}, table=None)
        result = _cut(project, "--release", "v3.8.0", "--scope", "alpha", "--apply")
        assert result.returncode == 0, result.stderr
        assert "consumer notes: this repo publishes no consumer digest" in result.stdout
        assert [p.name for p in (project / ".prawduct" / "changes").glob("*.md")] == ["beta.md"]

    def test_no_pending_fragment_is_nothing_to_do(self, tmp_path):
        project = _project(tmp_path, fragments={}, table=None)
        result = _cut(project, "--release", "v3.8.0")
        assert result.returncode == 0
        assert "nothing to do" in result.stdout


REFUSALS = [
    ("no-release-plan", {"alpha": _fragment("alpha")}, None, _digest(), ()),
    ("unclassified-fragment", {"alpha": _fragment("alpha"), "beta": _fragment("beta")}, "| alpha | ships | |\n", _digest(), ()),
    ("unknown-scope", {"alpha": _fragment("alpha")}, None, None, ("--scope", "gamma")),
    ("invalid-pending-set", {"alpha": _fragment("alpha").replace("type: fix", "type: bugfix")}, "| alpha | ships | |\n", _digest(), ()),
    # The headline is the open section's first non-empty line (the rule the release
    # gate reads it by), so only a section with no lines at all has none.
    ("no-headline", {"alpha": _fragment("alpha")}, "| alpha | ships | |\n", "# Changelog\n\n## v3.8.0-dev\n\n## v3.7.1\n\nOld.\n", ()),
    ("bad-version", {"alpha": _fragment("alpha")}, "| alpha | ships | |\n", _digest(), ("--release", "unreleased")),
    # The previous release's section still on top: by position it is "open", and
    # writing there would add these notes to notes already published.
    (
        "wrong-section",
        {"alpha": _fragment("alpha")},
        "| alpha | ships | |\n",
        f"# Changelog\n\n## v3.7.1\n\n{HEADLINE}\n\n**`older`**: an older note.\n",
        (),
    ),
    (
        "invalid-pending-set",
        {"alpha": _fragment("alpha").replace("schema: 1", "schema: 1\nrelease: v3.7.0")},
        "| alpha | ships | |\n",
        _digest(),
        (),
    ),
]


@pytest.mark.parametrize("code,fragments,table,digest,extra", REFUSALS, ids=[f"{r[0]}-{i}" for i, r in enumerate(REFUSALS)])
def test_a_refusal_names_its_code_and_writes_nothing(tmp_path, code, fragments, table, digest, extra):
    project = _project(tmp_path, fragments=fragments, table=table, digest=digest)
    before = _snapshot(project)
    args = list(extra) if "--release" in extra else ["--release", "v3.8.0", *extra]
    result = _cut(project, *args, "--apply")
    assert result.returncode == 1
    assert f"refused: {code}:" in result.stderr
    assert _snapshot(project) == before


class TestRecovery:
    def test_a_failed_write_restores_everything_and_keeps_the_fragments(self, tmp_path, monkeypatch):
        project = _project(tmp_path, fragments={"alpha": _fragment("alpha")}, table="| alpha | ships | |\n", digest=_digest())
        before = _snapshot(project)
        plan = change_cut.plan_cut(project, "v3.8.0")

        def failing(writes):
            raise OSError("disk full")

        monkeypatch.setattr(core, "write_all_or_none", failing)
        with pytest.raises(OSError):
            change_cut.apply_cut(plan)
        assert _snapshot(project) == before

    def test_a_rerun_after_an_interrupted_removal_duplicates_nothing(self, tmp_path):
        project = _project(tmp_path, fragments={"alpha": _fragment("alpha")}, table="| alpha | ships | |\n", digest=_digest())
        plan = change_cut.plan_cut(project, "v3.8.0")
        (project / ".prawduct" / "change-log-archive").mkdir()
        core.write_all_or_none(plan.writes)  # the writes landed; the removal never ran
        assert (project / ".prawduct" / "changes" / "alpha.md").exists()

        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 0, result.stderr
        bucket = (project / ".prawduct" / "change-log-archive" / "2026-10.md").read_text()
        assert len(change_log.parse_change_log(bucket)) == 1
        assert (project / DIGEST).read_text().count("**`alpha`**:") == 1
        assert not (project / ".prawduct" / "changes" / "alpha.md").exists()


def test_two_branches_adding_fragments_merge_without_a_union_driver(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
            cwd=str(repo), capture_output=True, text=True, timeout=15,
        )

    git("init", "-q", "-b", "main")
    _write(repo / "app.py", "x = 1\n")
    git("add", "-A")
    git("commit", "-qm", "base")
    assert not (repo / ".gitattributes").exists()
    for scope in ("alpha", "beta"):
        git("checkout", "-q", "-b", scope, "main")
        _write(repo / ".prawduct" / "changes" / f"{scope}.md", _fragment(scope))
        git("add", "-A")
        git("commit", "-qm", scope)
    git("checkout", "-q", "main")
    assert git("merge", "-q", "--no-ff", "-m", "a", "alpha").returncode == 0
    merged = git("merge", "-q", "--no-ff", "-m", "b", "beta")
    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert sorted(p.name for p in (repo / ".prawduct" / "changes").glob("*.md")) == ["alpha.md", "beta.md"]


def test_the_cut_writes_the_bucket_archive_change_log_writes_for_the_same_entry(tmp_path):
    """Byte-identical history either way (#1012 Chunk 03 acceptance).

    The same change recorded two ways: once as a legacy entry, hand-written in
    the log's grammar and moved by `archive-change-log`'s selection and apply,
    and once as a fragment the cut ships. The two month files must be equal byte
    for byte, so history does not depend on which shape a change was recorded in.
    """
    legacy_entry = (
        "## 2026-10-19: alpha title\n\n"
        "<!-- prawduct: type=fix | scope=alpha | release=v3.8.0 -->\n\n"
        "What alpha changed.\n\n"
        "**Consumer note:**\n\n"
        "The alpha change, for users.\n"
    )
    legacy = tmp_path / "legacy"
    _write(legacy / ".prawduct" / "change-log.md", "# Change Log\n\n" + legacy_entry)
    selection = change_log_archive.select(
        (legacy / ".prawduct" / "change-log.md").read_text(), threshold=0, versions=True
    )
    change_log_archive.apply(legacy / ".prawduct", selection)
    by_archive = (legacy / ".prawduct" / "change-log-archive" / "2026-10.md").read_bytes()

    project = _project(tmp_path, fragments={"alpha": _fragment("alpha")}, table="| alpha | ships | |\n")
    assert _cut(project, "--release", "v3.8.0", "--apply").returncode == 0
    by_cut = (project / ".prawduct" / "change-log-archive" / "2026-10.md").read_bytes()
    assert by_cut == by_archive


def test_a_cut_refuses_when_git_would_ignore_the_archive(tmp_path):
    project = _project(tmp_path, fragments={"alpha": _fragment("alpha")}, table="| alpha | ships | |\n")
    _write(project / ".gitignore", ".prawduct/change-log-archive/\n")
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "base"]):
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
            cwd=str(project), capture_output=True, check=True, timeout=15,
        )
    before = _snapshot(project)
    result = _cut(project, "--release", "v3.8.0", "--apply")
    assert result.returncode == 1
    assert "refused: archive-ignored:" in result.stderr
    assert _snapshot(project) == before


def test_a_failed_removal_says_the_history_is_written(tmp_path, monkeypatch, capsys):
    project = _project(tmp_path, fragments={"alpha": _fragment("alpha")}, table="| alpha | ships | |\n")

    def refuse(self, *args, **kwargs):
        raise PermissionError("read-only")

    monkeypatch.setattr(Path, "unlink", refuse)
    assert change_cut.cut_cmd(project, ["--release", "v3.8.0", "--apply"]) == 1
    err = capsys.readouterr().err
    assert "refused: removal-failed:" in err
    assert "archive and notes are written" in err
    assert (project / ".prawduct" / "change-log-archive" / "2026-10.md").exists()


def _git_commit_all(project: Path) -> None:
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "base"]):
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
            cwd=str(project), capture_output=True, check=True, timeout=15,
        )


class TestAFragmentsOnlyRepo:
    """A repo that records changes as fragments and has no live log at all,
    which is what `init-product` scaffolds."""

    def _project(self, tmp_path: Path) -> Path:
        project = _project(tmp_path, fragments={"alpha": _fragment("alpha")}, table="| alpha | ships | |\n")
        (project / ".prawduct" / "change-log.md").unlink()
        return project

    def test_a_cut_refuses_when_only_the_fragments_are_tracked_and_the_archive_is_ignored(self, tmp_path):
        project = self._project(tmp_path)
        _write(project / ".gitignore", ".prawduct/*\n!.prawduct/changes/\n")
        _git_commit_all(project)
        before = _snapshot(project)
        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 1
        assert "refused: archive-ignored:" in result.stderr
        assert _snapshot(project) == before

    def test_the_same_repo_cuts_once_the_archive_is_tracked(self, tmp_path):
        project = self._project(tmp_path)
        _write(project / ".gitignore", ".prawduct/*\n!.prawduct/changes/\n!.prawduct/change-log-archive/\n")
        _git_commit_all(project)
        assert _cut(project, "--release", "v3.8.0", "--apply").returncode == 0

    def test_history_readers_see_what_the_cut_shipped(self, tmp_path):
        from lib import plan_backfill, record_lint, release_readiness

        project = self._project(tmp_path)
        _write(
            project / ".prawduct" / "artifacts" / "build-plan-alpha.md",
            "---\nartifact: build-plan\nscope: alpha\n---\n\n## Status\n\n- [x] Chunk 01: done\n",
        )
        assert _cut(project, "--release", "v3.8.0", "--apply").returncode == 0
        assert not (project / ".prawduct" / "change-log.md").exists()

        history = release_readiness._history_entries(project, [])
        assert release_readiness.scopes_tagged_for(history, "v3.8.0") == {"alpha"}
        shipped = plan_backfill.survey(project / ".prawduct")["shipped"]
        assert [(i["scope"], i["release"]) for i in shipped] == [("alpha", "v3.8.0")]
        assert record_lint._scope_declared_in_change_log(project / ".prawduct", "alpha") is True
        assert record_lint._scope_declared_in_change_log(project / ".prawduct", "nope") is False
