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
from dataclasses import dataclass
from pathlib import Path

from . import buildplan_refs
from . import change_fragments
from . import change_log as change_log_mod
from . import consumer_digest
from . import gates
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
#: A ``withheld`` row's third cell declaring the scope collateral of another (#1024).
_COLLATERAL_RE = re.compile(r"collateral-of\s+`?([^\s`]+)`?")

#: What "this file cannot be read" means, for every read in this module.
#: ``read_text`` raises ``UnicodeDecodeError`` — a ``ValueError``, not an
#: ``OSError`` — on a mis-encoded file, so catching only the latter lets a bad
#: byte past the reason line and out as a traceback. That is wrong twice over
#: here: the refusing reads promise "every failure path returns 1 with a named
#: reason", and the advisory read promises to fail soft. Named once because the
#: five reads have to agree about it; five hand-written tuples are how four of
#: them get widened and the fifth does not.
_UNREADABLE = (OSError, UnicodeDecodeError)


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
    """Release-pending legacy change-log entries: tagged, and carrying no ``release=``.

    The release reads ``.prawduct/changes/`` fragments only (#1125), so an entry
    this returns is work no release can see: :func:`legacy_pending_refusals`
    refuses on it, and the size archive (``change_log_archive``) keeps it in the
    live log, where that refusal and ``migrate-change-log`` both look for it.
    The third reader, ``gitattributes_probes``, holds its remove-``merge=union``
    advice while one is pending. None of them enumerates a scope from it.

    An entry with **no tag line at all** is not release-pending. Predating the
    tag convention is not the same as being tagged wrong, and this gate has
    never claimed authority over untagged history.
    """
    return [
        entry
        for entry in entries
        if entry.tag_line_count > 0 and not entry.tags.get("release")
    ]


def legacy_pending_refusals(content: str, entries: list | None = None) -> list[str]:
    """One ``legacy-pending-entry:`` refusal per change the live log still holds unshipped.

    The release cut and this gate read fragments only, so a release-pending entry
    in ``.prawduct/change-log.md`` would otherwise be in no pending set: not
    shipped, not withheld, and not mentioned. That is the silent drop the gate
    exists to prevent (v3.1.2, v3.2.8), so it refuses instead and names the way
    out, ``/prawduct:doctor``, whose check #22 runs ``migrate-change-log``.

    Two readers, because each sees what the other cannot. Every release-pending
    entry is named by title and line. Then the migration's own converter runs,
    and every entry it would refuse is named with its reason: that is how a
    ``release=`` that is not a version (``release=unreleased``) is caught, which
    reads as shipped to the first reader and is the v3.2.8 shape exactly. The
    converter's type decision is left to doctor, which owns ``--default-type``,
    so a missing type is not reported here.
    """
    if entries is None:
        entries = change_log_mod.parse_change_log(content)
    rel = change_log_mod.CHANGE_LOG_REL_PATH
    remedy = (
        f"run /prawduct:doctor to move it into {change_fragments.FRAGMENT_DIR_REL}/ "
        "(it runs `prawduct-hook migrate-change-log`)"
    )
    refusals = [
        f"legacy-pending-entry: {entry.title!r} ({rel} line {entry.line_number}) has not "
        f"shipped, and releases read only {change_fragments.FRAGMENT_DIR_REL}/ — {remedy}"
        for entry in release_pending_entries(entries)
    ]
    # The default type only silences the type decision; nothing is written.
    conversion = change_fragments.legacy_entries_as_fragments(content, default_type="chore")
    refusals += [
        f"legacy-pending-entry: {rel} holds an entry the move to fragments refuses, "
        f"{problem.code}: {problem.detail} — fix it, then {remedy}"
        for problem in conversion.refusals
    ]
    return refusals


