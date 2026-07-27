"""Agent-facing prose names BOTH handoff files, never only the machine's.

A preference pin, not a unit test. The original defect was an *affordance*, not
a missing mechanism: the methodology named exactly one handoff filename — the
one the agent must not write — so that is the one agents wrote, and `/clear`
overwrote it. Chunk 01 built the model-owned channel and the guides still had
no name for it.

A guide can only re-create that gap by mentioning the generated file without
its counterpart, which is a structural property of the text.

**Deliberately not a verb list.** The obvious detector ("no sentence tells the
agent to *write* the handoff") keys on which words read as instructions, and
this codebase has twice watched a convention-keyed detector drift out from
under the rule it was guarding — the fix that finally held for build-plan
decoding keys on nothing anyone holds by habit, and so does this.

**What it does not prove**, stated so a future reader does not over-trust it:
co-naming is not adjacency. A file could name both hundreds of lines apart and
still misdirect within a paragraph. It catches the whole-file omission — the
shape the defect actually had — and no more.
"""

from __future__ import annotations

from pathlib import Path

_PLUGIN = Path(__file__).resolve().parent.parent.parent / "plugin"
_REPO = _PLUGIN.parent


class TestHandoffProseNamesBothFiles:
    """Every agent-facing guide that names the generated `.session-handoff.md`
    must also name the model-owned `.handoff-notes.md`.

    The original defect was an affordance, not a mechanism: the guides named one
    file — the one the agent must not write — so that is the one they wrote. A
    guide can only re-create that gap by mentioning the generated file without
    its counterpart, which is a structural property of the text.

    **Deliberately not a verb list.** The obvious detector ("no sentence tells
    the agent to *write* the handoff") keys on which words read as instructions,
    and this branch has twice watched a convention-keyed detector drift out from
    under the rule it was guarding. File-scoped co-naming keys on nothing anyone
    holds by habit.

    **What it does not prove**, stated so a future reader does not over-trust it:
    co-naming is not adjacency. A file could name both hundreds of lines apart
    and still misdirect within a paragraph. It catches the whole-file omission —
    the shape the defect actually had — and no more.
    """

    def _corpus(self) -> list[Path]:
        paths = [_REPO / "CLAUDE.md"]
        for sub in ("methodology", "skills", "docs", "templates"):
            paths.extend(sorted((_PLUGIN / sub).rglob("*.md")))
        return [p for p in paths if p.is_file()]

    def _naming_the_generated_file(self) -> list[Path]:
        return [
            p
            for p in self._corpus()
            if ".session-handoff.md" in p.read_text(encoding="utf-8")
        ]

    def test_the_pin_has_something_to_check(self):
        # A structural guard whose subject gets renamed passes vacuously
        # forever. If this ever finds nothing, the pin is dead, not satisfied.
        named = self._naming_the_generated_file()
        assert named, (
            "no agent-facing guide names `.session-handoff.md` — the pin below "
            "cannot fail, so it is asserting nothing"
        )

    def test_every_mention_is_accompanied_by_the_file_the_agent_owns(self):
        offenders = [
            str(p.relative_to(_REPO))
            for p in self._naming_the_generated_file()
            if ".handoff-notes.md" not in p.read_text(encoding="utf-8")
        ]
        assert not offenders, (
            "these agent-facing guides name `.session-handoff.md` (machine-owned) "
            "without naming `.handoff-notes.md` (the file the agent owns), which is "
            f"the affordance gap that lost cross-session context: {offenders}"
        )
