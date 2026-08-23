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
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugin"
CLI_PATH = PLUGIN / "lib" / "backlog" / "cli.py"
ADAPTER_DIR = PLUGIN / "lib" / "backlog"

# The adapter itself is one of the two things this file compares: several checks
# below assert that a surface's claim matches what the CLI actually does, which
# means importing it rather than re-reading its source into a second opinion.
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))

import pytest  # noqa: E402

from lib.backlog import cli  # noqa: E402

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


# --- the altitude question (issue-standard §1 / discovery §4c) ---------------
#
# Not a phantom-guard check like the rest of this file, but the same shape of
# hazard: an instruction surface that omits a step the standard depends on.

_ALTITUDE_SURFACES = ("SKILL.md", "migration-scrub.md")


def test_dedup_surfaces_ask_the_shared_root_cause_question():
    """The co-ship condition on the §1 title enforcement (#614).

    Enforcing "≤72, atomic" WITHOUT this question makes the backlog worse in a
    specific way: a scrub rewriting titles item-by-item cannot see that three
    issues are one defect, and rewriting each to a *tighter* symptom title
    entrenches the split, because a sharper title reads more like a well-formed
    issue. Over-splitting is the more expensive direction — a split backlog looks
    more thorough, so nothing prompts a re-read.

    No per-title lint can catch it: it is a fact *between* issues. The dedup
    sweep and the migration scrub are the only places it can live, which is why
    both are pinned rather than one. The existing grouping is a *duplicate* test
    (title-keyword + body overlap) and the two come apart exactly where it
    matters — `crash on emoji` and `crash on UTF-16` share a cause and almost no
    keywords.
    """
    missing = []
    for rel in _ALTITUDE_SURFACES:
        text = (_BACKLOG_SKILL_DIR / rel).read_text(encoding="utf-8").lower()
        # The question itself, however it is punctuated, plus the name of the
        # test it encodes — a surface carrying only one of the two has kept the
        # words and lost the instruction, or vice versa.
        asks = "would a single change close all of these" in text
        names = "shared-root-cause" in text or "shared root cause" in text
        if not (asks and names):
            missing.append(f"{rel} (asks={asks}, names_the_test={names})")

    assert not missing, (
        "A dedup/scrub surface no longer asks the altitude question. This is the "
        "co-ship condition the owner attached to §1 title enforcement: shipping "
        "the length/shape half alone uses the window to build a large, tidy, "
        "OVER-SPLIT backlog that then has to be merged back by hand. Restore it "
        "rather than relaxing this test.\n  - " + "\n  - ".join(missing)
    )


# --- the op set is discoverable, so the bound that cites it can resolve -------
#
# The whole mutation surface rests on one sentence: "the adapter exposes exactly
# the ops in the usage table." It bounded the model by REFERENCE, and for a long
# stretch the referent did not exist anywhere — `--help` answered exit 2,
# "unknown flag". A bound whose referent cannot be resolved is not a bound, and
# it fails in the worst direction: a reader who cannot find the table does not
# stop, it falls back to its own notion of the op set. So the referent is now a
# command, and these pins keep the command, the table and the sentence in step.


@pytest.mark.parametrize("op", cli._ALL_OPS)
def test_every_op_prints_its_own_usage_at_exit_zero(op, capsys):
    """Asked by rule over the whole dispatch surface, never by naming today's ops:
    an op added tomorrow inherits this assertion instead of quietly reopening the
    gap. Help is a request that SUCCEEDED — stdout, exit 0 — because a reader
    discovering the surface is the intended use, and an error exit teaches the
    opposite."""
    code = cli.run(".", [op, "--help"])
    captured = capsys.readouterr()

    assert code == 0, f"`backlog {op} --help` exited {code}: {captured.err.strip()!r}"
    assert f"prawduct-hook backlog {op}" in captured.out, (
        f"`backlog {op} --help` printed no usage for {op!r} on stdout"
    )


