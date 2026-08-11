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


def _normalize(token: str) -> str:
    """Lowercase + a light, predictable singularization. No real stemmer — an
    aggressive one collapses distinct terms ("series" -> "seri")."""
    t = token.lower().strip("'-")
    # Contractions/possessives reduce to their base word ("let's" -> "let",
    # "don't" -> "do") — the bare plural rule would otherwise mint non-words
    # like "let'" that read as unfamiliar terms.
    if t.endswith("'s"):
        t = t[:-2]
    elif t.endswith("n't"):
        t = t[:-3]
    if len(t) > 5 and t.endswith("ies"):
        return t[:-3] + "y"
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
