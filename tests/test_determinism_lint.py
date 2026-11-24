"""Tests for the test-scope and test-clock checks (``lib/determinism_lint``).

The detector finds, in what a change adds, the test shapes that widen every test's
dependency closure or stop a result repeating. What is pinned here:

* **Each rule fires on its shape and not on the neighbour it is worst at
  confusing it with**: a test-only import in a root conftest, ``TYPE_CHECKING``, a
  nested conftest, a two-name re-export, a single test reading the clock, a seeded
  generator.
* **Only introduced sites count.** A pre-existing site, a renamed file and an
  unrelated edit report nothing, so a product's existing debt never blocks an
  unrelated change.
* **The waiver needs a reason.** One with a reason drops the site; one without
  waives nothing.
* **Nothing is silently passed.** A test file in a language without rules and a
  Python file that will not parse each report ``unchecked``, at the severities
  record-lint's table gives them.

Real git repos with the suite's sterile git environment, mirroring
``test_retired_claims.py``. The review-layer delivery (dispatch, then consolidation
at each stage) is pinned in ``test_critic_consolidate.py``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_TESTS_DIR = Path(__file__).resolve().parent
_PLUGIN = _TESTS_DIR.parent / "plugin"
for _p in (str(_PLUGIN), str(_TESTS_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from lib import determinism_lint, record_lint  # noqa: E402

APP = {
    "myapp/__init__.py": "",
    "myapp/core.py": "X = 1\n",
    "myapp/db.py": "Y = 1\n",
    "myapp/web.py": "Z = 1\n",
    "tests/__init__.py": "",
    "tests/helpers.py": "def helper():\n    return 1\n",
}


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True, timeout=15,
    )
    assert proc.returncode == 0, f"git {args} failed: {proc.stderr}"
    return proc.stdout.strip()


def _write(repo: Path, files: "dict[str, str | None]") -> None:
    for rel, text in files.items():
        path = repo / rel
        if text is None:
            path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return _git(repo, "rev-parse", "HEAD^{tree}")


def _change(tmp_path: Path, base: "dict[str, str]", head: "dict[str, str | None]"):
    """A repo whose base holds ``APP`` plus ``base`` and whose head applies ``head``.
    Returns ``(repo, changed paths, base tree, head tree)``."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _write(repo, {**APP, **base})
    base_tree = _commit(repo, "base")
    _write(repo, head)
    head_tree = _commit(repo, "head")
    changed = _git(repo, "diff", "--name-only", base_tree, head_tree).splitlines()
    return repo, changed, base_tree, head_tree


def _run(tmp_path, base, head):
    repo, changed, base_tree, head_tree = _change(tmp_path, base, head)
    findings, unchecked, no_answer = determinism_lint.check(repo, changed, base_tree, head_tree)
    assert no_answer == set(), "every input was readable, so every check answered"
    return findings, unchecked


def _sites(findings) -> "list[tuple[str, str, int]]":
    return sorted((f["check"], f["path"], f["line"]) for f in findings)


# ---------------------------------------------------------------------------
# A root conftest's module-level first-party import
# ---------------------------------------------------------------------------


