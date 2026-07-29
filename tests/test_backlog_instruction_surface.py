"""Guard: the backlog adapter's instruction surfaces never promise a safety
mechanism the adapter does not implement (BKL-8V3D, hardened by CRT/cumulative
2026-07-24).

`skills/backlog/adapter-mode.md` once told the model that "mutations follow the
adapter's own ``--apply``/dry-run … contracts (you never invent a mutation
path)" — but ``lib/backlog/`` implements no such flag. The hazard is not
cosmetic: a migration/scrub run then walks a write path *believing a dry-run
guarded it* (BKL-2Q7F's 100–250-real-issues blast radius). The real
preview-before-write is ``restructure-preview`` — a distinct op — never a
per-mutation flag.

**Why this file was hardened.** The first version pinned the *flag token* family
only, and the very branch that shipped it introduced a **second** phantom claim
of the same class that the guard could not see: `skills/backlog/SKILL.md` told
the model the migration's primary guard was "the adapter's target-pin", a
mechanism that does not exist anywhere in ``lib/backlog/`` and that Chunk 02
explicitly deferred. A guard that catches the instance it was written for and
misses the next instance of the same class is not a class guard. Four concrete
evasions were found and are each closed below:

1. **Whole-file substring on ``cli.py``** — a *comment or docstring* mentioning
   ``--apply`` made ``_cli_parses`` true and disabled the check globally. Now the
   CLI is parsed with :mod:`ast` and only **non-docstring string literals** count,
   which is the only form argparse can actually receive a flag in.
2. **Dashless prose** — "the adapter's own dry-run contract" names the same
   phantom mechanism without ever writing ``--dry-run``. Now matched as prose.
3. **Too narrow a file set** — only ``skills/backlog/*.md`` was scanned, while
   other skills (onboard, doctor) carry ``prawduct-hook backlog`` command lines.
   The surface set is now *derived*: any plugin skill that drives the adapter.
4. **Flag tokens only, so mechanism claims slipped** — the blocking finding. Now
   a named-mechanism check requires each claimed adapter guard to appear in an
   explicit allowlist of mechanisms that genuinely exist. Note *why* it is an
   allowlist and not a source-token check: the source-token version was written
   first and passed, because its backing token lived in a docstring — reproducing
   evasion 1 one level up. Unknown guard names are unbacked by default.

**Honest limit, stated rather than implied (Principle 5).** Prose claims are not
fully mechanizable: this catches *named* mechanisms from a curated vocabulary, not
arbitrary paraphrase. It is deliberately scoped to the mutation-safety family — a
blanket "every ``--flag`` in the docs must be a CLI flag" false-positives on
legitimate roadmap (``--like``) and skill-frontmatter flags, and a probe that
misfires trains its reader to ignore the one real catch (`docs/norms.md`, and the
same reasoning `tests/preferences/test_no_upstream_content_egress.py` gives for
scoping). Extend the vocabularies below when a new safety mechanism is coined.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugin"
CLI_PATH = PLUGIN / "lib" / "backlog" / "cli.py"
ADAPTER_DIR = PLUGIN / "lib" / "backlog"

# Evasion 3 — derive the surface set instead of hardcoding one directory. Any
# skill markdown that drives the adapter can make a safety claim about it.
_ADAPTER_INVOCATION = re.compile(r"prawduct-hook\s+backlog\b")


def _adapter_instruction_surfaces() -> list[Path]:
    surfaces = set((PLUGIN / "skills" / "backlog").glob("*.md"))
    for md in (PLUGIN / "skills").rglob("*.md"):
        if _ADAPTER_INVOCATION.search(md.read_text(encoding="utf-8")):
            surfaces.add(md)
    return sorted(surfaces)


SURFACES = _adapter_instruction_surfaces()

# A "preview / apply before a mutation" flag is the exact shape adapter-mode.md
# over-claimed. Extend this tuple if a new mutation-safety flag is coined.
MUTATION_PREVIEW_FLAGS = ("--apply", "--dry-run")

# Evasion 2 — the same claim, spelled as prose instead of as a flag token.
PROSE_MUTATION_CLAIMS = (
    re.compile(r"adapter'?s?\s+(?:own\s+)?dry[- ]run", re.I),
    re.compile(r"dry[- ]run\s+contract", re.I),
)

# Evasion 4 — named adapter guard mechanisms.
#
# This is an EXPLICIT ALLOWLIST, not a source-token heuristic, and that choice is
# load-bearing. The first attempt mapped each guard name to a "backing token"
# that had to appear in the adapter source — and it silently passed, because
# `backlog_service_repo` appears in a *docstring* at `migrate.py:595`. That is
# the identical whole-file-substring flaw this module closes as evasion 1, so a
# heuristic backing check reproduced the very defect one level up. A curated list
# has no such failure mode: an unknown guard name is unbacked BY DEFAULT, and
# shipping a real mechanism requires deliberately adding it here — which is
# exactly the review moment that should exist.
#
# Add a name here only when the mechanism is genuinely implemented in
# lib/backlog/. Chunk 08's file-upstream pin belongs here when it lands.
IMPLEMENTED_ADAPTER_GUARDS: frozenset[str] = frozenset({"restructure-preview"})

# Guard-mechanism names that appear in prose. Anything here that is not in
# IMPLEMENTED_ADAPTER_GUARDS is a phantom claim. `target-pin` is the one that
# shipped: no repo-identity comparison exists anywhere in lib/backlog/
# (`ids.parse_repo` is shape-only at all ten call sites).
NAMED_ADAPTER_GUARDS = ("target-pin", "target pin", "restructure-preview")

# A claim is only a claim if it is asserted. Lines that *deny* the mechanism —
# which is exactly what an honest surface must be free to say — are not offenders.
#
# The negation must be looked for in a WINDOW IMMEDIATELY BEFORE the match, not
# anywhere on the line. A line-wide check was the first thing tried and it was
# worse than useless: the phantom claim this guard exists to catch reads
# "… the adapter's target-pin — not the tools list", so a line-wide search found
# "not", classified the whole line as a denial, and let the offender straight
# through. Instruction prose is dense with unrelated negations; only an adjacent
# one can plausibly be negating THIS mechanism.
_NEGATION_WINDOW = 48
_NEGATION = re.compile(
    r"\b(?:no|not|never|without|absent|does not|do not|don't|lacks?|nor)\b\s*$", re.I
)


def _is_denied(line: str, match_start: int) -> bool:
    """True when a negation sits just before the claim (so it is a denial)."""
    window = line[max(0, match_start - _NEGATION_WINDOW) : match_start]
    # Tolerate intervening adjectives/hyphenation: "no adapter-side target guard".
    return bool(_NEGATION.search(re.sub(r"[\w-]+\s*$", "", window)) or _NEGATION.search(window))


def _cli_string_literals() -> set[str]:
    """Every non-docstring string constant in the backlog CLI.

    Evasion 1 — the old check was ``flag in CLI_SOURCE``, a whole-file substring,
    so a passing mention in a comment or docstring silently satisfied it *for
    every surface at once*. argparse can only receive a flag as a real string
    literal, so that is the authoritative signal. Comments never reach the AST;
    docstrings are stripped explicitly.
    """
    tree = ast.parse(CLI_PATH.read_text(encoding="utf-8"))
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstrings.add(id(body[0].value))
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    }


_BACKLOG_SKILL_DIR = PLUGIN / "skills" / "backlog"


def _in_adapter_context(surface: Path, line: str) -> bool:
    """Whether this line is talking about the BACKLOG ADAPTER specifically.

    Inside ``skills/backlog/`` the whole file is adapter context. Elsewhere only
    lines that actually invoke the adapter count — because other skills carry
    legitimate ``--apply`` flags belonging to entirely different commands
    (``init-product --apply``, ``coverage-scaffold --apply``,
    ``audit-learnings --apply``). Scanning those files wholesale produced five
    false positives on the first run: exactly the misfiring probe this module's
    docstring warns trains its reader to ignore the one real catch.
    """
    if surface.parent == _BACKLOG_SKILL_DIR:
        return True
    return bool(_ADAPTER_INVOCATION.search(line))


def _offending_lines(finder) -> list[str]:
    """``finder(line)`` returns the match offset, or None. Offset is required so
    negation is judged adjacent to the claim rather than line-wide."""
    offenders: list[str] = []
    for surface in SURFACES:
        for lineno, line in enumerate(
            surface.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not _in_adapter_context(surface, line):
                continue
            at = finder(line)
            if at is None or _is_denied(line, at):
                continue
            rel = surface.relative_to(PLUGIN).as_posix()
            offenders.append(f"{rel}:{lineno}: {line.strip()[:120]}")
    return offenders


def _first_offset(line: str, needles) -> int | None:
    hits = [line.find(n) for n in needles if n in line]
    return min(hits) if hits else None


def test_surfaces_name_no_unparsed_mutation_flag():
    """The original BKL-8V3D guard, with evasions 1 and 3 closed."""
    parsed = _cli_string_literals()
    unbacked = [f for f in MUTATION_PREVIEW_FLAGS if f not in parsed]
    offenders = _offending_lines(lambda line: _first_offset(line, unbacked))
    assert not offenders, (
        "A backlog instruction surface names a mutation preview/apply flag the "
        "backlog CLI does not parse. The adapter has no generic --apply/--dry-run "
        "contract; the only preview-before-write is `restructure-preview`. Either "
        "the CLI must implement the flag or the surface must stop promising it "
        "(BKL-8V3D).\n  - " + "\n  - ".join(offenders)
    )


def test_surfaces_make_no_prose_dry_run_claim():
    """Evasion 2 — the flag claim spelled without ever writing the flag."""
    if "--dry-run" in _cli_string_literals():
        return  # genuinely implemented; the prose is then honest
    def _find(line: str):
        hits = [m.start() for p in PROSE_MUTATION_CLAIMS if (m := p.search(line))]
        return min(hits) if hits else None

    offenders = _offending_lines(_find)
    assert not offenders, (
        "A backlog instruction surface describes an adapter dry-run contract in "
        "prose. Writing it without the flag token does not make it true — the "
        "adapter implements no dry-run. Name `restructure-preview`, or say plainly "
        "that no preview exists for the op (BKL-8V3D).\n  - " + "\n  - ".join(offenders)
    )


def test_surfaces_claim_no_unbacked_adapter_guard():
    """Evasion 4 — the blocking finding's class: a named *mechanism*, not a flag.

    `skills/backlog/SKILL.md` claimed the migration's primary guard was "the
    adapter's target-pin". No adapter code compares repo identity, so the claim
    pointed a model at a safety net that would not catch it — the same defect
    class this whole file exists to close, one abstraction level up.
    """
    unbacked = [n for n in NAMED_ADAPTER_GUARDS if n not in IMPLEMENTED_ADAPTER_GUARDS]
    offenders = _offending_lines(lambda line: _first_offset(line.lower(), unbacked))
    assert not offenders, (
        "A backlog instruction surface names an adapter-side guard mechanism that "
        "lib/backlog/ does not implement. `ids.parse_repo` is shape-only at every "
        "call site and no adapter op consults `backlog_service_repo`, so there is "
        "no target pin to rely on — the runbook's Step 0 owner confirmation is the "
        "guard. Either build the mechanism or stop naming it (BKL-8V3D / "
        "BKL-2Q7F).\n  - " + "\n  - ".join(offenders)
    )
