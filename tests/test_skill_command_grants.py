"""Every `prawduct-hook` command a skill tells you to RUN is one it may run.

The failure this pins is quiet and consumer-only. A skill's `allowed-tools` is a
pure-allow list; a command outside it is not something the skill can invoke
without leaving its grant. In THIS repo the gap is invisible, because the two
skills with a broad `Bash(python3 *)` interpreter grant reach
`python3 plugin/bin/prawduct-hook` — the plugin is in the tree here. In a
governed product the plugin is installed elsewhere and the bare `prawduct-hook`
spelling, which is the one every SKILL.md writes, is the only one that works.
`skills/janitor/SKILL.md` already records exactly this reasoning for granting
`backlog cache-query` despite its interpreter grant; this test generalises it.

Found by hand while scrubbing the artifact-lifecycle branch: the archival work
gave doctor, janitor and pr each an `archive-plan` instruction and granted it to
none of them — and doctor's own edit had added the two sibling commands, so the
list was being maintained, just not completely. Four older instances were found
in the same sweep. Prose review had not caught any of them in either direction,
which is the argument for a mechanical check rather than a resolution to be
careful.

**Existing skill-metadata tests guard OVER-permission** (the Critic must not be
able to run pytest — `test_critic_skill_metadata.py`). This is the other
direction, and the two are not substitutes: a skill that cannot run what it
instructs fails silently, by prompting, at the moment a consumer needs it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest


SKILLS_DIR = Path(__file__).resolve().parents[1] / "plugin" / "skills"

#: `prawduct-hook <command>` anywhere. Subcommand families (`backlog pick`,
#: `advisory list`, `evidence status`) are matched at their FIRST word only —
#: grants are written per family (`Bash(prawduct-hook backlog *)`), so the family
#: name is the unit that has to appear.
_INVOCATION_RE = re.compile(r"prawduct-hook ([a-z][a-z0-9-]*)")

#: Commands a skill NAMES but is deliberately not granted. Every entry is a
#: decision with a reason, not a suppression: the whole value of this test is
#: that adding a row is uncomfortable enough to make you check.
#:
#: Two shapes qualify, and nothing else does:
#:   * a CROSS-REFERENCE — the text describes what some *other* flow runs, so
#:     granting it would hand this skill a capability it has no business with;
#:   * a DELIBERATE EXCLUSION — the skill's own protocol states that it must not
#:     run the command, and the missing grant is the mechanism enforcing that.
_NOT_GRANTED: dict[tuple[str, str], str] = {
    # Deliberate exclusion, stated in the Critic's own protocol: "what happens
    # to a completed review's findings — discarded, or brought back — is an
    # operator decision and belongs to the main session, which is why both are
    # absent from your `allowed-tools`."
    ("critic", "critic-discard"): "operator decision, not the reviewer's",
    ("critic", "critic-restore"): "operator decision, not the reviewer's",
    # Deliberate exclusion, and load-bearing: an independent reviewer must never
    # mutate the session it is reviewing. `clear` appears only as the thing the
    # critic-active marker REFUSES.
    ("critic", "clear"): "the review must not mutate the session it reviews",
    # Cross-reference: doctor explains that `init-product`'s starter corpus wrote
    # a marker, and points at `/prawduct:onboard` for onboarding. Doctor covers
    # already-onboarded repos and must not scaffold one.
    ("doctor", "init-product"): "narrative; onboarding belongs to /prawduct:onboard",
    # Cross-reference, and a grant here would be actively wrong: doctor names the
    # evidence store as where a real test count lives, so an operator dropping the
    # hand-maintained `build_state.test_tracking` knows what to read instead.
    # Recording evidence RUNS the product's suite — doctor reports and guides, and
    # never executes the product's own tooling.
    ("doctor", "test-evidence"): "pointer to where the real count lives; recording "
    "it would run the product's suite, which doctor must not do",
    # Cross-reference: names what the RELEASE CHECKLIST runs when gitflow
    # retention ends. The PR flow archives one plan by name; a fleet sweep is
    # not its to run.
    ("pr", "plan-backfill"): "cross-reference to the release checklist",
}


def _skill_files() -> list[Path]:
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def _frontmatter_grant(text: str) -> str | None:
    match = re.search(r"^allowed-tools:(.*)$", text, re.M)
    return match.group(1) if match else None


def test_the_sweep_has_subjects() -> None:
    """A green assert-absent test proves nothing if it swept an empty set."""
    files = _skill_files()
    assert len(files) >= 8, f"only {len(files)} skills found"
    assert any(_frontmatter_grant(p.read_text(encoding="utf-8")) for p in files)


@pytest.mark.parametrize("skill_path", _skill_files(), ids=lambda p: p.parent.name)
def test_every_instructed_command_is_granted(skill_path: Path) -> None:
    name = skill_path.parent.name
    text = skill_path.read_text(encoding="utf-8")
    grant = _frontmatter_grant(text)
    if grant is None:
        pytest.skip(f"{name} declares no allowed-tools (unrestricted)")

    granted = set(_INVOCATION_RE.findall(grant))
    body = text[text.index(grant) + len(grant) :]
    missing = sorted(
        command
        for command in set(_INVOCATION_RE.findall(body))
        if command not in granted and (name, command) not in _NOT_GRANTED
    )
    assert not missing, (
        f"skills/{name}/SKILL.md tells its reader to run "
        f"{', '.join('prawduct-hook ' + c for c in missing)} but does not grant "
        f"{'it' if len(missing) == 1 else 'them'} in allowed-tools. In a governed "
        f"product the bare `prawduct-hook` spelling is the only one that works, so "
        f"the skill will prompt at exactly the moment it is needed. Add the grant, "
        f"or — if the text is a cross-reference to another flow, or the command is "
        f"one this skill must NOT run — add it to _NOT_GRANTED with the reason."
    )


def test_no_stale_exemptions() -> None:
    """An exemption outlives the sentence that earned it.

    A row here is a standing claim that some skill still names some command. If
    the mention goes away the row must go too — otherwise the list slowly
    becomes a place where a real grant can hide.
    """
    stale = []
    for (name, command), reason in _NOT_GRANTED.items():
        path = SKILLS_DIR / name / "SKILL.md"
        if not path.is_file():
            stale.append((name, command, "skill no longer exists"))
            continue
        if command not in _INVOCATION_RE.findall(path.read_text(encoding="utf-8")):
            stale.append((name, command, f"no longer mentioned ({reason})"))
    assert not stale, f"stale _NOT_GRANTED rows: {stale}"