class TestRootConftestImport:
    def test_a_new_first_party_import_is_reported_at_its_line(self, tmp_path):
        findings, unchecked = _run(
            tmp_path,
            {"tests/conftest.py": "import pytest\n"},
            {"tests/conftest.py": "import pytest\nfrom myapp import core\n"},
        )
        assert _sites(findings) == [(determinism_lint.CONFTEST_CHECK, "tests/conftest.py", 2)]
        assert "`myapp`" in findings[0]["detail"]
        assert unchecked == []

    def test_test_only_and_third_party_imports_are_not(self, tmp_path):
        findings, _ = _run(
            tmp_path,
            {"tests/conftest.py": "\n"},
            {"tests/conftest.py": (
                "import pytest\nimport json\nfrom tests.helpers import helper\n"
                "from . import helpers\n"
            )},
        )
        assert findings == []

    def test_type_checking_is_exempt_and_a_module_level_try_is_not(self, tmp_path):
        findings, _ = _run(
            tmp_path,
            {"tests/conftest.py": "\n"},
            {"tests/conftest.py": (
                "from typing import TYPE_CHECKING\n"
                "if TYPE_CHECKING:\n    import myapp.db\n"
                "try:\n    import myapp.web\nexcept ImportError:\n    pass\n"
            )},
        )
        assert _sites(findings) == [(determinism_lint.CONFTEST_CHECK, "tests/conftest.py", 5)]

    def test_an_import_inside_a_fixture_is_not(self, tmp_path):
        findings, _ = _run(
            tmp_path,
            {"tests/conftest.py": "import pytest\n"},
            {"tests/conftest.py": (
                "import pytest\n\n@pytest.fixture\ndef app():\n"
                "    import myapp.core\n    return myapp.core\n"
            )},
        )
        assert findings == []

    def test_a_nested_conftest_is_not_the_root(self, tmp_path):
        """The root conftest loads for every test; a nested one only for its
        directory, so only the root's import is this check's business."""
        findings, _ = _run(
            tmp_path,
            {"conftest.py": "\n", "tests/conftest.py": "\n"},
            {"tests/conftest.py": "import myapp\n", "conftest.py": "import myapp.core\n"},
        )
        assert _sites(findings) == [(determinism_lint.CONFTEST_CHECK, "conftest.py", 1)]

    def test_a_monorepo_subproject_is_first_party(self, tmp_path):
        """A directory holding a `pyproject.toml` is a project root of its own: arrt
        keeps its package at `arrt/src/arrt`, which the repo root alone never sees."""
        repo, changed, base_tree, head_tree = _change(
            tmp_path,
            {
                "svc/pyproject.toml": "[project]\nname = 'svc'\n",
                "svc/src/svc/__init__.py": "",
                "svc/src/svc/a.py": "", "svc/src/svc/b.py": "", "svc/src/svc/c.py": "",
                "svc/tests/conftest.py": "\n",
            },
            {
                "svc/tests/conftest.py": "import svc.a\n",
                "svc/src/svc/__init__.py": "from svc import a, b, c\n",
            },
        )
        findings, _, _ = determinism_lint.check(repo, changed, base_tree, head_tree)
        assert _sites(findings) == [
            (determinism_lint.CONFTEST_CHECK, "svc/tests/conftest.py", 1),
            (determinism_lint.INIT_CHECK, "svc/src/svc/__init__.py", 1),
        ]

    def test_a_src_layout_package_is_first_party(self, tmp_path):
        repo, changed, base_tree, head_tree = _change(
            tmp_path,
            {"src/other/__init__.py": "", "tests/conftest.py": "\n"},
            {"tests/conftest.py": "import other\n"},
        )
        findings, _, _ = determinism_lint.check(repo, changed, base_tree, head_tree)
        assert _sites(findings) == [(determinism_lint.CONFTEST_CHECK, "tests/conftest.py", 1)]


# ---------------------------------------------------------------------------
# Introduced, not present
# ---------------------------------------------------------------------------


class TestOnlyIntroducedSitesCount:
    def test_a_pre_existing_import_reports_nothing_when_its_file_changes(self, tmp_path):
        findings, _ = _run(
            tmp_path,
            {"tests/conftest.py": "import myapp\n"},
            {"tests/conftest.py": "import myapp\nimport pytest\n"},
        )
        assert findings == []

    def test_a_second_import_of_a_new_module_is_reported(self, tmp_path):
        """The control for the case above: the key is the imported module, so a
        site the base did not carry is new even beside one it did."""
        findings, _ = _run(
            tmp_path,
            {"tests/conftest.py": "import myapp\n"},
            {"tests/conftest.py": "import myapp\nimport myapp.db\n"},
        )
        assert _sites(findings) == [(determinism_lint.CONFTEST_CHECK, "tests/conftest.py", 2)]

    def test_a_renamed_conftest_introduces_nothing(self, tmp_path):
        body = "import pytest\nimport myapp\n\n" + "".join(
            f"def helper_{n}():\n    return {n}\n\n" for n in range(10)
        )
        findings, _ = _run(
            tmp_path,
            {"tests/conftest.py": body},
            {"tests/conftest.py": None, "testing/conftest.py": body},
        )
        assert findings == []

    def test_a_change_touching_no_test_file_reads_nothing(self, tmp_path):
        repo, changed, base_tree, head_tree = _change(
            tmp_path, {"tests/conftest.py": "import myapp\n"}, {"myapp/core.py": "X = 2\n"},
        )
        assert changed == ["myapp/core.py"]
        assert determinism_lint.check(repo, changed, base_tree, head_tree) == ([], [], set())


