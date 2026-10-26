"""``retired-claim-survives`` — a retired claim's old wording, found where it survives.

When a governing record retires a claim, the old phrasing keeps living wherever
the author's sweep did not reach. Every correction is a fresh chance to miss a
home, so the sweep cannot be left to the author's attention. This check makes
the literal part mechanical.

**The declaration.** A ``Retires:`` field lists the retired phrasings as
double-quoted strings; prose around the quotes is ignored. It is read in two
places:

- on a norm entry inside a ``## Direction`` section of any
  ``.prawduct/artifacts/*.md``, as a line-start field (``docs/norms.md`` §
  Anatomy), soft-wrapped like every other field;
- as a ``retires:`` list on a ``technical_decisions`` or ``design_decisions``
  entry in ``.prawduct/project-state.yaml``, in flow or block form.

**The search.** Every tracked file is searched, the worktree copy, case-
insensitively, with the phrase's words allowed to wrap across a line break and
a line-leading comment or quote marker. Prose here is hard-wrapped, so a
fixed-string, per-line match misses exactly the survivor that wrapped. Open
backlog issues are searched too, from the local cache, when
``backlog_service_repo`` names the backlog.

**Not survivors:** a ``Retires:`` field anywhere (a declaration, not an
assertion); history (archives, ``.prawduct/changes/``, change-logs, and
``.prawduct/backlog.md`` once ``backlog_service_repo`` freezes it); and any line
acknowledged with ``prawduct:allow prawduct/retired-claim-survives -- <reason>``
on it or the line above, for a site that quotes the claim as its subject, such
as an absence test. Files the current change edits are **not** exempt: they
are the ones the decision is about.

**Coverage, by the five ways a retired claim survives.** It catches:

- *literal survival*: the phrase verbatim, somewhere the sweep did not reach;
- *a survivor inside a file the author is editing*, which a sweep that skips
  its own edits misses;
- *a survivor in the backlog*, which no artifact graph reaches.

It does **not** catch a *paraphrase*. Grep cannot see a restatement;
the complementary control is Critic Goal 4, which reads for the citations a
renamed or removed term leaves behind, and an author can list a known
paraphrase as one more ``Retires:`` phrase. It does **not** catch a finding's
enumerated sites consumed only in part. The complementary control is
``verify-resolutions``, which re-reviews exactly the sites a finding named.

**Repo-wide, unlike record-lint's line checks.** Those read only lines a change
added. This one cannot: its whole subject is text the change did not touch. The
cost is one ``git grep -l`` that narrows the candidates by each phrase's longest
word, then a read of the files it names. A repo that declares nothing pays for
reading the declarations and no more.
"""

from __future__ import annotations

import bisect
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import consumer_digest
from . import waivers
from .core import read_str_yaml_key

CHECK = "retired-claim-survives"
WAIVER_REF = f"prawduct/{CHECK}"

#: A phrase shorter than this, in non-space characters, would match nearly every
#: file. It is reported as a defect in its declaration rather than searched.
_MIN_PHRASE_CHARS = 4

_STATE_REL = ".prawduct/project-state.yaml"
_DECISION_KEYS = ("technical_decisions", "design_decisions")

#: A quoted phrase on a ``Retires:`` line: straight or curly double quotes.
_QUOTED_RE = re.compile(r'"([^"\n]+)"|“([^”\n]+)”')

#: The field marker, tolerant of the same emphasis and blockquote prefixes the
#: norm reader accepts for its own fields.
_RETIRES_FIELD_RE = re.compile(r"^\s*(?:>\s?)*\s*(?:\*{1,2}|_{1,2})?Retires:")

#: ``Retires:`` after other text on the same line — the inline form, not read.
_INLINE_RETIRES_RE = re.compile(r"\S.*?(?:\*{1,2}|_{1,2})?\bRetires:")

#: Sentinel phrases for a declaration that names nothing searchable. Each is
#: reported at its record instead of searched, so an inert field is visible.
_INLINE = "\0inline"

_TOP_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*):")
#: The prefix group spans any ``- `` marker, so its length is the KEY's column:
#: a list under ``  - retires:`` belongs to it only at that column or deeper,
#: and the next record's ``  - name:`` at the dash's column ends it.
_YAML_RETIRES_RE = re.compile(r"^(\s+(?:-\s+)?)retires:\s*(.*?)\s*$")
_YAML_ITEM_RE = re.compile(r"^(\s*)-\s+(.*?)\s*$")

