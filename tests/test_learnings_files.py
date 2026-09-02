"""Tests for the learnings resolver — the one place that knows the rules layout.

Three things are asserted, in rough order of how much a wrong answer costs:

1. **The matcher agrees with the harness.** Every glob in the harness's own
   documented table is exercised on both sides — a path it must match and a path
   it must not. A matcher that under-matches is an area file the Critic never
   opens while the session had it in context, which is the cross-check going
   quietly dark; a matcher that over-matches only wastes a read. The pairs below
   pin both directions anyway, because "over-matching is cheap" stops being true
   the moment a budget gate sizes what a diff pulled in.
2. **The four states are told apart** — a repo mid-migration (``both``) must not
   read as migrated, and an empty leftover directory must not either.
3. **The scaffold never overwrites**, because from a product's second session on
   ``core.md`` is authored content nobody else holds a copy of.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Self-sufficient on sys.path — don't depend on another test module having
# inserted the plugin root first.
_PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_ROOT))

from lib import learnings_files as lf  # noqa: E402


def _rules(root: Path, name: str, text: str) -> Path:
    path = root / lf.RULES_DIR_REL / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _legacy(root: Path, text: str = "# Learnings\n") -> Path:
    path = root / lf.LEGACY_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _area(globs: str, body: str = "\n## a rule\n") -> str:
    return f"---\npaths:\n{globs}\n---\n{body}"


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    def test_block_list(self):
        globs, body = lf.parse_frontmatter(
            '---\npaths:\n  - "src/**"\n  - web/**\n---\n\n# Web\n'
        )
        assert globs == ["src/**", "web/**"]
        assert body.strip() == "# Web"

    def test_inline_list(self):
        globs, _ = lf.parse_frontmatter('---\npaths: ["src/**", \'web/**\']\n---\n')
        assert globs == ["src/**", "web/**"]

    def test_bare_scalar(self):
        globs, _ = lf.parse_frontmatter("---\npaths: src/**\n---\n")
        assert globs == ["src/**"]

    def test_brace_expansion(self):
        globs, _ = lf.parse_frontmatter('---\npaths:\n  - "src/{a,b}/**"\n---\n')
        assert globs == ["src/a/**", "src/b/**"]

    def test_nested_brace_expansion(self):
        globs, _ = lf.parse_frontmatter("---\npaths: [src/{a,b{c,d}}/**]\n---\n")
        assert globs == ["src/a/**", "src/bc/**", "src/bd/**"]

    def test_block_list_item_with_a_trailing_comment(self):
        # `- "src/**" # web` ends in `b`, so a reader that decides "is this
        # quoted?" from the last character keeps the quote marks — and the glob
        # then demands literal `"` characters and matches no path at all.
        globs, _ = lf.parse_frontmatter('---\npaths:\n  - "src/**" # web\n---\n')
        assert globs == ["src/**"]
        assert lf.matches(globs, ["src/a.py"])

    def test_inline_list_with_a_trailing_comment(self):
        # Same defect, plus a stray `]`: `value.strip("[]")` only reaches the
        # ends, so the bracket survives inside the trailing comment.
        globs, _ = lf.parse_frontmatter('---\npaths: ["src/**"] # web\n---\n')
        assert globs == ["src/**"]
        assert lf.matches(globs, ["src/a.py"])

    def test_a_hash_inside_quotes_is_not_a_comment(self):
        globs, _ = lf.parse_frontmatter('---\npaths:\n  - "src/#tmp/**"\n---\n')
        assert globs == ["src/#tmp/**"]
        assert lf.matches(globs, ["src/#tmp/a.py"])

    def test_a_bare_hash_not_preceded_by_space_is_not_a_comment(self):
        # YAML's rule, and the reason the cut is not simply "the first unquoted
        # `#`": that would truncate this glob to `src/` and silently widen it.
        globs, _ = lf.parse_frontmatter("---\npaths: src/#tmp/**\n---\n")
        assert globs == ["src/#tmp/**"]

    def test_a_comment_on_the_paths_key_line_does_not_hide_the_block_list(self):
        globs, _ = lf.parse_frontmatter(
            '---\npaths: # the areas this file scopes\n  - "src/**"\n---\n'
        )
        assert globs == ["src/**"]

    def test_inline_list_splits_around_brace_groups_not_through_them(self):
        # `"a,b".split(",")` on an inline list tears `{a,b}` into nonsense globs
        # that then silently match nothing — the under-match this module's whole
        # contract is about.
        globs, _ = lf.parse_frontmatter('---\npaths: ["src/{a,b}/**", "web/**"]\n---\n')
        assert globs == ["src/a/**", "src/b/**", "web/**"]

    def test_unbalanced_brace_is_literal_not_an_error(self):
        # A malformed pattern should scope its own file oddly; it must never
        # raise inside session start.
        globs, _ = lf.parse_frontmatter("---\npaths: src/{a,b/**\n---\n")
        assert globs == ["src/{a,b/**"]

    def test_absent_frontmatter_is_no_globs_and_whole_body(self):
        text = "# Learnings — core\n\n## a rule\n"
        assert lf.parse_frontmatter(text) == ([], text)

    def test_body_is_a_verbatim_slice_of_the_input(self):
        text = '---\npaths: ["src/**"]\n---\n\n## a rule\n\nbody text\n'
        _globs, body = lf.parse_frontmatter(text)
        assert body == "\n## a rule\n\nbody text\n"
        assert text.endswith(body)

    def test_frontmatter_without_paths_key(self):
        globs, body = lf.parse_frontmatter("---\ndescription: notes\n---\nbody\n")
        assert globs == []
        assert body.strip() == "body"

    def test_other_keys_and_nesting_do_not_leak_into_paths(self):
        globs, _ = lf.parse_frontmatter(
            '---\ndescription: x\npaths:\n  - "src/**"\nother:\n  - "nope/**"\n---\n'
        )
        assert globs == ["src/**"]

    def test_block_must_open_on_the_first_line(self):
        # `plan_index` tolerates an HTML-comment header before a build plan's
        # frontmatter. The harness does not, so neither does this: a block it
        # would not read must not be read here as scoping the file.
        text = '<!-- note -->\n---\npaths:\n  - "src/**"\n---\nbody\n'
        globs, body = lf.parse_frontmatter(text)
        assert globs == []
        assert body == text

    def test_unterminated_frontmatter_reads_as_absent(self):
        text = '---\npaths:\n  - "src/**"\n\n# no close\n'
        assert lf.parse_frontmatter(text) == ([], text)

    def test_duplicate_globs_are_collapsed(self):
        globs, _ = lf.parse_frontmatter('---\npaths: ["src/**", "src/**"]\n---\n')
        assert globs == ["src/**"]


# ---------------------------------------------------------------------------
# Globs
# ---------------------------------------------------------------------------

#: The harness documentation's own table, plus the discovery's discodon case.
#: Each row is (glob, paths that MUST match, paths that MUST NOT).
_GLOB_CASES = [
    ("**/*.ts", ["a.ts", "src/a.ts", "src/deep/a.ts"], ["a.tsx", "src/a.js"]),
    ("src/**/*", ["src/a.ts", "src/deep/a.ts"], ["web/a.ts", "srcx/a.ts"]),
    ("*.md", ["README.md"], ["docs/README.md", "README.mdx"]),
    (
        "src/components/*.tsx",
        ["src/components/Button.tsx"],
        ["src/components/ui/Button.tsx", "web/src/components/Button.tsx"],
    ),
    (
        "discodon/eval/**",
        ["discodon/eval/report.py", "discodon/eval/sub/x.py"],
        ["discodon/evaluate.py", "discodon/eval.py"],
    ),
]


class TestGlobToRegex:
    @pytest.mark.parametrize("glob,hits,misses", _GLOB_CASES, ids=[c[0] for c in _GLOB_CASES])
    def test_documented_semantics(self, glob, hits, misses):
        rx = lf.glob_to_regex(glob)
        for path in hits:
            assert rx.match(path), f"{glob!r} must match {path!r}"
        for path in misses:
            assert not rx.match(path), f"{glob!r} must not match {path!r}"

    def test_question_mark_is_one_character_within_a_segment(self):
        rx = lf.glob_to_regex("src/?.ts")
        assert rx.match("src/a.ts")
        assert not rx.match("src/ab.ts")
        assert not rx.match("src/a/.ts")

    def test_dots_are_literal_not_any_character(self):
        rx = lf.glob_to_regex("*.md")
        assert not rx.match("READMEXmd")

    def test_matching_is_anchored_at_both_ends(self):
        rx = lf.glob_to_regex("src/*.py")
        assert not rx.match("vendor/src/a.py")
        assert not rx.match("src/a.py.bak")

    def test_leading_dot_slash_is_normalized_on_both_sides(self):
        assert lf.matches(["src/**"], ["./src/a.py"])
        globs, _ = lf.parse_frontmatter("---\npaths: ./src/**\n---\n")
        assert lf.matches(globs, ["src/a.py"])

    def test_matches_is_false_for_no_changed_paths(self):
        assert not lf.matches(["src/**"], [])

    def test_matches_accepts_path_objects(self):
        assert lf.matches(["src/**"], [Path("src/a.py")])


# ---------------------------------------------------------------------------
# resolve — the four states
# ---------------------------------------------------------------------------


class TestResolveStates:
    def test_none(self, tmp_path):
        layout = lf.resolve(tmp_path)
        assert layout.state == lf.STATE_NONE
        assert layout.core is None
        assert layout.files == []
        assert not layout.migrated

    def test_legacy(self, tmp_path):
        _legacy(tmp_path)
        layout = lf.resolve(tmp_path)
        assert layout.state == lf.STATE_LEGACY
        assert layout.core is None
        assert layout.files == []

    def test_new(self, tmp_path):
        core = _rules(tmp_path, "core.md", lf.CORE_HEADER)
        layout = lf.resolve(tmp_path)
        assert layout.state == lf.STATE_NEW
        assert layout.core == core
        assert layout.files == [core]
        assert layout.migrated

    def test_both(self, tmp_path):
        _rules(tmp_path, "core.md", lf.CORE_HEADER)
        _legacy(tmp_path)
        layout = lf.resolve(tmp_path)
        assert layout.state == lf.STATE_BOTH
        # A repo mid-migration has migrated nothing yet, and reading it as
        # migrated is what would silence the fold directive.
        assert not layout.migrated

    def test_an_empty_rules_directory_is_not_a_migrated_repo(self, tmp_path):
        (tmp_path / lf.RULES_DIR_REL).mkdir(parents=True)
        _legacy(tmp_path)
        assert lf.resolve(tmp_path).state == lf.STATE_LEGACY

    def test_area_files_without_core_still_read_as_new(self, tmp_path):
        _rules(tmp_path, "web.md", _area('  - "web/**"'))
        layout = lf.resolve(tmp_path)
        assert layout.state == lf.STATE_NEW
        assert layout.core is None
        assert [a.path.name for a in layout.areas] == ["web.md"]


class TestResolveContents:
    def test_areas_carry_their_globs_and_files_puts_core_first(self, tmp_path):
        _rules(tmp_path, "web.md", _area('  - "web/**"'))
        _rules(tmp_path, "api.md", _area('  - "api/**"'))
        core = _rules(tmp_path, "core.md", lf.CORE_HEADER)
        layout = lf.resolve(tmp_path)
        assert layout.files[0] == core
        assert [p.name for p in layout.files] == ["core.md", "api.md", "web.md"]
        assert [a.globs for a in layout.areas] == [["api/**"], ["web/**"]]

    def test_nested_area_files_are_found(self, tmp_path):
        # The harness loads `.claude/rules/` subdirectories recursively, so a
        # nested file is in context whether or not prawduct expected nesting —
        # and anything in context must be budgeted and reviewed.
        _rules(tmp_path, "core.md", lf.CORE_HEADER)
        nested = _rules(tmp_path, "sub/deep.md", _area('  - "deep/**"'))
        assert nested in lf.resolve(tmp_path).files

    def test_an_unreadable_area_file_is_still_listed_and_unscoped(self, tmp_path):
        _rules(tmp_path, "core.md", lf.CORE_HEADER)
        bad = tmp_path / lf.RULES_DIR_REL / "bad.md"
        bad.write_bytes(b"\xff\xfe\x00binary")
        layout = lf.resolve(tmp_path)
        assert bad in layout.files
        assert layout.areas[0].globs == []


# ---------------------------------------------------------------------------
# files_for_paths
# ---------------------------------------------------------------------------


class TestFilesForPaths:
    @pytest.fixture
    def repo(self, tmp_path):
        _rules(tmp_path, "core.md", lf.CORE_HEADER)
        _rules(tmp_path, "web.md", _area('  - "web/**"'))
        _rules(tmp_path, "api.md", _area('  - "api/**/*.py"'))
        return tmp_path

    def test_empty_changed_yields_core_only(self, repo):
        assert [p.name for p in lf.files_for_paths(lf.resolve(repo), [])] == ["core.md"]

    def test_one_matching_area(self, repo):
        got = lf.files_for_paths(lf.resolve(repo), ["web/src/App.tsx"])
        assert [p.name for p in got] == ["core.md", "web.md"]

    def test_ordering_is_core_then_areas_by_name(self, repo):
        got = lf.files_for_paths(lf.resolve(repo), ["web/a.ts", "api/x/y.py"])
        assert [p.name for p in got] == ["core.md", "api.md", "web.md"]

    def test_a_near_miss_does_not_pull_the_area_in(self, repo):
        got = lf.files_for_paths(lf.resolve(repo), ["api/x/y.ts"])
        assert [p.name for p in got] == ["core.md"]

    def test_an_unscoped_area_is_always_loaded(self, tmp_path):
        # A non-core rules file with no `paths:` is loaded by the harness on
        # every session. Excluding it here would hand the reviewer a shorter
        # list than the session actually had.
        _rules(tmp_path, "core.md", lf.CORE_HEADER)
        _rules(tmp_path, "always.md", "# always\n")
        layout = lf.resolve(tmp_path)
        assert [p.name for p in lf.files_for_paths(layout, [])] == [
            "core.md",
            "always.md",
        ]
        assert [p.name for p in lf.files_for_paths(layout, ["web/a.ts"])] == [
            "core.md",
            "always.md",
        ]

    def test_legacy_layout_yields_nothing(self, tmp_path):
        _legacy(tmp_path)
        assert lf.files_for_paths(lf.resolve(tmp_path), ["src/a.py"]) == []


# ---------------------------------------------------------------------------
# scaffold_core
# ---------------------------------------------------------------------------


class TestScaffoldCore:
    def test_creates_the_file_with_the_header(self, tmp_path):
        path = lf.scaffold_core(tmp_path)
        assert path == tmp_path / lf.RULES_DIR_REL / lf.CORE_NAME
        assert path.read_text(encoding="utf-8") == lf.CORE_HEADER

    def test_header_carries_the_descent_obligation(self):
        # The obligation is what a product actually receives — the two sentences
        # that make a read rule cost something to ignore.
        assert "Reading a rule is not applying it" in lf.CORE_HEADER
        assert "does not apply" in lf.CORE_HEADER
        # No `paths:` frontmatter: core is the always-loaded file.
        assert lf.parse_frontmatter(lf.CORE_HEADER)[0] == []

    def test_is_idempotent_and_never_overwrites(self, tmp_path):
        path = lf.scaffold_core(tmp_path)
        path.write_text(lf.CORE_HEADER + "\n## an authored rule\n", encoding="utf-8")
        again = lf.scaffold_core(tmp_path)
        assert again == path
        assert "an authored rule" in path.read_text(encoding="utf-8")

    def test_scaffolded_repo_resolves_as_new(self, tmp_path):
        lf.scaffold_core(tmp_path)
        layout = lf.resolve(tmp_path)
        assert layout.state == lf.STATE_NEW
        assert layout.files == [tmp_path / lf.RULES_DIR_REL / lf.CORE_NAME]


class TestRulesDirIsGitignored:
    """The one predicate for "will the rules tree survive a clone?"."""

    @staticmethod
    def _repo(tmp_path):
        import subprocess as sp
        sp.run(["git", "init", "-q"], cwd=tmp_path, check=True)
        return tmp_path

    def test_false_in_a_repo_that_does_not_ignore_it(self, tmp_path):
        repo = self._repo(tmp_path)
        assert lf.rules_dir_is_gitignored(repo) is False

    def test_true_when_claude_is_ignored(self, tmp_path):
        repo = self._repo(tmp_path)
        (repo / ".gitignore").write_text(".claude/\n")
        assert lf.rules_dir_is_gitignored(repo) is True

    def test_a_tracked_sibling_does_not_mask_the_answer(self, tmp_path):
        """A directory pathspec is satisfied by any tracked file beneath it;
        the question is about the NEXT file, so a tracked area file beside an
        ignored core.md must still read as ignored."""
        import subprocess as sp
        repo = self._repo(tmp_path)
        (repo / ".gitignore").write_text(".claude/\n")
        area = repo / lf.RULES_DIR_REL / "area.md"
        area.parent.mkdir(parents=True)
        area.write_text("# area\n")
        sp.run(["git", "add", "-f", str(area)], cwd=repo, check=True)
        assert lf.rules_dir_is_gitignored(repo) is True

    def test_false_outside_a_git_repo(self, tmp_path):
        assert lf.rules_dir_is_gitignored(tmp_path) is False
