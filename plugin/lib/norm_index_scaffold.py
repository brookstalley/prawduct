"""Leftover scaffold rows in a product's preferences norm index (#570).

`#567` made `probe_norm_health_sweep_overdue` treat a populated Enforcement
norm row as a homed norm, and the resulting over-fire was fixed by shipping
`templates/project-preferences.md` with that table **empty**. That fix reaches
**new onboards only**: `init_product` and `core.write_template` skip existing
destinations, so every already-onboarded repo keeps the two illustrative rows
the template used to ship — rows whose `Audit home` / `Why` cells are non-empty
placeholders. Those repos therefore read as having a ratified norm registry and
get nudged about a Norm Health sweep they owe nothing to.

**Detection is exact-match against the rows prawduct actually shipped**, not a
heuristic for placeholder-shaped text. Sniffing for italics-in-parentheses was
considered and rejected when the same choice arose in `#567`: it bakes a
formatting convention into a governance predicate, and a real norm's *why* may
legitimately be italic. Matching what we shipped cannot mistake an authored row
for a scaffold one. The two row strings are byte-identical across the whole
template lineage (verified back through the `plugin/` move), so the exact set
is small, closed, and complete.

Shape mirrors :mod:`lib.learnings_obligation` — the established pattern for a
defect that lives in already-onboarded repos and that a template change cannot
reach: report a status, offer a repair, never apply it unasked. This edits a
product's own authored preferences file, so the repair is **delete-only** and
touches nothing but the scaffold rows themselves.
"""

from __future__ import annotations

from pathlib import Path

from . import core

PREFERENCES_REL = ".prawduct/artifacts/project-preferences.md"

# The rows the template shipped, verbatim. Compared after stripping trailing
# whitespace only — an editor that trimmed line ends must still be recognised,
# but any edit to the row's CONTENT means a human touched it and it is theirs.
SCAFFOLD_ROWS = (
    "| *(a code-level convention)* | Test | `tests/preferences/test_*.py` | janitor | "
    "*(the constraint's rationale)* |",
    "| norm lives in `observability-strategy.md` § Direction | Critic | — | advisory | "
    "*(pointer row — the why lives in the Direction entry)* |",
)

STATUS_OK = "ok"
STATUS_LEFTOVER = "leftover"
STATUS_ABSENT = "absent"
STATUS_UNREADABLE = "unreadable"


def _read_text(path: Path) -> str | None:
    """File text, or None when it cannot be decoded as utf-8.

    A missing file and an undecodable one are different answers and the caller
    distinguishes them, so this returns None only for the latter; existence is
    checked separately.

    ``newline=""`` disables universal-newline translation. Without it a CRLF
    file is read as ``\n``-only and the repair writes it back that way — the
    delete-only guarantee would hold line-by-line while silently re-line-ending
    every line in a product's authored file. ``str.splitlines`` still splits on
    ``\r\n``, and the row comparison rstrips, so detection is unaffected.
    """
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return None


def _scaffold_line_numbers(text: str) -> list[int]:
    """1-based line numbers of every shipped scaffold row present."""
    wanted = {row.rstrip() for row in SCAFFOLD_ROWS}
    return [
        idx
        for idx, line in enumerate(text.splitlines(), start=1)
        if line.rstrip() in wanted
    ]


def check(project_dir: str | Path) -> dict:
    """Report leftover scaffold rows in the preferences norm index.

    Returns ``{status, path, rows, detail}``. ``rows`` is the 1-based line
    numbers of the scaffold rows found, so the report can name them rather than
    telling the owner to go looking.

    ``unreadable`` is deliberately its own status rather than folding into
    ``absent``: a check that could not run must never be reported as one that
    ran and found nothing (`architecture.md` § Direction — advice degrades to a
    note, and a degraded path must still name its consequence).
    """
    path = Path(project_dir) / PREFERENCES_REL
    if not path.is_file():
        return {
            "status": STATUS_ABSENT,
            "path": str(path),
            "rows": [],
            "detail": "no project-preferences.md — nothing to inspect",
        }
    text = _read_text(path)
    if text is None:
        return {
            "status": STATUS_UNREADABLE,
            "path": str(path),
            "rows": [],
            "detail": "project-preferences.md is not decodable utf-8 — check declined",
        }
    rows = _scaffold_line_numbers(text)
    if not rows:
        return {
            "status": STATUS_OK,
            "path": str(path),
            "rows": [],
            "detail": "no shipped scaffold rows remain in the norm index",
        }
    return {
        "status": STATUS_LEFTOVER,
        "path": str(path),
        "rows": rows,
        "detail": (
            f"{len(rows)} template scaffold row(s) still in the norm index "
            f"(line{'s' if len(rows) > 1 else ''} {', '.join(str(r) for r in rows)}) — "
            "they read as homed norms, so this repo is nudged about a Norm Health "
            "sweep it owes nothing to"
        ),
    }


def repair(project_dir: str | Path, *, apply: bool = False) -> dict:
    """Offer — and on ``apply`` perform — removal of the scaffold rows.

    **Delete-only, and only the rows in :data:`SCAFFOLD_ROWS`.** Every other
    line is written back byte-for-byte in its original order; nothing is
    reformatted, reordered or re-line-ended. This is a product's authored file,
    so the repair does the least it can and the owner confirms it
    (`architecture.md` § Direction — the plugin writes into a governed repo only
    what it must reconcile).
    """
    state = check(project_dir)
    if state["status"] != STATUS_LEFTOVER:
        return {**state, "applied": False, "removed": 0}
    path = Path(state["path"])
    text = _read_text(path)
    if text is None:  # raced with an edit between check and repair
        return {
            "status": STATUS_UNREADABLE,
            "path": str(path),
            "rows": [],
            "detail": "became undecodable between check and repair — nothing written",
            "applied": False,
            "removed": 0,
        }
    wanted = {row.rstrip() for row in SCAFFOLD_ROWS}
    kept = [line for line in text.splitlines(keepends=True) if line.rstrip() not in wanted]
    removed = len(text.splitlines()) - len(kept)
    if not apply:
        return {
            **state,
            "applied": False,
            "removed": removed,
            "detail": (
                f"{state['detail']}. Dry run: `--apply` would delete "
                f"{removed} row(s) and change nothing else."
            ),
        }
    # newline="" so the file's own line endings survive untouched; utf-8
    # because every reader of a product artifact opens utf-8.
    core.atomic_write_text(path, "".join(kept), encoding="utf-8", newline="")
    return {
        "status": STATUS_OK,
        "path": str(path),
        "rows": [],
        "detail": f"removed {removed} template scaffold row(s) from the norm index",
        "applied": True,
        "removed": removed,
    }
