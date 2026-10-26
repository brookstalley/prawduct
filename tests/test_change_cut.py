"""Tests for `lib/change_cut.py` — the release cut over change fragments (#1012, #733).

The cut writes history that is never edited afterwards, so the tests pin what a
cut must never do as much as what it does: write anything when it refuses, ship
a withheld or unclassified scope, duplicate an entry or a note on a re-run, or
lose a fragment that the archive does not hold. Where a repo declares
`consumer_digest:`, it also writes the release file and inserts the same lines
into the declared changelog without touching any other byte of it.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

_PLUGIN = Path(__file__).resolve().parent.parent / "plugin"
if str(_PLUGIN) not in sys.path:
    sys.path.insert(0, str(_PLUGIN))

from lib import change_cut, change_log, change_log_archive, core, release_readiness  # noqa: E402

HOOK = _PLUGIN / "bin" / "prawduct-hook"
DIGEST = "plugin/CHANGELOG.md"
HEADLINE = "**This release does three things.** And says so in one line."
HEADLINE_FILE = ".prawduct/release-headline.md"
RELEASE_FILE = ".prawduct/releases/v3.8.0.md"

#: Prawduct's own declaration (CD11).
PRAWDUCT_DECL = (
    'consumer_digest:\n  path: plugin/CHANGELOG.md\n  heading: "## {version}"\n'
    "  headline: required\n  layout: paragraphs\n"
)
#: The changelog after the last release, with no section open for the next one.
CHANGELOG = "# Changelog\n\nPreamble.\n\n## v3.7.1\n\nOld.\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _fragment(scope: str, *, note: str | None = None, date: str = "2026-10-19", title: str | None = None) -> str:
    note = note if note is not None else f"The {scope} change, for users."
    title = title if title is not None else f"{scope} title"
    return (
        f"---\nschema: 1\ntype: fix\nscope: {scope}\ndate: {date}\ntitle: {title}\n---\n"
        f"What {scope} changed.\n\n## Consumer note\n{note}\n"
    )


def _project(
    tmp_path: Path,
    *,
    fragments: dict[str, str],
    table: str | None,
    digest: str | bytes | None = None,
    decl: str | None = None,
    headline: str | bytes | None = None,
) -> Path:
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
        (project / DIGEST).parent.mkdir(parents=True, exist_ok=True)
        if isinstance(digest, bytes):
            (project / DIGEST).write_bytes(digest)
        else:
            _write(project / DIGEST, digest)
    if decl is not None:
        _write(project / ".prawduct" / "project-state.yaml", decl)
    if headline is not None:
        path = project / HEADLINE_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(headline if isinstance(headline, bytes) else headline.encode())
    return project


def _declared(tmp_path: Path, *, fragments: dict[str, str], table: str | None = None, **kw) -> Path:
    """Prawduct's own shape: declared, headline in its file, no open section."""
    kw.setdefault("digest", CHANGELOG)
    kw.setdefault("decl", PRAWDUCT_DECL)
    kw.setdefault("headline", HEADLINE + "\n")
    return _project(tmp_path, fragments=fragments, table=table, **kw)


def _snapshot(project: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(project)): p.read_bytes()
        for p in sorted(project.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(project).parts
    }


def _cut(project: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(HOOK), "cut-change-log", *args],
        cwd=str(project), capture_output=True, text=True, timeout=60,
        env={"PATH": "/usr/bin:/bin", "CLAUDE_PROJECT_DIR": str(project), "HOME": str(project.parent)},
    )


def _preview(stdout: str) -> str:
    """The dry run's section block, the text between its two marker lines."""
    lines = stdout.splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if line.startswith("--- section (as written to "))
    end = next(i for i, line in enumerate(lines) if line.rstrip("\n") == "--- end ---")
    return "".join(lines[start + 1 : end])


def _git_commit_all(project: Path) -> None:
    for args in (["init", "-q"], ["add", "-A"], ["commit", "-qm", "base"]):
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
            cwd=str(project), capture_output=True, check=True, timeout=15,
        )


