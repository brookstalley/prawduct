"""Phase 0 of the release runbook: is everything on ``develop`` *fit* to ship?

The runbook's historical precondition was ``git diff --stat origin/main
origin/develop`` — non-empty means unreleased content exists, so proceed. That
asks *"is there anything to ship?"*, never *"is everything fit to ship?"*. On
v3.1.2 the two answers diverged: the check passed, and following the promotion
phase literally would have published the backlog-service subsystem with all
four of its go-live blockers still open. Nothing in the procedure would have
noticed; what caught it was incidental (enumerating change-log entries happened
to surface ten from an unexpected subsystem).

That is an **unrecallable** publish — consumers re-resolve ``main`` at their
next session start and there is no recall, only a forward fix. So this gate
fails **closed**: every release-pending scope must be classified, by a human,
as either shipping in this release or withheld behind a named open blocker.
Nothing unclassified.

The classification lives in the release-plan artifact
(``.prawduct/artifacts/release-plan-<version>*.md``) under a
``## Release classification`` table, because a release plan is the artifact a
maintainer already writes per release and the decision belongs next to the
release it governs.

Design note — why a withholding blocker must still be OPEN: the blocker IS the
justification. If it closed, the reason to withhold evaporated and the decision
needs re-taking. Shipping on a stale withholding and withholding on a stale
blocker are the same defect, so the gate names both.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_CHANGE_LOG_REL_PATH = ".prawduct/change-log.md"
_BACKLOG_REL_PATH = ".prawduct/backlog.md"
_ARTIFACTS_REL_DIR = ".prawduct/artifacts"

#: Recognised dispositions in the classification table.
SHIPS = "ships"
WITHHELD = "withheld"

_HEADING_RE = re.compile(r"^##\s+Release classification\s*$", re.IGNORECASE)
_NEXT_HEADING_RE = re.compile(r"^#{1,6}\s+")
#: A backlog id: 2-4 uppercase letters, hyphen, 4 alphanumerics (PFX-XXXX).
_ITEM_ID_RE = re.compile(r"\b([A-Z]{2,4}-[A-Z0-9]{4})\b")


def release_pending_scopes(entries: list) -> list[str]:
    """Scopes with at least one tagged change-log entry carrying no ``release=``.

    Narrower than :func:`views.collect_release_pending_scopes`, which also
    includes ``status=shipped`` scopes so ``regen-views`` can flip plans
    regardless of convention. For *releasability* the question is strictly
    "what has not shipped yet", and the authoritative marker for that is the
    absence of ``release=`` — a status stamp is bookkeeping that can lag, but a
    ``release=`` tag names the release that carried the code.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for entry in entries:
        if entry.tag_line_count <= 0:
            continue
        if entry.tags.get("release"):
            continue
        scope = entry.tags.get("scope")
        if isinstance(scope, str) and scope and scope not in seen:
            seen.add(scope)
            ordered.append(scope)
    return ordered


def parse_classification(content: str) -> tuple[dict[str, tuple[str, str | None]], list[str]]:
    """Parse the ``## Release classification`` table.

    Returns ``(classification, errors)`` where classification maps
    ``scope -> (disposition, blocker_id_or_None)``. Rows are markdown table
    rows: ``| scope | ships |  |`` or ``| scope | withheld | BKL-6J2X |``.

    Malformed rows become errors rather than being skipped: a row a human
    wrote and this parser ignored is exactly the silent-omission class the
    gate exists to prevent.
    """
    classification: dict[str, tuple[str, str | None]] = {}
    errors: list[str] = []
    lines = content.splitlines()

    start = None
    for i, line in enumerate(lines):
        if _HEADING_RE.match(line.strip()):
            start = i + 1
            break
    if start is None:
        return classification, ["no `## Release classification` section"]

    for line in lines[start:]:
        stripped = line.strip()
        if _NEXT_HEADING_RE.match(stripped):
            break
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        scope, disposition = cells[0], cells[1].lower()
        blocker = cells[2].strip() if len(cells) > 2 else ""
        # Header row and its separator.
        if scope.lower() in {"scope", ""} or set(scope) <= set("-: "):
            continue
        if disposition not in {SHIPS, WITHHELD}:
            errors.append(
                f"scope `{scope}`: unrecognised disposition {cells[1]!r} "
                f"(expected `{SHIPS}` or `{WITHHELD}`)"
            )
            continue
        if scope in classification:
            errors.append(f"scope `{scope}`: classified twice")
            continue
        if disposition == WITHHELD:
            match = _ITEM_ID_RE.search(blocker)
            if not match:
                errors.append(
                    f"scope `{scope}`: `{WITHHELD}` requires a blocker item id "
                    "(e.g. `BKL-6J2X`) — a withholding with no named blocker is "
                    "an unrecorded decision"
                )
                continue
            classification[scope] = (WITHHELD, match.group(1))
        else:
            classification[scope] = (SHIPS, None)
    return classification, errors


