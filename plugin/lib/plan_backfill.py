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

**Checkbox state is never CORRECTED on the way in.** Nothing reads an archived
plan's boxes, so "make it look complete first" would be ceremony with no
consumer — and it would put a writer exactly where the rule is that only a
session with the work in context may say which chunk is done. That half is
unchanged and binds both routes.

**It IS a precondition of this sweep, though — since #634 (v3.3.1).** The test
above answers "did the scope ship", never "did the plan finish", and the two come
apart whenever a scope ships partially: a real product archived a plan as
``completed``/``released_in`` with two chunks unbuilt and still live work, having
declined the identical proposal at its two previous cuts. So a plan whose own
``## Status`` does not evidence completion is now *refused and named* rather than
proposed (:func:`_incompleteness_refusal`). This does not put a model in the write
path — the predicate is a deterministic count, and declining moves the judgment to
a human and OUT of the write path. Nor does it strand the descoped plan the
archival norm worries about: that plan was never meant to be archived *completed*
but **superseded**, which needs a human to name a reason, so an explicit
``archive-plan`` — which asks no completeness question at all — is one command
away. The ruling is recorded in ``data-model.md`` § Direction (Ruled 2026-08-11).

**Module boundary.** ``change_log.py`` knows tags and nothing about plans;
``plan_index.py`` knows plans and nothing about tags. Deriving the shipped set
needs both, so the composition lives here rather than pushing tag knowledge down
into the plan reader — the two leaf modules stay ignorant of each other and this
one imports both.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import buildplan_refs, change_log, plan_archive, plan_index

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

    try:
        pointed_at = core.pointer_plan_path(prawduct_dir)
    except OSError:
        return None
    if pointed_at is None:
        return None
    try:
        return pointed_at.resolve()
    except OSError:
        return None


def _incompleteness_refusal(plan_path: Path) -> "str | None":
    """The sweep's extra caution: this plan's own Status forbids archiving it.

    **Deliberately here and not in :func:`plan_archive.refusal_reason`**, even
    though that function is otherwise the single home for refusals. The two
    callers are asking different questions. An explicit ``archive-plan <path>``
    is a human asserting the plan is done, and ``plan_archive``'s own module
    docstring records that an archived plan may legitimately carry unticked
    boxes — nothing reads them again. The *sweep* has no such assertion behind
    it: it selects by a ``release=`` tag on a scope, and a scope can ship while
    chunks of its plan remain unbuilt. Moving this check down would break
    deliberate archiving to fix the automatic kind.

    The preview/write invariant the survey docstring states is unaffected:
    :func:`backfill` archives ``survey()["shipped"]``, so both paths ask this.

    Read failure is a refusal, not a pass — the same direction every other
    guard here takes.
    """
    try:
        content = plan_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return f"cannot read the plan to check completeness: {exc}"
    return buildplan_refs.incompleteness_reason(content)


def survey(prawduct_dir: Path) -> dict:
    """What the backfill would do, without doing any of it.

    Returns ``{has_release_tags, shipped, blocked, unshipped}``. ``shipped`` is
    ``[{path, scope, release}]`` — the plans a run would actually archive.
    ``blocked`` is ``[{path, scope, release, reason}]``: plans the change log
    says shipped but which :func:`plan_archive.refusal_reason` would refuse, plus
    (since #634) those whose own ``## Status`` does not evidence completion —
    see :func:`_incompleteness_refusal` for why that second predicate lives here
    rather than beside the first.
    ``unshipped`` is ``[{path, scope}]``, the live plans it leaves alone.

    **The preview asks the refusal predicate, because a preview that overstates
    permission is worse than none.** Without this the survey answered "would
    archive N finished plan(s)" from the change log alone, so a plan already
    carrying a terminal state, one colliding with an archived namesake, or one
    that cannot be read counted toward N and then refused at ``--apply`` —
    the operator having approved a set on the strength of a number that was
    never achievable. That divergence was already found and closed one layer
    down, in ``archive-plan --dry-run``; this is the same defect one frame up,
    and the fix is the same one: there is a single predicate and both the
    preview and the write ask it.

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
    blocked: list[dict] = []
    unshipped: list[dict] = []
    for plan_path, scope in plan_index.iter_scoped_plan_candidates(artifacts_dir):
        release = shipped_map.get(scope)
        if not release or plan_path.resolve() == active:
            unshipped.append({"path": plan_path, "scope": scope})
            continue
        candidate = {"path": plan_path, "scope": scope, "release": release}
        reason = plan_archive.refusal_reason(
            plan_path, artifacts_dir, state=plan_archive.COMPLETED
        ) or _incompleteness_refusal(plan_path)
        if reason is None:
            shipped.append(candidate)
        else:
            blocked.append({**candidate, "reason": reason})
    return {
        "has_release_tags": versions,
        "shipped": shipped,
        "blocked": blocked,
        "unshipped": unshipped,
    }


def backfill(prawduct_dir: Path, *, date: str, apply: bool = False) -> dict:
    """Archive every plan the change log records as shipped.

    ``date`` has no default and no clock is read here — the caller owns the
    calendar, which is what lets this be tested without freezing time.

    Each plan is stamped ``lifecycle: completed`` and ``released_in: <version>``.
    *Completed* rather than *superseded* because the change log recording a
    release for the scope is evidence that the SCOPE shipped.

    **That is not the same as the plan having finished, and since #634 this no
    longer assumes it is.** The two come apart whenever a scope ships partially,
    and the assumption archived two unbuilt chunks as shipped in a real product.
    :func:`survey` now also asks :func:`_incompleteness_refusal`, so a plan whose
    own ``## Status`` does not evidence completion lands in ``blocked`` with the
    chunk named. Checkboxes are still never *corrected* on the way in — how the
    work ended is a fact worth keeping — and an explicit ``archive-plan`` still
    asks no completeness question at all.

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