class TestApply:
    def test_a_dry_run_writes_nothing_and_previews_the_section(self, tmp_path):
        project = _declared(tmp_path, fragments={"alpha": _fragment("alpha")}, table="| alpha | ships | |\n")
        before = _snapshot(project)
        result = _cut(project, "--release", "v3.8.0")
        assert result.returncode == 0, result.stderr
        assert "1 fragment(s) ship in v3.8.0: alpha" in result.stdout
        assert f"--- section (as written to {RELEASE_FILE}) ---" in result.stdout
        assert "Nothing was written" in result.stdout
        assert _snapshot(project) == before

    def test_apply_archives_writes_the_release_file_inserts_it_and_removes(self, tmp_path):
        project = _declared(
            tmp_path,
            fragments={"alpha": _fragment("alpha"), "beta": _fragment("beta", note="none: test-only")},
            table="| alpha | ships | |\n| beta | ships | |\n",
        )
        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 0, result.stderr
        assert "none: beta — test-only" in result.stdout
        assert f"consumer notes: 1 written to {DIGEST} as a new section at line 5 (release file {RELEASE_FILE})" in result.stdout

        bucket = (project / ".prawduct" / "change-log-archive" / "2026-10.md").read_text()
        entries = change_log.parse_change_log(bucket)
        assert sorted(e.tags["scope"] for e in entries) == ["alpha", "beta"]
        assert all(e.tags["release"] == "v3.8.0" for e in entries)
        assert change_log.validate_change_log_tags(entries) == ([], [])

        digest = (project / DIGEST).read_text().splitlines()
        # A new section above the last release's, its headline first; a `none:`
        # note contributes nothing.
        assert digest.index("## v3.8.0") < digest.index(HEADLINE) < digest.index(
            "**`alpha`**: The alpha change, for users."
        ) < digest.index("## v3.7.1")
        assert not any("beta" in line for line in digest)
        assert (project / RELEASE_FILE).read_text() == f"## v3.8.0\n\n{HEADLINE}\n\n**`alpha`**: The alpha change, for users.\n"

        assert not list((project / ".prawduct" / "changes").glob("*.md"))
        assert not (project / HEADLINE_FILE).exists()
        # The release gate now reads alpha as shipped in this release, not pending.
        pending = release_readiness.pending_scopes(project)
        assert pending.scopes == []
        history = release_readiness._history_entries(project, pending.entries)
        assert release_readiness.scopes_tagged_for(history, "v3.8.0") >= {"alpha", "beta"}

    def test_withheld_scopes_stay_pending(self, tmp_path):
        project = _declared(
            tmp_path,
            fragments={"alpha": _fragment("alpha"), "beta": _fragment("beta")},
            table="| alpha | ships | |\n| beta | withheld | BKL-6J2X |\n",
        )
        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 0, result.stderr
        assert "kept pending (withheld): beta" in result.stdout
        assert [p.name for p in (project / ".prawduct" / "changes").glob("*.md")] == ["beta.md"]
        assert "beta" not in (project / RELEASE_FILE).read_text()

    def test_named_scopes_cut_exactly_those_without_a_release_plan(self, tmp_path):
        project = _project(tmp_path, fragments={"alpha": _fragment("alpha"), "beta": _fragment("beta")}, table=None)
        result = _cut(project, "--release", "v3.8.0", "--scope", "alpha", "--apply")
        assert result.returncode == 0, result.stderr
        assert [p.name for p in (project / ".prawduct" / "changes").glob("*.md")] == ["beta.md"]

    def test_no_pending_fragment_is_nothing_to_do(self, tmp_path):
        project = _project(tmp_path, fragments={}, table=None)
        result = _cut(project, "--release", "v3.8.0")
        assert result.returncode == 0
        assert "nothing to do" in result.stdout

    def test_a_declared_repo_with_nothing_pending_writes_no_release_file(self, tmp_path):
        project = _declared(tmp_path, fragments={}, table=None)
        before = _snapshot(project)
        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 0, result.stderr
        assert "nothing to do" in result.stdout
        assert _snapshot(project) == before

    def test_a_headline_file_is_used_and_consumed_when_the_declaration_does_not_require_one(self, tmp_path):
        project = _declared(
            tmp_path, fragments={"alpha": _fragment("alpha")}, table="| alpha | ships | |\n",
            decl=PRAWDUCT_DECL.replace("headline: required", "headline: none"),
        )
        assert _cut(project, "--release", "v3.8.0", "--apply").returncode == 0
        assert (project / RELEASE_FILE).read_text().splitlines()[:3] == ["## v3.8.0", "", HEADLINE]
        assert not (project / HEADLINE_FILE).exists()

    def test_every_parent_directory_is_created(self, tmp_path):
        """The archive, the release file and the changelog each sit in a directory
        a first cut may have to create."""
        project = _declared(
            tmp_path, fragments={"alpha": _fragment("alpha")}, table="| alpha | ships | |\n",
            decl=PRAWDUCT_DECL.replace("plugin/CHANGELOG.md", "docs/notes/CHANGELOG.md"),
        )
        _write(project / "docs" / "notes" / "CHANGELOG.md", CHANGELOG)
        assert not (project / ".prawduct" / "releases").exists()
        assert not (project / ".prawduct" / "change-log-archive").exists()
        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 0, result.stderr
        assert (project / RELEASE_FILE).is_file()
        assert (project / ".prawduct" / "change-log-archive" / "2026-10.md").is_file()


