"""Every Critic mode that can raise a finding reaches the instance-or-class rule.

The rule — a site-naming finding says whether the defect is only where it
pointed or everywhere that pattern appears — shipped stated in exactly one
place, `review-protocol.md` § Severity Levels. `final` and `cumulative` load
that file. `chunk` and `verify-resolutions` load `goals-1-3.md` and are
forbidden to open the protocol, so for those two the rule did not exist, and
the release notes claimed it did.

That gap is not visible from either carrier: `review-protocol.md` states the
rule correctly and always did, and `goals-1-3.md` reads as complete because a
payload's job is to be self-contained. Only the MAP — which mode loads which
carrier — shows the hole, which is why the map is what this file pins.

**These are a construction, not an enumeration**, which is the rule applied to
itself. A test naming today's two carriers is a longer list of names: it passes
unchanged when a fifth mode is added, when a payload is re-routed, or when the
emission stops firing, and all three are how the gap arrived or could return.
So three separate things are derived rather than asserted:

1. the mode set, from `MODE_TOKEN_TO_VERBOSE` — the dict that defines what a
   mode IS, so a fifth mode fails here until someone says which carrier serves
   it;
2. the mode→payload map, from `review-cycle.md`'s `Protocol read` table — the
   prose home a re-route would edit, so re-routing `cumulative` to
   `goals-1-3.md` in the docs reddens this file instead of silently leaving
   that mode with no rule;
3. DELIVERY, by running `critic-begin` per mode and reading stdout — because
   the rule reaching the reviewer is the whole deliverable, and asserting that
   a constant exists, or that its name appears in the hook's source, is
   satisfied by a comment: every such name also appears in the prose explaining
   the emission, so a source scan stays green after the `print` is deleted.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugin"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib import critic_consolidate as cc  # noqa: E402
from test_critic_consolidate import (  # noqa: E402
    _commit_file,
    _git,
    _init_repo,
    _run_begin,
    _seed_prior_review_with_blocker,
)

CRITIC = ROOT / "skills" / "critic"
PROTOCOL = CRITIC / "review-protocol.md"
GOALS_1_3 = CRITIC / "goals-1-3.md"
REVIEW_CYCLE = CRITIC / "review-cycle.md"

PROTOCOL_TEXT = PROTOCOL.read_text(encoding="utf-8")
DIRECTIVE = cc.FINDING_SCOPE_DIRECTIVE

#: Every mode, from the dict that defines what a mode is.
ALL_MODES = sorted(cc.MODE_TOKEN_TO_VERBOSE)


def _documented_payload_map() -> dict[str, str]:
    """`{mode token: payload filename}` parsed from `review-cycle.md`'s
    `Protocol read` row.

    Read rather than restated because this is the map's PROSE home and the one
    a re-route edits. `GOALS_1_3_MODES` is the code home; a test that asserted
    the code home against itself could never see the two disagree, which is the
    failure mode that put a mode in front of a payload with no rule in it.
    """
    text = REVIEW_CYCLE.read_text(encoding="utf-8")
    # Group into contiguous table blocks and take the one holding the row, so
    # the header is THAT table's first line. Scanning the whole file for a row
    # naming the modes finds prose in a different table instead.
    blocks: list[list[str]] = []
    in_table = False
    for line in text.splitlines():
        if line.lstrip().startswith("|"):
            if not in_table:
                blocks.append([])
                in_table = True
            blocks[-1].append(line)
        else:
            in_table = False
    block = next(b for b in blocks if any("**Protocol read**" in r for r in b))
    header = block[0]
    protocol_row = next(r for r in block if "**Protocol read**" in r)

    def cells(row: str) -> list[str]:
        return [c.strip() for c in row.strip().strip("|").split("|")]

    modes = [c.strip("`") for c in cells(header)[1:]]
    payloads = [c.strip("`") for c in cells(protocol_row)[1:]]
    assert len(modes) == len(payloads), (
        "review-cycle.md's mode header and `Protocol read` row have different "
        "column counts — the table cannot be read, so nothing here can tell "
        "which payload a mode loads"
    )
    return dict(zip(modes, payloads))


DOCUMENTED = _documented_payload_map()


def _carrier_for(mode_token: str) -> str:
    """The text a reviewer in ``mode_token`` actually meets the rule in.

    Total by construction: the payload is looked up in the DOCUMENTED map and
    an unrecognized payload raises, because a mode quietly defaulting to "the
    protocol carries it" is exactly what `verify-resolutions` did.
    """
    payload = DOCUMENTED[mode_token]
    if payload == "goals-1-3.md":
        # This payload has no room for the rule; its readers are handed the
        # directive at dispatch instead. Delivery is pinned below.
        return DIRECTIVE
    if payload == "review-protocol.md":
        return PROTOCOL_TEXT
    raise AssertionError(
        f"mode {mode_token!r} is documented as loading {payload!r}, which this "
        "file knows nothing about — say whether that payload carries the "
        "instance-or-class rule or whether its readers are handed a directive."
    )


# ---------------------------------------------------------------------------
# The map
# ---------------------------------------------------------------------------


def test_every_mode_is_documented() -> None:
    """No mode falls outside the table. A mode the table never names has no
    determinable carrier, and the lookup above would raise rather than guess.
    """
    undocumented = set(ALL_MODES) - set(DOCUMENTED)
    assert not undocumented, (
        f"mode(s) {sorted(undocumented)} exist in MODE_TOKEN_TO_VERBOSE but are "
        "absent from review-cycle.md's Per-Mode Behavior table, so nothing can "
        "say which payload their reviewers load"
    )


def test_the_code_map_matches_the_documented_map() -> None:
    """`GOALS_1_3_MODES` is what the emission fires on; the table is what the
    reviewer's instructions follow. A re-route edits the table, and if the two
    drift the mode reads a payload without the rule AND is handed no directive
    — the original defect, reproduced green.
    """
    documented_goals_1_3 = {
        mode for mode, payload in DOCUMENTED.items() if payload == "goals-1-3.md"
    }
    assert documented_goals_1_3 == set(cc.GOALS_1_3_MODES), (
        f"review-cycle.md says {sorted(documented_goals_1_3)} load goals-1-3.md "
        f"but GOALS_1_3_MODES says {sorted(cc.GOALS_1_3_MODES)}. The set that "
        "reads the payload with no rule in it and the set handed the rule at "
        "dispatch have come apart — one of those modes now meets the "
        "instance-or-class rule nowhere at all."
    )


# ---------------------------------------------------------------------------
# The content, per mode, in whichever carrier serves it
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode_token", ALL_MODES)
def test_the_mode_reaches_the_rule(mode_token: str) -> None:
    carrier = _carrier_for(mode_token)
    assert "`instance`" in carrier and "`class`" in carrier, (
        f"a reviewer in `{mode_token}` mode never meets the instance-or-class "
        "rule. Its findings go back to naming two files when the defect is in "
        "six, which costs a full extra fix round every time."
    )


@pytest.mark.parametrize("mode_token", ALL_MODES)
def test_the_mode_reaches_the_test_that_decides_it(mode_token: str) -> None:
    # The label without its decision procedure is a field to fill in, not a
    # rule: the whole mechanism is that the one-sentence reason is what tells
    # you which answer is right, and it is mechanical rather than a judgement
    # call precisely because the sentence either names your site or does not.
    carrier = _carrier_for(mode_token)
    assert "one sentence" in carrier, (
        f"`{mode_token}`'s carrier states instance-vs-class without the "
        "one-sentence test that decides it — the label becomes a guess."
    )


@pytest.mark.parametrize("mode_token", ALL_MODES)
def test_the_mode_reaches_the_withholding(mode_token: str) -> None:
    # The half with teeth, and the half a trim reaches for first because it
    # reads as elaboration. Without it a class finding closes by listing more
    # addresses, which is the resolution the rule exists to refuse — and the
    # next member to be written is on nobody's list.
    carrier = _carrier_for(mode_token)
    assert "construction" in carrier.lower(), (
        f"`{mode_token}`'s carrier no longer says an unbounded class closes "
        "only by a construction, so a longer list of names reads as a fix."
    )


@pytest.mark.parametrize("mode_token", ALL_MODES)
def test_the_mode_reaches_the_no_defect_answer(mode_token: str) -> None:
    # The mandated cross-checks (priors, learnings, backlog reconciliation)
    # must report even when clean, so they raise notes bounding no defect at
    # all. Without a third answer their reviewers invent one — three findings
    # in one observed review already had — and an invented vocabulary is how a
    # rule with teeth acquires an escape hatch nobody ruled on.
    carrier = _carrier_for(mode_token)
    assert "`none`" in carrier, (
        f"`{mode_token}`'s carrier offers no answer for a mandated cross-check "
        "carrying no defect, so its reviewers will coin one."
    )


# ---------------------------------------------------------------------------
# Delivery — the deliverable itself, exercised rather than grepped
# ---------------------------------------------------------------------------


def _seed_for_verify(repo: Path) -> None:
    """Prior review fact with a blocker, then an uncommitted fix — the state a
    `verify-resolutions` dispatch needs. Mirrors the sibling directive's
    fixture rather than inventing a second one.
    """
    head = _commit_file(repo, "src/app.py", "x = 1\n", "init")
    head_tree = _git(repo, "rev-parse", "HEAD^{tree}").stdout.strip()
    (repo / ".prawduct").mkdir(exist_ok=True)
    _seed_prior_review_with_blocker(repo, head, head_tree=head_tree, head_commit=head)
    (repo / "src/app.py").write_text("x = 2  # fixed\n")


def _dispatch(repo: Path, mode: str):
    """A `critic-begin` in ``mode`` against a fixture that mode will accept."""
    _init_repo(repo)
    if mode == "verify-resolutions":
        _seed_for_verify(repo)
    else:
        _commit_file(repo, "src/app.py", "x = 1\n", "init")
        (repo / ".prawduct").mkdir(exist_ok=True)
        if mode == "cumulative":
            _git(repo, "checkout", "-q", "-b", "feature/demo")
            _commit_file(repo, "src/feat.py", "z = 1\n", "feature work")
        else:
            (repo / "src/app.py").write_text("x = 2\n")
    return _run_begin(repo, "--mode", mode)


@pytest.mark.parametrize("mode", ALL_MODES)
def test_the_directive_is_delivered_to_exactly_the_modes_that_need_it(
    tmp_path, mode: str
) -> None:
    """The deliverable, run rather than described.

    Asserting the constant's CONTENT proves it says the right thing; asserting
    its NAME appears in the hook proves nothing, because the name also appears
    in the comment above the emission. Only stdout answers whether a reviewer
    in this mode is handed the rule — and running it also pins the token→verbose
    conversion at the emission, which no source-text assertion can see.
    """
    result = _dispatch(tmp_path / "r", mode)
    assert result.returncode == 0, f"stderr={result.stderr!r}"
    expected = mode in cc.GOALS_1_3_MODES
    delivered = cc.FINDING_SCOPE_DIRECTIVE in result.stdout
    if expected:
        assert delivered, (
            f"`{mode}` loads goals-1-3.md, which has no room for the "
            "instance-or-class rule, and the dispatch did not hand it the "
            "directive either — that reviewer meets the rule nowhere."
        )
    else:
        assert not delivered, (
            f"`{mode}` already reads the rule in review-protocol.md; "
            "delivering the directive too spends dispatch tokens restating "
            "what the payload says, and a directive that prints on every "
            "dispatch is one the reader learns to skip."
        )


def test_the_directive_sits_between_its_two_siblings(tmp_path) -> None:
    """Order is a deliverable, not a detail, and nothing pinned it before.

    The reviewer decides whether there IS a finding (the severity narrowing),
    then how to write it (this), then what a resolution claims — and the
    resolution warning stays last because it is the only one whose subject can
    weaken a gate, and the reader acts on the tail.
    """
    result = _dispatch(tmp_path / "r", "verify-resolutions")
    assert result.returncode == 0, f"stderr={result.stderr!r}"
    out = result.stdout
    for name, text in (
        ("VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE", cc.VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE),
        ("FINDING_SCOPE_DIRECTIVE", cc.FINDING_SCOPE_DIRECTIVE),
        ("RESOLUTION_IS_A_CLAIM_DIRECTIVE", cc.RESOLUTION_IS_A_CLAIM_DIRECTIVE),
    ):
        assert text in out, f"{name} is missing from a verify-resolutions dispatch"
    assert (
        out.index(cc.VERIFY_RATES_BLOCKING_ONLY_DIRECTIVE)
        < out.index(cc.FINDING_SCOPE_DIRECTIVE)
        < out.index(cc.RESOLUTION_IS_A_CLAIM_DIRECTIVE)
    ), (
        "the dispatch directives are out of order. The scope rule must follow "
        "the severity narrowing (how to write a finding is moot until there is "
        "one) and precede the resolution warning (which stays last, adjacent "
        "to the only claim that can weaken a gate)."
    )


# ---------------------------------------------------------------------------
# Cost
# ---------------------------------------------------------------------------


def _estimate(text: str) -> int:
    """The estimator every budgeted file in this repo uses."""
    return int(len(text.split()) * 1.3)


def test_the_directive_has_a_size_ceiling() -> None:
    """Pinned for the reason its two siblings are, and pinned now because this
    is the edit that created it.

    It is delivered on every `chunk` dispatch — the mode with the tightest
    wall-clock target in the system — so it competes with the review it is
    trying to improve. Two numbers, two jobs: the pin fails on any drift and
    carries the new figure; the ceiling says how much drift is allowed before a
    clause has to move out.
    """
    tokens = _estimate(DIRECTIVE)
    assert tokens == 148, (
        f"FINDING_SCOPE_DIRECTIVE is ~{tokens} tokens; this pin says 148. "
        f"Update it to {tokens} and say in the docstring what paid for the "
        "change — the ceiling below is not a budget to spend."
    )
    assert tokens < 200, (
        f"the directive is ~{tokens} tokens. It rides every chunk dispatch, "
        "which targets 1-2 minutes end to end. Trim, or move a clause to the "
        "file that owns it."
    )


#: Every dispatch directive this module defines, by name. Collected from the
#: module rather than listed, so a directive added for some future mode is
#: metered the day it exists instead of the day someone remembers this file.
DIRECTIVES = {
    name: getattr(cc, name) for name in dir(cc) if name.endswith("_DIRECTIVE")
}

#: The ceiling each mode's reviewer payload must stay under. Keyed by mode so
#: :func:`test_the_per_mode_load_has_a_ceiling` covers whatever `ALL_MODES`
#: holds; a fifth mode reddens :func:`test_every_mode_has_a_ceiling` until
#: someone decides what it may cost, rather than going quietly unmetered.
CEILINGS = {
    "chunk": 2500,
    "verify-resolutions": 3500,
    "final": 3900,
    "cumulative": 3900,
}


def _payload_tokens(mode: str) -> int:
    """The payload FILE half of a mode's load, with no directives counted."""
    return _estimate(
        {
            "goals-1-3.md": GOALS_1_3.read_text(encoding="utf-8"),
            "review-protocol.md": PROTOCOL_TEXT,
        }[DOCUMENTED[mode]]
    )


