"""Re-anchoring an already-onboarded repo — the detector and the offered repair.

``migrate_plugin.apply_governance_anchor`` inserts the governance anchor when a
repo has none, and **returns immediately when the sentinel is already present**. That
is correct for insertion and it is exactly why a *stale* anchor is invisible: a
repo onboarded before the anchor's text changed carries the sentinel, so nothing
in the codebase can tell it apart from a current one. Onboarding shipped the fix
to the empty set — new repos — and left the live fleet, which is entirely
already-onboarded, on whatever text it received.

That gap only started to matter when the anchor's text became *load-bearing for a
reader the plugin cannot reach*. A repo cloned onto a machine without the plugin
loads its instruction files and nothing else prawduct ships: no hooks, no skills, no gates,
and no session output saying so — measured, in this repo's plugin-absent-clone
investigation artifact. Every anchor shipped before that measurement told such a
reader that enforcement was structural and a Stop hook would block them, which is
false in precisely the session that most needs the truth. So this module exists to
converge the fleet onto an anchor that says what is actually true there.

**Detection is by substance, not by a revision tag.** The anchor carries a small
number of load-bearing sentences — the plugin-absent notice, and the rule that
review rigor is stage-keyed — and each is detected by the one token an equivalent
sentence would have to contain (:data:`SUBSTANCE`). The question asked is "does
this anchor say each thing the current one says?", never "which revision is it?".
A revision tag would be a second fact to keep in sync with the thing it describes,
and it would grade an owner who wrote their own equivalent notice as stale — which
is the wrong answer. Substance grades them correct, because they are.

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

**Where the anchor lives.** It belongs in ``AGENTS.md``, which every agent host
reads, and ``CLAUDE.md`` imports it with the one line ``@AGENTS.md`` (#942, #928
D-8). Every anchor shipped before that move sits in ``CLAUDE.md``, so a shipped
anchor found there grades ``legacy-layout``, and the repair moves it.

**The repair is offered, never applied for them.** Both files are the product's
own, edited by the plugin only at the declared seam that ``architecture.md``
§ Direction names. The dry run prints the exact replacement; ``--apply`` writes it
under one informed confirmation covering the whole act, which is the shape
``security-model.md`` § Direction requires and the shape ``learnings_obligation``
and ``norm_index_scaffold`` already use.
"""

from __future__ import annotations

from pathlib import Path

from . import core
from .anchor_archive import (  # noqa: F401 — re-exported: callers and tests read them here
    ANCHOR_V1,
    ANCHOR_V2,
    ANCHOR_V3,
    ANCHOR_V4,
    ANCHOR_V5,
    SUPERSEDED_ANCHORS,
    shipped_anchor_in,
)
from .migrate_plugin import (
    AGENTS_REL,
    ANCHOR_SENTINEL,
    CLAUDE_REL,
    PLUGIN_ID,
    STATIC_ANCHOR,
    anchor_files_are_one,
    apply_governance_anchor,
    imports_agents,
    plan_governance_anchor,
)

STATUS_OK = "ok"
STATUS_STALE = "stale"
STATUS_STALE_MODIFIED = "stale-modified"
STATUS_ABSENT = "absent"
STATUS_LEGACY_BLOCK = "legacy-block"
STATUS_LEGACY_LAYOUT = "legacy-layout"
STATUS_IMPORT_MISSING = "import-missing"
STATUS_UNREADABLE = "unreadable"
STATUS_UNWRITABLE = "unwritable"

#: What makes an anchor current, expressed as the one thing a plugin-less reader
#: can act on. Derived from the install contract for the same reason the anchor
#: itself is (``migrate_plugin.PLUGIN_ID``): the probe and the text it looks for
#: must move together, or the detector starts grading against a command the
#: anchor no longer contains.
NOTICE_PROBE = f"claude plugin install {PLUGIN_ID}"

#: What makes an anchor current on the review-rigor axis: the name of the norm
#: it states (review rigor is *stage-keyed*), which is the one token an owner's
#: own wording of the rule keeps. The sentence itself is free to be reworded; a
#: rewording that drops the norm's name is graded as not stating it, and the
#: detail names what is missing so the owner can judge.
STAGE_PROBE = "stage-keyed"

