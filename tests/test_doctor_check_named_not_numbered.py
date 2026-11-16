"""A message that sends someone to a doctor check names the check, never its ordinal.

Doctor's Health Checks are a numbered list, and the numbers move whenever a check is
inserted or retired. A string printed to an owner or an agent that says "check #22"
then silently points at a different check, and no test notices because the sentence
still reads fine. The check's NAME is what doctor's routing table and its list both
carry, so that is what a message cites.

Scanned: every string literal the runtime can print (``plugin/lib`` and the hook),
docstrings excluded since nobody is shown those, plus the PR skill's Step 1c rows,
which relay the PR gate's verdicts.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent / "plugin"
ORDINAL = re.compile(r"(?i)\bcheck ?#\d+")
LEGACY_LOG_CHECK = "Change record still on the legacy log"

#: User-facing ordinals outside this change's files, reported for their owners to fix.
#: Each is (file, count): a NEW ordinal in the same file still fails.
KNOWN = {"plugin/lib/norm_probes.py": 1}


def _runtime_sources() -> list[Path]:
    return [*sorted((PLUGIN / "lib").rglob("*.py")), PLUGIN / "bin" / "prawduct-hook"]


def _printed_literals(path: Path) -> list[str]:
    """String constants that are not docstrings (f-string parts included)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                docstrings.add(id(body[0].value))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings
    ]


def test_the_scan_reaches_the_runtime():
    sources = _runtime_sources()
    assert len(sources) > 20 and all(p.is_file() for p in sources)
    # The instrument can catch the shape it polices.
    assert ORDINAL.search("run /prawduct:doctor (check #22) to") and ORDINAL.search("Health Check #14 ")


def test_no_printed_string_cites_a_doctor_check_by_number():
    hits: dict[str, int] = {}
    for path in _runtime_sources():
        n = sum(len(ORDINAL.findall(s)) for s in _printed_literals(path))
        if n:
            hits[str(path.relative_to(PLUGIN.parent))] = n
    assert hits == KNOWN, (
        f"printed strings cite a doctor check by number: {hits} (known: {KNOWN}). "
        "Name the check instead; its number moves when the list does."
    )


def test_step_1c_cites_no_doctor_check_by_number():
    text = (PLUGIN / "skills" / "pr" / "SKILL.md").read_text(encoding="utf-8")
    start = text.index("### Step 1c:")
    step = text[start : text.index("### Step 1d:", start)]
    assert "/prawduct:doctor" in step, "control: Step 1c still routes to doctor"
    assert not ORDINAL.findall(step)


def test_the_name_cited_is_the_name_doctor_gives_the_check(tmp_path, capsys):
    """The name only helps if doctor's list carries it verbatim, and each message that
    sends an owner there for the legacy log says it."""
    import json
    import sys

    sys.path.insert(0, str(PLUGIN))
    from lib import coverage, init_product  # noqa: PLC0415

    doctor = (PLUGIN / "skills" / "doctor" / "SKILL.md").read_text(encoding="utf-8")
    assert re.search(rf"^\d+\. \*\*{re.escape(LEGACY_LOG_CHECK)}\*\*", doctor, re.M)
    assert LEGACY_LOG_CHECK in coverage._MOVE_ONTO_FRAGMENTS
    log = tmp_path / ".prawduct" / "change-log.md"
    log.parent.mkdir(parents=True)
    log.write_text("# Change Log\n", encoding="utf-8")
    assert init_product.run([str(tmp_path), "--name", "P", "--json"]) == 0
    warnings = json.loads(capsys.readouterr().out)["warnings"]
    (legacy,) = [w for w in warnings if "change-log.md" in w]
    assert LEGACY_LOG_CHECK in legacy and not ORDINAL.search(legacy)
