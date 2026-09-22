"""What ONE Critic reviewer loads before it sees a line of diff, priced as a sum.

#850. Every governance prose file carries a token budget and every budget is
green; nothing prices the total, and the total is what a reviewer pays. Between
July and September the budgeted set went 3 files / 10,214 tokens to 11 files /
46,964 — 4.6x — with every individual raise scrutinised and approved on its
merits. No single decision looks wrong, which is exactly why the sum needs an
owner: `nonfunctional-requirements.md` § Direction makes review wall-clock a P0
constraint whose two levers are run-count and **unit-cost via the reviewer's
payload**, and this is the only assertion in the repo pointed at the second.

**Route-keyed, because the payload is.** #850 quoted one number (~26k) for what
a reviewer reads. The dispatch path falsifies it: `skills/critic/SKILL.md` sends
a `chunk` / `verify-resolutions` reviewer to `goals-1-3.md` and tells it to read
*"nothing else — not the two files below"*, while `final` / `cumulative` gets
the seven-goal protocol, the lifecycle table and the framework checks. Those are
8,743 and 22,714 tokens respectively, so a single ceiling over the union would
price a payload nobody loads and would let the cheap route's cost double without
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
ceiling left above its reading after a cut, and a file joining a route's payload
via an explicit `${CLAUDE_SKILL_DIR}/…` route without joining its sum.

**What it deliberately does NOT cover, because a ceiling that overstates its
reach is worse than none.** `_routed_protocol_files` matches only the explicit
`${CLAUDE_SKILL_DIR}/…` form, so four classes of read are outside these sums
and outside the "cannot join the dispatch without joining a sum" guarantee:

* **Bare-name sibling reads.** `SKILL.md` blesses them explicitly ("When the
  protocol refers to a sibling by bare name, read it from `${CLAUDE_SKILL_DIR}/`")
  and `review-protocol.md` already uses them, so a protocol file can be pulled
  in by a citation this deriver cannot see.
* **Files one level up.** The same paragraph routes reviewers to
  `../../docs/principles.md` and `../../docs/norms.md`; neither is summed
  here.
* **Files the protocol reaches by a different route entirely.**
  `skills/backlog/cache-reads.md`, which the backlog reconciliation pass opens.
* **Product-side reads.** A reviewer opens the governed product's own
  `.claude/rules/learnings/` — `core.md` alone is ~22,514 tokens in THIS repo,
  comparable to the whole priced single-pass-full route below, so the largest
  single input to a real review is not in any figure here and varies per product.
  (Recompute rather than trusting that figure: it moves with every rules edit,
  and this sentence's previous version quoted a BYTE count as tokens.)

Widening the deriver to chase citations was considered and not built: it would
have to resolve prose references transitively, and a guard that silently
resolves *some* of them is the false-completeness this note exists to prevent.
The sums below are a floor on the framework-controlled payload, not a total.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parent.parent / "plugin"

#: The payload ROUTES, keyed by what actually selects a file set: the protocol
#: a mode routes to, and which actor is reading.
#:
#: **Not `stage`, which was the first cut and was wrong.** `review-cycle.md`
#: puts `final` in the *inner* STAGE ("any review of an uncommitted or delta
#: interval — `chunk`, `final`, `verify-resolutions`") while routing it to the
#: seven-goal protocol, so a STAGE-keyed model priced `final` at a third of
#: what it loads and its keys collided with the manifest's own `stage` field.
#: The governing norm names the right axis: `nonfunctional-requirements.md`
#: § Direction says unit-cost is "the reviewer's *payload* (what a given MODE
#: must load to answer its goals)".
#:
#: **And the actor differs, not just the mode.** `chunk` and
#: `verify-resolutions` are always single-pass, so no `critic-reviewer` body is
#: ever loaded for them — charging the agent definition to those modes prices
#: ~2.5k nobody reads. Conversely a dispatched reviewer never opens `SKILL.md`;
#: the coordinator does, and then dispatches.
PAYLOAD_ROUTES = {
    # The single-pass fork on the cheap protocol — `chunk`, `verify-resolutions`.
    "single-pass-inner": (
        "skills/critic/SKILL.md",
        "skills/critic/goals-1-3.md",
    ),
    # The single-pass fork on the full protocol — `final`/`cumulative` whose
    # derived roster is single-pass.
    "single-pass-full": (
        "skills/critic/SKILL.md",
        "skills/critic/review-protocol.md",
        "skills/critic/review-cycle.md",
        "skills/critic/framework-checks.md",
    ),
    # One dispatched `critic-reviewer` on a coordinator roster. Its system
    # prompt replaces `SKILL.md`, and a roster multiplies this by its size.
    "dispatched-reviewer": (
        "agents/critic-reviewer.md",
        "skills/critic/review-protocol.md",
        "skills/critic/review-cycle.md",
        "skills/critic/framework-checks.md",
    ),
}

#: The measured sum per route, and what moved it. Same contract as
#: `LAST_MEASURED_INJECTED_TOKENS`: this is the READING; the ceiling below sits
#: exactly one over it, so nothing is banked.
LAST_MEASURED_PAYLOAD_TOKENS = {
    # Established 2026-09-19 (#850, review-cost-decision Chunk 03), re-keyed the
    # same day from `stage` to route after the cumulative review found `final`
    # is an inner-STAGE mode carrying the full protocol. Baseline, so nothing
    # "paid" for it — it records where each route stood when it first got an
    # owner. All three are AFTER the declared raise in `review-cost-decision`
    # Chunk 02 (naming the plan because a later plan had a Chunk 02 too, and a
    # bare chunk number does not survive the plan being archived).
    # +30 to every route on 2026-09-19: finding R-12's correction to the
    # severity bound, which lands in `goals-1-3.md` and `review-protocol.md` —
    # one of which every route loads. Declared, and the first thing this control
    # priced: the per-file tests saw two +30s, and only this sum shows that a
    # dispatched reviewer on a three-reviewer roster pays it three times.
    # 2026-09-19 (#640 re-apply, review-convergence Chunk 01): the
    # `rule-unenforced` substitution lands in `critic-reviewer.md` (+289) and
    # `review-cycle.md` (+83). A DECLARED raise — the rule is a new obligation,
    # not a restatement, and it exists to REMOVE rounds by substituting one
    # finding for N.
    #
    # This is the first edit the route sums priced that the per-file budgets
    # could not, and the asymmetry is the whole argument for them:
    # `critic-reviewer.md` carries NO per-file ceiling, so its +289 was
    # invisible to every other control — and a coordinator roster pays it once
    # per reviewer, so the dispatched route moves +372 against single-pass-full's
    # +83. The cheap route is untouched, which is the split working.
    # RATCHETED with the readings below (review-interval-extension, 2026-09-22):
    # the chunk/final interval rewording (it now starts at the covered
    # frontier) was paid in place and came out smaller, and the ceilings follow.
    # RAISED (review-interval-extension, 2026-09-22, cumulative finding): the demotion
    # property's list of commits `chunk`/`final` cannot reach — behind an open blocker,
    # before any review, across a base sync — was cut to one case in the same branch and
    # restored. DECLARED, not paid: the sentence has no duplicate to fund it, and a builder
    # reading the one-case version demotes the other three to a mode that cannot see them.
    # RATCHETED (review-interval-extension PR review, 2026-09-22): "the uncommitted interval" dropped from SKILL.md's
    # fall-through sentence, now false for an extended chunk interval.
    # RAISED +29 on both single-pass routes (review-scrub-seams, 2026-09-22),
    # DECLARED: `SKILL.md`'s exit-table row for `critic-begin` 6, which every
    # single-pass review loads and the dispatched route does not. Priced against
    # the SUM: 29 tokens per review against the full round (median ~300s) the
    # exit-1 fallback would buy every time the store is unusable — a round that
    # cannot help. Drafted at +81; the remedy moved to the refusal's stderr.
    "single-pass-inner": 6332,
    # RAISED +43 (reviewer-prompt-file-list, 2026-09-22), DECLARED: all of it the
    # `review-protocol.md` template change that sends coordinator reviewers to the
    # manifest for their file sets; see the dispatched-reviewer entry for the price.
    "single-pass-full": 20420,
    # +2 in the same chunk: adapting the ported prose off the retired
    # `learnings.md` vocabulary onto `.claude/rules/learnings/`, which the
    # single-resolver guard requires and which a near-verbatim port carries
    # in from its source branch by construction.
    #
    # +28 on 2026-09-20, a DECLARED raise, all of it in `critic-reviewer.md`
    # (`review-cycle.md`'s matching edit is token-neutral). The 2026-09-20
    # cumulative found the `rule-unenforced:` instruction naming a field that
    # does not exist: it said to open the finding's `summary`, but a Critic
    # partial has none — `merge_findings` maps the reviewer's `name` to the
    # fact's `title`, and a partial's top-level summary is never persisted. The
    # token therefore landed where no query could read it and the control's
    # yield was structurally ZERO from the day it shipped. The +28 names the
    # right field and carries the reason inline so the next port cannot
    # repeat it. Priced against the SUM and not the file: this is the cheapest
    # possible repair of a control the route is already paying 2791 tokens to
    # carry, and paying that in full for nothing is the actual waste.
    #
    # +119 on 2026-09-22 (reviewer-prompt-file-list), a DECLARED raise: +43 in
    # `review-protocol.md` (the template now names the manifest instead of pasting
    # the file lists) and the rest in `critic-reviewer.md`, which says the sets come
    # from the manifest and adds a guard: an unreadable manifest, one whose `id` is
    # not this review's, or one with no subject files ends in `dispatch-mismatch`.
    # The guard is the price of removing the lists — without it a reviewer that
    # cannot read the manifest reviews nothing and reports clean. Priced against the
    # SUM: the coordinator no longer writes each list three times in a row, which on
    # a large review is thousands of output tokens on the dispatch critical path.
    "dispatched-reviewer": 19607,
}

PAYLOAD_CEILINGS = {
    "single-pass-inner": 6333,
    "single-pass-full": 20421,
    "dispatched-reviewer": 19608,
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

    Derived from the routing prose, not from `PAYLOAD_ROUTES`, so the two can
    disagree — which is the whole point. A new protocol file added to the
    dispatch and not to a route's sum would otherwise be invisible here, and
    invisible is how the 4.6x happened.
    """
    text = (PLUGIN / "skills" / "critic" / "SKILL.md").read_text(encoding="utf-8")
    return {f"skills/critic/{m}" for m in re.findall(r"\$\{CLAUDE_SKILL_DIR\}/([\w-]+\.md)", text)}


