"""The release cut: shipping change fragments into the archive and the release notes.

A fragment (`lib/change_fragments.py`) records one scope's change while it is
pending. At a release the cut does three things to every fragment that ships,
and nothing to the rest:

1. renders it into the change-log archive's month file as an entry tagged
   ``release=vX.Y.Z``, in the archive's existing grammar;
2. writes its consumer note under the open section's headline in the consumer
   digest (`plugin/CHANGELOG.md`), when the repo publishes one;
3. removes the fragment, so the fragment directory is exactly the pending set.

What ships is decided by the release plan's classification table, or by
naming the scopes. Everything is
validated before anything is written, the writes are all-or-nothing, and the
fragments are removed last, so a run that fails part-way can simply be re-run:
the archive composer skips an entry it already holds, and a note already in the
digest is not added twice.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

from . import change_fragments
from . import change_log as change_log_mod
from . import change_log_archive
from . import core
from . import release_readiness


class CutRefused(Exception):
    """The cut cannot proceed; nothing was written. ``code`` names the reason."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class FragmentRemovalFailed(OSError):
    """The archive and digest were written, but a cut fragment could not be removed."""


@dataclass
class CutPlan:
    """What a cut would do, computed without writing anything."""

    version: str
    cut: list[change_fragments.FragmentFile]
    kept: list[str]
    writes: list[tuple[Path, str]] = field(default_factory=list)
    buckets: list[str] = field(default_factory=list)
    notes_added: list[str] = field(default_factory=list)
    digest: str | None = None
    none_reasons: list[tuple[str, str]] = field(default_factory=list)


def _selected_scopes(
    project_dir: Path, version: str, fragment_scopes: list[str], scopes: list[str] | None
) -> tuple[list[str], list[str]]:
    """``(cut, kept)`` among the pending fragment scopes.

    Named scopes are cut exactly. Otherwise the release plan decides: ``ships``
    is cut, ``withheld`` is kept, and a fragment the table does not classify
    refuses the cut, because skipping it silently would publish a release that
    leaves work behind with no record of why.
    """
    if scopes:
        unknown = sorted(set(scopes) - set(fragment_scopes))
        if unknown:
            raise CutRefused(
                "unknown-scope",
                f"no pending fragment for {', '.join(unknown)} in {change_fragments.FRAGMENT_DIR_REL}/",
            )
        return [s for s in fragment_scopes if s in scopes], [s for s in fragment_scopes if s not in scopes]

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
    unclassified = [s for s in fragment_scopes if s not in classification]
    if unclassified:
        raise CutRefused(
            "unclassified-fragment",
            f"{', '.join(unclassified)} pending as fragments but not in {plan_path.name}'s classification table",
        )
    cut = [s for s in fragment_scopes if classification[s][0] == release_readiness.SHIPS]
    kept = [s for s in fragment_scopes if classification[s][0] != release_readiness.SHIPS]
    return cut, kept


def _digest_write(
    project_dir: Path, fragments: list[change_fragments.Fragment]
) -> tuple[tuple[Path, str] | None, list[str], str | None]:
    """``(write or None, scopes noted, the digest's open heading)``.

    Notes go under the open section's headline, which the cut never writes:
    the headline is the release's one-sentence judgement, and the banner shows
    it to every repo that crosses this version. A section with no headline is
    refused rather than given one. A repo that publishes no digest gets no
    write and no refusal: there is nothing for the notes to join.
    """
    path = project_dir / release_readiness._DIGEST_REL_PATH
    if not path.is_file():
        return None, [], None
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    section = release_readiness._open_digest_section(lines)
    if section is None:
        raise CutRefused("no-headline", f"{release_readiness._DIGEST_REL_PATH} has no `## ` section to write into")
    heading, body = section
    start = next(i for i, line in enumerate(lines) if line.strip() == heading)
    headline_offset = next((i for i, line in enumerate(body) if line.strip()), None)
    if headline_offset is None:
        raise CutRefused(
            "no-headline",
            f"the open section {heading!r} has no headline; write its first line before cutting",
        )
    section_text = "\n".join(body)
    fresh = [f for f in fragments if f.consumer_text and f"**`{f.scope}`**:" not in section_text]
    if not fresh:
        return None, [], heading
    # The headline is a paragraph; notes start after its blank line.
    insert_at = start + 1 + headline_offset
    while insert_at < len(lines) and lines[insert_at].strip():
        insert_at += 1
    notes = change_fragments.render_consumer_section(fresh)
    new_lines = lines[:insert_at] + ["", *notes.splitlines()] + lines[insert_at:]
    new_text = "\n".join(new_lines) + ("\n" if text.endswith("\n") else "")
    return (path, new_text), [f.scope or "" for f in fresh], heading


