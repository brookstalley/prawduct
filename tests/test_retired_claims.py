"""Tests for the ``retired-claim-survives`` record-lint check (#136).

When a governing record retires a claim, the old wording survives wherever the
author's sweep did not reach. The check reads the record's machine-read
``Retires:`` phrases and reports every surviving copy, in tracked files and in
open backlog issues. What is pinned here:

* **What it catches is named, and so is what it does not.** Literal survival,
  including inside a file the current change edits and inside the backlog, is
  caught. A paraphrase is not: Critic Goal 4 owns that. The coverage statement
  is the module's docstring, and the replay class below pins it in both
  directions.
* **History is not a survivor.** Archives, the change-log and fragments record
  the retirement by quoting it, so they are excluded. A ``Retires:`` field is a
  declaration, not an assertion.
* **An unread input is never a clean result.** A backlog that cannot be read
  reports ``unchecked`` and the tally is ``None``.

Real git repos with sterile config, mirroring ``test_record_lint.py``. The
backlog leg runs against the offline ``FakeGitHub`` through a real cache
rebuild.
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

_TESTS_DIR = Path(__file__).resolve().parent
_PLUGIN = _TESTS_DIR.parent / "plugin"
for _p in (str(_PLUGIN), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lib import record_lint, retired_claims  # noqa: E402
from lib.backlog import core as backlog_core  # noqa: E402
from lib.backlog import sync  # noqa: E402
from fakes.fake_github import FakeGitHub  # noqa: E402

CHECK = "retired-claim-survives"
OWNER, REPO = "octo", "repo"
SCOPE = f"{OWNER}/{REPO}"

# The phrase #136's acceptance names. Every line below that carries it is the
# fixture's subject, not a claim this file makes.
PHRASE = "fails safe to thoroughness"  # prawduct:allow prawduct/retired-claim-survives -- the acceptance fixture's phrase

NORM_ARTIFACT = f"""# Nonfunctional requirements

## Direction

- **Unsure defaults to the inner review.** The boundary is never inferred away.
  Why: an undeclared repo should not pay for the boundary review on every chunk.
  Retires: the old fail-safe family, *"{PHRASE}"*, in every carrier.

## Notes

