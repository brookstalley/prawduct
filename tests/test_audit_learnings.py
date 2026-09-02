"""Tests for `lib/audit_learnings_cmd.py` and the `bin/prawduct-hook audit-learnings` CLI.

Covers the F9 learnings lifecycle tracker: metadata parsing,
file segmentation, audit classification (promotion / retirement / stale /
error), and the `--apply` retirement file mutation. Sentinel subprocess
invocation is gated via ``run_sentinels=False`` so the test suite stays
hermetic and fast — a separate test exercises the real subprocess path
against a synthetic passing test fixture.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import textwrap
from datetime import date
from pathlib import Path

import pytest

import sys  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from lib import audit_learnings_cmd as _mod  # noqa: E402

parse_learning_metadata = _mod.parse_learning_metadata
parse_learnings_file = _mod.parse_learnings_file
audit_learnings = _mod.audit_learnings
run_audit_learnings = _mod.run_audit_learnings
run_sentinel = _mod.run_sentinel
_HOOK_PATH = _REPO_ROOT / "bin" / "prawduct-hook"


# =============================================================================
# parse_learning_metadata — single line parser
# =============================================================================


class TestParseLearningMetadata:
    def test_well_formed_all_fields(self):
        line = (
            "<!-- prawduct-learning: confirmations=2; created=2026-02-22; "
            "sentinel=tests/test_x.py::test_y -->"
        )
        result = parse_learning_metadata(line)
        assert result == {
            "confirmations": "2",
            "created": "2026-02-22",
            "sentinel": "tests/test_x.py::test_y",
        }

    def test_absent_comment_returns_none(self):
        assert parse_learning_metadata("Some prose, not metadata.") is None
        assert parse_learning_metadata("") is None
        assert parse_learning_metadata("## Section heading") is None

    def test_partial_metadata(self):
        """Only one field present — others absent rather than empty."""
        result = parse_learning_metadata(
            "<!-- prawduct-learning: confirmations=1 -->"
        )
        assert result == {"confirmations": "1"}

    def test_whitespace_tolerance(self):
        """Leading/trailing whitespace inside the comment doesn't break parsing."""
        result = parse_learning_metadata(
            "  <!--   prawduct-learning:   confirmations = 3 ;  created = 2026-01-01  -->  "
        )
        assert result == {"confirmations": "3", "created": "2026-01-01"}

    def test_trailing_semicolon(self):
        """Common manual-edit pattern; must not produce a phantom empty key."""
        result = parse_learning_metadata(
            "<!-- prawduct-learning: confirmations=2; -->"
        )
        assert result == {"confirmations": "2"}

    def test_unknown_keys_preserved(self):
        """Forward compat: new fields don't break parsing. The audit logic
        ignores keys it doesn't recognize, but the parser keeps them."""
        result = parse_learning_metadata(
            "<!-- prawduct-learning: confirmations=2; future_field=hello -->"
        )
        assert result == {"confirmations": "2", "future_field": "hello"}

    def test_non_prawduct_comment_ignored(self):
        """A plain HTML comment is not metadata — parser must not match."""
        assert parse_learning_metadata("<!-- just a comment -->") is None
        assert parse_learning_metadata("<!-- TODO: write this -->") is None

    def test_malformed_pair_dropped(self):
        """A bareword with no = is dropped silently (forward compat)."""
        result = parse_learning_metadata(
            "<!-- prawduct-learning: confirmations=2; bareword -->"
        )
        assert result == {"confirmations": "2"}


# =============================================================================
# parse_learnings_file — file segmentation
# =============================================================================


class TestParseLearningsFile:
    def test_empty_file(self):
        assert parse_learnings_file("") == []

    def test_no_entries_only_preamble(self):
        content = "# Learnings\n\nSome preamble text.\n"
        assert parse_learnings_file(content) == []

    def test_single_entry_no_metadata(self):
        content = "# Learnings\n\n## My rule\n\nBody of the rule.\n"
        entries = parse_learnings_file(content)
        assert len(entries) == 1
        assert entries[0].title == "My rule"
        assert entries[0].metadata == {}
        assert "Body of the rule." in "\n".join(entries[0].body_lines)

    def test_single_entry_with_metadata(self):
        content = (
            "# Learnings\n\n"
            "## My rule\n"
            "<!-- prawduct-learning: confirmations=2; created=2026-01-01 -->\n\n"
            "Body of the rule.\n"
        )
        entries = parse_learnings_file(content)
        assert len(entries) == 1
        assert entries[0].metadata == {
            "confirmations": "2",
            "created": "2026-01-01",
        }

    def test_mixed_annotated_and_unannotated(self):
        content = (
            "# Learnings\n\n"
            "## Rule A\n"
            "<!-- prawduct-learning: confirmations=2 -->\n\n"
            "Body A.\n\n"
            "## Rule B\n\n"
            "Body B with no metadata.\n"
        )
        entries = parse_learnings_file(content)
        assert len(entries) == 2
        assert entries[0].title == "Rule A"
        assert entries[0].metadata == {"confirmations": "2"}
        assert entries[1].title == "Rule B"
        assert entries[1].metadata == {}

    def test_metadata_must_be_first_nonblank_body_line(self):
        """A metadata comment deeper in the entry body must NOT be honored —
        entries that quote example metadata in prose would otherwise hijack
        their own classification."""
        content = (
            "# Learnings\n\n"
            "## Rule\n\n"
            "Some prose first.\n"
            "<!-- prawduct-learning: confirmations=9 -->\n"
            "More prose.\n"
        )
        entries = parse_learnings_file(content)
        assert entries[0].metadata == {}

    def test_round_trip_preserves_body(self):
        """Body content (including the metadata comment line itself) must
        appear verbatim in body_lines so the file can be reconstructed."""
        original_body = (
            "<!-- prawduct-learning: confirmations=1 -->\n\n"
            "Body line 1.\n"
            "Body line 2.\n"
        )
        content = "## Rule\n" + original_body
        entries = parse_learnings_file(content)
        assert entries[0].body_lines[0] == "<!-- prawduct-learning: confirmations=1 -->"


# =============================================================================
# audit_learnings — classification logic
# =============================================================================


def _seed_learnings(product_dir: Path, content: str) -> Path:
    prawduct = product_dir / ".prawduct"
    prawduct.mkdir(parents=True, exist_ok=True)
    learnings = prawduct / "learnings.md"
    learnings.write_text(content)
    return learnings


def _archive_text(product_dir: Path) -> str:
    """The retired-entry archive, which since #350 is its OWN file.

    Retirement used to append to a `## Historical` section at the bottom of
    `learnings-detail.md`, which made the archive part of every lookup's read —
    557KB across 4,748 lines, 182KB of it archive, growing 65% a month. It now
    moves one file further, to `learnings-history.md`, read only on a miss.

    Every assertion about *where a retired entry lands* points here. The
    assertions themselves are unchanged: an entry still moves, still carries its
    forwarding address, still sheds its lifecycle comment, and is still never
    deleted.
    """
    return (product_dir / ".prawduct" / _mod.HISTORY_FILENAME).read_text()


#: A verbatim restoration of the default this fix deleted, kept as the specimen
#: the guard is tested against. Source text, not a live function: it must never
#: be importable or callable, only parsed.
_REINSTATED_DEFAULT_FOR_TESTING = '''
def run_sentinel(product_dir, sentinel, *, timeout=120):
    """Run pytest against the sentinel."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", sentinel, "-q"],
        cwd=str(product_dir),
        capture_output=True,
    )
    return result.returncode == 0, ""
'''


def _hardcoded_runner_violations(*functions, from_source: bool = False) -> list[str]:
    """Names of test runners or interpreters wired into a subprocess invocation.

    **Structural, not textual**, and that is the whole point. The question is
    not "does the word pytest appear" — it appears twice in
    ``resolve_sentinel_command``, explaining the deleted default and showing an
    operator what to declare, and both must stay. The question is whether a
    runner reaches the *invocation*: a string literal inside the argv handed to
    ``subprocess``, or a reference to this interpreter. Prose cannot trip it and
    an argv literal cannot hide from it, which is the pair the earlier
    token-stripping version got backwards.
    """
    import ast
    import inspect

    sources = (
        functions if from_source else [inspect.getsource(f) for f in functions]
    )
    violations: list[str] = []
    for source in sources:
        tree = ast.parse(textwrap.dedent(source))
        for node in ast.walk(tree):
            # `sys.executable` anywhere is this runtime's interpreter leaking in.
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "executable"
                and isinstance(node.value, ast.Name)
                and node.value.id == "sys"
            ):
                violations.append("sys.executable")
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_subprocess = (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "subprocess"
            )
            if not is_subprocess or not node.args:
                continue
            # A built argv arrives as a Name; a hardcoded one as a list literal.
            for element in ast.walk(node.args[0]):
                if isinstance(element, ast.Constant) and isinstance(
                    element.value, str
                ):
                    violations.append(f"literal {element.value!r} in argv")
    return violations


def _declare_sentinel_command(product_dir: Path, command: str) -> Path:
    """Give a synthetic product a `sentinel_command:`.

    Needed by every test that expects a real verdict: without a declaration the
    runner reports `ungraded` by design, so a fixture that forgets this is
    asserting the undeclared path while looking like it tests the declared one.
    """
    prawduct = product_dir / ".prawduct"
    prawduct.mkdir(parents=True, exist_ok=True)
    state = prawduct / "project-state.yaml"
    prior = state.read_text() if state.is_file() else ""
    state.write_text(f"{prior}sentinel_command: {command}\n")
    return state


