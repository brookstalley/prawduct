"""Every temp file prawduct writes into a working tree carries ``core.TEMP_SUFFIX`` (#1202).

A write goes through a sibling that is renamed into place, so for an instant the
sibling exists untracked. Consolidation's tree check must read it as a session
file, or the writer refuses a review; and it must be ignored, or a write that died
before the rename leaves it for the next ``git add -A``. One suffix makes that a
single ignore entry and a single exemption. These tests pin the three halves: the
writers use the suffix, the contract ignores it, and the tree check exempts it.
"""

from __future__ import annotations

import ast
import subprocess
from pathlib import Path

from conftest import plugin_python_sources  # noqa: E402

from lib import core
from lib import critic_consolidate as cc

ROOT = Path(__file__).resolve().parent.parent


def _plugin_sources() -> list[Path]:
    """Every Python source under ``plugin/`` (the extensionless hook included) and
    this repo's ``tools/``, which write into ``.prawduct/research/``."""
    files = plugin_python_sources()
    files += sorted((ROOT / "tools").glob("*.py"))
    return files


def _tmp_literals(path: Path) -> list[tuple[int, str]]:
    """String constants in ``path`` that END in ``.tmp`` — a temp name or suffix.
    f-string parts are constants too, so ``f"{p}.{pid}.tmp"`` is seen."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.endswith(".tmp")
    ]


class TestWritersUseTheSuffix:
    def test_no_temp_name_in_plugin_ends_in_a_bare_tmp(self):
        sources = _plugin_sources()
        assert len(sources) > 100, "the scan read almost nothing — the glob broke"
        offenders = [
            f"{path.relative_to(ROOT)}:{line}: {value!r}"
            for path in sources
            for line, value in _tmp_literals(path)
            if not value.endswith(core.TEMP_SUFFIX)
        ]
        assert offenders == [], (
            "temp names must end in core.TEMP_SUFFIX (use core.temp_sibling, or end a "
            "mkstemp suffix with it): " + "; ".join(offenders)
        )

    def test_the_scan_reaches_the_spelled_sites(self):
        """The two modules that cannot import ``lib`` spell the suffix; the scan must
        see their literals, or a reverted spelling would pass unnoticed."""
        seen = {
            path.name
            for path in _plugin_sources()
            for _line, value in _tmp_literals(path)
            if value.endswith(core.TEMP_SUFFIX)
        }
        assert {"host.py", "prawduct-hook"} <= seen

    def test_atomic_write_goes_through_a_suffixed_sibling(self, tmp_path, monkeypatch):
        target = tmp_path / ".prawduct" / "state.json"
        target.parent.mkdir()
        replaced: list[tuple[str, str]] = []
        real_replace = core.os.replace

        def spy(src, dst):
            replaced.append((Path(src).name, Path(dst).name))
            real_replace(src, dst)

        monkeypatch.setattr(core.os, "replace", spy)
        core.atomic_write_text(target, "{}\n")
        assert replaced == [("state.json" + core.TEMP_SUFFIX, "state.json")]


#: Renames that move a finished file rather than stage one, by (file, function).
_MOVES_NOT_STAGING = {
    # Moves a dead review's leftover files into the archive; nothing is written.
    ("critic_consolidate.py", "_archive_leftovers"),
}


def _staged_renames(path: Path) -> list[tuple[int, str, str]]:
    """``(line, function, source)`` for each rename-into-place in ``path`` whose
    source is not built with the temp suffix.

    Keyed on the ACT, not the name shape: a write renamed into place leaves its
    source behind on a crash whatever it is called, which is how
    ``.critic-findings.json.derived`` escaped a ``.tmp``-name sweep. The act is
    ``os.replace``/``os.rename`` and a one-argument ``.replace``/``.rename`` on a
    name (``str.replace`` takes two). A source counts as suffixed when its
    assignment in the same function calls ``temp_sibling``, names
    ``TEMP_SUFFIX``, or spells a constant ending in it."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if (path.name, fn.name) in _MOVES_NOT_STAGING:
            continue
        bindings: dict[str, list[ast.AST]] = {}
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    for leaf in ast.walk(target):
                        if isinstance(leaf, ast.Name):
                            bindings.setdefault(leaf.id, []).append(node.value)
        for node in ast.walk(fn):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            attr, recv = node.func.attr, node.func.value
            if attr not in ("replace", "rename"):
                continue
            if isinstance(recv, ast.Name) and recv.id == "os" and len(node.args) == 2:
                source = node.args[0]
            elif len(node.args) == 1 and not node.keywords and isinstance(recv, ast.Name) and recv.id != "os":
                source = recv
            else:
                continue
            if not isinstance(source, ast.Name):
                out.append((node.lineno, fn.name, ast.unparse(source)))
                continue
            values = bindings.get(source.id, [])
            if not any(_carries_suffix(v) for v in values):
                out.append((node.lineno, fn.name, source.id))
    return out


