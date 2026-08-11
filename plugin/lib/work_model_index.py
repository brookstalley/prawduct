"""Work model — artifact vocabulary + jurisdiction matching (pure logic).

Given a plan or prompt, answer *which governing artifacts already cover this
text's vocabulary* — the input that seeds a plan's ``governed_by:`` field with
mechanical candidates for the planner's judgment. See
:func:`jurisdiction_candidates`, which is this module's only entry point.

This module is PURE — no I/O, no environment, no Claude Code coupling. The
``prawduct-hook jurisdiction`` subcommand supplies the corpus.

**History, because it explains the shape of what is left.** These functions were
built for the *inverse* question: an orphan-term tripwire that fired pre-turn on
any salient term in a user's prompt that no artifact covered, as an external
enforcement of requirements-precede-code ("tripwire #1"). Jurisdiction matching
was the later inversion, reusing the same salience machinery so the two answers
stayed complements over one term-set.

**The tripwire was deleted 2026-08-11 by owner ruling (2026-07-12, recorded on
#257): its resolution was deletion, not a further precision fix.** It never
achieved usable precision — it fired on ordinary conversational prompts, and a
frequency floor plus a firing threshold narrowed the noise without ending it,
which is the pattern that trains a reader to ignore the one real catch.
Requirements-precede-code enforcement moved to a review-time question instead
(CRT-5M9J): the ``scope-trace:`` check now carried by both the Critic and PR
review protocols, which asks whether a capability traces to a documented
requirement and is reachable end-to-end.

The salience layer survives here because jurisdiction needs it, not because the
tripwire might return. Note what that means for precision: a defect in
:func:`_normalize` no longer produces a visible false claim, it produces a
slightly worse *ranking*. That is a real but much cheaper failure, and it is why
this module is no longer on a precision-fix footing.

**And why the 2026-07-12 ruling does not forbid fixing it anyway (#638, v3.3.4).**
That ruling declared the remaining precision work moot *because the code was
slated for deletion*. The tripwire was deleted; ``_normalize`` was not, because
:func:`jurisdiction_candidates` reads through it. The ruling's premise no longer
holds over this function, so the ruling no longer covers it — the same
premise-falsified-without-the-decision-being-wrong shape recorded at
``[[harness-only-removal-is-not-a-major]]``. What the lowered stakes DO govern is
how much machinery is warranted here: a light, measured, closed-set reduction is
in bounds; a real stemmer still is not.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from lib.common_words import WORDS as _COMMON_RAW

# Genuine English function words only. Deliberately NARROW: widening this to
# suppress noise would swallow the content-bearing nouns matching depends on
# (review finding — "jargon vs. concept").
STOPWORDS: frozenset[str] = frozenset(
    """
    a an the this that these those and or but nor for so yet
    is are was were be been being am
    do does did done doing
    have has had having
    will would shall should can could may might must
    i you he she it we they me him her us them
    my your his its our their mine yours
    of in on at to from by with about as into over under between through
    not no yes if then else when while because since than
    here there what which who whom whose how why where
    out up down off only just also too very more most some any
    each every both all none
    let lets need want make made get got
    please thing things way ways
    """.split()
)

_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")
_MIN_LEN = 4  # shorter tokens are too generic to count as a "salient" term


#: Contraction and possessive suffixes, reduced to the base word ("let's" ->
#: "let", "you'd" -> "you"). LONGEST FIRST, because the loop takes the first
#: match and "n't" would otherwise never be reached past a shorter sibling.
#: Every clitic English writes with an apostrophe is here — an incomplete set is
#: what left "you'd"/"i'll"/"they've" surviving whole into the term vocabulary
#: while "let's"/"don't" reduced correctly (#638).
_CLITICS: tuple[str, ...] = ("n't", "'ll", "'re", "'ve", "'s", "'d", "'m")

#: Stems that take the ``-es`` plural/3sg allomorph rather than a bare ``-s``.
#: Stripping one ``s`` from "enriches" mints "enriche"; stripping "es" gives
#: "enrich".
#:
#: **The membership is measured, not guessed**, because every ending here is
#: ambiguous in principle — "match" + "es" and "cache" + "s" are the same four
#: letters — so the question is which reading is right more often in the prose
#: this actually runs on. Counted over every ``.md`` in this repo's
#: ``.prawduct/``, ``plugin/`` and ``documentation/`` trees: ``ch`` (matches,
#: reaches, catches, branches, touches, dispatches, searches, …), ``sh``
#: (publishes, hashes, refreshes, finishes, crashes), ``ss`` (passes, classes,
#: misses, addresses, bypasses) and ``x`` (fixes, prefixes, suffixes, indexes,
#: checkboxes) are true ``-es`` in every occurrence but one.
#:
#: Two endings are DELIBERATELY ABSENT, and both were in an earlier draft:
#: a bare ``s`` (it makes "cases" -> "cas") and ``z`` (it makes "sizes" -> "siz"
#: and "generalizes" -> "generaliz" — the ``-ize`` verb family is the dominant
#: ``-zes`` population, 100+ occurrences against a handful of true ones).
_ES_STEM_ENDINGS: tuple[str, ...] = ("ch", "sh", "ss", "x")

#: The one-in-a-hundred exception to the rule above: ordinary words whose stem
#: genuinely ends in ``-e``, so their plural is a bare ``-s``. "caches" is the
#: measured instance (34 occurrences in this repo, against zero other ``-ches``
#: exceptions); the rest of the ``-che`` nouns are carried because this module
#: runs inside every governed product, whose prose this corpus does not predict.
#: A CLOSED set of known exceptions, not the beginning of a dictionary — add to
#: it only for a word someone has actually seen mis-stemmed.
_ES_EXCEPTIONS: frozenset[str] = frozenset(
    {"caches", "niches", "aches", "headaches", "avalanches", "mustaches", "quiches"}
)

#: Words that END in "-ies" without it being a plural suffix. The ``-ies`` -> "y"
#: rule is right for "stories"/"queries" and wrong for these, and no lexical test
#: separates them — so they are named. Same closed-set discipline as above.
_IES_INVARIANTS: frozenset[str] = frozenset({"series", "species"})


def _normalize(token: str) -> str:
    """Lowercase + a light, predictable singularization. No real stemmer — an
    aggressive one collapses distinct terms ("series" -> "seri").

    **Every branch here exists to avoid minting a non-word**, because a minted
    token is a term the artifact vocabulary can never match and therefore a
    silent hole in :func:`jurisdiction_candidates`' ranking. The three rules are
    clitics, the ``-es`` allomorph, and the bare plural, applied in that order.
    """
    t = token.lower().strip("'-")
    for clitic in _CLITICS:
        if t.endswith(clitic):
            t = t[: -len(clitic)]
            break
    # Returned WHOLE, not merely exempted from the ``-ies`` rule: falling through
    # would hand "series" to the bare-plural rule, which mints "serie" — the same
    # defect one branch lower down.
    if t in _IES_INVARIANTS:
        return t
    if len(t) > 5 and t.endswith("ies"):
        return t[:-3] + "y"
    # "-es" after a sibilant is one suffix, not an "-e" plus a plural "s".
    if (
        len(t) > 4
        and t.endswith("es")
        and t not in _ES_EXCEPTIONS
        and t[:-2].endswith(_ES_STEM_ENDINGS)
    ):
        return t[:-2]
    if len(t) > 4 and t.endswith("s") and not t.endswith(("ss", "us", "is")):
        return t[:-1]
    return t


def _tokens(text: str) -> list[str]:
    return [_normalize(m.group(0)) for m in _WORD.finditer(text)]


# The frequency floor, normalized the same way text tokens are so plural forms
# match ("settings" -> "setting").
_COMMON: frozenset[str] = frozenset(_normalize(w) for w in _COMMON_RAW) | _COMMON_RAW


def _in_floor(t: str) -> bool:
    """Frequency-floor membership, closed over light -ly/-ed derivation:
    "cleanly"/"landed"/"merged" are as conversational as their common bases.
    Deliberately NOT closed over -ing — that would swallow genuine concept
    markers whose base happens to be common ("conflicting" -> "conflict").
    Applies only to the floor, never to the artifact vocabulary."""
    if t in _COMMON:
        return True
    if t.endswith("ly") and t[:-2] in _COMMON:
        return True
    return t.endswith("ed") and (t[:-2] in _COMMON or t[:-1] in _COMMON)


def _salient(tokens: Iterable[str]) -> list[str]:
    """Content words, first-seen order, deduped."""
    seen: dict[str, None] = {}
    for t in tokens:
        if len(t) >= _MIN_LEN and t not in STOPWORDS:
            seen.setdefault(t, None)
    return list(seen)


def extract_vocabulary(text: str) -> set[str]:
    """Conservative vocabulary from one artifact: explicit frontmatter
    ``vocabulary:`` terms + markdown heading words + bold (``**...**``) terms.

    Conservative on purpose — we do not slurp the whole body, only the parts an
    author signals as significant (headings, bold) plus any declared vocabulary.
    """
    vocab: set[str] = set()

    # frontmatter `vocabulary: [a, b, c]`
    inline = re.search(r"^vocabulary:\s*\[(.+?)\]", text, re.MULTILINE)
    if inline:
        vocab.update(_tokens(inline.group(1)))
    # frontmatter block form:  vocabulary:\n  - term\n  - term
    block = re.search(r"^vocabulary:\s*\n((?:\s*-\s*.+\n?)+)", text, re.MULTILINE)
    if block:
        for line in block.group(1).splitlines():
            item = line.strip().lstrip("-").strip()
            if item:
                vocab.update(_tokens(item))

    for m in re.finditer(r"^#{1,6}\s+(.+)$", text, re.MULTILINE):
        vocab.update(_tokens(m.group(1)))
    for m in re.finditer(r"\*\*(.+?)\*\*", text):
        vocab.update(_tokens(m.group(1)))

    return {t for t in vocab if len(t) >= _MIN_LEN and t not in STOPWORDS}


def salient_terms(text: str) -> list[str]:
    """Candidate content words from a text, first-seen order."""
    return _salient(_tokens(text))


def jurisdiction_candidates(
    text: str, files: Iterable[tuple[str, str]], *, limit: int = 8
) -> list[dict]:
    """Which governing artifacts have *jurisdiction* over this text.

    For a plan or prompt, which artifacts' vocabularies already cover its
    salient terms — i.e. which artifacts plausibly *govern* it. The stoplist
    (via :func:`salient_terms`), the ``_MIN_LEN`` floor, and the common-English
    frequency floor (:func:`_in_floor`) all apply, so common words and short
    tokens can never produce a jurisdiction match.

    ``text`` is the plan/prompt to place; ``files`` is an iterable of
    ``(path, content)`` pairs (the governing corpus). Each file's vocabulary is
    harvested with :func:`extract_vocabulary` (headings + bold + declared
    vocabulary); ``matched`` is the text's floor-filtered salient terms present
    in that vocabulary.

    Returns candidates with ``count > 0`` only, ranked by count descending then
    path ascending (a stable, deterministic tie-break), capped at ``limit``.
    Shape::

        [{"path": str, "matched": [sorted terms], "count": int}, ...]

    This SEEDS a plan's ``governed_by:`` field — a mechanically-derived
    candidate list for the planner's judgment (a term-overlap heuristic, not a
    semantic ruling), never an authority. Reconciling each candidate (conform /
    ruling / amendment / inapplicable) stays the author's call.
    """
    # Floor-filter the text's salient terms once — the intersection below then
    # inherits the floor for free, so common words never surface as matches.
    salient = {t for t in salient_terms(text) if not _in_floor(t)}
    if not salient:
        return []

    candidates: list[dict] = []
    for path, content in files:
        matched = sorted(salient & extract_vocabulary(content))
        if matched:
            candidates.append(
                {"path": str(path), "matched": matched, "count": len(matched)}
            )

    # count desc, then path asc — path is the stable secondary key so ties
    # resolve deterministically regardless of corpus iteration order.
    candidates.sort(key=lambda c: (-c["count"], c["path"]))
    return candidates[:limit]
