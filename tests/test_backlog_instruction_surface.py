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

The phantom-CAPABILITY half (added #550) carries **two blind spots of its own**,
stated here rather than only beside the code:

- **Shape, not paraphrase.** It matches a command form (``update <id> foo=bar``)
  and a verb-led prose form ("set ``foo:`` to …"). It does not match arbitrary
  wording. A real miss it did not catch: *"write it into the metadata bar as
  ``closed-by: <ref>``"* — backwards for the Issues backend, where the block IS
  the body — because the backtick span holds a value as well as a key. Widening
  to value-bearing spans was tried and rejected: `` `key: value` `` matches
  ordinary documentation constantly.
- **Backend scoping is heuristic.** ``SKILL.md`` documents both backends, and the
  writable set is the Issues adapter's, so a markdown-legitimate write
  (``accepted-by:``, ``added:``) would read as a phantom. The exemption is the
  word "markdown" within ``_MARKDOWN_WINDOW`` characters *before* the write —
  adjacency, not line-wide, because line-wide exempted ten mixed-backend lines
  outright. A markdown-scoped write further from that word than the window still
  reports, and a doc restructure that separates the scope from the instruction
  will need this revisited.
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


# --- Phantom CAPABILITIES (the sibling class of phantom guards) --------------
#
# Everything above catches an instruction surface promising a *safety mechanism*
# the adapter lacks. This section catches the sibling: a surface instructing the
# model to WRITE A FIELD no exposed op can write. Same defect shape — prose
# describing an adapter that does not exist — and the reason it needed its own
# check is that the guards above are scoped, by their own docstring, to "the
# mutation-safety family", so a capability claim sailed straight through them.
#
# It went unnoticed for the whole GitHub-Issues cutover (#550). The importer
# preserves every metadata key verbatim as a block field, one-way, while the
# ongoing write surface covered only facets, title and body — so `refs`,
# `reviewed`, `closed-by` and `accepted-by` were instructed but unwritable, and
# `update --body` made it look like it worked by returning ok and discarding the
# edit.
#
# The writable set is DERIVED, never listed here: a hand-kept list is a snapshot
# of what someone thought of, and drifts silently the moment the CLI changes.
#
# HONEST LIMIT, stated rather than implied (Principle 5) — same discipline as the
# mutation-safety half above. This catches two SHAPES of field-write instruction:
# a command form (`update <id> foo=bar`) and a verb-led prose form
# ("set `foo:` to …"). It does not catch arbitrary paraphrase. A real example it
# misses: "write it into the metadata bar as `closed-by: <ref>`" — the backtick
# span holds a value as well as the key, so the prose pattern does not fire. That
# sentence was fixed by hand, not by this guard. Widening the value-tolerant case
# was tried and rejected: `` `key: value` `` spans match ordinary documentation
# prose constantly, and a check that cries wolf trains its reader to skip the one
# real catch — the failure this module's own docstring warns about.
#
# There is a SECOND blind spot, and it is not restated here so the two cannot
# drift apart: backend scoping is heuristic (the `markdown` adjacency window
# below). Both are written out together in the module docstring — read that
# before trusting a green run to mean "no phantom capability is instructed".

# Fields with no flag of their own because a dedicated op owns them — writing
# them through `update` would bypass that op's invariants (atomic take-and-
# verify, edge symmetry, redirect-before-close). Curated for the same reason
# IMPLEMENTED_ADAPTER_GUARDS is: an unknown name must be unbacked BY DEFAULT, so
# adding one is a deliberate review moment rather than a heuristic's guess.
OP_OWNED_FIELDS: frozenset[str] = frozenset({
    "status",         # `status --to`
    "assignee",       # `claim` / `unclaim` (the API identity, never caller-supplied)
    "claimed_at",     # stamped by `claim`, cleared by `unclaim`
    "related",        # `link` / `unlink`
    "superseded_by",  # `merge`
})

# Tokens that match the `field=value` shape without being item fields at all.
_NOT_ITEM_FIELDS: frozenset[str] = frozenset({
    "repo", "to", "edge", "from", "archive", "restructure", "plan", "out",
    "limit", "page", "per-page", "sort", "direction", "state", "assignee-filter",
    "type", "scope", "chunks", "id", "key", "value", "name", "owner",
    # Syntax placeholders, not field names: the `update` heading is literally
    # spelled `update PFX-XXXX <field=value>`.
    "field",
})

# "set `refs:` …" / "stamp `reviewed:` …" — a field write asserted in prose.
_PROSE_FIELD_WRITE = re.compile(
    r"\b(?:set|sets|setting|stamp|stamps|record|records|write|writes)\b[^.\n]{0,80}?"
    r"`(?P<f>[a-z][a-z0-9_-]*):`"
)
# "update <id> closed-by=<scope>" — a field write asserted as a command form.
_COMMAND_FIELD_WRITE = re.compile(r"(?<![\w-])(?P<f>[a-z][a-z0-9_-]{2,})=")
_UPDATE_FORM = re.compile(r"\bupdate\b\s+(?:`)?(?:PFX-XXXX|<id>|&lt;id&gt;)")


def _writable_field_names() -> frozenset[str]:
    """Every field name the adapter can actually write, derived from the CLI.

    A flag reaches `_parse_flags` only as a real string literal in its `valued=`
    / `boolean=` set, so the CLI's non-docstring literals ARE the flag
    vocabulary — the same authoritative signal `_cli_string_literals` already
    relies on for evasion 1, reused rather than re-derived.
    """
    return frozenset(_cli_string_literals()) | OP_OWNED_FIELDS


# SKILL.md is the DUAL-BACKEND file, and the writable set derived above is the
# Issues adapter's. A line that explicitly scopes itself to the markdown backend
# is therefore judged against the wrong vocabulary: `accepted-by:`, `closes:` and
# `added:` are legitimate markdown metadata-bar writes and phantom Issues ones.
# Today nothing false-positives, but only by luck of phrasing — so scope it
# rather than wait for the misfire (cumulative R-8).
#
# Deliberately a NAMED-BACKEND check, not a heuristic: the prose has to say
# "markdown" to be exempt, which keeps the default "this is an Issues claim" and
# makes the exemption visible in the text a reader is already looking at.
#
# ADJACENCY, not line-wide — the same correction `_is_denied` already carries for
# negations, and for the same reason. A line-wide test exempted TEN SKILL.md
# lines outright, including the ~1,300-char `update` paragraph and the Issues
# claim rule: both mention markdown *somewhere* while stating Issues-side
# behaviour, and both are precisely where a future phantom Issues capability
# would land. Scoping to a window means a mixed-backend line still gets scanned,
# and only the clause actually next to the word "markdown" is exempt.
_MARKDOWN_WINDOW = 90
_MARKDOWN_SCOPED = re.compile(r"\bmarkdown\b", re.I)


def _is_markdown_scoped(line: str, match_start: int) -> bool:
    """True when 'markdown' sits close enough before this write to be scoping it."""
    window = line[max(0, match_start - _MARKDOWN_WINDOW) : match_start]
    return bool(_MARKDOWN_SCOPED.search(window))


def _instructed_field_writes(surfaces=None) -> list[tuple[str, str]]:
    """``(field, "path:lineno: line")`` for every field write an instruction asserts."""
    found: list[tuple[str, str]] = []
    for surface in surfaces if surfaces is not None else SURFACES:
        for lineno, line in enumerate(
            surface.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not _in_adapter_context(surface, line):
                continue
            names = {
                m.group("f")
                for m in _PROSE_FIELD_WRITE.finditer(line)
                if not _is_markdown_scoped(line, m.start())
            }
            if _UPDATE_FORM.search(line):
                names |= {
                    m.group("f")
                    for m in _COMMAND_FIELD_WRITE.finditer(line)
                    if not _is_markdown_scoped(line, m.start())
                }
            # `relative_to` raises for a path outside PLUGIN, which the
            # discrimination fixtures below deliberately are.
            try:
                rel = surface.relative_to(PLUGIN).as_posix()
            except ValueError:
                rel = surface.name
            for name in sorted(names - _NOT_ITEM_FIELDS):
                found.append((name, f"{rel}:{lineno}: {line.strip()[:110]}"))
    return found


def test_surfaces_instruct_no_unwritable_field():
    """A surface must not tell the model to set a field no op can write.

    The phantom-CAPABILITY class. `update --body` accepts an edited block and
    silently discards it (`_body_update_preserving_block` re-appends the old one
    by design), so an instruction to set an unwritable field does not fail — it
    reports success and changes nothing, which is the worst available outcome.
    """
    writable = _writable_field_names()
    offenders = [
        where for field, where in _instructed_field_writes() if field not in writable
    ]
    assert not offenders, (
        "A backlog instruction surface tells the model to set a field the adapter "
        "cannot write. `update` writes only its declared flags; everything else in "
        "the prawduct: block is import-only, and a --body edit carrying the field "
        "is silently discarded. Either add the flag (lib/backlog/cli.py + core.py) "
        "or redirect the instruction to the op that owns the field (#550).\n  - "
        + "\n  - ".join(offenders)
    )


def test_the_capability_guard_actually_discriminates(tmp_path):
    """The guard must FAIL on a surface claiming an unwritable field.

    Without this, the check above passes just as happily when its regexes match
    nothing at all — and a guard that cannot fail is indistinguishable from one
    that is working. `added` is the fixture's phantom because it is a real block
    field that is deliberately NOT writable (native `created_at` answers it), so
    the fixture tests the actual predicate rather than a nonsense token.
    """
    fixture = tmp_path / "SKILL.md"
    fixture.write_text(
        "Run `prawduct-hook backlog update <id>` and always set `added:` to today.\n",
        encoding="utf-8",
    )
    caught = [
        f for f, _ in _instructed_field_writes([fixture])
        if f not in _writable_field_names()
    ]
    assert "added" in caught, (
        "the phantom-capability guard did not flag a surface instructing an "
        "unwritable field — it is matching nothing and would pass on a real one"
    )


def test_the_capability_guard_does_not_flag_a_writable_field(tmp_path):
    """The other half: it must stay silent on a field that IS writable, or the
    real check would be noise the next reader learns to ignore."""
    fixture = tmp_path / "SKILL.md"
    fixture.write_text(
        "Run `prawduct-hook backlog update <id>` and set `refs:` to the design doc.\n",
        encoding="utf-8",
    )
    assert [
        f for f, _ in _instructed_field_writes([fixture])
        if f not in _writable_field_names()
    ] == []


# --- The prose enumeration must match the derived set ------------------------

# Bounded at the SENTENCE, not the line: the surrounding paragraph goes on to
# discuss `--body` (which is a real flag, but not a block field), and a
# to-end-of-line span swept it in and reported a disagreement that was the
# regex's fault rather than the prose's. A false alarm here is worse than none —
# it is the "probe that misfires trains its reader to ignore it" failure this
# module's own docstring names.
_WRITABLE_PROSE = re.compile(r"block fields are writable[^.]*")


def test_skill_prose_field_list_matches_the_derived_writable_set():
    """SKILL.md states the writable block fields in prose; that list must be true.

    The guards above check that no instruction names an UNWRITABLE field. They do
    not check the converse — a sentence enumerating "only these are writable"
    carries a closed-world claim, and nothing binds it to the CLI. Add a fifth
    flag and that sentence becomes silently false, which is precisely the drift
    class this whole file exists to close, one level up (cumulative R-7).

    The expected set is DERIVED from `core._UPDATE_BLOCK` plus the boolean
    `reviewed`, never restated here — restating it would reproduce the defect
    inside its own guard.
    """
    import sys

    if str(PLUGIN) not in sys.path:
        sys.path.insert(0, str(PLUGIN))
    from lib.backlog import core  # noqa: PLC0415 — path set above

    expected = {f"--{name}" for name in core._UPDATE_BLOCK} | {"--reviewed"}
    skill = (PLUGIN / "skills" / "backlog" / "SKILL.md").read_text(encoding="utf-8")
    claims = _WRITABLE_PROSE.findall(skill)
    assert claims, (
        "SKILL.md no longer states which block fields are writable — if the "
        "sentence moved, retarget this guard; if it was deleted, the skill lost "
        "the one place a reader learns the write surface"
    )
    for claim in claims:
        named = set(re.findall(r"`(--[a-z-]+)`", claim))
        assert named == expected, (
            f"SKILL.md's writable-field list {sorted(named)} disagrees with the "
            f"adapter's actual set {sorted(expected)} — update the prose, or the "
            "closed-world claim 'only these are writable' is false"
        )


def test_a_markdown_scoped_line_is_exempt_but_an_issues_one_is_not(tmp_path):
    """R-8's scoping must cut exactly one way.

    A markdown-backend line naming `added:` is legitimate; the identical claim
    without that scope is a phantom Issues capability. Both directions are pinned
    because an exemption that swallows the unscoped case would silently disable
    the guard for every line that happens to say "markdown".
    """
    exempt = tmp_path / "a.md"
    exempt.write_text(
        "Run `prawduct-hook backlog update <id>`. On the markdown backend, set `added:` to today.\n",
        encoding="utf-8",
    )
    assert [f for f, _ in _instructed_field_writes([exempt])] == []

    caught = tmp_path / "b.md"
    caught.write_text(
        "Run `prawduct-hook backlog update <id>` and set `added:` to today.\n",
        encoding="utf-8",
    )
    assert "added" in [f for f, _ in _instructed_field_writes([caught])]


def test_a_mixed_backend_line_is_still_scanned(tmp_path):
    """R-8's exemption must be adjacency-scoped, not line-wide.

    SKILL.md's real lines state markdown and Issues behaviour in one long
    paragraph. A line-wide exemption left ten of them — including the `update`
    paragraph and the claim rule, exactly where a phantom Issues capability would
    land — entirely unscanned. This pins the shape that actually occurs, not just
    the short synthetic one.
    """
    mixed = tmp_path / "SKILL.md"
    mixed.write_text(
        "Run `prawduct-hook backlog update <id>`. On the markdown backend the bar "
        "carries `accepted-by:`; on this backend the block is the body, there is no "
        "metadata bar, and the ship handle rides along. Always set `added:` to today "
        "so the sweep can rank it.\n",
        encoding="utf-8",
    )
    caught = [
        f for f, _ in _instructed_field_writes([mixed])
        if f not in _writable_field_names()
    ]
    assert "added" in caught, (
        "a field write far from the word 'markdown' was exempted anyway — the "
        "scope is line-wide again, and the mixed-backend lines that make up most "
        "of SKILL.md are unscanned"
    )
    # NOT asserting `accepted-by` is absent here: the fixture's verb ("carries")
    # is not in `_PROSE_FIELD_WRITE`'s list and there is no `foo=` form, so that
    # field can never be emitted from this line — the assertion would pass with
    # the exemption present, absent, or inverted. Vacuous, so it is gone; the
    # exempt direction is genuinely covered by
    # `test_a_markdown_scoped_line_is_exempt_but_an_issues_one_is_not`, whose
    # fixture uses a real write verb.
