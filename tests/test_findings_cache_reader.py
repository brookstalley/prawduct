"""``.prawduct/.critic-findings.json`` has ONE reader.

The UTF-8 fix for this file went in site by site — ``critic_mode`` twice, the
briefing, ``gates.validate_critic_findings``, ``ledger``, ``verify_anchor`` and
more in ``critic_consolidate`` — and a comment that fix deleted recorded that
the per-site pattern had already regressed three times. So the file is read
through :func:`critic_consolidate.read_findings_cache` (or, for a path such as
the ``.derived`` candidate, :func:`critic_consolidate.read_findings_record`),
which answers with the parsed record or a typed absence, and a guard keeps
every other module from building the path to open it.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lib import critic_consolidate as cc  # noqa: E402

OWNER = ROOT / "lib" / "critic_consolidate.py"
NAME = ".critic-findings.json"


def _plugin_sources() -> "list[Path]":
    """Every Python source the plugin ships: ``*.py`` anywhere under it, and
    the extensionless executables in ``bin/`` that are Python."""
    found = sorted(ROOT.rglob("*.py"))
    for path in sorted((ROOT / "bin").iterdir()):
        if path.is_file() and path.suffix == "" and path.read_text(
            encoding="utf-8", errors="replace"
        ).startswith("#!/usr/bin/env python"):
            found.append(path)
    return found


def _opens_the_cache(source: str) -> "list[int]":
    """Lines where ``source`` builds the cache's path to read it: the file
    name as a path component (``x / ".critic-findings.json"``), or a string
    naming the file passed to a call (``Path(...)``, ``open(...)``,
    ``os.path.join(...)``). A list of paths (a gitignore set) and prose in a
    message or docstring name the file without opening it."""
    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    hits = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        value = node.value
        if not (value == NAME or value.endswith("/" + NAME)):
            continue
        parent = parents.get(node)
        if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Div):
            hits.append(node.lineno)
        elif isinstance(parent, ast.Call):
            hits.append(node.lineno)
        elif value == NAME and not isinstance(parent, (ast.Tuple, ast.List, ast.Set)):
            # The bare file name has no use but as a path component; one bound
            # to a name (a second constant) is a second spelling to open by.
            hits.append(node.lineno)
    return sorted(hits + _reads_a_findings_path(tree))


_READS = {"read_text", "read_bytes", "open"}


def _names_findings(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return "findings" in node.id.lower()
    if isinstance(node, ast.Attribute):
        return "findings" in node.attr.lower()
    return False


def _reads_a_findings_path(tree: ast.AST) -> "list[int]":
    """The second shape: a path handed in from elsewhere and read in place —
    ``findings_path.read_text()``, ``open(findings_path)`` — which is how
    ``gates.validate_critic_findings`` read the cache without naming it."""
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and func.attr in _READS and _names_findings(func.value):
            hits.append(node.lineno)
        elif isinstance(func, ast.Name) and func.id == "open" and node.args and _names_findings(node.args[0]):
            hits.append(node.lineno)
    return hits


class TestOneReader:
    def test_the_detector_catches_each_shape_it_names(self):
        """A guard never seen to fire proves nothing: each opening shape is
        flagged, and the shapes that only name the file are not."""
        assert _opens_the_cache('p = d / ".critic-findings.json"\n') == [1]
        assert _opens_the_cache('p = Path(".prawduct/.critic-findings.json")\n') == [1]
        assert _opens_the_cache('NAME = ".critic-findings.json"\n') == [1]
        assert _opens_the_cache('t = (".prawduct/.critic-findings.json",)\n') == []
        assert _opens_the_cache('print("rewrite .critic-findings.json now")\n') == []
        assert _opens_the_cache('p = d / ".critic-findings.json.derived"\n') == []
        assert _opens_the_cache("def v(findings_path):\n    return findings_path.read_text()\n") == [2]
        assert _opens_the_cache("with open(findings_path) as f:\n    pass\n") == [1]
        assert _opens_the_cache("text = state_path.read_text()\n") == []

    def test_no_module_but_the_owner_opens_the_cache(self):
        sources = _plugin_sources()
        names = {p.name for p in sources}
        # The set was really walked: the modules that used to open it are in it.
        for known in ("briefing.py", "critic_mode.py", "gates.py", "ledger.py", "prawduct-hook"):
            assert known in names, known
        offenders = {
            str(p.relative_to(ROOT)): hits
            for p in sources
            if p != OWNER and (hits := _opens_the_cache(p.read_text(encoding="utf-8")))
        }
        assert offenders == {}, (
            "read .prawduct/.critic-findings.json through "
            f"critic_consolidate.read_findings_cache: {offenders}"
        )

    def test_the_owner_spells_the_name_once(self):
        """In the owner too the path is built in one place, so its own readers
        and writers go through ``findings_cache_path``."""
        assert len(_opens_the_cache(OWNER.read_text(encoding="utf-8"))) == 1
        assert cc.FINDINGS_CACHE_NAME == NAME


def _prawduct(tmp_path: Path) -> Path:
    d = tmp_path / ".prawduct"
    d.mkdir()
    return d


class TestTheTypedAnswer:
    def test_a_record(self, tmp_path):
        d = _prawduct(tmp_path)
        (d / NAME).write_text(json.dumps({"fact_id": "rev-é"}), encoding="utf-8")
        read = cc.read_findings_cache(d)
        assert (read.state, read.record, read.reason) == (cc.FINDINGS_OK, {"fact_id": "rev-é"}, "")

    @pytest.mark.parametrize("write, state, said", [
        (None, cc.FINDINGS_ABSENT, "no findings cache in this worktree"),
        (b"\xff\xfe not utf-8\n", cc.FINDINGS_UNDECODABLE, "not valid UTF-8"),
        (b"{not json", cc.FINDINGS_INVALID_JSON, "not valid JSON"),
        (b"[1, 2]", cc.FINDINGS_NOT_A_RECORD, "not a findings record"),
    ], ids=["absent", "undecodable", "invalid-json", "not-a-record"])
    def test_each_absence_is_typed_and_says_no_path(self, tmp_path, write, state, said):
        d = _prawduct(tmp_path)
        if write is not None:
            (d / NAME).write_bytes(write)
        read = cc.read_findings_cache(d)
        assert read.state == state and read.record is None, read
        assert said in read.reason, read.reason
        assert str(tmp_path) not in read.reason and "/" not in read.reason, read.reason

    def test_an_unreadable_path_is_its_own_state(self, tmp_path):
        d = _prawduct(tmp_path)
        (d / NAME).mkdir()  # a directory where the file should be
        read = cc.read_findings_cache(d)
        assert read.state == cc.FINDINGS_UNREADABLE and read.record is None, read
        assert str(tmp_path) not in read.reason, read.reason

    def test_the_schema_validator_reads_through_it(self, tmp_path):
        """``gates.validate_critic_findings`` reads the file it validates by
        the one reader: a UTF-8 record passes, anything else fails."""
        from lib import gates

        d = _prawduct(tmp_path)
        path = d / NAME
        path.write_text(json.dumps(
            {"files_reviewed": ["a.py"], "findings": [], "summary": "clean — é"}
        ), encoding="utf-8")
        assert gates.validate_critic_findings(path) is True
        path.write_bytes(b"\xff\xfe")
        assert gates.validate_critic_findings(path) is False
        path.write_text("[]", encoding="utf-8")
        assert gates.validate_critic_findings(path) is False

    def test_a_named_path_reads_the_same_way(self, tmp_path):
        """The ``.derived`` candidate the cache writer validates before it
        replaces the cache is read by the same function."""
        candidate = tmp_path / (NAME + ".derived")
        candidate.write_bytes(b"\xff\xfe")
        assert cc.read_findings_record(candidate).state == cc.FINDINGS_UNDECODABLE
