"""The release cut: shipping change fragments into the archive and the release notes.

A fragment (`lib/change_fragments.py`) records one scope's change while it is
pending. At a release the cut does this to the fragments that ship, and
nothing to the rest:

1. renders each into the change-log archive's month file as an entry tagged
   ``release=vX.Y.Z``, in the archive's existing grammar;
2. where the repo declares ``consumer_digest:`` (`lib/consumer_digest.py`),
   renders the release's section — heading, the headline from
   ``.prawduct/release-headline.md``, the consumer notes — writes it to the
   release file ``.prawduct/releases/vX.Y.Z.md``, and inserts the same lines
   into the declared changelog as a new section, changing no other byte;
3. removes the fragments and the headline file, so the fragment directory is
   exactly the pending set.

What ships is decided by the release plan's classification table, or by
naming the scopes. The changelog is written, never searched for a section to
write into: a release is its release file, and that file's existence is the
record that the release was cut. Everything is validated before anything is
written, the writes are one all-or-nothing transaction, and the removals come
last. A run that fails while removing is completed by running it again: with
the release file present, a fragment whose own archive entry is already held
is removed and nothing is written, and any other fragment belongs to the next
release, so the cut refuses rather than add it to a release already published.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date as date_cls
from datetime import datetime, timezone
from pathlib import Path

from . import change_fragments
from . import change_log as change_log_mod
from . import change_log_archive
from . import consumer_digest
from . import core
from . import release_readiness


class CutRefused(Exception):
    """The cut cannot proceed; nothing was written. ``code`` names the reason."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class FragmentRemovalFailed(OSError):
    """Every file was written, but a fragment or the headline file could not be removed."""


@dataclass
class CutPlan:
    """What a cut would do, computed without writing anything."""

    version: str
    cut: list[change_fragments.FragmentFile]
    kept: list[str]
    writes: list[tuple[Path, str]] = field(default_factory=list)
    buckets: list[str] = field(default_factory=list)
    notes_added: list[str] = field(default_factory=list)
    #: The declared changelog's repo-relative path; ``None`` when undeclared.
    digest: str | None = None
    none_reasons: list[tuple[str, str]] = field(default_factory=list)
    release_file: Path | None = None
    #: The release file's text, which is also the dry run's preview.
    section_text: str | None = None
    #: The 1-based changelog line the section's heading lands on.
    insert_line: int | None = None
    #: Fragments a cut of this release already archived, to be removed only.
    cleanup: list[change_fragments.FragmentFile] = field(default_factory=list)
    #: The headline file, when this cut consumes it.
    headline_file: Path | None = None
    #: A headline file left in place because it is not this release's.
    headline_kept: Path | None = None
    #: Pending legacy scopes that ship; they carry no consumer note.
    legacy_shipping: list[str] = field(default_factory=list)

    @property
    def has_work(self) -> bool:
        return bool(self.cut or self.cleanup or self.headline_file)


def _classification(project_dir: Path, version: str) -> tuple[Path, dict[str, tuple[str, str | None]]]:
    plan_path = release_readiness._find_release_plan(project_dir, version)
    if plan_path is None:
        raise CutRefused(
            "no-release-plan",
            f"no release-plan-{version}*.md classifies what ships; write one, or name the scopes with --scope",
        )
    classification, errors = release_readiness.parse_classification(
        plan_path.read_text(encoding="utf-8")
    )
    if errors:
        raise CutRefused("bad-release-plan", "; ".join(errors))
    return plan_path, classification


def _check_named(fragment_scopes: list[str], scopes: list[str]) -> None:
    unknown = sorted(set(scopes) - set(fragment_scopes))
    if unknown:
        raise CutRefused(
            "unknown-scope",
            f"no pending fragment for {', '.join(unknown)} in {change_fragments.FRAGMENT_DIR_REL}/",
        )


