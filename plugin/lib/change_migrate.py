"""Moving a legacy change log's release-pending entries into change fragments.

A repo that recorded changes in the single-file log (`.prawduct/change-log.md`)
moves onto fragments by converting the entries that have not shipped yet: each
becomes `.prawduct/changes/<scope>.md` and leaves the log. Shipped and untagged
entries stay where they are, because archived history is never rewritten. The
conversion rules and refusals belong to the format's owner,
:func:`change_fragments.legacy_entries_as_fragments`; this module reads the log,
refuses what would lose a record, and writes the result all-or-nothing.

The result is meant to be one commit, so `git revert` undoes it, and a second
run finds nothing left to convert.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from . import change_fragments
from . import change_log as change_log_mod
from . import core

USAGE = "usage: migrate-change-log [--default-type TYPE] [--apply]"


class MigrationRefused(Exception):
    """The migration cannot proceed; nothing was written."""

    def __init__(self, problems: list[change_fragments.Problem]) -> None:
        super().__init__("; ".join(str(p) for p in problems))
        self.problems = problems


def _fragments_would_be_ignored(project_dir: Path) -> bool:
    """True when git tracks the live log but would ignore the fragment directory.

    The migration then commits the entries' removal from the log and none of the
    fragments they moved to, which loses the pending record with no error.
    """
    from . import gitstate  # noqa: PLC0415 — lazy; git is only asked on the write path

    if gitstate.git_path_is_tracked(project_dir, change_log_mod.CHANGE_LOG_REL_PATH) is not True:
        return False
    return gitstate.git_path_is_ignored(project_dir, f"{change_fragments.FRAGMENT_DIR_REL}/0000.md")


#: The first release whose readers accept change fragments. A clone whose
#: committed install reference pins an older release would read a migrated repo
#: as having nothing pending, so the migration refuses to strand it.
FRAGMENT_READERS_RELEASE = (3, 7, 2)

_PINNED_RELEASE_RE = re.compile(r"v?(\d+)\.(\d+)\.(\d+)")


def install_pin_too_old(project_dir: Path) -> str | None:
    """The committed install reference's ``ref`` when it pins a release older than
    :data:`FRAGMENT_READERS_RELEASE`, else ``None``.

    A branch (``main``), a commit or an unreadable reference is not a pin this
    can judge, so it answers ``None``: the check exists for the one case it can
    see, a clone that would keep running pre-fragment readers after migrating.
    """
    from .migrate_plugin import INSTALL_REFERENCE  # noqa: PLC0415 — lazy; only the migration asks

    marketplace = next(iter(INSTALL_REFERENCE["extraKnownMarketplaces"]))
    try:
        data = json.loads((project_dir / ".claude" / "settings.json").read_text(encoding="utf-8"))
        ref = data["extraKnownMarketplaces"][marketplace]["source"]["ref"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
        return None
    match = _PINNED_RELEASE_RE.fullmatch(ref) if isinstance(ref, str) else None
    if match is None:
        return None
    return ref if tuple(int(g) for g in match.groups()) < FRAGMENT_READERS_RELEASE else None


def plan_migration(
    project_dir: Path, *, default_type: str | None = None
) -> tuple[list[tuple[Path, str]], tuple[tuple[str, str], ...]]:
    """``(writes, defaulted)``: every ``(path, text)`` the migration would write,
    and each scope that took ``default_type``. With nothing pending, the writes are
    the fragment directory's ``.gitkeep`` when it is missing, else none.

    Raises :class:`MigrationRefused` when any entry needs its author's decision,
    when a fragment for a converted scope already exists, or when git would
    ignore the fragments.
    """
    log_path = project_dir / change_log_mod.CHANGE_LOG_REL_PATH
    if not log_path.is_file():
        return [], ()
    try:
        text = log_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise MigrationRefused([change_fragments.Problem("unreadable", f"{log_path.name}: {exc}")]) from exc
    conversion = change_fragments.legacy_entries_as_fragments(text, default_type=default_type)
    if conversion.refusals:
        raise MigrationRefused(list(conversion.refusals))
    directory = project_dir / change_fragments.FRAGMENT_DIR_REL
    if not conversion.fragments and directory.is_dir():
        return [], ()

    pinned = install_pin_too_old(project_dir)
    if pinned is not None:
        first = "v" + ".".join(map(str, FRAGMENT_READERS_RELEASE))
        raise MigrationRefused(
            [
                change_fragments.Problem(
                    "plugin-pin-too-old",
                    f".claude/settings.json pins prawduct to {pinned}, whose readers predate change "
                    f"fragments; every clone would see nothing pending. Move the pin to {first} or later first",
                )
            ]
        )
    existing = [scope for scope, _ in conversion.fragments if (directory / f"{scope}.md").exists()]
    if existing:
        raise MigrationRefused(
            [
                change_fragments.Problem(
                    "fragment-exists",
                    f"{change_fragments.FRAGMENT_DIR_REL}/{scope}.md already exists, and the log still "
                    "holds a pending entry for that scope; keep one of the two",
                )
                for scope in existing
            ]
        )
    if _fragments_would_be_ignored(project_dir):
        raise MigrationRefused(
            [
                change_fragments.Problem(
                    "fragments-ignored",
                    f"git would ignore {change_fragments.FRAGMENT_DIR_REL}/; un-ignore it so the "
                    "fragments are committed with the entries' removal from the log",
                )
            ]
        )
    writes = [(directory / f"{scope}.md", fragment) for scope, fragment in conversion.fragments]
    # The directory is how readers know the repo records fragments, and git drops
    # an empty one: without this, the first release that ships every fragment
    # leaves a fresh clone that looks like a repo still on the single-file log.
    # A log with nothing pending still gets it: adopting the format is having the
    # directory, so new work is recorded as fragments from the next branch on.
    keep = directory / ".gitkeep"
    if not keep.exists():
        writes.append((keep, ""))
    if not conversion.fragments:
        return writes, ()
    writes.append((log_path, conversion.remaining))
    return writes, conversion.defaulted


def migrate_cmd(project_dir: Path, argv: list[str]) -> int:
    """``migrate-change-log [--default-type TYPE] [--apply]``. Exit 0 done or nothing to do / 1 refused / 2 usage."""
    apply = False
    default_type: str | None = None
    args = list(argv)
    while args:
        arg = args.pop(0)
        if arg == "--apply":
            apply = True
        elif arg == "--default-type" and args and args[0] in change_fragments.TYPES:
            default_type = args.pop(0)
        else:
            print(
                f"{USAGE} (unexpected {arg!r}; --default-type takes one of "
                f"{', '.join(change_fragments.TYPES)})",
                file=sys.stderr,
            )
            return 2
    try:
        writes, defaulted = plan_migration(project_dir, default_type=default_type)
    except MigrationRefused as exc:
        for problem in exc.problems:
            print(f"refused: {problem}", file=sys.stderr)
        untyped = sum(p.code in ("missing-type", "bad-type") for p in exc.problems)
        if untyped and default_type is None:
            print(
                f"{untyped} entr(ies) have no type in the closed set "
                f"({', '.join(change_fragments.TYPES)}): add one to each, or re-run with "
                "--default-type TYPE to give every such entry that one type.",
                file=sys.stderr,
            )
        print("Nothing was written.", file=sys.stderr)
        return 1
    mode = "apply" if apply else "dry-run"
    if not writes:
        print(f"migrate-change-log ({mode}): no release-pending entry in the legacy change log; nothing to do.")
        return 0
    directory = project_dir / change_fragments.FRAGMENT_DIR_REL
    fragments = [path for path, _ in writes if path.suffix == ".md" and path.parent == directory]
    if not fragments:
        keep = directory / ".gitkeep"
        print(
            f"migrate-change-log ({mode}): no release-pending entry to convert; "
            f"{keep.relative_to(project_dir)} makes this repo record new changes as fragments."
        )
        if apply:
            keep.parent.mkdir(parents=True, exist_ok=True)
            try:
                core.write_all_or_none(writes)
            except OSError as exc:
                print(f"refused: write-failed: {exc}. Every file was restored.", file=sys.stderr)
                return 1
            print("  wrote it; commit it.")
        else:
            print("  Re-run with --apply to write. Nothing was written.")
        return 0
    print(f"migrate-change-log ({mode}): {len(fragments)} release-pending entry(ies) become fragments:")
    for path in fragments:
        print(f"  {path.relative_to(project_dir)}")
    for scope, legacy in defaulted:
        print(f"  {scope}: type={default_type} (was {f'type={legacy}' if legacy else 'untyped'})")
    print(
        "  Each gets a `none:` consumer note saying it was migrated; write the real note where "
        "consumers need one. The cut's dry run lists every `none:`."
    )
    if not apply:
        print("  Re-run with --apply to write. Nothing was written.")
        return 0
    fragments[0].parent.mkdir(parents=True, exist_ok=True)
    try:
        core.write_all_or_none(writes)
    except OSError as exc:
        print(f"refused: write-failed: {exc}. Every file was restored.", file=sys.stderr)
        return 1
    print(
        f"  wrote {len(fragments)} fragment(s) and removed their entries from "
        f"{change_log_mod.CHANGE_LOG_REL_PATH}; commit them together so `git revert` undoes it."
    )
    return 0
