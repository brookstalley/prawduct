"""Tests for `lib/audit_learnings_cmd.py` and the `bin/prawduct-hook audit-learnings` CLI.

Covers the F9 learnings lifecycle sentinel tracker: metadata parsing,
file segmentation, audit classification (promotion / retirement / stale /
error), and the `--apply` retirement file mutation. Sentinel subprocess
invocation is gated via ``run_sentinels=False`` so the test suite stays
hermetic and fast — a separate test exercises the real subprocess path
against a synthetic passing test fixture.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
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
        entry from learnings.md to learnings-detail.md under the historical
        section."""
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

        # learnings-detail.md was created with the historical section + the
        # retired entry body.
        detail_path = tmp_path / ".prawduct" / "learnings-detail.md"
        assert detail_path.is_file()
        detail_content = detail_path.read_text()
        assert "Historical (structurally enforced)" in detail_content
        assert "Retired rule" in detail_content
        assert "Body of retired rule." in detail_content

    def test_apply_true_appends_to_existing_detail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """When learnings-detail.md already has the historical section,
        append rather than re-creating the header."""
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

        detail_content = detail_path.read_text()
        # Header appears exactly once.
        assert detail_content.count("## Historical (structurally enforced)") == 1
        # Earlier and new retirements both present.
        assert "Earlier retired rule" in detail_content
        assert "Retired rule" in detail_content

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
        passed, excerpt = run_sentinel(
            tmp_path, "tests/test_synthetic.py::test_fails"
        )
        assert passed is False
        assert excerpt  # some diagnostic text returned

    def test_nonexistent_sentinel_returns_false(self, tmp_path: Path):
        """pytest exits non-zero when the requested node ID can't be
        collected. The audit must surface this as a failure, not raise."""
        (tmp_path / "tests").mkdir()
        passed, excerpt = run_sentinel(
            tmp_path, "tests/does_not_exist.py::nope"
        )
        assert passed is False


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