def _selected_scopes(
    project_dir: Path,
    version: str,
    fragment_scopes: list[str],
    scopes: list[str] | None,
    legacy_scopes: list[str],
) -> tuple[list[str], list[str], list[str]]:
    """``(cut, kept, legacy shipping)`` among the pending scopes.

    Named scopes are cut exactly. Otherwise the release plan decides: ``ships``
    is cut, ``withheld`` is kept, and a fragment the table does not classify
    refuses the cut, because skipping it silently would publish a release that
    leaves work behind with no record of why.
    """
    if scopes:
        _check_named(fragment_scopes, scopes)
        return [s for s in fragment_scopes if s in scopes], [s for s in fragment_scopes if s not in scopes], []

    plan_path, classification = _classification(project_dir, version)
    unclassified = [s for s in fragment_scopes if s not in classification]
    if unclassified:
        raise CutRefused(
            "unclassified-fragment",
            f"{', '.join(unclassified)} pending as fragments but not in {plan_path.name}'s classification table",
        )
    cut = [s for s in fragment_scopes if classification[s][0] == release_readiness.SHIPS]
    kept = [s for s in fragment_scopes if classification[s][0] != release_readiness.SHIPS]
    legacy = [s for s in legacy_scopes if classification.get(s, ("",))[0] == release_readiness.SHIPS]
    return cut, kept, legacy


def _entry_block(fragment: change_fragments.Fragment, version: str) -> change_log_archive.Block:
    _preamble, blocks = change_log_archive.split(change_fragments.render_entry(fragment, release=version))
    return blocks[0]


def _headline_lines(text: str) -> list[str]:
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return lines


def _published_headline(headline_text: str, release_text: str) -> bool:
    """Whether the headline file's lines occur, consecutively, in the release file.

    Compared line by line with trailing whitespace and line endings dropped on
    both sides, so a CRLF or trailing-space headline file still matches the
    section the cut rendered from it.
    """
    want = _headline_lines(headline_text)
    have = [line.rstrip() for line in release_text.splitlines()]
    return any(have[i : i + len(want)] == want for i in range(len(have) - len(want) + 1))


def _plan_rerun(
    project_dir: Path,
    version: str,
    scopes: list[str] | None,
    fragment_scopes: list[str],
    release_file: Path,
    decl: consumer_digest.Declaration,
) -> CutPlan:
    """The cut of a release whose release file already exists: complete it, write nothing."""
    if scopes:
        _check_named(fragment_scopes, scopes)
    prawduct_dir = project_dir / ".prawduct"
    files = [f for f in change_fragments.load_pending(project_dir) if f.ok]
    cleanup = [f for f in files if change_log_archive.holds_entry(prawduct_dir, _entry_block(f.fragment, version))]
    held = {f.fragment.scope for f in cleanup}
    unheld = [s for s in fragment_scopes if s not in held]

    withheld: set[str] = set()
    if unheld:
        if scopes:
            withheld = {s for s in unheld if s not in scopes}
        else:
            # With no release plan nothing is withheld, and every unheld
            # fragment is refused below rather than read as kept.
            if release_readiness._find_release_plan(project_dir, version) is not None:
                _path, classification = _classification(project_dir, version)
                withheld = {
                    s for s in unheld if s in classification and classification[s][0] != release_readiness.SHIPS
                }
    late = [s for s in unheld if s not in withheld]
    rel = consumer_digest.release_file_rel(version)
    if late:
        raise CutRefused(
            "release-already-cut",
            f"{rel} exists, so {version} is already cut, and {', '.join(late)} is pending but not in it; "
            "a fragment written after the cut belongs to the next release, so cut it under that version",
        )

    result = CutPlan(version=version, cut=[], kept=sorted(withheld), cleanup=cleanup, digest=decl.path)
    result.release_file = release_file
    headline = project_dir / consumer_digest.HEADLINE_FILE_REL
    if headline.is_file():
        try:
            published = _published_headline(
                headline.read_text(encoding="utf-8"), release_file.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeDecodeError):
            published = False
        if published:
            result.headline_file = headline
        else:
            result.headline_kept = headline
    return result


def _today(today: date_cls | str | None) -> str:
    if today is None:
        return datetime.now(timezone.utc).date().isoformat()
    return today if isinstance(today, str) else today.isoformat()