# ---------------------------------------------------------------------------
# Waivers
# ---------------------------------------------------------------------------


class TestTheWaiverNeedsAReason:
    def test_a_waiver_on_the_line_or_above_drops_the_site(self, tmp_path):
        findings, _ = _run(
            tmp_path,
            {"tests/conftest.py": "\n"},
            {"tests/conftest.py": (
                "import myapp  # prawduct:allow prawduct/test-scope -- pytest plugin registration\n"
                "# prawduct:allow prawduct/test-scope -- registers the db fixtures pytest loads\n"
                "import myapp.db\n"
            )},
        )
        assert findings == []

    def test_a_reasonless_or_foreign_waiver_drops_nothing(self, tmp_path):
        findings, _ = _run(
            tmp_path,
            {"tests/conftest.py": "\n"},
            {"tests/conftest.py": (
                "import myapp  # prawduct:allow prawduct/test-scope\n"
                "import myapp.db  # prawduct:allow prawduct/broad-except -- wrong rule\n"
            )},
        )
        assert _sites(findings) == [
            (determinism_lint.CONFTEST_CHECK, "tests/conftest.py", 1),
            (determinism_lint.CONFTEST_CHECK, "tests/conftest.py", 2),
        ]


# ---------------------------------------------------------------------------
# Autouse fixtures and import-everything packages
# ---------------------------------------------------------------------------


class TestAutouseAndInit:
    def test_an_importing_autouse_fixture_is_reported_and_an_opt_in_one_is_not(self, tmp_path):
        findings, _ = _run(
            tmp_path,
            {"tests/test_a.py": "import pytest\n"},
            {"tests/test_a.py": (
                "import pytest\n\n"
                "@pytest.fixture(autouse=True)\ndef registry():\n"
                "    from myapp import core\n    yield core\n\n"
                "@pytest.fixture\ndef opt_in():\n    import myapp.db\n    return 1\n"
            )},
        )
        assert _sites(findings) == [(determinism_lint.AUTOUSE_CHECK, "tests/test_a.py", 5)]
        assert "`registry`" in findings[0]["detail"]

    def test_an_init_importing_every_submodule_is_reported(self, tmp_path):
        findings, _ = _run(
            tmp_path,
            {},
            {"myapp/__init__.py": "from . import core, db\nfrom .web import Z\n"},
        )
        assert _sites(findings) == [(determinism_lint.INIT_CHECK, "myapp/__init__.py", 1)]

    def test_an_init_re_exporting_some_submodules_is_not(self, tmp_path):
        findings, _ = _run(
            tmp_path, {}, {"myapp/__init__.py": "from .core import X\nfrom .db import Y\n"},
        )
        assert findings == []

    def test_a_package_with_two_submodules_is_too_small_to_judge(self, tmp_path):
        findings, _ = _run(
            tmp_path,
            {"small/__init__.py": "", "small/a.py": "", "small/b.py": ""},
            {"small/__init__.py": "from . import a, b\n"},
        )
        assert findings == []

    def test_an_init_already_importing_everything_introduces_nothing(self, tmp_path):
        findings, _ = _run(
            tmp_path,
            {"myapp/__init__.py": "from . import core, db, web\n"},
            {"myapp/__init__.py": "from . import core, db, web\n__all__ = ['core']\n"},
        )
        assert findings == []


# ---------------------------------------------------------------------------
# Real clock and randomness
# ---------------------------------------------------------------------------


