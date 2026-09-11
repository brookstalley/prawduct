"""Tests for the work-model matching logic (``lib/work_model_index.py``).

What remains is `jurisdiction_candidates` — which governing artifacts already
cover a text's vocabulary, the mechanical seed for a plan's ``governed_by:`` —
plus the salience layer it is built on (`extract_vocabulary`, `salient_terms`).

The orphan-term tripwire these functions were originally written for was deleted
in v3.3.2 (owner ruling 2026-07-12, #257: its resolution was deletion, not a
further precision fix). Its tests went with it: the nudge formatting and firing
threshold, the requirement/maintenance verb classification, the harness-text
suppression, the index build, and the real-prompt replay that once served as
evidence for whether a deterministic diff could catch a new-concept message.
That question is no longer live — requirements-precede-code moved to the
review-time ``scope-trace:`` check (CRT-5M9J).

The salience tests below are kept because jurisdiction depends on them, not as
residue: the stoplist, the ``_MIN_LEN`` floor and the common-English frequency
floor are what stop common words from PRODUCING a match.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))

from lib import work_model_index as wmi  # noqa: E402


# --- salience layer (jurisdiction's precision depends on these) -------------


_ARTIFACT = """---
artifact: spec
vocabulary: [fact, contradiction, continuity]
---
# Model-based verification

## Fact graph
The derived **world model** indexes **facts** as queryable rows. A **continuity**
defect is the world layer **contradicting** itself.

## Scene judging
The **judge** evaluates a **scene** against an **entity**'s captured facts.
"""


def test_extract_vocabulary_harvests_headings_bold_and_frontmatter():
    vocab = wmi.extract_vocabulary(_ARTIFACT)
    # frontmatter declaration + bold + headings, normalized (facts -> fact)
    assert {"fact", "contradiction", "continuity", "entity", "scene"} <= vocab
    # short/function words are dropped
    assert "the" not in vocab and "a" not in vocab


def test_salient_terms_drops_stopwords_and_short_tokens():
    terms = wmi.salient_terms("We will model the belief of a character")
    assert "belief" in terms and "character" in terms
    assert "will" not in terms and "the" not in terms and "we" not in terms


# The frequency floor is asserted through `_in_floor` directly now. It used to be
# driven through `find_orphan_terms`, which is deleted; the floor itself is very
# much alive, because it is what stops jurisdiction matching on common words.


def test_floor_suppresses_common_english():
    for word in (
        "thank", "look", "again", "good", "development", "continue",
        "improve", "efficiency", "quality", "performance",
    ):
        assert wmi._in_floor(word) is True, f"{word} must be floor-suppressed"


def test_floor_closes_over_ly_and_ed_but_not_ing_derivations():
    # Inflections of common bases are as conversational as the bases.
    assert wmi._in_floor("cleanly") is True
    assert wmi._in_floor("landed") is True
    assert wmi._in_floor("merged") is True
    # -ing is deliberately open: "conflicting" is a keystone concept marker even
    # though its base "conflict" is common — so it can still produce a match.
    assert wmi._in_floor("conflicting") is False


# --- normalization (#638) ---------------------------------------------------
# ``_normalize`` is the gate every term passes through on BOTH sides of a
# jurisdiction match — the text's tokens and the artifact's vocabulary. A minted
# non-word is therefore not a cosmetic defect: it is a term that can never match
# anything, so the ranking silently degrades with nothing to catch it. These
# assertions are all about that one property: what comes out is a real word.


def test_every_clitic_reduces_to_its_base_word():
    """#638: only ``'s`` and ``n't`` were handled, so the rest survived whole."""
    assert wmi._normalize("you'd") == "you"
    assert wmi._normalize("i'll") == "i"
    assert wmi._normalize("they've") == "they"
    assert wmi._normalize("we're") == "we"
    assert wmi._normalize("i'm") == "i"
    # The two that already worked, pinned so a reordering of the suffix tuple
    # cannot regress them: "n't" is longer than "'s" and must be tried first.
    assert wmi._normalize("don't") == "do"
    assert wmi._normalize("let's") == "let"
    assert wmi._normalize("team's") == "team"


