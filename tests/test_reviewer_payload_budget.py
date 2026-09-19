"""What ONE Critic reviewer loads before it sees a line of diff, priced as a sum.

#850. Every governance prose file carries a token budget and every budget is
green; nothing prices the total, and the total is what a reviewer pays. Between
July and September the budgeted set went 3 files / 10,214 tokens to 11 files /
46,964 — 4.6x — with every individual raise scrutinised and approved on its
merits. No single decision looks wrong, which is exactly why the sum needs an
owner: `nonfunctional-requirements.md` § Direction makes review wall-clock a P0
constraint whose two levers are run-count and **unit-cost via the reviewer's
payload**, and this is the only assertion in the repo pointed at the second.

**Stage-keyed, because the payload is.** #850 quoted one number (~26k) for what
a reviewer reads. The dispatch path falsifies it: `skills/critic/SKILL.md` sends
a `chunk` / `verify-resolutions` reviewer to `goals-1-3.md` and tells it to read
*"nothing else — not the two files below"*, while `final` / `cumulative` gets
the seven-goal protocol, the lifecycle table and the framework checks. Those are
8,743 and 22,714 tokens respectively, so a single ceiling over the union would
price a payload nobody loads and would let the inner stage's cost double without
anything going red. The split mirrors `review-cycle.md`'s own stage-keyed rigor
rule, and it is the reason the `goals-1-3.md` split was built in the first
place.

**Its expected yield, stated so it can be judged later** (the NFR norm requires
a new control to name the yield it expects and emit it observably): this refuses
an edit that grows a reviewer's payload without the grower saying so. It is
prevention, not relief — it shrinks nothing today. If a year passes with no
entry below moving and no raise declared, it fired zero times and the honest
reading is that per-file budgets were already sufficient; retire it then rather
than defend it on principle. The readings are dated and carry what moved them,
so that question is answerable from `git log -p` on this file.

**What turns this red:** any member file growing past the recorded sum, a
ceiling left above its reading after a cut, and a file joining a stage's payload
without joining its sum. That last one is the reason `_payload` derives the
member list from `SKILL.md`'s own routing prose rather than from a literal list
here — a ceiling over a hand-listed set is a prefix of the real set wherever the
set can grow.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent.parent / "plugin"

#: Loaded by every dispatched reviewer regardless of mode: the agent definition
#: is its system prompt, and `SKILL.md` is what routes it to a protocol.
_ALWAYS = ("agents/critic-reviewer.md", "skills/critic/SKILL.md")

#: The protocol file(s) each stage opens, per `SKILL.md` "Read your protocol —
#: one file, chosen by the mode you just resolved."
_BY_STAGE = {
    "inner": ("skills/critic/goals-1-3.md",),
    "boundary": (
        "skills/critic/review-protocol.md",
        "skills/critic/review-cycle.md",
        "skills/critic/framework-checks.md",
    ),
}

#: The measured sum per stage, and what moved it. Same contract as
#: `LAST_MEASURED_INJECTED_TOKENS`: this is the READING; the ceiling below sits
#: exactly one over it, so nothing is banked.
LAST_MEASURED_PAYLOAD_TOKENS = {
    # Established 2026-09-19 (#850, review-cost-decision Chunk 03). Baseline, so
    # nothing "paid" for it — it records where the sum stood when it first got
    # an owner. Both figures are AFTER Chunk 02's declared raise.
    "inner": 8743,
    "boundary": 22714,
}

PAYLOAD_CEILINGS = {
    "inner": 8744,
    "boundary": 22715,
}


def estimate_tokens(text: str) -> int:
    """The repo's one token estimator, imported rather than reimplemented.

    A second copy could disagree with the per-file budgets these sums are made
    of, and two estimators disagreeing about one corpus is worse than none —
    the per-file tests would stay green while this one refused an edit they
    permitted.
    """
    from test_v5_methodology import estimate_tokens as canonical  # noqa: PLC0415

    return canonical(text)


def _routed_protocol_files() -> set[str]:
    """Every `skills/critic/*.md` that `SKILL.md` routes a reviewer to.

    Derived from the routing prose, not from `_BY_STAGE`, so the two can
    disagree — which is the whole point. A new protocol file added to the
    dispatch and not to a stage's sum would otherwise be invisible here, and
    invisible is how the 4.6x happened.
    """
    text = (PLUGIN / "skills" / "critic" / "SKILL.md").read_text(encoding="utf-8")
    return {f"skills/critic/{m}" for m in re.findall(r"\$\{CLAUDE_SKILL_DIR\}/([\w-]+\.md)", text)}


def _payload(stage: str) -> dict[str, int]:
    return {f: estimate_tokens((PLUGIN / f).read_text(encoding="utf-8"))
            for f in _ALWAYS + _BY_STAGE[stage]}


@pytest.mark.parametrize("stage", sorted(LAST_MEASURED_PAYLOAD_TOKENS))
def test_the_payload_is_non_empty_and_holds_what_it_names(stage):
    """A check whose subject is a SET asserts the set is non-empty and contains
    what the check names — otherwise green means nothing was summed, forever."""
    payload = _payload(stage)
    assert payload, f"the {stage} payload is empty — this sum measures nothing"
    for member, tokens in payload.items():
        assert tokens > 0, f"{member} contributed 0 tokens — it was not read"
    assert "skills/critic/SKILL.md" in payload
    assert "agents/critic-reviewer.md" in payload, (
        "the agent definition is a dispatched reviewer's system prompt and is "
        "paid on every review — a sum that omits it understates every stage"
    )


@pytest.mark.parametrize("stage", sorted(LAST_MEASURED_PAYLOAD_TOKENS))
def test_the_recorded_reading_is_current(stage):
    actual = sum(_payload(stage).values())
    expected = LAST_MEASURED_PAYLOAD_TOKENS[stage]
    assert actual == expected, (
        f"the {stage} reviewer payload is ~{actual} tokens; "
        f"LAST_MEASURED_PAYLOAD_TOKENS says {expected}. Update the entry to {actual} "
        f"and say what moved it — and raise the ceiling with it, by declaration and "
        f"with a reason that prices the SUM rather than the file you edited. Funding "
        f"it by trimming an unrelated clause is what this control exists to stop."
    )


@pytest.mark.parametrize("stage", sorted(PAYLOAD_CEILINGS))
def test_the_payload_is_under_its_ceiling(stage):
    actual = sum(_payload(stage).values())
    ceiling = PAYLOAD_CEILINGS[stage]
    assert actual < ceiling, (
        f"the {stage} reviewer payload is ~{actual} tokens, over its {ceiling} "
        f"ceiling. This is unit-cost under `nonfunctional-requirements.md` § Direction: "
        f"every {stage} review pays it, so moving content between members of this same "
        f"set buys nothing — the assertion sums them. Move it OUT of the reviewer's "
        f"path, or declare the raise."
    )


@pytest.mark.parametrize("stage", sorted(PAYLOAD_CEILINGS))
def test_each_ceiling_is_exactly_one_over_its_reading(stage):
    """The ratchet, asserted rather than remembered — a ceiling left above its
    reading after a cut silently re-funds the growth the cut paid for."""
    reading = LAST_MEASURED_PAYLOAD_TOKENS[stage]
    ceiling = PAYLOAD_CEILINGS[stage]
    assert ceiling == reading + 1, (
        f"the {stage} ceiling is {ceiling} against a recorded reading of {reading}. "
        f"Set it to {reading + 1} in the same edit that moved the reading."
    )


def test_every_routed_protocol_file_belongs_to_a_stage():
    """The half a hand-listed set cannot deliver.

    `_BY_STAGE` is a claim about what `SKILL.md` routes to. If someone adds a
    sixth protocol file to the dispatch and not here, every assertion above
    stays green while a reviewer loads prose nothing prices — which is the 4.6x
    mechanism, arriving one file at a time.
    """
    routed = _routed_protocol_files()
    assert routed, (
        "no `${CLAUDE_SKILL_DIR}/*.md` routing found in SKILL.md — the deriver "
        "stopped matching, so this guard went blind rather than the dispatch "
        "having shrunk"
    )
    summed = {f for files in _BY_STAGE.values() for f in files} | set(_ALWAYS)
    unpriced = routed - summed
    assert not unpriced, (
        f"SKILL.md routes a reviewer to {sorted(unpriced)}, which no stage's sum "
        f"includes — add each to the stage that opens it and re-record both readings"
    )


def test_the_inner_stage_is_materially_cheaper_than_the_boundary():
    """The property the split exists to protect, pinned as a RELATION so it
    survives both numbers moving.

    `review-cycle.md` keys rigor to stage, and `SKILL.md` sends the inner modes
    to a self-contained `goals-1-3.md` precisely so the common case stops paying
    the seven-goal protocol. `verify-resolutions` alone is 58% of all review
    volume, so an inner payload that crept toward the boundary's would be the
    single most expensive regression available here — and every per-file budget
    would stay green through it.
    """
    inner = sum(_payload("inner").values())
    boundary = sum(_payload("boundary").values())
    assert inner * 2 < boundary, (
        f"the inner payload ({inner}) is no longer less than half the boundary's "
        f"({boundary}). The `goals-1-3.md` split exists to keep the common mode "
        f"cheap; if the inner protocol has genuinely earned this much, say so and "
        f"move this bound — but do not let it drift."
    )
