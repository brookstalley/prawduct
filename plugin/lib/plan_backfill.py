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

from pathlib import Path

from . import change_log, plan_archive, plan_index

CHANGE_LOG_REL = "change-log.md"


def shipped_scopes(change_log_text: str) -> dict[str, str]:
    """``{scope: release}`` for every scope the change log records as shipped.

    A scope shipping more than once keeps its **latest** release by document
    order — the change log is newest-first, so the first entry seen for a scope
    is the most recent one, and that is the release worth stamping on the plan.
    """
    shipped: dict[str, str] = {}
    for entry in change_log.parse_change_log(change_log_text):
        scope = entry.tags.get("scope")
        release = entry.tags.get("release")
        if isinstance(scope, str) and isinstance(release, str) and scope and release:
            shipped.setdefault(scope, release)
    return shipped


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

    shipped: list[dict] = []
    unshipped: list[dict] = []
    for plan_path, scope in plan_index.iter_scoped_plan_candidates(artifacts_dir):
        release = shipped_map.get(scope)
        if release:
            shipped.append({"path": plan_path, "scope": scope, "release": release})
        else:
            unshipped.append({"path": plan_path, "scope": scope})
    return {
        "has_release_tags": bool(shipped_map),
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