def _payload(route: str) -> dict[str, int]:
    return {f: estimate_tokens((PLUGIN / f).read_text(encoding="utf-8"))
            for f in PAYLOAD_ROUTES[route]}


@pytest.mark.parametrize("route", sorted(LAST_MEASURED_PAYLOAD_TOKENS))
def test_the_payload_is_non_empty_and_holds_what_it_names(route):
    """A check whose subject is a SET asserts the set is non-empty and contains
    what the check names — otherwise green means nothing was summed, forever.

    The per-route entry assertions pin the ACTOR distinction that the first cut
    of this file got wrong: the single-pass fork enters through `SKILL.md` and
    never loads an agent body, while a dispatched reviewer's system prompt IS
    the agent body and it never opens `SKILL.md`.
    """
    payload = _payload(route)
    assert payload, f"the {route} payload is empty — this sum measures nothing"
    for member, tokens in payload.items():
        assert tokens > 0, f"{member} contributed 0 tokens — it was not read"
    if route.startswith("single-pass"):
        assert "skills/critic/SKILL.md" in payload, (
            "a single-pass fork enters through SKILL.md — a sum omitting it "
            "understates what that route loads"
        )
        assert "agents/critic-reviewer.md" not in payload, (
            "single-pass modes dispatch no subagent, so charging them the agent "
            "definition prices a file nobody reads"
        )
    else:
        assert "agents/critic-reviewer.md" in payload, (
            "the agent definition is a dispatched reviewer's system prompt"
        )
        assert "skills/critic/SKILL.md" not in payload, (
            "a dispatched reviewer never opens SKILL.md — the coordinator does"
        )