class TestClockAndRandomness:
    def test_a_fake_reading_the_real_clock_is_reported(self, tmp_path):
        findings, _ = _run(
            tmp_path,
            {"tests/fakes.py": "class FakeKv:\n    def __init__(self):\n        self.t = 0\n"},
            {"tests/fakes.py": (
                "from datetime import datetime\n\n"
                "class FakeKv:\n    def __init__(self):\n        self.t = datetime.now()\n"
            )},
        )
        assert _sites(findings) == [(determinism_lint.CLOCK_FAKE_CHECK, "tests/fakes.py", 5)]
        assert "`FakeKv.__init__`" in findings[0]["detail"]

    def test_a_single_test_reading_the_clock_is_not_a_shared_helper(self, tmp_path):
        findings, _ = _run(
            tmp_path,
            {},
            {"tests/test_t.py": "import time\n\ndef test_t():\n    assert time.time() > 0\n"},
        )
        assert findings == []

    def test_import_time_reads_are_reported_wherever_they_run(self, tmp_path):
        findings, _ = _run(
            tmp_path,
            {},
            {"tests/test_t.py": (
                "import datetime, uuid, os, pytest\n"
                "NOW = datetime.datetime.now()\n"
                "@pytest.mark.parametrize('k', [uuid.uuid4()])\n"
                "def test_k(k, salt=os.urandom(4)):\n"
                "    assert uuid.uuid4() != k\n"
            )},
        )
        assert _sites(findings) == [
            (determinism_lint.CLOCK_IMPORT_CHECK, "tests/test_t.py", 2),
            (determinism_lint.CLOCK_IMPORT_CHECK, "tests/test_t.py", 3),
            (determinism_lint.CLOCK_IMPORT_CHECK, "tests/test_t.py", 4),
        ]

    def test_an_interval_clock_for_a_deadline_is_not_an_ambient_read(self, tmp_path):
        """`time.monotonic` and `time.perf_counter` time a wait or a duration; no
        result carries their value. A polling helper is the population this rule
        would otherwise flood, so it must stay silent — and `time.time` beside it
        must not."""
        findings, _ = _run(
            tmp_path,
            {},
            {"tests/helpers.py": (
                "import time\n\n"
                "def wait_for(cond, timeout=5):\n"
                "    deadline = time.monotonic() + timeout\n"
                "    started = time.perf_counter()\n"
                "    while time.monotonic() < deadline:\n"
                "        if cond():\n"
                "            return time.perf_counter() - started\n"
                "    return time.time()\n"
            )},
        )
        assert [(f["check"], f["line"]) for f in findings] == [(determinism_lint.CLOCK_FAKE_CHECK, 9)]

    def test_a_seeded_generator_is_deterministic_and_an_unseeded_one_is_not(self, tmp_path):
        findings, _ = _run(
            tmp_path,
            {},
            {"tests/helpers.py": (
                "import random\n\n"
                "def seeded():\n    return random.Random(42).random()\n\n"
                "def unseeded():\n    return random.Random()\n"
            )},
        )
        # `random.Random(42).random()` is a method on a seeded instance, not the
        # module-level generator, so only the unseeded constructor is a site.
        assert _sites(findings) == [(determinism_lint.CLOCK_FAKE_CHECK, "tests/helpers.py", 7)]


# ---------------------------------------------------------------------------
# Nothing silently passed
# ---------------------------------------------------------------------------