class TestTheOutput:
    def test_the_undeclared_line_names_the_key_and_where_it_goes(self, tmp_path):
        project = _project(tmp_path, fragments={"alpha": _fragment("alpha")}, table="| alpha | ships | |\n", digest=CHANGELOG)
        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 0, result.stderr
        line = next(line for line in result.stdout.splitlines() if "consumer notes:" in line)
        assert line == (
            "  consumer notes: this repo declares no consumer_digest:, so the notes stay in the archive entries. "
            "Declare consumer_digest: in .prawduct/project-state.yaml to have the cut write them to your changelog"
        )
        # Undeclared: no release file and no changelog write, even with a changelog present.
        assert not (project / ".prawduct" / "releases").exists()
        assert (project / DIGEST).read_text() == CHANGELOG

    def test_the_legacy_line_appears_only_when_legacy_entries_ship(self, tmp_path):
        legacy = (
            "# Change Log\n\n## 2026-10-18: legacy thing\n\n"
            "<!-- prawduct: type=fix | scope=oldway -->\n\nBody.\n"
        )
        line = "  legacy entries carry no consumer note; /prawduct:doctor offers the move to fragments"
        shipping = _declared(
            tmp_path / "a", fragments={"alpha": _fragment("alpha")},
            table="| alpha | ships | |\n| oldway | ships | |\n",
        )
        _write(shipping / ".prawduct" / "change-log.md", legacy)
        out = _cut(shipping, "--release", "v3.8.0")
        assert out.returncode == 0, out.stderr
        assert line in out.stdout.splitlines()

        withheld = _declared(
            tmp_path / "b", fragments={"alpha": _fragment("alpha")},
            table="| alpha | ships | |\n| oldway | withheld | BKL-6J2X |\n",
        )
        _write(withheld / ".prawduct" / "change-log.md", legacy)
        out = _cut(withheld, "--release", "v3.8.0")
        assert out.returncode == 0, out.stderr
        assert line not in out.stdout.splitlines()

    def test_the_dry_run_section_is_the_release_file_apply_writes(self, tmp_path):
        project = _declared(
            tmp_path,
            fragments={
                "alpha": _fragment("alpha", note="Two lines.\nSecond."),
                "gamma": _fragment("gamma", date="2026-10-21"),
            },
            table="| alpha | ships | |\n| gamma | ships | |\n",
        )
        dry = _cut(project, "--release", "v3.8.0")
        assert dry.returncode == 0, dry.stderr
        preview = _preview(dry.stdout)
        assert preview.startswith("## v3.8.0\n")
        applied = _cut(project, "--release", "v3.8.0", "--apply")
        assert applied.returncode == 0, applied.stderr
        assert (project / RELEASE_FILE).read_text() == preview
        assert "--- section" not in applied.stdout


# ---------------------------------------------------------------------------
# Refusals: each names its code, writes nothing, and leaves the fragments
# ---------------------------------------------------------------------------

_ONE = {"alpha": _fragment("alpha")}
_ONE_TABLE = "| alpha | ships | |\n"

#: ``(code, project kwargs, extra args)``. A missing ``decl``/``headline`` key
#: takes `_declared`'s default; ``None`` removes it.
REFUSALS = [
    ("no-release-plan", {"table": None}, ()),
    ("unclassified-fragment", {"fragments": {**_ONE, "beta": _fragment("beta")}}, ()),
    ("unknown-scope", {"table": None}, ("--scope", "gamma")),
    ("invalid-pending-set", {"fragments": {"alpha": _fragment("alpha").replace("type: fix", "type: bugfix")}}, ()),
    ("bad-version", {}, ("--release", "unreleased")),
    (
        "invalid-pending-set",
        {"fragments": {"alpha": _fragment("alpha").replace("schema: 1", "schema: 1\nrelease: v3.7.0")}},
        (),
    ),
    # CD7, each code in turn.
    ("digest-declaration-invalid", {"decl": PRAWDUCT_DECL.replace("layout: paragraphs", "layout: tables")}, ()),
    ("digest-declaration-invalid", {"decl": PRAWDUCT_DECL + "  layout: bullets\n"}, ()),
    ("digest-missing", {"digest": None}, ()),
    ("digest-unreadable", {"digest": b"# Changelog\n\n\xff\xfe not utf-8\n"}, ()),
    ("marker-missing", {"decl": PRAWDUCT_DECL + "  marker: <!-- releases go below -->\n"}, ()),
    # The section-flow golden's starting state, refused under the release-file model.
    ("release-in-changelog", {"digest": f"# Changelog\n\n## v3.8.0\n\n{HEADLINE}\n\n## v3.7.1\n\nOld.\n"}, ()),
    # Keep a Changelog's spelling names the same release.
    ("release-in-changelog", {"digest": "# Changelog\n\n## [3.8.0] - 2026-10-01\n\n- x\n"}, ()),
    # The old model's `no-headline` was an open section with no first line; the
    # headline now lives in its own file, so its absence is what refuses.
    ("no-headline", {"headline": None}, ()),
    ("no-headline", {"headline": "\n  \n\n"}, ()),
]