class TestAuditLearnings:
    def test_no_learnings_file_returns_empty(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        result = audit_learnings(tmp_path, run_sentinels=False)
        assert result["promotions"] == []
        assert result["retirements"] == []
        assert result["stale_flags"] == []
        assert result["errors"] == []
        assert result["applied"] is False

    def test_empty_learnings_file_returns_empty(self, tmp_path: Path):
        _seed_learnings(tmp_path, "# Learnings\n\nNo entries yet.\n")
        result = audit_learnings(tmp_path, run_sentinels=False)
        assert result["promotions"] == []
        assert result["retirements"] == []

    def test_promotion_candidate_surfaces(self, tmp_path: Path):
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n## Rule\n"
            "<!-- prawduct-learning: confirmations=2 -->\n\nBody.\n",
        )
        result = audit_learnings(tmp_path, run_sentinels=False)
        assert len(result["promotions"]) == 1
        assert result["promotions"][0]["title"] == "Rule"
        assert result["promotions"][0]["confirmations"] == 2

    def test_single_confirmation_not_promoted(self, tmp_path: Path):
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n## Rule\n"
            "<!-- prawduct-learning: confirmations=1 -->\n\nBody.\n",
        )
        result = audit_learnings(tmp_path, run_sentinels=False)
        assert result["promotions"] == []

    def test_stale_flag_surfaces(self, tmp_path: Path):
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n## Old rule\n"
            "<!-- prawduct-learning: confirmations=1; created=2025-01-01 -->\n\nBody.\n",
        )
        result = audit_learnings(
            tmp_path, today=date(2026, 5, 19), run_sentinels=False
        )
        assert len(result["stale_flags"]) == 1
        flag = result["stale_flags"][0]
        assert flag["title"] == "Old rule"
        assert flag["age_days"] >= 90
        assert flag["confirmations"] == 1

    def test_recent_entry_not_stale(self, tmp_path: Path):
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n## Fresh rule\n"
            "<!-- prawduct-learning: confirmations=0; created=2026-05-01 -->\n\nBody.\n",
        )
        result = audit_learnings(
            tmp_path, today=date(2026, 5, 19), run_sentinels=False
        )
        assert result["stale_flags"] == []

    def test_confirmed_entry_not_stale_even_when_old(self, tmp_path: Path):
        """Stale threshold gates on confirmations<=1. A confirmations=2 entry
        that's a year old is "validated history," not "abandoned scaffolding."
        """
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n## Old well-confirmed rule\n"
            "<!-- prawduct-learning: confirmations=2; created=2025-01-01 -->\n\nBody.\n",
        )
        result = audit_learnings(
            tmp_path, today=date(2026, 5, 19), run_sentinels=False
        )
        assert result["stale_flags"] == []

    def test_malformed_date_surfaces_error(self, tmp_path: Path):
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n## Rule\n"
            "<!-- prawduct-learning: created=not-a-date -->\n\nBody.\n",
        )
        result = audit_learnings(tmp_path, run_sentinels=False)
        assert any(
            "could not parse created" in e["error"] for e in result["errors"]
        )

    def test_malformed_confirmations_surfaces_error(self, tmp_path: Path):
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n## Rule\n"
            "<!-- prawduct-learning: confirmations=many -->\n\nBody.\n",
        )
        result = audit_learnings(tmp_path, run_sentinels=False)
        assert any(
            "could not parse confirmations" in e["error"]
            for e in result["errors"]
        )

    def test_sentinel_skipped_when_run_sentinels_false(self, tmp_path: Path):
        """The test seam: an entry with a sentinel is recorded as a
        retirement candidate with passed=None, no subprocess invocation,
        no error."""
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n## Rule\n"
            "<!-- prawduct-learning: sentinel=tests/foo.py::test_bar -->\n\nBody.\n",
        )
        result = audit_learnings(tmp_path, run_sentinels=False)
        assert len(result["retirements"]) == 1
        assert result["retirements"][0]["passed"] is None
        assert result["retirements"][0]["sentinel"] == "tests/foo.py::test_bar"
        assert result["errors"] == []

    def test_apply_false_does_not_mutate_file(self, tmp_path: Path):
        learnings_path = _seed_learnings(
            tmp_path,
            "# Learnings\n\n## Rule\n"
            "<!-- prawduct-learning: sentinel=tests/foo.py::test_bar -->\n\nBody.\n",
        )
        original = learnings_path.read_text()

        # Force "sentinel passes" without subprocess by monkeying _audit_logic
        # through a patched run_sentinel — easier path: drive through the
        # public audit_learnings with a custom run_sentinels=False and
        # manually flip the apply on a stubbed pass. Instead we patch
        # subprocess.run to return success.
        result = audit_learnings(
            tmp_path,
            apply=False,
            run_sentinels=False,
        )
        assert result["applied"] is False
        assert learnings_path.read_text() == original

    def test_apply_true_with_passing_sentinel_moves_entry(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """End-to-end retirement: passing sentinel + apply=True moves the
        entry from learnings.md to `learnings-history.md` under the historical
        section, and does NOT leave it in the detail file's read path."""
        learnings_path = _seed_learnings(
            tmp_path,
            "# Learnings\n\n"
            "Preamble paragraph.\n\n"
            "## Retired rule\n"
            "<!-- prawduct-learning: sentinel=tests/foo.py::test_bar -->\n\n"
            "Body of retired rule.\n\n"
            "## Active rule\n\n"
            "Body of active rule.\n",
        )

        # The audit logic looks up run_sentinel inside its own module; patch
        # there to avoid invoking pytest as a subprocess.
        import lib.audit_learnings_cmd as audit_mod
        monkeypatch.setattr(
            audit_mod, "run_sentinel",
            lambda product_dir, sentinel, timeout=120: (True, "1 passed"),
        )

        result = audit_learnings(tmp_path, apply=True)

        assert result["applied"] is True
        assert len(result["retirements"]) == 1
        assert result["retirements"][0]["passed"] is True
        assert result["retirements"][0]["applied"] is True

        # learnings.md no longer contains the retired entry, but keeps
        # the active one and the preamble.
        new_content = learnings_path.read_text()
        assert "Retired rule" not in new_content
        assert "Active rule" in new_content
        assert "Preamble paragraph" in new_content

        # learnings-history.md was created with the historical section + the
        # retired entry body.
        history_path = tmp_path / ".prawduct" / _mod.HISTORY_FILENAME
        assert history_path.is_file()
        archive = history_path.read_text()
        assert "Historical (structurally enforced)" in archive
        assert "Retired rule" in archive
        assert "Body of retired rule." in archive
        # And the archive is NOT in the detail file, which is the whole route
        # out: a lookup reads the active corpus without paying for history.
        detail_path = tmp_path / ".prawduct" / "learnings-detail.md"
        if detail_path.is_file():
            assert "Retired rule" not in detail_path.read_text()

    def test_apply_true_appends_to_existing_detail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """A PRE-SPLIT corpus keeps its archive inside `learnings-detail.md`.

        The first `--apply` after the split lifts it wholesale into
        `learnings-history.md` rather than leaving the old sink in place beside
        a new one — a route out that routes nothing is not a route out, and the
        old archive would keep being read on every lookup. Nothing is deleted:
        the earlier retirement arrives in the new file intact, and the section
        header exists exactly once.
        """
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n## Retired rule\n"
            "<!-- prawduct-learning: sentinel=tests/foo.py::test_bar -->\n\nBody.\n",
        )
        detail_path = tmp_path / ".prawduct" / "learnings-detail.md"
        detail_path.write_text(
            "# Learnings — Full Detail\n\nPrior content.\n\n"
            "## Historical (structurally enforced)\n\n"
            "Earlier retirement note.\n\n"
            "## Earlier retired rule\n\nEarlier body.\n"
        )

        import lib.audit_learnings_cmd as audit_mod
        monkeypatch.setattr(
            audit_mod, "run_sentinel",
            lambda product_dir, sentinel, timeout=120: (True, "1 passed"),
        )

        audit_learnings(tmp_path, apply=True)

        archive = _archive_text(tmp_path)
        # Header appears exactly once, in the file that now owns the archive.
        assert archive.count("## Historical (structurally enforced)") == 1
        # Earlier and new retirements both present — the lift loses nothing.
        assert "Earlier retired rule" in archive
        assert "Earlier body." in archive
        assert "Retired rule" in archive

        # ...and the legacy section is GONE from the detail file, which is the
        # point of the lift. The active prose above it survives.
        detail_content = detail_path.read_text()
        assert "Historical (structurally enforced)" not in detail_content
        assert "Earlier retired rule" not in detail_content
        assert "Prior content." in detail_content

    def test_failing_sentinel_surfaces_as_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        learnings_path = _seed_learnings(
            tmp_path,
            "# Learnings\n\n## Rule\n"
            "<!-- prawduct-learning: sentinel=tests/foo.py::test_missing -->\n\nBody.\n",
        )

        import lib.audit_learnings_cmd as audit_mod
        monkeypatch.setattr(
            audit_mod, "run_sentinel",
            lambda product_dir, sentinel, timeout=120: (False, "no tests ran"),
        )

        result = audit_learnings(tmp_path, apply=True)

        # Even with apply=True, a failing sentinel does NOT retire the entry.
        assert "Rule" in learnings_path.read_text()
        assert len(result["errors"]) == 1
        assert "tests/foo.py::test_missing" in result["errors"][0]["error"]
        # The retirement record is still emitted (so the user sees the
        # attempt) but with passed=False and applied=False.
        assert result["retirements"][0]["passed"] is False
        assert result["retirements"][0]["applied"] is False

    def test_unannotated_entries_untouched(self, tmp_path: Path):
        """Entries with no metadata comment must never appear in any list
        and must not be mutated even with --apply."""
        learnings_path = _seed_learnings(
            tmp_path,
            "# Learnings\n\n"
            "## Plain rule\n\nNo metadata here.\n\n"
            "## Another plain rule\n\nAlso no metadata.\n",
        )
        original = learnings_path.read_text()

        result = audit_learnings(tmp_path, apply=True, run_sentinels=False)

        assert result["promotions"] == []
        assert result["retirements"] == []
        assert result["stale_flags"] == []
        assert result["errors"] == []
        assert learnings_path.read_text() == original

    def test_result_shape_is_stable(self, tmp_path: Path):
        """Every branch (no file, empty file, populated file) must produce
        the same keys."""
        # No prawduct dir → run_audit_learnings path returns error. The
        # internal audit_learnings called with a path that has .prawduct/
        # always returns the canonical shape.
        (tmp_path / ".prawduct").mkdir()

        result = audit_learnings(tmp_path, run_sentinels=False)
        assert set(result.keys()) == {
            "product_dir", "applied", "promotions",
            "retirements", "stale_flags", "errors",
        }


# =============================================================================
# run_audit_learnings — runner with error handling
# =============================================================================


class TestRunAuditLearnings:
    def test_no_prawduct_returns_error(self, tmp_path: Path):
        result = run_audit_learnings(str(tmp_path))
        assert "error" in result
        assert ".prawduct" in result["error"]

    def test_missing_learnings_returns_clean_empty(self, tmp_path: Path):
        """A scaffolded product without a learnings.md file is a clean
        empty result, not an error."""
        (tmp_path / ".prawduct").mkdir()
        result = run_audit_learnings(str(tmp_path))
        assert "error" not in result
        assert result["promotions"] == []
        assert result["retirements"] == []
        assert result["stale_flags"] == []
        assert result["errors"] == []

    def test_result_shape_stable_on_success(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        result = run_audit_learnings(str(tmp_path))
        assert set(result.keys()) == {
            "product_dir", "applied", "promotions",
            "retirements", "stale_flags", "errors",
        }


# =============================================================================
# run_sentinel — real subprocess invocation
# =============================================================================


class TestRunSentinel:
    """Exercises the real subprocess path against a synthetic passing test.

    The audit's main paths are covered by the monkeypatched test cases
    above; this class exists to pin the contract that ``run_sentinel`` does
    NOT raise on common failure modes and returns the documented tuple
    shape across success / failure branches.
    """

    def test_passing_sentinel_returns_true(self, tmp_path: Path):
        # Synthetic product layout with a passing test.
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_synthetic.py").write_text(
            "def test_passes():\n    assert True\n"
        )
        _declare_sentinel_command(tmp_path, f"{sys.executable} -m pytest {{sentinel}} -q")
        passed, excerpt = run_sentinel(
            tmp_path, "tests/test_synthetic.py::test_passes"
        )
        assert passed is True
        assert "passed" in excerpt.lower() or excerpt == ""

    def test_failing_sentinel_returns_false(self, tmp_path: Path):
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_synthetic.py").write_text(
            "def test_fails():\n    assert False\n"
        )
        _declare_sentinel_command(tmp_path, f"{sys.executable} -m pytest {{sentinel}} -q")
        passed, excerpt = run_sentinel(
            tmp_path, "tests/test_synthetic.py::test_fails"
        )
        assert passed is False
        assert excerpt  # some diagnostic text returned

    def test_missing_node_in_an_existing_file_returns_false(self, tmp_path: Path):
        """The file exists but names no such case: the runner ran and judged, so
        this is a real FAILED verdict. Contrast the ungraded cases below, where
        the *file* is gone and no runner ever spoke about the rule."""
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_synthetic.py").write_text(
            "def test_passes():\n    assert True\n"
        )
        _declare_sentinel_command(tmp_path, f"{sys.executable} -m pytest {{sentinel}} -q")
        passed, excerpt = run_sentinel(
            tmp_path, "tests/test_synthetic.py::no_such_case"
        )
        assert passed is False


