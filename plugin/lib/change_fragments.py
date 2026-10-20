"""One file per change: reading and validating `.prawduct/changes/<scope>.md`.

A branch records its change as one new file named for its scope, so two branches
never edit the same file and the change record merges without a union driver.
This module is the **single owner** of that format: no other module parses a
fragment, and readers ask it rather than knowing the layout.

A fragment is YAML-style frontmatter, a narrative, and a required consumer note::

    ---
    schema: 1
    type: fix
    scope: backlog-file-path
    date: 2026-10-17
    title: backlog file writes only to its own repo
    closes: [brookstalley/prawduct#1004, BKL-6J2X]
    ---
    What changed and why, naming every chunk shipped. Subheadings use ``###``.

    ## Consumer note
    What someone using the product needs to know, or exactly one line
    ``none: <reason>`` when there is nothing to tell them.

Every file in the directory is release-pending: the release cut moves a shipped
fragment's content into the change-log archive and removes the file, so a
``release`` key never appears here and is refused when it does.

The persisted schema answers a fixed set of consumer questions, and a key exists
only because one of them asks it: which scopes are pending, which plan a scope
belongs to, what a release tells its consumers, which backlog items a change
closes, which earlier scope a change reopens, and whether a newer plugin wrote
the file.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date as _date
from pathlib import Path

from . import change_log as change_log_mod
from . import plan_index
from .backlog import ids

FRAGMENT_DIR_REL = ".prawduct/changes"

#: The schema version this plugin writes and reads. A fragment declaring a higher
#: one was written by a newer plugin and is refused rather than misread.
SCHEMA_VERSION = 1

#: The closed set of change types. Synonyms in the legacy log (`feat`, `bugfix`,
#: `improvement`) are normalised by the migration, never accepted here.
TYPES = ("feature", "fix", "chore", "docs", "refactor", "perf", "governance")

REQUIRED_KEYS = ("schema", "type", "scope", "date", "title")
OPTIONAL_KEYS = ("closes", "reopens")

CONSUMER_NOTE_HEADING = "## Consumer note"

# A scope is also a filename stem, so it must be a safe path component on every
# platform: lowercase letters, digits and hyphens, starting with a letter or
# digit. Dots are allowed between them because version-named scopes
# (`release-v3.7.1`, `dev-track-bump-3.7.1-dev.2`) recur in every release's
# record; a dot is never leading, trailing or doubled, so the stem never ends in a
# dot (Windows drops one) and `Path.stem` of `<scope>.md` is the scope. A dot
# must be followed by a letter or digit; hyphens keep the rule they had.
_SCOPE_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]|\.(?=[a-z0-9]))*")
_KEY_LINE_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*):(.*)")
_NONE_RE = re.compile(r"none:(.*)", re.IGNORECASE)
# `date.fromisoformat` accepts compact and week forms from Python 3.11 on, so the
# shape is pinned first: the archive header is always `YYYY-MM-DD`.
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True)
class Problem:
    """One reason a fragment is refused: a stable code and what it found."""

    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


class FragmentError(ValueError):
    """The file cannot be read as a fragment at all, so no field can be checked."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.problem = Problem(code, detail)


@dataclass(frozen=True)
class Fragment:
    """A parsed fragment. Field values are as written; validation is separate."""

    filename_stem: str
    keys: dict[str, str | tuple[str, ...]]
    duplicate_keys: tuple[str, ...]
    narrative: str
    consumer_note: str | None
    consumer_note_headings: int
    body_h2_lines: tuple[str, ...]

    def _scalar(self, key: str) -> str | None:
        value = self.keys.get(key)
        return value if isinstance(value, str) else None

    @property
    def scope(self) -> str | None:
        return self._scalar("scope")

    @property
    def type(self) -> str | None:
        return self._scalar("type")

    @property
    def date(self) -> str | None:
        return self._scalar("date")

    @property
    def title(self) -> str | None:
        return self._scalar("title")

    @property
    def reopens(self) -> str | None:
        return self._scalar("reopens")

    @property
    def closes(self) -> tuple[str, ...]:
        value = self.keys.get("closes")
        return value if isinstance(value, tuple) else ()

    @property
    def none_reason(self) -> str | None:
        """The reason given by a ``none: <reason>`` consumer note, else ``None``."""
        if self.consumer_note is None:
            return None
        match = _NONE_RE.fullmatch(self.consumer_note.strip())
        return match.group(1).strip() if match else None

    @property
    def consumer_text(self) -> str | None:
        """The note's text for consumers, or ``None`` when it is absent or ``none:``."""
        if self.consumer_note is None or not self.consumer_note.strip():
            return None
        if _NONE_RE.fullmatch(self.consumer_note.strip()):
            return None
        return self.consumer_note.strip()