Descriptive surroundings.
"""


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _make_repo(tmp_path: Path, files: "dict[str, str] | None" = None, *, state: str = "") -> Path:
    repo = tmp_path / "repo"
    _write(repo, ".prawduct/project-state.yaml", "project_name: t\n" + state)
    _write(repo, ".prawduct/artifacts/nonfunctional-requirements.md", NORM_ARTIFACT)
    for rel, text in (files or {}).items():
        _write(repo, rel, text)
    _git(repo, "init", "-q")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "c1")
    return repo


def _tree(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD^{tree}")


def _lint(repo: Path, paths: "list[str] | None" = None) -> dict:
    tree = _tree(repo)
    return record_lint.lint_records(repo, repo / ".prawduct", paths or [], tree, tree)


def _found(result: dict) -> "list[tuple[str, int | None]]":
    return sorted(
        (f["path"], f["line"]) for f in result["findings"] if f["check"] == CHECK
    )


def _check_unchecked(result: dict) -> list[str]:
    return [r for r in result["unchecked"] if r.startswith(CHECK)]


# ---------------------------------------------------------------------------
# The file leg
# ---------------------------------------------------------------------------


class TestASurvivorInATrackedFileIsReported:
    def test_the_acceptance_fixture_is_reported_at_its_line(self, tmp_path):
        """#136's red-first box: a norm retires the phrase and `docs/x.md` still
        says it. The finding names the file, the line and the declaring record."""
        repo = _make_repo(
            tmp_path,
            {"docs/x.md": "# X\n\nIntro.\nEvery layer " + PHRASE + ".\n"},
        )
        result = _lint(repo)
        assert _found(result) == [("docs/x.md", 4)]
        (finding,) = [f for f in result["findings"] if f["check"] == CHECK]
        assert PHRASE in finding["detail"]
        assert ".prawduct/artifacts/nonfunctional-requirements.md:7" in finding["detail"]
        assert result["counts"][CHECK] == 1
        assert _check_unchecked(result) == []

    def test_a_clean_repo_counts_zero_not_none(self, tmp_path):
        """A control: same declaration, no survivor. Zero is an answer."""
        repo = _make_repo(tmp_path, {"docs/x.md": "# X\n\nNothing retired here.\n"})
        result = _lint(repo)
        assert _found(result) == []
        assert result["counts"][CHECK] == 0

    def test_a_wrapped_capitalised_copy_in_a_comment_is_reported(self, tmp_path):
        """Prose here is hard-wrapped, so a multi-word phrase straddles lines,
        and a sentence start capitalises it. A fixed-string per-line grep misses
        both, which is exactly the survivor this check exists for."""
        repo = _make_repo(
            tmp_path,
            {
                "docs/wrapped.md": "# W\n\nThe old rule said review\nFails safe to\nthoroughness.\n",
                "src/mod.py": "x = 1\n# the default fails safe\n#   to thoroughness, it said\n",
            },
        )
        assert _found(_lint(repo)) == [("docs/wrapped.md", 4), ("src/mod.py", 2)]

    def test_a_longer_word_containing_the_phrase_is_not_a_match(self, tmp_path):
        """Word boundaries at the phrase's ends: `retires: "label/"` must not
        fire on `relabel/`. The control in the same file proves the file was read."""
        repo = _make_repo(
            tmp_path,
            {
                ".prawduct/project-state.yaml": (
                    "project_name: t\ntechnical_decisions:\n"
                    "  - name: storage\n    retires: [\"label/\"]\n"
                ),
                "docs/p.md": "# P\n\nuse relabel/ here\nand label/ there\n",
            },
        )
        assert _found(_lint(repo)) == [("docs/p.md", 4)]

    def test_a_file_the_current_change_edits_is_still_reported(self, tmp_path):
        """Cause class 3: excluding the files being edited inverts the risk,
        because they are the ones the decision is about. The survivor is added
        in the working tree and named in the diff's paths, and is reported."""
        repo = _make_repo(tmp_path, {"docs/edited.md": "# E\n\nA fresh rule.\n"})
        _write(repo, "docs/edited.md", "# E\n\nA fresh rule.\n\nIt " + PHRASE + ".\n")
        assert _found(_lint(repo, ["docs/edited.md"])) == [("docs/edited.md", 5)]

    def test_an_untracked_file_is_not_searched(self, tmp_path):
        """Tracked files only: scratch output in the work tree is not a record."""
        repo = _make_repo(tmp_path)
        _write(repo, "scratch.md", "It " + PHRASE + ".\n")
        assert _found(_lint(repo)) == []


