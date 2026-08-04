"""Tests for the post-release verification gate (``lib/release_verification``).

Structure ported from ``test_release_readiness.py`` — the precedent this
subcommand is modelled on — before adding cases of its own.

Two deliberate choices, each answering "what change would turn this red?":

* The tree-reading checks run against a **real git repository** built in
  ``tmp_path``, not a fixture standing in for one. ``check_version_files`` reads
  through ``git show <tag>:<path>``, so a fixture would exercise the parser and
  never the thing that can actually be wrong — which tree got read. Point these
  at the working tree instead of the tag and the mismatch tests go green while
  the gate reports on the wrong commit.
* The network check is exercised through a substituted ``_run``, so no test
  reaches GitHub. Collapse ``UNVERIFIABLE`` into ``FAILED`` and
  ``test_missing_gh_is_unverifiable_not_failed`` goes red — which is the whole
  point of that state existing.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))
from lib import release_verification as rv  # noqa: E402

HOOK = Path(__file__).resolve().parent.parent / "plugin" / "bin" / "prawduct-hook"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _git(repo: Path, *args: str) -> None:
    """Run git with the developer's global config neutralised.

    Sibling test files do the same: without it these repos inherit whatever the
    machine sets — `commit.gpgsign`, hooks, a default branch name — and the
    suite passes or fails on the author's dotfiles rather than on the code.
    """
    subprocess.run(
        ["git", *args],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
        env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"},
    )


#: The three shapes prawduct's own layout uses, as declaration entries.
_BARE = ("plugin/VERSION", "bare", None)
_JSON = ("plugin/.claude-plugin/plugin.json", "json", "version")
_TOML = ("pyproject.toml", "toml", "project.version")


def _state_yaml(*specs: tuple[str, str, str | None]) -> str:
    """A `project-state.yaml` body declaring ``specs``.

    Neighbouring column-0 keys are included on purpose: the reader scans for a
    column-0 `release_version_files:` and must stop at the next one, so a block
    with nothing after it would never exercise the terminator.
    """
    lines = ["base_branch: develop", "", "release_version_files:"]
    for path, fmt, key in specs:
        lines += [f"  - path: {path}", f"    format: {fmt}"]
        if key:
            lines.append(f"    key: {key}")
    lines += ["", "views_enabled: true"]
    return "\n".join(lines) + "\n"


def _make_repo(
    tmp_path: Path,
    *,
    version: str = "3.2.0",
    tag: str | None = None,
    declare: str | None = None,
) -> Path:
    """A real repo whose tagged tree carries ``version`` in all three files.

    ``declare`` writes a `.prawduct/project-state.yaml` **into the tagged tree**,
    because that is where the check reads it from — which files carried a
    release's version is a fact about that release, not about the checkout you
    are standing in. Left ``None``, the tree declares nothing and the check
    falls back to its built-in guess, which is the pre-declaration behaviour and
    what most cases here still exercise.
    """
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "T")
    _write(repo / "plugin" / "VERSION", version + "\n")
    _write(
        repo / "plugin" / ".claude-plugin" / "plugin.json",
        json.dumps({"name": "prawduct", "version": version}) + "\n",
    )
    _write(repo / "pyproject.toml", f'[project]\nname = "x"\nversion = "{version}"\n')
    if declare is not None:
        _write(repo / ".prawduct" / "project-state.yaml", declare)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "release")
    _git(repo, "tag", tag or f"v{version}")
    # `origin/main` is what the gate compares against; a local clone has none,
    # so point a ref at the same commit under the name the gate reads.
    _git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repo


needs_tomllib = pytest.mark.skipif(
    rv._toml_loader() is None,
    reason="tomllib is 3.11+; the 3.10 floor leg proves the degraded path instead",
)


def _read(fmt: str, content: str, key: str = "") -> rv._Read:
    return rv._read_version(rv.VersionFile("f", fmt, key), content)


class TestVersionParsing:
    @pytest.mark.parametrize(
        ("kind", "key", "content", "expected"),
        [
            ("bare", "", "3.2.0\n", "3.2.0"),
            ("bare", "", "  3.2.0  ", "3.2.0"),
            ("bare", "", "", None),
            ("json", "version", '{"version": "3.2.0"}', "3.2.0"),
            ("json", "version", '{"name": "x"}', None),
            ("json", "version", "not json at all", None),
            ("json", "a.b.version", '{"a": {"b": {"version": "3.2.0"}}}', "3.2.0"),
            ("json", "a.b.version", '{"a": {"b": {}}}', None),
            pytest.param("toml", "version", 'version = "3.2.0"\n', "3.2.0", marks=needs_tomllib),
            pytest.param("toml", "version", "version = '3.2.0'\n", "3.2.0", marks=needs_tomllib),
            pytest.param(
                "toml", "project.version", "[project]\nname = 'x'\n", None, marks=needs_tomllib
            ),
        ],
    )
    def test_extracts_or_reports_absent(self, kind, key, content, expected):
        assert _read(kind, content, key).value == expected

    @needs_tomllib
    @pytest.mark.parametrize("first", ["project", "tool.other"])
    def test_the_declared_table_wins_at_either_ordering(self, first):
        """#580, and the test that used to assert the defect as a guarantee.

        The replaced `test_toml_takes_the_first_assignment` asserted that
        `[project]` above `[tool.other]` returns the project version, and its
        docstring called the ordering a guarantee — *"`[project].version` sits
        above any `[tool.*]` table that repeats it."* **TOML promises no such
        thing**, and #580's measured repro is the reverse ordering: with
        `[tool.myplugin] version = "9.9.9"` first, the line scanner returned
        9.9.9 and reported a confident false mismatch.

        Correcting that is not weakening it — the old assertion was true only of
        the example it chose. Both orderings are exercised here, and the answer
        no longer depends on the order at all, because `key: project.version`
        says which table is authoritative instead of position implying it.
        """
        tables = {
            "project": '[project]\nversion = "3.2.0"\n',
            "tool.other": '[tool.other]\nversion = "9.9.9"\n',
        }
        second = "tool.other" if first == "project" else "project"
        content = f"{tables[first]}\n{tables[second]}"
        assert _read("toml", content, "project.version").value == "3.2.0"
        # And the other table stays reachable by its own name — proof the key
        # path is descended, not that `[project]` acquired a special case.
        assert _read("toml", content, "tool.other.version").value == "9.9.9"

    @needs_tomllib
    @pytest.mark.parametrize("key", ["versioning", "version_scheme", "versions"])
    def test_a_neighbouring_key_is_not_read_as_the_version(self, key):
        """A prefix match reads a neighbouring key as the release version.

        Red before the key comparison replaced `startswith`; now structural,
        since a mapping lookup cannot prefix-match. Kept because the guarantee
        is what matters, not the mechanism that provides it.
        """
        assert _read("toml", f'{key} = "scheme-x"\n', "version").value is None

    @pytest.mark.parametrize(
        ("content", "key"),
        [
            ('["3.2.0"]', "version"),  # top level is not a mapping at all
            ('{"project": 3}', "project.version"),  # descends INTO a scalar
            ('{"project": "3.2.0"}', "project.version.major"),  # and into a string
        ],
    )
    def test_descending_through_a_non_mapping_reports_absent_not_a_crash(self, content, key):
        """`_descend` must not assume every level is a dict.

        **The first cut of this test only passed a top-level list**, which the
        membership test alone survives (`"version" not in [...]` is merely
        False), so it went green with the `isinstance` guard deleted. The cases
        that actually raise are the ones that descend *into* a scalar —
        `"version" not in 3` is a `TypeError`, thrown out of a release check.
        A guard that cannot fail for the regression it names is not a guard.
        """
        assert _read("json", content, key).value is None

    def test_a_declared_entry_missing_its_key_is_blocked_not_failed(self):
        """The same authoring slip as a missing `format:`, so the same posture.

        A `json`/`toml` entry with no `key:` used to reach FAILED while one with
        no `format:` reached UNVERIFIABLE — identical mistakes, opposite
        verdicts, and the FAILED leg contradicts R1: without a key there is no
        question to ask of the file, and a check that could not ask must not
        answer.
        """
        read = _read("json", '{"version": "3.2.0"}', key="")
        assert read.blocked is True
        assert read.value is None

    def test_an_unreadable_format_is_blocked_not_merely_absent(self):
        """`blocked` is what keeps a runtime limitation out of the FAILED lane.

        A declared file whose format this check cannot read must reach
        UNVERIFIABLE, while a declared file it *can* read and finds no version
        in is a real defect. Collapse the two and the module's founding error
        returns one level down.
        """
        for fmt in ("xml", ""):
            read = _read(fmt, "<v>1</v>", "version")
            assert read.blocked is True, f"{fmt!r} must not be read as a verdict"
            assert read.value is None
        readable = _read("json", '{"name": "x"}', "version")
        assert readable.blocked is False, "a readable file with no version is not blocked"

    def test_toml_without_tomllib_is_blocked_naming_the_interpreter(self, monkeypatch):
        """The 3.10 floor, exercised on every interpreter.

        On 3.10 this path is reached for real and `needs_tomllib` skips the
        cases above; on 3.11+ the import cannot be un-done, so the loader lookup
        is substituted — the same split the suite already uses for a hung
        toolchain, which likewise cannot be staged for real. What is asserted is
        the caller's handling: an absent stdlib module is not evidence about a
        release, so it must be `blocked`, never a version verdict.
        """
        monkeypatch.setattr(rv, "_toml_loader", lambda: None)
        read = _read("toml", 'version = "3.2.0"\n', "version")
        assert read.blocked is True
        assert read.value is None
        assert "3.11+" in read.problem


class TestDeclarationReading:
    """The minimal-YAML reader. Undeclared, declared-empty and declared are
    three different facts and the caller reads them oppositely, so the
    distinctions are pinned here rather than only through the check."""

    def test_undeclared_is_none_not_empty(self):
        """`None` falls back to a guess that cannot fail a release; `[]` is an
        exclusive opt-out. Collapse them and either the guess starts failing
        products or an explicit opt-out silently re-enables it."""
        assert rv._read_declaration("base_branch: develop\n") is None

    def test_declared_empty_is_a_list_not_none(self):
        assert rv._read_declaration("release_version_files: []\n") == []

    def test_entries_carry_path_format_and_key(self):
        parsed = rv._read_declaration(_state_yaml(_BARE, _JSON, _TOML))
        assert parsed == [
            rv.VersionFile("plugin/VERSION", "bare", ""),
            rv.VersionFile("plugin/.claude-plugin/plugin.json", "json", "version"),
            rv.VersionFile("pyproject.toml", "toml", "project.version"),
        ]

    def test_the_block_stops_at_the_next_column_zero_key(self):
        """Without the terminator the reader swallows the rest of the file.

        **Pinned against a following block whose items carry `path:`**, because
        that is the only shape that makes the terminator observable. An earlier
        version of this test used `risk_surfaces:` with bare `- skills/` items,
        and passed with the terminator deleted: those items parse to no `path`
        and are dropped anyway, so the assertion could not tell a reader that
        stopped from one that ran on and discarded what it found.
        """
        text = _state_yaml(_BARE) + "deprecated_terms:\n  - path: docs/old-name.md\n"
        assert rv._read_declaration(text) == [rv.VersionFile("plugin/VERSION", "bare", "")]

    def test_a_comment_between_entries_does_not_end_the_block(self):
        """A comment is inert at any indent — column 0 included.

        The terminator looks for a column-0 line, and a full-line comment is
        one. Before the skip, a product annotating its declaration lost every
        entry below the comment: the check then reported `ok` over the survivors
        while a declared version file went unread, which is a silent hole in a
        gate whose entire purpose is catching version disagreement. Both indents
        are exercised because only the column-0 one ever terminated.
        """
        text = (
            "release_version_files:\n"
            "  - path: plugin/VERSION\n"
            "    format: bare\n"
            "# added when the manifest moved\n"
            "  # indented note\n"
            "  - path: package.json\n"
            "    format: json\n"
            "    key: version\n"
        )
        assert rv._read_declaration(text) == [
            rv.VersionFile("plugin/VERSION", "bare", ""),
            rv.VersionFile("package.json", "json", "version"),
        ]

    def test_comments_and_quotes_are_stripped(self):
        text = (
            "release_version_files:\n"
            '  - path: "pyproject.toml"  # the manifest\n'
            "    format: toml\n"
            "    key: 'project.version'\n"
        )
        assert rv._read_declaration(text) == [
            rv.VersionFile("pyproject.toml", "toml", "project.version")
        ]

    def test_a_commented_out_block_is_undeclared(self):
        """The template ships the key commented out as its schema legend. A
        reader that matched it would give every scaffolded product a
        declaration it never made."""
        text = "# release_version_files:\n#   - path: pyproject.toml\n"
        assert rv._read_declaration(text) is None

    def test_this_repo_s_own_declaration_parses_to_its_real_layout(self):
        """Every other case here is synthesised; this one reads the shipped file.

        Chunk 02's acceptance criteria include prawduct keeping its own verdict,
        and a declaration that silently loses an entry would still report `ok` —
        over two files instead of three, distinguishable from a complete check
        only by a digit. Pinned against `_FALLBACK_VERSION_FILES` rather than a
        literal list: prawduct's declaration and the built-in guess describe the
        same repo, so if one is ever edited without the other, that is the bug.
        """
        state_file = Path(__file__).resolve().parent.parent / ".prawduct" / "project-state.yaml"
        parsed = rv._read_declaration(state_file.read_text(encoding="utf-8"))
        assert parsed == list(rv._FALLBACK_VERSION_FILES), (
            "this repo's declared version files drifted from the layout the "
            "fallback assumes for it — one of the two was edited alone"
        )

    def test_the_shipped_template_declares_nothing(self):
        """The template carries the key as a commented-out schema legend.

        If it ever ships uncommented, every scaffolded product inherits a
        declaration it never made — and a declaration is exactly what turns a
        version mismatch into a failed release.
        """
        template = Path(__file__).resolve().parent.parent / "plugin" / "templates"
        text = (template / "project-state.yaml").read_text(encoding="utf-8")
        assert "release_version_files:" in text, "the schema legend went missing"
        assert rv._read_declaration(text) is None, (
            "the template ships an ACTIVE declaration; scaffolded products would "
            "be held to prawduct's example layout"
        )

    def test_an_entry_without_a_path_is_dropped_but_one_without_a_format_is_kept(self):
        """Opposite handling, on purpose. A pathless entry names no file and
        cannot be reported against; a formatless one names a file the product
        says carries its version, so it must surface as unreadable rather than
        vanish — unknown shapes report *unchecked*, never *passed*."""
        text = "release_version_files:\n  - format: bare\n  - path: VERSION\n"
        assert rv._read_declaration(text) == [rv.VersionFile("VERSION", "", "")]


class TestVersionFiles:
    # `_make_repo` mirrors prawduct's real layout, which includes a `toml`
    # version file — unreadable below 3.11, where this check reports
    # `unverifiable` by design. The full-verification outcome is therefore
    # interpreter-dependent; `test_the_floor_leg_degrades_instead_of_failing`
    # pins what the 3.10 leg sees instead, so the floor still proves something.
    @needs_tomllib
    def test_agreeing_tree_is_ok(self, tmp_path):
        repo = _make_repo(tmp_path, version="3.2.0")
        state, detail = rv.check_version_files(repo, "v3.2.0")
        assert state == rv.OK
        assert "3 version file(s) agree" in detail
        # Names, not just a count. Red if the detail goes back to reporting a
        # bare number: the count alone cannot be acted on, and this string is
        # what reaches both the operator and the --json payload.
        for path in ("plugin/VERSION", "plugin/.claude-plugin/plugin.json", "pyproject.toml"):
            assert path in detail
        assert "not in this tree" not in detail, "nothing was skipped in this tree"

    def test_a_declared_file_that_disagrees_fails(self, tmp_path):
        """The strong contract, and it now requires a declaration to reach.

        **This assertion used to run without one.** The tree said nothing about
        which files carried its version, prawduct guessed its own layout, and a
        disagreement found through that guess exited 1 — which is #576: a
        setuptools-scm project or a tooling-only `pyproject.toml` was told its
        release was broken against a layout it never claimed. So FAILED is now
        earned by the product *declaring* these files, and the sibling test
        below pins what the undeclared half does instead. The contract is not
        weakened — it is the same assertion, now with the premise that
        justifies it, and the fallback it left behind is separately guarded.
        """
        repo = _make_repo(
            tmp_path, version="3.2.0", tag="v3.2.1", declare=_state_yaml(_BARE, _JSON)
        )
        state, detail = rv.check_version_files(repo, "v3.2.1")
        assert state == rv.FAILED
        assert "plugin/VERSION: says 3.2.0, tag says 3.2.1" in detail

    def test_an_undeclared_disagreement_is_unverifiable_and_says_how_to_fix_that(
        self, tmp_path
    ):
        """R2's whole point: an undeclared layout may not produce a failure.

        `_FALLBACK_VERSION_FILES` is prawduct's own layout applied to a product
        that never claimed it. A disagreement found through it is still worth
        reporting — so the numbers stay in the detail — but it is not a verdict
        about someone else's release, and the one edit that would make it one is
        named rather than left to be deduced. Red if the fallback regains the
        ability to reach FAILED, which is the #576 behaviour returning.
        """
        repo = _make_repo(tmp_path, version="3.2.0", tag="v3.2.1")
        state, detail = rv.check_version_files(repo, "v3.2.1")
        assert state == rv.UNVERIFIABLE, "a guessed layout produced a verdict about a release"
        assert "plugin/VERSION: says 3.2.0, tag says 3.2.1" in detail, (
            "the disagreement was softened into silence, not into a soft failure"
        )
        assert "release_version_files" in detail

    def test_a_declared_file_missing_from_the_tree_fails(self, tmp_path):
        """Declared and absent is a real defect — the product said it ships this.

        The mirror of `test_absent_file_is_skipped_not_failed`: same tree state,
        opposite verdict, and the only difference is who chose the layout.
        """
        repo = _make_repo(tmp_path, version="3.2.0", declare=_state_yaml(_BARE, _JSON))
        _git(repo, "rm", "-q", "plugin/.claude-plugin/plugin.json")
        _git(repo, "commit", "-qm", "drop the cache key")
        _git(repo, "tag", "v3.2.4")
        state, detail = rv.check_version_files(repo, "v3.2.4")
        assert state == rv.FAILED
        assert "plugin/.claude-plugin/plugin.json: declared, but not in v3.2.4's tree" in detail

    def test_a_declared_file_present_but_unparseable_fails(self, tmp_path):
        """#576's other half, and the reason declaration is not merely cosmetic.

        A `pyproject.toml` with no `[project].version` is *skipped* under the
        guess and *failed* under a declaration, because the product asserted the
        version lives there. Driven through `json` rather than `toml` so the
        3.10 floor leg exercises it too — the format is incidental here, the
        provenance is the subject.
        """
        repo = tmp_path / "declared"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "config", "user.email", "t@example.com")
        _git(repo, "config", "user.name", "T")
        _write(repo / "plugin" / ".claude-plugin" / "plugin.json", '{"name": "prawduct"}\n')
        _write(repo / ".prawduct" / "project-state.yaml", _state_yaml(_JSON))
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "no version key")
        _git(repo, "tag", "v1.0.0")
        state, detail = rv.check_version_files(repo, "v1.0.0")
        assert state == rv.FAILED
        assert "declared to carry the version but has no version" in detail

    def test_an_undeclared_pyproject_without_a_project_version_is_not_failed(self, tmp_path):
        """#576's measured repro: setuptools-scm, or a tooling-only pyproject.

        The file is present and carries no literal version — under the guess
        that is not a broken release, it is a layout prawduct assumed. Red if
        this returns FAILED, which is the filed defect verbatim.
        """
        repo = tmp_path / "scm"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "config", "user.email", "t@example.com")
        _git(repo, "config", "user.name", "T")
        _write(repo / "pyproject.toml", '[project]\nname = "x"\ndynamic = ["version"]\n')
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "setuptools-scm")
        _git(repo, "tag", "v1.0.0")
        state, _ = rv.check_version_files(repo, "v1.0.0")
        assert state != rv.FAILED, "an assumed layout graded a product that never claimed it"

    def test_the_floor_leg_degrades_instead_of_failing(self, tmp_path, monkeypatch):
        """What Python 3.10 sees, asserted on every interpreter.

        Four happy-path tests in this file assert prawduct's full three-file
        verification, which is true only on 3.11+ — `_make_repo` mirrors the
        real layout, `pyproject.toml` included. They now carry `@needs_tomllib`,
        which would leave the CI floor leg (`tests.yml` runs 3.10 and 3.14) with
        no coverage of the shape it actually runs. This is that coverage, and it
        pins the property that matters: the floor **degrades**, it does not fail.

        Found by simulating the loader's absence across the whole file. A
        reviewer caught one test failing on 3.10; there were five, because the
        fallback layout carries a toml entry for every fixture built from it.
        """
        monkeypatch.setattr(rv, "_toml_loader", lambda: None)
        repo = _make_repo(tmp_path, version="3.2.0")
        state, detail = rv.check_version_files(repo, "v3.2.0")
        assert state == rv.UNVERIFIABLE, "the floor must not report a verdict it cannot support"
        assert state != rv.FAILED, "an interpreter's stdlib is not evidence about a release"
        assert "3.11+" in detail
        # The two readable files still verified — the degradation is scoped to
        # the entry that needs the missing module, not to the whole check.
        assert "2 file(s) did agree" in detail
        assert "plugin/VERSION" in detail

    def test_a_blocked_file_does_not_swallow_a_disagreement_beside_it(
        self, tmp_path, monkeypatch
    ):
        """Every soft finding is reported, not just the first kind found.

        The shape a 3.10 operator actually hits: `pyproject.toml` cannot be read
        at all, and `plugin/VERSION` disagrees. Returning only the blocked list
        drops a live version disagreement because an unrelated sibling could not
        be parsed — "advice fails soft" is not "advice fails silent", one level
        down from where this branch fixed it last chunk.

        Writing this also caught the detail calling `checked` files "did agree"
        while it still held files that had just disagreed.
        """
        monkeypatch.setattr(rv, "_toml_loader", lambda: None)
        repo = _make_repo(tmp_path, version="3.2.0", tag="v3.2.1")
        state, detail = rv.check_version_files(repo, "v3.2.1")
        assert state == rv.UNVERIFIABLE
        assert "3.11+" in detail, "the unreadable file went unreported"
        assert "plugin/VERSION: says 3.2.0, tag says 3.2.1" in detail, (
            "a real disagreement was dropped because a sibling file was unreadable"
        )
        assert "did agree" not in detail, "nothing agreed here"

    def test_a_declaration_naming_no_files_is_unverifiable_not_a_pass(self, tmp_path):
        """`release_version_files: []` is a deliberate opt-out, not a green light.

        Nothing was measured, and the module's standing rule is that saying so
        is not the same as passing. `risk_surfaces: []` draws the same line.
        """
        repo = _make_repo(tmp_path, version="3.2.0", declare="release_version_files: []\n")
        state, detail = rv.check_version_files(repo, "v3.2.0")
        assert state == rv.UNVERIFIABLE
        assert "no version file to check" in detail

    @needs_tomllib
    def test_a_fully_declared_tree_agrees(self, tmp_path):
        repo = _make_repo(tmp_path, version="3.2.0", declare=_state_yaml(_BARE, _JSON, _TOML))
        state, detail = rv.check_version_files(repo, "v3.2.0")
        assert state == rv.OK
        assert "3 version file(s) agree" in detail
        assert "not in this tree" not in detail

    def test_the_declaration_is_read_from_the_tag_tree_not_the_checkout(self, tmp_path):
        """The module's founding rule, applied to the declaration itself.

        The tagged tree declares only `plugin/VERSION`; the working tree is then
        rewritten to declare a file that would fail. A check reading the
        checkout grades v3.2.0 against a layout that release never had — the
        same class of error as reading the working tree's version files, which
        this module already refuses to do.
        """
        repo = _make_repo(tmp_path, version="3.2.0", declare=_state_yaml(_BARE))
        _write(
            repo / ".prawduct" / "project-state.yaml",
            _state_yaml(("does/not/exist.txt", "bare", None)),
        )
        state, detail = rv.check_version_files(repo, "v3.2.0")
        assert state == rv.OK, "the working tree's declaration reached a tagged release"
        assert "plugin/VERSION" in detail

    def test_absent_file_is_skipped_not_failed(self, tmp_path):
        """This module ships to products with a different layout.

        Red before the skip: a product with no `pyproject.toml` was reported
        `not-released`, naming a file that cannot exist in its tree.
        """
        repo = _make_repo(tmp_path, version="3.2.0")
        _git(repo, "rm", "-q", "pyproject.toml")
        # Move the REMAINING files to the new version, so this test isolates the
        # absent file rather than tripping on a version mismatch.
        _write(repo / "plugin" / "VERSION", "3.2.3\n")
        _write(
            repo / "plugin" / ".claude-plugin" / "plugin.json",
            json.dumps({"name": "prawduct", "version": "3.2.3"}) + "\n",
        )
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "no pyproject")
        _git(repo, "tag", "v3.2.3")
        state, detail = rv.check_version_files(repo, "v3.2.3")
        assert state == rv.OK
        assert "2 version file(s) agree" in detail
        # The skip must be VISIBLE. A tag tree missing
        # `plugin/.claude-plugin/plugin.json` — the auto-update cache key, and
        # the root cause this whole check exists for — otherwise reports
        # `released` / exit 0, distinguishable from a complete release only by a
        # "2" where a "3" belongs. Red if the naming clause is dropped.
        assert "not in this tree: pyproject.toml" in detail

    def test_a_present_file_carrying_no_version_is_not_called_absent(self, tmp_path):
        """The skip is reported with the reason it actually had.

        A tooling-only `pyproject.toml` contributes nothing under the guess —
        correctly, that is #576 — but it is *present*, and the detail used to
        lump it in with genuinely absent files and announce "not in this tree"
        about a file sitting right there. Same wrong-cause defect this plan
        fixed one level up, where a non-repository was reported as a question
        about the product's layout: the verdict was right and the reason was
        not, and a soft failure still owes its reader the real one.

        **Built on a `json` file, not the `pyproject.toml` this defect was found
        through.** The first cut used the latter and asserted `OK` — which is
        true on 3.11+ and false on the 3.10 CI leg, where the toml entry is
        `blocked` and the check returns UNVERIFIABLE without ever reaching the
        detail string this greps. It was R-1's only test, so on the floor leg
        the fix went from covered to red. The reason-split has nothing to do
        with TOML, so it is proven on a format every interpreter can read.
        """
        repo = tmp_path / "mixed"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "config", "user.email", "t@example.com")
        _git(repo, "config", "user.name", "T")
        _write(repo / "plugin" / "VERSION", "1.0.0\n")
        # Present, and carrying no version — the same shape as a tooling-only
        # `pyproject.toml`, minus the interpreter dependency.
        _write(repo / "plugin" / ".claude-plugin" / "plugin.json", '{"name": "x"}\n')
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "no version key")
        _git(repo, "tag", "v1.0.0")
        state, detail = rv.check_version_files(repo, "v1.0.0")
        assert state == rv.OK
        assert "present but carrying no version: plugin/.claude-plugin/plugin.json" in detail
        assert "not in this tree: pyproject.toml" in detail
        # The regression guard, and it has to read the ABSENT clause specifically.
        # A first cut asserted "not in this tree" was absent from everything after
        # the "present but carrying" marker — tautological, since the absent clause
        # is always emitted first, so it could not catch the fold it names.
        absent_clause = detail.split("not in this tree: ")[1].split(" — ")[0]
        assert "plugin.json" not in absent_clause, (
            "a file that IS in the tree is being announced as missing from it"
        )

    def test_tree_with_no_known_version_file_is_unverifiable(self, tmp_path):
        repo = tmp_path / "bare"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "config", "user.email", "t@example.com")
        _git(repo, "config", "user.name", "T")
        _write(repo / "readme.md", "hi\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "x")
        _git(repo, "tag", "v1.0.0")
        state, _ = rv.check_version_files(repo, "v1.0.0")
        assert state == rv.UNVERIFIABLE

    # `_make_repo` mirrors prawduct's real layout, which includes a `toml`
    # version file — unreadable below 3.11, where this check reports
    # `unverifiable` by design. The full-verification outcome is therefore
    # interpreter-dependent; `test_the_floor_leg_degrades_instead_of_failing`
    # pins what the 3.10 leg sees instead, so the floor still proves something.
    @needs_tomllib
    def test_reads_the_tag_tree_not_the_working_tree(self, tmp_path):
        """The regression this gate exists to prevent, in one test.

        The tag's tree says 3.2.0; the working tree is then moved to 9.9.9 and
        left dirty. A gate reading the checkout would report 9.9.9 and, on a
        later branch, confidently grade a release that never shipped.
        """
        repo = _make_repo(tmp_path, version="3.2.0")
        _write(repo / "plugin" / "VERSION", "9.9.9\n")
        assert rv.check_version_files(repo, "v3.2.0")[0] == rv.OK


class TestVersionFilesWhenGitCannotAnswer:
    """A broken toolchain is not evidence about a release.

    **Neither `_run` site in `check_version_files` had a test**, and this chunk
    added a second one (the declaration read) in front of the loop. Both must
    degrade, because a `MISSING`/`ERRORED` sentinel falling through to
    `shown[0]` indexes the *string* — `"m" != 0` is True — and every file would
    be silently read as absent from the tree, which is a wrong answer wearing a
    confident face.

    Monkeypatched, unlike the non-repository tests beside them: an uninstalled
    or hung git cannot be staged for real, which is the same split the suite
    already draws for `check_tag_on_main`.
    """

    _CASES = [
        (rv.MISSING, "git is not installed"),
        (rv.ERRORED, "git could not read the tag's tree"),
    ]

    @pytest.mark.parametrize(("sentinel", "expected"), _CASES)
    def test_git_unavailable_at_the_declaration_read(
        self, tmp_path, monkeypatch, sentinel, expected
    ):
        monkeypatch.setattr(rv, "_run", lambda *a, **k: sentinel)
        state, detail = rv.check_version_files(tmp_path, "v1.0.0")
        assert state == rv.UNVERIFIABLE
        assert expected in detail

    @pytest.mark.parametrize(("sentinel", "expected"), _CASES)
    def test_git_unavailable_at_a_version_file_read(
        self, tmp_path, monkeypatch, sentinel, expected
    ):
        """The declaration read answers, then git stops answering.

        Reaching the loop's guard needs the first call to succeed, so the stub
        is selective — a blanket one returns at the declaration read and the
        per-file branch is never entered, which is how both went untested.
        """

        def fake(args, cwd):
            if args[-1].endswith("project-state.yaml"):
                return (1, "", "")  # no declaration in this tree
            return sentinel

        monkeypatch.setattr(rv, "_run", fake)
        state, detail = rv.check_version_files(tmp_path, "v1.0.0")
        assert state == rv.UNVERIFIABLE
        assert expected in detail
        # **`expected` alone cannot tell this branch from the fallback.** Delete
        # the guards and the sentinel string indexes as a non-zero exit, every
        # file reads as absent, and the no-files branch asks
        # `_outside_repo_reason` — which, with git equally unavailable there,
        # answers "git is not installed" too. The MISSING case passed under
        # exactly that mutation until this line: same words, wrong route, and
        # the difference is the trailing clause only the other branch appends.
        assert "no tree to read version files from" not in detail, (
            "the per-file guard was skipped; this answer came from the no-files branch"
        )


class TestVersionFilesOutsideARepo:
    def test_a_non_repository_names_its_real_cause(self, tmp_path):
        """The verdict was already right; the REASON was not.

        `git show <tag>:<path>` fails per-file outside a repository exactly as
        it does for a path absent from the tree, so every file was "skipped" and
        the no-files branch reported a layout question: *"a different product
        layout, or a tag this clone has not fetched"*. Neither is true, and a
        product owner reading it would go looking at their own layout.

        Unverifiable was the correct verdict, so this is not a false red — it is
        the rule one level down: *"advice fails soft" is not "advice fails
        silent"*. A soft failure still owes its reader the real cause.
        """
        state, detail = rv.check_version_files(tmp_path, "v1.0.0")
        assert state == rv.UNVERIFIABLE
        assert "not a git repository" in detail
        assert "product layout" not in detail, (
            "a non-repository is still reported as a question about the "
            "product's layout"
        )

    def test_a_real_repo_missing_the_files_still_says_layout(self, tmp_path):
        """The pre-existing message is correct for the case it was written for,
        and must survive the new branch above.

        **The first cut of this test asserted nothing.** It used `_make_repo`,
        which carries all three version files and therefore returns `OK`
        deterministically — so the only load-bearing line sat inside
        `if state == rv.UNVERIFIABLE:` and never ran. A test that cannot reach
        its subject passes forever, and Chunk 02 rewrites `check_version_files`
        wholesale believing this path is guarded. Now built on a repo that
        genuinely holds no version file, and asserted unconditionally.
        """
        repo = tmp_path / "bare"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "config", "user.email", "t@example.com")
        _git(repo, "config", "user.name", "T")
        _write(repo / "readme.md", "hi\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "x")
        _git(repo, "tag", "v1.0.0")
        state, detail = rv.check_version_files(repo, "v1.0.0")
        assert state == rv.UNVERIFIABLE
        assert "product layout" in detail, (
            "inside a real repository the no-files case must still report the "
            "layout question — the non-repo branch is stealing this path"
        )
        assert "not a git repository" not in detail


class TestTagOnMain:
    def test_tag_on_main_is_ok(self, tmp_path):
        repo = _make_repo(tmp_path, version="3.2.0")
        state, _ = rv.check_tag_on_main(repo, "v3.2.0")
        assert state == rv.OK

    def test_unresolvable_tag_fails(self, tmp_path):
        repo = _make_repo(tmp_path, version="3.2.0")
        state, detail = rv.check_tag_on_main(repo, "v9.9.9")
        assert state == rv.FAILED
        assert "does not resolve" in detail

    def test_a_non_repository_is_unverifiable_not_a_broken_release(self, tmp_path):
        """The check must not answer a question it could not ask.

        `git rev-parse <tag>^{commit}` exits **128** for two unrelated states —
        the tag is absent, and this is not a git repository — and the branch
        below read every non-zero as the first. Measured before the fix:
        `prawduct-hook check-released v3.2.4` from any non-repo directory printed
        `ERROR: tag-on-main: tag v3.2.4 does not resolve to a commit`, verdict
        `not-released`, exit 1 — a finding about a release, produced by an
        environment that could not look at it. This module's own docstrings say
        twice that a false red is worse than no check, because it is the reading
        that teaches people to ignore the check.

        Driven through the REAL failure — an ordinary empty directory, no
        monkeypatch — because a stubbed return proves the caller reads a signal,
        never that git produces it. The sibling test above patches `_run` and is
        the right shape for a hung toolchain, which cannot be staged for real.
        """
        state, detail = rv.check_tag_on_main(tmp_path, "v1.0.0")
        assert state == rv.UNVERIFIABLE, (
            "a non-repository still reports a verdict about the release"
        )
        assert "not a git repository" in detail
        assert "does not resolve" not in detail

    def test_an_absent_tag_inside_a_real_repo_still_fails(self, tmp_path):
        """The other half, and the one that keeps the fix honest: the repair
        must not soften a TRUE finding into `unverifiable`.

        Without this, returning UNVERIFIABLE unconditionally from the non-zero
        branch would pass the test above and silently retire the check.
        """
        repo = _make_repo(tmp_path, version="3.2.0")
        state, detail = rv.check_tag_on_main(repo, "v9.9.9")
        assert state == rv.FAILED
        assert "does not resolve" in detail

    def test_git_that_cannot_complete_is_unverifiable_not_a_tag_verdict(self, tmp_path, monkeypatch):
        """A broken toolchain is not evidence about the release.

        Also a regression guard: an edit meant to add this branch deleted the
        unresolvable-tag branch instead, and every check here still passed
        because nothing exercised the ERRORED path.
        """
        monkeypatch.setattr(rv, "_run", lambda *a, **k: rv.ERRORED)
        state, detail = rv.check_tag_on_main(tmp_path, "v1.0.0")
        assert state == rv.UNVERIFIABLE
        assert "could not resolve" in detail

    def test_absent_origin_main_is_unverifiable_not_failed(self, tmp_path):
        """A clone that cannot answer must not answer "broken".

        Red before the ref-existence check: a repo with no `origin/main` — a
        fresh checkout, a fork, a shallow CI fetch — reported
        `not contained in origin/main`, which reads as a broken release.
        """
        repo = tmp_path / "noremote"
        repo.mkdir()
        _git(repo, "init", "-q", "-b", "main")
        _git(repo, "config", "user.email", "t@example.com")
        _git(repo, "config", "user.name", "T")
        _git(repo, "commit", "-q", "--allow-empty", "-m", "x")
        _git(repo, "tag", "v1.0.0")
        state, detail = rv.check_tag_on_main(repo, "v1.0.0")
        assert state == rv.UNVERIFIABLE
        assert "origin/main is not present" in detail

    def test_tag_off_main_fails(self, tmp_path):
        """A tag on a side branch is not a release, however real the tag is."""
        repo = _make_repo(tmp_path, version="3.2.0")
        _git(repo, "checkout", "-q", "-b", "side")
        _write(repo / "extra.txt", "x\n")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-qm", "side work")
        _git(repo, "tag", "v3.2.9")
        state, detail = rv.check_tag_on_main(repo, "v3.2.9")
        assert state == rv.FAILED
        assert "not contained in origin/main" in detail


class TestGithubRelease:
    def test_release_present_is_ok(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rv, "_run", lambda *a, **k: (0, "https://example/tag/v1", ""))
        state, detail = rv.check_github_release(tmp_path, "v1")
        assert state == rv.OK
        assert detail == "https://example/tag/v1"

    def test_absent_release_fails(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rv, "_run", lambda *a, **k: (1, "", "release not found"))
        state, detail = rv.check_github_release(tmp_path, "v1")
        assert state == rv.FAILED
        assert "the tag alone is not a release" in detail

    def test_missing_gh_is_unverifiable_not_failed(self, tmp_path, monkeypatch):
        """A machine without `gh` must not be told its release is broken."""
        monkeypatch.setattr(rv, "_run", lambda *a, **k: rv.MISSING)
        state, detail = rv.check_github_release(tmp_path, "v1")
        assert state == rv.UNVERIFIABLE
        assert "not installed" in detail

    def test_other_gh_error_is_unverifiable(self, tmp_path, monkeypatch):
        monkeypatch.setattr(rv, "_run", lambda *a, **k: (1, "", "HTTP 503 upstream"))
        state, _ = rv.check_github_release(tmp_path, "v1")
        assert state == rv.UNVERIFIABLE


class TestScrub:
    """The credential scrub is a claim `security-model.md` now makes in prose.

    Untested, deleting the `_scrub` call kept the whole suite green — which is
    how a security assertion outlives the code behind it. Red if the call site
    is removed, and red if the `except ImportError` fallback starts swallowing
    a real scrub.
    """

    _BAIT = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"

    def test_scrub_removes_a_planted_token(self):
        assert self._BAIT not in rv._scrub(f"gh: bad credentials for {self._BAIT}")

    def test_gh_error_detail_is_scrubbed_before_it_is_reported(self, tmp_path, monkeypatch):
        """The path that actually reaches stderr and the --json payload."""
        monkeypatch.setattr(
            rv, "_run", lambda *a, **k: (1, "", f"HTTP 401 using token {self._BAIT}")
        )
        state, detail = rv.check_github_release(tmp_path, "v1")
        assert state == rv.UNVERIFIABLE
        assert self._BAIT not in detail


class TestCheckReleased:
    def _stub_gh(self, monkeypatch, result):
        real = rv._run

        def fake(args, cwd):
            if args and args[0] == "gh":
                return result
            return real(args, cwd)

        monkeypatch.setattr(rv, "_run", fake)

    # `_make_repo` mirrors prawduct's real layout, which includes a `toml`
    # version file — unreadable below 3.11, where this check reports
    # `unverifiable` by design. The full-verification outcome is therefore
    # interpreter-dependent; `test_the_floor_leg_degrades_instead_of_failing`
    # pins what the 3.10 leg sees instead, so the floor still proves something.
    @needs_tomllib
    def test_complete_release_exits_zero(self, tmp_path, monkeypatch, capsys):
        repo = _make_repo(tmp_path, version="3.2.0")
        self._stub_gh(monkeypatch, (0, "https://example/v3.2.0", ""))
        assert rv.check_released(repo, "v3.2.0") == 0
        out = capsys.readouterr().out
        assert "released: v3.2.0" in out
        assert "3 of 3 verified" in out

    def test_a_non_repository_composes_to_unverified_not_not_released(
        self, tmp_path, monkeypatch, capsys
    ):
        """The acceptance criterion is about the COMPOSED verdict, and the
        per-check tests do not reach it.

        `check_released` aggregates three states into one exit code, and the
        rule that decides the criterion — `if failed: not-released` before
        `elif unverifiable: unverified` — lives here, not in the checks. So a
        single check regressing to `FAILED` flips the whole verdict back to the
        #579 behaviour while every per-check test stays green.

        `gh` is stubbed absent so the network is never touched; the two local
        checks run for real against an empty directory, which is the repro.
        """
        self._stub_gh(monkeypatch, rv.MISSING)
        code = rv.check_released(tmp_path, "v3.2.4")
        assert code == rv.EXIT_UNVERIFIABLE, (
            f"a non-repository composed to exit {code}; exit 1 is the false red "
            "this chunk exists to remove, and exit 0 would hide it entirely"
        )
        err = capsys.readouterr().err
        assert "unverified: v3.2.4" in err
        assert "not-released" not in err
        assert "not a git repository" in err

    # `_make_repo` mirrors prawduct's real layout, which includes a `toml`
    # version file — unreadable below 3.11, where this check reports
    # `unverifiable` by design. The full-verification outcome is therefore
    # interpreter-dependent; `test_the_floor_leg_degrades_instead_of_failing`
    # pins what the 3.10 leg sees instead, so the floor still proves something.
    @needs_tomllib
    def test_accepts_bare_version(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path, version="3.2.0")
        self._stub_gh(monkeypatch, (0, "https://example/v3.2.0", ""))
        assert rv.check_released(repo, "3.2.0") == 0

    def test_missing_github_release_exits_one(self, tmp_path, monkeypatch, capsys):
        repo = _make_repo(tmp_path, version="3.2.0")
        self._stub_gh(monkeypatch, (1, "", "release not found"))
        assert rv.check_released(repo, "v3.2.0") == 1
        err = capsys.readouterr().err
        assert "not-released: v3.2.0" in err
        assert "github-release" in err

    def test_unverifiable_is_its_own_exit_code_not_success(self, tmp_path, monkeypatch, capsys):
        """The finding that inverted the first design.

        `gh` absent, everything else good. This used to exit 0 — which made the
        gate green in exactly the environment it exists for, since a tag-push
        job without a token gets a `gh` that cannot answer. Red if
        EXIT_UNVERIFIABLE collapses back into 0.

        Asserted against the **literal 3**, not against `rv.EXIT_UNVERIFIABLE`.
        Comparing the return value to the very constant under test passes for
        whatever value that constant takes — including the 0 this docstring
        names as its red-trigger, because the human-output branch keys off the
        same constant and would still print "unverified". A guard that cannot
        fail for the regression it names is not a guard.
        """
        repo = _make_repo(tmp_path, version="3.2.0")
        self._stub_gh(monkeypatch, rv.MISSING)
        assert rv.check_released(repo, "v3.2.0") == 3
        assert rv.EXIT_UNVERIFIABLE == 3, "the published exit-code contract moved"
        captured = capsys.readouterr()
        assert "unverified: v3.2.0" in captured.err
        assert "could not run" in captured.err

    def test_allow_unverifiable_opts_back_into_zero(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path, version="3.2.0")
        self._stub_gh(monkeypatch, rv.MISSING)
        assert rv.check_released(repo, "v3.2.0", allow_unverifiable=True) == 0

    def test_ci_shaped_checkout_without_origin_main_is_not_green(self, tmp_path, monkeypatch):
        """`actions/checkout` on a tag has no `origin/main`. That must not pass.

        This is the CI case Chunk 05 builds on, and the first design exited 0
        for it while the Releases page could be empty.
        """
        repo = _make_repo(tmp_path, version="3.2.0")
        _git(repo, "update-ref", "-d", "refs/remotes/origin/main")
        self._stub_gh(monkeypatch, (0, "https://example/v3.2.0", ""))
        # Literal, for the reason spelled out on the sibling test above.
        assert rv.check_released(repo, "v3.2.0") == 3

    def test_unauthenticated_gh_is_not_read_as_absence(self, tmp_path, monkeypatch):
        """A refused question is not a missing release."""
        repo = _make_repo(tmp_path, version="3.2.0")
        self._stub_gh(monkeypatch, (1, "", "gh: To use GitHub CLI, authenticate with gh auth login"))
        assert rv.check_released(repo, "v3.2.0") == 3

    def test_json_output_carries_every_check(self, tmp_path, monkeypatch, capsys):
        repo = _make_repo(tmp_path, version="3.2.0")
        self._stub_gh(monkeypatch, (1, "", "release not found"))
        assert rv.check_released(repo, "v3.2.0", json_output=True) == 1
        payload = json.loads(capsys.readouterr().out)
        assert payload["release"] == "v3.2.0"
        assert payload["verdict"] == "not-released"
        assert {c["check"] for c in payload["checks"]} == {
            "version-files",
            "tag-on-main",
            "github-release",
        }


class TestCli:
    """The wrapper's own contract. Exercised through the real hook, because the
    argument scan and the exit-code mapping live there and nowhere else.

    **Pointed at an isolated project dir on purpose.** ``main()`` resolves
    ``get_project_dir()`` and runs the binary-skew check *before* dispatch, so a
    bare ``subprocess.run`` with no ``cwd`` aims the real hook at this working
    repository — reading, and potentially writing, live ``.prawduct/`` state from
    inside the test suite. Tests are independent or they are not tests.
    """

    def _run(self, tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
        project = tmp_path / "isolated"
        project.mkdir(exist_ok=True)
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)}
        return subprocess.run(
            [sys.executable, str(HOOK), "check-released", *args],
            capture_output=True,
            text=True,
            timeout=20,
            cwd=str(project),
            env=env,
        )

    def test_no_version_is_usage_error(self, tmp_path):
        result = self._run(tmp_path)
        assert result.returncode == 2
        assert "a version argument is required" in result.stderr

    def test_unknown_flag_is_usage_error_not_ignored(self, tmp_path):
        result = self._run(tmp_path, "v1.0.0", "--bogus")
        assert result.returncode == 2
        assert "unknown argument: --bogus" in result.stderr

    def test_second_version_is_usage_error(self, tmp_path):
        result = self._run(tmp_path, "v1.0.0", "v2.0.0")
        assert result.returncode == 2
        assert "unexpected second version" in result.stderr
