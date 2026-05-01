"""Project-preferences enforcement: public functions in `tools/lib/` are tested.

Enforces the Coverage expectations preference in
`.prawduct/artifacts/project-preferences.md`: every public (non-underscore)
module-level function in `tools/lib/` must be referenced by at least one
test file.

**Detection (presence-only, intentionally narrow):** cross-file consistency
check via AST. Walks `tools/lib/*.py` to collect public function names, then
walks `tests/` and counts a function as "covered" if it appears in EITHER:
  - an `Attribute.attr` position (e.g., `_mod.compute_hash`) — captures the
    project's importlib-binding pattern
  - a `Name` in `Call.func` position (e.g., `compute_hash(file)`) — captures
    direct invocation after rebinding

This deliberately excludes bare `Name.id` reads (assignment LHS, parameter
names, etc.) to avoid false positives from local variable shadowing.

**Known limitations (this is a presence check, not a coverage proof):**
- For uncommon function names (`compute_block_hash`, `untrack_gitignored_files`),
  the check is essentially exact.
- For common names (`log`, `run`, `parse`), the check can match unrelated
  attribute access (e.g., `mock_logger.log(...)` would match a function `log`).
  Critic Goal 1 (test coverage) backstops semantic correctness — this test
  catches the egregious case (function with NO references at all) so Critic
  doesn't have to.
- Per the project's Enforcement guardrail: a green test that doesn't actually
  check the rule is worse than no test. Tightening detection further (e.g.,
  requiring imports to resolve to `tools.lib`) would require more invasive
  static analysis; if the heuristic above starts producing false negatives,
  demote this rule to Critic rather than continuing to patch.

**Not checked here** (lives in Critic):
- That the test class is named after the function (`TestFooBar` for `foo_bar`).
  The project preference is "class-based test grouping," satisfied by
  scenario-named classes (`TestHealthyRepo` testing `run_validate`) too.
- Adequacy of coverage (happy path + error cases + edge cases).

Underscore-prefixed functions (e.g., `_bootstrap_manifest`) are treated as
private by convention and excluded, even when re-exported.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LIB_DIR = REPO_ROOT / "tools" / "lib"
TESTS_DIR = REPO_ROOT / "tests"

# Exemptions: public functions exercised only transitively (called from a
# tested entry point, never imported by a test directly). Each entry must
# include a resolution path so the exemption doesn't become permanent.
# See backlog item "Audit public-function coverage exemptions" (2026-05-01).
EXEMPT_FROM_DIRECT_COVERAGE: dict[str, str] = {
    "log": (
        "Stdout-print helper used throughout tools/lib/ for user-facing "
        "command output. Output is observed indirectly via stdout assertions "
        "in many TestRun* classes. Resolution: rename to _log (it's not part "
        "of the public API consumers should call), or add a small direct test."
    ),
    "load_json": (
        "JSON-loading helper used pervasively in tools/lib/ (sync_cmd, "
        "migrate_cmd, validate_cmd). Exercised transitively via TestRunSync, "
        "TestRunMigrate, etc. Resolution: add direct unit tests, or accept "
        "transitive coverage and keep on the exemption list with this rationale."
    ),
    "strip_test_tracking": (
        "Migration helper called only from run_migrate. Exercised transitively "
        "via TestRunMigrate scenarios. Resolution: add direct test, or rename "
        "to _strip_test_tracking and remove from public API."
    ),
    "generate_sync_manifest": (
        "Manifest-generation helper called from run_migrate. Exercised "
        "transitively via TestRunMigrate bootstrap scenarios. Resolution: "
        "add direct test, or rename to _generate_sync_manifest."
    ),
}


def _public_functions_in_lib() -> dict[str, list[str]]:
    """Map public function name -> sorted list of defining files (relative paths)."""
    funcs: dict[str, list[str]] = {}
    for path in sorted(LIB_DIR.glob("*.py")):
        if path.name == "__init__.py":
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                rel = path.relative_to(REPO_ROOT).as_posix()
                funcs.setdefault(node.name, []).append(rel)
    for name in funcs:
        funcs[name].sort()
    return funcs


def _names_referenced_in_tests() -> set[str]:
    """Collect names that appear in test files in positions that suggest
    actual function usage: `Attribute.attr` (e.g., `_mod.compute_hash`) or
    `Name` in `Call.func` position (e.g., `compute_hash(file)`).

    Bare `Name` reads outside a Call.func position are excluded to avoid
    false positives from local variables that happen to share a function
    name (e.g., a local variable named `log` shadowing the `log` helper).
    """
    referenced: set[str] = set()
    for path in TESTS_DIR.rglob("test_*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                referenced.add(node.attr)
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                referenced.add(node.func.id)
    return referenced


class TestPublicFunctionCoverage:
    def test_every_public_lib_function_referenced_in_some_test(self):
        functions = _public_functions_in_lib()
        used = _names_referenced_in_tests()
        violations: list[str] = []
        for name, defining_files in functions.items():
            if name in EXEMPT_FROM_DIRECT_COVERAGE:
                continue
            if name not in used:
                violations.append(f"{', '.join(defining_files)}::{name}")
        assert not violations, (
            "Public functions in tools/lib/ with no test reference "
            "(no test file imports, calls, or references the name):\n  - "
            + "\n  - ".join(violations)
            + "\n\nIf the function is exercised only transitively, add it to "
            "EXEMPT_FROM_DIRECT_COVERAGE with a resolution path."
        )

    def test_exempt_functions_still_exist(self):
        # Self-guard: when an exempt function is renamed or removed, drop the
        # exemption rather than letting it silently no-op.
        functions = _public_functions_in_lib()
        stale: list[str] = []
        for name in EXEMPT_FROM_DIRECT_COVERAGE:
            if name not in functions:
                stale.append(name)
        assert not stale, (
            "EXEMPT_FROM_DIRECT_COVERAGE contains functions that no longer "
            "exist in tools/lib/ — remove these entries:\n  - "
            + "\n  - ".join(stale)
        )

    def test_lib_directory_has_public_functions(self):
        # If tools/lib/ has no public functions at all, the coverage test
        # silently passes — this guard ensures the test is doing real work.
        functions = _public_functions_in_lib()
        assert functions, (
            "No public functions found in tools/lib/ — either the directory "
            "moved or the detection logic is broken."
        )