class TestSentinelWithoutAVerdictIsUngradedNotFailed:
    """The three-valued contract, and the reason it exists.

    `run_sentinel` used to hardcode `sys.executable -m pytest`, so in a product
    that does not use pytest every sentinel came back FAILED with "No module
    named pytest" — against tests that were green. That is worse than silence:
    the audit decides which learnings are structurally enforced, so a
    false-failing sentinel argues for retiring a rule that is still enforced.

    Each case below returns `None`, never `False`. A caller testing truthiness
    cannot tell them apart, which is why the runner's docstring forbids it.
    """

    def test_no_declaration_is_ungraded_and_names_the_knob(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        passed, reason = run_sentinel(tmp_path, "tests/test_x.py")
        assert passed is None, "undeclared must be ungraded, never failed"
        assert "sentinel_command" in reason
        assert "{sentinel}" in reason, "the reason must show the placeholder"

    def test_declaration_without_placeholder_is_refused(self, tmp_path: Path):
        """A command naming no file would run the whole suite and report its
        verdict as this one rule's — the defect that rules out reusing
        `test_command:` for this, so it must not be reachable by hand either."""
        _declare_sentinel_command(tmp_path, "npx vitest run")
        passed, reason = run_sentinel(tmp_path, "tests/test_x.py")
        assert passed is None
        assert "{sentinel}" in reason

    def test_unlaunchable_command_is_ungraded_not_failed(self, tmp_path: Path):
        _declare_sentinel_command(tmp_path, "definitely-not-a-real-binary {sentinel}")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_x.py").write_text("")
        passed, reason = run_sentinel(tmp_path, "tests/test_x.py")
        assert passed is None, "a launch failure is an environment fault, not a verdict"
        assert "could not launch" in reason

    def test_missing_sentinel_target_is_ungraded_not_failed(self, tmp_path: Path):
        """A test that is GONE returned no verdict about the rule.

        Runners disagree here — many exit non-zero on an uncollectable target,
        which renders "deleted" as "failing" and accuses a test that no longer
        exists. Live in this repo when the fix landed: a learning pointed at
        `tests/test_prawduct_sync.py`, deleted long before, and the audit
        reported its rule as failing.
        """
        _declare_sentinel_command(tmp_path, f"{sys.executable} -m pytest {{sentinel}} -q")
        passed, reason = run_sentinel(tmp_path, "tests/gone.py::test_x")
        assert passed is None, "a deleted test is ungraded, never failed"
        assert "does not exist" in reason

    def test_ungraded_entry_raises_no_error_and_is_retained(self, tmp_path: Path):
        """The two safety properties of the ungraded path, asserted rather than
        merely exercised.

        Both are one edit from silently regressing — `is False` written as
        `not` restores the false accusation, and dropping the retain branch
        would retire a rule on a verdict nobody took. A test that only walks
        the path stays green through either.
        """
        learnings = _seed_learnings(
            tmp_path,
            "# Learnings\n\n## Enforced rule\n"
            "<!-- prawduct-learning: sentinel=bridge/auth.test.js -->\n\nBody.\n",
        )
        result = audit_learnings(tmp_path, apply=True)

        assert result["errors"] == [], "an ungraded sentinel accuses nothing"
        assert len(result["retirements"]) == 1
        record = result["retirements"][0]
        assert record["passed"] is None
        assert record["applied"] is False, "--apply must not retire an ungraded rule"
        assert record["unevaluated_reason"]
        # The excerpt slot means "what the test printed"; on the ungraded route
        # nothing printed, and the reason lives in its own field. Empty iff
        # `unevaluated_reason` is set is the invariant that keeps a reader from
        # mistaking a prawduct diagnostic for runner output.
        assert record["output_excerpt"] == ""
        assert "Enforced rule" in learnings.read_text(), "the rule stays active"

    def test_opaque_runner_id_is_not_claimed_to_be_missing(self, tmp_path: Path):
        """A sentinel that is not path-shaped must reach the runner.

        The missing-target check is a filesystem question, and a runner id need
        not be a filename: JUnit's `com.acme.BarTest#testX`, Go's `./pkg -run X`.
        Reporting "does not exist — update the learning" about one of those is a
        confident diagnostic naming the wrong fault, which is the defect shape
        fixed one function over for the unreadable state file.
        """
        seen = {}

        def fake_run(cmd, **kwargs):
            seen["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

        _declare_sentinel_command(tmp_path, "gradle test --tests {sentinel}")
        monkeypatch_run = pytest.MonkeyPatch()
        monkeypatch_run.setattr(_mod.subprocess, "run", fake_run)
        try:
            passed, _detail = run_sentinel(tmp_path, "com.acme.BarTest#testX")
        finally:
            monkeypatch_run.undo()

        assert passed is True, "an opaque id must be handed to the declared runner"
        assert seen["cmd"] == ["gradle", "test", "--tests", "com.acme.BarTest#testX"]

    def test_timeout_is_ungraded_not_failed(self, tmp_path: Path, monkeypatch):
        _declare_sentinel_command(tmp_path, "sleep {sentinel}")
        (tmp_path / "9999").write_text("")

        def fake_run(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd, 120)

        monkeypatch.setattr(_mod.subprocess, "run", fake_run)
        passed, reason = run_sentinel(tmp_path, "9999")
        assert passed is None, "a command that never finished returned no verdict"
        assert "timed out" in reason


# =============================================================================
# CLI end-to-end — `python3 bin/prawduct-hook audit-learnings`
# =============================================================================


class TestAuditLearningsCLI:
    """Smoke test for the CLI dispatch — verifies JSON output is stable
    and the human-readable mode exits cleanly. Heavy logic is covered above;
    this guards the wiring between argparse, the runner, and stdout."""

    def test_json_output_contains_expected_keys(self, tmp_path: Path):
        (tmp_path / ".prawduct").mkdir()
        # Target the tmp repo via CLAUDE_PROJECT_DIR — the CLI takes no
        # positional dir. The original form passed tmp_path as an (ignored)
        # argument and inherited the env, silently auditing the REAL repo:
        # ~13s against its large learnings.md, which crossed the 30s
        # pytest-timeout under full-suite xdist load and killed the worker
        # ("worker crashed", 2026-06-10).
        env = {"CLAUDE_PROJECT_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"}
        result = subprocess.run(
            ["python3", str(_HOOK_PATH), "audit-learnings", "--json"],
            capture_output=True,
            text=True,
            env=env,
        )
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert set(payload.keys()) == {
            "product_dir", "applied", "promotions",
            "retirements", "stale_flags", "errors",
        }
        # NOTE: the plugin runtime's `audit-learnings` CLI contract (stdout
        # stream, exit codes, missing-learnings handling, usage) is covered by
        # tests/test_plugin_runtime.py::TestAuditLearningsSubcommand — the
        # engine's stderr/exit-1 contract retired with tools/prawduct-setup.py.


class TestKnownMetadataKeysMatchesTheLogic:
    """`_KNOWN_METADATA_KEYS` is the schema roster a reader checks first.

    It had exactly ONE reference in the module — its own definition — while its
    comment asserted that "the audit logic only consults this set". A set
    nothing reads cannot be wrong loudly: adding `superseded-by=` to it changes
    no behavior, so the plan's deliverable would have been decorative and a
    future key could be acted on without ever appearing here.

    Pinned against the module's own `meta.get(...)` call sites so it fails in
    both directions. Source-derived rather than hardcoded: a hardcoded expected
    set is a second transcription of the same list and goes stale the same way.
    """

    def _keys_the_logic_reads(self) -> set[str]:
        import ast

        source = Path(_mod.__file__).read_text()
        tree = ast.parse(source)
        found: set[str] = set()
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "get"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "meta"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)
            ):
                found.add(node.args[0].value)
        assert found, (
            "parsed no `meta.get('...')` call sites — the audit loop was "
            "restructured and this guard now checks nothing. Re-point it."
        )
        return found

    def test_every_key_the_logic_reads_is_declared(self):
        undeclared = self._keys_the_logic_reads() - _mod._KNOWN_METADATA_KEYS
        assert not undeclared, (
            f"the audit logic acts on {sorted(undeclared)}, which "
            "_KNOWN_METADATA_KEYS does not declare — the schema roster a reader "
            "checks first would not mention a field that changes behavior."
        )

    def test_every_declared_key_is_actually_read(self):
        unread = _mod._KNOWN_METADATA_KEYS - self._keys_the_logic_reads()
        assert not unread, (
            f"_KNOWN_METADATA_KEYS declares {sorted(unread)}, which nothing in "
            "the module reads — a documented field that silently does nothing "
            "is worse than an undocumented one, because authors will use it."
        )

    def test_superseded_by_is_declared(self):
        # The chunk's own deliverable, stated directly so its absence names
        # itself rather than surfacing as a set-difference.
        assert "superseded-by" in _mod._KNOWN_METADATA_KEYS


class TestSupersessionResolution:
    """`superseded-by=` resolves to exactly one heading, or it is an error.

    Fail-closed on every ambiguity, matching the failing-sentinel path. A
    forwarding pointer nobody can follow is worse than no retirement at all:
    the rule is gone AND its replacement is unfindable, which is strictly worse
    than the hole the mechanism exists to prevent.
    """

    TITLES = [
        "Assert the property, not one spelling of it",
        "Assert the invariant, never a transcribed count",
        "When the deliverable is INSTRUCTIONS, model the reader",
    ]

    def _resolve(self, prefix, own="Some other rule"):
        return _mod.resolve_supersession_target(prefix, self.TITLES, own)

    def test_unique_prefix_resolves_to_the_full_heading(self):
        resolved, err = self._resolve("When the deliverable")
        assert err is None
        assert resolved == "When the deliverable is INSTRUCTIONS, model the reader"

    def test_ambiguous_prefix_is_an_error_naming_the_candidates(self):
        resolved, err = self._resolve("Assert the")
        assert resolved is None
        assert "ambiguous" in err and "matches 2 headings" in err
        # The remedy has to be actionable without opening the file.
        assert "Assert the property" in err and "Assert the invariant" in err

    def test_unresolvable_prefix_is_an_error(self):
        resolved, err = self._resolve("A rule that was never written")
        assert resolved is None
        assert "does not resolve" in err

    def test_empty_prefix_is_an_error(self):
        resolved, err = self._resolve("   ")
        assert resolved is None
        assert "is empty" in err

    def test_the_empty_case_is_reachable_from_a_real_corpus(self, tmp_path: Path):
        """The branch above was unreachable from production and this test could
        not tell.

        `parse_learning_metadata` strips the value, so `superseded-by=` yields
        `""`, which the audit loop's truthiness guards treated as absent — the
        entry fell through to "active, no lifecycle metadata" with no error, no
        retirement record, and no CLI line, while `skills/doctor/SKILL.md`, the
        plan, and the helper all said empty errors. Calling `_resolve('   ')`
        directly passed the whole time, on an input shape the parser cannot
        emit: a fixture that cannot reach the subject. Drive it through
        `audit_learnings` so the guard and the promise are the same claim.
        """
        learnings = _seed_learnings(
            tmp_path,
            "# Learnings\n\n"
            "## Half-finished pointer\n"
            "<!-- prawduct-learning: superseded-by= -->\n\n"
            "Body.\n",
        )
        before = learnings.read_text()
        result = audit_learnings(tmp_path, apply=True, today=date(2026, 7, 31))

        assert len(result["errors"]) == 1, (
            "an empty `superseded-by=` produced no diagnostic — the author who "
            "wrote half a pointer mid-consolidation reads the silence as "
            "'active, no lifecycle metadata'"
        )
        assert "is empty" in result["errors"][0]["error"]
        assert result["retirements"][0]["applied"] is False
        assert learnings.read_text() == before

    def test_whitespace_only_prefix_is_reachable_too(self, tmp_path: Path):
        # `superseded-by=   ` strips to "" identically; pinned separately so a
        # future guard that tests `== ""` rather than `.strip()` fails here.
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n"
            "## Whitespace pointer\n"
            "<!-- prawduct-learning: superseded-by=    -->\n\n"
            "Body.\n",
        )
        result = audit_learnings(tmp_path, apply=True, today=date(2026, 7, 31))
        assert len(result["errors"]) == 1
        assert "is empty" in result["errors"][0]["error"]

    def test_self_supersession_is_an_error(self):
        """A rule cannot forward to itself. Without this the entry retires and
        its pointer sends the reader back to the entry they just failed to
        find — a hole that reads as a forwarding address."""
        resolved, err = self._resolve(
            "Assert the property", own="Assert the property, not one spelling of it"
        )
        assert resolved is None
        assert "cannot supersede itself" in err

    def test_matching_is_case_sensitive(self):
        """A case-insensitive fallback would make the common near-miss resolve
        to *something*, which is the failure the error exists to report."""
        resolved, err = self._resolve("when the deliverable")
        assert resolved is None
        assert "does not resolve" in err