def _per_mode_payload_tokens(mode: str, dispatch_stdout: str) -> int:
    """What a `mode` reviewer loads before reading a changed line: its payload
    file, plus every directive the dispatch ACTUALLY emitted.

    Which directives a mode gets is read out of `dispatch_stdout` rather than
    re-decided here. A meter that re-states the routing rule agrees with itself
    by construction: it keeps metering the old route after a directive moves,
    and it is blind to a directive it was never told about. Running the
    dispatch and weighing what came back is the only version that cannot.
    """
    total = _payload_tokens(mode)
    for text in DIRECTIVES.values():
        if text in dispatch_stdout:
            total += _estimate(text)
    return total


def test_every_mode_has_a_ceiling() -> None:
    """The meter's own coverage, because an unmetered mode is the failure this
    meter exists to prevent, arriving as an absent test rather than a red one."""
    assert set(CEILINGS) == set(ALL_MODES), (
        f"modes without a payload ceiling: {sorted(set(ALL_MODES) - set(CEILINGS))}; "
        f"ceilings for modes that no longer exist: {sorted(set(CEILINGS) - set(ALL_MODES))}"
    )


def test_the_directives_collected_here_are_the_ones_that_ship() -> None:
    """The collection above is a `dir()` scan, so it is only as good as the
    naming convention. A dispatch printing a directive this scan cannot see
    would make every ceiling below under-count in silence."""
    assert DIRECTIVES, "no directive constants found — the naming convention moved"
    assert "FINDING_SCOPE_DIRECTIVE" in DIRECTIVES
    for name, text in DIRECTIVES.items():
        assert isinstance(text, str) and text.strip(), f"{name} is not deliverable text"