def parse_classification(content: str) -> tuple[dict[str, tuple[str, str | None]], list[str]]:
    """Parse the ``## Release classification`` table.

    Returns ``(classification, errors)`` where classification maps
    ``scope -> (disposition, blocker_id_or_None)``. Rows are markdown table
    rows: ``| scope | ships |  |`` or ``| scope | withheld | ABC-1234 |``; a
    blocker may also be an Issues id, ``#123`` or ``owner/repo#123`` (#1033).

    A ``withheld`` row's third cell may instead declare the scope **collateral**
    of another (#1024): ``| small-fix | withheld | collateral-of big-feature |``.
    Collateral is work that merged at or before a pruned release's cut point, so
    the range prune cannot separate it from the withheld work and it stays on
    ``develop``. It has no blocker of its own; it is held by its parent's, so its
    tuple carries the parent's blocker and every caller (the gate's liveness and
    stale-blocker checks, the cut's ``withheld`` → kept rule) treats it exactly
    as a withheld scope. :func:`parse_collateral` says which scopes are
    collateral, and of what.

    A row with a recognised shape but bad content (unknown disposition,
    duplicate scope, `withheld` with no blocker id, a collateral declaration the
    table cannot honour) becomes an **error**: a row a human wrote and this
    parser ignored is the silent-omission class the gate exists to prevent.
    Three cases are skipped rather than reported, because they name no scope and
    so carry nothing to report *about*: the header/separator rows, any line with
    fewer than two cells, and a row whose scope cell is empty (even when its
    disposition cell is well-formed).
    """
    classification, errors, _collateral = _parse_table(content)
    return classification, errors


def parse_collateral(content: str) -> dict[str, str]:
    """``collateral scope -> parent scope`` for every well-formed ``collateral-of`` row.

    A sibling of :func:`parse_classification` rather than a third return value,
    so no caller of that function changes shape. A row whose declaration is an
    error is still listed: the error is what refuses, and this map only says
    what the operator declared.
    """
    _classification, _errors, collateral = _parse_table(content)
    return collateral


def _parse_table(
    content: str,
) -> tuple[dict[str, tuple[str, str | None]], list[str], dict[str, str]]:
    classification: dict[str, tuple[str, str | None]] = {}
    errors: list[str] = []
    collateral: dict[str, str] = {}
    lines = content.splitlines()

    start = None
    for i, line in enumerate(lines):
        if _HEADING_RE.match(line.strip()):
            start = i + 1
            break
    if start is None:
        return classification, ["no `## Release classification` section"], collateral

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
        declared = _COLLATERAL_RE.fullmatch(blocker.strip("`"))
        if disposition == SHIPS:
            if declared:
                # Requirement 2 of #1024: the operator said this scope's code
                # cannot be separated from withheld work, so shipping it would
                # archive it as released while its code stays on develop.
                parent = declared.group(1)
                errors.append(
                    f"scope `{scope}`: `{SHIPS}` but declared `collateral-of {parent}` — its code "
                    f"stays on develop with `{parent}`'s, so the cut would archive it as shipped "
                    f"in a release that does not carry it. Reclassify it "
                    f"`{WITHHELD} | collateral-of {parent}`, or ship `{parent}`"
                )
            classification[scope] = (SHIPS, None)
            continue
        if declared:
            collateral[scope] = declared.group(1)
            # Resolved to the parent's blocker once every row is read, so a
            # collateral row may come before its parent.
            classification[scope] = (WITHHELD, None)
            continue
        blocker_id = _blocker_id(blocker)
        if blocker_id is None:
            errors.append(
                f"scope `{scope}`: `{WITHHELD}` requires a blocker item id "
                "(e.g. `ABC-1234`, `#123` or `owner/repo#123`) or `collateral-of <scope>` — "
                "a withholding with no named blocker is an unrecorded decision"
            )
            continue
        classification[scope] = (WITHHELD, blocker_id)

    for scope, parent in collateral.items():
        if parent not in classification:
            errors.append(
                f"scope `{scope}`: declared `collateral-of {parent}`, but `{parent}` is not in "
                "the table — classify the parent, whose blocker holds both"
            )
        elif parent in collateral:
            errors.append(
                f"scope `{scope}`: declared `collateral-of {parent}`, and `{parent}` is itself "
                f"collateral — name the scope `{parent}` is collateral of, the one with the blocker"
            )
        elif classification[parent][0] != WITHHELD:
            errors.append(
                f"scope `{scope}`: declared `collateral-of {parent}`, but `{parent}` is not "
                f"`{WITHHELD}` — collateral is held by its parent's blocker, so either withhold "
                f"`{parent}` or reclassify `{scope}`"
            )
        else:
            classification[scope] = (WITHHELD, classification[parent][1])
    return classification, errors, collateral