class TestHistoryAndDeclarationsAreNotSurvivors:
    def test_the_declaring_line_and_history_are_not_reported(self, tmp_path):
        """History records the retirement by quoting it. A second record that
        ALSO retires the phrase is a declaration too. Only the live doc reports."""
        quoted = "The entry retired " + PHRASE + " today.\n"
        repo = _make_repo(
            tmp_path,
            {
                ".prawduct/change-log.md": "# Change log\n\n" + quoted,
                ".prawduct/change-log-archive/2026-09.md": quoted,
                ".prawduct/changes/review-stages.md": quoted,
                ".prawduct/artifacts/archive/build-plan-old.md": quoted,
                "docs/archive/old.md": quoted,
                "CHANGELOG.md": quoted,
                ".prawduct/artifacts/architecture.md": (
                    "# Architecture\n\n## Direction\n\n- **A second norm.** Detail.\n"
                    "  Why: a reason.\n"
                    '  Retires: "' + PHRASE + '" here as well.\n'
                ),
                "docs/live.md": quoted,
            },
        )
        assert _found(_lint(repo)) == [("docs/live.md", 1)]

    def test_what_the_release_cut_writes_is_history_whatever_its_name(self, tmp_path):
        """A release file and the declared changelog hold text that shipped and
        is never edited, so a retired phrase quoted there is history. The same
        name undeclared is an ordinary doc, and still reports."""
        quoted = "The release retired " + PHRASE + ".\n"
        files = {".prawduct/releases/v1.4.0.md": quoted, "docs/NEWS.md": quoted, "NOTES.md": quoted}
        declared = _make_repo(
            tmp_path / "declared", files, state="consumer_digest:\n  path: docs/NEWS.md\n"
        )
        assert _found(_lint(declared)) == [("NOTES.md", 1)]
        undeclared = _make_repo(tmp_path / "undeclared", files)
        assert _found(_lint(undeclared)) == [("NOTES.md", 1), ("docs/NEWS.md", 1)]

    def test_a_retires_line_outside_a_direction_section_declares_nothing(self, tmp_path):
        """The field is read on Direction norm entries only. A `Retires:` in a
        plan's prose or a section of notes is ordinary text."""
        repo = _make_repo(
            tmp_path,
            {
                ".prawduct/artifacts/notes.md": (
                    '# Notes\n\n## Background\n\n- **Not a norm.**\n  Retires: "a phrase of notes"\n'
                ),
                "docs/x.md": "It holds a phrase of notes.\n",
            },
        )
        assert _found(_lint(repo)) == []

    def test_a_wrapped_retires_field_is_read_whole_and_excluded_whole(self, tmp_path):
        """A field soft-wraps across physical lines like every norm field. A
        phrase quoted on the continuation line is still declared, and the
        continuation line is still part of the declaration."""
        repo = _make_repo(
            tmp_path,
            {
                ".prawduct/artifacts/data-model.md": (
                    "# Data model\n\n## Direction\n\n- **Facts are immutable.** Detail.\n"
                    "  Why: a reason.\n"
                    '  Retires: the edit-in-place wording, "rewrite the fact" and\n'
                    '  "patch the ledger row", both gone.\n'
                ),
                "docs/x.md": "Then patch the ledger row.\n",
            },
        )
        assert _found(_lint(repo)) == [("docs/x.md", 1)]


class TestAWaiverAcknowledgesAQuotation:
    def test_a_waiver_on_the_line_or_above_silences_it_and_a_wrong_ref_does_not(self, tmp_path):
        """An absence test or an analysis arguing against the claim quotes it as
        its subject. The repo's own pragma, with a reason, says so. A waiver for
        another rule is not an acknowledgement of this one."""
        repo = _make_repo(
            tmp_path,
            {
                "tests/t.py": (
                    "def test_gone():\n"
                    "    assert '" + PHRASE + "' not in TEXT  # prawduct:allow prawduct/retired-claim-survives -- absence test\n"
                    "    # prawduct:allow prawduct/retired-claim-survives -- the next line asserts absence too\n"
                    "    assert '" + PHRASE + "' not in OTHER\n"
                    "    assert '" + PHRASE + "' not in THIRD  # prawduct:allow prawduct/broad-except -- wrong rule\n"
                ),
            },
        )
        assert _found(_lint(repo)) == [("tests/t.py", 5)]