#: Between two words of a phrase: spaces, or a line break optionally followed by
#: a line-leading comment or quote marker, so a copy wrapped inside a comment
#: block or a blockquote is still the same words.
_WORD_SEP = r"[ \t]*(?:\r?\n[ \t]*(?:(?:#+|//+|>+|\*|--)[ \t]*)?|[ \t])[ \t]*"


class _Declaration:
    __slots__ = ("phrase", "record", "line")

    def __init__(self, phrase: str, record: str, line: int) -> None:
        self.phrase = phrase
        self.record = record
        self.line = line

    @property
    def where(self) -> str:
        return f"{self.record}:{self.line}"


def _finding(path: str, line: "int | None", detail: str) -> dict:
    return {"check": CHECK, "path": path, "line": line, "detail": detail}


def _phrases(text: str) -> list[str]:
    return [" ".join((a or b).split()) for a, b in _QUOTED_RE.findall(text) if (a or b).strip()]


# ---------------------------------------------------------------------------
# Declarations
# ---------------------------------------------------------------------------


def _markdown_fields(lines: list[str]) -> "list[tuple[int, int, str]]":
    """Every ``Retires:`` field as ``(first index, last index, joined text)``.

    A field continues onto following lines until a blank line or the next line
    that starts a field or list item: the soft-wrap rule ``norm_probes`` reads
    every norm field by, applied through its own matcher so the two cannot
    disagree about where a field ends.
    """
    from .norm_probes import _BLOCKQUOTE_PREFIX_RE, _FIELD_OR_ITEM_RE  # noqa: PLC0415 — lazy; heavy deps

    fields: list[tuple[int, int, str]] = []
    i = 0
    while i < len(lines):
        if not _RETIRES_FIELD_RE.match(lines[i]):
            i += 1
            continue
        start = i
        joined = _BLOCKQUOTE_PREFIX_RE.sub("", lines[i]).rstrip()
        i += 1
        while i < len(lines):
            line = _BLOCKQUOTE_PREFIX_RE.sub("", lines[i])
            if not line.strip() or _FIELD_OR_ITEM_RE.match(line):
                break
            joined += " " + line.strip()
            i += 1
        fields.append((start, i - 1, joined))
    return fields


def _artifact_declarations(
    project_dir: Path, prawduct_dir: Path
) -> "tuple[list[_Declaration], list[str]]":
    from .norm_probes import _direction_lines  # noqa: PLC0415 — lazy; heavy deps

    declarations: list[_Declaration] = []
    unreadable: list[str] = []
    for path in sorted((prawduct_dir / "artifacts").glob("*.md")):
        rel = _rel(project_dir, path)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            unreadable.append(f"{rel} ({type(exc).__name__})")
            continue
        if "Retires:" not in text:
            continue
        # A field is a declaration only where the norm reader sees it as a line
        # of a Direction section. Asking that reader, rather than tracking
        # headings here as well, keeps one definition of "inside Direction".
        logical = _direction_lines(text)
        direction = {line.strip() for line in logical}
        lines = text.splitlines()
        for start, _end, joined in _markdown_fields(lines):
            if joined.strip() not in direction:
                continue
            phrases = _phrases(joined)
            declarations.extend(_Declaration(p, rel, start + 1) for p in phrases)
            if not phrases:
                declarations.append(_Declaration("", rel, start + 1))
        # The inline form (`- **S.** Detail. Retires: "x"`) is not read; say so
        # where it is written rather than leave it looking like a declaration.
        for entry in logical:
            if _INLINE_RETIRES_RE.search(entry) and not _RETIRES_FIELD_RE.match(entry):
                at = next(
                    (n for n, line in enumerate(lines) if _INLINE_RETIRES_RE.search(line)
                     and not _RETIRES_FIELD_RE.match(line)),
                    None,
                )
                declarations.append(_Declaration(_INLINE, rel, (at or 0) + 1))
    return declarations, unreadable


def _yaml_value_phrases(value: str) -> list[str]:
    """Phrases from a flow list (``["a", 'b']``) or a single scalar."""
    from .record_lint import _split_unquoted, _unquote  # noqa: PLC0415 — the module's YAML posture

    value = _split_unquoted(value, "#")[0].strip()
    if value.startswith("[") and value.endswith("]"):
        items = _split_unquoted(value[1:-1], ",")
    else:
        items = [value]
    return [" ".join(_unquote(item).split()) for item in items if _unquote(item).strip()]


