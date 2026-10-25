"""Tests for `lib/change_fragments.py` — the one-file-per-scope change record.

The fragment format is persisted state every later reader depends on, so each
refusal code has a fixture that must produce it, and every fixture is built by
changing one thing in a valid fragment: the valid base is what proves the
change alone caused the refusal.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib import change_fragments as cf  # noqa: E402
from lib import change_log  # noqa: E402

FRONT = {
    "schema": "1",
    "type": "fix",
    "scope": "backlog-file-path",
    "date": "2026-10-17",
    "title": "backlog file writes only to its own repo",
}
NARRATIVE = "Four fixes on the `backlog file` path.\n\n### Details\nThe refusal runs first."
NOTE = "**`backlog file` writes only to this repo's own tracker.**"


def fragment_text(front=None, *, extra_lines=(), narrative=NARRATIVE, note=NOTE, note_heading=True):
    """A valid fragment, or one with exactly the given departures from it."""
    keys = dict(FRONT if front is None else front)
    lines = ["---", *(f"{k}: {v}" for k, v in keys.items()), *extra_lines, "---", narrative, ""]
    if note_heading:
        lines += ["## Consumer note", note]
    return "\n".join(lines) + "\n"


def codes(text, filename="backlog-file-path.md"):
    try:
        fragment = cf.parse_fragment(text, filename=filename)
    except cf.FragmentError as exc:
        return [exc.problem.code]
    return [p.code for p in cf.validate_fragment(fragment)]


def without(key):
    return {k: v for k, v in FRONT.items() if k != key}


def with_(key, value):
    return {**FRONT, key: value}


class TestValid:
    def test_the_base_fragment_is_valid(self):
        assert codes(fragment_text()) == []

    def test_both_backlog_id_shapes_are_accepted_in_closes(self):
        text = fragment_text(with_("closes", "[brookstalley/prawduct#1004, BKL-6J2X]"))
        fragment = cf.parse_fragment(text, filename="backlog-file-path.md")
        assert cf.validate_fragment(fragment) == []
        assert fragment.closes == ("brookstalley/prawduct#1004", "BKL-6J2X")

    def test_a_hash_inside_a_value_is_kept_and_a_spaced_comment_is_dropped(self):
        text = fragment_text(with_("closes", "[brookstalley/prawduct#1004]  # the 422 bug"))
        fragment = cf.parse_fragment(text, filename="backlog-file-path.md")
        assert fragment.closes == ("brookstalley/prawduct#1004",)

    def test_a_none_note_has_a_reason_and_no_consumer_text(self):
        fragment = cf.parse_fragment(
            fragment_text(note="none: test-only change"), filename="backlog-file-path.md"
        )
        assert cf.validate_fragment(fragment) == []
        assert fragment.none_reason == "test-only change"
        assert fragment.consumer_text is None

    @pytest.mark.parametrize("scope", ["release-v3.7.1", "dev-track-bump-3.7.1-dev.2"])
    def test_a_version_named_scope_is_a_valid_slug(self, scope):
        assert codes(fragment_text(with_("scope", scope)), filename=f"{scope}.md") == []

    def test_every_scope_this_repo_has_recorded_is_a_valid_slug(self):
        # The migration carries legacy scopes into filenames unchanged, so the slug
        # rule must accept the vocabulary real records use, read from the real log.
        prawduct = Path(__file__).resolve().parent.parent / ".prawduct"
        files = [prawduct / "change-log.md", *sorted((prawduct / "change-log-archive").glob("*.md"))]
        scopes = {
            entry.tags["scope"]
            for path in files
            for entry in change_log.parse_change_log(path.read_text(encoding="utf-8"))
            if isinstance(entry.tags.get("scope"), str)
        }
        assert any("." in scope for scope in scopes), "the corpus no longer holds a dotted scope"
        assert sorted(s for s in scopes if codes(fragment_text(with_("scope", s)), filename=f"{s}.md")) == []

    def test_the_template_is_a_valid_fragment_once_named_for_its_scope(self):
        template = _REPO_ROOT / "templates" / "change-fragment.md"
        fragment = cf.parse_fragment(template.read_text(), filename="pantry-v1.md")
        assert cf.validate_fragment(fragment) == []

    def test_reopens_names_a_scope(self):
        front = {**with_("scope", "backlog-file-path-reopen-1"), "reopens": "backlog-file-path"}
        assert codes(fragment_text(front), filename="backlog-file-path-reopen-1.md") == []


# Each case: (code it must produce, fragment text, filename). One departure each.
REFUSALS = [
    ("no-frontmatter", "Just prose.\n\n## Consumer note\nnone: x\n", "backlog-file-path.md"),
    ("no-frontmatter", "---\nschema: 1\n", "backlog-file-path.md"),
    ("bad-frontmatter-line", fragment_text(extra_lines=["  nested: value"]), "backlog-file-path.md"),
    ("bad-frontmatter-line", fragment_text(extra_lines=["not a key value line"]), "backlog-file-path.md"),
    ("duplicate-key", fragment_text(extra_lines=["type: chore"]), "backlog-file-path.md"),
    ("released-fragment", fragment_text(with_("release", "v3.7.1")), "backlog-file-path.md"),
    ("retired-key", fragment_text(with_("chunks", "01")), "backlog-file-path.md"),
    ("retired-key", fragment_text(with_("status", "shipped")), "backlog-file-path.md"),
    ("unknown-key", fragment_text(with_("issues", "[1004]")), "backlog-file-path.md"),
    ("missing-key", fragment_text(without("schema")), "backlog-file-path.md"),
    ("missing-key", fragment_text(without("type")), "backlog-file-path.md"),
    ("missing-key", fragment_text(without("scope")), "backlog-file-path.md"),
    ("missing-key", fragment_text(without("date")), "backlog-file-path.md"),
    ("missing-key", fragment_text(without("title")), "backlog-file-path.md"),
    ("missing-key", fragment_text(with_("title", "")), "backlog-file-path.md"),
    ("bad-schema", fragment_text(with_("schema", "one")), "backlog-file-path.md"),
    ("bad-schema", fragment_text(with_("schema", "0")), "backlog-file-path.md"),
    ("schema-ahead", fragment_text(with_("schema", "2")), "backlog-file-path.md"),
    ("bad-type", fragment_text(with_("type", "bugfix")), "backlog-file-path.md"),
    ("bad-type", fragment_text(with_("type", "feat")), "backlog-file-path.md"),
    ("bad-scope-slug", fragment_text(with_("scope", "Backlog_File")), "Backlog_File.md"),
    ("bad-scope-slug", fragment_text(with_("scope", "release-v3..7")), "release-v3..7.md"),
    ("bad-scope-slug", fragment_text(with_("scope", ".release")), ".release.md"),
    ("bad-scope-slug", fragment_text(with_("scope", "release.")), "release..md"),
    ("scope-mismatch", fragment_text(), "some-other-scope.md"),
    ("bad-date", fragment_text(with_("date", "2026-13-01")), "backlog-file-path.md"),
    ("bad-date", fragment_text(with_("date", "20261017")), "backlog-file-path.md"),
    ("bad-value", fragment_text(with_("type", "[fix, chore]")), "backlog-file-path.md"),
    # A list would otherwise skip both schema checks, so a newer plugin's
    # `schema: [2]` read as valid: the one case the key exists to refuse.
    ("bad-value", fragment_text(with_("schema", "[2]")), "backlog-file-path.md"),
    ("bad-closes", fragment_text(with_("closes", "brookstalley/prawduct#1004")), "backlog-file-path.md"),
    ("bad-closes", fragment_text(with_("closes", "[1004]")), "backlog-file-path.md"),
    ("bad-closes", fragment_text(with_("closes", "[prawduct#1004]")), "backlog-file-path.md"),
    ("bad-closes", fragment_text(with_("closes", "[brookstalley/prawduct#01004]")), "backlog-file-path.md"),
    ("bad-reopens", fragment_text(with_("reopens", "")), "backlog-file-path.md"),
    ("bad-reopens", fragment_text(with_("reopens", "Not A Scope")), "backlog-file-path.md"),
    ("empty-narrative", fragment_text(narrative=""), "backlog-file-path.md"),
    ("h2-in-body", fragment_text(narrative="Intro.\n\n## Details\nMore."), "backlog-file-path.md"),
    ("missing-consumer-note", fragment_text(note_heading=False), "backlog-file-path.md"),
    (
        "duplicate-consumer-note",
        fragment_text(note=NOTE + "\n\n## Consumer note\nagain"),
        "backlog-file-path.md",
    ),
    ("empty-consumer-note", fragment_text(note=""), "backlog-file-path.md"),
    ("empty-consumer-note", fragment_text(note="none:"), "backlog-file-path.md"),
    ("empty-consumer-note", fragment_text(note="None:   "), "backlog-file-path.md"),
]


@pytest.mark.parametrize(
    "code,text,filename", REFUSALS, ids=[f"{c}-{i}" for i, (c, _, _) in enumerate(REFUSALS)]
)
def test_each_refusal_is_produced_by_its_departure(code, text, filename):
    assert code in codes(text, filename)


def test_every_refusal_code_has_a_fixture():
    """A code with no fixture is a check never seen to fail."""
    source = (_REPO_ROOT / "lib" / "change_fragments.py").read_text()
    import re

    emitted = set(re.findall(r'(?:Problem|FragmentError)\(\s*"([a-z-]+)"', source))
    # The migration's codes live in this module too, and are pinned by the
    # migration tests' own refusal table.
    spec = importlib.util.spec_from_file_location(
        "_migrate_refusals", Path(__file__).with_name("test_change_migrate.py")
    )
    migrate_tests = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migrate_tests)
    # `scope-misspells-plan` judges a fragment against its repo's plans, so its
    # fixtures are repo layouts (TestFragmentScopeNamesItsPlan), not texts.
    covered = (
        {code for code, _, _ in REFUSALS}
        | {code for _, code in migrate_tests.REFUSALS}
        | {"unreadable", "scope-misspells-plan"}
    )
    # The scan must have found the codes it polices, or an empty set passes.
    assert {"no-frontmatter", "missing-consumer-note", "schema-ahead", "bad-closes"} <= emitted
    assert emitted - covered == set()


def test_an_unreadable_file_is_reported_not_raised(tmp_path):
    path = tmp_path / "backlog-file-path.md"
    path.write_bytes(b"\xff\xfe not utf-8")
    result = cf.read_fragment_file(path)
    assert result.fragment is None
    assert [p.code for p in result.problems] == ["unreadable"]


class TestLoadPending:
    def test_a_missing_directory_is_an_empty_pending_set(self, tmp_path):
        assert cf.load_pending(tmp_path) == []

    def test_only_markdown_files_are_fragments_and_each_is_judged(self, tmp_path):
        directory = tmp_path / cf.FRAGMENT_DIR_REL
        directory.mkdir(parents=True)
        (directory / ".gitkeep").write_text("")
        (directory / "backlog-file-path.md").write_text(fragment_text())
        (directory / "broken.md").write_text("no frontmatter here\n")
        loaded = cf.load_pending(tmp_path)
        assert [f.path.name for f in loaded] == ["backlog-file-path.md", "broken.md"]
        assert loaded[0].ok
        assert not loaded[1].ok
        assert loaded[1].problems[0].code == "no-frontmatter"


class TestRenderEntry:
    def fragment(self, **front):
        text = fragment_text({**FRONT, **front})
        return cf.parse_fragment(text, filename=f"{(FRONT | front)['scope']}.md")

    def test_the_archive_block_parses_with_the_legacy_reader(self):
        fragment = self.fragment(closes="[brookstalley/prawduct#1004, BKL-6J2X]")
        block = cf.render_entry(fragment, release="v3.8.0")
        entries = change_log.parse_change_log(block)
        assert len(entries) == 1
        entry = entries[0]
        assert entry.title == "2026-10-17: backlog file writes only to its own repo"
        assert entry.tags["scope"] == "backlog-file-path"
        assert entry.tags["type"] == "fix"
        assert entry.tags["release"] == "v3.8.0"
        assert entry.tags["closes"] == "brookstalley/prawduct#1004,BKL-6J2X"
        assert change_log.validate_change_log_tags(entries) == ([], [])

    def test_the_archive_block_keeps_narrative_and_note(self):
        block = cf.render_entry(self.fragment())
        assert NARRATIVE in block
        assert NOTE in block
        assert "release=" not in block
        # The narrative's `###` survives; only one `##` heading opens the block.
        assert [line for line in block.splitlines() if line.startswith("## ")] == [
            "## 2026-10-17: backlog file writes only to its own repo"
        ]

    def test_a_non_version_release_is_refused(self):
        with pytest.raises(ValueError):
            cf.render_entry(self.fragment(), release="unreleased")


class TestConsumerSection:
    def make(self, scope, when, note):
        text = fragment_text({**FRONT, "scope": scope, "date": when}, note=note)
        return cf.parse_fragment(text, filename=f"{scope}.md")

    def test_newest_first_then_scope_and_none_notes_are_left_out(self):
        fragments = [
            self.make("b-scope", "2026-10-17", "B note."),
            self.make("a-scope", "2026-10-17", "A note."),
            self.make("newer", "2026-10-18", "Newer note."),
            self.make("internal", "2026-10-19", "none: test-only"),
        ]
        section = cf.render_consumer_section(fragments)
        assert section == "**`newer`**: Newer note.\n\n**`a-scope`**: A note.\n\n**`b-scope`**: B note."
        assert cf.none_reasons(fragments) == [("internal", "test-only")]


def problems_of(text, filename="backlog-file-path.md"):
    return cf.validate_fragment(cf.parse_fragment(text, filename=filename))


def test_closes_written_as_a_scalar_is_one_problem_naming_the_list_form():
    # Without its own check, a string would be walked character by character
    # and refused once per character, which says nothing useful.
    found = [p for p in problems_of(fragment_text(with_("closes", "brookstalley/prawduct#1004")))
             if p.code == "bad-closes"]
    assert len(found) == 1
    assert "is a list" in found[0].detail


def test_an_indented_frontmatter_line_is_named_as_indentation():
    with pytest.raises(cf.FragmentError) as raised:
        cf.parse_fragment(fragment_text(extra_lines=["  nested: value"]), filename="backlog-file-path.md")
    assert raised.value.problem.code == "bad-frontmatter-line"
    assert "indented" in raised.value.problem.detail


def test_a_quoted_value_keeps_its_colon_and_loses_its_quotes():
    fragment = cf.parse_fragment(
        fragment_text(with_("title", '"backlog file: own repo only"')), filename="backlog-file-path.md"
    )
    assert fragment.title == "backlog file: own repo only"


# ---------------------------------------------------------------------------
# WU2 at write time: a fragment's scope names its plan, or no plan near it
# ---------------------------------------------------------------------------


def _plan_file(root, rel, scope):
    path = root / ".prawduct" / "artifacts" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nartifact: build-plan\nscope: {scope}\n---\n\n## Status\n")
    return path


def _fragment_file(root, scope):
    directory = root / cf.FRAGMENT_DIR_REL
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{scope}.md"
    path.write_text(fragment_text(with_("scope", scope)))
    return path


def _scope_codes(item):
    return [p.code for p in item.problems if p.code == "scope-misspells-plan"]


class TestFragmentScopeNamesItsPlan:
    """The fragment's ``scope:`` must equal the plan's (FRG2), and until this check
    nothing compared them before release (CL7). Each fixture is a whole repo
    layout, because the check is about the fragment's neighbours, not its text."""

    @pytest.mark.parametrize("plan_scope,fragment_scope", [
        ("work_unit_binding", "work-unit-binding"),   # `_` vs `-`
        ("Work-Unit-Binding", "work-unit-binding"),   # case
        ("release-v3.7.1", "release-v3-7-1"),         # `.` vs `-`
        ("work-unit-binding", "work-binding"),        # a dropped interior segment
        ("work-binding", "work-unit-binding"),        # an added interior segment
    ])
    def test_a_scope_a_plan_spells_differently_is_refused_at_write(
        self, tmp_path, plan_scope, fragment_scope
    ):
        _plan_file(tmp_path, "build-plan-x.md", plan_scope)
        item = cf.read_fragment_file(_fragment_file(tmp_path, fragment_scope))
        assert _scope_codes(item) == ["scope-misspells-plan"]
        detail = next(p.detail for p in item.problems if p.code == "scope-misspells-plan")
        assert plan_scope in detail and "build-plan-x.md" in detail

    def test_an_archived_plan_is_searched_too(self, tmp_path):
        _plan_file(tmp_path, "archive/build-plan-x.md", "work_unit_binding")
        item = cf.read_fragment_file(_fragment_file(tmp_path, "work-unit-binding"))
        assert _scope_codes(item) == ["scope-misspells-plan"]

    def test_the_check_runs_wherever_the_fragment_is_validated(self, tmp_path):
        # Every consumer reaches validation through one of these three doors;
        # the PR gate's `git show` path passes text and a path, so the path
        # alone must be enough to find the repo.
        _plan_file(tmp_path, "build-plan-x.md", "work_unit_binding")
        path = _fragment_file(tmp_path, "work-unit-binding")
        assert _scope_codes(cf.check_fragment_text(path.read_text(), path))
        assert [_scope_codes(i) for i in cf.load_pending(tmp_path)] == [["scope-misspells-plan"]]

    @pytest.mark.parametrize("plan_scope,fragment_scope", [
        ("work-unit-binding", "work-unit-binding"),          # names its plan exactly
        ("goal-grounding", "goal-grounding-discovery"),      # a trailing follow-up: a new unit (D4)
        ("norm-lifecycle", "fix-norm-lifecycle"),            # a leading verb: also a new unit
        ("backlog-file-path", "backlog-file-path-reopen-1"),  # the template's reopen naming
        ("docs", "docs-fix"),                                # one-word scopes never near-match
        ("work-unit-binding", "evidence-store"),             # unrelated
    ])
    def test_a_scope_naming_its_plan_or_no_plan_near_it_is_accepted(
        self, tmp_path, plan_scope, fragment_scope
    ):
        _plan_file(tmp_path, "build-plan-x.md", plan_scope)
        item = cf.read_fragment_file(_fragment_file(tmp_path, fragment_scope))
        assert item.ok, item.problems

    def test_a_plan_less_fix_is_its_own_declaration(self, tmp_path):
        # Small fixes have no plan; the fragment is then the unit.
        item = cf.read_fragment_file(_fragment_file(tmp_path, "work-unit-binding"))
        assert item.ok, item.problems

    def test_an_exact_live_plan_wins_over_a_near_archived_one(self, tmp_path):
        _plan_file(tmp_path, "build-plan-x.md", "work-unit-binding")
        _plan_file(tmp_path, "archive/build-plan-old.md", "work_unit_binding")
        item = cf.read_fragment_file(_fragment_file(tmp_path, "work-unit-binding"))
        assert item.ok, item.problems

    def test_a_fragment_outside_a_repo_layout_is_judged_on_its_text_alone(self, tmp_path):
        # A fixture path, or text with nowhere to look: no plan can be found, so
        # none can be near — the schema checks still run.
        path = tmp_path / "work-unit-binding.md"
        path.write_text(fragment_text(with_("scope", "work-unit-binding")))
        assert cf.read_fragment_file(path).ok

    def test_this_repo_s_history_stays_clean(self):
        """The rule measured on the real corpus: every recorded scope in this
        repo's change history against every live and archived plan. A
        near-match rule that refused a shipped scope would refuse its next
        sibling; the two trailing-suffix follow-ups the corpus holds
        (`goal-grounding-discovery`, `norm-lifecycle-stopgaps`) are why the
        segment rule is interior-only."""
        from lib import change_log_archive
        from lib import plan_index

        repo = _REPO_ROOT.parent
        plans = plan_index.build_scope_to_plan_map(
            repo / ".prawduct" / "artifacts", include_archived=True
        )
        text = change_log_archive.load_all_text(repo / ".prawduct") or ""
        recorded = {
            e.tags["scope"] for e in change_log.parse_change_log(text)
            if isinstance(e.tags.get("scope"), str)
        }
        # The corpus was reached, or "nothing near-matched" means nothing was read.
        assert len(plans) > 50 and len(recorded) > 100
        hits = [
            (s, p) for s in recorded if s not in plans for p in plans if cf.scope_near_match(s, p)
        ]
        assert hits == []
        # And the rule is live on this corpus: the two follow-ups ARE adjacent
        # to their parents by one segment, which only the interior bound excuses.
        assert not cf.scope_near_match("norm-lifecycle-stopgaps", "norm-lifecycle")
