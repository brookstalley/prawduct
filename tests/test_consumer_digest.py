"""Tests for `lib/consumer_digest.py` — the declared changelog the release cut writes (#733).

The module decides three things a wrong answer to would publish wrongly: what a
declaration allows the cut to write, where a new release section goes, and
which bytes of a product's own file change. So the tests pin each refusal, each
insertion rule against the heading that must not attract it, and byte equality
outside the inserted span on line-ending and BOM shapes the repo's own files
never use.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_PLUGIN = Path(__file__).resolve().parent.parent / "plugin"
if str(_PLUGIN) not in sys.path:
    sys.path.insert(0, str(_PLUGIN))

from lib import change_fragments  # noqa: E402
from lib import consumer_digest as cd  # noqa: E402


def _state(body: str) -> str:
    return f"project: x\n\nconsumer_digest:\n{body}\nother: 1\n"


def _parse(tmp_path: Path, body: str):
    return cd.parse_declaration(_state(body), tmp_path)


def _fragment(scope: str, *, kind: str = "fix", date: str = "2026-10-19", note: str | None = None,
              title: str | None = None) -> change_fragments.Fragment:
    note = note if note is not None else f"The {scope} change."
    text = (
        f"---\nschema: 1\ntype: {kind}\nscope: {scope}\ndate: {date}\ntitle: {title or scope + ' title'}\n---\n"
        f"What {scope} changed.\n\n## Consumer note\n{note}\n"
    )
    return change_fragments.parse_fragment(text, filename=f"{scope}.md")


class TestDeclaration:
    def test_undeclared_is_none_none(self, tmp_path):
        assert cd.parse_declaration("project: x\n", tmp_path) == (None, None)

    def test_an_absent_state_file_reads_as_undeclared(self, tmp_path):
        assert cd.read_declaration(tmp_path) == (None, None)

    def test_an_unreadable_state_file_is_not_undeclared(self, tmp_path):
        """It may hold a declaration; reading it as none would ship a release with no section.

        Renegotiated from "absent or unreadable reads as undeclared" (#733 review):
        an unreadable file can be told apart from an absent one, and the cut is
        the writer that would act on the wrong answer.
        """
        (tmp_path / ".prawduct" / "project-state.yaml").mkdir(parents=True)  # a directory: unreadable
        decl, reason = cd.read_declaration(tmp_path)
        assert decl is None and reason and "cannot be read" in reason
        (tmp_path / ".prawduct" / "project-state.yaml").rmdir()
        (tmp_path / ".prawduct" / "project-state.yaml").write_bytes(b"consumer_digest:\n  path: \xff\n")
        decl, reason = cd.read_declaration(tmp_path)
        assert decl is None and reason and "cannot be read" in reason

    def test_the_minimal_declaration_takes_every_default(self, tmp_path):
        decl, reason = _parse(tmp_path, "  path: CHANGELOG.md")
        assert reason is None
        assert decl == cd.Declaration(path="CHANGELOG.md")
        assert decl.heading == "## {version} - {date}" and decl.layout == "bullets" and decl.headline == "none"
        assert decl.entry_template == "- {note}"

    def test_prawducts_own_declaration_reads(self, tmp_path):
        decl, reason = _parse(
            tmp_path,
            '  path: plugin/CHANGELOG.md\n  heading: "## {version}"\n  headline: required\n  layout: paragraphs',
        )
        assert reason is None
        assert (decl.path, decl.heading, decl.headline, decl.layout) == (
            "plugin/CHANGELOG.md", "## {version}", "required", "paragraphs",
        )
        assert decl.entry_template == "**`{scope}`**: {note}"

    def test_a_quoted_hash_in_the_heading_is_data(self, tmp_path):
        decl, reason = _parse(tmp_path, '  path: CHANGELOG.md\n  heading: "## [{version_no_prefix}] - {date}"  # KaC')
        assert reason is None and decl.heading == "## [{version_no_prefix}] - {date}"

    def test_an_unquoted_heading_is_refused_and_told_to_quote_it(self, tmp_path):
        decl, reason = _parse(tmp_path, "  path: CHANGELOG.md\n  heading: ## {version}")
        assert decl is None and "quote it" in reason

    def test_types_parse_in_order(self, tmp_path):
        decl, reason = _parse(tmp_path, "  path: CHANGELOG.md\n  layout: by-type\n  types: {fix: Fixed, feature: Added}")
        assert reason is None and decl.types == (("fix", "Fixed"), ("feature", "Added"))

    @pytest.mark.parametrize(
        ("body", "says"),
        [
            ("  heading: \"## {version}\"", "needs `path`"),
            ("  path: /etc/CHANGELOG.md", "repo-relative"),
            ("  path: ../CHANGELOG.md", "repo-relative"),
            ("  path: .git/CHANGELOG.md", "must not write"),
            ("  path: .prawduct/CHANGELOG.md", "must not write"),
            # Case-folded: on a case-insensitive filesystem these ARE .git and .prawduct.
            ("  path: .GIT/CHANGELOG.md", "must not write"),
            ("  path: .Git/config", "must not write"),
            ("  path: .Prawduct/CHANGELOG.md", "must not write"),
            # A nested repository's config is as executable as the top one's.
            ("  path: vendor/lib/.git/config", "must not write"),
            ("  path: .", "must not write"),
            # Spellings some filesystem reads as `.git` / `.prawduct`, as git itself refuses.
            ("  path: .g\u200cit/config", "must not write"),
            ("  path: .git./config", "must not write"),
            ("  path: GIT~1/config", "must not write"),
            ("  path: vendor/git~2/config", "must not write"),
            ("  path: .prawduct./CHANGELOG.md", "must not write"),
            ("  path: PRAWDU~1/CHANGELOG.md", "must not write"),
            ("  path: CHANGELOG.md\n  path: OTHER.md", "given twice"),
            ("  path: CHANGELOG.md\n  colour: blue", "unknown field"),
            ("  path: CHANGELOG.md\n  layout: table", "layout"),
            ("  path: CHANGELOG.md\n  headline: maybe", "headline"),
            ("  path: CHANGELOG.md\n  heading: \"# {version}\"", "must start with `## `"),
            ("  path: CHANGELOG.md\n  heading: \"## {release}\"", "placeholder {release}"),
            ("  path: CHANGELOG.md\n  heading: \"## {version\"", "unbalanced brace"),
            ("  path: CHANGELOG.md\n  heading: \"## Release {version}\"", "must start with the version"),
            ("  path: CHANGELOG.md\n  entry: \"- {body}\"", "placeholder {body}"),
            ("  path: CHANGELOG.md\n  entry: \"- ({scope})\"", "must contain {note}"),
            ("  path: CHANGELOG.md\n  types: {fix: Fixed}", "only read by `layout: by-type`"),
            ("  path: CHANGELOG.md\n  layout: by-type\n  types: {bugs: Fixed}", "not a fragment type"),
            ("  path: CHANGELOG.md\n  layout: by-type\n  types: fix=Fixed", "one flow mapping"),
            ("  path: CHANGELOG.md\n  marker: \"\"", "marker is empty"),
            ("  path: CHANGELOG.md\n  layout: by-type\n  types: {}", "types is empty"),
            ("  just words", "not a `field: value` pair"),
        ],
    )
    def test_each_invalid_declaration_is_refused_with_its_reason(self, tmp_path, body, says):
        decl, reason = _parse(tmp_path, body)
        assert decl is None
        assert reason is not None and reason.startswith("consumer_digest:") and says in reason, reason

    def test_an_inline_value_is_unparseable_not_undeclared(self, tmp_path):
        decl, reason = cd.parse_declaration("consumer_digest: {path: CHANGELOG.md}\n", tmp_path)
        assert decl is None and reason and "cannot parse" in reason

    def test_a_symlink_out_of_the_repo_is_refused(self, tmp_path):
        repo, outside = tmp_path / "repo", tmp_path / "outside"
        repo.mkdir()
        outside.mkdir()
        (outside / "CHANGELOG.md").write_text("x")
        os.symlink(outside / "CHANGELOG.md", repo / "CHANGELOG.md")
        decl, reason = cd.parse_declaration(_state("  path: CHANGELOG.md"), repo)
        assert decl is None and "outside the repo" in reason
        # Control: the same declaration over a real file in the repo is valid.
        (repo / "CHANGELOG.md").unlink()
        (repo / "CHANGELOG.md").write_text("x")
        assert cd.parse_declaration(_state("  path: CHANGELOG.md"), repo)[1] is None


class TestVersionHeadings:
    @pytest.mark.parametrize(
        ("line", "version"),
        [
            ("## v3.7.2\n", "3.7.2"),
            ("## [1.4.0] - 2026-10-25\r\n", "1.4.0"),
            ("## 1.4.0 (unreleased)", "1.4.0"),
            ("## v3.8.0-dev.4", "3.8.0-dev.4"),
            ("## v3.7.1.1", "3.7.1.1"),
        ],
    )
    def test_a_heading_leading_with_a_version(self, line, version):
        assert cd.heading_version(line) == version

    @pytest.mark.parametrize("line", ["## [Unreleased]", "## Contents", "### 1.0.0", "## 1.0", "##1.0.0", "# 1.0.0", "text 1.0.0"])
    def test_a_line_that_is_not_a_version_heading(self, line):
        assert cd.heading_version(line) is None

    def test_names_release_is_exact_prerelease_included(self):
        assert cd.names_release("## v3.8.0", "v3.8.0")
        assert cd.names_release("## [3.8.0] - 2026-10-25", "v3.8.0")
        assert cd.names_release("## v3.8.0-rc.1", "v3.8.0-rc.1")
        # A published prerelease is history and must not block its final release.
        assert not cd.names_release("## v3.8.0-rc.1", "v3.8.0")
        assert not cd.names_release("## v3.8.0-dev.4", "v3.8.0")
        assert not cd.names_release("## v3.8.0.1", "v3.8.0")
        assert not cd.names_release("## v3.7.2", "v3.8.0")


class TestTextModel:
    @pytest.mark.parametrize(
        "data",
        [
            b"# C\n\n## v1.0.0\n\nOld.\n",
            b"# C\r\n\r\n## v1.0.0\r\n\r\nOld.\r\n",
            b"\xef\xbb\xbf# C\r\n\r\n## v1.0.0\r\nOld.",
            b"# C\r\nmixed\n## v1.0.0\rOld.\n",
            b"",
        ],
    )
    def test_reading_and_rendering_reproduces_every_byte(self, data):
        assert cd.parse_changelog(data).render().encode("utf-8") == data

    def test_the_bom_is_held_apart_and_the_eol_is_the_first_one(self):
        text = cd.parse_changelog(b"\xef\xbb\xbf# C\r\nnext\n")
        assert text.bom and text.eol == "\r\n" and text.lines[0] == "# C\r\n"

    def test_a_path_that_cannot_be_read_is_unreadable(self, tmp_path):
        (tmp_path / "CHANGELOG.md").mkdir()
        with pytest.raises(cd.DigestUnreadable):
            cd.read_changelog(tmp_path / "CHANGELOG.md")

    def test_a_dot_directory_that_only_resembles_git_is_writable(self, tmp_path):
        # Control for the case-folded refusals: `.github` is not `.git`.
        decl, reason = cd.parse_declaration(_state("  path: .github/CHANGELOG.md"), tmp_path)
        assert reason is None and decl.path == ".github/CHANGELOG.md"

    def test_invalid_utf8_is_unreadable(self):
        with pytest.raises(cd.DigestUnreadable):
            cd.parse_changelog(b"# C\n\xff\xfe\n")

    def _insert(self, data: bytes, section: list[str], marker: str | None = None) -> bytes:
        text = cd.parse_changelog(data)
        return cd.place_section(text, cd.insertion_index(text, marker), section)[0].render().encode("utf-8")

    def test_insert_above_the_newest_release_leaves_every_other_byte(self):
        data = b"\xef\xbb\xbf# Changelog\r\n\r\n## [Unreleased]\r\n\r\n## [1.3.0] - 2026-09-01\r\n- old\r\n"
        out = self._insert(data, ["## [1.4.0] - 2026-10-25", "", "- new"])
        head = b"\xef\xbb\xbf# Changelog\r\n\r\n## [Unreleased]\r\n\r\n"
        tail = b"## [1.3.0] - 2026-09-01\r\n- old\r\n"
        assert out.startswith(head) and out.endswith(tail)
        assert out[len(head):len(out) - len(tail)] == b"## [1.4.0] - 2026-10-25\r\n\r\n- new\r\n\r\n"

    def test_a_crlf_file_gets_crlf_lines_and_an_lf_writer_would_differ(self):
        data = b"# C\r\n\r\n## v1.0.0\r\nOld.\r\n"
        out = self._insert(data, ["## v1.1.0", "", "- n"])
        assert b"\n" not in out.replace(b"\r\n", b"")
        # Control: the "\n".join rewrite this replaces changes bytes outside the span.
        naive = "\n".join(data.decode().splitlines()).encode()
        assert naive != data

    def test_a_marker_places_the_section_directly_below_it(self):
        data = b"# C\n<!-- releases -->\n## v1.0.0\n"
        out = self._insert(data, ["## v1.1.0"], marker="<!-- releases -->")
        assert out == b"# C\n<!-- releases -->\n\n## v1.1.0\n\n## v1.0.0\n"

    def test_a_missing_marker_is_reported(self):
        with pytest.raises(cd.MarkerMissing):
            cd.insertion_index(cd.parse_changelog(b"# C\n## v1.0.0\n"), "<!-- releases -->")

    def test_a_subsection_heading_never_attracts_the_insert(self):
        data = b"# C\n\n### 9.9.9 notes\n\n## v1.0.0\n"
        text = cd.parse_changelog(data)
        assert text.lines[cd.insertion_index(text, None)] == "## v1.0.0\n"

    def test_with_no_version_heading_the_section_goes_at_the_end(self):
        assert self._insert(b"# C\n\nIntro.\n", ["## v1.0.0", "", "- n"]) == b"# C\n\nIntro.\n\n## v1.0.0\n\n- n\n"

    def test_at_the_end_of_a_file_without_a_trailing_newline_the_file_still_ends_without_one(self):
        out = self._insert(b"# C\r\nIntro.", ["## v1.0.0"])
        assert out == b"# C\r\nIntro.\r\n\r\n## v1.0.0"

    def test_at_index_zero_nothing_goes_before(self):
        out = self._insert(b"## v1.0.0\nOld.\n", ["## v1.1.0"])
        assert out == b"## v1.1.0\n\n## v1.0.0\nOld.\n"

    def test_an_empty_file(self):
        assert self._insert(b"", ["## v1.0.0", "", "- n"]) == b"## v1.0.0\n\n- n\n"


class TestRendering:
    def _decl(self, **kw) -> cd.Declaration:
        return cd.Declaration(path="CHANGELOG.md", **kw)

    def test_notes_are_newest_first_ties_by_scope_and_none_notes_drop(self):
        frags = [
            _fragment("b", date="2026-10-20"),
            _fragment("a", date="2026-10-20"),
            _fragment("old", date="2026-10-01"),
            _fragment("quiet", note="none: internal"),
        ]
        assert [f.scope for f in cd.ordered_notes(frags)] == ["a", "b", "old"]

    def test_paragraphs_reproduce_prawducts_section_form(self):
        decl = self._decl(heading="## {version}", headline="required", layout="paragraphs")
        frags = [_fragment("alpha", note="First.\nSecond line."), _fragment("gamma", date="2026-10-21")]
        assert cd.render_section(decl, "v3.8.0", "2026-10-25", "**Headline.** One line.", frags) == [
            "## v3.8.0", "", "**Headline.** One line.", "",
            "**`gamma`**: The gamma change.", "",
            "**`alpha`**: First.", "Second line.",
        ]

    def test_a_note_is_kept_verbatim_including_a_markdown_hard_break(self):
        decl = self._decl(layout="paragraphs")
        out = cd.render_section(decl, "v1.0.0", "2026-10-25", None, [_fragment("s", note="Line one.  \nLine two.")])
        assert out[-2:] == ["**`s`**: Line one.  ", "Line two."]

    def test_a_paragraph_note_that_opens_a_list_starts_below_its_label(self):
        # Glued to the label, the first item renders as inline text and only the rest as a list.
        decl = self._decl(layout="paragraphs")
        for opener in ("- ", "* ", "1. ", "2) "):
            note = f"{opener}First item.\n  Wrapped.\n{opener}Second item."
            out = cd.render_section(decl, "v1.0.0", "2026-10-25", None, [_fragment("s", note=note)])
            assert out[2:] == ["**`s`**:", "", f"{opener}First item.", "  Wrapped.", f"{opener}Second item."]

    def test_a_paragraph_note_that_merely_mentions_a_dash_stays_on_its_label_line(self):
        decl = self._decl(layout="paragraphs")
        for note in ("-1 is now refused.", "Line one.\n- a later item."):
            out = cd.render_section(decl, "v1.0.0", "2026-10-25", None, [_fragment("s", note=note)])
            assert out[2] == f"**`s`**: {note.splitlines()[0]}"

    def test_a_list_note_under_a_template_with_nothing_before_the_note_gains_no_blank_line(self):
        decl = self._decl(layout="paragraphs", entry="{note}\n({scope})")
        out = cd.render_section(decl, "v1.0.0", "2026-10-25", None, [_fragment("s", note="- One.")])
        assert out[2:] == ["- One.", "(s)"]

    def test_a_headline_is_kept_verbatim_inside_its_trimmed_edges(self):
        decl = self._decl(headline="required")
        out = cd.render_section(decl, "v1.0.0", "2026-10-25", "\n**Big.** Line one.  \nLine two.\n\n", [])
        assert out == ["## v1.0.0 - 2026-10-25", "", "**Big.** Line one.  ", "Line two."]

    def test_bullets_keep_a_multi_line_note_one_item(self):
        decl = self._decl()
        frags = [_fragment("a", note="Line one.\n\nLine three.")]
        assert cd.render_section(decl, "v1.4.0", "2026-10-25", None, frags) == [
            "## v1.4.0 - 2026-10-25", "", "- Line one.", "", "  Line three.",
        ]

    def test_by_type_default_map_and_order(self):
        decl = self._decl(heading="## [{version_no_prefix}] - {date}", layout="by-type")
        frags = [
            _fragment("deps", kind="chore", note="Bumped."),
            _fragment("login", kind="fix", note="Login fixed."),
            _fragment("search", kind="feature", note="Search."),
            _fragment("quiet", kind="docs", note="none: internal"),
        ]
        assert cd.render_section(decl, "v1.4.0", "2026-10-25", None, frags) == [
            "## [1.4.0] - 2026-10-25", "",
            "### Added", "", "- Search.", "",
            "### Fixed", "", "- Login fixed.", "",
            "### Changed", "", "- Bumped.",
        ]

    def test_a_declared_map_orders_subsections_and_an_unmapped_type_falls_into_changed(self):
        decl = self._decl(layout="by-type", types=(("fix", "Bug fixes"), ("feature", "New")))
        frags = [_fragment("s", kind="feature", note="S."), _fragment("p", kind="perf", note="Faster.")]
        out = cd.render_section(decl, "v1.0.0", "2026-10-25", None, frags)
        assert out[2:] == ["### New", "", "- S.", "", "### Changed", "", "- Faster."]

    def test_an_entry_template_renders_every_placeholder_and_literal_braces(self):
        decl = self._decl(entry="- {note} ({scope}, {type}: {title}) {{x}}")
        out = cd.render_section(decl, "v1.0.0", "2026-10-25", None, [_fragment("s", title="T")])
        assert out[-1] == "- The s change. (s, fix: T) {x}"

    def test_a_none_only_release_is_heading_and_headline(self):
        decl = self._decl(headline="required")
        out = cd.render_section(decl, "v1.0.0", "2026-10-25", "Quiet release.", [_fragment("q", note="none: x")])
        assert out == ["## v1.0.0 - 2026-10-25", "", "Quiet release."]

    def test_a_rendered_heading_is_recognised_by_the_next_cut(self):
        for heading in ("## {version}", "## {version} - {date}", "## [{version_no_prefix}] - {date}"):
            line = cd.render_section(self._decl(heading=heading), "v1.4.0", "2026-10-25", None, [])[0]
            assert cd.names_release(line, "v1.4.0"), heading

    def test_release_file_rel(self):
        assert cd.release_file_rel("v1.4.0") == ".prawduct/releases/v1.4.0.md"



class TestSharedAnswers:
    """The answers the cut asks for instead of computing again (#733 review)."""

    def test_place_section_reports_the_line_its_heading_lands_on(self):
        for data, expected in ((b"# C\n## v1.0.0\n", 3), (b"# C\n\n## v1.0.0\n", 3), (b"## v1.0.0\n", 1), (b"# C", 3)):
            text = cd.parse_changelog(data)
            placed, line = cd.place_section(text, cd.insertion_index(text, None), ["## v1.1.0"])
            assert placed.render().splitlines()[line - 1] == "## v1.1.0", data

    def test_a_headline_is_published_exactly_when_its_rendered_lines_are_in_the_release(self):
        decl = cd.Declaration(path="CHANGELOG.md", headline="required")
        headline = "\r\n**Big.** Line one.  \r\nLine two.\r\n"
        release = cd.release_file_text(cd.render_section(decl, "v1.0.0", "2026-10-25", headline, []))
        assert cd.headline_published(headline, release)
        assert not cd.headline_published("A different headline.", release)
        assert not cd.headline_published("", release)
        # A committed release file an editor trimmed still holds the published headline.
        trimmed = "\n".join(line.rstrip() for line in release.splitlines()) + "\n"
        assert trimmed != release and cd.headline_published(headline, trimmed)

    def test_the_release_file_text_is_lf_terminated(self):
        assert cd.release_file_text(["## v1.0.0", "", "- n"]) == "## v1.0.0\n\n- n\n"


class TestTheHeadlineFileReader:
    def _with(self, tmp_path, data: bytes | None) -> cd.HeadlineRead:
        if data is not None:
            (tmp_path / ".prawduct").mkdir(exist_ok=True)
            (tmp_path / ".prawduct" / "release-headline.md").write_bytes(data)
        return cd.read_headline(tmp_path)

    def test_each_state(self, tmp_path):
        assert self._with(tmp_path / "a", None) == cd.HeadlineRead(None, "is absent")
        (tmp_path / "b").mkdir()
        assert self._with(tmp_path / "b", b"\n  \n") == cd.HeadlineRead(None, "is empty")
        (tmp_path / "c").mkdir()
        bad = self._with(tmp_path / "c", b"\xff\xfe\n")
        assert bad.unreadable and bad.text is None and bad.problem.startswith("cannot be read")
        (tmp_path / "d").mkdir()
        good = self._with(tmp_path / "d", b"\n  **Big.** Line one.  \r\nTwo.\r\n")
        assert not good.unreadable and good.problem is None and good.first_line == "**Big.** Line one."

    def test_release_sections_are_exact(self):
        text = cd.parse_changelog(b"# C\n\n## v1.4.0-rc.1\n\n## v1.4.0\n\n### v1.4.0\n")
        assert cd.release_sections(text, "v1.4.0") == [(5, "## v1.4.0")]


def test_the_declaration_has_one_reader():
    """CD2: Phase 0, the cut and the retired-claims check read `consumer_digest:`
    only through `read_declaration`.

    A second reader (say, one parsing the key straight from a tag's tree, as
    `release_verification` does for its own key) would reopen the two-homes split
    #733 closed, under a name the deleted-names pin cannot know.
    """
    import re as _re

    lib = _PLUGIN / "lib"
    sources = {p.name: p.read_text(encoding="utf-8") for p in sorted(lib.glob("*.py"))}
    sources["prawduct-hook"] = (_PLUGIN / "bin" / "prawduct-hook").read_text(encoding="utf-8")
    # This key, spelled as a literal or through the module's constant; another
    # module's own `_DECLARATION_KEY` names a different key.
    reader = _re.compile(
        r"read_(?:yaml_block|str_yaml_key|block_sequence)\([^)]*(?:[\"']consumer_digest[\"']|(?<![\w])DECLARATION_KEY)"
    )
    hits = sorted(name for name, text in sources.items() if reader.search(text))
    assert hits == ["consumer_digest.py"], hits
    users = sorted(name for name, text in sources.items() if "consumer_digest.read_declaration(" in text)
    # retired_claims asks which file is the declared changelog, to treat it as history.
    assert users == ["change_cut.py", "release_readiness.py", "retired_claims.py"], users