def _state_declarations(
    project_dir: Path,
) -> "tuple[list[_Declaration], set[int], str | None]":
    """``retires:`` lists on decision records, the line indices they occupy, and
    an unreadable reason. Line-based, like every reader of this file: the
    codebase carries no YAML dependency."""
    path = project_dir / _STATE_REL
    if not path.is_file():
        return [], set(), None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return [], set(), f"{_STATE_REL} ({type(exc).__name__})"
    declarations: list[_Declaration] = []
    occupied: set[int] = set()
    top: "str | None" = None
    i = 0
    while i < len(lines):
        line = lines[i]
        key = _TOP_KEY_RE.match(line)
        if key:
            top = key.group(1)
        match = _YAML_RETIRES_RE.match(line) if top in _DECISION_KEYS else None
        if match is None:
            i += 1
            continue
        indent, value = len(match.group(1)), match.group(2)
        occupied.add(i)
        key_line = i + 1
        before = len(declarations)
        if value:
            declarations.extend(
                _Declaration(p, _STATE_REL, i + 1) for p in _yaml_value_phrases(value)
            )
            i += 1
            if len(declarations) == before:
                declarations.append(_Declaration("", _STATE_REL, key_line))
            continue
        i += 1
        while i < len(lines):
            item = _YAML_ITEM_RE.match(lines[i])
            if item is None or len(item.group(1)) < indent:
                break
            occupied.add(i)
            declarations.extend(
                _Declaration(p, _STATE_REL, i + 1) for p in _yaml_value_phrases(item.group(2))
            )
            i += 1
        if len(declarations) == before:
            declarations.append(_Declaration("", _STATE_REL, key_line))
    return declarations, occupied, None


# ---------------------------------------------------------------------------
# The search
# ---------------------------------------------------------------------------


def _pattern(phrase: str) -> "re.Pattern[str]":
    words = phrase.split()
    body = _WORD_SEP.join(re.escape(word) for word in words)
    lead = r"(?<!\w)" if re.match(r"\w", words[0]) else ""
    tail = r"(?!\w)" if re.search(r"\w$", words[-1]) else ""
    return re.compile(lead + body + tail, re.IGNORECASE)


def _key_word(phrase: str) -> str:
    """The phrase's longest word: the cheapest filter that still sees every copy."""
    return max(phrase.split(), key=len)


def _is_history(rel: str, backlog_frozen: bool, digest: "consumer_digest.Declaration | None" = None) -> bool:
    # What the release cut writes is history by what it is, not by its name:
    # a declared changelog called NEWS.md is as append-only as CHANGELOG.md.
    if consumer_digest.is_history(rel, digest):
        return True
    lowered = rel.lower()
    name = lowered.rsplit("/", 1)[-1]
    if "/archive/" in f"/{lowered}" or "change-log-archive/" in lowered:
        return True
    if lowered.startswith(".prawduct/changes/") or "/.prawduct/changes/" in lowered:
        return True
    if name.startswith(("change-log", "changelog")):
        return True
    return backlog_frozen and rel == ".prawduct/backlog.md"


def _candidates(project_dir: Path, words: list[str]) -> "list[str] | None":
    """Tracked text files holding any key word, or None when git cannot answer."""
    args = ["git", "-C", str(project_dir), "grep", "-l", "-I", "-i", "-F", "-z"]
    for word in sorted(set(words)):
        args += ["-e", word]
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode == 1:
        return []
    if proc.returncode != 0:
        return None
    return [rel for rel in proc.stdout.split("\0") if rel]


def _matches(
    text: str, declarations: "list[_Declaration]", excluded: "set[int] | None" = None
) -> "list[tuple[int, _Declaration]]":
    """``(1-based line, declaration)`` for every unexcused copy in ``text``.

    ``excluded`` defaults to the lines of every ``Retires:`` field in ``text``,
    so a declaration is never its own survivor — in a file or in an issue body
    alike. The state file passes its own ``retires:`` spans instead."""
    lines = text.splitlines()
    if excluded is None:
        excluded = {
            i for start, end, _ in _markdown_fields(lines) for i in range(start, end + 1)
        }
    starts = [0]
    for line in text.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    hits: list[tuple[int, _Declaration]] = []
    seen: set[tuple[int, str]] = set()
    for decl in declarations:
        for found in _pattern(decl.phrase).finditer(text):
            index = bisect.bisect_right(starts, found.start()) - 1
            if index in excluded or (index, decl.phrase) in seen:
                continue
            if waivers.waives(lines, index, WAIVER_REF):
                continue
            seen.add((index, decl.phrase))
            hits.append((index + 1, decl))
    return hits


def _detail(decl: _Declaration) -> str:
    return (
        f'"{decl.phrase}" survives; {decl.where} retires it. Rewrite it, or acknowledge a '
        f"quotation with `prawduct:allow {WAIVER_REF} -- <why the quote is the point>`"
    )


