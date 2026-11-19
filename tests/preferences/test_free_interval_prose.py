"""The prose surfaces must not teach the review treadmill they now prevent.

`critic-begin` refuses a review the coverage gate would not require (exit 3,
"no review needed") — measured 2026-08-06 at 62 of 492 recorded reviews, 12.6%,
~5.2 opus-hours of reviewer time spent on intervals that were free the whole
time. The mechanism is only half the fix. The other half is that the surfaces a
builder reads *at the moment they decide whether to spend a round* stop telling
them to spend one unconditionally, and start telling them the cheaper truth:
**asking is free, so ask instead of reasoning.**

Prose is the load-bearing part here, not decoration. Skill and methodology files
in this framework are behavioral logic executed by a model — which is why
`is_judgeable_path` classifies them as judgeable code — and the measured waste
was produced by builders following exactly these instructions correctly.

**Structural, not a content audit** (same posture as
`test_critic_skill_structure.py`): each surface must *carry the qualifier*, and
must not carry the specific unconditional phrasing that predates the guard. It
does not check that the surrounding explanation is good — that is the Critic's
job (Goal 4: Coherence).

**Why `methodology/building.md` is deliberately NOT in `_SURFACES`.** Its
"Resolve findings" paragraph names where the fix order is printed and points at
the anchoring derivation; running the verify pass and letting the exit code
answer is exactly the desired behaviour, and the guard makes that cheaper rather
than wrong. Adding the qualifier there would spend that file's token budget
restating a mechanism the command itself now enforces, on the one surface whose
job is the shape of the cycle rather than the cost of a round. Recorded here
because the omission is a judgement, not an oversight (cumulative
`rev-20260806T215117Z-31201027`, R-15). It IS a pointer surface for the
post-fix coverage rule below (#723).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
PLUGIN = REPO_ROOT / "plugin"

#: Every surface that tells a builder whether to spend a review round, with the
#: token proving it carries the free-interval answer. `exit 3` / `exits 3` is
#: the load-bearing token: it names the observable outcome, so a rewrite that
#: keeps the advice but drops the mechanism still fails here.
_SURFACES = [
    pytest.param(
        PLUGIN / "skills" / "pr" / "SKILL.md",
        ("exit 3",),
        id="pr-skill-step-2-sequencing",
    ),
    pytest.param(
        PLUGIN / "skills" / "critic" / "review-cycle.md",
        ("exits 3", "no review needed"),
        id="review-cycle-close-coverage",
    ),
    pytest.param(
        PLUGIN / "skills" / "critic" / "SKILL.md",
        ("Exit 3", "--force"),
        id="critic-skill-dispatch",
    ),
    pytest.param(
        PLUGIN / "lib" / "critic_consolidate.py",
        ("exits 3",),
        id="next-action-text",
    ),
]


@pytest.mark.parametrize(("path", "tokens"), _SURFACES)
def test_the_surface_names_the_free_interval_answer(path: Path, tokens):
    assert path.is_file(), f"{path} moved — this test's subject no longer exists"
    text = path.read_text()
    missing = [t for t in tokens if t not in text]
    assert not missing, (
        f"{path.relative_to(REPO_ROOT)} decides whether a review round is spent "
        f"but never tells the reader the dispatcher answers that for free "
        f"(missing: {missing}). A builder reading it will reason about "
        f"judgeability, or spend the round to be safe — which is the measured "
        f"waste the guard exists to end."
    )


def test_the_next_action_text_does_not_prescribe_an_unconditional_round():
    """The clean-review arms must keep their condition.

    `_next_action` has three arms. The BLOCKING arm's "then run one
    verify-resolutions" is CORRECT and deliberately untouched: a blocking
    finding is cleared only by the resolution facts a verify pass records, which
    is exactly why the refusal predicate's second conjunct exists — refusing
    that pass would wedge the gate with no command that clears it.

    The 0-blocking arms are the ones that must stay conditional. This asserts
    the condition survives, phrased against the two tokens that carry it.
    """
    # Read from the composed constants, not the module's source text: the
    # clause is built from string pieces (`gates.FIX_ORDER` and its neighbours), so a
    # source grep sees it split across literals and cannot find it.
    from lib import critic_consolidate as cc

    text = cc._IF_YOU_FIX_SOME + (PLUGIN / "lib" / "critic_consolidate.py").read_text()
    assert "exits 3 (`no review needed`) when the fixes touch nothing judgeable" in cc._IF_YOU_FIX_SOME, (
        "the 0-blocking arm lost its condition — it now prescribes a "
        "re-cover round regardless of whether the commit moved any coverage"
    )
    assert "cost-of-commit" in text, (
        "the 0-blocking arm no longer names the pre-commit price check"
    )


# ---------------------------------------------------------------------------
# The post-fix coverage rule has one home (#723)
# ---------------------------------------------------------------------------
#
# One rule — what closes a coverage gap after a fix, and which tree a
# verify-resolutions pass graded — was restated in five carriers, and #722's fix
# shipped a wrong reading of it (a commit-SET test where the code compares
# TREES) in two of them at once. The construction that replaced the copies:
#
# - the discriminator (which tree a pass grades, and why) is derived once, in
#   `review-cycle.md` § Verify-resolutions anchoring and demotion;
# - the operator-facing consequence is one string, `gates.POST_FIX_COVERAGE`,
#   keyed on what a pass PRINTS about work it left out rather than on a
#   prediction of the discriminator — so a correction to the discriminator does
#   not reach it — and composed by both code carriers: the blocking remedy (PR
#   gate and Stop hook) and the PR gate's `uncovered` remedy;
# - the prose carriers (the PR skill's sequencing, the Critic skill's exit-3
#   qualifier, building.md's Resolve findings) point at the derivation and
#   restate neither.
#
# So correcting the operator sentence edits gates.py alone, and correcting the
# discriminator edits review-cycle.md alone (beside the code it describes).

#: The prose carriers, and whether each must cite the derivation. None may
#: restate it. The Critic skill cites nothing: it is the payload every review
#: mode loads, and naming `review-cycle.md` there sends a `chunk` reviewer to a
#: file no review mode opens (`test_v5_methodology`'s fast-path pin) — so its
#: exit-3 qualifier says only that named work sits outside what was graded.
_POINTER_SURFACES = [
    pytest.param(PLUGIN / "skills" / "pr" / "SKILL.md", True, id="pr-skill-step-2-sequencing"),
    pytest.param(PLUGIN / "skills" / "critic" / "SKILL.md", False, id="critic-skill-exit-3"),
    pytest.param(PLUGIN / "methodology" / "building.md", True, id="building-resolve-findings"),
]

#: The discriminator's vocabulary — what a carrier says when it restates WHICH
#: tree a pass anchored instead of pointing at the derivation. Every phrase here
#: was shipped by a carrier before #723 (the control below feeds them back);
#: case-folded, because the carriers emphasised words in caps at whim.
_DISCRIMINATOR_PHRASES = (
    "never saw",
    "re-anchor",
    "anchors on committed head",
    "anchor at committed head",
    "anchored committed head",
    "anchored the working tree",
    "did i commit",
)

_POINTER = "§ Verify-resolutions anchoring"


def _restatements(text: str) -> list[str]:
    folded = text.lower()
    return [p for p in _DISCRIMINATOR_PHRASES if p in folded]


def _gates():
    from lib import gates

    return gates


def test_the_restatement_check_can_fail():
    """Positive control, on the carriers' own pre-#723 sentences: a detector that
    misses these proves nothing about the surfaces it passes."""
    shipped = (
        # pr/SKILL.md Step 2's sequencing bullet
        "The pass anchors on committed HEAD instead when you have committed "
        "content the prior review never saw.",
        # critic/SKILL.md's exit-3 qualifier
        "unless the block names work it left out: both anchor at committed HEAD "
        "over a dirty tree, so that work is unreviewed",
        # building.md's Resolve findings
        "then land them in one commit (in that order — committing first "
        "re-anchors the pass; `review-cycle.md`)",
        # gates.py's uncovered remedy
        "It anchored the WORKING tree unless you had committed CONTENT the prior "
        "review never saw",
        # gates.FIX_ORDER_AFTER_CUMULATIVE
        "(A fix committed after a `cumulative` still infers that pass, but "
        "committing first re-anchors it on committed HEAD.)",
    )
    for sentence in shipped:
        assert _restatements(sentence), sentence


@pytest.mark.parametrize(("path", "cites"), _POINTER_SURFACES)
def test_a_prose_carrier_points_at_the_derivation_and_restates_none_of_it(path: Path, cites: bool):
    text = path.read_text()
    assert not cites or _POINTER in text, (
        f"{path.relative_to(REPO_ROOT)} tells a builder what a fix's commit costs "
        "but no longer cites the derivation — a reader who cannot reach it "
        "cannot tell a stale copy from a current one."
    )
    found = _restatements(text)
    assert not found, (
        f"{path.relative_to(REPO_ROOT)} restates which tree a verify pass anchored "
        f"({found}) instead of pointing at `review-cycle.md`. Each restatement is a "
        "copy the next correction must find; #722 shipped a wrong one in two "
        "carriers at once."
    )


def test_building_md_names_the_fix_order_rather_than_copying_it():
    """building.md's verbatim copy of `gates.FIX_ORDER` made correcting the order
    a two-file edit (the constant, then the guide its pin turned red). The guide
    names where the order is printed; the order is the constant's alone."""
    text = (PLUGIN / "methodology" / "building.md").read_text()
    assert _gates().FIX_ORDER not in text
    assert "`gates.FIX_ORDER`" in text


