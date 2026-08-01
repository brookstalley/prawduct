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

        detail = (tmp_path / ".prawduct" / "learnings-detail.md").read_text()
        assert "## Narrow rule about fixtures" in detail
        assert "superseded by **General rule about evidence**" in detail
        assert "Retired 2026-07-31" in detail
        assert "Body of the narrow rule." in detail

        # The pointer sits directly under the title — a forwarding address
        # below the body is one the reader reads the whole entry to find.
        lines = detail.splitlines()
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

        detail = (tmp_path / ".prawduct" / "learnings-detail.md").read_text()
        assert "prawduct-learning:" not in detail
        assert "sentinel `tests/foo.py::test_bar` passes" in detail
        assert "Retired 2026-07-31" in detail

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

        detail = (tmp_path / ".prawduct" / "learnings-detail.md").read_text()
        assert "superseded by **Rule B**" in detail
        assert "superseded by **Rule C**" in detail
        assert "## Rule C" not in detail  # C is still active

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

        detail = (tmp_path / ".prawduct" / "learnings-detail.md").read_text()
        assert "superseded by **General rule**" in detail
        assert "prawduct-learning:" not in detail
        block = detail.split("## Terse rule", 1)[1]
        assert "\n\n\n" not in block, f"stray blank paragraph in the block: {block!r}"

    def test_retired_entries_land_inside_the_historical_section(self, tmp_path: Path):
        """"Under the historical section" was a docstring claim, not behavior:
        blocks were appended at EOF, which coincides with the section only while
        the section is last. Chunk 03's bulk collapse is the first `--apply`
        here, so a later top-level section in `learnings-detail.md` would leave
        every subsequent retirement filed under a heading it does not belong
        to — with the file reading as though it did."""
        _seed_learnings(tmp_path, self.CORPUS)
        detail = tmp_path / ".prawduct" / "learnings-detail.md"
        detail.write_text(
            "# Learnings — Full Detail\n\n"
            "## Historical (structurally enforced)\n\n"
            "Existing blurb.\n\n"
            "## Previously retired\n\nOld body.\n\n"
            "# Appendix\n\nUnrelated trailing section.\n"
        )
        audit_learnings(tmp_path, apply=True, today=date(2026, 7, 31))

        text = detail.read_text()
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
        detail = tmp_path / ".prawduct" / "learnings-detail.md"
        detail.write_text(f"# Learnings — Full Detail\n\n{header}\n\nBlurb.\n")

        audit_learnings(tmp_path, apply=True, today=date(2026, 7, 31))

        # Retired out of the active file...
        assert "Narrow rule about fixtures" not in learnings.read_text()
        # ...and INTO the detail file. Neither half may happen alone.
        text = detail.read_text()
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

        monkeypatch.setattr(_mod, "_detail_with_retirements", _boom)
        with pytest.raises(RuntimeError):
            audit_learnings(tmp_path, apply=True, today=date(2026, 7, 31))

        assert learnings.read_text() == before, (
            "learnings.md was rewritten before the detail file was composed — "
            "the retired entries are gone and were never filed"
        )
        assert not (tmp_path / ".prawduct" / "learnings-detail.md").exists()

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
        detail = (tmp_path / ".prawduct" / "learnings-detail.md").read_text()
        assert "## Narrow rule about fixtures" in detail, (
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

        detail = (tmp_path / ".prawduct" / "learnings-detail.md").read_text()
        # Both retired, each keeping ITS OWN reason and body.
        assert detail.count("## Same heading") == 2
        assert "sentinel `tests/foo.py::test_bar` passes" in detail
        assert "superseded by **General rule**" in detail
        first = detail.index("First body.")
        second = detail.index("Second body.")
        assert detail.index("sentinel `tests/foo.py::test_bar` passes") < first
        assert first < detail.index("superseded by **General rule**") < second

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
        res = self._run(tmp_path)
        assert res.returncode == 0, res.stderr
        assert "retire[blocked]: Enforced rule (sentinel=tests/nope.py::test_missing)" in res.stdout


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