def _rel(project_dir: Path, path: Path) -> str:
    try:
        return str(path.relative_to(project_dir))
    except ValueError:
        return str(path)


def _search_files(
    project_dir: Path,
    declarations: "list[_Declaration]",
    state_lines: "set[int]",
    backlog_frozen: bool,
) -> "tuple[list[dict], str | None]":
    rels = _candidates(project_dir, [_key_word(d.phrase) for d in declarations])
    if rels is None:
        return [], f"{CHECK} unchecked — git could not search the tracked files"
    findings: list[dict] = []
    # An invalid declaration names no file the cut writes, so only release files are history.
    digest, _invalid = consumer_digest.read_declaration(project_dir)
    for rel in sorted(rels):
        if _is_history(rel, backlog_frozen, digest):
            continue
        try:
            text = (project_dir / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue  # tracked but deleted in the worktree: nothing survives there
        excluded = state_lines if rel == _STATE_REL else None
        for line, decl in _matches(text, declarations, excluded):
            findings.append(_finding(rel, line, _detail(decl)))
    return findings, None


def _search_backlog(
    project_dir: Path, scope: str, declarations: "list[_Declaration]"
) -> "tuple[list[dict], str | None]":
    from .backlog import cachequery  # noqa: PLC0415 — lazy: only a repo on an issue backlog

    envelope = cachequery.open_items(project_dir, scope=scope, now=datetime.now(timezone.utc))
    if envelope.get("status") != "ok":
        err = envelope.get("error") or {}
        reason = err.get("message") or err.get("code") or "unknown error"
        return [], (
            f"{CHECK} unchecked on the backlog — the cache for {scope} could not be read "
            f"({reason}); run `prawduct-hook backlog sync --repo {scope}`"
        )
    findings: list[dict] = []
    for item in (envelope.get("data") or {}).get("items") or []:
        text = f"{item.get('title') or ''}\n{item.get('body') or ''}"
        hits = _matches(text, declarations)
        for _line, decl in hits:
            findings.append(
                _finding(
                    str(item.get("id")),
                    None,
                    f"open issue “{item.get('title') or ''}”: {_detail(decl)}",
                )
            )
    return findings, None


def check(project_dir: Path, prawduct_dir: Path) -> "tuple[list[dict], list[str], set[str]]":
    """Run the check. Returns ``(findings, unchecked, no_answer)``, the shape
    record-lint's other repo-wide arms return."""
    artifact_decls, unreadable = _artifact_declarations(project_dir, prawduct_dir)
    state_decls, state_lines, state_unreadable = _state_declarations(project_dir)
    if state_unreadable:
        unreadable.append(state_unreadable)

    findings: list[dict] = []
    unchecked: list[str] = []
    if unreadable:
        unchecked.append(
            f"{CHECK} unchecked on {', '.join(unreadable)} — a record that may declare "
            "retired phrases could not be read"
        )

    declarations: list[_Declaration] = []
    for decl in artifact_decls + state_decls:
        if decl.phrase == _INLINE:
            findings.append(
                _finding(
                    decl.record,
                    decl.line,
                    "`Retires:` written inline after the statement is not read; put it on a "
                    "line of its own (`docs/norms.md` § Anatomy)",
                )
            )
            continue
        if not decl.phrase:
            findings.append(
                _finding(
                    decl.record,
                    decl.line,
                    "this retires field names no double-quoted phrase, so nothing is "
                    'searched; quote each retired phrasing (`Retires: "old wording"`)',
                )
            )
            continue
        if len(decl.phrase.replace(" ", "")) < _MIN_PHRASE_CHARS:
            findings.append(
                _finding(
                    decl.record,
                    decl.line,
                    f'"{decl.phrase}" is too short to search; a phrase of a few words '
                    "names a claim, a fragment matches everything",
                )
            )
            continue
        declarations.append(decl)

    if declarations:
        scope = read_str_yaml_key(project_dir / _STATE_REL, "backlog_service_repo")
        file_findings, file_gap = _search_files(
            project_dir, declarations, state_lines, backlog_frozen=bool(scope)
        )
        findings.extend(file_findings)
        if file_gap:
            unchecked.append(file_gap)
        if scope:
            backlog_findings, backlog_gap = _search_backlog(project_dir, scope, declarations)
            findings.extend(backlog_findings)
            if backlog_gap:
                unchecked.append(backlog_gap)

    return findings, unchecked, ({CHECK} if unchecked else set())