def _release_writes(
    project_dir: Path,
    decl: consumer_digest.Declaration,
    version: str,
    fragments: list[change_fragments.Fragment],
    result: CutPlan,
    today: date_cls | str | None,
) -> None:
    """Validate the declared changelog and add the release file and the insert to ``result``.

    Each check refuses before anything is written, in the order the operator
    can act on them: where the release file would go, the changelog itself, a
    section already there, the headline, the marker.
    """
    rel = consumer_digest.release_file_rel(version)
    if change_log_archive.record_is_tracked(project_dir) and _git_ignores(project_dir, f"{consumer_digest.RELEASES_DIR_REL}/0000.md"):
        raise CutRefused(
            "releases-ignored",
            f"git would ignore {consumer_digest.RELEASES_DIR_REL}/; un-ignore it so the release file the cut writes is committed",
        )
    changelog = project_dir / decl.path
    if not changelog.is_file():
        raise CutRefused(
            "digest-missing",
            f"consumer_digest: declares {decl.path}, which is not a file; create it, or correct the path",
        )
    try:
        text = consumer_digest.read_changelog(changelog)
    except consumer_digest.DigestUnreadable as exc:
        raise CutRefused("digest-unreadable", f"{decl.path}: {exc}") from exc
    for number, line in enumerate(text.lines, start=1):
        if consumer_digest.names_release(line, version):
            raise CutRefused(
                "release-in-changelog",
                f"{decl.path} line {number} ({line.strip()!r}) is already a section for {version}; the cut writes "
                f"that section itself, so remove it, or move its first paragraph into "
                f"{consumer_digest.HEADLINE_FILE_REL} if it was the headline",
            )

    headline_path = project_dir / consumer_digest.HEADLINE_FILE_REL
    headline: str | None = None
    if headline_path.is_file():
        try:
            headline = headline_path.read_text(encoding="utf-8").strip() or None
        except (OSError, UnicodeDecodeError) as exc:
            raise CutRefused(
                "no-headline", f"{consumer_digest.HEADLINE_FILE_REL} cannot be read as UTF-8 text ({exc})"
            ) from exc
        result.headline_file = headline_path
    if decl.headline == "required" and headline is None:
        raise CutRefused(
            "no-headline",
            f"consumer_digest: requires a headline and {consumer_digest.HEADLINE_FILE_REL} is absent or blank; "
            f"write the release's one-line judgement there, and the cut puts it under the heading in {decl.path}",
        )
    try:
        index = consumer_digest.insertion_index(text, decl.marker)
    except consumer_digest.MarkerMissing as exc:
        raise CutRefused(
            "marker-missing",
            f"consumer_digest: inserts below the marker {decl.marker!r}, and no line of {decl.path} is exactly that",
        ) from exc

    section = consumer_digest.render_section(decl, version, _today(today), headline, fragments)
    result.section_text = "\n".join(section) + "\n"
    result.release_file = project_dir / rel
    lead = 1 if index > 0 and text.lines[index - 1].strip() else 0
    result.insert_line = index + lead + 1
    result.writes.append((result.release_file, result.section_text))
    result.writes.append((changelog, consumer_digest.insert_section(text, index, section).render()))
    result.notes_added = [f.scope or "" for f in consumer_digest.ordered_notes(fragments)]


def _git_ignores(project_dir: Path, rel: str) -> bool:
    from . import gitstate  # noqa: PLC0415 — lazy; git is only asked on the write path

    return gitstate.git_path_is_ignored(project_dir, rel)