@pytest.mark.parametrize("code,overrides,extra", REFUSALS, ids=[f"{r[0]}-{i}" for i, r in enumerate(REFUSALS)])
def test_a_refusal_names_its_code_writes_nothing_and_keeps_the_fragments(tmp_path, code, overrides, extra):
    kw = {"fragments": _ONE, "table": _ONE_TABLE, **overrides}
    fragments = kw.pop("fragments")
    project = _declared(tmp_path, fragments=fragments, **kw)
    before = _snapshot(project)
    args = list(extra) if "--release" in extra else ["--release", "v3.8.0", *extra]
    result = _cut(project, *args, "--apply")
    assert result.returncode == 1, result.stdout
    assert f"refused: {code}:" in result.stderr
    assert "Nothing was written." in result.stderr
    assert _snapshot(project) == before
    assert {p.stem for p in (project / ".prawduct" / "changes").glob("*.md")} == set(fragments)


def test_an_invalid_declaration_refuses_even_with_nothing_pending(tmp_path):
    project = _declared(tmp_path, fragments={}, decl="consumer_digest:\n  heading: \"## {version}\"\n")
    before = _snapshot(project)
    result = _cut(project, "--release", "v3.8.0", "--apply")
    assert result.returncode == 1
    assert "refused: digest-declaration-invalid:" in result.stderr
    assert _snapshot(project) == before


def test_release_in_changelog_names_the_line_and_the_way_out(tmp_path):
    project = _declared(
        tmp_path, fragments=_ONE, table=_ONE_TABLE,
        digest=f"# Changelog\n\n## v3.8.0\n\n{HEADLINE}\n\n## v3.7.1\n\nOld.\n",
    )
    result = _cut(project, "--release", "v3.8.0")
    assert result.returncode == 1
    assert "refused: release-in-changelog: plugin/CHANGELOG.md line 3 ('## v3.8.0')" in result.stderr
    assert HEADLINE_FILE in result.stderr


def test_a_published_prerelease_section_does_not_block_the_release(tmp_path):
    """`v3.8.0-rc.1` shipped; its section is history, and `v3.8.0` goes above it."""
    rc = "# Changelog\n\n## v3.8.0-rc.1\n\nPreview.\n\n## v3.7.1\n\nOld.\n"
    project = _declared(tmp_path, fragments=_ONE, table=_ONE_TABLE, digest=rc)
    result = _cut(project, "--release", "v3.8.0", "--apply")
    assert result.returncode == 0, result.stderr
    lines = (project / DIGEST).read_text().splitlines()
    assert lines.index("## v3.8.0") < lines.index("## v3.8.0-rc.1")


def test_a_previous_release_on_top_is_history_and_the_section_goes_above_it(tmp_path):
    """The old model refused this state as `wrong-section`.

    There the cut wrote notes into the topmost section, so a previous release's
    section on top meant adding notes to notes already published. The
    release-file model never writes into an existing section: the cut inserts a
    new one above the newest release, so this is the normal starting state, and
    the hazard `wrong-section` guarded now has `release-in-changelog` as its
    guard (a section already naming THIS release), pinned in REFUSALS.
    """
    old_top = f"# Changelog\n\n## v3.7.1\n\n{HEADLINE}\n\n**`older`**: an older note.\n"
    project = _declared(tmp_path, fragments=_ONE, table=_ONE_TABLE, digest=old_top)
    result = _cut(project, "--release", "v3.8.0", "--apply")
    assert result.returncode == 0, result.stderr
    text = (project / DIGEST).read_text()
    assert text.endswith("## v3.7.1\n\n" + HEADLINE + "\n\n**`older`**: an older note.\n")
    assert text.index("**`alpha`**:") < text.index("## v3.7.1")