class TestNothingIsSilentlyPassed:
    def test_a_test_file_in_a_language_without_rules_is_unchecked_as_an_observation(self, tmp_path):
        findings, unchecked = _run(
            tmp_path, {}, {"ios/Tests/AppTests/FooTests.swift": "import XCTest\n"},
        )
        assert findings == []
        [reason] = unchecked
        assert reason.startswith(f"{determinism_lint.UNRULED} unchecked on ios/Tests/AppTests/FooTests.swift")
        [graded] = record_lint.graded({"findings": [], "unchecked": unchecked})
        assert graded["severity"] is None

    def test_an_unparseable_test_file_is_unchecked_one_step_below_blocking(self, tmp_path):
        findings, unchecked = _run(
            tmp_path, {}, {"tests/conftest.py": "import myapp\ndef broken(:\n"},
        )
        assert findings == []
        [reason] = unchecked
        assert "tests/conftest.py" in reason
        [graded] = record_lint.graded({"findings": [], "unchecked": unchecked})
        assert (graded["check"], graded["severity"]) == (determinism_lint.CONFTEST_CHECK, "warning")

    def test_an_unreadable_tree_answers_nothing_rather_than_clean(self, tmp_path):
        repo, changed, base_tree, _head = _change(
            tmp_path, {}, {"tests/conftest.py": "import myapp\n"},
        )
        findings, unchecked, no_answer = determinism_lint.check(
            repo, changed, base_tree, "0" * 40
        )
        assert findings == []
        assert no_answer == set(determinism_lint.CHECKS)
        assert unchecked and unchecked[0].startswith(f"{determinism_lint.CONFTEST_CHECK} unchecked")


# ---------------------------------------------------------------------------
# Record-lint carries it
# ---------------------------------------------------------------------------


class TestRecordLintCarriesIt:
    def test_the_arm_runs_over_all_changed_paths_and_rates_at_the_table(self, tmp_path):
        repo, changed, base_tree, head_tree = _change(
            tmp_path,
            {"tests/conftest.py": "\n", "tests/fakes.py": "class F:\n    pass\n"},
            {"tests/conftest.py": "import myapp\n",
             "tests/fakes.py": "import time\nclass F:\n    def now(self):\n        return time.time()\n"},
        )
        result = record_lint.lint_records(
            repo, repo / ".prawduct", changed, base_tree, head_tree
        )
        rated = {(g["check"], g["severity"]) for g in record_lint.graded(result)}
        assert (determinism_lint.CONFTEST_CHECK, "blocking") in rated
        assert (determinism_lint.CLOCK_FAKE_CHECK, "warning") in rated
        assert result["counts"][determinism_lint.CONFTEST_CHECK] == 1
        assert result["counts"][determinism_lint.INIT_CHECK] == 0

    def test_the_blocking_checks_are_not_in_the_inner_blocking_set(self):
        """Owner ruling 2026-11-24: blocking at the merge boundary. The inner
        stage reports them as observations."""
        for check in (determinism_lint.CONFTEST_CHECK, determinism_lint.AUTOUSE_CHECK, determinism_lint.INIT_CHECK):
            assert record_lint.SEVERITY[check] == "blocking"
            assert check not in record_lint.INNER_BLOCKING
        for check in (determinism_lint.CLOCK_FAKE_CHECK, determinism_lint.CLOCK_IMPORT_CHECK):
            assert record_lint.SEVERITY[check] == "warning"


# ---------------------------------------------------------------------------
# Edges the review surfaced
# ---------------------------------------------------------------------------