class TestDecisionRecordsDeclareTheSameWay:
    def test_technical_and_design_decisions_retires_lists_are_read(self, tmp_path):
        """#136: a `technical_decisions` entry with `retires: [...]` reads the
        same as a norm's `Retires:`. Flow and block lists both, and
        `design_decisions` too. A `retires:` under another key is not a
        decision record."""
        state = (
            "technical_decisions:\n"
            "  - name: runtime split\n"
            "    status: AMENDED\n"
            '    retires: ["forced by a version conflict", \'not negotiable at all\']\n'
            "design_decisions:\n"
            "  - name: review gate\n"
            "    retires:\n"
            '      - "every addition stops at review"\n'
            "      - agents cannot auto-accept\n"
            "goals:\n"
            "  retires: [\"an unrelated goal phrase\"]\n"
        )
        repo = _make_repo(
            tmp_path,
            {
                "docs/a.md": "The split was forced by a version conflict.\n",
                "docs/b.md": "It is not negotiable at all.\n",
                "docs/c.md": "Every addition stops at review.\n",
                "docs/d.md": "Agents cannot auto-accept.\n",
                "docs/e.md": "An unrelated goal phrase.\n",
            },
            state=state,
        )
        assert _found(_lint(repo)) == [
            ("docs/a.md", 1),
            ("docs/b.md", 1),
            ("docs/c.md", 1),
            ("docs/d.md", 1),
        ]

    def test_the_templates_category_nesting_is_read(self, tmp_path):
        """The scaffolded `project-state.yaml` nests decisions under category
        keys (`technical_decisions.architecture[]`), one level deeper than a
        flat list. A product filling the template writes exactly this shape."""
        state = (
            "technical_decisions:\n"
            "  architecture:\n"
            "    - decision: two planes on one host\n"
            "      retires:\n"
            '        - "two planes on two machines"\n'
            "  technology: []\n"
        )
        repo = _make_repo(tmp_path, {"docs/a.md": "Two planes on two machines.\n"}, state=state)
        assert _found(_lint(repo)) == [("docs/a.md", 1)]

    def test_a_decision_records_own_retires_lines_are_not_survivors(self, tmp_path):
        """The state file is tracked, so its own `retires:` values would match
        themselves. They are declarations, excluded like a norm's field."""
        state = (
            "technical_decisions:\n"
            "  - name: x\n"
            "    retires:\n"
            '      - "a retired decision phrase"\n'
            "    note: the old record said a retired decision phrase once\n"
        )
        repo = _make_repo(tmp_path, state=state)
        assert _found(_lint(repo)) == [(".prawduct/project-state.yaml", 6)]


class TestADegeneratePhraseIsADeclarationDefect:
    def test_a_phrase_too_short_to_search_is_reported_at_its_record(self, tmp_path):
        """A two-letter phrase would match nearly every file. It is reported as
        a defect in the declaration, and the other phrases are still searched."""
        state = 'technical_decisions:\n  - name: x\n    retires: ["ok", "a real old phrase"]\n'
        repo = _make_repo(tmp_path, {"docs/x.md": "ok, a real old phrase.\n"}, state=state)
        result = _lint(repo)
        assert _found(result) == [(".prawduct/project-state.yaml", 4), ("docs/x.md", 1)]
        details = [f["detail"] for f in result["findings"] if f["check"] == CHECK]
        assert any("too short" in d for d in details)


class TestADeclarationThatNamesNothingIsReported:
    """A `Retires:` that yields no searchable phrase would otherwise be inert:
    it searches nothing and the tally reads a clean zero. Each shape is reported
    at its record, and the control beside it proves the record was read."""

    def test_a_markdown_field_with_no_quoted_phrase(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {
                ".prawduct/artifacts/architecture.md": (
                    "# A\n\n## Direction\n\n- **A norm.** Detail.\n  Why: a reason.\n"
                    "  Retires: the old split rule, unquoted.\n"
                ),
            },
        )
        assert _found(_lint(repo)) == [(".prawduct/artifacts/architecture.md", 7)]

    def test_the_inline_form_is_reported_not_read(self, tmp_path):
        repo = _make_repo(
            tmp_path,
            {
                ".prawduct/artifacts/architecture.md": (
                    "# A\n\n## Direction\n\n"
                    '- **A norm.** Detail. Why: a reason. Retires: "an inline old phrase".\n'
                ),
                "docs/x.md": "An inline old phrase.\n",
            },
        )
        result = _lint(repo)
        assert _found(result) == [(".prawduct/artifacts/architecture.md", 5)]
        assert "inline" in next(f["detail"] for f in result["findings"] if f["check"] == CHECK)

    def test_an_empty_or_unquoted_state_list(self, tmp_path):
        state = (
            "technical_decisions:\n"
            "  - name: a\n    retires: []\n"
            "  - name: b\n    retires:\n    note: nothing listed\n"
        )
        repo = _make_repo(tmp_path, state=state)
        assert _found(_lint(repo)) == [
            (".prawduct/project-state.yaml", 4),
            (".prawduct/project-state.yaml", 6),
        ]

    def test_retires_as_an_entrys_first_key_stops_at_the_next_entry(self, tmp_path):
        """`  - retires:` puts the key two columns right of its dash. Its list ends
        at the next record (`  - name: b`), which must not be read as a phrase."""
        state = (
            "technical_decisions:\n"
            '  - retires:\n    - "an entry-first old phrase"\n'
            "  - name: b\n"
        )
        repo = _make_repo(
            tmp_path,
            {"docs/a.md": "An entry-first old phrase.\n", "docs/b.md": "name: b is fine\n"},
            state=state,
        )
        assert _found(_lint(repo)) == [("docs/a.md", 1)]

    def test_a_trailing_comment_and_a_same_indent_list_still_declare(self, tmp_path):
        """Valid YAML both: a comment after a flow list, and a block list at the
        key's own indentation. Each declares its phrase."""
        state = (
            "technical_decisions:\n"
            '  - name: a\n    retires: ["first old phrase"]  # why it went\n'
            "  - name: b\n    retires:\n    - second old phrase\n"
        )
        repo = _make_repo(
            tmp_path,
            {"docs/a.md": "The first old phrase.\n", "docs/b.md": "The second old phrase.\n"},
            state=state,
        )
        assert _found(_lint(repo)) == [("docs/a.md", 1), ("docs/b.md", 1)]


