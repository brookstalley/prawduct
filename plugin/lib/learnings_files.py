"""The one resolver for a repo's learnings rules — where they are, which state
the repo is in, and which files apply to a given set of changed paths.

Learnings are ordinary committed ``.claude/rules/`` files, so the **harness**
loads them: ``core.md`` carries no ``paths:`` frontmatter and is in context from
launch; every ``<area>.md`` declares ``paths:`` globs and arrives when Claude
reads a file those globs match. Prawduct therefore builds no retrieval at all.
What it still needs is an *agreement* with the harness about which files exist
and which of them a given diff pulls in — the budget gate must size the same set
the session pays for, and the Critic's cross-check must read the same area files
the harness would have loaded. This module is that agreement, and it is the only
place in the plugin that knows the layout.

**The matcher must agree with the harness's, not merely be reasonable.** A glob
this module reads more narrowly than the harness does is an area file the
reviewer never opens while the session had it in context the whole time — the
cross-check going quietly dark, which is the one failure this layout could
introduce. So :func:`glob_to_regex` implements the documented semantics
literally (``**/`` spans zero or more directories, ``*`` stops at a separator,
patterns are root-relative and anchored), and the frontmatter reader below is
deliberately *stricter* than the build-plan one in ``plan_index``: it accepts a
block only at the very top of the file, because that is the only place the
harness accepts one. Sharing ``plan_index``'s reader would have bought
deduplication at the price of the two disagreeing about what a rules file is,
which is the disagreement that costs the most here.

Layout::

    .claude/rules/learnings/
        core.md          # no `paths:` — always loaded, always first
        <area>.md        # `paths:` globs — loaded on a matching read

The legacy corpus (``.prawduct/learnings.md``) is not read by anything here.
:data:`LEGACY_REL` exists only so :func:`resolve` can report *which of four
states* a repo is in, which is what the migration directive and the Stop floor
are driven from.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

#: The rules directory, repo-relative. Named ``learnings/`` rather than a flat
#: prefix under ``.claude/rules/`` so a repo's own hand-written rules files stay
#: unambiguously theirs — nothing prawduct budgets, migrates or deletes is
#: outside this one directory.
RULES_DIR_REL = ".claude/rules/learnings"

#: The always-loaded file. It carries no ``paths:``, so the harness puts it in
#: context at launch alongside CLAUDE.md; it is the file every session pays for
#: and therefore the one the budget gate exists to keep small.
CORE_NAME = "core.md"

#: The pre-cutover corpus. Read by nothing — its only role is telling the four
#: states apart (see :func:`resolve`).
LEGACY_REL = ".prawduct/learnings.md"

#: Layout states. ``new`` and ``none`` are healthy; ``legacy`` and ``both`` each
#: carry their own directive (a repo to migrate, and a repo whose migration was
#: interrupted or whose branch reintroduced the old file).
STATE_NEW = "new"
STATE_LEGACY = "legacy"
STATE_BOTH = "both"
STATE_NONE = "none"

#: What a scaffolded ``core.md`` opens with. The obligation is here rather than
#: in a pointer because this file is the one thing every session reads: a rule
#: that arrives, is agreed with, and changes nothing is the failure mode a
#: learnings corpus actually has, and the only cure is being asked to say out
#: loud what the rule did to the decision in hand.
CORE_HEADER = (
    "# Learnings — core\n"
    "\n"
    "**Reading a rule is not applying it.** For any rule below that bears on the "
    "decision in front of you, name the rule and say what it changes about that "
    "decision — or say that it does not apply, which is also an answer.\n"
)


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------


def _expand_braces(pattern: str) -> list[str]:
    """``a/{x,y}/b`` → ``["a/x/b", "a/y/b"]``; nested and repeated groups too.

    Expanded at parse time rather than in the matcher so that everything
    downstream — :class:`AreaFile`, the finding text, ``--for-diff`` output —
    deals in plain globs. A reader debugging why a file did or did not load sees
    the pattern that actually matched, not the shorthand it came from.

    An unbalanced brace is left alone and matched literally: a malformed pattern
    should scope its own file oddly, never raise inside session start.
    """
    start = pattern.find("{")
    if start == -1:
        return [pattern]
    depth = 0
    for i in range(start, len(pattern)):
        if pattern[i] == "{":
            depth += 1
        elif pattern[i] == "}":
            depth -= 1
            if depth == 0:
                head, body, tail = pattern[:start], pattern[start + 1 : i], pattern[i + 1 :]
                options = _split_top_level(body)
                out: list[str] = []
                for option in options:
                    out.extend(_expand_braces(head + option + tail))
                return out
    return [pattern]  # unbalanced — literal


def _split_top_level(body: str) -> list[str]:
    """Split on commas that are outside any brace group and outside quotes.

    Serves both brace expansion and the inline ``paths: [a, b]`` form, which is
    why it is not simply ``body.split(",")``: an inline list holding
    ``src/{a,b}/**`` would otherwise be torn into three nonsense globs, each of
    which then silently matches nothing.
    """
    parts: list[str] = []
    depth = 0
    quote = ""
    current: list[str] = []
    for ch in body:
        if quote:
            if ch == quote:
                quote = ""
        elif ch in ("'", '"'):
            quote = ch
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(ch)
    parts.append("".join(current))
    return parts


def _strip_inline_comment(value: str) -> str:
    """Everything before the first comment ``#``, by YAML's own rule.

    A ``#`` opens a comment only when it is unquoted AND at the start or
    preceded by whitespace. Both halves of that are load-bearing here, and each
    was a real under-match:

    * *unquoted* — ``"src/#tmp/**"`` is one glob, not a glob and a comment.
    * *preceded by whitespace* — so is the bare ``src/#tmp/**``. Cutting at any
      unquoted ``#`` would silently truncate it to ``src/``.

    Comment removal happens BEFORE unquoting, never after, because deciding
    "is this quoted" from the last character is wrong the moment a comment
    follows the closing quote — ``- "src/**" # web`` ends in ``b``, reads as
    unquoted, and yields a glob that demands literal quote characters and
    therefore matches no path at all.
    """
    quote = ""
    for i, ch in enumerate(value):
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch == "#" and (i == 0 or value[i - 1].isspace()):
            return value[:i]
    return value


def _inline_list_body(value: str) -> str:
    """The contents of a leading ``[...]``, up to its matching unquoted bracket.

    ``value.strip("[]")`` cannot do this job: it only reaches characters at the
    very ends, so ``["src/**"] # c`` keeps its ``]`` and the glob never matches.
    An unterminated list yields everything after the opening bracket, which
    degrades to "read the globs anyway" rather than raising.
    """
    quote = ""
    depth = 0
    for i, ch in enumerate(value):
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                return value[1:i]
    return value[1:]


def _clean_glob(raw: str) -> str:
    """Strip a list dash, an inline comment, quoting and a leading ``./`` or ``/``.

    In that order — see :func:`_strip_inline_comment` for why the comment must
    go before the quotes. Globs are root-relative, so a leading separator is
    decoration rather than an absolute path; normalising it here means
    ``/src/**`` and ``src/**`` cannot scope the same file differently.
    """
    value = raw.strip()
    if value.startswith("- "):
        value = value[2:]
    elif value == "-":
        return ""
    value = _strip_inline_comment(value).strip()
    if len(value) >= 2 and value[:1] in ("'", '"') and value[-1:] == value[:1]:
        value = value[1:-1]
    while value.startswith("./"):
        value = value[2:]
    return value.lstrip("/")


def parse_frontmatter(text: str) -> tuple[list[str], str]:
    """``(globs, body)`` for a rules file.

    ``globs`` is the ``paths:`` list — block form (``- "src/**"`` on following
    lines) or inline form (``paths: ["a/**", "b/**"]``), quoted or bare, with
    ``{a,b}`` groups expanded. It is empty for a file with no frontmatter and for
    one whose frontmatter declares no ``paths:``; both cases mean the same thing
    to the harness, which loads such a file unconditionally.

    ``body`` is everything after the closing ``---`` (the whole text when there
    is no block), so a caller counting rules or hashing content never has to
    re-find the boundary.

    **The block must open on the first line.** ``plan_index`` tolerates a leading
    HTML-comment header before a build plan's frontmatter because a third of this
    repo's plans have one; that tolerance is wrong here, where the format belongs
    to the harness and a block it would not read must not be read as scoping.
    A file whose frontmatter never closes reads as having none — degrading to
    "always loaded" rather than raising inside session start.
    """
    # `keepends` so ``body`` is a verbatim slice of the input: the migrate
    # command's byte-accounting test asserts that every rule byte of a source
    # file reappears in the output, and a reader that quietly drops a trailing
    # newline would make that accounting wrong by one byte per file.
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return ([], text)
    close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if close is None:
        return ([], text)  # unterminated — no frontmatter, whole file is body
    return (_parse_paths(lines[1:close]), "".join(lines[close + 1 :]))


def _parse_paths(fm: list[str]) -> list[str]:
    """The ``paths:`` value from already-extracted frontmatter lines."""
    raw: list[str] = []
    for index, line in enumerate(fm):
        if line[:1] in (" ", "\t"):
            continue  # nested under another key, not the top-level declaration
        if not line.strip().startswith("paths:"):
            continue
        # The comment goes first, so `paths: # the globs` followed by a block
        # list is recognised as an empty inline value rather than mistaken for a
        # one-glob scalar that then cleans down to nothing.
        inline = _strip_inline_comment(line.split(":", 1)[1]).strip()
        if inline.startswith("["):
            raw.extend(_split_top_level(_inline_list_body(inline)))
        elif inline:
            raw.append(inline)  # `paths: src/**` — a bare scalar, one glob
        else:
            for follower in fm[index + 1 :]:
                if not follower.strip():
                    continue
                if not follower.startswith((" ", "\t", "-")):
                    break  # next top-level key ends the list
                if follower.strip().startswith("#"):
                    continue
                if not follower.strip().startswith("-"):
                    break
                raw.append(follower)
        break
    globs: list[str] = []
    for item in raw:
        cleaned = _clean_glob(item)
        if not cleaned:
            continue
        for expanded in _expand_braces(cleaned):
            if expanded and expanded not in globs:
                globs.append(expanded)
    return globs


# ---------------------------------------------------------------------------
# Globs
# ---------------------------------------------------------------------------

#: Characters a regex would read as syntax and a glob reads as text. ``*`` and
#: ``?`` are handled by the translator; ``[`` is escaped rather than translated
#: into a character class, because the harness documents no bracket syntax and
#: guessing one would make a pattern mean something here that it does not mean
#: where it is actually loaded.
_ESCAPE = set(".^$+(){}[]|\\")


@lru_cache(maxsize=512)
def glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Compile a ``paths:`` glob to an anchored regex over ``/``-joined paths.

    The documented semantics, literally:

    ==============  ===========================================================
    ``**/``         zero or more directories (``**/*.ts`` matches ``a.ts`` and
                    ``src/a.ts``)
    ``**``          anything, separators included (``src/**``)
    ``*``           anything within one segment (``*.md`` is root-level only)
    ``?``           one character within one segment
    ==============  ===========================================================

    Patterns are root-relative and matched whole, so ``src/components/*.tsx``
    matches nothing under ``web/src/components/``. Compiled results are cached:
    a resolve over a large diff re-uses each area's handful of globs once per
    changed path.
    """
    out: list[str] = []
    i = 0
    while i < len(pattern):
        ch = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif ch == "*":
            out.append("[^/]*")
            i += 1
        elif ch == "?":
            out.append("[^/]")
            i += 1
        elif ch in _ESCAPE:
            out.append("\\" + ch)
            i += 1
        else:
            out.append(ch)
            i += 1
    return re.compile("".join(out) + r"\Z")


def _normalize(path: str | Path) -> str:
    text = Path(path).as_posix() if isinstance(path, Path) else str(path).replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def matches(globs: Iterable[str], changed: Iterable[str | Path]) -> bool:
    """True when any glob matches any changed path."""
    paths = [_normalize(p) for p in changed]
    if not paths:
        return False
    for glob in globs:
        rx = glob_to_regex(glob)
        if any(rx.match(p) for p in paths):
            return True
    return False


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AreaFile:
    """One scoped rules file and the globs its frontmatter declares.

    An area with **no** globs is not a broken area — it is a rules file the
    harness loads unconditionally, exactly like ``core.md``. It is reported with
    an empty ``globs`` and :func:`files_for_paths` returns it for every diff, so
    the reviewer reads what the session was actually given.
    """

    path: Path
    globs: list[str] = field(default_factory=list)

    @property
    def always_loaded(self) -> bool:
        return not self.globs


@dataclass(frozen=True)
class Layout:
    """What ``resolve`` found: the state, the core file, the areas, the ordered set.

    ``state`` is one of :data:`STATE_NEW`, :data:`STATE_LEGACY`,
    :data:`STATE_BOTH`, :data:`STATE_NONE`. ``core`` is ``None`` whenever
    ``core.md`` is absent — including in a ``new`` repo whose rules directory
    holds only area files, which is unusual but not an error.

    ``files`` is every rules file, core first then areas in path order: the set
    the budget gate sizes. :func:`files_for_paths` narrows it to what a
    particular diff pulls in.
    """

    state: str
    core: Path | None
    areas: list[AreaFile] = field(default_factory=list)
    files: list[Path] = field(default_factory=list)

    @property
    def migrated(self) -> bool:
        return self.state == STATE_NEW


def _read(path: Path) -> str:
    """A rules file's text, or ``""`` when it cannot be read.

    Unreadable reads as unscoped, so the file still appears in ``files`` and is
    still budgeted. Dropping it would be worse in both directions: silently
    unbudgeted, and silently unread by the cross-check.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def resolve(project_dir: str | Path) -> Layout:
    """The repo's learnings layout.

    The rules directory counts as present when it holds at least one ``.md``
    file, not merely when it exists: git does not track empty directories, so a
    leftover empty one is local debris, and letting it read as ``new`` would
    silence the migration directive for a repo that has migrated nothing.

    Discovery is recursive because the harness loads ``.claude/rules/``
    subdirectories recursively — a nested area file is in context whether or not
    prawduct expected the nesting, and anything in context must be budgeted and
    reviewed.
    """
    root = Path(project_dir)
    rules_dir = root / RULES_DIR_REL
    core_path = rules_dir / CORE_NAME

    found = sorted(
        (p for p in rules_dir.rglob("*.md") if p.is_file()),
        key=lambda p: p.relative_to(rules_dir).as_posix(),
    )
    new_present = bool(found)
    legacy_present = (root / LEGACY_REL).is_file()

    if new_present and legacy_present:
        state = STATE_BOTH
    elif new_present:
        state = STATE_NEW
    elif legacy_present:
        state = STATE_LEGACY
    else:
        state = STATE_NONE

    core = core_path if core_path in found else None
    areas = [
        AreaFile(path=p, globs=parse_frontmatter(_read(p))[0])
        for p in found
        if p != core_path
    ]
    files = ([core] if core is not None else []) + [a.path for a in areas]
    return Layout(state=state, core=core, areas=areas, files=files)


def files_for_paths(layout: Layout, changed: Iterable[str | Path]) -> list[Path]:
    """The rules files a diff over ``changed`` puts in context, in read order.

    Core first, then each area whose globs intersect ``changed`` — plus any area
    that declares no globs, which the harness loads unconditionally. An empty
    ``changed`` therefore yields the always-loaded set, which is the honest
    answer for a session with no diff rather than an empty list.
    """
    paths = [_normalize(p) for p in changed]
    out: list[Path] = []
    if layout.core is not None:
        out.append(layout.core)
    for area in layout.areas:
        if area.always_loaded or matches(area.globs, paths):
            out.append(area.path)
    return out


def scaffold_core(project_dir: str | Path) -> Path:
    """Create ``.claude/rules/learnings/core.md`` with :data:`CORE_HEADER`.

    Returns the path either way. **Never overwrites**: this is a product's own
    authored corpus from its second session onward, and a scaffold that rewrites
    it on a re-run of onboarding or a repair would delete rules nobody has a copy
    of. Absence is the only trigger.
    """
    path = Path(project_dir) / RULES_DIR_REL / CORE_NAME
    if not path.is_file():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(CORE_HEADER, encoding="utf-8")
    return path