def test_a_cut_refuses_when_git_would_ignore_the_release_files(tmp_path):
    project = _declared(tmp_path, fragments=_ONE, table=_ONE_TABLE)
    _write(project / ".gitignore", ".prawduct/releases/\n")
    _git_commit_all(project)
    before = _snapshot(project)
    result = _cut(project, "--release", "v3.8.0", "--apply")
    assert result.returncode == 1
    assert "refused: releases-ignored:" in result.stderr
    assert _snapshot(project) == before
    assert (project / ".prawduct" / "changes" / "alpha.md").exists()


def test_release_files_git_would_ignore_are_no_refusal_where_nothing_is_tracked(tmp_path):
    """Without a tracked record nothing is committed on either side."""
    project = _declared(tmp_path, fragments=_ONE, table=_ONE_TABLE)
    # A real repo that ignores all of `.prawduct/`, so git would ignore the
    # release files and only the untracked record keeps this from refusing.
    _write(project / ".gitignore", ".prawduct/\n")
    _git_commit_all(project)
    probe = subprocess.run(
        ["git", "check-ignore", "-q", RELEASE_FILE], cwd=str(project), capture_output=True, timeout=15
    )
    assert probe.returncode == 0, "the fixture must make git ignore the release file"
    result = _cut(project, "--release", "v3.8.0", "--apply")
    assert result.returncode == 0, result.stderr
    assert (project / RELEASE_FILE).is_file()


# ---------------------------------------------------------------------------
# Bytes outside the inserted span (CD5) on a Keep a Changelog CRLF + BOM file
# ---------------------------------------------------------------------------

KAC_DECL = (
    'consumer_digest:\n  path: CHANGELOG.md\n  heading: "## [{version_no_prefix}] - {date}"\n'
    "  layout: by-type\n"
)
KAC_BYTES = (
    b"\xef\xbb\xbf# Changelog\r\n\r\nAll notable changes.\r\n\r\n## [Unreleased]\r\n\r\n"
    b"## [1.3.0] - 2026-09-01\r\n\r\n### Fixed\r\n\r\n- An old fix.\r\n"
)
#: The design's worked example (733-design.md Section 4).
KAC_SECTION = [
    "## [1.4.0] - 2026-10-25",
    "",
    "### Added",
    "",
    "- Search across projects.",
    "  Results rank by recency.",
    "",
    "### Fixed",
    "",
    "- Login no longer loops on an expired token.",
]


def _kac_project(tmp_path: Path) -> Path:
    project = tmp_path / "kac"
    frag = (
        "---\nschema: 1\ntype: {type}\nscope: {scope}\ndate: 2026-10-20\ntitle: {scope} title\n---\n"
        "What changed.\n\n## Consumer note\n{note}\n"
    )
    for scope, kind, note in (
        ("search", "feature", "Search across projects.\nResults rank by recency."),
        ("login", "fix", "Login no longer loops on an expired token."),
        ("deps", "chore", "none: dependency bump"),
    ):
        _write(project / ".prawduct" / "changes" / f"{scope}.md", frag.format(type=kind, scope=scope, note=note))
    _write(project / ".prawduct" / "project-state.yaml", KAC_DECL)
    (project / "CHANGELOG.md").write_bytes(KAC_BYTES)
    return project


class TestKeepAChangelog:
    def _cut(self, project: Path) -> change_cut.CutPlan:
        plan = change_cut.plan_cut(project, "v1.4.0", ["search", "login", "deps"], today=date(2026, 10, 25))
        change_cut.apply_cut(plan)
        return plan

    def test_the_section_goes_below_unreleased_and_every_other_byte_is_kept(self, tmp_path):
        project = _kac_project(tmp_path)
        plan = self._cut(project)
        after = (project / "CHANGELOG.md").read_bytes()

        split_at = KAC_BYTES.index(b"## [1.3.0]")
        head, tail = KAC_BYTES[:split_at], KAC_BYTES[split_at:]
        assert head.endswith(b"## [Unreleased]\r\n\r\n")
        # The insert sits after a blank line, so it adds none before itself, and
        # one after, to separate it from the release below.
        inserted = b"".join(line.encode() + b"\r\n" for line in KAC_SECTION) + b"\r\n"
        assert after[: len(head)] == head
        assert after[len(head) : len(head) + len(inserted)] == inserted
        assert after[len(head) + len(inserted) :] == tail
        assert after.startswith(b"\xef\xbb\xbf")
        assert plan.insert_line == KAC_BYTES[:split_at].count(b"\n") + 1

    def test_the_release_file_is_the_inserted_lines_in_lf(self, tmp_path):
        project = _kac_project(tmp_path)
        self._cut(project)
        release = (project / ".prawduct" / "releases" / "v1.4.0.md").read_bytes()
        assert release == ("\n".join(KAC_SECTION) + "\n").encode()
        changelog = (project / "CHANGELOG.md").read_bytes().decode("utf-8-sig")
        assert "\r\n".join(release.decode().splitlines()) in changelog

    def test_a_failed_write_leaves_changelog_release_file_and_archive_untouched(self, tmp_path, monkeypatch):
        """The changelog is the last write, so the archive and the release file
        have landed when it fails; the rollback must restore all three."""
        project = _kac_project(tmp_path)
        before = _snapshot(project)
        plan = change_cut.plan_cut(project, "v1.4.0", ["search", "login", "deps"], today=date(2026, 10, 25))
        written = [path for path, _text in plan.writes]
        changelog = project / "CHANGELOG.md"
        assert written[-1] == changelog and project / ".prawduct" / "releases" / "v1.4.0.md" in written
        real = core.atomic_write_text
        landed: list[Path] = []

        def failing(path, text, **kw):
            if Path(path) == changelog:
                raise OSError("disk full")
            landed.append(Path(path))
            return real(path, text, **kw)

        monkeypatch.setattr(core, "atomic_write_text", failing)
        with pytest.raises(OSError):
            change_cut.apply_cut(plan)
        assert set(written[:-1]) <= set(landed), "the earlier writes must have landed before the failure"
        assert _snapshot(project) == before


