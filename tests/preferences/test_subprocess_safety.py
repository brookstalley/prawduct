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

REPO_ROOT = Path(__file__).resolve().parent.parent.parent / "plugin"
SUBPROCESS_FUNCS = frozenset({"run", "check_output", "check_call", "call", "Popen"})

# Every Python root this preference is enforced over. `lib` and `hooks` are
# plugin-root; `tests` and `tools` are REPO-root — and getting that base wrong is not
# hypothetical. Until 2026-08-06 `tests` was bound to the plugin base, and
# `plugin/tests` has never existed: the repo's largest Python surface went unscanned
# for `shell=True` and the suite stayed green, because a missing root yields no files
# rather than an error. Green meant "no files", not "no violations".
# `test_scan_roots_all_exist` is what distinguishes a root that is legitimately absent
# from one that is misaddressed.
SCAN_ROOTS = (
    ("lib", REPO_ROOT),
    ("hooks", REPO_ROOT),
    ("tests", REPO_ROOT.parent),
    ("tools", REPO_ROOT.parent),
)


def _python_files() -> list[Path]:
    files: list[Path] = []
    for root, base in SCAN_ROOTS:
        for path in (base / root).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            files.append(path)
    # The plugin runtime scripts are executable Python with no .py suffix.
    for name in ("prawduct-hook", "test-reference-verify"):
        script = REPO_ROOT / "bin" / name
        if script.is_file():
            files.append(script)
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
                    rel = path.relative_to(REPO_ROOT.parent).as_posix()  # repo-relative: files span plugin/ and tools/
                    func_name = node.func.attr if isinstance(node.func, ast.Attribute) else "?"
                    violations.append(f"{rel}:{node.lineno}: subprocess.{func_name}(..., shell=True)")
        assert not violations, (
            "Subprocess safety violation — shell=True enables command injection. "
            "Use the list-form (subprocess.run([\"cmd\", \"arg\"])) instead.\n  - "
            + "\n  - ".join(violations)
        )

    def test_scan_roots_all_exist(self):
        # A misaddressed root scans nothing and passes forever. This is the only check
        # that can tell "no violations" from "no files"; without it the `tests` root sat
        # on the wrong base unnoticed.
        missing = [str(base / root) for root, base in SCAN_ROOTS if not (base / root).is_dir()]
        assert not missing, (
            "Scan root does not exist — this preference silently enforces nothing over it:\n  - "
            + "\n  - ".join(missing)
            + "\n\nFix the path (check whether the root is repo-level or plugin-level), "
            "or drop it from SCAN_ROOTS."
        )

    def test_scan_reaches_the_repo_test_tree(self):
        # The specific regression: `plugin/tests` for a `tests/` tree that lives at the
        # repo root. Naming the tree explicitly means a future root-list rewrite cannot
        # drop it and stay green.
        scanned = {p.relative_to(REPO_ROOT.parent).as_posix() for p in _python_files()}
        assert "tests/preferences/test_subprocess_safety.py" in scanned, (
            f"The repo's tests/ tree is not being scanned for shell=True — SCAN_ROOTS is {SCAN_ROOTS}"
        )