def test_es_after_a_sibilant_is_one_suffix_not_an_e_plus_s():
    """#638: the bare-plural rule minted "enriche" from "enriches"."""
    assert wmi._normalize("enriches") == "enrich"
    assert wmi._normalize("matches") == "match"
    assert wmi._normalize("finishes") == "finish"
    assert wmi._normalize("passes") == "pass"
    assert wmi._normalize("boxes") == "box"


def test_the_es_rule_does_not_swallow_an_ordinary_plural():
    """The regression the ``-es`` rule could cause, pinned against it.

    "cases" -> "cas" and "enriches" -> "enrich" are indistinguishable by a bare
    trailing-``s`` test, which is why the stem must end in a sibilant CLUSTER
    and why a bare ``s`` is not one of them.
    """
    assert wmi._normalize("cases") == "case"
    assert wmi._normalize("phases") == "phase"
    assert wmi._normalize("releases") == "release"


def test_the_ize_verb_family_survives_the_es_rule():
    """``z`` is excluded from the sibilant set, and this is why.

    "-zes" is dominated by ``-ize`` verbs and ``-ze`` nouns, where the ``s`` is
    the whole suffix. An earlier draft included ``z`` and turned "sizes" into
    "siz" and "generalizes" into "generaliz".
    """
    assert wmi._normalize("sizes") == "size"
    assert wmi._normalize("generalizes") == "generalize"
    assert wmi._normalize("normalizes") == "normalize"
    assert wmi._normalize("freezes") == "freeze"


def test_the_measured_che_exception_is_honoured():
    """"caches" is "cache" + "s", not "cach" + "es" — the one measured exception.

    It matters here specifically: "cache" is load-bearing vocabulary in this
    codebase (the backlog cache, the plugin cache), so mis-stemming it would
    split a term the artifacts and the prose both use constantly.
    """
    assert wmi._normalize("caches") == "cache"
    assert wmi._normalize("caches") == wmi._normalize("cache")
    assert wmi._normalize("niches") == "niche"
    # The rule the exception set must not disable.
    assert wmi._normalize("branches") == "branch"
    assert wmi._normalize("dispatches") == "dispatch"


def test_ies_singulars_are_returned_whole():
    """"series" is the function's own docstring example of what not to mint.

    Exempting them from the ``-ies`` rule is not enough on its own — falling
    through hands them to the bare-plural rule, which mints "serie".
    """
    assert wmi._normalize("series") == "series"
    assert wmi._normalize("species") == "species"
    # The rule the deny-list must not disable.
    assert wmi._normalize("stories") == "story"
    assert wmi._normalize("queries") == "query"
    assert wmi._normalize("entries") == "entry"


def test_normalization_still_singularizes_the_ordinary_cases():
    """The behavior the frequency floor and the vocabulary index both rely on."""
    assert wmi._normalize("settings") == "setting"
    assert wmi._normalize("facts") == "fact"
    # Not-a-plural endings stay untouched.
    assert wmi._normalize("address") == "address"
    assert wmi._normalize("status") == "status"
    assert wmi._normalize("analysis") == "analysis"


def test_a_mis_stemmed_term_cannot_match_its_artifact():
    """Why the above matters, asserted end-to-end rather than argued.

    An artifact declaring "enrichment"-family vocabulary and a text saying
    "enriches" must meet at the same normalized token. Under the pre-#638
    function the text produced "enriche" and the artifact "enrich", so the two
    could never meet — the degraded ranking the issue describes.
    """
    assert wmi._normalize("enriches") == wmi._normalize("enrich")
    assert wmi._normalize("matches") == wmi._normalize("match")


# --- jurisdiction ----------------------------------------------------------
# ``jurisdiction_candidates`` answers "which artifacts cover this text's salient
# terms" — the mechanical seed for a plan's ``governed_by:``. The salience
# machinery (stoplist + _MIN_LEN + frequency floor) is what stops common words
# and short tokens from ever PRODUCING a match.