@dataclass(frozen=True)
class FragmentFile:
    """One file in the fragment directory and what reading it found."""

    path: Path
    fragment: Fragment | None
    problems: tuple[Problem, ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        return self.fragment is not None and not self.problems


def _strip_comment(raw: str) -> str:
    """Drop a trailing ``# comment``, YAML's way: only after whitespace.

    A bare ``#`` is part of the value, which is what lets ``owner/repo#1004``
    survive. The plan reader treats any ``#`` as a comment, which is right for the
    values it reads and would truncate every issue reference here.
    """
    in_quote: str | None = None
    for i, ch in enumerate(raw):
        if in_quote:
            if ch == in_quote:
                in_quote = None
        elif ch in ("'", '"'):
            in_quote = ch
        elif ch == "#" and (i == 0 or raw[i - 1] in (" ", "\t")):
            return raw[:i]
    return raw


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _parse_value(raw: str) -> str | tuple[str, ...]:
    value = _strip_comment(raw).strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return ()
        return tuple(_unquote(item.strip()) for item in inner.split(","))
    return _unquote(value)


def parse_fragment(text: str, *, filename: str) -> Fragment:
    """Split a fragment into frontmatter keys, narrative and consumer note.

    Raises :class:`FragmentError` only when there is no frontmatter block or a
    line in it is not ``key: value``, because then no field can be trusted.
    Everything else is collected for :func:`validate_fragment` to judge, so one
    run reports every problem rather than the first.
    """
    span = plan_index.frontmatter_span(text)
    if span is None:
        raise FragmentError(
            "no-frontmatter",
            "the file must open with a `---` frontmatter block closed by a second `---`",
        )
    lines = text.splitlines()
    keys: dict[str, str | tuple[str, ...]] = {}
    duplicates: list[str] = []
    for number, line in enumerate(lines[span[0] + 1 : span[1]], start=span[0] + 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1] in (" ", "\t"):
            raise FragmentError(
                "bad-frontmatter-line",
                f"line {number} is indented; fragment frontmatter is flat `key: value` lines",
            )
        match = _KEY_LINE_RE.fullmatch(line.rstrip())
        if not match:
            raise FragmentError(
                "bad-frontmatter-line", f"line {number} is not `key: value`: {line.strip()!r}"
            )
        key = match.group(1)
        if key in keys:
            duplicates.append(key)
            continue
        keys[key] = _parse_value(match.group(2))

    body_lines = lines[span[1] + 1 :]
    note_indices = [i for i, line in enumerate(body_lines) if line.rstrip() == CONSUMER_NOTE_HEADING]
    if note_indices:
        first = note_indices[0]
        narrative_lines = body_lines[:first]
        note_lines = body_lines[first + 1 :]
        if len(note_indices) > 1:
            note_lines = body_lines[first + 1 : note_indices[1]]
        consumer_note: str | None = "\n".join(note_lines).strip()
    else:
        narrative_lines = body_lines
        consumer_note = None
    h2_lines = tuple(
        line.rstrip()
        for line in body_lines
        if line.startswith("## ") and line.rstrip() != CONSUMER_NOTE_HEADING
    )
    return Fragment(
        filename_stem=Path(filename).stem,
        keys=keys,
        duplicate_keys=tuple(duplicates),
        narrative="\n".join(narrative_lines).strip(),
        consumer_note=consumer_note,
        consumer_note_headings=len(note_indices),
        body_h2_lines=h2_lines,
    )


def _closes_problems(values: tuple[str, ...]) -> list[Problem]:
    problems = []
    for value in values:
        if ids.is_pfx(value) and value == value.strip():
            continue
        normalized = ids.normalize_id(value)
        if normalized.ok and normalized.canonical == value:
            continue
        problems.append(
            Problem(
                "bad-closes",
                f"{value!r} is not a backlog item ID; write `owner/repo#N` for an issue "
                "or the markdown backlog's `PFX-XXXX`",
            )
        )
    return problems


def validate_fragment(fragment: Fragment) -> list[Problem]:
    """Every schema problem in ``fragment``, in a stable order. Empty means valid."""
    problems: list[Problem] = []
    keys = fragment.keys

    for key in fragment.duplicate_keys:
        problems.append(Problem("duplicate-key", f"`{key}` is set more than once"))
    if "release" in keys:
        problems.append(
            Problem(
                "released-fragment",
                "`release` is never written on a fragment: the release cut moves a shipped "
                "fragment into the archive, so every file here is pending",
            )
        )
    for key in keys:
        if key in change_log_mod.RETIRED_TAG_KEYS:
            problems.append(Problem("retired-key", f"`{key}` is retired and read by nothing"))
        elif key not in REQUIRED_KEYS and key not in OPTIONAL_KEYS and key != "release":
            problems.append(
                Problem(
                    "unknown-key",
                    f"`{key}` is not a fragment key; the keys are "
                    f"{', '.join(REQUIRED_KEYS + OPTIONAL_KEYS)}",
                )
            )
    for key in REQUIRED_KEYS:
        if key not in keys or keys[key] in ("", ()):
            problems.append(Problem("missing-key", f"`{key}` is required"))

    schema = keys.get("schema")
    if isinstance(schema, str) and schema:
        if not schema.isdigit() or int(schema) < 1:
            problems.append(Problem("bad-schema", f"`schema` must be a whole number, got {schema!r}"))
        elif int(schema) > SCHEMA_VERSION:
            problems.append(
                Problem(
                    "schema-ahead",
                    f"written by schema {schema}, and this plugin reads schema "
                    f"{SCHEMA_VERSION}; update the plugin rather than editing the fragment",
                )
            )

    kind = fragment.type
    if kind and kind not in TYPES:
        problems.append(Problem("bad-type", f"{kind!r} is not one of {', '.join(TYPES)}"))

    scope = fragment.scope
    if scope:
        if not _SCOPE_RE.fullmatch(scope):
            problems.append(
                Problem("bad-scope-slug", f"{scope!r} must be lowercase letters, digits, hyphens and single interior dots")
            )
        if scope != fragment.filename_stem:
            problems.append(
                Problem(
                    "scope-mismatch",
                    f"`scope: {scope}` must equal the filename stem {fragment.filename_stem!r}",
                )
            )

    when = fragment.date
    if when:
        try:
            if not _DATE_RE.fullmatch(when):
                raise ValueError(when)
            _date.fromisoformat(when)
        except ValueError:
            problems.append(Problem("bad-date", f"{when!r} is not a YYYY-MM-DD date"))

    for key in ("schema", "type", "scope", "date", "title", "reopens"):
        if isinstance(keys.get(key), tuple):
            problems.append(Problem("bad-value", f"`{key}` takes one value, not a list"))

    closes = keys.get("closes")
    if isinstance(closes, str):
        problems.append(Problem("bad-closes", "`closes` is a list: `closes: [owner/repo#N]`"))
    elif closes:
        problems.extend(_closes_problems(closes))

    reopens = fragment.reopens
    if "reopens" in keys and not reopens:
        problems.append(Problem("bad-reopens", "`reopens` names the scope this change reopens"))
    elif reopens and not _SCOPE_RE.fullmatch(reopens):
        problems.append(Problem("bad-reopens", f"{reopens!r} is not a scope"))

    if not fragment.narrative:
        problems.append(Problem("empty-narrative", "say what changed and why above the consumer note"))
    for line in fragment.body_h2_lines:
        problems.append(
            Problem(
                "h2-in-body",
                f"{line!r}: only `{CONSUMER_NOTE_HEADING}` is a `##` heading here; use `###`, "
                "because `##` starts a new entry once the fragment is archived",
            )
        )

    if fragment.consumer_note_headings == 0:
        problems.append(
            Problem(
                "missing-consumer-note",
                f"add `{CONSUMER_NOTE_HEADING}` with the text for consumers, "
                "or `none: <reason>` when there is nothing to tell them",
            )
        )
    elif fragment.consumer_note_headings > 1:
        problems.append(Problem("duplicate-consumer-note", f"`{CONSUMER_NOTE_HEADING}` appears more than once"))
    elif not fragment.consumer_note:
        problems.append(
            Problem("empty-consumer-note", "write the note, or `none: <reason>` when there is nothing to tell consumers")
        )
    elif _NONE_RE.fullmatch(fragment.consumer_note.strip()) and not fragment.none_reason:
        problems.append(Problem("empty-consumer-note", "`none:` needs a reason after it"))

    return problems


def check_fragment_text(text: str, path: Path) -> FragmentFile:
    """Parse and validate fragment ``text`` that belongs at ``path``.

    For callers that read the text from somewhere other than the working tree,
    such as a commit; :func:`read_fragment_file` is the disk form.
    """
    try:
        fragment = parse_fragment(text, filename=path.name)
    except FragmentError as exc:
        return FragmentFile(path, None, (exc.problem,))
    return FragmentFile(path, fragment, tuple(validate_fragment(fragment)))


def read_fragment_file(path: Path) -> FragmentFile:
    """Read and validate one fragment file; never raises for a bad fragment."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return FragmentFile(path, None, (Problem("unreadable", str(exc)),))
    return check_fragment_text(text, path)


def load_pending(root: Path) -> list[FragmentFile]:
    """Every fragment file under ``root``, sorted by filename. Each one is pending.

    Only ``*.md`` files are fragments, so a ``.gitkeep`` that holds the directory
    open is not one. A missing directory is an empty pending set.
    """
    directory = root / FRAGMENT_DIR_REL
    if not directory.is_dir():
        return []
    return [read_fragment_file(path) for path in sorted(directory.glob("*.md"))]


def render_entry(fragment: Fragment, *, release: str | None = None) -> str:
    """The fragment as a block in the change-log archive's existing grammar.

    The archive keeps its format, so its parser and invariants are unchanged:
    ``## date: title``, one tag line, then the body. ``closes`` and ``reopens``
    ride the tag line as keys the legacy parser preserves, and the consumer note
    follows the narrative under a bold label rather than a heading, because a
    ``##`` would start a new archive entry.
    """
    tags = [f"type={fragment.type}", f"scope={fragment.scope}"]
    if fragment.closes:
        tags.append("closes=" + ",".join(fragment.closes))
    if fragment.reopens:
        tags.append(f"reopens={fragment.reopens}")
    if release is not None:
        if not change_log_mod.RELEASE_VALUE_RE.match(release):
            raise ValueError(f"release must be a version like v1.2.3, got {release!r}")
        tags.append(f"release={release}")
    note = fragment.consumer_note or ""
    return (
        f"## {fragment.date}: {fragment.title}\n\n"
        f"<!-- prawduct: {' | '.join(tags)} -->\n\n"
        f"{fragment.narrative}\n\n"
        f"**Consumer note:**\n\n{note}\n"
    )


def render_consumer_section(fragments: list[Fragment]) -> str:
    """The `plugin/CHANGELOG.md` paragraphs for ``fragments`` that have consumer text.

    Newest first, ties broken by scope, so the output is stable. ``none:`` notes
    contribute nothing here; :func:`none_reasons` lists them for the operator.
    """
    with_text = [f for f in fragments if f.consumer_text]
    # Two stable sorts: scope ascending, then date descending, so same-day scopes
    # read alphabetically under the newest-first order.
    ordered = sorted(with_text, key=lambda f: f.scope or "")
    ordered = sorted(ordered, key=lambda f: f.date or "", reverse=True)
    return "\n\n".join(f"**`{f.scope}`**: {f.consumer_text}" for f in ordered)


def none_reasons(fragments: list[Fragment]) -> list[tuple[str, str]]:
    """``(scope, reason)`` for every fragment whose consumer note is ``none:``."""
    return sorted(
        (f.scope or "", f.none_reason) for f in fragments if f.none_reason is not None
    )


@dataclass(frozen=True)
class RecordedChange:
    """One scope's change record, wherever it lives now.

    ``source`` is ``"fragment"`` while the change is pending and ``"archive"``
    once a cut has moved it; ``text`` is what a reviewer reads either way.
    """

    scope: str
    closes: tuple[str, ...]
    source: str
    path: str
    text: str


@dataclass(frozen=True)
class BranchRecord:
    """What a branch recorded about its own change: fragments it added, and
    archive entries it added by cutting its own fragments (a trunk PR, PR Step
    1d). ``error`` names a git failure, and then ``changes`` is not the whole answer.
    """

    changes: tuple[RecordedChange, ...] = ()
    error: str | None = None


def _git(project_dir: Path, *args: str) -> tuple[int, str]:
    """``(returncode, stdout)`` through the shared read-only runner, which never
    raises and decodes any byte. A non-zero code carries a description instead."""
    from . import gitstate  # noqa: PLC0415 — lazy; only the branch-record readers run git

    code, out = gitstate._run_git_text(project_dir, *args)
    return code, out if code == 0 else f"git {' '.join(args[:2])} exited {code}"


def _archived_change(block_text: str, path: str) -> RecordedChange | None:
    entries = change_log_mod.parse_change_log(block_text)
    scope = entries[0].tags.get("scope") if entries else None
    if not isinstance(scope, str) or not scope:
        return None
    raw = entries[0].tags.get("closes")
    closes = tuple(c.strip() for c in raw.split(",") if c.strip()) if isinstance(raw, str) else ()
    return RecordedChange(scope=scope, closes=closes, source="archive", path=path, text=block_text)


def branch_change_record(project_dir: Path, base: str) -> BranchRecord:
    """The one answer to "what change record did this branch add?".

    A fragment the branch added is found in its diff. A trunk PR cuts its own
    fragment before review (PR Step 1d), so the fragment is in neither the diff
    nor the merged tree; what the branch added instead is an archive entry, and
    that is found here too. An archive entry is the branch's own only when its
    text is in neither the base's archive nor the base's live log: the size
    archive moves entries verbatim out of the live log, and those are history,
    not this branch's record. Readers with a branch diff (Step 1c, the reviewer
    payload) read the record through this; the merge-time close, which runs
    after the diff is gone, reads :func:`scope_change_record`.
    """
    from . import change_log_archive  # noqa: PLC0415 — the archive's splitter owns entry boundaries

    code, merge_base = _git(project_dir, "merge-base", base, "HEAD")
    if code != 0:
        return BranchRecord(error=f"cannot find the merge-base of {base} and HEAD ({merge_base})")
    merge_base = merge_base.strip()
    changes: list[RecordedChange] = []

    code, out = _git(
        project_dir, "diff", "--name-only", "--diff-filter=A", f"{merge_base}..HEAD", "--", FRAGMENT_DIR_REL + "/"
    )
    if code != 0:
        return BranchRecord(error=f"git diff of {FRAGMENT_DIR_REL}/ failed: {out}")
    for rel in (line.strip() for line in out.splitlines()):
        if not rel.endswith(".md"):
            continue
        code, text = _git(project_dir, "show", f"HEAD:{rel}")
        if code != 0:
            return BranchRecord(error=f"git show HEAD:{rel} failed: {text}")
        item = check_fragment_text(text, project_dir / rel)
        scope = item.fragment.scope if item.fragment and item.fragment.scope else Path(rel).stem
        closes = item.fragment.closes if item.fragment else ()
        changes.append(RecordedChange(scope=scope, closes=closes, source="fragment", path=rel, text=text))

    archive_rel = change_log_archive.ARCHIVE_DIR_REL
    code, out = _git(project_dir, "diff", "--name-only", f"{merge_base}..HEAD", "--", archive_rel + "/")
    if code != 0:
        return BranchRecord(error=f"git diff of {archive_rel}/ failed: {out}")
    buckets = [line.strip() for line in out.splitlines() if line.strip().endswith(".md")]
    if buckets:
        known: set[str] = set()
        code, live = _git(project_dir, "show", f"{merge_base}:{change_log_mod.CHANGE_LOG_REL_PATH}")
        if code == 0:
            known.update(block.key for block in change_log_archive.split(live)[1])
        for rel in buckets:
            code, old = _git(project_dir, "show", f"{merge_base}:{rel}")
            if code == 0:
                known.update(block.key for block in change_log_archive.split(old)[1])
        for rel in buckets:
            code, new = _git(project_dir, "show", f"HEAD:{rel}")
            if code != 0:
                continue  # the branch deleted the bucket; it added nothing there
            for block in change_log_archive.split(new)[1]:
                if block.key in known:
                    continue
                change = _archived_change(block.text, rel)
                if change is not None:
                    changes.append(change)
    return BranchRecord(changes=tuple(changes))


def scope_change_record(project_dir: Path, scope: str) -> RecordedChange | None:
    """A scope's change record on the current tree: its pending fragment, or,
    once cut, its newest archive entry. For readers that run after the merge,
    when no branch diff is left to ask (the Merge Flow's close)."""
    from . import change_log_archive  # noqa: PLC0415 — the archive's splitter owns entry boundaries

    path = project_dir / FRAGMENT_DIR_REL / f"{scope}.md"
    if path.is_file():
        item = read_fragment_file(path)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            text = ""
        closes = item.fragment.closes if item.fragment else ()
        return RecordedChange(
            scope=scope, closes=closes, source="fragment", path=f"{FRAGMENT_DIR_REL}/{scope}.md", text=text
        )
    found: RecordedChange | None = None
    newest = ""
    directory = project_dir / ".prawduct" / change_log_archive.ARCHIVE_DIR_NAME
    for bucket in sorted(directory.glob("*.md")) if directory.is_dir() else []:
        try:
            content = bucket.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            import sys  # noqa: PLC0415 — lazy; only this rare path writes to stderr

            print(f"NOTE: could not read {bucket.name} ({exc}); a record there was not searched.", file=sys.stderr)
            continue
        for block in change_log_archive.split(content)[1]:
            change = _archived_change(block.text, f"{change_log_archive.ARCHIVE_DIR_REL}/{bucket.name}")
            if change is not None and change.scope == scope and (block.date or "") >= newest:
                found, newest = change, block.date or ""
    return found


def change_record_cmd(project_dir: Path, argv: list[str]) -> int:
    """``change-record <scope>... [--json]``: each scope's record and what it closes.

    Exit 0 when every scope has a record, 1 when one has none (it is named), 2
    on a usage error. Reads the current tree only, so it answers after a merge.
    """
    import json  # noqa: PLC0415 — lazy; only this command prints JSON
    import sys  # noqa: PLC0415 — lazy, for the same reason

    as_json = "--json" in argv
    scopes = [arg for arg in argv if arg != "--json"]
    if not scopes or any(arg.startswith("-") for arg in scopes):
        print("usage: change-record <scope>... [--json]", file=sys.stderr)
        return 2
    records = {scope: scope_change_record(project_dir, scope) for scope in scopes}
    if as_json:
        print(json.dumps({
            scope: None if r is None else {"source": r.source, "path": r.path, "closes": list(r.closes)}
            for scope, r in records.items()
        }))
    else:
        for scope, r in records.items():
            if r is None:
                print(f"{scope}: no record — no fragment and no archive entry with this scope")
            else:
                print(f"{scope}: {r.source} {r.path}; closes: {', '.join(r.closes) or 'nothing'}")
    return 0 if all(r is not None for r in records.values()) else 1


def _frontmatter_value(value: str) -> str:
    """``value`` spelled so :func:`parse_fragment` reads it back unchanged.

    Quoted only when it must be: a value that would read as a list, a comment,
    or lose surrounding quotes or whitespace.
    """
    needs_quotes = (
        value != value.strip()
        or (value.startswith("[") and value.endswith("]"))
        or value[:1] in ("'", '"', "#")
        or " #" in value
        or "\t#" in value
    )
    if not needs_quotes:
        return value
    quote = "'" if '"' in value else '"'
    return f"{quote}{value}{quote}"


def render_fragment(
    *,
    kind: str,
    scope: str,
    date: str,
    title: str,
    narrative: str,
    consumer_note: str,
    closes: tuple[str, ...] = (),
    reopens: str | None = None,
) -> str:
    """The text of a fragment file holding these values. Nothing is validated here."""
    lines = ["---", f"schema: {SCHEMA_VERSION}", f"type: {kind}", f"scope: {scope}", f"date: {date}"]
    lines.append(f"title: {_frontmatter_value(title)}")
    if closes:
        lines.append(f"closes: [{', '.join(closes)}]")
    if reopens:
        lines.append(f"reopens: {reopens}")
    lines.append("---")
    return "\n".join(lines) + f"\n{narrative.strip()}\n\n{CONSUMER_NOTE_HEADING}\n{consumer_note.strip()}\n"


#: Legacy ``type=`` spellings of a member of :data:`TYPES`. Normalised once, when
#: an entry becomes a fragment, so the closed set never has to accept them.
LEGACY_TYPE_SYNONYMS = {
    "feat": "feature",
    "improvement": "feature",
    "bugfix": "fix",
    "bug": "fix",
    "documentation": "docs",
    "optimization": "perf",
    "performance": "perf",
    "debt-paydown": "refactor",
    "tooling": "chore",
    "test": "chore",
    "tests": "chore",
    "ci": "chore",
    "infra": "chore",
    "maintenance": "chore",
    "cleanup": "chore",
}

#: The consumer note a migrated entry gets. The legacy log had no consumer note,
#: so whether consumers need one is still the author's call; ``none:`` keeps the
#: fragment valid, and the cut's dry run lists the reason for the release operator.
MIGRATED_NOTE = (
    "none: migrated from the legacy change log, which held no consumer note; "
    "replace this line with the note if consumers need one"
)

#: ``## date: title``, and the dash spellings real logs also use (``## date — title``).
#: A dash needs space on both sides, so a hyphenated title is never split.
_LEGACY_HEADER_RE = re.compile(r"(\d{4}-\d{2}-\d{2})(?::\s*|\s+[—–-]\s+)(.+)")
_LEGACY_KEYS = ("type", "scope")


@dataclass(frozen=True)
class LegacyConversion:
    """What converting a legacy log's release-pending entries would produce.

    ``fragments`` pairs each scope with its fragment's text, and ``remaining`` is
    the log without those entries. When ``refusals`` is non-empty the caller
    writes nothing: ``fragments`` is then empty and ``remaining`` is the log as given.
    """

    fragments: tuple[tuple[str, str], ...]
    remaining: str
    refusals: tuple[Problem, ...]
    #: ``(scope, the legacy type or "")`` for every converted entry that took the
    #: caller's default type, so the operator sees each guess the default made.
    defaulted: tuple[tuple[str, str], ...] = ()
    #: Every scope after the first in an entry holding several changes
    #: (:func:`_separate_changes`). The legacy reader saw only the first, so these
    #: join the pending set here, and the operator is shown each one.
    split: tuple[str, ...] = ()


def _legacy_tags_line(extra: dict[str, object]) -> str:
    """The keys a fragment has no field for, kept as a line of its narrative."""
    parts = []
    for key in sorted(extra):
        value = extra[key]
        parts.append(f"{key}={', '.join(map(str, value)) if isinstance(value, list) else value}")
    return "Legacy tags: " + "; ".join(parts)


@dataclass(frozen=True)
class _PendingEntry:
    """One release-pending legacy entry, read and ready to render."""

    where: str
    scope: str
    legacy_type: str
    date: str
    title: str
    body: str
    #: Tag keys a fragment has no field for; rendered as the ``Legacy tags:`` line.
    extra: dict[str, object]

    def narrative(self, kind: str) -> str:
        """The body plus its ``Legacy tags:`` line, recording a ``type`` the
        fragment's own ``kind`` does not carry, so a merge or a default loses it
        nowhere."""
        extra = dict(self.extra)
        if self.legacy_type and LEGACY_TYPE_SYNONYMS.get(self.legacy_type, self.legacy_type) != kind:
            extra["type"] = self.legacy_type
        if not extra:
            return self.body
        line = _legacy_tags_line(extra)
        return f"{self.body}\n\n{line}" if self.body else line


def _separate_changes(entry_text: str) -> list[change_log_mod.TagSection] | None:
    """The changes one legacy entry holds, when it holds several; ``None`` when unsure.

    Some logs record two or three changes under one header, each a tag line over
    its own paragraph. The legacy reader merged those tag lines first-wins, so
    every scope after the first was pending to nobody; one fragment per section
    records each change as its author wrote it.

    The same text shape also comes from a union merge of one entry edited on two
    branches, whose second tag line is a version of the first and owns no prose.
    So an entry separates only when nothing but blank lines precedes its first tag
    line, every section has prose of its own, and every section names its own
    scope. Anything else still needs its author to say which tag line is meant.
    """
    lead, sections = change_log_mod.tag_sections(entry_text)
    if lead or len(sections) < 2 or not all(s.body for s in sections):
        return None
    scopes = [s.tags.get("scope") for s in sections]
    if not all(isinstance(sc, str) and sc for sc in scopes) or len(set(scopes)) != len(scopes):
        return None
    return sections


def legacy_entries_as_fragments(text: str, *, default_type: str | None = None) -> LegacyConversion:
    """Convert every release-pending entry of a legacy change log into a fragment.

    An entry is release-pending when it has a tag line and no ``release=``, the
    legacy gate's own definition. Shipped entries and untagged ones stay in the
    log as they are, because archived history is never rewritten.

    What real logs carry is converted rather than refused, because nothing is
    lost: a tag key a fragment has no field for (the retired ``chunks=`` and
    ``status=``, and the occasional ``issues=``) becomes a ``Legacy tags:`` line of
    the narrative; a header written ``## date — title`` reads like ``## date: title``;
    and several pending entries sharing a scope become that scope's one fragment,
    each under its own ``###`` heading, newest first, the way the log ordered them.
    An entry holding several changes, each a tag line over its own paragraph,
    converts as one entry per change (:func:`_separate_changes`), each scope the
    legacy reader did not see listed in ``split``.

    A ``type`` is the one value that cannot be read off the entry when it is
    missing or names no member of the closed set after normalising synonyms.
    Those are refused unless the caller passes ``default_type``, one decision for
    every such entry, and each entry that took it is listed in ``defaulted``.

    What is still refused, each an entry its author must decide about: a
    ``release=`` that is not a version (a placeholder hides a scope from the
    release gate, and the author knows whether it shipped), two tag lines that do
    not separate into changes or conflicting tags (which value is meant is
    unknown), a missing ``scope``, a
    header with no date, and any entry whose fragment would not validate or read
    back as written.
    """
    from . import change_log_archive  # noqa: PLC0415 — the archive's splitter owns entry boundaries

    if default_type is not None and default_type not in TYPES:
        raise ValueError(f"default_type must be one of {', '.join(TYPES)}, got {default_type!r}")
    preamble, blocks = change_log_archive.split(text)
    refusals: list[Problem] = []
    kept: list[str] = []
    groups: dict[str, list[_PendingEntry]] = {}
    split: list[str] = []
    for block in blocks:
        entry = block.entry
        where = f"entry {entry.title!r} (line {entry.line_number})"
        release = entry.tags.get("release")
        if release is not None:
            if not (isinstance(release, str) and change_log_mod.RELEASE_VALUE_RE.match(release)):
                refusals.append(
                    Problem(
                        "unreleased-placeholder",
                        f"{where} has release={release!r}, which is not a version: set the version "
                        "it shipped in, or delete the tag if it has not shipped",
                    )
                )
            kept.append(block.text)
            continue
        if entry.tag_line_count == 0:
            # A tag line under the prose is one no reader ever saw. Shipped, it is
            # history and stays; pending, leaving it would strand the change unseen.
            _lead, stranded = change_log_mod.tag_sections(block.text)
            if any("release" not in s.tags for s in stranded):
                refusals.append(
                    Problem(
                        "stranded-tag-line",
                        f"{where} has a tag line below its prose, which no reader sees; "
                        "move it to just under the header",
                    )
                )
            kept.append(block.text)
            continue

        header = _LEGACY_HEADER_RE.fullmatch(entry.title)
        if entry.tag_line_count > 1 or entry.unconsumed_tag_lines:
            sections = _separate_changes(block.text)
            if sections is None:
                refusals.append(Problem("multi-tag-line", f"{where} has more than one tag line; merge them into one"))
                kept.append(block.text)
                continue
            split.extend(s.tags["scope"] for s in sections[1:])  # type: ignore[misc]
        else:
            body = block.text.splitlines()[1:]
            while body and (not body[0].strip() or change_log_mod.TAG_LINE_RE.search(body[0])):
                body.pop(0)
            sections = [change_log_mod.TagSection(entry.tags, tuple(entry.tag_conflicts), "\n".join(body).strip())]
        before = len(refusals)
        for section in sections:
            if section.conflicts:
                refusals.append(
                    Problem("conflicting-tags", f"{where} sets a key twice: {'; '.join(section.conflicts)}")
                )
            if not isinstance(section.tags.get("scope"), str) or not section.tags.get("scope"):
                refusals.append(Problem("missing-scope", f"{where} has a tag line with no scope="))
        if header is None:
            refusals.append(Problem("bad-header", f"{where} is not `## YYYY-MM-DD: title`"))
        if len(refusals) > before:
            kept.append(block.text)
            continue
        assert header is not None

        for section in sections:
            scope, kind = section.tags["scope"], section.tags.get("type")
            assert isinstance(scope, str)
            groups.setdefault(scope, []).append(
                _PendingEntry(
                    where=where,
                    scope=scope,
                    legacy_type=kind if isinstance(kind, str) else "",
                    date=header.group(1),
                    title=header.group(2).strip(),
                    body=section.body,
                    extra={k: v for k, v in section.tags.items() if k not in _LEGACY_KEYS},
                )
            )
        kept.append("")  # its place in the log; dropped below when the scope converts

    converted: list[tuple[str, str]] = []
    defaulted: list[tuple[str, str]] = []
    for scope, entries in groups.items():
        newest = entries[0]
        # The newest entry that names a type in the closed set decides it; the
        # others keep theirs in their own `Legacy tags:` line.
        typed = [
            LEGACY_TYPE_SYNONYMS.get(e.legacy_type, e.legacy_type)
            for e in entries
            if LEGACY_TYPE_SYNONYMS.get(e.legacy_type, e.legacy_type) in TYPES
        ]
        if typed:
            normalised = typed[0]
        elif default_type is not None:
            defaulted.append((scope, newest.legacy_type))
            normalised = default_type
        elif not newest.legacy_type:
            refusals.append(Problem("missing-type", f"{newest.where} has no type="))
            continue
        else:
            normalised = newest.legacy_type  # the validator below names the closed set
        if len(entries) == 1:
            narrative = newest.narrative(normalised)
        else:
            narrative = "\n\n".join(
                f"### {e.date}: {e.title}\n\n{e.narrative(normalised)}".rstrip() for e in entries
            )
        rendered = render_fragment(
            kind=normalised, scope=scope, date=newest.date, title=newest.title,
            narrative=narrative, consumer_note=MIGRATED_NOTE,
        )
        checked = check_fragment_text(rendered, Path(f"{scope}.md"))
        if checked.problems:
            refusals.extend(Problem(p.code, f"{newest.where}: {p.detail}") for p in checked.problems)
            continue
        assert checked.fragment is not None
        if checked.fragment.title != newest.title or checked.fragment.narrative != narrative.strip():
            refusals.append(
                Problem("unrepresentable", f"{newest.where} would not read back from a fragment as written")
            )
            continue
        converted.append((scope, rendered))

    if refusals:
        return LegacyConversion(fragments=(), remaining=text, refusals=tuple(refusals))
    if not converted:
        return LegacyConversion(fragments=(), remaining=text, refusals=())
    remaining = (preamble + "".join(kept)).rstrip("\n") + "\n"
    return LegacyConversion(
        fragments=tuple(converted), remaining=remaining, refusals=(), defaulted=tuple(defaulted),
        split=tuple(split),
    )