#: The load-bearing sentences, as ``(token, what it carries, what its absence
#: costs)``. EVERY verdict below that describes a not-current anchor derives its
#: wording from this table by asking which rows the anchor lacks — never from a
#: sentence written for the one revision in mind, because the archive now holds
#: anchors that carry the notice and lack the stage rule, and a fixed "predates
#: the plugin-absent notice" would be flatly false of them.
SUBSTANCE: tuple[tuple[str, str, str], ...] = (
    (
        NOTICE_PROBE,
        "the plugin-absent notice",
        "a session without the plugin is told a Stop hook will block it, which is "
        "false, and a clone is not told how to install it",
    ),
    (
        STAGE_PROBE,
        "the stage-keyed review rule",
        "a session here is told to run the Critic after medium+ work with no word "
        "on what a mid-build review blocks on, so it either escalates every review "
        "or skips the one at the boundary",
    ),
)


def _missing_substance(text: str) -> list[tuple[str, str, str]]:
    """The :data:`SUBSTANCE` rows ``text`` does not carry — empty means current."""
    return [row for row in SUBSTANCE if row[0] not in text]


def _lacks(rows: list[tuple[str, str, str]]) -> tuple[str, str]:
    """``(what is missing, what that costs)`` rendered from the rows, for a detail."""
    names = " and ".join(name for _token, name, _cost in rows)
    costs = "; ".join(cost for _token, _name, cost in rows)
    return names, costs


#: What a current anchor says, rendered once for both the ``ok`` grade and the
#: post-repair report — two surfaces, one sentence, so they cannot drift apart.
_CURRENT_DETAIL = (
    "tells a session without the plugin that governance is off, names "
    f"`{NOTICE_PROBE}`, and says review rigor is {STAGE_PROBE}"
)

def _record_success(result: dict, verb: str) -> None:
    """Turn a graded finding into a report of the write that closed it.

    ``repair`` starts from ``check``'s dict, so without this a successful
    ``--apply`` hands back the status and the detail that DESCRIBED THE DEFECT,
    with only ``applied`` distinguishing it from a refusal. The CLI prints exactly
    that, ``--json`` publishes it, and doctor maps every non-``ok`` status to
    degraded: a repair that worked would be reported as the problem it had just
    fixed. ``norm_index_scaffold`` returns its OK status on success, and this is
    that line.
    """
    result["status"] = STATUS_OK
    result["repairable"] = False
    result["detail"] = f"the governance anchor was {verb} — it now {_CURRENT_DETAIL}"


def _read(path: Path) -> tuple[str | None, str | None]:
    """``(text, None)``, or ``(None, cause)`` when the file cannot be read.

    A binary, mis-encoded or unreadable file is reported rather than crashed on,
    and reported as its own status WITH its cause: a check that could not run
    must never be indistinguishable from one that ran and found nothing — and
    "not decodable" sends an owner to fix an encoding when the file was merely
    unreadable, so the two are not folded into one word.
    """
    try:
        # newline="" — read the file's OWN line endings rather than translating
        # them. `read_text` would hand back LF for a CRLF file, and writing that
        # back reformats every line of a document this module promises to leave
        # untouched outside one swapped region.
        with path.open(encoding="utf-8", newline="") as fh:
            return fh.read(), None
    except UnicodeDecodeError as exc:
        return None, f"is not decodable as UTF-8 ({exc.reason} at byte {exc.start})"
    except OSError as exc:
        return None, f"could not be read ({exc.strerror or exc})"


def _finding(status: str, path: str, repairable: bool, detail: str) -> dict:
    return {"status": status, "path": path, "repairable": repairable, "detail": detail}


def _grade_anchor(rel: str, text: str) -> dict:
    """Grade the anchor block in ``text`` — current, shipped-stale, or edited.

    ORDER IS THE CHECK. A verbatim shipped-stale anchor settles the question
    before the substance probes are asked, because the probes scan the WHOLE
    file: a file whose anchor still promises an unconditional Stop gate, and
    which names the install command anywhere else, would otherwise grade healthy
    while the anchor goes on lying. Asked in this order, the probes only ever
    decide files that carry no anchor prawduct shipped, which is exactly where
    their judgement is wanted.
    """
    matched = shipped_anchor_in(text)
    if matched is None:
        missing = _missing_substance(text)
        if not missing:
            return _finding(STATUS_OK, rel, False, f"the anchor {_CURRENT_DETAIL}")
        names, costs = _lacks(missing)
        return _finding(
            STATUS_STALE_MODIFIED, rel, False,
            f"the anchor in {rel} does not state {names} and does not match any anchor "
            f"prawduct shipped, so it has been edited here — {costs}; this one is "
            "yours to reword rather than prawduct's to replace",
        )
    # The matched archive entry says what THIS anchor lacks, so an anchor that
    # already carries the notice is not accused of predating it.
    names, costs = _lacks(_missing_substance(matched))
    detail = f"the anchor in {rel} is one prawduct shipped"
    if names:
        detail += f" before {names}: {costs}"
    return _finding(STATUS_STALE, rel, True, detail)