def plan_cut(
    project_dir: Path,
    release: str,
    scopes: list[str] | None = None,
    *,
    today: date_cls | str | None = None,
) -> CutPlan:
    """Everything the cut would write, validated. Raises :class:`CutRefused`.

    ``today`` dates the release section (``YYYY-MM-DD``); it defaults to the
    current UTC date.
    """
    version = release_readiness.normalize_version(release)
    if not change_log_mod.RELEASE_VALUE_RE.match(version):
        raise CutRefused("bad-version", f"{release!r} is not a version like v1.2.3")
    pending = release_readiness.pending_scopes(project_dir)
    if pending.read_error is not None:
        raise CutRefused("no-change-log", pending.read_error)
    if pending.refusals:
        raise CutRefused("invalid-pending-set", "; ".join(pending.refusals))

    decl, reason = consumer_digest.read_declaration(project_dir)
    if reason is not None:
        raise CutRefused("digest-declaration-invalid", reason)
    # Ahead of every "nothing to cut" return: a run that failed while removing
    # is completed from here, and by then nothing is left to cut.
    if decl is not None:
        release_file = project_dir / consumer_digest.release_file_rel(version)
        if release_file.exists():
            return _plan_rerun(project_dir, version, scopes, pending.fragment_scopes, release_file, decl)

    if not pending.fragment_scopes and not scopes:
        return CutPlan(version=version, cut=[], kept=[], legacy_shipping=list(pending.legacy_scopes))
    # A repo that tracks its fragments but would ignore the archive would commit
    # the fragments' removal and silently drop the history they moved to.
    if change_log_archive.archive_would_be_ignored(project_dir):
        raise CutRefused(
            "archive-ignored",
            f"git would ignore {change_log_archive.ARCHIVE_DIR_REL}/; un-ignore it so the history the cut writes is committed",
        )
    cut_scopes, kept, legacy = _selected_scopes(
        project_dir, version, pending.fragment_scopes, scopes, pending.legacy_scopes
    )

    files = {f.fragment.scope: f for f in change_fragments.load_pending(project_dir) if f.ok}
    cut = [files[s] for s in cut_scopes]
    fragments = [f.fragment for f in cut]
    result = CutPlan(version=version, cut=cut, kept=kept, legacy_shipping=legacy)
    if not cut:
        return result

    archive_dir = project_dir / ".prawduct" / change_log_archive.ARCHIVE_DIR_NAME
    by_bucket: dict[str, list[change_log_archive.Block]] = {}
    for fragment in fragments:
        block = _entry_block(fragment, version)
        by_bucket.setdefault(block.bucket or "undated", []).append(block)
    for bucket, blocks in sorted(by_bucket.items()):
        path = archive_dir / f"{bucket}.md"
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        result.writes.append((path, change_log_archive._compose_bucket(existing, blocks, bucket)))
        result.buckets.append(bucket)

    if decl is not None:
        result.digest = decl.path
        _release_writes(project_dir, decl, version, fragments, result, today)
    result.none_reasons = change_fragments.none_reasons(fragments)
    return result


def apply_cut(plan: CutPlan) -> None:
    """Write the plan's files all-or-nothing, then remove what the cut consumed.

    The removals go last, cut fragments, then fragments a previous run already
    archived, then the headline file: a failure while writing leaves every file
    as it was and every fragment pending, and a failure while removing leaves
    only things the written files already hold, which a re-run finds through the
    release file and removes without writing anything.
    """
    for parent in {path.parent for path, _text in plan.writes}:
        parent.mkdir(parents=True, exist_ok=True)
    if plan.writes:
        core.write_all_or_none(plan.writes)
    removals = [item.path for item in (*plan.cut, *plan.cleanup)]
    if plan.headline_file is not None:
        removals.append(plan.headline_file)
    for path in removals:
        try:
            path.unlink()
        except OSError as exc:
            raise FragmentRemovalFailed(str(exc)) from exc


def _rel(project_dir: Path, path: Path) -> str:
    try:
        return path.relative_to(project_dir).as_posix()
    except ValueError:
        return str(path)


def _print_headline_kept(project_dir: Path, cut_plan: CutPlan) -> None:
    if cut_plan.headline_kept is not None and cut_plan.release_file is not None:
        print(
            f"  headline file: kept {_rel(project_dir, cut_plan.headline_kept)}; its text is not in "
            f"{_rel(project_dir, cut_plan.release_file)}, so it is the next release's headline"
        )


def _print_legacy(cut_plan: CutPlan) -> None:
    if cut_plan.legacy_shipping:
        print("  legacy entries carry no consumer note; /prawduct:doctor offers the move to fragments")


