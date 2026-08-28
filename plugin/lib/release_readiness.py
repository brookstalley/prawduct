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

from . import change_log as change_log_mod
from . import plan_index

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


def release_pending_entries(entries: list) -> list:
    """Release-pending change-log entries, counted as **entries**.

    Tagged (a ``prawduct:`` tag line heads it) and carrying no ``release=``.
    :func:`release_pending_scopes` is this same set collapsed to its ``scope=``
    values, and that collapse is lossy in one direction only: an entry carrying
    no ``scope=`` contributes nothing to collapse, so it leaves the set without
    leaving a trace. Holding the entries is what makes the loss countable — see
    :func:`unclassifiable_pending_entries`.

    An entry with **no tag line at all** is not release-pending. Predating the
    tag convention is not the same as being tagged wrong, and this gate has
    never claimed authority over untagged history.
    """
    return [
        entry
        for entry in entries
        if entry.tag_line_count > 0 and not entry.tags.get("release")
    ]


def unclassifiable_pending_entries(entries: list) -> list:
    """Release-pending entries carrying no ``scope=`` — work no gate can see.

    The classification table is keyed by scope, so an entry contributing no
    scope reaches no row in it: it can be neither shipped nor withheld, and
    Phase 0 certifies ``releasable`` over work it never enumerated. That is the
    unrecallable-publish shape this module exists to prevent, entered through
    the one door the scope collapse leaves open.
    """
    return [
        entry
        for entry in release_pending_entries(entries)
        if not (isinstance(entry.tags.get("scope"), str) and entry.tags.get("scope"))
    ]