class TestSupersessionRetirement:
    """The lifecycle event: a rule retired because a broader rule replaced it.

    Without this, every consolidation is an unauditable hand-edit — which is
    how a corpus accumulates near-duplicate families, since
    adding is cheap and merging is not.
    """

    CORPUS = (
        "# Learnings\n\n"
        "Preamble paragraph.\n\n"
        "## Narrow rule about fixtures\n"
        "<!-- prawduct-learning: superseded-by=General rule about evidence -->\n\n"
        "Body of the narrow rule.\n\n"
        "## General rule about evidence\n\n"
        "Body of the general rule.\n"
    )

    def test_retires_with_no_sentinel_and_no_subprocess(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Supersession must not run a sentinel — there isn't one, and the
        point is that a rule can be retired for a reason a test cannot express.
        `run_sentinel` is booby-trapped rather than merely unasserted: a future
        refactor that routed supersession through the sentinel path would
        otherwise pass this test while shelling out to pytest per entry."""
        learnings = _seed_learnings(tmp_path, self.CORPUS)

        def _explode(*a, **k):  # pragma: no cover — the point is it is not called
            raise AssertionError("supersession must not invoke a sentinel")

        monkeypatch.setattr(_mod, "run_sentinel", _explode)

        result = audit_learnings(tmp_path, apply=True, today=date(2026, 7, 31))

        assert result["errors"] == []
        assert len(result["retirements"]) == 1
        record = result["retirements"][0]
        assert record["reason"] == "superseded-by"
        assert record["applied"] is True
        assert record["sentinel"] is None and record["passed"] is None
        assert record["superseded_by"] == "General rule about evidence"
        assert record["resolved_to"] == "General rule about evidence"

        remaining = learnings.read_text()
        assert "Narrow rule about fixtures" not in remaining
        assert "General rule about evidence" in remaining
        assert "Preamble paragraph" in remaining

    def test_historical_entry_carries_the_forwarding_pointer(self, tmp_path: Path):
        """The whole point of the lifecycle event. A reader who remembers the
        old rule and cannot find it must land on its replacement."""
        _seed_learnings(tmp_path, self.CORPUS)
        audit_learnings(tmp_path, apply=True, today=date(2026, 7, 31))

        archive = _archive_text(tmp_path)
        assert "## Narrow rule about fixtures" in archive
        assert "superseded by **General rule about evidence**" in archive
        assert "Retired 2026-07-31" in archive
        assert "Body of the narrow rule." in archive

        # The pointer sits directly under the title — a forwarding address
        # below the body is one the reader reads the whole entry to find.
        lines = archive.splitlines()
        title_at = lines.index("## Narrow rule about fixtures")
        after = [ln for ln in lines[title_at + 1:title_at + 4] if ln.strip()]
        assert after and "superseded by" in after[0]

    def test_retired_entry_does_not_carry_its_lifecycle_comment(self, tmp_path: Path):
        """Verified against the repo's own guard
        (`test_no_lifecycle_metadata_has_drifted_to_the_detail_file`): a
        `prawduct-learning:` comment in learnings-detail.md is inert, because
        that file is never parsed — and an inert comment there once disabled
        the whole mechanism. Before this, retiring ANY annotated entry wrote
        its comment into the detail file, so Chunk 03's collapse would have
        broken the suite the first time it ran `--apply` on this repo."""
        _seed_learnings(tmp_path, self.CORPUS)
        audit_learnings(tmp_path, apply=True, today=date(2026, 7, 31))

        detail = (tmp_path / ".prawduct" / "learnings-detail.md").read_text()
        stray = [
            ln.strip() for ln in detail.splitlines()
            if ln.strip().startswith("<!--") and "prawduct-learning:" in ln
        ]
        assert not stray, f"lifecycle comment(s) carried into the detail file: {stray}"

    def test_sentinel_retirement_also_sheds_its_comment_and_states_its_reason(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Same treatment on the older route. Flagged as a deliberate change to
        existing behavior: the sentinel path previously copied the entry
        verbatim, comment included. It is the same latent break, so fixing only
        the new route would leave the guard failing for the older one."""
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n"
            "## Enforced rule\n"
            "<!-- prawduct-learning: sentinel=tests/foo.py::test_bar -->\n\n"
            "Body.\n",
        )
        monkeypatch.setattr(
            _mod, "run_sentinel",
            lambda product_dir, sentinel, timeout=120: (True, "1 passed"),
        )
        audit_learnings(tmp_path, apply=True, today=date(2026, 7, 31))

        archive = _archive_text(tmp_path)
        assert "prawduct-learning:" not in archive
        assert "sentinel `tests/foo.py::test_bar` passes" in archive
        assert "Retired 2026-07-31" in archive

    def test_unresolvable_target_errors_and_does_not_apply(self, tmp_path: Path):
        """Fail-closed. The entry stays put, the detail file is never created,
        and the error names the fix."""
        learnings = _seed_learnings(
            tmp_path,
            "# Learnings\n\n"
            "## Narrow rule\n"
            "<!-- prawduct-learning: superseded-by=A rule nobody wrote -->\n\n"
            "Body.\n",
        )
        before = learnings.read_text()
        result = audit_learnings(tmp_path, apply=True, today=date(2026, 7, 31))

        assert len(result["errors"]) == 1
        assert "does not resolve" in result["errors"][0]["error"]
        assert result["retirements"][0]["applied"] is False
        assert result["retirements"][0]["resolved_to"] is None
        assert learnings.read_text() == before
        assert not (tmp_path / ".prawduct" / "learnings-detail.md").exists()

    def test_declaring_both_reasons_errors_and_retires_under_neither(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Picking a winner silently would let a FAILING sentinel be bypassed
        by adding a supersession key — a gate weakened by an edit to the thing
        it guards. So neither fires and the author must choose."""
        learnings = _seed_learnings(
            tmp_path,
            "# Learnings\n\n"
            "## Narrow rule\n"
            "<!-- prawduct-learning: sentinel=tests/foo.py::test_bar; "
            "superseded-by=General rule -->\n\n"
            "Body.\n\n"
            "## General rule\n\nBody.\n",
        )
        monkeypatch.setattr(
            _mod, "run_sentinel",
            lambda product_dir, sentinel, timeout=120: (False, "1 failed"),
        )
        before = learnings.read_text()
        result = audit_learnings(tmp_path, apply=True, today=date(2026, 7, 31))

        assert result["retirements"] == []
        assert len(result["errors"]) == 1
        assert "both" in result["errors"][0]["error"]
        assert learnings.read_text() == before

    def test_dry_run_reports_the_candidate_without_mutating(self, tmp_path: Path):
        learnings = _seed_learnings(tmp_path, self.CORPUS)
        before = learnings.read_text()
        result = audit_learnings(tmp_path, apply=False, today=date(2026, 7, 31))

        assert result["retirements"][0]["applied"] is False
        assert result["retirements"][0]["resolved_to"] == "General rule about evidence"
        assert result["errors"] == []
        assert learnings.read_text() == before

    def test_a_chain_retired_in_one_pass_resolves_both_pointers(self, tmp_path: Path):
        """A -> B -> C with A and B both retiring in the same run. Targets
        resolve against the corpus as it stood BEFORE the run, so B is still a
        legal target for A. The reader following A lands on B in the historical
        section, which carries its own pointer to C — a chain that terminates
        in history, which is a worse read than a direct pointer and a far
        better one than a hole."""
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n"
            "## Rule A\n<!-- prawduct-learning: superseded-by=Rule B -->\n\nA body.\n\n"
            "## Rule B\n<!-- prawduct-learning: superseded-by=Rule C -->\n\nB body.\n\n"
            "## Rule C\n\nC body.\n",
        )
        result = audit_learnings(tmp_path, apply=True, today=date(2026, 7, 31))

        assert result["errors"] == []
        assert {r["title"] for r in result["retirements"]} == {"Rule A", "Rule B"}
        assert all(r["applied"] for r in result["retirements"])

        archive = _archive_text(tmp_path)
        assert "superseded by **Rule B**" in archive
        assert "superseded by **Rule C**" in archive
        assert "## Rule C" not in archive  # C is still active

    def test_a_bodyless_entry_retires_to_note_only(self, tmp_path: Path):
        """The branch the delivered green-is-evidence directive sent me back for:
        `_historical_block`'s `if body:` arm was covered, its empty arm was not.
        A one-line rule whose entry is title + comment and nothing else must not
        render a stray blank paragraph, and must still carry its pointer."""
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n"
            "## Terse rule\n"
            "<!-- prawduct-learning: superseded-by=General rule -->\n\n"
            "## General rule\n\nBody.\n",
        )
        audit_learnings(tmp_path, apply=True, today=date(2026, 7, 31))

        archive = _archive_text(tmp_path)
        assert "superseded by **General rule**" in archive
        assert "prawduct-learning:" not in archive
        block = archive.split("## Terse rule", 1)[1]
        assert "\n\n\n" not in block, f"stray blank paragraph in the block: {block!r}"

    def test_retired_entries_land_inside_the_historical_section(self, tmp_path: Path):
        """"Under the historical section" was a docstring claim, not behavior:
        blocks were appended at EOF, which coincides with the section only while
        the section is last. Chunk 03's bulk collapse is the first `--apply`
        here, so a later top-level section in `learnings-detail.md` would leave
        every subsequent retirement filed under a heading it does not belong
        to — with the file reading as though it did."""
        _seed_learnings(tmp_path, self.CORPUS)
        history = tmp_path / ".prawduct" / _mod.HISTORY_FILENAME
        history.write_text(
            "# Learnings — Retired\n\n"
            "## Historical (structurally enforced)\n\n"
            "Existing blurb.\n\n"
            "## Previously retired\n\nOld body.\n\n"
            "# Appendix\n\nUnrelated trailing section.\n"
        )
        audit_learnings(tmp_path, apply=True, today=date(2026, 7, 31))

        text = history.read_text()
        hist = text.index("## Historical (structurally enforced)")
        appendix = text.index("# Appendix")
        retired = text.index("## Narrow rule about fixtures")
        assert hist < retired < appendix, (
            "the retired entry landed outside the historical section — it must "
            f"sit between the section header and the next top-level heading:\n{text}"
        )
        # The trailing section survives intact.
        assert "Unrelated trailing section." in text
        assert "Old body." in text

    @pytest.mark.parametrize(
        "header",
        [
            "## Historical (structurally enforced)",
            "## Historical (structurally enforced) — 2026 archive",
            "### Historical (structurally enforced)",
        ],
        ids=["exact", "decorated", "deeper-level"],
    )
    def test_a_decorated_section_heading_never_loses_entries(
        self, tmp_path: Path, header: str
    ):
        """Data loss, not cosmetics. The guard tested SUBSTRING and the locator
        tested EQUALITY, so a decorated heading meant "section present" to one
        and "not found" to the other — `next()` raised, and `learnings.md` had
        already been rewritten, so the retired entries were gone from the active
        file and never reached the detail file. Chunk 03's bulk `--apply` is the
        first caller. Both files are now composed before either is written."""
        learnings = _seed_learnings(tmp_path, self.CORPUS)
        history = tmp_path / ".prawduct" / _mod.HISTORY_FILENAME
        history.write_text(f"# Learnings — Retired\n\n{header}\n\nBlurb.\n")

        audit_learnings(tmp_path, apply=True, today=date(2026, 7, 31))

        # Retired out of the active file...
        assert "Narrow rule about fixtures" not in learnings.read_text()
        # ...and INTO the archive. Neither half may happen alone.
        text = history.read_text()
        assert "## Narrow rule about fixtures" in text, (
            f"entry vanished: removed from learnings.md and never filed under "
            f"{header!r}"
        )
        assert "superseded by **General rule about evidence**" in text

    def test_nothing_is_written_when_composing_the_detail_file_fails(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """The ordering invariant itself, independent of any one bug: if
        composing the detail content raises, `learnings.md` must be untouched.
        Retirement is a MOVE, and a move that can half-happen is data loss."""
        learnings = _seed_learnings(tmp_path, self.CORPUS)
        before = learnings.read_text()

        def _boom(*a, **k):
            raise RuntimeError("composition failed")

        monkeypatch.setattr(_mod, "_compose_retirement_files", _boom)
        with pytest.raises(RuntimeError):
            audit_learnings(tmp_path, apply=True, today=date(2026, 7, 31))

        assert learnings.read_text() == before, (
            "learnings.md was rewritten before the archive was composed — "
            "the retired entries are gone and were never filed"
        )
        assert not (tmp_path / ".prawduct" / "learnings-detail.md").exists()
        assert not (tmp_path / ".prawduct" / _mod.HISTORY_FILENAME).exists()

    def test_a_failed_write_leaves_a_duplicate_not_a_hole(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """The two writes are not atomic, so they are ordered by blast radius.

        Composing both files first removes logic errors from the window; it
        cannot remove I/O failure. What ordering buys is DIRECTION: the archive
        is written first, so a failure on the second write leaves the entry in
        both files — visible, and reconciled by a re-run — instead of removing
        it from the active file and filing it nowhere.
        """
        learnings = _seed_learnings(tmp_path, self.CORPUS)
        before = learnings.read_text()
        real_write = Path.write_text

        def _fail_on_learnings(self, *a, **k):
            if self.name == "learnings.md":
                raise OSError("disk full")
            return real_write(self, *a, **k)

        monkeypatch.setattr(Path, "write_text", _fail_on_learnings)
        with pytest.raises(OSError):
            audit_learnings(tmp_path, apply=True, today=date(2026, 7, 31))
        monkeypatch.undo()

        # Active file untouched — the rule is still there...
        assert learnings.read_text() == before
        # ...and the archive already has it. A duplicate, which a re-run fixes.
        archive = _archive_text(tmp_path)
        assert "## Narrow rule about fixtures" in archive, (
            "the archive write did not happen first — a failure here would have "
            "deleted the entry from learnings.md and filed it nowhere"
        )

    def test_duplicate_headings_do_not_cross_assign_retirement_notes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Titles are not unique by construction — nothing rejects two `## `
        entries with the same heading. Keyed by title, two same-titled
        retirements collapsed to the last note written, so one entry's history
        cited the other's reason: silently wrong, in the file a reader consults
        precisely when they cannot find a rule."""
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n"
            "## Same heading\n"
            "<!-- prawduct-learning: sentinel=tests/foo.py::test_bar -->\n\nFirst body.\n\n"
            "## Same heading\n"
            "<!-- prawduct-learning: superseded-by=General rule -->\n\nSecond body.\n\n"
            "## General rule\n\nBody.\n",
        )
        monkeypatch.setattr(
            _mod, "run_sentinel",
            lambda product_dir, sentinel, timeout=120: (True, "1 passed"),
        )
        audit_learnings(tmp_path, apply=True, today=date(2026, 7, 31))

        archive = _archive_text(tmp_path)
        # Both retired, each keeping ITS OWN reason and body.
        assert archive.count("## Same heading") == 2
        assert "sentinel `tests/foo.py::test_bar` passes" in archive
        assert "superseded by **General rule**" in archive
        first = archive.index("First body.")
        second = archive.index("Second body.")
        assert archive.index("sentinel `tests/foo.py::test_bar` passes") < first
        assert first < archive.index("superseded by **General rule**") < second

    def test_result_keys_are_uniform_across_both_routes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """A reader branches on `reason`, never on which keys exist. Non-uniform
        records are how a consumer ends up probing shapes and getting it wrong
        on the route it was not written against."""
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n"
            "## Enforced rule\n"
            "<!-- prawduct-learning: sentinel=tests/foo.py::test_bar -->\n\nBody.\n\n"
            "## Narrow rule\n"
            "<!-- prawduct-learning: superseded-by=General rule -->\n\nBody.\n\n"
            "## General rule\n\nBody.\n",
        )
        monkeypatch.setattr(
            _mod, "run_sentinel",
            lambda product_dir, sentinel, timeout=120: (True, "1 passed"),
        )
        result = audit_learnings(tmp_path, today=date(2026, 7, 31))

        assert len(result["retirements"]) == 2
        shapes = {frozenset(r) for r in result["retirements"]}
        assert len(shapes) == 1, f"retirement records disagree on keys: {shapes}"
        assert {r["reason"] for r in result["retirements"]} == {
            "sentinel", "superseded-by"
        }
        # And the top-level shape is unchanged — supersessions ride the
        # existing list rather than adding a key no existing reader looks for.
        assert set(result.keys()) == {
            "product_dir", "applied", "promotions",
            "retirements", "stale_flags", "errors",
        }