def cut_cmd(project_dir: Path, argv: list[str]) -> int:
    """``cut-change-log --release vX.Y.Z [--scope S]... [--apply]``. Exit 0 / 1 refused / 2 usage."""
    release: str | None = None
    scopes: list[str] = []
    apply = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--apply":
            apply = True
        elif arg in ("--release", "--scope") and i + 1 < len(argv):
            if arg == "--release":
                release = argv[i + 1]
            else:
                scopes.append(argv[i + 1])
            i += 1
        else:
            print(
                f"usage: cut-change-log --release vX.Y.Z [--scope S]... [--apply] (unexpected {arg!r})",
                file=sys.stderr,
            )
            return 2
        i += 1
    if release is None:
        print("usage: cut-change-log --release vX.Y.Z [--scope S]... [--apply]", file=sys.stderr)
        return 2
    try:
        cut_plan = plan_cut(project_dir, release, scopes or None)
    except CutRefused as exc:
        print(f"refused: {exc.code}: {exc.detail}. Nothing was written.", file=sys.stderr)
        return 1
    mode = "apply" if apply else "dry-run"
    if not cut_plan.has_work:
        print(f"cut-change-log ({mode}): no fragment ships in {cut_plan.version}; nothing to do.")
        _print_headline_kept(project_dir, cut_plan)
        _print_legacy(cut_plan)
        return 0
    if cut_plan.cut:
        print(
            f"cut-change-log ({mode}): {len(cut_plan.cut)} fragment(s) ship in {cut_plan.version}: "
            + ", ".join(item.fragment.scope for item in cut_plan.cut)
        )
        print(f"  archive: {', '.join(f'{b}.md' for b in cut_plan.buckets)}")
        if cut_plan.digest is None:
            print(
                "  consumer notes: this repo declares no consumer_digest:, so the notes stay in the archive "
                "entries. Declare consumer_digest: in .prawduct/project-state.yaml to have the cut write them "
                "to your changelog"
            )
        else:
            print(
                f"  consumer notes: {len(cut_plan.notes_added)} written to {cut_plan.digest} as a new section "
                f"at line {cut_plan.insert_line} (release file {_rel(project_dir, cut_plan.release_file)})"
            )
    else:
        print(f"cut-change-log ({mode}): {cut_plan.version} is already cut; completing that cut.")
        print(
            f"  consumer notes: the release file exists; removing {len(cut_plan.cleanup)} fragment(s) "
            "the archive already holds, writing nothing"
        )
    if cut_plan.cleanup and cut_plan.cut:
        print(f"  already archived, removing: {', '.join(item.fragment.scope for item in cut_plan.cleanup)}")
    if not cut_plan.cut and cut_plan.headline_file is not None:
        print(
            f"  headline file: removing {_rel(project_dir, cut_plan.headline_file)}, which "
            f"{_rel(project_dir, cut_plan.release_file)} already holds"
        )
    _print_headline_kept(project_dir, cut_plan)
    _print_legacy(cut_plan)
    for scope, reason in cut_plan.none_reasons:
        print(f"  none: {scope} — {reason}")
    if cut_plan.kept:
        print(f"  kept pending (withheld): {', '.join(cut_plan.kept)}")
    if not apply:
        if cut_plan.section_text is not None:
            print(f"--- section (as written to {_rel(project_dir, cut_plan.release_file)}) ---")
            sys.stdout.write(cut_plan.section_text)
            print("--- end ---")
        print("  Re-run with --apply to write. Nothing was written.")
        return 0
    try:
        apply_cut(cut_plan)
    except FragmentRemovalFailed as exc:
        print(
            f"refused: removal-failed: {exc}. The archive and notes are written; re-run to remove "
            "what remains, which writes nothing.",
            file=sys.stderr,
        )
        return 1
    except OSError as exc:
        print(f"refused: write-failed: {exc}. Every file was restored; re-run when the cause is fixed.", file=sys.stderr)
        return 1
    removed = len(cut_plan.cut) + len(cut_plan.cleanup)
    extra = " and the headline file" if cut_plan.headline_file is not None else ""
    if cut_plan.cut and cut_plan.digest is not None:
        print(f"  removed {removed} fragment(s){extra}; commit the archive, release file, changelog and removals together.")
    elif cut_plan.cut:
        print(f"  removed {removed} fragment(s); commit the archive and removals together.")
    else:
        print(f"  removed {removed} fragment(s){extra}; nothing was written.")
    return 0