def release_pending_scopes(entries: list) -> list[str]:
    """Scopes with at least one tagged change-log entry carrying no ``release=``.

    **The absence of ``release=`` is the marker, and it is now the only one.**
    A wider collector once sat beside this, adding ``status=shipped`` scopes so
    the derived-view regenerator could flip plan checkboxes regardless of tagging
    convention; it went with that regenerator, and its extra input — a ``status=``
    stamp — is bookkeeping that could lag reality, where a ``release=`` tag names
    the release that actually carried the code. So this was always the right
    question for *releasability*, and it is no longer the narrower of two.

    Which entries are release-pending is :func:`release_pending_entries`' one
    answer, consumed here rather than re-derived: the two must agree, because
    the gap between them is precisely what the reconciliation measures.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for entry in release_pending_entries(entries):
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
    exists to prevent. Three cases are skipped rather than reported, because
    they name no scope and so carry nothing to report *about*: the
    header/separator rows, any line with fewer than two cells, and a row whose
    scope cell is empty (even when its disposition cell is well-formed).
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
    # ``pending_items()`` is the backlog module's PUBLIC "outstanding work"
    # query: non-struck, non-empty title, and not in a resolved section
    # (resolved / done / completed / archive, by substring — so a product whose
    # backlog says `## Resolved` is handled, not just prawduct's `## Archive`).
    # Deliberately not the private ``_is_resolved_section``: a cross-package
    # private call would let a rename there silently change blocker liveness in
    # every product, with a green suite.
    return {
        item.item_id
        for item in backlog.pending_items()
        if item.item_id and (item.status or "").strip().lower() == "open"
    }


def _markdown_backlog_unavailable_reason(project_dir: Path) -> str | None:
    """``None`` when ``.prawduct/backlog.md`` is the live backlog; else *why* not.

    ``data-model.md`` § Direction: once ``backlog_service_repo`` is set the
    markdown is **frozen history**, and every item archived at cutover still
    parses as ``status: open``. Reading it post-cutover would make
    :func:`_open_item_ids` return the whole frozen roster, so a withholding
    blocker that has since closed would still look open and the gate would
    print ``releasable:`` on exactly the stale decision it exists to catch.
    Every other ``lib/`` reader checks this scalar first; this is not an
    exception.

    Returns the *reason* rather than a bool because two unrelated causes land
    here — a real cutover, and a project-state that would not load — and they
    need different remedies. Collapsing both into False made the caller state
    the cutover as fact, so an operator with a corrupt ``project-state.yaml``
    was told something about their backlog backend that was not true and sent
    to check a scalar that is unset. A wrong remedy is worse than a bare
    failure. Both directions still fail CLOSED.
    """
    from . import advisory_store  # noqa: PLC0415 -- lazy: keeps this module's import DAG light
    from . import backlog_probes  # noqa: PLC0415

    try:
        state = advisory_store.load_project_state(project_dir)
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- unreadable state must fail CLOSED, and the loader's failure modes are not enumerable here
        return (
            "unreadable-project-state: cannot determine which backlog is live "
            f"(project-state did not load: {exc}), so blocker liveness is "
            "unverifiable."
        )
    if backlog_probes.post_cutover(state):
        return (
            "cannot-verify-blockers: this repo has cut over to the GitHub Issues "
            "backlog (`backlog_service_repo` set), so `.prawduct/backlog.md` is "
            "frozen history and cannot say whether a blocker is still open."
        )
    return None


def normalize_version(release: str) -> str:
    """``3.2.0`` and ``v3.2.0`` name the same release; tags carry the ``v``.

    Public because ``release_verification`` needs the identical rule: the two
    gates sit at opposite ends of the same release and must agree on what the
    operator's argument means, and a second copy is how they would stop agreeing.
    """
    return release if release.startswith("v") else f"v{release}"


def _resolve_version(project_dir: Path, release: str | None) -> str | None:
    """The release under test.

    ``--release`` is authoritative. The ``plugin/VERSION`` fallback exists for
    ad-hoc mid-cycle checks and is **wrong by construction during Phase 0** —
    but not for the reason it used to give. It once said the file named the
    PREVIOUS release, because Phase 1 step 7 bumps ``VERSION`` after this gate
    runs. Phase 3 falsified that: ``develop`` now carries the next patch plus a
    ``-dev`` suffix all cycle, so at gate time the file names a **prerelease
    marker that is not any release** — never a tag, never a directory name, and
    guessed low on purpose, so it is not even reliably the number being cut.
    Either way the fallback says so out loud rather than quietly grading the
    wrong release — the same refusal-to-guess posture as the argv scan in the
    CLI wrapper.
    """
    if release:
        return normalize_version(release)
    version_file = project_dir / "plugin" / "VERSION"
    try:
        raw = version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw:
        return None
    print(
        f"NOTE: no --release given, falling back to plugin/VERSION (v{raw}). On "
        "develop that is a `-dev` PRERELEASE MARKER, not a release — no tag or "
        "release-plan will ever carry that name, and it is guessed low, so it is "
        "not reliably the number you are cutting either. Do NOT create artifacts "
        "named after it. Pass --release vX.Y.Z to grade the release you are cutting.",
        file=sys.stderr,
    )
    return f"v{raw}"


def _find_release_plan(project_dir: Path, version: str) -> Path | None:
    """The release-plan artifact for ``version``, live first, then archived.

    Globbed rather than exact-matched: shipped plans carry a descriptive suffix
    (``release-plan-v3.1.2-pruned.md``), so an exact name would miss every real
    one.

    **Live wins, archive is the fallback.** A release plan is one of the
    artifacts eligible for archival once its release ships, and this gate is the
    one thing that must not fail because an artifact reached its end of life:
    a re-run against an already-cut version would otherwise report
    ``no-release-plan`` and fail closed on a release that demonstrably happened.
    Ordering matters as much as coverage — an archived plan for a version being
    re-cut must never shadow the live one that supersedes it.
    """
    artifacts = project_dir / _ARTIFACTS_REL_DIR
    pattern = f"release-plan-{version}*.md"
    for root in (artifacts, artifacts / plan_index.ARCHIVE_DIR_NAME):
        matches = sorted(root.glob(pattern)) if root.is_dir() else []
        if matches:
            return matches[0]
    return None


def _duplicate_scope_warnings(project_dir: Path) -> list[str]:
    """Report scopes declared by more than one live build plan.

    **Split out of :func:`_plan_coverage_warnings` and hoisted above the
    no-pending early return.** The rehoming put it behind ``if not pending:
    return 0``, so on a repo with nothing release-pending it stopped running —
    where its previous caller ran it on every invocation. Nobody chose that
    coupling: this asks a question about repo *structure* (two plans claiming one
    scope), takes only the artifacts directory, and is answerable whether or not
    a release is in flight. Its message is actionable at any time, and the defect
    it names is cheap to fix on a quiet day and expensive to discover mid-release,
    when scope→plan resolution has just become load-bearing. Noise risk is near
    zero — two plans genuinely declaring one scope is rare and always wrong.

    The missing-plan half stays in :func:`_plan_coverage_warnings`: that one is
    *about* the pending set and is correctly scoped to it.
    """
    artifacts = project_dir / _ARTIFACTS_REL_DIR
    return [message for _scope, message in plan_index.duplicate_scope_errors(artifacts)]


def _plan_coverage_warnings(project_dir: Path, pending: list[str]) -> list[str]:
    """Report release-pending scopes with no build plan.

    This check lived in the derived-view regenerator, whose only product was a
    view; each error there suppressed one scope's regeneration. That caller is
    being retired, and the field it guards — the frontmatter ``scope:`` that
    ties a change-log entry to the plan describing the work — is not. This is
    the gate that resolves scopes to plans, so it is where it belongs.

    **Reported, not fatal, and deliberately.** The gate fails closed on state it
    cannot evaluate: no change log, no release plan, an unclassified scope. A
    missing *build* plan is none of those — the classification table still
    classifies the scope, so the release stays evaluable. What it signals is a
    Principle 6 problem (work shipping with no documented parent), which is a
    message for a person rather than a reason to refuse the release. Escalating
    it here would be a new gate semantic, not a rehoming.

    Archived plans count as coverage: a scope whose plan reached its end of life
    is documented, just not current. Only "no plan anywhere" is the signal.
    """
    artifacts = project_dir / _ARTIFACTS_REL_DIR
    known = plan_index.build_scope_to_plan_map(artifacts, include_archived=True)
    warnings = [
        f"release-pending scope={scope!r} has no build-plan file under "
        f"{_ARTIFACTS_REL_DIR}/ (live or archived) — work is shipping with no "
        f"plan describing it."
        for scope in pending
        if scope not in known
    ]
    return warnings


def _tagged_count(entries: list) -> int:
    """How many entries a ``prawduct:`` tag line heads.

    The denominator both accounting lines are built on, so it is derived once:
    a repo whose two branches disagreed about how many entries the gate can even
    see would be reporting the confusion rather than the count.
    """
    return sum(1 for entry in entries if entry.tag_line_count > 0)


def _scan_accounting(
    entries: list,
    pending_entries: list,
    scopes: list[str],
    unclassifiable: list,
) -> str:
    """The gate's denominator, as one phrase.

    A verdict that does not say what it looked at cannot be audited, and cannot
    be *retired* either: the only honest argument for dropping a check later is
    a run of it finding nothing, which requires it to have counted out loud.
    Entries scanned, entries release-pending, the scopes they enumerate, and the
    ones that enumerate none — the last is the reconciliation's whole yield.
    """
    return (
        f"{len(entries)} change-log entries, {_tagged_count(entries)} tagged, "
        f"{len(pending_entries)} release-pending across {len(scopes)} scope(s), "
        f"{len(unclassifiable)} unclassifiable"
    )


def check_releasability(project_dir: Path, release: str | None = None) -> int:
    """Phase 0 gate. Exit 0 when every release-pending scope is classified.

    Every failure path returns 1 with a named reason on stderr. Un-evaluable
    state (missing change log, missing release plan) fails closed — the whole
    point is that an unclassified scope must never read as "fine".
    """
    change_log = project_dir / change_log_mod.CHANGE_LOG_REL_PATH
    try:
        change_log_content = change_log.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"no-change-log: cannot read {change_log_mod.CHANGE_LOG_REL_PATH}: {exc}", file=sys.stderr)
        return 1

    entries = change_log_mod.parse_change_log(change_log_content)

    # The tag checks run BEFORE the pending set is computed, because a malformed
    # tag is precisely what makes that set wrong. `release_pending_scopes` skips
    # any entry carrying a `release=` value — it cannot tell a version from a
    # placeholder — so `release=unreleased` silently removes its whole scope and
    # the gate answers "nothing to cut". That is not a hypothetical failure
    # mode: it hid an entire branch from the v3.2.8 release. These checks had
    # lived in the derived-view regenerator, which was their only caller and
    # which is not what a release depends on.
    tag_errors, tag_warnings = change_log_mod.validate_change_log_tags(entries)
    for warning in tag_warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    if tag_errors:
        # Fail closed: this gate's job is that an unclassifiable release state
        # never reads as "fine", and a tag it cannot interpret is exactly that.
        for err in tag_errors:
            print(f"bad-change-log-tag: {err}", file=sys.stderr)
        return 1

    # Structure, not release state — so it runs BEFORE the no-pending return.
    # A duplicate scope makes scope→plan resolution a coin toss, and a repo with
    # nothing pending is exactly where that is cheapest to fix; discovering it
    # mid-release, when the resolution has just become load-bearing, is the
    # expensive order. See `_duplicate_scope_warnings`.
    for warning in _duplicate_scope_warnings(project_dir):
        print(f"WARNING: {warning}", file=sys.stderr)

    # Reconcile release-pending ENTRIES against the scopes they collapse to, and
    # do it BEFORE the no-pending return — because the entry this catches is
    # exactly the one that can empty `pending` while release-pending work still
    # exists. An entry carrying no `scope=` is in no scope, so it reaches no row
    # of the classification table, so it can be neither shipped nor withheld,
    # and the gate certifies `releasable` over work it never enumerated.
    #
    # It REFUSES rather than reports: this is a releasability verdict over work
    # that cannot be classified, and an authority gate fails closed on state it
    # cannot evaluate. The remedy is one `scope=` per named entry, which is why
    # every offending entry is named — a refusal whose fix is mechanical costs
    # an operator a minute; the publish it prevents is unrecallable.
    #
    # Exit 1, the value every other refusal here uses. Not 3: the change log
    # READ fine, so this is not the unreadable-subject case — it is the work
    # that is unclassifiable.
    pending_entries = release_pending_entries(entries)
    pending = release_pending_scopes(entries)
    unclassifiable = unclassifiable_pending_entries(entries)
    accounting = _scan_accounting(entries, pending_entries, pending, unclassifiable)
    if unclassifiable:
        noun = "entry" if len(unclassifiable) == 1 else "entries"
        print(
            f"unclassifiable-pending-entry: {len(unclassifiable)} release-pending "
            f"change-log {noun} with no `scope=` — in no scope, so in no "
            "classification table, so neither shipped nor withheld. Add a "
            "`scope=` naming the work, then re-run:",
            file=sys.stderr,
        )
        for entry in unclassifiable:
            print(f"  - {entry.title!r} (change-log line {entry.line_number})", file=sys.stderr)
        print(f"  scanned: {accounting}.", file=sys.stderr)
        return 1

    if not pending:
        # Name the denominator: "0 pending" from a change log the parser could
        # not read looks identical to "0 pending" because everything shipped,
        # and only one of those is a pass. Split it further, because `tagged`
        # alone cannot separate everything already carrying `release=` (normal,
        # or Phase 1 step 3 just ran and emptied the set out from under a
        # re-run) from a log that parsed to nothing.
        #
        # A third cause used to reach here and no longer can: release-pending
        # entries carrying no `scope=` key, invisible to a gate that enumerates
        # scopes. The reconciliation above refuses on those by name, so an empty
        # `pending` here is now an honestly empty one.
        detail = f"{len(entries)} change-log entries scanned, {_tagged_count(entries)} tagged"
        if release:
            asked = normalize_version(release)
            stamped = len(scopes_tagged_for(entries, asked))
            detail += f", {stamped} scope(s) already tagged release={asked}"
        print(f"releasable: no release-pending scopes — nothing to classify ({detail}).")
        return 0

    # The accounting the no-pending branch has always printed, now printed on
    # the branch where something IS pending too. Its absence here was the bug's
    # other half: the gate reported a verdict without ever saying what it had
    # looked at, so nothing it missed could be noticed. The `unclassifiable`
    # count is 0 by construction at this point, and that is the emission worth
    # having — it is the evidence on which this check could later be retired.
    print(f"scanned: {accounting}.")

    for warning in _plan_coverage_warnings(project_dir, pending):
        print(f"WARNING: {warning}", file=sys.stderr)

    version = _resolve_version(project_dir, release)
    if version is None:
        # The `plugin/VERSION` fallback is prawduct's own layout. This module
        # ships inside `plugin/` to every product, so telling a product user to
        # "make plugin/VERSION readable" names a path that cannot exist in their
        # repo — an instruction they can only fail. Offer it only where the file
        # is actually the repo's version source. (Generality beyond this message
        # was declined with reasons in R-13/R-30; this is the misleading half.)
        hint = (
            " or make plugin/VERSION readable"
            if (project_dir / "plugin" / "VERSION").exists()
            else ""
        )
        print(f"no-version: pass --release vX.Y.Z{hint}.", file=sys.stderr)
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
    # Blocker liveness is the ONLY sub-verdict a frozen backlog can withhold.
    # Returning here instead would report the one thing the gate could not check
    # and stay silent about the thing it exists to check — whether every
    # release-pending scope is classified at all. The runbooks tell the operator
    # to hand-verify liveness and continue, so a bare refusal would route them
    # past an unclassified scope on the way to an unrecallable publish: the
    # v3.1.2 near-miss this module was built for, re-entered through its own
    # remedy. Carry the reason as a problem and let every other check run.
    liveness_unverifiable: str | None = None
    if withheld_scopes:
        liveness_unverifiable = _markdown_backlog_unavailable_reason(project_dir)
    if withheld_scopes and liveness_unverifiable is None:
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
    contradictions: list[str] = []
    for scope, (disposition, blocker) in classification.items():
        shipped_now = scope in already_shipped
        # Withheld AND tagged for this release is a contradiction, and it needs
        # its OWN diagnosis. Left in the orphan bucket it reads "stale table
        # row?" — false for a scope carrying the release tag, and acting on that
        # hint (delete the row) makes the gate return 0 and ship the very scope
        # the table withheld. A wrong remedy is worse than a bare failure.
        if disposition == WITHHELD and shipped_now:
            # Name the blocker's liveness here too. Falling through to the
            # stale-blocker check is not an option (the `continue` keeps this
            # scope out of the orphan bucket), but staying silent about a closed
            # blocker would print a remedy — "the withholding stands" — that is
            # not actually available, which is the same wrong-remedy defect this
            # branch exists to fix.
            blocker_note = (
                f"{blocker}, which is no longer open"
                if blocker and liveness_unverifiable is None and blocker not in open_ids
                else blocker
            )
            contradictions.append(
                f"{scope} (withheld behind {blocker_note}, but its entries are "
                f"already tagged release={version})"
            )
            continue
        # The re-run exemption is `ships`-only: Phase 1 stamps `release=` on the
        # shipping set, so those scopes correctly leave `pending`.
        if scope not in pending and not (disposition == SHIPS and shipped_now):
            orphans.append(scope)
        # Unverifiable liveness is NOT a closed blocker. Claiming "not open" from
        # an unread backlog would be a wrong remedy — re-take a decision that may
        # be perfectly sound — so the liveness problem below says so once instead.
        if (
            disposition == WITHHELD
            and blocker
            and liveness_unverifiable is None
            and blocker not in open_ids
        ):
            stale_blockers.append(f"{scope} (withheld behind {blocker}, which is not open)")

    problems = list(errors)
    if liveness_unverifiable is not None:
        problems.append(
            f"{liveness_unverifiable} {len(withheld_scopes)} scope(s) are withheld "
            "behind blockers that must be confirmed open by hand before publishing: "
            f"{', '.join(sorted(withheld_scopes))}. Every other check still ran — "
            "fix any other problem listed beside this one first."
        )
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
    if contradictions:
        problems.append(
            "scope(s) classified `withheld` whose entries already carry this "
            "release's tag — the table and the change log disagree about what is "
            "shipping. Do NOT delete the row: either the withholding stands (drop "
            f"the release= tag) or it does not (reclassify as `{SHIPS}`): "
            f"{'; '.join(sorted(contradictions))}"
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