class TestTheFileLegNeverPassesSilently:
    def test_git_that_cannot_search_is_unchecked(self, tmp_path):
        """A project dir git cannot answer for: declarations read, search
        unanswerable. `unchecked`, and the tally is None."""
        repo = tmp_path / "plain"
        _write(repo, ".prawduct/project-state.yaml", "project_name: t\n")
        _write(repo, ".prawduct/artifacts/nonfunctional-requirements.md", NORM_ARTIFACT)
        findings, unchecked, no_answer = retired_claims.check(repo, repo / ".prawduct")
        assert findings == []
        assert any("could not search the tracked files" in r for r in unchecked), unchecked
        assert no_answer == {CHECK}

    def test_an_unreadable_declaring_record_is_unchecked(self, tmp_path):
        repo = _make_repo(tmp_path, {"docs/x.md": "It " + PHRASE + ".\n"})
        (repo / ".prawduct/artifacts/broken.md").write_bytes(b"# B\n\xff\xfe Retires: \x80\n")
        result = _lint(repo)
        assert _found(result) == [("docs/x.md", 1)]
        reasons = _check_unchecked(result)
        assert len(reasons) == 1 and "broken.md" in reasons[0]
        assert result["counts"][CHECK] is None


# ---------------------------------------------------------------------------
# The backlog leg (cause class 5)
# ---------------------------------------------------------------------------


def _file_issue(fake: FakeGitHub, title: str, body: str) -> str:
    result = backlog_core.file_item(
        fake, owner=OWNER, repo=REPO, title=title, body=body, facets={"area": "governance"}
    )
    assert result["status"] == "ok", result
    return result["data"]["id"]


def _rebuild(fake: FakeGitHub, repo: Path) -> None:
    result = sync.full_rebuild(
        fake, project_dir=repo, owner=OWNER, repo=REPO, now=datetime.now(timezone.utc)
    )
    assert result["status"] == "ok", result