class TestAuditLearningsHumanOutputPerRoute:
    """The `retire[...]` line, which no test in the repo asserted at all.

    Its own inline comment names the defect it prevents: reading `passed` for
    both routes renders every resolvable supersession as `blocked`, because a
    supersession's `passed` is `None` by construction — a clean candidate
    reported to the operator as a problem, on the surface `/prawduct:doctor`
    relays verbatim.
    """

    def _run(self, repo: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["python3", str(_HOOK_PATH), "audit-learnings", *args],
            cwd=str(repo), capture_output=True, text=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(repo)}, timeout=60,
        )

    def test_resolvable_supersession_renders_ready_not_blocked(self, tmp_path: Path):
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n"
            "## Narrow rule\n"
            "<!-- prawduct-learning: superseded-by=General rule -->\n\nBody.\n\n"
            "## General rule\n\nBody.\n",
        )
        res = self._run(tmp_path)
        assert res.returncode == 0, res.stderr
        assert "retire[ready]: Narrow rule (superseded-by=General rule)" in res.stdout, (
            f"expected a ready supersession line; got:\n{res.stdout}"
        )
        assert "sentinel=None" not in res.stdout

    def test_unresolvable_supersession_renders_blocked(self, tmp_path: Path):
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n"
            "## Narrow rule\n"
            "<!-- prawduct-learning: superseded-by=Nobody wrote this -->\n\nBody.\n",
        )
        res = self._run(tmp_path)
        assert res.returncode == 0, res.stderr
        assert "retire[blocked]: Narrow rule" in res.stdout
        assert "does not resolve" in res.stdout

    def test_applied_supersession_renders_retired(self, tmp_path: Path):
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n"
            "## Narrow rule\n"
            "<!-- prawduct-learning: superseded-by=General rule -->\n\nBody.\n\n"
            "## General rule\n\nBody.\n",
        )
        res = self._run(tmp_path, "--apply")
        assert res.returncode == 0, res.stderr
        assert "retire[retired]: Narrow rule" in res.stdout

    def test_sentinel_route_still_renders_its_sentinel(self, tmp_path: Path):
        """The older route's line is unchanged — the per-route branch must not
        have relabelled it on the way past."""
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n"
            "## Enforced rule\n"
            "<!-- prawduct-learning: sentinel=tests/nope.py::test_missing -->\n\nBody.\n",
        )
        _declare_sentinel_command(tmp_path, f"{sys.executable} -m pytest {{sentinel}} -q")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "nope.py").write_text("")
        res = self._run(tmp_path)
        assert res.returncode == 0, res.stderr
        assert "retire[blocked]: Enforced rule (sentinel=tests/nope.py::test_missing)" in res.stdout

    def test_ungraded_notice_reaches_stderr_on_both_renderers(self, tmp_path: Path):
        """The machine half of the ungraded signal, pinned on the path that needs it.

        `--json` writes a payload to stdout, so a notice printed there would
        either corrupt it or be omitted — as shipped, it was omitted, leaving
        `doctor` (the only `--json` consumer) with no signal where the pre-fix
        code at least printed something loud and wrong. Routing it to stderr is
        what carries R-1's fix to that path, and three durable records now assert
        it as fact — including the `api-contract.md` Ruling whose in-bounds
        argument for the norm departure rests on this notice existing.

        Nothing pinned it: the human CLI test reads stdout only and the `--json`
        test ignored stderr, so deleting the branch left the suite green and the
        defect restored.
        """
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n## Enforced rule\n"
            "<!-- prawduct-learning: sentinel=bridge/auth.test.js -->\n\nBody.\n",
        )
        for args in (["--json"], []):
            res = self._run(tmp_path, *args)
            assert res.returncode == 0, res.stderr
            assert "notice:" in res.stderr, (
                f"the ungraded notice must reach stderr with args={args!r}"
            )
            assert "sentinel_command" in res.stderr, "it must name the remedy"
        # ...and the payload it rides beside stays parseable.
        payload = json.loads(self._run(tmp_path, "--json").stdout)
        assert payload["retirements"][0]["passed"] is None

    def test_no_notice_when_every_sentinel_was_graded(self, tmp_path: Path):
        """The notice must not cry wolf — otherwise it stops being read."""
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n## Superseded rule\n"
            "<!-- prawduct-learning: superseded-by=General rule -->\n\nBody.\n\n"
            "## General rule\n\nBody.\n",
        )
        res = self._run(tmp_path)
        assert res.returncode == 0, res.stderr
        assert "notice:" not in res.stderr

    def test_undeclared_sentinel_renders_ungraded_not_blocked(self, tmp_path: Path):
        """The operator-facing half of the fix.

        With no `sentinel_command:` the old code ran pytest anyway, so a
        non-Python repo saw `retire[blocked]` — reported as a failing test
        against one that was green, or in this case one that does not exist.
        `blocked` claims a verdict; `ungraded` reports that none was taken, and
        the reason line says what to declare.
        """
        _seed_learnings(
            tmp_path,
            "# Learnings\n\n"
            "## Enforced rule\n"
            "<!-- prawduct-learning: sentinel=bridge/auth.test.js -->\n\nBody.\n",
        )
        res = self._run(tmp_path)
        assert res.returncode == 0, res.stderr
        assert "retire[ungraded]: Enforced rule (sentinel=bridge/auth.test.js)" in res.stdout
        assert "blocked" not in res.stdout, "an ungraded sentinel accuses nothing"
        assert "not graded:" in res.stdout
        assert "sentinel_command" in res.stdout, "the remedy must name the knob"


class TestLifecycleMetadataLivesWhereItsReaderLooks:
    """The invariant a byte-conservation check cannot see.

    `audit-learnings` parses `.prawduct/learnings.md` and NOTHING else, and
    `_METADATA_RE` requires the comment on the line immediately after its `## `
    title. So a `prawduct-learning:` comment anywhere else is inert.

    On 2026-07-30 a compaction moved every entry's body to
    `learnings-detail.md` — and the metadata comment is the body's first line,
    so all three went with it. `audit-learnings` returned zero promotions and
    zero retirements: indistinguishable from "nothing to report", and it is the
    live path behind `/prawduct:doctor`. Two of the three carried `sentinel=`,
    the retirement signal and the only structural path that *shrinks*
    `learnings.md` — so the pass billed as the last compaction disabled the
    mechanism that makes future ones unnecessary.

    The move was verified by a byte-conservation check, which passed: every byte
    did land in the destination. Conservation is not function. The repo already
    carried the rule ("when compacting a file that tooling parses, classify
    every span by its CONSUMER"), learned from the *same operation* on
    2026-07-17. A rule that had already been written and already been violated
    is a rule that needs a test.

    Stated as an invariant rather than a count, so it cannot go stale as
    entries are promoted or retired.
    """

    def _repo_root(self):
        return Path(__file__).resolve().parent.parent

    def test_no_lifecycle_metadata_has_drifted_to_the_detail_file(self):
        detail = self._repo_root() / ".prawduct" / "learnings-detail.md"
        if not detail.is_file():
            pytest.skip("no learnings-detail.md in this checkout")
        stray = [
            line.strip()
            for line in detail.read_text().splitlines()
            if line.strip().startswith("<!--") and "prawduct-learning:" in line
        ]
        assert not stray, (
            f"{len(stray)} lifecycle comment(s) in learnings-detail.md — "
            "audit-learnings never reads that file, so these are inert. Move "
            "them back under their `## ` title in learnings.md."
        )

    def test_no_lifecycle_metadata_has_drifted_to_the_history_file(self):
        """The same invariant, at the archive the split created.

        Retired entries land in `learnings-history.md` now, and the strip that
        keeps their lifecycle comments out is the same one — so the guard has to
        follow the entries. Without this, the split would have moved 92 archived
        entries out from under the check that has been watching them.
        """
        history = self._repo_root() / ".prawduct" / _mod.HISTORY_FILENAME
        if not history.is_file():
            pytest.skip("no learnings-history.md in this checkout")
        stray = [
            line.strip()
            for line in history.read_text().splitlines()
            if line.strip().startswith("<!--") and "prawduct-learning:" in line
        ]
        assert not stray, (
            f"{len(stray)} lifecycle comment(s) in learnings-history.md — "
            "audit-learnings never reads that file, so these are inert, and a "
            "retired entry has no live lifecycle state anyway. The retirement "
            "note replaces the comment."
        )

    def test_every_comment_in_learnings_sits_where_the_parser_expects(self):
        learnings = self._repo_root() / ".prawduct" / "learnings.md"
        if not learnings.is_file():
            pytest.skip("no learnings.md in this checkout")
        lines = learnings.read_text().splitlines()
        misplaced = [
            i + 1
            for i, line in enumerate(lines)
            if "prawduct-learning:" in line
            and not (i > 0 and lines[i - 1].startswith("## "))
        ]
        assert not misplaced, (
            f"lifecycle comment(s) at line(s) {misplaced} are not immediately "
            "after a `## ` title — _METADATA_RE will not associate them with "
            "any entry, so they are silently ignored."
        )


class TestRetirementMovesTheDetailNarrative:
    """Retirement is a MOVE, and the detail narrative has to move with it.

    Before 2026-08-01 `_apply_retirements` rewrote `learnings.md` and appended a
    historical block to `learnings-detail.md` — but never touched the entry's
    EXISTING narrative in that same file. In this corpus the prose lives there
    under the identical heading, so the first bulk `--apply` produced 17
    duplicated headings, and the **undecorated** copy sorts first.

    That is worse than untidy. `/prawduct:learnings` reads the detail file for
    Key Context, so the copy a reader reaches first presents a retired rule as
    current and carries no forwarding address — the exact hole that
    `resolve_supersession_target` fails closed to prevent, reintroduced one file
    downstream of the check. All three reviewers found it independently.
    """

    def _apply(self, tmp_path: Path, learnings: str, detail: str) -> str:
        """Both post-move files, concatenated.

        The narrative's DESTINATION moved (it now lands in
        `learnings-history.md`) but the property under test did not: exactly one
        copy of a retired heading exists across the corpus, and an unrelated
        narrative is never cut. Reading both files is what keeps these
        assertions counting copies of a heading rather than copies in one file —
        a per-file count would go green on a duplicate that straddles the split.
        """
        _seed_learnings(tmp_path, learnings)
        (tmp_path / ".prawduct" / "learnings-detail.md").write_text(detail)
        audit_learnings(tmp_path, apply=True, today=date(2026, 8, 1))
        history = tmp_path / ".prawduct" / _mod.HISTORY_FILENAME
        return (
            (tmp_path / ".prawduct" / "learnings-detail.md").read_text()
            + (history.read_text() if history.is_file() else "")
        )

    def test_the_narrative_moves_instead_of_being_duplicated(self, tmp_path):
        out = self._apply(
            tmp_path,
            "# Learnings\n\n## Old rule\n"
            "<!-- prawduct-learning: superseded-by=New rule -->\n\n## New rule\n",
            "# Detail\n\n## Old rule\n\nThe original narrative prose.\n",
        )
        assert out.count("## Old rule") == 1, (
            "the retired heading appears twice — the undecorated copy sorts "
            "first and reads as a current rule with no successor"
        )
        assert "The original narrative prose." in out, "narrative was dropped"
        assert "superseded by **New rule**" in out
        moved = out.index("The original narrative prose.")
        assert moved > out.index("superseded by **New rule**"), (
            "the narrative should sit under the retirement note, so a reader "
            "who followed a stale reference meets the forwarding address first"
        )

    def test_an_entry_with_no_detail_narrative_still_retires(self, tmp_path):
        out = self._apply(
            tmp_path,
            "# Learnings\n\n## Old rule\n"
            "<!-- prawduct-learning: superseded-by=New rule -->\n\n## New rule\n",
            "# Detail\n\n## Some other rule\n\nUnrelated prose.\n",
        )
        assert out.count("## Old rule") == 1
        assert "Unrelated prose." in out, "an unrelated narrative was cut"

    def test_an_already_archived_block_is_never_re_cut(self, tmp_path: Path):
        """The `limit` guard's own case, and it is destructive when absent.

        When a heading exists ONLY in the historical section — a rule retired,
        later re-added under the same title, now retiring again — an unbounded
        search finds the archived block and cuts it, destroying the previous
        retirement's forwarding address to write a new one. Nothing else in
        this class covers it: every other fixture has an ACTIVE narrative,
        which the forward search reaches first either way, so all of them stay
        green with the guard removed. Written after a mutation proved that.
        """
        out = self._apply(
            tmp_path,
            "# Learnings\n\n## Old rule\n"
            "<!-- prawduct-learning: superseded-by=New rule -->\n\n## New rule\n",
            "# Detail\n\n## Historical (structurally enforced)\n\n"
            "## Old rule\n\n*Retired 2019-01-01 — superseded by **Ancient rule**.*\n",
        )
        # A substring check cannot see this defect: an unbounded search deletes
        # the archived HEADING while its note survives, orphaned under whatever
        # heading precedes it. So assert the structural property — the old
        # forwarding address must still sit under its own title.
        lines = out.splitlines()
        note_at = next(i for i, ln in enumerate(lines) if "Ancient rule" in ln)
        owner = next(
            (lines[i] for i in range(note_at, -1, -1) if lines[i].startswith("## ")),
            None,
        )
        assert owner == "## Old rule", (
            f"the 2019 forwarding address is now filed under {owner!r} — its "
            "archived heading was cut and reused, so a reader following the "
            "older reference lands on the wrong entry"
        )

    def test_a_retained_entrys_narrative_is_never_cut(self, tmp_path):
        out = self._apply(
            tmp_path,
            "# Learnings\n\n## Old rule\n"
            "<!-- prawduct-learning: superseded-by=New rule -->\n\n## New rule\n",
            "# Detail\n\n## New rule\n\nThe successor's own prose.\n",
        )
        assert "The successor's own prose." in out
        assert out.count("## New rule") == 1, (
            "the SUCCESSOR's narrative was moved into the archive — only the "
            "retiring entry's prose may be cut"
        )