def _carries_suffix(value: ast.AST) -> bool:
    for n in ast.walk(value):
        if isinstance(n, ast.Name) and n.id == "TEMP_SUFFIX":
            return True
        if isinstance(n, ast.Attribute) and n.attr in ("TEMP_SUFFIX", "temp_sibling"):
            return True
        if isinstance(n, ast.Name) and n.id == "temp_sibling":
            return True
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value.endswith(core.TEMP_SUFFIX):
            return True
    return False


class TestEveryRenameIntoPlaceStagesASuffixedFile:
    def test_every_staged_rename_source_carries_the_suffix(self):
        sources = _plugin_sources()
        offenders = [
            f"{path.relative_to(ROOT)}:{line} in {fn}(): {src}"
            for path in sources
            for line, fn, src in _staged_renames(path)
        ]
        assert offenders == [], (
            "a file renamed into place must be staged under core.TEMP_SUFFIX "
            "(core.temp_sibling), or a crash leaves it untracked: " + "; ".join(offenders)
        )

    def test_the_sweep_reaches_the_renames_it_polices(self):
        """Non-vacuous: the act is seen at every kind of site — the core writer,
        the hook, a spelled suffix, a mkstemp suffix, and the findings candidate."""
        reached = set()
        for path in _plugin_sources():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == "replace" and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "os" and len(node.args) == 2):
                    reached.add(path.name)
        assert {"core.py", "prawduct-hook", "host.py", "snapshot.py", "critic_consolidate.py"} <= reached

    def test_every_exempt_move_still_exists(self):
        """An exemption naming a function that is gone would exempt its successor
        silently, so each entry must still name a function in that file."""
        defined = {
            (path.name, n.name)
            for path in _plugin_sources()
            for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert _MOVES_NOT_STAGING <= defined

    def test_it_catches_an_unsuffixed_stage_and_passes_a_suffixed_one(self, tmp_path):
        planted = tmp_path / "planted.py"
        planted.write_text(
            "import os\n"
            "def bad(d, f):\n"
            "    candidate = d / '.x.json.derived'\n"
            "    candidate.write_text('{}')\n"
            "    os.replace(candidate, f)\n"
            "def bad_method(d, f):\n"
            "    tmp = d / 'x.tmp'\n"
            "    tmp.replace(f)\n"
            "def good(d, f):\n"
            "    tmp = d / ('.x.json.derived' + TEMP_SUFFIX)\n"
            "    os.replace(tmp, f)\n"
            "def good_sibling(f):\n"
            "    tmp = temp_sibling(f)\n"
            "    tmp.replace(f)\n"
            "def not_a_rename(s):\n"
            "    return s.replace('a', 'b')\n",
            encoding="utf-8",
        )
        assert [(fn, src) for _l, fn, src in _staged_renames(planted)] == [
            ("bad", "candidate"), ("bad_method", "tmp"),
        ]


class TestTheContractCoversTheSuffix:
    def test_the_session_contract_ignores_the_suffix_under_prawduct(self):
        """Anchored under `.prawduct/`, so a wholesale `.prawduct/` rule in a
        product's `.gitignore` already satisfies it (test_gitignore_contract_semantics)."""
        assert ".prawduct/**/*" + core.TEMP_SUFFIX in core.GITIGNORE_ENTRIES

    def test_this_repos_gitignore_ignores_temp_files_under_prawduct(self):
        """The real ignore file, read by git: a temp directly under `.prawduct/` and
        one beside a plan are ignored; a bare `.tmp` (a product's own name) is not."""

        def ignored(rel: str) -> bool:
            return subprocess.run(
                ["git", "check-ignore", "-q", "--no-index", rel], cwd=ROOT
            ).returncode == 0

        assert ignored(".prawduct/.critic-findings.json" + core.TEMP_SUFFIX)
        assert ignored(".prawduct/artifacts/build-plan.md" + core.TEMP_SUFFIX)
        assert ignored(".prawduct/.critic-findings.json.derived" + core.TEMP_SUFFIX)
        assert not ignored("src/scratch.tmp")
        assert not ignored(".prawduct/.critic-findings.json.tmp")


class TestTheTreeCheckExemptsTheSuffix:
    def test_a_temp_sibling_under_prawduct_is_a_session_file(self):
        for target in (".prawduct/.critic-findings.json", ".prawduct/artifacts/plan.md"):
            sibling = core.temp_sibling(Path(target)).as_posix()
            assert cc._is_session_file(sibling, ""), sibling
            assert cc._is_session_file("proj/" + sibling, "proj/"), sibling

    def test_the_exemption_is_the_suffix_under_prawduct_only(self):
        """Controls: not every `.tmp`; not another project's `.prawduct/`; and not
        the learnings temp file, the one writer outside `.prawduct/` (an attended
        compaction, whose leftover git shows): the boundary is deliberate."""
        assert not cc._is_session_file(".prawduct/.critic-findings.json.tmp", "")
        assert not cc._is_session_file("src/scratch.tmp", "")
        assert not cc._is_session_file(".prawduct/x.json" + core.TEMP_SUFFIX, "proj/")
        learnings = core.temp_sibling(Path(".claude/rules/learnings/core.md")).as_posix()
        assert not cc._is_session_file(learnings, "")
