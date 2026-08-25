"""Coherence tripwires for what a governed repo tells the next person who clones it.

Four surfaces describe the same mechanism, in files no single reviewer opens
together: `README.md` (what an owner reads when deciding what to tell their team),
`plugin/skills/onboard/SKILL.md` (what the agent says at onboarding),
`documentation/MIGRATION.md` (what a cutover promises afterwards), and the
`CLAUDE.md` governance anchor (the only one that reaches a session without the
plugin). Prose has no compiler, and this particular prose describes a mechanism
**prawduct does not control** — Claude Code's plugin activation — so it can go
false with nothing in this repo changing. That is what happened: as of Claude
Code v2.1.195 a plugin sourced from a repository is no longer auto-installed from
a project's `enabledPlugins`, and three shipped documents went on promising that
it was, for releases.

That class of decay is why these are tripwires rather than assertions about
wording. The measured behaviour is recorded in this repo's plugin-absent-clone
investigation artifact; what is pinned here is only the part that made the docs
actively harmful — **they are what an owner reads when deciding what to tell
their team, so a false promise of automatic activation suppresses the one message
that would close the gap.**

**Two guards, and only one of them is derived — the distinction matters, because
the first version of this module claimed to catch "the claim, not the wording"
while in fact matching four literal phrasings.** It shipped green over
`MIGRATION.md`'s "everyone who clones the repo gets the plugin automatically",
sixty lines above the paragraph retiring it, in the same commit. A phrase list
cannot make that claim; it can only ever catch the phrasings someone already
thought of.

* :data:`_RETIRED_CLAIMS` is the phrase list, kept for what it is: known-false
  wordings, cheap, matched anywhere in the file. It is a backstop, not the guard.
* :func:`test_clone_claims_are_discharged_where_they_are_made` is the derived
  one. It needs no list of wordings: **any paragraph that talks about cloning and
  the plugin together must also discharge the install step**, because that is the
  structural property a false promise necessarily lacks — a paragraph claiming
  activation is automatic is exactly a paragraph that does not tell you to
  install anything. It catches rewordings nobody has written yet, and it catches
  the one that shipped.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Self-sufficient on sys.path (mirrors tests/test_anchor_repair.py).
if str(_REPO_ROOT / "plugin") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "plugin"))

from lib.migrate_plugin import PLUGIN_ID  # noqa: E402

#: The command every surface must name, built from the install contract rather
#: than frozen here. A literal in this file would be one more home for the plugin
#: id — and the one that keeps passing after a marketplace rename, because a test
#: asserting a stale string against stale docs agrees with itself.
_INSTALL_COMMAND = f"claude plugin install {PLUGIN_ID}"

#: Every surface that describes clone-time activation to a human.
_CLONE_SURFACES = (
    "README.md",
    "plugin/skills/onboard/SKILL.md",
    "documentation/MIGRATION.md",
)

#: Claims that were true before Claude Code v2.1.195 and are false now. Matched as
#: patterns rather than exact sentences: the defect is the CLAIM, and a reworded
#: copy of a false claim is the same defect. Each pattern is anchored on the verb
#: that makes it a promise, so ordinary mentions of installing the plugin — which
#: every one of these files must still make — do not trip it.
_RETIRED_CLAIMS = {
    "the plugin installs itself on clone": re.compile(
        r"plugin\s+auto-?instal", re.I
    ),
    "activation is automatic for the next person": re.compile(
        r"auto-?activates?\s+the\s+plugin", re.I
    ),
    "Claude Code prompts for the install": re.compile(
        r"prompts?\s+each\s+(developer|contributor|teammate)", re.I
    ),
    "no setup step for the next person": re.compile(
        r"no\s+setup\s+step\s+for\s+the\s+next\s+person", re.I
    ),
}


@pytest.mark.parametrize("rel", _CLONE_SURFACES)
@pytest.mark.parametrize("claim", sorted(_RETIRED_CLAIMS))
def test_no_surface_promises_automatic_activation(rel, claim):
    """The negative half, and the half that matters.

    Each of these three files carried one of these claims at some point, and each
    is read by someone deciding what to tell their team. A document that says
    activation is automatic does not merely fail to help — it suppresses the
    message ("everyone installs the plugin once") that closes the gap.
    """
    text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
    match = _RETIRED_CLAIMS[claim].search(text)
    assert match is None, (
        f"{rel} claims {claim!r} ({match.group(0)!r}) — Claude Code has not "
        "auto-installed a repository-sourced plugin since v2.1.195, so a clone on a "
        "machine without prawduct runs ungoverned and silent"
    )


@pytest.mark.parametrize("rel", _CLONE_SURFACES)
def test_every_surface_names_the_install_step(rel):
    """The positive half: saying nothing is not the same as telling the truth.

    Deleting the false claim alone would leave each document silent about a step
    the next person must take — which is the state the investigation found the
    *product* in, reproduced in the docs.
    """
    text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
    assert _INSTALL_COMMAND in text, (
        f"{rel} describes clone-time setup but never names the one command that "
        "actually installs the plugin"
    )


#: A paragraph is making a clone claim when it mentions cloning and the plugin
#: together — that is the shape of every promise about what the next person gets.
_CLONE_MENTION = re.compile(r"\bclon(?:e|es|ed|ing)\b", re.I)
_PLUGIN_MENTION = re.compile(r"\bplugin\b", re.I)

#: What discharges such a claim: naming the install step, or saying plainly that
#: it does not happen for them. Deliberately a *family of discharges* rather than
#: one required sentence — the surfaces legitimately phrase it several ways, and
#: pinning one phrasing would make this the same phrase-list guard one level up.
_DISCHARGED = re.compile(
    r"claude plugin install"
    r"|installs? (?:it|the plugin|that) once"
    r"|each contributor"
    r"|does not install"
    r"|not install the plugin"
    r"|installs nothing",
    re.I,
)


@pytest.mark.parametrize("rel", _CLONE_SURFACES)
def test_clone_claims_are_discharged_where_they_are_made(rel):
    """The derived guard: a clone claim must discharge the install step in place.

    Not "somewhere in the file" — *in the paragraph making the claim*. A reader
    of `MIGRATION.md` step 1 does not scroll to line 117 before telling their
    team what to do, and that is precisely how the false promise survived: the
    same file already said the opposite twice, further down.

    This needs no catalogue of bad phrasings. A paragraph promising the plugin
    arrives automatically is, structurally, a paragraph that names no install
    step — so the property is checkable without anyone having anticipated the
    wording.
    """
    text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
    undischarged = [
        " ".join(para.split())
        for para in re.split(r"\n\s*\n", text)
        if _CLONE_MENTION.search(para)
        and _PLUGIN_MENTION.search(para)
        and not _DISCHARGED.search(para)
    ]
    assert not undischarged, (
        f"{rel} has {len(undischarged)} paragraph(s) describing what a clone gets "
        "without saying the plugin must be installed once per machine — the reader "
        f"of this paragraph tells their team nothing: {undischarged}"
    )


def test_doctor_grades_the_anchor_by_running_the_command():
    """Health Check #4 must not be satisfied by the marker's mere presence.

    Presence was the whole check before, which is why it graded a lying anchor
    healthy: every anchor shipped before the plugin-absent notice carries the
    sentinel. The check has to ask what the anchor SAYS, and only `reanchor`
    answers that.
    """
    text = (_REPO_ROOT / "plugin/skills/doctor/SKILL.md").read_text(encoding="utf-8")
    check4 = text.split("4. **Static governance anchor**", 1)[1].split("\n5. ", 1)[0]
    assert "prawduct-hook reanchor" in check4
    # All four non-healthy statuses route somewhere; `stale-modified` in
    # particular must not be described as repairable, because the repair declines
    # it by design and an offer that cannot be honoured is worse than none.
    for status in ("stale", "stale-modified", "absent", "unreadable"):
        assert f"`{status}`" in check4, f"Health Check #4 does not say what `{status}` means"
    assert "--apply" in check4, "the repair must be offered explicitly, not implied"