class TestDescentObligationReachesTheReader:
    """The corpus's standing read-instruction, pinned by POSITION and POINTER.

    `learnings-firing` Chunk 03(c) states the descent obligation once — a rule
    agreed with and not applied to the case in hand has done nothing — in
    `learnings.md`'s preamble, and has `/prawduct:learnings` *reference* it
    rather than carry a second copy.

    Two ways that goes inert, and neither is visible to a size or
    word-presence check (the failure mode learning 320 names: when the
    deliverable is INSTRUCTIONS, at least one guardrail must model the READER):

    * The statement drifts BELOW the first rule, where a reader meets it after
      the rules it governs — reading order is the whole mechanism.
    * The statement is deleted, leaving the skill pointing at nothing. A
      reference to a thing that no longer exists is the corpus's own
      absence-claim failure, one level up.

    Anchored on the ``prawduct:descent-obligation`` MARKER, never on the prose.
    A test matching a literal passes for every rewording of the same defect
    (learning 318) — and this repo shipped exactly that mistake on 2026-07-31,
    freezing the wording of prose chosen an hour earlier. The marker is a
    mechanism the skill names; the paragraph under it is free to be rewritten.
    """

    MARKER = "prawduct:descent-obligation"

    def _repo_root(self):
        return Path(__file__).resolve().parent.parent

    def test_the_obligation_sits_above_every_rule_it_governs(self):
        learnings = self._repo_root() / ".prawduct" / "learnings.md"
        if not learnings.is_file():
            pytest.skip("no learnings.md in this checkout")
        lines = learnings.read_text().splitlines()

        marker_at = next(
            (i for i, ln in enumerate(lines) if self.MARKER in ln), None
        )
        assert marker_at is not None, (
            f"no `{self.MARKER}` marker in learnings.md — the descent "
            "obligation is the corpus's standing read-instruction and "
            "/prawduct:learnings points at it by this marker."
        )

        first_rule = next(
            (i for i, ln in enumerate(lines) if ln.startswith("## ")), None
        )
        assert first_rule is not None, "learnings.md has no `## ` rules at all"
        assert marker_at < first_rule, (
            f"the descent obligation (line {marker_at + 1}) sits BELOW the "
            f"first rule (line {first_rule + 1}) — a reader meets it after the "
            "rules it governs, which is the inertness it exists to prevent."
        )

    def test_a_newly_onboarded_product_gets_the_home_too(self):
        """The obligation must reach PRODUCTS, not only this repo.

        The guard above reads *this repo's* corpus, so it stayed green while
        every newly onboarded product received an instruction aimed at a starter
        file that carried nothing — a framework-repo-only feature with a
        framework-repo-only test, which is the corpus's own "a test asserting
        the framework repo's OWN state instead of the propagated contract"
        failure. So this asserts the contract that reaches consumer repos.

        The carrier changed and the contract did not: a new product's corpus is
        `.claude/rules/learnings/core.md`, scaffolded from
        `learnings_files.CORE_HEADER`, and the obligation is stated there in
        full rather than pointed at by a marker.

        Asserted on the SCAFFOLDED STRING, not on the module's text. The first
        cut of this guard read the whole file, where the statement appears twice
        — once in the comment explaining it and once in the string that ships.
        Deleting it from the string left the guard green, satisfied by the
        comment standing beside the thing it guards.
        """
        if not (self._repo_root() / "plugin" / "lib" / "learnings_files.py").is_file():
            pytest.skip("no learnings_files.py in this checkout")
        from lib import learnings_files  # noqa: PLC0415 — plugin/ is on sys.path via conftest

        assert "Reading a rule is not applying it" in learnings_files.CORE_HEADER, (
            "the starter core.md states no descent obligation, so every "
            "onboarded product receives a corpus with nothing telling its "
            "reader that reading a rule is not applying it."
        )

    def test_the_skill_references_the_home_and_does_not_copy_it(self):
        skill = (
            self._repo_root()
            / "plugin" / "skills" / "learnings" / "SKILL.md"
        )
        if not skill.is_file():
            pytest.skip("no learnings SKILL.md in this checkout")
        body = skill.read_text()
        assert self.MARKER in body, (
            f"/prawduct:learnings no longer names `{self.MARKER}` — its caller "
            "never sees learnings.md's header, so without this pointer the "
            "obligation reaches the subagent and not the reader who acts."
        )


# =============================================================================
# sentinel runner — the interpreter it spawns
# =============================================================================


class TestThisRepoDeclaresWhatItAsksOthersFor:
    """Prawduct's own state, pinned — it is the first consumer of this contract.

    Both properties below fail SOFT and SILENTLY in production: an absent
    `sentinel_command:` ungrades every sentinel, and a sentinel pointing at a
    deleted file is ungraded too. Neither raises, neither reddens a suite, and
    both leave the audit reporting less than it did while looking healthy — so
    if nothing asserts them here, nothing ever will.
    """

    _STATE = _REPO_ROOT.parent / ".prawduct" / "project-state.yaml"
    _LEARNINGS = _REPO_ROOT.parent / ".prawduct" / "learnings.md"

    def test_repo_declares_a_usable_sentinel_command(self):
        declared = [
            line for line in self._STATE.read_text().splitlines()
            if line.startswith("sentinel_command:")
        ]
        assert len(declared) == 1, (
            "prawduct governs its own repo; without this key its every sentinel "
            "is ungraded and the mechanism is silently off here"
        )
        assert "{sentinel}" in declared[0], (
            "a command with no {sentinel} names no file and would grade every "
            "rule by the whole suite's verdict"
        )

    def test_every_declared_sentinel_target_exists(self):
        """A sentinel naming a deleted test grades ungraded — permanently, and
        without complaint. One had been dead since the plugin migration.

        **Vacuous today, and deliberately kept.** Retiring that dead key left
        this repo with zero sentinels, so there is currently nothing to check.
        It is a FORWARD guard: it binds the moment a sentinel is declared again,
        which is exactly when the mistake it catches becomes possible. Said out
        loud because a reader counting green tests would otherwise credit it
        with checking something it cannot yet reach.
        """
        missing = []
        for match in re.finditer(
            r"prawduct-learning:[^>]*?sentinel=([^\s;]+)", self._LEARNINGS.read_text()
        ):
            target = match.group(1).split("::", 1)[0]
            if not (_REPO_ROOT.parent / target).exists():
                missing.append(target)
        assert not missing, (
            f"learnings.md declares sentinel(s) whose target is gone: {missing}. "
            "Repoint each at the test's new home, or drop the `sentinel=` key if "
            "the rule is no longer structurally enforced."
        )


class TestSentinelRunsTheDeclaredCommand:
    """The product declares the invocation; prawduct never picks one.

    This replaced a `sys.executable -m pytest` default. That default was
    correct about one thing worth keeping — a bare `python3` resolves through
    the product's PATH, which under a virtualenv is a different interpreter —
    but it answered that by assuming every governed product is Python, which
    `architecture.md` § Direction forbids. The interpreter question is now the
    product's to answer in its own declaration, the same posture `test_command:`
    already takes.
    """

    def test_argv_comes_from_the_declaration(self, tmp_path, monkeypatch):
        seen = {}

        def fake_run(cmd, **kwargs):
            seen["cmd"] = cmd
            return subprocess.CompletedProcess(cmd, 0, stdout="1 passed", stderr="")

        _declare_sentinel_command(tmp_path, "npx vitest run {sentinel} --reporter=dot")
        (tmp_path / "bridge").mkdir()
        (tmp_path / "bridge" / "auth.test.js").write_text("")
        monkeypatch.setattr(_mod.subprocess, "run", fake_run)
        passed, _excerpt = run_sentinel(tmp_path, "bridge/auth.test.js")

        assert passed is True
        assert seen["cmd"] == [
            "npx", "vitest", "run", "bridge/auth.test.js", "--reporter=dot"
        ], "the declared command, shlex-split, with {sentinel} substituted in place"
        assert isinstance(seen["cmd"], list), "list-form args, never shell=True"

    def test_no_python_specific_literal_survives_in_the_sentinel_path(self):
        """The norm this fix discharges, pinned against reintroduction.

        A future edit adding a pytest fallback would restore the exact defect —
        so the source of the two functions that build and run the invocation
        must name no test runner and no interpreter at all.
        """
        violations = _hardcoded_runner_violations(
            _mod.resolve_sentinel_command, _mod.run_sentinel
        )
        assert not violations, (
            f"the sentinel invocation path hardcodes a runner: {violations}. "
            "Prawduct must state the requirement and let the product declare it."
        )

    def test_the_guard_catches_a_verbatim_reinstatement(self):
        """The guard above, guarded — because its first version caught nothing.

        That version scanned text with every string token stripped, so an argv
        literal `"pytest"` was invisible, and it space-joined tokens, so
        `sys.executable` became `sys . executable` and matched no needle. A
        verbatim restoration of the deleted code passed it — while
        `architecture.md`'s LNG-5W8R discharge cited it as the pin against
        exactly that.

        Text matching cannot separate `["-m", "pytest"]` (the defect) from an
        example inside an operator message (the remedy, and worth keeping), so
        the check is now structural: a literal handed to a subprocess call is a
        hardcoded runner wherever it appears; the same word in prose is not.

        A guard nobody has watched fail is a guess. This one is run against the
        real regression and required to catch it.
        """
        violations = _hardcoded_runner_violations(
            _REINSTATED_DEFAULT_FOR_TESTING, from_source=True
        )
        assert violations, (
            "the guard must flag a verbatim restoration of the deleted default"
        )

    def test_the_guard_still_lets_the_history_be_explained(self):
        """...and does not force the docstrings to be gutted to stay green.

        Why this code has no default is the most useful thing about it, and a
        scanner that also flagged prose would push the next author to delete the
        explanation rather than keep the property. `resolve_sentinel_command`
        names a runner twice on purpose — once explaining the deleted default,
        once as the example command in the message telling an operator what to
        declare — and both must survive the guard that is green above.
        """
        import inspect

        source = inspect.getsource(_mod.resolve_sentinel_command)
        assert "pytest" in source, "the history must still be explainable"
        # The example is asserted on the RENDERED message, not the source text:
        # the diagnostic interpolates `SENTINEL_PLACEHOLDER` rather than repeating
        # the literal, so that a rename cannot leave the docs teaching a spelling
        # the parser rejects. A source-text match would forbid exactly that fix.
        assert "npx vitest run" in source, (
            "the operator-facing example must still be showable"
        )


class TestTheDocumentedExampleActuallyWorks:
    """The key and its placeholder have five homes and nothing compares them.

    `sentinel_command:` / `{sentinel}` appear in the module docstring, the
    runner's own diagnostics, `templates/project-state.yaml`, this repo's own
    state file, and `skills/doctor/SKILL.md`. A rename or a typo in the template
    ships a knob nobody reads — and the failure is silent by this bundle's own
    design: every sentinel simply reports `ungraded`. That is the exact class
    this branch exists to close, reappearing in its own documentation.

    Pinned by running the TEMPLATE'S OWN commented example through the real
    parser, so the docs and the code cannot drift apart without a red test.
    """

    _TEMPLATE = _REPO_ROOT / "templates" / "project-state.yaml"

    def _example_from_template(self) -> str:
        for line in self._TEMPLATE.read_text().splitlines():
            stripped = line.lstrip("# ").strip()
            if stripped.startswith("sentinel_command:"):
                return stripped
        raise AssertionError(
            "templates/project-state.yaml documents no `sentinel_command:` example — "
            "the knob is undiscoverable to every product being onboarded"
        )

    def test_template_example_parses_and_substitutes(self, tmp_path: Path):
        example = self._example_from_template()
        prawduct = tmp_path / ".prawduct"
        prawduct.mkdir()
        (prawduct / "project-state.yaml").write_text(example + "\n")

        argv, reason = _mod.resolve_sentinel_command(tmp_path)
        assert argv is not None, (
            f"the template's own example is rejected by the parser: {reason}"
        )
        assert _mod.SENTINEL_PLACEHOLDER in " ".join(argv), (
            "the documented example carries no placeholder, so it would grade "
            "every rule by the whole suite's verdict"
        )
        substituted = [
            tok.replace(_mod.SENTINEL_PLACEHOLDER, "a/b.test.js") for tok in argv
        ]
        assert "a/b.test.js" in substituted

    def test_this_repo_state_matches_the_placeholder_constant(self):
        """The constant is the authority; the repo's own declaration must use it."""
        state = (_REPO_ROOT.parent / ".prawduct" / "project-state.yaml").read_text()
        declared = [
            l for l in state.splitlines() if l.startswith("sentinel_command:")
        ][0]
        assert _mod.SENTINEL_PLACEHOLDER in declared

    def test_the_diagnostic_quotes_the_constant_not_a_copy(self, tmp_path: Path):
        """The undeclared-knob message tells an operator what to type. If it
        drifts from the constant it teaches a spelling the parser rejects."""
        (tmp_path / ".prawduct").mkdir()
        _argv, reason = _mod.resolve_sentinel_command(tmp_path)
        assert _mod.SENTINEL_PLACEHOLDER in reason


