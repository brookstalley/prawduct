"""Every reader of the build plan decodes it the same way, and fails the same way.

A preference pin, not a unit test. The rule it enforces was a convention for
five consecutive Critic rounds and lost every one: six of seven reads in a
module, then two more outside it, then the except-set axis nobody had swept,
then a twelfth reader, then a thirteenth sixty-eight lines below the twelfth.
Each sweep reached exactly as far as the unit being edited, because a boundary
you are inside is invisible.

The risk is NOT that a plan fails to decode; PEP 538/540 coerce C/POSIX to UTF-8
on Linux and macOS, so reachability is narrow. The risk is DISAGREEMENT —
readers of the same file answering differently about whether it parses. Two axes
produce it, and sweeping one leaves the class open:

* the **codec** — a bare ``read_text()`` uses the operator's locale, so one
  reader decodes a plan another cannot;
* the **except-set** — ``UnicodeDecodeError`` is a ``ValueError``, NOT an
  ``OSError``, so ``except OSError`` lets it escape. That turned
  ``verify-chunk-refs``' documented ``cannot-verify:`` exit and ``regen-views``
  into tracebacks, across a boundary whose recorded ``api_error_model_approach``
  says no internal stack trace may cross it.

**Two mechanisms, because each covers the other's blind spot.** The predecessor
of this file matched one local-name idiom (``plan_path.read_text(``) and so was
blind to two readers that spelled it ``path`` — a limitation this file's own
prose once *documented* while the sweep it called for went undone. So:

1. **File-scoped and exhaustive** over the modules whose job IS the build plan
   (``lib/buildplan_refs.py``, ``lib/plan_index.py``). Every ``read_text`` in them,
   whatever the local is called. No naming convention to drift from.
2. **Data-flow** for readers outside those modules: any read whose content is
   passed to a build-plan parser. Catches ``critic_mode`` and ``ledger``
   without dragging in their unrelated JSON reads (those are ROB-7T2N).

Neither is complete alone; the union has no known gap. Related backlog item:
ROB-7T2N — the same class across the ~67 other runtime reads, deliberately out
of scope here.
"""

from __future__ import annotations

import ast
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent.parent / "plugin"

# Modules that exist to read the build plan — swept exhaustively (mechanism 1).
PLAN_MODULES = (
    "lib/buildplan_refs.py",
    "lib/plan_index.py",  # the scope→plan resolver; every plan read now lands here
)

# Functions that consume build-plan text. A read feeding one of these IS a
# build-plan read, whatever its local is called (mechanism 2).
PLAN_PARSERS = frozenset(
    {
        "parse_build_plan_frontmatter_scope",
        "frontmatter_lines",
        "_iter_status_section_lines",
        "_iter_status_section_items",
        "_chunk_section_lines",
        "_resolve_chunk_progress_from",
        "_chunk_id_from_item_text",
    }
)


class _Read:
    __slots__ = ("rel", "lineno", "func", "encoded", "guard")

    def __init__(self, rel, lineno, func, encoded, guard):
        self.rel, self.lineno, self.func = rel, lineno, func
        self.encoded, self.guard = encoded, guard

    def __repr__(self) -> str:
        return f"{self.rel}:{self.lineno} ({self.func})"


def _read_calls(node: ast.AST) -> list[ast.Call]:
    return [
        n
        for n in ast.walk(node)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "read_text"
    ]


def _guard_for(func: ast.AST, call: ast.Call) -> str | None:
    """The ``except`` clause guarding ``call``, or None if unguarded.

    Walks the enclosing ``try`` however far away it is, which the earlier
    three-line-lookahead probe could not — that limitation forced a documented
    exemption for a read guarded 74 lines below itself.
    """
    for tryblock in [n for n in ast.walk(func) if isinstance(n, ast.Try)]:
        if any(call is c for stmt in tryblock.body for c in _read_calls(stmt)):
            return " | ".join(
                ast.unparse(h.type) if h.type else "bare" for h in tryblock.handlers
            )
    return None


def _plan_reads() -> list[_Read]:
    out: list[_Read] = []
    for path in sorted(PLUGIN.rglob("*.py")):
        rel = path.relative_to(PLUGIN).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        in_plan_module = rel in PLAN_MODULES
        for func in [
            n
            for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]:
            consumed: set[str] = set()
            for n in ast.walk(func):
                if isinstance(n, ast.Call):
                    f = n.func
                    name = (
                        f.id
                        if isinstance(f, ast.Name)
                        else (f.attr if isinstance(f, ast.Attribute) else None)
                    )
                    if name in PLAN_PARSERS:
                        for arg in n.args:
                            consumed |= {
                                s.id for s in ast.walk(arg) if isinstance(s, ast.Name)
                            }
            for call in _read_calls(func):
                if not in_plan_module:
                    # Mechanism 2: only reads whose content reaches a parser.
                    assigned: set[str] = set()
                    for n in ast.walk(func):
                        if isinstance(n, ast.Assign) and any(
                            c is call for c in _read_calls(n.value)
                        ):
                            assigned |= {
                                t.id for t in n.targets if isinstance(t, ast.Name)
                            }
                    if not (assigned & consumed):
                        continue
                out.append(
                    _Read(
                        rel,
                        call.lineno,
                        func.name,
                        any(k.arg == "encoding" for k in call.keywords),
                        _guard_for(func, call),
                    )
                )
    return out


def test_the_pin_has_something_to_check():
    """Guard the guard: a refactor must not silently empty this file's coverage.

    The floor moved 12 -> 11 when the derived-view module was deleted, and the
    membership assertion below is the reason that is a retune rather than a
    weakening: it requires EVERY listed module to contribute a read, so a
    module going silent fails here regardless of what the count says. The
    count alone would have been satisfied by any eleven reads.

    Three parser names left `PLAN_PARSERS` in the same change — the two Status
    view builders and the pre-split private frontmatter alias — because the
    functions no longer exist anywhere in `plugin/`. A name that can never match
    inflates the vocabulary without widening the sweep, which is how this pin
    reads as broader than it is.
    """
    reads = _plan_reads()
    modules = {r.rel for r in reads}
    assert len(reads) >= 11, f"only {len(reads)} build-plan reads matched: {reads}"
    assert set(PLAN_MODULES) <= modules, f"a plan module contributed nothing: {modules}"


def test_every_build_plan_read_names_utf8():
    offenders = [r for r in _plan_reads() if not r.encoded]
    assert not offenders, (
        f"{offenders} decode the build plan with the operator's locale codec. "
        'Pass encoding="utf-8" so every reader of the file agrees on what it says.'
    )


def test_every_guarded_build_plan_read_catches_unicode_decode_error():
    """A read guarded at all must catch what it can actually raise.

    An *unguarded* read is out of scope — that is a deliberate let-it-propagate
    choice and this pin does not second-guess it. A read guarded by a broad
    ``except Exception`` further out already catches ``UnicodeDecodeError``, so
    it passes on its merits rather than by exemption.
    """
    offenders = [
        f"{r} -> except {r.guard}"
        for r in _plan_reads()
        if r.guard is not None
        and "UnicodeDecodeError" not in r.guard
        and "Exception" not in r.guard
    ]
    assert not offenders, (
        f"{offenders} catch OSError but not UnicodeDecodeError, which is a "
        "ValueError and escapes. Catch (OSError, UnicodeDecodeError) so the "
        "designed degradation actually runs."
    )