def plan_cut(project_dir: Path, release: str, scopes: list[str] | None = None) -> CutPlan:
    """Everything the cut would write, validated. Raises :class:`CutRefused`."""
    version = release_readiness.normalize_version(release)
    if not change_log_mod.RELEASE_VALUE_RE.match(version):
        raise CutRefused("bad-version", f"{release!r} is not a version like v1.2.3")
    pending = release_readiness.pending_scopes(project_dir)
    if pending.read_error is not None:
        raise CutRefused("no-change-log", pending.read_error)
    if pending.refusals:
        raise CutRefused("invalid-pending-set", "; ".join(pending.refusals))
    if not pending.fragment_scopes and not scopes:
        return CutPlan(version=version, cut=[], kept=[])
    # A repo that tracks its fragments but would ignore the archive would commit
    # the fragments' removal and silently drop the history they moved to.
    if change_log_archive.archive_would_be_ignored(project_dir):
        raise CutRefused(
            "archive-ignored",
            f"git would ignore {change_log_archive.ARCHIVE_DIR_REL}/; un-ignore it so the history the cut writes is committed",
        )
    cut_scopes, kept = _selected_scopes(project_dir, version, pending.fragment_scopes, scopes)

    files = {f.fragment.scope: f for f in change_fragments.load_pending(project_dir) if f.ok}
    cut = [files[s] for s in cut_scopes]
    fragments = [f.fragment for f in cut]
    result = CutPlan(version=version, cut=cut, kept=kept)
    if not cut:
        return result

    prawduct_dir = project_dir / ".prawduct"
    archive_dir = prawduct_dir / change_log_archive.ARCHIVE_DIR_NAME
    by_bucket: dict[str, list[change_log_archive.Block]] = {}
    for fragment in fragments:
        _preamble, blocks = change_log_archive.split(
            change_fragments.render_entry(fragment, release=version)
        )
        block = blocks[0]
        by_bucket.setdefault(block.bucket or "undated", []).append(block)
    for bucket, blocks in sorted(by_bucket.items()):
        path = archive_dir / f"{bucket}.md"
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        result.writes.append((path, change_log_archive._compose_bucket(existing, blocks, bucket)))
        result.buckets.append(bucket)

    digest_write, noted, heading = _digest_write(project_dir, fragments)
    if digest_write is not None:
        result.writes.append(digest_write)
    result.notes_added = noted
    result.digest = heading
    result.none_reasons = change_fragments.none_reasons(fragments)
    return result


def apply_cut(plan: CutPlan) -> None:
    """Write the plan's files all-or-nothing, then remove the cut fragments.

    The fragments go last: a failure while writing leaves every file as it was
    and every fragment pending, and a failure while removing leaves fragments
    the archive already holds, which a re-run finds and removes without
    duplicating anything.
    """
    if plan.writes:
        plan.writes[0][0].parent.mkdir(parents=True, exist_ok=True)
        core.write_all_or_none(plan.writes)
    for item in plan.cut:
        try:
            item.path.unlink()
        except OSError as exc:
            raise FragmentRemovalFailed(str(exc)) from exc


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
    if not cut_plan.cut:
        print(f"cut-change-log ({mode}): no fragment ships in {cut_plan.version}; nothing to do.")
        return 0
    print(
        f"cut-change-log ({mode}): {len(cut_plan.cut)} fragment(s) ship in {cut_plan.version}: "
        + ", ".join(item.fragment.scope for item in cut_plan.cut)
    )
    print(f"  archive: {', '.join(f'{b}.md' for b in cut_plan.buckets)}")
    if cut_plan.digest is None:
        print("  consumer notes: this repo publishes no consumer digest; the notes stay in the archive entries")
    else:
        print(f"  consumer notes: {len(cut_plan.notes_added)} added under {cut_plan.digest!r}")
    for scope, reason in cut_plan.none_reasons:
        print(f"  none: {scope} — {reason}")
    if cut_plan.kept:
        print(f"  kept pending (withheld): {', '.join(cut_plan.kept)}")
    if not apply:
        print("  Re-run with --apply to write. Nothing was written.")
        return 0
    try:
        apply_cut(cut_plan)
    except FragmentRemovalFailed as exc:
        print(
            f"refused: removal-failed: {exc}. The archive and notes are written; re-run to remove "
            "the remaining fragments, which adds nothing twice.",
            file=sys.stderr,
        )
        return 1
    except OSError as exc:
        print(f"refused: write-failed: {exc}. Every file was restored; re-run when the cause is fixed.", file=sys.stderr)
        return 1
    shipped = len(cut_plan.cut)
    print(f"  removed {shipped} fragment(s); commit the archive, digest and removals together.")
    return 0