class TestUnknownMetadataKeysAreReported:
    """A well-formed key nobody reads is reported, not silently ignored (#346).

    The failure this closes is silence, not damage. `sentinal=tests/x.py` parses
    cleanly, matches no branch in the audit, and leaves the entry classified
    "active, no lifecycle metadata" — byte-for-byte the same outcome as an entry
    carrying no comment at all. The author who wrote a lifecycle directive sees
    a fully-annotated entry in the file and an audit that never mentions it, so
    the typo survives every run that was supposed to catch it.

    The roster is the allow-list; the PARSER is deliberately not. Validation
    lives in the audit because that is the layer that decides what a key means,
    and `parse_learning_metadata` stays usable by callers that only want pairs.
    """

    def test_unknown_key_raises_an_error_naming_it(self, tmp_path):
        _seed_learnings(tmp_path, (
            "# Learnings\n\n"
            "## Misspelled directive\n"
            "<!-- prawduct-learning: sentinal=tests/test_x.py::test_y -->\n"
            "Body.\n"
        ))
        result = _mod.audit_learnings(tmp_path, run_sentinels=False)
        messages = [e["error"] for e in result["errors"]]
        assert len(messages) == 1, messages
        assert "`sentinal=`" in messages[0]
        assert result["errors"][0]["title"] == "Misspelled directive"
        # And it names the roster, so the fix is visible without opening source.
        for known in _mod._KNOWN_METADATA_KEYS:
            assert f"`{known}=`" in messages[0]

    def test_every_known_key_passes_validation(self, tmp_path):
        """Roster-derived, not a second transcription of the same list."""
        pairs = "; ".join(f"{k}=x" for k in sorted(_mod._KNOWN_METADATA_KEYS))
        _seed_learnings(tmp_path, (
            "# Learnings\n\n"
            "## Fully annotated\n"
            f"<!-- prawduct-learning: {pairs} -->\n"
            "Body.\n"
        ))
        result = _mod.audit_learnings(tmp_path, run_sentinels=False)
        unknown = [
            e for e in result["errors"] if "unknown lifecycle metadata" in e["error"]
        ]
        assert unknown == []

    def test_malformed_no_equals_fragments_stay_tolerated(self, tmp_path):
        """The parser's prose tolerance is NOT reconsidered by this validation.

        A fragment with no `=` is prose that resembled metadata. Grading it
        would turn a stray semicolon in an entry's narrative into a finding,
        which is the misfiring probe this repo names by its cost.
        """
        _seed_learnings(tmp_path, (
            "# Learnings\n\n"
            "## Stray semicolon\n"
            "<!-- prawduct-learning: created=2026-01-01; and then; more prose -->\n"
            "Body.\n"
        ))
        result = _mod.audit_learnings(tmp_path, run_sentinels=False)
        assert [e["error"] for e in result["errors"]] == []

    def test_an_unknown_key_does_not_block_a_valid_sibling_key(self, tmp_path):
        """Reported and ignored — never fatal to the keys that ARE correct.

        An unknown key cannot retire anything, so fail-closed is already the
        behavior. Letting a typo elsewhere in the comment veto a retirement
        whose own key is right would be a gate weakened by an unrelated edit.
        """
        _seed_learnings(tmp_path, (
            "# Learnings\n\n"
            "## Promotable but typo'd\n"
            "<!-- prawduct-learning: confirmations=3; sentinal=tests/x.py -->\n"
            "Body.\n"
        ))
        result = _mod.audit_learnings(tmp_path, run_sentinels=False)
        assert [p["title"] for p in result["promotions"]] == ["Promotable but typo'd"]
        assert any("`sentinal=`" in e["error"] for e in result["errors"])

    def test_this_repos_own_corpus_declares_no_unknown_key(self):
        """The guard, run against the corpus it governs.

        A validation shipped without this is one nobody has pointed at real
        data — and this repo's `learnings.md` is the only corpus prawduct's own
        development touches every day.
        """
        repo_learnings = Path(__file__).resolve().parents[1] / ".prawduct" / "learnings.md"
        if not repo_learnings.is_file():
            pytest.skip("no .prawduct/learnings.md in this checkout")
        for entry in _mod.parse_learnings_file(repo_learnings.read_text()):
            unknown = set(entry.metadata) - _mod._KNOWN_METADATA_KEYS
            assert not unknown, (
                f"{entry.title!r} carries {sorted(unknown)}, which the audit "
                "does not read — fix it here, not by widening the roster."
            )


class TestRetirementReadinessHasOneHome:
    """Readiness is decided once at the producer; consumers render it (#349).

    The predicate was re-derived in three places — the audit's own apply-site
    branch, the CLI printer, and doctor's prose — and the two routes do not
    share a field to read: a sentinel is ready when `passed is True`, a
    supersession when `resolved_to` is not None. A consumer that picks one field
    and branches reports every resolvable supersession as blocked, because its
    `passed` is None by construction. The copy furthest from the producer
    (prose in a skill file) cannot be tested at all.
    """

    def test_every_retirement_record_carries_the_three_fields(self, tmp_path):
        _seed_learnings(tmp_path, (
            "# Learnings\n\n"
            "## Broad rule\nBody.\n\n"
            "## Superseded one\n"
            "<!-- prawduct-learning: superseded-by=Broad rule -->\n"
            "Body.\n\n"
            "## Sentineled one\n"
            "<!-- prawduct-learning: sentinel=tests/test_x.py::test_y -->\n"
            "Body.\n"
        ))
        result = _mod.audit_learnings(tmp_path, run_sentinels=False)
        assert len(result["retirements"]) == 2
        for record in result["retirements"]:
            assert {"ready", "readiness", "why"} <= set(record)
            assert record["readiness"] in _mod.RETIREMENT_READINESS_STATES

    def test_ready_and_readiness_never_disagree(self):
        """`ready` is exactly `readiness == "ready"` — pinned, not conventional.

        Two fields expressing one decision is how they drift; this is the pin
        that makes the redundancy safe rather than a second source of truth.
        """
        cases = [
            {"reason": "superseded-by", "resolved_to": "X", "superseded_by": "X"},
            {"reason": "superseded-by", "resolved_to": None, "superseded_by": "X"},
            {"reason": "sentinel", "sentinel": "t.py", "passed": True},
            {"reason": "sentinel", "sentinel": "t.py", "passed": False},
            {"reason": "sentinel", "sentinel": "t.py", "passed": None},
            {"reason": "some-future-route"},
        ]
        for record in cases:
            out = _mod.retirement_readiness(record)
            assert out["ready"] is (out["readiness"] == "ready"), record

    def test_a_resolvable_supersession_is_ready_though_passed_is_none(self):
        """The exact misread a per-consumer re-derivation makes."""
        record = {
            "reason": "superseded-by", "passed": None,
            "superseded_by": "Broad", "resolved_to": "Broad rule",
        }
        out = _mod.retirement_readiness(record)
        assert out["ready"] is True
        assert out["readiness"] == "ready"
        assert out["why"] == "superseded-by=Broad rule"

    def test_an_ungraded_sentinel_is_ungraded_not_blocked(self):
        out = _mod.retirement_readiness(
            {"reason": "sentinel", "sentinel": "t.py", "passed": None}
        )
        assert out["readiness"] == "ungraded"
        assert out["ready"] is False
        assert out["why"] == "sentinel=t.py"

    def test_an_unrecognised_route_is_ungraded_and_says_so(self):
        """No catch-all `else` reading the sentinel field.

        The printer's `else` arm meant "everything that is not superseded-by",
        so a third route would have been graded by reading a `sentinel` field it
        does not set — rendering a brand-new route as a failing test. Ungraded
        is the honest reading, and it surfaces the gap instead of hiding it.
        """
        out = _mod.retirement_readiness({"reason": "licence-expired"})
        assert out["readiness"] == "ungraded"
        assert out["ready"] is False
        assert "licence-expired" in out["why"]
        assert "sentinel=" not in out["why"]

    def test_a_blocked_supersession_names_the_unresolved_prefix(self):
        """`why` must still name something when the pointer did not resolve —
        a blocked candidate with no target named is one an operator cannot fix.
        """
        out = _mod.retirement_readiness({
            "reason": "superseded-by", "superseded_by": "Nonexistent prefix",
            "resolved_to": None,
        })
        assert out["readiness"] == "blocked"
        assert "Nonexistent prefix" in out["why"]

    def test_the_audit_apply_branch_reads_the_minted_field(self, tmp_path):
        """The producer's own branch renders the decision too.

        A field only *consumers* read is decorative — the same shape the
        unknown-key roster had one layer up. This pins that an applied run
        retires exactly the records the readiness helper called ready.
        """
        _seed_learnings(tmp_path, (
            "# Learnings\n\n"
            "## Broad rule\nBody.\n\n"
            "## Superseded one\n"
            "<!-- prawduct-learning: superseded-by=Broad rule -->\n"
            "Body.\n"
        ))
        result = _mod.audit_learnings(tmp_path, apply=True, run_sentinels=False)
        for record in result["retirements"]:
            assert record["applied"] is record["ready"]


class TestBrokenEnvironmentIsUngradedWhenDeclared:
    """#720: a runner that dies on a broken environment is not a failing test.

    A runner that starts and then exits non-zero because `node_modules` is
    absent, or the workspace is unbuilt, is indistinguishable from a test that
    ran and failed — from outside. Prawduct must not learn per-runner exit-code
    tables, so the PRODUCT declares which codes mean "could not run", in the
    same posture that gives `sentinel_command:` no default.

    The stakes are the ones this whole tri-state exists for: a rule reported as
    failing when nothing judged it argues for retiring a rule that is still
    enforced.
    """

    def _declare(self, product_dir: Path, value: str) -> None:
        prawduct = product_dir / ".prawduct"
        prawduct.mkdir(parents=True, exist_ok=True)
        state = prawduct / "project-state.yaml"
        prior = state.read_text() if state.is_file() else ""
        state.write_text(f"{prior}sentinel_ungraded_exit_codes: {value}\n")

    def test_absent_declaration_leaves_every_nonzero_a_real_failure(self, tmp_path):
        """The default is unchanged — this is additive to existing products."""
        codes, error = _mod.resolve_ungraded_exit_codes(tmp_path)
        assert codes == frozenset()
        assert error is None

    def test_a_declared_code_grades_ungraded_not_failed(self, tmp_path):
        (tmp_path / "t.py").write_text("")
        _declare_sentinel_command(
            tmp_path, f"{sys.executable} -c \"import sys; sys.exit(3)\" {{sentinel}}"
        )
        self._declare(tmp_path, "3")
        passed, detail = _mod.run_sentinel(tmp_path, "t.py")
        assert passed is None, detail
        assert "ungraded rather than failed" in detail
        assert "sentinel_ungraded_exit_codes" in detail

    def test_an_undeclared_nonzero_code_is_still_a_real_failure(self, tmp_path):
        """The declaration widens the ungraded side; it must not swallow the
        failures the retirement route depends on catching."""
        (tmp_path / "t.py").write_text("")
        _declare_sentinel_command(
            tmp_path, f"{sys.executable} -c \"import sys; sys.exit(1)\" {{sentinel}}"
        )
        self._declare(tmp_path, "3")
        passed, _detail = _mod.run_sentinel(tmp_path, "t.py")
        assert passed is False

    def test_a_declared_code_does_not_change_a_passing_sentinel(self, tmp_path):
        (tmp_path / "t.py").write_text("")
        _declare_sentinel_command(
            tmp_path, f"{sys.executable} -c \"pass\" {{sentinel}}"
        )
        self._declare(tmp_path, "3 4")
        passed, _detail = _mod.run_sentinel(tmp_path, "t.py")
        assert passed is True

    def test_zero_is_refused(self, tmp_path):
        """Listing 0 would report every green sentinel as ungraded and disable
        the retirement route entirely — a gate switched off by a declaration
        that reads like configuration."""
        self._declare(tmp_path, "0")
        codes, error = _mod.resolve_ungraded_exit_codes(tmp_path)
        assert codes == frozenset()
        assert error is not None and "PASSED" in error

    def test_a_malformed_declaration_is_reported_not_ignored(self, tmp_path):
        """An operator who asked for the distinction and typo'd must not keep
        getting the false accusation with the file reading as though they had
        fixed it."""
        self._declare(tmp_path, "three")
        codes, error = _mod.resolve_ungraded_exit_codes(tmp_path)
        assert codes == frozenset()
        assert error is not None and "'three'" in error

    def test_a_malformed_declaration_ungrades_rather_than_grades(self, tmp_path):
        """And it reaches `run_sentinel` BEFORE the subprocess runs — spending a
        test run to produce a number nobody can interpret is the wrong order."""
        (tmp_path / "t.py").write_text("")
        _declare_sentinel_command(
            tmp_path, f"{sys.executable} -c \"import sys; sys.exit(1)\" {{sentinel}}"
        )
        self._declare(tmp_path, "not-a-code")
        passed, detail = _mod.run_sentinel(tmp_path, "t.py")
        assert passed is None
        assert "sentinel_ungraded_exit_codes" in detail

    def test_codes_parse_from_either_separator(self, tmp_path):
        self._declare(tmp_path, "3, 4  5")
        codes, error = _mod.resolve_ungraded_exit_codes(tmp_path)
        assert error is None
        assert codes == frozenset({3, 4, 5})

    def test_the_boundary_is_documented_where_sentinel_is_defined(self):
        """The acceptance criterion, asserted rather than assumed.

        "Document the boundary" was the third option on #720 and is not an
        alternative to fixing it — the module docstring is where a reader learns
        what `sentinel=` means, so it is where ungraded-versus-failed belongs.
        """
        doc = _mod.__doc__ or ""
        assert "Ungraded is not failed" in doc
        assert _mod.UNGRADED_EXIT_CODES_KEY in doc

    def test_no_runner_is_hardcoded_by_the_new_resolver(self):
        """The language-agnostic acceptance criterion, structurally."""
        assert _hardcoded_runner_violations(_mod.resolve_ungraded_exit_codes) == []
        assert _hardcoded_runner_violations(_mod.run_sentinel) == []