# ---------------------------------------------------------------------------
# Re-runs (CD8), every row of the design's table driven through the command
# ---------------------------------------------------------------------------

_THREE = {
    "alpha": _fragment("alpha"),
    "gamma": _fragment("gamma", date="2026-10-21"),
}
_THREE_TABLE = "| alpha | ships | |\n| gamma | ships | |\n"


def _failing_unlink(monkeypatch, target: Path) -> None:
    real = Path.unlink

    def unlink(self, *args, **kwargs):
        if self == target:
            raise PermissionError(f"read-only: {self.name}")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)


def _written(project: Path) -> dict[str, bytes]:
    """Every file a cut writes: the archive, the release files, the changelog."""
    snap = _snapshot(project)
    return {
        k: v for k, v in snap.items()
        if k.startswith((".prawduct/change-log-archive/", ".prawduct/releases/")) or k == DIGEST
    }


class TestReRuns:
    def test_a_fragment_left_by_a_failed_removal_is_removed_and_nothing_is_written(self, tmp_path, monkeypatch, capsys):
        project = _declared(tmp_path, fragments=_THREE, table=_THREE_TABLE)
        stuck = project / ".prawduct" / "changes" / "gamma.md"
        with monkeypatch.context() as m:
            _failing_unlink(m, stuck)
            assert change_cut.cut_cmd(project, ["--release", "v3.8.0", "--apply"]) == 1
        assert "refused: removal-failed:" in capsys.readouterr().err
        assert stuck.exists() and (project / RELEASE_FILE).is_file()
        # The headline file goes last, so a fragment that failed to go keeps it.
        assert (project / HEADLINE_FILE).exists()
        written = _written(project)

        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 0, result.stderr
        assert "removing 1 fragment(s) the archive already holds, writing nothing" in result.stdout
        assert not stuck.exists()
        # The headline file was never reached by the failed run; the re-run finds
        # it in the release file and removes it too.
        assert not (project / HEADLINE_FILE).exists()
        assert _written(project) == written
        assert (project / DIGEST).read_text().count("**`gamma`**:") == 1

    def test_a_headline_file_left_by_a_failed_removal_is_removed_and_nothing_is_written(self, tmp_path, monkeypatch, capsys):
        project = _declared(tmp_path, fragments=_THREE, table=_THREE_TABLE)
        headline = project / HEADLINE_FILE
        with monkeypatch.context() as m:
            _failing_unlink(m, headline)
            assert change_cut.cut_cmd(project, ["--release", "v3.8.0", "--apply"]) == 1
        capsys.readouterr()
        assert headline.exists() and not list((project / ".prawduct" / "changes").glob("*.md"))
        written = _written(project)

        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 0, result.stderr
        assert f"headline file: removing {HEADLINE_FILE}" in result.stdout
        assert not headline.exists()
        assert _written(project) == written

    def test_a_published_crlf_trailing_space_headline_file_is_still_removed(self, tmp_path, monkeypatch, capsys):
        published = b"\r\n**Two-line headline.**  \r\nIts second line.\t\r\n\r\n"
        project = _declared(tmp_path, fragments=_THREE, table=_THREE_TABLE, headline=published)
        headline = project / HEADLINE_FILE
        with monkeypatch.context() as m:
            _failing_unlink(m, headline)
            assert change_cut.cut_cmd(project, ["--release", "v3.8.0", "--apply"]) == 1
        capsys.readouterr()
        release = (project / RELEASE_FILE).read_text()
        # The first line keeps the trailing spaces it was written with: only the
        # headline's ends are stripped, never a line's inside it.
        assert "**Two-line headline.**  \nIts second line.\n" in release

        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 0, result.stderr
        assert not headline.exists()

    def test_a_later_fragment_reusing_a_cut_scope_name_refuses_and_stays(self, tmp_path):
        project = _declared(tmp_path, fragments=_THREE, table=_THREE_TABLE)
        assert _cut(project, "--release", "v3.8.0", "--apply").returncode == 0
        later = project / ".prawduct" / "changes" / "alpha.md"
        _write(later, _fragment("alpha", date="2026-10-24", title="alpha again", note="A second alpha change."))
        before = _snapshot(project)

        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 1
        assert "refused: release-already-cut:" in result.stderr
        assert "alpha" in result.stderr.split("refused: release-already-cut:", 1)[1]
        assert later.exists()
        assert _snapshot(project) == before

    def test_an_unclassified_fragment_after_the_cut_refuses_rather_than_naming_the_table(self, tmp_path):
        project = _declared(tmp_path, fragments=_THREE, table=_THREE_TABLE)
        assert _cut(project, "--release", "v3.8.0", "--apply").returncode == 0
        _write(project / ".prawduct" / "changes" / "delta.md", _fragment("delta", date="2026-10-24"))
        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 1
        assert "refused: release-already-cut:" in result.stderr

    def test_a_withheld_fragment_after_the_cut_is_kept_pending(self, tmp_path):
        project = _declared(tmp_path, fragments=_THREE, table=_THREE_TABLE + "| delta | withheld | BKL-6J2X |\n")
        assert _cut(project, "--release", "v3.8.0", "--apply").returncode == 0
        delta = project / ".prawduct" / "changes" / "delta.md"
        _write(delta, _fragment("delta", date="2026-10-24"))
        before = _snapshot(project)
        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 0, result.stderr
        assert "nothing to do" in result.stdout
        assert delta.exists() and _snapshot(project) == before

    def test_a_next_release_headline_file_survives_and_the_output_says_so(self, tmp_path):
        project = _declared(tmp_path, fragments=_THREE, table=_THREE_TABLE)
        assert _cut(project, "--release", "v3.8.0", "--apply").returncode == 0
        _write(project / HEADLINE_FILE, "**The next release.** Something else entirely.\n")
        before = _snapshot(project)
        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 0, result.stderr
        assert "nothing to do" in result.stdout
        assert f"headline file: kept {HEADLINE_FILE}; its text is not in {RELEASE_FILE}" in result.stdout
        assert _snapshot(project) == before

    def test_with_nothing_left_a_rerun_is_nothing_to_do(self, tmp_path):
        project = _declared(tmp_path, fragments=_THREE, table=_THREE_TABLE)
        assert _cut(project, "--release", "v3.8.0", "--apply").returncode == 0
        before = _snapshot(project)
        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 0, result.stderr
        assert "nothing to do" in result.stdout
        assert "headline file" not in result.stdout
        assert _snapshot(project) == before

    def test_a_rerun_needs_no_release_plan_when_only_held_fragments_remain(self, tmp_path, monkeypatch, capsys):
        project = _declared(tmp_path, fragments=_THREE, table=_THREE_TABLE)
        stuck = project / ".prawduct" / "changes" / "alpha.md"
        with monkeypatch.context() as m:
            _failing_unlink(m, stuck)
            assert change_cut.cut_cmd(project, ["--release", "v3.8.0", "--apply"]) == 1
        capsys.readouterr()
        (project / ".prawduct" / "artifacts" / "release-plan-v3.8.0.md").unlink()
        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 0, result.stderr
        assert not stuck.exists()


