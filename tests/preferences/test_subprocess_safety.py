"""Project-preferences enforcement: subprocess safety.

Enforces a security-relevant invariant aligned with the Tooling preference
in `.prawduct/artifacts/project-preferences.md` (subprocess used for git and
external commands): no `shell=True` in any subprocess invocation.

`shell=True` enables command injection when arguments include user-controlled
or path-derived strings. The list-form (`subprocess.run(["git", "status"])`)
is safe and equally capable. Prawduct's existing code uses the list-form
exclusively; this test locks that invariant in.

Detection: AST call-pattern check. Walks `Call` nodes whose function resolves
to `subprocess.<name>` (run, check_output, check_call, call, Popen) and asserts
no keyword argument `shell=True` is passed.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SUBPROCESS_FUNCS = frozenset({"run", "check_output", "check_call", "call", "Popen"})


def _python_files() -> list[Path]:
    files: list[Path] = []
    for root in ("tools", "tests"):
        for path in (REPO_ROOT / root).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            files.append(path)
    return sorted(files)


def _is_subprocess_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Attribute):
        if func.attr in SUBPROCESS_FUNCS:
            value = func.value
            if isinstance(value, ast.Name) and value.id == "subprocess":
                return True
    return False


def _has_shell_true(node: ast.Call) -> bool:
    for kw in node.keywords:
        if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
            return True
    return False


class TestSubprocessSafety:
    def test_no_shell_true_in_subprocess_calls(self):
        violations: list[str] = []
        for path in _python_files():
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _is_subprocess_call(node) and _has_shell_true(node):
                    rel = path.relative_to(REPO_ROOT).as_posix()
                    func_name = node.func.attr if isinstance(node.func, ast.Attribute) else "?"
                    violations.append(f"{rel}:{node.lineno}: subprocess.{func_name}(..., shell=True)")
        assert not violations, (
            "Subprocess safety violation — shell=True enables command injection. "
            "Use the list-form (subprocess.run([\"cmd\", \"arg\"])) instead.\n  - "
            + "\n  - ".join(violations)
        )