def _open_item_ids(backlog_content: str) -> set[str]:
    """Ids of backlog items whose status is ``open``."""
    from .backlog import legacy  # noqa: PLC0415 -- lazy: keeps this module's import DAG light

    backlog = legacy.parse_backlog(backlog_content)
    return {
        item.item_id
        for item in backlog.items
        if item.item_id and (item.status or "").strip().lower() == "open"
    }


def _resolve_version(project_dir: Path, release: str | None) -> str | None:
    if release:
        return release if release.startswith("v") else f"v{release}"
    version_file = project_dir / "plugin" / "VERSION"
    try:
        raw = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return f"v{raw}" if raw else None


def _find_release_plan(project_dir: Path, version: str) -> Path | None:
    """The release-plan artifact for ``version``.

    Globbed rather than exact-matched: shipped plans carry a descriptive
    suffix (``release-plan-v3.1.2-pruned.md``), so an exact name would miss
    every real one.
    """
    artifacts = project_dir / _ARTIFACTS_REL_DIR
    matches = sorted(artifacts.glob(f"release-plan-{version}*.md"))
    return matches[0] if matches else None


def check_releasability(project_dir: Path, release: str | None = None) -> int:
    """Phase 0 gate. Exit 0 when every release-pending scope is classified.

    Every failure path returns 1 with a named reason on stderr. Un-evaluable
    state (missing change log, missing release plan) fails closed — the whole
    point is that an unclassified scope must never read as "fine".
    """
    from . import views  # noqa: PLC0415 -- lazy: mirrors coverage.py's import posture

    change_log = project_dir / _CHANGE_LOG_REL_PATH
    try:
        change_log_content = change_log.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"no-change-log: cannot read {_CHANGE_LOG_REL_PATH}: {exc}", file=sys.stderr)
        return 1

    pending = release_pending_scopes(views.parse_change_log(change_log_content))
    if not pending:
        print("releasable: no release-pending scopes — nothing to classify.")
        return 0

    version = _resolve_version(project_dir, release)
    if version is None:
        print(
            "no-version: pass --release vX.Y.Z, or make plugin/VERSION readable.",
            file=sys.stderr,
        )
        return 1

    plan_path = _find_release_plan(project_dir, version)
    if plan_path is None:
        print(
            f"no-release-plan: no `{_ARTIFACTS_REL_DIR}/release-plan-{version}*.md`. "
            f"{len(pending)} scope(s) are release-pending and must be classified "
            f"before publishing: {', '.join(pending)}.",
            file=sys.stderr,
        )
        return 1

    try:
        plan_content = plan_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"unreadable-release-plan: {plan_path}: {exc}", file=sys.stderr)
        return 1

    classification, errors = parse_classification(plan_content)

    try:
        backlog_content = (project_dir / _BACKLOG_REL_PATH).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"no-backlog: cannot read {_BACKLOG_REL_PATH}: {exc}", file=sys.stderr)
        return 1
    open_ids = _open_item_ids(backlog_content)

    unclassified = [s for s in pending if s not in classification]
    stale_blockers: list[str] = []
    orphans: list[str] = []

    for scope, (disposition, blocker) in classification.items():
        if scope not in pending:
            orphans.append(scope)
        if disposition == WITHHELD and blocker and blocker not in open_ids:
            stale_blockers.append(f"{scope} (withheld behind {blocker}, which is not open)")

    problems = list(errors)
    if unclassified:
        problems.append(
            "unclassified scope(s) — name the release each ships in, or the open "
            f"blocker withholding it: {', '.join(unclassified)}"
        )
    if stale_blockers:
        problems.append(
            "withholding blocker(s) no longer open — the reason to withhold is "
            f"gone, so the decision needs re-taking: {'; '.join(stale_blockers)}"
        )
    if orphans:
        problems.append(
            "classified scope(s) with nothing release-pending behind them "
            f"(stale table row?): {', '.join(sorted(orphans))}"
        )

    if problems:
        print(f"not-releasable: {version} — {len(problems)} problem(s).", file=sys.stderr)
        for problem in problems:
            print(f"  ERROR: {problem}", file=sys.stderr)
        print(
            f"  Classification table: {plan_path}. Publishing is irreversible; "
            "every release-pending scope must be accounted for.",
            file=sys.stderr,
        )
        return 1

    shipping = sorted(s for s in pending if classification[s][0] == SHIPS)
    withheld = sorted(
        f"{s} (blocked by {classification[s][1]})"
        for s in pending
        if classification[s][0] == WITHHELD
    )
    print(
        f"releasable: {version} — {len(pending)} release-pending scope(s), "
        f"{len(shipping)} shipping, {len(withheld)} withheld."
    )
    if shipping:
        print(f"  shipping: {', '.join(shipping)}")
    if withheld:
        print(f"  withheld: {', '.join(withheld)}")
    return 0
