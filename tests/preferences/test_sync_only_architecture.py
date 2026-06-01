"""Project-preferences enforcement: sync-only architecture.

Enforces the Async preference in `.prawduct/artifacts/project-preferences.md`:
prawduct's CLI tools are sync throughout — no `async def`, no `import asyncio`.

This is an AST recursive walk: every node in every implementation file under
`tools/`, `tests/`, `hooks/`, and `lib/` (plus the extensionless plugin runtime
`bin/prawduct-hook`) is checked, not just top-level statements. Catches asyncio
creep anywhere — nested functions, conditional imports, etc. The `lib/` and
`bin/` roots are the v2.0.0 plugin runtime (build-plan Chunk 5); the invariant
holds for the bundled governance code too.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _python_files() -> list[Path]:
    files: list[Path] = []
    for root in ("tools", "tests", "hooks", "lib"):
        for path in (REPO_ROOT / root).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            files.append(path)
    # The plugin runtime hook is an executable Python script with no .py suffix.
    hook = REPO_ROOT / "bin" / "prawduct-hook"
    if hook.is_file():
        files.append(hook)
    return sorted(files)


def _async_violations(tree: ast.Module) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            violations.append(f"async def {node.name} (line {node.lineno})")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "asyncio" or alias.name.startswith("asyncio."):
                    violations.append(f"import {alias.name} (line {node.lineno})")
        elif isinstance(node, ast.ImportFrom):
            if node.module == "asyncio" or (node.module or "").startswith("asyncio."):
                violations.append(f"from {node.module} import ... (line {node.lineno})")
    return violations


class TestSyncOnlyArchitecture:
    def test_no_async_def_or_asyncio_imports(self):
        violations: list[str] = []
        for path in _python_files():
            tree = ast.parse(path.read_text(), filename=str(path))
            for finding in _async_violations(tree):
                rel = path.relative_to(REPO_ROOT).as_posix()
                violations.append(f"{rel}: {finding}")
        assert not violations, (
            "Sync-only architecture violation — async constructs found:\n  - "
            + "\n  - ".join(violations)
        )
