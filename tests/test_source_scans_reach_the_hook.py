"""A structural scan of the plugin's Python reaches the extensionless hook.

The hook's whole CLI lives in ``plugin/bin/prawduct-hook``, which has no ``.py``
suffix. A test that pins a property of "the plugin's code" by globbing ``*.py``
passes over it, so a defect there stays green. That gap stood in eight guards
at once (an AST pin that only ``branch_review_chain`` calls ``review_chain``,
the build-plan decoding sweep, the foreign-target guard's call sites, a
one-home prose pin, and others), so the source set has one owner,
``conftest.plugin_python_sources``, and this test holds the plugin's ``*.py``
scans to it.

**What turns this red.** A ``*.py`` glob (``rglob("*.py")``, ``glob("*.py")``
or ``glob("**/*.py")``), in a function or at module level, on a receiver built
from a literal ``"plugin"`` path or a name bound to one (through derivations,
annotated and walrus bindings, and imports from a sibling test module), where
the hook is not brought into THAT scan: the statement holding the glob names
neither ``prawduct-hook`` nor ``plugin_python_sources``, and no statement in the
same scope names one while also using a name the glob's statement fills. A
subprocess call to the hook elsewhere in the function does not count.

**What slips it.** A receiver whose root the AST cannot see is a plugin path,
such as a loop variable over a roots table; those scans name the hook by hand.
A scan deliberately bounded to one package (``plugin/lib/backlog``) is a plugin
scan to this rule and sits in ``_BOUNDED_BY_DESIGN`` with its reason. The check
raises the cost of the hole; it does not make it impossible.
"""

from __future__ import annotations

import ast
import functools
from pathlib import Path

from conftest import plugin_python_sources  # noqa: E402

TESTS = Path(__file__).resolve().parent
PLUGIN = TESTS.parent / "plugin"

_PY_GLOBS = {("rglob", "*.py"), ("glob", "*.py"), ("glob", "**/*.py")}

#: Scans that leave the hook out of the glob on purpose, by (test file, scope).
_BOUNDED_BY_DESIGN: dict[tuple[str, str], str] = {
    ("test_backlog_invariants.py", "<module>"):
        "pins the backlog package's own modules; the hook is not in that package",
    ("test_handoff_parser_correctness.py", "test_no_consumer_walks_the_status_section_itself"):
        "scans the hook in its own pass, skipping the one writer span it owns",
    ("test_source_scans_reach_the_hook.py", "test_it_holds_every_py_file_and_both_executables"):
        "the owner's own check: globs *.py to prove the owner holds every one",
}


@functools.lru_cache(maxsize=None)
def _parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


@functools.lru_cache(maxsize=None)
def _sibling_plugin_names(directory: Path, module: str, seen: "frozenset[str]") -> "frozenset[str]":
    """Resolved the way pytest's prepend import mode finds it: the importing
    file's own directory first, then ``tests/``."""
    for base in (directory, TESTS):
        sibling = base / f"{module}.py"
        if sibling.is_file():
            return frozenset(_plugin_names(_parsed(sibling), sibling.parent, seen))
    return frozenset()


def _bindings(node: ast.AST) -> "tuple[list[ast.expr], ast.expr | None]":
    if isinstance(node, ast.Assign):
        return node.targets, node.value
    if isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and node.value is not None:
        return [node.target], node.value
    return [], None


