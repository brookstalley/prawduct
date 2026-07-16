"""Tests for the work-model catch logic (``lib/work_model_index.py``).

The keystone of the work model is an *external, deterministic* pre-turn nudge
that surfaces salient terms a user introduces which NO governing artifact
covers. These tests pin its contract and — decisively — replay the **real scriob
prompt** that triggered the original failure, to answer empirically whether the
deterministic diff actually catches a real new-concept message. Per the build
plan, the stoplist is NOT tuned to make the replay pass; the replay's result is
evidence either way (a miss would unlock the deferred LLM classifier).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lib import work_model_index as wmi  # noqa: E402


# A representative governing-artifact corpus for scriob's verification work —
# the domain the agent was actually building when the new dimension arrived.
# Headings + bold are what extract_vocabulary harvests.
VERIFICATION_ARTIFACTS = [
    """---
artifact: spec
vocabulary: [fact, contradiction, continuity]
---
# Model-based verification

## Fact graph
The derived **world model** indexes **facts** as queryable rows. A **continuity**
defect is the world layer **contradicting** itself. Structural **retrieval** finds
**same-subject** candidates via the **fact graph**.

## Scene judging
The **judge** evaluates a **scene** against an **entity**'s captured facts, gated
by the knowledge **horizon**. The **embedder** governs lexical **retrieval** over a
candidate **window**.
""",
]


def _index():
    return wmi.build_index(VERIFICATION_ARTIFACTS)


# --- unit contract ---------------------------------------------------------

def test_extract_vocabulary_harvests_headings_bold_and_frontmatter():
    vocab = wmi.extract_vocabulary(VERIFICATION_ARTIFACTS[0])
    # frontmatter declaration + bold + headings, normalized (facts -> fact)
    assert {"fact", "contradiction", "continuity", "entity", "scene"} <= vocab
    # short/function words are dropped
    assert "the" not in vocab and "a" not in vocab


def test_build_index_unions_and_sorts():
    idx = _index()
    assert idx["vocab"] == sorted(idx["vocab"])
    assert "fact" in idx["vocab"]


def test_salient_terms_drops_stopwords_and_short_tokens():
    terms = wmi.salient_terms("We will model the belief of a character")
    assert "belief" in terms and "character" in terms
    assert "will" not in terms and "the" not in terms and "we" not in terms


def test_find_orphan_terms_flags_only_uncovered():
    idx = _index()
    # "continuity" is covered; "sincerity" is not
    orphans = wmi.find_orphan_terms("check continuity against sincerity", idx)
    assert "sincerity" in orphans
    assert "continuity" not in orphans


def test_format_nudge_silent_when_clean():
    assert wmi.format_nudge([]) is None


def test_format_nudge_speaks_on_orphans():
    msg = wmi.format_nudge(["belief", "sincerity"])
    assert msg is not None and "belief" in msg and "tripwire #1" in msg


def test_format_nudge_caps_long_lists():
    msg = wmi.format_nudge([f"t{i}" for i in range(20)], limit=8)
    assert "+12 more" in msg


# --- THE DECISIVE REPLAY: the real scriob prompt --------------------------

# Verbatim essence of the turn-7/turn-8 messages that introduced the belief/
# truth/lies dimension mid-build — the failure the work model exists to catch.
SCRIOB_PROMPT = (
    "I think that's correct, but please do think about how we model in-world "
    "sources, canonical sources from author's notes, and even conflicting claims "
    "(Charlie tells Alice that Bob can't swim; Charlie tells David that Bob can "
    "swim; David relays the truth he knows to Eddie; but Alice lies to Fred and "
    "says that Bob can swim). Each character has beliefs, they may differ, their "
    "speech may or may not reflect their true beliefs, and there is an objectively "
    "true world. This seems likely to be a solved problem — logical or taxonomy "
    "models of events, beliefs, truth, and sincerity in fiction."
)


def test_replay_real_scriob_prompt_fires_the_nudge():
    """Against a verification-domain index, the real scriob prompt MUST surface
    the new epistemic concepts and fire the nudge. This is the keystone gate."""
    idx = _index()
    orphans = wmi.find_orphan_terms(SCRIOB_PROMPT, idx)

    # The distinctive new-concept markers must be caught (these are genuinely
    # absent from a fact/continuity verification vocabulary):
    expected = {"belief", "canonical", "conflicting", "sincerity"}
    caught = expected & set(orphans)
    assert caught == expected, (
        f"deterministic catch MISSED concept markers {expected - caught}; "
        f"orphans were {orphans} — if this fails honestly, it is the evidence "
        "that unlocks the deferred LLM classifier (do NOT tune the stoplist)."
    )

    assert wmi.format_nudge(orphans) is not None


# --- HONEST false-positive characterization (the make-or-break risk) -------

def test_index_suppresses_covered_terms_and_keeps_signal_above_noise():
    """The noise lever is the INDEX, not the stoplist. The honest contract a
    pure lexical diff can deliver: (1) no *covered* domain term leaks as noise,
    and (2) a routine in-domain prompt yields far fewer orphans than a genuine
    new-concept prompt. The small residual (common verbs like 'widen'/'sees') is
    irreducible lexical noise — the documented evidence that a *clean* catch
    needs the deferred LLM classifier, NOT a wider stoplist (which would swallow
    the very concepts the catch exists for)."""
    idx = _index()
    routine = (
        "widen the retrieval window so the continuity judge sees the same-subject "
        "facts in the world model"
    )
    routine_orphans = wmi.find_orphan_terms(routine, idx)
    scriob_orphans = wmi.find_orphan_terms(SCRIOB_PROMPT, idx)

    # (1) The index does its job: covered domain terms never surface as noise.
    for covered in ("retrieval", "continuity", "judge", "fact", "world", "model"):
        assert covered not in routine_orphans

    # (2) Signal >> noise: the new-concept prompt fires far more than routine work.
    assert len(routine_orphans) < len(scriob_orphans)
    # Residual noise is small and bounded (documented, not zero — honest).
    assert len(routine_orphans) <= 3


def test_sparse_index_is_noisy_documenting_the_risk():
    """With an almost-empty index the catch still flags genuinely rare domain
    words — documenting honestly that the catch's quality depends on a
    populated index (the make-or-break risk the review named). This is
    characterization, not a target.

    Contract renegotiated in review-fixes Chunk 2 (was ``>= 3``): the
    common-English frequency floor now absorbs the ordinary-word part of the
    sparse-index noise (window, judge, refactor), which is the chunk's point —
    only the genuinely rare terms (retrieval, continuity) still surface."""
    sparse = wmi.build_index(["# Notes\nnothing **domain** here"])
    orphans = wmi.find_orphan_terms(
        "refactor the retrieval window for the continuity judge", sparse
    )
    assert "retrieval" in orphans and "continuity" in orphans
    assert "window" not in orphans  # the floor at work


# --- Precision layer (review-fixes Chunk 2): floor + firing threshold -------

# The index for precision tests: a representative governing corpus.
PRECISION_INDEX = wmi.build_index(VERIFICATION_ARTIFACTS)

# Conversational / non-requirement prompts: every one of these MUST be silent.
# The first four are the false-positive classes observed live in the 2026-06-09
# review session (the chunk's acceptance criteria).
CONVERSATIONAL_PROMPTS = [
    "Please continue!",
    "thanks, looks good",
    "Please review the framework for efficiency, quality, performance, and "
    "token management improvements",
    "<task-notification>\n<task-id>b31kix32k</task-id>\n<status>completed</status>\n"
    "Background command finished: pytest exited 0 with 1037 passed, "
    "porcelain gitstate regression fixtures all green\n</task-notification>",
    "yes, that's exactly right",
    "ok great, ship it",
    "hmm, can you explain why the second test failed?",
    "what does the critic do during a cumulative review?",
    "looks good to me, nice work",
    "typo in the readme, third paragraph",
    "that fixed it, thanks!",
    "go ahead",
    "sounds good, proceed with the plan",
    "interesting — I didn't expect that result",
    "let's pause here and pick this up tomorrow",
    # Verb homographs used as nouns must not make chatter requirement-shaped
    # (Critic NOTE, review-fixes ch.2):
    "the build failed with a segfault",
    "thanks for the support — that refactor landed cleanly",
    "the new integration looks solid, nice work on the rollout",
]

# Genuine new-requirement prompts: every one of these MUST still fire.
REQUIREMENT_PROMPTS = [
    "add OAuth login to the settings page",
    SCRIOB_PROMPT,
    "implement webhook retries with exponential backoff",
    "build a kanban board view for the backlog",
    "we should support SSO via SAML for enterprise tenants",
]


def test_precision_conversational_corpus_is_silent():
    noisy = [p for p in CONVERSATIONAL_PROMPTS if wmi.nudge_for(p, PRECISION_INDEX)]
    assert not noisy, f"false positives on: {noisy!r}"


def test_precision_requirement_corpus_still_fires():
    missed = [p for p in REQUIREMENT_PROMPTS if not wmi.nudge_for(p, PRECISION_INDEX)]
    assert not missed, f"missed genuine requirement prompts: {missed!r}"


def test_floor_suppresses_common_english_regardless_of_corpus():
    empty = wmi.build_index([])
    assert wmi.find_orphan_terms(
        "thank you, look again — good development, continue to improve "
        "efficiency, quality and performance", empty
    ) == []


def test_floor_closes_over_ly_and_ed_but_not_ing_derivations():
    empty = wmi.build_index([])
    # Inflections of common bases are as conversational as the bases.
    assert wmi.find_orphan_terms("it landed cleanly and merged", empty) == []
    # -ing is deliberately open: "conflicting" is a keystone concept marker
    # even though its base "conflict" is common.
    assert "conflicting" in wmi.find_orphan_terms("conflicting claims", empty)


def test_threshold_single_orphan_non_imperative_is_silent():
    assert wmi.nudge_for("consider the provenance here", PRECISION_INDEX) is None


def test_threshold_two_orphans_fire():
    msg = wmi.nudge_for("provenance and attestation matter here", PRECISION_INDEX)
    assert msg is not None and "provenance" in msg


def test_threshold_imperative_plus_one_orphan_fires():
    msg = wmi.nudge_for("add provenance tracking", PRECISION_INDEX)
    assert msg is not None and "provenance" in msg


def test_threshold_bare_question_is_silent_even_with_orphans():
    assert wmi.nudge_for(
        "what about provenance and attestation?", PRECISION_INDEX
    ) is None


def test_threshold_requirement_shaped_question_still_fires():
    # A question that REQUESTS work is a requirement carrier, not a bare question.
    assert wmi.nudge_for("can you add provenance tracking?", PRECISION_INDEX) is not None


def test_verb_homographs_as_nouns_are_not_requirement_shaped():
    assert not wmi.is_requirement_shaped("the build failed with a segfault")
    assert not wmi.is_requirement_shaped("thanks for the support")
    # ... while genuine directives still are:
    assert wmi.is_requirement_shaped("build a kanban view")
    assert wmi.is_requirement_shaped("can you build a kanban view?")
    assert wmi.is_requirement_shaped("we should support SSO")
    # The noun-determiner check resets at sentence boundaries (Critic NOTE):
    assert wmi.is_requirement_shaped("I like this. Build a kanban view")



# --- Maintenance-verb split (gate-noise, GOV-7T2M) ---------------------------
# Verbs that act on what already exists (refactor/rename/redesign/rework/
# remove/replace) are routine-work directives, not requirement carriers: they
# no longer lower the firing threshold to a single orphan. They stay exempt
# from orphan reporting — rename/redesign/rework sit above the frequency floor
# and would otherwise surface as bogus domain terms.


def test_maintenance_verbs_are_not_requirement_shaped():
    assert not wmi.is_requirement_shaped("refactor the retrieval pipeline")
    assert not wmi.is_requirement_shaped("rename FooBar to BazQux across the repo")
    assert not wmi.is_requirement_shaped("rework the session digest and remove the shim")
    assert not wmi.is_requirement_shaped(
        "Please review the framework for efficiency — then redesign the noisiest gate"
    )


def test_maintenance_prompt_with_single_orphan_is_silent():
    # The owner's-review-prompt class: a maintenance verb plus one novel term
    # used to fire at the single-orphan threshold; now needs >= 2 orphans.
    assert wmi.nudge_for("refactor the provenance handling", PRECISION_INDEX) is None
    assert wmi.nudge_for("rename the attestation module", PRECISION_INDEX) is None


def test_maintenance_prompt_with_two_orphans_still_fires():
    # The split narrows the trigger, it doesn't blind the catch: genuinely new
    # domain vocabulary in maintenance phrasing still surfaces via >= 2 orphans.
    msg = wmi.nudge_for("refactor provenance and attestation handling", PRECISION_INDEX)
    assert msg is not None and "provenance" in msg and "attestation" in msg


def test_maintenance_verbs_are_never_the_orphan():
    # rename/redesign/rework are NOT absorbed by the frequency floor, so the
    # orphan exemption must cover the union of both verb sets — a bare drop
    # from REQUIREMENT_VERBS would have reported the verb itself as the orphan.
    empty = wmi.build_index([])
    orphans = wmi.find_orphan_terms("rename and redesign the provenance rework", empty)
    assert orphans == ["provenance"]


def test_requirement_verbs_are_never_the_orphan():
    # "extend"/"integrate" rank above the frequency floor, but a directive verb
    # is never the undocumented domain term — only "telemetry" may surface.
    orphans = wmi.find_orphan_terms("extend and integrate the telemetry", PRECISION_INDEX)
    assert orphans == ["telemetry"]


def test_harness_injected_content_never_fires():
    blob = "<system-reminder>provenance attestation doxastic ledger</system-reminder>"
    assert wmi.nudge_for(blob, PRECISION_INDEX) is None


# --- Jurisdiction assist (norm-lifecycle Chunk 2): the orphan-detection inverse
# ``find_orphan_terms`` answers "which salient terms does NO artifact cover".
# ``jurisdiction_candidates`` answers the complement "which artifacts cover this
# text's salient terms" — the mechanical seed for a plan's ``governed_by:``.
# Same salience machinery (stoplist + _MIN_LEN + frequency floor), so common
# words and short tokens can never PRODUCE a match, just as they can never
# BECOME an orphan.

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