def test_the_usage_table_covers_every_dispatched_op():
    """The table is composed from the same dict `--help` serves, so this catches
    the one way they can still come apart: an op dispatched by `run` with no
    entry to render."""
    unserved = [op for op in cli._ALL_OPS if cli._op_usage(op) is None]
    assert not unserved, (
        f"{unserved} are dispatched but have no usage entry, so `--help` cannot "
        "describe them and any surface bounding a reader to the usage table "
        "under-reports the op set"
    )


def test_a_bare_help_renders_the_whole_table(capsys):
    code = cli.run(".", ["--help"])
    captured = capsys.readouterr()

    assert code == 0
    missing = [op for op in cli._ALL_OPS if op not in captured.out]
    assert not missing, f"the usage table does not name {missing}"


_OP_SET_BOUND = re.compile(
    r"exposes exactly the ops|the ops in the usage table", re.I
)
#: The referent that resolves: a command the reader can run, not a document to
#: go looking for.
_RESOLVABLE_REFERENT = "backlog --help"


def _bounding_citations() -> list[tuple[str, str]]:
    """Every line that bounds a reader to the adapter's op set, paired with a
    two-line window (the citation is free to wrap)."""
    found: list[tuple[str, str]] = []
    for surface in SURFACES:
        lines = surface.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, 1):
            if not _in_adapter_context(surface, line):
                continue
            if _OP_SET_BOUND.search(line):
                rel = surface.relative_to(PLUGIN).as_posix()
                found.append((f"{rel}:{lineno}", " ".join(lines[lineno - 1 : lineno + 1])))
    return found


def test_the_op_set_bound_cites_something_that_resolves():
    citations = _bounding_citations()
    assert citations, (
        "no instruction surface bounds the reader to the adapter's op set any "
        "more. That sentence is the only thing standing between a model and an "
        "invented mutation path — restore it, with its referent."
    )
    dangling = [ref for ref, window in citations if _RESOLVABLE_REFERENT not in window]
    assert not dangling, (
        "an instruction surface bounds the reader by 'the ops in the usage "
        f"table' without naming `prawduct-hook {_RESOLVABLE_REFERENT}`, the "
        "command that prints it. A reference a reader cannot resolve is not a "
        f"bound.\n  - " + "\n  - ".join(dangling)
    )


# --- the retry budget: bounded, or it is not a budget ------------------------
#
# `retryable: true` says re-attempting CAN work. It never said how often, so a
# run of GitHub 503s met a caller that retried 23 times across 5+ minutes. The
# adapter is innocent: a single op runs `gh` once and returns immediately, so
# the loop only ever existed in the caller — which is precisely why the bound
# has to be published where the caller reads, and why every surface that hands
# out the hint owes the budget beside it.

_RETRY_BUDGET_SIGNALS = {
    "a maximum attempt count": re.compile(
        rf"attempts?\b[^\n]{{0,24}}\b{cli.RETRY_MAX_ATTEMPTS}\b"
        rf"|\b{cli.RETRY_MAX_ATTEMPTS}\b[^\n]{{0,24}}attempts?",
        re.I,
    ),
    "a deadline": re.compile(rf"\b{cli.RETRY_DEADLINE_SECONDS}\s?s(?:econds)?\b", re.I),
    "a give-up rule": re.compile(r"give[s]? up", re.I),
}


def _retryable_surfaces() -> list[Path]:
    """Surfaces that hand the reader the `retryable` hint."""
    return [
        s for s in SURFACES if "retryable" in s.read_text(encoding="utf-8")
    ]


def test_every_surface_that_hands_out_retryable_also_bounds_the_retrying():
    surfaces = _retryable_surfaces()
    assert surfaces, "no surface documents `retryable` any more — check the derivation"
    missing: list[str] = []
    for surface in surfaces:
        text = surface.read_text(encoding="utf-8")
        for what, pattern in _RETRY_BUDGET_SIGNALS.items():
            if not pattern.search(text):
                missing.append(f"{surface.relative_to(PLUGIN).as_posix()}: no {what}")
    assert not missing, (
        "a surface tells a reader an error is `retryable` without bounding the "
        "retrying. The budget is the caller's whole ceiling — no adapter code "
        "enforces it, because a single op makes one call and returns — so a "
        "surface that omits it hands out a licence to loop.\n  - "
        + "\n  - ".join(missing)
    )


