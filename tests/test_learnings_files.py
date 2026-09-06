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
        assert layout.state != lf.STATE_NEW

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
        assert layout.state == lf.STATE_NEW

    def test_both(self, tmp_path):
        _rules(tmp_path, "core.md", lf.CORE_HEADER)
        _legacy(tmp_path)
        layout = lf.resolve(tmp_path)
        assert layout.state == lf.STATE_BOTH
        # A repo mid-migration has migrated nothing yet, and reading it as
        # migrated is what would silence the fold directive.
        assert layout.state != lf.STATE_NEW

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


# ---------------------------------------------------------------------------
# Rule units and their hashes — the join key the ledger events are about
# ---------------------------------------------------------------------------


class TestRuleUnits:
    def test_headings_below_the_title_are_units(self):
        text = (
            "# Learnings — core\n"
            "\n"
            "## Unsorted\n"
            "\n"
            "### First rule\n"
            "Some narrative body.\n"
            "\n"
            "### Second rule\n"
        )
        assert lf.rule_units(text) == ["Unsorted", "First rule", "Second rule"]

    def test_top_level_bullets_are_units_and_indented_ones_are_not(self):
        text = (
            "# Rules\n"
            "\n"
            "- a bullet rule\n"
            "  - a continuation, not its own rule\n"
            "- another bullet rule\n"
        )
        assert lf.rule_units(text) == ["a bullet rule", "another bullet rule"]

    def test_mixed_corpus_keeps_document_order(self):
        text = (
            "# Rules\n"
            "\n"
            "## Section\n"
            "- bullet one\n"
            "\n"
            "### Heading rule\n"
            "- bullet two\n"
        )
        assert lf.rule_units(text) == [
            "Section", "bullet one", "Heading rule", "bullet two",
        ]

    def test_the_title_is_never_a_unit(self):
        """Excluded by LEVEL, not by position — so a file whose first heading is
        a rule keeps that rule."""
        assert "Learnings — core" not in lf.rule_units(lf.CORE_HEADER)
        assert lf.rule_units("## a rule with no title above it\n") == [
            "a rule with no title above it"
        ]

    def test_the_scaffold_obligation_header_is_not_a_unit(self):
        """`CORE_HEADER` is a title plus a bold paragraph. A freshly scaffolded
        repo must have ZERO rules, or its first Stop records a rule nobody
        wrote and the corpus reads as used from the moment it is created."""
        assert lf.rule_units(lf.CORE_HEADER) == []

    def test_frontmatter_contributes_no_units(self):
        text = _area("  - src/**\n", body="\n# Area\n\n### the only rule\n")
        assert lf.rule_units(text) == ["the only rule"]

    def test_fenced_code_is_not_scanned(self):
        """A `#` comment or a `- ` item inside a fence is an illustration. A
        unit minted from one can never be cited, so it would sit in
        "rules that never fired" forever."""
        text = (
            "# Rules\n"
            "\n"
            "### a real rule\n"
            "\n"
            "```bash\n"
            "## not a heading\n"
            "- not a bullet rule\n"
            "```\n"
            "\n"
            "### another real rule\n"
        )
        assert lf.rule_units(text) == ["a real rule", "another real rule"]

    def test_tilde_fences_close_on_their_own_marker(self):
        text = "# R\n\n~~~\n### inside\n~~~\n\n### outside\n"
        assert lf.rule_units(text) == ["outside"]

    def test_deeper_headings_are_not_units(self):
        """`####` and below are structure within a rule, not rules."""
        assert lf.rule_units("# R\n\n#### deep\n") == []

    def test_empty_headings_are_dropped(self):
        assert lf.rule_units("# R\n\n###   \n\n### real\n") == ["real"]


class TestUnitHash:
    def test_stable_across_case_and_whitespace_and_trailing_punctuation(self):
        base = "When a fix lands, sweep the neighbouring prose"
        for variant in (
            "when a fix lands, sweep the neighbouring prose",
            "WHEN A FIX LANDS, SWEEP THE NEIGHBOURING PROSE",
            "When a fix   lands,\n  sweep the neighbouring prose",
            "When a fix lands, sweep the neighbouring prose.",
            "  When a fix lands, sweep the neighbouring prose —  ",
            "When a fix lands, sweep the neighbouring prose…",
            "When a fix lands, sweep the neighbouring prose`",
        ):
            assert lf.unit_hash(variant) == lf.unit_hash(base), variant

    def test_two_real_headings_hash_differently(self):
        a = "When a review finds the SAME class twice, stop fixing instances"
        b = "When a review finds the SAME class twice, stop fixing instance"
        assert lf.unit_hash(a) != lf.unit_hash(b)

    def test_shape(self):
        h = lf.unit_hash("anything")
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_rewording_mints_a_new_id(self):
        """Deliberate: "this rule has never fired" must not be answered from
        text the corpus no longer carries."""
        assert lf.unit_hash("Verify, do not guess") != lf.unit_hash(
            "Verify; never guess"
        )