@pytest.mark.parametrize("route", sorted(LAST_MEASURED_PAYLOAD_TOKENS))
def test_the_recorded_reading_is_current(route):
    actual = sum(_payload(route).values())
    expected = LAST_MEASURED_PAYLOAD_TOKENS[route]
    assert actual == expected, (
        f"the {route} reviewer payload is ~{actual} tokens; "
        f"LAST_MEASURED_PAYLOAD_TOKENS says {expected}. Update the entry to {actual} "
        f"and say what moved it — and raise the ceiling with it, by declaration and "
        f"with a reason that prices the SUM rather than the file you edited. Funding "
        f"it by trimming an unrelated clause is what this control exists to stop."
    )


@pytest.mark.parametrize("route", sorted(PAYLOAD_CEILINGS))
def test_the_payload_is_under_its_ceiling(route):
    actual = sum(_payload(route).values())
    ceiling = PAYLOAD_CEILINGS[route]
    assert actual < ceiling, (
        f"the {route} reviewer payload is ~{actual} tokens, over its {ceiling} "
        f"ceiling. This is unit-cost under `nonfunctional-requirements.md` § Direction: "
        f"every {route} review pays it, so moving content between members of this same "
        f"set buys nothing — the assertion sums them. Move it OUT of the reviewer's "
        f"path, or declare the raise."
    )


