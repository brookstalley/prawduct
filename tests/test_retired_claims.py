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