class TestRecovery:
    def test_a_failed_write_restores_everything_and_keeps_the_fragments(self, tmp_path, monkeypatch):
        project = _declared(tmp_path, fragments={"alpha": _fragment("alpha")}, table="| alpha | ships | |\n")
        before = _snapshot(project)
        plan = change_cut.plan_cut(project, "v3.8.0")

        def failing(writes):
            raise OSError("disk full")

        monkeypatch.setattr(core, "write_all_or_none", failing)
        with pytest.raises(OSError):
            change_cut.apply_cut(plan)
        assert _snapshot(project) == before

    def test_an_undeclared_rerun_after_an_interrupted_removal_duplicates_nothing(self, tmp_path):
        project = _project(tmp_path, fragments={"alpha": _fragment("alpha")}, table="| alpha | ships | |\n")
        plan = change_cut.plan_cut(project, "v3.8.0")
        (project / ".prawduct" / "change-log-archive").mkdir()
        core.write_all_or_none(plan.writes)  # the writes landed; the removal never ran
        assert (project / ".prawduct" / "changes" / "alpha.md").exists()

        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 0, result.stderr
        bucket = (project / ".prawduct" / "change-log-archive" / "2026-10.md").read_text()
        assert len(change_log.parse_change_log(bucket)) == 1
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
    _git_commit_all(project)
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