class TestReviewedEdges:
    def test_a_new_read_does_not_hide_behind_an_old_waived_one(self, tmp_path):
        """Ordinal keys pair the n-th read with the n-th; a waived base read must
        leave the matching, or a new unwaived read above it pairs with it and
        vanishes."""
        waived = "A = time.time()  # prawduct:allow prawduct/test-scope -- the clock is the subject\n"
        findings, _ = _run(
            tmp_path,
            {"tests/test_t.py": "import time\n" + waived},
            {"tests/test_t.py": "import time\nB = time.time()\n" + waived},
        )
        assert _sites(findings) == [(determinism_lint.CLOCK_IMPORT_CHECK, "tests/test_t.py", 2)]

    def test_a_read_in_a_nested_function_is_attributed_once(self, tmp_path):
        findings, _ = _run(
            tmp_path,
            {},
            {"tests/helpers.py": (
                "import time\n\ndef outer():\n    def inner():\n        return time.time()\n"
                "    return inner\n"
            )},
        )
        assert [(f["check"], f["line"]) for f in findings] == [
            (determinism_lint.CLOCK_FAKE_CHECK, 5),
        ]
        assert "`outer.inner`" in findings[0]["detail"]

    def test_aliased_clock_imports_resolve(self, tmp_path):
        findings, _ = _run(
            tmp_path,
            {},
            {"tests/helpers.py": (
                "import time as t\nfrom uuid import uuid4 as fresh\n\n"
                "def stamp():\n    return t.time(), fresh()\n"
            )},
        )
        assert [f["line"] for f in findings] == [5, 5]
        assert {d for f in findings for d in ("time.time", "uuid.uuid4") if d in f["detail"]} == {
            "time.time", "uuid.uuid4",
        }

    def test_an_import_in_a_module_level_with_block_counts(self, tmp_path):
        findings, _ = _run(
            tmp_path,
            {"tests/conftest.py": "\n"},
            {"tests/conftest.py": (
                "import warnings\nwith warnings.catch_warnings():\n    import myapp\n"
            )},
        )
        assert _sites(findings) == [(determinism_lint.CONFTEST_CHECK, "tests/conftest.py", 3)]

    def test_an_unparseable_base_makes_every_head_site_new(self, tmp_path):
        findings, _ = _run(
            tmp_path,
            {"tests/conftest.py": "import myapp\ndef broken(:\n"},
            {"tests/conftest.py": "import myapp\n"},
        )
        assert _sites(findings) == [(determinism_lint.CONFTEST_CHECK, "tests/conftest.py", 1)]

    def test_an_unreadable_blob_answers_nothing_rather_than_clean(self, tmp_path, monkeypatch):
        repo, changed, base_tree, head_tree = _change(
            tmp_path, {}, {"tests/conftest.py": "import myapp\n"},
        )
        monkeypatch.setattr(determinism_lint, "_blobs", lambda *a, **k: None)
        findings, unchecked, no_answer = determinism_lint.check(
            repo, changed, base_tree, head_tree
        )
        assert findings == []
        assert no_answer == set(determinism_lint.CHECKS)
        assert unchecked[0].startswith(f"{determinism_lint.CONFTEST_CHECK} unchecked")

    def test_co_located_tests_in_other_languages_are_unchecked_and_lookalikes_are_not(self, tmp_path):
        findings, unchecked = _run(
            tmp_path,
            {},
            {
                "pkg/store_test.go": "package pkg\n",
                "web/cart.test.ts": "test('x', () => {})\n",
                "App/MyApp.Tests/CartTests.cs": "class CartTests {}\n",
                "web/latest.js": "export const x = 1\n",
                "pkg/contest.go": "package pkg\n",
            },
        )
        assert findings == []
        [reason] = unchecked
        named = reason.split(" unchecked on ", 1)[1].split(" — ", 1)[0].split(", ")
        assert sorted(named) == [
            "App/MyApp.Tests/CartTests.cs", "pkg/store_test.go", "web/cart.test.ts",
        ]

    def test_the_detector_module_is_not_itself_a_test_file(self):
        assert not determinism_lint.is_test_path("plugin/lib/determinism_lint.py")
        assert determinism_lint.is_test_path("pkg/foo_test.py")


# ---------------------------------------------------------------------------
# The whole-tree listing
# ---------------------------------------------------------------------------


class TestScanTree:
    def test_existing_sites_are_listed_by_blast_radius_and_waived_ones_are_not(self, tmp_path):
        repo, _changed, _base, _head = _change(
            tmp_path,
            {
                # Sorts BEFORE the conftest by path, so only the rank can put it second.
                "tests/a_fakes.py": "import time\nclass F:\n    def now(self):\n        return time.time()\n",
                "tests/conftest.py": (
                    "import myapp\n"
                    "import myapp.db  # prawduct:allow prawduct/test-scope -- registers fixtures\n"
                ),
            },
            {},
        )
        result = determinism_lint.scan_tree(repo)
        assert [(s["check"], s["path"], s["line"]) for s in result["sites"]] == [
            (determinism_lint.CONFTEST_CHECK, "tests/conftest.py", 1),
            (determinism_lint.CLOCK_FAKE_CHECK, "tests/a_fakes.py", 4),
        ]
        assert result["scanned"] >= 4  # conftest, fakes, helpers, both __init__s

    def test_a_clean_tree_lists_nothing_over_a_scanned_set(self, tmp_path):
        repo, _changed, _base, _head = _change(tmp_path, {"tests/conftest.py": "import pytest\n"}, {})
        result = determinism_lint.scan_tree(repo)
        assert result["sites"] == []
        assert result["scanned"] > 0, "an empty listing must be a scan of something"
        assert result["unparsed"] == [] and result["unruled"] == []

    def test_an_unreadable_tree_is_none(self, tmp_path):
        repo, _changed, _base, _head = _change(tmp_path, {}, {})
        assert determinism_lint.scan_tree(repo, "0" * 40) is None