_LEGACY_LAYOUT_DETAIL = (
    f"{CLAUDE_REL} carries an anchor prawduct shipped, so a host that reads only "
    f"{AGENTS_REL} (Codex) is told nothing about how this repo is governed; the "
    f"repair moves it to {AGENTS_REL} and leaves `@{AGENTS_REL}` in its place, "
    "so Claude Code still reads it"
)


def _grade(project_dir: Path) -> dict:
    """Grade this repo's governance anchor layout by what it says and where it
    sits. ``repairable`` here is provisional: :func:`check` settles it against
    the one layout plan. What each status means is :func:`check`'s to say.
    """
    project_dir = Path(project_dir)
    texts: dict[str, str | None] = {}
    for rel in (CLAUDE_REL, AGENTS_REL):
        path = project_dir / rel
        if not path.is_file():
            texts[rel] = None
            continue
        text, cause = _read(path)
        if text is None:
            return _finding(
                STATUS_UNREADABLE, rel, False,
                f"{rel} {cause} — the anchor could not be graded, which is not "
                "the same as grading it healthy",
            )
        texts[rel] = text

    # A pre-2.0 file-sync repo carries the heavy PRAWDUCT:BEGIN/END block and no
    # sentinel, so every check below would read it as "no anchor" and the repair
    # would strip that block and reformat the prose around it. That is a
    # migration, performed silently, under a preview promising an insertion. It
    # is `/prawduct:migrate`'s act and takes its own informed approval.
    for rel, text in texts.items():
        if text is not None and core.extract_block(text)[0] is not None:
            return _finding(
                STATUS_LEGACY_BLOCK, rel, False,
                f"{rel} still carries the pre-2.0 PRAWDUCT:BEGIN/END block, so this "
                "repo has not cut over to the plugin — re-anchoring it would mean "
                "stripping that block and rewriting the prose around it, which is "
                "`/prawduct:migrate`'s act and takes its own approval. Run that "
                "first; it installs the current anchor on the way through",
            )

    agents, claude = texts[AGENTS_REL], texts[CLAUDE_REL]

    if anchor_files_are_one(project_dir):
        # Both hosts read the one file, so its anchor is graded where it stands.
        rel = CLAUDE_REL if (project_dir / AGENTS_REL).is_symlink() else AGENTS_REL
        if ANCHOR_SENTINEL in (agents or ""):
            return _grade_anchor(rel, agents or "")
        return _finding(
            STATUS_ABSENT, rel, True,
            f"{rel} (which {AGENTS_REL} and {CLAUDE_REL} share) carries no "
            f"{ANCHOR_SENTINEL} block — the repo's own instructions say nothing "
            "about the governance it is under",
        )

    if agents is not None and ANCHOR_SENTINEL in agents:
        graded = _grade_anchor(AGENTS_REL, agents)
        if graded["status"] != STATUS_OK:
            return graded
        if claude is not None and ANCHOR_SENTINEL in claude:
            if shipped_anchor_in(claude) is not None:
                return _finding(STATUS_LEGACY_LAYOUT, CLAUDE_REL, True, _LEGACY_LAYOUT_DETAIL)
            return _finding(
                STATUS_STALE_MODIFIED, CLAUDE_REL, False,
                f"{CLAUDE_REL} still carries an anchor beside {AGENTS_REL}'s, and it "
                "matches nothing prawduct shipped, so it was edited here — replace "
                f"it with the line `@{AGENTS_REL}` yourself; prawduct will not "
                "rewrite text it did not write",
            )
        if claude is None or not imports_agents(claude):
            return _finding(
                STATUS_IMPORT_MISSING, CLAUDE_REL, True,
                f"{AGENTS_REL} carries the anchor but {CLAUDE_REL} does not import it, "
                f"so Claude Code never reads it — {CLAUDE_REL} needs the line "
                f"`@{AGENTS_REL}`",
            )
        return graded

    if claude is not None and ANCHOR_SENTINEL in claude:
        if shipped_anchor_in(claude) is not None:
            return _finding(STATUS_LEGACY_LAYOUT, CLAUDE_REL, True, _LEGACY_LAYOUT_DETAIL)
        return _finding(
            STATUS_STALE_MODIFIED, CLAUDE_REL, False,
            f"the anchor in {CLAUDE_REL} matches nothing prawduct shipped, so it was "
            f"edited here — move it to {AGENTS_REL} and leave the line "
            f"`@{AGENTS_REL}` in its place; prawduct will not rewrite text it did "
            "not write",
        )

    return _finding(
        STATUS_ABSENT, AGENTS_REL, True,
        f"no {ANCHOR_SENTINEL} block in {AGENTS_REL} or {CLAUDE_REL} — the repo's "
        "own instructions say nothing about the governance it is under",
    )


