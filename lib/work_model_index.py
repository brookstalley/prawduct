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
the catch would miss the concept it exists for.

Precision layer (review-fixes Chunk 2, 2026-06-09): in live use the original
"index is the only noise lever" stance failed — the probe fired on ordinary
conversational prompts ("thanks, looks good", "Please continue!") and on the
review session's own prompts (*efficiency, improve, quality, performance*),
~80 noise tokens per misfire, training the model to ignore the one real catch.
Three additions restore precision without touching the stoplist:

1. a **common-English frequency floor** (``lib/common_words.py``) — high-
   frequency words are never orphans, regardless of corpus;
2. a **firing threshold** (``should_fire``) — the nudge fires only when the
   prompt is requirement-shaped (imperative build/add/implement-class verb)
   or when >= 2 orphans co-occur; bare questions, acknowledgments, and
   harness-injected notifications never fire;
3. a **wider corpus** (hook side) — CLAUDE.md, ``docs/``, and ``methodology/``
   feed the index alongside ``.prawduct/artifacts/``.

The accepted recall trade: a requirement phrased entirely in floor words
("add payment support") stays silent. The deferred LLM-in-hook classifier
remains the evidence-gated upgrade for that documented gap.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from lib.common_words import WORDS as _COMMON_RAW

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
    # Contractions/possessives reduce to their base word ("let's" -> "let",
    # "don't" -> "do") — the bare plural rule would otherwise mint non-words
    # like "let'" that read as orphan terms (review-fixes Chunk 2).
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


# The frequency floor, normalized the same way prompt tokens are so plural
# forms match ("settings" -> "setting"). Membership is checked against
# normalized tokens only — see find_orphan_terms.
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

# Imperative build/add/implement-class verbs: their presence marks a prompt as
# requirement-shaped, so even a single orphan term fires the nudge. Base forms
# only (plus light plural normalization, "implements" -> "implement"); polite
# requests use base-form imperatives, and a missed "-ing" participle still
# fires via the >= 2 orphan path.
REQUIREMENT_VERBS: frozenset[str] = frozenset(
    """
    add build implement create support integrate migrate introduce extend
    enable disable wire ship write expose persist enforce
    """.split()
)

# Maintenance verbs act on what already exists: a refactor/rename directive is
# routine work, not a new requirement entering undocumented, so these never
# make a prompt requirement-shaped (gate-noise — the old combined set made the
# tripwire fire on review/cleanup prompts at the single-orphan threshold).
# They are still directive vocabulary, so find_orphan_terms exempts them like
# REQUIREMENT_VERBS: rename/redesign/rework sit above the frequency floor and
# would otherwise surface as bogus domain terms.
MAINTENANCE_VERBS: frozenset[str] = frozenset(
    "refactor rename redesign rework remove replace".split()
)

# The orphan exemption covers both roles of directive vocabulary.
_DIRECTIVE_VERBS: frozenset[str] = REQUIREMENT_VERBS | MAINTENANCE_VERBS

# Harness-injected (non-user-authored) content that flows through the
# UserPromptSubmit hook: task notifications, command transcripts, system
# reminders. Hundreds of orphan-shaped tokens, zero requirements — never fire.
# Accepted trade: a marker anywhere silences the WHOLE prompt, so a genuine
# requirement pasted alongside such markup goes unchecked — rare, and the miss
# is one nudge, not a gate; the alternative (excising marked spans) buys
# little for real parsing risk.
_HARNESS_MARKERS: tuple[str, ...] = (
    "<task-notification>",
    "<system-reminder>",
    "<command-name>",
    "<local-command-stdout>",
)


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
    """Salient prompt terms that appear in NO governing artifact and are not
    common English (the frequency floor — high-frequency words are never
    flagged, regardless of corpus). Directive verbs — requirement AND
    maintenance — are not domain terms: "extend X" must never report *extend*
    as the orphan, nor "rename X" *rename*."""
    vocab = set(index.get("vocab", ()))
    return [
        t
        for t in salient_terms(prompt)
        if t not in vocab and not _in_floor(t) and t not in _DIRECTIVE_VERBS
    ]


# A requirement verb preceded by one of these reads as a NOUN, not a directive:
# "the build failed", "thanks for the support". Skipping those keeps status
# chatter from counting as requirement-shaped (Critic NOTE, review-fixes ch.2).
_NOUN_DETERMINERS: frozenset[str] = frozenset(
    "the a an this that these those my your his her its our their some any each no".split()
)


_SENTENCE_BREAK = re.compile(r"[.!?;:\n]")


def is_requirement_shaped(prompt: str) -> bool:
    """True when the prompt contains an imperative build/add/implement-class
    verb — the shape of a directive that can carry a new requirement. A verb
    homograph used as a noun ("the build", "your support") does not count;
    the noun-determiner check resets at sentence boundaries so "I like this.
    Build a kanban view" still reads as a directive."""
    prev = ""
    last_end = 0
    for m in _WORD.finditer(prompt):
        if _SENTENCE_BREAK.search(prompt, last_end, m.start()):
            prev = ""
        raw = m.group(0).lower()
        if (
            (raw in REQUIREMENT_VERBS or _normalize(raw) in REQUIREMENT_VERBS)
            and prev not in _NOUN_DETERMINERS
        ):
            return True
        prev = raw
        last_end = m.end()
    return False


def _is_question(prompt: str) -> bool:
    return prompt.rstrip().endswith("?")


def _is_harness_text(prompt: str) -> bool:
    return any(marker in prompt for marker in _HARNESS_MARKERS)


def should_fire(prompt: str, orphans: list[str]) -> bool:
    """The firing threshold (precision layer). Fire only when:

    * the prompt is requirement-shaped (imperative verb) with >= 1 orphan, or
    * >= 2 orphan terms co-occur in a non-question prompt.

    Never fire on harness-injected content (notifications, command output) or
    on bare questions — a question that *requests* work ("can you add X?") is
    requirement-shaped and still fires.
    """
    if not orphans or _is_harness_text(prompt):
        return False
    if is_requirement_shaped(prompt):
        return True
    if _is_question(prompt):
        return False
    return len(orphans) >= 2


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


def nudge_for(prompt: str, index: dict) -> str | None:
    """The full pipeline the hook runs: orphan detection + firing threshold.
    Returns the nudge text, or None (silent-when-clean)."""
    orphans = find_orphan_terms(prompt, index)
    if not should_fire(prompt, orphans):
        return None
    return format_nudge(orphans)