# ---------------------------------------------------------------------------
# The doctor's command
# ---------------------------------------------------------------------------


def _scan(repo: Path, *args: str):
    from _hook_inproc import run_hook  # noqa: PLC0415 — only the CLI tests need it

    return run_hook("determinism-scan", *args, cwd=repo,
                    env={"CLAUDE_PLUGIN_ROOT": str(_PLUGIN)})


class TestDeterminismScanCommand:
    def test_it_lists_the_sites_at_head_and_exits_zero(self, tmp_path):
        repo, _c, _b, _h = _change(
            tmp_path, {"tests/conftest.py": "import myapp\n"}, {},
        )
        result = _scan(repo)
        assert result.returncode == 0, result.stderr
        lines = result.stdout.splitlines()
        assert lines[0].startswith("determinism-scan: 1 site(s) and 0 tool-state finding(s) over ")
        assert lines[1].startswith(f"  {determinism_lint.CONFTEST_CHECK}  tests/conftest.py:1 — ")

    def test_json_carries_the_listing_and_its_scanned_count(self, tmp_path):
        import json

        repo, _c, _b, _h = _change(tmp_path, {"tests/conftest.py": "import pytest\n"}, {})
        result = _scan(repo, "--json")
        assert result.returncode == 0, result.stderr
        body = json.loads(result.stdout)
        assert body["status"] == "scanned"
        assert body["sites"] == [] and body["scanned"] > 0

    def test_an_unknown_argument_is_a_usage_error(self, tmp_path):
        repo, _c, _b, _h = _change(tmp_path, {}, {})
        result = _scan(repo, "--apply")
        assert result.returncode == 2
        assert "determinism-scan: unknown argument '--apply'" in result.stderr

    def test_a_repo_with_no_commit_is_unchecked(self, tmp_path):
        repo = tmp_path / "empty"
        repo.mkdir()
        _git(repo, "init", "-q")
        result = _scan(repo)
        assert result.returncode == 3
        assert "unchecked" in result.stdout


class TestHypothesisDatabase:
    def test_an_in_tree_example_database_is_reported(self, tmp_path):
        repo, _c, _b, _h = _change(
            tmp_path,
            {"tests/test_p.py": "from hypothesis import given\n"},
            {},
        )
        [item] = determinism_lint.scan_tree(repo)["tool_state"]
        assert item["path"] == "tests/test_p.py"
        assert "example database" in item["detail"]

    def test_following_the_remedy_clears_it(self, tmp_path):
        """The advice's effect, not its wording: point the database out of the
        checkout as the detail says, and the finding goes."""
        repo, _c, _b, _h = _change(
            tmp_path,
            {"tests/test_p.py": "from hypothesis import given\n"},
            {"tests/conftest.py": (
                "from hypothesis import settings\n"
                "settings.register_profile('ci', database=None)\n"
                "settings.load_profile('ci')\n"
            )},
        )
        assert determinism_lint.scan_tree(repo)["tool_state"] == []

    def test_a_suite_without_hypothesis_has_nothing_to_report(self, tmp_path):
        repo, _c, _b, _h = _change(tmp_path, {"tests/test_p.py": "import pytest\n"}, {})
        assert determinism_lint.scan_tree(repo)["tool_state"] == []
