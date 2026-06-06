"""Work model — vocabulary index + orphan-term detection (pure logic).

The "catch" behind the work model's external enforcement (``docs/work-model.md``
§3b; ``docs/work-model-delta.md``): a deterministic check that surfaces, pre-turn,
any salient term in a user's message that NO governing artifact covers — the
signal that a new requirement may be entering undocumented (tripwire #1).

This module is PURE — no I/O, no environment, no Claude Code coupling. The hook
wiring (``bin/prawduct-hook`` subcommands + ``hooks/hooks.json``) is Chunk 2 and
builds on these functions. Keeping the logic here makes the keystone question —
*does the deterministic diff actually catch a real new-concept prompt?* —
unit-testable in isolation, before any live-hook risk.

Honest scope (independent review, ``docs/work-model-review.md``): this is an
*unfamiliar-token* tripwire. It reliably surfaces content-word terms absent from
the artifacts; it is weaker on new concepts phrased entirely in very common
words. The stoplist below is genuine English function words ONLY — deliberately
NOT widened to suppress noise, because suppressing content words is exactly how
the catch would miss the concept it exists for. Noise is the index's job: a
populated index makes routine in-domain prompts quiet. Where that proves
insufficient, the deferred LLM-in-hook classifier is the evidence-gated upgrade.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

# Genuine English function words only. Deliberately NARROW: widening this to
# suppress false positives would swallow the content-bearing nouns the catch
# depends on (review finding — "jargon vs. concept"). Noise is handled by a
# populated index, not by an aggressive stoplist.
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
    if len(t) > 5 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 4 and t.endswith("s") and not t.endswith(("ss", "us", "is")):
        return t[:-1]
    return t


def _tokens(text: str) -> list[str]:
    return [_normalize(m.group(0)) for m in _WORD.finditer(text)]


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


def build_index(texts: Iterable[str]) -> dict:
    """Union the per-artifact vocabularies into a sorted index document."""
    vocab: set[str] = set()
    for text in texts:
        vocab |= extract_vocabulary(text)
    return {"vocab": sorted(vocab)}


def salient_terms(prompt: str) -> list[str]:
    """Candidate content words from a user prompt, first-seen order."""
    return _salient(_tokens(prompt))


def find_orphan_terms(prompt: str, index: dict) -> list[str]:
    """Salient prompt terms that appear in NO governing artifact."""
    vocab = set(index.get("vocab", ()))
    return [t for t in salient_terms(prompt) if t not in vocab]


def format_nudge(orphans: list[str], *, limit: int = 8) -> str | None:
    """The pre-turn nudge text, or None when there is nothing to flag
    (silent-when-clean — the property that keeps this signal, not ceremony)."""
    if not orphans:
        return None
    shown = orphans[:limit]
    more = "" if len(orphans) <= limit else f" (+{len(orphans) - limit} more)"
    return (
        "⚠ Work model: terms not found in any governing artifact: "
        f"{', '.join(shown)}{more}. If this introduces new behavior, locate or "
        "write the parent requirement before designing against it "
        "(tripwire #1 — requirements precede code)."
    )