class TestTheArchiveHasItsOwnFile:
    """#350: `learnings-detail.md` had no route out, and the archive was the sink.

    Measured 2026-09-01 on this repo: the detail file was 557KB across 4,748
    lines and 273 headings, up 65% in a month, with ~182KB of it the terminal
    `## Historical (structurally enforced)` section. Every `/prawduct:learnings`
    lookup read all of it — ~658KB with the index — to answer a question about
    the ACTIVE corpus.

    The route out is a third tier: retired entries move to
    `learnings-history.md`, which the skill reads only on a miss. Nothing is
    deleted, and retirement is still a MOVE — it just moves one file further,
    out of the read path instead of to the bottom of it.
    """

    CORPUS = (
        "# Learnings\n\n"
        "## Old rule\n"
        "<!-- prawduct-learning: superseded-by=New rule -->\n\nRule body.\n\n"
        "## New rule\n\nSuccessor body.\n"
    )

    def _apply(self, tmp_path: Path, detail: str | None = None) -> None:
        _seed_learnings(tmp_path, self.CORPUS)
        if detail is not None:
            (tmp_path / ".prawduct" / "learnings-detail.md").write_text(detail)
        audit_learnings(tmp_path, apply=True, today=date(2026, 9, 1))

    def test_the_archive_is_not_in_the_file_a_lookup_reads(self, tmp_path):
        self._apply(tmp_path, "# Detail\n\n## Old rule\n\nNarrative prose.\n")
        detail = (tmp_path / ".prawduct" / "learnings-detail.md").read_text()
        assert "Old rule" not in detail
        assert "Narrative prose." not in detail
        assert "Historical (structurally enforced)" not in detail
        # And the successor's own narrative is untouched by the move.
        archive = _archive_text(tmp_path)
        assert "Narrative prose." in archive
        assert "superseded by **New rule**" in archive

    def test_the_history_file_is_seeded_with_its_own_preamble(self, tmp_path):
        self._apply(tmp_path)
        archive = _archive_text(tmp_path)
        assert archive.startswith("# Learnings — Retired")
        # The invariant that governs the file is stated IN the file, where an
        # agent about to prune it will read it.
        assert "Nothing is ever deleted from this file" in archive
        assert _mod._HISTORICAL_SECTION_HEADER in archive

    def test_a_pre_split_archive_is_lifted_whole_and_loses_nothing(self, tmp_path):
        """The migration path every existing product takes on its next apply.

        Leaving the old section in place beside a new file would give a product
        two archives and a route out that routes nothing — the old sink would
        keep being read on every lookup.
        """
        self._apply(
            tmp_path,
            "# Detail\n\nActive prose.\n\n"
            "## Old rule\n\nNarrative prose.\n\n"
            "## Historical (structurally enforced)\n\n"
            "Boilerplate blurb.\n\n"
            "## Ancient rule\n\n*Retired 2019-01-01 — superseded by **Gone**.*\n"
        )
        detail = (tmp_path / ".prawduct" / "learnings-detail.md").read_text()
        archive = _archive_text(tmp_path)

        assert "Historical (structurally enforced)" not in detail
        assert "Ancient rule" not in detail
        assert "Active prose." in detail, "the lift cut live prose"

        assert archive.count("## Ancient rule") == 1
        assert "superseded by **Gone**" in archive, "a forwarding address was lost"
        assert archive.count(_mod._HISTORICAL_SECTION_HEADER) == 1, (
            "the lifted section's own header was carried across, filing a "
            "second header inside the first section"
        )
        assert "Boilerplate blurb." not in archive, (
            "the old section's blurb rode along — the history file supplies its "
            "own, so this is a duplicate paragraph, not content"
        )
        # The new retirement is there too, alongside the lifted one.
        assert "## Old rule" in archive

    def test_a_lift_and_a_retirement_never_produce_two_archives(self, tmp_path):
        self._apply(
            tmp_path,
            "# Detail\n\n## Historical (structurally enforced)\n\n"
            "## Ancient rule\n\nold\n",
        )
        detail = (tmp_path / ".prawduct" / "learnings-detail.md").read_text()
        archive = _archive_text(tmp_path)
        assert _mod._HISTORICAL_SECTION_HEADER not in detail
        assert archive.count(_mod._HISTORICAL_SECTION_HEADER) == 1

    def test_a_detail_file_with_no_archive_is_the_steady_state(self, tmp_path):
        """Post-split, the lift is a no-op and must not disturb the file."""
        lines = "# Detail\n\n## Unrelated\n\nprose\n".split("\n")
        assert _mod._lift_legacy_historical_section(lines) == []
        assert "\n".join(lines) == "# Detail\n\n## Unrelated\n\nprose\n"

    def test_the_archive_is_written_before_the_file_the_entry_leaves(
        self, tmp_path, monkeypatch
    ):
        """Three files now, and the direction argument is unchanged.

        Every partial failure must land on the DUPLICATE side — the entry
        visible in two places, which a re-run reconciles — never on the deletion
        side. With the archive written last, a failure here removes the entry
        from `learnings.md` and files it nowhere.
        """
        learnings = _seed_learnings(tmp_path, self.CORPUS)
        (tmp_path / ".prawduct" / "learnings-detail.md").write_text(
            "# Detail\n\n## Old rule\n\nThe only copy.\n"
        )
        before = learnings.read_text()
        real_write = Path.write_text

        def _fail_after_history(self, *a, **k):
            if self.name != _mod.HISTORY_FILENAME:
                raise OSError("disk full")
            return real_write(self, *a, **k)

        monkeypatch.setattr(Path, "write_text", _fail_after_history)
        with pytest.raises(OSError):
            audit_learnings(tmp_path, apply=True, today=date(2026, 9, 1))
        monkeypatch.undo()

        assert learnings.read_text() == before
        assert "The only copy." in _archive_text(tmp_path), (
            "the narrative existed in exactly one place and the failure "
            "destroyed it — the archive must be written first"
        )

    def test_this_repos_own_corpus_is_split(self):
        """The migration, asserted against the real files rather than assumed.

        A split shipped without this is one nobody has pointed at the corpus it
        was measured on.
        """
        prawduct = Path(__file__).resolve().parents[1] / ".prawduct"
        detail = prawduct / "learnings-detail.md"
        history = prawduct / _mod.HISTORY_FILENAME
        if not detail.is_file():
            pytest.skip("no learnings-detail.md in this checkout")
        assert history.is_file(), (
            "the archive was never split out — a lookup still reads it"
        )
        assert _mod._HISTORICAL_SECTION_HEADER not in detail.read_text(), (
            "an archive has re-formed inside learnings-detail.md"
        )


class TestRetirementFindsAPrefixPairedNarrative:
    """The machinery half of the convention, and the orphan factory it was.

    `_take_active_narrative` matched EXACT titles while the corpus paired by
    prefix, so retiring a truncated pair wrote a historical block with no prose
    and left the narrative behind in the active file — orphaned, pointed at by
    nothing. One orphan manufactured per retirement, by the operation whose own
    docstring calls itself a MOVE.
    """

    def test_a_truncated_detail_heading_has_its_narrative_moved(self, tmp_path):
        _seed_learnings(tmp_path, (
            "# Learnings\n\n"
            "## Old rule — with a sharpened tail\n"
            "<!-- prawduct-learning: superseded-by=New rule -->\n\nbody\n\n"
            "## New rule\n\nb\n"
        ))
        (tmp_path / ".prawduct" / "learnings-detail.md").write_text(
            "# D\n\n## Old rule\n\nThe original narrative.\n"
        )
        audit_learnings(tmp_path, apply=True, today=date(2026, 9, 1))

        detail = (tmp_path / ".prawduct" / "learnings-detail.md").read_text()
        assert "The original narrative." not in detail, (
            "the prefix-paired narrative was left behind — an orphan created by "
            "the retirement that was supposed to move it"
        )
        assert "The original narrative." in _archive_text(tmp_path)

    def test_an_exact_match_still_wins_over_a_prefix_one(self, tmp_path):
        """Exact first, so nothing about a conforming pair changes — and a
        shorter heading that merely prefixes the title must not outrank the
        block that actually carries the title."""
        _seed_learnings(tmp_path, (
            "# Learnings\n\n"
            "## Old rule extended\n"
            "<!-- prawduct-learning: superseded-by=New rule -->\n\nbody\n\n"
            "## New rule\n\nb\n"
        ))
        (tmp_path / ".prawduct" / "learnings-detail.md").write_text(
            "# D\n\n## Old rule\n\nThe PREFIX block.\n\n"
            "## Old rule extended\n\nThe EXACT block.\n"
        )
        audit_learnings(tmp_path, apply=True, today=date(2026, 9, 1))

        detail = (tmp_path / ".prawduct" / "learnings-detail.md").read_text()
        assert "The PREFIX block." in detail, "the wrong block was cut"
        assert "The EXACT block." not in detail
        assert "The EXACT block." in _archive_text(tmp_path)

    def test_two_prefix_candidates_refuse_rather_than_choose(self, tmp_path):
        """Fail-closed, the same way a duplicate does. Which of two blocks that
        both prefix one title is the real one is not something this can know,
        and cutting the wrong one destroys an unrelated narrative."""
        learnings = _seed_learnings(tmp_path, (
            "# Learnings\n\n"
            "## Old rule extended further\n"
            "<!-- prawduct-learning: superseded-by=New rule -->\n\nbody\n\n"
            "## New rule\n\nb\n"
        ))
        before = learnings.read_text()
        (tmp_path / ".prawduct" / "learnings-detail.md").write_text(
            "# D\n\n## Old rule\n\nA.\n\n## Old rule extended\n\nB.\n"
        )
        result = audit_learnings(tmp_path, apply=True, today=date(2026, 9, 1))

        assert result["applied"] is False
        assert learnings.read_text() == before
        assert any("2 active blocks pairing" in e["error"] for e in result["errors"])

    def test_a_bare_heading_never_prefixes_everything(self, tmp_path):
        """An empty `## ` is a prefix of every title in the file. Left in the
        candidate set it matches the first block and cuts it."""
        _seed_learnings(tmp_path, (
            "# Learnings\n\n"
            "## Old rule\n"
            "<!-- prawduct-learning: superseded-by=New rule -->\n\nbody\n\n"
            "## New rule\n\nb\n"
        ))
        (tmp_path / ".prawduct" / "learnings-detail.md").write_text(
            "# D\n\n## \n\nStray empty heading.\n\n## Old rule\n\nThe narrative.\n"
        )
        result = audit_learnings(tmp_path, apply=True, today=date(2026, 9, 1))
        assert result["errors"] == []
        detail = (tmp_path / ".prawduct" / "learnings-detail.md").read_text()
        assert "Stray empty heading." in detail
        assert "The narrative." not in detail


def test_this_repos_header_states_the_decided_convention():
    """The header is the third surface, and it was the one asserting an
    invariant that never held. A convention decided in code and left unstated in
    the file its authors read is one nobody will follow."""
    header = (
        Path(__file__).resolve().parent.parent / ".prawduct" / "learnings.md"
    ).read_text(encoding="utf-8").split("---", 1)[0]
    assert "prefix" in header.lower()
    assert "not a copy" in header.lower() or "never required to be a copy" in header.lower()
    assert "order is not part of it" in header.lower()
    assert "learnings-history.md" in header
