"""One-time backfill of already-shipped build plans into the archive (FL6).

:mod:`lib.plan_archive` gives one plan an end of life. This gives the accumulated
ones theirs — the plans that shipped before archival existed and have been
sitting in the live artifacts directory reading as active work ever since. This
repo alone carries 76 of them; a fleet survey found repos with 16 nested plans
each.

**Why a backfill at all, rather than "from now on".** Archival that only applies
going forward leaves every existing repo in exactly the state this whole change
exists to fix: a directory you have to read to sort. The retroactivity was
declared *migrate*, not *contain*, and this is that sweep.

**Shipped is decided mechanically, and by one test: a plan whose ``scope=``
carries a ``release=`` tag in the change log.** That reuses the tag field the
change-log schema keeps, needs no judgment, and is a fitting last use of the tag
data. Where a product has no release tags at all, nothing is moved — the set is
*proposed* and the operator confirms. Proposing a move is not writing governance
state, so the report-never-write rule that governs checkbox state does not reach
it.

**Checkbox state is explicitly not a precondition, and is not corrected on the
way in.** Nothing reads an archived plan's boxes, so "make it look complete
first" would be ceremony with no consumer — and it would put a writer exactly
where the rule is that only a session with the work in context may say which
chunk is done. Removing that precondition is what makes this fully mechanical;
it was the only step that could not be automated before.

**Module boundary.** ``change_log.py`` knows tags and nothing about plans;
``plan_index.py`` knows plans and nothing about tags. Deriving the shipped set
needs both, so the composition lives here rather than pushing tag knowledge down
into the plan reader — the two leaf modules stay ignorant of each other and this
one imports both.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import change_log, plan_archive, plan_index

CHANGE_LOG_REL = "change-log.md"


#: A change-log entry opens ``## YYYY-MM-DD: title``. The date is compared as a
#: string because ISO dates sort lexicographically, which is the whole reason
#: this format was chosen.
_ENTRY_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def shipped_scopes(change_log_text: str) -> dict[str, str]:
    """``{scope: release}`` for every scope whose work is **finished**.

    **A scope is shipped only if no LATER entry for it is untagged.** The obvious
    rule — "it has a release tag somewhere" — archives a live plan the moment a
    work-stream name is reused, because an older round of `auth` shipping in
    v1.0.0 makes the in-flight `auth` plan look finished. That plan is then moved
    out of the live directory and stamped with a release that did not carry it,
    the ``active_build_plan`` pointer dangles, and every gate reading that pointer
    goes quiet — the failure class this whole change treats as its worst. It is
    not hypothetical and it is not rare: the release checklist runs this sweep
    unattended at every release, so the reuse only has to happen once.

    **Decided by DATE, not by document position.** The obvious cheap version —
    "the first entry for this scope wins, since the log is newest-first" — is
    wrong on half this fleet: 7 of 14 surveyed change logs contain at least one
    out-of-order pair. Every one of 1117 scoped entries surveyed carries a
    parseable date, so the date is both available and reliable where the ordering
    is not.

    An entry whose date cannot be parsed is treated as **newer than anything**
    when untagged, so it withholds the scope rather than releasing it. That is
    the fail-safe direction for a mover: the cost of not archiving is a plan that
    stays visible one release longer; the cost of archiving wrongly is a live
    plan disappearing from under an in-flight chunk.
    """
    newest_tagged: dict[str, tuple[str, str]] = {}
    newest_untagged: dict[str, str] = {}
    for entry in change_log.parse_change_log(change_log_text):
        scope = entry.tags.get("scope")
        if not isinstance(scope, str) or not scope:
            continue
        match = _ENTRY_DATE_RE.match(entry.title)
        release = entry.tags.get("release")
        if isinstance(release, str) and release:
            # An undated *tagged* entry is the weak one: treat it as oldest, so
            # it cannot out-rank a dated untagged entry and release a live scope.
            date = match.group(1) if match else ""
            if scope not in newest_tagged or date > newest_tagged[scope][0]:
                newest_tagged[scope] = (date, release)
        else:
            date = match.group(1) if match else "9999-99-99"
            if date > newest_untagged.get(scope, ""):
                newest_untagged[scope] = date

    shipped: dict[str, str] = {}
    for scope, (tagged_date, release) in newest_tagged.items():
        pending = newest_untagged.get(scope)
        if pending is not None and pending > tagged_date:
            continue  # newer work in flight for this scope
        shipped[scope] = release
    return shipped


def _active_plan_path(prawduct_dir: Path) -> Path | None:
    """The plan ``active_build_plan`` names, resolved, or ``None``.

    Read here rather than passed in so the guard cannot be forgotten by a caller.
    Any failure to read resolves to ``None``, which leaves the date rule as the
    only protection — acceptable, because this is the second of two independent
    guards and neither is load-bearing alone.
    """
    from . import core  # noqa: PLC0415 — local, keeps this module's imports flat

    pointer = core.read_str_yaml_key(
        prawduct_dir / "project-state.yaml", "active_build_plan"
    )
    if not pointer:
        return None
    try:
        return (prawduct_dir / pointer.removeprefix(".prawduct/")).resolve()
    except OSError:
        return None


def survey(prawduct_dir: Path) -> dict:
    """What the backfill would do, without doing any of it.

    Returns ``{has_release_tags, shipped, unshipped}`` where ``shipped`` is
    ``[{path, scope, release}]`` — the plans a run would archive — and
    ``unshipped`` is ``[{path, scope}]``, the live plans it would leave alone.

    ``has_release_tags`` is the fork the operator needs: ``False`` means this
    product does not tag releases, so the mechanical test cannot answer and
    every live plan lands in ``unshipped``. That is not "nothing to do" — it is
    "nobody but you can decide", and the caller must say so rather than
    reporting a clean sweep.
    """
    artifacts_dir = prawduct_dir / "artifacts"
    try:
        text = (prawduct_dir / CHANGE_LOG_REL).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        text = ""
    shipped_map = shipped_scopes(text)
    # Whether the product versions AT ALL, which is a different question from
    # whether any scope currently qualifies. Deriving it from `shipped_map` made
    # a repo whose every scope has newer work in flight report "this product's
    # change log records no releases" — false, and it sends the operator to fix
    # the wrong thing.
    versions = any(
        entry.tags.get("release") for entry in change_log.parse_change_log(text)
    )

    # A plan the session is actively building is never this sweep's to move, and
    # no derived answer overrides that. Archiving it dangles the pointer, and a
    # dangling pointer reads to every gate as "no active build plan" — they stop
    # firing rather than fail, which is the failure mode this work exists to end.
    # The date rule above should already withhold it; this is the guard that does
    # not depend on the change log being written correctly.
    active = _active_plan_path(prawduct_dir)

    shipped: list[dict] = []
    unshipped: list[dict] = []
    for plan_path, scope in plan_index.iter_scoped_plan_candidates(artifacts_dir):
        release = shipped_map.get(scope)
        if release and plan_path.resolve() != active:
            shipped.append({"path": plan_path, "scope": scope, "release": release})
        else:
            unshipped.append({"path": plan_path, "scope": scope})
    return {
        "has_release_tags": versions,
        "shipped": shipped,
        "unshipped": unshipped,
    }


def backfill(prawduct_dir: Path, *, date: str, apply: bool = False) -> dict:
    """Archive every plan the change log records as shipped.

    ``date`` has no default and no clock is read here — the caller owns the
    calendar, which is what lets this be tested without freezing time.

    Each plan is stamped ``lifecycle: completed`` and ``released_in: <version>``.
    *Completed* rather than *superseded* because the change log recording a
    release for the scope is precisely the evidence that the work shipped; the
    plan's own checkboxes are not consulted, and deliberately so.

    Refusals are per-plan and collected, not fatal: a name collision in the
    archive must not abandon a 73-plan sweep partway with no report of where it
    stopped.
    """
    artifacts_dir = prawduct_dir / "artifacts"
    state = survey(prawduct_dir)
    archived: list[dict] = []
    refused: list[dict] = []

    if not apply:
        return {"status": "preview", **state, "archived": [], "refused": []}

    for item in state["shipped"]:
        result = plan_archive.archive_plan(
            item["path"],
            artifacts_dir,
            state=plan_archive.COMPLETED,
            date=date,
            release=item["release"],
        )
        if result["status"] == "archived":
            archived.append(
                {
                    "scope": item["scope"],
                    "release": item["release"],
                    "source": str(result["source"]),
                    "destination": str(result["destination"]),
                }
            )
        else:
            refused.append({"scope": item["scope"], "reason": result.get("reason", "")})
    return {"status": "applied", **state, "archived": archived, "refused": refused}