#: The statuses that are prawduct's to fix — offered as a repair exactly when
#: the layout plan can finish the job.
_PRAWDUCTS_TO_FIX = frozenset({
    STATUS_STALE, STATUS_LEGACY_LAYOUT, STATUS_IMPORT_MISSING, STATUS_ABSENT,
})


def check(project_dir: Path) -> dict:
    """Grade this repo's governance anchor layout. Reads only; writes nothing.

    The anchor belongs in ``AGENTS.md``, and ``CLAUDE.md`` imports it. The two
    "not current" answers that route to different people stay distinct:
    ``stale``, ``legacy-layout``, ``import-missing`` and ``absent`` are
    prawduct's to fix; ``stale-modified`` is the owner's. Whether prawduct can
    fix one is the layout plan's answer, never this grade's own: a repair is
    offered only when the plan's writes complete the layout, and when they
    cannot, the detail says what is in the way and what the owner can do.
    """
    project_dir = Path(project_dir)
    finding = _grade(project_dir)
    if finding["status"] in _PRAWDUCTS_TO_FIX:
        plan = plan_governance_anchor(project_dir)
        finding["repairable"] = bool(plan.writes) and plan.unplaced is None
        if plan.unplaced:
            finding["detail"] += f" — and prawduct cannot fix it here: {plan.unplaced}"
    return finding


def repair(project_dir: Path, apply: bool = False) -> dict:
    """Re-anchor this repo. Dry run by default; ``apply=True`` writes.

    The writes are :func:`migrate_plugin.plan_governance_anchor`'s — the same
    plan the dry run prints — so the preview the owner confirms is exactly what
    ``--apply`` writes. A shipped anchor is swapped by exact match, so the
    product's own text and line endings are untouched by construction. After
    writing, the repo is graded again and that grade is reported: a write that
    did not reach the healthy layout is never reported as one.
    """
    project_dir = Path(project_dir)
    result = dict(check(project_dir))
    result["applied"] = False
    result["replacement"] = None
    result["writes"] = []

    if not result["repairable"]:
        return result

    status = result["status"]
    result["replacement"] = STATIC_ANCHOR.strip()
    plan = plan_governance_anchor(project_dir)
    result["writes"] = [{"path": w.path, "how": w.how, "text": w.text} for w in plan.writes]
    if not apply:
        return result

    try:
        apply_governance_anchor(project_dir)
    except (OSError, UnicodeError) as exc:
        # This command is offered BY `/prawduct:doctor` by name, so an
        # unwritable file must come back as a report. A traceback out of a
        # health check is not a finding, it is a crash.
        result.update({
            "status": STATUS_UNWRITABLE,
            "repairable": False,
            "detail": f"could not write {result['path']}: {exc}",
        })
        return result

    result["applied"] = True
    after = check(project_dir)
    if after["status"] != STATUS_OK:
        result.update({k: after[k] for k in ("status", "path", "repairable", "detail")})
        return result
    verb = {
        STATUS_ABSENT: f"inserted into {AGENTS_REL}",
        STATUS_STALE: f"rewritten in {result['path']}",
        STATUS_LEGACY_LAYOUT: f"moved to {AGENTS_REL}, with {CLAUDE_REL} importing it",
        STATUS_IMPORT_MISSING: f"imported into {CLAUDE_REL}",
    }.get(status, "repaired")
    _record_success(result, verb)
    return result