def _blocker_id(cell: str) -> str | None:
    """The blocker id a classification cell names, or ``None``.

    A markdown ``PFX-XXXX`` first, as before. Otherwise the first token carrying
    a ``#`` that the backlog service's own id parser accepts — ``#123`` or
    ``owner/repo#123`` — so a repo whose backlog lives on Issues can name the
    blocker it actually has, and so this module does not grow a second
    definition of what an Issues id looks like. The parser needs a repo to accept
    a bare ``#123``; the placeholder only lets it judge the spelling, and the id is
    kept as written, to be resolved against the real scope by
    :func:`_issues_blocker_liveness`. The short ``repo#123`` form needs an owner
    and stays rejected: nothing here could say whose repo it means.
    """
    match = _ITEM_ID_RE.search(cell)
    if match:
        return match.group(1)
    from .backlog import ids  # noqa: PLC0415 -- lazy: keeps this module's import DAG light

    for raw in cell.split():
        token = raw.strip("`.,;:()[]")
        if "#" in token and ids.normalize_id(token, default_repo=("owner", "repo")).ok:
            return token
    return None


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


def _blocker_liveness(project_dir: Path, blockers: set[str]) -> tuple[set[str], dict[str, str]]:
    """Which withholding blockers are open, routed by the backlog that is live.

    Returns ``(open_blockers, unverifiable)``, ``unverifiable`` mapping a blocker
    to *why* its liveness could not be established. A blocker in neither is
    closed. Raises an ``_UNREADABLE`` error when the markdown backlog is the live
    one and cannot be read, which the caller reports as ``no-backlog``.

    **Routed by backend, because only one backlog is ever the truth.**
    ``data-model.md`` § Direction: once ``backlog_service_repo`` is set the
    markdown is **frozen history**, and every item archived at cutover still
    parses as ``status: open``. Reading it post-cutover would make every
    withholding blocker look open, so the gate would print ``releasable:`` on
    exactly the stale decision it exists to catch. Post-cutover, liveness comes
    from the local backlog cache (``cachequery.resolve``, the reader behind
    ``prawduct-hook backlog cache-query resolve``) — which also resolves a legacy
    ``PFX`` blocker through the alias the importer stamped. Pre-cutover, the
    markdown answers for ``PFX`` ids and cannot answer for an Issues id at all.

    **Unverifiable is never closed.** A cache that will not open, an id the
    cache does not hold, a project-state that will not load: each lands in
    ``unverifiable`` with its own reason, because each needs a different remedy
    and "the blocker closed, re-take the decision" is the remedy for none of
    them. Every direction still fails CLOSED.
    """
    from . import advisory_store  # noqa: PLC0415 -- lazy: keeps this module's import DAG light
    from . import backlog_probes  # noqa: PLC0415

    try:
        state = advisory_store.load_project_state(project_dir)
    except Exception as exc:  # prawduct:allow prawduct/broad-except -- unreadable state must fail CLOSED, and the loader's failure modes are not enumerable here
        reason = (
            "unreadable-project-state: cannot determine which backlog is live "
            f"(project-state did not load: {exc}), so blocker liveness is "
            "unverifiable."
        )
        return set(), {blocker: reason for blocker in blockers}
    if backlog_probes.post_cutover(state):
        return _issues_blocker_liveness(
            project_dir, str(state.get("backlog_service_repo")), blockers
        )

    markdown = {blocker for blocker in blockers if _ITEM_ID_RE.fullmatch(blocker)}
    unverifiable = {
        blocker: (
            "cannot-verify-blockers: this repo's live backlog is "
            f"`{_BACKLOG_REL_PATH}` (`backlog_service_repo` unset), which cannot say "
            f"whether the GitHub issue {blocker} is still open."
        )
        for blocker in blockers - markdown
    }
    if not markdown:
        return set(), unverifiable
    content = (project_dir / _BACKLOG_REL_PATH).read_text(encoding="utf-8")
    return markdown & _open_item_ids(content), unverifiable