class TestTheBacklogIsPartOfTheSweepSet:
    def test_an_open_issue_carrying_the_phrase_is_reported(self, tmp_path):
        """No artifact graph reaches an issue. A closed issue is history, and a
        waived line in an issue body is an acknowledged quotation."""
        repo = _make_repo(tmp_path, state=f"backlog_service_repo: {SCOPE}\n")
        fake = FakeGitHub(user={"login": "agent-a", "id": 1})
        live = _file_issue(fake, "governance: argue from the old rule", "The review " + PHRASE + ".")
        closed = _file_issue(fake, "governance: an old closed one", "It " + PHRASE + ".")
        _file_issue(
            fake,
            "governance: quote it on purpose",
            "Retire\n\"" + PHRASE + "\"  <!-- prawduct:allow prawduct/retired-claim-survives -- the item retires it -->",
        )
        _file_issue(fake, "governance: unrelated", "Nothing to see.")
        _file_issue(
            fake,
            "governance: propose a retirement in the documented form",
            'Amend the norm.\n\nRetires: "' + PHRASE + '"\n',
        )
        assert backlog_core.set_status(fake, id_raw=closed, target="shipped")["status"] == "ok"
        _rebuild(fake, repo)

        result = _lint(repo)
        assert _found(result) == [(live, None)]
        assert result["counts"][CHECK] == 1
        assert _check_unchecked(result) == []

    def test_an_unreadable_backlog_is_unchecked_never_clean(self, tmp_path):
        """`backlog_service_repo` is set but the cache was never synced. The
        backlog leg reports `unchecked` and the tally is None. The file leg's
        finding still prints: only the tally withholds."""
        repo = _make_repo(
            tmp_path,
            {"docs/x.md": "It " + PHRASE + ".\n"},
            state=f"backlog_service_repo: {SCOPE}\n",
        )
        result = _lint(repo)
        assert _found(result) == [("docs/x.md", 1)]
        reasons = _check_unchecked(result)
        assert len(reasons) == 1 and "backlog" in reasons[0]
        assert result["counts"][CHECK] is None

    def test_backlog_md_is_searched_until_the_service_repo_freezes_it(self, tmp_path):
        """Unset, `.prawduct/backlog.md` IS the live backlog and an ordinary
        tracked file. Set, it is frozen history (data-model § Direction) and
        the cache is read instead."""
        backlog = "# Backlog\n\n- **[GOV-1AAA]** the review " + PHRASE + "\n"
        unset = _make_repo(tmp_path / "a", {".prawduct/backlog.md": backlog})
        assert _found(_lint(unset)) == [(".prawduct/backlog.md", 3)]

        frozen = _make_repo(
            tmp_path / "b",
            {".prawduct/backlog.md": backlog},
            state=f"backlog_service_repo: {SCOPE}\n",
        )
        _rebuild(FakeGitHub(user={"login": "agent-a", "id": 1}), frozen)
        result = _lint(frozen)
        assert _found(result) == []
        assert result["counts"][CHECK] == 0


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------


class TestWiring:
    def test_the_check_is_registered_and_runs_whatever_the_diff_touched(self, tmp_path):
        """Not record-scoped: a code-only diff, or none, still runs it, because
        its whole target is text the diff did not touch."""
        assert CHECK in record_lint.CHECKS
        repo = _make_repo(tmp_path, {"docs/x.md": "It " + PHRASE + ".\n"})
        assert _found(_lint(repo, [])) == [("docs/x.md", 1)]

    def test_the_docstring_states_what_it_does_not_catch(self):
        """The coverage statement ships in the docstring (#136), naming each
        uncaught class with the control that owns it."""
        doc = retired_claims.__doc__ or ""
        for needle in ("paraphrase", "Goal 4", "verify-resolutions"):
            assert needle in doc, needle


# ---------------------------------------------------------------------------
# Replay: the recorded recurrences (#136 Evidence)
# ---------------------------------------------------------------------------