@pytest.mark.parametrize("route", sorted(PAYLOAD_CEILINGS))
def test_each_ceiling_is_exactly_one_over_its_reading(route):
    """The ratchet, asserted rather than remembered — a ceiling left above its
    reading after a cut silently re-funds the growth the cut paid for."""
    reading = LAST_MEASURED_PAYLOAD_TOKENS[route]
    ceiling = PAYLOAD_CEILINGS[route]
    assert ceiling == reading + 1, (
        f"the {route} ceiling is {ceiling} against a recorded reading of {reading}. "
        f"Set it to {reading + 1} in the same edit that moved the reading."
    )


def test_every_routed_protocol_file_belongs_to_a_route():
    """The half a hand-listed set cannot deliver.

    `PAYLOAD_ROUTES` is a claim about what `SKILL.md` routes to. If someone adds
    a sixth protocol file to the dispatch and not here, every assertion above
    stays green while a reviewer loads prose nothing prices — which is the 4.6x
    mechanism, arriving one file at a time.
    """
    routed = _routed_protocol_files()
    assert routed, (
        "no `${CLAUDE_SKILL_DIR}/*.md` routing found in SKILL.md — the deriver "
        "stopped matching, so this guard went blind rather than the dispatch "
        "having shrunk"
    )
    summed = {f for files in PAYLOAD_ROUTES.values() for f in files}
    unpriced = routed - summed
    assert not unpriced, (
        f"SKILL.md routes a reviewer to {sorted(unpriced)}, which no route's sum "
        f"includes — add each to the route that opens it and re-record its reading"
    )


def test_the_cheap_protocol_route_stays_materially_cheaper():
    """The property the `goals-1-3.md` split exists to protect, pinned as a
    RELATION so it survives both numbers moving.

    `SKILL.md` sends `chunk` and `verify-resolutions` to a self-contained
    `goals-1-3.md` precisely so the common case stops paying the seven-goal
    protocol. `verify-resolutions` alone is 58% of review volume, so a cheap
    route creeping toward the full one is the single most expensive regression
    available here — and every per-file budget would stay green through it.

    Stated between the two SINGLE-PASS routes, which differ only by protocol
    file, so the comparison isolates the split rather than mixing in the actor
    difference.
    """
    cheap = sum(_payload("single-pass-inner").values())
    full = sum(_payload("single-pass-full").values())
    assert cheap * 2 < full, (
        f"the cheap protocol route ({cheap}) is no longer less than half the full "
        f"one ({full}). The `goals-1-3.md` split exists to keep the common mode "
        f"cheap; if the cheap protocol has genuinely earned this much, say so and "
        f"move this bound — but do not let it drift."
    )