def _issues_blocker_liveness(
    project_dir: Path, scope: str, blockers: set[str]
) -> tuple[set[str], dict[str, str]]:
    """:func:`_blocker_liveness` for a repo whose backlog lives on GitHub Issues.

    Read from the local cache, never the network: this gate runs in a release
    procedure that must not depend on a live provider, and the cache already
    owns id resolution — bare ``#N`` against its own scope, aliases, redirects.
    A bare ``#N`` means an issue in ``scope``, the repo the cache holds."""
    from datetime import datetime, timezone  # noqa: PLC0415

    from .backlog import cachequery  # noqa: PLC0415 -- lazy: only the post-cutover arm

    now = datetime.now(timezone.utc)
    default_owner = scope.split("/", 1)[0] if "/" in scope else None
    open_blockers: set[str] = set()
    unverifiable: dict[str, str] = {}
    for blocker in sorted(blockers):
        envelope = cachequery.resolve(
            project_dir, scope=scope, id_raw=blocker, now=now, default_owner=default_owner
        )
        if envelope.get("status") != "ok":
            err = envelope.get("error") or {}
            unverifiable[blocker] = (
                "cannot-verify-blockers: the backlog cache could not be read "
                f"({err.get('message') or err.get('code') or 'unknown error'}), so "
                "whether a blocker is still open is unknown — run "
                f"`prawduct-hook backlog sync --repo {scope}`."
            )
            continue
        data = envelope.get("data") or {}
        if not data.get("resolved"):
            unverifiable[blocker] = (
                f"cannot-verify-blockers: the backlog cache for {scope} holds no "
                f"item {blocker} — sync it (`prawduct-hook backlog sync --repo "
                f"{scope}`) or correct the id."
            )
            continue
        if not data.get("dead"):
            open_blockers.add(blocker)
    return open_blockers, unverifiable


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
    except _UNREADABLE:
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

    **A plan that declares no ``scope:`` is not "no plan", and saying so would be
    false rather than merely incomplete.** The map is keyed on the frontmatter
    ``scope:``, so a perfectly good plan that omits the key is absent from it —
    and the sentence above would then tell an operator that work is shipping
    undocumented when the document is sitting in the same directory. This is the
    v3.3.4 recurrence exactly: five *"no build-plan file"* advisories against a
    plan the walk could not key. So the warning carries the count when there is
    one; the gate's verdict is untouched, because which scope an unscoped plan
    belongs to is precisely what nothing here can know.
    """
    artifacts = project_dir / _ARTIFACTS_REL_DIR
    known = plan_index.build_scope_to_plan_map(artifacts, include_archived=True)
    unscoped = buildplan_refs.plans_missing_scope(artifacts)
    caveat = ""
    if unscoped:
        caveat = (
            f" ({len(unscoped)} live plan(s) declare no `scope:` at all and are "
            "invisible to this lookup, so one of them may be this scope's plan — "
            "check before treating this as undocumented work)"
        )
    warnings = [
        f"release-pending scope={scope!r} has no build-plan file under "
        f"{_ARTIFACTS_REL_DIR}/ (live or archived) — work is shipping with no "
        f"plan describing it.{caveat}"
        for scope in pending
        if scope not in known
    ]
    return warnings


def _ships_the_plugin_tree(project_dir: Path) -> bool:
    """Whether this repo IS prawduct's source, rather than a repo governed by it.

    Every ``plugin/…`` path this module can print names prawduct's own layout.
    The module ships *inside* ``plugin/`` to every product, so downstream those
    paths cannot exist, and naming one at a product user describes a file they
    have no way to have.

    **One predicate, not one guard per message.** Asked once, so every message
    naming a ``plugin/…`` path is suppressed by the same answer. A guard per
    message is the shape that lets the next such message be written without
    one, which is how this became a class rather than a slip.

    **It drops the ``plugin/…`` clause rather than rewording it.** The product's
    remedy (pass ``--release``) is the same sentence without it, so there is
    nothing to say in its place.

    ``plugin/VERSION`` is the evidence because it is prawduct's version source
    and the file :func:`_resolve_version` already treats as the tell.
    """
    return (project_dir / "plugin" / "VERSION").exists()


def _heading_first_warning(decl: consumer_digest.Declaration, read: consumer_digest.HeadlineRead) -> list[str]:
    """A headline that opens on a heading, which the cut writes as given.

    The one headline condition the cut does not refuse: it writes the file
    into a section whose banner then shows nothing. Checked in either
    ``headline:`` mode, because the cut uses a present headline file either
    way, and this is the only place it is caught.
    """
    first = read.first_line or ""
    if not first.startswith("#"):
        return []
    return [
        f"{consumer_digest.HEADLINE_FILE_REL} starts with a heading ({first!r}) — the cut puts "
        f"it under the release's heading in {decl.path}, and the version-delta "
        f"banner reads no headline from a section whose first line is a "
        f"heading, so consumers would be shown nothing. Make the first line "
        f"the headline itself."
    ]


def _digest_advisories(
    project_dir: Path, release: str | None
) -> tuple[list[str], str | None, list[str]]:
    """What Phase 0 can ask of the declared consumer digest, before the cut does.

    The subject is the ``consumer_digest:`` declaration, read through the one
    reader the cut also calls. Every condition the cut refuses on comes from
    :func:`consumer_digest.preflight`, the list the cut itself raises from, and
    each is a warning here, so a refusal the cut gains is warned about with no
    edit to this module. The one thing added is a headline that opens on a
    heading, which the cut writes faithfully into a blank banner.

    **Advisory, because of the moment rather than the stakes.** Phase 0 runs
    before the step that writes the headline, so on a correct release a
    headline warning fires once and is then fixed; a refusal here would block a
    release for a condition it is on its way to fixing.

    ``release`` is the operator's ``--release`` argument, or ``None``. Never
    the ``plugin/VERSION`` fallback: that names a ``-dev`` marker guessed low,
    not a release, and looking for a section under it would answer about the
    wrong version. With no release, no section is looked for, and a note says
    so: a check that skips itself quietly is indistinguishable from one that
    passed.

    Returns ``(warnings, note, emissions)``, all empty-or-``None`` in a repo
    that declares no digest, where no question has a subject. An invalid
    declaration is a warning, never silence: an operator who wrote the key
    meant something, and the checks they asked for did not run. None of this
    changes the exit code.
    """
    decl, invalid = consumer_digest.read_declaration(project_dir)
    if invalid is not None:
        return [f"{invalid}; the consumer digest checks did not run"], None, []
    if decl is None:
        return [], None, []

    version = normalize_version(release) if release else None
    if version is not None and consumer_digest.already_cut(project_dir, version):
        release_file = consumer_digest.release_file_rel(version)
        # After the cut every question is answered: the headline file was
        # consumed and the section is the cut's own. Asking again would tell
        # the operator to remove the section the cut just wrote, and a re-cut
        # would not restore it, because the release file says done.
        return [], (
            f"{version} is already cut ({release_file} exists), so the headline "
            f"and section checks of {decl.path} have nothing left to ask."
        ), [f"digest: {version} already cut ({release_file} → {decl.path})"]

    check = consumer_digest.preflight(project_dir, decl, version)
    warnings = [f"{p.detail} — the cut refuses `{p.code}` until this is fixed." for p in check.problems]
    warnings += _heading_first_warning(decl, check.headline)
    note = None
    if version is None and check.text is not None:
        note = (
            f"no --release given, so {decl.path} was not checked for a section "
            f"already naming the release the cut will refuse "
            f"(`release-in-changelog`). Pass --release vX.Y.Z to have it checked."
        )
    headline = check.headline.first_line
    # Printed whether or not anything is wrong, and whatever `headline:` says,
    # because the cut uses a present headline file either way: the failure
    # this guards is a line nobody looked at.
    emission = (
        f"digest headline: {headline!r} "
        f"({consumer_digest.HEADLINE_FILE_REL} → {decl.path})"
        if headline is not None
        else "digest headline: none"
    )
    return warnings, note, [emission]


def _suite_verdict(project_dir: Path) -> tuple[bool, str]:
    """Whether the saved suite run can vouch for this release, and why.

    **The one thing on this gate that refuses over the code rather than over
    the bookkeeping.** v2.1.6 shipped on a red suite; nothing in the release
    path read a test result, so the redness was visible only to whoever
    happened to run the suite. Missing evidence, a run reporting failures, a run
    that predates the session and no longer matches the tree, and a run that
    reported itself ``degraded`` are one state as far as a release is concerned:
    nothing has said this code passes. So it fails closed, like every other
    verdict here — the publish it prevents is unrecallable and the remedy is one
    suite run.

    **What it does NOT claim, and the runbook says so too.** The predicate is
    the framework's own :func:`gates.tests_are_current`, whose first disjunct is
    session-freshness — it asks *when* a run happened, not which tree it met, so
    a run from earlier in this session vouches for edits made after it. That is
    the right bound here and not a weakness worked around: Phase 0 runs before
    Phase 1 rewrites four files, so **no** check at this point can vouch for the
    tree the tag will carry. The claim available at this moment is "the suite is
    recorded green and current", and that is the claim made. A refusal at the
    tagging moment would be a different control at a different phase.

    Reusing that predicate is also what keeps one answer to one question: the
    builder's ``test-status``, the Stop hook and this gate all read the same
    record through the same reader, so a repo cannot be green for one and stale
    for another.

    The reader's third element — which disjunct answered — is dropped here
    rather than forwarded. It exists so a surface can avoid implying tree
    coverage it does not have, and this gate makes no such claim to begin with:
    the paragraph above states session-freshness as the correct bound at this
    phase, and its one caller prints the reason verbatim.
    """
    is_current, reason, _clause = gates.tests_are_current(project_dir)
    return is_current, reason


def _history_entries(project_dir: Path, live_entries: list) -> list:
    """Live entries plus every archived one, for questions about what already shipped.

    Falls back to the live entries when the archive cannot be read: that is what
    this gate answered from before archiving existed, and an unreadable archive
    must not turn a history lookup into a refusal.
    """
    from . import change_log_archive  # noqa: PLC0415 — lazy; change_log_archive imports this module lazily too

    text = change_log_archive.load_all_text(project_dir / ".prawduct")
    if text is None:
        return live_entries
    return change_log_mod.parse_change_log(text)


def _scan_accounting(fragments: int, entries: list) -> str:
    """The gate's denominator, as one phrase.

    A verdict that does not say what it looked at cannot be audited. Fragments
    are the pending set; the live log's entries are counted too, as history the
    gate read and found nothing pending in, because "0 legacy entries pending"
    from a log that parsed to nothing and from one that holds only shipped
    history look the same without the count.
    """
    return (
        f"{fragments} change fragment(s) in {change_fragments.FRAGMENT_DIR_REL}/, "
        f"{fragments} release-pending scope(s); {len(entries)} "
        f"{change_log_mod.CHANGE_LOG_REL_PATH} entries read as shipped history"
    )


@dataclass(frozen=True)
class PendingSet:
    """What is release-pending: the change fragments, and nothing else (#1125).

    ``entries`` is every parsed entry of the live single-file log, read as
    history only (the "already tagged release=" question and the accounting
    need it). ``read_error`` is set when that log exists but cannot be read, or
    when the repo has neither it nor a fragment directory. ``refusals`` names
    whatever makes the pending set untrustworthy, a pending legacy entry among
    them, so a caller refuses on it before reading ``scopes``.
    """

    entries: list
    fragment_scopes: list[str]
    refusals: list[str]
    read_error: str | None = None

    @property
    def scopes(self) -> list[str]:
        """The release-pending scopes: one per fragment."""
        return list(self.fragment_scopes)


def pending_scopes(project_dir: Path) -> PendingSet:
    """The release-pending set: one scope per file in ``.prawduct/changes/``.

    The one owner of that set (design D6 of #1012). Every file in the fragment
    directory is pending, because the cut removes shipped ones. Two things are
    refused rather than resolved: a fragment that fails validation, which could
    be missing its scope or carrying the wrong one, and a release-pending entry
    still in the single-file log (:func:`legacy_pending_refusals`), which no
    release reads any more and which would otherwise vanish from the set
    unannounced. A repo with a fragment directory and no single-file log is a
    fragments-only repo, not a missing input.
    """
    path = project_dir / change_log_mod.CHANGE_LOG_REL_PATH
    read_error: str | None = None
    try:
        content = path.read_text(encoding="utf-8")
    except _UNREADABLE as exc:
        content = ""
        if not (
            isinstance(exc, FileNotFoundError)
            and (project_dir / change_fragments.FRAGMENT_DIR_REL).is_dir()
        ):
            read_error = f"cannot read {change_log_mod.CHANGE_LOG_REL_PATH}: {exc}"
    entries = change_log_mod.parse_change_log(content)
    refusals = legacy_pending_refusals(content, entries)
    files = change_fragments.load_pending(project_dir)
    refusals += [
        f"bad-change-fragment: {item.path.name}: {problem}"
        for item in files
        for problem in item.problems
    ]
    return PendingSet(
        entries=entries,
        fragment_scopes=[item.fragment.scope for item in files if item.ok and item.fragment.scope],
        refusals=refusals,
        read_error=read_error,
    )


def check_releasability(project_dir: Path, release: str | None = None) -> int:
    """Phase 0 gate. Exit 0 when every release-pending scope is classified.

    Every failure path returns 1 with a named reason on stderr. Un-evaluable
    state (no change record, missing release plan) fails closed — the whole
    point is that an unclassified scope must never read as "fine".
    """
    pending_set = pending_scopes(project_dir)
    if pending_set.read_error is not None:
        print(f"no-change-log: {pending_set.read_error}", file=sys.stderr)
        return 1
    entries = pending_set.entries

    # Structure, not release state — so it runs BEFORE the no-pending return.
    # A duplicate scope makes scope→plan resolution a coin toss, and a repo with
    # nothing pending is exactly where that is cheapest to fix; discovering it
    # mid-release, when the resolution has just become load-bearing, is the
    # expensive order. See `_duplicate_scope_warnings`.
    for warning in _duplicate_scope_warnings(project_dir):
        print(f"WARNING: {warning}", file=sys.stderr)

    # Refused before any verdict, because each is exactly what would make the
    # pending set wrong: a fragment that fails validation, or a release-pending
    # legacy entry, which the fragments-only pending set cannot see and so would
    # otherwise ship in no release with no word said (#1125). Exit 1, the value
    # every other refusal here uses: the record READ fine, so this is not the
    # unreadable-subject case.
    if pending_set.refusals:
        for refusal in pending_set.refusals:
            print(refusal, file=sys.stderr)
        return 1
    pending = pending_set.scopes
    accounting = _scan_accounting(len(pending_set.fragment_scopes), entries)

    if not pending:
        # Name the denominator, and split it further: an empty pending set is
        # either everything already shipped in past releases, or Phase 1 step 3
        # just ran and emptied it out from under a re-run, and only the count of
        # scopes already tagged for this release tells the two apart.
        detail = accounting
        if release:
            asked = normalize_version(release)
            stamped = len(scopes_tagged_for(_history_entries(project_dir, entries), asked))
            detail += f", {stamped} scope(s) already tagged release={asked}"
        print(f"releasable: no release-pending scopes — nothing to classify ({detail}).")
        return 0

    # The accounting the no-pending branch prints, printed on the branch where
    # something IS pending too: a verdict that never says what it looked at
    # cannot be audited, so nothing it missed could be noticed.
    print(f"scanned: {accounting}.")

    for warning in _plan_coverage_warnings(project_dir, pending):
        print(f"WARNING: {warning}", file=sys.stderr)

    # The declared consumer digest, beside the coverage of build plans: both ask
    # whether what ships will be described where a reader looks, and neither is
    # a releasability verdict. Emitted BEFORE the version resolves, so a repo
    # whose release plan does not exist yet — the state it is in while the
    # headline is still being written — gets the advice while it is still
    # actionable. It gets the raw `--release`, never the VERSION fallback.
    digest_warnings, digest_note, digest_emissions = _digest_advisories(project_dir, release)
    for warning in digest_warnings:
        print(f"WARNING: {warning}", file=sys.stderr)
    if digest_note:
        print(f"NOTE: {digest_note}", file=sys.stderr)
    for emission in digest_emissions:
        print(f"  {emission}.")

    # The suite verdict is REPORTED here and RETURNED at the bottom, and the
    # split is deliberate. Printing it here is what makes it reachable at all:
    # this repo's ordinary Phase 0 state exits at `no-release-plan:` a few lines
    # down — that is the documented, expected first run — so a refusal wired
    # only into the final return would never be seen by the operator it is for.
    # Holding the return to the bottom keeps the property the rest of this gate
    # holds: every other check still runs, so one command reports every problem
    # rather than one per round trip.
    #
    # Below the no-pending return on purpose. That branch is "there is nothing
    # to cut", and a suite verdict about a release that is not happening is a
    # refusal with no release to refuse.
    suite_ok, suite_reason = _suite_verdict(project_dir)
    if suite_ok:
        # Emitted on the passing runs too: a control heard from only when it
        # fires cannot be retired on evidence, and naming which evidence
        # vouched is what lets a reader disagree with it.
        print(f"  suite: green — {suite_reason}.")
    else:
        print(
            f"unproven-suite: {suite_reason}. Nothing has said this code "
            "passes, and a release publishes unrecallably — run the suite and "
            "record it (`prawduct-hook test-evidence record`), then re-run.",
            file=sys.stderr,
        )

    version = _resolve_version(project_dir, release)
    if version is None:
        # Telling a product user to "make plugin/VERSION readable" names a path
        # that cannot exist in their repo — an instruction they can only fail.
        # One predicate answers for every message that would otherwise name
        # prawduct's own layout, so the next such message has it to hand.
        hint = (
            " or make plugin/VERSION readable"
            if _ships_the_plugin_tree(project_dir)
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
    except _UNREADABLE as exc:
        print(f"unreadable-release-plan: {plan_path}: {exc}", file=sys.stderr)
        return 1

    classification, errors = parse_classification(plan_content)
    collateral = parse_collateral(plan_content)

    # Blocker liveness is only consulted when something is actually withheld —
    # a release that withholds nothing needs no backlog read at all.
    withheld_scopes = [s for s, (d, _) in classification.items() if d == WITHHELD]
    open_ids: set[str] = set()
    # Blocker liveness is the ONLY sub-verdict an unreadable backlog can withhold.
    # Returning here instead would report the one thing the gate could not check
    # and stay silent about the thing it exists to check — whether every
    # release-pending scope is classified at all. The runbooks tell the operator
    # to hand-verify liveness and continue, so a bare refusal would route them
    # past an unclassified scope on the way to an unrecallable publish: the
    # v3.1.2 near-miss this module was built for, re-entered through its own
    # remedy. Carry the reason as a problem and let every other check run.
    unverifiable: dict[str, str] = {}
    if withheld_scopes:
        blockers = {b for s, (d, b) in classification.items() if d == WITHHELD and b}
        try:
            open_ids, unverifiable = _blocker_liveness(project_dir, blockers)
        except _UNREADABLE as exc:
            print(f"no-backlog: cannot read {_BACKLOG_REL_PATH}: {exc}", file=sys.stderr)
            return 1

    unclassified = [s for s in pending if s not in classification]
    stale_blockers: list[str] = []
    orphans: list[str] = []

    # The cut writes the shipping fragments into the change-log archive tagged
    # `release=<version>`, so "already shipped in this release" is a history
    # question, answered from the archive and the live log together.
    already_shipped = scopes_tagged_for(_history_entries(project_dir, entries), version)
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
                if blocker and blocker not in unverifiable and blocker not in open_ids
                else blocker
            )
            contradictions.append(
                f"{scope} (withheld behind {blocker_note}, but its entries are "
                f"already tagged release={version})"
            )
            continue
        # The re-run exemption is `ships`-only: Phase 1's cut archives the
        # shipping set tagged `release=` and removes its fragments, so those
        # scopes correctly leave `pending`.
        if scope not in pending and not (disposition == SHIPS and shipped_now):
            orphans.append(scope)
        # Unverifiable liveness is NOT a closed blocker. Claiming "not open" from
        # an unread backlog would be a wrong remedy — re-take a decision that may
        # be perfectly sound — so the liveness problem below says so once instead.
        if (
            disposition == WITHHELD
            and blocker
            and blocker not in unverifiable
            and blocker not in open_ids
        ):
            # A collateral scope is held by its parent's blocker, so it goes
            # stale with it, and is named here beside its parent.
            held = f"as collateral of {collateral[scope]}, " if scope in collateral else ""
            stale_blockers.append(f"{scope} (withheld {held}behind {blocker}, which is not open)")

    problems = list(errors)
    # One problem per distinct reason: the reasons carry different remedies (sync
    # the cache, fix project-state, verify by hand), so merging them would hand
    # every scope the wrong one.
    unverified_by_reason: dict[str, list[str]] = {}
    for scope, (disposition, blocker) in classification.items():
        if disposition == WITHHELD and blocker in unverifiable:
            unverified_by_reason.setdefault(unverifiable[blocker], []).append(scope)
    for reason, scopes in unverified_by_reason.items():
        problems.append(
            f"{reason} {len(scopes)} scope(s) are withheld "
            "behind blockers that must be confirmed open by hand before publishing: "
            f"{', '.join(sorted(scopes))}. Every other check still ran — "
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
            "shipping. Do NOT delete the row: either the withholding stands (undo "
            "the cut before the prep commit, as the release runbook's Phase 1 step 3 "
            "says; once committed, write a `reopens:` fragment so it ships with the "
            f"release that carries its code) or it does not (reclassify as `{SHIPS}`): "
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

    if not suite_ok:
        # The reason was printed above, where the operator meets it beside the
        # rest of the gate's output; this is only the verdict it earns. Nothing
        # is re-said here — a second copy of the sentence would read as a second
        # problem.
        return 1

    shipping = sorted(s for s in pending if classification[s][0] == SHIPS)
    withheld = sorted(
        f"{s} (collateral of {collateral[s]}, blocked by {classification[s][1]})"
        if s in collateral
        else f"{s} (blocked by {classification[s][1]})"
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