#: One row per recorded recurrence, restating its SHAPE in new words (the
#: evidence lives in another product's record; its text is not copied). Each row
#: declares a phrase, plants the surviving copy as the recurrence left it, and
#: says whether this check catches it. A row expected NOT caught pins the
#: coverage statement's other half: paraphrase and half-consumed findings
#: belong to Critic Goal 4 and `verify-resolutions`, and a check that started
#: "catching" them would be matching something other than the phrase.
_REPLAY = [
    # (recurrence, cause class, declared phrase, {path: text}, caught)
    ("R1", "1: a heading in another file", "the split is not negotiable",
     {".prawduct/learnings.md": "# L\n\n## Why the split is not negotiable\n"}, True),
    ("R2", "1: verbatim in a state block", "agents cannot accept on their own",
     {".prawduct/project-state.yaml": "risk_profile:\n  note: agents cannot accept on their own\n"}, True),
    ("R3", "1: literal copies the sweep did not reach", "moves the heavy work off the small box",
     {"docs/a.md": "It moves the heavy work off the small box.\n",
      "docs/b.md": "That moves the heavy work\noff the small box.\n"}, True),
    ("R3p", "2: the same recurrence's paraphrased copies", "forced by a version conflict",
     {"docs/c.md": "Forced by the interpreter mismatch, not chosen.\n"}, False),
    ("R4", "1+3: below the new rule, in the file being edited", "spend attributes to the first run",
     {"docs/model.md": "## Spend\n\nNew rule: spend follows the re-run.\n" + "\n" * 180
      + "Spend attributes to the first run.\n"}, True),
    ("R5", "3: the edited file's older section", "one product-wide runtime target",
     {"docs/prefs.md": "## Per plane\n\nEach plane pins its own.\n" + "\n" * 140
      + "We keep one product-wide runtime target.\n"}, True),
    ("R6-R7", "4+2: a finding's other files, phrased differently", "every unfinished run is failed",
     {"docs/arch.md": "Startup reconciles each non-terminal run to failed.\n"}, False),
    ("R8", "4: the table cell the grep could not see", "a waiting run dies with the service",
     {"docs/arch.md": "| down | in-flight work is lost | waiting runs survive |\n"}, False),
    ("R10", "4: a finding's enumerated sites, the survivors literal", "single consumer, shipped together",
     {"docs/api.md": "Exempt: single consumer, shipped together.\n",
      ".prawduct/project-state.yaml": "notes:\n  - single consumer, shipped together\n"}, True),
    ("R11", "1: a dangling pointer to a closed question", "see the open question in state",
     {"docs/security.md": "## Open\n\nRights display: see the open question in state.\n"}, True),
    ("R11p", "1: the same section still framing it as open", "rights display is undecided",
     {"docs/security.md": "## Open\n\nWhether rights show is still to be settled.\n"}, False),
    ("R12", "1: an old wording quoted verbatim elsewhere", "has seen its image",
     {"docs/api.md": 'The gate passes once a reviewer "has seen its image".\n'}, True),
    ("R13", "4: a finding's fourth home, a literal token", "label/",
     {".prawduct/learnings.md": "# L\n\n## Cache contract\n\nKeys live under label/ today.\n"}, True),
]


def _replay_repo(tmp_path: Path, phrase: str, files: "dict[str, str]") -> Path:
    files = dict(files)
    declared = f'technical_decisions:\n  - name: replay\n    retires: ["{phrase}"]\n'
    state = files.pop(".prawduct/project-state.yaml", "")
    return _make_repo(tmp_path, files, state=declared + state)


class TestReplayOfTheRecordedRecurrences:
    def test_every_class_1_3_and_literal_survivor_is_caught(self, tmp_path):
        """#136's replay box: each class-1/3/5 recurrence, rebuilt, is caught,
        and a class-4 recurrence whose surviving sites carried the phrase
        verbatim is caught for the same reason. R9, the backlog home, is the
        next test, because it needs a cache."""
        rows = [row for row in _REPLAY if row[4]]
        assert len(rows) >= 8
        for recurrence, cause, phrase, files, _ in rows:
            repo = _replay_repo(tmp_path / recurrence, phrase, files)
            found = {path for path, _ in _found(_lint(repo, sorted(files)))}
            expected = {path for path in files}
            assert found == expected, (recurrence, cause, found)

    def test_paraphrase_and_unseen_cells_are_not_caught(self, tmp_path):
        """The other half of the coverage statement. If one of these starts
        firing, the matcher is matching something other than the phrase."""
        rows = [row for row in _REPLAY if not row[4]]
        assert len(rows) >= 4
        for recurrence, cause, phrase, files, _ in rows:
            repo = _replay_repo(tmp_path / recurrence, phrase, files)
            result = _lint(repo, sorted(files))
            assert _found(result) == [], (recurrence, cause)
            assert result["counts"][CHECK] == 0

    def test_r9_a_stale_tally_in_the_issue_that_argues_from_it(self, tmp_path):
        """Class 5: the tally was refreshed in the learnings file and not in the
        open issue whose argument it is. No sweep of `.prawduct/` reaches it."""
        repo = _replay_repo(
            tmp_path, "three times in two sessions",
            {".prawduct/project-state.yaml": f"backlog_service_repo: {SCOPE}\n"},
        )
        fake = FakeGitHub(user={"login": "agent-a", "id": 1})
        issue = _file_issue(
            fake, "governance: acknowledge dependent artifacts",
            "The learning was broken three times in two sessions.",
        )
        _rebuild(fake, repo)
        assert _found(_lint(repo)) == [(issue, None)]


