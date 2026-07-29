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


def scopes_tagged_for(entries: list, version: str) -> set[str]:
    """Scopes already tagged ``release=<version>``.

    Phase 0 must survive being re-run *after* Phase 1. Phase 1 step 3 stamps
    ``release=vX.Y.Z`` on the shipping entries, which removes those scopes from
    the release-pending set — so a second Phase 0 run would see the
    classification table referencing scopes that are no longer pending and
    report every one as a stale orphan. A scope tagged for *this* release is
    the successful outcome of the classification, not an orphan.
    """
    tagged: set[str] = set()
    for entry in entries:
        if entry.tags.get("release") != version:
            continue
        scope = entry.tags.get("scope")
        if isinstance(scope, str) and scope:
            tagged.add(scope)
    return tagged


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
    rows: ``| scope | ships |  |`` or ``| scope | withheld | ABC-1234 |``.

    A row with a recognised shape but bad content (unknown disposition,
    duplicate scope, `withheld` with no blocker id) becomes an **error**: a row
    a human wrote and this parser ignored is the silent-omission class the gate
    exists to prevent. Two cases are skipped rather than reported, because they
    are table syntax and not data — the header/separator rows, and any line with
    fewer than two cells (a decorative or truncated row that names no scope, so
    there is nothing to report about).
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
                    "(e.g. `ABC-1234`) — a withholding with no named blocker is "
                    "an unrecorded decision"
                )
                continue
            classification[scope] = (WITHHELD, match.group(1))
        else:
            classification[scope] = (SHIPS, None)
    return classification, errors


def _open_item_ids(backlog_content: str) -> set[str]:
    """Ids of backlog items that are live and ``status: open``.

    Section-aware on purpose: an item under ``## Archive`` can still carry
    ``status: open`` in its metadata bar (the archive move and the status flip
    are separate edits), and treating an archived item as a live blocker is the
    same stale-withholding error this gate exists to catch.
    """
    from .backlog import legacy  # noqa: PLC0415 -- lazy: keeps this module's import DAG light

    backlog = legacy.parse_backlog(backlog_content)
    return {
        item.item_id
        for item in backlog.items
        if item.item_id
        and (item.status or "").strip().lower() == "open"
        # Reuse the backlog module's own predicate rather than matching
        # "archive": it covers the whole resolved end of the lifecycle
        # (resolved / done / completed / archive, by substring). A product
        # whose backlog says `## Resolved` would otherwise get this defect
        # back, and only prawduct's own `## Archive` heading hid it.
        and not legacy._is_resolved_section(item.section or "")
    }


def _markdown_backlog_is_authoritative(project_dir: Path) -> bool:
    """True when ``.prawduct/backlog.md`` is the live backlog.

    ``data-model.md`` § Direction: once ``backlog_service_repo`` is set the
    markdown is **frozen history**, and every item archived at cutover still
    parses as ``status: open``. Reading it post-cutover would make
    :func:`_open_item_ids` return the whole frozen roster, so a withholding
    blocker that has since closed would still look open and the gate would
    print ``releasable:`` on exactly the stale decision it exists to catch.
    Every other ``lib/`` reader checks this scalar first; this is not an
    exception.
    """
    from . import advisory_store  # noqa: PLC0415 -- lazy: keeps this module's import DAG light
    from . import backlog_probes  # noqa: PLC0415

    try:
        state = advisory_store.load_project_state(project_dir)
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- unreadable state must fail CLOSED, and the loader's failure modes are not enumerable here
        print(f"  (project-state unreadable: {exc})", file=sys.stderr)
        return False
    return not backlog_probes.post_cutover(state)


def _resolve_version(project_dir: Path, release: str | None) -> str | None:
    """The release under test.

    ``--release`` is authoritative. The ``plugin/VERSION`` fallback exists for
    ad-hoc mid-cycle checks and is **wrong by construction during Phase 0**:
    the runbook bumps ``VERSION`` in Phase 1 step 7, *after* this gate runs, so
    at gate time the file still names the PREVIOUS release. The fallback says
    so out loud rather than quietly grading the wrong release — the same
    refusal-to-guess posture as the argv scan in the CLI wrapper.
    """
    if release:
        return release if release.startswith("v") else f"v{release}"
    version_file = project_dir / "plugin" / "VERSION"
    try:
        raw = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    print(
        f"NOTE: no --release given, falling back to plugin/VERSION (v{raw}). During "
        "Phase 0 that is the PREVIOUS release — VERSION is bumped later, in Phase 1 "
        "step 7. Pass --release vX.Y.Z to grade the release you are cutting.",
        file=sys.stderr,
    )
    return f"v{raw}"


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

    entries = views.parse_change_log(change_log_content)
    pending = release_pending_scopes(entries)
    if not pending:
        # Name the denominator: "0 pending" from a change log the parser could
        # not read looks identical to "0 pending" because everything shipped,
        # and only one of those is a pass.
        tagged = sum(1 for e in entries if e.tag_line_count > 0)
        print(
            f"releasable: no release-pending scopes — nothing to classify "
            f"({len(entries)} change-log entries scanned, {tagged} tagged)."
        )
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

    # Blocker liveness is only consulted when something is actually withheld —
    # a release that withholds nothing needs no backlog read at all.
    withheld_scopes = [s for s, (d, _) in classification.items() if d == WITHHELD]
    open_ids: set[str] = set()
    if withheld_scopes:
        if not _markdown_backlog_is_authoritative(project_dir):
            print(
                "cannot-verify-blockers: this repo has cut over to the GitHub Issues "
                "backlog (`backlog_service_repo` set), so `.prawduct/backlog.md` is "
                "frozen history and cannot say whether a blocker is still open. "
                f"{len(withheld_scopes)} scope(s) are withheld behind blockers that "
                "must be confirmed open by hand before publishing: "
                f"{', '.join(sorted(withheld_scopes))}.",
                file=sys.stderr,
            )
            return 1
        try:
            backlog_content = (project_dir / _BACKLOG_REL_PATH).read_text(encoding="utf-8")
        except OSError as exc:
            print(f"no-backlog: cannot read {_BACKLOG_REL_PATH}: {exc}", file=sys.stderr)
            return 1
        open_ids = _open_item_ids(backlog_content)

    unclassified = [s for s in pending if s not in classification]
    stale_blockers: list[str] = []
    orphans: list[str] = []

    already_shipped = scopes_tagged_for(entries, version)
    for scope, (disposition, blocker) in classification.items():
        # The re-run exemption applies to `ships` rows only. A `withheld` scope
        # carrying this release's tag is a contradiction — it was withheld and
        # then shipped anyway — so exempting it would let the gate print
        # `releasable:` while never mentioning the withholding at all: absent
        # from `pending`, absent from the orphan list, absent from the summary.
        if scope not in pending and not (disposition == SHIPS and scope in already_shipped):
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
    # Name the artifact the verdict came from: the glob can match more than one
    # file, and a pass that doesn't say which table it read is unauditable.
    print(f"  classification: {plan_path}")
    if shipping:
        print(f"  shipping: {', '.join(shipping)}")
    if withheld:
        print(f"  withheld: {', '.join(withheld)}")
    return 0