# Two governing artifacts whose vocabulary (headings + bold, per
# extract_vocabulary) overlaps a plan by different amounts.
_JURIS_FILE_A = (
    "artifacts/telemetry-strategy.md",
    "# Telemetry Substrate\n"
    "The **telemetry** substrate governs **tracing** and observability.\n",
)  # vocab: telemetry, substrate, tracing (+ observability)
_JURIS_FILE_B = (
    "artifacts/backlog-notes.md",
    "# Notes\nStray **telemetry** mention, nothing else here.\n",
)  # vocab: telemetry (+ notes/stray/mention)


def test_jurisdiction_ranks_higher_overlap_first():
    # Text shares 3 salient terms with A (telemetry, substrate, tracing) and 1
    # with B (telemetry) -> A must rank first, B second.
    cands = wmi.jurisdiction_candidates(
        "unify the telemetry substrate for tracing pipelines",
        [_JURIS_FILE_A, _JURIS_FILE_B],
    )
    assert [c["path"] for c in cands] == [
        "artifacts/telemetry-strategy.md",
        "artifacts/backlog-notes.md",
    ]
    assert cands[0]["count"] == 3
    assert cands[0]["matched"] == ["substrate", "telemetry", "tracing"]  # sorted
    assert cands[1]["count"] == 1 and cands[1]["matched"] == ["telemetry"]


def test_jurisdiction_shape_is_path_matched_count():
    cand = wmi.jurisdiction_candidates("telemetry tracing", [_JURIS_FILE_A])[0]
    assert set(cand) == {"path", "matched", "count"}
    assert isinstance(cand["path"], str)
    assert cand["matched"] == sorted(cand["matched"])  # always sorted
    assert cand["count"] == len(cand["matched"])


def test_jurisdiction_floor_common_and_short_words_never_match():
    # The file's vocabulary DOES contain common/floor words (quality,
    # performance, development) and a 3-char token (api). None may surface as a
    # match: floor words are filtered from the text's salient terms, and the
    # <4-char token is below _MIN_LEN in BOTH the text and extract_vocabulary.
    common_file = (
        "artifacts/x.md",
        "# Quality and Performance\nThe **development** api improves **widget** flow\n",
    )
    cands = wmi.jurisdiction_candidates(
        "improve development quality performance widget api", [common_file]
    )
    assert len(cands) == 1
    # Only the genuine domain term survives — never the floor/common words or
    # the short token.
    assert cands[0]["matched"] == ["widget"]
    for noise in ("quality", "performance", "development", "improve", "api"):
        assert noise not in cands[0]["matched"]


def test_jurisdiction_empty_text_is_empty():
    assert wmi.jurisdiction_candidates("", [_JURIS_FILE_A]) == []
    # All-stopword / all-floor text has no salient terms either.
    assert wmi.jurisdiction_candidates("please do this for us", [_JURIS_FILE_A]) == []


def test_jurisdiction_no_overlap_is_empty():
    # Genuine salient terms, but none appear in any file's vocabulary.
    assert wmi.jurisdiction_candidates(
        "quaternion holography magnetosphere", [_JURIS_FILE_A, _JURIS_FILE_B]
    ) == []


def test_jurisdiction_respects_limit_and_tie_breaks_on_path():
    # Ten files all sharing exactly one term (telemetry) -> a full count tie.
    # The deterministic tie-break is path ascending, and the cap is `limit`.
    files = [
        (f"artifacts/f{i}.md", "# T\nThe **telemetry** system\n") for i in range(10)
    ]
    # Feed them OUT of path order to prove the sort, not iteration, orders them.
    files_shuffled = list(reversed(files))

    capped = wmi.jurisdiction_candidates("telemetry", files_shuffled, limit=3)
    assert [c["path"] for c in capped] == [
        "artifacts/f0.md",
        "artifacts/f1.md",
        "artifacts/f2.md",
    ]
    # Default limit is 8.
    default = wmi.jurisdiction_candidates("telemetry", files_shuffled)
    assert len(default) == 8
    assert [c["path"] for c in default] == [f"artifacts/f{i}.md" for i in range(8)]