@pytest.mark.parametrize("mode", sorted(cc.GOALS_1_3_MODES))
def test_a_mode_that_receives_a_directive_is_charged_for_it(tmp_path, mode: str) -> None:
    """The meter's directive term, pinned on its own.

    Every ceiling has headroom, so a meter that silently stopped counting
    directives would leave all of them green — and a directive costs the reader
    exactly as much as the same words inside a payload file, which is the whole
    reason this meter is capability-scoped rather than file-scoped.
    """
    result = _dispatch(tmp_path / "r", mode)
    assert result.returncode == 0, f"stderr={result.stderr!r}"
    assert cc.FINDING_SCOPE_DIRECTIVE in result.stdout, (
        f"`{mode}` is in GOALS_1_3_MODES but its dispatch emitted no scope rule"
    )
    charged = _per_mode_payload_tokens(mode, result.stdout)
    assert charged >= _payload_tokens(mode) + _estimate(cc.FINDING_SCOPE_DIRECTIVE), (
        f"a `{mode}` reviewer is handed the scope directive and the meter did "
        "not charge for it — re-routing a rule out of a payload file would then "
        "read as a saving"
    )


@pytest.mark.parametrize("mode", ALL_MODES)
def test_the_per_mode_load_has_a_ceiling(tmp_path, mode: str) -> None:
    """`nonfunctional-requirements.md` § Direction governs unit-cost as *the
    reviewer's payload — what a given mode must load to answer its goals*.
    That is capability-scoped, not file-scoped, and until this pin existed only
    the FILES were metered: `goals-1-3.md` and `review-protocol.md` each had a
    ceiling, each directive had a ceiling, and nothing summed them per reader.

    A rule moved out of a full payload into a dispatch directive therefore left
    every individual meter green while raising what the reader loads — which
    made "add a directive" the default answer to a full file, with no meter
    able to see the third use. This is that meter.
    """
    ceiling = CEILINGS[mode]
    result = _dispatch(tmp_path / "r", mode)
    assert result.returncode == 0, f"stderr={result.stderr!r}"

    total = _per_mode_payload_tokens(mode, result.stdout)
    assert total < ceiling, (
        f"a `{mode}` reviewer now loads ~{total} tokens before reading a single "
        f"changed line, against a ceiling of {ceiling}. Moving a rule from a "
        "payload file into a dispatch directive does not reduce this number — "
        "trim the payload, or cut a clause, rather than re-routing the cost."
    )