def _plugin_names(tree: ast.AST, directory: Path = TESTS, _seen: "frozenset[str]" = frozenset()) -> set[str]:
    """Names this file binds, at any depth, to an expression spelling ``"plugin"``
    or to a name already so bound; and names it imports from a sibling test module
    that binds them so (``from test_critic_consolidate import ROOT``)."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            if node.module not in _seen:
                bound = _sibling_plugin_names(directory, node.module, _seen | {node.module})
                names |= {a.asname or a.name for a in node.names if a.name in bound}
    grew = True
    while grew:
        grew = False
        for node in ast.walk(tree):
            targets, value = _bindings(node)
            if value is None:
                continue
            spelled = _spells_plugin(value)
            derived = any(isinstance(n, ast.Name) and n.id in names for n in ast.walk(value))
            if spelled or derived:
                new = {t.id for t in targets if isinstance(t, ast.Name)} - names
                if new:
                    names |= new
                    grew = True
    return names


def _spells_plugin(expr: ast.AST) -> bool:
    return any(isinstance(n, ast.Constant) and n.value == "plugin" for n in ast.walk(expr))


def _is_plugin_receiver(receiver: ast.expr, plugin_names: set[str]) -> bool:
    if _spells_plugin(receiver):
        return True
    return any(isinstance(n, ast.Name) and n.id in plugin_names for n in ast.walk(receiver))


def _is_py_glob(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and bool(node.args)
        and isinstance(node.args[0], ast.Constant)
        and (node.func.attr, node.args[0].value) in _PY_GLOBS
    )


def _brings_hook(stmt: ast.AST, hook_names: "frozenset[str] | set[str]" = frozenset()) -> bool:
    """The statement names the hook, the owner, or a name bound to either."""
    return any(
        (isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.endswith("prawduct-hook"))
        or (isinstance(n, ast.Name) and (n.id == "plugin_python_sources" or n.id in hook_names))
        for n in ast.walk(stmt)
    )


_FILLS = {"append", "extend", "add", "update"}


def _filled_names(stmt: ast.stmt) -> set[str]:
    """Names the statement holding a glob fills with its result: an assignment's
    targets, and the collections a loop appends into or subscripts."""
    out = {leaf.id for t in _bindings(stmt)[0] for leaf in ast.walk(t) if isinstance(leaf, ast.Name)}
    for n in ast.walk(stmt):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in _FILLS and isinstance(n.func.value, ast.Name)):
            out.add(n.func.value.id)
        if isinstance(n, (ast.Assign, ast.AugAssign)):
            for t in (n.targets if isinstance(n, ast.Assign) else [n.target]):
                if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name):
                    out.add(t.value.id)
                if isinstance(n, ast.AugAssign) and isinstance(t, ast.Name):
                    out.add(t.id)
    return out


def _scopes(tree: ast.Module):
    """``(name, statements)`` for the module's own statements and each function's."""
    yield "<module>", [s for s in tree.body if not isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield fn.name, fn.body


def _statements(stmts: list) -> list[ast.stmt]:
    """Every statement in ``stmts``, nested ones included, not entering nested defs."""
    out: list[ast.stmt] = []
    stack = list(stmts)
    while stack:
        stmt = stack.pop()
        out.append(stmt)
        for child in ast.iter_child_nodes(stmt):
            if isinstance(child, ast.stmt) and not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                stack.append(child)
    return out


def _innermost(stmts: list[ast.stmt], call: ast.Call) -> ast.stmt:
    holding = [s for s in stmts if any(n is call for n in ast.walk(s))]
    return min(holding, key=lambda s: sum(1 for _ in ast.walk(s)))


def unreached_hook_scans(source: str, label: str, directory: Path = TESTS) -> list[str]:
    """``label:line`` for each plugin ``*.py`` scan in ``source`` that does not
    bring the hook into its own scan."""
    if "*.py" not in source:
        return []
    tree = ast.parse(source)
    plugin_names = _plugin_names(tree, directory)
    offenders = []
    for scope, body in _scopes(tree):
        if (label, scope) in _BOUNDED_BY_DESIGN:
            continue
        stmts = _statements(body)
        hook_names = {
            leaf.id
            for st in stmts
            for targets, value in [_bindings(st)]
            if value is not None and _brings_hook(value)
            for t in targets
            for leaf in ast.walk(t)
            if isinstance(leaf, ast.Name)
        }
        for stmt in stmts:
            for node in ast.walk(stmt):
                if not (_is_py_glob(node) and _is_plugin_receiver(node.func.value, plugin_names)):
                    continue
                inner = _innermost(stmts, node)
                if inner is not stmt:
                    continue  # counted once, at the statement that holds it most tightly
                if _brings_hook(inner):
                    continue
                filled = _filled_names(inner)
                if any(
                    _brings_hook(other, hook_names)
                    and any(isinstance(n, ast.Name) and n.id in filled for n in ast.walk(other))
                    for other in stmts
                    if other is not inner and not any(o is inner for o in ast.walk(other))
                ):
                    continue
                offenders.append(f"{label}:{node.lineno}")
    return sorted(set(offenders), key=lambda h: int(h.rsplit(":", 1)[1]))


def _test_sources() -> list[Path]:
    return sorted(
        p for p in TESTS.rglob("*.py")
        if "__pycache__" not in p.parts and p.name != "conftest.py"
    )


class TestEveryPluginScanReachesTheHook:
    def test_no_test_globs_the_plugin_without_the_hook(self):
        sources = _test_sources()
        assert len(sources) > 200, "the sweep read almost nothing — the glob broke"
        offenders = [
            hit
            for path in sources
            for hit in unreached_hook_scans(
                path.read_text(encoding="utf-8"), str(path.relative_to(TESTS)), path.parent
            )
        ]
        assert offenders == [], (
            "these scan the plugin's *.py and miss the extensionless bin/prawduct-hook; "
            "read conftest.plugin_python_sources instead: " + ", ".join(offenders)
        )

    def test_every_exemption_names_a_live_plugin_scan(self):
        """An exemption whose scope is gone, or no longer holds a plugin scan,
        would excuse whatever takes its name next: each must still match one."""
        for (label, scope), _reason in _BOUNDED_BY_DESIGN.items():
            path = TESTS / label
            tree = _parsed(path)
            names = _plugin_names(tree, path.parent)
            bodies = [body for name, body in _scopes(tree) if name == scope]
            assert bodies, f"{label}: no scope {scope!r}"
            assert any(
                _is_py_glob(n) and _is_plugin_receiver(n.func.value, names)
                for body in bodies for st in body for n in ast.walk(st)
            ), f"{label}:{scope} holds no plugin scan; drop the exemption"

    def test_the_sweep_sees_the_scans_it_polices(self):
        """Non-vacuous: the sweep's receiver rule recognises the plugin scans this
        suite really has, so a broken name resolver cannot pass by seeing none."""
        seen = 0
        for path in _test_sources():
            if "*.py" not in path.read_text(encoding="utf-8"):
                continue
            tree = _parsed(path)
            names = _plugin_names(tree, path.parent)
            seen += sum(
                1
                for node in ast.walk(tree)
                if _is_py_glob(node) and _is_plugin_receiver(node.func.value, names)
            )
        assert seen >= 5, seen

    def test_it_catches_a_scan_that_misses_the_hook(self):
        planted = (
            "from pathlib import Path\n"
            "ROOT = Path(__file__).parent.parent / 'plugin'\n"
            "def test_x():\n"
            "    for p in sorted((ROOT / 'lib').rglob('*.py')):\n"
            "        pass\n"
            "def test_local():\n"
            "    plugin = Path('.') / \"plugin\"\n"
            "    return list(plugin.glob('**/*.py'))\n"
            "from test_critic_consolidate import ROOT as IMPORTED\n"
            "def test_imported():\n"
            "    return sorted(IMPORTED.rglob('*.py'))\n"
            "def test_flat():\n"
            "    return [p for p in (ROOT / 'lib').glob('*.py')]\n"
            "MODULE_LEVEL = sorted((ROOT / 'lib').glob('*.py'))\n"
            "ANNOTATED: Path = Path('.') / 'plugin'\n"
            "def test_annotated():\n"
            "    return list(ANNOTATED.rglob('*.py'))\n"
            "def test_runs_the_hook_but_scans_without_it():\n"
            "    subprocess.run([str(ROOT / 'bin' / 'prawduct-hook')])\n"
            "    for p in ROOT.rglob('*.py'):\n"
            "        pass\n"
        )
        assert unreached_hook_scans(planted, "planted") == [
            "planted:4", "planted:8", "planted:11", "planted:13", "planted:14", "planted:17", "planted:20",
        ]

    def test_a_scan_that_names_the_hook_or_reads_the_owner_passes(self):
        """The control: the same scans, once they bring the hook in, are clean."""
        fixed = (
            "from pathlib import Path\n"
            "ROOT = Path(__file__).parent.parent / 'plugin'\n"
            "def test_x():\n"
            "    for p in [*(ROOT / 'lib').rglob('*.py'), ROOT / 'bin' / 'prawduct-hook']:\n"
            "        pass\n"
            "def test_y():\n"
            "    return plugin_python_sources()\n"
            "def test_tests_dir():\n"
            "    return list(Path('tests').rglob('*.py'))\n"
            "def test_appended_later():\n"
            "    files = []\n"
            "    for p in (ROOT / 'lib').rglob('*.py'):\n"
            "        files.append(p)\n"
            "    hook = ROOT / 'bin' / 'prawduct-hook'\n"
            "    if hook.is_file():\n"
            "        files.append(hook)\n"
            "    return files\n"
            "def test_extended():\n"
            "    files = sorted(ROOT.rglob('*.py'))\n"
            "    files.append(ROOT / 'bin' / 'prawduct-hook')\n"
        )
        assert unreached_hook_scans(fixed, "fixed") == []


class TestTheOwnerIsTheShippedRuntime:
    def test_it_holds_every_py_file_and_both_executables(self):
        found = set(plugin_python_sources())
        py = {p for p in PLUGIN.rglob("*.py") if "__pycache__" not in p.parts}
        assert py and py <= found
        assert {PLUGIN / "bin" / "prawduct-hook", PLUGIN / "bin" / "test-reference-verify"} <= found
        assert not any("__pycache__" in p.parts for p in found)

    def test_a_python_executable_counts_whatever_its_interpreter_line(self):
        from conftest import _PYTHON_SHEBANG

        for line in ("#!/usr/bin/env python3", "#!/usr/bin/python3", "#! /usr/bin/env python",
                     "#!/usr/bin/env python3.12"):
            assert _PYTHON_SHEBANG.match(line), line
        for line in ("#!/bin/sh", "#!/usr/bin/env bash", "# python3 is required"):
            assert not _PYTHON_SHEBANG.match(line), line