class TestThisRepoIsClean:
    # It searches this repo's tracked files through `git grep`, which a
    # history-less runner checkout cannot answer; the reached-assertion below
    # turns that into a failure rather than a vacuous pass.
    @pytest.mark.requires_history
    def test_no_unacknowledged_survivor_in_this_repos_tracked_files(self):
        """Dogfood: the stage-keyed norm's `Retires:` line is a live declaration,
        and every tracked copy of its phrases is rewritten or waived with a
        reason. The subject is asserted REACHED first, or a reader that lost the
        declaration would pass this as clean. The backlog leg is left out: the
        cache is per-clone state a CI runner does not have, and an open issue
        quoting a claim it retires closes when it ships."""
        root = _TESTS_DIR.parent
        declared, unreadable = retired_claims._artifact_declarations(root, root / ".prawduct")
        assert unreadable == []
        phrases = {d.phrase for d in declared}
        assert "fails safe to thoroughness" in phrases  # prawduct:allow prawduct/retired-claim-survives -- asserts the declaration was read
        findings, unchecked, _ = retired_claims.check(root, root / ".prawduct")
        assert not [r for r in unchecked if "tracked files" in r], unchecked
        in_files = [f"{f['path']}:{f['line']}" for f in findings if f["line"] is not None]
        assert in_files == []


class TestTheInlineFormTestIsLinear:
    """The inline-form test used `\\S.*?(?:\\*{1,2}|_{1,2})?\\bRetires:`, which
    re-scans to the end of the line from every non-space start: quadratic in a
    long line with no `Retires:` in it. 83 searches over this repo's governing
    artifacts took 3.2s of the dogfood scan above, which then hit its 30s wall
    clock on a loaded machine. `_has_inline_retires` answers the same question
    in one pass."""

    _OLD = __import__("re").compile(r"\S.*?(?:\*{1,2}|_{1,2})?\bRetires:")

    @pytest.mark.parametrize("text", [
        "Retires: \"x\"",
        "  **Retires:** \"x\"",
        "- **A norm.** Detail. Retires: \"x\"",
        "Detail.\nRetires: \"x\"",
        "Detail.\n  Retires: \"x\"",
        "NotRetires: \"x\"",
        "x Retires:",
        "x_Retires:",
        "x **Retires:**",
        "",
        "no field here",
    ])
    def test_it_agrees_with_the_regex_it_replaced(self, text):
        assert retired_claims._has_inline_retires(text) == bool(self._OLD.search(text))

    def test_it_agrees_on_every_real_line_that_carries_the_field(self):
        """The corpus that made the old one slow is the one it must agree on.
        Asserted non-empty, or agreement over nothing would pass."""
        root = _TESTS_DIR.parent
        tracked = subprocess.run(
            ["git", "ls-files", "*.md"], cwd=str(root), capture_output=True, text=True,
            check=True, timeout=30,
        ).stdout.splitlines()
        lines = [
            line
            for rel in tracked
            if (root / rel).is_file()
            for line in (root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
            if "Retires:" in line
        ]
        assert len(lines) >= 5, lines
        disagree = [l for l in lines if retired_claims._has_inline_retires(l) != bool(self._OLD.search(l))]
        assert disagree == []

    def test_a_long_line_without_the_field_is_one_pass(self):
        import time

        line = "word " * 40000
        start = time.perf_counter()
        assert retired_claims._has_inline_retires(line) is False
        assert time.perf_counter() - start < 1.0
