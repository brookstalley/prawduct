"""Re-anchoring an already-onboarded repo — the detector and the offered repair.

``migrate_plugin.apply_claude_anchor`` inserts the governance anchor when a repo
has none, and **returns immediately when the sentinel is already present**. That
is correct for insertion and it is exactly why a *stale* anchor is invisible: a
repo onboarded before the anchor's text changed carries the sentinel, so nothing
in the codebase can tell it apart from a current one. Onboarding shipped the fix
to the empty set — new repos — and left the live fleet, which is entirely
already-onboarded, on whatever text it received.

That gap only started to matter when the anchor's text became *load-bearing for a
reader the plugin cannot reach*. A repo cloned onto a machine without the plugin
loads ``CLAUDE.md`` and nothing else prawduct ships: no hooks, no skills, no gates,
and no session output saying so — measured, in this repo's plugin-absent-clone
investigation artifact. Every anchor shipped before that measurement told such a
reader that enforcement was structural and a Stop hook would block them, which is
false in precisely the session that most needs the truth. So this module exists to
converge the fleet onto an anchor that says what is actually true there.

**Detection is by substance, not by a revision tag.** The question asked is "does
this anchor tell a plugin-less reader how to end the condition?", answered by
looking for the install command. A revision tag would be a second fact to keep in
sync with the thing it describes, and it would grade an owner who wrote their own
equivalent notice as stale — which is the wrong answer. Substance grades them
correct, because they are.

**Replacement is exact-match against what prawduct shipped, never a guess at where
the anchor ends.** The sentinel is deliberately a single marker rather than a
BEGIN/END pair (so ``core.extract_block`` never treats the anchor as a strippable
block), which means there is no delimiter saying where the anchor stops and the
product's own prose starts. Rather than infer one — every inference here is a
chance to eat a line the owner wrote — the repair swaps a *known previous anchor,
matched byte for byte*, out of :data:`SUPERSEDED_ANCHORS`. An anchor that has been
edited matches nothing, is reported as ``stale-modified``, and is left for the
owner. The cost is one frozen string per anchor revision; the anchor is a stable
contract that changes rarely, and the alternative cost is a repair that can
silently truncate a product's instructions.

**The repair is offered, never applied for them.** ``CLAUDE.md`` is the product's
own file, edited by the plugin only at the declared seam that ``architecture.md``
§ Direction names. The dry run prints the exact replacement; ``--apply`` writes it
under one informed confirmation covering the whole act, which is the shape
``security-model.md`` § Direction requires and the shape ``learnings_obligation``
and ``norm_index_scaffold`` already use.
"""

from __future__ import annotations

from pathlib import Path

from .migrate_plugin import (
    ANCHOR_SENTINEL,
    PLUGIN_ID,
    STATIC_ANCHOR,
    apply_claude_anchor,
)

#: The product file carrying the anchor, repo-relative.
CLAUDE_REL = "CLAUDE.md"

STATUS_OK = "ok"
STATUS_STALE = "stale"
STATUS_STALE_MODIFIED = "stale-modified"
STATUS_ABSENT = "absent"
STATUS_UNREADABLE = "unreadable"

#: What makes an anchor current, expressed as the one thing a plugin-less reader
#: can act on. Derived from the install contract for the same reason the anchor
#: itself is (``migrate_plugin.PLUGIN_ID``): the probe and the text it looks for
#: must move together, or the detector starts grading against a command the
#: anchor no longer contains.
NOTICE_PROBE = f"claude plugin install {PLUGIN_ID}"

# --- The archive ------------------------------------------------------------
# Every anchor prawduct has shipped that predates the plugin-absent notice,
# stripped exactly as ``apply_claude_anchor`` writes them, oldest first.
#
# **Append, never edit.** An entry here is a historical artifact — the literal
# bytes sitting in real repos — not a description of the current anchor, so
# "tidying" one makes the repos it exists to match unmatchable.
#
# **Derive this set from the release tags, never from "the anchor I just
# replaced."** Written the second way, it first shipped covering v2.3.0+ only and
# missing the 31 releases from v2.0.0 to v2.2.3, which differ by a single line
# (`/prawduct:building`, from before the methodology reader was renamed). The
# cohort that gap stranded was the OLDEST repos — and it stranded them while
# reporting that their anchor had been edited locally, blaming an owner for text
# prawduct wrote. ``test_anchor_repair.py`` now reconstructs the shipped set from
# the tags themselves and fails when an entry is missing, so the next revision
# cannot repeat it.

#: v2.0.0 – v2.2.3 (31 releases).
ANCHOR_V1 = """<!-- PRAWDUCT:ANCHOR — static governance pointer managed by the prawduct plugin. Keep it small and version-free: principles, methodology, and the active version live in the plugin and are injected at session start. -->

## Governance (Prawduct)

This repo is governed by **Prawduct**, installed as a Claude Code plugin — not as
committed framework files. The principles, methodology, Critic protocol, and PR
review live in the plugin and are read on demand (run `/prawduct:methodology`);
they are intentionally not copied into this repo.

**Before writing any code, STOP and read the build cycle: `/prawduct:building`.**
Skipping it is the #1 governance failure.

The hardest rules (everything else is in the plugin):

- **Tests are contracts** — fix the code, never weaken a test.
- **No "pre-existing" exception** — fix what you find, or flag why you can't.
- **Never silently drop a requirement** — say so explicitly.
- **Run `/prawduct:critic` after medium+ work** — never write Critic findings
  yourself; the independence is the value.

**Enforcement is structural:** the plugin's Stop hook runs at session end and
**blocks** if code changed against an active build plan with no Critic findings.
The session-start banner shows the active version and what changed — this anchor
stays version-free."""

