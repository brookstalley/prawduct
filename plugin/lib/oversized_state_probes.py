"""Post-sync advisory probes for oversized governance files.

Replaces the bare ``print`` ``cmd_clear`` used to emit about
``.prawduct/project-state.yaml``. That note had three defects, and each one is
the reason for a design choice here.

**It prescribed cuts to content the measured file did not contain.** All three
of its bullets — completed build-plan chunk detail, per-chunk test history, and
change-log entries — named things that live in ``build-plan.md`` and
``change-log.md``. It measured one file and prescribed edits to two others it
never inspected, so an agent following it literally found nothing to cut and one
following it loosely started on the wrong file. Here every bullet is gated on a
:class:`_Advice` predicate evaluated against **the file it is advising on**, and
the file named is the file to edit. Silence beats misdirection.

**Its threshold penalised thorough decision recording.** In the product that
reported this, ``project-state.yaml`` was 214 KB of which 78% was
``technical_decisions`` / ``design_decisions`` / ``open_questions`` — recorded
reasoning, which the Reasoned Decisions principle asks for. The only lossless cut
available was 8% of plugin-shipped boilerplate, landing at 4x the ceiling. The
perverse incentive was the actual bug: the more faithfully a repo recorded
reasoning, the louder the framework told it to stop. So the threshold is
repo-configurable (:func:`lib.core.oversized_file_threshold`), and a file whose
bulk *is* recorded reasoning is told so rather than told to cut.

**It could not be dismissed.** A bare ``print`` fires every session forever, and
a repo that has correctly decided not to compact was nagged for months. As an
advisory it is dismissable like any other, and dismissing it is what *records*
that decision.

**One advisory per oversized file**, each with its own ``type``, so a repo can
accept the size of one file and act on another. Evidence carries the path and
nothing else — no size, no count — because evidence is hashed into the advisory
id (``advisory_store.compute_id``) and these files are edited by the sessions
that read them: evidence that moved with the contents would mint a new id on
every edit and silently un-dismiss a decision the owner had already made.

Registered at the composition root (``lib/probe_families.register_all``), not at
import time — the same pattern as the sibling probe modules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .advisory_store import AdvisoryCandidate, Codebase, ProjectState, register_probe
from .core import oversized_file_threshold, resolve_build_plan_path

FEATURE = "governance"
PROBE_VERSION = 1


@dataclass(frozen=True)
class _Advice:
    """One compaction bullet, and the content class that earns it.

    ``present`` is matched against the text of the file being advised on, and
    ``absent`` (when given) must NOT match it. A bullet whose class is not in the
    measured file is never printed — that gating is the whole point of this
    module, so the predicate rides on the bullet rather than being something each
    caller remembers to apply.
    """

    present: re.Pattern[str]
    text: str
    absent: re.Pattern[str] | None = None

    def applies_to(self, text: str) -> bool:
        if self.absent is not None and self.absent.search(text):
            return False
        return bool(self.present.search(text))


@dataclass(frozen=True)
class _Measured:
    """A governance file this probe measures, and the advice that applies to it."""

    #: The advisory ``type``. Stable per file, so each file's advisory is
    #: independently dismissable.
    type: str
    #: Repo-relative path, for the message. The measured path is resolved
    #: separately (a build plan is found through the pointer, not by name).
    rel: str
    advice: tuple[_Advice, ...]


def _key(*names: str) -> re.Pattern[str]:
    """A YAML/markdown key matcher for one content class, at any indent."""
    return re.compile(r"^\s*(?:" + "|".join(names) + r")\s*:", re.MULTILINE)


#: A completed chunk's full record — the single largest thing a `project-state`
#: or a long-lived build plan accumulates, and the one that is pure history once
#: the chunk has shipped.
_CHUNK_DETAIL = _Advice(
    present=_key("deliverables", "acceptance_criteria"),
    text=(
        "completed chunk records can keep `id`, `name` and `status` and drop "
        "`deliverables:` / `acceptance_criteria:` — those describe work already done"
    ),
)



_MEASURED: tuple[_Measured, ...] = (
    _Measured(
        type="oversized-project-state",
        rel=".prawduct/project-state.yaml",
        advice=(
            _CHUNK_DETAIL,
            _Advice(
                present=_key("test_history", "tests_passed", "test_count"),
                text=(
                    "test history can keep the current count and drop the per-chunk rows "
                    "— `prawduct-hook test-status` reads the real result"
                ),
            ),
            _Advice(
                present=_key("change_log", "changelog"),
                text=(
                    "an inline change log belongs in `.prawduct/change-log.md`, which has "
                    "its own readers and its own merge behaviour"
                ),
            ),
        ),
    ),
    _Measured(
        type="oversized-build-plan",
        rel="the active build plan",
        advice=(_CHUNK_DETAIL,),
    ),
    _Measured(
        type="oversized-change-log",
        rel=".prawduct/change-log.md",
        # No static bullets: whether anything can go is computed by the archiver's
        # own selection (see `_change_log_advice`), so the advice and the command
        # it recommends cannot disagree about what moves.
        advice=(),
    ),
)

#: Sections whose bulk is recorded reasoning rather than accumulated history.
#: Their presence changes the message, not the threshold: cutting them is the one
#: compaction the framework must not ask for.
_REASONING_SECTIONS = _key(
    "technical_decisions", "design_decisions", "open_questions", "product_definition"
)


def _change_log_advice(root: Path, text: str, threshold: int) -> tuple[list[str], bool]:
    """``(bullets, archivable)`` for an oversized change log.

    Asks the archiver's own selection rather than describing a rule beside it. The
    advice this replaced forbade deleting tagged entries, which was right and left
    nothing to do: in a tagged log that is nearly every byte, so the nudge fired in
    every product with no available action. Moving history verbatim is lossless, so
    when there is something to move the caller hands the runtime the command; when
    there is not, the bullet says why the file is big.
    """
    from . import change_log_archive  # noqa: PLC0415 — lazy; keeps probe registration light

    prawduct_dir = root / ".prawduct"
    versions = change_log_archive.product_versions(
        text, prawduct_dir / change_log_archive.ARCHIVE_DIR_NAME
    )
    try:
        selection = change_log_archive.select(text, threshold=threshold, versions=versions)
    except change_log_archive.ArchiveRefused:
        return (
            ["a tag line in it is malformed (the release gate names which), and no history "
             "can move out until that entry is fixed"],
            False,
        )
    if not selection.moved:
        return (
            ["its bulk is release-pending (or undated) entries, which stay in the live log "
             "until that work ships — it shrinks at the release"],
            False,
        )
    return (
        [f"{len(selection.moved)} entries of shipped history can move verbatim into "
         f"`.prawduct/change-log-archive/`, leaving {selection.kept_bytes // 1000}KB live — "
         "nothing is deleted, and release-pending entries stay"],
        True,
    )


def _measured_path(measured: _Measured, root: Path) -> Path | None:
    """Where ``measured`` actually lives in this repo, or None if it has no home.

    The build plan is found through the ``active_build_plan`` pointer rather than
    by name — a repo's plan is whatever the pointer resolves to, and measuring a
    guessed filename would nag about the wrong file or about none.
    """
    if measured.type == "oversized-build-plan":
        return resolve_build_plan_path(root / ".prawduct")
    return root / measured.rel


def probe_oversized_governance_file(state: ProjectState, codebase: Codebase):
    """One advisory per governance file over this repo's size threshold.

    Fail-soft throughout: an unreadable or missing file yields no advisory rather
    than a guess. Unlike the sibling probes' unreadable-file ``NOTE:``, silence is
    right here — the fact being reported is a *size*, and a file nothing can read
    is not a file anyone is being asked to compact.
    """
    root = Path(codebase.root)
    threshold = oversized_file_threshold(root / ".prawduct")
    candidates = []
    for measured in _MEASURED:
        path = _measured_path(measured, root)
        if path is None or not path.is_file():
            continue
        try:
            size = path.stat().st_size
            if size <= threshold:
                continue
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        shown = measured.rel
        if measured.type == "oversized-build-plan":
            try:
                shown = str(path.relative_to(root))
            except ValueError:
                shown = str(path)

        bullets = [advice.text for advice in measured.advice if advice.applies_to(text)]
        archivable = False
        if measured.type == "oversized-change-log":
            bullets, archivable = _change_log_advice(root, text, threshold)
        reasoning = bool(_REASONING_SECTIONS.search(text))
        summary = (
            f"{shown} is {size // 1000}KB, over this repo's {threshold // 1000}KB nudge "
            "threshold — every reader of it pays that once per session"
        )
        if bullets:
            summary += ". What is actually in it and can go: " + "; ".join(bullets)
        elif not reasoning:
            summary += (
                ". Nothing this nudge knows how to name is in it, so the cut — if there "
                "is one — is a judgement about this file's own content"
            )
        if reasoning:
            summary += (
                ". Note that recorded reasoning (`technical_decisions`, `design_decisions`, "
                "`open_questions`) is in it, and that is not the thing to cut — it is the "
                "methodology working"
            )
        if archivable:
            # Its own construction site, with literal copy: moving history is
            # mechanical and lossless, so the owner has nothing to weigh and the
            # runtime has a command — unlike every other file measured here.
            candidates.append(
                AdvisoryCandidate(
                    type=measured.type,
                    evidence=(f"{measured.rel} is over the governance-file size threshold",),
                    trigger_summary=summary,
                    owner_action=(
                        "Nothing to decide unless you object: the move is lossless (entries are "
                        "kept verbatim in the archive) and it rides in the next commit of the "
                        "current work."
                    ),
                    recommended_action="prawduct-hook archive-change-log --apply",
                    priority="info",
                )
            )
            continue
        candidates.append(
            AdvisoryCandidate(
                type=measured.type,
                # Path only. See the module docstring: a size in here would mint a
                # new id on every edit and un-dismiss a settled decision.
                evidence=(f"{measured.rel} is over the governance-file size threshold",),
                trigger_summary=summary,
                owner_action=(
                    "Decide whether this file should shrink at all. Keeping it is a real "
                    "answer — if its bulk is decisions you meant to record, cutting them "
                    "costs more than the size does, and dismissing this is how that "
                    "decision gets recorded rather than re-litigated every session. If the "
                    "ceiling itself is wrong for this repo, raise "
                    "`oversized_file_threshold_kb` in project-state.yaml instead."
                ),
                # Empty, deliberately: choosing what to cut from a governance file
                # is a judgement about content, and there is no command that makes
                # it. The old note put its three guesses behind a "Run" prefix.
                # (An archivable change log is the exception, handled above.)
                recommended_action="",
                priority="info",
            )
        )
    return candidates


#: The registry key. ONE registration for a probe that emits several candidate
#: types: ``run_all_probes`` runs each registered record once, so registering the
#: same function per measured file would run it N times and emit N copies of every
#: candidate. Each candidate still carries its own ``type``, which is what keeps
#: the three advisories separately dismissable.
PROBE_TYPE = "oversized-governance-file"


def register() -> None:
    """Register the oversized-governance-file probe. Idempotent."""
    register_probe(FEATURE, PROBE_TYPE, PROBE_VERSION, probe_oversized_governance_file)
