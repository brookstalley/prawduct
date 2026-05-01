"""Project-preferences enforcement: `from __future__ import annotations`.

Enforces the Imports preference in `.prawduct/artifacts/project-preferences.md`:
every implementation file in `tools/` and `tests/` must begin with
`from __future__ import annotations` (after the module docstring, if any).

Exceptions, by design:
- `__init__.py` files (typically re-export modules)
- `tests/conftest.py` (pytest discovery file, not implementation code)
- Files whose module docstring contains "Backward-compat shim" — these
  delegate to a primary entry point and re-export its namespace
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SHIM_MARKER = "Backward-compat shim"
EXPLICIT_EXCEPTIONS = {
    "tests/conftest.py",
}


def _python_files() -> list[Path]:
    files: list[Path] = []
    for root in ("tools", "tests"):
        for path in (REPO_ROOT / root).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            if path.name == "__init__.py":
                continue
            files.append(path)
    return sorted(files)


def _is_shim(tree: ast.Module) -> bool:
    docstring = ast.get_docstring(tree) or ""
    return SHIM_MARKER in docstring


def _first_non_docstring_statement(tree: ast.Module) -> ast.stmt | None:
    body = list(tree.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]
    return body[0] if body else None


def _imports_future_annotations(stmt: ast.stmt | None) -> bool:
    if not isinstance(stmt, ast.ImportFrom):
        return False
    if stmt.module != "__future__":
        return False
    return any(alias.name == "annotations" for alias in stmt.names)


class TestFutureAnnotations:
    def test_every_implementation_file_imports_future_annotations(self):
        violations: list[str] = []
        for path in _python_files():
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel in EXPLICIT_EXCEPTIONS:
                continue
            tree = ast.parse(path.read_text(), filename=str(path))
            if _is_shim(tree):
                continue
            stmt = _first_non_docstring_statement(tree)
            if not _imports_future_annotations(stmt):
                violations.append(rel)
        assert not violations, (
            "Files missing `from __future__ import annotations` "
            "as the first non-docstring statement:\n  - "
            + "\n  - ".join(violations)
            + "\n\nIf the file is a backward-compat shim, include "
            f'"{SHIM_MARKER}" in its module docstring.'
        )

    def test_explicit_exceptions_still_exist(self):
        # If an exception file is removed or renamed, drop it from the
        # exception list rather than letting the test silently no-op.
        for rel in EXPLICIT_EXCEPTIONS:
            assert (REPO_ROOT / rel).exists(), (
                f"Explicit exception '{rel}' no longer exists — "
                f"remove it from EXPLICIT_EXCEPTIONS."
            )