class TestUnitCitation:
    def test_opening_words_only(self):
        unit = "one two three four five six seven eight nine ten"
        assert lf.unit_citation(unit) == "one two three four five six seven eight"

    def test_a_short_unit_is_its_whole_self(self):
        assert lf.unit_citation("Verify, do not guess.") == "verify, do not guess"

    def test_empty_unit_yields_no_citation(self):
        """`""` is in every string — a caller must not treat it as a match."""
        assert lf.unit_citation("   ") == ""

    def test_a_unit_too_short_to_quote_yields_no_citation(self):
        """A section banner is a unit by the same grammar every rule is. One
        word is not a citation, and letting it be one reports a rule as
        exercised by every review that happens to use the word."""
        assert lf.unit_citation("Unsorted") == ""
        assert lf.unit_citation("Two words") == ""
        assert lf.unit_citation("Three words here") == "three words here"

    def test_an_uncitable_unit_still_has_a_hash(self):
        """It can be WRITTEN, it just cannot be cited — the two are separate
        questions and a shared "is this a rule" answer would drop it from the
        corpus the never-fired join is taken over."""
        assert lf.unit_hash("Unsorted")

    def test_citation_is_the_normalized_form(self):
        assert lf.unit_citation("  When A Fix   LANDS  ") == "when a fix lands"

    def test_the_cut_drops_its_own_trailing_punctuation(self):
        """The eighth word routinely ends in a comma, and the finding text a
        citation is matched against has had ITS trailing punctuation stripped —
        so a citation quoted at the very end of a finding would otherwise miss
        on a character neither side kept."""
        unit = "one two three four five six seven eight, nine ten"
        assert lf.unit_citation(unit) == "one two three four five six seven eight"
        assert lf.unit_citation(unit) in lf.normalize_unit(
            "as the rule says: One two three four five six seven eight."
        )


class TestAgainstTheRealCorpus:
    """A collision check against real DATA, not a fixture.

    A fixture encodes my belief about what a rules corpus looks like, so a
    suite made only of them is green exactly where the belief is wrong. This
    reads the repo's own `core.md` through the resolver's own path constants —
    the file the framework actually ships and grows — and asserts the property
    the whole join rests on: distinct rules get distinct ids.
    """

    def _core(self) -> Path:
        return Path(__file__).resolve().parent.parent / lf.RULES_DIR_REL / lf.CORE_NAME

    def test_the_real_core_file_is_where_the_resolver_says(self):
        """The reachability assert. Without it every assertion below passes
        vacuously on a checkout where the corpus moved or is not present."""
        assert self._core().is_file(), (
            f"{self._core()} is missing — this repo's own learnings corpus is "
            "the fixture for the collision check, and its absence makes the "
            "check pass without reading anything"
        )

    def test_every_unit_of_the_real_corpus_hashes_uniquely(self):
        units = lf.rule_units(self._core().read_text(encoding="utf-8"))
        # Well above zero: this repo's corpus is hundreds of rules, and a
        # parser that silently returned a handful would satisfy any bare
        # non-empty assertion.
        assert len(units) > 100, f"only {len(units)} units parsed from the real core.md"
        hashes = [lf.unit_hash(u) for u in units]
        collisions = {h for h in hashes if hashes.count(h) > 1}
        assert not collisions, (
            f"{len(collisions)} unit hash(es) collide in the real corpus — the "
            "'which rules never fired' join is keyed on this id, so a collision "
            "reports one rule as fired because a different one was cited"
        )

    def test_every_real_RULE_has_a_citation_key(self):
        """Uncitable units exist by design (a section banner), so this asserts
        the split rather than a blanket truth: the corpus's rules are citable,
        and the handful that are not are the ones too short to quote."""
        units = lf.rule_units(self._core().read_text(encoding="utf-8"))
        citable = [u for u in units if lf.unit_citation(u)]
        uncitable = [u for u in units if not lf.unit_citation(u)]
        assert len(citable) > 100, f"only {len(citable)} citable units"
        for unit in uncitable:
            assert len(lf.normalize_unit(unit).split()) < lf.MIN_CITATION_WORDS, (
                f"{unit!r} is long enough to quote but produced no citation"
            )
        # No citation is ever the empty string, which would match every finding.
        assert all(lf.unit_citation(u) for u in citable)

    def test_the_real_title_and_obligation_header_are_excluded(self):
        units = lf.rule_units(self._core().read_text(encoding="utf-8"))
        assert not any(u.startswith("Learnings —") for u in units)
        assert not any("Reading a rule is not applying it" in u for u in units)