# ---------------------------------------------------------------------------
# Prawduct's own changelog result is pinned byte for byte (#733, CD11)
# ---------------------------------------------------------------------------

#: Captured 2026-10-26 from the cut as it stood before the release-file model
#: (change_cut at 4d544b03), run on `_golden_fragments` against a
#: `plugin/CHANGELOG.md` whose `## v3.8.0` section held only `HEADLINE`. An
#: absolute value on purpose: it is the shipped format every upgrading repo's
#: banner reads, so a test derived from the renderer could not catch the
#: renderer drifting.
GOLDEN_PRAWDUCT_CHANGELOG = (
    b"# Changelog\n\nPreamble.\n\n## v3.8.0\n\n"
    b"**This release does three things.** And says so in one line.\n\n"
    b"**`gamma`**: The gamma change, for users.\n\n"
    b"**`alpha`**: The alpha change, for users.\nIt spans two lines.\n\n"
    b"## v3.7.1\n\nOld.\n"
)


def _golden_fragments() -> dict[str, str]:
    return {
        "alpha": _fragment("alpha", note="The alpha change, for users.\nIt spans two lines."),
        "beta": _fragment("beta", note="none: internal only", date="2026-10-20").replace("type: fix", "type: chore"),
        "gamma": _fragment("gamma", date="2026-10-21").replace("type: fix", "type: feature"),
    }


_GOLDEN_TABLE = "| alpha | ships | |\n| beta | ships | |\n| gamma | ships | |\n"


class TestPrawductGolden:
    def test_the_section_flow_starting_state_now_refuses_release_in_changelog(self, tmp_path):
        """The golden's old starting state, an open section already renamed to
        `## v3.8.0` and holding the headline, is refused under the release-file model.

        This test used to cut that state and expect the golden. The model
        changed on purpose (owner decision, 733-requirements Decision 2): the
        cut no longer writes into a section it finds, it writes the section
        itself, so a changelog that already names the release is the
        `release-in-changelog` refusal (CD7), and nothing is written. The golden
        bytes outlive the old flow: the release-file test below must reproduce
        them from the new starting state.
        """
        project = _project(
            tmp_path, fragments=_golden_fragments(), table=_GOLDEN_TABLE,
            digest=f"# Changelog\n\nPreamble.\n\n## v3.8.0\n\n{HEADLINE}\n\n## v3.7.1\n\nOld.\n",
            decl=PRAWDUCT_DECL,
        )
        before = _snapshot(project)
        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 1
        assert "refused: release-in-changelog:" in result.stderr
        assert _snapshot(project) == before

    def test_the_release_file_flow_produces_the_same_bytes(self, tmp_path):
        """The new starting state: no section, the headline in its file, prawduct's declaration."""
        project = _project(
            tmp_path, fragments=_golden_fragments(), table=_GOLDEN_TABLE,
            digest="# Changelog\n\nPreamble.\n\n## v3.7.1\n\nOld.\n",
        )
        _write(
            project / ".prawduct" / "project-state.yaml",
            'consumer_digest:\n  path: plugin/CHANGELOG.md\n  heading: "## {version}"\n'
            "  headline: required\n  layout: paragraphs\n",
        )
        _write(project / ".prawduct" / "release-headline.md", HEADLINE + "\n")
        result = _cut(project, "--release", "v3.8.0", "--apply")
        assert result.returncode == 0, result.stderr
        assert (project / DIGEST).read_bytes() == GOLDEN_PRAWDUCT_CHANGELOG


def test_the_default_release_date_is_the_operators_local_date(monkeypatch):
    """An evening cut west of UTC is dated the day it was cut, not tomorrow."""
    from datetime import datetime as real_datetime

    class _Evening(real_datetime):
        @classmethod
        def now(cls, tz=None):
            utc_instant = real_datetime(2026, 10, 26, 3, 30)  # 03:30 UTC
            return utc_instant if tz is not None else real_datetime(2026, 10, 25, 20, 30)  # 20:30 local

    monkeypatch.setattr(change_cut, "datetime", _Evening)
    assert change_cut._today(None) == "2026-10-25"