def _rendered_code_carriers(tmp_path: Path, capsys) -> dict[str, str]:
    """Every operator-facing rendering of the rule, produced by the code that
    prints it: the blocking remedy (the PR gate and the Stop hook share it), the
    PR gate's `uncovered` remedy from a real gate run, and the after-`cumulative`
    exception the review-close directive composes."""
    sys.path.insert(0, str(REPO_ROOT / "tests"))
    from test_cumulative_gate import _branch_repo, _commit, _fact, _run_gate, _tree

    gates = _gates()
    repo = _branch_repo(tmp_path)
    _fact(repo, _tree(repo, "main"), _tree(repo), ["feature.py"])
    _commit(repo, "sneaky.py", "s = 1\n", "unreviewed code")
    rc, _out, err = _run_gate(repo, capsys)
    assert rc == 1 and "uncovered" in err, err  # the subject was reached
    return {
        "blocking": "\n".join(gates.blocking_remedy_lines([{"fid": "R-1"}])),
        "uncovered": err,
        "after-cumulative": gates.FIX_ORDER_AFTER_CUMULATIVE,
    }


def test_both_code_carriers_compose_the_one_operator_sentence(tmp_path, capsys):
    rendered = _rendered_code_carriers(tmp_path, capsys)
    sentence = _gates().POST_FIX_COVERAGE
    for name in ("blocking", "uncovered"):
        assert sentence in rendered[name], f"the {name} remedy no longer composes POST_FIX_COVERAGE"
    for name, text in rendered.items():
        found = _restatements(text)
        assert not found, f"the {name} rendering restates the discriminator: {found}"
    assert _POINTER in sentence, "the operator sentence no longer cites its derivation"


