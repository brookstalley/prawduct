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

from lib import core
from lib import critic_consolidate as cc

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugin"


def _plugin_sources() -> list[Path]:
    """Every Python source under ``plugin/``, the extensionless hook included."""
    files = sorted(p for p in PLUGIN.rglob("*.py") if "__pycache__" not in p.parts)
    files.append(PLUGIN / "bin" / "prawduct-hook")
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