#: v2.3.0 – v3.4.0 (26 releases). Differs from :data:`ANCHOR_V1` only in the
#: build-cycle line, which gained the `methodology` reader.
#:
#: **This one entry is derived rather than frozen, which bends "append, never
#: edit" and is worth knowing before you edit V1:** a change to V1 silently
#: changes V2 too. Kept because the alternative is 1.3 KB of near-duplicate
#: literal whose only difference is one line — and because the coupling is
#: guarded rather than trusted: `test_the_archive_covers_every_anchor_prawduct_\
#: ever_shipped` reconstructs both from the release tags and fails if either
#: stops matching what shipped.
ANCHOR_V2 = ANCHOR_V1.replace(
    "`/prawduct:building`",
    "`/prawduct:methodology building`",
)

SUPERSEDED_ANCHORS: tuple[str, ...] = (ANCHOR_V1, ANCHOR_V2)


def _read(path: Path) -> str | None:
    """The file's text, or ``None`` when it is not decodable as UTF-8.

    A binary or mis-encoded ``CLAUDE.md`` is reported rather than crashed on, and
    reported as its own status: a check that could not run must never be
    indistinguishable from one that ran and found nothing.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def check(project_dir: Path) -> dict:
    """Grade this repo's governance anchor. Reads only; writes nothing.

    Five answers, and the two "not current" ones are deliberately distinct
    because they route to different people: ``stale`` is prawduct's to fix and
    ``stale-modified`` is the owner's. Collapsing them would either offer a repair
    that cannot run or refuse one that can.
    """
    path = Path(project_dir) / CLAUDE_REL

    if not path.is_file():
        return {
            "status": STATUS_ABSENT,
            "path": CLAUDE_REL,
            "repairable": True,
            "detail": (
                f"no {CLAUDE_REL} — the repo carries no governance anchor at all, so a "
                "session here is told nothing about how it is governed"
            ),
        }

    text = _read(path)
    if text is None:
        return {
            "status": STATUS_UNREADABLE,
            "path": CLAUDE_REL,
            "repairable": False,
            "detail": (
                f"{CLAUDE_REL} is not decodable as UTF-8 — the anchor could not be "
                "graded, which is not the same as grading it healthy"
            ),
        }

    if ANCHOR_SENTINEL not in text:
        return {
            "status": STATUS_ABSENT,
            "path": CLAUDE_REL,
            "repairable": True,
            "detail": (
                f"{CLAUDE_REL} carries no {ANCHOR_SENTINEL} block — the repo's own "
                "instructions say nothing about the governance it is under"
            ),
        }

    if NOTICE_PROBE in text:
        return {
            "status": STATUS_OK,
            "path": CLAUDE_REL,
            "repairable": False,
            "detail": (
                "the anchor tells a session without the plugin that governance is off "
                f"and names `{NOTICE_PROBE}`"
            ),
        }

    if not any(old in text for old in SUPERSEDED_ANCHORS):
        return {
            "status": STATUS_STALE_MODIFIED,
            "path": CLAUDE_REL,
            "repairable": False,
            "detail": (
                "the anchor predates the plugin-absent notice and does not match any "
                "anchor prawduct shipped, so it has been edited here — a clone of this "
                "repo onto a machine without the plugin is told nothing, and this one "
                "is yours to reword rather than prawduct's to replace"
            ),
        }

    return {
        "status": STATUS_STALE,
        "path": CLAUDE_REL,
        "repairable": True,
        "detail": (
            "the anchor is one prawduct shipped before the plugin-absent notice: it "
            "tells a session the Stop hook will block it, which is false when the "
            "plugin is not installed — and a clone is not told how to install it"
        ),
    }


def repair(project_dir: Path, apply: bool = False) -> dict:
    """Re-anchor this repo. Dry run by default; ``apply=True`` writes.

    Replacement is a single exact-match swap of a superseded anchor for the
    current one, so everything around it — the product's own title, its
    instructions, its line endings outside the swapped region — is untouched by
    construction rather than by care. The ``absent`` case delegates to
    ``apply_claude_anchor``, which already owns insertion; there is no second
    inserter here to disagree with it.
    """
    project_dir = Path(project_dir)
    result = dict(check(project_dir))
    result["applied"] = False
    result["replacement"] = None

    if not result["repairable"]:
        return result

    if result["status"] == STATUS_ABSENT:
        result["replacement"] = STATIC_ANCHOR.strip()
        if apply:
            result["applied"] = apply_claude_anchor(project_dir)
        return result

    path = project_dir / CLAUDE_REL
    text = _read(path)
    if text is None:  # pragma: no cover — check() already graded it readable
        result["status"] = STATUS_UNREADABLE
        result["repairable"] = False
        return result

    superseded = next(old for old in SUPERSEDED_ANCHORS if old in text)
    current = STATIC_ANCHOR.strip()
    result["replacement"] = current

    if apply:
        # `1` — replace the one occurrence found. A CLAUDE.md carrying the anchor
        # twice is malformed, and swapping both would hide that rather than fix it.
        path.write_text(text.replace(superseded, current, 1), encoding="utf-8")
        result["applied"] = True

    return result