def test_the_help_output_carries_the_budget_it_publishes():
    """`--help` is the referent the bound points at, so it is where a reader
    lands with no other context. The numbers come from the CLI's own constants,
    which is what keeps the command and the prose from drifting apart."""
    for what, pattern in _RETRY_BUDGET_SIGNALS.items():
        assert pattern.search(cli._HELP), f"the usage table states no {what}"


# --- the `prawduct:` block is the adapter's to write -------------------------

_BLOCK_OWNERSHIP = re.compile(r"adapter[- ]owned", re.I)
_BLOCK_PROHIBITION = re.compile(r"(?:do not|don't|never)\s+hand[- ]writ", re.I)


def test_the_prawduct_block_is_declared_adapter_owned_and_off_limits():
    """Ownership stated without a prohibition is a preference, and a preference
    is what a skill overrode when it hand-wrote a block: the adapter's composer
    strips the attribution stamps from any embedded block in both directions, so
    a hand-written one is at best redundant and at worst a field nothing reads.
    Both halves are required — the fact and the instruction."""
    text = (_BACKLOG_SKILL_DIR / "adapter-mode.md").read_text(encoding="utf-8")
    assert _BLOCK_OWNERSHIP.search(text), (
        "adapter-mode.md no longer states that the `prawduct:` block is "
        "adapter-owned; a reader with no owner for it will write one"
    )
    assert _BLOCK_PROHIBITION.search(text), (
        "adapter-mode.md states the ownership but no longer prohibits "
        "hand-writing a block — ownership alone reads as a preference"
    )


# --- a close records no scope, and no surface may say it does ----------------


def _status_valued_flags() -> set[str]:
    """The flags `status` actually parses, read off `_run_status`'s own
    `_parse_flags(valued=…)` call. Derived rather than typed here so the day the
    op learns `--closed-by` this check stands down by itself."""
    tree = ast.parse(CLI_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_run_status":
            for inner in ast.walk(node):
                if (
                    isinstance(inner, ast.Call)
                    and getattr(inner.func, "id", None) == "_parse_flags"
                ):
                    for kw in inner.keywords:
                        if kw.arg == "valued":
                            return {
                                elt.value
                                for elt in kw.value.elts
                                if isinstance(elt, ast.Constant)
                            }
    raise AssertionError(
        "`_run_status` no longer parses its flags through `_parse_flags(valued=…)`; "
        "this check reads that call to learn what a close can record"
    )


_CLOSED_BY_CLAIMS = (
    re.compile(r"records?\s+(?:the\s+)?`?closed[_-]by", re.I),
    re.compile(r"closed[_-]by`?\s+(?:is\s+)?(?:recorded|stamped|native)", re.I),
)


def test_no_surface_claims_a_close_records_the_closed_by_scope():
    """The skill-facing contract accepts `closed-by=<scope>` on a close, and the
    op it routes to has nowhere to put it: the scope is dropped, silently. The
    code has always been honest — `set_status` records the deferral in its own
    docstring — so this pins the only layer that overstated it, against the flag
    set the op really parses."""
    if "closed-by" in _status_valued_flags():
        return  # the op learned the flag; the claim is then true

    def _find(line: str):
        hits = [m.start() for p in _CLOSED_BY_CLAIMS if (m := p.search(line))]
        return min(hits) if hits else None

    offenders = _offending_lines(_find)
    assert not offenders, (
        "a backlog instruction surface says a close records `closed_by`. The "
        "`status` op parses only "
        f"{sorted(_status_valued_flags())}, so a `closed-by=<scope>` argument is "
        "dropped — and a caller told otherwise loses the traceability it asked "
        "for without ever seeing a failure. Say the scope is not recorded, and "
        "where to put it instead.\n  - " + "\n  - ".join(offenders)
    )
