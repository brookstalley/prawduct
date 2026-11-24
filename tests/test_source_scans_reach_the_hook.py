"""A structural scan of the plugin's Python reaches the extensionless hook.

The hook's whole CLI lives in ``plugin/bin/prawduct-hook``, which has no ``.py``
suffix. A test that pins a property of "the plugin's code" by globbing ``*.py``
passes over it, so a defect there stays green. That gap stood in seven guards
at once (an AST pin that only ``branch_review_chain`` calls ``review_chain``,
the build-plan decoding sweep, the foreign-target guard's call sites, and
others), so the source set has one owner, ``conftest.plugin_python_sources``,
and this test holds every ``*.py`` scan of ``plugin/`` to it.

**What turns this red.** A test function that globs ``*.py`` (``rglob("*.py")``
or ``glob("**/*.py")``) on a receiver built from a name bound to a ``"plugin"``
path, or a literal ``"plugin"`` path, while that function neither names
``prawduct-hook`` nor calls ``plugin_python_sources``. **What slips it.** A
receiver whose root the AST cannot see is a plugin path, such as a loop variable
over a roots table; those scans already name the hook by hand. The check raises
the cost of the hole; it does not make it impossible.
"""

from __future__ import annotations

import ast
import functools
from pathlib import Path

from conftest import plugin_python_sources  # noqa: E402

TESTS = Path(__file__).resolve().parent
PLUGIN = TESTS.parent / "plugin"

_PY_GLOBS = {("rglob", "*.py"), ("glob", "**/*.py")}


@functools.lru_cache(maxsize=None)
def _sibling_plugin_names(module: str, seen: "frozenset[str]") -> "frozenset[str]":
    sibling = TESTS / f"{module}.py"
    if not sibling.is_file():
        return frozenset()
    return frozenset(_plugin_names(_parsed(sibling), seen))


@functools.lru_cache(maxsize=None)
def _parsed(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _plugin_names(tree: ast.AST, _seen: "frozenset[str]" = frozenset()) -> set[str]:
    """Names this file binds, at any depth, to an expression spelling ``"plugin"``
    or to a name already so bound; and names it imports from a sibling test module
    that binds them so (``from test_critic_consolidate import ROOT``)."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            if node.module not in _seen:
                bound = _sibling_plugin_names(node.module, _seen | {node.module})
                names |= {a.asname or a.name for a in node.names if a.name in bound}
    grew = True
    while grew:
        grew = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            value = node.value
            spelled = _spells_plugin(value)
            derived = any(isinstance(n, ast.Name) and n.id in names for n in ast.walk(value))
            if spelled or derived:
                new = {t.id for t in node.targets if isinstance(t, ast.Name)} - names
                if new:
                    names |= new
                    grew = True
    return names


def _spells_plugin(expr: ast.expr) -> bool:
    return any(isinstance(n, ast.Constant) and n.value == "plugin" for n in ast.walk(expr))


def _is_plugin_receiver(receiver: ast.expr, plugin_names: set[str]) -> bool:
    if _spells_plugin(receiver):
        return True
    return any(isinstance(n, ast.Name) and n.id in plugin_names for n in ast.walk(receiver))


def unreached_hook_scans(source: str, label: str) -> list[str]:
    """``label:line`` for each plugin ``*.py`` scan in ``source`` whose function
    never brings the hook in."""
    if "*.py" not in source:
        return []
    tree = ast.parse(source)
    plugin_names = _plugin_names(tree)
    offenders = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if any(
            (isinstance(n, ast.Constant) and isinstance(n.value, str)
             and n.value.endswith("prawduct-hook"))
            or (isinstance(n, ast.Name) and n.id == "plugin_python_sources")
            for n in ast.walk(fn)
        ):
            continue
        for node in ast.walk(fn):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            arg = node.args[0] if node.args else None
            if not (isinstance(arg, ast.Constant) and (node.func.attr, arg.value) in _PY_GLOBS):
                continue
            if _is_plugin_receiver(node.func.value, plugin_names):
                offenders.append(f"{label}:{node.lineno}")
    return offenders


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
                path.read_text(encoding="utf-8"), str(path.relative_to(TESTS))
            )
        ]
        assert offenders == [], (
            "these scan the plugin's *.py and miss the extensionless bin/prawduct-hook; "
            "read conftest.plugin_python_sources instead: " + ", ".join(offenders)
        )

    def test_the_sweep_sees_the_scans_it_polices(self):
        """Non-vacuous: the sweep's receiver rule recognises the plugin scans this
        suite really has, so a broken name resolver cannot pass by seeing none."""
        seen = 0
        for path in _test_sources():
            if "*.py" not in path.read_text(encoding="utf-8"):
                continue
            tree = _parsed(path)
            names = _plugin_names(tree)
            seen += sum(
                1
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and (node.func.attr, node.args[0].value) in _PY_GLOBS
                and _is_plugin_receiver(node.func.value, names)
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
        )
        assert unreached_hook_scans(planted, "planted") == ["planted:4", "planted:8", "planted:11"]

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
        )
        assert unreached_hook_scans(fixed, "fixed") == []


class TestTheOwnerIsTheShippedRuntime:
    def test_it_holds_every_py_file_and_both_executables(self):
        found = set(plugin_python_sources())
        py = {p for p in PLUGIN.rglob("*.py") if "__pycache__" not in p.parts}
        assert py and py <= found
        assert {PLUGIN / "bin" / "prawduct-hook", PLUGIN / "bin" / "test-reference-verify"} <= found
        assert not any("__pycache__" in p.parts for p in found)
