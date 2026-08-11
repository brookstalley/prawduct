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