def test_correcting_the_operator_sentence_is_a_one_file_edit(tmp_path, capsys, monkeypatch):
    """#723's demonstration, made mechanical: change the one string and every
    code surface prints the change. A carrier holding its own copy keeps
    printing the old words here and fails."""
    gates = _gates()
    old = gates.POST_FIX_COVERAGE
    corrected = "CORRECTED post-fix rule; see `review-cycle.md` " + _POINTER + " and demotion."
    monkeypatch.setattr(gates, "POST_FIX_COVERAGE", corrected)
    rendered = _rendered_code_carriers(tmp_path, capsys)
    for name in ("blocking", "uncovered"):
        assert corrected in rendered[name], name
        assert old not in rendered[name], name


def test_the_sentence_quotes_tokens_the_dispatcher_actually_prints():
    """`POST_FIX_COVERAGE` is keyed on what a pass PRINTS about work it left out,
    which is what keeps it independent of the discriminator. That holds only
    while the producers still print those tokens: the exit-3 refusal's
    `NOT REVIEWED:` and a reviewing pass's dirty-anchor note."""
    from lib import critic_consolidate as cc

    sentence = _gates().POST_FIX_COVERAGE
    note = cc._dirty_anchor_note("verify-resolutions", ["src/a.py"])
    hook = (PLUGIN / "bin" / "prawduct-hook").read_text()
    assert "`NOT REVIEWED:`" in sentence and "NOT REVIEWED:" in hook
    assert "`NOT in the reviewed scope`" in sentence and "NOT in the reviewed scope" in note
    # The case a pass could not compute at all (the paired review of #723): the
    # exit-3 block's `UNVERIFIED:` and the dirty-anchor note's None branch.
    unknown = cc._dirty_anchor_note("verify-resolutions", None)
    assert "`UNVERIFIED:`" in sentence and "UNVERIFIED:" in hook
    assert "`could NOT be computed`" in sentence and "could NOT be computed" in unknown


def test_the_canonical_anchor_statement_still_names_a_tree_comparison():
    """The home the carriers above point at. If this sentence ever softens,
    their pointers point at nothing and the pins above stop meaning anything."""
    text = (PLUGIN / "skills" / "critic" / "review-cycle.md").read_text()
    assert '"Differs" is a **tree** comparison' in text, (
        "review-cycle.md no longer states the anchor test as a tree comparison "
        "— the carriers pointing at it now point at a statement that does not exist"
    )


def test_the_critic_skill_qualifies_exit_three_for_excluded_work():
    """A `cumulative`/`verify-resolutions` exit 3 means the PR gate is satisfied.
    It does NOT mean the branch is clean: both anchor at committed HEAD over a
    dirty tree, so judgeable uncommitted files sit outside the interval they
    graded and the two gate targets come apart. Reporting "clean" off that exit
    is how unreviewed work reaches a PR."""
    text = (PLUGIN / "skills" / "critic" / "SKILL.md").read_text()
    for token in ("NOT REVIEWED:", "UNVERIFIED:"):
        assert token in text, (
            f"the exit-3 instruction does not tell the reader to look for {token} "
            "— so a refusal that named excluded work would still be relayed as "
            '"the gate is satisfied"'
        )
