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
from . import gates
from . import plan_index

_BACKLOG_REL_PATH = ".prawduct/backlog.md"
_ARTIFACTS_REL_DIR = ".prawduct/artifacts"
#: The consumer-facing digest. It ships *inside* the plugin and never lands in
#: a consuming repo, so downstream this path cannot exist and the check that
#: reads it has no subject — see :func:`_ships_the_plugin_tree`.
_DIGEST_REL_PATH = "plugin/CHANGELOG.md"

#: Recognised dispositions in the classification table.
SHIPS = "ships"
WITHHELD = "withheld"

_HEADING_RE = re.compile(r"^##\s+Release classification\s*$", re.IGNORECASE)
_NEXT_HEADING_RE = re.compile(r"^#{1,6}\s+")
#: A backlog id: 2-4 uppercase letters, hyphen, 4 alphanumerics (PFX-XXXX).
_ITEM_ID_RE = re.compile(r"\b([A-Z]{2,4}-[A-Z0-9]{4})\b")
#: A digest version section header. Loose on purpose — see
#: :func:`_open_digest_section` for why a stricter match would let an
#: unparseable heading fail to delimit.
_DIGEST_SECTION_RE = re.compile(r"^##\s+\S")

#: The seeded prerelease headline. Every cut ends by opening a fresh
#: ``## vX.Y.Z-dev`` section carrying a one-line seed, and the NEXT cut is meant
#: to replace that seed with the release's real headline. It reached consumers
#: once already: the v3.4.0 section still led with the seed after eight weeks of
#: notes had accumulated underneath it, because a section full of good notes
#: reads as a finished section. Matched on the opening words rather than the
#: whole sentence, so rewording the seed's trailing clause cannot silently
#: retire the check.
_SEEDED_HEADLINE = "prerelease under test"

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

    **It suppresses the arm rather than rewording it.** A repo that publishes no
    consumer digest has no digest to be *missing*: there is no degraded state to
    report, only a subject that does not exist, and "advice fails soft is not
    advice fails silent" governs a check that ran and could not answer — not one
    that was never about this repo. Where the subject does exist, every degraded
    path still says so.

    ``plugin/VERSION`` is the evidence because it is prawduct's version source
    and the file :func:`_resolve_version` already treats as the tell.
    """
    return (project_dir / "plugin" / "VERSION").exists()


def _read_digest(project_dir: Path) -> tuple[list[str], str | None]:
    """The consumer digest's lines, or ``([], reason)`` when it cannot be read.

    Reading is kept apart from sectioning and judging so no one function
    becomes the place where all three live. The reason is a
    phrase, not a verdict: every caller here reports rather than refuses, so the
    only thing a failed read must produce is a sentence saying what went unread.
    """
    try:
        return (project_dir / _DIGEST_REL_PATH).read_text(encoding="utf-8").splitlines(), None
    except _UNREADABLE as exc:
        return [], f"cannot read {_DIGEST_REL_PATH}: {exc}"


def _open_digest_section(lines: list[str]) -> tuple[str, list[str]] | None:
    """The topmost ``## `` section as ``(heading, body)``; ``None`` if there is none.

    **The open section is identified by position, not by version.** The digest
    states its own convention — rolling notes accumulate under the top heading
    and it is renamed to the release number at the cut — so "topmost" is what
    "the section this release is being written into" means, and it stays true
    across the rename that a version match would have to be taught about.

    The heading pattern is correspondingly loose (``## `` plus any non-space).
    A stricter semver match would let a heading it cannot parse fail to
    *delimit*, silently merging the section below into this one and reporting
    the previous release's notes as coverage for this one — a false pass, from a
    check whose whole job is to notice absence.
    """
    start: int | None = None
    for i, line in enumerate(lines):
        if not _DIGEST_SECTION_RE.match(line):
            continue
        if start is None:
            start = i
            continue
        return lines[start].strip(), lines[start + 1 : i]
    if start is None:
        return None
    return lines[start].strip(), lines[start + 1 :]


def _digest_mentions(section_text: str, scope: str) -> bool:
    """Whether the open section names a scope — as its slug, or as its words.

    Prose spells a slug out: the work tagged ``scope=branch-claim-multiplicity``
    is described in the digest as "a build plan can declare the branch it
    governs", carrying neither the slug nor its words. Testing the slug alone
    would therefore report nearly every scope as uncovered; testing both forms
    narrows that without pretending to read prose.

    **Bounded, not substring.** A bare ``in`` test passes a short slug on any
    longer word containing it, and that error runs the wrong way: it reports a
    scope as COVERED that the digest never mentioned, which is the silent pass
    this whole check exists to prevent. A false alarm costs a reader ten
    seconds; a false all-clear is how the v3.4.0 cut shipped a scope with no
    notes. So the match is bounded on both ends.

    **The hyphen counts as part of a name, not as a boundary.** Slugs compose —
    ``delegation`` and ``adhoc-delegation`` are two scopes shipping different
    work — and a plain word boundary breaks on the hyphen, so a digest naming
    only the longer one would mark the shorter one covered. That is the same
    false all-clear one character narrower, so the boundary excludes ``-`` as
    well as word characters.

    **What it still cannot see is the point of the WARNING's wording.** A scope
    described in words its slug does not contain reads as absent here, so the
    message asks the reader to look rather than asserting the note is missing —
    an advisory that overstates its own certainty is how a fuzzy check gets
    promoted to a blocking one.
    """
    lowered = scope.lower()
    return any(
        re.search(rf"(?<![\w-]){re.escape(form)}(?![\w-])", section_text)
        for form in (lowered, lowered.replace("-", " "))
    )


def _section_headline(body: list[str]) -> str | None:
    """The line the version-delta banner shows for this section, or ``None``.

    The banner's rule restated: the first non-empty line that is not itself a
    markdown heading, and a heading reached first ends the search rather than
    being read as the headline. It is restated rather than imported because the
    banner is a hook and ``lib/`` never imports from a hook — so the coupling is
    held by a test fixing the property that matters (a section the banner
    renders blank is a section this check warns about) rather than by a shared
    body, which is the honest thing to pin: what the operator needs is that the
    two agree about *emptiness*, not that they strip emphasis alike.

    Returned verbatim, markers and all, because the emission prints it back and
    what the operator needs to see is the line as they wrote it.
    """
    for line in body:
        stripped = line.strip()
        if not stripped:
            continue
        return None if stripped.startswith("#") else stripped
    return None


def _headline_advisory(heading: str, body: list[str]) -> tuple[list[str], str]:
    """Whether this release's section carries a consumer-facing headline.

    Two failures, one message each, and both have shipped. v2.1.6 was tagged
    and version-bumped with no section at all — which left `develop` red on
    ``test_changelog_has_current_version_entry`` from the release onward, i.e.
    the release shipped on a red suite and the redness was the only complaint.
    v3.4.0 had its section and still led with the seed the previous cut wrote,
    so every upgrading repo was shown "Prerelease under test" as the news.

    **Advisory, and the reason is the moment rather than the stakes.** Phase 0
    runs *before* the step that writes the headline, so on a correct release
    this fires exactly once and is then fixed — a refusal here would block a
    release for a condition the release is on its way to fixing. What the
    warning buys is that the operator meets the reminder while reading the
    gate's output, instead of meeting it eight weeks later in a consumer's
    session banner.

    Returns ``(warnings, emission)``. The emission prints the headline itself
    rather than a verdict about it: the whole failure mode is a line nobody
    looked at, so the control's yield is putting that line in front of somebody.
    """
    headline = _section_headline(body)
    if headline is None:
        return [
            f"the open {_DIGEST_REL_PATH} section ({heading}) has no headline — "
            f"its first non-empty line is what the version-delta banner shows "
            f"every repo crossing this version, so consumers would meet this "
            f"release with nothing said about it."
        ], f"digest headline: none in {heading} of {_DIGEST_REL_PATH}"
    if _SEEDED_HEADLINE in headline.lower():
        return [
            f"the open {_DIGEST_REL_PATH} section ({heading}) still leads with "
            f"the seeded placeholder ({headline!r}) — the banner shows that line "
            f"verbatim to every upgrading repo, so replace it with this "
            f"release's headline before the cut."
        ], f"digest headline: {headline!r} (still the seed) in {heading}"
    return [], f"digest headline: {headline!r} in {heading}"


def _coverage_advisory(
    heading: str, body: list[str], pending: list[str]
) -> tuple[list[str], str]:
    """Release-pending scopes the open digest section does not mention.

    A scope can reach the tag with zero consumer-facing notes and nothing asks.
    It happened at the v3.4.0 cut: ``scope=tactical-efficiency`` carried nine
    ``release=v3.4.0`` entries and no mention in the digest, and the notes were
    hand-written at cut time because somebody happened to notice. The failure is
    asymmetric — a section full of good notes reads as finished, so the missing
    scope is invisible exactly when the digest looks healthiest.

    **Reported, and it never touches the exit code.** Its subject is prose and
    its instrument is a name match, so it is advice by construction; the
    authority gate beside it refuses on state it cannot evaluate, and an
    unmentioned scope is not that — the release stays perfectly evaluable, it
    just may ship under-described. A known false positive is live in this repo
    today, which is the argument settled rather than a defect outstanding.

    The emission is the control's yield, printed whether or not it found
    anything, because a control heard from only when it fires cannot be retired
    on evidence — the only honest argument for dropping this later is a run of
    it finding nothing, and that argument needs the denominator it was measured
    against.
    """
    section_text = "\n".join(body).lower()
    warnings = [
        f"could not find release-pending scope={scope!r} in the open "
        f"{_DIGEST_REL_PATH} section ({heading}) — if it ships in this release, "
        f"consumers get no note about it. The match is on the scope name, so "
        f"work described in other words reads as absent: check the section."
        for scope in pending
        if not _digest_mentions(section_text, scope)
    ]
    emission = (
        f"digest coverage: {len(pending) - len(warnings)} of {len(pending)} "
        f"release-pending scope(s) named in {heading} of {_DIGEST_REL_PATH}"
    )
    return warnings, emission


def _digest_advisories(
    project_dir: Path, pending: list[str]
) -> tuple[list[str], str | None, list[str]]:
    """Everything the consumer digest can be asked at Phase 0, from one read.

    Two questions with one subject: does this release's section carry a
    headline, and does it name each scope shipping in the release. They share a
    function because they share the section — reading the file twice would let
    the two answer about different states of it, and would double the degraded
    note into two sentences saying the same thing happened.

    Returns ``(warnings, note, emissions)`` — all three empty-or-``None`` in a
    repo that publishes no digest, where neither question has a subject at all.
    The note is non-``None`` exactly when a digest that should exist could not
    be read or held no section, and it names the consequence rather than only
    the cause: **advice fails soft is not advice fails silent**, and a check
    that skips itself quietly is indistinguishable from one that passed.

    **Why both questions stay prawduct-only, rather than taking a declared path
    the way the version files do.** A product forgets its release notes exactly
    the way this repo did, so the appetite is real and the declaration precedent
    exists. What is missing is not a path but a *convention*: these checks ask
    about the section this release is being written into, and "the topmost
    ``## ``, renamed to the release number at the cut" is prawduct's own release
    procedure rather than a property of changelogs. A declaration carrying only
    a path would silently impose that procedure on every product that set it,
    and the failure would be a false all-clear — the shape both checks exist to
    prevent. Generalizing therefore means designing the keying rule as a stated
    requirement, which is a piece of work rather than a parameter, and it is
    filed as one instead of guessed at here.
    """
    if not _ships_the_plugin_tree(project_dir):
        return [], None, []
    lines, reason = _read_digest(project_dir)
    section = None if reason is not None else _open_digest_section(lines)
    if section is None:
        reason = reason or f"{_DIGEST_REL_PATH} has no `## ` section to read"
        return [], (
            f"digest coverage not checked: {reason}. No release-pending scope "
            f"was tested for a consumer-facing note, so one shipping with "
            f"nothing written about it would not be reported here — and the "
            f"headline every upgrading repo is shown went unread with it."
        ), []

    heading, body = section
    headline_warnings, headline_emission = _headline_advisory(heading, body)
    coverage_warnings, coverage_emission = _coverage_advisory(heading, body, pending)
    return (
        headline_warnings + coverage_warnings,
        None,
        [headline_emission, coverage_emission],
    )


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
    """
    return gates.tests_are_current(project_dir)


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
    except _UNREADABLE as exc:
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

    # Coverage of the consumer digest, beside the coverage of build plans: both
    # ask whether the pending set is described somewhere a reader will look, and
    # neither is a releasability verdict. Emitted BEFORE the version resolves,
    # so a repo whose release plan does not exist yet — the state this one is in
    # while the notes are still being written — still gets the advice while it
    # is still actionable.
    digest_warnings, digest_note, digest_emissions = _digest_advisories(
        project_dir, pending
    )
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
        # The predicate is shared with the digest checks rather than repeated
        # here, so one answer suppresses every message that would otherwise
        # name prawduct's own layout.
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
        except _UNREADABLE as exc:
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

    if not suite_ok:
        # The reason was printed above, where the operator meets it beside the
        # rest of the gate's output; this is only the verdict it earns. Nothing
        # is re-said here — a second copy of the sentence would read as a second
        # problem.
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
