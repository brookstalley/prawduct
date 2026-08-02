"""The descent-obligation detector and its offered repair (#351).

``/prawduct:learnings`` tells every product's reader to apply the obligation marked
``prawduct:descent-obligation`` in that product's own ``learnings.md``. Only
``init_product``'s starter corpus ever wrote that marker, and only when the file did
not already exist — so the whole already-onboarded fleet holds a pointer at nothing.

**Everything here runs against a fixture, never against this repo.** This repo has
the marker, correctly placed, which is exactly why the defect shipped: a check
exercised only here is green for the one repo that never needed it. The framework's
own state stands in for the propagated contract only if you never look at anything
else, and this file is the "anything else".
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from lib import learnings_obligation as lo

ROOT = Path(__file__).resolve().parent.parent / "plugin"
HOOK = ROOT / "bin" / "prawduct-hook"

MARKER = lo.MARKER

_PREAMBLE = (
    "# Learnings\n\n"
    "Accumulated wisdom from building this product. Entries use "
    '"When X, do Y because Z" format.\n'
)
_RULES = (
    "\n## Always pin the timezone\n\n"
    "When storing a timestamp, store it in UTC because local time is ambiguous.\n\n"
    "## Never swallow an exception\n\n"
    "When catching, name the type because a bare catch hides the next bug.\n"
)


def _product(tmp_path: Path, learnings: str | None) -> Path:
    """A product-shaped repo: `.prawduct/` with a learnings corpus (or none)."""
    (tmp_path / ".prawduct").mkdir(parents=True, exist_ok=True)
    if learnings is not None:
        (tmp_path / lo.LEARNINGS_REL).write_text(learnings, encoding="utf-8")
    return tmp_path


def _marker_line(text: str) -> int | None:
    return next((i for i, ln in enumerate(text.splitlines()) if MARKER in ln), None)


def _first_rule_line(text: str) -> int | None:
    return next((i for i, ln in enumerate(text.splitlines()) if ln.startswith("## ")), None)


# ---------------------------------------------------------------------------
# check — the four answers that are not "ok"
# ---------------------------------------------------------------------------


class TestCheck:
    def test_a_product_corpus_without_the_marker_is_missing(self, tmp_path):
        _product(tmp_path, _PREAMBLE + _RULES)
        result = lo.check(tmp_path)
        assert result["status"] == lo.STATUS_MISSING
        assert result["marker_lines"] == []
        assert MARKER in result["detail"]

    def test_the_marker_above_the_first_rule_is_ok(self, tmp_path):
        _product(tmp_path, _PREAMBLE + "\n" + lo.OBLIGATION_BLOCK + _RULES)
        result = lo.check(tmp_path)
        assert result["status"] == lo.STATUS_OK
        assert result["marker_lines"] and result["first_rule_line"]
        assert result["marker_lines"][0] < result["first_rule_line"]

    def test_an_append_to_end_insertion_fails_the_position_check(self, tmp_path):
        """Position is the other half of presence, not a refinement of it.

        A repair that appends the block to the end of the file satisfies every
        presence check and is still wrong: the reader meets the obligation after
        the rules it governs. This is the variant the criterion names, and without
        it the position assertion below could pass on a check that only looks for
        the string anywhere.
        """
        _product(tmp_path, _PREAMBLE + _RULES + "\n" + lo.OBLIGATION_BLOCK)
        result = lo.check(tmp_path)
        assert result["status"] == lo.STATUS_MISPLACED
        assert "below the first rule" in result["detail"]

    def test_a_second_copy_below_the_rules_is_misplaced_even_beside_a_good_one(self, tmp_path):
        # One correctly-placed marker does not excuse a second home for the same
        # statement further down — the whole reason the skill points rather than copies.
        _product(tmp_path, _PREAMBLE + "\n" + lo.OBLIGATION_BLOCK + _RULES + "\n" + lo.OBLIGATION_BLOCK)
        assert lo.check(tmp_path)["status"] == lo.STATUS_MISPLACED

    def test_no_learnings_file_is_absent_not_missing(self, tmp_path):
        _product(tmp_path, None)
        result = lo.check(tmp_path)
        assert result["status"] == lo.STATUS_ABSENT
        assert "Health Check #5" in result["detail"]

    def test_undecodable_bytes_report_rather_than_guess(self, tmp_path):
        _product(tmp_path, "")
        (tmp_path / lo.LEARNINGS_REL).write_bytes(b"# Learnings\n\xff\xfe not utf-8\n")
        assert lo.check(tmp_path)["status"] == lo.STATUS_UNREADABLE

    def test_a_corpus_with_no_rules_yet_still_grades(self, tmp_path):
        _product(tmp_path, _PREAMBLE)
        result = lo.check(tmp_path)
        assert result["status"] == lo.STATUS_MISSING
        assert result["first_rule_line"] is None


# ---------------------------------------------------------------------------
# repair — insert-only, above the first rule, dry by default
# ---------------------------------------------------------------------------


class TestRepair:
    def test_the_repair_inserts_above_the_first_rule(self, tmp_path):
        _product(tmp_path, _PREAMBLE + _RULES)
        result = lo.repair(tmp_path, apply=True)
        assert result["applied"] is True

        text = (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8")
        marker_at, first_rule = _marker_line(text), _first_rule_line(text)
        assert marker_at is not None and first_rule is not None
        assert marker_at < first_rule
        assert lo.check(tmp_path)["status"] == lo.STATUS_OK

    def test_the_dry_run_writes_nothing_and_names_what_it_would_write(self, tmp_path):
        _product(tmp_path, _PREAMBLE + _RULES)
        before = (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8")
        result = lo.repair(tmp_path)
        assert result["applied"] is False
        assert result["repairable"] is True
        assert (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8") == before
        # The confirmation seam: the exact text, at the exact line.
        assert MARKER in result["insert_text"]
        assert result["insert_before_line"] == (_first_rule_line(before) or 0) + 1

    def test_the_repair_never_loses_an_authored_line(self, tmp_path):
        # Insert-only is the constraint that makes editing a product-authored file
        # a bounded act. Every original line survives, in order.
        original = _PREAMBLE + _RULES
        _product(tmp_path, original)
        lo.repair(tmp_path, apply=True)
        after = (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8").splitlines()

        cursor = iter(after)
        for line in original.splitlines():
            assert any(candidate == line for candidate in cursor), f"lost line: {line!r}"

    def test_repairing_twice_is_an_idempotent_no_op(self, tmp_path):
        _product(tmp_path, _PREAMBLE + _RULES)
        lo.repair(tmp_path, apply=True)
        once = (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8")
        second = lo.repair(tmp_path, apply=True)
        assert second["applied"] is False
        assert second["status"] == lo.STATUS_OK
        assert (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8") == once

    def test_a_misplaced_marker_is_declined_not_moved_and_not_duplicated(self, tmp_path):
        before = _PREAMBLE + _RULES + "\n" + lo.OBLIGATION_BLOCK
        _product(tmp_path, before)
        result = lo.repair(tmp_path, apply=True)
        assert result["repairable"] is False
        assert result["applied"] is False
        assert result["status"] == lo.STATUS_MISPLACED
        assert (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8") == before

    @pytest.mark.parametrize("corpus", [None, "unreadable"])
    def test_absent_and_unreadable_are_declined(self, tmp_path, corpus):
        _product(tmp_path, None if corpus is None else "")
        if corpus == "unreadable":
            (tmp_path / lo.LEARNINGS_REL).write_bytes(b"\xff\xfe")
        result = lo.repair(tmp_path, apply=True)
        assert result["repairable"] is False and result["applied"] is False

    def test_a_ruleless_corpus_gets_the_block_at_the_end(self, tmp_path):
        _product(tmp_path, _PREAMBLE)
        lo.repair(tmp_path, apply=True)
        assert lo.check(tmp_path)["status"] == lo.STATUS_OK

    def test_the_block_is_not_welded_to_its_neighbours(self, tmp_path):
        # Markdown collapses adjacent lines into one paragraph; a block run into the
        # preceding sentence stops introducing anything.
        _product(tmp_path, _PREAMBLE + _RULES)
        lo.repair(tmp_path, apply=True)
        lines = (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8").splitlines()
        marker_at = _marker_line("\n".join(lines))
        assert lines[marker_at - 1].strip() == ""
        assert lines[_first_rule_line("\n".join(lines)) - 1].strip() == ""


# ---------------------------------------------------------------------------
# One home for the obligation — the scaffold and the repair plant the same thing
# ---------------------------------------------------------------------------


def test_scaffold_and_repair_write_the_identical_block(tmp_path):
    """The defect one level up.

    If the starter corpus and the repair each carried their own copy, a reworded
    obligation would reach newly-onboarded products and skip repaired ones — the
    fleet would then hold two statements under one marker, which is worse than the
    hole this repair fills.
    """
    from lib import init_product  # noqa: PLC0415

    assert lo.OBLIGATION_BLOCK in init_product._LEARNINGS_STARTER

    _product(tmp_path, _PREAMBLE + _RULES)
    lo.repair(tmp_path, apply=True)
    repaired = (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8")
    assert lo.OBLIGATION_BLOCK in repaired


# ---------------------------------------------------------------------------
# The command surface the doctor skill actually calls
# ---------------------------------------------------------------------------


def _run(project_dir: Path, *args: str) -> subprocess.CompletedProcess:
    home = project_dir.parent / "_home"
    home.mkdir(exist_ok=True)
    env = {
        "HOME": str(home),
        "CLAUDE_PLUGIN_ROOT": str(ROOT),
        "CLAUDE_PROJECT_DIR": str(project_dir),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    return subprocess.run(
        ["python3", str(HOOK), "learnings-obligation", *args],
        capture_output=True, text=True, env=env, timeout=30,
    )


class TestCommand:
    def test_dry_run_reports_the_finding_and_exits_zero(self, tmp_path):
        # An advisory report: a finding is not a failure state.
        _product(tmp_path, _PREAMBLE + _RULES)
        before = (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8")
        result = _run(tmp_path, "--json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["status"] == lo.STATUS_MISSING
        assert data["applied"] is False
        assert (tmp_path / lo.LEARNINGS_REL).read_text(encoding="utf-8") == before

    def test_the_human_dry_run_shows_the_text_it_would_insert(self, tmp_path):
        # `--json`-only tests never exercise the formatter, and this formatter IS
        # the informed confirmation the security model requires before an edit to a
        # file the framework did not author.
        _product(tmp_path, _PREAMBLE + _RULES)
        result = _run(tmp_path)
        assert result.returncode == 0
        assert "dry-run" in result.stdout
        assert MARKER in result.stdout
        assert "Would insert into .prawduct/learnings.md above line" in result.stdout

    def test_apply_writes_and_exits_zero(self, tmp_path):
        _product(tmp_path, _PREAMBLE + _RULES)
        result = _run(tmp_path, "--apply", "--json")
        assert result.returncode == 0
        assert json.loads(result.stdout)["applied"] is True
        assert lo.check(tmp_path)["status"] == lo.STATUS_OK

    def test_apply_on_a_healthy_corpus_is_a_zero_exit_no_op(self, tmp_path):
        _product(tmp_path, _PREAMBLE + "\n" + lo.OBLIGATION_BLOCK + _RULES)
        result = _run(tmp_path, "--apply", "--json")
        assert result.returncode == 0
        assert json.loads(result.stdout)["applied"] is False

    @pytest.mark.parametrize("corpus", [None, _PREAMBLE + _RULES + "\n" + lo.OBLIGATION_BLOCK])
    def test_apply_refuses_with_exit_one_when_it_cannot_write(self, tmp_path, corpus):
        # State-mutating writer: refused → 1, never a false success.
        _product(tmp_path, corpus)
        assert _run(tmp_path, "--apply").returncode == 1

    def test_an_unreadable_corpus_could_not_run(self, tmp_path):
        _product(tmp_path, "")
        (tmp_path / lo.LEARNINGS_REL).write_bytes(b"\xff\xfe")
        assert _run(tmp_path).returncode == 1

    def test_an_absent_corpus_is_a_finding_not_an_unrun_check(self, tmp_path):
        # Dry run distinguishes "graded, and the answer is bad" (0) from "could not
        # grade" (1). A missing learnings.md is the former — doctor #5's finding.
        _product(tmp_path, None)
        result = _run(tmp_path, "--json")
        assert result.returncode == 0
        assert json.loads(result.stdout)["status"] == lo.STATUS_ABSENT

    def test_an_unknown_argument_is_a_usage_error(self, tmp_path):
        _product(tmp_path, _PREAMBLE + _RULES)
        result = _run(tmp_path, str(tmp_path))
        assert result.returncode == 2
        assert "unknown argument" in result.stderr
